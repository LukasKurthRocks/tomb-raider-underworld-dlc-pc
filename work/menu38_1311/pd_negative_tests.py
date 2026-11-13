"""PD (2026-11-13, TruMenu 0.22.38): negative tests for tools/trumenu_ini_check.py check_02238 (read-only on the
repository: every mutation goes into a copy below OUT_DIR, the repository files are only read).

Each case changes ONE thing the check must catch and expects at least one problem; case 0 (no change) expects none.
Prints one line per case and a summary; exit code 0 = every case behaved as expected.

Usage (from trudlcport): ../bin/pyt -t 600 work/menu38_1311/pd_negative_tests.py OUT_DIR
  OUT_DIR  scratch folder for the mutated copies (outside the repository)
"""
import os, sys, io, contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import trumenu_ini_check as T      # noqa: E402

CPP_CASES = [
    ('DeviceGlyphs default back to 0', '{"Input", "DeviceGlyphs", "1",', '{"Input", "DeviceGlyphs", "0",'),
    ('prefix rule without the dlc skip', "        if (*p == '_') s = p + 1;\n", ''),
    ('P5PrefixHidden with the old inline rule', '            k = P5PrefixKind(low);',
     '            if (!strncmp(low, "fx_", 3)) k = 2;'),
    ('edge queries after sb->Apply', '    PdEdgeIssue(dev, c, b, fw, fh);', '    // (moved)'),
    ('PdEdgeHow ignores Occlusion 0', 'if (!key || !g_p5Occl || g_pdQFailed) return 0;', 'if (!key || g_pdQFailed) return 0;'),
    ('DvLine numbers only lines in front',
     '    if (g_dvEdgeBase) g_dvEdgeKey = DvEdgeKeyOf(g_dvEdgeBase, g_dvEdgeSeg++ / g_dvEdgeRun);   // 0.22.38: edge number\n',
     ''),
    ('sphere circle not one key', '        g_dvEdgeRun = 24;', '        // g_dvEdgeRun'),
    ('DpFlush without the ALWAYS branch', '    if (g_dpAlways) {', '    if (false) {'),
    ('DpOnReset keeps the edge queries', '    PdEdgeRelease();                          // 0.22.38', '    // 0.22.38'),
    ('PdCornerDraw writes the game', '    if (!ReadDword(inst + 0x58, &intro)) return;\n    char text[16];',
     '    if (!ReadDword(inst + 0x58, &intro)) return;\n    WriteDword(inst + 0x58, 0);\n    char text[16];'),
    ('Lara-in outline pass without keys', '                DvEdgeBegin(t.inst, 0);', '                //'),
    ('no TriggerNearest filter', 'if (g_pdTrigNear > 0 && !t.laraIn) {', 'if (false) {'),
    ('item dbg.trigcorner missing', '    {"dbg.trigcorner", "bool",', '    {"dbg.trigcornerX", "bool",'),
    ('kOpts TriggerCornerId default 0', '{"Debug", "TriggerCornerId", "1",', '{"Debug", "TriggerCornerId", "0",'),
    ('PdCheck not called', '    PdCheck();                                // 0.22.38', '    // 0.22.38'),
]


def run_check(cpp, ini, switches):
    T.CPP = cpp
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        problems, _ = T.check_02238(ini, switches)
    return problems


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
        if old_n not in src_cpp:
            results.append(('%d %s' % (k, name), False, -1, ['mutation anchor not found']))
            continue
        path = os.path.join(out_dir, 'TruMenu_neg%d.cpp' % k)
        open(path, 'w', encoding='utf-8', newline='').write(src_cpp.replace(old_n, new_n, 1))
        p = run_check(path, ini, sw)
        results.append(('%d %s' % (k, name), len(p) > 0, len(p), p[:1]))
    k = len(CPP_CASES) + 1
    ini_text = open(ini, encoding='utf-8', newline='').read()
    bad_ini = os.path.join(out_dir, 'TruMenu_neg.ini')
    open(bad_ini, 'w', encoding='utf-8', newline='').write(ini_text.replace('\nDeviceGlyphs=1\n', '\nDeviceGlyphs=0\n'))
    p = run_check(real_cpp, bad_ini, sw)
    results.append(('%d INI with DeviceGlyphs=0' % k, len(p) > 0, len(p), p[:1]))
    k += 1
    sw_text = open(sw, encoding='utf-8', newline='').read()
    bad_sw = os.path.join(out_dir, 'TruMenu_neg.switches.txt')
    open(bad_sw, 'w', encoding='utf-8', newline='').write(
        sw_text.replace('(0 = all) | restart | 0 |', '(0 = all) | live | 0 |'))
    p = run_check(real_cpp, ini, bad_sw)
    results.append(('%d switches row TriggerNearest live' % k, len(p) > 0, len(p), p[:1]))
    k += 1
    open(bad_sw, 'w', encoding='utf-8', newline='').write(
        sw_text.replace('TruMenu | Input | DeviceGlyphs | bool', 'TruMenu | Input | DeviceGlyph | bool'))
    p = run_check(real_cpp, ini, bad_sw)
    results.append(('%d switches row DeviceGlyphs missing' % k, len(p) > 0, len(p), p[:1]))
    T.CPP = real_cpp
    # the Python copy of the prefix rule: positive / negative names
    k += 1
    want = {'dlc_fx_bloom': 2, 'dlc1_fx_ma_rb_pillory': 2, 'fx_haze': 2, 'co_light_rig': 1, 'co_fx_hel_saved': 1,
            'dlc2_co_test': 1, 'co_rock_b': 3, 'fx_saving_grab_prompt': 3, 'dlc_fx_x_grab_prompt': 3, 'dlc_checkpoint': 3,
            'dlc1_uo_sewer_gate': 3, 'rainfx_mex': 3, 'dlcx_fx_y': 3}
    wrong = ['%s -> %d' % (n, T.pd_prefix_kind(n)) for n, v in want.items() if T.pd_prefix_kind(n) != v]
    results.append(('%d prefix rule on 13 names' % k, not wrong, len(wrong), wrong[:1]))
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
