"""W3 (2026-11-14, TruMenu 0.22.42 debug view after the test evening 13.11.): negative tests for tools/trumenu_ini_check.py
check_02242 (with check_02237 / check_02239 / check_02241 and the switches check, which run on the same sources) -
read-only on the repository: every mutation goes into a copy below OUT_DIR, the repository files are only read.

Each case changes ONE thing (one or more text replacements) the checks must catch and expects at least one problem;
case 0 (no change) expects none. Prints one line per case and a summary; exit code 0 = every case behaved as expected.

Usage (from trudlcport): ../bin/pyt -t 600 work/w3_1411/w3_negative_tests.py OUT_DIR
  OUT_DIR  scratch folder for the mutated copies (outside the repository)
"""
import os, sys, io, shutil, contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import trumenu_ini_check as T      # noqa: E402

R1 = '    if (g_lblOn) DrawLabels();                   // 0.13 Thrall-Labels (foreground draw list)\n'
R2 = '    // labels and join a label of the same instance instead of covering it\n    if (g_ubOn) DrawUberLabels();\n'
CPP_CASES = [
    ('kVersion not 0.22.42', [('"TruMenu 0.22.42 (W3 debug view', '"TruMenu 0.22.42 (W4 debug view')]),
    ('byte check loop byte changed', [('{0x004a12c6, "a2dc39a000"},', '{0x004a12c6, "a2dc39a001"},')]),
    ('byte check row dropped', [('    {0x0077bbe0, "a0dae8fa00 c3"},', '')]),
    ('RoomOnly without the W3 rule', [('return unit[0] && !DvIsLaraUnit(unit) && W3RoomDrops(inst, unit);',
                                       'return unit[0] && !DvIsLaraUnit(unit);')]),
    ('own stream unit ignored', [('const int verdict = sameSid ? 1 : nearLara ? 2 : 0;', 'const int verdict = nearLara ? 2 : 0;')]),
    ('RoomNear ignored', [('g_w3RoomNear > 0.0f && dist >= 0.0f && dist <= g_w3RoomNear', 'false')]),
    ('drop without a log line', [('W3RoomLog(inst, unit, haveSid, sid, dist, verdict);', '(void)sid;')]),
    ('log without rate limit', [('if (g_w3LogLines >= 20)', 'if (g_w3LogLines >= 2000)')]),
    ('log every frame (no once)', [('if (g_w3Seen[i].verdict == verdict) return;', '(void)0;')]),
    ('log without the +0xe0 unit', [("intro unit %s, own stream unit (+0xe0) %s, Lara's unit %s",
                                     "intro unit %s, %s, Lara's unit %s")]),
    ('occlusion without the near rule', [('if (W3OcclNear(key, p)) return 1.0f;', '(void)0;')]),
    ('Lara fades again', [('if (key == player) { ++g_w3NearKept; return true; }', 'if (false) { ++g_w3NearKept; return true; }')]),
    ('names test point back at +60', [('const float pa[3] = {d.pos[0], d.pos[1], d.pos[2] + kW3OcclLift};',
                                       'const float pa[3] = {d.pos[0], d.pos[1], d.pos[2] + 60.0f};')]),
    ('uber test point back at +60', [('const float pa[3] = {c.pos[0], c.pos[1], c.pos[2] + kW3OcclLift};',
                                      'const float pa[3] = {c.pos[0], c.pos[1], c.pos[2] + 60.0f};')]),
    ('lift 0.6 m', [('const float kW3OcclLift = 100.0f;', 'const float kW3OcclLift = 60.0f;')]),
    ('DrawDebugView resets the rects', [('    g_dvTagN = 0;\n    W3LabFrame();', '    g_dvTagN = g_dvRectN = 0;\n    W3LabFrame();')]),
    ('uber labels before the debug view', [(R1, R1 + '    if (g_ubOn) DrawUberLabels();\n'),
                                           (R2, '    // labels and join a label of the same instance instead of covering it\n')]),
    ('uber labels with LabelDraw', [('const int how = W3UberDraw(dl, at, line1, line2,', 'const int how = 0; LabelDraw(dl, at, line1, line2,')]),
    ('no same-object merge', [('dx * dx + dy * dy + dz * dz <= 2500.0f', 'dx * dx + dy * dy + dz * dz <= 0.0f')]),
    ('uber never joins a label', [('const int had = W3LabFind(inst);', 'const int had = -1;')]),
    ('no stacking', [('for (int k = 0; k <= g_w3Stack; ++k) {', 'for (int k = 0; k <= 0; ++k) {')]),
    ('no cell cap', [('g_w3Cell[cy][cx] >= g_w3CellMax', 'false')]),
    ('frame without rect reset', [('    g_dvRectN = 0;\n    g_w3LabN = 0;', '    g_w3LabN = 0;')]),
    ('names label twice', [('if (W3LabFind(d.inst) >= 0) { ++twice; continue; }', '(void)twice;')]),
    ('M20Label old nudge', [('if (W3LabFind(m.inst) >= 0 || !W3LabPlace(&r, at, h + 4.0f)) return false;',
                             'if (!DvRectFree(r)) return false;')]),
    ('uber takes empty jars', [('if (take && W3EmptyPot(inst)) take = false;', '(void)0;')]),
    ('names take empty jars', [('if (hit && W3EmptyPot(inst)) { ++pots; hit = false; }', '(void)pots;')]),
    ('collect layer takes empty pots', [('if (ck == kCoPot && W3EmptyPot(inst)) {', 'if (false) {')]),
    ('collected reward jar kept', [('k == 1 || !CoRewardIndex(inst, &script) || P5Collected(inst)',
                                    'k == 1 || !CoRewardIndex(inst, &script)')]),
    ('teaser icon in the credits again', [('&& NaFrontEnd() && W3AtMainMenu(); }', '&& NaFrontEnd(); }')]),
    ('movie test off', [('const bool movie = handle && !loop;', 'const bool movie = false;')]),
    ('fallback hides the icon', [('if (!g_w3AtOk) return true;', 'if (!g_w3AtOk) return false;')]),
    ('W3AtMainMenu writes the game', [('const bool movie = handle && !loop;',
                                       'const bool movie = handle && !loop; WriteByte(kW3BinkLoop, 1);')]),
    ('front-end address changed', [('kW3FeState = 0x00fae8da,', 'kW3FeState = 0x00fae8db,')]),
    ('code default metres 0', [('int g_p5Room = 1, g_p5Metres = 1,', 'int g_p5Room = 1, g_p5Metres = 0,')]),
    ('kOpts DistMetres 0', [('{"Debug", "DistMetres", "1",', '{"Debug", "DistMetres", "0",')]),
    ('kOpts RoomNear 2000', [('{"Debug", "RoomNear", "3000",', '{"Debug", "RoomNear", "2000",')]),
    ('item dbg.emptypots renamed', [('{"dbg.emptypots", "bool",', '{"dbg.emptypotz", "bool",')]),
    ('bar row empty jars gone', [('"dbg.emptypots", "", kQbBool, -1, kQcNone, 0, kQbWhite, 0}', '"dbg.emptypots", "", kQbInfo, -1, kQcNone, 0, kQbWhite, 0}')]),
    ('W3Check not called', [('    W3Check();                                // 0.22.42', '    (void)0;                                  // 0.22.42')]),
    ('W3ReadOptions not called', [('    W3ReadOptions(ini);                      // 0.22.42', '    (void)ini;                               // 0.22.42')]),
    ('menu controls gone', [('        W3MenuControls(o, sizeof(o));', '        (void)0;')]),
]


def run_check(cpp, ini, switches):
    T.CPP = cpp
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        problems = T.check_02242(ini, switches)[0] + T.check_02241(ini, switches)[0] + T.check_02239(ini, switches)[0]
        problems += T.check_02237(ini, switches)[0]
        problems += T.check_switches(switches)[0]   # (problems, summary, rows)
    return problems


def mutate(text, pairs, crlf):
    for old, new in pairs:
        old_n, new_n = (old.replace('\n', '\r\n'), new.replace('\n', '\r\n')) if crlf else (old, new)
        if text.count(old_n) != 1: return None, 'mutation anchor found %d times: %s' % (text.count(old_n), old[:50])
        text = text.replace(old_n, new_n, 1)
    return text, ''


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    real_cpp, real_root = T.CPP, T.ROOT
    src_cpp = open(real_cpp, encoding='utf-8', newline='').read()
    ini, sw = T.INI, T.SWITCHES
    results = []
    p = run_check(real_cpp, ini, sw)
    results.append(('0 unchanged sources', len(p) == 0, len(p), p[:1]))
    k = 0
    for name, pairs in CPP_CASES:
        k += 1
        text, why = mutate(src_cpp, pairs, True)   # TruMenu.cpp has CRLF line ends
        if text is None:
            results.append(('%d %s' % (k, name), False, -1, [why]))
            continue
        path = os.path.join(out_dir, 'TruMenu_neg%d.cpp' % k)
        open(path, 'w', encoding='utf-8', newline='').write(text)
        p = run_check(path, ini, sw)
        results.append(('%d %s' % (k, name), len(p) > 0, len(p), p[:1]))
    T.CPP = real_cpp
    ini_text = open(ini, encoding='utf-8', newline='').read()
    bad_ini = os.path.join(out_dir, 'TruMenu_neg.ini')
    for name, old, new in (('INI DistMetres=0', '\nDistMetres=1\n', '\nDistMetres=0\n'),
                           ('INI HideEmptyPots=0', '\nHideEmptyPots=1\n', '\nHideEmptyPots=0\n'),
                           ('INI without OcclNear', '\nOcclNear=600\n', '\n')):
        k += 1
        text, why = mutate(ini_text, [(old, new)], False)
        if text is None:
            results.append(('%d %s' % (k, name), False, -1, [why]))
            continue
        open(bad_ini, 'w', encoding='utf-8', newline='').write(text)
        p = run_check(real_cpp, bad_ini, sw)
        results.append(('%d %s' % (k, name), len(p) > 0, len(p), p[:1]))
    sw_text = open(sw, encoding='utf-8', newline='').read()
    bad_sw = os.path.join(out_dir, 'TruMenu_neg.switches.txt')
    for name, old, new in (
            ('switches RoomNear live', '(0 = unit only) | restart | 3000 |', '(0 = unit only) | live | 3000 |'),
            ('switches HideEmptyPots default 0', '| Hide empty jars | restart | 1 |', '| Hide empty jars | restart | 0 |'),
            ('switches DistMetres default 0', '| Distance in metres | restart | 1 |', '| Distance in metres | restart | 0 |'),
            ('switches DistMetres since 0.22.37', '(default since 0.22.42) | TruMenu 0.22.42', '(default since 0.22.42) | TruMenu 0.22.37'),
            ('switches LabelCellMax renamed', '| LabelCellMax | int:0..40:1 |', '| LabelCellMx | int:0..40:1 |'),
            ('switches OcclNear since 0.22.41', '(0 = off) | TruMenu 0.22.42', '(0 = off) | TruMenu 0.22.41')):
        k += 1
        text, why = mutate(sw_text, [(old, new)], False)
        if text is None:
            results.append(('%d %s' % (k, name), False, -1, [why]))
            continue
        open(bad_sw, 'w', encoding='utf-8', newline='').write(text)
        p = run_check(real_cpp, ini, bad_sw)
        results.append(('%d %s' % (k, name), len(p) > 0, len(p), p[:1]))
    # README / Set-TruMenu / the precheck list: a copy root with these files (the checks read them below T.ROOT)
    files = (('src', 'asi', 'TruMenu', 'README.md'), ('scripts', 'windows', 'Set-TruMenu.ps1'),
             ('src', 'asi', 'TruTrace', 'TruTrace.cpp'), ('src', 'asi', 'TruTrace', 'TruTrace.ini'),
             ('work', 'p5_menu_1311', 'precheck_02237.txt'), ('work', 'p5_menu_1311', 'precheck_trace032.txt'),
             ('work', 'b_nav_1211', 'q105_room_names.txt'), ('work', 'w3_1411', 'precheck_02242.txt'))
    for name, rel, old, new in (
            ('README without TO TEST 0.22.42', files[0], '\n### TO TEST 0.22.42', '\n### TEST 0.22.42'),
            ('Set-TruMenu without the 0.22.41 hash', files[1], T.W3_HASH_02241, '0' * 64),
            ('precheck list with another byte', files[7], '0x004a12c6 a2dc39a000', '0x004a12c6 a2dc39a0ff')):
        k += 1
        root = os.path.join(out_dir, 'root%d' % k)
        for r in files:
            os.makedirs(os.path.join(root, *r[:-1]), exist_ok=True)
            shutil.copyfile(os.path.join(real_root, *r), os.path.join(root, *r))
        target = os.path.join(root, *rel)
        text, why = mutate(open(target, encoding='utf-8', newline='').read(), [(old, new)], False)
        if text is None:
            results.append(('%d %s' % (k, name), False, -1, [why]))
            continue
        open(target, 'w', encoding='utf-8', newline='').write(text)
        T.ROOT = root
        saved = T.W3_CHECKS_02242, T.P5_CHECKS_02237, T.P5_ROOMS_02237
        T.W3_CHECKS_02242 = os.path.join(root, *files[7])
        T.P5_CHECKS_02237 = os.path.join(root, *files[4])
        T.P5_ROOMS_02237 = os.path.join(root, *files[6])
        try:
            p = run_check(real_cpp, ini, sw)
        finally:
            T.ROOT = real_root
            T.W3_CHECKS_02242, T.P5_CHECKS_02237, T.P5_ROOMS_02237 = saved
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
