"""Does the PC game already carry the title-update (TU) picture of each texture the TU changed in a base-game DRM?
(read-only; docs: TU coverage audit)

Test 43 showed that texture 76 differs between Xbox retail and TU, yet the converted TU picture is byte-identical to
Crystal's PC texture - the PC was built after that change. This tool repeats that check for every changed or new TU
texture: the TU and the retail section are converted with tex_convert.convert (Xbox Xenos tiled -> PCD9) and
compared with the PC section of the same id (original PC game, or --pc FILE.drm).

Result per texture: "PC = TU" (nothing to port), "PC = retail" (the TU picture is missing on PC), "PC own" (neither
matches byte for byte, e.g. another size or format), "missing on PC" (new TU texture), or "convert failed".

Usage (from the repository root):
  ../bin/pyt -t 900 tools/tu_texture_state.py [NAME] [--pc FILE.drm]
  NAME default generalbank.drm
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_idrefs as IR
import tex_convert as T


def main(argv):
    pcfile = None
    if '--pc' in argv: k = argv.index('--pc'); pcfile = argv[k + 1]; del argv[k:k + 2]
    name = argv[0] if argv else 'generalbank.drm'
    tu = {i: bytes(d) for t, i, d, _ in IR.load('tu:' + name)[0] if t == 5 and d}
    rt = {i: bytes(d) for t, i, d, _ in IR.load('retail:' + name)[0] if t == 5 and d}
    if pcfile:
        pc = {i: bytes(d) for t, i, d, _ in IR.load(pcfile)[0] if t == 5 and d}
    else:
        import dtp_word_classes as C
        pc = {s['id']: bytes(s['data']) for s in C.find(C.PC, 'le', 'pc-w' + chr(92) + name) if s['type'] == 5 and s['data']}
    tally = collections.Counter()
    for i in sorted(tu):
        if rt.get(i) == tu[i]: continue
        p = pc.get(i)
        if p is None:
            state = 'missing on PC'
        else:
            try:
                ct = T.convert(tu[i])
                cr = T.convert(rt[i]) if i in rt else None
                state = 'PC = TU' if ct == p else 'PC = retail' if cr == p else 'PC own'
                if state == 'PC own': state += ' (PC %d B, converted TU %d B)' % (len(p), len(ct))
            except Exception as e:
                state = 'convert failed: %s' % str(e)[:60]
        tally[state.split(' (')[0].split(':')[0]] += 1
        print('texture %5d  %-8s %s' % (i, 'new' if i not in rt else 'changed', state))
    print('summary:', dict(tally))


if __name__ == '__main__':
    main(sys.argv[1:])
