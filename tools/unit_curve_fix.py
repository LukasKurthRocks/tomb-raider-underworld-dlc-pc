"""Unit-DTP curve records: the 64-entry u16 curve of every record is a u16 array (s16 words) - step `unitcurve` of
tools/dlc_struct_fixes.py (Q32, 2026-11-11; workspace docs Befund-Introtyped-1111.md, decision 7 of Status-2026-11-08).

The unit DTP (Level +0x74 target) holds regions of fixed-size records that end with the marker beebbeeb and carry a
64-entry u16 curve (on the Xbox a monotone ramp, mostly 0x0000 .. 0xffff):
  stride 0xc0: ..., float +0x30, u16[64] +0x34 .. +0xb3, u32 +0xb4, beebbeeb +0xb8   (regions root/+6c/*)
  stride 0xb0: ..., float +0x20, u16[64] +0x24 .. +0xa3, u32 +0xa4, 0 +0xa8, beebbeeb +0xac   (e.g. root/+1fc/+50)
The generic converter route (learned type-7 table: class per word from the Xbox value shape) wrote single words of
these ramps as s32 wherever the u16 pair looked like a float (38e33cf4, 41044514, b2cab6db ...), so the PC curve is
not monotone any more (installed DLC 2 tree 11.11.: ceremony 6 / goo_room 4 / machine_room 25 records broken). The
path-table part of step introtyped repairs most of them, but not the units whose PC unit DTP has another layout
(dlc2_machine_room 25392, +2 jump-target intros) or regions without enough base votes (ceremony root/+6c/+54 0x300),
and it leaves dlc_yggdrasil_hall02 23100 +0x6268 alone (TABLE_EXCLUDE: fp rule s32 against path table s16) - that
word is in a 0xb0 curve record (... 30d7 | 366b 3c03 | 419f ...): s16, decided here.
Rule: in every pointer-target region of the unit DTP reached from the root whose Xbox records ALL carry the marker of
one layout, paired with the PC region of the same pointer-path label and size (typed_family_fix.labels), the 32 curve
words of every record whose PC record carries the marker as well = s16 of the Xbox word; a word changes only where
the PC word is another byte order of the Xbox word (others are counted as kept); pointer / id slots are left alone.
Base-mapped unit DTPs (PC id != Xbox id: the PC game's own section) are left alone, as in introtyped.
Proof (base, pinned): every curve record of the base unit pairs (typed_family_fix.table_units, 77 units): each curve
word PC = s16 of the Xbox word (ok), s16 = another order (amb: symmetric bytes), else contra (must be 0).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/unit_curve_fix.py proof              pinned base counts (exit 1 otherwise)
  ../bin/pyt -t 3600 tools/unit_curve_fix.py scan TREE [--pack pack11] [--names a.drm,b.drm] [--report R.json]
        per DRM the words the step would change (nothing written); exit 1 when any
Library (step unitcurve): proven() -> (ok, counts) once per process; fix_drm(XD, raw) -> (new raw or None, changes
  [(section index, offset, old, new, section id)], info dict(rows, kept, notes)); proven write (decoded DRM differs
  only in the planned bytes, headers / relocations identical, re-plan 0 - AssertionError otherwise).
"""
import sys, os, json, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_write as DW, drm_reloc as R
import typed_family_fix as TF

BEEB = b'\xbe\xeb\xbe\xeb'
LAYOUTS = ((0xc0, 0x34, 0xb8), (0xb0, 0x24, 0xac))    # record stride, u16[64] curve offset, beebbeeb offset
CURVE = 0x80                                           # 64 u16
# the root lists the curve regions hang below (base: root/+6c/* 0xc0 and 0xb0 records, root/+6c/+NNN/* and root/+1fc/*
# 0xb0 records); regions directly at a root pointer with the same marker stride are other records (floats / counts:
# l2_norsehub / l4_traprooms / l7_arctic_sea ... root/* 0xc0, 259 base words NOT s16) and are not this rule
ROOT_LISTS = ('+6c', '+1fc')
PROOF_EXPECT = {'units': 20, 'regions': 230, 'records': 556, 'ok': 12893, 'amb': 4899, 'slot': 0, 'pc_marker_missing': 0,
                'contra': 0}    # calibrated 2026-11-11 (Q32) over the 77 base unit pairs (20 have curve regions)


def s16(w): return bytes((w[1], w[0], w[3], w[2]))


def layout(d, rs, sz, be):
    """(stride, curve offset, marker offset) of a region whose records all end in the marker, or None"""
    m = BEEB if be else BEEB[::-1]
    for st, co, mo in LAYOUTS:
        if sz < st or sz % st: continue
        if all(d[rs + r + mo:rs + r + mo + 4] == m for r in range(0, sz, st)): return st, co, mo
    return None


def region_pairs(ux, px, IX, up, pp, IP):
    """[(label, Xbox start, PC start, size)] of the root-reached regions with the same label and size on both sides"""
    xd, pd = bytes(ux.data), bytes(up.data)
    LX, _ = TF.labels(xd, px, IX, lambda k: '?')     # intro names do not matter: only root-reached labels are used
    LP, _ = TF.labels(pd, pp, IP, lambda k: '?')
    bx = {v[0]: (t, v[1]) for t, v in LX.items() if v[0][0] == 'root'}
    bp = {v[0]: (t, v[1]) for t, v in LP.items() if v[0][0] == 'root'}
    return [(lab, bx[lab][0], bp[lab][0], bx[lab][1]) for lab in sorted(set(bx) & set(bp)) if bx[lab][1] == bp[lab][1]]


def curve_words(ux, px, IX, up, pp, IP, st=None):
    """[(PC offset, Xbox word, PC word, label)] of every curve word of the paired curve regions (slots skipped)"""
    st = st if st is not None else collections.Counter()
    xd, pd = bytes(ux.data), bytes(up.data)
    sx, sp = TF.slots(ux, 'be'), TF.slots(up, 'le')
    out = []
    for lab, tx, tp, sz in region_pairs(ux, px, IX, up, pp, IP):
        if len(lab) < 3 or lab[1] not in ROOT_LISTS: continue
        L = layout(xd, tx, sz, True)
        if L is None: continue
        stride, co, mo = L
        st['regions'] += 1
        for r in range(0, sz, stride):
            if pd[tp + r + mo:tp + r + mo + 4] != BEEB[::-1]: st['pc_marker_missing'] += 1; continue
            st['records'] += 1
            for q in range(co, co + CURVE, 4):
                xo, po = tx + r + q, tp + r + q
                if xo in sx or po in sp: st['slot'] += 1; continue
                out.append((po, xd[xo:xo + 4], pd[po:po + 4], '/'.join(lab)))
    return out


def proof_counts():
    got = collections.Counter(); units = set()
    for name, ux, px, IX, up, pp, IP in TF.table_units():
        n0 = got['records']
        for po, xw, pw, lab in curve_words(ux, px, IX, up, pp, IP, got):
            want = s16(xw)
            if pw != want: got['contra'] += 1
            elif len({TF.xperm(xw, c) for c in TF.XPERMS}) == 1 or want in (xw, xw[::-1]): got['amb'] += 1
            else: got['ok'] += 1
        if got['records'] > n0: units.add(name)
    got['units'] = len(units)
    for k in ('slot', 'pc_marker_missing', 'contra', 'regions', 'records', 'ok', 'amb'): got.setdefault(k, 0)
    return dict(got)


_PROVEN = []


def proven():
    """(ok, counts) of the base proof once per process: ok = 0 contradicting base words and the pinned counts"""
    if not _PROVEN:
        got = proof_counts()
        _PROVEN.append((got.get('contra', 1) == 0 and got == PROOF_EXPECT, got))
    return _PROVEN[0]


def plan(XD, PD):
    """-> dict(rows=[(PC section index, offset, Xbox word, PC word, wanted word, label)], kept=[...], notes=[...])"""
    rows, kept, notes = [], [], []
    kp, kx = TF.unit_dtp(PD, 'le'), TF.unit_dtp(XD, 'be')
    if kp is None or kx is None: return dict(rows=rows, kept=kept, notes=notes)
    u, ux = PD.sections[kp], XD.sections[kx]
    if u.id != ux.id:
        notes.append('unit DTP %d = Xbox %d (base-mapped) - left alone' % (u.id, ux.id))
        return dict(rows=rows, kept=kept, notes=notes)
    IP, pp = TF.intros(u, 'le'); IX, px = TF.intros(ux, 'be')
    st = collections.Counter()
    for po, xw, pw, lab in curve_words(ux, px, IX, u, pp, IP, st):
        want = s16(xw)
        if pw == want: continue
        t = (kp, po, xw, pw, want, lab)
        (rows if TF.byteorder(xw, pw) else kept).append(t)
    if st['pc_marker_missing']:
        notes.append('unit DTP %d: %d records without the PC marker - skipped' % (u.id, st['pc_marker_missing']))
    return dict(rows=rows, kept=kept, notes=notes)


def fix_drm(XD, raw):
    ok, got = proven()
    if not ok: raise SystemExit('unitcurve: base proof FAILED - %s (expected %s)' % (got, PROOF_EXPECT))
    PD = DW.read(raw, 'le')
    info = plan(XD, PD)
    if not info['rows']: return None, [], info
    changes = []
    for k, o, xw, pw, want, lab in info['rows']:
        s = PD.sections[k]; d = bytearray(s.data)
        assert bytes(d[o:o + 4]) == pw
        d[o:o + 4] = want; s.data = bytes(d)
        changes.append((k, o, pw, want, s.id))
    out = PD.write('le')
    if raw[:4] == b'CDRM': out = DW.cdrm_encode(out, 'le')
    dec0, dec1 = DW.cdrm_decode(raw, 'le'), DW.cdrm_decode(out, 'le')
    D0, D1 = DW.read(raw, 'le'), DW.read(out, 'le')
    assert D0.write('le') == bytes(dec0), 'writer not lossless'
    assert len(dec0) == len(dec1) and len(D0.sections) == len(D1.sections), 'size / section count changed'
    assert (D0.names, D0.pad, D0.ver, D0.u0, D0.u1) == (D1.names, D1.pad, D1.ver, D1.u0, D1.u1), 'file header changed'
    base = 24 + 20 * len(D0.sections) + len(D0.names) + len(D0.pad); bases = []
    for a, b in zip(D0.sections, D1.sections):
        assert (a.type, a.id, a.flags, a.ver, a.spec, a.pad, a.reloc, len(a.data)) == \
               (b.type, b.id, b.flags, b.ver, b.spec, b.pad, b.reloc, len(b.data)), 'section header / relocation changed'
        bases.append(base + len(a.reloc)); base += len(a.reloc) + len(a.data)
    planned = {bases[k] + o + j for k, o, a, b, sid in changes for j in range(4) if a[j] != b[j]}
    diff = {i for i in range(len(dec0)) if dec0[i] != dec1[i]}
    assert diff == planned, 'byte diff %d != planned %d' % (len(diff), len(planned))
    assert not plan(XD, D1)['rows'], 're-plan not empty'
    return out, changes, info


def main(argv):
    a = list(argv)
    rep = None; names = None
    if '--report' in a: k = a.index('--report'); rep = a[k + 1]; del a[k:k + 2]
    if '--pack' in a: k = a.index('--pack'); os.environ['TRUDLC_PACK_FIRST'] = a[k + 1]; del a[k:k + 2]
    if '--names' in a: k = a.index('--names'); names = set(a[k + 1].split(',')); del a[k:k + 2]
    if a == ['proof']:
        ok, got = proven()
        print('unitcurve base proof %s: %s%s' % ('PROVEN' if ok else 'FAILED', got,
                                                 '' if got == PROOF_EXPECT else ' (expected %s)' % PROOF_EXPECT))
        return 0 if ok else 1
    if len(a) != 2 or a[0] != 'scan': print(__doc__); return 2
    import dtp_audit as DA
    from convert_dlc import raw_dlc
    from drm import cdrm_decode
    out = []; tot = 0
    for rel, path in sorted(DA.overlay([os.path.abspath(t) for t in a[1].split(',')], names).items()):
        xr, src = raw_dlc(rel.replace('/', '\\'))
        if xr is None: xr, src = raw_dlc(os.path.basename(rel))
        if xr is None: continue
        XD = DW.read(cdrm_decode(xr, 'be'), 'be')
        new, ch, info = fix_drm(XD, open(path, 'rb').read())
        if ch or info['kept'] or info['notes']:
            print('unitcurve %-50s %d words, %d kept (no byte order)%s' % (rel, len(ch), len(info['kept']),
                  ('; ' + '; '.join(info['notes'])) if info['notes'] else ''), flush=True)
            out.append(dict(rel=rel, words=len(ch), kept=len(info['kept']), notes=info['notes'],
                            changes=['%d +%#x %s -> %s' % (c[4], c[1], c[2].hex(), c[3].hex()) for c in ch]))
        tot += len(ch)
    print('scan: %d words in %d DRMs' % (tot, sum(1 for o in out if o['words'])))
    if rep: json.dump(out, open(rep, 'w', encoding='utf-8'), indent=1)
    return 1 if tot else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
