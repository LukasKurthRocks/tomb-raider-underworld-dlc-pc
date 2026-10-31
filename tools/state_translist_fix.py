"""State records of a player state chart and their u16 transition-index lists: check (and with --out repair) the PC
conversion against the Xbox original (read-only unless --out; TU state translation 2026-10-31, wall-run / rock-vein
transitions 607 / 608 never evaluated).

State record (0x28 bytes, both platforms, found in doppelganger_casual DTP 20212 and the base lara.drm):
  +0x00 u16 state id, +0x02 u16, +0x04 u16, +0x06 u16, +0x08 u16, +0x0a u16, +0x0c u16, +0x0e u16 transition count,
  +0x10 u32 0, +0x14 / +0x18 pointers, +0x1c = +0x20 pointer to the transition list, +0x24 u32 0.
Transition list = `count` u16 indices into the machine's transition pointer array (e.g. state 3 of DTP 20212: 61
entries at +0x4dec0, among them 88 / 89 = the rock-vein transitions {610, 610, 607} / {610, 610, 608}).
Correct PC bytes = every u16 byte-swapped on its own. Proof on the base pair (x_lara 12647 / pc_lara 850, different
offsets): every PC base list holds only indices below the transition count of its machine when read as LE u16.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/state_translist_fix.py XBOX_REF.drm PC_REF.drm XREF_ID PCREF_ID XBOX.drm PC.drm SID
      [--out OUT.drm] [--list N]
  e.g. work/rockvein/ref/x_lara.drm work/rockvein/ref/pc_lara.drm 12647 850 work/rockvein/ref/x_doppelganger_casual.drm
       work/rebuild/dlc2_asm_stage2b_sc/mods/doppelganger_casual.drm 20212
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def load(path, e, sid):
    D = DW.read(open(path, 'rb').read(), e)
    for s in D.sections:
        if s.id == sid and s.type == 7:
            return D, s
    raise SystemExit('DTP %d not in %s' % (sid, path))


def state_records(s, e):
    """[(offset, id, count, list_offset)] - 0x28-byte records with pointers at +0x14 / +0x18 / +0x1c / +0x20,
    +0x1c and +0x20 to the same target, +0x10 / +0x24 not pointers and zero"""
    f = '>' if e == 'be' else '<'
    d = bytes(s.data)
    it = dict(R.parse(bytes(s.reloc), e).internal)
    out = []
    for o in sorted(it):
        r = o - 0x1c
        if r < 0 or r % 4: continue
        if not all((r + k) in it for k in (0x14, 0x18, 0x1c, 0x20)): continue
        if it[r + 0x1c] != it[r + 0x20] or (r + 0x10) in it or (r + 0x24) in it: continue
        if struct.unpack_from(f + 'I', d, r + 0x10)[0] or struct.unpack_from(f + 'I', d, r + 0x24)[0]: continue
        sid, cnt = struct.unpack_from(f + 'H', d, r)[0], struct.unpack_from(f + 'H', d, r + 0xe)[0]
        out.append((r, sid, cnt, it[r + 0x1c]))
    return out


def lists(s, e, recs):
    f = '>' if e == 'be' else '<'
    d = bytes(s.data)
    return {r: list(struct.unpack_from(f + '%dH' % cnt, d, lo)) for r, sid, cnt, lo in recs if lo + 2 * cnt <= len(d)}


def main(argv):
    out_path = None; nlist = 20
    if '--out' in argv: k = argv.index('--out'); out_path = argv[k + 1]; del argv[k:k + 2]
    if '--list' in argv: k = argv.index('--list'); nlist = int(argv[k + 1]); del argv[k:k + 2]
    _, xb = load(argv[0], 'be', int(argv[2]))
    _, pb = load(argv[1], 'le', int(argv[3]))
    xbr, pbr = state_records(xb, 'be'), state_records(pb, 'le')
    xbl, pbl = lists(xb, 'be', xbr), lists(pb, 'le', pbr)
    def stats(name, recs, ls):
        n = sum(len(v) for v in ls.values())
        big = sum(1 for v in ls.values() for x in v if x >= 0x1000)
        print('%s: %d state records, %d list entries, %d entries >= 0x1000 (impossible index), max %d' % (
            name, len(recs), n, big, max([x for v in ls.values() for x in v] or [0])))
        return big
    stats('base Xbox %s' % argv[2], xbr, xbl)
    stats('base PC %s' % argv[3], pbr, pbl)
    # same state ids on both base charts: lists equal as multisets?
    xid = {sid: sorted(xbl[r]) for r, sid, cnt, lo in xbr if r in xbl}
    pid = {sid: sorted(pbl[r]) for r, sid, cnt, lo in pbr if r in pbl}
    common = set(xid) & set(pid)
    same = sum(1 for k in common if xid[k] == pid[k])
    print('base: %d state ids on both sides, %d with the same transition-index multiset' % (len(common), same))
    XD, xs = load(argv[4], 'be', int(argv[6]))
    PD, ps = load(argv[5], 'le', int(argv[6]))
    if len(xs.data) != len(ps.data): raise SystemExit('sizes differ - not the same layout')
    xr = state_records(xs, 'be')
    pr = {r for r, *_ in state_records(ps, 'le')}
    xl = lists(xs, 'be', xr)
    pdat = bytearray(ps.data)
    wrong_states, wrong_entries, total = [], 0, 0
    for r, sid, cnt, lo in xr:
        if r not in xl: continue
        want = struct.pack('<%dH' % cnt, *xl[r])
        total += cnt
        got = struct.unpack_from('<%dH' % cnt, pdat, lo)
        bad = sum(1 for a, b in zip(got, xl[r]) if a != b)
        hdr_want = struct.pack('<8H', *struct.unpack_from('>8H', bytes(xs.data), r))
        hdr_bad = bytes(pdat[r:r + 16]) != hdr_want
        if bad or hdr_bad:
            wrong_states.append((r, sid, cnt, lo, bad, hdr_bad, got, xl[r]))
            wrong_entries += bad
            pdat[lo:lo + 2 * cnt] = want
            # the 16 header bytes are only reported: their field types are not proven (u8 pairs possible)
    print('target DTP %s: %d state records (%d also found on the PC side), %d list entries; %d records with a wrong '
          'list or header, %d wrong entries' % (argv[6], len(xr), len(pr), total, len(wrong_states), wrong_entries))
    for r, sid, cnt, lo, bad, hdr_bad, got, want in wrong_states[:nlist]:
        print('  state %d (record +0x%05x, %d transitions at +0x%05x): %d wrong%s; Xbox %s; PC %s' % (
            sid, r, cnt, lo, bad, ', header wrong' if hdr_bad else '', ' '.join(map(str, want[:24])),
            ' '.join(map(str, got[:24]))))
    for r, sid, cnt, lo, bad, hdr_bad, got, want in wrong_states:
        if 88 in want and 89 in want:
            print('  -> the rock-vein transitions 88 / 89 are in the list of state %d: PC position of 88 = %s, '
                  'impossible indices before it on PC: %s' % (sid, got.index(88) if 88 in got else 'missing',
                  [x for x in got[:want.index(88)] if x >= 0x1000]))
    if out_path:
        ps.data = bytes(pdat)
        raw = PD.write('le')
        if open(argv[5], 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        open(out_path, 'wb').write(raw)
        chk = DW.read(open(out_path, 'rb').read(), 'le')
        assert len(chk.sections) == len(PD.sections)
        print('written %s (%d bytes, read back ok)' % (out_path, len(raw)))


if __name__ == '__main__':
    main(sys.argv[1:])
