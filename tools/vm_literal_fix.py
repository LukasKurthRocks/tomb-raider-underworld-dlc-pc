"""Literals of the engine's stack VM in converted DTPs: check them against the Xbox original and with --out repair them
(read-only unless --out; test 48l crash 2026-11-01 22:35:04, AV tru+0x448198 `rep movsd` with esi = [[obj+0x310]+0x58]
-> [0] + 36 x 0x04b10000, when Lara left the wall run (state 425 slot 2 tru+0x35eeb0 = message 0x69 to the player)).

The VM (tru.exe 2008 Steam build, interpreter tru+0x32b20, disassembly with tools/pe_dis.py): a program is a run of
u32 words; opcode = word >> 24 (byte table tru+0x32e48 / jump table tru+0x32df8); opcode 2 (handler tru+0x32b56)
pushes the NEXT u32 word (`mov ecx,[ecx]; mov [stack+top*4],ecx; pc += 4`), opcode 0x65 (tru+0x32dc9) pops a native
group / index and calls the native from the table tru+0x4ac128. So a literal is one u32 whatever it holds (int, float,
id) - the correct PC bytes are the Xbox word reversed as one u32. The anim native tru+0x448100 pops two floats, a flag
word and an animation index (36-byte records of [[obj+0x310]+0x58]); DTP 26870 of doppelganger_casual.drm pushed the
index 1201 (Xbox 0x000004b1) as 0x04b10000 (two u16 swapped).

Modes (from the repository root):
  ../bin/pyt -t 600 tools/vm_literal_fix.py check XBOX.drm PC.drm [--out OUT.drm]
        type-7 sections paired by id (same size); in every section that holds opcode-0x65 words, each word after an
        opcode-2 word (Xbox BE 0x02000000, PC LE the same) that is not relocated must equal the Xbox u32; lists the
        differences with their conversion mode, --out writes the repaired DRM (CDRM again if the input was CDRM)
  ../bin/pyt -t 600 tools/vm_literal_fix.py scan PC.drm
        PC file only: opcode-2 literals of the shape 0xHHHH0000 with 0 < HHHH < 0x1000 (a small integer whose u16
        halves were swapped) - a quick look at files without an Xbox original
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

PUSH = 0x02000000
CALL = 0x65000000


def rel(s, e):
    try:
        return dict(R.parse(bytes(s.reloc), e).internal) if s.reloc else {}
    except Exception:
        return {}


def mode(x, p):
    m16 = x[1::-1] + x[3:1:-1]
    for name, v in (('u32', x[::-1]), ('u16 pair', m16), ('raw', x)):
        if v == p: return name
    return 'other'


def check(argv):
    out = None
    if '--out' in argv: k = argv.index('--out'); out = argv[k + 1]; del argv[k:k + 2]
    XD = DW.read(open(argv[0], 'rb').read(), 'be')
    PD = DW.read(open(argv[1], 'rb').read(), 'le')
    xs = {s.id: s for s in XD.sections if s.type == 7}
    nsec = nlit = 0
    fixes = []
    for ps in PD.sections:
        if ps.type != 7 or ps.id not in xs: continue
        x, p = bytes(xs[ps.id].data), bytearray(ps.data)
        if len(x) != len(p): continue
        if not any(struct.unpack_from('>I', x, o)[0] == CALL for o in range(0, len(x) - 3, 4)): continue
        it = rel(ps, 'le')
        nsec += 1
        for o in range(0, len(x) - 7, 4):
            if struct.unpack_from('>I', x, o)[0] != PUSH or struct.unpack_from('<I', p, o)[0] != PUSH: continue
            q = o + 4
            if q in it: continue
            nlit += 1
            want = x[q:q + 4][::-1]
            if bytes(p[q:q + 4]) != want:
                fixes.append((ps, q, bytes(p[q:q + 4]), want, mode(x[q:q + 4], bytes(p[q:q + 4]))))
    print('%d VM sections paired, %d literals checked, %d wrong' % (nsec, nlit, len(fixes)))
    for ps, q, got, want, m in fixes:
        print('  DTP %6d +0x%05x: PC 0x%08x, Xbox u32 0x%08x (%s)' % (ps.id, q, struct.unpack('<I', got)[0],
              struct.unpack('<I', want)[0], m))
    if out:
        by = {}
        for ps, q, got, want, m in fixes: by.setdefault(ps.id, []).append((q, want))
        for ps in PD.sections:
            if ps.type == 7 and ps.id in by:
                d = bytearray(ps.data)
                for q, want in by[ps.id]: d[q:q + 4] = want
                ps.data = bytes(d)
        raw = PD.write('le')
        if open(argv[1], 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        open(out, 'wb').write(raw)
        chk = DW.read(open(out, 'rb').read(), 'le')
        assert len(chk.sections) == len(PD.sections)
        print('written %s (%d bytes, read back ok, %d words set)' % (out, len(raw), len(fixes)))


def scan(argv):
    PD = DW.read(open(argv[0], 'rb').read(), 'le')
    n = 0
    for ps in PD.sections:
        if ps.type != 7: continue
        p = bytes(ps.data)
        if not any(struct.unpack_from('<I', p, o)[0] == CALL for o in range(0, len(p) - 3, 4)): continue
        it = rel(ps, 'le')
        for o in range(0, len(p) - 7, 4):
            if struct.unpack_from('<I', p, o)[0] != PUSH or (o + 4) in it: continue
            v = struct.unpack_from('<I', p, o + 4)[0]
            if v & 0xffff == 0 and 0 < (v >> 16) < 0x1000:
                n += 1
                print('  DTP %6d +0x%05x: 0x%08x (= %d with the halves swapped)' % (ps.id, o + 4, v, v >> 16))
    print('%d suspicious literals' % n)


if __name__ == '__main__':
    a = sys.argv[1:]
    {'check': check, 'scan': scan}[a[0]](a[1:])
