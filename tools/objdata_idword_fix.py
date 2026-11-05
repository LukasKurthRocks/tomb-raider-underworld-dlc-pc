"""Player data: the two breath-sound ids at data +0x94 / +0x98 must be u32 section ids; check and with --out repair
(read-only unless --out; night 2026-11-04, TruDataGuard hits 'invalid id 0x68f40000 ... caller tru+0x194cad' in runs
50k / paket02 / paket03 / paket07: doppelganger_casual DTP 20212 +0x21088 = 0x68f40000, Xbox 0x000068f4 = DTP 26868 of
the same file, converted as two u16 instead of one u32; +0x21084 = 0x68f30000 the same).
Reader (tru.exe 2008 Steam build): tru+0x356c40 and tru+0x356db0 (thunks tru+0x35e300 / tru+0x35e310) take
`[[0xe7f094] + 0x50]` (player instance -> data) +0x94 when the air gameTracker+0x920 is below 0 (set to 0), else +0x98,
and pass it as a full u32 to tru+0x1954b0 -> tru+0x194ca0 -> tru+0x14df80(id) = [id*4 + 0x00c36f28] (section table)
-> tru+0x1935d0 (sound emitter on the instance's sound list +0x248); then HUD value 0x2e = air / data +0xf8 (s16, 4000).
The data block is the target of the DTP's relocated pointer at +0xc8 (as object 858's DTP 22497, Befund-Schattenkraft).
Usage (from the repository root):
  ../bin/pyt -t 600 tools/objdata_idword_fix.py check XBOX.drm PC.drm [--out OUT.drm] [--md5 TREE_DIR]
  ../bin/pyt -t 1800 tools/objdata_idword_fix.py scan DIR [DIR ..]
     scan: every PC .drm vs its Xbox DLC original (work/generic/dlc_drms.pkl): (a) the two fields above in every DTP
     with a +0xc8 pointer, (b) the generic signature anywhere in a DTP: aligned word, no relocation, Xbox 0x0000vvvv,
     PC 0xvvvv0000, 0x1000 <= v <= 0x7fff and v names a section of the PC file (candidates only - a real u16 pair
     (0, v) looks the same).
  --md5 TREE_DIR writes TREE_DIR/md5.tsv (md5 + path relative to TREE_DIR/mods) after --out.
Output per differing field: section, offset, PC word, Xbox word, class (u16 / raw / other), whether the id names a
section, data +0xf8 (the player's air maximum, 4000 in doppelganger_casual). Many DTPs have a +0xc8 pointer; only
class u16 whose Xbox u32 names a section of the same file is repaired.
Library / pipeline (2026-11-04, agent N11): fix_drm(XD, PD) = the same proven class as `check --out`, used by
tools/dlc_struct_fixes.py step 'objid' (tools/dlc_fixes_build.py, after objtex / objrec; check mode
`dlc_struct_fixes.py check TREE --steps objid`). The 20 generic candidates of `scan` are never repaired.
The repaired value is the PC id of the DTP the Xbox id names (id_map, position partner): the same for new DLC DTPs
(doppelganger 26867 / 26868), renumbered for base-game DTPs (the six Xbox costume packs' 1161 / 1162 -> PC 962 / 963,
as in the base pair lara.drm and the played B138 DLC 1 costumes; tools/player_breath_ids.py shows the values).
"""
import sys, os, struct, collections, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

FIELDS = ((0x94, 'breath sound, air below 0'), (0x98, 'breath sound'))
AIR_MAX = 0xf8


def cls(pw, xw):
    if pw == xw: return 'ok'
    xb = struct.pack('>I', xw)
    if struct.pack('<I', pw) == xb: return 'raw'
    if struct.pack('<I', pw) == xb[1::-1] + xb[3:1:-1]: return 'u16'
    return 'other'


def data_block(s, e):
    if not s.reloc or len(s.data) < 0xcc: return None
    r = R.parse(bytes(s.reloc), e)
    t = dict(r.internal).get(0xc8)
    if t is None or t + AIR_MAX + 2 > len(s.data): return None
    return t


def id_map(XD, PD):
    """{Xbox type-7 id: PC id of its position partner} (tools/converter_faults_fix.pairs_by_position: the converter keeps
    the section order). The id must be translated, not only byte-swapped: base-game DTP ids are renumbered on the PC
    (2026-11-04, agent N11: the Xbox costumes' breath ids 1161 / 1162 are PC 962 / 963 - the base pair x_lara 12647 /
    pc_lara 850 and all six played B138 DLC 1 costumes hold 0x3c2 / 0x3c3 there, while the PC file's own 1161 / 1162
    are other DTPs). Ids whose copies pair with different PC ids are left out (no repair)."""
    import converter_faults_fix as CF
    m = collections.defaultdict(set)
    for _, x, p in CF.pairs_by_position(XD, PD):
        if x.type == 7 and p.type == 7: m[x.id].add(p.id)
    return {k: next(iter(v)) for k, v in m.items() if len(v) == 1}


def check_fields(SP, SX, ids, label, fixes, out=print, pmap=None):
    """pmap (id_map): the repaired value is the PC id of the section the Xbox id names; without pmap (scan) the Xbox
    value itself (only right for ids that are the same on both platforms, e.g. new DLC DTPs)"""
    counts = collections.Counter()
    xs = {s.id: s for s in SX if s.type == 7}
    for p in SP:
        if p.type != 7: continue
        x = xs.get(p.id)
        if x is None or len(x.data) != len(p.data): continue
        bp, bx = data_block(p, 'le'), data_block(x, 'be')
        if bp is None or bp != bx: continue
        air = struct.unpack_from('<h', p.data, bp + AIR_MAX)[0]
        for off, what in FIELDS:
            o = bp + off
            pw = struct.unpack_from('<I', p.data, o)[0]; xw = struct.unpack_from('>I', x.data, o)[0]
            c = cls(pw, xw)
            counts[c] += 1
            named = xw in ids if pmap is None else xw in pmap
            want = xw if pmap is None else pmap.get(xw)
            if c == 'ok': continue          # most DTPs have a +0xc8 pointer; only differing words are of interest
            if pmap is not None and want is not None and want != xw and pw == want: continue   # translated already
            out('%s7:%-6d data +0x%05x field +0x%02x (%s): PC 0x%08x Xbox 0x%08x %-5s %s; data +0xf8 = %d' % (
                label, p.id, bp, off, what, pw, xw, c, ('names a section' if pmap is None else
                                                        'names DTP %d = PC DTP %d' % (xw, want)) if named
                else 'not a section id', air))
            # repair only the proven class: the Xbox u32 names a section of the same file, the PC holds its u16 pair
            if c == 'u16' and named and xw and fixes is not None:
                fixes.setdefault(p.id, []).append((o, want))
    return counts


def fix_drm(XD, PD):
    """library (tools/dlc_struct_fixes.py step 'objid'): the proven class only (fields +0x94 / +0x98 of the +0xc8 data
    block, class u16, the Xbox u32 names a type-7 section of the Xbox file; the value written is the PC id of that
    section's position partner, id_map) - never the generic candidates of `scan`.
    Sets the words in PD's sections in place; returns (changes [(section index, off, old 4 bytes, new 4 bytes)],
    lines, counts). Every PC copy of a DTP id is checked on its own against the Xbox section of that id (as
    check_fields), and only the words found in that copy are set in that copy."""
    ids = {s.id for s in PD.sections}
    pmap = id_map(XD, PD)
    lines, changes, c = [], [], collections.Counter()
    for k, s in enumerate(PD.sections):
        if s.type != 7: continue
        fixes = {}
        c.update(check_fields([s], XD.sections, ids, '', fixes, out=lines.append, pmap=pmap))
        if not fixes: continue
        d = bytearray(s.data)
        for o, v in sorted(set(fixes[s.id])):
            new = struct.pack('<I', v)
            changes.append((k, o, bytes(d[o:o + 4]), new)); d[o:o + 4] = new
        PD.sections[k] = DW.Section(s.type, s.id, bytes(d), s.reloc, s.flags, s.ver, s.spec, s.pad)
    return changes, lines, c


def generic(SP, SX, ids, label):
    counts = collections.Counter()
    xs = {s.id: s for s in SX if s.type == 7}
    for p in SP:
        if p.type != 7: continue
        x = xs.get(p.id)
        if x is None or len(x.data) != len(p.data): continue
        r = R.parse(bytes(p.reloc), 'le') if p.reloc else None
        skip = set(r.pointer_offsets()) | set(r.id_offsets()) if r else set()
        for o in range(0, len(p.data) - 3, 4):
            xw = struct.unpack_from('>I', x.data, o)[0]
            # ids below 0x1000 are mostly counts / indices (scan 2026-11-04: 4982 candidates with them, all small values)
            if xw < 0x1000 or xw > 0x7fff or o in skip: continue
            if struct.unpack_from('<I', p.data, o)[0] != xw << 16 or xw not in ids: continue
            counts['candidate'] += 1
            print('%s7:%-6d +0x%05x PC 0x%08x Xbox 0x%08x (u16 pair of an id that names a section)' % (
                label, p.id, o, xw << 16, xw))
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
    # every byte outside the repaired words is unchanged
    DI = DW.read(open(path, 'rb').read(), 'le')
    changed = 0
    for a, b in zip(DI.sections, DR.sections):
        if a.data != b.data:
            changed += sum(1 for i in range(len(a.data)) if a.data[i] != b.data[i])
    print('wrote %s: %d words in %d section copies (ids %s), %d bytes differ from the input, readback ok' % (
        out, n, sum(1 for s in D.sections if s.type == 7 and s.id in fixes), sorted(fixes), changed))


def write_md5(tree):
    mods = os.path.join(tree, 'mods')
    rows = []
    for dp, dn, fn in os.walk(mods):
        for f in sorted(fn):
            q = os.path.join(dp, f)
            rows.append((hashlib.md5(open(q, 'rb').read()).hexdigest(), os.path.relpath(q, mods).replace('\\', '/')))
    with open(os.path.join(tree, 'md5.tsv'), 'w', newline='\n') as h:
        h.write('md5\tpath\n')
        for m, q in sorted(rows, key=lambda r: r[1]): h.write('%s\t%s\n' % (m, q))
    print('wrote %s (%d files)' % (os.path.join(tree, 'md5.tsv'), len(rows)))


def main(argv):
    if len(argv) < 2: print(__doc__); return 2
    if argv[0] == 'scan':
        import pickle
        W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic', 'dlc_drms.pkl')
        C = pickle.load(open(W, 'rb'))
        base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
        byname = {}
        for k, v in C.items(): byname.setdefault(base(k[1]), []).append(v)
        tot = collections.Counter(); files = 0
        for top in argv[1:]:
            for dp, dn, fn in os.walk(top):
                for f in sorted(fn):
                    if not f.lower().endswith('.drm') or base(f) not in byname: continue
                    files += 1
                    DP = DW.read(open(os.path.join(dp, f), 'rb').read(), 'le')
                    h, secs = byname[base(f)][0]
                    SX = [DW.Section(s['type'], s['id'], s['data'], s['reloc'], s['flags'], s['ver'], s['spec'])
                          for s in secs if s['type'] == 7]
                    ids = {s.id for s in DP.sections}
                    c = check_fields(DP.sections, SX, ids, f + ' ', None)
                    g = generic(DP.sections, SX, ids, f + ' ')
                    if c or g: print('%s: fields %s, generic %s' % (f, dict(c), dict(g)))
                    tot.update(('field', k) for k in c.elements()); tot.update(('generic', k) for k in g.elements())
        print('total over %d files: %s' % (files, dict(tot)))
        return 0
    if argv[0] != 'check' or len(argv) < 3: print(__doc__); return 2
    DX = DW.read(open(argv[1], 'rb').read(), 'be'); DP = DW.read(open(argv[2], 'rb').read(), 'le')
    ids = {s.id for s in DP.sections}
    fixes = {} if '--out' in argv else None
    c = check_fields(DP.sections, DX.sections, ids, '', fixes, pmap=id_map(DX, DP))
    print('counts (class): %s' % dict(c))
    if fixes is not None:
        if not fixes: print('nothing to repair - %s not written' % argv[argv.index('--out') + 1])
        else: apply(argv[2], argv[argv.index('--out') + 1], fixes)
    if '--md5' in argv: write_md5(argv[argv.index('--md5') + 1])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
