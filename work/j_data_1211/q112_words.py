"""Q112 (b), read-only: which 32-bit words differ in the same-size changed base DTPs (rows of q112_detail.tsv, type 7,
size_eq y) of one DLC DRM - offset histogram, value patterns (Xbox base word -> DLC word, big-endian hex) and how
many rows share a pattern. Also the size difference histogram of the size-changed rows.

Usage (from trudlcport): ../bin/pyt -t 1800 work/j_data_1211/q112_words.py OUT_DIR PACK DRM [TYPE]
  e.g. OUT_DIR pack11 xenon-w\\lara_doppelganger.drm
"""
import sys, os, csv, struct, collections
sys.path.insert(0, os.path.join(os.getcwd(), 'work', 'j_data_1211'))
sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
import q112_detail as QD


def main(out, pk, drm, typ):
    rows = [r for r in csv.DictReader(open(os.path.join(out, 'q112_detail.tsv'), encoding='utf-8'), delimiter='\t')
            if r['type'] == str(typ) and r['pack'] == pk and r['drm'] == drm and r['base_holder']]
    dl = QD.read_rec([QD.DLC_ROOT + QD.PACKS[pk]], 'be', drm)
    offs = collections.Counter(); pats = collections.Counter(); sized = collections.Counter(); nrows = 0
    ex = {}
    for r in rows:
        xid = int(r['xbox_id'])
        b = QD.secs_of(('base', r['base_holder']), lambda: QD.read_rec(QD.BASE, 'be', r['base_holder']))
        d, x = dl[(typ, xid)][0], b[(typ, xid)][0]
        if len(d) != len(x):
            sized[len(d) - len(x)] += 1; continue
        nrows += 1
        for i in range(0, len(d) - 3, 4):
            if d[i:i + 4] != x[i:i + 4]:
                offs[i] += 1
                p = (x[i:i + 4].hex(), d[i:i + 4].hex())
                pats[p] += 1; ex.setdefault(p, (xid, i))
    print('%s %s type %d: %d same-size rows, %d size-changed' % (pk, drm, typ, nrows, sum(sized.values())))
    print('offsets (top 15):', [('0x%x' % o, n) for o, n in offs.most_common(15)])
    print('value patterns (top 20, base -> dlc, example id/offset):')
    for p, n in pats.most_common(20):
        xb = struct.unpack('>f', bytes.fromhex(p[0]))[0]; db = struct.unpack('>f', bytes.fromhex(p[1]))[0]
        print('   %s -> %s  x%d  (f32 %.6g -> %.6g)  e.g. id %d +0x%x' % (p[0], p[1], n, xb, db, ex[p][0], ex[p][1]))
    print('size differences (dlc - base, top 10):', sized.most_common(10))


if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 7)
