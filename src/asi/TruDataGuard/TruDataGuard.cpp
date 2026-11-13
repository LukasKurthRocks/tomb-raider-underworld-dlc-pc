// TruDataGuard.asi - turns invalid section ids into a logged "not found" instead of a crash, at known lookup points
// only, using the engine's own not-found path (PC tru.exe, Steam, image base 0x400000). Safety net and detector; the
// real fix stays in the converter (docs Plan-TruDataGuard.md, Befund-Felsrinne.md "Crash ... tru+0x14df84").
//
// Section lookup tru+0x14df80 (cdecl, one argument):
//     mov eax,[esp+4]; mov eax,[eax*4+0C36F28h]; test eax,eax; je zero; cmp byte [eax+4],0; jne zero; add eax,10h; ret
//     zero: xor eax,eax; ret
//   The table 0xc36f28 has 0x8000 entries: the register function tru+0x14dd10 asserts 0 < id < 0x8000; an entry is a
//   section record {u16 refs, u16, u8 loading, u8 type (flags >> 1 & 0x7f), ...} allocated through [0xc56fc4] +0x34
//   with a 0x10-byte header; data at +0x10. Free (tru+0x14dee0) clears the entry.
//   Crashes 2026-11-02: ids with swapped u16 halves or misread words - 0x688c0000 (50d, player event 0x87),
//   0x495f0000 (50e, fx node, entry read 0x2104), 0x04900000 (50f, state-chart parameter), 0x00652000 (50h, thrall
//   anim event list). All four are >= 0x8000; in the two full dumps of 50f / 50h all 2317 / 2718 non-zero entries are
//   16-byte aligned record pointers with refs 1..9, loading 0, type <= 34 (tools/dataguard_check.py table).
//   Refs 0 is a legitimate transitional state (0.2): the release tru+0x14f320 (section manager vtable 0x84c990 +0x18)
//   decrements refs and, at 0, calls the type pre-unload tru+0x14f200 and the type handler's unload callback
//   ([0xc57000 + type*4] vtable +8) while the entry is still set; only then it frees the record and clears the entry.
//   The type-13 handler (vtable 0x84ca70, +8 = tru+0x18bd30) looks its section up there (return tru+0x18bd3a): 0.1
//   rejected those 20+ lookups per level change as "not a section record" (runs 50j / 50k, tools/dataguard_check.py
//   hits). The record checks stay: pointer (aligned, >= 0x10000), loading flag 0 / 1, type <= 0x7f.
// Exists test tru+0x14df70 (cdecl): mov eax,[esp+4]; cmp dword [eax*4+0C36F28h],0; setne al; ret - one caller
//   (tru+0x12cd85, `test al,al`).
//
// The guard replaces the first 5 bytes of both functions with a jump to a stub that does the same work plus the bound
// and record checks BEFORE anything is dereferenced. A rejected lookup returns 0 ("not found") only to callers that
// test the result for 0 (static list kGuardedCallers, built by tools/dataguard_check.py callers; every entry is
// byte-checked at load: an E8 call to the lookup right before the return address). For any other caller the original
// lookup runs unchanged (option UncheckedCallers=0) after the log line, or returns 0 anyway (UncheckedCallers=1).
// 0.2.2: an id OUTSIDE the table (>= 0x8000, not -1) returns "not found" to every caller, also to callers that do not
//   test for 0: the original would read [0xc36f28 + id*4] beyond the 0x8000 entries (other globals or unmapped memory),
//   so it has no valid answer to give. Crash 2026-11-13 12:05:40 (docs Befund-DLC1-Absturz-Spinne-1311.md): id
//   0x24910000 (Xbox DTP 0x2491 as a u16 pair, AI record of DTP 20872 +0x5530 +0x1f4, small albino spider "melee")
//   from caller tru+0x19500f (tru+0x194ff0, AI attack sound, does not test for 0) ran the original and faulted at
//   0x93076f28. That path is NULL-safe: tru+0x194ea0 uses the section only as a hash key (tru+0x18d4a0) and as sound
//   data for the emitter tru+0x1935d0, which tests it for 0 (handle 0, no sound). Implausible ENTRIES inside the table
//   keep the 0.2 rule (unchecked callers: logged, original lookup).
// The fast path touches only eax and the flags, like the original. No exception is caught after a fault.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include "../TruLog.h"                      // Q107: date + time in every log line, session header
extern "C" __declspec(dllexport) const char *TruDataGuardVersion();   // Q107 session header (defined at the end)

namespace {

const DWORD kImageBase = 0x00400000;
const DWORD kLookup = 0x0054df80;
const char *const kLookupHex = "8b442404 8b0485286fc300 85c0 740a 80780400 7504 83c010 c3 33c0 c3";
const DWORD kExists = 0x0054df70;
const char *const kExistsHex = "8b442404 833c85286fc30000 0f95c0 c3";
const DWORD kRegister = 0x0054dd10;     // the bound: cmp esi,8000h; jae assert; test esi,esi; jg ok
const char *const kRegisterHex = "56 8b742408 81fe00800000 7304 85f6 7f0d";
const DWORD kTableAddress = 0x00c36f28;
const DWORD kTableCount = 0x8000;
const DWORD kMinPointer = 0x10000;
const DWORD kAlignMask = 0xf;           // every record seen in the 50f / 50h dumps is 16-byte aligned

// return addresses of the callers that test the lookup result for 0 before using it (tools/dataguard_check.py callers
// tru.exe, class TESTS: test / cmp with 0 + je / jne, and the 0 path does not dereference it). Sorted.
const DWORD kGuardedCallers[] = {
    0x004b0456, 0x00535e2d, 0x00535ec5, 0x005833b6, 0x005833e9, 0x005920f4, 0x00594c71, 0x00594cad,
    0x005953f2, 0x005d60ea, 0x005d613a, 0x005d618d, 0x005d6557, 0x005d659f, 0x005d6ccf, 0x005d6d07,
    0x005d6d5d, 0x005e207b, 0x005e21c2, 0x005e24a4, 0x005e3514, 0x005e37cb, 0x005e3ca6, 0x005e3eae,
    0x005e9b9c, 0x005e9c69, 0x005e9d36, 0x005f17bf, 0x005f17ee, 0x005f1c27, 0x005f1c57, 0x005f84cf,
    0x005f8eff, 0x005f9144, 0x005f91eb, 0x005f9306, 0x005f982c, 0x005f9a65, 0x005f9b55, 0x005f9f4f,
    0x005fa095, 0x005faae5, 0x005fac16, 0x005fc87f, 0x005fca9a, 0x005fcd95, 0x005fd996, 0x005fdd64,
    0x005fde04, 0x005fdee9, 0x005fe2ef, 0x005fe945, 0x005fea35, 0x005fee2f, 0x005fef75, 0x005ff815,
    0x005ff946, 0x00600c2f, 0x00600e5a, 0x00601155, 0x00601d56, 0x00602124, 0x006021c4, 0x006022a9,
    0x006026af, 0x00602b55, 0x00602f38, 0x006031b3, 0x0060448f, 0x00604b3f, 0x00604d56, 0x006052f4,
    0x00605593, 0x0060714f, 0x006072df, 0x00607506, 0x006076d1, 0x0060b364, 0x0060b631, 0x0060cb6f,
    0x0060cd56, 0x0060cffe, 0x0060d134, 0x0060d2bf, 0x006cc8e0, 0x00776760};
const int kGuardedCount = sizeof(kGuardedCallers) / sizeof(kGuardedCallers[0]);
const DWORD kExistsCaller = 0x0052cd8a;  // test al,al; jne exists - 0 = the engine's "missing" branch

// stream unit Lara is in (as TruMenu 0.7.1): id [0xe7f148], table 0xdbab40..0xdbc640 (0xd8 each, +4 state 2, +0xc name)
const DWORD kUnitId = 0x00e7f148;
const DWORD kStreamUnits = 0x00dbab40, kStreamUnitsEnd = 0x00dbc640, kStreamUnitSize = 0xd8;
const char *const kUnitLookupHex = "56 8b742408 33c0 33d2 b940abdb00 8bff 80790402 7504 3931 7413 81c1d8000000 83c201";
const char *const kUnitStoreHex = "893d48f1e700";     // tru+0x1c1c4e: STREAM_MoveIntoNewStreamUnit stores the id
const char *const kUnitNameHex = "e823ffffff 8b0db0a2db00 8d680c 55 6868428500";   // tru+0x1c1c28: name at +0xc

// hit kinds (OnBad)
const DWORD kKindId = 1, kKindEntry = 2, kKindExistsId = 3, kKindExistsEntry = 4;

// options (TruDataGuard.ini, section [DataGuard])
int g_enabled = 1;
int g_logLevel = 1;                     // 0 errors, 1 info + first hits + first hit per caller, 2 + powers of two, 3 all
int g_sectionLookup = 1;
int g_sectionExists = 1;
int g_uncheckedCallers = 0;             // 1 = return 0 also to callers that do not test for 0
int g_logFirst = 20;                    // detailed hit lines
int g_logUnit = 1;                      // name the stream unit in hit lines

// read by the stubs (variables, so the self test can point them at a test table)
DWORD g_table = kTableAddress;
DWORD g_count = kTableCount;
bool g_guardedOk[sizeof(kGuardedCallers) / sizeof(kGuardedCallers[0])];
bool g_existsCallerOk = false;
bool g_unitOk = false;
bool g_installed = false;
bool g_testMode = false;                // self test: every caller counts as guarded unless g_testUnguarded
bool g_testUnguarded = false;

volatile LONG g_hits = 0;
volatile LONG g_hitsByKind[5] = {0, 0, 0, 0, 0};
volatile LONG g_detailed = 0;
DWORD g_callersSeen[64];
volatile LONG g_callersSeenCount = 0;
DWORD g_lastId = 0, g_lastCaller = 0, g_lastKind = 0;

char g_logPath[MAX_PATH];
CRITICAL_SECTION g_logLock;

void Log(int level, const char *fmt, ...) {
    if (level > g_logLevel || !g_logPath[0]) return;
    char line[640];
    int n = TruLogStamp(line, sizeof(line));     // Q107: "YYYY-MM-DD HH:MM:SS.mmm "
    va_list ap;
    va_start(ap, fmt);
    if (n > 0) _vsnprintf_s(line + n, sizeof(line) - n, _TRUNCATE, fmt, ap);
    va_end(ap);
    EnterCriticalSection(&g_logLock);
    FILE *f = nullptr;
    if (fopen_s(&f, g_logPath, "a") == 0 && f) {
        TruLogSessionStart(f, "TruDataGuard", TruDataGuardVersion());
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

bool HexBytesAt(DWORD address, const char *hex) {
    BYTE buf[96];
    size_t n = 0;
    for (const char *p = hex; *p && n < sizeof(buf);) {
        if (*p == ' ') { ++p; continue; }
        char two[3] = {p[0], p[1], 0};
        buf[n++] = static_cast<BYTE>(strtoul(two, nullptr, 16));
        p += 2;
    }
    return BytesAt(address, buf, n);
}

// our own data reads for the log (stream unit name) - never game code
bool ReadDword(DWORD address, DWORD *out) {
    __try {
        *out = *reinterpret_cast<const volatile DWORD *>(address);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool ReadName(DWORD address, char *out, size_t size) {
    out[0] = 0;
    __try {
        size_t i = 0;
        const volatile char *p = reinterpret_cast<const volatile char *>(address);
        for (; i + 1 < size && p[i]; ++i) {
            char c = p[i];
            if (c < 32 || c > 126) { out[0] = 0; return false; }
            out[i] = c;
        }
        out[i] = 0;
        return out[0] != 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        out[0] = 0;
        return false;
    }
}

void UnitName(char *out, size_t size) {
    strncpy_s(out, size, "-", _TRUNCATE);
    if (!g_unitOk || !g_logUnit) return;
    DWORD id = 0;
    if (!ReadDword(kUnitId, &id)) return;
    for (DWORD e = kStreamUnits; e < kStreamUnitsEnd; e += kStreamUnitSize) {
        DWORD eid = 0, state = 0;
        if (!ReadDword(e, &eid) || !ReadDword(e + 4, &state)) return;
        if ((state & 0xff) != 2 || eid != id) continue;
        char name[64];
        if (ReadName(e + 0xc, name, sizeof(name))) strncpy_s(out, size, name, _TRUNCATE);
        return;
    }
}

bool IsGuarded(DWORD ret) {
    int lo = 0, hi = kGuardedCount - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (kGuardedCallers[mid] == ret) return g_guardedOk[mid];
        if (kGuardedCallers[mid] < ret) lo = mid + 1;
        else hi = mid - 1;
    }
    return false;
}

bool FirstFromCaller(DWORD ret) {
    LONG n = g_callersSeenCount;
    for (LONG i = 0; i < n && i < 64; ++i)
        if (g_callersSeen[i] == ret) return false;
    LONG slot = InterlockedIncrement(&g_callersSeenCount) - 1;
    if (slot < 64) g_callersSeen[slot] = ret;
    return true;
}

// Called by the stubs on a rejected id / entry (game thread). Returns 0 = answer "not found", 1 = run the original
// lookup (implausible entry, caller does not test for 0 and UncheckedCallers=0). An id outside the table is always
// answered 0 (0.2.2: the original would read beyond the table). Logs first, so a following crash has its line.
DWORD __stdcall OnBad(DWORD kind, DWORD id, DWORD entry, DWORD ret) {
    bool exists = kind == kKindExistsId || kind == kKindExistsEntry;
    bool outside = kind == kKindId || kind == kKindExistsId;
    bool guarded = g_testMode ? !g_testUnguarded : (exists ? (ret == kExistsCaller && g_existsCallerOk) : IsGuarded(ret));
    DWORD answer = (guarded || g_uncheckedCallers || outside) ? 0 : 1;
    LONG n = InterlockedIncrement(&g_hits);
    if (kind < 5) InterlockedIncrement(&g_hitsByKind[kind]);
    g_lastId = id;
    g_lastCaller = ret;
    g_lastKind = kind;
    bool first = FirstFromCaller(ret);
    bool detail = (g_logLevel >= 3) || (g_logLevel >= 1 && (n <= g_logFirst || first)) ||
                  (g_logLevel >= 2 && (n & (n - 1)) == 0);
    if (!detail) return answer;
    char unit[64];
    UnitName(unit, sizeof(unit));
    char what[128];
    if (kind == kKindId || kind == kKindExistsId)
        _snprintf_s(what, sizeof(what), _TRUNCATE, "outside the section table 0..0x%lx", g_count - 1);
    else {
        // record header {u16 refs, u16, u8 loading, u8 type} - our own guarded read, for the log only
        DWORD w0 = 0, w1 = 0;
        if (entry >= kMinPointer && ReadDword(entry, &w0) && ReadDword(entry + 4, &w1))
            _snprintf_s(what, sizeof(what), _TRUNCATE,
                        "table entry 0x%08lx is not a section record: refs %lu, loading %lu, type %lu", entry,
                        w0 & 0xffff, w1 & 0xff, (w1 >> 8) & 0xff);
        else
            _snprintf_s(what, sizeof(what), _TRUNCATE, "table entry 0x%08lx is not a section record", entry);
    }
    Log(1, "invalid id 0x%08lx (%s) in %s tru+0x%lx, caller 0x%08lx (tru+0x%lx, %s) -> %s%s; unit %s; hit %ld%s", id,
        what, exists ? "section exists test" : "section lookup", (exists ? kExists : kLookup) - kImageBase, ret,
        ret - kImageBase, guarded ? "tests for 0" : "does not test for 0",
        answer == 0 ? (exists ? "answered 'missing'" : "returned 0 (not found)")
                    : "original lookup runs (UncheckedCallers=0) - a crash may follow",
        (answer == 0 && !guarded && !g_uncheckedCallers) ? " (0.2.2: id outside the table, the original would read "
                                                           "beyond it)" : "",
        unit, n, (n == g_logFirst && g_logLevel < 3) ? " (further hits: first per caller, then counted)" : "");
    return answer;
}

// ---- stubs (naked: the fast path uses eax and the flags only, like the original) ----

__declspec(naked) void LookupStub() {
    __asm {
        mov eax, [esp+4]
        cmp eax, dword ptr [g_count]
        jae bad_id
        shl eax, 2
        add eax, dword ptr [g_table]
        mov eax, [eax]
        test eax, eax
        je zero
        test al, 0x0f                   // kAlignMask
        jne bad_entry
        cmp eax, 0x10000                // kMinPointer
        jb bad_entry
        // refs (u16 at +0) is not checked since 0.2: the release tru+0x14f320 calls the unload callbacks with refs 0
        cmp byte ptr [eax+4], 1         // loading flag 0 / 1
        ja bad_entry
        cmp byte ptr [eax+5], 0x7f      // type (flags >> 1) & 0x7f
        ja bad_entry
        cmp byte ptr [eax+4], 0
        jne zero
        add eax, 0x10
        ret
    zero:
        xor eax, eax
        ret
    bad_id:
        cmp eax, 0xffffffff             // "none" id; callers test for -1 first, the original reads 0 before the table
        je zero
        push 1                          // kKindId
        jmp slow
    bad_entry:
        push 2                          // kKindEntry
    slow:
        // [esp] kind, [esp+4] return address, [esp+8] id
        push ecx
        push edx
        sub esp, 0x80
        movdqu xmmword ptr [esp], xmm0
        movdqu xmmword ptr [esp+0x10], xmm1
        movdqu xmmword ptr [esp+0x20], xmm2
        movdqu xmmword ptr [esp+0x30], xmm3
        movdqu xmmword ptr [esp+0x40], xmm4
        movdqu xmmword ptr [esp+0x50], xmm5
        movdqu xmmword ptr [esp+0x60], xmm6
        movdqu xmmword ptr [esp+0x70], xmm7
        // [esp+0x80] edx, +0x84 ecx, +0x88 kind, +0x8c return address, +0x90 id
        push dword ptr [esp+0x8c]       // ret
        push eax                        // entry (kind 2) / id (kind 1)
        push dword ptr [esp+0x98]       // id
        push dword ptr [esp+0x94]       // kind
        call OnBad
        movdqu xmm0, xmmword ptr [esp]
        movdqu xmm1, xmmword ptr [esp+0x10]
        movdqu xmm2, xmmword ptr [esp+0x20]
        movdqu xmm3, xmmword ptr [esp+0x30]
        movdqu xmm4, xmmword ptr [esp+0x40]
        movdqu xmm5, xmmword ptr [esp+0x50]
        movdqu xmm6, xmmword ptr [esp+0x60]
        movdqu xmm7, xmmword ptr [esp+0x70]
        add esp, 0x80
        pop edx
        pop ecx
        add esp, 4                      // kind
        test eax, eax
        jne original
        ret                             // eax = 0: not found
    original:
        // the unchanged original lookup (tru+0x14df80) for a caller that does not test for 0
        mov eax, [esp+4]
        shl eax, 2
        add eax, dword ptr [g_table]
        mov eax, [eax]
        test eax, eax
        je zero
        cmp byte ptr [eax+4], 0
        jne zero
        add eax, 0x10
        ret
    }
}

__declspec(naked) void ExistsStub() {
    __asm {
        mov eax, [esp+4]
        cmp eax, dword ptr [g_count]
        jae bad_id
        shl eax, 2
        add eax, dword ptr [g_table]
        mov eax, [eax]
        test eax, eax
        je answer
        test al, 0x0f
        jne bad_entry
        cmp eax, 0x10000
        jb bad_entry
    answer:
        // the original: cmp dword [id*4+table],0; setne al (eax keeps the id's upper bytes)
        test eax, eax
        mov eax, [esp+4]
        setne al
        ret
    bad_id:
        cmp eax, 0xffffffff
        je missing
        push 3                          // kKindExistsId
        jmp slow
    bad_entry:
        push 4                          // kKindExistsEntry
    slow:
        push ecx
        push edx
        sub esp, 0x80
        movdqu xmmword ptr [esp], xmm0
        movdqu xmmword ptr [esp+0x10], xmm1
        movdqu xmmword ptr [esp+0x20], xmm2
        movdqu xmmword ptr [esp+0x30], xmm3
        movdqu xmmword ptr [esp+0x40], xmm4
        movdqu xmmword ptr [esp+0x50], xmm5
        movdqu xmmword ptr [esp+0x60], xmm6
        movdqu xmmword ptr [esp+0x70], xmm7
        push dword ptr [esp+0x8c]
        push eax
        push dword ptr [esp+0x98]
        push dword ptr [esp+0x94]
        call OnBad
        movdqu xmm0, xmmword ptr [esp]
        movdqu xmm1, xmmword ptr [esp+0x10]
        movdqu xmm2, xmmword ptr [esp+0x20]
        movdqu xmm3, xmmword ptr [esp+0x30]
        movdqu xmm4, xmmword ptr [esp+0x40]
        movdqu xmm5, xmmword ptr [esp+0x50]
        movdqu xmm6, xmmword ptr [esp+0x60]
        movdqu xmm7, xmmword ptr [esp+0x70]
        add esp, 0x80
        pop edx
        pop ecx
        add esp, 4
        test eax, eax
        jne original
    missing:
        xor eax, eax                    // al = 0: missing
        ret
    original:
        mov eax, [esp+4]
        shl eax, 2
        add eax, dword ptr [g_table]
        cmp dword ptr [eax], 0
        mov eax, [esp+4]
        setne al
        ret
    }
}

bool WriteJump(DWORD at, const void *to) {
    BYTE code[5] = {0xe9, 0, 0, 0, 0};
    DWORD rel = reinterpret_cast<DWORD>(to) - (at + 5);
    memcpy(code + 1, &rel, 4);
    DWORD old = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(at), 5, PAGE_EXECUTE_READWRITE, &old)) return false;
    memcpy(reinterpret_cast<void *>(at), code, 5);
    DWORD dummy = 0;
    VirtualProtect(reinterpret_cast<void *>(at), 5, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(at), 5);
    return true;
}

// an E8 call to `target` right before the return address
bool CallsTarget(DWORD ret, DWORD target) {
    BYTE code[5];
    DWORD rel = target - ret;
    code[0] = 0xe8;
    memcpy(code + 1, &rel, 4);
    return BytesAt(ret - 5, code, 5);
}

void ReadOptions(const char *dir) {
    char ini[MAX_PATH];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruDataGuard.ini", dir);
    g_enabled = GetPrivateProfileIntA("DataGuard", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("DataGuard", "LogLevel", 1, ini);
    g_sectionLookup = GetPrivateProfileIntA("DataGuard", "SectionLookup", 1, ini);
    g_sectionExists = GetPrivateProfileIntA("DataGuard", "SectionExists", 1, ini);
    g_uncheckedCallers = GetPrivateProfileIntA("DataGuard", "UncheckedCallers", 0, ini);
    g_logFirst = GetPrivateProfileIntA("DataGuard", "LogFirst", 20, ini);
    g_logUnit = GetPrivateProfileIntA("DataGuard", "LogUnit", 1, ini);
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruDataGuard.log", dir);
    ReadOptions(dir);
    Log(1, "TruDataGuard 0.2.2 loaded (enabled %d, log level %d, section lookup %d, section exists %d, unchecked callers "
        "%d, log first %d, log unit %d)", g_enabled, g_logLevel, g_sectionLookup, g_sectionExists, g_uncheckedCallers,
        g_logFirst, g_logUnit);
    if (!g_enabled) { Log(1, "disabled by TruDataGuard.ini - nothing patched"); return; }
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - not patched", base, kImageBase); return; }
    if (!HexBytesAt(kRegister, kRegisterHex)) {
        Log(0, "section register tru+0x%lx does not match (table bound 0x8000 not proven) - not patched",
            kRegister - kImageBase);
        return;
    }
    g_unitOk = HexBytesAt(0x005c1b50, kUnitLookupHex) && HexBytesAt(0x005c1c4e, kUnitStoreHex) &&
               HexBytesAt(0x005c1c28, kUnitNameHex);
    if (!g_unitOk) Log(1, "stream unit code does not match - hit lines without unit name");
    int ok = 0;
    for (int i = 0; i < kGuardedCount; ++i) {
        g_guardedOk[i] = CallsTarget(kGuardedCallers[i], kLookup);
        if (g_guardedOk[i]) ++ok;
        else Log(0, "guarded caller 0x%08lx: no call of tru+0x%lx before it - treated as not testing for 0",
                 kGuardedCallers[i], kLookup - kImageBase);
    }
    g_existsCallerOk = CallsTarget(kExistsCaller, kExists) && HexBytesAt(kExistsCaller, "83c404 84c0 7517");
    if (g_sectionLookup) {
        if (!HexBytesAt(kLookup, kLookupHex))
            Log(0, "section lookup tru+0x%lx does not match - guard off", kLookup - kImageBase);
        else if (WriteJump(kLookup, &LookupStub)) {
            g_installed = true;
            Log(1, "guard on: section lookup tru+0x%lx (ids >= 0x%lx -> not found for every caller; implausible records "
                "-> not found for %d of %d checked callers that test for 0; other callers: %s)", kLookup - kImageBase,
                kTableCount, ok, kGuardedCount, g_uncheckedCallers ? "also 0" : "logged, original lookup");
        } else
            Log(0, "section lookup tru+0x%lx not written (VirtualProtect %lu)", kLookup - kImageBase, GetLastError());
    }
    if (g_sectionExists) {
        if (!HexBytesAt(kExists, kExistsHex))
            Log(0, "section exists test tru+0x%lx does not match - guard off", kExists - kImageBase);
        else if (WriteJump(kExists, &ExistsStub)) {
            g_installed = true;
            Log(1, "guard on: section exists test tru+0x%lx (caller tru+0x%lx checked %d)", kExists - kImageBase,
                kExistsCaller - kImageBase, g_existsCallerOk ? 1 : 0);
        } else
            Log(0, "section exists test tru+0x%lx not written (VirtualProtect %lu)", kExists - kImageBase, GetLastError());
    }
}

// ---- offline self test (tools: SelfTest.exe loads the built .asi and calls this; refuses inside the game) ----

typedef DWORD(__cdecl *LookupFn)(DWORD id);

// calls a stub with sentinel values in ecx / edx / ebx / esi / edi / xmm0 / xmm7 and checks them afterwards
DWORD CallChecked(const void *fn, DWORD id, int *regsOk) {
    DWORD result = 0, ok = 0;
    __asm {
        mov ecx, 0x11111111
        mov edx, 0x22222222
        mov ebx, 0x33333333
        mov esi, 0x44444444
        mov edi, 0x55555555
        mov eax, 0x66666666
        movd xmm0, eax
        mov eax, 0x77777777
        movd xmm7, eax
        push id
        call fn
        add esp, 4
        mov result, eax
        xor eax, eax
        cmp ecx, 0x11111111
        jne done
        cmp edx, 0x22222222
        jne done
        cmp ebx, 0x33333333
        jne done
        cmp esi, 0x44444444
        jne done
        cmp edi, 0x55555555
        jne done
        movd eax, xmm0
        cmp eax, 0x66666666
        mov eax, 0
        jne done
        movd eax, xmm7
        cmp eax, 0x77777777
        mov eax, 0
        jne done
        mov eax, 1
    done:
        mov ok, eax
    }
    *regsOk = static_cast<int>(ok);
    return result;
}

struct TestOut {
    char *buf;
    size_t size;
    size_t used;
    int failed;
    int passed;
};

void Report(TestOut *o, bool pass, const char *fmt, ...) {
    char line[256];
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf_s(line, sizeof(line), _TRUNCATE, fmt, ap);
    va_end(ap);
    if (pass) ++o->passed; else ++o->failed;
    int n = _snprintf_s(o->buf + o->used, o->size - o->used, _TRUNCATE, "%s %s\n", pass ? "ok  " : "FAIL", line);
    if (n > 0) o->used += n;
}

__declspec(align(16)) BYTE g_testRecords[8][64];
DWORD g_testTable[0x8000];

void CheckLookup(TestOut *o, const char *name, DWORD id, DWORD expect, LONG expectHits, DWORD expectKind) {
    LONG before = g_hits;
    int regs = 0;
    DWORD got = CallChecked(&LookupStub, id, &regs);
    LONG hits = g_hits - before;
    bool pass = got == expect && hits == expectHits && regs == 1 && (expectHits == 0 || g_lastKind == expectKind);
    Report(o, pass, "lookup %-34s id 0x%08lx -> 0x%08lx (want 0x%08lx), hits %ld (want %ld), registers %s", name, id,
           got, expect, hits, expectHits, regs ? "kept" : "CHANGED");
}

void CheckExists(TestOut *o, const char *name, DWORD id, BYTE expect, LONG expectHits) {
    LONG before = g_hits;
    int regs = 0;
    DWORD got = CallChecked(&ExistsStub, id, &regs);
    LONG hits = g_hits - before;
    bool pass = static_cast<BYTE>(got) == expect && hits == expectHits && regs == 1;
    Report(o, pass, "exists %-34s id 0x%08lx -> al %u (want %u), hits %ld (want %ld), registers %s", name, id,
           static_cast<BYTE>(got), expect, hits, expectHits, regs ? "kept" : "CHANGED");
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

// hit counter for TruMenu / tools (all kinds since the start)
extern "C" __declspec(dllexport) LONG __cdecl TruDataGuardHits() { return g_hits; }

// last hit: id, return address of the caller, kind (1 id / 2 entry / 3, 4 the same in the exists test)
extern "C" __declspec(dllexport) void __cdecl TruDataGuardLastHit(DWORD *id, DWORD *caller, DWORD *kind) {
    if (id) *id = g_lastId;
    if (caller) *caller = g_lastCaller;
    if (kind) *kind = g_lastKind;
}

// Offline self test of the real stubs against a test table (never inside the game: refuses once a guard is
// installed). Writes one line per case into report; returns the number of failed cases (-1 = refused).
extern "C" __declspec(dllexport) int __cdecl TruDataGuardSelfTest(char *report, int size) {
    if (!report || size < 256) return -1;
    report[0] = 0;
    TestOut o = {report, static_cast<size_t>(size), 0, 0, 0};
    if (g_installed) {
        Report(&o, false, "refused: the guard is installed in this process (game) - the self test runs offline only");
        return -1;
    }
    DWORD savedTable = g_table, savedCount = g_count;
    int savedLevel = g_logLevel;
    if (g_logLevel < 1) g_logLevel = 1; // the hit lines go to TruDataGuard.log next to the tested .asi (format check)
    Log(1, "self test start (test table, every hit below is a planted case)");
    memset(g_testTable, 0, sizeof(g_testTable));
    memset(g_testRecords, 0, sizeof(g_testRecords));
    // record layout {u16 refs, u16, u8 loading, u8 type}: 0 good, 1 loading, 2 refs 0 (release state: the unload
    // callback of tru+0x14f320 runs with refs 0), 3 type 0x80, 4 loading flag 2, 5 refs 0 and still loading
    BYTE *good = g_testRecords[0], *loading = g_testRecords[1], *norefs = g_testRecords[2], *badtype = g_testRecords[3];
    BYTE *badloading = g_testRecords[4], *norefsLoading = g_testRecords[5];
    good[0] = 1; good[5] = 13;
    loading[0] = 1; loading[4] = 1; loading[5] = 19;
    norefs[0] = 0; norefs[5] = 13;
    badtype[0] = 2; badtype[5] = 0x80;
    badloading[0] = 1; badloading[4] = 2; badloading[5] = 13;
    norefsLoading[0] = 0; norefsLoading[4] = 1; norefsLoading[5] = 13;
    DWORD goodAt = reinterpret_cast<DWORD>(good);
    g_testTable[0x688c] = goodAt;                                   // 50d: the intended id of 0x688c0000
    g_testTable[0x0100] = reinterpret_cast<DWORD>(loading);
    g_testTable[0x0101] = reinterpret_cast<DWORD>(norefs);
    g_testTable[0x0102] = reinterpret_cast<DWORD>(badtype);
    g_testTable[0x0105] = reinterpret_cast<DWORD>(badloading);
    g_testTable[0x0106] = reinterpret_cast<DWORD>(norefsLoading);
    g_testTable[0x0103] = 0x00002104;                               // 50e: the entry value read for 0x495f0000
    g_testTable[0x0104] = goodAt + 4;                               // misaligned
    g_testTable[0x7fff] = goodAt;                                   // last valid id
    g_table = reinterpret_cast<DWORD>(g_testTable);
    g_count = kTableCount;
    g_testMode = true;
    g_testUnguarded = false;

    CheckLookup(&o, "good record", 0x688c, goodAt + 0x10, 0, 0);
    CheckLookup(&o, "last id 0x7fff", 0x7fff, goodAt + 0x10, 0, 0);
    CheckLookup(&o, "empty entry", 0x0001, 0, 0, 0);
    CheckLookup(&o, "record still loading", 0x0100, 0, 0, 0);
    CheckLookup(&o, "none id -1", 0xffffffff, 0, 0, 0);
    CheckLookup(&o, "50d player event 0x87", 0x688c0000, 0, 1, kKindId);
    CheckLookup(&o, "50e fx node", 0x495f0000, 0, 1, kKindId);
    CheckLookup(&o, "50f state-chart parameter", 0x04900000, 0, 1, kKindId);
    CheckLookup(&o, "50h thrall anim event list", 0x00652000, 0, 1, kKindId);
    CheckLookup(&o, "first id past the table 0x8000", 0x8000, 0, 1, kKindId);
    CheckLookup(&o, "entry 0x2104 (not a pointer)", 0x0103, 0, 1, kKindEntry);
    CheckLookup(&o, "misaligned entry", 0x0104, 0, 1, kKindEntry);
    CheckLookup(&o, "refs 0 (unload callback, 0.2)", 0x0101, reinterpret_cast<DWORD>(norefs) + 0x10, 0, 0);
    CheckLookup(&o, "refs 0 and still loading", 0x0106, 0, 0, 0);
    CheckLookup(&o, "50k id 0x68f4 swapped halves", 0x68f40000, 0, 1, kKindId);
    CheckLookup(&o, "record type 0x80", 0x0102, 0, 1, kKindEntry);
    CheckLookup(&o, "record loading flag 2", 0x0105, 0, 1, kKindEntry);
    CheckExists(&o, "good record", 0x688c, 1, 0);
    CheckExists(&o, "empty entry", 0x0001, 0, 0);
    CheckExists(&o, "50f state-chart parameter", 0x04900000, 0, 1);
    CheckExists(&o, "entry 0x2104 (not a pointer)", 0x0103, 0, 1);
    // a caller that does not test for 0: the original lookup runs (the test record with type 0x80 is readable here)
    g_testUnguarded = true;
    CheckLookup(&o, "unguarded caller, type 0x80 -> original", 0x0102, reinterpret_cast<DWORD>(badtype) + 0x10, 1,
                kKindEntry);
    CheckLookup(&o, "unguarded caller, refs 0 -> no hit", 0x0101, reinterpret_cast<DWORD>(norefs) + 0x10, 0, 0);
    CheckExists(&o, "unguarded caller, misaligned -> original", 0x0104, 1, 1);
    // 0.2.2: an id outside the table never runs the original (it would read beyond the table; crash 2026-11-13)
    CheckLookup(&o, "unguarded caller, 1311 spider id 0x24910000", 0x24910000, 0, 1, kKindId);
    CheckLookup(&o, "unguarded caller, first id past the table", 0x8000, 0, 1, kKindId);
    CheckLookup(&o, "unguarded caller, none id -1 (no hit)", 0xffffffff, 0, 0, 0);
    CheckExists(&o, "unguarded caller, id 0x8000 -> missing", 0x8000, 0, 1);
    g_testUnguarded = false;
    g_testMode = false;
    // the static caller list: the four crash callers of 2026-11-02 (50d / 50e / 50h test for 0, 50f does not)
    for (int i = 0; i < kGuardedCount; ++i) g_guardedOk[i] = true;   // in the game: byte-checked at load
    Report(&o, IsGuarded(0x00535ec5), "caller list: 50d tru+0x135ec5 tests for 0");
    Report(&o, IsGuarded(0x005920f4), "caller list: 50e tru+0x1920f4 tests for 0");
    Report(&o, IsGuarded(0x005953f2), "caller list: 50h tru+0x1953f2 tests for 0");
    Report(&o, IsGuarded(0x00594cad), "caller list: 50k tru+0x194cad tests for 0");
    Report(&o, !IsGuarded(0x0058bd3a), "caller list: unload callback tru+0x18bd3a does not test for 0 (tail jmp)");
    Report(&o, !IsGuarded(0x0075eefe), "caller list: 50f tru+0x35eefe does not test for 0 (tail jmp to tru+0x1ee890)");
    Report(&o, !IsGuarded(0x0059500f), "caller list: 1311 tru+0x19500f does not test for 0 (ids outside -> 0, 0.2.2)");
    bool sorted = true;
    for (int i = 1; i < kGuardedCount; ++i) if (kGuardedCallers[i] <= kGuardedCallers[i - 1]) sorted = false;
    Report(&o, sorted, "caller list sorted, %d entries", kGuardedCount);
    for (int i = 0; i < kGuardedCount; ++i) g_guardedOk[i] = false;

    g_table = savedTable;
    g_count = savedCount;
    g_logLevel = savedLevel;
    _snprintf_s(report + o.used, size - o.used, _TRUNCATE, "%d passed, %d failed\n", o.passed, o.failed);
    return o.failed;
}

// exported so the loader / tools can identify the plugin
extern "C" __declspec(dllexport) const char *TruDataGuardVersion() { return "TruDataGuard 0.2.2 (section lookup / exists test: invalid ids -> not found; 0.2.1: dated log lines; 0.2.2: ids outside the table -> not found for every caller)"; }
