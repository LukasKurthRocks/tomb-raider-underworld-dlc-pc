# TRU-DLC – Xbox-360-DLCs von Tomb Raider Underworld auf PC

Ziel: *Beneath the Ashes* (DLC1) und später *Lara's Shadow* (DLC2) in der Steam-PC-Version spielen,
mit dem Fan-Port [trudlcport](https://github.com/andrearicci93/trudlcport) (andrearicci93).

## Ordner

| Pfad | Inhalt |
|---|---|
| `input\xbox-dlc\` | eigene Xbox-360-DLC-Daten |
| `input\ModLoader-v1.2.zip` | [TombRaiderModding/ModLoader](https://github.com/TombRaiderModding/ModLoader/releases) v1.2 (20.07.2024) |
| `release\B138\` | `install_dlc.py` + `trudlcport-kit-B138.zip` (Release 21.10.2026) |

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
Welches Paket welches Kostüm-DLC ist: noch offen.

## Spiel (geprüft 27.10.2026)

`<Spielordner>` – `tru.exe` v1.1; `tru.exe`, `bigfile.000`–`003`
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

Fenstermodus: `.\Set-TruDisplay.ps1 -Windowed` (1600×900; Registry `HKCU\Software\Crystal Dynamics\Tomb Raider:
Underworld\Graphics`, vorher Export nach `backup\TRU-Graphics_<Zeit>.reg`), zurück mit `-Fullscreen` oder `-Restore`.
Alle 6 Monitore 1920×1080 @ 60 Hz → im Fenster mit `EnableVSync=1` automatisch 60 fps.

Ausgaben: `-Verbose` (Schritte), `-Debug` (Pfade, Hashes, Aufrufe), `-Trace` (PowerShell-Zeilentrace).
Jeder Lauf schreibt `logs\Install-TruDlc_<Zeit>_<Modus>.log` mit kompletter Python-Ausgabe.

Zurück zum Original: `.\Install-TruDlc.ps1 -Restore` (binkw32.dll + tru.exe aus `backup\`, `mods\` →
`mods_disabled_<Zeit>`, `ModLoader.asi` → `.disabled`).

Probleme: `docs/TROUBLESHOOTING.md` im Projekt (Anzeigetreiber-Fehler → dgVoodoo2). Fallback-Build: B132
(zuletzt komplett durchgespielt, Kit-MD5 `ee833768f743831e58e73fff1de1149b`).
