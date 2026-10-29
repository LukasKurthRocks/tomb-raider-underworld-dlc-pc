"""Take DataMember init values (default-value blocks) of a converted base-game script from the PC version (finding 43).

Why: init blocks hold mixed fields - u32 numbers, u8 flags, u16 pairs, UTF-16 characters (button glyphs) - and the
converter picks the byte permutation per label ('init', base type, depth, offset, userType of the TOP member), not
per real field type. In generalbank script 6 it got them wrong: a count 1 became 0x10000, glyph pairs came out
swapped, and the engine (cdc::UIMenuEntry) read a 65 536-entry glyph list and jumped to address 2 (DLC 2 tests 2-5d;
found with a full crash dump: the menu entry's list pointer pointed into script 6 at such an init block).

What it does in script SCRIPT_ID of IN: members are paired with the REF (PC) script by name Symbol (and equal type
tag / userType); their init trees are walked in parallel - a word that is a pointer on both sides is followed, any
other word is copied from REF. A node is copied only when both nodes have the same length and the same pointer
positions; anything else is reported and left as converted. Members without a PC counterpart (title-update additions)
keep their converted values - listed at the end. Arguments and locals are done the same way (paired by function and
position, names equal).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/script_init_from_pc.py IN_DRM REF_DRM OUT_DRM SCRIPT_ID
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, script_conv as SC


def node(w, it, t):
    """words of the init node starting at t: the run of ('init', ...) labels with offsets 0, 4, 8, ... (the walker's
    offset field saturates at 64, so beyond that the run continues while labels stay 'init' at the same depth)"""
    lab = w.lab.get(t)
    if not lab or lab[0] not in ('init', 'itext'): return []
    out = []; o = t
    while True:
        l = w.lab.get(o)
        if not l or l[0] != lab[0] or (lab[0] == 'init' and (l[2] != lab[2] or l[3] != min(o - t, 64))): break
        if o != t and o in w.targets: break
        out.append(o); o += 4
    return out


def copy_tree(d, wa, ita, pd, wb, itb, a, b, st, seen, shapes):
    if (a, b) in seen: return
    seen.add((a, b))
    na, nb = node(wa, ita, a), node(wb, itb, b)
    if not na or len(na) != len(nb) or [o in ita for o in na] != [o in itb for o in nb]:
        st['node shape differs (kept converted)'] += 1; shapes.append((a, len(na), b, len(nb)))
        return
    for oa, ob in zip(na, nb):
        if oa in ita: copy_tree(d, wa, ita, pd, wb, itb, ita[oa], itb[ob], st, seen, shapes)
        elif d[oa:oa + 4] != pd[ob:ob + 4]:
            d[oa:oa + 4] = pd[ob:ob + 4]; st['words changed'] += 1
        else: st['words already equal'] += 1


def members(w, d, e):
    E = '>' if e == 'be' else '<'
    out = collections.OrderedDict()
    for nm, t, n, sz in w.arrays:
        if nm not in ('members', 'args', 'locals') or sz != 20: continue
        for k in range(n):
            a = t + 20 * k
            tag, ut = struct.unpack_from(E + 'IH', d, a)
            name = struct.unpack_from(E + 'H', d, a + 14)[0]
            out.setdefault((nm, name, tag, ut), []).append(a)
    return out


def main(argv):
    src, ref, out, sid = argv[0], argv[1], argv[2], int(argv[3])
    D = DW.read(open(src, 'rb').read(), 'le'); P = DW.read(open(ref, 'rb').read(), 'le')
    s = next(x for x in D.sections if x.type == 8 and x.id == sid); p = next(x for x in P.sections if x.type == 8 and x.id == sid)
    ra, rb = R.parse(s.reloc, 'le'), R.parse(p.reloc, 'le')
    wa = SC.Walk(s.data, ra, 'le'); wa.run(); wb = SC.Walk(p.data, rb, 'le'); wb.run()
    ita, itb = dict(ra.internal), dict(rb.internal)
    d = bytearray(s.data); st = collections.Counter(); seen = set(); only = []; shapes = []
    ma, mb = members(wa, s.data, 'le'), members(wb, p.data, 'le')
    for key, la in ma.items():
        lb = mb.get(key)
        if not lb: only.append(key); continue
        for a, b in zip(la, lb):
            ia, ib = ita.get(a + 16), itb.get(b + 16)
            if ia is None and ib is None: continue
            if (ia is None) != (ib is None): st['init present on one side only (kept)'] += 1; continue
            st['%s with init paired' % key[0]] += 1
            copy_tree(d, wa, ita, p.data, wb, itb, ia, ib, st, seen, shapes)
    s.data = bytes(d)
    raw = D.write('le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(DW.cdrm_encode(raw, 'le'))
    print('script %d: %s' % (sid, dict(st)))
    if shapes: print('nodes of another shape (ours offset, words, PC offset, words):', ', '.join('0x%x %d / 0x%x %d' % x for x in shapes[:12]))
    with_init = [k for k in only if any(ita.get(a + 16) is not None for a in ma[k])]
    print('data members without a PC counterpart: %d (%d with init, kept as converted): %s' % (
        len(only), len(with_init), ', '.join('%s %d' % (k[0], k[1]) for k in with_init[:40])))
    print('->', out)


if __name__ == '__main__':
    main(sys.argv[1:])
