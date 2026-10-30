"""Function-level diff of two Xbox 360 executable images dumped from Xenia (read-only; finding 43, shadow power).

Compares the retail image and the title-update image of the same game: both are cut into functions with their own
.pdata, each function body is normalised (branch targets of b/bl, the 16-bit halves of lis/addi/ori/ld/st address
constants masked - they move when the exe is relinked) and hashed; the two hash sequences are aligned in address
order (difflib), so functions that kept their place and body pair up, inserted runs are NEW in the TU, replaced runs
are CHANGED (paired by position inside the run when the counts allow, else listed as new / removed).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/xbox_func_diff.py RETAIL.bin TU.bin [--list] [--mark ADDR,...] [--disp DISP,...]
  --list        print every new / changed TU function (start, size, retail partner)
  --mark A,..   flag TU functions that build one of these addresses (e.g. 0x827754ac,0x827754cc)
  --disp D,..   flag TU functions with a load / store using displacement D (e.g. 0x1244)
Output: counts and byte sizes of equal / changed / new / removed functions, flagged functions.
"""
import sys, os, struct, difflib, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as P

BASE = 0x82000000


def norm_hash(d, fs, fe):
    h = hashlib.md5()
    for a in range(fs, fe, 4):
        w = struct.unpack_from('>I', d, a - BASE)[0]
        op = w >> 26
        if op == 18:                                   # b / bl: target moves
            w &= 0xfc000003
        elif op in (15, 14, 24, 25) or op in P.LOADSTORE:
            w &= 0xffff0000                            # address halves / displacements of globals
        h.update(struct.pack('>I', w))
    return h.hexdigest()[:16] + ':%d' % ((fe - fs) // 4)


def functions(path):
    d, secs = P.load(path)
    funcs = P.pdata(d, secs)
    return d, funcs, [norm_hash(d, s, e) for s, e in funcs]


def disp_users(d, funcs, disps):
    out = set()
    for s, e in funcs:
        for a in range(s, e, 4):
            w = struct.unpack_from('>I', d, a - BASE)[0]
            if (w >> 26) in P.LOADSTORE and (w & 0xffff) in disps:
                out.add(s); break
    return out


def main(argv):
    lst = '--list' in argv; argv = [a for a in argv if a != '--list']
    marks, disps = set(), set()
    if '--mark' in argv:
        k = argv.index('--mark'); marks = set(int(x, 0) for x in argv[k + 1].split(',')); del argv[k:k + 2]
    if '--disp' in argv:
        k = argv.index('--disp'); disps = set(int(x, 0) for x in argv[k + 1].split(',')); del argv[k:k + 2]
    rd, rf, rh = functions(argv[0])
    td, tf, th = functions(argv[1])
    sm = difflib.SequenceMatcher(None, rh, th, autojunk=False)
    size = lambda f: f[1] - f[0]
    equal, changed, new, removed = [], [], [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            equal += [(rf[i], tf[j]) for i, j in zip(range(i1, i2), range(j1, j2))]
        elif tag == 'insert':
            new += tf[j1:j2]
        elif tag == 'delete':
            removed += rf[i1:i2]
        else:
            n = min(i2 - i1, j2 - j1)
            changed += [(rf[i1 + k], tf[j1 + k]) for k in range(n)]
            new += tf[j1 + n:j2]
            removed += rf[i1 + n:i2]
    print('retail %d functions %d B, TU %d functions %d B' % (len(rf), sum(map(size, rf)), len(tf), sum(map(size, tf))))
    print('equal   %6d functions %8d B' % (len(equal), sum(size(t) for r, t in equal)))
    print('changed %6d functions %8d B (TU size; retail %d B)' % (len(changed), sum(size(t) for r, t in changed),
                                                                  sum(size(r) for r, t in changed)))
    print('new     %6d functions %8d B' % (len(new), sum(map(size, new))))
    print('removed %6d functions %8d B' % (len(removed), sum(map(size, removed))))
    flagged = {}
    if marks:
        funcs, res = P.cached(argv[1])
        for fs, items in res.items():
            hit = sorted(v for a, k, v in items if k == 'addr' and v in marks)
            if hit:
                flagged.setdefault(fs, []).append('addr ' + ','.join('0x%08x' % v for v in hit))
    if disps:
        for fs in disp_users(td, tf, disps):
            flagged.setdefault(fs, []).append('disp ' + ','.join('0x%x' % x for x in sorted(disps)))
    cls = {}
    for r, t in equal: cls[t[0]] = ('equal', r[0])
    for r, t in changed: cls[t[0]] = ('changed', r[0])
    for t in new: cls[t[0]] = ('new', None)
    if flagged:
        print('flagged TU functions:')
        by = {}
        for fs, why in sorted(flagged.items()):
            c, rp = cls.get(fs, ('?', None))
            by[c] = by.get(c, 0) + 1
            fe = next(e for s, e in tf if s == fs)
            print('  0x%08x %5d B %-7s %s %s' % (fs, fe - fs, c, ('retail 0x%08x' % rp) if rp else '', '; '.join(why)))
        print('  by class: %s' % by)
    if lst:
        print('changed:')
        for r, t in changed:
            print('  TU 0x%08x %5d B  retail 0x%08x %5d B' % (t[0], size(t), r[0], size(r)))
        print('new:')
        for t in new:
            print('  TU 0x%08x %5d B' % (t[0], size(t)))


if __name__ == '__main__':
    main(sys.argv[1:])
