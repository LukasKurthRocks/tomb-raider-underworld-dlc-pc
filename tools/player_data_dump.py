"""Player data block (object data `[inst+0x50]` = `[0xfad764]` on the PC), Xbox original vs converted PC file, word by
word (read-only; K-5b 10.11.2026: lock-on never engages in DLC 2 because tuning byte +0x294 reads 0 on the PC).

The block is the target of the relocated pointer at +0xc8 of the player object's DTP whose block holds the air maximum
(s16 at block +0xf8, default 4000; tools/objdata_idword_fix.py). doppelganger_casual: DTP 20212, lara: DTP 850 (PC) /
12647 (Xbox).

Per 4-byte word: Xbox bytes (big endian), PC bytes, and the byte permutation that turns the Xbox bytes into the PC
bytes:
  same     identical bytes (byte fields, or symmetric values)
  u32      reversed as one u32 / f32
  u16      each half reversed (u16 pair)
  raw      left in Xbox order (not equal to the others)
  ptr      both words are relocated pointers (internal / external): the targets are compared instead
  other    none of these (the PC holds other data)
  zero-pc  the Xbox word is non-zero, the PC word is 0 (data missing)
A word whose classes coincide (e.g. 0x00000000) is 'same'.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/player_data_dump.py XBOX.drm PC.drm [--from 0] [--to 0x700] [--diff] [--air 4000]
      --diff   print only words that are not 'same' / 'u32' / 'ptr' with the same target
  ../bin/pyt -t 300 tools/player_data_dump.py --one FILE.drm [--be] [--from ..] [--to ..]   one file, values only
  ../bin/pyt -t 300 tools/player_data_dump.py --sec FILE.drm ID[,ID..] [--be]   sections that carry these ids
  ../bin/pyt -t 300 tools/player_data_dump.py --twin XBOX.drm PC.drm BASE_XBOX.drm BASE_PC.drm [--diff]
      the DLC player block against the base player block (e.g. x_lara / pc_lara): per word the byte order the base
      pair proves (same / u32 / u16), the wanted PC bytes (the Xbox word in that order) and the verdict:
      ok, FAULT (PC is another byte order of the Xbox word), other (PC holds other bytes), ambig / ok? (the base
      word fits several orders that give different wanted words), base-other (the base pair is no byte order),
      ptr (a pointer slot on any side). Exit 1 when any FAULT.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def block(D, e, air=4000):
    """(section index, section, block offset, reloc) of the player data block, or None"""
    f = '>' if e == 'be' else '<'
    for k, s in enumerate(D.sections):
        if s.type != 7 or not s.reloc or len(s.data) < 0xcc: continue
        r = R.parse(bytes(s.reloc), e)
        t = dict(r.internal).get(0xc8)
        if t is None or t + 0xfa > len(s.data): continue
        if struct.unpack_from(f + 'h', s.data, t + 0xf8)[0] != air: continue
        return k, s, t, r
    return None


def ptrs(r):
    d = {o: ('int', t) for o, t in r.internal}
    d.update({o: ('ext', si, t) for si, o, t in r.external})
    return d


def cls(xb, pb):
    if xb == pb: return 'same'
    if pb == xb[::-1]: return 'u32'
    if pb == xb[1::-1] + xb[3:1:-1]: return 'u16'
    if pb == b'\0\0\0\0': return 'zero-pc'
    return 'other'


def load(path, e):
    return DW.read(open(path, 'rb').read(), e)


def compare(xpath, ppath, lo=0, hi=0x700, air=4000):
    """[(off, xbytes, pbytes, class, note)] for the block words lo..hi, plus a header line"""
    XD, PD = load(xpath, 'be'), load(ppath, 'le')
    bx, bp = block(XD, 'be', air), block(PD, 'le', air)
    if bx is None or bp is None:
        raise SystemExit('no player data block: Xbox %s, PC %s' % (bx is not None, bp is not None))
    kx, sx, tx, rx = bx
    kp, sp, tp, rp = bp
    px, pp = ptrs(rx), ptrs(rp)
    head = 'Xbox %s section %d DTP %d block +0x%x | PC %s section %d DTP %d block +0x%x' % (
        os.path.basename(xpath), kx, sx.id, tx, os.path.basename(ppath), kp, sp.id, tp)
    out = []
    for o in range(lo, hi, 4):
        ax, ap = tx + o, tp + o
        if ax + 4 > len(sx.data) or ap + 4 > len(sp.data): break
        xb, pb = bytes(sx.data[ax:ax + 4]), bytes(sp.data[ap:ap + 4])
        note = ''
        if ax in px or ap in pp:
            qx, qp = px.get(ax), pp.get(ap)
            c = 'ptr'
            if qx is None or qp is None:
                c, note = 'other', 'pointer only on %s' % ('Xbox' if qp is None else 'PC')
            else:
                rel_x = qx[-1] - tx if qx[0] == 'int' else None
                rel_p = qp[-1] - tp if qp[0] == 'int' else None
                note = 'X %s P %s' % (qx, qp)
                if qx[0] == 'int' and qp[0] == 'int' and rel_x != rel_p:
                    note += ' (block-relative X %+#x P %+#x)' % (rel_x, rel_p)
        else:
            c = cls(xb, pb)
        out.append((o, xb, pb, c, note))
    return head, out


# byte orders: same (u8 x4 / raw), u32 (one u32 / f32), u16 (u16 pair), b2s16 {u8, u8, u16}, s16b2 {u16, u8, u8}
PERMS = {'same': (0, 1, 2, 3), 'u32': (3, 2, 1, 0), 'u16': (1, 0, 3, 2), 'b2s16': (0, 1, 3, 2), 's16b2': (1, 0, 2, 3)}


def perms_of(xb, pb):
    """every named byte order that turns xb into pb"""
    return {n for n, p in PERMS.items() if bytes(xb[i] for i in p) == pb}


def block_end(s, t, r):
    """end of the block: the first internal relocation target above t (the next record), else the section end"""
    cand = [b for _, b in r.internal if b > t]
    return min(cand) if cand else len(s.data)


def twin(xpath, ppath, bxpath, bppath, air=4000):
    """DLC player block vs the base player block (same struct): per word the byte order the base pair proves, the
    wanted PC bytes and the verdict. Returns (head, rows [(off, X, P, wanted or None, verdict, base orders)])"""
    D = {k: load(p, e) for k, p, e in (('x', xpath, 'be'), ('p', ppath, 'le'), ('bx', bxpath, 'be'),
                                        ('bp', bppath, 'le'))}
    B = {k: block(D[k], 'be' if k in ('x', 'bx') else 'le', air) for k in D}
    for k, v in B.items():
        if v is None: raise SystemExit('no player data block in %s' % k)
    ends = {k: block_end(v[1], v[2], v[3]) - v[2] for k, v in B.items()}
    n = min(ends.values())
    P = {k: ptrs(v[3]) for k, v in B.items()}
    head = 'block lengths %s -> compare 0..0x%x' % (', '.join('%s 0x%x' % kv for kv in sorted(ends.items())), n)
    rows = []
    for o in range(0, n - 3, 4):
        w = {k: bytes(v[1].data[v[2] + o:v[2] + o + 4]) for k, v in B.items()}
        bw = '%s->%s' % (w['bx'].hex(), w['bp'].hex())
        isptr = [k for k in B if B[k][2] + o in P[k]]
        if isptr:
            rows.append((o, w['x'], w['p'], None, 'ptr' if len(isptr) == 4 else 'ptr-%s' % '+'.join(isptr), bw))
            continue
        base = perms_of(w['bx'], w['bp'])
        if not base:
            rows.append((o, w['x'], w['p'], None, 'base-other', bw)); continue
        wants = {bytes(w['x'][i] for i in PERMS[b]) for b in base}
        dlc = perms_of(w['x'], w['p'])
        bw = '/'.join(sorted(base)) + ' ' + bw
        if len(wants) != 1:
            v = 'ok?' if w['p'] in wants else ('ambig' if dlc else 'ambig-other')
            rows.append((o, w['x'], w['p'], None, v, bw)); continue
        want = next(iter(wants))
        if w['p'] == want: v = 'ok'
        elif dlc: v = 'FAULT'
        else: v = 'other'
        rows.append((o, w['x'], w['p'], want, v, bw))
    return head, rows


def fmt(o, xb, pb, c, note):
    xf = struct.unpack('>f', xb)[0]; pf = struct.unpack('<f', pb)[0]
    return '+0x%03x  X %s (%11.4g) | P %s (%11.4g)  %-7s %s' % (o, xb.hex(), xf, pb.hex(), pf, c, note)


def main(argv):
    lo, hi, air = 0, 0x700, 4000
    def opt(name, conv=lambda v: int(v, 0)):
        if name in argv:
            k = argv.index(name); v = conv(argv[k + 1]); del argv[k:k + 2]; return v
        return None
    v = opt('--from'); lo = lo if v is None else v
    v = opt('--to'); hi = hi if v is None else v
    v = opt('--air', int); air = air if v is None else v
    diff = '--diff' in argv; argv = [a for a in argv if a != '--diff']
    if argv and argv[0] == '--sec':
        be = '--be' in argv; argv = [a for a in argv[1:] if a != '--be']
        D = load(argv[0], 'be' if be else 'le')
        want = [int(v, 0) for v in argv[1].split(',')]
        for i in want:
            hit = [(k, s.type, len(s.data)) for k, s in enumerate(D.sections) if s.id == i]
            print('id %d (0x%x): %s' % (i, i, ', '.join('section %d type %d size %d' % h for h in hit) or 'no section'))
        return 0
    if argv and argv[0] == '--twin':
        head, rows = twin(*argv[1:5], air=air)
        print(head)
        n = {}
        for o, xb, pb, want, v, base in rows:
            n[v] = n.get(v, 0) + 1
            if diff and v in ('ok', 'ptr'): continue
            print('+0x%03x  X %s  P %s  want %s  base %-30s %s' % (o, xb.hex(), pb.hex(), want.hex() if want else '-',
                                                                  base, v))
        print('verdicts: ' + ', '.join('%s %d' % kv for kv in sorted(n.items())))
        return 1 if n.get('FAULT') else 0
    if argv and argv[0] == '--one':
        be = '--be' in argv; argv = [a for a in argv[1:] if a != '--be']
        e = 'be' if be else 'le'; f = '>' if be else '<'
        D = load(argv[0], e)
        b = block(D, e, air)
        if b is None: raise SystemExit('no player data block in %s' % argv[0])
        k, s, t, r = b
        pp = ptrs(r)
        print('%s section %d DTP %d block +0x%x (%s)' % (os.path.basename(argv[0]), k, s.id, t, e))
        for o in range(lo, hi, 4):
            a = t + o
            if a + 4 > len(s.data): break
            w = bytes(s.data[a:a + 4])
            print('+0x%03x  %s  u32 %10d  f32 %11.4g  %s' % (o, w.hex(), struct.unpack(f + 'I', w)[0],
                                                       struct.unpack(f + 'f', w)[0], pp.get(a, '')))
        return 0
    if len(argv) < 2:
        print(__doc__); return 2
    head, rows = compare(argv[0], argv[1], lo, hi, air)
    print(head)
    n = {}
    for row in rows:
        n[row[3]] = n.get(row[3], 0) + 1
        if diff and row[3] in ('same', 'u32') or (diff and row[3] == 'ptr' and '(block' not in row[4]): continue
        print(fmt(*row))
    print('classes: ' + ', '.join('%s %d' % kv for kv in sorted(n.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
