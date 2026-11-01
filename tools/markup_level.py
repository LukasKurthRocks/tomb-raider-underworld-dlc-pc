"""List the unit markup records of a level DRM (read-only; DLC 2 rock vein, 607 / 608 ctx 0, 2026-11-01).

The PC adds a unit's markup at tru+0x5d21b4 .. +0x5d21c5: header = [level+0] (level = section 0, the unit's Level
struct), count = [header+8], records = [header+0xc], stride 0x5c, loop tru+0x5ce4f0 (+0x28 runtime flags, 0 in the
file -> flags from the type char at +0x33 via TRMarkupManager vtable +0x1c (tru+0x5d6f90) | +0x20 (tru+0x5d70a0);
+0x2e id (s16), +0x32 byte (1 = skip in the query), +0x58 pointer to the poly line {int count; points at +0x10}).
This tool follows section 0 +0 -> header, header +0xc -> records (relocations), and prints each record: id, type char,
+0x28, +0x30..+0x33 bytes, position +0x34 (3 floats), poly line point count and first / last point.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/markup_level.py FILE.drm [--be] [--raw]
  --be   big-endian (Xbox) DRM, e.g. work/rockvein/dlc_level2_start_xbox.drm or a pack11 original
  --raw  also print the 23 words of every record
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

STRIDE = 0x5c


def target(D, rel, si, o):
    """(section index, offset) a relocated word at section si offset o points to, or None"""
    r = rel[si]
    if o in r[0]: return si, r[0][o]
    if o in r[1]: return r[1][o]
    return None


def main(argv):
    be = '--be' in argv
    raw = '--raw' in argv
    find = '--find' in argv
    scan = '--scan' in argv
    brute = '--brute' in argv
    objects = '--objects' in argv
    xbox = None
    if '--xbox' in argv: k = argv.index('--xbox'); xbox = argv[k + 1]; del argv[k:k + 2]
    level = obj = None
    if '--object' in argv: k = argv.index('--object'); obj = int(argv[k + 1]); del argv[k:k + 2]
    if '--level' in argv: k = argv.index('--level'); level = int(argv[k + 1]); del argv[k:k + 2]
    argv = [a for a in argv if not a.startswith('--')]
    e = 'be' if be else 'le'; f = '>' if be else '<'
    D = DW.read(open(argv[0], 'rb').read(), e)
    rel = []
    for s in D.sections:
        r = R.parse(bytes(s.reloc), e)
        rel.append((dict(r.internal), {o: (xi, t) for xi, o, t in r.external}))
    if objects:                                 # every DTP with an object markup array; with --xbox X.drm compare
        X = XR = None
        if xbox:
            X = DW.read(open(xbox, 'rb').read(), 'be')
            XR = []
            for s in X.sections:
                r = R.parse(bytes(s.reloc), 'be')
                XR.append((dict(r.internal), {o: (xi, t) for xi, o, t in r.external}))
        for si, s in enumerate(D.sections):
            d = bytes(s.data)
            if s.type != 7 or len(d) < 0x5c: continue
            t = target(D, rel, si, 0x58)
            n = struct.unpack_from(f + 'I', d, 0x54)[0]
            if t is None or t[0] != si or not 1 <= n <= 1000 or t[1] + n * STRIDE > len(d): continue
            ro = t[1]
            if not all(struct.unpack_from(f + 'I', d, ro + k * STRIDE + 0x28)[0] == 0 for k in range(n)): continue
            tc = collections.Counter(d[ro + k * STRIDE + 0x33] for k in range(n))
            line = 'dtp %d: %d markup records at +0x%x, types %s' % (s.id, n, ro, ', '.join(
                '%d: %d' % kv for kv in sorted(tc.items())))
            if X is not None:
                xi = next((i for i, xs in enumerate(X.sections) if xs.type == 7 and xs.id == s.id), None)
                if xi is None:      # base pairs carry other ids: the Xbox DTP whose +0x54 / +0x58 give the same array
                    for i, xs in enumerate(X.sections):
                        xd = bytes(xs.data)
                        if xs.type != 7 or len(xd) < 0x5c or len(xd) != len(d): continue
                        xt = target(X, XR, i, 0x58)
                        if xt and xt[0] == i and xt[1] == ro and struct.unpack_from('>I', xd, 0x54)[0] == n:
                            xi = i; line += '  (Xbox dtp %d)' % xs.id; break
                if xi is None:
                    line += '  (no Xbox section)'
                else:
                    xd = bytes(X.sections[xi].data)
                    bad = collections.Counter()
                    for k in range(n):
                        o = ro + k * STRIDE
                        for w in range(0, 0x58, 4):
                            xw, pw = xd[o + w:o + w + 4], d[o + w:o + w + 4]
                            if w == 0x2c:   # u16 +0x2c, u16 id +0x2e (read as a word by tru+0x5ce569)
                                good = xw[0:2] == pw[0:2][::-1] and xw[2:4] == pw[2:4][::-1]
                            elif w == 0x30:  # u16 +0x30, byte +0x32 (tested by tru+0x5ce44a), type char +0x33
                                good = xw[0:2] == pw[0:2][::-1] and xw[2:4] == pw[2:4]
                            else:           # floats / dwords
                                good = xw == pw[::-1]
                            if not good: bad['+%x' % w] += 1
                    line += '  Xbox diff words: %s' % (', '.join('%s x%d' % kv for kv in sorted(bad.items())) or 'none')
            print(line)
            if raw or 22 in tc or 23 in tc:
                for k in range(n):
                    o = ro + k * STRIDE
                    if d[o + 0x33] in (22, 23) or raw:
                        print('   #%d +0x%x id %d type %d pos (%.0f %.0f %.0f)' % ((k, o, struct.unpack_from(
                            f + 'h', d, o + 0x2e)[0], d[o + 0x33]) + struct.unpack_from(f + '3f', d, o + 0x34)))
        return
    if brute:                                   # runs of >= 3 records at stride 0x5c: +0x28 == 0, type 1..30, sane position
        def ok(d, r0):
            if r0 < 0 or r0 + STRIDE > len(d): return False
            if struct.unpack_from(f + 'I', d, r0 + 0x28)[0] != 0: return False
            if not 1 <= d[r0 + 0x33] <= 30: return False
            p = struct.unpack_from(f + '3f', d, r0 + 0x34)
            return all(v == v and abs(v) < 1e5 for v in p) and any(abs(v) > 1.0 for v in p)
        for si, s in enumerate(D.sections):
            d = bytes(s.data)
            o = 0
            while o + STRIDE <= len(d):
                if ok(d, o) and ok(d, o + STRIDE) and ok(d, o + 2 * STRIDE):
                    n = 0
                    while ok(d, o + n * STRIDE): n += 1
                    tc = collections.Counter(d[o + k * STRIDE + 0x33] for k in range(n))
                    print('section %d type %d id %d: run at +0x%x, %d records, types %s' % (
                        si, s.type, s.id, o, n, ', '.join('%d: %d' % kv for kv in sorted(tc.items()))))
                    o += n * STRIDE
                else:
                    o += 4
        return
    if scan:                                    # records found by their relocated poly-line pointer at +0x58
        for si, s in enumerate(D.sections):
            d = bytes(s.data)
            hits = []
            for o in sorted(set(rel[si][0]) | set(rel[si][1])):
                r0 = o - 0x58
                if r0 < 0 or r0 + STRIDE > len(d): continue
                typ = d[r0 + 0x33]
                pos = struct.unpack_from(f + '3f', d, r0 + 0x34)
                if not (1 <= typ <= 40) or not all(abs(v) < 1e6 for v in pos) or pos == (0.0, 0.0, 0.0): continue
                pl = target(D, rel, si, o)
                pd = bytes(D.sections[pl[0]].data)
                if pl[1] + 4 > len(pd): continue
                cnt = struct.unpack_from(f + 'i', pd, pl[1])[0]
                if not (1 <= cnt <= 512): continue
                hits.append((r0, typ, struct.unpack_from(f + 'h', d, r0 + 0x2e)[0], pos, cnt))
            if not hits: continue
            tc = collections.Counter(h[1] for h in hits)
            print('section %d type %d id %d size 0x%x: %d candidate records, types %s' % (
                si, s.type, s.id, len(d), len(hits), ', '.join('%d: %d' % kv for kv in sorted(tc.items()))))
            for r0, typ, rid, pos, cnt in hits:
                if raw or typ in (22, 23):
                    print('   +0x%05x id %5d type %2d pos (%.1f %.1f %.1f) poly %d' % (r0, rid, typ, pos[0], pos[1], pos[2], cnt))
        return
    if find:                                    # sections shaped like the level struct: +8 count, +0xc / +0x20 relocated
        for si, s in enumerate(D.sections):
            d = bytes(s.data)
            if len(d) < 0x24: continue
            if target(D, rel, si, 0xc) and target(D, rel, si, 0x20):
                n = struct.unpack_from(f + 'I', d, 8)[0]
                print('section %d type %d id %d size 0x%x: +8 = %d, +0xc -> %s, +0x20 -> %s' % (
                    si, s.type, s.id, len(d), n, target(D, rel, si, 0xc), target(D, rel, si, 0x20)))
        return
    if obj is not None:                         # object markup: count [data+0x54], records [data+0x58] (tru+0x5d0656)
        si = next(i for i, s in enumerate(D.sections) if s.id == obj and s.type == 7)
        n = struct.unpack_from(f + 'I', bytes(D.sections[si].data), 0x54)[0]
        t = target(D, rel, si, 0x58)
        print('object data section %d (dtp %d): +0x54 count %d, +0x58 -> %s' % (si, obj, n, t))
        if t is None: return
        h = None
        rs, ro = t
    elif level is not None:
        h = (level, 0)
    else:
        h = target(D, rel, 0, 0)
    if obj is None:
        if h is None:
            print('section 0 +0 is not relocated - no level header'); return
        hs, ho = h
        hd = bytes(D.sections[hs].data)
        words = [struct.unpack_from(f + 'I', hd, ho + 4 * i)[0] for i in range(min(6, (len(hd) - ho) // 4))]
        print('level header: section %d +0x%x, words %s' % (hs, ho, ' '.join('%08x' % w for w in words)))
        for k in range(0, min(len(hd) - ho, 0x18), 4):
            t = target(D, rel, hs, ho + k)
            if t: print('  header +0x%02x -> section %d (type %d id %d, size 0x%x) +0x%x' % (
                k, t[0], D.sections[t[0]].type, D.sections[t[0]].id, len(D.sections[t[0]].data), t[1]))
        n = words[2]
        t = target(D, rel, hs, ho + 0xc)
        if t is None:
            print('header +0xc not relocated (count %d)' % n); return
        rs, ro = t
    rd = bytes(D.sections[rs].data)
    print('records: %d x 0x%x at section %d +0x%x (section size 0x%x)' % (n, STRIDE, rs, ro, len(rd)))
    types = collections.Counter()
    for i in range(n):
        o = ro + i * STRIDE
        if o + STRIDE > len(rd):
            print('  record %d past the section end' % i); break
        w28 = struct.unpack_from(f + 'I', rd, o + 0x28)[0]
        rid = struct.unpack_from(f + 'h', rd, o + 0x2e)[0]
        b30 = rd[o + 0x30:o + 0x34]
        pos = struct.unpack_from(f + '3f', rd, o + 0x34)
        typ = struct.unpack_from('b', rd, o + 0x33)[0]
        types[typ] += 1
        pl = target(D, rel, rs, o + 0x58)
        pls = '-'
        if pl:
            pd = bytes(D.sections[pl[0]].data)
            cnt = struct.unpack_from(f + 'i', pd, pl[1])[0]
            pts = []
            for j in (0, cnt - 1) if cnt > 0 else ():
                po = pl[1] + 0x10 + 16 * j
                if po + 12 <= len(pd): pts.append('(%.0f %.0f %.0f)' % struct.unpack_from(f + '3f', pd, po))
            pls = 'poly sec %d +0x%x n %d %s' % (pl[0], pl[1], cnt, ' .. '.join(pts))
        relw = [k for k in range(0, STRIDE, 4) if target(D, rel, rs, o + k)]
        print('  #%3d +0x%05x id %5d type %3d  +28 %08x  +30 %s  pos (%.1f %.1f %.1f)  %s  reloc %s' % (
            i, o, rid, typ, w28, b30.hex(), pos[0], pos[1], pos[2], pls, ','.join('+%x' % k for k in relw)))
        if raw:
            print('       ' + ' '.join('%08x' % struct.unpack_from(f + 'I', rd, o + k)[0] for k in range(0, STRIDE, 4)))
    print('type counts: ' + ', '.join('%d: %d' % kv for kv in sorted(types.items())))


if __name__ == '__main__':
    main(sys.argv[1:])
