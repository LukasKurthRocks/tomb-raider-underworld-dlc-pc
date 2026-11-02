"""Scan converted DTP sections for words the converter left RAW (PC bytes == Xbox bytes) although they hold a small
integer that names a section of the file (read-only; test 50e/50f: the id words of event sub 0x32 and of effect node
type 1 were left raw / u16-swapped). Pointer and id-relocation fields are skipped.

A word is reported when: PC 4 bytes == Xbox 4 bytes, the Xbox big-endian u32 v is 0 < v < 0x10000, v is the id of a
section of the PC file, and the bytes are not byte-order invariant. Also reported (class u16): PC bytes == the Xbox
bytes with each u16 swapped AND the Xbox u32 names a section while the PC u32 does not - candidates only, each needs its
reader in tru.exe before a fix (a genuine {u16 0, u16 x} pair looks the same).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/dtp_raw_id_scan.py tree DIR [DIR ..]        PC .drm files vs dlc_drms.pkl (sections by id)
  ../bin/pyt -t 600 tools/dtp_raw_id_scan.py pair XBOX.drm PC.drm
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def scan(SP, SX, label):
    ids = {s.id for s in SP}
    xs = {(s.type, s.id): s for s in SX}
    cnt = collections.Counter()
    for p in SP:
        if p.type != 7: continue
        x = xs.get((7, p.id))
        if x is None or len(x.data) != len(p.data): continue
        rel = R.parse(p.reloc, 'le')
        skip = set(rel.pointer_offsets()) | set(rel.id_offsets())
        for o in range(0, len(p.data) - 3, 4):
            if o in skip: continue
            pb, xb = p.data[o:o + 4], x.data[o:o + 4]
            v = struct.unpack('>I', xb)[0]
            if not (0 < v < 0x10000) or v not in ids: continue
            pv = struct.unpack('<I', pb)[0]
            if pv == v: continue
            if pb == xb and xb != xb[::-1]:
                cnt['raw'] += 1
                print('%s7:%-6d +0x%04x raw  PC 0x%08x Xbox 0x%08x (id %d)' % (label, p.id, o, pv, v, v))
            elif pb == xb[1::-1] + xb[3:1:-1] and pv not in ids:
                cnt['u16'] += 1
                print('%s7:%-6d +0x%04x u16  PC 0x%08x Xbox 0x%08x (id %d?)' % (label, p.id, o, pv, v, v))
    return cnt


def main(argv):
    if len(argv) < 2: print(__doc__); return 2
    if argv[0] == 'pair':
        DX = DW.read(open(argv[1], 'rb').read(), 'be'); DP = DW.read(open(argv[2], 'rb').read(), 'le')
        print(dict(scan(DP.sections, DX.sections, ''))); return 0
    import pickle
    W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic', 'dlc_drms.pkl')
    C = pickle.load(open(W, 'rb'))
    base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
    byname = {}
    for k, v in C.items(): byname.setdefault(base(k[1]), []).append(v)
    tot = collections.Counter()
    for top in argv[1:]:
        for dp, dn, fn in os.walk(top):
            for f in sorted(fn):
                if not f.lower().endswith('.drm') or base(f) not in byname: continue
                DP = DW.read(open(os.path.join(dp, f), 'rb').read(), 'le')
                h, secs = byname[base(f)][0]
                SX = [DW.Section(s['type'], s['id'], s['data'], s['reloc'], s['flags'], s['ver'], s['spec'])
                      for s in secs if s['type'] == 7]
                c = scan(DP.sections, SX, f + ' ')
                if c: print('%s: %s' % (f, dict(c)))
                tot.update(c)
    print('total: %s' % dict(tot))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
