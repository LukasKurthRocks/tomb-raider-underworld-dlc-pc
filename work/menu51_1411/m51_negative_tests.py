r"""0.22.51 (2026-11-14): negative tests of trumenu_ini_check.check_02251 - each case breaks one rule in a copy of
TruMenu.cpp (read_cpp is replaced in memory) or of TruMenu.switches.txt (a mutated copy in _archiv\ next to this script,
overwritten per case and kept) and must yield at least one problem; the unchanged sources none. Every pattern must occur
exactly once (else the case counts as failed).

Usage (from the repository root):
  ../bin/pyt -t 300 work/menu51_1411/m51_negative_tests.py
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import trumenu_ini_check as T

SRC = T.read_cpp()
SW = T.SWITCHES
SW_TEXT = open(SW, encoding='utf-8').read()
CPP_CASES = [
    ('version', 'const char *const kVersion = "TruMenu 0.22.51 (sonar view + base PDA + X default + DLC start from a level,',
     'const char *const kVersion = "TruMenu 0.22.51 (sonar view,'),
    ('check row changed', '{0x006e3bec, "8d4c2474 51"},', '{0x006e3bec, "8d4c2474 52"},'),
    ('check row dropped', '    {0x00551adb, "8b742414 8b5008 8b4c2410 03542418"},\n', ''),
    ('check order', '    S5Check();                                // 0.22.51', '    // S5Check();'),
    ('tick missing', '    S5Tick();                                 // 0.22.51', '    // S5Tick();'),
    ('options missing', '    S5ReadOptions(ini);', '    // S5ReadOptions(ini);'),
    ('detach without S5', '        S5Shutdown();                                 // 0.22.51', '        // 0.22.51'),
    ('D1 other site', 'const DWORD kS5D1 = 0x006e42ac,', 'const DWORD kS5D1 = 0x006e42a8,'),
    ('F1 game bytes', 'kS5F1Game[5] = {0xe8, 0xa7, 0xb0, 0xed, 0xff};', 'kS5F1Game[5] = {0xe8, 0xa7, 0xb0, 0xed, 0xfe};'),
    ('F2 not written', 'SoWrite(kS5F2, wantF ? kS5F2Game : g_s5F2New, wantF ? g_s5F2New : kS5F2Game, 5)',
     'WriteBytes(kS5F2, wantF ? g_s5F2New : kS5F2Game, 5)'),
    ('stub F2 missing', '    S5CallBytes(g_s5F2New, kS5F2, &S5FogStub);\n', ''),
    ('fog stub arg', '        mov dword ptr [esp + 0x14], eax\n', '        mov dword ptr [esp + 0x18], eax\n'),
    ('fog stub no test', '        test eax, eax\n        je s5f_go\n', ''),
    ('unit stub arg2', '        push dword ptr [esp + 0xc]\n', '        push dword ptr [esp + 0x8]\n'),
    ('unit stub no restore', '        pop edx\n        mov dword ptr [ecx], edx\n', '        pop edx\n'),
    ('S5 writes a dword', '    InterlockedExchange(&g_s5TintColour, static_cast<LONG>(out));\n',
     '    InterlockedExchange(&g_s5TintColour, static_cast<LONG>(out));\n    WriteDword(0x00ee03bc, out);\n'),
    ('fade far scale', 'farV = static_cast<float>(f) * 100.0f; nearV = farV * 0.5f;',
     'farV = static_cast<float>(f) * 10.0f; nearV = farV * 0.5f;'),
    ('fade clamp', 'return v < -1 ? -1 : v > 2000 ? 2000 : v;', 'return v < -1 ? -1 : v > 20000 ? 20000 : v;'),
    ('tint mix', 'mixed = (ch * 6 + tint[k] * 4) / 10', 'mixed = (ch * 4 + tint[k] * 6) / 10'),
    ('log not at open', '        S5LogView("open");', '        // S5LogView("open");'),
    ('pda word', 'kS5PdaGame = 0x04000001, kS5PdaOurs = 0x04000000;', 'kS5PdaGame = 0x04000001, kS5PdaOurs = 0x04000002;'),
    ('pda no safety', '    if (!S5PdaSafe(why, sizeof(why))) { Out(g_s5PdaWait, sizeof(g_s5PdaWait), "%s", why); return; }\n',
     ''),
    ('pda restores foreign', 'if (word != from || (!want && g_s5PdaOursAt != g_s5PdaAt))', 'if (word != from)'),
    ('pda while paused', 'if (ReadDword(kStreamFlags, &flags) && (flags & 0x1000)) {', 'if (ReadDword(kStreamFlags, &flags) && false) {'),
    ('pda not greyed', '    if (!_stricmp(id, "pda.basepda")) return S5PdaWhy();', '    // pda.basepda'),
    ('item thread', '"sonar.tint", "bool", "0.22.51: the map units other than Lara\'s',
     '"sonar.tint", "action", "0.22.51: the map units other than Lara\'s'),
    ('help missing', '    {"sonar.why", "", "Mitte, Achse, Schnitt-Ebene je Bereich ins Log|Centre, axis, cut plane per area to the log"},\n', ''),
    ('fade steps', 'const LONG kS5FadeSteps[8] = {-1, 0, 800, 400, 200, 100, 50, 20};',
     'const LONG kS5FadeSteps[8] = {0, -1, 800, 400, 200, 100, 50, 20};'),
    ('X runs nothing', '    case kQbValue: QbActRow(page, r, kQbDefDir); return;', '    case kQbValue: return;'),
    ('X no default', '    case kQvSoArea: i = 0; break;                           // alle\n', ''),
    ('switch X steps', 'if (dir == kQbXDir && r.type != kSwBool) {', 'if (dir == 9 && r.type != kSwBool) {'),
    ('footer', 'const bool xDef = QbSelIsValue(g_qbPage, sel);', 'const bool xDef = false;'),
    ('cmd no units', 'if (!UnitUnused(i) && !UnitNameNoArchive(kUnits[i].unit) && !UnitNoDrm(i))',
     'if (false && !UnitUnused(i))'),
    ('cmd menu map', 'const bool menuStart = !_stricmp(word, "level.load") && !InLevel();', 'const bool menuStart = false;'),
    ('level refused', 'if (state == 1 && InLevel()) return LevelStartInGame(name, given, o, n);', 'if (false) return false;'),
    ('in-level f22', '        reinterpret_cast<MissionStartFn>(kUgdF27)(args, select, 0, 1);         // f27 UILoadLevel',
     '        reinterpret_cast<VoidFn>(kUgdF22)();\n        reinterpret_cast<MissionStartFn>(kUgdF27)(args, select, 0, 1);         // f27 UILoadLevel'),
    ('in-level arg4', '        reinterpret_cast<MissionStartFn>(kUgdF27)(args, select, 0, 1);         // f27 UILoadLevel',
     '        reinterpret_cast<MissionStartFn>(kUgdF27)(args, select, 0, 0);         // f27 UILoadLevel'),
    ('in-level any unit', '_stricmp(name, "dlc_level1_start") && _stricmp(name, "dlc_level2_start")', 'false'),
    ('in-level ui ungated', '&& !g_menuPaused && !g_radPaused;', ';'),
]
SW_CASES = [
    ('fade range', 'TruMenu | Sonar | FadeFar | int:-1..2000:50 |', 'TruMenu | Sonar | FadeFar | int:0..2000:50 |'),
    ('tint default', 'Tint other areas | live | 0 |', 'Tint other areas | live | 1 |'),
    ('pda restart', 'Replace the shadow PDA with the base PDA | live | 0 |', 'Replace the shadow PDA with the base PDA | restart | 0 |'),
    ('fade since', 'faded out at n m | TruMenu 0.22.51', 'faded out at n m | TruMenu 0.22.50'),
]


def main():
    bad = 0
    T.read_cpp = lambda: SRC
    p, _ = T.check_02251(SW)
    print('positive (unchanged sources): %d problem(s) %s' % (len(p), 'ok' if not p else 'FAIL ' + '; '.join(p)))
    bad += 1 if p else 0
    for name, old, new in CPP_CASES:
        if SRC.count(old) != 1:
            print('case %-24s: pattern found %d times (need 1) - FAIL' % (name, SRC.count(old))); bad += 1; continue
        mutated = SRC.replace(old, new, 1)
        T.read_cpp = lambda m=mutated: m
        p, _ = T.check_02251(SW)
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-24s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    T.read_cpp = lambda: SRC
    os.makedirs(os.path.join(HERE, '_archiv'), exist_ok=True)
    copy = os.path.join(HERE, '_archiv', 'm51_switches_mutated.txt')
    for name, old, new in SW_CASES:
        if SW_TEXT.count(old) != 1:
            print('case %-24s: pattern found %d times (need 1) - FAIL' % (name, SW_TEXT.count(old))); bad += 1; continue
        with open(copy, 'w', encoding='utf-8', newline='') as f:
            f.write(SW_TEXT.replace(old, new, 1))
        p, _ = T.check_02251(copy)
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-24s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    print('%d cases + 1 positive, %d failed' % (len(CPP_CASES) + len(SW_CASES), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
