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
tools/soundplex_nodes.py (internal reloc at o, BE type word 0..13 at o-4).

Modes (from the repository root):
  ../bin/pyt -t 900 tools/soundplex_sequence_fix.py calibrate
        base-game Xbox / PC pairs (work/generic/store.pkl, same size + same internal relocs): byte class of the
        Sequence data words +0x0 / +0x4 / +0x8 / +0xc (raw / u32 / u16u16 / u8u8u16), Xbox repeat values
  ../bin/pyt -t 900 tools/soundplex_sequence_fix.py scan LIST_OR_DIR [--all]
        DLC DRMs (a folder, or a text file with one absolute .drm path per line, e.g. the output of
        tools/profile_last_source.py paths PROFILE), or a single .drm; several joined with ',' (later name wins):
        every Sequence node, Xbox word +0xc vs PC word, repeat byte the
        PC engine reads; only wrong ones unless --all
  ../bin/pyt -t 900 tools/soundplex_sequence_fix.py fix LIST_OR_DIR OUTDIR [NAME ...]
        writes the DRMs with wrong words to OUTDIR (only the +0xc words, set to the Xbox bytes = proven class
        'raw'), re-reads every written file and proves that nothing else changed; md5.tsv + log next to OUTDIR
        (in its parent folder, so nothing but DRMs lands in a mods tree)
"""
import sys, os, struct, collections, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('TRUDLC_PACK_FIRST', 'pack11')
import drm_reloc as R, drm_write as DW
from soundplex_nodes import nodes

PERMS = {'raw': (0, 1, 2, 3), 'u32': (3, 2, 1, 0), 'u16u16': (1, 0, 3, 2), 'u8u8u16': (0, 1, 3, 2)}
SEQ = 10
FIELDS = (0x0, 0x4, 0x8, 0xc)


def classes(xw, pw):
    return frozenset(n for n, pm in PERMS.items() if bytes(xw[i] for i in pm) == pw)


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


def calibrate():
    import dtpid_sweep as DS
    st, ids = DS.ctx()
    stat = collections.defaultdict(collections.Counter)
    rep = collections.Counter(); nseq = npairs = 0
    examples = []
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
            if len(examples) < 12:
                examples.append((x, p, tg, xd[tg + 0xc:tg + 0x10].hex(), pd[tg + 0xc:tg + 0x10].hex()))
    print('base pairs with Sequence nodes', npairs, 'Sequence nodes', nseq)
    for k in FIELDS:
        print('data+0x%x classes %s' % (k, dict(stat[k].most_common())))
    print('Xbox repeat byte (data+0xc byte 0) values', dict(sorted(rep.items())))
    for e in examples: print('  example Xbox DTP %d / PC DTP %d node data +%#x: Xbox %s PC %s' % e)


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


def xsecs(name):
    from convert_dlc import raw_dlc
    from drm import cdrm_decode, sections_with_data
    raw, pk = raw_dlc(name)
    if raw is None: return None, None
    return sections_with_data(cdrm_decode(raw, 'be'), 'be')[1], pk


def check_file(path):
    """-> (status, [(dtp id, section index, node data off, count, xbox word, pc word, verdict)])"""
    name = os.path.basename(path)
    xs, pk = xsecs(name)
    if xs is None: return 'no Xbox source', []
    D = DW.read(open(path, 'rb').read(), 'le')
    pool = collections.defaultdict(list)
    for i, s in enumerate(D.sections): pool[s.type, s.id].append(i)
    out = []
    for s in xs:
        if s['type'] != 7 or s['data'] is None: continue
        sq, slots = seq_nodes(s['data'], s['reloc'])
        lst = pool.get((7, s['id']))
        if not lst: continue                       # base ids are renumbered: those sections come from the PC game
        i = lst.pop(0)
        if not sq: continue
        pd = D.sections[i].data; xd = s['data']
        if len(pd) != len(xd) or dict(R.parse(D.sections[i].reloc, 'le').internal) != dict(R.parse(s['reloc'], 'be').internal):
            out.append((s['id'], i, None, None, None, None, 'layout differs - not paired')); continue
        for tg in sq:
            q = tg + 0xc
            cnt = struct.unpack_from('>I', xd, tg)[0]
            xw, pw = xd[q:q + 4], pd[q:q + 4]
            verdict = 'ok' if pw == xw else ('WRONG u32 swap' if pw == xw[::-1] else 'WRONG other')
            out.append((s['id'], i, tg, cnt, xw, pw, verdict))
    return 'ok (%s)' % pk, out


def scan(spec, show_all):
    tot = collections.Counter()
    for path in file_list(spec):
        st, rows = check_file(path)
        bad = [r for r in rows if r[6] != 'ok']
        tot['files'] += 1; tot['sequences'] += sum(1 for r in rows if r[2] is not None)
        tot['wrong'] += sum(1 for r in bad if r[6].startswith('WRONG'))
        if bad: tot['files_wrong'] += 1
        if not rows and not show_all: continue
        if bad or show_all:
            print('%s: %s, %d Sequence nodes, %d not ok' % (path, st, len(rows), len(bad)))
            for r in (rows if show_all else bad):
                if r[2] is None: print('   DTP %d: %s' % (r[0], r[6])); continue
                print('   DTP %d node data +%#06x count %d: Xbox %s (repeat %d) PC %s (engine reads repeat %d) %s' % (
                    r[0], r[2], r[3], r[4].hex(), struct.unpack('b', r[4][:1])[0], r[5].hex(),
                    struct.unpack('b', r[5][:1])[0], r[6]))
    print('TOTAL', dict(tot))


def fix(spec, outdir, names):
    os.makedirs(outdir, exist_ok=True)
    top = os.path.dirname(os.path.abspath(outdir))          # log + md5.tsv next to mods\, never inside it
    log = open(os.path.join(top, 'soundplex_sequence_fix.log.txt'), 'w', encoding='utf-8', newline='\r\n')
    md5s = ['md5\tpath']
    for path in file_list(spec):
        name = os.path.basename(path)
        if names and name not in names: continue
        st, rows = check_file(path)
        bad = [r for r in rows if r[6].startswith('WRONG')]
        if not bad: continue
        raw = open(path, 'rb').read(); D = DW.read(raw, 'le')
        patched = collections.defaultdict(list)
        for sid, i, tg, cnt, xw, pw, v in bad:
            b = bytearray(D.sections[i].data); q = tg + 0xc
            assert bytes(b[q:q + 4]) == pw
            b[q:q + 4] = xw; D.sections[i].data = bytes(b)
            patched[i].append(q)
            line = '%s DTP %d (section %d) +%#07x: %s -> %s (Sequence repeat %d -> %d)' % (
                name, sid, i, q, pw.hex(), xw.hex(), struct.unpack('b', pw[:1])[0], struct.unpack('b', xw[:1])[0])
            print(line); log.write(line + '\n')
        new = D.write('le')
        if raw[:4] == b'CDRM': new = DW.cdrm_encode(new, 'le')
        dst = os.path.join(outdir, name)
        open(dst, 'wb').write(new)
        # proof: re-read both, every byte equal except the patched words, relocations / ids / order equal
        A = DW.read(raw, 'le'); B = DW.read(open(dst, 'rb').read(), 'le')
        assert len(A.sections) == len(B.sections) and A.names == B.names
        ndiff = 0
        for i, (a, b) in enumerate(zip(A.sections, B.sections)):
            assert (a.type, a.id, a.reloc, a.flags, a.ver, a.spec, len(a.data)) == (b.type, b.id, b.reloc, b.flags, b.ver, b.spec, len(b.data))
            for o in range(len(a.data)):
                if a.data[o] != b.data[o]:
                    assert any(q <= o < q + 4 for q in patched.get(i, [])), (name, i, o)
                    ndiff += 1
        h = hashlib.md5(open(dst, 'rb').read()).hexdigest()
        sh = hashlib.sha256(open(dst, 'rb').read()).hexdigest()
        line = '%s: %d words, %d bytes differ from %s (all inside the patched words), %d sections identical otherwise; md5 %s sha256 %s' % (
            name, len(bad), ndiff, path, len(A.sections), h, sh)
        print(line); log.write(line + '\n')
        md5s.append('%s\t%s' % (h, name))
    open(os.path.join(top, 'md5.tsv'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md5s) + '\n')
    log.close()
    print('files written', len(md5s) - 1)


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == 'calibrate': calibrate()
    elif a[0] == 'scan' and len(a) >= 2: scan(a[1], '--all' in a)
    elif a[0] == 'fix' and len(a) >= 3: fix(a[1], a[2], set(a[3:]))
    else: sys.exit(__doc__)
