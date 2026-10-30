"""UI text elements in NEW DLC scripts (type 8, id >= 20000; finding 43, empty texts / hint box in DLC 2).

Record as in the base game (PC generalbank script 7 and its Xbox source, all 32-bit words):
    ... u32 0xffffffff, u32 colour (ARGB, alpha 0xff), u32 string id, u32 flags ...
In the new DLC 2 scripts the Xbox word after the colour holds the string id in its HIGH u16 (e.g. `0511 0000` =
1297 "OBJECTIVE REVEALED - Press [Back] to view"); the converter's learned table treated colour and id as Symbol
pairs (colour ff606060 -> 40016060, id 1297 -> Symbol 1326), and the engine then asked GetLocalString(1326) - an
empty PC entry (runtime trace, tools/script_const_calls.py did not find them as code constants).

Fix (EXPERIMENT until tested in game): colour = s32 of the Xbox word; string id = the converter's PC string id
(dlc_generic.DlcIds.loc, locmap_xbox_to_pc.json) of the high u16, written as u32. Only records whose Xbox words match:
0xffffffff, colour with alpha 0xff, id word with low u16 = 0 and high u16 a DLC string index (1284 .. 0xffff).
--check lists them without writing.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/script_uitext_fix.py IN_DIR[,IN_DIR2] OUT_DIR --locmap MAP.json [--pack pack11] [--check]
  MAP.json = locmap_xbox_to_pc.json of tools/locals.py build (e.g. work/rebuild/dlc2_test13/locmap_xbox_to_pc.json)
  ../bin/pyt -t 300 tools/script_uitext_fix.py --ported IN.drm OUT.drm 6 --locmap MAP.json
      (title-update scripts ported into a PC DRM, e.g. generalbank script 6 - the DLC 1 loading screen title)
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DLC_FIRST = 1284          # first DLC string index of the Xbox tables (base 0 .. 1283)
DLC_LAST = 1406           # last index of the pack10 / pack11 tables (1407 strings)


def process(rel, path, ids, st, log, write=True):
    import dtp_audit as DA, drm_write as DW, drm_reloc as R
    xs = DA.xsecs(rel)
    if xs is None: return None
    raw = open(path, 'rb').read(); D = DW.read(raw, 'le')
    pc8 = {s.id: s for s in D.sections if s.type == 8}
    changed = False
    for x in xs:
        sec = pc8.get(x['id']) if x['type'] == 8 and x['data'] is not None and x['id'] >= 20000 else None
        if sec is None or len(sec.data) != len(x['data']): continue
        xd = x['data']; xr = R.parse(x['reloc'], 'be'); sl = set(xr.pointer_offsets()) | set(xr.id_offsets())
        pd = bytearray(sec.data)
        for o in range(0, len(xd) - 12, 4):
            a, col, w = struct.unpack_from('>III', xd, o)
            if a != 0xffffffff or col >> 24 != 0xff or w & 0xffff or (w >> 16) < DLC_FIRST: continue
            if any(k in sl for k in (o, o + 4, o + 8)): continue
            xid = w >> 16; pid = ids.loc(xid) if ids else xid
            want = struct.pack('<II', col, pid)
            st['records'] += 1
            log.append('%s script %d +%#x: colour %08x -> %s, string %d -> %d (was %s)' % (
                rel, sec.id, o + 4, col, want[:4].hex(), xid, pid, pd[o + 4:o + 12].hex()))
            if pd[o + 4:o + 12] != want:
                pd[o + 4:o + 12] = want; changed = True; st['records changed'] += 1
        # pattern B (script 20089, the hint list: {ptr, id << 16, 0, 0}, e.g. 1402 "Press [Back] to access the
        # Information screen", 1403 "The shadow meter drains ..."): only ids inside the Xbox DLC string range, because
        # the same field also holds larger values (0x1ba2) that are no string ids
        ptrs = set(xr.pointer_offsets())
        for o in range(4, len(xd) - 4, 4):
            if o - 4 not in ptrs or o in sl: continue
            w = struct.unpack_from('>I', xd, o)[0]
            if w & 0xffff or not DLC_FIRST <= (w >> 16) <= DLC_LAST: continue
            xid = w >> 16; pid = ids.loc(xid) if ids else xid
            want = struct.pack('<I', pid)
            st['hint records'] += 1
            log.append('%s script %d +%#x: B string %d -> %d (was %s)' % (rel, sec.id, o, xid, pid, pd[o:o + 4].hex()))
            if pd[o:o + 4] != want:
                pd[o:o + 4] = want; changed = True; st['hint records changed'] += 1
        sec.data = bytes(pd)
    if not changed or not write: return None
    out = D.write('le')
    return DW.cdrm_encode(out, 'le') if raw[:4] in (b'CDRM', b'MRDC') else out


def process_ported(path, script_ids, ids, st, log):
    """PC-side variant for title-update scripts PORTED into a PC DRM (generalbank script 6, whose layout no longer
    matches the Xbox one): text elements `ffffffff, colour (alpha 0xff), u32 id` whose id is still an Xbox DLC
    string index (1284 .. 1406) get the PC id. Only the named scripts - PC originals use PC numbering."""
    import drm_write as DW
    raw = open(path, 'rb').read(); D = DW.read(raw, 'le')
    changed = False
    for sec in D.sections:
        if sec.type != 8 or sec.id not in script_ids: continue
        pd = bytearray(sec.data)
        for o in range(0, len(pd) - 12, 4):
            a, col, v = struct.unpack_from('<III', pd, o)
            if a != 0xffffffff or col >> 24 != 0xff or not DLC_FIRST <= v <= DLC_LAST: continue
            pid = ids.loc(v); st['ported records'] += 1
            log.append('%s script %d +%#x: string %d -> %d' % (os.path.basename(path), sec.id, o + 8, v, pid))
            if pid != v: struct.pack_into('<I', pd, o + 8, pid); changed = True; st['ported records changed'] += 1
        sec.data = bytes(pd)
    if not changed: return None
    out = D.write('le')
    return DW.cdrm_encode(out, 'le') if raw[:4] in (b'CDRM', b'MRDC') else out


def main(argv):
    if '--ported' in argv:      # --ported IN.drm OUT.drm SCRIPT_ID[,ID] --locmap MAP.json
        import json, dlc_generic as DG
        k = argv.index('--locmap'); lm = argv[k + 1]
        a = argv[argv.index('--ported') + 1:]
        ids = DG.DlcIds(); ids._loc = {int(x): y for x, y in json.load(open(lm))['map'].items()}
        st = collections.Counter(); log = []
        new = process_ported(a[0], {int(x) for x in a[2].split(',')}, ids, st, log)
        for l in log: print(' ', l)
        if new is not None:
            os.makedirs(os.path.dirname(os.path.abspath(a[1])), exist_ok=True); open(a[1], 'wb').write(new)
        print(dict(st))
        return
    check = '--check' in argv
    argv = [a for a in argv if a != '--check']
    if '--pack' in argv: k = argv.index('--pack'); os.environ['TRUDLC_PACK_FIRST'] = argv[k + 1]; del argv[k:k + 2]
    locmap = None
    if '--locmap' in argv: k = argv.index('--locmap'); locmap = argv[k + 1]; del argv[k:k + 2]
    import json, dtp_audit as DA, dlc_generic as DG
    ids = DG.DlcIds()
    if locmap:      # the converter reads work/generic/locals/locmap_xbox_to_pc.json, which the pipeline never wrote
        ids._loc = {int(k): v for k, v in json.load(open(locmap))['map'].items()}
    if not ids.loc(1297) != 1297: raise SystemExit('no string id map (pass --locmap FILE)')
    srcs = [os.path.abspath(s) for s in argv[0].split(',')]      # several IN dirs: the later one wins
    dst = os.path.abspath(argv[1])
    st = collections.Counter(); log = []
    for rel, path in sorted(DA.overlay(srcs, None).items()):
        new = process(rel, path, ids, st, log, write=not check)
        if new is None: continue
        q = os.path.join(dst, rel); os.makedirs(os.path.dirname(q), exist_ok=True)
        open(q, 'wb').write(new); st['files'] += 1
    for l in log[:25]: print(' ', l)
    vals = collections.Counter(l.split('string ')[1].split(' ->')[0] for l in log)
    for l in [l for l in log if ': B string' in l][:10]: print(' ', l)
    print(dict(st), 'distinct Xbox string ids:', dict(sorted(vals.items(), key=lambda kv: int(kv[0]))))


if __name__ == '__main__':
    main(sys.argv[1:])
