"""P5 (2026-11-13, TruMenu 0.22.37): negative tests for tools/trumenu_ini_check.py check_02237 and for the Paket R proof
of the chapter generator work/b_nav_1211/q105_order_table.py (read-only on the repository: every mutation goes into a
copy below OUT_DIR, the repository files are only read).

Each case changes ONE thing that the check / the proof must catch and expects at least one problem; case 0 (no change)
expects none. Prints one line per case and a summary; exit code 0 = every case behaved as expected.

Usage (from trudlcport): ../bin/pyt -t 600 work/p5_menu_1311/p5_negative_tests.py OUT_DIR PORTALS INTROS
  OUT_DIR  scratch folder for the mutated copies (outside the repository)
  PORTALS / INTROS  the generator inputs of group B (q105_portals.txt, q105_cp_intros.txt in the scratch tree)
"""
import os, sys, io, contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'work', 'b_nav_1211'))
import trumenu_ini_check as T      # noqa: E402
import q105_order_table as G       # noqa: E402

CPP_CASES = [
    ('kP5Checks row changed', '{0x005db6df, "8b3d38f3e700 85ff"},', '{0x005db6df, "8b3d38f3e700 85fe"},'),
    ('return visit CP 76 moved back', '{"Base game l1", "l1_kraken_room", false, "76 75",',
     '{"Base game l1", "l1_kraken_room", false, "75",'),
    ('LabelFilter without the co_ / fx_ rule', '    if (P5PrefixHidden(inst)) return 4;\n', ''),
    ('P5Collected writes the game', '    if (!ReadDword(data + 0x3ed90 + (ri >> 5) * 4, &word)) return 0;\n',
     '    if (!ReadDword(data + 0x3ed90 + (ri >> 5) * 4, &word)) return 0;\n    WriteDword(data, 0);\n'),
    ('QlTick gate before the pending check',
     '    if (LevelChangePending(why, sizeof(why))) { QlForget(why); return; }\n    static DWORD last = 0;',
     '    static DWORD last = 0;'),
    ('occlusion queries after sb->Apply', '    P5OcclIssue(dev, c, b);', '    // (moved)'),
    ('kOpts Occlusion default 2', '{"Debug", "Occlusion", "1",', '{"Debug", "Occlusion", "2",'),
    ('room name row changed', '{"l1_kraken_room", "Kraken-Raum", "Kraken room"},', '{"l1_kraken_room", "Krakenraum", "Kraken room"},'),
    ('QlForget without the tracker id test', 'static_cast<SHORT>(id) == q.id && ReadWord(e + 0xe, &status) && status;\n        const bool ok',
     'true;\n        const bool ok'),
]


def run_check(cpp, ini, switches):
    T.CPP = cpp
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        problems, _ = T.check_02237(ini, switches)
    return problems


def main(out_dir, portals, intros):
    os.makedirs(out_dir, exist_ok=True)
    real_cpp = T.CPP
    src_cpp = open(real_cpp, encoding='utf-8').read()
    ini, sw = T.INI, T.SWITCHES
    results = []
    p = run_check(real_cpp, ini, sw)
    results.append(('0 unchanged sources', len(p) == 0, len(p), p[:1]))
    for k, (name, old, new) in enumerate(CPP_CASES, 1):
        if old not in src_cpp:
            results.append(('%d %s' % (k, name), False, -1, ['mutation anchor not found']))
            continue
        path = os.path.join(out_dir, 'TruMenu_neg%d.cpp' % k)
        open(path, 'w', encoding='utf-8', newline='').write(src_cpp.replace(old, new, 1))
        p = run_check(path, ini, sw)
        results.append(('%d %s' % (k, name), len(p) > 0, len(p), p[:1]))
    # an INI without a new key / a switches row with the wrong "when"
    k = len(CPP_CASES) + 1
    ini_text = open(ini, encoding='utf-8').read()
    bad_ini = os.path.join(out_dir, 'TruMenu_neg.ini')
    open(bad_ini, 'w', encoding='utf-8', newline='').write(ini_text.replace('\nHideFx=1\n', '\n'))
    p = run_check(real_cpp, bad_ini, sw)
    results.append(('%d INI without HideFx' % k, len(p) > 0, len(p), p[:1]))
    k += 1
    sw_text = open(sw, encoding='utf-8').read()
    bad_sw = os.path.join(out_dir, 'TruMenu_neg.switches.txt')
    open(bad_sw, 'w', encoding='utf-8', newline='').write(
        sw_text.replace('TruMenu | Debug | DrawDistance | int:0..50000:1000 | Sichtweite (0 = aus) | Draw distance (0 = off) | restart',
                        'TruMenu | Debug | DrawDistance | int:0..50000:1000 | Sichtweite (0 = aus) | Draw distance (0 = off) | live'))
    p = run_check(real_cpp, ini, bad_sw)
    results.append(('%d switches row DrawDistance live' % k, len(p) > 0, len(p), p[:1]))
    T.CPP = real_cpp
    # generator: an intro the Paket R rows name is missing from the unit -> PROBLEM
    k += 1
    calls = os.path.join(ROOT, 'work', 'b_nav_1211', 'q105_chapter_calls.txt')
    cp_order = os.path.join(ROOT, 'work', 'q113_chain_1211', 'q113_cp_order.txt')
    lines = open(intros, encoding='utf-8', errors='replace').read().split('\n')
    cut, unit = [], None
    for ln in lines:
        if ln.startswith('== '): unit = ln[3:].split(':')[0]
        if unit == 'l1_baldrs_tomb' and ln.strip().startswith('intro') and ln.split()[1] == '160': continue
        cut.append(ln)
    bad_intros = os.path.join(out_dir, 'q105_cp_intros_no160.txt')
    open(bad_intros, 'w', encoding='utf-8', newline='\n').write('\n'.join(cut))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = G.main(portals, bad_intros, calls, os.path.join(out_dir, 'rows.txt'), os.path.join(out_dir, 'rows.md'), cp_order,
                    os.path.join(out_dir, 'rooms.txt'))
    msg = [l for l in out.getvalue().splitlines() if l.startswith('PROBLEM')]
    results.append(('%d generator: tomb intro 160 missing' % k, rc == 1 and any('160' in m for m in msg), len(msg), msg[:1]))
    k += 1
    with contextlib.redirect_stdout(io.StringIO()):   # and the real inputs: no problem, the committed outputs again
        rc = G.main(portals, intros, calls, os.path.join(out_dir, 'rows_ok.txt'), os.path.join(out_dir, 'rows_ok.md'),
                    cp_order, os.path.join(out_dir, 'rooms_ok.txt'))
    same = open(os.path.join(out_dir, 'rows_ok.txt'), encoding='utf-8').read() == \
        open(os.path.join(ROOT, 'work', 'b_nav_1211', 'q105_chaporder_rows.txt'), encoding='utf-8').read().replace('\r\n', '\n')
    results.append(('%d generator: real inputs = committed rows' % k, rc == 0 and same, 0 if rc == 0 else 1, []))
    bad = 0
    for name, ok, n, first in results:
        print('%-4s %-45s problems %3d %s' % ('ok' if ok else 'FAIL', name, n, ('- ' + first[0][:110]) if first else ''))
        bad += 0 if ok else 1
    print('%d cases, %d as expected, %d not' % (len(results), len(results) - bad, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(*sys.argv[1:4]))
