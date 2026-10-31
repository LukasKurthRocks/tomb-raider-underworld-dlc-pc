"""Base-game corpus of state-chart-like DTP pairs (finding 43, state chart conversion): every base DRM name that exists
in the Xbox base archives and in the PC bigfile / patch, with its chart-family DTPs paired Xbox <-> PC by family and
order. Writes one pickle with the section bytes and relocations, for tools/statechart_twins.py. Read-only on the game
data. Families (base player lara.drm: Xbox 12647 / 12646 / 2517 = PC 850 / 849 / 848):
  chart  state chart: words 3..6 = 10000, 12000, 4000, 6000
  table  the chart's 16-byte record table: u16 0x2001, u16 0, .., u16 0x15 at +8
  alist  pointer / id-ref list: word 0 = own id or 0, word 1 = 0, word 2 relocated, u16 count at +0xc, id-ref words
Result 2026-10-31: 940 common names; 615 chart pairs (603 of the same size), 20 table pairs, 836 alist pairs.

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/statechart_corpus.py OUT.pkl [--names a.drm,b.drm] [--workers N]
  Xbox: work/idx_xbox_base.json (layer2 wins over layer1, the title update over both); PC: work/idx_pc.json (patch wins)
"""
import sys, os, json, pickle, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work')
HDR = struct.pack('>4I', 10000, 12000, 4000, 6000)


def fam_be(d, sid):
    """family of an Xbox (big-endian) DTP without condition-record counting"""
    if len(d) >= 0x1c and d[0xc:0x1c] == HDR: return 'chart'
    if len(d) >= 0x20 and d[0:4] == b'\x20\x01\0\0' and d[8:10] == b'\x00\x15': return 'table'
    return None


def fam_le(d):
    if len(d) >= 0x1c and b''.join(d[k:k + 4][::-1] for k in range(0xc, 0x1c, 4)) == HDR: return 'chart'
    if len(d) >= 0x20 and d[0:4] == b'\x01\x20\0\0' and d[8:10] == b'\x15\x00': return 'table'
    return None


def job(a):
    path, e, i = a
    from archive import Archive
    from drm import cdrm_decode
    import drm_write as DW
    try:
        A = Archive(path, e)
        D = DW.read(cdrm_decode(A.read(A.idx[i]), e), e)
    except Exception as ex:
        return None
    out = []
    for s in D.sections:
        if s.type != 7: continue
        d = bytes(s.data)
        f = family(d, s.id, s.reloc, e)
        if f: out.append((f, s.id, d, bytes(s.reloc)))
    return out


def family(d, sid, reloc, e):
    """'chart' / 'table' / 'alist' or None for one DTP (e: 'be' Xbox, 'le' PC)"""
    import drm_reloc as R
    f = fam_be(d, sid) if e == 'be' else fam_le(d)
    if f is None and len(d) >= 0x10:
        # alist: word 0 = own id or 0, word 1 = 0, word 2 relocated, u16 count at +0xc, id-ref words
        fm = '>' if e == 'be' else '<'
        w0, w1 = struct.unpack_from(fm + '2I', d, 0)
        cnt = struct.unpack_from(fm + 'H', d, 0xc)[0]
        if w0 in (sid, 0) and w1 == 0 and cnt > 0 and d[0xe:0x10] == b'\0\0':
            r = R.parse(bytes(reloc), e)
            if 8 in set(r.pointer_offsets()) and r.id_offsets(): f = 'alist'
    return f


def main(argv):
    workers = 8; names = None
    if '--workers' in argv: k = argv.index('--workers'); workers = int(argv[k + 1]); del argv[k:k + 2]
    if '--names' in argv: k = argv.index('--names'); names = set(argv[k + 1].lower().split(',')); del argv[k:k + 2]
    from names import load as load_names, L as NAME_DIR
    nmx = load_names(NAME_DIR + 'Tomb Raider Underworld (Xenon).txt')
    nmp = load_names(NAME_DIR + 'Tomb Raider Underworld (PC).txt') if os.path.exists(NAME_DIR + 'Tomb Raider Underworld (PC).txt') else nmx
    from bigfile import read_index

    def pick(idx_file, nm, prio):
        best = {}
        hashes = {}
        for rec in json.load(open(os.path.join(W, idx_file))):
            path, i, h, spec, n, secs = rec[:6]
            if spec != 0xffffffff or not isinstance(secs, list): continue
            if not any(s[0] == 7 for s in secs): continue
            name = nm.get(h, '%08x' % h).split('\\')[-1].lower()
            if not name.endswith('.drm') or (names and name not in names): continue
            p = prio(path)
            if name not in best or p > best[name][0]: best[name] = (p, path, i)
        return best
    xb = pick('idx_xbox_base.json', nmx, lambda p: 2 if 'TitleUpdate' in p else 1 if 'layer2' in p else 0)
    pb = pick('idx_pc.json', nmp, lambda p: 1 if 'patch' in p else 0)
    common = sorted(set(xb) & set(pb))
    print('Xbox names %d, PC names %d, common %d' % (len(xb), len(pb), len(common)), flush=True)
    jobs = []
    for n in common:
        jobs.append((xb[n][1], 'be', xb[n][2])); jobs.append((pb[n][1], 'le', pb[n][2]))
    from multiprocessing import Pool
    with Pool(workers) as P: res = P.map(job, jobs, chunksize=4)
    corpus = []
    st = collections.Counter()
    for k, n in enumerate(common):
        xs, ps = res[2 * k], res[2 * k + 1]
        if not xs or not ps: continue
        for fam in ('chart', 'table', 'alist'):
            xl = [x for x in xs if x[0] == fam]; pl = [p for p in ps if p[0] == fam]
            st['%s_x' % fam] += len(xl); st['%s_p' % fam] += len(pl)
            if len(xl) != len(pl): st['%s_count_mismatch' % fam] += 1; continue
            for x, p in zip(xl, pl):
                corpus.append({'name': n, 'family': fam, 'xid': x[1], 'pid': p[1], 'x': x[2], 'xr': x[3], 'p': p[2], 'pr': p[3]})
                st['%s_pairs' % fam] += 1
                if len(x[2]) == len(p[2]): st['%s_same_size' % fam] += 1
    pickle.dump(corpus, open(argv[0], 'wb'))
    print('corpus: %d pairs -> %s; %s' % (len(corpus), argv[0], dict(st)))


if __name__ == '__main__':
    main(sys.argv[1:])
