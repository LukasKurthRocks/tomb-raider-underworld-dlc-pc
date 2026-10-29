"""Validate every pixel shader of the port's shader libraries in a mods-style folder offline (read-only): unique
shaders (md5) are disassembled (d3dcompiler_47) and reassembled with D3DX9 (shader_validate.assemble) - the same
rule set the GPU driver applied in upstream's native test (finding 43). Reports valid / rejected and the errors.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/shader_lib_check.py MODS_DIR [--all-libs]
  --all-libs: every shader library, not only the port's (2173, 2720-2783)
"""
import sys, os, hashlib, collections, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'native_test'))
import native_extract as NE
import shader_disasm as SD, shader_validate as SV


def main(argv):
    root = argv[0]; all_libs = '--all-libs' in argv
    seen = {}; res = collections.Counter(); errs = collections.Counter(); temps = collections.Counter()
    for dp, dn, fn in os.walk(root):
        for f in fn:
            if not f.lower().endswith('.drm'): continue
            raw = NE.cdrm_decode(open(os.path.join(dp, f), 'rb').read())
            for sid, data in NE.shader_sections(raw):
                if not all_libs and sid not in NE.NEW_LIBS: continue
                for slot, code in NE.lib_blobs(data):
                    if code[2:4] != b'\xff\xff': continue
                    md = hashlib.md5(code).hexdigest()
                    if md in seen: continue
                    ok, msg = SV.assemble(SD.disasm(code))
                    seen[md] = ok
                    res['valid' if ok else 'rejected'] += 1
                    if not ok:
                        for m in msg.split('\n'):
                            if 'error' in m: errs[re.sub(r'^.*?error', 'error', m.strip())[:150]] += 1
                        temps[len(set(re.findall(r'\br(\d+)\b', SD.disasm(code))))] += 1
    print('unique pixel shaders: %s' % dict(res))
    for k, n in errs.most_common(10): print('%5d  %s' % (n, k))
    if temps: print('temp registers used by the rejected ones: %s' % dict(sorted(temps.items())))


if __name__ == '__main__':
    main(sys.argv[1:])
