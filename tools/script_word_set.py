"""Set single 32-bit words of a script section (type 8) in a PC DRM, each only when its current value is the expected
one (read-only on IN, writes OUT). Finding 43: the DLC loading-screen title record in the ported title-update script 6
of generalbank has 0 where Crystal's PC records (base title 51, retail hint records) have 0x00010000 - the text
element is drawn every frame but invisibly.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/script_word_set.py IN.drm OUT.drm SCRIPT_ID OFFSET_HEX=OLD_HEX:NEW_HEX[,...]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def main(argv):
    inp, out, sid = argv[0], argv[1], int(argv[2])
    raw = open(inp, 'rb').read(); D = DW.read(raw, 'le')
    s = next(x for x in D.sections if x.type == 8 and x.id == sid)
    d = bytearray(s.data)
    for item in argv[3].split(','):
        off, vals = item.split('='); old, new = (int(v, 16) for v in vals.split(':')); off = int(off, 16)
        cur = struct.unpack_from('<I', d, off)[0]
        if cur != old: raise SystemExit('script %d +%#x is %08x, expected %08x - nothing written' % (sid, off, cur, old))
        struct.pack_into('<I', d, off, new); print('script %d +%#x: %08x -> %08x' % (sid, off, old, new))
    s.data = bytes(d)
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)


if __name__ == '__main__':
    main(sys.argv[1:])
