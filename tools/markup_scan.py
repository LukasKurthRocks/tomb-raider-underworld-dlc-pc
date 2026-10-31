"""Find the markup record arrays of a DRM and list their type chars (read-only; finding 43, DLC 2 rock vein).

The PC markup loader tru+0x1ce4f0 (records, count, mask, owner) walks 0x5c-byte records: +0x28 a runtime field
(0 in the file; when 0 the type is taken from +0x33), +0x2e the markup id (s16), +0x33 the markup type char (mapped
through the owner's vtable +0x1c / +0x20; a negative result prints "Bad Markup Type, disabling markup"), +0x58 a
pointer to the segment data (may be null). Its two callers pass a (count, pointer) pair that sits as two adjacent
dwords: a unit's markup list (count +0x08, records +0x0c, tru+0x5d21b4) and an object's markup (count +0x54,
records +0x58, tru+0x5d0656). So an array is: an internal relocation whose preceding dword is a plausible count
and whose target holds count x 0x5c bytes of records with +0x28 == 0 and a printable / small type char.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/markup_scan.py FILE.drm [FILE2.drm ...] [--be] [--list]
  --be    the files are big-endian (Xbox) DRMs (decoded, e.g. work/rockvein/dlc_level2_start_xbox.drm)
  --list  print every record (section, array, index, id, type char, segment pointer yes/no)
Output: per file the arrays found and the record count per type char.
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

STRIDE = 0x5c


def arrays(data, internal, f):
    """[(count_offset, records_offset, count)] for every (count, pointer) pair that looks like a markup array"""
    out = []
    for o, t in internal:
        if o < 4:
            continue
        n = struct.unpack_from(f + 'I', data, o - 4)[0]
        if not 1 <= n <= 4000 or t + n * STRIDE > len(data):
            continue
        good = 0
        for i in range(n):
            r = t + i * STRIDE
            if struct.unpack_from(f + "I", data, r + 0x28)[0] == 0 and data[r + 0x33] != 0 and struct.unpack_from(f + "h", data, r + 0x2e)[0] >= 0:
                good += 1
        if good >= max(1, int(0.9 * n)):
            out.append((o - 4, t, n))
    return out


def main(argv):
    be = '--be' in argv; lst = '--list' in argv
    argv = [a for a in argv if a not in ('--be', '--list')]
    e = 'be' if be else 'le'; f = '>' if be else '<'
    for path in argv:
        D = DW.read(open(path, 'rb').read(), e)
        hist = collections.Counter(); total = 0
        for s in D.sections:
            if not s.reloc:
                continue
            ra = R.parse(s.reloc, e)
            ptrs = dict(ra.internal)
            for co, ro, n in arrays(s.data, ra.internal, f):
                print('array type %d id %d count@+0x%05x records@+0x%05x x%d' % (s.type, s.id, co, ro, n))
                for i in range(n):
                    r = ro + i * STRIDE
                    mid = struct.unpack_from(f + 'h', s.data, r + 0x2e)[0]
                    tch = s.data[r + 0x33]
                    hist[tch] += 1; total += 1
                    if lst:
                        print('   [%3d] id %5d type %3d %r seg %s' % (i, mid, tch, chr(tch) if 32 <= tch < 127 else '?',
                                                                    'yes' if (r + 0x58) in ptrs else 'no'))
        print('== %s: %d records' % (os.path.basename(path), total))
        for ch, c in sorted(hist.items()):
            print('   type %3d %r  %4d' % (ch, chr(ch) if 32 <= ch < 127 else '?', c))


if __name__ == '__main__':
    main(sys.argv[1:])
