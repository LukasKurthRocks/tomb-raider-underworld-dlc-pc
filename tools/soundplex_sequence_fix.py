"""SoundPlex Sequence nodes (type 10): the REPEAT byte at data +0xc (F5 groan loop, 2026-11-05). Read-only except `fix`.

Engine (both sides decompiled, same logic):
  PC tru+0x18e070 (walker 0x5920b0 case 10, class vtbl 0x85127c): obj+0x20 = data; if u32 data+0 (child count) > 0:
     obj+0x18 = movsx BYTE [data+0xc] (repeat), obj+0x14 = -1.
  PC tru+0x193720 (vtbl[1], update) / Xbox TU 0x822457f0 (helper of vtbl[1] 0x822455d0): idx = obj+0x14 + 1;
     passes = idx / count; next child = children[idx % count] when passes < repeat OR repeat == 0, else the
     sequence ends (obj+0x14 = -2).  repeat 0 = play the children for ever.
  Xbox TU 0x8224277c (inlined in the TU walker) / retail 0x822442ac: `lbz r11, 0xc(r11); extsb r8, r11;
     stw r8, 0x18(r3)` - the Xbox reads the FIRST byte of the big-endian word data+0xc.
  => the PC must carry the same byte at data+0xc: an Xbox word `01 00 00 00` (repeat 1) must stay `01 00 00 00`;
     the u32 swap `00 00 00 01` gives repeat 0 = endless.

Data: data = {+0 u32 count, +4 ptr -> count node ptrs, +8 ptr, +0xc s8 repeat + 3 bytes}. Nodes are found as in
tools/soundplex_nodes.py (internal reloc at o, BE type word 0..13 at o-4), Sequence shape as in seq_nodes().

Rule (pipeline step `seqrepeat` of tools/dlc_struct_fixes.py since 2026-11-05, WINDOWS_REBUILD finding 49): the whole
word data+0xc is RAW on the PC (= the Xbox bytes). Base proof (`proof`): every informative base pair keeps the word
raw, none holds another byte order; that includes the bytes +0xe / +0xf (pairs whose Xbox bytes +0xe / +0xf differ).
A PC word that is a byte order of the Xbox word (u32 / u16u16 / u8u8u16) is set to the Xbox bytes; a PC word that is
no byte order of it cannot be explained by the rule (UNEXPECTED: the step stops, the gate fails). Sections are paired
by position (tools/converter_faults_fix.pairs_by_position); a pair with another id is a renumbered base DTP (the PC
game's own section) and is left alone, as a pair whose size / internal relocations differ.

Modes (from the repository root):
  ../bin/pyt -t 1800 tools/soundplex_sequence_fix.py proof
        base-game Xbox / PC pairs (work/generic/store.pkl, same size + same internal relocs): byte class of the
        Sequence data words +0x0 / +0x4 / +0x8 / +0xc against PROOF_EXPECT; exit 1 when a count differs or any
        pair contradicts the raw rule (`calibrate` = the same output, always exit 0)
  ../bin/pyt -t 900 tools/soundplex_sequence_fix.py scan LIST_OR_DIR [--all] [--pack PACK] [--report R.json]
  ../bin/pyt -t 900 tools/soundplex_sequence_fix.py scan --profile PROFILE.json [--base DIR] [--all] [--report R.json]
        DLC DRMs (a folder, or a text file with one absolute .drm path per line, e.g. the output of
        tools/profile_last_source.py paths PROFILE), or a single .drm; several joined with ',' (later name wins);
        --profile: what a test profile ends up installing (tools/objdata_texlist_check.profile_files: last tree
        source of every .drm, with --base the files of DIR no tree brings). Every Sequence node, Xbox word +0xc vs
        PC word, repeat byte the PC engine reads; only wrong ones unless --all.
        Xbox source: --pack PACK = that pack first (convert_dlc.raw_dlc, as the pipeline); without --pack every pack
        that holds the name is tried and the copy with the most id-equal pairs wins (finding 38: 10 names exist in
        pack10 and pack11 with different content). Exit 1 when any word is wrong or unexpected (the pipeline gate)
  ../bin/pyt -t 900 tools/soundplex_sequence_fix.py fix LIST_OR_DIR OUTDIR [NAME ...] [--pack PACK]
        writes the DRMs with wrong words to OUTDIR (only the +0xc words, set to the Xbox bytes), re-reads every
        written file and proves that nothing else changed; md5.tsv + log next to OUTDIR (in its parent folder, so
        nothing but DRMs lands in a mods tree)
Library (tools/dlc_struct_fixes.py step seqrepeat): plan(XD, PD), fix_drm(XD, raw) -> (new raw or None, changes, info).
"""
import sys, os, struct, collections, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_write as DW
from soundplex_nodes import nodes

PERMS = {'raw': (0, 1, 2, 3), 'u32': (3, 2, 1, 0), 'u16u16': (1, 0, 3, 2), 'u8u8u16': (0, 1, 3, 2)}
FIXABLE = ('u32', 'u16u16', 'u8u8u16')       # byte orders of the Xbox word the converter may have written
SEQ = 10
FIELDS = (0x0, 0x4, 0x8, 0xc)
# base proof, measured 2026-11-05 (agent F5, logs f5m_seq_calibrate.txt; again by `proof`, agent F5/F25 pipeline)
PROOF_EXPECT = {'pairs': 90, 'nodes': 172, 'count_u32': 172, 'pointers': 344,
                'raw_only': 71, 'raw_or_u8u8u16': 23, 'uninformative': 78, 'contradicting': 0, 'ef_raw': 71}


def classes(xw, pw):
    return frozenset(n for n, pm in PERMS.items() if bytes(xw[i] for i in pm) == pw)


def word_class(xw, pw):
    """'ok' (raw), one of FIXABLE (first match), or 'other' (no byte order of the Xbox word: unexpected)"""
    if pw == xw: return 'ok'
    for n in FIXABLE:
        if bytes(xw[i] for i in PERMS[n]) == pw: return n
    return 'other'


def seq_nodes(xd, xreloc):
    """type-10 nodes whose data has the Sequence shape the constructor / update use: +0 u32 count 1..256 (no
    pointer), +4 pointer to `count` pointers that each point at a node {BE u32 type 0..13, pointer}, +0xc no
    pointer (the repeat byte)"""
    nd, slots = nodes(xd, xreloc)
    it = dict(R.parse(xreloc, 'be').internal)
    out = []
    for t, tg in nd:
        if t != SEQ or tg + 0x10 > len(xd) or tg in slots or (tg + 0xc) in slots: continue
        cnt = struct.unpack_from('>I', xd, tg)[0]
        arr = it.get(tg + 4)
        if not 1 <= cnt <= 256 or arr is None or arr + 4 * cnt > len(xd): continue
        ok = True
        for j in range(cnt):
            ch = it.get(arr + 4 * j)
            if ch is None or ch + 8 > len(xd) or struct.unpack_from('>I', xd, ch)[0] > 13 or (ch + 4) not in it:
                ok = False; break
        if ok: out.append(tg)
    return out, slots


# ---------------------------------------------------------------- base proof
def base_stats():
    import dtpid_sweep as DS
    st, ids = DS.ctx()
    stat = collections.defaultdict(collections.Counter)
    rep = collections.Counter(); nseq = npairs = 0
    examples = []; contra = []
    # word byte j kept raw where every other byte order (FIXABLE) would put another value there - the pair tells the
    # byte apart; 'ef' = Xbox bytes +0xe != +0xf and PC raw (excludes the u8u8u16 swap of dlc1_uo_crushers DTP 20247)
    byte_proven = collections.Counter()
    for (t, x), xb in st['xb_store'].items():
        if t != 7: continue
        p = ids.base[7].get(x); pc = st['pc_store'].get((7, p)) if p is not None else None
        if pc is None or len(pc['data']) != len(xb['data']): continue
        if dict(R.parse(pc['reloc'], 'le').internal) != dict(R.parse(xb['reloc'], 'be').internal): continue
        sq, slots = seq_nodes(xb['data'], xb['reloc'])
        if not sq: continue
        npairs += 1
        for tg in sq:
            nseq += 1
            xd, pd = xb['data'], pc['data']
            rep[xd[tg + 0xc]] += 1
            for k in FIELDS:
                q = tg + k
                if q in slots: stat[k]['pointer'] += 1; continue
                c = classes(xd[q:q + 4], pd[q:q + 4])
                stat[k]['uninformative' if len(c) == len(PERMS) else ('+'.join(sorted(c)) if c else 'none')] += 1
            q = tg + 0xc; xw, pw = xd[q:q + 4], pd[q:q + 4]
            if 'raw' not in classes(xw, pw): contra.append((x, p, tg, xw.hex(), pw.hex()))
            elif xw == pw:
                for j in range(4):
                    moved = [PERMS[n][j] for n in FIXABLE if PERMS[n][j] != j]
                    if moved and all(xw[i] != xw[j] for i in moved): byte_proven[j] += 1
                if xw[2] != xw[3]: byte_proven['ef'] += 1
            if len(examples) < 12:
                examples.append((x, p, tg, xd[tg + 0xc:tg + 0x10].hex(), pd[tg + 0xc:tg + 0x10].hex()))
    return dict(pairs=npairs, nodes=nseq, stat=stat, rep=rep, examples=examples, contra=contra, byte_proven=byte_proven)


def proof(strict=True):
    b = base_stats(); s = b['stat']
    got = {'pairs': b['pairs'], 'nodes': b['nodes'], 'count_u32': s[0x0].get('u32', 0),
           'pointers': s[0x4].get('pointer', 0) + s[0x8].get('pointer', 0),
           'raw_only': s[0xc].get('raw', 0), 'raw_or_u8u8u16': s[0xc].get('raw+u8u8u16', 0),
           'uninformative': s[0xc].get('uninformative', 0), 'contradicting': len(b['contra'])}
    print('base pairs with Sequence nodes', b['pairs'], 'Sequence nodes', b['nodes'])
    for k in FIELDS:
        print('data+0x%x classes %s' % (k, dict(s[k].most_common())))
    print('Xbox repeat byte (data+0xc byte 0) values', dict(sorted(b['rep'].items())))
    print('word +0xc byte by byte: pairs that keep the byte raw where every other byte order would put another value '
          'there %s; Xbox +0xe != +0xf and PC raw (u8u8u16 excluded): %d' % (
              ', '.join('+0x%x: %d' % (0xc + j, b['byte_proven'][j]) for j in range(4)), b['byte_proven']['ef']))
    for e in b['examples']: print('  example Xbox DTP %d / PC DTP %d node data +%#x: Xbox %s PC %s' % e)
    for c in b['contra'][:20]: print('  CONTRADICTS Xbox DTP %d / PC DTP %d node data +%#x: Xbox %s PC %s' % c)
    got['ef_raw'] = b['byte_proven']['ef']
    ok = got == PROOF_EXPECT
    print('rule data+0xc raw: %s  %s (expected %s)' % ('PROVEN' if ok else 'FAILED', got, PROOF_EXPECT))
    print('proof: %s' % ('the raw rule holds on every base pair' if ok else 'FAILED'))
    return 0 if ok or not strict else 1


# ---------------------------------------------------------------- one DRM
def plan(XD, PD):
    """XD / PD: drm_write.Drm (Xbox big-endian / PC little-endian) -> dict(rows=[(PC section index, DTP id, node data
    offset, child count, Xbox word, PC word, class)], sections, base_mapped, layout=[ids], unpaired=[ids])"""
    import converter_faults_fix as CF
    pairs = CF.pairs_by_position(XD, PD)
    seen = set()
    res = dict(rows=[], sections=0, base_mapped=0, layout=[], unpaired=[])
    for k, x, p in pairs:
        seen.add(id(x))
        if x.type != 7: continue
        xd = bytes(x.data)
        sq, slots = seq_nodes(xd, bytes(x.reloc))
        if not sq: continue
        res['sections'] += 1
        if x.id != p.id: res['base_mapped'] += 1; continue     # renumbered base DTP: the PC game's own section
        pd = bytes(p.data)
        if len(pd) != len(xd) or dict(R.parse(bytes(p.reloc), 'le').internal) != dict(R.parse(bytes(x.reloc), 'be').internal):
            res['layout'].append(x.id); continue
        for tg in sq:
            q = tg + 0xc
            xw, pw = xd[q:q + 4], pd[q:q + 4]
            res['rows'].append((k, x.id, tg, struct.unpack_from('>I', xd, tg)[0], xw, pw, word_class(xw, pw)))
    for x in XD.sections:
        if id(x) in seen or x.type != 7: continue
        if seq_nodes(bytes(x.data), bytes(x.reloc))[0]: res['unpaired'].append(x.id)
    return res


def fix_drm(XD, raw):
    """-> (new raw or None, changes [(section index, offset, old, new, DTP id)], plan info). Raises SystemExit on an
    UNEXPECTED word (no byte order of the Xbox word) - nothing is guessed. The written bytes are proven: the decoded
    DRM differs only in the planned bytes, file / section headers and relocations identical, re-plan 0 words."""
    PD = DW.read(raw, 'le')
    info = plan(XD, PD)
    bad = [r for r in info['rows'] if r[6] == 'other']
    if bad:
        raise SystemExit('seqrepeat: %d UNEXPECTED word(s) (no byte order of the Xbox word): %s' % (len(bad), ', '.join(
            'DTP %d +%#x Xbox %s PC %s' % (r[1], r[2] + 0xc, r[4].hex(), r[5].hex()) for r in bad[:10])))
    todo = [r for r in info['rows'] if r[6] in FIXABLE]
    if not todo: return None, [], info
    changes = []
    for k, sid, tg, cnt, xw, pw, cls in todo:
        s = PD.sections[k]; b = bytearray(s.data); q = tg + 0xc
        assert bytes(b[q:q + 4]) == pw
        b[q:q + 4] = xw; s.data = bytes(b)
        changes.append((k, q, pw, xw, sid))
    new = PD.write('le')
    if raw[:4] == b'CDRM': new = DW.cdrm_encode(new, 'le')
    verify(raw, new, changes, XD)
    return new, changes, info


def verify(raw, new, changes, XD):
    """assert: only the planned bytes differ, headers / relocations / names identical, re-plan finds 0 words"""
    A, B = DW.read(raw, 'le'), DW.read(new, 'le')
    assert len(A.sections) == len(B.sections) and A.names == B.names and A.pad == B.pad, 'file layout changed'
    planned = {(k, q + j) for k, q, a, b, sid in changes for j in range(4) if a[j] != b[j]}
    got = set()
    for k, (a, b) in enumerate(zip(A.sections, B.sections)):
        assert (a.type, a.id, a.flags, a.ver, a.spec, a.pad, bytes(a.reloc), len(a.data)) == \
               (b.type, b.id, b.flags, b.ver, b.spec, b.pad, bytes(b.reloc), len(b.data)), 'section %d header changed' % k
        if a.data != b.data: got |= {(k, i) for i in range(len(a.data)) if a.data[i] != b.data[i]}
    assert got == planned, '%d bytes differ, %d planned' % (len(got), len(planned))
    again = [r for r in plan(XD, B)['rows'] if r[6] != 'ok']
    assert not again, 're-plan finds %d words' % len(again)
    return len(got)


# ---------------------------------------------------------------- files / Xbox sources
def file_list(spec):
    """folder, list file (one .drm path per line) or a single .drm; several joined with ',' (a later name wins)"""
    if ',' in spec:
        by = {}
        for part in spec.split(','):
            for p in file_list(part): by[os.path.basename(p).lower()] = p
        return sorted(by.values(), key=lambda p: os.path.basename(p).lower())
    if spec.lower().endswith('.drm') and os.path.isfile(spec): return [spec]
    if os.path.isdir(spec):
        out = []
        for r, _, fs in os.walk(spec):
            out += [os.path.join(r, f) for f in fs if f.lower().endswith('.drm')]
        return sorted(out)
    return [l.strip() for l in open(spec, encoding='utf-8-sig') if l.strip().lower().endswith('.drm')]


def rel_names(path):
    """Xbox archive names to try: the path below the last mods folder (sub folders such as cinstream), then the bare name"""
    p = path.replace('\\', '/'); low = p.lower()
    out = []
    if '/mods/' in low: out.append(p[low.rindex('/mods/') + 6:].replace('/', '\\'))
    if os.path.basename(p) not in out: out.append(os.path.basename(p))
    return out


def xbox_candidates(path, pack):
    """[(Xbox Drm, pack label)]: with pack the first match of convert_dlc.raw_dlc with that pack first (the pipeline's
    choice); without, the copy of every pack that holds the name"""
    import convert_dlc as CD
    from drm import cdrm_decode
    saved = os.environ.get('TRUDLC_PACK_FIRST')
    out, packs = [], []
    try:
        for first in ([pack] if pack else [p.split('/')[-1][:-4] for p in CD.PACKS]):
            os.environ['TRUDLC_PACK_FIRST'] = first
            for n in rel_names(path):
                raw, pk = CD.raw_dlc(n)
                if raw is not None: break
            if raw is None or pk in packs: continue
            packs.append(pk)
            out.append((DW.read(cdrm_decode(raw, 'be'), 'be'), pk.split('/')[-1]))
    finally:
        if saved is None: os.environ.pop('TRUDLC_PACK_FIRST', None)
        else: os.environ['TRUDLC_PACK_FIRST'] = saved
    return out


def check_file(path, pack=None):
    """-> (status, plan info or None, Xbox Drm or None)"""
    cands = xbox_candidates(path, pack)
    if not cands: return 'no Xbox source', None, None
    PD = DW.read(open(path, 'rb').read(), 'le')
    best = None
    for XD, pk in cands:
        info = plan(XD, PD)
        score = sum(1 for r in info['rows']) - len(info['layout']) - len(info['unpaired'])
        import converter_faults_fix as CF
        same = sum(1 for k, x, p in CF.pairs_by_position(XD, PD) if x.id == p.id and len(x.data) == len(p.data))
        if best is None or (same, score) > best[0]: best = ((same, score), XD, pk, info)
    _, XD, pk, info = best
    return 'ok (%s%s)' % (pk, '' if len(cands) == 1 else ', best of %s' % '/'.join(c[1] for c in cands)), info, XD


# ---------------------------------------------------------------- modes
def scan(paths, show_all, pack=None, label=None):
    tot = collections.Counter(); wrong_files = []; lines = []; repeat_files = []
    for path in paths:
        st, info, XD = check_file(path, pack)
        tot['files'] += 1
        if info is None:
            tot['no_xbox_source'] += 1
            if show_all: print('%s: %s' % (path, st))
            continue
        rows = info['rows']
        bad = [r for r in rows if r[6] != 'ok']
        tot['sequence_nodes'] += len(rows); tot['base_mapped_sections'] += info['base_mapped']
        tot['layout_differs_sections'] += len(info['layout']); tot['unpaired_sections'] += len(info['unpaired'])
        tot['wrong'] += sum(1 for r in bad if r[6] in FIXABLE)
        # wrong_repeat: the byte the engine reads (+0xc) differs from the Xbox repeat; the rest of the wrong words
        # differ only in +0xd..+0xf (no known reader - e.g. dlc1_uo_crushers DTP 20247), still wrong by the rule
        tot['wrong_repeat'] += sum(1 for r in bad if r[6] in FIXABLE and r[4][0] != r[5][0])
        tot['unexpected'] += sum(1 for r in bad if r[6] == 'other')
        for r in bad: tot['class_' + r[6]] += 1
        tot['repeat_0_to_nonzero'] += sum(1 for r in bad if r[5][0] == 0 and r[4][0] != 0)
        if bad: tot['files_wrong'] += 1; wrong_files.append(path.replace('\\', '/'))
        if any(r[6] == 'other' or r[4][0] != r[5][0] for r in bad): repeat_files.append(path.replace('\\', '/'))
        if bad or (show_all and (rows or info['layout'] or info['unpaired'])):
            print('%s: %s, %d Sequence nodes, %d not ok%s%s%s' % (
                path, st, len(rows), len(bad),
                (', %d base-mapped section(s) left alone' % info['base_mapped']) if info['base_mapped'] else '',
                (', layout differs (not paired): DTP %s' % info['layout']) if info['layout'] else '',
                (', no PC section by position: DTP %s' % info['unpaired']) if info['unpaired'] else ''))
            for r in (rows if show_all else bad):
                ln = '   DTP %d node data +%#06x count %d: Xbox %s (repeat %d) PC %s (engine reads repeat %d) %s' % (
                    r[1], r[2], r[3], r[4].hex(), struct.unpack('b', r[4][:1])[0], r[5].hex(),
                    struct.unpack('b', r[5][:1])[0], 'ok' if r[6] == 'ok' else ('UNEXPECTED (no byte order)' if r[6] == 'other' else 'WRONG ' + r[6]))
                print(ln); lines.append('%s %s' % (os.path.basename(path), ln.strip()))
    res = 'FAIL' if tot['wrong'] or tot['unexpected'] else 'ok'
    print('TOTAL%s %s' % ((' ' + label) if label else '', dict(tot)))
    print('scan: %s' % res)
    return res, dict(tot), wrong_files, lines, repeat_files


def fix(spec, outdir, names, pack):
    os.makedirs(outdir, exist_ok=True)
    top = os.path.dirname(os.path.abspath(outdir))          # log + md5.tsv next to mods\, never inside it
    log = open(os.path.join(top, 'soundplex_sequence_fix.log.txt'), 'w', encoding='utf-8', newline='\r\n')
    md5s = ['md5\tpath']
    for path in file_list(spec):
        name = os.path.basename(path)
        if names and name not in names: continue
        st, info, XD = check_file(path, pack)
        if info is None or not any(r[6] != 'ok' for r in info['rows']): continue
        raw = open(path, 'rb').read()
        new, changes, info = fix_drm(XD, raw)
        if new is None: continue
        D = DW.read(raw, 'le')
        for k, q, pw, xw, sid in changes:
            line = '%s DTP %d (section %d) +%#07x: %s -> %s (Sequence repeat %d -> %d)' % (
                name, sid, k, q, pw.hex(), xw.hex(), struct.unpack('b', pw[:1])[0], struct.unpack('b', xw[:1])[0])
            print(line); log.write(line + '\n')
        dst = os.path.join(outdir, name)
        open(dst, 'wb').write(new)
        ndiff = verify(raw, open(dst, 'rb').read(), changes, XD)
        h = hashlib.md5(new).hexdigest(); sh = hashlib.sha256(new).hexdigest()
        line = '%s: %d words, %d bytes differ from %s (all inside the patched words), %d sections identical otherwise; md5 %s sha256 %s' % (
            name, len(changes), ndiff, path, len(D.sections), h, sh)
        print(line); log.write(line + '\n')
        md5s.append('%s\t%s' % (h, name))
    open(os.path.join(top, 'md5.tsv'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md5s) + '\n')
    log.close()
    print('files written', len(md5s) - 1)


def opt(a, key, many=False):
    vals = []
    while key in a:
        k = a.index(key); vals.append(a[k + 1]); del a[k:k + 2]
        if not many: break
    return vals if many else (vals[0] if vals else None)


def main(a):
    if not a: sys.exit(__doc__)
    pack = opt(a, '--pack'); report = opt(a, '--report'); profiles = opt(a, '--profile', True); base = opt(a, '--base')
    show_all = '--all' in a
    a = [x for x in a if x != '--all']
    if a[0] == 'calibrate': return proof(strict=False)
    if a[0] == 'proof': return proof()
    if a[0] == 'scan' and (len(a) >= 2 or profiles):
        out = {'result': 'ok', 'scans': []}
        if profiles:
            import glob, objdata_texlist_check as TLC
            todo = []
            for pat in profiles: todo += sorted(glob.glob(pat)) or [pat]
            for p in todo:
                fl, nbase = TLC.profile_files(p, base)
                print('PROFILE %s: %d .drm files (%d from the base %s)' % (os.path.basename(p), len(fl), nbase, base or '-'))
                r, tot, wf, lines, rf = scan(fl, show_all, pack, os.path.basename(p))
                print('PROFILE %s: %s, Sequence nodes %d, wrong %d (repeat byte %d), unexpected %d, files %s; '
                      'repeat byte wrong in %s' % (
                          os.path.basename(p), r, tot.get('sequence_nodes', 0), tot.get('wrong', 0),
                          tot.get('wrong_repeat', 0), tot.get('unexpected', 0),
                          ', '.join(os.path.basename(f) for f in wf) or '-', ', '.join(os.path.basename(f) for f in rf) or '-'))
                out['scans'].append(dict(profile=p, base=base, result=r, totals=tot, files=wf, repeat_files=rf, lines=lines))
        else:
            r, tot, wf, lines, rf = scan(file_list(a[1]), show_all, pack)
            out['scans'].append(dict(spec=a[1], pack=pack, result=r, totals=tot, files=wf, repeat_files=rf, lines=lines))
        out['result'] = 'fail' if any(s['result'] != 'ok' for s in out['scans']) else 'ok'
        if report:
            os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
            json.dump(out, open(report, 'w', encoding='utf-8'), indent=1)
        return 1 if out['result'] != 'ok' else 0
    if a[0] == 'fix' and len(a) >= 3: fix(a[1], a[2], set(a[3:]), pack); return 0
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
