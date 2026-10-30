"""List the section-id references (relocation kinds A and resource) of one DRM section, read-only.

Finding 43, test 43: which texture (type 5) or DTP (type 7) sections a script references - e.g. whether the
title update's hint-box script 10 / our PC script 9 points at textures the PC generalbank lacks.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/drm_idrefs.py SRC TYPE:ID [--type T]
  SRC   a PC DRM file (little endian), or tu:NAME / retail:NAME (the Xbox title update / retail layers, big endian)
  --type T  only references to sections of type T (5 texture, 7 DTP, 8 script, 9 shaderlib, 10 material, 12 mesh)
Output: kind, referenced type, offset in the section, referenced id, and whether SRC has that section.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def load(spec):
    """[(type, id, data, reloc)], endian"""
    if spec.startswith(('tu:', 'retail:')):
        import dtp_word_classes as C
        kind, name = spec.split(':', 1)
        secs = C.find(C.BASE if kind == 'tu' else C.BASE[1:], 'be', 'xenon-w' + chr(92) + name)
        return [(s['type'], s['id'], s['data'], s['reloc']) for s in secs], 'be'
    D = DW.read(open(spec, 'rb').read(), 'le')
    return [(s.type, s.id, s.data, s.reloc) for s in D.sections], 'le'


def main(argv):
    only = None
    if '--type' in argv:
        k = argv.index('--type'); only = int(argv[k + 1]); del argv[k:k + 2]
    if len(argv) != 2: sys.exit(__doc__)
    secs, e = load(argv[0])
    st, sid = (int(x) for x in argv[1].split(':'))
    have = {(t, i) for t, i, _, _ in secs}
    s = next((x for x in secs if x[0] == st and x[1] == sid), None)
    if s is None: sys.exit('section %s not found in %s' % (argv[1], argv[0]))
    r = R.parse(s[3], e); fmt = '>I' if e == 'be' else '<I'
    rows = [('A', t, o) for t, o in r.idref_a] + [('res', t, o) for t, o in r.idref]
    print('%s %s: %d id references (kind A %d, resource %d)' % (argv[0], argv[1], len(rows), len(r.idref_a), len(r.idref)))
    for kind, t, o in sorted(rows, key=lambda x: x[2]):
        if only is not None and t != only: continue
        v, = struct.unpack_from(fmt, s[2], o)
        print('  %-3s type %2d  +0x%05x  id %6d  %s' % (kind, t, o, v, 'present' if (t, v) in have else 'MISSING in SRC'))


if __name__ == '__main__':
    main(sys.argv[1:])
