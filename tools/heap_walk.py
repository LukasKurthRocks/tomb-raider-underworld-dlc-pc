"""Walk the game's own boundary-tag heap (tru.exe, dlmalloc-like, tru+0x198210 free / tru+0x197430 malloc) in a
minidump and report every chunk whose header is inconsistent (read-only; test 50d heap crash, finding 43).

Heap layout proven from tru.exe (see docs/Befund-Felsrinne.md "Test 50e"):
  heap object H (vtable 0x008518ec for the helper heaps at [0x00cda0b8] / [0x00cda0bc]), state S = [H + 0x24]
  S + 0x0c   top chunk (segment end), S + 0x418  segment start (contains(): [S+0x418] <= p < [S+0x0c])
  chunk C:   [C + 0] prev_size (only valid when the previous chunk is free; otherwise user data of the previous)
             [C + 4] head = size | 1 (bit 0 = PREVIOUS chunk in use), size multiple of 8
             [C + 8] fd, [C + 0x0c] bk (free chunks only); user pointer = C + 8; usable = size - 4 (overlaps the
             next chunk's prev_size)
  free(p):   C = p - 8; prev free -> unlink prev (fd->bk = bk, bk->fd = fd: tru+0x1982b3 / +0x1982e9);
             next free -> unlink next.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/heap_walk.py DUMP EXE [--heap ADDR_OF_HEAP_PTR] [--around VA [N]] [--max-bad K]
     DUMP   minidump with the heap memory (full dump, or a TruGuard dump if it holds the segment)
     EXE    tru.exe (for RTTI names of vtables found at the start of user blocks)
     --heap pointer variable holding the heap object (default 0x00cda0bc = helper heap 2; 0x00cda0b8 = helper 1)
     --around VA [N]  list the N chunks before and after the chunk holding VA (default 6) with their first dwords
     --max-bad K      stop listing problems after K (default 40)
Output: segment range, chunk count, in-use / free bytes, every bad header (size 0 / not 8-aligned / past top,
free chunk whose footer or fd / bk is wrong) with a resync, the listing around --around.
"""
import sys, os, struct, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import minidump_read as MR
import pe_callers as PE


class Mem:
    def __init__(self, path):
        self.m = MR.Minidump(path)
        self.starts = [r[0] for r in self.m.ranges]

    def read(self, va, n):
        out = b''
        while n > 0:
            i = bisect.bisect_right(self.starts, va) - 1
            if i < 0: return None
            rv, sz, fo = self.m.ranges[i]
            if not (rv <= va < rv + sz): return None
            k = min(n, rv + sz - va)
            out += self.m.d[fo + va - rv:fo + va - rv + k]
            va += k; n -= k
        return out

    def u32(self, va):
        b = self.read(va, 4)
        return None if b is None or len(b) < 4 else struct.unpack('<I', b)[0]


class Rtti:
    def __init__(self, exe_path):
        self.exe = open(exe_path, 'rb').read()
        self.base, self.secs = PE.sections(self.exe)
        self.cache = {}

    def off(self, a):
        for _, sva, rptr, size, _ in self.secs:
            if sva <= a < sva + size: return rptr + a - sva
        return -1

    def u32(self, a):
        o = self.off(a)
        return None if o < 0 else struct.unpack_from('<I', self.exe, o)[0]

    def name(self, vt):
        if vt in self.cache: return self.cache[vt]
        r = None
        col = self.u32(vt - 4)
        if col is not None and self.u32(col) == 0:
            td = self.u32(col + 12)
            if td is not None:
                o = self.off(td + 8)
                if o >= 0 and self.exe[o:o + 4] == b'.?AV':
                    e = self.exe.index(b'\0', o)
                    r = self.exe[o:e].decode('latin-1')
        self.cache[vt] = r
        return r


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    dump, exe = argv[0], argv[1]
    heap_ptr, around, n_around, max_bad, refs = 0x00cda0bc, None, 6, 40, None
    i = 2
    while i < len(argv):
        if argv[i] == '--heap': heap_ptr = int(argv[i + 1], 16); i += 2
        elif argv[i] == '--around':
            around = int(argv[i + 1], 16); i += 2
            if i < len(argv) and not argv[i].startswith('--'): n_around = int(argv[i]); i += 1
        elif argv[i] == '--max-bad': max_bad = int(argv[i + 1]); i += 2
        elif argv[i] == '--refs': refs = int(argv[i + 1], 16); i += 2
        else: print('unknown option', argv[i]); return 2
    M = Mem(dump); R = Rtti(exe)
    H = M.u32(heap_ptr)
    S = M.u32(H + 0x24)
    top, seg = M.u32(S + 0x0c), M.u32(S + 0x418)
    print('heap ptr 0x%08x -> heap 0x%08x vtable 0x%08x, state 0x%08x, segment 0x%08x .. top 0x%08x (%.1f MB)'
          % (heap_ptr, H, M.u32(H), S, seg, top, (top - seg) / 1e6))
    print('heap counters: +0x1c %d blocks, +0x20 %d bytes' % (M.u32(H + 0x1c), M.u32(H + 0x20)))
    blob = M.read(seg, top - seg + 16)
    if blob is None:
        print('segment not in the dump'); return 1
    u = lambda va: struct.unpack_from('<I', blob, va - seg)[0]

    def first(c, k=6):
        return ' '.join('%08x' % u(c + 8 + 4 * j) for j in range(k) if c + 8 + 4 * j + 4 <= top + 16)

    def cls(c):
        vt = u(c + 8)
        n = R.name(vt) if 0x00400000 <= vt < 0x00d00000 else None
        return n or ''

    # the first chunk: try seg and seg + 8 (alignment pad)
    chunks, bad = [], []
    c = seg
    for cand in (seg, seg + 8, seg - 8):
        h = u(cand + 4) if seg <= cand + 4 < top else 0
        if h & ~3 and (h & ~3) % 8 == 0 and cand + (h & ~3) <= top:
            c = cand; break
    while c < top:
        h = u(c + 4); size = h & ~3
        if size < 16 or size % 8 or c + size > top:
            bad.append((c, h, 'bad head'))
            # resync: next position from which 8 chunks chain cleanly
            p = c + 8; found = None
            while p < top:
                q, ok = p, 0
                while ok < 8 and q < top:
                    hh = u(q + 4); ss = hh & ~3
                    if ss < 16 or ss % 8 or q + ss > top: break
                    q += ss; ok += 1
                if ok == 8 or q == top:
                    found = p; break
                p += 8
            if found is None: break
            chunks.append((c, h, found - c, 'GAP'))
            c = found; continue
        chunks.append((c, h, size, ''))
        c += size
    # free / in use and free-chunk checks
    n_free = free_bytes = used_bytes = 0
    for k, (c, h, size, tag) in enumerate(chunks):
        if tag: continue
        nxt = c + size
        in_use = True
        if nxt < top:
            in_use = bool(u(nxt + 4) & 1)
        if not in_use:
            n_free += 1; free_bytes += size
            if u(nxt) != size: bad.append((c, h, 'free chunk footer 0x%x != size 0x%x' % (u(nxt), size)))
            fd, bk = u(c + 8), u(c + 0x0c)
            for nm, p in (('fd', fd), ('bk', bk)):
                if not ((seg <= p < top) or (S <= p < S + 0x420)):
                    bad.append((c, h, 'free chunk %s 0x%08x outside segment / bins' % (nm, p)))
        else:
            used_bytes += size
    print('chunks %d (free %d, %.1f MB free, %.1f MB in use), problems %d'
          % (len(chunks), n_free, free_bytes / 1e6, used_bytes / 1e6, len(bad)))
    for c, h, what in bad[:max_bad]:
        print('  BAD chunk 0x%08x head 0x%08x: %s; user 0x%08x: %s  prev chunk: %s'
              % (c, h, what, c + 8, first(c), prev_desc(chunks, c, u, first, cls)))
    if around is not None:
        idx = max(0, bisect.bisect_right([x[0] for x in chunks], around) - 1)
        print('chunks around 0x%08x:' % around)
        for c, h, size, tag in chunks[max(0, idx - n_around):idx + n_around + 1]:
            nxt = c + size
            st = tag or ('used' if nxt >= top or u(nxt + 4) & 1 else 'FREE')
            print('  %s0x%08x head 0x%08x size 0x%05x %-4s user 0x%08x: %s  %s'
                  % ('=> ' if c <= around < c + size else '   ', c, h, size, st, c + 8, first(c), cls(c)))
    if refs is not None:
        # every dword in the segment equal to REFS; a state-VM context (0x2c bytes, tru+0x37020) holds its stack
        # buffer at +0x0c (top frame base) and +0x10 (buffer), its frame buffer at +0x14 and its owner at +0x1c
        import numpy as np
        a = np.frombuffer(blob[:(len(blob) // 4) * 4], '<u4')
        hits = np.nonzero(a == refs)[0]
        print('dwords equal to 0x%08x: %d' % (refs, len(hits)))
        for k in hits[:20]:
            va = seg + 4 * int(k)
            ctx = va - 0x10 if u(va - 4) == refs else (va - 0x0c if u(va + 4) == refs else None)
            extra = ''
            if ctx is not None:
                extra = '  -> VM context 0x%08x: top %d, base 0x%08x, stack 0x%08x, frames 0x%08x depth %d, owner 0x%08x' % (
                    ctx, struct.unpack('<i', struct.pack('<I', u(ctx + 4)))[0], u(ctx + 0x0c), u(ctx + 0x10),
                    u(ctx + 0x14), u(ctx + 0x18), u(ctx + 0x1c))
            print('  at 0x%08x%s' % (va, extra))
    return 0


def prev_desc(chunks, c, u, first, cls):
    starts = [x[0] for x in chunks]
    k = bisect.bisect_left(starts, c) - 1
    if k < 0: return '-'
    p, h, size, tag = chunks[k]
    return '0x%08x size 0x%x %s %s' % (p, size, tag, cls(p))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
