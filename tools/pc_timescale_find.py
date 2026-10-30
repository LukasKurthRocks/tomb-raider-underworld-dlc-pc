"""PC tru.exe time-scale globals and their callers (read-only; finding 43, shadow power, option C).

Background: on the Xbox (retail and title update) the engine keeps two time-scale ramps 0x20 apart (player at +0x00,
world at +0x20; TU guest 0x827754ac / 0x827754cc, retail 0x8277523c / 0x8277525c); the TU's shadow power drives them
to 1.2 (Lara) / 0.3 (world). The PC exe has the same engine code: ramps of 16 bytes {target, duration, start value,
start time} evaluated each frame by tru+0x38c4e0, set by tru+0x38c160. This tool lists, for given code addresses,
every x86 `call rel32` (E8) and `jmp rel32` (E9) that targets them, plus every absolute dword reference (4-byte
little-endian occurrence) to given data addresses in .text.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pc_timescale_find.py TRU_EXE [--calls ADDR,..] [--refs ADDR,..]
  default: --calls 0x776030,0x776090,0x78c160 --refs 0x8abe94,0x8abeb4,0xe7f1a0,0xe7f1d4
"""
import sys, struct


def text_section(d):
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    n = struct.unpack_from('<H', d, pe + 6)[0]
    opt = struct.unpack_from('<H', d, pe + 20)[0]
    base = struct.unpack_from('<I', d, pe + 24 + 28)[0]
    for i in range(n):
        o = pe + 24 + opt + 40 * i
        if d[o:o + 8].rstrip(b'\0') == b'.text':
            vsize, va, rsize, raw = struct.unpack_from('<IIII', d, o + 8)
            return base + va, d[raw:raw + rsize]
    raise SystemExit('no .text')


def main(argv):
    calls = [0x776030, 0x776090, 0x78c160]
    refs = [0x8abe94, 0x8abeb4, 0xe7f1a0, 0xe7f1d4]
    if '--calls' in argv:
        k = argv.index('--calls'); calls = [int(x, 0) for x in argv[k + 1].split(',')]; del argv[k:k + 2]
    if '--refs' in argv:
        k = argv.index('--refs'); refs = [int(x, 0) for x in argv[k + 1].split(',')]; del argv[k:k + 2]
    d = open(argv[0], 'rb').read()
    va, code = text_section(d)
    want = set(calls)
    hits = {c: [] for c in calls}
    for i in range(len(code) - 5):
        if code[i] in (0xe8, 0xe9):
            t = (va + i + 5 + struct.unpack_from('<i', code, i + 1)[0]) & 0xffffffff
            if t in want:
                hits[t].append(('call' if code[i] == 0xe8 else 'jmp', va + i))
    for c in calls:
        print('code 0x%08x: %d callers %s' % (c, len(hits[c]),
              ' '.join('%s@0x%08x' % (k, a) for k, a in hits[c][:60])))
    for r in refs:
        pat = struct.pack('<I', r); out = []
        j = code.find(pat)
        while j >= 0:
            out.append(va + j); j = code.find(pat, j + 1)
        print('data 0x%08x: %d references %s' % (r, len(out), ' '.join('0x%08x' % a for a in out[:60])))


if __name__ == '__main__':
    main(sys.argv[1:])
