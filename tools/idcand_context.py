"""Side-by-side context of one candidate word in a DTP (type 7) of a converted PC DRM and its Xbox DLC original
(read-only). Night 04.11. (workspace docs Befund-Restrisiken-0411.md, task B): the 20 generic u16-pair candidates of
tools/objdata_idword_fix.py `scan` (Xbox 0x0000vvvv, PC 0xvvvv0000, v names a section) - which structure does the
word belong to, how did the converter treat its neighbours, what does section v hold.

Per candidate: the containing section (size, relocations), every internal pointer of the section whose target lies
within --back bytes before OFF (structure starts), the words OFF-back .. OFF+fwd as Xbox (BE) / PC (LE) with the
byte class (same / s32 = u32 swapped / s16 = u16 halves swapped / raw / other) and relocation marks, and the
sections of the PC file whose id is the candidate value v (type, size, first words).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/idcand_context.py PC.drm SECTION_ID OFF [--back 0x40] [--fwd 0x40] [--pack pack11]
        [--xbox XBOX.drm] [--out FILE]
  OFF hex; the Xbox original comes from --xbox (a big-endian DRM file) or convert_dlc.raw_dlc(name) (pack11 first,
  DLC 2; --pack pack10 for DLC 1)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import drm_reloc as R


def wclass(xb, pb):
    if pb == xb: return 'same' if xb == xb[::-1] else 'raw'
    if pb == xb[::-1]: return 's32'
    if pb == xb[1::-1] + xb[3:1:-1]: return 's16'
    return 'other'


def xbox_sections(name, pack, path):
    if path:
        return DW.read(open(path, 'rb').read(), 'be').sections
    import convert_dlc as CD
    old = os.environ.get('TRUDLC_PACK_FIRST')
    os.environ['TRUDLC_PACK_FIRST'] = pack
    try: raw, _ = CD.raw_dlc(name)
    finally:
        if old is None: os.environ.pop('TRUDLC_PACK_FIRST', None)
        else: os.environ['TRUDLC_PACK_FIRST'] = old
    if raw is None: sys.exit('no Xbox original for ' + name)
    return DW.read(raw, 'be').sections


def main(argv):
    def opt(n, d):
        if n in argv:
            k = argv.index(n); v = argv[k + 1]; del argv[k:k + 2]; return v
        return d
    back = int(opt('--back', '0x40'), 16); fwd = int(opt('--fwd', '0x40'), 16)
    pack = opt('--pack', 'pack11'); xpath = opt('--xbox', None); out = opt('--out', None)
    pc, sid, off = argv[0], int(argv[1]), int(argv[2], 16)
    P = DW.read(open(pc, 'rb').read(), 'le').sections
    X = xbox_sections(os.path.basename(pc), pack, xpath)
    L = []
    pcs = [s for s in P if s.type == 7 and s.id == sid]
    xs = [s for s in X if s.type == 7 and s.id == sid]
    if not pcs or not xs: sys.exit('section 7:%d missing (PC %d, Xbox %d copies)' % (sid, len(pcs), len(xs)))
    p, x = pcs[0], xs[0]
    rp = R.parse(bytes(p.reloc), 'le') if p.reloc else R.Reloc()
    rx = R.parse(bytes(x.reloc), 'be') if x.reloc else R.Reloc()
    ip = dict(rp.internal); ids = set(rp.id_offsets())
    L.append('%s 7:%d PC %d bytes / Xbox %d bytes; PC relocations: %d internal, %d external, %d id; Xbox %d internal'
             % (os.path.basename(pc), sid, len(p.data), len(x.data), len(rp.internal), len(rp.external),
                len(ids), len(rx.internal)))
    starts = sorted({t for o, t in rp.internal if off - back <= t <= off})
    L.append('internal pointers into [OFF-0x%x, OFF]: %s' % (back, ', '.join(
        '+0x%x (from %s)' % (t, ','.join('+0x%x' % o for o, tt in rp.internal if tt == t)) for t in starts) or '-'))
    for o in range(max(0, (off - back) & ~3), min(len(p.data), len(x.data), off + fwd), 4):
        xb, pb = bytes(x.data[o:o + 4]), bytes(p.data[o:o + 4])
        mark = ''
        if o in ip: mark = 'ptr -> +0x%x' % ip[o]
        elif o in ids: mark = 'id reloc'
        elif o in {so for _, so, _ in rp.external}: mark = 'external'
        tgt = [('<-ptr' if o in starts else '')]
        L.append('%s +0x%05x  X %s  PC %s  %-5s %s %s' % ('>>' if o == off else '  ', o, xb.hex(), pb.hex(),
                                                        wclass(xb, pb), mark, ' '.join(t for t in tgt if t)))
    v = struct.unpack_from('>I', x.data, off)[0]
    L.append('sections with id %d (0x%x) in the PC file:' % (v, v))
    for s in P:
        if s.id == v:
            d = bytes(s.data)
            L.append('  type %d id %d size %d first words %s' % (s.type, s.id, len(d), ' '.join(
                d[k:k + 4].hex() for k in range(0, min(len(d), 32), 4))))
    text = '\n'.join(L) + '\n'
    if out: open(out, 'w', encoding='utf-8').write(text)
    sys.stdout.write(text)


if __name__ == '__main__':
    main(sys.argv[1:])
