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

Two pack11 audio streams have no entry in `docs/data/B270_acqua.kit_manifest.json`, so the B270 kit probably does not
install them (not checked against the kit itself). Both names are hash-checked: `tools/name_hash_check.py <name>`.

| Hash | Name (under `xenon-w\audio\streams\`) | Where the name comes from |
|---|---|---|
| `0xc986dd53` | `event_triggered\reveals\dlc2_machine_room_second_bridge_reveal.mul` | upstream's own `tools/dlc_names3.py` (round 3) finds it; the pipeline step that writes `dlc_names.txt` runs round 1 only |
| `0xc2492c8b` | `music\l7_valhalla_2\entering_hellheim(1).mul` | strings of the 2007 prototype DLC data |

Still unnamed: two `RAW!` images, `0x753ecefd` (983 168 bytes, in pack10 and pack11) and `0xae29666a` (3 768 448 bytes,
pack11).
