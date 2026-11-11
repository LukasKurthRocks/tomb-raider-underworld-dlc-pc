"""UI text element records of the NEW DLC scripts (type 8, id >= 20000) against Crystal's PC conversion rules
(read-only, or --fix OUT). Finding 43: the converter turned record words into swapped halves (4 -> 0x00040000) and
kept the Xbox 0 where every PC record has 0x00010000 (the "visible" word: the DLC loading-screen title was drawn
invisibly because of it). Rules per record position come from the retail Xbox / PC pair of generalbank script 10 / 9
(the same template as tools/script_record_template.py): u32 value, bytes as they are, or PC constant. The Xbox DLC
section and the PC section have one layout (same length), so every record is checked word by word; relocation words
and the string id (position 4, mapped by `uitext`) are left alone.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/script_records_dlc.py MODS_DIR [--pack pack11] [--fix OUT_DIR] [--list]
  --fix: write the changed DRMs to OUT_DIR (same relative paths); --list: every changed word
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

N = 16


def template():
    """(retail Xbox record words, retail PC record words, rules) of generalbank script 10 (Xbox) / 9 (PC)"""
    import locals as LC, drm_write as DW
    from archive import Archive
    from names import crc
    from drm import cdrm_decode

    def script(src, sid):
        path, e, pre = LC.SRC[src]; A = Archive(path, e)
        rec = A.find(crc(pre + '\\generalbank.drm'))
        if not rec: return None
        D = DW.read(cdrm_decode(A.read(rec[-1]), e), e)
        return next(s for s in D.sections if s.type == 8 and s.id == sid).data
    xd = script('xbase', 10) or script('xbase2', 10); pd = script('pcpatch', 9) or script('pcbig', 9)
    for o in range(0, len(xd) - 4 * N + 1, 4):
        w = struct.unpack_from('>4I', xd, o)
        if w[0] == 0xffffffff and w[1] == 0 and w[3] >> 24 == 0xff and w[2] >> 24 == 0xff:
            x = list(struct.unpack_from('>%dI' % N, xd, o)); p = list(struct.unpack_from('<%dI' % N, pd, o))
            if p[:2] == [0xffffffff, 0]: break
    else:
        raise SystemExit('no retail template record')
    rules = ['s32' if pv == xv else 'bytes' if pv == int.from_bytes(xv.to_bytes(4, 'big'), 'little') else 'pc'
             for xv, pv in zip(x, p)]
    return x, p, rules


_IDS = None


def process(rel, path, tpl, st, log, ids=None):
    """ids: dlc_generic.DlcIds for the script pairing (one is made once when None)"""
    global _IDS
    import dtp_audit as DA, drm_write as DW, drm_reloc as R, dlc_script_pairs as SP
    xs = DA.xsecs(rel)
    if xs is None: return None
    if ids is None:
        if _IDS is None:
            import dlc_generic as DG
            _IDS = DG.DlcIds()
        ids = _IDS
    rx, rp, rules = tpl
    raw = open(path, 'rb').read(); D = DW.read(raw, 'le')
    changed = False
    # Q46: Xbox <-> PC script by the converter's id map + name Symbol (as tools/script_uitext_fix.py): new DLC scripts
    # (Xbox id >= 20000) as before plus base scripts built in the Xbox layout (route 'convert'), renumbered or not
    pm, pst = SP.pairs(xs, D, ids)
    for k, v in pst.items(): st['pairing: ' + k] += v
    for k, (x, route) in sorted(pm.items()):
        sec = D.sections[k]
        if not (x['id'] >= 20000 or route == 'convert') or len(sec.data) != len(x['data']): continue
        if x['id'] < 20000: st['scripts in scope: base id, route convert'] += 1
        xd = x['data']; xr = R.parse(x['reloc'], 'be'); rel_off = set(xr.pointer_offsets()) | set(xr.id_offsets())
        pd = bytearray(sec.data)
        for o in range(0, len(xd) - 4 * N + 1, 4):
            w = struct.unpack_from('>4I', xd, o)
            if not (w[0] in (0xffffffff, 0x00ffffff) and w[1] == 0 and w[3] >> 24 == 0xff and w[2] >> 24 in (0, 0xff) and w[2]):
                continue
            st['records'] += 1; n0 = st['words changed']
            for i in range(N):
                q = o + 4 * i
                if q in rel_off or i == 4: continue
                v = struct.unpack_from('>I', xd, q)[0]
                if rules[i] == 'bytes': want = int.from_bytes(v.to_bytes(4, 'big'), 'little')
                elif rules[i] == 'pc' and v == rx[i]: want = rp[i]
                else: want = v
                cur = struct.unpack_from('<I', pd, q)[0]
                if cur != want:
                    struct.pack_into('<I', pd, q, want); st['words changed'] += 1; changed = True
                    log.append('%s script %d record +%#x word %d: xbox %08x pc %08x -> %08x' % (rel, sec.id, o, i, v, cur, want))
            if st['words changed'] > n0: st['records changed'] += 1
        sec.data = bytes(pd)
    if not changed: return None
    out = D.write('le')
    return DW.cdrm_encode(out, 'le') if raw[:4] in (b'CDRM', b'MRDC') else out


def main(argv):
    out = None; show = '--list' in argv; argv = [a for a in argv if a != '--list']
    if '--fix' in argv: k = argv.index('--fix'); out = argv[k + 1]; del argv[k:k + 2]
    if '--pack' in argv: k = argv.index('--pack'); os.environ['TRUDLC_PACK_FIRST'] = argv[k + 1]; del argv[k:k + 2]
    import dtp_audit as DA
    tpl = template(); print('template rules: %s' % ' '.join(tpl[2]))
    st = collections.Counter(); log = []
    for rel, path in sorted(DA.overlay([os.path.abspath(argv[0])], None).items()):
        new = process(rel, path, tpl, st, log)
        if new is not None:
            st['files'] += 1
            if out:
                q = os.path.join(out, rel); os.makedirs(os.path.dirname(q), exist_ok=True); open(q, 'wb').write(new)
    for l in (log if show else log[:12]): print(' ', l)
    print(dict(st))


if __name__ == '__main__':
    main(sys.argv[1:])
