"""Which native script types did the Xbox title update (TU) extend, does the PC generalbank have those natives, and
which TU scripts call them? (read-only; docs: TU coverage audit)

A native script (package + native name, e.g. game/game larabase) is a function table the exe fills in. The TU adds
entries at the end (e.g. larabase f70-f73, achievement f16-f20). The PC exe only implements what the PC table lists,
so a TU script that calls one of the new entries needs a PC native (or a stub) before it can run on PC.

Per native script: function count Xbox retail / TU / PC (matched by package + native name, since PC ids differ),
then for every new TU entry the TU scripts that refer to it (relocation into that function entry).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/tu_native_coverage.py [--pc FILE.drm]
  --pc: a PC (little-endian) generalbank to compare with instead of the original PC game (e.g. our built one)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import dtp_word_classes as C
import menu_dlc_probe as P

BS = chr(92)
NAME = 'generalbank.drm'


def funcs(d, rl, e):
    """(table offset, count, entry size) of the function table, or None"""
    import script_conv as SC
    W = SC.Walk(d, R.parse(rl, e), e).run()
    return next(((t, n, sz) for name, t, n, sz in W.arrays if name == 'funcs'), None)


def natives(secs, e):
    """{(package, native): (id, data, reloc)} for every native script"""
    out = {}
    for s in secs:
        if s['type'] == 8 and s['data']:
            pkg, nat, _ = P.script_info(s, e)
            if nat: out[(pkg, nat)] = (s['id'], s['data'], s['reloc'])
    return out


def main(argv):
    pcfile = None
    if '--pc' in argv: k = argv.index('--pc'); pcfile = argv[k + 1]; del argv[k:k + 2]
    tu = C.find([C.BASE[0]], 'be', 'xenon-w' + BS + NAME)
    rt = C.find(C.BASE[1:], 'be', 'xenon-w' + BS + NAME)
    if pcfile:
        import drm_write as DW
        D = DW.read(open(pcfile, 'rb').read(), 'le')
        pc = [{'type': s.type, 'id': s.id, 'data': s.data, 'reloc': s.reloc} for s in D.sections]
    else:
        pc = C.find(C.PC, 'le', 'pc-w' + BS + NAME)
    ntu, nrt, npc = natives(tu, 'be'), natives(rt, 'be'), natives(pc, 'le')
    print('native scripts: TU %d, retail %d, PC %d (%s)' % (len(ntu), len(nrt), len(npc), pcfile or 'original PC game'))
    for key in sorted(ntu):
        tid, td, tr = ntu[key]
        ft = funcs(td, tr, 'be')
        fr = funcs(*nrt[key][1:], 'be') if key in nrt else None
        fp = funcs(*npc[key][1:], 'le') if key in npc else None
        n_t, n_r = ft[1] if ft else 0, fr[1] if fr else 0
        if n_t == n_r: continue
        print('%s/%s: Xbox id %d, functions retail %d, TU %d, PC %s (PC id %s)' % (
            key[0], key[1], tid, n_r, n_t, fp[1] if fp else '-', npc[key][0] if key in npc else '-'))
        t, _, sz = ft
        callers = {}
        for s in tu:
            if s['type'] != 8 or not s['data'] or s['id'] == tid: continue
            rel = R.parse(s['reloc'], 'be')
            for si, so, do in rel.external:
                q = tu[si] if si < len(tu) else None
                if q and q['type'] == 8 and q['id'] == tid and do >= t + n_r * sz and do < t + n_t * sz:
                    callers.setdefault((do - t) // sz, set()).add(s['id'])
        for k in range(n_r, n_t):
            print('    f%-3d called by TU scripts %s' % (k, sorted(callers.get(k, ())) or 'none'))


if __name__ == '__main__':
    main(sys.argv[1:])
