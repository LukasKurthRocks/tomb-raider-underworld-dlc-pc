"""List the object table of an Xbox 360 TRU memory image (read-only) and optionally compare it with a PC id list.

Object 858 (player_tru_dlc2_extension) investigation: the TU looks the extension up in the object table
(Xbox 0x82979280, 0xcc entries x 0x24 bytes: +8 object pointer, +0xc s16 id, +0xe u16 state, 2 = loaded; PC 0xdb7400,
same layout). This prints the entries in use of a Xenia memory image taken during play.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/xbox_object_table.py IMAGE [--objectlist objectlist.txt] [--pc ID,ID,..] [--raw]
  IMAGE: memory image with guest base 0x82000000 (work/xenia_dump/*_image*.bin)
"""
import sys, struct

BASE = 0x82000000
TABLE = 0x82979280
COUNT = 0xcc
SIZE = 0x24


def load_names(path):
    names = {}
    if not path:
        return names
    for line in open(path, encoding='latin-1'):
        line = line.strip()
        if ',' in line:
            a, b = line.split(',', 1)
            if a.strip().isdigit():
                names[int(a)] = b.strip()
    return names


def main(argv):
    names, pc, raw = {}, None, False
    if '--objectlist' in argv:
        k = argv.index('--objectlist'); names = load_names(argv[k + 1]); del argv[k:k + 2]
    if '--pc' in argv:
        k = argv.index('--pc'); pc = [int(x) for x in argv[k + 1].split(',') if x]; del argv[k:k + 2]
    if '--raw' in argv:
        argv.remove('--raw'); raw = True
    d = open(argv[0], 'rb').read()
    off = TABLE - BASE
    used = []
    for i in range(COUNT):
        e = d[off + i * SIZE: off + (i + 1) * SIZE]
        obj = struct.unpack_from('>I', e, 8)[0]
        oid, state = struct.unpack_from('>hH', e, 0xc)
        if raw:
            print('%3d %s' % (i, e.hex()))
        if oid or state or obj:
            used.append((i, oid, state, obj))
    print('object table 0x%08x: %d entries in use' % (TABLE, len(used)))
    for i, oid, state, obj in used:
        print('  [%3d] id %4d state %d object 0x%08x  %s' % (i, oid, state, obj, names.get(oid, '?')))
    if pc is not None:
        xs = set(o for _, o, _, _ in used)
        ps = set(pc)
        print('only Xbox: %s' % ', '.join('%d %s' % (o, names.get(o, '?')) for o in sorted(xs - ps)))
        print('only PC:   %s' % ', '.join('%d %s' % (o, names.get(o, '?')) for o in sorted(ps - xs)))
        print('both: %d' % len(xs & ps))


if __name__ == '__main__':
    main(sys.argv[1:])
