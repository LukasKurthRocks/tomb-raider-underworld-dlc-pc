"""Check / fix state-chart activity values whose type the title-update code reads as one byte (read-only by default).

Shadow combat translation (docs Befund-Schattenkampf.md): Lara's state parameter 0x40f (activity id 1039, value type
46) is the target-list index of states 1017 / 1020 / 1019; the TU reads it with `lbz r8, 4(record)` (0x8245f64c,
0x8245f6a0, 0x8245f3c4: s8 at value +0) - so the 4 value bytes are {u8, 3 x 0} on both platforms. The converted PC
chart has some of these values byte-reversed as u32 / u16 pairs (index 6 read as 0, 0x6000000 ...).

Activity entry: 8 bytes {u16 id, u16 type, 4 value bytes} at state record +0x14 (tools/chart_state_path.py). Xbox and
PC records are paired by order (same chart, same record count required). For every entry of a listed type the
expected PC value bytes are the Xbox value bytes unchanged (u8 + three zero bytes; the tool refuses if the Xbox pad
bytes are not zero).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/chart_act_u8_fix.py XBOX.drm PC.drm SID [--types 46] [--out FIXED.drm]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import state_actlist_fix as SA


def section(D, sid):
    for k, s in enumerate(D.sections):
        if s.id == sid and s.type == 7: return k, s
    raise SystemExit("DTP %d not found" % sid)


def main(argv):
    if len(argv) < 3:
        print(__doc__); return 2
    out = argv[argv.index("--out") + 1] if "--out" in argv else None
    types = {46}
    if "--types" in argv: types = {int(x, 0) for x in argv[argv.index("--types") + 1].split(",")}
    sid = int(argv[2])
    DX = DW.read(open(argv[0], "rb").read(), "be")
    DP = DW.read(open(argv[1], "rb").read(), "le")
    _, sx = section(DX, sid)
    kp, sp = section(DP, sid)
    rx = sorted(SA.records(sx, "be"))
    rp = sorted(SA.records(sp, "le"))
    if len(rx) != len(rp): raise SystemExit("record counts differ: Xbox %d, PC %d" % (len(rx), len(rp)))
    d = bytearray(sp.data)
    n = wrong = 0
    for k, (a, b) in enumerate(zip(rx, rp)):
        if a[2][5] != b[2][5]: raise SystemExit("record %d: activity counts differ" % k)
        for j in range(a[2][5]):
            ox, op = a[3] + 8 * j, b[3] + 8 * j
            ix, tx = struct.unpack_from(">2H", sx.data, ox)
            ip, tp = struct.unpack_from("<2H", d, op)
            if (ix, tx) != (ip, tp): raise SystemExit("record %d entry %d: id / type differ (%d/%d vs %d/%d)" % (k, j, ix, tx, ip, tp))
            if tx not in types: continue
            n += 1
            xv, pv = bytes(sx.data[ox + 4:ox + 8]), bytes(d[op + 4:op + 8])
            if xv[1:] != b"\0\0\0": raise SystemExit("record %d entry %d (id %d): Xbox value %s is not one byte" % (k, j, ix, xv.hex()))
            ok = pv == xv
            if not ok:
                wrong += 1
                d[op + 4:op + 8] = xv
            print("record #%d +0x%x id %d type %d: Xbox %s PC %s -> %s" % (k, b[0], ix, tx, xv.hex(), pv.hex(),
                  "ok" if ok else "WRONG (byte value %d)" % xv[0]))
    print("%d entries of types %s, %d wrong" % (n, sorted(types), wrong))
    if out:
        DP.sections[kp] = DW.Section(sp.type, sp.id, bytes(d), sp.reloc, sp.flags, sp.ver, sp.spec, sp.pad)
        raw = DP.write("le")
        if open(argv[1], "rb").read(4) == b"CDRM": raw = DW.cdrm_encode(raw, "le")
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        open(out, "wb").write(raw)
        DR = DW.read(open(out, "rb").read(), "le")
        D0 = DW.read(open(argv[1], "rb").read(), "le")
        changed = [s.id for a, s in zip(D0.sections, DR.sections) if (a.data, a.reloc) != (s.data, s.reloc)]
        assert changed == ([sid] if wrong else []), changed
        assert bytes(section(DR, sid)[1].data) == bytes(d)
        print("wrote %s: sections changed %s, readback ok" % (out, changed))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
