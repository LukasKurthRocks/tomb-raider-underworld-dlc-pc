"""Test tree dlc_test51w_dtp: DTP byte-order words of DLC 1 that the upstream B270 kit corrected and that a
base-pair rule proves (kit-rest task 2, workspace docs Befund-Kit-Reste-0511.md). Reads PC DRMs from SRC_MODS
(normally work/rebuild/b138_pristine/mods = the copies every profile installs from the game folder), writes only the
changed DRMs to OUT_MODS. His files are NOT the reference: every new word is computed from the Xbox source bytes with
the permutation the base pairs prove; his word is only printed as a cross-check.

Word list (evidence in the Befund; tools/kitrest_fp_stats.py, kitrest_base_word.py, kitrest_dtp_words.py):
  sluice falls 20797 +0x188 raw, puddle 20452 +0x258 raw, water wheel 20790 +0xbc4 / +0xd04 u8u8u16 (b2s16),
  glare hallb 24075 / waterwhl 24189 +0x98 s32, intro cinematic 23767 (8 words + id slot +0x38c type 5 via the base id
  map), costumes b c e j: DTP 2616 (Xbox 12599) +0x10 count s32, o: DTP 2660 (Xbox 12626) +0x10 count s32, and in
  the costume model DTPs (b 23671, c 23684, e 23700, j 24271, o 21090) the words his file changed, each only if the
  dtp_audit fingerprint rule of that word says s16 (or it is one of the 10 words with only loose-key evidence, LOOSE).
Before a word is set: the old PC bytes must be a byte permutation of the Xbox bytes (else the word is re-numbered on
purpose and kept) - except kinds 'count' (proof: base pair count s32, pointer array length) and 'id'.
Proofs on every written DRM: read back, raw DRM differs from the input only in the planned bytes, section headers +
relocation blobs identical, a second plan on the output plans 0 words.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/kitrest_dtp_fix.py SRC_MODS OUT_MODS [--check] [--his HIS_MODS] [--no-loose]
"""
import sys, os, struct, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_write as DW
import tuning_word_audit as TA
import dtp_audit as DA
from drm import cdrm_decode, sections_with_data
from objdata_fx_fix import data_bases

PERM = dict(DA.PERMS)
# rel -> [(Xbox DTP id, PC DTP id, [(offset, kind)] or 'his-s16')]
PLAN = {
    'dlc1_uo_sluice_falls.drm': [(20797, 20797, [(0x188, 'raw')])],
    'fx_mex_puddle_ist.drm': [(20452, 20452, [(0x258, 'raw')])],
    'dlc1_uo_water_wheel.drm': [(20790, 20790, [(0xbc4, 'b2s16'), (0xd04, 'b2s16')])],
    'dlc_fx_glare_simple_hallb_ist.drm': [(24075, 24075, [(0x98, 's32')])],
    'dlc_fx_glare_simple_waterwhl_ist.drm': [(24189, 24189, [(0x98, 's32')])],
    'cinstream/pdlc1_010_intro.drm': [(23767, 23767, [(0x160, 'b2s16'), (0x180, 's16'), (0x19c, 'raw'), (0x1f4, 'raw'),
                                                      (0x224, 's16'), (0x318, 's16'), (0x348, 's16b2'), (0x3d0, 's16'),
                                                      (0x38c, 'id')])],
    'dlc_costume_b.drm': [(12599, 2616, [(0x10, 'count')]), (23671, 23671, 'his-s16')],
    'dlc_costume_c.drm': [(12599, 2616, [(0x10, 'count')]), (23684, 23684, 'his-s16')],
    'dlc_costume_e.drm': [(12599, 2616, [(0x10, 'count')]), (23700, 23700, 'his-s16')],
    'dlc_costume_j.drm': [(12599, 2616, [(0x10, 'count')]), (24271, 24271, 'his-s16')],
    'dlc_costume_o.drm': [(12626, 2660, [(0x10, 'count')]), (21090, 21090, 'his-s16')],
}
# words of the costume model DTPs without a strict dtp_audit rule; loose key (offset in region, slot mask, parent)
# s16 in all base samples (n 15 / 5, 0 exceptions), strict key n 2 (s32/s16, both fit s16) - kitrest_fp_stats log
LOOSE = {('dlc_costume_b.drm', 23671): {0x30658, 0x30668, 0x30678},
         ('dlc_costume_c.drm', 23684): {0x301e4, 0x3025c},
         ('dlc_costume_e.drm', 23700): {0x2ff78, 0x2ff88, 0x2ff98},
         ('dlc_costume_j.drm', 24271): {0x301e4, 0x3025c}}


def xbox(rel):
    TA.ORDER = ('pack10', 'pack11', 'tu', 'xbase2', 'xbase')
    return TA.load_x(rel.replace('/', chr(92)))


def first7(D, sid):
    k = [i for i, s in enumerate(D.sections) if s.type == 7 and s.id == sid]
    return k


def plan_file(rel, D, xs, his, no_loose, out_lines):
    """{(section index, offset): (old, new, note)}"""
    import dtpid_sweep as DS
    ch = {}
    for xid, pid, words in PLAN[rel]:
        xsec = [s for s in xs if s['type'] == 7 and s['id'] == xid]
        ks = first7(D, pid)
        if len(xsec) != 1 or not ks:
            out_lines.append('  DTP %d / Xbox %d: not found uniquely (Xbox %d, PC %d copies) - skipped' % (pid, xid, len(xsec), len(ks)))
            continue
        xd = xsec[0]['data']; xr = R.parse(xsec[0]['reloc'], 'be')
        hsec = None
        if his is not None:
            hk = first7(his, pid); hsec = his.sections[hk[0]] if hk else None
        for k in ks:
            pd = D.sections[k].data
            if len(pd) != len(xd):
                out_lines.append('  DTP %d section %d: size %d != Xbox %d - skipped' % (pid, k, len(pd), len(xd))); continue
            if words == 'his-s16':
                if hsec is None or len(hsec.data) != len(pd):
                    out_lines.append('  DTP %d: no comparable copy in his file - skipped' % pid); continue
                rl = DA.rules(); keys = dict(DA.word_keys(xd, xr))
                lst = []
                for o in range(0, len(pd) - 3, 4):
                    if hsec.data[o:o + 4] == pd[o:o + 4]: continue
                    r = rl.get(keys.get(o))
                    if r is not None and DA.NAMES[r] == 's16': lst.append((o, 's16'))
                    elif not no_loose and o in LOOSE.get((rel, pid), ()): lst.append((o, 's16'))
                    else: out_lines.append('  DTP %d +0x%x: his word differs, no s16 evidence (rule %s) - left' % (
                        pid, o, DA.NAMES[r] if r is not None else '-'))
                todo = lst
            else:
                todo = words
            slots = set(xr.pointer_offsets()) | set(xr.id_offsets())
            for o, kind in todo:
                xw, old = xd[o:o + 4], pd[o:o + 4]
                if kind == 'id':
                    t = xr.id_offsets().get(o)
                    if t is None: out_lines.append('  +0x%x: no id slot on the Xbox side - skipped' % o); continue
                    _, ids = DS.ctx(); v = int.from_bytes(xw, 'big'); m = ids.base.get(t, {}).get(v)
                    if m is None: out_lines.append('  +0x%x: id %d type %d not in the base map - skipped' % (o, v, t)); continue
                    new = struct.pack('<I', m); note = 'id slot type %d: Xbox %d -> base map %d' % (t, v, m)
                else:
                    if o in slots: out_lines.append('  +0x%x: relocated slot - skipped' % o); continue
                    p = PERM['s32' if kind == 'count' else kind]
                    new = bytes(xw[i] for i in p)
                    if kind != 'count' and sorted(old) != sorted(xw):
                        out_lines.append('  +0x%x: old %s is no permutation of Xbox %s - kept' % (o, old.hex(), xw.hex())); continue
                    note = '%s of Xbox %s' % (kind, xw.hex())
                if new == old: continue
                hw = hsec.data[o:o + 4] if hsec is not None and o + 4 <= len(hsec.data) else None
                note += ' | his %s' % ('same' if hw == new else (hw.hex() if hw else '-'))
                ch[(k, o)] = (old, new, 'DTP %d %s' % (pid, note))
    return ch


def main(a):
    check = '--check' in a; no_loose = '--no-loose' in a
    a = [x for x in a if x not in ('--check', '--no-loose')]
    his_dir = None
    if '--his' in a: k = a.index('--his'); his_dir = a[k + 1]; del a[k:k + 2]
    src, out = a
    if not check and os.path.realpath(src) == os.path.realpath(out): sys.exit('OUT_MODS is SRC_MODS')
    tot = collections.Counter(); written = []
    for rel in PLAN:
        p = os.path.join(src, rel)
        if not os.path.isfile(p): print('%s: not in %s' % (rel, src)); continue
        orig = open(p, 'rb').read(); D = DW.read(orig, 'le')
        xs, xsrc = xbox(rel)
        his = DW.read(open(os.path.join(his_dir, rel), 'rb').read(), 'le') if his_dir and os.path.isfile(os.path.join(his_dir, rel)) else None
        lines = []
        ch = plan_file(rel, D, xs, his, no_loose, lines)
        hissame = sum(1 for v in ch.values() if v[2].endswith('his same'))
        print('%s (Xbox %s, input md5 %s): %d word(s), his file has the same bytes in %d' % (
            rel, xsrc, hashlib.md5(orig).hexdigest(), len(ch), hissame))
        for l in lines: print(l)
        byd = collections.Counter(v[2].split(' ')[1] for v in ch.values())
        for (k, o), (old, new, note) in sorted(ch.items())[:12]:
            print('    section %d +0x%x %s -> %s  %s' % (k, o, old.hex(), new.hex(), note))
        if len(ch) > 12: print('    ... %d more (%s)' % (len(ch) - 12, dict(byd)))
        tot['words'] += len(ch); tot['his_same'] += hissame; tot['files'] += 1 if ch else 0
        if check or not ch: continue
        for (k, o), (old, new, note) in ch.items():
            s = D.sections[k]; d = bytearray(s.data); d[o:o + 4] = new; s.data = bytes(d)
        raw = D.write('le')
        if orig[:4] == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        # proofs
        D0 = DW.read(orig, 'le'); dec0 = DW.cdrm_decode(orig, 'le'); dec1 = DW.cdrm_decode(raw, 'le')
        assert D0.write('le') == bytes(dec0), 'writer not lossless'
        D1 = DW.read(raw, 'le')
        assert len(dec0) == len(dec1) and len(D0.sections) == len(D1.sections)
        for x, y in zip(D0.sections, D1.sections):
            assert (x.type, x.id, x.flags, x.ver, x.spec, x.pad, x.reloc, len(x.data)) == \
                   (y.type, y.id, y.flags, y.ver, y.spec, y.pad, y.reloc, len(y.data)), 'header / reloc changed'
        bases = data_bases(D0)
        planned = {bases[k] + o + j for (k, o), (old, new, _) in ch.items() for j in range(4) if old[j] != new[j]}
        diff = {i for i in range(len(dec0)) if dec0[i] != dec1[i]}
        assert diff == planned, 'byte diff %d != planned %d' % (len(diff), len(planned))
        again = plan_file(rel, DW.read(raw, 'le'), xs, his, no_loose, [])
        assert not again, 're-plan not empty: %d' % len(again)
        q = os.path.join(out, rel); os.makedirs(os.path.dirname(q), exist_ok=True)
        open(q, 'wb').write(raw); assert open(q, 'rb').read() == raw
        md = hashlib.md5(raw).hexdigest(); written.append((rel, md))
        print('  proof: readback ok, %d bytes differ = planned (%d words), %d sections: headers + relocation blobs identical, '
              're-plan 0 words; written %s md5 %s' % (len(diff), len(ch), len(D1.sections), q, md))
    print('total %s%s' % (dict(tot), ' (check only)' if check else ', written %d file(s)' % len(written)))


if __name__ == '__main__':
    main(sys.argv[1:])
