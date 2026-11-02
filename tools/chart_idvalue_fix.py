"""Player state chart: activity entries of value types 3 and 5 hold a section id (u32); check them against the Xbox
original through the file's Xbox -> PC section id map and with --out repair them (read-only unless --out; test 50f
crash 2026-11-02 19:50:48, AV tru+0x14df84 with eax 0x04900000 after a fall death).

Reader (tru.exe 2008 Steam build): state code tru+0x35eed0 (and its neighbours) asks the machine for parameter
0x458 (1112) via tru+0x383f50 / tru+0x384b30, checks `word [entry+2] == 5` and passes `dword [entry+4]` (a full u32)
to tru+0x14df80 = [id*4 + 0x00c36f28] (section table by id). Activity entry = {u16 id, u16 type, 4 value bytes}
(tools/state_actlist_fix.py).

The id map: Xbox and PC sections of one DRM are aligned by (type, data size) with difflib (the converter keeps the
section order); an Xbox id maps to the PC id of its aligned section of the same type. The value class is decided by
the target type: the type of the section whose PC id the base pair uses.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/chart_idvalue_fix.py XBOX.drm PC.drm SID_X SID_P [--types 3,5] [--base XREF PREF XSID PSID] [--out OUT.drm]
     expected value: the base pair's PC value for the same (id, type, Xbox value) if --base gives one, else the PC id of
     the aligned type-7 section (DTP) with the Xbox id
  e.g. base proof:  work/rockvein/ref/x_lara.drm work/rockvein/ref/pc_lara.drm 12647 850
Output: every entry of the listed types: Xbox value, PC value, expected PC value (mapped id), section type, verdict.
"""
import sys, os, struct, difflib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import state_actlist_fix as SA


def id_map(DX, DP):
    a = [(s.type, len(s.data)) for s in DX.sections]
    b = [(s.type, len(s.data)) for s in DP.sections]
    m = {}
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != 'equal': continue
        for k in range(i2 - i1):
            sx, sp = DX.sections[i1 + k], DP.sections[j1 + k]
            m.setdefault(sx.id, set()).add((sx.type, sp.id))
    return m




BASE = {}


def main(argv):
    if len(argv) < 4: print(__doc__); return 2
    xp, pp, sx_id, sp_id = argv[0], argv[1], int(argv[2]), int(argv[3])
    types = {3, 5}
    if '--types' in argv: types = {int(t) for t in argv[argv.index('--types') + 1].split(',')}
    out = argv[argv.index('--out') + 1] if '--out' in argv else None
    BASE.clear()
    if '--base' in argv:   # (id, type, Xbox value) -> PC value as observed on the base pair
        k = argv.index('--base')
        bx, bp, bsx, bsp = argv[k + 1], argv[k + 2], int(argv[k + 3]), int(argv[k + 4])
        BX = [s for s in DW.read(open(bx, 'rb').read(), 'be').sections if s.type == 7 and s.id == bsx][0]
        BP = [s for s in DW.read(open(bp, 'rb').read(), 'le').sections if s.type == 7 and s.id == bsp][0]
        for tx, tp in zip(SA.records(BX, 'be'), SA.records(BP, 'le')):
            for i in range(tx[2][5]):
                eid, et = struct.unpack_from('>HH', BX.data, tx[3] + 8 * i)
                if et in types:
                    BASE.setdefault((eid, et, struct.unpack_from('>I', BX.data, tx[3] + 8 * i + 4)[0]), set()).add(
                        struct.unpack_from('<I', BP.data, tp[3] + 8 * i + 4)[0])
        print('base table: %s' % {k: sorted(v) for k, v in BASE.items()})
    DX = DW.read(open(xp, 'rb').read(), 'be'); DP = DW.read(open(pp, 'rb').read(), 'le')
    M = id_map(DX, DP)
    pids = {}
    for s in DP.sections: pids.setdefault(s.id, set()).add(s.type)
    SX = [s for s in DX.sections if s.type == 7 and s.id == sx_id][0]
    k_p = [k for k, s in enumerate(DP.sections) if s.type == 7 and s.id == sp_id][0]
    SP = DP.sections[k_p]
    rx, rp = SA.records(SX, 'be'), SA.records(SP, 'le')
    if len(rx) != len(rp): print('record count differs: Xbox %d PC %d' % (len(rx), len(rp))); return 1
    d = bytearray(SP.data)
    cnt = collections.Counter(); fixed = 0
    for tx, tp in zip(rx, rp):
        qp = tp[0]
        n_x, lx, lp = tx[2][5], tx[3], tp[3]
        for i in range(n_x):
            ex, ep = lx + 8 * i, lp + 8 * i
            eid, et = struct.unpack_from('>HH', SX.data, ex)
            if et not in types: continue
            xv = struct.unpack_from('>I', SX.data, ex + 4)[0]
            pv = struct.unpack_from('<I', d, ep + 4)[0]
            cand = M.get(xv, set())
            t7 = sorted({p for t, p in cand if t == 7})
            src = ''
            if (eid, et, xv) in BASE and len(BASE[(eid, et, xv)]) == 1:
                exp = next(iter(BASE[(eid, et, xv)])); src = 'base pair'
            elif len(t7) == 1:
                exp = t7[0]; src = 'DTP map'
            else:
                exp = None
            verdict = 'ok' if pv == exp else ('WRONG' if exp is not None else 'unmapped')
            if src: verdict += ' (' + src + ')'
            cnt[(et, verdict)] += 1
            print('rec +0x%05x entry %2d at +0x%05x id %4d type %d: Xbox 0x%08x PC 0x%08x expected %s (Xbox sections %s) %s'
                  % (qp, i, ep, eid, et, xv, pv, ('0x%08x' % exp) if exp is not None else '-',
                     sorted(cand) or '-', verdict))
            if verdict.startswith('WRONG') and out:
                struct.pack_into('<I', d, ep + 4, exp); fixed += 1
    print('counts (type, verdict): %s' % dict(cnt))
    if out:
        DP.sections[k_p] = DW.Section(SP.type, SP.id, bytes(d), SP.reloc, SP.flags, SP.ver, SP.spec, SP.pad)
        raw = DP.write('le')
        if open(pp, 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        open(out, 'wb').write(raw)
        DR = DW.read(open(out, 'rb').read(), 'le')
        assert [(a.type, a.id, a.data, a.reloc) for a in DR.sections] == [(b.type, b.id, b.data, b.reloc) for b in DP.sections]
        print('wrote %s: %d values, readback ok' % (out, fixed))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
