"""F1 (2026-11-14): compare the cell stream list pairs of every DRM in NEW_DIR with the same file in OLD_DIR (both PC,
LE; tools/unit_ids.cell_stream_fields). Read-only. Prints per file: pairs, equal, different (+ list with --list).
Usage (repository root): ../bin/pyt -t 600 work/f1_1411/f1_compare_old.py NEW_DIR OLD_DIR [--list]
"""
import sys, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm_write as DW
import unit_ids as U


def plist(path):
    D = DW.read(open(path, 'rb').read(), 'le')
    secs = [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]
    return [struct.unpack_from('<HH', secs[si]['data'], o) for si, o in U.cell_stream_fields(secs, 'le')], \
        U.streamgroup_count(secs, 'le')


def main(a):
    lst = '--list' in a
    a = [x for x in a if x != '--list']
    new, old = a[0], a[1]
    tot = [0, 0, 0]
    for f in sorted(os.listdir(new)):
        if not f.endswith('.drm') or not os.path.isfile(os.path.join(old, f)): continue
        pn, cn = plist(os.path.join(new, f)); po, co = plist(os.path.join(old, f))
        if len(pn) != len(po):
            print('%s: pair count new %d old %d' % (f, len(pn), len(po))); tot[2] += 1; continue
        eq = sum(1 for x, y in zip(pn, po) if x == y)
        tot[0] += len(pn); tot[1] += eq
        print('%s: %d pairs, equal %d, different %d; streamgroup records new %s old %s' % (f, len(pn), eq, len(pn) - eq, cn, co))
        if lst:
            for x, y in zip(pn, po):
                print('   new %d/%d old %d/%d%s' % (x[0], x[1], y[0], y[1], '' if x == y else '  DIFF'))
    print('total pairs %d, equal %d, files with another pair count %d' % tuple(tot))
    return 0 if tot[0] == tot[1] and not tot[2] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
