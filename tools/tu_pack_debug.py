"""Test 50o (03.11.): why does a tu_batch group fail at `pack_lib` ("packed slot N invalid")? Rebuilds the group exactly as
`tu_batch.py run` does (build_group with the first file's records / MaterialParams, all checks), then per slot: the
abs-constant fold (TLT.fix_abs_consts) and the validity check (f4_lint + D3DX9) before and after the fold, with the
error text and the instructions the fold changed. Read-only except the scratch WORKDIR.

Usage (from the repository root):
  TRUDLC_GAME_MODS=... ../bin/pyt -t 1800 tools/tu_pack_debug.py INV.json XLIB WORKDIR
"""
import sys, os, json, struct
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import tu_batch as TB
import tu_light_transplant as TLT
from tu_light_transplant import sm3asm
import fade_slots_translate as FST


def main(a):
    if len(a) < 3: sys.exit(__doc__)
    inv = json.load(open(a[0])); xlib = int(a[1]); wd = a[2]; os.makedirs(wd, exist_ok=True)
    rows = [r for r in inv if r['xlib'] == xlib]
    if not rows: sys.exit('xlib %d not in the inventory' % xlib)
    r0 = rows[0]; f0 = r0['files'][0]
    _, Pd = TLT.load(f0['pc'], 'le'); _, Xd = TLT.load(f0['xbox'], 'be')
    rr = TB.recs_of(Pd, Xd, r0['mat'], f0['xmat'])
    if rr is None: sys.exit('records do not pair')
    smap, dxn = rr
    XP = TLT.mparams(Xd[(10, f0['xmat'])], 'be')
    lg = []
    res = TB.build_group(xlib, r0['surrogate'], smap, dxn, XP, r0['lit'], os.path.join(wd, 'b'), lg)
    for l in lg: print('build:', l)
    for k in sorted(res):
        bc0 = res[k]
        ok0, _, err0 = FST.valid(bc0)
        bc, nf = TLT.fix_abs_consts(bc0)
        ok1, txt1, err1 = FST.valid(bc)
        print('slot %d: before fold valid %s %s | fold %d operands | after fold valid %s %s' % (k, ok0, '' if ok0 else err0, nf, ok1, '' if ok1 else err1))
        if nf:
            A = [sm3asm.fmt_instr(i, 'ps') for i in sm3asm.decode(bc0).instrs()]
            B = [sm3asm.fmt_instr(i, 'ps') for i in sm3asm.decode(bc).instrs()]
            sa = set(A)
            for l in B:
                if l not in sa: print('   new / changed:', l)
        if not ok1: open(os.path.join(wd, 'slot%d_after_fold.txt' % k), 'w').write(txt1 + '\n' + str(err1))


if __name__ == '__main__':
    main(sys.argv[1:])
