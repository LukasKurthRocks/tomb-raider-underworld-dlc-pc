"""Object ids (u16) the converter left as the Xbox id: typed record fields, base proof, gate and fix (Q110 / group E1,
2026-11-12, workspace docs Befund-Gruppe-E1-1211.md).

Object ids differ Xbox / PC for the 821 base objects (35 equal; work/generic/merged/object_id_remap_xbox_to_pc.json,
tools/objlists.py); DLC objects (>= 822) keep their id. The learned type-7 table remaps an object id only where its
label key learned the class id16:11 on the base pairs; a DLC DTP without a base twin of that key keeps the Xbox value.
Q97 found one: the DLC 2 default gear list DTP 25270 gives gear 51 = Xbox `g_pda`, on the PC 51 = `g_tanks` (PC
`g_pda` = 48), so the PC doppelganger got diving tanks instead of the PDA.

Record classes (each proven on every base Xbox / PC pair that has it; the systematic search of E1 over all DLC 1 / DLC 2
DTPs of work/rebuild/pipeline_check_1111c found no other proven class, docs section Q110 b):
  GEAR   default gear lists of a unit: level (section 0) +0x70 -> environment block, +0x2b4 -> {u32 DTP id A, u32 DTP
         id B} (player message handler 0x7200ba..0x72011b, ENGINE 20.6), each list DTP {+0 u16* weapons, +4 n,
         +8 u16* gear, +0xc n}; every entry = object id (given by 0x7198d0 -> 0x716130). Base proof: 81 units,
         1466 distinct entries (1493 counting list B where it is the same DTP as A), all PC = remap(Xbox), all
         renumbered, 0 contradicting.
  CHUNK  chunkdoll object data (object DTP +0xc8 -> D, D+2 u16 type 0x3b, D+4 u16 0xb00b): D+8 u16 = object id of the
         creature (yeti_thrall 363 -> 705). Base proof: the 3 base chunkdolls (viking / yeti / panther thrall), 3 / 3
         PC = remap(Xbox), 0 contradicting. Reader of D+8 not found (the chunkdoll create 0x696f90 takes the
         chunkdoll object from message 0x180 of the enemy); the field is set like the base game.
Rule: the PC u16 field := LE u16 of the PC id of the Xbox object NAME (Xbox list of the source pack -> PC object list),
only where the PC field holds the untranslated Xbox id; any other PC value is UNEXPECTED (left, check fails).

Modes (from the repository root; read-only except fix):
  ../bin/pyt -t 1800 tools/object_id_field_fix.py proof            base proof (exit 1 on a contradiction / other counts)
  ../bin/pyt -t 1800 tools/object_id_field_fix.py scan DIR [--pack pack11]   exit 1 when a field is wrong / unexpected
  ../bin/pyt -t 1800 tools/object_id_field_fix.py fix SRC_DIR OUT_DIR [--pack pack11]   writes changed DRMs
Library: fix_drm(XD, raw, pack) -> (new raw or None, changes, info); proven() -> (ok, lines) once per process.
Pipeline step 'objfield' in tools/dlc_struct_fixes.py (after waveid).
"""
import sys, os, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_write as DW, drm_reloc as R

ROOT = os.path.dirname(HERE)
LISTS = os.path.join(ROOT, 'work', 'generic', 'lists')
BASE_XLIST, BASE_PLIST = os.path.join(LISTS, 'xbox_objectlist.txt'), os.path.join(LISTS, 'pc_objectlist.txt')
DLC_PLIST = os.path.join(ROOT, 'work', 'generic', 'merged', 'tr8', 'pc-w', 'objectlist.txt')
PROOF_EXPECT = {'GEAR': 1466, 'CHUNK': 3}     # base fields, each list DTP once per unit (all renumbered); 2026-11-12
CHUNK_TYPE = 0x3b
_LISTS = {}


def objlist(path):
    """{id: name} of an object list file (first line = count)"""
    if path not in _LISTS:
        d = {}
        for line in open(path, encoding='utf-8', errors='replace').read().splitlines()[1:]:
            if ',' in line:
                i, n = line.split(',', 1); d[int(i)] = n.strip().lower()
        _LISTS[path] = d
    return _LISTS[path]


def pc_id(xid, xlist, plist):
    """PC id of the Xbox object id by name, or None (unknown / ambiguous)"""
    n = objlist(xlist).get(xid)
    if n is None: return None
    ids = [i for i, m in objlist(plist).items() if m == n]
    return ids[0] if len(ids) == 1 else None


class Img:
    """sections of one DRM (drm_write.Drm) with a pointer map per section: offset -> (section index, target)"""
    def __init__(self, D, e):
        self.D = D; self.E = '>' if e == 'be' else '<'; self.ptr = []
        self.dtp = {s.id: i for i, s in enumerate(D.sections) if s.type == 7}
        for i, s in enumerate(D.sections):
            r = R.parse(bytes(s.reloc), e) if s.reloc else R.Reloc()
            m = {o: (i, t) for o, t in r.internal}
            for si, src, dst in r.external: m[src] = (si, dst)
            self.ptr.append(m)

    def deref(self, loc, off):
        return self.ptr[loc[0]].get(loc[1] + off) if loc else None

    def u32(self, loc, off):
        return struct.unpack_from(self.E + 'I', self.D.sections[loc[0]].data, loc[1] + off)[0]

    def u16(self, k, o):
        return struct.unpack_from(self.E + 'H', self.D.sections[k].data, o)[0]


def fields(img):
    """[(class, section index, field offset, what)] of the object id fields of one DRM"""
    out = []
    D = img.D
    # GEAR: level env +0x2b4 lists (unit DRMs; section 0 = level)
    if D.sections and D.sections[0].type == 0:
        try:
            g = img.deref(img.deref((0, 0), 0x70), 0x2b4)
        except Exception:
            g = None
        if g is not None:
            seen = set()
            for tag, k in (('A', 0), ('B', 4)):
                did = img.u32(g, k)
                if did not in img.dtp or did in seen: continue
                seen.add(did); p = (img.dtp[did], 0)
                for kind, h in (('weapon', 0), ('gear', 8)):
                    q = img.deref(p, h); n = img.u32(p, h + 4)
                    if q is None or n > 64 or q[0] != p[0]: continue
                    for i in range(n):
                        out.append(('GEAR', q[0], q[1] + 2 * i, 'list DTP %d %s[%d]' % (did, kind, i)))
    # CHUNK: chunkdoll object data D+8
    for i, s in enumerate(D.sections):
        if s.type != 7: continue
        t = img.ptr[i].get(0xc8)
        if t is None or t[0] != i or t[1] + 0x10 > len(s.data): continue
        if img.u16(i, t[1] + 2) == CHUNK_TYPE and img.u16(i, t[1] + 4) == 0xb00b:
            out.append(('CHUNK', i, t[1] + 8, 'chunkdoll data DTP %d +0x%x D+8' % (s.id, t[1])))
    return out


def pair_fields(XD, PD):
    """[(class, x section, x offset, p section, p offset, what)] - fields of the Xbox source and the PC file paired by
    class and order (DTP ids differ Xbox / PC for base-game DTPs, e.g. gear list 15911 -> 11546); a class whose field
    count or in-section offsets differ is not paired (listed in miss)"""
    xi, pi = Img(XD, 'be'), Img(PD, 'le')
    xf, pf = fields(xi), fields(pi)
    out, miss = [], []
    for cl in ('GEAR', 'CHUNK'):
        a = [f for f in xf if f[0] == cl]; b = [f for f in pf if f[0] == cl]
        if len(a) != len(b) or any(f[2] != g[2] for f, g in zip(a, b)):
            miss += ['%s: Xbox %d fields, PC %d (offsets differ)' % (cl, len(a), len(b))] if (a or b) else []
            continue
        out += [(cl, f[1], f[2], g[1], g[2], g[3]) for f, g in zip(a, b)]
    return out, miss, xi, pi


def plan(XD, PD, pack=None, xlist=None, plist=None):
    """rows [(class, p section, offset, DTP id, Xbox id, PC value, wanted, status, what)]; status ok / fix / unmapped
    (no unique PC object of that name) / UNEXPECTED (PC value neither the Xbox id nor the wanted id)"""
    xlist = xlist or os.path.join(LISTS, 'dlc_%s_objectlist.txt' % (pack or 'pack11'))
    plist = plist or DLC_PLIST
    pairs, miss, xi, pi = pair_fields(XD, PD)
    rows = []
    for c, xk, xo, pk, po, w in pairs:
        xv = xi.u16(xk, xo); pv = pi.u16(pk, po)
        want = pc_id(xv, xlist, plist) if xv not in (0, 0xffff) else xv
        if want is None: st = 'unmapped'
        elif pv == want: st = 'ok'
        elif pv == xv: st = 'fix'
        else: st = 'UNEXPECTED'
        rows.append((c, pk, po, PD.sections[pk].id, xv, pv, want, st, w))
    return rows, miss


def fix_drm(XD, raw, pack=None):
    """-> (new raw or None, changes [(section index, offset, old u16, new u16, DTP id, class, what)], info)"""
    PD = DW.read(raw, 'le')
    rows, miss = plan(XD, PD, pack)
    info = dict(rows=rows, miss=miss)
    todo = [r for r in rows if r[7] == 'fix']
    if not todo: return None, [], info
    changes = []
    for c, k, o, sid, xv, pv, want, st, w in todo:
        s = PD.sections[k]; b = bytearray(s.data)
        assert struct.unpack_from('<H', b, o)[0] == pv
        struct.pack_into('<H', b, o, want); s.data = bytes(b)
        changes.append((k, o, pv, want, sid, c, w))
    new = PD.write('le')
    if raw[:4] == b'CDRM': new = DW.cdrm_encode(new, 'le')
    verify(raw, new, changes, XD, pack)
    return new, changes, info


def verify(raw, new, changes, XD, pack=None):
    A, B = DW.read(raw, 'le'), DW.read(new, 'le')
    assert len(A.sections) == len(B.sections) and A.names == B.names and A.pad == B.pad, 'file layout changed'
    planned = set()
    for k, o, a, b, sid, c, w in changes:
        x, y = struct.pack('<H', a), struct.pack('<H', b)
        planned |= {(k, o + j) for j in range(2) if x[j] != y[j]}
    got = set()
    for k, (a, b) in enumerate(zip(A.sections, B.sections)):
        assert (a.type, a.id, a.flags, a.ver, a.spec, a.pad, bytes(a.reloc), len(a.data)) == \
               (b.type, b.id, b.flags, b.ver, b.spec, b.pad, bytes(b.reloc), len(b.data)), 'section %d header changed' % k
        if a.data != b.data: got |= {(k, i) for i in range(len(a.data)) if a.data[i] != b.data[i]}
    assert got == planned, '%d bytes differ, %d planned' % (len(got), len(planned))
    again = [r for r in plan(XD, B, pack)[0] if r[7] == 'fix']
    assert not again, 're-plan finds %d fields' % len(again)
    return len(got)


# ------------------------------------------------------------------------------------------------------------ proof
def proof(verbose=False):
    """every base Xbox / PC DRM pair (work/generic pair cache): each GEAR / CHUNK field = PC id of the Xbox name.
    -> (ok, lines)"""
    from generic_cache import load_pairs
    lines = []; c = collections.Counter(); bad = 0
    P = load_pairs(patch=False)
    for nm, (x, p) in sorted(P.items()):
        try:
            XD = _drm(x[1]); PD = _drm(p[1])
        except Exception:
            continue
        rows, miss = plan(XD, PD, xlist=BASE_XLIST, plist=BASE_PLIST)
        for r in rows:
            cl, st = r[0], r[7]
            c[(cl, st)] += 1
            if r[4] != r[5]: c[(cl, 'renumbered')] += 1
            if st != 'ok':
                bad += 1; lines.append('CONTRA %s %s DTP %d +0x%x Xbox %d PC %d want %s (%s)' % (nm, cl, r[3], r[2], r[4], r[5], r[6], r[8]))
            elif verbose:
                lines.append('ok %s %s DTP %d +0x%x Xbox %d -> PC %d' % (nm, cl, r[3], r[2], r[4], r[5]))
        if miss: lines.append('unpaired fields %s: %s' % (nm, miss[:4]))
    for cl, n in PROOF_EXPECT.items():
        got = c[(cl, 'ok')]
        if got != n or c[(cl, 'renumbered')] != n:
            bad += 1; lines.append('COUNT %s: %d ok / %d renumbered, expected %d' % (cl, got, c[(cl, 'renumbered')], n))
    lines.append('proof: %s; %d contradicting -> %s' % (', '.join('%s %s %d' % (k[0], k[1], v) for k, v in sorted(c.items())),
                                                        bad, 'ok' if not bad else 'FAIL'))
    return not bad, lines


def _drm(secs):
    """section dicts of the pair cache -> a drm_write.Drm-like object (sections with type, id, data, reloc)"""
    class S: pass
    class Dm: pass
    D = Dm(); D.sections = []
    for s in secs:
        o = S(); o.type, o.id = s['type'], s['id']; o.data = s['data'] or b''; o.reloc = s.get('reloc') or b''
        D.sections.append(o)
    return D


_PROVEN = None
def proven():
    global _PROVEN
    if _PROVEN is None: _PROVEN = proof()
    return _PROVEN


# ------------------------------------------------------------------------------------------------------------ CLI
def _xbox(rel, pack):
    os.environ['TRUDLC_PACK_FIRST'] = pack
    from convert_dlc import raw_dlc
    from drm import cdrm_decode
    raw, _ = raw_dlc(rel.replace('/', '\\'))
    if raw is None: raw, _ = raw_dlc(os.path.basename(rel))
    return DW.read(cdrm_decode(raw, 'be'), 'be') if raw is not None else None


def _files(d):
    out = {}
    for r, _, fs in os.walk(d):
        for f in fs:
            if f.lower().endswith('.drm'): out[os.path.relpath(os.path.join(r, f), d).replace('\\', '/')] = os.path.join(r, f)
    return out


def cmd_scan(d, pack, out=None):
    c = collections.Counter(); n = 0
    for rel, path in sorted(_files(d).items()):
        raw = open(path, 'rb').read(); PD = DW.read(raw, 'le')
        if not fields(Img(PD, 'le')): continue
        XD = _xbox(rel, pack)
        if XD is None: c['no_xbox'] += 1; continue
        if out is not None:
            new, ch, info = fix_drm(XD, raw, pack)
            if new is not None:
                q = os.path.join(out, rel); os.makedirs(os.path.dirname(q), exist_ok=True); open(q, 'wb').write(new)
                n += 1
                for k, o, a, b, sid, cl, w in ch: print('fix %s %s DTP %d +0x%x %d -> %d (%s)' % (rel, cl, sid, o, a, b, w))
            rows = info['rows']
        else:
            rows, _ = plan(XD, PD, pack)
        for r in rows:
            c[(r[0], r[7])] += 1
            if r[7] != 'ok' and out is None:
                print('%s %s %s DTP %d +0x%x Xbox %d PC %d want %s (%s)' % (r[7], rel, r[0], r[3], r[2], r[4], r[5], r[6], r[8]))
    bad = sum(v for (cl, st), v in c.items() if st != 'ok' and (out is None or st != 'fix'))
    print('scan %s (%s): %s%s -> %s' % (d, pack, ', '.join('%s %s %d' % (k[0], k[1], v) for k, v in sorted(c.items(), key=str)),
                                         ('; written %d DRMs to %s' % (n, out)) if out else '', 'ok' if not bad else 'FAIL'))
    return 1 if (bad and out is None) else 0


def main(argv):
    pack = 'pack11'
    if '--pack' in argv: k = argv.index('--pack'); pack = argv[k + 1]; del argv[k:k + 2]
    if argv[:1] == ['proof']:
        ok, lines = proof('-v' in argv)
        for l in lines: print(l)
        return 0 if ok else 1
    if argv[:1] == ['scan'] and len(argv) == 2: return cmd_scan(argv[1], pack)
    if argv[:1] == ['fix'] and len(argv) == 3: return cmd_scan(argv[1], pack, argv[2])
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
