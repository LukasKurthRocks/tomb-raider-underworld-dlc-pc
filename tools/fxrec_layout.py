"""Record stride of the 'table record' DTPs (rule R3 of tools/dlc_idpair_fix.py) on Xbox vs PC - read-only.

Night 04.11. (workspace docs Befund-Restrisiken-0411.md, task B): DTP head +0x34 = u16 count n, +0x38 = pointer P to
n records (Xbox stride 0x24; record +0x04 colour, +0x14 id of a 12736-byte table DTP). In Crystal's own PC base-game
files the second record sits 4 bytes later than on the Xbox (fx_torch_med_kraken_room_sml_ist, fx_goo_hel_pool_ist):
the PC layout differs. This tool measures, per DTP and record k, at which PC offset the Xbox record's words reappear
(as same / s32 / s16 / raw permutations): it tries PC shifts 0, 4, 8, 12 for every record and prints the best one.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/fxrec_layout.py basepair NAME [NAME ...]      Xbox base vs Crystal's PC
  ../bin/pyt -t 900 tools/fxrec_layout.py dlc PC.drm [--pack pack11]     Xbox DLC original vs the converted PC file
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


CLASSES = collections.defaultdict(collections.Counter)    # record field offset -> byte classes seen
EXTRA = collections.Counter()                             # PC word at record +0x24 (the 4 extra PC bytes)
# field layouts as byte permutations (PC byte i = Xbox byte pm[i]), as tools/soundplex_nodes.py
PERMS = {'u32': (3, 2, 1, 0), 'u16u16': (1, 0, 3, 2), 'u8u8u16': (0, 1, 3, 2), 'u16u8u8': (1, 0, 2, 3),
         'u8x4': (0, 1, 2, 3)}
FITS = collections.defaultdict(list)                      # record field offset -> [set of layouts that fit]


def perm(xb, pb):
    return pb in (xb, xb[::-1], xb[1::-1] + xb[3:1:-1])


def records(x):
    it = dict(R.parse(bytes(x.reloc), 'be').internal) if x.reloc else {}
    d = x.data
    if len(d) < 0x3c or 0x38 not in it: return None
    n = struct.unpack_from('>H', d, 0x34)[0]; p = it[0x38]
    if not (0 < n <= 64 and p + 0x24 * n <= len(d)): return None
    return n, p


def measure(XD, PD, label):
    import converter_faults_fix as CF
    out = collections.Counter()
    for k, x, p in CF.pairs_by_position(XD, PD):
        if x.type != 7 or p.type != 7 or len(x.data) != len(p.data): continue
        r = records(x)
        if not r: continue
        n, ptr = r
        row = []
        for j in range(n):
            xo = ptr + 0x24 * j
            best = None
            for sh in (0, 4, 8, 12):
                po = xo + sh
                if po + 0x24 > len(p.data): continue
                sc = sum(1 for w in range(0, 0x24, 4) if x.data[xo + w:xo + w + 4] != b'\0\0\0\0'
                         and perm(x.data[xo + w:xo + w + 4], p.data[po + w:po + w + 4]))
                nz = sum(1 for w in range(0, 0x24, 4) if x.data[xo + w:xo + w + 4] != b'\0\0\0\0')
                if best is None or sc > best[1]: best = (sh, sc, nz)
            row.append('r%d +%d (%d/%d)' % (j, best[0], best[1], best[2]))
            out['record shift +%d' % best[0]] += 1
            po = xo + best[0]
            for w in range(0, 0x24, 4):       # byte class per field (Xbox word -> PC word at the found place)
                xb, pb = x.data[xo + w:xo + w + 4], p.data[po + w:po + w + 4]
                if xb == b'\0\0\0\0': continue
                c = ('same' if xb == xb[::-1] else 'raw') if pb == xb else 's32' if pb == xb[::-1] else \
                    's16' if pb == xb[1::-1] + xb[3:1:-1] else 'other'
                CLASSES[w][c] += 1
                ok = {nm for nm, pm in PERMS.items() if bytes(xb[i] for i in pm) == pb}
                FITS[w].append(ok)
                if 'u16u16' not in ok and 'u8u8u16' in ok and w == 8:
                    print('    evidence u8u8u16 at +0x08: %s 7:%d record %d Xbox %s -> PC %s' % (
                        label, x.id, j, xb.hex(), pb.hex()))
            if best[0] == 4 * j and po + 0x28 <= len(p.data):
                EXTRA[p.data[po + 0x24:po + 0x28].hex()] += 1
        print('%s 7:%d / PC 7:%d n=%d ptr +0x%x: %s' % (label, x.id, p.id, n, ptr, ', '.join(row)))
    return out


def main(argv):
    if len(argv) < 2: sys.exit(__doc__)
    tot = collections.Counter()
    if argv[0] == 'basepair':
        import dtp_word_classes as C
        mk = lambda secs: DW.Drm([DW.Section(s['type'], s['id'], s['data'] or b'', s['reloc'] or b'') for s in secs])
        for name in argv[1:]:
            X = C.find(C.BASE, 'be', 'xenon-w' + C.BS + name); P = C.find(C.PC, 'le', 'pc-w' + C.BS + name)
            if X is None or P is None: print('%s: no base pair' % name); continue
            tot.update(measure(mk(X), mk(P), name))
    elif argv[0] == 'scan':                # every DRM of a mods folder that has an Xbox DLC original
        pack = argv[argv.index('--pack') + 1] if '--pack' in argv else 'pack11'
        import dlc_idpair_fix as F
        for dp, dn, fn in os.walk(argv[1]):
            for f in sorted(fn):
                if not f.lower().endswith('.drm'): continue
                try: XD = F.xbox_doc(f, pack, None)
                except Exception: XD = None
                if XD is None: continue
                tot.update(measure(XD, DW.read(open(os.path.join(dp, f), 'rb').read(), 'le'), f))
    elif argv[0] == 'dlc':
        pack = argv[argv.index('--pack') + 1] if '--pack' in argv else 'pack11'
        import dlc_idpair_fix as F
        XD = F.xbox_doc(os.path.basename(argv[1]), pack, None)
        PD = DW.read(open(argv[1], 'rb').read(), 'le')
        tot.update(measure(XD, PD, os.path.basename(argv[1])))
    print('total: %s' % dict(tot))
    for w in sorted(CLASSES):
        fits = FITS[w]; allok = set(PERMS)
        for s in fits:
            if s: allok &= s
        print('  record +0x%02x: %s; layouts that fit every sample: %s (%d samples, %d fit none)' % (
            w, dict(CLASSES[w]), sorted(allok) if any(fits) else '-', len(fits), sum(1 for s in fits if not s)))
    print('  PC record +0x24 (extra word, records at the +4k place): %s' % dict(EXTRA))


if __name__ == '__main__':
    main(sys.argv[1:])
