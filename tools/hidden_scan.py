"""Hidden-content scan (read-only): which units, cinematics, audio streams and images of the game archives does no
other file name? Builds a token index of every record of the PC bigfile / patch, the Xbox DLC packs, the Xbox title
update and the executables, then answers reference questions from it. No game bytes are written - the index keeps only
tokens (identifier-like words) and record names.

Token = run of [a-z0-9_] (lower case), 5..80 chars, taken from: the DRM header + dependency-name block, and the data of
every section except texture (5), wave (6), shader (9), mesh (12) and animation (2); for non-DRM records (.mul, .raw,
...) the first 64 KiB; executables completely. A file "references" NAME when NAME is one of its tokens. Portals of unit
DRMs (StreamUnitPortal.tolevelname via tools/unit_ids.level_info) are kept separately.

Limits: a name built at run time (sprintf "%s_%02d") or referenced only by a hash / id is not seen - a "no reference"
result is a candidate, not a proof; the reports say so.

Usage (from the repository root; outputs default to work/cut_scan/):
  ../bin/pyt -t 3600 tools/hidden_scan.py index [SRC ...]        SRC: pcbig pcpatch pack10 pack11 pack1 tu pcexe xtuexe
                                                                  xexe (default: all) -> work/cut_scan/idx_<SRC>.pkl
  ../bin/pyt -t 600 tools/hidden_scan.py refs NAME [NAME ...]     every record that has NAME as a token
  ../bin/pyt -t 600 tools/hidden_scan.py tokens REGEX [SRC ...]   every token matching REGEX (+ records), e.g. ^container
  ../bin/pyt -t 600 tools/hidden_scan.py strings SRC NAME.drm REGEX [--ctx N]   strings of one archived DRM (BE/LE)
  ../bin/pyt -t 600 tools/hidden_scan.py units [--out F]         unit reference / reachability table
  ../bin/pyt -t 600 tools/hidden_scan.py cines [--out F]          cinstream .mul: who names each cinematic
  ../bin/pyt -t 600 tools/hidden_scan.py audio [--out F]          audio streams + music folders without a reference
  ../bin/pyt -t 600 tools/hidden_scan.py images [--out F]         image\\*.raw (concept art etc.) without a reference
  ../bin/pyt -t 600 tools/hidden_scan.py unnamed [--out F]        records no file list names (size + token hints)
  ../bin/pyt -t 3600 tools/hidden_scan.py guess [SRC ...]         name unnamed hashes from tokens x known folders
  ../bin/pyt -t 300 tools/hidden_scan.py png IN.raw OUT.png        a PC image\\*.raw as PNG (to look at it)
"""
import sys, os, re, pickle, collections, struct
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'work', 'cut_scan')
LISTS = os.path.join(ROOT, 'work', 'generic', 'lists')
YURA = os.path.join(ROOT, 'ref', 'yura-release', 'FileLists')
DLCN = os.path.join(ROOT, 'work', 'generic', 'dlc_names.txt')
GAME = os.path.join(ROOT, '..', 'data', 'pc')
EXES = {'pcexe': (os.path.join(GAME, 'tru.exe.steam_original'), 'le'),
        'xtuexe': (os.path.join(ROOT, 'work', 'xenia_dump', 'tu_image_82000000.bin'), 'be'),
        'xexe': (os.path.join(ROOT, 'work', 'xenia_dump', 'retail_image_82000000.bin'), 'be')}
ARCH = ('pcbig', 'pcpatch', 'pack10', 'pack11', 'pack1', 'tu')
SKIP_TYPES = {2, 5, 6, 9, 12}
TOK = re.compile(rb'[a-z0-9_]{5,80}')


def name_map(pre):
    """{hash: path} from the Yura list of the platform (+ dlc_names.txt for Xenon)"""
    from names import crc
    d = {}
    fn = 'Tomb Raider Underworld (PC).txt' if pre == 'pc-w' else 'Tomb Raider Underworld (Xenon).txt'
    for l in open(os.path.join(YURA, fn), encoding='utf8', errors='ignore'):
        l = l.strip()
        if l: d[crc(l)] = l
    if pre != 'pc-w' and os.path.isfile(DLCN):
        for l in open(DLCN, encoding='utf8', errors='ignore'):
            t = l.split()
            if len(t) >= 6 and t[-1] != '?':
                d.setdefault(int(t[0], 16), t[-1].lstrip('\\'))
    return d


def tokens_of(raw, e):
    """(token set, portal names or None) of one record"""
    from drm import cdrm_decode, sections_with_data
    if raw[:4] in (b'CDRM', b'MRDC'):
        try: raw = cdrm_decode(raw, e)
        except Exception: return set(TOK.findall(raw[:65536].lower())), None
    E = '>' if e == 'be' else '<'
    is_drm = len(raw) > 24 and struct.unpack(E + 'i', raw[:4])[0] in (19, 20, 21, 22)
    if not is_drm:
        return set(TOK.findall(raw[:65536].lower())), None
    try:
        h, secs = sections_with_data(raw, e)
    except Exception:
        return set(TOK.findall(raw[:65536].lower())), None
    toks = set(TOK.findall(raw[:24 + 20 * len(secs) + h['namesz'] + h['padsz']].lower()))
    for s in secs:
        if s['type'] in SKIP_TYPES or not s['data']: continue
        toks.update(TOK.findall(s['data'].lower()))
    portals = None
    try:
        import unit_ids as U
        L = U.level_info(secs, e)
        if L is not None:
            portals = []
            for si, o in L['portals']:
                nm = secs[si]['data'][o:o + 128].split(b'\0', 1)[0].decode('latin1').lower()
                portals.append(nm)
    except Exception:
        portals = None
    return toks, portals


def _work(job):
    src, path, e, i = job
    from archive import Archive
    A = _work.cache.get(path)
    if A is None:
        A = _work.cache[path] = Archive(path, e)
    r = A.idx[i]
    try:
        raw = A.read(r)
    except Exception as ex:
        return i, None, None, 'read error %r' % ex
    t, p = tokens_of(raw, e)
    return i, t, p, None
_work.cache = {}


def index(srcs):
    import locals as LC
    from archive import Archive
    os.makedirs(OUT, exist_ok=True)
    for src in srcs:
        recs = []; tok = collections.defaultdict(list); portals = {}; errs = 0
        if src in EXES:
            path, e = EXES[src]
            if not os.path.isfile(path): print('skip %s: %s missing' % (src, path)); continue
            b = open(path, 'rb').read()
            recs.append((src, os.path.basename(path), 'exe', len(b)))
            for t in set(TOK.findall(b.lower())): tok[t].append(0)
        else:
            path, e, pre = LC.SRC[src]
            if not os.path.exists(path): print('skip %s: %s missing' % (src, path)); continue
            A = Archive(path, e); nm = name_map(pre)
            jobs = [(src, path, e, i) for i in range(len(A.idx))]
            with Pool(8) as P:
                res = P.map(_work, jobs, chunksize=16)
            for i, t, p, err in res:
                r = A.idx[i]
                label = nm.get(r['hash'], '0x%08x' % r['hash'])
                if r['spec'] not in (0xffffffff,): label += '@%08x' % r['spec']
                recs.append((src, label, '', r['size']))
                if err: errs += 1; continue
                k = len(recs) - 1
                for x in t: tok[x].append(k)
                if p is not None: portals[k] = p
        out = os.path.join(OUT, 'idx_%s.pkl' % src)
        with open(out, 'wb') as f:
            pickle.dump(dict(recs=recs, tok=dict(tok), portals=portals), f, protocol=4)
        print('%s: %d records, %d tokens, %d unit DRMs (portals), %d read errors -> %s' % (
            src, len(recs), len(tok), len(portals), errs, out))


class Index:
    """merged view over all idx_*.pkl: rec id = (src, k)"""
    def __init__(self, srcs=None):
        self.recs = {}; self.tok = collections.defaultdict(list); self.portals = {}
        for fn in sorted(os.listdir(OUT)):
            m = re.match(r'idx_(\w+)\.pkl$', fn)
            if not m or (srcs and m.group(1) not in srcs): continue
            D = pickle.load(open(os.path.join(OUT, fn), 'rb'))
            s = m.group(1)
            for k, r in enumerate(D['recs']): self.recs[(s, k)] = r
            for t, ks in D['tok'].items():
                if isinstance(t, bytes): t = t.decode('latin1')
                self.tok[t].extend((s, k) for k in ks)
            for k, p in D['portals'].items(): self.portals[(s, k)] = p
        self.srcs = sorted(set(s for s, _ in self.recs))

    def users(self, name):
        return self.tok.get(name.lower(), [])

    def label(self, rid):
        r = self.recs[rid]
        return '%s:%s' % (r[0], r[1])


def base(label):
    """file base name without folder, extension and @spec"""
    b = label.split('@')[0].replace('/', '\\').split('\\')[-1]
    return b.rsplit('.', 1)[0].lower() if '.' in b else b.lower()


def folder(label):
    p = label.split('@')[0].lower().replace('/', '\\').split('\\')
    return p[1] if len(p) > 2 else ''


def read_unitlist(path):
    L = [l for l in open(path, 'rb').read().decode('latin1').split('\r\n') if l]
    return L[1:]


def all_units():
    """{unit base: (path, [lists that name it])}"""
    out = {}
    for fn in ('pc_unitlist.txt', 'xbox_unitlist.txt', 'xboxtu_unitlist.txt', 'dlc_pack10_unitlist.txt',
               'dlc_pack11_unitlist.txt', 'dlc_pack1_unitlist.txt'):
        p = os.path.join(LISTS, fn)
        if not os.path.isfile(p): continue
        for u in read_unitlist(p):
            b = u.split('\\')[-1].lower()
            out.setdefault(b, [u, []])[1].append(fn.replace('_unitlist.txt', ''))
    return out


def rec_kind(I, rid, units):
    src, label, _, _ = I.recs[rid]
    if src in EXES: return 'exe'
    b = base(label); f = folder(label)
    if f == 'cinstream': return 'cine'
    if f == 'streamgroups': return 'streamgroup'
    if f in ('audio', 'music', 'image', 'local'): return f
    if b == 'generalbank': return 'generalbank'
    if b in ('objlist', 'unitlist', 'objectlist'): return 'list'
    if b == 'g_pda': return 'pda'
    if b.endswith('_map') and b[:-4] in units: return 'pdamap'
    if b in units: return 'unit'
    if label.startswith('0x'): return 'unnamed'
    if label.lower().split('@')[0].endswith('.drm'): return 'object'
    return 'other'


def fmt_users(I, rids, units, limit=8):
    by = collections.defaultdict(list)
    for r in rids:
        by[rec_kind(I, r, units)].append(r)
    parts = []
    for k in sorted(by):
        names = sorted(set('%s:%s' % (I.recs[r][0], base(I.recs[r][1])) for r in by[k]))
        more = '' if len(names) <= limit else ' +%d' % (len(names) - limit)
        parts.append('%s[%s%s]' % (k, ', '.join(names[:limit]), more))
    return '; '.join(parts)


def cmd_refs(names):
    I = Index(); units = all_units()
    for n in names:
        rids = I.users(n)
        print('%s: %d records' % (n, len(rids)))
        for r in sorted(rids):
            print('   %-12s %s' % (rec_kind(I, r, units), I.label(r)))


def cmd_tokens(pat, srcs):
    """every token matching a regex, with the records that hold it (for names built at run time / prefixes)"""
    I = Index(srcs or None); units = all_units(); rx = re.compile(pat)
    for t in sorted(x for x in I.tok if rx.search(x)):
        rids = I.tok[t]
        print('%-40s %3d  %s' % (t, len(rids), fmt_users(I, rids, units, 5)))


def cmd_strings(src, name, pat, ctx):
    """strings of one DRM of an archive (any endian) matching a regex, with section, offset and ctx neighbours"""
    import locals as LC
    from archive import Archive
    from names import crc
    from drm import cdrm_decode, sections_with_data
    path, e, pre = LC.SRC[src]
    A = Archive(path, e)
    recs = A.find(crc(pre + '\\' + name))
    if not recs: raise SystemExit('%s not in %s' % (name, src))
    raw = cdrm_decode(A.read(recs[-1]), e)
    h, secs = sections_with_data(raw, e)
    rx = re.compile(pat, re.I); hits = 0
    for s in secs:
        if s['type'] in SKIP_TYPES or not s['data']: continue
        ss = [(m.start(), m.group().decode('latin1')) for m in re.finditer(rb'[\x20-\x7e]{4,}', s['data'])]
        for k, (o, t) in enumerate(ss):
            if not rx.search(t): continue
            hits += 1
            near = ' | '.join(x for _, x in ss[max(0, k - ctx):k + ctx + 1])
            print('sec type %d id %d off 0x%x: %s%s' % (s['type'], s['id'], o, t, ('   [' + near + ']') if ctx else ''))
    print('%s %s: %d sections, %d hits' % (src, name, len(secs), hits))


def cmd_unnamed(out):
    """records whose hash no file list names, with size and a few of their tokens (hints what they are)"""
    I = Index()
    inv = collections.defaultdict(list)
    for t, rids in I.tok.items():
        for r in rids:
            if I.recs[r][1].startswith('0x'): inv[r].append(t)
    lines = ['# tools/hidden_scan.py unnamed; sources: %s' % ', '.join(I.srcs), '# src\thash@spec\tsize\ttokens (first 12, sorted)']
    cnt = collections.Counter()
    for rid in sorted(r for r in I.recs if I.recs[r][1].startswith('0x')):
        src, label, _, size = I.recs[rid]; cnt[src] += 1
        lines.append('%s\t%s\t%d\t%s' % (src, label, size, ' '.join(sorted(inv.get(rid, []))[:12])))
    lines.append('# unnamed records: %s (of %s)' % (', '.join('%s %d' % kv for kv in sorted(cnt.items())),
                 ', '.join('%s %d' % (s, sum(1 for r in I.recs if r[0] == s)) for s in I.srcs)))
    write(out or os.path.join(OUT, 'unnamed.tsv'), lines)


def cmd_guess(srcs):
    """try to name unnamed records: every token of the given sources (default pack10 pack11 tu) under every folder /
    extension seen in the file lists (xenon-w + pc-w), hashed with the archive CRC and compared with unnamed hashes"""
    from names import crc
    I = Index(); srcs = srcs or ['pack10', 'pack11', 'tu']
    want = {}
    for rid, (src, label, _, _) in I.recs.items():
        if label.startswith('0x'): want.setdefault(int(label.split('@')[0], 16), []).append('%s:%s' % (src, label))
    folders = set()
    for fn in ('Tomb Raider Underworld (PC).txt', 'Tomb Raider Underworld (Xenon).txt'):
        for l in open(os.path.join(YURA, fn), encoding='utf8', errors='ignore'):
            l = l.strip().lower()
            if '\\' in l and '.' in l:
                d, f = l.rsplit('\\', 1)
                folders.add((d.replace('pc-w', 'xenon-w', 1), '.' + f.rsplit('.', 1)[1]))
    for l in open(DLCN, encoding='utf8', errors='ignore'):
        t = l.split()
        if len(t) >= 6 and t[-1] != '?' and '\\' in t[-1] and '.' in t[-1]:
            d, f = t[-1].lower().lstrip('\\').rsplit('\\', 1); folders.add((d, '.' + f.rsplit('.', 1)[1]))
    folders = set(f for f in folders if f[1] in ('.mul', '.drm', '.raw', '.mus', '.sam'))
    toks = sorted(set(t for t, rids in I.tok.items() if any(r[0] in srcs for r in rids) and len(t) <= 60))
    print('%d unnamed hashes, %d tokens, %d folder/extension pairs' % (len(want), len(toks), len(folders)))
    tab = []                               # table form of names.crc (MSB first, poly 0x04c11db7, init / xorout ffffffff)
    for i in range(256):
        c = i << 24
        for _ in range(8): c = ((c << 1) ^ 0x4c11db7) & 0xffffffff if c & 0x80000000 else (c << 1) & 0xffffffff
        tab.append(c)

    def fcrc(s, h=0xffffffff):
        for ch in s: h = ((h << 8) & 0xffffffff) ^ tab[((h >> 24) ^ ord(ch)) & 0xff]
        return h
    assert (~fcrc('xenon-w\\a\\b.mul')) & 0xffffffff == crc('xenon-w\\a\\b.mul')
    hits = 0
    for d, ext in sorted(folders):
        pre = fcrc(d + '\\')
        for t in toks:
            h = (~fcrc(t + ext, pre)) & 0xffffffff
            if h in want:
                hits += 1; print('NAMED 0x%08x = %s\\%s%s  (%s)' % (h, d, t, ext, ', '.join(want[h][:2])))
    print('%d hashes named' % hits)


def own(I, rid, names):
    return base(I.recs[rid][1]) in names


def cmd_units(out):
    I = Index(); units = all_units()
    present = collections.defaultdict(list)
    for rid, (src, label, _, _) in I.recs.items():
        b = base(label)
        if b in units and label.lower().split('@')[0].endswith('.drm'): present[b].append(src)
    # edges: unit A -> unit B when A's DRM (or one of A's streamgroups) names B; portals separately
    edges = collections.defaultdict(set); portal_edges = collections.defaultdict(set)
    roots = collections.defaultdict(set)
    rows = []
    for u in sorted(units):
        rids = [r for r in I.users(u) if base(I.recs[r][1]) != u]
        kinds = collections.Counter(rec_kind(I, r, units) for r in rids)
        for r in rids:
            k = rec_kind(I, r, units)
            src_u = base(I.recs[r][1])
            if k == 'unit':
                edges[src_u].add(u)
                if u in (I.portals.get(r) or []): portal_edges[src_u].add(u)
            elif k in ('streamgroup', 'list', 'pda', 'pdamap', 'local'):
                pass        # inventories / PDA map pages / text: name a unit, but do not load it
            else:
                roots[u].add('%s:%s' % (I.recs[r][0], base(I.recs[r][1])))
        rows.append((u, units[u], kinds, rids))
    # reachability from units named outside unit DRMs (exe, generalbank, object scripts, cine data)
    seen = set(u for u in units if roots[u]); todo = list(seen)
    while todo:
        a = todo.pop()
        for b in edges.get(a, ()):
            if b not in seen: seen.add(b); todo.append(b)
    pseen = set(u for u in units if roots[u]); todo = list(pseen)
    while todo:
        a = todo.pop()
        for b in portal_edges.get(a, ()):
            if b not in pseen: pseen.add(b); todo.append(b)
    lines = ['# tools/hidden_scan.py units; sources: %s' % ', '.join(I.srcs),
             '# unit\tlists\tDRM in\tref records\treachable(any ref)\treachable(portals only)\troots\tportal-from\tall users']
    nz = 0; nr = 0; np_ = 0
    for u, (path, lists), kinds, rids in rows:
        pf = sorted(a for a, bs in portal_edges.items() if u in bs)
        nz += not rids; nr += u not in seen; np_ += u not in pseen
        lines.append('%s\t%s\t%s\t%d\t%s\t%s\t%s\t%s\t%s' % (
            path, ','.join(lists), ','.join(sorted(set(present.get(u, [])))) or '-', len(rids),
            'yes' if u in seen else 'NO', 'yes' if u in pseen else 'NO', ', '.join(sorted(roots[u])[:6]) or '-',
            ', '.join(pf) or '-', fmt_users(I, rids, units)))
    lines.append('# %d units; %d named by no other record; %d not reachable from a root over any name reference; '
                 '%d not reachable over portals only' % (len(rows), nz, nr, np_))
    write(out or os.path.join(OUT, 'units.tsv'), lines)


def write(path, lines):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    print('\n'.join(l for l in lines if l.startswith('# ') and not l.startswith('# unit') and not l.startswith('# name')))
    print('wrote', path)


def files_in(I, fold, ext):
    """{base: [labels]} of records in a folder with an extension (named records only)"""
    d = collections.defaultdict(set)
    for rid, (src, label, _, _) in I.recs.items():
        p = label.split('@')[0].lower()
        if folder(label) == fold and p.endswith(ext): d[base(label)].add('%s:%s' % (src, p))
    return d


def cmd_cines(out):
    I = Index(); units = all_units()
    cines = files_in(I, 'cinstream', '.mul')
    lines = ['# tools/hidden_scan.py cines; sources: %s' % ', '.join(I.srcs),
             '# name\tfiles\tunit users\tscript/object users\tgeneralbank\texe\tother users']
    n_none = n_nounit = 0; listed = []
    for c in sorted(cines):
        rids = [r for r in I.users(c) if base(I.recs[r][1]) != c]
        by = collections.defaultdict(set)
        for r in rids:
            by[rec_kind(I, r, units)].add('%s:%s' % (I.recs[r][0], base(I.recs[r][1])))
        u = sorted(by.pop('unit', set())); o = sorted(by.pop('object', set()) | by.pop('unnamed', set()))
        g = sorted(by.pop('generalbank', set())); x = sorted(by.pop('exe', set()))
        rest = '; '.join('%s[%s]' % (k, ', '.join(sorted(v)[:6])) for k, v in sorted(by.items()))
        n_none += not rids; n_nounit += not u and not o
        if not u and not o: listed.append(c)
        lines.append('%s\t%s\t%s\t%s\t%s\t%s\t%s' % (c, ', '.join(sorted(cines[c])), ', '.join(u) or '-',
                     ', '.join(o) or '-', ', '.join(g) or '-', ', '.join(x) or '-', rest or '-'))
    lines.append('# %d cinematic streams; %d named by no other record; %d named by no unit / object DRM: %s' % (
        len(cines), n_none, n_nounit, ', '.join(listed)))
    write(out or os.path.join(OUT, 'cines.tsv'), lines)


_ARCH = {}


def raw_contains(rid, needle):
    """re-read one indexed record (decoded) and test for a byte string - for names with characters outside the token
    alphabet, e.g. 'thor_reveal_1(2)' (the index only holds the token 'thor_reveal_1')"""
    import locals as LC
    from archive import Archive
    from drm import cdrm_decode
    src, k = rid
    if src in EXES:
        b = open(EXES[src][0], 'rb').read()
    else:
        path, e, pre = LC.SRC[src]
        A = _ARCH.get(src) or _ARCH.setdefault(src, Archive(path, e))
        b = A.read(A.idx[k])
        if b[:4] in (b'CDRM', b'MRDC'): b = cdrm_decode(b, e)
    return needle.lower().encode('latin1') in b.lower()


def users_full(I, name):
    """records naming NAME; names with non-token characters: token-prefix candidates checked on the raw bytes"""
    m = re.match(r'[a-z0-9_]+', name.lower())
    if m and m.group() == name.lower():
        return I.users(name)
    if not m or len(m.group()) < 5: return []
    return [r for r in I.users(m.group()) if raw_contains(r, name)]


def cmd_audio(out):
    I = Index(); units = all_units()
    lines = ['# tools/hidden_scan.py audio; sources: %s' % ', '.join(I.srcs),
             '# group\tname\tfiles\tusers']
    stat = collections.Counter(); free = collections.defaultdict(list)
    groups = collections.defaultdict(lambda: collections.defaultdict(set))
    for rid, (src, label, _, _) in I.recs.items():
        p = label.split('@')[0].lower().replace('/', '\\').split('\\')
        if len(p) >= 4 and p[1] == 'audio' and p[2] == 'streams':
            groups['audio\\' + p[3]][base(label)].add('%s:%s' % (src, '\\'.join(p)))
        elif len(p) >= 4 and p[1] == 'music':
            groups['music'][p[2]].add('%s:%s' % (src, '\\'.join(p)))
    for g in sorted(groups):
        for n in sorted(groups[g]):
            rids = [r for r in users_full(I, n) if base(I.recs[r][1]) != n and not (g == 'music' and folder(I.recs[r][1]) == 'music')]
            stat[(g, bool(rids))] += 1
            if not rids: free[g].append(n)
            lines.append('%s\t%s\t%s\t%s' % (g, n, ', '.join(sorted(groups[g][n])[:3]), fmt_users(I, rids, units, 4) or 'NONE'))
    for g in sorted(groups):
        lines.append('# %s: %d names, %d with a reference, %d without: %s' % (
            g, stat[(g, True)] + stat[(g, False)], stat[(g, True)], stat[(g, False)], ', '.join(free[g][:400])))
    write(out or os.path.join(OUT, 'audio.tsv'), lines)


def cmd_images(out):
    I = Index(); units = all_units()
    imgs = files_in(I, 'image', '.raw')
    lines = ['# tools/hidden_scan.py images; sources: %s' % ', '.join(I.srcs), '# name\tfiles\tusers']
    free = []; conc = 0; conc_free = []
    for n in sorted(imgs):
        rids = [r for r in I.users(n) if base(I.recs[r][1]) != n]
        conc += n.startswith('concept_')
        if not rids:
            free.append(n)
            if n.startswith('concept_'): conc_free.append(n)
        lines.append('%s\t%s\t%s' % (n, ', '.join(sorted(imgs[n])[:3]), fmt_users(I, rids, units, 4) or 'NONE'))
    lines.append('# %d image names (%d concept_*); %d without a reference: %s' % (len(imgs), conc, len(free), ', '.join(free)))
    lines.append('# concept_* without a reference: %d: %s' % (len(conc_free), ', '.join(conc_free)))
    write(out or os.path.join(OUT, 'images.tsv'), lines)


def main(argv):
    if not argv:
        print(__doc__); return 2
    out = None
    if '--out' in argv:
        k = argv.index('--out'); out = argv[k + 1]; del argv[k:k + 2]
    c = argv[0]
    if c == 'index': index(argv[1:] or list(ARCH) + list(EXES))
    elif c == 'refs': cmd_refs(argv[1:])
    elif c == 'tokens': cmd_tokens(argv[1], argv[2:])
    elif c == 'strings':
        ctx = 0
        if '--ctx' in argv:
            k = argv.index('--ctx'); ctx = int(argv[k + 1]); del argv[k:k + 2]
        cmd_strings(argv[1], argv[2], argv[3], ctx)
    elif c == 'units': cmd_units(out)
    elif c == 'cines': cmd_cines(out)
    elif c == 'audio': cmd_audio(out)
    elif c == 'images': cmd_images(out)
    elif c == 'unnamed': cmd_unnamed(out)
    elif c == 'guess': cmd_guess(argv[1:])
    elif c == 'png':                    # png IN.raw OUT.png : a PC image\*.raw (e.g. concept art) as PNG to look at
        import raw_image_convert as RI
        RI.to_png(open(argv[1], 'rb').read(), argv[2]); print('wrote', argv[2])
    else: print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]) or 0)
