"""Section-id words that the converter wrote as two u16 (or left raw) although the structure holds a u32 id - three
structure rules for the generic candidates of tools/objdata_idword_fix.py `scan` (night 04.11., agent N12, workspace
docs Befund-Restrisiken-0411.md, task B). Read-only unless --out.

Rules (Xbox original big-endian, paired with the converted PC DRM; the expected PC value is the little-endian u32 of
the PC id of the DTP the Xbox id names - its position partner, objdata_idword_fix.id_map):
  R1 sound record   a 28-byte record {u8 0x50 + 3 bytes, u32 0, bytes 03 00 00 00, u32 DTP id, u32 count, 0, 0} in a
                    DTP (thrall sound tables; the id names a SoundPlex DTP, root node type 4). Proof: Crystal's PC
                    base game stores this word as the u32 PC id (tools/idcand_basepair.py viking_thrall.drm /
                    yeti_thrall.drm "50......0000000003000000" --rel 0xc: 6 / 6 and 7 / 7 matches renumbered u32
                    ids; the tag, the 03 bytes and the count have the same byte classes in base and DLC).
  R2 own-id node    a 16-byte node {u32 1, internal pointer, u32 id of the containing DTP, u32 0} (SoundPlex type-1
                    node list in doppelganger_casual DTP 20212). Proof: every other node of that list holds the own id
                    as u32 (converted s32); the reader tru+0x1920e9 uses only +4, so the word is wrong but inert.
  R3 table record   DTP head +0x34 = u16 count n, +0x38 = internal pointer P; n records of 0x24 bytes at P, record
                    +0x14 = id of a type-7 section of the same file (dlc_fx_cine_object DTP 26644: record 0 names
                    table DTP 26711 as u32, record 1 names table DTP 25700 left raw = 0x64640000). Proof: the same
                    field of the sibling record is u32; an id above 0x7fff is never valid (section table 0..0x7fff).
Repaired (rules in --repair, default R1 only): words of class u16 (each u16 half swapped) or raw (the Xbox bytes left)
whose Xbox u32 names a type-7 section of the Xbox file with a unique PC partner; every other mismatch is reported.
Why not R2 / R3 by default (night 04.11.): R2 is not read by the SoundPlex walker (tru+0x1920b0 reads node +0 / +4
only) - wrong but inert; R3 records are 0x24 bytes on the Xbox and 0x28 on the PC (Crystal's base-game files, tools/
fxrec_layout.py basepair: record 1 always 4 bytes later, extra word 0), so a DLC-new R3 DTP needs the record array
re-laid (tools/fxrec_relayout_fix.py), not a single word.
`basepair NAME ...` runs the rules on Crystal's own PC build of base-game files (proof of the u32 class).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/dlc_idpair_fix.py check PC.drm [--xbox XBOX.drm] [--pack pack11] [--repair R1[,R2,R3]]
        [--out OUT.drm] [--md5 TREE]
  ../bin/pyt -t 3600 tools/dlc_idpair_fix.py scan DIR [--pack pack11]
  ../bin/pyt -t 1800 tools/dlc_idpair_fix.py basepair NAME [NAME ...]
  XBOX default: convert_dlc.raw_dlc(file name) with TRUDLC_PACK_FIRST=--pack (pack11 = DLC 2, pack10 = DLC 1)
  --md5 TREE writes TREE/md5.tsv (md5 + path relative to TREE/mods) after --out
  ../bin/pyt -t 900 tools/dlc_idpair_fix.py proof      R1 on Crystal's base pairs, pinned counts (exit 1 otherwise)
Library (step `idpair` of tools/dlc_struct_fixes.py, 2026-11-11 Q5 = the R1 words of the played tree dlc_test51i_ids):
  proven() -> (ok, counts) once per process; fix_drm(XD, raw) -> (new raw or None, changes, counts), proven write
  (decoded DRM differs only in the planned bytes, headers / relocations identical, re-check 0).
"""
import sys, os, struct, collections, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import objdata_idword_fix as OI

# R1 base proof (Q5 2026-11-11): Crystal's PC viking_thrall / yeti_thrall hold every R1 id as the u32 PC id
BASE_PROOF = ('viking_thrall.drm', 'yeti_thrall.drm')
PROOF_EXPECT = {'R1 ok': 13, 'R1 to repair': 0}     # calibrated 2026-11-11 (6 viking + 7 yeti R1 records, all u32)


def u16pair(v):
    """PC bytes when the Xbox u32 v was converted as two u16 (each half byte-swapped)"""
    b = struct.pack('>I', v)
    return b[1::-1] + b[3:1:-1]


def xbox_doc(name, pack, path):
    if path: return DW.read(open(path, 'rb').read(), 'be')
    import convert_dlc as CD
    old = os.environ.get('TRUDLC_PACK_FIRST'); os.environ['TRUDLC_PACK_FIRST'] = pack
    try: raw, _ = CD.raw_dlc(name)
    finally:
        if old is None: os.environ.pop('TRUDLC_PACK_FIRST', None)
        else: os.environ['TRUDLC_PACK_FIRST'] = old
    return DW.read(raw, 'be') if raw else None


def sites(x):
    """[(rule, offset of the id word)] in Xbox DTP x"""
    d = x.data; out = []
    it = dict(R.parse(bytes(x.reloc), 'be').internal) if x.reloc else {}
    for o in range(0, len(d) - 0x1b, 4):
        if d[o] == 0x50 and d[o + 4:o + 8] == b'\0\0\0\0' and d[o + 8:o + 12] == b'\x03\0\0\0' \
                and d[o + 0x14:o + 0x1c] == b'\0' * 8 and o + 0xc not in it:
            out.append(('R1', o + 0xc))
    for o in range(0, len(d) - 0xf, 4):
        if struct.unpack_from('>I', d, o)[0] == 1 and (o + 4) in it and struct.unpack_from('>I', d, o + 8)[0] == x.id \
                and struct.unpack_from('>I', d, o + 12)[0] == 0:
            out.append(('R2', o + 8))
    if len(d) >= 0x3c and 0x38 in it:
        n = struct.unpack_from('>H', d, 0x34)[0]; p = it[0x38]
        if 0 < n <= 64 and p + 0x24 * n <= len(d):
            for k in range(n): out.append(('R3', p + 0x24 * k + 0x14))
    return out


def check_doc(XD, PD, label='', log=print, repair=('R1',)):
    """(changes [(section index, off, old, new, rule)], counts); only rules in `repair` produce changes"""
    pmap = OI.id_map(XD, PD)
    xids = {s.id for s in XD.sections if s.type == 7}
    import converter_faults_fix as CF
    st = collections.Counter(); changes = []
    for k, x, p in CF.pairs_by_position(XD, PD):
        if x.type != 7 or p.type != 7 or len(x.data) != len(p.data): continue
        for rule, o in sites(x):
            xv = struct.unpack_from('>I', x.data, o)[0]
            if rule == 'R3' and xv not in xids: continue        # R3: only record fields that name a section
            if xv == 0: st[rule + ' zero'] += 1; continue
            want = pmap.get(xv)
            pb = bytes(p.data[o:o + 4]); pv = struct.unpack('<I', pb)[0]
            if want is None:
                st[rule + ' unmapped'] += 1
                log('%s%s 7:%d +0x%x Xbox id %d not a type-7 section of this file (PC u32 0x%x) - left' % (
                    label, rule, p.id, o, xv, pv)); continue
            if pv == want: st[rule + ' ok'] += 1; continue
            xb = struct.pack('>I', xv)
            c = 'u16' if pb == u16pair(xv) else 'raw' if pb == xb else None
            if c:
                st[rule + ' ' + c] += 1
                fix = rule in repair
                if fix: changes.append((k, o, pb, struct.pack('<I', want), rule))
                log('%s%s 7:%d +0x%x PC 0x%08x (%s) -> %d (Xbox %d)%s' % (label, rule, p.id, o, pv,
                    'u16 pair' if c == 'u16' else 'Xbox bytes left', want, xv, '' if fix else ' - reported only'))
            else:
                st[rule + ' other'] += 1
                log('%s%s 7:%d +0x%x PC 0x%08x, Xbox %d, expected %d - other, left' % (label, rule, p.id, o, pv, xv, want))
    return changes, st


def apply(path, PD, changes, out):
    secs = list(PD.sections)
    for k in sorted({c[0] for c in changes}):
        d = bytearray(secs[k].data)
        for kk, o, old, new, rule in changes:
            if kk == k:
                assert bytes(d[o:o + 4]) == old; d[o:o + 4] = new
        s = secs[k]
        secs[k] = DW.Section(s.type, s.id, bytes(d), s.reloc, s.flags, s.ver, s.spec, s.pad)
    D = DW.Drm(secs, PD.names, PD.pad, PD.ver, PD.u0, PD.u1)
    raw = D.write('le'); src = open(path, 'rb').read()
    if src[:4] == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(raw)
    DR = DW.read(open(out, 'rb').read(), 'le'); DI = DW.read(src, 'le')
    assert [(a.type, a.id, a.reloc, a.flags) for a in DR.sections] == [(b.type, b.id, b.reloc, b.flags) for b in DI.sections]
    words = 0; other = 0
    for a, b in zip(DI.sections, DR.sections):
        if a.data == b.data: continue
        for o in range(0, len(a.data), 4):
            if a.data[o:o + 4] != b.data[o:o + 4]:
                if any(o == c[1] for c in changes): words += 1
                else: other += 1
    print('wrote %s: %d words changed (%d planned), %d other words, sections/relocations unchanged, readback ok' % (
        out, words, len(changes), other))
    return other == 0 and words == len(changes)


def proof_counts():
    """R1 on Crystal's own PC base pairs (BASE_PROOF): counts of check_doc; 'R1 to repair' must be 0"""
    import dtp_word_classes as C
    mk = lambda secs: DW.Drm([DW.Section(s['type'], s['id'], s['data'] or b'', s['reloc'] or b'') for s in secs])
    tot = collections.Counter()
    for name in BASE_PROOF:
        X = C.find(C.BASE, 'be', 'xenon-w' + C.BS + name); P = C.find(C.PC, 'le', 'pc-w' + C.BS + name)
        if X is None or P is None: tot['no base pair'] += 1; continue
        ch, st = check_doc(mk(X), mk(P), name + ' ', log=lambda *a: None, repair=('R1',))
        tot.update({k: v for k, v in st.items() if k.startswith('R1')})
        tot['R1 to repair'] += len(ch)
    tot.setdefault('R1 to repair', 0)
    return dict(tot)


_PROVEN = []


def proven():
    """(ok, counts) of the R1 base proof, once per process: ok = no base R1 word to repair and the pinned counts"""
    if not _PROVEN:
        got = proof_counts()
        _PROVEN.append((got.get('R1 to repair', 1) == 0 and got == PROOF_EXPECT, got))
    return _PROVEN[0]


def fix_drm(XD, raw):
    """step idpair (R1 only) on one DRM -> (new raw or None, changes [(k, off, old, new, rule)], counts). Proven write:
    the decoded DRM differs only in the planned bytes, section headers / relocations / names identical, re-check 0
    (AssertionError otherwise)."""
    PD = DW.read(raw, 'le')
    ch, st = check_doc(XD, PD, '', log=lambda *a: None, repair=('R1',))
    if not ch: return None, [], st
    for k in sorted({c[0] for c in ch}):
        d = bytearray(PD.sections[k].data)
        for kk, o, old, new, rule in ch:
            if kk == k:
                assert bytes(d[o:o + 4]) == old; d[o:o + 4] = new
        PD.sections[k].data = bytes(d)
    out = PD.write('le')
    if raw[:4] == b'CDRM': out = DW.cdrm_encode(out, 'le')
    D0, D1 = DW.read(raw, 'le'), DW.read(out, 'le')
    assert len(D0.sections) == len(D1.sections) and (D0.names, D0.pad, D0.ver) == (D1.names, D1.pad, D1.ver), 'header changed'
    planned = {(k, o + j) for k, o, a, b, r in ch for j in range(4) if a[j] != b[j]}
    for k, (a, b) in enumerate(zip(D0.sections, D1.sections)):
        assert (a.type, a.id, a.flags, a.reloc, len(a.data)) == (b.type, b.id, b.flags, b.reloc, len(b.data)), 'section changed'
        if a.data != b.data:
            assert {(k, i) for i in range(len(a.data)) if a.data[i] != b.data[i]} == {q for q in planned if q[0] == k}, 'unplanned bytes'
    again, _ = check_doc(XD, D1, '', log=lambda *a: None, repair=('R1',))
    assert not again, 're-check %d words' % len(again)
    return out, ch, st


def main(argv):
    def opt(n, d):
        if n in argv:
            k = argv.index(n); v = argv[k + 1]; del argv[k:k + 2]; return v
        return d
    pack = opt('--pack', 'pack11'); xp = opt('--xbox', None); out = opt('--out', None); md5 = opt('--md5', None)
    rep = opt('--repair', 'R1')
    if argv == ['proof']:
        ok, got = proven()
        print('idpair R1 base proof %s: %s%s' % ('PROVEN' if ok else 'FAILED', got,
                                                 '' if got == PROOF_EXPECT else ' (expected %s)' % PROOF_EXPECT))
        return 0 if ok else 1
    if len(argv) < 2: print(__doc__); return 2
    if argv[0] == 'basepair':          # the rules on Crystal's own PC build of base-game files: proof of the u32 class
        import dtp_word_classes as C
        tot = collections.Counter()
        for name in argv[1:]:
            X = C.find(C.BASE, 'be', 'xenon-w' + C.BS + name); P = C.find(C.PC, 'le', 'pc-w' + C.BS + name)
            if X is None or P is None: print('%s: no base pair' % name); continue
            mk = lambda secs: DW.Drm([DW.Section(s['type'], s['id'], s['data'] or b'', s['reloc'] or b'') for s in secs])
            ch, st = check_doc(mk(X), mk(P), name + ' ')
            print('%s: %s' % (name, dict(st))); tot.update(st)
        print('total: %s' % dict(tot))
        return 0
    if argv[0] == 'scan':
        tot = collections.Counter(); files = 0
        for dp, dn, fn in os.walk(argv[1]):
            for f in sorted(fn):
                if not f.lower().endswith('.drm'): continue
                try: XD = xbox_doc(f, pack, None)
                except Exception: XD = None
                if XD is None: continue
                files += 1
                PD = DW.read(open(os.path.join(dp, f), 'rb').read(), 'le')
                ch, st = check_doc(XD, PD, f + ' ')
                if st: print('%s: %s' % (f, dict(st)))
                tot.update(st)
        print('total over %d files with an Xbox original: %s' % (files, dict(tot)))
        return 0
    if argv[0] != 'check': print(__doc__); return 2
    path = argv[1]
    XD = xbox_doc(os.path.basename(path), pack, xp)
    if XD is None: sys.exit('no Xbox original')
    PD = DW.read(open(path, 'rb').read(), 'le')
    ch, st = check_doc(XD, PD, repair=tuple(rep.split(',')))
    print('counts: %s; %d words to repair' % (dict(st), len(ch)))
    if out:
        if not ch: print('nothing to repair - %s not written' % out)
        elif not apply(path, PD, ch, out): sys.exit('apply check failed')
    if md5: OI.write_md5(md5)
    return 1 if (ch and not out) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
