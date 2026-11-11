"""Pipeline data step "uiinit" (2026-11-09, N15 package H): re-derive the init value words of UI element members in DLC
scripts from the Xbox original, with the byte order per field proven on the base game (generalbank, Xbox <-> PC).

Why: the converter picks the byte order of script init words per label (init, base type, depth, offset, userType of
the top member - tools/script_conv.py initdata), not per real field. For the UI element userTypes (Xbox symbols 299 /
301 / 314 / 318 = PC 301 / 303 / 316 / 320) of the DLC 2 objective / hint notifier scripts (26430 hall02, 26078 end,
...) it wrote floats through the symbol map (0.1 -> cccd334f, -1.0 -> 0000c160) and u32 fields as 2 x u16 (field 4
-> 00040000): the banner "OBJECTIVE / HINT REVEALED" runs on PC but is invisible (docs ENGINE.md section 8,
tools/ui_text_init_scan.py: 53 of 1071 text anchors).

Rule (proof): base scripts of the same name in xbox:generalbank.drm and pc:generalbank.drm are paired by their name
Symbol (Xbox -> PC through the id map), their members by the place in the declaration order (Q55,
tools/script_member_pairs.align; until Q55 by (array, guessed name Symbol, type tag, userType), which paired neighbour
entries: PC prompt ids 129 -> 139 / 131 -> 150 said other texts), same type tag and userType; the init trees of paired
members with a UI userType are walked in parallel (tools/script_init_from_pc.py leaves: same tree shape required). Per
(PC userType, type tag, path in the init tree) the word classes of tools/script_learn.py that turn EVERY informative
Xbox word into the PC word give the rule; where no class fits, a consistent whole-word value map (Xbox word -> PC word)
is the rule (the PC-only field +0x08 behind a text id: Xbox 0 -> PC 00010000); anything else is a contradiction
(exit 1). Apply: in a DLC script (the PC file keeps the Xbox offsets) every leaf of a UI member's init tree whose key
has a rule gets the rule's word from the Xbox original; id classes (symbols, ...) and leaves without a rule keep the
converter's word (counted); relocation / id slots are never touched.

Locals string ids (Q46, 2026-11-11): with the pipeline's locals map (dlc_generic.locmap_path(); DlcIds.loc used to
read a path nothing writes and returned the Xbox index) the text id leaf of the UI text element (ut 301, path [0, 92])
proves as the locals class id16a:101 on the base pairs (86 observations; without the map a coincidental id16a:110 from
4). Such leaves (LOC_CLASSES) are applied: Xbox index (high u16) -> PC string id by the map, except where every base
observation of that Xbox index shows one other PC id (the PC's own button prompts, LOC_PC); an index outside the map
keeps the converter's word (counted). Scripts are paired with their Xbox source by dlc_script_pairs (id map + name
Symbol, renumbered scripts included); scripts whose PC bytes are a PC base copy (route pc_copy) are not touched.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/ui_init_fix.py proof [--report R.json]
        learn + prove on the base pairs; exit 1 on a contradiction or when a pinned count differs
  ../bin/pyt -t 3600 tools/ui_init_fix.py scan TREE [--pack pack11] [--report R.json]
        the words the step would change (nothing written); exit 1 when any
  ../bin/pyt -t 3600 tools/ui_init_fix.py apply TREE [--pack pack11] [--report R.json]
        rewrite the DRMs of TREE in place (only the planned words; relocations, headers and every other byte kept,
        each written file re-read and compared); exit 1 on a write that does not prove
TREE: a mods folder of converted PC DRMs (DLC scripts keep the Xbox offsets); --pack pack11 for DLC 2 (the pack11
record of the 10 names in both packs, as dlc_fixes_build --pack), pack10 (default order) for DLC 1.
Gate afterwards: tools/ui_text_init_scan.py TREE (exit 1 on a broken text anchor).
"""
import sys, os, struct, collections, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_write as DW, drm_reloc as R, script_conv as SC, script_func_list as FL, script_learn as L
import script_init_from_pc as SIP
import script_member_pairs as MP

UI_UTS = (301, 303, 316, 320)          # PC userTypes of the UI element native types (Xbox 299 / 301 / 314 / 318)
BASE_SRC = ('generalbank.drm',)
ID_CLASSES = {c for c in L.CLASSES if c.startswith('id') or c in ('syma_r', 'r_symb')}
LOC_CLASSES = {'id16a:101'}             # locals string id in the high u16 (Xbox) -> PC string id (applied, Q46)
LOC_PC = {}             # {key: {Xbox index: PC id}} - every base observation of the index shows this other PC id
PREF = ('s32', 'raw', 's16', 'b2s16', 's16b2')
ZERO_RULE_MIN = 5       # Xbox 0 -> one non-zero PC value: only with at least this many unanimous base observations
# pinned proof counts (first run 2026-11-09): changing data or code must not move them silently
# Q55 (2026-11-11): member twins by declaration order - 389 -> 446 members, 23279 -> 26195 observations, s32 129 -> 128
# (4 keys s32 -> id-mixed: script 7 holds a member-name Symbol path there), zero rule 108 -> 126, prompt ids 5 -> 3;
# planned words on pipeline_check_1111b unchanged (DLC 1 3116, DLC 2 1871 rows identical)
PINNED = {'base script pairs': 141, 'UI members paired': 446, 'observations': 26195, 'contradictions': 0,
          'rule s32': 128, 'zero rule ut 301 path [0, 100]: base observations': 126,
          # Q46 (2026-11-11): the text id leaf proves as the locals class once the map is read
          'rule id16a:101': 1,
          'locals text ids: PC prompt ids learned': 3}

_IDS = None


def ids():
    global _IDS
    if _IDS is None:
        import dlc_generic as DG
        _IDS = DG.DlcIds()
    return _IDS


def walk(data, reloc, e):
    rel = R.parse(reloc, e)
    W = SC.Walk(data, rel, e).run()
    return W, rel


def no_touch(rel):
    """offsets that are relocation / id slots (never rewritten)"""
    return set(rel.pointer_offsets()) | set(rel.id_offsets()) | set(dict(rel.internal))


def text_word(x):
    """4 bytes that start a NUL-terminated ASCII string (first byte printable, the rest printable or NUL)"""
    return 32 <= x[0] < 127 and all(32 <= b < 127 or b == 0 for b in x) and x != b'\0\0\0\0'


def script_name(d, e):
    return struct.unpack_from(('>' if e == 'be' else '<') + 'HH', d, 0x08)


def learn():
    """observations per (PC userType, tag, path) from the base pairs -> (rules, stats, contradictions)"""
    I = ids()
    obs = collections.defaultdict(list)
    st = collections.Counter()
    for name in BASE_SRC:
        X, xe = FL.sections('xbox:' + name)
        P, pe = FL.sections('pc:' + name)
        pmap = {}
        for t, sid, d, rl in P:
            if t == 8 and d: pmap.setdefault(script_name(d, 'le'), []).append((sid, d, rl))
        for t, sid, xd, xrl in X:
            if t != 8 or not xd: continue
            a, b = script_name(xd, 'be')
            cand = pmap.get((I.sym(a), I.sym(b)))
            if not cand: st['base scripts without a PC script of the same name'] += 1; continue
            if len(cand) > 1: st['base scripts with several PC scripts of the same name (first taken)'] += 1
            _, pd, prl = cand[0]
            Wx, rx = walk(xd, xrl, 'be'); Wp, rp = walk(pd, prl, 'le')
            nx, np_ = no_touch(rx), no_touch(rp)
            mx = SIP.members(Wx, xd, 'be')
            # Q55: the PC twin of a member / arg / local by its place in the declaration order
            # (script_member_pairs.align), not by the converter's guessed name Symbol
            twin, _ = MP.align(xd, xrl, pd, prl, I, None, Wx=Wx, Wp=Wp)
            st['base script pairs'] += 1
            for (arr, nm, tag, ut), la in mx.items():
                put = I.sym(ut)
                if put not in UI_UTS: continue
                for ma in la:
                    mb = twin.get(ma)
                    if mb is None: st['UI members without a PC twin'] += 1; continue
                    if struct.unpack_from('<IH', pd, mb) != (tag, put):
                        st['UI members whose PC twin has another userType (skipped)'] += 1; continue
                    if struct.unpack_from('<H', pd, mb + 14)[0] != I.sym(nm): st['UI members paired, PC name != DlcIds.sym(Xbox name)'] += 1
                    ia, ib = Wx.it.get(ma + 16), Wp.it.get(mb + 16)
                    if ia is None or ib is None: continue
                    lx, lp = list(SIP.leaves(Wx, Wx.it, ia)), list(SIP.leaves(Wp, Wp.it, ib))
                    if [p for p, _ in lx] != [p for p, _ in lp]: st['UI members with another init tree shape (skipped)'] += 1; continue
                    st['UI members paired'] += 1
                    for (path, ox), (_, op) in zip(lx, lp):
                        if ox in nx or op in np_ or ox + 4 > len(xd) or op + 4 > len(pd): continue
                        obs[(put, tag, path)].append((bytes(xd[ox:ox + 4]), bytes(pd[op:op + 4])))
    rules, contra = {}, []
    for key, Lo in obs.items():
        st['observations'] += len(Lo)
        info, zero = [], collections.Counter()
        for x, p in Lo:
            outs = {c: L.apply_word(x, c, I) for c in L.CLASSES}
            if x == b'\0\0\0\0': zero[p.hex()] += 1
            if len(set(outs.values())) == 1 and outs['s32'] == p: continue
            cs = {c for c, v in outs.items() if v == p}
            if not cs:
                # the PC holds another VALUE (Crystal re-authored the UI: positions, sizes, the PC-only field) - says
                # nothing about the byte order; counted, never taken over except the zero rule below
                st['observations with a re-authored PC value (no byte order fits)'] += 1; continue
            info.append((x, p, cs))
        zr = None
        if zero and len(zero) == 1:
            v, n = next(iter(zero.items()))
            if v != '00000000' and n >= ZERO_RULE_MIN: zr = v
        if not info and zr is None: st['keys without information'] += 1; continue
        ok = set.intersection(*[s for _, _, s in info]) if info else set()
        if info and not ok and all('s32' in s or ('raw' in s and text_word(x)) for x, _, s in info):
            # a union word: a number (s32) or the first 4 characters of a string ("null", "00") - both seen, nothing else
            rules[key] = ('cls', 's32text', len(info), zr); st['rule s32 / text start raw'] += 1; continue
        if info and not ok:
            if all(s & ID_CLASSES for _, _, s in info):
                rules[key] = ('cls', 'id-mixed', len(info), zr); st['rule id (mixed id classes, kept)'] += 1; continue
            contra.append((key, [(x.hex(), p.hex(), sorted(s)) for x, p, s in info[:6]])); continue
        c = (next((q for q in PREF if q in ok), None) or sorted(ok, key=lambda q: L.CLASSES.index(q))[0]) if ok else None
        rules[key] = ('cls', c, len(info), zr)
        st['rule %s' % c] += 1
        if zr:
            st['zero rule (Xbox 0 -> one PC value in every base observation)'] += 1
            st['zero rule ut %d path %s: base observations' % (key[0], list(key[2]))] = sum(zero.values())
    # Q46: locals string id leaves - per Xbox index the PC ids of ALL base observations; one id other than the map's =
    # the PC's own prompt (LOC_PC); several ids = the map is kept (counted)
    LOC_PC.clear()
    for key, r in rules.items():
        if r[1] not in LOC_CLASSES: continue
        seen = collections.defaultdict(set)
        for x, p in obs[key]:
            hi, lo = struct.unpack('>HH', x)
            if lo or hi in (0, 0xffff): continue
            seen[hi].add(struct.unpack('<I', p)[0])
            st['locals text id base observations: %s' % ('= map' if L.apply_word(x, r[1], I) == p else 'other PC id')] += 1
        for hi, ps in seen.items():
            if len(ps) > 1: st['locals text ids with several PC ids on the base (map kept)'] += 1; continue
            pv = next(iter(ps))
            if struct.pack('<I', pv) != L.apply_word(struct.pack('>HH', hi, 0), r[1], I):
                LOC_PC.setdefault(key, {})[hi] = pv
        st['locals text ids: PC prompt ids learned'] += len(LOC_PC.get(key, {}))
    st['contradictions'] = len(contra)
    return rules, st, contra


def xbox_sections(name, cache):
    """all Xbox sections of the DRM's source (list of drm.sections_with_data dicts, [] when none)"""
    if name not in cache:
        import convert_dlc as CD
        from drm import cdrm_decode, sections_with_data
        raw, _ = CD.raw_dlc(name)
        cache[name] = sections_with_data(cdrm_decode(raw, 'be'), 'be')[1] if raw else []
    return cache[name]


def plan_drm(path, rules, cache, st):
    """[(section index, offset, old, new, script id, key, class)] for one PC DRM"""
    import dlc_script_pairs as SP
    I = ids()
    D = DW.read(open(path, 'rb').read(), 'le')
    out = []
    pm = None
    for si, s in enumerate(D.sections):
        if s.type != 8 or not s.data: continue
        W, rel = walk(s.data, s.reloc, 'le')
        mem = SIP.members(W, s.data, 'le')
        ui = [(k, a) for k, la in mem.items() if k[3] in UI_UTS for a in la if W.it.get(a + 16) is not None]
        if not ui: continue
        if pm is None:
            # Q46: the Xbox script by the converter's id map + name Symbol (dlc_script_pairs; until 2026-11-11 the
            # Xbox section of the PC id: renumbered scripts such as g_pda PC 3347 = Xbox 3207 had none)
            pm, pst = SP.pairs(xbox_sections(os.path.basename(path), cache), D, I)
            for k, v in pst.items(): st['pairing: ' + k] += v
        x, route = pm.get(si, (None, None))
        if x is None: st['scripts with UI members but no Xbox section (kept)'] += 1; continue
        if route == 'pc_copy': st['scripts with UI members, PC bytes (route pc_copy, kept)'] += 1; continue
        if x['id'] != s.id: st['scripts with UI members, renumbered (Xbox id != PC id)'] += 1
        xd = x['data']
        if len(xd) != len(s.data): st['scripts with another size than the Xbox section (kept)'] += 1; continue
        nt = no_touch(rel)
        st['scripts with UI members'] += 1
        seen = set()
        for (arr, nm, tag, ut), a in ui:
            for path_, o in SIP.leaves(W, W.it, W.it[a + 16]):
                if o in seen or o in nt or o + 4 > len(xd): continue
                seen.add(o)
                r = rules.get((ut, tag, path_))
                pw = bytes(s.data[o:o + 4]); xw = bytes(xd[o:o + 4])
                if r is None: st['UI words without a base rule (kept)'] += 1; continue
                _, c, _, zr = r
                if zr is not None and xw == b'\0\0\0\0':
                    new, c = bytes.fromhex(zr), 'zero->%s' % zr
                elif c is None: st['UI words with only a zero rule, Xbox not 0 (kept)'] += 1; continue
                elif c in LOC_CLASSES:
                    hi, lo = struct.unpack('>HH', xw)
                    I.loc(1)                                    # loads the map (hard error when missing)
                    if lo or hi == 0xffff: st['UI text id words not in the index form (kept)'] += 1; continue
                    if hi == 0: new = L.apply_word(xw, c, I)
                    elif hi in LOC_PC.get((ut, tag, path_), {}): new, c = struct.pack('<I', LOC_PC[(ut, tag, path_)][hi]), c + ' PC prompt'
                    elif hi in I._loc: new = L.apply_word(xw, c, I)
                    else: st['UI text id words outside the locals map (kept)'] += 1; continue
                    st['UI text id words (locals map)'] += 1
                elif c == 'id-mixed' or c in ID_CLASSES: st['UI id words (kept: converter id maps)'] += 1; continue
                elif c == 's32text': new = xw if text_word(xw) else L.apply_word(xw, 's32', I)
                else: new = L.apply_word(xw, c, I)
                if new == pw: st['UI words already right'] += 1; continue
                out.append((si, o, pw, new, s.id, (ut, tag, path_), c, xw))
    return D, out


def drms(tree):
    for r, _, fs in os.walk(tree):
        for f in sorted(fs):
            if f.lower().endswith('.drm'): yield os.path.join(r, f)


def run_tree(tree, write, rules, report):
    cache, st, rows, bad = {}, collections.Counter(), [], 0
    for p in drms(tree):
        try:
            D, plan = plan_drm(p, rules, cache, st)
        except Exception as ex:
            st['DRMs not read'] += 1; print('%s: not read (%s)' % (p, ex)); continue
        if not plan: continue
        st['DRMs with changes'] += 1; st['words changed'] += len(plan)
        for si, o, old, new, sid, key, c, xw in plan:
            rows.append(dict(drm=os.path.basename(p), script=sid, off=o, old=old.hex(), new=new.hex(), ut=key[0],
                             path=list(key[2]), rule=c, xbox=xw.hex()))
        print('%s: %d words (scripts %s)' % (os.path.basename(p), len(plan), ','.join(sorted({str(x[4]) for x in plan}))))
        if not write: continue
        old_raw = open(p, 'rb').read()
        before = DW.read(old_raw, 'le')
        for si, o, oldw, new, *_ in plan:
            s = D.sections[si]
            d = bytearray(s.data); d[o:o + 4] = new; s.data = bytes(d)
        raw = DW.cdrm_encode(D.write('le'), 'le')
        E = DW.read(raw, 'le')
        want = {(si, o): new for si, o, _, new, *_ in plan}
        ok = len(E.sections) == len(before.sections)
        for si, (a, b) in enumerate(zip(before.sections, E.sections)):
            if (a.type, a.id, a.reloc) != (b.type, b.id, b.reloc) or len(a.data) != len(b.data): ok = False; break
            for o in range(0, len(a.data), 4):
                exp = want.get((si, o), a.data[o:o + 4])
                if b.data[o:o + 4] != exp: ok = False; break
            if len(a.data) % 4 and a.data[-(len(a.data) % 4):] != b.data[-(len(a.data) % 4):]: ok = False
            if not ok: break
        if not ok:
            bad += 1; print('%s: write does NOT prove - file left unchanged' % p); continue
        open(p, 'wb').write(raw)
        st['DRMs written'] += 1
    for k in sorted(st): print('  %-60s %d' % (k, st[k]))
    if report:
        json.dump(dict(tree=os.path.relpath(tree), write=write, stats=dict(st), rows=rows), open(report, 'w'), indent=1)
    return st, bad


def main(argv):
    if not argv:
        print(__doc__); return 2
    rep = None
    if '--report' in argv: k = argv.index('--report'); rep = argv[k + 1]; del argv[k:k + 2]
    if '--pack' in argv:
        k = argv.index('--pack'); os.environ['TRUDLC_PACK_FIRST'] = argv[k + 1]; del argv[k:k + 2]
    rules, st, contra = learn()
    if argv[0] == 'proof':
        for k in sorted(st): print('  %-60s %d' % (k, st[k]))
        for key, ex in contra: print('CONTRADICTION ut %d tag %#x path %s: %s' % (key[0], key[1], key[2], ex))
        pin = [k for k, v in PINNED.items() if st.get(k) != v]
        for k in pin: print('PINNED COUNT DIFFERS: %s = %s (pinned %s)' % (k, st.get(k), PINNED[k]))
        maps = {('%d %#x %s' % (k[0], k[1], list(k[2]))): r[3] for k, r in rules.items() if r[3]}
        for k, v in sorted(maps.items()): print('zero rule %s: Xbox 0 -> %s' % (k, v))
        for k, m in sorted(LOC_PC.items()):
            print('locals text id %d %#x %s: PC prompt ids %s' % (k[0], k[1], list(k[2]), dict(sorted(m.items()))))
        print('rules %d (%s), contradictions %d' % (len(rules), ', '.join('%s %d' % kv for kv in sorted(collections.Counter(
            str(r[1]) for r in rules.values()).items())), len(contra)))
        if rep:
            json.dump(dict(stats=dict(st), contradictions=[[list(map(str, k)), e] for k, e in contra], zero_rules=maps,
                           loc_pc={'%d %#x %s' % (k[0], k[1], list(k[2])): {str(a): b for a, b in sorted(m.items())}
                                   for k, m in LOC_PC.items()},
                           rules={'%d %#x %s' % (k[0], k[1], list(k[2])): [r[1], r[2], r[3]] for k, r in rules.items()}),
                      open(rep, 'w'), indent=1)
        return 1 if contra or pin else 0
    if contra:
        print('base rule has %d contradictions - not applied (run proof)' % len(contra)); return 1
    if argv[0] in ('scan', 'apply') and len(argv) == 2:
        st2, bad = run_tree(argv[1], argv[0] == 'apply', rules, rep)
        if argv[0] == 'scan': return 1 if st2.get('words changed') else 0
        return 1 if bad else 0
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
