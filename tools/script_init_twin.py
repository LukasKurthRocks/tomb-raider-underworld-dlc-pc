"""Init value blocks of a title-update port from their retail twins: same Xbox words -> Crystal's PC words (read-only
on the inputs, writes OUT). Shadow meter HUD (workspace Befund-Schattenleiste-HUD.md).

A script converted from the Xbox title update (TU) keeps the Xbox offsets, so every init value node (a run of words the
script walker labels 'init', starting at a pointer target) can be read word for word in the TU Xbox script. The same
chain applied to the RETAIL Xbox script (the control) ends equal to Crystal's PC script; so a TU node whose Xbox words
equal those of a control node (same length, relocations at the same positions, every other word equal) has a known PC
form: the control's words. The converter guesses the byte order of init words per label; on the HUD script 38 it turns
the floats 0.35 / 0.1 and the colours 0xff606060 of some UI element nodes (userType 320 / 0x343) into glyph-mapped u16
pairs - in the control those are Crystal's values. Nodes without a twin (title-update data) are left as converted and
listed with their word classes (tools/script_port_classes.py) for review.

Ambiguous twins (several control nodes with the same Xbox words but different PC words) are not used (reported).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/script_init_twin.py PORT.drm SCRIPT_ID XBOX XBOX_ID CONTROL.drm CONTROL_ID XBOX_CONTROL XBOX_CONTROL_ID OUT.drm
  e.g. t4.drm 37 xt 38 control.drm 37 xl 38 out.drm   (xt / xl: tools/menu_dlc_probe.py variants)
  --all: list every node without a twin (default: only those with words that are no plain 32-bit conversion)
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import script_port_check as PC
import script_port_classes as CL
import script_func_list as FL


def nodes(src, sid, xsrc, xid):
    """[(start, [offsets], key)] of the init nodes; key = Xbox words with relocated positions as 'R'"""
    import script_conv as SC
    P = PC.load(src, sid); X = PC.load(xsrc, xid)
    S, e = FL.sections(src)
    d, rl = next((q[2], q[3]) for q in S if q[0] == 8 and q[1] == sid)
    W = SC.Walk(d, R.parse(rl, e), e); W.run()
    reloc = set(P['it']) | set(P['ext']) | set(P['ida']) | set(P['idr'])
    targets = set(P['it'].values())
    out = []
    n = min(len(P['d']), len(X['d']))
    for t in sorted(targets):
        lab = W.lab.get(t)
        if not lab or lab[0] != 'init': continue
        offs = [t]; o = t + 4
        while o + 4 <= n and W.lab.get(o, ('',))[0] == 'init' and o not in targets:
            offs.append(o); o += 4
        if offs[-1] + 4 > n: continue
        key = tuple('R' if o in reloc else X['d'][o:o + 4] for o in offs)
        out.append((t, offs, key, lab))
    return P, X, out, reloc


def main(argv):
    all_nodes = '--all' in argv; argv = [a for a in argv if a != '--all']
    if len(argv) != 9: sys.exit(__doc__)
    port, sid, xv, xid, ctrl, cid, cxv, cxid, out = argv[0], int(argv[1]), argv[2], int(argv[3]), argv[4], \
        int(argv[5]), argv[6], int(argv[7]), argv[8]
    P, X, pn, preloc = nodes(port, sid, xv, xid)
    C, CX, cn, creloc = nodes(ctrl, cid, cxv, cxid)
    twins = collections.defaultdict(set)
    for t, offs, key, lab in cn:
        twins[key].add(tuple(None if k == 'R' else C['d'][o:o + 4] for o, k in zip(offs, key)))
    raw = open(port, 'rb').read(); D = DW.read(raw, 'le')
    s = next(x for x in D.sections if x.type == 8 and x.id == sid)
    d = bytearray(s.data); st = collections.Counter(); fixed = []; lonely = []
    for t, offs, key, lab in pn:
        tw = twins.get(key)
        if not tw:
            cls = collections.Counter(CL.cls(X['d'][o:o + 4], P['d'][o:o + 4]) for o, k in zip(offs, key) if k != 'R')
            st['nodes without a twin (kept)'] += 1
            if all_nodes or cls.get('other') or cls.get('s16') or cls.get('u8u8u16') or cls.get('u16u8u8'):
                lonely.append((t, len(offs), lab, dict(cls)))
            continue
        if len(tw) > 1: st['nodes with ambiguous twins (kept)'] += 1; continue
        pcw = next(iter(tw)); n = 0
        for o, w in zip(offs, pcw):
            if w is None or bytes(d[o:o + 4]) == w: continue
            d[o:o + 4] = w; n += 1
        st['nodes with a twin'] += 1
        if n:
            st['nodes changed'] += 1; st['words changed'] += n
            fixed.append((t, len(offs), n, lab))
    s.data = bytes(d)
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(o)
    print('script %d: %d init nodes, control %d; %s' % (sid, len(pn), len(cn), dict(st)))
    for t, n, k, lab in fixed:
        print('  changed node +%#06x (%d words, %d set from the twin) %s' % (t, n, k, lab))
    for t, n, lab, cls in lonely:
        print('  no twin  node +%#06x (%d words) %s classes %s' % (t, n, lab, cls))
    print('->', out)


if __name__ == '__main__':
    main(sys.argv[1:])
