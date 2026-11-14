r"""P4.4 K-3 (14.11.): model DTPs recognised by their head (word 0 = model magic 04c20453, +0x34 count, +0x38 list) in
the base pairs (obj_eventlist_fix.base_pairs, as model_reclist_fix proof): Xbox / PC stride of every list, split by
'reached via object +8' (today's reclist) and 'magic only' (second model copies such as DLC 24392). Then a tree: model
DTPs by magic that still have the Xbox stride 36 and are not reached via object +8.
Usage: ../bin/pyt -t 3600 work/p43_1411/k3_proof.py OUT.txt [TREE]"""
import sys, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import model_reclist_fix as MR, drm_write as DW, dtp_audit as DA

MAGIC = bytes.fromhex('04c20453')


def by_magic(D, e):
    """K-3 second try: the head shape alone (model_list: +0x34 u16 count, +0x38 internal pointer); env K3_MAGIC=1 for
    the word-0 magic of the costume model DTPs (first try: 0 base lists)"""
    if os.environ.get('K3_MAGIC') == '1':
        m = MAGIC if e == 'be' else MAGIC[::-1]
        return [s for s in D.sections if s.type == 7 and bytes(s.data[:4]) == m]
    return [s for s in D.sections if s.type == 7 and MR.model_list(s, e) is not None]


def main(a):
    import obj_eventlist_fix as OE
    out = open(a[0], 'w', encoding='utf-8', newline='\n'); w = lambda s: (out.write(s + '\n'), out.flush())
    st = collections.Counter(); seen = set()
    for XD, PD in OE.base_pairs('all', 'x'):
        via = {s.id for _, s in MR.model_dtps(XD, 'be')}
        x7 = [s for s in XD.sections if s.type == 7]; p7 = [s for s in PD.sections if s.type == 7]
        if len(x7) != len(p7): st['type7_count_differs'] += 1; continue
        P = {id(x): p for x, p in zip(x7, p7)}          # base PC ids are renumbered: pair by type-7 order
        for xs in by_magic(XD, 'be'):
            ps = P.get(id(xs))
            if ps is None or (xs.id, len(xs.data)) in seen: continue
            seen.add((xs.id, len(xs.data)))
            a_, b_ = MR.model_list(xs, 'be'), MR.model_list(ps, 'le')
            if a_ is None or b_ is None: st['no_list'] += 1; continue
            k = 'via+8' if xs.id in via else 'magic_only'
            st['%s stride %s -> %s' % (k, MR.stride(*a_), MR.stride(*b_))] += 1
    w('base model DTPs by magic (id-paired): %s' % dict(st))
    if len(a) > 1:
        tot = collections.Counter()
        for rel, path in sorted(DA.overlay([os.path.abspath(a[1])], None).items()):
            D = DW.read(DW.cdrm_decode(open(path, 'rb').read(), 'le'), 'le')
            via = {s.id for _, s in MR.model_dtps(D, 'le')}
            for s in by_magic(D, 'le'):
                m = MR.model_list(s, 'le')
                if m is None: continue
                sx = MR.stride(*m); tot['%s stride %s' % ('via+8' if s.id in via else 'magic_only', sx)] += 1
                if s.id not in via and sx == MR.XS: w('TREE %s DTP %d: %d records at +%#x, stride 36 (not reached via +8)' % (rel, s.id, m[1], m[0]))
        w('tree: %s' % dict(tot))
    out.close()


if __name__ == '__main__':
    main(sys.argv[1:])
