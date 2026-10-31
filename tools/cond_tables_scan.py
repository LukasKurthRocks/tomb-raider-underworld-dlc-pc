"""Find every state-machine condition table {id, group, function} in the Xbox TU / retail images and in the PC
tru.exe, and list the condition ids the title update (TU) has that the PC does not (read-only; TU coverage audit,
DLC 2 rock vein).

Background: the generic condition table (TU 0x82755f78 / PC 0x8b57e0, docs Befund-Felsrinne.md) maps most ids to
SCCondFunction_Default. The real tests (PSCCF_* / SCCondTest_* wrappers) sit in further {id, group, function}
tables, e.g. TU 0x8277f4d8: {611, 600, 0x82468ef8 -> SCCondTest_MarkupType}. A condition id that is missing from
those tables on PC is never dispatched to its test function, whatever the test function itself handles.

A table is a run of at least --min consecutive 12-byte records with 0 < id, group < 10000, group a multiple of 5 and
a function inside a code section. Xbox: big-endian image dumped from Xenia (guest base 0x82000000). PC: the PE file,
little-endian. Runs are printed with start, count and id range; then per TU run the ids that are new against retail
and the TU ids no PC run contains at all (with the TU group and handler).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/cond_tables_scan.py TU_DUMP RETAIL_DUMP TRU_EXE [--min 4] [--ids 607,608,...]
  --ids   also print, for these ids, every record found (all three binaries)
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xbox_image_sections as XS
import pe_callers as PE


def runs(blob, va0, E, code, minrun):
    """[(start_va, [(id, group, func)])] for every run of plausible records, scanned at 4-byte alignment"""
    n = len(blob) // 4
    w = struct.unpack_from(E + '%dI' % n, blob[:n * 4])
    ok = lambda i: (i + 2 < n and 0 < w[i] < 10000 and 0 < w[i + 1] < 10000 and w[i + 1] % 5 == 0
                    and any(a <= w[i + 2] < b for a, b in code))
    out, i = [], 0
    while i < n:
        j = i
        while ok(j): j += 3
        if (j - i) // 3 >= minrun:
            out.append((va0 + i * 4, [w[k:k + 3] for k in range(i, j, 3)])); i = j
        else:
            i += 1
    return out


def xbox(path, minrun):
    d = open(path, 'rb').read()
    secs = XS.sections(d)
    code = [(s, s + z) for _, s, z, ch in secs if ch & 0x20]
    out = []
    for name, s, z, ch in secs:
        if ch & 0x20: continue
        out += runs(d[s - 0x82000000:s - 0x82000000 + z], s, '>', code, minrun)
    return out


def pc(path, minrun):
    pe = open(path, 'rb').read()
    base, secs = PE.sections(pe)
    code = [(va, va + size) for _, va, _, size, ch in secs if ch & 0x20000000]
    out = []
    for name, va, rptr, size, ch in secs:
        if ch & 0x20000000: continue
        out += runs(pe[rptr:rptr + size], va, '<', code, minrun)
    return out


def main(argv):
    minrun = 4
    ids = set()
    if '--min' in argv: k = argv.index('--min'); minrun = int(argv[k + 1]); del argv[k:k + 2]
    if '--ids' in argv: k = argv.index('--ids'); ids = {int(x) for x in argv[k + 1].split(',')}; del argv[k:k + 2]
    if len(argv) != 3: sys.exit(__doc__)
    T, R, P = xbox(argv[0], minrun), xbox(argv[1], minrun), pc(argv[2], minrun)
    for label, tabs in (('TU', T), ('retail', R), ('PC', P)):
        print('%s: %d tables' % (label, len(tabs)))
        for s, recs in tabs:
            print('  0x%08x  %4d records  ids %d..%d  groups %s' % (
                s, len(recs), min(r[0] for r in recs), max(r[0] for r in recs),
                sorted({r[1] for r in recs})[:12]))
    rt_ids = {r[0] for _, recs in R for r in recs}
    pc_ids = {r[0] for _, recs in P for r in recs}
    print('TU ids missing on PC (in no PC table), per TU table; "new" = also missing in retail:')
    for s, recs in T:
        miss = [(r[0], r[1], r[2], r[0] not in rt_ids) for r in recs if r[0] not in pc_ids]
        if miss:
            print('  table 0x%08x: %s' % (s, ' '.join('%d/g%d->0x%08x%s' % (i, g, f, ' new' if n else '')
                                                     for i, g, f, n in miss)))
    if ids:
        print('records of the requested ids:')
        for label, tabs, fmt in (('TU', T, '0x%08x'), ('retail', R, '0x%08x'), ('PC', P, 'tru+0x%x')):
            for s, recs in tabs:
                for r in recs:
                    if r[0] in ids:
                        f = r[2] - 0x400000 if label == 'PC' else r[2]
                        print('  %-6s table 0x%08x  id %d group %d -> %s' % (label, s, r[0], r[1], fmt % f))


if __name__ == '__main__':
    main(sys.argv[1:])
