"""List the functions of one generalbank script: index, offset, prototype name Symbol, vtable index, code words
(none = native, implemented in the exe). Read-only (finding 43, test 33: which callee is a native the PC exe lacks).

Usage (from the repository root):
  ../bin/pyt tools/script_func_list.py VARIANT SCRIPT_ID      VARIANT = xl / xt / pb / pp (see menu_dlc_probe.py)
  ../bin/pyt tools/script_func_list.py FILE.drm SCRIPT_ID     a PC (little-endian) DRM file, e.g. a test tree's generalbank
  optional third argument TARGET_ID: also list the relocations into script TARGET_ID (e.g. its calls); "all": every
  referenced script with its native package/name and the offsets used
  SOURCE prefixes (also for script_members_list.py, 2026-11-04 thrall unload crash):
    pc:NAME.drm    the PC base-game file (patch.000 first, then bigfile.000)
    xbox:NAME.drm  the Xbox base-game file (title update first, then layer1 / layer2), big endian
    xdisc:NAME.drm / xtu:NAME.drm  only the disc layers / only the title update
    dlc:NAME.drm   the Xbox DLC original (convert_dlc.raw_dlc: pack10 first, TRUDLC_PACK_FIRST=pack11 for DLC 2), big endian
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import menu_dlc_probe as P


def sections(src):
    """[(type, id, data, reloc)], endian for a probe variant, a pc: / xbox: / dlc: base-game name or a PC DRM file"""
    if src in P.SRC:
        C = P.cache()
        return [(s['type'], s['id'], s['data'], s['reloc']) for s in P.secs(C, src)], P.SRC[src][1]
    if src.split(':', 1)[0] in ('pc', 'xbox', 'dlc', 'xdisc', 'xtu') and ':' in src[:6]:
        import dtp_word_classes as C
        from drm import cdrm_decode, sections_with_data
        pre, name = src.split(':', 1)
        if pre == 'dlc':
            import convert_dlc as CD
            raw, _ = CD.raw_dlc(name)
            secs = sections_with_data(cdrm_decode(raw, 'be'), 'be')[1] if raw else None
            e = 'be'
        elif pre == 'xbox':
            secs = C.find(C.BASE, 'be', 'xenon-w' + C.BS + name); e = 'be'
        elif pre == 'xdisc':       # Xbox disc version only (layer1 / layer2, without the title update)
            secs = C.find(C.BASE[1:], 'be', 'xenon-w' + C.BS + name); e = 'be'
        elif pre == 'xtu':         # Xbox title update only
            secs = C.find(C.BASE[:1], 'be', 'xenon-w' + C.BS + name); e = 'be'
        else:
            secs = C.find(C.PC, 'le', 'pc-w' + C.BS + name); e = 'le'
        if secs is None: sys.exit('not found: ' + src)
        return [(s['type'], s['id'], s['data'], s['reloc']) for s in secs], e
    import drm_write as DW
    D = DW.read(open(src, 'rb').read(), 'le')
    return [(s.type, s.id, s.data, s.reloc) for s in D.sections], 'le'


def main(argv):
    import script_conv as SC
    src, sid = argv[0], int(argv[1])
    S, e = sections(src)
    E = '>' if e == 'be' else '<'
    d, rl = next((q[2], q[3]) for q in S if q[0] == 8 and q[1] == sid and q[2])
    rel = R.parse(rl, e)
    it = dict(rel.internal)
    ext = {so: (S[si][0], S[si][1], do) for si, so, do in rel.external}
    W = SC.Walk(d, rel, e).run()
    print('script %s id %d size %d native %s' % (src, sid, len(d), P.script_info({'data': d, 'reloc': rl}, e)[:2]))
    vt = struct.unpack_from(E + 'H', d, 0x3c)[0]
    print('root: protos ptr 0x34 -> %s, funcs 0x38 -> %s, vtableSize %d, vtable 0x44 -> %s, walker problems %s' % (
        hex(it[0x34]) if 0x34 in it else 'none', hex(it[0x38]) if 0x38 in it else 'none', vt,
        hex(it[0x44]) if 0x44 in it else 'none', W.bad[:4]))
    protos = {}
    for name, t, n, sz in W.arrays:
        if name == 'protos':
            for k in range(n):
                a = t + k * sz
                protos[a] = (k, struct.unpack_from(E + 'H', d, a + 6)[0], struct.unpack_from(E + 'HH', d, a + 8))
    for name, t, n, sz in W.arrays:
        if name == 'funcs':
            print('functions: %d (entry size %d) at 0x%x' % (n, sz, t))
            for k in range(n):
                a = t + k * sz
                pr = it.get(a)
                pinfo = protos.get(pr) if pr is not None else ext.get(a)
                ct = it.get(a + 0x18)
                cn = struct.unpack_from(E + 'I', d, ct - 4)[0] if ct is not None else None
                print('  f%-3d @0x%04x proto %s code %s' % (k, a, pinfo, 'NATIVE (no code)' if ct is None else '%d words' % cn))
        elif name == 'protos':
            print('prototypes: %d at 0x%x' % (n, t))
    if len(argv) > 2 and argv[2] == 'all':                  # every script this one refers to, with its native name
        byid = {q[1]: q for q in S if q[0] == 8 and q[2]}
        tally = {}
        for so, (ty, tid, do) in ext.items():
            if ty == 8: tally.setdefault(tid, set()).add(do)
        for tid in sorted(tally):
            q = byid.get(tid)
            info = P.script_info({'data': q[2], 'reloc': q[3]}, e)[:2] if q else 'MISSING'
            print('  -> script %5d %-45s offsets %s' % (tid, info, ' '.join(hex(x) for x in sorted(tally[tid]))))
    elif len(argv) > 2:                                     # third argument: list the relocations into that script
        tid = int(argv[2])
        for so in sorted(ext):
            if ext[so][:2] == (8, tid):
                print('  reloc at 0x%04x -> (8,%d)+0x%x' % (so, tid, ext[so][2]))


if __name__ == '__main__':
    main(sys.argv[1:])
