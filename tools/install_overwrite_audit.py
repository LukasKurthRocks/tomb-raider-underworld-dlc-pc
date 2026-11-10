r"""Install overwrite audit (N2, 2026-11-11; read-only): did a later Install-TruTree install overwrite DRM sections an
EARLIER install had changed? The generic form of the 08.11. lesson (the n6b stack replaced the played ring fix of
30.10.; docs/WINDOWS_REBUILD.md finding 52) - it works on the install backups alone, no rule registry needed.

Inputs: <workspace>\backup\tree_*\manifest.json + files\ (Install-TruTree: the file as it was BEFORE that install;
names containing "truguard" are never opened), the install's source tree (when its md5 = the manifest's installed
md5) and the installed game file (env TRUDLC_GAME_MODS = the game's mods folder; read only).
Per file: owned(k) = sections an earlier non-restored install k changed (key type / id / occurrence, data + relocations).
A hit = an install s at or after --since changed a section of owned(k) whose bytes right before s were still k's
bytes. Per hit the word fate of k's change (same-size sections): kept / reverted to the value before k / other, and
the words s changed on top. A ShaderLib that s's tree lists in its nativefix.json (`tu_batch nativefix`, rewrite
proven bit-exact in the VM) counts as kept; copies taken from another tree's nativefix run (e.g. clean17z rest10 =
amd17r) are reported - read them with that tree's nativefix.json.

Usage (from the repository root):
  set TRUDLC_GAME_MODS=<game>\mods
  ../bin/pyt -t 1800 tools/install_overwrite_audit.py --since 20261108_170854 --out DIR
      -> DIR\history.json (install history per file), DIR\hits.tsv, DIR\summary.txt;
      exit 0 = no earlier-owned word lost, 1 = at least one hit loses words / sections (read the hits)
"""
import os, sys, json, hashlib, collections, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import drm_write as DW

REPO = os.path.normpath(os.path.join(HERE, '..'))
BK = os.path.join(os.path.dirname(REPO), 'backup')
TYPES = {0: 'gen', 5: 'tex', 6: 'wave', 7: 'DTP', 8: 'script', 9: 'shlib', 10: 'mat', 11: 'obj', 12: 'mesh'}


def md5(b): return hashlib.md5(b).hexdigest()


def rd(path):
    if 'truguard' in path.lower(): raise SystemExit('refused to open %s' % path)
    return open(path, 'rb').read() if os.path.isfile(path) else None


def secs(b):
    try: D = DW.read(b, 'le')
    except Exception: return None
    out, n = {}, collections.Counter()
    for s in D.sections:
        k = (s.type, s.id, n[(s.type, s.id)]); n[(s.type, s.id)] += 1
        out[k] = (bytes(s.data), bytes(s.reloc))
    return out


def kname(k): return '%s %d%s' % (TYPES.get(k[0], 't%d' % k[0]), k[1], '' if k[2] == 0 else '#%d' % k[2])


def history():
    """[install] and {file: [event]} from the backup manifests (time order)"""
    def entries(lst):
        for e in lst or []:
            if isinstance(e, str): yield e.replace('\\', '/'), None
            else: yield e['path'].replace('\\', '/'), e.get('md5')
    H = {}
    for d in sorted(os.listdir(BK)):
        if 'truguard' in d.lower() or not d.startswith('tree_'): continue
        mf = os.path.join(BK, d, 'manifest.json')
        if not os.path.isfile(mf): continue
        m = json.loads(open(mf, 'rb').read().decode('utf-8-sig'))
        inst = dict(entries(m.get('installed'))); rep = dict(entries(m.get('replaced'))); add = [p for p, _ in entries(m.get('added'))]
        src = re.sub(r'^.*?trudlcport[\\/]', '', m.get('source', ''))
        for p in set(rep) | set(add) | set(inst):
            if 'truguard' in p.lower(): continue
            H.setdefault(p, []).append(dict(time=m['time'], dir=d, restored=d.endswith('.restored'), source=src,
                                            before=rep.get(p), added=p in add, after=inst.get(p)))
    for p in H: H[p].sort(key=lambda e: e['time'])
    return H


_NF = {}


def nativefix_libs(source):
    """ShaderLib ids that `tu_batch nativefix` rewrote for the install source <tree>/mods (its <tree>/nativefix.json)"""
    if source not in _NF:
        p = os.path.join(REPO, os.path.dirname(os.path.normpath(source.replace('\\', os.sep))), 'nativefix.json')
        _NF[source] = {int(k) for k in json.load(open(p))['libs']} if os.path.isfile(p) else set()
    return _NF[source]


def words(b, a, s):
    if b is None or a is None or s is None or not (len(b[0]) == len(a[0]) == len(s[0])):
        return None
    own = [o for o in range(0, len(a[0]) - 3, 4) if a[0][o:o + 4] != b[0][o:o + 4]]
    kept = sum(1 for o in own if s[0][o:o + 4] == a[0][o:o + 4])
    rev = sum(1 for o in own if s[0][o:o + 4] == b[0][o:o + 4])
    top = sum(1 for o in range(0, len(a[0]) - 3, 4) if s[0][o:o + 4] != a[0][o:o + 4] and a[0][o:o + 4] == b[0][o:o + 4])
    lost = [hex(o) for o in own if s[0][o:o + 4] != a[0][o:o + 4]]
    return dict(owned=len(own), kept=kept, reverted=rev, other=len(own) - kept - rev, on_top=top, lost=lost[:12])


def main(argv):
    since = '20261108_170854'; out = None
    if '--since' in argv: since = argv[argv.index('--since') + 1]
    if '--out' in argv: out = argv[argv.index('--out') + 1]
    if not out: sys.exit(__doc__)
    game = os.environ.get('TRUDLC_GAME_MODS')
    if not game or not os.path.isdir(game): sys.exit('set TRUDLC_GAME_MODS to the installed "<game>\\mods" folder')
    os.makedirs(out, exist_ok=True)
    H = history(); json.dump(H, open(os.path.join(out, 'history.json'), 'w'), indent=1)
    hits = open(os.path.join(out, 'hits.tsv'), 'w', encoding='utf-8')
    hits.write('file\towner_time\towner_source\tsection\ttarget_time\ttarget_source\tsizes(before k/after k/after s)\twords\n')
    nlost = nhit = 0; files = 0
    for p, ev in sorted(H.items()):
        if not any(e['time'] >= since and not e['restored'] for e in ev): continue
        files += 1
        gf = rd(os.path.join(game, p.replace('/', os.sep)))
        bef = [rd(os.path.join(BK, e['dir'], 'files', p.replace('/', os.sep))) for e in ev]
        aft = []
        for i, e in enumerate(ev):
            a = None
            if e['after'] and e['source']:
                b = rd(os.path.join(REPO, e['source'].replace('\\', os.sep), p.replace('/', os.sep)))
                if b is not None and md5(b) == e['after']: a = b
            if a is None and i + 1 < len(ev) and bef[i + 1] is not None and (not e['after'] or md5(bef[i + 1]) == e['after']): a = bef[i + 1]
            if a is None and i + 1 == len(ev) and gf is not None and (not e['after'] or md5(gf) == e['after']): a = gf
            aft.append(a)
        S = {}
        def sv(b):
            if b is None: return None
            h = md5(b)
            if h not in S: S[h] = secs(b)
            return S[h]
        own = []
        for i, e in enumerate(ev):
            if e['restored'] or bef[i] is None or aft[i] is None: continue
            B, A = sv(bef[i]), sv(aft[i])
            if B is not None and A is not None: own.append((i, e, B, A, {k for k in set(B) | set(A) if B.get(k) != A.get(k)}))
        for j, s in enumerate(ev):
            if s['time'] < since or s['restored'] or bef[j] is None or aft[j] is None: continue
            Bs, As = sv(bef[j]), sv(aft[j])
            if Bs is None or As is None: continue
            ch = {k for k in set(Bs) | set(As) if Bs.get(k) != As.get(k)}
            for i, k, Bk, Ak, o in own:
                if i >= j: continue
                for key in sorted(o & ch):
                    if Bs.get(key) != Ak.get(key): continue
                    w = words(Bk.get(key), Ak.get(key), As.get(key))
                    nhit += 1
                    nf = key[0] == 9 and key[1] in nativefix_libs(s['source'])
                    if nf: w = dict(nativefix=True, note='ShaderLib rewritten by tu_batch nativefix (listed in the layer\'s nativefix.json; VM bit-exact)')
                    lost = not nf and (w is None or w['kept'] < w['owned'])
                    nlost += lost
                    ln = lambda V: str(len(V[key][0])) if key in V else '-'
                    hits.write('\t'.join([p, k['time'], k['source'], kname(key), s['time'], s['source'],
                                          '%s/%s/%s' % (ln(Bk), ln(Ak), ln(As)),
                                          json.dumps(w) if w else 'section replaced (size / presence changed)']) + '\n')
        S.clear()
    summ = '%d files with installs since %s; %d hits (earlier-owned section changed), %d of them lose words / sections' % (files, since, nhit, nlost)
    open(os.path.join(out, 'summary.txt'), 'w').write(summ + '\n')
    print(summ)
    return 1 if nlost else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
