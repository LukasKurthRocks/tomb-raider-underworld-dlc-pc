"""Dump the skeleton ('model' DTPs, word0 0x04c20453 / LE 0x5304c204) of character DRMs, read only (N22 stage 1).

Model DTP layout as tools/dlc_generic.py model_fix: header {.., u32 nseg @+4, ptr seg[] @+0xc}, segments 0x40 B (all u32
except a u16 pair @+0x34, HInfo* @+0x3c). This tool prints the header words and every segment's 16 words so the parent /
hierarchy field can be identified, and (with --summary) a skeleton signature per model.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/model_skeleton_dump.py raw PATH.drm le|be [--seg N]
  ../bin/pyt -t 300 tools/model_skeleton_dump.py pcbase NAME.drm [--seg N]      base PC bigfile (rung1.raw_pc)
  ../bin/pyt -t 300 tools/model_skeleton_dump.py xbase NAME.drm [--seg N]       base Xbox (rung1.raw_xbox)
  ../bin/pyt -t 300 tools/model_skeleton_dump.py xdlc NAME.drm [--seg N]        DLC Xbox pack (convert_dlc.raw_dlc)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

MAGIC_BE = bytes.fromhex('04c20453')


def load(src, name):
    if src == 'raw':
        return open(name, 'rb').read()
    if src == 'pcbase':
        import rung1
        return rung1.raw_pc(name)
    if src == 'xbase':
        import rung1
        return rung1.raw_xbox(name)
    if src == 'xdlc':
        import convert_dlc
        r = convert_dlc.raw_dlc(name)
        return r[0] if isinstance(r, tuple) else r
    raise SystemExit('unknown source ' + src)


def models(raw, e):
    """[(section id, nseg, header words, [segment word lists])] of every model DTP"""
    d = DW.read(raw, e)
    f = '>' if e == 'be' else '<'
    out = []
    for s in d.sections:
        if s.type != 7 or len(s.data) < 0x80:
            continue
        w0 = s.data[:4] if e == 'be' else s.data[:4][::-1]
        if w0 != MAGIC_BE:
            continue
        it = dict(R.parse(bytes(s.reloc), e).internal)
        n = struct.unpack_from(f + 'I', s.data, 4)[0]
        seg = it.get(0xc)
        hdr = list(struct.unpack_from(f + '28I', s.data, 0))
        segs = []
        if seg is not None and seg + 0x40 * n <= len(s.data):
            for j in range(n):
                e0 = seg + 0x40 * j
                ws = list(struct.unpack_from(f + '13I', s.data, e0))
                a, b = struct.unpack_from(f + '2H', s.data, e0 + 0x34)
                ws += [a, b, struct.unpack_from(f + 'I', s.data, e0 + 0x38)[0], 1 if (e0 + 0x3c) in it else 0]
                segs.append(ws)
        out.append((s.id, n, hdr, segs, len(s.data)))
    return out


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__)
        return 2
    src, name = a[0], a[1]
    e = 'be' if src in ('xbase', 'xdlc') else 'le'
    if src == 'raw':
        e = a[2]
    segsel = int(a[a.index('--seg') + 1]) if '--seg' in a else None
    raw = load(src, name)
    for sid, n, hdr, segs, size in models(raw, e):
        print('model DTP %d size 0x%x nseg %d' % (sid, size, n))
        print('  header u32: ' + ' '.join('%08x' % x for x in hdr[:24]))
        for j, ws in enumerate(segs):
            if segsel is not None and j != segsel:
                continue
            fl = [struct.unpack('<f', struct.pack('<I', x))[0] for x in ws[:12]]
            print('  seg %3d: f %s | w12 %08x | u16 %d %d | w38 %08x | hinfo %d' % (
                j, ' '.join('%.3g' % v for v in fl), ws[12], ws[13], ws[14], ws[15], ws[16]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
