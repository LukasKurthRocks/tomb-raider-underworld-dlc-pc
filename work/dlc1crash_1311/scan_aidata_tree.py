"""Scan installed trees for 0x390-byte enemy AI records (aidata, detected on the Xbox source) whose 33 DTP-id slots
(+0x8c + 0x18*k) or count words (+4) are not converted: id >= 0x8000 / count with zero low half. Read only.
Usage: pyt scan_aidata_tree.py <out.txt> <tree_dir> [<tree_dir>...]"""
import sys, os, struct, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW, drm_reloc as R, aidata_fix as A
from drm import cdrm_decode, sections_with_data
from convert_dlc import raw_dlc
ids = A._ids()
out = open(sys.argv[1], 'w', encoding='utf-8')
def p(*a):
    s = ' '.join(str(x) for x in a); print(s); out.write(s + '\n')
xcache = {}
for tree in sys.argv[2:]:
    tot = collections.Counter()
    names = sorted(f for f in os.listdir(tree) if f.endswith('.drm'))
    for nm in names:
        if nm not in xcache:
            raw, _ = raw_dlc(nm)
            xcache[nm] = None if raw is None else sections_with_data(cdrm_decode(raw, 'be'), 'be')[1]
        xs = xcache[nm]
        if xs is None: continue
        recs = [(s, A.detect(s['data'], R.parse(s['reloc'], 'be'))) for s in xs if s['type'] == 7 and s['data'] is not None]
        recs = [(s, st) for s, st in recs if st]
        if not recs: continue
        d = DW.read(open(os.path.join(tree, nm), 'rb').read(), 'le')
        pool = {(o.type, o.id): o for o in d.sections}
        for s, st in recs:
            o = pool.get((7, ids(7, s['id'])))
            if o is None: tot['no_pc_section'] += 1; continue
            for t in st:
                tot['records'] += 1; bad = []
                for k in range(33):
                    a = t + 0x8c + 0x18 * k
                    if a + 8 > len(o.data): break
                    xi, xc = struct.unpack_from('>II', s['data'], a)
                    pi, pc = struct.unpack_from('<II', o.data, a)
                    tot['slots'] += 1
                    if xi and (pi >= 0x8000 and pi != 0xffffffff): bad.append(('id', hex(0x8c + 0x18 * k), hex(xi), hex(pi)))
                    if xc != pc: bad.append(('cnt', hex(0x8c + 0x18 * k + 4), hex(xc), hex(pc)))
                if bad:
                    tot['bad_records'] += 1; tot['bad_ids'] += sum(b[0] == 'id' for b in bad); tot['bad_counts'] += sum(b[0] == 'cnt' for b in bad)
                    p('  %s DTP %d (xbox %d) rec +0x%x: %d bad: %s' % (nm, o.id, s['id'], t, len(bad), bad[:6]))
    p('TREE', tree, dict(tot))
out.close()
