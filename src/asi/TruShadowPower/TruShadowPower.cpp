// TruShadowPower.asi - DLC 2 "Lara's Shadow" shadow power (slow motion + meter) for the PC tru.exe (Steam, image base
// 0x400000).
//
// The Xbox title update (TU) gives Lara the Doppelgaenger's power: while LB or RB is held the world slows down, a meter
// drains, and the HUD shows it as the second silhouette. The PC exe never got that code, but it has the engine parts
// the TU drives (docs/WINDOWS_REBUILD.md finding 43). This plugin is a function-by-function TRANSLATION of the TU's
// meter code (decompiled from the TU memory image, see docs/Befund-Schattenkraft.md "ASI step 3.3"):
//
//   Xbox TU                       here                PC engine parts used
//   0x823d7700 meter init         MeterInit           -
//   0x823d7a10 per-frame tick     MeterTick           frame time 0xe7f190 (= Xbox 0x82efb560, unscaled, 30 fps units)
//   0x823d8120 may start?         CanStart            -
//   0x823d7d40 start              StartPower          SetPlayerTimeScale / SetWorldTimeScale (the TU's selector
//   0x823d7fb8 stop               StopPower             0x823d7520 writes the same ramps, 33 ms)
//   0x823d81a0 refill             Refill              HUD: 0xfae8d4 + display group 1 (tru+0x37d9d0, tru+0x37da70)
//   0x823d8380 drain              Drain               HUD as above
//   0x82415518 tuning lookup      FindTuning          object table 0xdb7400 (= Xbox 0x82979280), object 858
//
// The rates and scales come from the same data the Xbox reads: the tuning struct (u16 type 60) of the object
// player_tru_dlc2_extension (id 858), offsets +0x10 max .. +0x70 as the TU uses them. Parts of the TU functions that
// depend on systems not ported yet (sounds, the blur effect, instance messages, cinematic / zone checks) are left out
// and named at their place - see the doc for the full list.
//
// Hooks: the per-frame pad poll (tru+0x84b82, call dword ptr [0x00a02b8c] = XInputGetState) is redirected to a wrapper
// that runs the tick on the game thread, once per game frame. Every address is checked against the expected bytes
// first; on a mismatch the affected part stays off and the reason is logged. Loaded by the Ultimate ASI Loader
// (binkw32.dll of the installed game). Options: TruShadowPower.ini next to the .asi (see README.md).

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>

namespace {

struct PadState {                       // XINPUT_STATE without including xinput.h
    DWORD dwPacketNumber;
    WORD wButtons;
    BYTE bLeftTrigger, bRightTrigger;
    SHORT sThumbLX, sThumbLY, sThumbRX, sThumbRY;
};

typedef DWORD(WINAPI *XInputGetStateFn)(DWORD, PadState *);
typedef void(__stdcall *SetTimeScaleFn)(float target, float seconds);
typedef void(__cdecl *HudGroupFn)(int group);
typedef void(__cdecl *HudUpdateFn)();

const DWORD kImageBase = 0x00400000;
const DWORD kCallSite = 0x00484b82;     // ff 15 8c 2b a0 00 = call dword ptr [0x00a02b8c]
const DWORD kPadPointer = 0x00a02b8c;
const DWORD kSetWorld = 0x00776030;
const DWORD kSetPlayer = 0x00776090;
const BYTE kCallBytes[] = {0xff, 0x15, 0x8c, 0x2b, 0xa0, 0x00};
// first 12 bytes of both setters: push ecx; mov eax,[0xe7f15c]; fild dword [0xe7f15c]; test eax,eax
const BYTE kSetterBytes[] = {0x51, 0xa1, 0x5c, 0xf1, 0xe7, 0x00, 0xdb, 0x05, 0x5c, 0xf1, 0xe7, 0x00};
const BYTE kWorldRamp[] = {0xb9, 0xb4, 0xbe, 0x8a, 0x00};   // mov ecx,0x8abeb4 at +0x1d
const BYTE kPlayerRamp[] = {0xb9, 0x94, 0xbe, 0x8a, 0x00};  // mov ecx,0x8abe94 at +0x1d

// frame time: the frame update stores us / 33333.33 (1.0 = one 30 fps frame) unscaled into 0xe7f190, like the Xbox
// into 0x82efb560 (both frame updates use the constants 0x8235 / 50000 / 0x411b us); the game clock 0xe7f15c (ms,
// Xbox 0x82efb528) advances once per frame and is the setters' start time
const DWORD kFrameDivSite = 0x005da3f4;                     // fdiv qword [0x855280]
const BYTE kFrameDivBytes[] = {0xdc, 0x35, 0x80, 0x52, 0x85, 0x00};
const DWORD kFrameDivConst = 0x00855280;
const BYTE kFrameDivValue[] = {0x00, 0x00, 0x00, 0xa0, 0xaa, 0x46, 0xe0, 0x40};  // 33333.333
const DWORD kFrameStoreSite = 0x005da40c;                   // fst dword [0xe7f190]
const BYTE kFrameStoreBytes[] = {0xd9, 0x15, 0x90, 0xf1, 0xe7, 0x00};
const float *const kFrameTime = reinterpret_cast<const float *>(0x00e7f190);
const volatile DWORD *const kGameClock = reinterpret_cast<const volatile DWORD *>(0x00e7f15c);

// HUD: the second silhouette is a uimeter fed by hudscreenmgr native 36 (0xfae8d4); it is drawn while display group 1
// is requested. The TU meter does "0x829ca6cc = value / max; 0x829ca724 |= 2; (*0x829ca720)->vtbl[0xc]()", the PC
// breath code the same with tru+0x37d9d0(1) (0xfae924 |= 1 << 1) and tru+0x37da70 ((*0xfae920)->vtbl[0xc]()).
const DWORD kHudValueGetter = 0x0077a860;                   // hudscreenmgr native 36 body
const BYTE kHudValueBytes[] = {0xd9, 0x05, 0xd4, 0xe8, 0xfa, 0x00, 0xc3};   // fld dword [0xfae8d4]; ret
const DWORD kHudGroup = 0x0077d9d0;
const BYTE kHudGroupBytes[] = {0x8b, 0x4c, 0x24, 0x04, 0x8d, 0x41, 0xff, 0x83, 0xf8, 0x1e, 0x77, 0x0e, 0xba,
                               0x01, 0x00, 0x00, 0x00, 0xd3, 0xe2, 0x09, 0x15, 0x24, 0xe9, 0xfa, 0x00, 0xc3};
const DWORD kHudUpdate = 0x0077da70;
const BYTE kHudUpdateBytes[] = {0x8b, 0x0d, 0x20, 0xe9, 0xfa, 0x00, 0x8b, 0x01, 0x8b, 0x50, 0x0c, 0xff, 0xe2};
float *const kHudValue = reinterpret_cast<float *>(0x00fae8d4);
void *const *const kHudManager = reinterpret_cast<void *const *>(0x00fae920);

// object table (Xbox 0x82979280): 0xcc entries of 0x24 bytes, +8 object, +0xc s16 id, +0xe u16 state (2 = loaded);
// checked through the PC lookup tru+0x14e930 that walks it
const DWORD kFindObject = 0x0054e930;
const BYTE kFindObjectBytes[] = {0x8b, 0x54, 0x24, 0x04, 0x33, 0xc0, 0xb9, 0x0c, 0x74, 0xdb, 0x00};
const DWORD kFindObjectLoop = 0x0054e951;
const BYTE kFindObjectLoopBytes[] = {0x83, 0xc1, 0x24, 0x3d, 0xcc, 0x00, 0x00, 0x00};
const DWORD kObjectTable = 0x00db7400;
const int kObjectCount = 0xcc;
const SHORT kExtensionObject = 858;     // player_tru_dlc2_extension
const WORD kTuningType = 60;            // u16 at +2 of the object's data, checked by the TU (0x82412b74)

// 0.4: Lara's own condition link array (PC tru+0x368b60 = Xbox TU 0x82473b50 registers the conditions table
// 0x8b2ce8, activities 0x8b2280, states 0x8b0a50 of the state machine at gameTracker+0xf10). Its loop tru+0x385120
// inserts a record only when the id is also in the generic registry (tru+0x3851bc..+0x385208) - so the title-update ids
// need TruDoppelganger.asi's generic entries AND an entry here with the real handler, as on the Xbox.
const DWORD kLaraReg = 0x00768b60;
const BYTE kLaraRegBytes[] = {0xa1, 0x58, 0xdb, 0xfa, 0x00, 0x56, 0xc7, 0x05, 0x74, 0xda, 0xfa, 0x00, 0x48, 0x00,
                              0x00, 0x00, 0x8b, 0xb0, 0x10, 0x0f, 0x00, 0x00, 0x8b, 0xce, 0xe8, 0xc3, 0xa8, 0x01, 0x00,
                              0x85, 0xc0, 0x75, 0x24, 0x68, 0xe8, 0x2c, 0x8b, 0x00, 0x8b, 0xce, 0xe8, 0x93, 0xc5, 0x01,
                              0x00};
const DWORD kLaraCondPush = 0x00768b81;                     // push 0x8b2ce8 (operand at +1)
const DWORD kGenericCondPush = 0x00787343;                  // operand of the generic builder's push 0x8b57e0
const DWORD kGenericCondTable = 0x008b57e0;
const DWORD kLaraCondTable = 0x008b2ce8;
const int kLaraCondCount = 285;                             // records before the closing {0, 0, default}
const DWORD kCondDefaultFn = 0x00782140;                    // closing record's function (SCCondFunction_Default)
// condition template = Xbox 0x82487718: cache {agent, frame (+0x50c), bits}, predicate(record), value 0 now false,
// 1 now true, 2 falling edge, 3 rising edge, flag bit 0 negates
const DWORD kCondTemplate = 0x00782d70;
const BYTE kCondTemplateBytes[] = {0x51, 0x53, 0x55, 0x8b, 0x6c, 0x24, 0x18, 0x56, 0x8b, 0x74, 0x24, 0x18, 0x8b, 0x5e,
                                   0x08, 0x57, 0x8b, 0x7c, 0x24, 0x18, 0x39, 0x3e, 0xc6, 0x44, 0x24, 0x13, 0x00, 0x75,
                                   0x0b, 0x8b, 0x46, 0x04, 0x3b, 0x87, 0x0c, 0x05, 0x00, 0x00, 0x74, 0x23, 0x55, 0xff,
                                   0x54, 0x24, 0x28};
// float compare = Xbox 0x82487348: record value (s16 +4, key 1000 = variable), mode 1 value >= it, 2 value <= it,
// 0 |difference| < 1e-8 ([0x8454c4] = Xbox [0x8207dcd4]), flag bit 0 negates
const DWORD kCondCompare = 0x00783bd0;
const BYTE kCondCompareBytes[] = {0x56, 0x8b, 0x74, 0x24, 0x10, 0x66, 0x81, 0x3e, 0xe8, 0x03, 0x0f, 0xbf, 0x46, 0x04,
                                  0x89, 0x44, 0x24, 0x10, 0xdb, 0x44, 0x24, 0x10};

// TU constants (Xbox addresses in brackets)
const float kZero = 0.0f;               // [0x8207d538]
const float kOne = 1.0f;                // [0x8207d544] ramp target without a request
const float kMeterStart = 1000.0f;      // [0x8206af78] meter value at init, start value after a stop (+0xc)
const float kPerSecond = 1.0f / 30.0f;  // [0x82052c58] 0.0333333 - frame units -> seconds
const float kRampSeconds = 0.033f;      // [0x8207db70] 33.0 ms, the selector's ramp duration

// tuning struct offsets (floats) as the TU reads them
enum {
    kTuneMax = 0x10, kTuneDrain = 0x14, kTuneRefill = 0x18, kTuneRefillAlt = 0x1c, kTuneRefillDelayed = 0x20,
    kTuneRestart = 0x28, kTuneHigh = 0x2c, kTuneWorld = 0x3c, kTunePlayer = 0x40, kTuneSize = 0x74
};

// copy of the same struct from the converted file (player_tru_dlc2_extension.drm, DTP 22497 +0xf0), used only when
// the object is not found at run time and Fallback=1 - logged as such
BYTE g_fileTuning[kTuneSize];

void InitFileTuning() {
    struct { int offset; float value; } const values[] = {
        {kTuneMax, 1000.0f}, {kTuneDrain, 200.0f}, {kTuneRefill, 200.0f}, {kTuneRefillAlt, 400.0f},
        {kTuneRefillDelayed, 75.0f}, {0x24, 6.0f}, {kTuneRestart, 150.0f}, {kTuneHigh, 300.0f}, {0x30, 200.0f},
        {0x34, 500.0f}, {0x38, 0.1f}, {kTuneWorld, 0.3f}, {kTunePlayer, 1.2f}, {0x70, 75.0f}};
    memset(g_fileTuning, 0, sizeof(g_fileTuning));
    g_fileTuning[0] = 1;                                     // u16 1, u16 type 60 as in the file
    g_fileTuning[2] = static_cast<BYTE>(kTuningType);
    for (const auto &v : values) memcpy(g_fileTuning + v.offset, &v.value, sizeof(float));
}

// the TU's meter object (allocated with the player data; the fields used here, with their Xbox offsets)
struct Meter {
    DWORD flags;                        // +0x04: 1 active, 8 at or above tuning +0x2c, 0x200 ran empty (restart only
                                        //        above tuning +0x28); 0x10 / 0x80 block the meter (not set here)
    float value;                        // +0x08
    float startValue;                   // +0x0c value when the power started (1000 after a stop)
    float delay;                        // +0x10 refill delay timer (no writer found in the TU besides the refill)
    BYTE latch;                         // +0x14 buttons seen held
    DWORD startTime;                    // +0x3c game clock at the last start / stop
};

// options (TruShadowPower.ini)
int g_enabled = 1;
int g_logLevel = 1;                     // 0 errors, 1 info, 2 every start / stop, 3 debug
WORD g_buttons = 0x0300;                // LB 0x0100 | RB 0x0200 (Xbox: either); LB also sprints on PC
int g_hudFeed = 1;                      // [Meter] HudBar
int g_fallback = 1;                     // [Meter] Fallback: file copy of the tuning when the object is not loaded

char g_logPath[MAX_PATH];
CRITICAL_SECTION g_logLock;
volatile XInputGetStateFn g_original = nullptr;
SetTimeScaleFn g_setWorld = reinterpret_cast<SetTimeScaleFn>(kSetWorld);
SetTimeScaleFn g_setPlayer = reinterpret_cast<SetTimeScaleFn>(kSetPlayer);
HudGroupFn g_hudGroup = reinterpret_cast<HudGroupFn>(kHudGroup);
HudUpdateFn g_hudUpdate = reinterpret_cast<HudUpdateFn>(kHudUpdate);
WORD g_lastButtons[4] = {0, 0, 0, 0};
bool g_hudOk = false;                   // HUD code verified
bool g_tableOk = false;                 // object table verified
int g_tuningSource = -1;                // last logged source: 0 none, 1 game object, 2 file copy
DWORD g_lastClock = 0;
Meter g_meter;
volatile LONG g_stop = 0;
const BYTE *volatile g_tuning = nullptr;  // tuning of the last tick (Xbox 0x82415518's result), read by the conditions
int g_condEnabled = 1;                    // [Conditions] Enabled: register 1049-1054 / 1056 in Lara's link array
volatile LONG g_condCalls[8];             // first-call log per handler (1049..1054, 1056)
volatile LONG g_condLast[8];              // last result per handler (+1, 0 = none yet) for LogLevel 2

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

float Tune(const BYTE *tuning, int offset) { return *reinterpret_cast<const float *>(tuning + offset); }

// Xbox 0x82415518 returns the extension instance's data (game state +0x1314 -> instance +0x50); the instance is
// spawned by TU code (0x82412ab0) from the player's object list when the object's data has type 60. The PC has no
// such instance, so the same data is taken from the loaded object itself: table entry id 858, state 2 (loaded),
// object +0x5c data and +0x60 set, u16 type 60 at data +2 - the checks of 0x82412b44..0x82412b7c.
// 0.3.1 (2026-10-31): the lookup failed in the 0.3 test without saying why; it now records which check stopped it
// (same checks, same result) so the next log names the step: 1 table not verified, 2 id 858 not in the table,
// 3 entry state not 2, 4 no object, 5 object +0x5c / +0x60 empty, 6 data type not 60, 7 read fault.
int g_lookupReason = 0;
DWORD g_lookupDetail[4];

const BYTE *ObjectTuning() {
    g_lookupReason = 1;
    if (!g_tableOk) return nullptr;
    __try {
        g_lookupReason = 2;
        for (int i = 0; i < kObjectCount; ++i) {
            const BYTE *entry = reinterpret_cast<const BYTE *>(kObjectTable + i * 0x24);
            if (*reinterpret_cast<const SHORT *>(entry + 0xc) != kExtensionObject) continue;
            g_lookupDetail[0] = static_cast<DWORD>(i);
            g_lookupDetail[1] = *reinterpret_cast<const WORD *>(entry + 0xe);
            g_lookupDetail[2] = *reinterpret_cast<const DWORD *>(entry + 8);
            g_lookupReason = 3;
            if (*reinterpret_cast<const WORD *>(entry + 0xe) != 2) return nullptr;
            const BYTE *object = *reinterpret_cast<const BYTE *const *>(entry + 8);
            g_lookupReason = 4;
            if (!object) return nullptr;
            const BYTE *data = *reinterpret_cast<const BYTE *const *>(object + 0x5c);
            g_lookupDetail[3] = reinterpret_cast<DWORD>(data);
            g_lookupReason = 5;
            if (!data || !*reinterpret_cast<const DWORD *>(object + 0x60)) return nullptr;
            g_lookupReason = 6;
            g_lookupDetail[1] = *reinterpret_cast<const DWORD *>(data);   // first word of the data (u16 x2)
            if (*reinterpret_cast<const WORD *>(data + 2) != kTuningType) return nullptr;
            g_lookupReason = 0;
            return data;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        g_lookupReason = 7;
    }
    return nullptr;
}

// list of the loaded table entries (id / state) once, when the lookup fails - shows whether 858 is there at all
void LogObjectTable() {
    char line[900];
    int n = 0, count = 0;
    __try {
        for (int i = 0; i < kObjectCount && n < static_cast<int>(sizeof(line)) - 16; ++i) {
            const BYTE *entry = reinterpret_cast<const BYTE *>(kObjectTable + i * 0x24);
            WORD state = *reinterpret_cast<const WORD *>(entry + 0xe);
            if (!state) continue;
            int w = _snprintf_s(line + n, sizeof(line) - n, _TRUNCATE, " %d/%u", *reinterpret_cast<const SHORT *>(entry + 0xc),
                                state);
            if (w <= 0) break;
            n += w; ++count;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    line[n] = 0;
    Log(1, "object table 0x%08lx: %d entries in use (id/state):%s", kObjectTable, count, line);
}

const BYTE *FindTuning() {
    const BYTE *tuning = ObjectTuning();
    int source = tuning ? 1 : (g_fallback ? 2 : 0);
    if (!tuning && g_fallback) tuning = g_fileTuning;
    static int lastReason = -1, reasonLogs = 0;
    if (source != g_tuningSource || (source != 1 && g_lookupReason != lastReason && reasonLogs < 10)) {
        if (source != 1 && g_lookupReason != lastReason) ++reasonLogs;
        lastReason = g_lookupReason;
        if (source != 1) {
            static const char *const reasons[] = {"ok", "table code not verified", "id 858 not in the table",
                                                  "entry state is not 2", "entry has no object",
                                                  "object +0x5c / +0x60 empty", "data type at +2 is not 60",
                                                  "read fault"};
            Log(1, "tuning lookup of object %d failed: %s (entry %lu, state/first data word 0x%08lx, object 0x%08lx, "
                   "data 0x%08lx)", kExtensionObject, reasons[g_lookupReason & 7], g_lookupDetail[0], g_lookupDetail[1],
                g_lookupDetail[2], g_lookupDetail[3]);
            if (g_tableOk) LogObjectTable();
        }
        g_tuningSource = source;
        if (!tuning)
            Log(1, "tuning: object %d not loaded - no shadow power (as on the Xbox without the extension)",
                kExtensionObject);
        else
            Log(1, "tuning: %s - max %.1f, drain %.1f/s, refill %.1f/s (alt %.1f, delayed %.1f), restart above %.1f, "
                   "world %.3f, player %.3f",
                source == 1 ? "game object player_tru_dlc2_extension (858)"
                            : "FALLBACK copy of the file values (object 858 not found at run time)",
                Tune(tuning, kTuneMax), Tune(tuning, kTuneDrain), Tune(tuning, kTuneRefill),
                Tune(tuning, kTuneRefillAlt), Tune(tuning, kTuneRefillDelayed), Tune(tuning, kTuneRestart),
                Tune(tuning, kTuneWorld), Tune(tuning, kTunePlayer));
    }
    return tuning;
}

// HUD part of 0x823d81a0 / 0x823d8380: fraction, request display group 1, let the HUD manager react
void ShowMeter(float fraction) {
    if (!g_hudOk || !g_hudFeed) return;
    *kHudValue = fraction;
    if (!*kHudManager) return;
    g_hudGroup(1);
    g_hudUpdate();
}

// 0x823d7700: flags 0, value / start value 1000, latch 0 (the HUD fraction is written once the tuning is known)
void MeterInit() {
    g_meter.flags = 0;
    g_meter.startValue = kMeterStart;
    g_meter.latch = 0;
    g_meter.value = kMeterStart;
    g_meter.delay = kZero;
}

// 0x823d8120
bool CanStart(const BYTE *tuning) {
    if (!tuning) return false;
    if ((g_meter.flags & 0x200) && !(Tune(tuning, kTuneRestart) < g_meter.value)) return false;
    g_meter.flags &= ~0x200u;
    return true;
}

// 0x823d7d40 (the request list 0x823d7520 with only this request = both ramps to the tuning values in 33 ms)
void StartPower(const BYTE *tuning) {
    if (g_meter.flags & 1) return;
    // not ported: cinematic (0x82efb590) / 0x829ca6da / game state +0x628 > 0 checks, sounds 0x89 0x32 0x83 0x81
    // 0x87 0x88, the effect call (*0x82efc780)->vtbl[0xa4], message 0x1f4 to all instances
    if (!tuning) return;
    g_setPlayer(Tune(tuning, kTunePlayer), kRampSeconds);
    g_setWorld(Tune(tuning, kTuneWorld), kRampSeconds);
    g_meter.startValue = g_meter.value;
    g_meter.flags |= 1;
    g_meter.startTime = *kGameClock;
    Log(2, "shadow power ON (meter %.1f)", g_meter.value);
}

// 0x823d7fb8 (request cleared: both ramps back to 1.0 in 33 ms)
void StopPower(const char *why) {
    if (!(g_meter.flags & 1)) return;
    // not ported: effect off 0x823d9438 (flag 0x40), 0x823d9050 (flag 2), sounds 0x33 0x7e 0x82, message 0x1f5
    g_setPlayer(kOne, kRampSeconds);
    g_setWorld(kOne, kRampSeconds);
    if (!(kZero < g_meter.value)) g_meter.flags |= 0x200;
    g_meter.flags &= ~1u;
    g_meter.startValue = kMeterStart;
    g_meter.startTime = *kGameClock;
    Log(2, "shadow power OFF (%s, meter %.1f)", why, g_meter.value);
}

// 0x823d81a0
void Refill(const BYTE *tuning, float frames) {
    if (!tuning || (g_meter.flags & 0x90)) return;
    float before = g_meter.value;
    float dt = frames * kPerSecond;
    const bool alternate = false;       // game state +0xc94 != 0 (player state, PC offset not mapped) -> tuning +0x1c
    if (!alternate) {
        if (g_meter.delay <= kZero) {
            g_meter.value = Tune(tuning, kTuneRefill) * dt + before;
        } else {
            g_meter.delay -= dt;
            g_meter.value = Tune(tuning, kTuneRefillDelayed) * dt + before;
        }
    } else {
        g_meter.value = Tune(tuning, kTuneRefillAlt) * dt + before;
    }
    float max = Tune(tuning, kTuneMax);
    if (g_meter.value < max) {
        ShowMeter(g_meter.value / max);
    } else {
        g_meter.value = max;
        if (before < max) Log(3, "meter full");              // sound 0x7c not ported
        g_meter.delay = kZero;
    }
    // not ported: sounds 0x7f (crossing tuning +0x28), 0x85 / 0x86 (crossing +0x70 percent of max)
    if (Tune(tuning, kTuneHigh) <= g_meter.value) g_meter.flags |= 8;
}

// 0x823d8380
void Drain(const BYTE *tuning, float amount) {
    if (!tuning) return;
    float max = Tune(tuning, kTuneMax);
    float value = g_meter.value - amount;
    if (max - value < 0.0f) value = max;
    if (value < 0.0f) value = kZero;
    g_meter.value = value;
    ShowMeter(value / max);
    if (g_meter.value < Tune(tuning, kTuneHigh)) g_meter.flags &= ~8u;
    // not ported: sounds 0x7d (crossing tuning +0x30), 0x85 / 0x86
}

// 0x823d7a10, the part that runs the meter (on the Xbox called once per frame from the player update 0x824126d8;
// here from the pad poll, once per advance of the game clock)
void MeterTick(bool held) {
    const BYTE *tuning = FindTuning();
    g_tuning = tuning;
    // not ported: stop on cinematic / 0x829ca6da, zone query 0x412 (flag 0x80), the looping sound, effects
    // 0x823d77f0 / 0x823d94f8 (blur), the 0x82efb514 bit, the timed request +0x38
    float frames = *kFrameTime;
    if (!(frames >= 0.0f && frames < 30.0f)) frames = 0.0f;
    if (!(g_meter.flags & 0x90)) {
        if (held) {
            if (!g_meter.latch && CanStart(tuning)) {
                StartPower(tuning);
                g_meter.latch = 1;
            } else {
                g_meter.latch = 1;                            // sound 0x80 (refused) not ported
            }
        } else if (g_meter.latch == 1) {
            if (g_meter.flags & 1) StopPower("released");
            g_meter.latch = 0;
        }
        if (!(g_meter.flags & 1)) {
            Refill(tuning, frames);
        } else {
            if (kZero < g_meter.value && tuning) Drain(tuning, frames * kPerSecond * Tune(tuning, kTuneDrain));
            if (!(kZero < g_meter.value)) {
                g_meter.flags |= 0x200;
                StopPower("meter empty");
            }
        }
    }
}

DWORD WINAPI PadHook(DWORD index, PadState *state) {
    DWORD result = g_original ? g_original(index, state) : ERROR_DEVICE_NOT_CONNECTED;
    if (index > 3) return result;
    WORD before = g_lastButtons[index];
    g_lastButtons[index] = (result == ERROR_SUCCESS && state) ? static_cast<WORD>(state->wButtons & g_buttons) : 0;
    if (g_lastButtons[index] != before)
        Log(3, "pad %lu buttons 0x%04x (was 0x%04x)", index, g_lastButtons[index], before);
    DWORD clock = *kGameClock;
    if (clock == g_lastClock) return result;                  // same frame (another pad) or game clock stopped
    g_lastClock = clock;
    bool held = false;
    for (int i = 0; i < 4; ++i) held = held || g_lastButtons[i] != 0;
    MeterTick(held);
    return result;
}

// The game fills the pad pointer itself (GetProcAddress) - wait for it, swap it, and re-swap if the game ever
// writes the original back (e.g. after a device change).
DWORD WINAPI HookThread(LPVOID) {
    volatile LONG *slot = reinterpret_cast<volatile LONG *>(kPadPointer);
    for (int waited = 0; !g_stop; ++waited) {
        LONG current = *slot;
        LONG ours = static_cast<LONG>(reinterpret_cast<LONG_PTR>(&PadHook));
        if (current != 0 && current != ours) {
            g_original = reinterpret_cast<XInputGetStateFn>(static_cast<LONG_PTR>(current));
            if (InterlockedCompareExchange(slot, ours, current) == current)
                Log(1, "pad pointer 0x%08lx hooked (original XInputGetState 0x%08lx)", kPadPointer, current);
        } else if (current == 0 && waited == 600) {
            Log(1, "pad pointer still empty after 60 s - still waiting");
        }
        Sleep(current == ours ? 1000 : 100);
    }
    return 0;
}

// ---- 0.4: title-update conditions of Lara's link array that read the meter (translated) ----
// Called by the state machine on the game thread (cdecl, like every PC condition handler: agent, cache, record;
// result in al). The meter / tuning they read are the plugin's translation of the TU meter object (gameTracker+0x508)
// and of 0x82415518. The TU tests gameTracker+0x1244 (doppelganger player) first: these ids occur only in the DLC 2
// player's chart (doppelganger_casual.drm), whose init sets that byte on the Xbox (DoppelgangerInit) - the PC has no
// such field; the test is therefore met whenever the chart asks (named gap, docs Befund-Felsrinne).

typedef char(__cdecl *CondPredFn)(const BYTE *record);
typedef char(__cdecl *CondTemplateFn)(void *agent, void *cache, const BYTE *record, CondPredFn pred);
typedef char(__cdecl *CondCompareFn)(void *agent, void *cache, const BYTE *record, float value, int mode);

void LogCond(int slot, int id, const BYTE *record, int result) {
    if (InterlockedIncrement(&g_condCalls[slot]) == 1)
        Log(1, "condition %d is now evaluated (record value %d, flags %u) -> %d", id,
            *reinterpret_cast<const SHORT *>(record + 4), record[6], result);
    if (InterlockedExchange(&g_condLast[slot], result + 1) != result + 1)
        Log(2, "condition %d -> %d (meter %.1f, flags 0x%03lx)", id, result, g_meter.value, g_meter.flags);
}

// Xbox 0x8246e498 (predicate of 1056): meter fraction >= tuning +0x70 x 0.01 and the power active (flags bit 0)
char __cdecl Pred1056(const BYTE *) {
    const BYTE *tuning = g_tuning;                        // 0x82415518
    if (!tuning) return 0;
    double threshold = static_cast<double>(Tune(tuning, 0x70) * 0.01f);       // [0x820536ec] = 0.01
    double fraction = static_cast<double>(g_meter.value / Tune(tuning, kTuneMax));   // 0x823d8548
    if (fraction < threshold || !(g_meter.flags & 1)) return 0;
    return 1;
}

// Xbox 0x8246e528: r6 = 0x8246e498; b 0x82487718 (the template) - PC template tru+0x382d70
char __cdecl Cond1056(void *agent, void *cache, const BYTE *record) {
    char r = 0;
    __try {
        r = reinterpret_cast<CondTemplateFn>(kCondTemplate)(agent, cache, record, &Pred1056);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        r = 0;
    }
    LogCond(6, 1056, record, r ? 1 : 0);
    return r;
}

// Xbox 0x824703d0 (1049..1054): key must be 20; 1049-1051 compare the meter value (+8), 1052-1054 the fraction x 100
// ([0x8207d53c]); modes 0 / 1 / 2 (equal, >=, <=) through 0x82487348 = PC tru+0x383bd0; other ids: 0.0, mode 0
char __cdecl CondMeter(void *agent, void *cache, const BYTE *record) {
    int id = *reinterpret_cast<const SHORT *>(record + 2);
    int slot = (id >= 1049 && id <= 1054) ? id - 1049 : 7;
    char r = 0;
    const BYTE *tuning = g_tuning;
    if (tuning && *reinterpret_cast<const WORD *>(record) == 20) {   // TU: +0x1244, +0x508 set; record key 0x14
        unsigned idx = static_cast<unsigned>(id - 1049);
        float value = kZero;
        int mode = 0;
        if (idx <= 2) {
            value = g_meter.value;
        } else if (idx <= 5) {
            value = static_cast<float>(static_cast<double>(g_meter.value / Tune(tuning, kTuneMax)) * 100.0);
        }
        if (idx == 1 || idx == 4) mode = 1;
        else if (idx == 2 || idx == 5) mode = 2;
        __try {
            r = reinterpret_cast<CondCompareFn>(kCondCompare)(agent, cache, record, value, mode);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            r = 0;
        }
    }
    LogCond(slot, id, record, r ? 1 : 0);
    return r;
}

// copy of Lara's table with the TU records before the closing record; the builder's push operand points at the copy
DWORD g_laraConds[(kLaraCondCount + 16) * 3];

void RegisterLaraConditions() {
    if (!g_condEnabled) { Log(1, "Lara conditions: off ([Conditions] Enabled=0)"); return; }
    if (!BytesAt(kLaraReg, kLaraRegBytes, sizeof(kLaraRegBytes)) ||
        !BytesAt(kCondTemplate, kCondTemplateBytes, sizeof(kCondTemplateBytes)) ||
        !BytesAt(kCondCompare, kCondCompareBytes, sizeof(kCondCompareBytes))) {
        Log(0, "Lara conditions: registration / template / compare code does not match - not registered");
        return;
    }
    const DWORD *table = reinterpret_cast<const DWORD *>(kLaraCondTable);
    const DWORD *end = table + kLaraCondCount * 3;
    if (end[0] != 0 || end[1] != 0 || end[2] != kCondDefaultFn || table[0] != 10) {
        Log(0, "Lara conditions: table 0x%08lx is not the expected one (%lu records + closing) - not registered",
            kLaraCondTable, static_cast<DWORD>(kLaraCondCount));
        return;
    }
    struct { DWORD id; DWORD group; const void *fn; } const add[] = {
        {1049, 2000, &CondMeter}, {1050, 2000, &CondMeter}, {1051, 2000, &CondMeter}, {1052, 2000, &CondMeter},
        {1053, 2000, &CondMeter}, {1054, 2000, &CondMeter}, {1056, 2000, &Cond1056}};
    for (int i = 0; i < kLaraCondCount; ++i)
        for (const auto &a : add)
            if (table[i * 3] == a.id) {
                Log(0, "Lara conditions: id %lu already in the table - not registered", a.id);
                return;
            }
    // Precondition: every id must be in the generic registry. For an id found neither in Lara's tree nor in the
    // generic one, the loop reads a null node (tru+0x385258 -> 0x385265 cmp di,[edx] with edx = 0) - a crash. The
    // generic table is the builder's push operand tru+0x387343 (original 0x8b57e0); TruDoppelganger.asi (loaded
    // before us, alphabetical) points it at its copy with the TU ids. Register only if that copy holds all of ours.
    __try {
        DWORD generic = *reinterpret_cast<const DWORD *>(kGenericCondPush);
        if (generic == kGenericCondTable) {
            Log(0, "Lara conditions: the generic table is the original (TruDoppelganger.asi not active) - not "
                   "registered (the game would crash on ids the generic registry lacks)");
            return;
        }
        const DWORD *g = reinterpret_cast<const DWORD *>(generic);
        int found = 0;
        for (int i = 0; i < 1000 && g[i * 3] != 0; ++i)
            for (const auto &a : add)
                if (g[i * 3] == a.id) ++found;
        if (found != static_cast<int>(sizeof(add) / sizeof(add[0]))) {
            Log(0, "Lara conditions: the generic table 0x%08lx holds %d of our %d ids - not registered", generic, found,
                static_cast<int>(sizeof(add) / sizeof(add[0])));
            return;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "Lara conditions: generic table not readable - not registered");
        return;
    }
    memcpy(g_laraConds, table, kLaraCondCount * 3 * sizeof(DWORD));
    int n = kLaraCondCount;
    for (const auto &a : add) {
        g_laraConds[n * 3] = a.id;
        g_laraConds[n * 3 + 1] = a.group;
        g_laraConds[n * 3 + 2] = reinterpret_cast<DWORD>(a.fn);
        ++n;
    }
    memcpy(g_laraConds + n * 3, end, 3 * sizeof(DWORD));   // closing {0, 0, default}
    DWORD *operand = reinterpret_cast<DWORD *>(kLaraCondPush + 1);
    DWORD old = 0;
    if (!VirtualProtect(operand, 4, PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "Lara conditions: VirtualProtect failed (%lu) - not registered", GetLastError());
        return;
    }
    *operand = reinterpret_cast<DWORD>(g_laraConds);
    DWORD dummy = 0;
    VirtualProtect(operand, 4, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), operand, 4);
    Log(1, "Lara conditions: 1049-1054 (meter compare), 1056 (meter >= tuning +0x70 while active) added to the link "
           "array (copy 0x%08lx, %d records; generic registry has them via TruDoppelganger)",
        reinterpret_cast<DWORD>(g_laraConds), n);
}

void ReadOptions(const char *dir) {
    char ini[MAX_PATH];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruShadowPower.ini", dir);
    g_condEnabled = GetPrivateProfileIntA("Conditions", "Enabled", 1, ini);
    g_enabled = GetPrivateProfileIntA("ShadowPower", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("ShadowPower", "LogLevel", 1, ini);
    g_buttons = static_cast<WORD>(GetPrivateProfileIntA("ShadowPower", "Buttons", 0x0300, ini));
    g_hudFeed = GetPrivateProfileIntA("Meter", "HudBar", 1, ini);
    g_fallback = GetPrivateProfileIntA("Meter", "Fallback", 1, ini);
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruShadowPower.log", dir);
    ReadOptions(dir);
    InitFileTuning();
    Log(1, "TruShadowPower 0.4 loaded (enabled %d, buttons 0x%04x, HUD bar %d, fallback %d, conditions %d)",
        g_enabled, g_buttons, g_hudFeed, g_fallback, g_condEnabled);
    if (!g_enabled) { Log(1, "disabled by TruShadowPower.ini - nothing hooked"); return; }
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - not hooked", base, kImageBase); return; }
    if (!BytesAt(kCallSite, kCallBytes, sizeof(kCallBytes))) {
        Log(0, "pad poll call at 0x%08lx does not match (other tru.exe build?) - not hooked", kCallSite);
        return;
    }
    if (!BytesAt(kSetWorld, kSetterBytes, sizeof(kSetterBytes)) || !BytesAt(kSetWorld + 0x1d, kWorldRamp, 5) ||
        !BytesAt(kSetPlayer, kSetterBytes, sizeof(kSetterBytes)) || !BytesAt(kSetPlayer + 0x1d, kPlayerRamp, 5)) {
        Log(0, "time-scale setters at 0x%08lx / 0x%08lx do not match - not hooked", kSetWorld, kSetPlayer);
        return;
    }
    if (!BytesAt(kFrameDivSite, kFrameDivBytes, sizeof(kFrameDivBytes)) ||
        !BytesAt(kFrameDivConst, kFrameDivValue, sizeof(kFrameDivValue)) ||
        !BytesAt(kFrameStoreSite, kFrameStoreBytes, sizeof(kFrameStoreBytes))) {
        Log(0, "frame time store at 0x%08lx does not match - not hooked", kFrameStoreSite);
        return;
    }
    g_tableOk = BytesAt(kFindObject, kFindObjectBytes, sizeof(kFindObjectBytes)) &&
                BytesAt(kFindObjectLoop, kFindObjectLoopBytes, sizeof(kFindObjectLoopBytes));
    if (!g_tableOk) Log(0, "object table lookup at 0x%08lx does not match - tuning only from the fallback", kFindObject);
    g_hudOk = BytesAt(kHudValueGetter, kHudValueBytes, sizeof(kHudValueBytes)) &&
              BytesAt(kHudGroup, kHudGroupBytes, sizeof(kHudGroupBytes)) &&
              BytesAt(kHudUpdate, kHudUpdateBytes, sizeof(kHudUpdateBytes));
    if (!g_hudOk) Log(0, "HUD code at 0x%08lx / 0x%08lx / 0x%08lx does not match - meter runs without the HUD bar",
                      kHudValueGetter, kHudGroup, kHudUpdate);
    Log(3, "code checks passed (call site, setters, frame time, object table %d, HUD %d)", g_tableOk, g_hudOk);
    MeterInit();
    RegisterLaraConditions();
    HANDLE thread = CreateThread(nullptr, 0, HookThread, nullptr, 0, nullptr);
    if (thread) CloseHandle(thread);
    else Log(0, "CreateThread failed (%lu) - not hooked", GetLastError());
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        InitializeCriticalSection(&g_logLock);
        Start(instance);
    } else if (reason == DLL_PROCESS_DETACH) {
        g_stop = 1;
    }
    return TRUE;
}

// exported so the loader / tools can identify the plugin (the Ultimate ASI Loader needs no particular export)
extern "C" __declspec(dllexport) const char *TruShadowPowerVersion() {
    return "TruShadowPower 0.4 (translated TU meter, lookup diagnostics, Lara conditions 1049-1054 / 1056)";
}
