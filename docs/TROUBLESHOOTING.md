# Troubleshooting (players)

## Lock the game to 60 fps

Tomb Raider: Underworld ties physics and camera to the frame rate (variable time step, one physics step per frame). Above 60 fps
boxes, ragdolls and physics puzzles can break, in the base game and even more in the DLC. Lock the game to **60 fps** with one of:

- in-game V-Sync on a 60 Hz display;
- the frame limiter of your GPU driver (NVIDIA Control Panel → *Max Frame Rate*, AMD *Frame Rate Target Control*) or RTSS;
- [dxwrapper](https://github.com/elishacloud/dxwrapper) with `LimitPerFrameFPS = 60`;
- dgVoodoo2 (see below), which also has an `FPSLimit` option;
- DXVK (see below) already caps this game at 60 fps by itself: its built-in profile for `tru.exe` sets `d3d9.maxFrameRate = -60`.

V-Sync alone is not enough on a 120 / 144 Hz display. The GOG version of the game ships a 60 fps cap since March 2025; the
Steam version does not. A player-side plugin with a built-in 60 fps cap (`TruQoL`) is in progress on the `windows` branch.

## "A problem has occurred with your display driver"

**Fork finding (30 Oct 2026, `windows` branch): confirmed on a real GPU with B138 and fixed offline.** The box comes
from one failing `IDirect3DDevice9::CreatePixelShader` (`D3DERR_INVALIDCALL`) when the DLC 1 level draws: 272 of the
396 port-generated pixel shaders read two different constant registers in one instruction (Xbox allows it, Direct3D 9
shader model 3 does not) - a third form, besides the two below. `tools/shader_const_fix.py` rewrites them (24 B138
files); with them DLC 1 starts on that PC. Details: [WINDOWS_REBUILD.md](WINDOWS_REBUILD.md), finding 43.

**Fork check (8 Nov 2026, NVIDIA):** the native test v3 on the installed `windows` tree refused no port
shader (2919 shaders, negative controls refused as they should be). The newer translations still contain 272 pixel
shaders with the `cmp ... -|c221| ...` form that the AMD driver refused on 20 Oct; NVIDIA accepts it, so AMD stays
unconfirmed. A rewrite of that form is in progress; until it is released, AMD players should use DXVK (below).

**What happened (20-21 Oct 2026).** A player with an AMD RX 9070 XT (Windows 11, Windows' own Direct3D 9) got this box. The native test showed why: the driver refused pixel shaders that use two forms the original PC game never uses.

- `cmp` with an abs/-abs constant source, for example `cmp r0, -|c221|, ...`;
- `sincos` whose destination is also its source.

**Status.** B133 fixed the 274 shaders of B132. The converter brought the forms back from B147, and B147-B268 contain 240 of them (DLC1 and DLC2). In **B269** they are rewritten (bit-equivalent in our shader VM), the converter is fixed, and a build gate blocks them. This is verified offline only, so please run the test below once on B269 or later.

### Workaround: DXVK (or dgVoodoo2)

Both compile the shaders themselves and do not go through Windows' D3D9 validation.

- **DXVK**: from <https://github.com/doitsujin/dxvk/releases> copy `x32\d3d9.dll` next to `tru.exe`. To undo, delete it.
- **dgVoodoo2**: from <http://dege.fw.hu/> copy `MS\x86\D3D9.dll` next to `tru.exe`, plus [`tools/native_test/dgvoodoo/dgVoodoo.conf`](../tools/native_test/dgvoodoo/dgVoodoo.conf).

### Help us: run the native test v3 (2 minutes, changes nothing)

1. Download `trudlcport-native-test-v3.zip` from the latest release (or use [`tools/native_test`](../tools/native_test)) and unzip it anywhere.
2. Close the game and **move DXVK/dgVoodoo away** for the test.
3. Double-click `RUN_TEST.bat` and paste the game folder.

It reads the shaders of your installed `mods\` and creates on your GPU, with the game's device flags:

- every shader;
- every vertex layout and texture format;
- the render-target and depth formats;
- the state blocks.

It works without the game or the port too, with synthetic probes only.

Send us (GitHub issue) **`trudlcport_native_result.zip`**. `SUMMARY.txt` inside it is a short version you can paste. The zip contains:

- GPU, driver version and date, Windows build, display mode;
- every rejected shader with its lib id, source DRM, size, MD5, HRESULT and the suspicious instruction.

Also tell us **when** the box appears: at start-up, in the menu, or in the DLC (where).

If the test reports 0 rejected port shaders and the box still appears, run `RUN_DRAW_TEST.bat`.

- It also draws with every shader and can reset the screen once.
- If the driver resets, `native_progress.txt` names the shader that was being drawn.

## Known problems of the original PC game

Collected from player reports (PCGamingWiki, Steam discussions and guides, Tomb Raider Chronicles; 8 Nov 2026). They are
problems of Tomb Raider: Underworld itself, not of the DLC port. Most need no tool; the registry values below can be set
with `scripts/windows/Set-TruDisplay.ps1` (it saves a backup first; add `-Check` to see the change without writing it).

| Problem | What helps |
|---|---|
| Crash at start-up on CPUs with more than 31 threads | Steam launch option `cmd /c start "" /affinity FFFF %command%` (see `scripts/windows/README.md`) |
| White screen or hang in the first cutscene / at the end of the tutorial | registry `DontDeferShaderCreation` = 0 and `DisableDynamicTextures` = 0 (`Set-TruDisplay.ps1 -StutterFix`); Steam overlay off; reports differ, one player only needed the affinity option |
| Stutter, slow loading, frame rate dropping after 10-15 minutes | the same two registry values; some players also set `EnableWaterFX` = 0 |
| Crash with DEP (Data Execution Prevention) | add `tru.exe` as a DEP exception in Windows (the GOG version turns DEP off at run time) |
| Steam overlay crashes or does not show | turn the Steam overlay off for this game |
| Controller does nothing or the camera stutters | turn **Steam Input** off for this game (Properties → Controller) |
| Crackling sound | set the audio output to 96 kHz or less |
| Saving fails or crashes | allow the game to write to its save folder in your security software |
| Only 4:3 / 16:9 / 16:10 offered | registry `AspectRatio` = width / height x 10000 (`Set-TruDisplay.ps1 -AspectRatio Auto` or `-AspectRatio 21:9`); the in-game options overwrite it again; widths of 4096 pixels or more are reported not to start |
| Depth of field missing | it is in the PC game but off: registry `EnableDepthOfField` = 1 (`Set-TruDisplay.ps1 -DepthOfField On`); a missing value counts as off |
| Default key Q is both "centre camera" and the grapple | assign one of them to another key in the options |
| Linux / Steam Deck (Proton) | reported to need at most 4 CPU cores and Steam Input off |

---

## In italiano (breve)

- **Blocca il gioco a 60 fps** (V-Sync a 60 Hz, limitatore del driver NVIDIA/AMD o RTSS, dxwrapper `LimitPerFrameFPS = 60`):
  sopra i 60 fps fisica e camera si rompono.
- **"A problem has occurred with your display driver"**: in B269 sono corrette le forme di shader che il D3D9 di Windows rifiuta su AMD
  (verificato solo offline). Rimedio immediato: DXVK (`x32\d3d9.dll` accanto a `tru.exe`) o dgVoodoo2. Per aiutarci: a gioco chiuso
  lancia `RUN_TEST.bat` da `trudlcport-native-test-v3.zip` e mandaci `trudlcport_native_result.zip`.
