"""Systematic scan for the script-class fault family of the thrall unload crash (2026-11-04, workspace docs
Befund-Thrall-Absturz.md sections 9 / 11, WINDOWS_REBUILD.md finding 45): a DLC script class that runs on the PC
against a base class (or a copy of itself) whose layout differs from the one it was compiled against. Read-only.

Rule of the engine: the first loaded section of an id wins. A script id held by an always-loaded PC DRM (RESIDENT,
e.g. the installed generalbank.drm) is never taken from a DLC DRM; the DLC copy is dropped, and
  * DLC classes deriving from it run on the RESIDENT layout (instance size, members, vtable size),
  * pointer relocations of other DLC sections into the dropped copy (functions / prototypes / members by offset)
    resolve against the resident section (the material case of tests 25d/25e: the first loaded copy wins).
The DLC classes were compiled (on the Xbox) against the Xbox layout of their bases, so the reference is the Xbox
original of each DRM (paired by section position with the converted PC DRM), not the converted copy: the converter
copies many base scripts as the PC version (e.g. script 93 with the PC-only vtable slot 31), which hides the
difference in a converted-vs-resident comparison (tools/script_resident_clash.py).

For every converted DLC script D that is NOT resident (it is the copy in use) the scan follows both class chains,
PC (resident first, then the DRM's own copy, then any scanned DRM) and Xbox (the Xbox DRM's own copy, then the Xbox
generalbank), level by level, and reports each level whose PC-resolved layout differs from the Xbox one:
  inst   'same' | 'relaid' (the converter laid D out on this PC base: D's PC size - Xbox size = the base's, no own
         member below the PC base size - the DLC 1 / B138 pattern, played) | 'appended' (resident members = Xbox
         members + more at the end, no own member below the PC size) | 'OVERLAP' (own members of D or of a DLC class
         between D and the ancestor below the PC base size: the thrall crash class) | 'MOVED' (inherited members
         differ in offset / kind, D not re-laid)
  vt     'same' | 'short+N' (resident has N more slots, D adds no own slots: base code calling those slots on D reads
         past D's table) | 'SHIFT+N' (resident has N more slots and D / its DLC chain add own slots: the resident's
         extra slots and D's own slots share indices) | 'fixed+N' (D's PC vtable already has the N slots)
         | 'LESS-N' (resident has fewer slots)
For every RESIDENT script id that a DLC DRM also carries with other content (normalised: data + relocations by
(type, id), not by section index) it reports the dropped copy: Xbox and converted layout vs resident, and every
external relocation of the other sections of that DRM into it, mapped to its element (function / prototype /
member / vtable entry ... by array, ordinal and index) - 'MISMATCH' when the resident section holds another element
(or another offset of the same element) at that offset.

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/script_layout_clash.py RESIDENT[,RESIDENT2] [packNN:]TREE [[packNN:]TREE ...]
        [--xgb xbox:generalbank.drm] [--json OUT.json] [--out OUT.txt] [--quiet] [--pcindex]
  RESIDENT  installed generalbank.drm (or pc:generalbank.drm) and other always-loaded DRMs, comma separated
  packNN:   Xbox pack that wins for names present in several packs (pack10 = DLC 1, pack11 = DLC 2; finding 38)
  TREE      a mods folder; every *.drm below it (sub folders included)
  --xgb     Xbox generalbank used for Xbox base classes a DLC DRM does not carry (default xbox:generalbank.drm =
            title update first)
  --pcindex also list DLC script ids (not resident) that PC base-game DRMs (work/idx_pc.json) hold with another
            section size - a screen for the co-loaded (not always-loaded) case
Output: per resident id the dropped-copy lines, per (ancestor, Xbox layout, PC layout) the derived DLC classes with
the inst / vt verdict, a summary; --json the same as data.
"""
import sys, os, struct, json, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL

_LAY = {}


def lay(d, rl, e):
    """layout of a script section: self, base, size, align, members [(off, nib)], member tags, vt, nfunc, protos
    [(vtIndex, sym)], native name"""
    key = (hashlib.md5(d + rl).digest(), e)
    if key in _LAY: return _LAY[key]
    E = '>' if e == 'be' else '<'
    if len(d) < 0x48: _LAY[key] = None; return None
    rel = R.parse(rl, e)
    it = dict(rel.internal); ids = rel.id_offsets()

    def u32(o): return struct.unpack_from(E + 'I', d, o)[0]

    def u16(o): return struct.unpack_from(E + 'H', d, o)[0]
    mem = []
    if 0x2c in it:
        t = it[0x2c]
        for k in range(u32(t - 4)):
            a = t + 20 * k
            if a + 20 > len(d): break
            mem.append((u16(a + 12), u32(a) & 0xf))
    protos = []
    if 0x34 in it:
        t = it[0x34]
        for k in range(u32(t - 4)):
            a = t + 28 * k
            if a + 28 > len(d): break
            protos.append((u16(a + 6), u16(a + 8)))
    nat = None
    if 0x10 in it:
        o = it[0x10]; z = d.find(b'\0', o)
        nat = d[o:z].decode('latin-1') if z > o else None
    r = dict(self=u32(0x14) if 0x14 in ids else None, base=u32(0x18) if 0x18 in ids else None,
             size=u16(0x1c), align=u16(0x1e), mem=tuple(mem), vt=u16(0x3c),
             nfunc=u32(it[0x38] - 4) if 0x38 in it else 0, protos=tuple(protos), native=nat)
    _LAY[key] = r
    return r


def lkey(L):
    return None if L is None else (L['size'], L['align'], L['mem'], L['vt'])


def norm(S, i):
    """content hash of section i of section list S with external relocations by (type, id) instead of index"""
    t, sid, d, rl = S[i][:4]
    e = S[i][4] if len(S[i]) > 4 else 'le'
    h = hashlib.md5(d)
    if rl:
        rel = R.parse(rl, e)
        h.update(repr(sorted(rel.internal)).encode())
        h.update(repr(sorted((S[si][0], S[si][1], so, do) if si < len(S) else ('?', si, so, do)
                             for si, so, do in rel.external)).encode())
        h.update(repr((sorted(rel.idref), sorted(rel.idref_a))).encode())
    return h.hexdigest()


def diff(Sa, ia, Sb, ib):
    """what differs between two copies of a script: data length / changed words, internal / external (by type, id) /
    id relocations; 'struct' = same length and same internal relocations (every element at the same offset)"""
    a, b = Sa[ia], Sb[ib]
    ra, rb = R.parse(a[3], a[4]), R.parse(b[3], b[4])
    out = {}
    if len(a[2]) != len(b[2]): out['len'] = '%d vs %d' % (len(a[2]), len(b[2]))
    else:
        out['words'] = sum(a[2][o:o + 4] != b[2][o:o + 4] for o in range(0, len(a[2]), 4))
    out['internal'] = sorted(ra.internal) == sorted(rb.internal)

    def ext(S, r): return sorted((S[si][0], S[si][1], so, do) if si < len(S) else ('?', si, so, do) for si, so, do in r.external)
    out['external'] = ext(Sa, ra) == ext(Sb, rb)
    out['idref'] = (sorted(ra.idref), sorted(ra.idref_a)) == (sorted(rb.idref), sorted(rb.idref_a))
    out['struct'] = 'len' not in out and out['internal']
    return out


_EL = {}


def elements(d, rl, e):
    """[(start, end, name, ordinal, elemsize)] of the script's arrays (script_conv.Walk) + vtable entries"""
    key = (hashlib.md5(d + rl).digest(), e)
    if key in _EL: return _EL[key]
    import script_conv as SC
    E = '>' if e == 'be' else '<'
    rel = R.parse(rl, e)
    try: W = SC.Walk(d, rel, e).run()
    except Exception: _EL[key] = None; return None
    out = []; ordn = collections.Counter()
    for name, t, n, sz in W.arrays:
        out.append((t, t + n * sz, name, ordn[name], sz)); ordn[name] += 1
    it = dict(rel.internal)
    if 0x44 in it:
        t = it[0x44]; n = struct.unpack_from(E + 'H', d, 0x3c)[0]
        for k in range(n):
            s = it.get(t + 4 * k)
            if s is not None and s + 4 <= len(d):
                c = struct.unpack_from(E + 'I', d, s)[0]
                if c < 64: out.append((s, s + 4 + 4 * c, 'vte', k, 4 + 4 * c))
    _EL[key] = out
    return out


def el_of(els, o):
    """element key of offset o: ('root', o) | (array name, ordinal, index, delta)"""
    if o < 0x54: return ('root', o)
    best = None
    for t, end, name, ordn, sz in els:
        if t <= o < end and (best is None or end - t < best[1] - best[0]):
            best = (t, end, name, ordn, sz)
        elif o == t - 4 and best is None:
            best = (t, t, name, ordn, sz)
    if best is None: return None
    t, end, name, ordn, sz = best
    if o < t: return (name, ordn, -1, 0)
    return (name, ordn, (o - t) // sz, (o - t) % sz)


def el_off(els, key):
    if key is None: return None
    if key[0] == 'root': return key[1]
    name, ordn, idx, delta = key
    for t, end, nm, od, sz in els:
        if nm == name and od == ordn:
            if idx == -1: return t - 4
            o = t + idx * sz + delta
            return o if o < end or (end == t and idx == 0) else None
    return None


def load_resident(spec):
    res = {}
    for r in spec.split(','):
        S, e = FL.sections(r)
        S = [q + (e,) for q in S]
        for i, q in enumerate(S):
            if q[0] == 8 and q[2] and q[1] not in res:
                res[q[1]] = dict(src=os.path.basename(r), S=S, i=i, e=e, lay=lay(q[2], q[3], e), norm=norm(S, i))
    return res


def xbox_secs(rel, pack):
    import convert_dlc as CD
    from drm import cdrm_decode, sections_with_data
    old = os.environ.get('TRUDLC_PACK_FIRST')
    if pack: os.environ['TRUDLC_PACK_FIRST'] = pack
    try: raw, _ = CD.raw_dlc(rel.replace('/', '\\'))
    finally:
        if pack is None: pass
        elif old is None: os.environ.pop('TRUDLC_PACK_FIRST', None)
        else: os.environ['TRUDLC_PACK_FIRST'] = old
    if raw is None: return None
    return [(s['type'], s['id'], s['data'], s['reloc'], 'be') for s in sections_with_data(cdrm_decode(raw, 'be'), 'be')[1]]


def pair(S, X):
    """{PC section index: Xbox section index} by position (all types equal), else type-8 sections by their order"""
    if X is None: return {}
    if len(S) == len(X) and all(a[0] == b[0] for a, b in zip(S, X)): return {i: i for i in range(len(S))}
    a = [i for i, q in enumerate(S) if q[0] == 8]; b = [i for i, q in enumerate(X) if q[0] == 8]
    return dict(zip(a, b)) if len(a) == len(b) else {}


def drms(tree):
    for dp, dn, fn in os.walk(tree):
        dn.sort()
        for f in sorted(fn):
            if f.lower().endswith('.drm'):
                p = os.path.join(dp, f)
                yield p, os.path.relpath(p, tree).replace(os.sep, '/')


def chain(start, getter, limit=24):
    """[(id, layout, where)] from the base id start upwards"""
    out = []; seen = set(); b = start
    while b is not None and b not in seen and len(out) < limit:
        seen.add(b)
        L, where = getter(b)
        out.append((b, L, where))
        if L is None: break
        b = L['base']
    return out


def verdict(D_pc, D_x, between_pc, X_l, P_l):
    """inst / vt verdict for DLC class D whose ancestor is X_l (Xbox) / P_l (PC-resolved)"""
    # instance
    if X_l['size'] == P_l['size'] and X_l['mem'] == P_l['mem']: inst = 'same'
    else:
        own = [o for L in between_pc for o, nib in L['mem']]
        low = [o for o in own if o < P_l['size']]
        if low: inst = 'OVERLAP(%d own members below %d)' % (len(low), P_l['size'])
        elif D_x and D_pc['size'] - D_x['size'] == P_l['size'] - X_l['size']:
            inst = 'relaid'         # the converter laid D out on this PC base (size + own offsets follow it)
        elif P_l['mem'][:len(X_l['mem'])] == X_l['mem'] and P_l['size'] >= X_l['size']: inst = 'appended'
        else: inst = 'MOVED'
    # vtable
    dv = P_l['vt'] - X_l['vt']
    if dv == 0: vt = 'same'
    elif dv < 0: vt = 'LESS%d' % dv
    else:
        own_slots = (D_x['vt'] if D_x else D_pc['vt']) - X_l['vt']
        if D_x and D_pc['vt'] - D_x['vt'] >= dv: vt = 'fixed+%d' % dv
        elif own_slots <= 0: vt = 'short+%d' % dv
        else: vt = 'SHIFT+%d(own %d)' % (dv, own_slots)
    return inst, vt


def main(argv):
    quiet = '--quiet' in argv; argv = [a for a in argv if a != '--quiet']
    pcindex = '--pcindex' in argv; argv = [a for a in argv if a != '--pcindex']
    jout = None; xgb = 'xbox:generalbank.drm'
    if '--json' in argv: k = argv.index('--json'); jout = argv[k + 1]; del argv[k:k + 2]
    if '--xgb' in argv: k = argv.index('--xgb'); xgb = argv[k + 1]; del argv[k:k + 2]
    if '--out' in argv:          # the text report to a file (utf-8) instead of the console
        k = argv.index('--out'); sys.stdout = open(argv[k + 1], 'w', encoding='utf-8'); del argv[k:k + 2]
    res = load_resident(argv[0])
    print('resident: %s, %d scripts' % (argv[0], len(res)))
    XG, xe = FL.sections(xgb)
    xgb_by = {q[1]: lay(q[2], q[3], xe) for q in XG if q[0] == 8 and q[2]}
    print('xbox generalbank: %s, %d scripts' % (xgb, len(xgb_by)))
    trees = []
    for a in argv[1:]:
        pk = None
        if a.startswith('pack') and ':' in a[:8]: pk, a = a.split(':', 1)
        trees.append((pk, a))
    # pass 1: every DRM, its sections and the Xbox pairing
    files = []
    glob_pc = {}
    res_names = {os.path.basename(r.split(':')[-1]).lower() for r in argv[0].split(',')}
    for pk, tree in trees:
        for p, rel in drms(tree):
            if os.path.basename(p).lower() in res_names: continue      # the resident bank itself (B138 ships one)
            try:
                S, e = FL.sections(p); S = [q + (e,) for q in S]
            except Exception as x:
                print('%s: read failed %s' % (rel, x)); continue
            if not any(q[0] == 8 and q[2] for q in S): continue
            try: X = xbox_secs(rel, pk)
            except Exception as x: X = None; print('%s: xbox read failed %s' % (rel, x))
            files.append((pk, tree, rel, S, X, pair(S, X)))
            for i, q in enumerate(S):
                if q[0] == 8 and q[2] and q[1] not in glob_pc: glob_pc[q[1]] = lay(q[2], q[3], e)
    print('trees: %s; %d DRMs with scripts' % (', '.join('%s:%s' % (pk or '-', t) for pk, t in trees), len(files)))
    st = collections.Counter()
    dropped = collections.OrderedDict()          # resident id -> {...}
    derived = collections.OrderedDict()          # (anc pc id, xbox key, pc key, where) -> {...}
    unpaired = []
    for pk, tree, rel, S, X, P in files:
        if X is None: unpaired.append(rel + ' (no Xbox original)')
        elif not P: unpaired.append(rel + ' (sections not paired)')
        own_pc = {q[1]: i for i, q in enumerate(S) if q[0] == 8 and q[2]}
        own_x = {}
        if X:
            for i, q in enumerate(X):
                if q[0] == 8 and q[2]: own_x.setdefault(q[1], i)
        # dropped copies: resident ids with other content
        bad_ids = {}
        for sid, i in own_pc.items():
            if sid not in res: continue
            r = res[sid]
            if norm(S, i) == r['norm']: st['resident id, identical copy'] += 1; continue
            Lc = lay(S[i][2], S[i][3], 'le'); Lx = None
            if i in P: Lx = lay(X[P[i]][2], X[P[i]][3], 'be')
            dd = diff(S, i, r['S'], r['i'])
            bad_ids[sid] = (i, dd['struct'])
            g = dropped.setdefault(sid, dict(res_lay=r['lay'], groups=collections.OrderedDict(), relocs=collections.Counter(),
                                             mism=[], drms=[]))
            gk = (repr(lkey(Lx)), repr(lkey(Lc)), repr(sorted(dd.items())))
            g['groups'].setdefault(gk, dict(x=Lx, c=Lc, diff=dd, drms=[]))['drms'].append(rel)
            g['drms'].append(rel)
            st['resident id, other copy'] += 1
        # external relocations of the other sections into the dropped copies
        for k, q in enumerate(S):
            if not q[3] or (q[0] == 8 and q[1] in bad_ids and own_pc.get(q[1]) == k): continue
            rl = R.parse(q[3], 'le')
            for si, so, do in rl.external:
                if si >= len(S): continue
                t = S[si]
                if t[0] != 8 or t[1] not in bad_ids or own_pc[t[1]] != si: continue
                g = dropped[t[1]]; r = res[t[1]]
                if bad_ids[t[1]][1]:                # same length + internal relocations: every offset is the same element
                    g['relocs']['same offset (same structure)'] += 1; continue
                el_c = elements(t[2], t[3], 'le')
                el_r = elements(r['S'][r['i']][2], r['S'][r['i']][3], r['e'])
                key = el_of(el_c, do) if el_c is not None else None
                ro = el_off(el_r, key) if el_r is not None else None
                if key is not None and ro == do: g['relocs']['same element'] += 1
                else:
                    kr = el_of(el_r, do) if el_r is not None else None
                    g['relocs']['MISMATCH'] += 1
                    if len(g['mism']) < 12:
                        g['mism'].append('%s: %d:%d +0x%x -> +0x%x = %s in the DLC copy, resident %s (resident at +0x%x: %s)' % (
                            rel, q[0], q[1], so, do, key, 'at +0x%x' % ro if ro is not None else 'has no such element',
                            do, kr))
        # derived classes: every DLC script in use (not resident)
        for sid, i in own_pc.items():
            if sid in res: continue
            D = lay(S[i][2], S[i][3], 'le')
            if D is None or D['base'] is None: continue
            Dx = None; xi = P.get(i)
            if xi is not None: Dx = lay(X[xi][2], X[xi][3], 'be')
            st['DLC classes with a base'] += 1

            def gpc(b):
                if b in res: return res[b]['lay'], 'res'
                if b in own_pc: return lay(S[own_pc[b]][2], S[own_pc[b]][3], 'le'), 'own'
                if b in glob_pc: return glob_pc[b], 'other'
                return None, 'missing'

            def gx(b):
                if b in own_x: return lay(X[own_x[b]][2], X[own_x[b]][3], 'be'), 'own'
                if b in xgb_by: return xgb_by[b], 'xgb'
                return None, 'missing'
            cp = chain(D['base'], gpc)
            cx = chain(Dx['base'], gx) if Dx else []
            if not cx: st['DLC classes without Xbox chain'] += 1; continue
            between = [D]
            for lev, ((pid, PL, pw), (xid, XL, xw)) in enumerate(zip(cp, cx)):
                if PL is None or XL is None:
                    st['chain level missing'] += 1; break
                if lkey(PL) != lkey(XL):
                    inst, vt = verdict(D, Dx, between, XL, PL)
                    dk = (pid, xid, repr(lkey(XL)), repr(lkey(PL)), pw)
                    g = derived.setdefault(dk, dict(anc=pid, xid=xid, x=XL, p=PL, where=pw, cls=collections.OrderedDict()))
                    c = g['cls'].setdefault(sid, dict(level=lev, vt_pc=D['vt'], vt_x=Dx['vt'], size=D['size'],
                                                      verdicts=collections.Counter(), drms=[]))
                    c['verdicts'][(inst, vt)] += 1; c['drms'].append(rel)
                    st['derived findings'] += 1
                between.append(PL)
            if len(cp) != len(cx): st['chain length differs'] += 1
    # report
    print('\n== resident ids carried by DLC DRMs with other content (the DLC copy is dropped)')
    for sid, g in dropped.items():
        r = g['res_lay']
        print('script %d: resident size %d align %d members %d vt %d base %s funcs %d native %s; %d DRMs; relocations into the '
              'dropped copy: %s' % (sid, r['size'], r['align'], len(r['mem']), r['vt'], r['base'], r['nfunc'], r['native'],
                                    len(g['drms']), dict(g['relocs']) or '-'))
        for gk, gg in g['groups'].items():
            for tag, L in (('xbox', gg['x']), ('conv', gg['c'])):
                if L is None: print('   %s: -' % tag); continue
                dl = []
                if L['size'] != r['size']: dl.append('size %d' % L['size'])
                if L['mem'] != r['mem']:
                    dl.append('members %d%s' % (len(L['mem']), '' if r['mem'][:len(L['mem'])] == L['mem'] else ' (offsets/kinds differ)'))
                if L['vt'] != r['vt']: dl.append('vt %d' % L['vt'])
                if L['nfunc'] != r['nfunc']: dl.append('funcs %d' % L['nfunc'])
                if L['base'] != r['base'] and tag == 'conv': dl.append('base %s' % L['base'])
                print('   %s: %s' % (tag, ', '.join(dl) or 'layout same as resident'))
            print('   conv vs resident bytes: %s' % ', '.join('%s %s' % kv for kv in sorted(gg['diff'].items())))
            if not quiet: print('   DRMs (%d): %s' % (len(gg['drms']), ', '.join(gg['drms'][:8]) + (' ...' if len(gg['drms']) > 8 else '')))
        for m in g['mism']: print('   ' + m)
    print('\n== DLC classes whose PC-resolved ancestor differs from the Xbox one they were compiled against')
    for dk, g in derived.items():
        XL, PL = g['x'], g['p']
        print('ancestor PC %d (Xbox %d, PC copy from %s): Xbox size %d members %d vt %d / PC size %d members %d vt %d native %s; '
              '%d DLC classes' % (g['anc'], g['xid'], g['where'], XL['size'], len(XL['mem']), XL['vt'], PL['size'], len(PL['mem']),
                                  PL['vt'], PL['native'], len(g['cls'])))
        for sid, c in g['cls'].items():
            v = ', '.join('%s/%s x%d' % (a, b, n) for (a, b), n in c['verdicts'].items())
            print('   class %6d level %d size %d vt PC %d Xbox %d: %s (%d DRMs: %s%s)' % (
                sid, c['level'], c['size'], c['vt_pc'], c['vt_x'], v, len(c['drms']), ', '.join(c['drms'][:4]),
                ' ...' if len(c['drms']) > 4 else ''))
    if pcindex:
        # screen for other (not always-loaded) PC base DRMs that hold a DLC script id with another size: a DLC copy
        # loses whenever such a DRM is loaded first (player / weapon objects, units of the base game)
        idx = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'idx_pc.json')))
        pcs = collections.defaultdict(lambda: collections.defaultdict(list))
        for rec in idx:
            for s in rec[5] or []:
                if s[0] == 8: pcs[s[1]][s[2]].append((os.path.basename(rec[0]), rec[1]))
        dl = collections.defaultdict(lambda: collections.defaultdict(list))
        for pk, tree, rel, S, X, P in files:
            for q in S:
                if q[0] == 8 and q[2] and q[1] not in res: dl[q[1]][len(q[2])].append(rel)
        print('\n== DLC script ids (not resident) that PC base-game DRMs hold with another size')
        n = 0
        for sid in sorted(dl):
            if sid not in pcs: continue
            other = {sz: v for sz, v in dl[sid].items() if sz not in pcs[sid]}
            if not other: st['pc index: same size'] += 1; continue
            n += 1; st['pc index: OTHER SIZE'] += 1
            print('script %6d: DLC sizes %s; PC sizes %s (%d records, e.g. %s)' % (
                sid, {sz: len(v) for sz, v in dl[sid].items()}, sorted(pcs[sid]), sum(len(v) for v in pcs[sid].values()),
                ', '.join('%s#%d' % r for v in list(pcs[sid].values())[:1] for r in v[:3])))
        print('%d ids' % n)
    if unpaired:
        print('\n== DRMs without Xbox pairing (%d): %s' % (len(unpaired), ', '.join(unpaired[:20]) + (' ...' if len(unpaired) > 20 else '')))
    print('\nsummary: %s' % dict(st))
    if jout:
        J = dict(resident=argv[0], trees=trees, summary=dict(st), unpaired=unpaired,
                 dropped={str(k): dict(res_lay=v['res_lay'], relocs=dict(v['relocs']), mism=v['mism'], drms=v['drms'],
                                       groups=[dict(x=g['x'], c=g['c'], diff=g['diff'], drms=g['drms']) for g in v['groups'].values()])
                          for k, v in dropped.items()},
                 derived=[dict(anc=g['anc'], xid=g['xid'], where=g['where'], x=g['x'], p=g['p'],
                               cls={str(s): dict(level=c['level'], vt_pc=c['vt_pc'], vt_x=c['vt_x'], size=c['size'],
                                                 verdicts=['%s/%s x%d' % (a, b, n) for (a, b), n in c['verdicts'].items()],
                                                 drms=c['drms']) for s, c in g['cls'].items()})
                          for g in derived.values()])
        json.dump(J, open(jout, 'w'), indent=1, default=list)
        print('json: %s' % jout)


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
