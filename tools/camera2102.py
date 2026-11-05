"""TU state 2102 (camera manager) - read-only helpers (TruShadowPower 0.11, project doc Befund-Look.md section 7).

TU state 2102 slot 0 = 0x824627b0: r3 = 0x82efc780 (static camera manager), `b 0x822ae918`: if the current camera (+0x44)
is (+0xb50), or +0x44 == this+0x640 and +0x780 == +0xb50 -> tail call (+0xb50)->vtbl[0x80]. At run time +0xb50 is the
Lara camera (Xenia image: 0x82effab0, vtable 0x82068c60); its slot 0x80 is the TU-only 0x822c2130.

Modes (from the repository root):
  ../bin/pyt -t 300 tools/camera2102.py callers IMAGE TARGET[,TARGET]   every `bl TARGET` with the function around it
                                                                         (also targets without a .pdata entry)
  ../bin/pyt -t 300 tools/camera2102.py words IMAGE ADDR N              N big-endian words (runtime values of an image)
  ../bin/pyt -t 300 tools/camera2102.py slotcalls IMAGE FIELD SLOT [W]  `lbz FIELD` ... `lwz SLOT` + bctrl (vtable users)
  ../bin/pyt -t 300 tools/camera2102.py pcdefaults EXE                  PC sites `call tru+0x1d4080` (camera defaults
      [0xe7ee50]) directly followed by `mov reg, [eax+0x144]` - the inlined fallback of TU 0x822bc198, with the next
      instructions (does a settings lookup tru+0x14df80 follow?) and the function start
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as X


def callers(argv):
    path = argv[0]; want = {int(x, 16) for x in argv[1].split(',')}
    funcs, res = X.cached(path)
    for fs, items in sorted(res.items()):
        for x, k, v in items:
            if k == 'call' and v in want:
                f = X.func_of(funcs, x)
                print('0x%08x  bl 0x%08x  in 0x%08x..0x%08x' % (x, v, f[0] if f else 0, f[1] if f else 0))


def words(argv):
    d = open(argv[0], 'rb').read(); a = int(argv[1], 16); n = int(argv[2])
    for k in range(n):
        print('0x%08x  0x%08x' % (a + 4 * k, struct.unpack_from('>I', d, a + 4 * k - X.BASE)[0]))


def slotcalls(argv):
    """slotcalls IMAGE FIELD SLOT [WINDOW] - code where `lbz rX, FIELD(rY)` (e.g. 0x234, the model index of the render
    model list of instance +0x244) is followed within WINDOW instructions (default 16) by `lwz rZ, SLOT(rW)` and a
    bctrl: the Xbox users of a render-model-instance vtable slot (TruShadowPower 0.12, TU block 0x8247498c)"""
    d = open(argv[0], 'rb').read(); field = int(argv[1], 16); slot = int(argv[2], 16)
    win = int(argv[3]) if len(argv) > 3 else 16
    funcs, res = X.cached(argv[0])
    for fs, fe in funcs:
        a = fs
        while a < fe:
            w = struct.unpack_from('>I', d, a - X.BASE)[0]
            if w >> 26 == 34 and (w & 0xffff) == field:
                hit = None
                for k in range(1, win):
                    w2 = struct.unpack_from('>I', d, a + 4 * k - X.BASE)[0]
                    if w2 >> 26 == 32 and (w2 & 0xffff) == slot:
                        for j in range(k + 1, k + 6):
                            if struct.unpack_from('>I', d, a + 4 * j - X.BASE)[0] == 0x4e800421:
                                hit = a + 4 * j; break
                    if hit: break
                if hit: print('0x%08x  lbz +%#x ... bctrl at 0x%08x  in 0x%08x' % (a, field, hit, fs))
            a += 4


def pcdefaults(argv):
    import capstone
    import pe_callers as PE, pe_dis as PD
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    getter = 0x005d4080; n = 0; regs = {}
    for name, sva, rptr, size, ch in secs:
        if not (ch & 0x20000000): continue
        code = exe[rptr:rptr + size]
        i = code.find(b'\xe8')
        while i >= 0:
            if i + 5 <= len(code):
                va = sva + i
                rel = struct.unpack_from('<i', code, i + 1)[0]
                if va + 5 + rel == getter:
                    ins = list(md.disasm(code[i + 5:i + 5 + 48], va + 5))
                    if ins and ins[0].mnemonic == 'mov' and ins[0].op_str.endswith('[eax + 0x144]') and ins[0].size == 6:
                        n += 1
                        reg = ins[0].op_str.split(',')[0]
                        regs[reg] = regs.get(reg, 0) + 1
                        look = any(x.mnemonic == 'call' and x.op_str == '0x54df80' for x in ins[1:8])
                        print('0x%08x  call getter; 0x%08x %s %s (%s)  lookup tru+0x14df80 follows: %s  in 0x%08x'
                              % (va, ins[0].address, ins[0].mnemonic, ins[0].op_str, ins[0].bytes.hex(), look,
                                 PD.func_start(exe, secs, va)))
            i = code.find(b'\xe8', i + 1)
    print('%d sites, destination registers %s' % (n, regs))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    {'callers': callers, 'words': words, 'slotcalls': slotcalls, 'pcdefaults': pcdefaults}[sys.argv[1]](sys.argv[2:])
