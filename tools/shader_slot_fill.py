"""EXPERIMENT tool: let empty permutation slots of a PC ShaderLib (type 9) point at the entry of another slot of the
same library (only the slot table changes; several slots may share one entry - shaderlib.py). Finding 43 follow-up:
PC vertex-shader library 1595 (base eitr water surface) lacks slots 40-42 / 104-106 / 168-170 / 232-234 that the
Xbox 822 has (bits 8 + 32, most likely "second UV set + vertex colour"); the DLC 2 waterfall needs that variant, so
the PC falls back to one without vertex colour and the fall is opaque. Filling 40 <- 32 etc. keeps the vertex alpha
(at the cost of the second UV set's effect).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/shader_slot_fill.py IN.drm OUT.drm LIB_ID DST=SRC[,DST=SRC...]   (refuses occupied DST)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
from shaderlib import parse


def main(argv):
    inp, out, lid = argv[0], argv[1], int(argv[2])
    pairs = [tuple(int(v) for v in p.split('=')) for p in argv[3].split(',')]
    raw = open(inp, 'rb').read(); D = DW.read(raw, 'le')
    s = next(x for x in D.sections if x.type == 9 and x.id == lid)
    lib = parse(s.data, 'le'); d = bytearray(s.data)
    for dst, src in pairs:
        if lib['slots'][dst] != 0xffffffff: raise SystemExit('slot %d is occupied' % dst)
        if lib['slots'][src] == 0xffffffff: raise SystemExit('slot %d is empty' % src)
        struct.pack_into('<I', d, 12 + 4 * dst, lib['slots'][src]); print('lib %d slot %d -> entry of slot %d' % (lid, dst, src))
    s.data = bytes(d)
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)


if __name__ == '__main__':
    main(sys.argv[1:])
