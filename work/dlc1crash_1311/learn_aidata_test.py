"""Re-learn the aidata_fix table (missing work/generic/aidata_table.pkl) into THIS folder only (the shared table is not
written) and apply it in memory to the installed Q94 tree: which id / count words would it set, and does the result
equal the old tree (mods_stack_20261113_115332)? Read only. Usage: pyt learn_aidata_test.py <q94 mods> <old mods> <out.txt>"""
import sys, os, struct, pickle, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm_write as DW, drm_reloc as R, aidata_fix as A
from drm import cdrm_decode, sections_with_data
from convert_dlc import raw_dlc
q94, old, outp = sys.argv[1], sys.argv[2], sys.argv[3]
out = open(outp, 'w', encoding='utf-8')
def p(*a):
    s = ' '.join(str(x) for x in a); print(s); out.write(s + '\n'); out.flush()
ids = A._ids()
T, st = A.learn(A._pairs(), ids.base)
pickle.dump(T, open(os.path.join(HERE, 'aidata_table_test.pkl'), 'wb'))
p('learned offsets', len(T), 'ambiguous', sum(1 for e in T.values() if A.choose(e) is None), dict(st))
p('id32:7 offsets', [hex(w) for w, e in sorted(T.items()) if A.choose(e) == 'id32:7'])
tot = collections.Counter()
for nm in ('dlc_caverns.drm', 'dlc_caverns_hall.drm', 'dlc_dungeonhallb.drm', 'dlc_level1_start.drm', 'dlc2_machine_room.drm',
           'dlc2_ceremony_room.drm'):
    raw, _ = raw_dlc(nm)
    xs = sections_with_data(cdrm_decode(raw, 'be'), 'be')[1]
    dq = DW.read(open(os.path.join(q94, nm), 'rb').read(), 'le')
    do = DW.read(open(os.path.join(old, nm), 'rb').read(), 'le')
    pq = {(o.type, o.id): o for o in dq.sections}; po = {(o.type, o.id): o for o in do.sections}
    for s in xs:
        if s['type'] != 7 or s['data'] is None: continue
        rel = R.parse(s['reloc'], 'be'); recs = A.detect(s['data'], rel)
        if not recs: continue
        key = (7, ids(7, s['id'])); a = pq.get(key); b = po.get(key)
        if a is None: continue
        buf = bytearray(a.data)
        n = A.fix(s['data'], rel, buf, ids, T)
        diff_old = None
        if b is not None and len(b.data) == len(buf):
            diff_old = sum(1 for t in recs for w in range(0, A.SIZE, 4) if buf[t + w:t + w + 4] != b.data[t + w:t + w + 4])
        bad = 0
        for t in recs:
            for k in range(32):
                o = t + 0x8c + 0x18 * k
                xi, xc = struct.unpack_from('>II', s['data'], o); pi, pc = struct.unpack_from('<II', buf, o)
                bad += (xi and pi >= 0x8000 and pi != 0xffffffff) + (xc != pc)
        tot['words'] += n; tot['bad_after'] += bad
        p('%s DTP %d: %d records, fix changes %d words, bad id/count slots after fix %d, words differing from old tree '
          'after fix %s' % (nm, a.id, len(recs), n, bad, diff_old))
p('total', dict(tot), dict(A.FIX_STATS))
