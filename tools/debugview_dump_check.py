"""Read TruMenu 0.14's debug view data out of a full tru.exe minidump (read-only; 2026-11-06 TruMenu 0.14 triggers,
docs Befund-TruMenu-Trigger-0611.md): the same memory walks the plugin does at Present, so the layouts can be checked
against a real game state without starting the game.

  triggers   planes: count [0xdba21c], array 0xda61c8; volumes: count [0xdba220], array 0xdb6be0 (at most 0x200);
             entry +0x20 instance, +0x24 flags (bit 31 enabled, bit 30 tested against the player); instance +0x10
             object (+0x14 object id -> name table [0xdb94d0] + id * 8), +0x20 position, +0x30 Euler angles, +0x58
             intro id, +0x100 intro -> +0x78 IntroDataTrigger: +0x30 shape byte (1 box, 2 sphere), +0x34 / +0x38 /
             +0x3c half extents, +0x40 radius, +0x44 plane one-sided byte (0 = one-sided)
  portals    stream unit table 0xdbab40 (0xd8 per entry, 32 entries): +4 state (2 = loaded), +8 Level, +0xc name;
             [Level] = Terrain: +2 s16 portal count, +4 array of 0x100-byte StreamUnitPortal (name +0, +0x82 own id,
             +0x84 destination unit, +0x90 / +0xa0 box min / max, +0xb0..+0xe0 quad corners, +0xf0 normal)
  checkpoint game data [0xc59264]: +0x90 / +0x114 checkpoint id, +0x1f4 mode word

Usage (from the repository root):
  ../bin/pyt -t 900 tools/debugview_dump_check.py DUMP.dmp [--max N]     N trigger rows per list (default 40)
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import minidump_read as MR


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    show = int(argv[argv.index('--max') + 1]) if '--max' in argv else 40
    M = MR.Minidump(argv[0])

    def u32(va):
        b = M.read(va, 4)
        return None if b is None else struct.unpack('<I', b)[0]

    def f(va, n):
        b = M.read(va, 4 * n)
        return None if b is None else struct.unpack('<%df' % n, b)

    def cstr(va, n=64):
        b = M.read(va, n) if va else None
        return '' if b is None else b.split(b'\0', 1)[0].decode('latin-1')

    names = u32(0xdb94d0)

    def objname(inst):
        obj = u32(inst + 0x10)
        oid = u32(obj + 0x14) if obj else None
        if oid is None or not names: return '?', None
        oid &= 0xffff
        p = u32(names + oid * 8)
        return (cstr(p) if p else '?'), oid

    player = u32(0xe7f094)
    pp = f(player + 0x20, 3) if player else None
    print('player [0xe7f094] 0x%08x at %s' % (player or 0, 'n/a' if pp is None else '(%.1f %.1f %.1f)' % pp))
    for label, cnt_va, arr_va in (('planes', 0xdba21c, 0xda61c8), ('volumes', 0xdba220, 0xdb6be0)):
        n = u32(cnt_va)
        print('== %s: count [0x%08x] = %s' % (label, cnt_va, n))
        if n is None or n > 0x200: continue
        shapes = {}
        for i in range(n):
            e = u32(arr_va + 4 * i)
            inst = u32(e + 0x20) if e else None
            flags = u32(e + 0x24) if e else None
            if not inst:
                print('  [%3d] entry 0x%08x: no instance' % (i, e or 0))
                continue
            pos, rot = f(inst + 0x20, 3), f(inst + 0x30, 3)
            intro = u32(inst + 0x100)
            data = u32(intro + 0x78) if intro else None
            nm, oid = objname(inst)
            iid = u32(inst + 0x58)
            if data:
                sb = M.read(data + 0x30, 1)
                shape = sb[0] if sb else None
                ext, rad = f(data + 0x34, 3), f(data + 0x40, 1)
                side = M.read(data + 0x44, 1)
            else:
                shape, ext, rad, side = None, None, None, None
            shapes[shape] = shapes.get(shape, 0) + 1
            if i < show:
                print('  [%3d] %-34s obj %4s intro %8s flags %08x en %d pl %d pos (%.0f %.0f %.0f) rot (%.3f %.3f %.3f) '
                      'shape %s ext %s r %s one-sided-byte %s' % (
                          i, nm, oid, iid, flags or 0, (flags or 0) >> 31 & 1, (flags or 0) >> 30 & 1,
                          *(pos or (0, 0, 0)), *(rot or (0, 0, 0)), shape,
                          'n/a' if ext is None else '(%.1f %.1f %.1f)' % ext, 'n/a' if rad is None else '%.1f' % rad[0],
                          'n/a' if not side else side[0]))
        print('  shapes: %s' % ', '.join('%s x%d' % (k, v) for k, v in sorted(shapes.items(), key=lambda x: str(x[0]))))
    print('== stream units (0xdbab40) and portals')
    for k in range(32):
        e = 0xdbab40 + 0xd8 * k
        raw = M.read(e, 0x50)
        if raw is None: continue
        st = raw[4]
        lev, = struct.unpack_from('<I', raw, 8)
        name = raw[0xc:0x4c].split(b'\0', 1)[0].decode('latin-1')
        if st != 2 or not lev: continue
        ter = u32(lev)
        cnt = M.read(ter + 2, 2) if ter else None
        arr = u32(ter + 4) if ter else None
        n = struct.unpack('<h', cnt)[0] if cnt else None
        print('unit [%2d] %-26s Level 0x%08x Terrain 0x%08x portals %s array 0x%08x' % (k, name, lev, ter or 0, n, arr or 0))
        if not n or not arr or n > 64: continue
        for i in range(n):
            p = arr + 0x100 * i
            q = f(p + 0x90, 28)
            ids = M.read(p + 0x80, 6)
            if q is None or ids is None:
                print('   portal %d: not in the dump' % i)
                continue
            to, own, dest = struct.unpack('<hhh', ids)
            pts = [q[4 * j:4 * j + 3] for j in range(7)]
            print('   -> %-24s to %4d own %4d dest %4d min (%.0f %.0f %.0f) max (%.0f %.0f %.0f) corners %s normal '
                  '(%.2f %.2f %.2f)' % (cstr(p, 0x80), to, own, dest, *pts[0], *pts[1],
                                        ' '.join('(%.0f %.0f %.0f)' % c for c in pts[2:6]), *pts[6]))
    print('== instances named *checkpoint* (list [0xd98d54], next +8)')
    inst, n = u32(0xd98d54), 0
    while inst and n < 4096:
        nm, oid = objname(inst)
        if 'checkpoint' in nm.lower():
            pos = f(inst + 0x20, 3)
            print('   %-28s obj %4s intro %8s at %s' % (nm, oid, u32(inst + 0x58),
                                                    'n/a' if pos is None else '(%.0f %.0f %.0f)' % pos))
        n += 1
        inst = u32(inst + 8)
    print('   %d instances walked' % n)
    gd = u32(0xc59264)
    if gd:
        cp, cp2 = u32(gd + 0x90), u32(gd + 0x114)
        mode = M.read(gd + 0x1f4, 2)
        print('== game data [0xc59264] 0x%08x: checkpoint +0x90 %s, +0x114 %s, mode +0x1f4 %s' % (
            gd, cp, cp2, struct.unpack('<H', mode)[0] if mode else None))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
