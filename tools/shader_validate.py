"""Name the reason a Direct3D 9 shader is rejected: reassemble its disassembly with D3DX9's assembler
(d3dx9_43.dll, D3DXAssembleShader), which applies the shader-model rules and reports errors with line numbers
(read-only; DLC 2 test 13: the driver rejected 272 of 396 port-generated pixel shaders with D3DERR_INVALIDCALL).

Input: .asm files from tools/shader_disasm.py (D3DDisassemble text). The report groups the error messages
(line numbers removed) and counts files per message; --show N prints N full messages with the offending line.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/shader_validate.py ASM_DIR [--only LIST.txt] [--show N]
  --only: a file with one shader name per line (e.g. the FAIL lines of native_report.txt)
"""
import sys, os, re, ctypes, collections


class Blob:
    def __init__(self, p):
        vt = ctypes.cast(p, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        self.p = p
        self.get_ptr = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)(vt[3])
        self.get_size = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt[4])
        self.release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt[2])

    def bytes(self):
        b = ctypes.string_at(self.get_ptr(self.p), self.get_size(self.p)); self.release(self.p); return b


def assemble(text):
    """-> (ok, error text)"""
    lib = ctypes.WinDLL('d3dx9_43.dll')
    src = text.encode('ascii', 'replace')
    shader, errs = ctypes.c_void_p(), ctypes.c_void_p()
    hr = lib.D3DXAssembleShader(ctypes.c_char_p(src), ctypes.c_uint(len(src)), None, None, ctypes.c_uint(0),
                                ctypes.byref(shader), ctypes.byref(errs))
    msg = Blob(errs).bytes().decode('ascii', 'replace').rstrip('\0') if errs.value else ''
    if shader.value: Blob(shader).bytes()
    return hr == 0, msg


def main(argv):
    show = 0; only = None
    if '--show' in argv: k = argv.index('--show'); show = int(argv[k + 1]); del argv[k:k + 2]
    if '--only' in argv:
        k = argv.index('--only'); only = {l.strip() for l in open(argv[k + 1]) if l.strip()}; del argv[k:k + 2]
    d = argv[0]
    groups = collections.Counter(); examples = collections.defaultdict(list); nok = nbad = 0
    for f in sorted(os.listdir(d)):
        if not f.endswith('.asm') or (only and f[:-4] not in only): continue
        text = open(os.path.join(d, f)).read()
        ok, msg = assemble(text)
        if ok and not msg.strip(): nok += 1; continue
        if ok: nok += 1
        else: nbad += 1
        lines = text.split('\n')
        seen = set()
        for m in msg.split('\n'):
            m = m.strip()
            if not m: continue
            key = re.sub(r'^.*?\(\d+(,\d+)?\):\s*', '', m)
            key = re.sub(r'\b[rcvs]\d+\b', 'REG', key)
            if key in seen: continue
            seen.add(key); groups[key] += 1
            if len(examples[key]) < show:
                ln = re.search(r'\((\d+)', m)
                src = lines[int(ln.group(1)) - 1].strip() if ln and int(ln.group(1)) <= len(lines) else ''
                examples[key].append('%s: %s | %s' % (f, m, src))
    print('assembled ok: %d, rejected: %d' % (nok, nbad))
    for k, n in groups.most_common(): print('%5d  %s' % (n, k[:160]))
    for k, ex in examples.items():
        for e in ex: print('   ', e[:300])


if __name__ == '__main__':
    main(sys.argv[1:])
