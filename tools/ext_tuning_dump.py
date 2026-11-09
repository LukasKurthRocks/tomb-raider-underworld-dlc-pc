"""Dump the DLC 2 player tuning struct (object 858 `player_tru_dlc2_extension`, DTP 22497, struct at +0xf0) as floats
and u32, Xbox original next to a converted PC file (read-only; X23 09.11.2026: which tuning words drive the shadow
power's time-scale request slots - Start slot 0 {+0x40 player, +0x3c world}, slot 1 {+0x48, +0x44}, slot 2 {+0x50,
+0x4c}, slot 3 world +0x38, slot 4 {+0x58, +0x54}; drain +0x14, refill +0x18 / +0x1c / +0x20, cost +0x34).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/ext_tuning_dump.py XBOX.drm PC.drm [--from 0] [--to 0x80]
Output: one line per 4-byte word: offset, Xbox f32 / u32, PC f32 / u32, 'same' when the PC word is the Xbox value.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state_translist_fix as ST  # noqa: E402

SID = 22497
BASE = 0xf0


def words(path, e, lo, hi):
    _, s = ST.load(path, e, SID)
    d = bytes(s.data)
    f = '>' if e == 'be' else '<'
    out = []
    for o in range(lo, hi, 4):
        a = BASE + o
        if a + 4 > len(d):
            break
        out.append((o, struct.unpack_from(f + 'f', d, a)[0], struct.unpack_from(f + 'I', d, a)[0]))
    return out


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__)
        return 2
    lo, hi = 0, 0x80
    if '--from' in a:
        lo = int(a[a.index('--from') + 1], 0)
    if '--to' in a:
        hi = int(a[a.index('--to') + 1], 0)
    x = words(a[0], 'be', lo, hi)
    p = words(a[1], 'le', lo, hi)
    print('DTP %d struct +0x%x: Xbox %s | PC %s' % (SID, BASE, a[0], a[1]))
    for (o, xf, xu), (_, pf, pu) in zip(x, p):
        print('+0x%02x  X %12.4f 0x%08x | P %12.4f 0x%08x  %s' % (o, xf, xu, pf, pu, 'same' if xu == pu else 'DIFF'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
