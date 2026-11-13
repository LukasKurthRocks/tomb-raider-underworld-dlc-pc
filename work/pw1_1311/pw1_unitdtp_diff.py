"""PW.1 (2026-11-13, Q124): every word of the unit DTP (Level+0x74) where two PC trees differ, next to the Xbox word
at the same offset, with the byte-order class of each PC word and the owning structure (intro record / intro data
block of which intro and object, else 'root data').

Read-only. Usage (from the repository root):
  ../bin/pyt -t 600 work/pw1_1311/pw1_unitdtp_diff.py XBOX.drm OWN.drm OLD.drm
Classes: s32 (PC = Xbox u32 swapped), u16p (two u16 halves swapped), raw (bytes kept), sym, other.
Exit code 0.
"""
import sys, os, struct, collections
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import drm_write as DW, drm_reloc as R, unit_ids as U

LISTS = os.path.join(ROOT, 'work', 'generic', 'merged', 'tr8', 'pc-w', 'objectlist.txt')


def names():
    d = {}
    for line in open(LISTS, encoding='utf8', errors='ignore'):
        p = line.strip().split(',', 1)
        if len(p) == 2 and p[0].isdigit(): d[int(p[0])] = p[1]
    return d


def unit_dtp(path, e):
    D = DW.read(open(path, 'rb').read(), e)
    secs = [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]
    L = U.level_info(secs, e)
    E = '>' if e == 'be' else '<'
    si = L['intros'][0][0]
    d = secs[si]['data']
    ri = dict(R.parse(secs[si]['reloc'], e).internal)
    owners = []
    targets = sorted(set(ri.values()) | {o for _, o in L['intros']} | {len(d)})
    for _, o in L['intros']:
        oid = struct.unpack_from(E + 'H', d, o + 0x50)[0]
        uid = struct.unpack_from(E + 'I', d, o + 0x58)[0]
        owners.append((o, o + 0x90, 'intro %d obj %d rec' % (uid, oid)))
        t = ri.get(o + 0x78)
        if t is not None:
            end = next(x for x in targets if x > t)
            owners.append((t, end, 'intro %d obj %d data' % (uid, oid)))
    return d, set(ri), owners


def cls(x, p):
    if x == p and x == x[::-1] and x == bytes((x[1], x[0], x[3], x[2])): return 'sym'
    c = []
    if x[::-1] == p: c.append('s32')
    if bytes((x[1], x[0], x[3], x[2])) == p: c.append('u16p')
    if x == p: c.append('raw')
    return '/'.join(c) if c else 'other'


def main(argv):
    xp, op, pp = argv
    nm = names()
    xd, _, _ = unit_dtp(xp, 'be')
    od, optr, own = unit_dtp(op, 'le')
    pd, _, _ = unit_dtp(pp, 'le')
    print('unit DTP sizes: xbox 0x%x, own 0x%x, old 0x%x' % (len(xd), len(od), len(pd)))
    groups = collections.Counter()
    for q in range(0, min(len(od), len(pd)) - 3, 4):
        if od[q:q + 4] == pd[q:q + 4]: continue
        where = 'root data'
        for a, b, lab in own:
            if a <= q < b:
                oid = int(lab.split(' obj ')[1].split()[0])
                where = '%s +0x%x (%s)' % (lab, q - a, nm.get(oid, '?')); break
        x = xd[q:q + 4] if q + 4 <= len(xd) else b'????'
        co, cp = cls(x, od[q:q + 4]), cls(x, pd[q:q + 4])
        groups[(where.split(' +0x')[0] if where != 'root data' else 'root data', co, cp)] += 1
        print('  +0x%05x X %s own %s (%s) old %s (%s)  %s%s' % (
            q, x.hex(), od[q:q + 4].hex(), co, pd[q:q + 4].hex(), cp, where, ' [ptr]' if q in optr else ''))
    print('\nsummary (owner, own class, old class): count')
    for k, v in sorted(groups.items(), key=lambda kv: -kv[1]):
        print('  %4d  %s | own %s | old %s' % (v, k[0], k[1], k[2]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
