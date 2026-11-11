"""Player-path gate (plan Spielerweg P0, gate G3 / G4): developer-path output = player-path output, file by file.

Read-only. Compares two output trees (or a tree and an md5 list) by relative path (case-insensitive) and md5 of every
file. For a file whose md5 differs, a DRM (raw or CDRM, version 19) is compared section by section: header (names,
section count / order), then per section (type, id, occurrence) the md5 of data and relocations, size, version, flags,
spec and the first differing byte; any other file gets its sizes and first differing byte. Names containing
"truguard" are skipped (never opened).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/playerpath_gate.py compare DEV PLAYER [--report R.json] [--sections N] [--endian le|be]
        DEV / PLAYER = a folder (every file below it) or an md5 list (.tsv: md5 TAB path, as written by md5list /
        tools/tree_md5.py), or both single files (e.g. two generalbank.drm); exit 0 = same file set and every md5
        equal, 1 = any difference, 2 = usage / unreadable.
        --sections N: list at most N differing sections per DRM (default 40); --endian: DRM byte order (default le)
  ../bin/pyt -t 900 tools/playerpath_gate.py md5list TREE OUT.tsv
        writes the md5 list of TREE (md5 TAB path, sorted; the expected list of a developer run, plan 5.4 G4)
  ../bin/pyt -t 900 tools/playerpath_gate.py selftest TREE
        TREE against itself (must be 0 differences) and the section diff on an in-memory copy of TREE's first DRM
        with one data byte and one relocation byte changed (must find exactly those sections); writes nothing
"""
import sys, os, json, hashlib, struct, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def md5(b):
    return hashlib.md5(b).hexdigest()


def skip(name):
    return 'truguard' in name.lower()


def file_md5(p):
    m = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''): m.update(b)
    return m.hexdigest()


def listing(src):
    """{rel lower: (rel, md5, full path or None)} of a folder or an md5 list"""
    out = {}
    if os.path.isdir(src):
        for dp, dn, fn in os.walk(src):
            dn[:] = sorted(d for d in dn if not skip(d))
            for n in sorted(fn):
                if skip(n): continue
                q = os.path.join(dp, n)
                rel = os.path.relpath(q, src).replace('\\', '/')
                out[rel.lower()] = (rel, file_md5(q), q)
        return out
    if os.path.isfile(src):
        for l in open(src, encoding='utf-8'):
            f = l.rstrip('\r\n').split('\t')
            if len(f) < 2 or f[0] == 'md5' or l.startswith('#'): continue
            rel = f[-1].replace('\\', '/')
            if not skip(rel): out[rel.lower()] = (rel, f[0].lower(), None)
        return out
    sys.stderr.write('not a folder or md5 list: %s\n' % src); sys.exit(2)


def usage():
    sys.stderr.write(__doc__); sys.exit(2)


def first_diff(a, b):
    n = min(len(a), len(b))
    for i in range(0, n, 4096):
        if a[i:i + 4096] != b[i:i + 4096]:
            for j in range(i, min(i + 4096, n)):
                if a[j] != b[j]: return j
    return n if len(a) != len(b) else None


def try_drm(b, endian):
    if not (b[:4] == b'CDRM' or (len(b) >= 4 and struct.unpack_from('<i' if endian == 'le' else '>i', b)[0] == 19)):
        return None
    try:
        return DW.read(b, endian)
    except Exception:
        return None


def section_diff(da, db, limit=40):
    """header + per-section differences of two parsed DRMs"""
    res = dict(header=[], sections=[], only_dev=[], only_player=[], differing=0)
    if da.names != db.names: res['header'].append('dependency names differ')
    if da.pad != db.pad: res['header'].append('header padding differs')
    if len(da.sections) != len(db.sections):
        res['header'].append('section count %d != %d' % (len(da.sections), len(db.sections)))

    def keyed(d):
        seen, out = {}, {}
        for i, s in enumerate(d.sections):
            k = (s.type, s.id)
            n = seen.get(k, 0); seen[k] = n + 1
            out[(s.type, s.id, n)] = (i, s)
        return out
    ka, kb = keyed(da), keyed(db)
    order_a = [k for k, _ in sorted(ka.items(), key=lambda x: x[1][0])]
    order_b = [k for k, _ in sorted(kb.items(), key=lambda x: x[1][0])]
    if set(order_a) == set(order_b) and order_a != order_b: res['header'].append('section order differs')
    res['only_dev'] = ['%d:%d#%d' % k for k in order_a if k not in kb]
    res['only_player'] = ['%d:%d#%d' % k for k in order_b if k not in ka]
    for k in order_a:
        if k not in kb: continue
        (ia, a), (ib, b) = ka[k], kb[k]
        what = []
        for f in ('ver', 'flags', 'spec', 'pad'):
            if getattr(a, f) != getattr(b, f): what.append('%s %r != %r' % (f, getattr(a, f), getattr(b, f)))
        if a.data != b.data:
            what.append('data %d / %d B, md5 %s / %s, first diff +0x%x' % (len(a.data), len(b.data), md5(a.data)[:8],
                                                                         md5(b.data)[:8], first_diff(a.data, b.data)))
        if a.reloc != b.reloc:
            what.append('reloc %d / %d B, first diff +0x%x' % (len(a.reloc), len(b.reloc), first_diff(a.reloc, b.reloc)))
        if what:
            res['differing'] += 1
            if len(res['sections']) < limit: res['sections'].append(dict(section='%d:%d#%d' % k, index=ia, what=what))
    return res


def single(p):
    """a file that is not an md5 list: compared as a one-file tree under the name 'file'"""
    return os.path.isfile(p) and not p.lower().endswith('.tsv')


def compare(dev, player, endian='le', limit=40):
    if single(dev) and single(player):
        A = {'file': ('file', file_md5(dev), dev)}; B = {'file': ('file', file_md5(player), player)}
    else:
        A, B = listing(dev), listing(player)
    rep = dict(dev=dev, player=player, dev_files=len(A), player_files=len(B), only_dev=[], only_player=[],
               differ=[], equal=0)
    for k in sorted(set(A) | set(B)):
        if k not in B: rep['only_dev'].append(A[k][0]); continue
        if k not in A: rep['only_player'].append(B[k][0]); continue
        (ra, ma, pa), (rb, mb, pb) = A[k], B[k]
        if ma == mb: rep['equal'] += 1; continue
        d = dict(path=ra, md5_dev=ma, md5_player=mb)
        if pa and pb:
            ba, bb = open(pa, 'rb').read(), open(pb, 'rb').read()
            d['size_dev'], d['size_player'] = len(ba), len(bb)
            xa, xb = try_drm(ba, endian), try_drm(bb, endian)
            if xa is not None and xb is not None:
                d['drm'] = section_diff(xa, xb, limit)
            else:
                d['first_diff'] = first_diff(ba, bb)
        rep['differ'].append(d)
    rep['ok'] = not (rep['only_dev'] or rep['only_player'] or rep['differ'])
    return rep


def print_report(rep):
    print('dev    %s: %d files' % (rep['dev'], rep['dev_files']))
    print('player %s: %d files' % (rep['player'], rep['player_files']))
    print('equal %d, differ %d, only dev %d, only player %d' % (rep['equal'], len(rep['differ']), len(rep['only_dev']),
                                                               len(rep['only_player'])))
    for p in rep['only_dev']: print('  only dev     ', p)
    for p in rep['only_player']: print('  only player  ', p)
    for d in rep['differ']:
        print('  DIFFER %s  %s / %s' % (d['path'], d['md5_dev'], d['md5_player']))
        if 'drm' in d:
            s = d['drm']
            for h in s['header']: print('      header:', h)
            if s['only_dev']: print('      sections only dev:', ', '.join(s['only_dev'][:20]))
            if s['only_player']: print('      sections only player:', ', '.join(s['only_player'][:20]))
            print('      %d differing section(s)' % s['differing'])
            for x in s['sections']: print('        %-14s #%-4d %s' % (x['section'], x['index'], '; '.join(x['what'])))
        elif 'first_diff' in d:
            print('      size %s / %s, first differing byte %s' % (d.get('size_dev'), d.get('size_player'), d['first_diff']))
    print('gate:', 'ok (developer path = player path)' if rep['ok'] else 'DIFFERENT')


def cmd_md5list(tree, out):
    L = listing(tree)
    rows = sorted((v[0], v[1]) for v in L.values())
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('md5\tpath\n')
        for rel, m in rows: f.write('%s\t%s\n' % (m, rel))
    print('wrote %s (%d files)' % (out, len(rows)))
    return 0


def cmd_selftest(tree):
    fails = []
    rep = compare(tree, tree)
    print('tree against itself: %d files, equal %d, differ %d, only %d / %d' % (
        rep['dev_files'], rep['equal'], len(rep['differ']), len(rep['only_dev']), len(rep['only_player'])))
    if not rep['ok'] or rep['equal'] != rep['dev_files']: fails.append('self compare')
    drm = next((v[2] for k, v in sorted(listing(tree).items()) if k.endswith('.drm') and v[2]), None)
    if drm is None:
        print('no DRM in', tree); fails.append('no drm')
    else:
        a = try_drm(open(drm, 'rb').read(), 'le')
        if a is None:
            print('not a PC DRM:', drm); fails.append('parse')
        else:
            b = DW.read(a.write('le'), 'le')
            di = next(i for i, s in enumerate(b.sections) if s.data)
            ri = next((i for i, s in enumerate(b.sections) if s.reloc and i != di), None)
            s = b.sections[di]; s.data = bytes([s.data[0] ^ 0xff]) + s.data[1:]
            want = {'%d:%d' % (s.type, s.id)}
            if ri is not None:
                r = b.sections[ri]; r.reloc = r.reloc[:-1] + bytes([r.reloc[-1] ^ 0xff]); want.add('%d:%d' % (r.type, r.id))
            res = section_diff(a, b)
            got = {x['section'].split('#')[0] for x in res['sections']}
            print('%s: changed %s, found %s' % (os.path.basename(drm), sorted(want), sorted(got)))
            if got != want or res['header']: fails.append('section diff')
    print('selftest:', 'FAILED %s' % fails if fails else 'ok')
    return 1 if fails else 0


def main(argv):
    if not argv: usage()
    cmd = argv[0]
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    if cmd == 'compare':
        args = [a for i, a in enumerate(argv[1:], 1)
                if not a.startswith('--') and not (i > 1 and argv[i - 1] in ('--report', '--sections', '--endian'))]
        if len(args) != 2: usage()
        t0 = time.time()
        rep = compare(args[0], args[1], opt('--endian', 'le'), int(opt('--sections', 40)))
        rep['seconds'] = round(time.time() - t0, 1)
        print_report(rep)
        if opt('--report'):
            os.makedirs(os.path.dirname(os.path.abspath(opt('--report'))), exist_ok=True)
            with open(opt('--report'), 'w', encoding='utf-8') as f: json.dump(rep, f, indent=1)
            print('report', opt('--report'))
        return 0 if rep['ok'] else 1
    if cmd == 'md5list' and len(argv) == 3: return cmd_md5list(argv[1], argv[2])
    if cmd == 'selftest' and len(argv) == 2: return cmd_selftest(argv[1])
    usage()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
