"""Find PowerPC code that copies a SIGNED BYTE field of one structure into a word field of another (read-only;
F5 groan loop 2026-11-05: does the Xbox SoundPlex Sequence constructor read the repeat count as a byte at data+0xc,
like the PC constructor tru+0x18e070 `movsx ecx, byte [data+0xc]; mov [obj+0x18], ecx`?).

Pattern (window of --window instructions, default 6): `lbz rX, SRC(rA)` -> `extsb rX|rY, rX` -> `stw rY, DST(rB)`.
Also reported without extsb (plain lbz -> stw, marked 'unsigned') so a u8 reader is not missed. All code sections of
the image (tools/xbox_image_sections.py) are scanned word by word.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/ppc_sbyte_field_copy.py IMAGE SRC DST [--window 6]
        e.g. work/xenia_dump/tu_image_82000000.bin 0xc 0x18
Each hit: address of the lbz, the three decoded instructions, and the .pdata function start when known ('?').
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xbox_image_sections as XS

BASE = 0x82000000


def dec(w):
    op = w >> 26
    rd = (w >> 21) & 31; ra = (w >> 16) & 31; d = w & 0xffff
    if d & 0x8000: d -= 0x10000
    if op == 34: return ('lbz', rd, ra, d)
    if op == 36: return ('stw', rd, ra, d)
    if op == 31 and ((w >> 1) & 0x3ff) == 954: return ('extsb', ra, rd, 0)     # extsb rA, rS -> (dst, src)
    return None


def main(argv):
    if len(argv) < 3: sys.exit(__doc__)
    path, src, dst = argv[0], int(argv[1], 0), int(argv[2], 0)
    win = int(argv[argv.index('--window') + 1]) if '--window' in argv else 6
    d = open(path, 'rb').read()
    hits = 0
    for name, start, size, ch in XS.sections(d, BASE):
        if not ch & 0x20: continue
        off = start - BASE
        n = min(size, len(d) - off) // 4
        words = struct.unpack_from('>%dI' % n, d, off)
        for i, w in enumerate(words):
            a = dec(w)
            if not a or a[0] != 'lbz' or a[3] != src: continue
            reg = a[1]; signed = False; txt = ['lbz r%d, 0x%x(r%d)' % (a[1], src, a[2])]
            for j in range(i + 1, min(i + 1 + win, n)):
                b = dec(words[j])
                if b is None: continue
                if b[0] == 'extsb' and b[2] == reg:
                    signed = True; reg = b[1]; txt.append('extsb r%d, r%d' % (b[1], b[2])); continue
                if b[0] == 'stw' and b[1] == reg and b[3] == dst:
                    txt.append('stw r%d, 0x%x(r%d)' % (b[1], dst, b[2]))
                    hits += 1
                    print('0x%08x %-8s %s   %s' % (start + 4 * i, 'signed' if signed else 'unsigned', name,
                                                   ' ; '.join(txt)))
                    break
                if b[0] == 'lbz' and b[1] == reg: break
    print('hits', hits)


if __name__ == '__main__':
    main(sys.argv[1:])
