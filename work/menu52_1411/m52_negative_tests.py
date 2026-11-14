r"""0.22.52 (2026-11-14 late): negative tests of trumenu_ini_check.check_02252 - each case breaks one rule in a copy of
TruMenu.cpp (read_cpp is replaced in memory) or of TruMenu.switches.txt (a mutated copy in _archiv\ next to this script,
overwritten per case and kept) and must yield at least one problem; the unchanged sources none. Every pattern must occur
exactly once (else the case counts as failed).

Usage (from the repository root):
  ../bin/pyt -t 300 work/menu52_1411/m52_negative_tests.py
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import trumenu_ini_check as T

SRC = T.read_cpp()
SW = T.SWITCHES
SW_TEXT = open(SW, encoding='utf-8').read()
CPP_CASES = [
    ('version', 'const char *const kVersion = "TruMenu 0.22.52 (reverb mark + DSP graph',
     'const char *const kVersion = "TruMenu 0.22.52 (reverb + DSP graph'),
    # S6
    ('S6 row changed', '{0x006e4c45, "8b5040 8915fc03ee00"},', '{0x006e4c45, "8b5044 8915fc03ee00"},'),
    ('S6 row dropped', '    {0x00503fdb, "8b4f04 f7414400000040"},\n', ''),
    ('S6 check order', '    S6Check();                                // 0.22.52', '    // S6Check();'),
    ('S6 after return', '    S6Apply(why);                            // 0.22.52', '    // S6Apply'),
    ('S6 no shutdown', '    S6Shutdown();                            // 0.22.52', '    // S6Shutdown'),
    ('S6 offsets', 'const DWORD kS6Off[3] = {0x8c, 0x9c, 0xa0};', 'const DWORD kS6Off[3] = {0x8c, 0x9c, 0xa4};'),
    ('S6 any count', 'cnt != 11 ||', 'cnt == 0 ||'),
    ('S6 over foreign', 'if (cur != m.game[k] && cur != m.ours[k]) {', 'if (false) {'),
    ('S6 back always', 'cur == m.ours[k] && cur != m.game[k] &&', 'cur != m.game[k] &&'),
    ('S6 falloff kept', '    v[2] = 1.0f;\n', '    v[2] = 0.5f;\n'),
    ('S6 dword write', '            if (WriteBytes(params + kS6Off[k], &v[k], 4)) { m.ours[k] = v[k]; ++wrote; }',
     '            if (WriteDword(params + kS6Off[k], 0)) { m.ours[k] = v[k]; ++wrote; }'),
    # W10
    ('W10 tick missing', '    W10Tick();                                // 0.22.52', '    // W10Tick();'),
    ('W10 one loop', '                W10RevIcon(dl, ImVec2(p.x + h * 3.3f, p.y), h, v.rev, c);', '                // icon'),
    ('W10 no bar mark', 'W10RevIcon(dl, ImVec2(stateX, y), fs, v.rev - 1,', 'W10RevIcon(dl, ImVec2(stateX, y), fs, 0,'),
    ('W10 sweep all', '!W8FmOf(handle, &ci, &fl, &rf, &mode) || !(fl & 8)) continue;',
     '!W8FmOf(handle, &ci, &fl, &rf, &mode)) continue;'),
    ('W10 sweep idle', '    if (!g_w9On || (g_w10SweepTick && now - g_w10SweepTick < 50)) return;',
     '    if (g_w10SweepTick && now - g_w10SweepTick < 50) return;'),
    ('W10 no TO TEST', '"tgB2.dspgraph", kQbCheck', '"tgB2.dspgr", kQbCheck'),
    # area colours
    ('tint clamp', 'return v <= 0 ? 0 : v >= 2 ? 2 : 1;', 'return v != 0 ? 1 : 0;'),
    ('tint palette', 'const int kS5PalN = 8;', 'const int kS5PalN = 4;'),
    ('tint bool row', '{"Sonar: Bereichsfarben", "Sonar: area colours", "sonar.tint", "", kQbValue, -1, kQcNone, kQvSoTint, kQbBlue, 0},',
     '{"Sonar: Bereichsfarben", "Sonar: area colours", "sonar.tint", "", kQbBool, -1, kQcNone, 0, kQbBlue, 0},'),
    # (j) joint rows
    ('j motion driven', 'const bool usable = !motion && a < z && !(loOpen && hiOpen);', 'const bool usable = true;'),
    ('j no limit cut', '                if (z > lr1) z = lr1;\n', ''),
    ('j lock kept', '        JtStop(line, ours);', '        JtStop(line, false);'),
]
SW_CASES = [
    ('tint bool', 'TruMenu | Sonar | TintOthers | int:0..2 |', 'TruMenu | Sonar | TintOthers | bool |'),
]


def main():
    bad = 0
    T.read_cpp = lambda: SRC
    p, _ = T.check_02252(SW)
    print('positive (unchanged sources): %d problem(s) %s' % (len(p), 'ok' if not p else 'FAIL ' + '; '.join(p)))
    bad += 1 if p else 0
    for name, old, new in CPP_CASES:
        if SRC.count(old) != 1:
            print('case %-18s: pattern found %d times (need 1) - FAIL' % (name, SRC.count(old))); bad += 1; continue
        mutated = SRC.replace(old, new, 1)
        T.read_cpp = lambda m=mutated: m
        p, _ = T.check_02252(SW)
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-18s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    T.read_cpp = lambda: SRC
    os.makedirs(os.path.join(HERE, '_archiv'), exist_ok=True)
    copy = os.path.join(HERE, '_archiv', 'm52_switches_mutated.txt')
    for name, old, new in SW_CASES:
        if SW_TEXT.count(old) != 1:
            print('case %-18s: pattern found %d times (need 1) - FAIL' % (name, SW_TEXT.count(old))); bad += 1; continue
        with open(copy, 'w', encoding='utf-8', newline='') as f:
            f.write(SW_TEXT.replace(old, new, 1))
        p, _ = T.check_02252(copy)
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-18s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    n = len(CPP_CASES) + len(SW_CASES)
    print('%d cases + 1 positive, %d failed' % (n, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
