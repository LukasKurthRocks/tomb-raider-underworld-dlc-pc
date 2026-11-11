"""Default gear lists of PC unit DRMs (read-only; Q84 2026-11-11, Mediterranean diving tanks).

The player message handler (case at 0x7200ba..0x72011b, jump table entry 0x721040) takes the player's unit, its level
(stream unit record +8, 0x5c1b10), the environment block [level +0x70] and the word pair at env +0x2b4 = two DTP ids
{+0 list A, +4 list B (used when gameTracker+0x1244 is set)}; 0x7198d0 gives every object of the chosen list through
0x716130 (request object, birth a child instance, add it to the weapon manager). A list DTP is
{+0 u16* weapon ids, +4 count, +8 u16* gear ids, +0xc count}. The handler runs only while game block byte +0x390
matches its case value (meaning of the flag not traced).

This tool follows the same pointers through the DRM relocations (internal + external) starting at section 0 (the
level) and prints both lists with object names from an objectlist (`id,name` lines, e.g.
work/generic/lists/pc_objectlist.txt). DTPs that are not in the unit are looked up in the DRMs after --also.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/unit_default_gear.py OBJLIST UNIT.drm [UNIT.drm ...] [--also OTHER.drm ...]
  e.g. ../bin/pyt -t 600 tools/unit_default_gear.py work/generic/lists/pc_objectlist.txt l1_seatop.drm
Exit code 0; a unit without the pointer chain prints 'no gear block'.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import drm_reloc as R


def names(path):
    out = {}
    for ln in open(path, encoding='latin-1'):
        p = ln.strip().split(',', 1)
        if len(p) == 2 and p[0].isdigit(): out[int(p[0])] = p[1]
    return out


class Img:
    """sections of one little-endian DRM with a pointer map per section: offset -> (section index, target offset)"""
    def __init__(self, path):
        D = DW.read(open(path, 'rb').read(), 'le')
        self.data = [bytes(s.data) for s in D.sections]
        self.dtp = {s.id: i for i, s in enumerate(D.sections) if s.type == 7}
        self.ptr = []
        for i, s in enumerate(D.sections):
            r = R.parse(bytes(s.reloc), 'le') if s.reloc else R.Reloc()
            m = {o: (i, t) for o, t in r.internal}
            for si, src, dst in r.external: m[src] = (si, dst)
            self.ptr.append(m)

    def deref(self, loc, off):
        return self.ptr[loc[0]].get(loc[1] + off) if loc else None

    def u32(self, loc, off):
        return struct.unpack_from('<I', self.data[loc[0]], loc[1] + off)[0]

    def u16s(self, loc, n):
        return [struct.unpack_from('<H', self.data[loc[0]], loc[1] + 2 * i)[0] for i in range(n)]


def gearlist(img, loc, nm):
    out = []
    for k in (0, 8):
        p = img.deref(loc, k); n = img.u32(loc, k + 4)
        ids = img.u16s(p, n) if p is not None else []
        out.append('[%s]' % ', '.join('%d %s' % (i, nm.get(i, '?')) for i in ids))
    return ' + '.join(out)


def show(imgs, did, nm):
    for im in imgs:
        if did in im.dtp: return gearlist(im, (im.dtp[did], 0), nm)
    return '(DTP not found)'


def main(argv):
    if len(argv) < 2: print(__doc__); return 1
    nm = names(argv[0]); rest = argv[1:]; also = []
    if '--also' in rest:
        k = rest.index('--also'); also = rest[k + 1:]; rest = rest[:k]
    extra = [Img(p) for p in also]
    for path in rest:
        img = Img(path)
        g = img.deref(img.deref((0, 0), 0x70), 0x2b4)
        if g is None:
            print('%-26s no gear block' % os.path.basename(path)); continue
        a, b = img.u32(g, 0), img.u32(g, 4)
        print('%-26s A=DTP %d %s | B=DTP %d %s' % (os.path.basename(path), a, show([img] + extra, a, nm),
                                                    b, show([img] + extra, b, nm)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
