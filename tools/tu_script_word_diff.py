"""How much did the Xbox title update (TU) change each generalbank script, and of what kind? (read-only; docs: TU
coverage audit)

Per script that is new or differs from Xbox retail: its native package / name (script_info), sizes, and for scripts
of equal size the number of differing 32-bit words split by kind: relocation targets (pointer words, any change of
layout elsewhere), small values below 0x10000 (ids, Symbols, constants) and other words. A script whose only
differences are a few Symbol-sized values was most likely renumbered, not given new behaviour.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/tu_script_word_diff.py [NAME]      NAME default generalbank.drm
"""
import sys, os, re, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import dtp_word_classes as C
import menu_dlc_probe as P

BS = chr(92)


def main(argv):
    name = argv[0] if argv else 'generalbank.drm'
    tu = C.find([C.BASE[0]], 'be', 'xenon-w' + BS + name)
    rt = {(s['type'], s['id']): s for s in C.find(C.BASE[1:], 'be', 'xenon-w' + BS + name)}
    import dlc_generic as DG
    ids = DG.DlcIds()
    for s in tu:
        if s['type'] != 8 or not s['data']: continue
        r = rt.get((8, s['id']))
        if r is not None and r['data'] == s['data']: continue
        pkg, nat, _ = P.script_info(s, 'be')
        strs = [m.group().decode() for m in re.finditer(rb'[ -~]{8,}', s['data'])][:2]
        head = '8:%-6d PC %-6s %-24s' % (s['id'], ids(8, s['id']), ('%s' % nat) if nat else (pkg or '').split('/')[-1][:24])
        if r is None:
            print('%s new      %6d B  %s' % (head, len(s['data']), strs)); continue
        a, b = r['data'], s['data']
        if len(a) != len(b):
            print('%s grown    %6d -> %6d B  %s' % (head, len(a), len(b), strs)); continue
        ptr = set(dict(R.parse(s['reloc'], 'be').internal)) | {so for _, so, _ in R.parse(s['reloc'], 'be').external}
        n = len(a) // 4
        wa, wb = struct.unpack_from('>%dI' % n, a), struct.unpack_from('>%dI' % n, b)
        diff = [k * 4 for k in range(n) if wa[k] != wb[k]]
        kinds = {'reloc': 0, 'small': 0, 'other': 0}
        for o in diff:
            k = o // 4
            kinds['reloc' if o in ptr else 'small' if wa[k] < 0x10000 and wb[k] < 0x10000 else 'other'] += 1
        ex = ['+0x%x %x->%x' % (o, wa[o // 4], wb[o // 4]) for o in diff[:3]]
        print('%s same size %6d B, %d words differ (offsets 0x%x..0x%x) %s, e.g. %s  %s' % (
            head, len(a), len(diff), diff[0], diff[-1], kinds, ex, strs[:1]))


if __name__ == '__main__':
    main(sys.argv[1:])
