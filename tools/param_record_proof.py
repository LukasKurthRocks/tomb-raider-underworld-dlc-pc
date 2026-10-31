"""Typed parameter records of a player state chart: {u16 id, u16 type, 4-byte value whose byte order depends on type}
(finding 43, rock vein: doppelganger_casual.drm DTP 20212, e.g. +0x4b980 {601, 12, float 360.0}). Read-only unless
--out is given.

Candidates are 8-aligned 8-byte records in the Xbox data with id 100..3000, type 1..63, type != id, that are not
condition records (statechart_cond_fix's rule) and whose words are not relocated. For every type the value
conversion ('w' u32 swap, 'r' raw bytes, 'hh' two u16, 'hr' u16 + 2 bytes) is chosen that makes the multiset of the
converted Xbox base records (lara.drm 12647) equal to the PC base records (850); a type counts as proven when that
conversion matches >= MIN % of its Xbox records and at least N records. Only proven types are applied to the target.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/param_record_proof.py TU_IMAGE XREF.drm PCREF.drm XREF_ID PCREF_ID XBOX.drm PC.drm SID
        [--min 98] [--n 5] [--out OUT.drm]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import statechart_cond_fix as SC

CONV = {'w': lambda v: v[::-1], 'r': lambda v: v, 'hh': lambda v: v[1::-1] + v[3:1:-1], 'hr': lambda v: v[1::-1] + v[2:]}


def cands(d, f, ids, skip):
    cond = {r[0] for r in SC.records(d, f, ids, skip)}
    out = []
    for o in range(0, len(d) - 8, 8):
        if o in cond or o in skip or o + 4 in skip: continue
        i, t = struct.unpack_from(f + 'HH', d, o)
        if 100 <= i <= 3000 and 1 <= t <= 63 and t != i:
            out.append((o, i, t))
    return out


def main(argv):
    mn, nmin, out = 98.0, 5, None
    if '--min' in argv: k = argv.index('--min'); mn = float(argv[k + 1]); del argv[k:k + 2]
    if '--n' in argv: k = argv.index('--n'); nmin = int(argv[k + 1]); del argv[k:k + 2]
    if '--out' in argv: k = argv.index('--out'); out = argv[k + 1]; del argv[k:k + 2]
    ids = SC.tu_ids(open(argv[0], 'rb').read())
    _, xs = SC.load(argv[1], 'be', int(argv[3])); _, ps = SC.load(argv[2], 'le', int(argv[4]))
    xd, pd = bytes(xs.data), bytes(ps.data)
    xc = cands(xd, '>', ids, SC.ptr_words(xs, 'be')); pc = cands(pd, '<', ids, SC.ptr_words(ps, 'le'))
    pset = collections.defaultdict(collections.Counter)
    for o, i, t in pc: pset[t][(i, pd[o + 4:o + 8])] += 1
    byt = collections.defaultdict(list)
    for o, i, t in xc: byt[t].append((i, xd[o + 4:o + 8]))
    proven = {}
    print('reference candidates: Xbox %d, PC %d' % (len(xc), len(pc)))
    for t in sorted(byt):
        lst = byt[t]
        best = None
        for name, fn in CONV.items():
            c = collections.Counter((i, fn(v)) for i, v in lst)
            m = sum((c & pset[t]).values())
            if best is None or m > best[1]: best = (name, m)
        # a conversion that ties with another on every record (e.g. all-zero values) proves nothing
        ties = [n for n, fn in CONV.items() if n != best[0] and
                sum((collections.Counter((i, fn(v)) for i, v in lst) & pset[t]).values()) == best[1]]
        rate = 100.0 * best[1] / len(lst)
        ok = rate >= mn and len(lst) >= nmin
        if ok: proven[t] = best[0] if not ties else tuple([best[0]] + ties)
        print('  type %2d: Xbox %5d PC %5d  best %-2s %5d (%.1f %%)%s%s' % (t, len(lst), sum(pset[t].values()), best[0],
              best[1], rate, ' ties ' + ','.join(ties) if ties else '', '  PROVEN' if ok else ''))
    _, xs2 = SC.load(argv[5], 'be', int(argv[7])); PD, ps2 = SC.load(argv[6], 'le', int(argv[7]))
    xd2, pd2 = bytes(xs2.data), bytearray(ps2.data)
    skip = SC.ptr_words(xs2, 'be') | SC.ptr_words(ps2, 'le')
    tc = cands(xd2, '>', ids, skip)
    ch = collections.Counter(); seen = collections.Counter()
    for o, i, t in tc:
        m = proven.get(t)
        if m is None: continue
        v = xd2[o + 4:o + 8]
        outs = {CONV[n](v) for n in (m if isinstance(m, tuple) else (m,))}
        if len(outs) != 1: continue
        y = struct.pack('<HH', i, t) + outs.pop()
        seen[t] += 1
        if bytes(pd2[o:o + 8]) != y:
            ch[t] += 1; pd2[o:o + 8] = y
    print('target: %d candidates; applied types %s; changed records by type: %s' % (
        len(tc), ','.join(str(t) for t in sorted(proven)), ', '.join('%d:%d/%d' % (t, ch[t], seen[t]) for t in sorted(seen))))
    if out:
        ps2.data = bytes(pd2)
        raw = PD.write('le')
        if open(argv[6], 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        open(out, 'wb').write(raw); DW.read(open(out, 'rb').read(), 'le')
        print('written %s' % out)


if __name__ == '__main__':
    main(sys.argv[1:])
