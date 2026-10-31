"""Find state-chart DTPs in Xbox DRMs and measure how many of their condition records a converted PC copy gets wrong
(read-only; finding 43, rock vein follow-up: is the DLC 2 player the only mis-converted chart?).

A state chart DTP is recognised by the header the base player's chart and the DLC 2 doppelganger's share: words 3..6 =
10000, 12000, 4000, 6000 (big-endian u32 at +0xc..+0x18). Condition records are counted with
tools/statechart_cond_fix.py's rule (ids of the TU's Lara + generic condition tables).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/statechart_scan.py TU_IMAGE XBOX_SOURCE PC_MODS_DIR [NAME.drm ...]
  XBOX_SOURCE: archive key of tools/locals.py (e.g. pack11); without names every PC mods\*.drm is tried
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC, drm_write as DW, drm_reloc as R
from archive import Archive
from names import crc
from drm import cdrm_decode
import statechart_cond_fix as SC

HDR = struct.pack('>4I', 10000, 12000, 4000, 6000)


def main(argv):
    ids = SC.tu_ids(open(argv[0], 'rb').read())
    path, e, pre = LC.SRC[argv[1]]
    A = Archive(path, e)
    mods = argv[2]
    names = argv[3:] or sorted(n for n in os.listdir(mods) if n.endswith('.drm'))
    for name in names:
        recs = A.find(crc(pre + '\\' + name))
        if not recs: continue
        try:
            X = DW.read(cdrm_decode(A.read(recs[0]), e), e)
            P = DW.read(open(os.path.join(mods, name), 'rb').read(), 'le')
        except Exception as ex:
            print('%s: not readable (%s)' % (name, ex)); continue
        pc = {(s.type, s.id): s for s in P.sections}
        for s in X.sections:
            if s.type != 7 or bytes(s.data[0xc:0x1c]) != HDR: continue
            p = pc.get((7, s.id))
            if p is None or len(p.data) != len(s.data):
                print('%s DTP %d: chart, no PC section of the same id / size' % (name, s.id)); continue
            xd, pd = bytes(s.data), bytes(p.data)
            skip = set(R.parse(bytes(s.reloc), 'be').pointer_offsets()) | set(R.parse(bytes(p.reloc), 'le').pointer_offsets())
            rr = SC.records(xd, '>', ids, skip)
            bad = sum(1 for o, k, i, v, f6, f7 in rr if pd[o:o + 8] != struct.pack('<3H', k, i, v) + bytes((f6, f7)))
            print('%s DTP %d: chart 0x%x bytes, %d condition records, %d wrong on PC' % (name, s.id, len(xd), len(rr), bad))


if __name__ == '__main__':
    main(sys.argv[1:])
