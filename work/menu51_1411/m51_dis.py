"""TruMenu 0.22.51 research helper (read only): based-displacement search in .text of the PC exe.

Usage (from trudlcport):
  ../bin/pyt work/menu51_1411/m51_dis.py EXE disp LO HI     instructions with a memory operand whose displacement is in
                                                         [LO, HI) and that has a base / index register
  ../bin/pyt work/menu51_1411/m51_dis.py EXE floats VA N    N floats at VA (with the raw dwords)
Output goes to stdout; nothing is written. Uses the PE helpers of work/ledge18a_0811/qol_pe.py and the function-start
heuristic of work/sonar_1411/sonar_dis.py.
"""
import os
import sys
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'work', 'ledge18a_0811'))
sys.path.insert(0, os.path.join(ROOT, 'work', 'sonar_1411'))
import qol_pe as P  # noqa: E402
import capstone  # noqa: E402
import sonar_dis as S  # noqa: E402


def main(a):
    d, base, secs, pe = P.load(a[0])
    mode = a[1]
    if mode == 'disp':
        lo, hi = int(a[2], 16), int(a[3], 16)
        code, va = P.text(d, secs)
        md = P.cs(True)
        for ins in md.disasm(code, va):
            if ins.id == 0:
                continue
            for op in ins.operands:
                if op.type == capstone.x86.X86_OP_MEM and (op.mem.base != 0 or op.mem.index != 0):
                    v = op.mem.disp & 0xffffffff
                    if lo <= v < hi:
                        print('%08x  fn %08x  %s %s' % (ins.address, S.fstart(code, va, ins.address), ins.mnemonic,
                                                        ins.op_str))
                        break
    elif mode == 'floats':
        v = int(a[2], 16)
        n = int(a[3])
        off = P.va2off(secs, v)
        for k in range(n):
            w = struct.unpack_from('<I', d, off + 4 * k)[0]
            f = struct.unpack_from('<f', d, off + 4 * k)[0]
            print('%08x  %08x  %r' % (v + 4 * k, w, f))
    else:
        raise SystemExit('unknown mode ' + mode)


if __name__ == '__main__':
    main(sys.argv[1:])
