r"""P4a: dump a base PC lib slot (from shaderlibs.pkl P) with its light block marked and the constant table.
Usage: ../bin/pyt -t 300 work/p4a_shader_1311/dump_pc_slot.py LIB SLOT OUT.txt"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
from tu_light_transplant import F9, sm3asm, libs


def main(a):
    lid, k, outp = int(a[0]), int(a[1]), a[2]
    L = libs()['P'][lid]
    blob = L['entries'][L['slots'][k]]['blob']
    p = F9.decode_pc(blob); p0, p1 = F9.pc_light_block(p)
    with open(outp, 'w', encoding='utf-8', newline='\n') as f:
        f.write('lib %d slot %d slots %s light block [%s,%s)\n' % (lid, k, L['slots'], p0, p1))
        for c in F9.pc_ctab(blob): f.write('ctab %s\n' % (c,))
        for i in F9.header(p): f.write('   hdr %s\n' % sm3asm.fmt_instr(i, 'ps'))
        for j, i in enumerate(F9.body(p)):
            f.write('%s%4d  %s\n' % ('[]' if p0 is not None and p0 <= j < p1 else '  ', j, sm3asm.fmt_instr(i, 'ps')))
    print('wrote %s' % outp)


if __name__ == '__main__':
    main(sys.argv[1:])
