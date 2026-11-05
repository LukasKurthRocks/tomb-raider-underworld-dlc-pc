"""List the data members of EVERY script section (type 8) of one DRM in one line per member: script id, instance
size, member index, instance offset, type nibble (tag & 0xf), tag, userType, the member's type script (id + native
package/name when it is a native class) and the start-function-info list (the member objects the engine constructs).
Read-only.

Written for the thrall unload crash (2026-11-04, docs Befund-Thrall-Absturz.md section 9): which script of a thrall
DRM describes the unique-data member that tru+0x57b240 releases on unload (type nibble 0xa = native class, released
through the native type handler vtable +0x1c), and how the same scripts look in the Xbox original / the main game.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/script_members_scan.py SOURCE [--script ID] [--native NAME] [--size N]
  SOURCE    = a PC DRM file, pc:NAME.drm (PC base game), xbox:NAME.drm (Xbox base game), dlc:NAME.drm (Xbox DLC
              original; set TRUDLC_PACK_FIRST=pack11 for DLC 2) - see script_func_list.sections
  --script  only this script id
  --native  only scripts that have a member whose type is the native class NAME (e.g. health)
  --size    only scripts with this instance size (bytes)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL
import menu_dlc_probe as P


def scan(src):
    """{script id: (size, align, [(index, off, tag, ut, type id or None)], [(type id or raw, off)], native)},
    {script id: native (package, name)}"""
    import script_conv as SC
    S, e = FL.sections(src)
    E = '>' if e == 'be' else '<'
    natives = {}
    for q in S:
        if q[0] == 8 and q[2]:
            try: natives[q[1]] = tuple(P.script_info({'data': q[2], 'reloc': q[3]}, e)[:2])
            except Exception: natives[q[1]] = (None, None)
    out = {}
    for q in S:
        if q[0] != 8 or not q[2]: continue
        d, rl = q[2], q[3]
        rel = R.parse(rl, e)
        it = dict(rel.internal)
        ids = rel.id_offsets()
        try: W = SC.Walk(d, rel, e).run()
        except Exception as x:
            out[q[1]] = (None, None, [], [], natives.get(q[1]), 'walk failed: %s' % x); continue
        size, align = struct.unpack_from(E + 'HH', d, 0x1c)

        def u32(o): return struct.unpack_from(E + 'I', d, o)[0]
        mem = []
        for name, t, n, sz in W.arrays:
            if name != 'members': continue
            for k in range(n):
                a = t + k * sz
                tag, ut = struct.unpack_from(E + 'IH', d, a)
                off, nm = struct.unpack_from(E + 'HH', d, a + 12)
                tid = u32(a + 8) if a + 8 in ids else None
                mem.append((k, off, tag, ut, tid, nm))
        sfi = []
        st = it.get(0x30)
        ns = u32(st - 4) if st is not None else 0
        for k in range(ns):
            b = st + 8 * k
            sfi.append((u32(b) if b in ids else ('raw', u32(b)), u32(b + 4)))
        out[q[1]] = (size, align, mem, sfi, natives.get(q[1]), '')
    return out, natives


def main(argv):
    only = None; nat = None; size = None
    if '--script' in argv: k = argv.index('--script'); only = int(argv[k + 1]); del argv[k:k + 2]
    if '--native' in argv: k = argv.index('--native'); nat = argv[k + 1]; del argv[k:k + 2]
    if '--size' in argv: k = argv.index('--size'); size = int(argv[k + 1]); del argv[k:k + 2]
    src = argv[0]
    out, natives = scan(src)
    print('source %s: %d scripts' % (src, len(out)))
    for sid in sorted(out):
        sz, al, mem, sfi, nv, err = out[sid]
        if only is not None and sid != only: continue
        if size is not None and sz != size: continue
        if nat is not None and not any(m[4] is not None and (natives.get(m[4]) or (None, None))[1] == nat for m in mem):
            continue
        if not mem and only is None and nat is None and size is None: continue
        print('script %d size %s align %s native %s %s' % (sid, sz, al, nv, err))
        for k, off, tag, ut, tid, nm in mem:
            tn = natives.get(tid) if tid is not None else None
            print('   m%-3d off %5d nib %2d tag 0x%08x ut %5d name %5d type %s%s' % (
                k, off, tag & 0xf, tag, ut, nm, tid if tid is not None else '-',
                (' (%s)' % tn[1]) if tn and tn[1] else ''))
        for tid, off in sfi:
            tn = natives.get(tid) if not isinstance(tid, tuple) else None
            print('   sfi off %5d type %s%s' % (off, tid, (' (%s)' % tn[1]) if tn and tn[1] else ''))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
