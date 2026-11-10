"""Check the 0x17c-byte particle / FX records of an object against its Xbox original by the reader's access widths
(read-only; X24 "steam at the stones" in dlc_yggdrasil_end, 2026-11-10).

The record reader 0x543f70 (ENGINE.md 2, "Particle / FX record reader"; record = [objdata +0x10] + i * 0x17c,
i < u16 [objdata +0x0c]) reads every record word as one dword, as u16 halves or as single bytes. ACCESS below is its
access list (17o field list `work/d17o_0811/p2_fields.txt`, from the disassembly 0x543fc2..0x545566): per word offset the
(byte, width) pairs the reader uses. For each read byte the PC byte must be the Xbox byte moved the way that width moves
it on a little-endian machine (dword: reversed, u16: the two bytes swapped, byte: in place). Words the reader never
reads, relocated pointers and id references are skipped. A mismatch means the converted record is read differently
from the Xbox one (colour, size, rate, flags ...); 0 mismatches = the converted particle data is the Xbox data.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/fx_record_check.py XBOX.drm PC.drm [-v]
      XBOX.drm = the Xbox original (big-endian, e.g. from tools/dlc_raw_extract.py), PC.drm = the converted file.
      Prints per object data DTP the record count on both sides, per record the mismatching words; -v also prints
      the words that match (with the Xbox value as float where the reader reads a dword).
Exit 0 = no mismatch, 1 = mismatches, 2 = usage / structure problem.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import objdata_rec_classes as RC

_D, _W, _B = 4, 2, 1
# word offset -> [(byte, width)] read by 0x543f70 (p2_fields.txt); offsets not listed are not read by it
ACCESS = {}
for _o in (0x00, 0x10, 0x14, 0x18, 0x1c, 0x20, 0x24, 0x28, 0x2c, 0x30, 0x34, 0x38, 0x3c, 0x48, 0x4c, 0x50, 0x54, 0x60,
           0x64, 0x6c, 0x74, 0x78, 0x80, 0x8c, 0x98, 0x9c, 0xa0, 0xa4, 0xb8, 0xbc, 0xc4, 0xc8, 0xd4, 0xd8, 0xdc, 0xe0,
           0xe4, 0xe8, 0xec, 0xf8, 0xfc, 0x100, 0x104, 0x108, 0x10c, 0x110, 0x114, 0x118, 0x120, 0x124, 0x128, 0x130,
           0x134, 0x138, 0x13c, 0x140, 0x144, 0x158, 0x168, 0x16c, 0x170):
    ACCESS[_o] = [(0, _D)]
for _o in (0x04, 0xac, 0xb0, 0xf0, 0x11c, 0x174):
    ACCESS[_o] = [(0, _B), (1, _B), (2, _B), (3, _B)]
for _o in (0x40, 0x70, 0x90):
    ACCESS[_o] = [(0, _B), (1, _B), (2, _B)]
for _o in (0x68, 0x88):
    ACCESS[_o] = [(0, _B), (1, _B)]
for _o in (0x7c, 0x12c, 0x14c):
    ACCESS[_o] = [(0, _B)]
for _o in (0x0c, 0xc0, 0xd0, 0x150, 0x154, 0x164):
    ACCESS[_o] = [(0, _W)]
for _o in (0x44, 0x84, 0x94, 0xa8, 0xcc, 0xf4, 0x160):
    ACCESS[_o] = [(0, _W), (2, _W)]
ACCESS[0x08] = [(0, _B), (2, _W)]
ACCESS[0x58] = [(0, _B), (1, _B), (2, _W)]
ACCESS[0x15c] = [(0, _B), (1, _B), (2, _W)]
ACCESS[0x148] = [(0, _B), (1, _B), (2, _W)]       # the reader also reads byte 2 alone; the u16 rule covers byte 2


def expected(xw, acc):
    """PC bytes the reader expects for Xbox word xw: {byte index: value}"""
    out = {}
    for b, w in acc:
        if w == _D:
            for i in range(4): out[i] = xw[3 - i]
        elif w == _W:
            out[b], out[b + 1] = xw[b + 1], xw[b]
        else:
            out[b] = xw[b]
    return out


def objdata(path, e):
    D = DW.read(open(path, 'rb').read(), e)
    get = lambda s: (s.type, s.data, s.reloc, s.id)
    out = []
    for sid in RC.objdata_dtps(D.sections, e, get):
        sec = [s for s in D.sections if s.type == 7 and s.id == sid]
        if sec: out.append((sid, sec[0]))
    return out


def main():
    a = sys.argv[1:]
    verbose = '-v' in a
    a = [x for x in a if x != '-v']
    if len(a) != 2:
        print(__doc__)
        return 2
    X, P = objdata(a[0], 'be'), objdata(a[1], 'le')
    if not X or not P or len(X) != len(P):
        print('object data DTPs: Xbox %s, PC %s - cannot pair' % ([i for i, _ in X], [i for i, _ in P]))
        return 2
    bad = 0
    for (xi, xs), (pi, ps) in zip(X, P):
        xr, xsl = RC.records(xs.data, 'be', xs.reloc)
        pr, psl = RC.records(ps.data, 'le', ps.reloc)
        print('object data Xbox DTP %d / PC DTP %d: records Xbox %s, PC %s' % (
            xi, pi, len(xr) if xr else None, len(pr) if pr else None))
        if not xr or not pr or len(xr) != len(pr):
            print('  record lists differ - not compared'); bad += 1; continue
        for k, (bx, bp) in enumerate(zip(xr, pr)):
            nbad = nread = 0
            for o, acc in sorted(ACCESS.items()):
                if (bx + o) in xsl or (bp + o) in psl:
                    continue
                xw, pw = xs.data[bx + o:bx + o + 4], ps.data[bp + o:bp + o + 4]
                exp = expected(xw, acc)
                nread += 1
                ok = all(pw[i] == v for i, v in exp.items())
                if not ok:
                    nbad += 1
                    print('  rec %2d +%#05x Xbox %s PC %s reader %s -> MISMATCH (expected %s)' % (
                        k, o, xw.hex(), pw.hex(), acc, ''.join('%02x' % exp.get(i, pw[i]) for i in range(4))))
                elif verbose:
                    f = struct.unpack('>f', xw)[0] if acc == [(0, _D)] else None
                    print('  rec %2d +%#05x Xbox %s PC %s ok%s' % (k, o, xw.hex(), pw.hex(), (' (f %.6g)' % f) if f is not None else ''))
            bad += nbad
            print('  rec %2d: %d read words compared, %d mismatch' % (k, nread, nbad))
    print('total mismatches: %d' % bad)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
