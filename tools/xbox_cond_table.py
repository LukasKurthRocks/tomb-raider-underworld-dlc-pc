"""Diff the player state-machine condition table between two Xbox 360 memory images (read-only).

Finding 43 follow-up (DLC 2 rock vein): the table is an array of {id, group, function} big-endian triples; slots
without a handler point at SCCondFunction_Default. Given one image's default handler, the tool walks the table
outwards from the first slot that uses it and prints every (id, group) with its handler, then the differences.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/xbox_cond_table.py DUMP_A DEFAULT_A DUMP_B DEFAULT_B
  ../bin/pyt -t 300 tools/xbox_cond_table.py --dump DUMP DEFAULT     (list one table)
  ../bin/pyt -t 300 tools/xbox_cond_table.py --pairs DUMP_A START_A DUMP_B START_B   (activity table {id, func})
  ../bin/pyt -t 300 tools/xbox_cond_table.py --pc TRU_EXE COND_VA ACT_VA TU_DUMP TU_COND TU_ACT [PC_STATE TU_STATE]   (PC vs TU ids)
  ../bin/pyt -t 300 tools/xbox_cond_table.py --recs N DUMP_A START_A DUMP_B START_B   ({id, N-1 words} records)
  ../bin/pyt -t 300 tools/xbox_cond_table.py --pc-list TRU_EXE VA WORDS   (list one PC table: 3 = conditions, 2 = activities, 7 = states)
  DUMP_*: memory image with guest base 0x82000000 (work/xenia_dump/*.bin)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

BASE = 0x82000000


def is_rec(d, o):
    if o < 0 or o + 12 > len(d): return False
    i, g, f = struct.unpack_from('>3I', d, o)
    return i < 0x10000 and g < 0x10000 and 0x82000000 <= f < 0x83000000


def table(path, dflt):
    d = open(path, 'rb').read()
    pat = struct.pack('>I', dflt); first = d.find(pat)
    while first >= 0 and (first % 4 or not all(is_rec(d, first - 8 + 12 * k) for k in range(-2, 3))):
        first = d.find(pat, first + 1)              # skip lone pointers (vtables): need a run of records
    o = first - 8                                   # record = {id, group, func}
    while is_rec(d, o - 12): o -= 12
    recs = []
    while is_rec(d, o):
        recs.append((BASE + o,) + struct.unpack_from('>3I', d, o)); o += 12
        if recs[-1][1] == 0: break                  # the id-0 record closes the table (inserted too)
    return recs


def pairs(path, start):
    d = open(path, "rb").read(); o = start - BASE; out = []
    while True:
        i, f = struct.unpack_from(">2I", d, o)
        if i == 0: return out
        out.append((i, f)); o += 8


def pe_at(pe, va):
    for s in PE.sections(pe)[1]:
        if s[1] <= va < s[1] + s[3]: return s[2] + va - s[1]
    raise ValueError("VA 0x%x not in a section" % va)


def pc_ids(exe, va, size):
    """PC (little-endian) table: size 12 = condition {id, group, func}, 8 = activity {id, func}; ends at id 0."""
    pe = open(exe, "rb").read(); o = pe_at(pe, va); out = []
    while True:
        r = struct.unpack_from("<3I" if size == 12 else "<2I", pe, o)
        if r[0] == 0: return out
        out.append(r); o += size


def recs(path, start, n):
    d = open(path, "rb").read(); o = start - BASE; out = []
    while struct.unpack_from(">I", d, o)[0]:
        out.append(struct.unpack_from(">%dI" % n, d, o)); o += 4 * n
    return out


def main(argv):
    if argv[0] == "--pc-list":
        pe = open(argv[1], "rb").read(); va = int(argv[2], 0); n = int(argv[3]); o = pe_at(pe, va)
        while True:
            r = struct.unpack_from("<%dI" % n, pe, o)
            print("0x%08x  " % (va + o - pe_at(pe, va)) + " ".join("%d" % r[0] if k == 0 else "0x%08x" % w for k, w in enumerate(r)))
            if r[0] == 0: return
            o += 4 * n
    if argv[0] == "--recs":                        # --recs N DUMP_A START_A DUMP_B START_B: {id, N-1 words}, ends at id 0
        n = int(argv[1]); a, b = recs(argv[2], int(argv[3], 0), n), recs(argv[4], int(argv[5], 0), n)
        ia = set(r[0] for r in a)
        print("records A %d, B %d; only in B:" % (len(a), len(b)))
        for r in b:
            if r[0] not in ia: print("  " + " ".join("0x%08x" % w for w in r))
        return
    if argv[0] == "--pc":                          # --pc EXE COND_VA ACT_VA TU_DUMP TU_COND TU_ACT
        pc_c, pc_a = pc_ids(argv[1], int(argv[2], 0), 12), pc_ids(argv[1], int(argv[3], 0), 8)
        d = open(argv[4], "rb").read(); tu_c = []; o = int(argv[5], 0) - BASE
        while struct.unpack_from(">I", d, o)[0]: tu_c.append(struct.unpack_from(">3I", d, o)); o += 12
        tu_a = pairs(argv[4], int(argv[6], 0))
        sc, sa = set(r[0] for r in pc_c), set(r[0] for r in pc_a)
        print("PC conditions %d, activities %d; TU conditions %d, activities %d" % (len(pc_c), len(pc_a), len(tu_c), len(tu_a)))
        print("TU conditions missing on PC: " + " ".join("%d(group %d)" % (r[0], r[1]) for r in tu_c if r[0] not in sc))
        print("TU activities missing on PC: " + " ".join("%d->0x%08x" % r for r in tu_a if r[0] not in sa))
        print("PC conditions not in TU: " + " ".join(str(r[0]) for r in pc_c if r[0] not in set(x[0] for x in tu_c)))
        print("PC activities not in TU: " + " ".join(str(r[0]) for r in pc_a if r[0] not in set(x[0] for x in tu_a)))
        # handlers of the missing ids -> PC handler of the same function at a shared id (table pairs them by id)
        for name, tu, pc, fi in (("condition", tu_c, pc_c, 2), ("activity", tu_a, pc_a, 1)):
            pcid = dict((r[0], r[fi]) for r in pc)
            for f in sorted(set(r[fi] for r in tu if r[0] not in pcid)):
                shared = [r[0] for r in tu if r[fi] == f and r[0] in pcid]
                pcf = sorted(set(pcid[i] for i in shared))
                print("%s handler TU 0x%08x -> PC %s (via %d shared ids)" % (name, f, " ".join("0x%08x" % x for x in pcf)
                      or "none (TU-only function)", len(shared)))
        if len(argv) > 8:                          # ... PC_STATE_VA TU_STATE: {id, 6 funcs}
            pe = open(argv[1], "rb").read(); o = pe_at(pe, int(argv[7], 0)); pc_s = []
            while struct.unpack_from("<I", pe, o)[0]: pc_s.append(struct.unpack_from("<7I", pe, o)); o += 28
            tu_s = recs(argv[4], int(argv[8], 0), 7); ss = set(r[0] for r in pc_s)
            print("PC states %d, TU states %d; TU states missing on PC: %s" % (len(pc_s), len(tu_s),
                  " ".join(str(r[0]) for r in tu_s if r[0] not in ss)))
            pcid = dict((r[0], r[1:]) for r in pc_s)
            for f in sorted(set(w for r in tu_s if r[0] not in ss for w in r[1:])):
                pcf = sorted(set(pcid[r[0]][k] for r in tu_s if r[0] in pcid for k in range(6) if r[1 + k] == f))
                print("state handler TU 0x%08x -> PC %s" % (f, " ".join("0x%08x" % x for x in pcf) or "none"))
        return
    if argv[0] == "--pairs":                       # activity table {id, func}, ends at id 0
        a, b = pairs(argv[1], int(argv[2], 0)), pairs(argv[3], int(argv[4], 0))
        ia, ib = [x[0] for x in a], [x[0] for x in b]
        print("pairs A %d, B %d" % (len(a), len(b)))
        print("only in B: " + " ".join("%d->0x%08x" % x for x in b if x[0] not in ia))
        print("only in A: " + " ".join("%d->0x%08x" % x for x in a if x[0] not in ib))
        return
    if argv[0] == "--dump":
        for r in table(argv[1], int(argv[2], 0)): print("0x%08x  id %4d group %4d  0x%08x" % r)
        return
    ta, tb = table(argv[0], int(argv[1], 0)), table(argv[2], int(argv[3], 0))
    da, db = int(argv[1], 0), int(argv[3], 0)
    for name, t in (('A', ta), ('B', tb)):
        print('table %s: 0x%08x..0x%08x, %d records, %d default' % (name, t[0][0], t[-1][0] + 12, len(t),
              sum(1 for r in t if r[3] == (da if name == 'A' else db))))
    ma = {(r[1], r[2]): r for r in ta}; mb = {(r[1], r[2]): r for r in tb}
    print('only in B (id, group, handler):')
    for k in sorted(set(mb) - set(ma)):
        r = mb[k]; print('  id %4d group %4d  0x%08x%s' % (k[0], k[1], r[3], '  (default)' if r[3] == db else ''))
    print('only in A:')
    for k in sorted(set(ma) - set(mb)):
        r = ma[k]; print('  id %4d group %4d  0x%08x%s' % (k[0], k[1], r[3], '  (default)' if r[3] == da else ''))
    print('default in A, handled in B:')
    for k in sorted(set(ma) & set(mb)):
        if ma[k][3] == da and mb[k][3] != db: print('  id %4d group %4d  B 0x%08x' % (k[0], k[1], mb[k][3]))
    print('handled in A, default in B:')
    for k in sorted(set(ma) & set(mb)):
        if ma[k][3] != da and mb[k][3] == db: print('  id %4d group %4d  A 0x%08x' % (k[0], k[1], ma[k][3]))


if __name__ == '__main__':
    main(sys.argv[1:])
