"""Survey of cinematic streams (cinstream .mul) read straight from a game archive (read-only).

Per stream: header (sample rate, total samples, duration, float word 14), block counts (audio / cine), the scene name
of cine block 0 (char[64] @0xc), the unit id of the first header record {U, 1, U, intro} mapped to its name through
objlist.dat of the same platform, and every subtitle tail {u32 len, UTF-8 text} found at the end of a cine block
(with the block index and time = index / 30 s). Format: see tools/mul_convert.py.
Question: the deleted "extended ending" of TRU (Amanda, rock slab) - which cinematic holds "Goodbye Mother".

Usage (from the repository root):
  ../bin/pyt -t 600 tools/cine_mul_info.py SOURCE NAME.mul [SPEC] [--subs] [--hexhead N]
    SOURCE: pcbig / pcpatch / xbase / xbase2 / tu / pack10 / pack11 (tools/locals.py)
    NAME: file name below cinstream\\ (e.g. 340_hel_endgame.mul); SPEC: hex spec word (default: ffffffe1 if present,
    else the last record); --subs: print every subtitle; --hexhead N: hex dump of the first N bytes of cine block 0;
    --ids A,B,..: count aligned u32 words equal to these decimal values (intro unique ids) in cine block 0;
    --strings N: ASCII strings of at least N characters in cine block 0 (actor / bone / object names)
  ../bin/pyt -t 600 tools/cine_mul_info.py SOURCE --hash HASH8 [SPEC] [--subs]    (an unnamed record by its hash)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC
from archive import Archive
from names import crc
import objlists as OL

LISTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic', 'lists')


def blocks(d, E):
    o = 0x800; out = []
    while o + 16 <= len(d):
        t, sz, a, b = struct.unpack_from(E + '4I', d, o)
        if o + 16 + sz > len(d): raise ValueError('bad block at %x' % o)
        out.append((t, a, b, d[o + 16:o + 16 + sz])); o += 16 + sz
    return out, o


def texty(b):
    b = b.rstrip(b'\0')
    if len(b) < 2: return False
    s = b.decode('utf-8', errors='replace')
    good = sum(ch.isprintable() or ch in '\r\n\t' for ch in s if ch != '�')
    return good >= 0.9 * len(s) and '\r' in s


def subtitle(p, E):
    """text of the {u32 len, text} subtitle tail of a cine block (endian E), or None"""
    for w in range(8, len(p) - 4, 4):
        L = struct.unpack_from(E + 'I', p, w)[0]
        e = w + 4 + L
        if 2 <= L and len(p) - 16 < e <= len(p) and not p[e:].strip(b'\0') and texty(p[w + 4:e]):
            return p[w + 4:e].rstrip(b'\0').decode('utf-8', errors='replace')
    return None


def unit_names(src):
    f = 'pc_objlist.dat' if src.startswith('pc') else ('xboxtu_objlist.dat' if src == 'tu' else 'xbox_objlist.dat')
    if src in ('pack10', 'pack11', 'pack1'): f = 'dlc_%s_objlist.dat' % src
    p = os.path.join(LISTS, f)
    if not os.path.exists(p): return {}
    recs, first = OL.read_objlist(open(p, 'rb').read(), 'le' if src.startswith('pc') else 'be')
    return {i + 1: n for i, (n, _) in enumerate(recs)}


def main(argv):
    subs = '--subs' in argv; argv = [a for a in argv if a != '--subs']
    hexhead = 0; strs = 0; ids = []
    if '--ids' in argv: k = argv.index('--ids'); ids = [int(x) for x in argv[k + 1].split(',')]; del argv[k:k + 2]
    if '--strings' in argv: k = argv.index('--strings'); strs = int(argv[k + 1]); del argv[k:k + 2]
    if '--hexhead' in argv: k = argv.index('--hexhead'); hexhead = int(argv[k + 1]); del argv[k:k + 2]
    src = argv[0]
    path, e, pre = LC.SRC[src]
    E = '>' if e == 'be' else '<'
    A = Archive(path, e)
    if argv[1] == '--hash':
        h = int(argv[2], 16); name = 'hash %08x' % h; rest = argv[3:]
    else:
        name = argv[1]; h = crc(pre + '\\cinstream\\' + name); rest = argv[2:]
    recs = A.find(h)
    if not recs: raise SystemExit('%s not in %s' % (name, src))
    print('%s %s: %d record(s), specs %s' % (src, name, len(recs), ' '.join('%08x' % r['spec'] for r in recs)))
    if rest: r = [x for x in recs if x['spec'] == int(rest[0], 16)][0]
    else: r = ([x for x in recs if x['spec'] == 0xffffffe1] or recs)[-1]
    d = A.read(r)
    W = struct.unpack_from(E + '16I', d, 0)
    fl = struct.unpack_from(E + '16f', d, 0)
    rate, total = W[0], W[2]
    print('spec %08x size %d  rate %d  total samples %d  -> %.2f s  channels %d  word14 %.3f word15 %.3f'
          % (r['spec'], len(d), rate, total, total / rate if rate else 0, W[3], fl[14], fl[15]))
    B, end = blocks(d, E)
    na = sum(1 for b in B if b[0] == 0); nc = sum(1 for b in B if b[0] == 1)
    other = sorted({b[0] for b in B} - {0, 1})
    print('blocks %d: audio %d, cine %d, other types %s; parsed to 0x%x of 0x%x  -> cine frames %d = %.2f s at 30 fps'
          % (len(B), na, nc, other, end, len(d), nc, (nc - 1) / 30.0))
    C = [b[3] for b in B if b[0] == 1]
    if C:
        p0 = C[0]
        scene = p0[0xc:0x4c].split(b'\0')[0].decode('latin1', errors='replace')
        w = struct.unpack_from(E + '4I', p0, 0x4c)
        un = unit_names(src)
        unit = ''
        if w[0] == w[2] and w[1] == 1: unit = 'unit id %d = %s, first intro id %d' % (w[0], un.get(w[0], '?'), w[3])
        print('cine block 0: %d bytes, scene name "%s"  %s' % (len(p0), scene, unit))
        if hexhead:
            for o in range(0, min(hexhead, len(p0)), 16): print('  %05x  %s' % (o, p0[o:o + 16].hex(' ')))
        if ids:
            for v in ids:
                n = sum(1 for o in range(0, len(p0) - 3, 4) if struct.unpack_from(E + 'I', p0, o)[0] == v)
                print('  u32 %d (0x%x): %d aligned occurrence(s) in cine block 0' % (v, v, n))
        if strs:
            import re
            for m in re.finditer(rb'[\x20-\x7e]{%d,}' % strs, p0):
                print('  str @0x%05x  %s' % (m.start(), m.group().decode('ascii')))
    st = [(i, subtitle(p, E)) for i, p in enumerate(C)]
    st = [(i, s) for i, s in st if s]
    print('subtitle tails: %d (first at frame %s, last at frame %s)' % (len(st), st[0][0] if st else '-', st[-1][0] if st else '-'))
    if subs:
        last = None
        for i, s in st:
            if s == last: continue
            last = s
            print('  frame %5d  %7.2f s  %s' % (i, i / 30.0, s.replace('\r', ' | ').replace('\n', ' ')))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
