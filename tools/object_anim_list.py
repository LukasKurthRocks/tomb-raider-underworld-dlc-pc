"""Animation list of character objects (object DTP: u16/u32 count @+0x5c, ptr @+0x60, 0x24-byte entries; ENGINE.md
"Object load (0x54e200)", "Anim request 0x444ba0"), read only (N22 stage 1).

Finds every type-7 section whose root has an internal pointer at +0x60 and a plausible count at +0x5c, then prints the
count and the entries (hex words) - the entry layout is identified from the output, the run-time reader 0x444ba0
indexes `[[Object+0x58]] + i * 0x24`.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/object_anim_list.py raw PATH.drm le|be [--all]
  ../bin/pyt -t 300 tools/object_anim_list.py pcbase|xbase|xdlc NAME.drm [--all]
  --all prints every entry (default: first 8)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import model_skeleton_dump as M


def anim_lists(raw, e):
    """[(section id, count, list offset, [entry bytes], section, internal map, section type map)]"""
    d = DW.read(raw, e)
    f = '>' if e == 'be' else '<'
    out = []
    for s in d.sections:
        if s.type != 7 or len(s.data) < 0x64:
            continue
        rel = R.parse(bytes(s.reloc), e)
        it = dict(rel.internal)
        if 0x60 not in it:
            continue
        c32 = struct.unpack_from(f + 'I', s.data, 0x5c)[0]
        c16 = struct.unpack_from(f + 'H', s.data, 0x5c)[0] if e == 'le' else struct.unpack_from(f + 'H', s.data, 0x5e)[0]
        n = c32 if 0 < c32 < 2000 else (c16 if 0 < c16 < 2000 else 0)
        p = it[0x60]
        if not n or p + 0x24 * n > len(s.data):
            continue
        ents = [bytes(s.data[p + 0x24 * k:p + 0x24 * (k + 1)]) for k in range(n)]
        out.append((s.id, n, p, ents, s, it, rel))
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
    raw = M.load(src, name)
    f = '>' if e == 'be' else '<'
    for sid, n, p, ents, s, it, rel in anim_lists(raw, e):
        ext = dict(getattr(rel, 'external', []) or [])
        print('object DTP %d size 0x%x: anim count %d, list @+0x%x' % (sid, len(s.data), n, p))
        for k, b in enumerate(ents if '--all' in a else ents[:8]):
            ws = struct.unpack(f + '9I', b)
            hs = struct.unpack(f + '18H', b)
            ptrs = [o for o in range(p + 0x24 * k, p + 0x24 * (k + 1), 4) if o in it]
            print('  %3d: %s | u16 %s | ptr@%s' % (k, ' '.join('%08x' % w for w in ws),
                  ' '.join(str(h) for h in hs[:6]), ','.join('+%x' % (o - p - 0x24 * k) for o in ptrs)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
