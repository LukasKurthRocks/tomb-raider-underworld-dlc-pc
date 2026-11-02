"""Effect description nodes in DTP sections (the trees that kind-0 event records point at): the id word of type-1
nodes must be the u32 conversion of the Xbox word; check and with --fix repair (read-only unless --fix; test 50e crash
2026-11-02 19:32, AV tru+0x14df8f: node 7:22267 +0xa20 type 1 -> data word 0x495f0000 = Xbox id 0x00005f49 (24393)
left RAW by the converter).

Reader (tru.exe 2008 Steam build): kind-0 event record, payload byte 0 == 0 -> tru+0x1b99c0 -> tru+0x1935d0 ->
tru+0x1920b0(node): switch [node] (table 0x5923cc, 14 types); type 1 (tru+0x1920e9): `mov eax,[node+4]; mov esi,[eax]`
-> tru+0x14df80(id) = [id*4 + 0x00c36f28] (section table by id); type 4 (tru+0x1922de -> tru+0x190970 -> 0x1920b0
again) = a group whose children are nodes. Node layout: u32 type, ptr data (internal relocation), u32 self id (= the
id of the DTP that holds it), u32 0.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/fxnode_id_fix.py XBOX.drm PC.drm [--by-order] [--fix OUT.drm] [--all-types]
     --by-order: pair node DTPs by order (base pairs re-number DTPs; then ids are compared as "names a section")
  ../bin/pyt -t 1800 tools/fxnode_id_fix.py tree DIR [DIR ..]     every PC .drm vs its Xbox DLC original (dlc_drms.pkl)
Output per type-1 node: PC word, Xbox word, class (ok / raw / u16 / other), whether the id names a section.
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def nodes(s, e):
    """[(off, type, data_off)] of the effect nodes of one DTP"""
    E = '>' if e == 'be' else '<'
    if s.type != 7 or len(s.data) < 16: return []
    it = dict(R.parse(s.reloc, e).internal)
    out = []
    for o in range(0, len(s.data) - 15, 4):
        t, _, sid, z = struct.unpack_from(E + 'IIII', s.data, o)
        if t <= 13 and (o + 4) in it and sid == s.id and z == 0:
            out.append((o, t, it[o + 4]))
    return out


def cls(pw, xw):
    if pw == xw: return 'ok'
    xb = struct.pack('>I', xw)
    if struct.pack('<I', pw) == xb: return 'raw'
    if struct.pack('<I', pw) == xb[1::-1] + xb[3:1:-1]: return 'u16'
    return 'other'


def check_pair(SP, SX, ids, by_order, all_types, fixes, label=''):
    counts = collections.Counter()
    xs = {s.id: s for s in SX}
    pairs = []
    if by_order:
        pv = [s for s in SP if nodes(s, 'le')]
        xv = [s for s in SX if nodes(s, 'be')]
        pairs = list(zip(pv, xv))
    else:
        pairs = [(s, xs.get(s.id)) for s in SP if s.type == 7 and xs.get(s.id) is not None and nodes(s, 'le')]
    # anim event lists (tools/animfx.py walk, list+0 = u32 0): kind-1 records of sub 0x32 carry a u32 id in payload
    # word 1 (reader tru+0x1486b2, see tools/eventlist_idword_fix.py) - the same check for every such list
    import animfx as AF
    for p in SP:
        x = xs.get((7, p.id)) if p.type == 7 else None
        if x is None or len(x.data) != len(p.data): continue
        w = AF.walk(x.data, '>')
        if w is None: continue
        for a, h, fr, sz in w[0]:
            if h & 3 != 1 or sz < 16 or struct.unpack_from('>H', x.data, a + 8)[0] != 0x32: continue
            pw = struct.unpack_from('<I', p.data, a + 12)[0]; xw = struct.unpack_from('>I', x.data, a + 12)[0]
            c = cls(pw, xw)
            counts[('ev32', c)] += 1
            print('%s7:%-6d anim event +0x%04x sub 0x32: PC 0x%08x Xbox 0x%08x %-6s id %s' % (
                label, p.id, a, pw, xw, c, 'names a section' if xw in ids else 'NOT a section'))
            if c in ('raw', 'u16') and xw in ids and fixes is not None:
                fixes.setdefault(p.id, []).append((a + 12, xw))
    for p, x in pairs:
        np_, nx = nodes(p, 'le'), nodes(x, 'be')
        if [(a, b) for a, b, _ in np_] != [(a, b) for a, b, _ in nx]:
            counts['layout differs'] += 1
            continue
        for (o, t, d), (_, _, dx) in zip(np_, nx):
            if t != 1 and not all_types: continue
            if d + 4 > len(p.data) or dx + 4 > len(x.data): continue
            pw = struct.unpack_from('<I', p.data, d)[0]; xw = struct.unpack_from('>I', x.data, dx)[0]
            c = cls(pw, xw)
            if c == 'other' and pw in ids: c = 'renumbered'
            counts[(t, c)] += 1
            if c != 'ok' or all_types:
                print('%s7:%-6d node +0x%04x type %2d data +0x%04x: PC 0x%08x Xbox 0x%08x %-10s id %s' % (
                    label, p.id, o, t, d, pw, xw, c, 'names a section' if xw in ids else 'NOT a section of the PC file'))
            if t == 1 and c in ('raw', 'u16') and xw in ids and fixes is not None:
                fixes.setdefault(p.id, []).append((d, xw))
    return counts


def apply(path, out, fixes):
    D = DW.read(open(path, 'rb').read(), 'le')
    n = 0
    for k, s in enumerate(D.sections):
        if s.type == 7 and s.id in fixes:
            d = bytearray(s.data)
            for o, v in fixes[s.id]: struct.pack_into('<I', d, o, v); n += 1
            D.sections[k] = DW.Section(s.type, s.id, bytes(d), s.reloc, s.flags, s.ver, s.spec, s.pad)
    raw = D.write('le')
    if open(path, 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(raw)
    DR = DW.read(open(out, 'rb').read(), 'le')
    assert [(a.type, a.id, a.data, a.reloc) for a in DR.sections] == [(b.type, b.id, b.data, b.reloc) for b in D.sections]
    print('wrote %s: %d words in %d section copies (ids %s), readback ok' % (out, n, sum(
        1 for s in D.sections if s.type == 7 and s.id in fixes), sorted(fixes)))


def main(argv):
    if len(argv) < 2: print(__doc__); return 2
    if argv[0] == 'tree':
        import pickle
        W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic', 'dlc_drms.pkl')
        C = pickle.load(open(W, 'rb'))
        base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
        byname = {}
        for k, v in C.items(): byname.setdefault(base(k[1]), []).append(v)
        tot = collections.Counter()
        for top in argv[1:]:
            for dp, dn, fn in os.walk(top):
                for f in sorted(fn):
                    if not f.lower().endswith('.drm') or base(f) not in byname: continue
                    DP = DW.read(open(os.path.join(dp, f), 'rb').read(), 'le')
                    h, secs = byname[base(f)][0]
                    SX = [DW.Section(s['type'], s['id'], s['data'], s['reloc'], s['flags'], s['ver'], s['spec'])
                          for s in secs if s['type'] == 7]
                    ids = {s.id for s in DP.sections}
                    c = check_pair(DP.sections, SX, ids, False, False, None, f + ' ')
                    if c: print('%s: %s' % (f, dict(c)))
                    tot.update(c)
        print('total: %s' % dict(tot))
        return 0
    DX = DW.read(open(argv[0], 'rb').read(), 'be'); DP = DW.read(open(argv[1], 'rb').read(), 'le')
    ids = {s.id for s in DP.sections}
    fixes = {} if '--fix' in argv else None
    c = check_pair(DP.sections, DX.sections, ids, '--by-order' in argv, '--all-types' in argv, fixes)
    print('counts (type, class): %s' % dict(c))
    if fixes is not None:
        apply(argv[1], argv[argv.index('--fix') + 1], fixes)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
