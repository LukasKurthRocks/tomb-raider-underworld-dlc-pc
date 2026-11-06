"""List x86 instructions of a 32-bit PE (tru.exe) whose memory operand or immediate matches a filter (read-only;
thrall data fields 2026-11-06: indexed accesses into enemy tune arrays such as [R + I*4 + 0x80], and record strides
such as imul R, R, 0x228).

Filters (all given ones must hold for one operand):
  --disp X[,X..]   memory displacement (hex)
  --indexed        memory operand has an index register
  --scale N        index scale
  --imm X[,X..]    an immediate operand (hex), e.g. a record size used by imul / add
  --mnem M[,M..]   instruction mnemonic(s)
  --from VA --to VA  address range
Usage (from the repository root):
  ../bin/pyt -t 900 tools/pe_mem_operand_scan.py EXE [filters]
"""
import sys, os
import capstone
from capstone import x86
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def opt(argv, name, conv=None, flag=False):
    if name not in argv: return False if flag else None
    k = argv.index(name)
    if flag: del argv[k]; return True
    v = argv[k + 1]; del argv[k:k + 2]
    return conv(v) if conv else v


def main(argv):
    disp = opt(argv, '--disp', lambda v: {int(x, 16) for x in v.split(',')})
    imm = opt(argv, '--imm', lambda v: {int(x, 16) for x in v.split(',')})
    mnem = opt(argv, '--mnem', lambda v: set(v.split(',')))
    scale = opt(argv, '--scale', int)
    lo = opt(argv, '--from', lambda v: int(v, 16))
    hi = opt(argv, '--to', lambda v: int(v, 16))
    indexed = opt(argv, '--indexed', flag=True)
    if not argv: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    n = 0
    for name, va, raw_off, size, chars in secs:
        if not chars & 0x20000000: continue
        code = exe[raw_off:raw_off + size]
        off = 0
        while off < len(code):
            got = False
            for i in md.disasm(code[off:], va + off):
                off = i.address - va + i.size
                got = True
                if lo is not None and i.address < lo: continue
                if hi is not None and i.address >= hi: continue
                if mnem and i.mnemonic not in mnem: continue
                ok_mem = disp is None and not indexed and scale is None
                ok_imm = imm is None
                for o in i.operands:
                    if o.type == x86.X86_OP_MEM:
                        if disp is not None and o.mem.disp not in disp: continue
                        if indexed and o.mem.index == 0: continue
                        if scale is not None and o.mem.scale != scale: continue
                        ok_mem = True
                    elif o.type == x86.X86_OP_IMM and imm is not None and (o.imm & 0xffffffff) in imm:
                        ok_imm = True
                if ok_mem and ok_imm:
                    print('%08x  %s %s' % (i.address, i.mnemonic, i.op_str))
                    n += 1
            if not got: off += 1
    print('%d instruction(s)' % n)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
