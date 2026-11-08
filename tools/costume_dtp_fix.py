"""Costume DTP fix (P4a, 2026-11-07, workspace docs Befund-P4a-Kostueme-0711.md): two typed rules for the DLC costume
DRMs (dlc_costume_<x>.drm). Every new word is computed from the Xbox / TU source bytes with the field type; the upstream
B270 kit is only a cross-check (--his), never a source.

Rule MESH16 - model DTP (Xbox word 0 = 0x04c20453, the converter's MODEL_MAGIC), header (big-endian on Xbox):
    +0x20 u32 nv, +0x24 ptr -> vertex array  nv * 10 B  (five u16 per vertex)
    +0x30 u32 nq, +0x34 ptr -> index array   nq *  8 B  (four u16 vertex indices per entry)
  Both arrays are pure u16 data: on PC every u16 is byte-swapped on its own (s16 / u16 pair). A 4-byte word that the
  converter swapped as ONE u32 (float-shaped pairs such as Xbox 43b6 43e2 = indices 17334, 17378) moves each index to
  the other half and swaps its bytes (17334 -> 0xe243 = 57923 > nv) -> wrong / out-of-range triangles on the costume.
  Proof (`prove`): base-game Lara model DTPs, Xbox (tu / xbase2 / xbase) vs genuine PC (pcpatch / pcbig) - every word of
  both arrays must be the u16 swap; every Xbox index must be < nv (= they are vertex indices).
Rule LISTCOUNT - DTP {.., +0x04 ptr -> +0x10, +0x10 u32 n, +0x14 ptr -> +0x30, n pointers at +0x30 ..}:
  n is the length of the pointer list (the relocations hold exactly n slots from +0x30) -> PC = s32 of the Xbox count.
  The converter remapped the count as if it were a DTP id (22 -> 21, 18 -> 17): PC then reads one list entry less.
  Proof (`prove`): the same struct in the base Lara DRMs, PC count = s32 of Xbox count in every pair.

Scan gate (`scan` / `fix`): a word is planned only when (a) the section is paired to its Xbox section (same size and
internal pointer layout), (b) the struct check of the rule holds on the Xbox bytes (array sizes = next pointer target,
indices < nv, n pointer slots), (c) the old PC word is a byte permutation of the Xbox word (MESH16; LISTCOUNT: old PC
value != Xbox value, i.e. remapped) - else the word is reported and kept.
Proofs on every written DRM: read back, decompressed DRM differs from the input only in the planned bytes, section
headers + relocation blobs identical, a second plan on the output plans 0 words.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/costume_dtp_fix.py prove [NAME ...]          (default: the base Lara costume DRMs)
  ../bin/pyt -t 1800 tools/costume_dtp_fix.py scan DIR[,DIR..] [--his HIS_MODS] [-v]
  ../bin/pyt -t 1800 tools/costume_dtp_fix.py fix DIR[,DIR..] OUT_MODS [--check] [--his HIS_MODS]
      DIR[,DIR..] = overlay (later folder wins); every dlc_costume_*.drm found is handled; OUT_MODS gets only changed DRMs
Library (step `costumedtp` of tools/dlc_struct_fixes.py, 2026-11-08): fix_drm(raw, rel) -> (new raw or None, changes,
  report lines, Xbox source), proven like `fix` (prove_write)
"""
import sys, os, struct, hashlib, collections, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_write as DW
import tuning_word_audit as TA
from objdata_fx_fix import data_bases

MODEL_MAGIC = bytes.fromhex('04c20453')
VSTRIDE, QSTRIDE = 10, 8
BASE_NAMES = ['lara', 'lara_bikini', 'lara_casual', 'lara_jungle_a', 'lara_jungle_b', 'lara_jungle_heavy',
              'lara_snow_heavy', 'lara_snow_light', 'lara_wetsuit_cold', 'lara_wetsuit_warm', 'lara_doppelganger',
              'lara_mom_thrall']
XORDER = ('pack10', 'pack11', 'pack1', 'pack2', 'pack20', 'tu', 'xbase2', 'xbase')


def internal(reloc, endian):
    return dict(R.parse(reloc, endian).internal)


def u16_spans(xd, it):
    """MESH16 spans [(start, end, what)] of a model DTP from the Xbox bytes, or (None, reason)"""
    if xd[:4] != MODEL_MAGIC or len(xd) < 0x80: return None, 'no model DTP'
    tg = sorted(set(it.values()) | {len(xd)})
    out = []
    nv = struct.unpack_from('>I', xd, 0x20)[0]
    for cnt_o, ptr_o, stride, what in ((0x20, 0x24, VSTRIDE, 'vertex'), (0x30, 0x34, QSTRIDE, 'index')):
        a = it.get(ptr_o); n = struct.unpack_from('>I', xd, cnt_o)[0]
        if a is None or not n: return None, '%s: no pointer / count' % what
        nx = tg[bisect.bisect_right(tg, a)]
        e = a + stride * n
        if a % 2 or e > nx or nx - e > 3: return None, '%s array +0x%x n %d: end +0x%x != next target +0x%x' % (what, a, n, e, nx)
        out.append((a, e, what))
    a, e, _ = out[1]
    mx = max(struct.unpack_from('>%dH' % ((e - a) // 2), xd, a))
    return out, 'nv %d, nq %d, max index %d' % (nv, struct.unpack_from('>I', xd, 0x30)[0], mx)


def listcount(xd, it):
    """LISTCOUNT struct check on the Xbox bytes: n or None"""
    if len(xd) < 0x34 or it.get(0x04) != 0x10 or it.get(0x14) != 0x30: return None
    n = struct.unpack_from('>I', xd, 0x10)[0]
    if not 0 < n < 0x400 or 0x30 + 4 * n > len(xd): return None
    if not all((0x30 + 4 * j) in it for j in range(n)) or (0x30 + 4 * n) in it: return None
    return n


def plan_section(xd, xreloc, pd, slots_le=None):
    """{offset: (old, new, rule, note)} and [report lines] for one paired type-7 section"""
    it = internal(xreloc, 'be')
    xr = R.parse(xreloc, 'be')
    slots = set(xr.pointer_offsets()) | set(xr.id_offsets())
    ch, rep = {}, []
    if xd[:4] == MODEL_MAGIC:
        sp, why = u16_spans(xd, it)
        if sp is None:
            rep.append('MESH16 not provable: ' + why)
        else:
            rep.append('MESH16 struct ok: %s; vertex +0x%x..+0x%x, index +0x%x..+0x%x' % (why, sp[0][0], sp[0][1], sp[1][0], sp[1][1]))
            inspan = bytearray(len(xd))
            for a, e, _ in sp:
                for q in range(a, e): inspan[q] = 1
            lo, hi = sp[0][0] & ~3, (sp[1][1] + 3) & ~3
            for o in range(lo, min(hi, len(xd) // 4 * 4), 4):
                if not any(inspan[o:o + 4]): continue
                xw, old = xd[o:o + 4], pd[o:o + 4]
                new = bytearray(old)
                for h in (0, 2):
                    if inspan[o + h] and inspan[o + h + 1]: new[h], new[h + 1] = xw[h + 1], xw[h]
                new = bytes(new)
                if new == old: continue
                if o in slots: rep.append('MESH16 +0x%x: relocated slot - kept' % o); continue
                if sorted(old) != sorted(xw):
                    rep.append('MESH16 +0x%x: old %s is no permutation of Xbox %s - kept' % (o, old.hex(), xw.hex())); continue
                what = 'index' if o + 2 >= sp[1][0] else 'vertex'
                ch[o] = (old, new, 'MESH16', '%s u16 of Xbox %s (old %s)' % (what, xw.hex(), 's32' if old == xw[::-1] else 'other'))
    n = listcount(xd, it)
    if n is not None:
        xw, old = xd[0x10:0x14], pd[0x10:0x14]; new = xw[::-1]
        if old != new:
            ch[0x10] = (old, new, 'LISTCOUNT', 'count %d = %d list pointers (old %d)' % (n, n, struct.unpack('<I', old)[0]))
    return ch, rep


def pair_sections(xs, D):
    """[(xbox sec dict, pc section index)] for type 7: same id + size + internal layout, else unique size + layout"""
    lay = collections.defaultdict(list)
    for k, s in enumerate(D.sections):
        if s.type == 7: lay[len(s.data), tuple(sorted(internal(s.reloc, 'le').items()))].append(k)
    out, used = [], set()
    for x in xs:
        if x['type'] != 7 or x['data'] is None: continue
        key = (len(x['data']), tuple(sorted(internal(x['reloc'], 'be').items())))
        cand = [k for k in lay.get(key, []) if k not in used]
        same = [k for k in cand if D.sections[k].id == x['id']]
        k = same[0] if same else (cand[0] if len(cand) == 1 else None)
        if k is not None: used.add(k); out.append((x, k))
    return out


def load_xbox(rel):
    TA.ORDER = XORDER
    return TA.load_x(rel.replace('/', chr(92)))


def plan_file(xs, D, his=None):
    ch, rep = {}, []
    hp = {}
    if his is not None:
        for x, k in pair_sections(xs, his): hp[x['id'], len(x['data'])] = his.sections[k].data
    for x, k in pair_sections(xs, D):
        c, r = plan_section(x['data'], x['reloc'], D.sections[k].data)
        hd = hp.get((x['id'], len(x['data'])))
        for o, (old, new, rule, note) in c.items():
            hw = hd[o:o + 4] if hd is not None and o + 4 <= len(hd) else None
            ch[(k, o)] = (old, new, rule, 'Xbox DTP %d / PC %d: %s | his %s' % (
                x['id'], D.sections[k].id, note, '-' if hw is None else ('same' if hw == new else hw.hex())))
        rep += ['Xbox DTP %d / PC %d: %s' % (x['id'], D.sections[k].id, l) for l in r]
    return ch, rep


def is_costume(rel):
    b = os.path.basename(rel.replace(chr(92), '/')).lower()
    return b.startswith('dlc_costume_') and b.endswith('.drm')


def prove_write(orig, raw, ch, xs):
    """the proofs of `fix` on a written DRM: decoded DRM differs from the input only in the planned bytes, same section
    count, section headers + relocation blobs identical, a second plan finds 0 words -> number of differing bytes"""
    D0 = DW.read(orig, 'le'); dec0 = DW.cdrm_decode(orig, 'le'); dec1 = DW.cdrm_decode(raw, 'le')
    assert D0.write('le') == bytes(dec0), 'writer not lossless'
    D1 = DW.read(raw, 'le')
    assert len(dec0) == len(dec1) and len(D0.sections) == len(D1.sections), 'decoded size / section count changed'
    for x, y in zip(D0.sections, D1.sections):
        assert (x.type, x.id, x.flags, x.ver, x.spec, x.pad, x.reloc, len(x.data)) == \
               (y.type, y.id, y.flags, y.ver, y.spec, y.pad, y.reloc, len(y.data)), 'header / reloc changed'
    bases = data_bases(D0)
    planned = {bases[k] + o + j for (k, o), v in ch.items() for j in range(4) if v[0][j] != v[1][j]}
    diff = {i for i in range(len(dec0)) if dec0[i] != dec1[i]}
    assert diff == planned, 'byte diff %d != planned %d' % (len(diff), len(planned))
    again, _ = plan_file(xs, D1)
    assert not again, 're-plan not empty: %d' % len(again)
    return len(diff)


def fix_drm(raw, rel):
    """library for the step `costumedtp` of tools/dlc_struct_fixes.py (2026-11-08): one dlc_costume_*.drm ->
    (new raw or None, changes [(section index, offset, old, new, PC section id, rule)], report lines, Xbox source).
    The Xbox source is looked up as in `scan` / `fix` (XORDER, lower-case file name); the written bytes are proven
    (prove_write: an AssertionError leaves the caller's DRM unchanged). Not a costume DRM -> (None, [], [], None)."""
    if not is_costume(rel): return None, [], [], None
    order = TA.ORDER
    try:
        xs, src = load_xbox(os.path.basename(rel.replace(chr(92), '/')).lower())
    finally:
        TA.ORDER = order
    D = DW.read(raw, 'le')
    ch, rep = plan_file(xs, D)
    if not ch: return None, [], rep, src
    ids = {k: D.sections[k].id for k, o in ch}
    for (k, o), (old, new, _, _) in ch.items():
        s = D.sections[k]; d = bytearray(s.data); d[o:o + 4] = new; s.data = bytes(d)
    out = D.write('le')
    if raw[:4] == b'CDRM': out = DW.cdrm_encode(out, 'le')
    prove_write(raw, out, ch, xs)
    changes = [(k, o, old, new, ids[k], rule) for (k, o), (old, new, rule, _) in sorted(ch.items())]
    return out, changes, rep, src


def overlay(dirs):
    by = {}
    for d in dirs:
        if not os.path.isdir(d): continue
        for f in os.listdir(d):
            if f.lower().startswith('dlc_costume_') and f.lower().endswith('.drm'): by[f.lower()] = os.path.join(d, f)
    return by


def cmd_prove(names):
    tot = collections.Counter()
    import dtp_twin_field as TW
    for name in names or BASE_NAMES:
        xs, sx = TW.load_named(name, ('tu', 'xbase2', 'xbase'), 'be')
        ps, sp = TW.load_named(name, ('pcpatch', 'pcbig'), 'le')
        if not xs or not ps: print('%s: Xbox %s, PC %s - skipped' % (name, sx, sp)); continue
        # pair by size + internal layout (base ids differ between Xbox and PC)
        lay = collections.defaultdict(list)
        for k, s in enumerate(ps):
            if s['type'] == 7: lay[len(s['data']), tuple(sorted(internal(s['reloc'], 'le').items()))].append(k)
        seen = collections.Counter(); c = collections.Counter()
        for x in xs:
            if x['type'] != 7: continue
            key = (len(x['data']), tuple(sorted(internal(x['reloc'], 'be').items())))
            j = seen[key]; seen[key] += 1
            if j >= len(lay.get(key, [])): continue
            xd, pd = x['data'], ps[lay[key][j]]['data']
            it = internal(x['reloc'], 'be')
            if xd[:4] == MODEL_MAGIC:
                sp_, why = u16_spans(xd, it)
                if sp_ is None:
                    c['model_unprovable'] += 1
                    print('  %s model DTP Xbox %d (%d B): not provable - %s' % (name, x['id'], len(xd), why)); continue
                c['model'] += 1
                for a, e, what in sp_:
                    for o in range(a, e - 1, 2):
                        ok = pd[o:o + 2] == xd[o:o + 2][::-1]
                        c['%s_u16_%s' % (what, 'swap' if ok else 'OTHER')] += 1
                        if not ok and c['%s_u16_OTHER' % what] <= 3:
                            print('  %s %s +0x%x: Xbox %s PC %s' % (name, what, o, xd[o:o + 2].hex(), pd[o:o + 2].hex()))
                    # the same words as 4-byte units: how often would a u32 swap give the same bytes (ambiguous)?
                    for o in range((a + 3) & ~3, e - 3, 4):
                        xw = xd[o:o + 4]
                        if xw[::-1] != xw[1::-1] + xw[:1:-1]: c['%s_words_informative' % what] += 1
            n = listcount(xd, it)
            if n is not None:
                ok = pd[0x10:0x14] == xd[0x10:0x14][::-1]
                c['listcount_%s' % ('s32' if ok else 'OTHER')] += 1
                if not ok: print('  %s LISTCOUNT: Xbox %s PC %s' % (name, xd[0x10:0x14].hex(), pd[0x10:0x14].hex()))
        print('%s (Xbox %s / PC %s): %s' % (name, sx, sp, dict(sorted(c.items()))))
        tot.update(c)
    print('TOTAL', dict(sorted(tot.items())))
    return 1 if any(k.endswith('OTHER') for k in tot) else 0


def cmd_scan(dirs, his_dir, verbose):
    tot = collections.Counter()
    for rel, p in sorted(overlay(dirs).items()):
        raw = open(p, 'rb').read(); D = DW.read(raw, 'le')
        try: xs, src = load_xbox(rel)
        except SystemExit as e: print('%s: %s' % (rel, e)); continue
        his = None
        if his_dir and os.path.isfile(os.path.join(his_dir, rel)): his = DW.read(open(os.path.join(his_dir, rel), 'rb').read(), 'le')
        ch, rep = plan_file(xs, D, his)
        by = collections.Counter((v[2], v[3].split(':')[0]) for v in ch.values())
        hs = sum(1 for v in ch.values() if v[3].endswith('his same'))
        print('%s (%s, Xbox %s, md5 %s): %d word(s) to fix%s' % (rel, p, src, hashlib.md5(raw).hexdigest(), len(ch),
              '' if his is None else ', his file has the same bytes in %d' % hs))
        for (rule, dtp), n in sorted(by.items()): print('    %s %s: %d' % (rule, dtp, n))
        for l in rep: print('  ' + l)
        for (k, o), (old, new, rule, note) in sorted(ch.items())[:None if verbose else 6]:
            print('    section %d +0x%x %s -> %s  %s %s' % (k, o, old.hex(), new.hex(), rule, note))
        tot['files'] += 1; tot['words'] += len(ch); tot['his_same'] += hs
        for (rule, _), n in by.items(): tot[rule] += n
    print('TOTAL', dict(sorted(tot.items())))
    return 0


def cmd_fix(dirs, out, check, his_dir):
    tot = collections.Counter(); written = []
    for rel, p in sorted(overlay(dirs).items()):
        if not check and os.path.realpath(os.path.dirname(p)) == os.path.realpath(out): sys.exit('OUT_MODS is a source folder')
        orig = open(p, 'rb').read(); D = DW.read(orig, 'le')
        xs, src = load_xbox(rel)
        his = None
        if his_dir and os.path.isfile(os.path.join(his_dir, rel)): his = DW.read(open(os.path.join(his_dir, rel), 'rb').read(), 'le')
        ch, rep = plan_file(xs, D, his)
        hs = sum(1 for v in ch.values() if v[3].endswith('his same'))
        print('%s (input %s md5 %s, Xbox %s): %d word(s) (%s), his file same bytes in %d' % (
            rel, p, hashlib.md5(orig).hexdigest(), src, len(ch), dict(collections.Counter(v[2] for v in ch.values())), hs))
        for l in rep: print('  ' + l)
        tot['words'] += len(ch); tot['his_same'] += hs
        if check or not ch: continue
        for (k, o), (old, new, _, _) in ch.items():
            s = D.sections[k]; d = bytearray(s.data); d[o:o + 4] = new; s.data = bytes(d)
        raw = D.write('le')
        if orig[:4] == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        D0 = DW.read(orig, 'le'); dec0 = DW.cdrm_decode(orig, 'le'); dec1 = DW.cdrm_decode(raw, 'le')
        assert D0.write('le') == bytes(dec0), 'writer not lossless'
        D1 = DW.read(raw, 'le')
        assert len(dec0) == len(dec1) and len(D0.sections) == len(D1.sections)
        for x, y in zip(D0.sections, D1.sections):
            assert (x.type, x.id, x.flags, x.ver, x.spec, x.pad, x.reloc, len(x.data)) == \
                   (y.type, y.id, y.flags, y.ver, y.spec, y.pad, y.reloc, len(y.data)), 'header / reloc changed'
        bases = data_bases(D0)
        planned = {bases[k] + o + j for (k, o), (old, new, _, _) in ch.items() for j in range(4) if old[j] != new[j]}
        diff = {i for i in range(len(dec0)) if dec0[i] != dec1[i]}
        assert diff == planned, 'byte diff %d != planned %d' % (len(diff), len(planned))
        again, _ = plan_file(xs, D1)
        assert not again, 're-plan not empty: %d' % len(again)
        q = os.path.join(out, rel); os.makedirs(os.path.dirname(q), exist_ok=True)
        open(q, 'wb').write(raw); assert open(q, 'rb').read() == raw
        md = hashlib.md5(raw).hexdigest(); written.append((rel, md)); tot['files'] += 1
        print('  proof: readback ok, %d bytes differ = planned (%d words), %d sections: headers + relocation blobs identical, '
              're-plan 0 words; written %s md5 %s' % (len(diff), len(ch), len(D1.sections), q, md))
    print('total %s%s' % (dict(tot), ' (check only)' if check else ', written %d file(s)' % len(written)))
    return 0


def main(a):
    if not a: sys.exit(__doc__)
    verbose = '-v' in a; check = '--check' in a
    a = [x for x in a if x not in ('-v', '--check')]
    his = None
    if '--his' in a: k = a.index('--his'); his = a[k + 1]; del a[k:k + 2]
    if a[0] == 'prove': return cmd_prove(a[1:])
    if a[0] == 'scan': return cmd_scan(a[1].split(','), his, verbose)
    if a[0] == 'fix': return cmd_fix(a[1].split(','), a[2], check, his)
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
