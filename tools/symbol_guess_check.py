"""Which guess rule for unmapped Xbox Symbols reproduces B138? (read-only, works on script_diff output)

For every differing u16 half of work/rebuild/script_diff_<label>.json whose Xbox value is an Xbox Symbol that is NOT
in our symbol map (work/generic/idmap.json key 100) and lies inside the base range, the candidates are computed:
  lower   m[a] + (xs - a)  with a = next mapped symbol below  (dlc_generic.DlcIds.sym 'guess_lower' / interpolation)
  upper   m[b] - (b - xs)  with b = next mapped symbol above
and compared with our value and B138's value.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/symbol_guess_check.py [LABEL]      default: stage2b
"""
import sys, os, json, struct, bisect, collections

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work')


def main(argv):
    label = argv[0] if argv else 'stage2b'
    m = {int(a): b for a, b in json.load(open(os.path.join(W, 'generic', 'idmap.json')))['100'].items()}
    ks = sorted(m)
    words = json.load(open(os.path.join(W, 'rebuild', 'script_diff_%s.json' % label)))
    st = collections.Counter(); seen = collections.Counter(); examples = {}
    for rel, rows in words.items():
        for sid, k, xw, o, r, co, cr in rows:
            xb, ob, rb = bytes.fromhex(xw), bytes.fromhex(o), bytes.fromhex(r)
            for h in (0, 1):
                ours = struct.unpack_from('<H', ob, 2 * h)[0]; b138 = struct.unpack_from('<H', rb, 2 * h)[0]
                if ours == b138: continue
                xs = struct.unpack_from('>H', xb, 2 * h)[0]      # BE halves keep their position (u16 pair)
                if xs in m or xs == 0 or not (ks[0] < xs < ks[-1]): continue
                i = bisect.bisect_left(ks, xs); a, b = ks[i - 1], ks[i]
                lower, upper = m[a] + xs - a, m[b] - (b - xs)
                kind = ('ours=lower ' if ours == lower else 'ours=other ') + \
                       ('B138=upper' if b138 == upper else 'B138=lower' if b138 == lower else 'B138=other')
                st[kind] += 1; seen[xs] += 1
                examples.setdefault(kind, (rel, sid, k, xs, (a, m[a]), (b, m[b]), ours, b138))
    print('differing halves with an unmapped base-range Xbox symbol: %d (%d distinct symbols)' % (sum(st.values()), len(seen)))
    for kind, n in st.most_common(): print('   %-24s %5d   e.g. %s' % (kind, n, examples[kind]))
    # per Xbox symbol: does B138 use ONE value everywhere, and is that value free in our map (not a PC symbol of
    # another Xbox symbol)? Such symbols are candidates for map entries; mixed values = not (only) a symbol field.
    per = collections.defaultdict(collections.Counter)
    for rel, rows in words.items():
        for sid, k, xw, o, r, co, cr in rows:
            xb, ob, rb = bytes.fromhex(xw), bytes.fromhex(o), bytes.fromhex(r)
            for h in (0, 1):
                ours = struct.unpack_from('<H', ob, 2 * h)[0]; b138 = struct.unpack_from('<H', rb, 2 * h)[0]
                xs = struct.unpack_from('>H', xb, 2 * h)[0]
                if ours != b138 and xs not in m and xs != 0 and ks[0] < xs < ks[-1]: per[xs][b138] += 1
    used = set(m.values())
    cons = {xs: c for xs, c in per.items() if len(c) == 1}
    free = {xs: next(iter(c)) for xs, c in cons.items() if next(iter(c)) not in used}
    mono = 0
    for xs, p in free.items():
        i = bisect.bisect_left(ks, xs); a, b = ks[i - 1], ks[i]
        mono += m[a] < p < m[b]
    print('per symbol: %d with one B138 value, %d of them free in our map, %d of those between the neighbours (monotone);'
          ' %d symbols with several B138 values' % (len(cons), len(free), mono, len(per) - len(cons)))
    if '--write' in argv:
        out = os.path.join(W, 'rebuild', 'symbol_candidates_%s.json' % label)
        json.dump({str(k): v for k, v in sorted(free.items())}, open(out, 'w'), indent=0)
        print('wrote', out)


if __name__ == '__main__':
    main(sys.argv[1:])
