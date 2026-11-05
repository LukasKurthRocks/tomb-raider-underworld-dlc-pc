"""Check / fix the target-list parameter records of the DLC 2 player tuning (DTP 22497 of player_tru_dlc2_extension).

Shadow combat translation (docs Befund-Schattenkampf.md): the title update builds 10 targeters instead of 7; the
parameters of targeters 8 and 9 come from the tuning struct of object 858 (DTP 22497, struct at +0xf0): TU 0x82402208
reads `lwz r7, 0x94(tuning)` (count, u32) and walks `tuning +0x90` = 8-byte entries {`lbz` index (u8), 3 bytes, ptr}
-> param struct {u32 flags (TU 0x82403b48 `lwz`, bit tests 0x80000000 / 0x20000000 / 0x4000000 / 0x2000000), u32 n
(PC ctor tru+0x31d900 `cmp dword [ebx+4]`), n x ptr} -> sub struct {ptr record, u32 m (PC `cmp ecx, dword [eax+4]`),
u32 (0 / 1, read as both u8 and u32 give the same bytes), m x ptr} -> record {u16 kind (PC `movzx ecx, word [eax]`),
u16, f32, f32 x3 (PC `movss [eax+8 / +0xc / +0x10]`)}.

The converted PC file has these words mixed: some byte-reversed as u32, some as u16 pairs, some unchanged. Expected
PC bytes are derived from the Xbox bytes by the field type of each word; the record's second u16 and first float have
no PC reader in the constructor - their type is taken from the identical sibling records of the same table (u16 at
+2: records +0x234 / +0x248 / +0x270 converted so; f32 at +4: +0x238 / +0x24c / +0x260 / +0x274), and the tool says
so. Only these words are compared / written; nothing else of the file changes (checked on read-back).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/tuning_target_fix.py XBOX.drm PC.drm [--out FIXED.drm]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

SID = 22497
BASE = 0xf0             # tuning struct (u16 1, u16 type 60) inside the DTP
# (DTP offset, kind, why) - kind: u32, u8 (+3 bytes that must be 0 on both), u16u16, f32
FIELDS = [
    (BASE + 0x94, "u32", "tuning +0x94 count of the +0x90 table (TU 0x82402248 lwz)"),
    (0x2c0, "u8x", "table entry 0 index (TU 0x82402264 lbz)"),
    (0x2c8, "u8x", "table entry 1 index (TU 0x82402264 lbz)"),
    (0x2d0, "u32", "param of targeter 8: flags (TU 0x82403b48 lwz + bit tests)"),
    (0x2d4, "u32", "param of targeter 8: n (PC tru+0x31d9fd cmp dword)"),
    (0x2dc, "u32", "param of targeter 9: flags"),
    (0x2e0, "u32", "param of targeter 9: n"),
    (0x294, "u32", "sub struct +0x290: m (PC tru+0x31daaf cmp dword)"),
    (0x298, "u32", "sub struct +0x290: +8 (0 / 1)"),
    (0x2a8, "u32", "sub struct +0x2a4: m"),
    (0x2ac, "u32", "sub struct +0x2a4: +8 (0 / 1)"),
]
RECORDS = [0x1f0, 0x204, 0x220, 0x234, 0x248, 0x25c, 0x270]   # 0x14-byte records {u16, u16, f32 x4}
for r in RECORDS:
    FIELDS.append((r, "u16u16", "record +0x%x: u16 kind (PC movzx word) + u16 (type from the sibling records)" % r))
    FIELDS.append((r + 4, "f32", "record +0x%x +4 (f32, type from the sibling records)" % r))
    for k in (8, 0xc, 0x10):
        FIELDS.append((r + k, "f32", "record +0x%x +0x%x (PC movss)" % (r, k)))


def expect(xb, kind):
    if kind == "u32" or kind == "f32": return xb[::-1]
    if kind == "u16u16": return xb[1::-1] + xb[3:1:-1]
    if kind == "u8x": return xb[:1] + b"\0\0\0" if xb[1:] == b"\0\0\0" else None
    raise ValueError(kind)


def section(D, sid):
    for k, s in enumerate(D.sections):
        if s.id == sid and s.type == 7: return k, s
    raise SystemExit("DTP %d not found" % sid)


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    out = argv[argv.index("--out") + 1] if "--out" in argv else None
    DX = DW.read(open(argv[0], "rb").read(), "be")
    DP = DW.read(open(argv[1], "rb").read(), "le")
    _, sx = section(DX, SID)
    kp, sp = section(DP, SID)
    if len(sx.data) != len(sp.data): raise SystemExit("DTP %d sizes differ" % SID)
    rx = dict(R.parse(bytes(sx.reloc), "be").internal)
    rp = dict(R.parse(bytes(sp.reloc), "le").internal)
    d = bytearray(sp.data)
    wrong = 0
    for off, kind, why in FIELDS:
        if off in rx or off in rp: raise SystemExit("+0x%x is a pointer (relocation) - layout assumption wrong" % off)
        xb, pb = bytes(sx.data[off:off + 4]), bytes(d[off:off + 4])
        e = expect(xb, kind)
        if e is None: raise SystemExit("+0x%x: Xbox bytes %s do not fit %s" % (off, xb.hex(), kind))
        ok = e == pb
        wrong += not ok
        print("+0x%03x %-6s Xbox %s PC %s expected %s %s  (%s)" % (off, kind, xb.hex(), pb.hex(), e.hex(),
              "ok" if ok else "WRONG", why))
        if not ok: d[off:off + 4] = e
    # the pointer chain itself: tuning +0x90 -> table, entries -> params -> sub structs -> records
    for off in (BASE + 0x90, 0x2c4, 0x2cc, 0x2d8, 0x2e4, 0x290, 0x29c, 0x2a0, 0x2a4 + 0, 0x2b0, 0x2b4):
        print("pointer +0x%03x: Xbox -> +0x%x, PC -> +0x%x %s" % (off, rx.get(off, -1), rp.get(off, -1),
              "ok" if rx.get(off) == rp.get(off) else "DIFFERENT"))
    print("%d fields, %d wrong" % (len(FIELDS), wrong))
    if out:
        DP.sections[kp] = DW.Section(sp.type, sp.id, bytes(d), sp.reloc, sp.flags, sp.ver, sp.spec, sp.pad)
        raw = DP.write("le")
        if open(argv[1], "rb").read(4) == b"CDRM": raw = DW.cdrm_encode(raw, "le")
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        open(out, "wb").write(raw)
        DR = DW.read(open(out, "rb").read(), "le")
        D0 = DW.read(open(argv[1], "rb").read(), "le")
        changed = [s.id for a, s in zip(D0.sections, DR.sections) if (a.type, a.id, a.data, a.reloc) != (s.type, s.id, s.data, s.reloc)]
        assert changed == ([SID] if wrong else []), changed
        _, s2 = section(DR, SID)
        assert bytes(s2.data) == bytes(d)
        diff = sum(1 for i in range(0, len(d), 4) if D0.sections[kp].data[i:i + 4] != s2.data[i:i + 4])
        print("wrote %s: sections changed %s, %d words of DTP %d differ from the input, readback ok" % (out, changed, diff, SID))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
