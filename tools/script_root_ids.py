"""Print the root ids of script sections (type 8): self id (+0x14), base-class id (+0x18), instance size / align
(+0x1c), member count and vtable size, so the class chain of a script can be followed across DRMs. Read-only.

Written for the thrall unload crash (2026-11-04, docs Befund-Thrall-Absturz.md section 9): which base class the DLC 2
thrall scripts derive from on the Xbox and on the PC, and whether that base script has the same layout in the DLC DRM
and in the main-game DRM that is loaded at the same time.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/script_root_ids.py SOURCE [ID ...]
  SOURCE = a PC DRM file, pc:NAME.drm, xbox:NAME.drm or dlc:NAME.drm (see script_func_list.sections)
  no ID: every script with a base class
  SOURCE = a folder (e.g. a tree's mods): every .drm in it, one line per DRM that holds one of the given IDs
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL


def roots(src):
    """{script id: (self id, base id, size, align, members, vtableSize)}"""
    S, e = FL.sections(src)
    E = '>' if e == 'be' else '<'
    out = {}
    for q in S:
        if q[0] != 8 or not q[2] or len(q[2]) < 0x40: continue
        d = q[2]
        rel = R.parse(q[3], e)
        ids = rel.id_offsets()
        it = dict(rel.internal)

        def u32(o): return struct.unpack_from(E + 'I', d, o)[0]
        me = u32(0x14) if 0x14 in ids else None
        base = u32(0x18) if 0x18 in ids else None
        size, align = struct.unpack_from(E + 'HH', d, 0x1c)
        nm = u32(it[0x2c] - 4) if 0x2c in it else 0
        vt = struct.unpack_from(E + 'H', d, 0x3c)[0]
        out[q[1]] = (me, base, size, align, nm, vt)
    return out


def main(argv):
    src = argv[0]; want = [int(x) for x in argv[1:]]
    if os.path.isdir(src):          # a tree folder: every .drm, only the given ids (one line per DRM and id)
        for fn in sorted(os.listdir(src)):
            if not fn.endswith('.drm'): continue
            try: r = roots(os.path.join(src, fn))
            except Exception as x: print('%s: read failed %s' % (fn, x)); continue
            for sid in want:
                if sid in r:
                    me, base, size, align, nm, vt = r[sid]
                    print('%-48s script %6d base %s size %d members %d vtableSize %d' % (fn, sid, base, size, nm, vt))
        return
    r = roots(src)
    print('source %s: %d scripts' % (src, len(r)))
    for sid in sorted(r):
        me, base, size, align, nm, vt = r[sid]
        if want and sid not in want: continue
        if not want and base is None: continue
        print('script %6d self %s base %s size %d align %d members %d vtableSize %d' % (sid, me, base, size, align, nm, vt))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
