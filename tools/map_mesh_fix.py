r"""Collision mesh of the *_map.drm files (PDA sonar map): typed byte order + gate (P4.9, 2026-11-14; from
work/w1_1411/w1_map_bvh.py, workspace docs Befund-W1-Testabend-1311.md "Dumps 1a" / Befund-P48-P49-Pipeline-1411.md).

Why: a map DRM is two type-13 sections - the map header (sentinel 0xbeebbeeb, dlc_generic) and ONE collision Mesh
(header 0x58 B, vertices, faces, KD nodes; layout generic_type0 "collision meshes"). Type 13 has no typed converter: the
learned generic table classed the words by label + value shape, so the KD node word +0xc (u8 axis, u8 leaf face count,
2 bytes) came out u32-swapped in 749 of 5933 nodes of dlc_yggdrasil_hall01_map (the walk tru 0x46c566 reads +0xd as
the leaf count -> an inner node with a far child outside the array -> the PDA sonar hang 13.11. 21:03), and in other
maps the header counts / face indices stayed raw (dlc_caverns_hall_map, dlc2_*: the mesh is not even found on PC).
Rule (every word of the mesh, decided by its place, not learned): header +0x00..+0x2c floats s32, +0x30 / +0x34 / +0x38
pointers (reloc), +0x3c and the counts +0x40..+0x50 s32, +0x54 {u16 vertexType, u16 height} s16; vertices float4 s32
(type 1) or int16 x3 s16 (type 0); faces 20 B {u32 i0, i1, i2, 4 bytes, 4 bytes} s32 s32 s32 raw raw (16 B: the first
four); KD nodes {float, float, u32, 4 bytes} s32 s32 s32 raw. Proof = the base-game map pairs (Xbox title update /
layers vs PC bigfile, mesh section of the same size): every mesh word, 0 contradicting (pinned PROOF_EXPECT).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/map_mesh_fix.py proof [--report R.json]
        base proof (exit 1 when a mesh word contradicts the rule or a pinned count differs)
  ../bin/pyt -t 1800 tools/map_mesh_fix.py check TREE[,TREE..] [--pack PACK] [--report R.json]
        gate: every *_map.drm of the tree with an Xbox twin: the PC file has the Xbox mesh (same place, same counts),
        KD node bytes +0xc..+0xf = the Xbox bytes, every node a leaf with its faces inside the face array or an inner
        node with both children inside the node array, face vertex indices < numVertices. Exit 1 on any fault
  ../bin/pyt -t 1800 tools/map_mesh_fix.py fix OUTDIR SRCDIR[,SRCDIR..] [--pack PACK] [name_map.drm ...]
        rewrite the mesh words of already converted map DRMs from their Xbox source (default: every *_map.drm of the
        first SRCDIR); everything else byte-identical (decoded DRM), each write re-read and checked
Library: mesh_words(xd, rel_be) -> {word offset: class}; fix_section(xd, rel_be, out) -> (bytes, words changed).
"""
import sys, os, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_write as DW

HDR = dict([(4 * k, 's32') for k in range(12)] + [(0x3c, 's32')] + [(0x40 + 4 * k, 's32') for k in range(5)] + [(0x54, 's16')])
FACE20 = ('s32', 's32', 's32', 'raw', 'raw')
FACE16 = ('s32', 's32', 's32', 'raw')
NODE16 = ('s32', 's32', 's32', 'raw')
PERM = {'s32': (3, 2, 1, 0), 's16': (1, 0, 3, 2), 'raw': (0, 1, 2, 3)}
# pinned base proof (2026-11-14): the 82 maps of the PC file list, 81 with an Xbox base twin; 39 meshes of the same
# section size, of them 23 with the same content on PC (every mesh word a byte order of the Xbox word) - those prove the
# rule; 16 re-baked on PC (other floats / KD tree: 'other' words; their byte-order matches are counted, not judged)
PROOF_EXPECT = {'pairs_missing': 1, 'pairs': 81, 'meshes': 39, 'meshes_same': 23, 'same_ok': 2250506, 'same_amb': 732880,
                'same_raw_not_s32': 503133, 'nodes': 295077, 'faces': 258253, 'mesh_size_differs': 47,
                'meshes_rebaked': 16, 'rebaked_ok': 263602, 'rebaked_amb': 113497, 'rebaked_other': 76385,
                'rebaked_raw_not_s32': 63120, 'rebaked_contra': 803, 'contra': 0}
PC_FILELIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ref', 'yura-release', 'FileLists',
                           'Tomb Raider Underworld (PC).txt')


def perm(w, c):
    return bytes(w[i] for i in PERM[c])


def find_mesh(d, rel, e='be', strict=True):
    """(header offset, numNodes, numFaces, numVertices, vertexType, face stride, (vo, fo, no)) of the collision Mesh in
    one map section (header pointers +0x30 / +0x34 / +0x38 internal, counts plausible, arrays inside), or None.
    strict=False: vertexType not checked (vertex stride 16) - only to describe a broken PC header"""
    E = '>' if e == 'be' else '<'
    itn = dict(rel.internal)
    found = []
    for o in sorted(itn):
        h = o - 0x38
        if h < 0 or (h + 0x30) not in itn or (h + 0x34) not in itn or h + 0x58 > len(d): continue
        nn, nf, nv = struct.unpack_from(E + '3I', d, h + 0x40)
        vt, = struct.unpack_from(E + 'H', d, h + 0x54)
        if not (0 < nn < 1 << 22 and 0 < nf < 1 << 22 and 0 < nv < 1 << 22) or (strict and vt not in (0, 1)): continue
        vo, fo, no = itn[h + 0x30], itn[h + 0x34], itn[h + 0x38]
        vs = 6 if vt == 0 else 16
        if vo + nv * vs > len(d) or no + 16 * nn > len(d): continue
        # face stride: the face array runs up to the next array start (or the section end)
        nxt = min([x for x in (vo, no, h, len(d)) if x > fo] or [len(d)])
        fs = 20 if fo + 20 * nf <= nxt else 16 if fo + 16 * nf <= nxt else None
        if fs is None: continue
        found.append((h, nn, nf, nv, vt, fs, (vo, fo, no)))
    return found[0] if len(found) == 1 else None


def mesh_words(xd, rel):
    """{word offset: class} for every non-pointer word of the Xbox mesh section (BE), {} without a mesh"""
    m = find_mesh(xd, rel, 'be')
    if m is None: return {}
    h, nn, nf, nv, vt, fs, (vo, fo, no) = m
    skip = set(rel.pointer_offsets()) | set(rel.id_offsets())
    ov = {}
    def put(o, c):
        if o % 4 == 0 and o + 4 <= len(xd) and o not in skip: ov[o] = c
    for w, c in HDR.items(): put(h + w, c)
    if vt == 1:
        for k in range(4 * nv): put(vo + 4 * k, 's32')
    elif vo % 4 == 0:
        for k in range((6 * nv + 3) // 4): put(vo + 4 * k, 's16')
    fc = FACE20 if fs == 20 else FACE16
    for k in range(nf):
        for j, c in enumerate(fc): put(fo + fs * k + 4 * j, c)
    for k in range(nn):
        for j, c in enumerate(NODE16): put(no + 16 * k + 4 * j, c)
    return ov


def fix_section(xd, rel, out):
    """mesh words of the converted section `out` (PC) from the Xbox section xd -> (new bytes, words changed)"""
    ov = mesh_words(xd, rel)
    if not ov or len(out) != len(xd): return bytes(out), 0
    b = bytearray(out); n = 0
    for o, c in ov.items():
        w = perm(xd[o:o + 4], c)
        if b[o:o + 4] != w: b[o:o + 4] = w; n += 1
    return bytes(b), n


def is_map(name):
    return os.path.basename(name).lower().endswith('_map.drm')


# ------------------------------------------------------------------------------------------------ base proof
def base_map_names():
    return sorted({l.strip().split('\\')[-1] for l in open(PC_FILELIST, encoding='utf-8', errors='replace')
                   if l.strip().lower().startswith('pc-w\\') and is_map(l.strip())})


def proof(p=print):
    """every mesh word of the base map pairs (Xbox base vs PC, mesh section of the same size): the rule's word = the PC
    word ('ok'), the Xbox word reads the same in every order ('amb'), else 'contra'. Also counted: the face words +0xc /
    +0x10 where raw and b2s16 / s32 differ (the alternatives the proof decides)."""
    import dtp_word_classes as C
    got = collections.Counter(); lines = []
    for nm in base_map_names():
        xs = C.find(C.BASE, 'be', 'xenon-w' + C.BS + nm); ps = C.find(C.PC, 'le', 'pc-w' + C.BS + nm)
        if xs is None or ps is None: got['pairs_missing'] += 1; continue
        got['pairs'] += 1
        if len(xs) != len(ps): got['section_count_differs'] += 1; continue
        for x, q in zip(xs, ps):
            if x['type'] != 13 or x['data'] is None or q['data'] is None: continue
            rel = R.parse(x['reloc'], 'be')
            ov = mesh_words(x['data'], rel)
            if not ov: continue
            if len(x['data']) != len(q['data']):
                got['mesh_size_differs'] += 1; lines.append('  %s: mesh section Xbox %d B PC %d B (re-authored) - skipped'
                                                            % (nm, len(x['data']), len(q['data']))); continue
            got['meshes'] += 1
            xd, pd = x['data'], q['data']
            m = find_mesh(xd, rel, 'be')
            pm = find_mesh(pd, R.parse(q['reloc'], 'le'), 'le')
            if pm is None or pm[:6] != m[:6]: got['pc_mesh_header_differs'] += 1
            c1 = collections.Counter(); first = []
            for o, c in ov.items():
                xw, pw = xd[o:o + 4], pd[o:o + 4]
                if len({perm(xw, k) for k in PERM}) == 1: c1['amb'] += 1; continue
                if perm(xw, c) == pw:
                    c1['ok'] += 1
                    # the byte words: decided against another order (s32 = the learned table's swap; b2s16 = the unit
                    # mesh rule of generic_type0 FACE20 +0xc)
                    if c == 'raw' and perm(xw, 's32') != xw: c1['raw_not_s32'] += 1
                    if c == 'raw' and xw[2] != xw[3]: c1['raw_not_b2s16'] += 1
                elif any(perm(xw, k) == pw for k in PERM):      # another byte order of the same bytes: against the rule
                    c1['contra'] += 1
                    if len(first) < 3: first.append('+0x%x %s: Xbox %s PC %s' % (o, c, xw.hex(), pw.hex()))
                else: c1['other'] += 1                          # PC value differs (re-baked map content), no order
            # a mesh whose PC content differs (re-baked: other floats, other KD tree) proves nothing about byte order;
            # only meshes where every word is a byte order of the Xbox word count
            kind = 'same' if not c1['other'] else 'rebaked'
            got['meshes_' + kind] += 1
            for k, v in c1.items(): got['%s_%s' % (kind, k)] += v
            if kind == 'same': got['nodes'] += m[1]; got['faces'] += m[2]
            lines.append('  %s: mesh nodes %d faces %d: %s %s%s' % (nm, m[1], m[2], kind, dict(c1),
                                                                  ' e.g. ' + '; '.join(first) if first else ''))
    got['contra'] = got['same_contra']
    return dict(got), lines


# ------------------------------------------------------------------------------------------------ PC-side check
def check_pc(pd, prel, xd=None, xrel=None):
    """faults of one PC mesh section (LE); with the Xbox section: same mesh place / counts, node bytes +0xc..+0xf"""
    c = collections.Counter(); faults = []
    m = find_mesh(pd, prel, 'le')
    xm = find_mesh(xd, xrel, 'be') if xd is not None else None
    if xd is not None and xm is None:
        c['sections_without_mesh'] += 1; return c, faults
    if m is None:
        lm = find_mesh(pd, prel, 'le', strict=False)
        why = ' (header +0x54 reads vertexType %d: {u16 vertexType, u16 height} not as u16 pair)' % \
            struct.unpack_from('<H', pd, lm[0] + 0x54)[0] if lm else ''
        faults.append('no collision mesh found on PC' + (' (Xbox has one at +0x%x)' % xm[0] if xm else '') + why)
        c['no_mesh'] += 1; return c, faults
    h, nn, nf, nv, vt, fs, (vo, fo, no) = m
    c['meshes'] += 1; c['nodes'] += nn; c['faces'] += nf
    if xm is not None and xm[:6] != m[:6]:
        faults.append('mesh header differs from the Xbox: PC %s Xbox %s' % (m[:6], xm[:6]))
    bad = leaf = inner = 0
    for k in range(nn):
        o = no + 16 * k
        idx = struct.unpack_from('<I', pd, o + 8)[0]
        if pd[o + 0xd]:
            leaf += 1
            if idx + pd[o + 0xd] > nf: bad += 1
        elif idx == 0 or k + idx >= nn or k + 1 >= nn: bad += 1
        else: inner += 1
    c['leaf'] += leaf; c['inner'] += inner; c['bad_nodes'] += bad
    if bad: faults.append('%d of %d KD nodes neither a leaf inside the faces nor an inner node inside the array' % (bad, nn))
    badf = 0
    for k in range(nf):
        i0, i1, i2 = struct.unpack_from('<3I', pd, fo + fs * k)
        if i0 >= nv or i1 >= nv or i2 >= nv: badf += 1
    c['bad_faces'] += badf
    if badf: faults.append('%d of %d faces with a vertex index >= %d' % (badf, nf, nv))
    if xm is not None and xm[6][2] == no:
        sw = sum(1 for k in range(nn) if pd[no + 16 * k + 0xc:no + 16 * k + 0x10] != xd[no + 16 * k + 0xc:no + 16 * k + 0x10])
        c['node_bytes_not_xbox'] += sw
        if sw: faults.append('%d KD nodes with bytes +0xc..+0xf other than the Xbox bytes' % sw)
    return c, faults


def opt(a, key):
    if key in a:
        k = a.index(key); v = a[k + 1]; del a[k:k + 2]; return v
    return None


def tree_maps(trees):
    return sorted({os.path.relpath(os.path.join(r, f), d).replace('\\', '/') for d in trees for r, _, fs in os.walk(d)
                   for f in fs if is_map(f)})


def xbox_drm(nm):
    from convert_dlc import raw_dlc
    raw, _ = raw_dlc(nm.replace('/', '\\'))
    if raw is None: raw, _ = raw_dlc(os.path.basename(nm))
    return DW.read(raw, 'be') if raw is not None else None


def check(trees, p=print):
    tot = collections.Counter(); rows = []
    for nm in tree_maps(trees):
        path = next(os.path.join(d, nm) for d in trees if os.path.isfile(os.path.join(d, nm)))
        X = xbox_drm(nm)
        if X is None: tot['no_xbox'] += 1; continue
        P = DW.read(open(path, 'rb').read(), 'le')
        tot['files'] += 1
        if len(P.sections) != len(X.sections):
            rows.append(dict(file=nm, faults=['section count PC %d Xbox %d' % (len(P.sections), len(X.sections))])); continue
        ff = []
        for k, (x, q) in enumerate(zip(X.sections, P.sections)):
            if x.type != 13 or q.type != 13 or len(x.data) != len(q.data): continue
            c, f = check_pc(bytes(q.data), R.parse(bytes(q.reloc), 'le'), bytes(x.data), R.parse(bytes(x.reloc), 'be'))
            tot.update(c)
            ff += ['section %d: %s' % (k, s) for s in f]
        if ff:
            tot['bad_files'] += 1
            rows.append(dict(file=nm, faults=ff))
            p('  BAD %s: %s' % (nm, '; '.join(ff)))
    return tot, rows


# ------------------------------------------------------------------------------------------------ fix existing files
def fix_file(path, X):
    raw_old = open(path, 'rb').read()
    D = DW.read(raw_old, 'le')
    n = 0
    for k, (x, q) in enumerate(zip(X.sections, D.sections)):
        if x.type != 13 or q.type != 13 or len(x.data) != len(q.data): continue
        nb, c = fix_section(bytes(x.data), R.parse(bytes(x.reloc), 'be'), bytes(q.data))
        if c: q.data = nb; n += c
    data = D.write('le')
    if raw_old[:4] == b'CDRM': data = DW.cdrm_encode(data, 'le')
    return data, n


def main(a):
    if not a: sys.exit(__doc__)
    a = list(a)
    pack = opt(a, '--pack'); report = opt(a, '--report')
    if pack: os.environ['TRUDLC_PACK_FIRST'] = pack
    if a[0] == 'proof':
        got, lines = proof()
        for l in lines: print(l)
        rc = 0 if got.get('contra', 1) == 0 and (not PROOF_EXPECT or got == PROOF_EXPECT) else 1
        if PROOF_EXPECT and got != PROOF_EXPECT: print('pinned counts differ: want %s' % PROOF_EXPECT)
        print('%s: %s' % ('ok' if rc == 0 else 'FAIL', got))
        if report: json.dump(dict(gate='map_mesh_proof', got=got, want=PROOF_EXPECT, exit=rc), open(report, 'w'), indent=1)
        return rc
    if a[0] == 'check' and len(a) >= 2:
        trees = a[1].split(',')
        miss = [t for t in trees if not os.path.isdir(t)]
        if miss: print('FAIL: tree folder(s) not found: %s' % miss); return 1
        tot, rows = check(trees)
        rc = 1 if tot['bad_files'] or not tot['files'] else 0
        print('%s: %s %s' % ('ok' if rc == 0 else 'FAIL', ','.join(trees), dict(tot)))
        if report:
            os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
            json.dump(dict(gate='map_mesh', trees=trees, pack=pack, totals=dict(tot), bad=rows, exit=rc),
                      open(report, 'w', encoding='utf-8'), indent=1)
        return rc
    if a[0] == 'fix' and len(a) >= 3:
        out, srcs = a[1], a[2].split(',')
        names = a[3:] or tree_maps(srcs[:1])
        rc = 0
        for nm in names:
            path = next((os.path.join(d, nm) for d in srcs if os.path.isfile(os.path.join(d, nm))), None)
            X = xbox_drm(nm)
            if path is None or X is None: print('%s: %s' % (nm, 'not found' if path is None else 'no Xbox source')); continue
            data, n = fix_file(path, X)
            if not n: print('%s: 0 words (unchanged, not written)' % nm); continue
            op = os.path.join(out, nm); os.makedirs(os.path.dirname(op), exist_ok=True)
            open(op, 'wb').write(data)
            # re-read: only mesh words changed, and the gate passes on the written file
            A, B = DW.read(open(path, 'rb').read(), 'le'), DW.read(open(op, 'rb').read(), 'le')
            same_rest = all(s.type == t.type and s.id == t.id and s.reloc == t.reloc and len(s.data) == len(t.data)
                            for s, t in zip(A.sections, B.sections)) and len(A.sections) == len(B.sections)
            faults = []
            for x, q in zip(X.sections, B.sections):
                if x.type == 13 and q.type == 13 and len(x.data) == len(q.data):
                    faults += check_pc(bytes(q.data), R.parse(bytes(q.reloc), 'le'), bytes(x.data), R.parse(bytes(x.reloc), 'be'))[1]
            ok = same_rest and not faults
            if not ok: rc = 1
            print('%s: %d mesh words changed -> %s (%s)%s' % (nm, n, op, 'ok' if ok else 'FAIL',
                                                             '' if not faults else ' ' + '; '.join(faults)))
        return rc
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
