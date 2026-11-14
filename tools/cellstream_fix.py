r"""Cell stream list rule + gate (F1 / PT2-1, 2026-11-14; workspace docs Befund-PT2-Pranger-1411.md,
Befund-F1-Zellstreamlisten-1411.md; ENGINE.md 'Cell stream lists').

Why: each cell of a unit's scene carries a list {u16 StreamUnitID, u16 streamgroup index} (cell section +0x90 -> cell
record R in the unit DTP, R+0x88 count, R+0x8c -> pairs; read by 0x5b8e80 when Lara's cell changes). StreamUnitID is
the global unit id space (objlist record index, unit_idmaps.json 'unit', pseudo type 110), numbered differently on
Xbox. The learned type-7 table converted only the first pair of a list (its label had id16a:110 votes); the others kept
the Xbox id (PC - 1 in DLC 1) -> the pillory main cell names dlc_water_wheel group 1 (does not exist, read one record
past the table end) -> streamgroup request with a SceneCell pointer as name -> file system queue stuck -> the next
loading screen hangs (PT.2). The converter maps every pair since 2026-11-14 (generic_type0.fix_unit_fields over
unit_ids.cell_stream_fields: unit id through the map, index = Xbox value).

  proof   every base unit pair (work/generic/pairs.pkl via generic_cache.load_pairs): the lists found on Xbox and PC
          (same count), each PC pair = {map(Xbox unit), Xbox index}; every PC index + 1 < record count of the named
          unit's streamgroup table (PC base units). Exit 1 on a contradiction or another pinned count.
  check   every unit DRM of the tree with an Xbox twin (convert_dlc.raw_dlc; --pack PACK first): same list layout, each
          pair = {map(Xbox unit), Xbox index} (else 'unmapped' = Xbox raw id left, or 'wrong'), the named unit is a unit
          of the tree (or of the PC base: --base-counts FILE written by proof --write-counts FILE; the DLC lists name
          only DLC units, 2026-11-14) and index + 1 < its streamgroup record
          count (record = index + 1, record 0 'default'; index = count - 1 reads past the end, index >= count is
          skipped by the engine). Exit 1 on any unmapped / wrong / past-end / beyond-count / unknown-unit pair, a layout
          difference, a missing tree folder, no unit DRM.
  fix     rewrite the pairs of already converted DRMs with the rule (offline proofs / A-B), output OUTDIR\<name>
Usage (from the repository root):
  ../bin/pyt -t 1800 tools/cellstream_fix.py proof [--report R.json] [--write-counts COUNTS.json]
  ../bin/pyt -t 1800 tools/cellstream_fix.py check TREE[,TREE..] [--pack PACK] [--report R.json] [--base-counts COUNTS.json]
  ../bin/pyt -t 1800 tools/cellstream_fix.py fix OUTDIR SRCDIR[,SRCDIR..] [--pack PACK] name.drm [...]
"""
import sys, os, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import unit_ids as U

UNIT = 110
# pinned base proof (2026-11-14): 81 base units of the pairs, 25 with lists, 310 pairs, rule = PC 310 / 310 (128 of
# them with a different id on Xbox and PC, i.e. the raw Xbox id would be wrong), every PC index in range
PROOF_EXPECT = {'units': 81, 'units_without_lists': 56, 'units_with_lists': 25, 'pairs': 310, 'ok': 310,
                'same_id_both': 182, 'index_in_range': 310}


def opt(a, key):
    if key in a:
        k = a.index(key); v = a[k + 1]; del a[k:k + 2]; return v
    return None


def secs_of(D):
    return [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data) if s.data is not None else 0) for s in D.sections]


def own_unit(secs, e):
    if not secs or secs[0]['type'] != 0 or secs[0]['data'] is None or len(secs[0]['data']) < 0x50: return None
    if U.level_info(secs, e) is None: return None
    return struct.unpack_from(('>' if e == 'be' else '<') + 'I', secs[0]['data'], 0x4c)[0]


def pairs(secs, e):
    """[(sec, off, unit, index)] of the cell stream lists"""
    E = '>' if e == 'be' else '<'
    return [(si, o, *struct.unpack_from(E + 'HH', secs[si]['data'], o)) for si, o in U.cell_stream_fields(secs, e)]


def rule(xu, xi, ids):
    return (ids(UNIT, xu) & 0xffff if xu not in (0, 0xffff) else xu), xi


class _BaseIds:
    def __init__(self, base): self.base = base; self.miss = collections.Counter()
    def __call__(self, t, v):
        m = self.base.get(t, {})
        if v not in m: self.miss[t] += 1
        return m.get(v, v)


def proof(p=print):
    from generic_cache import load_pairs
    import generic_type0
    ids = _BaseIds(generic_type0.space_maps())
    P = load_pairs()
    got = collections.Counter(); lines = []; counts = {}; lists = []
    for nm, ((xh, sx), (ph, sp)) in sorted(P.items()):
        if nm.startswith('patch:'): continue
        pu = own_unit(sp, 'le')
        if pu is None: continue
        got['units'] += 1
        c = U.streamgroup_count(sp, 'le')
        if c is not None: counts[pu] = c
        fx, fp = pairs(sx, 'be'), pairs(sp, 'le')
        if not fx and not fp: got['units_without_lists'] += 1; continue
        if len(fx) != len(fp):
            got['layout_differs'] += 1; lines.append('  layout %s: Xbox %d pairs PC %d' % (nm, len(fx), len(fp))); continue
        got['units_with_lists'] += 1
        for (_, xo, xu, xi), (_, po, pu_, pi) in zip(fx, fp):
            got['pairs'] += 1
            n0 = ids.miss[UNIT]
            w = rule(xu, xi, ids)
            if ids.miss[UNIT] != n0: got['unit_unmapped'] += 1
            if w == (pu_, pi): got['ok'] += 1
            else:
                got['contra'] += 1
                if got['contra'] <= 20:
                    lines.append('  CONTRA %s Xbox +0x%x %d/%d PC +0x%x %d/%d rule %d/%d' % (nm, xo, xu, xi, po, pu_, pi, *w))
            if xu == pu_: got['same_id_both'] += 1
            lists.append((nm, pu_, pi))
    for nm, u, i in lists:
        c = counts.get(u)
        if c is None: got['pc_unit_unknown'] += 1; lines.append('  unknown PC unit %d in %s' % (u, nm))
        elif i + 1 < c: got['index_in_range'] += 1
        else:
            got['index_past_end'] += 1; lines.append('  PAST-END %s pair %d/%d (records %d)' % (nm, u, i, c))
    return dict(got), lines, counts


def tree_names(trees):
    return sorted({os.path.relpath(os.path.join(r, f), d).replace('\\', '/') for d in trees for r, _, fs in os.walk(d)
                   for f in fs if f.endswith('.drm')})


def tree_path(trees, nm):
    return next((os.path.join(d, nm) for d in trees if os.path.isfile(os.path.join(d, nm))), None)


def xbox_raw(raw_dlc, nm):
    raw, _ = raw_dlc(nm.replace('/', '\\'))
    if raw is None: raw, _ = raw_dlc(os.path.basename(nm))
    return raw


def check(trees, ids, raw_dlc, base_counts, p=print):
    tot = collections.Counter(); bad = []; units = {}; todo = []
    for nm in tree_names(trees):
        raw = xbox_raw(raw_dlc, nm)
        if raw is None: tot['no_xbox'] += 1; continue
        PD = DW.read(open(tree_path(trees, nm), 'rb').read(), 'le'); sp = secs_of(PD)
        pu = own_unit(sp, 'le')
        if pu is None: continue
        sx = secs_of(DW.read(raw, 'be'))
        tot['units'] += 1
        units[pu] = (nm, U.streamgroup_count(sp, 'le'))
        todo.append((nm, pairs(sx, 'be'), pairs(sp, 'le')))
    for nm, fx, fp in todo:
        if len(fx) != len(fp):
            tot['layout_differs'] += 1; bad.append(dict(file=nm, kind='layout', xbox=len(fx), pc=len(fp)))
            p('  LAYOUT %s: Xbox %d pairs PC %d' % (nm, len(fx), len(fp))); continue
        if fx: tot['units_with_lists'] += 1
        for (_, xo, xu, xi), (_, po, pu_, pi) in zip(fx, fp):
            tot['pairs'] += 1
            w = rule(xu, xi, ids)
            if (pu_, pi) == w: tot['mapped'] += 1
            else:
                k = 'unmapped' if (pu_, pi) == (xu, xi) else 'wrong'
                tot[k] += 1
                bad.append(dict(file=nm, kind=k, off=hex(po), xbox=[xu, xi], pc=[pu_, pi], want=list(w)))
                p('  %s %s +0x%x: Xbox %d/%d PC %d/%d want %d/%d' % (k.upper(), nm, po, xu, xi, pu_, pi, *w))
            if pu_ in units: c = units[pu_][1]; tot['pairs_tree_unit'] += 1
            elif str(pu_) in base_counts: c = base_counts[str(pu_)]; tot['pairs_base_unit'] += 1
            else:
                tot['unit_unknown'] += 1; bad.append(dict(file=nm, kind='unit_unknown', off=hex(po), pc=[pu_, pi]))
                p('  UNIT-UNKNOWN %s +0x%x: PC %d/%d' % (nm, po, pu_, pi)); continue
            # index + 1 == count: passes the engine check 0x5b8f5c (index < count) and reads one record past the end
            # (the hang); index >= count: skipped by the engine (dead pair) - with correct data neither occurs (proof)
            if c is None or pi + 1 >= c:
                k = 'past_end' if c is not None and pi + 1 == c else 'beyond_count'
                tot[k] += 1
                bad.append(dict(file=nm, kind=k, off=hex(po), pc=[pu_, pi], records=c))
                p('  %s %s +0x%x: PC %d/%d, unit %s has %s records' % (
                    k.upper().replace('_', '-'), nm, po, pu_, pi, units.get(pu_, ('base',))[0], c))
            else: tot['index_ok'] += 1
    return tot, bad, units


def fix_file(path, XD, ids):
    raw_old = open(path, 'rb').read()
    D = DW.read(raw_old, 'le'); sp = secs_of(D)
    fx, fp = pairs(secs_of(XD), 'be'), pairs(sp, 'le')
    if len(fx) != len(fp): return None, 'layout Xbox %d PC %d' % (len(fx), len(fp))
    ch = []
    for (_, _, xu, xi), (si, po, pu_, pi) in zip(fx, fp):
        w = rule(xu, xi, ids)
        if w != (pu_, pi):
            b = bytearray(D.sections[si].data); struct.pack_into('<HH', b, po, *w); D.sections[si].data = bytes(b)
            ch.append((si, po, (pu_, pi), w))
    data = D.write('le')
    if raw_old[:4] == b'CDRM': data = DW.cdrm_encode(data, 'le')
    return data, ch


def main(a):
    if not a or a[0] not in ('check', 'proof', 'fix'): sys.exit(__doc__)
    a = list(a)
    pack = opt(a, '--pack'); report = opt(a, '--report')
    wcounts = opt(a, '--write-counts'); bcounts = opt(a, '--base-counts')
    if pack: os.environ['TRUDLC_PACK_FIRST'] = pack
    if a[0] == 'proof':
        got, lines, counts = proof()
        for l in lines: print(l)
        rc = 0 if got.get('ok') and not got.get('contra') and not got.get('index_past_end') and \
            not got.get('pc_unit_unknown') and (PROOF_EXPECT is None or got == PROOF_EXPECT) else 1
        if PROOF_EXPECT is not None and got != PROOF_EXPECT: print('pinned counts differ: want %s' % PROOF_EXPECT)
        print('%s: %s' % ('ok' if rc == 0 else 'FAIL', got))
        if wcounts:
            json.dump({str(k): v for k, v in sorted(counts.items())}, open(wcounts, 'w'), indent=0)
            print('wrote', wcounts, len(counts))
        if report: json.dump(dict(gate='cellstream_proof', got=got, want=PROOF_EXPECT, exit=rc), open(report, 'w'), indent=1)
        return rc
    from convert_dlc import raw_dlc
    import dlc_generic as DG
    ids = DG.DlcIds()
    if a[0] == 'fix':
        out, srcs = a[1], a[2].split(',')
        rc = 0
        for nm in a[3:]:
            path = tree_path(srcs, nm); raw = xbox_raw(raw_dlc, nm)
            if path is None or raw is None: print('%s: not found / no Xbox source' % nm); rc = 1; continue
            data, ch = fix_file(path, DW.read(raw, 'be'), ids)
            if data is None: print('%s: %s - not written' % (nm, ch)); rc = 1; continue
            for si, po, old, new in ch: print('  %s sec#%d +0x%x %d/%d -> %d/%d' % (nm, si, po, *old, *new))
            op = os.path.join(out, nm); os.makedirs(os.path.dirname(op) or '.', exist_ok=True)
            open(op, 'wb').write(data)
            print('%s: %d pairs -> %s' % (nm, len(ch), op))
        return rc
    trees = a[1].split(',')
    miss = [t for t in trees if not os.path.isdir(t)]
    if miss: print('FAIL: tree folder(s) not found: %s' % miss); return 1
    base_counts = json.load(open(bcounts)) if bcounts else {}
    tot, rows, units = check(trees, ids, raw_dlc, base_counts, print)
    for u, (nm, c) in sorted(units.items()): print('  unit %d %s: %s streamgroup records' % (u, nm, c))
    rc = 1 if (tot['unmapped'] or tot['wrong'] or tot['past_end'] or tot['beyond_count'] or tot['unit_unknown']
               or tot['layout_differs'] or not tot['units']) else 0
    print('%s: %s %s' % ('ok' if rc == 0 else 'FAIL', ','.join(trees), dict(tot)))
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        json.dump(dict(gate='cellstream', trees=trees, pack=pack, totals=dict(tot), wrong=rows,
                       units={str(u): v for u, v in units.items()}, exit=rc), open(report, 'w', encoding='utf-8'), indent=1)
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
