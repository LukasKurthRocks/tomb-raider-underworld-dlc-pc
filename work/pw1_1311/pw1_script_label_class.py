"""PW.1 (2026-11-13): which byte-order / id class the learned script table (work/script/script_table.pkl,
tools/script_learn.py) gives a script word label, with the class counts behind it (read-only).

Usage (from the repository root):
  ../bin/pyt -t 300 work/pw1_1311/pw1_script_label_class.py [BASETYPE USERTYPE]   (default 10 4697)
Prints for the label ('init', BASETYPE, 1, 0, USERTYPE) and its prefixes the counter and the chosen class.
Exit code 0.
"""
import sys, os, pickle
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import script_learn as SL


def main(argv):
    bt, ut = (int(argv[0]), int(argv[1])) if len(argv) >= 2 else (10, 4697)
    T = SL.Table.load()
    print('table', SL.TABLE)
    xw = bytes.fromhex(argv[2]) if len(argv) >= 3 else bytes.fromhex('25970000')
    shape = '~' + SL._shape(xw)
    for depth in (0, 1):
        lab = ('init', bt, depth, 0, ut, shape)
        print('label', lab)
        for p in SL.prefixes(lab):
            c = T.v.get(p)
            if c:
                print('   prefix %-40s %s' % (p, ', '.join('%s %d' % kv for kv in c.most_common(8))))
        print('   best:', T.best(lab), ' prior:', T.prior.get(lab[:-1]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
