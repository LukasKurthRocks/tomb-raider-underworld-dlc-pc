"""Xbox -> PC Symbol entries proven by declaration-order twins (Q58, 2026-11-11) -> docs/data/symbol_twins.json, read by
dlc_generic.DlcIds.sym as exact entries after the learned base map (before the B138 calibration and every guess).

Why: a script member / argument / local name is a cdc::Symbol (a global string id). Where the learned base map has no
entry, DlcIds.sym guesses it (interpolation, 'guess_lower') or takes the B138 calibration; Q55 measured that only 1 492
of 2 946 aligned PC member names equal that guess and that the calibration names another member in 234 / 234 aligned
cases. The PC twin of an Xbox entry (script_member_pairs.align: monotonic alignment of the declaration order by type
tag, userType, base-map name and init words; 623 / 7 against the text id referee) carries the PC name of the same
Symbol. Converted DLC scripts are self-consistent either way (member names and path words go through the same map,
Q58 measurement), so the twin names matter where converted data meets PC data by name: a PC-byte script (route
pc_copy / pc_reauthored), a ported member copied from its PC twin (gpda_port), the engine's or TruMenu's name lookups.

Rule (build): every base script pair (Xbox base content of the store -> PC content of the base-mapped id; 7 259 pairs):
pairs of the same size and the same internal relocation layout pair their entries at the same offset, every other pair
through script_member_pairs.align. Votes Xbox Symbol -> PC Symbol: each paired member / argument name (locals only in
pairs of the same layout: aligned locals 186 = / 7 != against the base map), each paired entry's userType (same layout
only), the script name (root +0x08) and, in pairs of the same layout, the prototype names. Referee = the learned base
map, independent of the alignment (2026-11-11: 30 078 voting observations, 0 !=). 6 147 entries, 1 596 of them
differ from the old route (guess_lower 877, interpolated 498, calibration 130, collision 91). An Xbox Symbol gets an entry when (1) the
base map has none, (2) it is not TU / DLC-new (> the Xbox base map maximum, no PC twin by definition), (3) ALL its
votes name one PC Symbol, (4) that PC Symbol is no base-map value and no other Symbol's twin. A vote != the base map
would disprove the alignment (exit 1). DLC-only names (no twin anywhere) keep DlcIds' rule; a guess that hits a twin's
PC Symbol takes DlcIds' collision rule 40000 + Xbox, so it stays unique.

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/symbol_twins.py build [--out FILE]   derive and write (default docs/data/symbol_twins.json)
  ../bin/pyt -t 3600 tools/symbol_twins.py check                derive again, exit 1 when it differs from the file or a
                                                               base-map vote disagrees
"""
import sys, os, json, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_reloc as R
import script_member_pairs as MP

OUT = os.path.join(HERE, '..', 'docs', 'data', 'symbol_twins.json')
DISAGREE = []


def ids_no_twins():
    """DlcIds without the twin entries (the derivation must not read its own output)"""
    os.environ['TRUDLC_SYM_TWINS'] = 'off'
    import dlc_generic as DG
    return DG.DlcIds()


def derive():
    import dlc_script_pairs as SP
    from dlc_generic import SYM
    I = ids_no_twins()
    store = SP.store()
    bm8 = I.base.get(8, {}); sm = I.base[SYM]
    votes = collections.defaultdict(collections.Counter)
    src_same, src_al = set(), set()
    st = collections.Counter()
    for (t, x), xb in sorted(store['xb_store'].items()):
        if t != 8 or not xb.get('data'): continue
        pc = store['pc_store'].get((8, bm8.get(x)))
        if pc is None or not pc.get('data'): st['Xbox base scripts without a PC pair'] += 1; continue
        xd, xrl, pd, prl = xb['data'], xb['reloc'], pc['data'], pc['reloc']
        try:
            Wx, ex = MP.entries(xd, xrl, 'be'); _, ep = MP.entries(pd, prl, 'le')
        except Exception:
            st['pairs not walked'] += 1; continue
        same = len(xd) == len(pd) and R.parse(xrl, 'be').internal == R.parse(prl, 'le').internal
        if same:
            pa = {q['a']: q for k in MP.KINDS for q in ep[k]}
            tw = {q['a']: q['a'] for k in MP.KINDS for q in ex[k] if q['a'] in pa}
            st['pairs of the same layout (twin = same offset)'] += 1
        else:
            tw, _ = MP.align(xd, xrl, pd, prl, I)
            st['pairs of another layout (script_member_pairs.align)'] += 1
        pn = {q['a']: q['name'] for k in MP.KINDS for q in ep[k]}
        put = {q['a']: q['ut'] for k in MP.KINDS for q in ep[k]}
        for k in MP.KINDS:
            for q in ex[k]:
                b = tw.get(q['a'])
                if b is None: continue
                if q['name'] in (0, 0xffff): continue
                # aligned locals do not vote: across all functions of a re-authored script the walk-order alignment
                # pairs other locals where the PC added / removed functions (referee base map: 186 = / 7 != - all
                # Symbol 249, scripts 6, 9, 10, 2843, 3226, 13272); members 224 / 0, args 255 / 0, same layout 13 957 / 0
                if k == 'locals' and not same:
                    if q['name'] in sm:
                        st['referee aligned locals (not voting): base-map Symbol, PC name %s map' % (
                            '=' if sm[q['name']] == pn[b] else '!=')] += 1
                    continue
                votes[q['name']][pn[b]] += 1
                (src_same if same else src_al).add(q['name'])
                st['%s: twin votes' % k] += 1
                # the userType Symbol of the twin's DataType (+0x04; type name of a native / struct type) - only from
                # pairs of the same layout: align scores userType equality itself, and no userType Symbol has a
                # base-map entry to referee the aligned ones (Q58: 0 referee observations)
                xu, pu = q['ut'], put[b]
                if xu not in (0, 0xffff) and same:
                    votes[xu][pu] += 1
                    (src_same if same else src_al).add(xu)
                    st['userTypes: twin votes'] += 1
                    if xu in sm:
                        st['referee %s userTypes: base-map Symbol, PC name %s map' % (
                            'same layout' if same else 'aligned', '=' if sm[xu] == pu else '!=')] += 1
                        if sm[xu] != pu:
                            DISAGREE.append('script %d %s Xbox +0x%x userType %d (map %d) -> PC %d' % (x, k, q['a'], xu, sm[xu], pu))
                if q['name'] in sm:     # referee: the learned base map (independent of the alignment)
                    st['referee %s %s: base-map Symbol, PC name %s map' % (
                        'same layout' if same else 'aligned', k, '=' if sm[q['name']] == pn[b] else '!=')] += 1
                if q['name'] in sm and sm[q['name']] != pn[b]:
                    DISAGREE.append('script %d %s Xbox +0x%x name %d (map %d) -> PC +0x%x name %d (%s)' % (
                        x, k, q['a'], q['name'], sm[q['name']], b, pn[b], 'same layout' if same else 'aligned'))
        # the script's own name (root +0x08, ScriptName = two Symbols; the pair is the base id map's) and, in a pair
        # of the same layout, the prototype names at the same offset (+0x08 of each 28-byte Prototype)
        named = [('script names', 8)]
        if same:
            named += [('prototype names', t + 28 * j + 8) for nm, t, n, sz in Wx.arrays if nm == 'protos' for j in range(n)]
        for k, o in named:
            if o + 4 > len(xd) or o + 4 > len(pd): continue
            for xs_, ps_ in zip(struct.unpack_from('>HH', xd, o), struct.unpack_from('<HH', pd, o)):
                if xs_ in (0, 0xffff): continue
                votes[xs_][ps_] += 1
                (src_same if same else src_al).add(xs_)
                st['%s: twin votes' % k] += 1
                if xs_ in sm:
                    st['referee %s %s: base-map Symbol, PC name %s map' % (
                        'same layout' if same else 'aligned', k, '=' if sm[xs_] == ps_ else '!=')] += 1
                    if sm[xs_] != ps_:
                        DISAGREE.append('script %d %s +0x%x Xbox %d (map %d) -> PC %d' % (x, k, o, xs_, sm[xs_], ps_))
    used = set(sm.values())
    cand = {}
    for xs, c in votes.items():
        if xs in sm:
            st['base-map Symbols: votes = map' if set(c) == {sm[xs]} else 'base-map Symbols: a vote != map'] += 1
            continue
        if xs > I.xs_max: st['TU / DLC-new Symbols (no twin by rule)'] += 1; continue
        if len(c) > 1: st['Symbols with disagreeing votes (no entry)'] += 1; continue
        (p, n), = c.items()
        if p in used: st['Symbols whose twin name is a base-map value (no entry)'] += 1; continue
        cand[xs] = p
    inv = collections.Counter(cand.values())
    out = {}
    for xs, p in sorted(cand.items()):
        if inv[p] > 1: st['Symbols sharing a twin name with another (no entry)'] += 1; continue
        out[xs] = p
        r = route(I, xs)
        st['entries: route before %s, %s' % (r, '= guess' if I.sym(xs) == p else '!= guess')] += 1
        st['entries: %s the base-map bracket, votes from %s' % ('inside' if bracket_ok(I, xs, p) else 'OUTSIDE',
            'same-layout pairs' if xs in src_same else 'aligned pairs only')] += 1
    st['entries'] = len(out)
    return out, st


def bracket_ok(I, xs, p):
    """p lies strictly between the PC values of the nearest base-mapped Xbox Symbols below and above xs (the base map
    is near-monotone: Symbols are interned in source order on both platforms)"""
    import bisect
    from dlc_generic import SYM
    m = I.base[SYM]
    k = bisect.bisect_left(I.sks, xs)
    lo = m[I.sks[k - 1]] if k > 0 else -1
    hi = m[I.sks[k]] if k < len(I.sks) else 1 << 20
    return lo < p < hi


def route(I, xs):
    import script_path_check as C
    return C.sym_route(I, xs)


def main(argv):
    if not argv or argv[0] not in ('build', 'check'):
        print(__doc__); return 2
    out_path = OUT
    if '--out' in argv: k = argv.index('--out'); out_path = argv[k + 1]; del argv[k:k + 2]
    m, st = derive()
    for k in sorted(st): print('  %-70s %d' % (k, st[k]))
    for e in DISAGREE: print('  base-map disagreement:', e)
    bad = st.get('base-map Symbols: a vote != map', 0)
    if argv[0] == 'build':
        doc = dict(rule=__doc__.split('\n\n')[2], stats=dict(st), symbols={str(a): b for a, b in sorted(m.items())})
        with open(out_path, 'w', encoding='utf-8', newline='\n') as f: json.dump(doc, f, indent=0, sort_keys=False)
        print('%d entries -> %s' % (len(m), out_path))
    else:
        old = {int(a): b for a, b in json.load(open(out_path, encoding='utf-8'))['symbols'].items()}
        diff = sorted(set(old.items()) ^ set(m.items()))
        print('file %d entries, derived %d, differing %d' % (len(old), len(m), len(diff)))
        if diff: bad += 1
    if bad: print('FAIL: base-map votes disagree or the file differs'); return 1
    print('ok')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
