"""Read-only wrapper: run tools/pe_dis.py for several ranges of the PC tru.exe and write them to one text file.

Usage (from the repository root):
  ../bin/pyt -t 300 work/adrnotarget_1411/dis.py OUT.txt EXE FROM:TO [FROM:TO ...]
"""
import sys, os, io, contextlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import pe_dis


def main(argv):
    out, exe = argv[0], argv[1]
    with open(out, 'w', encoding='utf-8') as f:
        for r in argv[2:]:
            lo, hi = r.split(':')
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                pe_dis.main([exe, lo, hi])
            f.write('; ---- range %s .. %s\n' % (lo, hi))
            f.write(buf.getvalue())
    print('written', out)


if __name__ == '__main__':
    main(sys.argv[1:])
