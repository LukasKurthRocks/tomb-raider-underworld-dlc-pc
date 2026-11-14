"""W4 (2026-11-14): which intros of DLC 1 units carry a given instance script (intro +0x7c), read-only.

Usage (from the repository root):
  ../bin/pyt -t 600 work/w4_1411/w4_intro_scripts.py SID[,SID..]|all SOURCE [SOURCE ...]
  SOURCE = a PC (little-endian) DRM file, a folder of PC DRMs, or dlc:NAME.drm / xbox:NAME.drm / pc:NAME.drm
Prints per hit: source, intro index, object id + name (PC object list), unique id (+0x58), script id (+0x7c),
position (floats +0x10). Exit code 0.
"""
import sys, os, struct
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import drm_reloc as R
import script_func_list as FL

OBJ = os.path.join(ROOT, 'work', 'generic', 'merged', 'tr8', 'pc-w', 'objectlist.txt')


def names():
    nm = {}
    for line in open(OBJ, encoding='utf8', errors='ignore'):
        p = line.strip().split(',', 1)
        if len(p) == 2 and p[0].isdigit(): nm[int(p[0])] = p[1]
    return nm


def intros(S, e):
    """[(index, obj, uid, script, (x, y, z))] of a unit DRM (section 0 = Level, unit DTP at Level+0x74)"""
    E = '>' if e == 'be' else '<'
    if not S or S[0][0] != 0 or not S[0][2] or len(S[0][2]) < 0x78: return []
    ext = {so: (si, do) for si, so, do in R.parse(S[0][3], e).external}
    if 0x74 not in ext: return []
    di, do = ext[0x74]
    d = S[di][2]
    if S[di][0] != 7 or do != 0 or not d or len(d) < 0x14: return []
    ri = dict(R.parse(S[di][3], e).internal)
    n = struct.unpack_from(E + 'I', d, 0xc)[0]; t = ri.get(0x10)
    if t is None or t + 0x90 * n > len(d): return []
    out = []
    for k in range(n):
        o = t + 0x90 * k
        box = None
        b = ri.get(o + 0x78)    # intro data block (trigger volume: shape byte +0x30, half extents +0x34..+0x3c, radius +0x40)
        if b is not None and b + 0x44 <= len(d):
            box = (d[b + 0x30], struct.unpack_from(E + 'ffff', d, b + 0x34))
        out.append((k, struct.unpack_from(E + 'H', d, o + 0x50)[0], struct.unpack_from(E + 'I', d, o + 0x58)[0],
                    struct.unpack_from(E + 'I', d, o + 0x7c)[0], struct.unpack_from(E + 'fff', d, o + 0x10), box))
    return out


def run(src, want, nm, e_obj):
    try:
        S, e = FL.sections(src)
    except SystemExit as ex:
        print('%s: %s' % (src, ex)); return
    except Exception as ex:
        print('%s: read error %s' % (src, ex)); return
    E = '>' if e == 'be' else '<'
    org = struct.unpack_from(E + 'fff', S[0][2], 0x80) if S and S[0][0] == 0 and S[0][2] and len(S[0][2]) >= 0x8c else None
    if org: print('%-40s Level+0x80 %.1f %.1f %.1f (live = data - this)' % (os.path.basename(src), *org))
    for k, obj, uid, sid, pos, box in intros(S, e):
        if want is None or sid in want:
            live = ' live %9.1f %9.1f %9.1f' % tuple(p - o for p, o in zip(pos, org)) if org else ''
            bx = ''
            if box and 'volume' in nm.get(obj, ''):
                bx = ' shape %d half %.1f %.1f %.1f r %.1f' % (box[0], *box[1])
            print('%-40s #%-4d obj %5d %-36s uid %6d script %6d pos %9.1f %9.1f %9.1f%s%s' % (
                os.path.basename(src), k, obj, nm.get(obj, '?') if e == 'le' else '(xbox obj id)', uid, sid, *pos,
                live, bx))


def main(argv):
    want = None if argv[0] == 'all' else {int(x) for x in argv[0].split(',')}
    nm = names()
    for a in argv[1:]:
        if os.path.isdir(a):
            for f in sorted(os.listdir(a)):
                if f.lower().endswith('.drm'): run(os.path.join(a, f), want, nm, 'le')
        else:
            run(a, want, nm, 'le')
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
