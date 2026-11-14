"""E2-8 one-off (read-only): the three g_pda 3347 member twins whose PC partner changed between knowledge G20261111-3
(2026-11-11 09:42, before the Q58 Symbol twins) and the re-learned knowledge (2026-11-14): pack entries 27640 / 27660 /
27680. Prints the pack entries, their Xbox base twins, the PC candidates and the align score of each pair with the
current DlcIds (Symbol twins on) - and, for comparison, the userType / name the old map gave (TRUDLC_SYM_TWINS=off run).
usage: ../bin/pyt -t 600 work/gpda_e28_1411/twin_shift.py [PACK_OFFSETS...]
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.realpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
import gpda_port as G
import script_member_pairs as MP


def main(argv):
    want = [int(x) for x in argv] or [27620, 27640, 27660, 27680, 27700]
    I = G.ids()
    pk = {(s['type'], s['id']): s for s in G.read_pack()}
    xb = {(s['type'], s['id']): s for s in G.read_xbase()}
    pc = {(s['type'], s['id']): s for s in G.read_pc()}
    inv = {(t, I(t, x)): (t, x) for (t, x) in pk}
    xk = inv[(8, 3347)]
    P, X, C = pk[xk], xb[xk], pc[(8, 3347)]
    m1, _ = MP.same_space(P['data'], P['reloc'], X['data'], X['reloc'])
    m2, _ = MP.align(X['data'], X['reloc'], C['data'], C['reloc'], I)
    Wp, ep = MP.entries(P['data'], P['reloc'], 'be')
    Wx, ex = MP.entries(X['data'], X['reloc'], 'be')
    Wc, ec = MP.entries(C['data'], C['reloc'], 'le')
    byp = {q['a']: (k, q) for k, l in ep.items() for q in l}
    byx = {q['a']: (k, q) for k, l in ex.items() for q in l}
    byc = {q['a']: (k, q) for k, l in ec.items() for q in l}
    print('twins env TRUDLC_SYM_TWINS=%s' % os.environ.get('TRUDLC_SYM_TWINS'))
    for a in want:
        k, q = byp[a]
        xa = m1.get(a); ca = m2.get(xa) if xa is not None else None
        print('pack +%d %s #%d tag %d ut %d (sym %s) name %d (sym %s, exact %s) init %s' % (
            a, k, q['k'], q['tag'], q['ut'], I.sym(q['ut']), q['name'], I.sym(q['name']),
            I.base.get(__import__('dlc_generic').SYM, {}).get(q['name']), q['init'] is not None))
        print('    Xbox base twin +%s -> PC +%s' % (xa, ca))
    kind = byp[want[0]][0]
    xl = MP._prep(Wx, X['data'], ex[kind], True, I, None)
    pl = MP._prep(Wc, C['data'], ec[kind], False, I, None)
    xi = {q['a']: q for q in xl}
    lo = min(m2.get(m1.get(a), 10 ** 9) for a in want if m1.get(a) is not None) - 60
    hi = max(m2.get(m1.get(a), 0) for a in want if m1.get(a) is not None) + 60
    cands = [p for p in pl if lo <= p['a'] <= hi]
    print('PC %s entries +%d..+%d:' % (kind, lo, hi))
    for p in cands:
        print('    PC +%d #%d tag %d ut %d name %d init %s' % (p['a'], p['k'], p['tag'], p['ut'], p['name'], p['paths'] is not None))
    print('scores (Xbox base twin x PC candidate):')
    for a in want:
        xa = m1.get(a)
        if xa is None or xa not in xi: continue
        x = xi[xa]
        print('    pack +%d (Xbox +%d, put %s): %s' % (a, xa, x['put'], ['+%d:%s' % (p['a'], MP.score(x, p)) for p in cands]))


if __name__ == '__main__':
    main(sys.argv[1:])
