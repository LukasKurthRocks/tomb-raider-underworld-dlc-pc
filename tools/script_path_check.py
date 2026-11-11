"""Pipeline check "Symbol paths" (Q58, 2026-11-11): do the Symbol path words in the init data of the converted DLC
scripts resolve on PC to the member / function the Xbox path names? Read-only (nothing written but the report).

Why: tru.exe resolves Symbol paths BY NAME at run time (0x4d08e0, ENGINE.md Q55 row): per path element 0x4c8420 scans
the DataMembers of the CURRENT type only ([[obj+8]+0x2c], 20-byte entries, name u16 at +0xe; a member of base type
0xa / 0xb hands its referenced ScriptType on to the next element: the DataType union +8, through the Compound when
tag bit 7 is set), else 0x4d0850 scans the functions ([type+0x38], 28-byte entries, Prototype* -> name u16 at +0xa)
up the class chain (0x5749c0: [[type+8]+0x18] = the super id of the stream data) and a function returning base type
0xa / 0xb hands its type on. Member names and path words are Symbols the converter maps through dlc_generic.DlcIds.sym,
which GUESSES where its base map has no entry (Q55: 1 492 of 2 946 aligned PC member names = the guess) - a path into a
PC base class (a native property, an inherited function) can then name nothing or another member.

Path word (the form Q55 found in UI timeline descriptors): an init leaf word {u16 a, u16 b} (members, arguments and
locals of a script, script_init_from_pc.leaves) whose Xbox high half a names a member or function of the owning Xbox
class (the root the descriptors resolve against, Q55) that hands a type on (base type 0xa / 0xb - only then does the
engine walk on to b) and whose low half b is neither 0 nor 0xffff. The Xbox side is resolved
with the Xbox scripts (same DRM first, then every DRM of the pack, then the Xbox base with the title update), the PC
side with the converted tree (same DRM first, then the tree, then --extra trees such as generalbank_pc, then the PC
base). The PC target is RIGHT when it is the twin of the Xbox target: the same entry offset where the PC class keeps
the Xbox layout (converter routes convert / template), else the declaration-order twin (script_member_pairs.align for
members, script_conv.offset_map for functions). Words whose low half resolves on neither side (a native property
outside the script types) are compared as Symbols: PC = the learned base map of the Xbox Symbol = 'native, base map',
else 'native, not provable'.

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/script_path_check.py scan TREE [--pack pack11] [--extra DIR ...] [--report R.json] [--list N]
        exit 1 when any path element resolves to another member or to nothing on PC while it resolves on the Xbox
TREE: a mods folder of converted PC DRMs; --pack pack11 for DLC 2 (as ui_init_fix / dlc_fixes_build --pack).
"""
import sys, os, struct, collections, json, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_write as DW, drm_reloc as R, script_conv as SC
import script_init_from_pc as SIP
import script_member_pairs as MP

OBJ_BT = (0xa, 0xb)         # base types whose DataType hands a ScriptType on (0x4c8420 / 0x4d0850)
_IDS = None


def ids():
    global _IDS
    if _IDS is None:
        import dlc_generic as DG
        _IDS = DG.DlcIds()
    return _IDS


def sym_route(I, xs):
    """the DlcIds.sym route of Xbox Symbol xs (same order as DlcIds.sym)"""
    import bisect
    from dlc_generic import SYM
    m = I.base[SYM]
    if xs in m: return 'mapped'
    if xs in getattr(I, 'sym_twins', {}): return 'twin'
    if xs in I.sym_extra: return 'extra'
    if xs in (0, 0xffff): return 'null'
    if xs > I.xs_max: return 'dlc_new_shift'
    k = bisect.bisect_left(I.sks, xs)
    if 0 < k < len(I.sks):
        a, b = I.sks[k - 1], I.sks[k]
        if m[b] - m[a] == b - a: return 'interpolated'
        return 'guess_lower' if m[a] + xs - a not in I.sused else 'guess_collision_new'
    return 'identity_below_min'


class Cls:
    """one script section: own members by name, functions by name, super id, the type each hands on"""
    def __init__(self, sid, d, rl, e):
        self.sid, self.d, self.rl, self.e = sid, d, rl, e
        E = '>' if e == 'be' else '<'
        self.rel = R.parse(rl, e)
        self.W, ent = MP.entries(d, rl, e)
        it = self.W.it
        idoff = self.rel.id_offsets()

        def idat(o):
            return struct.unpack_from(E + 'I', d, o)[0] if o in idoff and o + 4 <= len(d) else None

        def handed(a):          # DataType at a: the script id it hands on (0x4c8420 / 0x4d08b0), None when none
            tag = struct.unpack_from(E + 'I', d, a)[0]
            if tag & 0xf not in OBJ_BT: return None
            if tag & 0x80:
                c = it.get(a + 8)
                return idat(c) if c is not None else None
            return idat(a + 8)
        self.members = {}
        self.mem = ent['members']
        for q in ent['members']:
            self.members.setdefault(q['name'], (q['a'], handed(q['a'])))
        self.funcs = {}
        for nm, t, n, sz in self.W.arrays:
            if nm != 'funcs': continue
            for k in range(n):
                a = t + 28 * k
                p = it.get(a)
                if p is None or p + 0x14 > len(d): continue
                self.funcs.setdefault(struct.unpack_from(E + 'H', d, p + 0xa)[0], (a, handed(p + 0x10)))
        self.super = idat(0x18)


class Side:
    """script classes of one platform by id: per-DRM first, then the pool, then the fallback store"""
    def __init__(self, e, fallback):
        self.e, self.pool, self.fallback, self.cache = e, {}, fallback, {}

    def add(self, sid, d, rl, origin):
        self.pool.setdefault(sid, (d, rl, origin))

    def get(self, sid, local=None):
        if sid is None: return None
        src = None
        if local is not None and sid in local: src = local[sid] + ('drm',)
        elif sid in self.pool: src = self.pool[sid]
        else:
            f = self.fallback.get((8, sid))
            if f is not None and f.get('data'): src = (f['data'], f['reloc'], 'store')
        if src is None: return None
        key = (sid, hashlib.md5(src[0]).digest())
        c = self.cache.get(key)
        if c is None:
            try: c = Cls(sid, src[0], src[1], self.e)
            except Exception: c = False
            self.cache[key] = c
        if c is not False: c.origin = src[2]
        return c or None


def resolve(side, cls, sym, local):
    """one path element in class cls: ('m', class, entry offset, handed id) | ('f', owner class, func offset, handed id)"""
    if cls is None: return None
    if sym in cls.members:
        a, h = cls.members[sym]; return ('m', cls, a, h)
    c, depth = cls, 0
    while c is not None and depth < 32:
        if sym in c.funcs:
            a, h = c.funcs[sym]; return ('f', c, a, h)
        c = side.get(c.super, local); depth += 1
    return None


class Twins:
    """Xbox class + entry -> PC entry offset (identity for Xbox-layout PC sections, else declaration-order twins)"""
    def __init__(self):
        self.cache = {}

    def map(self, xc, pc, xlayout):
        key = (id(xc), id(pc), xlayout)
        m = self.cache.get(key)
        if m is None:
            if xlayout: m = None
            else:
                I = ids()
                from dlc_generic import SYM
                try:
                    m, _ = MP.align(xc.d, xc.rl, pc.d, pc.rl, I)
                    m = dict(m)
                    m.update(SC.offset_map(xc.d, xc.rel, pc.d, pc.rel, I.base.get(SYM, {})))
                except Exception:
                    m = {}
            self.cache[key] = m
        return m

    def twin(self, xc, pc, xa, xlayout):
        if xlayout: return xa
        return self.map(xc, pc, xlayout).get(xa)


def pc_id_of(I, xid, clash, local):
    nid = I(8, xid)
    if local is not None and nid not in local and clash.get(nid) in local: return clash[nid]
    return nid


def drms(tree):
    for r, _, fs in os.walk(tree):
        for f in sorted(fs):
            if f.lower().endswith('.drm'): yield os.path.join(r, f)


def scan(tree, extras, report, nlist):
    import dlc_script_pairs as SP
    import ui_init_fix as UF
    from dlc_generic import SYM
    I = ids()
    store = SP.store()
    clash = SP.clash_ids()
    X = Side('be', store['xb_store']); P = Side('le', store['pc_store'])
    P0 = Side('le', store['pc_store'])          # the PC base alone: reference for the PC-byte scripts (route pc_copy)
    files = []
    xcache = {}
    st = collections.Counter()
    # pass 1: every PC DRM of the tree, its Xbox source, the script pairs (with the converter's route)
    for p in drms(tree):
        try:
            D = DW.read(open(p, 'rb').read(), 'le')
        except Exception as ex:
            st['DRMs not read'] += 1; print('%s: not read (%s)' % (p, ex)); continue
        xs = UF.xbox_sections(os.path.basename(p), xcache)
        xcache.pop(os.path.basename(p), None)
        xl = {x['id']: (x['data'], x['reloc']) for x in xs if x['type'] == 8 and x['data']}
        pl = {s.id: (s.data, s.reloc) for s in D.sections if s.type == 8 and s.data}
        for k, v in xl.items(): X.add(k, v[0], v[1], 'pack')
        for k, v in pl.items(): P.add(k, v[0], v[1], 'tree')
        if not pl: continue
        pm, pst = SP.pairs(xs, D, I, store)
        for k, v in pst.items(): st['pairing: ' + k] += v
        files.append((p, D, xl, pl, pm))
        st['DRMs with scripts'] += 1
    for ex in extras:
        for p in drms(ex):
            D = DW.read(open(p, 'rb').read(), 'le')
            for s in D.sections:
                if s.type == 8 and s.data: P.add(s.id, s.data, s.reloc, 'extra')
    # which PC ids keep the Xbox layout (converter routes convert / template in this tree)
    xlay = {}
    for p, D, xl, pl, pm in files:
        for k, (x, route) in pm.items():
            xlay[(p, D.sections[k].id)] = route in ('convert', 'template')
    T = Twins()
    rows = []
    per_script = collections.defaultdict(collections.Counter)
    seen_content = set()

    def is_xlayout(p, pid, pc):
        if pc is None: return False
        if pc.origin == 'drm': return xlay.get((p, pid), False)
        # a pool / extra / store section: Xbox layout only if it came from the tree with route convert / template
        return any(v for (pp, i), v in xlay.items() if i == pid and pp != p) if pc.origin == 'tree' else False

    def target_ok(p, xr, pr, local_p, kind):
        """'right' / 'wrong' / 'unresolved' / 'xbox-unresolved' for one element"""
        if xr is None: return 'xbox-unresolved'
        if pr is None: return 'unresolved'
        if xr[0] != pr[0]: return 'wrong'
        xc, pc = xr[1], pr[1]
        want_pid = pc_id_of(I, xc.sid, clash, local_p)
        if pc.sid != want_pid and not (xc.sid == cur_x[0] and pc.sid == cur_p[0]): return 'wrong'
        tw = T.twin(xc, pc, xr[2], is_xlayout(p, pc.sid, pc))
        if tw is None: return 'no-twin'
        return 'right' if tw == pr[2] else 'wrong'

    cur_x, cur_p = [None], [None]
    for p, D, xl, pl, pm in files:
        drm = os.path.basename(p)
        for k, (x, route) in sorted(pm.items()):
            s = D.sections[k]
            if route == 'pc_copy':
                pc_copy_paths(p, s, pl, P, P0, st, rows, seen_content)
                continue
            if len(x['data']) != len(s.data): st['scripts with another size than the Xbox (skipped)'] += 1; continue
            hk = (s.id, hashlib.md5(s.data).digest(), hashlib.md5(x['data']).digest())
            dup = hk in seen_content
            seen_content.add(hk)
            st['script sections checked'] += 1
            if not dup: st['unique script contents checked'] += 1
            xc = X.get(x['id'], xl); pc = P.get(s.id, pl)
            if xc is None or pc is None: st['scripts not parsed'] += 1; continue
            cur_x[0], cur_p[0] = x['id'], s.id
            done = set()
            for kind in MP.KINDS:
                for q in MP.entries(x['data'], x['reloc'], 'be', xc.W)[1][kind]:
                    if q['init'] is None: continue
                    for path, o in SIP.leaves(xc.W, xc.W.it, q['init']):
                        if o in done or o + 4 > len(x['data']): continue
                        done.add(o)
                        xa, xb = struct.unpack_from('>HH', x['data'], o)
                        if xa in (0, 0xffff) or xb in (0, 0xffff): continue
                        r1x = resolve(X, xc, xa, xl)
                        # a two-element path goes on only from an element that hands a type (0x4d0981: ebx = 0 ends
                        # the walk); without that a float such as 0.02 = 3ca3 d70a matches a member name by chance
                        if r1x is None or r1x[3] is None: continue
                        pa, pb = struct.unpack_from('<HH', s.data, o)
                        r1p = resolve(P, pc, pa, pl)
                        e1 = target_ok(p, r1x, r1p, pl, kind)
                        r2x = resolve(X, X.get(r1x[3], xl), xb, xl) if r1x[3] is not None else None
                        r2p = resolve(P, P.get(r1p[3], pl), pb, pl) if (r1p is not None and r1p[3] is not None) else None
                        if r2x is not None: e2 = target_ok(p, r2x, r2p, pl, kind)
                        elif r2p is not None: e2 = 'pc-only'
                        else:
                            e2 = 'native, base map' if I.base[SYM].get(xb) == pb else (
                                'native, not provable' if xb not in I.base[SYM] else 'native, base map differs')
                        cat = ('elem1 ' + e1, 'elem2 ' + e2)
                        form = word_form(x['data'][o:o + 4], s.data[o:o + 4], I)
                        if not dup:
                            for c in cat: st['path words: ' + c] += 1
                            st['path words'] += 1
                            st['path words: PC word form ' + form] += 1
                            per_script[s.id]['words'] += 1
                            bad = e1 in ('wrong', 'unresolved', 'no-twin') or e2 in ('wrong', 'unresolved', 'no-twin', 'native, base map differs')
                            if bad:
                                st['path words bad'] += 1
                                per_script[s.id]['bad'] += 1
                                st['bad path words: PC word form ' + form] += 1
                            rows.append(dict(drm=drm, script=s.id, xbox_script=x['id'], route=route, off=o, kind=kind,
                                             xbox='%04x %04x' % (xa, xb), pc='%04x %04x' % (pa, pb), form=form,
                                             elem1=e1, elem2=e2, bad=bad,
                                             a_route=sym_route(I, xa), b_route=sym_route(I, xb),
                                             a_target=_desc(r1x), a_pc=_desc(r1p), b_target=_desc(r2x), b_pc=_desc(r2p)))
    for k in sorted(st): print('  %-72s %d' % (k, st[k]))
    worst = sorted(per_script.items(), key=lambda kv: (-kv[1]['bad'], -kv[1]['words'], kv[0]))
    drms_of = collections.defaultdict(set)
    for r in rows: drms_of[r['script']].add(r['drm'])
    print('scripts with path words: %d, with a bad word: %d' % (len(per_script), sum(1 for _, c in worst if c['bad'])))
    for sid, c in worst[:nlist]:
        if c['bad']: print('  script %6d: %d bad of %d path words (%d DRMs, e.g. %s)' % (
            sid, c['bad'], c['words'], len(drms_of[sid]), sorted(drms_of[sid])[0]))
    if report:
        json.dump(dict(tree=os.path.relpath(tree), stats=dict(st),
                       scripts=[dict(script=k, drms=sorted(drms_of[k]), bad=v['bad'], words=v['words']) for k, v in worst],
                       rows=rows), open(report, 'w'), indent=1)
    return st


def pc_copy_paths(p, s, pl, P, P0, st, rows, seen):
    """a script the converter took as PC bytes (route pc_copy): its path words are PC words; mixed origin breaks them
    when a class they reach is a CONVERTED one in the tree (Xbox layout, converter names). Bad = resolves on the PC
    base alone but resolves to nothing / another (class, entry) with the tree's classes."""
    hk = ('pc', s.id, hashlib.md5(s.data).digest())
    st['scripts route pc_copy checked'] += 1
    if hk in seen: return
    seen.add(hk)
    pc = P.get(s.id, pl); pb = P0.get(s.id)
    if pc is None: return
    done = set()
    for kind in MP.KINDS:
        for q in MP.entries(s.data, s.reloc, 'le', pc.W)[1][kind]:
            if q['init'] is None: continue
            for path, o in SIP.leaves(pc.W, pc.W.it, q['init']):
                if o in done or o + 4 > len(s.data): continue
                done.add(o)
                a, b = struct.unpack_from('<HH', s.data, o)
                if a in (0, 0xffff) or b in (0, 0xffff): continue
                r1 = resolve(P, pc, a, pl)
                if r1 is None or r1[3] is None: continue
                r10 = resolve(P0, pb, a, None) if pb is not None else None
                r2 = resolve(P, P.get(r1[3], pl), b, pl) if r1[3] is not None else None
                r20 = resolve(P0, P0.get(r10[3]), b, None) if (r10 is not None and r10[3] is not None) else None
                key = lambda r: None if r is None else (r[0], r[1].sid, r[2])
                st['pc_copy path words'] += 1
                bad = (r10 is not None and key(r1) != key(r10)) or (r20 is not None and key(r2) != key(r20))
                if r20 is None and r2 is None: st['pc_copy path words: element 2 resolves on neither (native)'] += 1
                if bad:
                    st['pc_copy path words bad (tree classes differ from the PC base)'] += 1
                    st['path words bad'] += 1
                rows.append(dict(drm=os.path.basename(p), script=s.id, xbox_script=None, route='pc_copy', off=o, kind=kind,
                                 xbox=None, pc='%04x %04x' % (a, b), form='pc', elem1='pc_copy', elem2='pc_copy', bad=bad,
                                 a_route=None, b_route=None, a_target=_desc(r10), a_pc=_desc(r1), b_target=_desc(r20),
                                 b_pc=_desc(r2)))


FORMS = ('id16ab:100', 'id16a:100', 'id16b:100', 's32', 'raw', 's16')


def word_form(xw, pw, I):
    """which converter word class turns the Xbox word into the PC word (script_learn classes), 'other' when none"""
    import script_learn as L
    for c in FORMS:
        if L.apply_word(bytes(xw), c, I) == bytes(pw): return c
    return 'other'


def _desc(r):
    if r is None: return None
    return '%s %d +0x%x%s' % (r[0], r[1].sid, r[2], '' if r[3] is None else ' -> %d' % r[3])


def main(argv):
    if not argv or argv[0] != 'scan':
        print(__doc__); return 2
    argv = argv[1:]
    rep = None; nlist = 30; extras = []
    if '--report' in argv: k = argv.index('--report'); rep = argv[k + 1]; del argv[k:k + 2]
    if '--list' in argv: k = argv.index('--list'); nlist = int(argv[k + 1]); del argv[k:k + 2]
    while '--extra' in argv: k = argv.index('--extra'); extras.append(argv[k + 1]); del argv[k:k + 2]
    if '--pack' in argv:
        k = argv.index('--pack'); os.environ['TRUDLC_PACK_FIRST'] = argv[k + 1]; del argv[k:k + 2]
    st = scan(argv[0], extras, rep, nlist)
    bad = st.get('path words bad', 0)
    print('%s Symbol paths: %d path words, %d bad' % ('ok  ' if not bad else 'FAIL', st.get('path words', 0), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
