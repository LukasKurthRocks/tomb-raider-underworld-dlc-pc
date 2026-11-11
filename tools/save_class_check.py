"""Which checkpoint save class an object gets: the PC save classifier SAVE_SaveableInstance (tru.exe 0x556020) applied
to object DRMs, read-only (Q72, 2026-11-11, workspace docs Befund-Checkpoint-Zustand-Q72-1111.md).

Object data = section 11:<object id>; its word +0 is an id reference to the type-7 object DTP that the Object tracker
entry points at (`[Object+0]` in the classifier; the same DTP gives the anim count +0x5c / anim list +0x60 of the
object load 0x54e200). Classifier tests on that DTP (PC 0x556020..0x5560cd, TU 0x821fd618 unchanged):
  +4 & 2                         -> 0: never saved
  +4 & 0x400000 or +8 & 0x800    -> the dead bit of the intro is tested first (alive -> full save)
  +0 & 0x80000000                -> full save: block 3 (moved to another unit / spawned / no intro record) or block 4
                                    (position / rotation only if changed, iflags +0x14 / +0x18, link parent +0x228)
  otherwise                      -> block 5 (0x14 B: anim component words only, no position) unless the instance
                                    flag +0x14 & 0x100000 is set and query 0x5d answers non-zero
Not decided here (instance state at save time): the player and dead / excluded instances (+0x18 & 0x20000).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/save_class_check.py OBJ.drm [OBJ.drm ...]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_idrefs as IR


def classify(w0, w4, w8):
    if w4 & 2: return 'never saved (+4 bit 2)'
    pre = 'dead bit tested; ' if (w4 & 0x400000) or (w8 & 0x800) else ''
    if w0 & 0x80000000: return pre + 'full (block 3 / 4, with position)'
    return pre + 'block 5 (anim state only, no position) unless iflag 0x100000 + query 0x5d'


def main(argv):
    if not argv: sys.exit(__doc__)
    for path in argv:
        secs, e = IR.load(path)
        idx = {(t, i): d for t, i, d, r in secs}
        s11 = [(i, d) for t, i, d, r in secs if t == 11]
        name = os.path.basename(path)
        if not s11:
            print('%-36s no type-11 section' % name); continue
        oid, d11 = s11[0]
        dtp_id, = struct.unpack_from('<I', bytes(d11), 0)
        d = idx.get((7, dtp_id))
        if d is None:
            print('%-36s 11:%d -> 7:%d missing' % (name, oid, dtp_id)); continue
        w0, w4, w8 = struct.unpack_from('<III', bytes(d), 0)
        print('%-36s obj %4d dtp 7:%-6d +0 %08x +4 %08x +8 %08x  %s' % (name, oid, dtp_id, w0, w4, w8,
                                                                        classify(w0, w4, w8)))


if __name__ == '__main__':
    main(sys.argv[1:])
