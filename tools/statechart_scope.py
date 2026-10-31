"""Scope of the state-chart conversion defect (finding 43, rock vein follow-up): find every state-chart-like DTP and
measure a converted PC tree against its Xbox source. Read-only.

Families (base player lara.drm: Xbox 12647 / 12646 / 2517 = PC 850 / 849 / 848; DLC 2 doppelganger_casual.drm:
20212 / 20172 / 20134 (+ its copy 24392)):
  chart  the state chart: words 3..6 = 10000, 12000, 4000, 6000 (big-endian u32 at +0xc)
  table  the chart's 16-byte record table: first u16 0x2001, u8 at +4, u16 0x15 at +8 (Xbox)
  alist  the pointer / id-ref list: word 0 = own id or 0, word 1 = 0, word 2 relocated, u16 count at +0xc,
         at least one id-ref word
  cond   any other DTP with >= 8 condition records by tools/statechart_cond_fix.py's rule

Modes:
  base IDX_JSON [MINSIZE]   list chart DTPs of a base archive index (tools/index_all.py output, e.g.
                            work/idx_xbox_base.json, work/idx_pc.json): reads only records with a type-7 section of at
                            least MINSIZE bytes (default 0x40000)
  tree TU_IMAGE PC_TREE PACK [PACK ...]
                            every DRM of the PC tree (sub folders included): Xbox source from the first PACK
                            (tools/locals.py keys, e.g. pack11 pack10) that holds the name; per family DTP with a PC
                            section of the same id and size: condition records (proven layout u16 key, u16 id, u16
                            value, u8 flags, u8) wrong / total, transitions (20 bytes, pointers +8 / +0xc, "hhhhppw")
                            wrong / total, and word statistics (PC word = raw / u32-swapped / u16-swapped Xbox word)
  file TU_IMAGE XBOX.drm PC.drm
                            the same for one pair of files

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/statechart_scope.py tree work/xenia_dump/tu_image_82000000.bin work/rebuild/dlc2_asm_stage2b/mods pack11 pack10
"""
import sys, os, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import statechart_cond_fix as SC

HDR = struct.pack('>4I', 10000, 12000, 4000, 6000)
TRANS_SIZE, TRANS_PTRS, TRANS_LAYOUT = 0x14, (8, 0xc), 'hhhhppw'


def family(s, d, rel_ids, ncond):
    if len(d) >= 0x1c and d[0xc:0x1c] == HDR: return 'chart'
    if len(d) >= 0x20 and len(d) % 4 == 0 and d[0:2] == b'\x20\x01' and d[8:10] == b'\x00\x15' and d[2:4] == b'\0\0':
        return 'table'
    w0, w1 = struct.unpack_from('>2I', d, 0) if len(d) >= 0x10 else (None, None)
    if w0 in (s.id, 0) and w1 == 0 and 8 in rel_ids[0] and rel_ids[1] and d[0xe:0x10] == b'\0\0' and \
            struct.unpack_from('>H', d, 0xc)[0] > 0:
        return 'alist'
    if ncond >= 8: return 'cond'
    return None


def transitions(d, internal):
    import shape_proof as SP
    return SP.shaped(d, internal, TRANS_SIZE, TRANS_PTRS)


def measure(xs, ps, ids):
    """counts for one Xbox / PC section pair of the same size"""
    xd, pd = bytes(xs.data), bytes(ps.data)
    xr, pr = R.parse(bytes(xs.reloc), 'be'), R.parse(bytes(ps.reloc), 'le')
    skip = set(xr.pointer_offsets()) | set(xr.id_offsets()) | set(pr.pointer_offsets()) | set(pr.id_offsets())
    m = collections.Counter()
    for o, k, i, v, f6, f7 in SC.records(xd, '>', ids, skip):
        m['cond'] += 1
        if pd[o:o + 8] != struct.pack('<3H', k, i, v) + bytes((f6, f7)): m['cond_bad'] += 1
    import shape_proof as SP
    for a in transitions(xd, dict(xr.internal)):
        m['trans'] += 1
        y = SP.convert(xd[a:a + TRANS_SIZE], TRANS_LAYOUT)
        if any(pd[a + o:a + o + 4] != y[o:o + 4] for o in range(0, TRANS_SIZE, 4) if a + o not in skip): m['trans_bad'] += 1
    for o in range(0, len(xd) - 3, 4):
        if o in skip: continue
        x = xd[o:o + 4]; p = pd[o:o + 4]
        m['words'] += 1
        fits = [n for n, y in (('raw', x), ('u32', x[::-1]), ('u16', x[1::-1] + x[:1:-1])) if p == y]
        if len(fits) == 1: m[fits[0]] += 1
        elif fits: m['ambig'] += 1                  # e.g. zero words: every byte order gives the same bytes
        else: m['other'] += 1
    return m


def pairs_of(X, P, ids):
    """[(family, xbox section, pc section or None)] for the family DTPs of one Xbox DRM"""
    pc = {}
    for s in P.sections:
        if s.type == 7: pc.setdefault(s.id, []).append(s)
    out = []
    for s in X.sections:
        if s.type != 7: continue
        d = bytes(s.data)
        r = R.parse(bytes(s.reloc), 'be')
        ptr, idw = set(r.pointer_offsets()), set(r.id_offsets())
        n = 0
        if len(d) >= 8 and d[0xc:0x1c] != HDR:
            n = len(SC.records(d, '>', ids, ptr | idw))
        fam = family(s, d, (ptr, idw), n)
        if fam is None: continue
        cand = [p for p in pc.get(s.id, ()) if len(p.data) == len(d)]
        # duplicate ids (e.g. 2517 twice in lara.drm): pair by "first word zero or not"
        best = cand[0] if cand else None
        if len(cand) > 1:
            best = next((p for p in cand if (struct.unpack_from('<I', p.data, 0)[0] == 0) == (d[:4] == b'\0\0\0\0')), cand[0])
        out.append((fam, s, best))
    return out


def report(name, X, P, ids, rows):
    for fam, s, p in pairs_of(X, P, ids):
        if p is None:
            print('%-40s DTP %6d %-5s 0x%06x  no PC section of the same id / size' % (name, s.id, fam, len(s.data)))
            rows.append({'file': name, 'dtp': s.id, 'family': fam, 'size': len(s.data), 'pc': None}); continue
        m = measure(s, p, ids)
        print('%-40s DTP %6d %-5s 0x%06x  cond %5d/%5d  trans %4d/%4d  words %6d: raw %6d u32 %6d u16 %6d other %5d'
              % (name, s.id, fam, len(s.data), m['cond_bad'], m['cond'], m['trans_bad'], m['trans'], m['words'],
                 m['raw'], m['u32'], m['u16'], m['other']))
        rows.append(dict(file=name, dtp=s.id, family=fam, size=len(s.data), **m))


def xbox_drm(rel, packs):
    import locals as LC
    from archive import Archive
    from names import crc
    from drm import cdrm_decode
    for k in packs:
        path, e, pre = LC.SRC[k]
        A = xbox_drm.cache.get(k) or xbox_drm.cache.setdefault(k, Archive(path, e))
        for nm in (rel.replace('/', '\\'), os.path.basename(rel)):
            r = [x for x in A.find(crc(pre + '\\' + nm)) if x['spec'] == 0xffffffff]
            if r: return DW.read(cdrm_decode(A.read(r[0]), e), e), k
    return None, None
xbox_drm.cache = {}


def cmd_base(idx, mins):
    from archive import Archive
    from drm import cdrm_decode
    from names import load as load_names, L as NAME_DIR
    recs = json.load(open(idx))
    arch = {}
    for rec in recs:
        path, i, h, spec, n, secs = rec[:6]
        if not isinstance(secs, list) or not any(s[0] == 7 and s[2] >= mins for s in secs): continue
        e = 'be' if 'Patched' in path or 'Xenia' in path else 'le'
        A = arch.get(path) or arch.setdefault(path, Archive(path, e))
        try:
            D = DW.read(cdrm_decode(A.read(A.idx[i]), e), e)
        except Exception as ex:
            print('%s #%d: not readable (%s)' % (os.path.basename(path), i, ex)); continue
        for s in D.sections:
            d = bytes(s.data)
            if s.type != 7 or len(d) < 0x1c: continue
            hd = d[0xc:0x1c] if e == 'be' else b''.join(d[k:k + 4][::-1] for k in range(0xc, 0x1c, 4))
            if hd == HDR:
                print('%s #%d hash %08x spec %08x: chart DTP %d 0x%x bytes' % (os.path.basename(path), i, h, spec, s.id, len(d)))


def main(argv):
    mode = argv[0]
    if mode == 'base':
        cmd_base(argv[1], int(argv[2], 0) if len(argv) > 2 else 0x40000); return
    out_json = None
    if '--json' in argv: k = argv.index('--json'); out_json = argv[k + 1]; del argv[k:k + 2]
    ids = SC.tu_ids(open(argv[1], 'rb').read())
    rows = []
    if mode == 'file':
        X = DW.read(open(argv[2], 'rb').read(), 'be'); P = DW.read(open(argv[3], 'rb').read(), 'le')
        report(os.path.basename(argv[3]), X, P, ids, rows)
    elif mode == 'tree':
        tree, packs = argv[2], argv[3:]
        import dtp_audit as DA
        files = DA.overlay([os.path.abspath(tree)], None)
        nx = 0
        for rel, path in sorted(files.items()):
            X, k = xbox_drm(rel, packs)
            if X is None: continue
            nx += 1
            try:
                P = DW.read(open(path, 'rb').read(), 'le')
            except Exception as ex:
                print('%s: PC not readable (%s)' % (rel, ex)); continue
            report(rel, X, P, ids, rows)
        print('%d DRMs in the tree, %d with an Xbox source' % (len(files), nx))
    else:
        raise SystemExit(__doc__)
    if out_json: json.dump(rows, open(out_json, 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
