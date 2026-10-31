// TruRockVein.asi - DLC 2 "Lara's Shadow" rock veins for the PC tru.exe (Steam, image base 0x400000).
//
// Lara's moves run through a data-driven state machine; transitions test numbered conditions. The Xbox title update
// added two markup conditions to SCCondTest_MarkupType (Xbox TU 0x82486dd8, retail 0x82480e78; docs Befund-Felsrinne
// "step 3.4"): 607 = "the player's markup has type 23", 608 = "... type 22" - most likely the rock vein and its jump
// target. The PC exe (like the Xbox retail exe) has no case for them: its jump table sends 604-609 to the default
// "unhandled condition" case, so every state transition that needs them is false and LB/RB + A at a rock vein does
// nothing. This plugin adds the two cases with exactly the title update's logic:
//
//   Xbox TU 607 / 608: ctx == 0 -> false; markup = [ctx+0x24] ? type byte +0x4d : ([ctx+0x20] ? type byte +0x33 : -)
//                      result = (signed char)type == 23 (607) / 22 (608)
//   PC   tru+0x1be340  the same getter already exists (thiscall: [ecx+24h]->+4Dh, else [ecx+20h]->+33h, else 0)
//   PC   tru+0x382810  SCCondTest_MarkupType (cdecl; after its push ebx / push esi: [esp+14h] condition record,
//                      [esp+18h] markup flags, [esp+1Ch] the context the TU code reads)
//   PC   tru+0x382a54  jump table for ids 601-628 (index = id - 601), default case tru+0x382a19 ("unhandled
//                      condition (%d)"), common exit tru+0x382a3f (result in bl, negation flag of the record applied)
//
// The two table entries (index 6 = 607, 7 = 608) are pointed at small stubs that compute bl and jump to the common
// exit. Optionally every other "unhandled" entry is pointed at a stub that logs the id once and then runs the
// original default case - so the next missing title-update condition shows up in TruRockVein.log.
// Every address is checked against the expected bytes first; on any mismatch nothing is patched and the reason is
// logged. Loaded by the Ultimate ASI Loader the installed game ships as binkw32.dll. Options: TruRockVein.ini.
//
// 0.2 (2026-10-31) - diagnostics for the morning test (docs Befund-Felsrinne "Rock vein: why 607/608 are never
// evaluated"). 607 / 608 are not condition ids but the u16 VALUE (+4) of a condition record {u16 key, u16 id, u16
// value, u8 flags}; the record id (610..613) selects the handler from Lara's link array, which passes the record to
// SCCondTest_MarkupType. Our converted DLC 2 state chart had these values in Xbox byte order (608 -> 24578), so the
// dispatch went to the default before the jump table and the 0.1 stubs never ran. Two read-only probes, no change of
// the game's results:
//   * LogBadValues: a 5-byte detour on `sub eax,259h` at tru+0x38288d logs every markup value > 628 (except the
//     special 1000) once - with a correct chart there are none; and at LogLevel 2 the first call of each 601..628.
//   * LogDefaultConditions: a detour on the entry of the condition default handler tru+0x382140 (Xbox
//     SCCondFunction_Default 0x82484db0: formats "You must add a condition function ...", returns true) logs each
//     condition id that reaches it once, with record key / value and the agent's state name - the title-update
//     conditions Lara's own link array lacks (TU-Abdeckung.md: 1048-1056, 2005, 2006, 2013, 2401) show up here.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>

namespace {

const DWORD kImageBase = 0x00400000;
const DWORD kDispatch = 0x0078288d;     // sub eax,259h; cmp eax,1Bh; ja default; jmp [table+eax*4]
const BYTE kDispatchBytes[] = {0x2d, 0x59, 0x02, 0x00, 0x00, 0x83, 0xf8, 0x1b, 0x0f, 0x87, 0x7e, 0x01, 0x00, 0x00,
                               0xff, 0x24, 0x85, 0x54, 0x2a, 0x78, 0x00};
const DWORD kTable = 0x00782a54;        // 28 entries, ids 601-628
const int kTableCount = 28;
const DWORD kDefault = 0x00782a19;      // cmp dx,3E8h ... "--- SCCondTest_MarkupType unhandled condition (%d) ---"
const BYTE kDefaultBytes[] = {0x66, 0x81, 0xfa, 0xe8, 0x03};
const DWORD kExit = 0x00782a3f;         // test byte [esi+6],1; je ...; test bl,bl; pop esi
const BYTE kExitBytes[] = {0xf6, 0x46, 0x06, 0x01, 0x74, 0x08, 0x84, 0xdb, 0x5e};
const DWORD kCtxUse = 0x007828c3;       // case 603: mov eax,[esp+1Ch]; push eax (the context argument)
const BYTE kCtxUseBytes[] = {0x8b, 0x44, 0x24, 0x1c, 0x50};
const DWORD kGetType = 0x005be340;      // markup type getter (thiscall), same logic as the TU's 607 / 608
const BYTE kGetTypeBytes[] = {0x8b, 0x41, 0x24, 0x85, 0xc0, 0x74, 0x05, 0x0f, 0xbe, 0x40, 0x4d, 0xc3,
                              0x8b, 0x49, 0x20, 0x85, 0xc9, 0x74, 0x05, 0x0f, 0xbe, 0x41, 0x33, 0xc3};
// the original table (tru.exe 2008 Steam build) - every entry is checked before anything is written
const DWORD kTableOriginal[kTableCount] = {
    0x007829da, 0x00782938, 0x007828b1, 0x00782a19, 0x00782a19, 0x00782a19, 0x00782a19, 0x00782a19,  // 601-608
    0x00782a19, 0x007828db, 0x00782923, 0x007828a2, 0x0078295a, 0x00782969, 0x00782978, 0x00782987,  // 609-616
    0x00782997, 0x007829a6, 0x00782a19, 0x007829b5, 0x00782a19, 0x00782a19, 0x007829c2, 0x007829ce,  // 617-624
    0x00782a0d, 0x00782978, 0x00782a19, 0x007828ea};                                                  // 625-628

// 0.2 probes
const DWORD kDispatchNext = 0x00782892; // cmp eax,1Bh (after the 5-byte sub eax,259h we detour)
const DWORD kCondDefault = 0x00782140;  // condition default handler: sub esp,204h; mov eax,[__security_cookie] ...
const BYTE kCondDefaultBytes[] = {0x81, 0xec, 0x04, 0x02, 0x00, 0x00, 0xa1, 0xe8, 0xd7, 0x8b, 0x00, 0x33, 0xc4,
                                  0x89, 0x84, 0x24, 0x00, 0x02, 0x00, 0x00, 0x8b, 0x84, 0x24, 0x10, 0x02, 0x00, 0x00,
                                  0x0f, 0xbf, 0x40, 0x02};   // ... mov eax,[esp+210h] (record); movsx eax,word [eax+2]
const DWORD kCondDefaultNext = 0x00782146;
const BYTE kFormatPush[] = {0x68, 0xa8, 0x06, 0x86, 0x00};  // tru+0x382182 push "You must add a condition ..." format
const DWORD kFormatPushAt = 0x00782182;

typedef int(__fastcall *GetTypeFn)(void *ctx, void *unused);   // thiscall getter, no stack arguments

// options (TruRockVein.ini, section [RockVein])
int g_enabled = 1;
int g_logLevel = 1;                     // 0 errors, 1 info + first unhandled ids, 2 result changes, 3 every call
int g_logUnhandled = 1;
int g_type607 = 23, g_type608 = 22;     // Xbox title update values
int g_logBadValues = 1;                 // 0.2: markup values outside 601..628 (data in the wrong byte order)
int g_logDefaultConditions = 1;         // 0.2: condition ids answered by the default handler
DWORD g_dispatchNext = kDispatchNext;
DWORD g_condDefaultNext = kCondDefaultNext;
volatile LONG g_valueSeen[29];          // 601..628 first-call flags (index value - 600)
volatile LONG g_badSeen = 0;            // number of distinct bad values logged
WORD g_badValues[64];
volatile LONG g_defaultSeen[65536 / 32];   // bit per condition id
volatile LONG g_defaultCount = 0;

char g_logPath[MAX_PATH];
char g_dir[MAX_PATH];                   // folder of the plugin (= game folder), with trailing backslash
CRITICAL_SECTION g_logLock;
DWORD g_exitAddress = kExit;            // jump targets read by the stubs
DWORD g_defaultAddress = kDefault;
int g_last[2] = {-2, -2};               // last logged (type, result) per condition, packed
LONG g_calls[2] = {0, 0};
LONG g_unhandledSeen[64];               // per table index: calls of an unhandled id

void Log(int level, const char *fmt, ...) {
    if (level > g_logLevel || !g_logPath[0]) return;
    char line[512];
    SYSTEMTIME t;
    GetLocalTime(&t);
    int n = _snprintf_s(line, sizeof(line), _TRUNCATE, "%02d:%02d:%02d.%03d ", t.wHour, t.wMinute, t.wSecond,
                        t.wMilliseconds);
    va_list ap;
    va_start(ap, fmt);
    if (n > 0) _vsnprintf_s(line + n, sizeof(line) - n, _TRUNCATE, fmt, ap);
    va_end(ap);
    EnterCriticalSection(&g_logLock);
    FILE *f = nullptr;
    if (fopen_s(&f, g_logPath, "a") == 0 && f) {
        fputs(line, f);
        fputs("\n", f);
        fclose(f);
    }
    LeaveCriticalSection(&g_logLock);
}

bool BytesAt(DWORD address, const BYTE *expected, size_t length) {
    __try {
        return memcmp(reinterpret_cast<const void *>(address), expected, length) == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

int SafeType(void *ctx, int *ok) {
    __try {
        *ok = 1;
        return reinterpret_cast<GetTypeFn>(kGetType)(ctx, nullptr);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        *ok = 0;
        return -1;
    }
}

// called from the stubs on the game thread: 1 if the context's markup has the wanted type (TU 607 / 608 semantics)
int __stdcall CheckType(void *ctx, int id, int want) {
    int slot = id == 607 ? 0 : 1;
    LONG calls = InterlockedIncrement(&g_calls[slot]);
    int type = -1, ok = 1, result = 0;
    if (ctx) {
        type = SafeType(ctx, &ok);
        result = ok && type == want;
    }
    int packed = (type & 0xff) | (result << 8) | (ctx ? 0 : 0x10000) | (ok ? 0 : 0x20000);
    if (g_logLevel >= 3)
        Log(3, "condition %d: ctx 0x%08lx type %d -> %d (call %ld)", id, reinterpret_cast<DWORD>(ctx), type, result, calls);
    else if (packed != g_last[slot])
        Log(2, "condition %d: ctx 0x%08lx type %d -> %d%s (call %ld)", id, reinterpret_cast<DWORD>(ctx), type, result,
            ok ? "" : " (read failed)", calls);
    if (calls == 1) Log(1, "condition %d is now evaluated (first call: type %d -> %d)", id, type, result);
    g_last[slot] = packed;
    return result;
}

void __stdcall LogUnhandled(int index) {
    if (index < 0 || index >= 64) return;
    LONG n = InterlockedIncrement(&g_unhandledSeen[index]);
    if (n == 1 || (g_logLevel >= 2 && (n & (n - 1)) == 0))   // first call, then 2, 4, 8 ... at level 2
        Log(1, "unhandled markup condition %d (call %ld) - not implemented on PC", 601 + index, n);
}

// jump-table targets: run inside SCCondTest_MarkupType's frame (after its push ebx / push esi), so the context
// argument is [esp+1Ch]; after pushad (32 bytes) it is [esp+32+1Ch].
__declspec(naked) void Cond607() {
    __asm {
        pushad
        mov eax, [esp + 32 + 0x1c]
        push dword ptr [g_type607]
        push 607
        push eax
        call CheckType
        mov [esp + 16], eax             // saved EBX of pushad -> bl = result
        popad
        jmp dword ptr [g_exitAddress]
    }
}

__declspec(naked) void Cond608() {
    __asm {
        pushad
        mov eax, [esp + 32 + 0x1c]
        push dword ptr [g_type608]
        push 608
        push eax
        call CheckType
        mov [esp + 16], eax
        popad
        jmp dword ptr [g_exitAddress]
    }
}

// for the other unhandled ids: eax = id - 601 (the dispatch index) - log, then the original default case
__declspec(naked) void CondUnhandled() {
    __asm {
        pushad
        push eax
        call LogUnhandled
        popad
        jmp dword ptr [g_defaultAddress]
    }
}

// ---- 0.2 probes (read only; the game's own code runs unchanged after them) ----

bool ReadRecord(const BYTE *record, WORD *out4, BYTE *flags) {
    __try {
        for (int i = 0; i < 3; ++i) out4[i] = reinterpret_cast<const WORD *>(record)[i];
        *flags = record[6];
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// from the dispatch detour: value = the markup subtest SCCondTest_MarkupType switches on (> 600 here)
void __stdcall CheckValue(int value, const BYTE *record) {
    WORD r[3] = {0, 0, 0};
    BYTE fl = 0;
    if (value >= 601 && value <= 628) {
        if (g_logLevel >= 2 && InterlockedExchange(&g_valueSeen[value - 600], 1) == 0) {
            ReadRecord(record, r, &fl);
            Log(2, "markup subtest %d first evaluated (record {%u, %u, %u, flags %u})", value, r[0], r[1], r[2], fl);
        }
        return;
    }
    if (value == 1000 || !g_logBadValues) return;
    LONG n = g_badSeen;                                 // game thread only; the list is just a log filter
    for (LONG i = 0; i < n && i < 64; ++i)
        if (g_badValues[i] == static_cast<WORD>(value)) return;
    if (n >= 64) return;
    g_badValues[n] = static_cast<WORD>(value);
    g_badSeen = n + 1;
    bool ok = ReadRecord(record, r, &fl);
    Log(1, "markup record value %d (0x%04x) is no subtest 601..628: record at 0x%08lx {%u, %u, %u, flags %u}%s - "
           "state chart data in the wrong byte order? (Xbox order of %d would be %d)",
        value, value & 0xffff, reinterpret_cast<DWORD>(record), r[0], r[1], r[2], fl, ok ? "" : " (read failed)", value,
        ((value & 0xff) << 8) | ((value >> 8) & 0xff));
}

// from the default-handler detour: agent = 1st argument, record = 3rd (as tru+0x382154 / +0x382160 read them)
void __stdcall LogDefault(const BYTE *agent, const BYTE *record) {
    if (!g_logDefaultConditions) return;
    WORD r[3] = {0, 0, 0};
    BYTE fl = 0;
    if (!ReadRecord(record, r, &fl)) return;
    int id = static_cast<short>(r[1]);
    LONG bit = 1L << (id & 31);
    if (InterlockedOr(&g_defaultSeen[(id & 0xffff) >> 5], bit) & bit) return;
    char state[64] = "?";
    WORD proc = 0;
    __try {
        const BYTE *sm = *reinterpret_cast<const BYTE *const *>(agent + 0x510);
        const char *name = sm ? *reinterpret_cast<const char *const *>(sm + 0x24) : nullptr;
        if (name) { strncpy_s(state, sizeof(state), name, _TRUNCATE); }
        const BYTE *p = *reinterpret_cast<const BYTE *const *>(agent + 4);
        if (p) proc = *reinterpret_cast<const WORD *>(p + 2);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    LONG n = InterlockedIncrement(&g_defaultCount);
    Log(1, "condition %d answered by the default handler (true): record {%u, %d, %u, flags %u}, agent 0x%08lx "
           "(AnimProcID %u) in state \"%s\" [%ld distinct]", id, r[0], id, r[2], fl, reinterpret_cast<DWORD>(agent), proc,
        state, n);
}

// detour of `sub eax,259h` (5 bytes) at tru+0x38288d: eax = value, esi = record (tru+0x382812)
__declspec(naked) void DispatchProbe() {
    __asm {
        pushad
        push esi
        push eax
        call CheckValue
        popad
        sub eax, 0x259
        jmp dword ptr [g_dispatchNext]
    }
}

// detour of `sub esp,204h` (6 bytes) at the default handler's entry: [esp+4] agent, [esp+0Ch] record
__declspec(naked) void DefaultProbe() {
    __asm {
        pushad
        push dword ptr [esp + 32 + 0x0c]      // record
        push dword ptr [esp + 32 + 0x04 + 4]  // agent (one push above)
        call LogDefault
        popad
        sub esp, 0x204
        jmp dword ptr [g_condDefaultNext]
    }
}

bool WriteJump(DWORD at, const void *to, int length) {
    BYTE code[8] = {0xe9, 0, 0, 0, 0, 0x90, 0x90, 0x90};
    DWORD rel = reinterpret_cast<DWORD>(to) - (at + 5);
    memcpy(code + 1, &rel, 4);
    DWORD old = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(at), length, PAGE_EXECUTE_READWRITE, &old)) return false;
    memcpy(reinterpret_cast<void *>(at), code, length);
    DWORD dummy = 0;
    VirtualProtect(reinterpret_cast<void *>(at), length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(at), length);
    return true;
}

void InstallProbes() {
    if (g_logBadValues || g_logLevel >= 2) {
        // the dispatch bytes were verified in Start (kDispatchBytes starts with the 5-byte sub eax,259h)
        if (WriteJump(kDispatch, &DispatchProbe, 5))
            Log(1, "probe: markup values outside 601..628 are logged (detour at 0x%08lx)", kDispatch);
        else
            Log(0, "probe at 0x%08lx not written (VirtualProtect %lu)", kDispatch, GetLastError());
    }
    if (g_logDefaultConditions) {
        // TruDoppelganger.asi verifies the first bytes of this handler before it registers its ids; the ASI loader
        // loads alphabetically, so it normally runs first - if its file is there but it is not loaded yet, our detour
        // would make its check fail: then the probe stays off
        char other[MAX_PATH];
        _snprintf_s(other, sizeof(other), _TRUNCATE, "%sTruDoppelganger.asi", g_dir);
        if (GetFileAttributesA(other) != INVALID_FILE_ATTRIBUTES && !GetModuleHandleA("TruDoppelganger.asi")) {
            Log(0, "default-condition probe off: TruDoppelganger.asi is present but not loaded yet (load order)");
            return;
        }
        if (!BytesAt(kCondDefault, kCondDefaultBytes, sizeof(kCondDefaultBytes)) ||
            !BytesAt(kFormatPushAt, kFormatPush, sizeof(kFormatPush))) {
            Log(0, "condition default handler at 0x%08lx does not match - default-condition probe off", kCondDefault);
        } else if (WriteJump(kCondDefault, &DefaultProbe, 6)) {
            Log(1, "probe: conditions answered by the default handler are logged (detour at 0x%08lx)", kCondDefault);
        } else {
            Log(0, "probe at 0x%08lx not written (VirtualProtect %lu)", kCondDefault, GetLastError());
        }
    }
}

void ReadOptions(const char *dir) {
    char ini[MAX_PATH];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruRockVein.ini", dir);
    g_enabled = GetPrivateProfileIntA("RockVein", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("RockVein", "LogLevel", 1, ini);
    g_logUnhandled = GetPrivateProfileIntA("RockVein", "LogUnhandled", 1, ini);
    g_type607 = GetPrivateProfileIntA("RockVein", "Type607", 23, ini);
    g_type608 = GetPrivateProfileIntA("RockVein", "Type608", 22, ini);
    g_logBadValues = GetPrivateProfileIntA("RockVein", "LogBadValues", 1, ini);
    g_logDefaultConditions = GetPrivateProfileIntA("RockVein", "LogDefaultConditions", 1, ini);
}

bool PatchTable() {
    DWORD *table = reinterpret_cast<DWORD *>(kTable);
    DWORD old = 0;
    if (!VirtualProtect(table, kTableCount * sizeof(DWORD), PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "VirtualProtect failed (%lu) - not patched", GetLastError());
        return false;
    }
    table[607 - 601] = reinterpret_cast<DWORD>(&Cond607);
    table[608 - 601] = reinterpret_cast<DWORD>(&Cond608);
    int logged = 0;
    if (g_logUnhandled) {
        for (int i = 0; i < kTableCount; ++i) {
            if (i == 607 - 601 || i == 608 - 601 || kTableOriginal[i] != kDefault) continue;
            table[i] = reinterpret_cast<DWORD>(&CondUnhandled);
            ++logged;
        }
    }
    DWORD dummy = 0;
    VirtualProtect(table, kTableCount * sizeof(DWORD), old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), table, kTableCount * sizeof(DWORD));
    Log(1, "jump table patched: 607 -> 0x%08lx (type %d), 608 -> 0x%08lx (type %d), %d unhandled ids logged",
        reinterpret_cast<DWORD>(&Cond607), g_type607, reinterpret_cast<DWORD>(&Cond608), g_type608, logged);
    return true;
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruRockVein.log", dir);
    strncpy_s(g_dir, sizeof(g_dir), dir, _TRUNCATE);
    ReadOptions(dir);
    Log(1, "TruRockVein 0.2 loaded (enabled %d, log level %d, log unhandled %d, bad values %d, default conditions %d)",
        g_enabled, g_logLevel, g_logUnhandled, g_logBadValues, g_logDefaultConditions);
    if (!g_enabled) { Log(1, "disabled by TruRockVein.ini - nothing patched"); return; }
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - not patched", base, kImageBase); return; }
    if (!BytesAt(kDispatch, kDispatchBytes, sizeof(kDispatchBytes)) || !BytesAt(kDefault, kDefaultBytes, sizeof(kDefaultBytes)) ||
        !BytesAt(kExit, kExitBytes, sizeof(kExitBytes)) || !BytesAt(kCtxUse, kCtxUseBytes, sizeof(kCtxUseBytes))) {
        Log(0, "SCCondTest_MarkupType at 0x%08lx does not match (other tru.exe build?) - not patched", kDispatch);
        return;
    }
    if (!BytesAt(kGetType, kGetTypeBytes, sizeof(kGetTypeBytes))) {
        Log(0, "markup type getter at 0x%08lx does not match - not patched", kGetType);
        return;
    }
    if (!BytesAt(kTable, reinterpret_cast<const BYTE *>(kTableOriginal), sizeof(kTableOriginal))) {
        Log(0, "condition jump table at 0x%08lx is not the original (patched by something else?) - not patched", kTable);
        return;
    }
    Log(3, "code checks passed (dispatch, default case, exit, context use, type getter, table)");
    if (PatchTable()) InstallProbes();
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        InitializeCriticalSection(&g_logLock);
        Start(instance);
    }
    return TRUE;
}

// exported so the loader / tools can identify the plugin (the Ultimate ASI Loader needs no particular export)
extern "C" __declspec(dllexport) const char *TruRockVeinVersion() { return "TruRockVein 0.2 (markup conditions 607 / 608, chart probes)"; }
