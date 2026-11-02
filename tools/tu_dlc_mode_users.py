"""Which entries of Lara's title-update (TU) state machine tables branch on the DLC 2 / doppelganger mode
(gameTracker+0x1244) or use the meter object (gameTracker+0x508) in their own body (read-only; 2026-11-02, missing
list for DLC 2: the TU changed retail states such as 1014 - not only the TU-only ids 243-245 / 1017-1020 / 2102).

Tables (TU image, registered by 0x82473b50 like the PC tru+0x368b60): states 0x82757948 / 0x82758dd8 {id, 6 slot functions},
conditions 0x8277f558 / 0x8277f068 {id, group, function}, activities 0x82759258 / 0x827596c8 {id, function}
(each record list closed by id 0). Body of an entry = its .pdata range, or (leaf code without .pdata) from the entry up
to the next .pdata start / table entry, at most 0x400 bytes. The same ids are then looked up in the retail tables
(retail image, same table order from the retail registration) when --retail is given, to tell TU-only ids from changed
retail ids.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/tu_dlc_mode_users.py TU_IMAGE [--disp 1244,508]
"""
import sys, os, struct, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xbox_image_sections as XS
import ppc_xrefs as PX

BASE = 0x82000000
STATES = (0x82757948, 0x82758dd8)
CONDS = (0x8277f558, 0x8277f068)
ACTS = (0x82759258, 0x827596c8)


def rd(d, va, n):
    return struct.unpack_from('>%dI' % n, d, va - BASE)


def table(d, va, words):
    out = []
    while True:
        r = rd(d, va, words)
        if r[0] == 0 or r[0] > 0xffff: break
        out.append(r); va += 4 * words
        if len(out) > 2000: break
    return out


TEMPLATE = 0x82487718                             # shared condition template (PC tru+0x382d70)


def body(d, f, funcs, starts):
    """(end, words) - the .pdata range, else leaf code up to the first blr / unconditional b (max 0x400 bytes)"""
    k = bisect.bisect_left(starts, f)
    if k < len(funcs) and funcs[k][0] == f:
        end = funcs[k][1]
        return end, rd(d, f, (end - f) // 4)
    out = []
    for i in range(0x100):
        x = rd(d, f + 4 * i, 1)[0]
        out.append(x)
        if x == 0x4e800020 or (x >> 26 == 18 and not x & 3): break
    return f + 4 * len(out), tuple(out)


def uses(w, f, disps):
    return ['0x%08x +0x%x' % (f + 4 * i, x & 0xffff) for i, x in enumerate(w)
            if x >> 26 in (32, 34, 36, 38, 40) and (x & 0xffff) in disps]


def predicate(w, f):
    """condition handler `lis r11,hi; addi r6,r11,lo; b TEMPLATE` -> the predicate address"""
    if len(w) >= 3 and w[0] >> 26 == 15 and w[1] >> 26 == 14 and (w[1] >> 21) & 31 == 6 and w[2] >> 26 == 18:
        li = w[2] & 0x03fffffc
        if li & 0x02000000: li -= 0x04000000
        if (f + 8 + li) & 0xffffffff == TEMPLATE:
            lo = w[1] & 0xffff
            return (((w[0] & 0xffff) << 16) + (lo - 0x10000 if lo & 0x8000 else lo)) & 0xffffffff
    return None


def main(argv):
    disps = [0x1244, 0x508]
    if '--disp' in argv: k = argv.index('--disp'); disps = [int(x, 16) for x in argv[k + 1].split(',')]; del argv[k:k + 2]
    d, secs = PX.load(argv[0])
    funcs = PX.pdata(d, secs)
    starts = [f[0] for f in funcs]
    entries = []                                  # (func, label)
    for r in [r for t in STATES for r in table(d, t, 7)]:
        for s, f in enumerate(r[1:]):
            if f: entries.append((f, 'state %d slot %d' % (r[0], s)))
    for t in CONDS:
        for r in table(d, t, 3): entries.append((r[2], 'condition %d (table 0x%08x)' % (r[0], t)))
    for t in ACTS:
        for r in table(d, t, 2): entries.append((r[1], 'activity %d (table 0x%08x)' % (r[0], t)))
    entries = [e for e in entries if BASE <= e[0] < BASE + len(d)]
    for f, label in entries:
        end, w = body(d, f, funcs, starts)
        hits = uses(w, f, disps)
        p = predicate(w, f)
        if p:
            pe, pw = body(d, p, funcs, starts)
            hits += ['predicate 0x%08x: %s' % (p, h) for h in uses(pw, p, disps)]
        if hits:
            print('%-40s 0x%08x..0x%08x  %s' % (label, f, end, ', '.join(hits)))


if __name__ == '__main__':
    main(sys.argv[1:])
