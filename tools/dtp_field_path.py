"""Where does a word of a DTP live: its block (relocation target <= offset), the pointer chain from the DTP root to
that block, and the same field in the sibling blocks (read-only; finisher / thrall analysis 2026-11-05: which struct
holds the thrall float words that the converter wrote as u16 pairs, and how the converter wrote the same field in the
other records of the same array).

A block = from one internal relocation target up to the next. The chain goes from the block start to the words that
point at it (internal pointers), then their blocks, until a block nobody points at (normally the DTP start). Sibling
blocks = the blocks pointed at by the neighbouring words of the same pointer array (consecutive pointer words in the
referring block). For every sibling the word at the same block offset is printed Xbox / PC with its conversion class
(u32 = byte-reversed, u16pair = halves reversed, raw = unchanged) - the field type evidence of an array of records.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/dtp_field_path.py XBOX_NAME PC.drm DTP OFF[,OFF..] [--siblings N] [--words N]
    XBOX_NAME: DRM name in the Xbox archives or a file (as tools/tuning_word_audit.py)
    --siblings N  how many pointer words before / after the referring word count as the array (default 64)
    --words N     words of the block to print around the field (default 0 = none)
"""
import sys, os, struct, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import tuning_word_audit as TA


def cls(xw, pw):
    if xw[::-1] == pw: return 'u32'
    if xw[1::-1] + xw[:1:-1] == pw: return 'u16pair'
    if xw == pw: return 'raw'
    return 'other'


def fval(b, e):
    v = struct.unpack(e + 'f', b)[0]
    return '%.6g' % v if math.isfinite(v) else 'nan'


def section(secs, sid):
    for s in secs:
        if s['type'] == 7 and s['id'] == sid: return s
    sys.exit('DTP %d not found' % sid)


def main(argv):
    if len(argv) < 4: sys.exit(__doc__)
    nsib, nwords = 64, 0
    if '--siblings' in argv: k = argv.index('--siblings'); nsib = int(argv[k + 1]); del argv[k:k + 2]
    if '--words' in argv: k = argv.index('--words'); nwords = int(argv[k + 1]); del argv[k:k + 2]
    xsecs, src = TA.load_x(argv[0])
    psecs = TA.load_p(argv[1])
    sid = int(argv[2])
    offs = [int(x, 16) for x in argv[3].split(',')]
    sx, sp = section(xsecs, sid), section(psecs, sid)
    xd, pd = bytes(sx['data']), bytes(sp['data'])
    rx = R.parse(bytes(sx['reloc']), 'be')
    rp = R.parse(bytes(sp['reloc']), 'le')
    ix, ip = dict(rx.internal), dict(rp.internal)
    print('Xbox %s (%s) DTP %d: 0x%x bytes, %d internal pointers; PC %s: 0x%x bytes, %d internal pointers' % (
        argv[0], src, sid, len(xd), len(ix), argv[1], len(pd), len(ip)))
    if len(xd) != len(pd) or sorted(ix.items()) != sorted(ip.items()):
        print('NOTE: Xbox / PC layout differs (size or internal pointers) - offsets below are PC offsets')
    targets = sorted(set(ip.values()) | {0})
    referrers = {}
    for o, t in ip.items(): referrers.setdefault(t, []).append(o)

    def block_of(o):
        lo, hi = 0, len(targets)
        while lo < hi:
            m = (lo + hi) // 2
            if targets[m] <= o: lo = m + 1
            else: hi = m
        b = targets[lo - 1]
        nxt = targets[lo] if lo < len(targets) else len(pd)
        return b, nxt

    for off in offs:
        b, nxt = block_of(off)
        xw, pw = xd[off:off + 4], pd[off:off + 4]
        print('\n== +0x%x: Xbox %s (f %s) PC %s (f %s) %s; block +0x%x..+0x%x (size 0x%x), field +0x%x' % (
            off, xw.hex(), fval(xw, '>'), pw.hex(), fval(pw, '<'), cls(xw, pw), b, nxt, nxt - b, off - b))
        # chain to the root
        seen, cur, depth = set(), b, 0
        while cur in referrers and cur not in seen and depth < 12:
            seen.add(cur)
            refs = sorted(referrers[cur])
            r0 = refs[0]
            rb, rn = block_of(r0)
            print('   %s<- pointer at +0x%x (block +0x%x, field +0x%x)%s' % ('  ' * depth, r0, rb, r0 - rb,
                  (' and %d more referrer(s): %s' % (len(refs) - 1, ', '.join('+0x%x' % r for r in refs[1:6]))) if len(refs) > 1 else ''))
            cur, depth = rb, depth + 1
        # siblings: neighbouring pointer words of the first referrer
        refs = sorted(referrers.get(b, []))
        if refs:
            r0 = refs[0]
            arr = [r0]
            k = r0 - 4
            while k in ip and len(arr) < 1 + nsib: arr.insert(0, k); k -= 4
            k = r0 + 4
            while k in ip and len(arr) < 1 + 2 * nsib: arr.append(k); k += 4
            print('   pointer array +0x%x..+0x%x: %d entries (this record = entry %d)' % (arr[0], arr[-1], len(arr), arr.index(r0)))
            stats = {}
            for a in arr:
                t = ip[a]
                tb, tn = block_of(t)
                fo = t + (off - b)
                if fo + 4 > tn or fo + 4 > len(pd):
                    print('     entry +0x%x -> block +0x%x (size 0x%x): field outside' % (a, t, tn - t)); continue
                c = cls(xd[fo:fo + 4], pd[fo:fo + 4])
                if xd[fo:fo + 4] == b'\0\0\0\0' or xd[fo:fo + 4] == xd[fo:fo + 4][::-1]: c = 'same'
                stats[c] = stats.get(c, 0) + 1
                print('     entry +0x%x -> block +0x%x (size 0x%x): +0x%x Xbox %s (f %s) PC %s (f %s) %s%s' % (
                    a, t, tn - t, fo, xd[fo:fo + 4].hex(), fval(xd[fo:fo + 4], '>'), pd[fo:fo + 4].hex(),
                    fval(pd[fo:fo + 4], '<'), c, '   <== this' if t == b else ''))
            print('   same field in the array: %s' % ', '.join('%s %d' % kv for kv in sorted(stats.items())))
        else:
            print('   no internal pointer to the block start (root block)')
        if nwords:
            lo = max(b, off - 4 * nwords); hi = min(nxt, off + 4 * nwords + 4)
            for o in range(lo - lo % 4, hi, 4):
                print('     +0x%x (block +0x%x) Xbox %s (f %s) PC %s (f %s) %s%s' % (o, o - b, xd[o:o + 4].hex(),
                      fval(xd[o:o + 4], '>'), pd[o:o + 4].hex(), fval(pd[o:o + 4], '<'), cls(xd[o:o + 4], pd[o:o + 4]),
                      ' ptr' if o in ip else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
