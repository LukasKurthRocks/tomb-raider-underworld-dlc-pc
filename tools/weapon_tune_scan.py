"""Find and read the weapon tuning record T (INSTANCE_Query(inst, 0x36)) inside a weapon object DRM (read-only;
F10 / B29 shotgun stutter, 04.11.2026).

Facts the search uses (tru.exe, docs/Menue-Funktionen-Katalog.md 17.2 + the shot function 0x6c9e50):
  s8  T+0x4  weapon kind (0..4, HUD)          s8  T+0x5  shots per trigger pull (loop 0x6ca1fc..0x6ca20d)
  s8  T+0xa  ammo type (0xff = none)          s8  T+0xb  clip size
  s16 T+0x14 index of the section-0x38 record passed to 0x6c95f0 per shot (projectile birth 0x69b1c0)
  u8  T+0x88 flags (bit 0x80 = infinite ammo)
Live anchor (TruMenu.log of run 20261103_202947_paket03_rad, cheat.ammo): wp_dlc_handgun T has ammo type -1 and
flags 0xe0.

find FILE.drm [OFF=VAL ...]   every type-7 section offset p where all byte constraints hold (default: the live
                              anchor 0xa=0xff 0x88=0xe0), with the fields above and the relocations that point to p
                              (pointer word, the word before it = a property id if the table is {id, ptr})
read FILE.drm SECID OFF       the fields above at section SECID (type 7) offset OFF (hex)
ptrs FILE.drm SECID LO HI     relocated pointers (any section) whose target in section SECID is in [LO, HI) (hex)
props FILE.drm VALUE          every relocated pointer whose preceding u32 equals VALUE (e.g. 0x36), target listed

Usage (from the repository root):
  ../bin/pyt -t 300 tools/weapon_tune_scan.py find ../data/pc/mods/wp_dlc_handgun.drm
  ../bin/pyt -t 300 tools/weapon_tune_scan.py read work/f10_shotgun/pc_wp_shotgun.drm 3018 0x40
  ../bin/pyt -t 300 tools/weapon_tune_scan.py props work/f10_shotgun/pc_wp_shotgun.drm 0x36
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def load(path):
    D = DW.read(open(path, 'rb').read(), 'le')
    out = []
    for si, s in enumerate(D.sections):
        r = R.parse(bytes(s.reloc), 'le')
        out.append((si, s, bytes(s.data), dict(r.internal), r.external))
    return D, out


def fields(d, p):
    def s8(o): return struct.unpack_from('<b', d, p + o)[0] if p + o < len(d) else None
    def u8(o): return d[p + o] if p + o < len(d) else None
    s16 = struct.unpack_from('<h', d, p + 0x14)[0] if p + 0x16 <= len(d) else None
    return 'kind %s  shots %s  ammo %s  clip %s  rec38 %s  flags88 %s' % (
        s8(4), s8(5), s8(0xa), s8(0xb), s16, ('0x%02x' % u8(0x88)) if u8(0x88) is not None else None)


def pointers_to(secs, si_t, p):
    hits = []
    for si, s, d, intern, ext in secs:
        if si == si_t:
            for o, t in intern.items():
                if t == p:
                    prev = struct.unpack_from('<I', d, o - 4)[0] if o >= 4 else None
                    hits.append('sec %d id %d +0x%x (word before 0x%08x)' % (si, s.id, o, prev if prev is not None else 0))
        for xi, o, t in ext:
            if xi == si_t and t == p:
                prev = struct.unpack_from('<I', d, o - 4)[0] if o >= 4 else None
                hits.append('sec %d id %d +0x%x ext (word before 0x%08x)' % (si, s.id, o, prev if prev is not None else 0))
    return hits


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    mode, path = argv[0], argv[1]
    D, secs = load(path)
    if mode == 'find':
        cons = []
        for a in (argv[2:] or ['0xa=0xff', '0x88=0xe0']):
            k, v = a.split('=')
            cons.append((int(k, 16), int(v, 16)))
        n = 0
        for si, s, d, intern, ext in secs:
            if s.type != 7: continue
            for p in range(0, len(d) - max(k for k, _ in cons)):
                if all(d[p + k] == v for k, v in cons):
                    n += 1
                    print('sec %d type 7 id %d size 0x%x  +0x%x  %s' % (si, s.id, len(d), p, fields(d, p)))
                    for h in pointers_to(secs, si, p): print('    pointed to by ' + h)
        print('%d candidate(s)' % n)
    elif mode == 'read':
        sid, off = int(argv[2]), int(argv[3], 16)
        for si, s, d, intern, ext in secs:
            if s.type == 7 and s.id == sid:
                print('sec %d id %d +0x%x  %s' % (si, s.id, off, fields(d, off)))
                for h in pointers_to(secs, si, off): print('    pointed to by ' + h)
    elif mode == 'ptrs':
        sid, lo, hi = int(argv[2]), int(argv[3], 16), int(argv[4], 16)
        for si_t, s_t, d_t, _, _ in secs:
            if s_t.type != 7 or s_t.id != sid: continue
            for si, s, d, intern, ext in secs:
                if si == si_t:
                    for o, t in sorted(intern.items()):
                        if lo <= t < hi:
                            print('sec %d id %d +0x%x -> +0x%x (word before 0x%08x)' % (
                                si, s.id, o, t, struct.unpack_from('<I', d, o - 4)[0] if o >= 4 else 0))
                for xi, o, t in ext:
                    if xi == si_t and lo <= t < hi:
                        print('sec %d id %d +0x%x ext -> +0x%x' % (si, s.id, o, t))
    elif mode == 'props':
        val = int(argv[2], 16)
        for si, s, d, intern, ext in secs:
            for o, t in sorted(intern.items()):
                if o >= 4 and struct.unpack_from('<I', d, o - 4)[0] == val:
                    print('sec %d type %d id %d +0x%x -> +0x%x   target: %s' % (
                        si, s.type, s.id, o, t, fields(d, t) if s.type == 7 else ''))
            for xi, o, t in ext:
                if o >= 4 and struct.unpack_from('<I', d, o - 4)[0] == val:
                    ts = secs[xi]
                    print('sec %d type %d id %d +0x%x -> sec %d id %d +0x%x   target: %s' % (
                        si, s.type, s.id, o, xi, ts[1].id, t, fields(ts[2], t) if ts[1].type == 7 else ''))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
