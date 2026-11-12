# TruMercLang.asi - the mercenaries speak another language (fun option)

Version 0.1.1 (2026-11-12, `work\asi\i_1211\TruMercLang`: dated log lines only, see below; 0.1 of 2026-11-06 in
`work\asi\merclang01`). **Default off** (`TruMercLang.ini` `Enabled=0`). Built, byte checks run offline against the
installed `tru.exe`; not yet played.

**0.1.1 (Q107):** every line of `TruMercLang.log` starts with `YYYY-MM-DD HH:MM:SS.mmm`, and each game process writes
one header line `=== <date time> TruMercLang 0.1.1 session start (pid n) ===` before its first line (the log is
written with `Enabled=0` too). Install: `scripts\windows\Set-TruMercLang.ps1 -Install -SourceDir work\asi\i_1211\TruMercLang`.

| # | TO TEST 0.1.1 | expected |
|---|---|---|
| 1 | start the game once with 0.1.1 installed (`Enabled=0` is enough), read `TruMercLang.log` from its last `session start` line on | header and `---- ... loaded` line name 0.1.1; every newer line starts with the date (`2026-11-..`); the time matches the other plugin logs of the same start |

With `Enabled=1` and `Language=es` the mercenaries on the ship levels (Mediterranean end `l1_ship_*`, Andaman Sea
`l6_ship_*`) shout their barks in Spanish while Lara, the story, the subtitles and the menus keep the game language.
Any of `en fr de it es` works. No audio file is shipped: the PC `bigfile.000` already holds every merc bark in all five
languages (finding `docs/Befund-Tonspuren-Soeldner-0611.md` in the workspace, section B).

## How it works

* The merc barks are `audio\streams\vo\enemy\merc\b_mNN_<category>_<g|s>_NN.mul` - 669 names, 490 of them with one
  record per language (same path, same hash, spec word `ffffffe1` EN, `ffffe002` FR, `ffffe004` DE, `ffffe008` IT,
  `ffffe010` ES), 179 language-neutral (`ffffffff`: voice m11, all `gat` pain sounds, `cbr` / `evg` 06-10 of m05 / m06 /
  m07 / m09).
* `tru.exe` picks the record per file in `ArchiveFileSystem::FindEntry` (0x4726e0, thiscall, argument = path):
  binary search of the path hash, then the first record with `(spec & mask) == mask`, mask = `this+8` =
  `1 << language` (SetLanguage 0x49a900 -> 0x54f2e0 -> SetSpecialisationMask 0x472990). Barks are looked up on every
  play.
* The plugin detours FindEntry (5-byte jmp at its entry, trampoline with the relocated 7-byte prologue). For a path
  that contains `PathFilter` it runs the normal search, then searches again with a **copy** of the 0x20-byte
  file-system object whose mask field holds `1 << Language`. If that finds a record, the plugin returns it, else the
  normal one. The real object is never written (FindEntry runs on loader threads too); FindEntry reads only `+0x08`,
  `+0x14`, `+0x18`, `+0x1c` of `this`, and the returned record points into the real record table, so the four callers
  (RequestRead, FileExists, GetFileSize, OpenFile) all get the same record for the same path.
* Paths outside the filter, lookups that find nothing in an archive (e.g. `patch.000`) and a game language equal to
  `Language` go through unchanged.

## Checks (all or nothing)

Before patching, the plugin compares 21 byte sequences and a FNV-1a hash of the whole FindEntry body
(0x4726e0-0x472872, `0x39269461`): the prologue, the three mask reads and the `+0x14 / +0x18 / +0x1c` reads,
Set/GetSpecialisationMask, the ArchiveFileSystem vtable, the four `call FindEntry` sites, `mask = 1 << language` in
SetLanguage, the installer language ids French 1 ... Spanish 4, GetFS. One mismatch = nothing hooked, every failed
check is logged. Offline: `tools/pe_bytes_check.py` with the same list, `tools/merclang_check.py` for the records.

## Options (`TruMercLang.ini`, section `[MercLang]`)

| Key | Default | Meaning |
|---|---|---|
| `Enabled` | 0 | 1 = hook in at game start; 0 = load, hook nothing |
| `Language` | es | `en` `fr` `de` `it` `es` (the game's language ids 0-4) or `off` |
| `PathFilter` | `\vo\enemy\merc\` | only paths containing this (case-insensitive, `/` or `\`) are redirected |
| `LiveReload` | 0 | 1 = read `Enabled` / `Language` again when the .ini changes while the game runs (once a second, from the next bark on). The hook itself goes in only when `Enabled=1` at start |
| `LogLevel` | 1 | 0 errors, 1 info, 2 + unchanged (language-neutral) paths, 3 + every byte check |

## Log (`TruMercLang.log` next to the .asi)

```
---- TruMercLang 0.1 (merc barks in another language) loaded (enabled 1, language es = mask 0x10, filter \vo\enemy\merc\, live reload 0, log level 1)
mods\: 552 files, none under the filter (every merc bark comes from the archive)
checks: 22 of 22 ok (FindEntry body fnv 0x39269461, mask at this+8, 4 callers, vtable, language ids)
hook installed: FindEntry 0x004726e0 -> 0x........ (trampoline 0x........)
game file system 0x........, vtable 0x........ (...); ModLoader.asi loaded
redirect vo\enemy\merc\b_m02_inv_g_03.mul: de (spec ffffe004) -> es (spec ffffe010)
last 30 s: 12 lookups redirected, 3 unchanged (language-neutral), 0 fallback, 0 already in the game language; 9 distinct paths so far
```

The redirect lines (once per distinct path and language) and the 30 s count lines are written by a helper thread,
never from inside the hook. While no bark plays, no count line is written.

## Limits

* **mods\ / ModLoader**: ModLoader's `HookFileSystem` sits above the game's file system and answers files that exist
  in `mods\` itself, so FindEntry never sees them. No merc bark is in `mods\` today; the plugin counts files under the
  filter at start (warning with the first 5 names) and logs which file-system object the game uses. It does not work
  around it.
* Language-neutral barks (voice m11, pain sounds) have one recording only and stay as they are.
* `LiveReload`: a switch exactly between a bark's size query and its open could mix two languages for that one bark
  (both lookups run separately). Change the language between fights, not mid-bark.
* No other plugin hooks 0x4726e0 (TruGuard not checked, by rule); one that patched it would make the checks fail.

## Build and install

```
scripts\windows\Build-TruAsi.ps1 -Name TruMercLang -OutDir <repo>\work\asi\merclang01
scripts\windows\Set-TruMercLang.ps1 -Install -SourceDir <repo>\work\asi\merclang01     (game closed)
scripts\windows\Set-TruMercLang.ps1 -Remove
```

Then set `Enabled=1` in `TruMercLang.ini` next to `tru.exe`.
