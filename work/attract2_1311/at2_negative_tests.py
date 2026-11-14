"""Q126b (2026-11-13, TruMenu 0.22.40 attract display styles): negative tests for tools/trumenu_ini_check.py check_02240
(with check_02239 and the switches check, which run on the same sources) - read-only on the repository: every mutation
goes into a copy below OUT_DIR, the repository files are only read.

Each case changes ONE thing the checks must catch and expects at least one problem; case 0 (no change) expects none.
Prints one line per case and a summary; exit code 0 = every case behaved as expected.

Usage (from trudlcport): ../bin/pyt -t 600 work/attract2_1311/at2_negative_tests.py OUT_DIR
  OUT_DIR  scratch folder for the mutated copies (outside the repository)
"""
import os, sys, io, shutil, contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import trumenu_ini_check as T      # noqa: E402

CPP_CASES = [
    ('kOpts AttractIcon default 1', '{"Menu", "AttractIcon", "7",', '{"Menu", "AttractIcon", "1",'),
    ('kOpts AttractIconText back', '    {"Pad", "BlockInput", "1",',
     '    {"Menu", "AttractIconText", "1", "old"},\n    {"Pad", "BlockInput", "1",'),
    ('g_atText back', 'volatile LONG g_atWant = 0, g_atStyle = 7,', 'volatile LONG g_atWant = 0, g_atText = 1, g_atStyle = 7,'),
    ('old INI 1 + 1 mapped to 3', 'const int mapped = v == 0 ? 0 : v == 1 ? (text ? 7 : 3) : v;',
     'const int mapped = v == 0 ? 0 : v == 1 ? (text ? 3 : 7) : v;'),
    ('no range clamp', 'if (v < 0 || v >= kAtStyleN) { *bad = true; v = def; }', '(void)0;'),
    ('AtStyleRead writes without migrate', '        if (migrate) {', '        if (true) {'),
    ('AtStyleRead keeps AttractIconText',
     'const BOOL ok = WritePrivateProfileStringA("Menu", "AttractIconText", nullptr, ini) &&', 'const BOOL ok = TRUE &&'),
    ('AtReadSwitch does not migrate', 'AtStyleRead(g_iniPath, true, &bad, &raw);', 'AtStyleRead(g_iniPath, false, &bad, &raw);'),
    ('ReadOptions migrates (log not open)', 'AtStyleRead(ini, false, &bad, &raw);', 'AtStyleRead(ini, true, &bad, &raw);'),
    ('AtReadSwitch leaves g_atWant', '        InterlockedExchange(&g_atWant, style ? 1 : 0);\n        g_atIniOn = style;',
     '        g_atIniOn = style;'),
    ('style 2 with strike', '{1, 0, kAtTextNone, "Kreis", "circle"},', '{1, 1, kAtTextNone, "Kreis", "circle"},'),
    ('table with 7 rows', '    {1, 1, kAtTextInside, "Kreis + Strich, Text innen", "circle + strike, text inside"},\n', ''),
    ('style 5 name English only', '"Kreis, Text unten", "circle, text below"', '"circle, text below", "circle, text below"'),
    ('default style 3', 'const int kAtStyleN = 8, kAtStyleDefault = 7;', 'const int kAtStyleN = 8, kAtStyleDefault = 3;'),
    ('AtStyleOf without clamp', 'return kAtStyles[s >= 0 && s < kAtStyleN ? s : kAtStyleDefault];', 'return kAtStyles[s];'),
    ('strike in every style', 'if (held && st.strike)', 'if (held)'),
    ('text only draws the circle', '        if (!st.circle) {', '        if (false) {'),
    ('inside circle not enlarged', 'd = fs * 6.0f > need ? fs * 6.0f : need;', 'd = d + need * 0.0f;'),
    ('reason squeezed inside', 'if (why[0] && textAt == kAtTextInside) textAt = kAtTextBelow;', '(void)0;'),
    ('inside text English only', 'de ? "keine Uhr" : "no clock"', '"no clock"'),
    ('text only path without End', '            ImGui::End();\n            if (lit) ImGui::PopStyleColor();\n            return;',
     '            return;'),
    ('DrawAt writes the clock', 'const AtStyleDef &st = AtStyleOf(g_atStyle);',
     'const AtStyleDef &st = AtStyleOf(g_atStyle); *reinterpret_cast<float *>(g_naClock + 0x10) = 0.0f;'),
    ('item type bool', '{"menu.attracticon", "value", "0.22.40 0..7', '{"menu.attracticon", "bool", "0.22.40 0..7'),
    ('RunAt takes on', '    else if (!_stricmp(arg, "off")) v = 0;',
     '    else if (!_stricmp(arg, "off")) v = 0;\n    else if (!_stricmp(arg, "on")) v = 7;'),
    ('RunAt without the upper bound', '    if (v < 0 || v >= kAtStyleN) {\n        Out(o, n, "usage',
     '    if (v < 0) {\n        Out(o, n, "usage'),
    ('RunAt keeps the old key',
     '    if (g_iniPath[0]) WritePrivateProfileStringA("Menu", "AttractIconText", nullptr, g_iniPath);   // the 0.22.39 key\n', ''),
    ('RunAt does not keep the INI', '    IniKeepInt("Menu", "AttractIcon", v);', '    (void)0;'),
    ('RunAt flips without an argument',
     '    if (!arg || !arg[0]) { ValAt(o, n); return true; }   // no argument = report, never a flip',
     '    if (!arg || !arg[0]) arg = g_atStyle ? "0" : "7";'),
    ('bar row bool again',
     '{"Teaser-Anzeige", "Teaser display", "menu.attracticon", "", kQbValue, -1, kQcNone, kQvAtStyle,',
     '{"Teaser-Anzeige", "Teaser display", "menu.attracticon", "", kQbBool, -1, kQcNone, 0,'),
    ('QbValueCount 7 steps', ': val == kQvAtStyle ? kAtStyleN : 0;', ': val == kQvAtStyle ? 7 : 0;'),
    ('QbValueNow without the style', '    case kQvAtStyle: v = static_cast<int>(g_atStyle); break;   // 0.22.40 (Q126b)\n', ''),
    ('bar row without the style name', 'Out(o, n, "%ld %s", s, de ? AtStyleOf(s).de : AtStyleOf(s).en);', 'Out(o, n, "%ld", s);'),
    ('kVersion not 0.22.40', 'const char *const kVersion = "TruMenu 0.22.40 (Q126b', 'const char *const kVersion = "TruMenu 0.22.40 (Q126c'),
    ('help line over 60 characters', '(Varianten 2-7)|Off', '(Varianten 2-7) und noch viel mehr Text dahinter|Off'),
]


def run_check(cpp, ini, switches):
    T.CPP = cpp
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        problems = T.check_02240(ini, switches)[0] + T.check_02239(ini, switches)[0]
        problems += T.check_switches(switches)[0]   # (problems, summary, rows)
    return problems


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    real_cpp, real_root = T.CPP, T.ROOT
    src_cpp = open(real_cpp, encoding='utf-8', newline='').read()
    ini, sw = T.INI, T.SWITCHES
    results = []
    p = run_check(real_cpp, ini, sw)
    results.append(('0 unchanged sources', len(p) == 0, len(p), p[:1]))
    for k, (name, old, new) in enumerate(CPP_CASES, 1):
        old_n, new_n = old.replace('\n', '\r\n'), new.replace('\n', '\r\n')   # TruMenu.cpp has CRLF line ends
        if src_cpp.count(old_n) != 1:
            results.append(('%d %s' % (k, name), False, -1, ['mutation anchor found %d times' % src_cpp.count(old_n)]))
            continue
        path = os.path.join(out_dir, 'TruMenu_neg%d.cpp' % k)
        open(path, 'w', encoding='utf-8', newline='').write(src_cpp.replace(old_n, new_n, 1))
        p = run_check(path, ini, sw)
        results.append(('%d %s' % (k, name), len(p) > 0, len(p), p[:1]))
    T.CPP = real_cpp
    k = len(CPP_CASES)
    ini_text = open(ini, encoding='utf-8', newline='').read()
    bad_ini = os.path.join(out_dir, 'TruMenu_neg.ini')
    for name, old, new in (('INI with AttractIcon=1', '\nAttractIcon=7\n', '\nAttractIcon=1\n'),
                           ('INI with AttractIconText again', '\nAttractIcon=7\n', '\nAttractIcon=7\nAttractIconText=1\n')):
        k += 1
        if ini_text.count(old) != 1:
            results.append(('%d %s' % (k, name), False, -1, ['mutation anchor found %d times' % ini_text.count(old)]))
            continue
        open(bad_ini, 'w', encoding='utf-8', newline='').write(ini_text.replace(old, new, 1))
        p = run_check(real_cpp, bad_ini, sw)
        results.append(('%d %s' % (k, name), len(p) > 0, len(p), p[:1]))
    sw_text = open(sw, encoding='utf-8', newline='').read()
    bad_sw = os.path.join(out_dir, 'TruMenu_neg.switches.txt')
    for name, old, new in (
            ('switches row bool', '| AttractIcon | int:0..7 |', '| AttractIcon | bool |'),
            ('switches row default 1', '(0-7) | live | 7 |', '(0-7) | live | 1 |'),
            ('switches row restart', '(0-7) | live | 7 |', '(0-7) | restart | 7 |'),
            ('switches row since 0.22.39', '5 below) | TruMenu 0.22.40', '5 below) | TruMenu 0.22.39'),
            ('switches row AttractIconText again', 'TruMenu | Menu | AttractIcon | int:0..7',
             'TruMenu | Menu | AttractIconText | bool | Teaser-Text | Teaser text | live | 1 | a // b | TruMenu 0.22.39\n'
             'TruMenu | Menu | AttractIcon | int:0..7'),
            ('switches group tmhauptmenue missing', 'group | tmhauptmenue |', 'group | tmhaupt |')):
        k += 1
        if sw_text.count(old) != 1:
            results.append(('%d %s' % (k, name), False, -1, ['mutation anchor found %d times' % sw_text.count(old)]))
            continue
        open(bad_sw, 'w', encoding='utf-8', newline='').write(sw_text.replace(old, new, 1))
        p = run_check(real_cpp, ini, bad_sw)
        results.append(('%d %s' % (k, name), len(p) > 0, len(p), p[:1]))
    # README / Set-TruMenu: a copy root with only these two files (the checks read them below T.ROOT)
    for name, rel, old, new in (
            ('README without TO TEST 0.22.40', ('src', 'asi', 'TruMenu', 'README.md'), '\n### TO TEST 0.22.40', '\n### TEST 0.22.40'),
            ('Set-TruMenu without the 0.22.39 hash', ('scripts', 'windows', 'Set-TruMenu.ps1'),
             '11bce73110d4c61c3b85cf8375e5bb019442c6154060468027b589372a10f6d5', '0' * 64)):
        k += 1
        root = os.path.join(out_dir, 'root%d' % k)
        for r in (('src', 'asi', 'TruMenu', 'README.md'), ('scripts', 'windows', 'Set-TruMenu.ps1')):
            os.makedirs(os.path.join(root, *r[:-1]), exist_ok=True)
            shutil.copyfile(os.path.join(real_root, *r), os.path.join(root, *r))
        target = os.path.join(root, *rel)
        text = open(target, encoding='utf-8', newline='').read()
        if text.count(old) != 1:
            results.append(('%d %s' % (k, name), False, -1, ['mutation anchor found %d times' % text.count(old)]))
            continue
        open(target, 'w', encoding='utf-8', newline='').write(text.replace(old, new, 1))
        T.ROOT = root
        try:
            p = run_check(real_cpp, ini, sw)
        finally:
            T.ROOT = real_root
        results.append(('%d %s' % (k, name), len(p) > 0, len(p), p[:1]))
    bad = 0
    for name, ok, n, first in results:
        print('%-4s %-45s problems %3d %s' % ('ok' if ok else 'FAIL', name, n, ('- ' + first[0][:110]) if first else ''))
        bad += 0 if ok else 1
    print('%d cases, %d as expected, %d not' % (len(results), len(results) - bad, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
