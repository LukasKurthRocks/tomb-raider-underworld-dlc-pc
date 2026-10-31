"""Re-convert the state-chart-like DTPs of a converted DLC tree (finding 43, state chart conversion; pipeline fix
`statechart` of tools/dlc_fixes_build.py and tools/b138_fix_tree.py). Read-only unless --out / process() writes.

Per DRM of the tree with an Xbox source (convert_dlc.raw_dlc, TRUDLC_PACK_FIRST honoured):
  * DTPs of the families chart / table / alist (tools/statechart_corpus.family), new DLC DTPs only (id >= 20000),
    with a PC section of the same id and size.
  * Player charts (>= MIN_COND condition records of the title update's Lara + generic condition ids, e.g. DLC 2
    doppelganger_casual.drm DTP 20212) first get the five typed steps of tools/statechart_fix_all.run (base pair
    lara.drm Xbox layer2 12647 / PC 850, extracted on demand).
  * Then every family DTP gets the base game's twin truth (tools/statechart_twins.py, levels exact + value,
    leave-one-pair-out precision 99.99 %).
  * Player charts last: the proven condition-record and transition layouts are applied again in memory (they agree
    with the twins on DTP 20212; any word they override is logged).
Needs work/statechart/corpus.pkl (built with tools/statechart_corpus.py when missing) and, for player charts, the
title-update memory image (TRUDLC_TU_IMAGE, default work/xenia_dump/tu_image_82000000.bin; without it player charts
get the twins only and a log line says so).

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/statechart_fix_tree.py PC_TREE [--pack pack11] [--out OUT_TREE] [--names a.drm,b.drm]
  without --out: report only (wrong truth words per DTP)
"""
import sys, os, struct, collections, shutil, contextlib, io, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_write as DW
import statechart_twins as TW, statechart_corpus as CO

W = os.path.join(HERE, '..', 'work')
CORPUS = os.path.join(W, 'statechart', 'corpus.pkl')
TU_IMAGE = os.environ.get('TRUDLC_TU_IMAGE') or os.path.join(W, 'xenia_dump', 'tu_image_82000000.bin')
MIN_COND = 1000


def quiet(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = fn(*a)
    return r, buf.getvalue()


class Fixer:
    def __init__(self, tmp, corpus=CORPUS):
        import pickle
        if not os.path.exists(corpus):
            os.makedirs(os.path.dirname(corpus), exist_ok=True)
            CO.main([corpus])
        self.T = TW.Truth(pickle.load(open(corpus, 'rb')))
        self.tmp = tmp
        self.ids = None
        if os.path.exists(TU_IMAGE):
            import statechart_cond_fix as SC
            self.ids = SC.tu_ids(open(TU_IMAGE, 'rb').read())
        self.refs = None

    def lara_refs(self):
        if self.refs is None:
            import bigfile_extract as BE
            xl, pl = os.path.join(self.tmp, 'x_lara.drm'), os.path.join(self.tmp, 'pc_lara.drm')
            quiet(BE.main, ['xbase2', 'lara.drm', xl]); quiet(BE.main, ['pcbig', 'lara.drm', pl])
            self.refs = (xl, pl)
        return self.refs

    def pairs(self, XD, PD):
        """[(family, xbox section, pc section)] - DLC DTPs (id >= 20000) with a PC section of the same id and size"""
        pc = collections.defaultdict(list)
        for s in PD.sections:
            if s.type == 7: pc[s.id].append(s)
        out, used = [], set()
        for s in XD.sections:
            if s.type != 7 or s.id < 20000: continue
            f = CO.family(bytes(s.data), s.id, s.reloc, 'be')
            if f is None: continue
            cand = [p for p in pc.get(s.id, ()) if len(p.data) == len(s.data) and id(p) not in used]
            if not cand: continue
            p = next((p for p in cand if (bytes(p.data[:4]) == b'\0\0\0\0') == (bytes(s.data[:4]) == b'\0\0\0\0')), cand[0])
            used.add(id(p)); out.append((f, s, p))
        return out

    def player_chart(self, s):
        if self.ids is None or CO.fam_be(bytes(s.data), s.id) != 'chart': return False
        import statechart_cond_fix as SC, drm_reloc as R
        r = R.parse(bytes(s.reloc), 'be')
        return len(SC.records(bytes(s.data), '>', self.ids, set(r.pointer_offsets()) | set(r.id_offsets()))) >= MIN_COND

    def process(self, rel, path, log, st, write=True):
        """-> new raw bytes of the PC DRM or None (nothing to change / no Xbox source)"""
        from convert_dlc import raw_dlc
        from drm import cdrm_decode
        raw, _ = raw_dlc(rel.replace('/', '\\'))
        if raw is None: raw, _ = raw_dlc(os.path.basename(rel))
        if raw is None: return None
        xraw = cdrm_decode(raw, 'be')
        XD = DW.read(xraw, 'be')
        praw = open(path, 'rb').read()
        PD = DW.read(praw, 'le')
        prs = self.pairs(XD, PD)
        if not prs: return None
        players = [s.id for f, s, p in prs if f == 'chart' and self.player_chart(s)]
        if players and write:
            import statechart_fix_all as FA
            xl, pl = self.lara_refs()
            xf = os.path.join(self.tmp, 'x_' + os.path.basename(rel)); open(xf, 'wb').write(xraw)
            cur = path
            for sid in players:
                d = os.path.join(self.tmp, 'chain_%d' % sid)
                cur, txt = quiet(FA.run, TU_IMAGE, xl, pl, xf, cur, d, sid, False)
                log.append('%s DTP %d: player chart, five typed steps (%s)' % (rel, sid, ' / '.join(
                    l.strip() for l in txt.splitlines() if l.startswith('target'))))
            PD = DW.read(open(cur, 'rb').read(), 'le')
            prs = self.pairs(XD, PD)
        elif self.ids is None and any(f == 'chart' for f, _, _ in prs):
            log.append('%s: no title-update image (%s) - player charts get the twins only' % (rel, TU_IMAGE))
        changed = False
        for f, s, p in prs:
            n, t = TW.fix_section(self.T, s, p)
            extra = ''
            if s.id in players: extra = self.proven(s, p)
            st[f] += 1; st['truth_words'] += t; st['twin_changed'] += n
            log.append('%s DTP %d %s 0x%x: %d truth words, %d changed by the twins%s' % (rel, s.id, f, len(s.data), t, n, extra))
            if n or s.id in players: changed = True
        if not changed: return None
        raw = PD.write('le')
        if praw[:4] == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        return raw

    def proven(self, s, p):
        """condition records + transitions of a player chart again, by their proven layouts; returns a log note"""
        import statechart_cond_fix as SC, shape_proof as SP, drm_reloc as R
        xd = bytes(s.data); pd = bytearray(p.data)
        xr, pr = R.parse(bytes(s.reloc), 'be'), R.parse(bytes(p.reloc), 'le')
        skip = set(xr.pointer_offsets()) | set(xr.id_offsets()) | set(pr.pointer_offsets()) | set(pr.id_offsets())
        nc = nt = 0
        for o, k, i, v, f6, f7 in SC.records(xd, '>', self.ids, skip):
            want = struct.pack('<3H', k, i, v) + bytes((f6, f7))
            if bytes(pd[o:o + 8]) != want: pd[o:o + 8] = want; nc += 1
        for a in SP.shaped(xd, dict(xr.internal), 0x14, (8, 0xc)):
            y = SP.convert(xd[a:a + 0x14], 'hhhhppw')
            for o in range(0, 0x14, 4):
                if a + o in skip: continue
                if bytes(pd[a + o:a + o + 4]) != y[o:o + 4]: pd[a + o:a + o + 4] = y[o:o + 4]; nt += 1
        p.data = bytes(pd)
        return '; proven layouts after the twins: %d condition records, %d transition words overridden' % (nc, nt)


def report(F, rel, path, log):
    """wrong truth words per family DTP of one PC DRM (no change)"""
    from convert_dlc import raw_dlc
    from drm import cdrm_decode
    raw, _ = raw_dlc(rel.replace('/', '\\'))
    if raw is None: raw, _ = raw_dlc(os.path.basename(rel))
    if raw is None: return []
    XD = DW.read(cdrm_decode(raw, 'be'), 'be'); PD = DW.read(open(path, 'rb').read(), 'le')
    rows = []
    for f, s, p in F.pairs(XD, PD):
        X = TW.Chart(s.data, s.reloc, 'be'); Pc = TW.Chart(p.data, p.reloc, 'le')
        tw = TW.truth_words(F.T, X, Pc.mask, f)
        pd = bytes(p.data)
        bad = sum(1 for o, (w, k) in tw.items() if pd[o:o + 4] != w)
        nw = sum(1 for o in range(0, len(pd) - 3, 4) if o not in X.mask and o not in Pc.mask)
        rows.append((rel, s.id, f, len(s.data), nw, len(tw), bad))
        log.append('%-45s DTP %6d %-5s 0x%06x  words %6d  truth %6d  wrong %5d' % rows[-1])
    return rows


def main(argv):
    out = None; names = None
    if '--out' in argv: k = argv.index('--out'); out = argv[k + 1]; del argv[k:k + 2]
    if '--names' in argv: k = argv.index('--names'); names = set(argv[k + 1].split(',')); del argv[k:k + 2]
    if '--pack' in argv: k = argv.index('--pack'); os.environ['TRUDLC_PACK_FIRST'] = argv[k + 1]; del argv[k:k + 2]
    import dtp_audit as DA
    tree = os.path.abspath(argv[0])
    files = DA.overlay([tree], names)
    tmp = tempfile.mkdtemp(prefix='statechart_', dir=os.path.join(W, 'statechart'))
    try:
        F = Fixer(tmp)
        log = []; st = collections.Counter()
        if out is None:
            tot = collections.Counter()
            for rel, path in sorted(files.items()):
                for r in report(F, rel, path, log):
                    tot['dtps'] += 1; tot['truth'] += r[5]; tot['wrong'] += r[6]; tot['with_wrong'] += r[6] > 0
            for l in log: print(l)
            print('total: %s' % dict(tot))
            return
        os.makedirs(out, exist_ok=True)
        for rel, path in sorted(files.items()):
            new = F.process(rel, path, log, st)
            if new is not None:
                q = os.path.join(out, rel); os.makedirs(os.path.dirname(q), exist_ok=True); open(q, 'wb').write(new)
        for l in log: print(l)
        print('total: %s' % dict(st))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main(sys.argv[1:])
