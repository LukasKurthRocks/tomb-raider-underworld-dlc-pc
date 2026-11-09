"""TU coverage list: every changed and every new function of the title update (Xbox, TU vs retail) with a topic, a PC
partner where one is mapped, and a status (ported / explained / irrelevant / open) - read-only (TODO N20, 09.11.2026).

Inputs (all workspace-relative):
  work/xenia_dump/retail_image_82000000.bin, work/xenia_dump/tu_image_82000000.bin   Xenia image dumps
      -> functions aligned exactly like tools/xbox_func_diff.py (equal / changed / new)
  work/xmap/xbox_pc_map.tsv            retail -> PC function map (tier verified / anchor / unverified / contradicted)
  work/proto2007/proto_retail_pc_names.tsv   2007 prototype names (name, obj) per retail function
  src/asi/<plugin>/*.cpp|*.md|*.ini    TU / retail addresses our plugins translate (TruGuard is never read)
  docs/ENGINE.md, ../docs/Befund-*.md  TU / retail addresses mentioned in findings (local docs, if present)
  docs/data/tu_coverage_overrides.tsv  hand-kept statuses (tu_addr, status, basis, plugin, note) - win over everything

Status rules (honest: unknown = open):
  ported      an address inside the function is named in a plugin source / README (basis doc; override: code)
  explained   only via the override file (a finding says no port is needed)
  irrelevant  prototype object of an Xbox platform library (xmedia, xam, xui, xnet, live, storage, Xenos d3d) -
              basis heuristic; or via override
  open        everything else; `refs` lists findings / ENGINE.md that mention it (known but not ported)
Topic: from the prototype object of the retail partner, else a vote of the named callers / callees, else strings,
else data marks (doppelganger flag disp 0x1244, meter +0x508, TU global 0x827754ac); `topic_basis` says which.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/tu_coverage.py [--out docs/data/tu_coverage.tsv] [--summary FILE]
Output: the TSV (one row per changed / new TU function) and a summary (counts per status / topic, biggest open
topics) on stdout and in --summary. Only addresses, names and counts are written - no game bytes.
"""
import sys, os, re, struct, difflib, collections, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xbox_func_diff as XD
import ppc_xrefs as P

BASE = 0x82000000
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
WS = os.path.normpath(os.path.join(ROOT, '..'))
RETAIL = os.path.join(ROOT, 'work', 'xenia_dump', 'retail_image_82000000.bin')
TU = os.path.join(ROOT, 'work', 'xenia_dump', 'tu_image_82000000.bin')
XMAP = os.path.join(ROOT, 'work', 'xmap', 'xbox_pc_map.tsv')
PROTO = os.path.join(ROOT, 'work', 'proto2007', 'proto_retail_pc_names.tsv')
OVR = os.path.join(ROOT, 'docs', 'data', 'tu_coverage_overrides.tsv')

PLATFORM = ('xmedia:', 'xam', 'xui', 'xnet', 'xonline', 'xhv', 'xapilib', 'xboxkrnl', 'xgraphics', 'd3d9:', 'd3d9i:',
            'xbdm', 'xcontent', 'xstorage', 'xlive', 'xact', 'x3daudio', 'xaudio', 'fmodxbox360', 'xenonsave')
TOPICS = [  # (topic, keywords in prototype name / object, lower case) - first hit wins
    ('enemy / combat', ('enemy', 'thrall', 'combat', 'sense', 'behavior', 'behaviour', 'attack', 'melee', 'damage',
                        'health', 'chunk', 'targeting', 'targeter', 'creature', 'yeti', 'soldier')),
    ('player / chart', ('player', 'lara', 'playersc', 'statechart', 'chart', 'doppel', 'shadow')),
    ('camera', ('camera',)),
    ('physics', ('physics', 'multibody', 'ntmultibody', 'collide', 'collision', 'chuckable', 'ragdoll', 'rigid',
                 'sweepandprune', 'geom', 'joint', 'body', 'contact')),
    ('markup / navigation', ('markup', 'navmesh', 'navgraph', 'nav', 'path', 'jump', 'ledge', 'climb', 'grab',
                             'parabola', 'solvecubic', 'trmarkup')),
    ('animation / cloth', ('anim', 'cloth', 'hair', 'skeleton', 'bone', 'ik')),
    ('render / fx', ('render', 'draw', 'shader', 'light', 'texture', 'material', 'vertex', 'effect', 'fx', 'particle',
                     'scene', 'model', 'blur', 'reticle', 'decal', 'shadowmap', 'gpu', 'nga')),
    ('sound', ('sound', 'audio', 'fmod', 'music', 'voice', 'dialog')),
    ('ui / hud', ('ui', 'hud', 'menu', 'pda', 'screen', 'font', 'text', 'subtitle', 'local', 'objective', 'hint')),
    ('script', ('script', 'native', 'cdcscript', 'scenums')),
    ('streaming / save', ('stream', 'load', 'unit', 'level', 'drm', 'file', 'save', 'resource', 'memory', 'heap',
                          'archive', 'objectlist')),
    ('input', ('input', 'pad', 'controller', 'rumble', 'button')),
]
MARKS = {0x1244: 'doppelganger flag disp 0x1244', 0x508: 'meter +0x508'}
GLOBAL_MARKS = {0x827754ac: 'TU global 0x827754ac', 0x827754cc: 'TU global 0x827754cc'}
ADDR_RE = re.compile(r'0x82[0-9a-fA-F]{6}')


def topic_of(text):
    """keywords of <= 3 letters must be a whole word token (CamelCase / non-letters split), longer ones a substring"""
    t = text.lower()
    tokens = set(w.lower() for w in re.findall(r'[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+', text))
    for name, keys in TOPICS:
        if any((k in tokens) if len(k) <= 3 else (k in t) for k in keys):
            return name
    return ''


def is_platform(obj):
    o = obj.lower()
    return any(o.startswith(p) or (':' in o and p.rstrip(':') in o.split(':')[0]) for p in PLATFORM)


def align():
    rd, rf, rh = XD.functions(RETAIL)
    td, tf, th = XD.functions(TU)
    sm = difflib.SequenceMatcher(None, rh, th, autojunk=False)
    equal, changed, new, removed = [], [], [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            equal += [(rf[i], tf[j]) for i, j in zip(range(i1, i2), range(j1, j2))]
        elif tag == 'insert':
            new += tf[j1:j2]
        elif tag == 'delete':
            removed += rf[i1:i2]
        else:
            n = min(i2 - i1, j2 - j1)
            changed += [(rf[i1 + k], tf[j1 + k]) for k in range(n)]
            new += tf[j1 + n:j2]
            removed += rf[i1 + n:i2]
    return rd, rf, td, tf, equal, changed, new, removed


def read_tsv(path):
    if not os.path.exists(path):
        return []
    lines = open(path, encoding='utf-8-sig').read().splitlines()
    rows = [l.split('\t') for l in lines if l.strip() and not l.startswith('#')]
    head = rows[0]
    return [dict(zip(head, r + [''] * (len(head) - len(r)))) for r in rows[1:]]


def cstring(d, a):
    o = a - BASE
    if o < 0 or o >= len(d) - 4:
        return None
    e = d.find(b'\0', o, o + 96)
    if e < 0 or e - o < 5:
        return None
    s = d[o:e]
    if all(32 <= c < 127 for c in s) and sum(chr(c).isalpha() for c in s) >= 3:
        t = s.decode('ascii')
        if ':\\' in t or '\\' in t or ':/' in t:      # file paths of the Xbox build: not needed, kept out of the repo
            return None
        return t
    return None


NEGATED = re.compile(r'not (yet )?(translated|ported)|untranslated|nicht (übersetzt|portiert)|no port', re.I)


def harvest(paths, label):
    """[(address, kind tu/retail/unlabeled, source label, negated)] from text files; negated = the same line says the
    address is NOT translated / ported (then it only counts as a mention)"""
    out = []
    for p in paths:
        try:
            t = open(p, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        for m in ADDR_RE.finditer(t):
            pre = t[max(0, m.start() - 16):m.start()]
            kind = 'retail' if 'retail' in pre.lower() else ('tu' if re.search(r'\bTU\b', pre) else 'unlabeled')
            ls, le = t.rfind('\n', 0, m.start()) + 1, t.find('\n', m.end())
            neg = bool(NEGATED.search(t[ls:le if le >= 0 else len(t)]))
            out.append((int(m.group(0), 16), kind, label(p), neg))
    return out


PLUGIN_TOPIC = {'TruShadowCombat': 'enemy / combat', 'TruShadowPower': 'player / chart', 'TruRockVein':
                'markup / navigation', 'TruShadowHud': 'ui / hud', 'TruDlc2Player': 'player / chart',
                'TruDoppelganger': 'player / chart'}
WEAK = ('', '2nd-ring neighbours (weak)', 'callers / callees', 'strings', 'data marks')


def main(argv):
    out = os.path.join(ROOT, 'docs', 'data', 'tu_coverage.tsv')
    summ = None
    if '--out' in argv:
        out = argv[argv.index('--out') + 1]
    if '--summary' in argv:
        summ = argv[argv.index('--summary') + 1]
    rd, rf, td, tf, equal, changed, new, removed = align()
    tu_starts = [f[0] for f in tf]
    tu_end = dict(tf)
    rt_starts = [f[0] for f in rf]
    rt_end = dict(rf)
    tu2rt = {t[0]: r[0] for r, t in equal + changed}
    rt2tu = {r[0]: t[0] for r, t in equal + changed}
    cls = {t[0]: 'changed' for r, t in changed}
    cls.update({t[0]: 'new' for t in new})
    xmap = {}
    for r in read_tsv(XMAP):
        try:
            xmap[int(r['xbox_retail'], 16)] = (r['pc'], r['tier'])
        except (KeyError, ValueError):
            pass
    proto = {}
    for r in read_tsv(PROTO):
        if r.get('retail'):
            try:
                proto.setdefault(int(r['retail'], 16), (r['name'], r['obj']))
            except ValueError:
                pass
    funcs, res = P.cached(TU)
    callers = collections.defaultdict(set)
    for fs, items in res.items():
        for a, k, v in items:
            if k == 'call':
                callers[v].add(fs)

    def name_of_tu(fs):
        rp = tu2rt.get(fs)
        return proto.get(rp, ('', ''))[0] if rp else ''

    def obj_of_tu(fs):
        rp = tu2rt.get(fs)
        return proto.get(rp, ('', ''))[1] if rp else ''

    def owner(starts, ends, a):
        i = __import__('bisect').bisect_right(starts, a) - 1
        if i >= 0 and starts[i] <= a < ends[starts[i]]:
            return starts[i]
        return None

    # where our plugins / findings name addresses
    plugin_files = []
    for p in glob.glob(os.path.join(ROOT, 'src', 'asi', '*', '*')):
        if 'TruGuard' in p or 'third_party' in p:
            continue
        if p.lower().endswith(('.cpp', '.h', '.md', '.ini', '.txt')):
            plugin_files.append(p)
    hits_plugin = harvest(plugin_files, lambda p: os.path.basename(os.path.dirname(p)))
    doc_files = [os.path.join(ROOT, 'docs', 'ENGINE.md')] + sorted(glob.glob(os.path.join(WS, 'docs', 'Befund-*.md')))
    hits_doc = harvest(doc_files, lambda p: os.path.basename(p))
    plug_by_fn = collections.defaultdict(set)
    doc_by_fn = collections.defaultdict(set)
    hits_doc += [(a, k, 'plugin ' + s + ' (not ported)', n) for a, k, s, n in hits_plugin if n]
    hits_plugin = [h for h in hits_plugin if not h[3]]
    why = int(argv[argv.index('--why') + 1], 16) if '--why' in argv else None
    for hits, target in ((hits_plugin, plug_by_fn), (hits_doc, doc_by_fn)):
        for a, kind, src, neg in hits:
            if why is not None:
                fw = owner(tu_starts, tu_end, a) if kind != 'retail' else None
                rw = owner(rt_starts, rt_end, a) if kind == 'retail' else None
                if fw == why or (rw is not None and rt2tu.get(rw) == why):
                    print('why 0x%08x: 0x%08x (%s) from %s' % (why, a, kind, src))
            fn = None
            if kind in ('tu', 'unlabeled'):          # unlabeled addresses are read as TU addresses only
                fn = owner(tu_starts, tu_end, a)
            elif kind == 'retail':
                rfn = owner(rt_starts, rt_end, a)
                if rfn is not None:
                    fn = rt2tu.get(rfn)
            if fn is not None and fn in cls:
                target[fn].add(src)
    ovr = {}
    for r in read_tsv(OVR):
        try:
            a = int(r['tu_addr'], 16)
        except (KeyError, ValueError):
            continue
        fn = owner(tu_starts, tu_end, a)          # any address inside the function names it
        if fn is not None:
            ovr[fn] = r
        else:
            print('override 0x%08x: not inside a TU function - ignored' % a)

    rows = []
    for fs in sorted(cls):
        fe = tu_end[fs]
        rp = tu2rt.get(fs)
        pc, tier = xmap.get(rp, ('', '')) if rp else ('', '')
        pname, pobj = proto.get(rp, ('', '')) if rp else ('', '')
        items = res.get(fs, [])
        callees = sorted({v for a, k, v in items if k == 'call'})
        built = sorted({v for a, k, v in items if k == 'addr'})
        strs = []
        for v in built:
            s = cstring(td, v)
            if s and s not in strs:
                strs.append(s)
        marks = []
        for a in range(fs, fe, 4):
            w = struct.unpack_from('>I', td, a - BASE)[0]
            if (w >> 26) in P.LOADSTORE and (w & 0xffff) in MARKS and MARKS[w & 0xffff] not in marks:
                marks.append(MARKS[w & 0xffff])
        marks += [GLOBAL_MARKS[v] for v in built if v in GLOBAL_MARKS and GLOBAL_MARKS[v] not in marks]
        neigh = [n for n in (name_of_tu(c) for c in callees) if n] + \
                [n for n in (name_of_tu(c) for c in callers.get(fs, ())) if n]
        nobj = [o for o in (obj_of_tu(c) for c in list(callees) + list(callers.get(fs, ()))) if o]
        topic, tb = '', ''
        if pname or pobj:
            topic, tb = topic_of(pobj + ' ' + pname), 'proto name'
            if not topic and pobj and is_platform(pobj):
                topic, tb = 'xbox platform library', 'proto object'
        if not topic and neigh and all(n.startswith('FMOD::') for n in neigh):
            topic, tb = 'xbox platform library', 'callers / callees (FMOD only)'
        if not topic and (neigh or nobj):
            votes = collections.Counter(t for t in (topic_of(x) for x in neigh + nobj) if t)
            if votes:
                topic, tb = votes.most_common(1)[0][0], 'callers / callees'
            elif nobj and all(is_platform(o) for o in nobj):
                topic, tb = 'xbox platform library', 'callers / callees'
        if not topic:
            ring = set()
            for c in list(callees) + list(callers.get(fs, ())):
                ring.update(v for a, k, v in res.get(c, []) if k == 'call')
                ring.update(callers.get(c, ()))
            ring.discard(fs)
            r2 = [x for x in ([name_of_tu(c) for c in ring] + [obj_of_tu(c) for c in ring]) if x]
            votes = collections.Counter(t for t in (topic_of(x) for x in r2) if t)
            if votes and votes.most_common(1)[0][1] >= 2:
                topic, tb = votes.most_common(1)[0][0], '2nd-ring neighbours (weak)'
        if not topic and strs:
            t = topic_of(' '.join(strs))
            if t:
                topic, tb = t, 'strings'
        if not topic and marks:
            topic, tb = ('player / chart' if any('doppel' in m or 'meter' in m or 'global' in m for m in marks)
                         else ''), 'data marks'
        if not topic:
            topic, tb = '?', ''
        status, basis, plugin, note = 'open', 'heuristic', '', ''
        if plug_by_fn.get(fs):
            status, basis, plugin = 'ported', 'doc', ','.join(sorted(plug_by_fn[fs]))
            pt = [PLUGIN_TOPIC[p] for p in sorted(plug_by_fn[fs]) if p in PLUGIN_TOPIC]
            if pt and tb in WEAK:
                topic, tb = pt[0], 'plugin that ports it'
        elif topic == 'xbox platform library' or (pobj and is_platform(pobj)):
            status, basis, note = 'irrelevant', 'heuristic', 'Xbox platform library (%s; the PC has its own)' % (
                pobj or tb)
        if fs in ovr:
            o = ovr[fs]
            status = o.get('status') or status
            basis = o.get('basis') or basis
            plugin = o.get('plugin') or plugin
            note = o.get('note') or note
        rows.append([
            '0x%08x' % fs, cls[fs], str(fe - fs), ('0x%08x' % rp) if rp else '',
            str(rt_end[rp] - rp) if rp else '', pc, tier, pname, pobj, topic, tb, '; '.join(marks),
            ' | '.join(s[:40] for s in strs[:3]), ', '.join(sorted(set(neigh))[:4]), status, plugin, basis,
            ', '.join(sorted(doc_by_fn.get(fs, ())))[:200], note])
    head = ['tu_addr', 'class', 'size', 'retail', 'retail_size', 'pc', 'pc_tier', 'proto_name', 'proto_obj', 'topic',
            'topic_basis', 'marks', 'strings', 'named_neighbours', 'status', 'plugin', 'basis', 'refs', 'note']
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(head) + '\n')
        for r in rows:
            f.write('\t'.join(c.replace('\t', ' ').replace('\n', ' ') for c in r) + '\n')

    size = lambda r: int(r[2])
    lines = ['TU coverage (retail -> TU): equal %d, changed %d, new %d, removed %d; listed %d (changed + new), %d B'
             % (len(equal), len(changed), len(new), len(removed), len(rows), sum(map(size, rows)))]
    st = collections.Counter(r[14] for r in rows)
    sb = collections.Counter()
    for r in rows:
        sb[r[14]] += size(r)
    lines.append('status: ' + ', '.join('%s %d (%d B)' % (k, st[k], sb[k]) for k in ('ported', 'explained',
                                                                                     'irrelevant', 'open')))
    lines.append('basis: ' + ', '.join('%s %d' % kv for kv in collections.Counter(r[16] for r in rows).most_common()))
    lines.append('documented in findings / ENGINE.md (any status): %d' % sum(1 for r in rows if r[17]))
    lines.append('open but documented (known, not ported): %d' % sum(1 for r in rows if r[14] == 'open' and r[17]))
    lines.append('PC partner mapped: %d (tiers %s)' % (sum(1 for r in rows if r[5]), dict(collections.Counter(
        r[6] for r in rows if r[5]))))
    lines.append('topic (all rows / open rows / open bytes):')
    tall = collections.Counter(r[9] for r in rows)
    topen = collections.Counter(r[9] for r in rows if r[14] == 'open')
    tob = collections.Counter()
    for r in rows:
        if r[14] == 'open':
            tob[r[9]] += size(r)
    for t, n in tall.most_common():
        lines.append('  %-24s %5d %5d %8d' % (t, n, topen[t], tob[t]))
    lines.append('topic basis: ' + ', '.join('%s %d' % (k or '-', v) for k, v in
                                           collections.Counter(r[10] for r in rows).most_common()))
    lines.append('biggest open functions:')
    for r in sorted((r for r in rows if r[14] == 'open'), key=size, reverse=True)[:15]:
        lines.append('  %s %-7s %6s B  %-22s %s %s' % (r[0], r[1], r[2], r[9], r[7][:40], ('refs: ' + r[17][:60])
                                                       if r[17] else ''))
    text = '\n'.join(lines)
    print(text)
    if summ:
        open(summ, 'w', encoding='utf-8').write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
