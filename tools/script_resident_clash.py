"""Find DLC script sections (type 8) whose PC id is also held by an always-resident PC DRM (generalbank.drm, ...)
with another content. The engine keeps the first loaded section of an id: a DLC DRM's own copy of such a script is
never used, the resident one takes its place - fatal when the layout differs (instance size, members, vtable size),
because the DLC scripts that derive from it were compiled against the DLC layout. Read-only.

Written for the thrall unload crash (2026-11-04, docs Befund-Thrall-Absturz.md section 9): DLC 2 re-authored the
thrall base class (Xbox id 8453, 152 bytes: instance 8 bytes, 1 member, vtable 64) under the id of the main-game class
(3300 bytes: 16 bytes, 3 members, vtable 69). The Xbox title-update generalbank does not hold 8453, so on the Xbox
the DLC copy is the one in use; the PC patch generalbank holds the main-game class as 12433, so on the PC the DLC 2
thralls (24347 / 24545 / 22813 / 24891) run on the wrong base layout.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/script_resident_clash.py RESIDENT.drm[,RESIDENT2.drm] TREE_DIR [TREE_DIR ...] [--all]
  RESIDENT: the installed generalbank.drm (or pc:generalbank.drm) and other always-loaded DRMs, comma separated
  --all: also list ids whose bytes differ but whose layout is the same (default: layout differences only)
Output: one line per (script id, layout) with the DRMs that carry it; the summary counts.
"""
import sys, os, struct, collections, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL


def layout(d, rl, e):
    """(instance size, align, member count, vtableSize, base id) of a script section"""
    E = '>' if e == 'be' else '<'
    if len(d) < 0x40: return None
    rel = R.parse(rl, e)
    it = dict(rel.internal); ids = rel.id_offsets()
    size, align = struct.unpack_from(E + 'HH', d, 0x1c)
    nm = struct.unpack_from(E + 'I', d, it[0x2c] - 4)[0] if 0x2c in it else 0
    vt = struct.unpack_from(E + 'H', d, 0x3c)[0]
    base = struct.unpack_from(E + 'I', d, 0x18)[0] if 0x18 in ids else None
    return (size, align, nm, vt, base)


def main(argv):
    show_all = '--all' in argv
    argv = [a for a in argv if a != '--all']
    res = {}
    for r in argv[0].split(','):
        S, e = FL.sections(r)
        for q in S:
            if q[0] == 8 and q[2] and q[1] not in res:
                res[q[1]] = (os.path.basename(r), layout(q[2], q[3], e), hashlib.md5(q[2] + q[3]).hexdigest()[:12])
    print('resident: %s, %d scripts' % (argv[0], len(res)))
    seen = collections.defaultdict(list)       # (id, layout, md5) -> [drm]
    for tree in argv[1:]:
        for fn in sorted(os.listdir(tree)):
            if not fn.lower().endswith('.drm'): continue
            try: S, e = FL.sections(os.path.join(tree, fn))
            except Exception as x: print('%s: read failed %s' % (fn, x)); continue
            for q in S:
                if q[0] != 8 or not q[2] or q[1] not in res: continue
                lay = layout(q[2], q[3], e)
                h = hashlib.md5(q[2] + q[3]).hexdigest()[:12]
                seen[(q[1], lay, h)].append(fn)
    st = collections.Counter()
    for (sid, lay, h), fns in sorted(seen.items()):
        rn, rlay, rh = res[sid]
        if h == rh: st['identical'] += 1; continue
        if lay == rlay:
            st['bytes differ, same layout'] += 1
            if not show_all: continue
            tag = 'same layout'
        else:
            st['LAYOUT DIFFERS'] += 1; tag = 'LAYOUT DIFFERS'
        print('script %6d %-15s DLC size/align/members/vtable/base %s vs resident %s %s (%d DRMs: %s%s)' % (
            sid, tag, lay, rn, rlay, len(fns), ', '.join(fns[:6]), ' ...' if len(fns) > 6 else ''))
    print('summary (id, layout, bytes) groups: %s' % dict(st))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
