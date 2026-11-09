"""The DLC 2 words that the installed tree and pipeline_check_0813 converted differently (read-only; 2026-11-09,
Befund-0813-Rueckschritt-0911.md): judge them against base-game Xbox / PC pairs, and gate a tree.

  L   dlc_yggdrasil_end Level (section 0) +0x148 / +0x168 / +0x178 / +0x188 (float z ~10645 of vec4 records): the base
      twin l7_yggdrasil_end is s32 at these offsets (other value) -> s32 (typed_family_fix leveltwin since 2026-11-09)
  W1  unit DTP 21218 (dlc_yggdrasil_end) +0x14f04 = root +0xa4 block +0x94: the base units disagree (l7_yggdrasil_end
      raw, l7_yggdrasil_hall02 s32); the end unit's own twin l7_yggdrasil_end has the SAME Xbox word -> its PC word
      (typed_family_fix introtyped root_twin_words since 2026-11-09)
  W2  DTP 24411 (dlc2_uo_goo_drips) +0x464 = TRANS @0x430 +0x34 (flags byte; engine 0x4d4a00 reads the BYTE +0x34):
      the word at TRANS +0x34 of every base uber object (Xbox layers vs PC bigfile) -> one order
  W3  DTP 24420 (dlc2_uo_goo_drips_spawned) +0x6c: no structural base rule found here (DTP 24420 is not an object DTP;
      the base uber object DTPs are all 0 at +0x6c); tools/dtp_audit.py FP rule (>= 20 unanimous base samples) says raw
      (17l class a, merged in 17m) - the step for those keys (fpkeys) is not built (owner decision), so W3 only WARNs

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/endlevel_word_judge.py judge INSTALLED_MODS_DIR TREE_MODS_DIR
        base evidence + installed / tree verdict per word; exit 1 when a word has no base rule
  ../bin/pyt -t 1800 tools/endlevel_word_judge.py check TREE_MODS_DIR [--report R.json]
        gate: exit 1 when L / W1 / W2 differ from the wanted word in the tree (W3 is reported as WARN)
"""
import sys, os, struct, collections, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault('TRUDLC_PACK_FIRST', 'pack11')
import drm_reloc as R, drm_write as DW
import typed_family_fix as T

UBER_MAGIC = 0x8080b00b
LEVEL_WORDS = (0x148, 0x168, 0x178, 0x188)


def sec_by_id(path, sid):
    D = DW.read(open(path, 'rb').read(), 'le')
    for s in D.sections:
        if s.id == sid: return s
    return None


def level_of(path, e='le'):
    return DW.read(open(path, 'rb').read(), e).sections[0]


def xbox_drm(rel):
    from convert_dlc import raw_dlc
    return DW.read(raw_dlc(rel)[0], 'be')


def xbox_sec(rel, sid):
    for s in xbox_drm(rel).sections:
        if s.id == sid: return s
    return None


def uber_trans(data, reloc, e):
    """offsets of the TRANS records (0x38 B) of an object DTP with an uber block at +0xc8, or []"""
    E = '<' if e == 'le' else '>'
    ptr = dict(R.parse(reloc, e).internal)
    u32 = lambda o: struct.unpack_from(E + 'I', data, o)[0] if 0 <= o <= len(data) - 4 else None
    U = ptr.get(0xc8)
    if U is None or u32(U + 4) != UBER_MAGIC: return []
    nd = u32(U + 8); D0 = ptr.get(U + 0xc)
    if D0 is None or not nd or nd > 64: return []
    stride = None
    for s in [0x60] + list(range(0x40, 0x100, 4)):
        if all(ptr.get(D0 + s * m + 8) is not None for m in range(nd)): stride = s; break
    if stride is None: stride, nd = 0x60, 1
    out = []
    for m in range(nd):
        D = D0 + stride * m
        n_tr = u32(D + 0xc); Tr = ptr.get(D + 0x10)
        if Tr is not None and n_tr and n_tr < 500:
            out += [Tr + 0x38 * k for k in range(n_tr) if Tr + 0x38 * k + 0x38 <= len(data)]
    return out


def base_uber_objects():
    """[(name, Xbox section, PC section)] of the base uber object DTPs (objectlist ids < 850 with 'uo_'); the Xbox DTP is
    paired by id, else by its unique size (the ids differ between the builds, as 17h-C uber_anim_scan)"""
    import dtp_word_classes as C
    # object list: the merged PC list of the workspace (= the installed mods\tr8\pc-w\objectlist.txt); TRU_GAME_MODS
    # may point at a game's mods folder instead
    G = os.environ.get('TRU_GAME_MODS', os.path.join(HERE, '..', 'work', 'generic', 'merged'))
    ol = open(os.path.join(G, 'tr8', 'pc-w', 'objectlist.txt'), 'rb').read().decode('latin-1').splitlines()
    out = []
    for l in ol:
        if ',' not in l: continue
        n, nm = l.split(',', 1)
        if not (n.strip().isdigit() and int(n) < 850 and 'uo_' in nm): continue
        nm = nm.strip()
        X = C.find(C.BASE, 'be', 'xenon-w' + chr(92) + nm + '.drm')
        P = C.find(C.PC, 'le', 'pc-w' + chr(92) + nm + '.drm')
        if not X or not P: continue
        xs = {(s['type'], s['id']): s for s in X}
        by_size = collections.defaultdict(list)
        for s in X:
            if s['type'] == 7: by_size[len(s['data'])].append(s)
        for s in P:
            if s['type'] != 7 or not uber_trans(bytes(s['data']), bytes(s['reloc']), 'le'): continue
            x = xs.get((7, s['id']))
            if x is None or len(x['data']) != len(s['data']):
                c = by_size[len(s['data'])]
                x = c[0] if len(c) == 1 else None
            if x is not None: out.append((nm, x, s))
    return out


def evidence():
    """-> dict with the base evidence per word: L class, W1 twin pair + all units, W2 TRANS +0x34 classes"""
    ev = {}
    # L: the twin's class at the four offsets
    _, P = T.base_unit('l7_yggdrasil_end'); X, _ = T.base_unit('l7_yggdrasil_end')
    bx, bp = bytes(X.sections[0].data), bytes(P.sections[0].data)
    ev['L'] = {o: (bx[o:o + 4].hex(), bp[o:o + 4].hex(), T.cls(bx[o:o + 4], bp[o:o + 4])) for o in LEVEL_WORDS}
    # W1
    units = {}
    for name in T.BASE_UNITS:
        X, P = T.base_unit(name)
        kx, kp = T.unit_dtp(X, 'be'), T.unit_dtp(P, 'le')
        ux, up = X.sections[kx], P.sections[kp]
        rbx = dict(R.parse(bytes(ux.reloc), 'be').internal).get(0xa4)
        rb = dict(R.parse(bytes(up.reloc), 'le').internal).get(0xa4)
        if rbx is None or rb is None: continue
        xw, pw = bytes(ux.data)[rbx + 0x94:rbx + 0x98], bytes(up.data)[rb + 0x94:rb + 0x98]
        units[name] = (up.id, xw.hex(), pw.hex(), T.cls(xw, pw))
    ev['W1'] = units
    # W2
    c2, n_tr, objs = collections.Counter(), 0, base_uber_objects()
    for nm, x, p in objs:
        xd, pd = bytes(x['data']), bytes(p['data'])
        for tb in uber_trans(pd, bytes(p['reloc']), 'le'):
            n_tr += 1; c2[T.cls(xd[tb + 0x34:tb + 0x38], pd[tb + 0x34:tb + 0x38])] += 1
    ev['W2'] = {'objects': len(objs), 'trans': n_tr, 'classes': dict(c2)}
    return ev


def wanted(ev):
    """-> {(rel, sid or 'L', offset): (wanted bytes, gate 'FAIL' or 'WARN', why)} from the Xbox DLC words + evidence"""
    out = {}
    lx = bytes(xbox_drm('dlc_yggdrasil_end.drm').sections[0].data)
    for o in LEVEL_WORDS:
        c = ev['L'][o][2]
        if c == 's32': out[('dlc_yggdrasil_end.drm', 'L', o)] = (T.perm(lx[o:o + 4], 's32'), 'FAIL', 'Level twin pair s32')
    tw = ev['W1'].get('l7_yggdrasil_end')
    x1 = bytes(xbox_sec('dlc_yggdrasil_end.drm', 21218).data)[0x14f04:0x14f08]
    if tw and x1.hex() == tw[1]:
        out[('dlc_yggdrasil_end.drm', 21218, 0x14f04)] = (bytes.fromhex(tw[2]), 'FAIL', 'unit twin l7_yggdrasil_end, same Xbox word')
    one = [k for k in ev['W2']['classes'] if k != 'amb']
    if len(one) == 1:
        x2 = bytes(xbox_sec('dlc2_uo_goo_drips.drm', 24411).data)[0x464:0x468]
        out[('dlc2_uo_goo_drips.drm', 24411, 0x464)] = (T.perm(x2, one[0]), 'FAIL', 'base TRANS +0x34 %s' % one[0])
    x3 = bytes(xbox_sec('dlc2_uo_goo_drips_spawned.drm', 24420).data)[0x6c:0x70]
    out[('dlc2_uo_goo_drips_spawned.drm', 24420, 0x6c)] = (T.perm(x3, 'raw'), 'WARN', 'dtp_audit FP raw (fpkeys not built)')
    return out


def word_in(tree, rel, sid, o):
    p = os.path.join(tree, rel)
    s = level_of(p) if sid == 'L' else sec_by_id(p, sid)
    return bytes(s.data)[o:o + 4]


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ('judge', 'check'): print(__doc__); return 2
    ev = evidence()
    print('L  twin l7_yggdrasil_end Level: %s' % ', '.join('+%#x %s/%s %s' % (o, *v) for o, v in ev['L'].items()))
    print('W1 root +0xa4 block +0x94 of the base units: %s' % ', '.join('%s DTP %d %s->%s %s' % (n, *v) for n, v in ev['W1'].items()))
    print('W2 base uber object DTPs %(objects)d, TRANS %(trans)d, TRANS +0x34 classes %(classes)s' % ev['W2'])
    W = wanted(ev)
    if a[0] == 'judge':
        if len(a) != 3: print(__doc__); return 2
        for (rel, sid, o), (want, gate, why) in sorted(W.items(), key=str):
            wi, wt = word_in(a[1], rel, sid, o), word_in(a[2], rel, sid, o)
            print('%s %s +%#x: wanted %s (%s) - installed %s %s, tree %s %s' % (
                rel, 'Level' if sid == 'L' else 'DTP %d' % sid, o, want.hex(), why, wi.hex(), 'OK' if wi == want else 'WRONG',
                wt.hex(), 'OK' if wt == want else 'WRONG'))
        return 0 if len(W) == 7 else 1
    if len(a) < 2: print(__doc__); return 2
    tree = a[1]; rep = a[a.index('--report') + 1] if '--report' in a else None
    rows, fail = [], 0
    for (rel, sid, o), (want, gate, why) in sorted(W.items(), key=str):
        if not os.path.exists(os.path.join(tree, rel)): continue
        wt = word_in(tree, rel, sid, o)
        st = 'ok' if wt == want else gate
        fail += st == 'FAIL'
        rows.append(dict(file=rel, section='Level' if sid == 'L' else sid, offset=hex(o), tree=wt.hex(), wanted=want.hex(),
                         rule=why, state=st))
        print('%-5s %s %s +%#x tree %s wanted %s (%s)' % (st, rel, 'Level' if sid == 'L' else 'DTP %d' % sid, o, wt.hex(), want.hex(), why))
    if len(W) != 7: print('FAIL  evidence incomplete: %d of 7 words have a rule' % len(W)); fail += 1
    if rep:
        os.makedirs(os.path.dirname(os.path.abspath(rep)), exist_ok=True)
        json.dump(dict(tree=tree, rows=rows, fail=fail), open(rep, 'w'), indent=1)
    print('endlevel words: %d checked, %d FAIL' % (len(rows), fail))
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
