"""Which sections of PC DRM files reference a given section id (relocation id references, kinds A and resource),
read-only. Finding 43, test 44: which sections use material 24920 (the DLC 2 waterfall / pool) besides terrain batch
Y 64 - the fall column turned out not to be part of that terrain batch.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/drm_idref_users.py TYPE ID FILE_OR_DIR [...]
  TYPE: referenced section type (5 texture, 9 ShaderLib, 10 material, 12 mesh ...); directories are scanned for *.drm
Output per hit: file, referencing section (type:id, terrain / mesh / other), offsets of the references.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def files(args):
    for a in args:
        if os.path.isdir(a):
            for n in sorted(os.listdir(a)):
                if n.lower().endswith('.drm'): yield os.path.join(a, n)
        else:
            yield a


def kind(s):
    if s.type != 12: return ''
    return 'mesh' if s.data[0x10:0x14] in (b'hseM', b'Mesh') else 'terrain'


def main(argv):
    typ, sid = int(argv[0]), int(argv[1]); hits = 0
    for path in files(argv[2:]):
        try:
            D = DW.read(open(path, 'rb').read(), 'le')
        except Exception as ex:
            print('skip %s: %s' % (path, ex)); continue
        for s in D.sections:
            r = R.parse(s.reloc, 'le')
            offs = [o for t, o in r.idref_a + r.idref if t == typ and o + 4 <= len(s.data)
                    and struct.unpack_from('<I', s.data, o)[0] == sid]
            if offs:
                hits += 1
                print('%s  section %d:%d %s  refs at %s' % (os.path.basename(path), s.type, s.id, kind(s),
                                                         ' '.join('+%#x' % o for o in offs)))
    print('%d referencing sections' % hits)


if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    main(sys.argv[1:])
