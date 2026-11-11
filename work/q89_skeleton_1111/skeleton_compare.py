"""Q89 step 1 (model swap, read only): skeletons, anim skeletons and anim segment counts of character objects.

Per object name (resolved like the game: MODS_DIR flat <name>.drm, then data/pc/patch.000, data/pc/bigfile.000):
  models    every model DTP (word0 0x04c20453): section id, segment count (+4), header pointer fields (internal relocs
            in the first 0x80 bytes), +0x68 anim-skeleton pointer (the processor skeleton count reads [[model+0x68]]
            when set, else model+4, 0x627072), parent list (segment +0x38), pivots (segment +0x20..+0x28)
  object    root object DTP: model slots +0xa0 count / +0xa4 ptr (idrefs -> model DTP ids), anim table +0x54 / +0x58
  anims     type-2 sections: count per segment count (+0x36 u8)
Then a pairwise table: common parent prefix length, first differing bone, max pivot distance on the common prefix.

Usage (from the repository root):
  ../bin/pyt -t 1800 work/q89_skeleton_1111/skeleton_compare.py MODS_DIR NAME [NAME ...] [--segs] [--hdr]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'q83_allenemies_1111'))
import drm_write as DW, drm_reloc as R
from enemy_catalog import Src

MAGIC = 0x04c20453


def models(D):
    out = []
    for idx, s in enumerate(D.sections):
        d = s.data
        if s.type != 7 or len(d) < 0x80 or struct.unpack_from('<I', d, 0)[0] != MAGIC:
            continue
        rel = R.parse(s.reloc, 'le')
        it = dict(rel.internal)
        ids = rel.id_offsets()
        n = struct.unpack_from('<I', d, 4)[0]
        seg = it.get(0xc)
        hdr_ptr = {o: it[o] for o in sorted(it) if o < 0x80}
        hdr_ext = [(si, so, do) for si, so, do in rel.external if so < 0x80]
        segs = []
        if seg is not None:
            for j in range(n):
                e0 = seg + 0x40 * j
                if e0 + 0x40 > len(d):
                    break
                fl = struct.unpack_from('<12f', d, e0)
                a, b = struct.unpack_from('<2H', d, e0 + 0x34)
                p = struct.unpack_from('<i', d, e0 + 0x38)[0]
                w30 = struct.unpack_from('<I', d, e0 + 0x30)[0]
                segs.append({'f': fl, 'v': (a, b), 'parent': p, 'w30': w30, 'hinfo': (e0 + 0x3c) in it})
        sk = None
        if 0x68 in it:
            t = it[0x68]
            cnt = struct.unpack_from('<I', d, t)[0]
            sk = (t, cnt, d[t:t + 0x20].hex())
        for si, so, do in rel.external:
            if so == 0x68 and si < len(D.sections):
                ts = D.sections[si]
                td = ts.data
                c0 = struct.unpack_from('<I', td, do)[0] if do + 4 <= len(td) else None
                c1 = struct.unpack_from('<I', td, do + 4)[0] if do + 8 <= len(td) else None
                mb = None
                if ts.type == 12 and len(td) > 0x94 and td[0x10:0x14] in (b'hseM', b'Mesh'):
                    mb = struct.unpack_from('<H', td, 0x10 + 0x80)[0]
                sk = ('ext section #%d type %d id %d size 0x%x +0x%x' % (si, ts.type, ts.id, len(td), do), c0,
                      'next u32 0x%x, mesh numBones %s' % (c1 or 0, mb))
        out.append({'idx': idx, 'id': s.id, 'n': n, 'size': len(d), 'hdr': struct.unpack_from('<32I', d, 0),
                    'hdr_ptr': hdr_ptr, 'hdr_ext': hdr_ext, 'hdr_ids': {o: t for o, t in ids.items() if o < 0x80},
                    'segs': segs, 'animsk': sk, 'it': it, 'data': d})
    return out


def object_dtp(D):
    """root object DTP: the type-7 section with internal pointers at +0x58 and +0x60 and a sane +0x54 count"""
    for s in D.sections:
        d = s.data
        if s.type != 7 or len(d) < 0xcc:
            continue
        rel = R.parse(s.reloc, 'le')
        it = dict(rel.internal)
        if 0x58 not in it or 0x60 not in it:
            continue
        na = struct.unpack_from('<I', d, 0x54)[0]
        if not (0 < na < 4000):
            continue
        table = [struct.unpack_from('<H', d, it[0x58] + 12 * k)[0] for k in range(na)]
        nm = struct.unpack_from('<H', d, 0xa0)[0]
        mslots = []
        ids = rel.id_offsets()
        if 0xa4 in it:
            p = it[0xa4]
            for k in range(nm):
                o = p + 4 * k
                mslots.append((struct.unpack_from('<I', d, o)[0], ids.get(o), o in it))
        return {'id': s.id, 'table': table, 'nslots': struct.unpack_from('<I', d, 0x5c)[0], 'nmodels': nm,
                'mslots': mslots, 'w68': struct.unpack_from('<I', d, 0x68)[0]}
    return None


def anim_counts(D):
    c = collections.Counter()
    per = {}
    for s in D.sections:
        if s.type == 2 and len(s.data) >= 0x38:
            c[s.data[0x36]] += 1
            per[s.id] = s.data[0x36]
    return c, per


def prefix(pa, pb):
    k = 0
    while k < min(len(pa), len(pb)) and pa[k] == pb[k]:
        k += 1
    return k


def main(argv):
    mods = argv[0]
    names = [x for x in argv[1:] if not x.startswith('--')]
    S = Src(mods)
    res = {}
    for nm in names:
        g = S.get(nm)
        if g is None:
            print('%s: no DRM' % nm)
            continue
        src, st, raw = g
        D = DW.read(raw, 'le')
        ms = models(D)
        ob = object_dtp(D)
        ac, per = anim_counts(D)
        res[nm] = (ms, ob, ac, per)
        print('\n== %s [%s, %d B decoded, %d sections]' % (nm, src, len(raw), len(D.sections)))
        for m in ms:
            par = [s['parent'] for s in m['segs']]
            roots = [i for i, p in enumerate(par) if p < 0]
            bad = [i for i, p in enumerate(par) if p >= i]
            print('  model DTP %d (section #%d) nseg %d size 0x%x roots %s parent>=self %s animsk %s' % (
                m['id'], m['idx'], m['n'], m['size'], roots, bad[:5],
                ('%s count %s %s' % m['animsk']) if m['animsk'] else '-'))
            if '--hdr' in argv:
                print('    hdr ' + ' '.join('%08x' % x for x in m['hdr']))
                print('    hdr ptr ' + ' '.join('+0x%x->0x%x' % kv for kv in m['hdr_ptr'].items()))
                if m['hdr_ext']:
                    print('    hdr ext ' + str(m['hdr_ext']))
                if m['hdr_ids']:
                    print('    hdr ids ' + str(m['hdr_ids']))
            if '--segs' in argv:
                for j, s in enumerate(m['segs']):
                    f = s['f']
                    print('    seg %3d parent %4d pivot %8.2f %8.2f %8.2f | f0-7 %s | v %d..%d w30 %08x hinfo %d' % (
                        j, s['parent'], f[8], f[9], f[10], ' '.join('%.3g' % x for x in f[:8]), s['v'][0], s['v'][1],
                        s['w30'], s['hinfo']))
        if ob:
            hit = sum(1 for i in ob['table'] if i in per)
            segc = collections.Counter(per[i] for i in ob['table'] if i in per)
            print('  object DTP %d: anim table %d (in this DRM %d, seg counts %s), slots %d, model slots %d %s' % (
                ob['id'], len(ob['table']), hit, dict(segc), ob['nslots'], ob['nmodels'], ob['mslots']))
        else:
            print('  object DTP: none with an anim table')
        print('  type-2 anim sections in DRM: %d, seg counts %s' % (sum(ac.values()), dict(sorted(ac.items()))))
    # pairwise against the first name's largest anim-skeleton-sized model
    print('\n== pairwise (main model = the one with most segments; anim skeleton = model with the anim count)')
    main_sk = {}
    for nm, (ms, ob, ac, per) in res.items():
        if not ms:
            continue
        animseg = ac.most_common(1)[0][0] if ac else None
        cand = [m for m in ms if m['n'] == animseg] if animseg else []
        big = max(ms, key=lambda m: m['n'])
        main_sk[nm] = (big, cand[0] if cand else None, animseg)
        print('  %-28s render %d seg (DTP %d) | most common anim seg count %s | model with that count: %s' % (
            nm, big['n'], big['id'], animseg, cand[0]['id'] if cand else '-'))
    keys = list(main_sk)
    if keys:
        ref = keys[0]
        rb = main_sk[ref][1] or main_sk[ref][0]
        rp = [s['parent'] for s in rb['segs']]
        print('\n  reference %s skeleton DTP %d (%d seg)' % (ref, rb['id'], rb['n']))
        for nm in keys:
            for lab, m in (('render', main_sk[nm][0]), ('animsk', main_sk[nm][1])):
                if m is None:
                    continue
                p = [s['parent'] for s in m['segs']]
                k = prefix(rp, p)
                dmax = 0.0
                for j in range(k):
                    a, b = rb['segs'][j]['f'], m['segs'][j]['f']
                    dmax = max(dmax, sum((a[q] - b[q]) ** 2 for q in (8, 9, 10)) ** 0.5)
                print('  %-28s %-6s %3d seg: equal parent prefix %3d, first diff %s, max pivot distance on prefix %.2f' % (
                    nm, lab, m['n'], k, ('bone %d (%d vs %d)' % (k, rp[k] if k < len(rp) else -9, p[k] if k < len(p) else -9))
                    if k < max(len(rp), len(p)) else '-', dmax))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
