"""Check the B138 symbol calibration against base-game evidence (finding 43, DLC 2 test 4).

The learned symbol map lacks some Xbox Symbols; docs/data/b138_symbol_calibration.json fills them from B138's DLC 1
words (findings 33, 35). The base game gives independent evidence for function/prototype NAME Symbols: the same script
exists on the Xbox (retail layers) and on PC, and script_conv.offset_map pairs its functions/prototypes; pairs whose
Xbox name the learned map does not know vote xbox symbol -> PC symbol (positional runs of equal length, or by
structure). Example: generalbank script 6, function 1 has Xbox name 515 and PC name 517 (same slot, same 45 code
words), but the calibration maps 515 -> 333.
DataMember names (members, function arguments, locals) vote too: the i-th array of a kind on both sides when the
counts match, elements by index when their data offset matches as well (DLC 2 test 5b: 51 of 198 member names of the
converted retail script 6 differed from the PC). For names the learned map knows, agreement is counted as a check of
the check.

Reports per Symbol with base evidence: calibration agrees / disagrees / has no entry, and writes
work/rebuild/sym_base_evidence.json = {"symbols": {xbox: pc}} (majority vote, the calibration overridden where the base
disagrees) - usable as TRUDLC_SYM_EXTRA for converting base-game scripts (title-update generalbank).

Usage (from the repository root; loads the id store):
  ..\\bin\\venv\\Scripts\\python.exe -u -I -X utf8 tools/sym_calibration_check.py [NAME.drm ...]   (default generalbank.drm)
"""
import sys, os, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtp_word_classes as C, dlc_generic as DG, drm_reloc as R, script_conv as SC

BS = chr(92)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'rebuild', 'sym_base_evidence.json')


def member_votes(x, p, symmap, votes, kinds):
    """DataMember names (members, function args, locals): the i-th array of a kind on both sides when the counts
    match, elements by index when their data offset (u16 at +12) matches too; votes for names the map lacks"""
    wx = SC.Walk(x['data'], R.parse(x['reloc'], 'be'), 'be'); wx.run()
    wp = SC.Walk(p['data'], R.parse(p['reloc'], 'le'), 'le'); wp.run()
    for kind in ('members', 'args', 'locals'):
        ax = [a for a in wx.arrays if a[0] == kind]; ap = [a for a in wp.arrays if a[0] == kind]
        for (_, tx, nx, sx), (_, tp, np_, sp) in zip(ax, ap):
            if nx != np_ or sx != 20 or sp != 20: continue
            for k in range(nx):
                xo, xn = struct.unpack_from('>HH', x['data'], tx + 20 * k + 12)
                po, pn = struct.unpack_from('<HH', p['data'], tp + 20 * k + 12)
                if xo != po or xn in (0, 0xffff): continue
                if xn in symmap: kinds['learned map %s (%s)' % ('agrees' if symmap[xn] == pn else 'DISAGREES', kind)] += 1; continue
                votes[xn][pn] += 1; kinds[kind] += 1


CALL_WEIGHT = 10     # a call site names its target exactly; positional pairing of look-alike natives does not


def call_votes(x, p, xsecs, psecs, symmap, votes, kinds, names):
    """Call sites: functions paired by index (equal function counts), code of equal length compared word by word;
    where both have an external relocation at the same code word, the two targets are the same function -> vote
    target name (Xbox) -> target name (PC). Ground truth for natives that look alike (DLC 2 test 5c: script 87
    function 31 is PC function 35, positional pairing said 33)."""
    def tnames(secs, i, e):
        if (e, i) not in names:
            s = secs[i]; nm = {}
            if s['type'] == 8 and s['data']:
                el = SC.elements(s['data'], R.parse(s['reloc'], e), e)
                for k in ('funcs', 'protos'): nm.update({a: v for a, v, f in el.get(k, [])})
            names[e, i] = nm
        return names[e, i]
    rx, rp = R.parse(x['reloc'], 'be'), R.parse(p['reloc'], 'le')
    ix, ip = dict(rx.internal), dict(rp.internal)
    ex = {a: (si, d) for si, a, d in rx.external}; ep = {a: (si, d) for si, a, d in rp.external}
    fx = SC.elements(x['data'], rx, 'be').get('funcs', []); fp = SC.elements(p['data'], rp, 'le').get('funcs', [])
    if len(fx) != len(fp): kinds['call sites: function counts differ (script skipped)'] += 1; return
    for (ax, _, _), (ap, _, _) in zip(fx, fp):
        cx, cp = ix.get(ax + 0x18), ip.get(ap + 0x18)
        if cx is None or cp is None: continue
        nx, np_ = struct.unpack_from('>I', x['data'], cx - 4)[0], struct.unpack_from('<I', p['data'], cp - 4)[0]
        if nx != np_: kinds['call sites: code lengths differ (function skipped)'] += 1; continue
        for j in range(nx):
            a, b = ex.get(cx + 4 * j), ep.get(cp + 4 * j)
            if a is None or b is None: continue
            xn = tnames(xsecs, a[0], 'be').get(a[1]); pn = tnames(psecs, b[0], 'le').get(b[1])
            if xn is None or pn is None: continue
            if xn in symmap: kinds['learned map %s (calls)' % ('agrees' if symmap[xn] == pn else 'DISAGREES')] += 1; continue
            votes[xn][pn] += CALL_WEIGHT; kinds['call sites'] += 1


def main(argv):
    names = argv or ['generalbank.drm']
    ids = DG.DlcIds(); symmap = ids.base.get(DG.SYM, {})
    cal = json.load(open(DG.DlcIds.SYM_CALIBRATION)); cal = {int(a): b for a, b in cal.get('symbols', cal).items()}
    votes = collections.defaultdict(collections.Counter); scripts = 0; kinds = collections.Counter()
    for name in names:
        xs = C.find(C.BASE[1:], 'be', 'xenon-w' + BS + name); ps = C.find(C.PC, 'le', 'pc-w' + BS + name)
        if not xs or not ps: print('%s: missing on %s' % (name, 'Xbox' if not xs else 'PC')); continue
        pc = {s['id']: s for s in ps if s['type'] == 8 and s['data']}; tcache = {}
        for x in xs:
            if x['type'] != 8 or not x['data']: continue
            p = pc.get(ids(8, x['id']))
            if p is None: continue
            try:
                fv = collections.defaultdict(collections.Counter)
                SC.offset_map(x['data'], R.parse(x['reloc'], 'be'), p['data'], R.parse(p['reloc'], 'le'), symmap, fv)
                for a, c in fv.items(): votes[a].update(c); kinds['functions/prototypes'] += sum(c.values())
                member_votes(x, p, symmap, votes, kinds)
                call_votes(x, p, xs, ps, symmap, votes, kinds, tcache)
                scripts += 1
            except Exception as e:
                print('%s script %d: offset map failed: %s' % (name, x['id'], e))
    best = {}; rows = collections.Counter(); conv = collections.Counter(); bad = []
    # injective, strongest evidence first: a PC Symbol taken by the learned map or by a stronger vote is not given
    # to a second Xbox Symbol (call sites outweigh positional pairs of look-alike functions)
    taken = set(symmap.values())
    order = sorted((xs for xs in votes if xs not in symmap), key=lambda xs: (-votes[xs].most_common(1)[0][1], xs))
    for xsym in order:
        c = votes[xsym]
        pick = next(((ps, n) for ps, n in c.most_common() if ps not in taken), None)
        if pick is None: kinds['dropped: every candidate PC Symbol already taken'] += 1; continue
        psym, n = pick; best[xsym] = psym; taken.add(psym)
        if len(c) > 1: kinds['symbols with conflicting votes'] += 1
        if psym != c.most_common(1)[0][0]: kinds['took a weaker candidate (top one taken)'] += 1
        conv['converter (DlcIds.sym) right' if ids.sym(xsym) == psym else 'converter (DlcIds.sym) WRONG'] += 1
        if xsym not in cal: rows['no calibration entry'] += 1
        elif cal[xsym] == psym: rows['calibration agrees'] += 1
        else: rows['calibration DISAGREES'] += 1; bad.append((xsym, cal[xsym], psym, n, len(c)))
    print('%d scripts paired in %s; %d Xbox name Symbols outside the learned map with base evidence' % (
        scripts, ', '.join(names), len(best)))
    for k, n in sorted(rows.items()) + sorted(conv.items()): print('  %-32s %d' % (k, n))
    print('  converter rule used for them: %s' % dict(ids.sym_stats))
    print('  votes by kind: %s' % dict(kinds))
    for xsym, c, p, n, k in bad:
        print('  xbox %d: calibration %d, base %d (%d votes%s)' % (xsym, c, p, n, '' if k == 1 else ', %d candidates' % k))
    merged = {a: b for a, b in cal.items() if a not in best and b not in taken}
    dropped = sum(1 for a, b in cal.items() if a not in best and b in taken)
    merged.update(best)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({'symbols': {str(k): v for k, v in sorted(merged.items())}}, open(OUT, 'w'), indent=0)
    print('-> %s (%d entries: %d from base evidence, calibration without the %d entries whose PC Symbol base evidence '
          'took)' % (os.path.normpath(OUT), len(merged), len(best), dropped))


if __name__ == '__main__':
    main(sys.argv[1:])
