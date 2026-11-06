"""Offline check of TruMenu's flat-view palette pixel shaders (read-only; 2026-11-06 TruMenu 0.15 render mode, stage R1).

TruMenu 0.15 builds 34 tiny D3D9 pixel shaders at run time without a compiler (RmShadersCreate in
src/asi/TruMenu/TruMenu.cpp): for each of the 17 colours of kRmPalette and each version of kRmPsVersion (ps_2_0,
ps_3_0) the token stream
    version, def c0 = (r, g, b, 1.0), mov oC0, c0, end
from the constants kRmPsDef / kRmPsDefDst / kRmPsMov / kRmPsMovDst / kRmPsMovSrc / kRmPsEnd. This tool reads those
constants and the palette from the source, builds the same 34 streams and hands each to D3DDisassemble of the Windows
d3dcompiler_47.dll (System32, the HLSL compiler library - nothing is installed or written). A stream passes when the
disassembly is exactly the expected program (version line, "def c0, r, g, b, 1", "mov oC0, c0"). As a cross-check it
also compiles the HLSL "float4 main() : COLOR { return float4(r, g, b, 1); }" for ps_2_0 and ps_3_0 with D3DCompile and
prints that disassembly; the compiler's tokens without its comment block (constant table) must equal TruMenu's stream
for colour 0 (counted as a failure otherwise).

Usage (from the repository root):
  ../bin/pyt -t 60 tools/trumenu_flat_ps_check.py [--cpp FILE]
Exit 0 = all 34 streams disassemble to the expected program, 1 = a difference (listed), 2 = d3dcompiler not loadable.
"""
import ctypes, os, re, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CPP = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.cpp')


def const(src, name):
    m = re.search(r'\b%s = (0x[0-9a-fA-F]+)' % name, src)
    if not m: sys.exit('constant %s not found in TruMenu.cpp' % name)
    return int(m.group(1), 16)


def palette(src):
    block = src[src.index('const float kRmPalette[17][3] = {'):]
    block = block[:block.index('\n};')]
    rows = re.findall(r'\{([-0-9.]+)f, ([-0-9.]+)f, ([-0-9.]+)f\}', block)
    return [tuple(float(x) for x in r) for r in rows]


class Blob:
    """ID3DBlob through its vtable: 3 GetBufferPointer, 4 GetBufferSize, 2 Release"""
    def __init__(self, ptr):
        self.ptr = ptr
        vt = ctypes.cast(ctypes.cast(ptr, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
        proto = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)
        proto_size = ctypes.WINFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p)
        proto_rel = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
        self._get = proto(vt[3])
        self._size = proto_size(vt[4])
        self._rel = proto_rel(vt[2])

    def bytes(self):
        return ctypes.string_at(self._get(self.ptr), self._size(self.ptr))

    def release(self):
        self._rel(self.ptr)


def disassemble(lib, code):
    out = ctypes.c_void_p()
    hr = lib.D3DDisassemble(code, len(code), 0, None, ctypes.byref(out))
    if hr != 0 or not out.value: return None, hr & 0xffffffff
    b = Blob(out.value)
    text = b.bytes().decode('ascii', 'replace').rstrip('\0')
    b.release()
    return text, 0


def program(text):
    """the instruction lines of a disassembly (no comments / blank lines)"""
    return [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith('//')]


def fmt(v):
    s = ('%.6f' % v).rstrip('0').rstrip('.')
    return s if s not in ('', '-0') else '0'


def main(argv):
    cpp = argv[argv.index('--cpp') + 1] if '--cpp' in argv else CPP
    src = open(cpp, encoding='utf-8').read()
    m = re.search(r'kRmPsVersion\[2\] = \{(0x[0-9a-fA-F]+), (0x[0-9a-fA-F]+)\}', src)
    if not m: sys.exit('kRmPsVersion not found')
    versions = [int(m.group(1), 16), int(m.group(2), 16)]
    tok = {n: const(src, n) for n in ('kRmPsDef', 'kRmPsDefDst', 'kRmPsMov', 'kRmPsMovDst', 'kRmPsMovSrc', 'kRmPsEnd')}
    colours = palette(src)
    print('TruMenu.cpp: versions %s, def 0x%08x dst 0x%08x, mov 0x%08x dst 0x%08x src 0x%08x, end 0x%08x, %d colours'
          % (' '.join('0x%08x' % v for v in versions), tok['kRmPsDef'], tok['kRmPsDefDst'], tok['kRmPsMov'],
             tok['kRmPsMovDst'], tok['kRmPsMovSrc'], tok['kRmPsEnd'], len(colours)))
    if len(colours) != 17: print('FAIL: kRmPalette has %d rows, want 17' % len(colours)); return 1
    dll = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'd3dcompiler_47.dll')
    try:
        lib = ctypes.WinDLL(dll)
    except OSError as e:
        print('d3dcompiler_47.dll not loadable (%s): %s' % (dll, e))
        return 2
    lib.D3DDisassemble.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_char_p,
                                   ctypes.POINTER(ctypes.c_void_p)]
    lib.D3DDisassemble.restype = ctypes.c_long
    bad = 0
    for vi, version in enumerate(versions):
        name = 'ps_%d_%d' % ((version >> 8) & 0xff, version & 0xff)
        for ci, (r, g, b) in enumerate(colours):
            code = struct.pack('<11I', version, tok['kRmPsDef'], tok['kRmPsDefDst'],
                               *struct.unpack('<4I', struct.pack('<4f', r, g, b, 1.0)), tok['kRmPsMov'],
                               tok['kRmPsMovDst'], tok['kRmPsMovSrc'], tok['kRmPsEnd'])
            text, hr = disassemble(lib, code)
            want = [name, 'def c0, %s, %s, %s, 1' % (fmt(r), fmt(g), fmt(b)), 'mov oC0, c0']
            got = program(text) if text else ['D3DDisassemble failed 0x%08x' % hr]
            got = [re.sub(r'\s+', ' ', l) for l in got]
            # the disassembler prints the float32 values with 9 digits: compare the def numbers as numbers
            ok = len(got) == 3 and got[0] == want[0] and got[2] == want[2]
            if ok:
                m2 = re.fullmatch(r'def c0, ([-0-9.e]+), ([-0-9.e]+), ([-0-9.e]+), ([-0-9.e]+)', got[1])
                ok = bool(m2) and all(abs(float(m2.group(k + 1)) - v) < 1e-6 for k, v in enumerate((r, g, b, 1.0)))
            bad += not ok
            if not ok or ci in (0, 16):
                print('%s colour %2d: %s  %s' % (name, ci, 'ok  ' if ok else 'FAIL', ' | '.join(got)))
                if not ok: print('    want: %s' % ' | '.join(want))
    print('%d of %d palette shaders disassemble to the expected program' % (2 * len(colours) - bad, 2 * len(colours)))
    # cross-check: what the HLSL compiler emits for the same colour
    lib.D3DCompile.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p,
                               ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint,
                               ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
    lib.D3DCompile.restype = ctypes.c_long
    r, g, b = colours[0]
    hlsl = ('float4 main() : COLOR { return float4(%s, %s, %s, 1.0); }' % (fmt(r), fmt(g), fmt(b))).encode('ascii')
    for target in (b'ps_2_0', b'ps_3_0'):
        code, err = ctypes.c_void_p(), ctypes.c_void_p()
        hr = lib.D3DCompile(hlsl, len(hlsl), b'flat', None, None, b'main', target, 0, 0, ctypes.byref(code), ctypes.byref(err))
        if hr != 0 or not code.value:
            print('D3DCompile %s failed 0x%08x' % (target.decode(), hr & 0xffffffff))
            continue
        blob = Blob(code.value)
        data = blob.bytes()
        blob.release()
        text, _ = disassemble(lib, data)
        print('D3DCompile %s (%d bytes): %s' % (target.decode(), len(data), ' | '.join(program(text or ''))))
        # the compiler's tokens without its comment blocks (0xfffe, length in bits 16..30) vs TruMenu's stream
        words = list(struct.unpack('<%dI' % (len(data) // 4), data))
        plain, i = [], 0
        while i < len(words):
            if words[i] & 0xffff == 0xfffe and i > 0:
                i += 1 + ((words[i] >> 16) & 0x7fff)
                continue
            plain.append(words[i])
            i += 1
        version = versions[0 if target == b'ps_2_0' else 1]
        mine = [version, tok['kRmPsDef'], tok['kRmPsDefDst'], *struct.unpack('<4I', struct.pack('<4f', r, g, b, 1.0)),
                tok['kRmPsMov'], tok['kRmPsMovDst'], tok['kRmPsMovSrc'], tok['kRmPsEnd']]
        same = plain == mine
        bad += not same
        print('  tokens without comments %s TruMenu\'s stream: %s' % ('==' if same else '!=',
                                                                     ' '.join('%08x' % w for w in plain)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
