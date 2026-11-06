"""Scan the collision meshes of every base-game level unit in a PC archive for face clientFlags bits (read-only;
2026-11-06 debug render mode, workspace docs\\Befund-Debug-Rendermodus-0611.md).

Background (tru.exe, static): the player ground probe 0x5dd356 asks 0x5d3af0(result, 0x44, 0xa00): for a terrain hit
(result type 1) it returns u16 [face + 0x0e] & 0x44 (= IndexedFace.clientFlags, layout in tools/collision_faces.py);
bit 0x04 -> slope-slide kind 2, bit 0x40 -> kind 1 (written to playerstate +0x11d0, read by PSCCF_OnSlopeSlide
0x763670). A second probe 0x5dd44a asks mask 0x20. This tool counts, per unit, the faces with each clientFlags bit
and the slope range of the flagged faces, so the debug view knows how common the flags are.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/collision_flag_scan.py SOURCE UNITLIST.txt [--bits 0x04,0x40,0x20] [--only l2_]
  SOURCE as in tools/locals.py (pcbig, pcpatch; pcpatch is tried first for every unit when SOURCE = pc)
  UNITLIST: one unit path per line (e.g. work/b270_kit/mods/tr8/pc-w/unitlist.txt); only lines starting with
  'levels' are used
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC, drm_write as DW, drm_reloc as R
import collision_faces as CF
from archive import Archive
from names import crc
from drm import cdrm_decode


def open_src(name):
    path, e, pre = LC.SRC[name]
    return Archive(path, e), e, pre


def read_unit(srcs, unit):
    for A, e, pre in srcs:
        recs = A.find(crc(pre + '\\' + unit + '.drm'))
        if recs: return cdrm_decode(A.read(recs[-1]), e)
    return None


def main(argv):
    bits = [0x04, 0x40, 0x20]
    only = None
    if '--bits' in argv: k = argv.index('--bits'); bits = [int(x, 0) for x in argv[k + 1].split(',')]; del argv[k:k + 2]
    if '--only' in argv: k = argv.index('--only'); only = argv[k + 1]; del argv[k:k + 2]
    src, lst = argv[0], argv[1]
    srcs = [open_src('pcpatch'), open_src('pcbig')] if src == 'pc' else [open_src(src)]
    units = [l.strip().split('\\')[-1] for l in open(lst, encoding='latin-1') if l.strip().startswith('levels')]
    tot = {b: 0 for b in bits}; tot_units = {b: 0 for b in bits}; nunits = 0; nfaces = 0
    for u in units:
        if only and only not in u: continue
        raw = read_unit(srcs, u)
        if raw is None: print('%-34s not found' % u); continue
        D = DW.read(raw, 'le')
        rel = []
        for s in D.sections:
            r = R.parse(s.reloc, 'le')
            rel.append((dict(r.internal), {so: (si, do) for si, so, do in r.external}))
        M = CF.meshes(D, rel)
        F = []
        for gi, gid, ms, mo, h in M:
            F += [f for f in CF.faces(D, h) if f[5] is not None]
        nunits += 1; nfaces += len(F)
        parts = []
        for b in bits:
            hit = [f for f in F if (f[3] >> 16) & b]
            if hit:
                tot[b] += len(hit); tot_units[b] += 1
                sl = [f[6] for f in hit]
                parts.append('0x%02x: %d (slope %.0f..%.0f, materials %s)' % (
                    b, len(hit), min(sl), max(sl), ','.join('%d' % m for m in sorted({f[4] for f in hit}))))
            else:
                parts.append('0x%02x: 0' % b)
        print('%-34s meshes %2d faces %6d   %s' % (u, len(M), len(F), '   '.join(parts)))
    print('TOTAL %d units, %d faces; %s' % (nunits, nfaces, '  '.join(
        'clientFlags 0x%02x: %d faces in %d units' % (b, tot[b], tot_units[b]) for b in bits)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
