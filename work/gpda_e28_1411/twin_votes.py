"""E2-8 one-off (read-only): where the Symbol twin votes for Xbox 5425..5430 come from inside g_pda + generalbank (the
same rule as tools/symbol_twins.derive: same layout = same offset, else script_member_pairs.align with DlcIds without
twins; userTypes vote only in pairs of the same layout). Prints every Xbox base entry that carries one of the watched
Symbols as name or userType and its PC twin.
usage: ../bin/pyt -t 900 work/gpda_e28_1411/twin_votes.py
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.realpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
os.environ['TRUDLC_SYM_TWINS'] = 'off'
import drm_reloc as R
import script_member_pairs as MP
import script_func_list as FL
import dlc_generic as DG

W = set(range(5423, 5433))


def main():
    I = DG.DlcIds()
    bm8 = I.base.get(8, {})
    for fname in ('g_pda.drm', 'generalbank.drm'):
        X, _ = FL.sections('xbox:' + fname)
        P, _ = FL.sections('pc:' + fname)
        pc = {sid: (d, rl) for t, sid, d, rl in P if t == 8 and d}
        for t, x, xd, xrl in X:
            if t != 8 or not xd: continue
            _, ex = MP.entries(xd, xrl, 'be')
            hits = [(k, q) for k in MP.KINDS for q in ex[k] if q['name'] in W or q['ut'] in W]
            if not hits: continue
            pid = bm8.get(x)
            if pid not in pc: print('%s Xbox %d: no PC pair (base map %s)' % (fname, x, pid)); continue
            pd, prl = pc[pid]
            _, ep = MP.entries(pd, prl, 'le')
            pa = {q['a']: q for k in MP.KINDS for q in ep[k]}
            same = len(xd) == len(pd) and R.parse(xrl, 'be').internal == R.parse(prl, 'le').internal
            tw = {q['a']: q['a'] for k in MP.KINDS for q in ex[k] if q['a'] in pa} if same else MP.align(xd, xrl, pd, prl, I)[0]
            for k, q in hits:
                b = tw.get(q['a']); p = pa.get(b) if b is not None else None
                print('%s Xbox %d -> PC %d (%s) %s +%d tag %d ut %d name %d -> %s' % (
                    fname, x, pid, 'same layout' if same else 'aligned', k, q['a'], q['tag'], q['ut'], q['name'],
                    'PC +%d tag %d ut %d name %d' % (b, p['tag'], p['ut'], p['name']) if p else 'no twin'))


if __name__ == '__main__':
    main()
