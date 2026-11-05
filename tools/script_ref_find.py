"""Find every external relocation into one script section at given offsets (or an offset range), read-only: which
section of which DRM points at a function / prototype / member of script ID. Written for the night 04.11. scan
(workspace docs Befund-Thrall-Absturz.md section 11): who calls the PC-only vtable slot 31 of script 93 (uiscreen,
function f111 / prototype 111) - DLC UI classes compiled against the Xbox 93 (31 slots) put their own first virtual
function into that slot.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/script_ref_find.py ID OFF[,OFF...]|LO-HI SOURCE [SOURCE ...]
  SOURCE = a PC DRM file, a folder (every *.drm below it), or pc:NAME.drm / xbox:NAME.drm (script_func_list.sections)
  offsets hex (0x...) or decimal
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL


def targets(spec):
    if '-' in spec:
        lo, hi = spec.split('-')
        return lambda o, lo=int(lo, 0), hi=int(hi, 0): lo <= o < hi
    s = {int(x, 0) for x in spec.split(',')}
    return lambda o: o in s


def scan(src, sid, hit, st):
    S, e = FL.sections(src)
    for q in S:
        if not q[3]: continue
        rel = R.parse(q[3], e)
        for si, so, do in rel.external:
            if si < len(S) and S[si][0] == 8 and S[si][1] == sid:
                st['relocations into %d' % sid] += 1
                if hit(do):
                    st['HIT'] += 1
                    print('%s: section %d:%d +0x%x -> script %d +0x%x' % (src, q[0], q[1], so, sid, do))


def main(argv):
    sid = int(argv[0]); hit = targets(argv[1]); st = collections.Counter()
    for a in argv[2:]:
        if os.path.isdir(a):
            for dp, dn, fn in os.walk(a):
                for f in sorted(fn):
                    if f.lower().endswith('.drm'): scan(os.path.join(dp, f), sid, hit, st)
        else: scan(a, sid, hit, st)
    print('summary: %s' % dict(st))


if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    main(sys.argv[1:])
