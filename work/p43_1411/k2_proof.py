r"""P4.4 K-2 (14.11.): base proof of costume_dtp_fix LISTCOUNT over EVERY base Xbox / PC DTP pair of dtp_audit.base_pairs
(not only the Lara costume DRMs): where the Xbox bytes have the LISTCOUNT struct (+0x04 -> +0x10, +0x10 u32 n,
+0x14 -> +0x30, exactly n pointer slots from +0x30), is the PC count the s32 of the Xbox count? Counts ok / contra and
the struct's spread (DRM names, n). Then the same struct in a tree (scan): which words the widened rule would write.
Usage: ../bin/pyt -t 3600 work/p43_1411/k2_proof.py OUT.txt [TREE]"""
import sys, os, collections, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import costume_dtp_fix as CF, dtp_audit as DA, drm_write as DW


def main(a):
    out = open(a[0], 'w', encoding='utf-8', newline='\n'); w = lambda s: (out.write(s + '\n'), out.flush())
    cnt = collections.Counter(); srcs = collections.Counter(); ns = collections.Counter()
    for x, p, xb, pc, xr in DA.base_pairs():
        it = dict(xr.internal)
        n = CF.listcount(xb['data'], it)
        if n is None: continue
        xw, pw = xb['data'][0x10:0x14], pc['data'][0x10:0x14]
        ok = pw == xw[::-1]
        cnt['ok' if ok else 'contra'] += 1; srcs[os.path.basename(str(xb['src']))[:40]] += 1; ns[n] += 1
        if not ok: w('CONTRA %s DTP %s/%s: Xbox %s PC %s' % (xb['src'], x, p, xw.hex(), pw.hex()))
    w('base LISTCOUNT pairs: %s' % dict(cnt))
    w('by source (top 20): %s' % srcs.most_common(20))
    w('n values: %s' % sorted(ns.items())[:40])
    if len(a) > 1:
        tot = collections.Counter()
        for rel, path in sorted(DA.overlay([os.path.abspath(a[1])], None).items()):
            try: xs, src = CF.load_xbox(os.path.basename(rel).lower())
            except (Exception, SystemExit) as e: tot['no_xbox'] += 1; continue
            if not xs: tot['no_xbox'] += 1; continue
            D = DW.read(DW.cdrm_decode(open(path, 'rb').read(), 'le'), 'le')
            for xsec, k in CF.pair_sections(xs, D):
                xd = xsec['data']; it = CF.internal(xsec['reloc'], 'be')
                n = CF.listcount(xd, it)
                if n is None: continue
                old = D.sections[k].data[0x10:0x14]; new = xd[0x10:0x14][::-1]
                tot['struct'] += 1
                if old != new:
                    tot['would_write'] += 1
                    w('TREE %s DTP %d: n %d, PC %d -> %d%s' % (rel, D.sections[k].id, n, struct.unpack('<I', old)[0], n,
                                                            ' (costume, already ruled)' if CF.is_costume(rel) else ''))
        w('tree %s: %s' % (a[1], dict(tot)))
    out.close(); print(dict(cnt))


if __name__ == '__main__':
    main(sys.argv[1:])
