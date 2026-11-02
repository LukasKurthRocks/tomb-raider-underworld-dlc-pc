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
//
// 0.6 (2026-11-01, docs Befund-Felsrinne "Wall run: orientation, magnet and duration"): condition 1046 holds every loop
// transition of the wall run (chart DTP 20212 records 1477 / 1488 / 1492 / 1493: `{2000,1046,1}`, exits on 0). Its TU
// predicate 0x8246e400 reads, in doppelganger mode (gameTracker+0x1244), the meter object's flags bit 0 (power active;
// meter object +0x508 null -> 0), else the retail test (player +0x504)->+0x1fc bit 21. PC tru+0x3655c0 has only the
// retail test. Pred1046 replaces it (5-byte jump at its entry): doppelganger mode = TruDlc2Player's flag
// (TruDlc2PlayerDoppelganger, the TU's +0x1244), meter = this plugin's translation of the meter object.
//
// 0.7 (2026-11-02, docs Befund-Felsrinne "Condition 528 and the missing list"): condition 1055 was answered TRUE by the
// PC default handler (the id is in no PC table). Its only chart use is `{2000,1055,1,NOT}` in a transition of the second
// player machine, so the PC could never take it. TU 0x8246e488 = the template with predicate 0x8246e450: doppelganger
// mode -> meter flags bit 4, else (player)->+0x1fc bit 0x20000000 (PC writes that bit too: tru+0x315129). Meter flag 4
// is set only by the shadow look 0x823d8a80 (player anim event 5), and only while flag 2 is set; flag 2 is set only by
// 0x823d8978, the TU branch of state 1014 slot 0 (shadow strike) - both not ported, so in DLC 2 the translation answers
// 0, which is the TU's answer outside a shadow strike. Cond1055 joins the copy of Lara's condition table (option
// [Conditions] Cond1055).
//
// 0.8 (2026-11-02, docs Befund-Schattenkraft "Shadow-power look (title update) - translation"): the look of the power.
// No TU function of the meter group calls a post-process API; Start 0x823d7d40 and Stop 0x823d7fb8 fire PLAYER EVENTS
// by type through 0x82418158 (walk of the player object's event list, records of that type -> the player's anim-event
// callback) - on: 0x89, 0x32, (0x83 moving), 0x81 (meter full), 0x87 / 0x88 (above / below tuning +0x70 % of max);
// off: 0x33, then 0x7e (ran empty) or 0x82. The records are data of doppelganger_casual (object 857, DTP 20172):
// 0x32 starts the instance effects (model +0x18 effect 2 at two bones, model +0x38 record 14 as instance effect),
// 0x33 stops all of them. The PC has the walker with the same body: tru+0x318780 cdecl(instance, type, 0xff, channel
// 0). FireEvent calls it at the TU's places, in the TU's order ([Look] Enabled). Start / Stop also send message
// 0x1f4 / 0x1f5 to every instance whose query +0x11c answers 0x172 (PC instance list [0xd98d54], wake tru+0x1b2de0)
// - the level objects that react to the power, e.g. presumably dlc_fx_bloom (object 1038, states fx_on / fx_off)
// ([Look] Messages).
//
// 0.9 (2026-11-02, docs Befund-TU-Funktionen "Plugins 0.9"): the power only through the TU path, and the TU's
// adrenaline look.
//   * Tick = TU 0x823d7a10 as the TU calls it: the player update 0x824126d8 runs it only when gameTracker+0x1244 is set
//     (0x824128a4..0x824128b8) - so the tick (and with it every start) now needs TruDlc2Player's flag, which 0.2 clears
//     with every new tracker. The TU's own gates are translated: a running cinematic (TU inline test of
//     [0x82efb590] +0xdd / +0x2c = PC tru+0x53f00 on [0xe7f1c0]) or the byte 0x829ca6da (= retail 0x829ca5f1 = PC
//     0xfae8dd, set by tru+0x37bbf0 from GAMELOOP tru+0x1de480) stop the power and refuse a start; the start also needs
//     gameTracker+0x628 (health) > 0; the buttons count only while gameTrackerX+0xbc bit 0 (TU 0x82efb514 = PC
//     0xe7f144, the same test in the adrenaline tick TU 0x823defa8 = tru+0x318bd0) is clear, and that bit also stops
//     an active power; flag 0x80 = bool parameter 0x412 of Lara's current state (state machine gameTracker+0xf10)
//     blocks the meter; a refused start fires player event 0x80. A new tracker re-initialises the meter (TU: the meter
//     object belongs to the player data built by the player init). The TU reads LB / RB from the game's input records
//     (+0x1a70 / +0x1b30 & 4 of [[0x8286dd90]+0x18]->[0] = PC [[0xa02b68]+0x18]->[0]); no PC code reads these two
//     records, so the XInput state of the pad poll stays the button source by default ([ShadowPower] GameInput=1 reads
//     the game records instead; the log shows both while LB / RB is held). [ShadowPower] LegacyPadStart=1 restores the
//     0.8 tick (no doppelganger / cinematic gates).
//   * Look = TU adrenaline camera: 0x823d94f8 per tick (power on, meter > tuning +0x28, 0x823df8f8(player) = PC
//     tru+0x2f2800 with the TU's doppelganger branch, mode [gameTracker+0x500]+0x134 != 3, not flag 2) sets meter flag
//     0x40 through 0x823d9348 (world request slot 3 = tuning +0x38, HUD 0x9000 when player +0x1fc bit 10, event 0x39)
//     and clears it through 0x823d9438 (slot 3 empty, HUD &= ~0x9000, event 0x3a; also from Stop). In doppelganger mode
//     the TU's camera mode chooser (0x822acdd0 = tru+0x1e7fe0, site tru+0x1e80a9) picks mode 0x34 by meter flag 0x40
//     instead of player +0x1fc bit 27, and the adrenaline start / stop / tick (0x823ded18 / 0x823dee58 / 0x823defa8 =
//     tru+0x3189c0 / tru+0x318ad0 / tru+0x318bd0) read flag 0x40 for "active" and meter flag 2 for +0x1fc bit 21;
//     condition 1047 (TU predicate 0x8246e538 = PC tru+0x365600) the same. [Look] AdrenalineMode.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <math.h>

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
const float kNoRequest = -1.0f;         // [0x82052664] empty request slot
const float kPercent = 0.01f;           // [0x820536ec]
const float kHundred = 100.0f;          // [0x8207d53c]
const float kShortMove = 200.0f;        // [0x8206af90] frames value of a move of <= 2 steps (state 245)

// tuning struct offsets (floats) as the TU reads them
enum {
    kTuneMax = 0x10, kTuneDrain = 0x14, kTuneRefill = 0x18, kTuneRefillAlt = 0x1c, kTuneRefillDelayed = 0x20,
    kTuneRestart = 0x28, kTuneHigh = 0x2c, kTuneWorld = 0x3c, kTunePlayer = 0x40, kTuneDelay1018 = 0x24,
    kTuneTimedWorld = 0x54, kTuneTimedPlayer = 0x58, kTuneMoveSpeed = 0x68, kTuneMoveDistance = 0x6c, kTuneSize = 0x78
};

// copy of the same struct from the converted file (player_tru_dlc2_extension.drm, DTP 22497 +0xf0), used only when
// the object is not found at run time and Fallback=1 - logged as such
BYTE g_fileTuning[kTuneSize];

void InitFileTuning() {
    struct { int offset; float value; } const values[] = {
        {kTuneMax, 1000.0f}, {kTuneDrain, 200.0f}, {kTuneRefill, 200.0f}, {kTuneRefillAlt, 400.0f},
        {kTuneRefillDelayed, 75.0f}, {0x24, 6.0f}, {kTuneRestart, 150.0f}, {kTuneHigh, 300.0f}, {0x30, 200.0f},
        {0x34, 500.0f}, {0x38, 0.1f}, {kTuneWorld, 0.3f}, {kTunePlayer, 1.2f}, {0x44, 0.075f}, {0x48, 1.0f},
        {0x4c, 0.075f}, {0x50, 0.075f}, {kTuneTimedWorld, 1.0f}, {kTuneTimedPlayer, 0.02f}, {0x60, 25.0f},
        {0x64, 25.0f}, {kTuneMoveSpeed, 410.87f}, {kTuneMoveDistance, 1896.3f}, {0x70, 75.0f}, {0x74, 1.0f}};
    // (+0x5c is a pointer in the file - the sound / effect handle data, not used here)
    memset(g_fileTuning, 0, sizeof(g_fileTuning));
    g_fileTuning[0] = 1;                                     // u16 1, u16 type 60 as in the file
    g_fileTuning[2] = static_cast<BYTE>(kTuningType);
    for (const auto &v : values) memcpy(g_fileTuning + v.offset, &v.value, sizeof(float));
    // exact bit patterns of the two non-round values of the file (410.87 / 1896.3 are rounded above)
    const DWORD speed = 0x43cd6fa8, distance = 0x44ed0aaf;
    memcpy(g_fileTuning + kTuneMoveSpeed, &speed, sizeof(DWORD));
    memcpy(g_fileTuning + kTuneMoveDistance, &distance, sizeof(DWORD));
}

// the TU's meter object (allocated with the player data; the fields used here, with their Xbox offsets)
struct Meter {
    DWORD flags;                        // +0x04: 1 active, 8 at or above tuning +0x2c, 0x200 ran empty (restart only
                                        //        above tuning +0x28); 0x10 / 0x80 block the meter (not set here)
    float value;                        // +0x08
    float startValue;                   // +0x0c value when the power started (1000 after a stop)
    float delay;                        // +0x10 refill delay timer (no writer found in the TU besides the refill)
    BYTE latch;                         // +0x14 buttons seen held
    float requestTimer;                 // +0x38 frames until request slot 4 (condition 2401) is cleared
    DWORD startTime;                    // +0x3c game clock at the last start / stop
    // +0x40..+0x77: time-scale request list of 0x823d7520, 7 slots {player, world}; a value <= 0 = no request
    // (-1.0 [0x82052664] clears a slot). Slot 0 = the power (Start / Stop), 2 = shadow look (0x823d8a80, not ported),
    // 4 = timed request of condition 2401, 5 = state 1018.
    float request[7][2];
};

// options (TruShadowPower.ini)
int g_enabled = 1;
int g_logLevel = 1;                     // 0 errors, 1 info, 2 every start / stop, 3 debug
WORD g_buttons = 0x0300;                // LB 0x0100 | RB 0x0200 (Xbox: either); LB also sprints on PC
int g_hudFeed = 1;                      // [Meter] HudBar
int g_fallback = 1;                     // [Meter] Fallback: file copy of the tuning when the object is not loaded
int g_legacyPadStart = 0;               // 0.9 [ShadowPower] LegacyPadStart: 1 = the 0.8 tick (no TU gates)
int g_gameInput = 0;                    // 0.9 [ShadowPower] GameInput: 1 = LB / RB from the game's input records
int g_adrenalineMode = 1;               // 0.9 [Look] AdrenalineMode: TU 0x823d94f8 group + mode chooser / adrenaline

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
int g_statesEnabled = 1;                  // [States] Enabled (0.5): TU states 243 / 245 / 1018, conditions 1048 / 2401,
                                          // activities 1009 / 1039
volatile LONG g_condCalls[9];             // first-call log per handler (1049..1054, 1056, -, 1055)
volatile LONG g_condLast[9];              // last result per handler (+1, 0 = none yet) for LogLevel 2

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

// 0x823d7700: flags 0, value / start value 1000, latch 0 (the HUD fraction is written once the tuning is known).
// 0.5: the request slots and the timer are not set by 0x823d7700 (the meter object is allocated elsewhere, not
// inspected); they start empty here (-1.0, the TU's "no request" value) and 0.
void MeterInit() {
    g_meter.flags = 0;
    g_meter.startValue = kMeterStart;
    g_meter.latch = 0;
    g_meter.value = kMeterStart;
    g_meter.delay = kZero;
    g_meter.requestTimer = kZero;
    for (int i = 0; i < 7; ++i) g_meter.request[i][0] = g_meter.request[i][1] = kNoRequest;
}

// 0x823d7520 (request selector, argument meter +0x40): the highest slot with a player value > 0 sets the player
// ramp, the highest with a world value > 0 the world ramp; none -> 1.0. The TU writes the ramp structs directly
// (target, 33 ms, current value, clock) - the PC setters write the same ramps (0.3).
void Selector() {
    bool player = false, world = false;
    float playerTarget = kOne, worldTarget = kOne;
    for (int i = 6; i >= 0; --i) {
        if (!player && kZero < g_meter.request[i][0]) { player = true; playerTarget = g_meter.request[i][0]; }
        if (!world && kZero < g_meter.request[i][1]) { world = true; worldTarget = g_meter.request[i][1]; }
        if (player && world) break;
    }
    g_setPlayer(playerTarget, kRampSeconds);
    g_setWorld(worldTarget, kRampSeconds);
    Log(3, "selector: player %.3f, world %.3f", playerTarget, worldTarget);
}

// ---- 0.8: player events of Start / Stop (TU 0x82418158 = PC tru+0x318780) ----
// TU 0x82418158(player 0x82efb464, type, 0xff): every record of the player object's event list (instance +0x10 ->
// object +4) with that type byte (+4), channel 0 (h & 0xc00), skip bit (h & 4) clear, anim controller +0x5c == 0,
// kind 0 / 3 only if controller +0x4c & 0x40, kind 1 only if & 0x80 -> anim-event callback (msg 7). PC tru+0x318780
// (retail, same tests) takes the channel as a 4th argument ((arg ^ h) & 0xc00 == 0) - 0 = the TU's test.
typedef void(__cdecl *PlayerEventFn)(void *instance, int type, int param, int channel);
const DWORD kPlayerEvent = 0x00718780;
const char *const kPlayerEventHex = "51 817c240cff000000 0f84f2000000 8b442408 56 8b7010 8b8080020000 8b4814";
const DWORD kPlayerEventType = 0x007187d0;      // movzx ecx, byte [esi+4]; cmp ecx, [esp+0x1c] (the type byte)
const char *const kPlayerEventTypeHex = "0fb64e04 3b4c241c";
const DWORD kPlayerEventCall = 0x00718858;      // push 7; push ebp x3; push edx; call 0x7181a0 (anim-event callback)
const char *const kPlayerEventCallHex = "6a07 55 55 55 52 e83df9ffff";
int g_lookEnabled = 1;                          // [Look] Enabled
bool g_lookOk = false;                          // walker verified
volatile LONG g_lookStarts = 0;
int Doppelganger();                             // TruDlc2Player's flag (TU gameTracker+0x1244), defined below

// fire one TU player event on the player instance (TU 0x82efb464 = PC 0xe7f094); returns false when not fired.
// On the Xbox Start / Stop exist only with the meter object (gameTracker+0x508), i.e. for the DLC 2 doppelganger
// player - the look is therefore limited to doppelganger mode (the plugin's slow motion itself stays as in 0.7).
bool FireEvent(int type) {
    if (!g_lookOk || !g_lookEnabled || !Doppelganger()) return false;
    void *player = *reinterpret_cast<void *const *>(0x00e7f094);
    if (!player) return false;
    __try {
        reinterpret_cast<PlayerEventFn>(kPlayerEvent)(player, type, 0xff, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "player event 0x%02x (tru+0x318780): access fault - skipped", type);
        return false;
    }
    return true;
}

// TU 0x823d7f18..0x823d7fa0 (Start, message 0x1f4) / 0x823d8080.. (Stop, message 0x1f5): every instance of the list
// 0x828aaf18 (+4 first, +8 next - read before the calls) whose query function +0x11c answers 0x172 gets 0x8226fe00
// (wake) and then message (+0x120)(instance, msg, 0). PC: list head [0xd98d54] (the walk tru+0x1b53e0, same +8 next,
// +0x110 / +0x11c / +0x120 layout), wake tru+0x1b2de0 = 0x8226fe00 (same body). All cdecl.
typedef int(__cdecl *InstQueryFn)(void *instance, int id);
typedef int(__cdecl *InstMessageFn)(void *instance, int msg, int arg);
typedef void(__cdecl *InstWakeFn)(void *instance);
const DWORD kInstanceHead = 0x00d98d54;
const DWORD kInstWalk = 0x005b53ea;             // mov esi, [0xd98d54] in tru+0x1b53e0
const char *const kInstWalkHex = "8b35548dd900 85f6";
const DWORD kInstNext = 0x005b5563;             // mov esi, [esi+8]; test esi, esi
const char *const kInstNextHex = "8b7608 85f6";
const DWORD kInstQuery = 0x005b5425;            // mov eax, [esi+0x11c]; test; je; push 0x22; push esi; call eax
const char *const kInstQueryHex = "8b861c010000 85c0 7410 6a22 56 ffd0 83c408";
const DWORD kInstWake = 0x005b2de0;             // = TU 0x8226fe00
const char *const kInstWakeHex = "56 8b742408 8b4618 a801 744e 83e0fe 894618 8d8610010000 85c0 741c 57 8bbe20010000 "
                                 "85ff 7410 56 e8d3ffffff 6a00 6a13 56 ffd7 83c410";
int g_lookMessages = 1;                         // [Look] Messages
bool g_msgOk = false;                           // instance list / query / wake verified

// returns the number of instances that got the message, -1 when not sent
int BroadcastPowerMessage(int msg) {
    if (!g_msgOk || !g_lookEnabled || !g_lookMessages || !Doppelganger()) return -1;
    int sent = 0;
    __try {
        BYTE *inst = *reinterpret_cast<BYTE *const *>(kInstanceHead);
        for (int guard = 0; inst && guard < 4096; ++guard) {
            BYTE *next = *reinterpret_cast<BYTE *const *>(inst + 8);           // r29 = [r31+8] before the calls
            InstQueryFn query = *reinterpret_cast<InstQueryFn *>(inst + 0x11c);
            if (inst + 0x110 && query && query(inst, 0x172)) {
                InstMessageFn message = *reinterpret_cast<InstMessageFn *>(inst + 0x120);
                if (message) {
                    reinterpret_cast<InstWakeFn>(kInstWake)(inst);
                    message(inst, msg, 0);
                    ++sent;
                }
            }
            inst = next;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "message 0x%03x to the instances: access fault after %d - skipped", msg, sent);
        return -1;
    }
    return sent;
}

// 0.9, defined below: the TU's start gates (cinematic / 0x829ca6da / health) and the flag-0x40 clear 0x823d9438
bool TuStartRefused();
void Clear40();

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
    // 0.9: no cinematic (0x82efb590 = PC [0xe7f1c0] via tru+0x53f00), 0x829ca6da (PC 0xfae8dd) clear and gameTracker
    // +0x628 > 0 (0x823d7d68..0x823d7dd4); not with LegacyPadStart=1. Not ported: the camera manager call
    // (*0x82efc780)->vtbl[0xa4] (= 0x822a9e58: camera +0x7c |= 2, selects other camera curves - docs L9)
    if (!g_legacyPadStart && TuStartRefused()) return;
    if (!tuning) return;
    g_meter.request[0][0] = Tune(tuning, kTunePlayer);          // +0x40 = tuning +0x40
    g_meter.request[0][1] = Tune(tuning, kTuneWorld);           // +0x44 = tuning +0x3c
    Selector();
    // 0.8: 0x823d7e10..0x823d7efc - the player events of the start, in the TU's order
    char fired[64] = "";
    int n = 0;
    auto fire = [&](int type) {
        if (FireEvent(type) && n < static_cast<int>(sizeof(fired)) - 6)
            n += _snprintf_s(fired + n, sizeof(fired) - n, _TRUNCATE, " 0x%02x", type);
    };
    fire(0x89);
    fire(0x32);
    // 0x83 when the length of gameTracker+0x1f0 > 10.0 [0x8205262c]: not ported (PC gameTracker +0x1f0 not mapped;
    // its only record in DTP 20172 is sound 0x1cd)
    float max = Tune(tuning, kTuneMax);
    if (g_meter.value == max) fire(0x81);                       // [r28+8] == tuning +0x10
    float high = Tune(tuning, 0x70) * kPercent * max;           // tuning +0x70 x [0x820536ec] x tuning +0x10
    if (!(g_meter.value < high)) fire(0x87);
    else fire(0x88);
    g_meter.startValue = g_meter.value;
    g_meter.flags |= 1;
    int sent = BroadcastPowerMessage(0x1f4);                    // 0x823d7f18..0x823d7fa0
    g_meter.startTime = *kGameClock;
    Log(2, "shadow power ON (meter %.1f)", g_meter.value);
    if (g_lookOk && g_lookEnabled) {
        if (InterlockedIncrement(&g_lookStarts) == 1)
            Log(1, "shadow look on: first start, player events%s fired (TU 0x823d7d40 -> 0x82418158 = tru+0x318780), "
                   "message 0x1f4 to %d instances", n ? fired : " - none (no player or not doppelganger mode)", sent);
        else
            Log(2, "shadow look on: player events%s, message 0x1f4 to %d instances", n ? fired : " - none (no player or not doppelganger mode)",
                sent);
    }
}

// 0x823d7fb8 (request cleared: both ramps back to 1.0 in 33 ms)
void StopPower(const char *why) {
    if (!(g_meter.flags & 1)) return;
    // 0.9: flag 0x40 -> 0x823d9438 (Clear40, translated with [Look] AdrenalineMode); not ported: flag 2 -> 0x823d9050
    // (flag 2 is set only by the shadow strike 0x823d8978, not ported - never set here)
    if (g_meter.flags & 0x40) Clear40();
    g_meter.request[0][0] = g_meter.request[0][1] = kNoRequest;
    Selector();
    // 0.8: 0x823d7ffc..0x823d8068 - event 0x33, then 0x7e (ran empty, flag 0x200) or 0x82
    bool fired33 = FireEvent(0x33);
    bool left = kZero < g_meter.value;
    if (!left) g_meter.flags |= 0x200;
    int second = left ? 0x82 : 0x7e;
    bool fired2 = FireEvent(second);
    g_meter.flags &= ~1u;
    g_meter.startValue = kMeterStart;
    int sent = BroadcastPowerMessage(0x1f5);                    // 0x823d8080..
    g_meter.startTime = *kGameClock;
    Log(2, "shadow power OFF (%s, meter %.1f)", why, g_meter.value);
    if (g_lookOk && g_lookEnabled)
        Log(2, "shadow look off: player events%s%s%s, message 0x1f5 to %d instances", fired33 ? " 0x33" : "",
            fired2 ? (left ? " 0x82" : " 0x7e") : "", (fired33 || fired2) ? "" : " - none (no player or not doppelganger mode)", sent);
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

// 0x823d7a10 as translated up to 0.8 (kept for [ShadowPower] LegacyPadStart=1): runs in every level, without the
// TU's doppelganger / cinematic gates (on the Xbox called once per frame from the player update 0x824126d8; here from
// the pad poll, once per advance of the game clock). 0.9's MeterTick (below) is the TU path.
void LegacyMeterTick(bool held) {
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
    // 0x823d7cf8.. (outside the 0x90 test): the timed request of condition 2401 counts down in unscaled frames;
    // at 0 slot 4 is cleared and the selector runs
    if (kZero < g_meter.requestTimer) {
        g_meter.requestTimer = g_meter.requestTimer - frames;
        if (g_meter.requestTimer <= kZero) {
            g_meter.request[4][0] = g_meter.request[4][1] = kNoRequest;
            Selector();
            g_meter.requestTimer = kZero;
            Log(2, "timed request (2401) ended");
        }
    }
}

void MeterTick(bool padHeld);                // 0.9: the TU tick (defined below)

XInputGetStateFn g_realXInput = nullptr;    // the real XInputGetState (xinput* module), for the re-entry guard
__declspec(thread) int g_inPadHook = 0;

DWORD WINAPI PadHook(DWORD index, PadState *state) {
    if (g_inPadHook) {                          // another plugin's hook called back into us: break the loop
        return g_realXInput ? g_realXInput(index, state) : ERROR_DEVICE_NOT_CONNECTED;
    }
    g_inPadHook = 1;
    DWORD result = g_original ? g_original(index, state) : ERROR_DEVICE_NOT_CONNECTED;
    g_inPadHook = 0;
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

// true when the address lies in an xinput*.dll (the real XInputGetState, not another plugin's hook)
bool InXInputModule(LONG address) {
    HMODULE module = nullptr;
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            reinterpret_cast<LPCSTR>(static_cast<LONG_PTR>(address)), &module))
        return false;
    char path[MAX_PATH] = {0};
    if (!GetModuleFileNameA(module, path, MAX_PATH)) return false;
    const char *name = strrchr(path, '\\');
    name = name ? name + 1 : path;
    return _strnicmp(name, "xinput", 6) == 0;
}

// The game fills the pad pointer itself (GetProcAddress) - wait for it and chain in front of whatever is there
// (the real XInputGetState or another of our plugins: TruLink, TruMenu). Re-hook later only when the slot holds the
// real XInputGetState again (the game rewrote it, e.g. after a device change) - never just because it is "not ours",
// or two plugins would keep re-hooking each other.
DWORD WINAPI HookThread(LPVOID) {
    volatile LONG *slot = reinterpret_cast<volatile LONG *>(kPadPointer);
    bool hookedOnce = false;
    for (int waited = 0; !g_stop; ++waited) {
        if (!g_realXInput) {                    // resolve the real one for the re-entry guard
            const char *dlls[] = {"xinput1_3.dll", "xinput9_1_0.dll", "xinput1_4.dll"};
            for (int d = 0; d < 3 && !g_realXInput; ++d) {
                HMODULE xinput = GetModuleHandleA(dlls[d]);
                if (xinput)
                    g_realXInput = reinterpret_cast<XInputGetStateFn>(GetProcAddress(xinput, "XInputGetState"));
            }
        }
        LONG current = *slot;
        LONG ours = static_cast<LONG>(reinterpret_cast<LONG_PTR>(&PadHook));
        if (current != 0 && current != ours && (!hookedOnce || InXInputModule(current))) {
            if (InXInputModule(current)) g_realXInput = reinterpret_cast<XInputGetStateFn>(static_cast<LONG_PTR>(current));
            g_original = reinterpret_cast<XInputGetStateFn>(static_cast<LONG_PTR>(current));
            if (InterlockedCompareExchange(slot, ours, current) == current) {
                hookedOnce = true;
                Log(1, "pad pointer 0x%08lx hooked (previous 0x%08lx%s)", kPadPointer, current,
                    g_realXInput && current == reinterpret_cast<LONG>(g_realXInput) ? ", XInputGetState" : ", another hook");
            }
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

// ---- 0.5: title-update states / conditions / activities of Lara (docs Befund-Schattenkraft "TU states for Lara") ----
// PC building blocks, each verified by its bytes at load (kTuBlocks below). thiscall functions are called through
// __fastcall pointers (ecx = this, edx unused, the rest on the stack, callee cleans - the thiscall layout).
typedef void *(__fastcall *ParamNodeFn)(void *agent, int, int id);              // 0x783f50 = TU 0x82482d28
typedef void *(__fastcall *ParamFindFn)(void *node, int, int id);               // 0x784b30 = TU 0x82488680
typedef float(__cdecl *ParamFloatFn)(const void *record);                       // 0x783680 = TU 0x82484a08
typedef char(__fastcall *ParamBoolFn)(void *node, int, int id, char *out);      // 0x784c20 = TU 0x823d7230 tail
typedef void *(__cdecl *AnimFramesFn)(int *out, void *agent);                   // 0x75f3e0 = TU 0x82463af8 (flag 0)
typedef void(__fastcall *ChanMoveFn)(void *chan, int, const float *vec, float frames);   // 0x438d70 mode 1 /
                                                                                          // 0x438d00 mode 2
typedef void(__fastcall *ChanMoveAnimFn)(void *chan, int, const float *vec);    // 0x43e400 mode 1, frames of the anim

const DWORD kParamNode = 0x00783f50, kParamFind = 0x00784b30, kParamFloat = 0x00783680, kParamBool = 0x00784c20;
const DWORD kAnimFrames = 0x0075f3e0, kChanMode1 = 0x00438d70, kChanMode1Anim = 0x0043e400, kChanMode2 = 0x00438d00;
const DWORD kGameTrackerPtr = 0x00fadb58;   // TU 0x829892b0
const DWORD kPlayerPtr = 0x00e7f094;        // TU 0x82efb464 (player instance; frame-time block + 0xc)

struct CodeCheck { DWORD address; const char *bytes; };   // hex string, spaces ignored
const CodeCheck kTuBlocks[] = {
    {0x00783f50, "56 8bf1 8b8620050000 85c0"},                          // param node, cache agent +0x520
    {0x00784b30, "0fb701 53 56 57 8b7c2410 33db"},                       // param find
    {0x00783680, "51 8b442408 d9ee 0fbf4802"},                           // float value (switch on type +2)
    {0x00783770, "8b542404 0fbf4a02 32c0 83e902"},                       // bool value (types 2 / 0x10 / 0x29)
    {0x00784c20, "8b442404 50 e806ffffff 85c0"},                         // bool param of a node
    {0x0075f3e0, "56 57 8b7c2410 681b010000 681b010000"},                // anim frame count (param 0x11b)
    {0x0075f470, "83ec08 56 57 8b7c241c 8b4704 0fb77002 8b4f08 69f620030000 8b9180020000 037214"},  // channel
    {0x00438970, "0fb681f8000000 6bc070 038180000000"},                  // anim entry: chan +0x80 + 0x70 x +0xf8
    {0x00438d70, "55 8bec 83e4f0 83ec10 d9450c 8bc1 8b4d08 0f2801 0f294010"}, {0x00438db1, "c7402401000000"},
    {0x0043e400, "55 8bec 83e4f0 83ec20 8bc1 8b8880000000"}, {0x0043e464, "c7402401000000"},
    {0x00438d00, "55 8bec 83e4f0 83ec10 f30f100534118400 d9450c"}, {0x00438d59, "c7402402000000"},
    {0x00741764, "8b0d94f0e700 0f8599010000 8b8190000000"},               // player +0x90 matrix (row +0x10)
    {0x00764e79, "8b0d58dbfa00"}, {0x00764e85, "39b11c030000"}, {0x00764e99, "80b92003000000"},  // gt +0x31c/+0x320
    {0x0075e0e0, "a158dbfa00 8b8804050000"},                             // gt +0x504 = player instance
    {0x006457a0, "c3"},                                                  // print stub (activity 1039)
};

bool HexBytesAt(DWORD address, const char *hex) {
    BYTE buf[200];
    size_t n = 0;
    for (const char *p = hex; *p && n < sizeof(buf);) {
        if (*p == ' ') { ++p; continue; }
        char two[3] = {p[0], p[1], 0};
        buf[n++] = static_cast<BYTE>(strtoul(two, nullptr, 16));
        p += 2;
    }
    return BytesAt(address, buf, n);
}

bool g_tuStatesOk = false;          // all kTuBlocks verified
int g_gt1280 = 0;                   // TU-only gameTracker+0x1280 (move step count of 244 / 245, read by 1048) - the
                                    // PC uses +0x1280 for other data, so the translation keeps it here

BYTE *GameTracker() { return *reinterpret_cast<BYTE *const *>(kGameTrackerPtr); }

// agent motion channel: (agent+8)->+0x280->+0x14 + 0x320 x (agent+4)->+2 (TU and PC tru+0x35f470)
BYTE *Channel(const BYTE *agent) {
    const BYTE *instance = *reinterpret_cast<const BYTE *const *>(agent + 8);
    const BYTE *anim = *reinterpret_cast<const BYTE *const *>(instance + 0x280);
    WORD index = *reinterpret_cast<const WORD *>(*reinterpret_cast<const BYTE *const *>(agent + 4) + 2);
    return *reinterpret_cast<BYTE *const *>(anim + 0x14) + 0x320 * index;
}

// animation entry of a channel: chan->+0x80 + 0x70 x chan->+0xf8 (u8) - TU inline, PC tru+0x38970
const BYTE *AnimEntry(const BYTE *chan) {
    return *reinterpret_cast<const BYTE *const *>(chan + 0x80) + 0x70 * chan[0xf8];
}

// TU 0x82482d28 + 0x82488680 + 0x82484a08. The TU does not test the record for null before reading its type (a
// missing parameter would read guest address 2); a missing record answers 0.0 here - the getter's default value.
float ParamFloat(void *agent, int id) {
    void *node = reinterpret_cast<ParamNodeFn>(kParamNode)(agent, 0, id);
    if (!node) return kZero;
    void *record = reinterpret_cast<ParamFindFn>(kParamFind)(node, 0, id);
    if (!record) {
        static volatile LONG missing = 0;
        if (InterlockedIncrement(&missing) <= 5) Log(1, "state parameter 0x%x not in the current state (0.0 used)", id);
        return kZero;
    }
    return reinterpret_cast<ParamFloatFn>(kParamFloat)(record);
}

// TU 0x823d7230(agent, id, &out) = 0x82482d28 + 0x82488680 + (record ? out = 0x82484b88(record))
void ParamBool(void *agent, int id, char *out) {
    void *node = reinterpret_cast<ParamNodeFn>(kParamNode)(agent, 0, id);
    if (node) reinterpret_cast<ParamBoolFn>(kParamBool)(node, 0, id, out);
}

// first-call / rate-limited logging of the new handlers (proves in a test that a state / condition is entered)
struct Probe { const char *name; volatile LONG calls; DWORD lastTick; LONG lastLogged; };
Probe g_probes[] = {
    {"state 243 slot 0 (move to gameTracker+0x1270)"}, {"state 245 slot 0 (move tuning +0x6c along player row)"},
    {"state 245 slot 3 (stop at the current position)"}, {"state 1018 slot 0 (meter cost / world request)"},
    {"state 1018 slot 1 (meter cost / world request)"}, {"state 1018 slot 2 (clear request 5)"},
    {"condition 1048 (step count x 100 <= animation time)"}, {"condition 2401 (timed time-scale request)"},
    {"activity 1009 (player +0xc8 = record +4)"}, {"activity 1039 (print stub)"}};
enum { kP243, kP245a, kP245d, kP1018a, kP1018b, kP1018c, kP1048, kP2401, kP1009, kP1039 };

void Hit(int probe, const char *fmt = nullptr, double a = 0.0, double b = 0.0, double c = 0.0) {
    Probe &p = g_probes[probe];
    LONG n = InterlockedIncrement(&p.calls);
    char detail[160] = "";
    if (fmt) _snprintf_s(detail, sizeof(detail), _TRUNCATE, fmt, a, b, c);
    if (n == 1) {
        Log(1, "%s is now entered%s%s", p.name, detail[0] ? ": " : "", detail);
        p.lastTick = GetTickCount();
        p.lastLogged = 1;
        return;
    }
    DWORD now = GetTickCount();
    if (g_logLevel >= 3 || (g_logLevel >= 2 && now - p.lastTick >= 500)) {
        Log(2, "%s (call %ld, %ld since last line)%s%s", p.name, n, n - p.lastLogged, detail[0] ? ": " : "", detail);
        p.lastTick = now;
        p.lastLogged = n;
    }
}

// state 243, slot 0 = TU 0x82464180: v1 = gameTracker+0x1270; b 0x82463eb8 (TU-new). 0x82463eb8: unless the bool
// parameter 0x11d is set: n = 0x82463af8(agent, flag 0) (= PC 0x75f3e0, parameter 0x11b); n > 0 -> channel +0x10 =
// v1, +0x00 = 0 vector [0x8207db30], +0x20 = n, +0x24 = 1 (= PC 0x438d70); else the same with the animation's frame
// count (+0x80 -> +0x24: s16 +0x34 x +0x32) (= PC 0x43e400).
void __cdecl State243(BYTE *agent) {
    __try {
        float *target = reinterpret_cast<float *>(GameTracker() + 0x1270);
        BYTE *chan = Channel(agent);
        char keep = 0;
        ParamBool(agent, 0x11d, &keep);
        if (keep) { Hit(kP243, "parameter 0x11d set - nothing done"); return; }
        int n = 0;
        reinterpret_cast<AnimFramesFn>(kAnimFrames)(&n, agent);
        if (n > 0)
            reinterpret_cast<ChanMoveFn>(kChanMode1)(chan, 0, target, static_cast<float>(n));
        else
            reinterpret_cast<ChanMoveAnimFn>(kChanMode1Anim)(chan, 0, target);
        Hit(kP243, "frames %.0f, target %.1f %.1f", n, target[0], target[1]);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 243: access fault - skipped");
    }
}

// TU "busy" test of 245 (both slots): gameTracker+0x31c set, byte +0x320 set and (+0x31c)->u16 +0x40 == 2 or
// u16 +0x32 == 3
bool Busy245(const BYTE *gt) {
    if (!gt) return false;
    const BYTE *p = *reinterpret_cast<const BYTE *const *>(gt + 0x31c);
    if (!p || !gt[0x320]) return false;
    return *reinterpret_cast<const WORD *>(p + 0x40) == 2 || *reinterpret_cast<const WORD *>(p + 0x32) == 3;
}

// state 245, slot 0 = TU 0x824645d8: unless busy: target = player position (+0x20) + (row +0x10 of the player's
// matrix (+0x90) x -1.0) x tuning +0x6c; length = |target - position| (vrsqrtefp + one Newton step on the Xbox, 0
// for 0); n = (int)floor(length / tuning +0x68); n > 2: gameTracker+0x1280 = n, frames = n x 100.0; else +0x1280 = 2,
// frames = 200.0; channel +0x00 = target, +0x10 = (0, 0, 0, 1), +0x20 = frames, +0x24 = 2 (= PC 0x438d00).
void __cdecl State245(BYTE *agent) {
    __try {
        BYTE *gt = GameTracker();
        if (Busy245(gt)) { Hit(kP245a, "busy (gameTracker+0x31c) - nothing done"); return; }
        BYTE *chan = Channel(agent);
        const BYTE *tuning = gt ? g_tuning : nullptr;
        if (!tuning) { Log(1, "state 245: no tuning - skipped (the Xbox would read address 0x68)"); return; }
        float speed = Tune(tuning, kTuneMoveSpeed);
        float distance = Tune(tuning, kTuneMoveDistance);
        const BYTE *player = *reinterpret_cast<const BYTE *const *>(kPlayerPtr);
        const float *row = reinterpret_cast<const float *>(*reinterpret_cast<const BYTE *const *>(player + 0x90) + 0x10);
        const float *position = reinterpret_cast<const float *>(player + 0x20);
        __declspec(align(16)) float target[4];
        for (int i = 0; i < 4; ++i) target[i] = (row[i] * kNoRequest) * distance + position[i];   // [0x82052664]
        float d[3] = {target[0] - position[0], target[1] - position[1], target[2] - position[2]};
        float squared = d[0] * d[0] + d[1] * d[1] + d[2] * d[2];
        float length = squared == kZero ? squared : sqrtf(squared);
        int n = static_cast<int>(static_cast<float>(floor(static_cast<double>(length / speed))));
        float frames;
        if (n > 2) {
            g_gt1280 = n;
            frames = static_cast<float>(n) * kHundred;
        } else {
            g_gt1280 = 2;
            frames = kShortMove;
        }
        reinterpret_cast<ChanMoveFn>(kChanMode2)(chan, 0, target, frames);
        // direction of the move (-row): (0, 0, +-1) = vertical (wall run), otherwise horizontal
        Hit(kP245a, "direction %.2f %.2f %.2f", -row[0], -row[1], -row[2]);
        Log(2, "state 245: steps %d, length %.1f, frames %.0f, from %.1f %.1f %.1f to %.1f %.1f %.1f", g_gt1280, length,
            frames, position[0], position[1], position[2], target[0], target[1], target[2]);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 245: access fault - skipped");
    }
}

// state 245, slot 3 = TU 0x824647d0: only when busy: channel +0x00 = instance (agent+8) position +0x20, +0x10 =
// (0, 0, 0, 1), +0x20 = animation entry +0x28 - 1.0, +0x24 = 2 (= PC 0x438d00)
void __cdecl State245Slot3(BYTE *agent) {
    __try {
        if (!Busy245(GameTracker())) return;
        BYTE *chan = Channel(agent);
        const BYTE *instance = *reinterpret_cast<const BYTE *const *>(agent + 8);
        float frames = *reinterpret_cast<const float *>(AnimEntry(chan) + 0x28) - kOne;
        reinterpret_cast<ChanMoveFn>(kChanMode2)(chan, 0, reinterpret_cast<const float *>(instance + 0x20), frames);
        Hit(kP245d, "frames %.2f", frames);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 245 slot 3: access fault - skipped");
    }
}

// state 1018, slots 0 and 1 = TU 0x82465078 (gameTracker+0x1244 / +0x508 taken as present, see 0.4): parameters
// 0x410 (amount), 0x411 (percent), bool 0x414; amount > 0 -> Drain(amount) (0x823d8380), else percent > 0 ->
// Drain(max x percent x 0.01) (0x823d84d0); 0x414 set -> refill delay = tuning +0x24; parameter 0x413 > 0 -> world
// request slot 5 = it, else slot 5 cleared; selector.
void State1018(BYTE *agent, int probe) {
    __try {
        float amount = ParamFloat(agent, 0x410);
        float percent = ParamFloat(agent, 0x411);
        char delay = 0;
        ParamBool(agent, 0x414, &delay);
        const BYTE *tuning = g_tuning;
        if (kZero < amount) {
            Drain(tuning, amount);
        } else if (kZero < percent) {
            if (tuning) Drain(tuning, Tune(tuning, kTuneMax) * (percent * kPercent));
        }
        if (delay && tuning) g_meter.delay = Tune(tuning, kTuneDelay1018);
        float world = ParamFloat(agent, 0x413);
        if (kZero < world) {
            g_meter.request[5][1] = world;
        } else {
            g_meter.request[5][0] = g_meter.request[5][1] = kNoRequest;
        }
        Selector();
        Hit(probe, "cost %.1f / %.1f %%, world request %.3f", amount, percent, world);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1018: access fault - skipped");
    }
}
void __cdecl State1018Slot0(BYTE *agent) { State1018(agent, kP1018a); }
void __cdecl State1018Slot1(BYTE *agent) { State1018(agent, kP1018b); }

// state 1018, slot 2 = TU 0x824651c8: slot 5 cleared, selector
void __cdecl State1018Slot2(BYTE *) {
    g_meter.request[5][0] = g_meter.request[5][1] = kNoRequest;
    Selector();
    Hit(kP1018c);
}

// condition 1048 = TU 0x8246ece0 (agent; no record test, no NOT flag): true unless gameTracker+0x1280 x 100.0 >
// animation entry +0x28 of the agent's channel
char __cdecl Cond1048(BYTE *agent, void *, const BYTE *) {
    char r = 0;
    __try {
        float steps = static_cast<float>(g_gt1280) * kHundred;
        float time = *reinterpret_cast<const float *>(AnimEntry(Channel(agent)) + 0x28);
        r = steps > time ? 0 : 1;
        Hit(kP1048, "steps x 100 = %.0f, animation %.1f -> %.0f", steps, time, r);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        r = 0;
    }
    return r;
}

// condition 2401 = TU 0x824702b0 (always false): with the tuning: meter +0x38 = record value (s16 -> float, frames),
// slot 4 = {tuning +0x58 player, tuning +0x54 world}, selector
char __cdecl Cond2401(void *, void *, const BYTE *record) {
    __try {
        float value = static_cast<float>(*reinterpret_cast<const SHORT *>(record + 4));
        const BYTE *tuning = g_tuning;
        if (!tuning) return 0;
        g_meter.requestTimer = value;
        g_meter.request[4][0] = Tune(tuning, kTuneTimedPlayer);
        g_meter.request[4][1] = Tune(tuning, kTuneTimedWorld);
        Selector();
        Hit(kP2401, "%.0f frames, player %.3f, world %.3f", value, g_meter.request[4][0], g_meter.request[4][1]);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return 0;
}

// activity 1009 = TU 0x82472788: (gameTracker+0x504 = player instance)->+0xc8 = record +4
void __cdecl Act1009(void *, const BYTE *record) {
    __try {
        BYTE *player = *reinterpret_cast<BYTE *const *>(GameTracker() + 0x504);
        *reinterpret_cast<DWORD *>(player + 0xc8) = *reinterpret_cast<const DWORD *>(record + 4);
        Hit(kP1009, "value %.0f", static_cast<double>(*reinterpret_cast<const DWORD *>(record + 4)));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

// activity 1039 = TU 0x82455a38 = PC 0x6457a0 (an empty print function - `ret`)
void __cdecl Act1039(void *, const BYTE *) { Hit(kP1039); }

// ---- 0.7: condition 1055 = TU 0x8246e488 (r6 = predicate 0x8246e450; b 0x82487718 = PC template tru+0x382d70) ----
int g_cond1055 = 1;                       // [Conditions] Cond1055
volatile LONG g_p1055Calls = 0;
int Doppelganger();                       // 0.6, below: TruDlc2Player's doppelganger flag (TU gameTracker+0x1244)

// TU 0x8246e450: doppelganger mode -> (gameTracker+0x508)->flags bit 4 (rlwinm 0x1e = bit value 4), else
// (gameTracker+0x504)->+0x1fc bit 0x20000000 (rlwinm 3). The TU reads the meter without a null test; the plugin's meter
// always exists. Writers of flag 4 on the TU: 0x823d8a80 (set, needs flag 2) and 0x823d9050 (clear) - not ported here.
char __cdecl Pred1055(const BYTE *) {
    int dg = Doppelganger();
    char r = 0;
    if (dg) {
        r = (g_meter.flags & 4) ? 1 : 0;
    } else {
        __try {
            const BYTE *player = *reinterpret_cast<const BYTE *const *>(GameTracker() + 0x504);
            r = static_cast<char>((*reinterpret_cast<const DWORD *>(player + 0x1fc) >> 29) & 1);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            r = 0;
        }
    }
    if (InterlockedIncrement(&g_p1055Calls) == 1)
        Log(1, "condition 1055 predicate (TU 0x8246e450) first call: doppelganger %d -> %d (meter flags 0x%03lx; flag 4 "
               "comes only from the shadow look of the shadow strike, not ported)", dg, r, g_meter.flags);
    return r;
}

char __cdecl Cond1055(void *agent, void *cache, const BYTE *record) {
    char r = 0;
    __try {
        r = reinterpret_cast<CondTemplateFn>(kCondTemplate)(agent, cache, record, &Pred1055);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        r = 0;
    }
    LogCond(8, 1055, record, r ? 1 : 0);
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
    // 0.5: + 1048 and 2401 (only when the 0.5 building blocks are verified; group 2000 / 2400 as in the TU table)
    struct AddRec { DWORD id; DWORD group; const void *fn; };
    AddRec add[10] = {
        {1049, 2000, &CondMeter}, {1050, 2000, &CondMeter}, {1051, 2000, &CondMeter}, {1052, 2000, &CondMeter},
        {1053, 2000, &CondMeter}, {1054, 2000, &CondMeter}, {1056, 2000, &Cond1056}, {0, 0, nullptr}, {0, 0, nullptr},
        {0, 0, nullptr}};
    int addCount = 7;
    if (g_tuStatesOk && g_statesEnabled) {
        add[addCount++] = {1048, 2000, &Cond1048};
        add[addCount++] = {2401, 2400, &Cond2401};
    }
    bool with1055 = false;
    if (g_cond1055) { add[addCount++] = {1055, 2000, &Cond1055}; with1055 = true; }   // 0.7 (group 2000 as the TU)
    for (int i = 0; i < kLaraCondCount; ++i)
        for (int k = 0; k < addCount; ++k)
            if (table[i * 3] == add[k].id) {
                Log(0, "Lara conditions: id %lu already in the table - not registered", add[k].id);
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
            for (int k = 0; k < addCount; ++k)
                if (g[i * 3] == add[k].id) ++found;
        if (found != addCount) {
            Log(0, "Lara conditions: the generic table 0x%08lx holds %d of our %d ids - not registered", generic, found,
                addCount);
            return;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "Lara conditions: generic table not readable - not registered");
        return;
    }
    memcpy(g_laraConds, table, kLaraCondCount * 3 * sizeof(DWORD));
    int n = kLaraCondCount;
    for (int k = 0; k < addCount; ++k) {
        g_laraConds[n * 3] = add[k].id;
        g_laraConds[n * 3 + 1] = add[k].group;
        g_laraConds[n * 3 + 2] = reinterpret_cast<DWORD>(add[k].fn);
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
    Log(1, "Lara conditions: 1049-1054 (meter compare), 1056 (meter >= tuning +0x70 while active)%s%s added to the link "
           "array (copy 0x%08lx, %d records; generic registry has them via TruDoppelganger)",
        addCount > (with1055 ? 8 : 7) ? ", 1048 (move steps vs animation), 2401 (timed time-scale request)" : "",
        with1055 ? ", 1055 (TU predicate 0x8246e450: doppelganger -> meter flag 4, else player +0x1fc bit 29)" : "",
        reinterpret_cast<DWORD>(g_laraConds), n);
}

// 0.5: Lara's activity and state tables get the translated TU records the same way (push operands tru+0x368b8d /
// tru+0x368b99, loops tru+0x385390 / tru+0x385600 - the state loop has the same null-node crash path for an id the
// generic registry lacks, tru+0x3856e4 -> 0x385742). Generic tables: TruDoppelganger's copies (push operands
// tru+0x38735a / tru+0x38736a). TU slot positions kept: 243 {f, 0, 0, 0, 0, 0}, 245 {f, 0, 0, g, 0, 0}, 1018 {f, f,
// g, 0, 0, 0} (TU table 0x82757948).
const DWORD kLaraActPush = 0x00768b8d, kLaraStatePush = 0x00768b99;
const BYTE kLaraActStateBytes[] = {0x68, 0x80, 0x22, 0x8b, 0x00, 0x8b, 0xce, 0xe8, 0xf7, 0xc7, 0x01, 0x00,
                                   0x68, 0x50, 0x0a, 0x8b, 0x00, 0x8b, 0xce, 0xe8, 0x5b, 0xca, 0x01, 0x00};
const DWORD kLaraActTable = 0x008b2280, kLaraStateTable = 0x008b0a50;
const int kLaraActCount = 139, kLaraStateCount = 179;
const DWORD kActClosingFn = 0x00784cf0, kStateDefaultFn = 0x00781d10;
const DWORD kGenericActPush = 0x0078735a, kGenericStatePush = 0x0078736a;
const DWORD kGenericActTable = 0x008b6650, kGenericStateTable = 0x008b4200;
DWORD g_laraActs[(kLaraActCount + 4) * 2];
DWORD g_laraStates[(kLaraStateCount + 6) * 7];

// count of `ids` present in a generic {id, n-1 words} table that is not the original; -1 if it is the original / bad
int GenericHolds(DWORD pushOperand, DWORD original, int stride, const DWORD *ids, int count) {
    __try {
        DWORD table = *reinterpret_cast<const DWORD *>(pushOperand);
        if (table == original) return -1;
        const DWORD *t = reinterpret_cast<const DWORD *>(table);
        int found = 0;
        for (int i = 0; i < 2000 && t[i * stride] != 0; ++i)
            for (int k = 0; k < count; ++k)
                if (t[i * stride] == ids[k]) ++found;
        return found;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return -1;
    }
}

// ---- 0.6: condition 1046 (TU predicate 0x8246e400) ----
const DWORD kPred1046 = 0x007655c0;       // mov eax,[0FADB58h]; mov ecx,[eax+504h]; mov eax,[ecx+1FCh]; shr eax,15h; and al,1
const char *const kPred1046Hex = "a158dbfa00 8b8804050000 8b81fc010000 c1e815 2401 c3";
const DWORD kCond1046Push = 0x007655ec;   // condition 1046 tru+0x3655e0: push 0x7655c0 (template tru+0x382d70)
const char *const kCond1046PushHex = "68c0557600";
int g_cond1046 = 1;                       // [Conditions] Cond1046
typedef int(__cdecl *DoppelgangerFn)();
DoppelgangerFn g_doppelganger = nullptr;
int g_doppelgangerLooked = 0;
volatile LONG g_p1046Calls = 0, g_p1046Last = -1;

int Doppelganger() {
    if (!g_doppelgangerLooked) {
        HMODULE m = GetModuleHandleA("TruDlc2Player.asi");
        if (m) g_doppelganger = reinterpret_cast<DoppelgangerFn>(GetProcAddress(m, "TruDlc2PlayerDoppelganger"));
        g_doppelgangerLooked = 1;
        if (!g_doppelganger)
            Log(0, "TruDlc2Player.asi / TruDlc2PlayerDoppelganger not found - condition 1046 uses the retail test only");
    }
    return g_doppelganger ? g_doppelganger() : 0;
}

char __cdecl Pred1046(const BYTE *) {
    int dg = Doppelganger();
    char r = 0;
    if (dg) {
        r = (g_meter.flags & 1) ? 1 : 0;          // meter object +4 bit 0 (the plugin's meter always exists)
    } else {
        __try {                                   // retail: (gameTracker+0x504)->+0x1fc bit 21
            const BYTE *player = *reinterpret_cast<const BYTE *const *>(GameTracker() + 0x504);
            r = static_cast<char>((*reinterpret_cast<const DWORD *>(player + 0x1fc) >> 21) & 1);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            r = 0;
        }
    }
    LONG n = InterlockedIncrement(&g_p1046Calls);
    LONG packed = r | (dg << 1);
    if (n == 1)
        Log(1, "condition 1046 (predicate tru+0x3655c0 = TU 0x8246e400) is now evaluated: doppelganger %d -> %d (meter flags "
               "0x%03lx)", dg, r, g_meter.flags);
    else if (InterlockedExchange(&g_p1046Last, packed) != packed)
        Log(2, "condition 1046 -> %d (doppelganger %d, meter %.1f, flags 0x%03lx, call %ld)", r, dg, g_meter.value,
            g_meter.flags, n);
    if (n == 1) g_p1046Last = packed;
    return r;
}

bool WriteJump5(DWORD at, const void *to) {
    BYTE code[5] = {0xe9, 0, 0, 0, 0};
    DWORD rel = reinterpret_cast<DWORD>(to) - (at + 5);
    memcpy(code + 1, &rel, 4);
    DWORD old = 0, dummy = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(at), 5, PAGE_EXECUTE_READWRITE, &old)) return false;
    memcpy(reinterpret_cast<void *>(at), code, 5);
    VirtualProtect(reinterpret_cast<void *>(at), 5, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(at), 5);
    return true;
}

void Patch1046() {
    if (!HexBytesAt(kPred1046, kPred1046Hex) || !HexBytesAt(kCond1046Push, kCond1046PushHex)) {
        Log(0, "condition 1046 predicate at 0x%08lx does not match - not translated", kPred1046);
        return;
    }
    if (WriteJump5(kPred1046, &Pred1046))
        Log(1, "condition 1046: title-update predicate (doppelganger mode -> meter active, else retail; 0x%08lx)", kPred1046);
    else
        Log(0, "condition 1046 not written (VirtualProtect %lu)", GetLastError());
}

bool PatchPush(DWORD operandAddress, DWORD value) {
    DWORD *operand = reinterpret_cast<DWORD *>(operandAddress);
    DWORD old = 0;
    if (!VirtualProtect(operand, 4, PAGE_EXECUTE_READWRITE, &old)) return false;
    *operand = value;
    DWORD dummy = 0;
    VirtualProtect(operand, 4, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), operand, 4);
    return true;
}

void RegisterLaraStates() {
    if (!g_statesEnabled) { Log(1, "Lara states / activities: off ([States] Enabled=0)"); return; }
    if (!g_tuStatesOk) { Log(0, "Lara states / activities: building blocks not verified - not registered"); return; }
    // RegisterLaraConditions runs first and may already have pointed the condition push (inside kLaraRegBytes) at
    // our copy - accept the original operand or that copy, all other bytes must match
    const size_t condOff = kLaraCondPush + 1 - kLaraReg;
    const DWORD condCopy = reinterpret_cast<DWORD>(g_laraConds);
    const bool regOk = BytesAt(kLaraReg, kLaraRegBytes, condOff) &&
                       BytesAt(kLaraCondPush + 5, kLaraRegBytes + condOff + 4, sizeof(kLaraRegBytes) - condOff - 4) &&
                       (BytesAt(kLaraCondPush + 1, kLaraRegBytes + condOff, 4) ||
                        BytesAt(kLaraCondPush + 1, reinterpret_cast<const BYTE *>(&condCopy), 4));
    if (!regOk || !BytesAt(kLaraActPush, kLaraActStateBytes, sizeof(kLaraActStateBytes))) {
        Log(0, "Lara states / activities: registration code does not match - not registered");
        return;
    }
    // activities
    const DWORD *acts = reinterpret_cast<const DWORD *>(kLaraActTable);
    const DWORD *actEnd = acts + kLaraActCount * 2;
    const DWORD actIds[] = {1009, 1039};
    const DWORD actFns[] = {reinterpret_cast<DWORD>(&Act1009), reinterpret_cast<DWORD>(&Act1039)};
    bool actsOk = actEnd[0] == 0 && actEnd[1] == kActClosingFn && acts[0] == 203;
    for (int i = 0; actsOk && i < kLaraActCount; ++i)
        if (acts[i * 2] == 1009 || acts[i * 2] == 1039) actsOk = false;
    int actGeneric = GenericHolds(kGenericActPush, kGenericActTable, 2, actIds, 2);
    if (!actsOk) {
        Log(0, "Lara activities: table 0x%08lx is not the expected one - not registered", kLaraActTable);
    } else if (actGeneric != 2) {
        Log(0, "Lara activities: generic table lacks the ids (%d of 2; TruDoppelganger.asi active?) - not registered",
            actGeneric);
    } else {
        memcpy(g_laraActs, acts, kLaraActCount * 2 * sizeof(DWORD));
        int n = kLaraActCount;
        for (int k = 0; k < 2; ++k, ++n) { g_laraActs[n * 2] = actIds[k]; g_laraActs[n * 2 + 1] = actFns[k]; }
        memcpy(g_laraActs + n * 2, actEnd, 2 * sizeof(DWORD));
        if (PatchPush(kLaraActPush + 1, reinterpret_cast<DWORD>(g_laraActs)))
            Log(1, "Lara activities: 1009 (player +0xc8 = record +4), 1039 (print stub) added (copy 0x%08lx, %d "
                   "records)", reinterpret_cast<DWORD>(g_laraActs), n);
        else
            Log(0, "Lara activities: VirtualProtect failed (%lu) - not registered", GetLastError());
    }
    // states
    const DWORD *states = reinterpret_cast<const DWORD *>(kLaraStateTable);
    const DWORD *stateEnd = states + kLaraStateCount * 7;
    bool statesOk = stateEnd[0] == 0 && states[0] == 2;
    for (int k = 1; statesOk && k < 7; ++k) statesOk = stateEnd[k] == kStateDefaultFn;
    for (int i = 0; statesOk && i < kLaraStateCount; ++i)
        if (states[i * 7] == 243 || states[i * 7] == 245 || states[i * 7] == 1018) statesOk = false;
    const DWORD stateIds[] = {243, 245, 1018};
    int stateGeneric = GenericHolds(kGenericStatePush, kGenericStateTable, 7, stateIds, 3);
    if (!statesOk) {
        Log(0, "Lara states: table 0x%08lx is not the expected one - not registered", kLaraStateTable);
        return;
    }
    if (stateGeneric != 3) {
        Log(0, "Lara states: generic table lacks the ids (%d of 3; TruDoppelganger.asi active?) - not registered",
            stateGeneric);
        return;
    }
    const DWORD rec[3][7] = {
        {243, reinterpret_cast<DWORD>(&State243), 0, 0, 0, 0, 0},
        {245, reinterpret_cast<DWORD>(&State245), 0, 0, reinterpret_cast<DWORD>(&State245Slot3), 0, 0},
        {1018, reinterpret_cast<DWORD>(&State1018Slot0), reinterpret_cast<DWORD>(&State1018Slot1),
         reinterpret_cast<DWORD>(&State1018Slot2), 0, 0, 0}};
    memcpy(g_laraStates, states, kLaraStateCount * 7 * sizeof(DWORD));
    int n = kLaraStateCount;
    for (int k = 0; k < 3; ++k, ++n) memcpy(g_laraStates + n * 7, rec[k], 7 * sizeof(DWORD));
    memcpy(g_laraStates + n * 7, stateEnd, 7 * sizeof(DWORD));
    if (PatchPush(kLaraStatePush + 1, reinterpret_cast<DWORD>(g_laraStates)))
        Log(1, "Lara states: 243 (move to gameTracker+0x1270), 245 (move tuning +0x6c along the player), 1018 (meter "
               "cost / world request) added (copy 0x%08lx, %d records); not translated: 244, 1017, 1019, 1020, 2102",
            reinterpret_cast<DWORD>(g_laraStates), n);
    else
        Log(0, "Lara states: VirtualProtect failed (%lu) - not registered", GetLastError());
}

// ================================================================================================================
// 0.9: the TU tick 0x823d7a10 with its gates, and the adrenaline look group (0x823d94f8 / 0x823d9348 / 0x823d9438,
// mode chooser, adrenaline start / stop / tick, condition 1047)

// ---- TU gates (PC partners, each pinned by bytes in Start) ----
typedef char(__cdecl *CinematicFn)();
const DWORD kCinematic = 0x00453f00;      // [0xe7f1c0] && +0xdd && +0x2c != -1 (TU 0x823d7a30..0x823d7a6c inline)
const char *const kCinematicHex = "a1c0f1e700 85c0 7418 80b8dd00000000 740c 83782cff 7406 b801000000 c3 33c0 c3 32c0 c3";
const DWORD kBlockByte = 0x00fae8dd;      // TU 0x829ca6da = retail 0x829ca5f1
const DWORD kBlockGetter = 0x0077bc20;    // mov al,[0FAE8DDh]; ret
const char *const kBlockGetterHex = "a0dde8fa00 c3";
const DWORD kBlockSetter = 0x0077bbf0;    // mov al,[esp+4]; mov [0FAE8DDh],al; ret
const char *const kBlockSetterHex = "8a442404 a2dde8fa00 c3";
const DWORD kBlockSetterCall = 0x005de576;   // GAMELOOP tru+0x1de480 (= retail 0x8229c530, store 0x8229c708)
const char *const kBlockSetterCallHex = "e875d61900";
const DWORD kGtxFlags = 0x00e7f144;       // TU 0x82efb514 (gameTrackerX +0xbc), bit 0
const DWORD kGtxFlagsCheck = 0x00718c1f;  // adrenaline tick tru+0x318bd0 = TU 0x823defa8: test byte [0E7F144h],1
const char *const kGtxFlagsCheckHex = "f60544f1e70001 0f85c4000000 803d43f1e70004";
const DWORD kInputPtr = 0x00a02b68;       // TU 0x8286dd90: [[p]+0x18]->[0] = the input records
const DWORD kInputCheck = 0x00718c39;     // the same chain to +0x6f0 & 0x10 in tru+0x318bd0 (TU: +0x6f0 >> 4 & 1)
const char *const kInputCheckHex = "8b0d682ba000 8b5118 8b0a 8b91f0060000 80e210";
bool g_gatesOk = false;                   // cinematic / block byte / 0xe7f144 verified
bool g_inputOk = false;                   // input chain verified (GameInput / diagnostic)

bool Cinematic() {
    if (!g_gatesOk) return false;
    char c = 0;
    __try {
        c = reinterpret_cast<CinematicFn>(kCinematic)();
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        c = 0;
    }
    return c != 0;
}

bool BlockByte() { return g_gatesOk && *reinterpret_cast<const volatile BYTE *>(kBlockByte) != 0; }
bool GtxFlag() { return g_gatesOk && (*reinterpret_cast<const volatile BYTE *>(kGtxFlags) & 1) != 0; }

// TU 0x823d7d68..0x823d7dd4: refused while a cinematic runs, 0x829ca6da is set, no tracker or health <= 0.0
bool TuStartRefused() {
    if (Cinematic() || BlockByte()) return true;
    BYTE *gt = GameTracker();
    if (!gt) return true;
    float health = 0.0f;
    __try {
        health = *reinterpret_cast<const float *>(gt + 0x628);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return true;
    }
    return !(kZero < health);
}

// game input record word (TU 0x823d7b6c..0x823d7b8c reads +0x1a70 / +0x1b30); returns false when not readable
bool InputWord(DWORD offset, DWORD *value) {
    if (!g_inputOk) return false;
    __try {
        const BYTE *p = *reinterpret_cast<const BYTE *const *>(kInputPtr);
        if (!p) return false;
        const BYTE *list = *reinterpret_cast<const BYTE *const *>(p + 0x18);
        if (!list) return false;
        const BYTE *rec = *reinterpret_cast<const BYTE *const *>(list);
        if (!rec) return false;
        *value = *reinterpret_cast<const DWORD *>(rec + offset);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// ---- adrenaline look group ----
const DWORD kTargetCheck = 0x006f2800;    // TU 0x823df8f8 (retail leaf 0x823dd7a8), thiscall(player) -> al
const char *const kTargetCheckHex =
    "53 8b1d58dbfa00 8b8300050000 56 8bb034010000 83fe0c 57 8bf9 0f8491000000 83fe07 0f8488000000 83fe03 747d "
    "83fe04 7478 e898f6ffff 84c0 756f 8b87fc010000 8bc8 c1e91e f6c101 755f 8bd0 c1ea15 f6c201 7555 c1e818 a801 754e "
    "83feff 744f d9ee d89b88050000 dfe0 f6c405 7b3a 803de6b48a0000 7437 f60544f1e70001 752e 803d43f1e70004 7425 "
    "a1682ba000 8b4818 8b11 8b8230060000 2404 33c9 3c04 0f94c1 8bc1 85c0 7406 5f 5e b001 5b c3 5f 5e 32c0 5b c3";
const DWORD kAimHelper = 0x006f1ed0;      // +0x1fc bit 9 or bit 10 (TU inline 0x823df924..0x823df948)
const char *const kAimHelperHex = "8b81fc010000 8bc8 c1e909 f6c101 750a c1e80a a801 7503 33c0 c3 b801000000 c3";
const DWORD kHudClear = 0x0077db70;       // clear bit n of the HUD group mask 0xfae924 (PC adrenaline stop)
const char *const kHudClearHex = "8b4c2404 8d41ff 83f81e 7710 ba01000000 d3e2 f7d2 211524e9fa00 c3";
typedef void(__cdecl *HudClearFn)(int bit);
bool g_lookAdrOk = false;                 // check function / HUD clear verified (LookTick, Set40, Clear40)
volatile LONG g_set40 = 0, g_clear40 = 0;

// TU 0x823df8f8 (gameTracker in r8, player in r3). The TU inserted 0x823df918..0x823df970: in doppelganger mode only
// +0x1fc bits 9 / 10, 30, 24 answer 1 before the shared tail (no mode 3 / 4, no bit 21). The rest is the PC function's
// code (tru+0x2f2800, verified byte for byte) written out: mode 0xc / 7 -> 0; tail tru+0x2f285d = TU 0x823df9d8.
bool TargetCheck(const BYTE *gt, const BYTE *player) {
    const int mode = *reinterpret_cast<const int *>(*reinterpret_cast<const BYTE *const *>(gt + 0x500) + 0x134);
    if (mode == 0xc || mode == 7) return false;
    const DWORD w = *reinterpret_cast<const DWORD *>(player + 0x1fc);
    if (Doppelganger()) {
        if (((w >> 9) & 1) || ((w >> 10) & 1)) return true;
        if ((w >> 30) & 1) return true;
        if ((w >> 24) & 1) return true;
    } else {
        if (mode == 3 || mode == 4) return true;
        if (((w >> 9) & 1) || ((w >> 10) & 1)) return true;
        if (((w >> 30) & 1) || ((w >> 21) & 1) || ((w >> 24) & 1)) return true;
    }
    if (mode == -1) return false;
    if (kZero < *reinterpret_cast<const float *>(gt + 0x588)) return true;
    if (*reinterpret_cast<const volatile BYTE *>(0x008ab4e6) == 0) return false;         // TU 0x8275422a
    if (*reinterpret_cast<const volatile BYTE *>(kGtxFlags) & 1) return false;          // TU 0x82efb514
    if (*reinterpret_cast<const volatile BYTE *>(0x00e7f143) == 4) return false;        // TU 0x82efb513
    DWORD word = 0;
    if (!InputWord(0x630, &word)) return false;
    return (word & 4) == 4;
}

// TU 0x823d9348 (meter flag 0x40 on)
void Set40(const BYTE *tuning) {
    if ((g_meter.flags & 0x40) || !(g_meter.flags & 1)) return;
    BYTE *gt = GameTracker();
    if (gt && tuning) {
        g_meter.request[3][1] = Tune(tuning, 0x38);              // +0x5c = tuning +0x38 (world 0.1)
        g_meter.request[3][0] = kNoRequest;                      // +0x58 = -1.0
        Selector();
    }
    bool hud = false;
    __try {
        const BYTE *player = *reinterpret_cast<const BYTE *const *>(gt + 0x504);
        if ((*reinterpret_cast<const DWORD *>(player + 0x1fc) >> 10) & 1) {
            if (g_hudOk && *kHudManager) {                       // 0x829ca724 |= 0x9000; vtbl[0xc] - as tru+0x3189d7
                g_hudGroup(0xf);
                g_hudGroup(0xc);
                g_hudUpdate();
                hud = true;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    g_meter.flags |= 0x40;
    // not ported: 0x82415b50(1) (instance messages; PC partner 0x6f64c0 from the map, unverified)
    bool fired = FireEvent(0x39);
    LONG n = InterlockedIncrement(&g_set40);
    Log(n == 1 ? 1 : 2, "meter flag 0x40 ON (TU 0x823d9348%s): world request 3 = %.3f, HUD 0x9000 %s, event 0x39 %s", n == 1
        ? ", first time" : "", tuning ? Tune(tuning, 0x38) : 0.0f, hud ? "set" : "not set (player +0x1fc bit 10 clear)",
        fired ? "fired" : "not fired");
}

// TU 0x823d9438 (meter flag 0x40 off)
void Clear40() {
    if (!(g_meter.flags & 0x40)) return;
    const BYTE *tuning = g_tuning;
    if (GameTracker() && tuning) {
        g_meter.request[3][0] = g_meter.request[3][1] = kNoRequest;
        Selector();
    }
    if (g_hudOk && g_lookAdrOk && *kHudManager) {               // 0x829ca724 &= 0xffff6fff; vtbl[0xc]
        reinterpret_cast<HudClearFn>(kHudClear)(0xf);
        reinterpret_cast<HudClearFn>(kHudClear)(0xc);
        g_hudUpdate();
    }
    g_meter.flags &= ~0x40u;
    bool fired = FireEvent(0x3a);
    LONG n = InterlockedIncrement(&g_clear40);
    Log(n == 1 ? 1 : 2, "meter flag 0x40 OFF (TU 0x823d9438): request 3 cleared, HUD 0x9000 cleared, event 0x3a %s",
        fired ? "fired" : "not fired");
}

// TU 0x823d94f8, once per tick
void LookTick(const BYTE *tuning) {
    if (!g_lookAdrOk || !g_adrenalineMode) return;
    bool on = false;
    __try {
        const BYTE *gt = GameTracker();
        if (gt && tuning && Tune(tuning, kTuneRestart) < g_meter.value && (g_meter.flags & 1)) {
            const BYTE *player = *reinterpret_cast<const BYTE *const *>(gt + 0x504);
            if (player && TargetCheck(gt, player) &&
                *reinterpret_cast<const int *>(*reinterpret_cast<const BYTE *const *>(gt + 0x500) + 0x134) != 3 &&
                !(g_meter.flags & 2))
                on = true;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        on = false;
    }
    if (!on) {
        if (g_meter.flags & 0x40) Clear40();
    } else if (!(g_meter.flags & 0x40)) {
        Set40(tuning);
    }
}

// ---- the TU's doppelganger branches in the adrenaline code (naked stubs; no logging inside) ----
// The TU: gameTracker+0x1244 ? (meter +4 >> 6) & 1 : (player +0x1fc >> 27) & 1 (and for bit 21: meter flag 2).
// The stubs only read the cached export pointer (no lookup, no log) - Doppelganger() resolves it on the first tick.
volatile LONG g_adrHits[7];               // DG-mode answers 1: 0 chooser (mode 0x34), 1 start, 2 stop, 3 tick bit 21,
                                          // 4 tick toggle, 5 tick release, 6 condition 1047 (diagnostic counters)
LONG g_adrReported[7];
const char *const kAdrNames[7] = {
    "camera mode chooser tru+0x1e80a9 (TU 0x822acef8): mode 0x34 by meter flag 0x40 (doppelganger mode)",
    "adrenaline start tru+0x3189c6 (TU 0x823ded18): 'already active' = meter flag 0x40",
    "adrenaline stop tru+0x318ad6 (TU 0x823dee58): 'active' = meter flag 0x40",
    "adrenaline tick tru+0x318bf3 (TU 0x823defa8): +0x1fc bit 21 -> meter flag 2",
    "adrenaline tick tru+0x318c5d (TU 0x823defa8): toggle by meter flag 0x40",
    "adrenaline tick tru+0x318cda (TU 0x823defa8): release by meter flag 0x40",
    "condition 1047 (tru+0x365600 = TU 0x8246e538): meter flag 0x40"};

int __cdecl AdrBit(DWORD word, int counter) {
    if (g_adrenalineMode && g_doppelganger && g_doppelganger()) {
        int r = (g_meter.flags >> 6) & 1;
        if (r) InterlockedIncrement(&g_adrHits[counter]);
        return r;
    }
    return (word >> 27) & 1;
}

int __cdecl AdrBit21(DWORD word) {
    if (g_adrenalineMode && g_doppelganger && g_doppelganger()) {
        int r = (g_meter.flags >> 1) & 1;
        if (r) InterlockedIncrement(&g_adrHits[3]);
        return r;
    }
    return (word >> 21) & 1;
}

DWORD g_modeYes = 0x005e80b9, g_modeNo = 0x005e80c2;          // mov [esi+58h],34h | shr eax,0Ah
DWORD g_startActive = 0x00718ac0, g_startGo = 0x007189d7;
DWORD g_stopIdle = 0x00718bc1, g_stopGo = 0x00718ae7;
DWORD g_tickBit21Yes = 0x00718c71, g_tickBit21No = 0x00718bfd;
DWORD g_adrStart = 0x007189c0, g_adrStop = 0x00718ad0;
DWORD g_tickRelIdle = 0x00718cf0, g_tickRelGo = 0x00718ce8;

// tru+0x1e80a9 (6 bytes `mov eax,[ecx+1FCh]`; ecx = player): bit -> 0x5e80b9 (mode 0x34) else 0x5e80c2
__declspec(naked) void ModeStub() {
    __asm {
        push ecx
        push edx
        push 0
        push dword ptr [ecx + 1fch]
        call AdrBit
        add esp, 8
        pop edx
        pop ecx
        test eax, eax
        mov eax, [ecx + 1fch]
        mov ecx, eax                  // as the original: ecx = word >> 27
        jz no34
        shr ecx, 1bh
        jmp dword ptr [g_modeYes]
    no34:
        shr ecx, 1bh
        jmp dword ptr [g_modeNo]
    }
}

// tru+0x3189c6 (adrenaline start, esi = player): active -> return (0x718ac0), else go on (0x7189d7)
__declspec(naked) void StartStub() {
    __asm {
        push ecx
        push edx
        push 1
        push dword ptr [esi + 1fch]
        call AdrBit
        add esp, 8
        pop edx
        pop ecx
        test eax, eax
        jnz active
        jmp dword ptr [g_startGo]
    active:
        jmp dword ptr [g_startActive]
    }
}

// tru+0x318ad6 (adrenaline stop, esi = player): not active -> return (0x718bc1), else go on (0x718ae7)
__declspec(naked) void StopStub() {
    __asm {
        push ecx
        push edx
        push 2
        push dword ptr [esi + 1fch]
        call AdrBit
        add esp, 8
        pop edx
        pop ecx
        test eax, eax
        jz idle
        jmp dword ptr [g_stopGo]
    idle:
        jmp dword ptr [g_stopIdle]
    }
}

// tru+0x318bf3 (adrenaline tick, eax = player +0x1fc, kept): bit 21 (meter flag 2) -> 0x718c71, else 0x718bfd
__declspec(naked) void TickBit21Stub() {
    __asm {
        push eax
        push ecx
        push eax
        call AdrBit21
        add esp, 4
        mov edx, eax
        pop ecx
        pop eax
        test dl, 1
        jnz yes
        jmp dword ptr [g_tickBit21No]
    yes:
        jmp dword ptr [g_tickBit21Yes]
    }
}

// tru+0x318c5d (adrenaline tick, eax = player +0x1fc; then mov ecx,esi; pop esi; je start; jmp stop)
__declspec(naked) void TickToggleStub() {
    __asm {
        push ecx
        push edx
        push 4
        push eax
        call AdrBit
        add esp, 8
        pop edx
        pop ecx
        test eax, eax
        mov ecx, esi
        pop esi
        jz start
        jmp dword ptr [g_adrStop]
    start:
        jmp dword ptr [g_adrStart]
    }
}

// tru+0x318cda (6 bytes `mov ecx,[esi+1FCh]`): bit clear -> 0x718cf0 (return), else 0x718ce8 (stop)
__declspec(naked) void TickReleaseStub() {
    __asm {
        push eax
        push edx
        push 5
        push dword ptr [esi + 1fch]
        call AdrBit
        add esp, 8
        mov ecx, eax
        pop edx
        pop eax
        test cl, 1
        jz idle
        jmp dword ptr [g_tickRelGo]
    idle:
        jmp dword ptr [g_tickRelIdle]
    }
}

// condition 1047 predicate (PC tru+0x365600 = retail test; TU 0x8246e538 adds the doppelganger branch)
char __cdecl Pred1047(const BYTE *) {
    char r = 0;
    __try {
        const BYTE *player = *reinterpret_cast<const BYTE *const *>(GameTracker() + 0x504);
        r = static_cast<char>(AdrBit(*reinterpret_cast<const DWORD *>(player + 0x1fc), 6));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        r = 0;
    }
    return r;
}

bool WriteJumpN(DWORD at, const void *to, int length) {
    BYTE code[8] = {0xe9, 0, 0, 0, 0, 0x90, 0x90, 0x90};
    DWORD rel = reinterpret_cast<DWORD>(to) - (at + 5);
    memcpy(code + 1, &rel, 4);
    DWORD old = 0, dummy = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(at), length, PAGE_EXECUTE_READWRITE, &old)) return false;
    memcpy(reinterpret_cast<void *>(at), code, length);
    VirtualProtect(reinterpret_cast<void *>(at), length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(at), length);
    return true;
}

struct AdrSite { const char *name; DWORD check; const char *hex; DWORD at; const void *stub; int len; };
const AdrSite kAdrSites[] = {
    {"camera mode chooser", 0x005e80a9,
     "8b81fc010000 8bc8 c1e91b f6c101 7409 c7465834000000 eb17 c1e80a a801 7509 c7465830000000", 0x005e80a9, &ModeStub, 6},
    {"adrenaline start", 0x007189c0, "83ec0c 56 8bf1 8b86fc010000 c1e81b a801 0f85e9000000 6a0f e8f24f0600", 0x007189c6,
     &StartStub, 6},
    {"adrenaline stop", 0x00718ad0, "83ec0c 56 8bf1 8b86fc010000 c1e81b a801 0f84da000000 6a0f e882500600", 0x00718ad6,
     &StopStub, 6},
    {"adrenaline tick bit 21", 0x00718be3, "8b86fc010000 8bc8 c1e90a f6c101 747e 8bd0 c1ea15 f6c201 7574 8b0d58dbfa00",
     0x00718bf3, &TickBit21Stub, 5},
    {"adrenaline tick toggle", 0x00718c5d, "c1e81b a801 8bce 5e 7405 e964feffff e94ffdffff", 0x00718c5d,
     &TickToggleStub, 5},
    {"adrenaline tick release", 0x00718cda, "8b8efc010000 c1e91b f6c101 7408 8bce 5e e9e0fdffff 5e c3", 0x00718cda,
     &TickReleaseStub, 6},
    {"condition 1047 predicate", 0x00765600, "a158dbfa00 8b8804050000 8b81fc010000 c1e81b 2401 c3", 0x00765600,
     &Pred1047, 5}};
const char *const kCond1047PushHex = "8b44240c 8b4c2408 8b542404 6800567600 50 51 52 e837d70100";   // at 0x765620

// all or nothing: a partial set would let start / stop / tick disagree about "active"
void PatchAdrenalineMode() {
    if (!g_adrenalineMode) { Log(1, "adrenaline look: off ([Look] AdrenalineMode=0)"); return; }
    g_lookAdrOk = HexBytesAt(kTargetCheck, kTargetCheckHex) && HexBytesAt(kAimHelper, kAimHelperHex) &&
                  HexBytesAt(kHudClear, kHudClearHex) && g_gatesOk && g_inputOk;
    if (!g_lookAdrOk) {
        Log(0, "adrenaline look: check function 0x%08lx / helper 0x%08lx / HUD clear 0x%08lx / gates / input chain do not "
               "match - TU 0x823d94f8 group and the doppelganger branches not translated", kTargetCheck, kAimHelper,
            kHudClear);
        return;
    }
    bool sitesOk = HexBytesAt(0x00765620, kCond1047PushHex);
    for (const auto &s : kAdrSites)
        if (!HexBytesAt(s.check, s.hex)) {
            Log(0, "adrenaline look: %s at 0x%08lx does not match", s.name, s.at);
            sitesOk = false;
        }
    if (!sitesOk) {
        g_lookAdrOk = false;
        Log(0, "adrenaline look: not translated (all sites or none)");
        return;
    }
    int written = 0;
    for (const auto &s : kAdrSites) {
        if (WriteJumpN(s.at, s.stub, s.len)) ++written;
        else Log(0, "adrenaline look: %s not written (VirtualProtect %lu)", s.name, GetLastError());
    }
    Log(1, "adrenaline look: TU 0x823d94f8 / 0x823d9348 / 0x823d9438 (meter flag 0x40) per tick; doppelganger branches "
           "of the camera mode chooser (mode 0x34), adrenaline start / stop / tick and condition 1047 - %d of %d sites "
           "written", written, static_cast<int>(sizeof(kAdrSites) / sizeof(kAdrSites[0])));
}

void ReportAdrenalineHits() {
    for (int i = 0; i < 7; ++i) {
        LONG n = g_adrHits[i], last = g_adrReported[i];
        if (n == last) continue;
        g_adrReported[i] = n;
        bool pow2 = false;
        for (LONG p = 1; p > 0 && p <= n; p <<= 1)
            if (p > last) { pow2 = true; break; }
        if (last == 0 || (g_logLevel >= 2 && pow2)) Log(1, "%s (%ld times)", kAdrNames[i], n);
    }
}

// ---- new tracker -> new meter (TU player init 0x82412ca0 -> 0x82409418 -> meter init 0x823d7700) ----
typedef int(__cdecl *GenerationFn)();
GenerationFn g_generation = nullptr;
int g_generationLooked = 0, g_lastGeneration = -1;

void NewTrackerCheck() {
    if (!g_generationLooked) {
        HMODULE m = GetModuleHandleA("TruDlc2Player.asi");
        if (m) g_generation = reinterpret_cast<GenerationFn>(GetProcAddress(m, "TruDlc2PlayerTrackerGeneration"));
        g_generationLooked = 1;
        if (!g_generation)
            Log(0, "TruDlc2PlayerTrackerGeneration not found (TruDlc2Player older than 0.2?) - the meter is not "
                   "re-initialised with a new game tracker");
    }
    if (!g_generation) return;
    int gen = g_generation();
    if (gen == g_lastGeneration) return;
    if (g_lastGeneration >= 0) {
        bool requests = false;
        for (int i = 0; i < 7; ++i) requests = requests || kZero < g_meter.request[i][0] || kZero < g_meter.request[i][1];
        DWORD was = g_meter.flags;
        if ((was & 0x40) && g_hudOk && g_lookAdrOk && *kHudManager) {
            reinterpret_cast<HudClearFn>(kHudClear)(0xf);
            reinterpret_cast<HudClearFn>(kHudClear)(0xc);
            g_hudUpdate();
        }
        MeterInit();
        if (requests) Selector();       // the plugin's meter outlives the TU object: release its time-scale requests
        Log(1, "new game tracker (generation %d): meter re-initialised (was flags 0x%03lx%s)", gen, was,
            requests ? ", time-scale requests released" : "");
    }
    g_lastGeneration = gen;
}

// ---- the TU tick 0x823d7a10 ----
int g_lastDg = -1;
bool g_lastPadHeld = false;
int g_inputDiag = 0;

void MeterTick(bool padHeld) {
    if (g_legacyPadStart) { LegacyMeterTick(padHeld); return; }
    NewTrackerCheck();
    // TU 0x824128a4..0x824128b8: the player update runs the tick only when gameTracker+0x1244 is set
    int dg = Doppelganger();
    if (dg != g_lastDg) {
        if (g_lastDg < 0)
            Log(1, "doppelganger flag %d at the first tick: shadow-power tick %s (TU 0x824128a8)", dg,
                dg ? "runs" : "does not run");
        else
            Log(1, "doppelganger flag %d -> %d: shadow-power tick %s (TU 0x824128a8)", g_lastDg, dg,
                dg ? "runs" : "does not run");
        g_lastDg = dg;
    }
    // diagnostic for GameInput: the game's records while the pad's LB / RB change
    if (padHeld != g_lastPadHeld) {
        g_lastPadHeld = padHeld;
        DWORD lb = 0, rb = 0, adr = 0;
        if (g_inputDiag < 12 && InputWord(0x1a70, &lb) && InputWord(0x1b30, &rb) && InputWord(0x6f0, &adr)) {
            ++g_inputDiag;
            Log(1, "input diagnostic: pad LB/RB %s - game records +0x1a70 0x%08lx, +0x1b30 0x%08lx (TU tests & 4), "
                   "+0x6f0 0x%08lx", padHeld ? "held" : "released", lb, rb, adr);
        }
    }
    ReportAdrenalineHits();
    if (!dg) return;
    const BYTE *tuning = FindTuning();
    g_tuning = tuning;
    float frames = *kFrameTime;
    if (!(frames >= 0.0f && frames < 30.0f)) frames = 0.0f;
    // 0x823d7a30..0x823d7a9c: a running cinematic or 0x829ca6da -> print "ADRENALINE: Process(): stopping
    // adrenaline!" (0x82455a38 = empty print on PC) and Stop (no-op when not active)
    bool cine = Cinematic(), block = BlockByte();
    if ((cine || block) && (g_meter.flags & 1)) StopPower(cine ? "cinematic" : "0x829ca6da (PC 0xfae8dd) set");
    // 0x823d7aa0..0x823d7adc: flag 0x80 = bool parameter 0x412 of Lara's current state (state machine gt+0xf10)
    BYTE *gt = GameTracker();
    if (gt && g_tuStatesOk) {
        __try {
            void *machine = *reinterpret_cast<void *const *>(gt + 0xf10);
            if (machine) {
                char zone = 0;
                ParamBool(machine, 0x412, &zone);
                DWORD before = g_meter.flags;
                if (zone) g_meter.flags |= 0x80;
                else g_meter.flags &= ~0x80u;
                if ((before ^ g_meter.flags) & 0x80)
                    Log(1, "meter flag 0x80 %s (state parameter 0x412 of the current state; blocks the meter)",
                        zone ? "set" : "cleared");
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
    // not ported: 0x823d7ae0..0x823d7b34 looping sound (+0x0 handle), 0x823d77f0 (shadow-strike look group)
    LookTick(tuning);                                                       // 0x823d94f8
    if (!(g_meter.flags & 0x90)) {
        bool buttons = padHeld;
        if (g_gameInput) {                                                  // 0x823d7b6c..0x823d7b98
            DWORD lb = 0, rb = 0;
            buttons = (InputWord(0x1a70, &lb) && (lb & 4) == 4) || (InputWord(0x1b30, &rb) && (rb & 4) == 4);
        }
        if (buttons && !GtxFlag()) {
            if (!g_meter.latch && CanStart(tuning)) {
                StartPower(tuning);
                g_meter.latch = 1;
            } else {
                if (!g_meter.latch) {                                       // CanStart false: event 0x80 (refused)
                    FireEvent(0x80);
                    Log(2, "start refused (meter %.1f, flags 0x%03lx): event 0x80", g_meter.value, g_meter.flags);
                }
                g_meter.latch = 1;
            }
        } else if (g_meter.latch == 1) {
            if (g_meter.flags & 1) StopPower(buttons ? "game flag 0xe7f144" : "released");
            g_meter.latch = 0;
        }
        if (!(g_meter.flags & 1)) {
            Refill(tuning, frames);
        } else {
            if (kZero < g_meter.value && !(g_meter.flags & 0x90) && tuning)
                Drain(tuning, frames * kPerSecond * Tune(tuning, kTuneDrain));
            if (kZero < g_meter.value) {
                if (GtxFlag()) StopPower("game flag 0xe7f144");
            } else {
                g_meter.flags |= 0x200;
                StopPower("meter empty");
            }
        }
    }
    // 0x823d7cf8..: the timed request of condition 2401
    if (kZero < g_meter.requestTimer) {
        g_meter.requestTimer = g_meter.requestTimer - frames;
        if (g_meter.requestTimer <= kZero) {
            g_meter.request[4][0] = g_meter.request[4][1] = kNoRequest;
            Selector();
            g_meter.requestTimer = kZero;
            Log(2, "timed request (2401) ended");
        }
    }
}

void ReadOptions(const char *dir) {
    char ini[MAX_PATH];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruShadowPower.ini", dir);
    g_legacyPadStart = GetPrivateProfileIntA("ShadowPower", "LegacyPadStart", 0, ini);
    g_gameInput = GetPrivateProfileIntA("ShadowPower", "GameInput", 0, ini);
    g_adrenalineMode = GetPrivateProfileIntA("Look", "AdrenalineMode", 1, ini);
    g_condEnabled = GetPrivateProfileIntA("Conditions", "Enabled", 1, ini);
    g_statesEnabled = GetPrivateProfileIntA("States", "Enabled", 1, ini);
    g_cond1046 = GetPrivateProfileIntA("Conditions", "Cond1046", 1, ini);
    g_cond1055 = GetPrivateProfileIntA("Conditions", "Cond1055", 1, ini);
    g_enabled = GetPrivateProfileIntA("ShadowPower", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("ShadowPower", "LogLevel", 1, ini);
    g_buttons = static_cast<WORD>(GetPrivateProfileIntA("ShadowPower", "Buttons", 0x0300, ini));
    g_hudFeed = GetPrivateProfileIntA("Meter", "HudBar", 1, ini);
    g_fallback = GetPrivateProfileIntA("Meter", "Fallback", 1, ini);
    g_lookEnabled = GetPrivateProfileIntA("Look", "Enabled", 1, ini);
    g_lookMessages = GetPrivateProfileIntA("Look", "Messages", 1, ini);
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruShadowPower.log", dir);
    ReadOptions(dir);
    InitFileTuning();
    Log(1, "TruShadowPower 0.9 loaded (enabled %d, buttons 0x%04x, HUD bar %d, fallback %d, conditions %d, states %d, "
        "condition 1046 %d, condition 1055 %d, look %d, legacy pad start %d, game input %d, adrenaline mode %d)", g_enabled,
        g_buttons, g_hudFeed, g_fallback, g_condEnabled, g_statesEnabled, g_cond1046, g_cond1055, g_lookEnabled,
        g_legacyPadStart, g_gameInput, g_adrenalineMode);
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
    // 0.8: player event walker (TU 0x82418158) for the look events of Start / Stop
    g_lookOk = HexBytesAt(kPlayerEvent, kPlayerEventHex) && HexBytesAt(kPlayerEventType, kPlayerEventTypeHex) &&
               HexBytesAt(kPlayerEventCall, kPlayerEventCallHex);
    if (!g_lookEnabled)
        Log(1, "shadow look: off ([Look] Enabled=0) - no player events at start / stop");
    else if (!g_lookOk)
        Log(0, "shadow look: player event walker at 0x%08lx does not match - look not translated", kPlayerEvent);
    else
        Log(1, "shadow look: player event walker tru+0x318780 verified - start fires 0x89 0x32 (0x81) 0x87/0x88, stop "
               "0x33 0x7e/0x82 (TU 0x823d7d40 / 0x823d7fb8)");
    g_msgOk = HexBytesAt(kInstWalk, kInstWalkHex) && HexBytesAt(kInstNext, kInstNextHex) &&
              HexBytesAt(kInstQuery, kInstQueryHex) && HexBytesAt(kInstWake, kInstWakeHex);
    if (g_lookEnabled && g_lookMessages)
        Log(g_msgOk ? 1 : 0, g_msgOk ? "shadow look: instance list [0x%08lx] / query +0x11c / wake tru+0x1b2de0 verified - "
                                       "start / stop send 0x1f4 / 0x1f5 to the instances answering 0x172"
                                     : "shadow look: instance list code at 0x%08lx does not match - messages 0x1f4 / 0x1f5 "
                                       "not sent", g_msgOk ? kInstanceHead : kInstWalk);
    else if (g_lookEnabled)
        Log(1, "shadow look: messages 0x1f4 / 0x1f5 off ([Look] Messages=0)");
    MeterInit();
    g_tuStatesOk = true;
    for (const auto &c : kTuBlocks)
        if (!HexBytesAt(c.address, c.bytes)) {
            Log(0, "0.5 building block at 0x%08lx does not match - TU states / 1048 / 2401 / activities not registered",
                c.address);
            g_tuStatesOk = false;
            break;
        }
    RegisterLaraConditions();
    RegisterLaraStates();
    if (g_cond1046) Patch1046();
    // 0.9: TU gates of the tick / start and the game input chain
    g_gatesOk = HexBytesAt(kCinematic, kCinematicHex) && HexBytesAt(kBlockGetter, kBlockGetterHex) &&
                HexBytesAt(kBlockSetter, kBlockSetterHex) && HexBytesAt(kBlockSetterCall, kBlockSetterCallHex) &&
                HexBytesAt(kGtxFlagsCheck, kGtxFlagsCheckHex);
    g_inputOk = HexBytesAt(kInputCheck, kInputCheckHex);
    if (g_legacyPadStart)
        Log(1, "tick: LEGACY 0.8 path ([ShadowPower] LegacyPadStart=1) - power in every level, no cinematic gates");
    else if (g_gatesOk)
        Log(1, "tick: TU path - only with the doppelganger flag (TU 0x824128a8); cinematic tru+0x53f00, block byte "
               "0x%08lx, game flag 0x%08lx bit 0 and health gt+0x628 gate the power as TU 0x823d7a10 / 0x823d7d40",
            kBlockByte, kGtxFlags);
    else
        Log(0, "tick: TU path, but the cinematic / block byte / game flag code does not match - those gates are off "
               "(the doppelganger gate stays)");
    if (g_gameInput && !g_inputOk) {
        Log(0, "GameInput=1 but the input chain at 0x%08lx does not match - buttons from the pad poll", kInputCheck);
        g_gameInput = 0;
    } else if (!g_legacyPadStart) {
        Log(1, "buttons: %s", g_gameInput ? "game input records +0x1a70 / +0x1b30 & 4 (TU 0x823d7b6c, GameInput=1)"
                                          : "pad poll LB / RB (XInput); the TU reads the game records +0x1a70 / +0x1b30");
    }
    if (g_legacyPadStart)
        Log(1, "adrenaline look: off with LegacyPadStart=1 (meter flag 0x40 comes from the TU tick only)");
    else if (g_lookEnabled)
        PatchAdrenalineMode();
    else
        Log(1, "adrenaline look: off ([Look] Enabled=0)");
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
    return "TruShadowPower 0.9 (translated TU meter with the TU tick gates, Lara conditions 1046 / 1047 / 1048-1056 / "
           "2401, states 243 / 245 / 1018, activities 1009 / 1039, shadow look = TU player events of start / stop, "
           "adrenaline look = meter flag 0x40 / camera mode 0x34)";
}
