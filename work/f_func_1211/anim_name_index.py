"""Group F (Q78 pose): where do Lara's animation names (e.g. screen_capture_01..07) sit in her object DTP, and which
record index points at them (read-only).

For every type-7 section of the DRM that contains the name string: the string offset, every internal relocation whose
target is that string, and - when the pointing fields form a table of equal stride - the record index of the name and
the record words around it (to tie the name to the anim table index / anim section id).

Usage (from the repository root):
  ../bin/pyt -t 600 work/f_func_1211/anim_name_index.py MODS_DIR OBJECT NAME[,NAME..]
  OBJECT is resolved like the game (MODS_DIR flat <name>.drm, then PC patch.000, bigfile.000).
"""
import sys, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
sys.path.insert(0, os.path.join(HERE, '..', 'q83_allenemies_1111'))
import drm_write as DW, drm_reloc as R
from enemy_catalog import Src


def main(argv):
    if len(argv) < 3:
        print(__doc__); return 2
    src = Src(argv[0])
    got = src.get(argv[1])
    if not got:
        print('object %s not found' % argv[1]); return 1
    D = DW.read(got[2], 'le')
    names = argv[2].split(',')
    for si, s in enumerate(D.sections):
        if s.type != 7: continue
        d = bytes(s.data)
        hits = {n: d.find(n.encode() + b'\0') for n in names}
        if all(v < 0 for v in hits.values()): continue
        rel = R.parse(bytes(s.reloc), 'le')
        by_target = {}
        for o, t in rel.internal: by_target.setdefault(t, []).append(o)
        allsrc = sorted(o for o, _ in rel.internal)
        print('== DTP %d (section #%d) size 0x%x, %d internal relocations' % (s.id, si, len(d), len(rel.internal)))
        intern = dict(rel.internal)
        # object DTP: +0x54 anim table count (u16 at +0x54 per skeleton_compare), +0x58 -> table of 12-byte records
        # {u16 anim section id, s16 run-time slot, u32, char* debug name} (0x5b4290: [Object+0x44] + k * 12)
        tab = intern.get(0x58)
        cnt = struct.unpack_from('<H', d, 0x54)[0] if len(d) > 0x56 else 0
        if tab is not None: print('  anim table +0x58 -> +0x%x, count (u16 +0x54) %d' % (tab, cnt))
        for n, off in hits.items():
            if off < 0: print('  %-24s not in this DTP' % n); continue
            srcs = by_target.get(off, [])
            print('  %-24s string +0x%x, pointed at from %s' % (n, off, ', '.join('+0x%x' % o for o in srcs) or '-'))
            for o in srcs:
                # stride guess: distance to the neighbouring pointer fields that also point at strings
                k = allsrc.index(o)
                nb = [allsrc[j] for j in range(max(0, k - 3), min(len(allsrc), k + 4))]
                print('    neighbours %s' % ' '.join('+0x%x' % x for x in nb))
                w = [struct.unpack_from('<I', d, o + 4 * j)[0] for j in range(-2, 4) if 0 <= o + 4 * j < len(d) - 3]
                print('    words around (from -8): %s' % ' '.join('%08x' % x for x in w))
                if tab is not None and (o - 8 - tab) % 12 == 0 and 0 <= (o - 8 - tab) // 12 < max(cnt, 1) * 2:
                    k = (o - 8 - tab) // 12
                    aid, slot = struct.unpack_from('<Hh', d, o - 8)
                    print('    anim table index %d: anim section id %d, run-time slot %d' % (k, aid, slot))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
