"""Check (and with --out repair) every condition record a state chart's transitions point at, by the transition layout
instead of by recognising records by their ids (read-only unless --out; wall run 2026-11-02, condition 528 audit).

Why: tools/statechart_cond_fix.py recognises a record only when its key is the id, the id's group or 1000. Records
such as {800, 501, 1} (key 800, id 501, group 500 - used next to 528 in the transitions to the aim states 113 / 114 /
115 / 150) do not match that rule; in the converted DLC 2 chart (doppelganger_casual.drm DTP 20212) they were left
u32-swapped and read {501, 800, 0, NOT} on PC.

Layouts used (both proven on the base pair x_lara.drm 12647 / pc_lara.drm 850, see docs Befund-Felsrinne):
  transition = 20 bytes {u16 target, u16, u16 count, u16, ptr conditions (+8), ptr (+0xc), u32} (tools/shape_proof.py,
  2 573 / 2 574); condition record = 8 bytes {u16 key, u16 id, u16 value, u8 flags, u8} (6 427 / 6 427).
A transition is a relocation-target block of exactly 0x14 bytes with relocated words at +8 and +0xc (as
tools/chart_transitions.py); its list = `count` records at the +8 target. Correct PC bytes of a record = the Xbox
u16 / u16 / u16 swapped, the two flag bytes kept.

Step 1 (proof): the same walk over the base pair; the multisets of converted Xbox records and PC records must agree.
Step 2: the target pair (same DTP size, same relocations); every listed record compared; --out writes the repaired
PC file (CDRM kept), read back.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/chart_condlist_fix.py XBOX_REF.drm PC_REF.drm XREF_ID PCREF_ID XBOX.drm PC.drm SID
        [--out OUT.drm] [--list N]
  e.g. work/rockvein/ref/x_lara.drm work/rockvein/ref/pc_lara.drm 12647 850
       work/rockvein/ref/x_doppelganger_casual.drm <mods>/doppelganger_casual.drm 20212
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def load(path, e, sid):
    D = DW.read(open(path, 'rb').read(), e)
    for s in D.sections:
        if s.id == sid and s.type == 7: return D, s
    raise SystemExit('DTP %d not in %s' % (sid, path))


def lists(s, e):
    """{list offset: record count} of every transition's condition list (count = max over the transitions)"""
    f = '>' if e == 'be' else '<'
    d = bytes(s.data); it = dict(R.parse(bytes(s.reloc), e).internal)
    t = sorted(set(it.values()) | {0})
    out = {}
    ntr = 0
    for k, a in enumerate(t):
        end = t[k + 1] if k + 1 < len(t) else len(d)
        if end - a != 0x14 or (a + 8) not in it or (a + 0xc) not in it: continue
        ntr += 1
        cnt = struct.unpack_from(f + 'H', d, a + 4)[0]
        if cnt > 64: continue
        c0 = it[a + 8]
        out[c0] = max(out.get(c0, 0), cnt)
    return out, ntr


def recs(d, f, ls):
    """[(offset, key, id, value, f6, f7)] of all listed records (each offset once)"""
    seen = {}
    for c0, n in ls.items():
        for j in range(n):
            o = c0 + 8 * j
            if o + 8 > len(d) or o in seen: continue
            k, i, v = struct.unpack_from(f + '3H', d, o)
            seen[o] = (o, k, i, v, d[o + 6], d[o + 7])
    return [seen[o] for o in sorted(seen)]


def main(argv):
    out_path = None; nlist = 40
    if '--out' in argv: k = argv.index('--out'); out_path = argv[k + 1]; del argv[k:k + 2]
    if '--list' in argv: k = argv.index('--list'); nlist = int(argv[k + 1]); del argv[k:k + 2]
    # 1. proof on the base pair
    _, xs = load(argv[0], 'be', int(argv[2])); _, ps = load(argv[1], 'le', int(argv[3]))
    xl, xn = lists(xs, 'be'); pl, pn = lists(ps, 'le')
    xr = recs(bytes(xs.data), '>', xl); pr = recs(bytes(ps.data), '<', pl)
    xc = collections.Counter(r[1:] for r in xr); pc = collections.Counter(r[1:] for r in pr)
    common = sum((xc & pc).values())
    print('reference: Xbox %d transitions / %d lists / %d records, PC %d / %d / %d; %d identical after the '
          'u16/u16/u16/u8/u8 conversion (Xbox-only %d, PC-only %d)' % (xn, len(xl), len(xr), pn, len(pl), len(pr),
                                                                       common, len(xr) - common, len(pr) - common))
    odd = collections.Counter(r[1:3] for r in xr if r[1] not in (r[2], 1000) and r[1] != r[2] - r[2] % 100)
    print('reference: records whose key is not the id / 1000 / the id rounded to 100: %d (e.g. %s)' % (
        sum(odd.values()), ', '.join('{%d,%d}x%d' % (a, b, n) for (a, b), n in odd.most_common(8))))
    # 2. target
    XD, xs2 = load(argv[4], 'be', int(argv[6])); PD, ps2 = load(argv[5], 'le', int(argv[6]))
    xd, pdat = bytes(xs2.data), bytearray(ps2.data)
    if len(xd) != len(pdat): raise SystemExit('sizes differ: 0x%x / 0x%x - not the same layout' % (len(xd), len(pdat)))
    xl2, xn2 = lists(xs2, 'be'); pl2, pn2 = lists(ps2, 'le')
    if set(xl2) != set(pl2):
        print('WARNING: list offsets differ Xbox %d / PC %d (only the Xbox walk is used)' % (len(xl2), len(pl2)))
    rr = recs(xd, '>', xl2)
    wrong = []
    for o, k, i, v, f6, f7 in rr:
        want = struct.pack('<3H', k, i, v) + bytes((f6, f7))
        if bytes(pdat[o:o + 8]) != want:
            got = struct.unpack_from('<3H', pdat, o) + (pdat[o + 6],)
            wrong.append((o, k, i, v, f6, got))
            pdat[o:o + 8] = want
    byid = collections.Counter((w[1], w[2]) for w in wrong)
    print('target: %d transitions, %d lists, %d records; %d wrong in the PC file' % (xn2, len(xl2), len(rr), len(wrong)))
    print('  wrong by {key,id}: ' + ', '.join('{%d,%d}:%d' % (a, b, n) for (a, b), n in sorted(byid.items())))
    for o, k, i, v, f6, got in wrong[:nlist]:
        print('  +0x%05x  {%d, %d, %d%s}  PC had {%d, %d, %d%s}' % (o, k, i, v, ',NOT' if f6 & 1 else '', got[0], got[1],
                                                                   got[2], ',NOT' if got[3] & 1 else ''))
    if out_path:
        ps2.data = bytes(pdat)
        raw = PD.write('le')
        if open(argv[5], 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        open(out_path, 'wb').write(raw)
        chk = DW.read(open(out_path, 'rb').read(), 'le')
        assert len(chk.sections) == len(PD.sections)
        c2 = [q for q in chk.sections if q.id == int(argv[6]) and q.type == 7][0]
        assert bytes(c2.data) == bytes(pdat)
        print('written %s (%d bytes, read back ok)' % (out_path, len(raw)))


if __name__ == '__main__':
    main(sys.argv[1:])
