"""Show one section of a DLC DRM side by side: the Xbox source (read from the pack archive, big-endian) and a
converted PC file (little-endian), as 32-bit words around an offset - to see how the converter encoded each word
(s32 swap, two s16 swaps, raw). Read-only (finding 43: cloth iteration count of `co_dlc_lara.drm` DTP 24717).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/dlc_section_compare.py PACK NAME.drm SECTION_ID PC_FILE.drm OFFSET_HEX [WORDS]
  PACK: pack10 or pack11; the section is matched by id (PC id first, then the Xbox id at the same section index)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
from dlc_convert_all import PACK_PATHS
from archive import Archive
from names import load, L
from drm import cdrm_decode


def classify(x, p):
    """how the PC word p encodes the Xbox word x"""
    if x == p: return 'same'
    if x[::-1] == p and x[1::-1] + x[:1:-1] == p: return 's32=s16'     # equal u16 halves: both swaps agree
    if struct.unpack('>I', x)[0] == struct.unpack('<I', p)[0]: return 's32'
    if x[1::-1] + x[:1:-1] == p: return 's16'
    return 'other'


def main(argv):
    pack, name, sid, pcf, off = argv[0], argv[1], int(argv[2]), argv[3], int(argv[4], 16)
    words = int(argv[5]) if len(argv) > 5 else 16
    pi = [i for i, p in enumerate(PACK_PATHS) if pack in os.path.basename(p)][0]
    A = Archive(PACK_PATHS[pi], 'be'); xn = load(L + 'Tomb Raider Underworld (Xenon).txt')
    rec = [r for r in A.idx if xn.get(r['hash'], '').split('\\')[-1] == name]
    if not rec: raise SystemExit('%s not in %s' % (name, pack))
    X = DW.read(cdrm_decode(A.read(rec[-1]), 'be'), 'be')
    P = DW.read(open(pcf, 'rb').read(), 'le')
    k = [i for i, s in enumerate(P.sections) if s.id == sid]
    if not k: raise SystemExit('section %d not in %s' % (sid, pcf))
    k = k[0]; ps = P.sections[k]
    same = [s for s in X.sections if s.type == ps.type and s.id == sid]     # same id first (B138 reorders sections)
    if same: xs = same[0]
    elif k < len(X.sections) and X.sections[k].type == ps.type: xs = X.sections[k]   # id remapped: same index
    else: raise SystemExit('no Xbox section of type %d with id %d or at index %d' % (ps.type, sid, k))
    print('section %d: PC type %d id %d len %d | Xbox type %d id %d len %d' % (
        k, ps.type, ps.id, len(ps.data), xs.type, xs.id, len(xs.data)))
    a = max(0, off - words * 2) & ~3
    for o in range(a, min(len(ps.data), len(xs.data), a + words * 4), 4):
        x, p = xs.data[o:o + 4], ps.data[o:o + 4]
        print('  +0x%04x  xbox %s  pc %s  %-5s%s' % (o, x.hex(), p.hex(), classify(x, p), '  <==' if o == off else ''))


if __name__ == '__main__':
    main(sys.argv[1:])
