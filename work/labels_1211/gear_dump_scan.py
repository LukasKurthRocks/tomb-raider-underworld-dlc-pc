"""TruMenu 0.22.36 (labels, 2026-11-12): which instances of a full tru.exe minidump are Lara's own gear, by game data
(read-only). For every instance of the list [0xd98d54] (+0x08 next) it prints the object name, the parent +0x54
(INSTANCE_BirthObject 0x5bd381 stores the parent there; the give-gear path 0x716183 passes the player [0xe7f094]),
whether it sits in a weapon-manager slot handle (WM = [[0xfadb58]+0x500], 15 slots, handles WM+4+16i / WM+0xc+16i) or
in the gear list WM+0xf4 (8 handles), and the 0.21 LfNotDrawn reason (hide 0x800, kill 0x20, scene entity off).

Usage (from the repository root):
  ../bin/pyt -t 900 work/labels_1211/gear_dump_scan.py DUMP.dmp [--all]
  without --all only instances with a gear hit, a g_ / wp_ / grenade name or the player as parent are printed
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import minidump_read as MR


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    show_all = '--all' in argv
    M = MR.Minidump(argv[0])

    def u32(va):
        b = M.read(va, 4) if va else None
        return None if b is None else struct.unpack('<I', b)[0]

    def cstr(va, n=64):
        b = M.read(va, n) if va else None
        return '' if b is None else b.split(b'\0', 1)[0].decode('latin-1')

    names = u32(0xdb94d0)

    def objname(inst):
        obj = u32(inst + 0x10)
        oid = u32(obj + 0x14) if obj else None
        if oid is None or not names: return '?'
        p = u32(names + (oid & 0xffff) * 8)
        return cstr(p) if p else '?'

    def resolve(h):                          # handle {inst, stamp}: valid when [inst+0x44] == stamp (0x5b39d0)
        inst, stamp = u32(h), u32(h + 4)
        return inst if inst and u32(inst + 0x44) == stamp else 0

    player = u32(0xe7f094)
    tracker = u32(0xfadb58)
    wm = u32(tracker + 0x500) if tracker else None
    slots, glist = {}, {}
    if wm:
        for i in range(15):
            for hand, off in ((0, 4), (1, 0xc)):
                inst = resolve(wm + off + 16 * i)
                if inst: slots[inst] = 'slot %d hand %d' % (i, hand)
        for i in range(8):
            inst = resolve(wm + 0xf4 + 8 * i)
            if inst: glist[inst] = 'gear list %d' % i
    print('player 0x%08x, tracker 0x%08x, WM 0x%08x: %d slot handle(s), %d gear-list handle(s)' % (
        player or 0, tracker or 0, wm or 0, len(slots), len(glist)))
    inst = u32(0xd98d54)
    n = shown = 0
    stats = {'parent': 0, 'wm': 0, 'both': 0, 'name_only': 0}
    while inst and n < 4096:
        n += 1
        nm = objname(inst)
        parent = u32(inst + 0x54) or 0
        f14 = u32(inst + 0x14) or 0
        by_parent = player and parent == player
        by_wm = inst in slots or inst in glist
        gear_name = nm.startswith(('g_', 'wp_')) or 'grenade' in nm
        if by_parent and by_wm: stats['both'] += 1
        elif by_parent: stats['parent'] += 1
        elif by_wm: stats['wm'] += 1
        elif gear_name and inst != player: stats['name_only'] += 1
        if show_all or by_parent or by_wm or gear_name or inst == player:
            shown += 1
            print('0x%08x %-28s id %10d parent 0x%08x%s f14 0x%08x hide %d kill %d  %s %s' % (
                inst, nm, u32(inst + 0x58) or 0, parent, ' (PLAYER)' if by_parent else '', f14, 1 if f14 & 0x800 else 0,
                1 if f14 & 0x20 else 0, slots.get(inst, ''), glist.get(inst, '')))
        inst = u32(inst + 8)
    print('%d instance(s) walked, %d printed; gear: parent = player and WM %d, parent only %d, WM only %d; '
          'gear-like name without either %d' % (n, shown, stats['both'], stats['parent'], stats['wm'], stats['name_only']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
