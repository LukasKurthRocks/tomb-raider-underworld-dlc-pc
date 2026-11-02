"""Find PowerPC instructions with a given 16-bit immediate in an Xbox 360 image (read-only; 2026-11-02, TU function
comparison item L9: does any exe code name the TU-only generalbank DTPs 21237 / 21238 / 22194 or a message id?).

Matches li / addi / addis-free forms (op 14 with any rA), cmpwi / cmplwi (ops 11 / 10), ori / andi. (24 / 28) and
mulli (7) whose immediate equals one of the values (signed or unsigned 16-bit), in all code sections, .pdata or not.
With --pair the TU function is also given with its retail partner and class from work/tu_funcdiff/classes.tsv.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/ppc_imm_scan.py IMAGE IMM[,IMM..] [--classes work/tu_funcdiff/classes.tsv]
Only addresses and decoded mnemonics are printed.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xbox_image_sections as XS
import ppc_xrefs as P

NAMES = {14: 'addi/li', 11: 'cmpwi', 10: 'cmplwi', 24: 'ori', 28: 'andi.', 7: 'mulli'}


def main(argv):
    classes = None
    if '--classes' in argv:
        k = argv.index('--classes'); classes = argv[k + 1]; del argv[k:k + 2]
    if len(argv) != 2:
        sys.exit(__doc__)
    d, secs = P.load(argv[0])
    funcs = P.pdata(d, secs)
    want = set(int(x, 0) & 0xffff for x in argv[1].split(','))
    info = {}
    if classes:
        with open(classes, encoding='utf-8') as f:
            f.readline()
            for line in f:
                v = line.rstrip('\n').split('\t')
                if v[0]:
                    info[int(v[0], 16)] = '%s %s %s' % (v[1] or '-', v[4], v[5])
    n = 0
    for name, start, size, ch in XS.sections(d, 0x82000000):
        if not (ch & 0x20):
            continue
        off = start - 0x82000000
        m = min(size, len(d) - off) // 4
        w = struct.unpack_from('>%dI' % m, d, off)
        for i, x in enumerate(w):
            op = x >> 26
            if op in NAMES and (x & 0xffff) in want:
                va = start + 4 * i
                f = P.func_of(funcs, va)
                print('0x%08x  %-8s r%d, r%d, 0x%x   in %s %s' % (
                    va, NAMES[op], (x >> 21) & 31, (x >> 16) & 31, x & 0xffff, ('0x%08x' % f[0]) if f else '?',
                    info.get(f[0], '') if f else ''))
                n += 1
    print('%d hits' % n)


if __name__ == '__main__':
    main(sys.argv[1:])
