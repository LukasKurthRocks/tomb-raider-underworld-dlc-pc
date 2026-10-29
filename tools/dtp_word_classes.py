"""How does a PC DTP encode the words of its Xbox source? (read-only; checks byte-order rules such as float_fix's)

Each 4-byte word of the Xbox DTP (big-endian) is compared with the same offset of a PC DTP and classed:
  same    bytes equal (e.g. 0, symmetric patterns)
  s32     the 4 bytes reversed (32-bit value: float or int)
  s16     each 16-bit half swapped (two 16-bit values)
  raw     PC still has the Xbox bytes (and they are not symmetric)
  other   anything else (remapped id, re-authored value)
Words at relocation offsets (pointers, id references) are counted separately. With --float only words whose Xbox
value is a plausible float (float_fix.plaus, strict) are counted.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/dtp_word_classes.py SOURCE NAME XBOX_DTP_ID PC_DRM [PC_DTP_ID] [--float]
  SOURCE: pack10 | pack11 | base (Xbox title update, layer1, layer2)   NAME: e.g. co_doppelganger.drm
  PC_DRM: a PC DRM file, or 'pc' for the same name in the PC base game; PC_DTP_ID default: the PC DTP of the same size
"""
import sys, os, struct, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc
from drm import cdrm_decode, sections_with_data
import drm_reloc as R, drm_write as DW
from convert_dlc import R as DLC_ROOT, PACKS

BASE = ['../data/TombRaiderUnderworld_Patched/' + f for f in ('TitleUpdate.000', 'layer1.000', 'layer2.000')]
PC = ['../data/pc/patch.000', '../data/pc/bigfile.000']
BS = chr(92)


def find(paths, endian, name):
    for p in paths:
        a = Archive(p, endian); r = [x for x in a.find(crc(name)) if x['spec'] == 0xffffffff]
        if r: return sections_with_data(cdrm_decode(a.read(r[0]), endian), endian)[1]
    return None


def plaus(b):
    v = struct.unpack('>f', b)[0]; u = struct.unpack('>I', b)[0]
    if not math.isfinite(v) or v == 0: return False
    ex = (u >> 23) & 0xff
    return 1e-3 <= abs(v) <= 1e5 and 100 <= ex <= 160 and (u & 0xfff) != 0


def main(argv):
    only_float = '--float' in argv; argv = [a for a in argv if a != '--float']
    source, name, xid, pc = argv[0], argv[1], int(argv[2]), argv[3]
    pid = int(argv[4]) if len(argv) > 4 else None
    xpaths = BASE if source == 'base' else [DLC_ROOT + p for p in PACKS if p.endswith('/%s.000' % source)]
    X = find(xpaths, 'be', 'xenon-w' + BS + name)
    x = [s for s in X if s['type'] == 7 and s['id'] == xid][0]
    if pc == 'pc':
        P = [dict(type=s['type'], id=s['id'], data=s['data']) for s in find(PC, 'le', 'pc-w' + BS + name)]
    else:
        P = [dict(type=s.type, id=s.id, data=s.data) for s in DW.read(open(pc, 'rb').read(), 'le').sections]
    cand = [s for s in P if s['type'] == 7 and (s['id'] == pid if pid is not None else len(s['data'] or b'') == len(x['data']))]
    if not cand: sys.exit('no PC DTP found (id %s, size %d)' % (pid, len(x['data'])))
    p = cand[0]
    xd, pd = x['data'], p['data']
    rl = R.parse(x['reloc'], 'be'); sl = {a for a, _ in rl.internal} | {o for _, o in rl.idref} | {o for _, o in rl.idref_a}
    st = collections.Counter()
    for o in range(0, min(len(xd), len(pd)) - 3, 4):
        w, q = xd[o:o + 4], pd[o:o + 4]
        if o in sl: st['reloc'] += 1; continue
        if only_float and not plaus(w): continue
        if q == w: st['same' if w == w[::-1] else 'raw'] += 1
        elif q == w[::-1]: st['s32'] += 1
        elif q == w[1::-1] + w[3:1:-1]: st['s16'] += 1
        else: st['other'] += 1
    n = sum(v for k, v in st.items() if k != 'reloc')
    print('%s %s Xbox DTP %d (%d bytes) vs PC DTP %d (%d bytes)%s' % (source, name, xid, len(xd), p['id'], len(pd),
          ' - plausible floats only' if only_float else ''))
    print('   words %d: ' % n + ', '.join('%s %d (%.1f %%)' % (k, st[k], 100.0 * st[k] / n if n else 0)
                                        for k in ('s32', 's16', 'raw', 'same', 'other')) + '; at relocations %d' % st['reloc'])


if __name__ == '__main__':
    main(sys.argv[1:])
