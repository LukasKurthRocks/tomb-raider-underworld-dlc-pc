"""Who reads / writes given fields of an object reached through a global pointer (read-only; 2026-11-04, TU states
1019 / 1020, docs Befund-Schattenkampf-0411b.md).

State 1019 (TU 0x8245f420 / 0x8245f540) keeps its target as a handle {object, id} in the TU meter object, which hangs
at gameTracker+0x508 (gameTracker = [0x829892b0]). Before the translation keeps that handle inside TruShadowCombat
(the TU meter is TruShadowPower's), every other user of meter +0x20 / +0x24 must be known. This scan, linear over the
code range like tools/ppc_list_index_users.py (function start = `mflr r12`, conservative):

  * marks registers loaded from GLOBAL (`lis rH, hi` + `lwz rD, lo(rH)`) as "object 1" (the game tracker),
  * marks `lwz rD, DISP(object-1 register)` as "object 2" (the meter); `mr` copies a mark,
  * reports every D-form load / store / addi / addic with an object-2 base register and a displacement in FIELDS,
  * reports every `bl` while r3 holds object 2 (a call with the meter as first argument); with --callees the
    called functions are scanned a second time with r3 (and `mr rN, r3` copies) marked as object 2 from their start.
A mark is dropped when the register is written again, at blr and at the next function start. Indexed forms (lwzx /
lvx128) are not followed - their index register would need the `li` tracking of tools/ppc_field_writes.py.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/ppc_ptr_field_users.py IMAGE GLOBAL DISP FIELD[,FIELD..] [--callees]
  e.g. ../bin/pyt -t 600 tools/ppc_ptr_field_users.py work/xenia_dump/tu_image_82000000.bin 0x829892b0 0x508 0x20,0x24 --callees
Only addresses and decoded instruction kinds are printed - no game bytes.
"""
import sys, struct

BASE = 0x82000000
TEXT_START, TEXT_END = 0x82080000, 0x82700000
DFORM = {32: 'lwz', 33: 'lwzu', 34: 'lbz', 35: 'lbzu', 36: 'stw', 37: 'stwu', 38: 'stb', 39: 'stbu', 40: 'lhz',
         41: 'lhzu', 42: 'lha', 43: 'lhau', 44: 'sth', 45: 'sthu', 48: 'lfs', 49: 'lfsu', 50: 'lfd', 51: 'lfdu',
         52: 'stfs', 53: 'stfsu', 54: 'stfd', 55: 'stfdu', 14: 'addi', 13: 'addic.', 12: 'addic'}
# instructions whose rD field (bits 21..25) is a GPR result
GPR_RESULT = {7, 8, 10, 11, 12, 13, 14, 15, 20, 21, 23, 24, 25, 28, 29, 32, 33, 34, 35, 40, 41, 42, 43}
STORE_OPS = {36, 37, 38, 39, 44, 45, 52, 53, 54, 55, 47}


def scan_range(d, start, end, glob, disp, fields, entry_r3=False, stop_at_blr=True):
    hi_want, lo_want = (glob + 0x8000) >> 16 & 0xffff, glob & 0xffff
    lis, obj1, obj2 = {}, set(), set()
    if entry_r3:
        obj2.add(3)
    func = start
    hits, calls = [], []
    for o in range(start - BASE, min(end - BASE, len(d)), 4):
        w = struct.unpack_from('>I', d, o)[0]
        a = o + BASE
        if w == 0x7d8802a6 and a != start:          # next function
            if entry_r3:
                break
            func = a
            lis.clear(); obj1.clear(); obj2.clear()
        op = w >> 26
        rd, ra = (w >> 21) & 31, (w >> 16) & 31
        imm = w & 0xffff
        simm = imm - 0x10000 if imm & 0x8000 else imm
        if op == 15 and ra == 0:                    # lis
            lis[rd] = imm; obj1.discard(rd); obj2.discard(rd); continue
        if op == 18 and (w & 1):                    # bl
            if 3 in obj2:
                tgt = (a + ((w & 0x03fffffc) - (0x04000000 if w & 0x02000000 else 0))) & 0xffffffff
                calls.append((func, a, tgt))
            for r in (0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12):   # volatile registers are gone after a call
                obj1.discard(r); obj2.discard(r); lis.pop(r, None)
            continue
        if op == 31 and ((w >> 1) & 0x3ff) == 444 and ((w >> 21) & 31) == ((w >> 11) & 31):   # mr ra, rs
            rs = (w >> 21) & 31
            obj1.discard(ra); obj2.discard(ra); lis.pop(ra, None)
            if rs in obj1: obj1.add(ra)
            if rs in obj2: obj2.add(ra)
            continue
        if op == 32 and ra in lis and lis[ra] == hi_want and imm == lo_want:
            obj1.add(rd); obj2.discard(rd); lis.pop(rd, None); continue
        if op == 32 and ra in obj1 and simm == disp:
            obj2.add(rd); obj1.discard(rd); lis.pop(rd, None); continue
        if op in DFORM and ra in obj2 and simm in fields:
            kind = 'store' if op in STORE_OPS else ('address' if op in (12, 13, 14) else 'load')
            hits.append((func, a, '%s r%d, 0x%x(object 2 in r%d)' % (DFORM[op], rd, simm, ra), kind))
        if w == 0x4e800020 and stop_at_blr and not entry_r3:
            lis.clear(); obj1.clear(); obj2.clear(); continue
        if op in GPR_RESULT and op not in STORE_OPS:
            obj1.discard(rd); obj2.discard(rd); lis.pop(rd, None)
        elif op == 31:
            xo = (w >> 1) & 0x3ff
            if xo in (24, 28, 316, 444, 536, 792, 824, 954, 922, 986):   # logical / shift: result in ra
                obj1.discard(ra); obj2.discard(ra); lis.pop(ra, None)
            elif xo not in (151, 215, 407, 663, 695, 727, 759, 983, 0, 32):   # not a store / compare: result in rd
                obj1.discard(rd); obj2.discard(rd); lis.pop(rd, None)
    return hits, calls


def main(argv):
    callees = '--callees' in argv
    argv = [x for x in argv if x != '--callees']
    if len(argv) != 4:
        print(__doc__); return 2
    d = open(argv[0], 'rb').read()
    glob, disp = int(argv[1], 16), int(argv[2], 16)
    fields = set(int(x, 16) for x in argv[3].split(','))
    hits, calls = scan_range(d, TEXT_START, TEXT_END, glob, disp, fields)
    print('direct uses of [0x%08x] -> +0x%x -> fields %s: %d' % (glob, disp, ','.join('0x%x' % f for f in sorted(fields)), len(hits)))
    for func, a, text, kind in hits:
        print('  func 0x%08x  0x%08x  %-7s %s' % (func, a, kind, text))
    targets = sorted(set(t for _, _, t in calls))
    print('calls with object 2 in r3: %d sites, %d targets' % (len(calls), len(targets)))
    for func, a, t in calls:
        print('  func 0x%08x  0x%08x  bl 0x%08x' % (func, a, t))
    if callees:
        print('fields used inside those targets (r3 = object 2 at entry, up to the next function start):')
        n = 0
        for t in targets:
            h, _ = scan_range(d, t, TEXT_END, 0, 0, fields, entry_r3=True)
            for func, a, text, kind in h:
                print('  target 0x%08x  0x%08x  %-7s %s' % (t, a, kind, text))
                n += 1
        print('  %d uses' % n)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
