"""F1 (2026-11-14): word diff of two PC DRM folders (same file names): per file the sections whose data / reloc / id /
type differ and the differing 4-byte words (offset, A, B). Read-only.
Usage (repository root): ../bin/pyt -t 600 work/f1_1411/f1_wordiff.py DIR_A DIR_B [--list]
"""
import sys, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm_write as DW


def main(a):
    lst = '--list' in a
    a = [x for x in a if x != '--list']
    da, db = a[0], a[1]
    total = 0
    for f in sorted(os.listdir(da)):
        pa, pb = os.path.join(da, f), os.path.join(db, f)
        if not f.endswith('.drm') or not os.path.isfile(pb): continue
        A = DW.read(open(pa, 'rb').read(), 'le').sections; B = DW.read(open(pb, 'rb').read(), 'le').sections
        if len(A) != len(B): print('%s: section count %d vs %d' % (f, len(A), len(B))); total += 1; continue
        words = 0; other = []
        for i, (x, y) in enumerate(zip(A, B)):
            if (x.type, x.id) != (y.type, y.id) or x.reloc != y.reloc or len(x.data) != len(y.data):
                other.append(i); continue
            if x.data == y.data: continue
            for o in range(0, len(x.data) - 3, 4):
                if x.data[o:o + 4] != y.data[o:o + 4]:
                    words += 1
                    if lst: print('   %s sec#%d (%d:%d) +0x%05x %s -> %s' % (f, i, x.type, x.id, o, x.data[o:o + 4].hex(),
                                                                         y.data[o:o + 4].hex()))
        total += words + len(other)
        print('%s: %d words differ; sections with other id / reloc / size: %s' % (f, words, other))
    print('total differences', total)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
