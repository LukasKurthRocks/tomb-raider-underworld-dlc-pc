"""List the transitions of a converted (little-endian) player state chart DTP with their condition records
(read-only; finding 43, rock vein: which transitions lead to the title-update states and which test markup 607 / 608).

Transition = 20-byte block {u16 target state, u16, u16 count, u16, ptr conditions, ptr, u32} (layout proven by
tools/shape_proof.py on lara.drm 12647 / 850); its condition list = `count` records {u16 key, u16 id, u16 value, u8
flags, u8} at the first pointer.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/chart_transitions.py PC.drm SID [--target ID[,ID..]] [--value V[,V..]] [--cond ID[,ID..]]
        [--holders]
  ../bin/pyt -t 900 tools/chart_transitions.py all DIR_OR_DRM [DRM ..] --cond ID[,ID..]   every state-chart DTP
        (header words 3..6 = 10000, 12000, 4000, 6000) of every DRM given / in the folder (2026-11-02: where is
        condition 528 used?)
  --value    markup value V of a record {610..613, *, V}
  --cond     any condition record with this id (u16 +2)
  --holders  also print the pointer lists / blocks that point at each listed transition (who owns it)
"""
import sys, os, struct, bisect, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

HDR = struct.pack('<4I', 10000, 12000, 4000, 6000)


def listing(s, tg, vals, cids, holders, prefix=''):
    d = bytes(s.data); it = dict(R.parse(bytes(s.reloc), 'le').internal)
    t = sorted(set(it.values()) | {0})
    ptrs_in = collections.defaultdict(list)
    for o, x in it.items(): ptrs_in[x].append(o)
    n = 0
    for k, a in enumerate(t):
        end = t[k + 1] if k + 1 < len(t) else len(d)
        if end - a != 0x14 or (a + 8) not in it or (a + 0xc) not in it: continue
        target, w1, cnt, w3 = struct.unpack_from('<4H', d, a)
        c0 = it[a + 8]
        conds = []
        for j in range(min(cnt, 16)):
            if c0 + 8 * j + 8 > len(d): break
            ky, i, v = struct.unpack_from('<3H', d, c0 + 8 * j); fl = d[c0 + 8 * j + 6]
            conds.append((ky, i, v, fl))
        if tg and target not in tg: continue
        if vals and not any(c[2] in vals and c[1] in (610, 611, 612, 613) for c in conds): continue
        if cids and not any(c[1] in cids for c in conds): continue
        n += 1
        print('%s+0x%05x -> state %5d  (%d, count %d, %d)  conds @+0x%x: %s' % (prefix, a, target, w1, cnt, w3, c0,
              ' '.join('{%d,%d,%d%s}' % (c[0], c[1], c[2], ',NOT' if c[3] & 1 else '') for c in conds)))
        if holders:
            for p in ptrs_in.get(a, ()):
                kb = bisect.bisect_right(t, p) - 1
                print('      held by +0x%05x (block +0x%x, slot %d)' % (p, t[kb], (p - t[kb]) // 4))
    return n


def main(argv):
    holders = '--holders' in argv; argv = [a for a in argv if a != '--holders']
    tg = vals = cids = None
    if '--target' in argv: k = argv.index('--target'); tg = set(int(x) for x in argv[k + 1].split(',')); del argv[k:k + 2]
    if '--value' in argv: k = argv.index('--value'); vals = set(int(x) for x in argv[k + 1].split(',')); del argv[k:k + 2]
    if '--cond' in argv: k = argv.index('--cond'); cids = set(int(x) for x in argv[k + 1].split(',')); del argv[k:k + 2]
    if argv[0] == 'all':
        files = []
        for p in argv[1:]:
            if os.path.isdir(p): files += [os.path.join(p, f) for f in sorted(os.listdir(p)) if f.endswith('.drm')]
            else: files.append(p)
        total = charts = 0
        for f in files:
            try:
                D = DW.read(open(f, 'rb').read(), 'le')
            except Exception as ex:
                print('%s: not readable (%s)' % (os.path.basename(f), ex)); continue
            for s in D.sections:
                if s.type != 7 or bytes(s.data[0xc:0x1c]) != HDR: continue
                charts += 1
                m = listing(s, tg, vals, cids, holders, '%s DTP %d ' % (os.path.basename(f), s.id))
                print('%s DTP %d: state chart, %d transitions listed' % (os.path.basename(f), s.id, m))
                total += m
        print('%d files, %d state charts, %d transitions listed' % (len(files), charts, total))
        return
    D = DW.read(open(argv[0], 'rb').read(), 'le')
    s = [q for q in D.sections if q.id == int(argv[1]) and q.type == 7][0]
    print('%d transitions listed' % listing(s, tg, vals, cids, holders))


if __name__ == '__main__':
    main(sys.argv[1:])
