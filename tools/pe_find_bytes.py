"""Find a hex byte pattern (with ?? wildcards) in the sections of a 32-bit PE such as tru.exe (read-only; TruMenu 0.10
spawn facts: which code compares / writes the object tracker status word +0xe with 2).

Prints the virtual address of every hit (section name, at most MAX hits per pattern). Byte-pattern based like
tools/pe_callers.py: no disassembler, so a hit can sit inside another instruction - check it with tools/pe_dis.py.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_find_bytes.py EXE "HEX ?? HEX" [--max N] [--code]
    HEX pairs may be separated by spaces; ?? matches any byte; --code = executable sections only; N default 50
  e.g. "<game folder>/tru.exe" "66 83 78 0e 02" "66 c7 46 0e 02 00"   (whole bytes only: one pattern per register)
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def compile_pattern(text):
    parts = text.replace(',', ' ').split()
    if len(parts) == 1 and len(parts[0]) > 2:
        s = parts[0]
        parts = [s[i:i + 2] for i in range(0, len(s), 2)]
    out = b''
    for p in parts:
        if p == '??': out += b'.'
        else: out += re.escape(bytes([int(p, 16)]))
    return re.compile(out, re.DOTALL)


def main(argv):
    exe = open(argv[0], 'rb').read()
    pats = []
    maxhits, code_only = 50, False
    i = 1
    while i < len(argv):
        if argv[i] == '--max': maxhits = int(argv[i + 1]); i += 2; continue
        if argv[i] == '--code': code_only = True; i += 1; continue
        pats.append(argv[i]); i += 1
    base, secs = PE.sections(exe)
    for text in pats:
        rx = compile_pattern(text)
        hits = 0
        for name, va, rptr, size, chars in secs:
            if code_only and not (chars & 0x20000000): continue
            blob = exe[rptr:rptr + size]
            for m in rx.finditer(blob):
                print('%-8s 0x%08x  %s' % (name, va + m.start(), text))
                hits += 1
                if hits >= maxhits: break
            if hits >= maxhits: break
        print('# %s: %d hit(s)%s' % (text, hits, ' (max reached)' if hits >= maxhits else ''))


if __name__ == '__main__':
    main(sys.argv[1:])
