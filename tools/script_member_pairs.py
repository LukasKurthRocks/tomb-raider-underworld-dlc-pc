"""Xbox <-> PC twins of script DataMembers, arguments and locals - by their place in the declaration order, not by the
converter's guessed name (Q55, 2026-11-11; docs Befund-Member-Paarung-Q55-1111.md in the workspace docs folder).

Why: the name Symbol of a member (entry +14) is a cdc::Symbol id. Where the base map has no entry the converter
guesses it (dlc_generic.DlcIds.sym: interpolation / 'guess_lower'), and the guess names the NEIGHBOUR entry wherever the
PC inserted, dropped or renamed members (g_pda 3347 +1, 3360 -1 / -3, 3365 +3, 3367 +4, 3368 +8, 3384 +2 / -1; Q48).
Pairing "the PC member with the same (guessed) name" therefore copied neighbour values (gpda_port, Q10) and taught
ui_init_fix / gpda_port rules from wrong pairs (PC prompt ids 129 -> 139, 131 -> 150 say other texts).
Measured on the 283 base script pairs of generalbank + g_pda (Xbox base <-> PC base; text id leaves ut 223 [0, 0] /
ut 301 [0, 92] as the referee, NOT part of the score): same-name pairing 207 right / 181 wrong, same index 455 / 132,
this alignment 623 / 7 (6 = PC re-authored texts in script 72, same index in an identical array shape, wrong for every
method; 1 = a PC-inserted list entry with an identical init, generalbank 7); with the text leaves in the score 624 / 6.
The callers (gpda_port, ui_init_fix) pass no locals map: the text leaves stay the independent referee of the rules
they learn.

Rule (align): per kind (members; all argument arrays in walk order; all local arrays in walk order) a monotonic
alignment (dynamic programming, gaps free) of the Xbox and PC entries maximising the summed score of the matched
pairs. A match needs the same type tag and an Xbox name that the PC can have (a TU / DLC-new Symbol above the Xbox
base map without a map entry has no PC twin). Score = 1 + userType equal (Xbox through DlcIds.sym) + 2 x name equal
where the Xbox name has an entry in the learned base map (never a guess, never the B138 calibration) + 2 x the share of equal init
words (Xbox word byte-swapped = PC word; same init tree shape; text id leaves excluded) + 2 x text id leaves equal
through the locals map (optional, locmap given) - 0.5 when only one side has an init block.
Same-space pairing (same_space): two Xbox versions of one script (pack11 vs Xbox base, both Xbox Symbols): the
longest common subsequence of (kind, name, tag, userType) in walk order.
chain(pack, xbase, pc): pack entry -> Xbox base entry (same_space) -> PC entry (align); pack entries without an Xbox
base twin are DLC-only.

  entries(d, rl, e)                          -> (walk, {kind: [entry]})  entry: a, i, k, tag, ut, off, name, init
  align(xd, xrl, pd, prl, ids, locmap=None)  -> ({Xbox entry offset: PC entry offset}, Counter)
  same_space(ad, arl, bd, brl)               -> ({a entry offset: b entry offset}, Counter)
  chain(pk, pkrl, xd, xrl, pd, prl, ids, locmap=None) -> ({pack entry offset: PC entry offset}, Counter)
Read-only helpers, no game bytes written. Usage as a module (gpda_port.py learn / build knowledge, ui_init_fix.py learn).
"""
import os, sys, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_reloc as R, script_conv as SC
import script_init_from_pc as SIP

KINDS = ('members', 'args', 'locals')
TEXT_LEAVES = {(223, (0, 0)), (301, (0, 92))}       # (PC userType, init path) of the locals string id leaves (Q46 / Q48)


def entries(d, rl, e, W=None):
    """(walk, {kind: [entry dict]}) of the 20-byte member / argument / local entries in walk order"""
    if W is None: W = SC.Walk(d, R.parse(rl, e), e).run()
    E = '>' if e == 'be' else '<'
    out = collections.OrderedDict((k, []) for k in KINDS)
    for i, (nm, t, n, sz) in enumerate(W.arrays):
        if nm not in KINDS or sz != 20: continue
        for k in range(n):
            a = t + 20 * k
            tag, ut = struct.unpack_from(E + 'IH', d, a)
            off, name = struct.unpack_from(E + 'HH', d, a + 12)
            out[nm].append(dict(a=a, i=i, k=k, tag=tag, ut=ut, off=off, name=name, init=W.it.get(a + 16)))
    return W, out


def _prep(W, d, lst, be, ids, locmap):
    from dlc_generic import SYM
    sm = ids.base.get(SYM, {})
    out = []
    for e in lst:
        q = dict(e)
        q['put'] = ids.sym(e['ut']) if be else e['ut']
        if be:
            # exact = the learned base map only: the B138 calibration entries (DlcIds.sym_extra) differ from the aligned
            # PC name in 234 of 234 aligned base entries (members 211, args 22, locals 1; base map: 2420 = / 5 !=,
            # measured Q55) - they are a kit's choice, not the PC's names
            q['exact'] = sm.get(e['name'])
            q['new'] = q['exact'] is None and e['name'] > ids.xs_max
        else:
            q['exact'] = None; q['new'] = False
        paths, words, texts = [], [], []
        if e['init'] is not None:
            for p, o in SIP.leaves(W, W.it, e['init']):
                w = bytes(d[o:o + 4])
                paths.append(p)
                if (q['put'], p) in TEXT_LEAVES:
                    words.append(None)
                    if be:
                        hi, lo = struct.unpack('>HH', w)
                        texts.append(None if (lo or hi in (0, 0xffff) or locmap is None or hi not in locmap)
                                     else struct.pack('<I', locmap[hi]))
                    else:
                        texts.append(w)
                else:
                    words.append(w[::-1] if be else w); texts.append(None)
        q['paths'] = tuple(paths) if e['init'] is not None else None
        q['words'] = words; q['texts'] = texts
        out.append(q)
    return out


def score(x, p):
    """match score of Xbox entry x and PC entry p (prepared), None = no match possible"""
    if x['tag'] != p['tag'] or x['new']: return None
    s = 1.0
    if x['put'] == p['put']: s += 1
    if x['exact'] is not None and x['exact'] == p['name']: s += 2
    if x['paths'] is not None and p['paths'] is not None:
        if x['paths'] == p['paths']:
            n = sum(1 for a in x['words'] if a is not None)
            if n: s += 2.0 * sum(1 for a, b in zip(x['words'], p['words']) if a is not None and a == b) / n
            tx = [(a, b) for a, b in zip(x['texts'], p['texts']) if a is not None]
            if tx: s += 2.0 * sum(1 for a, b in tx if a == b) / len(tx)
    elif (x['paths'] is None) != (p['paths'] is None):
        s -= 0.5
    return s


def _dp(xl, pl, sc):
    """monotonic alignment maximising the summed score (gaps free) -> {x index: p index}"""
    n, m = len(xl), len(pl)
    if not n or not m: return {}
    prev = [0.0] * (m + 1)
    back = []
    for a in range(1, n + 1):
        cur = [0.0] * (m + 1); bk = bytearray(m + 1)
        xa = xl[a - 1]
        for b in range(1, m + 1):
            best = prev[b]; t = 1
            if cur[b - 1] > best: best = cur[b - 1]; t = 2
            s = sc(xa, pl[b - 1])
            if s is not None and prev[b - 1] + s > best: best = prev[b - 1] + s; t = 3
            cur[b] = best; bk[b] = t
        back.append(bk); prev = cur
    res = {}
    a, b = n, m
    while a > 0 and b > 0:
        t = back[a - 1][b]
        if t == 3: res[a - 1] = b - 1; a -= 1; b -= 1
        elif t == 1: a -= 1
        else: b -= 1
    return res


def align(xd, xrl, pd, prl, ids, locmap=None, Wx=None, Wp=None):
    """Xbox section (big-endian) <-> PC section (little-endian) of one script: {Xbox entry offset: PC entry offset}"""
    Wx, ex = entries(xd, xrl, 'be', Wx); Wp, ep = entries(pd, prl, 'le', Wp)
    out, st = {}, collections.Counter()
    for kind in KINDS:
        xl = _prep(Wx, xd, ex[kind], True, ids, locmap); pl = _prep(Wp, pd, ep[kind], False, ids, locmap)
        r = _dp(xl, pl, score)
        st['%s: Xbox entries' % kind] += len(xl); st['%s: paired' % kind] += len(r)
        st['%s: Xbox entries with a TU / DLC-new name (no PC twin)' % kind] += sum(1 for q in xl if q['new'])
        for a, b in r.items():
            out[xl[a]['a']] = pl[b]['a']
            if xl[a]['i'] == pl[b]['i'] and xl[a]['k'] == pl[b]['k']: st['%s: paired at the same index' % kind] += 1
            if ids.sym(xl[a]['name']) == pl[b]['name']: st['%s: paired, PC name = DlcIds.sym(Xbox name)' % kind] += 1
            if xl[a]['exact'] is not None:
                st['%s: paired, exact map entry %s PC name' % (kind, '=' if xl[a]['exact'] == pl[b]['name'] else '!=')] += 1
    return out, st


def same_space(ad, arl, bd, brl):
    """two Xbox (big-endian) versions of one script: {a entry offset: b entry offset} by the longest common
    subsequence of (kind, name, tag, userType) in walk order"""
    _, ea = entries(ad, arl, 'be'); _, eb = entries(bd, brl, 'be')
    out, st = {}, collections.Counter()
    key = lambda q: (q['name'], q['tag'], q['ut'])
    for kind in KINDS:
        la, lb = ea[kind], eb[kind]
        r = _dp(la, lb, lambda x, p: 1.0 if key(x) == key(p) else None)
        st['%s: entries' % kind] += len(la); st['%s: same-space twins' % kind] += len(r)
        for a, b in r.items(): out[la[a]['a']] = lb[b]['a']
    return out, st


def chain(pk, pkrl, xd, xrl, pd, prl, ids, locmap=None):
    """pack (DLC) version -> Xbox base version -> PC version of one script: {pack entry offset: PC entry offset}"""
    m1, s1 = same_space(pk, pkrl, xd, xrl)
    m2, s2 = align(xd, xrl, pd, prl, ids, locmap)
    out = {a: m2[b] for a, b in m1.items() if b in m2}
    st = collections.Counter()
    st.update({'pack -> Xbox base ' + k: v for k, v in s1.items()})
    st.update({'Xbox base -> PC ' + k: v for k, v in s2.items()})
    st['pack entries with a PC twin'] = len(out)
    return out, st
