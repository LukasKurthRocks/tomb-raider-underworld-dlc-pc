"""List the UI text element records of PC script sections (read-only): `ffffffff|00ffffff 0 colour colour | id w1 w2 w3`
with the word after the record's first flag (w2) - Crystal's PC records carry 0x00010000 there where the Xbox has 0
(finding 43: the DLC loading-screen title in the ported title-update script 6 kept the Xbox 0 and is drawn
invisibly). Prints offset, both colours, string id, w1..w3; with two files, the records of each and a count of w2
values per file.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/script_text_records.py FILE.drm:SCRIPT_ID|all [FILE.drm:SCRIPT_ID ...]
  all: one line per script whose records carry w2 = 0
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def records(d):
    out = []
    for o in range(0, len(d) - 31, 4):
        a, b, c1, c2, sid, w1, w2, w3 = struct.unpack_from('<8I', d, o)
        if a in (0xffffffff, 0x00ffffff) and b == 0 and c1 >> 24 in (0, 0xff) and c2 >> 24 == 0xff and c1 != 0:
            out.append((o, c1, c2, sid, w1, w2, w3))
    return out


def main(argv):
    for spec in argv:
        path, sid = spec.rsplit(':', 1)
        secs = [x for x in DW.read(open(path, 'rb').read(), 'le').sections if x.type == 8]
        if sid == 'all':      # summary over every script: only scripts whose records carry w2 = 0
            for s in secs:
                rs = records(s.data); zero = [r for r in rs if r[5] == 0]
                if zero:
                    print('%s script %d: %d records, w2 = 0 in %d: %s' % (os.path.basename(path), s.id, len(rs), len(zero),
                          ', '.join('+%05x id %d' % (r[0], r[3]) for r in zero[:6])))
            continue
        s = next(x for x in secs if x.id == int(sid))
        rs = records(s.data)
        print('== %s script %s: %d records, w2 values %s' % (os.path.basename(path), sid, len(rs),
                                                             dict(collections.Counter('%08x' % r[5] for r in rs))))
        for o, c1, c2, i, w1, w2, w3 in rs:
            print('  +%05x  colours %08x %08x  id %5d (%08x)  w1 %08x  w2 %08x  w3 %08x' % (o, c1, c2, i & 0xffff if i < 0x10000 else i, i, w1, w2, w3))


if __name__ == '__main__':
    main(sys.argv[1:])
