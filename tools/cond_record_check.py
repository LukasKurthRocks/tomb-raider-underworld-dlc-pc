"""Check the condition records of a converted PC state chart against the Xbox original (read-only; finding 43, rock
vein - doppelganger_casual.drm DTP 20212).

State-chart condition records are 16 bytes on both platforms, as in the PC base player (lara.drm DTP 850, e.g.
+0x700e0: u16 610, u16 610, u16 618, u16 0, 8 bytes): u16 id, u16 id (group / handler id), u16 value, u16 flags
(bit 0 negates), then a 4-byte value (float / int) and 4 bytes. PC tru+0x382816 / +0x382819 read id (+0) and value
(+4) as u16; the flag test reads +6. A record is located by its first word (both u16 equal, in 100..3000); the tool
compares the next three words with the correct per-field conversion (u16, u16, u32, u32).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/cond_record_check.py XBOX.drm PC.drm SECTION_ID [--show N] [--value V[,V..]]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def section(path, e, sid):
    D = DW.read(open(path, 'rb').read(), e)
    for s in D.sections:
        if s.id == sid and s.type == 7: return bytes(s.data)
    raise SystemExit('DTP %d not in %s' % (sid, path))


def main(argv):
    show = 10; vals = None
    if '--show' in argv: k = argv.index('--show'); show = int(argv[k + 1]); del argv[k:k + 2]
    if '--value' in argv: k = argv.index('--value'); vals = set(int(v) for v in argv[k + 1].split(',')); del argv[k:k + 2]
    xs = section(argv[0], 'be', int(argv[2])); ps = section(argv[1], 'le', int(argv[2]))
    n = min(len(xs), len(ps))
    ok = bad = 0; byid = collections.Counter(); badid = collections.Counter(); shown = 0
    for o in range(0, n - 16, 4):
        a, b = struct.unpack_from('>HH', xs, o)
        if a != b or not 100 <= a <= 3000: continue
        val, fl = struct.unpack_from('>HH', xs, o + 4)
        if vals and val not in vals: continue
        if not (0 < val < 0x1000 or val == 0): continue
        want = struct.pack('<HH', val, fl)
        got = ps[o + 4:o + 8]
        byid[a] += 1
        if got == want and ps[o:o + 4] == struct.pack('<HH', a, b):
            ok += 1
        else:
            bad += 1; badid[a] += 1
            if shown < show:
                g = struct.unpack('<HH', got)
                print('  +0x%05x  record %d/%d value %d flags %d  -> PC reads value %d flags %d' % (o, a, b, val, fl, g[0], g[1]))
                shown += 1
    print('records (Xbox id == group id, 100..3000): %d correct, %d wrong' % (ok, bad))
    print('wrong by id: ' + ', '.join('%d:%d/%d' % (i, badid[i], byid[i]) for i in sorted(badid)))


if __name__ == '__main__':
    main(sys.argv[1:])
