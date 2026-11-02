"""Compare the light sub-blocks (`if bN ... endif`) of base PC pixel-shader libraries (read-only; test 50c, rock vein
strip). The upstream light transplant (tools/tu_light_transplant.py) found two PC light-chain variants among the donors
whose Xbox light block is equivalent; they differ in the sun light (b6) and slightly in b3. This tool shows, per PC
lib and slot, each `if bN` block's instruction count and a register-normalised hash, so the variant a PC lib belongs
to (e.g. the material's current surrogate) can be read off.

Normalisation: temps renamed in order of first appearance inside the block, constants / samplers / inputs kept.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/ps_bool_block_cmp.py PCLIB[,PCLIB...] [SLOT] [--bools 0,3,6] [--diff A B]
  --diff A B: unified diff of the normalised b6 (or the first --bools) block of PC libs A and B
"""
import sys, os, hashlib, difflib
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'shader4'))
import sm3asm, sm3dis
from column_shader_translate import libs, trim


def blocks(prog):
    """{bool register: [instructions of the outermost `if bN` block]} (first occurrence per bool)"""
    out = {}; ins = prog.instrs(); i = 0
    while i < len(ins):
        x = ins[i]
        if x.op == 'if' and x.ops and x.ops[0].rtype == sm3asm.RT_CONSTBOOL and x.ops[0].num not in out:
            depth = 0; j = i
            while j < len(ins):
                if ins[j].op in ('if', 'ifc', 'rep', 'loop'): depth += 1
                elif ins[j].op in ('endif', 'endrep', 'endloop'):
                    depth -= 1
                    if depth == 0: break
                j += 1
            out[x.ops[0].num] = ins[i:j + 1]
        i += 1
    return out


def norm(block):
    ren = {}; lines = []
    for x in block:
        for o in x.ops:
            if o.rtype == sm3asm.RT_TEMP and o.num not in ren: ren[o.num] = len(ren)
        t = sm3asm.fmt_instr(x, 1)
        # rename temps r<N> -> t<k> (longest numbers first)
        for n in sorted(ren, key=lambda v: -v): t = t.replace('r%d' % n, 'T%d' % ren[n])
        lines.append(t)
    return lines


def main(a):
    want = None
    if '--bools' in a: k = a.index('--bools'); want = [int(x) for x in a[k + 1].split(',')]; del a[k:k + 2]
    diff = None
    if '--diff' in a: k = a.index('--diff'); diff = (int(a[k + 1]), int(a[k + 2])); del a[k:k + 3]
    ids = [int(x) for x in a[0].split(',')] if a and not diff else []
    slot = int(a[1]) if len(a) > 1 else (int(a[0]) if diff and a else 0)
    L = libs(); P = L['P']
    def get(pid):
        lib = P[pid]; e = lib['entries'][lib['slots'][slot]]
        return blocks(sm3asm.decode(trim(e['blob'])))
    if diff:
        b = (want or [6])[0]
        A, B = norm(get(diff[0]).get(b, [])), norm(get(diff[1]).get(b, []))
        print('\n'.join(difflib.unified_diff(A, B, 'p%d b%d' % (diff[0], b), 'p%d b%d' % (diff[1], b), lineterm='', n=1)))
        return
    for pid in ids:
        bl = get(pid)
        cells = []
        for b in sorted(bl):
            if want and b not in want: continue
            n = norm(bl[b])
            cells.append('b%d %3d %s' % (b, len(n), hashlib.md5('\n'.join(n).encode()).hexdigest()[:8]))
        print('PC %5d slot %d: %s' % (pid, slot, '  '.join(cells)))


if __name__ == '__main__':
    main(sys.argv[1:])
