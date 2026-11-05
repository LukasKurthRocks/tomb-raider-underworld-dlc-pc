"""Per-offset byte-class rules for the 0x17c-byte particle records of object data DTPs, proven on the base Xbox / PC
pairs, and a scan of converted DLC DRMs against them (read-only; night analysis N5 04.11.2026, F3 / B24 follow-up to
tools/objdata_rec148_scan.py, which checks only the spawn word +0x148).

calibrate: for every base object (PC objectlist ids 1..821, tools/pairs.py) the object data DTP (object section +8) is
  paired Xbox / PC, and for every record word offset o (0..0x178 step 4) that is no relocated pointer / id reference
  on either side, the permutation(s) that turn the Xbox bytes into the PC bytes are collected (s32, s16, u16u8u8,
  u8u8u16, raw). An offset is RULED when >= MIN_N informative samples (exactly one permutation fits) all agree.
  Result: work/generic/objdata_rec_rules.pkl {offset: (class, n_informative, n_contradicting)} + printed table.
scan PATH..: for every installed DLC DRM with an Xbox source (work/generic/dlc_drms.pkl, pack11 then pack10), all
  copies of its object data DTP(s), every record word at a ruled offset whose PC bytes != class(Xbox bytes) is
  reported (per file / copy / offset count; -v lists every word).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/objdata_rec_classes.py calibrate OBJECTLIST.txt
  ../bin/pyt -t 1800 tools/objdata_rec_classes.py scan PATH [PATH ...] [-v]
"""
import sys, os, struct, pickle, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_write as DW

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
RULES = os.path.join(ROOT, 'work', 'generic', 'objdata_rec_rules.pkl')
PERMS = {'s32': (3, 2, 1, 0), 's16': (1, 0, 3, 2), 'u16u8u8': (1, 0, 2, 3), 'u8u8u16': (0, 1, 3, 2), 'raw': (0, 1, 2, 3)}
REC = 0x17c
MIN_N = 20


def perm(b, p):
    return bytes(b[i] for i in p)


def slots(reloc, e):
    r = R.parse(reloc, e) if reloc else R.Reloc()
    s = set(o for o, _ in r.internal) | set(o for _, o in r.idref) | set(o for _, o in r.idref_a)
    s |= set(src for _, src, _ in r.external)
    return s, dict(r.internal)


def objdata_dtps(secs, e, get):
    """[(dtp_id)] named at object section +8"""
    out = []
    for s in secs:
        t, d, rel, sid = get(s)
        if t != 11 or len(d) < 12:
            continue
        r = R.parse(rel, e) if rel else R.Reloc()
        if dict((o, ty) for ty, o in r.idref).get(8) == 7:
            out.append(struct.unpack_from(('>' if e == 'be' else '<') + 'I', d, 8)[0])
    return out


def records(d, e, reloc):
    sl, it = slots(reloc, e)
    if len(d) < 0x14 or 0x10 not in it:
        return None, sl
    n = struct.unpack_from(('>' if e == 'be' else '<') + 'H', d, 0x0c)[0]
    b = it[0x10]
    if b + n * REC > len(d):
        return None, sl
    return [b + k * REC for k in range(n)], sl


def calibrate(objlist):
    os.chdir(ROOT)
    import pairs as P
    names = []
    for ln in open(objlist, encoding='latin-1').read().splitlines()[1:]:
        if ',' in ln:
            i, n = ln.split(',', 1)
            if int(i) <= 821:
                names.append(n.strip())
    stat = collections.defaultdict(collections.Counter)
    nobj = 0
    get = lambda s: (s['type'], s['data'], s['reloc'], s['id'])
    for n in names:
        try:
            xd_ = P.xbox_drm(n + '.drm'); pd_ = P.pc_drm(n + '.drm')
        except Exception:
            continue
        if not xd_ or not pd_:
            continue
        xs, ps = xd_[1], pd_[1]
        xi, pi = objdata_dtps(xs, 'be', get), objdata_dtps(ps, 'le', get)
        if not xi or not pi:
            continue
        xsec = [s for s in xs if s['type'] == 7 and s['id'] == xi[0]]
        psec = [s for s in ps if s['type'] == 7 and s['id'] == pi[0]]
        if not xsec or not psec:
            continue
        xr, xsl = records(xsec[0]['data'], 'be', xsec[0]['reloc'])
        pr, psl = records(psec[0]['data'], 'le', psec[0]['reloc'])
        if not xr or not pr or len(xr) != len(pr):
            continue
        nobj += 1
        xd, pd = xsec[0]['data'], psec[0]['data']
        for bx, bp in zip(xr, pr):
            for o in range(0, REC - 3, 4):
                if (bx + o) in xsl or (bp + o) in psl:
                    stat[o]['ptr'] += 1
                    continue
                xb, pb = xd[bx + o:bx + o + 4], pd[bp + o:bp + o + 4]
                fit = [k for k, p in PERMS.items() if perm(xb, p) == pb]
                stat[o][fit[0] if len(fit) == 1 else ('amb' if fit else 'none')] += 1
    rules = {}
    print('base objects paired: %d' % nobj)
    for o in sorted(stat):
        c = stat[o]
        inf = {k: v for k, v in c.items() if k in PERMS}
        tot = sum(inf.values())
        best = max(inf, key=inf.get) if inf else None
        if best and tot >= MIN_N and inf[best] == tot and c['ptr'] == 0:
            rules[o] = (best, tot, c['none'])
        print('+0x%03x %-8s %s' % (o, ('RULE ' + best) if o in rules else '-', dict(c)))
    pickle.dump(rules, open(RULES, 'wb'))
    print('ruled offsets: %d -> %s' % (len(rules), RULES))


def files(paths):
    for p in paths:
        if os.path.isdir(p):
            for n in sorted(os.listdir(p)):
                if n.lower().endswith('.drm'):
                    yield os.path.join(p, n)
        else:
            yield p


def scan(paths, verbose):
    rules = pickle.load(open(RULES, 'rb'))
    C = pickle.load(open(os.path.join(ROOT, 'work', 'generic', 'dlc_drms.pkl'), 'rb'))
    base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
    idx = {}
    for k, v in C.items():
        if k[0] in ('ack11.000', 'ack10.000'):
            nm = base(k[1])
            if nm not in idx or k[0] == 'ack11.000':
                idx[nm] = v
    tot = collections.Counter()
    nwords = 0
    for path in files(paths):
        nm = os.path.splitext(os.path.basename(path))[0].lower()
        if nm not in idx:
            continue
        try:
            pdrm = DW.read(open(path, 'rb').read(), 'le')
        except Exception:
            continue
        xs = idx[nm][1]
        pids = objdata_dtps(pdrm.sections, 'le', lambda s: (s.type, s.data, s.reloc, s.id))
        xids = objdata_dtps(xs, 'be', lambda s: (s['type'], s['data'], s['reloc'], s['id']))
        for did in sorted(set(pids) & set(xids)):
            pl = [s for s in pdrm.sections if s.type == 7 and s.id == did]
            xl = [s for s in xs if s['type'] == 7 and s['id'] == did]
            for copy, (ps, xsec) in enumerate(zip(pl, xl)):
                xr, xsl = records(xsec['data'], 'be', xsec['reloc'])
                pr, psl = records(ps.data, 'le', ps.reloc)
                if not xr or not pr or len(xr) != len(pr):
                    continue
                per = collections.Counter()
                for k, (bx, bp) in enumerate(zip(xr, pr)):
                    for o, (cls, n, _) in rules.items():
                        if (bx + o) in xsl or (bp + o) in psl:
                            continue
                        xb, pb = xsec['data'][bx + o:bx + o + 4], ps.data[bp + o:bp + o + 4]
                        want = perm(xb, PERMS[cls])
                        if pb != want:
                            per[o] += 1
                            nwords += 1
                            if verbose:
                                print('   %s DTP %d copy %d rec %d +0x%03x (file +0x%x): xbox %s pc %s want %s (%s)'
                                      % (nm, did, copy, k, o, bp + o, xb.hex(), pb.hex(), want.hex(), cls))
                if per:
                    print('%s DTP %d copy %d (section %d, %d records): %d wrong words at %s'
                          % (nm, did, copy, pdrm.sections.index(ps), len(pr), sum(per.values()),
                             ', '.join('+0x%03x x%d' % (o, c) for o, c in sorted(per.items()))))
                    tot[nm] += sum(per.values())
    print('files with wrong record words: %d, words: %d' % (len(tot), nwords))


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == 'calibrate':
        calibrate(a[1])
    elif a[0] == 'scan':
        scan([x for x in a[1:] if x != '-v'], '-v' in a)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
