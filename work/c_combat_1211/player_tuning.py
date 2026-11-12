"""Group C 12.11. (read-only): words of the player data block ([0xfad764] = lara DTP block, ENGINE 13.7) at given
offsets, as f32 / u32 / two u16. Readers of the offsets used in docs/Befund-Gruppe-C-1211.md (main workspace):
  +0x29c / +0x29e u16  lock-on switch repeat timers (tru+0x31ce69 / +0x31ce89 -> player +0x78c / +0x790)
  +0x2a0 f32           lock-on switch threshold (|stick + accumulator| squared compared at tru+0x31ceaa)
  +0x2a4 f32           lock-on switch dead zone (tru+0x31cdf9; below it bits 1 / 2 of CM+0x1fc are cleared)
  +0x2a8 u32           sound id played on a target switch (tru+0x31cf8b)
  +0x454 f32           strike pointer speed of the right stick (tru+0x2f2f91)
  +0x47c u32           parameter of the direction search tru+0x31a740 (tru+0x31cf50)
Usage (from trudlcport): ../bin/pyt work/c_combat_1211/player_tuning.py PC_LARA.drm 0x29c 0x2a0 ...
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW
import player_block_fix as PB

D = DW.read(open(sys.argv[1], 'rb').read(), 'le')
k, t, _ = PB.block(D, 'le')
data = D.sections[k].data
print('section %d block +0x%x' % (k, t))
for a in sys.argv[2:]:
    off = int(a, 16)
    f = struct.unpack_from('<f', data, t + off)[0]
    u = struct.unpack_from('<I', data, t + off)[0]
    lo, hi = struct.unpack_from('<HH', data, t + off)
    print('+0x%03x  f32 %-14.6g u32 0x%08x  u16 %d / %d' % (off, f, u, lo, hi))
