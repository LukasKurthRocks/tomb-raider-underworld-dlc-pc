"""Group L 12.11. (read-only): which script functions of a PC DRM call function FUNC of the native script type with
package PKG and name NAME (e.g. game/script/ui / ui, function 31 = tru.exe binder 0x7ad9d0 index 0x1f = 0x79e5d0 ->
0x77a7d0, the setter of the strike circle radius [0xfae8d0]). For every external relocation of a script section that
points at that function entry and is the operand word of a call instruction (opcode 0x65..0x71), the caller's function
index and the 8 code words before the call (with op02 float literals) are printed.
Usage (from trudlcport): ../bin/pyt work/l_combat_1211/native_callers.py DRM PKG NAME FUNC
  PKG = id, NAME = script id: any script (also one without a native type) by its section id."""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_reloc as R
import script_func_list as FL
import menu_dlc_probe as P
import script_dis as SD
import script_conv as SC


def main(a):
    src, pkg, name, func = a[0], a[1], a[2], int(a[3])
    S, e = FL.sections(src)
    E = '>' if e == 'be' else '<'
    tgt = None
    for k, q in enumerate(S):
        if q[0] != 8 or not q[2]:
            continue
        info = P.script_info({'data': q[2], 'reloc': q[3]}, e)
        if (info[0] == pkg and info[1] == name) or (pkg == 'id' and str(q[1]) == name):
            tgt = k
    if tgt is None:
        print('no script %s / %s in %s' % (pkg, name, src))
        return 1
    ents = SD.func_entries(S[tgt][2], S[tgt][3], e)
    want = [o for o, i in ents.items() if i == func]
    print('type %s / %s = script id %d (section %d), %d functions, f%d entry %s' % (
        pkg, name, S[tgt][1], tgt, len(ents), func, ['0x%x' % o for o in want]))
    if not want:
        return 1
    hits = 0
    for k, q in enumerate(S):
        if q[0] != 8 or not q[2] or not q[3]:
            continue
        d, rel = q[2], R.parse(q[3], e)
        refs = [so for si, so, do in rel.external if si == tgt and do == want[0]]
        if not refs:
            continue
        own = SD.func_entries(d, q[3], e)
        it = dict(rel.internal)
        W = SC.Walk(d, rel, e).run()
        # code ranges per function: code pointer at entry +0x18, word count before it
        ranges = []
        for fo, fi in own.items():
            ct = it.get(fo + 0x18)
            if ct is None:
                continue
            cn = struct.unpack_from(E + 'I', d, ct - 4)[0]
            ranges.append((ct, ct + 4 * cn, fi))
        for so in refs:
            w = struct.unpack_from(E + 'I', d, so - 4)[0]
            op = w >> 24
            fn = next((r for r in ranges if r[0] <= so < r[1]), None)
            if not (0x65 <= op <= 0x71) or fn is None:
                continue
            hits += 1
            print('\nscript id %d (%s) f%d: call op%02x at +0x%x' % (q[1], P.script_info({'data': d, 'reloc': q[3]}, e)[:2],
                                                                   fn[2], op, so - 4))
            o = max(fn[0], so - 4 - 4 * 10)
            while o <= so:
                ww = struct.unpack_from(E + 'I', d, o)[0]
                txt = 'op%02x %d' % (ww >> 24, (ww & 0xffffff) - (0x1000000 if ww & 0x800000 else 0))
                if o - 4 >= fn[0] and (struct.unpack_from(E + 'I', d, o - 4)[0] >> 24) == P.PUSHF:
                    txt = 'literal f32 %g / u32 0x%x' % (struct.unpack(E + 'f', struct.pack(E + 'I', ww))[0], ww)
                print('  +0x%05x  %08x  %s' % (o, ww, txt))
                o += 4
    print('\n%d call(s)' % hits)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
