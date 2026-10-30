"""Inline u16 arrays of NEW DLC scripts (type 8, id >= 20000) - the target paths of UI timeline descriptors, whose
elements are script member Symbols (finding 43, crash after the DLC 2 intro). Pattern as in
tools/script_u16array_check.py ({u32 n, internal pointer to the next word, u16[n]}), narrowed to entry lists (the
first entry is the target of an internal pointer, the next ones follow it directly), PC words that are exactly the
whole-word swap of the Xbox ones, non-zero elements and mapped values that fit u16. The converter swapped these
words as s32 and kept the Xbox Symbol values, so the engine's path lookup (tru.exe +0xd08e0) found no member and
returned a stack address as the timeline target. Base-game scripts are left alone (PC copies).

  --mode sym (default): every element = the converter's PC Symbol for the Xbox one (dlc_generic.DlcIds.sym),
                        Xbox element order, u16 little-endian - fixed the crash (test 16)
  --mode s16          : experiment 1 (failed in game): Xbox element order, values unchanged

Also used as stage-2b fix `uipath` (tools/dlc_fixes_build.py, in place). Standalone it writes only the changed DRMs
to OUT (same relative paths); IN is not modified.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/script_u16array_fix.py IN_MODS_DIR OUT_DIR [--pack pack11] [--mode sym|s16]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from script_u16array_check import arrays


def process(rel, path, ids, st, log):
    """-> new file bytes or None; ids = DlcIds (mode sym) or None (mode s16)"""
    import dtp_audit as DA, drm_write as DW, drm_reloc as R
    xs = DA.xsecs(rel)
    if xs is None: return None
    raw = open(path, 'rb').read(); D = DW.read(raw, 'le')
    pc8 = {s.id: s for s in D.sections if s.type == 8}
    changed = False
    for x in xs:
        sec = pc8.get(x['id']) if x['type'] == 8 and x['data'] is not None and x['id'] >= 20000 else None
        if sec is None or len(sec.data) != len(x['data']): continue
        xd = x['data']; xr = R.parse(x['reloc'], 'be'); ptrs = set(xr.pointer_offsets())
        targets = {t for _, t in xr.internal}
        pd = bytearray(sec.data)
        ends = set()          # entry lists: the first entry is pointed to, the next ones follow it directly
        for co, n, t, words in sorted(arrays(xd, xr)):
            if any(t + 4 * k in ptrs for k in range(words)): continue
            if co not in targets and co not in ends: st['skipped: not an entry list'] += 1; continue
            xw = xd[t:t + 4 * words]
            if pd[t:t + 4 * words] != b''.join(xw[k:k + 4][::-1] for k in range(0, len(xw), 4)):
                st['skipped: PC words not the whole-word swap'] += 1; continue
            xv = list(struct.unpack_from('>%dH' % (2 * words), xd, t))
            if not all(xv[:n]): st['skipped: zero element'] += 1; continue
            pv = [ids.sym(v) if (ids and k < n) else v for k, v in enumerate(xv)]
            if max(pv) > 0xFFFF: st['skipped: mapped Symbol above 0xffff'] += 1; continue
            ends.add(t + 4 * words)
            want = struct.pack('<%dH' % len(pv), *pv)
            st['arrays'] += 1
            if pd[t:t + 4 * words] != want:
                log.append('%s script %d +%#x: %s -> %s (xbox %s)' % (
                    rel, sec.id, t, pd[t:t + 4 * words].hex(), want.hex(), ' '.join('%04x' % v for v in xv[:n])))
                pd[t:t + 4 * words] = want; st['arrays changed'] += 1; changed = True
        sec.data = bytes(pd)
    if not changed: return None
    out = D.write('le')
    return DW.cdrm_encode(out, 'le') if raw[:4] in (b'CDRM', b'MRDC') else out


def main(argv):
    mode = 'sym'
    if '--mode' in argv: k = argv.index('--mode'); mode = argv[k + 1]; del argv[k:k + 2]
    if '--pack' in argv: k = argv.index('--pack'); os.environ['TRUDLC_PACK_FIRST'] = argv[k + 1]; del argv[k:k + 2]
    import dtp_audit as DA
    ids = None
    if mode == 'sym':
        import dlc_generic as DG
        ids = DG.DlcIds()
    src, dst = os.path.abspath(argv[0]), os.path.abspath(argv[1])
    st = collections.Counter(); log = []
    for rel, path in sorted(DA.overlay([src], None).items()):
        new = process(rel, path, ids, st, log)
        if new is None: continue
        q = os.path.join(dst, rel); os.makedirs(os.path.dirname(q), exist_ok=True)
        open(q, 'wb').write(new); st['files'] += 1
    for l in log[:20]: print(' ', l)
    print(dict(st), 'symbol routes:', dict(ids.sym_stats) if ids else '-')


if __name__ == '__main__':
    main(sys.argv[1:])
