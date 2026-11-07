"""Sound groups of TR Underworld PC (read-only): the group table in globalsoundinfo.drm and which sounds use each group.

Engine facts (tru.exe PC, Steam exe; tools/pe_dis.py, docs Befund-Ton-Gruppen-0611.md):
  globalSoundInfo = [0xccdea0] (set at 0x5df0c9 from the object "globalsoundinfo", 0x8553bc) = DTP 792 + 0xe0:
    +0x04 u32 group count, +0x08 ptr group entries (0x84 bytes each)  -> CreateGroups 0x593530 -> 0x591ef0(entries,
          count) on the collection 0x8a80d8 (entries [0x8a80d8], count [0x8a80dc])
    +0x0c u32 n / +0x10 ptr  group list switched by 0x5872c0 ("Player fall sound %s")
    +0x14 u32 n / +0x18 ptr  group list switched by 0x5871e0 ("Player death sound %s")
    +0x1c u32 n / +0x20 ptr  group list paused by the pause menu (0x5873a0, bit 0 of entry +0x10)
    +0x24 ptr category slots (s32): [0] music slider 0x589520, [1] effects slider 0x589590, [2] speech slider
          0x587140, [3] music players / MUSBANK link 0 (0x591c6d, 0x593210), [4] default group of a wave / stream
          whose params group is 0 or -1 (0x59127b, 0x5910d6) and MUSBANK link 1 (0x59320b), [5] 0x4a0f33 / 0x5b24fa,
          [6] .., [7] 0x58dd8e (-1 = none)
    +0x28 ptr floats (listener / 3D settings, CreateGroups 0x59355b ..)
  group entry (0x84): +0x00 f32 volume, +0x10 flags (bit 0 paused, bit 1 muted by the death / fall lists, bit 7),
    +0x68 s32 parent group index (-1 = root), +0x80 ptr (runtime area in the DTP)
  SoundPlex Assign node (type 4, 0x590970) record +0x40 s32 group (0 / -1 = inherit); a Wave (type 2, 0x591220) or
  Stream (type 3, 0x591080) leaf plays in the inherited group or, without one, in category slot [4].

Usage (from the repository root):
  ../bin/pyt -t 120 tools/sound_groups.py table GSI      GSI = a globalsoundinfo.drm path or SRC:NAME (tools/locals.SRC,
                                                          e.g. pcbig:globalsoundinfo.drm, tu:globalsoundinfo.drm)
  ../bin/pyt -t 3600 tools/sound_groups.py scan OUT_DIR [--mods DIR] [--manifest KIT_MANIFEST.json] [--only REGEX]
        every DRM of pcbig <- pcpatch <- DIR (the installed mods folder, later wins): SoundPlex trees of all DTP
        sections, wave names from the FSB4 headers, per group: Assign records, sound DTPs, waves, streams, type-1
        references (emitters / anim events / object data), split by DRM kind (generalbank / unit / object / global)
        and origin (base / dlc1 / dlc2 / shared). Writes OUT_DIR/groups_scan.json + groups_waves.tsv
  ../bin/pyt -t 300 tools/sound_groups.py report OUT_DIR GSI [--examples N]   markdown tables from the scan
"""
import sys, os, re, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
from drm import cdrm_decode, sections_with_data

GSI_OFF = 0xe0          # globalSoundInfo inside the DTP (the object resolves to DTP 792 + 0xe0; checked below)
ENTRY = 0x84
CAT_NAMES = ['music (slider Musik)', 'SFX (slider Effekte)', 'speech (slider Sprache)', 'music players / MUSBANK 0',
             'default (no group in the plex)', 'slot 5 (0x4a0f33, 0x5b24fa)', 'slot 6', 'slot 7 (0x58dd8e)']


# ------------------------------------------------------------------------------------------------ loading
def load_drm(spec):
    """spec = path or SRC:NAME -> (sections, endian)"""
    if os.path.isfile(spec):
        raw = open(spec, 'rb').read(); e = 'le'
        if raw[:4] in (b'CDRM', b'MRDC'): raw = cdrm_decode(raw, 'le')
        if struct.unpack_from('<i', raw, 0)[0] not in (19, 20, 21, 22): e = 'be'
        return sections_with_data(raw, e)[1], e
    src, name = spec.split(':', 1)
    import locals as LC
    from archive import Archive
    from names import crc
    path, e, pre = LC.SRC[src]
    A = Archive(path, e)
    recs = A.find(crc(pre + '\\' + name))
    if not recs: sys.exit('%s not in %s' % (name, src))
    return sections_with_data(cdrm_decode(A.read(recs[-1]), e), e)[1], e


def gsi_table(spec):
    """-> dict(count, groups[{i, parent, vol, flags, words}], cats, lists) of a globalsoundinfo.drm"""
    secs, e = load_drm(spec)
    E = '>' if e == 'be' else '<'
    obj = [s for s in secs if s['type'] == 11]
    dtp_id = None
    if obj:
        rel = R.parse(obj[0]['reloc'], e)
        for t, o in rel.idref:
            if t == 7: dtp_id = struct.unpack_from(E + 'I', obj[0]['data'], o)[0]
    s = [x for x in secs if x['type'] == 7 and x['id'] == dtp_id][0]
    d = s['data']; it = dict(R.parse(s['reloc'], e).internal)
    u = lambda o: struct.unpack_from(E + 'I', d, o)[0]
    i32 = lambda o: struct.unpack_from(E + 'i', d, o)[0]
    f32 = lambda o: struct.unpack_from(E + 'f', d, o)[0]
    g = GSI_OFF
    n = u(g + 4); ent = it[g + 8]
    cats_p = it[g + 0x24]
    assert ent + n * ENTRY <= len(d), 'entries out of the DTP'
    cats = []
    for k in range(8):
        v = i32(cats_p + 4 * k)
        cats.append(v)
        if v == -1: break
    def lst(nofs, pofs):
        cnt = u(g + nofs); p = it.get(g + pofs)
        return [i32(p + 4 * k) for k in range(cnt)] if p is not None and cnt < 64 else []
    groups = []
    for k in range(n):
        o = ent + k * ENTRY
        groups.append(dict(i=k, parent=i32(o + 0x68), vol=f32(o), flags=u(o + 0x10),
                           words=[d[o + q:o + q + 4].hex() for q in range(0, ENTRY, 4)],
                           floats=[round(f32(o + q), 4) for q in range(0, 0x68, 4)]))
    return dict(dtp=dtp_id, endian=e, count=n, groups=groups, cats=cats,
                fall=lst(0x0c, 0x10), death=lst(0x14, 0x18), pause=lst(0x1c, 0x20))


def tree_info(T):
    kids = collections.defaultdict(list)
    for gr in T['groups']:
        if gr['parent'] >= 0: kids[gr['parent']].append(gr['i'])
    depth = {}
    def dep(i, seen=()):
        if i in depth: return depth[i]
        p = T['groups'][i]['parent']
        depth[i] = 0 if p < 0 or p in seen else dep(p, seen + (i,)) + 1
        return depth[i]
    for gr in T['groups']: dep(gr['i'])
    return kids, depth


def cmd_table(spec):
    T = gsi_table(spec)
    kids, depth = tree_info(T)
    print('%s: DTP %s (%s), %d groups' % (spec, T['dtp'], T['endian'], T['count']))
    print('category slots:', ', '.join('[%d]=%d %s' % (k, v, CAT_NAMES[k] if k < len(CAT_NAMES) else '')
                                       for k, v in enumerate(T['cats'])))
    print('fall list', T['fall'], 'death list', T['death'], 'pause list', T['pause'])
    def show(i):
        gr = T['groups'][i]
        tags = [('cat[%d]' % k) for k, v in enumerate(T['cats']) if v == i]
        if i in T['pause']: tags.append('pause')
        if i in T['death']: tags.append('death')
        if i in T['fall']: tags.append('fall')
        print('%s%2d  parent %3d  vol %.3f  flags %08x  f[1..5] %s  %s' % ('  ' * depth[i], i, gr['parent'], gr['vol'],
              gr['flags'], gr['floats'][1:6], ' '.join(tags)))
        for c in kids.get(i, []): show(c)
    for gr in T['groups']:
        if gr['parent'] < 0: show(gr['i'])
    orphans = [gr['i'] for gr in T['groups'] if gr['parent'] >= T['count']]
    if orphans: print('parent out of range:', orphans)
    return T


# ------------------------------------------------------------------------------------------------ SoundPlex scan
def fsb_name(d):
    f = d[16:]
    if f[:4] != b'FSB4' or len(f) < 0x30 + 32: return None
    return f[0x32:0x32 + 30].split(b'\0')[0].decode('latin-1')


class Sec:
    """one DTP section: nodes {off: (type, data_off)}, internal pointer map"""
    __slots__ = ('d', 'it', 'slots', 'nodes')

    def __init__(self, d, reloc):
        rel = R.parse(reloc, 'le')
        self.d = d; self.it = dict(rel.internal)
        self.slots = set(rel.pointer_offsets()) | set(rel.id_offsets())
        self.nodes = {}
        for o, tg in rel.internal:
            if o < 4 or o % 4 or (o - 4) in self.slots or tg % 4 or tg + 4 > len(d): continue
            t = struct.unpack_from('<I', d, o - 4)[0]
            if t > 13: continue
            self.nodes[o - 4] = (t, tg)

    def u32(self, o):
        return struct.unpack_from('<I', self.d, o)[0] if 0 <= o and o + 4 <= len(self.d) else None

    def i32(self, o):
        return struct.unpack_from('<i', self.d, o)[0] if 0 <= o and o + 4 <= len(self.d) else None

    def assign_group(self, tg, ngroups):
        """group word of a valid Assign (type 4) record, else None"""
        if tg + 0x48 > len(self.d) or tg not in self.slots: return None
        ch = self.it.get(tg)
        if ch is None or ch not in self.nodes: return None
        if any(tg + k in self.slots for k in range(4, 0x48, 4)): return None
        g = self.i32(tg + 0x40)
        return g if -1 <= g < ngroups else None

    def children(self, off):
        """child node offsets of the node at off (pointer slots in its data record, or arrays of node pointers)"""
        t, tg = self.nodes[off]
        out = []
        if t in (1, 2, 3): return out
        for o in range(tg, min(tg + 0x60, len(self.d)), 4):
            p = self.it.get(o)
            if p is None: continue
            if p in self.nodes and p != off:
                out.append(p); continue
            for q in range(p, min(p + 0x100, len(self.d)), 4):
                p2 = self.it.get(q)
                if p2 is None:
                    if q > p + 8 and (self.u32(q) or 0) > 13: break
                    continue
                if p2 in self.nodes and p2 != off: out.append(p2)
            if t == 4: break                                   # Assign: only +0 is a child pointer
        return out


def stream_name(sec, tg):
    m = re.search(rb'[A-Za-z0-9_\\/.]{4,}', sec.d[tg:tg + 0x100])
    return m.group().decode('latin-1') if m else None


def summarise(sec, ngroups):
    """per section: roots (nodes no other node of the section points to) and their leaves with the explicit group
    path: list of (root_off, root type, [(kind, value, group_or_None)], [assign groups]); kind = wave / stream / ext
    (type-1 id). The child heuristic can reach a leaf both through an Assign and around it, so states are
    (node, inherited group) and a leaf that has an explicit group anywhere in the section drops its None entries."""
    child_of = set(); kids = {}
    for off in sec.nodes:
        kids[off] = sec.children(off)
        child_of.update(kids[off])
    res = []
    seen = set()           # (node, group) states shared by all roots of the section: a later (often false) root
    assign_seen = set()    # that only reaches states an earlier root reached adds nothing and is dropped
    explicit = set()
    for root in sorted(sec.nodes):
        if root in child_of: continue
        leaves = []; assigns = []
        stack = [(root, None, 0)]
        while stack:
            off, g, dep = stack.pop()
            if (off, g) in seen or dep > 40: continue
            seen.add((off, g))
            t, tg = sec.nodes[off]
            if t == 4:
                ag = sec.assign_group(tg, ngroups)
                if ag is None: continue                        # not a real Assign record: stop here
                if off not in assign_seen:
                    assign_seen.add(off); assigns.append(ag)
                if ag not in (0, -1): g = ag
            elif t == 2:
                wid = sec.u32(tg)
                if tg in sec.slots or wid is None: continue
                leaves.append(('wave', wid, g)); continue
            elif t == 3:
                leaves.append(('stream', stream_name(sec, tg), g)); continue
            elif t == 1:
                if tg in sec.slots: continue
                leaves.append(('ext', sec.u32(tg), g)); continue
            for c in kids[off]: stack.append((c, g, dep + 1))
        for lk, v, g in leaves:
            if g is not None: explicit.add((lk, v))
        if leaves or assigns: res.append([root, sec.nodes[root][0], leaves, assigns])
    for r in res:
        r[2] = sorted(set(l for l in r[2] if l[2] is not None or (l[0], l[1]) not in explicit), key=str)
    return [tuple(r) for r in res if r[2] or r[3]]


def drm_kind(name, secs):
    n = name.lower()
    if n.startswith('generalbank'): return 'generalbank'
    if n.startswith('global') or n in ('camerashakes.drm',): return 'global'
    if secs and secs[0]['type'] == 0: return 'unit'
    if secs and secs[0]['type'] == 11: return 'object'
    return 'other'


def iter_drms(mods, only):
    """(name, origin_hint, raw_le) of every DRM: pcbig <- pcpatch <- mods (name-wise, later wins)"""
    import locals as LC
    from archive import Archive
    from names import load, L
    names = load(L + 'Tomb Raider Underworld (PC).txt')
    src = {}
    for key in ('pcbig', 'pcpatch'):
        path, e, pre = LC.SRC[key]
        A = Archive(path, e)
        for r in A.idx:
            nm = names.get(r['hash'], '')
            if not nm.lower().endswith('.drm'): continue
            base = nm.split('\\')[-1].lower()
            if only and not re.search(only, base): continue
            if r['spec'] not in (0xffffffff, 0xffffffe1): continue
            src[base] = (key, A, r)
    if mods:
        for root, _, fs in os.walk(mods):
            for f in fs:
                if f.lower().endswith('.drm') and (not only or re.search(only, f.lower())):
                    src[f.lower()] = ('mods', None, os.path.join(root, f))
    for base in sorted(src):
        key, A, r = src[base]
        try:
            raw = open(r, 'rb').read() if key == 'mods' else A.read(r)
            raw = cdrm_decode(raw, 'le')
        except Exception as ex:
            print('skip', base, ex); continue
        yield base, key, raw


def cmd_scan(out_dir, mods, manifest, only, ngroups):
    os.makedirs(out_dir, exist_ok=True)
    dlc_of = {}
    if manifest:
        for f in json.load(open(manifest))['files']:
            if f['rel'].lower().endswith('.drm'): dlc_of[os.path.basename(f['rel']).lower()] = f.get('dlc')
    wave_name = {}; wave_home = collections.defaultdict(set)
    plex = {}            # DTP id -> (drm, kind, origin, [(root, type, leaves, assigns)]) for roots at offset 0
    roots = []           # (drm, kind, origin, sec id, root off, type, leaves, assigns)
    nd = 0
    for base, key, raw in iter_drms(mods, only):
        try:
            secs = sections_with_data(raw, 'le')[1]
        except Exception as ex:
            print('skip', base, ex); continue
        nd += 1
        kind = drm_kind(base, secs)
        origin = 'base' if key != 'mods' else (dlc_of.get(base) or 'mods')
        for s in secs:
            if s['type'] == 6 and s['data']:
                nm = fsb_name(s['data'])
                # DLC waves were first written as silence (tools/wave_convert.py) and keep the FSB name
                # 'silence.wav' after the real audio went in (wave_swap.py): any other name wins
                if nm and (s['id'] not in wave_name or wave_name[s['id']].lower() == 'silence.wav'):
                    wave_name[s['id']] = nm
                wave_home[s['id']].add(base)
        for s in secs:
            if s['type'] != 7 or not s['data'] or not s['reloc']: continue
            try:
                sec = Sec(s['data'], s['reloc'])
                if not sec.nodes: continue
                summ = summarise(sec, ngroups)
            except Exception as ex:
                print('section error', base, s['id'], ex); continue
            for root, t, leaves, assigns in summ:
                roots.append((base, kind, origin, s['id'], root, t, leaves, assigns))
                if root == 0 and s['id'] not in plex: plex[s['id']] = len(roots) - 1
        if nd % 100 == 0: print('...', nd, 'DRMs', len(roots), 'plex roots', len(wave_name), 'wave names', flush=True)
    print('DRMs', nd, 'roots', len(roots), 'DTPs with a plex at +0', len(plex), 'waves named', len(wave_name))
    json.dump(dict(roots=roots, plex=plex, wave_name={str(k): v for k, v in wave_name.items()},
                   wave_home={str(k): sorted(v) for k, v in wave_home.items()}),
              open(os.path.join(out_dir, 'groups_scan.json'), 'w'))
    print('written', os.path.join(out_dir, 'groups_scan.json'))


# ------------------------------------------------------------------------------------------------ report
def resolve(scan, cats_default):
    """-> per group: assigns, roots, waves, streams, refs with the DRM kind / origin; type-1 links followed (the
    referenced plex inherits the group of the referring path)"""
    roots = scan['roots']; plex = {int(k): v for k, v in scan['plex'].items()}
    memo = {}

    def leaves_of(ri, g, depth=0, seen=()):
        """[(kind, value, eff_group, root index)] of root ri with inherited group g"""
        key = (ri, g)
        if key in memo: return memo[key]
        out = []
        base, kind, origin, sid, root, t, leaves, assigns = roots[ri]
        for lk, v, lg in leaves:
            eg = lg if lg is not None else g
            if lk == 'ext':
                pi = plex.get(v)
                if pi is None or pi in seen or depth > 12:
                    out.append(('missing', v, eg, ri)); continue
                out += leaves_of(pi, eg, depth + 1, seen + (ri,))
            else:
                out.append((lk, v, eg, ri))
        memo[key] = out
        return out
    return leaves_of


def cmd_report(out_dir, gsi, nex):
    scan = json.load(open(os.path.join(out_dir, 'groups_scan.json')))
    T = gsi_table(gsi)
    kids, depth = tree_info(T)
    dflt = T['cats'][4]
    roots = scan['roots']; plex = {int(k): v for k, v in scan['plex'].items()}
    wname = scan['wave_name']; whome = scan['wave_home']
    leaves_of = resolve(scan, dflt)
    referenced = set()
    for ri, r in enumerate(roots):
        for lk, v, lg in r[6]:
            if lk == 'ext' and v in plex: referenced.add(plex[v])
    # per group statistics
    G = collections.defaultdict(lambda: dict(assign=collections.Counter(), dtp=set(), waves=collections.Counter(),
                                             wave_ids=set(), streams=collections.Counter(), refs=collections.Counter(),
                                             drms=collections.Counter(), origin=collections.Counter(),
                                             wdrm=collections.Counter(), worigin=collections.Counter()))
    for ri, r in enumerate(roots):
        base, kind, origin, sid, root, t, leaves, assigns = r
        for a in assigns:
            if a not in (0, -1):
                G[a]['assign'][kind] += 1; G[a]['dtp'].add(sid); G[a]['drms'][base] += 1; G[a]['origin'][origin] += 1
    seen_wave = collections.defaultdict(set); seen_stream = collections.defaultdict(set)
    for ri, r in enumerate(roots):
        if ri in referenced: continue                          # counted through the referring plex
        base, kind, origin, sid, root, t, leaves, assigns = r
        reached = set()
        for lk, v, eg, src_ri in leaves_of(ri, None):
            g = eg if eg not in (None, 0, -1) else 'default'
            if lk == 'wave':
                if str(v) not in whome: continue               # no wave section with that id: a false node
                G[g]['wave_ids'].add(v); seen_wave[g].add(v); reached.add(g)
            elif lk == 'stream':
                if not v or not re.match(r'^[A-Za-z][A-Za-z0-9_]+(\\[A-Za-z0-9_]{2,})*\\[A-Za-z][A-Za-z0-9_()]{4,}$', v):
                    continue                                   # not a stream path (false stream node)
                G[g]['streams'][v] += 1; seen_stream[g].add(v); reached.add(g)
            elif lk == 'missing':
                G[g]['refs']['unresolved'] += 1
        for g in reached:                                      # users: one per root (plex, emitter / event / object
            G[g]['waves'][kind] += 1                           # reference) that reaches a real wave / stream
            G[g]['wdrm'][base] += 1; G[g]['worigin'][origin] += 1
    with open(os.path.join(out_dir, 'groups_waves.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('group\twave_id\tname\n')
        for g in sorted(seen_wave, key=str):
            for w in sorted(seen_wave[g]):
                f.write('%s\t%d\t%s\n' % (g, w, wname.get(str(w), '?')))
        for g in sorted(seen_stream, key=str):
            for s in sorted(x for x in seen_stream[g] if x):
                f.write('%s\tstream\t%s\n' % (g, s))
    print('| group | parent | depth | category | Assign gb/unit/obj/glob | DTPs | waves (distinct) | users gb/unit/obj | streams (refs) | origin of the users | examples |')
    print('|---|---|---|---|---|---|---|---|---|---|---|')
    rows = list(range(T['count'])) + ['default']
    detail = []
    for g in rows:
        st = G.get(g)
        if g == 'default':
            par, dp, cat = '-', '-', 'no Assign -> slot [4] = %d' % dflt
        else:
            par = T['groups'][g]['parent']; dp = depth[g]
            cat = ' '.join('[%d]' % k for k, v in enumerate(T['cats']) if v == g)
            if g in T['pause']: cat += ' pause'
            if g in T['death']: cat += ' death'
        if st is None:
            print('| %s | %s | %s | %s | 0 | 0 | 0 | 0 | 0 | - | - |' % (g, par, dp, cat)); continue
        a = st['assign']; w = st['waves']
        names = collections.Counter()
        for wid in st['wave_ids']:
            nm = wname.get(str(wid))
            if nm:
                fam = re.sub(r'(_?\d+)?(\.wav|\.wa|\.w|\.)?$', '', nm.lower())
                names['(dlc wave, name silence)' if fam == 'silence' else fam] += 1
        ndlc = names.pop('(dlc wave, name silence)', 0)
        ex = ', '.join(n for n, _ in names.most_common(nex)) + (' (+%d DLC waves without a name)' % ndlc if ndlc else '')
        sx = ', '.join(sorted(x.split('\\')[-1] for x in st['streams'] if x)[:4])
        org = st['worigin'] if st['worigin'] else st['origin']
        print('| %s | %s | %s | %s | %d/%d/%d/%d | %d | %d | %d/%d/%d | %d | %s | %s%s |' % (
            g, par, dp, cat, a['generalbank'], a['unit'], a['object'], a['global'], len(st['dtp']),
            len(st['wave_ids']), w['generalbank'], w['unit'], w['object'], sum(st['streams'].values()),
            ' '.join('%s %d' % kv for kv in org.most_common()), ex, (' ; streams: ' + sx) if sx else ''))
        detail.append('== group %s (parent %s, %s)\n  DRMs (wave hits): %s\n  DRMs (assign): %s\n  waves: %s\n'
                      '  streams (%d): %s\n' % (
                          g, par, cat, ', '.join('%s %d' % kv for kv in st['wdrm'].most_common(12)),
                          ', '.join('%s %d' % kv for kv in st['drms'].most_common(12)),
                          ', '.join('%s %d' % kv for kv in names.most_common(40)), len(st['streams']),
                          ', '.join(sorted(x for x in st['streams'] if x)[:40])))
    with open(os.path.join(out_dir, 'groups_detail.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(detail)


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == 'table':
        cmd_table(a[1])
    elif a[0] == 'scan':
        mods = a[a.index('--mods') + 1] if '--mods' in a else None
        man = a[a.index('--manifest') + 1] if '--manifest' in a else None
        only = a[a.index('--only') + 1] if '--only' in a else None
        ng = int(a[a.index('--ngroups') + 1]) if '--ngroups' in a else 0x50
        cmd_scan(a[1], mods, man, only, ng)
    elif a[0] == 'report':
        nex = int(a[a.index('--examples') + 1]) if '--examples' in a else 10
        cmd_report(a[1], a[2], nex)
    else:
        sys.exit(__doc__)
