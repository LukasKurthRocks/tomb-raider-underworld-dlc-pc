// TruShadowCombat.asi - DLC 2 "Lara's Shadow" combat (target list, target conditions, shadow-strike gate) for the PC
// tru.exe (Steam, image base 0x400000). Translation of the Xbox title update (TU), docs/Befund-Schattenkampf.md.
//
// 1. Target list: the TU grew the player's targeter array from 7 to 10 entries (retail -> TU: `li/cmpwi 7` -> 0xa at
//    every loop over it, candidate mask 0x71 -> 0x3f1, array 0x1c -> 0x28 bytes) and gave the targeters their
//    parameters through the new helper 0x82402208: index 0..5 as retail, 6 -> the parameters of 2 (+0x468), 7 -> the
//    old 6 (+0x478), 8 / 9 -> none, and for every index an override from the DLC 2 player tuning (object 858, table
//    tuning +0x90 / +0x94 count: entries for 8 and 9). The PC still has the retail list ([0xfadfac], 7 entries). The
//    plugin patches the same constants at the PC sites (tools/tu_imm_change_sites.py, PC loops tru+0x31dc78 ctor,
//    tru+0x316946 / +0x3169d0 instance add + masks tru+0x316915 / +0x3169a2, tru+0x31aca9, tru+0x31dcce, destroy
//    tru+0x316843, per-frame update tru+0x3228a3, alloc tru+0x322631) and replaces the PC parameter function
//    tru+0x2ecc10 (= retail 0x823ff7d8, the TU's 0x82402208) with the TU logic. PC slots 0..6 keep their retail
//    meaning (PC code passes those indices); the TU-only targeters live in the new slots: slot 7 = TU 6, 8 = TU 8,
//    9 = TU 9 (TU 7 = the old 6 = PC slot 6). Every TU index below is mapped through SlotOf().
// 2. Lara's conditions (both state machines, as the TU tables): 2005 / 2006 / 2013 (TU-only predicates 0x8246e8e0 /
//    0x8246eb08 / 0x8246ea30), 2011 (TU 0x8246f140: doppelganger branch with targeter 9) and 538 (TU 0x8246faa8:
//    doppelganger -> meter flag 8). Outside doppelganger mode the PC predicates (retail) answer.
// 3. State 1014 (shadow strike, TU slots 0 / 2 / 3 -> 0x823d8978 / 0x823d9210 / 0x823d8d18 in doppelganger mode): not
//    translated yet (needs the meter object owned by TruShadowPower, see MeterApi). In doppelganger mode the PC's
//    retail strike (tru+0x31d3c0 / +0x318fd0 / +0x318d00, player fields) is NOT run ([Strike] Gate=1) - logged.
// 4. 0.5: states 1019 / 1020 (TU 0x8245f420 / 0x8245f540 / 0x8245f398 + 0x8245f2a8 / 0x82463c18 / 0x82463eb8, VMX128
//    bodies decoded), registered log-only; [States] Translate1019 / Translate1020 = 1 makes them act.
// 5. 0.5.1: TU table differences of states 231 (slots 0 / 1 = 0x82464160, the move helper with the doppelganger branch)
//    and 1004 (slots 0 / 1 = 0x8245efc8, hit list kept with parameter 0x415); PC handlers unless [States]
//    Translate231Slot0 / Translate231Slot1 / Translate1004 = 1.
//
// Every engine address is byte-checked before use; a failed check switches the affected part off with a logged
// reason. Options: TruShadowCombat.ini next to the .asi (README.md).

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <math.h>

namespace {

const char kVersion[] = "TruShadowCombat 0.5.1 (TU target list 7 -> 10, conditions 2005 / 2006 / 2011 / 2013 / 538, "
                        "states 1017 / 244 / 1007, shadow strike 1014 (Translate, TruShadowPowerMeterApi v1-v3), "
                        "finisher 1013 probe + doppelganger translation (Translate1013); 0.4.1: both switches read "
                        "again at run time; 0.5: states 1019 / 1020 (Translate1019 / Translate1020, log only by default); 0.5.1: states 231 / 1004 slots 0 / 1 "
                        "(Translate231Slot0 / Translate231Slot1 / Translate1004, PC handler by default), strike look off "
                        "0x823d9050 through TruShadowPowerMeterApi v4)";
const DWORD kImageBase = 0x00400000;

// ---------------------------------------------------------------- options / log
int g_enabled = 1;
int g_logLevel = 1;          // 0 errors, 1 info, 2 + every result change, 3 + every call (rate-limited)
int g_targetList = 1;        // [TargetList] Enabled
int g_conditions = 1;        // [Conditions] Enabled
int g_strikeGate = 1;        // [Strike] Gate
int g_statesOn = 1;          // 0.2 [States] Enabled: TU states 1017 / 244 / 1007 (slots 4 / 5)

char g_logPath[MAX_PATH];
char g_iniPath[MAX_PATH];    // 0.4.1: read again at run time (ReadSwitches)
CRITICAL_SECTION g_logLock;

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

// hex string, spaces ignored
size_t ParseHex(const char *hex, BYTE *out, size_t size) {
    size_t n = 0;
    for (const char *p = hex; *p && p[1] && n < size;) {
        if (*p == ' ') { ++p; continue; }
        char two[3] = {p[0], p[1], 0};
        out[n++] = static_cast<BYTE>(strtoul(two, nullptr, 16));
        p += 2;
    }
    return n;
}

bool HexAt(DWORD address, const char *hex) {
    BYTE buf[256];
    size_t n = ParseHex(hex, buf, sizeof(buf));
    return BytesAt(address, buf, n);
}

bool WriteCode(DWORD address, const void *bytes, size_t length) {
    DWORD old = 0;
    void *p = reinterpret_cast<void *>(address);
    if (!VirtualProtect(p, length, PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "VirtualProtect failed (%lu) at 0x%08lx", GetLastError(), address);
        return false;
    }
    memcpy(p, bytes, length);
    DWORD dummy = 0;
    VirtualProtect(p, length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), p, length);
    return true;
}

bool WriteJump(DWORD from, const void *to) {
    BYTE j[5] = {0xe9};
    DWORD rel = reinterpret_cast<DWORD>(to) - (from + 5);
    memcpy(j + 1, &rel, 4);
    return WriteCode(from, j, 5);
}

// rate-limited probe: first call always, then every result change at level 2, every 2 s at level 3
struct Probe { const char *name; volatile LONG calls; LONG lastResult; DWORD lastTick; };
void Hit(Probe &p, int result, const char *fmt = nullptr, DWORD a = 0, DWORD b = 0, DWORD c = 0) {
    LONG n = InterlockedIncrement(&p.calls);
    char detail[200] = "";
    if (fmt) _snprintf_s(detail, sizeof(detail), _TRUNCATE, fmt, a, b, c);
    DWORD now = GetTickCount();
    if (n == 1) {
        Log(1, "%s: first call -> %d%s%s", p.name, result, detail[0] ? " - " : "", detail);
    } else if (result != p.lastResult) {
        Log(2, "%s: -> %d (call %ld)%s%s", p.name, result, n, detail[0] ? " - " : "", detail);
    } else if (g_logLevel >= 3 && now - p.lastTick >= 2000) {
        Log(3, "%s: still %d (call %ld)%s%s", p.name, result, n, detail[0] ? " - " : "", detail);
    } else {
        p.lastResult = result;
        return;
    }
    p.lastResult = result;
    p.lastTick = now;
}

// ---------------------------------------------------------------- engine globals (PC = TU)
const DWORD kGameTrackerPtr = 0x00fadb58;    // TU 0x829892b0
const DWORD kPlayerPtr = 0x00e7f094;         // TU 0x82efb464 (= [0x82efb458 + 0xc])
const DWORD kListPtr = 0x00fadfac;           // TU 0x829ca648 / retail 0x829ca560: targeter array
const DWORD kParamBase = 0x00fad764;         // TU / retail 0x82998ebc: player globals, +0x460.. targeter params
const DWORD kFreeList = 0x00cda0c4;          // TU 0x829beb64: free list of the weak-reference nodes

BYTE *GameTracker() { return *reinterpret_cast<BYTE *const *>(kGameTrackerPtr); }
BYTE *Player() { return *reinterpret_cast<BYTE *const *>(kPlayerPtr); }

// TruDlc2Player's doppelganger flag (TU gameTracker+0x1244)
typedef int(__cdecl *DoppelgangerFn)();
DoppelgangerFn g_dgFn = nullptr;
int g_dgLooked = 0;
int Doppelganger() {
    if (!g_dgFn && g_dgLooked < 100) {
        ++g_dgLooked;
        HMODULE m = GetModuleHandleA("TruDlc2Player.asi");
        if (m) g_dgFn = reinterpret_cast<DoppelgangerFn>(GetProcAddress(m, "TruDlc2PlayerDoppelganger"));
        if (!g_dgFn && g_dgLooked == 100) Log(0, "TruDlc2Player.asi / TruDlc2PlayerDoppelganger not found - doppelganger mode never seen");
    }
    return g_dgFn ? g_dgFn() : 0;
}

// The TU meter object (gameTracker+0x508) is owned by TruShadowPower (its translation of 0x823d7700..). It does not
// export it yet; this is the interface the strike / condition 538 need (proposal, docs Befund-Schattenkampf.md 5).
struct TruShadowPowerMeter {
    DWORD size;                       // sizeof the exporter's struct
    DWORD version;                    // 1
    volatile DWORD *flags;            // TU meter +0x04 (1 active, 2 strike, 4 strike look, 8 value >= tuning +0x2c, ..)
    float *value;                     // +0x08
    float *startValue;                // +0x0c
    float (*request)[2];              // +0x40: 7 time-scale request slots {player, world}
    void(__cdecl *selector)();        // 0x823d7520
    void(__cdecl *drain)(float amount);   // 0x823d8380
    // version 2 (TruShadowPower 0.11; layout only, not used here)
    float *delay;
    void(__cdecl *delayStart)();
    char(__cdecl *strikeReady)();
    char(__cdecl *canStart)();
    float(__cdecl *delayLeft)();
    // version 3 (proposal, docs Befund-Schattenkampf.md section 5): TruShadowPower's gameTracker+0x1280 copy
    volatile LONG *gt1280;
    // version 4 (TruShadowPower 0.14): TU 0x823d9050 (strike look off; returns at once unless meter flag 4, as the TU)
    void(__cdecl *strikeLookOff)();
};
const DWORD kMeterV1Size = 8 * 4;
const DWORD kMeterV3Size = 14 * 4;     // up to gt1280 (0.5.1: no longer sizeof - the struct grew with version 4)
const DWORD kMeterV4Size = 15 * 4;     // up to strikeLookOff (60)
typedef const TruShadowPowerMeter *(__cdecl *MeterApiFn)();
const TruShadowPowerMeter *g_meter = nullptr;
int g_meterLooked = 0;
const TruShadowPowerMeter *Meter() {
    if (!g_meter && g_meterLooked < 50) {
        ++g_meterLooked;
        HMODULE m = GetModuleHandleA("TruShadowPower.asi");
        MeterApiFn fn = m ? reinterpret_cast<MeterApiFn>(GetProcAddress(m, "TruShadowPowerMeterApi")) : nullptr;
        const TruShadowPowerMeter *api = fn ? fn() : nullptr;
        if (api && api->version >= 1 && api->size >= kMeterV1Size && api->flags && api->value && api->startValue &&
            api->request && api->selector && api->drain) {
            g_meter = api;
            Log(1, "TruShadowPower meter interface found (version %lu, size %lu)%s", api->version, api->size,
                (api->version >= 3 && api->size >= kMeterV3Size && api->gt1280)
                    ? " - gameTracker+0x1280 shared"
                    : " - no gameTracker+0x1280 (version 3): state 244 keeps its step count locally, condition 1048 "
                      "(TruShadowPower) does not see it");
            Log(1, "meter interface: strike look off (TU 0x823d9050) %s", (api->version >= 4 && api->size >= kMeterV4Size &&
                api->strikeLookOff) ? "found (version 4) - called by the strike tick / end as the TU"
                                    : "not offered (version < 4 or size < 60) - the strike skips it");
        } else if (fn && api && g_meterLooked == 1) {
            Log(0, "TruShadowPowerMeterApi returned an incomplete interface (version %lu, size %lu, expected >= %lu) - "
                   "not used", api->version, api->size, kMeterV1Size);
            g_meterLooked = 50;
        } else if (g_meterLooked == 50) {
            Log(1, "no meter interface: TruShadowPower.asi exports no TruShadowPowerMeterApi (0.9 does not) - the "
                   "doppelganger branch of condition 538 (meter flag 8) answers 0, the shadow strike is not run, "
                   "states 244 keep gameTracker+0x1280 locally");
        }
    }
    return g_meter;
}

// ---------------------------------------------------------------- tuning (object 858, as TruShadowPower)
// TU 0x82415518 returns the extension instance's data; the PC keeps the same data at the loaded object (+0x5c) of the
// object table entry id 858, state 2, data type 60 at +2 (checks of TU 0x82412b44..0x82412b7c).
const DWORD kFindObject = 0x0054e930;        // PC lookup that walks the table (checked: base / stride / count)
const char *const kFindObjectHex = "8b542404 33c0 b90c74db00";
const DWORD kFindObjectLoop = 0x0054e951;
const char *const kFindObjectLoopHex = "83c124 3dcc000000";
const DWORD kObjectTable = 0x00db7400;
const int kObjectCount = 0xcc;
const SHORT kExtensionObject = 858;
const WORD kTuningType = 60;
bool g_tableOk = false;

const BYTE *Tuning() {
    if (!g_tableOk) return nullptr;
    __try {
        for (int i = 0; i < kObjectCount; ++i) {
            const BYTE *entry = reinterpret_cast<const BYTE *>(kObjectTable + i * 0x24);
            if (*reinterpret_cast<const SHORT *>(entry + 0xc) != kExtensionObject) continue;
            if (*reinterpret_cast<const WORD *>(entry + 0xe) != 2) return nullptr;
            const BYTE *object = *reinterpret_cast<const BYTE *const *>(entry + 8);
            if (!object) return nullptr;
            const BYTE *data = *reinterpret_cast<const BYTE *const *>(object + 0x5c);
            if (!data || !*reinterpret_cast<const DWORD *>(object + 0x60)) return nullptr;
            if (*reinterpret_cast<const WORD *>(data + 2) != kTuningType) return nullptr;
            return data;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return nullptr;
}

// ---------------------------------------------------------------- 1. target list
const int kRetailTargeters = 7, kTuTargeters = 10;
bool g_listOk = false;       // patches applied: [0xfadfac] arrays are built with 10 entries

// TU index -> PC slot (slots 0..6 keep the PC / retail meaning)
int SlotOf(int tu) {
    if (tu == 6) return 7;
    if (tu == 7) return 6;
    return tu;
}
int TuOf(int slot) { return SlotOf(slot); }   // the mapping is its own inverse

struct Patch { DWORD at; const char *expect; DWORD write; const char *with; const char *what; };
const Patch kListPatches[] = {
    {0x00722630, "6a1c ffd0 3bc3 740e 8bc8 e8f1b5ffff", 0x00722631, "28", "player init: array 0x1c -> 0x28 bytes (TU 0x824135f0)"},
    {0x0071dc78, "83fe07 7cc3", 0x0071dc7a, "0a", "list ctor tru+0x31dc30: 7 -> 10 targeters (TU 0x8240633c)"},
    {0x00716915, "bd71000000", 0x00716916, "f1030000", "instance add tru+0x316860: candidate mask 0x71 -> 0x3f1 (TU 0x824064a4)"},
    {0x00716946, "83fe07 7ce6", 0x00716948, "0a", "instance add tru+0x316860: marker loop 7 -> 10 (TU 0x824064dc)"},
    {0x007169a2, "bf71000000", 0x007169a3, "f1030000", "instance add tru+0x316860: mask 0x71 -> 0x3f1 (TU 0x8240656c)"},
    {0x007169d0, "83fe07 7ceb", 0x007169d2, "0a", "instance add tru+0x316860: loop 7 -> 10 (TU 0x82406594)"},
    {0x0071aca9, "83fe07 7ce9", 0x0071acab, "0a", "tru+0x31ac80 (all targeters, from tru+0x31f1d0 = TU 0x823ed958): 7 -> 10"},
    {0x0071dcce, "83fe07 7ced", 0x0071dcd0, "0a", "tru+0x31dcb0 (all targeters, TU 0x823c3eb8 / 0x823c6790 / 0x822ebc58 / 0x823ed958): 7 -> 10"},
    {0x00716843, "83f807 89442410 7c95", 0x00716845, "0a", "list destroy tru+0x3167d0: 7 -> 10 (TU 0x82412f4c)"},
    {0x007228a3, "83fe07 7ce8", 0x007228a5, "0a", "player update: per-frame targeter loop 7 -> 10 (TU 0x82412878)"},
};

// PC parameter function tru+0x2ecc10 (retail 0x823ff7d8): cdecl(s8 index), switch 0..6 over [0xfad764] +0x460..
const DWORD kParamFn = 0x006ecc10;
const char *const kParamFnHex = "0fbe442404 83f806 775f ff24857ccc6e00 a164d7fa00 8b8060040000 c3 8b0d64d7fa00 8b8164040000 c3 "
                                "8b1564d7fa00 8b8268040000 c3 a164d7fa00 8b806c040000 c3 8b0d64d7fa00 8b8170040000 c3 "
                                "8b1564d7fa00 8b8274040000 c3 a164d7fa00 8b8078040000 c3 33c0 c3";
const DWORD kParamFnCaller = 0x0071dc5c;     // its only caller: push esi; call; add esp, 4 (list ctor)
const char *const kParamFnCallerHex = "56 e8aeeffcff 83c404 50 56 8bcf e892fcffff";

volatile LONG g_paramLogs = 0;

// TU 0x82402208(s8 index): with a player, a game tracker and the tuning, the first entry of tuning +0x90 (count
// +0x94; 8-byte entries {u8 index, 3 bytes, param}) with that index wins; otherwise 0..5 -> +0x460 + 4 i, 6 -> +0x468,
// 7 -> +0x478, else 0.
DWORD __cdecl ParamHook(int arg) {
    const int slot = static_cast<signed char>(arg);
    const int tu = TuOf(slot);
    DWORD param = 0;
    const char *source = "none";
    __try {
        const BYTE *tuning = (Player() && GameTracker()) ? Tuning() : nullptr;
        if (tuning) {
            const DWORD count = *reinterpret_cast<const DWORD *>(tuning + 0x94);
            const BYTE *table = *reinterpret_cast<const BYTE *const *>(tuning + 0x90);
            if (count > 64) {
                // the converted file of 50k has 0x200 here (u32 2 converted as a u16 pair) - tree 50l fixes it
                Log(0, "tuning +0x94 = %lu entries - implausible (converter error, fixed in tree dlc_test50l_combat): "
                       "table not used for targeter slot %d", count, slot);
            } else if (count && table) {
                for (DWORD i = 0; i < count; ++i) {
                    if (static_cast<signed char>(table[i * 8]) == tu) {
                        param = *reinterpret_cast<const DWORD *>(table + i * 8 + 4);
                        source = "DLC 2 tuning table (object 858 +0x90)";
                        break;
                    }
                }
            }
        }
        if (!param && strcmp(source, "none") == 0) {
            const BYTE *base = *reinterpret_cast<const BYTE *const *>(kParamBase);
            int offset = -1;
            if (tu >= 0 && tu <= 5) offset = 0x460 + 4 * tu;
            else if (tu == 6) offset = 0x468;
            else if (tu == 7) offset = 0x478;
            if (offset >= 0) {
                param = *reinterpret_cast<const DWORD *>(base + offset);
                source = tu == 6 ? "default +0x468 (TU: index 6 takes the parameters of 2)" : "default (retail table)";
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "targeter slot %d: access fault in the parameter lookup - no parameters", slot);
        param = 0;
        source = "fault";
    }
    if (InterlockedIncrement(&g_paramLogs) <= 40 || g_logLevel >= 2)
        Log(1, "targeter slot %d (TU index %d): parameters 0x%08lx - %s", slot, tu, param, source);
    return param;
}

bool SetupTargetList() {
    if (!g_targetList) { Log(1, "target list: off ([TargetList] Enabled=0) - conditions 2005 / 2006 / 2011 (doppelganger) / 2013 answer 0"); return false; }
    for (const Patch &p : kListPatches)
        if (!HexAt(p.at, p.expect)) {
            Log(0, "target list: bytes at 0x%08lx do not match (%s) - nothing patched", p.at, p.what);
            return false;
        }
    if (!HexAt(kParamFn, kParamFnHex) || !HexAt(kParamFnCaller, kParamFnCallerHex) ||
        !HexAt(kFindObject, kFindObjectHex) || !HexAt(kFindObjectLoop, kFindObjectLoopHex)) {
        Log(0, "target list: parameter function tru+0x2ecc10 / its caller / the object table lookup do not match - nothing patched");
        return false;
    }
    __try {
        if (*reinterpret_cast<const DWORD *>(kListPtr) != 0) {
            Log(0, "target list: [0xfadfac] is already built (0x%08lx) - too late, nothing patched",
                *reinterpret_cast<const DWORD *>(kListPtr));
            return false;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    // parameter function first (only the ctor calls it), then the constants
    if (!WriteJump(kParamFn, reinterpret_cast<const void *>(&ParamHook))) return false;
    for (const Patch &p : kListPatches) {
        BYTE b[8];
        size_t n = ParseHex(p.with, b, sizeof(b));
        if (!WriteCode(p.write, b, n)) {
            Log(0, "target list: write at 0x%08lx failed - the game may be inconsistent, restart without the plugin", p.write);
            return false;
        }
        Log(2, "target list: 0x%08lx patched (%s)", p.write, p.what);
    }
    Log(1, "target list: %d -> %d targeters (TU 0x824062c8 / 0x82406390 / 0x82412ca0 / 0x824126d8), %d sites patched, "
           "parameter function tru+0x2ecc10 = TU 0x82402208 (slot 7 = TU 6, 8 / 9 = TU 8 / 9)",
        kRetailTargeters, kTuTargeters, static_cast<int>(sizeof(kListPatches) / sizeof(kListPatches[0])));
    return true;
}

// ---------------------------------------------------------------- PC building blocks of the target code
typedef BYTE *(__fastcall *TargetOfFn)(BYTE *player, int, int index);        // tru+0x31caf0 = TU 0x823dd260
typedef DWORD *(__fastcall *TargeterTargetFn)(BYTE *targeter, int);          // tru+0x319f00 = TU 0x82404568
typedef int(__fastcall *AcceptsFn)(BYTE **list, int, BYTE *target, int idx); // tru+0x313760 = TU 0x82406618
typedef int(__cdecl *QueryArgFn)(BYTE *inst, int id, void *arg);             // tru+0x1b3720 (query + [0xd98f9c] = arg)
typedef char(__fastcall *TargetCheckPcFn)(BYTE *player, int);                // tru+0x2f2800 = TU 0x823df8f8 (retail)
typedef char(__cdecl *PredFn)(const BYTE *record);
typedef char(__cdecl *CondTemplateFn)(void *agent, void *cache, const BYTE *record, PredFn pred);
typedef char(__cdecl *CondFn)(void *agent, void *cache, const BYTE *record);
typedef void(__cdecl *StateFn)(void *agent);

const DWORD kTargetOf = 0x0071caf0;
const char *const kTargetOfHex = "8b442404 50 e8a6feffff 85c0 740c 50 e8cc6ee9ff 83c404 c20400";
const DWORD kTargetOfInner = 0x0071c9a0;     // = TU 0x823dd138: bit 11, bit 6 (+0x20), +0x788, bit 10 -> list[0], list[idx]
const char *const kTargetOfInnerHex = "83ec08 53 8bd9 8b83fc010000 55 c1e80b 33ed a801";
const DWORD kTargetOfIndex = 0x0071cac4;     // mov ecx, [0xfadfac]; mov ecx, [ecx + eax*4]; call 0x719f00
const char *const kTargetOfIndexHex = "8b0dacdffa00 8b0c81 e82ed4ffff";
const DWORD kTargeterTarget = 0x00719f00;
const char *const kTargeterTargetHex = "56 8bf1 8b8690000000 85c0 7438 83c008 50 e88a2dfdff";
const DWORD kAccepts = 0x00713760;
const char *const kAcceptsHex = "8b442404 53 8b5c240c 56 57 8bf9 8b0c9f 6a00 50 e8a897fdff 8bf0 85f6 7432 56 e81c95fdff";
const DWORD kQueryArg = 0x005b3720;
const char *const kQueryArgHex = "8b4c2404 8b44240c 8d9110010000 85d2 a39c8fd900 740a 8b811c010000 85c0";
const DWORD kWeakRefInline = 0x0071ca5c;     // the PC inline of TU 0x8237e050 on player +0x20 (same node / free list)
const char *const kWeakRefInlineHex = "834004ff 750d 8b15c4a0cd00 8910 a3c4a0cd00";
const DWORD kCondTemplate = 0x00782d70;      // = TU 0x82487718
const char *const kCondTemplateHex = "51 53 55 8b6c2418 56 8b742418 8b5e08 57 8b7c2418 393e c644241300 750b 8b4604 3b870c050000 7423 55 ff542428";
// TU 0x823df8f8 = tru+0x2f2800 (retail body) + the TU's doppelganger branch (same translation as TruShadowPower 0.9)
const DWORD kTargetCheckPc = 0x006f2800;
const char *const kTargetCheckPcHex =
    "53 8b1d58dbfa00 8b8300050000 56 8bb034010000 83fe0c 57 8bf9 0f8491000000 83fe07 0f8488000000 83fe03 747d "
    "83fe04 7478 e898f6ffff 84c0 756f 8b87fc010000 8bc8 c1e91e f6c101 755f 8bd0 c1ea15 f6c201 7555 c1e818 a801 754e "
    "83feff 744f d9ee d89b88050000 dfe0 f6c405 7b3a 803de6b48a0000 7437 f60544f1e70001 752e 803d43f1e70004 7425 "
    "a1682ba000 8b4818 8b11 8b8230060000 2404 33c9 3c04 0f94c1 8bc1 85c0 7406 5f 5e b001 5b c3 5f 5e 32c0 5b c3";
// PC (retail) condition handlers / predicates replaced in doppelganger mode
const DWORD kCond2011Pc = 0x007659e0, kPred2011Pc = 0x00765970;
const char *const kCond2011PcHex = "8b44240c 8b4c2408 8b542404 6870597600";
const char *const kPred2011PcHex = "51 a158dbfa00 8b8804050000 8b91fc010000 c1ea0a f6c201 7504 32c0 59 c3 56 6a05 e85a71fbff";
const DWORD kCond538Pc = 0x00765fb0, kPred538Pc = 0x00765fa0;
const char *const kCond538PcHex = "8b44240c 8b4c2408 8b542404 68a05f7600";
const char *const kPred538PcHex = "a158dbfa00 8b8804050000 e91007f8ff";

bool g_blocksOk = false;

BYTE **List() { return *reinterpret_cast<BYTE **const *>(kListPtr); }

// object of a handle {object, id} if still valid (PC tru+0x1b39d0 = the TU's inline `+0x44 == id`)
BYTE *HandleObject(const DWORD *h) {
    if (!h) return nullptr;
    BYTE *o = reinterpret_cast<BYTE *>(h[0]);
    if (!o || *reinterpret_cast<const DWORD *>(o + 0x44) != h[1]) return nullptr;
    return o;
}

bool Excluded(const BYTE *o) { return (*reinterpret_cast<const DWORD *>(o + 0x14) & 0x400000) != 0; }

// TU 0x8237e050(x): weak reference node at x+0xc {handle *, count}: handle -> return it; else count - 1, at 0 the
// node goes to the free list [0xcda0c4] (TU 0x829beb64), x+0xc = 0, return 0
DWORD *WeakRef(BYTE *x) {
    DWORD *node = *reinterpret_cast<DWORD **>(x + 0xc);
    if (!node) return nullptr;
    if (node[0]) return reinterpret_cast<DWORD *>(node[0]);
    if (--node[1] == 0) {
        node[0] = *reinterpret_cast<DWORD *>(kFreeList);
        *reinterpret_cast<DWORD *>(kFreeList) = reinterpret_cast<DWORD>(node);
    }
    *reinterpret_cast<DWORD **>(x + 0xc) = nullptr;
    return nullptr;
}

// TU 0x82404568(list[tu]) + handle check
BYTE *TargeterObject(int tu) {
    BYTE **list = List();
    if (!list) return nullptr;
    BYTE *t = list[SlotOf(tu)];
    if (!t) return nullptr;
    return HandleObject(reinterpret_cast<TargeterTargetFn>(kTargeterTarget)(t, 0));
}

// TU 0x823dd260(player, tu)
BYTE *TargetOf(BYTE *player, int tu) {
    return reinterpret_cast<TargetOfFn>(kTargetOf)(player, 0, SlotOf(tu));
}

// TU 0x82406618(list, target, tu)
bool Accepts(BYTE *target, int tu) {
    BYTE **list = List();
    if (!list || !list[SlotOf(tu)]) return false;
    return reinterpret_cast<AcceptsFn>(kAccepts)(list, 0, target, SlotOf(tu)) != 0;
}

// TU 0x823df8f8 with the doppelganger branch (0x823df918..0x823df970)
bool InputWord(DWORD offset, DWORD *value) {
    const BYTE *p = *reinterpret_cast<const BYTE *const *>(0x00a02b68);   // TU 0x8286dd90
    if (!p) return false;
    const BYTE *list = *reinterpret_cast<const BYTE *const *>(p + 0x18);
    if (!list) return false;
    const BYTE *rec = *reinterpret_cast<const BYTE *const *>(list);
    if (!rec) return false;
    *value = *reinterpret_cast<const DWORD *>(rec + offset);
    return true;
}

bool TargetCheck(const BYTE *gt, BYTE *player) {
    if (!Doppelganger()) return reinterpret_cast<TargetCheckPcFn>(kTargetCheckPc)(player, 0) != 0;
    const int mode = *reinterpret_cast<const int *>(*reinterpret_cast<const BYTE *const *>(gt + 0x500) + 0x134);
    if (mode == 0xc || mode == 7) return false;
    const DWORD w = *reinterpret_cast<const DWORD *>(player + 0x1fc);
    if (((w >> 9) & 1) || ((w >> 10) & 1)) return true;
    if ((w >> 30) & 1) return true;
    if ((w >> 24) & 1) return true;
    if (mode == -1) return false;
    if (0.0f < *reinterpret_cast<const float *>(gt + 0x588)) return true;
    if (*reinterpret_cast<const volatile BYTE *>(0x008ab4e6) == 0) return false;   // TU 0x8275422a
    if (*reinterpret_cast<const volatile BYTE *>(0x00e7f144) & 1) return false;    // TU 0x82efb514
    if (*reinterpret_cast<const volatile BYTE *>(0x00e7f143) == 4) return false;   // TU 0x82efb513
    DWORD word = 0;
    if (!InputWord(0x630, &word)) return false;
    return (word & 4) == 4;
}

bool CheckBlocks() {
    struct { DWORD at; const char *hex; const char *what; } const checks[] = {
        {kTargetOf, kTargetOfHex, "tru+0x31caf0 (TU 0x823dd260)"},
        {kTargetOfInner, kTargetOfInnerHex, "tru+0x31c9a0 (TU 0x823dd138)"},
        {kTargetOfIndex, kTargetOfIndexHex, "tru+0x31cac4 list[index]"},
        {kTargeterTarget, kTargeterTargetHex, "tru+0x319f00 (TU 0x82404568)"},
        {kAccepts, kAcceptsHex, "tru+0x313760 (TU 0x82406618)"},
        {kQueryArg, kQueryArgHex, "tru+0x1b3720 (query with argument)"},
        {kWeakRefInline, kWeakRefInlineHex, "free list [0xcda0c4] (TU 0x8237e050)"},
        {kCondTemplate, kCondTemplateHex, "condition template tru+0x382d70 (TU 0x82487718)"},
        {kTargetCheckPc, kTargetCheckPcHex, "tru+0x2f2800 (TU 0x823df8f8)"},
        {0x006f1ed0, "8b81fc010000 8bc8 c1e909 f6c101 750a c1e80a a801 7503 33c0 c3 b801000000 c3", "tru+0x2f1ed0 (bits 9 / 10)"},
        {0x00718c39, "8b0d682ba000 8b5118 8b0a 8b91f0060000 80e210", "input chain [[0xa02b68]+0x18]->[0]"},
        {kCond2011Pc, kCond2011PcHex, "condition 2011 tru+0x3659e0"},
        {kPred2011Pc, kPred2011PcHex, "predicate 2011 tru+0x365970"},
        {kCond538Pc, kCond538PcHex, "condition 538 tru+0x365fb0"},
        {kPred538Pc, kPred538PcHex, "predicate 538 tru+0x365fa0"},
    };
    for (const auto &c : checks)
        if (!HexAt(c.at, c.hex)) {
            Log(0, "conditions: %s at 0x%08lx does not match - conditions not translated", c.what, c.at);
            return false;
        }
    return true;
}

// ---------------------------------------------------------------- 2. predicates
Probe g_p2005 = {"condition 2005 (TU 0x8246e8e0: aim target / targeter 6 agree)"};
Probe g_p2006 = {"condition 2006 (TU 0x8246eb08: target is a data-type 0x4f / 0xb00b instance)"};
Probe g_p2013 = {"condition 2013 (TU 0x8246ea30: target of state 1017 = targeter 6)"};
Probe g_p2011 = {"condition 2011 (TU 0x8246f140: doppelganger -> targeter 9 + query 0x161)"};
Probe g_p538 = {"condition 538 (TU 0x8246faa8: doppelganger -> meter flag 8)"};

// TU-only gameTracker +0x1284 / +0x1288 (handle {object, id} of state 1017's target; the PC uses those offsets for
// other data). Zeroed with every new tracker on the TU (memset 0x82413878); only 1017 writes it - not ported in 0.1.
DWORD g_gt1284[2] = {0, 0};

bool IsBooBType(const BYTE *o) {
    const BYTE *d = *reinterpret_cast<const BYTE *const *>(o + 0x50);
    return d && *reinterpret_cast<const WORD *>(d + 4) == 0xb00b && *reinterpret_cast<const WORD *>(d + 2) == 0x4f;
}

char __cdecl Pred2005(const BYTE *) {
    char r = 0;
    DWORD why = 0;
    __try {
        BYTE *gt = GameTracker();
        BYTE *player = *reinterpret_cast<BYTE **>(gt + 0x504);
        if (!g_listOk) { why = 9; goto done; }
        if ((*reinterpret_cast<const DWORD *>(player + 0x1fc) >> 10) & 1) {
            if (WeakRef(player)) {
                BYTE *aim = HandleObject(WeakRef(player));
                if (aim && !Excluded(aim)) { why = 1; r = Accepts(aim, 6) ? 1 : 0; goto done; }
            }
        }
        BYTE *t = TargetOf(player, 6);
        if (!t || Excluded(t)) { why = 2; goto done; }
        BYTE *o = TargeterObject(6);
        if (!o || Excluded(o)) { why = 3; goto done; }
        why = 4;
        r = (o == t) ? 1 : 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        why = 8;
        r = 0;
    }
done:
    Hit(g_p2005, r, "path %lu (1 aim, 2 no target 6, 3 targeter 6 empty, 4 compare, 8 fault, 9 list off)", why);
    return r;
}

char __cdecl Pred2006(const BYTE *) {
    char r = 0;
    DWORD why = 0;
    __try {
        BYTE *gt = GameTracker();
        BYTE *player = *reinterpret_cast<BYTE **>(gt + 0x504);
        if (!g_listOk) { why = 9; goto done; }
        if (TargetCheck(gt, player) && WeakRef(player)) {
            BYTE *o = HandleObject(WeakRef(player));
            why = 1;
            // the TU reads +0x50 of a null object here (guest memory); the PC would fault - 0 is the TU's result there
            r = (o && IsBooBType(o)) ? 1 : 0;
        } else {
            BYTE *t = TargetOf(player, 6);
            why = 2;
            if (t && !Excluded(t)) {
                BYTE *o = TargeterObject(6);
                why = 3;
                if (o && !Excluded(o) && t == o && IsBooBType(t)) r = 1;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        why = 8;
        r = 0;
    }
done:
    Hit(g_p2006, r, "path %lu (1 check + aim, 2 no target 6, 3 targeter 6, 8 fault, 9 list off)", why);
    return r;
}

char __cdecl Pred2013(const BYTE *) {
    char r = 0;
    __try {
        BYTE *o = HandleObject(g_gt1284);
        if (g_listOk && o && !Excluded(o)) {
            BYTE *t = TargeterObject(6);
            r = (t && !Excluded(t) && t == o) ? 1 : 0;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        r = 0;
    }
    Hit(g_p2013, r, "state-1017 target 0x%08lx (state 1017 not ported in 0.1)", g_gt1284[0]);
    return r;
}

char __cdecl Pred2011(const BYTE *record) {
    const int dg = Doppelganger();
    if (!dg) return reinterpret_cast<PredFn>(kPred2011Pc)(record);      // retail = PC
    char r = 0;
    DWORD why = 0;
    BYTE *target = nullptr;
    __try {
        if (!g_listOk) { why = 9; goto done; }
        // TU 0x8246f170..: doppelganger -> targeter 9
        target = TargeterObject(9);
        if (!target || Excluded(target)) { why = 1; goto done; }
        BYTE *player = Player();
        void *arg = player;                                             // TU [0x829bffa4] = &{player}
        why = 2;
        if (reinterpret_cast<QueryArgFn>(kQueryArg)(target, 0x161, &arg)) { why = 3; r = 1; }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        why = 8;
        r = 0;
    }
done:
    Hit(g_p2011, r, "doppelganger, target 0x%08lx, path %lu (1 targeter 9 empty, 2 query 0x161 = 0, 3 ok, 8 fault, 9 list off)",
        reinterpret_cast<DWORD>(target), why);
    return r;
}

char __cdecl Pred538(const BYTE *record) {
    const int dg = Doppelganger();
    if (!dg) return reinterpret_cast<PredFn>(kPred538Pc)(record);       // player +0x1fc bit 22 (retail = PC)
    const TruShadowPowerMeter *m = Meter();
    char r = m ? static_cast<char>((*m->flags >> 3) & 1) : 0;
    if (m)
        Hit(g_p538, r, "doppelganger, meter flags 0x%03lx", *m->flags);
    else
        Hit(g_p538, r, "doppelganger, no meter interface (TruShadowPowerMeterApi) - 0");
    return r;
}

#define COND_HANDLER(name, pred)                                                              \
    char __cdecl name(void *agent, void *cache, const BYTE *record) {                         \
        char r = 0;                                                                           \
        __try {                                                                               \
            r = reinterpret_cast<CondTemplateFn>(kCondTemplate)(agent, cache, record, &pred); \
        } __except (EXCEPTION_EXECUTE_HANDLER) {                                              \
            r = 0;                                                                            \
        }                                                                                     \
        return r;                                                                             \
    }
COND_HANDLER(Cond2005, Pred2005)   // TU 0x8246ea20
COND_HANDLER(Cond2006, Pred2006)   // TU 0x8246ec68
COND_HANDLER(Cond2013, Pred2013)   // TU 0x8246eaf8
COND_HANDLER(Cond2011, Pred2011)   // TU 0x8246f270
COND_HANDLER(Cond538, Pred538)     // TU 0x8246fae0

// ---------------------------------------------------------------- 3. state 1014 gate
// TU 0x8245fd70 / 0x8245fdc0 / 0x8245fd98: gameTracker+0x1244 -> meter functions 0x823d8978 / 0x823d9210 /
// 0x823d8d18, else the player functions (= PC tru+0x31d3c0 / +0x318fd0 / +0x318d00 through tru+0x35e0b0 / d0 / c0).
const DWORD kState1014Pc[3] = {0x0075e0b0, 0x0075e0d0, 0x0075e0c0};   // slots 0, 2, 3
const char *const kState1014PcHex[3] = {"a158dbfa00 8b8804050000 e900f3fbff", "a158dbfa00 8b8804050000 e9f0aefbff",
                                        "a158dbfa00 8b8804050000 e930acfbff"};
StateFn g_orig1014[3] = {nullptr, nullptr, nullptr};
Probe g_p1014[3] = {{"state 1014 slot 0 (TU 0x823d8978 shadow strike start)"},
                    {"state 1014 slot 2 (TU 0x823d9210 shadow strike end)"},
                    {"state 1014 slot 3 (TU 0x823d8d18 shadow strike tick)"}};

// ---------------------------------------------------------------- 0.2: PC building blocks of the states / strike
const float kZero = 0.0f, kOne = 1.0f, kMinusOne = -1.0f, kHundred = 100.0f, kShortMove = 200.0f;   // TU 0x8207d538,
// 0x8207d544, 0x82052664, 0x8207d53c, 0x8206af90
const double kPerHundred = 0.01;    // TU 0x8207dd48 (double)
const float kMeterStart = 1000.0f;  // TU 0x8206af78

typedef void *(__fastcall *ParamNodeFn)(void *agent, int, int id);             // tru+0x383f50 = TU 0x82482d28
typedef BYTE *(__fastcall *ParamFindFn)(void *node, int, int id);              // tru+0x384b30 = TU 0x82488680
typedef float *(__cdecl *FaceFn)(float *out, const BYTE *inst, const float *dir);   // tru+0x30b8a0 = TU 0x8241b1e8
typedef float *(__fastcall *AxisAngleFn)(float *out, int, const float *axis, float angle);   // tru+0x49dfd0 = 0x8213e760
typedef void(__fastcall *ToRotFn)(const float *src, int, float *out);         // tru+0x49d450 = TU 0x820ef928
typedef void(__fastcall *ChanMode2Fn)(BYTE *chan, int, const float *vec, float frames);     // tru+0x438d00
typedef void(__fastcall *ChanMode3Fn)(BYTE *chan, int, const float *rot, const float *pos, float frames);  // +0x438dc0
typedef void(__fastcall *AnimSetFn)(BYTE *chan, int, int anim, void *object);  // tru+0x444ba0 = TU 0x820e0560
typedef BYTE *(__cdecl *RecordFn)(BYTE *target, BYTE *player, const float *pos, const float *rot, float frames);  // +0x645e40
typedef void(__cdecl *MessageFn)(BYTE *inst, int msg, void *arg);              // tru+0x1b3750 (wake + message)
typedef void(__cdecl *PlayerEventFn)(BYTE *inst, int type, int all, int channel);   // tru+0x318780 = TU 0x82418158
typedef void(__cdecl *HudUpdateFn)();                                          // tru+0x37da70
typedef void(__fastcall *HitFn)(BYTE *hit, int, BYTE *attacker, int a, int b, int c, int d);   // tru+0x1b4de0
typedef BYTE *(__fastcall *VGetFn)(BYTE *self, int);                           // virtual getters

const DWORD kParamNode = 0x00783f50, kParamFind = 0x00784b30, kFace = 0x0070b8a0, kAxisAngle = 0x0049dfd0,
            kToRot = 0x0049d450, kChanMode2 = 0x00438d00, kChanMode3 = 0x00438dc0, kAnimSet = 0x00444ba0,
            kRecord = 0x00645e40, kMessage = 0x005b3750, kPlayerEvent = 0x00718780, kHudUpdate = 0x0077da70,
            kHit = 0x005b4de0, kCameraMgr = 0x00e804f0, kAimObjPtr = 0x00fadfb0, kHudStrikeByte = 0x00fae8ae;
bool g_statesOk = false, g_strikeOk = false;

bool CheckStateBlocks() {
    struct { DWORD at; const char *hex; const char *what; } const s[] = {
        {kParamNode, "56 8bf1 8b8620050000 85c0", "state parameter node tru+0x383f50"},
        {kParamFind, "0fb701 53 56 57 8b7c2410 33db", "state parameter record tru+0x384b30"},
        {0x0075f470, "83ec08 56 57 8b7c241c 8b4704 0fb77002 8b4f08 69f620030000 8b9180020000 037214", "channel (tru+0x35f470)"},
        {0x00438970, "0fb681f8000000 6bc070 038180000000", "animation entry tru+0x38970"},
        {kFace, "55 8bec 83e4f0 83ec6c f30f101d1c118400 8b4510 0f2800 f30f103534118400 f30f100d30118400", "facing tru+0x30b8a0 (TU 0x8241b1e8)"},
        {0x0070b9e0, "8b442408 8b0d94f0e700 56 8b742408 50 51 56 e8a9feffff", "facing wrapper tru+0x30b9e0"},
        {kAxisAngle, "55 8bec 83e4f0 83ec18 d9450c 56 dc0dc0138400", "axis / angle tru+0x49dfd0"},
        {kChanMode2, "55 8bec 83e4f0 83ec10 f30f100534118400 d9450c", "channel mode 2 tru+0x38d00"},
        {0x00438d59, "c7402402000000", "channel mode 2 store"},
        {0x005e7770, "b8f004e800 c3", "camera manager getter (0xe804f0)"},
        {0x00855bc4, "b03a4300", "camera manager vtable slot 0xe0 -> tru+0x33ab0"},
        {0x00433ab0, "8b4144 c3", "camera manager slot 0xe0: mov eax, [ecx+0x44] (TU 0x822a9fd8 lwz r3, 0x44(r3))"},
        {0x0071388f, "d94710", "[0xfadfb0] +0xb0 use (tru+0x3137c0 = retail 0x82404bc0)"},
    };
    for (const auto &c : s)
        if (!HexAt(c.at, c.hex)) { Log(0, "states 1017 / 244 / 1007: %s at 0x%08lx does not match - not translated", c.what, c.at); return false; }
    return true;
}

bool CheckStrikeBlocks() {
    struct { DWORD at; const char *hex; const char *what; } const s[] = {
        {kToRot, "55 8bec 83e4f0 8b4508 83ec5c 56 8bf1 50", "rotation from facing tru+0x49d450 (TU 0x820ef928)"},
        {kChanMode3, "55 8bec 83e4f0 d94510 8bc1 8b4d08 0f2801 8b4d0c 0f294010", "channel mode 3 tru+0x38dc0"},
        {0x00438df1, "c7402403000000", "channel mode 3 store"},
        {kAnimSet, "83ec2c a1e8d78b00 33c4 89442428", "animation set tru+0x44ba0 (TU 0x820e0560)"},
        {kRecord, "55 8bec 83e4f0 6a40 e8c3acf7ff d94518", "message record tru+0x245e40"},
        {kMessage, "56 8b742408 8d8610010000 85c0 7422 57 8bbe20010000", "wake + message tru+0x1b3750"},
        {kPlayerEvent, "51 817c240cff000000 0f84f2000000", "player event walker tru+0x318780"},
        {kHudUpdate, "8b0d20e9fa00 8b01 8b500c ffe2", "HUD update tru+0x37da70"},
        {0x00718e23, "c605aee8fa0001", "HUD strike byte [0xfae8ae] (retail strike tick tru+0x318d00)"},
        {kHit, "55 8bec 83e4f0 83ec24 8a550c 53 668b5d18 56 8bf1 8b4e40 57 8b7d08 8b8718020000 89464c", "hit tru+0x1b4de0 (TU 0x8226f5c8)"},
        {0x005b4efd, "c21400", "hit: ret 0x14"},
    };
    for (const auto &c : s)
        if (!HexAt(c.at, c.hex)) { Log(0, "shadow strike: %s at 0x%08lx does not match - not translated", c.what, c.at); return false; }
    return true;
}

BYTE *Channel(const BYTE *agent) {
    const BYTE *instance = *reinterpret_cast<const BYTE *const *>(agent + 8);
    const BYTE *anim = *reinterpret_cast<const BYTE *const *>(instance + 0x280);
    WORD index = *reinterpret_cast<const WORD *>(*reinterpret_cast<const BYTE *const *>(agent + 4) + 2);
    return *reinterpret_cast<BYTE *const *>(anim + 0x14) + 0x320 * index;
}
const BYTE *AnimEntry(const BYTE *chan) { return *reinterpret_cast<const BYTE *const *>(chan + 0x80) + 0x70 * chan[0xf8]; }

const BYTE *ParamRecord(void *agent, int id) {
    void *node = reinterpret_cast<ParamNodeFn>(kParamNode)(agent, 0, id);
    return node ? reinterpret_cast<ParamFindFn>(kParamFind)(node, 0, id) : nullptr;
}

typedef __declspec(align(16)) float Vec4[4];
void Copy4(float *d, const float *s) { for (int i = 0; i < 4; ++i) d[i] = s[i]; }
// TU normalisation (vdot3fp, vrsqrtefp + one Newton step, vsel): xyz / |xyz|, w = w / |xyz|; a zero length gives
// the zero vector (the squared length). sqrtf instead of the estimate - differs in the last bits only.
void Normalize3(float *v) {
    float sq = v[0] * v[0] + v[1] * v[1] + v[2] * v[2];
    if (sq == kZero) { v[0] = v[1] = v[2] = v[3] = kZero; return; }
    float r = 1.0f / sqrtf(sq);
    for (int i = 0; i < 4; ++i) v[i] *= r;
}
float Length3(const float *v) { return sqrtf(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]); }

// gameTracker+0x1280: TruShadowPower's copy through the interface, else a local one (condition 1048 then lacks it)
LONG g_local1280 = 0;
volatile LONG *Gt1280() {
    const TruShadowPowerMeter *m = Meter();
    return (m && m->version >= 3 && m->size >= kMeterV3Size && m->gt1280) ? m->gt1280 : &g_local1280;
}

// 0.5.1: TU 0x823d9050 (strike look off) through the meter interface v4 (TruShadowPower 0.14). It returns at once
// unless meter flag 4 is set - on the TU as in TruShadowPower's StrikeLookOffBody. Without version 4 it is skipped
// (logged once): then a strike look ([Look] StrikeLook=1 in TruShadowPower) can leave flag 4 set after the strike.
volatile LONG g_lookOffMissing = 0;
void LookOff(const TruShadowPowerMeter *m, const char *where) {
    if (m->version >= 4 && m->size >= kMeterV4Size && m->strikeLookOff) {
        const DWORD before = *m->flags;
        m->strikeLookOff();
        if (before & 4) Log(1, "shadow strike %s: strike look off (TU 0x823d9050 via meter interface v4), meter flags 0x%03lx -> 0x%03lx",
                            where, before, *m->flags);
        return;
    }
    if (InterlockedIncrement(&g_lookOffMissing) == 1)
        Log(1, "shadow strike %s: TU 0x823d9050 (strike look off) skipped - meter interface version %lu, size %lu (needs "
               "version >= 4, size >= %lu: TruShadowPower 0.14); logged once", where, m->version, m->size, kMeterV4Size);
}

// TU 0x82457b28(out, target, flag): flag set and no / excluded target -> [0x829ca64c] (= PC [0xfadfb0]) +0xb0: +0x18 >
// 0 -> rotation about (0, 0, 1, 0) [0x8207db00] by +0x8 (0x8213e760 = tru+0x49dfd0), else face along -row 1 of the
// player matrix; otherwise face the target from the player matrix position (+0x90 -> +0x30). The TU's calls of
// 0x8213fbe8 / 0x820d7948 before that have their results overwritten (f1 / v1 reloaded) - not made here.
float *FaceTarget(float *out, BYTE *target, int flag) {
    BYTE *player = Player();
    const BYTE *matrix = *reinterpret_cast<const BYTE *const *>(player + 0x90);
    Vec4 dir;
    if (flag && (!target || Excluded(target))) {
        const BYTE *aim = *reinterpret_cast<const BYTE *const *>(kAimObjPtr);
        const BYTE *sub = *reinterpret_cast<const BYTE *const *>(aim + 0xb0);
        if (kZero < *reinterpret_cast<const float *>(sub + 0x18)) {
            static __declspec(align(16)) const float axis[4] = {0.0f, 0.0f, 1.0f, 0.0f};
            return reinterpret_cast<AxisAngleFn>(kAxisAngle)(out, 0, axis, *reinterpret_cast<const float *>(sub + 8));
        }
        const float *row = reinterpret_cast<const float *>(matrix + 0x10);
        for (int i = 0; i < 4; ++i) dir[i] = row[i] * kMinusOne;
        return reinterpret_cast<FaceFn>(kFace)(out, player, dir);
    }
    if (!target) { Copy4(out, reinterpret_cast<const float *>(player + 0x30)); return out; }   // TU would read 0x20
    const float *t = reinterpret_cast<const float *>(target + 0x20);
    const float *p = reinterpret_cast<const float *>(matrix + 0x30);
    for (int i = 0; i < 3; ++i) dir[i] = t[i] - p[i];
    dir[3] = kZero;
    Normalize3(dir);
    return reinterpret_cast<FaceFn>(kFace)(out, player, dir);
}

// ---------------------------------------------------------------- 0.2: state 1017 slot 4 (TU 0x8245f5a0)
Probe g_p1017 = {"state 1017 slot 4 (TU 0x8245f5a0: pick / face the target)"};
void __cdecl State1017Slot4(void *agent) {
    __try {
        const BYTE *rec = ParamRecord(agent, 0x40f);
        if (!rec) { Hit(g_p1017, -1, "parameter 0x40f missing - nothing done (the TU would read address 4)"); return; }
        const int index = static_cast<signed char>(rec[4]);
        BYTE *gt = GameTracker();
        BYTE *player = *reinterpret_cast<BYTE **>(gt + 0x504);
        float *v1270 = reinterpret_cast<float *>(gt + 0x1270), *v1260 = reinterpret_cast<float *>(gt + 0x1260);
        Vec4 face;
        BYTE *o = nullptr;
        if (((*reinterpret_cast<const DWORD *>(player + 0x1fc) >> 10) & 1) && WeakRef(player)) {
            BYTE *aim = HandleObject(WeakRef(player));
            if (aim && !Excluded(aim)) {
                o = aim;
                Copy4(v1270, FaceTarget(face, o, 0));
                Copy4(v1260, reinterpret_cast<const float *>((Accepts(o, index) ? o : Player()) + 0x20));
                g_gt1284[0] = reinterpret_cast<DWORD>(o);
                g_gt1284[1] = *reinterpret_cast<const DWORD *>(o + 0x44);
                Hit(g_p1017, 1, "aim target 0x%08lx, list index %lu", reinterpret_cast<DWORD>(o), static_cast<DWORD>(index));
                return;
            }
        }
        o = TargeterObject(index);
        if (o) {
            Copy4(v1270, FaceTarget(face, o, 0));
            Copy4(v1260, reinterpret_cast<const float *>(o + 0x20));
            g_gt1284[0] = reinterpret_cast<DWORD>(o);
            g_gt1284[1] = *reinterpret_cast<const DWORD *>(o + 0x44);
            Hit(g_p1017, 2, "targeter (TU index %lu) target 0x%08lx", static_cast<DWORD>(index), reinterpret_cast<DWORD>(o));
            return;
        }
        // no target: face along the current camera's +0x10 matrix row +0x20 ((*0x82efc780)->vtbl[0xe0]()->vtbl[0x38]())
        BYTE *mgr = reinterpret_cast<BYTE *>(kCameraMgr);
        BYTE *cam = (*reinterpret_cast<VGetFn *const *>(mgr))[0xe0 / 4](mgr, 0);
        BYTE *m = (*reinterpret_cast<VGetFn *const *>(cam))[0x38 / 4](cam, 0);
        Vec4 dir;
        Copy4(dir, reinterpret_cast<const float *>(m + 0x20));
        Copy4(v1270, reinterpret_cast<FaceFn>(kFace)(face, Player(), dir));
        g_gt1284[0] = g_gt1284[1] = 0;
        Hit(g_p1017, 0, "no target (TU index %lu): camera direction", static_cast<DWORD>(index));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1017 slot 4: access fault - skipped");
    }
}

// ---------------------------------------------------------------- 0.2: state 244 (TU 0x82464198 / 0x824642a8)
Probe g_p244a = {"state 244 slot 0 (TU 0x82464198: dash to the state-1017 target)"};
Probe g_p244d = {"state 244 slot 3 (TU 0x824642a8: dash update)"};

bool Busy244(const BYTE *gt) {     // gameTracker+0x31c set, byte +0x320 set, (+0x31c)->u16 +0x40 == 2
    if (!gt) return false;
    const BYTE *p = *reinterpret_cast<const BYTE *const *>(gt + 0x31c);
    return p && gt[0x320] && *reinterpret_cast<const WORD *>(p + 0x40) == 2;
}
float Radius(const BYTE *inst) {   // (inst +0x288) -> +0x65c (same on PC: tru+0x2f3ec5)
    const BYTE *p = *reinterpret_cast<const BYTE *const *>(inst + 0x288);
    return *reinterpret_cast<const float *>(p + 0x65c);
}
// point next to the target: target pos + normalise(player pos - target pos) x (radius target + radius player)
void StandOff(float *out, const BYTE *target, const BYTE *player) {
    const float *t = reinterpret_cast<const float *>(target + 0x20), *p = reinterpret_cast<const float *>(player + 0x20);
    Vec4 d;
    for (int i = 0; i < 4; ++i) d[i] = p[i] - t[i];
    Normalize3(d);
    float r = Radius(target) + Radius(player);
    for (int i = 0; i < 4; ++i) out[i] = d[i] * r + t[i];
}

// TU 0x82463fc8(agent, point): n = floor(|point - player| / tuning +0x68); n > 2: +0x1280 = n, frames = n x 100, else
// +0x1280 = 2, frames = 200; channel mode 2 {point, (0, 0, 0, 1), frames} (= tru+0x38d00)
void Dash(void *agent, const float *point) {
    BYTE *chan = Channel(static_cast<BYTE *>(agent));
    const BYTE *tuning = Tuning();
    if (!tuning) { Log(1, "state 244: no tuning (object 858) - skipped (the TU would read address 0x68)"); return; }
    const float *p = reinterpret_cast<const float *>(Player() + 0x20);
    Vec4 d;
    for (int i = 0; i < 4; ++i) d[i] = point[i] - p[i];
    float len = Length3(d);
    int n = static_cast<int>(static_cast<float>(floor(static_cast<double>(len / *reinterpret_cast<const float *>(tuning + 0x68)))));
    float frames = kShortMove;
    if (n > 2) { *Gt1280() = n; frames = static_cast<float>(n) * kHundred; }
    else *Gt1280() = 2;
    Vec4 v;
    Copy4(v, point);
    reinterpret_cast<ChanMode2Fn>(kChanMode2)(chan, 0, v, frames);
}

void __cdecl State244Slot0(void *agent) {
    __try {
        BYTE *gt = GameTracker();
        BYTE *t = HandleObject(g_gt1284);
        if (!t || Busy244(gt)) { Hit(g_p244a, 0, "target 0x%08lx, busy %lu", reinterpret_cast<DWORD>(t), Busy244(gt) ? 1 : 0); return; }
        Vec4 point;
        StandOff(point, t, Player());
        Dash(agent, point);
        Hit(g_p244a, 1, "target 0x%08lx, steps %ld", reinterpret_cast<DWORD>(t), static_cast<DWORD>(*Gt1280()));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 244 slot 0: access fault - skipped");
    }
}

void __cdecl State244Slot3(void *agent) {
    __try {
        BYTE *gt = GameTracker();
        BYTE *chan = Channel(static_cast<BYTE *>(agent));
        if (Busy244(gt)) {     // stop: mode 2 at the instance position, frames = animation +0x28 - 1
            const BYTE *inst = *reinterpret_cast<const BYTE *const *>(static_cast<BYTE *>(agent) + 8);
            float frames = *reinterpret_cast<const float *>(AnimEntry(chan) + 0x28) - kOne;
            reinterpret_cast<ChanMode2Fn>(kChanMode2)(chan, 0, reinterpret_cast<const float *>(inst + 0x20), frames);
            Hit(g_p244d, 2, "busy: stop");
            return;
        }
        BYTE *t = HandleObject(g_gt1284);
        if (!t) return;
        Vec4 point;
        StandOff(point, t, Player());
        const BYTE *tuning = Tuning();
        if (!tuning) return;
        const float *p = reinterpret_cast<const float *>(Player() + 0x20);
        Vec4 d;
        for (int i = 0; i < 4; ++i) d[i] = point[i] - p[i];
        int n = static_cast<int>(static_cast<float>(floor(static_cast<double>(Length3(d) / *reinterpret_cast<const float *>(tuning + 0x68)))));
        if (n <= 0) return;
        const LONG g = *Gt1280();
        // steps still to go: (g x 100 - animation time) x 0.01
        int m = static_cast<int>((static_cast<float>(g) * kHundred - *reinterpret_cast<const float *>(AnimEntry(chan) + 0x28)) * kPerHundred);
        if (m < 0 || n == m) return;
        LONG ng = g - m + n;
        *Gt1280() = ng;
        reinterpret_cast<ChanMode2Fn>(kChanMode2)(chan, 0, point, static_cast<float>(ng) * kHundred);
        Hit(g_p244d, 1, "steps %ld -> %ld (to go %ld)", static_cast<DWORD>(g), static_cast<DWORD>(ng), static_cast<DWORD>(m));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 244 slot 3: access fault - skipped");
    }
}

// ---------------------------------------------------------------- 0.2: state 1007 slots 4 / 5 (TU 0x8245f068)
// doppelganger mode only; outside it the PC handler of slot 4 (tru+0x36d930, retail) runs and slot 5 stays empty
StateFn g_orig1007Slot4 = nullptr;
Probe g_p1007 = {"state 1007 slot 4 / 5 (TU 0x8245f068: face target 5, doppelganger)"};
void State1007(void *agent, int slot) {
    if (!Doppelganger()) { if (slot == 4 && g_orig1007Slot4) g_orig1007Slot4(agent); return; }
    __try {
        BYTE *gt = GameTracker();
        BYTE *player = *reinterpret_cast<BYTE **>(gt + 0x504);
        float *v1260 = reinterpret_cast<float *>(gt + 0x1260), *v1270 = reinterpret_cast<float *>(gt + 0x1270);
        BYTE *t = TargetOf(player, 5);
        if (t && ((*reinterpret_cast<const DWORD *>(player + 0x1fc) >> 10) & 1) && !Accepts(t, 5)) t = TargeterObject(5);
        if (t) {
            const BYTE *inst = *reinterpret_cast<const BYTE *const *>(static_cast<BYTE *>(agent) + 8);
            const float *tp = reinterpret_cast<const float *>(t + 0x20), *ip = reinterpret_cast<const float *>(inst + 0x20);
            float r = Radius(inst);
            if (*reinterpret_cast<const DWORD *>(t + 0x288)) r += Radius(t);
            Vec4 d;
            for (int i = 0; i < 4; ++i) d[i] = ip[i] - tp[i];
            Normalize3(d);
            for (int i = 0; i < 4; ++i) v1260[i] = d[i] * r + tp[i];
            if (IsBooBType(t)) { v1260[2] = ip[2]; v1260[3] = kZero; }   // TU: x, y of the point, z of Lara (+0x28)
        } else {
            Copy4(v1260, reinterpret_cast<const float *>(Player() + 0x20));
        }
        Vec4 face;
        Copy4(v1270, FaceTarget(face, t, 1));
        Hit(g_p1007, t ? 1 : 0, "slot %lu, target 0x%08lx", static_cast<DWORD>(slot), reinterpret_cast<DWORD>(t));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1007 slot %d: access fault - skipped", slot);
    }
}
// ---------------------------------------------------------------- 0.5: states 1019 / 1020 (TU 0x8245f420 / 0x8245f540 /
// 0x8245f398, their TU-new helper 0x8245f2a8 and the channel helpers 0x82463c18 / 0x82463eb8). VMX128 bodies decoded
// with tools/ppc_dis128.py and cross-checked against Xenia's decoder tables by tools/vmx128_xenia_check.py (77 / 77
// words the same; docs Befund-Schattenkampf-0411b.md). TU table 0x82757948: 1019 = {0x8245f420, 0x8245f420, 0,
// 0x8245f540, 0, 0}, 1020 = {0x8245f398, 0x8245f398, 0, 0, 0, 0}. Chart (doppelganger_casual DTP 20212): 1019 in record
// #756 (the combat hub, parent 711), 1020 in #748 (after the finisher #741, activity 1039 = list index 8).
// Behaviour only with [States] Translate1019 / Translate1020 = 1 (default 0, read again at run time at most once per
// second); with 0 the records are still registered ([Probe] States1019=1) and only log what the TU would do - the
// PC had no handler for these ids (the generic default tru+0x381d10 formats a debug text and drops it), so that is
// the PC behaviour.
int g_translate1019 = 0, g_translate1020 = 0;    // [States] Translate1019 / Translate1020
int g_probe1019 = 1;                             // [Probe] States1019: register 1019 / 1020 (log-only when off)
bool g_s1019Ok = false;                          // building blocks below verified
bool g_reg1019 = false, g_reg1020 = false;       // records in Lara's state table copy
void ReadSwitches();                             // 0.4.1 / 0.5, defined with the strike below

typedef void(__fastcall *ChanVecFn)(BYTE *chan, int, const float *vec);                       // tru+0x3e400 / +0x3e370
typedef void(__fastcall *ChanVec2Fn)(BYTE *chan, int, const float *face, const float *point); // tru+0x3e480
typedef void *(__cdecl *AnimFramesFn)(int *out, void *agent);                                 // tru+0x35f3e0
typedef char(__fastcall *ParamBoolFn)(void *node, int, int id, char *out);                    // tru+0x384c20
const DWORD kChanMode1 = 0x00438d70, kChanMode1Anim = 0x0043e400, kChanMode2Anim = 0x0043e370,
            kChanMode3Anim = 0x0043e480, kAnimFrames = 0x0075f3e0, kParamBool = 0x00784c20;

bool CheckState1019Blocks() {
    struct { DWORD at; const char *hex; const char *what; } const s[] = {
        {kChanMode1, "55 8bec 83e4f0 83ec10 d9450c 8bc1 8b4d08 0f2801 0f294010", "channel mode 1 tru+0x38d70 (TU 0x82463eb8 stores)"},
        {0x00438db1, "c7402401000000", "channel mode 1 store"},
        {kChanMode1Anim, "55 8bec 83e4f0 83ec20 8bc1 8b8880000000 8b4924 0fbf5134 0fbf4932", "channel mode 1, animation frames tru+0x3e400"},
        {0x0043e464, "c7402401000000", "channel mode 1 (animation) store"},
        {kChanMode2Anim, "55 8bec 83e4f0 83ec20 f30f100534118400 8bc1 8b8880000000 8b4924 0fbf5134 0fbf4932", "channel mode 2, animation frames tru+0x3e370 (TU 0x820e47f8)"},
        {0x0043e3ec, "c7402402000000", "channel mode 2 (animation) store"},
        {kChanMode3Anim, "55 8bec 83e4f0 83ec10 8bc1 8b8880000000 8b4924 0fbf5134 0fbf4932", "channel mode 3, animation frames tru+0x3e480"},
        {0x0043e4d5, "c7402403000000", "channel mode 3 (animation) store"},
        {kChanMode3, "55 8bec 83e4f0 d94510 8bc1 8b4d08 0f2801 8b4d0c 0f294010", "channel mode 3 tru+0x38dc0"},
        {0x00438df1, "c7402403000000", "channel mode 3 store"},
        {0x00841134, "0000803f", "1.0f [0x841134] (w of the mode-2 vector, TU 0x8207d544)"},
        {0x0084111c, "00000000", "0.0f [0x84111c] (TU 0x8207d538 / zero vector 0x8207db30)"},
        {kAnimFrames, "56 57 8b7c2410 681b010000 681b010000 8bcf e8594b0200 8bc8 e832570200 8bf0 6683 7e0223", "frame count tru+0x35f3e0 (= TU 0x82463af8 flag 0)"},
        {0x0075f42e, "d94004 dc0d08048500", "frame count: time x 0.01 [0x850408] (TU 0x8207dd48)"},
        {0x00850408, "7b14ae47e17a843f", "0.01 (double) [0x850408]"},
        {kParamBool, "8b442404 50 e806ffffff 85c0 7505 32c0 c20800 50 e837ebffff", "bool parameter tru+0x384c20 (TU 0x82484b88 via 0x823d7230)"},
        {0x0075f4ad, "681d010000 681d010000", "tru+0x35f470 reads parameter 0x11d as TU 0x82463c18 / 0x82463eb8"},
    };
    for (const auto &c : s)
        if (!HexAt(c.at, c.hex)) { Log(0, "states 1019 / 1020: %s at 0x%08lx does not match - not registered", c.what, c.at); return false; }
    return true;
}

// rate-limited decision log: every enter (event) at level 1 up to 400 lines per state (then level 2), a tick only
// when its decision changes (level 1, same cap) or every 2 s at level 3
struct Trace { const char *name; volatile LONG calls; LONG lastDecision; DWORD lastTick; volatile LONG lines; };
void TraceLog(Trace &t, bool event, int decision, const char *fmt, ...) {
    LONG n = InterlockedIncrement(&t.calls);
    char detail[400] = "";
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf_s(detail, sizeof(detail), _TRUNCATE, fmt, ap);
    va_end(ap);
    DWORD now = GetTickCount();
    const bool changed = n == 1 || decision != t.lastDecision;
    int level = 0;
    if (event || changed) level = (InterlockedIncrement(&t.lines) <= 400) ? 1 : 2;
    else if (now - t.lastTick >= 2000) level = 3;
    t.lastDecision = decision;
    if (!level) return;
    t.lastTick = now;
    Log(level, "%s (call %ld): %s", t.name, n, detail);
}

// TU 0x82463eb8(agent, v1 face) - TU-new: unless the bool parameter 0x11d is set: n = 0x82463af8(&n, agent, 0)
// (= PC tru+0x35f3e0); n > 0 -> channel +0x10 = face, +0 = zero vector 0x8207db30, +0x20 = (float) n (no x 100 here),
// +0x24 = 1 (= PC tru+0x38d70); else the same with the animation's frame count (= PC tru+0x3e400). Returns the path
// (1 parameter 0x11d set: nothing, 2 n frames, 3 animation frames); apply = 0 only computes it.
int FaceOnly(void *agent, const float *face, bool apply, int *frames) {
    char keep = 0;
    void *node = reinterpret_cast<ParamNodeFn>(kParamNode)(agent, 0, 0x11d);
    if (node) reinterpret_cast<ParamBoolFn>(kParamBool)(node, 0, 0x11d, &keep);
    if (keep) return 1;
    int n = 0;
    reinterpret_cast<AnimFramesFn>(kAnimFrames)(&n, agent);
    *frames = n;
    BYTE *chan = Channel(static_cast<BYTE *>(agent));
    if (n > 0) {
        if (apply) reinterpret_cast<ChanMode2Fn>(kChanMode1)(chan, 0, face, static_cast<float>(n));
        return 2;
    }
    if (apply) reinterpret_cast<ChanVecFn>(kChanMode1Anim)(chan, 0, face);
    return 3;
}

// TU 0x82463c18(agent, v1 face, v2 point) = retail 0x8245f930 (PC tru+0x35f470) plus a TU-new doppelganger branch:
//   n = 0x82463af8(&n, agent, 0) (PC tru+0x35f3e0), flag = bool parameter 0x11d, t = animation entry +0x28 (f29)
//   n > 0: frames = n x 100.0f [0x8207d53c]; frames > t: flag -> mode 2 {point, (0, 0, 0, 1), frames}, else mode 3
//          {face, point, frames} (the retail path); else (TU-new 0x82463d74): no doppelganger -> nothing; the call
//          0x82463af8(.., 1) (parameter 0x11e) only fills a stack word that is overwritten unread - not made; t >= 0
//          (or NaN) -> nothing; else flag -> mode 2 with t + 100, else mode 3 with frames + 100
//   n <= 0: flag -> 0x820e47f8 (mode 2, animation frames = PC tru+0x3e370), else mode 3 with animation frames
//          (PC tru+0x3e480)
// Returns the path (1 / 2 retail mode 2 / 3, 3 TU branch without doppelganger, 4 TU branch t >= 0, 5 / 6 TU branch
// mode 2 / 3, 7 / 8 animation frames mode 2 / 3).
int MoveTo(void *agent, const float *face, const float *point, bool apply, int *frames, float *time) {
    BYTE *chan = Channel(static_cast<BYTE *>(agent));
    int n = 0;
    reinterpret_cast<AnimFramesFn>(kAnimFrames)(&n, agent);
    char flag = 0;
    void *node = reinterpret_cast<ParamNodeFn>(kParamNode)(agent, 0, 0x11d);
    if (node) reinterpret_cast<ParamBoolFn>(kParamBool)(node, 0, 0x11d, &flag);
    const float t = *reinterpret_cast<const float *>(AnimEntry(chan) + 0x28);
    *frames = n;
    *time = t;
    if (n > 0) {
        const float f = static_cast<float>(n) * kHundred;
        if (f > t) {
            if (flag) { if (apply) reinterpret_cast<ChanMode2Fn>(kChanMode2)(chan, 0, point, f); return 1; }
            if (apply) reinterpret_cast<ChanMode3Fn>(kChanMode3)(chan, 0, face, point, f);
            return 2;
        }
        if (!Doppelganger()) return 3;
        if (!(t < kZero)) return 4;
        if (flag) { if (apply) reinterpret_cast<ChanMode2Fn>(kChanMode2)(chan, 0, point, t + kHundred); return 5; }
        if (apply) reinterpret_cast<ChanMode3Fn>(kChanMode3)(chan, 0, face, point, f + kHundred);
        return 6;
    }
    if (flag) { if (apply) reinterpret_cast<ChanVecFn>(kChanMode2Anim)(chan, 0, point); return 7; }
    if (apply) reinterpret_cast<ChanVec2Fn>(kChanMode3Anim)(chan, 0, face, point);
    return 8;
}

// TU 0x8245f2a8(o, agent) - TU-new: point next to o seen from the agent's instance, facing o, then 0x82463c18:
//   d = instance +0x20 - o +0x20 (vsubfp128, 4 lanes); r = radius(instance) + (o +0x288 ? radius(o) : 0)
//   face = 0x82457b28(o, 1); d = d x rsqrt(dot3(d, d)) (vrsqrtefp128 + one Newton step, vsel: 0 for a zero length)
//   point = d x r + o +0x20 (vmaddcfp128); 0x82463c18(agent, face, point)
int StandOffMove(BYTE *o, void *agent, bool apply, char *text, size_t size) {
    if (!o || !agent) { _snprintf_s(text, size, _TRUNCATE, "no object"); return 0; }
    const BYTE *inst = *reinterpret_cast<const BYTE *const *>(static_cast<BYTE *>(agent) + 8);
    const float *ip = reinterpret_cast<const float *>(inst + 0x20), *op = reinterpret_cast<const float *>(o + 0x20);
    __declspec(align(16)) float d[4], point[4], face[4];
    for (int i = 0; i < 4; ++i) d[i] = ip[i] - op[i];
    float r = Radius(inst);
    if (*reinterpret_cast<const DWORD *>(o + 0x288)) r = Radius(o) + r;
    FaceTarget(face, o, 1);
    Normalize3(d);
    for (int i = 0; i < 4; ++i) point[i] = d[i] * r + op[i];
    int frames = 0;
    float time = 0.0f;
    const int path = MoveTo(agent, face, point, apply, &frames, &time);
    _snprintf_s(text, size, _TRUNCATE, "object 0x%08lx, point %.1f %.1f %.1f (radius %.1f), frame count %d, animation "
                "+0x28 %.1f, move path %d (1 / 2 mode 2 / 3, 3 / 4 TU branch skipped, 5 / 6 TU branch, 7 / 8 animation "
                "frames)", reinterpret_cast<DWORD>(o), point[0], point[1], point[2], r, frames, time, path);
    return path;
}

// TU meter +0x20 / +0x24 (handle {object, id} of 1019's target). Only 1019 reads / writes it
// (tools/ppc_ptr_field_users.py: 5 uses, all in 0x8245f420 / 0x8245f540; the meter methods called with the meter in
// r3 use neither field); the TU zeroes it when it builds the meter in the player init (0x82409c78 in 0x82409418, called
// from 0x82412ca0, which also allocates the target list). Kept here; a new target list ([0xfadfac] changed, PC player
// init tru+0x322631) counts as that new meter. "meter present" (TU gameTracker+0x508 != 0) = TruShadowPower's meter
// interface found.
DWORD g_m1019[2] = {0, 0};
BYTE **g_m1019List = nullptr;
DWORD *Handle1019() {
    if (g_m1019List != List()) { g_m1019[0] = g_m1019[1] = 0; g_m1019List = List(); }
    return g_m1019;
}

Trace g_t1019e = {"state 1019 slot 0 / 1 (TU 0x8245f420: target 5 into the meter, step next to it)"};
Trace g_t1019t = {"state 1019 slot 3 (TU 0x8245f540: follow the meter target)"};
Trace g_t1020 = {"state 1020 slot 0 / 1 (TU 0x8245f398: step next to the target of the list index of parameter 0x40f)"};
volatile LONG g_ticks1019 = 0;

void State1019Enter(void *agent, int slot) {
    ReadSwitches();
    const bool apply = g_translate1019 != 0;
    const LONG ticks = InterlockedExchange(&g_ticks1019, 0);
    char text[300] = "";
    __try {
        BYTE *gt = GameTracker();
        BYTE *player = *reinterpret_cast<BYTE **>(gt + 0x504);
        BYTE *t = TargetOf(player, 5);
        const int dg = Doppelganger();
        const bool meter = dg && Meter() != nullptr;
        DWORD *h = Handle1019();
        if (meter && apply) h[0] = h[1] = 0;
        int why = 0;      // 1 not doppelganger, 2 no target 5, 3 0x4f / 0xb00b target, 4 aiming, not accepted by targeter 5
        if (!dg) why = 1;
        else if (!t) why = 2;
        else if (IsBooBType(t)) why = 3;
        else if (((*reinterpret_cast<const DWORD *>(player + 0x1fc) >> 10) & 1) && !Accepts(t, 5)) why = 4;
        if (!why) {
            const int path = StandOffMove(t, agent, apply, text, sizeof(text));
            if (meter && apply) { h[0] = reinterpret_cast<DWORD>(t); h[1] = *reinterpret_cast<const DWORD *>(t + 0x44); }
            TraceLog(g_t1019e, true, 10 + path, "%s slot %d, %lu ticks since the last enter: target 5 0x%08lx -> step next "
                     "to it (0x8245f2a8), meter handle %s; %s", apply ? "ON" : "off (would)", slot, ticks,
                     reinterpret_cast<DWORD>(t), meter ? (apply ? "set" : "would be set") : "none (no meter interface)", text);
            return;
        }
        __declspec(align(16)) float face[4];
        FaceTarget(face, t, 1);
        int frames = 0;
        const int path = FaceOnly(agent, face, apply, &frames);
        TraceLog(g_t1019e, true, why * 10 + path, "%s slot %d, %lu ticks since the last enter: target 5 0x%08lx, reason "
                 "%d (1 not doppelganger, 2 no target, 3 0x4f / 0xb00b target, 4 aiming, not accepted) -> face only "
                 "(0x82457b28 + 0x82463eb8), path %d (1 parameter 0x11d: nothing, 2 frames %d, 3 animation frames), "
                 "meter handle %s", apply ? "ON" : "off (would)", slot, ticks, reinterpret_cast<DWORD>(t), why, path,
                 frames, meter ? (apply ? "cleared" : "would be cleared") : "none");
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1019 slot %d: access fault - skipped", slot);
    }
}
void __cdecl State1019Slot0(void *agent) { State1019Enter(agent, 0); }
void __cdecl State1019Slot1(void *agent) { State1019Enter(agent, 1); }

void __cdecl State1019Slot3(void *agent) {
    InterlockedIncrement(&g_ticks1019);
    ReadSwitches();
    const bool apply = g_translate1019 != 0;
    char text[300] = "";
    __try {
        const int dg = Doppelganger();
        const bool meter = Meter() != nullptr;
        BYTE *o = HandleObject(Handle1019());
        if (!dg || !meter || !o) {
            TraceLog(g_t1019t, false, !dg ? 1 : !meter ? 2 : 3, "%s nothing (%s)", apply ? "ON:" : "off:",
                     !dg ? "not doppelganger" : !meter ? "no meter interface" : "no valid meter target");
            return;
        }
        const int path = StandOffMove(o, agent, apply, text, sizeof(text));
        TraceLog(g_t1019t, false, 10 + path, "%s follow the meter target: %s", apply ? "ON" : "off (would)", text);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1019 slot 3: access fault - skipped");
    }
}

void State1020(void *agent, int slot) {
    ReadSwitches();
    const bool apply = g_translate1020 != 0;
    char text[300] = "";
    __try {
        const BYTE *rec = ParamRecord(agent, 0x40f);
        if (!rec) { TraceLog(g_t1020, true, 1, "slot %d: parameter 0x40f missing - nothing (the TU would read address 4)", slot); return; }
        const int index = static_cast<signed char>(rec[4]);
        BYTE **list = List();
        if (index < 0 || index >= kTuTargeters || !list || !list[SlotOf(index)]) {
            TraceLog(g_t1020, true, 2, "slot %d: list index %d - no targeter (the TU reads the entry unchecked) - nothing",
                     slot, index);
            return;
        }
        DWORD *h = reinterpret_cast<TargeterTargetFn>(kTargeterTarget)(list[SlotOf(index)], 0);
        BYTE *o = HandleObject(h);
        if (!o) {
            TraceLog(g_t1020, true, 3, "slot %d: targeter (TU index %d) %s - nothing", slot, index,
                     h ? "handle no longer valid" : "has no target");
            return;
        }
        const int path = StandOffMove(o, agent, apply, text, sizeof(text));
        TraceLog(g_t1020, true, 10 + path, "%s slot %d: targeter (TU index %d) -> step next to it (0x8245f2a8): %s",
                 apply ? "ON" : "off (would)", slot, index, text);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1020 slot %d: access fault - skipped", slot);
    }
}
void __cdecl State1020Slot0(void *agent) { State1020(agent, 0); }
void __cdecl State1020Slot1(void *agent) { State1020(agent, 1); }

// ---------------------------------------------------------------- 0.5.1: states 231 and 1004 (TU table differences)
// Slot meaning (PC record setter tru+0x3843a0 / enter loop tru+0x385a30): slot 0 = enter; slot 1 = enter while the
// state was already active in the previous chart record (getter tru+0x384790, called when tru+0x381dc0(previous
// record, id) is true); a null slot is skipped (`test eax, eax` before the call), so a handler that does nothing is
// the same as no handler.
// 231: TU {0x82464160, 0x82464160, 0, ..} = 0x82463c18(agent, v1 = gameTracker+0x1270, v2 = gameTracker+0x1260) (the
//      helper with the doppelganger branch, MoveTo above); PC {tru+0x35f550, 0, ..} = tru+0x35f470 (retail 0x8245f930,
//      without the branch). Slot 0 differs from the PC only on MoveTo paths 3..6 (frames n x 100 <= animation +0x28:
//      the TU then does nothing outside doppelganger mode and runs its branch inside); slot 1 is TU-only.
// 1004: TU {0x8245efc8, 0x8245efc8, 0x8245f050, ..}: 0x8245efc8 = unless the bool parameter 0x415 is set: clear the
//      8-slot hit list player +0xa4 (the list state 1013 fills); then 0x823dfc98(player) (moved-equal = retail
//      0x823ddaf8 = PC tru+0x3036c0). PC {tru+0x35e020, 0, tru+0x35e060, ..}: tru+0x35e020 = clear (tru+0x2e6950) +
//      print stub + tru+0x3036c0 always (= retail 0x8245ba70); slot 2 is the same on all three (player +0xc4 = 0).
// Switches [States] Translate231Slot0 / Translate231Slot1 / Translate1004 (default 0, read again at run time): 0 = the
// PC handler runs (slot 1: nothing) and a line says what the TU would do differently ("off (would)").
int g_translate231s0 = 0, g_translate231s1 = 0, g_translate1004 = 0;
int g_probe231 = 1;                              // [Probe] States231And1004: wrap / add the slots at all
bool g_s231Ok = false, g_reg231 = false, g_reg1004 = false;
const DWORD kState231Pc = 0x0075f550, kState1004Pc = 0x0075e020, kState1004PcSlot2 = 0x0075e060,
            kClearHitList = 0x006e6950, kAfter1004 = 0x007036c0;
typedef void(__fastcall *PlayerFn)(BYTE *player, int);    // tru+0x2e6950 / tru+0x3036c0 (thiscall, no arguments)
StateFn g_orig231 = nullptr, g_orig1004 = nullptr;

bool CheckState231Blocks() {
    struct { DWORD at; const char *hex; const char *what; } const s[] = {
        {kState231Pc, "8b442404 50 a158dbfa00 8d8860120000 51 0570120000 50 e804ffffff 83c40c c3",
         "state 231 slot 0 tru+0x35f550 (tru+0x35f470(gT+0x1270, gT+0x1260, agent))"},
        {kState1004Pc, "a158dbfa00 8b8804050000 e82089f8ff 8b0d58dbfa00 8b9104050000 8b0a e85d77eeff a158dbfa00 "
                       "8b8804050000 e96d56faff", "state 1004 slot 0 tru+0x35e020"},
        {kState1004PcSlot2, "a158dbfa00 8b8804050000 c781c400000000000000 c3", "state 1004 slot 2 tru+0x35e060"},
        {kClearHitList, "33c0 8981a4000000 8981a8000000 8981ac000000 8981b0000000 8981b4000000 8981b8000000 "
                        "8981bc000000 8981c0000000 c3", "hit list clear tru+0x2e6950 (player +0xa4..+0xc0)"},
        {kAfter1004, "57 8bf9 8b470c 85c0 7457 8b08 85c9 751c 834004ff", "tru+0x3036c0 (TU 0x823dfc98)"},
        {0x006457a0, "c3", "print stub tru+0x2457a0"},
    };
    for (const auto &c : s)
        if (!HexAt(c.at, c.hex)) { Log(0, "states 231 / 1004: %s at 0x%08lx does not match - not wrapped", c.what, c.at); return false; }
    return true;
}

Trace g_t231[2] = {{"state 231 slot 0 (TU 0x82464160 = 0x82463c18 to gameTracker+0x1260, facing +0x1270)"},
                   {"state 231 slot 1 (TU 0x82464160, TU-only slot: re-enter)"}};
void State231(void *agent, int slot) {
    ReadSwitches();
    const bool apply = slot == 0 ? g_translate231s0 != 0 : g_translate231s1 != 0;
    bool runPc = !apply && slot == 0;
    __try {
        BYTE *gt = GameTracker();
        __declspec(align(16)) float face[4], point[4];
        Copy4(face, reinterpret_cast<const float *>(gt + 0x1270));
        Copy4(point, reinterpret_cast<const float *>(gt + 0x1260));
        int frames = 0;
        float time = 0.0f;
        const int path = MoveTo(agent, face, point, apply, &frames, &time);
        const bool differs = slot == 1 || (path >= 3 && path <= 6);
        if (apply || differs)
            TraceLog(g_t231[slot], true, path, "%s point %.1f %.1f %.1f, frame count %d, animation +0x28 %.1f, move path %d "
                     "(1 / 2 mode 2 / 3 as the PC, 3 / 4 TU: nothing, 5 / 6 TU doppelganger branch, 7 / 8 animation frames)%s",
                     apply ? "ON:" : "off (would):", point[0], point[1], point[2], frames, time, path,
                     runPc ? " - the PC handler runs instead" : "");
        else if (g_logLevel >= 2)
            TraceLog(g_t231[slot], false, path, "off: move path %d = the PC path", path);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 231 slot %d: access fault - %s", slot, runPc ? "PC handler runs" : "skipped");
    }
    if (runPc && g_orig231) g_orig231(agent);
}
void __cdecl State231Slot0(void *agent) { State231(agent, 0); }
void __cdecl State231Slot1(void *agent) { State231(agent, 1); }

Trace g_t1004[2] = {{"state 1004 slot 0 (TU 0x8245efc8: hit list +0xa4 kept with parameter 0x415)"},
                    {"state 1004 slot 1 (TU 0x8245efc8, TU-only slot: re-enter)"}};
void State1004(void *agent, int slot) {
    ReadSwitches();
    const bool apply = g_translate1004 != 0;
    char keep = 0;
    BYTE *player = nullptr;
    DWORD used = 0;
    __try {
        void *node = reinterpret_cast<ParamNodeFn>(kParamNode)(agent, 0, 0x415);
        if (node) reinterpret_cast<ParamBoolFn>(kParamBool)(node, 0, 0x415, &keep);
        player = *reinterpret_cast<BYTE **>(GameTracker() + 0x504);
        for (int k = 0; k < 8; ++k)
            if (reinterpret_cast<const DWORD *>(player + 0xa4)[k]) ++used;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1004 slot %d: access fault reading parameter 0x415 / the hit list", slot);
        player = nullptr;
    }
    // TU: keep -> the list stays; slot 1 runs the same function. PC: slot 0 always clears, slot 1 nothing.
    const bool differs = slot == 1 || keep;
    if (apply || differs)
        TraceLog(g_t1004[slot], true, (slot == 1 ? 10 : 0) + (keep ? 1 : 0), "%s parameter 0x415 %d, hit list slots used "
                 "%lu -> TU: %s, then tru+0x3036c0 (TU 0x823dfc98)%s", apply ? "ON:" : "off (would):", keep ? 1 : 0, used,
                 keep ? "list kept" : "list cleared",
                 apply ? "" : slot == 0 ? " - PC: list cleared (tru+0x35e020 runs)" : " - PC: no slot 1, nothing runs");
    if (!apply || !player) {
        if (slot == 0 && g_orig1004) g_orig1004(agent);
        return;
    }
    __try {
        if (!keep) reinterpret_cast<PlayerFn>(kClearHitList)(player, 0);
        reinterpret_cast<PlayerFn>(kAfter1004)(player, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1004 slot %d: access fault in the translation", slot);
    }
}
void __cdecl State1004Slot0(void *agent) { State1004(agent, 0); }
void __cdecl State1004Slot1(void *agent) { State1004(agent, 1); }

// ---------------------------------------------------------------- 0.3: state 1013 slot 0 probe (finisher)
// TU 0x823e0a88 (= retail 0x823de6d0 = PC tru+0x31d600 via tru+0x35e090): the finisher on a target (query 0x162
// animation, 0x80-byte hit record, message 0xf4). The TU takes the target from targeter 9 in doppelganger mode
// (0x823e0ac8..0x823e0b0c, else 0x823dd260(player, 5)) and writes the hit record +0x68 from the attack data (player
// +0xc4) +1 instead of retail's 0xff (0x823e0dc4 / 0x823e0e4c). Not translated yet (VMX body); this probe only logs
// what the TU would hit and what the PC hits, then runs the PC handler.
const DWORD kState1013Pc = 0x0075e090;
const char *const kState1013PcHex = "a158dbfa00 8b8804050000 e960f5fbff";
StateFn g_orig1013 = nullptr;
int g_probe1013 = 1;               // [Probe] State1013
Probe g_p1013 = {"state 1013 slot 0 (finisher, PC tru+0x31d600; TU 0x823e0a88)"};
void __cdecl State1013Slot0(void *agent) {
    __try {
        int dg = Doppelganger();
        BYTE *player = *reinterpret_cast<BYTE **>(GameTracker() + 0x504);
        BYTE *pcTarget = TargetOf(player, 5);
        BYTE *tuTarget = dg ? (g_listOk ? TargeterObject(9) : nullptr) : pcTarget;
        const BYTE *attack = *reinterpret_cast<const BYTE *const *>(player + 0xc4);
        Hit(g_p1013, dg, "PC target (targeter 5) 0x%08lx, TU target (doppelganger: targeter 9) 0x%08lx, attack data "
                         "0x%08lx", reinterpret_cast<DWORD>(pcTarget), reinterpret_cast<DWORD>(tuTarget),
            reinterpret_cast<DWORD>(attack));
        if (dg && attack) Log(2, "state 1013: attack data +1 (TU hit record +0x68) = %u, retail 0xff", attack[1]);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    if (g_orig1013) g_orig1013(agent);
}

// ---------------------------------------------------------------- 0.4: state 1013 slot 0, doppelganger branch
// TU 0x823e0a88 = retail 0x823de6d0 = PC tru+0x31d600 except (Befund-Schattenkampf section 10 / 11):
//   1. 0x823e0ac8..0x823e0b0c: doppelganger -> the handle of targeter 9 (if non-null) instead of 0x823dd260(player, 5)
//   2. 0x823e0bac..0x823e0be4: the target goes into the player's 8-slot hit list +0xa4 (first empty slot, unless
//      present) - the same loop retail has in another attack function (retail 0x823defd4 / TU 0x823e1530)
//   3. 0x823e0dc4 / 0x823e0e4c: hit record +0x68 = attack data (player +0xc4) byte +1, retail 0xff
//   4. 0x823e0e84: message record +0x3c = 0 (retail leaves it)
// +0x34 (gameTracker+0x858 -> +0x50 -> +8, retail r24 = TU r23 = PC ebx) and +0x38 (hit record) are the same on all.
// The PC function runs; three call / push sites in it are redirected (only with [States] Translate1013=1):
//   tru+0x31d610 call tru+0x31c9a0 (target, 1.), tru+0x31d825 push 0xff (22nd argument of the hit record builder
//   tru+0x23c9b0 = record +0x68, 3.), tru+0x31d895 call tru+0x245de0 (message record, 2. + 4.).
// Outside doppelganger mode every site does exactly what the PC code did.
// 0.4.1: the three sites are patched at the start whenever their byte checks pass (also with Translate1013=0, then
// every site runs the PC path - the same as outside doppelganger mode), so the switch can be turned on / off at run
// time (ReadSwitches, at most once per second; the decision is taken per call at the target site).
int g_translate1013 = 0;           // [States] Translate1013
bool g_t1013Patched = false;       // 0.4.1: the three sites are redirected
volatile LONG g_t1013Active = 0;   // set per call of tru+0x31d600 by the target site
void ReadSwitches();               // 0.4.1, defined with the strike below
DWORD g_back1013 = 0x0071d82a;
Probe g_p1013t = {"state 1013 translation (TU 0x823e0a88 doppelganger branch)"};
typedef DWORD *(__fastcall *TargetInnerFn)(BYTE *player, int, int index);     // tru+0x31c9a0 = TU 0x823dd138
typedef BYTE *(__cdecl *Record1013Fn)(BYTE *target, BYTE *player, const float *pos, const float *rot, float frames,
                                      DWORD x34, BYTE *hit);                    // tru+0x245de0

DWORD *__fastcall Target1013(BYTE *player, int, int index) {
    DWORD *h = reinterpret_cast<TargetInnerFn>(0x0071c9a0)(player, 0, index);
    ReadSwitches();
    LONG active = (g_translate1013 && g_listOk && Doppelganger()) ? 1 : 0;
    InterlockedExchange(&g_t1013Active, active);
    if (!active) return h;
    __try {
        BYTE **list = List();
        DWORD *h9 = (list && list[9]) ? reinterpret_cast<TargeterTargetFn>(kTargeterTarget)(list[9], 0) : nullptr;
        if (h9) {
            Hit(g_p1013t, 1, "target of targeter 9: 0x%08lx (PC targeter 5: 0x%08lx)",
                reinterpret_cast<DWORD>(HandleObject(h9)), reinterpret_cast<DWORD>(HandleObject(h)));
            return h9;
        }
        Hit(g_p1013t, 0, "targeter 9 has no handle - the targeter-5 target 0x%08lx stays (as the TU)",
            reinterpret_cast<DWORD>(HandleObject(h)));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1013 translation: access fault at the target - PC target kept");
    }
    return h;
}

DWORD __cdecl Class1013() {
    if (!g_t1013Active) return 0xff;
    DWORD v = 0xff;
    __try {
        const BYTE *player = *reinterpret_cast<const BYTE *const *>(GameTracker() + 0x504);
        const BYTE *attack = *reinterpret_cast<const BYTE *const *>(player + 0xc4);
        v = attack[1];
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        v = 0xff;
    }
    Log(2, "state 1013 translation: hit record +0x68 = %lu (attack data +1), PC 0xff", v);
    return v;
}

// replaces `push 0xff` at tru+0x31d825 (eax = the facing just returned, ecx / edx / xmm dead there)
__declspec(naked) void PushClass1013() {
    __asm {
        push eax
        call Class1013
        xchg eax, [esp]
        jmp dword ptr [g_back1013]
    }
}

BYTE *__cdecl Record1013(BYTE *target, BYTE *player, const float *pos, const float *rot, float frames, DWORD x34,
                         BYTE *hit) {
    BYTE *rec = reinterpret_cast<Record1013Fn>(0x00645de0)(target, player, pos, rot, frames, x34, hit);
    if (!g_t1013Active) return rec;
    __try {
        if (rec) *reinterpret_cast<DWORD *>(rec + 0x3c) = 0;
        BYTE *p = *reinterpret_cast<BYTE **>(GameTracker() + 0x504);
        DWORD *slots = reinterpret_cast<DWORD *>(p + 0xa4);
        int k = 0;
        for (; k < 8; ++k) {
            if (slots[k] == 0) { slots[k] = reinterpret_cast<DWORD>(target); break; }
            if (slots[k] == reinterpret_cast<DWORD>(target)) break;
        }
        Log(1, "state 1013 translation: message 0xf4 to 0x%08lx, hit list slot %d, record +0x3c = 0",
            reinterpret_cast<DWORD>(target), k);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1013 translation: access fault after the message record");
    }
    InterlockedExchange(&g_t1013Active, 0);
    return rec;
}

bool WriteCall(DWORD at, const void *to) {
    BYTE c[5] = {0xe8};
    DWORD rel = reinterpret_cast<DWORD>(to) - (at + 5);
    memcpy(c + 1, &rel, 4);
    return WriteCode(at, c, 5);
}

void SetupTranslate1013() {
    if (!g_listOk || !g_blocksOk) {
        Log(g_translate1013 ? 0 : 1, "state 1013 translation: target list / building blocks not active - off%s",
            g_translate1013 ? "" : " ([States] Translate1013=0; the switch has no effect in this run)");
        g_translate1013 = 0;
        return;
    }
    struct { DWORD at; const char *hex; const char *what; } const s[] = {
        {0x0071d600, "55 8bec 83e4f0 83ec64 53 56 57 6a05 8bf9 e88bf3ffff 85c0", "tru+0x31d600 head / target call"},
        {0x0071d825, "68ff000000 6a00 6a00 0f2800 8b87c4000000", "push 0xff (hit record +0x68) / attack data +0xc4"},
        {0x0071d895, "e84685f2ff 50 68f4000000 56 e8aa5ee9ff", "message record call / message 0xf4"},
        {0x0063ca36, "8b542460 88486f 8b4c243c 83c404 85c9 895068", "hit record builder: 22nd argument -> +0x68"},
        {0x00645de0, "55 8bec 83e4f0 6a40 e8", "message record builder tru+0x245de0"},
        {0x00645e2b, "894834 895038", "message record +0x34 / +0x38"},
    };
    for (const auto &c : s)
        if (!HexAt(c.at, c.hex)) { Log(0, "state 1013 translation: %s at 0x%08lx does not match - off", c.what, c.at); g_translate1013 = 0; return; }
    if (!WriteCall(0x0071d610, reinterpret_cast<const void *>(&Target1013)) ||
        !WriteJump(0x0071d825, reinterpret_cast<const void *>(&PushClass1013)) ||
        !WriteCall(0x0071d895, reinterpret_cast<const void *>(&Record1013))) {
        Log(0, "state 1013 translation: patch failed - restart without the plugin");
        return;
    }
    g_t1013Patched = true;
    if (g_translate1013)
        Log(1, "state 1013 translation: ON (tru+0x31d610 target, tru+0x31d825 hit class, tru+0x31d895 message record; "
               "doppelganger mode only; [States] Translate1013 read again at most once per second)");
    else
        Log(1, "state 1013 translation: off ([States] Translate1013=0) - sites tru+0x31d610 / +0x31d825 / +0x31d895 "
               "patched but they run the PC path; the switch turns it on at run time (read again at most once per second)");
}

void __cdecl State1007Slot4(void *agent) { State1007(agent, 4); }
void __cdecl State1007Slot5(void *agent) { State1007(agent, 5); }

// ---------------------------------------------------------------- 0.2: the shadow strike (state 1014, doppelganger)
// TU meter fields the strike owns (+0x15 look latch, +0x18 / +0x1c target handle, +0x28 strike count, +0x2c
// frames) are kept here; flags / value / requests / drain come from TruShadowPower (TruShadowPowerMeterApi).
struct Strike { BYTE latch; DWORD target[2]; LONG count; float frames; } g_strike = {0, {0, 0}, 0, 0.0f};
int g_strikeTranslate = 0;          // [Strike] Translate
Probe g_pStrike = {"shadow strike (TU 0x823d86a8: placement + message 0xbe)"};

// ---------------------------------------------------------------- 0.4.1: the two switches at run time
// TruMenu's TO TEST switches (sc-strike, sc-translate1013) write TruShadowCombat.ini at once. [Strike] Translate and
// [States] Translate1013 are read again from it at most once per second, from the code they switch (state 1014
// slots, the 1013 target site) - so a change counts from the next strike / finisher. Nothing new is built: they
// only turn the code on / off that the start installed and byte-checked (1014 wrappers, 1013 sites); without it a
// change is logged as "no effect". A strike that runs keeps the translation until its end (slot 2 clears meter flag
// 2) - else its end would never run. A missing key / file keeps the current value.
volatile LONG g_switchTick = 0;
int g_strikeWaitLogged = 0;

void ReadSwitches() {
    if (!g_iniPath[0]) return;
    const LONG now = static_cast<LONG>(GetTickCount() | 1);
    const LONG last = g_switchTick;
    if (static_cast<DWORD>(now) - static_cast<DWORD>(last) < 1000) return;
    if (InterlockedCompareExchange(&g_switchTick, now, last) != last) return;
    int strike = GetPrivateProfileIntA("Strike", "Translate", g_strikeTranslate, g_iniPath) ? 1 : 0;
    if (strike != (g_strikeTranslate ? 1 : 0)) {
        const TruShadowPowerMeter *m = g_strikeTranslate ? g_meter : nullptr;
        if (m && (*m->flags & 2)) {
            if (!g_strikeWaitLogged)
                Log(1, "0.4.1 switch: [Strike] Translate %d -> %d waits - a translated strike runs (meter flags 0x%03lx)",
                    g_strikeTranslate ? 1 : 0, strike, *m->flags);
            g_strikeWaitLogged = 1;
        } else {
            Log(1, "0.4.1 switch: [Strike] Translate %d -> %d (read again from TruShadowCombat.ini)%s",
                g_strikeTranslate ? 1 : 0, strike,
                !g_orig1014[0] ? " - state 1014 not wrapped at the start: no effect in this run"
                : (strike && !g_strikeOk) ? " - strike building blocks not verified: no effect in this run" : "");
            g_strikeTranslate = strike;
            g_strikeWaitLogged = 0;
        }
    }
    int t1013 = GetPrivateProfileIntA("States", "Translate1013", g_translate1013, g_iniPath) ? 1 : 0;
    if (t1013 != (g_translate1013 ? 1 : 0)) {
        Log(1, "0.4.1 switch: [States] Translate1013 %d -> %d (read again from TruShadowCombat.ini)%s",
            g_translate1013 ? 1 : 0, t1013,
            g_t1013Patched ? "" : " - the 1013 sites are not patched: no effect in this run");
        g_translate1013 = t1013;      // only the patched target site reads it
    }
    // 0.5: states 1019 / 1020 (the handlers are registered at the start whenever their checks pass; the switch only
    // decides whether they act or only log)
    int t1019 = GetPrivateProfileIntA("States", "Translate1019", g_translate1019, g_iniPath) ? 1 : 0;
    if (t1019 != (g_translate1019 ? 1 : 0)) {
        Log(1, "0.5 switch: [States] Translate1019 %d -> %d (read again from TruShadowCombat.ini)%s", g_translate1019 ? 1 : 0,
            t1019, g_reg1019 ? "" : " - state 1019 not registered (yet): no effect until it is");
        g_translate1019 = t1019;
    }
    int t1020 = GetPrivateProfileIntA("States", "Translate1020", g_translate1020, g_iniPath) ? 1 : 0;
    if (t1020 != (g_translate1020 ? 1 : 0)) {
        Log(1, "0.5 switch: [States] Translate1020 %d -> %d (read again from TruShadowCombat.ini)%s", g_translate1020 ? 1 : 0,
            t1020, g_reg1020 ? "" : " - state 1020 not registered (yet): no effect until it is");
        g_translate1020 = t1020;
    }
    // 0.5.1: states 231 / 1004
    struct { const char *key; int *value; bool *reg; } const sw[3] = {
        {"Translate231Slot0", &g_translate231s0, &g_reg231}, {"Translate231Slot1", &g_translate231s1, &g_reg231},
        {"Translate1004", &g_translate1004, &g_reg1004}};
    for (const auto &s : sw) {
        int v = GetPrivateProfileIntA("States", s.key, *s.value, g_iniPath) ? 1 : 0;
        if (v == (*s.value ? 1 : 0)) continue;
        Log(1, "0.5.1 switch: [States] %s %d -> %d (read again from TruShadowCombat.ini)%s", s.key, *s.value ? 1 : 0, v,
            *s.reg ? "" : " - state not wrapped (yet): no effect until it is");
        *s.value = v;
    }
}

// TU 0x823d86a8(meter, target, arg) - the retail finisher block (PC twin tru+0x31d40e..+0x31d5dd), meter storage
bool StrikeAt(BYTE *target, int arg) {
    int anim = reinterpret_cast<QueryArgFn>(kQueryArg)(target, 0x165, reinterpret_cast<void *>(arg));
    if (!anim) return false;
    BYTE *player = Player();
    BYTE *chan = *reinterpret_cast<BYTE **>(*reinterpret_cast<BYTE **>(player + 0x280) + 0x14);
    if (!chan) return false;
    reinterpret_cast<AnimSetFn>(kAnimSet)(chan, 0, anim, *reinterpret_cast<void **>(target + 0x10));
    Vec4 dir, point, face, tface, neg;
    const float *tp = reinterpret_cast<const float *>(target + 0x20), *pp = reinterpret_cast<const float *>(player + 0x20);
    for (int i = 0; i < 3; ++i) dir[i] = tp[i] - pp[i];
    dir[3] = kZero;
    Normalize3(dir);
    float dist = static_cast<float>(static_cast<DWORD>(reinterpret_cast<QueryArgFn>(kQueryArg)(target, 0x166, reinterpret_cast<void *>(arg))));
    float frames = static_cast<float>(static_cast<DWORD>(reinterpret_cast<QueryArgFn>(kQueryArg)(target, 0x167, reinterpret_cast<void *>(arg))));
    for (int i = 0; i < 4; ++i) point[i] = tp[i] - dir[i] * dist;
    reinterpret_cast<FaceFn>(kFace)(face, player, dir);
    if (kZero < frames) {
        // TU 0x823d8860..0x823d8880: channel {+0x10 face, +0 point, +0x24 3, +0x20 frames x 100}, meter +0x2c = frames
        reinterpret_cast<ChanMode3Fn>(kChanMode3)(chan, 0, face, point, frames * kHundred);
        g_strike.frames = frames;
    } else {
        Copy4(reinterpret_cast<float *>(player + 0x20), point);
        Vec4 rot;
        reinterpret_cast<ToRotFn>(kToRot)(face, 0, rot);
        Copy4(reinterpret_cast<float *>(player + 0x30), rot);
        g_strike.frames = kZero;
    }
    for (int i = 0; i < 4; ++i) neg[i] = dir[i] * kMinusOne;
    reinterpret_cast<FaceFn>(kFace)(tface, target, neg);
    // TU 0x823d88b4 reloads v126 = target +0x20: the record carries the target's own position (as the PC twin
    // tru+0x31d571), its facing towards the player, the frames and the argument
    Vec4 tpos;
    Copy4(tpos, tp);
    BYTE *record = reinterpret_cast<RecordFn>(kRecord)(target, player, tpos, tface, frames);
    if (record) *reinterpret_cast<int *>(record + 0x34) = arg;          // TU record +0x34 = arg
    if (*reinterpret_cast<void **>(target + 0x120)) reinterpret_cast<MessageFn>(kMessage)(target, 0xbe, record);
    Hit(g_pStrike, 1, "target 0x%08lx, animation %lu, frames %lu", reinterpret_cast<DWORD>(target), static_cast<DWORD>(anim),
        static_cast<DWORD>(frames));
    return true;
}

// TU 0x823d8978 (slot 0)
void StrikeStart(const TruShadowPowerMeter *m) {
    if (*m->flags & 2) return;
    BYTE *t = TargetOf(*reinterpret_cast<BYTE **>(GameTracker() + 0x504), 5);
    if (!t || Excluded(t)) return;
    g_strike.target[0] = reinterpret_cast<DWORD>(t);
    g_strike.target[1] = *reinterpret_cast<const DWORD *>(t + 0x44);
    g_strike.count = 1;
    if (!StrikeAt(t, 1)) return;
    const BYTE *tuning = Tuning();
    if (tuning) {
        m->drain(*reinterpret_cast<const float *>(tuning + 0x34));
        m->request[1][0] = *reinterpret_cast<const float *>(tuning + 0x48);
        m->request[1][1] = *reinterpret_cast<const float *>(tuning + 0x44);
        m->selector();
    }
    *m->startValue = *m->value;
    // TU [0x829ca3d0] = 1 (the "Adren Result" UI call of the exit, retail 0x822a5d28) - compiled out on PC (tru+0x319035)
    *m->flags = (*m->flags & ~0x108u) | 0x12u;
    Log(1, "shadow strike start: target 0x%08lx, meter flags 0x%03lx", g_strike.target[0], *m->flags);
}

// TU 0x823d8d18 (slot 3, every frame)
void StrikeTick(const TruShadowPowerMeter *m) {
    if (!(*m->flags & 2)) return;
    BYTE *gt = GameTracker();
    BYTE *player = *reinterpret_cast<BYTE **>(gt + 0x504);
    DWORD word = 0;
    const DWORD flags = *m->flags;      // TU 0x823d8d28: r10 = flags once, tested again at 0x823d8dfc
    if (*reinterpret_cast<const volatile BYTE *>(0x008ab4e6) && !(*reinterpret_cast<const volatile BYTE *>(0x00e7f144) & 1) &&
        *reinterpret_cast<const volatile BYTE *>(0x00e7f143) != 4 && InputWord(0x1ad0, &word) && (word & 0x10)) {
        const BYTE *model = *reinterpret_cast<BYTE **>(player);
        if (!((*reinterpret_cast<const WORD *>(model + 0x40) >> 7) & 1)) {
            // TU 0x823d8dfc..0x823d8e1c: flag 4 -> 0x823d84d0(1.0) (drain all), then 0x823d9050 (look off)
            if (flags & 4) {
                const BYTE *tu = Tuning();
                if (tu) m->drain(*reinterpret_cast<const float *>(tu + 0x10));
                LookOff(m, "tick (end by input)");
            }
        } else {
            // TU 0x823d8db0: 0x823d9050 (look off; nothing unless flag 4) before the second strike
            LookOff(m, "tick (second strike)");
            BYTE *t = HandleObject(g_strike.target);
            if (!t) return;
            ++g_strike.count;
            if (!StrikeAt(t, g_strike.count)) return;
        }
    }
    const BYTE *model = *reinterpret_cast<BYTE **>(player);
    const bool on = (*m->flags & 2) && ((*reinterpret_cast<const WORD *>(model + 0x40) >> 7) & 1);
    if (on && !g_strike.latch) {
        reinterpret_cast<PlayerEventFn>(kPlayerEvent)(Player(), 0x34, 0xff, 0);
        *reinterpret_cast<volatile BYTE *>(kHudStrikeByte) = 1;
        reinterpret_cast<HudUpdateFn>(kHudUpdate)();
    } else if (!on && g_strike.latch) {
        reinterpret_cast<PlayerEventFn>(kPlayerEvent)(Player(), 0x35, 0xff, 0);
        *reinterpret_cast<volatile BYTE *>(kHudStrikeByte) = 0;
        reinterpret_cast<HudUpdateFn>(kHudUpdate)();
    }
    BYTE *t = HandleObject(g_strike.target);
    if (t && !(*m->flags & 0x100)) {
        // 0x8226f958: same root (+0x214 chain) as the player -> no hit
        const BYTE *a = Player(), *b = t;
        bool same = false;
        if (a != b) {
            while (*reinterpret_cast<const BYTE *const *>(a + 0x214)) a = *reinterpret_cast<const BYTE *const *>(a + 0x214);
            while (*reinterpret_cast<const BYTE *const *>(b + 0x214)) b = *reinterpret_cast<const BYTE *const *>(b + 0x214);
            same = a == b;
        }
        BYTE *pc = *reinterpret_cast<BYTE **>(*reinterpret_cast<BYTE **>(Player() + 0x280) + 0x14);
        if (!same && *reinterpret_cast<const float *>(AnimEntry(pc) + 0x28) > g_strike.frames * kHundred) {
            const SHORT id = *reinterpret_cast<const SHORT *>(*reinterpret_cast<const BYTE *const *>(Player() + 0x50) + 0x214);
            reinterpret_cast<HitFn>(kHit)(t + 0x1d0, 0, Player(), 0, id, 0, 0);
            *m->flags |= 0x100;
            Log(1, "shadow strike hit: target 0x%08lx (tru+0x1b4de0, id %d)", reinterpret_cast<DWORD>(t), id);
        }
    }
    g_strike.latch = on ? 1 : 0;
}

// TU 0x823d9210 (slot 2)
void StrikeEnd(const TruShadowPowerMeter *m) {
    if (!(*m->flags & 2)) return;
    BYTE *t = HandleObject(g_strike.target);
    BYTE *gt = GameTracker();
    if (t && *reinterpret_cast<const int *>(*reinterpret_cast<const BYTE *const *>(gt + 0xf10) + 0x24) < 1 &&
        *reinterpret_cast<void **>(t + 0x120))
        reinterpret_cast<MessageFn>(kMessage)(t, 0x3f, nullptr);
    g_strike.target[0] = g_strike.target[1] = 0;
    // TU 0x823d92ac..0x823d92d0: flag 4 -> 0x823d9050 (look off) first, then 0x823d84d0(1.0) (drain all)
    if (*m->flags & 4) {
        LookOff(m, "end");
        const BYTE *tu = Tuning();
        if (tu) m->drain(*reinterpret_cast<const float *>(tu + 0x10));
    }
    if (Tuning()) {
        m->request[1][0] = m->request[1][1] = kMinusOne;
        m->selector();
    }
    *m->flags &= ~0x12u;
    *m->startValue = kMeterStart;
    Log(1, "shadow strike end: message 0x3f %s, meter flags 0x%03lx", t ? "sent" : "not sent", *m->flags);
}

void State1014(int k, void *agent) {
    ReadSwitches();
    if (Doppelganger()) {
        const TruShadowPowerMeter *m = (g_strikeTranslate && g_strikeOk) ? Meter() : nullptr;
        if (m) {
            Hit(g_p1014[k], 1, "doppelganger mode: TU strike translation");
            __try {
                if (k == 0) StrikeStart(m);
                else if (k == 1) StrikeEnd(m);
                else StrikeTick(m);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                Log(0, "state 1014 slot %d: access fault in the strike - skipped", k == 0 ? 0 : k == 1 ? 2 : 3);
            }
            return;
        }
        if (g_strikeGate) {
            Hit(g_p1014[k], 0, g_strikeTranslate ? "doppelganger mode: no meter interface / blocks - strike not run"
                                                 : "doppelganger mode: [Strike] Translate=0 - strike not run");
            return;
        }
    }
    if (g_orig1014[k]) g_orig1014[k](agent);
}
void __cdecl State1014Slot0(void *agent) { State1014(0, agent); }
void __cdecl State1014Slot2(void *agent) { State1014(1, agent); }
void __cdecl State1014Slot3(void *agent) { State1014(2, agent); }

// ---------------------------------------------------------------- Lara's tables at registration time
// TU 0x82473b50 = PC tru+0x368b60 (virtual, the only reference is the vtable slot 0x85e1d4) registers the tables of
// the two machines (gameTracker+0xf10 / +0xf14) through `push table` operands. TruShadowPower (machine 1) points
// them at its copies when it loads - after this plugin (alphabetical) and with byte checks over that code, so the
// tables are extended here only when the registration runs: the current operand (original or another plugin's copy)
// is copied with this plugin's records.
const DWORD kRegSlot = 0x0085e1d4, kRegFn = 0x00768b60;
const char *const kRegFnHex = "a158dbfa00 56 c70574dafa0048000000 8bb0100f0000 8bce e8c3a80100 85c0 7524";
const DWORD kM1CondPush = 0x00768b81, kM1StatePush = 0x00768b99, kM2CondPush = 0x00768bd6;
const char *const kM1CondTailHex = "8bce e893c50100";     // after the push imm32: mov ecx, esi; call 0x785120
const char *const kM1StateTailHex = "8bce e85bca0100";    // call 0x785600
const char *const kM2CondTailHex = "8bce e83ec50100";     // call 0x785120
const DWORD kGenericCondPush = 0x00787343, kGenericCondTable = 0x008b57e0;
const DWORD kGenericStatePush = 0x0078736a;
typedef void(__fastcall *RegFn)(void *self, void *edx, DWORD a, DWORD b);
RegFn g_origReg = nullptr;
bool g_regPatched = false;

DWORD g_m1Cond[(400 + 8) * 3], g_m2Cond[(400 + 8) * 3], g_m1State[(260 + 4) * 7];

int Count(const DWORD *t, int stride, int limit) {
    for (int i = 0; i < limit; ++i)
        if (t[i * stride] == 0) return i;
    return -1;
}
int Find(const DWORD *t, int stride, int count, DWORD id) {
    for (int i = 0; i < count; ++i)
        if (t[i * stride] == id) return i;
    return -1;
}

bool GenericHas(DWORD pushOperand, DWORD original, int stride, DWORD id) {
    DWORD table = *reinterpret_cast<const DWORD *>(pushOperand);
    if (table == original) return false;
    const DWORD *t = reinterpret_cast<const DWORD *>(table);
    int n = Count(t, stride, 3000);
    return n > 0 && Find(t, stride, n, id) >= 0;
}

struct CondAdd { DWORD id; const void *fn; DWORD expectOld; };

// copy of the condition table at the operand with: replaced handlers (only when they are still the PC ones) and
// added ids (only when absent here and present in the generic registry - else the registration loop crashes)
bool ExtendConds(DWORD pushAt, DWORD *copy, int capacity, const CondAdd *adds, int addCount, int machine) {
    DWORD *operand = reinterpret_cast<DWORD *>(pushAt + 1);
    if (*operand == reinterpret_cast<DWORD>(copy)) return true;           // already ours (next level)
    const DWORD *t = reinterpret_cast<const DWORD *>(*operand);
    int n = Count(t, 3, capacity - addCount - 1);
    if (n <= 0) { Log(0, "machine %d conditions: table 0x%08lx unreadable / too long - not extended", machine, *operand); return false; }
    memcpy(copy, t, (n + 1) * 3 * sizeof(DWORD));
    int added = 0, replaced = 0;
    char done[300] = "";
    for (int k = 0; k < addCount; ++k) {
        const CondAdd &a = adds[k];
        int i = Find(copy, 3, n, a.id);
        char item[40];
        if (a.expectOld) {
            if (i < 0) { Log(0, "machine %d: condition %lu not in the table - not replaced", machine, a.id); continue; }
            if (copy[i * 3 + 2] != a.expectOld) {
                Log(0, "machine %d: condition %lu handler is 0x%08lx, expected the PC 0x%08lx (another plugin?) - not "
                       "replaced", machine, a.id, copy[i * 3 + 2], a.expectOld);
                continue;
            }
            copy[i * 3 + 2] = reinterpret_cast<DWORD>(a.fn);
            ++replaced;
            _snprintf_s(item, sizeof(item), _TRUNCATE, " %lu (replaced)", a.id);
        } else {
            if (i >= 0) { Log(0, "machine %d: condition %lu already registered (0x%08lx) - not added", machine, a.id, copy[i * 3 + 2]); continue; }
            if (!GenericHas(kGenericCondPush, kGenericCondTable, 3, a.id)) {
                Log(0, "machine %d: condition %lu is not in the generic registry (TruDoppelganger.asi not active?) - not "
                       "added (the registration would crash)", machine, a.id);
                continue;
            }
            memmove(copy + (n + 1) * 3, copy + n * 3, 3 * sizeof(DWORD));   // closing record one further
            copy[n * 3] = a.id;
            copy[n * 3 + 1] = 2000;                                           // group 2000 as in the TU tables
            copy[n * 3 + 2] = reinterpret_cast<DWORD>(a.fn);
            ++n;
            ++added;
            _snprintf_s(item, sizeof(item), _TRUNCATE, " %lu (added)", a.id);
        }
        strncat_s(done, sizeof(done), item, _TRUNCATE);
    }
    DWORD value = reinterpret_cast<DWORD>(copy);
    if (!WriteCode(reinterpret_cast<DWORD>(operand), &value, 4)) return false;
    Log(1, "machine %d conditions:%s - table copy 0x%08lx (%d records, from 0x%08lx)", machine, done[0] ? done : " none",
        reinterpret_cast<DWORD>(copy), n, reinterpret_cast<DWORD>(t));
    return added + replaced > 0;
}

bool ExtendStates() {
    DWORD *operand = reinterpret_cast<DWORD *>(kM1StatePush + 1);
    if (*operand == reinterpret_cast<DWORD>(g_m1State)) return true;
    const DWORD *t = reinterpret_cast<const DWORD *>(*operand);
    int n = Count(t, 7, 260);
    if (n <= 0) { Log(0, "machine 1 states: table 0x%08lx unreadable / too long - state 1014 not gated", *operand); return false; }
    memcpy(g_m1State, t, (n + 1) * 7 * sizeof(DWORD));
    char done[320] = "";
    // 1014 (strike gate / translation)
    if (g_strikeGate || g_strikeTranslate) {
        int i = Find(g_m1State, 7, n, 1014);
        DWORD *rec = i >= 0 ? g_m1State + i * 7 : nullptr;
        const int slots[3] = {0, 2, 3};
        const void *wrap[3] = {&State1014Slot0, &State1014Slot2, &State1014Slot3};
        bool ok = rec != nullptr;
        for (int k = 0; ok && k < 3; ++k)
            if (rec[1 + slots[k]] != kState1014Pc[k]) {
                Log(0, "machine 1 state 1014 slot %d is 0x%08lx, expected the PC 0x%08lx - not wrapped", slots[k],
                    rec[1 + slots[k]], kState1014Pc[k]);
                ok = false;
            }
        if (ok) {
            for (int k = 0; k < 3; ++k) {
                g_orig1014[k] = reinterpret_cast<StateFn>(rec[1 + slots[k]]);
                rec[1 + slots[k]] = reinterpret_cast<DWORD>(wrap[k]);
            }
            strncat_s(done, sizeof(done), g_strikeTranslate ? " 1014 (slots 0 / 2 / 3 wrapped: strike translation)"
                                                            : " 1014 (slots 0 / 2 / 3 gated)", _TRUNCATE);
        }
    }
    if (g_probe1013 && g_blocksOk) {
        int i = Find(g_m1State, 7, n, 1013);
        if (i >= 0 && g_m1State[i * 7 + 1] == kState1013Pc && HexAt(kState1013Pc, kState1013PcHex)) {
            g_orig1013 = reinterpret_cast<StateFn>(g_m1State[i * 7 + 1]);
            g_m1State[i * 7 + 1] = reinterpret_cast<DWORD>(&State1013Slot0);
            strncat_s(done, sizeof(done), " 1013 (slot 0 probe)", _TRUNCATE);
        } else {
            Log(0, "machine 1 state 1013 slot 0 is not the PC 0x%08lx - no probe", kState1013Pc);
        }
    }
    if (g_statesOn && g_statesOk && g_listOk) {
        // 1007: slot 4 = PC tru+0x36d930 kept for the main game, slot 5 (TU-only) added - both doppelganger-only TU code
        int i = Find(g_m1State, 7, n, 1007);
        if (i >= 0 && g_m1State[i * 7 + 5] == 0x0076d930 && g_m1State[i * 7 + 6] == 0) {
            g_orig1007Slot4 = reinterpret_cast<StateFn>(g_m1State[i * 7 + 5]);
            g_m1State[i * 7 + 5] = reinterpret_cast<DWORD>(&State1007Slot4);
            g_m1State[i * 7 + 6] = reinterpret_cast<DWORD>(&State1007Slot5);
            strncat_s(done, sizeof(done), " 1007 (slots 4 / 5)", _TRUNCATE);
        } else {
            Log(0, "machine 1 state 1007 is not {.., 0x0076d930, 0} - not wrapped");
        }
        // 1017 {0, 0, 0, 0, f, 0} and 244 {f, 0, 0, g, 0, 0} as in the TU table 0x82757948
        struct { DWORD id; DWORD fn[6]; } const adds[2] = {
            {1017, {0, 0, 0, 0, reinterpret_cast<DWORD>(&State1017Slot4), 0}},
            {244, {reinterpret_cast<DWORD>(&State244Slot0), 0, 0, reinterpret_cast<DWORD>(&State244Slot3), 0, 0}}};
        for (const auto &a : adds) {
            if (Find(g_m1State, 7, n, a.id) >= 0) { Log(0, "machine 1 state %lu already registered - not added", a.id); continue; }
            if (!GenericHas(kGenericStatePush, 0x008b4200, 7, a.id)) {
                Log(0, "machine 1 state %lu is not in the generic registry (TruDoppelganger.asi?) - not added", a.id);
                continue;
            }
            memmove(g_m1State + (n + 1) * 7, g_m1State + n * 7, 7 * sizeof(DWORD));
            g_m1State[n * 7] = a.id;
            for (int k = 0; k < 6; ++k) g_m1State[n * 7 + 1 + k] = a.fn[k] ? a.fn[k] : 0;
            ++n;
            char item[24];
            _snprintf_s(item, sizeof(item), _TRUNCATE, " %lu (added)", a.id);
            strncat_s(done, sizeof(done), item, _TRUNCATE);
        }
    }
    if (g_statesOn && g_statesOk && g_listOk && g_s1019Ok && g_probe1019) {
        // 0.5: 1019 {e, e, 0, t, 0, 0} and 1020 {e, e, 0, 0, 0, 0} as in the TU table 0x82757948 (records 143 / 153)
        struct { DWORD id; DWORD fn[6]; bool *reg; } const adds[2] = {
            {1019, {reinterpret_cast<DWORD>(&State1019Slot0), reinterpret_cast<DWORD>(&State1019Slot1), 0,
                    reinterpret_cast<DWORD>(&State1019Slot3), 0, 0}, &g_reg1019},
            {1020, {reinterpret_cast<DWORD>(&State1020Slot0), reinterpret_cast<DWORD>(&State1020Slot1), 0, 0, 0, 0}, &g_reg1020}};
        for (const auto &a : adds) {
            if (Find(g_m1State, 7, n, a.id) >= 0) {
                Log(0, "machine 1 state %lu already registered (0x%08lx, another plugin?) - not added", a.id,
                    g_m1State[Find(g_m1State, 7, n, a.id) * 7 + 1]);
                continue;
            }
            if (!GenericHas(kGenericStatePush, 0x008b4200, 7, a.id)) {
                Log(0, "machine 1 state %lu is not in the generic registry (TruDoppelganger.asi?) - not added", a.id);
                continue;
            }
            if (n + 2 > 260) { Log(0, "machine 1 state table copy full - state %lu not added", a.id); continue; }
            memmove(g_m1State + (n + 1) * 7, g_m1State + n * 7, 7 * sizeof(DWORD));
            g_m1State[n * 7] = a.id;
            for (int k = 0; k < 6; ++k) g_m1State[n * 7 + 1 + k] = a.fn[k];
            ++n;
            *a.reg = true;
            char item[48];
            _snprintf_s(item, sizeof(item), _TRUNCATE, " %lu (added, %s)", a.id,
                        (a.id == 1019 ? g_translate1019 : g_translate1020) ? "ON" : "log only");
            strncat_s(done, sizeof(done), item, _TRUNCATE);
        }
    } else if (g_statesOn && g_probe1019) {
        Log(0, "machine 1 states 1019 / 1020: not added (building blocks %d, target list %d, states blocks %d)",
            g_s1019Ok ? 1 : 0, g_listOk ? 1 : 0, g_statesOk ? 1 : 0);
    }
    if (g_statesOn && g_statesOk && g_s1019Ok && g_s231Ok && g_probe231) {
        // 0.5.1: 231 {PC 0 -> wrapper, 0 -> TU slot 1}, 1004 {PC 0 -> wrapper, 0 -> TU slot 1, PC slot 2 kept}
        int i = Find(g_m1State, 7, n, 231);
        const DWORD *r = i >= 0 ? g_m1State + i * 7 : nullptr;
        if (r && r[1] == kState231Pc && r[2] == 0) {
            g_orig231 = reinterpret_cast<StateFn>(r[1]);
            g_m1State[i * 7 + 1] = reinterpret_cast<DWORD>(&State231Slot0);
            g_m1State[i * 7 + 2] = reinterpret_cast<DWORD>(&State231Slot1);
            g_reg231 = true;
            strncat_s(done, sizeof(done), g_translate231s0 || g_translate231s1 ? " 231 (slots 0 / 1, ON)"
                                                                                : " 231 (slots 0 / 1, log only)", _TRUNCATE);
        } else {
            Log(0, "machine 1 state 231 is not {0x%08lx, 0, ..} (%s) - not wrapped", kState231Pc,
                r ? "other handlers - another plugin?" : "missing");
        }
        i = Find(g_m1State, 7, n, 1004);
        r = i >= 0 ? g_m1State + i * 7 : nullptr;
        if (r && r[1] == kState1004Pc && r[2] == 0 && r[3] == kState1004PcSlot2) {
            g_orig1004 = reinterpret_cast<StateFn>(r[1]);
            g_m1State[i * 7 + 1] = reinterpret_cast<DWORD>(&State1004Slot0);
            g_m1State[i * 7 + 2] = reinterpret_cast<DWORD>(&State1004Slot1);
            g_reg1004 = true;
            strncat_s(done, sizeof(done), g_translate1004 ? " 1004 (slots 0 / 1, ON)" : " 1004 (slots 0 / 1, log only)", _TRUNCATE);
        } else {
            Log(0, "machine 1 state 1004 is not {0x%08lx, 0, 0x%08lx, ..} (%s) - not wrapped", kState1004Pc,
                kState1004PcSlot2, r ? "other handlers - another plugin?" : "missing");
        }
    } else if (g_statesOn && g_probe231) {
        Log(0, "machine 1 states 231 / 1004: not wrapped (building blocks 231 / 1004 %d, 1019 %d, states %d)",
            g_s231Ok ? 1 : 0, g_s1019Ok ? 1 : 0, g_statesOk ? 1 : 0);
    }
    if (!done[0]) return false;
    DWORD value = reinterpret_cast<DWORD>(g_m1State);
    if (!WriteCode(reinterpret_cast<DWORD>(operand), &value, 4)) return false;
    Log(1, "machine 1 states:%s - table copy 0x%08lx (%d records, from 0x%08lx)", done, value, n, reinterpret_cast<DWORD>(t));
    return true;
}

volatile LONG g_regCalls = 0;
void __fastcall RegHook(void *self, void *edx, DWORD a, DWORD b) {
    LONG call = InterlockedIncrement(&g_regCalls);
    __try {
        if (g_conditions && g_blocksOk) {
            const CondAdd m1[] = {{2005, &Cond2005, 0}, {2013, &Cond2013, 0}, {2006, &Cond2006, 0},
                                  {2011, &Cond2011, kCond2011Pc}, {538, &Cond538, kCond538Pc}};
            const CondAdd m2[] = {{2005, &Cond2005, 0}, {2013, &Cond2013, 0},
                                  {2011, &Cond2011, kCond2011Pc}, {538, &Cond538, kCond538Pc}};
            ExtendConds(kM1CondPush, g_m1Cond, sizeof(g_m1Cond) / 12, m1, 5, 1);
            ExtendConds(kM2CondPush, g_m2Cond, sizeof(g_m2Cond) / 12, m2, 4, 2);
        }
        if (g_strikeGate || g_strikeTranslate || g_statesOn) ExtendStates();
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "Lara registration hook: access fault while extending the tables - original tables kept where not yet written");
    }
    if (call == 1) Log(1, "Lara state-machine registration (tru+0x368b60) reached - tables checked / extended");
    g_origReg(self, edx, a, b);
}

bool SetupRegistration() {
    if (!g_conditions && !g_strikeGate && !g_strikeTranslate && !g_statesOn) {
        Log(1, "conditions, states and strike off - Lara's tables untouched");
        return false;
    }
    if (*reinterpret_cast<const DWORD *>(kRegSlot) != kRegFn || !HexAt(kRegFn, kRegFnHex) ||
        *reinterpret_cast<const BYTE *>(kM1CondPush) != 0x68 || !HexAt(kM1CondPush + 5, kM1CondTailHex) ||
        *reinterpret_cast<const BYTE *>(kM1StatePush) != 0x68 || !HexAt(kM1StatePush + 5, kM1StateTailHex) ||
        *reinterpret_cast<const BYTE *>(kM2CondPush) != 0x68 || !HexAt(kM2CondPush + 5, kM2CondTailHex)) {
        Log(0, "Lara registration tru+0x368b60 / vtable slot 0x%08lx / push operands do not match - tables untouched", kRegSlot);
        return false;
    }
    for (int k = 0; k < 3; ++k)
        if (!HexAt(kState1014Pc[k], kState1014PcHex[k])) {
            Log(0, "state 1014 handler 0x%08lx does not match - strike gate off", kState1014Pc[k]);
            g_strikeGate = 0;
        }
    g_origReg = reinterpret_cast<RegFn>(kRegFn);
    DWORD hook = reinterpret_cast<DWORD>(&RegHook);
    if (!WriteCode(kRegSlot, &hook, 4)) return false;
    Log(1, "Lara registration: vtable slot 0x%08lx -> hook (tables are extended when tru+0x368b60 runs)", kRegSlot);
    return true;
}

// ---------------------------------------------------------------- start
void ReadOptions(const char *dir) {
    char *ini = g_iniPath;
    _snprintf_s(g_iniPath, sizeof(g_iniPath), _TRUNCATE, "%sTruShadowCombat.ini", dir);
    g_enabled = GetPrivateProfileIntA("ShadowCombat", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("ShadowCombat", "LogLevel", 1, ini);
    g_targetList = GetPrivateProfileIntA("TargetList", "Enabled", 1, ini);
    g_conditions = GetPrivateProfileIntA("Conditions", "Enabled", 1, ini);
    g_strikeGate = GetPrivateProfileIntA("Strike", "Gate", 1, ini);
    g_strikeTranslate = GetPrivateProfileIntA("Strike", "Translate", 0, ini);
    g_statesOn = GetPrivateProfileIntA("States", "Enabled", 1, ini);
    g_probe1013 = GetPrivateProfileIntA("Probe", "State1013", 1, ini);
    g_translate1013 = GetPrivateProfileIntA("States", "Translate1013", 0, ini);
    g_translate1019 = GetPrivateProfileIntA("States", "Translate1019", 0, ini) ? 1 : 0;
    g_translate1020 = GetPrivateProfileIntA("States", "Translate1020", 0, ini) ? 1 : 0;
    g_probe1019 = GetPrivateProfileIntA("Probe", "States1019", 1, ini);
    g_translate231s0 = GetPrivateProfileIntA("States", "Translate231Slot0", 0, ini) ? 1 : 0;
    g_translate231s1 = GetPrivateProfileIntA("States", "Translate231Slot1", 0, ini) ? 1 : 0;
    g_translate1004 = GetPrivateProfileIntA("States", "Translate1004", 0, ini) ? 1 : 0;
    g_probe231 = GetPrivateProfileIntA("Probe", "States231And1004", 1, ini);
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruShadowCombat.log", dir);
    ReadOptions(dir);
    Log(1, "%s loaded (enabled %d, log level %d, target list %d, conditions %d, states %d, strike gate %d, strike "
           "translate %d)", kVersion, g_enabled, g_logLevel, g_targetList, g_conditions, g_statesOn, g_strikeGate,
        g_strikeTranslate);
    if (!g_enabled) { Log(1, "disabled by TruShadowCombat.ini - nothing patched"); return; }
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - nothing patched", base, kImageBase); return; }
    g_tableOk = HexAt(kFindObject, kFindObjectHex) && HexAt(kFindObjectLoop, kFindObjectLoopHex);
    g_listOk = SetupTargetList();
    g_blocksOk = CheckBlocks();       // also the building blocks of the states / strike (list, targets, template)
    if (g_conditions && !g_blocksOk) g_conditions = 0;
    g_statesOk = g_blocksOk && CheckStateBlocks();
    if (g_statesOn && !g_statesOk) Log(0, "states 1017 / 244 / 1007: building blocks not verified - not registered");
    g_strikeOk = g_statesOk && CheckStrikeBlocks();
    g_s1019Ok = g_statesOk && CheckState1019Blocks();
    if (g_statesOn && g_probe1019)
        Log(1, "states 1019 / 1020 (TU 0x8245f420 / 0x8245f540 / 0x8245f398): %s - Translate1019 %d, Translate1020 %d "
               "(0 = registered, log only; read again at run time at most once per second)",
            g_s1019Ok ? "building blocks verified, registered with Lara's tables" : "building blocks NOT verified - not registered",
            g_translate1019, g_translate1020);
    g_s231Ok = g_s1019Ok && CheckState231Blocks();
    if (g_statesOn && g_probe231)
        Log(1, "states 231 / 1004 (TU 0x82464160 / 0x8245efc8, slots 0 / 1): %s - Translate231Slot0 %d, Translate231Slot1 %d, "
               "Translate1004 %d (0 = PC handler + \"off (would)\" lines; read again at run time)",
            g_s231Ok ? "building blocks verified, wrapped at Lara's registration" : "building blocks NOT verified - PC handlers",
            g_translate231s0, g_translate231s1, g_translate1004);
    if (g_strikeTranslate)
        Log(1, "shadow strike translation %s ([Strike] Translate=1; also needs TruShadowPowerMeterApi at run time)",
            g_strikeOk ? "ready" : "OFF: building blocks not verified");
    if (g_conditions && !g_listOk)
        Log(1, "conditions: target list not active - 2005 / 2006 / 2013 and the doppelganger branch of 2011 answer 0 "
               "(the TU's targeters 6 / 9 do not exist)");
    SetupTranslate1013();
    SetupRegistration();
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

extern "C" __declspec(dllexport) const char *TruShadowCombatVersion() { return kVersion; }

// the strike's TU meter fields (+0x15 latch, +0x18 / +0x1c target handle, +0x28 count, +0x2c frames) for the owner of
// the strike look (TU 0x823d8a80 / 0x823d9050, player anim events 5 / 4) - docs Befund-Schattenkampf.md section 5
struct TruShadowCombatStrike { DWORD size, version; BYTE *latch; DWORD *target; LONG *count; float *frames; };
extern "C" __declspec(dllexport) const TruShadowCombatStrike *__cdecl TruShadowCombatStrikeState() {
    static const TruShadowCombatStrike s = {sizeof(TruShadowCombatStrike), 1, &g_strike.latch, g_strike.target,
                                            &g_strike.count, &g_strike.frames};
    return &s;
}

// TU target of a targeter by TU index (0..9) for diagnostics (TruMenu / tests): object pointer or 0
extern "C" __declspec(dllexport) void *__cdecl TruShadowCombatTarget(int tuIndex) {
    if (!g_listOk || tuIndex < 0 || tuIndex >= kTuTargeters) return nullptr;
    __try {
        return TargeterObject(tuIndex);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return nullptr;
    }
}
