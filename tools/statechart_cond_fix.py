"""Typed re-conversion of the condition records of a player state chart DTP (finding 43, rock vein: DLC 2
doppelganger_casual.drm DTP 20212; read-only unless --out is given).

Record layout (8 bytes, both platforms; PC base lara.drm DTP 850 +0x700e0 `62 02 62 02 6a 02 00 00`):
  +0 u16 key (the id or its group, or 1000), +2 u16 id, +4 u16 value (SCCondTest_MarkupType: markup subtest
  601..628, PC tru+0x382819 movzx word [esi+4]), +6 u8 flags (bit 0 negates), +7 u8.
Correct PC bytes = u16, u16, u16 swapped, the two flag bytes kept. The generic converter turned many of these into one
u32 swap or left them raw (the value 607 / 608 became 24322 / 24578).

A record is recognised in the Xbox (big-endian) section at an 8-aligned offset when its id is a condition id of the
title update's tables (Lara's table and the generic table, read from the TU memory image) and the key is the id or the
id's group, or key == 1000 with id < 1000; relocated words are never touched. The same rule is first applied to a
reference pair (Xbox base lara.drm DTP 12647 vs PC lara.drm DTP 850): the multiset of records found in both must agree
after a u16/u16/u16/u8/u8 conversion - this proves the rule and the layout on the base game.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/statechart_cond_fix.py TU_IMAGE XBOX_REF.drm PC_REF.drm XREF_ID PCREF_ID XBOX.drm PC.drm SID [--out OUT.drm] [--list N]
  e.g. work/xenia_dump/tu_image_82000000.bin  ref/x_lara.drm ref/pc_lara.drm 12647 850
       ref/x_doppelganger_casual.drm mods/doppelganger_casual.drm 20212 --out work/rockvein/doppelganger_casual.drm
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

XBASE = 0x82000000
TU_TABLES = (0x8277f558, 0x82755f78)       # Lara's condition table, generic condition table (TU image)


def tu_ids(img):
    """{id: group} from the TU condition tables ({id, group, func} big-endian, closed by id 0)"""
    out = {}
    for va in TU_TABLES:
        o = va - XBASE
        while True:
            i, g, f = struct.unpack_from('>3I', img, o)
            if i == 0 or not (XBASE <= f < XBASE + len(img)): break
            out.setdefault(i, g); o += 12
    return out


def load(path, e, sid):
    D = DW.read(open(path, 'rb').read(), e)
    for s in D.sections:
        if s.id == sid and s.type == 7: return D, s
    raise SystemExit('DTP %d not in %s' % (sid, path))


def ptr_words(s, e):
    r = R.parse(bytes(s.reloc), e)
    return set(r.pointer_offsets()) | set(r.id_offsets())


def records(d, f, ids, skip):
    """[(offset, key, id, value, f6, f7)] of the 8-aligned condition records (f: '>' Xbox, '<' PC)"""
    out = []
    for o in range(0, len(d) - 8, 8):
        if o in skip or o + 4 in skip: continue
        k, i, v = struct.unpack_from(f + '3H', d, o)
        f6, f7 = d[o + 6], d[o + 7]
        if k == 1000:
            if not (0 < i < 1000): continue
        elif i not in ids or ids[i] == 0 or k not in (i, ids[i]):
            continue                                # group-0 ids (id 1: {0, 1, ..}) match other data - excluded
        if f7 != 0 or f6 > 0x0f: continue          # flag byte layout as in the PC base chart
        out.append((o, k, i, v, f6, f7))
    return out


def main(argv):
    out_path = None; nlist = 10
    if '--out' in argv: k = argv.index('--out'); out_path = argv[k + 1]; del argv[k:k + 2]
    if '--list' in argv: k = argv.index('--list'); nlist = int(argv[k + 1]); del argv[k:k + 2]
    img = open(argv[0], 'rb').read()
    ids = tu_ids(img)
    print('TU condition ids: %d' % len(ids))
    # 1. proof on the base game pair
    _, xs = load(argv[1], 'be', int(argv[3])); _, ps = load(argv[2], 'le', int(argv[4]))
    xr = records(bytes(xs.data), '>', ids, ptr_words(xs, 'be'))
    pr = records(bytes(ps.data), '<', ids, ptr_words(ps, 'le'))
    xc = collections.Counter(r[1:] for r in xr); pc = collections.Counter(r[1:] for r in pr)
    common = sum((xc & pc).values())
    print('reference: Xbox %d records, PC %d records, %d identical after u16/u16/u16/u8/u8 conversion '
          '(Xbox-only %d, PC-only %d)' % (len(xr), len(pr), common, len(xr) - common, len(pr) - common))
    if '--ref-detail' in argv:
        inter = xc & pc
        for i in sorted({r[1] for r in xc} | {r[1] for r in pc}):
            a = sum(v for r, v in xc.items() if r[1] == i); b = sum(v for r, v in pc.items() if r[1] == i)
            c = sum(v for r, v in inter.items() if r[1] == i)
            if a != c or b != c: print('    id %5d: Xbox %4d PC %4d common %4d' % (i, a, b, c))
    # 2. the converted DTP
    XD, xs2 = load(argv[5], 'be', int(argv[7])); PD, ps2 = load(argv[6], 'le', int(argv[7]))
    xd, pdat = bytes(xs2.data), bytearray(ps2.data)
    if len(xd) != len(pdat): raise SystemExit('sizes differ: 0x%x / 0x%x - not the same layout' % (len(xd), len(pdat)))
    skip = ptr_words(xs2, 'be') | ptr_words(ps2, 'le')
    recs = records(xd, '>', ids, skip)
    wrong = []
    for o, k, i, v, f6, f7 in recs:
        want = struct.pack('<3H', k, i, v) + bytes((f6, f7))
        if bytes(pdat[o:o + 8]) != want:
            got = struct.unpack_from('<3H', pdat, o) + (pdat[o + 6],)
            wrong.append((o, k, i, v, f6, got))
            pdat[o:o + 8] = want
    byid = collections.Counter(w[2] for w in wrong)
    print('target: %d records, %d wrong in the PC file (by id: %s)' % (len(recs), len(wrong),
          ', '.join('%d:%d' % kv for kv in sorted(byid.items()))))
    for o, k, i, v, f6, got in wrong[:nlist]:
        print('  +0x%05x  {%d, %d, %d, flags %d}  PC had {%d, %d, %d}' % (o, k, i, v, f6, got[0], got[1], got[2]))
    mk = collections.Counter()
    for o, k, i, v, f6, got in wrong:
        if 601 <= v <= 628 and i in (610, 611, 612, 613):
            mk[v] += 1
            if v in (607, 608):
                print('  markup record +0x%05x {%d, %d, %d, flags %d}: PC read value %d flags %d' % (o, k, i, v, f6, got[2],
                                                                                                    got[3]))
    print('markup subtests (610-613 records) corrected: ' + ', '.join('%d:%d' % kv for kv in sorted(mk.items())))
    if out_path:
        ps2.data = bytes(pdat)
        raw = PD.write('le')
        if open(argv[6], 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        open(out_path, 'wb').write(raw)
        chk = DW.read(open(out_path, 'rb').read(), 'le')        # read back: same sections, only DTP SID changed
        assert len(chk.sections) == len(PD.sections)
        print('written %s (%d bytes, read back ok)' % (out_path, len(raw)))


if __name__ == '__main__':
    main(sys.argv[1:])
