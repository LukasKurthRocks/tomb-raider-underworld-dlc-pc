"""List the pointer-like dwords of instances and of their enemy brains in a minidump (read-only; thrall link crash
tru+0x1976a3, docs Befund-Thrall-Absturz.md): which fields hold an INSTANCE pointer (a pool slot start, "self" = the
instance itself) and which hold a WEAK-REFERENCE NODE (8-byte nodes {+0 target, +4 refcount} in the table [0xcda0c0],
free list [0xcda0c4]; release = `add dword ptr [node+4], -1`). A holder that should point to a weak node but points to
an instance turns the release into "instance +4 link - 1" - the damage of 50i / 50j / 50k.

Per instance: the instance itself (0x2f0 bytes), the object behind +0x2d0 ([inst+0x2d0] -> p, [p] -> q, brain =
[q+0x2ec], the enemy brain used by the type callbacks 0x6187c0 / 0x627a80) over --brain-size bytes. A field is shown
when its value is a slot start / "slot N - d" / a weak node (inside the table, 8-aligned) / the weak table itself.
With two or more slots, a field offset that holds "self" in one instance is compared over all given instances.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/instance_refs_dump.py DUMP SLOT[,SLOT..] [--pool-start 0x00cdcd50] [--stride 0x2f0]
                     [--slots 1024] [--brain-size 0x2000] [--weak-size 0x80000]
  e.g. ../bin/pyt -t 300 tools/instance_refs_dump.py ../runs/<run>/dumps/tru_av2_full.dmp 110,111,112,113,114
Exit code: 0 = read, 2 = usage error.
"""
import sys, os, struct, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import minidump_read as MR


def opt(argv, name, default):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


def main(argv):
    argv = list(argv)
    start = int(opt(argv, '--pool-start', '0x00cdcd50'), 16)
    stride = int(opt(argv, '--stride', '0x2f0'), 16)
    nslots = int(opt(argv, '--slots', '1024'))
    bsize = int(opt(argv, '--brain-size', '0x2000'), 16)
    wsize = int(opt(argv, '--weak-size', '0x80000'), 16)
    if len(argv) != 2:
        print(__doc__)
        return 2
    M = MR.Minidump(argv[0])
    slots = [int(x, 0) for x in argv[1].split(',')]
    wbase, wfree = M.u32(0xcda0c0), M.u32(0xcda0c4)
    print('# instance refs: %s' % argv[0])
    print('weak table [0xcda0c0] = %s, free head [0xcda0c4] = %s; pool 0x%08x stride 0x%x' % (
        '0x%08x' % wbase if wbase is not None else '?', '0x%08x' % wfree if wfree is not None else '?', start, stride))

    def label(v, own):
        if v == own and own:
            return 'SELF'
        if start <= v < start + nslots * stride:
            n, d = divmod(v - start, stride)
            if d == 0:
                return 'slot%d' % n
            if d > stride - 16:
                return 'slot%d-%d' % (n + 1, stride - d)
            return None
        if wbase and wbase <= v < wbase + wsize and (v - wbase) % 8 == 0:
            t = M.u32(v)
            return 'weaknode#%d(target %s, refs %s)' % ((v - wbase) // 8, '0x%08x' % t if t is not None else '?',
                                                        M.u32(v + 4))
        if v == wbase:
            return 'weaktable'
        return None

    selfmap = collections.defaultdict(dict)    # (region, off) -> {slot: label}
    for s in slots:
        inst = start + s * stride
        b = M.read(inst, stride)
        if b is None:
            print('slot%d not in dump' % s)
            continue
        obj, fl = struct.unpack_from('<II', b, 0x10)
        p = struct.unpack_from('<I', b, 0x2d0)[0]
        q = M.u32(p) if p else None
        brain = M.u32(q + 0x2ec) if q else None
        print('slot%d 0x%08x obj 0x%08x flags 0x%08x +0x185 %02x  +0x2d0 -> 0x%08x -> %s -> brain %s' % (
            s, inst, obj, fl, b[0x185], p, '0x%08x' % q if q else '?', '0x%08x' % brain if brain else '?'))
        regions = [('inst', inst, b)]
        if brain:
            bb = M.read(brain, bsize)
            if bb is not None:
                regions.append(('brain', brain, bb))
            else:
                print('    brain 0x%08x not in dump (size 0x%x)' % (brain, bsize))
        for name, base, data in regions:
            for off in range(0, len(data) - 3, 4):
                v = struct.unpack_from('<I', data, off)[0]
                if not v:
                    continue
                lab = label(v, inst)
                if lab:
                    if not (name == 'inst' and off in (0, 4, 8, 0xc)):    # the list links are known
                        print('    %-5s +0x%04x = 0x%08x %s' % (name, off, v, lab))
                    selfmap[(name, off)][s] = lab.split('(')[0]
    if len(slots) > 1:
        print('fields that hold SELF or an instance in at least one of the given slots:')
        for (name, off), d in sorted(selfmap.items()):
            if any(x == 'SELF' or x.startswith('slot') for x in d.values()):
                print('    %-5s +0x%04x: %s' % (name, off, ', '.join('slot%d=%s' % kv for kv in sorted(d.items()))))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
