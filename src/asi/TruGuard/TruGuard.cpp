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
//
// The log is written with a pre-opened HANDLE (WriteFile, FILE_APPEND_DATA); the handler does not allocate, takes no
// CRT lock and uses only VirtualQuery-protected reads. A spin lock plus an in-handler flag keep it reentrancy safe;
// if the lock is busy the line is still written (worst case interleaved) - a deadlock in a crash handler would be
// worse. MiniDumpWriteDump is loaded from dbghelp.dll at start and called inside the handler (accepted risk: it can
// block; Dump / DumpType turn it off).
//
// Scope: local, offline, single player, no anti-cheat. Nothing of this is meant for end users.
//
// 0.1 (2026-11-01) - first build: first-chance VEH, per-site log, optional resume, minidumps, exports.

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
const DWORD kGameTracker = 0x00e7f088;  // +0xbc cheatMode (dword), +0x38 unit name
const DWORD kPlayerPtr = 0x00e7f094;    // GameTracker +0xc player instance
const DWORD kCheatMode = 0x00e7f144;
const DWORD kPlayerState = 0x00fadb58;
const DWORD kUnitName = 0x00e7f0c0;     // GameTracker +0x38 (char[<=64])
const DWORD kUnitId = 0x00e7f148;

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
int g_dump = 1;
int g_dumpType = 1;      // 0 none, 1 mini (thread info, indirect references, data segments), 2 full memory
int g_maxDumps = 16;
int g_maxHitsPerSite = 8;
int g_skipUnknown = 0;   // decode the instruction and skip it when no Site rule matches
int g_allowWriteSkip = 1;
int g_allowExecuteSkip = 1;
int g_logStack = 1;
int g_logContext = 1;

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
    DWORD lastTick, code, access, fault, thread;
};
const int kMaxSites = 64;
Site g_sites[kMaxSites];
volatile LONG g_siteCount = 0;

volatile LONG g_firstChanceCount = 0;
volatile LONG g_unhandledCount = 0;
volatile LONG g_resumedCount = 0;
volatile LONG g_dumpCount = 0;
volatile LONG g_inHandler = 0;
volatile LONG g_stackNoted = 0;
volatile LONG g_logSpin = 0;
volatile LONG g_stateSeq = 0;

char g_selfDir[MAX_PATH];   // plugin / game folder with trailing backslash
char g_logPath[MAX_PATH];
char g_dumpDir[MAX_PATH];
char g_runId[32];
char g_lastText[512];
HANDLE g_log = INVALID_HANDLE_VALUE;
DWORD g_truBase = 0, g_truEnd = 0;
DWORD g_startTick = 0;
HANDLE g_stop = nullptr;

typedef BOOL(WINAPI *MiniDumpWriteDumpFn)(HANDLE, DWORD, HANDLE, MINIDUMP_TYPE, PMINIDUMP_EXCEPTION_INFORMATION,
                                          PMINIDUMP_USER_STREAM_INFORMATION, PMINIDUMP_CALLBACK_INFORMATION);
MiniDumpWriteDumpFn g_miniDump = nullptr;

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
    return false;
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

void LockSpin() {
    for (int i = 0; i < 4000; ++i) {
        if (InterlockedCompareExchange(&g_logSpin, 1, 0) == 0) return;
        YieldProcessor();
    }
    // fall through: write anyway, an interleaved line beats a hang
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
    bool locked = InterlockedCompareExchange(&g_logSpin, 0, 0) == 0;
    if (locked) LockSpin();
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

int FindSite(DWORD offset, bool *created) {
    if (created) *created = false;
    LONG count = g_siteCount;
    for (LONG i = 0; i < count && i < kMaxSites; ++i)
        if (g_sites[i].offset == offset) return static_cast<int>(i);
    LONG slot = InterlockedIncrement(&g_siteCount) - 1;
    if (slot >= kMaxSites) {
        InterlockedDecrement(&g_siteCount);
        return -1;
    }
    g_sites[slot].offset = offset;
    g_sites[slot].hits = 0;
    g_sites[slot].detailed = 0;
    g_sites[slot].dumped = 0;
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

// ---- minidump ------------------------------------------------------------------------------------------------

void WriteDump(PEXCEPTION_POINTERS info, int site, DWORD offset) {
    if (!g_miniDump || !g_dump || g_dumpType == 0) return;
    if (g_sites[site].dumped) return;
    if (g_maxDumps <= 0 || g_dumpCount >= g_maxDumps) return;   // do not mark a site as dumped without a file
    if (InterlockedCompareExchange(&g_sites[site].dumped, 1, 0) != 0) return;
    LONG number = InterlockedIncrement(&g_dumpCount);

    char path[MAX_PATH];
    _snprintf_s(path, sizeof(path), _TRUNCATE, "%sTruGuard_%s_site%04lx_%02ld.dmp", g_dumpDir, g_runId, offset,
                number);
    HANDLE file = CreateFileA(path, GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        Log(0, "minidump %s not written (CreateFile %lu)", path, GetLastError());
        return;
    }
    MINIDUMP_TYPE type = MiniDumpWithThreadInfo;
    if (g_dumpType == 2) type = static_cast<MINIDUMP_TYPE>(type | MiniDumpWithFullMemory | MiniDumpWithDataSegs |
                                                          MiniDumpWithHandleData);
    else type = static_cast<MINIDUMP_TYPE>(type | MiniDumpWithIndirectlyReferencedMemory | MiniDumpWithDataSegs);
    MINIDUMP_EXCEPTION_INFORMATION mei;
    mei.ThreadId = GetCurrentThreadId();
    mei.ExceptionPointers = info;
    mei.ClientPointers = FALSE;
    BOOL ok = FALSE;
    __try {
        ok = g_miniDump(GetCurrentProcess(), GetCurrentProcessId(), file, type, &mei, nullptr, nullptr);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = FALSE;
    }
    CloseHandle(file);
    if (ok) {
        Log(1, "minidump %s (%ld of max %d)", path, number, g_maxDumps);
        SetLast("site tru+0x%lx: dump %s", offset, path);
    } else {
        Log(0, "minidump %s failed (%lu)", path, GetLastError());
    }
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

void AddGameContext(Buf &b) {
    if (!g_logContext) return;
    char unit[64];
    SafeString(kUnitName, unit, sizeof(unit));
    DWORD unitId = 0, cheat = 0, player = 0, state = 0;
    SafeRead(kUnitId, &unitId, 4);
    SafeRead(kCheatMode, &cheat, 4);
    SafeRead(kPlayerPtr, &player, 4);
    SafeRead(kPlayerState, &state, 4);

    DWORD object = 0, objectId = 0, namePtr = 0;
    char objectName[64] = "";
    if (player) {
        SafeRead(player + 0x10, &object, 4);
        if (object) {
            SafeRead(object + 0x14, &objectId, 4);
            if (SafeRead(object + 0x60, &namePtr, 4) && namePtr) SafeString(namePtr, objectName, sizeof(objectName));
        }
    }
    b.add("game: unit \"%s\" (id %lu), cheatMode 0x%lx; player 0x%08lx, playerstate 0x%08lx; object 0x%08lx id %lu "
          "\"%s\"\n",
          unit[0] ? unit : "-", unitId, cheat, player, state, object, objectId, objectName);
}

void Describe(PEXCEPTION_POINTERS info, int site, bool dump) {
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

    b.add("---- TruGuard %s: tru.exe+0x%lx %s %s at 0x%08lx (thread %lu)\n", g_runId, offset, known,
          AccessName(access), fault, GetCurrentThreadId());
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
    b.finish();
    bool locked = InterlockedCompareExchange(&g_logSpin, 0, 0) == 0;
    if (locked) LockSpin();
    WriteRaw(text, b.used);
    if (locked) UnlockSpin();

    InterlockedExchange(&g_sites[site].detailed, 1);
    g_sites[site].code = code;
    g_sites[site].access = access;
    g_sites[site].fault = fault;
    g_sites[site].thread = GetCurrentThreadId();
    g_sites[site].lastTick = GetTickCount();
    SetLast("tru+0x%lx %s 0x%08lx thread %lu hits %ld", offset, AccessName(access), fault, GetCurrentThreadId(),
            g_sites[site].hits);
    if (dump) WriteDump(info, site, offset);
}

char g_stackNotice[160];   // pre-built at load time: the stack-overflow path must not format anything
int g_stackNoticeLen = 0;

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

    if (!resume) {
        if (g_firstChance && hits <= 3) {
            if (hits > 1) {
                Log(2, "first chance tru+0x%lx %s 0x%08lx (hit %ld) - leaving it to the game", offset,
                    AccessName(access), fault, hits);
            } else {
                Log(1, "first chance tru+0x%lx %s 0x%08lx - %s", offset, AccessName(access), fault,
                    g_mode >= 2 ? "no safe skip, letting it crash" : "leaving it to the game (or crash)");
            }
        }
        return EXCEPTION_CONTINUE_SEARCH;
    }

    int oldEax = static_cast<int>(info->ContextRecord->Eax);
    int oldEcx = static_cast<int>(info->ContextRecord->Ecx);
    Describe(info, site, true);
    Buf extra = {nullptr, 0, 0};
    char text[512];
    extra.data = text;
    extra.cap = sizeof(text);
    extra.add("continued: skipped %d byte(s) at tru+0x%lx -> tru+0x%lx", skip, offset, offset + skip);
    if (setEax >= 0) extra.add(", eax 0x%08x -> 0x%08x", oldEax, setEax);
    if (setEcx >= 0) extra.add(", ecx 0x%08x -> 0x%08x", oldEcx, setEcx);
    extra.finish();
    bool locked = InterlockedCompareExchange(&g_logSpin, 0, 0) == 0;
    if (locked) LockSpin();
    WriteRaw(text, extra.used);
    if (locked) UnlockSpin();

    info->ContextRecord->Eip = eip + static_cast<DWORD>(skip);
    if (setEax >= 0) info->ContextRecord->Eax = static_cast<DWORD>(setEax);
    if (setEcx >= 0) info->ContextRecord->Ecx = static_cast<DWORD>(setEcx);
    InterlockedIncrement(&g_resumedCount);
    return EXCEPTION_CONTINUE_EXECUTION;
}

LONG CALLBACK Veh(PEXCEPTION_POINTERS info) {
    if (g_truBase == 0 || !info || !info->ExceptionRecord || !info->ContextRecord) return EXCEPTION_CONTINUE_SEARCH;
    DWORD code = info->ExceptionRecord->ExceptionCode;
    if (!Interesting(code)) return EXCEPTION_CONTINUE_SEARCH;   // guard pages / breakpoints / debug prints stay untouched
    DWORD eip = static_cast<DWORD>(info->ContextRecord->Eip);
    if (eip < g_truBase || eip >= g_truEnd) return EXCEPTION_CONTINUE_SEARCH;

    if (InterlockedCompareExchange(&g_inHandler, 1, 0) != 0) return EXCEPTION_CONTINUE_SEARCH;
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
    if (eip < g_truBase || eip >= g_truEnd) return EXCEPTION_CONTINUE_SEARCH;
    if (InterlockedCompareExchange(&g_inHandler, 1, 0) != 0) return EXCEPTION_CONTINUE_SEARCH;
    __try {
        if (code != EXCEPTION_STACK_OVERFLOW) {
            DWORD offset = eip - g_truBase;
            int site = FindSite(offset, nullptr);
            if (site >= 0 && InterlockedCompareExchange(&g_sites[site].detailed, 1, 0) == 0) {
                // detailed == 0 means: first chance only logged a short note (or nothing) - this one is real
                InterlockedIncrement(&g_unhandledCount);
                Describe(info, site, true);
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

DWORD WINAPI Worker(LPVOID) {
    WaitForSingleObject(g_stop, 1000);   // let DllMain return (the loader lock is held while it runs)
    for (;;) {
        RefreshModules();
        if (WaitForSingleObject(g_stop, 2000) != WAIT_TIMEOUT) break;
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

void ReadOptions(const char *ini) {
    g_enabled = GetPrivateProfileIntA("Guard", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("Guard", "LogLevel", 1, ini);
    g_mode = GetPrivateProfileIntA("Guard", "Mode", 1, ini);
    g_firstChance = GetPrivateProfileIntA("Guard", "FirstChance", 1, ini);
    g_dump = GetPrivateProfileIntA("Guard", "Dump", 1, ini);
    g_dumpType = GetPrivateProfileIntA("Guard", "DumpType", 1, ini);
    g_maxDumps = GetPrivateProfileIntA("Guard", "MaxDumps", 16, ini);
    g_maxHitsPerSite = GetPrivateProfileIntA("Guard", "MaxHitsPerSite", 8, ini);
    g_skipUnknown = GetPrivateProfileIntA("Guard", "SkipUnknown", 0, ini);
    g_allowWriteSkip = GetPrivateProfileIntA("Guard", "AllowWriteSkip", 1, ini);
    g_allowExecuteSkip = GetPrivateProfileIntA("Guard", "AllowExecuteSkip", 1, ini);
    g_logStack = GetPrivateProfileIntA("Guard", "LogStack", 1, ini);
    g_logContext = GetPrivateProfileIntA("Guard", "LogContext", 1, ini);
    if (g_mode < 0) g_mode = 0;
    if (g_mode > 2) g_mode = 2;
    if (g_maxDumps < 0) g_maxDumps = 0;
    if (g_maxDumps > 200) g_maxDumps = 200;
    if (g_maxHitsPerSite < 1) g_maxHitsPerSite = 1;
    if (g_maxHitsPerSite > 1000) g_maxHitsPerSite = 1000;
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
    _snprintf_s(g_stackNotice, sizeof(g_stackNotice), _TRUNCATE,
                "TruGuard %s: stack overflow in tru.exe (no context, no dump)\n", g_runId);
    g_stackNoticeLen = static_cast<int>(strlen(g_stackNotice));

    g_log = CreateFileA(g_logPath, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_ALWAYS,
                        FILE_ATTRIBUTE_NORMAL, nullptr);
    Log(1, "TruGuard 0.1 loaded (enabled %d, log %d, mode %d, firstChance %d, dump %d/%d, maxDumps %d, rules %ld)",
        g_enabled, g_logLevel, g_mode, g_firstChance, g_dump, g_dumpType, g_maxDumps, g_ruleCount);
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

    if (g_dump && g_dumpType != 0) {
        CreateDirectoryA(g_dumpDir, nullptr);
        HMODULE dbghelp = LoadLibraryA("dbghelp.dll");
        if (dbghelp) g_miniDump = reinterpret_cast<MiniDumpWriteDumpFn>(
            GetProcAddress(dbghelp, "MiniDumpWriteDump"));
        if (!g_miniDump) Log(0, "dbghelp.dll / MiniDumpWriteDump not available - dumps off");
    }

    g_stop = CreateEventA(nullptr, TRUE, FALSE, nullptr);
    HANDLE thread = CreateThread(nullptr, 0, Worker, nullptr, 0, nullptr);
    if (thread) CloseHandle(thread);

    if (!AddVectoredExceptionHandler(1, Veh)) {
        Log(0, "AddVectoredExceptionHandler failed (%lu) - not watching", GetLastError());
        return;
    }
    SetUnhandledExceptionFilter(UnhandledFilter);
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
    return "TruGuard 0.1 (fault sites, minidumps, optional resume)";
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
                        "mode=%d firstChance=%ld unhandled=%ld resumed=%ld dumps=%ld sites=%ld maxSites=%d "
                        "maxHits=%d skipUnknown=%d rules=%ld log=%s",
                        g_mode, g_firstChanceCount, g_unhandledCount, g_resumedCount, g_dumpCount, sites, kMaxSites,
                        g_maxHitsPerSite, g_skipUnknown, g_ruleCount, g_logPath);
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
