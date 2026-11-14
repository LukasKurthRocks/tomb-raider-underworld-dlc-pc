r"""P4.4 (14.11.): test files vs their source tree and vs the kits. Per file: changed sections (type:id, size before ->
after, words changed); for every changed section the number of words that differ from B270 / B138 (same type:id, same
size) before and after - the kit comparison of the touched classes.
Usage: ../bin/pyt -t 1800 work/p43_1411/p44_verify.py SRC_TREE TEST_TREE OUT.txt"""
import sys, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import drm_write as DW

KITS = {'B270': os.path.join(ROOT, 'work', 'b270_kit', 'mods'),
        'B138': os.path.join(ROOT, 'work', 'rebuild', 'pipeline_check_1011_repair', 'b138_pristine', 'mods')}


def find(tree, rel):
    p = os.path.join(tree, rel)
    if os.path.isfile(p): return p
    b = os.path.basename(rel).lower()
    for dp, dn, fn in os.walk(tree):
        dn[:] = [d for d in dn if 'truguard' not in d.lower()]
        for f in fn:
            if f.lower() == b: return os.path.join(dp, f)


def secs(p):
    D = DW.read(DW.cdrm_decode(open(p, 'rb').read(), 'le'), 'le')
    out = {}
    for s in D.sections: out.setdefault((s.type, s.id), bytes(s.data))
    return out


def ndiff(a, b):
    if a is None or b is None or len(a) != len(b): return None
    return sum(1 for o in range(0, len(a) - 3, 4) if a[o:o + 4] != b[o:o + 4])


def main(a):
    src, test, outp = a
    out = open(outp, 'w', encoding='utf-8', newline='\n'); tot = collections.Counter()
    for dp, dn, fn in os.walk(test):
        for f in sorted(fn):
            if not f.lower().endswith('.drm'): continue
            rel = os.path.relpath(os.path.join(dp, f), test)
            S, T = secs(find(src, rel)), secs(os.path.join(dp, f))
            K = {n: (secs(find(d, rel)) if find(d, rel) else None) for n, d in KITS.items()}
            ch = [k for k in T if S.get(k) != T[k]]
            out.write('%s: %d sections changed\n' % (rel, len(ch)))
            for k in ch:
                s, t = S.get(k), T[k]
                line = '   %d:%d size %s -> %d, words changed %s' % (k[0], k[1], len(s) if s else '-', len(t), ndiff(s, t))
                for n, Kd in K.items():
                    kd = Kd.get(k) if Kd else None
                    b4, af = ndiff(s, kd), ndiff(t, kd)
                    line += ' | %s: %s -> %s' % (n, '-' if b4 is None else b4, '-' if af is None else af)
                    if kd is not None and af is not None: tot['%s after' % n] += af
                    if kd is not None and b4 is not None: tot['%s before' % n] += b4
                    if kd is not None and len(kd) == len(t) and (s is None or len(s) != len(t)): tot['%s size now = kit' % n] += 1
                out.write(line + '\n')
            tot['files'] += 1; tot['sections'] += len(ch)
    out.write('SUMMARY %s\n' % dict(tot)); out.close(); print(dict(tot))


if __name__ == '__main__':
    main(sys.argv[1:])
