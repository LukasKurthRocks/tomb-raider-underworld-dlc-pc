# TRU-DLC – Xbox-360-DLCs von Tomb Raider Underworld auf PC

Ziel: *Beneath the Ashes* (DLC1) und später *Lara's Shadow* (DLC2) in der Steam-PC-Version spielen,
mit dem Fan-Port [trudlcport](https://github.com/andrearicci93/trudlcport) (andrearicci93).

## Ordner

| Pfad | Inhalt |
|---|---|
| `input\xbox-dlc\` | eigene Xbox-360-DLC-Daten |
| `input\xbox-game\` | eigenes Xbox-360-Hauptspiel (`layer1.000/.001`, `layer2.000/.001`, `default.xex`) + Title Update (`TitleUpdate.000`, `default.xexp`) |
| `input\ModLoader-v1.2.zip` | [TombRaiderModding/ModLoader](https://github.com/TombRaiderModding/ModLoader/releases) v1.2 (20.07.2024) |
| `release\B138\` | `install_dlc.py` + `trudlcport-kit-B138.zip` (Release 21.10.2026) |
| `trudlcport\` | Klon von trudlcport, Branch `windows` (eigenes Git-Repo, siehe „Upstream-Klon“) |
| `bin\` | Werkzeuge (Python-venv, Ghidra, JDK, Xenia, Yura, ffmpeg) – `Get-Tools.ps1` |
| `data\` | Verknüpfungen auf Spiel, Xbox-Daten und Klon – siehe „Entwicklungsumgebung“ |
| `backup\` | Sicherungen (Original-`tru.exe`/`binkw32.dll`, ersetzte Mod-Dateien, Registry-Exporte) |
| `logs\` | Protokolle aller Skriptläufe |
| `Referenzen\` | Vergleichsbilder (Xbox/Xenia, PC) und Kostüm-Vorschauen – `Referenzen\README.md` |

Alle Ordner außer den Skripten, `docs\`, `Referenzen\` und den Markdown-Dateien sind in `.gitignore`.

## Skripte (PowerShell, Verbose/Debug/Trace + Protokoll in `logs\`)

| Skript | Zweck |
|---|---|
| `Install-TruDlc.ps1` | B138-Kit + ModLoader installieren (`-Check` Trockenlauf, `-Restore`), Spielordner über Steam |
| `Install-TruModFile.ps1` | eine Datei in `mods\` austauschen (mit MD5-benannter Sicherung) oder zurücksetzen |
| `Set-TruDisplay.ps1` | Fenstermodus/Vollbild und Sprache (Registry, mit Sicherung) |
| `Get-Tools.ps1` | Werkzeuge nach `bin\` laden, SHA-256 prüfen |
| `Invoke-TruPipeline.ps1` | trudlcport-Pipeline Schritt für Schritt (`-Step Index/Cache/Ids/Learn/Tables/Prep/Convert`, `-FromTool`), mit Fortschritt |

## Doku im Klon (englisch)

| Datei | Inhalt |
|---|---|
| `trudlcport\docs\WINDOWS_REBUILD.md` | Nachbau der Pipeline unter Windows: Reihenfolge, Lücken/Funde, Laufprotokoll, Vergleich mit B138 |
| `trudlcport\docs\DLC_MENU.md` | DLC-Missionsmenü: Ursache und Fix (Titel über der Beschreibung) |
| `trudlcport\docs\DLC2.md` | *Lara's Shadow*: Xbox-Referenz, Shadow-Meter-Mechanik |
| `trudlcport\docs\COSTUMES.md` | Kostüm-Pakete: welches Paket welche Kostüme enthält |

## Stand Pipeline-Nachbau (27.10.2026)

Stufe 0 (Index, Paare, Id-Tabellen, gelernte Regeln) und Stufe 1 (Grundumwandlung) laufen unter Windows; dafür
fehlende Bausteine wurden nachgebaut (`dlc_drms_build.py`, `objlists_extract.py`, `pc_vers_build.py`). Vergleich
mit B138 für DLC 1: Objektlisten byte-identisch; Abschnitte vom Typ 2/11 zu 100 %, Texturen 99,7 %, DTP 97,7 %
identisch; Audio, Shader und Level-Daten fehlen noch (Stufen 2–4). Details: `WINDOWS_REBUILD.md`.

Xbox-Ordner (Titel-ID `534307EC`):

| Ordner | Dateien | Bedeutung |
|---|---|---|
| `9CA70CF0EDA43654D158C2E37470D301DFA850E753` | `pack10.000`, `credits_DLC1.wmv`, `spa.bin` | DLC1 Beneath the Ashes (Pflicht) |
| `600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153` | `pack11.000`, `credits_DLC2.wmv`, `spa.bin` | DLC2 Lara's Shadow (optional, noch nicht portiert) |
| `9FDD…`, `AC00…`, `E5AF…` | `pack2.000`, `pack20.000`, `pack1.000` | Kostüm-DLCs (Classic Costumes, Wetsuit, Designer), vom Installer nicht unterstützt |

Kostüm-Pakete (27.10.2026 gelesen): je 13 Einträge, Namen `dlc_costume_a`…`_p`, `dlc_costumes1/2`,
`co_lara_backpack`; `pack20.000` zusätzlich `co_dlc_lara_f`, `dlc_costumes4`, `dlc_doppel_costume_a`.
trudlcport (Stand B138) erwähnt die Kostüm-Pakete nirgends (STATUS/FINDINGS/INVESTIGATION); nur
`tools/costume_cmp.py` vergleicht DLC-Kostüm-Objekte mit den Lara-Objekten der Xbox-Version.
Zuordnung (27.10.2026, aus den Daten): `pack1` = Wetsuit (Kostüme k, p), `pack2` = Classic (a, h),
`pack20` = Designer (l, m) – Details und Vorschaubilder in `Referenzen\README.md`.

## Upstream-Klon

`trudlcport\` = `git clone https://github.com/andrearicci93/trudlcport.git` (27.10.2026, Stand `72b4ceb`),
eigenes Git-Repo, im Projekt-Repo ignoriert. Lizenz MIT („Copyright (c) 2026 trudlcport contributors“) –
bei Veröffentlichung als eigener Klon LICENSE behalten und auf das Original verweisen (kein PR).

## Entwicklungsumgebung (`data\`, nicht in Git)

Die Python-Werkzeuge von trudlcport laufen mit `bin\venv\Scripts\python.exe` (Python 3.14, numpy, Pillow, capstone).
Im Klon liegt der Branch `windows`: die Platzhalter `/path/to/…` in `tools\` zeigen relativ auf `../data/` –
die Werkzeuge deshalb immer aus dem Klon-Ordner starten (`cd trudlcport`, dann `..\bin\venv\Scripts\python.exe -I tools\…`).

| `data\…` | Verknüpfung (Junction) auf |
|---|---|
| `pc` | Spielordner (siehe „Spiel“, nur lesen) |
| `trudlcport` | den Klon `trudlcport\` |
| `Xenia-SteveRepack\Content\534307EC\00000002` | `input\xbox-dlc` |
| `TombRaiderUnderworld_Patched` | `input\xbox-game` (Xbox-Hauptspiel + Title Update) |

**Achtung:** `data\` nie rekursiv löschen (`Remove-Item -Recurse`, Explorer) – das kann durch die Junctions die
Spieldateien bzw. den Klon löschen. Junctions einzeln entfernen: `cmd /c rmdir data\pc`.

## Werkzeuge (`bin\`, nicht in Git)

| Werkzeug | Version | Quelle | SHA-256 |
|---|---|---|---|
| Ghidra | 12.2 (22.10.2026) | [NationalSecurityAgency/ghidra](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.2_build), `ghidra_12.2_PUBLIC_20261016.zip` | `2c2cd776…7be67` |
| JDK (Temurin) | 25.0.5+8 (Ghidra 12.2 braucht Java ≥ 25) | [adoptium/temurin25-binaries](https://github.com/adoptium/temurin25-binaries/releases), `OpenJDK25U-jdk_x64_windows_hotspot_25.0.5_8.zip` | `636bdc13…96c42` |

| Yura | 1.7.2 (03.04.2026) | [TheIndra55/Yura](https://github.com/TheIndra55/Yura/releases/tag/v1.7.2), `Yura.zip` – Dateilisten (`ref\yura-release` im Klon) | `4e482042…8df07` |
| ffmpeg (gyan.dev essentials) | 9.0.2 (20.09.2026) | [GyanD/codexffmpeg](https://github.com/GyanD/codexffmpeg/releases/tag/9.0.2) – XMA-Decoder für die Audio-Umwandlung | `60f46726…047ba` |
| Xenia Canary | 02d2cb5 (24.03.2026) | [xenia-canary/xenia-canary-releases](https://github.com/xenia-canary/xenia-canary-releases/releases/tag/02d2cb5), `xenia_canary_windows_.zip` | `1adbb2c1…d0796` |

Xenia (zum Vergleich mit der Xbox-Fassung): `bin\xenia-canary\` mit `portable.txt`; Inhalte unter
`content\0000000000000000\534307EC\` – `00000002` ist eine Verknüpfung auf `input\xbox-dlc`, `000B0000\<TU>\` enthält
eine Kopie von `default.xexp` + `TitleUpdate.000`. Start: `.\bin\xenia-canary\xenia_canary.exe .\input\xbox-game\default.xex`.
`bin\` wegen der Verknüpfung ebenfalls nie rekursiv löschen.
Xenia-Konfiguration (`xenia-canary.config.toml`, Sicherungen `.bak`–`.bak3`): Tastatur an (`keyboard_mode = 1`;
A = Enter/Leertaste, B = Rücktaste, Steuerkreuz = Pfeiltasten, rechter Stick = Ziffernblock 8/4/2/6),
`license_mask = -1` (DLC lizenziert), `render_target_path_d3d12 = "rov"` (gegen die Grafikfehler in Underworld,
laut xenia-canary game-compatibility #418).

Neu einrichten: `.\Get-Tools.ps1 -Verbose` – lädt die Zips nach `bin\_download\`, prüft SHA-256, entpackt nach `bin\`.
Schon vorhanden auf dem PC: cdb x86 (Windows Kits 10), x32dbg (x64dbg-Snapshot 2019-11-05),
Cheat Engine 7.5, Python 3.14 mit capstone/pefile/bsdiff4. REA (morluto/rea) folgt später (ändert die
Claude-Code-Konfiguration, braucht Ghidra).

## Spiel (geprüft 27.10.2026)

Spielordner = `<Steam-Bibliothek>\steamapps\common\Tomb Raider Underworld` (Steam-App 8140). `Install-TruDlc.ps1`
findet ihn selbst: `SteamPath` aus der Registry `HKCU\Software\Valve\Steam`, dazu alle Bibliotheken aus
`<SteamPath>\steamapps\libraryfolders.vdf`; liegt das Spiel woanders, `-GamePath` angeben.

`tru.exe` v1.1; `tru.exe`, `bigfile.000`–`003`
und `patch.000` stimmen in Größe und MD5 mit `docs/data/pc_game_files.tsv` des Projekts überein.
Kein `mods\`-Ordner, original `binkw32.dll` (356.104 Bytes) – vor dem ModLoader sichern.

## Schritte

1. [x] `python -m pip install bsdiff4` – bsdiff4 1.3.2 installiert (27.10.2026)
2. [x] Kit-MD5 geprüft (B138: `9fb60fa291df6e299a8ea5cc2d44352d` = ok), nach `release\B138\kit\` entpackt (278 Dateien);
   `install_dlc.py` (MD5 `225308d2126aed0b53746c3c2e934dab`) durchgelesen: kein Netz, `--check` schreibt nichts
3. [x] Backups in `backup\` (`binkw32.dll.steam_original` MD5 `2f912c88…f320`, `tru.exe.steam_original`),
   ModLoader entpackt nach `staging\ModLoader-v1.2\`
4. [x] Trockenlauf: `.\Install-TruDlc.ps1 -Check` (schreibt nichts) – 27.10.2026: Build `B138_audio`,
   pack10.000 + pack11.000 gefunden, „All inputs OK (277 files verified, 0 optional skipped)“, Exit 0
5. [x] Installation: `.\Install-TruDlc.ps1` – prüft Backups + Trockenlauf, kopiert `ModLoader.asi` und
   `binkw32.dll` in den Spielordner, startet dann `install_dlc.py` (legt `mods\` an, patcht `tru.exe`,
   schreibt `movies\credits_DLC1.bik`) – 27.10.2026: „Installed: 277 files“, Exit 0; nachgeprüft:
   275 Dateien in `mods\` + `tru.exe` + `credits_DLC1.bik`, alle MD5 = Manifest
6. [ ] Steam: neues Spiel über „Downloadable content“ → Beneath the Ashes, 60 fps begrenzen
7. [ ] Kostüm-Issue posten (Entwurf: `docs\Issue-Kostueme.md`)
8. [ ] Steam Machine (SteamOS/Proton): geänderte Dateien übertragen, testen – erst wenn Schritt 6 auf dem PC läuft

## Stand 27.10.2026 nach erstem Spielstart

- DLC1 erscheint im Menü „Downloadable content“ und startet (mit `/affinity FFFF`).
- Deutsch: `.\Set-TruDisplay.ps1 -Language German` (Registry `Language = 2`) – im Spiel bestätigt, DLC-Texte deutsch.
- Fenstermodus: das Spiel setzt `Fullscreen` beim Start wieder auf 1 (registry nach dem Start geprüft) –
  `LockWindowSize`/`LockedWindow*` bleiben stehen, werden aber nicht benutzt. Offen: Alt+Enter, Ursache.
- **Menüfehler (offen):** Im DLC-Missionsmenü liegt der Titel („UNTER DER ASCHE“ / „BENEATH THE ASHES“)
  mitten über dem Beschreibungstext oben rechts – in Englisch und Deutsch, bei 1600×900 und 1920×1080.
  Upstream nicht dokumentiert (STATUS/CHANGELOG). Kandidat für den eigenen Klon: Layout des DLC-Menüs;
  upstream ändert per `tools/menu_dlc_patch.py` das Ring-Menü-Skript (Section 7 UIPause in `generalbank.drm`).
- Steam-Startoption mit Spielzeit-Erfassung: `cmd /c start "" /wait /affinity FFFF %command%`.

Fenstermodus: `.\Set-TruDisplay.ps1 -Windowed` (1600×900; Registry `HKCU\Software\Crystal Dynamics\Tomb Raider:
Underworld\Graphics`, vorher Export nach `backup\TRU-Graphics_<Zeit>.reg`), zurück mit `-Fullscreen` oder `-Restore`.
Alle 6 Monitore 1920×1080 @ 60 Hz → im Fenster mit `EnableVSync=1` automatisch 60 fps.

## Absturz beim Start (27.10.2026) – CPU mit mehr als 31 Threads

Erster Start nach der Installation: Absturz nach 24 s, `tru.exe` `0xc0000409` (FAST_FAIL_INVALID_EXCEPTION_CHAIN) an
`tru+0xa235d`, Folgeabsturz in `windows.storage.dll`. Dump-Auswertung mit cdb (x86): Die CPU-Erkennung des Spiels
(`cpuid`/`bsr`) schiebt eine Affinitätsmaske Kern für Kern weiter; bei 32 Bit läuft sie über, die Schleife endet nie
und schreibt über den Stack hinaus (Index `edi = 0x4d0`). Ursache ist der i9-9980XE mit **36 Threads** – bekannter Fehler
des Originalspiels bei mehr als 31 Threads (PCGamingWiki), nicht der DLC-Port.

Lösung: Spiel mit höchstens 31 Threads starten – Steam → Eigenschaften → Startoptionen:
`cmd /c start "" /affinity FFFF %command%` (16 Threads).

Ausgaben: `-Verbose` (Schritte), `-Debug` (Pfade, Hashes, Aufrufe), `-Trace` (PowerShell-Zeilentrace).
Jeder Lauf schreibt `logs\Install-TruDlc_<Zeit>_<Modus>.log` mit kompletter Python-Ausgabe.

Zurück zum Original: `.\Install-TruDlc.ps1 -Restore` (binkw32.dll + tru.exe aus `backup\`, `mods\` →
`mods_disabled_<Zeit>`, `ModLoader.asi` → `.disabled`).

Probleme: `docs/TROUBLESHOOTING.md` im Projekt (Anzeigetreiber-Fehler → dgVoodoo2). Fallback-Build: B132
(zuletzt komplett durchgespielt, Kit-MD5 `ee833768f743831e58e73fff1de1149b`).
