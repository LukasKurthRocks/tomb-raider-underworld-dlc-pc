# TruShadowPower.asi

A small ASI plugin for the **PC** `tru.exe` (Steam, Tomb Raider: Underworld) that brings back the **slow motion of the
DLC 2 shadow power** (*Lara's Shadow*). On the Xbox the title update gives Lara the Doppelgänger's power: while LB or RB
is held the world runs at 0.3 and Lara at 1.2 of normal speed. The PC exe never received that code, but it has the
engine's time-scale system the title update drives. This plugin does what the title update does for the slow motion:
on a press / release of the shadow buttons it calls the engine's own setters with the Xbox values.

Background, measurements and the debugger prototype it is based on: [docs/WINDOWS_REBUILD.md](../../../docs/WINDOWS_REBUILD.md)
finding 43 ("Shadow-power slow motion reproduced on PC", test 39b) and [docs/DLC2.md](../../../docs/DLC2.md).

**Status: step 3.1 of re-implementing the title update - slow motion only.** Not covered: the shadow meter (drain,
refill, falling off a rock vein), the blur / bloom look, rock veins, the shadow jump and the combat moves. It is active
in **every level** (no DLC 2 check yet) - LB also sprints on PC, so for tests outside DLC 2 set `Enabled=0` or remove it.

## How it works

| Address (tru.exe, image base 0x400000) | What |
|---|---|
| `0x00484b82` `ff 15 8c 2b a0 00` | the per-frame pad poll: `call dword ptr [0x00a02b8c]` (XInputGetState through a stored pointer) |
| `0x00a02b8c` | that pointer - the game fills it at start; the plugin swaps it for a wrapper |
| `0x00776030` | `SetWorldTimeScale(float target, float seconds)`, `__stdcall`, `ret 8`, world ramp `0x8abeb4` |
| `0x00776090` | `SetPlayerTimeScale(float target, float seconds)`, `__stdcall`, `ret 8`, player ramp `0x8abe94` |

The wrapper calls the original XInputGetState and, on the edge of "shadow button held" (any pad), calls
`SetWorldTimeScale(0.3, 0.033)` + `SetPlayerTimeScale(1.2, 0.033)` on press and both with 1.0 on release - on the game
thread, inside its pad poll. At load the plugin checks the image base and the bytes at all addresses above; on any
mismatch (another exe build) it hooks nothing and logs why. A helper thread waits for the game to fill the pointer and
re-hooks if the game ever writes the original back.

The installed game ships the **Ultimate ASI Loader** as `binkw32.dll`; it loads every `*.asi` next to `tru.exe` (the same
way it loads `ModLoader.asi`), so no further exe change is needed.

## Options (`TruShadowPower.ini` next to the `.asi`, optional)

| Key | Default | Meaning |
|---|---|---|
| `Enabled` | 1 | 0 = load but hook nothing |
| `LogLevel` | 1 | 0 errors, 1 info, 2 every press / release, 3 debug - `TruShadowPower.log` next to `tru.exe` |
| `Buttons` | 768 | XInput mask: 256 LB, 512 RB, 768 either (Xbox) |
| `WorldScale` / `PlayerScale` / `RampSeconds` | 0.3 / 1.2 / 0.033 | title update values |

## Build, install, remove (Windows)

```powershell
.\scripts\windows\Build-TruAsi.ps1 -Verbose              # Visual Studio 2022 x86 toolchain -> work\asi\TruShadowPower.asi
.\scripts\windows\Set-TruShadowPower.ps1 -Install        # copies .asi + .ini next to tru.exe (game closed)
.\scripts\windows\Set-TruShadowPower.ps1 -Remove         # removes them again (only if they are this build)
```

No external libraries; static runtime (`/MT`), imports only `KERNEL32.dll`. License: MIT, as the repository.
