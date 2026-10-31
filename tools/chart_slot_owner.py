"""Find the records of a converted (little-endian) player state chart DTP that refer to transition slots by index
(read-only; TU state translation 2026-10-31: which chart state owns a transition such as the rock-vein / wall-run
transitions with markup values 607 / 608).

The chart keeps all transitions in one pointer array (block +0x5b020 in doppelganger_casual DTP 20212, see
tools/chart_transitions.py --holders); there are no pointers into the middle of that array, so the states must refer
to their transitions by slot index. This tool searches every u16 equal to one of the given slot indices and prints
the 32 bytes around it as u16 words, so the record layout can be read off.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/chart_slot_owner.py PC.drm SID SLOT[,SLOT..] [--before N] [--after N]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    before, after = 16, 16
    if '--before' in argv: k = argv.index('--before'); before = int(argv[k + 1]); del argv[k:k + 2]
    if '--after' in argv: k = argv.index('--after'); after = int(argv[k + 1]); del argv[k:k + 2]
    D = DW.read(open(argv[0], 'rb').read(), 'le')
    s = [q for q in D.sections if q.id == int(argv[1]) and q.type == 7][0]
    d = bytes(s.data)
    it = dict(R.parse(bytes(s.reloc), 'le').internal)
    if argv[2] == '--targets':
        # --targets FROM TO: relocation targets inside [FROM, TO) and the words around each pointer to them
        lo, hi = int(argv[3], 16), int(argv[4], 16)
        for src, tgt in sorted(it.items(), key=lambda x: x[1]):
            if lo <= tgt < hi:
                a = max(0, src - before) & ~1
                words = ' '.join('%s%d' % ('*' if p == src else '', struct.unpack_from('<H', d, p)[0])
                                 for p in range(a, min(len(d), src + after), 2))
                print('target +0x%05x <- +0x%05x: [+0x%05x] %s' % (tgt, src, a, words))
        return
    slots = [int(x) for x in argv[2].split(',')]
    for slot in slots:
        hits = [o for o in range(0, len(d) - 1, 2) if struct.unpack_from('<H', d, o)[0] == slot]
        print('slot %d: %d u16 hits' % (slot, len(hits)))
        for o in hits:
            a = max(0, o - before) & ~1
            b = min(len(d), o + after)
            words = []
            for p in range(a, b, 2):
                mark = '*' if p == o else ''
                rel = 'P' if p in it else ''
                words.append('%s%d%s' % (mark, struct.unpack_from('<H', d, p)[0], rel))
            print('  +0x%05x: [+0x%05x] %s' % (o, a, ' '.join(words)))


if __name__ == '__main__':
    main(sys.argv[1:])
