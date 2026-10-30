"""Compare the section lists (type, id, size) of an Xbox DRM (big endian, decoded) and a PC DRM, read-only.
Finding 43, test 36: does the title update's generalbank carry sections (e.g. textures for the hint box) that our PC
generalbank lacks?

Usage (from the repository root):
  ../bin/pyt -t 300 tools/drm_section_ids_diff.py XBOX_BE.drm PC.drm [TYPE]
  XBOX_BE.drm may also be tu:NAME or retail:NAME (the file NAME from the Xbox title update / retail layers)
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def xbox_sections(spec):
    if spec.startswith(('tu:', 'retail:')):
        import dtp_word_classes as C
        kind, name = spec.split(':', 1)
        secs = C.find(C.BASE if kind == 'tu' else C.BASE[1:], 'be', 'xenon-w' + chr(92) + name)
        return {(s['type'], s['id']): len(s['data']) for s in secs}
    return {(s.type, s.id): len(s.data) for s in DW.read(open(spec, 'rb').read(), 'be').sections}


def main(argv):
    P = DW.read(open(argv[1], 'rb').read(), 'le')
    only = int(argv[2]) if len(argv) > 2 else None
    xs = xbox_sections(argv[0]); ps = {(s.type, s.id): len(s.data) for s in P.sections}
    cx = collections.Counter(t for t, _ in xs); cp = collections.Counter(t for t, _ in ps)
    print('sections per type  xbox %s' % dict(sorted(cx.items())))
    print('                   pc   %s' % dict(sorted(cp.items())))
    for k in sorted(set(xs) - set(ps)):
        if only is None or k[0] == only: print('only xbox: type %d id %d size %d' % (k[0], k[1], xs[k]))
    n = sum(1 for k in set(ps) - set(xs) if only is None or k[0] == only)
    print('only pc: %d sections%s' % (n, '' if only is None else ' of type %d' % only))


if __name__ == '__main__':
    main(sys.argv[1:])
