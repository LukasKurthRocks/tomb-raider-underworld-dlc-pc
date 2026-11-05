"""Find the IMA ADPCM tables (89-entry step table, index adjust table) in a PE file and the code that reads them
(read-only; task F13 "S-Laute": which decoder does tru.exe use for .mul speech, and does it match our model in
tools/compare_audio.ima_decode?).

Searches the whole file for the step table as int16 / int32 little endian and for the index table
(-1,-1,-1,-1,2,4,6,8 as int8 / int16 / int32), converts file offsets to virtual addresses, then lists every
instruction in .text whose memory operand displacement or immediate lies inside a found table (capstone sweep).
With --func VA it disassembles from VA until the first ret (to read a decoder loop).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/f13_ima_tables.py EXE                 (tables + references)
  ../bin/pyt -t 120 tools/f13_ima_tables.py EXE --func 0x4a1230 [--max 400]
  ../bin/pyt -t 600 tools/f13_ima_tables.py EXE --refs 0xcd3bd0 0xcd43d0   (references into an address range)
  ../bin/pyt -t 60  tools/f13_ima_tables.py EXE --dump 0x8a96f0 16          (hex dump at a virtual address)
"""
import sys, struct
import capstone

STEP = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97,
        107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
        876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428,
        4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350,
        22385, 24623, 27086, 29794, 32767]
IDX = [-1, -1, -1, -1, 2, 4, 6, 8]


def sections(d):
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    n = struct.unpack_from('<H', d, pe + 6)[0]; opt = struct.unpack_from('<H', d, pe + 20)[0]
    base = struct.unpack_from('<I', d, pe + 24 + 28)[0]
    out = []
    for k in range(n):
        name, vs, va, rs, ro = struct.unpack_from('<8sIIII', d, pe + 24 + opt + 40 * k)
        out.append((name.rstrip(b'\0').decode('latin-1'), va, vs, ro, rs))
    return base, out


def off2va(base, secs, off):
    for name, va, vs, ro, rs in secs:
        if ro <= off < ro + rs: return base + va + off - ro, name
    return None, None


def find_all(d, pat):
    r = []; i = d.find(pat)
    while i >= 0: r.append(i); i = d.find(pat, i + 1)
    return r


def main(argv):
    path = argv[0]; d = open(path, 'rb').read()
    base, secs = sections(d)
    if '--dump' in argv:             # hex dump of N bytes at a virtual address (masks, constants)
        k = argv.index('--dump'); va0 = int(argv[k + 1], 16); nb = int(argv[k + 2])
        for name, va, vs, ro, rs in secs:
            if base + va <= va0 < base + va + rs:
                o = ro + va0 - base - va; print('%08x (%s): %s' % (va0, name, d[o:o + nb].hex(' '))); return
        print('address not in a raw section (bss?)'); return
    if '--func' in argv:
        va0 = int(argv[argv.index('--func') + 1], 16)
        mx = int(argv[argv.index('--max') + 1]) if '--max' in argv else 300
        for name, va, vs, ro, rs in secs:
            if base + va <= va0 < base + va + rs:
                code = d[ro + va0 - base - va: ro + rs]; break
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for k, ins in enumerate(md.disasm(code, va0)):
            print('%08x  %-8s %s' % (ins.address, ins.mnemonic, ins.op_str))
            if k >= mx: break
        return
    tables = []
    if '--refs' in argv:             # any instruction with a displacement / immediate in [LO, HI)
        k = argv.index('--refs'); tables.append(('range', int(argv[k + 1], 16), int(argv[k + 2], 16)))
    for label, pat in [] if tables else (('step int16', struct.pack('<89h', *STEP)), ('step int32', struct.pack('<89i', *STEP)),
                       ('idx int8', struct.pack('<8b', *IDX)), ('idx int16', struct.pack('<8h', *IDX)),
                       ('idx int32', struct.pack('<8i', *IDX))):
        for off in find_all(d, pat):
            va, sec = off2va(base, secs, off)
            nxt = d[off + len(pat): off + len(pat) + 32].hex()
            print('%-10s file 0x%x  va %s (%s)  next bytes %s' % (label, off, hex(va) if va else '-', sec, nxt))
            if va: tables.append((label, va, va + len(pat) * (2 if label.startswith('idx') else 1)))
    if not tables: print('no IMA tables found'); return
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); md.detail = True; md.skipdata = True
    for name, va, vs, ro, rs in secs:
        if not name.startswith('.text'): continue
        for ins in md.disasm(d[ro:ro + rs], base + va):
            if ins.id == 0: continue
            vals = []
            try:
                for op in ins.operands:
                    if op.type == capstone.x86.X86_OP_MEM: vals.append(op.mem.disp & 0xffffffff)
                    elif op.type == capstone.x86.X86_OP_IMM: vals.append(op.imm & 0xffffffff)
            except capstone.CsError:
                continue
            for v in vals:
                for label, lo, hi in tables:
                    if lo <= v < hi:
                        print('ref %-10s %08x  %-6s %s' % (label, ins.address, ins.mnemonic, ins.op_str))


if __name__ == '__main__':
    main(sys.argv[1:])
