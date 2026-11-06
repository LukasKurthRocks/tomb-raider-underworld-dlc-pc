"""Level fog / underwater environment block per unit (read-only; 2026-11-06 thalassophobia - feasibility of an
accessibility option against fear of deep water, docs Befund-Thalassophobie-0611.md).

The PC exe reads the fog of the camera's unit in 0x5c1f50 (PC partner of the prototype's TERRAIN_GetUnitFog):
level = [streamUnit+8], block P = [level+0x70]. Above water it uses colour bytes P+0x18..0x1a and the floats
P+0x38 / P+0x3c / P+0x40; when the camera is below the water surface (0x5ea200 = 1) it uses colour bytes
P+0x1c..0x1e and the floats P+0x44 / P+0x48 / P+0x4c (near = P+0x4c, far = P+0x48 or P+0x44 when P+0x48 is 0).
The per-frame environment code 0x5c7ca0 starts the sound referenced by P+0x68 when the camera goes under water and
the one of P+0x6c when it comes up again (0x535eb0). This tool prints those fields from the unit DRMs (Level =
section 0, its +0x70 pointer resolved through the relocations), plus the raw first 0x80 bytes of P, so the
interpretation can be checked. Nothing is written.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/thalasso_level_fog.py --src pc UNIT [UNIT ...]       (PC archives: pcpatch, then pcbig)
  ../bin/pyt -t 600 tools/thalasso_level_fog.py PATH.drm [PATH.drm ...]        (unit DRM files, e.g. our DLC trees)
  add --raw to print the first 0x80 bytes of the block as dwords.
Exit code 0 = read, 2 = usage error.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC
from archive import Archive
from names import crc
from drm import cdrm_decode
import drm_write as DW, drm_reloc as R


def unit_bytes(archives, unit):
    for src, A, pre in archives:
        recs = A.find(crc(pre + '\\' + unit + '.drm'))
        if recs: return src, cdrm_decode(A.read(recs[-1]), 'le')
    return None, None


def target(sec, off):
    """(section index or None for internal, data offset) of the pointer at off in sec, or None."""
    rx = R.parse(sec.reloc, 'le')
    for si, so, do in rx.external:
        if so == off: return si, do
    for so, do in rx.internal:
        if so == off: return None, do
    return None


def report(label, data, raw):
    D = DW.read(data, 'le')
    secs = D.sections
    if not secs or secs[0].type != 0:
        print('== %s: not a unit DRM' % label); return
    t = target(secs[0], 0x70)
    if t is None:
        print('== %s: Level+0x70 has no relocation' % label); return
    si, do = t
    s = secs[0] if si is None else secs[si]
    p = s.data
    if p is None or do + 0x80 > len(p):
        print('== %s: block out of range (sec %s +0x%x)' % (label, si, do)); return
    f = lambda o: struct.unpack_from('<f', p, do + o)[0]
    b = lambda o: p[do + o]
    pr = target(s, do + 0x68), target(s, do + 0x6c)
    print('== %s: block in section %s (type %d, id %d) +0x%x' % (label, si, s.type, s.id, do))
    print('   above water: colour %3d %3d %3d  floats +38 %.0f  +3c %.0f  +40(near) %.0f' % (
        b(0x18), b(0x19), b(0x1a), f(0x38), f(0x3c), f(0x40)))
    print('   under water: colour %3d %3d %3d  floats +44 %.0f  +48 %.0f  +4c(near) %.0f  byte +1f %d' % (
        b(0x1c), b(0x1d), b(0x1e), f(0x44), f(0x48), f(0x4c), b(0x1f)))
    w68, w6c = struct.unpack_from('<II', p, do + 0x68)
    print('   +68 0x%08x reloc %s   +6c 0x%08x reloc %s' % (w68, pr[0], w6c, pr[1]))
    if do + 0x94 <= len(p):
        # 0x5c78a0 (called by the per-frame code) picks P+0x88 / P+0x90 when the camera is under water, else
        # P+0x84 / P+0x8c, looks the id up in the table at 0xc36f28 (0x54df80) and pushes (entry, weight) into the
        # 5-slot list 0xadb694 (0x52c480, sound module) - printed raw, meaning inferred
        i84, i88 = struct.unpack_from('<II', p, do + 0x84)
        print('   +84 id %d (above)  +88 id %d (under)  +8c %.3g  +90 %.3g' % (i84, i88, f(0x8c), f(0x90)))
    if raw:
        for k in range(0, 0x80, 0x10):
            w = struct.unpack_from('<4I', p, do + k)
            print('   +%02x  %s' % (k, ' '.join('%08x' % x for x in w)))


def main(argv):
    argv = list(argv)
    raw = '--raw' in argv
    if raw: argv.remove('--raw')
    src = None
    if '--src' in argv:
        i = argv.index('--src'); src = argv[i + 1]; del argv[i:i + 2]
    if not argv: print(__doc__); return 2
    if src:
        order = ['pcpatch', 'pcbig'] if src == 'pc' else [src]
        archives = []
        for s in order:
            path, e, pre = LC.SRC[s]
            if e != 'le': print('only little-endian (PC) sources'); return 2
            if os.path.exists(path): archives.append((s, Archive(path, e), pre))
        for unit in argv:
            s, data = unit_bytes(archives, unit.lower())
            if data is None: print('== %s: not found' % unit); continue
            report('%s [%s]' % (unit, s), data, raw)
    else:
        for path in argv:
            if not os.path.isfile(path): print('== %s: no such file' % path); continue
            report(os.path.basename(path), open(path, 'rb').read(), raw)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
