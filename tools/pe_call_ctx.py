"""Every direct call (E8) of one function in a 32-bit PE (x86) such as tru.exe with the N instructions before it
(read-only; night 04.11., workspace docs Befund-Restrisiken-0411.md, task B: which callers of the section lookup
tru+0x14df80 take the id from a record field such as [reg+0xc] / [reg+0x14]).

The bytes before each call site are disassembled with capstone from a start that decodes the call itself (tried from
LOOKBACK bytes back towards the call). --grep TEXT keeps only sites whose context contains TEXT.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/pe_call_ctx.py EXE FUNC_VA [--ctx 6] [--lookback 48] [--grep TEXT] [--out FILE]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone
import pe_callers as PE


def main(argv):
    def opt(n, d):
        if n in argv:
            k = argv.index(n); v = argv[k + 1]; del argv[k:k + 2]; return v
        return d
    ctx = int(opt('--ctx', '6')); lb = int(opt('--lookback', '48')); g = opt('--grep', None); out = opt('--out', None)
    exe = open(argv[0], 'rb').read(); func = int(argv[1], 16)
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    L = []; n = 0; shown = 0
    for name, sva, rptr, size, chars in secs:
        if not (chars & 0x20000000): continue
        blob = exe[rptr:rptr + size]
        for i in range(len(blob) - 5):
            if blob[i] != 0xe8: continue
            if (sva + i + 5 + struct.unpack_from('<i', blob, i + 1)[0]) & 0xffffffff != func: continue
            n += 1
            best = None
            for st in range(max(0, i - lb), i + 1):
                ins = list(md.disasm(blob[st:i + 5], sva + st))
                if ins and ins[-1].address == sva + i and ins[-1].mnemonic == 'call':
                    best = ins; break
            lines = ['   0x%08x  %s %s' % (q.address, q.mnemonic, q.op_str) for q in (best or [])[-ctx - 1:]]
            if g and not any(g in l for l in lines): continue
            shown += 1
            L.append('== 0x%08x (tru+0x%x)' % (sva + i, sva + i - base)); L += lines
    L.append('%d call sites, %d shown' % (n, shown))
    text = '\n'.join(L) + '\n'
    if out: open(out, 'w', encoding='utf-8').write(text); print(L[-1] + ' -> ' + out)
    else: sys.stdout.write(text)


if __name__ == '__main__':
    main(sys.argv[1:])
