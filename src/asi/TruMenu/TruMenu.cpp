// TruMenu.asi - in-game debug menu for the PC tru.exe (Steam, Tomb Raider: Underworld, image base 0x400000),
// operated with the Xbox controller (L3 + R3 opens / closes it), drawn with Dear ImGui (MIT, src/asi/third_party).
//
// Hooks (every address is checked against the expected bytes first; on a mismatch that part stays off and the reason
// is logged - see README.md):
//   pad    The game loads XInput itself: tru+0x824f0 calls LoadLibraryW("xinput9_1_0.dll") and GetProcAddress through
//          the import slot 0x0083e08c and stores "XInputGetState" in 0x00a02b8c (the pointer the per-frame pad poll
//          tru+0x84b82 calls). TruMenu replaces that import slot at load time with a filter that hands out its own
//          PadHook for "XInputGetState" - so the game itself writes PadHook into 0x00a02b8c, before any other plugin
//          can wrap the pointer. TruShadowPower.asi (waits for the pointer, then wraps whatever is there) therefore
//          always wraps PadHook, whatever the load order of the two plugins. PadHook calls the real XInputGetState,
//          watches L3 + R3 and hands the game a neutral pad while the menu is open. Project chaining rule (shared
//          with TruShadowPower / TruLink): hook once, re-hook only when the slot points into xinput*.dll again,
//          thread-local re-entry guard that calls the real XInputGetState. When the game does not poll the slot
//          (front end, loading) the Present hook reads the pad itself after 250 ms.
//   d3d9   The game's device manager is [0x00ad75e4] (created at tru+0x1239c0), its IDirect3DDevice9 at +0x20 (out
//          parameter of the CreateDevice call tru+0x122736; +0x208 are the present parameters). A worker thread waits for that device and patches the
//          device's own vtable entries Reset (16) and Present (17). This works with or without a d3d9.dll proxy
//          (TRAWindowed): the vtable patched is the one of the object the game calls.
//   game   Every menu entry is an item with a stable id (kItems); items that touch the game (cheat, camera, level
//          change, debug flag) are queued and run on the game thread inside PadHook - or inside the Present hook
//          while the game does not poll the pad. Exports TruMenuList / TruMenuInvoke make them callable without the
//          controller (TruLink "menu" command).
//
// Facts about engine functions marked "TRLAU" were learned from TheIndra55/TRLAU-menu-hook (GPL v3), read as reference
// only; no code was taken from it (README.md, Credits).

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d9.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <ctype.h>
#include <math.h>

#include "imgui.h"
#include "imgui_internal.h"                 // 0.6: ClearActiveID (command bar -> pad picker)
#include "imgui_impl_dx9.h"
#include "imgui_impl_win32.h"

extern IMGUI_IMPL_API LRESULT ImGui_ImplWin32_WndProcHandler(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam);

namespace {

const char *const kVersion = "TruMenu 0.7.2 (game.quit: TerminateProcess with exit code 0x544D after a safety step; "
                             "level.load / level.start refused while a level change or a mission start is pending; "
                             "level.start: the title update's outfit rule ([Levels] OutfitRule, DLC 2 without the outfit "
                             "selection); log overlay filter [Log] OverlaySources / OverlayExclude; "
                             "0.7.1: game input frozen while the menu is open: [Menu] BlockGameInput = the "
                             "game's DirectInput keyboard and key messages, [Menu] PauseGame; B twice = keyboard, then "
                             "menu; real keyboard switch without hover; [Test] AutoStart = level.start (mission menu "
                             "path, intro plays); [Log] UnitChanges; "
                             "0.7: command bar without a keyboard: L3 = focus + on-screen keyboard, the mouse "
                             "belongs to the menu while it is open, [Cmd] UpOpensHistory / FirstPadPressOnlyFocuses; "
                             "TruGuard action guard.dump: full minidump + thread snapshot on the TruLink "
                             "thread, also while the game hangs; 0.6: command bar: ids with autocomplete, history, pad "
                             "picker, cmd.*; 0.5: TO TEST "
                             "steps / checks / toggles + test.export; 0.4: TO TEST checklist over "
                             "TruLink, log collapse / filters / rate limit, weapon "
                             "slots, ammo fill, gear give; debug menu: Crystal's original developer menu from the exe's "
                             "tables, time / player / HUD, instances, live outfit switch, log page + overlay, videos, "
                             "status, outfits, level select, Lara position overlay, cheat / camera; items callable by id)";

struct PadState {                       // XINPUT_STATE without including xinput.h
    DWORD dwPacketNumber;
    WORD wButtons;
    BYTE bLeftTrigger, bRightTrigger;
    SHORT sThumbLX, sThumbLY, sThumbRX, sThumbRY;
};

typedef DWORD(WINAPI *XInputGetStateFn)(DWORD, PadState *);
typedef FARPROC(WINAPI *GetProcAddressFn)(HMODULE, LPCSTR);
typedef HRESULT(STDMETHODCALLTYPE *PresentFn)(IDirect3DDevice9 *, const RECT *, const RECT *, HWND, const RGNDATA *);
typedef HRESULT(STDMETHODCALLTYPE *ResetFn)(IDirect3DDevice9 *, D3DPRESENT_PARAMETERS *);
typedef void(__cdecl *InstancePostFn)(void *instance, int message, int data);
typedef void(__cdecl *CameraSetModeFn)(int mode);
typedef void(__fastcall *CameraRestoreFn)(void *manager, int);   // thiscall without arguments
typedef void(__cdecl *LevelChangeFn)(char *name, void *gameTracker, int doneType);

const WORD kPadL3 = 0x0040, kPadR3 = 0x0080;

// ---- addresses (PC tru.exe, Steam) ----
const DWORD kImageBase = 0x00400000;
// pad: tru+0x824f0 loads XInput; the import slot of GetProcAddress, the pointer it fills, the per-frame poll
const DWORD kPadLoader = 0x004824f0;
const char *const kPadLoaderBytes = "68a84b8400 ff1590e08300 85c0 a3882ba000 743b 56 8b358ce08300 68984b8400 50 ffd6"
                                    " a38c2ba000";
const DWORD kGetProcSlot = 0x0083e08c;
const DWORD kPadPointer = 0x00a02b8c;
const DWORD kPadCallSite = 0x00484b82;
const char *const kPadCallBytes = "ff158c2ba000";              // call dword ptr [0x00a02b8c]
const DWORD kXInputName = 0x00844b98;                          // "XInputGetState"
// d3d9: device manager global and the device field (CreateDevice out parameter)
const DWORD kD3dCreate = 0x005239c0;
const char *const kD3dCreateBytes = "a1e475ad00 85c0 56 57 0f859c000000 6810b68400 ff15b8e08300";
const DWORD kD3dStore = 0x00523a30;
const char *const kD3dStoreBytes = "a3e475ad00";
// CreateDevice(adapter, type, [esi+0x14] window, [esi+0x248] flags, esi+0x208 present params, esi+0x20 ppDevice);
// +0x208 holds the present parameters (1920 / 1080 / format 0x15 seen live 31.10.), the device is at +0x20
const DWORD kCreateDeviceCall = 0x0052270a;
const char *const kCreateDeviceBytes = "8d6e20 55";            // lea ebp, [esi+0x20]; push ebp (ppDevice)
const DWORD kCreateDeviceCall2 = 0x00522733;
const char *const kCreateDeviceBytes2 = "8b4a40 ffd1";         // mov ecx, [edx+0x40]; call ecx (IDirect3D9 slot 16)
const DWORD kDeviceManager = 0x00ad75e4;
const DWORD kDeviceField = 0x20;
// game state
const DWORD kGameTracker = 0x00e7f088;                         // TRLAU: GameTracker
const DWORD kPlayerPtr = 0x00e7f094;                           // GameTracker +0xc playerInstance
const char *const kPlayerReaderBytes = "8b0d94f0e700";         // a reader at 0x00741764 (as TruShadowPower checks)
const DWORD kPlayerReader = 0x00741764;
const DWORD kInstancePosition = 0x20;                          // TRLAU Instance.h: position (16-byte vector)
const DWORD kInstanceRotation = 0x30;                          //                  rotation (16-byte vector)
const DWORD kCheatMode = 0x00e7f144;                           // GameTracker +0xbc cheatMode (TRLAU)
const DWORD kDebugFlags2 = 0x00e7f09c;                         // GameTracker +0x14 debugFlags2 (TRLAU)
const DWORD kInstancePost = 0x005b3750;                        // TRLAU: INSTANCE_Post (cdecl, ret)
const char *const kInstancePostBytes = "56 8b742408 8d8610010000 85c0 7422 57 8bbe20010000";
const DWORD kCameraSetMode = 0x005f39f0;                       // TRLAU / Befund-Entwicklerkanal: CAMERA_SetMode
const char *const kCameraSetModeBytes = "56 8b742408 83fe06 751e 813d3405e800e0eae800";
const DWORD kCameraRestore = 0x005edf50;                       // thiscall CameraManager, no arguments
const char *const kCameraRestoreBytes = "d90530118400 56 8bf1 33c9 d95e78";
const DWORD kCameraManager = 0x00e804f0;
const DWORD kCurrentCamera = 0x00e80534;                       // [manager + 0x44]
const volatile DWORD *const kGameClock = reinterpret_cast<const volatile DWORD *>(0x00e7f15c);
const DWORD kLevelChange = 0x005df8c0;                         // TRLAU: GAMELOOP_RequestLevelChangeByName (cdecl)
const char *const kLevelChangeBytes = "56 8b742408 57 56 e8d45e0600 8b7c2414 83c404 80bfb900000000 754d 834f2c01";
const DWORD kLevelNameCopy = 0x005df8ee;                       // add edi, 0x38: name copied to GameTracker+0x38
const DWORD kUnitName = 0x00e7f0c0;                            // GameTracker +0x38 (tru+0x3744ae reloads it)
const DWORD kFrameStore = 0x005da40c;
const char *const kFrameStoreBytes = "d91590f1e700";           // fst dword [0xe7f190] (frame time, 30 fps units)
const float *const kFrameTime = reinterpret_cast<const float *>(0x00e7f190);
// costume / game data (0.2; read from the PC tru.exe with tools/pe_dis.py, README "Outfits")
const DWORD kGameDataPtr = 0x00c59264;      // pointer to the game data (re-allocated by the new-game reset 0x556940)
const DWORD kGdMode = 0x1f4;                // u16: 0 = the level load reads +0x20c, else +0x210
const DWORD kGdChosen0 = 0x20c, kGdChosen1 = 0x20e, kGdChosen2 = 0x210;   // u16 chosen costume (object id)
const DWORD kLevelLoadChoice = 0x005de2d6;  // GAMELOOP_LevelLoadAndInit tru+0x1de2b0: chosen costume by +0x1f4
const char *const kLevelLoadChoiceBytes = "a16492c500 56 33f6 6639b0f4010000 7409 0fb78010020000 eb07 0fb7800c020000";
const DWORD kResetCostume = 0x00556abe;     // new-game reset (PC partner of TU 0x821fe9a8): +0x210 / +0x20e / +0x20c = 0
const char *const kResetCostumeBytes = "66899910020000 8b156492c500 66899a0e020000 a16492c500 6689980c020000";
const DWORD kSaveCostume = 0x00555cb1;      // game state save: word [game data +0x20c] = word [0xe7f1c8]
const char *const kSaveCostumeBytes = "66a1c8f1e700 6689820c020000";
const DWORD kCostumeNow = 0x00e7f1c8;       // costume object id set by the level load (= the player object)
const DWORD kObjNames = 0x00db94d0;         // pointer: +0 count, name of object id n at +n*8 (objectlist.txt)
const DWORD kNameLookup = 0x005bf770;       // name -> object id over [0xdb94d0] (0 = none)
const char *const kNameLookupBytes = "8b0dd094db00 56 33f6 3931 57 7e27 8b7c240c 8b44f108";
const DWORD kCostumeValid = 0x005c54e0;     // bool cdecl(id): id <= count and <name>.drm exists (tail call 0x5bf7b0)
const char *const kCostumeValidBytes = "8b442404 8b0dd094db00 3b01 7e03 32c0 c3 8b04c1";
const DWORD kTypeLookup = 0x005bf121;       // cmp [type table], esi in the type-by-name lookup tru+0x1bf0e0
const DWORD kTypeTableOrig = 0x008aba28;    // player type table {name, init, f2..f6}; TruDlc2Player may move it
const DWORD kPlayerF2 = 0x007228e0;         // f2 of every player record (TruDlc2Player's record has it too)
const DWORD kUnitId = 0x00e7f148;           // GameTracker +0xc0 current stream unit id (read at tru+0x1de379)
const DWORD kUnitLookup = 0x005c1b50;       // stream unit table 0xdbab40, 0xd8 per unit, +0 id, +4 state 2, +8 data
const char *const kUnitLookupBytes = "56 8b742408 33c0 33d2 b940abdb00 8bff 80790402 7504 3931 7413 81c1d8000000 83c201"
                                     " 81f940c6db00";
const DWORD kStreamUnits = 0x00dbab40, kStreamUnitsEnd = 0x00dbc640, kStreamUnitSize = 0xd8;
const DWORD kDefaultCostume = 0x005de379;   // unit default costume: [[unit+8]+0x70]+0x294 (u16 object id)
const char *const kDefaultCostumeBytes = "8b0d48f1e700 51 e8cb37feff 8b5008 8b4270 0fb78094020000";
const DWORD kObjectTable = 0x00db7400;      // 0xcc entries of 0x24: +8 object, +0xc s16 id, +0xe u16 state (TruLink)
const int kObjectEntries = 0xcc;
typedef bool(__cdecl *CostumeValidFn)(int id);

// ---- options (TruMenu.ini) ----
// 0.3: every key with its default and comment in one table. ReadOptions takes the defaults from here, settings.reset
// writes TruMenu.ini from it (DefaultIniText), and the shipped src/asi/TruMenu/TruMenu.ini is exactly that text
// (keep both in step; a '\n' in a comment starts a new "; " line).
struct OptDef { const char *section, *key, *def, *comment; };
const OptDef kOpts[] = {
    {"Menu", "Enabled", "1", "0 = load but hook nothing"},
    {"Menu", "LogLevel", "1", "0 errors, 1 info, 2 every menu toggle / action, 3 debug - TruMenu.log next to tru.exe"},
    {"Menu", "ToggleButtons", "192", "XInput buttons that open / close the menu together: 0x0040 L3 + 0x0080 R3 = 192 (0x00C0)"},
    {"Menu", "ToggleKey", "0", "keyboard key that also opens / closes the menu (virtual key code, e.g. 119 = F8); 0 = off"},
    {"Menu", "Scale", "1.5", "size of the menu (font and spacing), 0.5 .. 4"},
    {"Menu", "Overlay", "0", "1 = show the Lara position overlay from the start"},
    {"Menu", "FreeMouse", "1", "1 = while the menu is open the mouse belongs to the menu: a cursor is drawn, the game gets no "
                               "mouse messages (no camera\nturn, no re-centring) and its SetCursorPos / ClipCursor calls "
                               "wait until the menu closes; 0 = as before 0.7"},
    {"Menu", "BlockGameInput", "1", "1 = while the menu is open the game gets no keyboard: its DirectInput keyboard reads "
                                    "no key events (a key the game\nsaw going down is released once, a key still held "
                                    "at the close stays away until released) and key messages go to\nthe menu only; 0 = "
                                    "as 0.7 (pad: [Pad] BlockInput, mouse: FreeMouse)"},
    {"Menu", "PauseGame", "0", "1 = also pause the game time while the menu is open (time.pause: streamFlags bit 0x1000); "
                               "on close the state\nfrom before the menu comes back (unless time.pause was used meanwhile)"},
    {"Pad", "BlockInput", "1", "1 = the game gets a neutral pad while the menu is open; 0 = the game sees the pad as well"},
    {"Cheat", "Experimental", "1", "1 = show the experimental actions (cheat / flight, camera mode, level load, costumes, "
                                   "developer menu rows, time /\nplayer / instance / video items); 0 = read-only"},
    {"Cheat", "FlightSpeed", "20", "flight: units per 30 fps frame at full trigger (RT up, LT down) while cheat mode is on"},
    {"Levels", "List", "dlc_level1_start,dlc_level2_start", "units offered as buttons on the Level select page (comma list)"},
    {"Levels", "OutfitRule", "1", "level.start: 1 = as the title update's mission menu: dlc_level2_start (and "
                                  "dlc_level4..6_start) start without the outfit /\nweapon selection, every other unit "
                                  "with it; 0 = as the PC mission menu (script 104): always with the selection"},
    {"Log", "Overlay", "0", "1 = log lines (Tru*.log tails, script prints) in the bottom-left corner from the start"},
    {"Log", "Lines", "12", "lines on the Debug / Log page and in the overlay, 1 .. 64"},
    {"Log", "Script", "0", "1 = redirect the game's 8 script print / log natives to the log page from the start (patches 5 "
                           "bytes each)"},
    {"Log", "Collapse", "1", "1 = repeated lines (same source, same text after the time stamp) become one line \"text x42 "
                             "(17:09:02-17:09:33)\""},
    {"Log", "HideLinkReads", "1", "1 = drop TruLink's echo of read / scan / watch / ping commands and of menu reads (info "
                                  "items such as status.*,\ntest.list) - the lines never enter the log page"},
    {"Log", "MinLevel", "0", "lines shown on the page / overlay: 0 all, 1 warnings and errors, 2 errors only"},
    {"Log", "MaxLinesPerSecond", "40", "at most this many new lines per source and second (more are dropped and counted); "
                                       "0 = no limit"},
    {"Log", "UnitChanges", "1", "1 = a line \"unit: <name> (was <name>)\" when Lara moves into another stream unit "
                                "(TruMenu.log, log page and overlay)"},
    {"Log", "OverlaySources", "TruMenu,TruGuard", "sources the corner overlay shows (comma list of log names: TruMenu, "
                                                  "TruGuard, TruShadowPower, TruRockVein,\nTruLink, TruDlc2Player, "
                                                  "script, ...); * = all. Overlay only - the log page and the log files "
                                                  "stay complete"},
    {"Log", "OverlayExclude", "", "overlay only: lines holding one of these texts are not shown (comma list, e.g. "
                                  "activity 1009,markup subtest); empty = none"},
    {"Favorites", "Ids", "", "item ids on the \"Quick access / Favourites\" page (comma list); empty = default list. Y on an "
                             "item in the menu\npins / unpins it and rewrites this line (TruLink: menu fav.add <id> / "
                             "fav.del <id> / fav.list)"},
    {"Cmd", "Enabled", "1", "1 = command bar under the menu: type item ids as over TruLink without \"menu\" (\"time.scale 0.5\", "
                            "\"help\"); the\nkeyboard focus goes to it when the menu opens, D-pad / stick go on into the "
                            "menu, View / F2 / Tab come back"},
    {"Cmd", "HistorySize", "32", "commands kept in TruMenu.history.txt next to tru.exe (Up in the empty bar), 1 .. 64"},
    {"Cmd", "FocusButton", "64", "XInput button that puts the focus into the command bar and opens the on-screen keyboard "
                                 "while the menu is open\n(pressed and released alone, not as part of the open / close "
                                 "combo): 0x0040 L3 = 64; again = keyboard closed; 0 = off"},
    {"Cmd", "Keyboard", "1", "1 = on-screen keyboard under the bar when the bar gets the focus by controller (FocusButton, "
                             "A in the idle bar, View in\nthe pad picker); a key on a real keyboard closes it again"},
    {"Cmd", "UpOpensHistory", "1", "1 = Up in the empty bar opens the history (Up older, Down newer); 0 = Up goes into the "
                                   "menu like Down (Ctrl + Up\nstill opens the history)"},
    {"Cmd", "FirstPadPressOnlyFocuses", "1", "1 = the first D-pad / stick press in the bar only moves the focus into the "
                                             "menu; 0 = the same press also moves\nin the menu at once"},
    {"Test", "AutoStart", "", "test only: dlc2 (or dlc1) = once per game start, when the main menu is up, start that DLC "
                              "the way the mission\nmenu does (level.start, the intro plays); empty = off"},
    {"Test", "AutoStartDelay", "3", "seconds the main menu must be up before AutoStart starts the level, 1 .. 60"},
};
const char *const kIniHeader = "TruMenu.asi options - put next to tru.exe together with TruMenu.asi (optional; defaults below)";

const char *OptDefault(const char *section, const char *key) {
    for (const OptDef &o : kOpts)
        if (_stricmp(o.section, section) == 0 && _stricmp(o.key, key) == 0) return o.def;
    return "";
}
int OptInt(const char *ini, const char *section, const char *key) {
    return static_cast<int>(GetPrivateProfileIntA(section, key, atoi(OptDefault(section, key)), ini));
}
void OptString(const char *ini, const char *section, const char *key, char *out, DWORD size) {
    GetPrivateProfileStringA(section, key, OptDefault(section, key), out, size, ini);
}

int g_enabled = 1;
int g_logLevel = 1;                     // 0 errors, 1 info, 2 actions, 3 debug
WORD g_toggleButtons = kPadL3 | kPadR3;
int g_toggleKey = 0;                    // virtual key (e.g. 119 = F8), 0 = off
int g_blockInput = 1;
float g_scale = 1.5f;
int g_overlayAtStart = 0;
int g_logOverlayAtStart = 0, g_logLinesAtStart = 12, g_scriptLogAtStart = 0;   // 0.3 [Log]
volatile LONG g_logCollapse = 1, g_logHideReads = 1;                         // 0.4 [Log] Collapse / HideLinkReads
int g_logMinLevel = 0, g_logRate = 40;                                       // 0.4 [Log] MinLevel / MaxLinesPerSecond
int g_experimental = 1;
float g_flightSpeed = 20.0f;
int g_cmdEnabled = 1, g_cmdHistSize = 32;                                    // 0.6 [Cmd] Enabled / HistorySize
int g_freeMouse = 1;                                                         // 0.7 [Menu] FreeMouse
WORD g_cmdFocusButton = 0x0040;                                              // 0.7 [Cmd] FocusButton (L3)
int g_cmdKeyboard = 1, g_cmdUpHistory = 1, g_cmdFirstPressFocus = 1;         // 0.7 [Cmd] Keyboard / UpOpensHistory /
                                                                             //     FirstPadPressOnlyFocuses
int g_blockGameInput = 1, g_pauseGame = 0;                                   // 0.7.1 [Menu] BlockGameInput / PauseGame
int g_unitChanges = 1;                                                       // 0.7.1 [Log] UnitChanges
char g_autoStart[24] = "";                                                   // 0.7.1 [Test] AutoStart ("" = off)
int g_autoStartDelay = 3;                                                    // 0.7.1 [Test] AutoStartDelay (seconds)
volatile LONG g_menuPaused = 0;                                              // 0.7.1: TruMenu set the pause bit
const char *g_pauseMode = "off ([Menu] PauseGame=0)";                        // 0.7.1 status texts
const char *g_autoStartMode = "off ([Test] AutoStart empty)";
int g_outfitRule = 1;                                                        // 0.7.2 [Levels] OutfitRule
bool g_pendingOk = false;                                                    // 0.7.2: main state 2 / 9 code checks
bool g_outfitRuleOk = false;                                                 // 0.7.2: f27 arg 2 = selection flag checks

// ---- state ----
char g_logPath[MAX_PATH];
CRITICAL_SECTION g_logLock;
CRITICAL_SECTION g_padLock;
volatile LONG g_stop = 0;
volatile LONG g_menuOpen = 0;
volatile LONG g_menuJustOpened = 0;
volatile LONG g_overlay = 0;
volatile LONG g_guardOverlay = 0;        // TruGuard status in the top-right corner (opt-in, plugin is optional)
volatile LONG g_testFocus = 0;          // 0.4: a TO TEST row had the nav focus last frame (X / Y go to the row)
volatile LONG g_testX = 0, g_testY = 0; // 0.4: X / Y pressed while a row had the focus (edges, consumed by the page)
// 0.6 command bar: pad ownership (FeedGamepad, from the bar state of the last frame) and keyboard capture (WndProcHook)
volatile LONG g_cmdWantText = 0;        // ImGui took text input last frame: WM_KEYDOWN / WM_CHAR stay away from the game
bool g_cmdOwnPad = false;               // the bar (text field or pad picker) had the focus last frame
WORD g_cmdPadEdges = 0;                 // bar buttons pressed this frame (left stick folded into the D-pad bits)
WORD g_cmdPadHeld = 0;                  // bar buttons held (owned by the bar), for the repeat
bool g_cmdBackEdge = false;             // View / Back pressed this frame (focuses the bar from the menu)
// 0.7: controller focus + on-screen keyboard, mouse release
volatile LONG g_cmdOskReq = 0;          // 1 = FocusButton tapped (toggle the keyboard), 2 = cmd.keyboard (open it)
bool g_cmdHandOver = false;             // FirstPadPressOnlyFocuses=0: the D-pad press that left the bar goes on to ImGui
bool g_oskOpen = false;                 // on-screen keyboard shown under the bar (render thread)
UINT g_bbWidth = 0, g_bbHeight = 0;     // back buffer size of the last frame (mouse coordinates are scaled to it)

bool g_levelOk = false;
bool g_baseOk = false, g_padCodeOk = false, g_d3dCodeOk = false, g_playerOk = false, g_postOk = false,
     g_cameraOk = false, g_frameOk = false;
bool g_costumeOk = false;               // level-load choice, reset, name table, validator, type table checked
bool g_unitOk = false;                  // stream unit table / unit default costume checked
volatile GetProcAddressFn g_getProcOriginal = nullptr;
volatile XInputGetStateFn g_padOriginal = nullptr;   // what PadHook calls (the real XInputGetState)
volatile XInputGetStateFn g_selfPoll = nullptr;      // fallback: own reads when PadHook could not be placed
volatile XInputGetStateFn g_padReal = nullptr;        // XInputGetState inside the xinput module (re-entry guard)
const char *g_padMode = "waiting";
bool g_padSetupDone = false;
bool g_padModeIdle = false;             // the game has not polled the pad slot for 250 ms (front end?)
PadState g_pad[4];                                    // last real state per pad (before neutralising)
bool g_padConnected[4];
bool g_comboHeld[4];
bool g_swallow[4];
int g_lastPad = 0;
DWORD g_lastClock = 0;

volatile PresentFn g_presentOriginal = nullptr;
volatile ResetFn g_resetOriginal = nullptr;
IDirect3DDevice9 *volatile g_device = nullptr;
const char *g_d3dMode = "waiting for the device";
HWND g_hwnd = nullptr;
WNDPROC g_wndProcOriginal = nullptr;
bool g_imguiReady = false;
bool g_imguiFailed = false;
IDirect3DDevice9 *g_imguiDevice = nullptr;
bool g_keyHeld = false;

// game-thread request slot (one at a time): written by the menu / TruMenuInvoke, run by PadHook (or by the Present
// hook when the game has not polled the pad for 250 ms, e.g. in the front end)
CRITICAL_SECTION g_reqLock;
HANDLE g_reqDone = nullptr;
volatile LONG g_reqPending = 0;
char g_reqId[64], g_reqArg[160], g_reqResult[1024];
char g_lastAction[1024] = "none";
volatile DWORD g_lastPadHookTick = 0;
bool g_flight = false;                  // our view of GameTracker.cheatMode after our own toggle
int g_cameraModeChoice = 11;
char g_levelList[1024] = "";            // [Levels] List (comma separated unit names)
char g_iniPath[MAX_PATH] = "";
char g_favs[1024] = "";                 // 0.3 [Favorites] Ids (comma separated item ids)
CRITICAL_SECTION g_favLock;
const char *const kFavDefault = "player.invincible,player.health,time.scale,time.pause,level.reload,camera.free,"
                                "overlay.position,log.overlay,costume.next";

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

bool HexBytesAt(DWORD address, const char *hex) {
    BYTE buf[64];
    size_t n = 0;
    for (const char *p = hex; *p && n < sizeof(buf);) {
        if (*p == ' ') { ++p; continue; }
        char pair[3] = {p[0], p[1], 0};
        buf[n++] = static_cast<BYTE>(strtoul(pair, nullptr, 16));
        p += 2;
    }
    __try {
        return memcmp(reinterpret_cast<const void *>(address), buf, n) == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool ReadDword(DWORD address, DWORD *out) {
    __try {
        *out = *reinterpret_cast<const volatile DWORD *>(address);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool ReadFloats(DWORD address, float *out, int count) {
    __try {
        for (int i = 0; i < count; ++i) out[i] = reinterpret_cast<const volatile float *>(address)[i];
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// module that holds an address ("?" if none) - for the status page and the log
void ModuleOf(const void *address, char *out, size_t size) {
    HMODULE module = nullptr;
    out[0] = '?';
    out[1] = 0;
    if (!address || !GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                                        static_cast<LPCSTR>(address), &module))
        return;
    char path[MAX_PATH];
    DWORD len = GetModuleFileNameA(module, path, MAX_PATH);
    if (!len) return;
    const char *name = path + len;
    while (name > path && name[-1] != '\\' && name[-1] != '/') --name;
    strncpy_s(out, size, name, _TRUNCATE);
}

bool WriteDword(DWORD address, DWORD value) {
    DWORD old = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(address), sizeof(DWORD), PAGE_EXECUTE_READWRITE, &old)) return false;
    InterlockedExchange(reinterpret_cast<volatile LONG *>(address), static_cast<LONG>(value));
    DWORD unused = 0;
    VirtualProtect(reinterpret_cast<void *>(address), sizeof(DWORD), old, &unused);
    return true;
}

void RunPending();     // items section below
bool InLevel();
void WeaponsTick();    // 0.3 costume switch: player message 35 a frame later
void InvincibleTick(); // 0.3 player.invincible: health = MaxHealth once per game frame
void LogTailTick();    // 0.3 log page: tail Tru*.log once per second (worker thread)

// flight: while cheat mode is on and the menu is closed, the triggers move Lara up (RT) / down (LT) - TRLAU moves
// position.z the same way with keys
void FlightTick(const PadState &pad) {
    if (!g_flight || !g_playerOk || !g_frameOk) return;
    __try {
        if (!*reinterpret_cast<volatile BYTE *>(kCheatMode)) { g_flight = false; return; }
        DWORD player = *reinterpret_cast<volatile DWORD *>(kPlayerPtr);
        if (!player) return;
        float frames = *kFrameTime;
        if (!(frames >= 0.0f && frames < 30.0f)) frames = 0.0f;
        float up = (pad.bRightTrigger > 30 ? pad.bRightTrigger / 255.0f : 0.0f) -
                   (pad.bLeftTrigger > 30 ? pad.bLeftTrigger / 255.0f : 0.0f);
        if (up != 0.0f) *reinterpret_cast<volatile float *>(player + kInstancePosition + 8) += up * g_flightSpeed * frames;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        g_flight = false;
    }
}

// ---- pad ----
void ToggleMenu(const char *by) {
    LONG open = !InterlockedCompareExchange(&g_menuOpen, 0, 0);
    InterlockedExchange(&g_menuOpen, open);
    if (open) InterlockedExchange(&g_menuJustOpened, 1);
    Log(1, "menu %s (%s)", open ? "opened" : "closed", by);   // 0.7.1: level 1 - the reason of every close in the log
}

// real pad state in, toggle detection; returns true when the game must get a neutral state
bool OnPad(DWORD index, bool connected, const PadState *state) {
    if (index > 3) return false;
    EnterCriticalSection(&g_padLock);
    g_padConnected[index] = connected;
    WORD buttons = connected ? state->wButtons : 0;
    if (connected) {
        g_pad[index] = *state;
        if (buttons) g_lastPad = static_cast<int>(index);
    }
    bool combo = (buttons & g_toggleButtons) == g_toggleButtons;
    bool toggled = false;
    if (combo && !g_comboHeld[index]) {
        g_comboHeld[index] = true;
        g_swallow[index] = true;
        toggled = true;
    } else if (!combo) {
        g_comboHeld[index] = false;
    }
    // after a toggle the pad stays neutral until both sticks are released, so the game never sees the half combo
    if (g_swallow[index] && !(buttons & g_toggleButtons)) g_swallow[index] = false;
    bool neutral = g_swallow[index];
    LeaveCriticalSection(&g_padLock);
    if (toggled) ToggleMenu("pad");
    return neutral || (g_blockInput && g_menuOpen);
}

// project chaining rule (TruShadowPower / TruLink / TruMenu share the slot 0x00a02b8c): hook once, re-hook only when
// the slot points into the real XInputGetState again, and on re-entry on the same thread call the real one directly
__declspec(thread) int t_padDepth = 0;

bool IsXInputModule(const void *address) {
    char owner[MAX_PATH];
    ModuleOf(address, owner, sizeof(owner));
    return _strnicmp(owner, "xinput", 6) == 0;
}

XInputGetStateFn RealXInput() {
    XInputGetStateFn real = g_padReal;
    if (real) return real;
    const char *const names[] = {"xinput9_1_0.dll", "xinput1_3.dll", "xinput1_4.dll"};
    for (const char *name : names) {
        HMODULE module = GetModuleHandleA(name);
        if (module && (real = reinterpret_cast<XInputGetStateFn>(GetProcAddress(module, "XInputGetState"))) != nullptr) {
            g_padReal = real;
            return real;
        }
    }
    return nullptr;
}

DWORD WINAPI PadHook(DWORD index, PadState *state) {
    if (t_padDepth > 0) {                     // re-entered through another plugin's wrapper: no second pass
        XInputGetStateFn real = RealXInput();
        return real ? real(index, state) : ERROR_DEVICE_NOT_CONNECTED;
    }
    ++t_padDepth;
    XInputGetStateFn original = g_padOriginal;
    DWORD result = original ? original(index, state) : ERROR_DEVICE_NOT_CONNECTED;
    --t_padDepth;
    bool connected = result == ERROR_SUCCESS && state;
    PadState copy = {};
    if (connected) copy = *state;
    if (OnPad(index, connected, &copy) && connected) {
        DWORD packet = state->dwPacketNumber;
        memset(state, 0, sizeof(*state));
        state->dwPacketNumber = packet;
    }
    g_lastPadHookTick = GetTickCount();
    if (g_reqPending) RunPending();           // game thread; the game clock may stand still (front end, pause)
    DWORD clock = *kGameClock;
    if (clock != g_lastClock) {               // once per game frame (the game polls several pads per frame)
        g_lastClock = clock;
        if (!g_menuOpen && connected) FlightTick(copy);
        WeaponsTick();
        InvincibleTick();
    }
    return result;
}

FARPROC WINAPI GetProcHook(HMODULE module, LPCSTR name) {
    GetProcAddressFn original = g_getProcOriginal;
    FARPROC result = original(module, name);
    if (result && HIWORD(reinterpret_cast<DWORD_PTR>(name)) && strcmp(name, "XInputGetState") == 0 &&
        reinterpret_cast<FARPROC>(&PadHook) != result) {
        if (IsXInputModule(reinterpret_cast<const void *>(result))) g_padReal = reinterpret_cast<XInputGetStateFn>(result);
        g_padOriginal = reinterpret_cast<XInputGetStateFn>(result);
        g_padMode = "PadHook given to the game (import filter)";
        char owner[MAX_PATH];
        ModuleOf(reinterpret_cast<const void *>(result), owner, sizeof(owner));
        Log(1, "pad: game asked for XInputGetState (0x%08lx, %s) - handed out PadHook", reinterpret_cast<DWORD>(result),
            owner);
        return reinterpret_cast<FARPROC>(&PadHook);
    }
    return result;
}

// ---- d3d9 ----
void PatchVtable(void **vtable, int index, void *hook, void *volatile *original, const char *what) {
    if (vtable[index] == hook) return;
    DWORD old = 0;
    if (!VirtualProtect(&vtable[index], sizeof(void *), PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "d3d9: VirtualProtect on the vtable failed (%lu) - %s not hooked", GetLastError(), what);
        return;
    }
    *original = vtable[index];               // set before the swap: the game may call it right away
    InterlockedExchange(reinterpret_cast<volatile LONG *>(&vtable[index]),
                        static_cast<LONG>(reinterpret_cast<DWORD_PTR>(hook)));
    DWORD unused = 0;
    VirtualProtect(&vtable[index], sizeof(void *), old, &unused);
    char owner[MAX_PATH];
    ModuleOf(*original, owner, sizeof(owner));
    Log(1, "d3d9: %s hooked (vtable 0x%08lx slot %d, original 0x%08lx in %s)", what, reinterpret_cast<DWORD>(vtable),
        index, reinterpret_cast<DWORD>(*original), owner);
}

// ---- 0.7 mouse release while the menu is open ----
// The game turns the camera from WM_MOUSEMOVE in its class window procedure 0x478bc0 (tru+0x78e7b: delta to the client
// centre -> 0x4827d0, then SetCursorPos(centre) through the import slot 0x0083e308, ShowCursor(FALSE) until hidden,
// ClipCursor(client rect) through 0x0083e2e0; without capture it shows the cursor and calls ClipCursor(NULL)). The
// activation path (tru+0x791b6) also centres + clips. tru.exe imports no raw input; it creates DirectInput8 (CoCreate,
// EnumDevices tru+0x865f7 with callback 0x486380) but GUID_SysMouse is not in the file - not verified live that no
// mouse comes that way. So while the menu is open: mouse messages go to ImGui only, and the two import slots
// point to holders that remember the game's request instead of moving / clipping; on close the slots are restored and
// the game's last request (or the state from before the menu) is applied once.
typedef BOOL(WINAPI *SetCursorPosFn)(int, int);
typedef BOOL(WINAPI *ClipCursorFn)(const RECT *);
const DWORD kSetCursorPosSlot = 0x0083e308, kClipCursorSlot = 0x0083e2e0;   // dumpbin /imports tru.exe (USER32 IAT
                                                                             // 0x83e278: entries 36 and 26)
volatile DWORD *g_setCursorPosSlot = nullptr, *g_clipCursorSlot = nullptr;   // found by name in the import directory
volatile SetCursorPosFn g_setCursorPosGame = nullptr;                        // what the slot held when the menu opened
volatile ClipCursorFn g_clipCursorGame = nullptr;
volatile LONG g_mouseHeld = 0;                                               // slots point to the holders
const char *g_mouseMode = "waiting for the first menu open";
bool g_mouseSlotsOk = false;
CRITICAL_SECTION g_mouseLock;
bool g_heldPosSet = false, g_heldClipSet = false, g_heldClipNull = false;    // the game's requests while held
POINT g_heldPos = {}, g_openPos = {};
RECT g_heldClip = {}, g_openClip = {};
bool g_openPosOk = false, g_openClipOk = false;
LONG g_heldCalls = 0;

BOOL WINAPI SetCursorPosHold(int x, int y) {
    if (!g_mouseHeld) {                          // released meanwhile: pass on
        SetCursorPosFn game = g_setCursorPosGame;
        return game ? game(x, y) : SetCursorPos(x, y);
    }
    EnterCriticalSection(&g_mouseLock);
    g_heldPos.x = x;
    g_heldPos.y = y;
    g_heldPosSet = true;
    ++g_heldCalls;
    LeaveCriticalSection(&g_mouseLock);
    return TRUE;
}

BOOL WINAPI ClipCursorHold(const RECT *rect) {
    if (!g_mouseHeld) {
        ClipCursorFn game = g_clipCursorGame;
        return game ? game(rect) : ClipCursor(rect);
    }
    EnterCriticalSection(&g_mouseLock);
    g_heldClipSet = true;
    g_heldClipNull = rect == nullptr;
    if (rect) g_heldClip = *rect;
    ++g_heldCalls;
    LeaveCriticalSection(&g_mouseLock);
    return TRUE;
}

// import slot of <dll>!<func> in tru.exe, by name (Import Name Table), or nullptr
volatile DWORD *FindImportSlot(const char *dll, const char *func) {
    __try {
        BYTE *base = reinterpret_cast<BYTE *>(GetModuleHandleA(nullptr));
        const IMAGE_DOS_HEADER *dos = reinterpret_cast<const IMAGE_DOS_HEADER *>(base);
        const IMAGE_NT_HEADERS32 *nt = reinterpret_cast<const IMAGE_NT_HEADERS32 *>(base + dos->e_lfanew);
        const IMAGE_DATA_DIRECTORY &dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
        if (!dir.VirtualAddress) return nullptr;
        for (const IMAGE_IMPORT_DESCRIPTOR *d = reinterpret_cast<const IMAGE_IMPORT_DESCRIPTOR *>(base + dir.VirtualAddress);
             d->Name; ++d) {
            if (_stricmp(reinterpret_cast<const char *>(base + d->Name), dll) != 0) continue;
            const IMAGE_THUNK_DATA32 *names = reinterpret_cast<const IMAGE_THUNK_DATA32 *>(
                base + (d->OriginalFirstThunk ? d->OriginalFirstThunk : d->FirstThunk));
            IMAGE_THUNK_DATA32 *slots = reinterpret_cast<IMAGE_THUNK_DATA32 *>(base + d->FirstThunk);
            for (; names->u1.AddressOfData; ++names, ++slots) {
                if (IMAGE_SNAP_BY_ORDINAL32(names->u1.Ordinal)) continue;
                const IMAGE_IMPORT_BY_NAME *ibn = reinterpret_cast<const IMAGE_IMPORT_BY_NAME *>(base + names->u1.AddressOfData);
                if (strcmp(reinterpret_cast<const char *>(ibn->Name), func) == 0)
                    return reinterpret_cast<volatile DWORD *>(&slots->u1.Function);
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return nullptr;
}

// at load: both slots by name, and they must be the ones the game's code calls (checked addresses, README "Mouse")
void MouseSetup() {
    g_setCursorPosSlot = FindImportSlot("USER32.dll", "SetCursorPos");
    g_clipCursorSlot = FindImportSlot("USER32.dll", "ClipCursor");
    // the class window procedure 0x478bc0 (WNDCLASS at tru+0x790cf) starts with cmp edi, WM_MOUSEMOVE; its centring
    // SetCursorPos / ClipCursor calls, and the activation path's pair
    bool code = HexBytesAt(0x00478bda, "81ff00020000") && HexBytesAt(0x004790cf, "c744241cc08b4700") &&
                HexBytesAt(0x00478f15, "ff1508e38300") && HexBytesAt(0x00478e75, "ff15e0e28300") &&
                HexBytesAt(0x004791b6, "ff1508e38300") && HexBytesAt(0x004791c1, "ff15e0e28300");
    g_mouseSlotsOk = code && reinterpret_cast<DWORD>(g_setCursorPosSlot) == kSetCursorPosSlot &&
                     reinterpret_cast<DWORD>(g_clipCursorSlot) == kClipCursorSlot;
    if (!g_freeMouse) g_mouseMode = "off ([Menu] FreeMouse=0) - the game gets the mouse while the menu is open";
    else if (g_mouseSlotsOk) g_mouseMode = "ready (mouse messages + SetCursorPos / ClipCursor held while the menu is open)";
    else g_mouseMode = "slots NOT matched - only the mouse messages are held";
    Log(1, "0.7 mouse: SetCursorPos slot 0x%08lx, ClipCursor slot 0x%08lx (expected 0x%08lx / 0x%08lx), game code %d -> "
           "%s", reinterpret_cast<DWORD>(g_setCursorPosSlot), reinterpret_cast<DWORD>(g_clipCursorSlot), kSetCursorPosSlot,
        kClipCursorSlot, code ? 1 : 0, g_mouseMode);
}

bool FullClip(const RECT &r) {               // GetClipCursor answers the virtual screen when nothing is clipped
    int x = GetSystemMetrics(SM_XVIRTUALSCREEN), y = GetSystemMetrics(SM_YVIRTUALSCREEN);
    return r.left <= x && r.top <= y && r.right >= x + GetSystemMetrics(SM_CXVIRTUALSCREEN) &&
           r.bottom >= y + GetSystemMetrics(SM_CYVIRTUALSCREEN);
}

// render thread, every Present: follow the menu state (hold on open, release on close)
void MouseTick() {
    bool want = g_menuOpen && g_freeMouse;
    if (want == (g_mouseHeld != 0)) return;
    if (want) {
        g_openPosOk = GetCursorPos(&g_openPos) != FALSE;
        RECT clip = {};
        g_openClipOk = GetClipCursor(&clip) && !FullClip(clip);
        g_openClip = clip;
        EnterCriticalSection(&g_mouseLock);
        g_heldPosSet = g_heldClipSet = false;
        g_heldCalls = 0;
        LeaveCriticalSection(&g_mouseLock);
        InterlockedExchange(&g_mouseHeld, 1);
        if (g_mouseSlotsOk) {
            DWORD pos = *g_setCursorPosSlot, clipSlot = *g_clipCursorSlot;
            if (pos != reinterpret_cast<DWORD>(&SetCursorPosHold)) {
                g_setCursorPosGame = reinterpret_cast<SetCursorPosFn>(pos);
                WriteDword(reinterpret_cast<DWORD>(g_setCursorPosSlot), reinterpret_cast<DWORD>(&SetCursorPosHold));
            }
            if (clipSlot != reinterpret_cast<DWORD>(&ClipCursorHold)) {
                g_clipCursorGame = reinterpret_cast<ClipCursorFn>(clipSlot);
                WriteDword(reinterpret_cast<DWORD>(g_clipCursorSlot), reinterpret_cast<DWORD>(&ClipCursorHold));
            }
        }
        ClipCursor(nullptr);                     // our own import, not the game's slot
        g_mouseMode = g_mouseSlotsOk ? "held (menu open): mouse messages to the menu only, SetCursorPos / ClipCursor held"
                                     : "held (menu open): mouse messages to the menu only (slots not matched)";
        Log(2, "mouse: held (cursor %ld,%ld, clip %s)", g_openPos.x, g_openPos.y, g_openClipOk ? "saved" : "none");
        return;
    }
    // release: slots back (only if they still hold ours), then the game's last wish or the state from before the menu
    if (g_mouseSlotsOk) {
        if (*g_setCursorPosSlot == reinterpret_cast<DWORD>(&SetCursorPosHold) && g_setCursorPosGame)
            WriteDword(reinterpret_cast<DWORD>(g_setCursorPosSlot), reinterpret_cast<DWORD>(g_setCursorPosGame));
        if (*g_clipCursorSlot == reinterpret_cast<DWORD>(&ClipCursorHold) && g_clipCursorGame)
            WriteDword(reinterpret_cast<DWORD>(g_clipCursorSlot), reinterpret_cast<DWORD>(g_clipCursorGame));
    }
    InterlockedExchange(&g_mouseHeld, 0);
    EnterCriticalSection(&g_mouseLock);
    bool posSet = g_heldPosSet, clipSet = g_heldClipSet, clipNull = g_heldClipNull;
    POINT pos = g_heldPos;
    RECT clip = g_heldClip;
    LONG calls = g_heldCalls;
    LeaveCriticalSection(&g_mouseLock);
    bool front = !g_hwnd || GetForegroundWindow() == g_hwnd;   // never trap the cursor in a window in the background
    if (front) {
        if (clipSet) ClipCursor(clipNull ? nullptr : &clip);
        else if (g_openClipOk) ClipCursor(&g_openClip);
        if (posSet) SetCursorPos(pos.x, pos.y);
        else if (g_openPosOk) SetCursorPos(g_openPos.x, g_openPos.y);   // the game's next delta starts from here
    }
    g_mouseMode = g_mouseSlotsOk ? "released (menu closed); held again while the menu is open"
                                 : "released (menu closed); slots not matched - only the mouse messages are held";
    Log(2, "mouse: released (%ld held game calls, %s)", calls, front ? "cursor / clip restored" : "game not in front");
}

bool IsMouseMessage(UINT msg) {
    return (msg >= WM_MOUSEFIRST && msg <= WM_MOUSELAST) || msg == WM_MOUSELEAVE;   // client area only (no raw input
                                                                                     // in tru.exe)
}

// client coordinates -> back-buffer pixels (ImGui draws in back-buffer pixels; a scaling window proxy makes them differ)
LPARAM ScaleMouse(HWND hwnd, UINT msg, LPARAM lParam) {
    if (msg == WM_MOUSEWHEEL || msg == WM_MOUSEHWHEEL || msg < WM_MOUSEFIRST || msg > WM_MOUSELAST) return lParam;
    RECT rc;
    if (!g_bbWidth || !g_bbHeight || !GetClientRect(hwnd, &rc) || rc.right <= 0 || rc.bottom <= 0) return lParam;
    if (static_cast<UINT>(rc.right) == g_bbWidth && static_cast<UINT>(rc.bottom) == g_bbHeight) return lParam;
    int x = static_cast<short>(LOWORD(lParam)), y = static_cast<short>(HIWORD(lParam));
    x = MulDiv(x, static_cast<int>(g_bbWidth), rc.right);
    y = MulDiv(y, static_cast<int>(g_bbHeight), rc.bottom);
    return MAKELPARAM(static_cast<WORD>(static_cast<short>(x)), static_cast<WORD>(static_cast<short>(y)));
}

// ---- 0.7.1 keyboard while the menu is open ([Menu] BlockGameInput) ----
// The game reads the keyboard through DirectInput, not through window messages (README "Keyboard while the menu is
// open", read with tools/pe_dis.py / pe_callers.py / pe_abs_uses.py): the EnumDevices callback 0x486380 builds for a
// DI8DEVTYPE_KEYBOARD device (cmp 0x13 at 0x4863f3) the wrapper 0x485e00 (vtable 0x844f5c, IDirectInputDevice8 at +4,
// c_dfDIKeyboard, buffer size 64, DISCL_NONEXCLUSIVE | DISCL_FOREGROUND) and stores it at input manager
// [0xa02b9c]+0x24. Every frame the input manager's read 0x483db0 calls the wrapper's slot 2 (0x483eea: call
// [vtable+8] with (events, room, full)) = 0x486100: buffered GetDeviceData (0x486020) or, after an overflow /
// re-acquire, the full GetDeviceState (0x485f10); both write 16-byte events {1, DIK code, time, value 1.0 / 0.0}.
// The window procedure 0x478bc0 only puts WM_CHAR and the Escape key-up (WM_KEYUP + VK_ESCAPE -> 0x477ae0) into the
// game's character queue 0x9eeb40 (the live test 2026-11-02 opened the pause menu with Esc; WM_KEYUP passed in 0.7).
// TruMenu replaces slot 2 of that vtable (only the keyboard wrapper uses it - constructor 0x485e3f / destructor
// 0x486160) and, while the menu is open, gives the game no key events - after the device was read, so nothing piles
// up - but once a release for every key the game saw going down; a key still held when the menu closes stays away
// from the game until it is released. Key messages go to ImGui only while the menu is open. Mouse / pad: unchanged.
struct KbdEvent { DWORD type; DWORD key; DWORD time; float value; };   // as written at 0x48609d / 0x485fb1
typedef int(__fastcall *KbdReadFn)(void *self, void *edx, KbdEvent *events, int room, int full);   // thiscall, ret 0xc
const DWORD kKbdSlot = 0x00844f64, kKbdRead = 0x00486100;
const char *const kKbdReadBytes = "56 8bf1 837e0400 7506 33c0 5e c20c00 807c241000 751e 80be9008000000";
volatile KbdReadFn g_kbdReadOriginal = nullptr;
bool g_kbdOk = false;
const char *g_kbdMode = "not set up";
BYTE g_kbdGameDown[256];                 // keys the game saw going down (game thread)
BYTE g_kbdRealDown[256];                 // keys down on the device, from the events read (game thread)
BYTE g_kbdSwallow[256];                  // held at the close: kept from the game until released (game thread)
LONG g_kbdHeldEvents = 0, g_kbdReleases = 0, g_kbdSwallowed = 0;
bool g_kbdWasBlocked = false;
BYTE g_msgKeyHeld[256];                  // WM_KEYDOWN kept from the game: its WM_KEYUP is kept away too (window thread)
volatile LONG g_oskRealKeys = 0;         // 0.7.1: real key presses while the menu is open (on-screen keyboard switch)

int __fastcall KbdReadHook(void *self, void *edx, KbdEvent *events, int room, int full) {
    KbdReadFn original = g_kbdReadOriginal;
    int n = original ? original(self, edx, events, room, full) : 0;
    if (!events || room <= 0 || n < 0 || n > room) return n;
    for (int i = 0; i < n; ++i)
        if (events[i].type == 1 && events[i].key < 256) g_kbdRealDown[events[i].key] = events[i].value > 0.5f ? 1 : 0;
    if (g_blockGameInput && g_menuOpen) {
        if (!g_kbdWasBlocked) Log(2, "keyboard: held (menu open)");
        g_kbdWasBlocked = true;
        g_kbdHeldEvents += n;
        int out = 0;
        DWORD now = GetTickCount();
        for (DWORD k = 0; k < 256 && out < room; ++k) {   // neutral state once: release what the game holds
            if (!g_kbdGameDown[k]) continue;
            KbdEvent &e = events[out++];
            e.type = 1;
            e.key = k;
            e.time = now;
            e.value = 0.0f;
            g_kbdGameDown[k] = 0;
            ++g_kbdReleases;
        }
        memcpy(g_kbdSwallow, g_kbdRealDown, sizeof(g_kbdSwallow));
        return out;
    }
    if (g_kbdWasBlocked) {
        g_kbdWasBlocked = false;
        Log(2, "keyboard: released (menu closed; %ld events held, %ld releases sent)", g_kbdHeldEvents, g_kbdReleases);
    }
    int out = 0;
    for (int i = 0; i < n; ++i) {
        KbdEvent e = events[i];
        if (e.type == 1 && e.key < 256) {
            bool down = e.value > 0.5f;
            if (g_kbdSwallow[e.key]) {          // held since the menu was open: the game never saw it go down
                if (!down) g_kbdSwallow[e.key] = 0;
                ++g_kbdSwallowed;
                continue;
            }
            g_kbdGameDown[e.key] = down ? 1 : 0;
        }
        events[out++] = e;
    }
    return out;
}

// at load: the wrapper vtable slot, after the byte checks (precheck list in README "Keyboard while the menu is open")
void KbdSetup() {
    if (!g_blockGameInput) {
        g_kbdMode = "off ([Menu] BlockGameInput=0) - the game reads the keyboard while the menu is open (as 0.7)";
        Log(1, "0.7.1 keyboard: %s", g_kbdMode);
        return;
    }
    DWORD slot = 0;
    bool code = HexBytesAt(kKbdRead, kKbdReadBytes) && HexBytesAt(0x00485e3f, "c7065c4f8400") &&
                HexBytesAt(0x004863f3, "83f813 754a") && HexBytesAt(0x0048641f, "e8dcf9ffff 8b0d9c2ba000 894124") &&
                HexBytesAt(0x00483eea, "8b4f24 8b01 8b4008 52 55 56 ffd0") &&
                HexBytesAt(0x0048609d, "8970f4 8b79fc 8978f8 f60180") &&
                HexBytesAt(0x00485fb1, "f6440c1480 8970f4 8948f8");
    bool slotOk = ReadDword(kKbdSlot, &slot) && slot == kKbdRead;
    if (!code || !slotOk) {
        g_kbdMode = "code / slot NOT matched - DirectInput keyboard not held, only the key messages";
        Log(0, "0.7.1 keyboard: code %d, slot 0x%08lx = 0x%08lx (expected 0x%08lx) -> %s", code ? 1 : 0, kKbdSlot, slot,
            kKbdRead, g_kbdMode);
        return;
    }
    g_kbdReadOriginal = reinterpret_cast<KbdReadFn>(slot);
    if (!WriteDword(kKbdSlot, reinterpret_cast<DWORD>(&KbdReadHook))) {
        g_kbdMode = "vtable slot not writable - only the key messages are held";
        Log(0, "0.7.1 keyboard: VirtualProtect failed (%lu) -> %s", GetLastError(), g_kbdMode);
        return;
    }
    g_kbdOk = true;
    g_kbdMode = "ready (DirectInput keyboard reads + key messages held while the menu is open)";
    Log(1, "0.7.1 keyboard: wrapper vtable slot 0x%08lx 0x%08lx -> KbdReadHook -> %s", kKbdSlot, slot, g_kbdMode);
}

bool IsKeyMessage(UINT msg) {
    return msg == WM_KEYDOWN || msg == WM_KEYUP || msg == WM_CHAR || msg == WM_DEADCHAR || msg == WM_SYSCHAR ||
           msg == WM_SYSDEADCHAR;   // WM_SYSKEYDOWN / UP pass: Alt + Tab, Alt + F4 (the game only filters Alt there)
}

LRESULT CALLBACK WndProcHook(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    if (g_imguiReady && g_menuOpen && msg == WM_KEYDOWN) {
        // 0.7.1: a real key for the on-screen keyboard switch (not Esc / modifiers / F2 / Tab / the toggle key)
        WPARAM vk = wParam;
        if (vk != VK_ESCAPE && vk != VK_SHIFT && vk != VK_CONTROL && vk != VK_MENU && vk != VK_LWIN && vk != VK_RWIN &&
            vk != VK_CAPITAL && vk != VK_F2 && vk != VK_TAB && static_cast<int>(vk) != g_toggleKey)
            InterlockedIncrement(&g_oskRealKeys);
    }
    if (g_imguiReady && g_menuOpen) {
        // 0.7: with [Menu] FreeMouse the mouse belongs to the menu - the game's window procedure never sees it (no
        // camera turn, no SetCursorPos to the centre, no ShowCursor(FALSE)); WM_SETCURSOR stays with ImGui (it draws
        // its own cursor and hides the system one)
        if (g_freeMouse && (IsMouseMessage(msg) || msg == WM_SETCURSOR)) {
            ImGui_ImplWin32_WndProcHandler(hwnd, msg, wParam, ScaleMouse(hwnd, msg, lParam));
            if (msg != WM_SETCURSOR) return 0;
            if (LOWORD(lParam) == HTCLIENT) { SetCursor(nullptr); return TRUE; }   // borders: as before (resize cursor)
        } else {
            ImGui_ImplWin32_WndProcHandler(hwnd, msg, wParam, lParam);
        }
        // 0.7.1 [Menu] BlockGameInput: no key message reaches the game's window procedure while the menu is open (it
        // only queues WM_CHAR and the Esc key-up, which opened the pause menu); a key that went down meanwhile keeps
        // its key-up away from the game after the close as well
        if (g_blockGameInput && IsKeyMessage(msg)) {
            if (msg == WM_KEYDOWN && wParam < 256) g_msgKeyHeld[wParam] = 1;
            if (msg == WM_KEYUP && wParam < 256) g_msgKeyHeld[wParam] = 0;
            return 0;
        }
        // 0.6: while ImGui takes text (command bar, filter fields) typed keys do not reach the game's window procedure.
        // Key-up messages still do, so a key the game saw going down before the focus moved is released there too.
        if (g_cmdWantText && (msg == WM_KEYDOWN || msg == WM_CHAR || msg == WM_DEADCHAR || msg == WM_SYSCHAR))
            return 0;
    } else if (g_blockGameInput && msg == WM_KEYUP && wParam < 256 && g_msgKeyHeld[wParam]) {
        g_msgKeyHeld[wParam] = 0;               // 0.7.1: went down while the menu was open - the game saw no key-down
        return 0;
    }
    return IsWindowUnicode(hwnd) ? CallWindowProcW(g_wndProcOriginal, hwnd, msg, wParam, lParam)
                                 : CallWindowProcA(g_wndProcOriginal, hwnd, msg, wParam, lParam);
}

bool InitImGui(IDirect3DDevice9 *device) {
    D3DDEVICE_CREATION_PARAMETERS params = {};
    HWND hwnd = nullptr;
    if (SUCCEEDED(device->GetCreationParameters(&params))) hwnd = params.hFocusWindow;
    if (!hwnd) {
        IDirect3DSwapChain9 *chain = nullptr;
        if (SUCCEEDED(device->GetSwapChain(0, &chain)) && chain) {
            D3DPRESENT_PARAMETERS pp = {};
            if (SUCCEEDED(chain->GetPresentParameters(&pp))) hwnd = pp.hDeviceWindow;
            chain->Release();
        }
    }
    if (!hwnd) {
        Log(0, "imgui: no window handle from the device - menu off");
        return false;
    }
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO &io = ImGui::GetIO();
    io.IniFilename = nullptr;                // nothing written next to the game
    io.LogFilename = nullptr;
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableGamepad | ImGuiConfigFlags_NavEnableKeyboard;
    io.FontGlobalScale = g_scale;
    ImGui::StyleColorsDark();
    ImGui::GetStyle().ScaleAllSizes(g_scale);
    if (!ImGui_ImplWin32_Init(hwnd) || !ImGui_ImplDX9_Init(device)) {
        Log(0, "imgui: backend init failed - menu off");
        return false;
    }
    g_hwnd = hwnd;
    g_imguiDevice = device;
    WNDPROC previous = reinterpret_cast<WNDPROC>(
        IsWindowUnicode(hwnd) ? GetWindowLongPtrW(hwnd, GWLP_WNDPROC) : GetWindowLongPtrA(hwnd, GWLP_WNDPROC));
    g_wndProcOriginal = previous;
    LONG_PTR set = IsWindowUnicode(hwnd)
                       ? SetWindowLongPtrW(hwnd, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(&WndProcHook))
                       : SetWindowLongPtrA(hwnd, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(&WndProcHook));
    if (!set) Log(1, "imgui: window procedure not replaced (%lu) - mouse / keyboard input off", GetLastError());
    Log(1, "imgui %s ready (window 0x%08lx, device 0x%08lx, scale %.2f)", IMGUI_VERSION, reinterpret_cast<DWORD>(hwnd),
        reinterpret_cast<DWORD>(device), g_scale);
    return true;
}

void FeedGamepad(ImGuiIO &io) {
    io.BackendFlags |= ImGuiBackendFlags_HasGamepad;
    PadState pad = {};
    bool have = false;
    EnterCriticalSection(&g_padLock);
    if (g_padConnected[g_lastPad]) { pad = g_pad[g_lastPad]; have = true; }
    LeaveCriticalSection(&g_padLock);
    if (!g_menuOpen || !have) memset(&pad, 0, sizeof(pad));
    // 0.7: [Cmd] FocusButton (L3) pressed and released alone = focus into the bar + on-screen keyboard. A press that
    // becomes part of the open / close combo (L3 + R3) is not one: any other combo button down while it is held cancels.
    {
        static bool armed = false, wasDown = false;
        WORD fb = g_cmdFocusButton;
        WORD others = static_cast<WORD>(g_toggleButtons & ~fb);
        bool down = fb && (pad.wButtons & fb) == fb;
        if (down && !wasDown) armed = !(pad.wButtons & others);
        if (down && (pad.wButtons & others)) armed = false;
        if (!down && wasDown && armed && g_menuOpen && g_cmdEnabled) InterlockedExchange(&g_cmdOskReq, 1);
        if (!down) armed = false;
        wasDown = down;
    }
    // 0.4 TO TEST: while a row has the focus, X and Y belong to the row (fail / skip). ImGui would otherwise toggle its
    // menu layer on X and activate the row on Y (= OK). Held until released, also if the focus moves meanwhile.
    static WORD rowOwned = 0, rowHeld = 0;
    WORD xy = pad.wButtons & 0xC000;
    if (g_testFocus) rowOwned |= static_cast<WORD>(xy & ~rowHeld);
    WORD pressed = static_cast<WORD>(xy & ~rowHeld & rowOwned);
    if (pressed & 0x4000) InterlockedExchange(&g_testX, 1);
    if (pressed & 0x8000) InterlockedExchange(&g_testY, 1);
    rowHeld = xy;
    rowOwned &= xy;                          // released buttons go back to ImGui
    pad.wButtons &= static_cast<WORD>(~rowOwned);
    // 0.6 command bar: while the bar has the focus, D-pad / left stick / A / B / X / Y / LB / RB / View belong to the
    // bar (edges in g_cmdPadEdges); a button stays the bar's until it is released, so the press that moves the focus
    // into the menu does not reach ImGui as well
    static WORD cmdOwned = 0, cmdHeld = 0;
    WORD dirs = 0;
    if (pad.sThumbLY > 16000) dirs |= 0x0001;
    if (pad.sThumbLY < -16000) dirs |= 0x0002;
    if (pad.sThumbLX < -16000) dirs |= 0x0004;
    if (pad.sThumbLX > 16000) dirs |= 0x0008;
    WORD cmdBits = static_cast<WORD>((pad.wButtons & 0xF33F) | dirs);   // A B X Y, LB RB, View, Start (0.7), D-pad
    WORD cmdNew = static_cast<WORD>(cmdBits & ~cmdHeld);
    g_cmdBackEdge = (cmdNew & 0x0020) != 0;
    if (g_cmdHandOver) {                     // 0.7 FirstPadPressOnlyFocuses=0: the held direction goes on to ImGui
        g_cmdHandOver = false;
        cmdOwned &= static_cast<WORD>(~0x000F);
    }
    if (g_cmdOwnPad || g_oskOpen) cmdOwned |= cmdNew;   // 0.7.1: the open on-screen keyboard owns the pad, focus or not
    g_cmdPadEdges = static_cast<WORD>(cmdNew & cmdOwned);
    g_cmdPadHeld = static_cast<WORD>(cmdBits & cmdOwned);
    cmdHeld = cmdBits;
    cmdOwned &= cmdBits;
    pad.wButtons &= static_cast<WORD>(~cmdOwned);
    if (cmdOwned & 0x000F) pad.sThumbLX = pad.sThumbLY = 0;
    struct { ImGuiKey key; WORD mask; } const buttons[] = {
        {ImGuiKey_GamepadStart, 0x0010}, {ImGuiKey_GamepadBack, 0x0020}, {ImGuiKey_GamepadFaceLeft, 0x4000},
        {ImGuiKey_GamepadFaceRight, 0x2000}, {ImGuiKey_GamepadFaceUp, 0x8000}, {ImGuiKey_GamepadFaceDown, 0x1000},
        {ImGuiKey_GamepadDpadLeft, 0x0004}, {ImGuiKey_GamepadDpadRight, 0x0008}, {ImGuiKey_GamepadDpadUp, 0x0001},
        {ImGuiKey_GamepadDpadDown, 0x0002}, {ImGuiKey_GamepadL1, 0x0100}, {ImGuiKey_GamepadR1, 0x0200},
        {ImGuiKey_GamepadL3, 0x0040}, {ImGuiKey_GamepadR3, 0x0080}};
    for (const auto &b : buttons) io.AddKeyEvent(b.key, (pad.wButtons & b.mask) != 0);
    auto analog = [&io](ImGuiKey key, float value, float lo, float hi) {
        float v = (value - lo) / (hi - lo);
        if (v < 0.0f) v = 0.0f;
        if (v > 1.0f) v = 1.0f;
        io.AddKeyAnalogEvent(key, v > 0.1f, v);
    };
    analog(ImGuiKey_GamepadL2, pad.bLeftTrigger, 30.0f, 255.0f);
    analog(ImGuiKey_GamepadR2, pad.bRightTrigger, 30.0f, 255.0f);
    const float dead = 7849.0f;
    analog(ImGuiKey_GamepadLStickLeft, pad.sThumbLX, -dead, -32768.0f);
    analog(ImGuiKey_GamepadLStickRight, pad.sThumbLX, dead, 32767.0f);
    analog(ImGuiKey_GamepadLStickUp, pad.sThumbLY, dead, 32767.0f);
    analog(ImGuiKey_GamepadLStickDown, pad.sThumbLY, -dead, -32768.0f);
    analog(ImGuiKey_GamepadRStickLeft, pad.sThumbRX, -dead, -32768.0f);
    analog(ImGuiKey_GamepadRStickRight, pad.sThumbRX, dead, 32767.0f);
    analog(ImGuiKey_GamepadRStickUp, pad.sThumbRY, dead, 32767.0f);
    analog(ImGuiKey_GamepadRStickDown, pad.sThumbRY, -dead, -32768.0f);
}

// fallback when PadHook is not in the chain: read the pad ourselves (toggle + navigation, no blocking)
void SelfPoll(XInputGetStateFn poll) {
    static DWORD frames = 0;
    PadState state = {};
    DWORD index = static_cast<DWORD>(g_lastPad);
    bool connected = poll(index, &state) == ERROR_SUCCESS;
    OnPad(index, connected, &state);
    // no pad at that index: look at the next one twice a second (a pad that sends buttons becomes g_lastPad)
    if (!connected && ++frames % 30 == 0) {
        DWORD next = (index + 1 + (frames / 30) % 3) % 4;
        PadState other = {};
        bool found = poll(next, &other) == ERROR_SUCCESS;
        OnPad(next, found, &other);
        if (found) g_lastPad = static_cast<int>(next);
    }
}

void KeyboardToggle() {
    if (!g_toggleKey) return;
    bool down = (GetAsyncKeyState(g_toggleKey) & 0x8000) != 0 && GetForegroundWindow() == g_hwnd;
    if (down && !g_keyHeld) ToggleMenu("key");
    g_keyHeld = down;
}

// ---- pages ----
void Text(const char *fmt, ...) {
    char line[512];
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf_s(line, sizeof(line), _TRUNCATE, fmt, ap);
    va_end(ap);
    ImGui::TextUnformatted(line);
}

void PluginLine(const char *name) {
    char file[64], exportName[64];
    _snprintf_s(file, sizeof(file), _TRUNCATE, "%s.asi", name);
    _snprintf_s(exportName, sizeof(exportName), _TRUNCATE, "%sVersion", name);
    HMODULE module = GetModuleHandleA(file);
    if (!module) { Text("%-16s not loaded", name); return; }
    typedef const char *(*VersionFn)();
    VersionFn version = reinterpret_cast<VersionFn>(GetProcAddress(module, exportName));
    if (version) {
        ImGui::TextWrapped("%-16s %s", name, version());
    } else {
        Text("%-16s loaded (no %s export)", name, exportName);
    }
}

void Status03Line();                    // 0.3 code checks line, defined with the 0.3 pages
void ValStatusUnit(char *o, size_t n);  // 0.2 helpers, defined with the items below
void ValCostume(char *o, size_t n);
void PlayerInfo(char *o, size_t n);
const char *GameState();
void QueueItem(const char *id, const char *arg);   // defined after kItems
bool QuitArmed(DWORD *leftMs);                     // 0.7.2 game.quit, defined after the command history

void PageStatus() {
    ImGui::TextWrapped("%s", kVersion);
    HMODULE exe = GetModuleHandleA(nullptr);
    const IMAGE_DOS_HEADER *dos = reinterpret_cast<const IMAGE_DOS_HEADER *>(exe);
    const IMAGE_NT_HEADERS *nt = reinterpret_cast<const IMAGE_NT_HEADERS *>(reinterpret_cast<const BYTE *>(exe) + dos->e_lfanew);
    Text("tru.exe: base 0x%08lx, PE time stamp 0x%08lx, size 0x%lx", reinterpret_cast<DWORD>(exe),
         nt->FileHeader.TimeDateStamp, nt->OptionalHeader.SizeOfImage);
    ImGui::TextWrapped("code checks: base %s, pad %s, d3d9 %s, player %s, post %s, camera %s, frame %s, level %s",
                       g_baseOk ? "ok" : "NO", g_padCodeOk ? "ok" : "NO", g_d3dCodeOk ? "ok" : "NO",
                       g_playerOk ? "ok" : "NO", g_postOk ? "ok" : "NO", g_cameraOk ? "ok" : "NO",
                       g_frameOk ? "ok" : "NO", g_levelOk ? "ok" : "NO");
    Text("in a level: %s; pad read in Present (front end): %s", InLevel() ? "yes" : "no", g_padModeIdle ? "yes" : "no");
    ImGui::TextWrapped("costume %s, unit table %s", g_costumeOk ? "ok" : "NO", g_unitOk ? "ok" : "NO");
    Status03Line();
    ImGui::Separator();
    char line[1024];
    ValStatusUnit(line, sizeof(line));
    ImGui::TextWrapped("unit: %s   [status.unit]", line);
    ImGui::TextWrapped("state: %s   [status.state]", GameState());
    ValCostume(line, sizeof(line));
    ImGui::TextWrapped("costume: %s   [status.costume]", line);
    PlayerInfo(line, sizeof(line));
    ImGui::TextWrapped("player: %s   [status.player]", line);
    ImGui::Separator();
    ImGui::TextUnformatted("Our plugins   [status.plugins]");
    PluginLine("TruShadowPower");
    PluginLine("TruDoppelganger");
    PluginLine("TruDlc2Player");
    PluginLine("TruRockVein");
    PluginLine("TruLink");
    Text("%-16s %s", "ModLoader", GetModuleHandleA("ModLoader.asi") ? "loaded" : "not loaded");
    ImGui::Separator();
    char owner[MAX_PATH], inner[MAX_PATH];
    DWORD pointer = 0;
    ReadDword(kPadPointer, &pointer);
    ModuleOf(reinterpret_cast<const void *>(pointer), owner, sizeof(owner));
    ModuleOf(reinterpret_cast<const void *>(g_padOriginal), inner, sizeof(inner));
    Text("pad: %s", g_padMode);
    Text("  game calls 0x%08lx (%s), PadHook calls 0x%08lx (%s)", pointer, owner,
         reinterpret_cast<DWORD>(g_padOriginal), inner);
    Text("  last pad %d, input to the game while open: %s", g_lastPad, g_blockInput ? "blocked" : "passed");
    ImGui::TextWrapped("mouse (0.7): %s", g_mouseMode);
    ImGui::TextWrapped("keyboard (0.7.1): %s; %ld events held, %ld releases sent, %ld kept after close", g_kbdMode,
                       g_kbdHeldEvents, g_kbdReleases, g_kbdSwallowed);
    HMODULE d3d9 = GetModuleHandleA("d3d9.dll");
    char d3dPath[MAX_PATH] = "not loaded";
    if (d3d9) GetModuleFileNameA(d3d9, d3dPath, MAX_PATH);
    Text("d3d9: %s", g_d3dMode);
    ImGui::TextWrapped("  d3d9.dll = %s", d3dPath);
    Text("  device 0x%08lx, window 0x%08lx", reinterpret_cast<DWORD>(g_device), reinterpret_cast<DWORD>(g_hwnd));
    // 0.7.2 game.quit: owner only, two presses within 5 s (the item itself keeps the safety step)
    ImGui::Separator();
    DWORD left = 0;
    bool armed = QuitArmed(&left);
    char label[128];
    if (armed)
        _snprintf_s(label, sizeof(label), _TRUNCATE, "CONFIRM: quit the game now (%lu s)  [game.quit]##quit",
                    (left + 999) / 1000);
    else
        _snprintf_s(label, sizeof(label), _TRUNCATE, "Quit game (press twice)  [game.quit]##quit");
    if (armed) ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.7f, 0.2f, 0.1f, 1.0f));
    if (ImGui::Button(label)) QueueItem("game.quit", "");
    if (armed) ImGui::PopStyleColor();
    ImGui::TextWrapped("game.quit ends tru.exe at once (TerminateProcess, exit code 0x544D = 21581) - also while the game "
                       "hangs; TruMenu.log, the TO TEST list and the history are written first. Never automatic.");
}

bool ReadLara(float *position, float *rotation, DWORD *instance) {
    DWORD player = 0;
    if (!g_playerOk || !ReadDword(kPlayerPtr, &player) || !player) return false;
    *instance = player;
    return ReadFloats(player + kInstancePosition, position, 3) && ReadFloats(player + kInstanceRotation, rotation, 3);
}

// ---- items: every menu entry has a stable id, callable from the menu and through TruMenuInvoke (TruLink "menu") ----
bool InLevel() {
    DWORD player = 0;
    return g_playerOk && ReadDword(kPlayerPtr, &player) && player != 0;
}

void Out(char *out, size_t size, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf_s(out, size, _TRUNCATE, fmt, ap);
    va_end(ap);
}

// arg: "" toggles, "0" / "1" set; returns the new state
bool BoolArg(const char *arg, bool current) {
    if (!arg || !arg[0]) return !current;
    return atoi(arg) != 0 || _stricmp(arg, "on") == 0 || _stricmp(arg, "true") == 0;
}

void CurrentUnit(char *out, size_t size) {
    out[0] = 0;
    __try {
        const volatile char *name = reinterpret_cast<const volatile char *>(kUnitName);
        size_t i = 0;
        for (; i + 1 < size && i < 63 && name[i]; ++i) out[i] = name[i];
        out[i] = 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        out[0] = 0;
    }
}

// ---- 0.2: units, game data, costumes (read-only helpers, any thread) ----
// playable units of the PC unit list tr8/pc-w/unitlist.txt (the list the game loads; = installed mods list),
// grouped by tools/menu_unit_table.py: base game by unit prefix l1_ .. l7_ (l7_* units sit in levels\l5), DLC 1 =
// dlc\dlc_level1, DLC 2 = dlc\dlc_level2, DLC 3-6 start units. Containers / cine / costume units are not offered.
struct UnitRow { const char *group, *unit, *path; };
const UnitRow kUnits[] = {
    {"Base game l1", "l1_baldrs_hall", "levels\\l1\\l1_baldrs_hall"},
    {"Base game l1", "l1_baldrs_sideroom", "levels\\l1\\l1_baldrs_sideroom"},
    {"Base game l1", "l1_baldrs_tomb", "levels\\l1\\l1_baldrs_tomb"},
    {"Base game l1", "l1_baldrsstairs_a", "levels\\l1\\l1_baldrsstairs_a"},
    {"Base game l1", "l1_baldrsstairs_b", "levels\\l1\\l1_baldrsstairs_b"},
    {"Base game l1", "l1_cine_ship_sinking", "levels\\l1\\l1_cine_ship_sinking"},
    {"Base game l1", "l1_cineseatop", "levels\\l1\\l1_cineseatop"},
    {"Base game l1", "l1_kraken_entrance", "levels\\l1\\l1_kraken_entrance"},
    {"Base game l1", "l1_kraken_room", "levels\\l1\\l1_kraken_room"},
    {"Base game l1", "l1_krakenstairs_a", "levels\\l1\\l1_krakenstairs_a"},
    {"Base game l1", "l1_krakenstairs_b", "levels\\l1\\l1_krakenstairs_b"},
    {"Base game l1", "l1_norse_hallway_a", "levels\\l1\\l1_norse_hallway_a"},
    {"Base game l1", "l1_rutlands_ship_m1", "levels\\l1\\l1_rutlands_ship_m1"},
    {"Base game l1", "l1_seafloor", "levels\\l1\\l1_seafloor"},
    {"Base game l1", "l1_seatop", "levels\\l1\\l1_seatop"},
    {"Base game l1", "l1_ship_engine_hall", "levels\\l1\\l1_ship\\l1_ship_engine_hall"},
    {"Base game l1", "l1_ship_exterior", "levels\\l1\\l1_ship\\l1_ship_exterior"},
    {"Base game l1", "l1_ship_lower_hallway", "levels\\l1\\l1_ship\\l1_ship_lower_hallway"},
    {"Base game l1", "l1_ship_natla_room", "levels\\l1\\l1_ship\\l1_ship_natla_room"},
    {"Base game l1", "l1_ship_sinking_hall", "levels\\l1\\l1_ship\\l1_ship_sinking_hall"},
    {"Base game l1", "l1_ship_upper_hallway", "levels\\l1\\l1_ship\\l1_ship_upper_hallway"},
    {"Base game l1", "l1_ship_upper_hallway_a", "levels\\l1\\l1_ship\\l1_ship_upper_hallway_a"},
    {"Base game l1", "l1_ship_upper_hallway_b", "levels\\l1\\l1_ship\\l1_ship_upper_hallway_b"},
    {"Base game l2", "l2_cliffclimb", "levels\\l2\\l2_cliffclimb"},
    {"Base game l2", "l2_cliffhall", "levels\\l2\\l2_cliffhall"},
    {"Base game l2", "l2_cliffhall_b", "levels\\l2\\l2_cliffhall_b"},
    {"Base game l2", "l2_flushtunnel", "levels\\l2\\l2_flushtunnel"},
    {"Base game l2", "l2_hubhall", "levels\\l2\\l2_hubhall"},
    {"Base game l2", "l2_junglehub", "levels\\l2\\l2_junglehub"},
    {"Base game l2", "l2_mapconnector", "levels\\l2\\l2_mapconnector"},
    {"Base game l2", "l2_maproom", "levels\\l2\\l2_maproom"},
    {"Base game l2", "l2_norsehall", "levels\\l2\\l2_norsehall"},
    {"Base game l2", "l2_norsehub", "levels\\l2\\l2_norsehub"},
    {"Base game l2", "l2_puzzleconnector", "levels\\l2\\l2_puzzleconnector"},
    {"Base game l2", "l2_puzzleroom", "levels\\l2\\l2_puzzleroom"},
    {"Base game l2", "l2_shrineroom", "levels\\l2\\l2_shrineroom"},
    {"Base game l2", "l2_towerconnector", "levels\\l2\\l2_towerconnector"},
    {"Base game l2", "l2_towerroom", "levels\\l2\\l2_towerroom"},
    {"Base game l2", "l2_upperhallway", "levels\\l2\\l2_upperhallway"},
    {"Base game l3", "l3_bedroom_hall", "levels\\l3\\l3_bedroom_hall"},
    {"Base game l3", "l3_caverns_start", "levels\\l3\\l3_caverns_start"},
    {"Base game l3", "l3_chamberrockhall", "levels\\l3\\l3_chamberrockhall"},
    {"Base game l3", "l3_chapel", "levels\\l3\\l3_chapel"},
    {"Base game l3", "l3_main_bedroom", "levels\\l3\\l3_main_bedroom"},
    {"Base game l3", "l3_main_hall", "levels\\l3\\l3_main_hall"},
    {"Base game l3", "l3_mansion_exterior_afterburn", "levels\\l3\\l3_mansion_exterior_afterburn"},
    {"Base game l3", "l3_secretchamber", "levels\\l3\\l3_secretchamber"},
    {"Base game l3", "l3_stairhall", "levels\\l3\\l3_stairhall"},
    {"Base game l4", "l4_ballcourt", "levels\\l4\\l4_ballcourt"},
    {"Base game l4", "l4_pool", "levels\\l4\\l4_pool"},
    {"Base game l4", "l4_ragnarok_room", "levels\\l4\\l4_ragnarok_room"},
    {"Base game l4", "l4_staircase_mictlan", "levels\\l4\\l4_staircase_mictlan"},
    {"Base game l4", "l4_staircase_upper", "levels\\l4\\l4_staircase_upper"},
    {"Base game l4", "l4_staircase_xibalba", "levels\\l4\\l4_staircase_xibalba"},
    {"Base game l4", "l4_temple", "levels\\l4\\l4_temple"},
    {"Base game l4", "l4_templepath", "levels\\l4\\l4_templepath"},
    {"Base game l4", "l4_trailstart", "levels\\l4\\l4_trailstart"},
    {"Base game l4", "l4_trailtube", "levels\\l4\\l4_trailtube"},
    {"Base game l4", "l4_traprooms", "levels\\l4\\l4_traprooms"},
    {"Base game l5", "l5_startsnow", "levels\\l5\\l5_startsnow"},
    {"Base game l5", "l5_valaskjalf", "levels\\l5\\l5_valaskjalf"},
    {"Base game l5", "l5_valaskjalf_entry", "levels\\l5\\l5_valaskjalf_entry"},
    {"Base game l5", "l5_valaskjalf_entryb", "levels\\l5\\l5_valaskjalf_entryb"},
    {"Base game l5", "l5_valgrind", "levels\\l5\\l5_valgrind"},
    {"Base game l5", "l5_valgrind_tunnel", "levels\\l5\\l5_valgrind_tunnel"},
    {"Base game l6", "l6_ship_engine_hall", "levels\\l6\\l6_ship_engine_hall"},
    {"Base game l6", "l6_ship_exterior", "levels\\l6\\l6_ship_exterior"},
    {"Base game l6", "l6_ship_natla_room", "levels\\l6\\l6_ship_natla_room"},
    {"Base game l6", "l6_ship_upper_hallway", "levels\\l6\\l6_ship_upper_hallway"},
    {"Base game l6", "l6_ship_upper_hallway_a", "levels\\l6\\l6_ship_upper_hallway_a"},
    {"Base game l6", "l6_ship_upper_hallway_b", "levels\\l6\\l6_ship_upper_hallway_b"},
    {"Base game l7", "l7_arctic_sea", "levels\\l5\\l7_arctic_sea"},
    {"Base game l7", "l7_helheim01", "levels\\l5\\l7_helheim01"},
    {"Base game l7", "l7_helheim02", "levels\\l5\\l7_helheim02"},
    {"Base game l7", "l7_helheim03", "levels\\l5\\l7_helheim03"},
    {"Base game l7", "l7_helheim_hall01", "levels\\l5\\l7_helheim_hall01"},
    {"Base game l7", "l7_helheim_hall02", "levels\\l5\\l7_helheim_hall02"},
    {"Base game l7", "l7_himalaya_end", "levels\\l5\\l7_himalaya_end"},
    {"Base game l7", "l7_monastery", "levels\\l5\\l7_monastery"},
    {"Base game l7", "l7_thin_ice", "levels\\l5\\l7_thin_ice"},
    {"Base game l7", "l7_yggdrasil", "levels\\l5\\l7_yggdrasil"},
    {"Base game l7", "l7_yggdrasil_end", "levels\\l5\\l7_yggdrasil_end"},
    {"Base game l7", "l7_yggdrasil_hall01", "levels\\l5\\l7_yggdrasil_hall01"},
    {"Base game l7", "l7_yggdrasil_hall02", "levels\\l5\\l7_yggdrasil_hall02"},
    {"DLC 1", "dlc_caverns", "dlc\\dlc_level1\\dlc_caverns"},
    {"DLC 1", "dlc_caverns_hall", "dlc\\dlc_level1\\dlc_caverns_hall"},
    {"DLC 1", "dlc_dungeon", "dlc\\dlc_level1\\dlc_dungeon"},
    {"DLC 1", "dlc_dungeonhalla", "dlc\\dlc_level1\\dlc_dungeonhalla"},
    {"DLC 1", "dlc_dungeonhallb", "dlc\\dlc_level1\\dlc_dungeonhallb"},
    {"DLC 1", "dlc_level1_left", "dlc\\dlc_level1\\dlc_level1_left"},
    {"DLC 1", "dlc_level1_right", "dlc\\dlc_level1\\dlc_level1_right"},
    {"DLC 1", "dlc_level1_start", "dlc\\dlc_level1\\dlc_level1_start"},
    {"DLC 1", "dlc_pillory", "dlc\\dlc_level1\\dlc_pillory"},
    {"DLC 1", "dlc_treasureroom", "dlc\\dlc_level1\\dlc_treasureroom"},
    {"DLC 1", "dlc_water_wheel", "dlc\\dlc_level1\\dlc_water_wheel"},
    {"DLC 1", "dlc_watertunnel", "dlc\\dlc_level1\\dlc_watertunnel"},
    {"DLC 2", "dlc2_ceremony_room", "dlc\\dlc_level2\\dlc2_ceremony_room"},
    {"DLC 2", "dlc2_goo_room", "dlc\\dlc_level2\\dlc2_goo_room"},
    {"DLC 2", "dlc2_hall_ceremony_goo", "dlc\\dlc_level2\\dlc2_hall_ceremony_goo"},
    {"DLC 2", "dlc2_hall_goo_machine", "dlc\\dlc_level2\\dlc2_hall_goo_machine"},
    {"DLC 2", "dlc2_hall_machine_ceremony", "dlc\\dlc_level2\\dlc2_hall_machine_ceremony"},
    {"DLC 2", "dlc2_machine_room", "dlc\\dlc_level2\\dlc2_machine_room"},
    {"DLC 2", "dlc2_treasure_room_cine", "dlc\\dlc_level2\\dlc2_treasure_room_cine"},
    {"DLC 2", "dlc_level2_start", "dlc\\dlc_level2\\dlc_level2_start"},
    {"DLC 2", "dlc_yggdrasil_end", "dlc\\dlc_level2\\dlc_yggdrasil_end"},
    {"DLC 2", "dlc_yggdrasil_hall01", "dlc\\dlc_level2\\dlc_yggdrasil_hall01"},
    {"DLC 2", "dlc_yggdrasil_hall02", "dlc\\dlc_level2\\dlc_yggdrasil_hall02"},
    {"DLC other starts", "dlc_level3_start", "dlc\\dlc_level3\\dlc_level3_start"},
    {"DLC other starts", "dlc_level4_start", "dlc\\dlc_level4\\dlc_level4_start"},
    {"DLC other starts", "dlc_level5_start", "dlc\\dlc_level5\\dlc_level5_start"},
    {"DLC other starts", "dlc_level6_start", "dlc\\dlc_level6\\dlc_level6_start"},
};
const int kUnitCount = sizeof(kUnits) / sizeof(kUnits[0]);

bool ReadWord(DWORD address, WORD *out) {
    __try {
        *out = *reinterpret_cast<const volatile WORD *>(address);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool ReadString(DWORD address, char *out, size_t size) {
    out[0] = 0;
    if (!address) return false;
    __try {
        size_t i = 0;
        const volatile char *p = reinterpret_cast<const volatile char *>(address);
        for (; i + 1 < size && i < 127 && p[i]; ++i) out[i] = p[i];
        out[i] = 0;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        out[0] = 0;
        return false;
    }
}

// object id -> name as the game does ([0xdb94d0] + id * 8)
bool ObjectName(int id, char *out, size_t size) {
    out[0] = 0;
    DWORD table = 0, count = 0, name = 0;
    if (id <= 0 || !ReadDword(kObjNames, &table) || !table || !ReadDword(table, &count) || id > static_cast<int>(count))
        return false;
    return ReadDword(table + static_cast<DWORD>(id) * 8, &name) && ReadString(name, out, size) && out[0];
}

// name -> object id as tru+0x1bf770 does (case-insensitive, 0 = not in the object list)
int ObjectId(const char *name) {
    DWORD table = 0, count = 0;
    if (!name || !name[0] || !ReadDword(kObjNames, &table) || !table || !ReadDword(table, &count) || count > 4096) return 0;
    for (DWORD id = 1; id <= count; ++id) {
        DWORD p = 0;
        char other[128];
        if (ReadDword(table + id * 8, &p) && ReadString(p, other, sizeof(other)) && _stricmp(other, name) == 0)
            return static_cast<int>(id);
    }
    return 0;
}

// the player type table the game uses now (the operand of tru+0x1bf121; TruDlc2Player points it at its copy)
DWORD TypeTable() {
    DWORD table = 0;
    if (!ReadDword(kTypeLookup + 2, &table)) return 0;
    return table;
}

// record <index>: name, player record (f2 = the player's)? false past the end
bool TypeRecord(int index, char *name, size_t size, bool *player) {
    DWORD table = TypeTable(), namePtr = 0, f2 = 0;
    if (!table || index < 0 || index > 63) return false;
    DWORD rec = table + static_cast<DWORD>(index) * 0x1c;
    if (!ReadDword(rec, &namePtr) || !namePtr || !ReadString(namePtr, name, size)) return false;
    ReadDword(rec + 8, &f2);
    *player = f2 == kPlayerF2;
    return true;
}

// type of an object name as tru+0x1bf0e0: the first record with that name, -1 if none
int TypeIndexOf(const char *name) {
    char rec[64];
    bool player = false;
    for (int i = 0; TypeRecord(i, rec, sizeof(rec), &player); ++i)
        if (_stricmp(rec, name) == 0) return i;
    return -1;
}

DWORD GameData() {
    DWORD gd = 0;
    ReadDword(kGameDataPtr, &gd);
    return gd;
}

struct CostumeState {
    DWORD gameData;
    WORD mode, chosen0, chosen1, chosen2;  // +0x1f4, +0x20c, +0x20e, +0x210
    DWORD current;                          // [0xe7f1c8]
    int unitDefault;                        // unit data +0x70 -> +0x294, -1 = unknown
    DWORD unitId;
};

int UnitDefaultCostume(DWORD *unitId) {
    *unitId = 0;
    if (!g_unitOk || !ReadDword(kUnitId, unitId)) return -1;
    for (DWORD e = kStreamUnits; e < kStreamUnitsEnd; e += kStreamUnitSize) {
        DWORD id = 0, state = 0, data = 0, level = 0;
        if (!ReadDword(e, &id) || !ReadDword(e + 4, &state)) return -1;
        if ((state & 0xff) != 2 || id != *unitId) continue;
        WORD costume = 0;
        if (ReadDword(e + 8, &data) && data && ReadDword(data + 0x70, &level) && level &&
            ReadWord(level + 0x294, &costume))
            return costume;
        return -1;
    }
    return -1;
}

void ReadCostumeState(CostumeState *s) {
    memset(s, 0, sizeof(*s));
    s->gameData = GameData();
    if (s->gameData) {
        ReadWord(s->gameData + kGdMode, &s->mode);
        ReadWord(s->gameData + kGdChosen0, &s->chosen0);
        ReadWord(s->gameData + kGdChosen1, &s->chosen1);
        ReadWord(s->gameData + kGdChosen2, &s->chosen2);
    }
    ReadDword(kCostumeNow, &s->current);
    s->unitDefault = UnitDefaultCostume(&s->unitId);
}

// "<id> <name>" or "0 (none)"
void IdName(int id, char *out, size_t size) {
    char name[128];
    if (id <= 0) { Out(out, size, "%d (none)", id); return; }
    if (ObjectName(id, name, sizeof(name))) Out(out, size, "%d %s", id, name);
    else Out(out, size, "%d (?)", id);
}

int PendingMainState();   // 0.7.2: 2 / 9 while a level start is set up / the outfit selection is open, else 0

const char *GameState() {
    DWORD busy = 0;
    ReadDword(kGameTracker + 0xb8, &busy);
    if ((busy >> 8) & 0xff) return "level change pending (GameTracker+0xb9)";
    int pending = PendingMainState();
    if (pending == 9) return "outfit / weapon selection of a level start (main state 9) - level.load / level.start refused";
    if (pending == 2) return "level start being set up (main state 2) - level.load / level.start refused";
    if (InLevel()) return "in a level (player instance present)";
    return "no player instance (front end / loading)";
}

// player object: the costume id [0xe7f1c8], its entry in the object table 0xdb7400 (object +0x14 id, +0x34 type)
void PlayerInfo(char *o, size_t n) {
    DWORD player = 0, current = 0;
    ReadDword(kPlayerPtr, &player);
    ReadDword(kCostumeNow, &current);
    char idName[160];
    IdName(static_cast<int>(current), idName, sizeof(idName));
    char name[128] = "";
    ObjectName(static_cast<int>(current), name, sizeof(name));
    int type = name[0] ? TypeIndexOf(name) : -1;
    DWORD object = 0, objType = 0xffffffff, state = 0;
    for (int i = 0; i < kObjectEntries && current; ++i) {
        DWORD e = kObjectTable + static_cast<DWORD>(i) * 0x24, obj = 0, idState = 0;
        if (!ReadDword(e + 8, &obj) || !ReadDword(e + 0xc, &idState)) break;
        if (obj && static_cast<DWORD>(static_cast<SHORT>(idState & 0xffff)) == current) {
            object = obj;
            state = idState >> 16;
            ReadDword(obj + 0x34, &objType);
            break;
        }
    }
    Out(o, n, "instance 0x%08lx; object %s (type record %d by name, object 0x%08lx state %lu, object+0x34 type %ld)",
        player, idName, type, object, state, static_cast<LONG>(objType));
}

void PluginsInfo(char *o, size_t n) {
    const char *const names[] = {"TruShadowPower", "TruDoppelganger", "TruDlc2Player", "TruRockVein", "TruGuard",
                                "TruLink"};
    size_t used = 0;
    o[0] = 0;
    for (const char *name : names) {
        char file[64], exportName[64];
        _snprintf_s(file, sizeof(file), _TRUNCATE, "%s.asi", name);
        _snprintf_s(exportName, sizeof(exportName), _TRUNCATE, "%sVersion", name);
        HMODULE module = GetModuleHandleA(file);
        typedef const char *(*VersionFn)();
        VersionFn version = module ? reinterpret_cast<VersionFn>(GetProcAddress(module, exportName)) : nullptr;
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s=%s", used ? "; " : "", name,
                            !module ? "no" : version ? version() : "loaded");
        if (w < 0) return;
        used += static_cast<size_t>(w);
    }
    _snprintf_s(o + used, n - used, _TRUNCATE, "; ModLoader=%s", GetModuleHandleA("ModLoader.asi") ? "loaded" : "no");
}

void CostumeInfo(char *o, size_t n) {
    CostumeState s;
    ReadCostumeState(&s);
    char cur[160], c0[160], c2[160], def[160];
    IdName(static_cast<int>(s.current), cur, sizeof(cur));
    IdName(s.chosen0, c0, sizeof(c0));
    IdName(s.chosen2, c2, sizeof(c2));
    IdName(s.unitDefault, def, sizeof(def));
    Out(o, n, "current [0x%08lx] %s; game data [0x%08lx] = 0x%08lx: +0x1f4 %u (level load reads +0x%x), chosen +0x20c %s, "
        "+0x20e %u, +0x210 %s; unit %lu default %s", kCostumeNow, cur, kGameDataPtr, s.gameData, s.mode,
        s.mode ? kGdChosen2 : kGdChosen0, c0, s.chosen1, c2, s.unitId, def);
}

// 0.7.1: the stream unit Lara is in. GameTracker+0x38 (kUnitName) is only the unit the level load started with. The
// game loop (0x5dfc88) compares GameTracker+0xc0 with the player instance's +0xe0 and on a difference calls
// STREAM_MoveIntoNewStreamUnit 0x5c1bf0, which stores the player's unit id into GameTracker+0xc0 (0x5c1c4e) and prints
// the name at entry+0xc of the stream unit table found by 0x5c1b50 (0x5c1c33, "STREAM_MoveIntoNewStreamUnit(%s)");
// the name lookup 0x5c1b90 compares entry+0xc as well. So: id = [0xe7f148], entry = state byte 2 + same id, name = +0xc.
bool g_streamNameOk = false;

bool StreamUnitName(DWORD id, char *out, size_t size) {
    out[0] = 0;
    if (!g_streamNameOk) return false;
    for (DWORD e = kStreamUnits; e < kStreamUnitsEnd; e += kStreamUnitSize) {
        DWORD eid = 0, state = 0;
        if (!ReadDword(e, &eid) || !ReadDword(e + 4, &state)) return false;
        if ((state & 0xff) != 2 || eid != id) continue;
        if (!ReadString(e + 0xc, out, size)) return false;
        for (const char *p = out; *p; ++p)
            if (static_cast<unsigned char>(*p) < 32 || static_cast<unsigned char>(*p) > 126) { out[0] = 0; return false; }
        return out[0] != 0;
    }
    return false;
}

// 0.7.1 [Log] UnitChanges: worker thread, every 250 ms; a line only when the name changes
void UnitTick() {
    static char last[64] = "";
    static DWORD lastId = 0xffffffff;
    if (!g_unitChanges || !g_streamNameOk) return;
    DWORD id = 0;
    if (!ReadDword(kUnitId, &id) || id == lastId) return;
    char name[64];
    if (!StreamUnitName(id, name, sizeof(name))) return;   // not loaded yet: try again next time
    lastId = id;
    if (!strcmp(name, last)) return;
    Log(1, "unit: %s (was %s; stream unit id %lu)", name, last[0] ? last : "-", id);
    strncpy_s(last, sizeof(last), name, _TRUNCATE);
}

// value getters (any thread, read-only)
void ValStatusUnit(char *o, size_t n) {
    char unit[64], stream[64];
    CurrentUnit(unit, sizeof(unit));
    DWORD id = 0;
    ReadDword(kUnitId, &id);
    StreamUnitName(id, stream, sizeof(stream));
    Out(o, n, "%s (stream unit id %lu = Lara's unit %s)", unit[0] ? unit : "-", id, stream[0] ? stream : "?");
}
void ValState(char *o, size_t n) { Out(o, n, "%s", GameState()); }
void ValCostume(char *o, size_t n) {
    if (!g_costumeOk) { Out(o, n, "costume code check failed"); return; }
    CostumeInfo(o, n);
}
void ValCostumeCurrent(char *o, size_t n) {
    DWORD current = 0;
    ReadDword(kCostumeNow, &current);
    IdName(static_cast<int>(current), o, n);
}
void ValPlayerObject(char *o, size_t n) { PlayerInfo(o, n); }
void ValPlugins(char *o, size_t n) { PluginsInfo(o, n); }
// TruGuard (optional plugin): its exports are only read, the plugin decides what it logs
typedef int (*GuardIntFn)();
typedef int (*GuardTextFn)(char *, int);
GuardIntFn GuardIntExport(const char *name) {
    HMODULE module = GetModuleHandleA("TruGuard.asi");
    return module ? reinterpret_cast<GuardIntFn>(GetProcAddress(module, name)) : nullptr;
}
GuardTextFn GuardTextExport(const char *name) {
    HMODULE module = GetModuleHandleA("TruGuard.asi");
    return module ? reinterpret_cast<GuardTextFn>(GetProcAddress(module, name)) : nullptr;
}
void ValGuardStatus(char *o, size_t n) {
    GuardTextFn fn = GuardTextExport("TruGuardStatus");
    if (!fn) { Out(o, n, "TruGuard not loaded"); return; }
    char text[1024];
    fn(text, sizeof(text));
    Out(o, n, "%s", text);
}
void ValGuardCount(char *o, size_t n) {
    GuardIntFn count = GuardIntExport("TruGuardCount"), distinct = GuardIntExport("TruGuardDistinct");
    if (!count || !distinct) { Out(o, n, "TruGuard not loaded"); return; }
    Out(o, n, "%d exception(s) in tru.exe at %d distinct site(s)", count(), distinct());
}
void ValGuardLast(char *o, size_t n) {
    GuardTextFn fn = GuardTextExport("TruGuardLast");
    if (!fn) { Out(o, n, "TruGuard not loaded"); return; }
    char text[512];
    fn(text, sizeof(text));
    Out(o, n, "%s", text);
}
typedef int (*GuardSetModeFn)(int);
GuardSetModeFn GuardSetModeExport() {
    HMODULE module = GetModuleHandleA("TruGuard.asi");
    return module ? reinterpret_cast<GuardSetModeFn>(GetProcAddress(module, "TruGuardSetMode")) : nullptr;
}
void ValGuardMode(char *o, size_t n) {
    GuardIntFn mode = GuardIntExport("TruGuardMode");
    if (!mode) { Out(o, n, "TruGuard not loaded"); return; }
    Out(o, n, "%d", mode());
}
bool RunGuardMode(const char *arg, char *o, size_t n) {
    GuardSetModeFn set = GuardSetModeExport();
    GuardIntFn mode = GuardIntExport("TruGuardMode");
    if (!set || !mode) { Out(o, n, "TruGuard not loaded"); return false; }
    if (!arg || !arg[0]) { Out(o, n, "guard.mode %d", mode()); return true; }
    char *end = nullptr;
    long v = strtol(arg, &end, 0);
    if (*end || v < 0 || v > 2) { Out(o, n, "usage: guard.mode <0|1|2>"); return false; }
    Out(o, n, "guard.mode %d", set(static_cast<int>(v)));
    return true;
}
void ValGuardOverlay(char *o, size_t n) { Out(o, n, "%d", g_guardOverlay ? 1 : 0); }
bool RunGuardOverlay(const char *arg, char *o, size_t n) {
    bool on = BoolArg(arg, g_guardOverlay != 0);
    InterlockedExchange(&g_guardOverlay, on ? 1 : 0);
    Out(o, n, "guard.overlay %d", on ? 1 : 0);
    return true;
}

typedef int (*GuardDumpFn)(const char *);
GuardDumpFn GuardDumpExport() {
    HMODULE module = GetModuleHandleA("TruGuard.asi");
    return module ? reinterpret_cast<GuardDumpFn>(GetProcAddress(module, "TruGuardDump")) : nullptr;
}
bool RunGuardDump(const char *arg, char *o, size_t n) {
    GuardDumpFn dump = GuardDumpExport();
    if (!dump) { Out(o, n, "TruGuard not loaded"); return false; }
    const char *reason = (arg && arg[0]) ? arg : "menu";
    int ok = dump(reason);
    Out(o, n, ok ? "guard.dump written (see TruGuard.log / TruGuardDumps)" : "guard.dump failed");
    return ok != 0;
}
// "index name id; ..." for every player record of the type table
void ValCostumeList(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    char name[64];
    bool player = false;
    for (int i = 0; TypeRecord(i, name, sizeof(name), &player); ++i) {
        if (!player) continue;
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%d %s %d", used ? "; " : "", i, name, ObjectId(name));
        if (w < 0) return;
        used += static_cast<size_t>(w);
    }
    if (!used) Out(o, n, "no type table");
}
// "group: unit unit ...; group: ..." for every offered unit
void ValLevelList(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    const char *group = nullptr;
    for (const UnitRow &u : kUnits) {
        bool head = !group || strcmp(group, u.group) != 0;
        group = u.group;
        int w = head ? _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s: %s", used ? "; " : "", u.group, u.unit)
                     : _snprintf_s(o + used, n - used, _TRUNCATE, " %s", u.unit);
        if (w < 0) return;
        used += static_cast<size_t>(w);
    }
}

void ValMenu(char *o, size_t n) { Out(o, n, "%d", g_menuOpen ? 1 : 0); }
void ValOverlay(char *o, size_t n) { Out(o, n, "%d", g_overlay ? 1 : 0); }
void ValVersion(char *o, size_t n) { Out(o, n, "%s", kVersion); }
void ValHooks(char *o, size_t n) {
    Out(o, n, "pad=%s; d3d9=%s; frontend-pad=%d; mouse=%s; keyboard=%s; pause=%s; autostart=%s", g_padMode, g_d3dMode,
        g_padModeIdle ? 1 : 0, g_mouseMode, g_kbdMode, g_pauseMode, g_autoStartMode);
}
void ValPlayer(char *o, size_t n) {
    float p[3], r[3];
    DWORD instance = 0;
    if (ReadLara(p, r, &instance)) Out(o, n, "%.2f %.2f %.2f rot %.4f %.4f %.4f", p[0], p[1], p[2], r[0], r[1], r[2]);
    else Out(o, n, "-");
}
void ValCamera(char *o, size_t n) {
    DWORD camera = 0;
    ReadDword(kCurrentCamera, &camera);
    Out(o, n, "0x%08lx", camera);
}
void ValCheat(char *o, size_t n) {
    DWORD v = 0;
    ReadDword(kCheatMode, &v);
    Out(o, n, "%lu", v & 0xff);
}
void ValSpeed(char *o, size_t n) { Out(o, n, "%.1f", g_flightSpeed); }
void ValUnit(char *o, size_t n) { CurrentUnit(o, n); if (!o[0]) Out(o, n, "-"); }
void ValLevels(char *o, size_t n) { Out(o, n, "%s", g_levelList); }
void ValTodo(char *o, size_t n) { Out(o, n, "todo"); }

// runners: return true on success, text in out
bool RunMenu(const char *arg, char *o, size_t n) {
    bool open = BoolArg(arg, g_menuOpen != 0);
    if (open != (g_menuOpen != 0)) ToggleMenu("item");
    Out(o, n, "menu.open %d", open ? 1 : 0);
    return true;
}
bool RunOverlay(const char *arg, char *o, size_t n) {
    if (!g_playerOk) { Out(o, n, "player pointer check failed"); return false; }
    bool on = BoolArg(arg, g_overlay != 0);
    InterlockedExchange(&g_overlay, on ? 1 : 0);
    Out(o, n, "overlay.position %d", on ? 1 : 0);
    return true;
}
bool RunCameraMode(const char *arg, char *o, size_t n) {
    if (!g_cameraOk || !g_experimental) { Out(o, n, "camera code not verified / experimental off"); return false; }
    if (!InLevel()) { Out(o, n, "needs a level"); return false; }
    char *end = nullptr;
    long mode = strtol(arg ? arg : "", &end, 0);
    if (!arg || !arg[0] || *end || mode < 0 || mode > 15) { Out(o, n, "usage: camera.mode <0..15>"); return false; }
    reinterpret_cast<CameraSetModeFn>(kCameraSetMode)(static_cast<int>(mode));
    DWORD camera = 0;
    ReadDword(kCurrentCamera, &camera);
    Out(o, n, "CAMERA_SetMode(%ld) done, current camera 0x%08lx", mode, camera);
    return true;
}
bool RunCameraRestore(const char *, char *o, size_t n) {
    if (!g_cameraOk || !g_experimental) { Out(o, n, "camera code not verified / experimental off"); return false; }
    if (!InLevel()) { Out(o, n, "needs a level"); return false; }
    reinterpret_cast<CameraRestoreFn>(kCameraRestore)(reinterpret_cast<void *>(kCameraManager), 0);
    Out(o, n, "camera restored");
    return true;
}
bool RunCheat(const char *arg, char *o, size_t n) {
    if (!g_postOk || !g_playerOk || !g_experimental) { Out(o, n, "INSTANCE_Post / player not verified / experimental off"); return false; }
    DWORD player = 0;
    if (!ReadDword(kPlayerPtr, &player) || !player) { Out(o, n, "needs a level"); return false; }
    volatile BYTE *cheat = reinterpret_cast<volatile BYTE *>(kCheatMode);
    BYTE value = BoolArg(arg, *cheat != 0) ? 1 : 0;
    *cheat = value;
    // TRLAU Skew.cpp (TR8): message 12 to the player with the new cheatMode value
    reinterpret_cast<InstancePostFn>(kInstancePost)(reinterpret_cast<void *>(player), 12, value);
    g_flight = value != 0;
    Out(o, n, "cheat.flight %u (cheatMode 0x%08lx, message 12 to 0x%08lx)", value, kCheatMode, player);
    return true;
}
bool RunSpeed(const char *arg, char *o, size_t n) {
    float v = arg && arg[0] ? static_cast<float>(atof(arg)) : 0.0f;
    if (!(v > 0.0f && v < 1000.0f)) { Out(o, n, "usage: cheat.speed <0..1000>"); return false; }
    g_flightSpeed = v;
    Out(o, n, "cheat.speed %.1f", v);
    return true;
}
bool LevelChangePending(char *why, size_t n);   // 0.7.2, in the level.start section
bool LoadUnit(const char *unit, char *o, size_t n) {
    if (!g_levelOk || !g_experimental) { Out(o, n, "level change code not verified / experimental off"); return false; }
    size_t len = unit ? strlen(unit) : 0;
    if (!len || len > 63) { Out(o, n, "usage: level.load <unit name, 1..63 chars>"); return false; }
    for (size_t i = 0; i < len; ++i)
        if (!(isalnum(static_cast<unsigned char>(unit[i])) || unit[i] == '_' || unit[i] == '-')) {
            Out(o, n, "unit name may hold a-z 0-9 _ - only");
            return false;
        }
    // 0.7.2: also refused during a mission start (main state 2 / 9 - live 2026-11-02 20:29:17: a level.load during the
    // outfit selection set GameTracker+0xb9, the state-9 screen never served it, the game hung)
    char why[200];
    if (LevelChangePending(why, sizeof(why))) { Out(o, n, "refused: level change pending (%s)", why); return false; }
    static char name[64];                    // the game copies it to GameTracker+0x38; keep ours alive anyway
    strncpy_s(name, sizeof(name), unit, _TRUNCATE);
    // GAMELOOP_RequestLevelChangeByName(name, gameTracker, doneType 4) - TRLAU name / signature, doneType 4 as the
    // game's own caller tru+0x1dfb6b
    reinterpret_cast<LevelChangeFn>(kLevelChange)(name, reinterpret_cast<void *>(kGameTracker), 4);
    Out(o, n, "level change to '%s' requested", name);
    if (g_menuOpen) ToggleMenu("level change");
    return true;
}
bool RunLevel(const char *arg, char *o, size_t n) { return LoadUnit(arg, o, n); }
bool RunReload(const char *, char *o, size_t n) {
    char unit[64];
    CurrentUnit(unit, sizeof(unit));
    if (!unit[0]) { Out(o, n, "no current unit name"); return false; }
    return LoadUnit(unit, o, n);
}
// costume.set <index|name> [20c|210]: the chosen costume (object id) into the game-data word the level load reads
// (+0x20c while +0x1f4 is 0, else +0x210 - tru+0x1de2d6), checked first with the game's own validator tru+0x1c54e0
// (the level load's check: id in the object list and <name>.drm present). The game writes +0x20c the same way in its
// state save tru+0x155cb1 (word = costume object id). Takes effect at the next level load.
bool SetCostume(const char *arg, char *o, size_t n) {
    if (!g_costumeOk || !g_experimental) { Out(o, n, "costume code not verified / experimental off"); return false; }
    char first[64] = "", second[16] = "";
    if (!arg || sscanf_s(arg, "%63s %15s", first, static_cast<unsigned>(sizeof(first)), second,
                         static_cast<unsigned>(sizeof(second))) < 1) {
        Out(o, n, "usage: costume.set <type record index | costume name> [20c|210]");
        return false;
    }
    char name[64] = "";
    bool player = false;
    char *end = nullptr;
    long index = strtol(first, &end, 10);
    if (end && !*end) {
        if (!TypeRecord(static_cast<int>(index), name, sizeof(name), &player)) { Out(o, n, "no type record %ld", index); return false; }
    } else {
        index = TypeIndexOf(first);
        if (index < 0 || !TypeRecord(static_cast<int>(index), name, sizeof(name), &player)) {
            Out(o, n, "'%s' is not in the player type table", first);
            return false;
        }
    }
    if (!player) { Out(o, n, "type record %ld '%s' is not a player record", index, name); return false; }
    int id = ObjectId(name);
    if (!id) { Out(o, n, "'%s' is not in the object list", name); return false; }
    if (!reinterpret_cast<CostumeValidFn>(kCostumeValid)(id)) {
        Out(o, n, "'%s' (id %d) refused by the game's check 0x%08lx (no %s.drm?) - the level load would ignore it", name,
            id, kCostumeValid, name);
        return false;
    }
    DWORD gd = GameData();
    WORD mode = 0;
    if (!gd || !ReadWord(gd + kGdMode, &mode)) { Out(o, n, "no game data at [0x%08lx]", kGameDataPtr); return false; }
    DWORD slot = mode ? kGdChosen2 : kGdChosen0;
    if (_stricmp(second, "20c") == 0) slot = kGdChosen0;
    else if (_stricmp(second, "210") == 0) slot = kGdChosen2;
    else if (second[0]) { Out(o, n, "slot must be 20c or 210"); return false; }
    __try {
        *reinterpret_cast<volatile WORD *>(gd + slot) = static_cast<WORD>(id);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Out(o, n, "write to 0x%08lx failed", gd + slot);
        return false;
    }
    Out(o, n, "costume %ld %s (object %d) written to game data 0x%08lx +0x%lx (+0x1f4 = %u); used at the next level load",
        index, name, id, gd, slot, mode);
    return true;
}
bool RunCostumeSet(const char *arg, char *o, size_t n) { return SetCostume(arg, o, n); }
bool RunCostumeSetReload(const char *arg, char *o, size_t n) {
    if (!SetCostume(arg, o, n)) return false;
    char first[400];
    strncpy_s(first, sizeof(first), o, _TRUNCATE);
    char unit[64];
    CurrentUnit(unit, sizeof(unit));
    if (!unit[0]) { Out(o, n, "%s; no current unit to reload", first); return false; }
    char text[300];
    bool ok = LoadUnit(unit, text, sizeof(text));
    Out(o, n, "%s; %s", first, text);
    return ok;
}
// costume.reset: what the new-game reset does (TU 0x821fe9a8, PC tru+0x156abe): +0x210 / +0x20e / +0x20c = 0, so the
// next level load takes the unit's default costume. Only these three words - the reset itself does far more.
bool RunCostumeReset(const char *, char *o, size_t n) {
    if (!g_costumeOk || !g_experimental) { Out(o, n, "costume code not verified / experimental off"); return false; }
    DWORD gd = GameData();
    if (!gd) { Out(o, n, "no game data at [0x%08lx]", kGameDataPtr); return false; }
    __try {
        *reinterpret_cast<volatile WORD *>(gd + kGdChosen2) = 0;
        *reinterpret_cast<volatile WORD *>(gd + kGdChosen1) = 0;
        *reinterpret_cast<volatile WORD *>(gd + kGdChosen0) = 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Out(o, n, "write to game data 0x%08lx failed", gd);
        return false;
    }
    Out(o, n, "game data 0x%08lx +0x210 / +0x20e / +0x20c = 0 (unit default at the next level load)", gd);
    return true;
}
bool RunTodo(const char *, char *o, size_t n) { Out(o, n, "todo - not implemented"); return false; }

// ======================================================================================================================
// 0.3: original developer debug menu, quick wins, log page, videos
// ======================================================================================================================

volatile LONG g_exceptionLines = 0;          // log lines (tails / script) that mention an exception
volatile LONG g_ownExceptions = 0;           // exceptions TruMenu caught in its own game calls (dev rows, script natives)

bool WriteBytes(DWORD address, const void *data, size_t size) {
    DWORD old = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(address), size, PAGE_EXECUTE_READWRITE, &old)) return false;
    bool ok = true;
    __try {
        memcpy(reinterpret_cast<void *>(address), data, size);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = false;
    }
    DWORD unused = 0;
    VirtualProtect(reinterpret_cast<void *>(address), size, old, &unused);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(address), size);
    return ok;
}

bool ReadByte(DWORD address, BYTE *out) {
    __try {
        *out = *reinterpret_cast<const volatile BYTE *>(address);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// ---- developer menu: Crystal's tables in .data 0x8aaa6c .. 0x8ab3f0 (tools/devmenu_dump.py; README "Developer
// menu"). Row 0x18 bytes: +0 type, +4 min / action argument, +8 max, +0xc label, +0x10 target, +0x14 mask / bool
// value / int callback. The retail exe has no driver for them any more (the root 0x8aaae8 is referenced from the
// tables only); TruMenu reads the rows at load and draws / runs them as the row types say.
const DWORD kDevFrom = 0x008aaa6c, kDevTo = 0x008ab3f0, kDevRoot = 0x008aaae8, kDevRowSize = 0x18;
const DWORD kDevRootTitle = 0x00855070;     // "This should not be the Options Title"
enum DevType { kDevFlag = 0x00, kDevBool = 0x02, kDevInt = 0x03, kDevAction = 0x09, kDevLink = 0x0a, kDevTitle = 0x0b,
               kDevEnd = 0x10, kDevHeader = 0x11 };
struct DevRow {
    DWORD addr, page;                        // row address, page (first row) it belongs to
    DWORD type, p1, p2, label, target, p5;   // the six dwords
    char text[48];                           // label string
    char id[56];                             // "dev.<slug>" for value / action rows, "" else
};
const int kDevMax = 128;
DevRow g_dev[kDevMax];
int g_devCount = 0;
DWORD g_devPages[48];
int g_devPageCount = 0;
bool g_devOk = false;
DWORD g_devPage = kDevRoot;                  // page shown in the menu
char g_devStatus[160] = "not read";

// facts per row from the static pass (tools/devmenu_dump.py, 2026-10-31): who reads the target in retail code
struct DevNote { DWORD row; const char *note; };
const DevNote kDevNotes[] = {
    {0x008aab00, "live: streamFlags 0x200000 is read by Reload Current Unit 0x5dfba0 and ~20 other sites"},
    {0x008aab30, "0x5d37b0 = jmp 0x6457a0 (empty function): compiled out"},
    {0x008aaab8, "0x5dfba0: if byte [0xe7f141] == 0 { if streamFlags & 0x200000: 0x5570f0(0); 0x5df760(4) }; "
                 "byte [0xe7f143] = 0 - reloads the unit"},
    {0x008aab78, "0x6457a0 is an empty function (ret): compiled out"},
    {0x008aab90, "0x555d40: streamFlags |= 0x200000 only"},
    {0x008aabd8, "readers with this mask: 0x5cf331, 0x5cf434, 0x5cf57b (what they draw in retail: unknown)"},
    {0x008aabf0, "no reader of 0xe7edb4 in retail code: effect unknown / dead"},
    {0x008aac38, "callback 0x5d36a0: writes the current unit's fog (unit +0x94 / +0x98 / +0xa0..0xa3) and calls "
                 "0x5bfe10 / 0x5bfe40"},
    {0x008aac50, "callback 0x5d36a0 (see Fog Far)"},
    {0x008aac68, "callback 0x5d36a0 (see Fog Far)"},
    {0x008aac80, "callback 0x5d36a0 (see Fog Far)"},
    {0x008aac98, "callback 0x5d36a0 (see Fog Far)"},
    {0x008aacb0, "0x5d3760: the unit's fog defaults (0xe7b8a0 / 0xe7ecdc) back into the five ints, then 0x5d36a0(0)"},
    {0x008aacf8, "written once at init (0x5df56d = 1), no reader found: effect unknown"},
    {0x008aad10, "no reader of 0xa02b80 in retail code: effect unknown / dead"},
    {0x008aad28, "live: read at 0x5da2e9, written at 0x5d3cfb / 0x5da316"},
    {0x008aad40, "live: init 0x1000 at 0x5d3d44, read at 0x5da380 (fild)"},
    {0x008aad58, "byte in .rdata, no reader: dead"},
    {0x008aad70, "debugFlags is tested with a register mask (0x5dfd7b ...): not resolved, effect unknown"},
    {0x008aad88, "debugFlags is tested with a register mask (0x5dfd7b ...): not resolved, effect unknown"},
    {0x008aada0, "no reader with this mask found: effect unknown"},
    {0x008aadb8, "debugFlags is tested with a register mask (0x5dfd7b ...): not resolved, effect unknown"},
    {0x008aadd0, "0x5d3510: dword [0xe7f0b4] |= 0x100 (GameTracker+0x2c) - a progress bit, TruMenu cannot undo it"},
    {0x008aae18, "0x5d7590: calls [0x8ab79c](float [0x8416b4])"},
    {0x008aae30, "no reader with this mask found: effect unknown"},
    {0x008aae48, "byte in .rdata, no reader: dead"},
    {0x008aaf38, "byte in .rdata, no reader: dead"},
};

const char *DevNoteOf(DWORD row) {
    for (const DevNote &n : kDevNotes)
        if (n.row == row) return n.note;
    return nullptr;
}

const char *DevTypeName(DWORD type) {
    switch (type) {
    case kDevFlag: return "flag";
    case kDevBool: return "bool";
    case kDevInt: return "int";
    case kDevAction: return "action";
    case kDevLink: return "page";
    case kDevTitle: return "title";
    case kDevEnd: return "end";
    case kDevHeader: return "header";
    default: return nullptr;
    }
}

void Slug(const char *in, char *out, size_t size) {
    size_t n = 0;
    bool sep = false;
    for (const char *p = in; *p && n + 1 < size; ++p) {
        unsigned char c = static_cast<unsigned char>(*p);
        if (isalnum(c)) {
            if (sep && n) out[n++] = '_';
            if (n + 1 < size) out[n++] = static_cast<char>(tolower(c));
            sep = false;
        } else {
            sep = true;
        }
    }
    out[n] = 0;
}

// a function that is only "ret" (or a jmp to one): compiled out in retail
bool IsEmptyFunction(DWORD fn) {
    BYTE b = 0;
    if (!ReadByte(fn, &b)) return false;
    if (b == 0xc3) return true;
    DWORD rel = 0;
    if (b == 0xe9 && ReadDword(fn + 1, &rel)) {
        BYTE t = 0;
        return ReadByte(fn + 5 + rel, &t) && t == 0xc3;
    }
    return false;
}

// read the tables the way tools/devmenu_dump.py walks them: pages end with a type 0x10 row, a 0x11 header page keeps
// its 0x10 rows as empty slots, a lone dword between pages (0x8aaa9c = the root pointer) is skipped
void DevRead() {
    g_devCount = g_devPageCount = 0;
    DWORD title[6] = {};
    for (int i = 0; i < 6; ++i) ReadDword(kDevRoot + 4 * i, &title[i]);
    char text[64];
    ReadString(kDevRootTitle, text, sizeof(text));
    if (title[0] != kDevTitle || title[3] != kDevRootTitle || strcmp(text, "This should not be the Options Title") != 0) {
        Out(g_devStatus, sizeof(g_devStatus), "root row 0x%08lx does not match (type %lu, label 0x%08lx)", kDevRoot,
            title[0], title[3]);
        return;
    }
    DWORD a = kDevFrom, page = kDevFrom;
    bool header = false;
    while (a + kDevRowSize <= kDevTo && g_devCount < kDevMax) {
        DWORD r[6] = {};
        for (int i = 0; i < 6; ++i) ReadDword(a + 4 * i, &r[i]);
        if (header && page != a && r[0] != kDevEnd) { header = false; page = a; }
        if (a == page) {
            if (!DevTypeName(r[0])) { a += 4; page = a; continue; }
            header = r[0] == kDevHeader;
            if (g_devPageCount < 48) g_devPages[g_devPageCount++] = page;
        }
        if (!DevTypeName(r[0])) {
            Out(g_devStatus, sizeof(g_devStatus), "unknown row type 0x%lx at 0x%08lx - stopped", r[0], a);
            return;
        }
        DevRow &d = g_dev[g_devCount++];
        d.addr = a;
        d.page = page;
        d.type = r[0]; d.p1 = r[1]; d.p2 = r[2]; d.label = r[3]; d.target = r[4]; d.p5 = r[5];
        d.text[0] = d.id[0] = 0;
        if (d.label) ReadString(d.label, d.text, sizeof(d.text));
        if ((d.type == kDevFlag || d.type == kDevBool || d.type == kDevInt || d.type == kDevAction) && d.text[0]) {
            char slug[48];
            Slug(d.text, slug, sizeof(slug));
            Out(d.id, sizeof(d.id), "dev.%s", slug);
            for (int k = 0; k + 1 < g_devCount; ++k)          // keep ids unique (none collide in retail)
                if (strcmp(g_dev[k].id, d.id) == 0) { Out(d.id, sizeof(d.id), "dev.%s_%08lx", slug, a); break; }
        }
        if (d.type == kDevEnd && !header) page = a + kDevRowSize;
        a += kDevRowSize;
    }
    g_devOk = g_devCount > 90;
    Out(g_devStatus, sizeof(g_devStatus), "%d rows in %d pages read from 0x%08lx .. 0x%08lx%s", g_devCount, g_devPageCount,
        kDevFrom, kDevTo, g_devOk ? "" : " (fewer than expected - off)");
}

const DevRow *DevFind(const char *id) {
    if (!g_devOk || !id) return nullptr;
    for (int i = 0; i < g_devCount; ++i)
        if (g_dev[i].id[0] && _stricmp(g_dev[i].id, id) == 0) return &g_dev[i];
    return nullptr;
}

// page name: its title row, else the label of the first link to it, else "page 0x.. (not linked)"
void DevPageName(DWORD page, char *out, size_t size) {
    for (int i = 0; i < g_devCount; ++i)
        if (g_dev[i].addr == page && g_dev[i].type == kDevTitle && g_dev[i].text[0]) {
            Out(out, size, "%s", page == kDevRoot ? "Main Menu (root)" : g_dev[i].text);
            return;
        }
    for (int i = 0; i < g_devCount; ++i)
        if (g_dev[i].type == kDevLink && g_dev[i].target == page && g_dev[i].page != page) {
            Out(out, size, "%s", g_dev[i].text);
            return;
        }
    Out(out, size, "page 0x%08lx (not linked)", page);
}

void DevValue(const DevRow &d, char *o, size_t n) {
    DWORD v = 0;
    BYTE b = 0;
    switch (d.type) {
    case kDevFlag:
        if (ReadDword(d.target, &v)) Out(o, n, "%d", (v & d.p5) ? 1 : 0); else Out(o, n, "?");
        break;
    case kDevBool:
        if (ReadByte(d.target, &b)) Out(o, n, "%d", b ? 1 : 0); else Out(o, n, "?");
        break;
    case kDevInt:
        if (ReadDword(d.target, &v)) Out(o, n, "%ld", static_cast<LONG>(v)); else Out(o, n, "?");
        break;
    case kDevAction:
        Out(o, n, "%s", IsEmptyFunction(d.target) ? "empty" : "-");
        break;
    default:
        Out(o, n, "-");
    }
}

typedef void(__cdecl *DevFn)(DWORD);

// game thread: change / run one row
bool DevRun(const DevRow &d, const char *arg, char *o, size_t n) {
    if (!g_experimental) { Out(o, n, "experimental off"); return false; }
    __try {
        if (d.type == kDevFlag) {
            volatile DWORD *p = reinterpret_cast<volatile DWORD *>(d.target);
            bool on = BoolArg(arg, (*p & d.p5) != 0);
            if (on) *p |= d.p5; else *p &= ~d.p5;
            Out(o, n, "%s %d ([0x%08lx] = 0x%08lx, mask 0x%lx)", d.id, on ? 1 : 0, d.target, *p, d.p5);
            return true;
        }
        if (d.type == kDevBool) {
            BYTE cur = 0;
            ReadByte(d.target, &cur);
            bool on = BoolArg(arg, cur != 0);
            BYTE value = on ? static_cast<BYTE>(d.p5 & 0xff) : 0;
            if (on && !value) value = 1;
            if (!WriteBytes(d.target, &value, 1)) { Out(o, n, "write to 0x%08lx failed", d.target); return false; }
            Out(o, n, "%s %d (byte [0x%08lx] = 0x%02x)", d.id, on ? 1 : 0, d.target, value);
            return true;
        }
        if (d.type == kDevInt) {
            char *end = nullptr;
            long v = strtol(arg ? arg : "", &end, 0);
            if (!arg || !arg[0] || *end) { Out(o, n, "usage: %s <%ld..%ld>", d.id, static_cast<LONG>(d.p1), static_cast<LONG>(d.p2)); return false; }
            LONG lo = static_cast<LONG>(d.p1), hi = static_cast<LONG>(d.p2);
            if (v < lo) v = lo;
            if (v > hi) v = hi;
            if (d.p5 && !IsEmptyFunction(d.p5) && !InLevel()) { Out(o, n, "needs a level (callback 0x%08lx)", d.p5); return false; }
            *reinterpret_cast<volatile LONG *>(d.target) = v;
            // callback as the game's own caller 0x5d3760 calls it: cdecl, one argument 0
            if (d.p5) reinterpret_cast<DevFn>(d.p5)(0);
            Out(o, n, "%s %ld ([0x%08lx]%s)", d.id, v, d.target, d.p5 ? ", callback called" : "");
            return true;
        }
        if (d.type == kDevAction) {
            bool empty = IsEmptyFunction(d.target);
            if (!empty && !InLevel()) { Out(o, n, "needs a level"); return false; }
            reinterpret_cast<DevFn>(d.target)(d.p1);   // cdecl; +4 is the argument (only the Chapter rows have one)
            Out(o, n, "%s: 0x%08lx(0x%lx) called%s", d.id, d.target, d.p1, empty ? " - empty function in retail" : "");
            return true;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
        Out(o, n, "%s: exception 0x%08lx", d.id, GetExceptionCode());
        Log(0, "dev menu: %s", o);           // reaches the log page through the TruMenu.log tail
        return false;
    }
    Out(o, n, "row type %lu has no value", d.type);
    return false;
}

void ValDevList(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    if (!g_devOk) { Out(o, n, "%s", g_devStatus); return; }
    for (int i = 0; i < g_devCount; ++i) {
        const DevRow &d = g_dev[i];
        if (!d.id[0]) continue;
        char value[32], page[64];
        DevValue(d, value, sizeof(value));
        DevPageName(d.page, page, sizeof(page));
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s %s=%s (%s; row 0x%08lx)", used ? "; " : "", d.id,
                            DevTypeName(d.type), value, page, d.addr);
        if (w < 0) return;
        used += static_cast<size_t>(w);
    }
}

// ---- quick wins (catalog section 14; every address checked at load, Start) ----
const DWORD kTimeDilation = 0x00e7f1d0;     // GameTracker+0x148 float (TRLAU MainMenu.cpp); init 0x5d3d25, read 0x5da3a0
const DWORD kStreamFlags = 0x00e7f0b8;      // GameTracker+0x30; pause = bit 0x1000 (TRLAU, key F3)
const DWORD kPlayerControl = 0x008ab4e6;    // byte, 1 = player control on (TRLAU Input.cpp); 0x5d5f45 / 0x5d5f60
const DWORD kUiHidden = 0x00cdc9a0;         // bool (TRLAU Frontend.cpp); read at 0x5a434c
const DWORD kCameraFov = 0xb0;              // [0xe80534] + 0xb0 float (TRLAU Camera.h)
const DWORD kFirstInstance = 0x00d98d54;    // first instance, +0x08 next (TRLAU Instances.cpp); written at 0x5b2ec6
const DWORD kRemoveInstance = 0x005bc4e0;   // INSTANCE_ReallyRemoveInstance(inst, 0, 0) cdecl (TRLAU)
const char *const kRemoveInstanceBytes = "53 56 8b74240c 33db 395e60 57 0f8496000000";
const DWORD kCostumeSwitch = 0x006f0a90;    // reached from 0x778ca0 (native 0x79db50): alt id or the next of the list
const char *const kCostumeSwitchBytes = "a194f0e700 8b4810 8b5114 83ec0c 53 56 57 6aff 52";
const DWORD kCostumeSwitchAlt = 0x00778ca0; // thiscall: [0xe7f1cc] = id of entry [ecx], then jmp 0x6f0a90
const char *const kCostumeSwitchAltBytes = "8b01 50 e898dce5ff 0fb74808 83c404 890dccf1e700 e9d67df7ff";
const DWORD kAltPlayerObject = 0x00e7f1cc;  // GameTracker+0x144 altPlayerObjectID
const DWORD kGlobalInfo = 0x00e7ee50;       // [..]+4 -> {u16 count; u16 *ids at +4} (read at 0x6f0ac7)
const DWORD kMainState = 0x00e7ed60;        // TRLAU: 10 = main menu; read at 0x5d56e0
const DWORD kMoviePlay = 0x004a12b0;        // cdecl (name, bool loop) (catalog 11.1)
const char *const kMoviePlayBytes = "8b4c2404 8a442408 83ec20 53 55 33db 51 881db839a000";
const DWORD kMenuLoopPtr = 0x008abf20;      // char* "medsea_loop" 0x8552a8, read at 0x5daf35 for the menu background
const DWORD kMenuLoopOrig = 0x008552a8;
typedef void(__cdecl *VoidFn)();
typedef void(__cdecl *RemoveFn)(void *instance, int, int);
typedef void(__cdecl *MoviePlayFn)(const char *name, bool loop);

bool g_timeOk = false, g_pauseOk = false, g_controlOk = false, g_uiOk = false, g_instOk = false, g_removeOk = false,
     g_switchOk = false, g_movieOk = false, g_menuLoopOk = false, g_mainStateOk = false;
float g_mark[3];
bool g_markSet = false;
volatile LONG g_weaponsPending = 0;          // frames until INSTANCE_Post(player, 35, 0) after a costume switch
char g_menuLoopName[64];
char g_exeDir[MAX_PATH], g_asiDir[MAX_PATH];

void Post(DWORD instance, int message, int data) {
    reinterpret_cast<InstancePostFn>(kInstancePost)(reinterpret_cast<void *>(instance), message, data);
}

bool ParseFloats(const char *arg, float *v, int count) {
    if (!arg) return false;
    const char *p = arg;
    for (int i = 0; i < count; ++i) {
        char *end = nullptr;
        v[i] = static_cast<float>(strtod(p, &end));
        if (end == p) return false;
        p = end;
    }
    while (*p == ' ') ++p;
    return *p == 0;
}

void ValTimeScale(char *o, size_t n) {
    float f = 0.0f;
    if (g_timeOk && ReadFloats(kTimeDilation, &f, 1)) Out(o, n, "%.3f", f); else Out(o, n, "?");
}
bool RunTimeScale(const char *arg, char *o, size_t n) {
    if (!g_timeOk || !g_experimental) { Out(o, n, "time code not verified / experimental off"); return false; }
    float f = arg && arg[0] ? static_cast<float>(atof(arg)) : 1.0f;
    if (!(f >= 0.0f && f <= 10.0f)) { Out(o, n, "usage: time.scale <0..10> (\"\" = 1)"); return false; }
    *reinterpret_cast<volatile float *>(kTimeDilation) = f;
    Out(o, n, "time.scale %.3f (timeDilation 0x%08lx)", f, kTimeDilation);
    return true;
}
void ValPause(char *o, size_t n) {
    DWORD v = 0;
    ReadDword(kStreamFlags, &v);
    Out(o, n, "%d", (v & 0x1000) ? 1 : 0);
}
bool RunPause(const char *arg, char *o, size_t n) {
    if (!g_pauseOk || !g_experimental) { Out(o, n, "streamFlags not verified / experimental off"); return false; }
    volatile DWORD *f = reinterpret_cast<volatile DWORD *>(kStreamFlags);
    bool on = BoolArg(arg, (*f & 0x1000) != 0);
    if (on) *f |= 0x1000; else *f &= ~0x1000u;
    InterlockedExchange(&g_menuPaused, 0);      // 0.7.1: set by hand - the menu close does not undo it
    Out(o, n, "time.pause %d (streamFlags 0x%08lx)", on ? 1 : 0, *f);
    return true;
}

// 0.7.1 [Menu] PauseGame: the time.pause bit while the menu is open (render thread = the game's Present call). Only
// what TruMenu set is undone on close: a pause from before the menu stays, and time.pause used while the menu is open
// takes over (g_menuPaused = 0).
void PauseTick() {
    static bool applied = false;
    bool want = g_pauseGame && g_pauseOk && g_menuOpen;
    if (want == applied) return;
    applied = want;
    volatile LONG *f = reinterpret_cast<volatile LONG *>(kStreamFlags);
    if (want) {
        LONG before = InterlockedOr(f, 0x1000);
        InterlockedExchange(&g_menuPaused, (before & 0x1000) ? 0 : 1);
        g_pauseMode = (before & 0x1000) ? "menu open - the game was paused already (left as it is on close)"
                                        : "menu open - game paused by TruMenu (streamFlags bit 0x1000)";
        Log(2, "pause: %s", g_pauseMode);
        return;
    }
    LONG ours = InterlockedExchange(&g_menuPaused, 0);
    if (ours) InterlockedAnd(f, ~0x1000L);
    g_pauseMode = ours ? "menu closed - pause bit cleared again (waits for the next menu open)"
                       : "menu closed - pause bit left as it was (paused before the menu, or time.pause used)";
    Log(2, "pause: %s", g_pauseMode);
}
void ValControl(char *o, size_t n) {
    BYTE b = 0;
    if (ReadByte(kPlayerControl, &b)) Out(o, n, "%u", b); else Out(o, n, "?");
}
bool RunControl(const char *arg, char *o, size_t n) {
    if (!g_controlOk || !g_experimental) { Out(o, n, "player control byte not verified / experimental off"); return false; }
    volatile BYTE *b = reinterpret_cast<volatile BYTE *>(kPlayerControl);
    bool on = BoolArg(arg, *b != 0);
    *b = on ? 1 : 0;
    Out(o, n, "player.control %d (byte 0x%08lx)", on ? 1 : 0, kPlayerControl);
    return true;
}
bool RunDie(const char *, char *o, size_t n) {
    if (!g_postOk || !g_experimental) { Out(o, n, "INSTANCE_Post not verified / experimental off"); return false; }
    DWORD player = 0;
    if (!ReadDword(kPlayerPtr, &player) || !player) { Out(o, n, "needs a level"); return false; }
    Post(player, 4, 3);                      // TRLAU MainMenu.cpp (F11): message 4, data 3 = ragdoll death
    Out(o, n, "INSTANCE_Post(player 0x%08lx, 4, 3)", player);
    return true;
}
void ValUiHide(char *o, size_t n) {
    BYTE b = 0;
    if (ReadByte(kUiHidden, &b)) Out(o, n, "%d", b ? 1 : 0); else Out(o, n, "?");
}
bool RunUiHide(const char *arg, char *o, size_t n) {
    if (!g_uiOk || !g_experimental) { Out(o, n, "UI byte not verified / experimental off"); return false; }
    volatile BYTE *b = reinterpret_cast<volatile BYTE *>(kUiHidden);
    bool on = BoolArg(arg, *b != 0);
    *b = on ? 1 : 0;
    Out(o, n, "ui.hide %d", on ? 1 : 0);
    return true;
}
bool FovAddress(DWORD *address, float *value) {
    DWORD camera = 0;
    if (!ReadDword(kCurrentCamera, &camera) || !camera) return false;
    *address = camera + kCameraFov;
    return ReadFloats(*address, value, 1);
}
void ValFov(char *o, size_t n) {
    DWORD a = 0;
    float f = 0.0f;
    if (FovAddress(&a, &f)) Out(o, n, "%.4f", f); else Out(o, n, "-");
}
bool RunFov(const char *arg, char *o, size_t n) {
    if (!g_experimental || !InLevel()) { Out(o, n, "needs a level / experimental off"); return false; }
    DWORD a = 0;
    float cur = 0.0f;
    if (!FovAddress(&a, &cur)) { Out(o, n, "no current camera [0x%08lx]", kCurrentCamera); return false; }
    // sanity check of the catalog's offset: the field must already hold an angle in radians
    if (!(cur > 0.05f && cur < 3.1f)) { Out(o, n, "camera+0xb0 = %f does not look like a fov - not written", cur); return false; }
    float f = arg && arg[0] ? static_cast<float>(atof(arg)) : 0.7854f;
    if (!(f > 0.05f && f < 3.1f)) { Out(o, n, "usage: camera.fov <0.05..3.1 radians> (\"\" = pi/4)"); return false; }
    *reinterpret_cast<volatile float *>(a) = f;
    Out(o, n, "camera.fov %.4f (was %.4f, 0x%08lx)", f, cur, a);
    return true;
}

// ---- instances: [0xd98d54] first, +0x08 next; +0x10 object (+0x14 object id), +0x20 position, +0x30 rotation,
// +0x58 intro unique id, +0x14 iflags, +0x23c no-draw groups (catalog section 1, TRLAU Instance.h)
struct InstInfo { DWORD addr; LONG intro; int objectId; char name[64]; float pos[3]; };

bool ReadInstance(DWORD inst, InstInfo *info) {
    memset(info, 0, sizeof(*info));
    info->addr = inst;
    DWORD object = 0, oid = 0, intro = 0;
    if (!ReadDword(inst + 0x10, &object) || !ReadDword(inst + 0x58, &intro)) return false;
    info->intro = static_cast<LONG>(intro);
    if (object && ReadDword(object + 0x14, &oid)) info->objectId = static_cast<int>(oid & 0xffff);
    if (!ObjectName(info->objectId, info->name, sizeof(info->name))) Out(info->name, sizeof(info->name), "?");
    return ReadFloats(inst + kInstancePosition, info->pos, 3);
}

// walks the list; calls fn for each instance until it returns false; max 4096
template <typename F> int ForInstances(F fn) {
    DWORD inst = 0;
    if (!g_instOk || !ReadDword(kFirstInstance, &inst)) return 0;
    int count = 0;
    while (inst && count < 4096) {
        InstInfo info;
        if (!ReadInstance(inst, &info)) break;
        ++count;
        if (!fn(info)) break;
        if (!ReadDword(inst + 8, &inst)) break;
    }
    return count;
}

void ValInstCount(char *o, size_t n) {
    int count = ForInstances([](const InstInfo &) { return true; });
    Out(o, n, "%d instances", count);
}

// "<intro id>" (decimal), "0x<address>" or "#<index>" -> instance address (0 = none)
DWORD FindInstance(const char *arg, char *o, size_t n) {
    if (!arg || !arg[0]) { Out(o, n, "give an instance: intro id, 0x<address> or #<index> (instance.list)"); return 0; }
    DWORD found = 0;
    char *end = nullptr;
    if (arg[0] == '#') {
        long want = strtol(arg + 1, &end, 10), i = 0;
        ForInstances([&](const InstInfo &x) { if (i++ == want) { found = x.addr; return false; } return true; });
    } else if (arg[0] == '0' && (arg[1] == 'x' || arg[1] == 'X')) {
        DWORD want = strtoul(arg, &end, 16);
        ForInstances([&](const InstInfo &x) { if (x.addr == want) { found = x.addr; return false; } return true; });
    } else {
        long want = strtol(arg, &end, 10);
        ForInstances([&](const InstInfo &x) { if (x.intro == want) { found = x.addr; return false; } return true; });
    }
    if (!found) Out(o, n, "no instance '%s' in the list [0x%08lx]", arg, kFirstInstance);
    return found;
}

bool RunInstanceList(const char *arg, char *o, size_t n) {
    if (!g_instOk) { Out(o, n, "instance list not verified"); return false; }
    size_t used = 0;
    o[0] = 0;
    int index = 0, shown = 0;
    int total = ForInstances([&](const InstInfo &x) {
        int i = index++;
        if (arg && arg[0] && !strstr(x.name, arg)) return true;
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s#%d %ld %s 0x%08lx (%.0f %.0f %.0f)", used ? "; " : "", i,
                            x.intro, x.name, x.addr, x.pos[0], x.pos[1], x.pos[2]);
        if (w < 0) return false;
        used += static_cast<size_t>(w);
        ++shown;
        return true;
    });
    if (!total) { Out(o, n, "no instances (needs a level)"); return false; }
    if (used + 40 < n) _snprintf_s(o + used, n - used, _TRUNCATE, "%s%d of %d shown", used ? "; " : "", shown, total);
    return true;
}
bool RunInstanceInfo(const char *arg, char *o, size_t n) {
    DWORD inst = FindInstance(arg, o, n);
    if (!inst) return false;
    InstInfo x;
    ReadInstance(inst, &x);
    float rot[3] = {};
    DWORD flags = 0, nodraw = 0, prev = 0;
    ReadFloats(inst + kInstanceRotation, rot, 3);
    ReadDword(inst + 0x14, &flags);
    ReadDword(inst + 0x23c, &nodraw);
    ReadDword(inst, &prev);
    Out(o, n, "0x%08lx intro %ld object %d %s pos %.2f %.2f %.2f rot %.4f %.4f %.4f iflags 0x%08lx noDrawGroups 0x%08lx%s",
        inst, x.intro, x.objectId, x.name, x.pos[0], x.pos[1], x.pos[2], rot[0], rot[1], rot[2], flags, nodraw,
        prev ? "" : " (node prev 0: removed)");
    return true;
}
bool SetPosition(DWORD inst, const float *p) {
    __try {
        volatile float *dst = reinterpret_cast<volatile float *>(inst + kInstancePosition);
        dst[0] = p[0]; dst[1] = p[1]; dst[2] = p[2];
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}
bool NeedPlayer(DWORD *player, char *o, size_t n) {
    if (!g_experimental || !g_playerOk || !ReadDword(kPlayerPtr, player) || !*player) {
        Out(o, n, "needs a level / experimental off");
        return false;
    }
    return true;
}
bool RunTeleport(const char *arg, char *o, size_t n) {
    DWORD player = 0;
    if (!NeedPlayer(&player, o, n)) return false;
    float p[3];
    if (!ParseFloats(arg, p, 3)) { Out(o, n, "usage: player.teleport <x> <y> <z>"); return false; }
    if (!SetPosition(player, p)) { Out(o, n, "write failed"); return false; }
    Out(o, n, "player at %.1f %.1f %.1f (tip: cheat.flight on, so Lara does not fall)", p[0], p[1], p[2]);
    return true;
}
bool RunMark(const char *, char *o, size_t n) {
    float p[3], r[3];
    DWORD instance = 0;
    if (!ReadLara(p, r, &instance)) { Out(o, n, "needs a level"); return false; }
    memcpy(g_mark, p, sizeof(g_mark));
    g_markSet = true;
    Out(o, n, "mark %.1f %.1f %.1f", p[0], p[1], p[2]);
    return true;
}
void ValMark(char *o, size_t n) {
    if (g_markSet) Out(o, n, "%.1f %.1f %.1f", g_mark[0], g_mark[1], g_mark[2]); else Out(o, n, "-");
}
bool RunRecall(const char *, char *o, size_t n) {
    DWORD player = 0;
    if (!NeedPlayer(&player, o, n)) return false;
    if (!g_markSet) { Out(o, n, "no mark (player.mark first)"); return false; }
    if (!SetPosition(player, g_mark)) { Out(o, n, "write failed"); return false; }
    Out(o, n, "player back at the mark %.1f %.1f %.1f", g_mark[0], g_mark[1], g_mark[2]);
    return true;
}
bool RunGoto(const char *arg, char *o, size_t n) {
    DWORD player = 0;
    if (!NeedPlayer(&player, o, n)) return false;
    DWORD inst = FindInstance(arg, o, n);
    if (!inst) return false;
    float p[3];
    if (!ReadFloats(inst + kInstancePosition, p, 3) || !SetPosition(player, p)) { Out(o, n, "read / write failed"); return false; }
    Out(o, n, "player at instance 0x%08lx (%.1f %.1f %.1f)", inst, p[0], p[1], p[2]);
    return true;
}
bool RunBring(const char *arg, char *o, size_t n) {
    DWORD player = 0;
    if (!NeedPlayer(&player, o, n)) return false;
    DWORD inst = FindInstance(arg, o, n);
    if (!inst) return false;
    float p[3];
    if (!ReadFloats(player + kInstancePosition, p, 3) || !SetPosition(inst, p)) { Out(o, n, "read / write failed"); return false; }
    Out(o, n, "instance 0x%08lx brought to Lara (%.1f %.1f %.1f)", inst, p[0], p[1], p[2]);
    return true;
}
bool RunUnhide(const char *arg, char *o, size_t n) {
    if (!g_postOk || !g_experimental) { Out(o, n, "INSTANCE_Post not verified / experimental off"); return false; }
    DWORD inst = FindInstance(arg, o, n);
    if (!inst) return false;
    Post(inst, 7, 0);                        // TRLAU modules/Instance.cpp: message 7, data 0 = unhide
    Out(o, n, "INSTANCE_Post(0x%08lx, 7, 0)", inst);
    return true;
}
bool RunUnhideAll(const char *, char *o, size_t n) {
    if (!g_postOk || !g_experimental || !InLevel()) { Out(o, n, "needs a level / INSTANCE_Post / experimental"); return false; }
    DWORD list[4096];
    int count = 0;
    ForInstances([&](const InstInfo &x) { list[count++] = x.addr; return true; });
    for (int i = 0; i < count; ++i) Post(list[i], 7, 0);
    Out(o, n, "message 7 posted to %d instances", count);
    return true;
}
bool RunRemove(const char *arg, char *o, size_t n) {
    if (!g_removeOk || !g_experimental) { Out(o, n, "INSTANCE_ReallyRemoveInstance not verified / experimental off"); return false; }
    DWORD inst = FindInstance(arg, o, n), player = 0;
    if (!inst) return false;
    ReadDword(kPlayerPtr, &player);
    if (inst == player) { Out(o, n, "refused: that is the player"); return false; }
    reinterpret_cast<RemoveFn>(kRemoveInstance)(reinterpret_cast<void *>(inst), 0, 0);
    Out(o, n, "INSTANCE_ReallyRemoveInstance(0x%08lx, 0, 0)", inst);
    return true;
}

// ---- costume live: GlobalInfo list + the game's switch 0x6f0a90 ----
// 0x6f0a90 (reached from the costume native 0x79db50 -> 0x778ca0): if altPlayerObjectID [0xe7f1cc] != 0 it becomes
// the current costume [0xe7f1c8], else the id after the player's object id in GlobalInfo [0xe7ee50]+4 (wraps).
// TRLAU then posts message 35 to the player (re-birth the weapons) one frame later.
int GlobalCostumes(WORD *ids, int max) {
    DWORD gi = 0, list = 0, arr = 0;
    WORD count = 0;
    if (!ReadDword(kGlobalInfo, &gi) || !gi || !ReadDword(gi + 4, &list) || !list || !ReadWord(list, &count) ||
        !ReadDword(list + 4, &arr) || !arr)
        return -1;
    int c = count < max ? count : max;
    for (int i = 0; i < c; ++i)
        if (!ReadWord(arr + static_cast<DWORD>(i) * 2, &ids[i])) return i;
    return c;
}
void ValGlobalCostumes(char *o, size_t n) {
    WORD ids[128];
    int c = GlobalCostumes(ids, 128);
    if (c < 0) { Out(o, n, "no GlobalInfo [0x%08lx]", kGlobalInfo); return; }
    size_t used = 0;
    o[0] = 0;
    for (int i = 0; i < c; ++i) {
        char name[64];
        if (!ObjectName(ids[i], name, sizeof(name))) Out(name, sizeof(name), "?");
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%u %s", used ? "; " : "", ids[i], name);
        if (w < 0) return;
        used += static_cast<size_t>(w);
    }
    if (!c) Out(o, n, "empty list");
}
bool SwitchCostume(int id, char *o, size_t n) {
    if (!g_switchOk || !g_postOk || !g_experimental) { Out(o, n, "costume switch not verified / experimental off"); return false; }
    if (!InLevel()) { Out(o, n, "needs a level"); return false; }
    *reinterpret_cast<volatile DWORD *>(kAltPlayerObject) = static_cast<DWORD>(id);
    reinterpret_cast<VoidFn>(kCostumeSwitch)();
    InterlockedExchange(&g_weaponsPending, 2);   // INSTANCE_Post(player, 35, 0) two game frames later
    DWORD now = 0;
    ReadDword(kCostumeNow, &now);
    char cur[96];
    IdName(static_cast<int>(now), cur, sizeof(cur));
    Out(o, n, "costume switched (0x%08lx, alt %d): current %s; weapons message 35 next frame", kCostumeSwitch, id, cur);
    return true;
}
bool RunCostumeNext(const char *, char *o, size_t n) { return SwitchCostume(0, o, n); }
bool RunCostumeLive(const char *arg, char *o, size_t n) {
    if (!arg || !arg[0]) { Out(o, n, "usage: costume.set <object name | object id> (live switch)"); return false; }
    char *end = nullptr;
    long id = strtol(arg, &end, 10);
    if (*end) id = ObjectId(arg);
    if (id <= 0) { Out(o, n, "'%s' is not in the object list", arg); return false; }
    if (g_costumeOk && !reinterpret_cast<CostumeValidFn>(kCostumeValid)(static_cast<int>(id))) {
        Out(o, n, "object %ld refused by the game's check 0x%08lx (no .drm?)", id, kCostumeValid);
        return false;
    }
    return SwitchCostume(static_cast<int>(id), o, n);
}
void WeaponsTick() {
    if (!g_weaponsPending || InterlockedDecrement(&g_weaponsPending) > 0) return;
    DWORD player = 0;
    if (g_postOk && ReadDword(kPlayerPtr, &player) && player) {
        Post(player, 35, 0);
        Log(2, "costume: INSTANCE_Post(player, 35, 0)");
    }
}

// ---- log page: tail of the Tru*.log files (once per second, worker thread) + the game's script prints ----
// 0.4: text = the line without its leading time stamp; stamp = "HH:MM:SS.mmm" of the first occurrence (from the line,
// or the local time for lines without one), last = of the latest repeat, count = repeats collapsed into this entry;
// src[0] == 0 marks an entry that was moved to the head by a repeat
struct LogLine { char src[20]; char stamp[16]; char last[16]; char text[220]; int count; BYTE sev; bool hadStamp; };
const int kLogRing = 512;
LogLine g_logRing[kLogRing];
int g_logHead = 0, g_logTotal = 0;
CRITICAL_SECTION g_logRingLock;
struct TailFile { char name[24]; char path[MAX_PATH]; LONGLONG offset; bool used; };
TailFile g_tails[16];
volatile LONG g_logOverlay = 0;
int g_logLines = 12;
char g_logFilter[24] = "";                   // "" = all, else a source name (TruLink, script, ...)
// 0.7.2 [Log] OverlaySources / OverlayExclude: only the corner overlay (page and log files stay complete); both read
// and written under g_logRingLock
char g_ovlSources[256] = "TruMenu,TruGuard"; // comma list of sources, "*" or "" = all
char g_ovlExclude[512] = "";                 // comma list of substrings; a line holding one is not shown
LONG g_ovlHidden = 0;                        // lines the overlay filter kept out of the last overlay frame
volatile LONG g_scriptLog = 0;               // script print natives redirected
bool g_scriptOk = false;
char g_scriptPartial[220];
size_t g_scriptPartialLen = 0;
LONG g_scriptCount = 0;

// 0.4: per-source rate limit ([Log] MaxLinesPerSecond) and counters
struct SrcRate { char src[20]; DWORD second; int count; LONG dropped; };
SrcRate g_rates[24];
LONG g_logDropped = 0, g_logHidden = 0, g_logCollapsed = 0;
bool IsInfoItem(const char *id);             // defined after kItems

// 2 error, 1 warning, 0 info - by words in the line (the plugins write no level field)
BYTE LineSeverity(const char *t) {
    const char *const errors[] = {"fail", "FAIL", "error", "Error", "ERROR", "exception", "Exception", " NO ", "-> err ",
                                  "crash"};
    for (const char *w : errors)
        if (strstr(t, w)) return 2;
    if (strncmp(t, "err ", 4) == 0) return 2;
    const char *const warnings[] = {"warn", "Warn", "WARN", "not match", "mismatch", "busy", "refused", "unreadable",
                                    "timeout", "timed out", "missing", "skipped", "not verified"};
    for (const char *w : warnings)
        if (strstr(t, w)) return 1;
    return 0;
}

// "HH:MM:SS" or "HH:MM:SS.mmm" followed by a space at the start; returns its length (0 = none)
size_t StampLength(const char *t) {
    for (int i = 0; i < 8; ++i) {
        bool colon = i == 2 || i == 5;
        if (colon ? t[i] != ':' : !isdigit(static_cast<unsigned char>(t[i]))) return 0;
    }
    size_t len = 8;
    if (t[8] == '.' && isdigit(static_cast<unsigned char>(t[9])) && isdigit(static_cast<unsigned char>(t[10])) &&
        isdigit(static_cast<unsigned char>(t[11])))
        len = 12;
    return t[len] == ' ' ? len : 0;
}

// TruLink's echo of a read-type command ("> read32 ...", "> scan ...", "> watch ...", "> ping") and its "menu" lines
// for info items ("> menu status.state", "menu test.list  -> ok ...")
bool IsLinkRead(const char *src, const char *body) {
    if (_stricmp(src, "TruLink") != 0) return false;
    bool echo = body[0] == '>' && body[1] == ' ';
    const char *p = echo ? body + 2 : body;
    char word[24] = "", id[64] = "";
    sscanf_s(p, "%23s %63s", word, static_cast<unsigned>(sizeof(word)), id, static_cast<unsigned>(sizeof(id)));
    if (echo && (_strnicmp(word, "read", 4) == 0 || _strnicmp(word, "scan", 4) == 0 || _strnicmp(word, "watch", 5) == 0 ||
                 _stricmp(word, "ping") == 0))
        return true;
    if (_stricmp(word, "menu") != 0) return false;
    return _strnicmp(id, "status.", 7) == 0 || _stricmp(id, "list") == 0 || IsInfoItem(id);
}

// g_logRingLock held
void PutLine(const LogLine &l) {
    g_logRing[g_logHead] = l;
    g_logHead = (g_logHead + 1) % kLogRing;
    if (g_logTotal < kLogRing) ++g_logTotal;
}

// g_logRingLock held: a "(n lines dropped)" line for every source whose second is over
void FlushDropsLocked(DWORD second) {
    for (SrcRate &r : g_rates) {
        if (!r.src[0] || r.second == second || !r.dropped) continue;
        LogLine l = {};
        strncpy_s(l.src, sizeof(l.src), r.src, _TRUNCATE);
        SYSTEMTIME t;
        GetLocalTime(&t);
        _snprintf_s(l.stamp, sizeof(l.stamp), _TRUNCATE, "%02d:%02d:%02d.%03d", t.wHour, t.wMinute, t.wSecond,
                    t.wMilliseconds);
        strncpy_s(l.last, sizeof(l.last), l.stamp, _TRUNCATE);
        _snprintf_s(l.text, sizeof(l.text), _TRUNCATE, "(%ld lines dropped: more than %d per second, [Log] "
                    "MaxLinesPerSecond / log.rate)", r.dropped, g_logRate);
        l.count = 1;
        l.sev = 1;
        PutLine(l);
        r.dropped = 0;
    }
}

void PushLine(const char *src, const char *text) {
    if (strstr(text, "exception") || strstr(text, "Exception")) InterlockedIncrement(&g_exceptionLines);
    LogLine l = {};
    strncpy_s(l.src, sizeof(l.src), src, _TRUNCATE);
    const char *body = text;
    size_t stamp = StampLength(text);
    if (stamp) {
        memcpy(l.stamp, text, stamp);
        l.stamp[stamp] = 0;
        l.hadStamp = true;
        body = text + stamp;
        while (*body == ' ') ++body;
    } else {
        SYSTEMTIME t;
        GetLocalTime(&t);
        _snprintf_s(l.stamp, sizeof(l.stamp), _TRUNCATE, "%02d:%02d:%02d.%03d", t.wHour, t.wMinute, t.wSecond,
                    t.wMilliseconds);
    }
    if (g_logHideReads && IsLinkRead(l.src, body)) { InterlockedIncrement(&g_logHidden); return; }
    strncpy_s(l.text, sizeof(l.text), body, _TRUNCATE);
    strncpy_s(l.last, sizeof(l.last), l.stamp, _TRUNCATE);
    l.count = 1;
    l.sev = LineSeverity(body);
    DWORD second = GetTickCount() / 1000;
    EnterCriticalSection(&g_logRingLock);
    FlushDropsLocked(second);
    // collapse: the newest line of the same source has the same text -> count it there and move it to the head
    if (g_logCollapse) {
        for (int k = 0; k < g_logTotal && k < 64; ++k) {
            LogLine &o = g_logRing[(g_logHead - 1 - k + kLogRing) % kLogRing];
            if (!o.src[0] || _stricmp(o.src, l.src) != 0) continue;
            if (strcmp(o.text, l.text) == 0) {
                l.count = o.count + 1;
                strncpy_s(l.stamp, sizeof(l.stamp), o.stamp, _TRUNCATE);
                l.hadStamp = o.hadStamp;
                l.sev = o.sev;
                if (k == 0) {
                    o = l;
                } else {
                    o.src[0] = 0;
                    PutLine(l);
                }
                ++g_logCollapsed;
                LeaveCriticalSection(&g_logRingLock);
                return;
            }
            break;
        }
    }
    // rate limit per source
    SrcRate *rate = nullptr;
    for (SrcRate &r : g_rates)
        if (r.src[0] && _stricmp(r.src, l.src) == 0) { rate = &r; break; }
    if (!rate)
        for (SrcRate &r : g_rates)
            if (!r.src[0]) { strncpy_s(r.src, sizeof(r.src), l.src, _TRUNCATE); r.second = second; rate = &r; break; }
    if (rate) {
        if (rate->second != second) { rate->second = second; rate->count = 0; }
        if (g_logRate > 0 && rate->count >= g_logRate) {
            ++rate->dropped;
            ++g_logDropped;
            LeaveCriticalSection(&g_logRingLock);
            return;
        }
        ++rate->count;
    }
    PutLine(l);
    LeaveCriticalSection(&g_logRingLock);
}

// worker thread, once per second: the "(n lines dropped)" line also when the source stays quiet afterwards
void FlushDrops() {
    EnterCriticalSection(&g_logRingLock);
    FlushDropsLocked(GetTickCount() / 1000);
    LeaveCriticalSection(&g_logRingLock);
}

// one shown line: "[src] stamp text", collapsed: "[src] text x42 (17:09:02-17:09:33)"
void FormatLine(const LogLine &l, char *o, size_t n, size_t maxText) {
    if (l.count > 1)
        _snprintf_s(o, n, _TRUNCATE, "[%s] %.*s x%d (%.8s-%.8s)", l.src, static_cast<int>(maxText), l.text, l.count,
                    l.stamp, l.last);
    else if (l.hadStamp)
        _snprintf_s(o, n, _TRUNCATE, "[%s] %s %.*s", l.src, l.stamp, static_cast<int>(maxText), l.text);
    else
        _snprintf_s(o, n, _TRUNCATE, "[%s] %.*s", l.src, static_cast<int>(maxText), l.text);
}

// 0.7.2: is <word> one of the comma separated tokens of <list>? (outer spaces ignored, case-insensitive)
bool ListHas(const char *list, const char *word) {
    size_t len = strlen(word);
    for (const char *p = list; *p;) {
        while (*p == ',' || *p == ' ') ++p;
        const char *e = p;
        while (*e && *e != ',') ++e;
        const char *t = e;
        while (t > p && t[-1] == ' ') --t;
        if (static_cast<size_t>(t - p) == len && len && _strnicmp(p, word, len) == 0) return true;
        p = e;
    }
    return false;
}
// 0.7.2, g_logRingLock held: the overlay filter ([Log] OverlaySources / OverlayExclude)
bool OverlayShowsLocked(const LogLine &l) {
    bool all = !g_ovlSources[0] || ListHas(g_ovlSources, "*");
    if (!all && !ListHas(g_ovlSources, l.src)) return false;
    for (const char *p = g_ovlExclude; *p;) {                  // substrings, comma separated, outer spaces dropped
        while (*p == ',' || *p == ' ') ++p;
        const char *e = p;
        while (*e && *e != ',') ++e;
        const char *t = e;
        while (t > p && t[-1] == ' ') --t;
        size_t len = static_cast<size_t>(t - p);
        if (len) {
            char sub[128];
            strncpy_s(sub, sizeof(sub), p, len < sizeof(sub) ? len : sizeof(sub) - 1);
            if (strstr(l.text, sub)) return false;
        }
        p = e;
    }
    return true;
}

// the last <max> lines matching the filter and [Log] MinLevel, oldest first; returns the count. 0.7.2: overlay = also
// the overlay filter
int CopyLines(LogLine *out, int max, const char *filter, bool overlay = false) {
    int c = 0;
    LONG hidden = 0;
    EnterCriticalSection(&g_logRingLock);
    for (int k = 0; k < g_logTotal && c < max; ++k) {
        const LogLine &l = g_logRing[(g_logHead - 1 - k + kLogRing) % kLogRing];
        if (!l.src[0] || l.sev < g_logMinLevel) continue;
        if (filter && filter[0] && _stricmp(l.src, filter) != 0) continue;
        if (overlay && !OverlayShowsLocked(l)) { ++hidden; continue; }
        out[c++] = l;
    }
    if (overlay) g_ovlHidden = hidden;
    LeaveCriticalSection(&g_logRingLock);
    for (int i = 0; i < c / 2; ++i) { LogLine t = out[i]; out[i] = out[c - 1 - i]; out[c - 1 - i] = t; }
    return c;
}

void TailOne(TailFile &t, bool first) {
    HANDLE h = CreateFileA(t.path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                           OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    LARGE_INTEGER size = {};
    GetFileSizeEx(h, &size);
    if (size.QuadPart < t.offset) t.offset = 0;                 // file was recreated
    LONGLONG from = t.offset;
    if (size.QuadPart - from > 6000) from = size.QuadPart - 6000;  // never more than the last ~6 KB
    if (first && size.QuadPart - from > 2000) from = size.QuadPart - 2000;
    if (size.QuadPart > from) {
        static char buf[6200];
        LARGE_INTEGER pos;
        pos.QuadPart = from;
        DWORD got = 0;
        if (SetFilePointerEx(h, pos, nullptr, FILE_BEGIN) &&
            ReadFile(h, buf, static_cast<DWORD>(size.QuadPart - from), &got, nullptr)) {
            buf[got] = 0;
            char *p = buf;
            if (from != t.offset) { char *nl = strchr(p, '\n'); p = nl ? nl + 1 : p + got; }  // skip a cut line
            DWORD consumed = got;
            char *lastNl = strrchr(p, '\n');
            if (lastNl) consumed = static_cast<DWORD>(lastNl + 1 - buf); else consumed = static_cast<DWORD>(p - buf);
            if (lastNl) *lastNl = 0;
            char *context = nullptr;
            if (lastNl)
                for (char *line = strtok_s(p, "\r\n", &context); line; line = strtok_s(nullptr, "\r\n", &context))
                    PushLine(t.name, line);
            t.offset = from + consumed;
        }
    }
    CloseHandle(h);
}

void TailDir(const char *dir) {
    char pattern[MAX_PATH];
    _snprintf_s(pattern, sizeof(pattern), _TRUNCATE, "%sTru*.log", dir);
    WIN32_FIND_DATAA fd;
    HANDLE f = FindFirstFileA(pattern, &fd);
    if (f == INVALID_HANDLE_VALUE) return;
    do {
        char path[MAX_PATH];
        _snprintf_s(path, sizeof(path), _TRUNCATE, "%s%s", dir, fd.cFileName);
        int slot = -1;
        for (int i = 0; i < 16; ++i)
            if (g_tails[i].used && _stricmp(g_tails[i].path, path) == 0) { slot = i; break; }
        bool first = false;
        if (slot < 0) {
            for (int i = 0; i < 16 && slot < 0; ++i)
                if (!g_tails[i].used) slot = i;
            if (slot < 0) continue;
            TailFile &t = g_tails[slot];
            t.used = true;
            t.offset = 0;
            strncpy_s(t.path, sizeof(t.path), path, _TRUNCATE);
            strncpy_s(t.name, sizeof(t.name), fd.cFileName, _TRUNCATE);
            char *dot = strrchr(t.name, '.');
            if (dot) *dot = 0;
            first = true;
        }
        TailOne(g_tails[slot], first);
    } while (FindNextFileA(f, &fd));
    FindClose(f);
}

void LogTailTick() {
    static DWORD last = 0;
    DWORD now = GetTickCount();
    if (now - last < 1000) return;
    last = now;
    TailDir(g_asiDir);
    FlushDrops();
    if (_stricmp(g_asiDir, g_exeDir) != 0) TailDir(g_exeDir);
}

// script print natives of NsCoreBase (registered as natives 0..7 at 0x7b3920..0x7b399e, cdecl (instance, numArgs,
// DataValue *args), 4 bytes per argument). In retail they end in empty functions (0x574be0 / 0x7987b0: ret) or in
// sprintf into a stack buffer that is dropped (0x4a3200 .. 0x4a32c0). TruMenu replaces their first 5 bytes with a
// jmp to the handlers below while log.script is on.
struct ScriptNative { DWORD addr; const char *bytes; int kind; BYTE saved[5]; };
enum { kSnInt, kSnBool, kSnFloat, kSnString };
ScriptNative g_natives[] = {
    {0x00795d30, "8b44240c 80780800 d94004 8b10", kSnInt, {}},          // print int (value, time, newline)
    {0x00795d50, "8b44240c 80780800 d94004 0f95c1 803800", kSnBool, {}}, // print bool
    {0x00795d80, "8b44240c 80780800 d94004 0f95c1 51 8b4c2408", kSnFloat, {}},  // print float
    {0x00795db0, "8b44240c 80780800 d94004 0f95c1 51 51 8b4c240c", kSnString, {}},  // print string
    {0x00795dd0, "8b44240c 80780400 8b10 0f95c1", kSnInt, {}},          // log int (value, newline)
    {0x00795df0, "8b44240c 80780400 0f95c1 803800", kSnBool, {}},       // log bool
    {0x00795e10, "8b44240c 80780400 d900 0f95c1", kSnFloat, {}},        // log float
    {0x00795e30, "8b44240c 80780400 0f95c1 51 8b4c2408 50", kSnString, {}},  // log string
};
const int kNativeCount = sizeof(g_natives) / sizeof(g_natives[0]);

void ScriptText(const char *text, bool newline) {
    for (const char *p = text; *p; ++p) {
        if (*p == '\n' || g_scriptPartialLen + 1 >= sizeof(g_scriptPartial)) {
            g_scriptPartial[g_scriptPartialLen] = 0;
            PushLine("script", g_scriptPartial);
            g_scriptPartialLen = 0;
            if (*p == '\n') continue;
        }
        if (*p != '\r') g_scriptPartial[g_scriptPartialLen++] = *p;
    }
    if (newline) {
        g_scriptPartial[g_scriptPartialLen] = 0;
        PushLine("script", g_scriptPartial);
        g_scriptPartialLen = 0;
    }
    ++g_scriptCount;
}

// a string DataValue: a char* or a pointer to one (not verified - both are tried, read under __try)
void ScriptString(DWORD *args, char *out, size_t size) {
    DWORD v = 0, w = 0;
    out[0] = 0;
    if (!ReadDword(reinterpret_cast<DWORD>(args), &v) || !v) return;
    char a[200];
    if (ReadString(v, a, sizeof(a)) && a[0] && isprint(static_cast<unsigned char>(a[0]))) {
        strncpy_s(out, size, a, _TRUNCATE);
        return;
    }
    if (ReadDword(v, &w) && w && ReadString(w, a, sizeof(a))) strncpy_s(out, size, a, _TRUNCATE);
}

void ScriptNativeCall(int kind, int argsWithTime, DWORD *args) {
    char text[220];
    bool newline = false;
    __try {
        int nlIndex = argsWithTime ? 2 : 1;
        newline = reinterpret_cast<BYTE *>(args)[4 * nlIndex] != 0;
        switch (kind) {
        case kSnInt: Out(text, sizeof(text), "%ld", static_cast<LONG>(args[0])); break;
        case kSnBool: Out(text, sizeof(text), "%s", reinterpret_cast<BYTE *>(args)[0] ? "true" : "false"); break;
        case kSnFloat: Out(text, sizeof(text), "%g", static_cast<double>(*reinterpret_cast<float *>(&args[0]))); break;
        default: ScriptString(args, text, sizeof(text)); break;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
        Out(text, sizeof(text), "(unreadable script argument)");
    }
    ScriptText(text, newline);
}
void __cdecl SnPrintInt(void *, int, DWORD *a) { ScriptNativeCall(kSnInt, 1, a); }
void __cdecl SnPrintBool(void *, int, DWORD *a) { ScriptNativeCall(kSnBool, 1, a); }
void __cdecl SnPrintFloat(void *, int, DWORD *a) { ScriptNativeCall(kSnFloat, 1, a); }
void __cdecl SnPrintString(void *, int, DWORD *a) { ScriptNativeCall(kSnString, 1, a); }
void __cdecl SnLogInt(void *, int, DWORD *a) { ScriptNativeCall(kSnInt, 0, a); }
void __cdecl SnLogBool(void *, int, DWORD *a) { ScriptNativeCall(kSnBool, 0, a); }
void __cdecl SnLogFloat(void *, int, DWORD *a) { ScriptNativeCall(kSnFloat, 0, a); }
void __cdecl SnLogString(void *, int, DWORD *a) { ScriptNativeCall(kSnString, 0, a); }
typedef void(__cdecl *SnFn)(void *, int, DWORD *);
const SnFn kSnHandlers[] = {SnPrintInt, SnPrintBool, SnPrintFloat, SnPrintString,
                            SnLogInt, SnLogBool, SnLogFloat, SnLogString};

// game thread: patch / restore the natives (the scripts run on the game thread, so none is running now)
bool SetScriptLog(bool on, char *o, size_t n) {
    if (!g_scriptOk) { Out(o, n, "script natives did not match at load - log.script off"); return false; }
    if (on == (g_scriptLog != 0)) { Out(o, n, "log.script %d (unchanged)", on ? 1 : 0); return true; }
    for (int i = 0; i < kNativeCount; ++i) {
        ScriptNative &s = g_natives[i];
        if (on) {
            BYTE jmp[5] = {0xe9};
            DWORD rel = reinterpret_cast<DWORD>(kSnHandlers[i]) - (s.addr + 5);
            memcpy(jmp + 1, &rel, 4);
            memcpy(s.saved, reinterpret_cast<const void *>(s.addr), 5);
            if (!WriteBytes(s.addr, jmp, 5)) { Out(o, n, "patch of 0x%08lx failed", s.addr); return false; }
        } else {
            WriteBytes(s.addr, s.saved, 5);
        }
    }
    InterlockedExchange(&g_scriptLog, on ? 1 : 0);
    Out(o, n, "log.script %d (%d NsCoreBase print / log natives %s)", on ? 1 : 0, kNativeCount,
        on ? "redirected to the log page" : "restored");
    Log(1, "%s", o);
    return true;
}
bool RunScriptLog(const char *arg, char *o, size_t n) { return SetScriptLog(BoolArg(arg, g_scriptLog != 0), o, n); }
void ValScriptLog(char *o, size_t n) { Out(o, n, "%d (%ld prints)", g_scriptLog ? 1 : 0, g_scriptCount); }

void LinesText(const char *filter, int max, char *o, size_t n) {
    static LogLine lines[64];                // only called from one thread at a time in practice (menu / TruLink)
    if (max > 64) max = 64;
    int c = CopyLines(lines, max, filter);
    size_t used = 0;
    o[0] = 0;
    for (int i = 0; i < c; ++i) {
        char line[300];
        FormatLine(lines[i], line, sizeof(line), 220);
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s", used ? " | " : "", line);
        if (w < 0) return;
        used += static_cast<size_t>(w);
    }
    if (!c) Out(o, n, "no lines");
}
void ValLogPage(char *o, size_t n) { LinesText(g_logFilter, g_logLines, o, n); }
void ValScriptLines(char *o, size_t n) { LinesText("script", g_logLines, o, n); }
void ValLogOverlay(char *o, size_t n) { Out(o, n, "%d", g_logOverlay ? 1 : 0); }
bool RunLogOverlay(const char *arg, char *o, size_t n) {
    bool on = BoolArg(arg, g_logOverlay != 0);
    InterlockedExchange(&g_logOverlay, on ? 1 : 0);
    Out(o, n, "log.overlay %d", on ? 1 : 0);
    return true;
}
void ValLogLines(char *o, size_t n) { Out(o, n, "%d", g_logLines); }
bool RunLogLines(const char *arg, char *o, size_t n) {
    int v = arg ? atoi(arg) : 0;
    if (v < 1 || v > 64) { Out(o, n, "usage: log.lines <1..64>"); return false; }
    g_logLines = v;
    Out(o, n, "log.lines %d", v);
    return true;
}
void ValLogFilter(char *o, size_t n) { Out(o, n, "%s", g_logFilter[0] ? g_logFilter : "all"); }
bool RunLogFilter(const char *arg, char *o, size_t n) {
    if (!arg || !arg[0] || _stricmp(arg, "all") == 0) g_logFilter[0] = 0;
    else strncpy_s(g_logFilter, sizeof(g_logFilter), arg, _TRUNCATE);
    Out(o, n, "log.filter %s", g_logFilter[0] ? g_logFilter : "all");
    return true;
}
// 0.7.2 overlay filter (runtime; the start values come from [Log] OverlaySources / OverlayExclude)
void ValOvlSources(char *o, size_t n) {
    EnterCriticalSection(&g_logRingLock);
    Out(o, n, "%s", !g_ovlSources[0] || ListHas(g_ovlSources, "*") ? "* (all)" : g_ovlSources);
    LeaveCriticalSection(&g_logRingLock);
}
bool RunOvlSources(const char *arg, char *o, size_t n) {   // no argument: only shows the value
    if (arg && arg[0]) {
        EnterCriticalSection(&g_logRingLock);
        strncpy_s(g_ovlSources, sizeof(g_ovlSources), arg, _TRUNCATE);
        LeaveCriticalSection(&g_logRingLock);
    }
    char v[300];
    ValOvlSources(v, sizeof(v));
    Out(o, n, "log.overlaysources %s (overlay only; page and log files unchanged)", v);
    return true;
}
void ValOvlExclude(char *o, size_t n) {
    EnterCriticalSection(&g_logRingLock);
    Out(o, n, "%s", g_ovlExclude[0] ? g_ovlExclude : "(none)");
    LeaveCriticalSection(&g_logRingLock);
}
bool RunOvlExclude(const char *arg, char *o, size_t n) {   // no argument: only shows the value; none = off
    if (arg && arg[0]) {
        EnterCriticalSection(&g_logRingLock);
        if (!_stricmp(arg, "none")) g_ovlExclude[0] = 0;
        else strncpy_s(g_ovlExclude, sizeof(g_ovlExclude), arg, _TRUNCATE);
        LeaveCriticalSection(&g_logRingLock);
    }
    char v[600];
    ValOvlExclude(v, sizeof(v));
    Out(o, n, "log.overlayexclude %s (overlay only)", v);
    return true;
}
void ValLogCount(char *o, size_t n) {
    Out(o, n, "%d lines, %ld exception lines, %ld caught by TruMenu; 0.4: %ld repeats collapsed, %ld TruLink reads hidden, "
        "%ld dropped by the rate limit", g_logTotal, g_exceptionLines, g_ownExceptions, g_logCollapsed, g_logHidden,
        g_logDropped);
}
// 0.4 log options (also [Log] Collapse / HideLinkReads / MinLevel / MaxLinesPerSecond)
void ValLogCollapse(char *o, size_t n) { Out(o, n, "%d", g_logCollapse ? 1 : 0); }
bool RunLogCollapse(const char *arg, char *o, size_t n) {
    bool on = BoolArg(arg, g_logCollapse != 0);
    InterlockedExchange(&g_logCollapse, on ? 1 : 0);
    Out(o, n, "log.collapse %d (new lines; %ld repeats collapsed so far)", on ? 1 : 0, g_logCollapsed);
    return true;
}
void ValLogHideReads(char *o, size_t n) { Out(o, n, "%d", g_logHideReads ? 1 : 0); }
bool RunLogHideReads(const char *arg, char *o, size_t n) {
    bool on = BoolArg(arg, g_logHideReads != 0);
    InterlockedExchange(&g_logHideReads, on ? 1 : 0);
    Out(o, n, "log.hidereads %d (new lines; %ld hidden so far)", on ? 1 : 0, g_logHidden);
    return true;
}
const char *const kLevelNames[] = {"all", "warn", "error"};
void ValLogLevel(char *o, size_t n) { Out(o, n, "%d (%s)", g_logMinLevel, kLevelNames[g_logMinLevel]); }
bool RunLogLevel(const char *arg, char *o, size_t n) {
    int v = -1;
    if (arg && (_stricmp(arg, "all") == 0 || _stricmp(arg, "info") == 0)) v = 0;
    else if (arg && _strnicmp(arg, "warn", 4) == 0) v = 1;
    else if (arg && _strnicmp(arg, "err", 3) == 0) v = 2;
    else if (arg && isdigit(static_cast<unsigned char>(arg[0]))) v = atoi(arg);
    if (v < 0 || v > 2) { Out(o, n, "usage: log.level 0|1|2 (all | warn | error)"); return false; }
    g_logMinLevel = v;
    Out(o, n, "log.level %d (%s)", v, kLevelNames[v]);
    return true;
}
void ValLogRate(char *o, size_t n) { Out(o, n, "%d (%ld dropped)", g_logRate, g_logDropped); }
bool RunLogRate(const char *arg, char *o, size_t n) {
    if (!arg || !isdigit(static_cast<unsigned char>(arg[0])) || atoi(arg) > 10000) {
        Out(o, n, "usage: log.rate <lines per source and second, 0 = no limit>");
        return false;
    }
    g_logRate = atoi(arg);
    Out(o, n, "log.rate %d", g_logRate);
    return true;
}
bool RunLogClear(const char *, char *o, size_t n) {
    EnterCriticalSection(&g_logRingLock);
    g_logTotal = 0;
    LeaveCriticalSection(&g_logRingLock);
    Out(o, n, "log cleared");
    return true;
}

// ---- videos: Movies\*.bik next to tru.exe, played with 0x4a12b0(name, loop) ----
void ValVideoList(char *o, size_t n) {
    char pattern[MAX_PATH];
    _snprintf_s(pattern, sizeof(pattern), _TRUNCATE, "%sMovies\\*.bik", g_exeDir);
    WIN32_FIND_DATAA fd;
    HANDLE f = FindFirstFileA(pattern, &fd);
    size_t used = 0;
    o[0] = 0;
    if (f == INVALID_HANDLE_VALUE) { Out(o, n, "no Movies\\*.bik next to tru.exe"); return; }
    do {
        char name[MAX_PATH];
        strncpy_s(name, sizeof(name), fd.cFileName, _TRUNCATE);
        char *dot = strrchr(name, '.');
        if (dot) *dot = 0;
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s", used ? " " : "", name);
        if (w < 0) break;
        used += static_cast<size_t>(w);
    } while (FindNextFileA(f, &fd));
    FindClose(f);
}
bool VideoName(const char *arg, char *name, size_t size, char *o, size_t n) {
    if (!arg || !arg[0] || strlen(arg) > 48) { Out(o, n, "give a video name (media.video.list)"); return false; }
    strncpy_s(name, size, arg, _TRUNCATE);
    char *dot = strrchr(name, '.');
    if (dot && _stricmp(dot, ".bik") == 0) *dot = 0;
    for (const char *p = name; *p; ++p)
        if (!(isalnum(static_cast<unsigned char>(*p)) || *p == '_' || *p == '-')) { Out(o, n, "name: a-z 0-9 _ - only"); return false; }
    char path[MAX_PATH];
    _snprintf_s(path, sizeof(path), _TRUNCATE, "%sMovies\\%s.bik", g_exeDir, name);
    if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) { Out(o, n, "no Movies\\%s.bik", name); return false; }
    return true;
}
bool RunVideoPlay(const char *arg, char *o, size_t n) {
    if (!g_movieOk || !g_mainStateOk || !g_experimental) { Out(o, n, "movie player not verified / experimental off"); return false; }
    static char name[64];
    if (!VideoName(arg, name, sizeof(name), o, n)) return false;
    DWORD state = 0;
    ReadDword(kMainState, &state);
    // catalog 11.1: the player is a blocking-style one; only from the front end (TRLAU main state 10 = main menu)
    if (state != 10) { Out(o, n, "front end only (main state [0x%08lx] = %lu, needs 10)", kMainState, state); return false; }
    reinterpret_cast<MoviePlayFn>(kMoviePlay)(name, false);
    Out(o, n, "0x%08lx(\"%s\", 0) called", kMoviePlay, name);
    return true;
}
void ValMenuLoop(char *o, size_t n) {
    DWORD p = 0;
    char s[64] = "";
    if (ReadDword(kMenuLoopPtr, &p)) ReadString(p, s, sizeof(s));
    Out(o, n, "%s", s[0] ? s : "?");
}
bool RunMenuLoop(const char *arg, char *o, size_t n) {
    if (!g_menuLoopOk || !g_experimental) { Out(o, n, "menu loop pointer not verified / experimental off"); return false; }
    if (!arg || !arg[0]) {
        *reinterpret_cast<volatile DWORD *>(kMenuLoopPtr) = kMenuLoopOrig;
        Out(o, n, "menu background back to medsea_loop");
        return true;
    }
    char name[64];
    if (!VideoName(arg, name, sizeof(name), o, n)) return false;
    strncpy_s(g_menuLoopName, sizeof(g_menuLoopName), name, _TRUNCATE);
    *reinterpret_cast<volatile DWORD *>(kMenuLoopPtr) = reinterpret_cast<DWORD>(g_menuLoopName);
    Out(o, n, "menu background loop = %s (0x%08lx; used when the main menu starts its movie again)", name, kMenuLoopPtr);
    return true;
}

// ---- 0.7.1 level.start: start a unit the way the mission menu does (Befund-Direktstart.md, README "AutoStart") ----
// PC generalbank script 104 (mission menu) on confirm: uigamedata f22, uigamedata f27(unit, 1, 0, 1), stdscreenmgr
// f19 + f7 (test 41e did the same from the attract timer script 60 and the DLC 2 intro played). The natives, read with
// tools/pe_dis.py: uigamedata binder 0x7af0c0 registers f22 = 0x7a0d00 (jmp 0x77bc90 -> jmp 0x4a0f10: byte [0xa039b8]
// = 1, no arguments) and f27 = 0x7a0d40 (its three bools from the argument block, then jmp 0x77e170 = cdecl
// (DataValue *args, bool, bool, bool), args[0] = char *unit, copied by 0x5dfb20 into GameTracker+0x38; plain ret);
// stdscreenmgr binder 0x7adca0 registers f7 = 0x79ea00 (jmp 0x4be580) and f19 = 0x79eac0 (jmp 0x4be5e0): both ignore
// the script instance and call slot 4 of the screen-manager singletons [0xa13f58] (vtable 0x847c7c) / [0xa13f50]
// (vtable 0x847cc4), both 0x4c5260 (thiscall, no arguments, plain ret). So the whole sequence is callable from C on
// the game thread without a script frame. level.load (GAMELOOP_RequestLevelChangeByName) skips the intro; this does not.
bool Enqueue(const char *id, const char *arg);   // game-thread request slot, defined after kItems
typedef void(__cdecl *MissionStartFn)(const DWORD *args, int b1, int b2, int b3);
const DWORD kUgdF22 = 0x004a0f10, kUgdF27 = 0x0077e170, kScrF7 = 0x004be580, kScrF19 = 0x004be5e0;
const DWORD kScrMgr7 = 0x00a13f58, kScrMgr19 = 0x00a13f50, kScrVt7 = 0x00847c7c, kScrVt19 = 0x00847cc4;
bool g_missionOk = false;

bool MissionCheck() {
    return HexBytesAt(0x007af201, "68000d7a00 6a16") && HexBytesAt(0x007af247, "68400d7a00 6a1b") &&
           HexBytesAt(0x007a0d00, "e98baffdff") && HexBytesAt(0x0077bc90, "e97b52d2ff") &&
           HexBytesAt(kUgdF22, "c605b839a00001 c3") &&
           HexBytesAt(0x007a0d40, "8b44240c 80780c00 89442404 0f95c1 80780800 0f95c2 80780400") &&
           HexBytesAt(0x007a0d69, "e902d4fdff") &&
           HexBytesAt(kUgdF27, "55 8bec 83e4f8 81ec54020000 807d0c00 8b4508 8b08 53 0f95c2 807d1400") &&
           HexBytesAt(0x0077e425, "8b4c2448 898290000000 8b4510 50 51 e8e716e6ff 83c408 5f 5e 5b 8be5 5d c3") &&
           HexBytesAt(0x007add0f, "6800ea7900 6a07") && HexBytesAt(0x007addb7, "68c0ea7900 6a13") &&
           HexBytesAt(0x0079ea00, "8b4c2404 e977fbd1ff") && HexBytesAt(0x0079eac0, "8b4c2404 e917fbd1ff") &&
           HexBytesAt(kScrF7, "8b0d583fa100 8b01 8b5010 ffe2") && HexBytesAt(kScrF19, "8b0d503fa100 8b01 8b5010 ffe2") &&
           HexBytesAt(0x00847c8c, "60524c00") && HexBytesAt(0x00847cd4, "60524c00") &&
           HexBytesAt(0x004c5260, "51 8b4104 85c0 740b 8d0c24 890424 e8edfe2d00 59 c3") &&
           HexBytesAt(0x004ccd3d, "c7067c7c8400 8935583fa100") && HexBytesAt(0x004ccd96, "c706c47c8400 8935503fa100");
}

// ---- 0.7.2: what a mission start does after f27, read statically (tools/pe_dis.py, tools/pe_callers.py) ----
// The game loop 0x5e01ab calls the main-state dispatcher 0x5e0090(&mainState 0xe7ed60, GameTracker 0xe7f088): jump
// table 0x5e015c on state - 1 (states 1..10). f27 = 0x77e170 stores its 2nd argument as byte [0xfae8d9] (0x77e193,
// "costume / weapon selection", TU MainTracker_UILoadLevel), then 0x5dfb20 copies the unit to GameTracker+0x38 and,
// unless the main state is 1 (in a level: GAMELOOP_RequestLevelChangeByName), sets main state = 2 (0x5dfb83).
// State 2 (table 0x5e0160 -> 0x5e00cd -> 0x5de7e0): byte [0xfae8d9] != 0 -> main state = 9 (0x5de884) = the outfit /
// weapon selection (state 9 -> 0x5e012e); else the level load itself (0x5de2b0). 0x77e450 clears the byte when the
// selection is done (then 0x5de9c0). GameTracker+0xb9 (the level.load request byte) stays 0 the whole time - so the
// 0.7.1 test missed it, and a level.load during state 9 set +0xb9 that the state-9 screen never serves (hang).
const DWORD kSelectFlag = 0x00fae8d9;

bool PendingCheck() {
    return HexBytesAt(0x005e01ab, "6888f0e700 6860ede700 e8d6feffff") &&
           HexBytesAt(0x005e0096, "8b3e 8d47ff 83f809 0f87b0000000 ff24855c015e00") &&
           HexBytesAt(0x005e0160, "cd005e00") && HexBytesAt(0x005e017c, "2e015e00") &&
           HexBytesAt(0x005e00cd, "8b442410 50 56 e808e7ffff") &&
           HexBytesAt(0x005de877, "381dd9e8fa00 740d 8b54240c 5e c70209000000") &&
           HexBytesAt(0x005dfb5c, "833d60ede70001 881df2f1e700 7517") &&
           HexBytesAt(0x005dfb83, "c70560ede70002000000");
}

// main state 2 (level start being set up) or 9 (outfit / weapon selection), else 0; 0 when the checks failed
int PendingMainState() {
    if (!g_pendingOk) return 0;
    DWORD state = 0;
    if (!ReadDword(kMainState, &state)) return 0;
    return state == 2 || state == 9 ? static_cast<int>(state) : 0;
}

// true (with the reason) while a level change or a mission start is pending: level.load / level.start are refused
bool LevelChangePending(char *why, size_t n) {
    DWORD busy = 0;
    ReadDword(kGameTracker + 0xb8, &busy);
    if ((busy >> 8) & 0xff) { Out(why, n, "GameTracker+0xb9 = %lu: a level change request waits", (busy >> 8) & 0xff); return true; }
    int state = PendingMainState();
    if (state == 9) { Out(why, n, "main state 9: the outfit / weapon selection of a level start is open"); return true; }
    if (state == 2) { Out(why, n, "main state 2: a level start is being set up"); return true; }
    return false;
}

// Title update rule (translated): TU generalbank script 134 function 9 (tools/menu_dlc_probe.py dis xt 134,
// +0x257c..+0x2608): unit == dlc_level4_start || dlc_level5_start || dlc_level6_start || dlc_level2_start ->
// uigamedata f26(unit, 0, 0, 1), else f26(unit, 1, 0, 1) (the TU's MainTracker_UILoadLevel = PC f27 0x77e170). The PC
// script 104 function 9 (dis pp 104, +0x23c0..+0x2438) tests only levels 4 / 5 / 6, so DLC 2 gets the selection.
// Returns f27's 2nd argument: 1 = outfit / weapon selection (main state 9), 0 = none.
int MissionSelectArg(const char *unit) {
    if (!g_outfitRule || !g_outfitRuleOk) return 1;
    static const char *const kNoSelect[] = {"dlc_level4_start", "dlc_level5_start", "dlc_level6_start", "dlc_level2_start"};
    for (const char *u : kNoSelect)
        if (!_stricmp(unit, u)) return 0;
    return 1;
}

// "dlc2" / "dlc1" or a unit name -> unit name; false if not usable
bool StartUnitName(const char *arg, char *unit, size_t size) {
    const char *u = arg && arg[0] ? arg : "dlc_level2_start";
    if (!_stricmp(u, "dlc2")) u = "dlc_level2_start";
    else if (!_stricmp(u, "dlc1")) u = "dlc_level1_start";
    size_t len = strlen(u);
    if (!len || len > 63) return false;
    for (size_t i = 0; i < len; ++i)
        if (!(isalnum(static_cast<unsigned char>(u[i])) || u[i] == '_' || u[i] == '-')) return false;
    strncpy_s(unit, size, u, _TRUNCATE);
    return true;
}

bool MissionCall(const DWORD *args, int select) {
    __try {
        reinterpret_cast<VoidFn>(kUgdF22)();                                   // uigamedata f22
        reinterpret_cast<MissionStartFn>(kUgdF27)(args, select, 0, 1);         // uigamedata f27(unit, select, 0, 1)
        reinterpret_cast<VoidFn>(kScrF19)();                                   // stdscreenmgr f19
        reinterpret_cast<VoidFn>(kScrF7)();                                    // stdscreenmgr f7
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
        return false;
    }
}

// game thread (queued): level.start [dlc2|dlc1|<unit>]
bool RunLevelStart(const char *arg, char *o, size_t n) {
    if (!g_missionOk || !g_mainStateOk || !g_experimental) {
        Out(o, n, "mission start path not verified / experimental off (level.load skips the intro)");
        return false;
    }
    static char unit[64];                        // the game keeps no pointer to it (copied to GameTracker+0x38)
    static DWORD args[4];                        // DataValue block of f27: unit, 1, 0, 1
    char name[64];
    if (!StartUnitName(arg, name, sizeof(name))) { Out(o, n, "usage: level.start [dlc2|dlc1|<unit name a-z 0-9 _ ->]"); return false; }
    char why[200];                               // 0.7.2: first, so a second start during the first one says why
    if (LevelChangePending(why, sizeof(why))) { Out(o, n, "refused: level change pending (%s)", why); return false; }
    DWORD state = 0;
    ReadDword(kMainState, &state);
    if (state != 10) { Out(o, n, "main menu only (main state [0x%08lx] = %lu, needs 10)", kMainState, state); return false; }
    DWORD m7 = 0, m19 = 0, vt7 = 0, vt19 = 0;
    if (!ReadDword(kScrMgr7, &m7) || !m7 || !ReadDword(m7, &vt7) || vt7 != kScrVt7 || !ReadDword(kScrMgr19, &m19) ||
        !m19 || !ReadDword(m19, &vt19) || vt19 != kScrVt19) {
        Out(o, n, "screen managers not ready ([0x%08lx] = 0x%08lx vtable 0x%08lx, [0x%08lx] = 0x%08lx vtable 0x%08lx)",
            kScrMgr7, m7, vt7, kScrMgr19, m19, vt19);
        return false;
    }
    strncpy_s(unit, sizeof(unit), name, _TRUNCATE);
    int select = MissionSelectArg(unit);         // 0.7.2: the TU rule ([Levels] OutfitRule)
    args[0] = reinterpret_cast<DWORD>(unit);
    args[1] = static_cast<DWORD>(select);
    args[2] = 0;
    args[3] = 1;
    if (!MissionCall(args, select)) { Out(o, n, "exception in the mission start sequence (unit '%s')", unit); return false; }
    Out(o, n, "mission start '%s': uigamedata f22, f27('%s', %d, 0, 1), stdscreenmgr f19 + f7 called (intro plays; %s)",
        unit, unit, select,
        select ? (g_outfitRule && g_outfitRuleOk ? "outfit / weapon selection - as the title update for this unit"
                                                 : "outfit / weapon selection - PC script 104 rule")
               : "no outfit / weapon selection - title update rule, [Levels] OutfitRule=1");
    if (g_menuOpen) ToggleMenu("level start");
    return true;
}
void ValLevelStart(char *o, size_t n) {
    DWORD state = 0;
    ReadDword(kMainState, &state);
    BYTE flag = 0;
    if (g_outfitRuleOk) ReadByte(kSelectFlag, &flag);
    Out(o, n, "path %s, main state %lu (needs 10); outfit rule %s (selection byte [0x%08lx] = %u); pending check %s; "
        "AutoStart %s", g_missionOk ? "ok" : "NOT verified", state,
        !g_outfitRule ? "off - PC script 104 (always the selection)"
                      : g_outfitRuleOk ? "title update (dlc_level2 / 4..6_start without the selection)"
                                       : "NOT verified - PC script 104 (always the selection)",
        kSelectFlag, flag, g_pendingOk ? "main state 2 / 9 + GameTracker+0xb9" : "NOT verified - GameTracker+0xb9 only",
        g_autoStartMode);
}

// 0.7.1 [Test] AutoStart: once per game start, when the main menu has been up for AutoStartDelay seconds, queue
// level.start (or, without the verified path, level.load with a log line). Render thread, every Present.
void AutoStartTick() {
    static bool done = false;
    static DWORD since = 0;
    if (done || !g_autoStart[0]) return;
    char unit[64];
    if (!StartUnitName(g_autoStart, unit, sizeof(unit))) {
        done = true;
        g_autoStartMode = "off - [Test] AutoStart is not dlc2 / dlc1 / a unit name";
        Log(0, "AutoStart: '%s' %s", g_autoStart, g_autoStartMode);
        return;
    }
    if (!g_mainStateOk || !g_experimental) {
        done = true;
        g_autoStartMode = "off - main state check failed or [Cheat] Experimental=0";
        Log(0, "AutoStart: %s", g_autoStartMode);
        return;
    }
    DWORD state = 0;
    ReadDword(kMainState, &state);
    DWORD now = GetTickCount();
    if (state != 10) { since = 0; return; }
    if (!since) {
        since = now ? now : 1;
        g_autoStartMode = "waiting (main menu up)";
        Log(1, "AutoStart: main menu up (state 10) - %s in %d s", unit, g_autoStartDelay);
        return;
    }
    if (now - since < static_cast<DWORD>(g_autoStartDelay) * 1000) return;
    const char *id = g_missionOk ? "level.start" : "level.load";
    if (!Enqueue(id, unit)) return;                     // another request pending: next frame
    done = true;
    if (g_missionOk) {
        g_autoStartMode = "done (level.start queued once for this game start)";
        Log(1, "AutoStart: level.start %s queued (mission menu path, the intro plays)", unit);
    } else {
        g_autoStartMode = "done (fallback level.load - intro skipped)";
        Log(0, "AutoStart: intro skipped (mission start path not available) - level.load %s queued instead", unit);
    }
}

// ---- draw.markup / draw.ledges (experimental, read-only): the markup boxes projected like the game's
// TRANS_RotTransPersVectorf 0x49f630 and drawn into ImGui's background draw list ----
// Facts (static, tru.exe): MarkupManager [0xdb94cc] (a vtable object); 0x5c3ce0 (called with ecx = [0xdb94cc] at
// 0x5d3349) walks its boxes: box = [mgr+0x14], next = [box+4]; box +0x20 MarkUp*, +0x28 flags (bits 19 / 20 tested
// there); MarkUp +0x34 position (x y z), +0x58 poly line {int count; points at +0x10 + 16*i}. All of them are moved by
// that function's world shift, so they are world coordinates. Projection 0x49f630: view = M * p with M = 4 columns of
// 16 bytes at 0xa038f0 (column 3 = translation); x' = x / z * f + 256, y' = y / z * f + 224, f = float [0x8906d0]
// (512.0 in the file); TRLAU draws only when z > 16. The 512 x 448 screen space is a reading of those constants and is
// scaled to the back buffer here (draw.scale) - to verify live. Flag bit names are the catalog's (TRLAU Markup.h,
// 30 ledge grab, 27..25 poles, 22 ladder, 20 water, 19 rope) and are not verified for box +0x28.
const DWORD kMarkupMgr = 0x00db94cc, kViewMatrix = 0x00a038f0, kFocal = 0x008906d0;
const DWORD kCentreX = 0x00843a00, kCentreY = 0x008454c8;   // doubles 256.0 / 224.0
bool g_drawOk = false;
volatile LONG g_drawMarkup = 0, g_drawLedges = 0;
float g_drawW = 512.0f, g_drawH = 448.0f;
int g_drawnBoxes = 0;

struct View { float m[16]; float f; double cx, cy; float sx, sy; };

bool ReadView(View *v, float width, float height) {
    if (!ReadFloats(kViewMatrix, v->m, 16) || !ReadFloats(kFocal, &v->f, 1)) return false;
    __try {
        v->cx = *reinterpret_cast<const double *>(kCentreX);
        v->cy = *reinterpret_cast<const double *>(kCentreY);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    v->sx = width / g_drawW;
    v->sy = height / g_drawH;
    return v->f > 0.0f;
}

bool Project(const View &v, const float *p, ImVec2 *out) {
    const float *m = v.m;
    float x = m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12];
    float y = m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13];
    float z = m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14];
    if (!(z > 16.0f)) return false;
    out->x = static_cast<float>(x / z * v.f + v.cx) * v.sx;
    out->y = static_cast<float>(y / z * v.f + v.cy) * v.sy;
    return out->x > -4000.0f && out->x < 8000.0f && out->y > -4000.0f && out->y < 8000.0f;
}

ImU32 MarkupColour(DWORD flags) {
    if (flags & (1u << 30)) return IM_COL32(255, 220, 40, 230);    // ledge grab
    if (flags & (1u << 22)) return IM_COL32(60, 230, 90, 230);     // ladder
    if (flags & (7u << 25)) return IM_COL32(60, 220, 230, 230);    // poles
    if (flags & (1u << 20)) return IM_COL32(60, 120, 255, 230);    // water
    if (flags & (1u << 19)) return IM_COL32(230, 120, 40, 230);    // rope
    return IM_COL32(200, 200, 200, 160);
}

void DrawMarkup() {
    if (!g_drawOk || !InLevel()) return;
    ImGuiIO &io = ImGui::GetIO();
    View v;
    if (!ReadView(&v, io.DisplaySize.x, io.DisplaySize.y)) return;
    ImDrawList *dl = ImGui::GetBackgroundDrawList();
    DWORD mgr = 0, box = 0;
    if (!ReadDword(kMarkupMgr, &mgr) || !mgr || !ReadDword(mgr + 0x14, &box)) return;
    int drawn = 0;
    for (int guard = 0; box && guard < 4000; ++guard) {
        DWORD flags = 0, markup = 0, line = 0, next = 0;
        ReadDword(box + 0x28, &flags);
        ReadDword(box + 0x20, &markup);
        if (!ReadDword(box + 4, &next)) break;
        bool ledge = (flags & (1u << 30)) != 0;
        if (markup && (!g_drawLedges || ledge)) {
            ImU32 colour = MarkupColour(flags);
            float pos[3];
            DWORD count = 0;
            ImVec2 a, b;
            bool havePoly = ReadDword(markup + 0x58, &line) && line && ReadDword(line, &count) && count >= 2 && count <= 64;
            if (havePoly) {
                float p0[3], p1[3];
                bool ok0 = ReadFloats(line + 0x10, p0, 3) && Project(v, p0, &a);
                for (DWORD i = 1; i < count; ++i) {
                    bool ok1 = ReadFloats(line + 0x10 + 16 * i, p1, 3) && Project(v, p1, &b);
                    if (ok0 && ok1) dl->AddLine(a, b, colour, 2.0f);
                    a = b;
                    ok0 = ok1;
                }
                ++drawn;
            } else if (ReadFloats(markup + 0x34, pos, 3) && Project(v, pos, &a)) {
                dl->AddCircle(a, 5.0f, colour, 8, 2.0f);
                ++drawn;
            }
        }
        box = next;
    }
    g_drawnBoxes = drawn;
}

void ValDrawMarkup(char *o, size_t n) { Out(o, n, "%d (%d boxes drawn)", g_drawMarkup ? 1 : 0, g_drawnBoxes); }
void ValDrawLedges(char *o, size_t n) { Out(o, n, "%d", g_drawLedges ? 1 : 0); }
bool RunDrawMarkup(const char *arg, char *o, size_t n) {
    if (!g_drawOk) { Out(o, n, "markup / projection code not verified"); return false; }
    bool on = BoolArg(arg, g_drawMarkup != 0);
    InterlockedExchange(&g_drawMarkup, on ? 1 : 0);
    if (!on) InterlockedExchange(&g_drawLedges, 0);
    Out(o, n, "draw.markup %d", on ? 1 : 0);
    return true;
}
bool RunDrawLedges(const char *arg, char *o, size_t n) {
    if (!g_drawOk) { Out(o, n, "markup / projection code not verified"); return false; }
    bool on = BoolArg(arg, g_drawLedges != 0);
    InterlockedExchange(&g_drawLedges, on ? 1 : 0);
    if (on) InterlockedExchange(&g_drawMarkup, 1);
    Out(o, n, "draw.ledges %d (only boxes with flag bit 30)", on ? 1 : 0);
    return true;
}
void ValDrawScale(char *o, size_t n) { Out(o, n, "%.0f %.0f", g_drawW, g_drawH); }
bool RunDrawScale(const char *arg, char *o, size_t n) {
    float v[2];
    if (!ParseFloats(arg, v, 2) || !(v[0] >= 64.0f && v[0] <= 8192.0f && v[1] >= 64.0f && v[1] <= 8192.0f)) {
        Out(o, n, "usage: draw.scale <width> <height> of the game's projected space (default 512 448)");
        return false;
    }
    g_drawW = v[0];
    g_drawH = v[1];
    Out(o, n, "draw.scale %.0f %.0f", v[0], v[1]);
    return true;
}

// ---- weapons / ammo / health (experimental; catalog section 17, static facts, not yet checked live) ----
// playerstate P = [0xfadb58]; weapon manager WM = [P+0x500]; WM::GiveWeaponByName 0x7161f0 thiscall (name, a, b),
// the default loadout's call with (1, 0) - it polls the stream load queue until the object is loaded (blocking, game
// thread, in a level only); reserve ammo u16 P+0x51c+2*type (6 types, HUD reader 0x6e8475); health float P+0x628
// (GetHealth 0x6e7860); MaxHealth 0x6e7990 () -> float.
const DWORD kPlayerState = 0x00fadb58, kGiveWeapon = 0x007161f0, kMaxHealth = 0x006e7990;
typedef void(__fastcall *GiveWeaponFn)(void *wm, int, const char *name, int a, int b);   // thiscall via fastcall
typedef float(__cdecl *MaxHealthFn)();
bool g_weaponOk = false, g_ammoOk = false, g_healthOk = false;
volatile LONG g_invincible = 0;
struct WeaponName { int id; const char *name; };
const WeaponName kWeapons[] = {{37, "wp_handgun"}, {38, "wp_assault_rifle"}, {40, "wp_shotgun"}, {41, "wp_speargun"},
                               {42, "wp_thorhammer"}, {43, "wp_tranq"}, {44, "wp_uzi"}, {114, "wp_akrifle"}};

DWORD PlayerState() {
    DWORD p = 0;
    ReadDword(kPlayerState, &p);
    return p;
}
void ValWeaponList(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    for (const WeaponName &w : kWeapons) {
        char name[64];
        bool listed = ObjectName(w.id, name, sizeof(name)) && _stricmp(name, w.name) == 0;
        int r = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%d %s%s", used ? "; " : "", w.id, w.name,
                            listed ? "" : " (not in the object list)");
        if (r < 0) return;
        used += static_cast<size_t>(r);
    }
}
bool RunWeaponGive(const char *arg, char *o, size_t n) {
    if (!g_weaponOk || !g_experimental) { Out(o, n, "weapon code not verified / experimental off"); return false; }
    DWORD state = 0, p = PlayerState(), wm = 0;
    ReadDword(kMainState, &state);
    if (!InLevel() || state != 1 || !p || !ReadDword(p + 0x500, &wm) || !wm) {
        Out(o, n, "in a level only (main state %lu, needs 1; playerstate 0x%08lx, weapon manager 0x%08lx)", state, p, wm);
        return false;
    }
    if (!arg || !arg[0]) { Out(o, n, "usage: weapon.give <object name> (weapon.list)"); return false; }
    static char name[64];
    strncpy_s(name, sizeof(name), arg, _TRUNCATE);
    if (!ObjectId(name)) { Out(o, n, "'%s' is not in the object list", name); return false; }
    reinterpret_cast<GiveWeaponFn>(kGiveWeapon)(reinterpret_cast<void *>(wm), 0, name, 1, 0);
    Out(o, n, "WM::GiveWeaponByName 0x%08lx(\"%s\", 1, 0) on 0x%08lx done", kGiveWeapon, name, wm);
    return true;
}
void ValAmmo(char *o, size_t n) {
    DWORD p = PlayerState();
    WORD v[6] = {};
    if (!g_ammoOk || !p) { Out(o, n, "-"); return; }
    for (int i = 0; i < 6; ++i) ReadWord(p + 0x51c + 2 * i, &v[i]);
    Out(o, n, "%u %u %u %u %u %u", v[0], v[1], v[2], v[3], v[4], v[5]);
}
bool RunAmmoSet(const char *arg, char *o, size_t n) {
    if (!g_ammoOk || !g_experimental) { Out(o, n, "ammo code not verified / experimental off"); return false; }
    DWORD p = PlayerState();
    int type = -1, value = -1;
    if (!arg || sscanf_s(arg, "%d %d", &type, &value) != 2 || type < 0 || type > 5 || value < 0 || value > 9999) {
        Out(o, n, "usage: ammo.set <type 0..5> <n 0..9999>");
        return false;
    }
    if (!p || !InLevel()) { Out(o, n, "needs a level"); return false; }
    *reinterpret_cast<volatile WORD *>(p + 0x51c + 2 * type) = static_cast<WORD>(value);
    Out(o, n, "reserve ammo type %d = %d (playerstate 0x%08lx +0x%x)", type, value, p, 0x51c + 2 * type);
    return true;
}
void ValHealth(char *o, size_t n) {
    DWORD p = PlayerState();
    float h = 0.0f;
    if (g_healthOk && p && ReadFloats(p + 0x628, &h, 1)) Out(o, n, "%.2f", h); else Out(o, n, "-");
}
bool RunHealth(const char *arg, char *o, size_t n) {
    if (!g_healthOk || !g_experimental) { Out(o, n, "health code not verified / experimental off"); return false; }
    DWORD p = PlayerState();
    if (!p || !InLevel()) { Out(o, n, "needs a level"); return false; }
    float max = reinterpret_cast<MaxHealthFn>(kMaxHealth)();
    float v = arg && arg[0] ? static_cast<float>(atof(arg)) : max;
    if (!(v > 0.0f && v < 100000.0f)) { Out(o, n, "usage: player.health <n > 0> (\"\" = max %.1f)", max); return false; }
    *reinterpret_cast<volatile float *>(p + 0x628) = v;
    Out(o, n, "health %.2f (max %.2f)", v, max);
    return true;
}
void ValInvincible(char *o, size_t n) { Out(o, n, "%d", g_invincible ? 1 : 0); }
bool RunInvincible(const char *arg, char *o, size_t n) {
    if (!g_healthOk || !g_experimental) { Out(o, n, "health code not verified / experimental off"); return false; }
    bool on = BoolArg(arg, g_invincible != 0);
    InterlockedExchange(&g_invincible, on ? 1 : 0);
    Out(o, n, "player.invincible %d (health = MaxHealth every frame; state deaths such as falls still kill)", on ? 1 : 0);
    return true;
}
// game thread, once per game frame (PadHook)
void InvincibleTick() {
    if (!g_invincible || !InLevel()) return;
    DWORD p = PlayerState();
    if (!p) return;
    __try {
        float max = reinterpret_cast<MaxHealthFn>(kMaxHealth)();
        if (max > 0.0f) *reinterpret_cast<volatile float *>(p + 0x628) = max;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
        InterlockedExchange(&g_invincible, 0);
    }
}

// 0.4 (catalog 17.1 / 17.2 / 17.5, static facts, not yet checked live). Weapon slots: WM+4+0x10*slot = handle
// {instance, id} of the right hand, WM+0xC+0x10*slot the left hand, 15 slots (reader 0x6e7b90); a handle is valid when
// [instance+0x44] == handle id (the game's check 0x5b39d0, done here with our own reads); the weapon's object name is
// [[instance+0x10]+0x60] (as the gear callback 0x715ea2 reads it). MaxAmmo 0x6eeae0 cdecl (s8 type) -> u16 (0xffff for
// type > 5). GiveObject 0x555f60 cdecl (owner, objectId, callback, flag) with the save-restore callback 0x715e90, flag 1
// = WM::AddGear (17.1 step 5).
const DWORD kMaxAmmo = 0x006eeae0, kGiveObject = 0x00555f60, kGearCallback = 0x00715e90;
typedef unsigned short(__cdecl *MaxAmmoFn)(int type);
typedef void(__cdecl *GiveObjectFn)(DWORD owner, int objectId, DWORD callback, int flag);
bool g_slotsOk = false, g_maxAmmoOk = false, g_gearOk = false;

DWORD HandleInstance(DWORD handle) {
    DWORD inst = 0, id = 0, check = 0;
    if (!ReadDword(handle, &inst) || !inst || !ReadDword(handle + 4, &id) || !ReadDword(inst + 0x44, &check) || check != id)
        return 0;
    return inst;
}
bool InstanceObjectName(DWORD inst, char *out, size_t size) {
    DWORD object = 0, name = 0;
    out[0] = 0;
    return ReadDword(inst + 0x10, &object) && object && ReadDword(object + 0x60, &name) && name &&
           ReadString(name, out, size);
}
DWORD WeaponManager() {
    DWORD p = PlayerState(), wm = 0;
    if (!p || !InLevel() || !ReadDword(p + 0x500, &wm)) return 0;
    return wm;
}
// fn(slot, left, name) for every filled slot / hand
template <typename F> int ForWeaponSlots(DWORD wm, F fn) {
    int c = 0;
    for (int slot = 0; slot < 15; ++slot)
        for (int left = 0; left < 2; ++left) {
            DWORD inst = HandleInstance(wm + (left ? 0xc : 0x4) + 0x10 * slot);
            if (!inst) continue;
            char name[64];
            if (!InstanceObjectName(inst, name, sizeof(name))) strncpy_s(name, sizeof(name), "?", _TRUNCATE);
            fn(slot, left != 0, name);
            ++c;
        }
    return c;
}
void ValWeaponSlots(char *o, size_t n) {
    DWORD wm = WeaponManager();
    if (!g_slotsOk || !wm) { Out(o, n, g_slotsOk ? "needs a level" : "slot code not verified"); return; }
    DWORD selected = 0;
    ReadDword(wm + 0x138, &selected);
    size_t used = 0;
    o[0] = 0;
    int c = ForWeaponSlots(wm, [&](int slot, bool left, const char *name) {
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%d%s %s", used ? "; " : "", slot, left ? "L" : "", name);
        if (w > 0) used += static_cast<size_t>(w);
    });
    _snprintf_s(o + used, n - used, _TRUNCATE, "%s(%d filled, selected slot %ld, WM 0x%08lx)", c ? " " : "no weapon ", c,
                static_cast<LONG>(selected), wm);
}
bool RunWeaponHas(const char *arg, char *o, size_t n) {
    if (!arg || !arg[0]) { Out(o, n, "usage: weapon.has <object name> (weapon.list / weapon.slots)"); return false; }
    DWORD wm = WeaponManager();
    if (!g_slotsOk || !wm) { Out(o, n, g_slotsOk ? "needs a level" : "slot code not verified"); return false; }
    int found = -1;
    bool foundLeft = false;
    ForWeaponSlots(wm, [&](int slot, bool left, const char *name) {
        if (found < 0 && _stricmp(name, arg) == 0) { found = slot; foundLeft = left; }
    });
    if (found >= 0) Out(o, n, "yes: %s in slot %d%s", arg, found, foundLeft ? " (left hand)" : "");
    else Out(o, n, "no: %s is in none of the 15 slots", arg);
    return true;
}
// game thread: every reserve = MaxAmmo(type) (the clips are not touched)
bool RunAmmoFill(const char *, char *o, size_t n) {
    if (!g_ammoOk || !g_maxAmmoOk || !g_experimental) { Out(o, n, "ammo code not verified / experimental off"); return false; }
    DWORD p = PlayerState();
    if (!p || !InLevel()) { Out(o, n, "needs a level"); return false; }
    WORD v[6] = {};
    __try {
        for (int type = 0; type < 6; ++type) {
            v[type] = reinterpret_cast<MaxAmmoFn>(kMaxAmmo)(type);
            if (v[type] != 0xffff) *reinterpret_cast<volatile WORD *>(p + 0x51c + 2 * type) = v[type];
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
        Out(o, n, "exception in MaxAmmo 0x%08lx", kMaxAmmo);
        return false;
    }
    Out(o, n, "reserve = MaxAmmo per type: %u %u %u %u %u %u (clips unchanged)", v[0], v[1], v[2], v[3], v[4], v[5]);
    return true;
}
// game thread, main state 1: GiveObject(player, id, 0x715e90, 1) -> WM::AddGear (an existing instance of the object
// is taken at once, else the game loads and births it first)
bool RunGearGive(const char *arg, char *o, size_t n) {
    if (!g_gearOk || !g_experimental) { Out(o, n, "gear code not verified / experimental off"); return false; }
    DWORD state = 0, player = 0;
    ReadDword(kMainState, &state);
    if (!InLevel() || state != 1 || !ReadDword(kPlayerPtr, &player) || !player) {
        Out(o, n, "in a level only (main state %lu, needs 1)", state);
        return false;
    }
    if (!arg || !arg[0]) { Out(o, n, "usage: gear.give <object name> (g_binoculars, g_grapple, g_pda, g_healthpack, ...)"); return false; }
    char name[64];
    strncpy_s(name, sizeof(name), arg, _TRUNCATE);
    int id = ObjectId(name);
    if (!id) { Out(o, n, "'%s' is not in the object list", name); return false; }
    __try {
        reinterpret_cast<GiveObjectFn>(kGiveObject)(player, id, kGearCallback, 1);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
        Out(o, n, "exception in GiveObject 0x%08lx", kGiveObject);
        return false;
    }
    Out(o, n, "GiveObject 0x%08lx(player, %d %s, 0x%08lx, 1) done%s", kGiveObject, id, name, kGearCallback,
        _strnicmp(name, "g_", 2) == 0 ? "" : " (not a g_ gear object - check the result)");
    return true;
}

// ---- favourites: [Favorites] Ids in TruMenu.ini (comma list of item ids; empty = kFavDefault) ----
bool ItemUsable(const char *id);         // defined after kItems: id exists and is not a todo item

// calls fn(id) for every usable favourite
template <typename F> void ForFavs(F fn) {
    char copy[sizeof(g_favs)];
    EnterCriticalSection(&g_favLock);
    strncpy_s(copy, sizeof(copy), g_favs, _TRUNCATE);
    LeaveCriticalSection(&g_favLock);
    char *context = nullptr;
    for (char *id = strtok_s(copy, ", ", &context); id; id = strtok_s(nullptr, ", ", &context))
        if (ItemUsable(id)) fn(id);
}
bool FavHas(const char *id) {
    bool found = false;
    ForFavs([&](const char *f) { if (_stricmp(f, id) == 0) found = true; });
    return found;
}
void FavSave() {
    if (g_iniPath[0] && !WritePrivateProfileStringA("Favorites", "Ids", g_favs, g_iniPath))
        Log(1, "favourites: writing %s failed (%lu)", g_iniPath, GetLastError());
}
bool FavSet(const char *id, bool add, char *o, size_t n) {
    if (!id || !id[0] || !ItemUsable(id)) { Out(o, n, "no such item '%s'", id ? id : ""); return false; }
    char rebuilt[sizeof(g_favs)] = "";
    size_t used = 0;
    bool had = false;
    ForFavs([&](const char *f) {
        if (_stricmp(f, id) == 0) { had = true; if (!add) return; }
        int w = _snprintf_s(rebuilt + used, sizeof(rebuilt) - used, _TRUNCATE, "%s%s", used ? "," : "", f);
        if (w > 0) used += static_cast<size_t>(w);
    });
    if (add && !had) _snprintf_s(rebuilt + used, sizeof(rebuilt) - used, _TRUNCATE, "%s%s", used ? "," : "", id);
    EnterCriticalSection(&g_favLock);
    strncpy_s(g_favs, sizeof(g_favs), rebuilt, _TRUNCATE);
    LeaveCriticalSection(&g_favLock);
    FavSave();
    Out(o, n, "fav %s %s (%s)", add ? "add" : "del", id, add ? (had ? "was already in" : "added") : (had ? "removed" : "was not in"));
    return true;
}
void FavToggle(const char *id) {
    char o[160];
    FavSet(id, !FavHas(id), o, sizeof(o));
    _snprintf_s(g_lastAction, sizeof(g_lastAction), _TRUNCATE, "%s", o);
}
void ValFavList(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    ForFavs([&](const char *f) {
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s", used ? " " : "", f);
        if (w > 0) used += static_cast<size_t>(w);
    });
    if (!used) Out(o, n, "-");
}
bool RunFavAdd(const char *arg, char *o, size_t n) { return FavSet(arg, true, o, n); }
bool RunFavDel(const char *arg, char *o, size_t n) { return FavSet(arg, false, o, n); }

bool RunFavReset(const char *, char *o, size_t n) {
    EnterCriticalSection(&g_favLock);
    strncpy_s(g_favs, sizeof(g_favs), kFavDefault, _TRUNCATE);
    LeaveCriticalSection(&g_favLock);
    // empty Ids = the default list (kOpts), so later changes of the default reach this file too
    if (g_iniPath[0]) WritePrivateProfileStringA("Favorites", "Ids", "", g_iniPath);
    Out(o, n, "favourites back to the default list (%s)", kFavDefault);
    return true;
}

// ---- 0.4 TO TEST: a checklist the main session fills over TruLink (menu test.add / test.mark / test.list ...),
// marked in the menu (A ok, X fail, Y skip on the selected row); kept in TruMenu.tests.txt next to tru.exe, one row per
// line: id TAB state TAB hint TAB note TAB time [TAB kind TAB target TAB number] (lines starting with '#' are
// comments; 0.4 files without the last three columns load as checks).
// 0.5 row kinds: "check" (ok / fail / skip / open, as in 0.4), "step" (an ordered instruction, id "step<n>", state
// open / done, optional item to run: target "id" or "id:arg"), "toggle" (a switch, state on / off; target = a TruMenu
// item run with 1 / 0, or "ini:<Plugin>:<Section>:<Key>" written to <Plugin>.ini next to the .asi files) ----
struct TestRow {
    char id[64]; char state[8]; char hint[240]; char note[160]; char when[16];
    char kind[8]; char target[128]; int num;
};
const int kTestMax = 64;
TestRow g_tests[kTestMax];
int g_testCount = 0;
CRITICAL_SECTION g_testLock;
char g_testPath[MAX_PATH] = "";

bool ItemUsable(const char *id);                        // defined after kItems
bool ItemValueText(const char *id, char *o, size_t n);  // defined after kItems: the item's value text
void QueueItem(const char *id, const char *arg);        // defined after kItems: run from the menu, never waits

// tabs / line breaks would break the file and '|' / '{' / '}' the test.list answer
void TestClean(char *s) {
    for (; *s; ++s) {
        if (*s == '\t' || *s == '\r' || *s == '\n') *s = ' ';
        else if (*s == '|') *s = '/';
        else if (*s == '{') *s = '(';
        else if (*s == '}') *s = ')';
    }
}
bool TestStateOk(const char *s) {
    return !_stricmp(s, "open") || !_stricmp(s, "ok") || !_stricmp(s, "fail") || !_stricmp(s, "skip");
}
bool TestIs(const TestRow &t, const char *kind) { return _stricmp(t.kind, kind) == 0; }
// valid states per kind: check open|ok|fail|skip, step open|done, toggle on|off
bool TestStateFits(const char *kind, const char *s) {
    if (!_stricmp(kind, "step")) return !_stricmp(s, "open") || !_stricmp(s, "done");
    if (!_stricmp(kind, "toggle")) return !_stricmp(s, "on") || !_stricmp(s, "off");
    return TestStateOk(s);
}
const char *TestDefaultState(const char *kind) { return !_stricmp(kind, "toggle") ? "off" : "open"; }

// "ini:<Plugin>:<Section>:<Key>" -> path of <Plugin>.ini next to the .asi files, section, key; the plugin name must
// start with "Tru" and hold letters / digits only (no other files are written)
bool TestIniTarget(const char *target, char *path, size_t pathSize, char *section, size_t secSize, char *key,
                   size_t keySize) {
    if (_strnicmp(target, "ini:", 4) != 0) return false;
    char plugin[40] = "";
    const char *p = target + 4;
    const char *c1 = strchr(p, ':');
    const char *c2 = c1 ? strchr(c1 + 1, ':') : nullptr;
    if (!c1 || !c2 || c1 - p < 4 || static_cast<size_t>(c1 - p) >= sizeof(plugin) || c2 - c1 < 2 || !c2[1]) return false;
    memcpy(plugin, p, static_cast<size_t>(c1 - p));
    plugin[c1 - p] = 0;
    if (_strnicmp(plugin, "Tru", 3) != 0) return false;
    for (const char *q = plugin; *q; ++q) if (!isalnum(static_cast<unsigned char>(*q))) return false;
    if (static_cast<size_t>(c2 - c1 - 1) >= secSize) return false;
    memcpy(section, c1 + 1, static_cast<size_t>(c2 - c1 - 1));
    section[c2 - c1 - 1] = 0;
    strncpy_s(key, keySize, c2 + 1, _TRUNCATE);
    for (const char *q = section; *q; ++q) if (!isalnum(static_cast<unsigned char>(*q)) && *q != '_') return false;
    for (const char *q = key; *q; ++q) if (!isalnum(static_cast<unsigned char>(*q)) && *q != '_') return false;
    _snprintf_s(path, pathSize, _TRUNCATE, "%s%s.ini", g_asiDir, plugin);
    return true;
}

// the current state of a toggle: INI value (1 / 0; missing file or key = off) or the item's value text
// ("1" / "on" / "true" ... = on); false when the target cannot be read (state unchanged)
bool TestToggleRead(const char *target, bool *on) {
    char path[MAX_PATH], section[64], key[64];
    if (TestIniTarget(target, path, sizeof(path), section, sizeof(section), key, sizeof(key))) {
        if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) return false;
        *on = GetPrivateProfileIntA(section, key, 0, path) != 0;
        return true;
    }
    if (!_strnicmp(target, "ini:", 4)) return false;
    char value[256] = "";
    if (!ItemValueText(target, value, sizeof(value))) return false;
    const char *v = value;
    while (*v == ' ') ++v;
    if (*v == '1' || !_strnicmp(v, "on", 2) || !_strnicmp(v, "true", 4) || !_strnicmp(v, "yes", 3)) { *on = true; return true; }
    if (*v == '0' || !_strnicmp(v, "off", 3) || !_strnicmp(v, "false", 5) || !_strnicmp(v, "no", 2)) { *on = false; return true; }
    return false;
}

// g_testLock held
void TestSaveLocked() {
    if (!g_testPath[0]) return;
    FILE *f = nullptr;
    if (fopen_s(&f, g_testPath, "wb") != 0 || !f) { Log(1, "tests: cannot write %s", g_testPath); return; }
    fputs("# TruMenu.tests.txt - TO TEST list (TruMenu 0.5): id<TAB>state<TAB>hint<TAB>note<TAB>time<TAB>kind<TAB>target"
          "<TAB>number\r\n", f);
    for (int i = 0; i < g_testCount; ++i) {
        const TestRow &t = g_tests[i];
        fprintf(f, "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%d\r\n", t.id, t.state, t.hint, t.note, t.when, t.kind, t.target, t.num);
    }
    fclose(f);
}

void TestLoad() {
    FILE *f = nullptr;
    if (!g_testPath[0] || fopen_s(&f, g_testPath, "rb") != 0 || !f) return;
    char line[1024];
    EnterCriticalSection(&g_testLock);
    g_testCount = 0;
    while (g_testCount < kTestMax && fgets(line, sizeof(line), f)) {
        size_t len = strlen(line);
        while (len && (line[len - 1] == '\n' || line[len - 1] == '\r')) line[--len] = 0;
        if (!line[0] || line[0] == '#') continue;
        char *field[8] = {line, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr};
        for (int k = 1; k < 8; ++k) {
            char *tab = field[k - 1] ? strchr(field[k - 1], '\t') : nullptr;
            if (!tab) break;
            *tab = 0;
            field[k] = tab + 1;
        }
        if (!field[0][0]) continue;
        TestRow &t = g_tests[g_testCount++];
        memset(&t, 0, sizeof(t));
        const char *kind = field[5] && (!_stricmp(field[5], "step") || !_stricmp(field[5], "toggle")) ? field[5] : "check";
        strncpy_s(t.kind, sizeof(t.kind), kind, _TRUNCATE);
        _strlwr_s(t.kind, sizeof(t.kind));
        strncpy_s(t.id, sizeof(t.id), field[0], _TRUNCATE);
        strncpy_s(t.state, sizeof(t.state), field[1] && TestStateFits(t.kind, field[1]) ? field[1] : TestDefaultState(t.kind),
                  _TRUNCATE);
        _strlwr_s(t.state, sizeof(t.state));
        strncpy_s(t.hint, sizeof(t.hint), field[2] ? field[2] : "", _TRUNCATE);
        strncpy_s(t.note, sizeof(t.note), field[3] ? field[3] : "", _TRUNCATE);
        strncpy_s(t.when, sizeof(t.when), field[4] ? field[4] : "", _TRUNCATE);
        strncpy_s(t.target, sizeof(t.target), field[6] ? field[6] : "", _TRUNCATE);
        t.num = field[7] ? atoi(field[7]) : 0;
    }
    int count = g_testCount;
    LeaveCriticalSection(&g_testLock);
    fclose(f);
    // toggles show the real state of their target (an INI may have been edited between two runs)
    for (int i = 0; i < count; ++i) {
        EnterCriticalSection(&g_testLock);
        char target[128] = "";
        if (i < g_testCount && TestIs(g_tests[i], "toggle")) strncpy_s(target, sizeof(target), g_tests[i].target, _TRUNCATE);
        LeaveCriticalSection(&g_testLock);
        bool on = false;
        if (target[0] && !_strnicmp(target, "ini:", 4) && TestToggleRead(target, &on)) {
            EnterCriticalSection(&g_testLock);
            if (i < g_testCount) strncpy_s(g_tests[i].state, sizeof(g_tests[i].state), on ? "on" : "off", _TRUNCATE);
            LeaveCriticalSection(&g_testLock);
        }
    }
    Log(1, "tests: %d rows from %s", count, g_testPath);
}

// g_testLock held
int TestFindLocked(const char *id) {
    for (int i = 0; i < g_testCount; ++i)
        if (_stricmp(g_tests[i].id, id) == 0) return i;
    return -1;
}

// open / ok / fail / skip count the checks only; total = every row
void TestCounts(int *open, int *ok, int *fail, int *skip, int *total) {
    *open = *ok = *fail = *skip = 0;
    EnterCriticalSection(&g_testLock);
    for (int i = 0; i < g_testCount; ++i) {
        if (!TestIs(g_tests[i], "check")) continue;
        const char *s = g_tests[i].state;
        if (!_stricmp(s, "ok")) ++*ok;
        else if (!_stricmp(s, "fail")) ++*fail;
        else if (!_stricmp(s, "skip")) ++*skip;
        else ++*open;
    }
    *total = g_testCount;
    LeaveCriticalSection(&g_testLock);
}

// splits "<word> <rest>": word (cut to size), rest = after the spaces
const char *TestWord(const char *arg, char *word, size_t size) {
    const char *rest = arg ? arg : "";
    while (*rest == ' ') ++rest;
    size_t len = 0;
    while (rest[len] && rest[len] != ' ' && len + 1 < size) { word[len] = rest[len]; ++len; }
    word[len] = 0;
    rest += len;
    while (*rest && *rest != ' ') ++rest;          // an over-long word is cut
    while (*rest == ' ') ++rest;
    return rest;
}

// g_testLock held: a new row at index at (rows behind it move down); false when the list is full
bool TestInsertLocked(int at) {
    if (g_testCount >= kTestMax) return false;
    for (int k = g_testCount; k > at; --k) g_tests[k] = g_tests[k - 1];
    ++g_testCount;
    memset(&g_tests[at], 0, sizeof(TestRow));
    return true;
}

// "<id> <hint text>": new check row (state open) or new hint for an existing row (state back to open, note cleared)
bool RunTestAdd(const char *arg, char *o, size_t n) {
    char id[64] = "";
    const char *rest = TestWord(arg, id, sizeof(id));
    if (!id[0]) { Out(o, n, "usage: test.add <id> <hint text> (id = a menu item id, id:arg, or any key)"); return false; }
    TestClean(id);
    for (char *p = id; *p; ++p) if (*p == ' ') *p = '_';
    EnterCriticalSection(&g_testLock);
    int i = TestFindLocked(id);
    bool added = i < 0;
    if (added && !TestInsertLocked(g_testCount)) {
        LeaveCriticalSection(&g_testLock);
        Out(o, n, "list full (%d rows) - test.clear or test.del first", kTestMax);
        return false;
    }
    if (added) i = g_testCount - 1;
    TestRow &t = g_tests[i];
    memset(&t, 0, sizeof(t));
    strncpy_s(t.id, sizeof(t.id), id, _TRUNCATE);
    strncpy_s(t.kind, sizeof(t.kind), "check", _TRUNCATE);
    strncpy_s(t.state, sizeof(t.state), "open", _TRUNCATE);
    strncpy_s(t.hint, sizeof(t.hint), rest, _TRUNCATE);
    TestClean(t.hint);
    TestSaveLocked();
    int count = g_testCount;
    LeaveCriticalSection(&g_testLock);
    Out(o, n, "test.add %s (%s, %d rows)", id, added ? "new" : "updated, state open again", count);
    Log(1, "tests: %s", o);
    return true;
}

// 0.5 "<n> <id|-> <text>": step n (1..999, row id "step<n>"); id = the item it runs ("id" or "id:arg", "-" = none).
// A new step goes in front of the first step with a higher number (checks / toggles between steps keep their place);
// an existing step n gets the new item / text and is open again.
bool RunTestStep(const char *arg, char *o, size_t n) {
    char num[16] = "", target[128] = "";
    const char *rest = TestWord(arg, num, sizeof(num));
    rest = TestWord(rest, target, sizeof(target));
    int number = atoi(num);
    if (number < 1 || number > 999 || !target[0]) {
        Out(o, n, "usage: test.step <n 1..999> <item id | id:arg | -> <text>");
        return false;
    }
    if (!strcmp(target, "-")) target[0] = 0;
    TestClean(target);
    char id[16];
    _snprintf_s(id, sizeof(id), _TRUNCATE, "step%d", number);
    EnterCriticalSection(&g_testLock);
    int i = TestFindLocked(id);
    bool added = i < 0;
    if (added) {
        int at = g_testCount;
        for (int k = 0; k < g_testCount; ++k)
            if (TestIs(g_tests[k], "step") && g_tests[k].num > number) { at = k; break; }
        if (!TestInsertLocked(at)) {
            LeaveCriticalSection(&g_testLock);
            Out(o, n, "list full (%d rows) - test.clear or test.del first", kTestMax);
            return false;
        }
        i = at;
    }
    TestRow &t = g_tests[i];
    memset(&t, 0, sizeof(t));
    strncpy_s(t.id, sizeof(t.id), id, _TRUNCATE);
    strncpy_s(t.kind, sizeof(t.kind), "step", _TRUNCATE);
    strncpy_s(t.state, sizeof(t.state), "open", _TRUNCATE);
    strncpy_s(t.target, sizeof(t.target), target, _TRUNCATE);
    strncpy_s(t.hint, sizeof(t.hint), rest, _TRUNCATE);
    TestClean(t.hint);
    t.num = number;
    TestSaveLocked();
    int count = g_testCount;
    LeaveCriticalSection(&g_testLock);
    Out(o, n, "test.step %d %s (%s, %d rows)", number, target[0] ? target : "-", added ? "new" : "updated, open again",
        count);
    Log(1, "tests: %s", o);
    return true;
}

// 0.5 "<id> <target> <text>": a switch row; target = a TruMenu item (run with 1 / 0) or ini:<Plugin>:<Section>:<Key>
bool RunTestToggle(const char *arg, char *o, size_t n) {
    char id[64] = "", target[128] = "";
    const char *rest = TestWord(arg, id, sizeof(id));
    rest = TestWord(rest, target, sizeof(target));
    if (!id[0] || !target[0]) {
        Out(o, n, "usage: test.toggle <id> <item id | ini:<Plugin>:<Section>:<Key>> <text>");
        return false;
    }
    TestClean(id);
    TestClean(target);
    char path[MAX_PATH], section[64], key[64];
    bool isIni = !_strnicmp(target, "ini:", 4);
    if (isIni && !TestIniTarget(target, path, sizeof(path), section, sizeof(section), key, sizeof(key))) {
        Out(o, n, "bad ini target '%s' (ini:<TruPlugin>:<Section>:<Key>, letters / digits / _)", target);
        return false;
    }
    if (!isIni && !ItemUsable(target)) { Out(o, n, "unknown or todo item '%s'", target); return false; }
    bool on = false, known = TestToggleRead(target, &on);
    EnterCriticalSection(&g_testLock);
    int i = TestFindLocked(id);
    bool added = i < 0;
    if (added && !TestInsertLocked(g_testCount)) {
        LeaveCriticalSection(&g_testLock);
        Out(o, n, "list full (%d rows) - test.clear or test.del first", kTestMax);
        return false;
    }
    if (added) i = g_testCount - 1;
    TestRow &t = g_tests[i];
    memset(&t, 0, sizeof(t));
    strncpy_s(t.id, sizeof(t.id), id, _TRUNCATE);
    strncpy_s(t.kind, sizeof(t.kind), "toggle", _TRUNCATE);
    strncpy_s(t.state, sizeof(t.state), on ? "on" : "off", _TRUNCATE);
    strncpy_s(t.target, sizeof(t.target), target, _TRUNCATE);
    strncpy_s(t.hint, sizeof(t.hint), rest, _TRUNCATE);
    TestClean(t.hint);
    if (isIni) strncpy_s(t.note, sizeof(t.note), "INI: takes effect at the next start", _TRUNCATE);
    TestSaveLocked();
    int count = g_testCount;
    LeaveCriticalSection(&g_testLock);
    Out(o, n, "test.toggle %s %s now %s%s (%s, %d rows)", id, target, on ? "on" : "off", known ? "" : " (not readable)",
        added ? "new" : "updated", count);
    Log(1, "tests: %s", o);
    return true;
}

// "" = every row; "done" = only the checks that are marked (steps and toggles stay)
bool RunTestClear(const char *arg, char *o, size_t n) {
    bool doneOnly = arg && _stricmp(arg, "done") == 0;
    if (arg && arg[0] && !doneOnly) { Out(o, n, "usage: test.clear [done]"); return false; }
    EnterCriticalSection(&g_testLock);
    int before = g_testCount, kept = 0;
    for (int i = 0; doneOnly && i < g_testCount; ++i)
        if (!TestIs(g_tests[i], "check") || !_stricmp(g_tests[i].state, "open")) g_tests[kept++] = g_tests[i];
    g_testCount = kept;
    TestSaveLocked();
    LeaveCriticalSection(&g_testLock);
    Out(o, n, "test.clear%s: %d rows removed, %d left", doneOnly ? " done" : "", before - kept, kept);
    Log(1, "tests: %s", o);
    return true;
}

bool RunTestDel(const char *arg, char *o, size_t n) {
    if (!arg || !arg[0]) { Out(o, n, "usage: test.del <id>"); return false; }
    EnterCriticalSection(&g_testLock);
    int i = TestFindLocked(arg);
    if (i >= 0) {
        for (int k = i; k + 1 < g_testCount; ++k) g_tests[k] = g_tests[k + 1];
        --g_testCount;
        TestSaveLocked();
    }
    LeaveCriticalSection(&g_testLock);
    Out(o, n, i >= 0 ? "test.del %s" : "no test row '%s'", arg);
    return i >= 0;
}

// a toggle row switched: INI written at once (the plugins read it at start) or the item run with 1 / 0
bool TestToggleApply(const char *target, bool on, char *o, size_t n) {
    char path[MAX_PATH], section[64], key[64];
    if (TestIniTarget(target, path, sizeof(path), section, sizeof(section), key, sizeof(key))) {
        if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) { Out(o, n, "%s not found - not created", path); return false; }
        if (!WritePrivateProfileStringA(section, key, on ? "1" : "0", path)) {
            Out(o, n, "cannot write %s (%lu)", path, GetLastError());
            return false;
        }
        Out(o, n, "[%s] %s=%d written to %s - takes effect at the next start", section, key, on ? 1 : 0, path);
        return true;
    }
    if (!ItemUsable(target)) { Out(o, n, "unknown or todo item '%s'", target); return false; }
    if (!_stricmp(target, "game.quit")) { Out(o, n, "game.quit is no toggle (owner only, menu)"); return false; }   // 0.7.2
    QueueItem(target, on ? "1" : "0");
    Out(o, n, "%s %d run (%s)", target, on ? 1 : 0, g_lastAction);
    return true;
}

bool TestMark(const char *id, const char *state, const char *note, char *o, size_t n) {
    EnterCriticalSection(&g_testLock);
    int i = TestFindLocked(id);
    if (i < 0) {
        LeaveCriticalSection(&g_testLock);
        Out(o, n, "no test row '%s' (test.list)", id);
        return false;
    }
    if (!TestStateFits(g_tests[i].kind, state)) {
        const char *kind = g_tests[i].kind;
        LeaveCriticalSection(&g_testLock);
        Out(o, n, "%s is a %s row: %s", id, kind, !_stricmp(kind, "step") ? "open|done" : !_stricmp(kind, "toggle")
                                                                            ? "on|off" : "ok|fail|skip|open");
        return false;
    }
    char apply[300] = "";
    if (TestIs(g_tests[i], "toggle")) {
        char target[128];
        strncpy_s(target, sizeof(target), g_tests[i].target, _TRUNCATE);
        LeaveCriticalSection(&g_testLock);          // the INI write / item run happens without the lock
        bool ok = TestToggleApply(target, !_stricmp(state, "on"), apply, sizeof(apply));
        if (!ok) { Out(o, n, "%s", apply); Log(1, "tests: toggle %s: %s", id, apply); return false; }
        EnterCriticalSection(&g_testLock);
        i = TestFindLocked(id);
        if (i < 0) { LeaveCriticalSection(&g_testLock); Out(o, n, "%s (row removed meanwhile)", apply); return true; }
    }
    TestRow &t = g_tests[i];
    strncpy_s(t.state, sizeof(t.state), state, _TRUNCATE);
    _strlwr_s(t.state, sizeof(t.state));
    if (note) { strncpy_s(t.note, sizeof(t.note), note, _TRUNCATE); TestClean(t.note); }
    SYSTEMTIME s;
    GetLocalTime(&s);
    _snprintf_s(t.when, sizeof(t.when), _TRUNCATE, "%02d:%02d:%02d", s.wHour, s.wMinute, s.wSecond);
    TestSaveLocked();
    Out(o, n, "test.mark %s %s%s%s%s%s", t.id, t.state, t.note[0] ? " - " : "", t.note, apply[0] ? "; " : "", apply);
    LeaveCriticalSection(&g_testLock);
    Log(1, "tests: %s", o);
    return true;
}

// "<id> <state> [note]": check ok|fail|skip|open, step done|open, toggle on|off (switches the target)
bool RunTestMark(const char *arg, char *o, size_t n) {
    char id[64] = "", state[16] = "";
    int used = 0;
    if (!arg || sscanf_s(arg, "%63s %15s %n", id, static_cast<unsigned>(sizeof(id)), state,
                         static_cast<unsigned>(sizeof(state)), &used) < 2 ||
        !(TestStateOk(state) || !_stricmp(state, "done") || !_stricmp(state, "on") || !_stricmp(state, "off"))) {
        Out(o, n, "usage: test.mark <id> ok|fail|skip|open [note] (steps: done|open, toggles: on|off)");
        return false;
    }
    const char *note = used > 0 && static_cast<size_t>(used) <= strlen(arg) ? arg + used : "";
    return TestMark(id, state, note[0] ? note : nullptr, o, n);
}

// "<n> rows (o open, k ok, f fail, s skip): id [state] hint {note} | ..." - steps / toggles carry their kind:
// "step3 (step 3 -> level.load:x) [open] text", "sp-states (toggle ini:...) [on] text"
void ValTestList(char *o, size_t n) {
    int open, ok, fail, skip, total;
    TestCounts(&open, &ok, &fail, &skip, &total);
    int used = _snprintf_s(o, n, _TRUNCATE, "%d rows (%d open, %d ok, %d fail, %d skip)%s", total, open, ok, fail, skip,
                           total ? ":" : "");
    if (used < 0) return;
    EnterCriticalSection(&g_testLock);
    for (int i = 0; i < g_testCount; ++i) {
        const TestRow &t = g_tests[i];
        char kind[180] = "";
        if (TestIs(t, "step"))
            _snprintf_s(kind, sizeof(kind), _TRUNCATE, " (step %d%s%s)", t.num, t.target[0] ? " -> " : "", t.target);
        else if (TestIs(t, "toggle"))
            _snprintf_s(kind, sizeof(kind), _TRUNCATE, " (toggle %s)", t.target);
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s %s%s [%s] %s%s%s%s", i ? " |" : "", t.id, kind, t.state,
                            t.hint, t.note[0] ? " {" : "", t.note, t.note[0] ? "}" : "");
        if (w < 0) break;
        used += w;
    }
    LeaveCriticalSection(&g_testLock);
}

// 0.5 test.export: the whole list as a TruLink block (InvokeItem answers it directly):
// "ok+ test.export <n> rows ..." then one line per row "kind<TAB>id<TAB>state<TAB>number<TAB>target<TAB>hint<TAB>note
// <TAB>time", then ".". As a plain value (menu list / status) only the counts.
void ValTestExport(char *o, size_t n) {
    int open, ok, fail, skip, total, steps = 0, done = 0, toggles = 0, on = 0;
    TestCounts(&open, &ok, &fail, &skip, &total);
    EnterCriticalSection(&g_testLock);
    for (int i = 0; i < g_testCount; ++i) {
        if (TestIs(g_tests[i], "step")) { ++steps; if (!_stricmp(g_tests[i].state, "done")) ++done; }
        if (TestIs(g_tests[i], "toggle")) { ++toggles; if (!_stricmp(g_tests[i].state, "on")) ++on; }
    }
    LeaveCriticalSection(&g_testLock);
    _snprintf_s(o, n, _TRUNCATE, "%d rows; checks %d open %d ok %d fail %d skip; steps %d/%d done; toggles %d/%d on",
                total, open, ok, fail, skip, done, steps, on, toggles);
}

void TestExportBlock(char *o, size_t n) {
    char head[200];
    ValTestExport(head, sizeof(head));
    int used = _snprintf_s(o, n, _TRUNCATE, "ok+ test.export %s (kind id state number target hint note time, tab "
                           "separated; file %s)\n", head, g_testPath[0] ? g_testPath : "-");
    if (used < 0) used = 0;
    EnterCriticalSection(&g_testLock);
    for (int i = 0; i < g_testCount; ++i) {
        const TestRow &t = g_tests[i];
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s\t%s\t%s\t%d\t%s\t%s\t%s\t%s\n", t.kind, t.id, t.state,
                            t.num, t.target, t.hint, t.note, t.when);
        if (w < 0) break;
        used += w;
    }
    LeaveCriticalSection(&g_testLock);
    // the block always ends with "." (TruLink adds the final line break); cut rows make room for it
    if (static_cast<size_t>(used) + 2 >= n) used = static_cast<int>(n) - 3;
    _snprintf_s(o + used, n - used, _TRUNCATE, ".");
}

// ---- settings: the kOpts table vs the file ----
void ReadOptions(const char *dir);       // with Start below

// TruMenu.ini as written from the table (= the shipped src/asi/TruMenu/TruMenu.ini)
size_t DefaultIniText(char *out, size_t size) {
    size_t used = 0;
    auto put = [&](const char *fmt, const char *a, const char *b) {
        int w = _snprintf_s(out + used, size - used, _TRUNCATE, fmt, a, b);
        if (w > 0) used += static_cast<size_t>(w);
    };
    put("; %s%s\n", kIniHeader, "");
    const char *section = nullptr;
    for (const OptDef &d : kOpts) {
        if (!section || strcmp(section, d.section) != 0) {
            put(section ? "\n[%s]%s\n" : "[%s]%s\n", d.section, "");
            section = d.section;
        }
        char comment[512];
        strncpy_s(comment, sizeof(comment), d.comment, _TRUNCATE);
        char *context = nullptr;
        for (char *line = strtok_s(comment, "\n", &context); line; line = strtok_s(nullptr, "\n", &context))
            put("; %s%s\n", line, "");
        put("%s=%s\n", d.key, d.def);
    }
    return used;
}

void ValSettings(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    for (const OptDef &d : kOpts) {
        char value[1024];
        GetPrivateProfileStringA(d.section, d.key, "\x01", value, sizeof(value), g_iniPath);
        bool missing = value[0] == '\x01';
        bool changed = !missing && strcmp(value, d.def) != 0;
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s[%s] %s=%s%s", used ? "; " : "", changed ? "* " : "",
                            d.section, d.key, missing ? d.def : value,
                            missing ? " (missing: default)" : changed ? "" : " (default)");
        if (changed && w > 0) {
            used += static_cast<size_t>(w);
            w = _snprintf_s(o + used, n - used, _TRUNCATE, " (default %s)", d.def[0] ? d.def : "\"\"");
        }
        if (w < 0) return;
        used += static_cast<size_t>(w);
    }
}

bool RunSettingsReset(const char *, char *o, size_t n) {
    if (!g_iniPath[0]) { Out(o, n, "no ini path"); return false; }
    SYSTEMTIME t;
    GetLocalTime(&t);
    char backup[MAX_PATH];
    _snprintf_s(backup, sizeof(backup), _TRUNCATE, "%s.bak_%04d%02d%02d_%02d%02d%02d", g_iniPath, t.wYear, t.wMonth, t.wDay,
                t.wHour, t.wMinute, t.wSecond);
    bool hadFile = GetFileAttributesA(g_iniPath) != INVALID_FILE_ATTRIBUTES;
    if (hadFile && !CopyFileA(g_iniPath, backup, TRUE)) {
        Out(o, n, "backup to %s failed (%lu) - nothing changed", backup, GetLastError());
        return false;
    }
    static char text[8192];
    size_t len = DefaultIniText(text, sizeof(text));
    FILE *f = nullptr;
    if (fopen_s(&f, g_iniPath, "wb") != 0 || !f) { Out(o, n, "cannot write %s", g_iniPath); return false; }
    fwrite(text, 1, len, f);
    fclose(f);
    ReadOptions(g_asiDir);
    g_logOverlay = g_logOverlayAtStart ? 1 : 0;
    g_logLines = g_logLinesAtStart;
    Out(o, n, "TruMenu.ini rewritten from the defaults%s%s; options reloaded (Scale / Enabled / Script take effect at the "
        "next start)", hadFile ? ", backup " : "", hadFile ? backup : "");
    Log(1, "settings: %s", o);
    return true;
}
void ValIniPath(char *o, size_t n) { Out(o, n, "%s", g_iniPath[0] ? g_iniPath : "-"); }

// Y (gamepad face up) on the focused widget pins / unpins <id>
void FavKey(const char *id) {
    if (ImGui::IsItemFocused() && ImGui::IsKeyPressed(ImGuiKey_GamepadFaceUp, false)) FavToggle(id);
}

// 0.6 command bar items, defined with the bar below
void ValCmdHistory(char *o, size_t n);
void ValCmdBar(char *o, size_t n);
bool RunCmdFocus(const char *arg, char *o, size_t n);
bool RunCmdRun(const char *arg, char *o, size_t n);
bool RunCmdKeyboard(const char *arg, char *o, size_t n);   // 0.7
void ValGameQuit(char *o, size_t n);                       // 0.7.2
bool RunGameQuit(const char *arg, char *o, size_t n);

struct Item {
    const char *id, *type, *label;
    bool gameThread;                         // runner must run on the game thread (queued)
    void (*value)(char *, size_t);
    bool (*run)(const char *, char *, size_t);
};
const Item kItems[] = {
    {"menu.open", "bool", "menu visible", false, ValMenu, RunMenu},
    {"status.version", "info", "TruMenu version", false, ValVersion, nullptr},
    {"status.hooks", "info", "pad / d3d9 hook state", false, ValHooks, nullptr},
    {"status.unit", "info", "current unit (GameTracker+0x38) and stream unit id", false, ValStatusUnit, nullptr},
    {"status.state", "info", "game state (level change pending / in a level / no player)", false, ValState, nullptr},
    {"status.costume", "info", "current costume, chosen costume words, game-data base, unit default", false, ValCostume,
     nullptr},
    {"status.player", "info", "player instance, object id / name, type record", false, ValPlayerObject, nullptr},
    {"status.plugins", "info", "our ASIs (loaded? version)", false, ValPlugins, nullptr},
    // 0.7.2: render / bar thread (works while the game thread hangs); refused over TruLink (InvokeCore, wait = true)
    {"game.quit", "action", "quit the game now: run twice within 5 s; logs written, then TerminateProcess(exit code "
                            "0x544D); menu / command bar / favourites only, never over TruLink", false, ValGameQuit,
     RunGameQuit},
    {"guard.status", "info", "TruGuard: mode, fault/dump counters, limits, log path", false, ValGuardStatus, nullptr},
    {"guard.count", "info", "TruGuard: exceptions seen in tru.exe / distinct sites", false, ValGuardCount, nullptr},
    {"guard.last", "info", "TruGuard: last fault site (tru offset, access, address, thread)", false, ValGuardLast,
     nullptr},
    {"guard.mode", "int", "TruGuard: 0 = log, 1 = log + dump, 2 = log + dump + resume (0..2)", false, ValGuardMode,
     RunGuardMode},
    {"guard.overlay", "bool", "TruGuard: counters / last fault in the top-right corner", false, ValGuardOverlay,
     RunGuardOverlay},
    {"guard.dump", "action", "TruGuard: full dump + thread snapshot now (arg = reason; also works while hung)", false,
     ValGuardOverlay, RunGuardDump},
    {"overlay.position", "bool", "Lara position overlay", false, ValOverlay, RunOverlay},
    {"player.position", "info", "Lara position / rotation (needs a level)", false, ValPlayer, nullptr},
    {"camera.current", "info", "current camera object", false, ValCamera, nullptr},
    {"camera.mode", "action", "CAMERA_SetMode(arg 0..15), experimental, needs a level", true, ValCamera, RunCameraMode},
    {"camera.restore", "action", "restore the game camera, needs a level", true, ValCamera, RunCameraRestore},
    {"camera.free", "todo", "own free camera - todo: offsets of Camera transform / invTransform not verified", false, ValTodo,
     RunTodo},
    {"cheat.flight", "bool", "cheatMode + message 12 (flight), needs a level", true, ValCheat, RunCheat},
    {"cheat.speed", "float", "flight speed per 30 fps frame (RT up / LT down)", false, ValSpeed, RunSpeed},
    {"draw.markup", "bool", "markup boxes / poly lines projected with the game camera (experimental)", false,
     ValDrawMarkup, RunDrawMarkup},
    {"draw.ledges", "bool", "only ledge-grab markup (flag bit 30), turns draw.markup on", false, ValDrawLedges,
     RunDrawLedges},
    {"draw.scale", "action", "<w> <h> of the projected screen space (default 512 448)", false, ValDrawScale, RunDrawScale},
    {"fav.list", "info", "favourite item ids (Quick access page; [Favorites] Ids)", false, ValFavList, nullptr},
    {"fav.add", "action", "pin <id> to Quick access (also: Y on an item in the menu)", false, ValFavList, RunFavAdd},
    {"fav.del", "action", "unpin <id>", false, ValFavList, RunFavDel},
    {"fav.reset", "action", "favourites back to the default list", false, ValFavList, RunFavReset},
    {"settings.show", "info", "every TruMenu.ini key: current value vs default (* = changed)", false, ValSettings, nullptr},
    {"settings.reset", "action", "back up TruMenu.ini to TruMenu.ini.bak_<time>, rewrite it from the defaults, reload",
     false, ValIniPath, RunSettingsReset},
    {"weapon.list", "info", "weapon object ids (catalog 17.1)", false, ValWeaponList, nullptr},
    {"weapon.give", "action", "WM::GiveWeaponByName 0x7161f0(<name>, 1, 0), main state 1 only, experimental", true,
     ValWeaponList, RunWeaponGive},
    {"ammo.show", "info", "reserve ammo u16 playerstate+0x51c, types 0..5", false, ValAmmo, nullptr},
    {"ammo.set", "action", "<type 0..5> <n>: reserve ammo, experimental", true, ValAmmo, RunAmmoSet},
    {"player.health", "float", "float playerstate+0x628 (\"\" = MaxHealth 0x6e7990), experimental", true, ValHealth,
     RunHealth},
    {"player.invincible", "bool", "health = MaxHealth every game frame (variant A), experimental", false, ValInvincible,
     RunInvincible},
    {"level.current", "info", "unit name at GameTracker+0x38", false, ValUnit, nullptr},
    {"level.list", "info", "all offered units by group (PC unitlist.txt)", false, ValLevelList, nullptr},
    {"level.presets", "info", "preset units ([Levels] List)", false, ValLevels, nullptr},
    {"level.load", "action", "load unit (arg = unit name), experimental", true, ValUnit, RunLevel},
    {"level.reload", "action", "reload the current unit, experimental", true, ValUnit, RunReload},
    // 0.7.1
    {"level.start", "action", "start dlc2 / dlc1 / <unit> as the mission menu does (uigamedata f22 + f27(unit, select, 0, "
                              "1), stdscreenmgr f19 + f7; the intro plays; 0.7.2: select 0 for DLC 2 as the title update, "
                              "[Levels] OutfitRule), main menu only, experimental", true,
     ValLevelStart, RunLevelStart},
    // 0.3: costume.list / costume.set are the live outfit cycle now; the 0.2 "chosen for the next level load" items
    // are costume.records / costume.choose* (costume.setreload / costume.reset keep their 0.2 meaning)
    {"costume.list", "info", "outfit cycle list GlobalInfo [0xe7ee50]+4: object-id name", false, ValGlobalCostumes, nullptr},
    {"costume.records", "info", "player records of the type table: index name object-id (0.2 costume.list)", false,
     ValCostumeList, nullptr},
    {"costume.current", "info", "costume object id [0xe7f1c8] of the last level load", false, ValCostumeCurrent, nullptr},
    {"costume.next", "action", "live: next outfit of the cycle list (0x6f0a90), needs a level", true, ValCostumeCurrent,
     RunCostumeNext},
    {"costume.set", "action", "live: outfit by object name / id now (altPlayerObjectID + 0x6f0a90), needs a level", true,
     ValCostumeCurrent, RunCostumeLive},
    {"costume.choose", "action", "chosen costume (arg = index or name [20c|210]) for the next level load (0.2 costume.set)",
     true, ValCostume, RunCostumeSet},
    {"costume.choosereload", "action", "costume.choose, then reload the current unit", true, ValCostume, RunCostumeSetReload},
    {"costume.choosereset", "action", "chosen costume words +0x20c/+0x20e/+0x210 = 0 (new-game reset)", true, ValCostume,
     RunCostumeReset},
    {"costume.setreload", "action", "= costume.choosereload (0.2 id)", true, ValCostume, RunCostumeSetReload},
    {"costume.reset", "action", "= costume.choosereset (0.2 id)", true, ValCostume, RunCostumeReset},
    {"dev.log", "todo", "engine channel log (stub 0x6457a0) - todo; script prints: log.script", false, ValTodo, RunTodo},
    // 0.3
    {"dev.list", "info", "original developer menu: id type=value (page; row) for every value / action row", false,
     ValDevList, nullptr},
    {"time.scale", "float", "timeDilation 0xe7f1d0 (0..10, \"\" = 1)", false, ValTimeScale, RunTimeScale},
    {"time.pause", "bool", "freeze the world: streamFlags 0xe7f0b8 bit 0x1000", true, ValPause, RunPause},
    {"player.control", "bool", "player control byte 0x8ab4e6 (1 = on)", true, ValControl, RunControl},
    {"player.die", "action", "INSTANCE_Post(player, 4, 3): ragdoll death, needs a level", true, ValPlayer, RunDie},
    {"player.teleport", "action", "Lara to <x> <y> <z>, needs a level", true, ValPlayer, RunTeleport},
    {"player.mark", "action", "remember Lara's position", false, ValMark, RunMark},
    {"player.recall", "action", "Lara back to the mark", true, ValMark, RunRecall},
    {"player.goto", "action", "Lara to an instance (intro id, 0x<address> or #<index>)", true, ValPlayer, RunGoto},
    {"ui.hide", "bool", "hide the HUD (bool 0xcdc9a0)", true, ValUiHide, RunUiHide},
    {"camera.fov", "float", "current camera +0xb0 fov in radians (\"\" = pi/4), needs a level", true, ValFov, RunFov},
    {"instance.list", "action", "instances (arg = name filter): #index intro name address (pos)", false, ValInstCount,
     RunInstanceList},
    {"instance.info", "action", "one instance (intro id, 0x<address> or #<index>)", false, ValInstCount, RunInstanceInfo},
    {"instance.bring", "action", "move an instance to Lara", true, ValInstCount, RunBring},
    {"instance.unhide", "action", "INSTANCE_Post(instance, 7, 0)", true, ValInstCount, RunUnhide},
    {"instance.unhideall", "action", "message 7 to every instance", true, ValInstCount, RunUnhideAll},
    {"instance.remove", "action", "INSTANCE_ReallyRemoveInstance(instance, 0, 0) (not the player)", true, ValInstCount, RunRemove},
    {"log.page", "info", "last log.lines lines (Tru*.log tails + script prints, log.filter)", false, ValLogPage, nullptr},
    {"log.show", "info", "last script print / log lines", false, ValScriptLines, nullptr},
    {"log.script", "bool", "redirect the 8 NsCoreBase print / log natives to the log page", true, ValScriptLog,
     RunScriptLog},
    {"log.overlay", "bool", "log lines in the bottom-left corner", false, ValLogOverlay, RunLogOverlay},
    {"log.lines", "int", "lines on the page / overlay (1..64)", false, ValLogLines, RunLogLines},
    {"log.filter", "action", "only one source (TruLink, TruMenu, script, ...; \"\" / all = every source)", false,
     ValLogFilter, RunLogFilter},
    {"log.clear", "action", "clear the collected lines", false, ValLogCount, RunLogClear},
    // 0.7.2
    {"log.overlaysources", "action", "overlay only: sources shown (comma list: TruMenu,TruGuard,TruShadowPower,TruRockVein,"
                                     "TruLink,script,...; * = all) - [Log] OverlaySources", false, ValOvlSources,
     RunOvlSources},
    {"log.overlayexclude", "action", "overlay only: lines holding one of these substrings are not shown (comma list; "
                                     "none = off) - [Log] OverlayExclude", false, ValOvlExclude, RunOvlExclude},
    {"media.video.list", "info", "Movies\\*.bik next to tru.exe", false, ValVideoList, nullptr},
    {"media.video.play", "action", "0x4a12b0(<name>, 0), front end only (main state 10)", true, ValVideoList, RunVideoPlay},
    {"media.video.menuloop", "action", "main menu background loop [0x8abf20] = <name> (\"\" = medsea_loop)", false,
     ValMenuLoop, RunMenuLoop},
    // 0.4
    {"log.collapse", "bool", "collapse repeated lines (same source + text) into \"text xN (first-last)\"", false,
     ValLogCollapse, RunLogCollapse},
    {"log.hidereads", "bool", "drop TruLink's read / scan / watch / ping echo and menu info reads", false,
     ValLogHideReads, RunLogHideReads},
    {"log.level", "int", "lines shown: 0 all, 1 warnings + errors, 2 errors (also all / warn / error)", false, ValLogLevel,
     RunLogLevel},
    {"log.rate", "int", "max new lines per source and second (0 = no limit)", false, ValLogRate, RunLogRate},
    {"test.list", "info", "TO TEST rows: id [state] hint {note} | ...", false, ValTestList, nullptr},
    {"test.add", "action", "<id> <hint text>: add / update a TO TEST row (id = item id, id:arg or any key)", false,
     ValTestList, RunTestAdd},
    {"test.mark", "action", "<id> ok|fail|skip|open [note] (steps done|open, toggles on|off)", false, ValTestList,
     RunTestMark},
    {"test.del", "action", "<id>: remove one TO TEST row", false, ValTestList, RunTestDel},
    {"test.clear", "action", "remove every TO TEST row (\"done\" = only the marked checks)", false, ValTestList, RunTestClear},
    // 0.5
    {"test.step", "action", "<n> <id|id:arg|-> <text>: numbered step (in order, runs the item with a button)", false,
     ValTestList, RunTestStep},
    {"test.toggle", "action", "<id> <item id|ini:Plugin:Section:Key> <text>: switch row (checkbox)", false, ValTestList,
     RunTestToggle},
    {"test.export", "info", "the whole TO TEST list as a block (kind id state number target hint note time)", false,
     ValTestExport, nullptr},
    {"weapon.slots", "info", "the 15 weapon slots: slot[L] object name (WM+4+0x10*slot), selected slot", false,
     ValWeaponSlots, nullptr},
    {"weapon.has", "action", "<object name>: is it in a weapon slot? (read-only)", false, ValWeaponSlots, RunWeaponHas},
    {"ammo.fill", "action", "every reserve = MaxAmmo(type) 0x6eeae0 (clips unchanged), experimental", true, ValAmmo,
     RunAmmoFill},
    {"gear.give", "action", "GiveObject 0x555f60(player, <name>, 0x715e90, 1) -> AddGear, main state 1, experimental", true,
     ValWeaponSlots, RunGearGive},
    // 0.6
    {"cmd.focus", "action", "open the menu and put the keyboard focus into the command bar", false, ValCmdBar, RunCmdFocus},
    {"cmd.run", "action", "<text>: run a command bar line (\"time.scale 0.5\", \"get ui.hide\", \"list cost\", \"help\")",
     false, ValCmdBar, RunCmdRun},
    {"cmd.history", "info", "command bar history, newest first (TruMenu.history.txt next to tru.exe)", false,
     ValCmdHistory, nullptr},
    // 0.7
    {"cmd.keyboard", "action", "open the menu, focus the command bar and show the on-screen keyboard (as L3)", false,
     ValCmdBar, RunCmdKeyboard},
};

const Item *FindItem(const char *id) {
    if (!id) return nullptr;
    for (const Item &item : kItems)
        if (_stricmp(item.id, id) == 0) return &item;
    return nullptr;
}

bool IsInfoItem(const char *id) {
    const Item *item = FindItem(id);
    return item && strcmp(item->type, "info") == 0;
}

bool ItemUsable(const char *id) {
    const Item *item = FindItem(id);
    if (item) return strcmp(item->type, "todo") != 0;
    return DevFind(id) != nullptr;
}

// 0.5 (TO TEST toggles): the value text of an item or developer-menu row; false if there is none
bool ItemValueText(const char *id, char *o, size_t n) {
    const Item *item = FindItem(id);
    if (item) { item->value(o, n); return true; }
    const DevRow *dev = DevFind(id);
    if (dev) { DevValue(*dev, o, n); return true; }
    return false;
}

void SetLastAction(const char *id, bool ok, const char *text) {
    _snprintf_s(g_lastAction, sizeof(g_lastAction), _TRUNCATE, "%s: %s%s", id, ok ? "" : "err ", text);
    Log(ok ? 2 : 1, "item %s", g_lastAction);
}

// game thread: run the queued request
void RunPending() {
    if (!InterlockedCompareExchange(&g_reqPending, 0, 0)) return;
    EnterCriticalSection(&g_reqLock);
    const Item *item = FindItem(g_reqId);
    char text[1000] = "";
    bool ok = false;
    const DevRow *dev = item ? nullptr : DevFind(g_reqId);
    if (item && item->run) ok = item->run(g_reqArg, text, sizeof(text));
    else if (dev) ok = DevRun(*dev, g_reqArg, text, sizeof(text));
    else _snprintf_s(text, sizeof(text), _TRUNCATE, "unknown item");
    _snprintf_s(g_reqResult, sizeof(g_reqResult), _TRUNCATE, "%s%s", ok ? "ok " : "err ", text);
    SetLastAction(g_reqId, ok, text);
    InterlockedExchange(&g_reqPending, 0);
    LeaveCriticalSection(&g_reqLock);
    SetEvent(g_reqDone);
}

// queue for the game thread; false if another request is still pending
bool Enqueue(const char *id, const char *arg) {
    EnterCriticalSection(&g_reqLock);
    bool busy = g_reqPending != 0;
    if (!busy) {
        strncpy_s(g_reqId, sizeof(g_reqId), id, _TRUNCATE);
        strncpy_s(g_reqArg, sizeof(g_reqArg), arg ? arg : "", _TRUNCATE);
        g_reqResult[0] = 0;
        ResetEvent(g_reqDone);
        InterlockedExchange(&g_reqPending, 1);
    }
    LeaveCriticalSection(&g_reqLock);
    return !busy;
}

// from the menu (render hook): never waits
void QueueItem(const char *id, const char *arg) {
    const Item *item = FindItem(id);
    if (!item && DevFind(id)) {                // developer-menu rows always run on the game thread
        if (!Enqueue(id, arg)) SetLastAction(id, false, "busy (another request pending)");
        else SetLastAction(id, true, "queued");
        return;
    }
    if (!item || !item->run) return;
    if (!item->gameThread) {
        char text[1000];
        bool ok = item->run(arg, text, sizeof(text));
        SetLastAction(id, ok, text);
        return;
    }
    if (!Enqueue(id, arg)) SetLastAction(id, false, "busy (another request pending)");
    else SetLastAction(id, true, "queued");
}

__declspec(thread) char t_answer[49152];
__declspec(thread) char t_value[16384];

const char *CmdRunLine(const char *line, bool wait, const char *source);   // 0.6 command bar, below

// the one item path: TruMenuInvoke (TruLink, wait = true) and the command bar (render hook, wait = false: a game-thread
// item is queued and its result shows up in the bar at the next game frame)
const char *InvokeCore(const char *id, const char *arg, bool wait) {
    const Item *item = FindItem(id);
    const DevRow *dev = item ? nullptr : DevFind(id);
    if (!item && !dev) { _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "err unknown item '%s'", id ? id : ""); return t_answer; }
    const char *itemId = item ? item->id : dev->id;
    if (item && wait && !_stricmp(item->id, "game.quit")) {   // 0.7.2: never automatic - not over TruLink / cmd.run
        Log(1, "game.quit refused: TruLink / cmd.run (only the owner in the menu, the command bar or a favourite)");
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "err game.quit only from the menu, the command bar or a "
                    "favourite (owner) - never over TruLink");
        return t_answer;
    }
    if (item && !_stricmp(item->id, "test.export")) {          // 0.5: a block answer ("ok+ ...", rows, ".")
        TestExportBlock(t_answer, sizeof(t_answer));
        return t_answer;
    }
    if (item && !_stricmp(item->id, "cmd.run"))                // 0.6: the answer of the line's own item
        return CmdRunLine(arg ? arg : "", wait, "TruLink");
    if (item && !item->run) {
        char *value = t_value;
        item->value(value, sizeof(t_value));
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "ok %s %s", item->id, value);
        return t_answer;
    }
    if (dev && (!arg || !arg[0]) && dev->type == kDevInt) {   // an int row without argument: its value
        char value[32];
        DevValue(*dev, value, sizeof(value));
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "ok %s %s (%ld..%ld)", dev->id, value,
                    static_cast<LONG>(dev->p1), static_cast<LONG>(dev->p2));
        return t_answer;
    }
    if (item && !item->gameThread) {
        char *text = t_value;                  // lists (instance.list) can be long
        bool ok = item->run(arg, text, sizeof(t_value));
        SetLastAction(item->id, ok, text);
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "%s%s", ok ? "ok " : "err ", text);
        return t_answer;
    }
    if (!Enqueue(itemId, arg)) {
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "err busy (another request pending)");
        return t_answer;
    }
    if (!wait) {
        SetLastAction(itemId, true, "queued");
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "ok queued %s (runs on the game thread at the next frame)",
                    itemId);
        return t_answer;
    }
    if (WaitForSingleObject(g_reqDone, 3000) == WAIT_OBJECT_0 && !g_reqPending) {
        EnterCriticalSection(&g_reqLock);
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "%s", g_reqResult);
        LeaveCriticalSection(&g_reqLock);
    } else {
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "ok queued %s (no game frame within 3 s - runs at the next "
                    "one)", itemId);
    }
    return t_answer;
}

const char *ListItems() {
    size_t used = 0;
    t_answer[0] = 0;
    for (const Item &item : kItems) {
        char *value = t_value;
        item.value(value, sizeof(t_value));
        int w = _snprintf_s(t_answer + used, sizeof(t_answer) - used, _TRUNCATE, "%s\t%s\t%s\t%s\n", item.id, item.type,
                            value, item.label);
        if (w < 0) break;
        used += static_cast<size_t>(w);
    }
    // the developer menu rows (dev.<slug>), from the tables
    for (int i = 0; g_devOk && i < g_devCount; ++i) {
        const DevRow &d = g_dev[i];
        if (!d.id[0]) continue;
        char value[32], page[64];
        DevValue(d, value, sizeof(value));
        DevPageName(d.page, page, sizeof(page));
        const char *type = d.type == kDevAction ? "action" : d.type == kDevInt ? "int" : "bool";
        int w = _snprintf_s(t_answer + used, sizeof(t_answer) - used, _TRUNCATE, "%s\t%s\t%s\toriginal dev menu: %s / %s "
                            "(row 0x%08lx)\n", d.id, type, value, page, d.text, d.addr);
        if (w < 0) break;
        used += static_cast<size_t>(w);
    }
    return t_answer;
}

const char *InvokeItem(const char *id, const char *arg) { return InvokeCore(id, arg, true); }

// ======================================================================================================================
// 0.6 command bar: one input line under the menu window; "<id> [arg]" as TruLink's "menu <id> [arg]", plus help / list
// / get. Every line runs through InvokeCore (the TruMenuInvoke path) - game-thread items go through the same queue.
// ======================================================================================================================
const int kCmdHistMax = 64, kCmdLine = 256;
CRITICAL_SECTION g_cmdLock;                  // history + last result (render thread, TruLink thread)
char g_cmdHist[kCmdHistMax][kCmdLine];       // oldest first
int g_cmdHistCount = 0;
char g_cmdHistPath[MAX_PATH] = "";
char g_cmdResult[4096] = "";                 // answer of the last line (bar, cmd.run)
char g_cmdResultLine[kCmdLine] = "";         // that line
char g_cmdResultSource[16] = "";             // bar / TruLink / menu
volatile LONG g_cmdFocusReq = 0;             // cmd.focus, F2, Tab, Enter: keyboard focus into the bar next frame
__declspec(thread) int t_cmdDepth = 0;       // cmd.run inside a bar line is refused

enum CmdKind { kCkUnknown, kCkBool, kCkInt, kCkFloat, kCkInfo, kCkAction, kCkTodo, kCkBuiltin };
const char *const kCmdBuiltins[][2] = {
    {"help", "command bar help"}, {"list", "[filter]: matching ids"}, {"get", "<id>: the value of an item"}};
const char *const kCmdHelp =
    "<id> = show the value (bool / int / float / info items) or run an action; <id> <arg> = set / run with arg (time.scale "
    "0.5, costume.set doppelganger_casual, level.load dlc_level2_start, dev.fog_far 9000); get <id>; list [filter]; help. "
    "Keyboard: Tab / Down = suggestions, Enter = run, Up in the empty bar = history, Down / Esc = into the menu, F2 / Tab "
    "= back to the bar. Pad: D-pad / stick / B = into the menu, View = pick mode (D-pad choose, A run / pick, LB / RB "
    "value, B back, Y pin), View in the menu = back to the bar. 0.7: L3 = bar + on-screen keyboard (D-pad / stick move, "
    "A type, X backspace, Y take suggestion, Start run, B close, LB / RB rows).";

CmdKind CmdKindOf(const char *id) {
    for (const auto &b : kCmdBuiltins)
        if (!_stricmp(b[0], id)) return kCkBuiltin;
    const Item *item = FindItem(id);
    if (item) {
        const char *t = item->type;
        if (!strcmp(t, "bool")) return kCkBool;
        if (!strcmp(t, "int")) return kCkInt;
        if (!strcmp(t, "float")) return kCkFloat;
        if (!strcmp(t, "info")) return kCkInfo;
        if (!strcmp(t, "todo")) return kCkTodo;
        return kCkAction;
    }
    const DevRow *dev = DevFind(id);
    if (!dev) return kCkUnknown;
    return dev->type == kDevAction ? kCkAction : dev->type == kDevInt ? kCkInt : kCkBool;
}
bool CmdIsValue(CmdKind k) { return k == kCkBool || k == kCkInt || k == kCkFloat || k == kCkInfo; }

// value text of an item / developer-menu row (int rows with their range); false = no such id
bool CmdValue(const char *id, char *o, size_t n) {
    o[0] = 0;
    const Item *item = FindItem(id);
    if (item) { item->value(o, n); return true; }
    const DevRow *dev = DevFind(id);
    if (!dev) return false;
    char v[48];
    DevValue(*dev, v, sizeof(v));
    if (dev->type == kDevInt) Out(o, n, "%s (%ld..%ld)", v, static_cast<LONG>(dev->p1), static_cast<LONG>(dev->p2));
    else Out(o, n, "%s", v);
    return true;
}
const char *CmdLabel(const char *id) {
    for (const auto &b : kCmdBuiltins)
        if (!_stricmp(b[0], id)) return b[1];
    const Item *item = FindItem(id);
    if (item) return item->label;
    const DevRow *dev = DevFind(id);
    return dev ? dev->text : "";
}
const char *CmdCanonical(const char *id) {   // the table's spelling of an id
    const Item *item = FindItem(id);
    if (item) return item->id;
    const DevRow *dev = DevFind(id);
    return dev ? dev->id : id;
}

// every id the bar knows: built-ins, items (not the todo ones), developer menu rows - pointers stay valid
template <typename F> void CmdForIds(F fn) {
    for (const auto &b : kCmdBuiltins) fn(b[0]);
    for (const Item &item : kItems)
        if (strcmp(item.type, "todo") != 0) fn(item.id);
    for (int i = 0; g_devOk && i < g_devCount; ++i)
        if (g_dev[i].id[0]) fn(static_cast<const char *>(g_dev[i].id));
}

// case-insensitive: 2 = prefix (or empty part), 1 = inside, 0 = no match
int CmdMatch(const char *text, const char *part) {
    if (!part[0]) return 2;
    size_t lt = strlen(text), lp = strlen(part);
    for (size_t i = 0; i + lp <= lt; ++i)
        if (!_strnicmp(text + i, part, lp)) return i == 0 ? 2 : 1;
    return 0;
}

char g_cmdVideos[2048] = "";                 // Movies\*.bik names, refreshed at most every 3 s
DWORD g_cmdVideosTick = 0;

// known argument values of an item: fn(value, note)
template <typename F> void CmdArgValues(const char *id, F fn) {
    if (CmdKindOf(id) == kCkBool) { fn("1", "on"); fn("0", "off"); return; }
    if (!_stricmp(id, "level.load")) {
        for (int i = 0; i < kUnitCount; ++i) fn(kUnits[i].unit, kUnits[i].group);
    } else if (!_stricmp(id, "level.start")) {          // 0.7.1
        fn("dlc2", "dlc_level2_start, intro plays");
        fn("dlc1", "dlc_level1_start, intro plays");
    } else if (!_stricmp(id, "costume.set")) {
        WORD ids[128];
        int c = GlobalCostumes(ids, 128);
        for (int i = 0; i < c; ++i) {
            char name[64];
            if (ObjectName(ids[i], name, sizeof(name))) fn(name, "outfit cycle list");
        }
    } else if (!_stricmp(id, "costume.choose") || !_stricmp(id, "costume.choosereload") ||
               !_stricmp(id, "costume.setreload")) {
        char name[64];
        bool player = false;
        for (int i = 0; TypeRecord(i, name, sizeof(name), &player); ++i)
            if (player) fn(name, "player record (next level load)");
    } else if (!_stricmp(id, "media.video.play") || !_stricmp(id, "media.video.menuloop")) {
        DWORD now = GetTickCount();
        if (!g_cmdVideosTick || now - g_cmdVideosTick > 3000) {
            ValVideoList(g_cmdVideos, sizeof(g_cmdVideos));
            g_cmdVideosTick = now;
        }
        if (!strncmp(g_cmdVideos, "no ", 3)) return;
        char copy[sizeof(g_cmdVideos)];
        strncpy_s(copy, sizeof(copy), g_cmdVideos, _TRUNCATE);
        char *context = nullptr;
        for (char *v = strtok_s(copy, " ", &context); v; v = strtok_s(nullptr, " ", &context)) fn(v, "Movies\\*.bik");
    } else if (!_stricmp(id, "weapon.give") || !_stricmp(id, "weapon.has")) {
        for (const WeaponName &w : kWeapons) fn(w.name, "weapon object");
    } else if (!_stricmp(id, "guard.mode")) {
        fn("0", "log"); fn("1", "log + dump"); fn("2", "log + dump + resume");
    } else if (!_stricmp(id, "log.level")) {
        fn("0", "all lines"); fn("1", "warnings + errors"); fn("2", "errors only");
    } else if (!_stricmp(id, "fav.del")) {
        ForFavs([&](const char *f) { fn(f, "favourite"); });
    }
}
bool CmdArgsAreIds(const char *id) { return !_stricmp(id, "get") || !_stricmp(id, "fav.add"); }
bool CmdHasArgValues(const char *id) {
    if (CmdArgsAreIds(id)) return true;
    int count = 0;
    CmdArgValues(id, [&](const char *, const char *) { ++count; });
    return count > 0;
}

// ---- history (TruMenu.history.txt next to tru.exe, oldest first) ----
void CmdClean(const char *in, char *out, size_t size) {   // tabs / line breaks -> spaces, trimmed
    while (*in == ' ' || *in == '\t' || *in == '\r' || *in == '\n') ++in;
    size_t i = 0;
    for (; *in && i + 1 < size; ++in) out[i++] = (*in == '\t' || *in == '\r' || *in == '\n') ? ' ' : *in;
    while (i && out[i - 1] == ' ') --i;
    out[i] = 0;
}
void CmdHistSaveLocked() {
    if (!g_cmdHistPath[0]) return;
    FILE *f = nullptr;
    if (fopen_s(&f, g_cmdHistPath, "wb") != 0 || !f) return;
    fputs("# TruMenu command bar history, oldest first ([Cmd] HistorySize in TruMenu.ini)\r\n", f);
    for (int i = 0; i < g_cmdHistCount; ++i) fprintf(f, "%s\r\n", g_cmdHist[i]);
    fclose(f);
}
void CmdHistAddLocked(const char *text) {
    if (!text[0]) return;
    for (int i = 0; i < g_cmdHistCount; ++i) {   // an older identical line moves to the end
        if (strcmp(g_cmdHist[i], text) != 0) continue;
        memmove(g_cmdHist[i], g_cmdHist[i + 1], static_cast<size_t>(g_cmdHistCount - i - 1) * kCmdLine);
        --g_cmdHistCount;
        break;
    }
    while (g_cmdHistCount >= g_cmdHistSize && g_cmdHistCount > 0) {
        memmove(g_cmdHist[0], g_cmdHist[1], static_cast<size_t>(g_cmdHistCount - 1) * kCmdLine);
        --g_cmdHistCount;
    }
    strncpy_s(g_cmdHist[g_cmdHistCount++], kCmdLine, text, _TRUNCATE);
}

// ---- 0.7.2 game.quit (owner wish 2026-11-02: the game showed only black, TruMenu still worked) ----
// Safety step: the first run arms it, a second run 0.3 .. 5 s later quits. Runs on the calling thread (render hook /
// command bar - not the game thread, which may hang). TerminateProcess, not ExitProcess: no DLL detach / atexit that
// could block on a hung thread. Never automatic: InvokeCore refuses it over TruLink, nothing in TruMenu queues it.
const UINT kQuitExitCode = 0x544D;          // "TM"; Invoke-TruTestRun.ps1 maps 21581 to "ended via TruMenu game.quit"
const DWORD kQuitWindowMs = 5000, kQuitMinGapMs = 300;
volatile LONG g_quitArmedAt = 0;             // GetTickCount of the first run, 0 = not armed

bool QuitArmed(DWORD *leftMs) {
    DWORD at = static_cast<DWORD>(g_quitArmedAt), age = GetTickCount() - at;
    bool armed = at != 0 && age <= kQuitWindowMs;
    if (leftMs) *leftMs = armed ? kQuitWindowMs - age : 0;
    return armed;
}
void ValGameQuit(char *o, size_t n) {
    DWORD left = 0;
    if (QuitArmed(&left)) Out(o, n, "ARMED - run again within %lu ms to quit", left);
    else Out(o, n, "not armed (run twice within 5 s)");
}
DWORD QuitNow() {                            // returns only when TerminateProcess failed (its error)
    Log(0, "game.quit by the owner (TruMenu) - logs flushed next, then TerminateProcess(GetCurrentProcess(), 0x%x)",
        kQuitExitCode);
    // TO TEST rows and the history are written on every change already; once more, without waiting for a lock a
    // hung thread may hold, and only when there is something to write
    if (g_testCount > 0 && TryEnterCriticalSection(&g_testLock)) { TestSaveLocked(); LeaveCriticalSection(&g_testLock); }
    if (g_cmdHistCount > 0 && TryEnterCriticalSection(&g_cmdLock)) { CmdHistSaveLocked(); LeaveCriticalSection(&g_cmdLock); }
    _flushall();
    // TruMenu.log is opened / closed per line; commit it to the disk as well
    HANDLE h = CreateFileA(g_logPath, GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                           OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h != INVALID_HANDLE_VALUE) {
        FlushFileBuffers(h);
        CloseHandle(h);
    }
    // on success TerminateProcess on the own process does not return
    TerminateProcess(GetCurrentProcess(), kQuitExitCode);
    DWORD error = GetLastError();
    Log(0, "game.quit: TerminateProcess failed (%lu) - the game keeps running", error);
    return error;
}
bool RunGameQuit(const char *, char *o, size_t n) {
    DWORD now = GetTickCount(), at = static_cast<DWORD>(g_quitArmedAt), age = now - at;
    if (!at || age > kQuitWindowMs) {
        InterlockedExchange(&g_quitArmedAt, static_cast<LONG>(now ? now : 1));
        Log(1, "game.quit armed by the owner - run it again within 5 s to end the game");
        Out(o, n, "armed - run game.quit again within 5 s to end the game (TerminateProcess, exit code 0x544D)");
        return true;
    }
    if (age < kQuitMinGapMs) {
        Out(o, n, "armed - second press too fast (%lu ms), press again", age);
        return true;
    }
    InterlockedExchange(&g_quitArmedAt, 0);
    DWORD error = QuitNow();
    Out(o, n, "TerminateProcess failed (%lu) - see TruMenu.log", error);
    return false;
}

void CmdHistLoad() {
    FILE *f = nullptr;
    if (fopen_s(&f, g_cmdHistPath, "rb") != 0 || !f) return;
    char line[512], clean[kCmdLine];
    EnterCriticalSection(&g_cmdLock);
    while (fgets(line, sizeof(line), f)) {
        CmdClean(line, clean, sizeof(clean));
        if (clean[0] && clean[0] != '#') CmdHistAddLocked(clean);
    }
    int count = g_cmdHistCount;
    LeaveCriticalSection(&g_cmdLock);
    fclose(f);
    Log(1, "cmd: %d history lines from %s", count, g_cmdHistPath);
}

// ---- execution ----
// one line -> answer in t_answer ("ok ..." / "err ..."); wait = may wait for the game thread (TruLink's thread)
const char *CmdExecute(const char *line, bool wait) {
    char word[64] = "", arg[kCmdLine] = "";
    size_t w = 0;
    while (line[w] && line[w] != ' ') ++w;
    if (!w) { Out(t_answer, sizeof(t_answer), "err empty line (help = the commands)"); return t_answer; }
    if (w >= sizeof(word)) { Out(t_answer, sizeof(t_answer), "err id too long"); return t_answer; }
    memcpy(word, line, w);
    word[w] = 0;
    const char *a = line + w;
    while (*a == ' ') ++a;
    strncpy_s(arg, sizeof(arg), a, _TRUNCATE);
    if (!_stricmp(word, "help")) { Out(t_answer, sizeof(t_answer), "ok %s", kCmdHelp); return t_answer; }
    if (!_stricmp(word, "list")) {
        int count = 0, total = 0;
        size_t used = 0;
        t_value[0] = 0;
        CmdForIds([&](const char *id) {
            ++total;
            if (!CmdMatch(id, arg)) return;
            ++count;
            int n = _snprintf_s(t_value + used, sizeof(t_value) - used, _TRUNCATE, "%s%s", used ? " " : "", id);
            if (n > 0) used += static_cast<size_t>(n);
        });
        Out(t_answer, sizeof(t_answer), "ok list: %d of %d ids%s%s: %s", count, total, arg[0] ? " matching " : "", arg,
            t_value);
        return t_answer;
    }
    if (!_stricmp(word, "get")) {
        char id[64];
        size_t i = 0;
        for (; arg[i] && arg[i] != ' ' && i + 1 < sizeof(id); ++i) id[i] = arg[i];
        id[i] = 0;
        if (!id[0]) { Out(t_answer, sizeof(t_answer), "err get <id>"); return t_answer; }
        if (!CmdValue(id, t_value, sizeof(t_value))) {
            Out(t_answer, sizeof(t_answer), "err unknown item '%s'", id);
            return t_answer;
        }
        Out(t_answer, sizeof(t_answer), "ok %s = %s", CmdCanonical(id), t_value);
        return t_answer;
    }
    if (!_stricmp(word, "cmd.run")) {
        Out(t_answer, sizeof(t_answer), "err cmd.run is for TruLink - type the line itself");
        return t_answer;
    }
    CmdKind kind = CmdKindOf(word);
    if (kind == kCkUnknown) {
        const char *near1 = nullptr;
        for (int pass = 2; pass >= 1 && !near1; --pass)
            CmdForIds([&](const char *id) { if (!near1 && CmdMatch(id, word) == pass) near1 = id; });
        Out(t_answer, sizeof(t_answer), "err unknown item '%s'%s%s%s", word, near1 ? " - did you mean " : "",
            near1 ? near1 : "", near1 ? "?" : "");
        return t_answer;
    }
    if (!arg[0] && CmdIsValue(kind)) {           // "<id>" alone on a value item: its value (owner's rule)
        CmdValue(word, t_value, sizeof(t_value));
        Out(t_answer, sizeof(t_answer), "ok %s = %s", CmdCanonical(word), t_value);
        return t_answer;
    }
    return InvokeCore(word, arg, wait);
}

// cleans the line, runs it, keeps it in the history and as the bar's result line
const char *CmdRunLine(const char *line, bool wait, const char *source) {
    char clean[kCmdLine];
    CmdClean(line ? line : "", clean, sizeof(clean));
    if (t_cmdDepth) { Out(t_answer, sizeof(t_answer), "err cmd.run inside a command line"); return t_answer; }
    ++t_cmdDepth;
    const char *answer = CmdExecute(clean, wait);
    --t_cmdDepth;
    EnterCriticalSection(&g_cmdLock);
    if (clean[0]) {
        CmdHistAddLocked(clean);
        CmdHistSaveLocked();
    }
    strncpy_s(g_cmdResult, sizeof(g_cmdResult), answer, _TRUNCATE);
    strncpy_s(g_cmdResultLine, sizeof(g_cmdResultLine), clean, _TRUNCATE);
    strncpy_s(g_cmdResultSource, sizeof(g_cmdResultSource), source, _TRUNCATE);
    LeaveCriticalSection(&g_cmdLock);
    Log(2, "cmd (%s): %s -> %.200s", source, clean, answer);
    return answer;
}

void ValCmdHistory(char *o, size_t n) {
    EnterCriticalSection(&g_cmdLock);
    int used = _snprintf_s(o, n, _TRUNCATE, "%d:", g_cmdHistCount);
    for (int i = g_cmdHistCount - 1; i >= 0 && used > 0; --i) {
        int w = _snprintf_s(o + used, n - static_cast<size_t>(used), _TRUNCATE, "%s %s",
                            i == g_cmdHistCount - 1 ? "" : ";", g_cmdHist[i]);
        if (w < 0) break;
        used += w;
    }
    LeaveCriticalSection(&g_cmdLock);
}
void ValCmdBar(char *o, size_t n) {
    EnterCriticalSection(&g_cmdLock);
    Out(o, n, "bar %s, %d history lines; last (%s): %s -> %.160s", g_cmdEnabled ? "on" : "off ([Cmd] Enabled=0)",
        g_cmdHistCount, g_cmdResultSource[0] ? g_cmdResultSource : "-", g_cmdResultLine[0] ? g_cmdResultLine : "-",
        g_cmdResult[0] ? g_cmdResult : "-");
    LeaveCriticalSection(&g_cmdLock);
}
bool RunCmdFocus(const char *, char *o, size_t n) {
    if (!g_cmdEnabled) { Out(o, n, "command bar off ([Cmd] Enabled=0)"); return false; }
    if (!g_menuOpen) ToggleMenu("cmd.focus");
    InterlockedExchange(&g_cmdFocusReq, 1);
    Out(o, n, "command bar focused");
    return true;
}
bool RunCmdKeyboard(const char *, char *o, size_t n) {   // 0.7
    if (!g_cmdEnabled) { Out(o, n, "command bar off ([Cmd] Enabled=0)"); return false; }
    if (!g_cmdKeyboard) { Out(o, n, "on-screen keyboard off ([Cmd] Keyboard=0)"); return false; }
    if (!g_menuOpen) ToggleMenu("cmd.keyboard");
    InterlockedExchange(&g_cmdOskReq, 2);
    Out(o, n, "command bar focused, on-screen keyboard open");
    return true;
}
// only reached through the menu (a favourite button) - TruLink's cmd.run is answered by InvokeCore itself
bool RunCmdRun(const char *arg, char *o, size_t n) {
    const char *answer = CmdRunLine(arg, false, "menu");
    bool ok = !strncmp(answer, "ok", 2);
    const char *text = answer + (ok ? 2 : 3);
    while (*text == ' ' || *text == '+') ++text;
    Out(o, n, "%s", text);
    return ok;
}

// ---- the bar (render thread only below) ----
struct CmdSug {
    char text[kCmdLine];                     // id (id token) or the whole line "<id> <value>"
    char show[72];
    char note[96];
    const char *valueId;                     // id whose value is shown, nullptr = none
    bool idToken;                            // completes the id word
};
const int kSugMax = 400;
CmdSug g_sug[kSugMax];
int g_sugCount = 0, g_sugSel = -1;
char g_sugFor[kCmdLine] = "\x01";
bool g_sugAll = false;
DWORD g_sugTick = 0;

char g_cmdBuf[kCmdLine] = "";
char g_cmdSetText[kCmdLine] = "";
bool g_cmdSetPending = false;                // text for the active field, applied in the callback
int g_cmdHistPos = -1;                       // browsing the history (index), -1 = typing
bool g_cmdLeaveReq = false;                  // Up / Down with nothing to choose: focus into the menu
bool g_cmdPadMode = false;                   // pad picker: D-pad scrolls the suggestions, A runs / picks
bool g_cmdTextActive = false;                // the text field was active last frame
int g_pickMode = 0;                          // 0 list, 1 value picker (+/-)
char g_pickId[64] = "";
double g_pickValue = 0, g_pickStep = 1, g_pickMin = 0, g_pickMax = 0;
bool g_pickRange = false, g_pickInt = false;
char g_cmdWaitId[64] = "";                   // queued game-thread item whose answer is still to come
DWORD g_cmdWaitTick = 0;
WORD g_cmdRepeatMask = 0;
DWORD g_cmdRepeatAt = 0;
float g_cmdBarHeight = 0.0f;
ImVec2 g_menuPos, g_menuSize;
bool g_menuRectOk = false;
const char *const kMenuTitle = "TruMenu  (L3 + R3 closes)";

void CmdSugAdd(const char *text, const char *show, const char *note, const char *valueId, bool idToken) {
    if (g_sugCount >= kSugMax) return;
    CmdSug &s = g_sug[g_sugCount++];
    strncpy_s(s.text, sizeof(s.text), text, _TRUNCATE);
    strncpy_s(s.show, sizeof(s.show), show, _TRUNCATE);
    strncpy_s(s.note, sizeof(s.note), note ? note : "", _TRUNCATE);
    s.valueId = valueId;
    s.idToken = idToken;
}

// suggestions for the line: ids (prefix matches first, then inside), or argument values after "<id> "
void CmdBuildSuggestions(const char *line, bool all) {
    DWORD now = GetTickCount();
    bool changed = strcmp(g_sugFor, line) != 0 || all != g_sugAll;
    if (!changed && now - g_sugTick < 1000) return;
    strncpy_s(g_sugFor, sizeof(g_sugFor), line, _TRUNCATE);
    g_sugAll = all;
    g_sugTick = now;
    g_sugCount = 0;
    while (*line == ' ') ++line;
    const char *space = strchr(line, ' ');
    if (!space) {
        if (line[0] || all)
            for (int pass = 2; pass >= 1; --pass)
                CmdForIds([&](const char *id) { if (CmdMatch(id, line) == pass) CmdSugAdd(id, id, CmdLabel(id), id, true); });
    } else {
        char word[64];
        size_t w = static_cast<size_t>(space - line);
        if (w < sizeof(word)) {
            memcpy(word, line, w);
            word[w] = 0;
            const char *arg = space;
            while (*arg == ' ') ++arg;
            if (!strchr(arg, ' ')) {                 // one argument word only
                for (int pass = 2; pass >= 1; --pass) {
                    if (CmdArgsAreIds(word)) {
                        CmdForIds([&](const char *id) {
                            if (CmdKindOf(id) == kCkBuiltin || CmdMatch(id, arg) != pass) return;
                            char text[kCmdLine];
                            Out(text, sizeof(text), "%s %s", word, id);
                            CmdSugAdd(text, id, CmdLabel(id), id, false);
                        });
                    } else {
                        CmdArgValues(word, [&](const char *v, const char *note) {
                            if (CmdMatch(v, arg) != pass) return;
                            char text[kCmdLine];
                            Out(text, sizeof(text), "%s %s", word, v);
                            CmdSugAdd(text, v, note, nullptr, false);
                        });
                    }
                }
            }
        }
    }
    if (changed) g_sugSel = all && g_sugCount ? 0 : -1;
    if (g_sugSel >= g_sugCount) g_sugSel = g_sugCount - 1;
}

// the text a suggestion puts into the field (Tab: with a space when the id takes an argument)
void CmdCompletionText(int i, char *out, size_t size, bool forTab) {
    const CmdSug &s = g_sug[i];
    if (!s.idToken) { Out(out, size, "%s", s.text); return; }
    CmdKind k = CmdKindOf(s.text);
    bool space = forTab && (k == kCkBuiltin ? _stricmp(s.text, "help") != 0 : (k != kCkInfo && k != kCkTodo));
    Out(out, size, "%s%s", s.text, space ? " " : "");
}

// values in the suggestion list: cached for 500 ms (some value functions read files)
struct CmdValCache { const char *id; DWORD tick; char value[100]; };
CmdValCache g_valCache[24];
int g_valNext = 0;
const char *CmdCachedValue(const char *id) {
    DWORD now = GetTickCount();
    CmdValCache *slot = nullptr;
    for (CmdValCache &c : g_valCache)
        if (c.id == id) { if (now - c.tick < 500) return c.value; slot = &c; }
    if (!slot) { slot = &g_valCache[g_valNext]; g_valNext = (g_valNext + 1) % 24; }
    char v[2048];
    if (CmdKindOf(id) == kCkBuiltin || !CmdValue(id, v, sizeof(v))) v[0] = 0;
    CmdClean(v, slot->value, sizeof(slot->value));
    slot->id = id;
    slot->tick = now;
    return slot->value;
}

void CmdReplace(ImGuiInputTextCallbackData *d, const char *text) {
    d->DeleteChars(0, d->BufTextLen);
    d->InsertChars(0, text);
    d->CursorPos = d->SelectionStart = d->SelectionEnd = d->BufTextLen;
}

int CmdCallback(ImGuiInputTextCallbackData *d) {
    switch (d->EventFlag) {
    case ImGuiInputTextFlags_CallbackAlways:
        if (g_cmdSetPending) { g_cmdSetPending = false; CmdReplace(d, g_cmdSetText); }
        break;
    case ImGuiInputTextFlags_CallbackEdit:
        g_cmdHistPos = -1;
        g_sugSel = -1;
        break;
    case ImGuiInputTextFlags_CallbackCompletion:
        if (g_sugCount) {
            char text[kCmdLine];
            CmdCompletionText(g_sugSel >= 0 ? g_sugSel : 0, text, sizeof(text), true);
            CmdReplace(d, text);
            g_sugSel = -1;
            g_cmdHistPos = -1;
        }
        break;
    case ImGuiInputTextFlags_CallbackHistory: {
        bool up = d->EventKey == ImGuiKey_UpArrow;
        char entry[kCmdLine] = "";
        bool load = false;
        int pos = g_cmdHistPos;
        EnterCriticalSection(&g_cmdLock);
        int count = g_cmdHistCount;
        if (pos >= count) pos = count - 1;
        if (pos >= 0) {                              // browsing: Up older, Down newer / back to an empty line
            if (up) { if (pos > 0) --pos; }
            else if (++pos >= count) pos = -1;
            load = true;
        } else if (d->BufTextLen == 0) {
            // 0.7 [Cmd] UpOpensHistory=0: Up goes into the menu like Down, Ctrl + Up still opens the history
            bool history = g_cmdUpHistory || ImGui::GetIO().KeyCtrl;
            if (up && count && history) { pos = count - 1; load = true; }
            else g_cmdLeaveReq = true;               // Down (or no history): into the menu
        } else if (g_sugCount) {
            if (up) { if (g_sugSel >= 0) --g_sugSel; }
            else if (g_sugSel < g_sugCount - 1) ++g_sugSel;
        } else {
            g_cmdLeaveReq = true;                    // nothing to choose: into the menu
        }
        if (load && pos >= 0) strncpy_s(entry, sizeof(entry), g_cmdHist[pos], _TRUNCATE);
        LeaveCriticalSection(&g_cmdLock);
        if (load) { g_cmdHistPos = pos; CmdReplace(d, entry); }
        break;
    }
    default:
        break;
    }
    return 0;
}

// a queued game-thread item: its answer shows up in the bar when the game thread has run it
void CmdNoteQueued(const char *answer, const char *line) {
    if (strncmp(answer, "ok queued ", 10) != 0) return;
    char word[64];
    size_t w = 0;
    while (line[w] && line[w] != ' ' && w + 1 < sizeof(word)) { word[w] = line[w]; ++w; }
    word[w] = 0;
    strncpy_s(g_cmdWaitId, sizeof(g_cmdWaitId), CmdCanonical(word), _TRUNCATE);
    g_cmdWaitTick = GetTickCount();
}
void CmdPollQueued() {
    if (!g_cmdWaitId[0]) return;
    if (g_reqPending) {
        if (GetTickCount() - g_cmdWaitTick > 5000) g_cmdWaitId[0] = 0;
        return;
    }
    char result[sizeof(g_reqResult)] = "";
    EnterCriticalSection(&g_reqLock);
    if (!_stricmp(g_reqId, g_cmdWaitId)) strncpy_s(result, sizeof(result), g_reqResult, _TRUNCATE);
    LeaveCriticalSection(&g_reqLock);
    g_cmdWaitId[0] = 0;
    if (!result[0]) return;
    EnterCriticalSection(&g_cmdLock);
    strncpy_s(g_cmdResult, sizeof(g_cmdResult), result, _TRUNCATE);
    LeaveCriticalSection(&g_cmdLock);
}

void CmdRunFromBar(const char *line) {
    char copy[kCmdLine];
    strncpy_s(copy, sizeof(copy), line, _TRUNCATE);
    const char *answer = CmdRunLine(copy, false, "bar");
    CmdNoteQueued(answer, copy);
}

void CmdFocusMenu() {
    ImGui::SetWindowFocus(kMenuTitle);
    ImGui::SetNavCursorVisible(true);
    g_cmdPadMode = false;
    g_pickMode = 0;
}

// pad: an edge, or the auto-repeat while the button stays held
bool CmdPadPress(WORD mask) {
    DWORD now = GetTickCount();
    if (g_cmdPadEdges & mask) { g_cmdRepeatMask = mask; g_cmdRepeatAt = now + 350; return true; }
    if ((g_cmdPadHeld & mask) && g_cmdRepeatMask == mask && static_cast<LONG>(now - g_cmdRepeatAt) >= 0) {
        g_cmdRepeatAt = now + 60;
        return true;
    }
    return false;
}

void CmdPickValueStart(const char *id) {
    CmdKind k = CmdKindOf(id);
    char v[256];
    CmdValue(id, v, sizeof(v));
    strncpy_s(g_pickId, sizeof(g_pickId), CmdCanonical(id), _TRUNCATE);
    g_pickValue = atof(v);
    g_pickInt = k == kCkInt;
    g_pickStep = g_pickInt ? 1.0 : 0.1;
    g_pickRange = false;
    struct { const char *id; double step, lo, hi; } const steps[] = {
        {"time.scale", 0.1, 0.0, 10.0}, {"camera.fov", 0.05, 0.05, 3.1}, {"cheat.speed", 1.0, 1.0, 999.0},
        {"player.health", 10.0, 0.0, 100000.0}, {"log.lines", 1.0, 1.0, 64.0}, {"log.rate", 5.0, 0.0, 10000.0},
        {"guard.mode", 1.0, 0.0, 2.0}, {"log.level", 1.0, 0.0, 2.0}};
    for (const auto &s : steps)
        if (!_stricmp(s.id, g_pickId)) { g_pickStep = s.step; g_pickMin = s.lo; g_pickMax = s.hi; g_pickRange = true; }
    const DevRow *dev = FindItem(id) ? nullptr : DevFind(id);
    if (dev) {
        g_pickRange = true;
        g_pickMin = static_cast<double>(static_cast<LONG>(dev->p1));
        g_pickMax = static_cast<double>(static_cast<LONG>(dev->p2));
        double range = g_pickMax - g_pickMin;
        g_pickStep = range > 255.0 ? floor(range / 64.0) : 1.0;
    }
    g_pickMode = 1;
}
void CmdPickValueText(char *o, size_t n) {
    if (g_pickInt) Out(o, n, "%d", static_cast<int>(g_pickValue < 0 ? g_pickValue - 0.5 : g_pickValue + 0.5));
    else Out(o, n, "%.4g", g_pickValue);
}

// A on suggestion i in the pad picker
void CmdPadChoose(int i) {
    const CmdSug &s = g_sug[i];
    if (!s.idToken) { CmdRunFromBar(s.text); return; }   // an argument value: run "<id> <value>"
    const char *id = s.text;
    CmdKind k = CmdKindOf(id);
    char line[kCmdLine];
    if (k == kCkBuiltin) {
        if (!_stricmp(id, "get")) { Out(g_cmdBuf, sizeof(g_cmdBuf), "get "); return; }
        CmdRunFromBar(id);
    } else if (k == kCkBool) {                       // a toggle: no argument asked, the other state
        char v[64];
        CmdValue(id, v, sizeof(v));
        Out(line, sizeof(line), "%s %s", id, v[0] == '1' ? "0" : "1");
        CmdRunFromBar(line);
    } else if (CmdHasArgValues(id)) {                // a list: the values become the suggestions
        Out(g_cmdBuf, sizeof(g_cmdBuf), "%s ", id);
    } else if (k == kCkInt || k == kCkFloat) {
        CmdPickValueStart(id);
    } else {
        CmdRunFromBar(id);                           // action (no argument) / info (value)
    }
}

void DrawCmdSuggestions(const ImVec2 &barPos, float width) {
    if (!g_sugCount || g_pickMode != 0) return;
    const int shown = 10;
    int first = g_sugSel - shown / 2;
    if (first > g_sugCount - shown) first = g_sugCount - shown;
    if (first < 0) first = 0;
    ImGui::SetNextWindowPos(ImVec2(barPos.x, barPos.y - 2.0f), ImGuiCond_Always, ImVec2(0.0f, 1.0f));
    ImGui::SetNextWindowSizeConstraints(ImVec2(width, 0.0f), ImVec2(width, FLT_MAX));
    ImGui::SetNextWindowBgAlpha(0.95f);
    ImGuiWindowFlags flags = ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoNav |
                             ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoFocusOnAppearing |
                             ImGuiWindowFlags_NoSavedSettings;
    if (ImGui::Begin("##TruCmdSuggestions", nullptr, flags)) {
        ImGui::BringWindowToDisplayFront(ImGui::GetCurrentWindow());
        for (int i = first; i < g_sugCount && i < first + shown; ++i) {
            const CmdSug &s = g_sug[i];
            bool sel = i == g_sugSel;
            ImGui::TextColored(sel ? ImVec4(1.0f, 0.85f, 0.2f, 1.0f) : ImVec4(0.9f, 0.9f, 0.9f, 1.0f), "%s %s",
                               sel ? ">" : " ", s.show);
            const char *value = s.valueId ? CmdCachedValue(s.valueId) : "";
            if (value[0]) {
                ImGui::SameLine();
                ImGui::TextColored(ImVec4(0.45f, 0.8f, 1.0f, 1.0f), "= %.48s", value);
            }
            if (s.note[0]) {
                ImGui::SameLine();
                ImGui::TextDisabled("%.80s", s.note);
            }
        }
        ImGui::TextDisabled("%d / %d   %s", g_sugSel >= 0 ? g_sugSel + 1 : 0, g_sugCount,
                            g_cmdPadMode ? "D-pad = choose, A = run / pick, B = back, Y = pin, View = type"
                                         : "Tab / Down = choose, Enter = run");
    }
    ImGui::End();
}

// ======================================================================================================================
// 0.7 on-screen keyboard: drawn inside the bar window under the result line while the bar has the focus by controller
// ([Cmd] FocusButton = L3, A in the idle bar, View in the pad picker, cmd.keyboard). Row 0 = suggestions (the ids /
// argument values of the line; the history, newest first, while the line is empty), row 1 = quick tokens, rows 2..5 =
// QWERTZ with a number row, row 6 = space / backspace / clear / close / run. The text field is not active meanwhile:
// the keys edit g_cmdBuf directly; a key on a real keyboard (or a click into the field) switches back to typing.
// ======================================================================================================================
enum OskAction { kOskType, kOskBack, kOskClear, kOskClose, kOskRun };
struct OskKey { const char *label, *text; float units; int action; };
struct OskRow { const OskKey *keys; int count; float offset; };
const OskKey kOskTokens[] = {{"time.", "time.", 1, kOskType},   {"player.", "player.", 1, kOskType},
                             {"costume.", "costume.", 1, kOskType}, {"level.", "level.", 1, kOskType},
                             {"dev.", "dev.", 1, kOskType},     {"menu.", "menu.", 1, kOskType},
                             {"0", "0", 1, kOskType},           {"1", "1", 1, kOskType},
                             {"space", " ", 1, kOskType},       {".", ".", 1, kOskType}};
const OskKey kOskNum[] = {{"1", "1", 1, 0}, {"2", "2", 1, 0}, {"3", "3", 1, 0}, {"4", "4", 1, 0}, {"5", "5", 1, 0},
                          {"6", "6", 1, 0}, {"7", "7", 1, 0}, {"8", "8", 1, 0}, {"9", "9", 1, 0}, {"0", "0", 1, 0},
                          {"-", "-", 1, 0}};
const OskKey kOskQ[] = {{"q", "q", 1, 0}, {"w", "w", 1, 0}, {"e", "e", 1, 0}, {"r", "r", 1, 0}, {"t", "t", 1, 0},
                        {"z", "z", 1, 0}, {"u", "u", 1, 0}, {"i", "i", 1, 0}, {"o", "o", 1, 0}, {"p", "p", 1, 0},
                        {"_", "_", 1, 0}};
const OskKey kOskA[] = {{"a", "a", 1, 0}, {"s", "s", 1, 0}, {"d", "d", 1, 0}, {"f", "f", 1, 0}, {"g", "g", 1, 0},
                        {"h", "h", 1, 0}, {"j", "j", 1, 0}, {"k", "k", 1, 0}, {"l", "l", 1, 0}, {":", ":", 1, 0},
                        {"#", "#", 1, 0}};
const OskKey kOskY[] = {{"y", "y", 1, 0}, {"x", "x", 1, 0}, {"c", "c", 1, 0}, {"v", "v", 1, 0}, {"b", "b", 1, 0},
                        {"n", "n", 1, 0}, {"m", "m", 1, 0}, {",", ",", 1, 0}, {".", ".", 1, 0}, {"/", "/", 1, 0}};
const OskKey kOskBottom[] = {{"space", " ", 4, kOskType}, {"<-  (X)", "", 2, kOskBack}, {"clear", "", 1.5f, kOskClear},
                             {"close (B)", "", 1.5f, kOskClose}, {"run (Start)", "", 2, kOskRun}};
const OskRow kOskRows[7] = {{nullptr, 0, 0.0f},      {kOskTokens, 10, 0.0f}, {kOskNum, 11, 0.0f}, {kOskQ, 11, 0.0f},
                            {kOskA, 11, 0.0f},        {kOskY, 10, 0.5f},     {kOskBottom, 5, 0.0f}};
const int kOskRowCount = 7, kOskMaxKeys = 16;

int g_oskRow = 3, g_oskCol = 0;              // cursor; row 0: g_oskSug is the chip
bool g_oskBackClosed = false;                // 0.7.1: B just closed the keyboard - the next B (nothing between) closes
                                             //        the menu
int g_typeFocusFrames = 0;                   // 0.7.1: frames left to get the text field active after a real key
int g_oskSug = 0, g_oskFirst = 0;            // highlighted / first visible suggestion chip
float g_oskCx[kOskRowCount][kOskMaxKeys];    // key centres (x) of the last frame, for up / down
int g_oskCxIndex[kOskMaxKeys];               // row 0: suggestion index of each drawn chip
int g_oskCxCount[kOskRowCount];
int g_oskFlashRow = -1, g_oskFlashCol = -1;  // key just pressed (lights up shortly)
DWORD g_oskFlashTick = 0;
char g_oskHist[16][kCmdLine];                // history, newest first (suggestions of the empty line)
int g_oskHistCount = 0;

bool OskHistoryMode() { return g_cmdBuf[0] == 0; }
int OskSugCount() { return OskHistoryMode() ? g_oskHistCount : g_sugCount; }
const char *OskSugShow(int i) { return OskHistoryMode() ? g_oskHist[i] : g_sug[i].show; }

void OskEdited() {                           // after every change of the line
    g_sugSel = -1;
    g_cmdHistPos = -1;
    g_oskSug = 0;
    g_oskFirst = 0;
}
void OskAppend(const char *text) {
    size_t used = strlen(g_cmdBuf), add = strlen(text);
    if (used + add >= sizeof(g_cmdBuf)) return;
    memcpy(g_cmdBuf + used, text, add + 1);
    OskEdited();
}
void OskBackspace() {
    size_t used = strlen(g_cmdBuf);
    if (used) g_cmdBuf[used - 1] = 0;
    OskEdited();
}
void OskTakeSuggestion(int i) {
    if (i < 0 || i >= OskSugCount()) return;
    char text[kCmdLine];
    if (OskHistoryMode()) strncpy_s(text, sizeof(text), g_oskHist[i], _TRUNCATE);
    else CmdCompletionText(i, text, sizeof(text), true);   // with a space when the id takes an argument
    strncpy_s(g_cmdBuf, sizeof(g_cmdBuf), text, _TRUNCATE);
    OskEdited();
}
void OskRun() {
    if (!g_cmdBuf[0]) return;
    char line[kCmdLine];
    strncpy_s(line, sizeof(line), g_cmdBuf, _TRUNCATE);
    CmdRunFromBar(line);
    g_cmdBuf[0] = 0;
    OskEdited();
}

// the key under the cursor (rows 1..6) or the chip (row 0)
void OskActivate(int row, int col) {
    g_oskFlashRow = row;
    g_oskFlashCol = row == 0 ? g_oskSug : col;
    g_oskFlashTick = GetTickCount();
    if (row == 0) { OskTakeSuggestion(g_oskSug); return; }
    const OskKey &k = kOskRows[row].keys[col];
    switch (k.action) {
    case kOskType: OskAppend(k.text); break;
    case kOskBack: OskBackspace(); break;
    case kOskClear: g_cmdBuf[0] = 0; OskEdited(); break;
    case kOskClose: g_oskOpen = false; break;
    case kOskRun: OskRun(); break;
    default: break;
    }
}

// the key of row <row> whose centre is nearest to x (last frame's layout)
int OskNearest(int row, float x) {
    int best = 0;
    float bestDist = FLT_MAX;
    for (int i = 0; i < g_oskCxCount[row]; ++i) {
        float d = fabsf(g_oskCx[row][i] - x);
        if (d < bestDist) { bestDist = d; best = i; }
    }
    return best;
}
float OskCursorX() {
    if (g_oskRow == 0) {
        for (int i = 0; i < g_oskCxCount[0]; ++i)
            if (g_oskCxIndex[i] == g_oskSug) return g_oskCx[0][i];
        return g_oskCxCount[0] ? g_oskCx[0][0] : 0.0f;
    }
    return g_oskCol < g_oskCxCount[g_oskRow] ? g_oskCx[g_oskRow][g_oskCol] : 0.0f;
}
void OskGoRow(int row) {
    float x = OskCursorX();
    g_oskRow = row;
    if (row == 0) {
        int i = OskNearest(0, x);
        g_oskSug = g_oskCxCount[0] ? g_oskCxIndex[i] : 0;
    } else {
        g_oskCol = g_oskCxCount[row] ? OskNearest(row, x) : 0;
        if (g_oskCol >= kOskRows[row].count) g_oskCol = kOskRows[row].count - 1;
    }
}

// pad input (edges only while the bar owns the pad)
void OskInput(WORD e) {
    bool sugs = OskSugCount() > 0;
    if (g_oskRow == 0 && !sugs) OskGoRow(1);
    if (CmdPadPress(0x0001)) OskGoRow(g_oskRow == 0 ? kOskRowCount - 1 : g_oskRow == 1 && !sugs ? kOskRowCount - 1
                                                                                                   : g_oskRow - 1);
    if (CmdPadPress(0x0002)) OskGoRow(g_oskRow == kOskRowCount - 1 ? (sugs ? 0 : 1) : g_oskRow + 1);
    bool left = CmdPadPress(0x0004), right = CmdPadPress(0x0008);
    if (left || right) {
        if (g_oskRow == 0) {
            int c = OskSugCount();
            g_oskSug = (g_oskSug + (right ? 1 : c - 1)) % c;
        } else {
            int c = kOskRows[g_oskRow].count;
            g_oskCol = (g_oskCol + (right ? 1 : c - 1)) % c;
        }
    }
    // LB / RB: jump between the rows suggestions, tokens, keyboard (letters)
    if (e & 0x0200) OskGoRow(g_oskRow == 0 ? 1 : g_oskRow == 1 ? 3 : (sugs ? 0 : 1));
    if (e & 0x0100) OskGoRow(g_oskRow >= 2 ? 1 : g_oskRow == 1 ? (sugs ? 0 : 3) : 3);
    if (e & 0x1000) OskActivate(g_oskRow, g_oskCol);                       // A: type / take
    if (CmdPadPress(0x4000)) {                                             // X: backspace (repeats while held)
        OskBackspace();
        g_oskFlashRow = 6; g_oskFlashCol = 1; g_oskFlashTick = GetTickCount();
    }
    if ((e & 0x8000) && sugs) OskTakeSuggestion(g_oskSug);                // Y: the highlighted suggestion
    if (e & 0x0010) OskRun();                                              // Start: run the line
    if (e & 0x2000) {                                                      // B: keyboard closed (bar keeps the focus);
        g_oskOpen = false;                                                 //    0.7.1: a second B closes the menu
        g_oskBackClosed = true;
    }
}

// one key: rounded box in the menu's button colours, highlight = the suggestion yellow; true when clicked
bool OskDrawKey(const char *id, const char *label, ImVec2 pos, ImVec2 size, bool cursor, bool flash, ImU32 fill,
                ImU32 textColour) {
    ImGui::SetCursorScreenPos(pos);
    bool clicked = ImGui::InvisibleButton(id, size);
    bool hovered = ImGui::IsItemHovered();
    ImDrawList *dl = ImGui::GetWindowDrawList();
    float rounding = 5.0f * g_scale;
    ImVec2 end(pos.x + size.x, pos.y + size.y);
    if (cursor) fill = ImGui::GetColorU32(ImGuiCol_ButtonActive);
    else if (hovered) fill = ImGui::GetColorU32(ImGuiCol_ButtonHovered);
    dl->AddRectFilled(pos, end, fill, rounding);
    if (flash) dl->AddRectFilled(pos, end, IM_COL32(255, 255, 255, 70), rounding);
    if (cursor) dl->AddRect(ImVec2(pos.x - 1.0f, pos.y - 1.0f), ImVec2(end.x + 1.0f, end.y + 1.0f),
                            IM_COL32(255, 217, 51, 255), rounding, 0, 2.0f * g_scale);
    ImVec2 ts = ImGui::CalcTextSize(label);
    ImVec2 tp(pos.x + (size.x - ts.x) * 0.5f, pos.y + (size.y - ts.y) * 0.5f);
    if (tp.x < pos.x + 4.0f) tp.x = pos.x + 4.0f;
    dl->PushClipRect(pos, end, true);
    dl->AddText(tp, textColour, label);
    dl->PopClipRect();
    return clicked;
}

void DrawOsk() {
    // history for the empty line, newest first
    EnterCriticalSection(&g_cmdLock);
    g_oskHistCount = 0;
    for (int i = g_cmdHistCount - 1; i >= 0 && g_oskHistCount < 16; --i)
        strncpy_s(g_oskHist[g_oskHistCount++], kCmdLine, g_cmdHist[i], _TRUNCATE);
    LeaveCriticalSection(&g_cmdLock);
    int sugCount = OskSugCount();
    if (g_oskSug >= sugCount) g_oskSug = sugCount ? sugCount - 1 : 0;
    if (g_oskRow == 0 && !sugCount) g_oskRow = 1;

    const ImGuiStyle &style = ImGui::GetStyle();
    ImGui::PushItemFlag(ImGuiItemFlags_NoNav, true);   // the pad goes to the keyboard, not to ImGui's navigation
    ImGui::Separator();
    ImVec2 start = ImGui::GetCursorScreenPos();
    float avail = ImGui::GetContentRegionAvail().x;
    float gap = style.ItemSpacing.x * 0.6f;
    float keyH = ImGui::GetFrameHeight() * 1.15f;
    float y = start.y;
    bool flashOn = GetTickCount() - g_oskFlashTick < 150;
    ImU32 text = ImGui::GetColorU32(ImGuiCol_Text);

    // row 0: suggestions (chips sized by their text; the highlighted one is always visible)
    float pad = style.FramePadding.x * 1.5f;
    auto chipW = [&](int i) {
        float w = ImGui::CalcTextSize(OskSugShow(i)).x + pad * 2.0f;
        return w > avail * 0.6f ? avail * 0.6f : w;
    };
    if (g_oskSug < g_oskFirst) g_oskFirst = g_oskSug;
    float used = 0.0f;
    for (int i = g_oskFirst; i <= g_oskSug && i < sugCount; ++i) used += chipW(i) + gap;
    while (g_oskFirst < g_oskSug && used > avail) used -= chipW(g_oskFirst++) + gap;
    g_oskCxCount[0] = 0;
    if (sugCount) {
        float x = start.x;
        for (int i = g_oskFirst; i < sugCount && g_oskCxCount[0] < kOskMaxKeys; ++i) {
            float w = chipW(i);
            if (x + w > start.x + avail + 0.5f && i > g_oskFirst) break;
            char id[24];
            Out(id, sizeof(id), "##osks%d", i);
            bool cur = g_oskRow == 0 && g_oskSug == i;
            bool sel = g_oskRow != 0 && g_oskSug == i;   // Y takes this one
            ImU32 fill = sel ? ImGui::GetColorU32(ImGuiCol_HeaderHovered) : ImGui::GetColorU32(ImGuiCol_FrameBg);
            if (OskDrawKey(id, OskSugShow(i), ImVec2(x, y), ImVec2(w, keyH), cur,
                           flashOn && g_oskFlashRow == 0 && g_oskFlashCol == i, fill, IM_COL32(115, 204, 255, 255))) {
                g_oskRow = 0;
                g_oskSug = i;
                OskActivate(0, i);
            }
            g_oskCx[0][g_oskCxCount[0]] = x + w * 0.5f;
            g_oskCxIndex[g_oskCxCount[0]++] = i;
            x += w + gap;
        }
    } else {
        ImGui::SetCursorScreenPos(ImVec2(start.x, y + (keyH - ImGui::GetTextLineHeight()) * 0.5f));
        ImGui::TextDisabled("%s", OskHistoryMode() ? "(no history yet - type an id)" : "(no matching id / value)");
    }
    y += keyH + gap * 2.5f;

    // rows 1..6: tokens (10 equal cells), keyboard (11 units per row)
    for (int r = 1; r < kOskRowCount; ++r) {
        const OskRow &row = kOskRows[r];
        float units = r == 1 ? 10.0f : 11.0f;
        float unit = (avail - gap * (units - 1.0f)) / units;
        float x = start.x + row.offset * (unit + gap);
        g_oskCxCount[r] = 0;
        for (int c = 0; c < row.count && c < kOskMaxKeys; ++c) {
            const OskKey &k = row.keys[c];
            float w = k.units * unit + (k.units - 1.0f) * gap;
            char id[24];
            Out(id, sizeof(id), "##osk%d_%d", r, c);
            ImU32 fill = ImGui::GetColorU32(ImGuiCol_Button);
            if (r == 1) fill = ImGui::GetColorU32(ImGuiCol_Header);
            if (k.action == kOskRun) fill = IM_COL32(46, 125, 70, 255);
            if (k.action == kOskClose || k.action == kOskClear) fill = ImGui::GetColorU32(ImGuiCol_FrameBg);
            bool cur = g_oskRow == r && g_oskCol == c;
            if (OskDrawKey(id, k.label, ImVec2(x, y), ImVec2(w, keyH), cur,
                           flashOn && g_oskFlashRow == r && g_oskFlashCol == c, fill, text)) {
                g_oskRow = r;
                g_oskCol = c;
                OskActivate(r, c);
            }
            g_oskCx[r][g_oskCxCount[r]++] = x + w * 0.5f;
            x += w + gap;
        }
        y += keyH + (r == 1 ? gap * 2.5f : gap);
    }
    ImGui::SetCursorScreenPos(ImVec2(start.x, y));
    ImGui::PopItemFlag();
    // the highlighted suggestion: value and label (what Y / A would take)
    if (sugCount && !OskHistoryMode()) {
        const CmdSug &s = g_sug[g_oskSug];
        const char *value = s.valueId ? CmdCachedValue(s.valueId) : "";
        ImGui::TextColored(ImVec4(0.45f, 0.8f, 1.0f, 1.0f), "%s%s%.48s", s.show, value[0] ? " = " : "", value);
        if (s.note[0]) { ImGui::SameLine(); ImGui::TextDisabled("%.80s", s.note); }
    }
    ImGui::TextDisabled("A type   X backspace   Y take suggestion   Start run   B close   LB / RB rows   L3 = keyboard "
                        "off   (a real keyboard works too)");
}

// the bar: a window directly under the menu window (always visible, outside the menu's scrolling)
void DrawCmdBar(bool menuJustOpened) {
    if (!g_cmdEnabled || !g_menuRectOk) { g_cmdOwnPad = false; return; }
    ImGuiIO &io = ImGui::GetIO();
    const ImGuiStyle &style = ImGui::GetStyle();
    bool barHadFocus = g_cmdOwnPad;
    bool wantFocus = menuJustOpened || InterlockedExchange(&g_cmdFocusReq, 0) != 0;
    bool keyFocus = ImGui::IsKeyPressed(ImGuiKey_F2, false) ||
                    (!barHadFocus && !io.WantTextInput && ImGui::IsKeyPressed(ImGuiKey_Tab, false));
    if (keyFocus) { wantFocus = true; g_oskOpen = false; }   // F2 / Tab: typing on the real keyboard
    bool toPicker = !barHadFocus && g_cmdBackEdge;    // View in the menu: the bar's pad picker
    if (wantFocus) { g_cmdPadMode = false; g_pickMode = 0; }
    if (toPicker) { g_cmdPadMode = true; g_pickMode = 0; g_oskOpen = false; }
    // 0.7: FocusButton (L3) / cmd.keyboard - focus + on-screen keyboard; L3 again while it is open closes it
    LONG oskReq = InterlockedExchange(&g_cmdOskReq, 0);
    if (oskReq && !toPicker) {
        g_oskBackClosed = false;
        if (oskReq == 1 && g_oskOpen) {               // 0.7.1: also without the bar focus (no hover / focus state)
            g_oskOpen = false;
        } else if (g_cmdKeyboard) {
            g_oskOpen = true;
            g_cmdPadMode = false;
            g_pickMode = 0;
            ImGui::ClearActiveID();                   // the field shows g_cmdBuf, the keys edit it
            wantFocus = true;
            OskEdited();
            g_oskRow = 3;
            g_oskCol = 0;
        } else {
            wantFocus = true;                         // [Cmd] Keyboard=0: only the focus (text field)
        }
    }
    // a real keyboard while the on-screen one is open: back to typing (the typed characters are kept).
    // 0.7.1: independent of the bar focus, mouse hover and the selected key - any real key press seen by the window
    // procedure (g_oskRealKeys) switches; the characters are taken from ImGui's queue here (and removed from it, so the
    // field does not get them twice), and until the text field is really active (up to 20 frames) the focus is
    // requested again and further characters still go into the line
    LONG realKeys = InterlockedExchange(&g_oskRealKeys, 0);
    bool catching = g_oskOpen || (g_typeFocusFrames > 0 && !g_cmdTextActive);
    if (catching) {
        bool typed = false;
        for (int i = 0; i < io.InputQueueCharacters.Size; ++i) {
            ImWchar c = io.InputQueueCharacters[i];
            if (c >= 32 && c < 127) { char s[2] = {static_cast<char>(c), 0}; OskAppend(s); typed = true; }
        }
        if (typed) io.InputQueueCharacters.resize(0);
        if (ImGui::IsKeyPressed(ImGuiKey_Backspace, false)) { OskBackspace(); typed = true; }
        if (g_oskOpen && realKeys && !ImGui::IsKeyPressed(ImGuiKey_Escape, false)) typed = true;
        if (typed) {
            if (g_oskOpen) {
                g_oskOpen = false;
                g_oskBackClosed = false;
                g_cmdPadMode = false;
                g_pickMode = 0;
                g_typeFocusFrames = 20;
                Log(3, "osk: real keyboard -> typing");
            }
            strncpy_s(g_cmdSetText, sizeof(g_cmdSetText), g_cmdBuf, _TRUNCATE);
            g_cmdSetPending = true;                   // cursor to the end, no "select all" of the focus request
            wantFocus = true;
        } else if (g_oskOpen && ImGui::IsKeyPressed(ImGuiKey_Escape, false)) {
            g_oskOpen = false;
        }
    }
    if (g_typeFocusFrames > 0) {                      // 0.7.1: keep asking until the field is active
        if (g_cmdTextActive || g_oskOpen) g_typeFocusFrames = 0;
        else { --g_typeFocusFrames; wantFocus = true; }
    }

    ImGuiViewport *vp = ImGui::GetMainViewport();
    float width = g_menuSize.x;
    ImVec2 pos(g_menuPos.x, g_menuPos.y + g_menuSize.y + 4.0f);
    float height = g_cmdBarHeight > 0.0f ? g_cmdBarHeight : ImGui::GetFrameHeightWithSpacing() * 2.5f;
    float bottom = vp->WorkPos.y + vp->WorkSize.y;
    if (pos.y + height > bottom) pos.y = bottom - height;
    ImGui::SetNextWindowPos(pos, ImGuiCond_Always);
    ImGui::SetNextWindowSizeConstraints(ImVec2(width, 0.0f), ImVec2(width, FLT_MAX));
    if (wantFocus || toPicker) ImGui::SetNextWindowFocus();
    ImGuiWindowFlags flags = ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove |
                             ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoSavedSettings |
                             ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoScrollbar;
    bool textActive = false, focused = false;
    if (ImGui::Begin("TruMenu command bar###TruCmdBar", nullptr, flags)) {
        CmdPollQueued();
        CmdBuildSuggestions(g_cmdBuf, g_cmdPadMode);
        WORD e = g_cmdPadEdges;
        bool leave = false, runNow = false;
        if (g_oskOpen && (e & 0x0020)) {                   // 0.7: View with the keyboard open: pad picker
            g_oskOpen = false;
            g_cmdPadMode = true;
            g_pickMode = 0;
            CmdBuildSuggestions(g_cmdBuf, true);
            e = 0;
        }
        if (e & static_cast<WORD>(~0x2000)) g_oskBackClosed = false;   // 0.7.1: only B right after B counts
        if (barHadFocus && !g_cmdPadMode && !toPicker && !g_oskOpen) {   // text field (or idle bar): the pad goes on
            if ((e & 0x2000) && g_oskBackClosed) {       // 0.7.1: B closed the keyboard, this B closes the menu
                g_oskBackClosed = false;
                if (g_menuOpen) ToggleMenu("B twice: keyboard, then menu");
                e = 0;
            } else if (e & 0x200F) {                     // D-pad / stick / B: into the menu
                leave = true;
                // 0.7 FirstPadPressOnlyFocuses=0: the direction also moves in the menu (FeedGamepad hands it over)
                if (!g_cmdFirstPressFocus && (e & 0x000F)) g_cmdHandOver = true;
            } else if (e & 0x1000) {                     // A: run the typed line, empty = into the menu
                if (g_cmdTextActive && g_cmdBuf[0]) runNow = true;
                else if (g_cmdTextActive) leave = true;
                else if (g_cmdKeyboard) {                // 0.7: A in the idle bar = the on-screen keyboard
                    g_oskOpen = true;
                    OskEdited();
                    g_oskRow = 3;
                    g_oskCol = 0;
                } else wantFocus = true;
            } else if (e & 0x0020) {                     // View: pad picker
                ImGui::ClearActiveID();
                g_cmdPadMode = true;
                g_pickMode = 0;
                CmdBuildSuggestions(g_cmdBuf, true);
                e = 0;                                   // this View press is used up
            }
        }
        ImGui::AlignTextToFramePadding();
        ImGui::TextUnformatted(">");
        ImGui::SameLine();
        float pickWidth = ImGui::CalcTextSize("Pick (View)").x + style.FramePadding.x * 2.0f;
        ImGui::SetNextItemWidth(ImGui::GetContentRegionAvail().x - pickWidth - style.ItemSpacing.x);
        if (wantFocus && !g_cmdPadMode && !g_oskOpen) ImGui::SetKeyboardFocusHere();
        ImGuiInputTextFlags tf = ImGuiInputTextFlags_EnterReturnsTrue | ImGuiInputTextFlags_CallbackCompletion |
                                 ImGuiInputTextFlags_CallbackHistory | ImGuiInputTextFlags_CallbackEdit |
                                 ImGuiInputTextFlags_CallbackAlways;
        bool enter = ImGui::InputTextWithHint("##cmd", "item id [arg] - help, list <filter>, get <id>; Tab / Down = "
                                              "choose, Up = history", g_cmdBuf, sizeof(g_cmdBuf), tf, CmdCallback);
        textActive = ImGui::IsItemActive();
        if (textActive && g_oskOpen) g_oskOpen = false;   // 0.7: a click into the field = typing on the real keyboard
        if (ImGui::IsItemDeactivated() && ImGui::IsKeyPressed(ImGuiKey_Escape, false)) leave = true;
        ImGui::SameLine();
        if (ImGui::Button("Pick (View)")) { g_cmdPadMode = true; g_pickMode = 0; }
        if (enter || runNow) {
            char line[kCmdLine];
            if (g_sugSel >= 0 && g_sugSel < g_sugCount) CmdCompletionText(g_sugSel, line, sizeof(line), false);
            else strncpy_s(line, sizeof(line), g_cmdBuf, _TRUNCATE);
            CmdRunFromBar(line);
            if (enter) {                             // Enter left the field: empty it, focus it again next frame
                g_cmdBuf[0] = 0;
                InterlockedExchange(&g_cmdFocusReq, 1);
            } else {
                g_cmdSetText[0] = 0;
                g_cmdSetPending = true;
            }
            g_cmdHistPos = -1;
            g_sugSel = -1;
        }
        if (g_cmdLeaveReq) { g_cmdLeaveReq = false; leave = true; }

        // pad picker
        if (g_cmdPadMode && !toPicker) {
            if (g_pickMode == 1) {
                double mult = ImGui::IsKeyDown(ImGuiKey_GamepadR2) ? 10.0 : 1.0;
                if (CmdPadPress(0x0100)) g_pickValue -= g_pickStep * mult;
                if (CmdPadPress(0x0200)) g_pickValue += g_pickStep * mult;
                if (g_pickRange) {
                    if (g_pickValue < g_pickMin) g_pickValue = g_pickMin;
                    if (g_pickValue > g_pickMax) g_pickValue = g_pickMax;
                }
                char value[64], line[kCmdLine];
                CmdPickValueText(value, sizeof(value));
                ImGui::TextColored(ImVec4(1.0f, 0.85f, 0.2f, 1.0f), "%s = %s", g_pickId, value);
                ImGui::SameLine();
                ImGui::TextDisabled("LB - / RB + (hold RT: x10), A = set, B = back");
                if (e & 0x1000) { Out(line, sizeof(line), "%s %s", g_pickId, value); CmdRunFromBar(line); }
                if (e & 0x2000) g_pickMode = 0;
            } else {
                if (g_sugCount && g_sugSel < 0) g_sugSel = 0;
                if (CmdPadPress(0x0001) && g_sugSel > 0) --g_sugSel;
                if (CmdPadPress(0x0002) && g_sugSel < g_sugCount - 1) ++g_sugSel;
                if (CmdPadPress(0x0004)) g_sugSel = g_sugSel > 8 ? g_sugSel - 8 : 0;
                if (CmdPadPress(0x0008)) g_sugSel = g_sugSel + 8 < g_sugCount ? g_sugSel + 8 : g_sugCount - 1;
                if ((e & 0x1000) && g_sugSel >= 0 && g_sugSel < g_sugCount) CmdPadChoose(g_sugSel);
                else if (e & 0x2000) {                   // B: out of an argument list, else into the menu
                    if (strchr(g_cmdBuf, ' ')) g_cmdBuf[0] = 0;
                    else leave = true;
                } else if ((e & 0x8000) && g_sugSel >= 0 && g_sugSel < g_sugCount && g_sug[g_sugSel].idToken &&
                           CmdKindOf(g_sug[g_sugSel].text) != kCkBuiltin) {
                    FavToggle(g_sug[g_sugSel].text);
                } else if (e & 0x0020) {                 // View: back to typing (0.7: on the on-screen keyboard)
                    g_cmdPadMode = false;
                    if (g_cmdKeyboard) {
                        g_oskOpen = true;
                        OskEdited();
                        g_oskRow = 3;
                        g_oskCol = 0;
                    } else {
                        InterlockedExchange(&g_cmdFocusReq, 1);
                    }
                }
                if (!g_sugCount) ImGui::TextDisabled("pad picker: no matching id - B = back");
            }
        }

        // result line
        char result[sizeof(g_cmdResult)], rline[kCmdLine], source[16];
        EnterCriticalSection(&g_cmdLock);
        strncpy_s(result, sizeof(result), g_cmdResult, _TRUNCATE);
        strncpy_s(rline, sizeof(rline), g_cmdResultLine, _TRUNCATE);
        strncpy_s(source, sizeof(source), g_cmdResultSource, _TRUNCATE);
        LeaveCriticalSection(&g_cmdLock);
        if (result[0]) {
            bool ok = !strncmp(result, "ok", 2);
            ImGui::TextDisabled("%s: %s%s", source, rline, g_cmdWaitId[0] ? "   (waiting for the game thread)" : "");
            ImGui::PushStyleColor(ImGuiCol_Text, ok ? ImVec4(0.45f, 0.95f, 0.45f, 1.0f) : ImVec4(1.0f, 0.4f, 0.4f, 1.0f));
            if (strlen(result) > 240) {
                ImGui::BeginChild("##cmdresult", ImVec2(0.0f, ImGui::GetTextLineHeightWithSpacing() * 6.0f),
                                  ImGuiChildFlags_Borders, ImGuiWindowFlags_NoNav);
                ImGui::TextWrapped("%s", result);
                ImGui::EndChild();
            } else {
                ImGui::TextWrapped("%s", result);
            }
            ImGui::PopStyleColor();
        } else {
            ImGui::TextDisabled("help = the commands; D-pad / Down = into the menu, View / F2 / Tab = back to the bar, "
                                "L3 = on-screen keyboard");
        }
        // 0.7 on-screen keyboard (0.7.1: the open keyboard owns the pad - FeedGamepad - whatever the focus / hover)
        if (g_oskOpen) OskInput(e);
        if (g_oskOpen) DrawOsk();
        if (leave) CmdFocusMenu();
        focused = ImGui::IsWindowFocused(ImGuiFocusedFlags_RootAndChildWindows);
        if (!focused) { g_cmdPadMode = false; g_oskOpen = false; g_oskBackClosed = false; }
        if (textActive) g_oskBackClosed = false;
    }
    g_cmdBarHeight = ImGui::GetWindowHeight();
    ImVec2 barPos = ImGui::GetWindowPos();
    ImGui::End();
    if ((textActive || g_cmdPadMode) && focused) DrawCmdSuggestions(barPos, width);
    g_cmdTextActive = textActive;
    g_cmdOwnPad = focused;
}

void PageLevel() {
    char unit[64];
    CurrentUnit(unit, sizeof(unit));
    Text("current unit (GameTracker+0x38): %s", unit[0] ? unit : "-");
    if (!g_levelOk || !g_experimental) {
        ImGui::TextUnformatted(g_levelOk ? "(experimental actions off in TruMenu.ini)" : "level change code check failed");
        return;
    }
    // presets from [Levels] List
    char list[sizeof(g_levelList)];
    strncpy_s(list, sizeof(list), g_levelList, _TRUNCATE);
    char *context = nullptr;
    int index = 0;
    for (char *name = strtok_s(list, ", ", &context); name; name = strtok_s(nullptr, ", ", &context), ++index) {
        char label[96];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "Load %s##lvl%d", name, index);
        if (ImGui::Button(label)) QueueItem("level.load", name);
    }
    if (unit[0] && ImGui::Button("Reload current unit  [level.reload]")) QueueItem("level.reload", "");
    // 0.7.1: the mission menu's start (main menu only) - the intro plays, unlike level.load
    if (g_missionOk) {                                     // 0.7.2: DLC 1 first
        if (ImGui::Button("Start DLC 1 as the mission menu (intro)  [level.start dlc1]")) QueueItem("level.start", "dlc1");
        if (ImGui::Button("Start DLC 2 as the mission menu (intro)  [level.start dlc2]")) QueueItem("level.start", "dlc2");
        char why[200];
        if (LevelChangePending(why, sizeof(why))) ImGui::TextDisabled("level.load / level.start refused now: %s", why);
    } else {
        ImGui::TextDisabled("level.start: mission start path not verified (see TruMenu.log)");
    }
    // every playable unit of the PC unit list, one tree node per group
    ImGui::Separator();
    Text("All units (%d, PC tr8/pc-w/unitlist.txt) - [level.load <unit>]", kUnitCount);
    for (int i = 0; i < kUnitCount;) {
        const char *group = kUnits[i].group;
        int count = 0;
        while (i + count < kUnitCount && strcmp(kUnits[i + count].group, group) == 0) ++count;
        char head[64];
        _snprintf_s(head, sizeof(head), _TRUNCATE, "%s (%d)##grp%d", group, count, i);
        if (ImGui::TreeNode(head)) {
            for (int k = i; k < i + count; ++k) {
                char label[96];
                _snprintf_s(label, sizeof(label), _TRUNCATE, "%s##unit%d", kUnits[k].unit, k);
                if (ImGui::Button(label)) QueueItem("level.load", kUnits[k].unit);
                if (ImGui::IsItemHovered()) ImGui::SetTooltip("%s", kUnits[k].path);
            }
            ImGui::TreePop();
        }
        i += count;
    }
    ImGui::TextWrapped("GAMELOOP_RequestLevelChangeByName 0x%08lx (name, GameTracker, 4). Any other unit: TruLink "
                       "\"menu level.load <unit>\" or [Levels] List in TruMenu.ini. A unit loads with the chosen costume "
                       "(Outfits page) or the unit's default.", kLevelChange);
}

void PageOutfits() {
    if (!g_costumeOk) { ImGui::TextUnformatted("costume code check failed (see TruMenu.log)"); return; }
    CostumeState s;
    ReadCostumeState(&s);
    char cur[160], c0[160], c2[160], def[160];
    IdName(static_cast<int>(s.current), cur, sizeof(cur));
    IdName(s.chosen0, c0, sizeof(c0));
    IdName(s.chosen2, c2, sizeof(c2));
    IdName(s.unitDefault, def, sizeof(def));
    Text("current costume [0x%08lx]: %s", kCostumeNow, cur);
    Text("game data [0x%08lx] = 0x%08lx, +0x1f4 = %u -> the level load reads +0x%lx", kGameDataPtr, s.gameData, s.mode,
         s.mode ? kGdChosen2 : kGdChosen0);
    Text("chosen +0x20c: %s   +0x20e: %u   +0x210: %s", c0, s.chosen1, c2);
    Text("unit default (unit %lu, data +0x70 -> +0x294): %s", s.unitId, s.unitDefault < 0 ? "-" : def);
    if (!g_experimental) { ImGui::TextUnformatted("(experimental actions off in TruMenu.ini)"); return; }
    static bool reload = false;
    ImGui::Checkbox("reload the current unit after choosing  [costume.setreload]", &reload);
    if (ImGui::Button("Reset chosen costume (0 / 0 / 0)  [costume.reset]")) QueueItem("costume.reset", "");
    ImGui::Separator();
    ImGui::TextUnformatted("Player records of the type table (index  name  object id):");
    // object ids by record, recomputed when the object name table or the type table moves (the lookup walks ~1000 names)
    static int ids[64];
    static DWORD cachedNames = 0, cachedTypes = 0;
    DWORD names = 0;
    ReadDword(kObjNames, &names);
    bool fresh = names != cachedNames || TypeTable() != cachedTypes;
    if (fresh) { cachedNames = names; cachedTypes = TypeTable(); }
    char name[64];
    bool player = false;
    for (int i = 0; i < 64 && TypeRecord(i, name, sizeof(name), &player); ++i) {
        if (!player) continue;
        if (fresh) ids[i] = ObjectId(name);
        int id = ids[i];
        bool chosen = id && id == (s.mode ? s.chosen2 : s.chosen0);
        bool now = id && static_cast<DWORD>(id) == s.current;
        char label[128];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "%2d  %s  (%d)%s%s##cos%d", i, name, id, chosen ? "  [chosen]" : "",
                    now ? "  [current]" : "", i);
        if (!id) ImGui::BeginDisabled();
        if (ImGui::Button(label)) {
            char arg[16];
            _snprintf_s(arg, sizeof(arg), _TRUNCATE, "%d", i);
            QueueItem(reload ? "costume.setreload" : "costume.set", arg);
        }
        if (!id) ImGui::EndDisabled();
    }
    ImGui::TextWrapped("Choosing writes the object id (u16) to game data +0x20c (+0x210 while +0x1f4 != 0) after the "
                       "game's check 0x%08lx; the next level load (tru+0x1de2b0) uses it unless byte [0x0084216c] holds "
                       "a name, and in l1_seatop it takes lara_wetsuit_warm instead. The state save tru+0x155cb1 writes "
                       "the current costume back to +0x20c.", kCostumeValid);
}

void PageOverlay() {
    bool overlay = g_overlay != 0;
    if (!g_playerOk) ImGui::BeginDisabled();
    if (ImGui::Checkbox("Show Lara's position (top left)", &overlay)) InterlockedExchange(&g_overlay, overlay);
    if (!g_playerOk) ImGui::EndDisabled();
    float p[3], r[3];
    DWORD instance = 0;
    if (ReadLara(p, r, &instance)) {
        Text("player instance 0x%08lx", instance);
        Text("position %.1f  %.1f  %.1f", p[0], p[1], p[2]);
        Text("rotation %.3f  %.3f  %.3f", r[0], r[1], r[2]);
    } else {
        ImGui::TextUnformatted(g_playerOk ? "no player instance (menu / loading)" : "player pointer check failed");
    }
    ImGui::TextWrapped("Source: [0x%08lx] = GameTracker+0xc, instance +0x%lx position / +0x%lx rotation (TRLAU Instance.h).",
                       kPlayerPtr, kInstancePosition, kInstanceRotation);
}

void Todo(const char *text) {
    ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(1.0f, 0.8f, 0.3f, 1.0f));
    ImGui::TextWrapped("TODO: %s", text);
    ImGui::PopStyleColor();
}

void PageCamera() {
    if (!InLevel()) { ImGui::TextUnformatted("needs a level (no player instance)"); return; }
    Todo("own free camera (move / rotate the camera transform with the sticks) - needs the camera struct offsets.");
    ImGui::TextWrapped("Known: CameraManager 0x%08lx, current camera [0x%08lx]; CAMERA_SetMode 0x%08lx; restore 0x%08lx "
                       "(thiscall manager). Modes: 5 FreeCamera, 9 ObjectDebugCamera, 10 CheatCamera; TRLAU enters its "
                       "free camera with mode 11.", kCameraManager, kCurrentCamera, kCameraSetMode, kCameraRestore);
    DWORD camera = 0;
    ReadDword(kCurrentCamera, &camera);
    Text("current camera 0x%08lx", camera);
    if (!g_experimental || !g_cameraOk) {
        ImGui::TextUnformatted(g_cameraOk ? "(experimental actions off in TruMenu.ini)" : "camera code check failed");
        return;
    }
    ImGui::TextUnformatted("Experimental (runs on the game thread when the menu is closed or next frame):");
    ImGui::SliderInt("mode", &g_cameraModeChoice, 0, 12);
    char arg[16];
    _snprintf_s(arg, sizeof(arg), _TRUNCATE, "%d", g_cameraModeChoice);
    if (ImGui::Button("CAMERA_SetMode(mode)  [camera.mode]")) QueueItem("camera.mode", arg);
    if (ImGui::Button("Restore game camera  [camera.restore]")) QueueItem("camera.restore", "");
}

void PageCheat() {
    if (!InLevel()) { ImGui::TextUnformatted("needs a level (no player instance)"); return; }
    BYTE cheat = 0;
    DWORD value = 0;
    if (ReadDword(kCheatMode & ~3u, &value)) cheat = static_cast<BYTE>(value >> ((kCheatMode & 3) * 8));
    Text("GameTracker.cheatMode [0x%08lx] = %u", kCheatMode, cheat);
    if (!g_experimental || !g_postOk || !g_playerOk) {
        ImGui::TextUnformatted(g_postOk && g_playerOk ? "(experimental actions off in TruMenu.ini)"
                                                      : "INSTANCE_Post / player check failed");
        return;
    }
    if (ImGui::Button(cheat ? "Cheat / flight OFF  [cheat.flight]" : "Cheat / flight ON  [cheat.flight]"))
        QueueItem("cheat.flight", "");
    ImGui::TextWrapped("Toggles cheatMode and posts message 12 to the player (TRLAU Skew.cpp). While on and the menu "
                       "is closed: RT moves Lara up, LT down (speed %.0f per 30 fps frame, [Cheat] FlightSpeed).",
                       g_flightSpeed);
    Todo("PSCCF_IsInCheatMode (bit 30 of [[0xfadb58]+0x68], player message 0x9f) is a different switch - not used yet.");
}

void PageMarkup() {
    ImGui::TextWrapped("0.3: draw.debugflag (debugFlags2 0x100) was removed - that bit is the TR7 / TRAE debug-draw path, "
                       "not TR8 (catalog section 7). The TR8 developer flags are on the page \"Developer menu "
                       "(original)\" (e.g. Show Spline Info = debugFlags2 0x400000).");
    if (!g_drawOk) { ImGui::TextUnformatted("markup / projection code check failed"); return; }
    bool markup = g_drawMarkup != 0, ledges = g_drawLedges != 0;
    if (ImGui::Checkbox("draw markup  [draw.markup]", &markup)) { char o[96]; RunDrawMarkup(markup ? "1" : "0", o, sizeof(o)); }
    ImGui::SameLine();
    if (ImGui::Checkbox("ledges only  [draw.ledges]", &ledges)) { char o[96]; RunDrawLedges(ledges ? "1" : "0", o, sizeof(o)); }
    ImGui::SliderFloat("projected width  [draw.scale]", &g_drawW, 256.0f, 2048.0f, "%.0f");
    ImGui::SliderFloat("projected height", &g_drawH, 224.0f, 2048.0f, "%.0f");
    Text("boxes drawn last frame: %d", g_drawnBoxes);
    ImGui::TextWrapped("Experimental: boxes of MarkupManager [0xdb94cc]+0x14 (next +4), poly line of MarkUp +0x58 or a "
                       "circle at MarkUp +0x34, projected like 0x49f630 (matrix 0xa038f0, focal [0x8906d0], centre "
                       "256 / 224). Colours: yellow ledge (bit 30), green ladder (22), cyan poles (25-27), blue water "
                       "(20), orange rope (19) - catalog bit names, not verified. If lines sit off, adjust the "
                       "projected size (default 512 x 448).");
    Todo("draw.collision / portals / triggers (catalog section 7).");
}

// ---- 0.3 pages ----
void Status03Line() {
    ImGui::TextWrapped("0.3: dev menu %s, time %s, pause %s, control %s, ui %s, instances %s, remove %s, costume switch %s, "
                       "movie %s, menu loop %s, script natives %s, markup draw %s", g_devOk ? "ok" : "NO",
                       g_timeOk ? "ok" : "NO", g_pauseOk ? "ok" : "NO", g_controlOk ? "ok" : "NO", g_uiOk ? "ok" : "NO",
                       g_instOk ? "ok" : "NO", g_removeOk ? "ok" : "NO", g_switchOk ? "ok" : "NO",
                       g_movieOk && g_mainStateOk ? "ok" : "NO", g_menuLoopOk ? "ok" : "NO", g_scriptOk ? "ok" : "NO",
                       g_drawOk ? "ok" : "NO");
    ImGui::TextWrapped("     weapon.give %s, ammo %s, health %s", g_weaponOk ? "ok" : "NO", g_ammoOk ? "ok" : "NO",
                       g_healthOk ? "ok" : "NO");
    ImGui::TextWrapped("0.4: weapon slots %s, ammo.fill %s, gear.give %s; TO TEST file %s", g_slotsOk ? "ok" : "NO",
                       g_maxAmmoOk && g_ammoOk ? "ok" : "NO", g_gearOk ? "ok" : "NO", g_testPath);
}

void Note(const char *text) {
    ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.6f, 0.75f, 1.0f, 1.0f));
    ImGui::TextWrapped("%s", text);
    ImGui::PopStyleColor();
}

// one widget for any item id: bool -> checkbox, info -> value text, else a button that runs it with "" (its default)
void ItemWidget(const char *id) {
    const Item *item = FindItem(id);
    const DevRow *dev = item ? nullptr : DevFind(id);
    char value[256] = "";
    const char *type = "action", *label = id;
    if (item) {
        item->value(value, sizeof(value));
        type = item->type;
        label = item->label;
    } else if (dev) {
        DevValue(*dev, value, sizeof(value));
        type = dev->type == kDevAction ? "action" : dev->type == kDevInt ? "int" : "bool";
        label = dev->text;
    } else {
        return;
    }
    ImGui::PushID(id);
    char text[200];
    if (strcmp(type, "bool") == 0) {
        bool on = value[0] == '1';
        _snprintf_s(text, sizeof(text), _TRUNCATE, "%s  [%s]", label, id);
        if (ImGui::Checkbox(text, &on)) QueueItem(id, on ? "1" : "0");
    } else if (strcmp(type, "info") == 0) {
        _snprintf_s(text, sizeof(text), _TRUNCATE, "%s: %.120s", id, value);
        ImGui::Selectable(text);
    } else {
        _snprintf_s(text, sizeof(text), _TRUNCATE, "%s  [%s]%s%s", label, id, value[0] ? " = " : "", value);
        if (ImGui::Button(text)) QueueItem(id, "");
    }
    FavKey(id);
    ImGui::PopID();
}

void PageFavourites() {
    ImGui::TextUnformatted("Y on an item pins / unpins it ([Favorites] Ids in TruMenu.ini; fav.list / fav.add / fav.del).");
    int count = 0;
    ForFavs([&](const char *id) { ItemWidget(id); ++count; });
    if (!count) ImGui::TextUnformatted("(no favourites)");
    if (ImGui::TreeNode("Add an item (A or Y on an id)")) {
        for (const Item &item : kItems) {
            if (strcmp(item.type, "todo") == 0 || FavHas(item.id)) continue;
            if (ImGui::Selectable(item.id)) FavToggle(item.id);
            else FavKey(item.id);
            if (ImGui::IsItemHovered()) ImGui::SetTooltip("%s", item.label);
        }
        ImGui::TreePop();
    }
}

// 0.4 TO TEST page: one row per test (state, hint, id, note), A on the row = OK, X = FAIL, Y = SKIP (X / Y are taken
// from ImGui in FeedGamepad while a row has the focus), buttons OK / FAIL / SKIP and Run (when the id - or the part
// before ':' - is a usable item; the part after ':' is its argument)
void TestMarkFromMenu(const char *id, const char *state) {
    char o[300];
    TestMark(id, state, nullptr, o, sizeof(o));
    _snprintf_s(g_lastAction, sizeof(g_lastAction), _TRUNCATE, "%s", o);
}

bool ConfirmButton(const char *label, const char *key);

// "id" or "id:arg" -> item id + argument; false when it is not a usable item
bool TestRunTarget(const char *target, char *itemId, size_t idSize, const char **runArg) {
    strncpy_s(itemId, idSize, target, _TRUNCATE);
    char *colon = strchr(itemId, ':');
    *runArg = "";
    if (colon) { *colon = 0; *runArg = target + (colon - itemId) + 1; }
    return itemId[0] && ItemUsable(itemId);
}

// 0.5: switches first (toggles: a checkbox each; INI targets take effect at the next start), then steps and checks
// in list order; steps are numbered, the first open step is marked "NEXT"; A on a step runs its item and marks it
// done, "Run" only runs it, "Done" / "Open" only mark it
void PageTestToggles(const TestRow *rows, int c) {
    bool any = false;
    for (int i = 0; i < c; ++i) if (TestIs(rows[i], "toggle")) { any = true; break; }
    if (!any) return;
    ImGui::SeparatorText("Switches (on / off - to find the step or feature that crashes)");
    for (int i = 0; i < c; ++i) {
        const TestRow &t = rows[i];
        if (!TestIs(t, "toggle")) continue;
        ImGui::PushID(1000 + i);
        bool on = !_stricmp(t.state, "on");
        char label[512];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "%s   [%s -> %s]", t.hint[0] ? t.hint : t.id, t.id, t.target);
        if (ImGui::Checkbox(label, &on)) TestMarkFromMenu(t.id, on ? "on" : "off");
        if (t.note[0] || t.when[0]) {
            ImGui::Indent();
            ImGui::TextDisabled("%s%s%s", t.note, t.note[0] && t.when[0] ? "  " : "", t.when);
            ImGui::Unindent();
        }
        ImGui::PopID();
    }
    ImGui::Separator();
}

void PageTests() {
    ImGui::TextWrapped("TO TEST list from the main session or Invoke-TruTestRun.ps1 (TruLink: menu test.step / test.add / "
                       "test.toggle / test.mark / test.export). Checks: A = OK, X = FAIL, Y = SKIP. Steps: A = run + "
                       "done. Kept in %s.", g_testPath[0] ? g_testPath : "TruMenu.tests.txt");
    static TestRow rows[kTestMax];
    EnterCriticalSection(&g_testLock);
    int c = g_testCount;
    memcpy(rows, g_tests, sizeof(TestRow) * static_cast<size_t>(c));
    LeaveCriticalSection(&g_testLock);
    bool xPressed = InterlockedExchange(&g_testX, 0) != 0, yPressed = InterlockedExchange(&g_testY, 0) != 0;
    bool anyFocus = false;
    PageTestToggles(rows, c);
    int nextStep = -1;
    for (int i = 0; i < c && nextStep < 0; ++i)
        if (TestIs(rows[i], "step") && _stricmp(rows[i].state, "done") != 0) nextStep = i;
    for (int i = 0; i < c; ++i) {
        const TestRow &t = rows[i];
        if (TestIs(t, "toggle")) continue;
        if (TestIs(t, "step")) {
            ImGui::PushID(i);
            bool done = !_stricmp(t.state, "done");
            char itemId[64];
            const char *runArg = "";
            bool runnable = t.target[0] && TestRunTarget(t.target, itemId, sizeof(itemId), &runArg);
            char label[512];
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s %2d. %s", done ? "[DONE]" : i == nextStep ? "NEXT->" : "      ",
                        t.num, t.hint[0] ? t.hint : "(no text)");
            ImVec4 colour = done ? ImVec4(0.6f, 0.6f, 0.6f, 1.0f) : i == nextStep ? ImVec4(1.0f, 0.85f, 0.3f, 1.0f)
                                                                                  : ImVec4(0.75f, 0.85f, 1.0f, 1.0f);
            ImGui::PushStyleColor(ImGuiCol_Text, colour);
            bool activated = ImGui::Selectable(label);
            ImGui::PopStyleColor();
            if (activated) {
                if (runnable) QueueItem(itemId, runArg);
                TestMarkFromMenu(t.id, "done");
            }
            ImGui::Indent();
            if (runnable) {
                char run[160];
                _snprintf_s(run, sizeof(run), _TRUNCATE, "Run %s%s%s", itemId, runArg[0] ? " " : "", runArg);
                if (ImGui::SmallButton(run)) QueueItem(itemId, runArg);
                ImGui::SameLine();
            } else if (t.target[0]) {
                ImGui::TextDisabled("(%s: no such item)", t.target);
                ImGui::SameLine();
            }
            if (ImGui::SmallButton(done ? "Open again" : "Done")) TestMarkFromMenu(t.id, done ? "open" : "done");
            if (t.when[0]) {
                ImGui::SameLine();
                ImGui::TextDisabled("%s", t.when);
            }
            ImGui::Unindent();
            ImGui::PopID();
            continue;
        }
        ImGui::PushID(i);
        bool ok = !_stricmp(t.state, "ok"), fail = !_stricmp(t.state, "fail"), skip = !_stricmp(t.state, "skip");
        ImVec4 colour = ok ? ImVec4(0.45f, 1.0f, 0.45f, 1.0f) : fail ? ImVec4(1.0f, 0.45f, 0.4f, 1.0f)
                      : skip ? ImVec4(0.65f, 0.65f, 0.65f, 1.0f) : ImVec4(1.0f, 1.0f, 1.0f, 1.0f);
        char label[512];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "%s  %s   [%s]%s%s", ok ? "[OK]  " : fail ? "[FAIL]" : skip ? "[SKIP]" : "[    ]",
                    t.hint[0] ? t.hint : "(no hint)", t.id, t.note[0] ? "  - " : "", t.note);
        ImGui::PushStyleColor(ImGuiCol_Text, colour);
        bool activated = ImGui::Selectable(label);
        ImGui::PopStyleColor();
        if (ImGui::IsItemFocused()) {
            anyFocus = true;
            if (xPressed) TestMarkFromMenu(t.id, "fail");
            else if (yPressed) TestMarkFromMenu(t.id, "skip");
        }
        if (activated) TestMarkFromMenu(t.id, "ok");
        ImGui::Indent();
        if (ImGui::SmallButton("OK")) TestMarkFromMenu(t.id, "ok");
        ImGui::SameLine();
        if (ImGui::SmallButton("FAIL")) TestMarkFromMenu(t.id, "fail");
        ImGui::SameLine();
        if (ImGui::SmallButton("SKIP")) TestMarkFromMenu(t.id, "skip");
        char itemId[64];
        strncpy_s(itemId, sizeof(itemId), t.id, _TRUNCATE);
        char *colon = strchr(itemId, ':');
        const char *runArg = "";
        if (colon) { *colon = 0; runArg = t.id + (colon - itemId) + 1; }
        if (ItemUsable(itemId)) {
            ImGui::SameLine();
            char run[160];
            _snprintf_s(run, sizeof(run), _TRUNCATE, "Run %s%s%s", itemId, runArg[0] ? " " : "", runArg);
            if (ImGui::SmallButton(run)) QueueItem(itemId, runArg);
        }
        if (t.when[0]) {
            ImGui::SameLine();
            ImGui::TextDisabled("%s", t.when);
        }
        ImGui::Unindent();
        ImGui::PopID();
    }
    InterlockedExchange(&g_testFocus, anyFocus ? 1 : 0);
    if (ImGui::Button("Remove the marked rows  [test.clear done]")) { char o[160]; RunTestClear("done", o, sizeof(o)); }
    ImGui::SameLine();
    if (ConfirmButton("Remove all rows  [test.clear]", "testclear")) { char o[160]; RunTestClear("", o, sizeof(o)); }
}

// in-menu confirmation (no dialogs): the first A arms a button for 5 s, the second A runs it
bool ConfirmButton(const char *label, const char *key) {
    static char armed[32] = "";
    static DWORD armedAt = 0;
    bool isArmed = strcmp(armed, key) == 0 && GetTickCount() - armedAt < 5000;
    char text[160];
    _snprintf_s(text, sizeof(text), _TRUNCATE, isArmed ? "%s - press A again to confirm##%s" : "%s##%s", label, key);
    if (isArmed) ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.7f, 0.2f, 0.1f, 1.0f));
    bool pressed = ImGui::Button(text);
    if (isArmed) ImGui::PopStyleColor();
    if (!pressed) return false;
    if (isArmed) { armed[0] = 0; return true; }
    strncpy_s(armed, sizeof(armed), key, _TRUNCATE);
    armedAt = GetTickCount();
    return false;
}

void PageSettings() {
    Text("TruMenu.ini: %s", g_iniPath[0] ? g_iniPath : "-");
    static char all[8192];
    ValSettings(all, sizeof(all));
    char *context = nullptr;
    for (char *line = strtok_s(all, ";", &context); line; line = strtok_s(nullptr, ";", &context)) {
        while (*line == ' ') ++line;
        bool changed = line[0] == '*';
        if (changed) ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(1.0f, 0.8f, 0.3f, 1.0f));
        ImGui::TextUnformatted(line);
        if (changed) ImGui::PopStyleColor();
    }
    ImGui::TextUnformatted("(* = changed from the default)   [settings.show]");
    char o[512];
    if (ConfirmButton("Favourites back to the default list  [fav.reset]", "favreset")) {
        bool ok = RunFavReset("", o, sizeof(o));
        SetLastAction("fav.reset", ok, o);
    }
    if (ConfirmButton("Reset all settings (backup, rewrite TruMenu.ini)  [settings.reset]", "setreset")) {
        bool ok = RunSettingsReset("", o, sizeof(o));
        SetLastAction("settings.reset", ok, o);
    }
}

// one page of Crystal's developer menu, drawn from its rows: links switch the page, values are read live
void PageDev() {
    if (!g_devOk) { ImGui::TextWrapped("developer menu tables: %s", g_devStatus); return; }
    ImGui::TextWrapped("Crystal Dynamics' own debug menu, still in tru.exe .data (%s). The driver is gone in retail; "
                       "TruMenu draws the rows as their types say. Effects in retail are mostly unverified (notes in "
                       "blue). [dev.<label>], dev.list", g_devStatus);
    if (!g_experimental) ImGui::TextUnformatted("(experimental actions off in TruMenu.ini - read only)");
    char name[64];
    DevPageName(g_devPage, name, sizeof(name));
    ImGui::Separator();
    Text("page: %s (0x%08lx)", name, g_devPage);
    if (g_devPage != kDevRoot && ImGui::Button("<< root page##devroot")) g_devPage = kDevRoot;
    for (int i = 0; i < g_devCount; ++i) {
        const DevRow &d = g_dev[i];
        if (d.page != g_devPage) continue;
        ImGui::PushID(static_cast<int>(d.addr));
        char value[32];
        DevValue(d, value, sizeof(value));
        const char *note = DevNoteOf(d.addr);
        switch (d.type) {
        case kDevTitle:
            Text("== %s ==", d.text[0] ? d.text : "(no title)");
            break;
        case kDevHeader:
            Text("(page header, text layout \"%s\"; its slots are empty in retail)", d.text);
            break;
        case kDevLink: {
            char label[96];
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s  ->", d.text);
            if (ImGui::Button(label)) g_devPage = d.target;
            break;
        }
        case kDevFlag:
        case kDevBool: {
            bool on = value[0] == '1';
            char label[120];
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s  [%s]", d.text, d.id);
            if (!g_experimental) ImGui::BeginDisabled();
            if (ImGui::Checkbox(label, &on)) QueueItem(d.id, on ? "1" : "0");
            FavKey(d.id);
            if (!g_experimental) ImGui::EndDisabled();
            if (ImGui::IsItemHovered())
                ImGui::SetTooltip(d.type == kDevFlag ? "[0x%08lx] & 0x%lx" : "byte [0x%08lx] (value 0x%lx)", d.target, d.p5);
            break;
        }
        case kDevInt: {
            int v = atoi(value), lo = static_cast<int>(d.p1), hi = static_cast<int>(d.p2);
            char label[120];
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s  [%s]", d.text, d.id);
            if (!g_experimental) ImGui::BeginDisabled();
            bool changed = hi - lo <= 255 ? ImGui::SliderInt(label, &v, lo, hi)
                                          : ImGui::InputInt(label, &v, hi > 1000 ? 100 : 1, 1000);
            FavKey(d.id);
            if (changed) {
                char arg[16];
                _snprintf_s(arg, sizeof(arg), _TRUNCATE, "%d", v);
                QueueItem(d.id, arg);
            }
            if (!g_experimental) ImGui::EndDisabled();
            if (ImGui::IsItemHovered())
                ImGui::SetTooltip("s32 [0x%08lx] %d..%d%s", d.target, lo, hi, d.p5 ? ", callback after a change" : "");
            break;
        }
        case kDevAction: {
            char label[120];
            bool empty = IsEmptyFunction(d.target);
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s%s  [%s]", d.text, empty ? " (empty in retail)" : "", d.id);
            if (!g_experimental) ImGui::BeginDisabled();
            if (ImGui::Button(label)) QueueItem(d.id, "");
            FavKey(d.id);
            if (!g_experimental) ImGui::EndDisabled();
            if (ImGui::IsItemHovered()) ImGui::SetTooltip("cdecl 0x%08lx(0x%lx)", d.target, d.p1);
            break;
        }
        default:
            break;
        }
        if (note && d.type != kDevLink) { ImGui::Indent(); Note(note); ImGui::Unindent(); }
        ImGui::PopID();
    }
    ImGui::Separator();
    // the retail root links only "Units" and "Chapters"; the other pages are not linked from anywhere any more
    if (ImGui::TreeNode("All pages of the tables (most are not linked from the root in retail)")) {
        for (int p = 0; p < g_devPageCount; ++p) {
            int rows = 0;
            for (int i = 0; i < g_devCount; ++i)
                if (g_dev[i].page == g_devPages[p] && g_dev[i].type != kDevEnd) ++rows;
            DevPageName(g_devPages[p], name, sizeof(name));
            char label[96];
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s (%d rows)##devp%d", name, rows, p);
            if (ImGui::Button(label)) g_devPage = g_devPages[p];
        }
        ImGui::TreePop();
    }
}

void PageTimePlayer() {
    char v[64];
    ValTimeScale(v, sizeof(v));
    float scale = static_cast<float>(atof(v));
    if (!g_timeOk || !g_experimental) ImGui::BeginDisabled();
    if (ImGui::SliderFloat("time scale  [time.scale]", &scale, 0.0f, 10.0f, "%.2f")) {
        char arg[16];
        _snprintf_s(arg, sizeof(arg), _TRUNCATE, "%.3f", scale);
        QueueItem("time.scale", arg);
    }
    if (ImGui::Button("time scale 1.0##ts1")) QueueItem("time.scale", "1");
    if (!g_timeOk || !g_experimental) ImGui::EndDisabled();
    ValPause(v, sizeof(v));
    bool paused = v[0] == '1';
    if (ImGui::Checkbox("freeze world (streamFlags 0x1000)  [time.pause]", &paused)) QueueItem("time.pause", paused ? "1" : "0");
    ValUiHide(v, sizeof(v));
    bool hidden = v[0] == '1';
    if (ImGui::Checkbox("hide HUD  [ui.hide]", &hidden)) QueueItem("ui.hide", hidden ? "1" : "0");
    if (!InLevel()) { ImGui::TextUnformatted("player items: needs a level"); return; }
    ValControl(v, sizeof(v));
    bool control = v[0] == '1';
    if (ImGui::Checkbox("player control  [player.control]", &control)) QueueItem("player.control", control ? "1" : "0");
    if (ImGui::Button("Ragdoll death  [player.die]")) QueueItem("player.die", "");
    if (ImGui::Button("Mark position  [player.mark]")) QueueItem("player.mark", "");
    ImGui::SameLine();
    if (ImGui::Button("Back to mark  [player.recall]")) QueueItem("player.recall", "");
    ValMark(v, sizeof(v));
    Text("mark: %s   (player.teleport x y z over TruLink)", v);
    ValFov(v, sizeof(v));
    float fov = static_cast<float>(atof(v));
    if (fov > 0.05f && fov < 3.1f && ImGui::SliderFloat("camera fov (rad)  [camera.fov]", &fov, 0.2f, 2.5f, "%.3f")) {
        char arg[16];
        _snprintf_s(arg, sizeof(arg), _TRUNCATE, "%.4f", fov);
        QueueItem("camera.fov", arg);
    }
    ImGui::Separator();
    ImGui::TextUnformatted("Weapons / ammo / health (experimental, catalog section 17, not checked live):");
    char ammo[64];
    ValHealth(v, sizeof(v));
    ValAmmo(ammo, sizeof(ammo));
    Text("health %s   [player.health]   reserve ammo %s   [ammo.show / ammo.set <type> <n>]", v, ammo);
    if (g_healthOk && ImGui::Button("Full health  [player.health]")) QueueItem("player.health", "");
    bool inv = g_invincible != 0;
    if (g_healthOk && ImGui::Checkbox("invincible (health = max every frame)  [player.invincible]", &inv))
        QueueItem("player.invincible", inv ? "1" : "0");
    for (const WeaponName &w : kWeapons) {
        char label[64];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "Give %s##wg%d", w.name, w.id);
        if (!g_weaponOk) ImGui::BeginDisabled();
        if (ImGui::Button(label)) QueueItem("weapon.give", w.name);
        if (!g_weaponOk) ImGui::EndDisabled();
        if (w.id != 41 && w.id != 114) ImGui::SameLine();
    }
}

void PageInstances() {
    if (!InLevel()) { ImGui::TextUnformatted("needs a level (no player instance)"); return; }
    static char filter[32] = "";
    ImGui::InputText("name filter", filter, sizeof(filter));
    ImGui::TextWrapped("ids for TruLink: intro id, 0x<address> or #<index> - instance.info / player.goto / instance.bring "
                       "/ unhide / remove");
    int index = 0, shown = 0;
    ForInstances([&](const InstInfo &x) {
        int i = index++;
        if (filter[0] && !strstr(x.name, filter)) return true;
        if (++shown > 200) return false;
        char label[160], arg[16];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "#%d  %s  intro %ld  (%.0f %.0f %.0f)##inst%d", i, x.name, x.intro,
                    x.pos[0], x.pos[1], x.pos[2], i);
        _snprintf_s(arg, sizeof(arg), _TRUNCATE, "#%d", i);
        if (ImGui::TreeNode(label)) {
            if (ImGui::Button("Lara goes there  [player.goto]")) QueueItem("player.goto", arg);
            ImGui::SameLine();
            if (ImGui::Button("Bring to Lara  [instance.bring]")) QueueItem("instance.bring", arg);
            if (ImGui::Button("Unhide  [instance.unhide]")) QueueItem("instance.unhide", arg);
            ImGui::SameLine();
            if (ImGui::Button("Remove  [instance.remove]")) QueueItem("instance.remove", arg);
            ImGui::TreePop();
        }
        return true;
    });
    Text("%d instances, %d shown (max 200)", index, shown > 200 ? 200 : shown);
    if (ImGui::Button("Unhide all  [instance.unhideall]")) QueueItem("instance.unhideall", "");
}

void PageCostumeLive() {
    ImGui::TextWrapped("Live switch (the game's 0x6f0a90, as the costume native 0x79db50): altPlayerObjectID [0xe7f1cc] "
                       "= id, or 0 = next of the cycle list GlobalInfo [0xe7ee50]+4; then player message 35 (weapons).");
    if (!g_switchOk) { ImGui::TextUnformatted("costume switch code check failed"); return; }
    if (!InLevel()) { ImGui::TextUnformatted("needs a level"); return; }
    if (ImGui::Button("Next outfit  [costume.next]")) QueueItem("costume.next", "");
    WORD ids[128];
    int c = GlobalCostumes(ids, 128);
    DWORD now = 0;
    ReadDword(kCostumeNow, &now);
    for (int i = 0; i < c; ++i) {
        char name[64], label[96], arg[16];
        if (!ObjectName(ids[i], name, sizeof(name))) Out(name, sizeof(name), "?");
        _snprintf_s(label, sizeof(label), _TRUNCATE, "%u %s%s##live%d", ids[i], name, ids[i] == now ? "  [current]" : "", i);
        _snprintf_s(arg, sizeof(arg), _TRUNCATE, "%u", ids[i]);
        if (ImGui::Button(label)) QueueItem("costume.set", arg);
    }
    if (c < 0) ImGui::TextUnformatted("no GlobalInfo list");
}

void PageLog() {
    ImGui::TextWrapped("Tails of the Tru*.log files next to the .asi / tru.exe (once per second) and, with log.script on, "
                       "the game's script print / log natives.");
    bool overlay = g_logOverlay != 0;
    if (ImGui::Checkbox("corner overlay  [log.overlay]", &overlay)) InterlockedExchange(&g_logOverlay, overlay ? 1 : 0);
    ImGui::SameLine();
    bool script = g_scriptLog != 0;
    if (!g_scriptOk) ImGui::BeginDisabled();
    if (ImGui::Checkbox("script prints  [log.script]", &script)) QueueItem("log.script", script ? "1" : "0");
    if (!g_scriptOk) ImGui::EndDisabled();
    ImGui::SliderInt("lines  [log.lines]", &g_logLines, 1, 64);
    // sources: every tailed file + "script"
    if (ImGui::Button(g_logFilter[0] ? "all##lf" : "[all]##lf")) g_logFilter[0] = 0;
    for (int i = 0; i < 16; ++i) {
        if (!g_tails[i].used) continue;
        ImGui::SameLine();
        char label[48];
        bool active = _stricmp(g_logFilter, g_tails[i].name) == 0;
        _snprintf_s(label, sizeof(label), _TRUNCATE, active ? "[%s]##lf%d" : "%s##lf%d", g_tails[i].name, i);
        if (ImGui::Button(label)) strncpy_s(g_logFilter, sizeof(g_logFilter), g_tails[i].name, _TRUNCATE);
    }
    ImGui::SameLine();
    if (ImGui::Button(_stricmp(g_logFilter, "script") == 0 ? "[script]##lfs" : "script##lfs"))
        strncpy_s(g_logFilter, sizeof(g_logFilter), "script", _TRUNCATE);
    ImGui::SameLine();
    if (ImGui::Button("clear  [log.clear]")) { char o[64]; RunLogClear("", o, sizeof(o)); }
    {                                                                       // 0.7.2 overlay filter
        char src[300], exc[600];
        ValOvlSources(src, sizeof(src));
        ValOvlExclude(exc, sizeof(exc));
        ImGui::TextWrapped("overlay only: sources %s [log.overlaysources], exclude %s [log.overlayexclude]; the page "
                           "shows every source", src, exc);
    }
    // 0.4: collapse, TruLink reads, severity, rate
    bool collapse = g_logCollapse != 0, hide = g_logHideReads != 0;
    if (ImGui::Checkbox("collapse repeats  [log.collapse]", &collapse)) InterlockedExchange(&g_logCollapse, collapse ? 1 : 0);
    ImGui::SameLine();
    if (ImGui::Checkbox("hide TruLink reads  [log.hidereads]", &hide)) InterlockedExchange(&g_logHideReads, hide ? 1 : 0);
    ImGui::TextUnformatted("show  [log.level]:");
    for (int i = 0; i < 3; ++i) {
        ImGui::SameLine();
        char label[32];
        _snprintf_s(label, sizeof(label), _TRUNCATE, g_logMinLevel == i ? "[%s]##ll%d" : "%s##ll%d",
                    i == 0 ? "all" : i == 1 ? "warnings + errors" : "errors", i);
        if (ImGui::Button(label)) g_logMinLevel = i;
    }
    ImGui::SliderInt("max lines per source and second (0 = off)  [log.rate]", &g_logRate, 0, 200);
    static LogLine lines[64];
    int c = CopyLines(lines, g_logLines, g_logFilter);
    ImGui::BeginChild("##logchild", ImVec2(0.0f, ImGui::GetTextLineHeightWithSpacing() * 14.0f), true);
    for (int i = 0; i < c; ++i) {
        BYTE sev = lines[i].sev;
        if (sev) ImGui::PushStyleColor(ImGuiCol_Text, sev == 2 ? ImVec4(1.0f, 0.5f, 0.4f, 1.0f) : ImVec4(1.0f, 0.85f, 0.4f, 1.0f));
        char line[300];
        FormatLine(lines[i], line, sizeof(line), 220);
        ImGui::TextWrapped("%s", line);
        if (sev) ImGui::PopStyleColor();
    }
    ImGui::EndChild();
    Text("script prints so far: %ld; lines mentioning an exception: %ld; exceptions caught by TruMenu: %ld", g_scriptCount,
         g_exceptionLines, g_ownExceptions);
    Text("repeats collapsed: %ld; TruLink reads hidden: %ld; dropped by the rate limit: %ld", g_logCollapsed, g_logHidden,
         g_logDropped);
}

void PageMedia() {
    char list[1024];
    ValVideoList(list, sizeof(list));
    Text("Movies: %s   [media.video.list]", list);
    DWORD state = 0;
    ReadDword(kMainState, &state);
    char loop[64];
    ValMenuLoop(loop, sizeof(loop));
    Text("main state [0x%08lx] = %lu (10 = main menu); menu background loop [0x%08lx] = %s", kMainState, state,
         kMenuLoopPtr, loop);
    if (!g_experimental) return;
    char copy[1024];
    strncpy_s(copy, sizeof(copy), list, _TRUNCATE);
    char *context = nullptr;
    int i = 0;
    for (char *name = strtok_s(copy, " ", &context); name && strncmp(name, "no", 2); name = strtok_s(nullptr, " ", &context), ++i) {
        char label[96];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "Play %s##vp%d", name, i);
        if (state != 10 || !g_movieOk) ImGui::BeginDisabled();
        if (ImGui::Button(label)) QueueItem("media.video.play", name);
        if (state != 10 || !g_movieOk) ImGui::EndDisabled();
        ImGui::SameLine();
        _snprintf_s(label, sizeof(label), _TRUNCATE, "as menu loop##vl%d", i);
        if (ImGui::Button(label)) QueueItem("media.video.menuloop", name);
    }
    if (ImGui::Button("menu loop back to medsea_loop")) QueueItem("media.video.menuloop", "");
    ImGui::TextWrapped("0x4a12b0(name, loop) is a blocking-style player (its callers loop while it plays): play only "
                       "from the main menu; experimental. The menu loop name is read when the main menu (re)starts "
                       "its background movie (0x5daf35).");
}

void DrawLogOverlay() {
    static LogLine lines[64];
    int c = CopyLines(lines, g_logLines, g_logFilter, true);   // 0.7.2: + [Log] OverlaySources / OverlayExclude
    ImGuiViewport *vp = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(vp->WorkPos.x + 10.0f, vp->WorkPos.y + vp->WorkSize.y - 10.0f), ImGuiCond_Always,
                            ImVec2(0.0f, 1.0f));
    ImGui::SetNextWindowBgAlpha(0.4f);
    ImGui::SetNextWindowSizeConstraints(ImVec2(0.0f, 0.0f), ImVec2(vp->WorkSize.x * 0.6f, vp->WorkSize.y * 0.5f));
    ImGuiWindowFlags flags = ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoNav |
                             ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoFocusOnAppearing |
                             ImGuiWindowFlags_NoSavedSettings;
    if (ImGui::Begin("##TruMenuLog", nullptr, flags)) {
        for (int i = 0; i < c; ++i) {
            char line[300];
            FormatLine(lines[i], line, sizeof(line), 160);
            BYTE sev = lines[i].sev;
            if (sev) ImGui::PushStyleColor(ImGuiCol_Text, sev == 2 ? ImVec4(1.0f, 0.5f, 0.4f, 1.0f) : ImVec4(1.0f, 0.85f, 0.4f, 1.0f));
            ImGui::TextUnformatted(line);
            if (sev) ImGui::PopStyleColor();
        }
        if (!c && g_ovlHidden) ImGui::Text("(log: no lines - %ld kept out by [Log] OverlaySources / OverlayExclude)", g_ovlHidden);
        else if (!c) ImGui::TextUnformatted("(log: no lines)");
    }
    ImGui::End();
}

void DrawMenu() {
    ImGuiViewport *vp = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(vp->WorkPos.x + 40.0f, vp->WorkPos.y + 40.0f), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(vp->WorkSize.x * 0.5f, vp->WorkSize.y * 0.7f), ImGuiCond_FirstUseEver);
    bool justOpened = InterlockedExchange(&g_menuJustOpened, 0) != 0;
    if (justOpened) ImGui::SetNextWindowFocus();
    bool open = true;
    bool began = ImGui::Begin(kMenuTitle, &open, ImGuiWindowFlags_NoCollapse);
    g_menuPos = ImGui::GetWindowPos();       // 0.6: the command bar sits directly under this window
    g_menuSize = ImGui::GetWindowSize();
    g_menuRectOk = true;
    if (began) {
        // 0.4: TO TEST first, only while the list holds rows
        int open04, ok04, fail04, skip04, total04;
        TestCounts(&open04, &ok04, &fail04, &skip04, &total04);
        bool testShown = false;
        if (total04) {
            char header[96];
            _snprintf_s(header, sizeof(header), _TRUNCATE, "TO TEST (%d open, %d ok, %d fail, %d skip)###totest", open04,
                        ok04, fail04, skip04);
            ImGui::PushStyleColor(ImGuiCol_Header, ImVec4(0.55f, 0.35f, 0.05f, 1.0f));
            bool show = ImGui::CollapsingHeader(header, ImGuiTreeNodeFlags_DefaultOpen);
            ImGui::PopStyleColor();
            if (show) { PageTests(); testShown = true; }
        }
        if (!testShown) InterlockedExchange(&g_testFocus, 0);
        if (ImGui::CollapsingHeader("Quick access / Favourites", ImGuiTreeNodeFlags_DefaultOpen)) PageFavourites();
        if (ImGui::CollapsingHeader("Status")) PageStatus();
        if (ImGui::CollapsingHeader("Developer menu (original)")) PageDev();
        if (ImGui::CollapsingHeader("Time / player / HUD")) PageTimePlayer();
        if (ImGui::CollapsingHeader("Instances")) PageInstances();
        if (ImGui::CollapsingHeader("Outfits (live switch)")) PageCostumeLive();
        if (ImGui::CollapsingHeader("Debug / Log")) PageLog();
        if (ImGui::CollapsingHeader("Media: videos")) PageMedia();
        if (ImGui::CollapsingHeader("Settings")) PageSettings();
        if (ImGui::CollapsingHeader("Overlay: Lara's position")) PageOverlay();
        if (ImGui::CollapsingHeader("Free camera")) PageCamera();
        if (ImGui::CollapsingHeader("Cheat / flight")) PageCheat();
        if (ImGui::CollapsingHeader("Markup / collision draw")) PageMarkup();
        if (ImGui::CollapsingHeader("Level select")) PageLevel();
        if (ImGui::CollapsingHeader("Outfits (next level load)")) PageOutfits();
        if (ImGui::CollapsingHeader("Dev channel")) {
            ImGui::TextWrapped("tru.exe has no developer channel (TCP 9264 is FMOD's profiler).");
            Todo("re-enable the compiled-out log stub 0x6457a0 (filtered by channel id) and show it here.");
        }
        ImGui::Separator();
        Text("last action: %s", g_lastAction);
        if (ImGui::Button("Close menu")) open = false;
    }
    ImGui::End();
    if (!open && g_menuOpen) ToggleMenu("close button");
    if (g_menuOpen) DrawCmdBar(justOpened);   // 0.6, a window of its own: the menu window's navigation is unchanged
}

void DrawOverlay() {
    float p[3], r[3];
    DWORD instance = 0;
    ImGuiViewport *vp = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(vp->WorkPos.x + 10.0f, vp->WorkPos.y + 10.0f), ImGuiCond_Always);
    ImGui::SetNextWindowBgAlpha(0.4f);
    ImGuiWindowFlags flags = ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoNav |
                             ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoFocusOnAppearing |
                             ImGuiWindowFlags_NoSavedSettings;
    if (ImGui::Begin("##TruMenuOverlay", nullptr, flags)) {
        if (ReadLara(p, r, &instance))
            Text("Lara  %.0f  %.0f  %.0f   rot %.2f", p[0], p[1], p[2], r[2]);
        else
            ImGui::TextUnformatted("Lara  -");
    }
    ImGui::End();
}

// optional plugin TruGuard: counters + last site, independent of the player pointer check
void DrawGuardOverlay() {
    GuardIntFn count = GuardIntExport("TruGuardCount"), distinct = GuardIntExport("TruGuardDistinct"),
                mode = GuardIntExport("TruGuardMode");
    if (!count || !distinct || !mode) return;
    GuardTextFn last = GuardTextExport("TruGuardLast");
    char lastText[512] = "";
    if (last) last(lastText, sizeof(lastText));
    ImGuiViewport *vp = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(vp->WorkPos.x + vp->WorkSize.x - 10.0f, vp->WorkPos.y + 10.0f), ImGuiCond_Always,
                            ImVec2(1.0f, 0.0f));
    ImGui::SetNextWindowBgAlpha(0.4f);
    ImGui::SetNextWindowSizeConstraints(ImVec2(0.0f, 0.0f), ImVec2(vp->WorkSize.x * 0.45f, vp->WorkSize.y));
    ImGuiWindowFlags flags = ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoNav |
                             ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoFocusOnAppearing |
                             ImGuiWindowFlags_NoSavedSettings;
    if (ImGui::Begin("##TruGuardOverlay", nullptr, flags)) {
        Text("TruGuard  mode %d  -  %d exception(s) at %d site(s)", mode(), count(), distinct());
        if (lastText[0]) ImGui::TextWrapped("%s", lastText);
    }
    ImGui::End();
}

void Render(IDirect3DDevice9 *device) {
    // front end / loading: if the game has not polled the pad slot for 250 ms, read the pad here (toggle +
    // navigation) and run queued requests from this hook (the game's Present call)
    bool padIdle = GetTickCount() - g_lastPadHookTick > 250;
    XInputGetStateFn poll = g_selfPoll ? g_selfPoll : (padIdle ? RealXInput() : nullptr);
    if (poll) SelfPoll(poll);
    if (padIdle != g_padModeIdle) {
        g_padModeIdle = padIdle;
        Log(2, padIdle ? "pad: slot not polled - reading the pad in Present" : "pad: slot polled again");
    }
    if (padIdle && g_reqPending) RunPending();
    if (padIdle) WeaponsTick();
    KeyboardToggle();
    MouseTick();                                 // 0.7: hold / release the game's cursor calls with the menu
    PauseTick();                                 // 0.7.1 [Menu] PauseGame
    AutoStartTick();                             // 0.7.1 [Test] AutoStart
    if (!g_menuOpen && !g_overlay && !g_logOverlay && !g_guardOverlay && !g_drawMarkup) return;
    if (g_imguiFailed) return;
    if (!g_imguiReady) {
        g_imguiReady = InitImGui(device);
        if (!g_imguiReady) { g_imguiFailed = true; return; }
    } else if (device != g_imguiDevice) {
        Log(1, "imgui: device changed 0x%08lx -> 0x%08lx", reinterpret_cast<DWORD>(g_imguiDevice),
            reinterpret_cast<DWORD>(device));
        ImGui_ImplDX9_Shutdown();
        ImGui_ImplDX9_Init(device);
        g_imguiDevice = device;
    }
    ImGuiIO &io = ImGui::GetIO();
    io.MouseDrawCursor = g_menuOpen != 0;
    ImGui_ImplDX9_NewFrame();
    ImGui_ImplWin32_NewFrame();
    // draw in back-buffer pixels: the window client size can differ (windowed proxies scale the back buffer)
    IDirect3DSurface9 *back = nullptr;
    if (SUCCEEDED(device->GetBackBuffer(0, 0, D3DBACKBUFFER_TYPE_MONO, &back)) && back) {
        D3DSURFACE_DESC desc = {};
        // (0.7: with [Menu] FreeMouse the window procedure scales the mouse messages from client to back-buffer pixels)
        if (SUCCEEDED(back->GetDesc(&desc)) && desc.Width && desc.Height) {
            io.DisplaySize = ImVec2(static_cast<float>(desc.Width), static_cast<float>(desc.Height));
            g_bbWidth = desc.Width;
            g_bbHeight = desc.Height;
        }
        back->Release();
    }
    FeedGamepad(io);
    ImGui::NewFrame();
    if (g_drawMarkup) DrawMarkup();
    if (g_overlay) DrawOverlay();
    if (g_logOverlay) DrawLogOverlay();
    if (g_guardOverlay) DrawGuardOverlay();
    if (g_menuOpen) DrawMenu();
    // 0.7.1: g_oskOpen is kept on close (owner decision 2026-11-02: the keyboard comes back with the menu when it was
    // open at the last close - in 0.7 only by chance, when Render returned before this line)
    if (!g_menuOpen) {
        g_cmdOwnPad = false;
        g_cmdTextActive = false;
        g_cmdPadMode = false;
        g_oskBackClosed = false;
        g_typeFocusFrames = 0;
    }
    ImGui::EndFrame();
    // 0.7: also while the on-screen keyboard is open - a real key then switches to typing instead of reaching the game
    InterlockedExchange(&g_cmdWantText, g_menuOpen && (io.WantTextInput || g_oskOpen || g_typeFocusFrames > 0) ? 1 : 0);
    if (SUCCEEDED(device->BeginScene())) {
        ImGui::Render();
        ImGui_ImplDX9_RenderDrawData(ImGui::GetDrawData());
        device->EndScene();
    }
}

HRESULT STDMETHODCALLTYPE PresentHook(IDirect3DDevice9 *device, const RECT *source, const RECT *dest, HWND window,
                                      const RGNDATA *dirty) {
    static bool seen = false;
    if (!seen) { seen = true; Log(1, "d3d9: first IDirect3DDevice9::Present call"); }
    Render(device);
    return g_presentOriginal(device, source, dest, window, dirty);
}

// the game may present through the implicit swap chain instead of the device (IDirect3DSwapChain9::Present, slot 3)
typedef HRESULT(STDMETHODCALLTYPE *SwapPresentFn)(IDirect3DSwapChain9 *, const RECT *, const RECT *, HWND,
                                                  const RGNDATA *, DWORD);
volatile SwapPresentFn g_swapPresentOriginal = nullptr;
volatile LONG g_inDevicePresent = 0;

HRESULT STDMETHODCALLTYPE SwapPresentHook(IDirect3DSwapChain9 *chain, const RECT *source, const RECT *dest,
                                          HWND window, const RGNDATA *dirty, DWORD flags) {
    static bool seen = false;
    if (!seen) { seen = true; Log(1, "d3d9: first IDirect3DSwapChain9::Present call"); }
    IDirect3DDevice9 *device = nullptr;
    if (SUCCEEDED(chain->GetDevice(&device)) && device) {
        Render(device);
        device->Release();
    }
    return g_swapPresentOriginal(chain, source, dest, window, dirty, flags);
}

HRESULT STDMETHODCALLTYPE ResetHook(IDirect3DDevice9 *device, D3DPRESENT_PARAMETERS *params) {
    if (g_imguiReady) ImGui_ImplDX9_InvalidateDeviceObjects();
    HRESULT hr = g_resetOriginal(device, params);
    Log(hr < 0 ? 0 : 3, "d3d9: Reset 0x%08lx", static_cast<DWORD>(hr));
    return hr;                               // device objects are re-created by the next ImGui_ImplDX9_NewFrame
}

void HookDevice(IDirect3DDevice9 *device) {
    void **vtable = nullptr;
    if (!ReadDword(reinterpret_cast<DWORD>(device), reinterpret_cast<DWORD *>(&vtable)) || !vtable) return;
    PatchVtable(vtable, 16, reinterpret_cast<void *>(&ResetHook), reinterpret_cast<void *volatile *>(&g_resetOriginal),
                "Reset");
    PatchVtable(vtable, 17, reinterpret_cast<void *>(&PresentHook),
                reinterpret_cast<void *volatile *>(&g_presentOriginal), "Present");
    IDirect3DSwapChain9 *chain = nullptr;
    if (SUCCEEDED(device->GetSwapChain(0, &chain)) && chain) {
        void **chainVtable = nullptr;
        if (ReadDword(reinterpret_cast<DWORD>(chain), reinterpret_cast<DWORD *>(&chainVtable)) && chainVtable)
            PatchVtable(chainVtable, 3, reinterpret_cast<void *>(&SwapPresentHook),
                        reinterpret_cast<void *volatile *>(&g_swapPresentOriginal), "SwapChain Present");
        chain->Release();
    }
    g_device = device;
    g_d3dMode = "Present / Reset hooked on the game's device";
}

// import slot of GetProcAddress: only when it holds a function inside a loaded module (resolved imports)
bool PatchGetProc() {
    DWORD current = 0;
    if (!ReadDword(kGetProcSlot, &current) || !current) return false;
    if (current == reinterpret_cast<DWORD>(&GetProcHook)) return true;
    char owner[MAX_PATH];
    ModuleOf(reinterpret_cast<const void *>(current), owner, sizeof(owner));
    if (owner[0] == '?') return false;
    g_getProcOriginal = reinterpret_cast<GetProcAddressFn>(current);
    if (!WriteDword(kGetProcSlot, reinterpret_cast<DWORD>(&GetProcHook))) {
        Log(0, "pad: VirtualProtect on the import slot failed (%lu) - pad filter off", GetLastError());
        g_padMode = "import slot not writable";
        return true;
    }
    g_padMode = "import filter set, waiting for the game to load XInput";
    Log(1, "pad: import slot 0x%08lx (GetProcAddress 0x%08lx in %s) filtered", kGetProcSlot, current, owner);
    return true;
}

// the pointer was already filled when we came (late load): take it over only if nobody wrapped it yet
// (hook once; if another plugin wrapped it first we go on top of that wrapper - the re-entry guard in PadHook keeps a
// wrapper that re-wraps us from recursing)
bool PlacePadHook(DWORD current, const char *mode) {
    char owner[MAX_PATH];
    ModuleOf(reinterpret_cast<const void *>(current), owner, sizeof(owner));
    if (IsXInputModule(reinterpret_cast<const void *>(current))) g_padReal = reinterpret_cast<XInputGetStateFn>(current);
    g_padOriginal = reinterpret_cast<XInputGetStateFn>(current);
    if (InterlockedCompareExchange(reinterpret_cast<volatile LONG *>(kPadPointer),
                                   static_cast<LONG>(reinterpret_cast<DWORD>(&PadHook)),
                                   static_cast<LONG>(current)) != static_cast<LONG>(current))
        return false;
    g_padMode = mode;
    Log(1, "pad: pointer 0x%08lx held 0x%08lx (%s) - PadHook placed (%s)", kPadPointer, current, owner, mode);
    return true;
}

void TakePointerLate(DWORD current) {
    if (current == reinterpret_cast<DWORD>(&PadHook) || PlacePadHook(current, "PadHook set on the pointer (late load)"))
        return;
    // could not swap (the slot changed under us): read the pad ourselves - toggle and navigation work, no blocking
    g_selfPoll = RealXInput();
    g_padMode = "pointer busy - own reads, game input NOT blocked";
    Log(0, "pad: pointer 0x%08lx changed while hooking - menu reads the pad itself, input to the game is not blocked",
        kPadPointer);
}

// chaining rule: re-hook only when the slot points into the real XInputGetState again (game re-loaded XInput)
void CheckPadSlot() {
    DWORD current = 0;
    if (!ReadDword(kPadPointer, &current) || !current) return;
    // never placed yet (the game took XInput past our import filter and other plugins chained first): go on top once
    if (!g_padOriginal && current != reinterpret_cast<DWORD>(&PadHook)) {
        TakePointerLate(current);
        return;
    }
    if (IsXInputModule(reinterpret_cast<const void *>(current)))
        PlacePadHook(current, "PadHook re-placed (slot pointed to XInput again)");
}

// pad setup: the import filter if the pointer is still empty, else the late path; false = try again later
bool SetupPad() {
    DWORD pointer = 0;
    if (ReadDword(kPadPointer, &pointer) && pointer) {
        TakePointerLate(pointer);
        return true;
    }
    return PatchGetProc();
}

DWORD WINAPI WorkerThread(LPVOID) {
    bool padDone = !g_padCodeOk || g_padSetupDone;
    while (!g_stop) {
        if (!padDone) padDone = SetupPad();
        else if (g_padCodeOk && !g_selfPoll) CheckPadSlot();
        if (g_d3dCodeOk) {
            DWORD manager = 0, device = 0;
            if (ReadDword(kDeviceManager, &manager) && manager && ReadDword(manager + kDeviceField, &device) && device &&
                device != reinterpret_cast<DWORD>(g_device))
                HookDevice(reinterpret_cast<IDirect3DDevice9 *>(device));
        }
        UnitTick();                                  // 0.7.1 [Log] UnitChanges (read-only)
        LogTailTick();
        Sleep(g_device ? 250 : 50);
    }
    return 0;
}

void ReadOptions(const char *dir) {
    char ini[MAX_PATH], text[32];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruMenu.ini", dir);
    // defaults: the kOpts table (also the source of the shipped TruMenu.ini)
    g_enabled = OptInt(ini, "Menu", "Enabled");
    g_logLevel = OptInt(ini, "Menu", "LogLevel");
    g_toggleButtons = static_cast<WORD>(OptInt(ini, "Menu", "ToggleButtons"));
    if (!g_toggleButtons) g_toggleButtons = kPadL3 | kPadR3;
    g_toggleKey = OptInt(ini, "Menu", "ToggleKey");
    OptString(ini, "Menu", "Scale", text, sizeof(text));
    g_scale = static_cast<float>(atof(text));
    if (!(g_scale >= 0.5f && g_scale <= 4.0f)) g_scale = static_cast<float>(atof(OptDefault("Menu", "Scale")));
    g_overlayAtStart = OptInt(ini, "Menu", "Overlay");
    g_blockInput = OptInt(ini, "Pad", "BlockInput");
    g_experimental = OptInt(ini, "Cheat", "Experimental");
    OptString(ini, "Cheat", "FlightSpeed", text, sizeof(text));
    g_flightSpeed = static_cast<float>(atof(text));
    if (!(g_flightSpeed > 0.0f && g_flightSpeed < 1000.0f))
        g_flightSpeed = static_cast<float>(atof(OptDefault("Cheat", "FlightSpeed")));
    OptString(ini, "Levels", "List", g_levelList, sizeof(g_levelList));
    strncpy_s(g_iniPath, sizeof(g_iniPath), ini, _TRUNCATE);
    OptString(ini, "Favorites", "Ids", g_favs, sizeof(g_favs));
    if (!g_favs[0]) strncpy_s(g_favs, sizeof(g_favs), kFavDefault, _TRUNCATE);
    g_logOverlayAtStart = OptInt(ini, "Log", "Overlay");
    g_logLinesAtStart = OptInt(ini, "Log", "Lines");
    if (g_logLinesAtStart < 1 || g_logLinesAtStart > 64) g_logLinesAtStart = atoi(OptDefault("Log", "Lines"));
    g_scriptLogAtStart = OptInt(ini, "Log", "Script");
    // 0.4: applied at once (also by settings.reset)
    InterlockedExchange(&g_logCollapse, OptInt(ini, "Log", "Collapse") ? 1 : 0);
    InterlockedExchange(&g_logHideReads, OptInt(ini, "Log", "HideLinkReads") ? 1 : 0);
    g_logMinLevel = OptInt(ini, "Log", "MinLevel");
    if (g_logMinLevel < 0 || g_logMinLevel > 2) g_logMinLevel = atoi(OptDefault("Log", "MinLevel"));
    g_logRate = OptInt(ini, "Log", "MaxLinesPerSecond");
    if (g_logRate < 0 || g_logRate > 10000) g_logRate = atoi(OptDefault("Log", "MaxLinesPerSecond"));
    // 0.6
    g_cmdEnabled = OptInt(ini, "Cmd", "Enabled");
    g_cmdHistSize = OptInt(ini, "Cmd", "HistorySize");
    if (g_cmdHistSize < 1 || g_cmdHistSize > 64) g_cmdHistSize = atoi(OptDefault("Cmd", "HistorySize"));
    // 0.7
    g_freeMouse = OptInt(ini, "Menu", "FreeMouse");
    g_cmdFocusButton = static_cast<WORD>(OptInt(ini, "Cmd", "FocusButton"));
    g_cmdKeyboard = OptInt(ini, "Cmd", "Keyboard");
    g_cmdUpHistory = OptInt(ini, "Cmd", "UpOpensHistory");
    g_cmdFirstPressFocus = OptInt(ini, "Cmd", "FirstPadPressOnlyFocuses");
    // 0.7.1
    g_blockGameInput = OptInt(ini, "Menu", "BlockGameInput");
    g_pauseGame = OptInt(ini, "Menu", "PauseGame");
    g_unitChanges = OptInt(ini, "Log", "UnitChanges");
    OptString(ini, "Test", "AutoStart", g_autoStart, sizeof(g_autoStart));
    g_autoStartDelay = OptInt(ini, "Test", "AutoStartDelay");
    if (g_autoStartDelay < 1 || g_autoStartDelay > 60) g_autoStartDelay = atoi(OptDefault("Test", "AutoStartDelay"));
    g_outfitRule = OptInt(ini, "Levels", "OutfitRule") != 0;                  // 0.7.2
    EnterCriticalSection(&g_logRingLock);                                    // 0.7.2 overlay filter
    OptString(ini, "Log", "OverlaySources", g_ovlSources, sizeof(g_ovlSources));
    OptString(ini, "Log", "OverlayExclude", g_ovlExclude, sizeof(g_ovlExclude));
    LeaveCriticalSection(&g_logRingLock);
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruMenu.log", dir);
    strncpy_s(g_asiDir, sizeof(g_asiDir), dir, _TRUNCATE);
    DWORD exeLen = GetModuleFileNameA(nullptr, g_exeDir, MAX_PATH);
    while (exeLen > 0 && g_exeDir[exeLen - 1] != '\\' && g_exeDir[exeLen - 1] != '/') --exeLen;
    g_exeDir[exeLen] = 0;
    ReadOptions(dir);
    Log(1, "%s loaded (enabled %d, toggle 0x%04x, key %d, block %d, scale %.2f, experimental %d)", kVersion, g_enabled,
        g_toggleButtons, g_toggleKey, g_blockInput, g_scale, g_experimental);
    if (!g_enabled) { Log(1, "disabled by TruMenu.ini - nothing hooked"); return; }
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    g_baseOk = base == kImageBase;
    if (!g_baseOk) { Log(0, "image base 0x%08lx, expected 0x%08lx - not hooked", base, kImageBase); return; }
    g_padCodeOk = HexBytesAt(kPadLoader, kPadLoaderBytes) && HexBytesAt(kPadCallSite, kPadCallBytes) &&
                  HexBytesAt(kXInputName, "58496e7075744765745374617465 00");
    if (!g_padCodeOk) Log(0, "pad: XInput loader 0x%08lx / poll 0x%08lx do not match - pad hook off (keyboard toggle "
                             "only)", kPadLoader, kPadCallSite);
    g_d3dCodeOk = HexBytesAt(kD3dCreate, kD3dCreateBytes) && HexBytesAt(kD3dStore, kD3dStoreBytes) &&
                  HexBytesAt(kCreateDeviceCall, kCreateDeviceBytes) && HexBytesAt(kCreateDeviceCall2, kCreateDeviceBytes2);
    if (!g_d3dCodeOk) Log(0, "d3d9: device manager code 0x%08lx does not match - no menu drawing", kD3dCreate);
    g_playerOk = HexBytesAt(kPlayerReader, kPlayerReaderBytes);
    g_postOk = HexBytesAt(kInstancePost, kInstancePostBytes);
    g_cameraOk = HexBytesAt(kCameraSetMode, kCameraSetModeBytes) && HexBytesAt(kCameraRestore, kCameraRestoreBytes);
    g_levelOk = HexBytesAt(kLevelChange, kLevelChangeBytes) && HexBytesAt(kLevelNameCopy, "83c738 8bd7 8bc6 2bd6");
    g_frameOk = HexBytesAt(kFrameStore, kFrameStoreBytes);
    // costume: the level load's choice, the reset, the state save, name table lookup, validator, type-table operand
    // (the original table or a copy outside tru.exe, e.g. TruDlc2Player's)
    DWORD typeTable = 0;
    bool typeOk = HexBytesAt(kTypeLookup, "3935") && ReadDword(kTypeLookup + 2, &typeTable) &&
                  (typeTable == kTypeTableOrig || typeTable < kImageBase || typeTable >= 0x01000000);
    g_costumeOk = HexBytesAt(kLevelLoadChoice, kLevelLoadChoiceBytes) && HexBytesAt(kResetCostume, kResetCostumeBytes) &&
                  HexBytesAt(kSaveCostume, kSaveCostumeBytes) && HexBytesAt(kNameLookup, kNameLookupBytes) &&
                  HexBytesAt(kCostumeValid, kCostumeValidBytes) && typeOk;
    g_unitOk = HexBytesAt(kUnitLookup, kUnitLookupBytes) && HexBytesAt(kDefaultCostume, kDefaultCostumeBytes);
    // 0.3: every address used by the new items, by an instruction of the game that uses it (README "0.3 facts")
    g_timeOk = HexBytesAt(0x005d3d25, "d915d0f1e700") && HexBytesAt(0x005da3a0, "d905d0f1e700");
    g_pauseOk = HexBytesAt(0x00555d40, "810db8f0e70000002000");     // Restore Game: streamFlags |= 0x200000
    g_controlOk = HexBytesAt(0x005d5f45, "c605e6b48a0001") && HexBytesAt(0x005d5f60, "c605e6b48a0000");
    g_uiOk = HexBytesAt(0x005a434c, "803da0c9cd0000");
    // the game's own walk at 0x5d467d: esi = [0xd98d54]; ... esi = [esi+8]
    g_instOk = HexBytesAt(0x005b2ec6, "890d548dd900") && HexBytesAt(0x005d467d, "8b35548dd900 85f6 7410 56 e8e377feff 8b7608");
    g_removeOk = HexBytesAt(kRemoveInstance, kRemoveInstanceBytes) && g_instOk;
    g_switchOk = HexBytesAt(kCostumeSwitch, kCostumeSwitchBytes) && HexBytesAt(kCostumeSwitchAlt, kCostumeSwitchAltBytes) &&
                 HexBytesAt(0x006f0ac7, "8b1550eee700 8b7a04") && HexBytesAt(0x0079db50, "8b4c2404 e947b1fdff");
    g_movieOk = HexBytesAt(kMoviePlay, kMoviePlayBytes);
    g_mainStateOk = HexBytesAt(0x005d56e0, "a160ede700 83f806");
    DWORD loopPtr = 0;
    g_menuLoopOk = HexBytesAt(0x005daf35, "8b1520bf8a00 6a01 52 e86d63ecff") && ReadDword(kMenuLoopPtr, &loopPtr) &&
                   loopPtr == kMenuLoopOrig;
    // markup walk 0x5c3ce0 (box list +0x14, MarkUp +0x20 / +0x34, poly line +0x58, next +4), its caller with
    // [0xdb94cc], and the projection 0x49f630 (matrix, focal, centre constants)
    g_drawOk = HexBytesAt(0x005c3ce8, "8b5914 85db") && HexBytesAt(0x005c3d1e, "8b4320 d907 d84034") &&
               HexBytesAt(0x005c3d54, "d94034 8b4858") && HexBytesAt(0x005c3da2, "8b5b04 85db") &&
               HexBytesAt(0x005d3349, "8b0dcc94db00 e88c09ffff") && HexBytesAt(0x0049f64e, "d9050039a000") &&
               HexBytesAt(0x0049f67f, "d8052039a000") && HexBytesAt(0x0049f6f8, "d905d0068900") &&
               HexBytesAt(0x0049f702, "dc05003a8400") && HexBytesAt(0x0049f713, "dc05c8548400") && g_playerOk;
    // weapons / ammo / health (catalog 17): give-by-name, the HUD's reserve reader, GetHealth, MaxHealth
    g_weaponOk = HexBytesAt(kGiveWeapon, "8b44240c 8b542404 56 8bf1 8b4c240c 50 51 52 e86995eaff") && g_mainStateOk;
    g_ammoOk = HexBytesAt(0x006e8475, "0fb784511c050000");
    g_healthOk = HexBytesAt(0x006e7860, "a158dbfa00 85c0 7407 d98028060000 c3") &&
                 HexBytesAt(kMaxHealth, "51 a16492c500 8b80a4ef0300 8b1550eee700");
    g_scriptOk = HexBytesAt(0x007b3990, "68305e7900 6a07");            // native 7 registration (NsCoreBase)
    for (int i = 0; i < kNativeCount && g_scriptOk; ++i) g_scriptOk = HexBytesAt(g_natives[i].addr, g_natives[i].bytes);
    // 0.4: weapon slots (the game's handle check 0x5b39d0 and the slot reader 0x6e7b90: right +4 / +8, left +0xc /
    // +0x10), MaxAmmo 0x6eeae0 (6-entry jump table), GiveObject 0x555f60 and the save-restore callback 0x715e90
    g_slotsOk = HexBytesAt(0x005b39d0, "8b4c2404 85c9 740e 8b01 85c0 7408 8b5044 3b5104") &&
                HexBytesAt(0x006e7bb9, "8b543e10 8b4c3e0c") && HexBytesAt(0x006e7bde, "8b443e04 8b4c3e08") &&
                HexBytesAt(0x006e7b98, "83fe0e") && g_playerOk;
    g_maxAmmoOk = HexBytesAt(kMaxAmmo, "0fbe442404 83f805 0f8779010000 ff24856cec6e00") &&
                  HexBytesAt(0x006eec67, "660dffff c3") && g_playerOk;
    g_gearOk = HexBytesAt(kGiveObject, "56 8b74240c 56 e8e5d90500 8b54240c 83c404 85c0 7410") &&
               HexBytesAt(kGearCallback, "8b44240c 83e800 742a 83e801 754b 8b442408 8b4810 8b5160") &&
               HexBytesAt(0x00715eb2, "a158dbfa00 8b8800050000") && g_mainStateOk && g_playerOk;
    _snprintf_s(g_testPath, sizeof(g_testPath), _TRUNCATE, "%sTruMenu.tests.txt", g_exeDir);
    TestLoad();
    _snprintf_s(g_cmdHistPath, sizeof(g_cmdHistPath), _TRUNCATE, "%sTruMenu.history.txt", g_exeDir);   // 0.6
    CmdHistLoad();
    Log(1, "0.7 cmd: focus button 0x%04x, keyboard %d, Up opens history %d, first pad press only focuses %d; free mouse %d",
        g_cmdFocusButton, g_cmdKeyboard, g_cmdUpHistory, g_cmdFirstPressFocus, g_freeMouse);
    MouseSetup();                                                                                       // 0.7
    // 0.7.1: keyboard (vtable slot), mission start natives, Lara's stream unit, pause option, AutoStart
    KbdSetup();
    g_missionOk = MissionCheck();
    g_streamNameOk = g_unitOk && HexBytesAt(0x005c1bf0, "a148f1e700 53 55 56 8b3594f0e700 57 8bbee0000000") &&
                     HexBytesAt(0x005c1c28, "e823ffffff 8b0db0a2db00 8d680c 55 6868428500") &&
                     HexBytesAt(0x005c1c4e, "893d48f1e700") &&
                     HexBytesAt(0x005c1b9c, "be44abdb00 8a06 84c0 7415 3c04 7411 8d4608") &&
                     HexBytesAt(0x005dfc88, "8b1548f1e700 3b90e0000000");
    if (g_pauseGame)
        g_pauseMode = g_pauseOk ? "ready (time.pause bit set while the menu is open)"
                                : "NOT verified (streamFlags check failed) - the game runs while the menu is open";
    if (g_autoStart[0])
        g_autoStartMode = g_missionOk ? "armed (level.start once the main menu is up)"
                                      : "armed - mission path NOT verified, fallback level.load (intro skipped)";
    Log(1, "0.7.1: block game input %d (keyboard %s), pause game %d (%s), mission start path %d, stream unit name %d "
           "(unit changes %d), AutoStart '%s' delay %d s (%s)", g_blockGameInput, g_kbdOk ? "hooked" : "not hooked",
        g_pauseGame, g_pauseMode, g_missionOk ? 1 : 0, g_streamNameOk ? 1 : 0, g_unitChanges, g_autoStart,
        g_autoStartDelay, g_autoStartMode);
    if (g_unitChanges && !g_streamNameOk)
        Log(0, "0.7.1: stream unit code did not match - [Log] UnitChanges off (status.unit shows GameTracker+0x38 only)");
    // 0.7.2: main state 2 / 9 (mission start pending) and f27's 2nd argument = the selection byte [0xfae8d9]
    g_pendingOk = PendingCheck();
    g_outfitRuleOk = g_missionOk && HexBytesAt(0x0077e17c, "807d0c00") && HexBytesAt(0x0077e186, "0f95c2") &&
                     HexBytesAt(0x0077e193, "8815d9e8fa00") && HexBytesAt(0x0077e450, "c605d9e8fa0000 e96405e6ff") &&
                     g_pendingOk;
    if (!g_pendingOk)
        Log(0, "0.7.2: main state code did not match - level.load / level.start refuse only on GameTracker+0xb9 (as "
               "0.7.1), a mission start in progress is not seen");
    if (g_outfitRule && !g_outfitRuleOk)
        Log(0, "0.7.2: outfit rule off - f27 / selection byte code did not match; level.start keeps f27(unit, 1, 0, 1) "
               "(PC script 104)");
    Log(1, "0.7.2: pending check %d (main state 2 / 9 + GameTracker+0xb9), outfit rule %d (ini %d; DLC 2 without the "
           "outfit selection as the title update), game.quit ready (exit code 0x%x, menu / bar / favourites only)",
        g_pendingOk ? 1 : 0, g_outfitRuleOk && g_outfitRule ? 1 : 0, g_outfitRule, kQuitExitCode);
    DevRead();
    g_logOverlay = g_logOverlayAtStart ? 1 : 0;
    g_logLines = g_logLinesAtStart;
    if (g_scriptLogAtStart && g_scriptOk && g_experimental) {   // at load no script runs yet: patch here
        char text[160];
        SetScriptLog(true, text, sizeof(text));
    }
    Log(1, "0.3 checks: time %d, pause %d, control %d, ui %d, instances %d, remove %d, costume switch %d, movie %d, "
           "main state %d, menu loop %d, script natives %d, markup draw %d; dev menu: %s", g_timeOk, g_pauseOk,
        g_controlOk, g_uiOk, g_instOk, g_removeOk, g_switchOk, g_movieOk, g_mainStateOk, g_menuLoopOk, g_scriptOk,
        g_drawOk, g_devStatus);
    Log(1, "0.3 checks: weapon.give %d, ammo %d, health %d", g_weaponOk, g_ammoOk, g_healthOk);
    Log(1, "0.4 checks: weapon slots %d, MaxAmmo %d, gear give %d; TO TEST file %s", g_slotsOk, g_maxAmmoOk, g_gearOk,
        g_testPath);
    Log(1, "code checks: pad %d, d3d9 %d, player %d, INSTANCE_Post %d, camera %d, frame time %d, level change %d, "
           "costume %d (type table 0x%08lx), unit table %d", g_padCodeOk, g_d3dCodeOk, g_playerOk, g_postOk, g_cameraOk,
        g_frameOk, g_levelOk, g_costumeOk, typeTable, g_unitOk);
    g_overlay = g_overlayAtStart && g_playerOk;
    // set the import filter now if the imports are resolved already (normal case), else the worker retries
    if (g_padCodeOk) {
        g_padSetupDone = SetupPad();
        if (!g_padSetupDone) Log(2, "pad: import slot not resolved yet - worker retries");
    }
    HANDLE thread = CreateThread(nullptr, 0, WorkerThread, nullptr, 0, nullptr);
    if (thread) CloseHandle(thread);
    else Log(0, "CreateThread failed (%lu) - no menu", GetLastError());
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        InitializeCriticalSection(&g_logLock);
        InitializeCriticalSection(&g_padLock);
        InitializeCriticalSection(&g_reqLock);
        InitializeCriticalSection(&g_logRingLock);
        InitializeCriticalSection(&g_favLock);
        InitializeCriticalSection(&g_testLock);
        InitializeCriticalSection(&g_cmdLock);
        InitializeCriticalSection(&g_mouseLock);
        g_reqDone = CreateEventA(nullptr, TRUE, FALSE, nullptr);
        Start(instance);
    } else if (reason == DLL_PROCESS_DETACH) {
        g_stop = 1;
    }
    return TRUE;
}

// exported so the loader / tools / other plugins can identify the plugin
extern "C" __declspec(dllexport) const char *TruMenuVersion() { return kVersion; }

// item interface for other plugins / tools (TruLink "menu"): one line per item "id<TAB>type<TAB>value<TAB>label\n".
// The returned text lives in a buffer of the calling thread, valid until that thread's next call.
extern "C" __declspec(dllexport) const char *__cdecl TruMenuList() { return ListItems(); }

// runs item <id> with <arg> ("" = toggle / default). Items that touch the game run on the game thread: the call
// waits up to 3 s for the next game frame and returns "ok ..." / "err ...".
extern "C" __declspec(dllexport) const char *__cdecl TruMenuInvoke(const char *id, const char *arg) {
    return InvokeItem(id, arg);
}
