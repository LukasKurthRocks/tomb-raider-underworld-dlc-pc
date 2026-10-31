"""Read-only report for translating DLC Xbox shader libraries (Xenos microcode) to PC (D3D9 SM3): finding 43, test 46
(DLC 2 fall column, material 24691, Xbox libs 2457 / 2458 / 2459, PC surrogates 1909 / 1910 / 1911).

Needs work/render/shaderlibs.pkl (X = base Xbox libs, P = base PC libs, D = DLC Xbox libs, XM / PM / DM materials) and
work/render/shader_x2p.pkl (base Xbox lib id -> PC lib id). The Xenos decoder is upstream's work/ws/xenos/xenos_xlat.py
(read-only use); the PC disassembly is Windows' d3dcompiler_47 (tools/shader_disasm.py).

Ids: Xbox and PC lib ids overlap - write d2457 (DLC Xbox), x1065 (base Xbox), p1909 (base PC); a bare id is looked
up DLC, base Xbox, base PC in that order. Register sets are printed b / i / f / s (bool, int4, float4, sampler).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/column_shader_report.py lib ID[,ID] [--out DIR]
      per library: kind, occupied slots, unique entries (hash), constant table, interpolators;
      with --out the full disassembly of every unique entry (Xenos: DIR/<d|x><id>_s<slot>.txt, PC: DIR/p<id>_s<slot>.asm)
  ../bin/pyt -t 900 tools/column_shader_report.py near DLCID [--top N]
      the base Xbox libraries closest to a DLC library: per occupied slot the Jaccard of the decoded instruction
      lines (multiset), plus identical-entry hits; with the PC id
  ../bin/pyt -t 900 tools/column_shader_report.py same DLCID
      base Xbox libs whose entry has the same decoded text as the DLC lib's, per slot
  ../bin/pyt -t 900 tools/column_shader_report.py grep TEXT KIND [--top N]      (KIND 0 VS, 1 PS)
      base Xbox libs with an entry whose decoded text contains TEXT
  ../bin/pyt -t 900 tools/column_shader_report.py diff ID_A ID_B [SLOT]
      line diff of two Xenos libraries (text form of xenos_xlat), slot SLOT (default first)
  ../bin/pyt -t 900 tools/column_shader_report.py pairs XID[,XID]
      per base Xbox lib: the PC lib (shader_x2p), slot occupancy Xbox vs PC, Xbox slot -> PC slots with the same
      constant table names
  ../bin/pyt -t 900 tools/column_shader_report.py regs NAME[,NAME] | all
      register conventions: per platform / stage / constant name the start registers and their counts
  ../bin/pyt -t 900 tools/column_shader_report.py flags
      PC entry size word: high 16 bits against shader features; checks flag == mask of dcl_cube samplers
  ../bin/pyt -t 1200 tools/column_shader_report.py pass0 [--top N]
      slot layouts of pass-0 PS libs, base Xbox vs PC (k kill, tN fetches, S shadow depth, V ViewportDepthScaleOffset)
  ../bin/pyt -t 600 tools/column_shader_report.py users ID[,ID]
      DLC and base Xbox materials whose shader tuple contains one of the lib ids
  ../bin/pyt -t 900 tools/column_shader_report.py vsparams
      VS MaterialParams count against material header word +0x3C / byte +0x50 (base Xbox materials)
"""
import sys, os, pickle, struct, collections, difflib
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'xenos'))
import xenos_xlat as XL
from shaderlib import constants, norm_name

W = os.path.join(ROOT, 'work', 'render')
_L = None


def libs():
    global _L
    if _L is None:
        _L = pickle.load(open(os.path.join(W, 'shaderlibs.pkl'), 'rb'))
        _L['x2p'] = pickle.load(open(os.path.join(W, 'shader_x2p.pkl'), 'rb'))
    return _L


def find(lid):
    """lid: int or 'd2457' / 'x1065' / 'p1909' (Xbox and PC lib ids overlap: a bare id is looked up D, X, P)"""
    L = libs()
    if isinstance(lid, str) and lid[:1].lower() in 'dxp':
        k = lid[0].upper(); n = int(lid[1:])
        return (k, L[k][n]) if n in L[k] else (None, None)
    lid = int(lid)
    for k in ('D', 'X', 'P'):
        if lid in L[k]: return k, L[k][lid]
    return None, None


def ids_arg(s):
    return [x if x[:1].lower() in 'dxp' else int(x) for x in s.split(',')]


def occ(lib): return [i for i, s in enumerate(lib['slots']) if s != 0xffffffff]


def uniq(lib):
    """[(first slot, [slots], entry)] in slot order"""
    seen = collections.OrderedDict()
    for i, s in enumerate(lib['slots']):
        if s == 0xffffffff: continue
        seen.setdefault(s, []).append(i)
    return [(v[0], v, lib['entries'][o]) for o, v in seen.items()]


def xtext(blob):
    sh = XL.parse(blob)
    return sh, XL.text(sh, 'pretty').lines


def pc_text(blob):
    import shader_disasm as SD
    from shader_const_fix import split_end
    body, _ = split_end(blob)
    return SD.disasm(body)


def cmd_lib(ids, out):
    for lid in ids:
        k, lib = find(lid)
        if lib is None: print('lib %s: not found' % lid); continue
        pl = 'p' if k == 'P' else 'x'
        o = occ(lib)
        print('== lib %s (%s, kind %d = %s) slots %d, occupied %s' % (lid, {'D': 'DLC Xbox', 'X': 'base Xbox', 'P': 'base PC'}[k],
              lib['kind'], 'VS' if lib['kind'] == 0 else 'PS', len(lib['slots']), o))
        if k == 'X': print('   PC lib (shader_x2p): %s' % libs()['x2p'].get(int(str(lid).lstrip('dxpDXP'))))
        for first, ss, e in uniq(lib):
            _, c = constants(e['blob'], pl)
            print('  entry slots %s hash %s size %d' % (ss, e['hash'].hex(), len(e['blob'])))
            for n, rs, ri, rc in sorted(c, key=lambda x: (x[1], x[2])):
                print('     %s%-3d x%d  %s' % ('bifs'[rs], ri, rc, n))
            if pl == 'x':
                sh, lines = xtext(e['blob'])
                print('     interp %s  outputs %s' % (sh.interp, getattr(sh, 'outputs', None)))
                print('     defs %s' % sh.defs)
                print('     summary %s' % dict(XL.summary(sh)))
                if out:
                    os.makedirs(out, exist_ok=True)
                    open(os.path.join(out, '%s_s%d.txt' % (lid if isinstance(lid, str) else k.lower() + str(lid), first)), 'w').write('\n'.join(lines) + '\n')
            elif out:
                os.makedirs(out, exist_ok=True)
                open(os.path.join(out, '%s_s%d.asm' % (lid if isinstance(lid, str) else 'p' + str(lid), first)), 'w').write(pc_text(e['blob']))


def shape(blob):
    """instruction multiset of a Xenos entry: the text lines with register numbers kept (they are the program)"""
    try:
        _, lines = xtext(blob)
    except Exception:
        return collections.Counter()
    return collections.Counter(l.strip() for l in lines if l.strip() and not l.strip().startswith('//'))


def jac(a, b):
    i = sum((a & b).values()); u = sum((a | b).values())
    return i / u if u else 0.0


def cmd_near(did, top):
    L = libs(); d = L['D'][did]; dk = d['kind']
    dsh = {i: shape(d['entries'][d['slots'][i]]['blob']) for i in occ(d)}
    dh = {d['entries'][d['slots'][i]]['hash'] for i in occ(d)}
    res = []
    for xid, x in L['X'].items():
        if x['kind'] != dk: continue
        xo = occ(x)
        if not xo: continue
        xh = {x['entries'][x['slots'][i]]['hash'] for i in xo}
        sc = []
        for i, a in dsh.items():
            if i in xo: sc.append(jac(a, shape(x['entries'][x['slots'][i]]['blob'])))
            else: sc.append(0.0)
        res.append((sum(sc) / len(sc), xid, len(dh & xh), xo, sc))
    res.sort(reverse=True)
    print('DLC lib %d kind %d occupied %s' % (did, dk, sorted(dsh)))
    for s, xid, same, xo, sc in res[:top]:
        print('  base Xbox %5d  score %.3f  identical entries %d  occupied %s  per slot %s  -> PC %s'
              % (xid, s, same, xo, ' '.join('%.2f' % v for v in sc), L['x2p'].get(xid)))


def cmd_same(did):
    """base Xbox libs whose entries have the same decoded text as the DLC lib's (per slot), any register naming kept"""
    L = libs(); d = L['D'][did]
    dt = {i: tuple(xtext(d['entries'][d['slots'][i]]['blob'])[1]) for i in occ(d)}
    byslot = collections.defaultdict(list)
    for xid, x in L['X'].items():
        if x['kind'] != d['kind']: continue
        for i, t in dt.items():
            if i < len(x['slots']) and x['slots'][i] != 0xffffffff:
                try:
                    if tuple(xtext(x['entries'][x['slots'][i]]['blob'])[1]) == t: byslot[i].append(xid)
                except Exception:
                    pass
    for i in sorted(dt):
        print('DLC %d slot %d: same text in base Xbox libs %s' % (did, i, ['%d->PC %s' % (x, L['x2p'].get(x)) for x in byslot[i][:20]]))
    full = set.intersection(*[set(byslot[i]) for i in dt]) if dt else set()
    print('all slots equal: %s' % ['%d->PC %s' % (x, L['x2p'].get(x)) for x in sorted(full)])


def cmd_grep(text, kind, top):
    """base Xbox libs (kind 0 VS / 1 PS) with an entry whose decoded text contains TEXT (plain substring)"""
    L = libs(); n = 0
    for xid in sorted(L['X']):
        x = L['X'][xid]
        if x['kind'] != kind: continue
        hit = []
        for first, ss, e in uniq(x):
            try:
                if text in '\n'.join(xtext(e['blob'])[1]): hit.append(first)
            except Exception:
                pass
        if hit:
            n += 1
            if n <= top: print('  base Xbox %5d slots %s -> PC %s' % (xid, hit, L['x2p'].get(xid)))
    print('libs with a hit: %d' % n)


def cmd_diff(a, b, slot):
    ka, la = find(a); kb, lb = find(b)
    sa = slot if slot is not None else occ(la)[0]; sb = slot if slot is not None else occ(lb)[0]
    _, A = xtext(la['entries'][la['slots'][sa]]['blob']); _, B = xtext(lb['entries'][lb['slots'][sb]]['blob'])
    for l in difflib.unified_diff(A, B, '%s_s%d' % (a, sa), '%s_s%d' % (b, sb), n=2, lineterm=''):
        print(l)
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    print('// ratio %.3f  lines %d / %d' % (sm.ratio(), len(A), len(B)))


def cmd_pairs(ids):
    L = libs()
    for xid in ids:
        x = L['X'][xid]; pid = L['x2p'].get(xid); p = L['P'].get(pid)
        print('== Xbox %d -> PC %s; Xbox slots %d occupied %s; PC slots %s occupied %s'
              % (xid, pid, len(x['slots']), occ(x), len(p['slots']) if p else '-', occ(p) if p else '-'))
        if not p: continue
        for i in occ(x):
            _, cx = constants(x['entries'][x['slots'][i]]['blob'], 'x')
            nx = sorted((norm_name(n), rs, ri) for n, rs, ri, rc in cx)
            same = []
            for j in occ(p):
                _, cp = constants(p['entries'][p['slots'][j]]['blob'], 'p')
                if sorted((norm_name(n), rs, ri) for n, rs, ri, rc in cp) == nx: same.append(j)
            print('   Xbox slot %3d (%d constants) -> PC slots with the same constant table: %s' % (i, len(nx), same))


def cmd_regs(names):
    """register conventions: per platform, lib kind and constant name, how often each start register occurs
    (over every unique entry of every base library); names = comma list or 'all'"""
    L = libs()
    for k, pl in (('X', 'x'), ('P', 'p')):
        cnt = collections.defaultdict(collections.Counter)
        for lid, lib in L[k].items():
            for first, ss, e in uniq(lib):
                _, c = constants(e['blob'], pl)
                for n, rs, ri, rc in c:
                    nn = norm_name(n) if rs == 3 else n
                    if names != 'all' and nn not in names: continue
                    cnt[(('VS', 'PS')[lib['kind']], 'bifs'[rs], nn)][ri] += 1
        print('== %s' % {'X': 'base Xbox', 'P': 'base PC'}[k])
        for key in sorted(cnt):
            print('  %s %s %-28s %s' % (key[0], key[1], key[2], ' '.join('%s%d:%d' % (key[1], r, n) for r, n in cnt[key].most_common(6))))


def cmd_flags():
    """PC entry size word: low 16 bits = entry bytes (8 header + 8 hash + code), high bits = flags. Which shader
    features go with each flag value (over all unique base PC entries)"""
    L = libs(); cnt = collections.Counter(); ex = {}
    for lid, lib in L['P'].items():
        for first, ss, e in uniq(lib):
            fl = e['size'] >> 16
            names = [n for n, rs, ri, rc in constants(e['blob'], 'p')[1]]
            samp = [n for n, rs, ri, rc in constants(e['blob'], 'p')[1] if rs == 3]
            feats = (('VS', 'PS')[lib['kind']], fl,
                     'backbuffer' if any('BackBuffer' in n for n in samp) else '-',
                     'depthbuffer' if any('DepthBuffer' in n for n in samp) else '-',
                     'ScreenExtents' if 'ScreenExtents' in names else '-',
                     'nsamp>8' if len(samp) > 8 else '-')
            cnt[feats] += 1; ex.setdefault(feats, (lid, first))
    for k, n in sorted(cnt.items(), key=lambda x: (x[0][0], x[0][1], -x[1])):
        print('  %s flag %#x %-11s %-12s %-14s %-8s : %5d entries (e.g. PC lib %d slot %d)' % (k + (n,) + ex[k]))
    # hypothesis: flag = bit mask of the sampler registers declared dcl_cube
    sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'shader4'))
    import sm3asm, sm3dis
    agree = collections.Counter(); bad = []
    for lid, lib in L['P'].items():
        if lib['kind'] != 1: continue
        for first, ss, e in uniq(lib):
            b = e['blob'][:sm3dis.bytecode_len(e['blob'])]
            cube = 0
            for i in sm3asm.decode(b).instrs():
                if i.op == 'dcl' and i.ops[0].rtype == sm3asm.RT_SAMPLER and (i.usage >> 27) & 15 == 3: cube |= 1 << i.ops[0].num
            ok = cube == e['size'] >> 16
            agree[ok] += 1
            if not ok and len(bad) < 8: bad.append((lid, first, hex(e['size'] >> 16), hex(cube)))
    print('flag == mask of dcl_cube samplers: %d entries yes, %d no %s' % (agree[True], agree[False], bad))


def feat_x(b):
    """short feature string of a Xenos PS entry: k = kill, t = texture fetches, e = exports r5 (shadow depth)"""
    t = '\n'.join(xtext(b)[1])
    return '%s%s%s' % ('k' if 'clip(' in t else '-', 't%d' % t.count('tfetch'), 'S' if 'ShadowDepthBias' in t or 'r5.x' in t else '-')


def feat_p(b):
    sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'shader4'))
    import sm3dis
    t = pc_text(b[:sm3dis.bytecode_len(b)])
    names = [n for n, rs, ri, rc in constants(b, 'p')[1]]
    return '%s%s%s%s' % ('k' if 'texkill' in t else '-', 't%d' % t.count('texld'), 'S' if 'ShadowDepthBias' in names else '-',
                         'V' if 'ViewportDepthScaleOffset' in names else '-')


def cmd_pass0(top):
    """slot layout of pass-0 pixel-shader libraries (material +0x28), base Xbox vs PC, grouped by slot counts and the
    per-slot features (k kill, tN texture fetches, S shadow-depth output, V ViewportDepthScaleOffset)"""
    import struct as _s
    L = libs(); mx2p = pickle.load(open(os.path.join(W, 'material_x2p.pkl'), 'rb'))
    seen = set(); groups = collections.Counter(); ex = {}
    for mid, (d, r) in L['XM'].items():
        x0 = _s.unpack_from('>I', d, 0x28)[0]; pm = mx2p.get(mid)
        if not x0 or pm not in L['PM'] or x0 in seen: continue
        p0 = _s.unpack_from('<I', L['PM'][pm][0], 0x28)[0]
        if x0 not in L['X'] or p0 not in L['P']: continue
        seen.add(x0); X, P = L['X'][x0], L['P'][p0]
        fx = tuple(feat_x(X['entries'][X['slots'][k]]['blob']) if X['slots'][k] != 0xffffffff else '.' for k in range(len(X['slots'])))
        fp = tuple(feat_p(P['entries'][P['slots'][k]]['blob']) if P['slots'][k] != 0xffffffff else '.' for k in range(len(P['slots'])))
        key = (len(X['slots']), len(P['slots']), fx, fp); groups[key] += 1; ex.setdefault(key, (x0, p0))
    for k, n in groups.most_common(top):
        print('  Xbox %d slots %s | PC %d slots %s : %d libs (e.g. Xbox %d -> PC %d)' % (k[0], ' '.join(k[2]), k[1], ' '.join(k[3]), n, ex[k][0], ex[k][1]))


def cmd_users(ids):
    """DLC (DM) and base Xbox (XM) materials whose shader tuple (+0x28..+0x34) contains one of the lib ids"""
    import struct as _s
    L = libs()
    for k in ('DM', 'XM'):
        for mid, (d, r) in sorted(L[k].items()):
            t = _s.unpack_from('>4I', d, 0x28)
            if set(t) & ids: print('  %s material %d tuple %s' % ({'DM': 'DLC', 'XM': 'base Xbox'}[k], mid, t))


def cmd_vsparams():
    """which material header word goes with a vertex shader that reads MaterialParams: over all base Xbox materials,
    (VS MaterialParams register count) against the header words +0x38 / +0x3C / +0x40 and byte +0x50"""
    import struct as _s
    L = libs(); cnt = collections.Counter(); vsn = {}
    for mid, (d, r) in L['XM'].items():
        vs = _s.unpack_from('>I', d, 0x34)[0]
        if vs not in L['X']:
            continue
        if vs not in vsn:
            n = 0
            for first, ss, e in uniq(L['X'][vs]):
                for nm, rs, ri, rc in constants(e['blob'], 'x')[1]:
                    if nm == 'MaterialParams': n = max(n, rc)
            vsn[vs] = n
        w = _s.unpack_from('>3I', d, 0x38)
        cnt[(vsn[vs], w[1], d[0x50])] += 1
    print('  (VS MaterialParams count, word +0x3C, byte +0x50): materials')
    for k, n in sorted(cnt.items()): print('   %s: %d' % (k, n))


def main(argv):
    out = None; top = 15
    if '--out' in argv: k = argv.index('--out'); out = argv[k + 1]; del argv[k:k + 2]
    if '--top' in argv: k = argv.index('--top'); top = int(argv[k + 1]); del argv[k:k + 2]
    c = argv[0]
    if c == 'lib': cmd_lib(ids_arg(argv[1]), out)
    elif c == 'near': cmd_near(int(argv[1]), top)
    elif c == 'same': cmd_same(int(argv[1]))
    elif c == 'grep': cmd_grep(argv[1], int(argv[2]), top)
    elif c == 'flags': cmd_flags()
    elif c == 'vsparams': cmd_vsparams()
    elif c == 'users': cmd_users({int(x) for x in argv[1].split(',')})
    elif c == 'pass0': cmd_pass0(top)
    elif c == 'regs': cmd_regs(argv[1] if argv[1] == 'all' else set(argv[1].split(',')))
    elif c == 'diff': cmd_diff(ids_arg(argv[1])[0], ids_arg(argv[2])[0], int(argv[3]) if len(argv) > 3 else None)
    elif c == 'pairs': cmd_pairs([int(x) for x in argv[1].split(',')])
    else: sys.exit(__doc__)


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
