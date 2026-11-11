"""What does the Xbox 360 title update (TU, TitleUpdate.000) change in the game DATA against Xbox retail (layer1 /
layer2), and what does the PC (patch.000 / bigfile.000) have at those places? Read-only, prints a report.
Written for Q60 (2026-11-11, workspace docs Befund-TU-Daten-Hauptspiel-Q60-1111.md): did the TU improve the BASE game
through data (camera, controls, combat, difficulty) that the PC never got?

Subcommands (from the repository root; ../bin/pyt -t 900 tools/tu_data_base_diff.py CMD ...):
  files                 the TU records: name, spec, size, md5; retail record of the same name / spec (equal?); PC
                        record (pc-w name) size
  drm NAME [--types 7]  section table TU vs retail of NAME (generalbank.drm, globalsoundinfo.drm): equal / changed /
                        new / removed per type; for every changed section of the listed types an ALIGNED word diff
                        (difflib on 32-bit words; words at internal-relocation offsets become a pointer token, so a
                        grown section aligns) with u32 / float view, and for each changed run the PC words at the same
                        aligned place (PC section = Xbox id through work/generic/idmap.json, or --pc X:P pairs;
                        PC words u32-swapped for the comparison): PC=retail / PC=TU / PC other
  scripts NAME          type 8 sections TU vs retail: size, words changed at the same offset, strings only in the TU /
                        only in retail (a script's printable strings are its log texts and names)
  text NAME             a text record (tr8 objectlist.txt / unitlist.txt): lines only in the TU / only in retail
  bin NAME              any other record (objlist.dat, padshock/padshocklib.tfb): size, differing bytes, first ranges
  locals [SPEC]         local/locals.bin: per language TU vs retail - indices changed in place, indices appended;
                        with SPEC (e.g. fffff7e1 = English) every changed base index with retail / TU / PC text
Names: generalbank.drm, globalsoundinfo.drm, objectlist.txt (= \\tr8\\xenon-w\\objectlist.txt), padshock/padshocklib.tfb
"""
import sys, os, struct, math, hashlib, difflib, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc, load, L
from drm import cdrm_decode, sections_with_data
import drm_reloc as R

B = '../data/'
X = B + 'TombRaiderUnderworld_Patched/'
TU = X + 'TitleUpdate.000'
RETAIL = [X + 'layer1.000', X + 'layer2.000']
PC = [B + 'pc/patch.000', B + 'pc/bigfile.000']
BS = chr(92)
IDMAP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic', 'idmap.json')
SPEC_ALL = 0xffffffff


def xname(n):
    return (BS + 'tr8' + BS + 'xenon-w' + BS + n[4:]) if n.startswith('tr8/') else 'xenon-w' + BS + n.replace('/', BS)


def pname(n):
    return (BS + 'tr8' + BS + 'pc-w' + BS + n[4:]) if n.startswith('tr8/') else 'pc-w' + BS + n.replace('/', BS)


def short(n):
    return {'objectlist.txt': 'tr8/objectlist.txt', 'unitlist.txt': 'tr8/unitlist.txt', 'objlist.dat': 'tr8/objlist.dat'}.get(n, n)


def records(paths, endian, name, spec=None):
    """first archive (in order) that has the name -> {spec: bytes}"""
    for p in paths:
        a = Archive(p, endian)
        r = [x for x in a.find(crc(name)) if spec is None or x['spec'] == spec]
        if r: return {x['spec']: a.read(x) for x in r}, p
    return {}, None


def drm_sections(paths, endian, name):
    f, p = records(paths, endian, name, SPEC_ALL)
    if not f: return None
    return {(s['type'], s['id']): s for s in sections_with_data(cdrm_decode(f[SPEC_ALL], endian), endian)[1]}


def md5(b):
    return hashlib.md5(b).hexdigest()


def fl(u):
    f = struct.unpack('>f', struct.pack('>I', u))[0]
    return ('%.6g' % f) if math.isfinite(f) and (f == 0 or 1e-5 < abs(f) < 1e7) else '-'


def cmd_files(argv):
    xn = load(L + 'Tomb Raider Underworld (Xenon).txt')
    a = Archive(TU, 'be')
    print('# TitleUpdate.000: %d records' % len(a.idx))
    for r in a.idx:
        nm = xn.get(r['hash'], '%08x' % r['hash'])
        raw = a.read(r)
        ret, rp = records(RETAIL, 'be', nm, r['spec'])
        rr = ret.get(r['spec'])
        pn = nm.replace('xenon-w', 'pc-w')
        pcr, pp = records(PC, 'le', pn, r['spec'])
        pr = pcr.get(r['spec'])
        print('%-40s spec %08x TU %8d md5 %s | retail %s %s | PC %s' % (
            nm, r['spec'], len(raw), md5(raw)[:8],
            ('%d %s' % (len(rr), 'EQUAL' if rr == raw else 'differs')) if rr is not None else '-', os.path.basename(rp or ''),
            ('%d (%s)' % (len(pr), os.path.basename(pp))) if pr is not None else '-'))


def norm_words(s, endian):
    """32-bit words of a section; internal-relocation words -> ('P',) token, id-reference words -> ('I', type, id)"""
    d = s['data']; e = '>' if endian == 'be' else '<'
    n = len(d) // 4
    w = list(struct.unpack_from(e + '%dI' % n, d)) if n else []     # values: PC little-endian read = u32 swap
    if s['reloc']:
        rel = R.parse(s['reloc'], endian)
        for o, t in rel.internal:
            if o % 4 == 0 and o // 4 < n: w[o // 4] = ('P',)
        for t, o in list(rel.idref) + list(rel.idref_a):
            if o % 4 == 0 and o // 4 < n: w[o // 4] = ('I', t)
        for si, so, do in rel.external:
            if so % 4 == 0 and so // 4 < n: w[so // 4] = ('E',)
    return w, d[4 * n:]


def show(v):
    if isinstance(v, tuple): return {'P': '<ptr>', 'I': '<id t%d>' % v[1] if len(v) > 1 else '<id>', 'E': '<ext>'}[v[0]]
    return '%08x(%s)' % (v, fl(v))


def cmd_drm(argv):
    name = argv[0]; types = {7}
    pcpairs = {}
    if '--types' in argv: k = argv.index('--types'); types = {int(x) for x in argv[k + 1].split(',')}
    if '--pc' in argv:
        k = argv.index('--pc'); pcpairs = {int(a): int(b) for a, b in (x.split(':') for x in argv[k + 1].split(','))}
    tu = drm_sections([TU], 'be', xname(name)); rt = drm_sections(RETAIL, 'be', xname(name))
    pc = drm_sections(PC, 'le', pname(name))
    im = json.load(open(IDMAP)) if os.path.exists(IDMAP) else {}
    st = collections.Counter()
    rows = []
    for k in sorted(set(tu) | set(rt)):
        a, b = rt.get(k), tu.get(k)
        c = 'new' if a is None else 'removed' if b is None else 'equal' if (a['data'] == b['data'] and a['reloc'] == b['reloc']) else 'changed'
        st[(k[0], c)] += 1
        if c != 'equal': rows.append((k, c))
    print('# %s: TU %d sections, retail %d, PC %d' % (name, len(tu), len(rt), len(pc or {})))
    for t in sorted({t for t, c in st}):
        print('#   type %2d: %s' % (t, ', '.join('%s %d' % (c, st[(t, c)]) for c in ('equal', 'changed', 'new', 'removed') if st[(t, c)])))
    for k, c in rows:
        if k[0] not in types: continue
        a, b = rt.get(k), tu.get(k)
        pid = pcpairs.get(k[1], im.get(str(k[0]), {}).get(str(k[1])))
        p = pc.get((k[0], pid)) if pc and pid is not None else None
        print('\n%d:%d %s: retail %s B, TU %s B; PC %s:%s %s B' % (k[0], k[1], c, len(a['data']) if a else '-', len(b['data']) if b else '-',
                                                                k[0], pid, len(p['data']) if p else '-'))
        if a is None or b is None: continue
        wa, ta = norm_words(a, 'be'); wb, tb = norm_words(b, 'be')
        wp = norm_words(p, 'le')[0] if p else None
        rp = None
        if wp is not None:     # retail index -> PC index (aligned)
            rp = {}
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wa, wp, autojunk=False).get_opcodes():
                if tag == 'equal' or (tag == 'replace' and i2 - i1 == j2 - j1):
                    for d in range(i2 - i1): rp[i1 + d] = j1 + d
        sm = difflib.SequenceMatcher(None, wa, wb, autojunk=False)
        cnt = collections.Counter(); pcst = collections.Counter()
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal': continue
            cnt[tag] += 1
            print('  %-7s retail +0x%04x..+0x%04x (%d w)  TU +0x%04x..+0x%04x (%d w)' % (tag, 4 * i1, 4 * i2, i2 - i1, 4 * j1, 4 * j2, j2 - j1))
            for d in range(max(i2 - i1, j2 - j1)):
                if d >= 12: print('      ...'); break
                ra = wa[i1 + d] if i1 + d < i2 else None; tb_ = wb[j1 + d] if j1 + d < j2 else None
                pv = None
                if rp is not None and ra is not None and (i1 + d) in rp: pv = wp[rp[i1 + d]]
                if ra is not None and pv is not None:
                    pc_is = 'PC=retail' if pv == ra else 'PC=TU' if pv == tb_ else 'PC other ' + show(pv)
                    pcst[pc_is.split(' ')[0] + (' ' + pc_is.split(' ')[1] if pc_is.startswith('PC other') else '')] += 1
                else: pc_is = 'PC: no aligned word'
                print('      %-20s -> %-20s  %s' % (show(ra) if ra is not None else '', show(tb_) if tb_ is not None else '', pc_is))
        print('  runs %s; PC at changed retail words: %s; tail bytes retail %d TU %d' % (dict(cnt), dict(pcst), len(ta), len(tb)))


def strings(d, n=6):
    out, cur = [], b''
    for x in d:
        if 32 <= x < 127: cur += bytes([x])
        else:
            if len(cur) >= n: out.append(cur.decode())
            cur = b''
    if len(cur) >= n: out.append(cur.decode())
    return out


def cmd_scripts(argv):
    name = argv[0]
    tu = drm_sections([TU], 'be', xname(name)); rt = drm_sections(RETAIL, 'be', xname(name))
    n = 0
    for k in sorted(set(tu) | set(rt)):
        if k[0] != 8: continue
        a, b = rt.get(k), tu.get(k)
        if a and b and a['data'] == b['data'] and a['reloc'] == b['reloc']: continue
        n += 1
        if a is None or b is None:
            s = b or a
            print('8:%-6d %s %d B  strings %s' % (k[1], 'new' if a is None else 'removed', len(s['data']), strings(s['data'])[:8])); continue
        da, db = a['data'], b['data']
        m = min(len(da), len(db)) // 4
        wd = sum(1 for i in range(m) if da[4 * i:4 * i + 4] != db[4 * i:4 * i + 4])
        sa, sb = set(strings(da)), set(strings(db))
        print('8:%-6d %6d -> %6d B  same-offset words differ %5d  reloc %s  TU-only strings %s  retail-only strings %s' % (
            k[1], len(da), len(db), wd, 'equal' if a['reloc'] == b['reloc'] else 'differs', sorted(sb - sa)[:10], sorted(sa - sb)[:10]))
    print('# %d changed / new / removed scripts' % n)


def cmd_text(argv):
    nm = short(argv[0])
    t, _ = records([TU], 'be', xname(nm)); r, rp = records(RETAIL, 'be', xname(nm)); p, pp = records(PC, 'le', pname(nm))
    t, r, p = t.get(SPEC_ALL, b''), r.get(SPEC_ALL, b''), p.get(SPEC_ALL, b'')
    lt = t.decode('latin-1').splitlines(); lr = r.decode('latin-1').splitlines(); lp = p.decode('latin-1').splitlines()
    print('# %s: TU %d lines, retail %d (%s), PC %d (%s)' % (nm, len(lt), len(lr), os.path.basename(rp or ''), len(lp), os.path.basename(pp or '')))
    sp = set(x.strip() for x in lp)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, lr, lt, autojunk=False).get_opcodes():
        if tag == 'equal': continue
        print('  %s retail %d..%d TU %d..%d' % (tag, i1 + 1, i2, j1 + 1, j2))
        for x in lr[i1:i2][:15]: print('    - %s%s' % (x, '   [in PC]' if x.strip() in sp else ''))
        for x in lt[j1:j2][:15]: print('    + %s%s' % (x, '   [in PC]' if x.strip() in sp else ''))


def cmd_bin(argv):
    nm = short(argv[0])
    t, _ = records([TU], 'be', xname(nm)); r, rp = records(RETAIL, 'be', xname(nm)); p, pp = records(PC, 'le', pname(nm))
    t, r, p = t.get(SPEC_ALL, b''), r.get(SPEC_ALL, b''), p.get(SPEC_ALL, b'')
    print('# %s: TU %d B, retail %d B (%s), PC %d B (%s); md5 TU %s retail %s PC %s' % (
        nm, len(t), len(r), os.path.basename(rp or ''), len(p), os.path.basename(pp or ''), md5(t)[:8], md5(r)[:8], md5(p)[:8] if p else '-'))
    sm = difflib.SequenceMatcher(None, r, t, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes()[:40]:
        if tag == 'equal': continue
        print('  %-7s retail 0x%x..0x%x (%d B)  TU 0x%x..0x%x (%d B)  TU strings %s' % (tag, i1, i2, i2 - i1, j1, j2, j2 - j1, strings(t[max(0, j1 - 32):j2 + 32], 4)[:6]))


def cmd_objlist(argv):
    import objlists as OL
    nm = short('objlist.dat')
    t, _ = records([TU], 'be', xname(nm)); r, _ = records(RETAIL, 'be', xname(nm))
    ob = {}
    for which, paths in (('TU', [TU]), ('retail', RETAIL)):
        b, _ = records(paths, 'be', xname(short('objectlist.txt')))
        ob[which] = OL.read_objectlist(b[SPEC_ALL])
    rt, _ = OL.read_objlist(r[SPEC_ALL], 'be'); tt, _ = OL.read_objlist(t[SPEC_ALL], 'be')
    R_, T_ = dict(rt), dict(tt)
    print('# objlist.dat units: retail %d, TU %d; only TU %d, only retail %d' % (
        len(R_), len(T_), len(set(T_) - set(R_)), len(set(R_) - set(T_))))
    for u in sorted(set(T_) - set(R_)): print('  only TU   %s (%d objects)' % (u, len(T_[u])))
    for u in sorted(set(R_) - set(T_)): print('  only retail %s (%d objects)' % (u, len(R_[u])))
    same = 0
    for u in sorted(set(R_) & set(T_)):
        a = [ob['retail'].get(i, '?%d' % i) for i in R_[u]]; b = [ob['TU'].get(i, '?%d' % i) for i in T_[u]]
        if a == b: same += 1; continue
        print('  changed   %s: +%s -%s' % (u, sorted(set(b) - set(a)), sorted(set(a) - set(b))))
    print('# units in both with the same object names: %d' % same)


def cmd_locals(argv):
    import locals as LC
    want = int(argv[0], 16) if argv else None
    t, _ = records([TU], 'be', xname('local/locals.bin')); r, _ = records(RETAIL, 'be', xname('local/locals.bin'))
    p, _ = records(PC, 'le', pname('local/locals.bin'))
    for spec in sorted(t):
        lt, st, _ = LC.parse(t[spec], 'be'); lr, sr, _ = LC.parse(r[spec], 'be')
        sp = LC.parse(p[spec], 'le')[1] if spec in p else []
        ch = [i for i in range(min(len(st), len(sr))) if st[i] != sr[i]]
        print('spec %08x lang %d: retail %d strings, TU %d (+%d appended), %d base indices changed in place; PC %d strings' % (
            spec, lt, len(sr), len(st), len(st) - len(sr), len(ch), len(sp)))
        if want == spec:
            pc_set = set(sp)
            for i in ch:
                print('  [%d] retail %r\n         TU %r   (in the PC table: TU text %s, retail text %s)' % (
                    i, sr[i][:160], st[i][:160], st[i] in pc_set, sr[i] in pc_set))


def main(argv):
    if not argv: sys.exit(__doc__)
    {'files': cmd_files, 'drm': cmd_drm, 'scripts': cmd_scripts, 'text': cmd_text, 'bin': cmd_bin, 'objlist': cmd_objlist,
     'locals': cmd_locals}[argv[0]](argv[1:])


if __name__ == '__main__':
    main(sys.argv[1:])
