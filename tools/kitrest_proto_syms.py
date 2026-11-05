"""Xbox -> PC Symbol hints from the base generalbank pair: prototype name Symbols (u16 at proto +8) of every script
present in the Xbox generalbank (title update) and the original PC generalbank, paired by script id and prototype
INDEX (read-only; kit-rest task 3, workspace docs Befund-Kit-Reste-0511.md). Noisy: PC scripts may order their
prototypes differently, so this is a hint, not a proof (2026-11-05: 386 of 803 symbols disagree with
dlc_generic.DlcIds.sym, most of them from re-ordered prototype lists). Printed for the Symbols on the command line.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/kitrest_proto_syms.py [0xSYM ...] [--layer tu]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_conv as SC
import dtp_twin_field as TF
import dtp_word_classes as C


def names(d, rl, e):
    rel = R.parse(rl, 'be' if e == '>' else 'le')
    W = SC.Walk(d, rel, 'be' if e == '>' else 'le').run()
    out = {}
    for name, t, n, sz in W.arrays:
        if name == 'protos':
            for k in range(n): out[('proto', k)] = struct.unpack_from(e + 'H', d, t + k * sz + 8)[0]
    return out


def main(a):
    layer = 'tu'
    if '--layer' in a: k = a.index('--layer'); layer = a[k + 1]; del a[k:k + 2]
    want = [int(x, 16) for x in a]
    import dlc_generic as DG
    ids = DG.DlcIds()
    xs, _ = TF.load_named('generalbank', [layer], 'be')
    pcs = {s['id']: s for s in C.find(C.PC, 'le', 'pc-w' + chr(92) + 'generalbank.drm') if s['type'] == 8 and s['data']}
    ev = collections.defaultdict(collections.Counter)
    for x in xs:
        if x['type'] != 8 or not x['data'] or x['id'] not in pcs: continue
        try:
            xn = names(x['data'], x['reloc'], '>'); pn = names(pcs[x['id']]['data'], pcs[x['id']]['reloc'], '<')
        except Exception:
            continue
        for k, v in xn.items():
            if k in pn: ev[v][pn[k]] += 1
    print('Xbox symbols with prototype evidence: %d' % len(ev))
    bad = 0
    for v in sorted(ev):
        top = ev[v].most_common(1)[0]
        d = ids.sym(v)
        if d != top[0]: bad += 1
        if (want and v in want) or (not want and d != top[0] and len(ev[v]) == 1):
            print('  xbox 0x%04x: genuine PC %s | DlcIds.sym 0x%04x' % (v, ', '.join('0x%04x x%d' % kv for kv in ev[v].most_common()), d))
    print('symbols where the most common genuine PC value != DlcIds.sym: %d of %d' % (bad, len(ev)))
    for v in want:
        if v not in ev: print('  xbox 0x%04x: no prototype evidence in the base pair (DlcIds.sym 0x%04x)' % (v, ids.sym(v)))


if __name__ == '__main__':
    main(sys.argv[1:])
