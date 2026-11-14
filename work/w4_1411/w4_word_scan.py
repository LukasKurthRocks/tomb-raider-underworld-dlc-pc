"""W4 (2026-11-14): find u32 words (intro ids etc.) in the sections of PC DRMs, read-only.

Usage (from the repository root):
  ../bin/pyt -t 600 work/w4_1411/w4_word_scan.py VALUE[,VALUE..] DIR_OR_DRM [...] [--types 8,7]
Prints every 4-byte-aligned little-endian u32 equal to one of the values: file, section type:id, offset, value.
Default section types: all. Exit code 0.
"""
import sys, os, struct
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import drm_write as DW


def secs(path):
    """[(type, id, data)] of a PC DRM file or a pc:NAME.drm base-game name (script_func_list.sections)"""
    if ':' in path[:6] and not os.path.exists(path):
        import script_func_list as FL
        S, e = FL.sections(path)
        return [(q[0], q[1], q[2]) for q in S]
    D = DW.read(open(path, 'rb').read(), 'le')
    return [(s.type, s.id, s.data) for s in D.sections]


def scan(path, vals, types):
    try:
        S = secs(path)
    except (Exception, SystemExit) as ex:
        print('%s: read error %s' % (path, ex)); return
    for t, i, d in S:
        if types and t not in types: continue
        s = type('S', (), {'type': t, 'id': i})
        d = d or b''
        for o in range(0, len(d) - 3, 4):
            v = struct.unpack_from('<I', d, o)[0]
            if v in vals:
                print('%-36s %2d:%-6d +0x%05x  %d' % (os.path.basename(path), s.type, s.id, o, v))


def main(argv):
    types = None
    if '--types' in argv:
        k = argv.index('--types'); types = {int(x) for x in argv[k + 1].split(',')}; del argv[k:k + 2]
    vals = {int(x, 0) for x in argv[0].split(',')}
    for a in argv[1:]:
        if os.path.isdir(a):
            for f in sorted(os.listdir(a)):
                if f.lower().endswith('.drm'): scan(os.path.join(a, f), vals, types)
        else:
            scan(a, vals, types)
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
