"""Where do the external relocations of a script point to? (DLC 2 tests 2-4, finding 43)

For every external relocation of script SCRIPT_ID in DRM: the target section and offset are classified with
script_conv.Walk on the target script - start of an element of an array (funcs, protos, members, states, ...), the
array itself, the root, inside an element (+n), or nowhere known. Run it on the converted script and on the PC's own
version of the same script: the PC original shows which kinds are normal; anything the converted one has on top
(inside an element, nowhere) is a suspect for a call through a wrong pointer.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/script_ext_check.py DRM SCRIPT_ID [--list N]
  --list N: print up to N suspect relocations (source offset, source label, target, class)
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, script_conv as SC

ROOT_SIZE = 0x54


def classify(walk, off):
    if off < ROOT_SIZE: return ('root', off)
    best = None
    for nm, t, n, sz in walk.arrays:
        if t <= off < t + n * sz:
            k, r = divmod(off - t, sz)
            c = (nm, 'element' if r == 0 else 'inside +%d' % r)
            if r == 0: return c
            best = best or c
        elif off == t and n == 0: return (nm, 'empty array')
    return best or ('none', walk.lab.get(off, ('no label',))[0])


def main(argv):
    lim = 0
    if '--list' in argv: k = argv.index('--list'); lim = int(argv[k + 1]); del argv[k:k + 2]
    path, sid = argv[0], int(argv[1])
    S = DW.read(open(path, 'rb').read(), 'le').sections
    s = next(x for x in S if x.type == 8 and x.id == sid)
    rel = R.parse(s.reloc, 'le')
    me = SC.Walk(s.data, rel, 'le'); me.run()
    walks = {}; counts = collections.Counter(); suspects = []
    for si, src, dst in rel.external:
        t = S[si]
        if t.type != 8:
            c = ('type %d' % t.type, 'in bounds' if 0 <= dst < len(t.data) else 'OUT OF BOUNDS')
        else:
            if si not in walks:
                w = SC.Walk(t.data, R.parse(t.reloc, 'le'), 'le'); w.run(); walks[si] = w
            c = classify(walks[si], dst)
        counts[c] += 1
        if c[1] not in ('element', 'in bounds') and c[0] != 'root':
            suspects.append((src, me.lab.get(src, ('?',))[0], t.type, t.id, dst, c))
    print('%s script %d: %d external relocations' % (path, sid, len(rel.external)))
    for c, n in sorted(counts.items(), key=lambda kv: -kv[1]): print('  %-40s %d' % (' / '.join(map(str, c)), n))
    print('  suspects (not root, not an element start): %d' % len(suspects))
    for x in suspects[:lim]:
        print('    src +0x%x (%s) -> %d:%d +0x%x  %s' % (x[0], x[1], x[2], x[3], x[4], ' / '.join(map(str, x[5]))))


if __name__ == '__main__':
    main(sys.argv[1:])
