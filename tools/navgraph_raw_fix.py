"""NavPower NavGraph image of a unit DRM (Level+0x60): the rule `navraw` (2026-11-05, workspace
docs\\Befund-Navmesh-Kombi-0511.md; found by docs\\Befund-Debug-Ansicht-0511.md 3.2 / tools/navgraph_probe.py).

Engine: Level+0x60 -> first dword 0xffffffff, the image starts at +4 and is handed unchanged to NavPower's
AddResource (PC tru+0x48c42f `cmp dword [eax], -1` ... `add eax, 4; push eax; call 0x42e990`). The image is the
middleware's own binary format; it is the same little-endian blob on the Xbox and on the PC (base pairs below), so the
correct conversion is: COPY IT RAW. Our converter byte-swapped words inside it (u16 pairs, u32, u8u8u16).

Image layout (read from the data, every base image explained byte for byte, `proof`): +0 0xffffffff, resource 1,
u32 COUNT, COUNT further resources up to the image end; resource = {u32 0, u32 1, u32 size, u32 checksum, size bytes
payload starting with the kind 0x10000 / 0x20000}, little-endian on both platforms. The COUNT word is the only
native-endian word: Xbox 00000001 -> PC 01000000 on every base pair with a second resource (7 / 7: l2_junglehub
+0x18264, l3_chapel +0x12f98, l7_arctic_sea +0x7fc78, l2_norsehub, l2_towerroom, l5_valaskjalf, l5_valaskjalf_entryb).
An image whose head is not -1 is no NavGraph (base l1_cine_ship_sinking: 8 zero bytes).

Rule `navraw`: the PC image = the Xbox image byte for byte, the COUNT word u32-swapped, when the pair has the same
layout (image in the same section index, same section type / id / size, image offset equal, no relocations in that
section on either side, the layout explains every byte). Every PC word that differs from that must be a byte order of
the wanted word (PERMS); a word that is no byte order of it is UNEXPECTED (fix_drm raises SystemExit: nothing is
guessed). The DLC 1 dlc_dungeon word +0x288cc (Xbox 00000001, upstream / B138 / B270 / ours 01000000) IS the COUNT
word of a two-resource image: the PC value 01000000 is right (same as the 7 base pairs) and stays.
Base pairs whose PC image is not the Xbox one (14 of the same size, 16 of another size) hold a navmesh the PC team
rebuilt (resource 1 checksum differs, or records re-ordered under the same checksum): 0 words of any base pair are a
byte order of the Xbox word.

Modes (from the repository root):
  ../bin/pyt -t 1800 tools/navgraph_raw_fix.py proof [--report R.json]
        every base unit (work/generic/lists/{xbox,pc}_unitlist.txt names) in the Xbox archives (xbase, xbase2, tu) and
        the PC archives (pcbig, pcpatch): image location, section relocations, size field, class of every word;
        exit 1 when the counts differ from PROOF_EXPECT (`calibrate` = same output, always exit 0)
  ../bin/pyt -t 900 tools/navgraph_raw_fix.py scan LIST_OR_DIR [--pack PACK] [--report R.json]
        DLC unit DRMs (folder, list file of .drm paths, single .drm; several joined with ',' = later name wins):
        words of the image that differ from the Xbox original, by class; exit 1 when any word differs (the gate)
  ../bin/pyt -t 900 tools/navgraph_raw_fix.py fix LIST_OR_DIR OUTDIR [NAME ...] [--pack PACK]
        writes the units with wrong words to OUTDIR (only the image words set raw), proves every written file
        (only the planned bytes differ, headers / relocations identical, re-plan 0); md5.tsv + log next to OUTDIR
  ../bin/pyt -t 300 tools/navgraph_raw_fix.py show PC.drm UNITNAME OFFSET [NWORDS] [--pack PACK]
        words around an image offset: Xbox bytes, PC bytes, both read little-endian (context of one word)
Library (tools/dlc_struct_fixes.py step navraw): plan(XD, PD), fix_drm(XD, raw) -> (new raw or None, changes, info).
"""
import sys, os, struct, collections, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

PERMS = {'raw': (0, 1, 2, 3), 'u32': (3, 2, 1, 0), 'u16u16': (1, 0, 3, 2), 'u8u8u16': (0, 1, 3, 2),
         'u16u8u8': (1, 0, 2, 3), 'halves': (2, 3, 0, 1)}
FIXABLE = ('u32', 'u16u16', 'u8u8u16', 'u16u8u8', 'halves')
FIELD = 0x60                     # Level+0x60 -> NavGraph image (Level+0x68 = 3D planner image, not touched)
LISTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic', 'lists')
XSRC = ('xbase', 'xbase2', 'tu')
PSRC = ('pcbig', 'pcpatch')
# measured by `calibrate` (2026-11-05, log logs\nav0511_proof.log); `proof` fails when a count differs
PROOF_EXPECT = {'pairs': 82, 'words': 589331, 'resources': 72, 'links': 65, 'link_ok': 58, 'link_u32': 7,
                'pairs_rule_exact': 52, 'pairs_pc_rebuilt': 14, 'pairs_pc_rebuilt_new_checksum': 12,
                'pairs_pc_rebuilt_same_checksum': 2, 'byteorder_words': 0, 'class_other': 10595,
                'image_at_section_start': 66, 'image_section_type0_id0': 66, 'not_comparable': 16,
                'not_comparable_size_differs': 16}


def word_class(xw, pw):
    """'ok' (raw), one of FIXABLE (first match), or 'other' (no byte order of the Xbox word)"""
    if pw == xw: return 'ok'
    for n in FIXABLE:
        if bytes(xw[i] for i in PERMS[n]) == pw: return n
    return 'other'


def is_unit(D, e):
    """section 0 = Level whose u32 @0 is an external pointer to a 24-byte Terrain section (tools/unit_ids.py)"""
    if not D.sections or D.sections[0].type != 0: return False
    ext = {so: (si, do) for si, so, do in R.parse(bytes(D.sections[0].reloc), e).external}
    return 0 in ext and len(D.sections[ext[0][0]].data) == 24


def image_loc(D, e):
    """(section index, offset) of the Level+0x60 image, or None"""
    if not is_unit(D, e): return None
    r0 = R.parse(bytes(D.sections[0].reloc), e)
    ext = {so: (si, do) for si, so, do in r0.external}
    if FIELD in ext: return ext[FIELD]
    it = dict(r0.internal)
    return (0, it[FIELD]) if FIELD in it else None


def image_info(D, e):
    """dict(sec, off, len, type, id, reloc_empty, head (-1?), size_ok (+0xc + 0x18 == image length)) or None"""
    t = image_loc(D, e)
    if t is None: return None
    si, o = t
    s = D.sections[si]; d = bytes(s.data)
    n = len(d) - o
    head = struct.unpack_from('<I', d, o)[0] if n >= 4 else None
    size = struct.unpack_from('<I', d, o + 0xc)[0] if n >= 0x10 else None
    return dict(sec=si, off=o, len=n, type=s.type, id=s.id, reloc_empty=R.parse(bytes(s.reloc), e).empty(),
                reloc_bytes=len(s.reloc), head=head, size=size, size_ok=size is not None and size + 0x18 == n)


def _resource(d, r):
    """one NavPower resource at r: {+0 u32 0, +4 u32 1, +8 u32 size, +0xc checksum, +0x10 payload of `size` bytes
    (payload +0 = kind 0x10000 / 0x20000)}, little-endian on both platforms -> (r, size, kind, end) or None"""
    if r + 0x14 > len(d): return None
    z, one, size, chk, kind = struct.unpack_from('<5I', d, r)
    end = r + 0x10 + size
    if z != 0 or one != 1 or size < 4 or end > len(d): return None
    return (r, size, kind, end)


def resources(d, E):
    """layout of an image: +0 0xffffffff, resource 1, u32 N (the COUNT word, in the platform's byte order E: '>' Xbox,
    '<' PC), N further resources; the last one ends at the image end.
    -> ([(start, size, kind, end)], count word offset or None, covers = the layout explains every byte)"""
    # no NavGraph: the engine passes nothing to NavPower unless the head is -1; base l1_cine_ship_sinking = 8 zero bytes
    if len(d) < 4 or d[:4] != b'\xff\xff\xff\xff': return [], None, d == b'\0' * len(d)
    r1 = _resource(d, 4)
    if r1 is None or r1[3] + 4 > len(d): return ([r1] if r1 else []), None, False
    out = [r1]; cq = r1[3]
    n = struct.unpack_from(E + 'I', d, cq)[0]
    r = cq + 4
    if n > 64: return out, cq, False
    for _ in range(n):
        x = _resource(d, r)
        if x is None: return out, cq, False
        out.append(x); r = x[3]
    return out, cq, r == len(d)


def link_words(d):
    """image offsets of the native-endian words (the COUNT word after resource 1). On every base pair whose count is
    not 0 the PC holds the u32 swap of the Xbox word (Xbox 00000001 -> PC 01000000; l2_junglehub +0x18264, l3_chapel
    +0x12f98, l7_arctic_sea +0x7fc78 ...); a count 0 reads the same in both orders. d = the Xbox image (count BE)"""
    rs, cq, covers = resources(d, '>')
    return ([cq] if cq is not None else []), rs, covers


def want_image(xd):
    """the PC image the rule asks for: the Xbox bytes, the count word u32-swapped"""
    w = bytearray(xd)
    links, rs, covers = link_words(xd)
    for q in links: w[q:q + 4] = xd[q:q + 4][::-1]
    return bytes(w), links, rs, covers


# ---------------------------------------------------------------- one DRM pair
def plan(XD, PD):
    """-> dict(status, rows=[(image offset, wanted word, PC word, class)] for every word that differs from the rule,
    xi, pi, classes, links, resources)
    status: 'ok' (pair laid out alike, rows = the wrong words), 'no image' (neither side has one), or a reason why the
    pair is not comparable (layout) - the step leaves such a DRM alone and the scan reports it"""
    xi, pi = image_info(XD, 'be'), image_info(PD, 'le')
    res = dict(status='ok', rows=[], xi=xi, pi=pi, classes=collections.Counter(), links=[], resources=[],
               link_classes=collections.Counter())
    if xi is None and pi is None: res['status'] = 'no image'; return res
    if xi is None or pi is None:
        res['status'] = 'image on one side only (Xbox %s, PC %s)' % (xi is not None, pi is not None); return res
    why = [k for k in ('sec', 'off', 'len', 'type', 'id') if xi[k] != pi[k]]
    if why: res['status'] = 'layout differs (%s)' % ', '.join('%s Xbox %s PC %s' % (k, xi[k], pi[k]) for k in why); return res
    if not (xi['reloc_empty'] and pi['reloc_empty']):
        res['status'] = 'image section has relocations (Xbox %d, PC %d bytes)' % (xi['reloc_bytes'], pi['reloc_bytes'])
        return res
    xd = bytes(XD.sections[xi['sec']].data)[xi['off']:]
    pd = bytes(PD.sections[pi['sec']].data)[pi['off']:]
    if len(xd) % 4:
        res['status'] = 'image length %d not a multiple of 4' % len(xd); return res
    wd, links, rs, covers = want_image(xd)
    res['links'], res['resources'], res['covers'] = links, rs, covers
    if not covers:
        res['status'] = 'resource chain does not cover the image (%d resources parsed)' % len(rs); return res
    ls = set(links)
    for q in range(0, len(xd), 4):
        ww, pw = wd[q:q + 4], pd[q:q + 4]
        c = word_class(ww, pw)
        res['classes'][c] += 1
        if q in ls: res['link_classes'][word_class(xd[q:q + 4], pw)] += 1
        if c != 'ok': res['rows'].append((q, ww, pw, c))
    return res


def fix_drm(XD, raw):
    """-> (new raw or None, changes [(section index, section offset, old, new, image offset)], plan info). Raises
    SystemExit on an UNEXPECTED word. The written bytes are proven: the decoded DRM differs only in the planned bytes,
    file / section headers and relocations identical, re-plan 0 words."""
    PD = DW.read(raw, 'le')
    info = plan(XD, PD)
    if info['status'] != 'ok': return None, [], info
    bad = [r for r in info['rows'] if r[3] == 'other']
    if bad:
        raise SystemExit('navraw: %d UNEXPECTED word(s) (no byte order of the Xbox word): %s' % (len(bad), ', '.join(
            '+%#x Xbox %s PC %s' % (q, xw.hex(), pw.hex()) for q, xw, pw, c in bad[:10])))
    if not info['rows']: return None, [], info
    si, o = info['pi']['sec'], info['pi']['off']
    s = PD.sections[si]; b = bytearray(s.data); changes = []
    for q, xw, pw, c in info['rows']:
        assert bytes(b[o + q:o + q + 4]) == pw
        b[o + q:o + q + 4] = xw
        changes.append((si, o + q, pw, xw, q))
    s.data = bytes(b)
    new = PD.write('le')
    if raw[:4] == b'CDRM': new = DW.cdrm_encode(new, 'le')
    verify(raw, new, changes, XD)
    return new, changes, info


def verify(raw, new, changes, XD):
    """assert: only the planned bytes differ, headers / relocations / names identical, re-plan finds 0 words"""
    A, B = DW.read(raw, 'le'), DW.read(new, 'le')
    assert len(A.sections) == len(B.sections) and A.names == B.names and A.pad == B.pad, 'file layout changed'
    planned = {(k, q + j) for k, q, a, b, iq in changes for j in range(len(a)) if a[j] != b[j]}
    got = set()
    for k, (a, b) in enumerate(zip(A.sections, B.sections)):
        assert (a.type, a.id, a.flags, a.ver, a.spec, a.pad, bytes(a.reloc), len(a.data)) == \
               (b.type, b.id, b.flags, b.ver, b.spec, b.pad, bytes(b.reloc), len(b.data)), 'section %d header changed' % k
        if a.data != b.data: got |= {(k, i) for i in range(len(a.data)) if a.data[i] != b.data[i]}
    assert got == planned, '%d bytes differ, %d planned' % (len(got), len(planned))
    again = plan(XD, B)
    assert again['status'] == 'ok' and not again['rows'], 're-plan: %s, %d words' % (again['status'], len(again['rows']))
    return len(got)


# ---------------------------------------------------------------- base proof
def base_names():
    out = set()
    for f in ('xbox_unitlist.txt', 'pc_unitlist.txt', 'xboxtu_unitlist.txt'):
        p = os.path.join(LISTS, f)
        if not os.path.exists(p): continue
        for l in open(p, encoding='utf-8-sig').read().splitlines()[1:]:
            l = l.strip()
            if l and not l.lower().startswith('dlc\\'): out.add(l.split('\\')[-1].lower() + '.drm')
    return sorted(out)


def archive_drm(src, name, cache):
    import locals as LC
    from archive import Archive
    from names import crc
    from drm import cdrm_decode
    if src not in cache:
        path, e, pre = LC.SRC[src]
        cache[src] = (Archive(path, e), e, pre)
    A, e, pre = cache[src]
    recs = A.find(crc(pre + '\\' + name))
    if not recs: return None
    full = [r for r in recs if r['spec'] == 0xffffffff]
    r = (full or recs)[-1]
    return DW.read(cdrm_decode(A.read(r), e), e)


def base_stats():
    cache = {}
    rows = []
    for name in base_names():
        X = {s: archive_drm(s, name, cache) for s in XSRC}
        P = {s: archive_drm(s, name, cache) for s in PSRC}
        for xs, XD in X.items():
            if XD is None: continue
            for ps, PD in P.items():
                if PD is None: continue
                info = plan(XD, PD)
                if info['status'] == 'no image': rows.append((name, xs, ps, 'no image', None)); continue
                same_units = [len(s.data) for s in XD.sections] == [len(s.data) for s in PD.sections]
                reauth = []
                if info['status'] == 'ok':
                    xd = bytes(XD.sections[info['xi']['sec']].data)[info['xi']['off']:]
                    pd = bytes(PD.sections[info['pi']['sec']].data)[info['pi']['off']:]
                    # a resource whose checksum (+0xc) differs was rebuilt for the PC (other content, not a byte order)
                    reauth = [s for s, n, k, e in info['resources'] if xd[s + 0xc:s + 0x10] != pd[s + 0xc:s + 0x10]]
                    rr = [(s, e) for s, n, k, e in info['resources'] if s in reauth]
                    inside = lambda q: any(s <= q < e for s, e in rr)
                    byteorder_rows = [r for r in info['rows'] if r[3] != 'other']
                    byteorder_outside = [r for r in byteorder_rows if not inside(r[0])]
                    other_outside = [r for r in info['rows'] if r[3] == 'other' and not inside(r[0])]
                else:
                    byteorder_rows = byteorder_outside = other_outside = []
                    if info['xi'] and info['pi']:
                        xd = bytes(XD.sections[info['xi']['sec']].data)[info['xi']['off']:]
                        pd = bytes(PD.sections[info['pi']['sec']].data)[info['pi']['off']:]
                        xr, pr = resources(xd, '>'), resources(pd, '<')
                        reauth = ['Xbox %d / PC %d resources, layout explained %s / %s, checksums %s / %s' % (
                            len(xr[0]), len(pr[0]), xr[2], pr[2], ','.join(xd[s + 0xc:s + 0x10].hex() for s, n, k, e in xr[0]),
                            ','.join(pd[s + 0xc:s + 0x10].hex() for s, n, k, e in pr[0]))]
                rows.append((name, xs, ps, info['status'], dict(
                    words=sum(info['classes'].values()), classes=dict(info['classes']),
                    link_classes=dict(info['link_classes']), links=['+%#x' % q for q in info['links']],
                    nres=len(info['resources']), kinds=['%#x' % k for s, n, k, e in info['resources']],
                    reauthored=[('+%#x' % s) if isinstance(s, int) else s for s in reauth], byteorder=len(byteorder_rows),
                    byteorder_outside=len(byteorder_outside), other_outside=len(other_outside),
                    xi=info['xi'], pi=info['pi'], same_section_sizes=same_units, nsec=(len(XD.sections), len(PD.sections)),
                    first=[('+%#x' % q, xw.hex(), pw.hex(), c) for q, xw, pw, c in info['rows'][:6]])))
    return rows


def proof(strict=True, report=None):
    rows = base_stats()
    got = collections.Counter()
    for name, xs, ps, st, d in rows:
        if st == 'no image': got['no_image'] += 1; continue
        got['pairs'] += 1
        if st != 'ok':
            got['not_comparable'] += 1
            # another image size = a navmesh rebuilt for the PC (resource 1 checksum differs in every such pair)
            if st.startswith('layout differs (len '): got['not_comparable_size_differs'] += 1
            print('%-28s %-6s %-7s NOT COMPARABLE: %s; %s; unit section sizes all equal %s, sections %s' % (
                name, xs, ps, st, '; '.join(d['reauthored']), d['same_section_sizes'], d['nsec']))
            continue
        bad = sum(v for k, v in d['classes'].items() if k != 'ok')
        got['words'] += d['words']
        got['resources'] += d['nres']; got['links'] += len(d['links'])
        for k, v in d['link_classes'].items(): got['link_' + k] += v
        # PC content differs (no word is a byte order of the Xbox word): the PC team rebuilt the navmesh; with a new
        # checksum (+0xc of the resource) or, in two pairs, records in another order under the same checksum
        if not bad: got['pairs_rule_exact'] += 1
        elif not d['byteorder']:
            got['pairs_pc_rebuilt'] += 1
            got['pairs_pc_rebuilt_new_checksum' if d['reauthored'] else 'pairs_pc_rebuilt_same_checksum'] += 1
        else: got['pairs_contradicting'] += 1
        for k, v in d['classes'].items():
            if k != 'ok': got['class_' + k] += v
        got['byteorder_words'] += d['byteorder']
        got['image_at_section_start'] += 1 if d['xi']['off'] == 0 else 0
        got['image_section_type0_id0'] += 1 if (d['xi']['type'], d['xi']['id']) == (0, 0) else 0
        print('%-28s %-6s %-7s section %d +%#x, %d bytes, %d resource(s) %s, link words %s %s: %s%s' % (
            name, xs, ps, d['xi']['sec'], d['xi']['off'], d['xi']['len'], d['nres'], '/'.join(d['kinds']),
            ','.join(d['links']) or '-', d['link_classes'] or '',
            'RULE EXACT (raw + count word u32)' if not bad else (
                ('PC REBUILT (%s; %d words differ, none a byte order of the Xbox word)' % (
                    ('checksum differs in resource ' + ','.join(d['reauthored'])) if d['reauthored'] else 'same checksum',
                    bad)) if not d['byteorder']
                else 'CONTRADICTS %s (byte-order words %d, outside rebuilt resources %d / %d)' % (
                    {k: v for k, v in d['classes'].items() if k != 'ok'}, d['byteorder'], d['byteorder_outside'], d['other_outside'])),
            '' if not bad else ' first ' + ' '.join('%s:%s>%s(%s)' % t for t in d['first'][:3])))
    got = dict(got)
    ok = PROOF_EXPECT is not None and got == PROOF_EXPECT
    print('TOTAL %s' % got)
    print('rule navraw (image raw, link words u32, on every comparable base pair): %s (expected %s)' % (
        'PROVEN' if ok else ('CALIBRATE' if PROOF_EXPECT is None else 'FAILED'), PROOF_EXPECT))
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        json.dump(dict(totals=got, expect=PROOF_EXPECT, rows=[list(r[:4]) + [r[4] and {k: v for k, v in r[4].items()}] for r in rows]),
                  open(report, 'w', encoding='utf-8'), indent=1, default=str)
    return 0 if ok or not strict else 1


_PROVEN = None


def proven():
    """the base proof once per process (stdout kept quiet) -> (ok, last two proof lines); the pipeline step navraw of
    tools/dlc_struct_fixes.py refuses to write or check when it fails"""
    global _PROVEN
    if _PROVEN is None:
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = proof(True)
        _PROVEN = (rc == 0, [l[:300] for l in buf.getvalue().splitlines()[-2:]])
    return _PROVEN


# ---------------------------------------------------------------- DLC trees
def check_file(path, pack=None):
    """-> (status text, plan info or None, Xbox Drm or None); Xbox source as tools/soundplex_sequence_fix.py"""
    import soundplex_sequence_fix as SQ
    PD = DW.read(open(path, 'rb').read(), 'le')
    if image_loc(PD, 'le') is None:            # cheap pre-check: a PC DRM without a Level+0x60 image is not a unit
        return 'no PC image', dict(status='no image', rows=[], xi=None, pi=None, classes=collections.Counter()), None
    cands = SQ.xbox_candidates(path, pack)
    if not cands: return 'no Xbox source', None, None
    best = None
    for XD, pk in cands:
        info = plan(XD, PD)
        score = (info['status'] == 'ok', -len(info['rows']))
        if best is None or score > best[0]: best = (score, XD, pk, info)
    _, XD, pk, info = best
    return '%s%s' % (pk, '' if len(cands) == 1 else ' (best of %s)' % '/'.join(c[1] for c in cands)), info, XD


def scan(paths, pack=None, label=None):
    import soundplex_sequence_fix as SQ
    tot = collections.Counter(); files = []; lines = []
    for path in paths:
        tot['files'] += 1
        st, info, XD = check_file(path, pack)
        if info is None: tot['no_xbox_source'] += 1; continue
        if info['status'] == 'no image': tot['no_image'] += 1; continue
        tot['units'] += 1
        if info['status'] != 'ok':
            tot['not_comparable'] += 1
            ln = '%s: %s: %s' % (os.path.basename(path), st, info['status']); print(ln); lines.append(ln); continue
        cl = collections.Counter(r[3] for r in info['rows'])
        tot['wrong'] += sum(v for k, v in cl.items() if k != 'other'); tot['unexpected'] += cl.get('other', 0)
        for k, v in cl.items(): tot['class_' + k] += v
        ln = '%s: %s: image section %d, %d bytes, %d words, %s' % (
            os.path.basename(path), st, info['pi']['sec'], info['pi']['len'], sum(info['classes'].values()),
            'raw (0 differ)' if not info['rows'] else '%d differ %s; first %s' % (len(info['rows']), dict(cl), ' '.join(
                '+%#x:%s>%s' % (q, xw.hex(), pw.hex()) for q, xw, pw, c in info['rows'][:6])))
        print(ln); lines.append(ln)
        if info['rows']: files.append(path.replace('\\', '/'))
    # a unit the rule cannot pair (layout / relocations / unexplained layout) fails the gate too: nothing is assumed
    res = 'FAIL' if tot['wrong'] or tot['unexpected'] or tot['not_comparable'] else 'ok'
    print('TOTAL%s %s' % ((' ' + label) if label else '', dict(tot)))
    print('scan: %s' % res)
    return res, dict(tot), files, lines


def fix(spec, outdir, names, pack):
    import soundplex_sequence_fix as SQ
    os.makedirs(outdir, exist_ok=True)
    top = os.path.dirname(os.path.abspath(outdir))
    log = open(os.path.join(top, 'navgraph_raw_fix.log.txt'), 'w', encoding='utf-8', newline='\r\n')
    md5s = ['md5\tpath']
    for path in SQ.file_list(spec):
        name = os.path.basename(path)
        if names and name not in names: continue
        st, info, XD = check_file(path, pack)
        if info is None or info['status'] != 'ok' or not info['rows']: continue
        raw = open(path, 'rb').read()
        new, changes, info = fix_drm(XD, raw)
        if new is None: continue
        cl = collections.Counter(r[3] for r in info['rows'])
        dst = os.path.join(outdir, name)
        open(dst, 'wb').write(new)
        ndiff = verify(raw, open(dst, 'rb').read(), changes, XD)
        h = hashlib.md5(new).hexdigest(); sh = hashlib.sha256(new).hexdigest()
        line = '%s (%s): %d image words set raw %s, %d bytes differ from %s (all inside the image), md5 %s sha256 %s' % (
            name, st, len(changes), dict(cl), ndiff, path, h, sh)
        print(line); log.write(line + '\n')
        md5s.append('%s\t%s' % (h, name))
    open(os.path.join(top, 'md5.tsv'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md5s) + '\n')
    log.close()
    print('files written', len(md5s) - 1)


def show(path, unit, off, n, pack):
    import soundplex_sequence_fix as SQ
    st, info, XD = check_file(path, pack)
    if info is None or info['xi'] is None: print('no Xbox image (%s)' % st); return 1
    PD = DW.read(open(path, 'rb').read(), 'le')
    xd = bytes(XD.sections[info['xi']['sec']].data)[info['xi']['off']:]
    pd = bytes(PD.sections[info['pi']['sec']].data)[info['pi']['off']:] if info['pi'] else b''
    print('%s (%s): status %s, image %d bytes' % (unit, st, info['status'], len(xd)))
    for q in range(max(0, off - 4 * n) & ~3, min(len(xd), off + 4 * n + 4), 4):
        xw, pw = xd[q:q + 4], pd[q:q + 4]
        print('  %s+%#07x  Xbox %s (LE %11d %12.4g)  PC %s (LE %11d)  %s' % (
            '>' if q == off else ' ', q, xw.hex(), struct.unpack('<i', xw)[0], struct.unpack('<f', xw)[0], pw.hex(),
            struct.unpack('<i', pw)[0] if len(pw) == 4 else 0, word_class(xw, pw)))
    return 0


def baseshow(name, off, n, xsrc, psrc):
    """words around an image offset of a BASE pair (archives), plus the image head (+0x00..+0x2c)"""
    cache = {}
    XD, PD = archive_drm(xsrc, name, cache), archive_drm(psrc, name, cache)
    if XD is None or PD is None: print('%s: not in %s / %s' % (name, xsrc, psrc)); return 1
    info = plan(XD, PD)
    if info['xi'] is None or info['pi'] is None: print('%s: no image (%s)' % (name, info['status'])); return 1
    xd = bytes(XD.sections[info['xi']['sec']].data)[info['xi']['off']:]
    pd = bytes(PD.sections[info['pi']['sec']].data)[info['pi']['off']:]
    print('%s %s/%s: %s; image Xbox %d bytes, PC %d bytes; resources Xbox %s PC %s' % (
        name, xsrc, psrc, info['status'], len(xd), len(pd), resources(xd, '>'), resources(pd, '<')))
    rng = sorted(set(list(range(0, min(0x30, len(xd)), 4)) + list(range(max(0, off - 4 * n) & ~3, min(len(xd), off + 4 * n + 4), 4))))
    for q in rng:
        xw, pw = xd[q:q + 4], pd[q:q + 4]
        print('  %s+%#07x  Xbox %s (LE %11d %12.4g)  PC %s (LE %11d)  %s' % (
            '>' if q == off else ' ', q, xw.hex(), struct.unpack('<i', xw)[0], struct.unpack('<f', xw)[0], pw.hex(),
            struct.unpack('<i', pw)[0] if len(pw) == 4 else 0, word_class(xw, pw)))
    return 0


def opt(a, key):
    if key in a:
        k = a.index(key); v = a[k + 1]; del a[k:k + 2]; return v
    return None


def main(a):
    if not a: sys.exit(__doc__)
    pack = opt(a, '--pack'); report = opt(a, '--report')
    if a[0] == 'calibrate': return proof(False, report)
    if a[0] == 'proof': return proof(True, report)
    if a[0] == 'scan' and len(a) == 2:
        import soundplex_sequence_fix as SQ
        r, tot, files, lines = scan(SQ.file_list(a[1]), pack)
        if report:
            os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
            json.dump(dict(spec=a[1], pack=pack, result=r.lower(), totals=tot, files=files, lines=lines),
                      open(report, 'w', encoding='utf-8'), indent=1)
        return 1 if r != 'ok' else 0
    if a[0] == 'fix' and len(a) >= 3: fix(a[1], a[2], set(a[3:]), pack); return 0
    if a[0] == 'show' and len(a) >= 4:
        return show(a[1], a[2], int(a[3], 0), int(a[4]) if len(a) > 4 else 8, pack)
    if a[0] == 'baseshow' and len(a) >= 3:
        xs = opt(a, '--xsrc') or 'xbase'; ps = opt(a, '--psrc') or 'pcbig'
        return baseshow(a[1], int(a[2], 0), int(a[3]) if len(a) > 3 else 8, xs, ps)
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
