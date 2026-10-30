"""Disassemble the functions of one script section (type 8) of a PC DRM file (or a menu_dlc_probe variant), read-only.

Like `menu_dlc_probe.py dis`, but for any DRM file: every code word with opcode / operand, extra words annotated as
internal pointer (with the C string it points at), external relocation ((type, id) + offset, plus the callee's
function index when the target is a function entry of a script in the same file) or raw value; float literals of
op02 shown as floats. Finding 43, test 39 (shadow slow motion): how base / DLC scripts call `gamebase` #23 / #24
(the engine time-scale natives) and read buttons through `inputaction`.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/script_dis.py SOURCE SCRIPT_ID [FUNC_INDEX,...]
  SOURCE = a PC (little-endian) DRM file, or a menu_dlc_probe variant (xl / xt / pb / pp)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL
import menu_dlc_probe as P


def func_entries(d, rl, e):
    """{function entry offset: index} of a script section"""
    import script_conv as SC
    W = SC.Walk(d, R.parse(rl, e), e).run()
    out = {}
    for name, t, n, sz in W.arrays:
        if name == 'funcs':
            for k in range(n):
                out[t + k * sz] = k
    return out


def main(argv):
    import script_conv as SC
    src, sid = argv[0], int(argv[1])
    only = set(int(x) for x in argv[2].split(',')) if len(argv) > 2 else None
    S, e = FL.sections(src)
    E = '>' if e == 'be' else '<'
    d, rl = next((q[2], q[3]) for q in S if q[0] == 8 and q[1] == sid and q[2])
    rel = R.parse(rl, e)
    it = dict(rel.internal)
    ext = {so: (S[si][0], S[si][1], do) for si, so, do in rel.external}
    ids = rel.id_offsets()
    entries = {}
    W = SC.Walk(d, rel, e).run()
    print('script %s id %d size %d native %s walker problems %s' % (
        src, sid, len(d), P.script_info({'data': d, 'reloc': rl}, e)[:2], W.bad[:4]))
    for name, t, n, sz in W.arrays:
        if name != 'funcs':
            continue
        for k in range(n):
            if only is not None and k not in only:
                continue
            a = t + k * sz
            ct = it.get(a + 0x18)
            if ct is None:
                continue
            cn = struct.unpack_from(E + 'I', d, ct - 4)[0]
            print('\n== func %d @0x%x code @0x%x n=%d' % (k, a, ct, cn))
            j = 0
            while j < cn:
                o = ct + 4 * j
                w = struct.unpack_from(E + 'I', d, o)[0]
                op = w >> 24; arg = w & 0xffffff
                extra = SC.Walk.EXTRA.get(op, 1 if op == P.PUSHF else 0)
                ann = []
                for q in range(1, extra + 1):
                    ao = o + 4 * q
                    aw = struct.unpack_from(E + 'I', d, ao)[0]
                    if ao in it:
                        tt = it[ao]; txt = P.cstr(d, tt)
                        ann.append('->int 0x%x %r' % (tt, txt[:60] if txt and all(32 <= ord(c) < 127 for c in txt) else None))
                    elif ao in ext:
                        ty, tid, do = ext[ao]
                        fi = None
                        if ty == 8:
                            if tid not in entries:
                                tgt = next((q for q in S if q[0] == 8 and q[1] == tid and q[2]), None)
                                entries[tid] = func_entries(tgt[2], tgt[3], e) if tgt else {}
                            fi = entries[tid].get(do)
                        ann.append('->ext (%d,%d)+0x%x f%s' % (ty, tid, do, fi))
                    elif ao in ids:
                        ann.append('->id type%d %d' % (ids[ao], aw))
                    elif op == P.PUSHF:
                        ann.append('float %g' % struct.unpack(E + 'f', struct.pack(E + 'I', aw))[0])
                    else:
                        ann.append('raw 0x%x' % aw)
                print('  %04x  %08x  op%02x %6d  %s' % (o, w, op, arg if arg < 0x800000 else arg - 0x1000000, ' | '.join(ann)))
                j += 1 + extra


if __name__ == '__main__':
    main(sys.argv[1:])
