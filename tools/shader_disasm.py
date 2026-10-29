"""Disassemble Direct3D 9 shader binaries (ps_3_0 / vs_3_0 token streams) to text with Windows' d3dcompiler_47.dll
(D3DDisassemble) - read-only, for comparing shaders the GPU driver rejects with ones it accepts (DLC 2 test 13).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/shader_disasm.py SHADER.bin [...] [--out DIR]
  without --out the text goes to stdout; with --out each file becomes DIR/<name>.asm
"""
import sys, os, ctypes


def disasm(b):
    lib = ctypes.WinDLL('d3dcompiler_47.dll')
    blob = ctypes.c_void_p()
    hr = lib.D3DDisassemble(ctypes.c_char_p(b), ctypes.c_size_t(len(b)), ctypes.c_uint(0), None, ctypes.byref(blob))
    if hr != 0: return 'D3DDisassemble failed: 0x%08x' % (hr & 0xffffffff)
    vt = ctypes.cast(blob, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    get_ptr = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)(vt[3])
    get_size = ctypes.WINFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p)(vt[4])
    release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt[2])
    text = ctypes.string_at(get_ptr(blob), get_size(blob)).decode('ascii', 'replace').rstrip('\0')
    release(blob)
    return text


def main(argv):
    out = None
    if '--out' in argv: k = argv.index('--out'); out = argv[k + 1]; del argv[k:k + 2]
    for p in argv:
        t = disasm(open(p, 'rb').read())
        if out:
            os.makedirs(out, exist_ok=True)
            open(os.path.join(out, os.path.basename(p) + '.asm'), 'w').write(t)
        else:
            print('==== %s\n%s' % (p, t))


if __name__ == '__main__':
    main(sys.argv[1:])
