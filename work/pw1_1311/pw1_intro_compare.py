"""PW.1 (2026-11-13, Q124): compare the placed intros of one unit DRM between the Xbox original (big endian) and
two PC trees (little endian), word by word - intro record (0x90 B) and its intro data block (+0x78).

Read-only. Usage (from the repository root):
  ../bin/pyt -t 600 work/pw1_1311/pw1_intro_compare.py XBOX.drm OWN.drm OLD.drm [--grep REGEX] [--all]
Prints: intro list (id, object, name, position) of every tree; intros whose record or data block differs between
OWN and OLD; for --grep matches (default water) a word table Xbox / own / old with the byte-order class per word:
  s32  = PC word is the Xbox u32 byte-swapped      u16p = swapped as two u16 halves
  raw  = PC bytes equal the Xbox bytes            sym  = the word reads the same in every order (0, ffffffff ...)
  ptr  = relocated pointer (not compared)         DIFF = none of these
Exit code 0.
"""
import sys, os, re, struct
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import drm_write as DW, drm_reloc as R, unit_ids as U

LISTS = os.path.join(ROOT, 'work', 'generic', 'lists')


def names(fn):
    d = {}
    for line in open(os.path.join(LISTS, fn), encoding='utf8', errors='ignore'):
        p = line.strip().split(',', 1)
        if len(p) == 2 and p[0].isdigit(): d[int(p[0])] = p[1]
    return d


def load(path, e):
    D = DW.read(open(path, 'rb').read(), e)
    secs = [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]
    L = U.level_info(secs, e)
    E = '>' if e == 'be' else '<'
    out = {}
    for si, o in L['intros']:
        d = secs[si]['data']
        rp = R.parse(secs[si]['reloc'], e)
        ri = dict(rp.internal)
        ptrs = set(ri) | set(so for so, _, _ in [(x[1], x[0], x[2]) for x in rp.external])
        targets = sorted(set(ri.values()) | set(o2 for _, o2 in L['intros']) | {len(d)})
        oid = struct.unpack_from(E + 'H', d, o + 0x50)[0]
        uid = struct.unpack_from(E + 'I', d, o + 0x58)[0]
        pos = struct.unpack_from(E + '3f', d, o + 0x10)
        t = ri.get(o + 0x78)
        blk = None
        if t is not None:
            end = next(x for x in targets if x > t)
            blk = (t, end)
        out[uid] = dict(sec=si, off=o, oid=oid, pos=pos, data=d, blk=blk, ptrs=ptrs, E=E)
    return out


def word_class(xb, pb, isptr):
    if isptr: return 'ptr'
    if xb == pb and xb == xb[::-1] and xb == bytes((xb[1], xb[0], xb[3], xb[2])): return 'sym'
    c = []
    if xb[::-1] == pb: c.append('s32')
    if bytes((xb[1], xb[0], xb[3], xb[2])) == pb: c.append('u16p')
    if xb == pb: c.append('raw')
    return '/'.join(c) if c else 'DIFF'


def fmt(b, E):
    u = struct.unpack(E + 'I', b)[0]
    f = struct.unpack(E + 'f', b)[0]
    h = struct.unpack(E + '2H', b)
    fs = ('%.4g' % f) if (f == f and 1e-6 < abs(f) < 1e9) else '-'
    return '%08x f=%-10s h=%5d,%5d' % (u, fs, h[0], h[1])


def dump(label, X, O, P, uid):
    x, o, p = X.get(uid), O.get(uid), P.get(uid)
    print('\n-- intro %d %s' % (uid, label))
    for part in ('rec', 'blk'):
        rng = {}
        for k, v in (('x', x), ('o', o), ('p', p)):
            if v is None: continue
            if part == 'rec': rng[k] = (v['off'], v['off'] + 0x90)
            elif v['blk']: rng[k] = v['blk']
        if not rng: continue
        print('   [%s] sizes %s' % (part, ', '.join('%s 0x%x' % (k, b - a) for k, (a, b) in rng.items())))
        n = max(b - a for a, b in rng.values())
        for w in range(0, n, 4):
            cells = []; raw = {}
            for k, v in (('x', x), ('o', o), ('p', p)):
                if k not in rng or rng[k][0] + w + 4 > rng[k][1]:
                    cells.append(' ' * 44); continue
                a = rng[k][0] + w
                raw[k] = (v['data'][a:a + 4], a in v['ptrs'])
                cells.append(fmt(v['data'][a:a + 4], v['E']))
            cls = []
            for k in ('o', 'p'):
                if 'x' in raw and k in raw:
                    cls.append(word_class(raw['x'][0], raw[k][0], raw[k][1]))
                else: cls.append('?')
            mark = ' <<' if (('o' in raw and 'p' in raw and raw['o'][0] != raw['p'][0]) or 'DIFF' in cls) else ''
            print('   +%03x X %s | own %s | old %s | %s%s' % (w, cells[0], cells[1], cells[2], ' '.join(cls), mark))


def main(argv):
    argv = list(argv)
    rx = 'water'
    if '--grep' in argv:
        i = argv.index('--grep'); rx = argv[i + 1]; del argv[i:i + 2]
    show_all = '--all' in argv
    if show_all: argv.remove('--all')
    xp, op, pp = argv
    nx = names('dlc_pack10_objectlist.txt'); npc = names('pc_objectlist.txt')
    try:
        npc.update({k: v for k, v in names(os.path.join('..', 'merged', 'tr8', 'pc-w', 'objectlist.txt')).items()})
    except OSError:
        pass
    X = load(xp, 'be'); O = load(op, 'le'); P = load(pp, 'le')
    print('intros: xbox %d, own %d, old %d' % (len(X), len(O), len(P)))
    if show_all:
        for uid in sorted(set(X) | set(O) | set(P)):
            v = O.get(uid) or P.get(uid); xv = X.get(uid)
            print('  %6d xobj %4s %-34s pcobj %4s %-34s pos %s' % (
                uid, xv['oid'] if xv else '-', nx.get(xv['oid'], '?') if xv else '-',
                v['oid'] if v else '-', npc.get(v['oid'], '?') if v else '-',
                ' '.join('%8.0f' % c for c in (v or xv)['pos'])))
    print('\nintros whose record or data block differs own <-> old:')
    for uid in sorted(set(O) & set(P)):
        o, p = O[uid], P[uid]
        ro = o['data'][o['off']:o['off'] + 0x90]; rp = p['data'][p['off']:p['off'] + 0x90]
        bo = o['data'][o['blk'][0]:o['blk'][1]] if o['blk'] else b''
        bp = p['data'][p['blk'][0]:p['blk'][1]] if p['blk'] else b''
        # pointers may legitimately differ (layout); compare non-pointer words only
        def words(v, a, b):
            return [v['data'][q:q + 4] for q in range(a, b, 4) if q not in v['ptrs']]
        dr = words(o, o['off'], o['off'] + 0x90) != words(p, p['off'], p['off'] + 0x90)
        db = (words(o, *o['blk']) if o['blk'] else []) != (words(p, *p['blk']) if p['blk'] else [])
        if dr or db:
            print('  %6d %-34s rec %s blk %s (sizes own %s old %s)' % (
                uid, npc.get(o['oid'], '?'), 'DIFF' if dr else 'same', 'DIFF' if db else 'same',
                hex(o['blk'][1] - o['blk'][0]) if o['blk'] else '-', hex(p['blk'][1] - p['blk'][0]) if p['blk'] else '-'))
    for uid in sorted(set(O) | set(P)):
        v = O.get(uid) or P.get(uid)
        nm = npc.get(v['oid'], '?')
        if re.search(rx, nm): dump(nm, X, O, P, uid)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
