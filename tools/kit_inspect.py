"""Read-only views of an upstream format-2 release kit (B269 / B270): manifest comparison, format statistics with the
literal share of the patches, name lookups and the patch sites of the exe patch (2026-11-05, docs
Befund-B270-Kit-0511.md). Runs no code of the kit; patches are parsed with tools/kit_rebuild.py (bsdiff4 layout).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/kit_inspect.py compare A.json B.json
        two kit manifests: file lists, every field per file, exe entry
  ../bin/pyt -t 900 tools/kit_inspect.py stats KIT_DIR
        files per dlc / mode / aux / source archive, pc_also, authored files; per patch: new bytes, bytes from the
        EXTRA block (literal, not derived from the user's source), non-zero DIFF bytes; sums per area and extension
  ../bin/pyt -t 300 tools/kit_inspect.py names KIT_DIR NAME|0xHASH [...]
        is a bigfile name (or its hash) a source of the kit, or a target path (rel, by base name)?
  ../bin/pyt -t 900 tools/kit_inspect.py exesites KIT_DIR OUR_EXE [--asi DIR] [--gap N] [--win N] [--out R.tsv]
        the exe patch's changed byte ranges (non-zero DIFF runs, EXTRA runs) as new-file offsets, mapped to sections /
        VAs with the PE header of the patch applied to OUR_EXE (the Steamless output is not needed for the ranges: a
        DIFF byte 0 means new = old at that position); the bytes shown as 'new~' are exact only where OUR_EXE equals
        the Steamless output (not at our B138 patch sites). --asi: plugin source folder (default src/asi); every
        `const DWORD k... = 0x00xxxxxx` and every `tru+0x...` in the plugins' .cpp / README.md (TruGuard excluded) is a
        site; a site within --win bytes (default 16) of a changed range is an overlap
"""
import sys, os, re, json, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import kit_rebuild as K

IMAGE_BASE = 0x400000
SKIP_PLUGINS = ('TruGuard',)          # belongs to a colleague: never read


def load(p): return json.load(open(p, encoding='utf-8'))


def cmd_compare(a, b):
    A, B = load(a), load(b)
    print('A %s format %s, %d files | B %s format %s, %d files' % (A.get('build'), A.get('format'), len(A['files']),
                                                                  B.get('build'), B.get('format'), len(B['files'])))
    fa = {f['rel']: f for f in A['files']}; fb = {f['rel']: f for f in B['files']}
    oa = sorted(set(fa) - set(fb)); ob = sorted(set(fb) - set(fa))
    print('only in A: %d, only in B: %d, in both: %d' % (len(oa), len(ob), len(set(fa) & set(fb))))
    for r in oa[:20]: print('  only A:', r)
    for r in ob[:20]: print('  only B:', r)
    same = 0; diff = collections.Counter(); ex = []
    for r in sorted(set(fa) & set(fb)):
        x, y = fa[r], fb[r]
        if x == y: same += 1; continue
        ks = sorted(k for k in set(x) | set(y) if x.get(k) != y.get(k))
        for k in ks: diff[k] += 1
        ex.append((r, ks))
    print('identical entries (all fields): %d, differing: %d' % (same, len(ex)))
    for k, n in diff.most_common(): print('  field %-10s differs in %d' % (k, n))
    for r, ks in ex[:30]: print('  %s: %s' % (r, ','.join(ks)))
    print('order of files equal: %s' % ([f['rel'] for f in A['files']] == [f['rel'] for f in B['files']]))
    print('exe equal: %s; other top-level keys equal: %s' % (A.get('exe') == B.get('exe'),
          {k: A.get(k) == B.get(k) for k in sorted(set(A) | set(B)) if k not in ('files',)}))
    print('md5 list A == B: %s' % (sorted((f['rel'], f['md5']) for f in A['files']) == sorted((f['rel'], f['md5']) for f in B['files'])))


def area(f):
    r = f['rel'].lower()
    if f['source'] is None: return 'authored'
    if r.endswith('.mul') or r.startswith('audio/') or r.endswith('.mus') or r.endswith('.sam'): return 'audio'
    if r.endswith('.raw'): return 'image'
    if '/' in r and r.split('/')[0] == 'streamgroups': return 'streamgroup'
    if 'costume' in r or 'outfit' in r: return 'costume'
    if r.startswith('cinstream/'): return 'cinstream'
    if r.startswith('local/') or 'locals.bin' in r: return 'text'
    return 'drm'


def cmd_stats(kit):
    man = load(os.path.join(kit, 'manifest.json'))
    files = man['files']
    print('kit %s format %s: %d files, exe %s' % (man.get('build'), man.get('format'), len(files), 'yes' if man.get('exe') else 'no'))
    for key, fn in (('dlc', lambda f: f.get('dlc')), ('mode', lambda f: f['mode']), ('aux', lambda f: ','.join(f['aux']) or '-'),
                    ('source', lambda f: (f['source'] or {}).get('archive', 'authored')),
                    ('source kind', lambda f: (f['source'] or {}).get('kind', 'authored')),
                    ('pc_also', lambda f: (f.get('pc_also') or {}).get('archive', '-')), ('area', area),
                    ('ext', lambda f: os.path.splitext(f['rel'])[1].lower())):
        c = collections.Counter(fn(f) for f in files)
        print('%-12s %s' % (key, ', '.join('%s %d' % kv for kv in sorted(c.items(), key=lambda kv: -kv[1]))))
    refd = set(f['patch'].replace('\\', '/') for f in files) | ({man['exe']['patch']} if man.get('exe') else set())
    have = set('patches/' + n for n in os.listdir(os.path.join(kit, 'patches'))) | set('authored/' + n for n in os.listdir(os.path.join(kit, 'authored')))
    print('patch / authored files in the kit: %d, referenced by the manifest: %d, unreferenced: %s, missing: %s' % (
        len(have), len(refd), sorted(have - refd) or 'none', sorted(refd - have) or 'none'))
    auth = [f for f in files if f['source'] is None]
    for f in auth: print('authored: %s (%d bytes) -> %s' % (f['rel'], f['size'], f['patch']))
    # source / target name differences
    ren = [f for f in files if f['source'] and os.path.basename(f['source']['name'].replace('\\', '/')).lower() != os.path.basename(f['rel']).lower()]
    print('files whose source name differs from the target name: %d' % len(ren))
    for f in ren[:40]: print('  %s <- %s %s' % (f['rel'], f['source']['archive'], f['source']['name']))
    # patches
    tot = collections.defaultdict(lambda: [0, 0, 0, 0, 0])        # n, new, extra, diff_nonzero, patch size
    rows = []
    ents = [f for f in files if f['source'] is not None] + ([dict(man['exe'], dlc='exe', mode='plain', aux=[], source={'archive': 'steamless'})] if man.get('exe') else [])
    for f in ents:
        p = K.parse_patch(open(os.path.join(kit, f['patch']), 'rb').read())
        df = np.frombuffer(p['diff'], dtype=np.uint8); nz = int(np.count_nonzero(df))
        ex = sum(t[1] for t in p['tri'])
        ar = 'exe' if f.get('dlc') == 'exe' else area(f)
        rows.append((f['rel'], f.get('dlc'), ar, p['new'], ex, nz, p['size']))
        for k in ('all', 'dlc:' + str(f.get('dlc')), 'area:' + ar, 'ext:' + (os.path.splitext(f['rel'])[1].lower() or '-')):
            t = tot[k]; t[0] += 1; t[1] += p['new']; t[2] += ex; t[3] += nz; t[4] += p['size']
    print('\nliteral share (new = patched result before recompression; extra = bytes from the patch EXTRA block; '
          'diffnz = non-zero DIFF bytes)')
    print('%-22s %5s %14s %8s %8s %12s' % ('group', 'n', 'new bytes', 'extra%', 'diffnz%', 'patch bytes'))
    for k in sorted(tot, key=lambda k: (k.split(':')[0] != 'all', k.split(':')[0], -tot[k][1])):
        n, nw, ex, nz, ps = tot[k]
        print('%-22s %5d %14d %7.1f%% %7.1f%% %12d' % (k, n, nw, 100.0 * ex / max(1, nw), 100.0 * nz / max(1, nw), ps))
    print('\nmost literal files (extra bytes):')
    for r in sorted(rows, key=lambda r: -r[4])[:25]:
        print('  %6.1f%% %11d of %11d  %-6s %s' % (100.0 * r[4] / max(1, r[3]), r[4], r[3], r[1], r[0]))
    full = [r for r in rows if r[4] >= r[3] * 0.99]
    print('files >= 99%% literal: %d (%s)' % (len(full), ', '.join('%s %d' % kv for kv in collections.Counter(r[2] for r in full).items())))


def cmd_names(kit, names):
    man = load(os.path.join(kit, 'manifest.json'))
    src = collections.defaultdict(list); base = collections.defaultdict(list)
    for f in man['files']:
        if f['source']: src[K.crc(f['source']['name'])].append(f)
        if f.get('pc_also'): src[K.crc(f['pc_also']['name'])].append(f)
        base[os.path.basename(f['rel']).lower()].append(f)
    for n in names:
        if n.lower().startswith('0x'):
            h = int(n, 16); bn = None
        else:
            h = K.crc(n); bn = os.path.basename(n.replace('\\', '/')).lower()
        hit_s = src.get(h, []); hit_b = base.get(bn, []) if bn else []
        print('%s hash 0x%08x: as source %d %s | as target (base name) %d %s' % (
            n, h, len(hit_s), [f['rel'] for f in hit_s], len(hit_b), [f['rel'] for f in hit_b]))


# ------------------------------------------------------------------ exe
def pe_sections(b):
    pe = struct.unpack_from('<I', b, 0x3c)[0]
    nsec = struct.unpack_from('<H', b, pe + 6)[0]; opt = struct.unpack_from('<H', b, pe + 20)[0]
    base = struct.unpack_from('<I', b, pe + 24 + 28)[0]
    out = []
    for i in range(nsec):
        o = pe + 24 + opt + 40 * i
        name = b[o:o + 8].rstrip(b'\0').decode('latin1')
        vsz, va, rsz, raw = struct.unpack_from('<IIII', b, o + 8)
        ch = struct.unpack_from('<I', b, o + 36)[0]
        out.append(dict(name=name, va=va, vsz=vsz, raw=raw, rsz=rsz, ch=ch))
    return base, out


def off2va(secs, base, off):
    for s in secs:
        if s['raw'] <= off < s['raw'] + s['rsz']: return s['name'], base + s['va'] + off - s['raw']
    return 'header' if off < 0x1000 else '?', None


def plugin_sites(asi):
    sites = collections.defaultdict(set)        # va -> {plugin:label}
    for d in sorted(os.listdir(asi)):
        if d in SKIP_PLUGINS or d == 'third_party' or not os.path.isdir(os.path.join(asi, d)): continue
        for fn in sorted(os.listdir(os.path.join(asi, d))):
            if not (fn.endswith('.cpp') or fn.endswith('.h') or fn == 'README.md'): continue
            t = open(os.path.join(asi, d, fn), encoding='utf-8', errors='replace').read()
            for m in re.finditer(r'const\s+(?:DWORD|uintptr_t|uint32_t)\s+(k\w+)\s*=\s*0x0*([4-9a-f][0-9a-f]{5})\b', t, re.I):
                sites[int(m.group(2), 16)].add('%s:%s' % (d, m.group(1)))
            for m in re.finditer(r'tru\+0x([0-9a-f]{4,6})\b', t, re.I):
                sites[IMAGE_BASE + int(m.group(1), 16)].add('%s:tru+0x%s' % (d, m.group(1).lower()))
    return sites


def changed_ranges(p, gap):
    """-> [(new_start, new_end, old_start or None, kind)] kind 'diff' (non-zero DIFF bytes) or 'extra'"""
    df = np.frombuffer(p['diff'], dtype=np.uint8)
    out = []; npos = opos = dpos = 0
    for x, y, z in p['tri']:
        if x:
            nz = np.flatnonzero(df[dpos:dpos + x])
            if len(nz):
                st = prev = int(nz[0])
                for i in nz[1:]:
                    i = int(i)
                    if i - prev > gap: out.append((npos + st, npos + prev + 1, opos + st, 'diff')); st = i
                    prev = i
                out.append((npos + st, npos + prev + 1, opos + st, 'diff'))
            npos += x; opos += x; dpos += x
        if y:
            out.append((npos, npos + y, None, 'extra')); npos += y
        opos += z
    return out


def cmd_exesites(kit, our_exe, argv):
    asi = K_arg(argv, '--asi', os.path.join(HERE, '..', 'src', 'asi')); gap = int(K_arg(argv, '--gap', '8'))
    win = int(K_arg(argv, '--win', '16')); rep = K_arg(argv, '--out')
    man = load(os.path.join(kit, 'manifest.json')); x = man['exe']
    pb = open(os.path.join(kit, x['patch']), 'rb').read(); p = K.parse_patch(pb)
    ob = open(our_exe, 'rb').read()
    print('exe patch %s: %d bytes, md5 %s; result %s md5 %s (%d bytes), source = Steamless output md5 %s (%d bytes)' % (
        x['patch'], len(pb), K.md5(pb), x.get('name'), x['md5'], x['size'], x['source']['md5'], x['source']['size']))
    print('our exe %s: md5 %s, %d bytes (equals the Steamless source: %s)' % (os.path.basename(our_exe), K.md5(ob), len(ob), K.md5(ob) == x['source']['md5']))
    seeks = [t[2] for t in p['tri'] if t[2]]
    print('control triples %d, non-zero seeks %d, diff bytes %d (non-zero %d), extra bytes %d' % (
        len(p['tri']), len(seeks), sum(t[0] for t in p['tri']), int(np.count_nonzero(np.frombuffer(p['diff'], dtype=np.uint8))),
        sum(t[1] for t in p['tri'])))
    approx = K.bspatch(ob, p)
    base, secs = pe_sections(approx); _, osecs = pe_sections(ob)
    print('sections new~ : ' + ', '.join('%s va 0x%x vsz 0x%x raw 0x%x rsz 0x%x ch %08x' % (s['name'], s['va'], s['vsz'], s['raw'], s['rsz'], s['ch']) for s in secs))
    print('sections ours : ' + ', '.join('%s va 0x%x vsz 0x%x raw 0x%x rsz 0x%x ch %08x' % (s['name'], s['va'], s['vsz'], s['raw'], s['rsz'], s['ch']) for s in osecs))
    rng = changed_ranges(p, gap)
    by = collections.Counter(); rows = []
    for ns, ne, os_, kind in rng:
        sec, va = off2va(secs, base, ns)
        by[(sec, kind)] += ne - ns
        rows.append(dict(ns=ns, ne=ne, os=os_, kind=kind, sec=sec, va=va, n=ne - ns,
                         new=approx[ns:ns + min(16, ne - ns)].hex(), old=ob[os_:os_ + min(16, ne - ns)].hex() if os_ is not None else ''))
    print('changed ranges (gap %d): %d; bytes per section / kind: %s' % (gap, len(rows), ', '.join('%s/%s %d' % (k[0], k[1], v) for k, v in sorted(by.items()))))
    sites = plugin_sites(asi)
    tx = [s for s in osecs if s['ch'] & 0x20000000]
    def in_code(va): return any(base + s['va'] <= va < base + s['va'] + s['vsz'] for s in tx)
    code_sites = {va: l for va, l in sites.items() if in_code(va)}
    print('plugin sites (TruGuard excluded): %d addresses, %d in executable sections' % (len(sites), len(code_sites)))
    hits = []
    for r in rows:
        if r['va'] is None: continue
        for va, l in sites.items():            # code and data sites (vtables / tables in .rdata / .data too)
            if r['va'] - win <= va < r['va'] + r['n'] + win: hits.append((r, va, l))
    print('\noverlaps (site within %d bytes of a changed range): %d pairs' % (win, len(hits)))
    pp = collections.defaultdict(lambda: [set(), set()])
    for r, va, l in hits:
        for x in l:
            pl = x.split(':')[0]; pp[pl][0].add(va); pp[pl][1].add(r['ns'])
    for pl in sorted(pp): print('  %-16s %3d sites, %3d changed ranges' % (pl, len(pp[pl][0]), len(pp[pl][1])))
    print('  all plugins      %3d sites, %3d changed ranges (of %d ranges, %d in .text)' % (
        len(set(h[1] for h in hits)), len(set(h[0]['ns'] for h in hits)), len(rows), sum(1 for r in rows if r['sec'] == '.text')))
    for r, va, l in sorted(hits, key=lambda h: h[1]):
        print('  site 0x%06x (tru+0x%x) %s  <- range 0x%06x..0x%06x (%d B, %s %s) new~ %s old %s' % (
            va, va - IMAGE_BASE, ', '.join(sorted(l)), r['va'], r['va'] + r['n'], r['n'], r['kind'], r['sec'], r['new'], r['old']))
    print('\nall changed ranges:')
    for r in rows:
        print('  %-6s %-8s off 0x%06x..0x%06x %6d B  va %s  new~ %s  old %s' % (r['kind'], r['sec'], r['ns'], r['ne'], r['n'],
              ('0x%06x (tru+0x%x)' % (r['va'], r['va'] - IMAGE_BASE)) if r['va'] else '-', r['new'], r['old']))
    if rep:
        with open(rep, 'w', encoding='utf-8', newline='\n') as fo:
            fo.write('kind\tsection\tnew_off\tnew_end\tbytes\tva\tnew_approx16\tours16\n')
            for r in rows: fo.write('%s\t%s\t0x%x\t0x%x\t%d\t%s\t%s\t%s\n' % (r['kind'], r['sec'], r['ns'], r['ne'], r['n'], ('0x%x' % r['va']) if r['va'] else '-', r['new'], r['old']))
        print('report:', rep)


def K_arg(argv, key, default=None):
    if key in argv:
        k = argv.index(key); v = argv[k + 1]; del argv[k:k + 2]; return v
    return default


def main(argv):
    c = argv[0]
    if c == 'compare': cmd_compare(argv[1], argv[2])
    elif c == 'stats': cmd_stats(argv[1])
    elif c == 'names': cmd_names(argv[1], argv[2:])
    elif c == 'exesites': cmd_exesites(argv[1], argv[2], argv[3:])
    else: sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
