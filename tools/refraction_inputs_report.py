"""Which samplers of a shader class are bound by the material and which by the engine: compares the sampler names
(constant tables) of Xbox / PC shader libraries with the texture records of the materials that use them, Xbox vs PC.
Read-only. Finding 43, test 45 (DLC 2 fall column, material 24691, PC surrogates 1909 / 1910 / 1911 read s2 / s3
in screen space): find base materials of the same shader class and how their s2 / s3 are supplied.

Usage (from the repository root; needs work/render/shaderlibs.pkl, shader_x2p.pkl, material_x2p.pkl):
  ../bin/pyt -t 900 tools/refraction_inputs_report.py names [--kind ps|vs] [--grep TEXT]
      sampler names (hash parts stripped) over all base Xbox and PC libraries: register, count of libs
  ../bin/pyt -t 900 tools/refraction_inputs_report.py lib PCID[,PCID]
      the Xbox base libraries mapped to these PC libraries (shader_x2p) and the sampler / constant names of both
  ../bin/pyt -t 900 tools/refraction_inputs_report.py mats --pclib PCID[,..] | --xlib XID[,..] | --sampler TEXT [--max N]
      base materials whose tuple uses the libraries (or whose libraries have a sampler name containing TEXT):
      tuple, header words +0x38..+0x53, texture records (id, type, u8 +12, sampler slot, filter) and MaterialParams,
      Xbox next to PC; --owners adds the Xbox DRM names that hold each material
  ../bin/pyt -t 900 tools/refraction_inputs_report.py stats [--below N]
      over all base materials, Xbox and PC: byte +0x4F vs highest sampler slot + 1, every texture record with an id
      below N (engine id 2) grouped by u8 +12 and the sampler name of that slot, engine-named samplers without a
      record, bytes +0x50..+0x52, and which header bits go with a back-buffer record (+0x44 bit 1)
  ../bin/pyt -t 900 tools/refraction_inputs_report.py one FILE.drm be|le MATID
      the same record dump for one material of any DRM (Xbox DLC: be)
"""
import sys, os, pickle, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import shader_map as SM
from shaderlib import constants, norm_name

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'render')


def lib_consts(lib, pl):
    """union over the occupied slot entries: set of (norm name, regset, reg, count)"""
    out = set()
    for s in lib['slots']:
        if s == 0xffffffff: continue
        _, c = constants(lib['entries'][s]['blob'], pl)
        for n, rs, ri, rc in c: out.add((norm_name(n), rs, ri, rc))
    return out


def samplers(lib, pl):
    return sorted((ri, n) for n, rs, ri, rc in lib_consts(lib, pl) if rs == 3)


def records(d, rb, e):
    """header words and texture records of a material (data, reloc blob, '>' or '<')"""
    r = R.parse(rb, 'be' if e == '>' else 'le')
    tp = dict(r.internal).get(0x54)
    head = ' '.join('%08x' % w for w in struct.unpack_from(e + '7I', d, 0x38))
    raw4c = d[0x4C:0x54].hex(' ')
    recs = []
    if tp is not None:
        for k in range(d[0x52]):
            tid, u1, typ, b0, slot, filt = struct.unpack_from(e + 'IIIBBH', d, tp + 16 * k)
            recs.append((slot, tid, typ, b0, filt, u1))
    return head, raw4c, recs          # record order as stored


def show(tag, d, rb, e):
    head, raw4c, recs = records(d, rb, e)
    print('    %-4s tuple %s  +38..+50 %s  bytes4c %s' % (tag, '/'.join(str(x) for x in struct.unpack_from(e + '4I', d, 0x28)), head, raw4c))
    print('         textures (stored order) %s' % '  '.join('s%d=%d(t%d,f%x%s%s)' % (s, t, ty, f, ',u%x' % u if u else '', ',b%d' % b if b else '')
                                                       for s, t, ty, b, f, u in recs))
    r = R.parse(rb, 'be' if e == '>' else 'le'); tp = dict(r.internal).get(0x54); pp = dict(r.internal).get(0x5C)
    if pp is not None:   # MaterialParams (c100..), vec4 each
        n = struct.unpack_from(e + 'I', d, 0x58)[0]
        print('         MaterialParams %s' % '  '.join('c%d=(%s)' % (100 + i, ','.join('%g' % v for v in struct.unpack_from(e + '4f', d, pp + 16 * i)))
                                                      for i in range(n)))
    if tp is not None:   # which record id fields carry an id reference (kind 4 list 'idref' / kind A 'idref_a')
        print('         id refs per record: %s' % ' '.join('%d:%s%s' % (k, 'R' if (5, tp + 16 * k) in r.idref else '-',
                                                                         'A' if (5, tp + 16 * k) in r.idref_a else '-')
                                                           for k in range(len(recs))))


def stats(M, e, P, pl, lo):
    """over all materials of one platform: byte +0x4F vs highest sampler slot + 1; records with texture id < lo
    (grouped by id, type, filter, u8 +12 and the sampler name of the material's pixel-shader libraries at that
    slot); engine-named samplers (BackBuffer / DepthBuffer) without a record; bytes +0x50 / +0x51 / +0x52 against
    the number of ordinary records, engine records and the position of the first engine record"""
    rel = collections.Counter(); low = collections.Counter(); ex = {}; miss = collections.Counter(); cnt = collections.Counter()
    for mid, (d, rb) in M.items():
        if len(d) < 0x60: continue
        _, _, recs = records(d, rb, e)
        if recs: rel[(d[0x4F] - (max(s for s, *_ in recs) + 1), d[0x52] == len(recs))] += 1
        names = collections.defaultdict(set)
        for lid in SM.tuple_of(d, e)[:3]:
            if lid in P:
                for ri, n in samplers(P[lid], pl): names[ri].add(n)
        for s, t, ty, b, f, u in recs:
            if t < lo:
                k = (t, ty, f, b, '|'.join(sorted(names.get(s, {'-'}))))
                low[k] += 1; ex.setdefault(k, mid)
        have = {s for s, *_ in recs}
        for ri, ns in names.items():
            for n in ns:
                if ('BackBuffer' in n or 'DepthBuffer' in n) and ri not in have: miss[n] += 1; ex.setdefault(('miss', n), mid)
        eng = [i for i, x in enumerate(recs) if x[1] < lo]
        if eng: cnt[(d[0x50], d[0x51], d[0x52], 'ordinary %d' % (len(recs) - len(eng)), 'engine %d' % len(eng),
                     'first engine at %d' % eng[0], 'engine records last' if eng == list(range(len(recs) - len(eng), len(recs))) else 'mixed')] += 1
    print('  +0x4F - (max slot + 1), count byte +0x52 == records: %s' % sorted(rel.items()))
    for k, c in sorted(low.items()):
        print('  tex id %d type %d filter %x u8+12 %d  x%-4d e.g. %d  sampler name(s) %s' % (k[0], k[1], k[2], k[3], c, ex[k], k[4]))
    print('  engine-named sampler without a record at its slot: %s' % (', '.join('%s x%d (e.g. %d)' % (n, c, ex[('miss', n)]) for n, c in miss.items()) or 'none'))
    print('  materials with engine records - bytes +50 +51 +52, ordinary / engine records, position:')
    for k, c in sorted(cnt.items(), key=lambda kv: -kv[1])[:15]: print('    %s  x%d' % (k, c))
    # header bits +0x38..+0x4B: share among materials with a back-buffer record vs all others (a flag that
    # tells the renderer to resolve the back buffer first would be set in all of the first group)
    grp = {True: collections.Counter(), False: collections.Counter()}; tot = collections.Counter()
    for mid, (d, rb) in M.items():
        if len(d) < 0x60: continue
        g = any(t < lo and b == 9 for s, t, ty, b, f, u in records(d, rb, e)[2]); tot[g] += 1
        for w in range(0x38, 0x4C, 4):
            v = struct.unpack_from(e + 'I', d, w)[0]
            for bit in range(32):
                if v >> bit & 1: grp[g][(w, bit)] += 1
    print('  header bits, back-buffer materials (%d) vs others (%d), bits set in >= 90 %% of the first group:' % (tot[True], tot[False]))
    for (w, bit), c in sorted(grp[True].items()):
        if c >= 0.9 * tot[True]:
            print('    +%#x bit %2d  %4d / %d  others %4d / %d' % (w, bit, c, tot[True], grp[False][(w, bit)], tot[False]))
    bd = collections.Counter()
    for mid, (d, rb) in M.items():
        if len(d) < 0x60: continue
        rr = records(d, rb, e)[2]
        key = ('back' if any(t < lo and b == 9 for s, t, ty, b, f, u in rr) else '-',
               'depth' if any(t < lo and b == 10 for s, t, ty, b, f, u in rr) else '-',
               '+0x44 bit1' if struct.unpack_from(e + 'I', d, 0x44)[0] & 2 else 'no bit1')
        bd[key] += 1; ex.setdefault(('bd',) + key, mid)
    print('  +0x44 bit 1 by engine records (back buffer, depth buffer): %s' % ', '.join(
        '%s x%d (e.g. %d)' % ('/'.join(k), c, ex[('bd',) + k]) for k, c in sorted(bd.items())))
    print('    (+0x38 values in the first group: %s)' % sorted(collections.Counter(
        struct.unpack_from(e + 'I', d, 0x38)[0] for mid, (d, rb) in M.items() if len(d) >= 0x60 and
        any(t < lo and b == 9 for s, t, ty, b, f, u in records(d, rb, e)[2])).items()))


def main(argv):
    L = SM.load_libs(); X, P, XM, PM = L['X'], L['P'], L['XM'], L['PM']
    x2p = pickle.load(open(os.path.join(W, 'shader_x2p.pkl'), 'rb'))
    mx2p = pickle.load(open(os.path.join(W, 'material_x2p.pkl'), 'rb'))
    cmd = argv[0]
    opt = lambda k, dflt=None: argv[argv.index(k) + 1] if k in argv else dflt
    if cmd == 'names':
        kind = {'ps': 1, 'vs': 0}.get(opt('--kind', 'ps')); g = (opt('--grep') or '').lower()
        for pl, libs in (('x', X), ('p', P)):
            cnt = collections.Counter()
            for lid, lib in libs.items():
                if lib['kind'] != kind: continue
                for ri, n in samplers(lib, pl): cnt[(ri, n)] += 1
            print('== %s libraries (%s)' % ('Xbox base' if pl == 'x' else 'PC', opt('--kind', 'ps')))
            for (ri, n), c in sorted(cnt.items()):
                if g in n.lower(): print('  s%-2d %-50s %5d libs' % (ri, n, c))
    elif cmd == 'lib':
        inv = collections.defaultdict(list)
        for xid, pid in x2p.items(): inv[pid].append(xid)
        for pid in map(int, argv[1].split(',')):
            print('== PC lib %d  kind %s  <- Xbox base libs %s' % (pid, P[pid]['kind'] if pid in P else '?', sorted(inv.get(pid, []))))
            if pid in P:
                print('   PC  constants: %s' % ', '.join('%s%d x%d %s' % ('bics'[rs] if rs < 4 else '?', ri, rc, n)
                                                       for n, rs, ri, rc in sorted(lib_consts(P[pid], 'p'), key=lambda t: (t[1], t[2]))))
            for xid in sorted(inv.get(pid, [])):
                print('   Xbox %d constants: %s' % (xid, ', '.join('%s%d x%d %s' % ('bics'[rs] if rs < 4 else '?', ri, rc, n)
                                                    for n, rs, ri, rc in sorted(lib_consts(X[xid], 'x'), key=lambda t: (t[1], t[2])))))
    elif cmd == 'mats':
        mx = int(opt('--max', '20'))
        if opt('--pclib'):
            want = set(map(int, opt('--pclib').split(',')))
            sel = [m for m, (d, r) in PM.items() if want & set(SM.tuple_of(d, '<'))]
            pcsel = True
        else:
            if opt('--xlib'): want = set(map(int, opt('--xlib').split(',')))
            else:
                t = opt('--sampler').lower()
                want = {k for k, l in X.items() if l['kind'] == 1 and any(t in n.lower() for ri, n in samplers(l, 'x'))}
                print('Xbox pixel libs with a sampler containing %r: %d  %s' % (t, len(want), sorted(want)[:60]))
            sel = [m for m, (d, r) in XM.items() if want & set(SM.tuple_of(d))]
            pcsel = False
        p2x = {v: k for k, v in mx2p.items()}
        print('materials: %d' % len(sel))
        xown = {}
        if '--owners' in argv:   # Xbox DRM names holding the material (slow: reads the bigfile indexes)
            from shader_peer_report import owners
            xown = owners(os.path.join(W, '..', 'idx_xbox_base.json'), 'Tomb Raider Underworld (Xenon).txt')
        for m in sorted(sel)[:mx]:
            xm = p2x.get(m) if pcsel else m
            pm = m if pcsel else mx2p.get(m)
            print('  Xbox %s  PC %s  %s' % (xm, pm, ', '.join(sorted(xown.get(xm, ())))))
            if xm in XM: show('xbox', XM[xm][0], XM[xm][1], '>')
            if pm in PM: show('pc', PM[pm][0], PM[pm][1], '<')
    elif cmd == 'stats':
        lo = int(opt('--below', '100'))
        print('== Xbox base materials (%d)' % len(XM)); stats(XM, '>', X, 'x', lo)
        print('== PC materials (%d)' % len(PM)); stats(PM, '<', P, 'p', lo)
    elif cmd == 'one':
        import drm_write as DW
        e = '>' if argv[2] == 'be' else '<'
        D = DW.read(open(argv[1], 'rb').read(), argv[2])
        s = next(x for x in D.sections if x.type == 10 and x.id == int(argv[3]))
        show(argv[2], s.data, s.reloc, e)
        r = R.parse(s.reloc, argv[2])     # internal pointers: offset -> target (stored value), for layout checks
        print('    internal pointers %s' % ' '.join('+%x->%x(%x)' % (o, t, struct.unpack_from(e + 'I', s.data, o)[0]) for o, t in sorted(r.internal)))
        print('    id refs %d, kind A %d, external %d, size %d' % (len(r.idref), len(r.idref_a), len(r.external), len(s.data)))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
