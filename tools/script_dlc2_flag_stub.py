"""Emulate the title update's `dlc2data` native in the ported hint-box script (PC script 9) - finding 43, test 37.

On the Xbox the TU exe decides natively whether a hint is the modal DLC 2 box (`dlc2data` f0 = get, f1 = set; no
level script calls them). The PC has no such native, so this tool rewrites the five call sites of a generalbank whose
script 9 already had them replaced by debug line markers (test 35/36 builds):
  * f2 site +0x434 (4 words): `op63 -> stub`; the stub, APPENDED to the section (nothing moves), asks the engine for
    the current unit name like TU script 6 function 9 does on PC - `uigamedata` f34 (no parameters, returns a
    string) into local 12 (the frame's type-0x34 string local), then `corebase` f14 on it (same call as script 6) -
    compares it (`op4f`, strcmp) with the 10 DLC 2 unit names of script 6 (level number 102), stores the result
    byte to local 1 AND to member +0x50 (the embedded `dlc2data` object, now our flag) and jumps back to +0x444,
    where `op06 1` (restored; test 35/36 had `op04 C`) feeds the original branch;
  * f9 site +0x958: `op09 8, op0c 80, op2e, op00` - local 8 = flag byte (the `dlc2data` getter); +0x968 `op06 8`
    restored;
  * f1 sites +0x754 (0), +0x864 (1), +0x9b8 (0): `op0f 80, op04 X, op2e, op00` - flag byte = X (the setter).
Opcodes as read from tru.exe (jump table tru+0x17e52c): op0f = address of member, op0c = byte member, op09 = address of
local, op08 = u32 local, op2e = store byte (pops value, then address), op4f = strcmp == 0, op64 N = jump N words if 0,
op63 N = jump N words (both relative to the next word), op65 / op66 = native / static call; a function with a return
value takes its result pointer from the stack slot below its arguments.
Every word that is replaced is checked first; the tool refuses if a site does not hold what a test 36 build holds.

Usage (from the repository root):
  ../bin/pyt tools/script_dlc2_flag_stub.py IN_DRM OUT_DRM
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

SID = 9
DLC2_UNITS = ['dlc_level2_start', 'dlc_yggdrasil_end', 'dlc_yggdrasil_hall01', 'dlc_yggdrasil_hall02',
              'dlc2_ceremony_room', 'dlc2_goo_room', 'dlc2_hall_ceremony_goo', 'dlc2_hall_goo_machine',
              'dlc2_hall_machine_ceremony', 'dlc2_machine_room']
F34 = (63, 0x41c)       # uigamedata f34: current unit name (PC offsets, as referenced by our PC script 6 +0xa480)
F14 = (230, 0x1fc)      # corebase f14 on that name (PC script 6 +0xa48c)
MEMBER = 0x50           # the embedded dlc2data object of script 9 (op0f 80 at every original call)
UGD = 140               # member holding the uigamedata object (script 9 f7: op0f 140 -> uigamedata f69)
PLACEHOLDER = 0xBEEBBEEB


def op(o, n=0):
    return ((o & 0xff) << 24) | (n & 0xffffff)


def main(argv):
    src, out = argv[0], argv[1]
    D = DW.read(open(src, 'rb').read(), 'le')
    s = next(x for x in D.sections if x.type == 8 and x.id == SID)
    d = bytearray(s.data); r = R.parse(s.reloc, 'le')
    it = dict(r.internal); ext = {so for _, so, _ in r.external}
    w = lambda a: struct.unpack_from('<I', d, a)[0]

    def put(a, v):
        struct.pack_into('<I', d, a, v)

    def need_markers(a, n=4):
        for k in range(n):
            x = a + 4 * k
            if x in it or x in ext or w(x) >> 24 != 0:
                sys.exit('+0x%x: expected a debug line marker (op00) without relocation, found %08x - not a test 36 '
                         'build, nothing written' % (x, w(x)))

    def need(a, v):
        if w(a) != v:
            sys.exit('+0x%x: expected %08x, found %08x - nothing written' % (a, v, w(a)))

    for a in (0x434, 0x958, 0x754, 0x864, 0x9b8):
        need_markers(a)
    need(0x444, op(4, 1)); need(0x448, op(0x64, 4))           # test 36 (f0 = 1): op04 1, op64 4
    need(0x968, op(4, 1)); need(0x96c, op(0x64, 24))
    idx = {(x.type, x.id): i for i, x in enumerate(D.sections)}
    si63, si230 = idx[(8, F34[0])], idx[(8, F14[0])]

    # --- appended stub: code, then the strings ------------------------------------------------------------------
    while len(d) % 4: d.append(0)
    stub = len(d)
    code = []                                   # (word, reloc) reloc = ('ext', si, dst) / ('int', string index) / None
    E = lambda word, rel=None: code.append((word, rel))
    E(op(0x09, 12)); E(op(0x09, 12))            # result slots: f14 -> local 12, f34 -> local 12 (pushed first = f14's)
    E(op(0x0f, UGD)); E(op(0x65)); E(PLACEHOLDER, ('ext', si63, F34[1]))     # local12 = uigamedata.f34()
    E(op(0x08, 12)); E(op(0x66)); E(PLACEHOLDER, ('ext', si230, F14[1]))     # local12 = corebase.f14(local12)
    jumps_to_match = []
    for k, _ in enumerate(DLC2_UNITS):
        # op05 + the relocated string pointer (test 37 lacked the op05 word: the pointer itself ran as op03 and pushed
        # its low 24 bits - crash in op4f at tru+0x17dbf3 with 0x00154660)
        E(op(0x08, 12)); E(op(0x05)); E(PLACEHOLDER, ('int', k)); E(op(0x4f)); E(op(0x64, 1))
        jumps_to_match.append(len(code)); E(None)                           # op63 -> MATCH, filled below
    tails = {}
    for name, val in (('nomatch', 0), ('match', 1)):
        tails[name] = len(code)
        E(op(0x09, 1)); E(op(0x04, val)); E(op(0x2e))                        # local1 = val
        E(op(0x0f, MEMBER)); E(op(0x04, val)); E(op(0x2e))                   # flag  = val
        tails[name + '_back'] = len(code); E(None)                          # op63 -> +0x444
    at = lambda i: stub + 4 * i
    for i in jumps_to_match:
        code[i] = (op(0x63, (at(tails['match']) - (at(i) + 4)) // 4), None)
    for t in ('nomatch_back', 'match_back'):
        i = tails[t]; code[i] = (op(0x63, (0x444 - (at(i) + 4)) // 4), None)
    for word, _ in code:
        d += struct.pack('<I', word)
    strs = []
    for u in DLC2_UNITS:
        while len(d) % 4: d.append(0)
        strs.append(len(d)); d += u.encode('ascii') + b'\0'
    while len(d) % 4: d.append(0)
    for i, (word, rel) in enumerate(code):
        if rel and rel[0] == 'ext': r.external.append((rel[1], at(i), rel[2]))
        elif rel and rel[0] == 'int': r.internal.append((at(i), strs[rel[1]]))

    # --- the call sites ---------------------------------------------------------------------------------------------
    put(0x434, op(0x63, (stub - 0x438) // 4))                                  # f2: f0 query -> stub
    put(0x444, op(0x06, 1))                                                    # restore op06 1
    put(0x958, op(0x09, 8)); put(0x95c, op(0x0c, MEMBER)); put(0x960, op(0x2e))  # f9: local8 = flag
    put(0x968, op(0x06, 8))                                                    # restore op06 8
    for a, val in ((0x754, 0), (0x864, 1), (0x9b8, 0)):                        # f1(val): flag = val
        put(a, op(0x0f, MEMBER)); put(a + 4, op(0x04, val)); put(a + 8, op(0x2e))

    before = len(s.data); s.data = bytes(d); s.reloc = R.write(r, 'le')
    raw = D.write('le'); C = DW.read(DW.cdrm_encode(raw, 'le'), 'le')
    infos = [dict(size=len(x.data)) for x in C.sections]
    bad = sum(bool(R.check(R.parse(x.reloc, 'le'), len(x.data), infos)) for x in C.sections)
    if bad: sys.exit('%d sections with relocations out of bounds - %s NOT written' % (bad, out))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(DW.cdrm_encode(raw, 'le'))
    print('script %d: stub at +0x%x (%d code words, %d strings, 2 external + %d internal relocations), section %d -> '
          '%d bytes; sites 0x434 / 0x444 / 0x958 / 0x968 / 0x754 / 0x864 / 0x9b8 rewritten; sections with relocations '
          'out of bounds: %d -> %s' % (SID, stub, len(code), len(strs), len(strs), before, len(d), bad, out))
    for i, (word, rel) in enumerate(code):
        print('  +0x%04x  %08x  %s' % (at(i), word, rel or ''))


if __name__ == '__main__':
    main(sys.argv[1:])
