"""Count the code references to absolute data addresses inside a range of a 32-bit PE (x86) such as tru.exe,
read-only: every instruction of the executable sections with a memory operand without base register (absolute or
absolute + index) or an imm32 operand whose value lies in [LO, HI). Prints per address the number of references and
how many of them lie inside / outside an optional code window, then a summary.
Example (coop feasibility, docs Befund-Koop-Stufe0-0611.md): which player-module globals (0xfad000..0xfaf000) the
code uses, and how much of that use sits outside the player code (0x6e0000..0x780000).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/pe_abs_range_uses.py EXE LO HI [--code-from VA --code-to VA] [--top N]
"""
import sys, os, collections
import capstone
from capstone import x86
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def arg(argv, name, default=None):
    return int(argv[argv.index(name) + 1], 0) if name in argv else default


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    lo, hi = int(argv[1], 0), int(argv[2], 0)
    cfrom, cto = arg(argv, '--code-from'), arg(argv, '--code-to')
    top = arg(argv, '--top', 0)
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    md.skipdata = True
    total = collections.Counter()
    inside = collections.Counter()
    for name, sva, rptr, size, ch in secs:
        if not (ch & 0x20000000):
            continue
        for ins in md.disasm(exe[rptr:rptr + size], sva):
            if ins.id == 0:                     # skipdata pseudo instruction (.byte)
                continue
            hits = set()
            for op in ins.operands:
                if op.type == x86.X86_OP_MEM and op.mem.base == 0:
                    v = op.mem.disp & 0xffffffff
                    if lo <= v < hi:
                        hits.add(v)
                elif op.type == x86.X86_OP_IMM:
                    v = op.imm & 0xffffffff
                    if lo <= v < hi:
                        hits.add(v)
            for v in hits:
                total[v] += 1
                if cfrom is not None and cfrom <= ins.address < cto:
                    inside[v] += 1
    rows = sorted(total.items(), key=lambda kv: (-kv[1], kv[0]))
    if top:
        rows = rows[:top]
    for v, n in rows:
        if cfrom is not None:
            print('0x%08x  %5d refs  (%d inside 0x%x..0x%x, %d outside)' % (v, n, inside[v], cfrom, cto, n - inside[v]))
        else:
            print('0x%08x  %5d refs' % (v, n))
    allrefs = sum(total.values())
    print('summary: %d distinct addresses in 0x%x..0x%x, %d references' % (len(total), lo, hi, allrefs), end='')
    if cfrom is not None:
        ins_n = sum(inside.values())
        print(', %d inside the code window, %d outside' % (ins_n, allrefs - ins_n))
    else:
        print()


if __name__ == '__main__':
    main(sys.argv[1:])
