"""Prototype vs final DLC comparison (read-only on all inputs; docs/Befund-Prototyp-DLC.md). Works on Xbox 360
(big-endian) bigfiles (packNN.000) extracted from LIVE packages with tools/stfs_extract.py, and on spa.bin (XDBF).
Only names, sizes, ids, counts and hashes are reported (no file bytes).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/proto_dlc_compare.py index ARCHIVE.000 OUT.pkl
        one pass over the archive: per record hash / spec / size / md5 of the decoded file / kind; per DRM the
        dependency names and every section (type, id, size, md5 of data and relocations, first u32 = DTP format
        word); identifier strings (name candidates); small text / list files kept in the cache
  ../bin/pyt -t 1800 tools/proto_dlc_compare.py compare A.pkl B.pkl OUT_PREFIX [--labels A,B]
        record level (same / changed / only A / only B, by name hash + spec mask; names from the Xbox file list,
        work/generic/dlc_names.txt and template search over the strings of both archives), section level for every
        changed DRM (by type + id; sections only on one side are matched by content md5 = "renumbered"), totals by
        section kind, objectlist / unitlist / locals.bin differences.
        Writes OUT_PREFIX.txt (report) and OUT_PREFIX.json
  ../bin/pyt -t 600 tools/proto_dlc_compare.py drm A.pkl B.pkl NAME_OR_0xHASH [--sections T:ID[:N],..] [--words N]
        one DRM: every section with its state; with --sections the word-level difference count (by position and
        aligned with difflib), the first differing offsets and idref offsets of those sections (re-read from the
        archives named in the caches; :N = the N-th extra copy of an id that occurs several times); --words N
        prints the first N differing words (A / B values, console only - not for the docs)
  ../bin/pyt -t 600 tools/proto_dlc_compare.py extract CACHE.pkl NAME_OR_0xHASH OUT.drm
        the decoded (big-endian) DRM of a record, e.g. for tools/statevm_check.py / fxnode_id_fix.py (--be modes)
  ../bin/pyt -t 600 tools/proto_dlc_compare.py find A.pkl B.pkl TYPE:ID[,TYPE:ID..]
        in which DRMs of each archive the sections live and whether their content is equal across A and B
  ../bin/pyt -t 300 tools/proto_dlc_compare.py spa A.spa.bin B.spa.bin
        XDBF: entries, title id, achievements (id, gamerscore, label), string tables per language, differences
  ../bin/pyt -t 300 tools/proto_dlc_compare.py md5 FILE [FILE ..]      size + md5 of whole files
  ../bin/pyt -t 900 tools/proto_dlc_compare.py show A.pkl [B.pkl ..] [--grep TEXT]
        records of the caches with names (resolved over all given caches), sections by kind, list-file entries
  ../bin/pyt -t 300 tools/proto_dlc_compare.py locals A.pkl B.pkl SPEC_HEX
        locals.bin strings of one language that differ (console only)
"""
import sys, os, re, json, pickle, hashlib, struct, collections, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from drm import cdrm_decode, sections_with_data, parse_drm
from names import load, L
import drm_reloc as R

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SEC_KIND = {0: 'generic', 1: 'empty', 2: 'animation', 3: 'pushbuffer_wc', 4: 'pushbuffer', 5: 'texture', 6: 'wave',
            7: 'dtp', 8: 'script', 9: 'shaderlib', 10: 'material', 11: 'object', 12: 'mesh', 13: 'collision',
            14: 'streamgroups'}
REV8 = bytes(int('{:08b}'.format(i)[::-1], 2) for i in range(256))


def rev32(v): return int('{:032b}'.format(v)[::-1], 2)


def fcrc(s): return rev32(zlib.crc32(s.lower().encode('latin1').translate(REV8)))


def md5(b): return hashlib.md5(b).hexdigest()


def kind(b):
    if b[:4] == b'CDRM' or b[:4] == b'\0\0\0\x13': return 'drm'
    if b[:4] in (b'FSB4', b'FSB3'): return 'fsb'
    return b[:4].hex()


# ---------------------------------------------------------------- index
def index(path, out):
    A = Archive(path, 'be')
    recs = []
    strings = set()
    for n, r in enumerate(A.idx):
        try: b = A.read(r)
        except Exception as ex:
            recs.append(dict(hash=r['hash'], spec=r['spec'], size=r['size'], error=str(ex))); continue
        k = kind(b)
        rec = dict(hash=r['hash'], spec=r['spec'], size=len(b), kind=k)
        if k == 'drm':
            try: raw = cdrm_decode(b, 'be')
            except Exception as ex:      # damaged CDRM block: keep the record with the md5 of the stored bytes
                rec['md5'] = md5(b); rec['error'] = 'cdrm decode: %s' % ex; recs.append(rec)
                print('record %d hash %08x: %s' % (n, r['hash'], rec['error']), flush=True); continue
            rec['md5'] = md5(raw); rec['raw_size'] = len(raw)
            try:
                h, secs = sections_with_data(raw, 'be')
                nsec = len(secs)
                nm = raw[24 + 20 * nsec:24 + 20 * nsec + h['namesz']]
                rec['deps'] = [x.decode('latin1') for x in nm.split(b'\0') if x]
                rec['sections'] = [(s['type'], s['id'], s['ver'], s['flags'], s['spec'], s['size'], md5(s['data']),
                                    md5(s['reloc']), s['data'][:4].hex()) for s in secs]
                for s in secs:
                    if s['type'] not in (0, 2, 7, 8, 11, 13): continue
                    for m in re.findall(rb'[A-Za-z0-9_\\/\.\-]{3,80}', s['data']):
                        m = m.decode('latin1').lower()
                        if re.search('[a-z]{2}', m): strings.add(m)
            except Exception as ex:
                rec['error'] = 'drm parse: %s' % ex
        else:
            rec['md5'] = md5(b)
            if len(b) <= 300000 and k != 'fsb': rec['data'] = b
        recs.append(rec)
        if n % 50 == 0: print('%d / %d' % (n, len(A.idx)), flush=True)
    pickle.dump(dict(path=os.path.abspath(path), records=recs, strings=sorted(strings)), open(out, 'wb'))
    print('indexed %d records, %d strings -> %s' % (len(recs), len(strings), out))


# ---------------------------------------------------------------- names
def name_map(caches, paths=None):
    """hash -> name; with `paths` (the cache files) the result is kept in names_<md5>.json beside the first cache"""
    if paths:
        cf = os.path.join(os.path.dirname(os.path.abspath(paths[0])),
                          'names_%s.json' % md5('|'.join(sorted(os.path.abspath(p) for p in paths)).encode())[:12])
        if os.path.exists(cf): return {int(k): v for k, v in json.load(open(cf)).items()}
        m = name_map(caches)
        hs = {r['hash'] for c in caches for r in c['records']}
        m = {k: v for k, v in m.items() if k in hs}
        json.dump({str(k): v for k, v in m.items()}, open(cf, 'w'), indent=0)
        return m
    known = dict(load(os.path.join(ROOT, L, 'Tomb Raider Underworld (Xenon).txt')))
    p = os.path.join(ROOT, 'work', 'generic', 'dlc_names.txt')
    if os.path.exists(p):
        for l in open(p, encoding='latin-1'):
            f = l.split()
            if len(f) >= 6 and f[5] != '?': known[int(f[0], 16)] = f[5]
    unk = {r['hash'] for c in caches for r in c['records']} - set(known)
    if not unk: return known
    xn = list(load(os.path.join(ROOT, L, 'Tomb Raider Underworld (Xenon).txt')).values())
    stems = set(); listnames = set()
    for c in caches:
        for s in c['strings']:
            s = s.replace('/', '\\').strip('\\.')
            base = s.split('\\')[-1]
            stems.update((s, base, base.rsplit('.', 1)[0]))
        for r in c['records']:
            listnames.update(d.lower() for d in r.get('deps', []))
            for e in (list_lines(r) or []) if r.get('data', b'')[:1].isdigit() else []:   # object / unit lists
                listnames.add(e.split('\\')[-1].lower())
    stems |= listnames
    for n in xn: stems.add(n.split('\\')[-1].rsplit('.', 1)[0].lower())
    stems = [s for s in stems if 2 < len(s) < 90]
    dirs = collections.Counter()
    for n in xn:
        d, _, f = n.lower().rpartition('\\'); e = f.rsplit('.', 1)[-1] if '.' in f else ''
        dirs[d, e] += 1
    tmpl = list(dirs)
    for u in [s for s in stems if s.startswith('dlc')]:
        for e in ('mus', 'sam', 'mul'): tmpl.append(('xenon-w\\music\\' + u, e))
    unk_r = {rev32(h): h for h in unk}
    found = {}
    for d, e in tmpl:
        st0 = zlib.crc32(((d + '\\') if d else '').encode('latin1').translate(REV8))
        suf = ('.' + e) if e else ''
        sufb = suf.encode('latin1').translate(REV8)
        for s in stems:
            if suf and s.endswith(suf): s = s[:-len(suf)]
            v = zlib.crc32(sufb, zlib.crc32(s.encode('latin1').translate(REV8), st0))
            h = unk_r.get(v)
            if h is not None and h not in found: found[h] = (d + '\\' if d else '') + s + suf
    # composed names: <unit>_map, streamgroups <unit>_<group>; units = DLC names of the list files, groups = the
    # last one / two '_' parts of the Xbox streamgroup names
    units = {s for s in listnames if s.startswith('dlc')}
    groups = {'map'}
    for n in xn:
        n = n.lower()
        if '\\streamgroups\\' in n:
            p = n.rsplit('\\', 1)[1].rsplit('.', 1)[0].split('_')
            groups.update(('_'.join(p[-1:]), '_'.join(p[-2:])))
    for u in units:
        for s in groups:
            for full in ('xenon-w\\streamgroups\\%s_%s.drm' % (u, s), 'xenon-w\\%s_%s.drm' % (u, s)):
                h = fcrc(full)
                if h in unk and h not in found: found[h] = full
    known.update(found)
    return known


def nm(names, h): return names.get(h, '0x%08x' % h)


# ---------------------------------------------------------------- compare
def keyed(secs, tid=lambda s: (s[0], s[1])):
    """{(type, id) or (type, id, n): section}; an id that occurs several times in one DRM (e.g. DTP 22267 x3) gets
    the occurrence number n >= 1 from its second copy on (copies paired in order)"""
    out = {}; seen = collections.Counter()
    for s in secs:
        k = tid(s); n = seen[k]; seen[k] += 1
        out[k if n == 0 else k + (n,)] = s
    return out


def skey(k): return '%d:%d' % k[:2] + ('#%d' % k[2] if len(k) > 2 else '')


def sec_compare(sa, sb):
    """sections of one DRM (lists of tuples) -> dict of states. 'same' = equal data + relocations (content);
    'hdr_only' = equal content, only the section-info fields differ (ver / flags / spec), listed apart"""
    A = keyed(sa); B = keyed(sb)
    res = dict(same=[], changed=[], only_a=[], only_b=[], renumbered=[], hdr_only=[])
    for k in A:
        if k not in B: continue
        a, b = A[k], B[k]
        if a[6] == b[6] and a[7] == b[7]:
            res['same'].append(k)
            if a[2:5] != b[2:5]:
                res['hdr_only'].append((k, ','.join(n for n, x, y in zip(('ver', 'flags', 'spec'), a[2:5], b[2:5])
                                                     if x != y)))
        else:
            what = []
            if a[6] != b[6]: what.append('data')
            if a[7] != b[7]: what.append('reloc')
            res['changed'].append((k, a[5], b[5], '+'.join(what), a[8]))
    oa = [k for k in A if k not in B]; ob = [k for k in B if k not in A]
    bmd = collections.defaultdict(list)
    for k in ob: bmd[B[k][0], B[k][6]].append(k)
    used = set()
    for k in oa:
        c = [x for x in bmd.get((A[k][0], A[k][6]), []) if x not in used]
        if c: res['renumbered'].append((k, c[0])); used.add(c[0])
        else: res['only_a'].append((k, A[k][5], A[k][8]))
    ren_a = {x[0] for x in res['renumbered']}
    res['only_b'] = [(k, B[k][5], B[k][8]) for k in ob if k not in used]
    return res


def list_lines(rec):
    if not rec or 'data' not in rec: return None
    out = []
    for line in rec['data'].decode('latin-1').splitlines()[1:]:     # first line = count
        line = line.strip()
        if ',' in line: out.append(line.split(',', 1)[1].strip())   # objectlist: "id,name"
        elif line: out.append(line)                                 # unitlist: "name"
    return out


def locals_parse(b):
    lang, n = struct.unpack_from('>II', b, 0)
    offs = struct.unpack_from('>%dI' % n, b, 8)
    return lang, [b[o:b.index(b'\0', o)] for o in offs]


def compare(pa, pb, prefix, labels):
    ca, cb = pickle.load(open(pa, 'rb')), pickle.load(open(pb, 'rb'))
    names = name_map([ca, cb], [pa, pb])
    la, lb = labels
    A = {(r['hash'], r['spec']): r for r in ca['records']}
    B = {(r['hash'], r['spec']): r for r in cb['records']}
    out = []; P = out.append
    J = dict(a=ca['path'], b=cb['path'], labels=labels, records={}, drms={})
    P('A (%s): %s  records %d' % (la, ca['path'], len(A)))
    P('B (%s): %s  records %d' % (lb, cb['path'], len(B)))
    unnamed = sorted({nm(names, h) for (h, s) in list(A) + list(B) if h not in names})
    P('names resolved: %d of %d hashes; unresolved: %s' % (len({h for h, s in list(A) + list(B)} - {int(x, 16) for x in unnamed}),
                                                          len({h for h, s in list(A) + list(B)}), ' '.join(unnamed)))
    st = collections.defaultdict(list)
    for k in sorted(set(A) | set(B), key=lambda k: nm(names, k[0])):
        a, b = A.get(k), B.get(k)
        if a and b: s = 'same' if a.get('md5') == b.get('md5') else 'changed'
        else: s = 'only_' + ('a' if a else 'b')
        st[s].append(k)
        J['records']['%s|%08x' % (nm(names, k[0]), k[1])] = dict(state=s, kind=(a or b).get('kind'),
                                                                  size_a=a and a['size'], size_b=b and b['size'])
    P('\n== record level: same %d, changed %d, only in %s %d, only in %s %d' % (
        len(st['same']), len(st['changed']), la, len(st['only_a']), lb, len(st['only_b'])))
    for s, lab in (('only_a', 'only in ' + la), ('only_b', 'only in ' + lb), ('changed', 'changed')):
        P('\n-- %s (%d)' % (lab, len(st[s])))
        for k in st[s]:
            a, b = A.get(k), B.get(k)
            P('  %-60s spec %08x kind %-8s size %s / %s' % (nm(names, k[0]), k[1], (a or b).get('kind'),
                                                            a and a['size'], b and b['size']))
    # section level
    tot = collections.defaultdict(collections.Counter)
    dtp_fmt = collections.Counter(); hdr_drms = []
    P('\n== section level of changed DRMs (by type:id; renumbered = same content under another id)')
    for k in st['changed']:
        a, b = A[k], B[k]
        if a.get('kind') != 'drm' or 'sections' not in a or 'sections' not in b: continue
        r = sec_compare(a['sections'], b['sections'])
        name = nm(names, k[0])
        J['drms'][name] = {x: [list(map(str, y)) if isinstance(y, tuple) else y for y in v] for x, v in r.items()}
        P('\n%s: sections %d / %d; same content %d (of them section-info only %d %s), changed %d, renumbered %d, '
          'only %s %d, only %s %d; deps %s' % (
            name, len(a['sections']), len(b['sections']), len(r['same']), len(r['hdr_only']),
            dict(collections.Counter(x[1] for x in r['hdr_only'])), len(r['changed']), len(r['renumbered']),
            la, len(r['only_a']), lb, len(r['only_b']),
            'same' if a.get('deps') == b.get('deps') else '%s -> %s' % (a.get('deps'), b.get('deps'))))
        if not (r['changed'] or r['only_a'] or r['only_b'] or r['renumbered']): hdr_drms.append(name)
        K = lambda k: SEC_KIND.get(k[0], k[0])
        for k in r['same']: tot[K(k)]['same'] += 1
        for k, _ in r['renumbered']: tot[K(k)]['renumbered'] += 1
        per = collections.Counter()
        for k, sa, sb, what, fmt in r['changed']:
            tot[K(k)]['changed'] += 1; per[K(k)] += 1
            if k[0] == 7: dtp_fmt[fmt] += 1
        for k, sz, fmt in r['only_a']: tot[K(k)]['only_' + la] += 1
        for k, sz, fmt in r['only_b']: tot[K(k)]['only_' + lb] += 1
        if per: P('   changed by kind: %s' % dict(per))
        F = lambda k, fmt: (' fmt ' + fmt) if k[0] == 7 else ''
        for k, sa, sb, what, fmt in r['changed'][:400]:
            P('   changed %-12s %-14s size %8d / %-8d %s%s' % (K(k), skey(k), sa, sb, what, F(k, fmt)))
        for k, sz, fmt in r['only_a'][:200]:
            P('   only %s %-12s %-14s size %8d%s' % (la, K(k), skey(k), sz, F(k, fmt)))
        for k, sz, fmt in r['only_b'][:200]:
            P('   only %s %-12s %-14s size %8d%s' % (lb, K(k), skey(k), sz, F(k, fmt)))
    P('\n== changed DRMs whose sections all have the same content (only section-info fields differ): %d %s' % (
        len(hdr_drms), ' '.join(hdr_drms)))
    J['hdr_only_drms'] = hdr_drms
    P('\n== totals over changed DRMs by section kind')
    for kd, c in sorted(tot.items(), key=lambda x: str(x[0])): P('  %-14s %s' % (kd, dict(c)))
    P('  changed DTPs by format word: %s' % dict(dtp_fmt.most_common()))
    J['totals'] = {str(k): dict(v) for k, v in tot.items()}
    # unique sections over the whole archive (a shared section counts once): (type, id) -> set of content md5s
    def uniq(c):
        d = collections.defaultdict(set); f = {}
        for r in c['records']:
            for s in r.get('sections', []):
                d[s[0], s[1]].add(s[6] + s[7]); f[s[0], s[1]] = s[8]
        return d, f
    (UA, FA), (UB, FB) = uniq(ca), uniq(cb)
    allb = collections.defaultdict(set)
    for k, v in UB.items():
        for m in v: allb[k[0], m].add(k[1])
    ut = collections.defaultdict(collections.Counter); ufmt = collections.Counter(); uchg = collections.defaultdict(list)
    for k in set(UA) | set(UB):
        K = SEC_KIND.get(k[0], k[0])
        if k in UA and k in UB:
            if UA[k] == UB[k]: ut[K]['same'] += 1
            else:
                ut[K]['changed'] += 1; uchg[K].append(k[1])
                if k[0] == 7: ufmt[FA[k]] += 1
        elif k in UA:
            if any(allb.get((k[0], m)) for m in UA[k]): ut[K]['renumbered'] += 1
            else: ut[K]['only_' + la] += 1
        else: ut[K]['only_' + lb] += 1
    P('\n== unique sections over the whole archive by (type, id) (a section shared by several DRMs counts once)')
    for kd, c in sorted(ut.items(), key=lambda x: str(x[0])): P('  %-14s %s' % (kd, dict(c)))
    P('  changed DTPs by format word: %s' % dict(ufmt.most_common()))
    J['unique_sections'] = {str(k): dict(v) for k, v in ut.items()}
    J['unique_changed_ids'] = {str(k): sorted(v) for k, v in uchg.items()}
    dupa = collections.Counter((r['hash'], r['spec']) for r in ca['records'])
    dupb = collections.Counter((r['hash'], r['spec']) for r in cb['records'])
    P('duplicate (hash, spec) records (the last in index order is compared): %s %d %s; %s %d %s' % (
        la, sum(v - 1 for v in dupa.values()), sorted(nm(names, k[0]) for k, v in dupa.items() if v > 1),
        lb, sum(v - 1 for v in dupb.values()), sorted(nm(names, k[0]) for k, v in dupb.items() if v > 1)))
    # lists
    for lname in ('\\tr8\\xenon-w\\objectlist.txt', '\\tr8\\xenon-w\\unitlist.txt'):
        h = fcrc(lname)
        ra = next((r for r in ca['records'] if r['hash'] == h), None)
        rb = next((r for r in cb['records'] if r['hash'] == h), None)
        xa, xb = list_lines(ra), list_lines(rb)
        if xa is None or xb is None: P('\n%s: %s %s, %s %s' % (lname, la, 'present' if ra else 'absent', lb, 'present' if rb else 'absent')); continue
        sa_, sb_ = set(xa), set(xb)
        P('\n== %s: %d / %d entries; only in %s %d: %s; only in %s %d: %s' % (
            lname, len(xa), len(xb), la, len(sa_ - sb_), ' '.join(sorted(sa_ - sb_)), lb, len(sb_ - sa_),
            ' '.join(sorted(sb_ - sa_))))
        J['list ' + lname] = dict(a=len(xa), b=len(xb), only_a=sorted(sa_ - sb_), only_b=sorted(sb_ - sa_))
    h = fcrc('xenon-w\\local\\locals.bin')
    for spec in sorted({r['spec'] for r in ca['records'] + cb['records'] if r['hash'] == h}):
        ra = A.get((h, spec)); rb = B.get((h, spec))
        if not (ra and rb and 'data' in ra and 'data' in rb): continue
        (lga, sa_), (lgb, sb_) = locals_parse(ra['data']), locals_parse(rb['data'])
        diff = sum(1 for i in range(min(len(sa_), len(sb_))) if sa_[i] != sb_[i])
        P('locals.bin spec %08x lang %d: strings %d / %d, differing at common indices %d' % (spec, lga, len(sa_), len(sb_), diff))
    open(prefix + '.txt', 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    json.dump(J, open(prefix + '.json', 'w', encoding='utf-8'), indent=1)
    print('\n'.join(out[:3]))
    print('record level: same %d, changed %d, only %s %d, only %s %d' % (len(st['same']), len(st['changed']), la,
          len(st['only_a']), lb, len(st['only_b'])))
    print('wrote %s.txt / .json' % prefix)


# ---------------------------------------------------------------- one DRM
def find_rec(c, names, key):
    if key.startswith('0x'): h = int(key, 16)
    else:
        h = None
        for hh, n in names.items():
            if n.lower().split('\\')[-1] in (key.lower(), key.lower() + '.drm'): h = hh; break
    return [r for r in c['records'] if r['hash'] == h], h


def raw_drm(path, h):
    A = Archive(path, 'be')
    r = [x for x in A.idx if x['hash'] == h][-1]
    return cdrm_decode(A.read(r), 'be')


def words_diff(a, b, max_list=12):
    n = min(len(a), len(b)) // 4
    wa = struct.unpack('>%dI' % n, a[:4 * n]); wb = struct.unpack('>%dI' % n, b[:4 * n])
    d = [4 * i for i in range(n) if wa[i] != wb[i]]
    return len(d), d[:max_list]


def drm_cmd(pa, pb, key, secs, words=0):
    ca, cb = pickle.load(open(pa, 'rb')), pickle.load(open(pb, 'rb'))
    names = name_map([ca, cb], [pa, pb])
    ra, h = find_rec(ca, names, key); rb, _ = find_rec(cb, names, key)
    print('%s hash %s: A %s, B %s' % (key, h and '0x%08x' % h, 'present' if ra else 'absent', 'present' if rb else 'absent'))
    if not (ra and rb): return
    a, b = ra[-1], rb[-1]
    print('md5 A %s B %s, raw size %s / %s, deps %s / %s' % (a['md5'], b['md5'], a.get('raw_size'), b.get('raw_size'),
                                                            a.get('deps'), b.get('deps')))
    r = sec_compare(a['sections'], b['sections'])
    print('sections %d / %d: same %d changed %d renumbered %d only A %d only B %d' % (
        len(a['sections']), len(b['sections']), len(r['same']), len(r['changed']), len(r['renumbered']),
        len(r['only_a']), len(r['only_b'])))
    by = collections.defaultdict(collections.Counter)
    for k in r['same']: by[SEC_KIND.get(k[0], k[0])]['same'] += 1
    for x in r['changed']: by[SEC_KIND.get(x[0][0], x[0][0])]['changed'] += 1
    for x in r['renumbered']: by[SEC_KIND.get(x[0][0], x[0][0])]['renumbered'] += 1
    for x in r['only_a']: by[SEC_KIND.get(x[0][0], x[0][0])]['only_A'] += 1
    for x in r['only_b']: by[SEC_KIND.get(x[0][0], x[0][0])]['only_B'] += 1
    for kd, c in sorted(by.items(), key=lambda x: str(x[0])): print('  %-12s %s' % (kd, dict(c)))
    for x in r['changed']: print('  changed %-14s size %d / %d %s fmt %s' % (skey(x[0]), x[1], x[2], x[3], x[4]))
    for x in r['renumbered']: print('  renumbered %s -> %s' % (skey(x[0]), skey(x[1])))
    for x in r['only_a']: print('  only A %-14s size %d fmt %s' % (skey(x[0]), x[1], x[2]))
    for x in r['only_b']: print('  only B %-14s size %d fmt %s' % (skey(x[0]), x[1], x[2]))
    if not secs: return
    _, SA = sections_with_data(raw_drm(ca['path'], h), 'be')
    _, SB = sections_with_data(raw_drm(cb['path'], h), 'be')
    tid = lambda s: (s['type'], s['id'])
    da = keyed(SA, tid); db = keyed(SB, tid)
    for k in secs:
        sa, sb = da.get(k), db.get(k)
        if not (sa and sb): print('  %s: A %s B %s' % (skey(k), bool(sa), bool(sb))); continue
        n, offs = words_diff(sa['data'], sb['data'])
        ia = R.parse(sa['reloc'], 'be'); ib = R.parse(sb['reloc'], 'be')
        print('  %s size %d / %d, data words differing by position %d (first offsets %s), reloc %s '
              '(internal %d/%d external %d/%d idref %d/%d); idrefs A %s; idrefs B %s' % (
                  skey(k), sa['size'], sb['size'], n, ' '.join(hex(o) for o in offs),
                  'same' if sa['reloc'] == sb['reloc'] else 'DIFFERENT', len(ia.internal), len(ib.internal),
                  len(ia.external), len(ib.external), len(ia.idref), len(ib.idref),
                  idrefs(sa, ia), idrefs(sb, ib)))
        if n:
            print('    aligned (difflib over u32 words): %s' % aligned(sa['data'], sb['data']))
            ida = {o: t for t, o in ia.idref + ia.idref_a}; idb = {o: t for t, o in ib.idref + ib.idref_a}
            if ida != idb:
                print('    idref offsets only A %s, only B %s' % (
                    ' '.join('%x(t%d)' % (o, t) for o, t in sorted(ida.items()) if idb.get(o) != t),
                    ' '.join('%x(t%d)' % (o, t) for o, t in sorted(idb.items()) if ida.get(o) != t)))
        if words and n:
            _, alloffs = words_diff(sa['data'], sb['data'], words)
            for o in alloffs:
                print('    +0x%-6x A %08x B %08x' % (o, struct.unpack_from('>I', sa['data'], o)[0],
                                                     struct.unpack_from('>I', sb['data'], o)[0]))


def aligned(a, b):
    """difflib opcodes over the u32 word sequences -> counts (equal / replaced / deleted in A / inserted in B words).
    Sections over 20 000 words use difflib's autojunk heuristic (frequent words such as 0 are not used as anchors;
    without it the 133 000-word state chart took > 25 min) - the counts are then marked 'approx'."""
    import difflib
    wa = struct.unpack('>%dI' % (len(a) // 4), a[:len(a) // 4 * 4])
    wb = struct.unpack('>%dI' % (len(b) // 4), b[:len(b) // 4 * 4])
    big = max(len(wa), len(wb)) > 20000
    sm = difflib.SequenceMatcher(None, wa, wb, autojunk=big)
    c = collections.Counter(); first = ['approx (autojunk)'] if big else []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        c[op] += max(i2 - i1, j2 - j1)
        if op != 'equal' and len(first) < 8: first.append('%s A+0x%x..0x%x B+0x%x..0x%x' % (op, 4 * i1, 4 * i2, 4 * j1, 4 * j2))
    return '%s; first %s' % (dict(c), '; '.join(first))


def extract_cmd(pc, key, out):
    """decoded DRM (raw, big endian) of one record of a cache's archive -> OUT (for the existing --be tools)"""
    c = pickle.load(open(pc, 'rb'))
    names = name_map([c], [pc])
    recs, h = find_rec(c, names, key)
    if not recs: raise SystemExit('%s not in %s' % (key, c['path']))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    raw = raw_drm(c['path'], h)
    open(out, 'wb').write(raw)
    print('%s (0x%08x) -> %s, %d bytes, md5 %s' % (key, h, out, len(raw), md5(raw)))


def idrefs(s, rl):
    out = collections.defaultdict(list)
    for t, off in rl.idref + rl.idref_a:
        if off + 4 <= len(s['data']): out[t].append(struct.unpack_from('>I', s['data'], off)[0])
    return {SEC_KIND.get(t, t): sorted(set(v)) for t, v in out.items()}


CHART_HDR = struct.pack('>4I', 10000, 12000, 4000, 6000)


def transitions(s):
    """state-chart transitions of a big-endian DTP (same rule as tools/chart_transitions.py, which reads PC files):
    20-byte blocks between internal pointer targets whose +8 and +0xc are pointers; {u16 target, u16, u16 count,
    u16, ptr conditions, ptr, u32}; conditions = count records {u16 key, u16 id, u16 value, u8 flags, u8}"""
    import bisect
    d = s['data']; it = dict(R.parse(s['reloc'], 'be').internal)
    t = sorted(set(it.values()) | {0})
    out = []
    for k, a in enumerate(t):
        end = t[k + 1] if k + 1 < len(t) else len(d)
        if end - a != 0x14 or (a + 8) not in it or (a + 0xc) not in it: continue
        target, w1, cnt, w3 = struct.unpack_from('>4H', d, a)
        c0 = it[a + 8]; conds = []
        for j in range(min(cnt, 16)):
            if c0 + 8 * j + 8 > len(d): break
            ky, i, v = struct.unpack_from('>3H', d, c0 + 8 * j)
            conds.append((ky, i, v, d[c0 + 8 * j + 6] & 1))
        out.append((a, target, w1, cnt, w3, tuple(conds)))
    return out


def chart_cmd(pa, pb, key, sid, vals):
    """transitions of one state chart in A and B; multiset difference by (target, conditions); --value V: the
    transitions with a markup record {610..613, *, V} (rock vein: 607 / 608)"""
    ca, cb = pickle.load(open(pa, 'rb')), pickle.load(open(pb, 'rb'))
    names = name_map([ca, cb], [pa, pb])
    res = {}
    for lab, c in (('A', ca), ('B', cb)):
        recs, h = find_rec(c, names, key)
        S = [s for s in sections_with_data(raw_drm(c['path'], h), 'be')[1] if s['type'] == 7 and s['id'] == sid]
        if not S: print('%s: DTP %d not found' % (lab, sid)); return
        s = S[0]
        tr = transitions(s)
        res[lab] = tr
        print('%s: DTP %d %d bytes, chart header %s, %d transitions' % (lab, sid, s['size'],
              'yes' if s['data'][0xc:0x1c] == CHART_HDR else 'no', len(tr)))
        if vals:
            m = [x for x in tr if any(c[2] in vals and c[1] in (610, 611, 612, 613) for c in x[5])]
            print('   transitions with markup value %s: %d' % (sorted(vals), len(m)))
            for a, tg, w1, cnt, w3, conds in m:
                print('     +0x%05x -> state %5d (%d, count %d, %d) %s' % (a, tg, w1, cnt, w3, ' '.join(
                    '{%d,%d,%d%s}' % (c[0], c[1], c[2], ',NOT' if c[3] else '') for c in conds)))
    ka = collections.Counter((x[1], x[2], x[3], x[4], x[5]) for x in res['A'])
    kb = collections.Counter((x[1], x[2], x[3], x[4], x[5]) for x in res['B'])
    oa, ob = ka - kb, kb - ka
    print('transitions equal by (target, words, conditions): %d; only A %d, only B %d' % (
        sum((ka & kb).values()), sum(oa.values()), sum(ob.values())))
    for lab, o in (('A', oa), ('B', ob)):
        for (tg, w1, cnt, w3, conds), n in sorted(o.items())[:60]:
            print('   only %s x%d -> state %5d (%d, count %d, %d) %s' % (lab, n, tg, w1, cnt, w3, ' '.join(
                '{%d,%d,%d%s}' % (c[0], c[1], c[2], ',NOT' if c[3] else '') for c in conds)))
    sa = collections.Counter(x[1] for x in res['A']); sb = collections.Counter(x[1] for x in res['B'])
    print('target states only in A: %s' % sorted(set(sa) - set(sb)))
    print('target states only in B: %s' % sorted(set(sb) - set(sa)))


def find_cmd(pa, pb, keys):
    ca, cb = pickle.load(open(pa, 'rb')), pickle.load(open(pb, 'rb'))
    names = name_map([ca, cb], [pa, pb])
    for k in keys:
        for lab, c in (('A', ca), ('B', cb)):
            hits = []
            for r in c['records']:
                for s in r.get('sections', []):
                    if (s[0], s[1]) == k: hits.append((nm(names, r['hash']), s[5], s[6][:8], s[7][:8]))
            print('%d:%d in %s: %s' % (k[0], k[1], lab, hits or 'none'))


# ---------------------------------------------------------------- spa.bin (XDBF)
def xdbf(b):
    mg, ver, etl, ec, ftl, fc = struct.unpack_from('>4sIIIII', b, 0)
    if mg != b'XDBF': raise SystemExit('not XDBF')
    base = 0x18 + etl * 18 + ftl * 8
    ents = []
    for i in range(ec):
        ns, eid, off, ln = struct.unpack_from('>HQII', b, 0x18 + 18 * i)
        ents.append((ns, eid, b[base + off:base + off + ln]))
    return ents


def spa_info(path):
    b = open(path, 'rb').read()
    E = xdbf(b)
    info = dict(size=len(b), entries=collections.Counter(e[0] for e in E), strings={}, ach=[], images=0)
    for ns, eid, d in E:
        if ns == 3 and d[:4] == b'XSTR':
            n = struct.unpack_from('>H', d, 12)[0]; p = 14; t = {}
            for _ in range(n):
                sid, ln = struct.unpack_from('>HH', d, p); t[sid] = d[p + 4:p + 4 + ln].decode('utf-8', 'replace'); p += 4 + ln
            info['strings'][eid] = t
        elif ns == 1 and d[:4] == b'XACH':
            n = struct.unpack_from('>H', d, 12)[0]
            for i in range(n):
                aid, lab, desc, unach, img, gs = struct.unpack_from('>HHHHIH', d, 14 + 0x24 * i)
                info['ach'].append((aid, lab, desc, unach, img, gs))
        elif ns == 1 and d[:4] == b'XTHD':
            info['title_id'] = '%08X' % struct.unpack_from('>I', d, 12)[0]
        elif ns == 2: info['images'] += 1
    return info


def spa_cmd(pa, pb):
    A, B = spa_info(pa), spa_info(pb)
    for lab, I in (('A', A), ('B', B)):
        en = I['strings'].get(1, {})
        print('%s: %d bytes, entries by namespace %s, title id %s, images %d, languages %s, strings (en) %d, '
              'achievements %d, gamerscore %d' % (lab, I['size'], dict(I['entries']), I.get('title_id'), I['images'],
              sorted(I['strings']), len(en), len(I['ach']), sum(a[5] for a in I['ach'])))
    ea, eb = A['strings'].get(1, {}), B['strings'].get(1, {})
    print('achievements (id, gamerscore, label en) A:')
    for a in A['ach']: print('   %3d %3d %s' % (a[0], a[5], ea.get(a[1], '?')))
    print('achievements B:')
    for a in B['ach']: print('   %3d %3d %s' % (a[0], a[5], eb.get(a[1], '?')))
    for lang in sorted(set(A['strings']) | set(B['strings'])):
        sa, sb = A['strings'].get(lang, {}), B['strings'].get(lang, {})
        ch = [i for i in sa if i in sb and sa[i] != sb[i]]
        print('lang %d: strings %d / %d, only A %s, only B %s, changed %d %s' % (
            lang, len(sa), len(sb), sorted(set(sa) - set(sb)), sorted(set(sb) - set(sa)), len(ch), ch[:20]))
        if lang == 1:
            for i in ch: print('    en %d: %r -> %r' % (i, sa[i], sb[i]))
            for i in sorted(set(sa) - set(sb)): print('    en only A %d: %r' % (i, sa[i]))
            for i in sorted(set(sb) - set(sa)): print('    en only B %d: %r' % (i, sb[i]))


def locals_cmd(pa, pb, spec):
    """locals.bin of one language (spec mask) in A and B: indices whose text differs or exists on one side only
    (console only)"""
    out = []
    for p in (pa, pb):
        c = pickle.load(open(p, 'rb'))
        r = [x for x in c['records'] if x['hash'] == fcrc('xenon-w\\local\\locals.bin') and x['spec'] == spec]
        out.append(locals_parse(r[-1]['data'])[1] if r else [])
    a, b = out
    print('strings %d / %d' % (len(a), len(b)))
    sa, sb = set(a), set(b)
    print('texts only in A (any index): %d' % len(sa - sb))
    for s in sorted(sa - sb): print('   A only %r' % s[:200])
    print('texts only in B (any index): %d' % len(sb - sa))
    for s in sorted(sb - sa): print('   B only %r' % s[:200])
    print('-- by index:')
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else None; y = b[i] if i < len(b) else None
        if x != y: print('%5d A %r\n      B %r' % (i, x and x[:160], y and y[:160]))


def show_cmd(paths, grep=None):
    """records of one or more caches with names; per DRM sections by kind and dependencies; list-file entries;
    --grep TEXT: only the raw list-file lines (with object ids) that contain TEXT"""
    cs = [pickle.load(open(p, 'rb')) for p in paths]
    names = name_map(cs, paths)
    for p, c in zip(paths, cs):
        print('== %s (%s): %d records' % (p, c['path'], len(c['records'])))
        if grep:
            for r in c['records']:
                if r.get('data', b'')[:1].isdigit():
                    for line in r['data'].decode('latin-1').splitlines():
                        if grep in line: print('  %s: %s' % (nm(names, r['hash']), line.strip()))
            continue
        for r in sorted(c['records'], key=lambda r: nm(names, r['hash'])):
            extra = ''
            if 'sections' in r:
                k = collections.Counter(SEC_KIND.get(s[0], s[0]) for s in r['sections'])
                extra = ' sections %d %s deps %s' % (len(r['sections']), dict(k), r.get('deps'))
            if r.get('error'): extra += ' ERROR ' + r['error']
            print('  %-58s spec %08x %-8s %10d md5 %s%s' % (nm(names, r['hash']), r['spec'], r.get('kind'), r['size'],
                                                            r.get('md5', '')[:12], extra))
            ll = list_lines(r) if r.get('data', b'')[:1].isdigit() else None
            if ll: print('      list entries %d: %s' % (len(ll), ' '.join(ll)))
            if nm(names, r['hash']).endswith('locals.bin') and 'data' in r:
                lg, st = locals_parse(r['data']); print('      locals.bin lang %d strings %d' % (lg, len(st)))


def main(argv):
    if len(argv) < 2: print(__doc__); return 2
    c = argv[0]
    if c == 'index': return index(argv[1], argv[2])
    if c == 'show':
        g = argv[argv.index('--grep') + 1] if '--grep' in argv else None
        return show_cmd([a for a in argv[1:] if a not in ('--grep', g)], g)
    if c == 'locals': return locals_cmd(argv[1], argv[2], int(argv[3], 16))
    if c == 'extract': return extract_cmd(argv[1], argv[2], argv[3])
    if c == 'compare':
        labels = argv[argv.index('--labels') + 1].split(',') if '--labels' in argv else ['A', 'B']
        return compare(argv[1], argv[2], argv[3], labels)
    if c == 'drm':
        secs = []
        if '--sections' in argv:
            secs = [tuple(int(x) for x in s.split(':')) for s in argv[argv.index('--sections') + 1].split(',')]
        words = int(argv[argv.index("--words") + 1]) if "--words" in argv else 0
        return drm_cmd(argv[1], argv[2], argv[3], secs, words)
    if c == 'find': return find_cmd(argv[1], argv[2], [tuple(int(x) for x in s.split(':')) for s in argv[3].split(',')])
    if c == 'spa': return spa_cmd(argv[1], argv[2])
    if c == 'chart':
        vals = {int(x) for x in argv[argv.index('--value') + 1].split(',')} if '--value' in argv else None
        return chart_cmd(argv[1], argv[2], argv[3], int(argv[4]), vals)
    if c == 'md5':
        for p in argv[1:]:
            h = hashlib.md5()
            with open(p, 'rb') as f:
                for blk in iter(lambda: f.read(1 << 22), b''): h.update(blk)
            print('%12d %s %s' % (os.path.getsize(p), h.hexdigest(), p))
        return 0
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]) or 0)
