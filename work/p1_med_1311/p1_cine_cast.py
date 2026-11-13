"""P1 (2026-11-13): which intros (co_* actors) each cinematic stream names in its cine block 0 (read-only).

Same reading as tools/cine_mul_info.py --ids (aligned u32 words equal to an intro unique id in cine block 0; the field
is the actor table - layout inferred, docs/Befund-Erweitertes-Ende.md 3.3). INTROS = lines 'unit uid object' (e.g.
the co_* / cinematic_object intros of the l1 / prologue units). Prints per stream the scene name, unit, and every
listed intro found (count), then per co_* object the streams that name one of its intros (and intros named nowhere).

Usage (from trudlcport):
  ../bin/pyt -t 900 work/p1_med_1311/p1_cine_cast.py SOURCE INTROS NAME.mul [NAME.mul ...]
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import cine_mul_info as CM
import locals as LC
from archive import Archive
from names import crc


def main(argv):
    if len(argv) < 3:
        print(__doc__); return 2
    src, intros, muls = argv[0], argv[1], argv[2:]
    rows = [l.split() for l in open(intros, encoding='utf-8') if l.strip()]
    ids = {int(r[1]): (r[0], r[2]) for r in rows}
    path, e, pre = LC.SRC[src]
    E = '>' if e == 'be' else '<'
    A = Archive(path, e)
    un = CM.unit_names(src)
    used = {}
    for name in muls:
        recs = A.find(crc(pre + '\\cinstream\\' + name))
        if not recs:
            print('%s: not in %s' % (name, src)); continue
        r = ([x for x in recs if x['spec'] == 0xffffffe1] or recs)[-1]
        d = A.read(r)
        B, end = CM.blocks(d, E)
        C = [b[3] for b in B if b[0] == 1]
        if not C:
            print('%s: no cine block' % name); continue
        p0 = C[0]
        scene = p0[0xc:0x4c].split(b'\0')[0].decode('latin1', errors='replace')
        w = struct.unpack_from(E + '4I', p0, 0x4c)
        cnt = {}
        for o in range(0, len(p0) - 3, 4):
            v = struct.unpack_from(E + 'I', p0, o)[0]
            if v in ids: cnt[v] = cnt.get(v, 0) + 1
        print('%s: scene "%s", unit %s, %d cine frames (%.1f s); intros named: %s' % (
            name, scene, un.get(w[0], w[0]), len(C), (len(C) - 1) / 30.0,
            ', '.join('%d %s/%s x%d' % (v, ids[v][0], ids[v][1], n) for v, n in sorted(cnt.items())) or '-'))
        for v in cnt:
            used.setdefault(ids[v][1], []).append('%s (%d)' % (name.rsplit('.', 1)[0], v))
    print()
    objs = sorted({r[2] for r in rows})
    for o in objs:
        if not o.startswith('co_'): continue
        mine = [int(r[1]) for r in rows if r[2] == o]
        named = {int(x.split('(')[1].rstrip(')')) for x in used.get(o, [])}
        print('%-34s %2d intro(s); in streams: %s%s' % (o, len(mine), ', '.join(sorted(set(used.get(o, [])))) or '-',
              ('; never named: ' + ' '.join(str(m) for m in mine if m not in named)) if any(m not in named for m in mine) else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
