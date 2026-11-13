"""PW.1 (2026-11-13): find intro ids in unit DRMs (read-only).

Usage (from the repository root):
  ../bin/pyt -t 600 work/pw1_1311/pw1_find_intro.py ID[,ID..] FILE.drm [FILE.drm ...] [--be]
Prints file, intro id, object id + name (PC object list), position. Exit code 0.
"""
import sys, os, struct
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import drm_write as DW, unit_ids as U

OBJ = os.path.join(ROOT, 'work', 'generic', 'merged', 'tr8', 'pc-w', 'objectlist.txt')


def main(argv):
    argv = list(argv)
    e = 'le'
    if '--be' in argv: argv.remove('--be'); e = 'be'
    E = '>' if e == 'be' else '<'
    ids = {int(v) for v in argv[0].split(',')}
    nm = {}
    for line in open(OBJ, encoding='utf8', errors='ignore'):
        p = line.strip().split(',', 1)
        if len(p) == 2 and p[0].isdigit(): nm[int(p[0])] = p[1]
    for path in argv[1:]:
        try:
            D = DW.read(open(path, 'rb').read(), e)
        except Exception as ex:
            continue
        secs = [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]
        L = U.level_info(secs, e)
        if not L: continue
        for si, o in L['intros']:
            d = secs[si]['data']
            uid = struct.unpack_from(E + 'I', d, o + 0x58)[0]
            if uid in ids:
                oid = struct.unpack_from(E + 'H', d, o + 0x50)[0]
                pos = struct.unpack_from(E + '3f', d, o + 0x10)
                print('%s: intro %d obj %d %s pos %.0f %.0f %.0f' % (
                    os.path.basename(path), uid, oid, nm.get(oid, '?'), *pos))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
