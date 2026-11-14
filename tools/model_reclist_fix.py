"""Record list of the model DTPs (header +0x34 count, +0x38 pointer): 36-byte records on the Xbox, 40 bytes on the PC
(one u32 0 appended per record). Test 48d (2026-10-31): the converted doppelganger model DTP 20134 kept the Xbox
stride (section size unchanged, 75 records at +0x380, next block +0xe10), so the PC engine reads every record from
the second one on shifted by 4 * index and the last ones run into the next block.

Modes (from the repository root; read-only unless an output path is given):
  ../bin/pyt -t 1800 tools/model_reclist_fix.py proof all x            every base pair of work/generic/pairs.pkl
  ../bin/pyt -t 300  tools/model_reclist_fix.py proof XBOX.drm PC.drm  one pair
      per object model DTP (type-7 id reference at object +8) with a list: Xbox / PC stride, and per record whether
      the PC words 0-8 are a known conversion of the Xbox words (u32 swap, u16 pair, raw) and word 9 is 0
  ../bin/pyt -t 300  tools/model_reclist_fix.py check PC.drm [...]       stride of every model list in PC files
  ../bin/pyt -t 300  tools/model_reclist_fix.py fix PC.drm OUT.drm DTP_ID [--words XBOX.drm]
      re-space the 36-byte records of DTP_ID to 40 bytes (u32 0 appended), move every later byte, internal pointer
      slot / target, id reference slot and external relocation into the section by the size change; with --words
      also re-convert the record words with the proven classes from the Xbox original (words 0 / 3 / 4 u16 pairs,
      word 1 u32, word 5 DTP id mapped by section position); nothing else
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

XS, PS = 36, 40
# P4.4 K-3 (2026-11-14): the step reclist also takes model lists found by their head shape alone (not via object +8);
# base (work/p43_1411/k3_proof.py over work/generic/pairs.pkl, type-7 order pairing): 26 lists Xbox 36 -> PC 40
# (25 via +8, 1 by shape only), none kept at 36. Switch TRUDLC_RECLIST_SHAPE=off.
SHAPE_ALL = os.environ.get('TRUDLC_RECLIST_SHAPE', 'on') != 'off'


def a16(v): return (v + 15) & ~15


def model_list(s, e):
    """(start, count, next block start) of the +0x34 / +0x38 list, or None"""
    d = s.data
    if len(d) < 0x40: return None
    f = '>' if e == 'be' else '<'
    r = R.parse(bytes(s.reloc), e); tg = dict(r.internal)
    if 0x38 not in tg: return None
    n = struct.unpack_from(f + 'H', d, 0x34)[0]   # u16 count (+0x36 u16 0), as both platforms store it
    if not 0 < n < 0x1000: return None
    L = tg[0x38]
    later = sorted(t for t in tg.values() if t > L)
    nxt = later[0] if later else len(d)
    return L, n, nxt


def model_dtps(D, e):
    f = '>' if e == 'be' else '<'
    dtp = {s.id: s for s in D.sections if s.type == 7}
    out = []
    for s in [x for x in D.sections if x.type == 11]:
        ids = R.parse(bytes(s.reloc), e).id_offsets()
        if len(s.data) >= 12 and ids.get(8) == 7:
            m = dtp.get(struct.unpack_from(f + 'I', s.data, 8)[0])
            if m is not None: out.append((s.id, m))
    return out


def stride(L, n, nxt):
    for st in (PS, XS):
        if L + n * st <= nxt < a16(L + n * st) + 16: return st
    return None


def word_class(xw, pw):
    c = set()
    if pw == xw[::-1]: c.add('u32')
    if pw == xw[1::-1] + xw[:1:-1]: c.add('u16')
    if pw == xw: c.add('raw')
    return c


def proof(argv):
    import obj_eventlist_fix as OE
    st = collections.Counter(); cls = collections.defaultdict(collections.Counter); seen = set()
    for XD, PD in OE.base_pairs(argv[0], argv[1]):
        xm, pm = model_dtps(XD, 'be'), model_dtps(PD, 'le')
        if len(xm) != len(pm): st['object_count_differs'] += 1; continue
        for (xo, xs), (po, ps) in zip(xm, pm):
            if (xs.id, ps.id) in seen: continue
            seen.add((xs.id, ps.id))
            a, b = model_list(xs, 'be'), model_list(ps, 'le')
            if a is None or b is None: st['no_list'] += 1; continue
            if a[1] != b[1] or a[0] != b[0]: st['count_or_start_differs'] += 1; continue
            sx, sp = stride(*a), stride(*b)
            st['lists'] += 1; st['stride %s -> %s' % (sx, sp)] += 1
            if sx != XS or sp != PS: continue
            L, n = a[0], a[1]
            for k in range(n):
                xr = xs.data[L + k * XS:L + (k + 1) * XS]; pr = ps.data[L + k * PS:L + (k + 1) * PS]
                st['records'] += 1
                if pr[36:40] != b'\0\0\0\0': st['word9_not_zero'] += 1
                for j in range(9):
                    c = word_class(xr[4 * j:4 * j + 4], pr[4 * j:4 * j + 4])
                    cls[j]['+'.join(sorted(c)) or 'other'] += 1
    print('base model DTP lists: %s' % dict(st))
    for j in range(9): print('  word %d: %s' % (j, dict(cls[j].most_common(6))))


def check(argv):
    for p in argv:
        D = DW.read(open(p, 'rb').read(), 'le')
        for oid, s in model_dtps(D, 'le'):
            m = model_list(s, 'le')
            if m is None: continue
            print('%-36s object %5d model DTP %5d: %3d records at +%#x, next block +%#x -> stride %s'
                  % (os.path.basename(p), oid, s.id, m[1], m[0], m[2], stride(*m)))


def fix(argv):
    words_from = None
    if '--words' in argv: k = argv.index('--words'); words_from = argv[k + 1]; del argv[k:k + 2]
    src, out, sid = argv[0], argv[1], int(argv[2])
    raw = open(src, 'rb').read(); D = DW.read(raw, 'le')
    idx = next(i for i, s in enumerate(D.sections) if s.type == 7 and s.id == sid)
    s = D.sections[idx]
    L, n, E = model_list(s, 'le')
    assert stride(L, n, E) == XS, 'list is not in the 36-byte layout'
    d = s.data; endx = L + n * XS
    assert d[endx:E] == b'\0' * (E - endx), 'padding after the list is not zero'
    E2 = a16(L + n * PS); delta = E2 - E

    def mv(o):
        if o < L: return o
        if o < endx: k, r = divmod(o - L, XS); return L + k * PS + r
        assert o >= E, 'offset %#x in the padding' % o
        return o + delta

    recs = [bytearray(d[L + k * XS:L + (k + 1) * XS]) for k in range(n)]
    if words_from:
        # proven per-word classes (proof all x: 26 base lists, 782 records): words 0 / 3 / 4 u16 pairs, word 1 u32,
        # word 5 a type-7 DTP id (PC id: section at the same position of the same DRM pair); words 2 / 6 / 7 / 8 stay
        X = DW.read(open(words_from, 'rb').read(), 'be')
        xsec = next(x for x in X.sections if x.type == 7 and x.id == sid)
        xL, xn, _ = model_list(xsec, 'be'); assert (xL, xn) == (L, n), 'Xbox list differs'
        idmap = {}
        x7 = [x for x in X.sections if x.type == 7]; p7 = [x for x in D.sections if x.type == 7]
        if len(x7) == len(p7) and all(len(a.data) <= len(b.data) for a, b in zip(x7, p7)):
            idmap = {a.id: b.id for a, b in zip(x7, p7)}     # type-7 sections keep their order (and size, or grow)
        changed = collections.Counter()
        for k in range(n):
            xr = xsec.data[L + k * XS:L + (k + 1) * XS]
            for j in (0, 1, 2, 3, 4, 5):
                xw = xr[4 * j:4 * j + 4]
                if j == 2:      # base: u16 133 / raw 26, never u32 -> only a u32-swapped word is wrong
                    cur = bytes(recs[k][8:12])
                    if cur == xw[::-1] and cur != xw[1::-1] + xw[:1:-1] and cur != xw: want = xw[1::-1] + xw[:1:-1]
                    else: continue
                elif j == 1: want = xw[::-1]
                elif j == 5:
                    v = struct.unpack('>I', xw)[0]
                    if v == 0: want = b'\0\0\0\0'
                    elif v in idmap: want = struct.pack('<I', idmap[v])
                    else: changed['word5 id %d not mapped' % v] += 1; continue
                else: want = xw[1::-1] + xw[:1:-1]
                if bytes(recs[k][4 * j:4 * j + 4]) != want:
                    recs[k][4 * j:4 * j + 4] = want; changed['word %d' % j] += 1
        print('record words changed: %s' % dict(changed))
    nd = bytearray(d[:L])
    for k in range(n): nd += bytes(recs[k]) + b'\0\0\0\0'
    nd += b'\0' * (E2 - len(nd)) + d[E:]
    r = R.parse(bytes(s.reloc), 'le')
    r.internal = [(mv(o), mv(t)) for o, t in r.internal]
    r.idref_a = [(t, mv(o)) for t, o in r.idref_a]
    r.idref = [(t, mv(o)) for t, o in r.idref]
    moved_ext = 0
    for j, x in enumerate(D.sections):
        xr = R.parse(bytes(x.reloc), 'le')
        if j == idx:
            xr = r; xr.external = [(si, mv(so), (mv(do) if si == idx else do)) for si, so, do in xr.external]
            x.reloc = R.write(xr, 'le'); continue
        if any(si == idx for si, _, _ in xr.external):
            xr.external = [(si, so, (mv(do) if si == idx else do)) for si, so, do in xr.external]
            moved_ext += 1; x.reloc = R.write(xr, 'le')
    s.data = bytes(nd)
    open(out, 'wb').write(DW.cdrm_encode(D.write('le'), 'le'))
    B = DW.read(open(out, 'rb').read(), 'le'); b = B.sections[idx]
    m = model_list(b, 'le')
    print('DTP %d: %d records at +%#x, stride 36 -> 40, next block +%#x -> +%#x (+%d bytes), size %d -> %d, '
          'sections with external relocations into it: %d; read back: stride %s, reloc check %s'
          % (sid, n, L, E, E2, delta, len(d), len(b.data), moved_ext, stride(*m),
             R.check(R.parse(bytes(b.reloc), 'le'), len(b.data)) or 'ok'))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    {'proof': proof, 'check': check, 'fix': fix}[sys.argv[1]](sys.argv[2:])
