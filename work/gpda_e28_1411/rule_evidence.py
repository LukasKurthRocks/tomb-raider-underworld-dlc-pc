"""E2-8 one-off (read-only): base-game evidence for the two new init rules that changed words of the new g_pda build -
ut 301 path [0, 152, 12, 0] (id16a:100) and ut 833 path [0, 4] (raw). For every Xbox base <-> PC base script pair of
generalbank + g_pda (gpda_port.base_pairs, members paired by script_member_pairs.align as gpda_port.learn_base_rules)
the Xbox word, the PC word and whether the rule turns one into the other.
usage: ../bin/pyt -t 1800 work/gpda_e28_1411/rule_evidence.py
"""
import sys, os, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.realpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
import gpda_port as G
import ui_init_fix as U
import script_learn as L
import script_init_from_pc as SIP
import script_member_pairs as MP

WATCH = {(301, (0, 152, 12, 0)): 'id16a:100', (833, (0, 4)): 'raw'}


def main():
    I = G.ids()
    res = collections.defaultdict(collections.Counter)
    ex = collections.defaultdict(list)
    for fname, sid, xd, xrl, pd, prl in G.base_pairs():
        Wx, rx = U.walk(xd, xrl, 'be'); Wp, rp = U.walk(pd, prl, 'le')
        mx = SIP.members(Wx, xd, 'be')
        twin, _ = MP.align(xd, xrl, pd, prl, I, None, Wx=Wx, Wp=Wp)
        for (arr, nm, tag, ut), la in mx.items():
            put = I.sym(ut)
            for ma in la:
                mb = twin.get(ma)
                if mb is None or struct.unpack_from('<IH', pd, mb) != (tag, put): continue
                ia, ib = Wx.it.get(ma + 16), Wp.it.get(mb + 16)
                if ia is None or ib is None: continue
                lx = dict(SIP.leaves(Wx, Wx.it, ia)); lp = dict(SIP.leaves(Wp, Wp.it, ib))
                for (wut, path), cls in WATCH.items():
                    if put != wut or path not in lx or path not in lp: continue
                    x = bytes(xd[lx[path]:lx[path] + 4]); p = bytes(pd[lp[path]:lp[path] + 4])
                    got = L.apply_word(x, cls, I); s32 = L.apply_word(x, 's32', I)
                    k = 'rule = PC' if got == p else 'rule != PC'
                    if got == s32: k += ' (s32 gives the same)'
                    res[(wut, path)][k] += 1
                    if len(ex[(wut, path)]) < 12: ex[(wut, path)].append('%s %d %s: Xbox %s PC %s rule %s s32 %s' % (
                        fname, sid, arr, x.hex(), p.hex(), got.hex() if got else None, s32.hex() if s32 else None))
    for key, c in res.items():
        print('%s %s: %s' % (key, WATCH[key], dict(c)))
        for e in ex[key]: print('    ' + e)


if __name__ == '__main__':
    main()
