r"""AI record gate (P4.2, 2026-11-13; from work/dlc1crash_1311/scan_aidata_tree.py, workspace docs
Befund-DLC1-Absturz-Spinne-1311.md / Befund-P4s-Pipeline-1311.md). Read only.

Why: tools/aidata_fix.py ran without its table in the Q94 run of 2026-11-12 and changed nothing, silently; 19 enemy AI
records stayed wrong (u16-pair ids such as 0x24910000 for the small albino spider attack sound -> crash 13.11. 12:05 in
the DTP lookup 0x54df80, which has no bounds check).

For every DRM of the tree with an Xbox twin (convert_dlc.raw_dlc; --pack PACK = that pack first, as the pipeline), every
0x390-byte AI record (aidata_fix.detect on the Xbox source) is compared slot by slot (32 entries {u32 DTP id, u32 count}
at +0x8c + 0x18*k): a wrong record has a PC id >= 0x8000 (not -1) where the Xbox id is non-zero, or a count that is not
the Xbox count. Exit 1 on any wrong record (or no record found at all with --expect-records), 0 otherwise.
  check TREE[,TREE..] [--pack PACK] [--report R.json] [--expect-records]
        TREE,TREE: the first tree that holds a file wins (layer stack, as the other gates)
Usage (from the repository root): ../bin/pyt -t 1800 tools/scan_aidata_tree.py check work/rebuild/asm_stage2b/mods --pack pack10
"""
import sys, os, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, aidata_fix as A

SLOTS = 32          # +0x8c .. +0x374 (aidata_fix: k = 0..31)


def opt(a, key):
    if key in a:
        k = a.index(key); v = a[k + 1]; del a[k:k + 2]; return v
    return None


def scan(trees, ids, raw_dlc, cdrm_decode, sections_with_data, p):
    tot = collections.Counter(); bad_rows = []
    names = sorted({os.path.relpath(os.path.join(r, f), d).replace('\\', '/') for d in trees for r, _, fs in os.walk(d)
                    for f in fs if f.endswith('.drm')})
    for nm in names:
        path = next((os.path.join(d, nm) for d in trees if os.path.isfile(os.path.join(d, nm))), None)
        raw, _ = raw_dlc(nm.replace('/', '\\'))
        if raw is None: raw, _ = raw_dlc(os.path.basename(nm))
        if raw is None: tot['no_xbox'] += 1; continue
        xs = sections_with_data(cdrm_decode(raw, 'be'), 'be')[1]
        recs = [(s, A.detect(s['data'], R.parse(s['reloc'], 'be'))) for s in xs if s['type'] == 7 and s['data'] is not None]
        recs = [(s, st) for s, st in recs if st]
        if not recs: continue
        tot['files'] += 1
        d = DW.read(open(path, 'rb').read(), 'le')
        pool = {(o.type, o.id): o for o in d.sections}
        for s, st in recs:
            o = pool.get((7, ids(7, s['id'])))
            if o is None: tot['no_pc_section'] += 1; continue
            for t in st:
                tot['records'] += 1; bad = []
                for k in range(SLOTS):
                    a = t + 0x8c + 0x18 * k
                    if a + 8 > len(o.data) or a + 8 > len(s['data']): break
                    xi, xc = struct.unpack_from('>II', s['data'], a)
                    pi, pc = struct.unpack_from('<II', o.data, a)
                    tot['slots'] += 1
                    if xi and pi >= 0x8000 and pi != 0xffffffff: bad.append(('id', hex(a - t), hex(xi), hex(pi)))
                    if xc != pc: bad.append(('cnt', hex(a - t + 4), hex(xc), hex(pc)))
                if bad:
                    tot['bad_records'] += 1
                    tot['bad_ids'] += sum(b[0] == 'id' for b in bad); tot['bad_counts'] += sum(b[0] == 'cnt' for b in bad)
                    bad_rows.append(dict(file=nm, dtp=o.id, xbox=s['id'], rec=hex(t), bad=bad))
                    p('  WRONG %s DTP %d (xbox %d) rec +0x%x: %d bad: %s' % (nm, o.id, s['id'], t, len(bad), bad[:6]))
    return tot, bad_rows


def main(a):
    if not a or a[0] != 'check' or len(a) < 2: sys.exit(__doc__)
    a = list(a)
    pack = opt(a, '--pack'); report = opt(a, '--report')
    expect = '--expect-records' in a
    a = [x for x in a if x != '--expect-records']
    trees = a[1].split(',')
    if pack: os.environ['TRUDLC_PACK_FIRST'] = pack
    from drm import cdrm_decode, sections_with_data
    from convert_dlc import raw_dlc
    ids = A._ids()
    tot, rows = scan(trees, ids, raw_dlc, cdrm_decode, sections_with_data, print)
    rc = 1 if tot['bad_records'] or (expect and not tot['records']) else 0
    print('%s: %s %s' % ('ok' if rc == 0 else 'FAIL', ','.join(trees), dict(tot)))
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        json.dump(dict(gate='aidata', trees=trees, pack=pack, totals=dict(tot), wrong=rows, exit=rc),
                  open(report, 'w', encoding='utf-8'), indent=1)
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
