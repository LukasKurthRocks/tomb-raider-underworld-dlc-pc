"""Map the statically linked FMOD Ex C++ API wrappers in a 32-bit PE (tru.exe) and their callers (read-only;
TruMenu 0.20.1 sound list, 2026-11-06).

tru.exe does not import fmodex.dll: FMOD Ex is linked into the exe (strings ..\\..\\src\\fmod_systemi.cpp etc.).
Every public C++ method (FMOD::System / Channel / ChannelGroup / Sound ..., __stdcall, `this` on the stack) is a
small wrapper of the form
    push ebp; mov ebp, esp; lea eax, [ebp+8]; push eax; push [ebp+8]; call VALIDATE; test eax, eax; pop; pop; jne ..
    ... call INTERNAL  |  call [eax+SLOT]  ...; pop ebp; ret N
This tool finds every such wrapper (byte pattern), groups them by VALIDATE (= the class), and prints for each the
argument count (ret N / 4 - 1 without `this`), the internal target or vtable slot, the number of direct callers
outside the FMOD range and up to --show caller sites.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_fmod_api_map.py EXE [--lib-from VA] [--lib-to VA] [--show N]
  defaults: --lib-from 0x7b9000 --lib-to 0x7d1000 (the FMOD object files in tru.exe 1.0 PC), --show 4
"""
import sys, os, struct
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

HEAD = bytes.fromhex('558bec8d450850ff7508e8')


def main(argv):
    if not argv: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    lib_from, lib_to, show = 0x7b9000, 0x7d1000, 4
    i = 1
    while i < len(argv):
        if argv[i] == '--lib-from': lib_from = int(argv[i + 1], 16); i += 2
        elif argv[i] == '--lib-to': lib_to = int(argv[i + 1], 16); i += 2
        elif argv[i] == '--show': show = int(argv[i + 1]); i += 2
        else: sys.exit('unknown argument ' + argv[i])
    base, secs = PE.sections(exe)
    code = [(va, rptr, size) for name, va, rptr, size, ch in secs if ch & 0x20000000]

    def off(a):
        for va, rptr, size in code:
            if va <= a < va + size: return rptr + a - va
        return -1

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    wrappers = []
    for va, rptr, size in code:
        blob = exe[rptr:rptr + size]
        p = blob.find(HEAD)
        while p >= 0:
            a = va + p
            if lib_from <= a < lib_to:
                vt = (a + len(HEAD) + 4 + struct.unpack_from('<i', blob, p + len(HEAD))[0]) & 0xffffffff
                inner, ret = None, None
                for ins in md.disasm(blob[p + len(HEAD) + 4:p + 160], a + len(HEAD) + 4):
                    if ins.mnemonic == 'call' and inner is None: inner = ins.op_str
                    if ins.mnemonic == 'jmp' and inner is None and not ins.op_str.startswith('0x7b'): inner = 'jmp ' + ins.op_str
                    if ins.mnemonic == 'ret':
                        ret = int(ins.op_str, 16) if ins.op_str else 0
                        break
                wrappers.append((a, vt, inner, ret))
            p = blob.find(HEAD, p + 1)
    # callers from outside the library
    targets = {w[0]: [] for w in wrappers}
    for va, rptr, size in code:
        blob = exe[rptr:rptr + size]
        for k in range(len(blob) - 5):
            if blob[k] != 0xe8: continue
            src = va + k
            if lib_from <= src < lib_to: continue
            t = (src + 5 + struct.unpack_from('<i', blob, k + 1)[0]) & 0xffffffff
            if t in targets: targets[t].append(src)
    by_class = {}
    for w in wrappers: by_class.setdefault(w[1], []).append(w)
    for vt in sorted(by_class):
        print('== validate 0x%08x: %d wrappers' % (vt, len(by_class[vt])))
        for a, _, inner, ret in by_class[vt]:
            n = (ret // 4 - 1) if ret else -1
            cs = targets[a]
            print('  0x%08x args %2d  inner %-28s callers %3d  %s' % (
                a, n, inner, len(cs), ' '.join('0x%08x' % c for c in cs[:show])))
    print('total wrappers %d, with outside callers %d' % (
        len(wrappers), sum(1 for w in wrappers if targets[w[0]])))


if __name__ == '__main__':
    main(sys.argv[1:])
