"""W2 (2026-11-14): one-off restructure of kQbTests in src/asi/TruMenu/TruMenu.cpp (TruMenu 0.22.44).

New order: block "TG 1411" (work/w2_1411/tg_block.txt, test guide packages A - F) first, then the groups that stay in use
(Teleport, Arena 1, Zwischensequenz), then the closed group "Archiv / Alt" with the old rows moved unchanged: the TP Q90
block (its group tp_q90 becomes a sub-group), Teststellen, Licht (Diagnose), Diagnose, hall02-Zaehler (each a sub-group).
Nothing is deleted: the script checks that every old row line is still there exactly once.

Usage (from the repository root):
  ../bin/pyt -t 120 work/w2_1411/w2_tests_page.py check    print the plan, write nothing
  ../bin/pyt -t 120 work/w2_1411/w2_tests_page.py write    rewrite TruMenu.cpp (CRLF kept)
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
CPP = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.cpp')
TG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tg_block.txt')

ARCHIVE_HEAD = [
    '    // 0.22.44 (W2, owner 2026-11-13 "Seite Tests aufraeumen: ueberholte Schalter"): the rows of earlier test rounds,',
    '    // moved here unchanged (nothing deleted) - each old top-level group is a sub-group now; closed at the start',
    '    {"Archiv / Alt", "Archive / old", "-", "ts_archive", kQbGroup, -1, kQcNone, 0, kQbGrey, 0},',
    '    {"Fr\\303\\274here Testrunden - nichts gel\\303\\266scht", "Earlier test rounds - nothing deleted", "-", "", kQbNote, -1,',
    '     kQcNone, 0, kQbGrey, 0},',
]
# (anchor of the section's first line, replacements inside the section)
SECTIONS = [
    ('teleport', '    {"Teleport", "Teleport", "-", "ts_teleport", kQbGroup', []),
    ('spots', '    // 0.21.9 test spots', [('"ts_spots", kQbGroup, -1, kQcNone, 0, kQbRed, 0}',
                                            '"ts_spots", kQbGroup, -1, kQcNone, 0, kQbRed, kQfSub}')]),
    ('arena', '    // 0.22.26 test arena', []),
    ('cine', '    // 0.22 cutscene pause', []),
    ('light', '    // 0.22.16: the light rows', [('"light_diag", kQbGroup, -1, kQcNone, 0, kQbBlue, 0}',
                                                  '"light_diag", kQbGroup, -1, kQcNone, 0, kQbBlue, kQfSub}')]),
    ('diag', '    // 0.22.9 enemy diagnosis', [('"ts_diag", kQbGroup, -1, kQcNone, 0, kQbBlue, 0}',
                                                '"ts_diag", kQbGroup, -1, kQcNone, 0, kQbBlue, kQfSub}')]),
    ('hall02', '    // 0.21.4 hall02 counter', [('"ts_hall02", kQbGroup, -1, kQcNone, 0, kQbRed, 0}',
                                                 '"ts_hall02", kQbGroup, -1, kQcNone, 0, kQbRed, kQfSub}')]),
]
TP_FIX = [('{"Testpakete 11.11. (Q90)", "Test packages 11.11. (Q90)", "-", "tp_q90", kQbGroup, -1, kQcNone, 0, kQbClaude, kQfTp},',
           '{"Alte Testpakete 11.11. (Q90)", "Old test packages 11.11. (Q90)", "-", "tp_q90", kQbGroup, -1, kQcNone, 0,\r\n'
           '     kQbClaude, kQfSub | kQfTp},')]


def main(mode):
    raw = open(CPP, 'rb').read()
    text = raw.decode('ascii')
    start = text.index('const QbRow kQbTests[] = {\r\n') + len('const QbRow kQbTests[] = {\r\n')
    end = text.index('\r\n};', start) + 2
    body = text[start:end]
    if '// ---- TG 1411 begin' in body:
        print('already restructured'); return 1
    a = body.index('    // ---- TP Q90 begin')
    b = body.index('    // ---- TP Q90 end\r\n') + len('    // ---- TP Q90 end\r\n')
    if a != 0: print('TP block is not the first part'); return 1
    tp = body[a:b]
    rest = body[b:]
    cuts = []
    for name, anchor, _ in SECTIONS:
        i = rest.index(anchor)
        if rest.count(anchor) != 1: print('anchor twice: %s' % name); return 1
        cuts.append(i)
    if cuts != sorted(cuts) or cuts[0] != 0: print('sections not in the expected order: %s' % cuts); return 1
    parts = {}
    for k, (name, anchor, reps) in enumerate(SECTIONS):
        seg = rest[cuts[k]:cuts[k + 1] if k + 1 < len(cuts) else len(rest)]
        for old, new in reps:
            if seg.count(old) != 1: print('%s: replacement source not found once: %s' % (name, old)); return 1
            seg = seg.replace(old, new)
        parts[name] = seg
    for old, new in TP_FIX:
        if tp.count(old) != 1: print('TP group row not found once'); return 1
        tp = tp.replace(old, new)
    tg = open(TG, 'rb').read().decode('ascii').replace('\r\n', '\n').replace('\n', '\r\n')
    new_body = (tg + parts['teleport'] + parts['arena'] + parts['cine'] + '\r\n'.join(ARCHIVE_HEAD) + '\r\n' + tp +
                parts['spots'] + parts['light'] + parts['diag'] + parts['hall02'])
    # nothing lost: every old row start line (and every comment line) is still there once
    old_lines = [l for l in body.split('\r\n') if l.strip()]
    new_lines = new_body.split('\r\n')
    missing = []
    for l in old_lines:
        if l in new_lines: continue
        if any(l == o for o, n in [(o, n) for _, _, r in SECTIONS for o, n in r]): continue
        if any(o in l for _, _, r in SECTIONS for o, _ in r) or any(o in l for o, _ in TP_FIX): continue
        missing.append(l)
    if missing:
        print('lines lost:'); [print('  ' + m) for m in missing]; return 1
    print('TG block %d lines, teleport %d, arena %d, cine %d, archive: TP %d, spots %d, light %d, diag %d, hall02 %d' % (
        tg.count('\r\n'), parts['teleport'].count('\r\n'), parts['arena'].count('\r\n'), parts['cine'].count('\r\n'),
        tp.count('\r\n'), parts['spots'].count('\r\n'), parts['light'].count('\r\n'), parts['diag'].count('\r\n'),
        parts['hall02'].count('\r\n')))
    print('old non-empty lines %d, new lines %d' % (len(old_lines), len(new_lines)))
    if mode == 'write':
        out = text[:start] + new_body + text[end:]
        open(CPP, 'wb').write(out.encode('ascii'))
        print('written %s' % CPP)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'check'))
