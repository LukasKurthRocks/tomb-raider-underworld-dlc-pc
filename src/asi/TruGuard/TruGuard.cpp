// TruGuard.asi - exception diagnostics for the tru.exe of Tomb Raider: Underworld (Steam, image base 0x400000).
//
// Developer tool for the DLC port (docs/TruGuard-Plan.md): the Xbox -> PC data conversion keeps producing single
// badly converted fields (a value read as a pointer, a D3D call that fails, a list that runs away). Each one shows
// up as a crash, and a cdb run finds exactly one per session. TruGuard watches the game process itself:
//
//   1. It catches access violations (and a few other faults) raised in the code of tru.exe. Faults in our own
//      plugins are ignored (their address is outside the tru.exe image), so the guarded SEH probes of the other
//      ASIs do not flood the log.
//   2. Every fault site is logged once with everything needed to identify it: tru.exe offset and instruction bytes,
//      registers, the EBP stack chain (module + offset, plus the names of the crash sites we already know), the
//      memory around the fault address and the involved registers, the current unit and the player object. One
//      minidump per site (Dump=1).
//   3. Optional: after a bad data access the game is resumed, so one test run shows several broken places in a row.
//      Per-site rules in TruGuard.ini say how many bytes to skip and what to put in eax / ecx, with a hit limit per
//      site and a fallback to "let it crash"; a generic instruction-length decoder covers faults without a rule.
//      Off by default (Mode=1); Mode=2 enables it.
//   4. Results are readable in game: TruMenu lists the plugin (status.plugins) and truelink answers over the local
//      TCP channel; TruGuardStatus / TruGuardLast / TruGuardCount / TruGuardDistinct are exported for both.
//   5. On demand (TruLink "menu guard.dump", menu row): a full dump plus a snapshot of every thread, also for a
//      hung game - no exception needed. The last faults are kept in a small ring and printed with a fatal record.
//
// The log is written with a pre-opened HANDLE (WriteFile, FILE_APPEND_DATA); the handler does not allocate and uses
// only VirtualQuery-protected reads. A spin lock plus a single-handler flag serialize the main record; a fault on a
// second thread while one is already handling is counted/dropped (VEH) or waits briefly (unhandled filter). If the
// lock is busy the line is still written (worst case interleaved) - a deadlock in a crash handler would be worse. The static
// CRT formatters are used, so "no heap / no CRT locks" is not a hard guarantee. MiniDumpWriteDump is loaded from
// dbghelp.dll at start and called inside the handler (accepted risk: it can block; Dump / DumpType turn it off).
//
// Scope: local, offline, single player, no anti-cheat. Nothing of this is meant for end users.
//
// 0.1 (2026-11-01) - first build: first-chance VEH, per-site log, optional resume, minidumps, exports.
// 0.3 (2026-11-02) - on-demand dumps, fault ring in the fatal record, "handled" note from the worker, resume safety
//                    (executable target, rate cap) and an [Ignore] list.
// 0.4 (2026-11-02) - GuardRails: plugin event/rail API (TruGuardEvent/TruGuardRail), passive context ring,
//                    optional [GuardRails]/[Watch]/[Rail.*], events in fatal record; no game code patched.
// 0.4 (2026-11-04) - review fixes: reserved fatal site when the table is full, debugger flag in markers, dump begin
//                    line, extra dump info flags, worker skips Toolhelp while a dump is active.
// 0.4.1 (2026-11-04) - review follow-up: wall-clock wait in the UEF, one MaxDumps slot reserved for fatal dumps,
//                      skipped concurrent faults counted in the status.
// 0.4.2 (2026-11-05) - section 9 follow-up: UEF logs fatal faults outside tru.exe (module, thread/start, registers,
//                      EBP frames, tru.exe stack hints); re-arm also happens for outside faults.
// 0.4.2+outside-fix (2026-11-05, patch proposal) - outside record only: guarded by __try in the UEF (a fault in
//                      the logger is swallowed, the crash proceeds unchanged), stack overflow outside tru.exe writes
//                      one pre-built line (no 4 KB frame), start= also as start_mod=<module>+0x<offset>.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <dbghelp.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>

namespace {

const DWORD kImageBaseExpected = 0x00400000;

// game addresses (see TruMenu.cpp / TruLink.cpp; all verified there)
// legacy name: this is the static player/agent block, not the heap GameTracker (see kPlayerState)
const DWORD kGameTracker = 0x00e7f088;  // +0xbc cheatMode (dword), +0x38 unit name
const DWORD kPlayerPtr = 0x00e7f094;    // +0xc player instance
const DWORD kCheatMode = 0x00e7f144;
const DWORD kPlayerState = 0x00fadb58;  // [0xfadb58] = heap GameTracker (legacy log name "playerstate")
const DWORD kUnitName = 0x00e7f0c0;     // static block +0x38 (char[<=64])
const DWORD kUnitId = 0x00e7f148;
const DWORD kAgent528 = 0x3ed;          // agent byte read by condition 528

// crash sites already identified in docs/ (offset relative to tru.exe) - used to name eip and stack frames
struct Known {
    DWORD offset;
    const char *name;
};
const Known kKnown[] = {
    {0x017ce95, "script interpreter loop"},
    {0x017dbf3, "script op4f: string compare"},
    {0x017de34, "script native call"},
    {0x017dea3, "script native call: mov ecx,[ecx+14]"},
    {0x017deae, "script native call: call ecx (NULL native)"},
    {0x014df80, "object lookup"},
    {0x014df8f, "object lookup: cmp byte [eax+4],0"},
    {0x0385265, "state machine: cmp di,[edx]"},
    {0x0385600, "state machine: node register"},
    {0x0385742, "state machine: null-node path"},
    {0x0385dc6, "state machine: mov edx,[edi+4c]"},
    {0x0193659, "event list: mov ecx,[edi+8]"},
    {0x01260e0, "shader empty slot"},
    {0x0124c50, "D3D resource failure handler"},
    {0x0382140, "condition default handler"},
    {0x05ce569, "SCCondTest markup"},
    {0x0785cc0, "node reader"},
    {0x007ae57, "D3D error message box"},
};

// options (TruGuard.ini)
int g_enabled = 1;
int g_logLevel = 1;      // 0 errors, 1 sites + unhandled + resume, 2 first-chance repeats, 3 everything
volatile LONG g_mode = 1;  // 0 log only, 1 log + dump, 2 log + dump + resume where a rule/decoder allows it
int g_firstChance = 1;   // log a one-line note for faults that the game may handle itself
int g_firstChanceDetail = 1;  // write the full record at first chance (once per site), even if the game handles it
int g_firstChanceDump = 0;    // also write the minidump at first chance (expensive: only for fault hunts)
int g_dump = 1;
int g_dumpType = 1;      // 0 none, 1 mini (thread info, indirect references, data segments), 2 full memory
int g_maxDumps = 16;
int g_maxHitsPerSite = 8;
int g_skipUnknown = 0;   // decode the instruction and skip it when no Site rule matches
int g_allowWriteSkip = 1;
int g_allowExecuteSkip = 1;
int g_logStack = 1;
int g_logContext = 1;
int g_handledNote = 1;             // worker: one line per site if no unhandled filter call follows within 2 s
int g_outsideFatal = 1;            // UEF: log a short record for fatal faults outside tru.exe
int g_maxResumesPerSecond = 20;    // 0 = no cap; stops a Mode=2 fault storm from looping
int g_guardRails = 1;              // passive context/event/rail support (no game patch)
int g_railEvents = 1;              // store TruGuardEvent calls and print them at LogLevel 2
int g_attachPendingNote = 1;       // one TRUGUARD_RAIL line when box != 0 but attach box == 0

// site rules: [Sites] Site1=offset,skip,eax,ecx,limit (+ optional 6th field: "w" allow write skip / "x" allow
// execute skip; empty = global). skip < 0 = generic decoder, skip = 0 = never resume.
struct Rule {
    DWORD offset;
    int skip;
    int eax, ecx;
    int limit;
    int allowWrite, allowExec;
};
const int kMaxRules = 32;
Rule g_rules[kMaxRules];
volatile LONG g_ruleCount = 0;

// per-site statistics
struct Site {
    DWORD offset;
    volatile LONG hits;
    volatile LONG detailed;
    volatile LONG dumped;
    volatile LONG fatalDumped;  // a fatal hit gets one extra dump even if the first-chance dump exists
    volatile LONG failed;   // the dump attempt failed: markers say dump=failed instead of dump=earlier
    volatile LONG unhandled;    // the unhandled filter saw this site: it was not handled by the game
    volatile LONG handledNoted; // worker printed the TRUGUARD_HANDLED line for this site
    volatile LONG ignored;      // [Ignore] list: no first-chance lines / detail (a fatal record is still written)
    volatile LONG resumed;      // the guard skipped it instead of the game handling it
    DWORD lastTick, code, access, fault, thread;
};
const int kMaxSites = 64;
const int kFatalSite = kMaxSites;   // reserve slot: a fatal hit still gets a record when the table is full
Site g_sites[kMaxSites + 1];
volatile LONG g_siteCount = 0;
volatile LONG g_siteFullNoted = 0;

// fault ring: the last few faults of the run, appended to a fatal record (the current fault is the newest entry)
struct Fault {
    DWORD tick;
    DWORD offset;
    DWORD code;
    DWORD access;
    DWORD fault;
    DWORD thread;
};
const int kRingSize = 16;
Fault g_ring[kRingSize];
volatile LONG g_ringCount = 0;
volatile LONG g_ringSeq = 0;

// GuardRails: a passive context ring and a ring of plugin events. Neither patches game code; both are only
// read by the reporter. The rail table is the policy the plugins ask for before they take their safe action.
struct Rail {
    int id;
    const char *name;
    int action;          // 0 off, 1 log, 2 block
    int limit;           // max TRUGUARD_RAIL lines; the return value is not limited
    volatile LONG hits;
};
Rail g_rails[] = {
    {1, "state572_attach", 1, 1, 0},
    {2, "point_on_box", 1, 1, 0},
    {3, "slot8_box", 1, 1, 0},
};
const int kRailCount = static_cast<int>(sizeof(g_rails) / sizeof(g_rails[0]));
volatile LONG g_unknownRailNoted = 0;

struct ContextSample {
    DWORD tick;
    DWORD gameTracker;
    DWORD agent;
    DWORD box;
    DWORD attachBox;
    DWORD agent528;
};
const int kContextSize = 32;
ContextSample g_context[kContextSize];
volatile LONG g_contextCount = 0;
volatile LONG g_contextSeq = 0;
volatile LONG g_contextFaulted = 0;   // a TOCTOU read faulted: stop sampling, keep the rail API alive

struct Event {
    DWORD tick;
    int id;
    DWORD a, b, c;
    DWORD thread;
};
const int kEventSize = 32;
Event g_events[kEventSize];
volatile LONG g_eventCount = 0;
volatile LONG g_eventSeq = 0;

// [Ignore] list: offsets whose first-chance faults are only counted, never logged
const int kMaxIgnores = 32;
DWORD g_ignores[kMaxIgnores];
volatile LONG g_ignoreCount = 0;

volatile LONG g_firstChanceCount = 0;
volatile LONG g_unhandledCount = 0;
volatile LONG g_resumedCount = 0;
volatile LONG g_dumpCount = 0;
volatile LONG g_detailCount = 0;
volatile LONG g_inHandler = 0;
volatile LONG g_handlerDropped = 0;
volatile LONG g_handlerBusy = 0;   // faults skipped because another handler was already running
volatile LONG g_stackNoted = 0;
volatile LONG g_logSpin = 0;
volatile LONG g_stateSeq = 0;
volatile LONG g_uefNoted = 0;   // the game installs its own filter during init - re-arm note printed once
volatile LONG g_dumping = 0;    // MiniDumpWriteDump is not reentrant: one dump at a time
volatile LONG g_manualCount = 0;
volatile LONG g_handledCount = 0;
volatile LONG g_outsideCount = 0;

DWORD g_resumeWindowTick = 0;   // resume rate window (handlers are serialized by g_inHandler)
int g_resumeWindowCount = 0;
volatile LONG g_resumeStopNoted = 0;

char g_selfDir[MAX_PATH];   // plugin / game folder with trailing backslash
char g_logPath[MAX_PATH];
char g_dumpDir[MAX_PATH];
char g_lastDumpPath[MAX_PATH];   // last file written by WriteDump (handlers are serialized by g_inHandler)
char g_runId[32];
char g_lastText[512];
HANDLE g_log = INVALID_HANDLE_VALUE;
DWORD g_truBase = 0, g_truEnd = 0;
DWORD g_startTick = 0;
HANDLE g_stop = nullptr;

typedef BOOL(WINAPI *MiniDumpWriteDumpFn)(HANDLE, DWORD, HANDLE, MINIDUMP_TYPE, PMINIDUMP_EXCEPTION_INFORMATION,
                                          PMINIDUMP_USER_STREAM_INFORMATION, PMINIDUMP_CALLBACK_INFORMATION);
MiniDumpWriteDumpFn g_miniDump = nullptr;

typedef LONG(NTAPI *NtQueryInformationThreadFn)(HANDLE, ULONG, PVOID, ULONG, PULONG);
const ULONG kThreadQuerySetWin32StartAddress = 9;

// module snapshot: the writer fills the inactive buffer and flips the index, readers never lock
struct ModEntry {
    DWORD base, size;
    char name[48];
};
const int kMaxMods = 192;
ModEntry g_mods[2][kMaxMods];
volatile LONG g_modCount[2] = {0, 0};
volatile LONG g_modActive = 0;

// ---- small helpers -------------------------------------------------------------------------------------------

bool Readable(DWORD protect) {
    if (protect & (PAGE_NOACCESS | PAGE_GUARD)) return false;
    return (protect & (PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE |
                       PAGE_EXECUTE_WRITECOPY)) != 0;
}

DWORD SafeReadSome(DWORD address, void *dst, DWORD length) {
    DWORD done = 0;
    while (done < length) {
        DWORD current = address + done;
        MEMORY_BASIC_INFORMATION mbi;
        if (VirtualQuery(reinterpret_cast<const void *>(static_cast<UINT_PTR>(current)), &mbi, sizeof(mbi)) == 0) break;
        if (mbi.State != MEM_COMMIT || !Readable(mbi.Protect)) break;
        DWORD end = static_cast<DWORD>(reinterpret_cast<UINT_PTR>(mbi.BaseAddress) + mbi.RegionSize);
        if (end <= current) break;
        DWORD chunk = length - done;
        if (end - current < chunk) chunk = end - current;
        memcpy(static_cast<BYTE *>(dst) + done, reinterpret_cast<const void *>(static_cast<UINT_PTR>(current)), chunk);
        done += chunk;
    }
    return done;
}

bool SafeRead(DWORD address, void *dst, DWORD length) { return SafeReadSome(address, dst, length) == length; }

bool SafeString(DWORD address, char *out, int capacity) {
    out[0] = 0;
    if (!address || capacity <= 1) return false;
    int i = 0;
    while (i < capacity - 1) {
        BYTE buffer[32];
        DWORD want = static_cast<DWORD>(capacity - 1 - i);
        if (want > sizeof(buffer)) want = sizeof(buffer);
        DWORD got = SafeReadSome(address + static_cast<DWORD>(i), buffer, want);
        if (!got) { out[i] = 0; return i > 0; }
        for (DWORD k = 0; k < got; ++k) {
            if (!buffer[k]) { out[i + k] = 0; return true; }
            out[i + k] = static_cast<char>(buffer[k]);
        }
        i += static_cast<int>(got);
    }
    out[capacity - 1] = 0;
    return true;
}

bool ModuleOfLive(DWORD address, char *name, size_t capacity, DWORD *offset) {
    MEMORY_BASIC_INFORMATION mbi;
    if (VirtualQuery(reinterpret_cast<const void *>(static_cast<UINT_PTR>(address)), &mbi, sizeof(mbi)) == 0) return false;
    if (mbi.Type != MEM_IMAGE || !mbi.AllocationBase) return false;
    char path[MAX_PATH];
    DWORD length = GetModuleFileNameA(static_cast<HMODULE>(mbi.AllocationBase), path, MAX_PATH);
    if (!length || length >= MAX_PATH) return false;
    char *base = path;
    for (char *p = path; *p; ++p)
        if (*p == '\\' || *p == '/') base = p + 1;
    strncpy_s(name, capacity, base, _TRUNCATE);
    *offset = address - static_cast<DWORD>(reinterpret_cast<UINT_PTR>(mbi.AllocationBase));
    return true;
}

bool ModuleOf(DWORD address, char *name, size_t capacity, DWORD *offset) {
    LONG active = g_modActive;
    LONG count = g_modCount[active];
    for (LONG i = 0; i < count && i < kMaxMods; ++i) {
        const ModEntry &m = g_mods[active][i];
        if (m.size && address >= m.base && address < m.base + m.size) {
            strncpy_s(name, capacity, m.name, _TRUNCATE);
            *offset = address - m.base;
            return true;
        }
    }
    if (g_truBase && address >= g_truBase && address < g_truEnd) {
        strncpy_s(name, capacity, "tru.exe", _TRUNCATE);
        *offset = address - g_truBase;
        return true;
    }
    return ModuleOfLive(address, name, capacity, offset);
}

DWORD ThreadStartAddress() {
    HMODULE ntdll = GetModuleHandleA("ntdll.dll");
    if (!ntdll) return 0;
    NtQueryInformationThreadFn query =
        reinterpret_cast<NtQueryInformationThreadFn>(GetProcAddress(ntdll, "NtQueryInformationThread"));
    if (!query) return 0;
    DWORD start = 0;
    LONG status = query(GetCurrentThread(), kThreadQuerySetWin32StartAddress, &start, sizeof(start), nullptr);
    return status >= 0 ? start : 0;
}

void KnownName(DWORD offset, char *out, size_t capacity) {
    out[0] = 0;
    const Known *best = nullptr;
    for (const Known &k : kKnown)
        if (k.offset <= offset && (!best || k.offset > best->offset)) best = &k;
    if (!best) return;
    DWORD delta = offset - best->offset;
    if (delta == 0) strncpy_s(out, capacity, best->name, _TRUNCATE);
    else if (delta <= 0x100) _snprintf_s(out, capacity, _TRUNCATE, "%s+0x%lx", best->name, delta);
}

bool LockSpin() {
    for (int i = 0; i < 4000; ++i) {
        if (InterlockedCompareExchange(&g_logSpin, 1, 0) == 0) return true;
        YieldProcessor();
    }
    // fall through: write anyway, an interleaved line beats a hang - and never unlock a foreign lock
    return false;
}

void UnlockSpin() { InterlockedExchange(&g_logSpin, 0); }

void WriteRaw(const char *text, size_t length) {
    if (g_log == INVALID_HANDLE_VALUE || !length) return;
    DWORD written = 0;
    WriteFile(g_log, text, static_cast<DWORD>(length), &written, nullptr);
}

void LogV(int level, const char *fmt, va_list ap) {
    if (level > g_logLevel || g_log == INVALID_HANDLE_VALUE) return;
    char line[1024];
    SYSTEMTIME t;
    GetLocalTime(&t);
    int n = _snprintf_s(line, sizeof(line), _TRUNCATE, "%02u:%02u:%02u.%03u ", t.wHour, t.wMinute, t.wSecond,
                        t.wMilliseconds);
    if (n < 0) n = 0;
    _vsnprintf_s(line + n, sizeof(line) - n, _TRUNCATE, fmt, ap);
    size_t used = strlen(line);
    if (used + 1 < sizeof(line)) { line[used++] = '\n'; line[used] = 0; }
    bool locked = LockSpin();
    WriteRaw(line, used);
    if (locked) UnlockSpin();
}

void Log(int level, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    LogV(level, fmt, ap);
    va_end(ap);
}

struct Buf {
    char *data;
    size_t cap, used;
    void add(const char *fmt, ...) {
        if (used >= cap) return;
        va_list ap;
        va_start(ap, fmt);
        int w = _vsnprintf_s(data + used, cap - used, _TRUNCATE, fmt, ap);
        va_end(ap);
        if (w < 0) used = cap;
        else used += static_cast<size_t>(w);
    }
    void finish() {
        if (used < cap) data[used] = 0;
        else data[cap - 1] = 0;
        used = strlen(data);
        if (used + 1 < cap) { data[used++] = '\n'; data[used] = 0; }
    }
};

// ---- x86 instruction length (32 bit) -------------------------------------------------------------------------

int ModRmBytes(const BYTE *p, int available, bool address16) {
    if (available < 1) return 0;
    BYTE modrm = p[0];
    int mod = modrm >> 6, rm = modrm & 7;
    int n = 1;
    if (mod == 3) return n;
    if (address16) {
        if (mod == 0 && rm == 6) n += 2;
        else if (mod == 1) n += 1;
        else if (mod == 2) n += 2;
        return n;
    }
    if (rm == 4) {
        if (available < 2) return 0;
        BYTE sib = p[1];
        int base = sib & 7;
        n += 1;
        if (mod == 0 && base == 5) n += 4;
    } else if (mod == 0 && rm == 5) {
        n += 4;
    }
    if (mod == 1) n += 1;
    else if (mod == 2) n += 4;
    return n;
}

// returns the length in bytes (1..15) or 0 if the bytes are not a valid / known encoding
int InstructionLength(const BYTE *code, int available) {
    const BYTE *p = code;
    int left = available;
    bool opsize16 = false, address16 = false;
    for (;;) {
        if (left < 1) return 0;
        BYTE b = *p;
        if (b == 0x66) { opsize16 = true; ++p; --left; continue; }
        if (b == 0x67) { address16 = true; ++p; --left; continue; }
        if (b == 0xF0 || b == 0xF2 || b == 0xF3) { ++p; --left; continue; }
        if (b == 0x2E || b == 0x36 || b == 0x3E || b == 0x26 || b == 0x64 || b == 0x65) { ++p; --left; continue; }
        break;
    }
    if (static_cast<int>(p - code) > 15) return 0;
    BYTE op = *p++;
    --left;
    bool modrm = false;
    int imm = 0;
    bool immZ = false, addrImm = false;

    if (op == 0x0F) {
        if (left < 1) return 0;
        BYTE op2 = *p++;
        --left;
        if (op2 == 0x38) {
            if (left < 1) return 0;
            ++p;
            --left;
            modrm = true;
        } else if (op2 == 0x3A) {
            if (left < 1) return 0;
            ++p;
            --left;
            modrm = true;
            imm = 1;
        } else if (op2 >= 0x80 && op2 <= 0x8F) {
            immZ = true;   // Jcc rel16/32, no ModRM
        } else if (op2 >= 0xC8 && op2 <= 0xCF) {
            // BSWAP reg, no ModRM
        } else {
            switch (op2) {
                case 0x05: case 0x06: case 0x07: case 0x08: case 0x09: case 0x0B: case 0x0E:
                case 0x30: case 0x31: case 0x32: case 0x33: case 0x34: case 0x35:
                case 0x77: case 0xA0: case 0xA1: case 0xA2: case 0xA8: case 0xA9: case 0xAA:
                    break;
                default:
                    modrm = true;
                    break;
            }
            switch (op2) {
                case 0x70: case 0x71: case 0x72: case 0x73: case 0xA4: case 0xAC: case 0xBA: case 0xC2:
                case 0xC4: case 0xC5: case 0xC6: case 0x0F:
                    imm = 1;
                    break;
                default:
                    break;
            }
        }
    } else if (op <= 0x3F) {
        switch (op & 7) {
            case 0: case 1: case 2: case 3: modrm = true; break;
            case 4: imm = 1; break;
            case 5: immZ = true; break;
            default: break;
        }
    } else if (op >= 0x40 && op <= 0x5F) {
        // inc / dec / push / pop register
    } else if (op >= 0x70 && op <= 0x7F) {
        imm = 1;
    } else if (op >= 0xB0 && op <= 0xB7) {
        imm = 1;
    } else if (op >= 0xB8 && op <= 0xBF) {
        immZ = true;
    } else {
        switch (op) {
            case 0x60: case 0x61: case 0x6C: case 0x6D: case 0x6E: case 0x6F:
            case 0x90: case 0x91: case 0x92: case 0x93: case 0x94: case 0x95: case 0x96: case 0x97:
            case 0x98: case 0x99: case 0x9B: case 0x9C: case 0x9D: case 0x9E: case 0x9F:
            case 0xA4: case 0xA5: case 0xA6: case 0xA7: case 0xAA: case 0xAB: case 0xAC: case 0xAD:
            case 0xAE: case 0xAF:
            case 0xC3: case 0xCB: case 0xCC: case 0xCE: case 0xCF:
            case 0xD6: case 0xD7: case 0xEC: case 0xED: case 0xEE: case 0xEF:
            case 0xF1: case 0xF4: case 0xF5: case 0xF8: case 0xF9: case 0xFA: case 0xFB: case 0xFC: case 0xFD:
                break;
            case 0x62: case 0x63: case 0x84: case 0x85: case 0x86: case 0x87: case 0x88: case 0x89:
            case 0x8A: case 0x8B: case 0x8C: case 0x8D: case 0x8E: case 0x8F:
            case 0xC4: case 0xC5: case 0xD0: case 0xD1: case 0xD2: case 0xD3:
            case 0xD8: case 0xD9: case 0xDA: case 0xDB: case 0xDC: case 0xDD: case 0xDE: case 0xDF:
            case 0xFE: case 0xFF:
                modrm = true;
                break;
            case 0x68: immZ = true; break;
            case 0x69: modrm = true; immZ = true; break;
            case 0x6A: imm = 1; break;
            case 0x6B: modrm = true; imm = 1; break;
            case 0x80: case 0x82: case 0x83: modrm = true; imm = 1; break;
            case 0x81: modrm = true; immZ = true; break;
            case 0x9A: imm = 6; break;
            case 0xA0: case 0xA1: case 0xA2: case 0xA3: addrImm = true; break;
            case 0xA8: imm = 1; break;
            case 0xA9: immZ = true; break;
            case 0xC0: case 0xC1: modrm = true; imm = 1; break;
            case 0xC2: imm = 2; break;
            case 0xC6: modrm = true; imm = 1; break;
            case 0xC7: modrm = true; immZ = true; break;
            case 0xC8: imm = 3; break;
            case 0xCA: imm = 2; break;
            case 0xCD: imm = 1; break;
            case 0xD4: case 0xD5: imm = 1; break;
            case 0xE0: case 0xE1: case 0xE2: case 0xE3: imm = 1; break;
            case 0xE4: case 0xE5: case 0xE6: case 0xE7: imm = 1; break;
            case 0xE8: case 0xE9: immZ = true; break;
            case 0xEA: imm = 6; break;
            case 0xEB: imm = 1; break;
            case 0xF6:
                modrm = true;
                if (left >= 1 && ((p[0] >> 3) & 7) <= 1) imm = 1;
                break;
            case 0xF7:
                modrm = true;
                if (left >= 1 && ((p[0] >> 3) & 7) <= 1) immZ = true;
                break;
            default:
                return 0;
        }
    }

    int total = static_cast<int>(p - code);
    if (modrm) {
        int n = ModRmBytes(p, left, address16);
        if (!n) return 0;
        p += n;
        left -= n;
        total += n;
    }
    if (immZ) imm = opsize16 ? 2 : 4;
    if (addrImm) imm = address16 ? 2 : 4;
    if (imm) {
        if (total + imm > 15) return 0;
        total += imm;
    }
    if (total < 1 || total > 15) return 0;
    return total;
}

// ---- site bookkeeping ----------------------------------------------------------------------------------------

bool IsIgnored(DWORD offset) {
    LONG count = g_ignoreCount;
    for (LONG i = 0; i < count && i < kMaxIgnores; ++i)
        if (g_ignores[i] == offset) return true;
    return false;
}

int FindSite(DWORD offset, bool *created, bool reserve = false) {
    if (created) *created = false;
    LONG count = g_siteCount;
    for (LONG i = 0; i < count && i < kMaxSites; ++i)
        if (g_sites[i].offset == offset) return static_cast<int>(i);
    LONG slot = InterlockedIncrement(&g_siteCount) - 1;
    if (slot >= kMaxSites) {
        InterlockedDecrement(&g_siteCount);
        if (!reserve) {
            if (InterlockedCompareExchange(&g_siteFullNoted, 1, 0) == 0)
                Log(0, "fault-site table full (%d) - further sites are not tracked", kMaxSites);
            return -1;
        }
        slot = kFatalSite;
    }
    Site &site = g_sites[slot];
    site.offset = offset;
    site.hits = 0;
    site.detailed = 0;
    site.dumped = 0;
    site.fatalDumped = 0;
    site.failed = 0;
    site.unhandled = 0;
    site.handledNoted = 0;
    site.ignored = IsIgnored(offset) ? 1 : 0;
    site.resumed = 0;
    site.lastTick = site.code = site.access = site.fault = site.thread = 0;
    if (created) *created = true;
    return static_cast<int>(slot);
}

const Rule *FindRule(DWORD offset) {
    LONG count = g_ruleCount;
    for (LONG i = 0; i < count && i < kMaxRules; ++i)
        if (g_rules[i].offset == offset) return &g_rules[i];
    return nullptr;
}

void SetLast(const char *fmt, ...) {
    char text[sizeof(g_lastText)];
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf_s(text, sizeof(text), _TRUNCATE, fmt, ap);
    va_end(ap);
    InterlockedIncrement(&g_stateSeq);   // odd = writing
    strncpy_s(g_lastText, sizeof(g_lastText), text, _TRUNCATE);
    InterlockedIncrement(&g_stateSeq);   // even = stable
}

// ---- fault ring ----------------------------------------------------------------------------------------------

const char *AccessName(DWORD access);   // context section, below
void RefreshModules();                 // setup section, below

void RingPush(DWORD offset, DWORD code, DWORD access, DWORD fault, DWORD thread) {
    InterlockedIncrement(&g_ringSeq);                         // odd: writing
    LONG total = InterlockedIncrement(&g_ringCount);
    Fault &entry = g_ring[(total - 1) & (kRingSize - 1)];
    entry.tick = GetTickCount() - g_startTick;
    entry.offset = offset;
    entry.code = code;
    entry.access = access;
    entry.fault = fault;
    entry.thread = thread;
    InterlockedIncrement(&g_ringSeq);                         // even: stable
}

// oldest .. newest, copied under a seqlock (a manual dump may read while a handler writes)
int RingCopy(Fault *out, int capacity) {
    for (int attempt = 0; attempt < 8; ++attempt) {
        LONG before = g_ringSeq;
        if (before & 1) { YieldProcessor(); continue; }
        LONG total = g_ringCount;
        LONG count = total < kRingSize ? total : kRingSize;
        if (count > capacity) count = capacity;
        LONG first = total - count;
        for (LONG i = 0; i < count; ++i) out[i] = g_ring[(first + i) & (kRingSize - 1)];
        if (g_ringSeq == before) return static_cast<int>(count);
    }
    return 0;
}

void AddFaultLine(Buf &b, const Fault &f) {
    char known[96];
    KnownName(f.offset, known, sizeof(known));
    b.add("  t+%lu ms tru+0x%lx code %08lx %s 0x%08lx (thread %lu)%s%s\n", f.tick, f.offset, f.code,
          AccessName(f.access), f.fault, f.thread, known[0] ? " " : "", known);
}

void AppendRing(Buf &b) {
    Fault faults[kRingSize];
    int count = RingCopy(faults, kRingSize);
    if (count <= 1) return;
    b.add("previous faults (%d, newest first):\n", count - 1);
    for (int i = count - 2; i >= 0 && i >= count - 9; --i) AddFaultLine(b, faults[i]);
}

// one marker line so a script does not have to parse the record block
void EmitPrevMarker() {
    Fault faults[kRingSize];
    int count = RingCopy(faults, kRingSize);
    if (count <= 1) return;
    char list[128];
    size_t used = 0;
    list[0] = 0;
    int shown = 0;
    DWORD seen[3];
    for (int i = count - 2; i >= 0 && shown < 3; --i) {
        DWORD offset = faults[i].offset;
        bool duplicate = false;
        for (int k = 0; k < shown; ++k)
            if (seen[k] == offset) duplicate = true;
        if (duplicate) continue;
        seen[shown++] = offset;
        int n = _snprintf_s(list + used, sizeof(list) - used, _TRUNCATE, "%stru+0x%lx", used ? "," : "", offset);
        if (n > 0) used += static_cast<size_t>(n);
    }
    Log(1, "TRUGUARD_PREV count=%d newest=%s", count - 1, list);
}

// ---- GuardRails: context / events / policy -------------------------------------------------------------------

const char *RailActionName(int action) {
    return action == 2 ? "block" : (action == 0 ? "off" : "log");
}

Rail *FindRail(int id) {
    for (int i = 0; i < kRailCount; ++i)
        if (g_rails[i].id == id) return &g_rails[i];
    return nullptr;
}

const char *EventName(int id) {
    switch (id) {
        case 1: return "chart";
        case 2: return "attach";
        case 3: return "nullbox";
        case 4: return "cond1055";
        default: return "event";
    }
}

void ContextPush(DWORD gameTracker, DWORD agent, DWORD box, DWORD attachBox, DWORD agent528) {
    InterlockedIncrement(&g_contextSeq);
    LONG total = InterlockedIncrement(&g_contextCount);
    ContextSample &c = g_context[(total - 1) & (kContextSize - 1)];
    c.tick = GetTickCount() - g_startTick;
    c.gameTracker = gameTracker;
    c.agent = agent;
    c.box = box;
    c.attachBox = attachBox;
    c.agent528 = agent528;
    InterlockedIncrement(&g_contextSeq);
}

int ContextCopy(ContextSample *out, int capacity) {
    for (int attempt = 0; attempt < 8; ++attempt) {
        LONG before = g_contextSeq;
        if (before & 1) { YieldProcessor(); continue; }
        LONG total = g_contextCount;
        LONG count = total < kContextSize ? total : kContextSize;
        if (count > capacity) count = capacity;
        LONG first = total - count;
        for (LONG i = 0; i < count; ++i) out[i] = g_context[(first + i) & (kContextSize - 1)];
        if (g_contextSeq == before) return static_cast<int>(count);
    }
    return 0;
}

bool LatestContext(ContextSample *out) {
    ContextSample samples[kContextSize];
    int count = ContextCopy(samples, kContextSize);
    if (count <= 0) return false;
    *out = samples[count - 1];
    return true;
}

void EventPush(int id, DWORD a, DWORD b, DWORD c) {
    InterlockedIncrement(&g_eventSeq);
    LONG total = InterlockedIncrement(&g_eventCount);
    Event &e = g_events[(total - 1) & (kEventSize - 1)];
    e.tick = GetTickCount() - g_startTick;
    e.id = id;
    e.a = a;
    e.b = b;
    e.c = c;
    e.thread = GetCurrentThreadId();
    InterlockedIncrement(&g_eventSeq);
}

int EventCopy(Event *out, int capacity) {
    for (int attempt = 0; attempt < 8; ++attempt) {
        LONG before = g_eventSeq;
        if (before & 1) { YieldProcessor(); continue; }
        LONG total = g_eventCount;
        LONG count = total < kEventSize ? total : kEventSize;
        if (count > capacity) count = capacity;
        LONG first = total - count;
        for (LONG i = 0; i < count; ++i) out[i] = g_events[(first + i) & (kEventSize - 1)];
        if (g_eventSeq == before) return static_cast<int>(count);
    }
    return 0;
}

void EmitContextMarker() {
    if (!g_guardRails) return;
    ContextSample c;
    if (!LatestContext(&c)) return;
    Log(1, "TRUGUARD_CONTEXT t=%lu gt=0x%08lx agent=0x%08lx box=0x%08lx attach=0x%08lx agent528=%lu", c.tick,
        c.gameTracker, c.agent, c.box, c.attachBox, c.agent528);
}

void AppendContext(Buf &b) {
    if (!g_guardRails) return;
    ContextSample samples[kContextSize];
    int count = ContextCopy(samples, kContextSize);
    if (count <= 0) return;
    b.add("guard context (%d, newest first):\n", count);
    for (int i = count - 1, shown = 0; i >= 0 && shown < 4; --i, ++shown) {
        const ContextSample &c = samples[i];
        b.add("  t+%lu ms gt 0x%08lx agent 0x%08lx box 0x%08lx attach 0x%08lx agent528 %lu\n", c.tick, c.gameTracker,
              c.agent, c.box, c.attachBox, c.agent528);
    }
}

void AppendEvents(Buf &b) {
    if (!g_guardRails || !g_railEvents) return;
    Event events[kEventSize];
    int count = EventCopy(events, kEventSize);
    if (count <= 0) return;
    b.add("recent events (%d, newest first):\n", count);
    for (int i = count - 1, shown = 0; i >= 0 && shown < 8; --i, ++shown) {
        const Event &e = events[i];
        b.add("  t+%lu ms %s a 0x%08lx b 0x%08lx c 0x%08lx (thread %lu)\n", e.tick, EventName(e.id), e.a, e.b, e.c,
              e.thread);
    }
}

void SampleContext() {
    if (!g_guardRails || g_contextFaulted) return;
    __try {
        DWORD gameTracker = 0, agent = 0, box = 0, attachBox = 0, agent528 = 0;
        SafeRead(kPlayerState, &gameTracker, 4);
        SafeRead(kPlayerPtr, &agent, 4);
        if (gameTracker) {
            SafeRead(gameTracker + 0xa64, &box, 4);
            SafeRead(gameTracker + 0xc94, &attachBox, 4);
        }
        if (agent) {
            BYTE value = 0;
            if (SafeRead(agent + kAgent528, &value, 1)) agent528 = value;
        }
        ContextPush(gameTracker, agent, box, attachBox, agent528);

        // A markup box without an attach box is exactly the 48j constellation. Two consecutive samples keep a
        // one-frame leftover from producing noise; this is only a log line, no state is changed.
        static DWORD lastBox = 0;
        static int pending = 0;
        if (g_attachPendingNote && box && !attachBox) {
            if (box != lastBox) pending = 0;
            if (++pending == 2)
                Log(1, "TRUGUARD_RAIL id=attach_pending value=0 action=log hits=1");
        } else {
            pending = 0;
        }
        lastBox = box;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        // VirtualQuery + memcpy is still TOCTOU when the game frees a page between the two calls. Never let that
        // fault escape into the game: the rail API stays usable, only passive sampling stops.
        InterlockedExchange(&g_contextFaulted, 1);
        Log(0, "context sampler faulted - passive sampling stopped (rail API still available)");
    }
}

// ---- minidump ------------------------------------------------------------------------------------------------

bool DumpFile(const char *path, MINIDUMP_TYPE type, PEXCEPTION_POINTERS info) {
    HANDLE file = CreateFileA(path, GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        Log(0, "minidump %s not written (CreateFile %lu)", path, GetLastError());
        return false;
    }
    MINIDUMP_EXCEPTION_INFORMATION mei;
    PMINIDUMP_EXCEPTION_INFORMATION pointers = nullptr;
    if (info) {
        mei.ThreadId = GetCurrentThreadId();
        mei.ExceptionPointers = info;
        mei.ClientPointers = FALSE;
        pointers = &mei;
    }
    BOOL ok = FALSE;
    __try {
        ok = g_miniDump(GetCurrentProcess(), GetCurrentProcessId(), file, type, pointers, nullptr, nullptr);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = FALSE;
    }
    DWORD error = ok ? 0 : GetLastError();
    CloseHandle(file);
    if (!ok) Log(0, "minidump %s failed (%lu)", path, error);
    return ok != FALSE;
}

// every other thread: short suspend, EIP/ESP/EBP, resume (also works while the game hangs)
void SnapshotThreads() {
    if (g_modCount[g_modActive] == 0) RefreshModules();   // an early manual dump would show raw addresses
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snap == INVALID_HANDLE_VALUE) {
        Log(0, "thread snapshot failed (%lu)", GetLastError());
        return;
    }
    THREADENTRY32 te;
    te.dwSize = sizeof(te);
    DWORD pid = GetCurrentProcessId(), self = GetCurrentThreadId();
    int count = 0;
    if (Thread32First(snap, &te)) {
        do {
            if (te.th32OwnerProcessID != pid || te.th32ThreadID == self) continue;
            HANDLE thread = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, FALSE,
                                       te.th32ThreadID);
            if (!thread) continue;
            DWORD suspend = SuspendThread(thread);
            CONTEXT ctx;
            memset(&ctx, 0, sizeof(ctx));
            ctx.ContextFlags = CONTEXT_CONTROL;
            BOOL got = GetThreadContext(thread, &ctx);
            DWORD eip = static_cast<DWORD>(ctx.Eip), esp = static_cast<DWORD>(ctx.Esp);
            DWORD ebp = static_cast<DWORD>(ctx.Ebp);
            DWORD error = got ? 0 : GetLastError();
            ResumeThread(thread);
            CloseHandle(thread);
            if (!got) {
                Log(1, "thread %lu: no context (%lu)", te.th32ThreadID, error);
                continue;
            }
            char module[48];
            DWORD offset = 0;
            if (ModuleOf(eip, module, sizeof(module), &offset))
                Log(1, "thread %lu suspend %lu eip=%s+0x%lx esp=0x%08lx ebp=0x%08lx", te.th32ThreadID, suspend, module,
                    offset, esp, ebp);
            else
                Log(1, "thread %lu suspend %lu eip=0x%08lx esp=0x%08lx ebp=0x%08lx", te.th32ThreadID, suspend, eip, esp,
                    ebp);
            ++count;
        } while (Thread32Next(snap, &te));
    }
    CloseHandle(snap);
    Log(1, "threads: %d other thread(s) snapshotted", count);
}

void SanitizeName(const char *in, char *out, size_t capacity) {
    size_t i = 0;
    for (; in && in[i] && i + 1 < capacity && i < 24; ++i) {
        char c = in[i];
        bool ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_';
        out[i] = ok ? c : '_';
    }
    out[i] = 0;
}

// on demand (menu / TruLink), no exception needed: full dump + thread snapshot; ignores Dump / MaxDumps
bool ManualDump(const char *reason) {
    if (InterlockedCompareExchange(&g_dumping, 1, 0) != 0) {
        Log(0, "manual dump: another dump is being written");
        return false;
    }
    if (!g_miniDump) {
        HMODULE dbghelp = LoadLibraryA("dbghelp.dll");
        if (dbghelp) g_miniDump = reinterpret_cast<MiniDumpWriteDumpFn>(GetProcAddress(dbghelp, "MiniDumpWriteDump"));
    }
    if (!g_miniDump) {
        InterlockedExchange(&g_dumping, 0);
        Log(0, "manual dump: dbghelp.dll / MiniDumpWriteDump not available");
        return false;
    }
    CreateDirectoryA(g_dumpDir, nullptr);
    LONG number = InterlockedIncrement(&g_manualCount);
    char name[32];
    SanitizeName(reason, name, sizeof(name));
    char path[MAX_PATH];
    _snprintf_s(path, sizeof(path), _TRUNCATE, "%sTruGuard_%s_manual%02ld%s%s.dmp", g_dumpDir, g_runId, number,
                name[0] ? "_" : "", name);
    Log(1, "manual dump (reason \"%s\") - %s", reason && reason[0] ? reason : "-", path);
    EmitContextMarker();
    SnapshotThreads();
    MINIDUMP_TYPE type = static_cast<MINIDUMP_TYPE>(MiniDumpWithThreadInfo | MiniDumpWithFullMemory |
                                                    MiniDumpWithDataSegs | MiniDumpWithHandleData |
                                                    MiniDumpWithFullMemoryInfo | MiniDumpWithUnloadedModules);
    bool ok = DumpFile(path, type, nullptr);
    InterlockedExchange(&g_dumping, 0);
    if (ok) {
        strncpy_s(g_lastDumpPath, sizeof(g_lastDumpPath), path, _TRUNCATE);
        Log(1, "TRUGUARD_DUMP kind=manual path=%s", path);
        SetLast("manual dump %s", path);
    }
    return ok;
}

bool WriteDump(PEXCEPTION_POINTERS info, int site, DWORD offset, bool fatal = false) {
    g_lastDumpPath[0] = 0;
    if (!g_miniDump || !g_dump || g_dumpType == 0) return false;
    if (g_mode <= 0) return false;   // Mode=0 is log only (manual dumps use ManualDump)
    if (fatal) {
        if (g_sites[site].fatalDumped) return false;
        if (InterlockedCompareExchange(&g_sites[site].fatalDumped, 1, 0) != 0) return false;
    } else {
        if (g_sites[site].dumped) return false;
        if (InterlockedCompareExchange(&g_sites[site].dumped, 1, 0) != 0) return false;
    }
    // Keep one MaxDumps slot for a fatal hit: a run full of first-chance dumps must not hide the crash dump.
    LONG dumpLimit = g_maxDumps;
    if (!fatal && dumpLimit > 0) --dumpLimit;
    if (g_maxDumps <= 0 || g_dumpCount >= dumpLimit) {   // do not mark a site as dumped without a file
        if (fatal) InterlockedExchange(&g_sites[site].fatalDumped, 0);
        else InterlockedExchange(&g_sites[site].dumped, 0);
        return false;
    }
    if (InterlockedCompareExchange(&g_dumping, 1, 0) != 0) {
        // avoid deadlock/blocking a fatal path: let the site be marked failed
        if (fatal) InterlockedExchange(&g_sites[site].fatalDumped, 0);
        else InterlockedExchange(&g_sites[site].dumped, 0);
        InterlockedExchange(&g_sites[site].failed, 1);
        Log(0, "minidump skipped (another dump in progress)");
        return false;
    }
    LONG number = InterlockedIncrement(&g_dumpCount);

    char path[MAX_PATH];
    _snprintf_s(path, sizeof(path), _TRUNCATE, "%sTruGuard_%s_site%04lx_%02ld.dmp", g_dumpDir, g_runId, offset,
                number);
    MINIDUMP_TYPE type = MiniDumpWithThreadInfo;
    if (g_dumpType == 2) type = static_cast<MINIDUMP_TYPE>(type | MiniDumpWithFullMemory | MiniDumpWithDataSegs |
                                                          MiniDumpWithHandleData | MiniDumpWithFullMemoryInfo |
                                                          MiniDumpWithUnloadedModules);
    else type = static_cast<MINIDUMP_TYPE>(type | MiniDumpWithIndirectlyReferencedMemory | MiniDumpWithDataSegs |
                                           MiniDumpWithFullMemoryInfo | MiniDumpWithUnloadedModules);
    Log(0, "minidump begin %s", path);
    bool ok = DumpFile(path, type, info);
    InterlockedExchange(&g_dumping, 0);
    if (ok) {
        strncpy_s(g_lastDumpPath, sizeof(g_lastDumpPath), path, _TRUNCATE);
        if (fatal) InterlockedExchange(&g_sites[site].dumped, 1);
        Log(1, "minidump %s (%ld of max %d)%s", path, number, g_maxDumps, fatal ? " (fatal)" : "");
        SetLast("site tru+0x%lx: dump %s", offset, path);
        return true;
    }
    InterlockedExchange(&g_sites[site].failed, 1);
    return false;
}

// ---- context -------------------------------------------------------------------------------------------------

const char *AccessName(DWORD access) {
    switch (access) {
        case 0: return "read";
        case 1: return "write";
        case 8: return "execute";
        default: return "?";
    }
}

void AddBytes(Buf &b, const char *label, DWORD address, int length) {
    if (!address) {
        b.add("  %-6s 0x00000000\n", label);
        return;
    }
    BYTE data[32];
    int want = length;
    if (want > static_cast<int>(sizeof(data))) want = sizeof(data);
    DWORD got = SafeReadSome(address, data, static_cast<DWORD>(want));
    b.add("  %-6s 0x%08lx:", label, address);
    if (!got) {
        b.add(" (unreadable)\n");
        return;
    }
    for (DWORD i = 0; i < got && i < 16; ++i) b.add(" %02x", data[i]);
    if (got < static_cast<DWORD>(want)) b.add(" ...");
    if (got > 16) {
        b.add(" |");
        for (DWORD i = 16; i < got && i < 32; ++i) b.add(" %02x", data[i]);
    }
    b.add("\n");
}

void AddStack(Buf &b, const CONTEXT *ctx) {
    if (!g_logStack) return;
    b.add("stack: esp 0x%08lx ebp 0x%08lx\n", ctx->Esp, ctx->Ebp);
    DWORD values[8];
    DWORD got = SafeReadSome(ctx->Esp, values, sizeof(values));
    b.add("  [esp] ");
    for (DWORD i = 0; i < got / 4; ++i) b.add("%08lx ", values[i]);
    b.add("\n");
    DWORD ebp = ctx->Ebp;
    int frame = 0;
    for (; frame < 16; ++frame) {
        DWORD next = 0, ret = 0;
        if (!SafeRead(ebp, &next, 4) || !SafeRead(ebp + 4, &ret, 4)) break;
        if (!ret) break;
        char module[48], known[96];
        DWORD offset = 0;
        if (!ModuleOf(ret, module, sizeof(module), &offset)) break;
        KnownName(offset, known, sizeof(known));
        b.add("  #%02d %s+0x%lx%s%s%s (ebp 0x%08lx)\n", frame, module, offset, known[0] ? " " : "", known,
             known[0] ? "" : "", ebp);
        if (next <= ebp || next - ebp > 0x10000) break;
        ebp = next;
    }
}

void AddTruStackHints(Buf &b, const CONTEXT *ctx) {
    if (!g_logStack || !g_truBase) return;
    b.add("tru-stack:");
    DWORD found = 0;
    for (DWORD i = 0; i < 256; ++i) {
        DWORD value = 0;
        if (!SafeRead(ctx->Esp + i * 4, &value, 4)) break;
        if (value >= g_truBase && value < g_truEnd) {
            b.add(" %08lx(tru+0x%lx)", value, value - g_truBase);
            if (++found >= 8) break;
        }
    }
    if (!found) b.add(" none");
    b.add("\n");
}

void AddGameContext(Buf &b) {
    if (!g_logContext) return;
    char unit[64];
    SafeString(kUnitName, unit, sizeof(unit));
    DWORD unitId = 0, cheat = 0, player = 0, gameTracker = 0, box = 0, attachBox = 0;
    SafeRead(kUnitId, &unitId, 4);
    SafeRead(kCheatMode, &cheat, 4);
    SafeRead(kPlayerPtr, &player, 4);
    SafeRead(kPlayerState, &gameTracker, 4);
    if (gameTracker) {
        SafeRead(gameTracker + 0xa64, &box, 4);
        SafeRead(gameTracker + 0xc94, &attachBox, 4);
    }
    DWORD agent528 = 0;
    if (player) {
        BYTE value = 0;
        if (SafeRead(player + kAgent528, &value, 1)) agent528 = value;
    }

    DWORD object = 0, objectId = 0, namePtr = 0;
    char objectName[64] = "";
    if (player) {
        SafeRead(player + 0x10, &object, 4);
        if (object) {
            SafeRead(object + 0x14, &objectId, 4);
            if (SafeRead(object + 0x60, &namePtr, 4) && namePtr) SafeString(namePtr, objectName, sizeof(objectName));
        }
    }
    b.add("game: unit \"%s\" (id %lu), cheatMode 0x%lx; player 0x%08lx, gameTracker 0x%08lx; box 0x%08lx, "
          "attach 0x%08lx, agent528 %lu; object 0x%08lx id %lu \"%s\"\n",
          unit[0] ? unit : "-", unitId, cheat, player, gameTracker, box, attachBox, agent528, object, objectId,
          objectName);
}

void EmitDetailMarker(int site, DWORD offset, DWORD code, DWORD access, DWORD fault, const char *state,
                      const char *dump) {
    const char *where = (dump && dump[0]) ? dump
                        : (g_sites[site].failed ? "failed" : (g_sites[site].dumped ? "earlier" : "none"));
    Log(1, "TRUGUARD_DETAIL site=tru+0x%lx code=%08lx access=%s addr=0x%08lx hits=%ld state=%s debugger=%d dump=%s",
        offset, code, AccessName(access), fault, g_sites[site].hits, state, IsDebuggerPresent() ? 1 : 0, where);
}

void Describe(PEXCEPTION_POINTERS info, int site, const char *state, bool dump) {
    const EXCEPTION_RECORD *rec = info->ExceptionRecord;
    const CONTEXT *ctx = info->ContextRecord;
    DWORD eip = static_cast<DWORD>(ctx->Eip);
    DWORD offset = eip - g_truBase;
    DWORD code = rec->ExceptionCode;
    DWORD access = 0xffffffff, fault = 0;
    if (rec->NumberParameters >= 2) {
        access = static_cast<DWORD>(rec->ExceptionInformation[0]);
        fault = static_cast<DWORD>(rec->ExceptionInformation[1]);
    }
    BYTE bytes[16];
    DWORD got = SafeReadSome(eip, bytes, sizeof(bytes));
    char known[96];
    KnownName(offset, known, sizeof(known));

    Buf b = {nullptr, 0, 0};
    char text[8192];
    b.data = text;
    b.cap = sizeof(text);

    b.add("---- TruGuard %s: tru.exe+0x%lx %s %s at 0x%08lx (thread %lu, debugger=%d, %s)\n", g_runId, offset,
          known, AccessName(access), fault, GetCurrentThreadId(), IsDebuggerPresent() ? 1 : 0, state);
    b.add("exception 0x%08lx", code);
    if (rec->ExceptionFlags & EXCEPTION_NONCONTINUABLE) b.add(" (noncontinuable)");
    b.add("; eip 0x%08lx; hits %ld\n", eip, g_sites[site].hits);
    b.add("instr:");
    for (DWORD i = 0; i < got; ++i) b.add(" %02x", bytes[i]);
    if (!got) b.add(" (unreadable)");
    int length = got ? InstructionLength(bytes, static_cast<int>(got)) : 0;
    b.add("   length %d\n", length);

    b.add("regs: eax 0x%08lx ebx 0x%08lx ecx 0x%08lx edx 0x%08lx\n", ctx->Eax, ctx->Ebx, ctx->Ecx, ctx->Edx);
    b.add("      esi 0x%08lx edi 0x%08lx ebp 0x%08lx esp 0x%08lx\n", ctx->Esi, ctx->Edi, ctx->Ebp, ctx->Esp);
    b.add("      efl 0x%08lx\n", ctx->EFlags);

    if (g_logContext) {
        AddBytes(b, "fault", fault, 32);
        AddBytes(b, "eax", ctx->Eax, 16);
        AddBytes(b, "ecx", ctx->Ecx, 16);
        AddBytes(b, "edx", ctx->Edx, 16);
        AddBytes(b, "esi", ctx->Esi, 16);
        AddBytes(b, "edi", ctx->Edi, 16);
    }
    AddStack(b, ctx);
    AddGameContext(b);
    bool fatal = strcmp(state, "unhandled") == 0;
    if (fatal) AppendRing(b);
    if (fatal) {
        AppendContext(b);
        AppendEvents(b);
    }
    b.finish();
    bool locked = LockSpin();
    WriteRaw(text, b.used);
    if (locked) UnlockSpin();

    InterlockedExchange(&g_sites[site].detailed, 1);
    InterlockedIncrement(&g_detailCount);
    g_sites[site].code = code;
    g_sites[site].access = access;
    g_sites[site].fault = fault;
    g_sites[site].thread = GetCurrentThreadId();
    g_sites[site].lastTick = GetTickCount();
    SetLast("tru+0x%lx %s 0x%08lx thread %lu hits %ld (%s)", offset, AccessName(access), fault,
            GetCurrentThreadId(), g_sites[site].hits, state);
    bool wrote = dump && WriteDump(info, site, offset, fatal);
    EmitContextMarker();
    EmitDetailMarker(site, offset, code, access, fault, state, wrote ? g_lastDumpPath : nullptr);
    if (fatal) EmitPrevMarker();
}

char g_stackNotice[160];   // pre-built at load time: the stack-overflow path must not format anything
int g_stackNoticeLen = 0;
char g_outsideStackNotice[192];   // same for a stack overflow outside tru.exe (UEF outside path)
int g_outsideStackNoticeLen = 0;
volatile LONG g_outsideStackNoted = 0;

bool Interesting(DWORD code) {
    switch (code) {
        case EXCEPTION_ACCESS_VIOLATION:
        case EXCEPTION_ILLEGAL_INSTRUCTION:
        case EXCEPTION_INT_DIVIDE_BY_ZERO:
        case EXCEPTION_INT_OVERFLOW:
        case EXCEPTION_PRIV_INSTRUCTION:
        case EXCEPTION_IN_PAGE_ERROR:
        case EXCEPTION_STACK_OVERFLOW:
            return true;
        default:
            return false;
    }
}

// ---- recovery ------------------------------------------------------------------------------------------------

bool Executable(DWORD address) {
    MEMORY_BASIC_INFORMATION mbi;
    if (VirtualQuery(reinterpret_cast<const void *>(static_cast<UINT_PTR>(address)), &mbi, sizeof(mbi)) == 0) return false;
    if (mbi.State != MEM_COMMIT) return false;
    if (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) return false;
    return (mbi.Protect & (PAGE_EXECUTE | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY)) != 0;
}

bool CanResume(DWORD code, DWORD access, DWORD eip, DWORD fault) {
    if (code != EXCEPTION_ACCESS_VIOLATION) return false;
    if (access == 1 && !g_allowWriteSkip) return false;
    if (access == 8 && !g_allowExecuteSkip) return false;
    if (access == 8 && eip == fault) return false;   // DEP hit: the faulting byte is not code, nothing to decode
    return true;
}

LONG HandleFirstChance(PEXCEPTION_POINTERS info, DWORD code, DWORD eip) {
    DWORD offset = eip - g_truBase;
    LONG hits = 0;
    int site = FindSite(offset, nullptr);
    if (site < 0) return EXCEPTION_CONTINUE_SEARCH;
    hits = InterlockedIncrement(&g_sites[site].hits);
    InterlockedIncrement(&g_firstChanceCount);

    DWORD access = 0xffffffff, fault = 0;
    if (info->ExceptionRecord->NumberParameters >= 2) {
        access = static_cast<DWORD>(info->ExceptionRecord->ExceptionInformation[0]);
        fault = static_cast<DWORD>(info->ExceptionRecord->ExceptionInformation[1]);
    }

    RingPush(offset, code, access, fault, GetCurrentThreadId());
    {
        Site &state = g_sites[site];
        state.lastTick = GetTickCount();
        state.code = code;
        state.access = access;
        state.fault = fault;
        state.thread = GetCurrentThreadId();
    }

    const Rule *rule = FindRule(offset);
    int skip = 0;
    int limit = g_maxHitsPerSite;
    int setEax = -1, setEcx = -1;
    bool allowWrite = g_allowWriteSkip != 0, allowExec = g_allowExecuteSkip != 0;
    if (rule) {
        skip = rule->skip;
        setEax = rule->eax;
        setEcx = rule->ecx;
        if (rule->limit >= 0) limit = rule->limit;
        if (rule->allowWrite >= 0) allowWrite = rule->allowWrite != 0;
        if (rule->allowExec >= 0) allowExec = rule->allowExec != 0;
    } else if (g_skipUnknown) {
        skip = -1;
    }

    bool resume = false;
    if (g_mode >= 2 && CanResume(code, access, eip, fault) && hits <= limit && (access != 1 || allowWrite) &&
        (access != 8 || allowExec)) {
        if (skip < 0 || (!rule && g_skipUnknown)) {
            BYTE bytes[16];
            DWORD got = SafeReadSome(eip, bytes, sizeof(bytes));
            skip = got ? InstructionLength(bytes, static_cast<int>(got)) : 0;
        }
        if (skip > 0 && skip <= 15) resume = true;
    }
    if (skip > 15) skip = 0;

    // never resume if the target is not executable (protects against a bad decoder / wild jump)
    if (resume && !Executable(eip + static_cast<DWORD>(skip))) resume = false;

    // resume rate cap: stop before we loop
    if (resume && g_maxResumesPerSecond > 0) {
        DWORD now = GetTickCount();
        if (now - g_resumeWindowTick > 1000) {
            g_resumeWindowTick = now;
            g_resumeWindowCount = 0;
            g_resumeStopNoted = 0;
        }
        if (++g_resumeWindowCount > g_maxResumesPerSecond) {
            if (InterlockedCompareExchange(&g_resumeStopNoted, 1, 0) == 0)
                Log(0, "TRUGUARD_RESUME_STOP %d resumes in 1 s - letting further faults crash",
                    g_maxResumesPerSecond);
            resume = false;
        }
    }
    bool ignored = g_sites[site].ignored != 0;
    if (!resume) {
        if (ignored) {
            Log(3, "ignored site tru+0x%lx (hit %ld) - counted only", offset, hits);
        } else if (g_firstChance && hits <= 3) {
            if (hits > 1) {
                Log(2, "first chance tru+0x%lx %s 0x%08lx (hit %ld) - leaving it to the game", offset,
                    AccessName(access), fault, hits);
            } else {
                Log(1, "first chance tru+0x%lx %s 0x%08lx - %s", offset, AccessName(access), fault,
                    g_mode >= 2 ? "no safe skip, letting it crash" : "leaving it to the game (or crash)");
            }
        }
        if (g_firstChance && !ignored && hits == 1) {
            Log(1, "TRUGUARD_FAULT site=tru+0x%lx code=%08lx access=%s addr=0x%08lx hits=%ld debugger=%d", offset, code,
                AccessName(access), fault, hits, IsDebuggerPresent() ? 1 : 0);
            // the game may handle this fault itself, so the full record (and optionally the dump) can be
            // requested for the first occurrence as well - the unhandled filter only adds the fatal state
            if (g_firstChanceDetail) Describe(info, site, "firstchance", g_firstChanceDump != 0);
        }
        return EXCEPTION_CONTINUE_SEARCH;
    }

    InterlockedExchange(&g_sites[site].resumed, 1);
    int oldEax = static_cast<int>(info->ContextRecord->Eax);
    int oldEcx = static_cast<int>(info->ContextRecord->Ecx);
    Describe(info, site, "resumed", true);
    Buf extra = {nullptr, 0, 0};
    char text[512];
    extra.data = text;
    extra.cap = sizeof(text);
    extra.add("continued: skipped %d byte(s) at tru+0x%lx -> tru+0x%lx", skip, offset, offset + skip);
    if (setEax >= 0) extra.add(", eax 0x%08x -> 0x%08x", oldEax, setEax);
    if (setEcx >= 0) extra.add(", ecx 0x%08x -> 0x%08x", oldEcx, setEcx);
    extra.finish();
    bool locked = LockSpin();
    WriteRaw(text, extra.used);
    if (locked) UnlockSpin();

    info->ContextRecord->Eip = eip + static_cast<DWORD>(skip);
    if (setEax >= 0) info->ContextRecord->Eax = static_cast<DWORD>(setEax);
    if (setEcx >= 0) info->ContextRecord->Ecx = static_cast<DWORD>(setEcx);
    InterlockedIncrement(&g_resumedCount);
    Log(1, "TRUGUARD_RESUME site=tru+0x%lx skip=%d to=tru+0x%lx", offset, skip, offset + skip);
    return EXCEPTION_CONTINUE_EXECUTION;
}

LONG WINAPI UnhandledFilter(PEXCEPTION_POINTERS info);

// noinline: the 4 KB record buffer must stay in this frame. Inlined into UnhandledFilter, its stack probe would run
// on every UEF entry, including the stack-overflow paths that must not touch more stack.
__declspec(noinline) void LogOutsideFatal(PEXCEPTION_POINTERS info) {
    if (!g_outsideFatal) return;
    const EXCEPTION_RECORD *rec = info->ExceptionRecord;
    const CONTEXT *ctx = info->ContextRecord;
    DWORD eip = static_cast<DWORD>(ctx->Eip);
    DWORD code = rec->ExceptionCode;
    DWORD access = 0xffffffff, fault = 0;
    if (rec->NumberParameters >= 2) {
        access = static_cast<DWORD>(rec->ExceptionInformation[0]);
        fault = static_cast<DWORD>(rec->ExceptionInformation[1]);
    }
    char module[48] = "?";
    DWORD offset = 0;
    bool named = ModuleOf(eip, module, sizeof(module), &offset);
    if (!named) offset = 0;
    DWORD thread = GetCurrentThreadId();
    DWORD start = ThreadStartAddress();
    char startModule[48] = "?";
    DWORD startOffset = 0;
    bool startNamed = start && ModuleOf(start, startModule, sizeof(startModule), &startOffset);
    if (!startNamed) startOffset = 0;
    InterlockedIncrement(&g_outsideCount);

    Log(0, "TRUGUARD_OUTSIDE module=%s+0x%lx code=%08lx access=%s addr=0x%08lx eip=0x%08lx thread=%lu start=0x%08lx "
           "start_mod=%s+0x%lx",
        module, offset, code, AccessName(access), fault, eip, thread, start, startModule, startOffset);

    Buf b = {nullptr, 0, 0};
    char text[4096];
    b.data = text;
    b.cap = sizeof(text);
    b.add("---- TruGuard %s: outside tru.exe %s+0x%lx %s at 0x%08lx (thread %lu start 0x%08lx %s+0x%lx, %s)\n",
          g_runId, module, offset, AccessName(access), fault, thread, start, startModule, startOffset, "unhandled");
    b.add("exception 0x%08lx", code);
    if (rec->ExceptionFlags & EXCEPTION_NONCONTINUABLE) b.add(" (noncontinuable)");
    b.add("; eip 0x%08lx\n", eip);
    b.add("regs: eax 0x%08lx ebx 0x%08lx ecx 0x%08lx edx 0x%08lx\n", ctx->Eax, ctx->Ebx, ctx->Ecx, ctx->Edx);
    b.add("      esi 0x%08lx edi 0x%08lx ebp 0x%08lx esp 0x%08lx\n", ctx->Esi, ctx->Edi, ctx->Ebp, ctx->Esp);
    b.add("      efl 0x%08lx\n", ctx->EFlags);
    if (code != EXCEPTION_STACK_OVERFLOW) {
        AddStack(b, ctx);
        AddTruStackHints(b, ctx);
    }
    b.finish();
    bool locked = LockSpin();
    WriteRaw(text, b.used);
    if (locked) UnlockSpin();
    SetLast("outside %s+0x%lx %s 0x%08lx thread %lu", module, offset, AccessName(access), fault, thread);
}

// tru.exe installs its own unhandled-exception filter during init (it imports SetUnhandledExceptionFilter and
// calls it after our DllMain). Re-arm ours from the vectored handler: a list entry cannot be replaced, the
// filter pointer can. Only the VEH call passes note=true; the initial call in Start must not consume the note
// (the previous filter is normally NULL or the CRT's, not a later replacement by the game).
void ArmUnhandled(bool note) {
    LPTOP_LEVEL_EXCEPTION_FILTER previous = SetUnhandledExceptionFilter(UnhandledFilter);
    if (note && previous != UnhandledFilter && InterlockedCompareExchange(&g_uefNoted, 1, 0) == 0) {
        char module[48];
        DWORD offset = 0;
        if (ModuleOf(static_cast<DWORD>(reinterpret_cast<UINT_PTR>(previous)), module, sizeof(module), &offset))
            Log(1, "unhandled-exception filter replaced by %s+0x%lx - re-armed", module, offset);
        else
            Log(1, "unhandled-exception filter replaced by 0x%p - re-armed", previous);
    }
}

LONG CALLBACK Veh(PEXCEPTION_POINTERS info) {
    if (g_truBase == 0 || !info || !info->ExceptionRecord || !info->ContextRecord) return EXCEPTION_CONTINUE_SEARCH;
    DWORD code = info->ExceptionRecord->ExceptionCode;
    if (!Interesting(code)) return EXCEPTION_CONTINUE_SEARCH;   // guard pages / breakpoints / debug prints stay untouched
    DWORD eip = static_cast<DWORD>(info->ContextRecord->Eip);
    if (code != EXCEPTION_STACK_OVERFLOW) ArmUnhandled(true);
    if (eip < g_truBase || eip >= g_truEnd) return EXCEPTION_CONTINUE_SEARCH;
    if (InterlockedCompareExchange(&g_inHandler, 1, 0) != 0) {
        InterlockedIncrement(&g_handlerBusy);
        return EXCEPTION_CONTINUE_SEARCH;
    }
    LONG result = EXCEPTION_CONTINUE_SEARCH;
    __try {
        if (code == EXCEPTION_STACK_OVERFLOW) {
            // the handler runs on the exhausted stack: keep it to one pre-built line (no 8 KB record, no ebp walk)
            if (InterlockedCompareExchange(&g_stackNoted, 1, 0) == 0)
                WriteRaw(g_stackNotice, g_stackNoticeLen);
        } else {
            result = HandleFirstChance(info, code, eip);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "TruGuard handler faulted while handling tru+0x%lx - falling back to a plain crash", eip - g_truBase);
        result = EXCEPTION_CONTINUE_SEARCH;
    }
    InterlockedExchange(&g_inHandler, 0);
    return result;
}

LONG WINAPI UnhandledFilter(PEXCEPTION_POINTERS info) {
    if (g_truBase == 0 || !info || !info->ExceptionRecord || !info->ContextRecord) return EXCEPTION_CONTINUE_SEARCH;
    DWORD code = info->ExceptionRecord->ExceptionCode;
    if (!Interesting(code)) return EXCEPTION_CONTINUE_SEARCH;
    DWORD eip = static_cast<DWORD>(info->ContextRecord->Eip);
    if (eip < g_truBase || eip >= g_truEnd) {
        // Diagnostics only, same guard as the tru.exe path below: a fault inside the logger (e.g. after heap or
        // loader corruption) is swallowed and the original crash proceeds unchanged.
        __try {
            if (code == EXCEPTION_STACK_OVERFLOW) {
                // the filter runs on the exhausted stack: one pre-built line, no formatting, no 4 KB record
                if (g_outsideFatal) {
                    InterlockedIncrement(&g_outsideCount);
                    if (InterlockedCompareExchange(&g_outsideStackNoted, 1, 0) == 0)
                        WriteRaw(g_outsideStackNotice, g_outsideStackNoticeLen);
                }
            } else {
                LogOutsideFatal(info);
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
        return EXCEPTION_CONTINUE_SEARCH;
    }
    // A second thread may be logging/dumping the first fatal hit. Wait briefly instead of dropping the fatal
    // record; 2 s is longer than a normal log and still bounded if the first dump hangs. Sleep(1) can round up to
    // the timer resolution, so use a wall-clock deadline instead of counting iterations.
    bool entered = false;
    DWORD waitStart = GetTickCount();
    for (;;) {
        if (InterlockedCompareExchange(&g_inHandler, 1, 0) == 0) {
            entered = true;
            break;
        }
        if (GetTickCount() - waitStart >= 2000) break;
        Sleep(1);
    }
    if (!entered) {
        InterlockedIncrement(&g_handlerBusy);
        if (InterlockedCompareExchange(&g_handlerDropped, 1, 0) == 0)
            Log(0, "unhandled handler busy for 2 s - fatal record for tru+0x%lx dropped", eip - g_truBase);
        return EXCEPTION_CONTINUE_SEARCH;
    }
    __try {
        if (code != EXCEPTION_STACK_OVERFLOW) {
            DWORD offset = eip - g_truBase;
            int site = FindSite(offset, nullptr, true);
            if (site >= 0) {
                InterlockedIncrement(&g_unhandledCount);
                InterlockedExchange(&g_sites[site].unhandled, 1);
                // A first-chance record can belong to an earlier, non-fatal hit at the same site. Always write the
                // fatal record again: the registers/stack and the dump are for this hit, and WriteDump() allows one
                // extra fatal dump per site.
                Describe(info, site, "unhandled", true);
            }
        } else {
            if (InterlockedCompareExchange(&g_stackNoted, 1, 0) == 0)
                WriteRaw(g_stackNotice, g_stackNoticeLen);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    InterlockedExchange(&g_inHandler, 0);
    return EXCEPTION_CONTINUE_SEARCH;
}

// ---- setup ---------------------------------------------------------------------------------------------------

void RefreshModules() {
    LONG next = 1 - g_modActive;
    LONG count = 0;
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, GetCurrentProcessId());
    if (snap == INVALID_HANDLE_VALUE) return;
    MODULEENTRY32 me;
    me.dwSize = sizeof(me);
    if (Module32First(snap, &me)) {
        do {
            if (count >= kMaxMods) break;
            g_mods[next][count].base = static_cast<DWORD>(reinterpret_cast<UINT_PTR>(me.modBaseAddr));
            g_mods[next][count].size = me.modBaseSize;
            strncpy_s(g_mods[next][count].name, sizeof(g_mods[next][count].name), me.szModule, _TRUNCATE);
            ++count;
        } while (Module32Next(snap, &me));
    }
    CloseHandle(snap);
    g_modCount[next] = count;
    InterlockedExchange(&g_modActive, next);
}

// a site that faults but never reaches the unhandled filter was handled by the game (or by one of our plugins):
// one line per site, so a test run yields a concrete handled/ignored list instead of a guess
void NoteHandledSites() {
    if (!g_handledNote) return;
    LONG count = g_siteCount;
    if (count > kMaxSites) count = kMaxSites;
    DWORD now = GetTickCount();
    for (LONG i = 0; i < count; ++i) {
        Site &site = g_sites[i];
        if (site.hits <= 0 || site.ignored || site.unhandled || site.resumed) continue;
        if (now - site.lastTick < 2000) continue;
        if (InterlockedCompareExchange(&site.handledNoted, 1, 0) != 0) continue;
        InterlockedIncrement(&g_handledCount);
        Log(1, "TRUGUARD_HANDLED site=tru+0x%lx hits=%ld - no unhandled filter call within 2 s", site.offset,
            site.hits);
    }
}

DWORD WINAPI Worker(LPVOID) {
    WaitForSingleObject(g_stop, 1000);   // let DllMain return (the loader lock is held while it runs)
    int slow = 0;
    for (;;) {
        SampleContext();
        if (slow == 0 && !g_dumping) {   // no Toolhelp while a handler is inside MiniDumpWriteDump
            RefreshModules();
            NoteHandledSites();
        }
        slow = (slow + 1) % 10;          // 200 ms samples, 2 s module/handled maintenance
        if (WaitForSingleObject(g_stop, 200) != WAIT_TIMEOUT) break;
    }
    return 0;
}

DWORD ParseDword(const char *text, const char **end) {
    char *stop = nullptr;
    DWORD value = strtoul(text, &stop, 0);
    if (end) *end = stop;
    return value;
}

void ReadRules(const char *ini) {
    LONG count = 0;
    for (int i = 1; i <= kMaxRules; ++i) {
        char key[24], value[160];
        _snprintf_s(key, sizeof(key), _TRUNCATE, "Site%d", i);
        value[0] = 0;
        GetPrivateProfileStringA("Sites", key, "", value, sizeof(value), ini);
        if (!value[0]) continue;
        const char *p = value;
        DWORD offset = ParseDword(p, &p);
        Rule r = {offset, 0, -1, -1, -1, -1, -1};
        for (int field = 0; field < 5; ++field) {
            while (*p == ' ' || *p == '\t') ++p;
            if (*p == ',') ++p;
            while (*p == ' ' || *p == '\t') ++p;
            if (!*p) break;
            if (field == 0 && (*p == 'w' || *p == 'x')) {   // flags may start right after the offset
                if (strchr(p, 'w')) r.allowWrite = 1;
                if (strchr(p, 'x')) r.allowExec = 1;
                break;
            }
            char *stop = nullptr;
            long number = strtol(p, &stop, 0);
            if (stop == p) break;
            p = stop;
            switch (field) {
                case 0: r.skip = static_cast<int>(number); break;
                case 1: r.eax = static_cast<int>(number); break;
                case 2: r.ecx = static_cast<int>(number); break;
                case 3: r.limit = static_cast<int>(number); break;
                default: break;
            }
        }
        // optional trailing " w" / " x" flags
        if (strchr(p, 'w')) r.allowWrite = 1;
        if (strchr(p, 'x')) r.allowExec = 1;
        if (count < kMaxRules) g_rules[count++] = r;
    }
    InterlockedExchange(&g_ruleCount, count);
}

void ReadIgnores(const char *ini) {
    LONG count = 0;
    for (int i = 1; i <= kMaxIgnores; ++i) {
        char key[24], value[64];
        _snprintf_s(key, sizeof(key), _TRUNCATE, "Site%d", i);
        value[0] = 0;
        GetPrivateProfileStringA("Ignore", key, "", value, sizeof(value), ini);
        if (!value[0]) continue;
        g_ignores[count++] = ParseDword(value, nullptr);
    }
    InterlockedExchange(&g_ignoreCount, count);
}

void ReadRails(const char *ini) {
    for (int i = 0; i < kRailCount; ++i) {
        Rail &r = g_rails[i];
        char section[80], action[32];
        _snprintf_s(section, sizeof(section), _TRUNCATE, "Rail.%s", r.name);
        action[0] = 0;
        GetPrivateProfileStringA(section, "Action", "log", action, sizeof(action), ini);
        if (strcmp(action, "off") == 0) r.action = 0;
        else if (strcmp(action, "block") == 0) r.action = 2;
        else r.action = 1;
        r.limit = GetPrivateProfileIntA(section, "Limit", 1, ini);
        if (r.limit < 1) r.limit = 1;
        if (r.limit > 100000) r.limit = 100000;
        InterlockedExchange(&r.hits, 0);
    }
}

void ReadOptions(const char *ini) {
    g_enabled = GetPrivateProfileIntA("Guard", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("Guard", "LogLevel", 1, ini);
    g_mode = GetPrivateProfileIntA("Guard", "Mode", 1, ini);
    g_firstChance = GetPrivateProfileIntA("Guard", "FirstChance", 1, ini);
    g_firstChanceDetail = GetPrivateProfileIntA("Guard", "FirstChanceDetail", 1, ini);
    g_firstChanceDump = GetPrivateProfileIntA("Guard", "FirstChanceDump", 0, ini);
    g_dump = GetPrivateProfileIntA("Guard", "Dump", 1, ini);
    g_dumpType = GetPrivateProfileIntA("Guard", "DumpType", 1, ini);
    g_maxDumps = GetPrivateProfileIntA("Guard", "MaxDumps", 16, ini);
    g_maxHitsPerSite = GetPrivateProfileIntA("Guard", "MaxHitsPerSite", 8, ini);
    g_skipUnknown = GetPrivateProfileIntA("Guard", "SkipUnknown", 0, ini);
    g_allowWriteSkip = GetPrivateProfileIntA("Guard", "AllowWriteSkip", 1, ini);
    g_allowExecuteSkip = GetPrivateProfileIntA("Guard", "AllowExecuteSkip", 1, ini);
    g_logStack = GetPrivateProfileIntA("Guard", "LogStack", 1, ini);
    g_logContext = GetPrivateProfileIntA("Guard", "LogContext", 1, ini);
    g_handledNote = GetPrivateProfileIntA("Guard", "HandledNote", 1, ini);
    g_outsideFatal = GetPrivateProfileIntA("Guard", "OutsideFatal", 1, ini);
    g_maxResumesPerSecond = GetPrivateProfileIntA("Guard", "MaxResumesPerSecond", 20, ini);
    g_guardRails = GetPrivateProfileIntA("GuardRails", "Enabled", 1, ini);
    g_railEvents = GetPrivateProfileIntA("GuardRails", "Events", 1, ini);
    g_attachPendingNote = GetPrivateProfileIntA("GuardRails", "AttachPending", 1, ini);
    if (g_mode < 0) g_mode = 0;
    if (g_mode > 2) g_mode = 2;
    if (g_firstChanceDetail != 0) g_firstChanceDetail = 1;
    if (g_firstChanceDump != 0) g_firstChanceDump = 1;
    if (g_handledNote != 0) g_handledNote = 1;
    if (g_outsideFatal != 0) g_outsideFatal = 1;
    if (g_maxDumps < 0) g_maxDumps = 0;
    if (g_maxDumps > 200) g_maxDumps = 200;
    if (g_maxHitsPerSite < 1) g_maxHitsPerSite = 1;
    if (g_maxHitsPerSite > 1000) g_maxHitsPerSite = 1000;
    if (g_maxResumesPerSecond < 0) g_maxResumesPerSecond = 0;
    if (g_maxResumesPerSecond > 1000) g_maxResumesPerSecond = 1000;
    if (g_guardRails != 0) g_guardRails = 1;
    if (g_railEvents != 0) g_railEvents = 1;
    if (g_attachPendingNote != 0) g_attachPendingNote = 1;
}

void Start(HMODULE self) {
    DWORD length = GetModuleFileNameA(self, g_selfDir, MAX_PATH);
    while (length > 0 && g_selfDir[length - 1] != '\\' && g_selfDir[length - 1] != '/') --length;
    g_selfDir[length] = 0;

    char ini[MAX_PATH];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruGuard.ini", g_selfDir);
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruGuard.log", g_selfDir);
    _snprintf_s(g_dumpDir, sizeof(g_dumpDir), _TRUNCATE, "%sTruGuardDumps\\", g_selfDir);
    g_startTick = GetTickCount();
    SYSTEMTIME t;
    GetLocalTime(&t);
    _snprintf_s(g_runId, sizeof(g_runId), _TRUNCATE, "%04u%02u%02u_%02u%02u%02u", t.wYear, t.wMonth, t.wDay, t.wHour,
                t.wMinute, t.wSecond);
    ReadOptions(ini);
    ReadRules(ini);
    ReadIgnores(ini);
    ReadRails(ini);
    _snprintf_s(g_stackNotice, sizeof(g_stackNotice), _TRUNCATE,
                "TruGuard %s: stack overflow in tru.exe (no context, no dump)\n", g_runId);
    g_stackNoticeLen = static_cast<int>(strlen(g_stackNotice));
    _snprintf_s(g_outsideStackNotice, sizeof(g_outsideStackNotice), _TRUNCATE,
                "TruGuard %s: TRUGUARD_OUTSIDE module=?+0x0 code=%08lx stack overflow outside tru.exe "
                "(pre-built line: no module, registers, stack or dump)\n",
                g_runId, static_cast<DWORD>(EXCEPTION_STACK_OVERFLOW));
    g_outsideStackNoticeLen = static_cast<int>(strlen(g_outsideStackNotice));

    g_log = CreateFileA(g_logPath, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_ALWAYS,
                        FILE_ATTRIBUTE_NORMAL, nullptr);
    Log(1, "TruGuard 0.4.2+outside-fix loaded (enabled %d, log %d, mode %d, firstChance %d/%d/%d, dump %d/%d, maxDumps %d, "
           "handled %d, rules %ld, ignores %ld, maxResumes/s %d, guardRails %d/%d/%d, rails %d)",
        g_enabled, g_logLevel, g_mode, g_firstChance, g_firstChanceDetail, g_firstChanceDump, g_dump, g_dumpType,
        g_maxDumps, g_handledNote, g_ruleCount, g_ignoreCount, g_maxResumesPerSecond, g_guardRails, g_railEvents,
        g_attachPendingNote, kRailCount);
    if (!g_enabled) {
        Log(1, "disabled by TruGuard.ini - no handler installed");
        return;
    }

    HMODULE exe = GetModuleHandleA(nullptr);
    g_truBase = static_cast<DWORD>(reinterpret_cast<UINT_PTR>(exe));
    if (g_truBase != kImageBaseExpected) {
        Log(0, "image base 0x%08lx, expected 0x%08lx - not watching", g_truBase, kImageBaseExpected);
        return;
    }
    DWORD nt = 0;
    if (!SafeRead(g_truBase + 0x3c, &nt, 4) || !nt) {
        Log(0, "no PE header - not watching");
        return;
    }
    DWORD sizeOfImage = 0;
    if (!SafeRead(g_truBase + nt + 0x50, &sizeOfImage, 4) || !sizeOfImage) {
        Log(0, "no SizeOfImage - not watching");
        return;
    }
    g_truEnd = g_truBase + sizeOfImage;

    // dbghelp is also needed for an on-demand dump while Dump=0 (automatic dumps stay off)
    CreateDirectoryA(g_dumpDir, nullptr);
    HMODULE dbghelp = LoadLibraryA("dbghelp.dll");
    if (dbghelp)
        g_miniDump = reinterpret_cast<MiniDumpWriteDumpFn>(GetProcAddress(dbghelp, "MiniDumpWriteDump"));
    if (!g_miniDump) Log(0, "dbghelp.dll / MiniDumpWriteDump not available - dumps off");

    g_stop = CreateEventA(nullptr, TRUE, FALSE, nullptr);
    HANDLE thread = CreateThread(nullptr, 0, Worker, nullptr, 0, nullptr);
    if (thread) CloseHandle(thread);

    if (!AddVectoredExceptionHandler(1, Veh)) {
        Log(0, "AddVectoredExceptionHandler failed (%lu) - not watching", GetLastError());
        return;
    }
    ArmUnhandled(false);   // the game replaces this filter during init - the vectored handler re-arms it as well
    Log(1, "watching tru.exe 0x%08lx..0x%08lx, log %s, dumps %s%s", g_truBase, g_truEnd, g_logPath, g_dumpDir,
        g_mode >= 2 ? " (resume where possible)" : "");
    SetLast("watching, no fault yet (mode %d)", g_mode);
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        Start(instance);
    }
    return TRUE;
}

extern "C" __declspec(dllexport) const char *TruGuardVersion() {
    return "TruGuard 0.4.2+outside-fix (outside-fatal record, GuardRails event/rail API, passive context, fault ring, on-demand dump)";
}

extern "C" __declspec(dllexport) int TruGuardCount() { return static_cast<int>(g_firstChanceCount); }

extern "C" __declspec(dllexport) int TruGuardDistinct() {
    LONG count = g_siteCount;
    return count > kMaxSites ? kMaxSites : static_cast<int>(count);
}

extern "C" __declspec(dllexport) int TruGuardMode() { return static_cast<int>(g_mode); }

extern "C" __declspec(dllexport) int TruGuardStatus(char *out, int size) {
    if (!out || size <= 0) return 0;
    LONG sites = g_siteCount;
    if (sites > kMaxSites) sites = kMaxSites;
    int n = _snprintf_s(out, static_cast<size_t>(size), _TRUNCATE,
                        "mode=%d firstChance=%ld details=%ld unhandled=%ld resumed=%ld dumps=%ld handled=%ld manual=%ld "
                        "outside=%ld busy=%ld sites=%ld maxSites=%d maxHits=%d skipUnknown=%d rules=%ld ignores=%ld maxResumes=%d "
                        "guardRails=%d events=%ld context=%ld rails=%d log=%s",
                        g_mode, g_firstChanceCount, g_detailCount, g_unhandledCount, g_resumedCount, g_dumpCount,
                        g_handledCount, g_manualCount, g_outsideCount, g_handlerBusy, sites, kMaxSites, g_maxHitsPerSite,
                        g_skipUnknown,
                        g_ruleCount,
                        g_ignoreCount, g_maxResumesPerSecond, g_guardRails, g_eventCount, g_contextCount, kRailCount,
                        g_logPath);
    return n < 0 ? size - 1 : n;
}

extern "C" __declspec(dllexport) int TruGuardLast(char *out, int size) {
    if (!out || size <= 0) return 0;
    for (int attempt = 0; attempt < 4; ++attempt) {
        LONG before = g_stateSeq;
        if (before & 1) { YieldProcessor(); continue; }
        strncpy_s(out, static_cast<size_t>(size), g_lastText, _TRUNCATE);
        if (g_stateSeq == before) break;
    }
    out[size - 1] = 0;
    return static_cast<int>(strlen(out));
}

extern "C" __declspec(dllexport) int TruGuardSetMode(int mode) {
    if (mode < 0) mode = 0;
    if (mode > 2) mode = 2;
    if (mode == g_mode) return static_cast<int>(g_mode);
    InterlockedExchange(&g_mode, mode);
    Log(1, "mode changed to %d", mode);
    SetLast("mode %d", mode);
    return g_mode;
}

// GuardRail policy: 1 = allow (caller continues), 0 = block (caller uses its safe action). The guard only reports;
// the caller (TruRockVein/TruShadowPower) owns the actual game-side action. Logging is limited, the return value is not.
extern "C" __declspec(dllexport) int TruGuardRail(int id, unsigned long value) {
    if (!g_enabled || !g_guardRails) return 1;
    Rail *rail = FindRail(id);
    if (!rail) {
        if (InterlockedCompareExchange(&g_unknownRailNoted, 1, 0) == 0)
            Log(0, "TRUGUARD_RAIL id=%d value=0x%08lx action=allow unknown-id", id, value);
        return 1;
    }
    if (rail->action == 0) return 1;
    LONG hit = InterlockedIncrement(&rail->hits);
    if (hit <= rail->limit)
        Log(1, "TRUGUARD_RAIL id=%s value=0x%08lx action=%s hits=%ld", rail->name, value, RailActionName(rail->action),
            hit);
    return rail->action == 2 ? 0 : 1;
}

// Plugin breadcrumb: keep it in the ring and log it at LogLevel 2. Call on changes, not every frame.
extern "C" __declspec(dllexport) int TruGuardEvent(int id, unsigned long a, unsigned long b, unsigned long c) {
    if (!g_enabled || !g_guardRails || !g_railEvents) return 1;
    EventPush(id, a, b, c);
    if (g_logLevel >= 2) Log(2, "TRUGUARD_EVENT name=%s a=0x%08lx b=0x%08lx c=0x%08lx", EventName(id), a, b, c);
    return 1;
}

// Latest passive context sample for TruMenu/TruLink and the test harness.
extern "C" __declspec(dllexport) int TruGuardContext(char *out, int size) {
    if (!out || size <= 0) return 0;
    ContextSample c;
    if (!LatestContext(&c)) {
        out[0] = 0;
        return 0;
    }
    int n = _snprintf_s(out, static_cast<size_t>(size), _TRUNCATE,
                        "t=%lu gt=0x%08lx agent=0x%08lx box=0x%08lx attach=0x%08lx agent528=%lu", c.tick, c.gameTracker,
                        c.agent, c.box, c.attachBox, c.agent528);
    return n < 0 ? size - 1 : n;
}

// on-demand full dump + thread snapshot (TruMenu "guard.dump", TruLink "menu guard.dump"); no exception needed
extern "C" __declspec(dllexport) int TruGuardDump(const char *reason) {
    return ManualDump(reason) ? 1 : 0;
}
