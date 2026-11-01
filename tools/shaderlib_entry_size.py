"""Does every ShaderLib entry's size field cover its bytecode the way the PC engine copies it? (read-only)
tru.exe +0x125900 (shader object init, called from the shader cache +0x1259d0 -> +0x124d00): with the copy flag set it
allocates `u16 [entry+4]` bytes, copies that many bytes from the ENTRY START ({u32 word0, u32 size, u64 hash, code})
and hands `copy + 0x10` to IDirect3DDevice9::CreatePixelShader / CreateVertexShader (+0x124d40 / +0x1299b0). So the
code must end (END token 0x0000FFFF included) within size - 16 bytes, and size must fit in a u16.
Test 48e (2026-10-31): CreatePixelShader returned D3DERR_INVALIDCALL for a doppelganger shader whose bytecode
validates offline.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/shaderlib_entry_size.py FILE_OR_DIR [...] [--all]
  per file: entries, how many have size - 16 < code length (truncated by the copy), size > 0xffff, and the size rule
  seen (size - 16 - code length); --all: one line per entry
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def code_len(code):
    """bytes up to and including the END token (D3D9 token walk), or None"""
    n = len(code) // 4
    if n < 2: return None
    w = struct.unpack_from('<%dI' % n, code, 0)
    i = 1
    while i < n:
        t = w[i]
        if t == 0x0000FFFF: return 4 * i + 4
        if t & 0xFFFF == 0xFFFE: i += 1 + (t >> 16); continue
        i += 1 + ((t >> 24) & 0xF)
    return None


def files(paths):
    for p in paths:
        if os.path.isdir(p):
            for n in sorted(os.listdir(p)):
                if n.lower().endswith('.drm'): yield os.path.join(p, n)
        else:
            yield p


def main(argv):
    every = '--all' in argv; argv = [a for a in argv if a != '--all']
    for path in files(argv):
        D = DW.read(open(path, 'rb').read(), 'le')
        rule = collections.Counter(); bad = []; n = 0
        for s in D.sections:
            if s.type != 9: continue
            d = s.data
            tb, = struct.unpack_from('<I', d, 4)
            slots = struct.unpack_from('<%dI' % (tb // 4), d, 12)
            offs = sorted(set(x for x in slots if x != 0xffffffff))
            for k, o in enumerate(offs):
                nxt = offs[k + 1] if k + 1 < len(offs) else len(d) - 4
                w0, size = struct.unpack_from('<II', d, 4 + o)
                code = d[4 + o + 16:4 + nxt]
                cl = code_len(code); n += 1
                kind = code[2:4].hex()
                if cl is None: bad.append((s.id, o, size, None, 'no END token', kind)); continue
                rule[size - 16 - cl] += 1
                why = []
                if size > 0xffff: why.append('size > u16')
                if (size & 0xffff) - 16 < cl: why.append('copy cuts %d bytes' % (cl - ((size & 0xffff) - 16)))
                if why: bad.append((s.id, o, size, cl, ' '.join(why), kind))
                if every:
                    print('  %s lib %d @%x size %d code %d %s %s' % (os.path.basename(path), s.id, o, size, cl, kind, ' '.join(why)))
        print('%s: %d entries, size - 16 - code length: %s, bad %d'
              % (os.path.basename(path), n, dict(sorted(rule.items())[:8]), len(bad)))
        for sid, o, size, cl, why, kind in bad[:40]:
            print('    lib %d entry @%x (%s) size %d code %s: %s' % (sid, o, 'ps' if kind == 'ffff' else 'vs' if kind == 'feff' else kind, size, cl, why))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
