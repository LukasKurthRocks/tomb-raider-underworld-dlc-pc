"""Every PowerPC D-form instruction with a given 16-bit immediate in a Xenia memory image (read-only; finisher analysis
2026-11-05: which code answers / asks query 0x161 - `li r4, 0x161` callers and `cmplwi rX, 0x161` / `cmpwi` handlers -
in the title update vs. retail).

Opcodes: 10 cmpli, 11 cmpi, 14 addi (li when rA = 0), 15 addis, 24 ori. With --classes the TU function of each site
(nearest function start of work/tu_funcdiff/classes.tsv at or below the site) and its diff class are shown.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/ppc_imm_sites.py IMAGE.bin IMM[,IMM..] [--classes work/tu_funcdiff/classes.tsv] [--col tu|retail]
    IMAGE: Xenia image at guest base 0x82000000; IMM hex; --col: which column of classes.tsv holds this image's
    function starts (tu for the TU image, retail for the retail image)
"""
import sys, struct, bisect

BASE = 0x82000000
NAMES = {10: 'cmplwi', 11: 'cmpwi', 14: 'addi', 15: 'addis', 24: 'ori'}


def main(argv):
    if len(argv) < 2: sys.exit(__doc__)
    cl = None
    col = 'tu'
    if '--col' in argv: k = argv.index('--col'); col = argv[k + 1]; del argv[k:k + 2]
    if '--classes' in argv:
        k = argv.index('--classes'); path = argv[k + 1]; del argv[k:k + 2]
        rows = [l.rstrip('\n').split('\t') for l in open(path, encoding='utf-8')]
        head = rows[0]
        ci = head.index(col)
        starts = []
        for r in rows[1:]:
            if len(r) > ci and r[ci].startswith('0x'):
                starts.append((int(r[ci], 16), r))
        starts.sort()
        cl = (starts, head)
    d = open(argv[0], 'rb').read()
    imms = [int(x, 16) for x in argv[1].split(',')]
    for imm in imms:
        n = 0
        for o in range(0, len(d) - 3, 4):
            w = struct.unpack_from('>I', d, o)[0]
            op = w >> 26
            if op not in NAMES or (w & 0xffff) != imm: continue
            rt, ra = (w >> 21) & 31, (w >> 16) & 31
            if op in (10, 11):
                txt = '%s cr%d, r%d, 0x%x' % (NAMES[op], rt >> 2, ra, imm)
            elif op == 14 and ra == 0:
                txt = 'li r%d, 0x%x' % (rt, imm)
            else:
                txt = '%s r%d, r%d, 0x%x' % (NAMES[op], rt, ra, imm)
            a = BASE + o
            extra = ''
            if cl:
                starts, head = cl
                k = bisect.bisect_right([s for s, _ in starts], a) - 1
                if k >= 0:
                    s, r = starts[k]
                    extra = '  func 0x%08x (tu %s retail %s pc %s class %s)' % (s, r[0], r[1], r[2] or '-', r[4])
            print('0x%08x  %08x  %s%s' % (a, w, txt, extra))
            n += 1
        print('# imm 0x%x: %d site(s)' % (imm, n))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
