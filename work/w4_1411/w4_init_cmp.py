"""W4 (2026-11-14): member init words of one DLC script in the own tree, the old tree and the Xbox DLC original, read-only.

Usage (from the repository root):
  ../bin/pyt -t 600 work/w4_1411/w4_init_cmp.py UNIT.drm SID[,SID..] OWN_DIR OLD_DIR
  UNIT.drm is read from OWN_DIR and OLD_DIR (PC, little endian) and as dlc:UNIT.drm (pack10, big endian).
Per member with an init value (walked in the own file): kind, name Symbol, tag, userType, then every non-pointer leaf
word: path, offset, own / old / Xbox bytes, and for the {u16, u16} reading of each word the two halves (own / old in
LE, Xbox in BE). Exit code 0.
"""
import sys, os, struct
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import drm_write as DW, drm_reloc as R, script_conv as SC
import script_init_from_pc as I
import script_func_list as FL


def sec(path, sid):
    D = DW.read(open(path, 'rb').read(), 'le')
    return next((x for x in D.sections if x.type == 8 and x.id == sid), None)


def main(argv):
    unit, sids, own, old = argv[0], [int(v) for v in argv[1].split(',')], argv[2], argv[3]
    S, e = FL.sections('dlc:' + unit)
    for sid in sids:
        so = sec(os.path.join(own, unit), sid); sd = sec(os.path.join(old, unit), sid)
        xb = next((q[2] for q in S if q[0] == 8 and q[1] == sid), None)
        print('== %s script %d: own %s old %s xbox %s' % (unit, sid, len(so.data) if so else None,
              len(sd.data) if sd else None, len(xb) if xb else None))
        if so is None: continue
        ra = R.parse(so.reloc, 'le'); w = SC.Walk(so.data, ra, 'le'); w.run(); it = dict(ra.internal)
        for key, L in I.members(w, so.data, 'le').items():
            for a in L:
                ia = it.get(a + 16)
                if ia is None: continue
                print('%s name %d tag 0x%x ut %d (entry 0x%x, init 0x%x)' % (key[0], key[1], key[2], key[3], a, ia))
                for path, o in I.leaves(w, it, ia):
                    wo = bytes(so.data[o:o + 4])
                    wd = bytes(sd.data[o:o + 4]) if sd and o + 4 <= len(sd.data) else b''
                    wx = bytes(xb[o:o + 4]) if xb and o + 4 <= len(xb) else b''
                    h = lambda b, E: '%5d:%-5d' % struct.unpack(E + 'HH', b) if len(b) == 4 else '-'
                    print('   %-12s 0x%04x own %s (%s) old %s (%s) xbox %s (%s)%s' % (
                        '.'.join(str(v) for v in path), o, wo.hex(), h(wo, '<'), wd.hex(), h(wd, '<'), wx.hex(),
                        h(wx, '>'), '' if h(wo, '<') == h(wx, '>') else '  <-- own != xbox (u16 pair)'))
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 5: sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
