## 2. Converter fault families fixed as pipeline steps

Each family was found through a crash dump or a test in game, proven on the Xbox / PC base pairs before it became a
rule, and has a check that reports affected files. They come from the shared converter, so other builds of the DLC may
show them too. Numbers: [WINDOWS_REBUILD.md](WINDOWS_REBUILD.md).

| Fault | Effect in game | Fix / check | Finding |
|---|---|---|---|
| SoundPlex sequence nodes (type 10): repeat byte at data +0xc swapped as a u32 (Xbox `01 00 00 00`, PC `00 00 00 01`) | repeat 0 = endless: doppelganger vocals loop until death | `tools/soundplex_sequence_fix.py scan <mods>` (step `seqrepeat` in `tools/dlc_struct_fixes.py`) | 49 |
| Object-data texture group counts left raw (`0x04000000` instead of 4) | the engine masks megabytes with 0x1fff, crash at tru+0x12b4a0 (`dlc_fx_cine_thrall_death` from pack11, `dlc_fx_goo_machine_column_core`) | `tools/objdata_texlist_check.py`, `tools/objdata_fx_fix.py` (steps `objtex` / `objrec`) | 47 |
| Particle record byte / u16 fields swapped as u32 | crash tru+0x42e62 (goo drips), wrong effects | `tools/objdata_fx_fix.py` (step `objrec`) | 47 |
| DLC 2 thrall base script re-authored under the main-game id 12433 with another instance layout | crash when thralls are unloaded | `tools/script_clash_fix.py`, scan `tools/script_layout_clash.py` | 45, 46 |
| Player breath-sound section ids as two u16 instead of one translated u32 | invalid ids (`0x04890000`, `0x68f40000`) | step `objid` in `tools/dlc_struct_fixes.py` | 48 |
| State-VM code words, event / effect-node ids, state-chart id parameters, anim / object event lists | heap corruption after the wall run, crashes near thralls | `tools/converter_faults_fix.py` (`statevm`, `idword`, `fxnode`, `chartid`, `animlist`, `objevent`) | 44 |
| Cloth iteration count as two s16 halves (4 -> 262 144 passes per frame) | DLC 2 intro in slow motion | step `cloth` in `tools/dlc_fixes_build.py` | 43 |
| UI timeline target paths and UI text string ids converted as Symbols | crash after the DLC 2 intro, empty hint box | `tools/script_u16array_fix.py`, `tools/script_uitext_fix.py` (steps `uipath` / `uitext`) | 43 |
| Pixel shaders reading two different constant registers in one instruction (272 in B138) | "A problem has occurred with your display driver" on a real GPU | `tools/shader_const_fix.py` | 43 |
| `.mul` IMA encoding that ignores the decoder's step cap (8191) | crackling sibilants, clicks on loud transients | game-model encoder in `tools/mul_audio_nch.py`, measure with `tools/listen_game_model.py` | 18 |

## 3. Names not listed in the B270 manifest

Four DLC records have no entry in `docs/data/B270_acqua.kit_manifest.json` (nor in B269 / B138, searched by source hash
and target path with `tools/kit_manifest_names.py`), so the kits probably do not install them. Every name is
hash-checked (`tools/name_hash_check.py <name>`) and now listed in `docs/data/dlc_names_extra.txt`, which
`tools/dlc_names.py` reads (it refuses a line whose hash does not match).

| Hash | Name | What it is / where the name comes from |
|---|---|---|
| `0x753ecefd` (pack10 and pack11, identical) | `xenon-w\image\loading_bg_dlc1.raw` | DLC 1 loading-screen background, 640x360 A8R8G8B8 (= `dlc_level1_preview` without the white frame); named by the title-update loading-screen script (generalbank script 8:6) next to the base `loading_bg_*` |
| `0xae29666a` (pack11) | `xenon-w\image\loading_bg_dlc2.raw` | DLC 2 loading-screen background, 1280x720, same script |
| `0xc986dd53` (pack11) | `xenon-w\audio\streams\event_triggered\reveals\dlc2_machine_room_second_bridge_reveal.mul` | named in `dlc2_goo_room` (script 8:26727); upstream's own `tools/dlc_names3.py` (round 3) finds it |
| `0xc2492c8b` (pack11) | `xenon-w\audio\streams\music\l7_valhalla_2\entering_hellheim(1).mul` | named in `dlc2_goo_room` (script 8:26727); round 3 misses it (the `(1)` does not fit its pattern) |
