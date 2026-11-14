r"""P4.3 base proof (14.11.) for the three new tu_perlight rules (visibility lane of the Xbox BRDF := 1, folded PC
visibility -> radiance = product of factors x colour, chunk-1 tail = colour / accumulator instructions only). For every base lit pair (Xbox lib XB, its real PC twin PB =
donor, F9.lit_pairs) and slots 0 / 2 / 6 (no shadow / shadow / shadow + sun permutations):
  * build with both rules OFF and ON; a build that succeeds OFF must give the same program ON (no regression);
  * where only ON builds (the new rules fire), the built shader is compared in the VM with the REAL PC lib PB
    (tu_perlight.compare2, as `oracle`): lights off / all on / mixed / b0 (shadow light 0) / b3 (non-shadow light 0) /
    b6 (sun) - this covers the shadow sub-blocks the Xbox-lit reference of the build does not light.
Usage: ../bin/pyt -t 5400 work/p43_1411/rad_fold_proof.py OUT.txt [--limit N]"""
import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import tu_perlight as TP
from tu_light_transplant import F9, sm3asm, libs
import f9_common


def build(xblob, pdblob, xnames, on):
    TP.VIS_RULE = TP.RAD_RULE = TP.TAIL_RULE = on
    log = []
    try:
        return TP.build(xblob, pdblob, xnames, log), log, None
    except (TP.Fail, F9.Fail) as e:
        return None, log, str(e)
    except Exception as e:
        return None, log, '%s %s' % (type(e).__name__, e)


def main(a):
    outp = a[0]; lim = int(a[a.index('--limit') + 1]) if '--limit' in a else None
    L = libs(); X, PL = L['X'], L['P']
    pairs = F9.lit_pairs()
    if lim: pairs = pairs[:lim]
    out = open(outp, 'w', encoding='utf-8', newline='\n'); w = lambda s: (out.write(s + '\n'), out.flush())
    t0 = time.time(); n = dict(both_ok=0, both_fail=0, regress=0, changed=0, new_ok=0, new_pass=0, new_bad=0, skipped=0)
    w('lit base pairs: %d' % len(pairs))
    for xb, pb in pairs:
        mt = f9_common.material_pairs(xb, pb)
        for slot in (0, 2, 6):
            if xb not in X or pb not in PL or PL[pb]['slots'][slot] == 0xffffffff or X[xb]['slots'][slot & 1] == 0xffffffff:
                n['skipped'] += 1; continue
            xblob = X[xb]['entries'][X[xb]['slots'][slot & 1]]['blob']; pbblob = PL[pb]['entries'][PL[pb]['slots'][slot]]['blob']
            xnames = {nm: ri for nm, rs, ri, rc in F9.pc_ctab(pbblob) if rs == 3}
            T0, lg0, e0 = build(xblob, pbblob, xnames, False)
            T1, lg1, e1 = build(xblob, pbblob, xnames, True)
            fired = [l for l in lg1 if l.startswith('P4.3')]
            if T0 is not None:
                if T1 is None: n['regress'] += 1; w('REGRESS %d/%d slot %d: %s' % (xb, pb, slot, e1)); continue
                same = sm3asm.encode(T0) == sm3asm.encode(T1)
                n['both_ok' if same else 'changed'] += 1
                if not same and mt:
                    Pb = F9.decode_pc(pbblob); sc = []
                    for T_ in (T0, T1):
                        sc.append({lab: TP.compare2(T_, Pb, mt[0][2], mt[0][3], bl) for lab, bl in
                                   (('off', {}), ('on', F9.ALLB), ('b0', {0: True}), ('b3', {3: True}), ('b6', {6: True}))})
                    better = min(sc[1].values()) >= min(sc[0].values()) - 1e-9
                    n['changed_better_or_equal' if better else 'changed_worse'] += 1
                    w('CHANGED %d/%d slot %d: old %s | new %s | %s' % (xb, pb, slot, ' '.join('%s=%.3f' % kv for kv in sc[0].items()),
                                                                   ' '.join('%s=%.3f' % kv for kv in sc[1].items()), '; '.join(fired)[:200]))
                elif not same: w('CHANGED %d/%d slot %d (%s)' % (xb, pb, slot, fired))
                continue
            if T1 is None:
                n['both_fail'] += 1
                if fired: w('still refused %d/%d slot %d after %s: %s' % (xb, pb, slot, fired, e1[:160]))
                continue
            n['new_ok'] += 1
            if not mt: w('NEW %d/%d slot %d builds (%s) - no base material for the VM compare' % (xb, pb, slot, fired)); continue
            Pb = F9.decode_pc(pbblob)
            res = {lab: TP.compare2(T1, Pb, mt[0][2], mt[0][3], bl) for lab, bl in
                   (('off', {}), ('on', F9.ALLB), ('mixed', {0: True, 3: True, 6: True}), ('b0', {0: True}), ('b3', {3: True}), ('b6', {6: True}))}
            ok = min(res.values()) >= 0.999
            n['new_pass' if ok else 'new_bad'] += 1
            w('NEW %s %d/%d slot %d: %s | was: %s | %s' % ('PASS' if ok else 'BAD ', xb, pb, slot, ' '.join('%s=%.3f' % kv for kv in res.items()),
                                                        (e0 or '')[:90], '; '.join(fired)[:300]))
    w('SUMMARY %s (%.0f s)' % (' '.join('%s=%d' % kv for kv in n.items()), time.time() - t0))
    out.close(); print('SUMMARY %s' % n)
    return 1 if n['regress'] or n.get('changed_worse') or n['new_bad'] else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
