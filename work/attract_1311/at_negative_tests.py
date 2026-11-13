"""Q126 (2026-11-13, TruMenu 0.22.39 attract icon): negative tests for tools/trumenu_ini_check.py check_02239 (and the
switches check for the two live rows) - read-only on the repository: every mutation goes into a copy below OUT_DIR, the
repository files are only read.

Each case changes ONE thing the check must catch and expects at least one problem; case 0 (no change) expects none.
Prints one line per case and a summary; exit code 0 = every case behaved as expected.

Usage (from trudlcport): ../bin/pyt -t 600 work/attract_1311/at_negative_tests.py OUT_DIR
  OUT_DIR  scratch folder for the mutated copies (outside the repository)
"""
import os, sys, io, contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import trumenu_ini_check as T      # noqa: E402

CPP_CASES = [
    ('kOpts AttractIcon default 0', '{"Menu", "AttractIcon", "1",', '{"Menu", "AttractIcon", "0",'),
    ('kOpts AttractIconText default 0', '{"Menu", "AttractIconText", "1",', '{"Menu", "AttractIconText", "0",'),
    ('ReadOptions does not read AttractIcon',
     'InterlockedExchange(&g_atWant, OptInt(ini, "Menu", "AttractIcon") != 0 ? 1 : 0);', '(void)0;'),
    ('NtPost without AtOnLimit', '    if (flash) AtOnLimit(held);', '    //'),
    ('NaTick slot not for the icon', 'want = hold || g_ntWant != 0 || g_atWant != 0;', 'want = hold || g_ntWant != 0;'),
    ('NaTick without AtTick', '    AtTick();                                // 0.22.39', '    //'),
    ('AtTick reads the INI every poll', '    if (g_atReadTick && now - g_atReadTick < 1000) return;\n', ''),
    ('AtReadSwitch keeps the old value', '    if (on != g_atIniOn) {', '    if (false) {'),
    ('icon also drawn in levels', 'bool AtWantsDraw() { return g_atWant != 0 && NaFrontEnd(); }',
     'bool AtWantsDraw() { return g_atWant != 0; }'),
    ('Render does not draw the icon', '    if (atDraw) DrawAt(ntDraw);', '    //'),
    ('Render returns early without the icon', '!flightHint && !atDraw && !cnBadge && !ntDraw)', '!flightHint && !cnBadge && !ntDraw)'),
    ('own counting instead of the shadow modulo', 'g_naRepeat ? fmodf(e, alarm)', 'g_naRepeat ? e'),
    ('fraction from an own constant limit', '    const float alarm = g_naAlarm;\n    if (!g_naClock', '    const float alarm = 40.0f;\n    if (!g_naClock'),
    ('AtOnLimit writes the clock', '    g_atBlinkTick = GetTickCount() | 1;',
     '    g_atBlinkTick = GetTickCount() | 1;\n    *reinterpret_cast<float *>(g_naClock + 0x10) = 0.0f;'),
    ('AtOnLimit without the counts', '    const LONG n = InterlockedIncrement(held ? &g_atSkipped : &g_atStarted);',
     '    const LONG n = 0;'),
    ('DrawAt text only English', 'de ? "Teaser: noch keine Uhr" : "Teaser: no clock yet"', '"Teaser: no clock yet"'),
    ('DrawAt without the blink', 'const bool blinking = blinkAt && now - blinkAt < kAtBlinkMs;', 'const bool blinking = false;'),
    ('DrawAt not below the timer box', 'g_ntPos == 2 && g_ntBoxH > 0.0f', 'false'),
    ('DrawAt fills one concave sector', 'AtSector(dl, c, r, a, a + kPi * 0.5f < a1 ? a + kPi * 0.5f : a1, fill);',
     'AtSector(dl, c, r, a0, a1, fill);'),
    ('RunAt flips without an argument', '    if (!arg || !arg[0]) { ValAt(o, n); return true; }   // no argument = report, never a flip',
     '    if (!arg || !arg[0]) arg = g_atWant ? "0" : "1";'),
    ('RunAt does not keep the INI', '    IniKeep("Menu", "AttractIcon", on ? "1" : "0");', '    (void)0;'),
    ('RadialWhy does not grey the icon', '    if (!_stricmp(id, "menu.attracticon")) return NaWhy();', '    //'),
    ('item menu.attracticon missing', '    {"menu.attracticon", "bool",', '    {"menu.attracticonX", "bool",'),
    ('bar row missing', '"menu.attracticon", "", kQbBool', '"menu.attracticonX", "", kQbBool'),
    ('help line over 60 characters', '+ Z\\303\\244hler|Circle', '+ Z\\303\\244hler und noch viel mehr Text dahinter|Circle'),
    ('kVersion not 0.22.39', 'const char *const kVersion = "TruMenu 0.22.39 (Q126', 'const char *const kVersion = "TruMenu 0.22.39 (X126'),
    ('a 14th byte check row', '    {0x005d56e0, "a160ede700 83f806 7408 83f80a 7403 32c0 c3 b001 c3"},',
     '    {0x005d56e0, "a160ede700 83f806 7408 83f80a 7403 32c0 c3 b001 c3"},\n    {0x00845860, "403b4a00"},'),
    ('DrawNt keeps no box height', '        g_ntBoxH = ImGui::GetWindowSize().y;', '        //'),
]


def run_check(cpp, ini, switches):
    T.CPP = cpp
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        problems, _ = T.check_02239(ini, switches)
        sw_problems = T.check_switches(switches)[0]   # (problems, summary, rows)
    return problems + sw_problems


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    real_cpp = T.CPP
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
    k = len(CPP_CASES) + 1
    ini_text = open(ini, encoding='utf-8', newline='').read()
    bad_ini = os.path.join(out_dir, 'TruMenu_neg.ini')
    open(bad_ini, 'w', encoding='utf-8', newline='').write(ini_text.replace('\nAttractIcon=1\n', '\nAttractIcon=0\n'))
    p = run_check(real_cpp, bad_ini, sw)
    results.append(('%d INI with AttractIcon=0' % k, len(p) > 0, len(p), p[:1]))
    sw_text = open(sw, encoding='utf-8', newline='').read()
    bad_sw = os.path.join(out_dir, 'TruMenu_neg.switches.txt')
    for name, old, new in (
            ('switches row AttractIcon restart', '(circle) | live | 1 |', '(circle) | restart | 1 |'),
            ('switches row AttractIconText missing', 'TruMenu | Menu | AttractIconText | bool', 'TruMenu | Menu | AttractIconTxt | bool'),
            ('switches row AttractIcon default 0', '(circle) | live | 1 |', '(circle) | live | 0 |'),
            ('switches group tmhauptmenue missing', 'group | tmhauptmenue |', 'group | tmhaupt |')):
        k += 1
        if sw_text.count(old) != 1:
            results.append(('%d %s' % (k, name), False, -1, ['mutation anchor found %d times' % sw_text.count(old)]))
            continue
        open(bad_sw, 'w', encoding='utf-8', newline='').write(sw_text.replace(old, new, 1))
        p = run_check(real_cpp, ini, bad_sw)
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
