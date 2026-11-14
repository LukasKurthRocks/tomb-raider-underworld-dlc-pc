"""F1 (2026-11-14): dump the streamgroup table of a unit DRM (Level+0x90 target) with its relocs. Read-only.
Usage (repository root): ../bin/pyt -t 120 work/f1_1411/f1_sgtable.py DRM [le|be]
"""
import sys, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm_write as DW
import drm_reloc as R

path = sys.argv[1]; e = sys.argv[2] if len(sys.argv) > 2 else 'le'
E = '<' if e == 'le' else '>'
D = DW.read(open(path, 'rb').read(), e); S = D.sections
ext = {so: (si, do) for si, so, do in R.parse(S[0].reloc, e).external}
si, do = ext[0x90]
d = S[si].data; r = R.parse(S[si].reloc, e)
print('Level+0x90 -> sec#%d type %d size %d at 0x%x' % (si, S[si].type, len(d), do))
print('internal', [(hex(a), hex(b)) for a, b in sorted(r.internal)][:40])
print('external', [(x, hex(a), hex(b)) for x, a, b in r.external][:40])
for o in range(do, min(len(d), do + 0xc0), 16):
    w = [struct.unpack_from(E + 'I', d, o + j)[0] for j in range(0, 16, 4) if o + j + 4 <= len(d)]
    print('  +0x%04x %s  %s' % (o, ' '.join('%08x' % x for x in w), bytes(d[o:o + 16]).replace(b'\x00', b'.').decode('latin1')))
