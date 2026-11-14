"""Q126c (2026-11-14, TruMenu 0.22.41 compact attract styles 8 .. 16): negative tests for tools/trumenu_ini_check.py
check_02241 (with check_02240 / check_02239 and the switches check, which run on the same sources) - read-only on the
repository: every mutation goes into a copy below OUT_DIR, the repository files are only read.

Each case changes ONE thing the checks must catch and expects at least one problem; case 0 (no change) expects none.
Prints one line per case and a summary; exit code 0 = every case behaved as expected.

Usage (from trudlcport): ../bin/pyt -t 600 work/attract3_1411/at3_negative_tests.py OUT_DIR
  OUT_DIR  scratch folder for the mutated copies (outside the repository)
"""
import os, sys, io, shutil, contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import trumenu_ini_check as T      # noqa: E402

CPP_CASES = [
    ('kVersion not 0.22.41', 'const char *const kVersion = "TruMenu 0.22.41 (Q126c',
     'const char *const kVersion = "TruMenu 0.22.41 (Q126d'),
    ('kAtStyleN 16', 'const int kAtStyleN = 17, kAtStyleDefault = 7;', 'const int kAtStyleN = 16, kAtStyleDefault = 7;'),
    ('default 8', 'const int kAtStyleN = 17, kAtStyleDefault = 7;', 'const int kAtStyleN = 17, kAtStyleDefault = 8;'),
    ('style 8 with strike', '{1, 0, kAtTextBare, "Klein, ohne Kasten"', '{1, 1, kAtTextBare, "Klein, ohne Kasten"'),
    ('style 9 without strike', '{1, 1, kAtTextBare, "Klein + Strich', '{1, 0, kAtTextBare, "Klein + Strich'),
    ('table with 16 rows', '    {0, 0, kAtTextWord, "Nur Zahl (Wort)", "count only (word)"},\n', ''),
    ('DE name twice', '"Klein, Zahl darunter", "small, count below"', '"Klein, Zahl daneben", "small, count below"'),
    ('style 16 name English only', '"Nur Zahl (Pfeil)", "count only (arrow)"', '"count only (arrow)", "count only (arrow)"'),
    ('enum order changed', 'kAtTextTerse, kAtTextTerseOf, kAtTextWord', 'kAtTextTerseOf, kAtTextTerse, kAtTextWord'),
    ('no dispatch to DrawAtBare',
     '    if (st.text >= kAtTextBare) return DrawAtBare(st, ntDrawn, lit, held, why, frac, shown);', '    (void)0;'),
    ('box back (no NoBackground)', 'ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoBackground;',
     'ImGuiWindowFlags_NoSavedSettings;'),
    ('box colour pushed', '    if (ImGui::Begin("##TruAttractIcon", nullptr, flags)) {\n        ImDrawList *dl',
     '    ImGui::PushStyleColor(ImGuiCol_WindowBg, ImVec4(0, 0, 0, 0.5f));\n'
     '    if (ImGui::Begin("##TruAttractIcon", nullptr, flags)) {\n        ImDrawList *dl'),
    ('time next to the circle (10)', 'else Out(t, sizeof(t), "\\303\\227%ld", count);',
     'else Out(t, sizeof(t), "%d \\303\\227%ld", static_cast<int>(shown), count);'),
    ('limit next to the circle (badge)', '    case kAtTextBadge: if (!why[0]) Out(t, sizeof(t), "%ld", count); break;',
     '    case kAtTextBadge: if (!why[0]) Out(t, sizeof(t), "%ld/%.0f", count, static_cast<double>(g_naAlarm)); break;'),
    ('strike in every small style', 'const bool strike = held && st.strike;', 'const bool strike = held;'),
    ('AtSmallCircle strikes always', '    if (strike)\n        dl->AddLine(', '    if (true)\n        dl->AddLine('),
    ('no blink for the bare text', 'const ImU32 text = lit ? IM_COL32(255, 140, 40, 255)',
     'const ImU32 text = false ? IM_COL32(255, 140, 40, 255)'),
    ('no blink ground in the small circle', 'lit ? IM_COL32(242, 115, 26, 235)', 'false ? IM_COL32(242, 115, 26, 235)'),
    ('word text English only', 'de ? "Teaser %ld" : "teaser %ld", count', '"teaser %ld", count'),
    ('arrow as a glyph (not in the font)', '        else Out(t, sizeof(t), "%ld", count);\n        break;\n    default: break;',
     '        else Out(t, sizeof(t), "\\342\\206\\267%ld", count);\n        break;\n    default: break;'),
    ('DrawAtBare without End', '    }\n    ImGui::End();\n}\nvoid DrawAt(bool ntDrawn) {', '    }\n}\nvoid DrawAt(bool ntDrawn) {'),
    ('DrawAtBare writes the clock', 'const LONG count = held ? g_atSkipped : g_atStarted;',
     'const LONG count = held ? g_atSkipped : g_atStarted; *reinterpret_cast<float *>(g_naClock + 0x10) = 0.0f;'),
    ('badge branch gone', '} else if (st.text == kAtTextBadge) {', '} else if (false) {'),
    ('RunAt one digit only (0.22.40)',
     "    if (arg[0] >= '0' && arg[0] <= '9' && (!arg[1] || (arg[1] >= '0' && arg[1] <= '9' && !arg[2])))\n"
     "        v = arg[1] ? (arg[0] - '0') * 10 + (arg[1] - '0') : arg[0] - '0';",
     "    if (arg[0] >= '0' && arg[0] <= '9' && !arg[1]) v = arg[0] - '0';"),
    ('RunAt takes three digits', "&& arg[1] <= '9' && !arg[2])))", "&& arg[1] <= '9')))"),
    ('RunAt without the upper bound', '    if (v < 0 || v >= kAtStyleN) {\n        Out(o, n, "usage',
     '    if (v < 0) {\n        Out(o, n, "usage'),
    ('usage without 8 ..', '8 .. %d compact without a "', '8 .. %d without a "'),
    ('item text 0.22.40 0..7', '{"menu.attracticon", "value", "0.22.41 0..16 (', '{"menu.attracticon", "value", "0.22.40 0..7 ('),
    ('help without 8-16', '(2-7, knapp 8-16)|Off, text or circle to the teaser "\n                             "(2-7, compact 8-16)"}',
     '(2-7)|Off, text or circle to the teaser "\n                             "(2-7)"}'),
    ('QbValueCount 8 steps', ': val == kQvAtStyle ? kAtStyleN : 0;', ': val == kQvAtStyle ? 8 : 0;'),
    ('0.22.40 style 4 changed', '{1, 0, kAtTextInside, "Kreis, Text innen", "circle, text inside"},',
     '{1, 0, kAtTextBare, "Kreis, Text innen", "circle, text inside"},'),
]


def run_check(cpp, ini, switches):
    T.CPP = cpp
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        problems = T.check_02241(ini, switches)[0] + T.check_02240(ini, switches)[0] + T.check_02239(ini, switches)[0]
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
    for name, old, new in (('INI with AttractIcon=8', '\nAttractIcon=7\n', '\nAttractIcon=8\n'),
                           ('INI comment of 0.22.40', '; 7 the 0.22.39 look; no box: 8 / 9 small circle',
                            '; 7 the 0.22.39 look; 8 / 9 small circle')):
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
            ('switches row int:0..7', '| AttractIcon | int:0..16 |', '| AttractIcon | int:0..7 |'),
            ('switches row default 8', '(0-16) | live | 7 |', '(0-16) | live | 8 |'),
            ('switches row restart', '(0-16) | live | 7 |', '(0-16) | restart | 7 |'),
            ('switches row since 0.22.40', '13-16 terse | TruMenu 0.22.41', '13-16 terse | TruMenu 0.22.40'),
            ('switches row names (0-7)', 'Teaser-Anzeige im Hauptmenü (0-16)', 'Teaser-Anzeige im Hauptmenü (0-7)')):
        k += 1
        if sw_text.count(old) != 1:
            results.append(('%d %s' % (k, name), False, -1, ['mutation anchor found %d times' % sw_text.count(old)]))
            continue
        open(bad_sw, 'w', encoding='utf-8', newline='').write(sw_text.replace(old, new, 1))
        p = run_check(real_cpp, ini, bad_sw)
        results.append(('%d %s' % (k, name), len(p) > 0, len(p), p[:1]))
    # README / Set-TruMenu: a copy root with only these two files (the checks read them below T.ROOT)
    for name, rel, old, new in (
            ('README without TO TEST 0.22.41', ('src', 'asi', 'TruMenu', 'README.md'), '\n### TO TEST 0.22.41', '\n### TEST 0.22.41'),
            ('Set-TruMenu without the 0.22.40 hash', ('scripts', 'windows', 'Set-TruMenu.ps1'),
             '71374f9d167be140a6b124b71b55f6c24c603dfd3a0effbcf4e0cb8fc2b80f4b', '0' * 64)):
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
