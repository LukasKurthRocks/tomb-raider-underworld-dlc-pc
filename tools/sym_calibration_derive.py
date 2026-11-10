"""Derive the 167 Symbol values of docs/data/b138_symbol_calibration.json from our own data instead of B138
(kit independence stage 3; developer tool: reads the Xbox <-> PC base pair cache, writes a small JSON of numbers).

The calibration (WINDOWS_REBUILD findings 33 / 35) holds Xbox Symbols (cdc::Symbol u16, script name ids) that the
learned symbol map (generic_symbols, work/generic/idmap.json key 100) lacks, with the PC value B138's DLC 1 words
carry; dlc_generic.DlcIds uses them for exact lookups. Our own evidence for such a Symbol can only come from the base
game, where the same script exists on the Xbox and on PC:
  name    function / prototype names paired by script_conv.offset_map (sym_calibration_check)
  member  DataMember names (members / arguments / locals) paired by index + data offset
  call    call sites: both code words have an external relocation into the same function -> its two names (x10)
  raw     code / init words of equal-layout pairs: Xbox u16 half = the Symbol, the word not a u32 number, the other
          half unchanged, mapped or another wanted Symbol (u16-pair form) -> the PC half; used only for Symbols without
          the three above,
          top value >= 2 votes and >= 75 % of them
over every script pair of work/generic/pairs.pkl (1 054 retail Xbox <-> PC bigfile DRM pairs) and pairs_patch.pkl
(title update generalbank / globalsoundinfo <-> PC patch.000 / bigfile, l2_puzzleroom / g_pda), each distinct script
pair once. Choice per Symbol as in sym_calibration_check: strongest evidence first, injective (a PC Symbol taken by
the learned map or a stronger vote is not given twice). A Symbol without base evidence gets the converter's own rule
(DlcIds.sym without any calibration: interpolation in a consistent span, else lower neighbour, collision 40000 + xs)
- that is what the converter does anyway when the calibration is off, so only evidence entries go into the file.

Gate (check): derived value == the B138 value for all 167. The pipeline is switched to the derived file only if
the gate is 100 %; otherwise the differences are listed by class and the switch stays the owner's decision.

Usage (from the repository root; ~3 GB of memory for the pair cache, a few minutes):
  ../bin/pyt -t 1800 tools/sym_calibration_derive.py derive [--out docs/data/sym_calibration_derived.json]
  ../bin/pyt -t 120 tools/sym_calibration_derive.py check [--derived JSON] [--report OUT.json]
        exit 0 when derived == B138 for every Symbol, else 1 (the list is printed / written)
"""
import sys, os, json, struct, hashlib, collections, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, '..')
CAL = os.path.join(REPO, 'docs', 'data', 'b138_symbol_calibration.json')
OUT = os.path.join(REPO, 'docs', 'data', 'sym_calibration_derived.json')
GEN = os.path.join(REPO, 'work', 'generic')


def load_cal():
    d = json.load(open(CAL))
    return {int(a): b for a, b in d.get('symbols', d).items()}


def raw_votes(x, p, want, symmap, votes):
    """code / init words: same size, same pointer / id layout; a word whose PC value is NOT the u32-swapped Xbox word
    (then it is a number) and whose other u16 half is the Xbox half unchanged or mapped by the learned map (u16-pair
    form, the form of every Symbol field) votes Xbox half -> PC half for the Symbols in `want`"""
    import drm_reloc as R
    xd, pd = x['data'], p['data']
    if len(xd) != len(pd): return
    rx, rp = R.parse(x['reloc'], 'be'), R.parse(p['reloc'], 'le')
    skip = set(rx.pointer_offsets()) | set(rx.id_offsets())
    if skip != set(rp.pointer_offsets()) | set(rp.id_offsets()): return
    for o in range(0, len(xd) - 3, 4):
        if o in skip: continue
        xh = struct.unpack_from('>HH', xd, o)
        if xh[0] not in want and xh[1] not in want: continue
        if struct.unpack_from('<I', pd, o)[0] == struct.unpack_from('>I', xd, o)[0]: continue     # a u32 number
        ph = struct.unpack_from('<HH', pd, o)
        for h in (0, 1):
            if xh[h] not in want: continue
            ox, op = xh[1 - h], ph[1 - h]
            # the other half: unchanged, mapped by the learned map, or itself one of the wanted Symbols (a pair of
            # two unmapped Symbols in one word, e.g. Xbox 4483 / 4484)
            if op == ox or symmap.get(ox) == op or (ox in want and op != ox): votes[xh[h]][ph[h]] += 1


def collect(symmap, ids, want):
    """votes {xbox Symbol: Counter(pc Symbol)} by kind over all distinct script pairs of the base pair cache"""
    import drm_reloc as R
    import script_conv as SC
    import sym_calibration_check as SCC
    votes = {k: collections.defaultdict(collections.Counter) for k in ('name', 'member', 'call', 'raw')}
    tu = {k: collections.defaultdict(collections.Counter) for k in votes}
    kinds = collections.Counter(); seen = set(); st = collections.Counter()
    srcs = [('base', os.path.join(GEN, 'pairs.pkl')), ('patch', os.path.join(GEN, 'pairs_patch.pkl'))]
    for label, path in srcs:
        P = pickle.load(open(path, 'rb'))
        st[label + ' drm pairs'] = len(P)
        for nm in sorted(P):
            (xh, xs), (ph, ps) = P[nm]
            pc = {s['id']: s for s in ps if s['type'] == 8 and s['data']}
            tcache = {}
            for x in xs:
                if x['type'] != 8 or not x['data']: continue
                p = pc.get(ids(8, x['id']))
                if p is None: st['script without a PC partner'] += 1; continue
                h = hashlib.md5(x['data'] + x['reloc'] + b'|' + p['data'] + p['reloc']).digest()
                if h in seen: st['script pair seen before'] += 1; continue
                seen.add(h)
                one = {k: collections.defaultdict(collections.Counter) for k in votes}
                try:
                    SC.offset_map(x['data'], R.parse(x['reloc'], 'be'), p['data'], R.parse(p['reloc'], 'le'), symmap,
                                  one['name'])
                    SCC.member_votes(x, p, symmap, one['member'], kinds)
                    SCC.call_votes(x, p, xs, ps, symmap, one['call'], kinds, tcache)
                    raw_votes(x, p, want, symmap, one['raw'])
                    st['script pairs (%s)' % label] += 1
                except Exception as e:
                    st['script walk failed'] += 1; continue
                for k in votes:
                    for a, c in one[k].items():
                        votes[k][a].update(c)
                        # the title-update era pairs separately: do DLC-era scripts number these Symbols like retail?
                        if label == 'patch' and a in want: tu[k][a].update(c)
        del P
    return votes, kinds, st, tu


RAW_MIN, RAW_SHARE = 2, 0.75     # raw words: at least 2 votes and 75 % of the Symbol's raw votes for the top value


def choose(votes, symmap):
    """injective choice in three rounds, strongest evidence first within a round (call votes already weighted x10):
    1. names (name / member / call) with >= 2 votes, for every Symbol outside the learned map;
    2. raw words for the rest: identity votes dropped (the u16 is then a plain number, e.g. 368 -> 368 in 108 words),
       top value >= RAW_MIN votes and >= RAW_SHARE of the remaining raw votes;
    3. names with a single vote. (Round order measured on the calibration Symbols: the single member votes of 364..441
       all come from one script pair and contradict 157 raw words, e.g. 375 -> 714.)"""
    tot = collections.defaultdict(collections.Counter)
    for k in ('name', 'member', 'call'):
        for a, c in votes[k].items():
            if a not in symmap: tot[a].update(c)
    raw = {a: collections.Counter({p: n for p, n in c.items() if p != a}) for a, c in votes['raw'].items()}
    taken = set(symmap.values()); best = {}; how = {}

    def names_round(single):
        order = sorted((a for a in tot if a not in best), key=lambda a: (-tot[a].most_common(1)[0][1], a))
        for a in order:
            if (tot[a].most_common(1)[0][1] >= 2) == single: continue
            pick = next(((p, n) for p, n in tot[a].most_common() if p not in taken), None)
            if pick is None: continue
            best[a] = pick[0]; taken.add(pick[0])
            how[a] = 'base evidence (names, single vote)' if single else 'base evidence (names)'
    names_round(False)
    for a in sorted((a for a in raw if raw[a] and a not in best and a not in symmap),
                    key=lambda a: (-raw[a].most_common(1)[0][1], a)):
        (p, n), = raw[a].most_common(1)
        if n < RAW_MIN or n < RAW_SHARE * sum(raw[a].values()) or p in taken: continue
        best[a] = p; taken.add(p); how[a] = 'base evidence (raw words)'
    names_round(True)
    return best, how


def derive(out):
    os.environ['TRUDLC_SYM_EXTRA'] = 'off'       # the converter's own rule, no calibration
    import dlc_generic as DG
    ids = DG.DlcIds(); symmap = ids.base.get(DG.SYM, {})
    cal = load_cal()
    votes, kinds, st, tu = collect(symmap, ids, set(cal))
    best, how = choose(votes, symmap)
    rows = {}; ev = {}
    for xs in sorted(cal):
        ids.sym_stats = collections.Counter()
        rule = ids.sym(xs); route = ','.join(ids.sym_stats)
        r = dict(b138=cal[xs], rule=rule, rule_route=route,
                 votes={k: votes[k][xs].most_common(3) for k in votes if votes[k].get(xs)},
                 tu_era_votes={k: tu[k][xs].most_common(3) for k in tu if tu[k].get(xs)})
        if xs in best:
            r.update(derived=best[xs], method=how[xs])
            # a single name vote is too weak for the file (364..441: one script pair, contradicted by raw words)
            if 'single vote' not in how[xs]: ev[str(xs)] = best[xs]
        else:
            r.update(derived=rule, method='converter rule (%s)' % route)
        rows[str(xs)] = r
    doc = dict(about=('Xbox Symbol -> PC Symbol for the 167 Symbols of b138_symbol_calibration.json, derived from our '
                      'own data (base-game Xbox <-> PC script pairs: function / prototype / member names, call sites, '
                      'raw code words) by tools/sym_calibration_derive.py; "symbols" holds only the Symbols with base '
                      'evidence of >= 2 votes (the others get the converter rule anyway when no calibration is '
                      'loaded), usable as TRUDLC_SYM_EXTRA. "detail" = per Symbol B138 value, derived value, method, '
                      'top votes (all pairs) and tu_era_votes (title-update generalbank <-> PC patch.000 only).'),
               symbols=ev, detail=rows,
               stats=dict(st), vote_kinds=dict(kinds),
               evidence_symbols_outside_map=len(best))
    open(out, 'w', encoding='utf-8', newline='\n').write(json.dumps(doc, indent=0, sort_keys=False) + '\n')
    print('script pairs / stats:', dict(st))
    print('Symbols outside the learned map with base evidence: %d; of the %d calibration Symbols: %d' % (
        len(best), len(cal), len(ev)))
    print('written', os.path.normpath(out))


CLASS_ORDER = ['equal (base evidence)', 'equal (converter rule)', 'DIFFERS: base evidence (>= 2 votes) contradicts B138',
               'DIFFERS: single name vote only (weak, not in "symbols")',
               'DIFFERS: no base evidence, B138 = 40000 + xs (upstream collision fallback)',
               'DIFFERS: no base evidence, other B138 value']


def classify(xs, r):
    ev = r['method'].startswith('base evidence')
    if r['derived'] == r['b138']:
        return CLASS_ORDER[0] if ev else CLASS_ORDER[1]
    if 'single vote' in r['method']: return CLASS_ORDER[3]
    if ev: return CLASS_ORDER[2]
    if r['b138'] == 40000 + xs: return CLASS_ORDER[4]
    return CLASS_ORDER[5]


def check(path, report):
    d = json.load(open(path)); cal = load_cal()
    rows = d['detail']
    miss = [xs for xs in cal if str(xs) not in rows]
    cls = collections.defaultdict(list)
    for xs in sorted(cal):
        r = rows.get(str(xs))
        if r is None: continue
        if r['b138'] != cal[xs]: raise SystemExit('derived file is stale: B138 value of %d changed' % xs)
        cls[classify(xs, r)].append(xs)
    eq = len(cls[CLASS_ORDER[0]]) + len(cls[CLASS_ORDER[1]])
    print('derived == B138: %d of %d (%.1f %%)%s' % (eq, len(cal), 100.0 * eq / len(cal),
                                                    '; missing %d' % len(miss) if miss else ''))
    for c in CLASS_ORDER:
        xs = cls.get(c, [])
        print('  %-75s %3d' % (c, len(xs)))
        if c.startswith('DIFFERS') and xs:
            print('     ' + ', '.join('%d: b138 %d / derived %d' % (x, rows[str(x)]['b138'], rows[str(x)]['derived'])
                                      for x in xs[:60]) + (' ...' if len(xs) > 60 else ''))
    tu_ok = [x for x in cls.get(CLASS_ORDER[2], []) if any(v and v[0][0] == rows[str(x)]['derived']
                                                          for v in rows[str(x)].get('tu_era_votes', {}).values())]
    tu_b138 = [x for x in cls.get(CLASS_ORDER[2], []) if any(v and v[0][0] == rows[str(x)]['b138']
                                                            for v in rows[str(x)].get('tu_era_votes', {}).values())]
    print('  of the contradicted: title-update era scripts (TU generalbank <-> PC patch.000) give the derived value for '
          '%d, the B138 value for %d' % (len(tu_ok), len(tu_b138)))

    weak = cls.get(CLASS_ORDER[3], [])
    b138_seen = [x for x in cls.get(CLASS_ORDER[2], []) + weak if any(
        p == rows[str(x)]['b138'] for v in rows[str(x)].get('votes', {}).values() for p, n in v)]
    print('  of the contradicted / weak: the B138 value is among the top base candidates (e.g. a lower raw-word vote) '
          'for %d: %s' % (len(b138_seen), ', '.join(map(str, b138_seen))))
    ok = eq == len(cal) and not miss
    if report:
        json.dump(dict(equal=eq, total=len(cal), missing=miss, classes={c: cls.get(c, []) for c in CLASS_ORDER},
                       contradicted_tu_era_derived=tu_ok, contradicted_tu_era_b138=tu_b138,
                       contradicted_single_vote=weak, contradicted_b138_among_candidates=b138_seen,
                       gate='ok' if ok else 'FAILED'), open(report, 'w'), indent=1)
    print('gate', 'ok' if ok else 'FAILED (pipeline stays on b138_symbol_calibration.json)')
    return 0 if ok else 1


def main(a):
    out = OUT
    if '--out' in a: k = a.index('--out'); out = a[k + 1]; del a[k:k + 2]
    if '--derived' in a: k = a.index('--derived'); out = a[k + 1]; del a[k:k + 2]
    rep = None
    if '--report' in a: k = a.index('--report'); rep = a[k + 1]; del a[k:k + 2]
    if a[:1] == ['derive']:
        derive(out); return 0
    if a[:1] == ['check']:
        return check(out, rep)
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
