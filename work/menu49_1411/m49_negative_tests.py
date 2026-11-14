r"""0.22.49 (2026-11-14): negative tests of trumenu_ini_check.check_02249 - each case breaks one rule in a copy of
TruMenu.cpp (read_cpp is replaced in memory) or of TruMenu.switches.txt (a mutated copy in _archiv\ next to this script,
overwritten per case and kept) and must yield at least one problem; the unchanged sources none. Every pattern must occur
exactly once (else the case counts as failed).

Usage (from the repository root):
  ../bin/pyt -t 300 work/menu49_1411/m49_negative_tests.py
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import trumenu_ini_check as T

SRC = T.read_cpp()
SW = T.SWITCHES
SW_TEXT = open(SW, encoding='utf-8').read()
CPP_CASES = [
    ('version', 'const char *const kVersion = "TruMenu 0.22.49 (sonar all floors + map info,',
     'const char *const kVersion = "TruMenu 0.22.49 (sonar,'),
    ('A1 address', 'const DWORD kSoA1 = 0x006e429b;', 'const DWORD kSoA1 = 0x006e429d;'),
    ('A1 game bytes', 'kSoA1Game[2] = {0x74, 0x1d}', 'kSoA1Game[2] = {0x74, 0x2b}'),
    ('A1 new bytes', 'kSoA1New[2] = {0x90, 0x90}', 'kSoA1New[2] = {0xeb, 0x1d}'),
    ('A1 check row', '{0x006e4284, "8b04b1 39b88c000000 742b 8a1568f2ed00 8490b0000000 741d"}',
     '{0x006e4284, "8b04b1 39b88c000000 742b 8a1568f2ed00 8490b0000000 7410"}'),
    ('close check row dropped', '    {0x006dff58, "33c0 391d10ff8a00 891d34ff8a00"},\n', ''),
    ('A1 without full', 'const bool wantA = wantC && g_soAll != 0;', 'const bool wantA = g_soAll != 0;'),
    ('A1 not put back', '    if (g_soOnA && SoWrite(kSoPartA.at, kSoPartA.ours, kSoPartA.game, kSoPartA.len)) g_soOnA = false;\n', ''),
    ('A1 off through SoPart', 'if (!SoPart(&kSoPartA, 1, false, "all floors")) return;',
     'if (!WriteBytes(kSoA1, kSoA1Game, 2)) return;'),
    ('read key', 'GetPrivateProfileIntA("Sonar", "AllFloors"', 'GetPrivateProfileIntA("Sonar", "AllFloor"'),
    ('options key', 'OptInt(ini, "Sonar", "AllFloors")', 'OptInt(ini, "Sonar", "AllFloor")'),
    ('item not kept', 'SoSetKey("AllFloors", &g_soAll, on, "sonar.allfloors");', 'InterlockedExchange(&g_soAll, on ? 1 : 0);'),
    ('section loads', '    SoMapTick(now);                          // 0.22.49',
     '    SoMapTick(now);                          // 0.22.49\n    ReadDword(0x006e4e80, &now);'),
    ('map tick writes', '    g_soMapTick = now ? now : 1;\n',
     '    g_soMapTick = now ? now : 1;\n    WriteBytes(kSoFloor, &g_soMapTick, 1);\n'),
    ('map tick while closed', 'mode == 0 || mode > 4', 'mode > 4'),
    ('map tick no list test', 'listed = ReadDword(list + 4 * k, &u) && u == anchor;', 'listed = true;'),
    ('map tick not called', '    SoMapTick(now);                          // 0.22.49', '    // SoMapTick(now);'),
    ('item thread', '"AllFloors, kept, live", true, ValSoAll, RunSoAll},', '"AllFloors, kept, live", false, ValSoAll, RunSoAll},'),
    ('item help', '{"sonar.unitmap", "", "', '{"sonar.unitmaq", "", "'),
    ('key default', '{"Sonar", "AllFloors", "0", ', '{"Sonar", "AllFloors", "1", '),
    ('settings row', '{"Karte dieser Unit", "Map of this unit", "sonar.unitmap", "", kQbInfo, -1, kQcNone, 0, kQbGrey, 0},',
     '{"Karte dieser Unit", "Map of this unit", "sonar.status", "", kQbInfo, -1, kQcNone, 0, kQbGrey, 0},'),
    ('Paket G row', '"sonar.allfloors", "", kQbBool, -1, kQcNone, 0, kQbBlue, kQfTg},',
     '"sonar.full", "", kQbBool, -1, kQcNone, 0, kQbBlue, kQfTg},'),
    ('keep label', '{"Nach Einsatz auffuellen", "Refill after use", "adren.keep", "", kQbBool, -1, kQcNone, 0, kQbCheat, 0},\n    {"Adrenalin bleibt',
     '{"Adrenalin voll halten", "Refill after use", "adren.keep", "", kQbBool, -1, kQcNone, 0, kQbCheat, 0},\n    {"Adrenalin bleibt'),
    ('mode label test', '{"Modus ohne Ziel", "Mode without target"', '{"Modus ohne Ziel (Test)", "Mode without target"'),
    ('assist label', '{"Zielhilfe Kreis", "Circle aim assist"', '{"Adrenalin: Zeiger im Ziel (Hilfe)", "Circle aim assist"'),
    ('stayfull row missing', '    {"Adrenalin bleibt voll", "Adrenaline stays full", "adren.stayfull", "", kQbBool, -1, kQcNone, 0, kQbCheat, 0},\n', ''),
    ('Paket A copy', '    {"Adrenalin bleibt voll", "Adrenaline stays full", "adren.stayfull", "", kQbBool, -1, kQcNone, 0, kQbCheat, kQfTg},\n', ''),
    ('stayfull other key', 'WritePrivateProfileStringA("Adrenaline", "DrainModePercent", b, path)',
     'WritePrivateProfileStringA("Adrenaline", "FillPercent", b, path)'),
    ('stayfull patches', '    g_asReadAt = 0;\n', '    g_asReadAt = 0;\n    WriteCode(0x006f2965, a, 2);\n'),
    ('stayfull not kept', '        IniKeepInt("Adrenaline", "StayFullDrainWas", d);\n', ''),
    ('stayfull off onto 0', '        if (nd == 0 && nm == 0) nd = nm = 100;   // never', '        // never'),
    ('cap without full', 'const LONG wantT = wantC && g_soCap > kSoCapGame ? g_soCap : 0;',
     'const LONG wantT = g_soCap > kSoCapGame ? g_soCap : 0;'),
    ('cap imm off by one', 'const DWORD imm = static_cast<DWORD>(wantT - 1);', 'const DWORD imm = static_cast<DWORD>(wantT);'),
    ('cap not put back', '    if (g_soOnT && SoWrite(kSoT1, g_soT1New, kSoT1Game, 4)) g_soOnT = 0;\n', ''),
    ('cap game bytes', 'kSoT1Game[4] = {0x83, 0x6d, 0x01, 0x00}', 'kSoT1Game[4] = {0x84, 0x6d, 0x01, 0x00}'),
    ('cap key default', '{"Sonar", "TriangleCap", "300000", ', '{"Sonar", "TriangleCap", "93572", '),
    ('sonar log fix undone', '"snd.sonar %d (src=%s, was %d): %s%s; [Sound] SonarMute=%d written"',
     '"snd.sonar %d (src=%s, was %d): %s; [Sound] SonarMute=%d written"'),
]
SW_CASES = [
    ('allfloors restart', 'All connected areas | live | 0 |', 'All connected areas | restart | 0 |'),
    ('allfloors default', 'All connected areas | live | 0 |', 'All connected areas | live | 1 |'),
    ('allfloors since', 'with FullMap) | TruMenu 0.22.49', 'with FullMap) | TruMenu 0.22.48'),
    ('cap row default', 'triangle cap | live | 300000 |', 'triangle cap | live | 93572 |'),
    ('cap row restart', 'triangle cap | live |', 'triangle cap | restart |'),
    ('mode test label', '| Adrenalin-Modus ohne Ziel | Adrenaline mode without target |',
     '| Adrenalin-Modus ohne Ziel (Test) | Adrenaline mode without target |'),
    ('strike test label', '| Absprung-Schlag ohne X | Jump-off strike without X |',
     '| Absprung-Schlag ohne X | Jump-off strike without X (test) |'),
]


def main():
    bad = 0
    T.read_cpp = lambda: SRC
    p, _ = T.check_02249(SW)
    print('positive (unchanged sources): %d problem(s) %s' % (len(p), 'ok' if not p else 'FAIL ' + '; '.join(p)))
    bad += 1 if p else 0
    for name, old, new in CPP_CASES:
        if SRC.count(old) != 1:
            print('case %-24s: pattern found %d times (need 1) - FAIL' % (name, SRC.count(old))); bad += 1; continue
        mutated = SRC.replace(old, new, 1)
        T.read_cpp = lambda m=mutated: m
        p, _ = T.check_02249(SW)
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-24s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    T.read_cpp = lambda: SRC
    os.makedirs(os.path.join(HERE, '_archiv'), exist_ok=True)
    copy = os.path.join(HERE, '_archiv', 'm49_switches_mutated.txt')
    for name, old, new in SW_CASES:
        if SW_TEXT.count(old) != 1:
            print('case %-24s: pattern found %d times (need 1) - FAIL' % (name, SW_TEXT.count(old))); bad += 1; continue
        with open(copy, 'w', encoding='utf-8', newline='') as f:
            f.write(SW_TEXT.replace(old, new, 1))
        p, _ = T.check_02249(copy)
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-24s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    print('%d cases + 1 positive, %d failed' % (len(CPP_CASES) + len(SW_CASES), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
