"""Which instructions of a 32-bit PE (tru.exe) can SET or CLEAR one bit of a global dword - read-only (TruMenu 0.11
"Ablauf": player deaths = bit 0x10000 of the player state-mode word [0xfada74], set by DeathState::Entry 0x75aa50).

Linear sweep of the executable sections with capstone (as tools/pe_abs_uses.py). Every instruction whose FIRST operand
is the memory dword [ADDR] (absolute, also [reg + ADDR]) is a writer: mov / or / and / xor / add / sub / bts / btr / btc
/ inc / dec / not / neg / xchg / cmpxchg. For each one the verdict on BIT:
  sets      mov imm with the bit, or imm with the bit, bts / btc with the bit index
  clears    mov imm without the bit, and imm without the bit, btr / btc with the bit index
  keeps     or imm / and imm / xor imm that leave the bit alone
  reg=imm   mov [ADDR], reg where reg got an immediate in one of the 24 instructions before, with no other write of
            reg, no call (eax / ecx / edx) and no jump / ret in between (that value is judged; a jump INTO the range
            is not seen - check the hit with tools/pe_dis.py)
  unknown   anything else (register value not found, add / sub / xchg ...) - must be read by hand with tools/pe_dis.py
Reads of [ADDR] (cmp / test / mov reg, [ADDR] / movsx ...) are not writers and are only counted.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/pe_flag_bit_writers.py EXE ADDR BIT        e.g. ../data/pc/tru.exe 0xfada74 0x10000
"""
import sys, os, collections
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

WRITERS = {'mov', 'or', 'and', 'xor', 'add', 'sub', 'bts', 'btr', 'btc', 'inc', 'dec', 'not', 'neg', 'xchg', 'cmpxchg',
           'adc', 'sbb', 'shl', 'shr', 'sar', 'rol', 'ror'}


def main(argv):
    if len(argv) < 3: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    addr, bit = int(argv[1], 16), int(argv[2], 16)
    bitno = bit.bit_length() - 1
    key = '0x%x]' % addr
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.skipdata = True
    verdicts = collections.Counter()
    reads = 0
    for name, sva, rptr, size, ch in secs:
        if not (ch & 0x20000000): continue
        recent = collections.deque(maxlen=24)
        for ins in md.disasm(exe[rptr:rptr + size], sva):
            ops = [o.strip() for o in ins.op_str.split(',')]
            first = ops[0] if ops else ''
            if key in ins.op_str and not (first.startswith('dword ptr [') and key in first and ins.mnemonic in WRITERS):
                reads += 1
            elif key in ins.op_str:
                src = ops[1] if len(ops) > 1 else ''
                imm = None
                try:
                    imm = int(src, 0) & 0xffffffff
                except ValueError:
                    pass
                m = ins.mnemonic
                if m == 'mov' and imm is not None: v = 'sets' if imm & bit else 'clears'
                elif m == 'or' and imm is not None: v = 'sets' if imm & bit else 'keeps'
                elif m == 'and' and imm is not None: v = 'keeps' if imm & bit else 'clears'
                elif m == 'xor' and imm is not None: v = 'flips' if imm & bit else 'keeps'
                elif m in ('bts', 'btr', 'btc') and imm is not None:
                    v = ('sets' if m == 'bts' else 'clears' if m == 'btr' else 'flips') if imm == bitno else 'keeps'
                elif m == 'mov' and src in ('eax', 'ebx', 'ecx', 'edx', 'esi', 'edi', 'ebp'):
                    v = 'unknown'
                    for p in reversed(recent):
                        po = [o.strip() for o in p.op_str.split(',')]
                        if p.mnemonic in ('call', 'ret') or p.mnemonic.startswith('j'):
                            if p.mnemonic == 'call' and src not in ('eax', 'ecx', 'edx'): continue
                            break                              # a call clobbers eax / ecx / edx; a jump = other paths
                        if p.mnemonic == 'mov' and po and po[0] == src and len(po) > 1:
                            try:
                                val = int(po[1], 0) & 0xffffffff
                                v = 'reg=imm 0x%x: %s' % (val, 'sets' if val & bit else 'clears')
                            except ValueError:
                                pass
                            break
                        if po and po[0] == src: break          # the register was written otherwise
                else: v = 'unknown'
                verdicts[v.split(': ')[-1] if v.startswith('reg=imm') else v] += 1
                print('0x%08x  %-8s %-40s %s' % (ins.address, m, ins.op_str, v))
            recent.append(ins)
    print('writers of [0x%x] judged for bit 0x%x: %s; reads %d' % (addr, bit, ', '.join(
        '%s %d' % (k, verdicts[k]) for k in sorted(verdicts)), reads))


if __name__ == '__main__':
    main(sys.argv[1:])
