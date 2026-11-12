"""Group F (Q78): find the GlobalInfo DTP of a PC generalbank (the one whose +0x144 / +0x148 hold the camera-settings
ids 20 / 21, ENGINE.md "camera settings") and print chosen u32 fields of it, then the floats of the DTPs they name
(read-only).

FreeCamera (vtable 0x855e54) reads its tuning from 0x54df80([[0xe7ee50]+0x134]) (0x5f914b / 0x5f91f2 / 0x5f930d):
S = result + 0x10 = DTP data; S+0x5c x 0x843070 = FOV (0x5f915f), S+0x60 roll, S+0x64 / +0x68 / +0x6c / +0x70 speed
pairs (0x5f9360..0x5f937b), S+0x1c look tuning (0x5f93ab).

Usage (from the repository root):
  ../bin/pyt -t 120 work/f_func_1211/globalinfo_ids.py GENERALBANK.drm [OFF,OFF,...]   (hex, default 0x134,0x144)
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW


def main(argv):
    D = DW.read(open(argv[0], 'rb').read(), 'le')
    offs = [int(x, 16) for x in (argv[1].split(',') if len(argv) > 1 else ['0x134', '0x144'])]
    by_id = {}
    for s in D.sections:
        if s.type == 7: by_id.setdefault(s.id, s)
    # [0xe7ee50] = GlobalInfo = DTP 2 data + 0xf0 (ENGINE.md "Camera curve tables": Xbox DTP 2 +0x254 = GI+0x164)
    GI = 0xf0
    gi = [s for s in D.sections if s.type == 7 and len(s.data) > GI + 0x150
          and struct.unpack_from('<I', bytes(s.data), GI + 0x144)[0] == 20
          and struct.unpack_from('<I', bytes(s.data), GI + 0x148)[0] == 21]
    if not gi:
        print('no GlobalInfo candidate (GI+0x144 == 20 and GI+0x148 == 21)'); return 1
    for g in gi:
        d = bytes(g.data)
        print('GlobalInfo candidate: DTP id %d size 0x%x (GI = data + 0x%x)' % (g.id, len(d), GI))
        for o in offs:
            v = struct.unpack_from('<I', d, GI + o)[0]
            print('  +0x%03x = %d (0x%x)' % (o, v, v))
            t = by_id.get(v)
            if t is None: print('    no type-7 section with that id'); continue
            td = bytes(t.data)
            print('    DTP %d size 0x%x' % (v, len(td)))
            for k in range(0, min(len(td), 0x90), 4):
                w = struct.unpack_from('<I', td, k)[0]
                f = struct.unpack_from('<f', td, k)[0]
                fs = ('%.6g' % f) if (w == 0 or 1e-6 < abs(f) < 1e8) else ''
                print('      +0x%02x  %08x  %s' % (k, w, fs))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
