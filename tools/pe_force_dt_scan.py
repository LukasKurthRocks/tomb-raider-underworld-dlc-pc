"""Frame-time use around the physics force API of tru.exe (read-only; Q69, 2026-11-11, finding Befund-PC-Technik-Q69-1111).

For every direct call of the body force API - AddForce 0x4dd710, AddForceAtPos 0x4dd750, AddTorque 0x4dd7e0 (thiscall
on a MultibodySystem body: +0xe0 force / +0xf0 torque accumulators, integrated as v += dt x F / m and cleared after the
step) - the enclosing function (start by the int3-padding heuristic of pe_dis) is disassembled up to the last call site
+ 0x40 and every instruction that reads the frame time is listed: 0xe7f188 scaled dt, 0xe7f190 / 0xe7f194 dt,
0xe7f1a0 world time scale. A function with no frame-time read that applies a ONE-FRAME push through this API gives
dt x F / m (weaker at high frame rates); a continuous force is correct without one. Prints only addresses and
instruction text (no game bytes).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_force_dt_scan.py EXE [API,API..]      APIs as hex VAs (default the three above)
Output: 'func 0x........: <API>@<site>, ..', '   dt reads: N', the reads; last line the totals.
"""
import sys, os, struct
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

DT = {0xe7f188: 'dt(scaled)', 0xe7f190: 'dt(unscaled)', 0xe7f194: 'dt2(scaled)', 0xe7f1a0: 'worldscale'}
API = {0x4dd710: 'AddForce', 0x4dd750: 'AddForceAtPos', 0x4dd7e0: 'AddTorque'}


def off_of(secs, a):
    for _, sva, rptr, size, _ in secs:
        if sva <= a < sva + size:
            return rptr + a - sva
    return -1


def func_start(exe, secs, a):
    o = off_of(secs, a)
    i = o
    while i > 2:
        if exe[i - 1] == 0xcc and exe[i - 2] == 0xcc:
            return a - (o - i)
        i -= 1
    return a


def call_sites(exe, secs, targets):
    """(site, target) of every E8 rel32 into targets in executable sections (the pe_callers byte scan)"""
    out = []
    for name, va, rptr, size, chars in secs:
        if not chars & 0x20000000:
            continue
        blob = exe[rptr:rptr + size]
        for i in range(1, len(blob) - 4):
            if blob[i - 1] != 0xe8:
                continue
            t = (va + i + 4 + struct.unpack_from('<i', blob, i)[0]) & 0xffffffff
            if t in targets:
                out.append((va + i - 1, t))
    return out


def main(argv):
    exe = open(argv[0], 'rb').read()
    targets = set(int(x, 16) for x in argv[1].split(',')) if len(argv) > 1 else set(API)
    base, secs = PE.sections(exe)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    funcs = {}
    sites = call_sites(exe, secs, targets)
    for site, tgt in sites:
        funcs.setdefault(func_start(exe, secs, site), []).append((site, API.get(tgt, '0x%08x' % tgt)))
    no_dt = 0
    for fs in sorted(funcs):
        end = max(s for s, _ in funcs[fs]) + 0x40
        o = off_of(secs, fs)
        reads = []
        for ins in md.disasm(exe[o:o + (end - fs)], fs):
            for va, what in DT.items():
                if ('0x%x' % va) in ins.op_str:
                    reads.append('%08x %s %s [%s]' % (ins.address, ins.mnemonic, ins.op_str, what))
        no_dt += not reads
        print('func 0x%08x: %s' % (fs, ', '.join('%s@0x%08x' % (n, s) for s, n in funcs[fs])))
        print('   dt reads: %d' % len(reads))
        for r in reads:
            print('     ' + r)
    print('total: %d calls in %d functions, %d functions without a frame-time read' % (len(sites), len(funcs), no_dt))


if __name__ == '__main__':
    main(sys.argv[1:])
