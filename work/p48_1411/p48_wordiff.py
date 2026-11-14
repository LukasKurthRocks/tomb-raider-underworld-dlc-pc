"""P4.8 / P4.9 (2026-11-14): word differences of two PC DRMs (decoded; sections paired by index, same type / id
required), plus the md5 of both files. Read-only.
Usage: ../bin/pyt -t 600 work/p48_1411/p48_wordiff.py A.drm B.drm [--max N]"""
import sys, os, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW
argv = sys.argv[1:]
mx = 60
if '--max' in argv:
    i = argv.index('--max'); mx = int(argv[i + 1]); del argv[i:i + 2]
a, b = argv
ra, rb = open(a, 'rb').read(), open(b, 'rb').read()
print('md5 %s %s' % (hashlib.md5(ra).hexdigest(), a))
print('md5 %s %s' % (hashlib.md5(rb).hexdigest(), b))
A, B = DW.read(ra, 'le'), DW.read(rb, 'le')
if len(A.sections) != len(B.sections): print('section count differs %d %d' % (len(A.sections), len(B.sections)))
n = 0
for k, (s, t) in enumerate(zip(A.sections, B.sections)):
    if (s.type, s.id) != (t.type, t.id): print('section %d: type/id differ %s %s' % (k, (s.type, s.id), (t.type, t.id))); continue
    if s.reloc != t.reloc: print('section %d (type %d id %d): reloc differs' % (k, s.type, s.id))
    if len(s.data) != len(t.data): print('section %d: size differs' % k); continue
    for o in range(0, len(s.data) // 4 * 4, 4):
        if s.data[o:o + 4] != t.data[o:o + 4]:
            n += 1
            if n <= mx: print('  type %d id %6d +0x%05x %s -> %s' % (s.type, s.id, o, bytes(s.data[o:o + 4]).hex(), bytes(t.data[o:o + 4]).hex()))
print('differing words: %d' % n)
