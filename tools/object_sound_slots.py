"""Fixed sound slots of an object (read-only; F5 groan loop 2026-11-05, TruTrace 'sound 20212' = a slot of the player).

Engine (PC tru.exe 6905b046):
  instance sound object tru+0x18d6a0 (built at tru+0x19443f, stored in [inst+0x248]): +0 instance, +4 slot count =
    [object +0xa8], +8 slot table = [object +0xac] (8 bytes per slot: {ptr SoundPlex node, s16 default parameter,
    s16}), +0xc 12-byte handles. The object is [inst+0x10] = the object's main DTP (doppelganger_casual: DTP 20212).
  play / stop a slot: tru+0x193d50(slot, mode, p3, p4) (thiscall on [inst+0x248]): mode 1 releases the old handle and
    starts the node through tru+0x193c90 (return 0x593cac, caller 0x593dec = what TruTrace 0.2 logs as 'wrapper');
    p4 != 0xff replaces the s16 default; the s16 p3 goes to emitter +0x44. Started only by anim event kind 2, record
    type 0x60 (tru+0x1b69c0 case 0x5b69f4: payload {s16 0x60, u8 +2 != 0xff, u8 +3, s8 slot +4, s8 mode +5}).
  The emitter id TruTrace prints (emitter +0xc = [node +8]) is the id of the section that holds the node, so every
  slot of the object shows up as 'sound <object DTP id>'.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/object_sound_slots.py XBOX.drm PC.drm DTP_ID
        both files: slot count / table offset, per slot the default parameter (Xbox s16 / PC s16), the SoundPlex tree
        (node types, wave ids, LOOP for looping waves); Sequence repeat bytes: tools/soundplex_sequence_fix.py
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anim_sound_loops as A


def slots(pl, k, f):
    d = pl.secs[k]['data']; it = dict(pl.r(k).internal)
    n = struct.unpack_from(f + 'I', d, 0xa8)[0]; tab = it.get(0xac)
    out = []
    if tab is None: return n, None, out
    for i in range(n):
        node = it.get(tab + 8 * i)
        par = struct.unpack_from(f + 'h', d, tab + 8 * i + 4)[0]
        out.append((i, node, par))
    return n, tab, out


def main(a):
    if len(a) < 3: sys.exit(__doc__)
    xs = A.load(a[0], 'be'); ps = A.load(a[1], 'le'); sid = int(a[2])
    X = A.Plex(xs, 'be'); P = A.Plex(ps, 'le')
    xk = X.by_id[7, sid][0]; pk = P.by_id[7, sid][0]
    xn, xt, xsl = slots(X, xk, '>'); pn, pt, psl = slots(P, pk, '<')
    print('DTP %d: slot count Xbox %d PC %d, table Xbox +%s PC +%s' % (sid, xn, pn, hex(xt) if xt is not None else '-',
                                                                       hex(pt) if pt is not None else '-'))
    fmt = lambda tr: ' '.join('%s%s%s' % ('.' * dd, A.NODE.get(t, t), '' if ex is None else '(%s)' % (
        ('w%d%s' % (ex[0], ' LOOP' if ex[1] else '')) if t == 2 else ex)) for dd, t, _, ex in tr)
    for (i, xnode, xpar), (_, pnode, ppar) in zip(xsl, psl):
        print('slot %2d: node Xbox +%s PC +%s, default parameter Xbox %d PC %d %s' % (
            i, hex(xnode) if xnode is not None else '-', hex(pnode) if pnode is not None else '-', xpar, ppar,
            '' if xpar == ppar else 'DIFF'))
        if xnode is not None:
            print('    X : %s' % fmt(X.tree(xk, xnode)))
        if pnode is not None:
            print('    PC: %s' % fmt(P.tree(pk, pnode)))


if __name__ == '__main__':
    main(sys.argv[1:])
