"""PW.1 (2026-11-13): list the unit marker records (unit DTP +0xac count, +0xb4 -> 0x40-byte records {pos, rot,
u32 global id @+0x20}; tools/unit_ids.py 'nodes') of a unit DRM, optionally only the given ids (read-only).

Usage (from the repository root):
  ../bin/pyt -t 300 work/pw1_1311/pw1_markers.py FILE.drm [--be] [--ids 9602,9621]
Prints id, position (+0x00) and the raw record words. Exit code 0.
"""
import sys, os, struct
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import drm_write as DW, unit_ids as U


def main(argv):
    argv = list(argv)
    e = 'le'
    if '--be' in argv: argv.remove('--be'); e = 'be'
    ids = None
    if '--ids' in argv:
        i = argv.index('--ids'); ids = {int(v) for v in argv[i + 1].split(',')}; del argv[i:i + 2]
    E = '>' if e == 'be' else '<'
    D = DW.read(open(argv[0], 'rb').read(), e)
    secs = [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]
    L = U.level_info(secs, e)
    print('%s: %d marker records' % (os.path.basename(argv[0]), len(L['nodes'])))
    for si, o in L['nodes']:
        d = secs[si]['data']
        gid = struct.unpack_from(E + 'I', d, o + 0x20)[0]
        if ids is not None and gid not in ids: continue
        pos = struct.unpack_from(E + '3f', d, o)
        words = ' '.join('%08x' % w for w in struct.unpack_from(E + '16I', d, o))
        print('  id %6d (0x%x) pos %9.1f %9.1f %9.1f  rec +0x%x  %s' % (gid, gid, pos[0], pos[1], pos[2], o, words))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
