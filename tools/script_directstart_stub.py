"""TEST ONLY: make the main menu start a DLC level by itself, once per game launch (finding 43, test 41).

How the mission screen (PC generalbank script 104) starts a DLC: its function 8 picks the unit name of the focused
entry ('dlc_level2_start' for DLC 2, after `dlcsystem` f1 confirmed the .drm exists), stores it in member 652 and calls
its function 9, which runs `uigamedata` f22 (member 560 = the uigamedata object), then `uigamedata` f27(unit name,
1, 0, 1) - the native that starts the level (levels 4-6 use 0, 0, 1) - and closes the screens with `stdscreenmgr`
f19 and f7 (member 596). The level select (script 119) does the same with literal unit names.

This tool appends that sequence as a stub to the main menu script (PC script 7) and jumps to it from the first debug
line marker of function 18 (vtable slot 22, name 983 - the screen's per-frame update: it also starts the attract
video when the menu idles). Test 41 hooked function 15 (vtable 14) instead: that one is NOT called while the menu
idles (played 21:54 - no f27, the only f22 was the attract video's from function 18), so test 41b uses function 18:
  if member byte 8 != 0 (the screen's "active" byte, the same test functions 15 and 18 make) and flag == "N":
      flag = "Y"; uigamedata.f22(); uigamedata.f27(UNIT, 1, 0, 1); stdscreenmgr.f19(); stdscreenmgr.f7(); return
  else: continue function 18 as before
The flag is a 2-byte string in the appended data ("N\\0"), compared with a second literal "N" (`op4f`) and set by a
byte store (`op2e`) - generalbank stays loaded, so the start happens once per launch; back in the main menu after
quitting the level the menu works normally. Script 7 members (from its own calls): 2764 = uigamedata object,
2612 = stdscreenmgr object. Opcodes as in tools/script_dlc2_flag_stub.py (op05 = push string pointer, op04 = push
byte, op0f = member address, op65 = native call, op63 / op64 = jump relative to the next word, op7b = return).
Every replaced word is checked first (debug line markers without relocation).

Test 41b did nothing visible either. Script 7 is the front-end "uipause" screen (strings "UIPause::Run()", "Muting
audio while the pause screen is open"), used as main AND pause menu; its functions are event handlers - function 0
(state 0) runs once, function 1 (vtable 2, name 521) is the screen's OnOpen (it sets member 8 = 1 at its end,
function 2 / vtable 3 / name 522 sets it to 0), 15 and 18 are input / timer handlers whose calls are not proven.
--site 3f64 --no-active (test 41c): hook the first debug line marker of function 1 = OnOpen instead (runs when the
main menu opens; member 8 is only set at its end, so no active gate), back to +0x3f68.

--debug-prints (test 41c): the stub also calls the script print native `corebase` f7 ((8,230)+0x138, static call,
exe tru+0x395e30) with markers "DIRECTSTART 0 enter", "1 active", "2 first", "3 after f22", "4 after f27" - a cdb
breakpoint on tru+0x395e30 logging the string shows how far the stub gets.

Usage (from the repository root):
  ../bin/pyt tools/script_directstart_stub.py IN_DRM OUT_DRM [UNIT] [--debug-prints] [--site HEX] [--no-active]
  UNIT default dlc_level2_start; --site default 33b4 (function 18 entry, test 41b)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

SID = 7
SITE = 0x33b4                 # function 18 entry: op00 2064 (debug line marker), back to SITE + 4
ACTIVE = 8                    # member byte tested by functions 15 / 18 before they act
UGD, SCR = 2764, 2612         # script 7 members: uigamedata object, stdscreenmgr object
F22, F27 = (63, 0x2cc), (63, 0x358)
F19, F7 = (95, 0x268), (95, 0x118)
PRINT = (230, 0x138)          # corebase f7: script print (string, bool), static call
PLACEHOLDER = 0xBEEBBEEB


def op(o, n=0):
    return ((o & 0xff) << 24) | (n & 0xffffff)


def main(argv):
    global SITE
    prints = '--debug-prints' in argv; gate = '--no-active' not in argv
    if '--site' in argv:
        k = argv.index('--site'); SITE = int(argv[k + 1], 16); del argv[k:k + 2]
    argv = [a for a in argv if a not in ('--debug-prints', '--no-active')]
    src, out = argv[0], argv[1]
    unit = argv[2] if len(argv) > 2 else 'dlc_level2_start'
    D = DW.read(open(src, 'rb').read(), 'le')
    s = next(x for x in D.sections if x.type == 8 and x.id == SID)
    d = bytearray(s.data); r = R.parse(s.reloc, 'le')
    it = dict(r.internal); ext = {so for _, so, _ in r.external}
    w = lambda a: struct.unpack_from('<I', d, a)[0]
    if SITE in it or SITE in ext or w(SITE) >> 24 != 0:
        sys.exit('+0x%x: expected a debug line marker (op00), found %08x - nothing written' % (SITE, w(SITE)))
    idx = {(x.type, x.id): i for i, x in enumerate(D.sections)}
    si = {63: idx[(8, 63)], 95: idx[(8, 95)], 230: idx[(8, 230)]}

    while len(d) % 4: d.append(0)
    stub = len(d)
    code = []                                    # (word, reloc): ('ext', script, offset) / ('int', string key)
    E = lambda word, rel=None: code.append((word, rel))
    marks = {}

    def P(n, text):                              # debug print: op05 text; op04 1; op66 corebase.f7
        if prints:
            marks['m%d' % n] = 'DIRECTSTART %d %s' % (n, text)
            E(op(0x05)); E(PLACEHOLDER, ('int', 'm%d' % n)); E(op(0x04, 1)); E(op(0x66)); E(PLACEHOLDER, ('ext', 230, PRINT[1]))
    P(0, 'enter')
    skips = []
    if gate:
        E(op(0x0c, ACTIVE))
        skips.append(len(code)); E(None)                               # op64 -> continue (screen not active)
    P(1, 'active')
    E(op(0x05)); E(PLACEHOLDER, ('int', 'flag')); E(op(0x05)); E(PLACEHOLDER, ('int', 'n')); E(op(0x4f))
    skips.append(len(code)); E(None)                                   # op64 -> continue (flag != "N")
    E(op(0x05)); E(PLACEHOLDER, ('int', 'flag')); E(op(0x04, 0x59)); E(op(0x2e))          # flag[0] = 'Y'
    P(2, 'first')
    E(op(0x0f, UGD)); E(op(0x65)); E(PLACEHOLDER, ('ext', 63, F22[1]))                     # uigamedata.f22()
    P(3, 'after f22')
    E(op(0x05)); E(PLACEHOLDER, ('int', 'unit')); E(op(0x04, 1)); E(op(0x04, 0)); E(op(0x04, 1))
    E(op(0x0f, UGD)); E(op(0x65)); E(PLACEHOLDER, ('ext', 63, F27[1]))                     # uigamedata.f27(unit,1,0,1)
    P(4, 'after f27')
    E(op(0x0f, SCR)); E(op(0x65)); E(PLACEHOLDER, ('ext', 95, F19[1]))                     # stdscreenmgr.f19()
    E(op(0x0f, SCR)); E(op(0x65)); E(PLACEHOLDER, ('ext', 95, F7[1]))                      # stdscreenmgr.f7()
    E(op(0x7b))                                                                             # return
    cont = len(code); E(None)                                          # op63 -> SITE + 4
    at = lambda i: stub + 4 * i
    for i in skips:
        code[i] = (op(0x64, (at(cont) - (at(i) + 4)) // 4), None)
    code[cont] = (op(0x63, ((SITE + 4) - (at(cont) + 4)) // 4), None)
    for word, _ in code:
        d += struct.pack('<I', word)
    strs = {}
    for key, text in [('flag', 'N'), ('n', 'N'), ('unit', unit)] + sorted(marks.items()):
        while len(d) % 4: d.append(0)
        strs[key] = len(d); d += text.encode('ascii') + b'\0'
    while len(d) % 4: d.append(0)
    for i, (word, rel) in enumerate(code):
        if rel and rel[0] == 'ext': r.external.append((si[rel[1]], at(i), rel[2]))
        elif rel and rel[0] == 'int': r.internal.append((at(i), strs[rel[1]]))
    struct.pack_into('<I', d, SITE, op(0x63, (stub - (SITE + 4)) // 4))

    before = len(s.data); s.data = bytes(d); s.reloc = R.write(r, 'le')
    raw = D.write('le'); C = DW.read(DW.cdrm_encode(raw, 'le'), 'le')
    infos = [dict(size=len(x.data)) for x in C.sections]
    bad = sum(bool(R.check(R.parse(x.reloc, 'le'), len(x.data), infos)) for x in C.sections)
    if bad: sys.exit('%d sections with relocations out of bounds - %s NOT written' % (bad, out))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(DW.cdrm_encode(raw, 'le'))
    print('script %d: site +0x%x -> stub at +0x%x (%d code words, unit %r), section %d -> %d bytes; sections with '
          'relocations out of bounds: %d -> %s' % (SID, SITE, stub, len(code), unit, before, len(d), bad, out))
    for i, (word, rel) in enumerate(code):
        print('  +0x%05x  %08x  %s' % (at(i), word, rel or ''))


if __name__ == '__main__':
    main(sys.argv[1:])
