"""Compare two script_diff reports (work/rebuild/script_diff_<label>.json): which differing words were fixed, which
remain, and which are NEW (identical to B138 before, different after) - the regression check for an experiment.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/script_diff_compare.py BEFORE_LABEL AFTER_LABEL [--prune CAND.json OUT.json]
  --prune: write the symbol candidates (symbol_guess_check.py --write) without those whose Xbox value appears in a
           new difference
"""
import sys, os, json, collections

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'rebuild')


def load(label):
    d = json.load(open(os.path.join(W, 'script_diff_%s.json' % label)))
    return {(rel, w[0], w[1]): w for rel, rows in d.items() for w in rows}


def main(argv):
    a, b = load(argv[0]), load(argv[1])
    fixed = set(a) - set(b); new = set(b) - set(a); both = set(a) & set(b)
    changed = [k for k in both if a[k][3] != b[k][3]]
    print('before %d, after %d differing words' % (len(a), len(b)))
    print('fixed (now = B138): %d' % len(fixed))
    print('still different: %d (of them our value changed: %d)' % (len(both), len(changed)))
    print('NEW differences (were = B138 before): %d' % len(new))
    for k in sorted(new)[:20]:
        rel, sid, off = k; w = b[k]
        print('   %s script %d +%#x xbox %s ours %s B138 %s' % (rel, sid, off, w[2], w[3], w[4]))
    per = collections.Counter(k[0] for k in new)
    if per: print('new differences per file:', dict(per.most_common(10)))
    if '--prune' in argv:
        # drop candidate symbols whose Xbox value sits in a NEW difference (the value means something else there)
        import struct
        cand_path, out_path = argv[argv.index('--prune') + 1], argv[argv.index('--prune') + 2]
        cand = json.load(open(cand_path)); bad = set()
        for k in new:
            xb = bytes.fromhex(b[k][2])
            for h in (0, 1): bad.add(struct.unpack_from('>H', xb, 2 * h)[0])
        kept = {x: v for x, v in cand.items() if int(x) not in bad}
        json.dump(kept, open(out_path, 'w'), indent=0)
        print('candidates %d, dropped %d (Xbox value in a new difference), kept %d -> %s' % (len(cand), len(cand) - len(kept), len(kept), out_path))


if __name__ == '__main__':
    main(sys.argv[1:])
