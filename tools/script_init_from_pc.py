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
keep their converted values - listed at the end. Arguments and locals are done the same way, paired by name / type
tag / userType in walk order across all functions (LIMIT: not per function - a function the PC added or removed can
shift the pairing; surplus entries are counted in the report). The output is not written if any relocation ends up
out of bounds.

With --xbox NAME (the Xbox file IN was converted from; title update first, --retail for the retail layers) the members
WITHOUT a PC counterpart get their init words re-derived from the Xbox words: per (type tag, userType, path in the
init tree) the byte order that turns Xbox into PC in every paired member, or a u16 value map where the values differ
(the PC's button glyph codes are the Xbox ones + 2). With --locmap FILE (locmap_xbox_to_pc.json of locals.py build)
locals string ids in those members (userType LOC_UT) are mapped to the PC ids of the merged locals table - the title
update's loading-screen texts (Xbox 1285 / 1288 / 1292) are appended there (5170 / 5173 / 5177).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/script_init_from_pc.py IN_DRM REF_DRM OUT_DRM SCRIPT_ID [--xbox NAME [--retail] [--xbox-id N]] [--locmap FILE]
  --xbox-id N: the Xbox script id when it differs from SCRIPT_ID (the hint box: title update script 10 = PC script 9;
  the port keeps the Xbox offsets, so the Xbox words are read at the same offsets)
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
    pa, pb = [o for o in na if o in ita], [o for o in nb if o in itb]
    if not na or len(na) != len(nb) or len(pa) != len(pb):
        st['node shape differs (kept converted)'] += 1; shapes.append((a, len(na), b, len(nb)))
        return
    if [o - a for o in pa] != [o - b for o in pb]:
        # same size, pointers elsewhere: the PC re-authored this native struct (type 351 of generalbank script 6:
        # three u8 fields widened to u32, the array pointer one word later) - take the PC layout, move the relocations
        moved = [(ob, ita.pop(oa)) for oa, ob in zip(pa, pb)]     # pop all first: old and new slots may overlap
        for ob, t in moved: ita[a + (ob - b)] = t
        st['nodes re-laid out to the PC struct layout'] += 1
    for oa, ob in zip(na, nb):
        if oa in ita: d[oa:oa + 4] = pd[ob:ob + 4]; copy_tree(d, wa, ita, pd, wb, itb, ita[oa], itb[ob], st, seen, shapes)
        elif d[oa:oa + 4] != pd[ob:ob + 4]:
            d[oa:oa + 4] = pd[ob:ob + 4]; st['words changed'] += 1
        else: st['words already equal'] += 1


LOC_UT = 223        # userType (PC Symbol) of the native init type that holds a locals string id (engine_walk_check UT_LOC)
GLYPH_UT = 361      # userType of the menu-entry struct whose word 0 counts its button-glyph list (DLC 2 tests 10 / 11)
PERMS = {'raw': (0, 1, 2, 3), 's32': (3, 2, 1, 0), 's16': (1, 0, 3, 2), 'u8u8u16': (0, 1, 3, 2), 'u16u8u8': (1, 0, 2, 3)}


def perm(x, p): return bytes(x[i] for i in PERMS[p])


def leaves(w, it, a, path=(), seen=None):
    """(path, offset) of every non-pointer word of an init tree; path = word offsets from the member's init root"""
    seen = set() if seen is None else seen
    if a in seen: return
    seen.add(a)
    for o in node(w, it, a):
        if o in it: yield from leaves(w, it, it[o], path + (o - a,), seen)
        else: yield path + (o - a,), o


def learn_rules(wa, ita, xd, pd, wb, itb, pairs):
    """per (type tag, userType, path): byte orders that turn the Xbox word into the PC word in EVERY informative
    observation, and u16 value maps (after a per-half swap) for fields whose values differ (button glyph codes)"""
    obs = collections.defaultdict(list)
    for (tag, ut), ia, ib in pairs:
        la, lb = list(leaves(wa, ita, ia)), list(leaves(wb, itb, ib))
        if [p for p, _ in la] != [p for p, _ in lb]: continue
        for (path, oa), (_, ob) in zip(la, lb):
            if oa + 4 <= len(xd): obs[(tag, ut, path)].append((bytes(xd[oa:oa + 4]), bytes(pd[ob:ob + 4])))
    rules = {}
    for key, L in obs.items():
        info = [(x, p) for x, p in L if len({perm(x, q) for q in PERMS}) > 1 or x != p]
        if not info: continue
        ok = [q for q in PERMS if all(perm(x, q) == p for x, p in info)]
        if ok: rules[key] = ('perm', ok[0] if len(ok) == 1 else ('raw' if 'raw' in ok else ok[0])); continue
        vmap = {}; good = True
        for x, p in info:
            for h in (0, 2):
                xv = struct.unpack_from('>H', x, h)[0]; pv = struct.unpack_from('<H', p, h)[0]
                if vmap.setdefault(xv, pv) != pv: good = False
        if good: rules[key] = ('u16map', vmap)
    return rules


def apply_rules(d, w, it, xd, ia, tag, ut, rules, st):
    """re-derive the words of one TU-only member; True when a glyph value is not in the learned map"""
    unknown = False
    for path, o in leaves(w, it, ia):
        r = rules.get((tag, ut, path))
        if r is None or o + 4 > len(xd): st['TU-only init words without a rule (kept)'] += 1; continue
        x = bytes(xd[o:o + 4])
        if r[0] == 'perm': new = perm(x, r[1])
        else:
            hv = [struct.unpack_from('>H', x, h)[0] for h in (0, 2)]
            if any(v not in r[1] for v in hv if v):       # byte order still per 16-bit half; unknown value kept
                st['TU-only glyph values not in the learned map (Xbox value kept)'] += 1; unknown = True
            new = b''.join(struct.pack('<H', r[1].get(v, v)) for v in hv)
        if bytes(d[o:o + 4]) != new: d[o:o + 4] = new; st['TU-only init words changed by rule'] += 1
        else: st['TU-only init words already right'] += 1
    return unknown


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


def pair_entries(wa, sd, wb, pd, prl, x, st, by_name=False):
    """IN (converted, Xbox layout, little-endian) <-> REF (PC) entries -> ([(key, IN entry, PC entry)], [(key, IN entry)
    without a PC partner]); key = (array, IN name, tag, userType).
    With the Xbox source x (--xbox) and the Xbox layout kept (same size): the PC twin in the declaration order
    (Q58: script_member_pairs.align on the Xbox source; a twin of another userType is not paired, counted). Q55 proved
    the alignment on the 280 base pairs (623 / 7 against the text id referee; the old name rule 207 / 181 there) and
    the name rule right on base pair 6 (41 / 0, every name there from the base map) - with the Q58 twin Symbols
    (docs/data/symbol_twins.json) the converter's names ARE the twins' names wherever a twin exists, so both rules agree
    where the name rule was proven. Without --xbox (or by_name, --by-name): the name rule (array, name, tag, userType),
    args / locals in walk order across functions (LIMIT: a function the PC added or removed shifts that pairing)."""
    ma, mb = members(wa, sd, 'le'), members(wb, pd, 'le')
    plist, only_e = [], []
    if x is not None and len(x['data']) == len(sd) and not by_name:
        import script_member_pairs as MP
        import dlc_generic as DG
        tw, _ = MP.align(x['data'], x['reloc'], pd, prl, DG.DlcIds())
        info = {a: k for k, la in mb.items() for a in la}
        st['pairing: declaration-order twins (script_member_pairs.align), locals by name'] = 1
        for key, la in ma.items():
            if key[0] == 'locals':
                # locals keep the name rule: aligned across all functions the walk order pairs other locals where the
                # PC added / removed functions (Q58 referee, base map: 186 = / 7 !=); script 6 with twin names: members
                # and args of both rules identical, locals 507 common, 57 name-rule-only / 72 twin-only pairs
                lb = mb.get(key, [])
                if len(la) != len(lb): st['locals: unequal counts per name (surplus not paired)'] += abs(len(la) - len(lb))
                plist += [(key, a, b) for a, b in zip(la, lb)]
                only_e += [(key, a) for a in la[len(lb):]]
                continue
            for a in la:
                b = tw.get(a)
                if b is None: only_e.append((key, a)); continue
                kb = info[b]
                if (kb[0], kb[2], kb[3]) != (key[0], key[2], key[3]):
                    st['%s: twin of another array / userType (not paired)' % key[0]] += 1; only_e.append((key, a)); continue
                if kb[1] != key[1]: st['%s: twin with another name than the converter\'s' % key[0]] += 1
                plist.append((key, a, b))
        return plist, only_e
    if x is not None and not by_name: st['pairing: by name (Xbox source of another size)'] = 1
    for key, la in ma.items():
        lb = mb.get(key)
        if not lb: only_e += [(key, a) for a in la]; continue
        if len(la) != len(lb): st['%s: unequal counts per name (surplus not paired)' % key[0]] += abs(len(la) - len(lb))
        plist += [(key, a, b) for a, b in zip(la, lb)]
        only_e += [(key, a) for a in la[len(lb):]]
    return plist, only_e


def main(argv):
    by_name = '--by-name' in argv; argv = [a for a in argv if a != '--by-name']
    xname = None; retail = '--retail' in argv; argv = [a for a in argv if a != '--retail']
    if '--xbox' in argv: k = argv.index('--xbox'); xname = argv[k + 1]; del argv[k:k + 2]
    xid = None      # Xbox script id when it differs from the PC one (title update script 10 = PC script 9)
    if '--xbox-id' in argv: k = argv.index('--xbox-id'); xid = int(argv[k + 1]); del argv[k:k + 2]
    locmap = None
    if '--locmap' in argv:
        import json
        k = argv.index('--locmap'); locmap = json.load(open(argv[k + 1]))['map']; del argv[k:k + 2]
    src, ref, out, sid = argv[0], argv[1], argv[2], int(argv[3])
    D = DW.read(open(src, 'rb').read(), 'le'); P = DW.read(open(ref, 'rb').read(), 'le')
    s = next(x for x in D.sections if x.type == 8 and x.id == sid); p = next(x for x in P.sections if x.type == 8 and x.id == sid)
    ra, rb = R.parse(s.reloc, 'le'), R.parse(p.reloc, 'le')
    wa = SC.Walk(s.data, ra, 'le'); wa.run(); wb = SC.Walk(p.data, rb, 'le'); wb.run()
    ita, itb = dict(ra.internal), dict(rb.internal)
    ita0 = dict(ita)        # relocations before any re-layout: field rules are learned in the Xbox layout
    d = bytearray(s.data); st = collections.Counter(); seen = set(); shapes = []; pairs = []
    x = None
    if xname:
        import dtp_word_classes as C
        x = next(q for q in C.find(C.BASE[1:] if retail else C.BASE, 'be', 'xenon-w' + chr(92) + xname)
                 if q['type'] == 8 and q['id'] == (sid if xid is None else xid))
    ma = members(wa, s.data, 'le')
    plist, only_e = pair_entries(wa, s.data, wb, p.data, p.reloc, x, st, by_name=by_name)
    for key, a, b in plist:
        ia, ib = ita.get(a + 16), itb.get(b + 16)
        if ia is None and ib is None: continue
        if (ia is None) != (ib is None): st['init present on one side only (kept)'] += 1; continue
        st['%s with init paired' % key[0]] += 1; pairs.append(((key[2], key[3]), ia, ib))
        copy_tree(d, wa, ita, p.data, wb, itb, ia, ib, st, seen, shapes)
    only = list(collections.OrderedDict.fromkeys(k for k, _ in only_e))
    if xname:       # members without a PC counterpart: byte order per field learned from the paired members
        rules = learn_rules(wa, ita0, x['data'], p.data, wb, itb, pairs)
        st['field rules learned'] = len(rules)
        for key, a in only_e:
            if True:
                ia = ita.get(a + 16)
                if ia is None: continue
                if apply_rules(d, wa, ita, x['data'], ia, key[2], key[3], rules, st) and key[3] == GLYPH_UT:
                    # a glyph the PC font map does not know (title update: 0x4021) crashed the engine's menu-entry
                    # text code (DLC 2 test 10) - empty the glyph list: count (word 0 of the struct) = 0. Only for the
                    # glyph-list struct: in the loading-screen title texts (userType 301) word 0 is a flag the DLC
                    # titles need (= 1 as on the Xbox; zeroed, the titles stayed invisible - test 38)
                    for path, o in leaves(wa, ita, ia):
                        if path == (0, 0): d[o:o + 4] = b'\0\0\0\0'; st['TU-only glyph lists emptied (unknown glyph)'] += 1
                if locmap is not None and key[3] == LOC_UT:     # locals string id (u16, first half of word 0)
                    for path, o in leaves(wa, ita, ia):
                        if path != (0, 0): continue          # depth 1, offset 0 (label ('init', 10, 1, 0, ut))
                        xv = struct.unpack_from('>H', x['data'], o)[0]
                        pv = locmap.get(str(xv))
                        if xv and pv is None: st['TU-only locals string ids not in the map (kept)'] += 1
                        elif xv and struct.unpack_from('<H', d, o)[0] != pv:
                            struct.pack_into('<H', d, o, pv); st['TU-only locals string ids mapped'] += 1
    s.data = bytes(d); ra.internal = list(ita.items()); s.reloc = R.write(ra, 'le')
    raw = D.write('le'); E = DW.read(DW.cdrm_encode(raw, 'le'), 'le'); infos = [dict(size=len(x.data)) for x in E.sections]
    st['sections with relocations out of bounds'] = bad = sum(bool(R.check(R.parse(x.reloc, 'le'), len(x.data), infos)) for x in E.sections)
    if bad: print('script %d: %s' % (sid, dict(st))); sys.exit('relocations out of bounds - %s NOT written' % out)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(DW.cdrm_encode(raw, 'le'))
    print('script %d: %s' % (sid, dict(st)))
    if shapes: print('nodes of another shape (ours offset, words, PC offset, words):', ', '.join('0x%x %d / 0x%x %d' % x for x in shapes[:12]))
    with_init = list(collections.OrderedDict.fromkeys(k for k, a in only_e if ita.get(a + 16) is not None))
    print('data members without a PC counterpart: %d (%d with init, kept as converted): %s' % (
        len(only), len(with_init), ', '.join('%s %d' % (k[0], k[1]) for k in with_init[:40])))
    print('->', out)


if __name__ == '__main__':
    main(sys.argv[1:])
