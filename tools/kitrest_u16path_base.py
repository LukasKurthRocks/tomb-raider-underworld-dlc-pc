"""Inline u16 arrays (UI timeline target paths, member Symbols) on the genuine base pair: Xbox generalbank (title
update / disc layers) vs the original PC generalbank (read-only; kit-rest task 3, workspace docs
Befund-Kit-Reste-0511.md).

For every script id present on both sides, every inline u16 array of the Xbox section (tools/script_u16array_check
pattern {u32 n, ptr -> next word, u16[n]}) whose offset is also an array on the PC side (same count word, internal
pointer to the next word): the PC elements read as u16 in Xbox order are compared with
  (a) the Xbox elements mapped by the base Symbol map (dlc_generic.DlcIds.base[SYM], the map learned from base
      pairs) - 'u16order' when every mapped element matches in place, 's32order' when they match only after the
      two u16 of each word trade places, else 'other';
  (b) dlc_generic.DlcIds.sym (what tools/script_u16array_fix / the pipeline step uipath writes) incl. its route.
Prints per array, a summary, and every Xbox Symbol whose genuine PC value differs from DlcIds.sym.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/kitrest_u16path_base.py [--layer tu|xbase2|xbase] [--show N]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import dtp_twin_field as TF
import dtp_word_classes as C
from script_u16array_check import arrays


def route(ids, v):
    before = dict(ids.sym_stats); r = ids.sym(v)
    k = [x for x in ids.sym_stats if ids.sym_stats[x] != before.get(x, 0)]
    return r, (k[0] if k else '?')


def main(a):
    layer, show = 'tu', 40
    if '--layer' in a: k = a.index('--layer'); layer = a[k + 1]; del a[k:k + 2]
    if '--show' in a: k = a.index('--show'); show = int(a[k + 1]); del a[k:k + 2]
    import dlc_generic as DG
    ids = DG.DlcIds(); SYM = 100
    bmap = ids.base.get(SYM, {})
    xs, _ = TF.load_named('generalbank', [layer], 'be')
    pcs = {s['id']: s for s in C.find(C.PC, 'le', 'pc-w' + chr(92) + 'generalbank.drm') if s['type'] == 8 and s['data']}
    st = collections.Counter(); diffs = {}; lines = []
    for x in xs:
        if x['type'] != 8 or not x['data'] or x['id'] not in pcs: continue
        p = pcs[x['id']]; xd = x['data']; pd = p['data']
        xr = R.parse(x['reloc'], 'be'); pr = R.parse(p['reloc'], 'le'); pit = dict(pr.internal)
        # aligned prefix: the internal relocations (source, target) agree on both sides up to offset L
        # (every pair with both ends below L is on both sides; a differing pair has an end at or above L)
        L = min(len(xd), len(pd))
        for a1, b1 in set(xr.internal) ^ set(pr.internal): L = min(L, max(a1, b1))
        st['scripts'] += 1
        if L == min(len(xd), len(pd)) and len(xd) == len(pd): st['scripts with identical relocation layout'] += 1
        for co, n, t, words in arrays(xd, xr):
            if t + 4 * words > len(pd) or pit.get(co + 4) != t or struct.unpack_from('<I', pd, co)[0] != n:
                st['not an array at the same PC offset'] += 1; continue
            if t + 4 * words > L:
                st['array behind the aligned prefix (layout differs)'] += 1; continue
            xv = list(struct.unpack_from('>%dH' % (2 * words), xd, t))[:n]
            pv_u16 = list(struct.unpack_from('<%dH' % (2 * words), pd, t))
            pv = pv_u16[:n]
            pv_s32 = []
            for k in range(words):            # whole-word swap: the two u16 of each word trade places
                a0, a1 = pv_u16[2 * k], pv_u16[2 * k + 1]; pv_s32 += [a1, a0]
            pv_s32 = pv_s32[:n]
            mapped = [bmap.get(v) for v in xv]
            if None in mapped: kind = 'unmapped element'
            elif mapped == pv: kind = 'u16order'
            elif mapped == pv_s32: kind = 's32order'
            elif xv == pv: kind = 'raw-values u16order'
            elif sorted(pv) == sorted(mapped): kind = 'other order'
            else: kind = 'other'
            st[kind] += 1
            # element mapping evidence in u16 order (the order the base pair shows for most arrays)
            for xe, pe in zip(xv, pv):
                d, rt = route(ids, xe)
                if d != pe: diffs.setdefault(xe, set()).add((pe, d, rt, bmap.get(xe)))
            if len(lines) < show or kind not in ('u16order',):
                lines.append('script %d +0x%x n=%d xbox %s | pc %s | base-map %s | %s' % (
                    x['id'], t, n, ' '.join('%04x' % v for v in xv), ' '.join('%04x' % v for v in pv),
                    ' '.join('%04x' % v if v is not None else '----' for v in mapped), kind))
    for l in lines: print(l)
    print('\nlayer %s: %s' % (layer, dict(st)))
    print('Xbox Symbols whose genuine PC element (u16 order) differs from DlcIds.sym: %d' % len(diffs))
    for xe in sorted(diffs):
        for pe, d, rt, bm in sorted(diffs[xe]):
            print('  xbox 0x%04x: genuine PC 0x%04x | DlcIds.sym 0x%04x (%s) | base map %s' % (
                xe, pe, d, rt, ('0x%04x' % bm) if bm is not None else '-'))


if __name__ == '__main__':
    main(sys.argv[1:])
