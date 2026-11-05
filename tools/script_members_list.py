"""List the data members of one script section (type 8): index, entry offset, instance offset, name Symbol, type tag,
userType, the DataType union word (script id / pointer), and the member's init block (words, strings). Read-only.

Written for the pause-menu port (TU script 7, 2026-11-03): which members of the title-update script hold the
`messagechannel` objects `PauseMsgCh` / `HODRefresh`, how their type and init block look, and where the PC script 7
instance ends (root +0x1c size / align).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/script_members_list.py SOURCE SCRIPT_ID [--from OFFSET] [--grep TEXT]
  SOURCE = a PC (little-endian) DRM file, or a tools/menu_dlc_probe.py variant (xl / xt / pb / pp)
  --from OFFSET: only members whose instance offset is >= OFFSET (decimal)
  --grep TEXT  : only members whose init block contains a string with TEXT
  --func N     : instead: function N's header (size / align / stackSize), its locals and its start-function-info list
                 (fsfi = the locals the engine constructs, e.g. strings: script id + frame offset)
Also prints the root start-function-info list (sfi: script id + instance offset of every member object the engine
constructs, highest offset first) when no --func is given.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL
import menu_dlc_probe as P


def main(argv):
    import script_conv as SC
    lo = None; grep = None; func = None
    if '--func' in argv: k = argv.index('--func'); func = int(argv[k + 1]); del argv[k:k + 2]
    if '--from' in argv: k = argv.index('--from'); lo = int(argv[k + 1]); del argv[k:k + 2]
    if '--grep' in argv: k = argv.index('--grep'); grep = argv[k + 1]; del argv[k:k + 2]
    src, sid = argv[0], int(argv[1])
    S, e = FL.sections(src)
    E = '>' if e == 'be' else '<'
    d, rl = next((q[2], q[3]) for q in S if q[0] == 8 and q[1] == sid and q[2])
    rel = R.parse(rl, e)
    it = dict(rel.internal)
    ext = {so: (S[si][0], S[si][1], do) for si, so, do in rel.external}
    ids = rel.id_offsets()
    W = SC.Walk(d, rel, e).run()
    size, align = struct.unpack_from(E + 'HH', d, 0x1c)
    print('script %s id %d section %d B, instance size %d align %d, members ptr %s' % (
        src, sid, len(d), size, align, hex(it[0x2c]) if 0x2c in it else None))

    def u32(o): return struct.unpack_from(E + 'I', d, o)[0]

    def words(t, n=16):
        out = []
        for k in range(n):
            o = t + 4 * k
            if o + 4 > len(d): break
            if k and o in W.targets: break
            if o in it:
                txt = P.cstr(d, it[o])
                out.append('->+0x%x%s' % (it[o], (' %r' % txt[:40]) if txt and all(32 <= ord(c) < 127 for c in txt) else ''))
            elif o in ext: out.append('->ext%s' % (ext[o],))
            elif o in ids: out.append('id%d:%d' % (ids[o], u32(o)))
            else: out.append('%08x' % u32(o))
        return out

    if func is not None:            # one function: header, locals (DataMember), its start-function-info list
        ft = next(t for name, t, n, sz in W.arrays if name == 'funcs')
        a = ft + 28 * func
        flags, state, fsz, falign, stack = struct.unpack_from(E + 'BBHHH', d, a + 4)
        print('function %d @0x%x: flags %d state %d size %d align %d stackSize %d, code @%s' % (
            func, a, flags, state, fsz, falign, stack, hex(it[a + 0x18]) if a + 0x18 in it else None))
        lt = it.get(a + 12); st = it.get(a + 16)
        nl = u32(lt - 4) if lt is not None else 0
        print('locals: %d%s' % (nl, (' at 0x%x' % lt) if lt is not None else ''))
        for k in range(nl):
            b = lt + 20 * k
            tag, ut = struct.unpack_from(E + 'IH', d, b)
            off, nm = struct.unpack_from(E + 'HH', d, b + 12)
            u = ('id%d:%d' % (ids[b + 8], u32(b + 8))) if b + 8 in ids else '%08x' % u32(b + 8)
            print('  l%-3d @0x%05x off %5d name %5d tag 0x%08x bt %2d ut %5d u %s init %s' % (
                k, b, off, nm, tag, tag & 0xf, ut, u, hex(it[b + 16]) if b + 16 in it else '-'))
        ns = u32(st - 4) if st is not None else 0
        print('fsfi: %d%s' % (ns, (' at 0x%x' % st) if st is not None else ''))
        for k in range(ns):
            b = st + 8 * k
            print('  s%-3d @0x%05x %s off %d' % (k, b, ('id%d:%d' % (ids[b], u32(b))) if b in ids else '%08x' % u32(b),
                                               u32(b + 4)))
        return

    for name, t, n, sz in W.arrays:
        if name != 'members': continue
        print('members: %d at 0x%x (entry %d bytes)' % (n, t, sz))
        for k in range(n):
            a = t + k * sz
            tag, ut = struct.unpack_from(E + 'IH', d, a)
            off, nm = struct.unpack_from(E + 'HH', d, a + 12)
            if lo is not None and off < lo: continue
            u = 'ptr+0x%x' % it[a + 8] if a + 8 in it else ('ext%s' % (ext[a + 8],) if a + 8 in ext else (
                'id%d:%d' % (ids[a + 8], u32(a + 8)) if a + 8 in ids else '%08x' % u32(a + 8)))
            ini = it.get(a + 16)
            iw = words(ini) if ini is not None else []
            if grep and not any(grep in x for x in iw): continue
            print('  m%-3d @0x%05x off %5d name %5d tag 0x%08x bt %2d arr %3d ut %5d u %s init %s' % (
                k, a, off, nm, tag, tag & 0xf, (tag >> 8) & 0xff, ut, u,
                ('@0x%x [%s]' % (ini, ' '.join(iw))) if ini is not None else '-'))
    st = it.get(0x30)
    ns = u32(st - 4) if st is not None else 0
    print('sfi: %d%s' % (ns, (' at 0x%x' % st) if st is not None else ''))
    for k in range(ns):
        b = st + 8 * k
        if lo is not None and u32(b + 4) < lo: continue
        print('  s%-3d @0x%05x %s off %d' % (k, b, ('id%d:%d' % (ids[b], u32(b))) if b in ids else '%08x' % u32(b),
                                           u32(b + 4)))


if __name__ == '__main__':
    main(sys.argv[1:])
