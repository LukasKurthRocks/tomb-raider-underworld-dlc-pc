"""Why does the GPU driver reject port-generated pixel/vertex shaders? (read-only; DLC 2 test 13, upstream native test)

Reads tools/native_test/native_report.txt (FAIL/ok per shader file) and the shader binaries in
tools/native_test/shaders/ (written by native_extract.py) and counts, for rejected and accepted port shaders, the
features the native test's probes single out:
  * abs / absneg source modifier (source token bits 24-27 = 0xB / 0xC) - probes feat_ps_*_absmod were rejected
  * def (opcode 0x51) after the first arithmetic / texture instruction - probe_ps_def_after_instr was rejected
  * instruction slots > 4096 (PS30Slots / VS30Slots of the report)
D3D9 token format: version token, then instructions (opcode in bits 0-15, instruction length in bits 24-27 for
SM2+), end token 0x0000FFFF; comment tokens (0xFFFE) are skipped.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/shader_reject_check.py [--list N]
"""
import sys, os, struct, collections

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'native_test')
DCL, DEF, DEFI, DEFB, END, COMMENT = 0x1F, 0x51, 0x30, 0x2F, 0xFFFF, 0xFFFE
NO_SRC_MOD_OPS = {DCL, DEF, DEFI, DEFB}


def features(b):
    w = struct.unpack('<%dI' % (len(b) // 4), b[:len(b) // 4 * 4])
    f = collections.Counter(); i = 1; seen_arith = False; n = 0
    while i < len(w):
        t = w[i]; op = t & 0xFFFF
        if op == END: break
        if op == COMMENT: i += 1 + ((t >> 16) & 0x7FFF); continue
        ln = (t >> 24) & 0xF
        n += 1
        if op in (DEF, DEFI, DEFB):
            if seen_arith: f['def after instruction'] += 1
        elif op != DCL:
            seen_arith = True
            for k in range(2, ln + 1):           # token 1 = destination (for most ops), then sources
                if i + k >= len(w): break
                m = (w[i + k] >> 24) & 0xF
                if m == 0xB: f['abs source modifier'] += 1
                elif m == 0xC: f['absneg source modifier'] += 1
        i += 1 + ln
    f['_instructions'] = n
    return f


def main(argv):
    lim = int(argv[argv.index('--list') + 1]) if '--list' in argv else 0
    res = {}
    for line in open(os.path.join(HERE, 'native_report.txt'), encoding='utf-8', errors='replace'):
        p = line.strip().split('\t')
        if len(p) >= 3 and p[1] == 'shader' and p[0] in ('ok', 'FAIL'): res[p[2]] = p[0]
    tally = {'FAIL': collections.Counter(), 'ok': collections.Counter()}; n = collections.Counter(); unexplained = []
    for name, r in sorted(res.items()):
        if not name.startswith(('new_', 'pc_')): continue
        path = os.path.join(HERE, 'shaders', name)
        if not os.path.exists(path): continue
        f = features(open(path, 'rb').read())
        kind = name[:3] + ('ps' if '_ps_' in name else 'vs')
        n[(kind, r)] += 1
        for k, v in f.items():
            if not k.startswith('_') and v: tally[r][(kind, k)] += 1
        if f['_instructions'] > 4096: tally[r][(kind, '> 4096 instructions')] += 1
        if r == 'FAIL' and not any(v for k, v in f.items() if not k.startswith('_')) and f['_instructions'] <= 4096:
            unexplained.append(name)
    print('shaders by (origin+type, result):', dict(n))
    for r in ('FAIL', 'ok'):
        print('%s - shaders with the feature:' % r)
        for k, v in sorted(tally[r].items()): print('   %-40s %d' % (' '.join(k), v))
    print('rejected without any of these features: %d %s' % (len(unexplained), unexplained[:lim]))


if __name__ == '__main__':
    main(sys.argv[1:])
