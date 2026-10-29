"""Which sections did the Xbox title update change in a base-game DRM, and does the PC version have those changes?
(read-only) The PC game is built from the retail state; DLC support came with the Xbox title update (TU), e.g. the
DLC mission screen (docs/DLC_MENU.md) and the loading screen (finding 42).

Per section (type, id) of the TU version: same as Xbox retail / changed by the TU / new in the TU; for changed and new
sections the PC section of the mapped id with its size, and DLC-related strings of the TU section.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/tu_script_changes.py [NAME] [--types 8]
  NAME default generalbank.drm; --types: comma-separated section types to list (default 8 = scripts)
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtp_word_classes as C

BS = chr(92)
HINT = re.compile(rb'[\x20-\x7e]*(?:dlc|doppel|shadow|costume|load|level id)[\x20-\x7e]*', re.I)


def main(argv):
    types = {8}
    if '--types' in argv: k = argv.index('--types'); types = {int(x) for x in argv[k + 1].split(',')}; del argv[k:k + 2]
    name = argv[0] if argv else 'generalbank.drm'
    import dlc_generic as DG
    ids = DG.DlcIds()
    tu = {(s['type'], s['id']): s['data'] for s in C.find([C.BASE[0]], 'be', 'xenon-w' + BS + name)}
    rt = {(s['type'], s['id']): s['data'] for s in C.find(C.BASE[1:], 'be', 'xenon-w' + BS + name)}
    pc = {(s['type'], s['id']): s['data'] for s in C.find(C.PC, 'le', 'pc-w' + BS + name)}
    cls = collections.Counter()
    rows = []
    for k, d in tu.items():
        c = 'same' if rt.get(k) == d else 'new' if k not in rt else 'changed'
        cls[(k[0], c)] += 1
        if c != 'same' and k[0] in types:
            p = pc.get((k[0], ids(k[0], k[1])))
            hints = sorted({m.group().decode('ascii')[:60] for m in HINT.finditer(d or b'')})[:4]
            rows.append((k, c, len(rt.get(k) or b''), len(d or b''), len(p) if p is not None else None, hints))
    print('%s: TU %d sections, retail %d, PC %d' % (name, len(tu), len(rt), len(pc)))
    print('TU vs retail by type:', {('%d %s' % k): n for k, n in sorted(cls.items()) if k[1] != 'same'})
    print('changed/new sections of types %s (retail size -> TU size; PC size of the mapped id):' % sorted(types))
    for (t, i), c, rs, ts, ps, hints in sorted(rows, key=lambda r: -abs(r[3] - r[2])):
        print('   %d:%-5d %-7s %6d -> %6d  PC %s  %s' % (t, i, c, rs, ts, ps if ps is not None else '-', hints))


if __name__ == '__main__':
    main(sys.argv[1:])
