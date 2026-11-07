// TruShadowHud.asi - DLC 2 "Lara's Shadow": the shadow meter HUD natives of the Xbox title update (TU) for the PC
// tru.exe (Steam, image base 0x400000). Workspace docs: Plan-Nacht-Analysen-2026-11-03.md section 2,
// Befund-Schattenleiste-HUD.md; plugin README.
//
// The TU HUD script (Xbox generalbank script 38 = PC script 37) function 15 colours the shadow meter with uimeter f25
// from four natives the PC exe does not have:
//   larabase f71 0x824aa0a0  bool  meter flag 8 and value > tuning +0x70 x 0.01 x tuning +0x10 (75 % of 1000)
//   larabase f72 0x824aa120  bool  CanStart(meter) 0x823d8120 (side effect: clears flag 0x200 above tuning +0x28)
//   larabase f73 0x824aa150  float max(meter +0x10, 0.0) - the refill delay left
//   dlc2data f0  0x824a1188  bool  gameTracker+0x1244 (DoppelgangerInit finished)
// and the TU added larabase f70 0x824aa060 (meter +0x10 = tuning +0x24; no TU caller) with them. On the TU the
// larabase type binder (vtable 0x820796c8 slot 3 = 0x824a7d28) binds 74 natives; the PC binder tru+0x3b5490 (vtable
// 0x862a38 slot 3) binds 70 (0..0x45) through tru+0x1768f0(index, function) = funcs[index].native. `dlc2data` is a
// native type only the TU registers (0x824d4f58: ctor fields +0x10 = 1, +0x14 = +0x18 = 4, vtable 0x8207a0ac, binder
// 0x824a1140 = f0 0x824a1188, f1 0x824a11a0); the PC registers no such type, so script 21239's natives stay null.
//
// This plugin translates both:
//   * larabase: vtable 0x862a38 slot 3 -> LaraBinderHook = the PC binder, then funcs[70..73] = f70..f73 through the
//     same tru+0x1768f0 - only when the bound script is the TU type script (74 function entries, 70..73 native and
//     still unbound); the 70-entry PC script is left as the PC binder made it.
//   * dlc2data: the larabase registration's `call tru+0x17ed00` (tru+0x3a946f) -> RegisterHook = the original
//     registration, then a dlc2data type as the TU builds it: engine allocator ([0xcd9cac]+0x48)->vtbl[0x34](0x24, 0),
//     ctor tru+0x174b60("game/script/game/game", "dlc2data", 4, 4, 0) (the PC twin of the TU field stores; the PC
//     `globaleffect` type is registered with exactly these arguments), vtable = copy of the PC `globaleffect` type
//     vtable 0x86279c (its TU twin 0x8207a148 equals the TU dlc2data vtable in all 13 slots but the binder) with slot 3
//     = Dlc2BinderHook: base bind tru+0x174bc0, then funcs[0] = f0 and (0.2) funcs[1] = f1.
//   * 0.2 (2026-11-07, P5d): dlc2data f1 0x824a11a0 = `byte 0x829ca67c = (s8)args[0] != 0`. Its only caller is the TU
//     hint-box script 10 (f8: 1 when the modal DLC 2 box opens; f7 on "paused" and f9: 0 - tu_native_coverage.py,
//     script_dis.py xt 10); its only reader (ppc_hilo_refs.py: 1 load, 1 store) is TU 0x8248cea8 = the Xbox system
//     notification listener (retail 0x824873d8): on XN_SYS_UI (9, the Guide opens) in main state "playgame" and not
//     quitting it pauses the game (TU 0x8229a118 = retail 0x8229d6d0 = PC tru+0x1d4780) when gameTrackerX+0xbb != 6
//     and !(+0x2c & 0x80) - the retail rule - and, new in the TU, also in those two states when the byte is set. The
//     PC has no Guide and no twin of that listener (the PC callers of tru+0x1d4780, tru+0x1d4891 / +0x1d4981 /
//     +0x38bb1e, never test +0x2c & 0x80), so the byte has no PC reader; f1 is bound 1:1 as the TU's store into the
//     plugin's byte (export TruShadowHudDlc2F1)
//     so that the TU script can call it. PC script 9 (the port of script 10) still has its calls replaced by
//     tools/script_dlc2_flag_stub.py. [ShadowHud] TranslateDlc2F1 (default 1 = TU; 0 = f1 left unbound as 0.1).
//   * the natives' bodies are TruShadowPower's translation (TruShadowPowerMeterApi version 2: delayStart / strikeReady
//     / canStart / delayLeft = f70..f73, the plugin owns the meter); dlc2data f0 = TruDlc2PlayerDoppelganger(). Both
//     are looked up at the first call (GetProcAddress); when absent the natives answer as the TU does without the
//     tuning object (f71 0, f72 0, f73 0.0, f70 nothing) and dlc2data f0 0 - logged once.
// PC native convention (read from the 70 PC larabase natives, e.g. tru+0x399eb0 / 0x399f20 / 0x39a6c0): cdecl
// (instance, ?, args, result) - [esp+0xc] the argument block, [esp+0x10] the result (bool: byte, float: dword); the TU
// natives get the same as r3..r6 (r5 args, r6 result).
// Not translated: the TU binder also caches the entry addresses 70..73 next to 0..69 (r30 +0x118..+0x124); the PC
// cache (0x105baa8..) has no slots for them and no PC code could read them.
// Every engine address is byte-checked first; on a mismatch that part is left alone and the reason is logged.
// Options: TruShadowHud.ini, log TruShadowHud.log.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>

namespace {

const char kVersion[] = "TruShadowHud 0.2";
const DWORD kImageBase = 0x00400000;

// ---- larabase binder (TU 0x824a7d28 / PC tru+0x3b5490) ----
const DWORD kLaraVtbl = 0x00862a38;        // NsLaraBase_ScriptType vtable (TU 0x820796c8)
const DWORD kLaraVtblSlot3 = kLaraVtbl + 0xc;
const DWORD kLaraBinder = 0x007b5490;      // push esi/edi; edi = script; base bind; bind(0, 0x7ac6f0); ...
const char *const kLaraBinderHex = "56 57 8b7c240c 57 8bf1 e822f7dbff 68f0c67a00 6a00 8bce e84414dcff";
const DWORD kLaraBinderLast = 0x007b5856;  // the last two binds: f68 0x79a6b0 (0x44), f69 0x79a6c0 (0x45), then caches
const char *const kLaraBinderLastHex = "68b0a67900 6a44 8bce e88c10dcff 68c0a67900 6a45 8bce e87e10dcff 8b4708";
const DWORD kBind = 0x005768f0;            // thiscall(type; index, fn): [[type+0x1c]+8]+0x38 [index * 0x1c + 0x14] = fn
const char *const kBindHex = "8b411c 8b4808 8b442404 8d14c500000000 2bd0 8b4138 8b4c2408 894c9014 c20800";
const DWORD kBaseBind = 0x00574bc0;        // thiscall(type; script): type+0x1c = script, +0x20 = 1, script+0xc = type
const char *const kBaseBindHex = "8b442404 89411c c6412001 89480c b001 c20400";
const int kPcLaraCount = 70, kTuLaraCount = 74;

// ---- type registration (TU 0x824d4f58 / PC tru+0x3a8650, registry [0xcc4f5c]) ----
const DWORD kLaraRegister = 0x007a9451;    // push "larabase"; push package; ctor 0x574b20; vtable; push edi; call register
const char *const kLaraRegisterHex = "686c2a8600 6814218600 8bcf e8beb6dcff c707382a8600 eb02 33ff 57 8bce e88c58ddff";
const DWORD kLaraRegisterCall = 0x007a946f;
const DWORD kRegister = 0x0057ed00;        // thiscall(registry; type)
const char *const kRegisterHex = "56 8b742408 8b4608 57 8bf9 50 8d4c2410 e87b3df2ff";
const DWORD kTypeCtor = 0x00574b60;        // thiscall(type; package, name, +0x14, +0x18, byte +0x11), ret 0x14
const char *const kTypeCtorHex = "8b542404 8bc1 53 8a5c2418 56 8b742414 33c9 66894804";
const DWORD kEffectRegister = 0x007a91b9;  // globaleffect: push 0; push 4; push 4; name; package; ctor; vtable 0x86279c
const char *const kEffectRegisterHex = "6a00 6a04 6a04 68d0278600 6814218600 8bcf e890b9dcff c7079c278600";
const DWORD kEffectVtbl = 0x0086279c;      // TU twin 0x8207a148 = TU dlc2data 0x8207a0ac except slot 3
const DWORD kEffectSlots[13] = {0x007ad960, 0x00597810, 0x0079c670, 0x007ac300, 0x007a2f00, 0x0079d8e0, 0x007987b0,
                                0x0079d8e0, 0x007987b0, 0x00574be0, 0x005f6420, 0x0079d8e0, 0x007a2f00};
const DWORD kPackage = 0x00862114;         // "game/script/game/game"
const char kPackageName[] = "game/script/game/game";
const DWORD kAllocatorPtr = 0x00cd9cac;    // [[0xcd9cac]+0x48]->vtbl[0x34](size, 0) (as every registration)
const char kDlc2Name[] = "dlc2data";

// options (TruShadowHud.ini, section [ShadowHud])
int g_enabled = 1, g_logLevel = 1, g_laraNatives = 1, g_dlc2Data = 1, g_meterApi = 1;
int g_dlc2F1 = 1;                          // 0.2 [ShadowHud] TranslateDlc2F1: bind dlc2data f1 (TU 0x824a11a0)
volatile char g_dlc2F1Byte = 0;            // 0.2: the TU's byte 0x829ca67c (no PC reader; export TruShadowHudDlc2F1)

char g_logPath[MAX_PATH];
CRITICAL_SECTION g_logLock;
DWORD g_laraBinder = kLaraBinder, g_baseBind = kBaseBind, g_register = kRegister;
bool g_laraOk = false, g_dlc2Ok = false;
DWORD g_dlc2Vtbl[13];
volatile LONG g_laraBinds = 0, g_dlc2Binds = 0;

void Log(int level, const char *fmt, ...) {
    if (level > g_logLevel || !g_logPath[0]) return;
    char line[700];
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

bool ReadDword(DWORD address, DWORD *value) {
    __try {
        *value = *reinterpret_cast<const DWORD *>(address);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool WriteCode(DWORD address, const void *bytes, size_t length) {
    DWORD old = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(address), length, PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "VirtualProtect failed (%lu) at 0x%08lx", GetLastError(), address);
        return false;
    }
    memcpy(reinterpret_cast<void *>(address), bytes, length);
    DWORD dummy = 0;
    VirtualProtect(reinterpret_cast<void *>(address), length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(address), length);
    return true;
}

// ---------------------------------------------------------------------------------------------------------------
// the bodies: TruShadowPower's meter (TU gameTracker+0x508) and TruDlc2Player's flag (TU gameTracker+0x1244)
struct TruShadowPowerMeter {
    DWORD size;                           // sizeof the exporter's struct
    DWORD version;                        // >= 2 (TruShadowPower 0.11: 2, 0.12: 3 = v2 + gt1280 appended; only the v2 part is used)
    volatile DWORD *flags;                // TU meter +0x04
    float *value;                         // +0x08
    float *startValue;                    // +0x0c
    float (*request)[2];                  // +0x40
    void(__cdecl *selector)();            // 0x823d7520
    void(__cdecl *drain)(float amount);   // 0x823d8380
    // version 2 (TruShadowPower 0.11)
    float *delay;                         // +0x10
    void(__cdecl *delayStart)();          // f70 0x824aa060
    char(__cdecl *strikeReady)();         // f71 0x824aa0a0
    char(__cdecl *canStart)();            // f72 0x824aa120
    float(__cdecl *delayLeft)();          // f73 0x824aa150
};
const DWORD kMeterV2Size = 13 * 4;
typedef const TruShadowPowerMeter *(__cdecl *MeterApiFn)();
typedef int(__cdecl *DoppelgangerFn)();

const TruShadowPowerMeter *g_meter = nullptr;
bool g_meterLooked = false;
DoppelgangerFn g_dgFn = nullptr;
bool g_dgLooked = false;

const TruShadowPowerMeter *Meter() {
    if (g_meterLooked) return g_meter;
    g_meterLooked = true;                  // first native call: every .asi is loaded by then
    if (!g_meterApi) {
        Log(1, "meter interface off ([ShadowHud] MeterApi=0) - f70-f73 answer as the TU without the tuning object");
        return nullptr;
    }
    HMODULE m = GetModuleHandleA("TruShadowPower.asi");
    MeterApiFn fn = m ? reinterpret_cast<MeterApiFn>(GetProcAddress(m, "TruShadowPowerMeterApi")) : nullptr;
    const TruShadowPowerMeter *api = fn ? fn() : nullptr;
    if (api && api->version >= 2 && api->size >= kMeterV2Size && api->delayStart && api->strikeReady &&
        api->canStart && api->delayLeft) {
        g_meter = api;
        Log(1, "TruShadowPower meter interface found (version %lu, size %lu) - f70-f73 = its delayStart / strikeReady "
               "/ canStart / delayLeft", api->version, api->size);
    } else if (api) {
        Log(0, "TruShadowPowerMeterApi: version %lu, size %lu (need version >= 2, size >= %lu) - not used; f70-f73 answer "
               "as the TU without the tuning object (f71 0, f72 0, f73 0.0)", api->version, api->size, kMeterV2Size);
    } else {
        Log(0, "no meter interface (%s) - f70-f73 answer as the TU without the tuning object (f71 0, f72 0 = red "
               "meter, f73 0.0); install TruShadowPower 0.11 or later", m ? "TruShadowPower.asi exports no "
                                                                        "TruShadowPowerMeterApi" : "TruShadowPower.asi "
                                                                                                   "not loaded");
    }
    return g_meter;
}

int Doppelganger() {
    if (!g_dgLooked) {
        g_dgLooked = true;
        HMODULE m = GetModuleHandleA("TruDlc2Player.asi");
        if (m) g_dgFn = reinterpret_cast<DoppelgangerFn>(GetProcAddress(m, "TruDlc2PlayerDoppelganger"));
        if (g_dgFn) Log(1, "dlc2data f0: TruDlc2Player.asi TruDlc2PlayerDoppelganger found (TU gameTracker+0x1244)");
        else Log(0, "dlc2data f0: TruDlc2Player.asi / TruDlc2PlayerDoppelganger not found - f0 answers 0 (as the TU "
                    "before DoppelgangerInit)");
    }
    return g_dgFn ? g_dgFn() : 0;
}

// first call / result changes per native (LogLevel 1: first call, 2: every change of the result)
struct Watch {
    const char *name;
    LONG calls;
    int last;
};
Watch g_watch[6] = {{"larabase f70 (TU 0x824aa060)", 0, -1}, {"larabase f71 (TU 0x824aa0a0)", 0, -1},
                    {"larabase f72 (TU 0x824aa120)", 0, -1}, {"larabase f73 (TU 0x824aa150)", 0, -1},
                    {"dlc2data f0 (TU 0x824a1188)", 0, -1}, {"dlc2data f1 (TU 0x824a11a0)", 0, -1}};

void Seen(int k, int value, const char *shown) {
    Watch &w = g_watch[k];
    LONG n = ++w.calls;
    if (n == 1) Log(1, "%s first call -> %s", w.name, shown);
    else if (value != w.last) Log(2, "%s call %ld -> %s", w.name, n, shown);
    w.last = value;
}

// PC native convention: cdecl (instance, ?, args, result)
void __cdecl NativeF70(void *, void *, void *, void *) {           // meter +0x10 = tuning +0x24
    const TruShadowPowerMeter *m = Meter();
    if (m) m->delayStart();
    Seen(0, 0, "(no result)");
}

void __cdecl NativeF71(void *, void *, void *, void *result) {      // bool: strike ready (flag 8, > 75 %)
    const TruShadowPowerMeter *m = Meter();
    char r = m ? m->strikeReady() : 0;     // TU: 0 without game tracker / tuning
    if (result) *static_cast<char *>(result) = r;
    Seen(1, r ? 1 : 0, r ? "1 (strike ready)" : "0");
}

void __cdecl NativeF72(void *, void *, void *, void *result) {      // bool: CanStart(meter) 0x823d8120
    const TruShadowPowerMeter *m = Meter();
    char r = m ? m->canStart() : 0;        // TU 0x823d8120: 0 without game tracker / tuning
    if (result) *static_cast<char *>(result) = r;
    Seen(2, r ? 1 : 0, r ? "1 (can start)" : "0 (cannot start: meter red)");
}

void __cdecl NativeF73(void *, void *, void *, void *result) {      // float: max(meter +0x10, 0.0)
    const TruShadowPowerMeter *m = Meter();
    float r = m ? m->delayLeft() : 0.0f;
    if (result) *static_cast<float *>(result) = r;
    char shown[48];
    _snprintf_s(shown, sizeof(shown), _TRUNCATE, "%.2f (refill delay left)", r);
    Seen(3, r > 0.0f ? 1 : 0, shown);
}

void __cdecl NativeDlc2F0(void *, void *, void *, void *result) {   // bool: gameTracker+0x1244
    char r = Doppelganger() ? 1 : 0;
    if (result) *static_cast<char *>(result) = r;
    Seen(4, r, r ? "1 (doppelganger player)" : "0");
}

// 0.2: TU 0x824a11a0: lbz r11, 0(r5); extsb; cntlzw; >> 5; xori 1 -> stb 0x829ca67c (= the bool argument != 0). PC
// natives read a bool argument the same way (tru+0x399f70: mov eax, [esp+0xc]; cmp byte [eax], 0; setne cl).
void __cdecl NativeDlc2F1(void *, void *, void *args, void *) {
    char v = 0;
    __try {
        v = args && *static_cast<const signed char *>(args) != 0 ? 1 : 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        v = 0;
    }
    g_dlc2F1Byte = v;
    Seen(5, v, v ? "1 (TU byte 0x829ca67c set: modal DLC 2 hint box open)" : "0 (TU byte 0x829ca67c cleared)");
}

// ---------------------------------------------------------------------------------------------------------------
// binding (tru+0x1768f0) and the function table of the bound script
void Bind(void *typeObj, int index, const void *fn) {
    DWORD bind = kBind;
    __asm {
        mov ecx, typeObj
        push fn
        push index
        mov eax, bind
        call eax
    }
}

// [[type+0x1c]+8]+0x38 = the script's function table (entries of 0x1c: +0x14 native, +0x18 code), count at -4
bool Functions(void *type, DWORD *table, DWORD *count) {
    DWORD script = 0, root = 0;
    return ReadDword(reinterpret_cast<DWORD>(type) + 0x1c, &script) && script && ReadDword(script + 8, &root) &&
           root && ReadDword(root + 0x38, table) && *table && ReadDword(*table - 4, count);
}

// an entry that is a native (no code) and not yet bound
bool FreeNative(DWORD table, int index) {
    DWORD native = 1, code = 1;
    return ReadDword(table + index * 0x1c + 0x14, &native) && ReadDword(table + index * 0x1c + 0x18, &code) &&
           native == 0 && code == 0;
}

extern "C" void __cdecl LaraBound(void *type) {
    LONG n = InterlockedIncrement(&g_laraBinds);
    DWORD table = 0, count = 0;
    if (!Functions(type, &table, &count)) {
        Log(0, "larabase bind %ld: function table not readable (type 0x%08lx) - f70-f73 not bound", n,
            reinterpret_cast<DWORD>(type));
        return;
    }
    if (count == kPcLaraCount) {
        Log(1, "larabase bind %ld: the script has %lu functions (the PC larabase type script) - f70-f73 not bound; the "
               "TU HUD script needs the generalbank with the 74-entry TU larabase script", n, count);
        return;
    }
    if (count != kTuLaraCount) {
        Log(0, "larabase bind %ld: the script has %lu functions (expected %d or %d) - f70-f73 not bound", n, count,
            kPcLaraCount, kTuLaraCount);
        return;
    }
    for (int k = kPcLaraCount; k < kTuLaraCount; ++k) {
        if (!FreeNative(table, k)) {
            Log(0, "larabase bind %ld: entry %d is not a free native - f70-f73 not bound", n, k);
            return;
        }
    }
    const void *fns[4] = {&NativeF70, &NativeF71, &NativeF72, &NativeF73};
    for (int k = 0; k < 4; ++k) Bind(type, kPcLaraCount + k, fns[k]);
    Log(1, "larabase bind %ld: %lu functions (TU type script) - f70-f73 bound (TU 0x824aa060 / 0x824aa0a0 / 0x824aa120 / "
           "0x824aa150; function table 0x%08lx)", n, count, table);
}

// vtable slot 3 of the larabase type: thiscall(type; script), ret 4, al = result of the PC binder
__declspec(naked) void LaraBinderHook() {
    __asm {
        push esi
        mov esi, ecx
        push dword ptr [esp + 8]
        call dword ptr [g_laraBinder]
        push eax
        push esi
        call LaraBound
        add esp, 4
        pop eax
        pop esi
        ret 4
    }
}

extern "C" void __cdecl Dlc2Bound(void *type) {
    LONG n = InterlockedIncrement(&g_dlc2Binds);
    DWORD table = 0, count = 0;
    if (!Functions(type, &table, &count)) {
        Log(0, "dlc2data bind %ld: function table not readable - f0 not bound", n);
        return;
    }
    if (count < 1 || !FreeNative(table, 0)) {
        Log(0, "dlc2data bind %ld: %lu functions, entry 0 not a free native - f0 not bound", n, count);
        return;
    }
    Bind(type, 0, &NativeDlc2F0);
    if (!g_dlc2F1) {
        Log(1, "dlc2data bind %ld: %lu functions - f0 bound (TU 0x824a1188), f1 left unbound ([ShadowHud] "
               "TranslateDlc2F1=0)", n, count);
        return;
    }
    if (count < 2 || !FreeNative(table, 1)) {
        Log(0, "dlc2data bind %ld: %lu functions - f0 bound (TU 0x824a1188); entry 1 missing or not a free native - f1 "
               "not bound", n, count);
        return;
    }
    Bind(type, 1, &NativeDlc2F1);
    Log(1, "dlc2data bind %ld: %lu functions - f0 bound (TU 0x824a1188), f1 bound (TU 0x824a11a0: byte 0x829ca67c = "
           "arg != 0; its TU reader 0x8248cea8, the Guide pause, has no PC twin)", n, count);
}

// slot 3 of the dlc2data type (TU 0x824a1140): base bind, natives, return byte +0x20 (TU: lbz r3, 0x20(r3))
__declspec(naked) void Dlc2BinderHook() {
    __asm {
        push esi
        mov esi, ecx
        push dword ptr [esp + 8]
        call dword ptr [g_baseBind]
        push esi
        call Dlc2Bound
        add esp, 4
        mov al, byte ptr [esi + 0x20]
        pop esi
        ret 4
    }
}

// ---------------------------------------------------------------------------------------------------------------
// registration of the dlc2data type right after larabase (the TU registers both in 0x824d4f58)
void *EngineAlloc(DWORD bytes) {
    DWORD holder = 0, allocator = 0;
    if (!ReadDword(kAllocatorPtr, &holder) || !holder || !ReadDword(holder + 0x48, &allocator) || !allocator) return nullptr;
    void *p = nullptr;
    __asm {
        mov ecx, allocator
        mov edx, [ecx]
        mov eax, [edx + 0x34]
        push 0
        push bytes
        call eax
        mov p, eax
    }
    return p;
}

void ConstructType(void *typeObj) {
    DWORD ctor = kTypeCtor;
    const char *name = kDlc2Name;
    DWORD package = kPackage;
    __asm {
        mov ecx, typeObj
        push 0                     // byte +0x11
        push 4                     // +0x18
        push 4                     // +0x14
        push name                  // +0x0c
        push package               // +0x08
        mov eax, ctor
        call eax
    }
}

void RegisterType(void *registry, void *typeObj) {
    DWORD reg = kRegister;
    __asm {
        mov ecx, registry
        push typeObj
        mov eax, reg
        call eax
    }
}

extern "C" void __cdecl LaraRegistered(void *registry) {
    void *type = EngineAlloc(0x24);
    if (!type) {
        Log(0, "dlc2data: engine allocation of the type object failed - not registered");
        return;
    }
    ConstructType(type);
    *reinterpret_cast<DWORD *>(type) = reinterpret_cast<DWORD>(g_dlc2Vtbl);
    RegisterType(registry, type);
    Log(1, "dlc2data: native type registered after larabase (type 0x%08lx, registry 0x%08lx, vtable = globaleffect "
           "0x%08lx with slot 3 = binder of f0)", reinterpret_cast<DWORD>(type), reinterpret_cast<DWORD>(registry),
        kEffectVtbl);
}

// replaces `call tru+0x17ed00` of the larabase registration: thiscall(registry; type), ret 4
__declspec(naked) void RegisterHook() {
    __asm {
        push ecx
        push dword ptr [esp + 8]
        call dword ptr [g_register]
        pop ecx
        push eax
        push ecx
        call LaraRegistered
        add esp, 4
        pop eax
        ret 4
    }
}

// ---------------------------------------------------------------------------------------------------------------
bool PatchLarabase() {
    DWORD slot = 0;
    if (!ReadDword(kLaraVtblSlot3, &slot) || slot != kLaraBinder) {
        Log(0, "larabase: vtable 0x%08lx slot 3 is 0x%08lx, expected 0x%08lx - not hooked", kLaraVtbl, slot, kLaraBinder);
        return false;
    }
    if (!HexBytesAt(kLaraBinder, kLaraBinderHex) || !HexBytesAt(kLaraBinderLast, kLaraBinderLastHex) ||
        !HexBytesAt(kBind, kBindHex)) {
        Log(0, "larabase: binder 0x%08lx / 0x%08lx or bind 0x%08lx does not match - not hooked", kLaraBinder,
            kLaraBinderLast, kBind);
        return false;
    }
    DWORD hook = reinterpret_cast<DWORD>(&LaraBinderHook);
    if (!WriteCode(kLaraVtblSlot3, &hook, 4)) return false;
    Log(1, "larabase: vtable 0x%08lx slot 3 -> hook (PC binder 0x%08lx binds 0..69, the hook 70..73 when the script has "
           "74 entries)", kLaraVtbl, kLaraBinder);
    return true;
}

bool PatchDlc2Data() {
    if (!HexBytesAt(kLaraRegister, kLaraRegisterHex) || !HexBytesAt(kRegister, kRegisterHex) ||
        !HexBytesAt(kTypeCtor, kTypeCtorHex) || !HexBytesAt(kEffectRegister, kEffectRegisterHex) ||
        !HexBytesAt(kBaseBind, kBaseBindHex) || !HexBytesAt(kBind, kBindHex) ||
        !BytesAt(kPackage, reinterpret_cast<const BYTE *>(kPackageName), sizeof(kPackageName))) {
        Log(0, "dlc2data: registration code 0x%08lx / 0x%08lx / ctor 0x%08lx / globaleffect 0x%08lx / bind does not "
               "match - not registered (dlc2data f0 stays a null native)", kLaraRegister, kRegister, kTypeCtor,
            kEffectRegister);
        return false;
    }
    for (int k = 0; k < 13; ++k) {
        DWORD v = 0;
        if (!ReadDword(kEffectVtbl + 4 * k, &v) || v != kEffectSlots[k]) {
            Log(0, "dlc2data: globaleffect vtable 0x%08lx slot %d is 0x%08lx, expected 0x%08lx - not registered",
                kEffectVtbl, k, v, kEffectSlots[k]);
            return false;
        }
        g_dlc2Vtbl[k] = v;
    }
    g_dlc2Vtbl[3] = reinterpret_cast<DWORD>(&Dlc2BinderHook);
    BYTE call[5] = {0xe8, 0, 0, 0, 0};
    DWORD rel = reinterpret_cast<DWORD>(&RegisterHook) - (kLaraRegisterCall + 5);
    memcpy(call + 1, &rel, 4);
    if (!WriteCode(kLaraRegisterCall, call, sizeof(call))) return false;
    Log(1, "dlc2data: registration hooked at 0x%08lx (after larabase; type as the TU's: \"%s\", fields 4 / 4 / 0)",
        kLaraRegisterCall, kDlc2Name);
    return true;
}

void ReadOptions(const char *dir) {
    char ini[MAX_PATH];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruShadowHud.ini", dir);
    g_enabled = GetPrivateProfileIntA("ShadowHud", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("ShadowHud", "LogLevel", 1, ini);
    g_laraNatives = GetPrivateProfileIntA("ShadowHud", "LaraNatives", 1, ini);
    g_dlc2Data = GetPrivateProfileIntA("ShadowHud", "Dlc2Data", 1, ini);
    g_meterApi = GetPrivateProfileIntA("ShadowHud", "MeterApi", 1, ini);
    g_dlc2F1 = GetPrivateProfileIntA("ShadowHud", "TranslateDlc2F1", 1, ini);    // 0.2, default 1 = TU
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruShadowHud.log", dir);
    ReadOptions(dir);
    Log(1, "%s loaded (enabled %d, log level %d, larabase natives %d, dlc2data %d, meter interface %d; 0.2: dlc2data "
        "f1 %d)", kVersion, g_enabled, g_logLevel, g_laraNatives, g_dlc2Data, g_meterApi, g_dlc2F1);
    if (!g_enabled) { Log(1, "disabled by TruShadowHud.ini - nothing patched"); return; }
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - not patched", base, kImageBase); return; }
    if (g_laraNatives) g_laraOk = PatchLarabase();
    else Log(1, "larabase: off ([ShadowHud] LaraNatives=0) - f70-f73 stay null (the TU HUD script would crash on them)");
    if (g_dlc2Data) g_dlc2Ok = PatchDlc2Data();
    else Log(1, "dlc2data: off ([ShadowHud] Dlc2Data=0) - f0 stays null (the TU HUD script would crash on it)");
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

extern "C" __declspec(dllexport) const char *TruShadowHudVersion() {
    return "TruShadowHud 0.2 (TU larabase natives f70-f73 and dlc2data f0 for the TU HUD script, bodies from "
           "TruShadowPowerMeterApi v2 / TruDlc2PlayerDoppelganger; dlc2data f1 = the TU's hint-box byte 0x829ca67c)";
}

// 0.2: the value dlc2data f1 last stored (TU byte 0x829ca67c: 1 while the TU hint-box script's modal DLC 2 box is
// open). The PC has no reader of it (the TU reader is the Xbox Guide listener 0x8248cea8); for diagnostics / TruMenu.
extern "C" __declspec(dllexport) int __cdecl TruShadowHudDlc2F1() {
    return g_dlc2F1Byte ? 1 : 0;
}
