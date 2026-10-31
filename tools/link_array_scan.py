"""Find the state-machine "link arrays" ({id, group, function} records, the per-agent condition / activity tables that
override the global default handlers) in an Xbox 360 image or in the PC tru.exe, and compare them (read-only;
finding 43, rock vein conditions 607 / 608).

A record is three 32-bit words {id < 0x10000, group < 0x10000 (multiple of 100 or 0), code pointer}. Runs of >= MIN
consecutive records are printed as one table (start address, record count, ids).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/link_array_scan.py xbox DUMP [--min N] [--id ID[,ID..]]
  ../bin/pyt -t 300 tools/link_array_scan.py pc TRU_EXE [--min N] [--id ID[,ID..]]
  --id   only print tables that contain one of these ids (and mark the records)
  --full print every record of the printed tables (id, group, function)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

XBASE = 0x82000000


def scan_words(words, va0, is_code, minimum):
    """words: list of u32; returns [(start_va, [(id, group, func), ...])]"""
    out = []
    n = len(words)
    for phase in range(3):
        i = phase
        while i + 2 < n:
            run = []
            j = i
            while j + 2 < n:
                a, g, f = words[j], words[j + 1], words[j + 2]
                if a < 0x10000 and g < 0x10000 and (g % 100 == 0) and is_code(f):
                    run.append((a, g, f)); j += 3
                else:
                    break
            if len(run) >= minimum:
                out.append((va0 + 4 * i, run)); i = j
            else:
                i += 3
    out.sort()
    return out


def main(argv):
    minimum = 3; ids = None; full = '--full' in argv
    if '--full' in argv: argv.remove('--full')
    if '--min' in argv: k = argv.index('--min'); minimum = int(argv[k + 1]); del argv[k:k + 2]
    if '--id' in argv: k = argv.index('--id'); ids = set(int(x, 0) for x in argv[k + 1].split(',')); del argv[k:k + 2]
    mode, path = argv[0], argv[1]
    blob = open(path, 'rb').read()
    tables = []
    if mode == 'xbox':
        import xbox_image_sections as XS
        secs = XS.sections(blob, XBASE)
        code = [(s[1], s[1] + s[2]) for s in secs if s[3] & 0x20]
        is_code = lambda f: any(lo <= f < hi for lo, hi in code)
        for s in secs:
            if s[3] & 0x20: continue
            o = s[1] - XBASE; sz = s[2] & ~3
            if o < 0 or o + sz > len(blob): continue
            words = list(struct.unpack_from('>%dI' % (sz // 4), blob, o))
            tables += scan_words(words, s[1], is_code, minimum)
    else:
        base, secs = PE.sections(blob)
        code = [(va, va + size) for name, va, rptr, size, ch in secs if ch & 0x20000000]
        is_code = lambda f: any(lo <= f < hi for lo, hi in code)
        for name, va, rptr, size, ch in secs:
            if ch & 0x20000000: continue
            sz = size & ~3
            words = list(struct.unpack_from('<%dI' % (sz // 4), blob, rptr))
            tables += scan_words(words, va, is_code, minimum)
    for va, run in tables:
        if ids and not any(r[0] in ids for r in run): continue
        print('table 0x%08x  %3d records  ids %s' % (va, len(run), ','.join(str(r[0]) for r in run)[:400]))
        if full or ids:
            for k, r in enumerate(run):
                if full or (ids and r[0] in ids):
                    print('    0x%08x  id %5d group %5d func 0x%08x' % (va + 12 * k, r[0], r[1], r[2]))


if __name__ == '__main__':
    main(sys.argv[1:])
