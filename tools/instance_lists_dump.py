"""Walk the 64 instance category lists of the static instance pool in a minidump (read-only; thrall link crash
tru+0x1976a3, tests 50i / 50j / 50k, docs Befund-Thrall-Absturz.md).

Engine facts (tru.exe, static analysis 2026-11-03):
  * pool: 1024 slots of 0x2f0 bytes, base = [0xd98f60] (normally 0x00ce74c0); globals 0xd98d50 count, 0xd98d54 active
    list head (links at instance +8 / +0xc), 0xd98d58 id counter, 0xd98d5c free list head (LIFO: a removed instance
    is the next one handed out - so the slot numbers of a spawn depend on what was removed before).
  * 64 category list heads at 0xd98d60 + 8*k (k = instance byte +0x185, computed at spawn tru+0x1bb437 /
    re-insert tru+0x1b2f40 from the low byte of [[object]]). Head S: S+0 unused (0), S+4 = newest instance.
    Instance links: +4 = the next OLDER instance (0 = end), +0 = the NEWER neighbour or the head S. push = tru+0x197670
    (insert-before(S, n): n+0 = S, n+4 = S+4, [S+4]+0 = n, S+4 = n), unlink = tru+0x197690 (crash site +0x1976a3).
Prints the globals, every non-empty list (newest -> oldest) with each node's +0 / +4 / object / flags / +0x185 /
object flag byte, and marks BAD links (pointer not a slot start or head, back link mismatch); walking stops at a
pointer that is not a slot start ("slot N - d" = off by d). Optionally all slots whose instance flags (+0x14) match.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/instance_lists_dump.py DUMP [--flags 0x0a014222,0x0a034222] [--k 0x3f] [--max 1100]
                     [--pool-start 0x00ce74c0] [--stride 0x2f0] [--slots 1024] [--heads 0xd98d60]
  e.g. ../bin/pyt -t 300 tools/instance_lists_dump.py ../runs/<run>/dumps/tru_av2_full.dmp --flags 0x0a014222,0x0a034222
Exit code: 0 = read, 2 = usage error.
"""
import sys, os, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import minidump_read as MR


def category(b):
    """the spawn mapping tru+0x1bb437..0x1bb467: object flag byte -> list index"""
    k = 0
    if b & 0x80: k |= 1
    if b & 0x20: k |= 2
    if b & 0x40: k |= 4
    if b & 0x08: k |= 0x20
    if b & 0x10: k |= 0x10
    if b & 0x01: k |= 8
    return k


def opt(argv, name, default):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


def main(argv):
    argv = list(argv)
    flags = opt(argv, '--flags', '')
    only_k = opt(argv, '--k', None)
    maxn = int(opt(argv, '--max', '1100'))
    start = int(opt(argv, '--pool-start', '0x00ce74c0'), 16)
    stride = int(opt(argv, '--stride', '0x2f0'), 16)
    nslots = int(opt(argv, '--slots', '1024'))
    heads = int(opt(argv, '--heads', '0xd98d60'), 16)
    if len(argv) != 1:
        print(__doc__)
        return 2
    M = MR.Minidump(argv[0])
    want_flags = {int(x, 16) for x in flags.split(',') if x}
    only_k = int(only_k, 16) if only_k else None

    def label(v):
        if v is None:
            return '?'
        if v == 0:
            return '0'
        if heads <= v < heads + 64 * 8:
            d = v - heads
            return 'head%02x%s' % (d // 8, '' if d % 8 == 0 else '+%d' % (d % 8))
        if start - stride <= v < start + nslots * stride:
            n, d = divmod(v - start, stride)
            if d == 0:
                return 'slot%d' % n
            if d > stride - 16:
                return 'slot%d-%d' % (n + 1, stride - d)
            return 'slot%d+0x%x' % (n, d)
        return '0x%08x' % v

    def is_node(v):
        return v is not None and v != 0 and start <= v < start + nslots * stride and (v - start) % stride == 0

    e = M.exception
    print('# instance lists: %s' % argv[0])
    if e:
        r = M.regs(e['ctx'])
        print('exception %08x at %s; eax %s ecx %s edx %s esi %s edi %s' % (
            e['code'], M.module_of(e['addr']) or '0x%08x' % e['addr'], label(r['eax']), label(r['ecx']),
            label(r['edx']), label(r['esi']), label(r['edi'])))
    g = [M.u32(a) for a in (0xd98d50, 0xd98d54, 0xd98d58, 0xd98d5c, 0xd98f60)]
    print('globals: count %s, active head %s, id counter %s, free head %s, pool base %s' % (
        g[0], label(g[1]), g[2], label(g[3]), '0x%08x' % g[4] if g[4] is not None else '?'))
    if g[4] is not None and g[4] != start:
        print('WARNING: pool base [0xd98f60] = 0x%08x differs from --pool-start 0x%08x' % (g[4], start))

    bad_total = 0
    for k in range(64):
        if only_k is not None and k != only_k:
            continue
        s = heads + 8 * k
        h0, h4 = M.u32(s), M.u32(s + 4)
        if not h0 and not h4:
            continue
        rows, bad, back, node, n = [], 0, s, h4, 0
        head_bad = h4 is not None and h4 != 0 and not is_node(h4)
        while node and n < maxn:
            if not is_node(node):
                raw = M.u32(node)
                rows.append('    BAD pointer %s (raw dword there 0x%08x) - walk stopped' % (
                    label(node), raw if raw is not None else 0))
                bad += 1
                break
            b = M.read(node, stride)
            if b is None:
                rows.append('    %s not in dump' % label(node))
                break
            nx0, nx4 = struct.unpack_from('<II', b, 0)
            obj, fl = struct.unpack_from('<II', b, 0x10)
            cat = b[0x185]
            p = M.u32(obj) if obj else None
            ob = M.read(p, 1) if p else None
            ob = ob[0] if ob else None
            mark = []
            if nx0 != back:
                mark.append('back %s != %s' % (label(nx0), label(back)))
            if nx4 and not is_node(nx4):
                mark.append('+4 not a slot')
            if cat != k:
                mark.append('+0x185 = %02x' % cat)
            bad += bool(mark)
            rows.append('    %s %s +0 %s +4 %s obj 0x%08x flags 0x%08x objbyte %s -> k %s%s' % (
                'BAD' if mark else '   ', label(node), label(nx0), label(nx4), obj, fl,
                '%02x' % ob if ob is not None else '?', '%02x' % category(ob) if ob is not None else '?',
                ('  <- ' + '; '.join(mark)) if mark else ''))
            back, node, n = node, nx4, n + 1
        bad_total += bad + head_bad
        print('head %02x @0x%08x: +0 %s +4 %s - %d node(s)%s%s' % (
            k, s, label(h0), label(h4), n, ', %d BAD' % bad if bad else '', ' (head +4 BAD)' if head_bad else ''))
        for r_ in rows:
            print(r_)

    if want_flags:
        print('slots with flags %s:' % ', '.join('0x%08x' % f for f in sorted(want_flags)))
        for i in range(nslots):
            a = start + i * stride
            b = M.read(a, stride)
            if b is None:
                continue
            nx0, nx4, w8, wc, obj, fl = struct.unpack_from('<6I', b, 0)
            if fl in want_flags:
                print('    slot%d 0x%08x +0 %s +4 %s +8 %s +c %s obj 0x%08x flags 0x%08x +0x185 %02x' % (
                    i, a, label(nx0), label(nx4), label(w8), label(wc), obj, fl, b[0x185]))
    print('BAD total: %d' % bad_total)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
