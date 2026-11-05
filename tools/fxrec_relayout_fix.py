"""Re-lay the record array of 'table record' DTPs (rule R3 of tools/dlc_idpair_fix.py) from the Xbox layout (stride
0x24) to the PC layout (stride 0x28) - read-only unless --out. Night 04.11., agent N12, workspace docs
Befund-Restrisiken-0411.md, task B.

Structure (Xbox DTP): head +0x34 = u16 count n, +0x38 = pointer P to n records; record = {+0x00 4 bytes, +0x04 u32
colour, +0x08 4 bytes, +0x0c 4 bytes, +0x10 4 bytes, +0x14 u32 id of a type-7 section (12736-byte tables), +0x18..
+0x23 zero}. Crystal's own PC base-game files (tools/fxrec_layout.py basepair, 8 files, 16 records): every record is
0x28 bytes (record 1 sits 4 bytes later, the extra word is 0), field layouts +0x00 u16u16 (or u8u8u16 - equal when
bytes 0 / 1 agree), +0x04 u32, +0x08 u8u8u16, +0x0c u16u16, +0x10 u16u16, +0x14 u32 PC id. The DTP keeps its size:
with n = 2 the Xbox array 0x48 bytes is followed by 8 bytes of 16-byte-alignment padding, the PC array uses them.
The converter keeps the Xbox stride for DLC-new DTPs (7 DTPs in DLC 2: torch sml / tiny / tongue, cine object,
goo cannonball, goo upcolumn pit with n = 2, bloom with n = 4) and mixes the byte classes from record 1 on, so the
PC engine reads record 1 four bytes off (and its table id as 0x....0000 garbage).

Rebuild: the n records are written from the Xbox bytes with the layouts above at stride 0x28, the id as the u32 PC id
of the Xbox id's position partner (objdata_idword_fix.id_map). Only done when the bytes [P + 0x24 n, P + 0x28 n) are
zero on the Xbox and no relocation (pointer source, pointer target other than P, id reference) lies inside
[P, P + 0x28 n); otherwise reported ('no room', e.g. bloom n = 4).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/fxrec_relayout_fix.py basepair NAME [NAME ...]   proof: rebuild = Crystal's PC bytes?
  ../bin/pyt -t 900 tools/fxrec_relayout_fix.py check PC.drm [--pack pack11] [--out OUT.drm] [--md5 TREE]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import objdata_idword_fix as OI

LAYOUT = {0x00: 'u16u16', 0x04: 'u32', 0x08: 'u8u8u16', 0x0c: 'u16u16', 0x10: 'u16u16'}
PERMS = {'u32': (3, 2, 1, 0), 'u16u16': (1, 0, 3, 2), 'u8u8u16': (0, 1, 3, 2)}
XS, PS = 0x24, 0x28


def table_dtp(x, xids):
    """(n, P) when x is a table-record DTP of this structure, else None"""
    rel = R.parse(bytes(x.reloc), 'be') if x.reloc else R.Reloc()
    it = dict(rel.internal); d = x.data
    if len(d) < 0x3c or 0x38 not in it: return None
    n = struct.unpack_from('>H', d, 0x34)[0]; P = it[0x38]
    if not (2 <= n <= 64 and P + XS * n <= len(d)): return None
    for j in range(n):
        r = P + XS * j
        if struct.unpack_from('>I', d, r + 0x14)[0] not in xids or d[r + 0x18:r + XS] != b'\0' * 12: return None
    return n, P


def rebuild(x, n, P, pmap):
    """(PC bytes of the n records at stride 0x28, problems)"""
    d = x.data; out = bytearray(); bad = []
    for j in range(n):
        r = P + XS * j; rec = bytearray(PS)
        for w, lay in LAYOUT.items():
            xb = d[r + w:r + w + 4]
            if w == 0 and xb[0] != xb[1]: bad.append('record %d +0: bytes 0/1 differ (u16u16 vs u8u8u16 open)' % j)
            rec[w:w + 4] = bytes(xb[i] for i in PERMS[lay])
        xv = struct.unpack_from('>I', d, r + 0x14)[0]
        if xv not in pmap: bad.append('record %d id %d has no unique PC partner' % (j, xv))
        else: struct.pack_into('<I', rec, 0x14, pmap[xv])
        out += rec
    return bytes(out), bad


def room(x, n, P):
    rel = R.parse(bytes(x.reloc), 'be') if x.reloc else R.Reloc()
    lo, hi = P, P + PS * n
    if x.data[P + XS * n:hi] != b'\0' * (hi - P - XS * n): return 'padding not zero'
    if any(lo <= o < hi for o, t in rel.internal): return 'pointer source inside'
    if any(lo < t < hi for o, t in rel.internal): return 'pointer target inside'
    if any(lo <= o < hi for o in rel.id_offsets()): return 'id reference inside'
    if any(lo <= so < hi for si, so, do in rel.external): return 'external reference inside'
    return None


def plan(XD, PD, label, log=print):
    import converter_faults_fix as CF
    pmap = OI.id_map(XD, PD)
    xids = {s.id for s in XD.sections if s.type == 7}
    st = collections.Counter(); edits = []
    for k, x, p in CF.pairs_by_position(XD, PD):
        if x.type != 7 or p.type != 7 or len(x.data) != len(p.data): continue
        t = table_dtp(x, xids)
        if not t: continue
        n, P = t
        new, bad = rebuild(x, n, P, pmap)
        cur = bytes(p.data[P:P + PS * n])
        if cur == new: st['ok (PC layout)'] += 1; log('%s7:%d n=%d P=+0x%x: already PC layout' % (label, p.id, n, P)); continue
        why = room(x, n, P)
        if bad or why:
            st['left'] += 1
            log('%s7:%d n=%d P=+0x%x: differs, left (%s)' % (label, p.id, n, P, '; '.join(bad + ([why] if why else []))))
            continue
        nd = sum(1 for w in range(0, PS * n, 4) if cur[w:w + 4] != new[w:w + 4])
        st['relaid'] += 1
        log('%s7:%d n=%d P=+0x%x: re-laid, %d of %d words differ from the converted bytes' % (label, p.id, n, P, nd, PS * n // 4))
        edits.append((k, P, cur, new))
    return edits, st


def main(argv):
    def opt(n, d):
        if n in argv:
            k = argv.index(n); v = argv[k + 1]; del argv[k:k + 2]; return v
        return d
    pack = opt('--pack', 'pack11'); out = opt('--out', None); md5 = opt('--md5', None)
    if len(argv) < 2: print(__doc__); return 2
    if argv[0] == 'basepair':
        import dtp_word_classes as C
        import converter_faults_fix as CF
        mk = lambda secs: DW.Drm([DW.Section(s['type'], s['id'], s['data'] or b'', s['reloc'] or b'') for s in secs])
        tot = collections.Counter()
        for name in argv[1:]:
            X = C.find(C.BASE, 'be', 'xenon-w' + C.BS + name); P_ = C.find(C.PC, 'le', 'pc-w' + C.BS + name)
            if X is None or P_ is None: print('%s: no base pair' % name); continue
            XD, PD = mk(X), mk(P_)
            pmap = OI.id_map(XD, PD); xids = {s.id for s in XD.sections if s.type == 7}
            for k, x, p in CF.pairs_by_position(XD, PD):
                if x.type != 7 or p.type != 7 or len(x.data) != len(p.data): continue
                t = table_dtp(x, xids)
                if not t: continue
                n, P = t
                new, bad = rebuild(x, n, P, pmap)
                cur = bytes(p.data[P:P + PS * n])
                diff = [hex(w) for w in range(0, PS * n, 4) if cur[w:w + 4] != new[w:w + 4]]
                tot['equal' if not diff else 'DIFF'] += 1
                print('%s 7:%d / PC 7:%d n=%d: rebuild %s Crystal\'s PC bytes%s%s' % (
                    name, x.id, p.id, n, '==' if not diff else '!=', (' (words %s)' % diff) if diff else '',
                    (' ' + '; '.join(bad)) if bad else ''))
        print('total: %s' % dict(tot))
        return 0
    if argv[0] != 'check': print(__doc__); return 2
    import dlc_idpair_fix as F
    path = argv[1]
    XD = F.xbox_doc(os.path.basename(path), pack, None)
    if XD is None: sys.exit('no Xbox original')
    src = open(path, 'rb').read(); PD = DW.read(src, 'le')
    edits, st = plan(XD, PD, '')
    print('counts: %s' % dict(st))
    if out and edits:
        secs = list(PD.sections)
        for k, P, cur, new in edits:
            s = secs[k]; d = bytearray(s.data); assert bytes(d[P:P + len(cur)]) == cur
            d[P:P + len(new)] = new
            secs[k] = DW.Section(s.type, s.id, bytes(d), s.reloc, s.flags, s.ver, s.spec, s.pad)
        raw = DW.Drm(secs, PD.names, PD.pad, PD.ver, PD.u0, PD.u1).write('le')
        if src[:4] == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        open(out, 'wb').write(raw)
        DR = DW.read(open(out, 'rb').read(), 'le')
        same_meta = [(a.type, a.id, a.reloc, a.flags, len(a.data)) for a in DR.sections] == \
                    [(b.type, b.id, b.reloc, b.flags, len(b.data)) for b in PD.sections]
        outside = 0
        for i, (a, b) in enumerate(zip(PD.sections, DR.sections)):
            rng = [(P, P + len(new)) for k, P, cur, new in edits if k == i]
            for o in range(0, len(a.data)):
                if a.data[o] != b.data[o] and not any(lo <= o < hi for lo, hi in rng): outside += 1
        print('wrote %s: %d DTPs re-laid, sizes / relocations unchanged %s, bytes changed outside the arrays %d, '
              'readback ok' % (out, len(edits), same_meta, outside))
        if not same_meta or outside: sys.exit('apply check failed')
    elif out:
        print('nothing to do - %s not written' % out)
    if md5: OI.write_md5(md5)
    return 1 if (edits and not out) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
