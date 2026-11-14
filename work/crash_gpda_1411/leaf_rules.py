"""Read-only: for given (script, offset) pairs of a ported / new g_pda script, the owning Xbox member (pack11), the
init leaf path (after relayout_path) and the gpda_port rule that decides the word (ui_init_fix rule / base rule /
none), plus whether the offset is in a structural array (protected).
Usage (repo root): ../bin/pyt -t 1800 work/crash_gpda_1411/leaf_rules.py BUILT_G_PDA SCRIPT_ID:OFF_HEX [...]
(the PC userType of each owner = the entry's userType in BUILT_G_PDA at the same offset)"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import gpda_port as GP
import drm_reloc as R
import script_conv as SC
import script_init_from_pc as SIP


def main(argv):
    K = GP.load_knowledge()
    I = GP.ids()
    PK = GP.read_pack(); pk = {(s['type'], s['id']): s for s in PK}
    inv = {(t, I(t, x)): (t, x) for (t, x) in pk}
    import drm_write as DW, struct
    built = {s.id: s for s in DW.read(open(argv[0], 'rb').read(), 'le').sections if s.type == 8}
    want = {}
    for a in argv[1:]:
        s, o = a.split(':'); want.setdefault(int(s), set()).add(int(o, 16))
    for sid, offs in sorted(want.items()):
        xs = pk[inv[(8, sid)]]
        xd = xs['data']; Wx = SC.Walk(xd, R.parse(xs['reloc'], 'be'), 'be').run()
        prot = GP.protected_offsets(Wx)
        mem = SIP.members(Wx, xd, 'be')
        hit = {}
        for mk, la in mem.items():
            for j, a in enumerate(la):
                ia = Wx.it.get(a + 16)
                if ia is None: continue
                for p, o in SIP.leaves(Wx, Wx.it, ia):
                    if o in offs: hit.setdefault(o, []).append((mk, j, a, p))
        for o in sorted(offs):
            print('%d +0x%x: Xbox word %s, protected %s' % (sid, o, xd[o:o + 4].hex(), o in prot))
            for mk, j, a, p in hit.get(o, []):
                tag = mk[2]
                ut = struct.unpack_from('<H', built[sid].data, a + 4)[0]      # PC userType of the converted entry
                pp = GP.relayout_path(ut, p)
                ui = K['_ui'].get((ut, tag, pp)) if pp is not None else None
                base = K['_rules'].get((ut, tag, pp)) if pp is not None else None
                fb = K['_rules'].get(GP.fallback_key(ut, tag, pp)) if pp is not None else None
                print('   owner %s %d #%d entry +0x%x ut %d tag %d path %s -> ui rule %s, base rule %s, fallback rule %s, UI_UTS %s' % (
                    mk[0], mk[1], j, a, ut, tag, list(pp) if pp is not None else None, ui, base, fb, ut in GP.UI_UTS))
            if o not in hit: print('   not an init leaf of any member / arg / local')


if __name__ == '__main__':
    main(sys.argv[1:])
