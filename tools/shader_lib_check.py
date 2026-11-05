"""Validate every pixel shader of the port's shader libraries in a mods-style folder offline (read-only): unique
shaders (md5) are disassembled (d3dcompiler_47) and reassembled with D3DX9 (shader_validate.assemble) - the same
rule set the GPU driver applied in upstream's native test (finding 43). Reports valid / rejected and the errors.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/shader_lib_check.py MODS_DIR [--all-libs] [--vs] [--list]
  --all-libs: every shader library, not only the port's (2173, 2720-2783)
  --vs: vertex shaders (vs_x_x) instead of pixel shaders (test 48d: lazily created shaders of the doppelganger)
  --list: print file / library / slot of every rejected shader
"""
import sys, os, hashlib, collections, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shader_libs as NE        # our copy of upstream's B138 native_extract helpers (native test v3 dropped them)
import shader_disasm as SD, shader_validate as SV


def main(argv):
    root = argv[0]; all_libs = '--all-libs' in argv; vs = '--vs' in argv; lst = '--list' in argv
    kind = b'\xfe\xff' if vs else b'\xff\xff'
    seen = {}; res = collections.Counter(); errs = collections.Counter(); temps = collections.Counter()
    for dp, dn, fn in os.walk(root):
        for f in fn:
            if not f.lower().endswith('.drm'): continue
            raw = NE.cdrm_decode(open(os.path.join(dp, f), 'rb').read())
            for sid, data in NE.shader_sections(raw):
                if not all_libs and sid not in NE.NEW_LIBS: continue
                for slot, code in NE.lib_blobs(data):
                    if code[2:4] != kind: continue
                    md = hashlib.md5(code).hexdigest()
                    if md in seen:
                        if lst and not seen[md]: print('rejected (same)  %s lib %d slot %d' % (f, sid, slot))
                        continue
                    ok, msg = SV.assemble(SD.disasm(code))
                    seen[md] = ok
                    if lst and not ok:
                        e = [m.strip() for m in msg.split('\n') if 'error' in m]
                        print('rejected  %s lib %d slot %d  %d bytes  %s' % (f, sid, slot, len(code), e[0][:160] if e else msg[:160]))
                    res['valid' if ok else 'rejected'] += 1
                    if not ok:
                        for m in msg.split('\n'):
                            if 'error' in m: errs[re.sub(r'^.*?error', 'error', m.strip())[:150]] += 1
                        temps[len(set(re.findall(r'\br(\d+)\b', SD.disasm(code))))] += 1
    print('unique %s shaders: %s' % ('vertex' if vs else 'pixel', dict(res)))
    for k, n in errs.most_common(10): print('%5d  %s' % (n, k))
    if temps: print('temp registers used by the rejected ones: %s' % dict(sorted(temps.items())))


if __name__ == '__main__':
    main(sys.argv[1:])
