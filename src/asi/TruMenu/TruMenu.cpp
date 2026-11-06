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
//   shots  0.10.5: no hook of its own - the Present hooks above copy the back buffer (GetRenderTargetData into a
//          system-memory surface) before or after TruMenu draws; PNG encoding and the file write on a worker thread.
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
#include <shlobj.h>                         // 0.9: SHGetFolderPathW (the save folder as tru.exe 0x78b550)
#pragma comment(lib, "shell32.lib")

#include "imgui.h"
#include "imgui_internal.h"                 // 0.6: ClearActiveID (command bar -> pad picker)
#include "imgui_impl_dx9.h"
#include "imgui_impl_win32.h"
#include "TruShotPng.h"                     // 0.10.5: PNG writer of the shot worker (own code)
#include "TruFlowCore.h"                    // 0.11: flow file parser + pattern matcher (own code, no game access)

extern IMGUI_IMPL_API LRESULT ImGui_ImplWin32_WndProcHandler(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam);

namespace {

const char *const kVersion = "TruMenu 0.14 (Debug view: dbg.triggers draws the game's trigger planes / volumes as "
                             "wireframes the way the engine tests them (box = 12 lines along the instance's Euler "
                             "matrix, sphere = 3 circles, plane = its quad, one-sided arrow), coloured by kind from the "
                             "object name (death, fire, checkpoint, water, sound, plain volume, plane, unknown), each kind "
                             "its own switch (dbg.show <layer>); dbg.portals = the stream portal quads (loading areas) of "
                             "the loaded units; dbg.checkpoints = checkpoint objects, the active one marked; dbg.legend; "
                             "dbg.view = master switch for every overlay (0.14 layers, dbg.labels, draw.markup, [Debug] "
                             "ViewNav); menu page Debug view, ring Spieler / Debug in groups Leveldaten / KI / Lara, "
                             "[Debug] keys per layer (0 by default), Persist; "
                             "0.13: Thrall-Labels: dbg.labels draws a text label at the projected screen position "
                             "of each thrall / enemy instance near Lara - object name, intro id, distance, health "
                             "(EnemyProcessFunc's value), and from TruShadowCombat 0.5.3's TscTargeterSnapshot targeter 9 "
                             "bucket / rejected (reason) / target, hit list, last condition 2011 - projected like the game's "
                             "own instance text (matrix 0xe804a0, 0x49f630), ring Spieler / Debug, [Debug] Labels 0 by "
                             "default; 0.12: Debug-Zeichnung: nav.draw <switch> 0|1 switches the NavPower debug drawing "
                             "compiled into tru.exe (planner_areas, planner_areas_solid, planner_connectivity, "
                             "planner_area_normals, obstacles, recent_navprobes, draw_mover3d_path - data bytes only, in a "
                             "loaded level), nav.mask (planner layer mask, every layer), nav.off, nav.status, ring Spieler / "
                             "Debug, [Debug] Enabled 0 by default; "
                             "0.11: Ablauf: guided test runs from TruMenu.flow.txt ([Flow] Enabled, 0 by default) "
                             "- action / observe / mark steps, counters (TruTrace unit / level loads and restores, plugin "
                             "log patterns, player deaths, switch flips, item runs, marks), conditions after= / check= / "
                             "fail=, ring level Claude: Weiter / Ueberspringen / Zurueck + Gut / Fehler = the step result, "
                             "a status line in coral ([Flow] Overlay / Position / Size / Lines), flow.say toast, "
                             "flow.goto / skip / add / status over TruLink, 'flow: ...' lines in TruMenu.log; "
                             "0.10.5: screenshots: shot.save [ui|clean] [name] -> [Shot] Folder (TruShots next "
                             "to tru.exe) as shot_<HHMMSS>_<TO TEST step>_<name>.png, taken in the game's Present "
                             "before TruMenu draws ([Shot] Clean=1) or after it, PNG encoded and written on a worker "
                             "thread, [Shot] Hotkey / MaxPerMinute, export TruMenuShot; Claude marks: ring level "
                             "Claude (coral), claude.mark <kind> = a TruMenu.log line 'claude.mark <kind>: ...' + a "
                             "clean shot, export TruMenuMark; ring level Objekte moved to Spieler/Objekte; "
                             "0.10.4: F7 light shaft: [Radial] FreezeShaderClock, 0 by default - the world "
                             "freeze also holds the shader clock TimeVector the pause menu's way (0x5bfdf0), ring item "
                             "time.freezeclock / state time.clock; the costume check accepts TruDlc2Player 0.5's "
                             "detour at the state save; "
                             "0.10.3: F7: [Radial] FreezeSound / [Menu] PauseSound, both 0 by default - "
                             "the world freeze also pauses the sound with the pause menu's own pair 0x5874b0 / "
                             "0x5874d0, never while the pause menu is open; ring items time.freezesound / "
                             "time.pausesound / time.sound; "
                             "0.10.2: fixes from the 03.11. ring tests: cheat.godfull without flight - the "
                             "player's no-damage bit 0xfada74 & 0x20000 per frame instead of cheatMode bit 0, the off "
                             "also ends a left-over flight; player.unstuck samples no safe ground while the menu / ring "
                             "is open, the world is paused, in a cinematic or with control off, and takes a spot by a "
                             "chord / slope test over ~1 s instead of 'height still'; marks and safe spots keep the "
                             "yaw; level.start greyed in the ring outside the main menu; "
                             "0.10.1: radial menu as a menu: [Radial] Mode=menu (default) - L3 + R3 held / "
                             "F9 tapped opens the ring and it stays open, left stick / right stick / D-pad / mouse "
                             "picks, only A / Enter / click runs, B back, L3 + R3 / F9 again closes; [Radial] Freeze "
                             "world / player / 0 while it is open; built-in top sector 'Spiel beenden' (game.quit, A "
                             "twice or hold 1 s, [Radial] QuitSector); Mode=wheel = the 0.10 hold-and-release ring; "
                             "0.10: radial menu: L3 + R3 held = a ring of up to 8 entries from "
                             "TruMenu.radial.txt, right stick / mouse picks, release runs, A runs and stays, B back, LB / "
                             "RB pages; F9 / mouse button hold; [Radial] keys; stage R2 instance.spawn <object> at Lara "
                             "behind [Radial] Spawn=1; "
                             "0.9: Saves page: the game's save folder (CSIDL_PERSONAL\\Eidos\\Tomb Raider - "
                             "Underworld, *.TRUSave), list with CRC check / unit / checkpoint, backup, restore, delete "
                             "and import with a backup first and a safety step, export; Media: srmusic tracks from "
                             "TruMenu.media.txt, media.music.play / stop through SRMUSIC_LoadMusic 0x594320, "
                             "media.music.now (8 slots), dev.musicvars / dev.monstermusicvars; "
                             "0.8.1: fixes from the 0.8.0 live test: game.quit 'Quit now' button with a "
                             "stable id while armed (10 s, hold A 1 s), [Log] InputTrace, menu keys released at open / "
                             "close (stuck Enter), a queued item runs once (cheat.flight ran twice), cheat.ammo reasons "
                             "per weapon, player.unstuck (mark / safe-ground ring), regression shortcuts (prepare); "
                             "0.8: Regression page: lists TruMenu.regress_dlc1 / _dlc2.txt, A ok / X fail / "
                             "Y skip, notes, TruMenu.regress_results.txt with plugin versions + sha256; Cheats page "
                             "from the 2007 prototype evaluation: god mode, one-hit kill, enemy health, infinite ammo, "
                             "fill 'er up, cheat codes, each with its category and a byte pre-check; camera log "
                             "[Log] CameraChanges; "
                             "0.7.2: game.quit:TerminateProcess with exit code 0x544D after a safety step; "
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
    {"Menu", "PauseSound", "0", "0.10.3: 1 = while the world pause bit is on in a level and the ring did not set it "
                                "(time.pause, PauseGame), the sound\npauses too - the pause menu's own functions "
                                "(0x5874b0 / 0x5874d0), not while the pause menu is open; item time.pausesound\n"
                                "switches it until the next start, a changed value here is taken over within a second"},
    {"Pad", "BlockInput", "1", "1 = the game gets a neutral pad while the menu is open; 0 = the game sees the pad as well"},
    {"Cheat", "Experimental", "1", "1 = show the experimental actions (cheat / flight, camera mode, level load, costumes, "
                                   "developer menu rows, time /\nplayer / instance / video items); 0 = read-only"},
    {"Cheat", "FlightSpeed", "20", "flight: units per 30 fps frame at full trigger (RT up, LT down) while cheat mode is on"},
    {"Cheats", "Enabled", "1", "0.8: 1 = the Cheats page (god mode, one-hit kill, enemy health, infinite ammo, fill 'er up, "
                               "cheat codes) can switch;\n0 = the page only lists them (also needs [Cheat] "
                               "Experimental=1)"},
    {"Cheats", "Persist", "0", "0.8: 0 = every cheat starts off at each game start; 1 = the cheats switched on are kept "
                               "in State below and switched\non again in the first level of the next game start"},
    {"Cheats", "State", "", "0.8: written by TruMenu when Persist=1 (comma list of cheat ids that are on); empty = none"},
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
    {"Log", "CameraChanges", "1", "0.8: 1 = a line \"camera: mode A -> B\" / \"camera: object ...\" when the camera "
                                  "manager's mode or current camera\nchanges (polled a few times per second, read-only; "
                                  "TruMenu.log, log page and overlay)"},
    {"Log", "InputTrace", "1", "0.8.1: 1 = with LogLevel 2 one line per pad button edge, mouse click and key while the "
                               "menu is open, with the source\n(XInput hook / Present fallback / window message) and what "
                               "the menu did (focused widget, activated or why not);\n0 = only the summary line at each "
                               "menu close"},
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
    {"Regress", "List", "all", "0.8: list shown on the Regression page at start: dlc1, dlc2 or all (TruMenu.regress_dlc1.txt "
                               "/ _dlc2.txt next to\nthe .asi; results go to TruMenu.regress_results.txt)"},
    {"Media", "MusicInLevels", "0", "0.9: 1 = media.music.play / stop also in a level; 0 = main menu only (until a live "
                                    "test proves play in a level safe)"},
    {"Media", "MusicFade", "60", "0.9: fade in / out of media.music.play / stop in frames (30 per second; the game's unit "
                                 "start uses 60), 0 .. 300"},
    {"Saves", "Folder", "", "0.9: save folder for the Saves page; empty = the game's own (Documents\\Eidos\\Tomb Raider - "
                            "Underworld, as tru.exe\n0x78b550). Backups, export and import live in TruMenu.saves next "
                            "to tru.exe"},
    {"Radial", "Enabled", "1", "0.10: 1 = radial menu: hold HoldButtons for HoldMs - a ring of up to 8 entries from "
                               "TruMenu.radial.txt next to tru.exe,\nhow it is used says Mode; a short press opens TruMenu as "
                               "before (at the release when\nHoldButtons = [Menu] ToggleButtons); 0 = TruMenu exactly as 0.9"},
    {"Radial", "Mode", "menu", "0.10.1: menu = the ring stays open after the open (L3 + R3 held / Key or MouseButton "
                               "tapped), left stick / right stick /\nD-pad / mouse pick, only A / Enter / left click runs or "
                               "opens a level, B / Backspace / right click = back, L3 + R3 / Key again\ncloses, the game gets "
                               "a neutral pad and no keys; wheel = the 0.10 ring (right stick picks, releasing the hold "
                               "runs)"},
    {"Radial", "Freeze", "world", "0.10.1, Mode=menu: while the ring is open in a level: world (or 1) = time.pause (the "
                                  "whole world incl. enemies stops; the\nstate from before comes back at the close unless "
                                  "time.pause was run meanwhile), player (or 2) = player.control 0 (restored at\nthe close), "
                                  "0 = nothing. Read again at every open (a TO TEST switch works at once)"},
    {"Radial", "FreezeSound", "0", "0.10.3: 1 = while Freeze=world holds the world (the ring set the pause bit), the "
                                   "sound pauses too ([Menu] PauseSound\nfor every other pause); item time.freezesound "
                                   "switches it until the next start, a changed value here is taken over\nwithin a "
                                   "second"},
    {"Radial", "FreezeShaderClock", "0", "0.10.4: 1 = while the world is frozen in a level (the ring's Freeze=world or "
                                         "time.pause / [Menu] PauseGame), the shader\nclock TimeVector holds too, the "
                                         "pause menu's own way (0x5bfdf0: dt 0, the accumulator RenderDevice +0xfa4c "
                                         "stays,\nso it goes on without a jump); item time.freezeclock switches it "
                                         "until the next start, a changed value here is\ntaken over within a second"},
    {"Radial", "QuitSector", "1", "0.10.1, Mode=menu: 1 = built-in last sector \"Spiel beenden\" on the top level (not "
                                  "from TruMenu.radial.txt): A arms it\n(red, 10 s), A again or A held 1 s = game.quit; "
                                  "pointing away / B / closing disarms; 0 = hidden"},
    {"Radial", "TestsLevel", "1", "0.10.1, Mode=menu: 1 = built-in top level \"Tests\": TO TEST rows, Regression lists, "
                                  "Prepare shortcuts, Schalter (TO TEST\ntoggles) - the page functions - and Rundgang "
                                  "(TruMenu.tour.txt next to tru.exe); 0 = hidden"},
    {"Radial", "HoldButtons", "0x00C0", "0.10: XInput buttons held together for the radial menu (hex or decimal): 0x00C0 = "
                                        "L3 + R3; 0 = no pad hold (key / mouse only)"},
    {"Radial", "HoldMs", "500", "0.10: milliseconds the buttons must be held (shorter = TruMenu), 100 .. 3000"},
    {"Radial", "Key", "0x78", "0.10: keyboard key for the radial menu (virtual key code, hex or decimal; 0x78 = F9 - for "
                              "a Steam Controller back\nbutton map it to that key in Steam Input; Mode=menu: a tap opens / "
                              "closes, Mode=wheel: held); the game does not get\nthis key while it is set; 0 = off"},
    {"Radial", "MouseButton", "0", "0.10: mouse button for the radial menu (3 = middle, 4 / 5 = side buttons; as Key); the "
                                   "mouse direction picks the entry;\n0 = off"},
    {"Radial", "RememberPosition", "1", "0.10: 1 = the ring opens again at the level, page and entry of its last close; "
                                        "0 = always at the top"},
    {"Radial", "PassLeftStick", "1", "0.10, Mode=wheel only: 1 = the left stick still reaches the game while the ring is "
                                     "open (Lara can walk); 0 = neutral pad\n(Mode=menu: always neutral - the left stick "
                                     "picks)"},
    {"Radial", "SlowMotion", "0", "0.10: time.scale while the ring is open (e.g. 0.25; the value from before comes back at "
                                  "the close); 0 = off"},
    {"Radial", "Deadzone", "0.5", "0.10: stick deflection (0.2 .. 0.95 of full) that picks an entry; inside it the centre "
                                  "(Mode=wheel: no entry, release = cancel;\nMode=menu: the pick stays)"},
    {"Radial", "Scale", "1.0", "0.10: size of the ring relative to the back-buffer height, 0.5 .. 2"},
    {"Radial", "Spawn", "0", "0.10 stage R2: 1 = instance.spawn <object> works (ring level Spieler/Objekte since 0.10.5, "
                             "command bar): the object is loaded and born at\nLara on the game thread (experimental - back "
                             "up the saves first); 0 = refused. Read again while the game runs (a TO TEST switch works at "
                             "once)"},
    {"Shot", "Enabled", "1", "0.10.5: 1 = screenshots on request only: item shot.save [ui|clean] [name] (command bar, TruLink "
                             "\"menu shot.save <name>\"),\nring Spieler / Screenshot, the ring level Claude (claude.mark: a "
                             "TruMenu.log line + a clean shot each), Hotkey, the exports\nTruMenuShot / TruMenuMark of "
                             "other plugins; nothing is taken automatically; 0 = every shot refused (claude.mark lines "
                             "are still\nwritten, with shot=-)"},
    {"Shot", "Folder", "", "0.10.5: folder for the PNG files; empty = TruShots next to tru.exe, a relative path is below the "
                           "game folder. File name\nshot_<HHMMSS>_<first open TO TEST step or ->_<name>.png; one TruMenu.log "
                           "line \"shot: <path> <w>x<h> <bytes> bytes, capture ... ms\" per file"},
    {"Shot", "Clean", "1", "0.10.5: 1 = the back buffer is copied before TruMenu draws (no menu, ring, command bar or "
                           "TruMenu overlay in the shot);\n0 = after it (as on screen). shot.save ui / clean overrides it "
                           "per shot; claude.mark is always clean"},
    {"Shot", "Hotkey", "0", "0.10.5: keyboard key (virtual key code, hex or decimal; 0x7A = F11) = claude.mark now (a mark "
                            "line + a clean shot);\nthe game still gets the key; 0 = off"},
    {"Shot", "MaxPerMinute", "30", "0.10.5: at most this many shots - and as many claude.mark lines - per minute, 1 .. 120; "
                                   "more are refused with a log line;\n0 = no limit"},
    {"Flow", "Enabled", "0", "0.11: 1 = Ablauf: read the flow file below (steps, counters; Invoke-TruTestRun.ps1 installs a "
                             "profile's flowFile) - the ring level\nClaude shows Weiter / Ueberspringen / Zurueck, Gut / "
                             "Fehler set the step result, 'flow: ...' lines go to TruMenu.log; 0 = off (no file read,\nno "
                             "tail, the flow.* items answer 'no flow')"},
    {"Flow", "File", "TruMenu.flow.txt", "0.11: flow file next to tru.exe (a relative name) or an absolute path"},
    {"Flow", "Overlay", "1", "0.11: 1 = the status line 'Claude-Ablauf  Schritt n/m | <counter a/b> | naechster: ...' in "
                             "Claude's coral in a screen corner while a flow\nis loaded; 0 = only in the ring"},
    {"Flow", "Position", "br", "0.11: corner of the status line: tl, tr, bl, br (top / bottom, left / right)"},
    {"Flow", "Size", "1.0", "0.11: text size of the status line and the flow.say toast, 0.5 .. 3"},
    {"Flow", "Lines", "2", "0.11: lines of the status line: 1 = step / counter / next, 2 = + the current step's text, 3 = + "
                           "what it waits for / its hint"},
    {"Flow", "AutoAdvance", "1", "0.11: 1 = a step finished by its check= / fail= / its commands moves the flow on to the "
                                 "next step; 0 = only Weiter /\nGut / Fehler / Ueberspringen move on"},
    {"Flow", "ToastSeconds", "6", "0.11: seconds a flow.say toast (TruLink: menu flow.say <text>) stays, 1 .. 30"},
    {"Flow", "PollMs", "500", "0.11: milliseconds between two reads of the log files the flow's patterns name (every new "
                              "byte, at most 256 KB per\nfile and read), 100 .. 5000"},
    {"Debug", "Enabled", "0", "0.12: 1 = Debug-Zeichnung: the items nav.draw / nav.mask / nav.off (ring Spieler / Debug, "
                              "command bar, TruLink) may switch\nthe NavPower debug drawing compiled into tru.exe (data "
                              "bytes only, in a loaded level, never while loading); 0 = off (the ring\nentries are greyed, "
                              "nav.status still reads)"},
    {"Debug", "NavDraw", "", "0.12: comma list of NavPower switches turned on once the first level is loaded (needs "
                             "Enabled=1), e.g. planner_areas;\nempty = none. Names: planner_areas, planner_areas_solid, "
                             "planner_connectivity, planner_area_normals, obstacles,\nrecent_navprobes, draw_mover3d_path"},
    {"Debug", "NavMask", "0", "0.12: 1 = together with NavDraw also nav.mask 1 (planner layer mask [0x88e454] = 0xffffffff: "
                              "every layer is drawn);\n0 = the game's mask"},
    {"Debug", "Labels", "0", "0.13: 1 = Thrall-Labels on from the start (needs Enabled=1; item dbg.labels, ring Spieler / "
                             "Debug): a text label at each\nthrall near Lara - name, intro id, distance, health, "
                             "targeter 9 / hit list / condition 2011 from TruShadowCombat 0.5.3\n(read-only, in a loaded "
                             "level only); 0 = off"},
    {"Debug", "LabelRadius", "3000", "0.13: labels only for instances at most this far from Lara (game units, 100 .. 50000)"},
    {"Debug", "LabelMax", "12", "0.13: at most this many labels, the nearest first (thralls before other matches), 1 .. 32"},
    {"Debug", "LabelMatch", "thrall", "0.13: comma list of parts of object names that get a label, e.g. thrall,yeti; * = every "
                                      "instance in the radius"},
    {"Debug", "LabelCross", "1", "0.13: 1 = a magenta cross at Lara's position (+0x20) projected the same way - the live "
                                 "check of the projection; 0 = none"},
    {"Debug", "View", "0", "0.14: 1 = the whole debug view on from the start (dbg.view: every layer below, Labels, Markup, "
                           "and ViewNav as NavDraw when\nNavDraw is empty; needs Enabled=1); 0 = only the single keys"},
    {"Debug", "ViewNav", "planner_areas,planner_connectivity,obstacles", "0.14: the NavPower switches dbg.view turns on "
                                                                         "(comma list, names as NavDraw)"},
    {"Debug", "Triggers", "0", "0.14: 1 = every trigger kind on from the start (dbg.triggers; wireframes of the game's "
                               "trigger planes / volumes)"},
    {"Debug", "TrgDeath", "0", "0.14: 1 = trigger kind death / kill on from the start (red; dbg.show death)"},
    {"Debug", "TrgFire", "0", "0.14: 1 = trigger kind fire / slow fire on from the start (orange; dbg.show fire)"},
    {"Debug", "TrgCheckpoint", "0", "0.14: 1 = checkpoint triggers on from the start (green; dbg.show checkpoint)"},
    {"Debug", "TrgWater", "0", "0.14: 1 = water triggers on from the start (blue; dbg.show water)"},
    {"Debug", "TrgSound", "0", "0.14: 1 = sound / swoosh triggers on from the start (violet; dbg.show sound)"},
    {"Debug", "TrgVolume", "0", "0.14: 1 = plain trigger volumes on from the start (yellow; dbg.show volume)"},
    {"Debug", "TrgPlane", "0", "0.14: 1 = plain trigger planes on from the start (cyan; dbg.show plane)"},
    {"Debug", "TrgUnknown", "0", "0.14: 1 = triggers of unknown kind on from the start (grey; dbg.show unknown)"},
    {"Debug", "Portals", "0", "0.14: 1 = loading areas (stream portal quads of the loaded units) on from the start (white; "
                              "dbg.portals)"},
    {"Debug", "Checkpoints", "0", "0.14: 1 = checkpoint objects on from the start (light green, the active one yellow; "
                                  "dbg.checkpoints)"},
    {"Debug", "TrgLabels", "0", "0.14: 1 = trigger names (object name, intro id, shape) on from the start (dbg.show "
                                "trglabels)"},
    {"Debug", "Legend", "0", "0.14: 1 = the legend top right on from the start (dbg.legend)"},
    {"Debug", "Markup", "0", "0.14: 1 = draw.markup on from the start"},
    {"Debug", "TriggerMax", "64", "0.14: at most this many triggers drawn per frame, the nearest to the camera first, "
                                  "1 .. 256"},
    {"Debug", "TriggerRadius", "20000", "0.14: triggers only up to this distance from the camera (game units, 500 .. "
                                        "200000)"},
    {"Debug", "TriggerLabelMax", "16", "0.14: at most this many trigger names per frame (the nearest), 0 .. 64"},
    {"Debug", "Names", "0", "0.14: 1 = object names on from the start (dbg.names: the object name of every instance from "
                            "the live object list)"},
    {"Debug", "NameMatch", "", "0.14: object names only for names containing one of these parts (comma list a-z 0-9 _, "
                               "e.g. thrall); empty or * = every\ninstance"},
    {"Debug", "NameRadius", "5000", "0.14: object names only up to this distance from the camera (game units, 100 .. "
                                    "200000)"},
    {"Debug", "NameMax", "24", "0.14: at most this many object names per frame, the nearest to the camera first, 1 .. 64"},
    {"Debug", "NameScale", "1.0", "0.14: font size factor of the object names, 0.5 .. 3"},
    {"Debug", "NameColour", "FFFFFF", "0.14: colour of the object names, RRGGBB (ring presets: white FFFFFF, yellow "
                                      "FFE040, cyan 40E8FF, magenta FF50FF)"},
    {"Debug", "NameIds", "1", "0.14: 1 = the intro id after each object name; 0 = the name only"},
    {"Debug", "Persist", "0", "0.14: 1 = every debug view switch (layers, Labels, Markup, NavDraw) is written back into "
                              "this file at once, so the\nchosen set comes back at the next start (Set-TruMenu.ps1 then "
                              "keeps the file as owner-edited); 0 = switches\nlast until the game ends"},
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
int g_cheatsEnabled = 1, g_cheatPersist = 0;                                 // 0.8 [Cheats] Enabled / Persist
char g_cheatState[256] = "";                                                 // 0.8 [Cheats] State (Persist=1)
int g_debugEnabled = 0, g_navAutoMask = 0;                                   // 0.12 [Debug] Enabled / NavMask
char g_navAuto[256] = "";                                                    // 0.12 [Debug] NavDraw (comma list)
int g_lblAtStart = 0, g_lblMax = 12, g_lblCross = 1;                         // 0.13 [Debug] Labels / LabelMax / LabelCross
float g_lblRadius = 3000.0f;                                                 // 0.13 [Debug] LabelRadius
char g_lblMatch[128] = "thrall";                                             // 0.13 [Debug] LabelMatch
volatile LONG g_cameraChanges = 1;                                           // 0.8 [Log] CameraChanges
char g_regressStart[8] = "all";                                              // 0.8 [Regress] List
volatile LONG g_inputTrace = 1;                                              // 0.8.1 [Log] InputTrace
// 0.10 [Radial] (workspace docs\Konzept-Bau-Rad.md): hold the pad buttons / the key / the mouse button = radial menu
int g_radEnabled = 1;
WORD g_radHold = kPadL3 | kPadR3;                                            // [Radial] HoldButtons (0 = no pad hold)
int g_radHoldMs = 500, g_radKey = 0x78, g_radMouse = 0;                     // HoldMs, Key (F9), MouseButton (0 = off)
int g_radRemember = 1, g_radPassLeft = 1, g_radSpawn = 0;                    // RememberPosition, PassLeftStick, Spawn
float g_radSlow = 0.0f, g_radDead = 0.5f, g_radScale = 1.0f;                 // SlowMotion, Deadzone, Scale
DWORD g_radKeyDik = 0;                                                       // DirectInput code of Key (kept from the game)
// ring state: 0 closed, 1 hold mode (the release runs the entry), 2 latched (stays open: after a level change or A)
volatile LONG g_radOpen = 0;
volatile LONG g_radBy = 0;                   // who holds it: 1 pad, 2 key, 3 mouse button, 4 radial.open (TruLink)
volatile LONG g_radJust = 0;                 // opened this frame (render thread sets level / page / slow motion)
volatile LONG g_radRelease = 0;              // the hold was released (OnPad / RadialTick) - the render thread runs it
volatile LONG g_radSwallow = 0;              // after the close: the pad stays neutral until every button is up
enum { kRadByPad = 1, kRadByKey = 2, kRadByMouse = 3, kRadByLink = 4 };
bool g_holdHeld[4], g_holdPending[4];        // pad hold: buttons down / waiting for HoldMs (under g_padLock)
DWORD g_holdStart[4];
// 0.10.1 [Radial] Mode / Freeze / QuitSector (workspace docs\Konzept-Bau-Rad.md section 10 "Bedienung v2")
enum { kRadModeMenu = 0, kRadModeWheel = 1 };
enum { kRadFreezeNone = 0, kRadFreezeWorld = 1, kRadFreezePlayer = 2 };
int g_radMode = kRadModeMenu;                // Mode=menu: the ring stays open (state 2), only A runs
int g_radFreeze = kRadFreezeWorld;           // [Radial] Freeze at the start; read again at every open (RadFreezeRead)
int g_radQuitSector = 1;                     // [Radial] QuitSector
volatile LONG g_radCloseReq = 0;             // Mode=menu: L3 + R3 pressed again on the open ring (OnPad) - render thread closes
volatile LONG g_radPaused = 0;               // Freeze=world: the ring set the time.pause bit (RunPause clears it: user's choice)
volatile LONG g_radCtlOurs = 0;              // Freeze=player: the ring wrote player.control 0 (RunControl clears it)
BYTE g_radCtlBefore = 1;                     // player.control before the open
bool RadMenuOpen() { return g_radOpen != 0 && g_radMode == kRadModeMenu; }   // the ring holds pad + keyboard

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
void CheatsTick();     // 0.8 Cheats page: [Cheats] Persist restore, infinite ammo re-apply (game thread)
void NavTick();        // 0.12 Debug-Zeichnung: [Debug] NavDraw / NavMask once in the first loaded level (game thread)
void SafeGroundTick(); // 0.8.1 player.unstuck: ring of recent safe positions (game thread)
void NoDamageTick();   // 0.10.2 cheat.godfull: the player's no-damage bit once per game frame (game thread)
void SoundFreezeTick(); // 0.10.3 [Radial] FreezeSound / [Menu] PauseSound: sound pause with the world (game thread)
void ShaderClockTick(); // 0.10.4 [Radial] FreezeShaderClock: the shader clock TimeVector holds with the freeze
void LogTailTick();   // 0.3 log page: tail Tru*.log once per second (worker thread)
// 0.11 Ablauf hooks (defined in the flow section): they only queue an event (any thread, any lock held)
void FlowOnItem(const char *id);
void FlowOnToggle(const char *id, const char *state);
void FlowOnMark(const char *kind, const char *file);
bool FlowShotStep(char *o, size_t n);
void ValFlowStatus(char *o, size_t n);

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

// ---- 0.8.1 input trace ([Log] InputTrace; owner wish 2026-11-02 after the game.quit case) ----
// Every raw pad button edge (OnPad: "XInput hook" = the game's poll through PadHook, "Present fallback" = SelfPoll),
// mouse click and key message (window procedure) while the menu is open goes into a small queue. The render thread
// takes the queue at the start of frame N and writes one line per edge at the end of frame N + 1: by then ImGui has
// applied a D-pad move, and the frame-N record says which widget had the focus / was hovered / was activated. Labels
// come from the Tm* widget wrappers (TraceItem), ids from imgui_internal (NavId, HoveredId, NavActivateId).
enum { kEdgePad = 0, kEdgeMouse = 1, kEdgeKey = 2 };
struct InputEdge { DWORD tick; BYTE kind, down, source, pad; WORD code; SHORT x, y; };
const int kEdgeMax = 48;
InputEdge g_edgeQueue[kEdgeMax];
int g_edgeCount = 0;
LONG g_edgeDropped = 0;
CRITICAL_SECTION g_edgeLock;
WORD g_edgePrev[4];                       // last buttons per pad (under g_padLock)
const char *const kEdgeSource[] = {"XInput hook", "Present fallback", "window message"};
struct PadBitName { WORD mask; const char *name; };
const PadBitName kPadBits[] = {{0x1000, "A"}, {0x2000, "B"}, {0x4000, "X"}, {0x8000, "Y"}, {0x0100, "LB"},
                               {0x0200, "RB"}, {0x0040, "L3"}, {0x0080, "R3"}, {0x0010, "Start"}, {0x0020, "View"},
                               {0x0001, "Up"}, {0x0002, "Down"}, {0x0004, "Left"}, {0x0008, "Right"}};
// per menu session, written at the close (also with InputTrace=0)
LONG g_sumPad = 0, g_sumA = 0, g_sumAAct = 0, g_sumANot = 0, g_sumMouse = 0, g_sumKeys = 0;

void EdgeAdd(BYTE kind, BYTE down, BYTE source, BYTE pad, WORD code, SHORT x, SHORT y) {
    EnterCriticalSection(&g_edgeLock);
    if (g_edgeCount < kEdgeMax) g_edgeQueue[g_edgeCount++] = {GetTickCount(), kind, down, source, pad, code, x, y};
    else ++g_edgeDropped;
    LeaveCriticalSection(&g_edgeLock);
}

// ---- pad ----
void ToggleMenu(const char *by) {
    LONG open = !InterlockedCompareExchange(&g_menuOpen, 0, 0);
    InterlockedExchange(&g_menuOpen, open);
    if (open) InterlockedExchange(&g_menuJustOpened, 1);
    Log(1, "menu %s (%s)", open ? "opened" : "closed", by);   // 0.7.1: level 1 - the reason of every close in the log
}

// real pad state in, toggle detection; returns what the game gets: 0 the real state, 1 a neutral state, 2 (0.10, radial
// menu with [Radial] PassLeftStick=1) a neutral state that keeps the left stick
// source: 0 = PadHook (the game's poll), 1 = SelfPoll in Present (0.8.1 input trace)
// 0.10 radial hold: when [Radial] HoldButtons = [Menu] ToggleButtons ("shared", L3 + R3) and the menu is closed, the press
// no longer toggles at once - a release before HoldMs opens the menu, HoldMs reached opens the ring in hold mode and the
// release then runs its entry (the render thread does that, g_radRelease). A different HoldButtons mask is watched on its
// own (the menu toggles as before; the game sees those buttons until the ring opens). The latched ring (open after the
// hold) goes back into hold mode when the buttons are pressed again.
int OnPad(DWORD index, bool connected, const PadState *state, BYTE source) {
    if (index > 3) return 0;
    EnterCriticalSection(&g_padLock);
    g_padConnected[index] = connected;
    WORD buttons = connected ? state->wButtons : 0;
    WORD changed = static_cast<WORD>(buttons ^ g_edgePrev[index]);   // 0.8.1: edges for the input trace
    g_edgePrev[index] = buttons;
    if (changed && g_menuOpen)
        for (const PadBitName &b : kPadBits)
            if (changed & b.mask)
                EdgeAdd(kEdgePad, (buttons & b.mask) ? 1 : 0, source, static_cast<BYTE>(index), b.mask, 0, 0);
    if (connected) {
        g_pad[index] = *state;
        if (buttons) g_lastPad = static_cast<int>(index);
    }
    bool combo = (buttons & g_toggleButtons) == g_toggleButtons;
    WORD hold = g_radEnabled ? g_radHold : 0;
    bool shared = hold && hold == g_toggleButtons;
    bool holdCombo = hold && (buttons & hold) == hold;
    bool toggled = false;
    const char *toggleBy = "pad";
    int radial = 0;                          // 1 = HoldMs reached, 2 = hold released, 3 = latched ring held again
    if (combo && !g_comboHeld[index]) {
        g_comboHeld[index] = true;
        g_swallow[index] = true;
        if (!shared || g_menuOpen) toggled = !g_radOpen || !shared;   // shared + menu closed: decided at the release
    } else if (!combo) {
        g_comboHeld[index] = false;
    }
    if (hold) {
        DWORD now = GetTickCount();
        if (holdCombo && !g_holdHeld[index]) {
            g_holdHeld[index] = true;
            if (g_radOpen == 2) radial = g_radMode == kRadModeMenu ? 4 : 3;   // 0.10.1 Mode=menu: pressed again = close
            else if (!g_radOpen && !g_menuOpen && !toggled) {
                g_holdPending[index] = true;
                g_holdStart[index] = now;
            }
        } else if (!holdCombo && g_holdHeld[index]) {
            g_holdHeld[index] = false;
            if (g_holdPending[index]) {          // shorter than HoldMs
                g_holdPending[index] = false;
                if (shared) { toggled = true; toggleBy = "pad, short press"; }
            } else if (g_radOpen == 1 && g_radBy == kRadByPad) {
                radial = 2;
            }
        }
        if (g_holdPending[index] && holdCombo && now - g_holdStart[index] >= static_cast<DWORD>(g_radHoldMs)) {
            g_holdPending[index] = false;
            radial = 1;
        }
    }
    // after a toggle the pad stays neutral until both sticks are released, so the game never sees the half combo
    if (g_swallow[index] && !(buttons & g_toggleButtons)) g_swallow[index] = false;
    bool neutral = g_swallow[index];
    bool pending = g_holdPending[index] && shared;
    LeaveCriticalSection(&g_padLock);
    if (toggled) ToggleMenu(toggleBy);
    if (radial == 1 && !g_menuOpen) {
        InterlockedExchange(&g_radBy, kRadByPad);
        InterlockedExchange(&g_radJust, 1);
        // 0.10.1 Mode=menu: open = latched at once (state 2) - the release of the hold runs nothing
        InterlockedExchange(&g_radOpen, g_radMode == kRadModeMenu ? 2 : 1);
        Log(2, "radial: opened (pad hold %d ms%s)", g_radHoldMs, g_radMode == kRadModeMenu ? ", menu mode: stays open" : "");
    } else if (radial == 2) {
        InterlockedExchange(&g_radRelease, 1);
    } else if (radial == 3) {
        InterlockedExchange(&g_radBy, kRadByPad);
        InterlockedExchange(&g_radOpen, 1);
    } else if (radial == 4) {
        InterlockedExchange(&g_radCloseReq, 1);
    }
    if (g_radSwallow && !buttons) InterlockedExchange(&g_radSwallow, 0);
    if (g_blockInput && g_menuOpen) return 1;
    // 0.10.1: PassLeftStick only in Mode=wheel; Mode=menu gives the game the whole pad neutral (the left stick picks)
    if (g_radOpen || pending || g_radSwallow) return g_radPassLeft && g_radMode == kRadModeWheel ? 2 : 1;
    return neutral ? 1 : 0;
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
    int neutral = OnPad(index, connected, &copy, 0);
    if (neutral && connected) {
        DWORD packet = state->dwPacketNumber;
        SHORT lx = state->sThumbLX, ly = state->sThumbLY;
        memset(state, 0, sizeof(*state));
        state->dwPacketNumber = packet;
        if (neutral == 2) {                   // 0.10 radial menu, [Radial] PassLeftStick=1: Lara can walk
            state->sThumbLX = lx;
            state->sThumbLY = ly;
        }
    }
    g_lastPadHookTick = GetTickCount();
    if (g_reqPending) RunPending();           // game thread; the game clock may stand still (front end, pause)
    SoundFreezeTick();                        // 0.10.3: every poll - the game clock stands still while paused
    ShaderClockTick();                        // 0.10.4: likewise (F7 light shaft: TimeVector held with the freeze)
    DWORD clock = *kGameClock;
    if (clock != g_lastClock) {               // once per game frame (the game polls several pads per frame)
        g_lastClock = clock;
        if (!g_menuOpen && connected) FlightTick(copy);
        WeaponsTick();
        InvincibleTick();
        NoDamageTick();                       // 0.10.2: cheat.godfull no-damage bit [0xfada74] & 0x20000
        CheatsTick();                         // 0.8: [Cheats] Persist restore, infinite ammo re-apply
        NavTick();                            // 0.12: [Debug] NavDraw / NavMask (once, first loaded level)
        SafeGroundTick();                     // 0.8.1: player.unstuck ring
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
    bool want = (g_menuOpen || g_radOpen) && g_freeMouse;   // 0.10: the radial menu holds the mouse as well
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
    // 0.10.1: the radial menu in Mode=menu holds the keyboard like the menu (Enter / Backspace / Esc / arrows are its keys)
    if (g_blockGameInput && (g_menuOpen || RadMenuOpen())) {
        if (!g_kbdWasBlocked) Log(2, "keyboard: held (%s open)", g_menuOpen ? "menu" : "radial menu");
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
            if (g_radKeyDik && e.key == g_radKeyDik) continue;   // 0.10: [Radial] Key belongs to the radial menu
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
    if (g_imguiReady && g_menuOpen) {           // 0.8.1 input trace: clicks and keys (no auto-repeat) as edges
        SHORT mx = static_cast<SHORT>(LOWORD(lParam)), my = static_cast<SHORT>(HIWORD(lParam));
        switch (msg) {
        case WM_LBUTTONDOWN: case WM_LBUTTONUP: EdgeAdd(kEdgeMouse, msg == WM_LBUTTONDOWN, 2, 0, 1, mx, my); break;
        case WM_RBUTTONDOWN: case WM_RBUTTONUP: EdgeAdd(kEdgeMouse, msg == WM_RBUTTONDOWN, 2, 0, 2, mx, my); break;
        case WM_MBUTTONDOWN: case WM_MBUTTONUP: EdgeAdd(kEdgeMouse, msg == WM_MBUTTONDOWN, 2, 0, 3, mx, my); break;
        case WM_KEYDOWN:
            if (!(lParam & 0x40000000)) EdgeAdd(kEdgeKey, 1, 2, 0, static_cast<WORD>(wParam & 0xff), 0, 0);
            break;
        case WM_KEYUP: EdgeAdd(kEdgeKey, 0, 2, 0, static_cast<WORD>(wParam & 0xff), 0, 0); break;
        default: break;
        }
    }
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
    } else if (g_blockGameInput && RadMenuOpen() && IsKeyMessage(msg)) {
        // 0.10.1 [Radial] Mode=menu: no key message reaches the game while the ring is open (the ring reads Enter /
        // Backspace / Esc / arrows with GetAsyncKeyState); a key that went down meanwhile keeps its key-up away after the
        // close (g_msgKeyHeld, as for the menu)
        if (msg == WM_KEYDOWN && wParam < 256) g_msgKeyHeld[wParam] = 1;
        if (msg == WM_KEYUP && wParam < 256) g_msgKeyHeld[wParam] = 0;
        return 0;
    } else if (g_blockGameInput && msg == WM_KEYUP && wParam < 256 && g_msgKeyHeld[wParam]) {
        g_msgKeyHeld[wParam] = 0;               // 0.7.1: went down while the menu was open - the game saw no key-down
        return 0;
    } else if (g_radEnabled) {
        // 0.10 radial menu: its key and mouse button never reach the game; while the ring is open the mouse belongs to
        // it ([Menu] FreeMouse) - the direction is read with GetCursorPos in RadialTick, no message is needed
        if ((msg == WM_KEYDOWN || msg == WM_KEYUP) && g_radKey && static_cast<int>(wParam) == g_radKey) return 0;
        if ((msg == WM_MBUTTONDOWN || msg == WM_MBUTTONUP) && g_radMouse == 3) return 0;
        if ((msg == WM_XBUTTONDOWN || msg == WM_XBUTTONUP) && (g_radMouse == 4 || g_radMouse == 5) &&
            GET_XBUTTON_WPARAM(wParam) == (g_radMouse == 4 ? XBUTTON1 : XBUTTON2))
            return 0;
        if (g_radOpen && g_freeMouse && IsMouseMessage(msg)) return 0;
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

bool CmdTextActive();                       // 0.6 command bar state, defined with the bar
// 0.8.1 input trace: what the menu did in one frame (render thread only)
struct TraceFrameRec {
    ImGuiID navId, hoverId, actId, navActId;
    char navLabel[72], hoverLabel[72], actLabel[72], navWindow[40], barNote[120];
    bool navAlive, navDisabled, osk, barFocus, textActive;
    WORD raw, fed, barOwned, rowOwned;   // pad buttons: read, given to ImGui, taken by the bar / keyboard, by a row
    InputEdge edges[kEdgeMax];
    int edgeCount;
};
TraceFrameRec g_trf[2];
int g_trfCur = 0;

void TraceLabel(const char *label, char *out, size_t size) {
    size_t i = 0;
    for (; label[i] && i + 1 < size && !(label[i] == '#' && label[i + 1] == '#'); ++i) out[i] = label[i];
    while (i && out[i - 1] == ' ') --i;
    out[i] = 0;
    if (!i) _snprintf_s(out, size, _TRUNCATE, "%.60s", label);   // "##id" only: show the id part
}
// after every wrapped widget: remember its label when it is the focused / hovered / activated one
void TraceItem(const char *label, bool pressed) {
    if (!g_menuOpen || !label) return;
    ImGuiContext &g = *GImGui;
    ImGuiID id = g.LastItemData.ID;
    if (!id) return;
    TraceFrameRec &f = g_trf[g_trfCur];
    if (id == g.NavId) {
        TraceLabel(label, f.navLabel, sizeof(f.navLabel));
        f.navDisabled = (g.LastItemData.ItemFlags & ImGuiItemFlags_Disabled) != 0;
    }
    if (id == g.HoveredId) TraceLabel(label, f.hoverLabel, sizeof(f.hoverLabel));
    if (pressed) {
        f.actId = id;
        TraceLabel(label, f.actLabel, sizeof(f.actLabel));
    }
}
// the widgets the pages use, with the trace hook (same arguments as ImGui's)
template <typename... A> bool TmButton(const char *label, A... a) {
    bool r = ImGui::Button(label, a...);
    TraceItem(label, r);
    return r;
}
template <typename... A> bool TmSmallButton(const char *label, A... a) {
    bool r = ImGui::SmallButton(label, a...);
    TraceItem(label, r);
    return r;
}
template <typename... A> bool TmCheckbox(const char *label, A... a) {
    bool r = ImGui::Checkbox(label, a...);
    TraceItem(label, r);
    return r;
}
template <typename... A> bool TmSelectable(const char *label, A... a) {
    bool r = ImGui::Selectable(label, a...);
    TraceItem(label, r);
    return r;
}
template <typename... A> bool TmCollapsingHeader(const char *label, A... a) {
    bool r = ImGui::CollapsingHeader(label, a...);
    TraceItem(label, ImGui::IsItemToggledOpen());
    return r;
}

const char *KeyName(WORD vk, char *buf, size_t size) {
    switch (vk) {
    case VK_RETURN: return "Enter";
    case VK_ESCAPE: return "Esc";
    case VK_SPACE: return "Space";
    case VK_TAB: return "Tab";
    case VK_BACK: return "Backspace";
    case VK_UP: return "Up";
    case VK_DOWN: return "Down";
    case VK_LEFT: return "Left";
    case VK_RIGHT: return "Right";
    case VK_SHIFT: return "Shift";
    case VK_CONTROL: return "Ctrl";
    default: break;
    }
    if (vk >= VK_F1 && vk <= VK_F24) _snprintf_s(buf, size, _TRUNCATE, "F%d", vk - VK_F1 + 1);
    else if ((vk >= '0' && vk <= '9') || (vk >= 'A' && vk <= 'Z')) _snprintf_s(buf, size, _TRUNCATE, "%c", vk);
    else _snprintf_s(buf, size, _TRUNCATE, "vk 0x%02x", vk);
    return buf;
}

// start of a frame (before FeedGamepad): the record of this frame, the edges since the last frame
void TraceBegin() {
    g_trfCur ^= 1;
    TraceFrameRec &f = g_trf[g_trfCur];
    memset(&f, 0, sizeof(f));
    EnterCriticalSection(&g_edgeLock);
    f.edgeCount = g_edgeCount;
    memcpy(f.edges, g_edgeQueue, sizeof(InputEdge) * static_cast<size_t>(g_edgeCount));
    g_edgeCount = 0;
    LeaveCriticalSection(&g_edgeLock);
}

// end of frame N + 1: one line per edge of frame N ("prev") with the focus of both frames
void TraceEnd() {
    ImGuiContext &g = *GImGui;
    TraceFrameRec &cur = g_trf[g_trfCur], &prev = g_trf[g_trfCur ^ 1];
    cur.navId = g.NavId;
    cur.navAlive = g.NavIdIsAlive;
    cur.hoverId = g.HoveredId;
    cur.navActId = g.NavActivateId;
    _snprintf_s(cur.navWindow, sizeof(cur.navWindow), _TRUNCATE, "%s", g.NavWindow ? g.NavWindow->Name : "-");
    char *hash = strstr(cur.navWindow, "###");
    if (hash) *hash = 0;
    if (!cur.navLabel[0] && cur.navId) _snprintf_s(cur.navLabel, sizeof(cur.navLabel), _TRUNCATE, "0x%08x", cur.navId);
    bool trace = g_inputTrace && g_logLevel >= 2;
    for (int i = 0; i < prev.edgeCount; ++i) {
        const InputEdge &e = prev.edges[i];
        char what[48], result[400] = "-", kb[16];
        bool aLike = false;
        if (e.kind == kEdgePad) {
            const char *name = "?";
            for (const PadBitName &b : kPadBits) if (b.mask == e.code) name = b.name;
            _snprintf_s(what, sizeof(what), _TRUNCATE, "pad%d %s %s", e.pad, name, e.down ? "down" : "up");
            if (e.down) InterlockedIncrement(&g_sumPad);
            if (!e.down) {
                result[0] = 0;
            } else if (static_cast<int>(e.pad) != g_lastPad) {
                _snprintf_s(result, sizeof(result), _TRUNCATE, "not the menu's pad (menu reads pad%d)", g_lastPad);
            } else if (!(prev.raw & e.code)) {
                _snprintf_s(result, sizeof(result), _TRUNCATE, "pressed and released between two frames - ImGui never saw it");
            } else if (prev.barOwned & e.code) {
                _snprintf_s(result, sizeof(result), _TRUNCATE, "%s owns the pad%s%s", prev.osk ? "on-screen keyboard" :
                            "command bar", prev.barNote[0] ? ": " : "", prev.barNote);
            } else if (prev.rowOwned & e.code) {
                _snprintf_s(result, sizeof(result), _TRUNCATE, "%s on the focused TO TEST / Regression row",
                            e.code == 0x4000 ? "X = fail" : "Y = skip");
            } else if (e.code & g_toggleButtons) {
                _snprintf_s(result, sizeof(result), _TRUNCATE, "menu combo / FocusButton (not given to a widget)");
            } else if (e.code == 0x1000) {
                aLike = true;
            } else if (e.code & 0x000F) {
                _snprintf_s(result, sizeof(result), _TRUNCATE, "focus '%s' -> '%s' (%s)", prev.navLabel[0] ? prev.navLabel :
                            "none", cur.navLabel[0] ? cur.navLabel : "none", cur.navWindow);
            } else {
                _snprintf_s(result, sizeof(result), _TRUNCATE, "given to ImGui (focus '%s')", prev.navLabel[0] ?
                            prev.navLabel : "none");
            }
        } else if (e.kind == kEdgeMouse) {
            _snprintf_s(what, sizeof(what), _TRUNCATE, "mouse %s %s at %d,%d", e.code == 1 ? "left" : e.code == 2 ?
                        "right" : "middle", e.down ? "down" : "up", e.x, e.y);
            if (e.down) {
                InterlockedIncrement(&g_sumMouse);
                _snprintf_s(result, sizeof(result), _TRUNCATE, "over '%s'", prev.hoverLabel[0] ? prev.hoverLabel :
                            prev.hoverId ? "unlabelled widget" : "no widget");
            } else if (e.code == 1) {
                if (prev.actId) _snprintf_s(result, sizeof(result), _TRUNCATE, "activated '%s'", prev.actLabel);
                else _snprintf_s(result, sizeof(result), _TRUNCATE, "no click (released outside the pressed widget, "
                                 "or its id changed meanwhile)");
            } else {
                result[0] = 0;
            }
        } else {
            WORD vk = e.code;
            _snprintf_s(what, sizeof(what), _TRUNCATE, "key %s %s", KeyName(vk, kb, sizeof(kb)), e.down ? "down" : "up");
            if (e.down) InterlockedIncrement(&g_sumKeys);
            if (!e.down) result[0] = 0;
            else if (prev.textActive) _snprintf_s(result, sizeof(result), _TRUNCATE, "into the command bar text field");
            else if (vk == VK_RETURN || vk == VK_SPACE) aLike = true;
            else if (vk == VK_UP || vk == VK_DOWN || vk == VK_LEFT || vk == VK_RIGHT)
                _snprintf_s(result, sizeof(result), _TRUNCATE, "focus '%s' -> '%s' (%s)", prev.navLabel[0] ?
                            prev.navLabel : "none", cur.navLabel[0] ? cur.navLabel : "none", cur.navWindow);
        }
        if (aLike) {                                  // pad A / Enter / Space: activated or why not
            if (e.kind == kEdgePad) InterlockedIncrement(&g_sumA);
            ImGuiID act = prev.actId ? prev.actId : prev.navActId;
            if (act) {
                if (e.kind == kEdgePad) InterlockedIncrement(&g_sumAAct);
                _snprintf_s(result, sizeof(result), _TRUNCATE, "activated '%s' (0x%08x)", prev.actId ? prev.actLabel :
                            "unlabelled widget", act);
            } else {
                if (e.kind == kEdgePad) InterlockedIncrement(&g_sumANot);
                const char *why = !prev.navId ? "no widget has the nav focus"
                                : !prev.navAlive ? "the focused widget was not drawn in that frame - its id changed "
                                                   "(label with ## instead of ###) or its page is closed"
                                : prev.navDisabled ? "the focused widget is disabled"
                                : !(g.IO.ConfigFlags & ImGuiConfigFlags_NavEnableGamepad) ? "gamepad navigation off"
                                : "ImGui saw the press but no widget took it";
                _snprintf_s(result, sizeof(result), _TRUNCATE, "not activated: %s (focus '%s' 0x%08x in %s)", why,
                            prev.navLabel[0] ? prev.navLabel : "none", prev.navId, prev.navWindow);
            }
        }
        if (trace)
            Log(2, "input: %s (%s)%s%s", what, kEdgeSource[e.source < 3 ? e.source : 2], result[0] ? " -> " : "", result);
    }
}

// at the menu close: the summary (also with InputTrace=0)
void TraceSummary() {
    LONG dropped = InterlockedExchange(&g_edgeDropped, 0);
    Log(1, "input while the menu was open: %ld pad presses (A %ld: %ld activated, %ld not), %ld mouse clicks, %ld keys%s",
        InterlockedExchange(&g_sumPad, 0), InterlockedExchange(&g_sumA, 0), InterlockedExchange(&g_sumAAct, 0),
        InterlockedExchange(&g_sumANot, 0), InterlockedExchange(&g_sumMouse, 0), InterlockedExchange(&g_sumKeys, 0),
        dropped ? " (some edges dropped: queue full)" : "");
}

void FeedGamepad(ImGuiIO &io) {
    io.BackendFlags |= ImGuiBackendFlags_HasGamepad;
    PadState pad = {};
    bool have = false;
    EnterCriticalSection(&g_padLock);
    if (g_padConnected[g_lastPad]) { pad = g_pad[g_lastPad]; have = true; }
    LeaveCriticalSection(&g_padLock);
    if (!g_menuOpen || !have) memset(&pad, 0, sizeof(pad));
    const WORD rawButtons = pad.wButtons;        // 0.8.1 input trace
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
    {                                            // 0.8.1 input trace: who got which button in this frame
        TraceFrameRec &tf = g_trf[g_trfCur];
        tf.raw = rawButtons;
        tf.rowOwned = rowOwned;
        tf.barOwned = cmdOwned;
        tf.fed = pad.wButtons;
        tf.osk = g_oskOpen;
        tf.barFocus = g_cmdOwnPad;
        tf.textActive = CmdTextActive();
    }
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
    OnPad(index, connected, &state, 1);
    // no pad at that index: look at the next one twice a second (a pad that sends buttons becomes g_lastPad)
    if (!connected && ++frames % 30 == 0) {
        DWORD next = (index + 1 + (frames / 30) % 3) % 4;
        PadState other = {};
        bool found = poll(next, &other) == ERROR_SUCCESS;
        OnPad(next, found, &other, 1);
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
void QuitByHold();                                 // 0.8.1: button held 1 s
void ValRadialStatus(char *o, size_t n);           // 0.10 radial menu, defined after the command bar

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
    {
        static char radial[1024];
        ValRadialStatus(radial, sizeof(radial));
        ImGui::TextWrapped("radial (0.10.1): %s   [radial.status]", radial);
        ValFlowStatus(radial, sizeof(radial));   // 0.11
        ImGui::TextWrapped("flow (0.11): %s   [flow.status]", radial);
    }
    HMODULE d3d9 = GetModuleHandleA("d3d9.dll");
    char d3dPath[MAX_PATH] = "not loaded";
    if (d3d9) GetModuleFileNameA(d3d9, d3dPath, MAX_PATH);
    Text("d3d9: %s", g_d3dMode);
    ImGui::TextWrapped("  d3d9.dll = %s", d3dPath);
    Text("  device 0x%08lx, window 0x%08lx", reinterpret_cast<DWORD>(g_device), reinterpret_cast<DWORD>(g_hwnd));
    // game.quit: owner only (the item itself keeps the safety step). 0.8.1 (P00c): 0.8.0 put the countdown into the
    // armed label "CONFIRM ... (%lu s) ...##quit" - "##" only hides the rest, the id is the hash of the WHOLE label, so
    // the button got a new id every second. The pad / keyboard focus (NavId) then named a widget that no longer
    // existed and A did nothing until the label was "Quit game (press twice)##quit" again - the first id, so that press
    // re-armed (live 22:24:06 / :12 / :17 / :24). Now: fixed labels with "###" ids; while armed a separate red
    // "Quit now" button (fixed label; the focus moves to it once the arming press is released), the time left as text
    // beside it; holding A / Enter / the mouse 1 s on either button quits as well.
    ImGui::Separator();
    DWORD left = 0;
    bool armed = QuitArmed(&left);
    static bool focusMoved = false;
    static DWORD holdStart = 0;
    bool holding = false;
    if (TmButton("Quit game (press twice, or hold 1 s)  [game.quit]###quitarm")) QueueItem("game.quit", "");
    holding = holding || ImGui::IsItemActive();
    if (!armed) focusMoved = false;
    if (armed) {
        ImGui::SameLine();
        bool held = ImGui::IsKeyDown(ImGuiKey_GamepadFaceDown) || ImGui::IsKeyDown(ImGuiKey_Enter) ||
                    ImGui::IsKeyDown(ImGuiKey_Space) || ImGui::IsMouseDown(ImGuiMouseButton_Left);
        if (!focusMoved && !held) {               // after the arming press: the focus to "Quit now"
            ImGui::SetKeyboardFocusHere();
            focusMoved = true;
        }
        ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.7f, 0.2f, 0.1f, 1.0f));
        if (TmButton("Quit now  [game.quit]###quitnow")) QueueItem("game.quit", "");
        holding = holding || ImGui::IsItemActive();
        ImGui::PopStyleColor();
        ImGui::SameLine();
        ImGui::TextColored(ImVec4(1.0f, 0.45f, 0.4f, 1.0f), "armed - %lu s left", (left + 999) / 1000);
    }
    if (holding) {
        DWORD now = GetTickCount();
        if (!holdStart) holdStart = now ? now : 1;
        DWORD held = now - holdStart;
        ImGui::ProgressBar(held >= 1000 ? 1.0f : static_cast<float>(held) / 1000.0f, ImVec2(-1.0f, 0.0f),
                           "hold 1 s to quit");
        if (held >= 1000) {
            holdStart = 0;
            QuitByHold();
        }
    } else {
        holdStart = 0;
    }
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

// 0.8 [Log] CameraChanges (read-only). The camera manager 0xe804f0 is processed by 0x5f3c70 (vtable 0x855ae4 slot 10,
// called at 0x5f3e0c with ecx = 0xe804f0), which calls the mode chooser 0x5e7fe0 (thiscall, this = the manager): it
// writes the requested mode to manager+0x58 (0x5e80b9 `mov [esi+0x58], 0x34` = adrenaline mode when the player's
// +0x1fc bit 27 is set; values seen there 1 / 0x13 / 0x30 / 0x33 / 0x34 / 0x36), and at 0x5e80da compares it with the
// applied mode +0x54; on a difference it calls the current camera's vtbl[0x60](mode), stores +0x54 = +0x58 and
// zeroes the time in mode +0x5c (float). The current camera object is manager+0x44 (= 0xe80534); the manager holds
// camera objects at +0x120, +0x670, +0x5b90 and a pointer at +0xb80 (all compared with +0x44 in 0x5f3c70 / 0x5e7fe0).
// A target instance / object name is NOT logged: no field of the PC camera struct is proven to hold one.
const DWORD kCamReqMode = 0x00e804f0 + 0x58, kCamAppliedMode = 0x00e804f0 + 0x54, kCamModeTime = 0x00e804f0 + 0x5c;
bool g_camLogOk = false;
volatile LONG g_camModeChanges = 0, g_camObjectChanges = 0;

void CameraObjectName(DWORD cam, char *o, size_t n) {
    const DWORD m = 0x00e804f0;
    DWORD vtbl = 0, ptrB80 = 0;
    ReadDword(m + 0xb80, &ptrB80);
    const char *slot = cam == 0 ? "none" : cam == m + 0x120 ? "manager+0x120" : cam == m + 0x670 ? "manager+0x670"
                     : cam == m + 0x5b90 ? "manager+0x5b90" : cam == ptrB80 ? "[manager+0xb80]" : "other";
    if (cam) ReadDword(cam, &vtbl);
    _snprintf_s(o, n, _TRUNCATE, "0x%08lx (%s, vtable 0x%08lx)", cam, slot, vtbl);
}

void ValCameraLog(char *o, size_t n) {
    if (!g_camLogOk) { Out(o, n, "camera manager code check failed - no camera log"); return; }
    DWORD req = 0, applied = 0, cam = 0;
    float t = 0.0f;
    ReadDword(kCamReqMode, &req);
    ReadDword(kCamAppliedMode, &applied);
    ReadFloats(kCamModeTime, &t, 1);
    ReadDword(kCurrentCamera, &cam);
    char name[96];
    CameraObjectName(cam, name, sizeof(name));
    Out(o, n, "%ld (log); mode requested %lu (0x%lx, manager+0x58), applied %lu (+0x54), %.1f in mode (+0x5c); camera %s; "
        "changes: mode %ld, object %ld", g_cameraChanges, req, req, applied, t, name, g_camModeChanges, g_camObjectChanges);
}

bool RunCameraLog(const char *arg, char *o, size_t n) {
    if (!g_camLogOk) { Out(o, n, "camera manager code check failed - no camera log"); return false; }
    bool on = BoolArg(arg, g_cameraChanges != 0);
    InterlockedExchange(&g_cameraChanges, on ? 1 : 0);
    Out(o, n, "camera.log %d ([Log] CameraChanges for this session)", on ? 1 : 0);
    return true;
}

// render thread, at most every 200 ms (Render, before its early return)
void CameraTick() {
    static DWORD lastTick = 0, lastReq = 0xffffffff, lastCam = 0xffffffff;
    if (!g_cameraChanges || !g_camLogOk) return;
    DWORD now = GetTickCount();
    if (now - lastTick < 200) return;
    lastTick = now;
    DWORD req = 0, applied = 0, cam = 0;
    if (!ReadDword(kCamReqMode, &req) || !ReadDword(kCamAppliedMode, &applied) || !ReadDword(kCurrentCamera, &cam)) return;
    if (req != lastReq) {
        if (lastReq == 0xffffffff)
            Log(1, "camera: mode %lu (0x%lx) at the start of the log (applied %lu)", req, req, applied);
        else
            Log(1, "camera: mode %lu -> %lu (0x%lx -> 0x%lx; requested manager+0x58, applied +0x54 = %lu)", lastReq, req,
                lastReq, req, applied);
        if (lastReq != 0xffffffff) InterlockedIncrement(&g_camModeChanges);
        lastReq = req;
    }
    if (cam != lastCam) {
        char a[96], b[96];
        CameraObjectName(cam, b, sizeof(b));
        if (lastCam == 0xffffffff) {
            Log(1, "camera: object %s at the start of the log", b);
        } else {
            CameraObjectName(lastCam, a, sizeof(a));
            Log(1, "camera: object %s -> %s", a, b);
            InterlockedIncrement(&g_camObjectChanges);
        }
        lastCam = cam;
    }
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
    Out(o, n, "pad=%s; d3d9=%s; frontend-pad=%d; mouse=%s; keyboard=%s; pause=%s; autostart=%s; radial=%s (enabled %d, "
        "mode %s)", g_padMode, g_d3dMode, g_padModeIdle ? 1 : 0, g_mouseMode, g_kbdMode, g_pauseMode, g_autoStartMode,
        g_radOpen == 1 ? "open (hold)" : g_radOpen == 2 ? (g_radMode == kRadModeMenu ? "open (menu)" : "open (latched)")
                                                        : "closed",
        g_radEnabled, g_radMode == kRadModeMenu ? "menu" : "wheel");
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
DWORD g_markTick = 0;                          // 0.8.1 player.unstuck
char g_markUnit[40] = "";
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
    InterlockedExchange(&g_radPaused, 0);       // 0.10.1: nor the radial close ([Radial] Freeze=world): the user's choice
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
    InterlockedExchange(&g_radCtlOurs, 0);      // 0.10.1: [Radial] Freeze=player does not restore over the user's choice
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
// 0.10.2 (F6, los7: "Zur Marke" after a jump left Lara hanging at a ledge): marks and safe spots keep Lara's facing too.
// Only the yaw (instance +0x38, rotation z; TRLAU Instance.h rotation at +0x30) is written back - x / y stay as the game
// has them. Lara's movement state and velocity are NOT reset: no player-state / velocity field and no "stand now" call
// is proven (docs Menue-Funktionen-Katalog.md 2 / 17, Befund-*.md: none; locomotion is animation driven), so a recall
// during a jump or fall keeps that state (she may still grab a ledge in reach) - recall while she stands.
// 0.10.4 (F6, [Menu] MarkSetStand NOT built): no game function to put the player into standing was found offline -
// every PC state change goes through the data-driven chart (SCAgent::ChangeState tru+0x387890, called only from the
// agent's own transition / event code tru+0x387c78 / 0x387d53 / 0x387d9e); the script teleport NsInstance::WarpTo
// (2007 prototype map) and INSTANCE_SetPositionPlayerFindGround set position / rotation only. Which chart state is
// "stand" is data - a state log (TruTrace) has to show it first (docs Befund-Menue-Dlc2Player-0411b.md).
float g_markYaw = 0.0f;
bool SetYaw(DWORD inst, float yaw) {
    __try {
        reinterpret_cast<volatile float *>(inst + kInstanceRotation)[2] = yaw;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}
bool RunMark(const char *, char *o, size_t n) {
    float p[3], r[3];
    DWORD instance = 0;
    if (!ReadLara(p, r, &instance)) { Out(o, n, "needs a level"); return false; }
    memcpy(g_mark, p, sizeof(g_mark));
    g_markYaw = r[2];                            // 0.10.2
    g_markSet = true;
    g_markTick = GetTickCount();                 // 0.8.1 player.unstuck: the newer of mark / safe ground wins
    CurrentUnit(g_markUnit, sizeof(g_markUnit));
    Out(o, n, "mark %.1f %.1f %.1f yaw %.3f", p[0], p[1], p[2], r[2]);
    return true;
}
void ValMark(char *o, size_t n) {
    if (g_markSet) Out(o, n, "%.1f %.1f %.1f yaw %.3f", g_mark[0], g_mark[1], g_mark[2], g_markYaw); else Out(o, n, "-");
}
bool RunRecall(const char *, char *o, size_t n) {
    DWORD player = 0;
    if (!NeedPlayer(&player, o, n)) return false;
    if (!g_markSet) { Out(o, n, "no mark (player.mark first)"); return false; }
    if (!SetPosition(player, g_mark)) { Out(o, n, "write failed"); return false; }
    bool yaw = SetYaw(player, g_markYaw);
    Out(o, n, "player back at the mark %.1f %.1f %.1f, yaw %.3f%s (movement state / velocity unchanged)", g_mark[0],
        g_mark[1], g_mark[2], g_markYaw, yaw ? "" : " NOT written");
    return true;
}

// ---- 0.8.1 player.unstuck (P00c: in hall02 with god mode Lara slid into the eitr and could not get out) ----
// No "Lara stands on ground" flag is proven yet, so "safe ground" is read from the position (0.8.1: once per 15 game
// frames, standing = height changed less than 5 units over three samples; 0.10.2: see below). A spot goes into a ring
// of 16 when it is at least
// 100 units from the newest entry. player.unstuck takes the newer of player.mark and the newest ring entry that is at
// least 3 s old and 150 units away from Lara (so not the spot she is stuck at); run again within 20 s it goes one
// entry further back. Same unit only (GameTracker+0x38). "mark" / "safe" force the source.
//
// 0.10.2 (F6, B28): the sampler had two faults in the 03.11. tests. los3: the spot it chose (-1311 4869 -683) lay
// ~7300 units above Lara - recorded during the DLC 2 intro (a cinematic: Lara's instance stands still somewhere
// else). los7: walking on uneven ground changes the height by >= 5 units within 1 s, so hardly anything was recorded
// and unstuck went back to the DLC 2 start. Now:
//   * no sampling (and the window starts again) while the menu or the ring is open, the world pause bit
//     (streamFlags 0x1000, time.pause) is set, the main state is not 1 (play game; TRLAU enum: 5 = cinematic), a
//     cinematic runs (the game's own test tru+0x53f00: [0xe7f1c0] && byte +0xdd && dword +0x2c != -1 - the TU gate
//     TruShadowPower 0.9 uses; read here, not called; bytes checked at load), player.control is off, time.scale is
//     not 1 (the window is in game frames), flight is on or health <= 0.
//   * a HEURISTIC instead of "height still" (no proven "on ground" signal: no player-state / collision flag is
//     documented; the state-mode word [0xfada74] is rewritten by every state entry with undocumented bits): 7 samples
//     5 game frames apart (~1 s at 30 frames/s). The middle sample is a safe spot when every sample lies within 12
//     units of the straight line (chord) between the first and the last one - free flight (jump, fall) is a parabola
//     and leaves the chord by g t^2 / 8 (~120 units over 1 s at ~980 units/s^2, 1 unit ~ 1 cm) - and the slope from
//     first to last is at most 0.8 (~39 degrees: no ladder, climb or lift), with at most 10 units extra for steps.
//     Walking up / down a ramp or over small bumps passes, standing still passes as before. Known blind spots
//     (documented in README / docs\TruMenu-0.10.2.md): hanging at a ledge and shimmying, swimming at the surface and
//     riding a moving platform look like ground too.
struct SafeSpot { float p[3]; float yaw; DWORD tick; char unit[40]; };
const int kSafeMax = 16;
const int kSafeEvery = 5, kSafeWindow = 7;            // 0.10.2: sample spacing (game frames), samples per window
const float kSafeChord = 12.0f, kSafeSlope = 0.8f, kSafeStep = 10.0f;
SafeSpot g_safe[kSafeMax];
int g_safeCount = 0, g_safeNext = 0;           // ring (game thread writes, render thread reads the count)
CRITICAL_SECTION g_safeLock;
DWORD g_unstuckLastTick = 0, g_unstuckLastSpot = 0;   // repeat: entries older than the last one used
DWORD PlayerState();                                  // weapons section below
const char *g_safePause = "-";                        // 0.10.2: why the sampler waits now (player.unstuck value)
LONG g_safeRejected = 0, g_safeAccepted = 0;          // windows that failed / passed the ground test
bool g_cineOk = false;                                // 0.10.2: tru+0x53f00 bytes as expected

// 0.10.2: the game's cinematic test tru+0x53f00 (TruShadowPower's kCinematic), as reads
bool CinematicNow() {
    if (!g_cineOk) return false;
    DWORD cine = 0, track = 0;
    BYTE on = 0;
    if (!ReadDword(0x00e7f1c0, &cine) || !cine) return false;
    if (!ReadByte(cine + 0xdd, &on) || !on) return false;
    return ReadDword(cine + 0x2c, &track) && track != 0xffffffff;
}

// why no safe ground is sampled now ("" = sample)
const char *SafePauseReason() {
    if (g_menuOpen) return "menu open";
    if (g_radOpen) return "ring open";
    if (g_flight) return "flight on";
    DWORD v = 0;
    if (ReadDword(kStreamFlags, &v) && (v & 0x1000)) return "world paused (streamFlags 0x1000)";
    if (g_mainStateOk && ReadDword(kMainState, &v) && v != 1) return "main state not 1 (play game)";
    if (CinematicNow()) return "cinematic";
    BYTE control = 1;
    if (g_controlOk && ReadByte(kPlayerControl, &control) && !control) return "player control off";
    float scale = 1.0f;
    if (g_timeOk && ReadFloats(kTimeDilation, &scale, 1) && (scale < 0.99f || scale > 1.01f)) return "time.scale not 1";
    return "";
}

void SafeGroundTick() {
    static int frames = 0;
    static float w[kSafeWindow][4];                   // x y z yaw, oldest first
    static int wCount = 0;
    if (++frames < kSafeEvery) return;
    frames = 0;
    float p[3], r[3];
    DWORD inst = 0;
    const char *why = SafePauseReason();
    float health = 0.0f;
    DWORD ps = PlayerState();
    if (!why[0] && !ReadLara(p, r, &inst)) why = "no player";
    if (!why[0] && (!ps || !ReadFloats(ps + 0x628, &health, 1) || !(health > 0.0f))) why = "health <= 0";
    g_safePause = why[0] ? why : "-";
    if (why[0]) { wCount = 0; return; }
    if (wCount == kSafeWindow) {
        memmove(w[0], w[1], sizeof(w[0]) * (kSafeWindow - 1));
        --wCount;
    }
    w[wCount][0] = p[0]; w[wCount][1] = p[1]; w[wCount][2] = p[2]; w[wCount][3] = r[2];
    if (++wCount < kSafeWindow) return;
    const float *a = w[0], *b = w[kSafeWindow - 1];
    float hx = b[0] - a[0], hy = b[1] - a[1], rise = b[2] - a[2];
    float run = sqrtf(hx * hx + hy * hy);
    bool ground = fabsf(rise) <= kSafeSlope * run + kSafeStep;
    for (int i = 1; i < kSafeWindow - 1 && ground; ++i) {
        float expect = a[2] + rise * static_cast<float>(i) / static_cast<float>(kSafeWindow - 1);
        if (fabsf(w[i][2] - expect) > kSafeChord) ground = false;
    }
    if (!ground) { ++g_safeRejected; return; }
    ++g_safeAccepted;
    const float *m = w[kSafeWindow / 2];
    char unit[40];
    CurrentUnit(unit, sizeof(unit));
    EnterCriticalSection(&g_safeLock);
    bool add = true;
    if (g_safeCount) {
        const SafeSpot &last = g_safe[(g_safeNext + kSafeMax - 1) % kSafeMax];
        float dx = m[0] - last.p[0], dy = m[1] - last.p[1], dz = m[2] - last.p[2];
        add = dx * dx + dy * dy + dz * dz >= 100.0f * 100.0f || _stricmp(last.unit, unit) != 0;
    }
    if (add) {
        SafeSpot &s = g_safe[g_safeNext];
        memcpy(s.p, m, sizeof(s.p));
        s.yaw = m[3];
        s.tick = GetTickCount();
        strncpy_s(s.unit, sizeof(s.unit), unit, _TRUNCATE);
        g_safeNext = (g_safeNext + 1) % kSafeMax;
        if (g_safeCount < kSafeMax) ++g_safeCount;
    }
    LeaveCriticalSection(&g_safeLock);
}
void ValUnstuck(char *o, size_t n) {
    EnterCriticalSection(&g_safeLock);
    int c = g_safeCount;
    SafeSpot last = {};
    if (c) last = g_safe[(g_safeNext + kSafeMax - 1) % kSafeMax];
    LeaveCriticalSection(&g_safeLock);
    // 0.10.2: + windows passed / failed by the ground test and why the sampler waits
    if (!c) Out(o, n, "%d safe spots; mark %s; ground windows %ld ok / %ld not; waiting: %s", c, g_markSet ? "set" : "-",
                g_safeAccepted, g_safeRejected, g_safePause);
    else Out(o, n, "%d safe spots, newest %.0f %.0f %.0f (%lu s ago, %s); mark %s; ground windows %ld ok / %ld not; "
             "waiting: %s", c, last.p[0], last.p[1], last.p[2], (GetTickCount() - last.tick) / 1000, last.unit,
             g_markSet ? "set" : "-", g_safeAccepted, g_safeRejected, g_safePause);
}
bool RunUnstuck(const char *arg, char *o, size_t n) {
    DWORD player = 0;
    if (!NeedPlayer(&player, o, n)) return false;
    float p[3], r[3];
    DWORD inst = 0;
    if (!ReadLara(p, r, &inst)) { Out(o, n, "needs a level"); return false; }
    bool onlyMark = arg && !_stricmp(arg, "mark"), onlySafe = arg && !_stricmp(arg, "safe");
    if (arg && arg[0] && !onlyMark && !onlySafe) { Out(o, n, "usage: player.unstuck [mark|safe]"); return false; }
    char unit[40];
    CurrentUnit(unit, sizeof(unit));
    DWORD now = GetTickCount();
    bool repeat = g_unstuckLastTick && now - g_unstuckLastTick < 20000;
    // newest usable ring entry
    SafeSpot spot = {};
    bool haveSpot = false;
    EnterCriticalSection(&g_safeLock);
    for (int i = 1; i <= g_safeCount && !onlyMark; ++i) {
        const SafeSpot &s = g_safe[(g_safeNext + kSafeMax - i) % kSafeMax];
        if (_stricmp(s.unit, unit) != 0 || now - s.tick < 3000) continue;
        if (repeat && g_unstuckLastSpot && static_cast<LONG>(s.tick - g_unstuckLastSpot) >= 0) continue;
        float dx = p[0] - s.p[0], dy = p[1] - s.p[1], dz = p[2] - s.p[2];
        if (dx * dx + dy * dy + dz * dz < 150.0f * 150.0f) continue;
        spot = s;
        haveSpot = true;
        break;
    }
    LeaveCriticalSection(&g_safeLock);
    bool markOk = g_markSet && !onlySafe && !_stricmp(g_markUnit, unit) && (!repeat || onlyMark);   // repeat: further back
    bool useMark = markOk && (!haveSpot || static_cast<LONG>(g_markTick - spot.tick) > 0 || onlyMark);
    if (!useMark && !haveSpot) {
        Out(o, n, "no target: %s%s", markOk || onlySafe ? "" : "no player.mark in this unit, ",
            onlyMark ? "" : "no safe spot >= 3 s old and >= 150 units away in this unit (walk on firm ground first)");
        return false;
    }
    const float *to = useMark ? g_mark : spot.p;
    if (!SetPosition(player, to)) { Out(o, n, "write failed"); return false; }
    float yaw = useMark ? g_markYaw : spot.yaw;  // 0.10.2: the facing of that moment too
    bool yawOk = SetYaw(player, yaw);
    g_unstuckLastTick = now;
    g_unstuckLastSpot = useMark ? g_markTick : spot.tick;
    Out(o, n, "player.unstuck: %s %.0f %.0f %.0f yaw %.3f%s%s (from %.0f %.0f %.0f)", useMark ? "player.mark" : "safe ground",
        to[0], to[1], to[2], yaw, yawOk ? "" : " (yaw NOT written)", useMark ? "" : (repeat ? ", one further back" : ""),
        p[0], p[1], p[2]);
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

// ---- 0.10 stage R2: instance.spawn <object> at Lara ([Radial] Spawn=1; workspace docs\Menue-Funktionen-Katalog.md
// section 6 "Spawn object at Lara", addresses re-read with tools/pe_dis.py / pe_callers.py / pe_find_bytes.py,
// byte list work\asi\menu010\precheck_010.txt) ----
// The order of the catalog row, each step the game's own function:
//   1. DRM present: 0x5bf7b0(name) = LOAD_UnitFileName 0x477970(buf[0x100], name) ("%s%s.drm" 0x8443bc with the prefix
//      0xa03824) + GetFS 0x472b50 ([0x9ce278]) -> vtable +8 (FileExists) - the game's own composition (the costume
//      validator 0x5c54e0 tail-calls it, the level load calls it at 0x5de368); bool cdecl, plain ret
//   2. OBTABLE_GetObjectID 0x5bf770 != 0 (TruMenu's ObjectId reads the same table)
//   3. STREAM_GetObjectTrackerByName 0x5c17d0(name) cdecl: id -> 0x5c1550(id, 0) = find or request the tracker entry
//      (0xdb7400, 0xcc entries of 0x24: +8 Object*, +0xc s16 id, +0xe u16 status; a new entry gets status 1 at
//      0x5c1670; no free entry = "Out of objecttracker space!" 0x854154 - so TruMenu wants 2 free entries first)
//   4. STREAM_PollLoadQueue 0x5c1da0 () until status 2 = loaded (the game's own loaded test 0x5bf2e0 "cmp word
//      [eax+0xe], 2"), at most kSpawnTimeoutMs; the costume switch 0x6f0bc5 polls the same way after 0x5c17d0
//   5. INSTANCE_BirthObjectNoParent 0x5bd0f0(StreamUnitID [0xe7f148], &pos, &rot, NULL, tracker->object, 0, 1) cdecl,
//      7 arguments (the script native 0x780aaf passes (unit, &pos, &rot, x, object, 0, 1), add esp 0x1c); pos / rot are
//      copied at once (0x5bd180: 16 bytes each into instance +0x20 / +0x30); returns the new instance or 0
// Runs on the game thread (queued); the load blocks it (a stutter), inside __try.
typedef bool(__cdecl *DrmExistsFn)(const char *name);
typedef DWORD(__cdecl *TrackerByNameFn)(const char *name);
typedef int(__cdecl *PollLoadQueueFn)();
typedef DWORD(__cdecl *BirthObjectFn)(DWORD unitId, const float *pos, const float *rot, void *intro, DWORD object, int a,
                                      int b);
const DWORD kDrmExists = 0x005bf7b0, kTrackerByName = 0x005c17d0, kPollLoadQueue = 0x005c1da0,
            kBirthObject = 0x005bd0f0;
const DWORD kSpawnTimeoutMs = 3000;
bool g_spawnOk = false;
const char *g_spawnWhy = "not checked";
LONG g_spawnCount = 0;

bool SpawnCheck() {
    bool drm = HexBytesAt(kDrmExists, "81ec04010000 a1e8d78b00 33c4 89842400010000 8b842408010000 50 8d442404 50 "
                                      "e89a81ebff 83c408 e87233ebff 8b10 8b5208 8d0c24 51 8bc8 ffd2") &&
               HexBytesAt(0x00477970, "8b442408 8b4c2404 50 682438a000 68bc438400 51 e86cc23900 83c410 c3") &&
               HexBytesAt(0x008443bc, "25732573 2e64726d 00") && HexBytesAt(0x00472b50, "a178e29c00 c3") &&
               HexBytesAt(0x005c54f8, "e9b3a2ffff");
    bool tracker = HexBytesAt(kTrackerByName, "56 57 8b7c240c 57 e894dfffff 8bf0 83c404 85f6 750e 57 68b8418500 "
                                              "e86073ebff 83c408 6a00 56 e855fdffff") &&
                   HexBytesAt(0x005c17fb, "83c408 83f8ff 5f 5e 7503 33c0 c3 8d04c0 8d04850074db00 c3") &&
                   HexBytesAt(0x005c15c6, "66837e0e00 7459") && HexBytesAt(0x005c162e, "e87dfeffff 6854418500 e87356fdff") &&
                   HexBytesAt(0x005c1670, "66c7460e0100 66896e0c") &&
                   HexBytesAt(0x005bf2d4, "b80074db00 b9cc000000 57 90 6683780e02 7508 0fbf780c 3bfa");
    bool poll = HexBytesAt(kPollLoadQueue, "56 e8aa0debff 8b10 8bc8 8b4218 ffd0 8bf0 e89a0debff 8b10 8bc8 8b421c ffd0 "
                                           "83fe01 5e 7416") &&
                HexBytesAt(0x005c1dd8, "33c0 c3 b801000000 c3") &&
                HexBytesAt(0x006f0bc5, "e8060cedff 83c414 8bf0 e8cc11edff 84c0 7423");
    bool birth = HexBytesAt(kBirthObject, "55 8bec 83e4f0 83ec24 53 56 57 8b7d18 85ff 897c242c 0f8455010000 8b07 "
                                          "f6400810 0f8549010000 e8d45dffff 8bf0 85f6") &&
                 HexBytesAt(0x005bd180, "8b03 f30f10051c118400 894620 8b4b04 894e24 8b5308 895628 8b430c 89462c 8b0f "
                                        "894e30") &&
                 HexBytesAt(0x005bd257, "8bc6 5f 5e 5b 8be5 5d c3") &&
                 HexBytesAt(0x00780aaf, "6a01 6a00 53 52 83c030 50 57 51 e830c6e3ff 8bf0 83c41c");
    bool names = HexBytesAt(kNameLookup, kNameLookupBytes) &&
                 HexBytesAt(0x005dfc88, "8b1548f1e700 3b90e0000000");   // StreamUnitID 0xe7f148 vs player +0xe0
    g_spawnWhy = !drm ? "DRM check 0x5bf7b0 / LOAD_UnitFileName 0x477970 / GetFS 0x472b50 bytes differ"
               : !tracker ? "STREAM_GetObjectTrackerByName 0x5c17d0 / tracker table code differs"
               : !poll ? "STREAM_PollLoadQueue 0x5c1da0 bytes differ"
               : !birth ? "INSTANCE_BirthObjectNoParent 0x5bd0f0 / its script native call 0x780aaf differ"
               : !names ? "OBTABLE_GetObjectID 0x5bf770 / the StreamUnitID read 0x5dfc88 differ"
               : !g_playerOk || !g_unitOk ? "player / stream unit code (0.1 / 0.2 checks) failed"
               : !g_mainStateOk ? "main state check (0.3) failed" : "ok";
    return drm && tracker && poll && birth && names && g_playerOk && g_unitOk && g_mainStateOk;
}

// [Radial] Spawn is read again from TruMenu.ini (at most once a second), so the TO TEST switch
// "ini:TruMenu:Radial:Spawn" works in the running game - the safe default 0 stays until the owner ticks it
bool SpawnOn() {
    static DWORD last = 0;
    DWORD now = GetTickCount();
    if (g_iniPath[0] && (!last || now - last > 1000)) {
        last = now ? now : 1;
        g_radSpawn = GetPrivateProfileIntA("Radial", "Spawn", g_radSpawn, g_iniPath) != 0 ? 1 : 0;
    }
    return g_radSpawn != 0;
}

void ValSpawn(char *o, size_t n) {
    Out(o, n, "%s; [Radial] Spawn=%d; %ld spawned this session", g_spawnOk ? "code ok" : g_spawnWhy, g_radSpawn,
        g_spawnCount);
}

// tracker entries: the one of <id> (status != 0) or -1, and the number of free ones (status 0)
int TrackerScan(int id, int *freeCount) {
    int found = -1, unused = 0;
    for (int i = 0; i < kObjectEntries; ++i) {
        WORD status = 0, oid = 0;
        DWORD e = kObjectTable + static_cast<DWORD>(i) * 0x24;
        if (!ReadWord(e + 0xe, &status) || !ReadWord(e + 0xc, &oid)) continue;
        if (!status) ++unused;
        else if (static_cast<SHORT>(oid) == id && found < 0) found = i;
    }
    *freeCount = unused;
    return found;
}

bool RunInstanceSpawn(const char *arg, char *o, size_t n) {
    if (!SpawnOn()) { Out(o, n, "off ([Radial] Spawn=0 - stage R2, back up the saves before switching it on)"); return false; }
    if (!g_spawnOk) { Out(o, n, "disabled: pre-check failed (%s)", g_spawnWhy); return false; }
    if (!g_experimental) { Out(o, n, "experimental actions off ([Cheat] Experimental=0)"); return false; }
    DWORD state = 0, player = 0;
    ReadDword(kMainState, &state);
    if (!InLevel() || state != 1 || !ReadDword(kPlayerPtr, &player) || !player) {
        Out(o, n, "in a level only (main state %lu, needs 1)", state);
        return false;
    }
    char why[160];
    if (LevelChangePending(why, sizeof(why))) { Out(o, n, "refused: %s", why); return false; }
    static char name[64];                    // stays valid for the game (tracker / log calls keep the pointer)
    size_t len = 0;
    for (; arg && arg[len] && arg[len] != ' ' && len + 1 < sizeof(name); ++len) {
        char c = static_cast<char>(tolower(static_cast<unsigned char>(arg[len])));
        if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_')) {
            Out(o, n, "object names are a-z 0-9 _ only");
            return false;
        }
        name[len] = c;
    }
    name[len] = 0;
    if (!len) { Out(o, n, "usage: instance.spawn <object name> (e.g. sh_ei_combat_crate_a, g_healthpack)"); return false; }
    int id = ObjectId(name);
    if (!id) { Out(o, n, "'%s' is not in the object list (OBTABLE_GetObjectID would answer 0)", name); return false; }
    int freeCount = 0;
    int entry = TrackerScan(id, &freeCount);
    if (entry < 0 && freeCount < 2) {
        Out(o, n, "refused: object tracker nearly full (%d free of %d) - the game would stop with \"Out of objecttracker "
            "space!\"", freeCount, kObjectEntries);
        return false;
    }
    __declspec(align(16)) float pos[4], rot[4];
    DWORD unitId = 0, playerUnit = 0, tracker = 0, object = 0, inst = 0, start = GetTickCount(), polls = 0;
    WORD status = 0;
    bool exists = false;
    __try {
        exists = reinterpret_cast<DrmExistsFn>(kDrmExists)(name);
        if (!exists) {
            Out(o, n, "no %s.drm (the game's FileExists 0x5bf7b0 answered 0)", name);
            return false;
        }
        tracker = reinterpret_cast<TrackerByNameFn>(kTrackerByName)(name);
        if (!tracker) { Out(o, n, "STREAM_GetObjectTrackerByName(\"%s\") = 0", name); return false; }
        while (ReadWord(tracker + 0xe, &status) && status != 2 && GetTickCount() - start < kSpawnTimeoutMs) {
            reinterpret_cast<PollLoadQueueFn>(kPollLoadQueue)();
            ++polls;
            Sleep(1);
        }
        if (status != 2) {
            Out(o, n, "%s not loaded within %lu ms (tracker 0x%08lx status %u after %lu polls) - the load request stays; "
                "run it again", name, kSpawnTimeoutMs, tracker, status, polls);
            return false;
        }
        if (!ReadDword(tracker + 8, &object) || !object) { Out(o, n, "tracker 0x%08lx has no object", tracker); return false; }
        if (!ReadFloats(player + kInstancePosition, pos, 4) || !ReadFloats(player + kInstanceRotation, rot, 4) ||
            !ReadDword(kUnitId, &unitId)) {
            Out(o, n, "player position / stream unit id not readable");
            return false;
        }
        ReadDword(player + 0xe0, &playerUnit);
        inst = reinterpret_cast<BirthObjectFn>(kBirthObject)(unitId, pos, rot, nullptr, object, 0, 1);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
        Out(o, n, "exception while spawning %s (tracker 0x%08lx, object 0x%08lx)", name, tracker, object);
        Log(0, "instance.spawn: exception (%s, tracker 0x%08lx status %u, object 0x%08lx)", name, tracker, status, object);
        return false;
    }
    if (!inst) {
        Out(o, n, "INSTANCE_BirthObjectNoParent returned 0 for %s (object 0x%08lx, unit %lu)", name, object, unitId);
        return false;
    }
    InterlockedIncrement(&g_spawnCount);
    Out(o, n, "%s (id %d) born at Lara (%.0f %.0f %.0f): instance 0x%08lx; tracker 0x%08lx %s, %lu polls / %lu ms; "
        "stream unit %lu (player +0xe0 = %lu)", name, id, pos[0], pos[1], pos[2], inst, tracker,
        entry >= 0 ? "was in the table" : "requested now", polls, GetTickCount() - start, unitId, playerUnit);
    Log(1, "instance.spawn: %s", o);
    return true;
}

// ======================================================================================================================
// 0.8 Cheats page (docs\Befund-Prototyp-2007.md section 3i; names from the 2007 prototype map, PC addresses by code
// semantics, checked with tools/pe_dis.py / pe_abs_uses.py / pe_callers.py; byte list work\asi\menu080\precheck_080.txt).
// Every row shows its category; every write runs on the game thread (gameThread items, QueueItem) and only in a level.
// ======================================================================================================================
enum CheatCat { kCatSwitch, kCatReattach, kCatCode, kCatRebuild };
const char *const kCheatCatNames[] = {"PC has it (switchable)", "logic present, entry cut (re-attach)",
                                      "cheat-code path (DEBUG_ApplyCheatCode)", "flag + reader gone (rebuild from prototype)"};
// ProcessHealth 0x6f5160: if ([0xfadf63] || [0xfadf60]) { P+0x638 = 30.0 (hit-invulnerability timer); P+0x63c = 5 }
const DWORD kGodByte = 0x00fadf60;          // PlayerHealth::gInvincibleCheat (cheat code 2 toggles it at 0x5d355a)
const DWORD kGodByteOld = 0x00fadf63;       // the former option g_invincible (no writer on PC)
const DWORD kOneHitKill = 0x00e91ffd;       // EnemyHealth::m_oneHitKill, readers 0x62e39f / 0x633eb3 / 0x63bb68
const DWORD kOhkToggle = 0x0060f670;        // ENEMY_ToggleOneHitKill (cdecl, no args) - what cheat code 1 jumps to
const DWORD kEnemyHealth = 0x00e91ffc;      // gEnemyDrawHealthCheat, reader 0x638ed4 in EnemyProcessFunc 0x638d40
const DWORD kInstanceQuery = 0x005b36f0;    // INSTANCE_Query(inst, query) cdecl -> inst->[+0x11c](inst, query)
const DWORD kGainHealth = 0x006f4ef0;       // GainHealth / AddHealth cdecl (float amount, bool noClamp)
const DWORD kApplyCheatCode = 0x005d3520;   // DEBUG_ApplyCheatCode(code) cdecl
const DWORD kGameMode = 0x00e7f143;         // GameTracker+0xbb gameMode; GAMELOOP_Process skips the cheat path at 6 / 10
typedef void(__cdecl *VoidCdeclFn)();
typedef DWORD(__cdecl *InstanceQueryFn)(DWORD inst, int query);
typedef void(__cdecl *GainHealthFn)(float amount, int noClamp);
typedef void(__cdecl *ApplyCheatCodeFn)(int code);

bool g_godOk = false, g_godFullOk = false, g_ohkOk = false, g_enemyHpOk = false, g_infAmmoOk = false, g_fillOk = false,
     g_codeOk = false;
const char *g_godWhy = "not checked", *g_godFullWhy = "not checked", *g_ohkWhy = "not checked",
           *g_enemyHpWhy = "not checked", *g_infAmmoWhy = "not checked", *g_fillWhy = "not checked",
           *g_codeWhy = "not checked";
// 0.10.2 (F15, los7 2026-11-03: cheatMode bit 0 made Lara fly): cheat.godfull no longer touches cheatMode. It uses the
// player's own no-damage bit instead: [0xfada74] & 0x20000 (prototype ControlFlag bit "rlwinm 14,14", docs
// Abakus-Pruefung.md 18.7 / item 1) is tested before anything else in ApplyDamage 0x6f4f71 - the only function that
// lowers health (P+0x628 writes in 0x6e0000..0x780000: 0x6f4e6c / 0x7000d9 = refill, 0x6f4f2e = GainHealth, 0x6f4fd7 /
// 0x6f5004 inside ApplyDamage, 0x6f55cc = HealthInstantDeath) - and by all three of its callers (PlayerTakeDamage
// 0x6f5042 before the type 8 / 5 tests, DamageBypass 0x6f5140, 0x703008), so types 8 / 5 are blocked too. 0x721c8d
// skips ProcessHealth 0x6f5160 while it is set (the death state's own value 0x40020208 at 0x75a447 contains it). State
// entries overwrite the word (mov [0xfada74], imm), so the bit is OR-ed in again once per game frame (PadHook, before
// GAMELOOP_Process): a state entry and a hit in the same frame can still pass one hit. Instant deaths
// (HealthInstantDeath 0x6f55a0, callers 0x75afda / 0x75b099) test neither this bit nor cheatMode - they still kill.
const DWORD kPlayerModeFlags = 0x00fada74;  // player state-mode flags (written by every state entry)
const DWORD kNoDamageBit = 0x00020000;
volatile LONG g_godFull = 0;                // cheat.godfull on (game thread re-applies the bit)
bool g_noDamageOurs = false;                // game thread: the bit was absent and we set it ...
DWORD g_noDamageWord = 0;                   // ... and this is the word we left (an unchanged word = still ours)
volatile LONG g_infAmmo = 0;                // cheat.ammo on (re-applied every 30 game frames)
struct AmmoMark { DWORD t; bool ours; bool seen; };
AmmoMark g_ammoMarks[32];
int g_ammoMarkCount = 0;                    // game thread only
bool g_cheatRestored = false;               // [Cheats] Persist=1: State applied once in the first level

bool ByteAt(DWORD address) { BYTE b = 0; return ReadByte(address, &b) && b != 0; }
bool PutByte(DWORD address, BYTE value) {
    __try {
        *reinterpret_cast<volatile BYTE *>(address) = value;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// common gate of every cheat write: INI, pre-check, level
bool CheatGate(bool ok, const char *why, char *o, size_t n) {
    if (!g_cheatsEnabled) { Out(o, n, "cheats off ([Cheats] Enabled=0)"); return false; }
    if (!g_experimental) { Out(o, n, "experimental actions off ([Cheat] Experimental=0)"); return false; }
    if (!ok) { Out(o, n, "disabled: pre-check failed (%s)", why); return false; }
    if (!InLevel()) { Out(o, n, "needs a level (no player instance)"); return false; }
    return true;
}

void CheatPersistSave();   // below the runners

void ValCheatGod(char *o, size_t n) { Out(o, n, "%d", ByteAt(kGodByte) ? 1 : 0); }
bool RunCheatGod(const char *arg, char *o, size_t n) {
    if (!CheatGate(g_godOk, g_godWhy, o, n)) return false;
    bool on = BoolArg(arg, ByteAt(kGodByte));
    if (!PutByte(kGodByte, on ? 1 : 0)) { Out(o, n, "write to 0x%08lx failed", kGodByte); return false; }
    Log(1, "cheat: god mode %s (byte 0x%08lx = %d; ProcessHealth 0x6f5160 keeps the hit timer full)", on ? "ON" : "OFF",
        kGodByte, on ? 1 : 0);
    CheatPersistSave();
    Out(o, n, "cheat.god %d (gInvincibleCheat 0x%08lx; damage types 8 / 5 and instant deaths still pass - cheat.godfull "
        "adds the no-damage bit [0x%08lx] & 0x%05lx)", on ? 1 : 0, kGodByte, kPlayerModeFlags, kNoDamageBit);
    return true;
}

// 0.10.2: god mode + the player's no-damage bit (see kPlayerModeFlags). Game thread (QueueItem) and NoDamageTick.
void NoDamageApply() {
    DWORD word = 0;
    if (!ReadDword(kPlayerModeFlags, &word)) return;
    if (!(word & kNoDamageBit)) {
        *reinterpret_cast<volatile DWORD *>(kPlayerModeFlags) = word | kNoDamageBit;
        g_noDamageOurs = true;
    } else if (word != g_noDamageWord) {
        g_noDamageOurs = false;              // a state entry wrote the word with the bit itself (e.g. the death state)
    }
    g_noDamageWord = word | kNoDamageBit;
}
// game thread, once per game frame (PadHook)
void NoDamageTick() {
    if (!g_godFull || !g_godFullOk || !InLevel()) return;
    NoDamageApply();
}
void ValCheatGodFull(char *o, size_t n) { Out(o, n, "%d", g_godFull && ByteAt(kGodByte) ? 1 : 0); }
bool RunCheatGodFull(const char *arg, char *o, size_t n) {
    if (!CheatGate(g_godFullOk, g_godFullWhy, o, n)) return false;
    char cur[4];
    ValCheatGodFull(cur, sizeof(cur));
    bool on = BoolArg(arg, cur[0] == '1');
    const char *flight = "";
    if (on) {
        PutByte(kGodByte, 1);
        InterlockedExchange(&g_godFull, 1);
        NoDamageApply();
    } else {
        InterlockedExchange(&g_godFull, 0);
        PutByte(kGodByte, 0);
        DWORD word = 0;
        // clear the bit only while the word is still the one we left (no state entry since): else it is the game's
        if (g_noDamageOurs && ReadDword(kPlayerModeFlags, &word) && word == g_noDamageWord)
            *reinterpret_cast<volatile DWORD *>(kPlayerModeFlags) = word & ~kNoDamageBit;
        g_noDamageOurs = false;
        // F15: a flight left over (0.8 - 0.10.1 godfull set cheatMode bit 0 without message 12, or a [Cheats] Persist
        // restore of that) ends with the off - unless cheat.flight itself is on
        BYTE mode = 0;
        DWORD player = 0;
        if (ReadByte(kCheatMode, &mode) && (mode & 1) && !g_flight) {
            PutByte(kCheatMode, static_cast<BYTE>(mode & ~1));
            if (g_postOk && ReadDword(kPlayerPtr, &player) && player) Post(player, 12, 0);   // as cheat.flight 0
            flight = "; cheatMode bit 0 (flight) was set without cheat.flight - cleared, message 12 (0) posted";
        }
    }
    DWORD word = 0;
    ReadDword(kPlayerModeFlags, &word);
    Log(1, "cheat: god mode full %s (byte 0x%08lx = %d, mode flags [0x%08lx] = 0x%08lx%s)", on ? "ON" : "OFF", kGodByte,
        on ? 1 : 0, kPlayerModeFlags, word, flight);
    CheatPersistSave();
    Out(o, n, "cheat.godfull %d (gInvincibleCheat + no-damage bit [0x%08lx] & 0x%05lx per frame, no flight; instant "
        "deaths still kill%s)", on ? 1 : 0, kPlayerModeFlags, kNoDamageBit, flight);
    return true;
}

void ValCheatOhk(char *o, size_t n) { Out(o, n, "%d", ByteAt(kOneHitKill) ? 1 : 0); }
bool RunCheatOhk(const char *arg, char *o, size_t n) {
    if (!CheatGate(g_ohkOk, g_ohkWhy, o, n)) return false;
    bool now = ByteAt(kOneHitKill), on = BoolArg(arg, now);
    if (on != now) {
        __try {
            reinterpret_cast<VoidCdeclFn>(kOhkToggle)();       // the game's own toggle (cheat code 1)
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            InterlockedIncrement(&g_ownExceptions);
            Out(o, n, "exception in ENEMY_ToggleOneHitKill 0x%08lx", kOhkToggle);
            return false;
        }
    }
    bool after = ByteAt(kOneHitKill);
    Log(1, "cheat: one-hit kill %s (toggle 0x%08lx %s, byte 0x%08lx = %d)", after ? "ON" : "OFF", kOhkToggle,
        on != now ? "called" : "not needed", kOneHitKill, after ? 1 : 0);
    CheatPersistSave();
    Out(o, n, "cheat.onehitkill %d", after ? 1 : 0);
    return after == on;
}

void ValCheatEnemyHp(char *o, size_t n) { Out(o, n, "%d", ByteAt(kEnemyHealth) ? 1 : 0); }
bool RunCheatEnemyHp(const char *arg, char *o, size_t n) {
    if (!CheatGate(g_enemyHpOk, g_enemyHpWhy, o, n)) return false;
    bool on = BoolArg(arg, ByteAt(kEnemyHealth));
    if (!PutByte(kEnemyHealth, on ? 1 : 0)) { Out(o, n, "write to 0x%08lx failed", kEnemyHealth); return false; }
    Log(1, "cheat: show enemy health %s (byte 0x%08lx = %d)", on ? "ON" : "OFF", kEnemyHealth, on ? 1 : 0);
    CheatPersistSave();
    Out(o, n, "cheat.enemyhealth %d (EnemyProcessFunc prints the hit points through the game's debug text - may draw "
        "nothing in retail)", on ? 1 : 0);
    return true;
}

// infinite ammo: per weapon in the 15 slots, T = INSTANCE_Query(inst, 0x36) (the weapon tuning the reload 0x69c600 /
// 0x6e7ae0 reads; ResetAmmo 0x6f58d1 passes the slot instances to 0x6e7ae0), T+0x88 |= 0x80 -> reload without using
// the reserve. T is the weapon object's shared data (every instance of that weapon). Only bits TruMenu set are cleared.
int AmmoMarkFind(DWORD t) {
    for (int i = 0; i < g_ammoMarkCount; ++i) if (g_ammoMarks[i].t == t) return i;
    return -1;
}
// game thread: on = set the bit on every slot weapon (remember which ones we changed); off = clear ours.
// 0.8.1 (P00c: live "2 weapon(s), 0 bit(s) set" in hall02, run 223338): the reload 0x69c600 skips the reserve when
// T+0xa (ammo type) == 0xff OR T+0x88 & 0x80 (bytes 0x69c623..0x69c635, read again 2026-11-02) - a weapon with type
// 0xff (the pistols) or with the bit already set needs nothing, so "0 set" for the two pistol hands is the expected
// answer, not a failed write. detail (optional) names every slot weapon with type / flags and what happened.
int InfAmmoWalk(bool on, int *changed, char *detail = nullptr, size_t dn = 0) {
    *changed = 0;
    if (detail && dn) detail[0] = 0;
    size_t used = 0;
    auto note = [&](const char *fmt, ...) {
        if (!detail || used + 1 >= dn) return;
        va_list ap;
        va_start(ap, fmt);
        int w = _vsnprintf_s(detail + used, dn - used, _TRUNCATE, fmt, ap);
        va_end(ap);
        if (w > 0) used += static_cast<size_t>(w);
    };
    DWORD wm = WeaponManager();
    if (!wm) return -1;
    for (int i = 0; i < g_ammoMarkCount; ++i) g_ammoMarks[i].seen = false;
    int weapons = 0;
    for (int slot = 0; slot < 15; ++slot)
        for (int left = 0; left < 2; ++left) {
            DWORD inst = HandleInstance(wm + (left ? 0xc : 0x4) + 0x10 * slot);
            if (!inst) continue;
            char name[48];
            if (!InstanceObjectName(inst, name, sizeof(name))) strncpy_s(name, sizeof(name), "?", _TRUNCATE);
            DWORD t = 0;
            __try {
                t = reinterpret_cast<InstanceQueryFn>(kInstanceQuery)(inst, 0x36);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                InterlockedIncrement(&g_ownExceptions);
                t = 0;
            }
            BYTE flags = 0, type = 0;
            if (!t || !ReadByte(t + 0x88, &flags) || !ReadByte(t + 0xa, &type)) {
                note("%sslot %d%s %s: query 0x36 = 0x%08lx - no weapon data", used ? "; " : "", slot, left ? "L" : "",
                     name, t);
                continue;
            }
            ++weapons;
            int k = AmmoMarkFind(t);
            if (k >= 0) g_ammoMarks[k].seen = true;
            const char *what = "-";
            if (on) {
                if (type == 0xff) {
                    what = "ammo type 0xff = unlimited already (the reload never uses a reserve)";
                } else if (!(flags & 0x80)) {
                    bool put = PutByte(t + 0x88, static_cast<BYTE>(flags | 0x80));
                    if (put) ++*changed;
                    what = put ? "bit set" : "write failed";
                    if (k < 0 && g_ammoMarkCount < 32) { g_ammoMarks[g_ammoMarkCount++] = {t, true, true}; }
                    else if (k >= 0) g_ammoMarks[k].ours = true;
                } else {
                    what = k >= 0 && g_ammoMarks[k].ours ? "bit set by TruMenu (same weapon data as another slot)"
                                                         : "bit 0x80 set already (by the weapon itself)";
                    if (k < 0 && g_ammoMarkCount < 32) g_ammoMarks[g_ammoMarkCount++] = {t, false, true};
                }
            } else if (k >= 0 && g_ammoMarks[k].ours && (flags & 0x80)) {
                bool put = PutByte(t + 0x88, static_cast<BYTE>(flags & ~0x80));
                if (put) ++*changed;
                what = put ? "bit cleared" : "write failed";
                g_ammoMarks[k].ours = false;
            } else {
                what = "not ours - unchanged";
            }
            note("%sslot %d%s %s: T 0x%08lx type %d flags 0x%02x -> %s", used ? "; " : "", slot, left ? "L" : "", name, t,
                 type == 0xff ? -1 : static_cast<int>(type), flags, what);
        }
    // marks of weapon data no slot returned this time are dropped (never written again: the data may be gone)
    if (weapons) {
        int kept = 0;
        for (int i = 0; i < g_ammoMarkCount; ++i) if (g_ammoMarks[i].seen) g_ammoMarks[kept++] = g_ammoMarks[i];
        g_ammoMarkCount = kept;
    }
    if (!on && weapons) g_ammoMarkCount = 0;
    return weapons;
}
void ValCheatAmmo(char *o, size_t n) { Out(o, n, "%d", g_infAmmo ? 1 : 0); }
bool RunCheatAmmo(const char *arg, char *o, size_t n) {
    if (!CheatGate(g_infAmmoOk, g_infAmmoWhy, o, n)) return false;
    bool on = BoolArg(arg, g_infAmmo != 0);
    char detail[700];
    int changed = 0, weapons = InfAmmoWalk(on, &changed, detail, sizeof(detail));
    InterlockedExchange(&g_infAmmo, on ? 1 : 0);
    Log(1, "cheat: infinite ammo %s (%d slot weapon(s), %d weapon data bit(s) T+0x88 & 0x80 %s): %s", on ? "ON" : "OFF",
        weapons < 0 ? 0 : weapons, changed, on ? "set" : "cleared", weapons < 0 ? "no weapon manager (needs a level)" :
        detail[0] ? detail : "no weapon in the 15 slots");
    CheatPersistSave();
    Out(o, n, "cheat.ammo %d: %d weapon(s), %d bit(s) %s%s - %.400s", on ? 1 : 0, weapons < 0 ? 0 : weapons, changed,
        on ? "set" : "cleared", on ? " (new weapons are picked up every 30 game frames)" : "",
        detail[0] ? detail : "no slot weapon");
    return true;
}

// fill 'er up: the prototype's DEBUG_FillUpAll = RAZIEL_DebugHealthFillUp (GainHealth(max, 0) + UI fade group 1 - the
// PC GainHealth triggers the HUD itself, 0x6f4f5f) + playerInvDebugAmmoFillUp (here: ammo.fill, reserve = MaxAmmo)
bool RunCheatFill(const char *, char *o, size_t n) {
    if (!CheatGate(g_fillOk, g_fillWhy, o, n)) return false;
    if (!PlayerState()) { Out(o, n, "no playerstate [0x%08lx]", kPlayerState); return false; }
    float before = 0.0f, after = 0.0f, max = 0.0f;
    ReadFloats(PlayerState() + 0x628, &before, 1);
    __try {
        max = reinterpret_cast<MaxHealthFn>(kMaxHealth)();
        if (max > 0.0f) reinterpret_cast<GainHealthFn>(kGainHealth)(max, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
        Out(o, n, "exception in MaxHealth / GainHealth 0x%08lx", kGainHealth);
        return false;
    }
    ReadFloats(PlayerState() + 0x628, &after, 1);
    char ammo[200] = "ammo not verified - health only";
    if (g_ammoOk && g_maxAmmoOk) RunAmmoFill("", ammo, sizeof(ammo));
    Log(1, "cheat: fill 'er up - health %.1f -> %.1f (GainHealth 0x%08lx(%.1f, 0)); %s", before, after, kGainHealth, max, ammo);
    Out(o, n, "health %.1f -> %.1f (max %.1f); %s", before, after, max, ammo);
    return true;
}

// the cheat-code path: GAMELOOP_Process 0x5dfc5f calls 0x5d74d0 every frame unless gameMode is 6 / 10, which runs
// CheatCodes::Process and DEBUG_ApplyCheatCode(code). The function first plays the hit-reaction effect on the player
// (0x6a5dd0(player, 0x71, 0xff, 0, &player.pos) - [0xe7f094] is used without a null check), then toggles: 1 one-hit
// kill (jmp 0x60f670), 2 0xfadf60, 9 wireframe dword 0xe7edb0, 10 textureless 0xe7edac (no readers on PC), 11 0xe91ffc.
// TruMenu calls it on the game thread with the same guard (player set, gameMode not 6 / 10). Codes 3..8 / 65 / 66 are
// `ret` on PC and are refused.
const char *CheatCodeName(int code) {
    switch (code) {
        case 1: return "one-shot kill (toggle 0xe91ffd)";
        case 2: return "infinite health (toggle 0xfadf60)";
        case 9: return "wireframe (xor 0xe7edb0, no reader on PC)";
        case 10: return "textureless (xor 0xe7edac, no reader on PC)";
        case 11: return "draw enemy health (toggle 0xe91ffc)";
        default: return nullptr;
    }
}
void ValCheatCode(char *o, size_t n) {
    DWORD wire = 0, tex = 0;
    ReadDword(0x00e7edb0, &wire);
    ReadDword(0x00e7edac, &tex);
    Out(o, n, "codes 1 2 9 10 11; now: god %d, one-hit kill %d, enemy health %d, wireframe %lu, textureless %lu",
        ByteAt(kGodByte) ? 1 : 0, ByteAt(kOneHitKill) ? 1 : 0, ByteAt(kEnemyHealth) ? 1 : 0, wire & 1, tex & 1);
}
bool RunCheatCode(const char *arg, char *o, size_t n) {
    if (!CheatGate(g_codeOk, g_codeWhy, o, n)) return false;
    int code = arg && arg[0] ? atoi(arg) : 0;
    const char *name = CheatCodeName(code);
    if (!name) { Out(o, n, "usage: cheat.code <1|2|9|10|11> (3..8, 65, 66 are empty on PC)"); return false; }
    BYTE mode = 0;
    ReadByte(kGameMode, &mode);
    if (mode == 6 || mode == 10) { Out(o, n, "refused: gameMode [0x%08lx] = %u (the game skips its cheat path at 6 / 10)", kGameMode, mode); return false; }
    __try {
        reinterpret_cast<ApplyCheatCodeFn>(kApplyCheatCode)(code);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
        Out(o, n, "exception in DEBUG_ApplyCheatCode 0x%08lx(%d)", kApplyCheatCode, code);
        return false;
    }
    char now[200];
    ValCheatCode(now, sizeof(now));
    Log(1, "cheat: code %d %s applied via DEBUG_ApplyCheatCode 0x%08lx; %s", code, name, kApplyCheatCode, now);
    CheatPersistSave();
    Out(o, n, "DEBUG_ApplyCheatCode(%d) = %s done; %s", code, name, now);
    return true;
}

// the switchable / re-attach rows that can be kept with [Cheats] Persist=1
struct CheatRow { const char *id; int cat; void (*value)(char *, size_t); bool (*run)(const char *, char *, size_t); };
const CheatRow kCheatRows[] = {
    {"cheat.god", kCatSwitch, ValCheatGod, RunCheatGod},
    {"cheat.godfull", kCatSwitch, ValCheatGodFull, RunCheatGodFull},
    {"cheat.onehitkill", kCatSwitch, ValCheatOhk, RunCheatOhk},
    {"cheat.enemyhealth", kCatSwitch, ValCheatEnemyHp, RunCheatEnemyHp},
    {"cheat.ammo", kCatReattach, ValCheatAmmo, RunCheatAmmo},
};
// "rebuild from the prototype" rows: read-only in 0.8 (reader gone on PC; the prototype function that read the flag)
struct RebuildRow { const char *name, *proto, *pc; };
const RebuildRow kRebuildRows[] = {
    {"no fall damage", "g_playerNoFallDamage, read in PLAYER_CalculateFallingDamage", "PC fall-damage function not found"},
    {"enemies ignore Lara (no senses)", "g_enemyNoSense, read in EnemySensesControl::GetNearestEnemyCommon",
     "senses rebuilt in retail, hook point open"},
    {"no AI", "g_enemyNoAI, read in EnemyProcessFunc / ENEMY_UpdateSystem", "no such test in PC EnemyProcessFunc 0x638d40"},
    {"infinite grenades", "gInfiniteGrenades, read in ProcessCombat (refills item 3)", "rebuild with ammo.fill per frame"},
    {"enemies don't attack", "g_enemyNoAttack (11 readers, EnemyBehavior_*::Priority)", "partners not paired"},
    {"enemies: no attack damage", "g_enemyNoAttackDamage, ENEMY_PostDamageToTarget", "partners not paired"},
    {"enemies: no health", "g_enemyNoHealth, ENEMY_ApplyDamage", "partners not paired"},
    {"enemies don't move", "g_enemyNoMove, ENEMY_CanMove", "partners not paired"},
    {"enemies don't investigate", "g_enemyNoInvestigate, EnemyBehavior_Investigate::Priority", "partners not paired"},
    {"enemies: no barks", "g_enemyNoBarks, ENEMY_PlayBark / ENEMY_UpdateBark", "ENEMY_UpdateBark -> PC 0x616c20 (tier D)"},
};

void CheatPersistSave() {
    if (!g_cheatPersist || !g_iniPath[0]) return;
    char list[256] = "";
    size_t used = 0;
    for (const CheatRow &r : kCheatRows) {
        char v[8];
        r.value(v, sizeof(v));
        if (v[0] != '1') continue;
        int w = _snprintf_s(list + used, sizeof(list) - used, _TRUNCATE, "%s%s", used ? "," : "", r.id);
        if (w > 0) used += static_cast<size_t>(w);
    }
    strncpy_s(g_cheatState, sizeof(g_cheatState), list, _TRUNCATE);
    WritePrivateProfileStringA("Cheats", "State", list, g_iniPath);
}

// game thread, once per game frame (PadHook): [Cheats] Persist=1 restore in the first level; infinite ammo re-apply
void CheatsTick() {
    static int frames = 0;
    if (!g_cheatsEnabled || !g_experimental || !InLevel()) return;
    if (g_cheatPersist && !g_cheatRestored) {
        g_cheatRestored = true;
        char copy[sizeof(g_cheatState)];
        strncpy_s(copy, sizeof(copy), g_cheatState, _TRUNCATE);
        char *context = nullptr;
        for (char *id = strtok_s(copy, ", ", &context); id; id = strtok_s(nullptr, ", ", &context))
            for (const CheatRow &r : kCheatRows)
                if (!_stricmp(r.id, id)) {
                    char o[300];
                    bool ok = r.run("1", o, sizeof(o));
                    Log(1, "cheats: [Cheats] Persist=1 - %s on again: %s%s", id, ok ? "" : "err ", o);
                }
    }
    if (g_infAmmo && ++frames >= 30) {
        frames = 0;
        int changed = 0;
        InfAmmoWalk(true, &changed);
        if (changed) Log(2, "cheat: infinite ammo - %d new weapon data bit(s) set", changed);
    }
}

// cheat.list: every row with category and state / reason
void ValCheatList(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    auto put = [&](const char *fmt, const char *a, const char *b, const char *c) {
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, fmt, a, b, c);
        if (w > 0) used += static_cast<size_t>(w);
    };
    const char *why[] = {g_godOk ? "" : g_godWhy, g_godFullOk ? "" : g_godFullWhy, g_ohkOk ? "" : g_ohkWhy,
                         g_enemyHpOk ? "" : g_enemyHpWhy, g_infAmmoOk ? "" : g_infAmmoWhy};
    int i = 0;
    for (const CheatRow &r : kCheatRows) {
        char v[8];
        r.value(v, sizeof(v));
        put("%s%s [%s] = ", used ? "; " : "", r.id, kCheatCatNames[r.cat]);
        put("%s%s%s", v, why[i][0] ? " disabled: " : "", why[i]);
        ++i;
    }
    put("; cheat.fillup [%s]%s%s", kCheatCatNames[kCatReattach], g_fillOk ? "" : " disabled: ", g_fillOk ? "" : g_fillWhy);
    put("; cheat.code [%s]%s%s", kCheatCatNames[kCatCode], g_codeOk ? "" : " disabled: ", g_codeOk ? "" : g_codeWhy);
    for (const RebuildRow &r : kRebuildRows) put("; %s [%s] not built yet%s", r.name, kCheatCatNames[kCatRebuild], "");
}

// Start: byte pre-checks (all from work\asi\menu080\precheck_080.txt); a failed check disables that row with the reason
void CheatsCheck() {
    bool player = g_playerOk && g_healthOk;
    g_godOk = HexBytesAt(0x006f5163, "803d63dffa0000 7509 803d60dffa0000 7421") &&
              HexBytesAt(0x005d355a, "803d60dffa0000 0f94c0 a260dffa00");
    g_godWhy = g_godOk ? "ok" : "ProcessHealth 0x6f5163 / cheat code 2 0x5d355a bytes differ";
    // 0.10.2: the five tests of the no-damage bit [0xfada74] & 0x20000 (ApplyDamage, PlayerTakeDamage, DamageBypass,
    // 0x703008, the ProcessHealth skip 0x721c8d) and ApplyDamage's three calls (precheck_0102.txt)
    g_godFullOk = g_godOk && HexBytesAt(0x006f4f71, "f70574dafa0000000200 0f85a7000000") &&
                  HexBytesAt(0x006f5042, "f70574dafa0000000200 0f85eb000000 56 8b742410 83fe08") &&
                  HexBytesAt(0x006f5140, "f70574dafa0000000200 7512 d9442404 6a00 51 d91c24 e815feffff") &&
                  HexBytesAt(0x00703008, "f70574dafa0000000200 757c 6a01 51 d91c24 e8511fffff") &&
                  HexBytesAt(0x00721c8d, "f70574dafa0000000200 7509 56 e8c134fdff") &&
                  HexBytesAt(0x006f50aa, "e8c1feffff");
    g_godFullWhy = g_godFullOk ? "ok" : g_godOk ? "no-damage bit tests [0xfada74] & 0x20000 (0x6f4f71 / 0x6f5042 / "
                                                  "0x6f5140 / 0x703008 / 0x721c8d) differ" : g_godWhy;
    g_ohkOk = HexBytesAt(kOhkToggle, "803dfd1fe90000 0f94c0 a2fd1fe900 c3") && HexBytesAt(0x0062e39f, "803dfd1fe90000") &&
              HexBytesAt(0x00633eb3, "803dfd1fe90000") && HexBytesAt(0x0063bb68, "381dfd1fe900");
    g_ohkWhy = g_ohkOk ? "ok" : "ENEMY_ToggleOneHitKill 0x60f670 / its readers differ";
    g_enemyHpOk = HexBytesAt(0x00638ed4, "803dfc1fe90000 741e d986642c0000") &&
                  HexBytesAt(0x005d357a, "803dfc1fe90000 0f94c1 880dfc1fe900");
    g_enemyHpWhy = g_enemyHpOk ? "ok" : "EnemyProcessFunc reader 0x638ed4 / cheat code 11 differ";
    g_infAmmoOk = HexBytesAt(kInstanceQuery, "8b4c2404 8d8110010000 85c0 740a 8b811c010000 85c0 7503 33c0 c3") &&
                  HexBytesAt(0x0069c61b, "6a36 51 e8cd70f1ff 8a480a 83c408 80f9ff 7448 f6808800000080") &&
                  HexBytesAt(0x006e7afb, "6a36 51 e8edbbecff 0fbe480a") && HexBytesAt(0x006e7b10, "f6808800000080") &&
                  HexBytesAt(0x006f58d1, "e8fae0ebff 83c418 85c0 740a 56 50 e8fc21ffff");
    g_infAmmoWhy = !g_infAmmoOk ? "INSTANCE_Query 0x5b36f0 / reload 0x69c61b / 0x6e7afb / ResetAmmo 0x6f58d1 differ"
                 : !g_slotsOk ? "weapon slot code (0.4 check) failed" : "ok";
    g_infAmmoOk = g_infAmmoOk && g_slotsOk;
    g_fillOk = player && HexBytesAt(kGainHealth, "a158dbfa00 d9442404 d88028060000 0528060000 83ec08 807c241000") &&
               HexBytesAt(0x006f4f34, "6a01 51 8b0d58dbfa00 d98128060000 d91c24 6a2c e8b301eeff");
    g_fillWhy = g_fillOk ? "ok" : !player ? "player / health code (0.3 check) failed" : "GainHealth 0x6f4ef0 bytes differ";
    g_codeOk = g_playerOk && HexBytesAt(kApplyCheatCode, "a194f0e700 8d4820 51 6a00 68ff000000 6a71 50 e898280d00 8b442418 "
                                                         "83c0ff 83c414 83f840 7743 0fb690a8355d00 ff24958c355d00") &&
               HexBytesAt(0x005d3555, "e916c10300") && HexBytesAt(0x005d356a, "8335b0ede70001 c3 8335acede70001 c3") &&
               HexBytesAt(0x005d358c, "55355d00 5a355d00 8a355d00 6a355d00 72355d00 7a355d00 8a355d00") &&
               HexBytesAt(0x005d35a8, "00 01 02 06 06 06 06 06 03 04 05") &&
               HexBytesAt(0x005dfc49, "a043f1e700 3c06 0f841c030000 3c0a 0f8414030000 57 e86c78ffff") && g_godOk &&
               g_ohkOk && g_enemyHpOk;
    g_codeWhy = g_codeOk ? "ok" : "DEBUG_ApplyCheatCode 0x5d3520 / its tables / the game loop call 0x5dfc49 (or a cheat "
                                  "byte check) differ";
    // the bytes live in .bss: readable?
    BYTE b = 0;
    if (!ReadByte(kGodByte, &b) || !ReadByte(kGodByteOld, &b)) { g_godOk = g_godFullOk = g_codeOk = false; g_godWhy = g_godFullWhy = "0xfadf60 not readable"; }
    if (!ReadByte(kOneHitKill, &b) || !ReadByte(kEnemyHealth, &b)) { g_ohkOk = g_enemyHpOk = g_codeOk = false; g_ohkWhy = g_enemyHpWhy = "0xe91ffc not readable"; }
    Log(1, "0.8 cheats (enabled %d, persist %d): god %d, god full %d, one-hit kill %d, enemy health %d, infinite ammo %d, "
           "fill 'er up %d, cheat code %d", g_cheatsEnabled, g_cheatPersist, g_godOk, g_godFullOk, g_ohkOk, g_enemyHpOk,
        g_infAmmoOk, g_fillOk, g_codeOk);
    const struct { bool ok; const char *id, *why; } rows[] = {
        {g_godOk, "cheat.god", g_godWhy}, {g_godFullOk, "cheat.godfull", g_godFullWhy}, {g_ohkOk, "cheat.onehitkill", g_ohkWhy},
        {g_enemyHpOk, "cheat.enemyhealth", g_enemyHpWhy}, {g_infAmmoOk, "cheat.ammo", g_infAmmoWhy},
        {g_fillOk, "cheat.fillup", g_fillWhy}, {g_codeOk, "cheat.code", g_codeWhy}};
    for (const auto &r : rows) if (!r.ok) Log(0, "0.8 cheats: %s disabled - %s", r.id, r.why);
}

// ---- 0.12 Debug-Zeichnung (debug view stage S0, F28): the NavPower ("bfx") debug drawing compiled into tru.exe ----
// Workspace docs\Befund-Debug-Ansicht-0511.md 1.1 and docs\Befund-TruMenu-Debug-0511.md; every byte check below is
// pinned in work\asi\menu012\precheck_012.txt (tools/pe_bytes_check.py on the Steam exe: 33 / 33 ok). NavPower's frame
// draw (game frame 0x5da141 -> 0x489c60 -> jmp 0x42f900: the draw function of every component while
// [[0x8c0f0c]+0x10] == 1) tests one byte per BoolSetting; the bytes sit in .bss (0 in retail) and no instruction writes
// them (tools/pe_abs_uses.py: only the readers and the static initialisers' reads). TruMenu writes only these bytes and
// the layer mask dword [0x88e454] - game code stays unchanged. The lines reach the screen through CDCRenderer (vtable
// 0x845224, object [0x8c0f3c]) slot 0 0x48a500 -> DRAW_DrawLines 0x5bfcd0 (not yet seen live). Middleware text ends in
// the empty stub 0x6457a0, so only switches that draw lines are offered (islands, refcount, stats are text).
const DWORD kNavRenderer = 0x008c0f3c, kNavRendererVtbl = 0x00845224, kNavLineBuffer = 0x008c0f48,
            kNavSystem = 0x008c0f0c, kNavPlanner = 0x008bf310, kNavMask = 0x0088e454, kNavSettingVtbl = 0x00841144;
// nav.mask 1: the mask's value in the tru.exe file (.data, tools/pe_dis.py --dwords 0x88e454 = 0xffffffff) before the
// CDC init 0x48aa23 narrows it to (1 << n) | (1 << (n + 16)), n = [0xa03590]; the planner draw 0x418680 draws layer i
// (of 32) only when bit i is set, and nothing at all when the mask is 0
const DWORD kNavMaskAll = 0xffffffff;
struct NavCheckBytes { DWORD at; const char *hex; };
// kind 0 = drives the per-area loop of the planner draw (0x41869c / 0x4186a5), 1 = read inside the per-area draw
// 0x40c3a0 (draws only with a kind 0 switch on), 2 = its own draw path
struct NavSwitch {
    const char *name;            // the setting name = the string at nameAt in tru.exe
    DWORD byte, object, nameAt;  // switch byte (.bss); BoolSetting object (+0 vtable, +0xc name, +0x10 the byte)
    int kind;
    const char *draws;
    NavCheckBytes checks[4];     // its readers + the static initialiser that pairs name and byte (precheck 4 .. 10)
};
const NavSwitch kNavSwitches[] = {
    {"planner_areas", 0x008bf2e5, 0x008bf430, 0x00842600, 0, "navmesh areas, outline",
     {{0x0040c3a0, "8a15e5f28b00"}, {0x0083098e, "c7053cf48b0000268400 c70540f48b00e5f28b00"}, {0, nullptr}, {0, nullptr}}},
    {"planner_areas_solid", 0x008bf2e6, 0x008bf36c, 0x00842610, 0, "navmesh areas, filled (cost per frame unknown)",
     {{0x0040c3ba, "803de6f28b0000"}, {0x0040c68d, "803de6f28b0000"},
      {0x008309ce, "c70578f38b0010268400 c7057cf38b00e6f28b00"}, {0, nullptr}}},
    {"planner_connectivity", 0x008bf2e7, 0x008bf384, 0x00842624, 1, "a line from each area to each neighbour",
     {{0x0040c8bb, "803de7f28b0000 0f841d010000"}, {0x00830a0e, "c70590f38b0024268400 c70594f38b00e7f28b00"},
      {0, nullptr}, {0, nullptr}}},
    {"planner_area_normals", 0x008bf2ec, 0x008bf354, 0x0084263c, 1, "the normal of each area",
     {{0x0040c7c8, "803decf28b0000 0f84e6000000"}, {0x00830a4e, "c70560f38b003c268400 c70564f38b00ecf28b00"},
      {0, nullptr}, {0, nullptr}}},
    {"obstacles", 0x008bf308, 0x008bf33c, 0x008426cc, 2, "dynamic obstacles (list [0x8bf2f8])",
     {{0x00407690, "803d08f38b0000 7427"}, {0x00830c4e, "c70548f38b00cc268400 c7054cf38b0008f38b00"}, {0, nullptr},
      {0, nullptr}}},
    {"recent_navprobes", 0x008bf309, 0x008bf4b0, 0x008426d8, 2, "the latest navmesh probes (the probe query 0x420580 "
     "records each probe while on)",
     {{0x00420583, "381d09f38b00"}, {0x004205bf, "803d09f38b0000"},
      {0x00830c8e, "c705bcf48b00d8268400 c705c0f48b0009f38b00"}, {0, nullptr}}},
    {"draw_mover3d_path", 0x008bf006, 0x008bf08c, 0x0084152c, 2, "the path of each Mover3D (flyers, list [0x8bf00c])",
     {{0x0040432d, "803d06f08b0000 7437"}, {0x00405da5, "e806e1ffff"}, {0x0040617b, "68805d4000"},
      {0x0083031e, "c70598f08b002c158400 c7059cf08b0006f08b00"}}},
};
const int kNavCount = static_cast<int>(sizeof(kNavSwitches) / sizeof(kNavSwitches[0]));
bool g_navCoreOk = false, g_navMaskOk = false, g_navAreaOk = false, g_navSwOk[kNavCount] = {};
const char *g_navCoreWhy = "not checked", *g_navMaskWhy = "not checked", *g_navSwWhy[kNavCount] = {};
BYTE g_navOrig[kNavCount] = {};              // the byte before TruMenu's first write (nav.off writes it back)
bool g_navSaved[kNavCount] = {};
DWORD g_navMaskPrev = 0;                     // nav.mask 1: the mask before (nav.mask 0 / nav.off restore it)
bool g_navMaskSet = false;
bool g_navAutoDone = false, g_navAutoWaitLogged = false;   // [Debug] NavDraw / NavMask: applied once

const char *ShotSource(const char *item);    // 0.10.5, below: "ring", "TruLink" or the given name
void DvPersistNav();                         // 0.14, below: [Debug] Persist=1 writes NavDraw

// switch index of the first word of text ("" / unknown = -1)
int NavFind(const char *text) {
    if (!text) return -1;
    while (*text == ' ') ++text;
    size_t len = 0;
    while (text[len] && text[len] != ' ') ++len;
    for (int i = 0; i < kNavCount; ++i)
        if (strlen(kNavSwitches[i].name) == len && !_strnicmp(kNavSwitches[i].name, text, len)) return i;
    return -1;
}
bool NavByteOn(int i) { return ByteAt(kNavSwitches[i].byte); }
bool NavPutDword(DWORD address, DWORD value) {   // .data dword (writable section, no VirtualProtect)
    __try {
        *reinterpret_cast<volatile DWORD *>(address) = value;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// the planner layers that hold something, tested as 0x4186bb .. 0x4186cd do (bit i of the mask, [planner + 4 * i] != 0,
// [layer + 8] != 0); returns the bit set, the text lists the layer numbers
DWORD NavLayers(char *o, size_t n) {
    o[0] = 0;
    DWORD planner = 0, bits = 0;
    if (!ReadDword(kNavPlanner, &planner) || !planner) { Out(o, n, "no planner ([0x%08lx] = 0)", kNavPlanner); return 0; }
    size_t used = 0;
    for (DWORD i = 0; i < 32; ++i) {
        DWORD layer = 0, graphs = 0;
        if (!ReadDword(planner + 4 * i, &layer) || !layer || !ReadDword(layer + 8, &graphs) || !graphs) continue;
        bits |= 1ul << i;
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%lu", used ? " " : "", i);
        if (w > 0) used += static_cast<size_t>(w);
    }
    if (!bits) Out(o, n, "none");
    return bits;
}
// NavPower system state [[0x8c0f0c]+0x10] (1 = started: the frame loop runs the draw functions), -1 = not readable
long NavState() {
    DWORD sys = 0, state = 0;
    if (!ReadDword(kNavSystem, &sys) || !sys || !ReadDword(sys + 0x10, &state)) return -1;
    return static_cast<long>(state);
}

// the world guard of every write: a loaded level (player, main state 1, no level change pending - never while
// loading, as instance.spawn) and the draw bridge set up (CDCRenderer, NavPower line buffer)
bool NavWorldReady(char *why, size_t n) {
    DWORD state = 0, renderer = 0, vtable = 0, buffer = 0;
    if (!InLevel()) { Out(why, n, "needs a level (no player instance)"); return false; }
    if (!g_mainStateOk) { Out(why, n, "main state code (0.3 check) failed - loading cannot be told apart"); return false; }
    ReadDword(kMainState, &state);
    if (state != 1) { Out(why, n, "in a loaded level only (main state %lu, needs 1)", state); return false; }
    if (LevelChangePending(why, n)) return false;
    if (!ReadDword(kNavRenderer, &renderer) || !renderer || !ReadDword(renderer, &vtable) || vtable != kNavRendererVtbl) {
        Out(why, n, "CDCRenderer [0x%08lx] = 0x%08lx, vtable 0x%08lx (want 0x%08lx) - the draw bridge is not set up",
            kNavRenderer, renderer, vtable, kNavRendererVtbl);
        return false;
    }
    if (!ReadDword(kNavLineBuffer, &buffer) || !buffer) {
        Out(why, n, "NavPower line buffer [0x%08lx] = 0 - NavPower not started", kNavLineBuffer);
        return false;
    }
    return true;
}

// the setting object still pairs this name and this byte (its static initialiser ran, nothing moved it)
bool NavObjectOk(int i, char *why, size_t n) {
    const NavSwitch &s = kNavSwitches[i];
    DWORD vtable = 0, name = 0, ptr = 0;
    char text[48];
    ReadDword(s.object, &vtable);
    ReadDword(s.object + 0xc, &name);
    ReadDword(s.object + 0x10, &ptr);
    ReadString(s.nameAt, text, sizeof(text));
    if (vtable == kNavSettingVtbl && name == s.nameAt && ptr == s.byte && strcmp(text, s.name) == 0) return true;
    Out(why, n, "setting object 0x%08lx: vtable 0x%08lx, name 0x%08lx '%s', byte 0x%08lx (want 0x%08lx, 0x%08lx '%s', "
        "0x%08lx)", s.object, vtable, name, text, ptr, kNavSettingVtbl, s.nameAt, s.name, s.byte);
    return false;
}

// common gate of nav.draw / nav.mask / nav.off (as CheatGate: INI, experimental, pre-check, level)
bool NavGate(char *o, size_t n) {
    if (!g_debugEnabled) { Out(o, n, "debug drawing off ([Debug] Enabled=0)"); return false; }
    if (!g_experimental) { Out(o, n, "experimental actions off ([Cheat] Experimental=0)"); return false; }
    if (!g_navCoreOk) { Out(o, n, "disabled: pre-check failed (%s)", g_navCoreWhy); return false; }
    char why[200];
    if (!NavWorldReady(why, sizeof(why))) { Out(o, n, "refused: %s", why); return false; }
    return true;
}

// switch i to on / off (gate passed); one TruMenu.log line "nav.draw <name> <0|1> ..." per call
bool NavSet(int i, bool on, const char *src, char *o, size_t n) {
    const NavSwitch &s = kNavSwitches[i];
    char why[240];
    if (!g_navSwOk[i]) {
        Out(o, n, "disabled: pre-check failed (%s)", g_navSwWhy[i]);
        Log(1, "nav.draw %s %d refused - %s (src=%s)", s.name, on ? 1 : 0, o, src);
        return false;
    }
    if (!NavObjectOk(i, why, sizeof(why))) {
        Out(o, n, "refused: %s", why);
        Log(1, "nav.draw %s %d refused - %s (src=%s)", s.name, on ? 1 : 0, o, src);
        return false;
    }
    BYTE before = 0, after = 0;
    bool read = ReadByte(s.byte, &before);
    if (read && !g_navSaved[i]) { g_navOrig[i] = before; g_navSaved[i] = true; }
    if (!read || !PutByte(s.byte, on ? 1 : 0) || !ReadByte(s.byte, &after)) {
        Out(o, n, "write to 0x%08lx failed", s.byte);
        Log(1, "nav.draw %s %d failed - %s (src=%s)", s.name, on ? 1 : 0, o, src);
        return false;
    }
    DWORD mask = 0;
    ReadDword(kNavMask, &mask);
    char layers[120];
    DWORD bits = NavLayers(layers, sizeof(layers));
    const char *note = "";
    if (on && s.kind == 1 && !NavByteOn(0) && !NavByteOn(1))
        note = " - draws only together with planner_areas / planner_areas_solid (the area loop of 0x418680 runs only then)";
    else if (on && s.kind <= 1 && !mask)
        note = " - layer mask [0x88e454] = 0: the planner draws nothing (nav.mask 1)";
    else if (on && s.kind <= 1 && bits && !(mask & bits))
        note = " - no layer that holds a navgraph is in the layer mask (nav.mask 1)";
    Log(1, "nav.draw %s %d (byte 0x%08lx %u -> %u; %s; mask [0x%08lx] = 0x%08lx, layers %s (0x%08lx), NavPower state %ld; "
           "src=%s)%s", s.name, on ? 1 : 0, s.byte, before, after, s.draws, kNavMask, mask, layers, bits, NavState(), src,
        note);
    Out(o, n, "nav.draw %s %d (%s; byte 0x%08lx %u -> %u, mask 0x%08lx, layers %s)%s", s.name, on ? 1 : 0, s.draws, s.byte,
        before, after, mask, layers, note);
    return after == (on ? 1 : 0);
}

// nav.mask on / off (gate passed): on = kNavMaskAll (the value before is kept), off = the value before - only when the
// mask still holds TruMenu's value (else the game wrote it meanwhile and it stays)
bool NavMaskApply(bool on, const char *src, char *o, size_t n) {
    if (!g_navMaskOk) {
        Out(o, n, "disabled: pre-check failed (%s)", g_navMaskWhy);
        Log(1, "nav.mask %d refused - %s (src=%s)", on ? 1 : 0, o, src);
        return false;
    }
    DWORD before = 0, after = 0;
    if (!ReadDword(kNavMask, &before)) { Out(o, n, "mask 0x%08lx not readable", kNavMask); return false; }
    const char *what = "";
    bool ok = true;
    if (on) {
        if (!g_navMaskSet) g_navMaskPrev = before;
        ok = NavPutDword(kNavMask, kNavMaskAll);
        if (ok) g_navMaskSet = true;
        what = ok ? "every layer" : "write failed";
    } else if (!g_navMaskSet) {
        what = "TruMenu has not changed it - left as is";
    } else if (before != kNavMaskAll) {
        what = "changed by the game since nav.mask 1 - left as is";
        g_navMaskSet = false;
    } else {
        ok = NavPutDword(kNavMask, g_navMaskPrev);
        what = ok ? "the value before" : "write failed";
        if (ok) g_navMaskSet = false;
    }
    ReadDword(kNavMask, &after);
    char layers[120];
    DWORD bits = NavLayers(layers, sizeof(layers));
    Log(1, "nav.mask %d ([0x%08lx] 0x%08lx -> 0x%08lx: %s; layers %s (0x%08lx), NavPower state %ld; src=%s)", on ? 1 : 0,
        kNavMask, before, after, what, layers, bits, NavState(), src);
    Out(o, n, "nav.mask %d (0x%08lx -> 0x%08lx: %s; layers %s)", on ? 1 : 0, before, after, what, layers);
    return ok;
}

void ValNavDraw(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    for (int i = 0; i < kNavCount; ++i) {
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s %d%s%s", i ? ", " : "", kNavSwitches[i].name,
                            NavByteOn(i) ? 1 : 0, g_navSwOk[i] ? "" : " (disabled: ", g_navSwOk[i] ? "" : g_navSwWhy[i]);
        if (w > 0) used += static_cast<size_t>(w);
        if (!g_navSwOk[i] && used + 1 < n) {
            w = _snprintf_s(o + used, n - used, _TRUNCATE, ")");
            if (w > 0) used += static_cast<size_t>(w);
        }
    }
}
bool RunNavDraw(const char *arg, char *o, size_t n) {
    const char *src = ShotSource("menu");
    char buf[96];
    strncpy_s(buf, sizeof(buf), arg ? arg : "", _TRUNCATE);
    char *context = nullptr;
    char *name = strtok_s(buf, " ", &context);
    char *value = name ? strtok_s(nullptr, " ", &context) : nullptr;
    if (!name) {
        char now[600];
        ValNavDraw(now, sizeof(now));
        Out(o, n, "usage: nav.draw <switch> [0|1] (no 0 / 1 = flip); now: %s", now);
        return false;
    }
    int i = NavFind(name);
    if (i < 0) {
        Out(o, n, "unknown switch '%s' (planner_areas, planner_areas_solid, planner_connectivity, planner_area_normals, "
            "obstacles, recent_navprobes, draw_mover3d_path)", name);
        return false;
    }
    bool on = BoolArg(value ? value : "", NavByteOn(i));
    if (!NavGate(o, n)) {
        Log(1, "nav.draw %s %d refused - %s (src=%s)", kNavSwitches[i].name, on ? 1 : 0, o, src);
        return false;
    }
    bool ok = NavSet(i, on, src, o, n);
    if (ok) DvPersistNav();                  // 0.14 [Debug] Persist=1: NavDraw = the switches on now
    return ok;
}

void ValNavMask(char *o, size_t n) {
    DWORD mask = 0;
    bool read = ReadDword(kNavMask, &mask);
    Out(o, n, "%d (layer mask [0x%08lx] = %s0x%08lx, %s)", g_navMaskSet ? 1 : 0, kNavMask, read ? "" : "unreadable ", mask,
        g_navMaskSet ? "set by nav.mask 1" : "the game's");
}
bool RunNavMask(const char *arg, char *o, size_t n) {
    const char *src = ShotSource("menu");
    bool on = BoolArg(arg, g_navMaskSet);
    if (!NavGate(o, n)) {
        Log(1, "nav.mask %d refused - %s (src=%s)", on ? 1 : 0, o, src);
        return false;
    }
    return NavMaskApply(on, src, o, n);
}

// nav.off: every switch TruMenu wrote back to the value before its first write, then the mask
bool RunNavOff(const char *, char *o, size_t n) {
    const char *src = ShotSource("menu");
    if (!NavGate(o, n)) {
        Log(1, "nav.off refused - %s (src=%s)", o, src);
        return false;
    }
    int restored = 0, failed = 0;
    char names[200] = "";
    size_t used = 0;
    for (int i = 0; i < kNavCount; ++i) {
        if (!g_navSaved[i]) continue;
        BYTE now = 0;
        if (ReadByte(kNavSwitches[i].byte, &now) && now != g_navOrig[i]) {
            if (PutByte(kNavSwitches[i].byte, g_navOrig[i])) {
                ++restored;
                int w = _snprintf_s(names + used, sizeof(names) - used, _TRUNCATE, "%s%s", used ? " " : "",
                                    kNavSwitches[i].name);
                if (w > 0) used += static_cast<size_t>(w);
            } else {
                ++failed;
            }
        }
        g_navSaved[i] = false;
    }
    char mask[220] = "mask: not changed by TruMenu";
    if (g_navMaskSet && !NavMaskApply(false, src, mask, sizeof(mask))) ++failed;
    Log(1, "nav.off: %d switch(es) back to the value before (%s), %d failed; %s (src=%s)", restored,
        restored ? names : "-", failed, mask, src);
    DvPersistNav();                          // 0.14 [Debug] Persist=1
    Out(o, n, "nav.off: %d switch(es) back (%s), %d failed; %s", restored, restored ? names : "-", failed, mask);
    return failed == 0;
}

// nav.status: read-only, any time
void ValNavStatus(char *o, size_t n) {
    DWORD renderer = 0, vtable = 0, buffer = 0, mask = 0;
    ReadDword(kNavRenderer, &renderer);
    if (renderer) ReadDword(renderer, &vtable);
    ReadDword(kNavLineBuffer, &buffer);
    ReadDword(kNavMask, &mask);
    char layers[120], draws[600];
    DWORD bits = NavLayers(layers, sizeof(layers));
    ValNavDraw(draws, sizeof(draws));
    Out(o, n, "[Debug] Enabled %d; draw path %s, layer mask code %s; CDCRenderer [0x%08lx] 0x%08lx (vtable 0x%08lx%s), "
        "line buffer [0x%08lx] 0x%08lx, NavPower state %ld; mask 0x%08lx (%s), layers %s (0x%08lx); %s", g_debugEnabled,
        g_navCoreWhy, g_navMaskWhy, kNavRenderer, renderer, vtable, vtable == kNavRendererVtbl ? " ok" : " - not set up",
        kNavLineBuffer, buffer, NavState(), mask, g_navMaskSet ? "set by nav.mask 1" : "the game's", layers, bits, draws);
}

// ring: why a nav.* entry is greyed out right now ("" = usable); arg = the entry's argument (nav.draw <switch>)
const char *NavRadWhy(const char *id, const char *arg) {
    if (!_stricmp(id, "nav.status")) return "";
    if (!g_debugEnabled) return "debug drawing off ([Debug] Enabled=0)";
    if (!g_experimental) return "experimental off ([Cheat] Experimental=0)";
    if (!g_navCoreOk) return g_navCoreWhy;
    if (!_stricmp(id, "nav.mask") && !g_navMaskOk) return g_navMaskWhy;
    if (!_stricmp(id, "nav.draw")) {
        int i = NavFind(arg);
        if (i < 0) return "unknown NavPower switch";
        if (!g_navSwOk[i]) return g_navSwWhy[i];
    }
    if (!InLevel()) return "needs a level";
    DWORD state = 0;
    if (g_mainStateOk && ReadDword(kMainState, &state) && state != 1) return "not while loading (main state is not 1)";
    return "";
}

// load: the byte checks of precheck_012.txt; a failed check disables that switch (or all) with the reason
void NavCheck() {
    bool renderer = HexBytesAt(0x0048a95f, "c70024528400 a33c0f8c00") && HexBytesAt(kNavRendererVtbl, "00a54800");
    bool frame = HexBytesAt(0x005da141, "e81afbeaff") && HexBytesAt(0x00489c68, "e9935cfaff") &&
                 HexBytesAt(0x0042f98a, "a10c0f8c00 83781001");
    bool planner = HexBytesAt(0x004211ad, "6870884100") &&
                   HexBytesAt(0x00418870, "8b0d10f38b00 e805feffff e810eefeff 803d09f38b0000 7428");
    g_navCoreOk = renderer && frame && planner;
    g_navCoreWhy = !renderer ? "CDCRenderer creation 0x48a95f / vtable slot 0 0x845224 differ"
                 : !frame ? "NavPower frame draw 0x5da141 / 0x489c68 / component loop 0x42f98a differ"
                 : !planner ? "planner draw registration 0x4211ad / frame draw 0x418870 differ" : "ok";
    bool reads = HexBytesAt(0x0041868f, "833d54e4880000 0f84b8000000 803de5f28b0000 7509 803de6f28b0000 7472") &&
                 HexBytesAt(0x004186bb, "8b0d54e48800 85c1 7416") && HexBytesAt(0x004186d3, "e878e0ffff") &&
                 HexBytesAt(0x004186f4, "8b3d54e48800") && HexBytesAt(0x0041873e, "a154e48800");
    bool writer = HexBytesAt(0x0048aa23, "891554e48800");
    DWORD mask = 0;
    bool maskRead = ReadDword(kNavMask, &mask);
    g_navMaskOk = g_navCoreOk && reads && writer && maskRead;
    g_navMaskWhy = !g_navCoreOk ? g_navCoreWhy : !reads ? "planner draw 0x418680 mask / area tests differ"
                 : !writer ? "mask writer 0x48aa23 differs" : !maskRead ? "mask 0x88e454 not readable" : "ok";
    g_navAreaOk = HexBytesAt(0x004167a4, "e8a7caffff") && HexBytesAt(0x004132d2, "e8c990ffff");
    int ok = 0;
    for (int i = 0; i < kNavCount; ++i) {
        const NavSwitch &s = kNavSwitches[i];
        bool bytes = true;
        for (const NavCheckBytes &c : s.checks)
            if (c.hex && !HexBytesAt(c.at, c.hex)) bytes = false;
        BYTE v = 0;
        bool readable = ReadByte(s.byte, &v);
        bool chain = s.kind == 2 || (g_navMaskOk && g_navAreaOk);
        g_navSwOk[i] = g_navCoreOk && bytes && readable && chain;
        g_navSwWhy[i] = !g_navCoreOk ? g_navCoreWhy : !bytes ? "its reader / initialiser bytes differ (precheck_012.txt)"
                      : !readable ? "switch byte not readable"
                      : !chain ? (g_navMaskOk ? "area chain 0x4167a4 / 0x4132d2 differs" : g_navMaskWhy) : "ok";
        if (g_navSwOk[i]) ++ok;
        else Log(0, "0.12 debug drawing: nav.draw %s disabled - %s", s.name, g_navSwWhy[i]);
    }
    if (!g_navMaskOk) Log(0, "0.12 debug drawing: nav.mask disabled - %s", g_navMaskWhy);
    char auto_[300];
    _snprintf_s(auto_, sizeof(auto_), _TRUNCATE, "%s", g_navAuto[0] ? g_navAuto : "-");
    Log(1, "0.12 debug drawing: [Debug] Enabled %d (NavDraw %s, NavMask %d), draw path %s, layer mask %s (0x%08lx now), "
           "%d / %d switches ok", g_debugEnabled, auto_, g_navAutoMask, g_navCoreWhy, g_navMaskWhy, mask, ok, kNavCount);
}

// game thread, once per game frame: [Debug] NavDraw / NavMask applied once in the first loaded level
void NavTick() {
    if (g_navAutoDone || !g_debugEnabled || (!g_navAuto[0] && !g_navAutoMask)) return;
    char why[240];
    if (!g_experimental || !g_navCoreOk) {
        g_navAutoDone = true;
        Log(0, "nav: [Debug] NavDraw / NavMask not applied - %s",
            !g_experimental ? "experimental actions off ([Cheat] Experimental=0)" : g_navCoreWhy);
        return;
    }
    if (!NavWorldReady(why, sizeof(why))) {
        if (InLevel() && !g_navAutoWaitLogged) {
            g_navAutoWaitLogged = true;
            Log(1, "nav: [Debug] NavDraw / NavMask wait - %s", why);
        }
        return;
    }
    g_navAutoDone = true;
    char copy[sizeof(g_navAuto)], answer[600];
    strncpy_s(copy, sizeof(copy), g_navAuto, _TRUNCATE);
    char *context = nullptr;
    int done = 0, failed = 0;
    for (char *name = strtok_s(copy, ", ", &context); name; name = strtok_s(nullptr, ", ", &context)) {
        int i = NavFind(name);
        if (i < 0) {
            ++failed;
            Log(0, "nav: [Debug] NavDraw: unknown switch '%s'", name);
            continue;
        }
        if (NavSet(i, true, "[Debug] NavDraw", answer, sizeof(answer))) ++done;
        else ++failed;
    }
    if (g_navAutoMask) {
        if (NavMaskApply(true, "[Debug] NavMask", answer, sizeof(answer))) ++done;
        else ++failed;
    }
    Log(1, "nav: [Debug] NavDraw / NavMask applied in the first loaded level: %d ok, %d failed", done, failed);
}

// ---- 0.13 Thrall-Labels (debug view stage S1, F28): a text label at each thrall / enemy instance near Lara ----
// Workspace docs\Befund-Thrall-Labels-0511.md; every byte check is pinned in work\asi\menu0130\precheck_013.txt
// (tools/pe_bytes_check.py on the Steam exe: 20 / 20 ok). Read-only: nothing is written into game memory, no game
// function is called. Drawn into ImGui's foreground draw list at Present, only in a loaded level (player instance, main
// state 1, no level change pending - the guards of nav.draw), with fixed static buffers (no allocation per frame).
// Projection = the game's own text-at-an-instance path (EnemyProcessFunc's health text 0x6224e0): matrix = the address
// the getter 0x5e7890 returns (0xe804a0), projected like TRANS_RotTransPersVectorf 0x49f630 (x' = row-0 dot p + m[12],
// ...; screen x = x' / z' * f + 256.0, y = y' / z' * f + 224.0, f = [0x8906d0]), drawn when 16.0 < z' ([0x8451e4],
// 0x62257b). 0xe804a0 is written once per game frame by the camera update 0x5f3df0 (called at 0x5d46a9 right after the
// instance walk): the camera's world -> camera matrix, column x scaled by (4 / 3) / aspect ([[0xad75e4]+0x170] / 10000,
// 0x5c59f0), column y by 448 / 384 (0x5e7b30); f = 192 / tan(fov / 2) (0x5f3ef6 -> 0x49f610). So the game's text space
// is 512 x 448 with a vertical field of view - mapped onto the back buffer with draw.scale (default 512 448), the same
// scale draw.markup uses. Live check: the magenta cross ([Debug] LabelCross) must sit on Lara's feet / origin, and with
// cheat.enemyhealth the game's own health number must sit at the label's anchor dot.
// Health = EnemyProcessFunc 0x638d40's value: brain = [[inst+0x2d0]]+0x2ec (0x638d59), hit points brain+0x2c64
// (printed at 0x638edd) - read only for names containing "thrall" (the DLC thralls; enemy type not proven per
// instance in code). A state-chart state id is NOT shown: the only chart machine constructor tru+0x3873c0 has one
// caller (tru+0x2eff9a, the player's machines playerstate +0xf10..), the thralls' chart runs elsewhere (unknown).
// TruShadowCombat 0.5.3: TscTargeterSnapshot(9, &snapshot, size) (version 1, size checked) - bucket / rejected (with
// the last WHY result) / target of targeter 9, the player's hit list, the last condition 2011. Without the export the
// labels show TruMenu's own data only.
const DWORD kLblMatrix = 0x00e804a0, kLblAspect = 0x00ad75e4;
bool g_lblOk = false;
bool g_lblProjOk = false;                    // 0.14: the text / camera update / projection checks alone (debug view)
const char *g_lblWhy = "not checked";
volatile LONG g_lblOn = 0;                   // dbg.labels
int g_lblShown = 0, g_lblInRadius = 0, g_lblThralls = 0;     // last frame
char g_lblState[160] = "off";                // last frame: why nothing / what was drawn (dbg.labels value)
DWORD g_lblLogTick = 0;                      // calibration log line, every 10 s while on
signed char g_lblNameKind[4096];             // per object id: 0 unknown, 1 thrall, 2 other match, 3 no label

// TruShadowCombat 0.5.3 export (layout = TscTargeterSnapshotV1 in TruShadowCombat.cpp, version 1)
struct LblTscEntry { const void *instance; DWORD where, why, whyTick, marker; };
struct LblTscSnap {
    DWORD size, version, tick, built;
    const void *targeter, *target;
    DWORD node, flags, candidates, groups, bucket[4], rejected;
    DWORD count, truncated;
    LblTscEntry entries[24];
    const void *hitList[8];
    DWORD c2011Calls, c2011Tick, c2011Path, c2011Result;
    LONG c2011Query;
    const void *c2011Target;
};
static_assert(sizeof(LblTscEntry) == 20 && sizeof(LblTscSnap) == 604, "TscTargeterSnapshot v1 layout (TruShadowCombat)");
typedef DWORD(__cdecl *TscSnapFn)(DWORD tuIndex, void *out, DWORD outSize);
TscSnapFn g_tscSnap = nullptr;
DWORD g_tscLookTick = 0;
const char *g_tscState = "not looked up";
LblTscSnap g_lblSnap;
bool g_lblSnapOk = false;

// load: the byte checks of precheck_013.txt
void LabelCheck() {
    bool text = HexBytesAt(0x005e7890, "b8a004e800 c3") && HexBytesAt(0x006224ed, "e89e53fcff 50 e828d1e7ff") &&
                HexBytesAt(0x0062257b, "d905e4518400 d85c2420");
    bool update = HexBytesAt(0x005d46a9, "e842f70100") &&
                  HexBytesAt(0x005f3e25, "50 b9a004e800 e8e0dfe3ff 68a004e800 e8f63cffff") &&
                  HexBytesAt(0x005e7b30, "56 8b742408 d906 dd05905a8400 dcc9 dd05d8548400") &&
                  HexBytesAt(0x005e7b5d, "d94604 dd05d0548400 dcc9 dd05f0598500") && HexBytesAt(0x005e7b87, "e864defdff") &&
                  HexBytesAt(0x005c59f1, "a1e475ad00 8b8870010000 db8070010000") &&
                  HexBytesAt(0x005f3ef6, "d91d98c28a00 e8cf34ffff d90598c28a00 51 dc3de8598500") &&
                  HexBytesAt(0x005f3f19, "e8f2b6eaff") && HexBytesAt(0x0049f610, "d9442404 d91dd0068900 c3");
    bool project = HexBytesAt(0x0049f6f8, "d905d0068900") && HexBytesAt(0x0049f702, "dc05003a8400") &&
                   HexBytesAt(0x0049f713, "dc05c8548400") && HexBytesAt(0x00843a00, "0000000000007040") &&
                   HexBytesAt(0x008454c8, "0000000000006c40") && HexBytesAt(0x008451e4, "00008041");
    bool health = HexBytesAt(0x00638d59, "8b87d0020000 85c0 7504 33f6 eb08 8b00 8bb0ec020000") &&
                  HexBytesAt(0x00638edd, "d986642c0000");
    g_lblOk = text && update && project && health && g_instOk && g_playerOk && g_mainStateOk;
    g_lblProjOk = text && update && project;      // 0.14 debug view: the same projection, no health chain needed
    g_lblWhy = !text ? "game instance text 0x6224e0 (matrix getter 0x5e7890, z test 0x62257b) differs"
             : !update ? "camera update 0x5f3df0 / 0x5e7b30 / focal 0x49f610 differs"
             : !project ? "projection 0x49f630 constants differ"
             : !health ? "EnemyProcessFunc health chain 0x638d59 / 0x638edd differs"
             : !g_instOk ? "instance list (0.3 check) failed"
             : !g_playerOk ? "player pointer check failed" : !g_mainStateOk ? "main state check failed" : "ok";
    memset(g_lblNameKind, 0, sizeof(g_lblNameKind));
    if (g_lblAtStart && g_debugEnabled && g_lblOk) InterlockedExchange(&g_lblOn, 1);
    Log(g_lblOk ? 1 : 0, "0.13 thrall labels: checks %s; [Debug] Labels %d (on now %d), LabelRadius %.0f, LabelMax %d, "
        "LabelMatch '%s', LabelCross %d; projection matrix 0x%08lx, focal [0x8906d0], text space %.0f x %.0f (draw.scale)",
        g_lblWhy, g_lblAtStart, g_lblOn ? 1 : 0, g_lblRadius, g_lblMax, g_lblMatch, g_lblCross, kLblMatrix, g_drawW, g_drawH);
}

// loaded level only (as NavWorldReady without the NavPower parts)
bool LabelWorldReady(char *why, size_t n) {
    if (!InLevel()) { Out(why, n, "needs a level (no player instance)"); return false; }
    DWORD state = 0;
    ReadDword(kMainState, &state);
    if (state != 1) { Out(why, n, "not while loading (main state %lu, needs 1)", state); return false; }
    return !LevelChangePending(why, n);
}

// object id -> 1 thrall (name contains "thrall"), 2 other instance, 3 no label: only names that contain a part of
// [Debug] LabelMatch (or LabelMatch "*") get a label; cached per object id (the name of an id does not change)
int LabelKind(int id) {
    if (id > 0 && id < 4096 && g_lblNameKind[id]) return g_lblNameKind[id];
    char name[64], list[sizeof(g_lblMatch)];
    int kind = 3;
    if (ObjectName(id, name, sizeof(name))) {
        _strlwr_s(name, sizeof(name));
        strncpy_s(list, sizeof(list), g_lblMatch, _TRUNCATE);
        _strlwr_s(list, sizeof(list));
        char *context = nullptr;
        for (char *part = strtok_s(list, ", ", &context); part; part = strtok_s(nullptr, ", ", &context))
            if (!strcmp(part, "*") || strstr(name, part)) { kind = strstr(name, "thrall") ? 1 : 2; break; }
    }
    if (id > 0 && id < 4096) g_lblNameKind[id] = static_cast<signed char>(kind);
    return kind;
}

// TruShadowCombat's snapshot of this frame (false = none: plugin / export missing, wrong version, no copy yet)
bool LabelTsc() {
    DWORD now = GetTickCount();
    if (!g_tscSnap && (!g_tscLookTick || now - g_tscLookTick >= 5000)) {
        g_tscLookTick = now;
        HMODULE module = GetModuleHandleA("TruShadowCombat.asi");
        g_tscSnap = module ? reinterpret_cast<TscSnapFn>(GetProcAddress(module, "TscTargeterSnapshot")) : nullptr;
        const char *was = g_tscState;
        g_tscState = !module ? "TruShadowCombat not loaded" : !g_tscSnap ? "TruShadowCombat without TscTargeterSnapshot "
                     "(older than 0.5.3)" : "export found";
        if (g_tscState != was) Log(1, "0.13 thrall labels: %s", g_tscState);     // only when it changes
    }
    if (!g_tscSnap) return false;
    DWORD r = 0;
    __try {
        r = g_tscSnap(9, &g_lblSnap, sizeof(g_lblSnap));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        g_tscSnap = nullptr;
        g_tscState = "TscTargeterSnapshot faulted - not called again";
        return false;
    }
    if (g_lblSnap.version != 1 || g_lblSnap.size != sizeof(LblTscSnap)) {
        static bool logged = false;
        if (!logged) {
            logged = true;
            Log(0, "0.13 thrall labels: TscTargeterSnapshot version %lu, size %lu (want 1, %u) - not used",
                g_lblSnap.version, g_lblSnap.size, static_cast<unsigned>(sizeof(LblTscSnap)));
        }
        g_tscState = "TscTargeterSnapshot version / size differ - not used";
        return false;
    }
    g_tscState = r == 1 ? "snapshot ok" : "no snapshot (first frame, [Diag] Targeter9 / Snapshot 0, or no target list)";
    return r == 1;
}

struct LblCand { DWORD inst; float pos[3]; float dist2; int kind; };
LblCand g_lblCand[33];

// appends to o (size n, *used bytes used so far)
void LabelAdd(char *o, size_t n, size_t *used, const char *fmt, ...) {
    if (*used + 1 >= n) return;
    va_list ap;
    va_start(ap, fmt);
    int w = _vsnprintf_s(o + *used, n - *used, _TRUNCATE, fmt, ap);
    va_end(ap);
    if (w > 0) *used += static_cast<size_t>(w);
}

// what TruShadowCombat knows about an instance (second label line) and the label colour: yellow = targeter 9's target,
// green = in a bucket, orange = rejected (E0 = eligibility tru+0x2ecca0 failed, Fxx = filter groups passed, "?" = not
// evaluated by WHY yet), white = not in targeter 9; " | H" = in the player's hit list; "2011 Pfad p q.. = r" = the last
// condition 2011 had this instance as targeter 9's target (path 1 empty / excluded, 2 query 0x161 = 0, 3 ok)
void LabelTscText(DWORD inst, char *o, size_t n, ImU32 *colour) {
    o[0] = 0;
    if (!g_lblSnapOk) return;
    const LblTscSnap &s = g_lblSnap;
    const void *p = reinterpret_cast<const void *>(inst);
    size_t used = 0;
    bool listed = false;
    if (s.target && s.target == p) {
        LabelAdd(o, n, &used, "Z9 ZIEL");
        *colour = IM_COL32(255, 230, 60, 255);
        listed = true;
    }
    for (DWORD i = 0; i < s.count && i < 24; ++i) {
        const LblTscEntry &e = s.entries[i];
        if (e.instance != p) continue;
        const char *gap = listed ? " " : "";
        if (e.where == 0x20) {
            if (e.why == 0xffffffff) LabelAdd(o, n, &used, "%sZ9 abgelehnt (Grund ?)", gap);
            else if (!(e.why & 0x100)) LabelAdd(o, n, &used, "%sZ9 abgelehnt E0 (Eignung)", gap);
            else LabelAdd(o, n, &used, "%sZ9 abgelehnt F%02lx (Filter)", gap, e.why & 0xff);
            if (!listed) *colour = IM_COL32(255, 120, 80, 255);
        } else {
            LabelAdd(o, n, &used, "%sZ9 Fach %lu", gap, e.where - 0x10);
            if (!listed) *colour = IM_COL32(110, 235, 120, 255);
        }
        listed = true;
        break;
    }
    if (!listed) LabelAdd(o, n, &used, "Z9 -");
    for (const void *h : s.hitList)
        if (h && h == p) { LabelAdd(o, n, &used, " | H"); break; }
    if (s.c2011Target == p && s.c2011Calls)
        LabelAdd(o, n, &used, " | 2011 Pfad %lu q%ld = %lu (%lus)", s.c2011Path, s.c2011Query, s.c2011Result,
                 (GetTickCount() - s.c2011Tick) / 1000);
}

// one label: background box, anchor dot, two text lines above the anchor
void LabelDraw(ImDrawList *dl, ImVec2 at, const char *line1, const char *line2, ImU32 colour) {
    const float fs = ImGui::GetFontSize();
    ImVec2 s1 = ImGui::CalcTextSize(line1);
    ImVec2 s2 = line2[0] ? ImGui::CalcTextSize(line2) : ImVec2(0.0f, 0.0f);
    float w = (s1.x > s2.x ? s1.x : s2.x) + 8.0f, h = line2[0] ? 2.0f * fs + 6.0f : fs + 4.0f;
    ImVec2 box(at.x - w * 0.5f, at.y - h - 8.0f);
    dl->AddRectFilled(box, ImVec2(box.x + w, box.y + h), IM_COL32(0, 0, 0, 150), 3.0f);
    dl->AddLine(ImVec2(at.x, at.y - 8.0f), at, colour, 1.5f);
    dl->AddCircleFilled(at, 3.0f, colour, 8);
    dl->AddText(ImVec2(box.x + 4.0f, box.y + 2.0f), colour, line1);
    if (line2[0]) dl->AddText(ImVec2(box.x + 4.0f, box.y + 4.0f + fs), colour, line2);
}

// Present, every frame while dbg.labels is on
void DrawLabels() {
    char why[160];
    g_lblShown = g_lblInRadius = g_lblThralls = 0;
    if (!g_debugEnabled || !g_lblOk) { Out(g_lblState, sizeof(g_lblState), "%s", !g_debugEnabled ? "[Debug] Enabled=0" : g_lblWhy); return; }
    if (!LabelWorldReady(why, sizeof(why))) { Out(g_lblState, sizeof(g_lblState), "waits: %s", why); return; }
    ImGuiIO &io = ImGui::GetIO();
    View v;
    if (!ReadView(&v, io.DisplaySize.x, io.DisplaySize.y) || !ReadFloats(kLblMatrix, v.m, 16)) {
        Out(g_lblState, sizeof(g_lblState), "camera matrix 0x%08lx / focal not readable", kLblMatrix);
        return;
    }
    DWORD player = 0;
    float lara[3];
    if (!ReadDword(kPlayerPtr, &player) || !player || !ReadFloats(player + kInstancePosition, lara, 3)) return;
    g_lblSnapOk = LabelTsc();
    const float r2 = g_lblRadius * g_lblRadius;
    int count = 0;
    DWORD inst = 0;
    ReadDword(kFirstInstance, &inst);
    for (int guard = 0; inst && guard < 4096; ++guard) {
        DWORD next = 0, object = 0, oid = 0;
        float p[3];
        if (inst != player && ReadFloats(inst + kInstancePosition, p, 3)) {
            float dx = p[0] - lara[0], dy = p[1] - lara[1], dz = p[2] - lara[2], d2 = dx * dx + dy * dy + dz * dz;
            if (d2 <= r2 && ReadDword(inst + 0x10, &object) && object && ReadDword(object + 0x14, &oid)) {
                int kind = LabelKind(static_cast<int>(oid & 0xffff));
                if (kind != 3) {
                    ++g_lblInRadius;
                    // sorted insert: thralls first, then nearest; keep g_lblMax
                    int at = count;
                    while (at > 0 && (g_lblCand[at - 1].kind > kind ||
                                      (g_lblCand[at - 1].kind == kind && g_lblCand[at - 1].dist2 > d2)))
                        --at;
                    if (at < g_lblMax) {
                        int last = count < g_lblMax ? count : g_lblMax - 1;
                        for (int k = last; k > at; --k) g_lblCand[k] = g_lblCand[k - 1];
                        LblCand &c = g_lblCand[at];
                        c.inst = inst;
                        c.pos[0] = p[0]; c.pos[1] = p[1]; c.pos[2] = p[2];
                        c.dist2 = d2;
                        c.kind = kind;
                        if (count < g_lblMax) ++count;
                    }
                }
            }
        }
        if (!ReadDword(inst + 8, &next)) break;
        inst = next;
    }
    ImDrawList *dl = ImGui::GetForegroundDrawList();
    ImVec2 laraAt(0.0f, 0.0f);
    bool laraSeen = Project(v, lara, &laraAt);
    if (g_lblCross && laraSeen) {
        const ImU32 magenta = IM_COL32(255, 60, 255, 255);
        dl->AddLine(ImVec2(laraAt.x - 10.0f, laraAt.y), ImVec2(laraAt.x + 10.0f, laraAt.y), magenta, 2.0f);
        dl->AddLine(ImVec2(laraAt.x, laraAt.y - 10.0f), ImVec2(laraAt.x, laraAt.y + 10.0f), magenta, 2.0f);
    }
    for (int i = 0; i < count; ++i) {
        const LblCand &c = g_lblCand[i];
        ImVec2 at;
        if (!Project(v, c.pos, &at)) continue;
        DWORD object = 0, oid = 0, intro = 0;
        ReadDword(c.inst + 0x10, &object);
        if (object) ReadDword(object + 0x14, &oid);
        ReadDword(c.inst + 0x58, &intro);
        char name[64], line1[160], line2[160], hp[32] = "";
        if (!ObjectName(static_cast<int>(oid & 0xffff), name, sizeof(name))) Out(name, sizeof(name), "obj %lu", oid & 0xffff);
        DWORD a = 0, b = 0, brain = 0;
        float health = 0.0f;
        if (c.kind == 1 && ReadDword(c.inst + 0x2d0, &a) && a && ReadDword(a, &b) && b && ReadDword(b + 0x2ec, &brain) &&
            brain && ReadFloats(brain + 0x2c64, &health, 1) && health > -1.0e6f && health < 1.0e6f)
            Out(hp, sizeof(hp), " | LP %.1f", health);
        Out(line1, sizeof(line1), "%s %ld | %.0f%s", name, static_cast<LONG>(intro), sqrtf(c.dist2), hp);
        ImU32 colour = IM_COL32(235, 235, 235, 255);
        LabelTscText(c.inst, line2, sizeof(line2), &colour);
        LabelDraw(dl, at, line1, line2, colour);
        ++g_lblShown;
        if (c.kind == 1) ++g_lblThralls;
    }
    Out(g_lblState, sizeof(g_lblState), "%d shown (%d thralls), %d in %.0f units; TruShadowCombat: %s", g_lblShown,
        g_lblThralls, g_lblInRadius, g_lblRadius, g_tscState);
    DWORD now = GetTickCount();
    if (!g_lblLogTick || now - g_lblLogTick >= 10000) {       // calibration line (log only), every 10 s while on
        g_lblLogTick = now;
        DWORD dev = 0, aspect = 0;
        if (ReadDword(kLblAspect, &dev) && dev) ReadDword(dev + 0x170, &aspect);
        Log(1, "0.13 thrall labels: %s; matrix 0xe804a0 rows %.3f %.3f %.3f | %.3f %.3f %.3f | %.3f %.3f %.3f | t %.1f %.1f "
            "%.1f, focal %.2f, aspect [[0xad75e4]+0x170] %lu, back buffer %.0f x %.0f; Lara (%.1f %.1f %.1f) -> %s %.1f %.1f",
            g_lblState, v.m[0], v.m[1], v.m[2], v.m[4], v.m[5], v.m[6], v.m[8], v.m[9], v.m[10], v.m[12], v.m[13], v.m[14],
            v.f, aspect, io.DisplaySize.x, io.DisplaySize.y, lara[0], lara[1], lara[2], laraSeen ? "screen" : "not in view",
            laraAt.x, laraAt.y);
    }
}

void ValLabels(char *o, size_t n) { Out(o, n, "%d (%s)", g_lblOn ? 1 : 0, g_lblOn ? g_lblState : "off"); }
bool RunLabels(const char *arg, char *o, size_t n) {
    if (!g_debugEnabled) { Out(o, n, "debug drawing off ([Debug] Enabled=0)"); return false; }
    if (!g_lblOk) { Out(o, n, "disabled: pre-check failed (%s)", g_lblWhy); return false; }
    bool on = BoolArg(arg, g_lblOn != 0);
    InterlockedExchange(&g_lblOn, on ? 1 : 0);
    g_lblLogTick = 0;                        // a calibration line with the first frame
    Log(1, "dbg.labels %d (src=%s)", on ? 1 : 0, ShotSource("dbg.labels"));
    Out(o, n, "dbg.labels %d", on ? 1 : 0);
    return true;
}
// ring: why dbg.labels is greyed out ("" = usable; outside a level it may be switched, it draws in the next level)
const char *LabelRadWhy() {
    if (!g_debugEnabled) return "debug drawing off ([Debug] Enabled=0)";
    if (!g_lblOk) return g_lblWhy;
    return "";
}

// ---- 0.14 Debug view (debug view stage S3, owner order 2026-11-06): trigger wireframes by kind, stream portals
// (loading areas), checkpoint objects, legend, master switch dbg.view ----
// Workspace docs\Befund-TruMenu-Trigger-0611.md; every byte check is pinned in work\asi\menu014\precheck_014.txt
// (tools/pe_bytes_check.py on the Steam exe: 67 / 67 ok). Read-only: nothing is written into game memory and no game
// function is called (dbg.view only calls the 0.12 / 0.13 / 0.3 items, which keep their own gates). Drawn at Present
// into ImGui's background draw list (legend: foreground), only in a loaded level (player instance, main state 1, no
// level change pending - the gates of dbg.labels; nothing about Lara's own state, so it keeps drawing during the 0.8.1
// flight), with fixed static buffers (no allocation by TruMenu per frame) and the projection of 0.13 (matrix 0xe804a0,
// 0x49f630) plus near-plane clipping per line (z' > 16), so a box around the camera still draws its visible part.
// Triggers = the two lists the game tests every frame (0x5cd520): planes count [0xdba21c] / array 0xda61c8, volumes
// count [0xdba220] / array 0xdb6be0 (at most 0x200 each, adders 0x5c8990 / 0x5c89e0). Entry +0x20 = the trigger
// instance, +0x24 bit 31 = enabled (0x4a4360; a disabled entry is skipped by the game and drawn dim here), bit 30 =
// tested against the player (0x4a4450). Data = [[instance+0x100]+0x78] (IntroDataTrigger). The game tests the point
// player +0x20 + (0, 0, 200.0) ([0x853f08]; drawn as the white "Testpunkt" cross):
//   volume (0x5cd1b0): byte +0x30 = shape; 1 box: centre = instance +0x20, half extents +0x34 / +0x38 / +0x3c along the
//     rows of M = Rz * Ry * Rx built from the instance Euler angles +0x30 (0x49d500: identity post-multiplied by the
//     axis rotations 0x49bd40 / 0x49bc70 / 0x49bb90, row vectors), tested through its quaternion (0x49d720) as
//     |conjugate(q) rotated (p - centre)| <= h (0x46b730) - i.e. local = (p - centre) * M^T, so corner = centre +
//     (+-h) * M; 2 sphere: squared distance to instance +0x20 < radius +0x40 squared (0x4355d0) -> 3 great circles.
//   plane (0x5ccc20): the quad (+-w, 0, +-h) * M + instance +0x20 (0x435220 -> 0x49ba20 adds row 3), w = +0x34,
//     h = +0x3c; byte +0x44 = 0 -> one-sided (the crossing direction is tested) -> arrow along row 1 (the quad normal).
// Kind (colour) from the trigger instance's object name (first match wins): checkpoint, death / kill, fire / burn /
// flame, water / swim, sound / swoosh / audio / music / sfx; no keyword = plain volume / plane; no intro data, an
// unknown shape or no name = unknown. Portals (loading areas): every loaded stream unit (table 0xdbab40, state 2): entry
// +8 Level, [Level] Terrain, Terrain +2 s16 count, +4 array of 0x100-byte StreamUnitPortal (name +0, quad corners
// +0xb0 / +0xc0 / +0xd0 / +0xe0, normal +0xf0 - the corner layout is read from the unit DRMs, docs). Checkpoints =
// instances whose object name contains "checkpoint"; the active one = game data [0xc59264] +0x90 (+0x114 when the word
// +0x1f4 is not 0), the id the player placement 0x5d40c0 uses.
struct DvCheck { DWORD at; const char *hex; };
const DvCheck kDvTrigChecks[] = {
    {0x005cd527, "392d1ca2db00"},
    {0x005cd540, "8b1cadc861da00 8bcb e8126eedff 84c0 0f84b6000000 8bcb e8f36eedff"},
    {0x005cd561, "a194f0e700 53 50 e8b3f6ffff"},
    {0x005cd61b, "33c0 390520a2db00 89442410 0f8e8f010000 8d6802 8b3485e06bdb00 8bce e8226dedff"},
    {0x005cd651, "8b1594f0e700 56 52 e852fbffff"},
    {0x005c89a1, "8b0d1ca2db00 81f900020000"},
    {0x005c89f1, "8b0d20a2db00 81f900020000"},
    {0x004a4360, "8b4124 c1e81f 2401 c3"},
    {0x004a4450, "8b4124 c1e81e 2401 c3"},
    {0x005cd1c2, "d905083f8500"},
    {0x00853f08, "00004843"},
    {0x005cd235, "0f284820 8b7120 0f58c8 0f294c2470 8b8600010000 85c0 0f84c5020000 8b7878 85ff 0f84ba020000"},
    {0x005cd27a, "0fb65f30"},
    {0x005cd345, "8b4e20 894c2440 8b5624 89542444 8b4628 89442448 8b4e2c 894c244c 83c630 56 8d8c24b4000000 e88f01edff"},
    {0x005cd3c1, "8d9424b0000000 52 8d8c24a4000000 0f298424e4000000 e84303edff d94734"},
    {0x005cd3ec, "d94738"},
    {0x005cd3f9, "d9473c"},
    {0x005cd42e, "d94740 8bc3 d95c2420 83e801 7470 83e801 0f85d2000000 d9442420"},
    {0x005cd456, "dcc8"},
    {0x005cd468, "e86381e6ff dc5c2420"},
    {0x004355d0, "55 8bec 83e4f0 83ec10 0f2801 0f59c0"},
    {0x005cd4c6, "e865e2e9ff"},
    {0x005cd4e7, "e844e2e9ff"},
    {0x0046b75f, "f30f1005a82a8400"},
    {0x0046b7a3, "8d442420 50 8d4c2404 0f29442434 0f2802 51 0f5cc8 8d4c2438 0f294c2428 e87a150300"},
    {0x0046b7c6, "d90424 8b4d14 d901 d8d9 dfe0 f6c405 7b4f d901 d9e0 ded9"},
    {0x0049cdce, "e86dfbffff"},
    {0x0049cdea, "e851fbffff"},
    {0x0049c987, "d944240c d9c0 d9442410 d9c0 deca d9442414 d9c0 d9442418 d9c0 deca d9cc dec1 d944241c d9c0 d84c2404 dec2 "
                 "d90424 d84c2408 deea"},
    {0x0049d50b, "f30f10051c118400 f30f100d34118400"},
    {0x0084111c, "00000000"},
    {0x00841134, "0000803f"},
    {0x0049d5a3, "d94708 d95c240c d944240c e86d5e3700 d95c2408 d9442408 51 d91c24 d9442410 e8b8603700"},
    {0x0049d5d0, "51 8bce d91c24 e865e7ffff d94704"},
    {0x0049d5e6, "e8355e3700"},
    {0x0049d5fb, "e880603700"},
    {0x0049d608, "51 8bce d91c24 e85de6ffff d907"},
    {0x0049d61d, "e8fe5d3700"},
    {0x0049d632, "e849603700"},
    {0x0049d63f, "51 8bce d91c24 e846e5ffff"},
    {0x0081348d, "d9ff"},
    {0x008136ed, "d9fe"},
    {0x0049bd40, "83ec08 8bc1 d900 d91c24 d94004 d95c2404 d90424 d9c0 d9442410 d9c0 deca d9442404 d9c0 d944240c d9c0 deca "
                 "d9cc dee1 d918 d9c2 decc d8c9 dec3 d9ca d95804"},
    {0x0049bc70, "83ec08 8bc1 d900 d95c2404 d94008 d91c24 d90424 d9c0 d944240c d9c0 deca d9442404 d9c0 d9442410 d9c0 deca "
                 "d9cc dec1 d918 d9c2 decc d8c9 deeb d9ca d95808"},
    {0x0049bb90, "83ec08 8bc1 d94004 d91c24 d94008 d95c2404 d90424 d9c0 d9442410 d9c0 deca d9442404 d9c0 d944240c d9c0 deca "
                 "d9cc dee1 d95804 d9c2 decc d8c9 dec3 d9ca d95808"},
    {0x0049d720, "8b542404 d902 d84214 d84228 d95c2404 d9ee d9442404 d8d1 dfe0 ddd9 f6c441 752b d94218 d86224 d919 d94220 "
                 "d86208 d95904 d94204 d86210 d95908"},
    {0x005ccc40, "d905083f8500"},
    {0x005cccb4, "8b7120"},
    {0x005cccc6, "8b8600010000 85c0 0f58c1 0f84b4040000 8b7878"},
    {0x005ccd22, "8d4e30 0f5cca 51"},
    {0x005ccd3b, "e8c007edff d94628"},
    {0x005ccda3, "d94734 f30f10051c118400 d95c2448 d9473c"},
    {0x005cce6e, "e8ad83e6ff"},
    {0x005ccea3, "e87883e6ff"},
    {0x005ccee4, "e83783e6ff"},
    {0x005ccf1c, "e8ff82e6ff"},
    {0x005ccf55, "807f4400"},
    {0x00435259, "e8c2670600"},
    {0x0049ba20, "55 8bec 83e4f0 8b4d10 0f2801 8b4d0c 0f285120 0f285910 8b4508 0f28c8 0fc6c8aa 0f59ca 0f285130 0f58ca"},
    {0x0049ba4b, "0f28d0 0fc6d055 0f59d3 0f58ca 0f28d0 0fc6d000 0f2801 0f59d0 0f58ca 0f2908"},
};
const DvCheck kDvPortalChecks[] = {
    {0x005d295f, "8b5608 8b02 0fbf4802 8b6804"},
    {0x005d2a48, "81c500010000"},
    {0x005d2ab5, "8b4808 8b11 8b4c2420 8b7914 c1e708 037a04"},
    {0x005d2aca, "0fbf9f84000000"},
};
const DvCheck kDvCpChecks[] = {
    {0x005d41df, "a16492c500 8b8890000000 8b9014010000 0fb780f4010000"},
    {0x005d4214, "6639b8f4010000 7408 8b9814010000 eb06 8b9890000000"},
    {0x0085512c, "636865636b706f696e7400"},
    {0x00855118, "696e7669735f636865636b706f696e7400"},
};
const DWORD kDvPlaneCount = 0x00dba21c, kDvPlanes = 0x00da61c8, kDvVolCount = 0x00dba220, kDvVols = 0x00db6be0;
const DWORD kDvListMax = 0x200, kDvGameData = 0x00c59264;
const float kDvTestLift = 200.0f;            // [0x853f08], added to the player position by both tests

// the layers: 8 trigger kinds first (kind = layer index), then portals, checkpoint objects, trigger names, legend
enum DvLayer {
    kDvDeath = 0, kDvFire, kDvCheckpoint, kDvWater, kDvSound, kDvVolume, kDvPlane, kDvUnknown, kDvKinds,
    kDvPortals = kDvKinds, kDvCheckpoints, kDvTrgLabels, kDvLegend, kDvNames, kDvCount
};
struct DvLayerDef { const char *name, *key, *de, *en; ImU32 colour; };
const DvLayerDef kDvLayers[kDvCount] = {
    {"death", "TrgDeath", "Tod / Kill", "death / kill", IM_COL32(255, 50, 50, 255)},
    {"fire", "TrgFire", "Feuer", "fire / slow fire", IM_COL32(255, 150, 30, 255)},
    {"checkpoint", "TrgCheckpoint", "Checkpoint-Trigger", "checkpoint trigger", IM_COL32(70, 255, 110, 255)},
    {"water", "TrgWater", "Wasser", "water", IM_COL32(70, 150, 255, 255)},
    {"sound", "TrgSound", "Ton / Swoosh", "sound / swoosh", IM_COL32(220, 110, 255, 255)},
    {"volume", "TrgVolume", "Trigger (Volumen)", "plain trigger volume", IM_COL32(255, 235, 70, 255)},
    {"plane", "TrgPlane", "Trigger-Ebene", "trigger plane", IM_COL32(60, 235, 235, 255)},
    {"unknown", "TrgUnknown", "Trigger unbekannt", "unknown trigger", IM_COL32(170, 170, 170, 255)},
    {"portals", "Portals", "Ladebereiche", "loading areas (stream portals)", IM_COL32(255, 255, 255, 255)},
    {"checkpoints", "Checkpoints", "Checkpoints", "checkpoint objects", IM_COL32(150, 255, 190, 255)},
    {"trglabels", "TrgLabels", "Trigger-Namen", "trigger names", IM_COL32(235, 235, 235, 255)},
    {"legend", "Legend", "Legende", "legend", IM_COL32(235, 235, 235, 255)},
    {"names", "Names", "Objektnamen", "object names", IM_COL32(255, 255, 255, 255)},
};
// object name part -> kind (first match wins, so "deathfiretriggervolume" is death)
struct DvWord { const char *part; int kind; };
const DvWord kDvWords[] = {{"checkpoint", kDvCheckpoint}, {"death", kDvDeath}, {"kill", kDvDeath}, {"fire", kDvFire},
                           {"burn", kDvFire},  {"flame", kDvFire}, {"water", kDvWater}, {"swim", kDvWater},
                           {"sound", kDvSound}, {"swoosh", kDvSound}, {"audio", kDvSound}, {"music", kDvSound},
                           {"sfx", kDvSound}};

bool g_dvTrgOk = false, g_dvPortalOk = false, g_dvCpOk = false, g_dvBaseOk = false;   // base = projection + lists
const char *g_dvBaseWhy = "not checked";
// object names (layer names, owner wish 2026-11-06): every instance's object name from the LIVE PC object list
// [0xdb94d0] (ObjectName, as LabelKind / dbg.labels) - never a name table taken from the Xbox data
char g_dvNameMatch[128] = "";                // [Debug] NameMatch: comma list of name parts, empty or * = every instance
float g_dvNameRadius = 5000.0f, g_dvNameScale = 1.0f;   // [Debug] NameRadius (from the camera) / NameScale (font)
int g_dvNameMax = 24, g_dvNameIds = 1;       // [Debug] NameMax / NameIds (intro id after the name)
DWORD g_dvNameRgb = 0xffffff;                // [Debug] NameColour RRGGBB
signed char g_dvNameHit[4096];               // per object id: 0 not looked up, 1 matches NameMatch, 2 not
struct DvColourPreset { const char *name, *de; DWORD rgb; };
const DvColourPreset kDvNameColours[] = {{"white", "weiss", 0xffffff}, {"yellow", "gelb", 0xffe040},
                                         {"cyan", "cyan", 0x40e8ff}, {"magenta", "magenta", 0xff50ff}};
const char *g_dvTrgWhy = "not checked", *g_dvPortalWhy = "not checked", *g_dvCpWhy = "not checked";
volatile LONG g_dvOn[kDvCount] = {};         // the layers (dbg.show <layer>, dbg.triggers, dbg.portals, ...)
int g_dvAtStart[kDvCount] = {};              // [Debug] TrgDeath .. Legend
int g_dvViewAtStart = 0, g_dvTrgAtStart = 0, g_dvMarkupAtStart = 0, g_dvPersist = 0;   // [Debug] View / Triggers / ..
int g_dvTrgMax = 64, g_dvLabelMax = 16;      // [Debug] TriggerMax / TriggerLabelMax
float g_dvRadius = 20000.0f;                 // [Debug] TriggerRadius (from the camera)
char g_dvViewNav[160] = "planner_areas,planner_connectivity,obstacles";   // [Debug] ViewNav
char g_dvState[640] = "off";                 // last frame: why nothing / what was drawn (dbg.status)
int g_dvDrawn[kDvCount] = {}, g_dvListed[kDvCount] = {};   // last frame per layer: drawn / found in the lists
volatile LONG g_dvLogPending = 0;            // one "drawn" log line with the first frame after a switch
signed char g_dvNameKind[4096];              // per object id: 0 not looked up, kind + 1, 100 no keyword, 101 checkpoint

void DvTrim(char *s) {                       // leading / trailing blanks off (item arguments)
    size_t len = strlen(s);
    while (len && (s[len - 1] == ' ' || s[len - 1] == '\t')) s[--len] = 0;
    size_t lead = strspn(s, " \t");
    if (lead) memmove(s, s + lead, len - lead + 1);
}

// load: the byte checks of precheck_014.txt (projection = the 0.13 checks, g_lblProjOk)
bool DvChecks(const DvCheck *c, size_t count, DWORD *failedAt) {
    for (size_t i = 0; i < count; ++i)
        if (!HexBytesAt(c[i].at, c[i].hex)) { *failedAt = c[i].at; return false; }
    return true;
}
char g_dvTrgWhyBuf[96], g_dvPortalWhyBuf[96], g_dvCpWhyBuf[96];
bool DvLayerOk(int layer, const char **why);  // below
void DebugViewCheck() {
    DWORD at = 0;
    bool base = g_lblProjOk && g_instOk && g_playerOk && g_mainStateOk;
    const char *baseWhy = !g_lblProjOk ? "projection (0.13 checks) failed" : !g_instOk ? "instance list (0.3 check) failed"
                        : !g_playerOk ? "player pointer check failed" : "main state check failed";
    g_dvTrgOk = base && DvChecks(kDvTrigChecks, sizeof(kDvTrigChecks) / sizeof(kDvTrigChecks[0]), &at);
    if (!base) Out(g_dvTrgWhyBuf, sizeof(g_dvTrgWhyBuf), "%s", baseWhy);
    else Out(g_dvTrgWhyBuf, sizeof(g_dvTrgWhyBuf), "trigger code differs at 0x%08lx", at);
    g_dvTrgWhy = g_dvTrgOk ? "ok" : g_dvTrgWhyBuf;
    g_dvPortalOk = base && g_unitOk && DvChecks(kDvPortalChecks, sizeof(kDvPortalChecks) / sizeof(kDvPortalChecks[0]), &at);
    if (!base) Out(g_dvPortalWhyBuf, sizeof(g_dvPortalWhyBuf), "%s", baseWhy);
    else if (!g_unitOk) Out(g_dvPortalWhyBuf, sizeof(g_dvPortalWhyBuf), "stream unit table check failed");
    else Out(g_dvPortalWhyBuf, sizeof(g_dvPortalWhyBuf), "stream portal code differs at 0x%08lx", at);
    g_dvPortalWhy = g_dvPortalOk ? "ok" : g_dvPortalWhyBuf;
    g_dvCpOk = base && DvChecks(kDvCpChecks, sizeof(kDvCpChecks) / sizeof(kDvCpChecks[0]), &at);
    if (!base) Out(g_dvCpWhyBuf, sizeof(g_dvCpWhyBuf), "%s", baseWhy);
    else Out(g_dvCpWhyBuf, sizeof(g_dvCpWhyBuf), "checkpoint game data code differs at 0x%08lx", at);
    g_dvCpWhy = g_dvCpOk ? "ok" : g_dvCpWhyBuf;
    g_dvBaseOk = base;
    g_dvBaseWhy = base ? "ok" : baseWhy;
    memset(g_dvNameKind, 0, sizeof(g_dvNameKind));
    memset(g_dvNameHit, 0, sizeof(g_dvNameHit));
    int on = 0;
    if (g_debugEnabled) {
        for (int i = 0; i < kDvCount; ++i) {
            bool want = g_dvAtStart[i] || g_dvViewAtStart || (i < kDvKinds && g_dvTrgAtStart);
            const char *why = "";
            if (want && DvLayerOk(i, &why)) { InterlockedExchange(&g_dvOn[i], 1); ++on; }
        }
        if ((g_dvMarkupAtStart || g_dvViewAtStart) && g_drawOk) InterlockedExchange(&g_drawMarkup, 1);
    }
    Log(g_dvTrgOk && g_dvPortalOk && g_dvCpOk ? 1 : 0, "0.14 debug view: triggers %s, portals %s, checkpoints %s, object "
        "names %s; [Debug] View %d, Triggers %d, %d layer(s) on now, Markup %d, ViewNav '%s', TriggerMax %d, TriggerRadius "
        "%.0f, TriggerLabelMax %d, NameMatch '%s', NameRadius %.0f, NameMax %d, NameScale %.2f, NameColour %06lX, NameIds "
        "%d, Persist %d", g_dvTrgWhy, g_dvPortalWhy, g_dvCpWhy, g_dvBaseWhy, g_dvViewAtStart, g_dvTrgAtStart, on,
        g_drawMarkup ? 1 : 0, g_dvViewNav, g_dvTrgMax, g_dvRadius, g_dvLabelMax, g_dvNameMatch, g_dvNameRadius,
        g_dvNameMax, g_dvNameScale, g_dvNameRgb, g_dvNameIds, g_dvPersist);
}

// the check a layer needs (true = usable)
bool DvLayerOk(int layer, const char **why) {
    bool ok = layer < kDvKinds || layer == kDvTrgLabels ? g_dvTrgOk : layer == kDvPortals ? g_dvPortalOk
            : layer == kDvCheckpoints ? g_dvCpOk : layer == kDvNames ? g_dvBaseOk : true;
    *why = layer < kDvKinds || layer == kDvTrgLabels ? g_dvTrgWhy : layer == kDvPortals ? g_dvPortalWhy
         : layer == kDvCheckpoints ? g_dvCpWhy : layer == kDvNames ? g_dvBaseWhy : "ok";
    return ok;
}
int DvFind(const char *text) {
    if (!text) return -1;
    while (*text == ' ') ++text;
    size_t len = 0;
    while (text[len] && text[len] != ' ') ++len;
    for (int i = 0; i < kDvCount; ++i)
        if (strlen(kDvLayers[i].name) == len && !_strnicmp(kDvLayers[i].name, text, len)) return i;
    return -1;
}
bool DvAnyOn() {
    for (int i = 0; i < kDvCount; ++i)
        if (g_dvOn[i]) return true;
    return false;
}
bool DvAnyTrigger() {
    for (int i = 0; i < kDvKinds; ++i)
        if (g_dvOn[i]) return true;
    return false;
}

// [Debug] Persist=1: a switch is written back to TruMenu.ini at once (read at the next start)
void DvPersistKey(const char *key, bool on) {
    if (g_dvPersist && g_iniPath[0]) WritePrivateProfileStringA("Debug", key, on ? "1" : "0", g_iniPath);
}
void DvPersistNav() {
    if (!g_dvPersist || !g_iniPath[0]) return;
    char list[200] = "";
    size_t used = 0;
    for (int i = 0; i < kNavCount; ++i) {
        if (!NavByteOn(i)) continue;
        int w = _snprintf_s(list + used, sizeof(list) - used, _TRUNCATE, "%s%s", used ? "," : "", kNavSwitches[i].name);
        if (w > 0) used += static_cast<size_t>(w);
    }
    WritePrivateProfileStringA("Debug", "NavDraw", list, g_iniPath);
}

// one layer on / off (check passed); src for the log line
bool DvSet(int layer, bool on, const char *src, char *o, size_t n) {
    const char *why = "";
    if (!g_debugEnabled) { Out(o, n, "debug drawing off ([Debug] Enabled=0)"); return false; }
    if (!DvLayerOk(layer, &why)) {
        Out(o, n, "disabled: pre-check failed (%s)", why);
        Log(1, "dbg.show %s %d refused - %s (src=%s)", kDvLayers[layer].name, on ? 1 : 0, o, src);
        return false;
    }
    InterlockedExchange(&g_dvOn[layer], on ? 1 : 0);
    InterlockedExchange(&g_dvLogPending, 1);
    DvPersistKey(kDvLayers[layer].key, on);
    Log(1, "dbg.show %s %d (src=%s)", kDvLayers[layer].name, on ? 1 : 0, src);
    Out(o, n, "dbg.show %s %d", kDvLayers[layer].name, on ? 1 : 0);
    return true;
}

// object id -> kind of a trigger instance (kDvDeath .. kDvSound), -1 no keyword, -2 no name; cached per object id
int DvNameKind(DWORD inst, char *name, size_t size) {
    DWORD object = 0, oid = 0;
    name[0] = 0;
    if (!ReadDword(inst + 0x10, &object) || !object || !ReadDword(object + 0x14, &oid)) return -2;
    int id = static_cast<int>(oid & 0xffff);
    if (!ObjectName(id, name, size)) return -2;
    if (id > 0 && id < 4096 && g_dvNameKind[id]) {
        int c = g_dvNameKind[id];
        return c >= 100 ? -1 : c - 1;
    }
    char low[64];
    strncpy_s(low, sizeof(low), name, _TRUNCATE);
    _strlwr_s(low, sizeof(low));
    int kind = -1;
    for (const DvWord &w : kDvWords)
        if (strstr(low, w.part)) { kind = w.kind; break; }
    if (id > 0 && id < 4096) g_dvNameKind[id] = static_cast<signed char>(kind < 0 ? 100 : kind + 1);
    return kind;
}

// projection with a near plane: camera space (x', y' scaled like the game's text space, z' = depth in world units)
struct DvCam { View v; float ux, uy; };     // ux / uy = 1 / length of the scaled x / y columns (world distances)
void DvToCam(const DvCam &c, const float *p, float *o) {
    const float *m = c.v.m;
    o[0] = m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12];
    o[1] = m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13];
    o[2] = m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14];
}
const float kDvNear = 16.5f;                 // the game draws when 16.0 < z' ([0x8451e4])
bool DvCamToScreen(const DvCam &c, const float *q, ImVec2 *out) {
    if (!(q[2] >= kDvNear)) return false;
    float x = static_cast<float>(q[0] / q[2] * c.v.f + c.v.cx) * c.v.sx;
    float y = static_cast<float>(q[1] / q[2] * c.v.f + c.v.cy) * c.v.sy;
    if (!(x > -100000.0f && x < 100000.0f && y > -100000.0f && y < 100000.0f)) return false;
    out->x = x;
    out->y = y;
    return true;
}
// a world line, clipped at the near plane; false = nothing of it in front of the camera
bool DvLine(ImDrawList *dl, const DvCam &c, const float *a, const float *b, ImU32 colour, float thick) {
    float ca[3], cb[3];
    DvToCam(c, a, ca);
    DvToCam(c, b, cb);
    if (ca[2] < kDvNear && cb[2] < kDvNear) return false;
    if (ca[2] < kDvNear || cb[2] < kDvNear) {
        float *near_ = ca[2] < kDvNear ? ca : cb;
        const float *far_ = ca[2] < kDvNear ? cb : ca;
        float t = (kDvNear - near_[2]) / (far_[2] - near_[2]);
        for (int k = 0; k < 3; ++k) near_[k] += (far_[k] - near_[k]) * t;
        near_[2] = kDvNear;
    }
    ImVec2 sa, sb;
    if (!DvCamToScreen(c, ca, &sa) || !DvCamToScreen(c, cb, &sb)) return false;
    dl->AddLine(sa, sb, colour, thick);
    return true;
}
bool DvFinite(const float *p, int count) {
    for (int i = 0; i < count; ++i)
        if (!(p[i] > -1.0e7f && p[i] < 1.0e7f)) return false;
    return true;
}
// rows of M = Rz * Ry * Rx (0x49d500) from the Euler angles r (x, y, z), row vectors: world offset = local * M
void DvEulerRows(const float *r, float rows[3][3]) {
    float cx = cosf(r[0]), sx = sinf(r[0]), cy = cosf(r[1]), sy = sinf(r[1]), cz = cosf(r[2]), sz = sinf(r[2]);
    rows[0][0] = cz * cy; rows[0][1] = sz * cx + cz * sy * sx; rows[0][2] = sz * sx - cz * sy * cx;
    rows[1][0] = -sz * cy; rows[1][1] = cz * cx - sz * sy * sx; rows[1][2] = cz * sx + sz * sy * cx;
    rows[2][0] = sy; rows[2][1] = -cy * sx; rows[2][2] = cy * cx;
}
void DvPoint(const float *pos, const float rows[3][3], float a, float b, float c, float *o) {
    for (int k = 0; k < 3; ++k) o[k] = pos[k] + a * rows[0][k] + b * rows[1][k] + c * rows[2][k];
}

struct DvTrig {
    DWORD entry, inst;
    float pos[3], rot[3], ext[3], radius, dist2, extent;
    int kind;                                // layer index kDvDeath .. kDvUnknown
    BYTE shape;                              // 1 box, 2 sphere, 0 plane / unknown
    bool plane, enabled, oneSided;
};
DvTrig g_dvTrig[257];
struct DvMark { DWORD inst; float pos[3], dist2; };
DvMark g_dvCp[33];

// distance from the camera (world units) and a cheap "can it be on screen" test with a bounding radius
bool DvVisible(const DvCam &c, const float *p, float extent, float *dist2) {
    float q[3];
    DvToCam(c, p, q);
    float x = q[0] * c.ux, y = q[1] * c.uy;
    *dist2 = x * x + y * y + q[2] * q[2];
    if (q[2] + extent < kDvNear) return false;                // behind the camera
    float z = q[2] > kDvNear ? q[2] : kDvNear;
    // text space half width 256 / half height 224 at focal f: |x'| / z' * f <= 256 (+ the extent)
    if ((fabsf(q[0]) - extent / c.ux) * c.v.f > 320.0f * z) return false;
    if ((fabsf(q[1]) - extent / c.uy) * c.v.f > 290.0f * z) return false;
    return true;
}

// sorted insert (nearest first), at most g_dvTrgMax; returns false when it did not fit
int g_dvTrigCount = 0;
void DvTrigInsert(const DvTrig &t) {
    int at = g_dvTrigCount;
    while (at > 0 && g_dvTrig[at - 1].dist2 > t.dist2) --at;
    if (at >= g_dvTrgMax) return;
    int last = g_dvTrigCount < g_dvTrgMax ? g_dvTrigCount : g_dvTrgMax - 1;
    for (int k = last; k > at; --k) g_dvTrig[k] = g_dvTrig[k - 1];
    g_dvTrig[at] = t;
    if (g_dvTrigCount < g_dvTrgMax) ++g_dvTrigCount;
}

// collect one list (planes or volumes) into g_dvTrig; counters for the state line
struct DvCount { int listed, behind, far_, noData, disabled; };
void DvCollect(const DvCam &c, bool planes, DvCount *k) {
    DWORD count = 0;
    if (!ReadDword(planes ? kDvPlaneCount : kDvVolCount, &count) || count > kDvListMax) return;
    for (DWORD i = 0; i < count; ++i) {
        DvTrig t = {};
        DWORD flags = 0, intro = 0, data = 0;
        if (!ReadDword((planes ? kDvPlanes : kDvVols) + i * 4, &t.entry) || !t.entry) continue;
        if (!ReadDword(t.entry + 0x20, &t.inst) || !t.inst || !ReadDword(t.entry + 0x24, &flags)) continue;
        if (!ReadFloats(t.inst + kInstancePosition, t.pos, 3) || !ReadFloats(t.inst + 0x30, t.rot, 3) ||
            !DvFinite(t.pos, 3) || !DvFinite(t.rot, 3))
            continue;
        t.plane = planes;
        t.enabled = (flags & 0x80000000u) != 0;
        bool haveData = ReadDword(t.inst + 0x100, &intro) && intro && ReadDword(intro + 0x78, &data) && data &&
                        ReadFloats(data + 0x34, t.ext, 3) && ReadFloats(data + 0x40, &t.radius, 1) &&
                        DvFinite(t.ext, 3) && DvFinite(&t.radius, 1) && ReadByte(data + 0x30, &t.shape);
        BYTE side = 1;
        if (haveData && planes) ReadByte(data + 0x44, &side);
        t.oneSided = planes && side == 0;
        char name[64];
        int kind = DvNameKind(t.inst, name, sizeof(name));
        bool known = haveData && (planes || t.shape == 1 || t.shape == 2) && kind != -2;
        t.kind = !known ? kDvUnknown : kind >= 0 ? kind : planes ? kDvPlane : kDvVolume;
        if (!haveData) ++k->noData;
        ++g_dvListed[t.kind];
        if (!g_dvOn[t.kind]) continue;
        ++k->listed;
        if (!t.enabled) ++k->disabled;
        t.extent = !known ? 60.0f : planes ? sqrtf(t.ext[0] * t.ext[0] + t.ext[2] * t.ext[2])
                 : t.shape == 2 ? fabsf(t.radius) : sqrtf(t.ext[0] * t.ext[0] + t.ext[1] * t.ext[1] + t.ext[2] * t.ext[2]);
        if (!DvVisible(c, t.pos, t.extent, &t.dist2)) { ++k->behind; continue; }
        if (t.dist2 > g_dvRadius * g_dvRadius) { ++k->far_; continue; }
        DvTrigInsert(t);
    }
}

// one trigger: box 12 lines, sphere 3 circles, plane quad + diagonals (+ normal arrow when one-sided), unknown a cross
void DvDrawTrig(ImDrawList *dl, const DvCam &c, const DvTrig &t, ImVec2 *labelAt, bool *labelSeen) {
    ImU32 colour = kDvLayers[t.kind].colour;
    if (!t.enabled) colour = (colour & 0x00ffffff) | (90u << 24);   // the game skips a disabled entry
    float thick = t.kind == kDvDeath ? 2.5f : 1.8f;
    float rows[3][3];
    DvEulerRows(t.rot, rows);
    float top[3] = {t.pos[0], t.pos[1], t.pos[2]};
    if (t.kind == kDvUnknown && !(t.plane || t.shape == 1 || t.shape == 2)) {
        for (int a = 0; a < 3; ++a) {
            float p0[3] = {t.pos[0], t.pos[1], t.pos[2]}, p1[3] = {t.pos[0], t.pos[1], t.pos[2]};
            p0[a] -= 60.0f;
            p1[a] += 60.0f;
            DvLine(dl, c, p0, p1, colour, thick);
        }
    } else if (t.plane) {
        float q[4][3];
        const float s[4][2] = {{1, -1}, {1, 1}, {-1, 1}, {-1, -1}};
        for (int i = 0; i < 4; ++i) DvPoint(t.pos, rows, s[i][0] * t.ext[0], 0.0f, s[i][1] * t.ext[2], q[i]);
        for (int i = 0; i < 4; ++i) DvLine(dl, c, q[i], q[(i + 1) & 3], colour, thick);
        DvLine(dl, c, q[0], q[2], colour, 1.0f);
        DvLine(dl, c, q[1], q[3], colour, 1.0f);
        if (t.oneSided) {
            float len = t.ext[0] < t.ext[2] ? t.ext[0] : t.ext[2];
            len = len < 50.0f ? 50.0f : len > 300.0f ? 300.0f : len;
            float tip[3];
            DvPoint(t.pos, rows, 0.0f, len, 0.0f, tip);
            DvLine(dl, c, t.pos, tip, colour, thick);
        }
    } else if (t.shape == 1) {
        float q[8][3];
        for (int i = 0; i < 8; ++i)
            DvPoint(t.pos, rows, (i & 1 ? 1.0f : -1.0f) * t.ext[0], (i & 2 ? 1.0f : -1.0f) * t.ext[1],
                    (i & 4 ? 1.0f : -1.0f) * t.ext[2], q[i]);
        static const BYTE kEdges[12][2] = {{0, 1}, {2, 3}, {4, 5}, {6, 7}, {0, 2}, {1, 3}, {4, 6}, {5, 7},
                                           {0, 4}, {1, 5}, {2, 6}, {3, 7}};
        for (const auto &e : kEdges) DvLine(dl, c, q[e[0]], q[e[1]], colour, thick);
        DvPoint(t.pos, rows, 0.0f, 0.0f, t.ext[2], top);
    } else {                                  // sphere: world-axis great circles, 24 segments each
        const float r = fabsf(t.radius);
        for (int plane = 0; plane < 3; ++plane) {
            int a = plane == 2 ? 1 : 0, b = plane == 0 ? 1 : 2;
            float prev[3] = {t.pos[0], t.pos[1], t.pos[2]};
            prev[a] += r;
            for (int s = 1; s <= 24; ++s) {
                float ang = s * (2.0f * 3.14159265f / 24.0f), p[3] = {t.pos[0], t.pos[1], t.pos[2]};
                p[a] += r * cosf(ang);
                p[b] += r * sinf(ang);
                DvLine(dl, c, prev, p, colour, thick);
                prev[0] = p[0]; prev[1] = p[1]; prev[2] = p[2];
            }
        }
        top[2] += r;
    }
    float q[3];
    DvToCam(c, top, q);
    *labelSeen = DvCamToScreen(c, q, labelAt);
}

// object names: does object id / name pass [Debug] NameMatch (cached per object id; the cache is cleared on a change)
bool DvNameMatches(int id, const char *name) {
    if (id > 0 && id < 4096 && g_dvNameHit[id]) return g_dvNameHit[id] == 1;
    bool hit = !g_dvNameMatch[0];
    if (!hit) {
        char low[64], list[sizeof(g_dvNameMatch)];
        strncpy_s(low, sizeof(low), name, _TRUNCATE);
        _strlwr_s(low, sizeof(low));
        strncpy_s(list, sizeof(list), g_dvNameMatch, _TRUNCATE);
        _strlwr_s(list, sizeof(list));
        char *context = nullptr;
        for (char *part = strtok_s(list, ", ", &context); part && !hit; part = strtok_s(nullptr, ", ", &context))
            hit = !strcmp(part, "*") || strstr(low, part) != nullptr;
    }
    if (id > 0 && id < 4096) g_dvNameHit[id] = hit ? 1 : 2;
    return hit;
}
struct DvName { DWORD inst; float pos[3], dist2; };
DvName g_dvNames[65];
// every instance (also Lara) whose object name matches, the nearest to the camera first (also from high above while
// flying), at most [Debug] NameMax within NameRadius; text size NameScale, colour NameColour
void DvDrawNames(ImDrawList *dl, const DvCam &c, char *state, size_t stateSize, size_t *used) {
    int count = 0, found = 0, walked = 0;
    const float r2 = g_dvNameRadius * g_dvNameRadius;
    DWORD inst = 0;
    ReadDword(kFirstInstance, &inst);
    for (int guard = 0; inst && guard < 4096; ++guard, ++walked) {
        DWORD next = 0, object = 0, oid = 0;
        float p[3], d2 = 0.0f;
        if (ReadDword(inst + 0x10, &object) && object && ReadDword(object + 0x14, &oid) &&
            ReadFloats(inst + kInstancePosition, p, 3) && DvFinite(p, 3)) {
            int id = static_cast<int>(oid & 0xffff);
            bool hit = false;
            if (id > 0 && id < 4096 && g_dvNameHit[id]) hit = g_dvNameHit[id] == 1;
            else {
                char name[64];
                hit = ObjectName(id, name, sizeof(name)) && DvNameMatches(id, name);
            }
            if (hit) {
                ++found;
                if (DvVisible(c, p, 100.0f, &d2) && d2 <= r2) {
                    int at = count;
                    while (at > 0 && g_dvNames[at - 1].dist2 > d2) --at;
                    if (at < g_dvNameMax) {
                        int last = count < g_dvNameMax ? count : g_dvNameMax - 1;
                        for (int m = last; m > at; --m) g_dvNames[m] = g_dvNames[m - 1];
                        g_dvNames[at].inst = inst;
                        g_dvNames[at].pos[0] = p[0]; g_dvNames[at].pos[1] = p[1]; g_dvNames[at].pos[2] = p[2];
                        g_dvNames[at].dist2 = d2;
                        if (count < g_dvNameMax) ++count;
                    }
                }
            }
        }
        if (!ReadDword(inst + 8, &next)) break;
        inst = next;
    }
    ImFont *font = ImGui::GetFont();
    const float size = ImGui::GetFontSize() * g_dvNameScale;
    const ImU32 colour = IM_COL32((g_dvNameRgb >> 16) & 0xff, (g_dvNameRgb >> 8) & 0xff, g_dvNameRgb & 0xff, 255);
    int drawn = 0;
    for (int i = 0; i < count; ++i) {
        const DvName &d = g_dvNames[i];
        float q[3];
        ImVec2 at;
        DvToCam(c, d.pos, q);
        if (!DvCamToScreen(c, q, &at)) continue;
        DWORD object = 0, oid = 0, intro = 0;
        char name[64], line[96];
        ReadDword(d.inst + 0x10, &object);
        if (object) ReadDword(object + 0x14, &oid);
        if (!ObjectName(static_cast<int>(oid & 0xffff), name, sizeof(name))) Out(name, sizeof(name), "obj %lu", oid & 0xffff);
        ReadDword(d.inst + 0x58, &intro);
        if (g_dvNameIds) Out(line, sizeof(line), "%s %ld", name, static_cast<LONG>(intro));
        else Out(line, sizeof(line), "%s", name);
        ImVec2 s = font->CalcTextSizeA(size, FLT_MAX, 0.0f, line);
        ImVec2 box(at.x - s.x * 0.5f - 3.0f, at.y - s.y - 8.0f);
        dl->AddRectFilled(box, ImVec2(box.x + s.x + 6.0f, box.y + s.y + 2.0f), IM_COL32(0, 0, 0, 140), 3.0f);
        dl->AddCircleFilled(at, 2.5f, colour, 8);
        dl->AddText(font, size, ImVec2(box.x + 3.0f, box.y + 1.0f), colour, line);
        ++drawn;
    }
    g_dvListed[kDvNames] = found;
    g_dvDrawn[kDvNames] = drawn;
    LabelAdd(state, stateSize, used, "names %d drawn of %d matching '%s' (%d instances, radius %.0f, max %d); ", drawn, found,
             g_dvNameMatch[0] ? g_dvNameMatch : "*", walked, g_dvNameRadius, g_dvNameMax);
}

// Present, every frame while a 0.14 layer is on
void DrawDebugView() {
    char why[160];
    memset(g_dvDrawn, 0, sizeof(g_dvDrawn));
    memset(g_dvListed, 0, sizeof(g_dvListed));
    if (!g_debugEnabled) { Out(g_dvState, sizeof(g_dvState), "[Debug] Enabled=0"); return; }
    if (!g_dvBaseOk) { Out(g_dvState, sizeof(g_dvState), "pre-check failed: %s", g_dvBaseWhy); return; }
    if (!LabelWorldReady(why, sizeof(why))) { Out(g_dvState, sizeof(g_dvState), "waits: %s", why); return; }
    ImGuiIO &io = ImGui::GetIO();
    DvCam c;
    if (!ReadView(&c.v, io.DisplaySize.x, io.DisplaySize.y) || !ReadFloats(kLblMatrix, c.v.m, 16) || !DvFinite(c.v.m, 16)) {
        Out(g_dvState, sizeof(g_dvState), "camera matrix 0x%08lx / focal not readable", kLblMatrix);
        return;
    }
    float lx = sqrtf(c.v.m[0] * c.v.m[0] + c.v.m[4] * c.v.m[4] + c.v.m[8] * c.v.m[8]);
    float ly = sqrtf(c.v.m[1] * c.v.m[1] + c.v.m[5] * c.v.m[5] + c.v.m[9] * c.v.m[9]);
    if (!(lx > 1.0e-4f && ly > 1.0e-4f)) { Out(g_dvState, sizeof(g_dvState), "camera matrix degenerate"); return; }
    c.ux = 1.0f / lx;
    c.uy = 1.0f / ly;
    ImDrawList *dl = ImGui::GetBackgroundDrawList();
    size_t used = 0;
    g_dvState[0] = 0;
    // triggers
    DvCount k = {};
    g_dvTrigCount = 0;
    int boxes = 0, spheres = 0, quads = 0, labels = 0;
    if (g_dvTrgOk && DvAnyTrigger()) {
        DvCollect(c, true, &k);
        DvCollect(c, false, &k);
        for (int i = 0; i < g_dvTrigCount; ++i) {
            const DvTrig &t = g_dvTrig[i];
            ImVec2 at;
            bool seen = false;
            DvDrawTrig(dl, c, t, &at, &seen);
            ++g_dvDrawn[t.kind];
            if (t.plane) ++quads;
            else if (t.shape == 2) ++spheres;
            else if (t.shape == 1) ++boxes;
            if (g_dvOn[kDvTrgLabels] && seen && labels < g_dvLabelMax) {
                char name[64], line[112];
                DWORD intro = 0;
                if (DvNameKind(t.inst, name, sizeof(name)) == -2) Out(name, sizeof(name), "?");
                ReadDword(t.inst + 0x58, &intro);
                Out(line, sizeof(line), "%s %ld%s%s", name, static_cast<LONG>(intro), t.enabled ? "" : " (aus)",
                    t.plane ? (t.oneSided ? " E1" : " E2") : t.shape == 2 ? " K" : t.shape == 1 ? " B" : " ?");
                LabelDraw(dl, at, line, "", kDvLayers[t.kind].colour);
                ++labels;
            }
        }
        // the point the game tests: player +0x20 + (0, 0, 200)
        DWORD player = 0;
        float p[3];
        if (ReadDword(kPlayerPtr, &player) && player && ReadFloats(player + kInstancePosition, p, 3) && DvFinite(p, 3)) {
            p[2] += kDvTestLift;
            const ImU32 white = IM_COL32(255, 255, 255, 230);
            for (int a = 0; a < 3; ++a) {
                float p0[3] = {p[0], p[1], p[2]}, p1[3] = {p[0], p[1], p[2]};
                p0[a] -= 25.0f;
                p1[a] += 25.0f;
                DvLine(dl, c, p0, p1, white, 2.0f);
            }
        }
        LabelAdd(g_dvState, sizeof(g_dvState), &used, "triggers %d drawn (box %d, sphere %d, plane %d) of %d listed, "
                 "%d off-screen, %d beyond %.0f, %d capped at %d, %d disabled (dim), %d without data; ", g_dvTrigCount,
                 boxes, spheres, quads, k.listed, k.behind, k.far_, g_dvRadius,
                 k.listed - k.behind - k.far_ - g_dvTrigCount, g_dvTrgMax, k.disabled, k.noData);
    }
    // portals of every loaded stream unit
    if (g_dvPortalOk && g_dvOn[kDvPortals]) {
        int units = 0, portals = 0, drawn = 0;
        const ImU32 colour = kDvLayers[kDvPortals].colour;
        for (DWORD e = kStreamUnits; e < kStreamUnitsEnd && portals < 128; e += kStreamUnitSize) {
            DWORD state = 0, level = 0, terrain = 0, arr = 0;
            WORD count = 0;
            if (!ReadDword(e + 4, &state) || (state & 0xff) != 2) continue;
            if (!ReadDword(e + 8, &level) || !level || !ReadDword(level, &terrain) || !terrain ||
                !ReadWord(terrain + 2, &count) || count > 64 || !ReadDword(terrain + 4, &arr) || !arr)
                continue;
            ++units;
            char unit[48];
            if (!ReadString(e + 0xc, unit, sizeof(unit))) unit[0] = 0;
            for (DWORD i = 0; i < count && portals < 128; ++i) {
                DWORD p = arr + i * 0x100;
                float q[5][4], centre[3] = {0, 0, 0};
                if (!ReadFloats(p + 0xb0, &q[0][0], 20) || !DvFinite(&q[0][0], 20)) continue;
                ++portals;
                for (int a = 0; a < 4; ++a)
                    for (int b = 0; b < 3; ++b) centre[b] += q[a][b] * 0.25f;
                float dist2 = 0.0f;
                float extent = fabsf(q[0][0] - q[2][0]) + fabsf(q[0][1] - q[2][1]) + fabsf(q[0][2] - q[2][2]);
                if (!DvVisible(c, centre, extent, &dist2)) continue;
                bool any = false;
                for (int a = 0; a < 4; ++a) any |= DvLine(dl, c, q[a], q[(a + 1) & 3], colour, 3.0f);
                DvLine(dl, c, q[0], q[2], (colour & 0x00ffffff) | (120u << 24), 1.0f);
                DvLine(dl, c, q[1], q[3], (colour & 0x00ffffff) | (120u << 24), 1.0f);
                float tip[3] = {centre[0] + q[4][0] * 150.0f, centre[1] + q[4][1] * 150.0f, centre[2] + q[4][2] * 150.0f};
                DvLine(dl, c, centre, tip, colour, 2.0f);
                if (!any) continue;
                ++drawn;
                char name[48], line[112];
                if (!ReadString(p, name, sizeof(name))) name[0] = 0;
                float cq[3];
                ImVec2 at;
                DvToCam(c, centre, cq);
                if (DvCamToScreen(c, cq, &at)) {
                    Out(line, sizeof(line), "%s -> %s", unit, name);
                    LabelDraw(dl, at, line, "", colour);
                }
            }
        }
        g_dvListed[kDvPortals] = portals;
        g_dvDrawn[kDvPortals] = drawn;
        LabelAdd(g_dvState, sizeof(g_dvState), &used, "portals %d drawn of %d in %d loaded unit(s); ", drawn, portals, units);
    }
    // checkpoint objects (instances named *checkpoint*), the active one from the game data
    if (g_dvCpOk && g_dvOn[kDvCheckpoints]) {
        DWORD data = 0, active = 0xffffffff;
        WORD mode = 0;
        if (ReadDword(kDvGameData, &data) && data && ReadWord(data + 0x1f4, &mode)) ReadDword(data + (mode ? 0x114 : 0x90), &active);
        int count = 0, found = 0;
        DWORD inst = 0;
        ReadDword(kFirstInstance, &inst);
        for (int guard = 0; inst && guard < 4096; ++guard) {
            DWORD next = 0, object = 0, oid = 0;
            if (ReadDword(inst + 0x10, &object) && object && ReadDword(object + 0x14, &oid)) {
                int id = static_cast<int>(oid & 0xffff);
                int cached = id > 0 && id < 4096 ? g_dvNameKind[id] : 0;
                bool cp = cached == kDvCheckpoint + 1;
                if (!cached) {
                    char name[64];
                    cp = DvNameKind(inst, name, sizeof(name)) == kDvCheckpoint;
                }
                float p[3], d2 = 0.0f;
                if (cp && ReadFloats(inst + kInstancePosition, p, 3) && DvFinite(p, 3)) {
                    ++found;
                    if (DvVisible(c, p, 300.0f, &d2)) {
                        int at = count;
                        while (at > 0 && g_dvCp[at - 1].dist2 > d2) --at;
                        if (at < 32) {
                            int last = count < 32 ? count : 31;
                            for (int m = last; m > at; --m) g_dvCp[m] = g_dvCp[m - 1];
                            g_dvCp[at].inst = inst;
                            g_dvCp[at].pos[0] = p[0]; g_dvCp[at].pos[1] = p[1]; g_dvCp[at].pos[2] = p[2];
                            g_dvCp[at].dist2 = d2;
                            if (count < 32) ++count;
                        }
                    }
                }
            }
            if (!ReadDword(inst + 8, &next)) break;
            inst = next;
        }
        int activeSeen = 0;
        for (int i = 0; i < count; ++i) {
            const DvMark &m = g_dvCp[i];
            DWORD intro = 0;
            ReadDword(m.inst + 0x58, &intro);
            bool isActive = intro == active;
            ImU32 colour = isActive ? IM_COL32(230, 255, 60, 255) : kDvLayers[kDvCheckpoints].colour;
            float thick = isActive ? 3.0f : 2.0f, top[3] = {m.pos[0], m.pos[1], m.pos[2] + 250.0f};
            DvLine(dl, c, m.pos, top, colour, thick);
            float d[4][3];
            const float s[4][2] = {{60, 0}, {0, 60}, {-60, 0}, {0, -60}};
            for (int a = 0; a < 4; ++a) {
                d[a][0] = top[0] + s[a][0];
                d[a][1] = top[1] + s[a][1];
                d[a][2] = top[2];
            }
            float up[3] = {top[0], top[1], top[2] + 60.0f}, down[3] = {top[0], top[1], top[2] - 60.0f};
            for (int a = 0; a < 4; ++a) {
                DvLine(dl, c, d[a], up, colour, thick);
                DvLine(dl, c, d[a], down, colour, thick);
            }
            float q[3];
            ImVec2 at;
            DvToCam(c, up, q);
            if (DvCamToScreen(c, q, &at)) {
                char line[64];
                Out(line, sizeof(line), "CP %ld%s", static_cast<LONG>(intro), isActive ? " AKTIV" : "");
                LabelDraw(dl, at, line, "", colour);
            }
            if (isActive) ++activeSeen;
        }
        g_dvListed[kDvCheckpoints] = found;
        g_dvDrawn[kDvCheckpoints] = count;
        LabelAdd(g_dvState, sizeof(g_dvState), &used, "checkpoints %d drawn of %d (active id %ld%s); ", count, found,
                 static_cast<LONG>(active), activeSeen ? ", drawn" : "");
    }
    if (g_dvBaseOk && g_dvOn[kDvNames]) DvDrawNames(dl, c, g_dvState, sizeof(g_dvState), &used);
    if (!used) Out(g_dvState, sizeof(g_dvState), "nothing switched on that this frame can draw");
    if (InterlockedExchange(&g_dvLogPending, 0)) Log(1, "0.14 debug view drawn: %s", g_dvState);   // once per switch
}

// the legend (foreground, top right): every layer that is on with its colour and drawn / listed
void DrawDebugLegend() {
    ImGuiIO &io = ImGui::GetIO();
    ImDrawList *dl = ImGui::GetForegroundDrawList();
    const float fs = ImGui::GetFontSize(), w = 330.0f;
    char lines[kDvCount + 2][112];
    ImU32 colours[kDvCount + 2];
    int n = 0;
    Out(lines[n], sizeof(lines[n]), "TruMenu 0.14 Debug-Ansicht (gezeichnet / gefunden)");
    colours[n++] = IM_COL32(235, 235, 235, 255);
    for (int i = 0; i < kDvCount; ++i) {
        if (!g_dvOn[i] || i == kDvLegend) continue;
        if (i == kDvTrgLabels) Out(lines[n], sizeof(lines[n]), "%s / %s", kDvLayers[i].de, kDvLayers[i].en);
        else Out(lines[n], sizeof(lines[n]), "%s / %s: %d / %d", kDvLayers[i].de, kDvLayers[i].en, g_dvDrawn[i],
                 g_dvListed[i]);
        colours[n++] = kDvLayers[i].colour;
    }
    if (DvAnyTrigger()) {
        Out(lines[n], sizeof(lines[n]), "Testpunkt (Lara +200) / test point; blass = aus / disabled");
        colours[n++] = IM_COL32(255, 255, 255, 230);
    }
    ImVec2 at(io.DisplaySize.x - w - 12.0f, 40.0f);
    dl->AddRectFilled(at, ImVec2(at.x + w, at.y + n * (fs + 3.0f) + 8.0f), IM_COL32(0, 0, 0, 160), 4.0f);
    for (int i = 0; i < n; ++i) {
        ImVec2 p(at.x + 8.0f, at.y + 4.0f + i * (fs + 3.0f));
        if (i) dl->AddRectFilled(ImVec2(p.x, p.y + 3.0f), ImVec2(p.x + 10.0f, p.y + fs - 3.0f), colours[i]);
        dl->AddText(ImVec2(p.x + (i ? 16.0f : 0.0f), p.y), colours[i], lines[i]);
    }
}

void ValDvStatus(char *o, size_t n) {
    char on[200] = "";
    size_t used = 0;
    for (int i = 0; i < kDvCount; ++i)
        if (g_dvOn[i]) LabelAdd(on, sizeof(on), &used, "%s%s", used ? "," : "", kDvLayers[i].name);
    Out(o, n, "[Debug] Enabled %d; checks: triggers %s, portals %s, checkpoints %s; on: %s; last frame: %s", g_debugEnabled,
        g_dvTrgWhy, g_dvPortalWhy, g_dvCpWhy, used ? on : "-", DvAnyOn() ? g_dvState : "off");
}
void ValDvShow(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    for (int i = 0; i < kDvCount; ++i)
        LabelAdd(o, n, &used, "%s%s %d", i ? ", " : "", kDvLayers[i].name, g_dvOn[i] ? 1 : 0);
}
// dbg.show <layer> [0|1]
bool RunDvShow(const char *arg, char *o, size_t n) {
    char buf[64];
    strncpy_s(buf, sizeof(buf), arg ? arg : "", _TRUNCATE);
    char *context = nullptr;
    char *name = strtok_s(buf, " ", &context);
    char *value = name ? strtok_s(nullptr, " ", &context) : nullptr;
    int i = DvFind(name);
    if (i < 0) {
        Out(o, n, "usage: dbg.show <layer> [0|1] - death, fire, checkpoint, water, sound, volume, plane, unknown, portals, "
            "checkpoints, trglabels, legend, names");
        return false;
    }
    return DvSet(i, BoolArg(value ? value : "", g_dvOn[i] != 0), ShotSource("dbg.show"), o, n);
}
// one layer as a bool item (dbg.portals / dbg.checkpoints / dbg.legend)
bool DvRunOne(int layer, const char *item, const char *arg, char *o, size_t n) {
    return DvSet(layer, BoolArg(arg, g_dvOn[layer] != 0), ShotSource(item), o, n);
}
void ValDvPortals(char *o, size_t n) { Out(o, n, "%d (%d drawn of %d)", g_dvOn[kDvPortals] ? 1 : 0, g_dvDrawn[kDvPortals], g_dvListed[kDvPortals]); }
bool RunDvPortals(const char *arg, char *o, size_t n) { return DvRunOne(kDvPortals, "dbg.portals", arg, o, n); }
void ValDvCheckpoints(char *o, size_t n) {
    Out(o, n, "%d (%d drawn of %d)", g_dvOn[kDvCheckpoints] ? 1 : 0, g_dvDrawn[kDvCheckpoints], g_dvListed[kDvCheckpoints]);
}
bool RunDvCheckpoints(const char *arg, char *o, size_t n) { return DvRunOne(kDvCheckpoints, "dbg.checkpoints", arg, o, n); }
void ValDvLegend(char *o, size_t n) { Out(o, n, "%d", g_dvOn[kDvLegend] ? 1 : 0); }
bool RunDvLegend(const char *arg, char *o, size_t n) { return DvRunOne(kDvLegend, "dbg.legend", arg, o, n); }
// object names: dbg.names (layer), dbg.namefilter <list|*>, dbg.namecolour <preset|RRGGBB>, dbg.namesize <0.5..3>
void ValDvNames(char *o, size_t n) {
    Out(o, n, "%d (%d drawn of %d; filter '%s', radius %.0f, max %d, size %.2f, colour %06lX, ids %d)",
        g_dvOn[kDvNames] ? 1 : 0, g_dvDrawn[kDvNames], g_dvListed[kDvNames], g_dvNameMatch[0] ? g_dvNameMatch : "*",
        g_dvNameRadius, g_dvNameMax, g_dvNameScale, g_dvNameRgb, g_dvNameIds);
}
bool RunDvNames(const char *arg, char *o, size_t n) { return DvRunOne(kDvNames, "dbg.names", arg, o, n); }
void ValDvNameFilter(char *o, size_t n) { Out(o, n, "%s", g_dvNameMatch[0] ? g_dvNameMatch : "*"); }
bool RunDvNameFilter(const char *arg, char *o, size_t n) {
    char v[sizeof(g_dvNameMatch)];
    strncpy_s(v, sizeof(v), arg ? arg : "", _TRUNCATE);
    DvTrim(v);
    bool okChars = v[0] != 0;
    for (const char *p = v; *p; ++p)
        if (!(isalnum(static_cast<unsigned char>(*p)) || *p == '_' || *p == '*' || *p == ',' || *p == ' ')) okChars = false;
    if (!okChars) {
        Out(o, n, "usage: dbg.namefilter <comma list of name parts a-z 0-9 _ | *> (* = every instance); now '%s'",
            g_dvNameMatch[0] ? g_dvNameMatch : "*");
        return false;
    }
    strncpy_s(g_dvNameMatch, sizeof(g_dvNameMatch), strcmp(v, "*") ? v : "", _TRUNCATE);
    memset(g_dvNameHit, 0, sizeof(g_dvNameHit));
    if (g_dvPersist && g_iniPath[0]) WritePrivateProfileStringA("Debug", "NameMatch", g_dvNameMatch, g_iniPath);
    Log(1, "dbg.namefilter '%s' (src=%s)", g_dvNameMatch[0] ? g_dvNameMatch : "*", ShotSource("dbg.namefilter"));
    Out(o, n, "dbg.namefilter %s", g_dvNameMatch[0] ? g_dvNameMatch : "*");
    return true;
}
void ValDvNameColour(char *o, size_t n) { Out(o, n, "%06lX", g_dvNameRgb); }
bool RunDvNameColour(const char *arg, char *o, size_t n) {
    char v[32];
    strncpy_s(v, sizeof(v), arg ? arg : "", _TRUNCATE);
    DvTrim(v);
    DWORD rgb = 0xffffffff;
    for (const DvColourPreset &c : kDvNameColours)
        if (!_stricmp(v, c.name) || !_stricmp(v, c.de)) rgb = c.rgb;
    if (rgb == 0xffffffff && strlen(v) == 6 && strspn(v, "0123456789abcdefABCDEF") == 6) rgb = strtoul(v, nullptr, 16);
    if (rgb == 0xffffffff) {
        Out(o, n, "usage: dbg.namecolour white|yellow|cyan|magenta|RRGGBB; now %06lX", g_dvNameRgb);
        return false;
    }
    g_dvNameRgb = rgb;
    char text[8];
    Out(text, sizeof(text), "%06lX", rgb);
    if (g_dvPersist && g_iniPath[0]) WritePrivateProfileStringA("Debug", "NameColour", text, g_iniPath);
    Log(1, "dbg.namecolour %s (src=%s)", text, ShotSource("dbg.namecolour"));
    Out(o, n, "dbg.namecolour %s", text);
    return true;
}
void ValDvNameSize(char *o, size_t n) { Out(o, n, "%.2f", g_dvNameScale); }
bool RunDvNameSize(const char *arg, char *o, size_t n) {
    float v = arg && arg[0] ? static_cast<float>(atof(arg)) : 0.0f;
    if (!(v >= 0.5f && v <= 3.0f)) { Out(o, n, "usage: dbg.namesize <0.5 .. 3> (font size factor); now %.2f", g_dvNameScale); return false; }
    g_dvNameScale = v;
    char text[16];
    Out(text, sizeof(text), "%.2f", v);
    if (g_dvPersist && g_iniPath[0]) WritePrivateProfileStringA("Debug", "NameScale", text, g_iniPath);
    Log(1, "dbg.namesize %s (src=%s)", text, ShotSource("dbg.namesize"));
    Out(o, n, "dbg.namesize %s", text);
    return true;
}
// dbg.triggers: every trigger kind together
void ValDvTriggers(char *o, size_t n) {
    int drawn = 0, listed = 0;
    for (int i = 0; i < kDvKinds; ++i) { drawn += g_dvDrawn[i]; listed += g_dvListed[i]; }
    Out(o, n, "%d (%d drawn of %d)", DvAnyTrigger() ? 1 : 0, drawn, listed);
}
bool RunDvTriggers(const char *arg, char *o, size_t n) {
    bool on = BoolArg(arg, DvAnyTrigger());
    const char *src = ShotSource("dbg.triggers");
    if (!g_debugEnabled) { Out(o, n, "debug drawing off ([Debug] Enabled=0)"); return false; }
    if (!g_dvTrgOk) {
        Out(o, n, "disabled: pre-check failed (%s)", g_dvTrgWhy);
        Log(1, "dbg.triggers %d refused - %s (src=%s)", on ? 1 : 0, o, src);
        return false;
    }
    for (int i = 0; i < kDvKinds; ++i) {
        InterlockedExchange(&g_dvOn[i], on ? 1 : 0);
        DvPersistKey(kDvLayers[i].key, on);
    }
    InterlockedExchange(&g_dvLogPending, 1);
    Log(1, "dbg.triggers %d (all %d kinds, src=%s)", on ? 1 : 0, static_cast<int>(kDvKinds), src);
    Out(o, n, "dbg.triggers %d", on ? 1 : 0);
    return true;
}

// dbg.view: the master - on = every 0.14 layer + dbg.labels + draw.markup + the [Debug] ViewNav switches; off = all of
// them off (nav.off); each one stays switchable alone afterwards. Value = 1 while any of them is on.
bool DvViewAny() {
    if (DvAnyOn() || g_lblOn || g_drawMarkup) return true;
    for (int i = 0; i < kNavCount; ++i)
        if (NavByteOn(i)) return true;
    return false;
}
void ValDvView(char *o, size_t n) {
    int layers = 0, nav = 0;
    for (int i = 0; i < kDvCount; ++i) layers += g_dvOn[i] ? 1 : 0;
    for (int i = 0; i < kNavCount; ++i) nav += NavByteOn(i) ? 1 : 0;
    Out(o, n, "%d (%d / %d layers, labels %d, markup %d, %d nav switch(es))", DvViewAny() ? 1 : 0, layers,
        static_cast<int>(kDvCount), g_lblOn ? 1 : 0, g_drawMarkup ? 1 : 0, nav);
}
bool RunDvView(const char *arg, char *o, size_t n) {
    if (!g_debugEnabled) { Out(o, n, "debug drawing off ([Debug] Enabled=0)"); return false; }
    bool on = BoolArg(arg, DvViewAny());
    const char *src = ShotSource("dbg.view");
    int layers = 0;
    for (int i = 0; i < kDvCount; ++i) {
        const char *why = "";
        if (!DvLayerOk(i, &why)) continue;
        InterlockedExchange(&g_dvOn[i], on ? 1 : 0);
        DvPersistKey(kDvLayers[i].key, on);
        ++layers;
    }
    InterlockedExchange(&g_dvLogPending, 1);
    char lbl[160] = "not verified", mk[96] = "not verified", nav[400] = "", one[300];
    if (g_lblOk) {
        RunLabels(on ? "1" : "0", lbl, sizeof(lbl));
        DvPersistKey("Labels", on);
    }
    if (g_drawOk) {
        RunDrawMarkup(on ? "1" : "0", mk, sizeof(mk));
        DvPersistKey("Markup", on);
    }
    size_t used = 0;
    if (on) {
        char copy[sizeof(g_dvViewNav)];
        strncpy_s(copy, sizeof(copy), g_dvViewNav, _TRUNCATE);
        char *context = nullptr;
        for (char *name = strtok_s(copy, ", ", &context); name; name = strtok_s(nullptr, ", ", &context)) {
            char cmd[64];
            Out(cmd, sizeof(cmd), "%s 1", name);
            bool ok = RunNavDraw(cmd, one, sizeof(one));
            LabelAdd(nav, sizeof(nav), &used, "%s%s %s", used ? ", " : "", name, ok ? "on" : "refused");
        }
    } else {
        bool ok = RunNavOff("", one, sizeof(one));
        LabelAdd(nav, sizeof(nav), &used, "nav.off %s", ok ? "ok" : one);
    }
    Log(1, "dbg.view %d: %d layer(s), labels: %s, markup: %s, nav: %s (src=%s)", on ? 1 : 0, layers, lbl, mk,
        used ? nav : "-", src);
    Out(o, n, "dbg.view %d: %d layer(s), labels %s, markup %s, nav %s", on ? 1 : 0, layers, lbl, mk, used ? nav : "-");
    return true;
}

// ring: why a dbg.* entry (not dbg.labels) is greyed out ("" = usable; outside a level it may be switched)
const char *DvRadWhy(const char *id, const char *arg) {
    if (!_stricmp(id, "dbg.status")) return "";
    if (!g_debugEnabled) return "debug drawing off ([Debug] Enabled=0)";
    const char *why = "";
    if (!_stricmp(id, "dbg.show")) {
        int i = DvFind(arg);
        if (i < 0) return "unknown layer";
        return DvLayerOk(i, &why) ? "" : why;
    }
    if (!_stricmp(id, "dbg.triggers")) return g_dvTrgOk ? "" : g_dvTrgWhy;
    if (!_stricmp(id, "dbg.portals")) return g_dvPortalOk ? "" : g_dvPortalWhy;
    if (!_stricmp(id, "dbg.checkpoints")) return g_dvCpOk ? "" : g_dvCpWhy;
    if (!_strnicmp(id, "dbg.name", 8)) return g_dvBaseOk ? "" : g_dvBaseWhy;   // dbg.names / namefilter / colour / size
    return "";
}

// menu page "Debug view": the same groups as the ring Spieler / Debug (master, level data, AI, Lara, display)
void PageDebugView() {
    char o[400];
    if (!g_debugEnabled) {
        ImGui::TextWrapped("[Debug] Enabled=0 in TruMenu.ini - the debug view is off (read-only drawing, set Enabled=1).");
        return;
    }
    bool all = DvViewAny();
    if (TmCheckbox("Everything / Alles an / aus  [dbg.view]###dvall", &all)) RunDvView(all ? "1" : "0", o, sizeof(o));
    ImGui::TextWrapped("last frame: %s", DvAnyOn() ? g_dvState : "off");
    if (ImGui::TreeNodeEx("Level data / Leveldaten###dvlevel", ImGuiTreeNodeFlags_DefaultOpen)) {
        if (!g_dvTrgOk) ImGui::TextWrapped("triggers off: %s", g_dvTrgWhy);
        bool trg = DvAnyTrigger();
        if (TmCheckbox("all triggers / Trigger alle  [dbg.triggers]###dvtrg", &trg)) RunDvTriggers(trg ? "1" : "0", o, sizeof(o));
        const int order[] = {kDvPortals, kDvCheckpoints, kDvDeath, kDvFire, kDvCheckpoint, kDvWater, kDvSound, kDvVolume,
                             kDvPlane, kDvUnknown, kDvTrgLabels};
        for (int i : order) {
            const DvLayerDef &d = kDvLayers[i];
            ImVec4 col = ImGui::ColorConvertU32ToFloat4(d.colour);
            char id[32], label[128];
            Out(id, sizeof(id), "##dvc%d", i);
            ImGui::ColorButton(id, col, ImGuiColorEditFlags_NoTooltip, ImVec2(14.0f, 14.0f));
            ImGui::SameLine();
            bool v = g_dvOn[i] != 0;
            Out(label, sizeof(label), "%s / %s  [dbg.show %s]  %d / %d###dvl%d", d.en, d.de, d.name, g_dvDrawn[i],
                g_dvListed[i], i);
            if (TmCheckbox(label, &v)) DvSet(i, v, "menu", o, sizeof(o));
        }
        ImGui::SliderInt("max triggers / frame  [Debug] TriggerMax", &g_dvTrgMax, 1, 256);
        ImGui::SliderFloat("radius from the camera  [Debug] TriggerRadius", &g_dvRadius, 500.0f, 200000.0f, "%.0f");
        ImGui::SliderInt("trigger names / frame  [Debug] TriggerLabelMax", &g_dvLabelMax, 0, 64);
        ImGui::TreePop();
    }
    if (ImGui::TreeNodeEx("AI / KI###dvai", ImGuiTreeNodeFlags_DefaultOpen)) {
        for (int i = 0; i < kNavCount; ++i) {
            bool v = NavByteOn(i);
            char label[128], cmd[64];
            Out(label, sizeof(label), "%s  [nav.draw]%s###dvn%d", kNavSwitches[i].name, g_navSwOk[i] ? "" : "  (off)", i);
            if (TmCheckbox(label, &v)) {
                Out(cmd, sizeof(cmd), "%s %d", kNavSwitches[i].name, v ? 1 : 0);
                RunNavDraw(cmd, o, sizeof(o));
            }
        }
        bool mask = g_navMaskSet;
        if (TmCheckbox("every layer / Alle Ebenen  [nav.mask]###dvmask", &mask)) RunNavMask(mask ? "1" : "0", o, sizeof(o));
        bool lbl = g_lblOn != 0;
        if (TmCheckbox("Thrall-Labels  [dbg.labels]###dvlbl", &lbl)) {
            RunLabels(lbl ? "1" : "0", o, sizeof(o));
            DvPersistKey("Labels", lbl);
        }
        ImGui::TreePop();
    }
    if (ImGui::TreeNodeEx("Object names / Objektnamen###dvnames", ImGuiTreeNodeFlags_DefaultOpen)) {
        if (!g_dvBaseOk) ImGui::TextWrapped("object names off: %s", g_dvBaseWhy);
        bool v = g_dvOn[kDvNames] != 0;
        char label[96];
        Out(label, sizeof(label), "object names / Objektnamen  [dbg.names]  %d / %d###dvnm", g_dvDrawn[kDvNames],
            g_dvListed[kDvNames]);
        if (TmCheckbox(label, &v)) DvSet(kDvNames, v, "menu", o, sizeof(o));
        static char filter[sizeof(g_dvNameMatch)] = "";
        static bool filterInit = false;
        if (!filterInit) { strncpy_s(filter, sizeof(filter), g_dvNameMatch[0] ? g_dvNameMatch : "*", _TRUNCATE); filterInit = true; }
        if (ImGui::InputText("filter (parts, * = all)  [dbg.namefilter]###dvnf", filter, sizeof(filter),
                             ImGuiInputTextFlags_EnterReturnsTrue))
            RunDvNameFilter(filter, o, sizeof(o));
        if (TmButton("all / alle###dvnfall")) { RunDvNameFilter("*", o, sizeof(o)); strcpy_s(filter, sizeof(filter), "*"); }
        ImGui::SameLine();
        if (TmButton("Thralls###dvnfthr")) { RunDvNameFilter("thrall", o, sizeof(o)); strcpy_s(filter, sizeof(filter), "thrall"); }
        ImGui::SameLine();
        if (TmButton("triggers###dvnftrg")) { RunDvNameFilter("trigger,volume,plane", o, sizeof(o)); strcpy_s(filter, sizeof(filter), "trigger,volume,plane"); }
        ImGui::SliderFloat("radius from the camera  [Debug] NameRadius", &g_dvNameRadius, 100.0f, 200000.0f, "%.0f");
        ImGui::SliderInt("max names / frame  [Debug] NameMax", &g_dvNameMax, 1, 64);
        // size / colour follow the widget at once; the log line (and Persist) once the edit is done
        ImGui::SliderFloat("font size  [dbg.namesize]###dvnsz", &g_dvNameScale, 0.5f, 3.0f, "%.2fx");
        if (ImGui::IsItemDeactivatedAfterEdit()) { char a[16]; Out(a, sizeof(a), "%.2f", g_dvNameScale); RunDvNameSize(a, o, sizeof(o)); }
        float col[3] = {((g_dvNameRgb >> 16) & 0xff) / 255.0f, ((g_dvNameRgb >> 8) & 0xff) / 255.0f, (g_dvNameRgb & 0xff) / 255.0f};
        if (ImGui::ColorEdit3("colour  [dbg.namecolour]###dvncol", col))
            g_dvNameRgb = (static_cast<DWORD>(col[0] * 255.0f + 0.5f) << 16) | (static_cast<DWORD>(col[1] * 255.0f + 0.5f) << 8) |
                          static_cast<DWORD>(col[2] * 255.0f + 0.5f);
        if (ImGui::IsItemDeactivatedAfterEdit()) { char a[16]; Out(a, sizeof(a), "%06lX", g_dvNameRgb); RunDvNameColour(a, o, sizeof(o)); }
        for (const DvColourPreset &c : kDvNameColours) {
            char b[48];
            Out(b, sizeof(b), "%s / %s###dvnc%s", c.name, c.de, c.name);
            if (TmButton(b)) RunDvNameColour(c.name, o, sizeof(o));
            ImGui::SameLine();
        }
        ImGui::NewLine();
        bool ids = g_dvNameIds != 0;
        if (TmCheckbox("intro id after the name  [Debug] NameIds###dvnid", &ids)) {
            g_dvNameIds = ids ? 1 : 0;
            DvPersistKey("NameIds", ids);
        }
        ImGui::TreePop();
    }
    if (ImGui::TreeNodeEx("Lara###dvlara", ImGuiTreeNodeFlags_DefaultOpen)) {
        bool mk = g_drawMarkup != 0, ledges = g_drawLedges != 0;
        if (TmCheckbox("markup / Markup  [draw.markup]###dvmk", &mk)) {
            RunDrawMarkup(mk ? "1" : "0", o, sizeof(o));
            DvPersistKey("Markup", mk);
        }
        if (TmCheckbox("ledges only / Nur Kanten  [draw.ledges]###dvledge", &ledges)) RunDrawLedges(ledges ? "1" : "0", o, sizeof(o));
        ImGui::TextWrapped("The white cross with the triggers is the point the game tests: Lara +0x20 + 200 up.");
        ImGui::TreePop();
    }
    if (ImGui::TreeNodeEx("Display / Anzeige###dvdisplay", ImGuiTreeNodeFlags_DefaultOpen)) {
        bool v = g_dvOn[kDvLegend] != 0;
        if (TmCheckbox("legend / Legende  [dbg.legend]###dvleg", &v)) DvSet(kDvLegend, v, "menu", o, sizeof(o));
        ImGui::TextWrapped("[Debug] Persist %d: %s", g_dvPersist, g_dvPersist ? "every switch here is written to TruMenu.ini"
                           " at once (Set-TruMenu.ps1 then keeps the INI as owner-edited)" : "switches last until the "
                           "game ends; start values = the [Debug] keys");
        ImGui::TreePop();
    }
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
// 0.10.1: 128 rows (was 64) - Invoke-TruTestRun.ps1 sends the profile rows with test.step / test.add / test.toggle and
// the radial profiles have more than 64 (regress_shadowlara_50l_radial 77, _radial2 94: rows 65+ got "list full")
const int kTestMax = 128;
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

// 0.8: the row parser of TruMenu.tests.txt, shared with the regression lists (same format); returns the row count.
// 0.8.1: an optional 9th column "shortcut" (regression lists: ';'-separated commands that prepare the situation, an
// optional first element "#title") goes into shortcuts[row] when given
const int kShortcutLen = 320;
int ParseTestRows(FILE *f, TestRow *rows, int max, char (*shortcuts)[kShortcutLen] = nullptr) {
    char line[1400];
    int count = 0;
    while (count < max && fgets(line, sizeof(line), f)) {
        size_t len = strlen(line);
        while (len && (line[len - 1] == '\n' || line[len - 1] == '\r')) line[--len] = 0;
        if (!line[0] || line[0] == '#') continue;
        char *field[9] = {line, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr};
        for (int k = 1; k < 9; ++k) {
            char *tab = field[k - 1] ? strchr(field[k - 1], '\t') : nullptr;
            if (!tab) break;
            *tab = 0;
            field[k] = tab + 1;
        }
        if (!field[0][0]) continue;
        if (shortcuts) strncpy_s(shortcuts[count], kShortcutLen, field[8] ? field[8] : "", _TRUNCATE);
        TestRow &t = rows[count++];
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
    return count;
}

void TestLoad() {
    FILE *f = nullptr;
    if (!g_testPath[0] || fopen_s(&f, g_testPath, "rb") != 0 || !f) return;
    EnterCriticalSection(&g_testLock);
    g_testCount = ParseTestRows(f, g_tests, kTestMax);
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
        FlowOnToggle(id, state);                    // 0.11: toggle:<id> counters (an event only)
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

// ======================================================================================================================
// 0.8 Regression page: fixed lists next to the ASI (TruMenu.regress_dlc1.txt / TruMenu.regress_dlc2.txt, copied by
// Set-TruMenu.ps1 from tests\regress\*.txt; same row format as TruMenu.tests.txt). The lists themselves are never
// written: every mark / note of a session is appended to TruMenu.regress_results.txt next to the ASI:
//   "#session<TAB>start<TAB>plugin versions<TAB>sha256 of the loaded Tru*.asi"   once per session, before its first row
//   "time<TAB>list<TAB>id<TAB>state<TAB>note<TAB>session start"                  one line per mark / note
// The rows start open at every game start (and at regress.load); the results file keeps the history.
// ======================================================================================================================
const int kRegLists = 2;
const char *const kRegNames[kRegLists] = {"dlc1", "dlc2"};
TestRow g_reg[kRegLists][kTestMax];
char g_regShortcut[kRegLists][kTestMax][kShortcutLen];   // 0.8.1 column 9 (g_testLock)
int g_regCount[kRegLists] = {0, 0};
bool g_regFound[kRegLists] = {false, false};
int g_regSel = 2;                            // 0 dlc1, 1 dlc2, 2 all (render thread + items; int writes)
char g_regPath[kRegLists][MAX_PATH];
char g_regResultsPath[MAX_PATH] = "";
char g_regSession[24] = "";                  // session start "yyyy-mm-dd hh:mm:ss"
bool g_regSessionWritten = false;            // g_testLock held
char g_regVersions[2048] = "";               // plugin versions (computed once, RegVersions)
char g_regHashes[2048] = "";                 // sha256 of the loaded Tru*.asi files
volatile LONG g_regHashState = 0;            // 0 not yet, 1 computing, 2 done

// ---- SHA-256 (FIPS 180-4), small and table driven: the results name the exact plugin builds like the install scripts
struct Sha256 { DWORD h[8]; BYTE buf[64]; DWORD used; unsigned long long bits; };
const DWORD kShaK[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01,
    0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08,
    0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
DWORD Ror(DWORD x, int r) { return (x >> r) | (x << (32 - r)); }
void ShaBlock(Sha256 &s, const BYTE *p) {
    DWORD w[64];
    for (int i = 0; i < 16; ++i)
        w[i] = (static_cast<DWORD>(p[4 * i]) << 24) | (static_cast<DWORD>(p[4 * i + 1]) << 16) |
               (static_cast<DWORD>(p[4 * i + 2]) << 8) | p[4 * i + 3];
    for (int i = 16; i < 64; ++i) {
        DWORD s0 = Ror(w[i - 15], 7) ^ Ror(w[i - 15], 18) ^ (w[i - 15] >> 3);
        DWORD s1 = Ror(w[i - 2], 17) ^ Ror(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    DWORD a = s.h[0], b = s.h[1], c = s.h[2], d = s.h[3], e = s.h[4], f = s.h[5], g = s.h[6], h = s.h[7];
    for (int i = 0; i < 64; ++i) {
        DWORD t1 = h + (Ror(e, 6) ^ Ror(e, 11) ^ Ror(e, 25)) + ((e & f) ^ (~e & g)) + kShaK[i] + w[i];
        DWORD t2 = (Ror(a, 2) ^ Ror(a, 13) ^ Ror(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
        h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
    }
    s.h[0] += a; s.h[1] += b; s.h[2] += c; s.h[3] += d; s.h[4] += e; s.h[5] += f; s.h[6] += g; s.h[7] += h;
}
void ShaInit(Sha256 &s) {
    const DWORD init[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    memcpy(s.h, init, sizeof(init));
    s.used = 0;
    s.bits = 0;
}
void ShaAdd(Sha256 &s, const BYTE *p, size_t n) {
    s.bits += static_cast<unsigned long long>(n) * 8;
    while (n) {
        size_t take = 64 - s.used < n ? 64 - s.used : n;
        memcpy(s.buf + s.used, p, take);
        s.used += static_cast<DWORD>(take);
        p += take;
        n -= take;
        if (s.used == 64) { ShaBlock(s, s.buf); s.used = 0; }
    }
}
void ShaHex(Sha256 &s, char *out) {        // out: 65 bytes
    unsigned long long bits = s.bits;
    BYTE pad = 0x80, zero = 0;
    ShaAdd(s, &pad, 1);
    while (s.used != 56) ShaAdd(s, &zero, 1);
    BYTE len[8];
    for (int i = 0; i < 8; ++i) len[i] = static_cast<BYTE>(bits >> (56 - 8 * i));
    ShaAdd(s, len, 8);
    for (int i = 0; i < 8; ++i) _snprintf_s(out + 8 * i, 65 - 8 * i, _TRUNCATE, "%08lx", s.h[i]);
}
bool ShaFile(const char *path, char *out) {
    HANDLE f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                           OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) return false;
    Sha256 s;
    ShaInit(s);
    static BYTE chunk[65536];
    DWORD got = 0;
    bool ok = true;
    while (ok && (ok = ReadFile(f, chunk, sizeof(chunk), &got, nullptr) != 0) && got) ShaAdd(s, chunk, got);
    CloseHandle(f);
    if (ok) ShaHex(s, out);
    return ok;
}

// "TruMenu=TruMenu 0.8.0; TruShadowPower=...": each plugin's *Version export up to " (" (or "loaded" / "no")
const char *const kRegPlugins[] = {"TruMenu", "TruShadowPower", "TruDoppelganger", "TruDlc2Player", "TruRockVein",
                                   "TruGuard", "TruLink", "TruDataGuard"};
void RegVersionsBuild() {
    size_t vUsed = 0, hUsed = 0;
    char versions[sizeof(g_regVersions)] = "", hashes[sizeof(g_regHashes)] = "";
    for (const char *name : kRegPlugins) {
        char file[64], exportName[64];
        _snprintf_s(file, sizeof(file), _TRUNCATE, "%s.asi", name);
        _snprintf_s(exportName, sizeof(exportName), _TRUNCATE, "%sVersion", name);
        HMODULE module = GetModuleHandleA(file);
        char version[96] = "no";
        if (module) {
            typedef const char *(*VersionFn)();
            VersionFn fn = reinterpret_cast<VersionFn>(GetProcAddress(module, exportName));
            const char *text = fn ? fn() : nullptr;
            if (text) {
                strncpy_s(version, sizeof(version), text, _TRUNCATE);
                char *cut = strstr(version, " (");
                if (cut) *cut = 0;
            } else {
                strncpy_s(version, sizeof(version), "loaded", _TRUNCATE);
            }
            TestClean(version);
            char path[MAX_PATH], sha[65] = "";
            if (GetModuleFileNameA(module, path, MAX_PATH) && ShaFile(path, sha)) {
                int w = _snprintf_s(hashes + hUsed, sizeof(hashes) - hUsed, _TRUNCATE, "%s%s.asi=%s", hUsed ? "; " : "",
                                    name, sha);
                if (w > 0) hUsed += static_cast<size_t>(w);
            }
        }
        int w = _snprintf_s(versions + vUsed, sizeof(versions) - vUsed, _TRUNCATE, "%s%s=%s", vUsed ? "; " : "", name,
                            version);
        if (w > 0) vUsed += static_cast<size_t>(w);
    }
    EnterCriticalSection(&g_testLock);
    strncpy_s(g_regVersions, sizeof(g_regVersions), versions, _TRUNCATE);
    strncpy_s(g_regHashes, sizeof(g_regHashes), hashes[0] ? hashes : "-", _TRUNCATE);
    LeaveCriticalSection(&g_testLock);
}
// worker thread once the device exists (every plugin is loaded by then); a mark before that computes it at once
void RegVersionsTick() {
    if (InterlockedCompareExchange(&g_regHashState, 1, 0) != 0) return;
    RegVersionsBuild();
    InterlockedExchange(&g_regHashState, 2);
    Log(2, "regress: plugin versions / sha256 ready: %s", g_regVersions);
}

void RegLoadOne(int list) {
    FILE *f = nullptr;
    int count = 0;
    bool found = g_regPath[list][0] && fopen_s(&f, g_regPath[list], "rb") == 0 && f;
    EnterCriticalSection(&g_testLock);
    if (found) count = ParseTestRows(f, g_reg[list], kTestMax, g_regShortcut[list]);
    for (int i = 0; i < count; ++i) {             // a fresh session: every row open, no note / time
        TestRow &t = g_reg[list][i];
        strncpy_s(t.state, sizeof(t.state), TestDefaultState(t.kind), _TRUNCATE);
        t.note[0] = t.when[0] = 0;
    }
    g_regCount[list] = count;
    g_regFound[list] = found;
    LeaveCriticalSection(&g_testLock);
    if (f) fclose(f);
    Log(1, "regress: %s %d rows from %s", kRegNames[list], count, found ? g_regPath[list] : "(file not found)");
}

int RegListIndex(const char *name) {
    for (int i = 0; i < kRegLists; ++i) if (!_stricmp(name, kRegNames[i])) return i;
    if (!_stricmp(name, "all")) return 2;
    return -1;
}

void RegCountsLocked(int list, int *open, int *ok, int *fail, int *skip) {
    *open = *ok = *fail = *skip = 0;
    for (int i = 0; i < g_regCount[list]; ++i) {
        const TestRow &t = g_reg[list][i];
        if (!TestIs(t, "check")) continue;
        if (!_stricmp(t.state, "ok")) ++*ok;
        else if (!_stricmp(t.state, "fail")) ++*fail;
        else if (!_stricmp(t.state, "skip")) ++*skip;
        else ++*open;
    }
}

// "list:id" or "id" (searched in the selected lists, then in both; ambiguous ids need the list) -> list, row
bool RegFindLocked(const char *spec, int *list, int *row, char *o, size_t n) {
    char name[16] = "";
    const char *id = spec;
    const char *colon = strchr(spec, ':');
    if (colon && static_cast<size_t>(colon - spec) < sizeof(name)) {
        memcpy(name, spec, static_cast<size_t>(colon - spec));
        name[colon - spec] = 0;
        id = colon + 1;
    }
    int only = name[0] ? RegListIndex(name) : -1;
    if (name[0] && (only < 0 || only > 1)) { Out(o, n, "unknown list '%s' (dlc1 / dlc2)", name); return false; }
    int hits = 0;
    for (int l = 0; l < kRegLists; ++l) {
        if (only >= 0 && l != only) continue;
        if (only < 0 && g_regSel != 2 && l != g_regSel) continue;
        for (int i = 0; i < g_regCount[l]; ++i)
            if (!_stricmp(g_reg[l][i].id, id)) { *list = l; *row = i; ++hits; }
    }
    if (!hits && only < 0 && g_regSel != 2)      // not in the selected list: try both
        for (int l = 0; l < kRegLists; ++l)
            for (int i = 0; i < g_regCount[l]; ++i)
                if (!_stricmp(g_reg[l][i].id, id)) { *list = l; *row = i; ++hits; }
    if (hits == 1) return true;
    Out(o, n, hits ? "'%s' is in both lists - write dlc1:%s or dlc2:%s" : "no regression row '%s%s%s' (regress.list)",
        id, hits ? id : "", hits ? id : "");
    return false;
}

// g_testLock held: one result line (+ the session line before the first one)
void RegAppendLocked(int list, const TestRow &t) {
    if (!g_regResultsPath[0]) return;
    FILE *f = nullptr;
    if (fopen_s(&f, g_regResultsPath, "ab") != 0 || !f) { Log(1, "regress: cannot write %s", g_regResultsPath); return; }
    if (!g_regSessionWritten) {
        fprintf(f, "#session\t%s\t%s\t%s\r\n", g_regSession, g_regVersions[0] ? g_regVersions : "-",
                g_regHashes[0] ? g_regHashes : "-");
        g_regSessionWritten = true;
    }
    SYSTEMTIME s;
    GetLocalTime(&s);
    fprintf(f, "%04d-%02d-%02d %02d:%02d:%02d\t%s\t%s\t%s\t%s\t%s\r\n", s.wYear, s.wMonth, s.wDay, s.wHour, s.wMinute,
            s.wSecond, kRegNames[list], t.id, t.state, t.note, g_regSession);
    fclose(f);
}

// state: check ok|fail|skip|open, step done|open; note = nullptr keeps the note
bool RegMark(const char *spec, const char *state, const char *note, char *o, size_t n) {
    if (InterlockedCompareExchange(&g_regHashState, 0, 0) != 2) RegVersionsTick();   // versions before the first line
    for (int i = 0; i < 50 && InterlockedCompareExchange(&g_regHashState, 0, 0) != 2; ++i) Sleep(10);   // worker busy
    EnterCriticalSection(&g_testLock);
    int list = -1, row = -1;
    if (!RegFindLocked(spec, &list, &row, o, n)) { LeaveCriticalSection(&g_testLock); return false; }
    TestRow &t = g_reg[list][row];
    if (state && !TestStateFits(t.kind, state)) {
        Out(o, n, "%s:%s is a %s row: %s", kRegNames[list], t.id, t.kind, TestIs(t, "step") ? "done|open" : "ok|fail|skip|open");
        LeaveCriticalSection(&g_testLock);
        return false;
    }
    if (state) { strncpy_s(t.state, sizeof(t.state), state, _TRUNCATE); _strlwr_s(t.state, sizeof(t.state)); }
    if (note) { strncpy_s(t.note, sizeof(t.note), note, _TRUNCATE); TestClean(t.note); }
    SYSTEMTIME s;
    GetLocalTime(&s);
    _snprintf_s(t.when, sizeof(t.when), _TRUNCATE, "%02d:%02d:%02d", s.wHour, s.wMinute, s.wSecond);
    RegAppendLocked(list, t);
    Out(o, n, "regress %s:%s %s%s%s", kRegNames[list], t.id, t.state, t.note[0] ? " - " : "", t.note);
    LeaveCriticalSection(&g_testLock);
    Log(1, "regress: %s", o);
    return true;
}

bool RunRegressLoad(const char *arg, char *o, size_t n) {
    int sel = arg && arg[0] ? RegListIndex(arg) : g_regSel;
    if (sel < 0) { Out(o, n, "usage: regress.load dlc1|dlc2|all"); return false; }
    for (int l = 0; l < kRegLists; ++l) if (sel == 2 || sel == l) RegLoadOne(l);
    g_regSel = sel;
    EnterCriticalSection(&g_testLock);
    int c1 = g_regCount[0], c2 = g_regCount[1];
    bool f1 = g_regFound[0], f2 = g_regFound[1];
    LeaveCriticalSection(&g_testLock);
    Out(o, n, "regress.load %s: dlc1 %d rows%s, dlc2 %d rows%s (all rows open; results append to %s)",
        sel == 2 ? "all" : kRegNames[sel], c1, f1 ? "" : " (no file)", c2, f2 ? "" : " (no file)",
        g_regResultsPath[0] ? g_regResultsPath : "-");
    return (sel == 2 ? (f1 || f2) : g_regFound[sel]);
}

// "<list:id|id> ok|fail|skip|open|done [note]"
bool RunRegressMark(const char *arg, char *o, size_t n) {
    char spec[96] = "", state[16] = "";
    const char *rest = TestWord(arg, spec, sizeof(spec));
    rest = TestWord(rest, state, sizeof(state));
    if (!spec[0] || !(TestStateOk(state) || !_stricmp(state, "done"))) {
        Out(o, n, "usage: regress.mark <dlc1:id|dlc2:id|id> ok|fail|skip|open [note] (steps: done|open)");
        return false;
    }
    return RegMark(spec, state, rest[0] ? rest : nullptr, o, n);
}

// "<list:id|id> <note text>": the note of a row (the state stays; a result line is written)
bool RunRegressNote(const char *arg, char *o, size_t n) {
    char spec[96] = "";
    const char *rest = TestWord(arg, spec, sizeof(spec));
    if (!spec[0]) { Out(o, n, "usage: regress.note <dlc1:id|dlc2:id|id> <note text>"); return false; }
    return RegMark(spec, nullptr, rest, o, n);
}

void ValRegressList(char *o, size_t n) {
    EnterCriticalSection(&g_testLock);
    int used = _snprintf_s(o, n, _TRUNCATE, "selected %s", g_regSel == 2 ? "all" : kRegNames[g_regSel]);
    for (int l = 0; l < kRegLists && used >= 0; ++l) {
        int open, ok, fail, skip;
        RegCountsLocked(l, &open, &ok, &fail, &skip);
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "; %s %d rows%s (%d open, %d ok, %d fail, %d skip)%s",
                            kRegNames[l], g_regCount[l], g_regFound[l] ? "" : " (no file)", open, ok, fail, skip,
                            g_regCount[l] ? ":" : "");
        if (w < 0) break;
        used += w;
        for (int i = 0; i < g_regCount[l]; ++i) {
            const TestRow &t = g_reg[l][i];
            w = _snprintf_s(o + used, n - used, _TRUNCATE, " %s [%s]%s%s%s", t.id, t.state, t.note[0] ? " {" : "", t.note,
                            t.note[0] ? "}" : "");
            if (w < 0) break;
            used += w;
        }
    }
    LeaveCriticalSection(&g_testLock);
}

// regress.export: "ok+ regress.export ..." then "list<TAB>kind<TAB>id<TAB>state<TAB>number<TAB>target<TAB>hint<TAB>
// note<TAB>time" per row, then "."
void ValRegressExport(char *o, size_t n) {
    EnterCriticalSection(&g_testLock);
    int used = 0;
    for (int l = 0; l < kRegLists; ++l) {
        int open, ok, fail, skip;
        RegCountsLocked(l, &open, &ok, &fail, &skip);
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s %d rows: %d open %d ok %d fail %d skip", l ? "; " : "",
                            kRegNames[l], g_regCount[l], open, ok, fail, skip);
        if (w < 0) break;
        used += w;
    }
    LeaveCriticalSection(&g_testLock);
}
void RegressExportBlock(char *o, size_t n) {
    char head[200];
    ValRegressExport(head, sizeof(head));
    int used = _snprintf_s(o, n, _TRUNCATE, "ok+ regress.export %s (list kind id state number target hint note time, tab "
                           "separated; session %s; results %s)\n", head, g_regSession, g_regResultsPath[0] ? g_regResultsPath : "-");
    if (used < 0) used = 0;
    EnterCriticalSection(&g_testLock);
    for (int l = 0; l < kRegLists; ++l)
        for (int i = 0; i < g_regCount[l]; ++i) {
            const TestRow &t = g_reg[l][i];
            int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s\t%s\t%s\t%s\t%d\t%s\t%s\t%s\t%s\n", kRegNames[l], t.kind,
                                t.id, t.state, t.num, t.target, t.hint, t.note, t.when);
            if (w < 0) break;
            used += w;
        }
    LeaveCriticalSection(&g_testLock);
    if (static_cast<size_t>(used) + 2 >= n) used = static_cast<int>(n) - 3;
    _snprintf_s(o + used, n - used, _TRUNCATE, ".");
}

void RegStart() {
    for (int l = 0; l < kRegLists; ++l)
        _snprintf_s(g_regPath[l], sizeof(g_regPath[l]), _TRUNCATE, "%sTruMenu.regress_%s.txt", g_asiDir, kRegNames[l]);
    _snprintf_s(g_regResultsPath, sizeof(g_regResultsPath), _TRUNCATE, "%sTruMenu.regress_results.txt", g_asiDir);
    SYSTEMTIME s;
    GetLocalTime(&s);
    _snprintf_s(g_regSession, sizeof(g_regSession), _TRUNCATE, "%04d-%02d-%02d %02d:%02d:%02d", s.wYear, s.wMonth, s.wDay,
                s.wHour, s.wMinute, s.wSecond);
    int sel = RegListIndex(g_regressStart);
    g_regSel = sel < 0 ? 2 : sel;
    for (int l = 0; l < kRegLists; ++l) RegLoadOne(l);   // both lists, the selection only filters the page
}

// ---- 0.8.1 regression shortcuts (owner wish 2026-11-02) ----
// Column 9 of a regression row: "#title;cmd;cmd ..." (title optional). "Prepare" runs the commands one after the other
// through the command bar path (CmdRunLine, source "shortcut") from the render thread: the next one only when the
// game-thread request slot is free; after level.load / level.start / level.reload it waits until no level change is
// pending, a player exists and (level.load) the unit is the requested one, for 2 s in a row (timeout 120 s). An "err"
// answer stops the run. game.quit is refused in a shortcut (never automatic).
const char *CmdRunLine(const char *line, bool wait, const char *source);   // 0.6 command bar, below
const int kScMaxSteps = 12, kScStepLen = 160;
CRITICAL_SECTION g_scLock;
volatile LONG g_scActive = 0;
char g_scTitle[96] = "";
char g_scSteps[kScMaxSteps][kScStepLen];
int g_scCount = 0, g_scIndex = 0;
bool g_scWaitLevel = false;
char g_scWaitUnit[64] = "";
char g_scQueued[64] = "";                      // id of the last step that went to the game thread
DWORD g_scWaitStart = 0, g_scReadySince = 0;
char g_scState[200] = "idle";

// "#title;a;b" -> title + steps; false + reason on an empty / too long list or game.quit
bool ShortcutParse(const char *text, char *title, size_t titleSize, char (*steps)[kScStepLen], int *count, char *o,
                   size_t n) {
    *count = 0;
    title[0] = 0;
    char copy[kShortcutLen];
    strncpy_s(copy, sizeof(copy), text ? text : "", _TRUNCATE);
    char *context = nullptr;
    for (char *part = strtok_s(copy, ";", &context); part; part = strtok_s(nullptr, ";", &context)) {
        while (*part == ' ') ++part;
        size_t len = strlen(part);
        while (len && part[len - 1] == ' ') part[--len] = 0;
        if (!len) continue;
        if (part[0] == '#') { if (!title[0]) strncpy_s(title, titleSize, part + 1, _TRUNCATE); continue; }
        if (!_strnicmp(part, "game.quit", 9) && (!part[9] || part[9] == ' ')) {
            Out(o, n, "game.quit is never run by a shortcut");
            return false;
        }
        if (*count >= kScMaxSteps) { Out(o, n, "more than %d commands", kScMaxSteps); return false; }
        strncpy_s(steps[(*count)++], kScStepLen, part, _TRUNCATE);
    }
    if (!*count) { Out(o, n, "no command in the shortcut"); return false; }
    return true;
}
bool ShortcutStart(const char *text, const char *fallbackTitle, char *o, size_t n) {
    char title[96], steps[kScMaxSteps][kScStepLen];
    int count = 0;
    if (!ShortcutParse(text, title, sizeof(title), steps, &count, o, n)) return false;
    EnterCriticalSection(&g_scLock);
    strncpy_s(g_scTitle, sizeof(g_scTitle), title[0] ? title : fallbackTitle, _TRUNCATE);
    memcpy(g_scSteps, steps, sizeof(steps));
    g_scCount = count;
    g_scIndex = 0;
    g_scWaitLevel = false;
    g_scQueued[0] = 0;
    g_scWaitUnit[0] = 0;
    _snprintf_s(g_scState, sizeof(g_scState), _TRUNCATE, "%s: step 1 of %d next", g_scTitle, count);
    InterlockedExchange(&g_scActive, 1);
    LeaveCriticalSection(&g_scLock);
    Log(1, "shortcut '%s' started: %d command(s): %s", g_scTitle, count, text);
    Out(o, n, "shortcut '%s' started (%d command(s); level changes are waited for)", g_scTitle, count);
    return true;
}
void ShortcutStopLocked(const char *why) {
    InterlockedExchange(&g_scActive, 0);
    _snprintf_s(g_scState, sizeof(g_scState), _TRUNCATE, "%s: %s", g_scTitle, why);
    Log(1, "shortcut '%s' %s", g_scTitle, why);
}
// render thread, every frame (also with the menu closed)
void ShortcutTick() {
    if (!g_scActive) return;
    EnterCriticalSection(&g_scLock);
    DWORD now = GetTickCount();
    while (g_scActive) {
        if (g_reqPending) break;                       // the step before still waits for the game thread
        if (g_scQueued[0]) {                           // its game-thread answer: err stops the run
            char result[200] = "";
            EnterCriticalSection(&g_reqLock);
            if (!_stricmp(g_reqId, g_scQueued)) strncpy_s(result, sizeof(result), g_reqResult, _TRUNCATE);
            LeaveCriticalSection(&g_reqLock);
            g_scQueued[0] = 0;
            if (!strncmp(result, "err", 3)) {
                Log(1, "shortcut '%s': %.180s", g_scTitle, result);
                ShortcutStopLocked("stopped: a command answered err on the game thread");
                break;
            }
        }
        if (g_scWaitLevel) {
            if (now - g_scWaitStart > 120000) { ShortcutStopLocked("stopped: the level did not come up within 120 s"); break; }
            if (now - g_scWaitStart < 1500) break;     // let the change start
            char why[200], unit[64];
            CurrentUnit(unit, sizeof(unit));
            bool ready = !LevelChangePending(why, sizeof(why)) && InLevel() &&
                         (!g_scWaitUnit[0] || !_stricmp(unit, g_scWaitUnit));
            if (!ready) { g_scReadySince = 0; break; }
            if (!g_scReadySince) { g_scReadySince = now; break; }
            if (now - g_scReadySince < 2000) break;
            g_scWaitLevel = false;
        }
        if (g_scIndex >= g_scCount) { ShortcutStopLocked("done"); break; }
        const char *step = g_scSteps[g_scIndex++];
        const char *answer = CmdRunLine(step, false, "shortcut");
        bool ok = !strncmp(answer, "ok", 2);
        Log(1, "shortcut '%s' %d/%d: %s -> %.200s", g_scTitle, g_scIndex, g_scCount, step, answer);
        _snprintf_s(g_scState, sizeof(g_scState), _TRUNCATE, "%s: %d of %d ran (%s)", g_scTitle, g_scIndex, g_scCount,
                    step);
        if (!ok) { ShortcutStopLocked("stopped: a command answered err (see the command bar / TruMenu.log)"); break; }
        if (!strncmp(answer, "ok queued ", 10)) {      // remember the id: its result is checked when it ran
            size_t w = 0;
            while (step[w] && step[w] != ' ' && w + 1 < sizeof(g_scQueued)) { g_scQueued[w] = step[w]; ++w; }
            g_scQueued[w] = 0;
        }
        if (!_strnicmp(step, "level.", 6)) {           // level.load / level.start / level.reload: wait for the level
            g_scWaitLevel = true;
            g_scWaitStart = now;
            g_scReadySince = 0;
            g_scWaitUnit[0] = 0;
            if (!_strnicmp(step, "level.load ", 11)) strncpy_s(g_scWaitUnit, sizeof(g_scWaitUnit), step + 11, _TRUNCATE);
            break;
        }
        break;                                         // one command per frame
    }
    LeaveCriticalSection(&g_scLock);
}
void ValShortcut(char *o, size_t n) {
    EnterCriticalSection(&g_scLock);
    Out(o, n, "%s%s", g_scActive ? "running - " : "", g_scState);
    LeaveCriticalSection(&g_scLock);
}
// "<dlc1:id|dlc2:id|id>" = run that row's shortcut; "stop" = stop the running one
bool RunRegressPrepare(const char *arg, char *o, size_t n) {
    if (!arg || !arg[0]) { Out(o, n, "usage: regress.prepare <dlc1:id|dlc2:id|id> | stop (regress.shortcuts lists them)"); return false; }
    if (!_stricmp(arg, "stop")) {
        EnterCriticalSection(&g_scLock);
        bool was = g_scActive != 0;
        if (was) ShortcutStopLocked("stopped by the owner");
        LeaveCriticalSection(&g_scLock);
        Out(o, n, was ? "shortcut stopped" : "no shortcut running");
        return true;
    }
    char text[kShortcutLen] = "", title[96] = "";
    EnterCriticalSection(&g_testLock);
    int list = -1, row = -1;
    bool found = RegFindLocked(arg, &list, &row, o, n);
    if (found) {
        strncpy_s(text, sizeof(text), g_regShortcut[list][row], _TRUNCATE);
        _snprintf_s(title, sizeof(title), _TRUNCATE, "%s:%s", kRegNames[list], g_reg[list][row].id);
    }
    LeaveCriticalSection(&g_testLock);
    if (!found) return false;
    if (!text[0]) { Out(o, n, "%s has no shortcut (column 9 of tests\\regress\\%s.txt)", title, kRegNames[list]); return false; }
    return ShortcutStart(text, title, o, n);
}
void ValRegressShortcuts(char *o, size_t n) {
    EnterCriticalSection(&g_testLock);
    int used = 0, c = 0;
    o[0] = 0;
    for (int l = 0; l < kRegLists; ++l)
        for (int i = 0; i < g_regCount[l]; ++i) {
            if (!g_regShortcut[l][i][0]) continue;
            ++c;
            int w = _snprintf_s(o + used, n - static_cast<size_t>(used), _TRUNCATE, "%s%s:%s = %s", used ? "; " : "",
                                kRegNames[l], g_reg[l][i].id, g_regShortcut[l][i]);
            if (w < 0) break;
            used += w;
        }
    LeaveCriticalSection(&g_testLock);
    if (!c) Out(o, n, "no row with a shortcut (column 9)");
}

// 0.8.1 [Log] InputTrace for this session
void ValInputTrace(char *o, size_t n) { Out(o, n, "%d", g_inputTrace ? 1 : 0); }
bool RunInputTrace(const char *arg, char *o, size_t n) {
    bool on = BoolArg(arg, g_inputTrace != 0);
    InterlockedExchange(&g_inputTrace, on ? 1 : 0);
    Out(o, n, "log.inputtrace %d%s", on ? 1 : 0, on && g_logLevel < 2 ? " (LogLevel is below 2: only the summary "
        "lines are written - [Menu] LogLevel=2 in TruMenu.ini)" : "");
    return true;
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
    static char text[16384];                     // 0.10: the [Radial] section made the text larger than 8 KB
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

// ======================================================================================================================
// 0.9 P0d: Saves page. Static facts (catalog section 11.4, tools/trusave_info.py, tools/pe_find_wstr.py):
//   folder  0x78b550: SHGetFolderLocation(CSIDL_PERSONAL) (fallback: registry Shell Folders "Personal", then
//           L"C:\My Documents") + L"\Eidos\" + L"Tomb Raider - Underworld" + L"\"; files L"<name>.TRUSave" (0x8614b0),
//           the load list enumerates L"*.TRUSave" (0x8614e4), the autosave is L"Autosave" (0x86140c).
//   format  0x0000 rich saved game header 'RGMH' (0x6db2f0, 0x2028 bytes), 0x2028 'PCUD' block (0x6dbb4f / 0x6dbba7):
//           +0x10 count, +0x14 table CRC, +0x18 header CRC, then count x {size, offset, CRC}; CRC = 0x596d80
//           (polynomial 0x04C11DB7 MSB first, init ~0, final ~ = CRC-32/BZIP2), checked by the reader 0x6dbc8d /
//           0x6dbbd5 / 0x6dbcc6. Data block (0x140000 bytes): +0x10 unit name (written 0x556cbe from GameTracker+0x38
//           0xe7f0c0, read back 0x556f38), +0x90 the checkpoint id ("MAIN checkpoint restore %s ID wanted = %d"
//           0x556f83). Nothing else of the block is proven - no field is written by TruMenu (no manipulation in 0.9).
// Every action is a file operation of TruMenu itself (no engine call): list / backup / export are harmless; restore /
// delete / import change the save folder and need the safety step (the same item twice within 10 s, menu buttons:
// a separate CONFIRM button) and are refused over TruLink (owner only). delete and import / restore always back up
// the files they replace first; nothing is ever deleted for good.
// ======================================================================================================================
const DWORD kSaveArmMs = 10000, kSaveArmMinGapMs = 300;
const int kSaveMax = 48, kSaveBackupMax = 24, kSaveImportMax = 24;
const DWORD kSaveDataSize = 0x140000;          // savegame type registration 0x7744e2: push 0x140000
struct SaveInfo {
    wchar_t name[128];                         // without .TRUSave
    char utf8[200];
    ULONGLONG size;
    FILETIME written;
    bool formatOk;                             // RGMH / PCUD + all three CRCs
    char problem[80];
    char unit[64];                             // data +0x10
    DWORD checkpoint;                          // data +0x90
};
struct SaveDir { char name[64]; int files; };
CRITICAL_SECTION g_saveLock;
SaveInfo g_saves[kSaveMax];
int g_saveCount = -1;                          // -1 = not scanned yet
SaveDir g_saveBackups[kSaveBackupMax];
int g_saveBackupCount = 0;
SaveDir g_saveImports[kSaveImportMax];         // name = file name without .TRUSave, files = 1 if its CRCs are ok
int g_saveImportCount = 0;
wchar_t g_saveFolder[MAX_PATH] = L"";
char g_saveFolderU8[MAX_PATH * 2] = "";
char g_saveFolderHow[96] = "not looked up";
wchar_t g_saveRoot[MAX_PATH] = L"";            // <game>\TruMenu.saves\ (backups, export, import)
char g_saveRootU8[MAX_PATH * 2] = "";
char g_saveFolderIni[MAX_PATH] = "";            // [Saves] Folder (UTF-8; empty = as the game)
char g_saveArmKey[200] = "";
volatile LONG g_saveArmAt = 0;
DWORD g_saveCrcTable[256];
bool g_saveCrcReady = false;

void SaveCrcInit() {
    for (DWORD i = 0; i < 256; ++i) {
        DWORD c = i << 24;
        for (int k = 0; k < 8; ++k) c = (c & 0x80000000u) ? ((c << 1) ^ 0x04C11DB7u) : (c << 1);
        g_saveCrcTable[i] = c;
    }
    g_saveCrcReady = true;
}
DWORD SaveCrc(const BYTE *p, size_t n) {          // as 0x596d80
    if (!g_saveCrcReady) SaveCrcInit();
    DWORD c = 0xFFFFFFFFu;
    for (size_t i = 0; i < n; ++i) c = (c << 8) ^ g_saveCrcTable[(c >> 24) ^ p[i]];
    return ~c;
}
void WideToUtf8(const wchar_t *w, char *o, size_t n) {
    if (!WideCharToMultiByte(CP_UTF8, 0, w, -1, o, static_cast<int>(n), nullptr, nullptr)) o[0] = 0;
}
bool Utf8ToWide(const char *s, wchar_t *o, size_t n) {
    return MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s, -1, o, static_cast<int>(n)) > 0;
}
DWORD U32At(const BYTE *p) { return static_cast<DWORD>(p[0]) | (static_cast<DWORD>(p[1]) << 8) |
                                    (static_cast<DWORD>(p[2]) << 16) | (static_cast<DWORD>(p[3]) << 24); }

// the folder the game uses (0x78b550) or [Saves] Folder
void SaveFolderInit() {
    wchar_t path[MAX_PATH] = L"";
    if (g_saveFolderIni[0]) {
        if (Utf8ToWide(g_saveFolderIni, path, MAX_PATH)) {
            size_t len = wcslen(path);
            if (len && path[len - 1] != L'\\' && len + 1 < MAX_PATH) wcscat_s(path, L"\\");
            wcscpy_s(g_saveFolder, path);
            strncpy_s(g_saveFolderHow, sizeof(g_saveFolderHow), "[Saves] Folder", _TRUNCATE);
        }
    } else if (SUCCEEDED(SHGetFolderPathW(nullptr, CSIDL_PERSONAL, nullptr, SHGFP_TYPE_CURRENT, path))) {
        _snwprintf_s(g_saveFolder, MAX_PATH, _TRUNCATE, L"%s\\Eidos\\Tomb Raider - Underworld\\", path);
        strncpy_s(g_saveFolderHow, sizeof(g_saveFolderHow), "CSIDL_PERSONAL + \\Eidos\\Tomb Raider - Underworld (as "
                  "tru.exe 0x78b550)", _TRUNCATE);
    } else {
        strncpy_s(g_saveFolderHow, sizeof(g_saveFolderHow), "CSIDL_PERSONAL not available - set [Saves] Folder",
                  _TRUNCATE);
    }
    WideToUtf8(g_saveFolder, g_saveFolderU8, sizeof(g_saveFolderU8));
    wchar_t exe[MAX_PATH] = L"";
    MultiByteToWideChar(CP_ACP, 0, g_exeDir, -1, exe, MAX_PATH);
    _snwprintf_s(g_saveRoot, MAX_PATH, _TRUNCATE, L"%sTruMenu.saves\\", exe);
    WideToUtf8(g_saveRoot, g_saveRootU8, sizeof(g_saveRootU8));
}

// reads one save and checks the container; fills unit / checkpoint from the data block
bool SaveRead(const wchar_t *path, SaveInfo *s) {
    s->formatOk = false;
    s->problem[0] = s->unit[0] = 0;
    s->checkpoint = 0;
    HANDLE f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) { Out(s->problem, sizeof(s->problem), "cannot open (%lu)", GetLastError()); return false; }
    LARGE_INTEGER size = {};
    GetFileSizeEx(f, &size);
    if (size.QuadPart < 0x2050 || size.QuadPart > 0x400000) {
        CloseHandle(f);
        Out(s->problem, sizeof(s->problem), "size %lld outside 0x2050..4 MB", size.QuadPart);
        return false;
    }
    DWORD n = static_cast<DWORD>(size.QuadPart), got = 0;
    BYTE *b = static_cast<BYTE *>(HeapAlloc(GetProcessHeap(), 0, n));
    bool read = b && ReadFile(f, b, n, &got, nullptr) && got == n;
    CloseHandle(f);
    if (!read) {
        if (b) HeapFree(GetProcessHeap(), 0, b);
        Out(s->problem, sizeof(s->problem), "read failed");
        return false;
    }
    DWORD o = 0;
    if (memcmp(b, "RGMH", 4) == 0) o = U32At(b + 8);                    // header size (0x2028)
    if (o + 0x1c > n || memcmp(b + o, "PCUD", 4) != 0 || U32At(b + o + 4) != 0x100 || memcmp(b + o + 8, "SURT", 4) != 0) {
        Out(s->problem, sizeof(s->problem), "no RGMH / PCUD 0x100 'SURT' block");
    } else {
        DWORD count = U32At(b + o + 0x10), table = o + 0x1c;
        if (count == 0 || count > 16 || table + 12 * count > n) {
            Out(s->problem, sizeof(s->problem), "entry count %lu", count);
        } else if (SaveCrc(b + o, 0x18) != U32At(b + o + 0x18)) {
            Out(s->problem, sizeof(s->problem), "header CRC mismatch");
        } else if (SaveCrc(b + table, 12 * count) != U32At(b + o + 0x14)) {
            Out(s->problem, sizeof(s->problem), "table CRC mismatch");
        } else {
            bool ok = true;
            for (DWORD k = 0; k < count && ok; ++k) {
                DWORD es = U32At(b + table + 12 * k), eo = U32At(b + table + 12 * k + 4);
                if (eo > n || es > n - eo) { Out(s->problem, sizeof(s->problem), "entry %lu outside the file", k); ok = false; }
                else if (SaveCrc(b + eo, es) != U32At(b + table + 12 * k + 8)) {
                    Out(s->problem, sizeof(s->problem), "entry %lu data CRC mismatch", k);
                    ok = false;
                } else if (k == 0 && es >= 0x94) {
                    const char *u = reinterpret_cast<const char *>(b + eo + 0x10);
                    size_t len = 0;
                    while (len < 63 && u[len] && isprint(static_cast<unsigned char>(u[len]))) ++len;
                    memcpy(s->unit, u, len);
                    s->unit[len] = 0;
                    s->checkpoint = U32At(b + eo + 0x90);
                }
            }
            s->formatOk = ok;
        }
    }
    HeapFree(GetProcessHeap(), 0, b);
    return s->formatOk;
}

void SaveScanDirs() {                          // backups (folders below the root) and import files
    g_saveBackupCount = g_saveImportCount = 0;
    wchar_t pattern[MAX_PATH];
    _snwprintf_s(pattern, MAX_PATH, _TRUNCATE, L"%s*", g_saveRoot);
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(pattern, &fd);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) || fd.cFileName[0] == L'.' ||
                !_wcsicmp(fd.cFileName, L"export") || !_wcsicmp(fd.cFileName, L"import"))
                continue;
            SaveDir d = {};
            WideToUtf8(fd.cFileName, d.name, sizeof(d.name));
            wchar_t inner[MAX_PATH];
            _snwprintf_s(inner, MAX_PATH, _TRUNCATE, L"%s%s\\*.TRUSave", g_saveRoot, fd.cFileName);
            WIN32_FIND_DATAW f2;
            HANDLE h2 = FindFirstFileW(inner, &f2);
            if (h2 != INVALID_HANDLE_VALUE) {
                do { ++d.files; } while (FindNextFileW(h2, &f2));
                FindClose(h2);
            }
            // newest first: the names start with yyyyMMdd_HHmmss
            int at = 0;
            while (at < g_saveBackupCount && strcmp(g_saveBackups[at].name, d.name) > 0) ++at;
            if (at >= kSaveBackupMax) continue;
            int last = g_saveBackupCount < kSaveBackupMax ? g_saveBackupCount : kSaveBackupMax - 1;
            for (int i = last; i > at; --i) g_saveBackups[i] = g_saveBackups[i - 1];
            g_saveBackups[at] = d;
            if (g_saveBackupCount < kSaveBackupMax) ++g_saveBackupCount;
        } while (FindNextFileW(h, &fd));
        FindClose(h);
    }
    _snwprintf_s(pattern, MAX_PATH, _TRUNCATE, L"%simport\\*.TRUSave", g_saveRoot);
    h = FindFirstFileW(pattern, &fd);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (g_saveImportCount >= kSaveImportMax) break;
            SaveDir &d = g_saveImports[g_saveImportCount++];
            d = SaveDir();
            wchar_t base[128];
            wcsncpy_s(base, fd.cFileName, _TRUNCATE);
            wchar_t *dot = wcsrchr(base, L'.');
            if (dot) *dot = 0;
            WideToUtf8(base, d.name, sizeof(d.name));
            wchar_t full[MAX_PATH];
            _snwprintf_s(full, MAX_PATH, _TRUNCATE, L"%simport\\%s", g_saveRoot, fd.cFileName);
            SaveInfo tmp;
            d.files = SaveRead(full, &tmp) ? 1 : 0;
        } while (FindNextFileW(h, &fd));
        FindClose(h);
    }
}

DWORD g_saveScanAt = 0;
// reads every save (CRC over ~1.3 MB each): at most every 1.5 s unless forced (after an action, the Refresh button)
void SaveScan(bool force = true) {
    EnterCriticalSection(&g_saveLock);
    if (!force && g_saveCount >= 0 && GetTickCount() - g_saveScanAt < 1500) { LeaveCriticalSection(&g_saveLock); return; }
    g_saveScanAt = GetTickCount();
    if (!g_saveFolder[0] && !g_saveRoot[0]) SaveFolderInit();
    g_saveCount = 0;
    wchar_t pattern[MAX_PATH];
    _snwprintf_s(pattern, MAX_PATH, _TRUNCATE, L"%s*.TRUSave", g_saveFolder);
    WIN32_FIND_DATAW fd = {};
    HANDLE h = g_saveFolder[0] ? FindFirstFileW(pattern, &fd) : INVALID_HANDLE_VALUE;
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if ((fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) || g_saveCount >= kSaveMax) continue;
            SaveInfo &s = g_saves[g_saveCount++];
            wcsncpy_s(s.name, fd.cFileName, _TRUNCATE);
            wchar_t *dot = wcsrchr(s.name, L'.');
            if (dot) *dot = 0;
            WideToUtf8(s.name, s.utf8, sizeof(s.utf8));
            s.size = (static_cast<ULONGLONG>(fd.nFileSizeHigh) << 32) | fd.nFileSizeLow;
            s.written = fd.ftLastWriteTime;
            wchar_t full[MAX_PATH];
            _snwprintf_s(full, MAX_PATH, _TRUNCATE, L"%s%s", g_saveFolder, fd.cFileName);
            SaveRead(full, &s);
        } while (FindNextFileW(h, &fd));
        FindClose(h);
    }
    SaveScanDirs();
    LeaveCriticalSection(&g_saveLock);
}

void FileTimeText(const FILETIME &ft, char *o, size_t n) {
    FILETIME local;
    SYSTEMTIME st;
    if (FileTimeToLocalFileTime(&ft, &local) && FileTimeToSystemTime(&local, &st))
        Out(o, n, "%04u-%02u-%02u %02u:%02u:%02u", st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
    else
        Out(o, n, "?");
}

// "<name>" of an existing save in the folder (UTF-8 argument, no path parts)
bool SaveNameArg(const char *arg, wchar_t *name, size_t size, char *o, size_t n) {
    if (!arg || !arg[0]) { Out(o, n, "give a save name (save.list; without .TRUSave)"); return false; }
    if (strchr(arg, '\\') || strchr(arg, '/') || strchr(arg, ':') || strstr(arg, "..") || strlen(arg) > 120) {
        Out(o, n, "a save name only (no path, no ..)");
        return false;
    }
    if (!Utf8ToWide(arg, name, size)) { Out(o, n, "name is not valid UTF-8"); return false; }
    wchar_t *dot = wcsrchr(name, L'.');
    if (dot && !_wcsicmp(dot, L".TRUSave")) *dot = 0;
    return true;
}
bool SaveBackupNameOk(const char *arg) {
    if (!arg || !arg[0] || strlen(arg) > 60) return false;
    for (const char *p = arg; *p; ++p)
        if (!(isalnum(static_cast<unsigned char>(*p)) || *p == '_' || *p == '-')) return false;
    return true;
}
bool FileExistsW(const wchar_t *path) {
    DWORD a = GetFileAttributesW(path);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}
bool MakeDirW(const wchar_t *path) {
    return CreateDirectoryW(path, nullptr) || GetLastError() == ERROR_ALREADY_EXISTS;
}

// the safety step: the same "<item> <arg>" twice within 10 s (and not faster than 0.3 s)
bool SaveConfirmed(const char *item, const char *arg, char *o, size_t n) {
    char key[200];
    _snprintf_s(key, sizeof(key), _TRUNCATE, "%s %s", item, arg ? arg : "");
    DWORD now = GetTickCount(), at = static_cast<DWORD>(g_saveArmAt), age = now - at;
    EnterCriticalSection(&g_saveLock);
    bool same = at && age <= kSaveArmMs && !strcmp(g_saveArmKey, key);
    if (same && age >= kSaveArmMinGapMs) {
        g_saveArmKey[0] = 0;
        InterlockedExchange(&g_saveArmAt, 0);
        LeaveCriticalSection(&g_saveLock);
        return true;
    }
    if (!same) {
        strncpy_s(g_saveArmKey, sizeof(g_saveArmKey), key, _TRUNCATE);
        InterlockedExchange(&g_saveArmAt, static_cast<LONG>(now ? now : 1));
    }
    LeaveCriticalSection(&g_saveLock);
    Log(1, "saves: '%s' armed - again within 10 s to confirm", key);
    Out(o, n, "armed - run '%s' again within 10 s to confirm (menu: the red CONFIRM button)", key);
    return false;
}
bool SaveArmed(char *key, size_t size, DWORD *left) {
    DWORD at = static_cast<DWORD>(g_saveArmAt), age = GetTickCount() - at;
    if (!at || age > kSaveArmMs) return false;
    EnterCriticalSection(&g_saveLock);
    strncpy_s(key, size, g_saveArmKey, _TRUNCATE);
    LeaveCriticalSection(&g_saveLock);
    *left = kSaveArmMs - age;
    return key[0] != 0;
}
void SaveDisarm() {
    InterlockedExchange(&g_saveArmAt, 0);
    EnterCriticalSection(&g_saveLock);
    g_saveArmKey[0] = 0;
    LeaveCriticalSection(&g_saveLock);
}

// <root><time>[_label]\ with a copy of every *.TRUSave of the save folder; folder name (UTF-8) into dirName
bool SaveBackupAll(const char *label, char *dirName, size_t dirSize, int *copied, char *o, size_t n) {
    *copied = 0;
    if (!g_saveFolder[0]) { Out(o, n, "save folder unknown (%s)", g_saveFolderHow); return false; }
    SYSTEMTIME st;
    GetLocalTime(&st);
    char name[96];
    _snprintf_s(name, sizeof(name), _TRUNCATE, "%04u%02u%02u_%02u%02u%02u%s%s", st.wYear, st.wMonth, st.wDay, st.wHour,
                st.wMinute, st.wSecond, label && label[0] ? "_" : "", label ? label : "");
    wchar_t wname[96], dir[MAX_PATH];
    MultiByteToWideChar(CP_ACP, 0, name, -1, wname, 96);
    if (!MakeDirW(g_saveRoot)) { Out(o, n, "cannot create %s (%lu)", g_saveRootU8, GetLastError()); return false; }
    _snwprintf_s(dir, MAX_PATH, _TRUNCATE, L"%s%s", g_saveRoot, wname);
    for (int k = 2; GetFileAttributesW(dir) != INVALID_FILE_ATTRIBUTES && k < 100; ++k)   // same second twice
        _snwprintf_s(dir, MAX_PATH, _TRUNCATE, L"%s%s_%d", g_saveRoot, wname, k);
    if (!CreateDirectoryW(dir, nullptr)) { Out(o, n, "cannot create the backup folder (%lu)", GetLastError()); return false; }
    const wchar_t *leaf = wcsrchr(dir, L'\\');
    WideToUtf8(leaf ? leaf + 1 : dir, dirName, dirSize);
    wchar_t pattern[MAX_PATH];
    _snwprintf_s(pattern, MAX_PATH, _TRUNCATE, L"%s*.TRUSave", g_saveFolder);
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(pattern, &fd);
    int failed = 0;
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
            wchar_t src[MAX_PATH], dst[MAX_PATH];
            _snwprintf_s(src, MAX_PATH, _TRUNCATE, L"%s%s", g_saveFolder, fd.cFileName);
            _snwprintf_s(dst, MAX_PATH, _TRUNCATE, L"%s\\%s", dir, fd.cFileName);
            if (CopyFileW(src, dst, TRUE)) ++*copied; else ++failed;
        } while (FindNextFileW(h, &fd));
        FindClose(h);
    }
    Log(1, "saves: backup %s: %d file(s) copied, %d failed (from %s)", dirName, *copied, failed, g_saveFolderU8);
    if (failed) { Out(o, n, "backup %s: %d copied, %d FAILED - see TruMenu.log", dirName, *copied, failed); return false; }
    Out(o, n, "backup %s: %d file(s) -> %s%s", dirName, *copied, g_saveRootU8, dirName);
    return true;
}

void ValSaveFolder(char *o, size_t n) {
    EnterCriticalSection(&g_saveLock);
    if (!g_saveFolder[0] && !g_saveRoot[0]) SaveFolderInit();
    Out(o, n, "%s (%s); backups %s", g_saveFolderU8[0] ? g_saveFolderU8 : "-", g_saveFolderHow, g_saveRootU8);
    LeaveCriticalSection(&g_saveLock);
}
void ValSaveList(char *o, size_t n) {
    SaveScan(false);
    EnterCriticalSection(&g_saveLock);
    size_t used = 0;
    o[0] = 0;
    for (int i = 0; i < g_saveCount; ++i) {
        const SaveInfo &s = g_saves[i];
        char when[32];
        FileTimeText(s.written, when, sizeof(when));
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s | %s | %llu bytes | unit %s | checkpoint %lu | %s",
                            used ? "\n" : "", s.utf8, when, s.size, s.unit[0] ? s.unit : "?", s.checkpoint,
                            s.formatOk ? "CRC ok" : s.problem);
        if (w < 0) break;
        used += static_cast<size_t>(w);
    }
    if (!g_saveCount) Out(o, n, "no *.TRUSave in %s", g_saveFolderU8[0] ? g_saveFolderU8 : "(folder unknown)");
    LeaveCriticalSection(&g_saveLock);
}
void ValSaveBackups(char *o, size_t n) {
    SaveScan(false);
    EnterCriticalSection(&g_saveLock);
    size_t used = 0;
    o[0] = 0;
    for (int i = 0; i < g_saveBackupCount; ++i) {
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s (%d)", used ? " " : "", g_saveBackups[i].name,
                            g_saveBackups[i].files);
        if (w < 0) break;
        used += static_cast<size_t>(w);
    }
    if (!g_saveBackupCount) Out(o, n, "no backups in %s", g_saveRootU8);
    LeaveCriticalSection(&g_saveLock);
}
bool RunSaveBackup(const char *arg, char *o, size_t n) {
    if (arg && arg[0] && !SaveBackupNameOk(arg)) { Out(o, n, "label: a-z 0-9 _ - only, up to 60"); return false; }
    char dir[96];
    int copied = 0;
    EnterCriticalSection(&g_saveLock);
    if (!g_saveFolder[0] && !g_saveRoot[0]) SaveFolderInit();
    bool ok = SaveBackupAll(arg, dir, sizeof(dir), &copied, o, n);
    LeaveCriticalSection(&g_saveLock);
    SaveScan();
    return ok;
}
bool RunSaveExport(const char *arg, char *o, size_t n) {
    wchar_t name[128];
    if (!SaveNameArg(arg, name, 128, o, n)) return false;
    EnterCriticalSection(&g_saveLock);
    if (!g_saveFolder[0] && !g_saveRoot[0]) SaveFolderInit();
    wchar_t src[MAX_PATH], dir[MAX_PATH], dst[MAX_PATH];
    _snwprintf_s(src, MAX_PATH, _TRUNCATE, L"%s%s.TRUSave", g_saveFolder, name);
    _snwprintf_s(dir, MAX_PATH, _TRUNCATE, L"%sexport", g_saveRoot);
    _snwprintf_s(dst, MAX_PATH, _TRUNCATE, L"%s\\%s.TRUSave", dir, name);
    bool ok = false;
    if (!FileExistsW(src)) Out(o, n, "no save '%s' (save.list)", arg);
    else if (!MakeDirW(g_saveRoot) || !MakeDirW(dir)) Out(o, n, "cannot create %sexport (%lu)", g_saveRootU8, GetLastError());
    else {
        if (FileExistsW(dst)) {                // never overwrite an earlier export: add the time
            SYSTEMTIME st;
            GetLocalTime(&st);
            _snwprintf_s(dst, MAX_PATH, _TRUNCATE, L"%s\\%s_%04u%02u%02u_%02u%02u%02u.TRUSave", dir, name, st.wYear,
                         st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
        }
        ok = CopyFileW(src, dst, TRUE) != 0;
        char d8[MAX_PATH * 2];
        WideToUtf8(dst, d8, sizeof(d8));
        if (ok) Out(o, n, "exported '%s' -> %s", arg, d8); else Out(o, n, "copy to %s failed (%lu)", d8, GetLastError());
    }
    LeaveCriticalSection(&g_saveLock);
    Log(1, "saves: export: %s", o);
    SaveScan();
    return ok;
}
bool RunSaveDelete(const char *arg, char *o, size_t n) {
    wchar_t name[128];
    if (!SaveNameArg(arg, name, 128, o, n)) return false;
    wchar_t src[MAX_PATH];
    EnterCriticalSection(&g_saveLock);
    if (!g_saveFolder[0] && !g_saveRoot[0]) SaveFolderInit();
    _snwprintf_s(src, MAX_PATH, _TRUNCATE, L"%s%s.TRUSave", g_saveFolder, name);
    bool exists = FileExistsW(src);
    LeaveCriticalSection(&g_saveLock);
    if (!exists) { Out(o, n, "no save '%s' (save.list)", arg); return false; }
    if (!SaveConfirmed("save.delete", arg, o, n)) return true;
    // first a full backup "<time>_deleted" (all files), then the file itself is removed from the save folder
    char dir[96];
    int copied = 0;
    EnterCriticalSection(&g_saveLock);
    bool ok = SaveBackupAll("deleted", dir, sizeof(dir), &copied, o, n);
    wchar_t wdir[96], kept[MAX_PATH];
    MultiByteToWideChar(CP_UTF8, 0, dir, -1, wdir, 96);
    _snwprintf_s(kept, MAX_PATH, _TRUNCATE, L"%s%s\\%s.TRUSave", g_saveRoot, wdir, name);
    if (ok && !FileExistsW(kept)) { Out(o, n, "backup %s has no copy of '%s' - NOT deleted", dir, arg); ok = false; }
    if (ok) {
        ok = DeleteFileW(src) != 0;
        if (ok) Out(o, n, "'%s' deleted from the save folder; copy (with all other saves) in %s%s", arg, g_saveRootU8, dir);
        else Out(o, n, "delete failed (%lu); backup %s made", GetLastError(), dir);
    }
    LeaveCriticalSection(&g_saveLock);
    Log(1, "saves: delete by the owner: %s", o);
    SaveScan();
    return ok;
}
// copies every file of a backup / one import file into the save folder after a backup of the current state
bool SaveCopyIn(const wchar_t *const *files, int count, const char *label, char *o, size_t n) {
    for (int i = 0; i < count; ++i) {
        SaveInfo tmp;
        if (!SaveRead(files[i], &tmp)) {
            char f8[MAX_PATH * 2];
            WideToUtf8(files[i], f8, sizeof(f8));
            Out(o, n, "%s: %s - nothing copied", f8, tmp.problem);
            return false;
        }
    }
    char dir[96];
    int copied = 0;
    if (!SaveBackupAll(label, dir, sizeof(dir), &copied, o, n)) return false;
    int done = 0;
    for (int i = 0; i < count; ++i) {
        const wchar_t *leaf = wcsrchr(files[i], L'\\');
        wchar_t dst[MAX_PATH];
        _snwprintf_s(dst, MAX_PATH, _TRUNCATE, L"%s%s", g_saveFolder, leaf ? leaf + 1 : files[i]);
        if (CopyFileW(files[i], dst, FALSE)) ++done;
        else { Out(o, n, "copy failed (%lu) after %d of %d; the state before is in %s%s", GetLastError(), done, count,
                   g_saveRootU8, dir); return false; }
    }
    Out(o, n, "%d file(s) copied into the save folder; the state before is in %s%s", done, g_saveRootU8, dir);
    return true;
}
bool RunSaveRestore(const char *arg, char *o, size_t n) {
    if (!SaveBackupNameOk(arg)) { Out(o, n, "give a backup folder name (save.backups)"); return false; }
    wchar_t dir[MAX_PATH], wname[64];
    MultiByteToWideChar(CP_UTF8, 0, arg, -1, wname, 64);
    EnterCriticalSection(&g_saveLock);
    if (!g_saveFolder[0] && !g_saveRoot[0]) SaveFolderInit();
    _snwprintf_s(dir, MAX_PATH, _TRUNCATE, L"%s%s\\", g_saveRoot, wname);
    LeaveCriticalSection(&g_saveLock);
    DWORD a = GetFileAttributesW(dir);
    if (a == INVALID_FILE_ATTRIBUTES || !(a & FILE_ATTRIBUTE_DIRECTORY)) { Out(o, n, "no backup '%s' (save.backups)", arg); return false; }
    if (!SaveConfirmed("save.restore", arg, o, n)) return true;
    static wchar_t paths[kSaveMax][MAX_PATH];
    const wchar_t *list[kSaveMax];
    int count = 0;
    wchar_t pattern[MAX_PATH];
    _snwprintf_s(pattern, MAX_PATH, _TRUNCATE, L"%s*.TRUSave", dir);
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(pattern, &fd);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if ((fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) || count >= kSaveMax) continue;
            _snwprintf_s(paths[count], MAX_PATH, _TRUNCATE, L"%s%s", dir, fd.cFileName);
            list[count] = paths[count];
            ++count;
        } while (FindNextFileW(h, &fd));
        FindClose(h);
    }
    if (!count) { Out(o, n, "backup '%s' holds no *.TRUSave", arg); return false; }
    EnterCriticalSection(&g_saveLock);
    bool ok = SaveCopyIn(list, count, "before_restore", o, n);
    LeaveCriticalSection(&g_saveLock);
    Log(1, "saves: restore %s by the owner: %s", arg, o);
    SaveScan();
    return ok;
}
bool RunSaveImport(const char *arg, char *o, size_t n) {
    wchar_t name[128];
    if (!SaveNameArg(arg, name, 128, o, n)) return false;
    wchar_t src[MAX_PATH];
    EnterCriticalSection(&g_saveLock);
    if (!g_saveFolder[0] && !g_saveRoot[0]) SaveFolderInit();
    _snwprintf_s(src, MAX_PATH, _TRUNCATE, L"%simport\\%s.TRUSave", g_saveRoot, name);
    LeaveCriticalSection(&g_saveLock);
    if (!FileExistsW(src)) { Out(o, n, "no %simport\\%s.TRUSave", g_saveRootU8, arg); return false; }
    if (!SaveConfirmed("save.import", arg, o, n)) return true;
    const wchar_t *list[1] = {src};
    EnterCriticalSection(&g_saveLock);
    bool ok = SaveCopyIn(list, 1, "before_import", o, n);
    LeaveCriticalSection(&g_saveLock);
    Log(1, "saves: import %s by the owner: %s", arg, o);
    SaveScan();
    return ok;
}
bool SaveOwnerOnly(const char *id) {
    return !_stricmp(id, "save.delete") || !_stricmp(id, "save.restore") || !_stricmp(id, "save.import");
}

// ======================================================================================================================
// 0.9 P1-P3: music through the engine's own srmusic functions (catalog 11.2; translate, don't imitate). PC facts:
//   SRMUSIC_LoadMusic 0x594320 cdecl (slot, name, a, b): ecx = 0xcc5260 + slot * 0x528, MusicSlot::LoadMusic 0x593eb0
//     (thiscall, play = 1). The game's own call when a unit starts: 0x5b2211 LoadMusic(0, name, 60, 60) (0x5b21d0,
//     name in 0xd98f64; "dummy" -> ""). Script natives: NtMusic::Play 0x4aa450 LoadMusic(slot, name, t1*30, t2*30),
//     stop 0x4aa490 LoadMusic(slot, NULL, t*30, 0) - a NULL name fades the slot out (0x593f8f). fps double 30.0 at
//     0x8439b8.
//   8 slots: the sound update 0x5954d0 walks 0xcc5260 .. 0xcc7ba0 in 0x528 steps (0x595588); slot +0 = current
//     name (strcmp at 0x593f30 against the request), +0x100 = the requested name (copied at 0x593f45), +0x51c = the
//     loaded music object (tested 0x593fa8).
// Calls run on the game thread (queued), like the natives.
// ======================================================================================================================
typedef void(__cdecl *MusicLoadFn)(int slot, const char *name, int a, int b);
const DWORD kMusicLoad = 0x00594320, kMusicSlots = 0x00cc5260, kMusicSlotSize = 0x528, kMusicUnitName = 0x00d98f64;
const int kMusicSlotCount = 8;
const char *const kMusicLoadBytes = "8b442410 8b4c240c 8b542408 6a01 50 51 8b4c2410 69c928050000 52 81c16052cc00 "
                                    "e86afbffff c3";
bool g_musicOk = false;
char g_musicCheck[160] = "not checked";
int g_musicInLevels = 0, g_musicFade = 60, g_musicVarsOk = 0, g_monsterVarsOk = 0;
struct MediaRow { char kind[8]; char name[64]; char source[40]; char flag[16]; };
const int kMediaMax = 160;
MediaRow g_media[kMediaMax];
int g_mediaCount = -1;                         // -1 = TruMenu.media.txt missing
char g_mediaPath[MAX_PATH] = "";

void MediaLoad() {
    _snprintf_s(g_mediaPath, sizeof(g_mediaPath), _TRUNCATE, "%sTruMenu.media.txt", g_asiDir);
    FILE *f = nullptr;
    if (fopen_s(&f, g_mediaPath, "rb") != 0 || !f) { g_mediaCount = -1; return; }
    g_mediaCount = 0;
    char line[256];
    while (fgets(line, sizeof(line), f) && g_mediaCount < kMediaMax) {
        if (line[0] == '#' || line[0] == '\r' || line[0] == '\n') continue;
        char *ctx = nullptr;
        char *kind = strtok_s(line, "\t\r\n", &ctx), *name = strtok_s(nullptr, "\t\r\n", &ctx);
        char *source = strtok_s(nullptr, "\t\r\n", &ctx), *flag = strtok_s(nullptr, "\t\r\n", &ctx);
        if (!kind || !name) continue;
        MediaRow &r = g_media[g_mediaCount++];
        strncpy_s(r.kind, sizeof(r.kind), kind, _TRUNCATE);
        strncpy_s(r.name, sizeof(r.name), name, _TRUNCATE);
        strncpy_s(r.source, sizeof(r.source), source ? source : "-", _TRUNCATE);
        strncpy_s(r.flag, sizeof(r.flag), flag ? flag : "-", _TRUNCATE);
    }
    fclose(f);
}
const MediaRow *MediaFind(const char *kind, const char *name) {
    for (int i = 0; i < g_mediaCount; ++i)
        if (!_stricmp(g_media[i].kind, kind) && !_stricmp(g_media[i].name, name)) return &g_media[i];
    return nullptr;
}
bool MusicCheck() {
    // the wrapper, the unit start call, the stop native, the play native's call, the 8-slot loop and the slot fields
    bool wrap = HexBytesAt(kMusicLoad, kMusicLoadBytes);
    bool unit = HexBytesAt(0x005b2211, "6a3c 6a3c 56 6a00 e80321feff") && HexBytesAt(0x005b21d4, "ba648fd900");
    bool stop = HexBytesAt(0x004aa490, "d9442404 56 dc0db8398400 6a00 8bf1 e87ca83600 50 8b4604 6a00 50 e8709e0e00");
    bool play = HexBytesAt(0x004aa470, "8b4e04 50 8b06 50 51 e8a39e0e00");
    bool loop = HexBytesAt(0x00595588, "be6052cc00") && HexBytesAt(0x00595597, "81c628050000 81fea07bcc00 7ceb");
    bool fields = HexBytesAt(0x00593f2d, "8bc2 50 56 e8dbac2900") && HexBytesAt(0x00593f45, "8dbe00010000") &&
                  HexBytesAt(0x00593fa8, "8b861c050000") && HexBytesAt(0x00593ecb, "85d2 56 57 8bf1 0f84b8000000");
    Out(g_musicCheck, sizeof(g_musicCheck), "LoadMusic 0x594320 %s, unit call 0x5b2211 %s, stop native 0x4aa490 %s, play "
        "native 0x4aa470 %s, slot loop 0x595588 %s, slot fields %s", wrap ? "ok" : "NO", unit ? "ok" : "NO",
        stop ? "ok" : "NO", play ? "ok" : "NO", loop ? "ok" : "NO", fields ? "ok" : "NO");
    return wrap && unit && stop && play && loop && fields;
}
// where music may run now: main menu always, a level only with [Media] MusicInLevels=1
bool MusicPlace(char *o, size_t n) {
    DWORD state = 0;
    if (!g_mainStateOk || !ReadDword(kMainState, &state)) { Out(o, n, "main state not verified"); return false; }
    if (state == 10) return true;
    if (InLevel()) {
        if (g_musicInLevels) return true;
        Out(o, n, "in a level: [Media] MusicInLevels=0 (default until a live test proves it safe)");
        return false;
    }
    Out(o, n, "only in the main menu (main state %lu, needs 10) or in a level with [Media] MusicInLevels=1", state);
    return false;
}
void ValMusicList(char *o, size_t n) {
    if (g_mediaCount < 0) { Out(o, n, "no %s (tools/music_list.py --menu-out; the install copies it)", g_mediaPath); return; }
    size_t used = 0;
    o[0] = 0;
    for (int i = 0; i < g_mediaCount; ++i) {
        if (_stricmp(g_media[i].kind, "music")) continue;
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s (%s%s)", used ? " " : "", g_media[i].name,
                            g_media[i].source, strcmp(g_media[i].flag, "unused?") ? "" : ", unused?");
        if (w < 0) break;
        used += static_cast<size_t>(w);
    }
}
int MusicSlotArg(const char *s, int def) {
    if (!s || !*s) return def;
    char *end = nullptr;
    long v = strtol(s, &end, 10);
    return (end && !*end && v >= 0 && v < kMusicSlotCount) ? static_cast<int>(v) : -1;
}
bool RunMusicPlay(const char *arg, char *o, size_t n) {
    if (!g_musicOk || !g_experimental) { Out(o, n, "music code not verified (%s) / experimental off", g_musicCheck); return false; }
    if (!arg || !arg[0]) { Out(o, n, "usage: media.music.play <track> [slot 0-7] (media.music.list)"); return false; }
    static char name[64];
    char slotText[8] = "";
    if (sscanf_s(arg, "%63s %7s", name, static_cast<unsigned>(sizeof(name)), slotText,
                 static_cast<unsigned>(sizeof(slotText))) < 1) { Out(o, n, "give a track name"); return false; }
    int slot = MusicSlotArg(slotText, 0);
    if (slot < 0) { Out(o, n, "slot 0..7"); return false; }
    if (g_mediaCount < 0) { Out(o, n, "no TruMenu.media.txt - the track names are not known, nothing played"); return false; }
    const MediaRow *row = MediaFind("music", name);
    if (!row) { Out(o, n, "'%s' is not in TruMenu.media.txt (media.music.list)", name); return false; }
    strncpy_s(name, sizeof(name), row->name, _TRUNCATE);
    if (!MusicPlace(o, n)) return false;
    reinterpret_cast<MusicLoadFn>(kMusicLoad)(slot, name, g_musicFade, g_musicFade);
    Out(o, n, "SRMUSIC_LoadMusic 0x%08lx(%d, \"%s\", %d, %d) called (%s)", kMusicLoad, slot, name, g_musicFade,
        g_musicFade, row->source);
    Log(1, "media.music.play: %s", o);
    return true;
}
bool RunMusicStop(const char *arg, char *o, size_t n) {
    if (!g_musicOk || !g_experimental) { Out(o, n, "music code not verified (%s) / experimental off", g_musicCheck); return false; }
    bool all = arg && !_stricmp(arg, "all");
    int slot = all ? 0 : MusicSlotArg(arg, 0);
    if (slot < 0) { Out(o, n, "usage: media.music.stop [slot 0-7 | all]"); return false; }
    if (!MusicPlace(o, n)) return false;
    for (int s = all ? 0 : slot; s <= (all ? kMusicSlotCount - 1 : slot); ++s)
        reinterpret_cast<MusicLoadFn>(kMusicLoad)(s, nullptr, g_musicFade, 0);   // as the stop native 0x4aa490
    char which[8];
    Out(which, sizeof(which), all ? "0..7" : "%d", slot);
    Out(o, n, "SRMUSIC_LoadMusic(%s, NULL, %d, 0) called (fade out, as the stop native 0x4aa490)", which, g_musicFade);
    Log(1, "media.music.stop %s: %s", all ? "all" : arg && arg[0] ? arg : "0", o);
    return true;
}
void ValMusicNow(char *o, size_t n) {
    if (!g_musicOk) { Out(o, n, "music code not verified (%s)", g_musicCheck); return; }
    size_t used = 0;
    o[0] = 0;
    char unit[64] = "";
    ReadString(kMusicUnitName, unit, sizeof(unit));
    int w = _snprintf_s(o, n, _TRUNCATE, "unit music [0x%08lx] '%s';", kMusicUnitName, unit);
    if (w > 0) used = static_cast<size_t>(w);
    int shown = 0;
    for (int s = 0; s < kMusicSlotCount; ++s) {
        DWORD base = kMusicSlots + kMusicSlotSize * static_cast<DWORD>(s), handle = 0;
        char cur[64] = "", req[64] = "";
        ReadString(base, cur, sizeof(cur));
        ReadString(base + 0x100, req, sizeof(req));
        ReadDword(base + 0x51c, &handle);
        if (!cur[0] && !req[0] && !handle) continue;
        w = _snprintf_s(o + used, n - used, _TRUNCATE, " slot %d: '%s'%s%s%s, object %s;", s, cur, req[0] ? " (requested '" : "",
                        req, req[0] ? "')" : "", handle ? "loaded" : "none");
        if (w < 0) break;
        used += static_cast<size_t>(w);
        ++shown;
    }
    if (!shown && used < n) _snprintf_s(o + used, n - used, _TRUNCATE, " all 8 slots empty");
}
// dev.musicvars / dev.monstermusicvars: the bits the original developer table names (rows found at runtime)
const DevRow *DevRowFor(DWORD target, DWORD mask) {
    for (int i = 0; g_devOk && i < g_devCount; ++i)
        if (g_dev[i].type == kDevFlag && g_dev[i].target == target && g_dev[i].p5 == mask) return &g_dev[i];
    return nullptr;
}
void ValFlagBit(DWORD target, DWORD mask, char *o, size_t n) {
    const DevRow *d = DevRowFor(target, mask);
    DWORD v = 0;
    if (!d) { Out(o, n, "no developer-table row for [0x%08lx] & 0x%08lx", target, mask); return; }
    if (ReadDword(target, &v)) Out(o, n, "%d (%s)", (v & mask) ? 1 : 0, d->text); else Out(o, n, "?");
}
bool RunFlagBit(DWORD target, DWORD mask, const char *arg, char *o, size_t n) {
    const DevRow *d = DevRowFor(target, mask);
    DWORD v = 0;
    if (!d || !ReadDword(target, &v)) { Out(o, n, "no developer-table row for [0x%08lx] & 0x%08lx - not switched", target, mask); return false; }
    bool on = BoolArg(arg, (v & mask) != 0);
    WriteDword(target, on ? (v | mask) : (v & ~mask));
    Out(o, n, "%s = %d ([0x%08lx] & 0x%08lx, developer row 0x%08lx)", d->text, on ? 1 : 0, target, mask, d->addr);
    return true;
}
void ValMusicVars(char *o, size_t n) { ValFlagBit(0x00e7f098, 0x10000000, o, n); }
bool RunMusicVars(const char *arg, char *o, size_t n) { return RunFlagBit(0x00e7f098, 0x10000000, arg, o, n); }
void ValMonsterMusicVars(char *o, size_t n) { ValFlagBit(0x00e7f0a0, 0x01000000, o, n); }
bool RunMonsterMusicVars(const char *arg, char *o, size_t n) { return RunFlagBit(0x00e7f0a0, 0x01000000, arg, o, n); }
void ValMediaVideoFlags(char *o, size_t n) {
    if (g_mediaCount < 0) { Out(o, n, "no TruMenu.media.txt"); return; }
    size_t used = 0;
    o[0] = 0;
    for (int i = 0; i < g_mediaCount; ++i) {
        if (_stricmp(g_media[i].kind, "video")) continue;
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s (%s, %s)", used ? " " : "", g_media[i].name,
                            g_media[i].source, g_media[i].flag);
        if (w < 0) break;
        used += static_cast<size_t>(w);
    }
}

// ======================================================================================================================
// 0.10.5 [Shot]: in-game screenshots and Claude marks (owner wish 2026-11-05: the main session gets named shots in the
// run folder instead of ShareX files without names / with wrong times).
// A request (item shot.save / claude.mark, the ring, [Shot] Hotkey, the exports TruMenuShot / TruMenuMark; any thread)
// gets its file name at once - local time of the request, the first open TO TEST step, the name - and waits in a small
// queue. The render thread takes it in the game's Present call (PresentHook / SwapPresentHook, no new hook): before
// Render() = clean (nothing TruMenu draws is in it), after Render() = ui. There: GetBackBuffer(0), for a multisampled
// back buffer a StretchRect into a plain render target, GetRenderTargetData into a D3DPOOL_SYSTEMMEM plain surface,
// the rows copied into memory, every surface released in the same call (nothing is left over for a Reset). Pixel
// conversion, PNG encoding (TruShotPng.h) and the file write run on a worker thread (at most kShotMaxInFlight at once;
// a request waits a frame while they are busy). One TruMenu.log line per file: "shot: <path> <w>x<h> <bytes> bytes,
// capture <ms> ms (render thread), encode <ms> ms + write <ms> ms (worker); clean|with TruMenu, <source>".
// claude.mark <kind> writes "claude.mark <kind>: <HH:MM:SS.mmm> unit=<stream unit> pos=<x> <y> <z> step=<step|->
// shot=<file|-> src=<source>" (TruMenu.log) and requests a clean shot named <kind>.
// ======================================================================================================================
int g_shotEnabled = 1, g_shotClean = 1, g_shotKey = 0, g_shotMaxPerMin = 30;   // [Shot]
char g_shotDir[MAX_PATH] = "";                // resolved [Shot] Folder with a trailing backslash
struct ShotReq { char file[128]; bool ui; char source[24]; LONG seq; };
const int kShotQueueMax = 4;
const LONG kShotMaxInFlight = 2;
ShotReq g_shotQueue[kShotQueueMax];
int g_shotQueueCount = 0;
CRITICAL_SECTION g_shotLock;                  // queue, counters, last texts, rate windows, the name repeat counter
volatile LONG g_shotQueued = 0;               // queue entries (the fast test in Present)
volatile LONG g_shotInFlight = 0;             // worker threads converting / writing
volatile LONG g_shotSeq = 0, g_shotTakenSeq = 0;   // last request / last captured request (shot.save over TruLink waits)
volatile DWORD g_renderThread = 0;            // thread id of the game's Present call
LONG g_shotWritten = 0, g_shotFailed = 0, g_shotRefused = 0, g_markCount = 0;
char g_shotLast[400] = "none", g_shotLastErr[300] = "none";
struct RateWindow { DWORD t[120]; int next; };   // request ticks of the last minute (MaxPerMinute is at most 120)
RateWindow g_shotRate = {}, g_markRate = {};
char g_shotLastBase[96] = "";
int g_shotBaseRepeat = 0;
bool g_shotKeyHeld = false;
bool g_radRunning = false;                    // RadialRun is running an entry (render thread): src=ring
bool RadFront();                              // radial menu, below: a window of this process is in front

// who runs shot.save / claude.mark: the ring, TruMenuInvoke on another thread (TruLink "menu"), else the menu / bar
const char *ShotSource(const char *item) {
    if (g_radRunning) return "ring";
    DWORD render = g_renderThread;
    if (render && GetCurrentThreadId() != render) return "TruLink";
    return item;
}

// lock held; true = one more request fits into the last minute
bool RateAllow(RateWindow &r, int maxPerMin, DWORD now) {
    if (maxPerMin <= 0) return true;
    int recent = 0;
    for (DWORD t : r.t)
        if (t && now - t < 60000) ++recent;
    if (recent >= maxPerMin) return false;
    r.t[r.next] = now ? now : 1;
    r.next = (r.next + 1) % 120;
    return true;
}

// "step<n>" of the TO TEST step with the lowest number that is not done, "-" without one
void ShotStep(char *o, size_t n) {
    if (FlowShotStep(o, n)) return;          // 0.11: while a flow is loaded = its current step id
    Out(o, n, "-");
    EnterCriticalSection(&g_testLock);
    int best = -1;
    for (int i = 0; i < g_testCount; ++i) {
        const TestRow &t = g_tests[i];
        if (!TestIs(t, "step") || !_stricmp(t.state, "done")) continue;
        if (best < 0 || t.num < g_tests[best].num) best = i;
    }
    if (best >= 0) Out(o, n, "step%d", g_tests[best].num);
    LeaveCriticalSection(&g_testLock);
}

// file-name part: A-Z a-z 0-9 _ - . kept, anything else '-', at most 40 characters, "" = "-"
void ShotName(const char *in, char *o, size_t n, bool lower) {
    size_t k = 0;
    for (const char *p = in ? in : ""; *p && k + 1 < n && k < 40; ++p) {
        char c = *p;
        bool ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_' || c == '-' ||
                  c == '.';
        char v = ok ? (lower && c >= 'A' && c <= 'Z' ? static_cast<char>(c - 'A' + 'a') : c) : '-';
        if (v == '-' && k && o[k - 1] == '-') continue;
        o[k++] = v;
    }
    while (k && (o[k - 1] == '-' || o[k - 1] == '.')) --k;
    o[k] = 0;
    if (!k) strncpy_s(o, n, "-", _TRUNCATE);
}

// [Shot] Folder -> g_shotDir: empty = <game folder>\TruShots\, relative = below the game folder
void ShotSetFolder(const char *folder) {
    char f[MAX_PATH];
    strncpy_s(f, sizeof(f), folder ? folder : "", _TRUNCATE);
    for (char *p = f; *p; ++p)
        if (*p == '/') *p = '\\';
    if (!f[0]) _snprintf_s(g_shotDir, sizeof(g_shotDir), _TRUNCATE, "%sTruShots\\", g_exeDir);
    else if (f[1] == ':' || (f[0] == '\\' && f[1] == '\\')) strncpy_s(g_shotDir, sizeof(g_shotDir), f, _TRUNCATE);
    else _snprintf_s(g_shotDir, sizeof(g_shotDir), _TRUNCATE, "%s%s", g_exeDir, f[0] == '\\' ? f + 1 : f);
    size_t len = strlen(g_shotDir);
    if (len && g_shotDir[len - 1] != '\\' && len + 1 < sizeof(g_shotDir)) { g_shotDir[len] = '\\'; g_shotDir[len + 1] = 0; }
}

// worker thread: every folder of g_shotDir (an existing one is fine); true when it is a folder now
bool ShotEnsureDir() {
    char p[MAX_PATH];
    strncpy_s(p, sizeof(p), g_shotDir, _TRUNCATE);
    size_t len = strlen(p);
    for (size_t i = 3; i < len; ++i) {      // after "C:\"; for \\server\share the first two parts fail harmlessly
        if (p[i] != '\\') continue;
        p[i] = 0;
        wchar_t wide[MAX_PATH];              // the W call TruMenu imports already (no new import for the A one)
        if (MultiByteToWideChar(CP_ACP, 0, p, -1, wide, MAX_PATH)) CreateDirectoryW(wide, nullptr);
        p[i] = '\\';
    }
    DWORD a = GetFileAttributesA(g_shotDir);
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY) != 0;
}

// any thread: queue a shot of the next frame. ui: 1 = after TruMenu draws, 0 = before (clean), -1 = [Shot] Clean.
// <file> = the planned file name (folder g_shotDir); false + <why> when refused. Never waits.
bool ShotRequest(const char *name, int ui, const char *source, char *file, size_t fileSize, char *why, size_t whySize,
                 LONG *seq) {
    file[0] = why[0] = 0;
    bool withUi = ui < 0 ? g_shotClean == 0 : ui != 0;
    char clean[48], step[16], base[96];
    ShotName(name, clean, sizeof(clean), false);
    ShotStep(step, sizeof(step));
    SYSTEMTIME t;
    GetLocalTime(&t);
    _snprintf_s(base, sizeof(base), _TRUNCATE, "shot_%02d%02d%02d_%s_%s", t.wHour, t.wMinute, t.wSecond, step, clean);
    bool ok = true;
    EnterCriticalSection(&g_shotLock);
    if (!g_shotEnabled) { Out(why, whySize, "shots off ([Shot] Enabled=0)"); ok = false; }
    else if (!g_device) { Out(why, whySize, "no d3d9 device hooked yet"); ok = false; }
    else if (g_shotQueueCount >= kShotQueueMax) { Out(why, whySize, "busy (%d shots wait for a frame)", g_shotQueueCount); ok = false; }
    else if (!RateAllow(g_shotRate, g_shotMaxPerMin, GetTickCount())) {
        Out(why, whySize, "more than %d shots per minute ([Shot] MaxPerMinute)", g_shotMaxPerMin);
        ok = false;
    }
    if (ok) {
        if (!strcmp(base, g_shotLastBase)) ++g_shotBaseRepeat;   // the same second, step and name: _2, _3, ...
        else { strncpy_s(g_shotLastBase, sizeof(g_shotLastBase), base, _TRUNCATE); g_shotBaseRepeat = 1; }
        if (g_shotBaseRepeat > 1) _snprintf_s(file, fileSize, _TRUNCATE, "%s_%d.png", base, g_shotBaseRepeat);
        else _snprintf_s(file, fileSize, _TRUNCATE, "%s.png", base);
        ShotReq &r = g_shotQueue[g_shotQueueCount++];
        strncpy_s(r.file, sizeof(r.file), file, _TRUNCATE);
        strncpy_s(r.source, sizeof(r.source), source, _TRUNCATE);
        r.ui = withUi;
        r.seq = InterlockedIncrement(&g_shotSeq);
        if (seq) *seq = r.seq;
        InterlockedIncrement(&g_shotQueued);
    } else {
        ++g_shotRefused;
    }
    LeaveCriticalSection(&g_shotLock);
    static DWORD lastRefusedLog = 0;
    if (ok) {
        Log(2, "shot: %s queued %s (%s)", source, file, withUi ? "with TruMenu" : "clean");
    } else if (GetTickCount() - lastRefusedLog >= 1000) {   // a held key / a loop never floods the log
        lastRefusedLog = GetTickCount();
        Log(1, "shot: %s refused - %s", source, why);
    }
    return ok;
}

struct ShotJob {
    unsigned char *raw;
    size_t row;                               // bytes per row in raw (no padding)
    int w, h;
    trushot::PixelKind kind;
    bool ui;
    double captureMs;
    char file[128], source[24];
};

void ShotNote(bool failed, const char *fmt, ...) {
    char text[300];
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf_s(text, sizeof(text), _TRUNCATE, fmt, ap);
    va_end(ap);
    EnterCriticalSection(&g_shotLock);
    if (failed) { ++g_shotFailed; strncpy_s(g_shotLastErr, sizeof(g_shotLastErr), text, _TRUNCATE); }
    else { ++g_shotWritten; strncpy_s(g_shotLast, sizeof(g_shotLast), text, _TRUNCATE); }
    LeaveCriticalSection(&g_shotLock);
    Log(failed ? 0 : 1, "shot: %s", text);
}

DWORD WINAPI ShotWorker(LPVOID param) {
    ShotJob *j = static_cast<ShotJob *>(param);
    LARGE_INTEGER freq, t0, t1, t2;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&t0);
    unsigned char *rgb = static_cast<unsigned char *>(malloc(static_cast<size_t>(j->w) * 3 * static_cast<size_t>(j->h)));
    trushot::Buf png;
    trushot::BufInit(png);
    bool encoded = false;
    if (rgb) {
        trushot::ToRgb(j->raw, j->row, j->w, j->h, j->kind, rgb);
        encoded = trushot::EncodePng(rgb, j->w, j->h, png);
    }
    free(rgb);
    free(j->raw);
    QueryPerformanceCounter(&t1);
    char path[MAX_PATH + 32] = "";
    DWORD err = 0;
    bool written = false, dirOk = encoded && ShotEnsureDir();
    if (dirOk) {
        char stem[128];
        strncpy_s(stem, sizeof(stem), j->file, _TRUNCATE);
        size_t sl = strlen(stem);
        if (sl > 4) stem[sl - 4] = 0;        // without ".png"
        for (int k = 1; k <= 9; ++k) {        // a file of that name from an earlier session: -2 .. -9
            if (k == 1) _snprintf_s(path, sizeof(path), _TRUNCATE, "%s%s", g_shotDir, j->file);
            else _snprintf_s(path, sizeof(path), _TRUNCATE, "%s%s-%d.png", g_shotDir, stem, k);
            HANDLE file = CreateFileA(path, GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
            if (file == INVALID_HANDLE_VALUE) {
                err = GetLastError();
                if (err == ERROR_FILE_EXISTS) continue;
                break;
            }
            DWORD done = 0;
            written = WriteFile(file, png.p, static_cast<DWORD>(png.n), &done, nullptr) && done == png.n;
            if (!written) err = GetLastError();
            CloseHandle(file);
            break;
        }
    }
    QueryPerformanceCounter(&t2);
    double encodeMs = 1000.0 * static_cast<double>(t1.QuadPart - t0.QuadPart) / static_cast<double>(freq.QuadPart);
    double writeMs = 1000.0 * static_cast<double>(t2.QuadPart - t1.QuadPart) / static_cast<double>(freq.QuadPart);
    if (written)
        ShotNote(false, "%s %dx%d %lu bytes, capture %.1f ms (render thread), encode %.0f ms + write %.0f ms (worker); "
                 "%s, %s", path, j->w, j->h, static_cast<unsigned long>(png.n), j->captureMs, encodeMs, writeMs,
                 j->ui ? "with TruMenu" : "clean", j->source);
    else if (!encoded)
        ShotNote(true, "%s not written - out of memory while encoding (%dx%d)", j->file, j->w, j->h);
    else if (!dirOk)
        ShotNote(true, "%s not written - folder %s cannot be made (error %lu)", j->file, g_shotDir, GetLastError());
    else
        ShotNote(true, "%s not written - error %lu (%s)", j->file, err, path);
    trushot::BufFree(png);
    free(j);
    InterlockedDecrement(&g_shotInFlight);
    return 0;
}

// render thread: copy the back buffer of <device> into memory and hand it to a worker
void ShotCapture(IDirect3DDevice9 *device, const ShotReq &r) {
    LARGE_INTEGER freq, t0, t1;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&t0);
    IDirect3DSurface9 *back = nullptr, *resolved = nullptr, *sys = nullptr;
    unsigned char *raw = nullptr;
    D3DSURFACE_DESC d = {};
    int bpp = 0;
    trushot::PixelKind kind = trushot::kPixNone;
    const char *step = "GetBackBuffer";
    HRESULT hr = device->GetBackBuffer(0, 0, D3DBACKBUFFER_TYPE_MONO, &back);
    if (SUCCEEDED(hr) && !back) hr = E_POINTER;
    if (SUCCEEDED(hr)) { step = "GetDesc"; hr = back->GetDesc(&d); }
    if (SUCCEEDED(hr)) {
        kind = trushot::KindOfD3dFormat(static_cast<unsigned>(d.Format), &bpp);
        if (kind == trushot::kPixNone || !d.Width || !d.Height) { step = "back-buffer format"; hr = E_NOTIMPL; }
    }
    IDirect3DSurface9 *src = back;
    if (SUCCEEDED(hr) && d.MultiSampleType != D3DMULTISAMPLE_NONE) {   // GetRenderTargetData needs a plain surface
        step = "CreateRenderTarget";
        hr = device->CreateRenderTarget(d.Width, d.Height, d.Format, D3DMULTISAMPLE_NONE, 0, FALSE, &resolved, nullptr);
        if (SUCCEEDED(hr)) { step = "StretchRect"; hr = device->StretchRect(back, nullptr, resolved, nullptr, D3DTEXF_NONE); }
        src = resolved;
    }
    if (SUCCEEDED(hr)) {
        step = "CreateOffscreenPlainSurface";
        hr = device->CreateOffscreenPlainSurface(d.Width, d.Height, d.Format, D3DPOOL_SYSTEMMEM, &sys, nullptr);
    }
    if (SUCCEEDED(hr)) { step = "GetRenderTargetData"; hr = device->GetRenderTargetData(src, sys); }
    size_t row = static_cast<size_t>(d.Width) * static_cast<size_t>(bpp);
    if (SUCCEEDED(hr)) {
        D3DLOCKED_RECT lr = {};
        step = "LockRect";
        hr = sys->LockRect(&lr, nullptr, D3DLOCK_READONLY);
        if (SUCCEEDED(hr)) {
            raw = static_cast<unsigned char *>(malloc(row * d.Height));
            if (raw)
                for (UINT y = 0; y < d.Height; ++y)
                    memcpy(raw + row * y, static_cast<const unsigned char *>(lr.pBits) + static_cast<size_t>(lr.Pitch) * y, row);
            sys->UnlockRect();
            if (!raw) { step = "memory"; hr = E_OUTOFMEMORY; }
        }
    }
    if (sys) sys->Release();
    if (resolved) resolved->Release();
    if (back) back->Release();
    QueryPerformanceCounter(&t1);
    double ms = 1000.0 * static_cast<double>(t1.QuadPart - t0.QuadPart) / static_cast<double>(freq.QuadPart);
    if (FAILED(hr)) {
        ShotNote(true, "%s not taken - %s failed 0x%08lx (back buffer %ux%u format %u, multisample %u)", r.file, step,
                 static_cast<DWORD>(hr), d.Width, d.Height, static_cast<unsigned>(d.Format),
                 static_cast<unsigned>(d.MultiSampleType));
        free(raw);
        return;
    }
    ShotJob *job = static_cast<ShotJob *>(malloc(sizeof(ShotJob)));
    if (!job) { free(raw); ShotNote(true, "%s not taken - out of memory", r.file); return; }
    job->raw = raw;
    job->row = row;
    job->w = static_cast<int>(d.Width);
    job->h = static_cast<int>(d.Height);
    job->kind = kind;
    job->ui = r.ui;
    job->captureMs = ms;
    strncpy_s(job->file, sizeof(job->file), r.file, _TRUNCATE);
    strncpy_s(job->source, sizeof(job->source), r.source, _TRUNCATE);
    InterlockedIncrement(&g_shotInFlight);
    HANDLE thread = CreateThread(nullptr, 0, ShotWorker, job, 0, nullptr);
    if (!thread) {
        DWORD e = GetLastError();
        InterlockedDecrement(&g_shotInFlight);
        free(raw);
        free(job);
        ShotNote(true, "%s not written - CreateThread failed (%lu)", r.file, e);
        return;
    }
    CloseHandle(thread);
}

// render thread, the game's Present call: before = true before Render() (clean requests), false after it (ui ones)
void ShotFrame(IDirect3DDevice9 *device, bool before) {
    if (!g_shotQueued || !device || g_shotInFlight >= kShotMaxInFlight) return;   // busy workers: the request waits
    ShotReq r = {};
    bool have = false;
    EnterCriticalSection(&g_shotLock);
    for (int i = 0; i < g_shotQueueCount && !have; ++i) {
        if (g_shotQueue[i].ui == before) continue;
        r = g_shotQueue[i];
        for (int k = i + 1; k < g_shotQueueCount; ++k) g_shotQueue[k - 1] = g_shotQueue[k];
        --g_shotQueueCount;
        have = true;
    }
    LeaveCriticalSection(&g_shotLock);
    if (!have) return;
    InterlockedDecrement(&g_shotQueued);
    ShotCapture(device, r);
    InterlockedExchange(&g_shotTakenSeq, r.seq);
}

bool ClaudeMark(const char *kindIn, const char *source, char *o, size_t n);

// render thread, every Present before the clean capture: [Shot] Hotkey = claude.mark now (key-down edge, game in front)
void ShotKeyTick() {
    if (!g_shotKey) return;
    bool down = (GetAsyncKeyState(g_shotKey) & 0x8000) != 0 && RadFront();
    if (down && !g_shotKeyHeld) {
        char o[256];
        ClaudeMark("now", "hotkey", o, sizeof(o));
    }
    g_shotKeyHeld = down;
}

// the start of PresentHook / SwapPresentHook
void ShotBeforeRender(IDirect3DDevice9 *device) {
    g_renderThread = GetCurrentThreadId();
    ShotKeyTick();
    ShotFrame(device, true);
}

// claude.mark <kind>: the log line + a clean shot named <kind> (any thread; never waits)
bool ClaudeMark(const char *kindIn, const char *source, char *o, size_t n) {
    char kind[24];
    ShotName(kindIn && kindIn[0] ? kindIn : "now", kind, sizeof(kind), true);
    if (strlen(kind) > 16) kind[16] = 0;
    EnterCriticalSection(&g_shotLock);
    bool allowed = RateAllow(g_markRate, g_shotMaxPerMin, GetTickCount());
    if (allowed) ++g_markCount;
    LeaveCriticalSection(&g_shotLock);
    if (!allowed) {
        Out(o, n, "more than %d marks per minute ([Shot] MaxPerMinute) - not marked", g_shotMaxPerMin);
        static DWORD lastLog = 0;
        if (GetTickCount() - lastLog >= 1000) { lastLog = GetTickCount(); Log(1, "claude.mark %s refused (%s): %s", kind, source, o); }
        return false;
    }
    char file[128], why[160];
    bool shot = ShotRequest(kind, 0, "claude.mark", file, sizeof(file), why, sizeof(why), nullptr);
    char unit[64] = "", pos[64], step[16];
    DWORD id = 0;
    if (ReadDword(kUnitId, &id)) StreamUnitName(id, unit, sizeof(unit));
    if (!unit[0]) CurrentUnit(unit, sizeof(unit));
    for (char *p = unit; *p; ++p)
        if (*p == ' ') *p = '_';
    if (!unit[0]) strncpy_s(unit, sizeof(unit), "-", _TRUNCATE);
    float p3[3], r3[3];
    DWORD instance = 0;
    if (ReadLara(p3, r3, &instance)) Out(pos, sizeof(pos), "%.0f %.0f %.0f", p3[0], p3[1], p3[2]);
    else Out(pos, sizeof(pos), "- - -");
    ShotStep(step, sizeof(step));
    SYSTEMTIME t;
    GetLocalTime(&t);
    char line[400];
    _snprintf_s(line, sizeof(line), _TRUNCATE, "claude.mark %s: %02d:%02d:%02d.%03d unit=%s pos=%s step=%s shot=%s src=%s%s%s%s",
                kind, t.wHour, t.wMinute, t.wSecond, t.wMilliseconds, unit, pos, step, shot ? file : "-", source,
                shot ? "" : " (no shot: ", shot ? "" : why, shot ? "" : ")");
    Log(1, "%s", line);
    Out(o, n, "%s", line);
    FlowOnMark(kind, shot ? file : "");      // 0.11: the flow step's result / marks (an event only)
    return true;
}

void ValShot(char *o, size_t n) {
    EnterCriticalSection(&g_shotLock);
    Out(o, n, "enabled %d, clean %d, hotkey 0x%02x%s, max %d per minute, folder %s; written %ld, failed %ld, refused %ld, "
        "waiting %d, in flight %ld, marks %ld; last: %s; last error: %s", g_shotEnabled, g_shotClean, g_shotKey,
        g_shotKey ? " (= claude.mark now)" : " (off)", g_shotMaxPerMin, g_shotDir, g_shotWritten, g_shotFailed,
        g_shotRefused, g_shotQueueCount, g_shotInFlight, g_markCount, g_shotLast, g_shotLastErr);
    LeaveCriticalSection(&g_shotLock);
}
void ValMarks(char *o, size_t n) {
    Out(o, n, "%ld marks (kinds now good bug gfx sound stutter; [Shot] MaxPerMinute %d, Hotkey 0x%02x)", g_markCount,
        g_shotMaxPerMin, g_shotKey);
}

// shot.save [ui|clean] [name]: from the render thread (menu, ring, command bar) only queued; from another thread
// (TruLink) it waits up to 2 s until the frame is copied and answers with the path
bool RunShotSave(const char *arg, char *o, size_t n) {
    char a[160];
    strncpy_s(a, sizeof(a), arg ? arg : "", _TRUNCATE);
    char *rest = a;
    while (*rest == ' ') ++rest;
    int ui = -1;
    for (int k = 0; k < 2; ++k) {
        const char *word = k ? "clean" : "ui";
        size_t len = strlen(word);
        if (!_strnicmp(rest, word, len) && (rest[len] == 0 || rest[len] == ' ')) {
            ui = k ? 0 : 1;
            rest += len;
            while (*rest == ' ') ++rest;
            break;
        }
    }
    char file[128], why[160];
    LONG seq = 0;
    if (!ShotRequest(rest, ui, ShotSource("menu"), file, sizeof(file), why, sizeof(why), &seq)) { Out(o, n, "%s", why); return false; }
    DWORD render = g_renderThread;
    if (!render || GetCurrentThreadId() == render) {
        Out(o, n, "queued %s%s (next frame; TruMenu.log 'shot:' line when written)", g_shotDir, file);
        return true;
    }
    for (int i = 0; i < 100 && g_shotTakenSeq - seq < 0; ++i) Sleep(20);
    if (g_shotTakenSeq - seq >= 0)
        Out(o, n, "captured %s%s (the PNG is written on a worker thread - TruMenu.log 'shot:' line)", g_shotDir, file);
    else
        Out(o, n, "queued %s%s (no frame within 2 s - taken at the next one)", g_shotDir, file);
    return true;
}
bool RunClaudeMark(const char *arg, char *o, size_t n) { return ClaudeMark(arg, ShotSource("menu"), o, n); }

// the exports TruMenuShot / TruMenuMark (other plugins; any thread, never wait); the name is copied SEH-guarded
int ShotExport(const char *name) {
    char copy[64] = "";
    if (name) ReadString(reinterpret_cast<DWORD>(name), copy, sizeof(copy));
    char file[128], why[160];
    bool ok = ShotRequest(copy, -1, "TruMenuShot", file, sizeof(file), why, sizeof(why), nullptr);
    Log(1, "shot: TruMenuShot(\"%s\") -> %s%s", copy, ok ? "queued " : "refused: ", ok ? file : why);
    return ok ? 1 : 0;
}
int MarkExport(const char *kind) {
    char copy[64] = "";
    if (kind) ReadString(reinterpret_cast<DWORD>(kind), copy, sizeof(copy));
    char o[400];
    return ClaudeMark(copy, "TruMenuMark", o, sizeof(o)) ? 1 : 0;
}

// ======================================================================================================================
// 0.11 "Ablauf" (guided test runs, stage 2; owner wish 2026-11-05): TruMenu.flow.txt next to tru.exe ([Flow] File)
// holds steps (action / observe / mark), counters and conditions (format: TruFlowCore.h, README "Ablauf"). The ring
// level Claude shows the current step ("Weiter: ..." runs an action's do= commands through the regression-shortcut
// path ShortcutStart / ShortcutTick - level changes are waited for there), Gut / Fehler (= claude.mark good / bug: mark
// + clean shot + the step's result), Ueberspringen, Zurueck; a status line in Claude's coral sits in a screen corner
// ([Flow] Overlay / Position / Size / Lines). Counters: unit / level loads and checkpoint restores from the TruTrace.log
// tail, plugin-log patterns from the Tru*.log tails (own tail, [Flow] PollMs, every new byte up to 256 KB per poll),
// player deaths from the player state-mode word, TO TEST switch flips, item runs, Claude marks. Every event is a
// TruMenu.log line "flow: ..." (Invoke-TruTestRun.ps1 builds the summary section "Ablauf" from them).
// Threads: g_flowLock guards g_flow and the run state (render thread FlowTick, worker FlowTailTick, item callers);
// FlowOnItem / FlowOnToggle / FlowOnMark only queue an event under the leaf lock g_flowEvLock (they are called while
// g_scLock / g_testLock / g_shotLock may be held), FlowTick applies the events. Only the render thread starts a step's
// commands (g_flowRunReq), so g_flowLock -> g_scLock is the only order of the two.
// Player deaths, static (tools/pe_abs_uses.py 0xfada74, tools/pe_dis.py; data/pc/tru.exe sha256 6905b046...): bit
// 0x10000 of [0xfada74] is set by exactly one instruction, `or dword [0xfada74], 0x10408` at 0x75aa69 =
// DeathState::Entry 0x75aa50 (name: docs Befund-Prototyp-2007.md, agrees with TRLAU); the ten immediate stores
// (0x48 0x2d9 0xc9 0x40020208 0x40 0x1049 0xc0000001 0x48 0x48 0x49) and the two register stores (ecx = 0x81 at
// 0x7522d5) never hold it, no and-mask clears it. So a rising edge of the bit is one DeathState entry; the next state
// entry's immediate store clears it. The bytes at 0x75aa69 are checked at load (mismatch = no death counter).
// ======================================================================================================================
int g_flowEnabled = 0, g_flowOverlay = 1, g_flowLines = 2, g_flowToastMs = 6000, g_flowPollMs = 500, g_flowAuto = 1;
int g_flowPos = 3;                           // [Flow] Position: 0 top left, 1 top right, 2 bottom left, 3 bottom right
const char *const kFlowCorners[4] = {"tl", "tr", "bl", "br"};
float g_flowSize = 1.0f;
char g_flowFile[MAX_PATH] = "TruMenu.flow.txt", g_flowPath[MAX_PATH] = "";
CRITICAL_SECTION g_flowLock, g_flowEvLock;
truflow::Flow g_flow;                        // under g_flowLock
enum { kFsOpen = 0, kFsRun, kFsOk, kFsFail, kFsSkip };
const char *const kFsNames[] = {"open", "run", "ok", "fail", "skip"};
struct FlowRun {
    int state;
    bool started, cmdsDone, scOurs;
    DWORD start, end;                        // GetTickCount of the (last) start / the result
    LONG startSeq;                           // g_flowSeq at the start: check= / fail= log lines must be newer
    unsigned marks;                          // Claude mark kinds seen since the start (bit = FlowMarkKind)
    char by[24], note[160], shots[200];
};
FlowRun g_flowRun[truflow::kMaxSteps];
int g_flowCount[truflow::kMaxCounters];
bool g_flowCountDirty[truflow::kMaxCounters], g_flowCountReached[truflow::kMaxCounters];
DWORD g_flowCountLogTick[truflow::kMaxCounters];
LONG g_flowWatchHits[truflow::kMaxWatches], g_flowWatchSeq[truflow::kMaxWatches];
LONG g_flowSeq = 0;                          // order of matched log lines (under g_flowLock)
LONG g_flowGen = 0;                          // +1 per load: the worker drops matches of an older flow
int g_flowCur = 0;                           // current step; g_flow.nSteps = finished
bool g_flowLoaded = false, g_flowDoneLogged = false;
char g_flowState[200] = "not loaded ([Flow] Enabled=0)";
DWORD g_flowT0 = 0;
int g_flowRunReq = -1;                       // flow.next on an action: the render thread starts its commands
DWORD g_flowRunReqTick = 0;
volatile LONG g_flowLoadReq = 1;             // the worker (re)loads the file: 1 at the start, flow.reload
char g_flowToast[200] = "";
DWORD g_flowToastTick = 0;
bool g_flowDeathOk = false, g_flowDeathBit = false;
DWORD g_flowDeathWord = 0;
LONG g_flowDeaths = 0;
const DWORD kFlowDeathSite = 0x0075aa69;     // DeathState::Entry: or dword [0xfada74], 0x10408
const DWORD kFlowDeathBit = 0x00010000;
struct FlowEv { int type; char a[48]; char b[128]; };
enum { kFeItem = 1, kFeToggle, kFeMark };
FlowEv g_flowEv[32];
int g_flowEvCount = 0;
LONG g_flowEvLost = 0;
struct FlowTail { char file[truflow::kFileLen]; char path[MAX_PATH]; LONGLONG offset; };
FlowTail g_flowTails[8];                     // worker thread only
int g_flowTailCount = 0;
LONG g_flowTailSkipped = 0;

float FlowSec() { return static_cast<float>(GetTickCount() - g_flowT0) / 1000.0f; }

// Claude mark kind (claude.mark now / good / bug / gfx / sound / stutter) of a name: the kind word or the German ring
// label; -1 = another word
int FlowMarkKind(const char *name) {
    static const char *const kinds[6][4] = {{"now", "jetzt", "", ""}, {"good", "gut", "", ""}, {"bug", "fehler", "", ""},
                                            {"gfx", "grafik", "grafik komisch", ""}, {"sound", "ton", "ton komisch", ""},
                                            {"stutter", "ruckler", "haenger", "ruckler / haenger"}};
    for (int k = 0; k < 6; ++k)
        for (const char *w : kinds[k])
            if (w[0] && !_stricmp(w, name)) return k;
    return -1;
}

void FlowCondText(const truflow::Cond &c, char *o, size_t n) {
    if (c.type == truflow::kCondWatch && c.index >= 0 && c.index < g_flow.nWatches) {
        const truflow::Watch &w = g_flow.watches[c.index];
        if (w.cat[0]) _snprintf_s(o, n, _TRUNCATE, "trace:%s:%s", w.cat, w.source);
        else _snprintf_s(o, n, _TRUNCATE, "log:%s:%s", w.file, w.source);
    } else _snprintf_s(o, n, _TRUNCATE, "%s:%s", truflow::kCondNames[c.type], c.ref);
}

// g_flowLock held. check = a log line / mark newer than the step's start; else (after=) any time since the load
bool FlowCondMetLocked(int i, const truflow::Cond &c, bool check) {
    switch (c.type) {
    case truflow::kCondStep: return c.index >= 0 && g_flowRun[c.index].state == kFsOk;
    case truflow::kCondDone: return c.index >= 0 && g_flowRun[c.index].state >= kFsOk;
    case truflow::kCondCounter: {
        const truflow::Counter &k = g_flow.counters[c.index];
        return k.target > 0 && g_flowCount[c.index] >= k.target;
    }
    case truflow::kCondMark: {
        int kind = FlowMarkKind(c.ref);
        return kind >= 0 && (g_flowRun[i].marks >> kind) & 1;
    }
    case truflow::kCondWatch:
        return check ? g_flowWatchSeq[c.index] > g_flowRun[i].startSeq : g_flowWatchHits[c.index] > 0;
    }
    return false;
}

// "" = every after= is met, else the first one that is not (for the overlay / Weiter)
const char *FlowWaitLocked(int i, char *o, size_t n) {
    o[0] = 0;
    const truflow::Step &s = g_flow.steps[i];
    for (int k = 0; k < s.nAfter; ++k)
        if (!FlowCondMetLocked(i, s.after[k], false)) {
            FlowCondText(s.after[k], o, n);
            break;
        }
    return o;
}

void FlowAdvanceLocked();

// a step's result; the current step moves on with [Flow] AutoAdvance=1 (Gut / Fehler / Weiter always)
void FlowFinishLocked(int i, int state, const char *by, const char *note, bool advance) {
    FlowRun &r = g_flowRun[i];
    if (!r.started) { r.started = true; r.start = GetTickCount(); r.startSeq = g_flowSeq; }
    r.state = state;
    r.end = GetTickCount();
    r.scOurs = false;
    strncpy_s(r.by, sizeof(r.by), by, _TRUNCATE);
    if (note) strncpy_s(r.note, sizeof(r.note), note, _TRUNCATE);
    Log(1, "flow: step %s %s %d/%d t=%.1f dur=%.1f by=%s%s%s", g_flow.steps[i].id, kFsNames[state], i + 1, g_flow.nSteps,
        FlowSec(), static_cast<float>(r.end - r.start) / 1000.0f, by, r.note[0] ? " note=" : "", r.note);
    if (i == g_flowCur && advance) FlowAdvanceLocked();
}

// step i becomes the current one (a step with skip= is skipped at once)
void FlowEnterLocked(int i) {
    g_flowCur = i;
    if (i >= g_flow.nSteps) {
        if (g_flowDoneLogged) return;
        g_flowDoneLogged = true;
        int c[5] = {};
        for (int k = 0; k < g_flow.nSteps; ++k) ++c[g_flowRun[k].state];
        Log(1, "flow: done %d ok, %d fail, %d skip, %d open t=%.1f", c[kFsOk], c[kFsFail], c[kFsSkip], c[kFsOpen] + c[kFsRun],
            FlowSec());
        return;
    }
    g_flowDoneLogged = false;
    FlowRun &r = g_flowRun[i];
    const truflow::Step &s = g_flow.steps[i];
    r.started = true;
    r.start = GetTickCount();
    r.startSeq = g_flowSeq;
    r.marks = 0;
    if (r.state != kFsRun) r.state = kFsOpen;
    Log(1, "flow: step %s start %d/%d (%s) t=%.1f: %s", s.id, i + 1, g_flow.nSteps, truflow::kKindNames[s.kind], FlowSec(), s.text);
    if (s.skip[0]) FlowFinishLocked(i, kFsSkip, "file", s.skip, true);
}

// the next step after the current one that has no result yet; none = the flow is done
void FlowAdvanceLocked() {
    for (int j = g_flowCur + 1; j < g_flow.nSteps; ++j)
        if (g_flowRun[j].state < kFsOk) { FlowEnterLocked(j); return; }
    FlowEnterLocked(g_flow.nSteps);
}

void FlowCounterAddLocked(int c, int delta) {
    if (delta <= 0) return;
    g_flowCount[c] += delta;
    g_flowCountDirty[c] = true;
}

void FlowErrLine(void *, int line, const char *message) { Log(0, "flow: error line %d: %s", line, message); }

// worker thread: (re)reads the file; every state and counter starts anew
void FlowLoad() {
    static char text[256 * 1024 + 1];
    size_t got = 0;
    bool found = false;
    FILE *f = nullptr;
    if (fopen_s(&f, g_flowPath, "rb") == 0 && f) {
        got = fread(text, 1, sizeof(text) - 1, f);
        found = true;
        fclose(f);
    }
    text[got] = 0;
    bool deathOk = HexBytesAt(kFlowDeathSite, "810d74dafa0008040100");
    EnterCriticalSection(&g_flowLock);
    ++g_flowGen;
    memset(g_flowRun, 0, sizeof(g_flowRun));
    memset(g_flowCount, 0, sizeof(g_flowCount));
    memset(g_flowCountDirty, 0, sizeof(g_flowCountDirty));
    memset(g_flowCountReached, 0, sizeof(g_flowCountReached));
    memset(g_flowCountLogTick, 0, sizeof(g_flowCountLogTick));
    memset(g_flowWatchHits, 0, sizeof(g_flowWatchHits));
    memset(g_flowWatchSeq, 0, sizeof(g_flowWatchSeq));
    g_flowSeq = 0;
    g_flowRunReq = -1;
    g_flowDoneLogged = false;
    g_flowT0 = GetTickCount();
    g_flowDeathOk = deathOk;
    g_flowTailCount = 0;                     // the worker syncs the tails (this is the worker thread)
    if (!found) {
        memset(&g_flow, 0, sizeof(g_flow));
        g_flowLoaded = false;
        _snprintf_s(g_flowState, sizeof(g_flowState), _TRUNCATE, "%s not found (Invoke-TruTestRun.ps1 installs a "
                    "profile's flowFile)", g_flowPath);
        Log(0, "flow: %s", g_flowState);
    } else {
        int errors = truflow::ParseText(g_flow, text, FlowErrLine, nullptr);
        g_flowLoaded = g_flow.nSteps > 0;
        _snprintf_s(g_flowState, sizeof(g_flowState), _TRUNCATE, "%s: %d steps, %d counters, %d log patterns, %d errors%s",
                    g_flowPath, g_flow.nSteps, g_flow.nCounters, g_flow.nWatches, errors,
                    got >= sizeof(text) - 1 ? " (cut at 256 KB)" : "");
        Log(1, "flow: loaded %s (id %s: %s); deaths %s", g_flowState, g_flow.id[0] ? g_flow.id : "-", g_flow.title,
            deathOk ? "counted (DeathState entry 0x75aa69 checked)" : "NOT counted (bytes at 0x75aa69 differ)");
        if (g_flowLoaded) FlowEnterLocked(0);
    }
    LeaveCriticalSection(&g_flowLock);
}

// a hook event (any thread, any lock held): queued under the leaf lock, FlowTick applies it
void FlowEvent(int type, const char *a, const char *b) {
    if (!g_flowLoaded) return;
    EnterCriticalSection(&g_flowEvLock);
    if (g_flowEvCount < 32) {
        FlowEv &e = g_flowEv[g_flowEvCount++];
        e.type = type;
        strncpy_s(e.a, sizeof(e.a), a ? a : "", _TRUNCATE);
        strncpy_s(e.b, sizeof(e.b), b ? b : "", _TRUNCATE);
    } else ++g_flowEvLost;
    LeaveCriticalSection(&g_flowEvLock);
}
void FlowOnItem(const char *id) { FlowEvent(kFeItem, id, ""); }
void FlowOnToggle(const char *id, const char *state) { FlowEvent(kFeToggle, id, state); }
void FlowOnMark(const char *kind, const char *file) { FlowEvent(kFeMark, kind, file); }

// g_flowLock held: one event
void FlowApplyLocked(const FlowEv &e) {
    using namespace truflow;
    int kind = e.type == kFeMark ? FlowMarkKind(e.a) : -1;
    for (int c = 0; c < g_flow.nCounters; ++c) {
        const Counter &k = g_flow.counters[c];
        if ((e.type == kFeItem && k.source == kSrcItem && !_stricmp(k.arg, e.a)) ||
            (e.type == kFeToggle && k.source == kSrcToggle && !_stricmp(k.arg, e.a)) ||
            (e.type == kFeMark && k.source == kSrcMark && (kind >= 0 ? FlowMarkKind(k.arg) == kind : !_stricmp(k.arg, e.a))))
            FlowCounterAddLocked(c, 1);
    }
    if (e.type != kFeMark) return;
    int i = g_flowCur;
    bool cur = i < g_flow.nSteps;
    Log(1, "flow: mark %s step=%s shot=%s t=%.1f", e.a, cur ? g_flow.steps[i].id : "-", e.b[0] ? e.b : "-", FlowSec());
    if (!cur) return;
    FlowRun &r = g_flowRun[i];
    if (kind >= 0) r.marks |= 1u << kind;
    size_t used = strlen(r.shots);
    _snprintf_s(r.shots + used, sizeof(r.shots) - used, _TRUNCATE, "%s%s:%s", used ? "; " : "", e.a, e.b[0] ? e.b : "-");
    if (r.state >= kFsOk) return;
    // Gut / Fehler = the owner's result for every kind; any other mark finishes a mark step
    if (kind == 1) FlowFinishLocked(i, kFsOk, "Gut", nullptr, true);
    else if (kind == 2) FlowFinishLocked(i, kFsFail, "Fehler", nullptr, true);
    else if (g_flow.steps[i].kind == kKindMark) FlowFinishLocked(i, kFsOk, e.a, nullptr, true);
}

// render thread, every frame
void FlowTick() {
    if (!g_flowLoaded) return;
    using namespace truflow;
    FlowEv ev[32];
    int nev = 0;
    EnterCriticalSection(&g_flowEvLock);
    nev = g_flowEvCount;
    memcpy(ev, g_flowEv, sizeof(FlowEv) * static_cast<size_t>(nev));
    g_flowEvCount = 0;
    LeaveCriticalSection(&g_flowEvLock);
    DWORD word = 0;
    bool bit = g_flowDeathOk && ReadDword(kPlayerModeFlags, &word) && (word & kFlowDeathBit);
    EnterCriticalSection(&g_flowLock);
    if (!g_flowLoaded) { LeaveCriticalSection(&g_flowLock); return; }
    for (int k = 0; k < nev; ++k) FlowApplyLocked(ev[k]);
    // player deaths: a rising edge of the DeathState bit while in a level
    if (bit && !g_flowDeathBit && InLevel()) {
        ++g_flowDeaths;
        g_flowDeathWord = word;
        Log(1, "flow: death %ld ([0x%08lx] = 0x%08lx, DeathState entry bit 0x%05lx) t=%.1f", g_flowDeaths, kPlayerModeFlags,
            word, kFlowDeathBit, FlowSec());
        for (int c = 0; c < g_flow.nCounters; ++c)
            if (g_flow.counters[c].source == kSrcDeaths) FlowCounterAddLocked(c, 1);
    }
    g_flowDeathBit = bit;
    // flow.next on an action: start its commands when the shortcut slot is free (at most 10 s)
    if (g_flowRunReq >= 0 && g_flowRunReq < g_flow.nSteps) {
        int i = g_flowRunReq;
        if (!g_scActive) {
            g_flowRunReq = -1;
            char title[48], o[200];
            _snprintf_s(title, sizeof(title), _TRUNCATE, "flow:%s", g_flow.steps[i].id);
            if (ShortcutStart(g_flow.steps[i].cmds, title, o, sizeof(o))) {
                g_flowRun[i].scOurs = true;
                g_flowRun[i].cmdsDone = false;
                Log(1, "flow: step %s run %d/%d t=%.1f cmds=%s", g_flow.steps[i].id, i + 1, g_flow.nSteps, FlowSec(),
                    g_flow.steps[i].cmds);
            } else FlowFinishLocked(i, kFsFail, "commands", o, true);
        } else if (GetTickCount() - g_flowRunReqTick > 10000) {
            g_flowRunReq = -1;
            FlowFinishLocked(i, kFsFail, "commands", "another shortcut / Prepare kept running for 10 s", true);
        }
    }
    for (int i = 0; i < g_flow.nSteps; ++i) {
        FlowRun &r = g_flowRun[i];
        const Step &s = g_flow.steps[i];
        if (!r.started || r.state >= kFsOk) continue;
        if (r.state == kFsRun && r.scOurs) {           // the step's commands: done / stopped / replaced
            char title[48], state[200];
            _snprintf_s(title, sizeof(title), _TRUNCATE, "flow:%s", s.id);
            EnterCriticalSection(&g_scLock);
            bool active = g_scActive != 0, ours = !_stricmp(g_scTitle, title);
            strncpy_s(state, sizeof(state), g_scState, _TRUNCATE);
            LeaveCriticalSection(&g_scLock);
            if (!ours) { FlowFinishLocked(i, kFsFail, "commands", "replaced by another shortcut / Prepare", true); continue; }
            if (!active) {
                r.scOurs = false;
                size_t len = strlen(state);
                if (len >= 6 && !strcmp(state + len - 6, ": done")) {
                    r.cmdsDone = true;
                    Log(1, "flow: step %s commands done t=%.1f", s.id, FlowSec());
                    if (!s.nCheck) { FlowFinishLocked(i, kFsOk, "commands", nullptr, g_flowAuto != 0); continue; }
                } else { FlowFinishLocked(i, kFsFail, "commands", state, true); continue; }
            }
        }
        bool done = false;
        for (int k = 0; k < s.nFail && !done; ++k)
            if (FlowCondMetLocked(i, s.fail[k], true)) {
                char t[200];
                FlowCondText(s.fail[k], t, sizeof(t));
                FlowFinishLocked(i, kFsFail, "auto", t, g_flowAuto != 0);
                done = true;
            }
        if (done || (s.kind == kKindAction && !r.cmdsDone)) continue;
        for (int k = 0; k < s.nCheck && !done; ++k)
            if (FlowCondMetLocked(i, s.check[k], true)) {
                char t[200];
                FlowCondText(s.check[k], t, sizeof(t));
                FlowFinishLocked(i, kFsOk, "auto", t, g_flowAuto != 0);
                done = true;
            }
    }
    // counters: at most one line per counter and second, the target line always
    DWORD now = GetTickCount();
    for (int c = 0; c < g_flow.nCounters; ++c) {
        const Counter &k = g_flow.counters[c];
        bool reached = k.target > 0 && g_flowCount[c] >= k.target && !g_flowCountReached[c];
        if (!g_flowCountDirty[c] || (!reached && now - g_flowCountLogTick[c] < 1000)) continue;
        g_flowCountDirty[c] = false;
        g_flowCountLogTick[c] = now;
        if (reached) g_flowCountReached[c] = true;
        Log(1, "flow: counter %s %d/%d t=%.1f%s", k.id, g_flowCount[c], k.target, FlowSec(), reached ? " reached" : "");
    }
    LeaveCriticalSection(&g_flowLock);
}

// worker thread: load requests + the log tails (every [Flow] PollMs; all new bytes up to 256 KB per file and poll)
void FlowTailTick() {
    if (!g_flowEnabled) return;
    if (InterlockedExchange(&g_flowLoadReq, 0)) FlowLoad();
    static DWORD last = 0;
    DWORD now = GetTickCount();
    if (!g_flowLoaded || now - last < static_cast<DWORD>(g_flowPollMs)) return;
    last = now;
    using namespace truflow;
    static Watch watches[kMaxWatches];
    int nw = 0;
    LONG gen = 0;
    EnterCriticalSection(&g_flowLock);           // a copy of the watches: matching runs without the lock
    nw = g_flow.nWatches;
    memcpy(watches, g_flow.watches, sizeof(Watch) * static_cast<size_t>(nw));
    gen = g_flowGen;
    LeaveCriticalSection(&g_flowLock);
    for (int w = 0; w < nw; ++w) {                // tails for new files (load, flow.add); a new tail starts at the end
        bool have = false;
        for (int t = 0; t < g_flowTailCount; ++t) have = have || !_stricmp(g_flowTails[t].file, watches[w].file);
        if (have || g_flowTailCount >= 8) continue;
        FlowTail &t = g_flowTails[g_flowTailCount++];
        strncpy_s(t.file, sizeof(t.file), watches[w].file, _TRUNCATE);
        _snprintf_s(t.path, sizeof(t.path), _TRUNCATE, "%s%s", g_exeDir, watches[w].file);
        WIN32_FILE_ATTRIBUTE_DATA a;
        t.offset = GetFileAttributesExA(t.path, GetFileExInfoStandard, &a)
                 ? (static_cast<LONGLONG>(a.nFileSizeHigh) << 32) | a.nFileSizeLow : 0;
        Log(2, "flow: tail %s from byte %lld", t.path, t.offset);
    }
    static char buf[256 * 1024 + 1];
    static LONG hits[kMaxWatches];
    static LONG lineSeq[kMaxWatches];
    for (int t = 0; t < g_flowTailCount; ++t) {
        FlowTail &tl = g_flowTails[t];
        HANDLE h = CreateFileA(tl.path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                               OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (h == INVALID_HANDLE_VALUE) continue;
        LARGE_INTEGER size = {};
        GetFileSizeEx(h, &size);
        if (size.QuadPart < tl.offset) tl.offset = 0;      // recreated
        LONGLONG avail = size.QuadPart - tl.offset;
        if (avail > static_cast<LONGLONG>(sizeof(buf) - 1)) {
            LONGLONG skip = avail - static_cast<LONGLONG>(sizeof(buf) - 1);
            tl.offset += skip;
            InterlockedExchangeAdd(&g_flowTailSkipped, static_cast<LONG>(skip > 0x7fffffff ? 0x7fffffff : skip));
            Log(1, "flow: tail %s: %lld bytes skipped (more than 256 KB in one poll) - counters may miss lines", tl.file, skip);
            avail = static_cast<LONGLONG>(sizeof(buf) - 1);
        }
        DWORD got = 0;
        LARGE_INTEGER pos;
        pos.QuadPart = tl.offset;
        if (avail > 0 && SetFilePointerEx(h, pos, nullptr, FILE_BEGIN) &&
            ReadFile(h, buf, static_cast<DWORD>(avail), &got, nullptr) && got) {
            buf[got] = 0;
            char *lastNl = nullptr;
            for (DWORD k = got; k > 0; --k) if (buf[k - 1] == '\n') { lastNl = buf + k - 1; break; }
            if (lastNl) {
                tl.offset += (lastNl + 1) - buf;
                *lastNl = 0;
                memset(hits, 0, sizeof(hits));
                memset(lineSeq, 0, sizeof(lineSeq));
                LONG line = 0;
                char *ctx = nullptr;
                for (char *l = strtok_s(buf, "\n", &ctx); l; l = strtok_s(nullptr, "\n", &ctx)) {
                    size_t len = strlen(l);
                    if (len && l[len - 1] == '\r') l[len - 1] = 0;
                    ++line;
                    for (int w = 0; w < nw; ++w)
                        if (!_stricmp(watches[w].file, tl.file) && WatchMatches(watches[w], l)) { ++hits[w]; lineSeq[w] = line; }
                }
                EnterCriticalSection(&g_flowLock);
                if (gen == g_flowGen) {
                    LONG base = g_flowSeq;
                    for (int w = 0; w < nw; ++w) {
                        if (!hits[w]) continue;
                        g_flowWatchHits[w] += hits[w];
                        g_flowWatchSeq[w] = base + lineSeq[w];
                        for (int c = 0; c < g_flow.nCounters; ++c)
                            if (g_flow.counters[c].watch == w) FlowCounterAddLocked(c, hits[w]);
                    }
                    g_flowSeq = base + line;
                }
                LeaveCriticalSection(&g_flowLock);
            } else if (got == sizeof(buf) - 1) tl.offset += got;   // one line longer than the buffer: dropped
        }
        CloseHandle(h);
    }
}

// ---- items ----
bool FlowReady(char *o, size_t n) {
    if (!g_flowEnabled) { Out(o, n, "no flow ([Flow] Enabled=0)"); return false; }
    if (!g_flowLoaded) { Out(o, n, "no flow loaded (%s)", g_flowState); return false; }
    return true;
}
void ValFlowStatus(char *o, size_t n) {
    EnterCriticalSection(&g_flowLock);
    if (!g_flowEnabled || !g_flowLoaded) {
        Out(o, n, "%s", g_flowEnabled ? g_flowState : "off ([Flow] Enabled=0)");
        LeaveCriticalSection(&g_flowLock);
        return;
    }
    int c[5] = {};
    for (int k = 0; k < g_flow.nSteps; ++k) ++c[g_flowRun[k].state];
    o[0] = 0;
    auto add = [&](const char *fmt, auto... a) {
        size_t used = strlen(o);
        if (used + 1 < n) _snprintf_s(o + used, n - used, _TRUNCATE, fmt, a...);
    };
    if (g_flowCur < g_flow.nSteps) {
        char wait[200];
        FlowWaitLocked(g_flowCur, wait, sizeof(wait));
        add("flow %s step %d/%d %s (%s, %s)%s%s: %s", g_flow.id, g_flowCur + 1, g_flow.nSteps, g_flow.steps[g_flowCur].id,
            truflow::kKindNames[g_flow.steps[g_flowCur].kind], kFsNames[g_flowRun[g_flowCur].state],
            wait[0] ? " waits for " : "", wait, g_flow.steps[g_flowCur].text);
    } else add("flow %s done (%d steps)", g_flow.id, g_flow.nSteps);
    add("; %d ok, %d fail, %d skip, %d open; deaths %ld%s", c[kFsOk], c[kFsFail], c[kFsSkip], c[kFsOpen] + c[kFsRun],
        g_flowDeaths, g_flowDeathOk ? "" : " (not counted)");
    for (int k = 0; k < g_flow.nCounters; ++k)
        add("%s%s %d/%d", k ? ", " : "; counters ", g_flow.counters[k].id, g_flowCount[k], g_flow.counters[k].target);
    LeaveCriticalSection(&g_flowLock);
}
void ValFlowList(char *o, size_t n) {
    EnterCriticalSection(&g_flowLock);
    o[0] = 0;
    size_t used = 0;
    for (int i = 0; i < g_flow.nSteps && g_flowLoaded; ++i) {
        const FlowRun &r = g_flowRun[i];
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s%d %s %s %s%s%s", used ? "; " : "", i == g_flowCur ? ">" : "", i + 1,
                            g_flow.steps[i].id, truflow::kKindNames[g_flow.steps[i].kind], kFsNames[r.state],
                            r.by[0] ? " by " : "", r.by);
        if (w < 0) break;
        used += static_cast<size_t>(w);
    }
    if (!used) Out(o, n, "%s", g_flowState);
    LeaveCriticalSection(&g_flowLock);
}
// Weiter: action = start its commands; mark = done; observe = left open; then the next step
bool RunFlowNext(const char *, char *o, size_t n) {
    if (!FlowReady(o, n)) return false;
    EnterCriticalSection(&g_flowLock);
    bool ok = true;
    int i = g_flowCur;
    if (i >= g_flow.nSteps) { Out(o, n, "flow done - flow.goto <id> / Zurueck to repeat a step"); ok = false; }
    else {
        const truflow::Step &s = g_flow.steps[i];
        FlowRun &r = g_flowRun[i];
        char wait[200];
        if (r.state >= kFsOk) { FlowAdvanceLocked(); Out(o, n, "step %s was %s - next", s.id, kFsNames[r.state]); }
        else if (s.kind == truflow::kKindAction) {
            if (r.state == kFsRun) { Out(o, n, "step %s runs (its commands / check)", s.id); ok = false; }
            else if (FlowWaitLocked(i, wait, sizeof(wait))[0]) { Out(o, n, "step %s waits for %s (Ueberspringen / flow.goto)", s.id, wait); ok = false; }
            else if (g_scActive || g_flowRunReq >= 0) { Out(o, n, "a shortcut / Prepare still runs - try again"); ok = false; }
            else {
                r.state = kFsRun;
                g_flowRunReq = i;
                g_flowRunReqTick = GetTickCount();
                Out(o, n, "step %s: %s", s.id, s.cmds);
            }
        } else if (s.kind == truflow::kKindMark) {
            FlowFinishLocked(i, kFsOk, "Weiter", nullptr, true);
            Out(o, n, "step %s done", s.id);
        } else {
            Log(1, "flow: step %s open %d/%d t=%.1f by=Weiter", s.id, i + 1, g_flow.nSteps, FlowSec());
            FlowAdvanceLocked();
            Out(o, n, "step %s left open (no Gut / Fehler)", s.id);
        }
    }
    LeaveCriticalSection(&g_flowLock);
    return ok;
}
int FlowFindLocked(const char *id) { return truflow::FindStep(g_flow, id); }
// a finished / left step becomes current again (state open; its marks start anew)
void FlowReopenLocked(int i, const char *by) {
    FlowRun &r = g_flowRun[i];
    if (r.state >= kFsOk || r.state == kFsRun) Log(1, "flow: step %s open %d/%d t=%.1f by=%s", g_flow.steps[i].id, i + 1, g_flow.nSteps,
                                                   FlowSec(), by);
    if (g_flowRunReq == i) g_flowRunReq = -1;
    r.state = kFsOpen;
    r.cmdsDone = r.scOurs = false;
    r.by[0] = r.note[0] = 0;
    FlowEnterLocked(i);
}
bool RunFlowBack(const char *, char *o, size_t n) {
    if (!FlowReady(o, n)) return false;
    EnterCriticalSection(&g_flowLock);
    bool ok = g_flowCur > 0;
    if (ok) { FlowReopenLocked(g_flowCur - 1, "Zurueck"); Out(o, n, "step %s again", g_flow.steps[g_flowCur].id); }
    else Out(o, n, "at the first step");
    LeaveCriticalSection(&g_flowLock);
    return ok;
}
bool RunFlowGoto(const char *arg, char *o, size_t n) {
    if (!FlowReady(o, n)) return false;
    char id[truflow::kIdLen] = "";
    if (arg) sscanf_s(arg, "%31s", id, static_cast<unsigned>(sizeof(id)));
    EnterCriticalSection(&g_flowLock);
    int i = FlowFindLocked(id);
    if (i >= 0) {
        Log(1, "flow: goto %s t=%.1f", id, FlowSec());
        FlowReopenLocked(i, "flow.goto");
        Out(o, n, "step %s (%d/%d) is current", g_flow.steps[i].id, i + 1, g_flow.nSteps);
    } else Out(o, n, "usage: flow.goto <step id> (no step '%s' - flow.list)", id);
    LeaveCriticalSection(&g_flowLock);
    return i >= 0;
}
// "[<id> [reason]]": no id = the current step (ring: Ueberspringen)
bool RunFlowSkip(const char *arg, char *o, size_t n) {
    if (!FlowReady(o, n)) return false;
    char id[truflow::kIdLen] = "";
    int used = 0;
    if (arg && arg[0]) sscanf_s(arg, "%31s %n", id, static_cast<unsigned>(sizeof(id)), &used);
    const char *why = used > 0 && static_cast<size_t>(used) <= strlen(arg) ? arg + used : "";
    char reason[160];
    truflow::Ascii(why[0] ? why : "Ueberspringen", reason, sizeof(reason));
    EnterCriticalSection(&g_flowLock);
    int i = id[0] ? FlowFindLocked(id) : g_flowCur;
    bool ok = i >= 0 && i < g_flow.nSteps;
    if (ok) {
        if (g_flowRunReq == i) g_flowRunReq = -1;
        FlowFinishLocked(i, kFsSkip, id[0] ? "flow.skip" : "Ueberspringen", reason, true);
        Out(o, n, "step %s skipped (%s)", g_flow.steps[i].id, reason);
    } else Out(o, n, id[0] ? "no step '%s' (flow.list)" : "flow done - nothing to skip%s", id);
    LeaveCriticalSection(&g_flowLock);
    return ok;
}
bool RunFlowAdd(const char *arg, char *o, size_t n) {
    if (!FlowReady(o, n)) return false;
    char why[240] = "";
    EnterCriticalSection(&g_flowLock);
    int before = g_flow.nSteps;
    bool ok = arg && arg[0] && truflow::ParseRecord(g_flow, arg, why, sizeof(why));
    if (ok && g_flow.nSteps > before) {
        int bad = -1;
        if (!truflow::Resolve(g_flow, before, &bad, why, sizeof(why))) { --g_flow.nSteps; ok = false; }
        else {
            memset(&g_flowRun[before], 0, sizeof(FlowRun));
            if (g_flowCur >= before) FlowEnterLocked(before);   // the flow was done: the new step is current
        }
    }
    if (!arg || !arg[0]) strncpy_s(why, sizeof(why), "usage: flow.add <counter | ... / step | ... record>", _TRUNCATE);
    Log(1, "flow: add %s -> %s%s", arg ? arg : "", ok ? "ok" : "err ", ok ? "" : why);
    if (ok) Out(o, n, "added (%d steps, %d counters)", g_flow.nSteps, g_flow.nCounters);
    else Out(o, n, "%s", why);
    LeaveCriticalSection(&g_flowLock);
    return ok;
}
bool RunFlowSay(const char *arg, char *o, size_t n) {
    if (!arg || !arg[0]) { Out(o, n, "usage: flow.say <text>"); return false; }
    char text[200];
    truflow::Ascii(arg, text, sizeof(text));
    EnterCriticalSection(&g_flowLock);
    strncpy_s(g_flowToast, sizeof(g_flowToast), text, _TRUNCATE);
    g_flowToastTick = GetTickCount();
    LeaveCriticalSection(&g_flowLock);
    Log(1, "flow: say %s", text);
    Out(o, n, "toast for %d s: %s", g_flowToastMs / 1000, text);
    return true;
}
bool RunFlowReload(const char *, char *o, size_t n) {
    if (!g_flowEnabled) { Out(o, n, "no flow ([Flow] Enabled=0)"); return false; }
    InterlockedExchange(&g_flowLoadReq, 1);
    Out(o, n, "%s is read again by the worker (within a second)", g_flowPath);
    return true;
}
// ok|fail [note] = claude.mark good / bug (the TruMenu.log mark line + a clean shot + the step result)
bool RunFlowResult(const char *arg, char *o, size_t n) {
    if (!FlowReady(o, n)) return false;
    bool good = arg && !_strnicmp(arg, "ok", 2), bad = arg && !_strnicmp(arg, "fail", 4);
    if (!good && !bad) { Out(o, n, "usage: flow.result ok|fail [note]"); return false; }
    const char *note = arg + (good ? 2 : 4);
    while (*note == ' ') ++note;
    if (note[0]) {
        char t[160];
        truflow::Ascii(note, t, sizeof(t));
        EnterCriticalSection(&g_flowLock);
        if (g_flowCur < g_flow.nSteps) strncpy_s(g_flowRun[g_flowCur].note, sizeof(g_flowRun[g_flowCur].note), t, _TRUNCATE);
        LeaveCriticalSection(&g_flowLock);
    }
    return ClaudeMark(good ? "good" : "bug", ShotSource("menu"), o, n);
}

// shot / claude.mark file names: the current flow step instead of the TO TEST step
bool FlowShotStep(char *o, size_t n) {
    if (!g_flowLoaded) return false;
    EnterCriticalSection(&g_flowLock);       // order g_shotLock -> g_flowLock only (flow code never takes g_shotLock)
    bool have = g_flowLoaded && g_flowCur < g_flow.nSteps;
    if (have) Out(o, n, "%s", g_flow.steps[g_flowCur].id);
    LeaveCriticalSection(&g_flowLock);
    return have;
}

// ---- ring (level Claude) ----
const char *FlowRadWhy(const char *id) {
    if (_strnicmp(id, "flow.", 5)) return "";
    if (!g_flowEnabled) return "kein Ablauf ([Flow] Enabled=0)";
    if (!g_flowLoaded) return "kein Ablauf geladen (TruMenu.flow.txt)";
    if ((!_stricmp(id, "flow.next") || !_stricmp(id, "flow.skip")) && g_flowCur >= g_flow.nSteps) return "Ablauf fertig";
    if (!_stricmp(id, "flow.back") && g_flowCur <= 0) return "erster Schritt";
    return "";
}
// the label of a flow entry right now (false = keep the file's label)
bool FlowRadLabel(const char *id, char *o, size_t n) {
    if (_strnicmp(id, "flow.", 5) || !g_flowLoaded) return false;
    EnterCriticalSection(&g_flowLock);
    bool set = true;
    int i = g_flowCur;
    if (!_stricmp(id, "flow.next") && i < g_flow.nSteps)
        _snprintf_s(o, n, _TRUNCATE, "Weiter: %s", g_flow.steps[i].text);
    else if (!_stricmp(id, "flow.status"))
        _snprintf_s(o, n, _TRUNCATE, "Ablauf %d/%d", i < g_flow.nSteps ? i + 1 : g_flow.nSteps, g_flow.nSteps);
    else set = false;
    LeaveCriticalSection(&g_flowLock);
    return set;
}
// the centre text when a flow entry / a Claude mark is picked (false = the ring's own text)
bool FlowRadInfo(const char *id, const char *arg, char *o, size_t n) {
    bool mark = !_stricmp(id, "claude.mark");
    if ((_strnicmp(id, "flow.", 5) && !mark) || !g_flowLoaded) return false;
    EnterCriticalSection(&g_flowLock);
    int i = g_flowCur;
    if (i >= g_flow.nSteps) _snprintf_s(o, n, _TRUNCATE, "Ablauf fertig (%d Schritte)", g_flow.nSteps);
    else {
        const truflow::Step &s = g_flow.steps[i];
        char wait[200];
        FlowWaitLocked(i, wait, sizeof(wait));
        if (mark && arg && (!_stricmp(arg, "good") || !_stricmp(arg, "bug")))
            _snprintf_s(o, n, _TRUNCATE, "%s %s = %s + Marke + Bild", s.id, !_stricmp(arg, "good") ? "Gut" : "Fehler",
                        !_stricmp(arg, "good") ? "ok" : "fail");
        else if (!_stricmp(id, "flow.back") && i > 0)
            _snprintf_s(o, n, _TRUNCATE, "zurueck zu %d/%d: %s", i, g_flow.nSteps, g_flow.steps[i - 1].text);
        else
            _snprintf_s(o, n, _TRUNCATE, "%d/%d %s: %s%s%s%s%s", i + 1, g_flow.nSteps, truflow::kKindNames[s.kind], s.text,
                        s.hint[0] ? " - " : "", s.hint, wait[0] ? " - wartet: " : "", wait);
    }
    LeaveCriticalSection(&g_flowLock);
    return true;
}

// ---- status line + toast (render thread, inside the ImGui frame) ----
bool FlowWantsDraw() {
    return g_flowEnabled && ((g_flowLoaded && g_flowOverlay) || (g_flowToast[0] && GetTickCount() - g_flowToastTick < static_cast<DWORD>(g_flowToastMs)));
}
void DrawFlowOverlay() {
    const ImVec4 coral(217.0f / 255.0f, 119.0f / 255.0f, 87.0f / 255.0f, 1.0f);
    ImGuiViewport *vp = ImGui::GetMainViewport();
    ImGuiWindowFlags flags = ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_NoNav |
                             ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoFocusOnAppearing |
                             ImGuiWindowFlags_NoSavedSettings;
    char l1[320] = "", l2[220] = "", l3[220] = "", toast[200] = "";
    bool showToast = false;
    EnterCriticalSection(&g_flowLock);
    if (g_flowToast[0] && GetTickCount() - g_flowToastTick < static_cast<DWORD>(g_flowToastMs)) {
        strncpy_s(toast, sizeof(toast), g_flowToast, _TRUNCATE);
        showToast = true;
    }
    if (g_flowLoaded && g_flowOverlay) {
        int i = g_flowCur, total = g_flow.nSteps;
        char counter[96] = "", next[120] = "";
        if (i < total) {
            const truflow::Step &s = g_flow.steps[i];
            if (s.nCount) {
                int c = s.counters[0];
                const truflow::Counter &k = g_flow.counters[c];
                if (k.target > 0) _snprintf_s(counter, sizeof(counter), _TRUNCATE, " | %s %d/%d", k.text[0] ? k.text : k.id, g_flowCount[c], k.target);
                else _snprintf_s(counter, sizeof(counter), _TRUNCATE, " | %s %d", k.text[0] ? k.text : k.id, g_flowCount[c]);
            }
            for (int j = i + 1; j < total; ++j)
                if (g_flowRun[j].state < kFsOk) { _snprintf_s(next, sizeof(next), _TRUNCATE, " | naechster: %.80s", g_flow.steps[j].text); break; }
            _snprintf_s(l1, sizeof(l1), _TRUNCATE, "Claude-Ablauf  Schritt %d/%d%s%s", i + 1, total, counter, next);
            _snprintf_s(l2, sizeof(l2), _TRUNCATE, "%s %s: %.150s", g_flowRun[i].state == kFsRun ? "laeuft" : "jetzt",
                        truflow::kKindNames[s.kind], s.text);
            char wait[200];
            FlowWaitLocked(i, wait, sizeof(wait));
            if (wait[0]) _snprintf_s(l3, sizeof(l3), _TRUNCATE, "wartet: %s", wait);
            else if (s.hint[0]) _snprintf_s(l3, sizeof(l3), _TRUNCATE, "%s", s.hint);
        } else {
            int c[5] = {};
            for (int k = 0; k < total; ++k) ++c[g_flowRun[k].state];
            _snprintf_s(l1, sizeof(l1), _TRUNCATE, "Claude-Ablauf fertig: %d ok, %d Fehler, %d uebersprungen, %d offen", c[kFsOk],
                        c[kFsFail], c[kFsSkip], c[kFsOpen] + c[kFsRun]);
        }
    }
    LeaveCriticalSection(&g_flowLock);
    if (l1[0]) {
        bool right = g_flowPos == 1 || g_flowPos == 3, bottom = g_flowPos >= 2;
        ImVec2 at(right ? vp->WorkPos.x + vp->WorkSize.x - 10.0f : vp->WorkPos.x + 10.0f,
                  bottom ? vp->WorkPos.y + vp->WorkSize.y - 10.0f : vp->WorkPos.y + 10.0f);
        ImGui::SetNextWindowPos(at, ImGuiCond_Always, ImVec2(right ? 1.0f : 0.0f, bottom ? 1.0f : 0.0f));
        ImGui::SetNextWindowBgAlpha(0.55f);
        ImGui::SetNextWindowSizeConstraints(ImVec2(0.0f, 0.0f), ImVec2(vp->WorkSize.x * 0.6f, vp->WorkSize.y * 0.3f));
        if (ImGui::Begin("##TruMenuFlow", nullptr, flags)) {
            ImGui::SetWindowFontScale(g_flowSize);
            ImGui::PushStyleColor(ImGuiCol_Text, coral);
            ImGui::TextUnformatted(l1);
            ImGui::PopStyleColor();
            if (g_flowLines >= 2 && l2[0]) ImGui::TextUnformatted(l2);
            if (g_flowLines >= 3 && l3[0]) ImGui::TextUnformatted(l3);
        }
        ImGui::End();
    }
    if (showToast) {
        ImGui::SetNextWindowPos(ImVec2(vp->WorkPos.x + vp->WorkSize.x * 0.5f, vp->WorkPos.y + vp->WorkSize.y * 0.12f),
                                ImGuiCond_Always, ImVec2(0.5f, 0.0f));
        ImGui::PushStyleColor(ImGuiCol_WindowBg, ImVec4(coral.x, coral.y, coral.z, 0.92f));
        ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(1.0f, 1.0f, 1.0f, 1.0f));
        ImGui::SetNextWindowSizeConstraints(ImVec2(0.0f, 0.0f), ImVec2(vp->WorkSize.x * 0.7f, vp->WorkSize.y * 0.3f));
        if (ImGui::Begin("##TruMenuFlowToast", nullptr, flags)) {
            ImGui::SetWindowFontScale(g_flowSize * 1.3f);
            ImGui::TextUnformatted("Claude:");
            ImGui::TextWrapped("%s", toast);
        }
        ImGui::End();
        ImGui::PopStyleColor(2);
    }
}

// game.quit: one last summary line (no waiting for a lock a hung thread may hold)
void FlowFinal(const char *why) {
    if (!g_flowLoaded || !TryEnterCriticalSection(&g_flowLock)) return;
    int c[5] = {};
    for (int k = 0; k < g_flow.nSteps; ++k) ++c[g_flowRun[k].state];
    Log(0, "flow: end (%s) step %d/%d; %d ok, %d fail, %d skip, %d open t=%.1f", why,
        g_flowCur < g_flow.nSteps ? g_flowCur + 1 : g_flow.nSteps, g_flow.nSteps, c[kFsOk], c[kFsFail], c[kFsSkip],
        c[kFsOpen] + c[kFsRun], FlowSec());
    LeaveCriticalSection(&g_flowLock);
}

// 0.6 command bar items, defined with the bar below
void ValCmdHistory(char *o, size_t n);
void ValCmdBar(char *o, size_t n);
bool RunCmdFocus(const char *arg, char *o, size_t n);
bool RunCmdRun(const char *arg, char *o, size_t n);
bool RunCmdKeyboard(const char *arg, char *o, size_t n);   // 0.7
void ValGameQuit(char *o, size_t n);                       // 0.7.2
bool RunGameQuit(const char *arg, char *o, size_t n);
void ValRadialStatus(char *o, size_t n);                   // 0.10 radial menu, defined after the command bar
void ValRadialList(char *o, size_t n);
bool RunRadialReload(const char *arg, char *o, size_t n);
bool RunRadialOpen(const char *arg, char *o, size_t n);
void ValFreezeSound(char *o, size_t n);      // 0.10.3 (F7) sound pause items, defined after the radial freeze
void ValPauseSound(char *o, size_t n);
void ValSoundState(char *o, size_t n);
bool RunFreezeSound(const char *arg, char *o, size_t n);
bool RunPauseSound(const char *arg, char *o, size_t n);
void ValFreezeClock(char *o, size_t n);      // 0.10.4 (F7) shader clock items, defined after the sound items
void ValClockState(char *o, size_t n);
bool RunFreezeClock(const char *arg, char *o, size_t n);

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
    {"game.quit", "action", "quit the game now: run twice within 10 s (menu: or hold 1 s); logs written, then TerminateProcess(exit code "
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
    // 0.10.3 (F7): the sound with the world freeze - runtime switches over the ini keys (TruMenu.ini is not written)
    {"time.freezesound", "bool", "0.10.3 [Radial] FreezeSound: the sound pauses while the ring holds the world "
                                 "(pause menu pair 0x5874b0 / 0x5874d0; until the next start)", false, ValFreezeSound,
     RunFreezeSound},
    {"time.pausesound", "bool", "0.10.3 [Menu] PauseSound: the sound pauses with every other world pause (time.pause, "
                                "PauseGame; until the next start)", false, ValPauseSound, RunPauseSound},
    {"time.sound", "info", "0.10.3: sound pause state - switches, pause bit, gameMode, [0xccde88], last action", false,
     ValSoundState, nullptr},
    // 0.10.4 (F7, light shaft): the shader clock TimeVector with every world freeze (pause menu's 0x5bfdf0)
    {"time.freezeclock", "bool", "0.10.4 [Radial] FreezeShaderClock: the shader clock TimeVector holds while the world "
                                 "is frozen (ring or time.pause; the pause menu's 0x5bfdf0; until the next start)",
     false, ValFreezeClock, RunFreezeClock},
    {"time.clock", "info", "0.10.4: shader clock state - switch, pause bit, gameMode, [0xdb94de], RenderDevice "
                           "+0xfa4c / +0xfa48, last action", false, ValClockState, nullptr},
    {"player.control", "bool", "player control byte 0x8ab4e6 (1 = on)", true, ValControl, RunControl},
    {"player.die", "action", "INSTANCE_Post(player, 4, 3): ragdoll death, needs a level", true, ValPlayer, RunDie},
    {"player.teleport", "action", "Lara to <x> <y> <z>, needs a level", true, ValPlayer, RunTeleport},
    {"player.mark", "action", "remember Lara's position and facing (yaw, 0.10.2)", false, ValMark, RunMark},
    {"player.recall", "action", "Lara back to the mark, facing as then (movement state / velocity unchanged)", true,
     ValMark, RunRecall},
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
    // 0.9 media (P1-P3): tracks from TruMenu.media.txt (tools/music_list.py), the engine's SRMUSIC_LoadMusic
    {"media.video.flags", "info", "videos with source and referenced / unused? (TruMenu.media.txt)", false,
     ValMediaVideoFlags, nullptr},
    {"media.music.list", "info", "srmusic tracks: name (source, unused?) from TruMenu.media.txt", false, ValMusicList,
     nullptr},
    {"media.music.play", "action", "<track> [slot 0-7]: SRMUSIC_LoadMusic 0x594320(slot, name, fade, fade) as the unit "
                                   "start 0x5b2211; main menu, in a level only with [Media] MusicInLevels=1; experimental",
     true, ValMusicNow, RunMusicPlay},
    {"media.music.stop", "action", "[slot 0-7 | all]: SRMUSIC_LoadMusic(slot, NULL, fade, 0) as the stop native 0x4aa490",
     true, ValMusicNow, RunMusicStop},
    {"media.music.now", "info", "the 8 srmusic slots 0xcc5260 (+0 current, +0x100 requested, +0x51c object) and the unit "
                                "music name 0xd98f64", false, ValMusicNow, nullptr},
    {"dev.musicvars", "bool", "developer flag Show Music Vars ([0xe7f098] & 0x10000000; row from the original table)", true,
     ValMusicVars, RunMusicVars},
    {"dev.monstermusicvars", "bool", "developer flag Show Monster Music Vars ([0xe7f0a0] & 0x01000000; no reader in "
                                     "retail known)", true, ValMonsterMusicVars, RunMonsterMusicVars},
    // 0.9 saves (P0d): file operations of TruMenu; delete / restore / import: twice within 10 s, never over TruLink
    {"save.folder", "info", "the game's save folder (as tru.exe 0x78b550) and the backup folder TruMenu.saves", false,
     ValSaveFolder, nullptr},
    {"save.list", "info", "*.TRUSave: name | date | size | unit (data +0x10) | checkpoint (+0x90) | CRC check", false,
     ValSaveList, nullptr},
    {"save.backups", "info", "backup folders in TruMenu.saves (newest first, file count)", false, ValSaveBackups, nullptr},
    {"save.backup", "action", "[label]: copy every *.TRUSave into TruMenu.saves\\<time>[_label]\\", false, ValSaveFolder,
     RunSaveBackup},
    {"save.export", "action", "<save>: copy one save to TruMenu.saves\\export\\", false, ValSaveFolder, RunSaveExport},
    {"save.delete", "action", "<save>: backup of all saves (<time>_deleted), then the file is removed; run twice within "
                              "10 s; owner only", false, ValSaveFolder, RunSaveDelete},
    {"save.restore", "action", "<backup>: back up the current saves (<time>_before_restore), then copy the backup's files "
                               "in (others stay); twice within 10 s; owner only", false, ValSaveFolder, RunSaveRestore},
    {"save.import", "action", "<name>: TruMenu.saves\\import\\<name>.TRUSave into the save folder (CRC checked, the old "
                              "state backed up first); twice within 10 s; owner only", false, ValSaveFolder, RunSaveImport},
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
    // 0.8 Regression page
    {"regress.list", "info", "regression lists dlc1 / dlc2: counts, id [state] {note}", false, ValRegressList, nullptr},
    {"regress.load", "action", "dlc1|dlc2|all: (re)load TruMenu.regress_<list>.txt (rows open again) and select it on the "
                               "Regression page", false, ValRegressList, RunRegressLoad},
    {"regress.mark", "action", "<dlc1:id|dlc2:id|id> ok|fail|skip|open [note] (steps done|open); appends to "
                               "TruMenu.regress_results.txt", false, ValRegressList, RunRegressMark},
    {"regress.note", "action", "<dlc1:id|dlc2:id|id> <text>: note of a regression row (result line appended)", false,
     ValRegressList, RunRegressNote},
    {"regress.export", "info", "both regression lists as a block (list kind id state number target hint note time)", false,
     ValRegressExport, nullptr},
    // 0.8 Cheats page (docs Befund-Prototyp-2007 3i; game thread, needs a level, [Cheats] Enabled)
    {"cheat.list", "info", "every cheat row with its category and state / reason (incl. the rows not built yet)", false,
     ValCheatList, nullptr},
    {"cheat.god", "bool", "god mode: gInvincibleCheat 0xfadf60 (ProcessHealth keeps the hit timer full; types 8 / 5 and "
                          "instant deaths pass) [PC has it]", true, ValCheatGod, RunCheatGod},
    {"cheat.godfull", "bool", "god mode + the player's no-damage bit 0xfada74 & 0x20000 per frame (ApplyDamage returns, "
                              "also types 8 / 5; no flight since 0.10.2; instant deaths still kill) [PC has it]", true,
     ValCheatGodFull, RunCheatGodFull},
    {"cheat.onehitkill", "bool", "one-hit kill 0xe91ffd through ENEMY_ToggleOneHitKill 0x60f670 [PC has it]", true,
     ValCheatOhk, RunCheatOhk},
    {"cheat.enemyhealth", "bool", "show enemy health 0xe91ffc (EnemyProcessFunc prints hit points) [PC has it]", true,
     ValCheatEnemyHp, RunCheatEnemyHp},
    {"cheat.ammo", "bool", "infinite ammo: weapon data INSTANCE_Query(inst, 0x36)+0x88 |= 0x80 per slot weapon "
                           "[re-attach]", true, ValCheatAmmo, RunCheatAmmo},
    {"cheat.fillup", "action", "fill 'er up: GainHealth 0x6f4ef0(MaxHealth, 0) + ammo.fill [re-attach]", true, ValHealth,
     RunCheatFill},
    {"cheat.code", "action", "<1|2|9|10|11>: DEBUG_ApplyCheatCode 0x5d3520(code) as a completed pad code (1 one-hit kill, "
                             "2 god, 9 wireframe, 10 textureless, 11 enemy health)", true, ValCheatCode, RunCheatCode},
    // 0.8 camera log
    {"camera.log", "bool", "log camera manager mode / current camera changes ([Log] CameraChanges, read-only)", false,
     ValCameraLog, RunCameraLog},
    // 0.8.1
    {"player.unstuck", "action", "Lara to the newer of player.mark and the last safe ground spot (>= 3 s old, >= 150 "
                                 "units away; again within 20 s = one further back); arg mark|safe; 0.10.2: no sampling "
                                 "in menu / ring / pause / cinematic, chord + slope ground test, yaw kept", true,
     ValUnstuck, RunUnstuck},
    {"player.safeground", "info", "0.10.2: the player.unstuck state - safe spots, ground windows passed / failed, why "
                                  "the sampler waits now (read-only)", false, ValUnstuck, nullptr},
    {"regress.prepare", "action", "<dlc1:id|dlc2:id|id>: run that regression row's shortcut (column 9: level.load, "
                                  "cheat.god ... one after the other, level changes waited for) | stop", false,
     ValShortcut, RunRegressPrepare},
    {"regress.shortcuts", "info", "every regression row with a shortcut (list:id = #title;commands)", false,
     ValRegressShortcuts, nullptr},
    {"log.inputtrace", "bool", "a TruMenu.log line per pad edge / click / key while the menu is open, with what the menu "
                               "did ([Log] InputTrace; needs LogLevel 2)", false, ValInputTrace, RunInputTrace},
    // 0.10 radial menu ([Radial]; TruMenu.radial.txt next to tru.exe) and stage R2
    {"radial.status", "info", "radial menu: [Radial] options, file, entries / levels, dropped / unknown ids, state", false,
     ValRadialStatus, nullptr},
    {"radial.list", "info", "every radial entry: path | label | item [arg] (= greyed: reason)", false, ValRadialList,
     nullptr},
    {"radial.reload", "action", "read TruMenu.radial.txt again (ring closed)", false, ValRadialStatus, RunRadialReload},
    {"radial.open", "action", "[path]: open the ring latched (at that level), e.g. for a test without the pad", false,
     ValRadialStatus, RunRadialOpen},
    {"instance.spawn", "action", "<object>: R2, needs [Radial] Spawn=1: DRM check 0x5bf7b0, tracker 0x5c17d0, poll 0x5c1da0 "
                                 "until loaded, INSTANCE_BirthObjectNoParent 0x5bd0f0 at Lara (game thread, experimental)",
     true, ValSpawn, RunInstanceSpawn},
    // 0.10.5 [Shot]: screenshots of the next frame (render thread copy, PNG on a worker) and Claude marks
    {"shot.save", "action", "0.10.5 [ui|clean] [name]: screenshot of the next frame as [Shot] Folder\\shot_<HHMMSS>_<TO TEST "
                            "step>_<name>.png (clean = before TruMenu draws, default [Shot] Clean=1); over TruLink the "
                            "answer waits for the copy (2 s)", false, ValShot, RunShotSave},
    {"shot.status", "info", "0.10.5: [Shot] options, folder, shots written / failed / refused, last file and last error",
     false, ValShot, nullptr},
    {"claude.mark", "action", "0.10.5 <now|good|bug|gfx|sound|stutter>: TruMenu.log line 'claude.mark <kind>: <time> unit= "
                              "pos= step= shot= src=' + a clean shot named <kind> (ring level Claude; [Shot] Hotkey = "
                              "now)", false, ValMarks, RunClaudeMark},
    // 0.11 Ablauf (TruMenu.flow.txt, [Flow] Enabled=1): ring level Claude, TruLink "menu flow.<x>"
    {"flow.status", "info", "0.11: the flow - file, step n/m with its state / what it waits for, results, deaths, counters",
     false, ValFlowStatus, nullptr},
    {"flow.list", "info", "0.11: every flow step: n id kind state by (> = the current one)", false, ValFlowList, nullptr},
    {"flow.next", "action", "0.11 Weiter: the current step - action: run its do= commands (the shortcut path, level changes "
                            "waited for), mark: done, observe: left open; then the next step", false, ValFlowStatus,
     RunFlowNext},
    {"flow.back", "action", "0.11 Zurueck: the step before is current again (reopened)", false, ValFlowStatus, RunFlowBack},
    {"flow.skip", "action", "0.11 [<id> [reason]]: skip that step (no id = the current one, ring: Ueberspringen)", false,
     ValFlowStatus, RunFlowSkip},
    {"flow.goto", "action", "0.11 <id>: that step is current (reopened when it had a result)", false, ValFlowStatus,
     RunFlowGoto},
    {"flow.add", "action", "0.11 <record>: append a 'counter | ...' or 'step | ...' record (TruMenu.flow.txt syntax)", false,
     ValFlowStatus, RunFlowAdd},
    {"flow.say", "action", "0.11 <text>: a toast in Claude's coral for [Flow] ToastSeconds + a 'flow: say' log line", false,
     ValFlowStatus, RunFlowSay},
    {"flow.result", "action", "0.11 ok|fail [note]: the current step's result = claude.mark good / bug (mark line + clean "
                              "shot)", false, ValFlowStatus, RunFlowResult},
    {"flow.reload", "action", "0.11: read the flow file again (every step and counter starts anew)", false, ValFlowStatus,
     RunFlowReload},
    // 0.12 Debug-Zeichnung ([Debug] Enabled; the NavPower debug switches of tru.exe - data bytes only, a loaded level)
    {"nav.status", "info", "0.12: NavPower debug drawing - [Debug], checks, CDCRenderer / line buffer / NavPower state, "
                           "layer mask, layers, every switch", false, ValNavStatus, nullptr},
    {"nav.draw", "action", "0.12 <switch> [0|1]: one NavPower debug switch - planner_areas, planner_areas_solid, "
                           "planner_connectivity, planner_area_normals, obstacles, recent_navprobes, draw_mover3d_path "
                           "(no 0 / 1 = flip)", false, ValNavDraw, RunNavDraw},
    {"nav.mask", "bool", "0.12: planner layer mask [0x88e454] = 0xffffffff (every layer drawn); 0 = the value before",
     false, ValNavMask, RunNavMask},
    {"nav.off", "action", "0.12: every NavPower switch TruMenu set and the layer mask back to the values before", false,
     ValNavDraw, RunNavOff},
    // 0.13 Thrall-Labels ([Debug] Enabled; read-only, drawn at Present in a loaded level)
    {"dbg.labels", "bool", "0.13: Thrall-Labels - name, intro id, distance, health, targeter 9 / hit list / condition 2011 "
                           "(TruShadowCombat 0.5.3) at each thrall near Lara", false, ValLabels, RunLabels},
    // 0.14 Debug view ([Debug] Enabled; read-only, drawn at Present in a loaded level, also during the flight)
    {"dbg.view", "bool", "0.14: master switch - every 0.14 layer + dbg.labels + draw.markup + the [Debug] ViewNav "
                         "switches on / off (nav.off); each one stays switchable alone", false, ValDvView, RunDvView},
    {"dbg.triggers", "bool", "0.14: trigger wireframes of every kind (the game's plane / volume lists: box, sphere, "
                             "plane quad, coloured by kind)", false, ValDvTriggers, RunDvTriggers},
    {"dbg.show", "action", "0.14 <layer> [0|1]: one layer - death, fire, checkpoint, water, sound, volume, plane, unknown "
                           "(trigger kinds), portals, checkpoints, trglabels, legend (no 0 / 1 = flip)", false, ValDvShow,
     RunDvShow},
    {"dbg.portals", "bool", "0.14: loading areas - the stream portal quads of every loaded unit (-> destination unit)",
     false, ValDvPortals, RunDvPortals},
    {"dbg.checkpoints", "bool", "0.14: checkpoint objects (instances named *checkpoint*), the active one (game data "
                                "+0x90 / +0x114) in yellow", false, ValDvCheckpoints, RunDvCheckpoints},
    {"dbg.legend", "bool", "0.14: legend top right - every layer that is on, its colour, drawn / found", false,
     ValDvLegend, RunDvLegend},
    {"dbg.status", "info", "0.14: debug view checks, layers on, what the last frame drew", false, ValDvStatus, nullptr},
    {"dbg.names", "bool", "0.14: object names - the name (live PC object list) and intro id of every instance matching "
                          "[Debug] NameMatch, nearest to the camera first", false, ValDvNames, RunDvNames},
    {"dbg.namefilter", "action", "0.14 <list|*>: object names only for names containing one of the comma-separated parts "
                                 "(e.g. thrall); * = every instance", false, ValDvNameFilter, RunDvNameFilter},
    {"dbg.namecolour", "action", "0.14 white|yellow|cyan|magenta|RRGGBB: colour of the object names", false,
     ValDvNameColour, RunDvNameColour},
    {"dbg.namesize", "action", "0.14 <0.5 .. 3>: font size factor of the object names", false, ValDvNameSize,
     RunDvNameSize},
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

// game thread: run the queued request.
// 0.8.1 (P00c, cheat.flight 1 at 22:19:54.690 and 0 at .706 from ONE "queued"): 0.8.0 tested g_reqPending outside the
// lock and never again inside it. A second caller that passed the test while the first one ran (PadHook on another
// thread, the Present fallback, or PadHook re-entered from the item through the pad poll - g_reqLock is recursive for
// the same thread) waited for the lock and then ran the same request again; a toggle ("" = flip) flipped back. Now the
// request is claimed atomically (1 = queued -> 2 = running): whoever loses the exchange returns, so a request runs
// exactly once. Enqueue / the waiting callers treat 2 like 1 (still pending).
void RunPending() {
    if (InterlockedCompareExchange(&g_reqPending, 2, 1) != 1) return;
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
    if (item && wait && SaveOwnerOnly(item->id)) {             // 0.9: save folder changes only by the owner
        Log(1, "%s refused: TruLink / cmd.run (owner only: menu, command bar)", item->id);
        _snprintf_s(t_answer, sizeof(t_answer), _TRUNCATE, "err %s only from the menu or the command bar (owner) - never "
                    "over TruLink", item->id);
        return t_answer;
    }
    if (item && !_stricmp(item->id, "test.export")) {          // 0.5: a block answer ("ok+ ...", rows, ".")
        TestExportBlock(t_answer, sizeof(t_answer));
        return t_answer;
    }
    if (item && !_stricmp(item->id, "regress.export")) {       // 0.8: the same block form for the regression lists
        RegressExportBlock(t_answer, sizeof(t_answer));
        return t_answer;
    }
    if (item && !_stricmp(item->id, "cmd.run"))                // 0.6: the answer of the line's own item
        return CmdRunLine(arg ? arg : "", wait, "TruLink");
    if (item && item->run) FlowOnItem(item->id);                // 0.11: item:<id> counters (an event only)
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
// Safety step: the first run arms it, a second run 0.3 .. 10 s later quits (0.8.1: 10 s, was 5; in the menu also a
// button held 1 s). Runs on the calling thread (render hook / command bar - not the game thread, which may hang). TerminateProcess, not ExitProcess: no DLL detach / atexit that
// could block on a hung thread. Never automatic: InvokeCore refuses it over TruLink, nothing in TruMenu queues it.
const UINT kQuitExitCode = 0x544D;          // "TM"; Invoke-TruTestRun.ps1 maps 21581 to "ended via TruMenu game.quit"
const DWORD kQuitWindowMs = 10000, kQuitMinGapMs = 300;
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
    else Out(o, n, "not armed (run twice within 10 s)");
}
DWORD QuitNow() {                            // returns only when TerminateProcess failed (its error)
    Log(0, "game.quit by the owner (TruMenu) - logs flushed next, then TerminateProcess(GetCurrentProcess(), 0x%x)",
        kQuitExitCode);
    FlowFinal("game.quit");                  // 0.11: the flow's last summary line
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
        Log(1, "game.quit armed by the owner - run it again within 10 s to end the game");
        Out(o, n, "armed - run game.quit again within 10 s to end the game (TerminateProcess, exit code 0x544D)");
        return true;
    }
    if (age < kQuitMinGapMs) {
        Log(1, "game.quit: second press too fast (%lu ms) - still armed", age);
        Out(o, n, "armed - second press too fast (%lu ms), press again", age);
        return true;
    }
    InterlockedExchange(&g_quitArmedAt, 0);
    DWORD error = QuitNow();
    Out(o, n, "TerminateProcess failed (%lu) - see TruMenu.log", error);
    return false;
}
// 0.8.1: a game.quit button in the menu held 1 s (A / Enter / Space / mouse) - the hold is the safety step
void QuitByHold() {
    Log(1, "game.quit: button held 1 s by the owner");
    InterlockedExchange(&g_quitArmedAt, 0);
    DWORD error = QuitNow();
    SetLastAction("game.quit", false, "TerminateProcess failed - see TruMenu.log");
    (void)error;
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
bool CmdTextActive() { return g_cmdTextActive; }   // 0.8.1 input trace (FeedGamepad is above)
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
            char *note = g_trf[g_trfCur].barNote;     // 0.8.1 input trace: what the bar did with the press
            size_t noteSize = sizeof(g_trf[g_trfCur].barNote);
            if ((e & 0x2000) && g_oskBackClosed) {       // 0.7.1: B closed the keyboard, this B closes the menu
                g_oskBackClosed = false;
                if (g_menuOpen) ToggleMenu("B twice: keyboard, then menu");
                e = 0;
                Out(note, noteSize, "B twice - the keyboard was closed, this B closed the menu");
            } else if (e & 0x200F) {                     // D-pad / stick / B: into the menu
                leave = true;
                // 0.7 FirstPadPressOnlyFocuses=0: the direction also moves in the menu (FeedGamepad hands it over)
                if (!g_cmdFirstPressFocus && (e & 0x000F)) g_cmdHandOver = true;
                Out(note, noteSize, (e & 0x000F) && g_cmdFirstPressFocus ? "focus from the bar into the menu - swallowed "
                    "by FirstPadPressOnlyFocuses (this press only moves the focus)" : "focus from the bar into the menu");
            } else if (e & 0x1000) {                     // A: run the typed line, empty = into the menu
                if (g_cmdTextActive && g_cmdBuf[0]) { runNow = true; Out(note, noteSize, "A ran the typed line"); }
                else if (g_cmdTextActive) { leave = true; Out(note, noteSize, "A on the empty line: focus into the menu"); }
                else if (g_cmdKeyboard) {                // 0.7: A in the idle bar = the on-screen keyboard
                    g_oskOpen = true;
                    OskEdited();
                    g_oskRow = 3;
                    g_oskCol = 0;
                    Out(note, noteSize, "A in the idle bar opened the on-screen keyboard");
                } else { wantFocus = true; Out(note, noteSize, "A focused the text field"); }
            } else if (e & 0x0020) {                     // View: pad picker
                Out(note, noteSize, "View: pad picker");
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
        if (TmButton("Pick (View)")) { g_cmdPadMode = true; g_pickMode = 0; }
        // 0.8.1: Enter only counts as a fresh press - a held / stuck Enter (ImGui's key repeat) ran the line every
        // 100 ms (run 224047: 70 "empty line" answers and single letters "u", "i", "." while the owner typed)
        if (enter && !ImGui::IsKeyPressed(ImGuiKey_Enter, false) && !ImGui::IsKeyPressed(ImGuiKey_KeypadEnter, false)) {
            enter = false;
            strncpy_s(g_cmdSetText, sizeof(g_cmdSetText), g_cmdBuf, _TRUNCATE);   // keep the text, stay in the field
            g_cmdSetPending = true;
            InterlockedExchange(&g_cmdFocusReq, 1);
            Log(3, "cmd: Enter repeat ignored");
        }
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

// ======================================================================================================================
// 0.10 radial menu (workspace docs\Konzept-Bau-Rad.md, stage R1; R2 = instance.spawn above): a faster way to run the
// existing items. Entries come from TruMenu.radial.txt next to tru.exe ("path | label | item id [argument]", # comments);
// a level holds the folders of its sub-paths and its entries in file order, at most 8 sectors per page (LB / RB). The
// ring is drawn into ImGui's foreground draw list (no window, no ImGui navigation); the input is read raw: the right stick
// of the last pad (g_pad, before PadHook neutralises it) or the mouse direction since the open (GetCursorPos), A / B /
// LB / RB / R3 edges of that pad, left / right click. An entry runs through InvokeCore (wait = false) - the command bar's
// path: game-thread items are queued, their answer arrives as "last action". Hold mode (buttons / key / mouse button
// still held): the stick picks live, the release runs the picked entry (a folder: enters it and the ring stays open,
// "latched"), the centre = cancel. Latched: the pick stays when the stick springs back (the thumb goes to A), A runs and
// stays, R3 alone runs and closes, the hold buttons again = hold mode. That is [Radial] Mode=wheel since 0.10.1.
// 0.10.1 [Radial] Mode=menu (default, owner wish 2026-11-03 "like a menu, not a weapon wheel"; workspace
// docs\Konzept-Bau-Rad.md section 10): the ring opens latched (state 2) and stays open; the left stick, the right stick,
// the D-pad left / right, the arrow keys and the mouse direction only move the pick; nothing runs on a release or by
// pointing - A / Enter / left click runs the pick or opens its level, B / Backspace / Esc / right click goes one level
// back (closes at the top), LB / RB pages, L3 + R3 / Key / MouseButton again closes. The game gets a neutral pad and no
// keys while it is open. [Radial] Freeze: world = the time.pause bit (as [Menu] PauseGame), player = player.control 0,
// both undone at the close unless the user ran that item meanwhile. A built-in last sector of the top level, "Spiel
// beenden" ([Radial] QuitSector=1, never from the file), runs game.quit with the safety step of the Status page button.
// ======================================================================================================================
const int kRadMaxItems = 256, kRadMaxLevels = 48, kRadPerLevel = 64, kRadPerPage = 8;
const float kPi = 3.14159265f;
enum { kRadSpecialNone = 0, kRadSpecialQuit = 1, kRadSpecialVirt = 2 };
// 0.10.1 Tests level (owner request 2026-11-03): the levels below "Tests" (TO TEST, Regression, Prepare, Schalter) are
// virtual - one reserved level slot (g_radVirtLevel) whose entries are made every frame from the existing lists
// (g_tests, g_reg, g_regShortcut under g_testLock); every action calls the function of the TO TEST / Regression page
// (TestMarkFromMenu, RegMarkFromMenu, QueueItem, RunRegressPrepare) - no second copy of a list. "Rundgang" is a real
// level read from TruMenu.tour.txt (the radial file format) below Tests/Rundgang.
enum RadVirt {
    kRvNone = 0, kRvTodo, kRvTodoRow, kRvRegLists, kRvReg, kRvRegRow, kRvPrepare, kRvToggles,   // virtual levels
    kRaRun, kRaOk, kRaFail, kRaSkip, kRaDone, kRaHint, kRaPrepare, kRaStop, kRaToggle           // virtual actions
};
struct RadItem {
    char label[48], id[48], arg[96], path[96];
    int child;                               // level of a folder entry, -1 = an item entry
    int line;                                // line in the file (0 = folder made from a path / built-in)
    const char *bad;                         // unknown item / todo found at load ("" = fine)
    int special;                             // 0.10.1: kRadSpecialQuit "Spiel beenden", kRadSpecialVirt (Tests level)
    int vkind, vlist, von;                   // 0.10.1 virtual entries: RadVirt kind, regression list, toggle state
    char info[160];                          // 0.10.1: text for the centre when picked (row hint), "" = id + arg
};
// entries of the virtual level (after the file entries in g_radItems) = all TO TEST rows; a file level keeps at most
// kRadPerLevel (RadAppend), only the virtual slot uses the rest of items[]
const int kRadVirtMax = kTestMax;
struct RadLevel { char path[96]; int parent; int count; short items[kRadVirtMax]; };
RadItem g_radItems[kRadMaxItems + kRadVirtMax];
RadLevel g_radLevels[kRadMaxLevels];
int g_radItemCount = 0, g_radLevelCount = 1, g_radDropped = 0, g_radUnknown = 0, g_radSkipped = 0;
char g_radFilePath[MAX_PATH] = "", g_radFileState[64] = "not read";
CRITICAL_SECTION g_radLock;                  // items / levels (render thread, radial.reload / radial.list callers)
int g_radLevel = 0, g_radPage = 0, g_radSel = -1;   // render thread; kept over a close with RememberPosition=1
bool g_radMoved = false;                     // the stick / mouse left the centre since this page was shown
char g_radResult[320] = "";
DWORD g_radResultTick = 0;
float g_radSlowBefore = -1.0f;               // time.scale before the open (SlowMotion), -1 = nothing to restore
volatile LONG g_radOpenReq = 0;              // radial.open: open latched at g_radOpenPath (render thread)
char g_radOpenPath[96] = "";
LONG g_radRuns = 0;
POINT g_radMouseOrigin = {};
float g_radMouseDx = 0.0f, g_radMouseDy = 0.0f;
// never offered in the ring (owner rule: game.quit is button-only; the others need the owner's second press or would
// chain other commands); tools/trumenu_ini_check.py has the same list
const char *const kRadForbidden[] = {"game.quit", "cmd.run", "save.delete", "save.restore", "save.import",
                                     "settings.reset"};
// 0.10.1 built-in quit sector: armed by the first confirm press (render thread only - RadialTick, from the real pad /
// keyboard / mouse; no item, no TruLink command, no list reaches it), own arm time (the Status page button keeps
// g_quitArmedAt). The ring has no ImGui widgets, so the 0.8.1 id lesson (fixed "###" ids) is kept the other way round:
// the arm belongs to the sector's item index, never to its label (the label shows the seconds left).
const char *const kRadQuitLabel = "Spiel beenden";
int g_radQuitItem = -1;                      // index in g_radItems, -1 = no quit sector
int g_radTests = 1;                          // [Radial] TestsLevel
int g_radTestsLevel = -1, g_radVirtLevel = -1;   // the real level "Tests", the reserved virtual slot
int g_radTestsItems[4] = {-1, -1, -1, -1};   // the virtual folders in Tests (labels with counts, refreshed)
int g_rvKind = kRvNone, g_rvList = 0, g_rvRowList = 0;   // the virtual level shown: kind, list view, the row's list
char g_rvRow[64] = "";                       // the row id of kRvTodoRow / kRvRegRow
char g_radTourPath[MAX_PATH] = "", g_radTourState[64] = "not read";
void TestMarkFromMenu(const char *id, const char *state);              // TO TEST page, below
void RegMarkFromMenu(int list, const char *id, const char *state);     // Regression page, below
bool TestRunTarget(const char *target, char *itemId, size_t idSize, const char **runArg);
DWORD g_radQuitArmedAt = 0;                  // GetTickCount of the arming press, 0 = not armed
DWORD g_radQuitHoldFrom = 0;                 // confirm held on the armed sector since (A / Enter / left button), 0 = no
const char *g_radFreezeState = "-";          // radial.status: what the last open froze

bool RadForbidden(const char *id) {
    for (const char *f : kRadForbidden)
        if (!_stricmp(f, id)) return true;
    return false;
}

void RadTrim(char *s) {
    size_t len = strlen(s);
    while (len && (s[len - 1] == ' ' || s[len - 1] == '\t' || s[len - 1] == '\r' || s[len - 1] == '\n')) s[--len] = 0;
    size_t lead = 0;
    while (s[lead] == ' ' || s[lead] == '\t') ++lead;
    if (lead) memmove(s, s + lead, len - lead + 1);
}

// adds item <e> to level <level>; false (with a log line) when a limit is reached
bool RadAppend(int level, const RadItem &e) {
    RadLevel &l = g_radLevels[level];
    if (g_radItemCount >= kRadMaxItems || l.count >= kRadPerLevel) {
        Log(0, "radial: line %d: more than %d entries (or %d in one level) - '%s' skipped", e.line, kRadMaxItems,
            kRadPerLevel, e.label);
        ++g_radSkipped;
        return false;
    }
    g_radItems[g_radItemCount] = e;
    l.items[l.count++] = static_cast<short>(g_radItemCount++);
    return true;
}

// the level of <path> ("A/B"), created with its folder entries on the way; -1 when a limit is reached
int RadLevelFor(const char *path, int line) {
    int level = 0;
    char copy[96];
    strncpy_s(copy, sizeof(copy), path, _TRUNCATE);
    char *context = nullptr;
    for (char *seg = strtok_s(copy, "/", &context); seg; seg = strtok_s(nullptr, "/", &context)) {
        RadTrim(seg);
        if (!seg[0]) continue;
        int found = -1;
        const RadLevel &l = g_radLevels[level];
        for (int i = 0; i < l.count && found < 0; ++i) {
            const RadItem &f = g_radItems[l.items[i]];
            if (f.child >= 0 && !_stricmp(f.label, seg)) found = f.child;
        }
        if (found < 0) {
            if (g_radLevelCount >= kRadMaxLevels) {
                Log(0, "radial: line %d: more than %d levels - '%s' skipped", line, kRadMaxLevels, path);
                ++g_radSkipped;
                return -1;
            }
            RadLevel &nl = g_radLevels[g_radLevelCount];
            _snprintf_s(nl.path, sizeof(nl.path), _TRUNCATE, "%s%s%s", l.path, l.path[0] ? "/" : "", seg);
            nl.parent = level;
            nl.count = 0;
            RadItem folder = {};
            strncpy_s(folder.label, sizeof(folder.label), seg, _TRUNCATE);
            strncpy_s(folder.path, sizeof(folder.path), l.path, _TRUNCATE);
            folder.child = g_radLevelCount;
            folder.bad = "";
            if (!RadAppend(level, folder)) return -1;
            found = g_radLevelCount++;
        }
        level = found;
    }
    return level;
}

// the lines of a radial-format file ("path | label | item id [argument]") into the levels below <prefix> ("" = top;
// 0.10.1 "Tests/Rundgang" for TruMenu.tour.txt); <src> names the file in the log lines ("" = TruMenu.radial.txt)
void RadialParse(FILE *f, const char *prefix, const char *src, int *dropped, int *unknown, int *skipped) {
    char line[512];
    int number = 0;
    while (fgets(line, sizeof(line), f)) {
        ++number;
        RadTrim(line);
        if (!line[0] || line[0] == '#') continue;
        char *p1 = strchr(line, '|');
        char *p2 = p1 ? strchr(p1 + 1, '|') : nullptr;
        if (!p1 || !p2 || strchr(p2 + 1, '|')) {
            Log(0, "radial: %sline %d: want \"path | label | item id [argument]\" - skipped", src, number);
            ++*skipped;
            continue;
        }
        *p1 = *p2 = 0;
        char path[96], cmd[160];
        RadItem e = {};
        e.child = -1;
        e.line = number;
        e.bad = "";
        strncpy_s(path, sizeof(path), line, _TRUNCATE);
        strncpy_s(e.label, sizeof(e.label), p1 + 1, _TRUNCATE);
        strncpy_s(cmd, sizeof(cmd), p2 + 1, _TRUNCATE);
        RadTrim(path);
        RadTrim(e.label);
        RadTrim(cmd);
        char *space = strchr(cmd, ' ');
        if (space) {
            *space = 0;
            strncpy_s(e.arg, sizeof(e.arg), space + 1, _TRUNCATE);
            RadTrim(e.arg);
        }
        strncpy_s(e.id, sizeof(e.id), cmd, _TRUNCATE);
        if (!e.id[0] || !e.label[0]) {
            Log(0, "radial: %sline %d: empty label or item id - skipped", src, number);
            ++*skipped;
            continue;
        }
        if (RadForbidden(e.id)) {
            Log(0, "radial: %sline %d: %s is never offered in the radial menu - dropped", src, number, e.id);
            ++*dropped;
            continue;
        }
        CmdKind kind = CmdKindOf(e.id);
        if (kind == kCkUnknown || kind == kCkBuiltin) {
            e.bad = "unknown item";
            Log(0, "radial: %sline %d: unknown item '%s' - entry greyed out", src, number, e.id);
            ++*unknown;
        } else if (kind == kCkTodo) {
            e.bad = "todo item";
        }
        char full[192];
        _snprintf_s(full, sizeof(full), _TRUNCATE, "%s%s%s", prefix, prefix[0] && path[0] ? "/" : "", path);
        int level = RadLevelFor(full, number);
        if (level < 0) continue;
        strncpy_s(e.path, sizeof(e.path), g_radLevels[level].path, _TRUNCATE);
        RadAppend(level, e);
    }
}

// 0.10.1 Tests level (Mode=menu, [Radial] TestsLevel=1): the real level "Tests" with four virtual folders (their
// entries come from the TO TEST / regression lists, RadVirtBuild) and the real level "Rundgang" from TruMenu.tour.txt
void RadialAddTests() {
    g_radTestsLevel = g_radVirtLevel = -1;
    for (int &i : g_radTestsItems) i = -1;
    g_rvKind = kRvNone;
    if (g_radMode != kRadModeMenu || !g_radTests) return;
    int tests = RadLevelFor("Tests", 0);
    if (tests < 0) return;
    if (g_radLevelCount >= kRadMaxLevels) {
        Log(0, "radial: more than %d levels - no room for the Tests level", kRadMaxLevels);
        return;
    }
    g_radTestsLevel = tests;
    g_radVirtLevel = g_radLevelCount++;
    RadLevel &v = g_radLevels[g_radVirtLevel];
    v.path[0] = 0;
    v.parent = tests;
    v.count = 0;
    const struct { const char *label; int kind; } folders[] = {
        {"TO TEST", kRvTodo}, {"Regression", kRvRegLists}, {"Prepare", kRvPrepare}, {"Schalter", kRvToggles}};
    for (int k = 0; k < 4; ++k) {
        RadItem e = {};
        strncpy_s(e.label, sizeof(e.label), folders[k].label, _TRUNCATE);
        strncpy_s(e.path, sizeof(e.path), "Tests", _TRUNCATE);
        e.child = g_radVirtLevel;
        e.bad = "";
        e.special = kRadSpecialVirt;
        e.vkind = folders[k].kind;
        if (!RadAppend(tests, e)) return;
        g_radTestsItems[k] = g_radItemCount - 1;
    }
    int tour = RadLevelFor("Tests/Rundgang", 0);
    int dropped = 0, unknown = 0, skipped = 0, before = g_radItemCount;
    FILE *f = nullptr;
    if (tour < 0) {
        strncpy_s(g_radTourState, sizeof(g_radTourState), "no room for the level", _TRUNCATE);
    } else if (fopen_s(&f, g_radTourPath, "r") != 0 || !f) {
        strncpy_s(g_radTourState, sizeof(g_radTourState), "missing - Rundgang is empty", _TRUNCATE);
        Log(0, "radial: tour %s not found - Rundgang is empty (Set-TruMenu.ps1 -Install copies it)", g_radTourPath);
    } else {
        RadialParse(f, "Tests/Rundgang", "tour ", &dropped, &unknown, &skipped);
        fclose(f);
        int items = 0;
        for (int i = before; i < g_radItemCount; ++i) if (g_radItems[i].child < 0) ++items;
        _snprintf_s(g_radTourState, sizeof(g_radTourState), _TRUNCATE, "%d stops / entries", items);
        Log(1, "radial: tour %d entries from %s (%d dropped, %d unknown, %d lines skipped)", items, g_radTourPath, dropped,
            unknown, skipped);
    }
}

// 0.10.1: the built-in sectors after the file (caller holds g_radLock): the Tests level, then "Spiel beenden" as the
// last entry of the top level (Mode=menu; each counts as one of the 8 sectors, more than 8 top entries = pages)
void RadialAddBuiltins() {
    g_radQuitItem = -1;
    g_radQuitArmedAt = g_radQuitHoldFrom = 0;
    RadialAddTests();
    if (g_radMode != kRadModeMenu || !g_radQuitSector) return;
    RadItem q = {};
    strncpy_s(q.label, sizeof(q.label), kRadQuitLabel, _TRUNCATE);
    q.child = -1;
    q.bad = "";
    q.special = kRadSpecialQuit;
    if (!RadAppend(0, q)) return;
    g_radQuitItem = g_radItemCount - 1;
    Log(1, "radial: built-in top sector '%s' (game.quit: A arms, A again within %lu s or A held 1 s quits) - %d top "
        "sector(s), %d page(s)", kRadQuitLabel, kQuitWindowMs / 1000, g_radLevels[0].count,
        (g_radLevels[0].count + kRadPerPage - 1) / kRadPerPage);
}

// reads TruMenu.radial.txt (caller holds g_radLock); unknown ids stay as greyed entries, forbidden ones are dropped
void RadialLoad() {
    g_radQuitItem = -1;
    g_radItemCount = 0;
    g_radLevelCount = 1;
    g_radDropped = g_radUnknown = g_radSkipped = 0;
    g_radLevels[0].path[0] = 0;
    g_radLevels[0].parent = -1;
    g_radLevels[0].count = 0;
    g_radLevel = g_radPage = 0;
    g_radSel = -1;
    FILE *f = nullptr;
    if (fopen_s(&f, g_radFilePath, "r") != 0 || !f) {
        strncpy_s(g_radFileState, sizeof(g_radFileState), "missing - the ring is empty", _TRUNCATE);
        Log(0, "radial: %s not found - the ring is empty (Set-TruMenu.ps1 -Install copies the default file)", g_radFilePath);
        RadialAddBuiltins();
        return;
    }
    RadialParse(f, "", "", &g_radDropped, &g_radUnknown, &g_radSkipped);
    fclose(f);
    int items = 0;
    for (int i = 0; i < g_radItemCount; ++i) if (g_radItems[i].child < 0) ++items;
    _snprintf_s(g_radFileState, sizeof(g_radFileState), _TRUNCATE, "%d entries, %d levels", items, g_radLevelCount);
    Log(1, "radial: %d entries in %d levels from %s (%d dropped, %d unknown, %d lines skipped)", items, g_radLevelCount,
        g_radFilePath, g_radDropped, g_radUnknown, g_radSkipped);
    RadialAddBuiltins();
}

// why an entry is greyed out right now ("" = usable): the item's byte pre-check, the INI switches, a level
const char *RadialWhy(const RadItem &e) {
    if (e.child >= 0 || e.special) return "";
    if (e.bad[0]) return e.bad;
    const char *id = e.id;
    const char *flowWhy = FlowRadWhy(id);   // 0.11: flow.* entries need a loaded flow
    if (flowWhy[0]) return flowWhy;
    const struct { const char *id; bool ok; const char *why; } cheats[] = {
        {"cheat.god", g_godOk, g_godWhy}, {"cheat.godfull", g_godFullOk, g_godFullWhy},
        {"cheat.onehitkill", g_ohkOk, g_ohkWhy}, {"cheat.enemyhealth", g_enemyHpOk, g_enemyHpWhy},
        {"cheat.ammo", g_infAmmoOk, g_infAmmoWhy}, {"cheat.fillup", g_fillOk, g_fillWhy}, {"cheat.code", g_codeOk, g_codeWhy}};
    for (const auto &c : cheats) {
        if (_stricmp(id, c.id) != 0) continue;
        if (!g_cheatsEnabled) return "cheats off ([Cheats] Enabled=0)";
        if (!c.ok) return c.why;
    }
    if (!_stricmp(id, "instance.spawn")) {
        if (!SpawnOn()) return "[Radial] Spawn=0 (stage R2 off)";
        if (!g_spawnOk) return g_spawnWhy;
    }
    if (!_stricmp(id, "weapon.give") && !g_weaponOk) return "weapon.give code not verified";
    if (!_stricmp(id, "ammo.fill") && !(g_ammoOk && g_maxAmmoOk)) return "ammo code not verified";
    if ((!_stricmp(id, "player.health") || !_stricmp(id, "player.invincible")) && !g_healthOk)
        return "health code not verified";
    if (!_stricmp(id, "time.scale") && !g_timeOk) return "time code not verified";
    if (!_stricmp(id, "time.pause") && !g_pauseOk) return "pause code not verified";
    if (!_strnicmp(id, "nav.", 4)) {         // 0.12 Debug-Zeichnung: [Debug] Enabled, byte checks, a loaded level
        const char *navWhy = NavRadWhy(id, e.arg);
        if (navWhy[0]) return navWhy;
    }
    if (!_stricmp(id, "dbg.labels")) {       // 0.13 Thrall-Labels: [Debug] Enabled, byte checks
        const char *lblWhy = LabelRadWhy();
        if (lblWhy[0]) return lblWhy;
    } else if (!_strnicmp(id, "dbg.", 4)) {  // 0.14 Debug view: [Debug] Enabled, byte checks of the layer
        const char *dvWhy = DvRadWhy(id, e.arg);
        if (dvWhy[0]) return dvWhy;
    }
    const Item *item = FindItem(id);
    if (((item && item->gameThread) || !_stricmp(id, "time.scale")) && !g_experimental)
        return "experimental off ([Cheat] Experimental=0)";
    static const char *const kNeedLevel[] = {"cheat.", "player.", "weapon.give", "ammo.", "gear.", "instance.bring",
                                             "instance.spawn", "instance.remove", "instance.unhide", "camera.mode",
                                             "camera.restore", "camera.fov", "costume.next", "costume.set"};
    bool needs = false;
    for (const char *p : kNeedLevel)
        if (!_strnicmp(id, p, strlen(p))) needs = true;
    if (!_stricmp(id, "cheat.list") || !_stricmp(id, "cheat.speed") || !_stricmp(id, "player.position")) needs = false;
    if (needs && !InLevel()) return "needs a level";
    // 0.10.2 (F8, los7 21:22:37 "err main menu only"): level.start runs from the main menu only; in a level the tour
    // has a "Laden <unit>" entry (level.load) next to it
    DWORD state = 0;
    if (!_stricmp(id, "level.start") && g_mainStateOk && ReadDword(kMainState, &state) && state != 10)
        return "main menu only - in a level: 'Laden ...' (level.load, no intro)";
    return "";
}

// bool item without an argument: its value is "on"
bool RadialOn(const RadItem &e, bool *isBool) {
    if (e.special == kRadSpecialVirt && e.vkind == kRaToggle) { *isBool = true; return e.von != 0; }   // 0.10.1 Schalter
    // 0.12: "nav.draw <switch>" (one word) shows on / off of that NavPower switch byte; RadialRun adds the target state
    if (e.child < 0 && !e.special && !e.bad[0] && e.arg[0] && !strchr(e.arg, ' ') && !_stricmp(e.id, "nav.draw")) {
        int nav = NavFind(e.arg);
        if (nav >= 0) { *isBool = true; return NavByteOn(nav); }
    }
    // 0.14: "dbg.show <layer>" (one word) shows on / off of that layer; RadialRun adds the target state
    if (e.child < 0 && !e.special && !e.bad[0] && e.arg[0] && !strchr(e.arg, ' ') && !_stricmp(e.id, "dbg.show")) {
        int layer = DvFind(e.arg);
        if (layer >= 0) { *isBool = true; return g_dvOn[layer] != 0; }
    }
    *isBool =e.child < 0 && !e.special && !e.bad[0] && !e.arg[0] && CmdKindOf(e.id) == kCkBool;
    if (!*isBool) return false;
    char v[64];
    CmdValue(e.id, v, sizeof(v));
    return v[0] == '1' || !_strnicmp(v, "on", 2) || !_strnicmp(v, "true", 4);
}

void RadialClose(const char *why);          // below (0.10.5: claude.mark closes the ring)

void RadialRun(const RadItem &e) {
    if (e.special) return;                  // 0.10.1: the quit sector runs only through RadQuitPress (RadialTick)
    if (RadForbidden(e.id)) { Log(0, "radial: %s refused (never from the ring)", e.id); return; }
    char arg[96];
    strncpy_s(arg, sizeof(arg), e.arg, _TRUNCATE);
    bool isBool = false;
    bool on = RadialOn(e, &isBool);
    if (isBool && e.arg[0])                  // 0.12: nav.draw <switch> -> "<switch> 0|1"
        _snprintf_s(arg, sizeof(arg), _TRUNCATE, "%s %s", e.arg, on ? "0" : "1");
    else if (isBool) strncpy_s(arg, sizeof(arg), on ? "0" : "1", _TRUNCATE);   // the target state (0.8.1: no "" = flip)
    g_radRunning = true;                     // 0.10.5: src=ring in shot / claude.mark lines
    const char *answer = InvokeCore(e.id, arg, false);
    g_radRunning = false;
    ++g_radRuns;
    Log(1, "radial: %s -> %s%s%s: %.200s", e.path[0] ? e.path : "(top)", e.id, arg[0] ? " " : "", arg, answer);
    _snprintf_s(g_radResult, sizeof(g_radResult), _TRUNCATE, "%s: %s", e.label, answer);
    g_radResultTick = GetTickCount();
    // 0.10.5: a Claude mark closes the ring - play goes on at once (the shot is clean either way: it is copied before
    // TruMenu draws, at the next Present)
    if (!_stricmp(e.id, "claude.mark")) RadialClose("claude.mark");
    // 0.11: Weiter that started / finished a step closes the ring as well (play goes on; a refusal keeps it open)
    else if (!_stricmp(e.id, "flow.next") && !strncmp(answer, "ok", 2)) RadialClose("flow.next");
}

// 0.10.5: the level "Claude" (top-level folder entry and everything below it) is drawn in Claude's coral #D97757
bool RadClaude(const RadItem &e) {
    if (e.child >= 0 && !e.path[0] && !_stricmp(e.label, "Claude")) return true;
    return !_strnicmp(e.path, "Claude", 6) && (e.path[6] == 0 || e.path[6] == '/');
}

int RadPages(int level) {
    int count = g_radLevels[level].count;
    return count <= 0 ? 1 : (count + kRadPerPage - 1) / kRadPerPage;
}
int RadPageCount(int level, int page) {             // sectors on that page
    int left = g_radLevels[level].count - page * kRadPerPage;
    return left < 0 ? 0 : left > kRadPerPage ? kRadPerPage : left;
}
const RadItem *RadAt(int level, int page, int sector) {
    if (sector < 0 || sector >= RadPageCount(level, page)) return nullptr;
    return &g_radItems[g_radLevels[level].items[page * kRadPerPage + sector]];
}

void RadShow(int level, int page, int sel) {
    g_radLevel = level;
    g_radPage = page;
    g_radSel = sel;
    g_radMoved = false;
}

// ---- 0.10.1 quit sector: safety step as the Status page button (0.8.1): the first confirm arms (10 s), a second one
// >= 0.3 s later or the confirm held 1 s quits through QuitNow (TruMenu.log line, TO TEST list / history / logs
// flushed, TerminateProcess exit code 0x544D). Pointing away, B, a page / level change, closing and the 10 s disarm.
bool RadQuitArmed() { return g_radQuitArmedAt != 0; }
void RadQuitDisarm(const char *why) {
    if (!g_radQuitArmedAt) return;
    g_radQuitArmedAt = g_radQuitHoldFrom = 0;
    Log(1, "game.quit (radial sector): disarmed - %s", why);
}
bool RadQuitPicked() {                       // the pick is the quit sector (top level, its page and sector)
    const RadItem *e = RadAt(g_radLevel, g_radPage, g_radSel);
    return e && e->special == kRadSpecialQuit;
}
void RadQuitPress(const char *by) {          // a confirm press (edge) on the quit sector
    DWORD now = GetTickCount();
    if (!g_radQuitArmedAt) {
        g_radQuitArmedAt = now ? now : 1;
        g_radQuitHoldFrom = g_radQuitArmedAt;
        Log(1, "game.quit armed by the owner (radial sector '%s', %s) - press A again within %lu s (or hold A 1 s) to "
            "end the game", kRadQuitLabel, by, kQuitWindowMs / 1000);
        _snprintf_s(g_radResult, sizeof(g_radResult), _TRUNCATE, "%s: armed - A again within %lu s ends the game",
                    kRadQuitLabel, kQuitWindowMs / 1000);
        g_radResultTick = now;
        return;
    }
    DWORD age = now - g_radQuitArmedAt;
    if (age < kQuitMinGapMs) {
        g_radQuitHoldFrom = now ? now : 1;
        Log(1, "game.quit (radial sector): second press too fast (%lu ms) - still armed", age);
        return;
    }
    Log(1, "game.quit (radial sector): confirmed by the owner (%s, second press after %lu ms)", by, age);
    g_radQuitArmedAt = g_radQuitHoldFrom = 0;
    DWORD error = QuitNow();                 // returns only when TerminateProcess failed
    _snprintf_s(g_radResult, sizeof(g_radResult), _TRUNCATE, "%s: err TerminateProcess failed (%lu) - see TruMenu.log",
                kRadQuitLabel, error);
    g_radResultTick = GetTickCount();
}
// every frame of the open ring (Mode=menu): disarm when the pick left the sector / 10 s passed; the 1 s hold
void RadQuitTick(bool confirmHeld) {
    if (!g_radQuitArmedAt) return;
    DWORD now = GetTickCount();
    if (!RadQuitPicked()) { RadQuitDisarm("the pick left the sector"); return; }
    if (now - g_radQuitArmedAt > kQuitWindowMs) { RadQuitDisarm("10 s passed"); return; }
    if (!confirmHeld) { g_radQuitHoldFrom = 0; return; }
    if (!g_radQuitHoldFrom) return;          // held again after a release: the press edge counts (RadQuitPress)
    if (now - g_radQuitHoldFrom >= 1000) {
        Log(1, "game.quit (radial sector): held 1 s by the owner");
        g_radQuitArmedAt = g_radQuitHoldFrom = 0;
        DWORD error = QuitNow();
        _snprintf_s(g_radResult, sizeof(g_radResult), _TRUNCATE, "%s: err TerminateProcess failed (%lu) - see TruMenu.log",
                    kRadQuitLabel, error);
        g_radResultTick = GetTickCount();
    }
}

// ---- 0.10.1 [Radial] Freeze (Mode=menu, render thread = the game's Present call, as PauseTick) ----
int RadFreezeParse(const char *v) {
    while (*v == ' ') ++v;
    if (!_stricmp(v, "world") || !strcmp(v, "1")) return kRadFreezeWorld;
    if (!_stricmp(v, "player") || !strcmp(v, "2")) return kRadFreezePlayer;
    return kRadFreezeNone;                   // "0", "off", "none", anything else
}
int RadFreezeRead() {                        // read again at every open: the TO TEST switch ini:TruMenu:Radial:Freeze
    if (!g_iniPath[0]) return g_radFreeze;
    char v[32];
    GetPrivateProfileStringA("Radial", "Freeze", g_radFreeze == kRadFreezeWorld ? "world" : g_radFreeze == kRadFreezePlayer
                                                 ? "player" : "0", v, sizeof(v), g_iniPath);
    return RadFreezeParse(v);
}
void RadFreezeApply() {
    int mode = RadFreezeRead();
    if (mode == kRadFreezeNone) { g_radFreezeState = "off ([Radial] Freeze=0)"; return; }
    if (!InLevel()) { g_radFreezeState = "not in a level - nothing frozen"; return; }
    if (mode == kRadFreezeWorld) {
        if (!g_pauseOk) {
            g_radFreezeState = "not possible: streamFlags check failed (Freeze=world) - nothing frozen";
            Log(1, "radial: freeze %s", g_radFreezeState);
            return;
        }
        LONG before = InterlockedOr(reinterpret_cast<volatile LONG *>(kStreamFlags), 0x1000);
        InterlockedExchange(&g_radPaused, (before & 0x1000) ? 0 : 1);
        g_radFreezeState = (before & 0x1000) ? "world: paused already (left as it is at the close)"
                                             : "world - time.pause bit set by the ring (streamFlags 0x1000)";
    } else {
        if (!g_controlOk || !g_experimental) {
            g_radFreezeState = "not possible: control byte not verified / experimental off (Freeze=player) - nothing frozen";
            Log(1, "radial: freeze %s", g_radFreezeState);
            return;
        }
        volatile BYTE *b = reinterpret_cast<volatile BYTE *>(kPlayerControl);
        g_radCtlBefore = *b;
        *b = 0;
        InterlockedExchange(&g_radCtlOurs, 1);
        g_radFreezeState = "player - player.control 0 set by the ring";
    }
    Log(2, "radial: freeze %s", g_radFreezeState);
}
void RadFreezeRelease() {
    if (InterlockedExchange(&g_radPaused, 0)) {
        InterlockedAnd(reinterpret_cast<volatile LONG *>(kStreamFlags), ~0x1000L);
        Log(2, "radial: freeze world released (time.pause bit cleared)");
    } else if (strncmp(g_radFreezeState, "world", 5) == 0) {
        Log(2, "radial: freeze world - pause bit left as it was (paused before the ring, or time.pause run in the ring)");
    }
    if (InterlockedExchange(&g_radCtlOurs, 0)) {
        volatile BYTE *b = reinterpret_cast<volatile BYTE *>(kPlayerControl);
        if (*b == 0) *b = g_radCtlBefore;    // only over our own 0
        Log(2, "radial: freeze player released (player.control %u)", *b);
    }
}

// ---- 0.10.3 F7 (B29, los3 2026-11-03: "Welt einfrieren" stopped the world, the sound played on) ----
// The pause menu (open 0x5d4780 / 0x5d4810: pause bit 0x1000 cleared, gameMode 0xe7f143 = 6) pauses the sound with
// 0x5874b0; its close (0x5d4700, only at gameMode 6) resumes it with 0x5874d0. Statically (docs\TruMenu-0.10.2.md,
// section 0.10.3; the only other callers of 0x5874d0 are the level start 0x5de4a5 and the level loads 0x5df80c /
// 0x5dfb7d / 0x5dfb8e):
//   0x5874b0 = 0x5873a0(1); [0xccde88] = 1; jmp 0x4831c0     0x5874d0 = 0x5873a0(0); [0xccde88] = 0; jmp 0x4831d0
//   0x5873a0(b): for every index in the list [0xccdea0] (+0x1c count, +0x20 ints) bit 0 of +0x10 of the sound group
//     [0x8a80d8] + index * 0x84 := b - a SET, no toggle, no counter. [0xccdea0] is read without a null test (0
//     between levels, 0x5df961), so it is never called then. Which groups the list holds is game data, not code.
//   [0xccde88] = 1: the stream / music update 0x595250 (8 players at 0xcca9a0, 0x178 bytes) returns at once.
//   0x4831c0 / 0x4831d0: input manager 0xa02bd0 (0x4816f0 / 0x481750), per pad 4 byte flags off / on again (not
//     the XInputSetState path 0x484940 - rumble is not proven).
// No counter: one resume undoes any number of pauses. So TruMenu acts on the edges of its own want only, only when
// the state is the other one ([0xccde88]), never at gameMode 6 (the pause menu owns the sound then: it resumes it at
// its close and cleared the pause bit at its open - our claim is dropped), and it does not fight the game: once the
// game resumed the sound itself (level load / start) it stays so until the next freeze. Game thread (PadHook), every
// poll: the game clock stands still while paused.
const DWORD kSoundPause = 0x005874b0;        // cdecl (), the pause menu's sound pause (callers 0x5d47b6, 0x5d4821)
const DWORD kSoundResume = 0x005874d0;       // cdecl (), its counterpart (0x5d4738 = the pause menu's close)
const DWORD kSoundPaused = 0x00ccde88;       // dword: 1 after 0x5874b0, 0 after 0x5874d0 (read by 0x595253)
const DWORD kSoundGroups = 0x00ccdea0;       // pointer to the group index list, 0 between levels
bool g_soundOk = false;                      // the bytes of the pair and of the pause menu's use of it (Start)
int g_freezeSound = 0, g_pauseSound = 0;     // [Radial] FreezeSound / [Menu] PauseSound now (items change them)
int g_freezeSoundIni = 0, g_pauseSoundIni = 0; // the values last read from TruMenu.ini (a change there wins)
bool g_sndOurs = false;                      // game thread: 0x5874b0 called by us, not resumed yet
bool g_sndWant = false, g_sndCand = false;   // game thread: the want acted on / the want of the last poll
char g_sndLast[200] = "-";                   // last action, for time.sound and the log

void SndNote(int level, const char *fmt, ...) {
    char text[160];
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf_s(text, sizeof(text), _TRUNCATE, fmt, ap);
    va_end(ap);
    SYSTEMTIME t;
    GetLocalTime(&t);
    _snprintf_s(g_sndLast, sizeof(g_sndLast), _TRUNCATE, "%02d:%02d:%02d %s", t.wHour, t.wMinute, t.wSecond, text);
    Log(level, "sound: %s", text);
}
// at most once a second: a value changed in TruMenu.ini (TO TEST switch ini:TruMenu:Radial:FreezeSound /
// ini:TruMenu:Menu:PauseSound) is taken over; the items' runtime value stays until the ini value changes
void SoundSwitchesRead() {
    static DWORD last = 0;
    DWORD now = GetTickCount();
    if (!g_iniPath[0] || (last && now - last < 1000)) return;
    last = now ? now : 1;
    int f = GetPrivateProfileIntA("Radial", "FreezeSound", g_freezeSoundIni, g_iniPath) != 0 ? 1 : 0;
    int p = GetPrivateProfileIntA("Menu", "PauseSound", g_pauseSoundIni, g_iniPath) != 0 ? 1 : 0;
    if (f != g_freezeSoundIni) {
        g_freezeSoundIni = g_freezeSound = f;
        Log(1, "sound: [Radial] FreezeSound=%d taken over from TruMenu.ini", f);
    }
    if (p != g_pauseSoundIni) {
        g_pauseSoundIni = g_pauseSound = p;
        Log(1, "sound: [Menu] PauseSound=%d taken over from TruMenu.ini", p);
    }
}
bool SoundCall(DWORD fn, const char *what) {
    __try {
        reinterpret_cast<VoidFn>(fn)();
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        g_soundOk = false;
        SndNote(0, "%s 0x%08lx faulted - sound pause off until the next start", what, fn);
        return false;
    }
}
void SoundFreezeTick() {
    if (!g_soundOk) return;
    SoundSwitchesRead();
    if (!g_freezeSound && !g_pauseSound && !g_sndOurs && !g_sndWant) return;   // both off, nothing held
    DWORD flags = 0, groups = 0, paused = 0;
    BYTE mode = 0;
    if (!ReadDword(kStreamFlags, &flags) || !ReadByte(kGameMode, &mode) || !ReadDword(kSoundGroups, &groups) ||
        !ReadDword(kSoundPaused, &paused))
        return;
    bool ring = g_radPaused != 0;            // the ring set the bit (Freeze=world) - FreezeSound decides
    bool want = (flags & 0x1000) && groups && InLevel() && (ring ? g_freezeSound != 0 : g_pauseSound != 0);
    if (mode == 6) {                         // the pause menu owns the sound now
        if (g_sndOurs) {
            g_sndOurs = false;
            SndNote(1, "the pause menu opened - it holds the sound and resumes it at its close (our pause dropped)");
        }
        g_sndWant = g_sndCand = false;
        return;
    }
    if (want != g_sndCand) { g_sndCand = want; return; }   // the same answer on two polls (the ring sets the bit and
                                                           // its flag one after the other on the render thread)
    if (want == g_sndWant) {
        if (want && g_sndOurs && !paused) {
            g_sndOurs = false;
            SndNote(1, "the game resumed the sound itself (level start / load?) - not paused again until the next freeze");
        }
        return;
    }
    g_sndWant = want;
    const char *why = ring ? "ring freeze, [Radial] FreezeSound" : "world pause bit, [Menu] PauseSound";
    if (want) {
        if (paused) { SndNote(1, "freeze (%s): the sound was paused already - left as it is", why); return; }
        if (SoundCall(kSoundPause, "pause")) {
            g_sndOurs = true;
            SndNote(1, "sound paused (0x5874b0) - %s", why);
        }
        return;
    }
    if (!g_sndOurs) { SndNote(2, "freeze over - the sound was not paused by TruMenu, nothing to resume"); return; }
    g_sndOurs = false;
    if (!paused) { SndNote(1, "freeze over - the game had resumed the sound already"); return; }
    if (!groups) { SndNote(1, "freeze over - no sound group list (between levels): the level load resumes the sound"); return; }
    if (SoundCall(kSoundResume, "resume"))
        SndNote(1, "sound resumed (0x5874d0) - %s", (flags & 0x1000) ? "switch off / pause bit no longer ours"
                                                                      : "pause bit cleared");
}
bool SoundCheck() {                          // Start: the pair, the reader of the flag, the pause menu's own calls
    return HexBytesAt(kSoundPause, "6a01 e8e9feffff 83c404 c70588decc0001000000 e9f7bcefff") &&
           HexBytesAt(kSoundResume, "6a00 e8c9feffff 83c404 c70588decc0000000000 e9e7bcefff") &&
           HexBytesAt(0x005873a0, "a1a0decc00 56 8b701c 33c9 85f6 7e52") &&
           HexBytesAt(0x00595253, "833d88decc0000") &&
           HexBytesAt(0x005d47a7, "c60543f1e70006 e83db6feff 83c404 e8f52cfbff") &&
           HexBytesAt(0x005d4700, "803d43f1e70006 7534") && HexBytesAt(0x005d4738, "e8932dfbff");
}
void ValFreezeSound(char *o, size_t n) { Out(o, n, "%d", g_freezeSound); }
void ValPauseSound(char *o, size_t n) { Out(o, n, "%d", g_pauseSound); }
bool RunSoundSwitch(int *v, const char *name, const char *key, const char *arg, char *o, size_t n) {
    if (!g_soundOk) { Out(o, n, "sound pause code not verified (0x5874b0 / 0x5874d0) - stays off"); return false; }
    *v = BoolArg(arg, *v != 0) ? 1 : 0;
    Out(o, n, "%s %d (%s until the next start, TruMenu.ini not written)", name, *v, key);
    Log(1, "sound: %s %d (%s, runtime only)", name, *v, key);
    return true;
}
bool RunFreezeSound(const char *arg, char *o, size_t n) {
    return RunSoundSwitch(&g_freezeSound, "time.freezesound", "[Radial] FreezeSound", arg, o, n);
}
bool RunPauseSound(const char *arg, char *o, size_t n) {
    return RunSoundSwitch(&g_pauseSound, "time.pausesound", "[Menu] PauseSound", arg, o, n);
}
void ValSoundState(char *o, size_t n) {
    if (!g_soundOk) { Out(o, n, "sound pause code not verified - off"); return; }
    DWORD flags = 0, paused = 0;
    BYTE mode = 0;
    ReadDword(kStreamFlags, &flags);
    ReadDword(kSoundPaused, &paused);
    ReadByte(kGameMode, &mode);
    Out(o, n, "ring %d / pause %d (ini %d / %d); pause bit %d (ring's %d), gameMode %u, sound paused %lu (by TruMenu %d); "
        "last: %s", g_freezeSound, g_pauseSound, g_freezeSoundIni, g_pauseSoundIni, (flags & 0x1000) ? 1 : 0,
        g_radPaused ? 1 : 0, mode, paused, g_sndOurs ? 1 : 0, g_sndLast);
}

// ---- 0.10.4 (F7, light shaft): the shader clock TimeVector with the freeze, [Radial] FreezeShaderClock ----
// How the game makes the value (static, docs Befund-Menue-Dlc2Player-0411b.md; TruMenu-0.10.2.md section 3):
//   0x5bf840 (once per frame, from 0x5cebc0): dt = byte [0xdb94de] ? 0 : [0xe7f188] / [0x8439b8] (unless held:
//     [0xe7f194] / [0x84bd00] while [0xe7f0b4] & 0x10000000), then RenderDevice [0xa1407c] vtable +0xc = 0x506f10(dt):
//     +0xfa48 = dt, +0xfa4c += (int)(dt * [0x8416d8]) - an integer accumulator (also read by the getter 0x509190)
//   upload 0x5096c7: TimeVector (PS c53 0x509711 / VS c23 0x509721) = ((+0xfa4c mod 1000000) * [0x8416d0], +0xfa48, 0, 0)
// The world pause bit 0x1000 (time.pause, the ring's Freeze=world) does not touch it - every TimeVector material keeps
// moving in the freeze. Only the pause menu holds it: 0x5bfdf0(1) at its open (0x5d47ae: [0xdb94de] = 1, dt = 0, the
// accumulator stays, x is held, y = 0), 0x5bfdf0(0) at its close (0x5d4765); the accumulator then goes on from the held
// value - no jump, so no offset is needed. TruMenu uses the same function with the 0.10.3 sound rules: acts on the edges
// of its own want only, never at gameMode 6 (the pause menu owns the byte and clears it at its close - our claim is
// dropped), and does not fight the game (level start 0x5de3c7 and the unknown menu 0x6e4887 / 0x6e548c write 0: claim
// dropped). Game thread (PadHook), every poll.
const DWORD kRenderHoldSet = 0x005bfdf0;     // cdecl (BYTE): [0xdb94de] := arg
const DWORD kRenderHold = 0x00db94de;        // byte: 1 = render dt 0 (read only by 0x5bf841)
const DWORD kRenderDevice = 0x00a1407c;      // pointer: RenderDevice (+0xfa4c accumulator, +0xfa48 dt)
bool g_clockOk = false;                      // Start: reader, setter, accumulator, upload, the pause menu's calls
int g_freezeClock = 0, g_freezeClockIni = 0; // [Radial] FreezeShaderClock now / last read from TruMenu.ini
bool g_clkOurs = false, g_clkWant = false, g_clkCand = false;
DWORD g_clkHeldAt = 0, g_clkHeldTick = 0;    // accumulator value / tick count when TruMenu held the clock
char g_clkLast[200] = "-";

bool ClockValues(DWORD *acc, float *dt) {
    DWORD dev = 0;
    *acc = 0; *dt = 0.0f;
    return ReadDword(kRenderDevice, &dev) && dev && ReadDword(dev + 0xfa4c, acc) && ReadFloats(dev + 0xfa48, dt, 1);
}
void ClkNote(int level, const char *fmt, ...) {
    char text[160];
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf_s(text, sizeof(text), _TRUNCATE, fmt, ap);
    va_end(ap);
    SYSTEMTIME t;
    GetLocalTime(&t);
    _snprintf_s(g_clkLast, sizeof(g_clkLast), _TRUNCATE, "%02d:%02d:%02d %s", t.wHour, t.wMinute, t.wSecond, text);
    Log(level, "shader clock: %s", text);
}
typedef void(__cdecl *ByteArgFn)(int);
bool ClockCall(int on) {
    __try {
        reinterpret_cast<ByteArgFn>(kRenderHoldSet)(on);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        g_clockOk = false;
        ClkNote(0, "0x%08lx(%d) faulted - shader clock hold off until the next start", kRenderHoldSet, on);
        return false;
    }
}
void ShaderClockTick() {
    if (!g_clockOk) return;
    static DWORD lastRead = 0;               // a changed ini value is taken over within a second (TO TEST switch)
    DWORD now = GetTickCount();
    if (g_iniPath[0] && (!lastRead || now - lastRead >= 1000)) {
        lastRead = now ? now : 1;
        int v = GetPrivateProfileIntA("Radial", "FreezeShaderClock", g_freezeClockIni, g_iniPath) != 0 ? 1 : 0;
        if (v != g_freezeClockIni) {
            g_freezeClockIni = g_freezeClock = v;
            ClkNote(1, "[Radial] FreezeShaderClock=%d taken over from TruMenu.ini", v);
        }
    }
    if (!g_freezeClock && !g_clkOurs && !g_clkWant) return;
    DWORD flags = 0;
    BYTE mode = 0, held = 0;
    if (!ReadDword(kStreamFlags, &flags) || !ReadByte(kGameMode, &mode) || !ReadByte(kRenderHold, &held)) return;
    bool ring = g_radPaused != 0;
    bool want = (flags & 0x1000) && InLevel() && g_freezeClock != 0;
    DWORD acc = 0;
    float dt = 0.0f;
    if (mode == 6) {                         // the pause menu owns the byte now
        if (g_clkOurs) {
            g_clkOurs = false;
            ClkNote(1, "the pause menu opened - it holds the clock and releases it at its close (our hold dropped)");
        }
        g_clkWant = g_clkCand = false;
        return;
    }
    if (want != g_clkCand) { g_clkCand = want; return; }   // the same answer on two polls (as the sound)
    if (want == g_clkWant) {
        if (want && g_clkOurs && !held) {
            g_clkOurs = false;
            ClockValues(&acc, &dt);
            ClkNote(1, "the game released the clock itself (level start?) - accumulator %lu; not held again until the "
                       "next freeze", acc);
        }
        return;
    }
    g_clkWant = want;
    const char *why = ring ? "ring freeze" : "world pause bit";
    ClockValues(&acc, &dt);
    if (want) {
        if (held) { ClkNote(1, "freeze (%s): the clock was held already - left as it is", why); return; }
        if (ClockCall(1)) {
            g_clkOurs = true;
            g_clkHeldAt = acc;
            g_clkHeldTick = now;
            ClkNote(1, "ON - TimeVector held (0x5bfdf0(1), %s, [Radial] FreezeShaderClock): accumulator +0xfa4c %lu, "
                       "dt +0xfa48 %.5f", why, acc, dt);
        }
        return;
    }
    if (!g_clkOurs) { ClkNote(2, "freeze over - the clock was not held by TruMenu, nothing to release"); return; }
    g_clkOurs = false;
    if (!held) { ClkNote(1, "freeze over - the game had released the clock already (accumulator %lu)", acc); return; }
    if (ClockCall(0))
        ClkNote(1, "OFF - TimeVector runs on (0x5bfdf0(0), %s) after %.1f s: accumulator %lu (held at %lu: %s)",
                (flags & 0x1000) ? "switch off" : "pause bit cleared", (now - g_clkHeldTick) / 1000.0, acc, g_clkHeldAt,
                acc == g_clkHeldAt ? "unchanged = no jump" : "CHANGED while held");
}
bool ClockCheck() {                          // Start: the game's own path, byte for byte (precheck_0104.txt)
    return HexBytesAt(0x005bf841, "a0de94db00 84c0 7404 d9ee eb0c d90588f1e700") &&
           HexBytesAt(kRenderHoldSet, "8a442404 a2de94db00 c3") &&
           HexBytesAt(0x00506fb8, "01864cfa0000") &&
           HexBytesAt(0x005096c7, "8b854cfa0000 33d2 b940420f00 f7f1") &&
           HexBytesAt(0x005d47a5, "6a01 c60543f1e70006 e83db6feff") &&
           HexBytesAt(0x005d475c, "6a00 c60543f1e70000 e886b6feff");
}
void ValFreezeClock(char *o, size_t n) { Out(o, n, "%d", g_freezeClock); }
bool RunFreezeClock(const char *arg, char *o, size_t n) {
    if (!g_clockOk) { Out(o, n, "shader clock code not verified (0x5bfdf0 / 0x5bf841) - stays off"); return false; }
    g_freezeClock = BoolArg(arg, g_freezeClock != 0) ? 1 : 0;
    Out(o, n, "time.freezeclock %d ([Radial] FreezeShaderClock until the next start, TruMenu.ini not written)",
        g_freezeClock);
    ClkNote(1, "time.freezeclock %d (runtime only)", g_freezeClock);
    return true;
}
void ValClockState(char *o, size_t n) {
    if (!g_clockOk) { Out(o, n, "shader clock code not verified - off"); return; }
    DWORD flags = 0, acc = 0;
    BYTE mode = 0, held = 0;
    float dt = 0.0f;
    ReadDword(kStreamFlags, &flags);
    ReadByte(kGameMode, &mode);
    ReadByte(kRenderHold, &held);
    ClockValues(&acc, &dt);
    Out(o, n, "switch %d (ini %d); pause bit %d (ring's %d), gameMode %u, hold byte [0xdb94de] %u (by TruMenu %d); "
        "accumulator +0xfa4c %lu, dt %.5f; last: %s", g_freezeClock, g_freezeClockIni, (flags & 0x1000) ? 1 : 0,
        g_radPaused ? 1 : 0, mode, held, g_clkOurs ? 1 : 0, acc, dt, g_clkLast);
}

void RadialClose(const char *why) {
    if (!g_radOpen) return;
    InterlockedExchange(&g_radOpen, 0);
    InterlockedExchange(&g_radRelease, 0);
    InterlockedExchange(&g_radCloseReq, 0);
    InterlockedExchange(&g_radSwallow, 1);   // the pad stays neutral until every button is up (B / A / R3 of the close)
    RadQuitDisarm("ring closed");
    RadFreezeRelease();
    if (g_radSlowBefore >= 0.0f) {           // SlowMotion: back to the value from before, unless an entry changed it
        float now = 0.0f;
        if (ReadFloats(kTimeDilation, &now, 1) && fabsf(now - g_radSlow) < 0.001f)
            *reinterpret_cast<volatile float *>(kTimeDilation) = g_radSlowBefore;
        g_radSlowBefore = -1.0f;
    }
    if (!g_radRemember) { RadShow(0, 0, -1); g_rvKind = kRvNone; }
    Log(2, "radial: closed (%s) at '%s'", why, g_radLevels[g_radLevel].path);
}

// ---- 0.10.1 Tests level: the virtual levels (render thread, g_radLock held; the lists under g_testLock) ----
const char *const kRvRegLabels[3] = {"DLC 1", "DLC 2", "Alle"};

// one entry of the virtual level; folder = it opens the next virtual level
void RadVirtAdd(const char *label, int vkind, int vlist, const char *arg, const char *info, bool folder, int on) {
    RadLevel &v = g_radLevels[g_radVirtLevel];
    if (v.count >= kRadVirtMax) return;
    RadItem &e = g_radItems[kRadMaxItems + v.count];
    e = RadItem();
    strncpy_s(e.label, sizeof(e.label), label, _TRUNCATE);
    strncpy_s(e.arg, sizeof(e.arg), arg ? arg : "", _TRUNCATE);
    strncpy_s(e.info, sizeof(e.info), info ? info : "", _TRUNCATE);
    strncpy_s(e.path, sizeof(e.path), v.path, _TRUNCATE);
    e.child = folder ? g_radVirtLevel : -1;
    e.bad = "";
    e.special = kRadSpecialVirt;
    e.vkind = vkind;
    e.vlist = vlist;
    e.von = on;
    v.items[v.count] = static_cast<short>(kRadMaxItems + v.count);
    ++v.count;
}

// open = step not done / check open; the counts of a list (toggles not counted)
bool RadRowOpen(const TestRow &t) {
    if (TestIs(t, "step")) return _stricmp(t.state, "done") != 0;
    return TestIs(t, "check") && !_stricmp(t.state, "open");
}
void RadRowCount(const TestRow *rows, int c, int *open, int *total) {
    *open = *total = 0;
    for (int i = 0; i < c; ++i) {
        if (TestIs(rows[i], "toggle")) continue;
        ++*total;
        if (RadRowOpen(rows[i])) ++*open;
    }
}
// the item a row runs: steps their target ("id" / "id:arg"), checks their id (as the TO TEST page); never an id of
// kRadForbidden (game.quit, cmd.run, save.*, settings.reset) - stricter than the page
bool RadRowRunnable(const TestRow &t, char *itemId, size_t idSize, const char **runArg) {
    bool ok = TestIs(t, "step") ? t.target[0] && TestRunTarget(t.target, itemId, idSize, runArg)
                                : TestRunTarget(t.id, itemId, idSize, runArg);
    return ok && !RadForbidden(itemId);
}
// "S12 Ring: left stick ..." / "[ok] radial-open"
void RadRowLabel(const TestRow &t, bool withState, char *o, size_t n) {
    const char *tag = !withState ? "" : !_stricmp(t.state, "ok") ? "[ok] " : !_stricmp(t.state, "fail") ? "[FAIL] "
                    : !_stricmp(t.state, "skip") ? "[skip] " : !_stricmp(t.state, "done") ? "[done] " : "";
    if (TestIs(t, "step")) _snprintf_s(o, n, _TRUNCATE, "%sS%d %s", tag, t.num, t.hint);
    else _snprintf_s(o, n, _TRUNCATE, "%s%s", tag, t.id);
}

// the row's actions: Run (if allowed), OK / Fail / Skip (checks) or Done (steps), Prepare (regression shortcut), Hint
void RadVirtRowActions(const TestRow &t, int list, const char *shortcut) {
    char itemId[64], label[48], info[160];
    const char *runArg = "";
    _snprintf_s(info, sizeof(info), _TRUNCATE, "%s", t.hint[0] ? t.hint : t.id);
    if (RadRowRunnable(t, itemId, sizeof(itemId), &runArg)) {
        _snprintf_s(label, sizeof(label), _TRUNCATE, "Run %s%s%s", itemId, runArg[0] ? " " : "", runArg);
        RadVirtAdd(label, kRaRun, list, t.id, info, false, 0);
    }
    if (TestIs(t, "step")) {
        RadVirtAdd(_stricmp(t.state, "done") ? "Done" : "Wieder offen", kRaDone, list, t.id, info, false, 0);
    } else {
        RadVirtAdd("OK", kRaOk, list, t.id, info, false, 0);
        RadVirtAdd("Fail", kRaFail, list, t.id, info, false, 0);
        RadVirtAdd("Skip", kRaSkip, list, t.id, info, false, 0);
    }
    if (shortcut && shortcut[0]) RadVirtAdd("Prepare", kRaPrepare, list, t.id, shortcut, false, 0);
    RadVirtAdd("Hint", kRaHint, list, t.id, info, false, 0);
}

// the virtual level of g_rvKind from the current lists (every frame while it is shown)
void RadVirtBuild() {
    if (g_radVirtLevel < 0) return;
    static TestRow rows[kRegLists + 1][kTestMax];   // [0] dlc1, [1] dlc2, [2] TO TEST
    static char cuts[kRegLists][kTestMax][kShortcutLen];
    int count[kRegLists + 1];
    EnterCriticalSection(&g_testLock);
    for (int l = 0; l < kRegLists; ++l) {
        count[l] = g_regCount[l];
        memcpy(rows[l], g_reg[l], sizeof(TestRow) * static_cast<size_t>(count[l]));
        memcpy(cuts[l], g_regShortcut[l], kShortcutLen * static_cast<size_t>(count[l]));
    }
    count[2] = g_testCount;
    memcpy(rows[2], g_tests, sizeof(TestRow) * static_cast<size_t>(count[2]));
    LeaveCriticalSection(&g_testLock);
    auto find = [&](int list, const char *id) {
        for (int i = 0; i < count[list]; ++i) if (!_stricmp(rows[list][i].id, id)) return i;
        return -1;
    };
    // a row that vanished (test.clear, regress.load) -> its list
    if (g_rvKind == kRvTodoRow && find(2, g_rvRow) < 0) g_rvKind = kRvTodo;
    if (g_rvKind == kRvRegRow && find(g_rvRowList, g_rvRow) < 0) g_rvKind = kRvReg;
    RadLevel &v = g_radLevels[g_radVirtLevel];
    v.count = 0;
    char label[48], line[160];
    switch (g_rvKind) {
    case kRvTodo:
        strncpy_s(v.path, sizeof(v.path), "Tests/TO TEST", _TRUNCATE);
        for (int i = 0; i < count[2]; ++i) {
            const TestRow &t = rows[2][i];
            if (TestIs(t, "toggle") || !RadRowOpen(t)) continue;
            RadRowLabel(t, false, label, sizeof(label));
            RadVirtAdd(label, kRvTodoRow, 2, t.id, t.hint, true, 0);
        }
        break;
    case kRvTodoRow: {
        const TestRow &t = rows[2][find(2, g_rvRow)];
        _snprintf_s(v.path, sizeof(v.path), _TRUNCATE, "Tests/TO TEST/%s", t.id);
        RadVirtRowActions(t, 2, nullptr);
        break;
    }
    case kRvRegLists:
        strncpy_s(v.path, sizeof(v.path), "Tests/Regression", _TRUNCATE);
        for (int l = 0; l <= kRegLists; ++l) {
            int open = 0, total = 0, o2 = 0, t2 = 0;
            if (l < kRegLists) RadRowCount(rows[l], count[l], &open, &total);
            else { RadRowCount(rows[0], count[0], &open, &total); RadRowCount(rows[1], count[1], &o2, &t2); open += o2; total += t2; }
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s %d/%d offen", kRvRegLabels[l], open, total);
            RadVirtAdd(label, kRvReg, l, "", "", true, 0);
        }
        break;
    case kRvReg:
        _snprintf_s(v.path, sizeof(v.path), _TRUNCATE, "Tests/Regression/%s", kRvRegLabels[g_rvList]);
        for (int l = 0; l < kRegLists; ++l) {
            if (g_rvList != 2 && g_rvList != l) continue;
            for (int i = 0; i < count[l]; ++i) {
                const TestRow &t = rows[l][i];
                RadRowLabel(t, true, label, sizeof(label));
                RadVirtAdd(label, kRvRegRow, l, t.id, t.hint, true, 0);
            }
        }
        break;
    case kRvRegRow: {
        int i = find(g_rvRowList, g_rvRow);
        const TestRow &t = rows[g_rvRowList][i];
        _snprintf_s(v.path, sizeof(v.path), _TRUNCATE, "Tests/Regression/%s/%s", kRvRegLabels[g_rvRowList], t.id);
        RadVirtRowActions(t, g_rvRowList, cuts[g_rvRowList][i]);
        break;
    }
    case kRvPrepare:                         // one entry per distinct shortcut, as the page's "Quick prepare" list
        strncpy_s(v.path, sizeof(v.path), "Tests/Prepare", _TRUNCATE);
        for (int l = 0; l < kRegLists; ++l)
            for (int i = 0; i < count[l]; ++i) {
                if (!cuts[l][i][0]) continue;
                bool dup = false;
                for (int j = 0; j < i && !dup; ++j) dup = !strcmp(cuts[l][j], cuts[l][i]);
                if (dup) continue;
                char title[96] = "", steps[kScMaxSteps][kScStepLen], o[80];
                int c = 0;
                ShortcutParse(cuts[l][i], title, sizeof(title), steps, &c, o, sizeof(o));
                _snprintf_s(label, sizeof(label), _TRUNCATE, "%s", title[0] ? title : rows[l][i].id);
                _snprintf_s(line, sizeof(line), _TRUNCATE, "%s:%s = %s", kRegNames[l], rows[l][i].id, cuts[l][i]);
                RadVirtAdd(label, kRaPrepare, l, rows[l][i].id, line, false, 0);
            }
        if (g_scActive) {
            ValShortcut(line, sizeof(line));
            RadVirtAdd("Stop", kRaStop, 0, "", line, false, 0);
        }
        break;
    case kRvToggles:
        strncpy_s(v.path, sizeof(v.path), "Tests/Schalter", _TRUNCATE);
        for (int i = 0; i < count[2]; ++i) {
            const TestRow &t = rows[2][i];
            if (!TestIs(t, "toggle")) continue;
            _snprintf_s(line, sizeof(line), _TRUNCATE, "%s (%s)", t.hint[0] ? t.hint : t.id, t.target);
            RadVirtAdd(t.id, kRaToggle, 2, t.id, line, false, !_stricmp(t.state, "on") ? 1 : 0);
        }
        break;
    default:
        strncpy_s(v.path, sizeof(v.path), "Tests", _TRUNCATE);
        break;
    }
    int pages = RadPages(g_radVirtLevel);
    if (g_radLevel == g_radVirtLevel) {
        if (g_radPage >= pages) g_radPage = pages - 1;
        int n = RadPageCount(g_radVirtLevel, g_radPage);
        if (g_radSel >= n) g_radSel = n - 1;
    }
}

// the labels of the four folders in Tests with their counts ("TO TEST 3/28 offen")
void RadTestsLabels() {
    if (g_radTestsItems[0] < 0) return;
    int open = 0, total = 0, regOpen = 0, regTotal = 0, cuts = 0, toggles = 0, on = 0;
    EnterCriticalSection(&g_testLock);
    RadRowCount(g_tests, g_testCount, &open, &total);
    for (int l = 0; l < kRegLists; ++l) {
        int o = 0, t = 0;
        RadRowCount(g_reg[l], g_regCount[l], &o, &t);
        regOpen += o;
        regTotal += t;
        for (int i = 0; i < g_regCount[l]; ++i) {
            if (!g_regShortcut[l][i][0]) continue;
            bool dup = false;
            for (int j = 0; j < i && !dup; ++j) dup = !strcmp(g_regShortcut[l][j], g_regShortcut[l][i]);
            if (!dup) ++cuts;
        }
    }
    for (int i = 0; i < g_testCount; ++i)
        if (TestIs(g_tests[i], "toggle")) { ++toggles; if (!_stricmp(g_tests[i].state, "on")) ++on; }
    LeaveCriticalSection(&g_testLock);
    _snprintf_s(g_radItems[g_radTestsItems[0]].label, sizeof(g_radItems[0].label), _TRUNCATE, "TO TEST %d/%d offen", open,
                total);
    _snprintf_s(g_radItems[g_radTestsItems[1]].label, sizeof(g_radItems[0].label), _TRUNCATE, "Regression %d/%d offen",
                regOpen, regTotal);
    _snprintf_s(g_radItems[g_radTestsItems[2]].label, sizeof(g_radItems[0].label), _TRUNCATE, "Prepare (%d)", cuts);
    _snprintf_s(g_radItems[g_radTestsItems[3]].label, sizeof(g_radItems[0].label), _TRUNCATE, "Schalter %d/%d an", on,
                toggles);
}

// pick the entry whose arg is <arg> (or the one at <fallback>) on the virtual level
void RadVirtSelect(const char *arg, int fallback) {
    const RadLevel &v = g_radLevels[g_radVirtLevel];
    int at = -1;
    for (int i = 0; i < v.count && at < 0; ++i)
        if (arg && arg[0] && !_stricmp(g_radItems[v.items[i]].arg, arg)) at = i;
    if (at < 0) at = fallback < v.count ? fallback : v.count - 1;
    if (at < 0) at = 0;
    RadShow(g_radVirtLevel, at / kRadPerPage, v.count ? at % kRadPerPage : -1);
}

void RadVirtEnter(int kind, int list, int rowList, const char *row) {
    g_rvKind = kind;
    if (kind == kRvReg) g_rvList = list;
    g_rvRowList = rowList;
    strncpy_s(g_rvRow, sizeof(g_rvRow), row ? row : "", _TRUNCATE);
    RadVirtBuild();
    RadShow(g_radVirtLevel, 0, g_radLevels[g_radVirtLevel].count ? 0 : -1);
    Log(2, "radial: level '%s'", g_radLevels[g_radVirtLevel].path);
}

// B on a virtual level: row -> its list (the row picked), list -> the level above, the first level -> Tests
void RadVirtBack() {
    char row[64];
    strncpy_s(row, sizeof(row), g_rvRow, _TRUNCATE);
    switch (g_rvKind) {
    case kRvTodoRow: g_rvKind = kRvTodo; RadVirtBuild(); RadVirtSelect(row, 0); return;
    case kRvRegRow: g_rvKind = kRvReg; RadVirtBuild(); RadVirtSelect(row, 0); return;
    case kRvReg: g_rvKind = kRvRegLists; RadVirtBuild(); RadVirtSelect(nullptr, g_rvList); return;
    default: break;
    }
    int kind = g_rvKind;
    g_rvKind = kRvNone;
    const RadLevel &p = g_radLevels[g_radTestsLevel];
    int pos = 0;
    for (int i = 0; i < p.count; ++i)
        if (g_radItems[p.items[i]].special == kRadSpecialVirt && g_radItems[p.items[i]].vkind == kind) pos = i;
    RadShow(g_radTestsLevel, pos / kRadPerPage, pos % kRadPerPage);
}

// a confirm press on a virtual entry; every action goes through the page's own function
void RadVirtActivate(const RadItem &e) {
    char o[300] = "";
    if (e.child >= 0) {                      // a virtual folder: from Tests (vkind = the level) or a list
        if (e.vkind == kRvTodoRow || e.vkind == kRvRegRow) RadVirtEnter(e.vkind, g_rvList, e.vlist, e.arg);
        else RadVirtEnter(e.vkind, e.vlist, 0, "");
        return;
    }
    bool todo = e.vlist == 2;
    switch (e.vkind) {
    case kRaRun: {
        TestRow t = {};
        bool found = false;
        EnterCriticalSection(&g_testLock);
        const TestRow *rows = todo ? g_tests : g_reg[e.vlist];
        int c = todo ? g_testCount : g_regCount[e.vlist];
        for (int i = 0; i < c && !found; ++i)
            if (!_stricmp(rows[i].id, e.arg)) { t = rows[i]; found = true; }
        LeaveCriticalSection(&g_testLock);
        char itemId[64];
        const char *runArg = "";
        if (!found || !RadRowRunnable(t, itemId, sizeof(itemId), &runArg)) {
            _snprintf_s(g_radResult, sizeof(g_radResult), _TRUNCATE, "%s: not available - no runnable item", e.arg);
            break;
        }
        char argCopy[128];
        strncpy_s(argCopy, sizeof(argCopy), runArg, _TRUNCATE);
        QueueItem(itemId, argCopy);          // as the page's Run button
        ++g_radRuns;
        Log(1, "radial: %s -> run %s%s%s (row %s)", g_radLevels[g_radLevel].path, itemId, argCopy[0] ? " " : "", argCopy,
            e.arg);
        _snprintf_s(g_radResult, sizeof(g_radResult), _TRUNCATE, "%s", g_lastAction);
        if (!_strnicmp(itemId, "level.", 6) && g_radOpen) {
            g_radResultTick = GetTickCount();
            RadialClose("level change from a test row - the world must run");
            return;
        }
        break;
    }
    case kRaOk: case kRaFail: case kRaSkip: case kRaDone: {
        const char *state = e.vkind == kRaOk ? "ok" : e.vkind == kRaFail ? "fail" : e.vkind == kRaSkip ? "skip"
                          : !_stricmp(e.label, "Done") ? "done" : "open";
        if (todo) TestMarkFromMenu(e.arg, state);
        else RegMarkFromMenu(e.vlist, e.arg, state);
        Log(2, "radial: %s -> mark %s", g_radLevels[g_radLevel].path, state);
        _snprintf_s(g_radResult, sizeof(g_radResult), _TRUNCATE, "%s", g_lastAction);
        g_radResultTick = GetTickCount();
        RadVirtBack();                       // back to the list (an open TO TEST row disappears there)
        return;
    }
    case kRaHint:
        _snprintf_s(g_radResult, sizeof(g_radResult), _TRUNCATE, "%s: %s", e.arg, e.info);
        break;
    case kRaPrepare: {
        char spec[96];
        _snprintf_s(spec, sizeof(spec), _TRUNCATE, "%s:%s", kRegNames[e.vlist], e.arg);
        bool ok = RunRegressPrepare(spec, o, sizeof(o));
        SetLastAction("regress.prepare", ok, o);   // as the page's Prepare button
        _snprintf_s(g_radResult, sizeof(g_radResult), _TRUNCATE, "Prepare %s: %s%s", spec, ok ? "" : "err ", o);
        g_radResultTick = GetTickCount();
        if (ok && g_radOpen) RadialClose("Prepare started - the world must run for its level change");
        return;
    }
    case kRaStop: {
        bool ok = RunRegressPrepare("stop", o, sizeof(o));
        SetLastAction("regress.prepare", ok, o);
        _snprintf_s(g_radResult, sizeof(g_radResult), _TRUNCATE, "Prepare: %s", o);
        break;
    }
    case kRaToggle:
        TestMarkFromMenu(e.arg, e.von ? "off" : "on");   // the target state, as the page's checkbox
        _snprintf_s(g_radResult, sizeof(g_radResult), _TRUNCATE, "%s", g_lastAction);
        break;
    default:
        break;
    }
    g_radResultTick = GetTickCount();
}

// A / R3 / the release on the picked sector: a folder opens its level, an entry runs (closeAfter: the ring closes)
void RadialActivate(bool closeAfter) {
    const RadItem *e = RadAt(g_radLevel, g_radPage, g_radSel);
    if (!e) {
        if (closeAfter) RadialClose("released in the centre");
        return;
    }
    if (e->special) return;                  // 0.10.1: the quit sector only through RadQuitPress (Mode=menu confirm)
    if (e->child >= 0) {
        int parent = g_radLevel;
        RadShow(e->child, 0, -1);
        if (closeAfter) InterlockedExchange(&g_radOpen, 2);   // the release entered a level: the ring stays (latched)
        Log(2, "radial: level '%s' (from '%s')", g_radLevels[g_radLevel].path, g_radLevels[parent].path);
        return;
    }
    const char *why = RadialWhy(*e);
    if (why[0]) {
        _snprintf_s(g_radResult, sizeof(g_radResult), _TRUNCATE, "%s: not available - %s", e->label, why);
        g_radResultTick = GetTickCount();
        Log(2, "radial: %s -> %s not run: %s", e->path, e->id, why);
        if (closeAfter) RadialClose("entry not available");
        return;
    }
    RadialRun(*e);
    if (closeAfter) RadialClose("entry run");
}

// B: one level back (to the folder entry that leads here); at the top the ring closes
void RadialBack() {
    RadQuitDisarm("B");
    if (g_radLevel <= 0) { RadialClose("B at the top"); return; }
    if (g_radLevel == g_radVirtLevel) { RadVirtBack(); return; }   // 0.10.1 Tests level
    int child = g_radLevel, parent = g_radLevels[child].parent;
    const RadLevel &p = g_radLevels[parent];
    int at = 0;
    for (int i = 0; i < p.count; ++i)
        if (g_radItems[p.items[i]].child == child) at = i;
    RadShow(parent, at / kRadPerPage, at % kRadPerPage);
}

void RadialOnOpen() {
    bool valid = g_radLevel >= 0 && g_radLevel < g_radLevelCount && g_radPage < RadPages(g_radLevel);
    if (!valid || (!g_radRemember && g_radBy != kRadByLink))   // radial.open has set its level already
        RadShow(0, 0, -1);
    else
        g_radMoved = false;                  // remembered pick: highlighted, the release still needs a deflection
    GetCursorPos(&g_radMouseOrigin);
    g_radMouseDx = g_radMouseDy = 0.0f;
    if (g_radSlow > 0.0f && g_timeOk && g_experimental) {
        float before = 1.0f;
        if (ReadFloats(kTimeDilation, &before, 1)) {
            g_radSlowBefore = before;
            *reinterpret_cast<volatile float *>(kTimeDilation) = g_radSlow;
        }
    }
    g_radQuitArmedAt = g_radQuitHoldFrom = 0;
    if (g_radMode == kRadModeMenu) {
        if (g_radLevel == g_radVirtLevel && g_radVirtLevel >= 0) {   // a remembered Tests level: the lists of now
            if (g_rvKind == kRvNone) RadShow(g_radTestsLevel, 0, 0);
            else RadVirtBuild();
        }
        if (g_radSel < 0 && RadPageCount(g_radLevel, g_radPage) > 0) g_radSel = 0;   // a menu: something is picked
        RadFreezeApply();
    }
    static const char *const by[] = {"?", "pad", "key", "mouse button", "radial.open"};
    LONG who = g_radBy;
    Log(2, "radial: opened by %s at '%s' page %d", by[who >= 0 && who <= 4 ? who : 0], g_radLevels[g_radLevel].path,
        g_radPage + 1);
}

bool RadFront() {                            // the game window (any window of this process) is in front
    HWND w = GetForegroundWindow();
    DWORD pid = 0;
    if (w) GetWindowThreadProcessId(w, &pid);
    return pid == GetCurrentProcessId();
}

// render thread, every Present: key / mouse button hold, radial.open, the open ring's input
void RadialTick() {
    if (!g_radEnabled) return;
    bool front = RadFront();
    static bool keyWas = false, mouseWas = false;
    int vkMouse = g_radMouse == 3 ? VK_MBUTTON : g_radMouse == 4 ? VK_XBUTTON1 : g_radMouse == 5 ? VK_XBUTTON2 : 0;
    bool key = g_radKey && front && (GetAsyncKeyState(g_radKey) & 0x8000) != 0;
    bool mouse = vkMouse && front && (GetAsyncKeyState(vkMouse) & 0x8000) != 0;
    if ((key && !keyWas) || (mouse && !mouseWas)) {
        LONG by = key && !keyWas ? kRadByKey : kRadByMouse;
        if (g_radMode == kRadModeMenu) {     // 0.10.1: a tap opens (stays open), the next tap closes
            if (!g_menuOpen && !g_radOpen) {
                InterlockedExchange(&g_radBy, by);
                InterlockedExchange(&g_radJust, 1);
                InterlockedExchange(&g_radOpen, 2);
            } else if (g_radOpen) {
                RadialClose(by == kRadByKey ? "key again" : "mouse button again");
            }
        } else if (!g_menuOpen && !g_radOpen) {
            InterlockedExchange(&g_radBy, by);
            InterlockedExchange(&g_radJust, 1);
            InterlockedExchange(&g_radOpen, 1);
        } else if (g_radOpen == 2) {
            InterlockedExchange(&g_radBy, by);
            InterlockedExchange(&g_radOpen, 1);
        }
    }
    if (g_radMode == kRadModeWheel && g_radOpen == 1 &&
        ((!key && keyWas && g_radBy == kRadByKey) || (!mouse && mouseWas && g_radBy == kRadByMouse)))
        InterlockedExchange(&g_radRelease, 1);
    keyWas = key;
    mouseWas = mouse;
    if (InterlockedExchange(&g_radCloseReq, 0) && g_radOpen) RadialClose("L3 + R3 again");   // 0.10.1 Mode=menu
    if (InterlockedExchange(&g_radOpenReq, 0) && !g_menuOpen) {
        EnterCriticalSection(&g_radLock);
        int level = 0;
        for (int i = 0; i < g_radLevelCount; ++i)
            if (!_stricmp(g_radLevels[i].path, g_radOpenPath)) level = i;
        RadShow(level, 0, -1);
        LeaveCriticalSection(&g_radLock);
        InterlockedExchange(&g_radBy, kRadByLink);
        InterlockedExchange(&g_radJust, 1);
        InterlockedExchange(&g_radOpen, 2);
    }
    if (g_radOpen && g_menuOpen) RadialClose("TruMenu opened");
    static WORD prev = 0, lastMouse = 0;
    static bool r3Armed = false;
    PadState pad = {};
    EnterCriticalSection(&g_padLock);
    bool have = g_padConnected[g_lastPad];
    if (have) pad = g_pad[g_lastPad];
    LeaveCriticalSection(&g_padLock);
    WORD clicks = static_cast<WORD>((front && (GetAsyncKeyState(VK_LBUTTON) & 0x8000) ? 1 : 0) |
                                    (front && (GetAsyncKeyState(VK_RBUTTON) & 0x8000) ? 2 : 0));
    // 0.10.1 Mode=menu keys (the game gets no keys while the ring is open): 1 Enter, 2 Backspace, 4 Esc, 8 left, 16 right
    static WORD lastKeys = 0;
    WORD keys = 0;
    if (front && g_radMode == kRadModeMenu) {
        const int vks[] = {VK_RETURN, VK_BACK, VK_ESCAPE, VK_LEFT, VK_RIGHT};
        for (int i = 0; i < 5; ++i)
            if (GetAsyncKeyState(vks[i]) & 0x8000) keys = static_cast<WORD>(keys | (1 << i));
    }
    if (!g_radOpen) {
        prev = pad.wButtons;
        lastMouse = clicks;
        lastKeys = keys;
        r3Armed = false;
        return;
    }
    EnterCriticalSection(&g_radLock);
    if (InterlockedExchange(&g_radJust, 0)) {
        RadialOnOpen();
        prev = pad.wButtons;                 // buttons held at the open (L3 + R3) are no edges
        lastMouse = clicks;
        lastKeys = keys;
        r3Armed = false;
    }
    if (g_radMode == kRadModeMenu) {         // 0.10.1 Tests level: counts and lists of this frame
        if (g_radLevel == g_radTestsLevel) RadTestsLabels();
        if (g_radLevel == g_radVirtLevel && g_radVirtLevel >= 0) {
            if (g_rvKind == kRvNone) RadShow(g_radTestsLevel, 0, 0);
            else RadVirtBuild();
        }
    }
    // the release first, with the pick of the last frame (the stick may spring back in the release poll)
    if (InterlockedExchange(&g_radRelease, 0) && g_radOpen == 1) {
        if (g_radMoved && g_radSel >= 0) RadialActivate(true);
        else RadialClose("released in the centre");
    }
    WORD edges = static_cast<WORD>(pad.wButtons & ~prev);
    WORD ups = static_cast<WORD>(prev & ~pad.wButtons);
    WORD clickEdges = static_cast<WORD>(clicks & ~lastMouse);
    WORD keyEdges = static_cast<WORD>(keys & ~lastKeys);
    prev = pad.wButtons;
    lastMouse = clicks;
    lastKeys = keys;
    if (g_radOpen && g_radMode == kRadModeMenu) {
        // 0.10.1 Mode=menu: nothing runs by pointing or releasing - only the confirm press below
        int pages = RadPages(g_radLevel);
        if (edges & 0x0100) { RadQuitDisarm("page change"); RadShow(g_radLevel, (g_radPage + pages - 1) % pages, -1); }
        if (edges & 0x0200) { RadQuitDisarm("page change"); RadShow(g_radLevel, (g_radPage + 1) % pages, -1); }
        int n = RadPageCount(g_radLevel, g_radPage);
        if (g_radSel < 0 && n > 0) g_radSel = 0;
        if (n > 0 && ((edges & 0x0008) || (keyEdges & 16))) g_radSel = (g_radSel + 1) % n;       // D-pad / arrow right
        if (n > 0 && ((edges & 0x0004) || (keyEdges & 8))) g_radSel = (g_radSel + n - 1) % n;    // D-pad / arrow left
        bool confirm = (edges & 0x1000) || (keyEdges & 1) || (clickEdges & 1);
        if (confirm) {
            const RadItem *e = RadAt(g_radLevel, g_radPage, g_radSel);
            // a level.* entry (tour / file): the ring closes after it - whether a level change goes on while
            // time.pause is set is not proven, so the freeze must end (README "Radial menu 0.10.1")
            bool levelChange = e && e->child < 0 && !e->special && !_strnicmp(e->id, "level.", 6) && !RadialWhy(*e)[0];
            if (RadQuitPicked())
                RadQuitPress((edges & 0x1000) ? "pad A" : (keyEdges & 1) ? "Enter" : "left click");
            else if (e && e->special == kRadSpecialVirt)
                RadVirtActivate(*e);         // 0.10.1 Tests level: the page functions
            else
                RadialActivate(false);       // a level opens, an entry runs; the ring stays open
            if (levelChange && g_radOpen) RadialClose("level change - the world must run");
            if (g_radOpen && g_radSel < 0 && RadPageCount(g_radLevel, g_radPage) > 0) g_radSel = 0;
        }
        if (g_radOpen && ((edges & 0x2000) || (keyEdges & 2) || (keyEdges & 4) || (clickEdges & 2))) {
            RadialBack();                    // B / Backspace / Esc / right click
            if (g_radOpen && g_radSel < 0 && RadPageCount(g_radLevel, g_radPage) > 0) g_radSel = 0;
        }
    } else if (g_radOpen) {
        int pages = RadPages(g_radLevel);
        if (edges & 0x0100) RadShow(g_radLevel, (g_radPage + pages - 1) % pages, -1);   // LB
        if (edges & 0x0200) RadShow(g_radLevel, (g_radPage + 1) % pages, -1);           // RB
        if ((edges & 0x1000) || (clickEdges & 1)) RadialActivate(false);                // A / left click: run, stay
        if ((edges & 0x2000) || (clickEdges & 2)) RadialBack();                         // B / right click
        // R3 alone (latched ring): run the pick and close; L3 joining makes it the hold combo instead
        if (g_radOpen == 2) {
            if ((edges & kPadR3) && !(pad.wButtons & kPadL3)) r3Armed = true;
            if (pad.wButtons & kPadL3) r3Armed = false;
            if ((ups & kPadR3) && r3Armed) {
                r3Armed = false;
                if (RadAt(g_radLevel, g_radPage, g_radSel)) RadialActivate(true);
            }
        } else {
            r3Armed = false;
        }
    }
    if (g_radOpen) {                         // the pick: right stick, else the mouse direction since the open
        bool menu = g_radMode == kRadModeMenu;
        int n = RadPageCount(g_radLevel, g_radPage);
        float x = have ? pad.sThumbRX / 32767.0f : 0.0f, y = have ? pad.sThumbRY / 32767.0f : 0.0f;
        if (menu && have) {                  // 0.10.1 Mode=menu: the left stick picks too (the stronger one wins)
            float lx = pad.sThumbLX / 32767.0f, ly = pad.sThumbLY / 32767.0f;
            if (lx * lx + ly * ly > x * x + y * y) { x = lx; y = ly; }
        }
        bool deflected = sqrtf(x * x + y * y) >= g_radDead;
        float angle = deflected ? atan2f(x, y) : 0.0f;   // clockwise from up
        POINT cur = {};
        static POINT lastCur = {};
        bool mouseMoved = true;
        if (GetCursorPos(&cur)) {
            // Mode=menu: the mouse picks only while it moves (a resting mouse does not undo a D-pad / arrow step)
            mouseMoved = !menu || cur.x != lastCur.x || cur.y != lastCur.y;
            lastCur = cur;
            float dx = static_cast<float>(cur.x - g_radMouseOrigin.x), dy = static_cast<float>(cur.y - g_radMouseOrigin.y);
            float dist = sqrtf(dx * dx + dy * dy), limit = 160.0f * g_radScale;
            if (dist > limit) {              // keep the virtual cursor on the ring: the origin follows
                g_radMouseOrigin.x = cur.x - static_cast<LONG>(dx * limit / dist);
                g_radMouseOrigin.y = cur.y - static_cast<LONG>(dy * limit / dist);
                dx = dx * limit / dist;
                dy = dy * limit / dist;
                dist = limit;
            }
            g_radMouseDx = dx;
            g_radMouseDy = dy;
            if (!deflected && mouseMoved && dist >= 60.0f * g_radScale * g_radDead) {
                deflected = true;
                angle = atan2f(dx, -dy);
            }
        }
        int sector = -1;
        if (deflected && n > 0) {
            if (angle < 0.0f) angle += 2.0f * kPi;
            float step = 2.0f * kPi / static_cast<float>(n);
            sector = static_cast<int>((angle + step * 0.5f) / step) % n;
        }
        if (sector >= 0) {
            g_radSel = sector;
            g_radMoved = true;
        } else if (g_radOpen == 1 && g_radMoved) {
            g_radSel = -1;                   // hold mode: back in the centre = nothing picked (release = cancel)
        }
        if (menu) {                          // 0.10.1: the quit sector's 10 s window, pointing away, the 1 s hold
            bool confirmHeld = (have && (pad.wButtons & 0x1000)) || (keys & 1) || (clicks & 1);
            RadQuitTick(confirmHeld);
        }
    }
    LeaveCriticalSection(&g_radLock);
}

// one text centred on <at>, broken at spaces into lines of at most <width> pixels
void RadText(ImDrawList *dl, ImFont *font, float size, ImVec2 at, ImU32 col, const char *text, float width) {
    char lines[4][64];
    int count = 0;
    const char *p = text;
    while (*p && count < 4) {
        int len = 0, lastSpace = -1;
        while (p[len] && len < 63) {
            char probe[64];
            memcpy(probe, p, static_cast<size_t>(len) + 1);
            probe[len + 1] = 0;
            if (font->CalcTextSizeA(size, FLT_MAX, 0.0f, probe).x > width && lastSpace > 0) break;
            if (p[len] == ' ') lastSpace = len;
            ++len;
        }
        if (p[len] && lastSpace > 0) len = lastSpace;
        memcpy(lines[count], p, static_cast<size_t>(len));
        lines[count][len] = 0;
        ++count;
        p += len;
        while (*p == ' ') ++p;
    }
    float lineH = size * 1.1f, top = at.y - lineH * static_cast<float>(count) * 0.5f;
    for (int i = 0; i < count; ++i) {
        float w = font->CalcTextSizeA(size, FLT_MAX, 0.0f, lines[i]).x;
        ImVec2 pos(at.x - w * 0.5f + 1.0f, top + lineH * static_cast<float>(i) + 1.0f);
        dl->AddText(font, size, pos, IM_COL32(0, 0, 0, 200), lines[i]);   // shadow
        dl->AddText(font, size, ImVec2(pos.x - 1.0f, pos.y - 1.0f), col, lines[i]);
    }
}

// the ring: 8 (or fewer) arc segments, the picked one bright, labels, on / off of switches, path + page in the centre
void DrawRadial() {
    ImGuiIO &io = ImGui::GetIO();
    ImDrawList *dl = ImGui::GetForegroundDrawList();
    ImFont *font = ImGui::GetFont();
    float h = io.DisplaySize.y, w = io.DisplaySize.x;
    if (h <= 0.0f || w <= 0.0f) return;
    EnterCriticalSection(&g_radLock);
    ImVec2 c(w * 0.5f, h * 0.5f);
    float outer = h * 0.36f * g_radScale, inner = outer * 0.42f, mid = (outer + inner) * 0.5f, thick = outer - inner;
    float size = h / 1080.0f * 25.0f * g_radScale;
    if (size < 11.0f) size = 11.0f;
    int n = RadPageCount(g_radLevel, g_radPage), pages = RadPages(g_radLevel);
    float step = n > 0 ? 2.0f * kPi / static_cast<float>(n) : 2.0f * kPi;
    float gap = n > 1 ? 0.03f : 0.0f;
    for (int i = 0; i < n; ++i) {
        const RadItem &e = *RadAt(g_radLevel, g_radPage, i);
        const char *why = RadialWhy(e);
        bool grey = why[0] != 0, hi = i == g_radSel;
        float a = -0.5f * kPi + step * static_cast<float>(i);   // centre angle: 0 = up, clockwise
        bool quit = e.special == kRadSpecialQuit, armed = quit && RadQuitArmed();
        bool claude = RadClaude(e);          // 0.10.5: coral #D97757 (217, 119, 87), white text
        ImU32 fill = grey ? (hi ? IM_COL32(95, 75, 60, 225) : IM_COL32(45, 45, 45, 175))
                   : armed ? IM_COL32(200, 40, 30, 245)
                   : quit ? (hi ? IM_COL32(150, 60, 50, 235) : IM_COL32(70, 28, 24, 205))
                   : claude ? (hi ? IM_COL32(238, 150, 119, 250) : IM_COL32(217, 119, 87, 235))
                   : e.child >= 0 ? (hi ? IM_COL32(70, 140, 95, 235) : IM_COL32(30, 55, 42, 205))
                                  : (hi ? IM_COL32(70, 110, 190, 235) : IM_COL32(28, 34, 50, 205));
        dl->PathClear();
        dl->PathArcTo(c, mid, a - step * 0.5f + gap, a + step * 0.5f - gap, 40);
        dl->PathStroke(fill, 0, thick);
        ImU32 rim = hi ? IM_COL32(255, 220, 90, 255) : IM_COL32(150, 160, 180, 120);
        dl->PathClear();
        dl->PathArcTo(c, outer, a - step * 0.5f + gap, a + step * 0.5f - gap, 40);
        dl->PathStroke(rim, 0, hi ? 3.0f : 1.5f);
        char text[64];
        _snprintf_s(text, sizeof(text), _TRUNCATE, "%s%s", e.label, e.child >= 0 ? " >" : "");
        if (e.child < 0 && !e.special) FlowRadLabel(e.id, text, sizeof(text));   // 0.11: "Weiter: <step>", "Ablauf n/m"
        if (armed) {                         // the countdown is only text: the arm belongs to the sector, not the label
            DWORD age = GetTickCount() - g_radQuitArmedAt;
            DWORD left = age < kQuitWindowMs ? (kQuitWindowMs - age + 999) / 1000 : 0;
            _snprintf_s(text, sizeof(text), _TRUNCATE, "A nochmal = beenden (%lu s)", left);
        }
        ImVec2 at(c.x + cosf(a) * mid, c.y + sinf(a) * mid);
        float width = thick * 1.25f, arc = mid * step * 0.85f;
        if (n > 1 && arc < width) width = arc;
        bool isBool = false;
        bool on = RadialOn(e, &isBool);
        ImU32 col = grey ? IM_COL32(150, 150, 150, 255) : claude ? IM_COL32(255, 255, 255, 255) : IM_COL32(240, 240, 240, 255);
        RadText(dl, font, size, ImVec2(at.x, at.y - (isBool || grey ? size * 0.45f : 0.0f)), col, text, width);
        if (isBool && !grey)
            RadText(dl, font, size * 0.85f, ImVec2(at.x, at.y + size * 1.0f),
                    on ? IM_COL32(110, 230, 120, 255) : IM_COL32(170, 170, 170, 255), on ? "on" : "off", width);
        else if (grey)
            RadText(dl, font, size * 0.75f, ImVec2(at.x, at.y + size * 1.0f), IM_COL32(220, 120, 100, 255), "n/a", width);
    }
    if (!n) RadText(dl, font, size, ImVec2(c.x, c.y - outer * 0.7f), IM_COL32(220, 120, 100, 255),
                    g_radItemCount ? "(empty level)" : "(no entries - TruMenu.radial.txt)", outer * 2.0f);
    // centre: path, page, the pick and why it is greyed
    dl->AddCircleFilled(c, inner * 0.94f, IM_COL32(14, 16, 22, 225), 48);
    dl->AddCircle(c, inner * 0.94f, IM_COL32(150, 160, 180, 140), 48, 1.5f);
    const char *path = g_radLevels[g_radLevel].path;
    bool claudeLevel = !_strnicmp(path, "Claude", 6) && (path[6] == 0 || path[6] == '/');   // 0.10.5: the title in coral
    RadText(dl, font, size * 0.9f, ImVec2(c.x, c.y - inner * 0.55f),
            claudeLevel ? IM_COL32(217, 119, 87, 255) : IM_COL32(255, 220, 90, 255), path[0] ? path : "TruMenu",
            inner * 1.6f);
    char line[160];
    if (pages > 1) {
        _snprintf_s(line, sizeof(line), _TRUNCATE, "page %d / %d  (LB / RB)", g_radPage + 1, pages);
        RadText(dl, font, size * 0.7f, ImVec2(c.x, c.y - inner * 0.25f), IM_COL32(200, 200, 200, 255), line, inner * 1.7f);
    }
    const RadItem *pick = RadAt(g_radLevel, g_radPage, g_radSel);
    if (pick) {
        const char *why = RadialWhy(*pick);
        if (pick->special == kRadSpecialQuit)
            _snprintf_s(line, sizeof(line), _TRUNCATE, "game.quit: A twice or hold A 1 s");
        else if (pick->child < 0 && !pick->special && FlowRadInfo(pick->id, pick->arg, line, sizeof(line))) {}   // 0.11
        else if (pick->info[0]) _snprintf_s(line, sizeof(line), _TRUNCATE, "%s", pick->info);   // 0.10.1: row hint
        else if (pick->special == kRadSpecialVirt) _snprintf_s(line, sizeof(line), _TRUNCATE, "-> %s", pick->label);
        else if (pick->child >= 0) _snprintf_s(line, sizeof(line), _TRUNCATE, "-> %s", g_radLevels[pick->child].path);
        else _snprintf_s(line, sizeof(line), _TRUNCATE, "%s%s%s", pick->id, pick->arg[0] ? " " : "", pick->arg);
        RadText(dl, font, size * 0.7f, ImVec2(c.x, c.y + inner * 0.12f), IM_COL32(170, 200, 255, 255), line, inner * 1.7f);
        if (why[0])
            RadText(dl, font, size * 0.65f, ImVec2(c.x, c.y + inner * 0.5f), IM_COL32(240, 120, 100, 255), why,
                    inner * 1.7f);
    } else {
        RadText(dl, font, size * 0.7f, ImVec2(c.x, c.y + inner * 0.2f), IM_COL32(170, 170, 170, 255),
                g_radOpen == 1 ? "centre = cancel" : "B = back", inner * 1.7f);
    }
    // mouse: a dot for the virtual cursor (direction since the open)
    if (g_radBy == kRadByKey || g_radBy == kRadByMouse || g_radMouseDx != 0.0f || g_radMouseDy != 0.0f) {
        float k = inner * 0.85f / (160.0f * g_radScale);
        dl->AddCircleFilled(ImVec2(c.x + g_radMouseDx * k, c.y + g_radMouseDy * k), size * 0.25f,
                            IM_COL32(255, 255, 255, 200), 16);
    }
    // under the ring: the controls of the mode, the last result
    const char *help = g_radMode == kRadModeMenu
        ? "stick / D-pad / mouse = pick   A / Enter / click = OK   B / Backspace = back   LB / RB = page   L3+R3 / F9 = close"
        : g_radOpen == 1
        ? "release = run   centre = cancel   A = run, stay open   B = back   LB / RB = page"
        : "stick / mouse = pick   A / click = run   R3 = run + close   B / right click = back   hold again = release runs";
    RadText(dl, font, size * 0.7f, ImVec2(c.x, c.y + outer + size * 1.2f), IM_COL32(210, 210, 210, 230), help, w * 0.9f);
    if (g_radResult[0] && GetTickCount() - g_radResultTick < 8000) {
        bool err = strstr(g_radResult, ": err ") != nullptr || strstr(g_radResult, "not available") != nullptr;
        RadText(dl, font, size * 0.75f, ImVec2(c.x, c.y + outer + size * 2.6f),
                err ? IM_COL32(255, 130, 110, 255) : IM_COL32(130, 230, 140, 255), g_radResult, w * 0.9f);
        if (strstr(g_radResult, "ok queued"))
            RadText(dl, font, size * 0.65f, ImVec2(c.x, c.y + outer + size * 3.9f), IM_COL32(200, 200, 200, 230),
                    g_lastAction, w * 0.9f);
    }
    LeaveCriticalSection(&g_radLock);
}

void ValRadialStatus(char *o, size_t n) {
    static const char *const modes[] = {"closed", "open (hold: the release runs)", "open (latched)"};
    static const char *const by[] = {"-", "pad", "key", "mouse button", "radial.open"};
    LONG open = g_radOpen, who = g_radBy;
    EnterCriticalSection(&g_radLock);
    Out(o, n, "enabled %d (hold 0x%04x %d ms%s, key 0x%02x (DirectInput 0x%02lx), mouse button %d, remember %d, pass left "
        "stick %d, slow motion %.2f, deadzone %.2f, scale %.2f); file %s: %s, %d dropped, %d unknown, %d skipped; ring %s "
        "by %s at '%s' page %d / %d; %ld entries run; spawn %s (Spawn=%d)", g_radEnabled, g_radHold, g_radHoldMs,
        g_radHold && g_radHold == g_toggleButtons ? " = the menu combo: short = menu at the release" : "", g_radKey,
        g_radKeyDik, g_radMouse, g_radRemember, g_radPassLeft, g_radSlow, g_radDead, g_radScale,
        g_radFilePath[0] ? g_radFilePath : "-", g_radFileState, g_radDropped, g_radUnknown, g_radSkipped,
        modes[open >= 0 && open <= 2 ? open : 0], by[who >= 0 && who <= 4 ? who : 0], g_radLevels[g_radLevel].path,
        g_radPage + 1, RadPages(g_radLevel), g_radRuns, g_spawnOk ? "code ok" : g_spawnWhy, g_radSpawn);
    size_t used = strlen(o);                 // 0.10.1
    int freezeNow = RadFreezeRead();
    if (used + 1 < n)
        _snprintf_s(o + used, n - used, _TRUNCATE, "; 0.10.1: mode %s, freeze %s (ini now %s; last open: %s), quit sector "
                    "%s, tests level %s (tour %s: %s)", g_radMode == kRadModeMenu ? "menu" : "wheel",
                    g_radFreeze == kRadFreezeWorld ? "world" : g_radFreeze == kRadFreezePlayer ? "player" : "0",
                    freezeNow == kRadFreezeWorld ? "world" : freezeNow == kRadFreezePlayer ? "player" : "0",
                    g_radFreezeState, g_radQuitItem >= 0 ? (RadQuitArmed() ? "ARMED" : "on") : "off",
                    g_radTestsLevel >= 0 ? "on" : "off", g_radTourPath[0] ? g_radTourPath : "-", g_radTourState);
    LeaveCriticalSection(&g_radLock);
}

void ValRadialList(char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    EnterCriticalSection(&g_radLock);
    for (int i = 0; i < g_radItemCount; ++i) {
        const RadItem &e = g_radItems[i];
        if (e.child >= 0) continue;
        if (e.special == kRadSpecialQuit) {  // 0.10.1: the built-in sector (not from the file, no item run)
            int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s- | %s | (built-in game.quit safety sector)",
                                used ? "; " : "", e.label);
            if (w < 0) break;
            used += static_cast<size_t>(w);
            continue;
        }
        const char *why = RadialWhy(e);
        int w = _snprintf_s(o + used, n - used, _TRUNCATE, "%s%s | %s | %s%s%s%s%s", used ? "; " : "", e.path[0] ? e.path : "-",
                            e.label, e.id, e.arg[0] ? " " : "", e.arg, why[0] ? " = greyed: " : "", why);
        if (w < 0) break;
        used += static_cast<size_t>(w);
    }
    LeaveCriticalSection(&g_radLock);
    if (!used) Out(o, n, "(no entries: %s)", g_radFileState);
}

bool RunRadialReload(const char *, char *o, size_t n) {
    if (!g_radEnabled) { Out(o, n, "radial menu off ([Radial] Enabled=0)"); return false; }
    if (g_radOpen) { Out(o, n, "close the ring first"); return false; }
    EnterCriticalSection(&g_radLock);
    RadialLoad();
    Out(o, n, "%s: %s, %d dropped, %d unknown, %d skipped", g_radFilePath, g_radFileState, g_radDropped, g_radUnknown,
        g_radSkipped);
    LeaveCriticalSection(&g_radLock);
    return true;
}

bool RunRadialOpen(const char *arg, char *o, size_t n) {
    if (!g_radEnabled) { Out(o, n, "radial menu off ([Radial] Enabled=0)"); return false; }
    if (g_menuOpen) { Out(o, n, "close TruMenu first (the ring and the menu are never open together)"); return false; }
    EnterCriticalSection(&g_radLock);
    strncpy_s(g_radOpenPath, sizeof(g_radOpenPath), arg ? arg : "", _TRUNCATE);
    RadTrim(g_radOpenPath);
    bool known = !g_radOpenPath[0];
    for (int i = 0; i < g_radLevelCount && !known; ++i) known = !_stricmp(g_radLevels[i].path, g_radOpenPath);
    LeaveCriticalSection(&g_radLock);
    if (!known) { Out(o, n, "no level '%s' (radial.list)", g_radOpenPath); return false; }
    InterlockedExchange(&g_radOpenReq, 1);
    Out(o, n, "ring opens latched at '%s' with the next frame (B at the top closes it)", g_radOpenPath);
    return true;
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
        if (TmButton(label)) QueueItem("level.load", name);
    }
    if (unit[0] && TmButton("Reload current unit  [level.reload]")) QueueItem("level.reload", "");
    // 0.7.1: the mission menu's start (main menu only) - the intro plays, unlike level.load
    if (g_missionOk) {                                     // 0.7.2: DLC 1 first
        if (TmButton("Start DLC 1 as the mission menu (intro)  [level.start dlc1]")) QueueItem("level.start", "dlc1");
        if (TmButton("Start DLC 2 as the mission menu (intro)  [level.start dlc2]")) QueueItem("level.start", "dlc2");
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
                if (TmButton(label)) QueueItem("level.load", kUnits[k].unit);
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
    TmCheckbox("reload the current unit after choosing  [costume.setreload]", &reload);
    if (TmButton("Reset chosen costume (0 / 0 / 0)  [costume.reset]")) QueueItem("costume.reset", "");
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
        _snprintf_s(label, sizeof(label), _TRUNCATE, "%2d  %s  (%d)%s%s###cos%d", i, name, id, chosen ? "  [chosen]" : "",
                    now ? "  [current]" : "", i);
        if (!id) ImGui::BeginDisabled();
        if (TmButton(label)) {
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
    if (TmCheckbox("Show Lara's position (top left)", &overlay)) InterlockedExchange(&g_overlay, overlay);
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
    if (TmButton("CAMERA_SetMode(mode)  [camera.mode]")) QueueItem("camera.mode", arg);
    if (TmButton("Restore game camera  [camera.restore]")) QueueItem("camera.restore", "");
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
    // 0.8.1: the target state, not "" (= flip): a request run twice can no longer switch it back; "###" = one id for
    // both labels (the focus stays on the button when its label changes)
    if (TmButton(cheat ? "Cheat / flight OFF  [cheat.flight]###flight" : "Cheat / flight ON  [cheat.flight]###flight"))
        QueueItem("cheat.flight", cheat ? "0" : "1");
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
    if (TmCheckbox("draw markup  [draw.markup]", &markup)) { char o[96]; RunDrawMarkup(markup ? "1" : "0", o, sizeof(o)); }
    ImGui::SameLine();
    if (TmCheckbox("ledges only  [draw.ledges]", &ledges)) { char o[96]; RunDrawLedges(ledges ? "1" : "0", o, sizeof(o)); }
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
    ImGui::TextWrapped("0.8: cheats god %s, god full %s, one-hit kill %s, enemy health %s, infinite ammo %s, fill %s, "
                       "cheat code %s; camera log %s; regression dlc1 %d / dlc2 %d rows", g_godOk ? "ok" : "NO",
                       g_godFullOk ? "ok" : "NO", g_ohkOk ? "ok" : "NO", g_enemyHpOk ? "ok" : "NO",
                       g_infAmmoOk ? "ok" : "NO", g_fillOk ? "ok" : "NO", g_codeOk ? "ok" : "NO",
                       g_camLogOk ? "ok" : "NO", g_regCount[0], g_regCount[1]);
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
        if (TmCheckbox(text, &on)) QueueItem(id, on ? "1" : "0");
    } else if (strcmp(type, "info") == 0) {
        _snprintf_s(text, sizeof(text), _TRUNCATE, "%s: %.120s###wi", id, value);
        TmSelectable(text);
    } else {
        _snprintf_s(text, sizeof(text), _TRUNCATE, "%s  [%s]%s%s###wb", label, id, value[0] ? " = " : "", value);
        if (TmButton(text)) QueueItem(id, "");
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
            if (TmSelectable(item.id)) FavToggle(item.id);
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
bool g_rowX = false, g_rowY = false;          // 0.8: X / Y edge of this frame for the focused TO TEST / Regression row
bool g_rowFocusAny = false;                   // 0.8: a TO TEST or Regression row had the focus this frame

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
        if (TmCheckbox(label, &on)) TestMarkFromMenu(t.id, on ? "on" : "off");
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
    bool xPressed = g_rowX, yPressed = g_rowY;   // 0.8: taken once per frame in DrawMenu (TO TEST + Regression)
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
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s %2d. %s###ts", done ? "[DONE]" : i == nextStep ? "NEXT->" : "      ",
                        t.num, t.hint[0] ? t.hint : "(no text)");
            ImVec4 colour = done ? ImVec4(0.6f, 0.6f, 0.6f, 1.0f) : i == nextStep ? ImVec4(1.0f, 0.85f, 0.3f, 1.0f)
                                                                                  : ImVec4(0.75f, 0.85f, 1.0f, 1.0f);
            ImGui::PushStyleColor(ImGuiCol_Text, colour);
            bool activated = TmSelectable(label);
            ImGui::PopStyleColor();
            if (activated) {
                if (runnable) QueueItem(itemId, runArg);
                TestMarkFromMenu(t.id, "done");
            }
            ImGui::Indent();
            if (runnable) {
                char run[160];
                _snprintf_s(run, sizeof(run), _TRUNCATE, "Run %s%s%s", itemId, runArg[0] ? " " : "", runArg);
                if (TmSmallButton(run)) QueueItem(itemId, runArg);
                ImGui::SameLine();
            } else if (t.target[0]) {
                ImGui::TextDisabled("(%s: no such item)", t.target);
                ImGui::SameLine();
            }
            if (TmSmallButton(done ? "Open again" : "Done")) TestMarkFromMenu(t.id, done ? "open" : "done");
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
        _snprintf_s(label, sizeof(label), _TRUNCATE, "%s  %s   [%s]%s%s###tc", ok ? "[OK]  " : fail ? "[FAIL]" : skip ? "[SKIP]" : "[    ]",
                    t.hint[0] ? t.hint : "(no hint)", t.id, t.note[0] ? "  - " : "", t.note);
        ImGui::PushStyleColor(ImGuiCol_Text, colour);
        bool activated = TmSelectable(label);
        ImGui::PopStyleColor();
        if (ImGui::IsItemFocused()) {
            anyFocus = true;
            if (xPressed) TestMarkFromMenu(t.id, "fail");
            else if (yPressed) TestMarkFromMenu(t.id, "skip");
        }
        if (activated) TestMarkFromMenu(t.id, "ok");
        ImGui::Indent();
        if (TmSmallButton("OK")) TestMarkFromMenu(t.id, "ok");
        ImGui::SameLine();
        if (TmSmallButton("FAIL")) TestMarkFromMenu(t.id, "fail");
        ImGui::SameLine();
        if (TmSmallButton("SKIP")) TestMarkFromMenu(t.id, "skip");
        char itemId[64];
        strncpy_s(itemId, sizeof(itemId), t.id, _TRUNCATE);
        char *colon = strchr(itemId, ':');
        const char *runArg = "";
        if (colon) { *colon = 0; runArg = t.id + (colon - itemId) + 1; }
        if (ItemUsable(itemId)) {
            ImGui::SameLine();
            char run[160];
            _snprintf_s(run, sizeof(run), _TRUNCATE, "Run %s%s%s", itemId, runArg[0] ? " " : "", runArg);
            if (TmSmallButton(run)) QueueItem(itemId, runArg);
        }
        if (t.when[0]) {
            ImGui::SameLine();
            ImGui::TextDisabled("%s", t.when);
        }
        ImGui::Unindent();
        ImGui::PopID();
    }
    if (anyFocus) g_rowFocusAny = true;          // 0.8: DrawMenu sets g_testFocus from both pages
    if (TmButton("Remove the marked rows  [test.clear done]")) { char o[160]; RunTestClear("done", o, sizeof(o)); }
    ImGui::SameLine();
    if (ConfirmButton("Remove all rows  [test.clear]", "testclear")) { char o[160]; RunTestClear("", o, sizeof(o)); }
}

// 0.8 Regression page: selector DLC 1 / DLC 2 / all; checks A = OK, X = FAIL, Y = SKIP (as TO TEST); "Note" puts
// "regress.note <list>:<id> " into the command bar and opens the on-screen keyboard; steps: A = run + done
void RegMarkFromMenu(int list, const char *id, const char *state) {
    char spec[96], o[300];
    _snprintf_s(spec, sizeof(spec), _TRUNCATE, "%s:%s", kRegNames[list], id);
    RegMark(spec, state, nullptr, o, sizeof(o));
    _snprintf_s(g_lastAction, sizeof(g_lastAction), _TRUNCATE, "%s", o);
}
void RegNoteFromMenu(int list, const char *id, const char *note) {
    _snprintf_s(g_cmdBuf, sizeof(g_cmdBuf), _TRUNCATE, "regress.note %s:%s %s", kRegNames[list], id, note);
    strncpy_s(g_cmdSetText, sizeof(g_cmdSetText), g_cmdBuf, _TRUNCATE);   // if the text field is active already
    g_cmdSetPending = true;
    OskEdited();
    char o[160];
    if (g_cmdKeyboard) RunCmdKeyboard("", o, sizeof(o));
    else RunCmdFocus("", o, sizeof(o));
    _snprintf_s(g_lastAction, sizeof(g_lastAction), _TRUNCATE, "note for %s:%s - type it in the command bar, Enter / Run "
                "saves (%s)", kRegNames[list], id, o);
}

void PageRegress() {
    static TestRow rows[kRegLists][kTestMax];
    static char shortcut[kRegLists][kTestMax][kShortcutLen];   // 0.8.1 column 9
    int count[kRegLists];
    bool found[kRegLists];
    EnterCriticalSection(&g_testLock);
    for (int l = 0; l < kRegLists; ++l) {
        count[l] = g_regCount[l];
        found[l] = g_regFound[l];
        memcpy(rows[l], g_reg[l], sizeof(TestRow) * static_cast<size_t>(count[l]));
        memcpy(shortcut[l], g_regShortcut[l], kShortcutLen * static_cast<size_t>(count[l]));
    }
    LeaveCriticalSection(&g_testLock);
    // 0.8.1 regression shortcuts: "Prepare" per row and this quick list (one button per distinct shortcut)
    auto prepare = [](int list, const TestRow &t) {
        char spec[96], o[300];
        _snprintf_s(spec, sizeof(spec), _TRUNCATE, "%s:%s", kRegNames[list], t.id);
        bool ok = RunRegressPrepare(spec, o, sizeof(o));
        SetLastAction("regress.prepare", ok, o);
    };
    {
        char state[220];
        ValShortcut(state, sizeof(state));
        bool running = g_scActive != 0;
        int shown = 0;
        for (int l = 0; l < kRegLists; ++l) {
            if (g_regSel != 2 && g_regSel != l) continue;
            for (int i = 0; i < count[l]; ++i) {
                if (!shortcut[l][i][0]) continue;
                bool dup = false;
                for (int j = 0; j < i && !dup; ++j) dup = !strcmp(shortcut[l][j], shortcut[l][i]);
                if (dup) continue;
                if (!shown++) ImGui::SeparatorText("Quick prepare (regression shortcuts)  [regress.prepare]");
                char title[96] = "", steps[kScMaxSteps][kScStepLen], o[80], label[200];
                int c = 0;
                ShortcutParse(shortcut[l][i], title, sizeof(title), steps, &c, o, sizeof(o));
                _snprintf_s(label, sizeof(label), _TRUNCATE, "%s  (%s:%s)###qp%d_%d", title[0] ? title : rows[l][i].id,
                            kRegNames[l], rows[l][i].id, l, i);
                if (TmButton(label)) prepare(l, rows[l][i]);
                if (ImGui::IsItemHovered() || ImGui::IsItemFocused()) ImGui::SetItemTooltip("%s", shortcut[l][i]);
            }
        }
        if (shown || running) {
            ImGui::TextDisabled("shortcut: %s", state);
            if (running) {
                ImGui::SameLine();
                if (TmSmallButton("Stop###scstop")) {
                    char o[120];
                    RunRegressPrepare("stop", o, sizeof(o));
                }
            }
        }
    }
    ImGui::TextWrapped("Fixed lists (tests\\regress in the repo, copied next to the .asi by Set-TruMenu.ps1). Checks: A = OK, "
                       "X = FAIL, Y = SKIP, Note = text via the command bar / keyboard. Steps: A = run + done. Every mark "
                       "is appended to %s (session %s).", g_regResultsPath[0] ? g_regResultsPath : "-", g_regSession);
    const char *selName[] = {"DLC 1", "DLC 2", "all"};
    for (int s = 0; s < 3; ++s) {
        if (s) ImGui::SameLine();
        char label[64];
        _snprintf_s(label, sizeof(label), _TRUNCATE, g_regSel == s ? "[%s]###rsel%d" : "%s###rsel%d", selName[s], s);
        if (TmButton(label)) g_regSel = s;
    }
    ImGui::SameLine();
    if (ConfirmButton("Reload lists (all rows open)  [regress.load]", "regload")) {
        char o[300];
        bool ok = RunRegressLoad(g_regSel == 2 ? "all" : kRegNames[g_regSel], o, sizeof(o));
        SetLastAction("regress.load", ok, o);
    }
    bool xPressed = g_rowX, yPressed = g_rowY, anyFocus = false;
    for (int l = 0; l < kRegLists; ++l) {
        if (g_regSel != 2 && g_regSel != l) continue;
        int open = 0, ok = 0, fail = 0, skip = 0;
        for (int i = 0; i < count[l]; ++i) {
            const TestRow &t = rows[l][i];
            if (!TestIs(t, "check")) continue;
            if (!_stricmp(t.state, "ok")) ++ok; else if (!_stricmp(t.state, "fail")) ++fail;
            else if (!_stricmp(t.state, "skip")) ++skip; else ++open;
        }
        char head[160];
        _snprintf_s(head, sizeof(head), _TRUNCATE, "%s: %d open, %d ok, %d fail, %d skip%s", l ? "DLC 2 (Lara's Shadow)"
                    : "DLC 1 (Beneath the Ashes)", open, ok, fail, skip, found[l] ? "" : " - TruMenu.regress file missing");
        ImGui::SeparatorText(head);
        for (int i = 0; i < count[l]; ++i) {
            const TestRow &t = rows[l][i];
            ImGui::PushID(l * 1000 + i);
            if (TestIs(t, "step")) {
                bool done = !_stricmp(t.state, "done");
                char itemId[64];
                const char *runArg = "";
                bool runnable = t.target[0] && TestRunTarget(t.target, itemId, sizeof(itemId), &runArg);
                char label[512];
                _snprintf_s(label, sizeof(label), _TRUNCATE, "%s %2d. %s###rs", done ? "[DONE]" : "      ", t.num, t.hint);
                ImGui::PushStyleColor(ImGuiCol_Text, done ? ImVec4(0.6f, 0.6f, 0.6f, 1.0f) : ImVec4(0.75f, 0.85f, 1.0f, 1.0f));
                bool activated = TmSelectable(label);
                ImGui::PopStyleColor();
                if (activated) {
                    if (runnable) QueueItem(itemId, runArg);
                    RegMarkFromMenu(l, t.id, "done");
                }
                ImGui::Indent();
                if (runnable) {
                    char run[160];
                    _snprintf_s(run, sizeof(run), _TRUNCATE, "Run %s%s%s", itemId, runArg[0] ? " " : "", runArg);
                    if (TmSmallButton(run)) QueueItem(itemId, runArg);
                    ImGui::SameLine();
                }
                if (shortcut[l][i][0]) {                 // 0.8.1
                    if (TmSmallButton("Prepare###prep")) prepare(l, t);
                    if (ImGui::IsItemHovered() || ImGui::IsItemFocused()) ImGui::SetItemTooltip("%s", shortcut[l][i]);
                    ImGui::SameLine();
                }
                if (TmSmallButton(done ? "Open again###done" : "Done###done"))
                    RegMarkFromMenu(l, t.id, done ? "open" : "done");
                ImGui::Unindent();
                ImGui::PopID();
                continue;
            }
            bool okS = !_stricmp(t.state, "ok"), failS = !_stricmp(t.state, "fail"), skipS = !_stricmp(t.state, "skip");
            ImVec4 colour = okS ? ImVec4(0.45f, 1.0f, 0.45f, 1.0f) : failS ? ImVec4(1.0f, 0.45f, 0.4f, 1.0f)
                          : skipS ? ImVec4(0.65f, 0.65f, 0.65f, 1.0f) : ImVec4(1.0f, 1.0f, 1.0f, 1.0f);
            char label[512];
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s  %s   [%s]%s%s###rc", okS ? "[OK]  " : failS ? "[FAIL]" : skipS ? "[SKIP]"
                        : "[    ]", t.hint[0] ? t.hint : "(no text)", t.id, t.note[0] ? "  - " : "", t.note);
            ImGui::PushStyleColor(ImGuiCol_Text, colour);
            bool activated = TmSelectable(label);
            ImGui::PopStyleColor();
            if (ImGui::IsItemFocused()) {
                anyFocus = true;
                if (xPressed) RegMarkFromMenu(l, t.id, "fail");
                else if (yPressed) RegMarkFromMenu(l, t.id, "skip");
            }
            if (activated) RegMarkFromMenu(l, t.id, "ok");
            ImGui::Indent();
            if (TmSmallButton("OK")) RegMarkFromMenu(l, t.id, "ok");
            ImGui::SameLine();
            if (TmSmallButton("FAIL")) RegMarkFromMenu(l, t.id, "fail");
            ImGui::SameLine();
            if (TmSmallButton("SKIP")) RegMarkFromMenu(l, t.id, "skip");
            ImGui::SameLine();
            if (TmSmallButton("Note")) RegNoteFromMenu(l, t.id, t.note);
            if (shortcut[l][i][0]) {                     // 0.8.1
                ImGui::SameLine();
                if (TmSmallButton("Prepare###prep")) prepare(l, t);
                if (ImGui::IsItemHovered() || ImGui::IsItemFocused()) ImGui::SetItemTooltip("%s", shortcut[l][i]);
            }
            if (t.when[0]) {
                ImGui::SameLine();
                ImGui::TextDisabled("%s", t.when);
            }
            ImGui::Unindent();
            ImGui::PopID();
        }
        if (!count[l]) ImGui::TextDisabled(found[l] ? "(no rows)" : "(install with Set-TruMenu.ps1 -Install: it copies the lists)");
    }
    if (anyFocus) g_rowFocusAny = true;
}

// 0.8 Cheats page: one row per cheat with its category; a failed pre-check shows the row disabled with the reason
void CheatRowWidget(const char *id, int cat, bool ok, const char *why) {
    const Item *item = FindItem(id);
    if (!item) return;
    ImGui::PushID(id);
    char value[256] = "";
    item->value(value, sizeof(value));
    bool usable = ok && g_cheatsEnabled && g_experimental && InLevel();
    if (!usable) ImGui::BeginDisabled();
    char label[300];
    if (!strcmp(item->type, "bool")) {
        bool on = value[0] == '1';
        _snprintf_s(label, sizeof(label), _TRUNCATE, "%s  [%s]", id, kCheatCatNames[cat]);
        if (TmCheckbox(label, &on)) QueueItem(id, on ? "1" : "0");
    } else {
        _snprintf_s(label, sizeof(label), _TRUNCATE, "%s  [%s]", id, kCheatCatNames[cat]);
        if (TmButton(label)) QueueItem(id, "");
    }
    if (!usable) ImGui::EndDisabled();
    FavKey(id);
    ImGui::Indent();
    ImGui::TextDisabled("%s", item->label);
    if (!ok) {
        ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(1.0f, 0.5f, 0.4f, 1.0f));
        ImGui::TextWrapped("disabled: %s", why);
        ImGui::PopStyleColor();
    }
    ImGui::Unindent();
    ImGui::PopID();
}

void PageCheats() {
    ImGui::TextWrapped("From the 2007 prototype evaluation (docs\\Befund-Prototyp-2007.md 3i), static facts - every row is "
                       "a live TO TEST. Runs on the game thread, in a level only; each switch logs on / off. [Cheats] "
                       "Enabled=%d, Persist=%d (0 = all off at every game start).", g_cheatsEnabled, g_cheatPersist);
    if (!g_cheatsEnabled) ImGui::TextUnformatted("([Cheats] Enabled=0: list only)");
    else if (!g_experimental) ImGui::TextUnformatted("([Cheat] Experimental=0: list only)");
    else if (!InLevel()) ImGui::TextUnformatted("needs a level (no player instance) - the switches are greyed out");
    ImGui::SeparatorText("PC has it (switchable)");
    CheatRowWidget("cheat.god", kCatSwitch, g_godOk, g_godWhy);
    CheatRowWidget("cheat.godfull", kCatSwitch, g_godFullOk, g_godFullWhy);
    CheatRowWidget("cheat.onehitkill", kCatSwitch, g_ohkOk, g_ohkWhy);
    CheatRowWidget("cheat.enemyhealth", kCatSwitch, g_enemyHpOk, g_enemyHpWhy);
    ImGui::SeparatorText("Logic present, entry cut (re-attach)");
    CheatRowWidget("cheat.ammo", kCatReattach, g_infAmmoOk, g_infAmmoWhy);
    CheatRowWidget("cheat.fillup", kCatReattach, g_fillOk, g_fillWhy);
    ImGui::SeparatorText("Cheat-code path: DEBUG_ApplyCheatCode 0x5d3520 (as a completed pad code)");
    {
        static const int codes[] = {1, 2, 9, 10, 11};
        bool usable = g_codeOk && g_cheatsEnabled && g_experimental && InLevel();
        if (!usable) ImGui::BeginDisabled();
        for (int i = 0; i < 5; ++i) {
            if (i) ImGui::SameLine();
            char label[48], arg[8];
            _snprintf_s(label, sizeof(label), _TRUNCATE, "code %d##cc%d", codes[i], codes[i]);
            _snprintf_s(arg, sizeof(arg), _TRUNCATE, "%d", codes[i]);
            if (TmButton(label)) QueueItem("cheat.code", arg);
            if (ImGui::IsItemHovered()) ImGui::SetTooltip("%s", CheatCodeName(codes[i]));
        }
        if (!usable) ImGui::EndDisabled();
        char v[200];
        ValCheatCode(v, sizeof(v));
        ImGui::TextDisabled("[cheat.code] 1 one-hit kill, 2 god, 9 wireframe, 10 textureless, 11 enemy health - %s", v);
        if (!g_codeOk) ImGui::TextWrapped("disabled: %s", g_codeWhy);
    }
    ImGui::SeparatorText("Flag + reader gone: rebuild from the prototype (not built yet)");
    ImGui::BeginDisabled();
    for (const RebuildRow &r : kRebuildRows) {
        ImGui::TextWrapped("%s - not built yet", r.name);
        ImGui::Indent();
        ImGui::TextWrapped("prototype: %s; PC: %s", r.proto, r.pc);
        ImGui::Unindent();
    }
    ImGui::EndDisabled();
}

// in-menu confirmation (no dialogs): the first A arms a button for 5 s, the second A runs it
bool ConfirmButton(const char *label, const char *key) {
    static char armed[32] = "";
    static DWORD armedAt = 0;
    bool isArmed = strcmp(armed, key) == 0 && GetTickCount() - armedAt < 5000;
    char text[160];
    _snprintf_s(text, sizeof(text), _TRUNCATE, isArmed ? "%s - press A again to confirm###%s" : "%s###%s", label, key);
    if (isArmed) ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.7f, 0.2f, 0.1f, 1.0f));
    bool pressed = TmButton(text);
    if (isArmed) ImGui::PopStyleColor();
    if (!pressed) return false;
    if (isArmed) { armed[0] = 0; return true; }
    strncpy_s(armed, sizeof(armed), key, _TRUNCATE);
    armedAt = GetTickCount();
    return false;
}

void PageSettings() {
    Text("TruMenu.ini: %s", g_iniPath[0] ? g_iniPath : "-");
    static char all[16384];
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
    if (g_devPage != kDevRoot && TmButton("<< root page##devroot")) g_devPage = kDevRoot;
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
            if (TmButton(label)) g_devPage = d.target;
            break;
        }
        case kDevFlag:
        case kDevBool: {
            bool on = value[0] == '1';
            char label[120];
            _snprintf_s(label, sizeof(label), _TRUNCATE, "%s  [%s]", d.text, d.id);
            if (!g_experimental) ImGui::BeginDisabled();
            if (TmCheckbox(label, &on)) QueueItem(d.id, on ? "1" : "0");
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
            if (TmButton(label)) QueueItem(d.id, "");
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
            if (TmButton(label)) g_devPage = g_devPages[p];
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
    if (TmButton("time scale 1.0##ts1")) QueueItem("time.scale", "1");
    if (!g_timeOk || !g_experimental) ImGui::EndDisabled();
    ValPause(v, sizeof(v));
    bool paused = v[0] == '1';
    if (TmCheckbox("freeze world (streamFlags 0x1000)  [time.pause]", &paused)) QueueItem("time.pause", paused ? "1" : "0");
    ValUiHide(v, sizeof(v));
    bool hidden = v[0] == '1';
    if (TmCheckbox("hide HUD  [ui.hide]", &hidden)) QueueItem("ui.hide", hidden ? "1" : "0");
    if (!InLevel()) { ImGui::TextUnformatted("player items: needs a level"); return; }
    ValControl(v, sizeof(v));
    bool control = v[0] == '1';
    if (TmCheckbox("player control  [player.control]", &control)) QueueItem("player.control", control ? "1" : "0");
    if (TmButton("Ragdoll death  [player.die]")) QueueItem("player.die", "");
    if (TmButton("Mark position  [player.mark]")) QueueItem("player.mark", "");
    ImGui::SameLine();
    if (TmButton("Back to mark  [player.recall]")) QueueItem("player.recall", "");
    ImGui::SameLine();
    if (TmButton("Unstuck  [player.unstuck]")) QueueItem("player.unstuck", "");   // 0.8.1
    ValMark(v, sizeof(v));
    Text("mark: %s   (player.teleport x y z over TruLink)", v);
    ValUnstuck(v, sizeof(v));
    ImGui::TextWrapped("unstuck: %s - the newer of the mark and the last safe ground spot (>= 3 s old, >= 150 units "
                       "away); again within 20 s = one spot further back", v);
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
    if (g_healthOk && TmButton("Full health  [player.health]")) QueueItem("player.health", "");
    bool inv = g_invincible != 0;
    if (g_healthOk && TmCheckbox("invincible (health = max every frame)  [player.invincible]", &inv))
        QueueItem("player.invincible", inv ? "1" : "0");
    for (const WeaponName &w : kWeapons) {
        char label[64];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "Give %s##wg%d", w.name, w.id);
        if (!g_weaponOk) ImGui::BeginDisabled();
        if (TmButton(label)) QueueItem("weapon.give", w.name);
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
        _snprintf_s(label, sizeof(label), _TRUNCATE, "#%d  %s  intro %ld  (%.0f %.0f %.0f)###inst%d", i, x.name, x.intro,
                    x.pos[0], x.pos[1], x.pos[2], i);
        _snprintf_s(arg, sizeof(arg), _TRUNCATE, "#%d", i);
        if (ImGui::TreeNode(label)) {
            if (TmButton("Lara goes there  [player.goto]")) QueueItem("player.goto", arg);
            ImGui::SameLine();
            if (TmButton("Bring to Lara  [instance.bring]")) QueueItem("instance.bring", arg);
            if (TmButton("Unhide  [instance.unhide]")) QueueItem("instance.unhide", arg);
            ImGui::SameLine();
            if (TmButton("Remove  [instance.remove]")) QueueItem("instance.remove", arg);
            ImGui::TreePop();
        }
        return true;
    });
    Text("%d instances, %d shown (max 200)", index, shown > 200 ? 200 : shown);
    if (TmButton("Unhide all  [instance.unhideall]")) QueueItem("instance.unhideall", "");
}

void PageCostumeLive() {
    ImGui::TextWrapped("Live switch (the game's 0x6f0a90, as the costume native 0x79db50): altPlayerObjectID [0xe7f1cc] "
                       "= id, or 0 = next of the cycle list GlobalInfo [0xe7ee50]+4; then player message 35 (weapons).");
    if (!g_switchOk) { ImGui::TextUnformatted("costume switch code check failed"); return; }
    if (!InLevel()) { ImGui::TextUnformatted("needs a level"); return; }
    if (TmButton("Next outfit  [costume.next]")) QueueItem("costume.next", "");
    WORD ids[128];
    int c = GlobalCostumes(ids, 128);
    DWORD now = 0;
    ReadDword(kCostumeNow, &now);
    for (int i = 0; i < c; ++i) {
        char name[64], label[96], arg[16];
        if (!ObjectName(ids[i], name, sizeof(name))) Out(name, sizeof(name), "?");
        _snprintf_s(label, sizeof(label), _TRUNCATE, "%u %s%s###live%d", ids[i], name, ids[i] == now ? "  [current]" : "", i);
        _snprintf_s(arg, sizeof(arg), _TRUNCATE, "%u", ids[i]);
        if (TmButton(label)) QueueItem("costume.set", arg);
    }
    if (c < 0) ImGui::TextUnformatted("no GlobalInfo list");
}

void PageLog() {
    ImGui::TextWrapped("Tails of the Tru*.log files next to the .asi / tru.exe (once per second) and, with log.script on, "
                       "the game's script print / log natives.");
    bool overlay = g_logOverlay != 0;
    if (TmCheckbox("corner overlay  [log.overlay]", &overlay)) InterlockedExchange(&g_logOverlay, overlay ? 1 : 0);
    ImGui::SameLine();
    bool script = g_scriptLog != 0;
    if (!g_scriptOk) ImGui::BeginDisabled();
    if (TmCheckbox("script prints  [log.script]", &script)) QueueItem("log.script", script ? "1" : "0");
    if (!g_scriptOk) ImGui::EndDisabled();
    ImGui::SliderInt("lines  [log.lines]", &g_logLines, 1, 64);
    // sources: every tailed file + "script"
    if (TmButton(g_logFilter[0] ? "all##lf" : "[all]##lf")) g_logFilter[0] = 0;
    for (int i = 0; i < 16; ++i) {
        if (!g_tails[i].used) continue;
        ImGui::SameLine();
        char label[48];
        bool active = _stricmp(g_logFilter, g_tails[i].name) == 0;
        _snprintf_s(label, sizeof(label), _TRUNCATE, active ? "[%s]###lf%d" : "%s###lf%d", g_tails[i].name, i);
        if (TmButton(label)) strncpy_s(g_logFilter, sizeof(g_logFilter), g_tails[i].name, _TRUNCATE);
    }
    ImGui::SameLine();
    if (TmButton(_stricmp(g_logFilter, "script") == 0 ? "[script]##lfs" : "script##lfs"))
        strncpy_s(g_logFilter, sizeof(g_logFilter), "script", _TRUNCATE);
    ImGui::SameLine();
    if (TmButton("clear  [log.clear]")) { char o[64]; RunLogClear("", o, sizeof(o)); }
    {                                                                       // 0.7.2 overlay filter
        char src[300], exc[600];
        ValOvlSources(src, sizeof(src));
        ValOvlExclude(exc, sizeof(exc));
        ImGui::TextWrapped("overlay only: sources %s [log.overlaysources], exclude %s [log.overlayexclude]; the page "
                           "shows every source", src, exc);
    }
    // 0.4: collapse, TruLink reads, severity, rate
    bool collapse = g_logCollapse != 0, hide = g_logHideReads != 0;
    if (TmCheckbox("collapse repeats  [log.collapse]", &collapse)) InterlockedExchange(&g_logCollapse, collapse ? 1 : 0);
    ImGui::SameLine();
    if (TmCheckbox("hide TruLink reads  [log.hidereads]", &hide)) InterlockedExchange(&g_logHideReads, hide ? 1 : 0);
    ImGui::TextUnformatted("show  [log.level]:");
    for (int i = 0; i < 3; ++i) {
        ImGui::SameLine();
        char label[32];
        _snprintf_s(label, sizeof(label), _TRUNCATE, g_logMinLevel == i ? "[%s]###ll%d" : "%s###ll%d",
                    i == 0 ? "all" : i == 1 ? "warnings + errors" : "errors", i);
        if (TmButton(label)) g_logMinLevel = i;
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
        if (TmButton(label)) QueueItem("media.video.play", name);
        if (state != 10 || !g_movieOk) ImGui::EndDisabled();
        ImGui::SameLine();
        _snprintf_s(label, sizeof(label), _TRUNCATE, "as menu loop##vl%d", i);
        if (TmButton(label)) QueueItem("media.video.menuloop", name);
    }
    if (TmButton("menu loop back to medsea_loop")) QueueItem("media.video.menuloop", "");
    ImGui::TextWrapped("0x4a12b0(name, loop) is a blocking-style player (its callers loop while it plays): play only "
                       "from the main menu; experimental. The menu loop name is read when the main menu (re)starts "
                       "its background movie (0x5daf35).");
    char flags[1024];
    ValMediaVideoFlags(flags, sizeof(flags));
    ImGui::TextWrapped("videos (source, flag): %s   [media.video.flags]", flags);
}

// 0.9 P3: music through the engine's SRMUSIC_LoadMusic (catalog 11.2); every label with a stable ### id
void PageMusic() {
    char why[200] = "";
    bool place = MusicPlace(why, sizeof(why));
    bool can = g_musicOk && g_experimental && place;
    if (!g_musicOk) ImGui::TextColored(ImVec4(1.0f, 0.5f, 0.4f, 1.0f), "music off - code check: %s", g_musicCheck);
    else if (!g_experimental) ImGui::TextUnformatted("music items need [Cheat] Experimental=1");
    else if (!place) ImGui::TextColored(ImVec4(1.0f, 0.85f, 0.4f, 1.0f), "buttons disabled: %s", why);
    char now[1024];
    ValMusicNow(now, sizeof(now));
    ImGui::TextWrapped("now: %s   [media.music.now]", now);
    if (!can) ImGui::BeginDisabled();
    if (TmButton("Stop slot 0 (fade)  [media.music.stop]###mstop")) QueueItem("media.music.stop", "");
    ImGui::SameLine();
    if (TmButton("Stop all slots  [media.music.stop all]###mstopall")) QueueItem("media.music.stop", "all");
    if (!can) ImGui::EndDisabled();
    bool vars = false;
    char v[96];
    ValMusicVars(v, sizeof(v));
    vars = v[0] == '1';
    if (!g_musicVarsOk) ImGui::BeginDisabled();
    if (TmCheckbox("Show Music Vars (developer flag)  [dev.musicvars]###mvars", &vars)) QueueItem("dev.musicvars", vars ? "1" : "0");
    if (!g_musicVarsOk) ImGui::EndDisabled();
    ValMonsterMusicVars(v, sizeof(v));
    vars = v[0] == '1';
    ImGui::SameLine();
    if (!g_monsterVarsOk) ImGui::BeginDisabled();
    if (TmCheckbox("Show Monster Music Vars  [dev.monstermusicvars]###mmvars", &vars))
        QueueItem("dev.monstermusicvars", vars ? "1" : "0");
    if (!g_monsterVarsOk) ImGui::EndDisabled();
    if (g_mediaCount < 0) {
        ImGui::TextWrapped("no track list: %s missing (tools/music_list.py --menu-out <folder>; Set-TruMenu.ps1 copies "
                           "it next to the .asi). Nothing can be played without it.", g_mediaPath);
        return;
    }
    static char filter[32] = "";
    ImGui::InputText("track filter###mfilter", filter, sizeof(filter));
    for (int i = 0; i < g_mediaCount; ++i) {
        const MediaRow &r = g_media[i];
        if (_stricmp(r.kind, "music")) continue;
        if (filter[0] && !strstr(r.name, filter)) continue;
        bool unused = !strcmp(r.flag, "unused?");
        char label[128];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "Play###mp_%s", r.name);
        if (!can) ImGui::BeginDisabled();
        if (TmButton(label)) QueueItem("media.music.play", r.name);
        if (!can) ImGui::EndDisabled();
        ImGui::SameLine();
        if (unused) ImGui::TextColored(ImVec4(1.0f, 0.75f, 0.3f, 1.0f), "%s  [%s, unused?]", r.name, r.source);
        else Text("%s  [%s]", r.name, r.source);
    }
    ImGui::TextWrapped("Play = SRMUSIC_LoadMusic 0x594320(0, name, fade, fade) as the unit start 0x5b2211 does; Stop = "
                       "LoadMusic(slot, NULL, fade, 0) as the stop native 0x4aa490. DLC tracks of the port are "
                       "converted with silent audio (tools/music_convert.py) - they play silence. Experimental.");
}

// 0.9 P0d: Saves page (file operations; restore / delete / import with a backup first and a CONFIRM button)
void PageSaves() {
    static bool scanned = false;
    if (!scanned || TmButton("Refresh  [save.list]###svref")) { SaveScan(true); scanned = true; }
    ImGui::SameLine();
    if (TmButton("Back up all saves now  [save.backup]###svbak")) QueueItem("save.backup", "");
    char key[200];
    DWORD left = 0;
    if (SaveArmed(key, sizeof(key), &left)) {
        ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.7f, 0.2f, 0.1f, 1.0f));
        if (TmButton("CONFIRM  [run the armed action]###svconfirm")) {
            char item[32] = "", *space = strchr(key, ' ');
            if (space) {
                size_t len = static_cast<size_t>(space - key);
                if (len < sizeof(item)) { memcpy(item, key, len); item[len] = 0; }
                QueueItem(item, space + 1);
            }
        }
        ImGui::PopStyleColor();
        ImGui::SameLine();
        if (TmButton("cancel###svcancel")) SaveDisarm();
        ImGui::SameLine();
        ImGui::TextColored(ImVec4(1.0f, 0.45f, 0.4f, 1.0f), "armed: %s - %lu s left", key, (left + 999) / 1000);
    }
    EnterCriticalSection(&g_saveLock);
    ImGui::TextWrapped("folder: %s (%s)", g_saveFolderU8[0] ? g_saveFolderU8 : "-", g_saveFolderHow);
    ImGui::TextWrapped("backups / export / import: %s", g_saveRootU8);
    // copy the rows: QueueItem below runs file actions that take the lock again
    static SaveInfo rows[kSaveMax];
    static SaveDir backups[kSaveBackupMax], imports[kSaveImportMax];
    int count = g_saveCount < 0 ? 0 : g_saveCount, nb = g_saveBackupCount, ni = g_saveImportCount;
    for (int i = 0; i < count; ++i) rows[i] = g_saves[i];
    for (int i = 0; i < nb; ++i) backups[i] = g_saveBackups[i];
    for (int i = 0; i < ni; ++i) imports[i] = g_saveImports[i];
    LeaveCriticalSection(&g_saveLock);
    Text("saves: %d", count);
    for (int i = 0; i < count; ++i) {
        const SaveInfo &s = rows[i];
        char when[32], label[160];
        FileTimeText(s.written, when, sizeof(when));
        _snprintf_s(label, sizeof(label), _TRUNCATE, "Export###svx_%s", s.utf8);
        if (TmButton(label)) QueueItem("save.export", s.utf8);
        ImGui::SameLine();
        _snprintf_s(label, sizeof(label), _TRUNCATE, "Delete###svd_%s", s.utf8);
        if (TmButton(label)) QueueItem("save.delete", s.utf8);
        ImGui::SameLine();
        if (s.formatOk)
            ImGui::TextWrapped("%s | %s | %llu B | unit %s | checkpoint %lu | CRC ok", s.utf8, when, s.size,
                               s.unit[0] ? s.unit : "?", s.checkpoint);
        else
            ImGui::TextColored(ImVec4(1.0f, 0.5f, 0.4f, 1.0f), "%s | %s | %s", s.utf8, when, s.problem);
    }
    ImGui::Separator();
    Text("backups (newest first): %d", nb);
    for (int i = 0; i < nb; ++i) {
        char label[128];
        _snprintf_s(label, sizeof(label), _TRUNCATE, "Restore###svr_%s", backups[i].name);
        if (TmButton(label)) QueueItem("save.restore", backups[i].name);
        ImGui::SameLine();
        Text("%s  (%d file(s))", backups[i].name, backups[i].files);
    }
    if (ni) {
        ImGui::Separator();
        Text("import folder: %d file(s)", ni);
        for (int i = 0; i < ni; ++i) {
            char label[128];
            _snprintf_s(label, sizeof(label), _TRUNCATE, "Import###svi_%s", imports[i].name);
            if (!imports[i].files) ImGui::BeginDisabled();
            if (TmButton(label)) QueueItem("save.import", imports[i].name);
            if (!imports[i].files) ImGui::EndDisabled();
            ImGui::SameLine();
            Text("%s  %s", imports[i].name, imports[i].files ? "(CRC ok)" : "(CRC / format NOT ok - refused)");
        }
    }
    ImGui::TextWrapped("Delete / Restore / Import arm first: press the red CONFIRM button (or run the same command again) "
                       "within 10 s. Each of them copies all saves into a new backup folder before it changes "
                       "anything; nothing is deleted for good. Do not use while the game is saving. Restore copies the "
                       "backup's files over the save folder; other saves stay. The game reads the save list when its "
                       "load menu opens. No save field is changed by TruMenu (format: catalog 11.4).");
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
    // 0.8: X / Y edges once per frame for the focused TO TEST / Regression row
    g_rowX = InterlockedExchange(&g_testX, 0) != 0;
    g_rowY = InterlockedExchange(&g_testY, 0) != 0;
    g_rowFocusAny = false;
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
            bool show = TmCollapsingHeader(header, ImGuiTreeNodeFlags_DefaultOpen);
            ImGui::PopStyleColor();
            if (show) { PageTests(); testShown = true; }
        }
        (void)testShown;
        {                                                                   // 0.8 Regression page
            int ro = 0, rk = 0, rf = 0, rs = 0;
            EnterCriticalSection(&g_testLock);
            for (int l = 0; l < kRegLists; ++l) {
                if (g_regSel != 2 && g_regSel != l) continue;
                int o2, k2, f2, s2;
                RegCountsLocked(l, &o2, &k2, &f2, &s2);
                ro += o2; rk += k2; rf += f2; rs += s2;
            }
            LeaveCriticalSection(&g_testLock);
            char header[112];
            _snprintf_s(header, sizeof(header), _TRUNCATE, "Regression %s (%d open, %d ok, %d fail, %d skip)###regress",
                        g_regSel == 2 ? "DLC 1 + DLC 2" : g_regSel ? "DLC 2" : "DLC 1", ro, rk, rf, rs);
            if (TmCollapsingHeader(header)) PageRegress();
        }
        if (TmCollapsingHeader("Quick access / Favourites", ImGuiTreeNodeFlags_DefaultOpen)) PageFavourites();
        if (TmCollapsingHeader("Status")) PageStatus();
        if (TmCollapsingHeader("Developer menu (original)")) PageDev();
        if (TmCollapsingHeader("Time / player / HUD")) PageTimePlayer();
        if (TmCollapsingHeader("Instances")) PageInstances();
        if (TmCollapsingHeader("Outfits (live switch)")) PageCostumeLive();
        if (TmCollapsingHeader("Debug / Log")) PageLog();
        if (TmCollapsingHeader("Media: videos")) PageMedia();
        if (TmCollapsingHeader("Media: music (srmusic)###musicpage")) PageMusic();             // 0.9
        if (TmCollapsingHeader("Saves (backup / restore / export / import)###savespage")) PageSaves();   // 0.9
        if (TmCollapsingHeader("Settings")) PageSettings();
        if (TmCollapsingHeader("Overlay: Lara's position")) PageOverlay();
        if (TmCollapsingHeader("Free camera")) PageCamera();
        if (TmCollapsingHeader("Cheat / flight")) PageCheat();
        if (TmCollapsingHeader("Cheats (2007 prototype evaluation)")) PageCheats();   // 0.8
        if (TmCollapsingHeader("Markup / collision draw")) PageMarkup();
        if (TmCollapsingHeader("Debug view / Debug-Ansicht (0.12 - 0.14)###debugview")) PageDebugView();   // 0.14
        if (TmCollapsingHeader("Level select")) PageLevel();
        if (TmCollapsingHeader("Outfits (next level load)")) PageOutfits();
        if (TmCollapsingHeader("Dev channel")) {
            ImGui::TextWrapped("tru.exe has no developer channel (TCP 9264 is FMOD's profiler).");
            Todo("re-enable the compiled-out log stub 0x6457a0 (filtered by channel id) and show it here.");
        }
        ImGui::Separator();
        Text("last action: %s", g_lastAction);
        if (TmButton("Close menu")) open = false;
    }
    InterlockedExchange(&g_testFocus, g_rowFocusAny ? 1 : 0);   // 0.8: X / Y to the focused TO TEST / Regression row
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
    // (0.8.1: the tick is read first and the difference taken signed - the game thread may store a newer tick between
    // the two reads, and the unsigned wrap made "idle" true for one frame)
    DWORD lastPoll = g_lastPadHookTick;
    bool padIdle = static_cast<LONG>(GetTickCount() - lastPoll) > 250;
    XInputGetStateFn poll = g_selfPoll ? g_selfPoll : (padIdle ? RealXInput() : nullptr);
    if (poll) SelfPoll(poll);
    if (padIdle != g_padModeIdle) {
        g_padModeIdle = padIdle;
        Log(2, padIdle ? "pad: slot not polled - reading the pad in Present" : "pad: slot polled again");
    }
    if (padIdle && g_reqPending) RunPending();
    if (padIdle) WeaponsTick();
    KeyboardToggle();
    RadialTick();                                // 0.10 radial menu: key / mouse hold, the open ring's input
    MouseTick();                                 // 0.7: hold / release the game's cursor calls with the menu
    PauseTick();                                 // 0.7.1 [Menu] PauseGame
    AutoStartTick();                             // 0.7.1 [Test] AutoStart
    CameraTick();                                // 0.8 [Log] CameraChanges (read-only, every 200 ms)
    ShortcutTick();                              // 0.8.1 regression shortcuts (one command per free request slot)
    FlowTick();                                  // 0.11 Ablauf: events, deaths, the step's commands, auto checks
    // 0.8.1: at every open / close ImGui's keys are released (a key that went down in the menu and up after the close
    // - Enter of "level.load" closes the menu - stayed down for ImGui and repeated Enter in the bar at the next open:
    // run 224047, 22:47:45-53, an empty line every 100 ms); the close writes the input summary
    static bool wasOpen = false;
    static bool clearKeys = false;
    bool openNow = g_menuOpen != 0;
    if (openNow != wasOpen) {
        wasOpen = openNow;
        clearKeys = true;
        if (openNow) {
            EnterCriticalSection(&g_edgeLock);
            g_edgeCount = 0;                     // edges from before the open
            LeaveCriticalSection(&g_edgeLock);
            memset(g_trf, 0, sizeof(g_trf));
        } else {
            TraceSummary();
        }
    }
    bool flowDraw = FlowWantsDraw();             // 0.11 status line / flow.say toast
    if (!g_menuOpen && !g_overlay && !g_logOverlay && !g_guardOverlay && !g_drawMarkup && !g_lblOn && !g_radOpen &&
        !flowDraw)
        return;
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
    if (clearKeys) {
        clearKeys = false;
        io.ClearInputKeys();                     // keyboard + gamepad state and queued characters
    }
    TraceBegin();                                // 0.8.1 input trace: this frame's record + the edges so far
    FeedGamepad(io);
    ImGui::NewFrame();
    if (g_drawMarkup) DrawMarkup();
    if (g_lblOn) DrawLabels();                   // 0.13 Thrall-Labels (foreground draw list)
    if (DvAnyOn()) DrawDebugView();              // 0.14 debug view (background draw list)
    if (g_dvOn[kDvLegend]) DrawDebugLegend();    // 0.14 legend (foreground, top right)
    if (g_overlay) DrawOverlay();
    if (g_logOverlay) DrawLogOverlay();
    if (g_guardOverlay) DrawGuardOverlay();
    if (flowDraw) DrawFlowOverlay();             // 0.11
    if (g_menuOpen) DrawMenu();
    if (g_menuOpen) TraceEnd();
    if (g_radOpen && !g_menuOpen) DrawRadial();  // 0.10: foreground draw list, no ImGui window
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
    ShotBeforeRender(device);                // 0.10.5: hotkey + clean shots (the frame without TruMenu)
    Render(device);
    ShotFrame(device, false);                // 0.10.5: shot.save ui / [Shot] Clean=0 (the frame as on screen)
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
        ShotBeforeRender(device);            // 0.10.5 as PresentHook
        Render(device);
        ShotFrame(device, false);
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
        if (g_device) RegVersionsTick();             // 0.8: plugin versions + sha256 for the regression results (once)
        LogTailTick();
        FlowTailTick();                              // 0.11 Ablauf: (re)load the flow file, tail the logs it names
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
    g_pauseSound = g_pauseSoundIni = OptInt(ini, "Menu", "PauseSound") != 0 ? 1 : 0;      // 0.10.3
    g_unitChanges = OptInt(ini, "Log", "UnitChanges");
    OptString(ini, "Test", "AutoStart", g_autoStart, sizeof(g_autoStart));
    g_autoStartDelay = OptInt(ini, "Test", "AutoStartDelay");
    if (g_autoStartDelay < 1 || g_autoStartDelay > 60) g_autoStartDelay = atoi(OptDefault("Test", "AutoStartDelay"));
    g_outfitRule = OptInt(ini, "Levels", "OutfitRule") != 0;                  // 0.7.2
    EnterCriticalSection(&g_logRingLock);                                    // 0.7.2 overlay filter
    OptString(ini, "Log", "OverlaySources", g_ovlSources, sizeof(g_ovlSources));
    OptString(ini, "Log", "OverlayExclude", g_ovlExclude, sizeof(g_ovlExclude));
    LeaveCriticalSection(&g_logRingLock);
    // 0.8
    g_cheatsEnabled = OptInt(ini, "Cheats", "Enabled") != 0;
    g_cheatPersist = OptInt(ini, "Cheats", "Persist") != 0;
    OptString(ini, "Cheats", "State", g_cheatState, sizeof(g_cheatState));
    g_debugEnabled = OptInt(ini, "Debug", "Enabled") != 0 ? 1 : 0;                  // 0.12 Debug-Zeichnung
    g_navAutoMask = OptInt(ini, "Debug", "NavMask") != 0 ? 1 : 0;
    OptString(ini, "Debug", "NavDraw", g_navAuto, sizeof(g_navAuto));
    g_lblAtStart = OptInt(ini, "Debug", "Labels") != 0 ? 1 : 0;                     // 0.13 Thrall-Labels
    g_lblMax = OptInt(ini, "Debug", "LabelMax");
    if (g_lblMax < 1 || g_lblMax > 32) g_lblMax = atoi(OptDefault("Debug", "LabelMax"));
    g_lblCross = OptInt(ini, "Debug", "LabelCross") != 0 ? 1 : 0;
    {
        char radius[32];
        OptString(ini, "Debug", "LabelRadius", radius, sizeof(radius));
        float r = static_cast<float>(atof(radius));
        g_lblRadius = (r >= 100.0f && r <= 50000.0f) ? r : static_cast<float>(atof(OptDefault("Debug", "LabelRadius")));
    }
    OptString(ini, "Debug", "LabelMatch", g_lblMatch, sizeof(g_lblMatch));
    // 0.14 debug view
    g_dvViewAtStart = OptInt(ini, "Debug", "View") != 0 ? 1 : 0;
    g_dvTrgAtStart = OptInt(ini, "Debug", "Triggers") != 0 ? 1 : 0;
    for (int i = 0; i < kDvCount; ++i) g_dvAtStart[i] = OptInt(ini, "Debug", kDvLayers[i].key) != 0 ? 1 : 0;
    g_dvMarkupAtStart = OptInt(ini, "Debug", "Markup") != 0 ? 1 : 0;
    g_dvPersist = OptInt(ini, "Debug", "Persist") != 0 ? 1 : 0;
    OptString(ini, "Debug", "ViewNav", g_dvViewNav, sizeof(g_dvViewNav));
    g_dvTrgMax = OptInt(ini, "Debug", "TriggerMax");
    if (g_dvTrgMax < 1 || g_dvTrgMax > 256) g_dvTrgMax = atoi(OptDefault("Debug", "TriggerMax"));
    g_dvLabelMax = OptInt(ini, "Debug", "TriggerLabelMax");
    if (g_dvLabelMax < 0 || g_dvLabelMax > 64) g_dvLabelMax = atoi(OptDefault("Debug", "TriggerLabelMax"));
    {
        char radius[32];
        OptString(ini, "Debug", "TriggerRadius", radius, sizeof(radius));
        float r = static_cast<float>(atof(radius));
        g_dvRadius = (r >= 500.0f && r <= 200000.0f) ? r : static_cast<float>(atof(OptDefault("Debug", "TriggerRadius")));
    }
    OptString(ini, "Debug", "NameMatch", g_dvNameMatch, sizeof(g_dvNameMatch));
    if (!strcmp(g_dvNameMatch, "*")) g_dvNameMatch[0] = 0;
    g_dvNameMax = OptInt(ini, "Debug", "NameMax");
    if (g_dvNameMax < 1 || g_dvNameMax > 64) g_dvNameMax = atoi(OptDefault("Debug", "NameMax"));
    g_dvNameIds = OptInt(ini, "Debug", "NameIds") != 0 ? 1 : 0;
    {
        char nameOpt[32];
        OptString(ini, "Debug", "NameRadius", nameOpt, sizeof(nameOpt));
        float r = static_cast<float>(atof(nameOpt));
        g_dvNameRadius = (r >= 100.0f && r <= 200000.0f) ? r : static_cast<float>(atof(OptDefault("Debug", "NameRadius")));
        OptString(ini, "Debug", "NameScale", nameOpt, sizeof(nameOpt));
        float s = static_cast<float>(atof(nameOpt));
        g_dvNameScale = (s >= 0.5f && s <= 3.0f) ? s : static_cast<float>(atof(OptDefault("Debug", "NameScale")));
        OptString(ini, "Debug", "NameColour", nameOpt, sizeof(nameOpt));
        g_dvNameRgb = (strlen(nameOpt) == 6 && strspn(nameOpt, "0123456789abcdefABCDEF") == 6) ? strtoul(nameOpt, nullptr, 16)
                                                                                                : 0xffffff;
    }
    if (g_dvViewAtStart && g_debugEnabled) {     // dbg.view at start: labels + the ViewNav switches (as NavDraw)
        g_lblAtStart = 1;
        if (!g_navAuto[0]) strncpy_s(g_navAuto, sizeof(g_navAuto), g_dvViewNav, _TRUNCATE);
    }
    InterlockedExchange(&g_cameraChanges, OptInt(ini, "Log", "CameraChanges") ? 1 : 0);
    OptString(ini, "Regress", "List", g_regressStart, sizeof(g_regressStart));
    InterlockedExchange(&g_inputTrace, OptInt(ini, "Log", "InputTrace") ? 1 : 0);   // 0.8.1
    g_musicInLevels = OptInt(ini, "Media", "MusicInLevels") != 0 ? 1 : 0;           // 0.9
    g_musicFade = OptInt(ini, "Media", "MusicFade");
    if (g_musicFade < 0 || g_musicFade > 300) g_musicFade = atoi(OptDefault("Media", "MusicFade"));
    OptString(ini, "Saves", "Folder", g_saveFolderIni, sizeof(g_saveFolderIni));
    // 0.10 [Radial]: HoldButtons / Key also as hex ("0x00C0", "0x78")
    auto number = [&](const char *key) {
        char v[32];
        OptString(ini, "Radial", key, v, sizeof(v));
        return static_cast<int>(strtoul(v, nullptr, 0));
    };
    auto real = [&](const char *key, float lo, float hi) {
        char v[32];
        OptString(ini, "Radial", key, v, sizeof(v));
        float f = static_cast<float>(atof(v));
        return f >= lo && f <= hi ? f : static_cast<float>(atof(OptDefault("Radial", key)));
    };
    g_radEnabled = number("Enabled") != 0 ? 1 : 0;
    g_radHold = static_cast<WORD>(number("HoldButtons"));
    g_radHoldMs = number("HoldMs");
    if (g_radHoldMs < 100 || g_radHoldMs > 3000) g_radHoldMs = atoi(OptDefault("Radial", "HoldMs"));
    g_radKey = number("Key") & 0xff;
    g_radMouse = number("MouseButton");
    if (g_radMouse != 3 && g_radMouse != 4 && g_radMouse != 5) g_radMouse = 0;
    g_radRemember = number("RememberPosition") != 0 ? 1 : 0;
    g_radPassLeft = number("PassLeftStick") != 0 ? 1 : 0;
    g_radSlow = real("SlowMotion", 0.0f, 10.0f);
    g_radDead = real("Deadzone", 0.2f, 0.95f);
    g_radScale = real("Scale", 0.5f, 2.0f);
    g_radSpawn = number("Spawn") != 0 ? 1 : 0;
    {                                        // 0.10.1 Mode / Freeze / QuitSector / TestsLevel
        char v[32];
        OptString(ini, "Radial", "Mode", v, sizeof(v));
        RadTrim(v);
        g_radMode = !_stricmp(v, "wheel") ? kRadModeWheel : kRadModeMenu;   // anything else = the default menu
        OptString(ini, "Radial", "Freeze", v, sizeof(v));
        g_radFreeze = RadFreezeParse(v);
        g_radQuitSector = number("QuitSector") != 0 ? 1 : 0;
        g_radTests = number("TestsLevel") != 0 ? 1 : 0;
        g_freezeSound = g_freezeSoundIni = number("FreezeSound") != 0 ? 1 : 0;      // 0.10.3
        g_freezeClock = g_freezeClockIni = number("FreezeShaderClock") != 0 ? 1 : 0;   // 0.10.4
    }
    {                                        // 0.10.5 [Shot] (Hotkey also as hex, "0x7A")
        auto shot = [&](const char *key) {
            char v[32];
            OptString(ini, "Shot", key, v, sizeof(v));
            return static_cast<int>(strtoul(v, nullptr, 0));
        };
        g_shotEnabled = shot("Enabled") != 0 ? 1 : 0;
        g_shotClean = shot("Clean") != 0 ? 1 : 0;
        g_shotKey = shot("Hotkey") & 0xff;
        g_shotMaxPerMin = shot("MaxPerMinute");
        if (g_shotMaxPerMin < 0 || g_shotMaxPerMin > 120) g_shotMaxPerMin = atoi(OptDefault("Shot", "MaxPerMinute"));
        char folder[MAX_PATH];
        OptString(ini, "Shot", "Folder", folder, sizeof(folder));
        ShotSetFolder(folder);
    }
    {                                        // 0.11 [Flow]
        char v[MAX_PATH];
        auto num = [&](const char *key, int lo, int hi) {
            OptString(ini, "Flow", key, v, sizeof(v));
            int x = static_cast<int>(strtol(v, nullptr, 0));
            return x >= lo && x <= hi ? x : atoi(OptDefault("Flow", key));
        };
        g_flowEnabled = num("Enabled", 0, 1);
        g_flowOverlay = num("Overlay", 0, 1);
        g_flowLines = num("Lines", 1, 3);
        g_flowAuto = num("AutoAdvance", 0, 1);
        g_flowToastMs = num("ToastSeconds", 1, 30) * 1000;
        g_flowPollMs = num("PollMs", 100, 5000);
        OptString(ini, "Flow", "Size", v, sizeof(v));
        float size = static_cast<float>(atof(v));
        g_flowSize = size >= 0.5f && size <= 3.0f ? size : 1.0f;
        OptString(ini, "Flow", "Position", v, sizeof(v));
        RadTrim(v);
        bool top = v[0] == 't' || v[0] == 'T', left = strchr(v, 'l') || strchr(v, 'L');
        g_flowPos = (top ? 0 : 2) + (left ? 0 : 1);   // anything else = the default bottom right
        if (!v[0]) g_flowPos = 3;
        OptString(ini, "Flow", "File", g_flowFile, sizeof(g_flowFile));
        RadTrim(g_flowFile);
        if (!g_flowFile[0]) strncpy_s(g_flowFile, sizeof(g_flowFile), OptDefault("Flow", "File"), _TRUNCATE);
        bool absolute = (g_flowFile[0] && g_flowFile[1] == ':') || g_flowFile[0] == '\\' || g_flowFile[0] == '/';
        _snprintf_s(g_flowPath, sizeof(g_flowPath), _TRUNCATE, "%s%s", absolute ? "" : g_exeDir, g_flowFile);
    }
    // DirectInput code of the key (= scan code, extended keys + 0x80) - KbdReadHook keeps it from the game
    UINT scan = g_radEnabled && g_radKey ? MapVirtualKeyA(static_cast<UINT>(g_radKey), 4 /* MAPVK_VK_TO_VSC_EX */) : 0;
    g_radKeyDik = (scan & 0xff) | ((scan & 0xff00) == 0xe000 ? 0x80 : 0);
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
    trushot::Crc32(0, nullptr, 0);           // 0.10.5: the CRC table once, before any shot worker runs
    Log(1, "shot: [Shot] Enabled %d, Clean %d, Hotkey 0x%02x%s, MaxPerMinute %d, folder %s", g_shotEnabled, g_shotClean,
        g_shotKey, g_shotKey ? " (= claude.mark now)" : " (off)", g_shotMaxPerMin, g_shotDir);
    Log(1, "0.11 flow: [Flow] Enabled %d, file %s, overlay %d (corner %s, size %.2f, %d line(s)), auto advance %d, toast %d s, "
        "poll %d ms%s", g_flowEnabled, g_flowPath, g_flowOverlay, kFlowCorners[g_flowPos], g_flowSize, g_flowLines, g_flowAuto,
        g_flowToastMs / 1000, g_flowPollMs, g_flowEnabled ? " - the worker reads the file" : " - off");
    if (g_shotKey && (g_shotKey == g_toggleKey || (g_radEnabled && g_shotKey == g_radKey)))
        Log(0, "shot: [Shot] Hotkey 0x%02x is also [Menu] ToggleKey / [Radial] Key - both act on that key", g_shotKey);
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
    // 0.10.4: the state save is the game's store or TruDlc2Player 0.5's [Costume] TuMapping detour there (jmp rel32 out
    // of tru.exe + 8 nops; it still stores +0x20c, mapped 857 -> 11 as the TU's save)
    DWORD saveJmp = 0;
    bool saveOk = HexBytesAt(kSaveCostume, kSaveCostumeBytes);
    if (!saveOk && HexBytesAt(kSaveCostume, "e9") && HexBytesAt(kSaveCostume + 5, "9090909090909090") &&
        ReadDword(kSaveCostume + 1, &saveJmp)) {
        DWORD to = kSaveCostume + 5 + saveJmp;
        saveOk = to < kImageBase || to >= 0x01000000;
        if (saveOk) Log(1, "costume: state save 0x%08lx is a detour to 0x%08lx (TruDlc2Player 0.5 TuMapping) - accepted",
                        kSaveCostume, to);
    }
    g_costumeOk = HexBytesAt(kLevelLoadChoice, kLevelLoadChoiceBytes) && HexBytesAt(kResetCostume, kResetCostumeBytes) &&
                  saveOk && HexBytesAt(kNameLookup, kNameLookupBytes) &&
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
    // 0.8: cheats (each row its own check), camera log (manager process -> chooser, mode fields), regression lists
    CheatsCheck();
    NavCheck();                               // 0.12 Debug-Zeichnung: NavPower switches (precheck_012.txt)
    LabelCheck();                             // 0.13 Thrall-Labels (precheck_013.txt)
    DebugViewCheck();                         // 0.14 debug view (precheck_014.txt)
    g_camLogOk = HexBytesAt(0x005f3e0c, "b9f004e800 e85afeffff") && HexBytesAt(0x005f3d12, "8bce d91c24 e8c442ffff") &&
                 HexBytesAt(0x005e7feb, "8bf1") && HexBytesAt(0x005e8041, "8b4658 83f801") &&
                 HexBytesAt(0x005e80b9, "c7465834000000") && HexBytesAt(0x005e80da, "8b7e58 397e54 7465") &&
                 HexBytesAt(0x005e810b, "8b4e58 d95e5c 5f 894e54") && HexBytesAt(0x005f3cb0, "8d8620010000 394644");
    if (!g_camLogOk) Log(0, "0.8 camera log: camera manager / mode chooser code (0x5f3e0c, 0x5e7fe0) does not match - "
                            "[Log] CameraChanges off");
    RegStart();
    Log(1, "0.8: camera log %d ([Log] CameraChanges %ld; mode = manager 0x%08lx +0x58 / +0x54), regression lists %s "
           "(dlc1 %d rows, dlc2 %d rows, page shows %s), results %s, session %s", g_camLogOk ? 1 : 0, g_cameraChanges,
        kCameraManager, g_asiDir, g_regCount[0], g_regCount[1], g_regSel == 2 ? "all" : kRegNames[g_regSel],
        g_regResultsPath, g_regSession);
    {
        int shortcuts = 0;
        for (int l = 0; l < kRegLists; ++l)
            for (int i = 0; i < g_regCount[l]; ++i) if (g_regShortcut[l][i][0]) ++shortcuts;
        Log(1, "0.8.1: input trace %ld ([Log] InputTrace; lines at LogLevel 2, now %d), game.quit window %lu s + hold "
               "1 s, request slot claimed once, regression shortcuts %d, player.unstuck ring %d spots",
            g_inputTrace, g_logLevel, kQuitWindowMs / 1000, shortcuts, kSafeMax);
    }
    // 0.10.2: the game's cinematic test (read by the safe-ground sampler; same bytes as TruShadowPower's kCinematicHex)
    g_cineOk = HexBytesAt(0x00453f00, "a1c0f1e700 85c0 7418 80b8dd00000000 740c 83782cff 7406 b801000000 c3 33c0 c3 32c0 c3");
    if (!g_cineOk) Log(0, "0.10.2: cinematic test tru+0x53f00 does not match - the safe-ground sampler skips cinematics "
                          "only by main state");
    Log(1, "0.10.2: cheat.godfull = no-damage bit [0x%08lx] & 0x%05lx per frame (no flight; check %d), safe ground: "
           "%d samples x %d frames, chord %.0f, slope %.1f + %.0f, cinematic test %d, marks keep the yaw",
        kPlayerModeFlags, kNoDamageBit, g_godFullOk ? 1 : 0, kSafeWindow, kSafeEvery, kSafeChord, kSafeSlope, kSafeStep,
        g_cineOk ? 1 : 0);
    DevRead();
    // 0.9: music (engine srmusic, each address checked), media list, save folder (file system only)
    g_musicOk = MusicCheck();
    MediaLoad();
    g_musicVarsOk = DevRowFor(0x00e7f098, 0x10000000) ? 1 : 0;
    g_monsterVarsOk = DevRowFor(0x00e7f0a0, 0x01000000) ? 1 : 0;
    EnterCriticalSection(&g_saveLock);
    SaveFolderInit();
    LeaveCriticalSection(&g_saveLock);
    Log(1, "0.9 music %d (%s); MusicInLevels %d, fade %d frames; media list %s: %d rows; dev rows: music vars %d, "
           "monster music vars %d", g_musicOk ? 1 : 0, g_musicCheck, g_musicInLevels, g_musicFade, g_mediaPath,
        g_mediaCount, g_musicVarsOk, g_monsterVarsOk);
    Log(1, "0.9 saves: folder %s (%s), backups %s", g_saveFolderU8[0] ? g_saveFolderU8 : "-", g_saveFolderHow,
        g_saveRootU8);
    // 0.10: radial menu (after DevRead: entries may name dev.<slug> rows) and the stage R2 spawn path
    g_spawnOk = SpawnCheck();
    _snprintf_s(g_radFilePath, sizeof(g_radFilePath), _TRUNCATE, "%sTruMenu.radial.txt", g_exeDir);
    _snprintf_s(g_radTourPath, sizeof(g_radTourPath), _TRUNCATE, "%sTruMenu.tour.txt", g_exeDir);   // 0.10.1
    if (g_radEnabled) {
        EnterCriticalSection(&g_radLock);
        RadialLoad();
        LeaveCriticalSection(&g_radLock);
    } else {
        strncpy_s(g_radFileState, sizeof(g_radFileState), "not read ([Radial] Enabled=0)", _TRUNCATE);
    }
    Log(1, "0.10 radial: enabled %d, hold buttons 0x%04x %d ms (%s), key 0x%02x (DirectInput 0x%02lx, %s), mouse button %d, "
           "remember %d, pass left stick %d, slow motion %.2f, deadzone %.2f, scale %.2f; spawn (R2) %s, [Radial] Spawn=%d",
        g_radEnabled, g_radHold, g_radHoldMs,
        g_radHold && g_radHold == g_toggleButtons ? "= the menu combo: short press = menu at the release" : "own combo",
        g_radKey, g_radKeyDik, g_kbdOk ? "kept from the game" : "keyboard hook off - the game may see it", g_radMouse,
        g_radRemember, g_radPassLeft, g_radSlow, g_radDead, g_radScale, g_spawnOk ? "code ok" : g_spawnWhy, g_radSpawn);
    if (!g_spawnOk) Log(0, "0.10 instance.spawn disabled - %s", g_spawnWhy);
    Log(1, "0.10.1 radial: mode %s (%s), freeze %s (read again at every open), quit sector %d (%s), tests level %d (tour "
           "%s), pause code %s, control code %s", g_radMode == kRadModeMenu ? "menu" : "wheel",
        g_radMode == kRadModeMenu ? "stays open, A confirms, B back, L3 + R3 / key again closes, pad + keys neutral"
                                  : "0.10 hold and release",
        g_radFreeze == kRadFreezeWorld ? "world" : g_radFreeze == kRadFreezePlayer ? "player" : "0", g_radQuitSector,
        g_radQuitItem >= 0 ? "built in" : "not built in (Mode=wheel / QuitSector=0)", g_radTests, g_radTourState,
        g_pauseOk ? "ok" : "NO", g_controlOk ? "ok" : "NO");
    // 0.10.3 (F7): the pause menu's sound pause pair (only with the pause bit check: the want reads that bit)
    g_soundOk = SoundCheck() && g_pauseOk && g_playerOk;
    Log(1, "0.10.3 sound with the freeze: code %s (0x%08lx / 0x%08lx, flag 0x%08lx, pause menu calls), [Radial] "
           "FreezeSound %d, [Menu] PauseSound %d (items time.freezesound / time.pausesound, state time.sound)",
        g_soundOk ? "ok" : "NOT verified - off", kSoundPause, kSoundResume, kSoundPaused, g_freezeSound, g_pauseSound);
    // 0.10.4 (F7, light shaft): the pause menu's shader clock hold (the want reads the pause bit as the sound's)
    g_clockOk = ClockCheck() && g_pauseOk && g_playerOk;
    Log(1, "0.10.4 shader clock with the freeze: code %s (hold 0x%08lx -> [0x%08lx], reader 0x005bf841, accumulator "
           "RenderDevice +0xfa4c 0x00506fb8, TimeVector upload 0x005096c7, pause menu calls), [Radial] FreezeShaderClock "
           "%d (item time.freezeclock, state time.clock)", g_clockOk ? "ok" : "NOT verified - off", kRenderHoldSet,
        kRenderHold, g_freezeClock);
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
        InitializeCriticalSection(&g_edgeLock);       // 0.8.1 input trace
        InitializeCriticalSection(&g_safeLock);       // 0.8.1 player.unstuck
        InitializeCriticalSection(&g_scLock);         // 0.8.1 regression shortcuts
        InitializeCriticalSection(&g_saveLock);       // 0.9 Saves page
        InitializeCriticalSection(&g_radLock);        // 0.10 radial menu
        InitializeCriticalSection(&g_shotLock);       // 0.10.5 shots / Claude marks
        InitializeCriticalSection(&g_flowLock);       // 0.11 Ablauf
        InitializeCriticalSection(&g_flowEvLock);
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

// 0.10.5: other plugins (TruShadowHud, TruTrace, ...) request a screenshot of the next frame. <name> as shot.save
// (sanitised to A-Z a-z 0-9 _ - ., at most 40; NULL / "" = "-"), clean or not per [Shot] Clean; never waits (also safe
// from the render thread). 1 = queued (the planned file name in a TruMenu.log line), 0 = refused (reason in the log).
extern "C" __declspec(dllexport) int __cdecl TruMenuShot(const char *name) { return ShotExport(name); }

// 0.10.5: a Claude mark as the ring level Claude / claude.mark <kind> (NULL / "" = now): the TruMenu.log line
// "claude.mark <kind>: ... src=TruMenuMark" + a clean shot; never waits. 1 = marked, 0 = refused (MaxPerMinute).
extern "C" __declspec(dllexport) int __cdecl TruMenuMark(const char *kind) { return MarkExport(kind); }
