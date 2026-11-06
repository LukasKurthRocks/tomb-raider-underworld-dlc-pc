"""Print the slots of a prototype 2007 vtable with the map names of the slot functions (read-only; 2026-11-06 enemy
senses - which vtable slot is EnemyBehavior_*::Priority, so the PC RTTI vtables of the same class can be read slot by
slot; docs Befund-Gegner-Wahrnehmung-0611.md).

The prototype content image work/proto2007/pe/content/tr8_Content.pe is a memory image (file offset = VA -
0x82000000, big endian). Vtable addresses and sizes come from the map inventory work/proto2007/proto_symbols.tsv
(kind 'vftable', name 'Class::vftable'); slot targets are named with every map symbol at that address (several names
= identical folded functions).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/proto_vtable.py CLASS[,CLASS..]        e.g. EnemyBehavior_Melee,EnemySense
"""
import sys, os, struct, csv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PE = os.path.join(ROOT, 'work', 'proto2007', 'pe', 'content', 'tr8_Content.pe')
SYMS = os.path.join(ROOT, 'work', 'proto2007', 'proto_symbols.tsv')
BASE = 0x82000000


def main(argv):
    if not argv: sys.exit(__doc__)
    img = open(PE, 'rb').read()
    names = {}
    vt = {}
    with open(SYMS, encoding='utf-8', errors='replace') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            a = int(r['address'], 16)
            if r['kind'] == 'vftable':
                vt[r['name']] = (a, int(r['size']))
            elif r['kind'] == 'func':
                names.setdefault(a, []).append(r['name'])
    for cls in argv[0].split(','):
        key = cls + '::vftable'
        if key not in vt:
            print('== %s: no vftable symbol' % cls); continue
        a, size = vt[key]
        print('== %s vftable 0x%08x (%d slots by map size)' % (cls, a, size // 4))
        for i in range(size // 4):
            v = struct.unpack_from('>I', img, a - BASE + 4 * i)[0]
            print('   [%2d] +0x%02x 0x%08x %s' % (i, 4 * i, v, ' / '.join(names.get(v, ['?'])[:3])))


if __name__ == '__main__':
    main(sys.argv[1:])
