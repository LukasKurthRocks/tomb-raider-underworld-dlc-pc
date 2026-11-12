"""Group N 12.11.2026 (read-only): print the zero-terminated strings at given offsets of one section of a PC DRM
(script debug texts that tools/script_dis.py cuts at 60 characters), or every string of the section with --all.

Usage (from trudlcport):
  ../bin/pyt -t 120 work/n_research_1211/sec_str.py FILE.drm TYPE ID OFF[,OFF..]|--all
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
import drm_write as DW


def main(argv):
    d = DW.read(open(argv[0], 'rb').read(), 'le')
    t, i = int(argv[1]), int(argv[2])
    b = next(s for s in d.sections if s.type == t and s.id == i).data
    if argv[3] == '--all':
        for m in re.finditer(rb'[\x20-\x7e]{6,}', b):
            print('+0x%x  %s' % (m.start(), m.group().decode('ascii')))
        return
    for o in argv[3].split(','):
        o = int(o, 0); e = b.index(b'\0', o)
        print('+0x%x  %s' % (o, b[o:e].decode('latin-1')))


if __name__ == '__main__':
    main(sys.argv[1:])
