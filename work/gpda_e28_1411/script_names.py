"""E2-8 one-off (read-only): which g_pda scripts carry the Symbols of the shifted 3347 tag-59 members (Xbox userTypes
5425 / 5427 / 5429, PC userTypes 4969 / 4971 / 4973 / 4975 / 4918) as their script name (root +0x08, two u16) - tag 59
members reference a script class by name, so the script id pairing (DlcIds id map) is the referee for the userType.
usage: ../bin/pyt -t 600 work/gpda_e28_1411/script_names.py
"""
import sys, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.realpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
import gpda_port as G

XW = {5424, 5425, 5426, 5427, 5428, 5429, 5430, 5431}
PW = {4965, 4967, 4969, 4970, 4971, 4972, 4973, 4974, 4975, 4976, 4918, 4977}


def names(S, e):
    E = '>' if e == 'be' else '<'
    out = {}
    for s in S:
        if s['type'] != 8 or not s['data'] or len(s['data']) < 0x0c: continue
        out[s['id']] = struct.unpack_from(E + 'HH', s['data'], 0x08)
    return out


def main():
    I = G.ids()
    xn = names(G.read_xbase(), 'be'); pn = names(G.read_pc(), 'le'); kn = names(G.read_pack(), 'be')
    print('Xbox base g_pda scripts named with a watched Symbol:')
    for sid, (a, b) in sorted(xn.items()):
        if a in XW or b in XW:
            pid = I(8, sid)
            print('   Xbox %5d name (%d, %d) -> PC id %d, PC name %s; DlcIds.sym(name) %s' % (sid, a, b, pid, pn.get(pid), (I.sym(a), I.sym(b))))
    print('pack11 g_pda scripts named with a watched Symbol:')
    for sid, (a, b) in sorted(kn.items()):
        if a in XW or b in XW: print('   pack %5d name (%d, %d) -> PC id %d' % (sid, a, b, I(8, sid)))
    print('PC g_pda scripts named with a watched Symbol:')
    for sid, (a, b) in sorted(pn.items()):
        if a in PW or b in PW: print('   PC %5d name (%d, %d)' % (sid, a, b))


if __name__ == '__main__':
    main()
