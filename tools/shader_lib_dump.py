"""Dump the shaders of one ShaderLib section (type 9) of a PC DRM as disassembly (d3dcompiler_47 D3DDisassemble):
one .asm per slot entry plus a summary line (vs/ps, instruction count, textures sampled, constants read).
Read-only. Finding 43 follow-up: compare a library before / after tools/shader_const_fix.py (grapple ring).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/shader_lib_dump.py FILE.drm LIB_ID OUT_DIR
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, shader_disasm as SD
from shader_const_fix import lib_parse, split_end


def main(argv):
    src, lid, out = argv[0], int(argv[1]), argv[2]
    os.makedirs(out, exist_ok=True)
    D = DW.read(open(src, 'rb').read(), 'le')
    s = next(x for x in D.sections if x.type == 9 and x.id == lid)
    head, tb, offs, ents, ds = lib_parse(s.data)
    for o, (a, h, code, at) in sorted(ents.items()):
        body, _ = split_end(code)
        t = SD.disasm(body)
        slots = [i for i, x in enumerate(offs) if x == o]
        p = os.path.join(out, 'lib%d_entry%05x.asm' % (lid, o))
        open(p, 'w').write(t)
        lines = [l.strip() for l in t.splitlines() if l.strip() and not l.strip().startswith(('//', 'dcl', 'def', 'ps_', 'vs_'))]
        tex = sorted(set(re.findall(r'\bs\d+\b', ' '.join(l for l in lines if l.startswith('texld')))))
        print('entry %05x slots %s hash %016x %s instr %3d tex %s' % (o, slots, h, t.split()[0] if t else '?', len(lines), ' '.join(tex)))


if __name__ == '__main__':
    main(sys.argv[1:])
