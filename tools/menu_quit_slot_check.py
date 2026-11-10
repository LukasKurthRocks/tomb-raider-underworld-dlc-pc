"""Which entry the last ring slot (slot 7, bottom left) of the PC main / pause menu shows, read-only (2026-11-10,
finding Befund-Hauptmenue-Beenden-1011.md: "Spiel beenden" missing from the main menu with the DLC entry).

generalbank script 7 (`uipause`, the ring menu shared by the main menu and the pause menu) decides slot 7 at three
code sites - "QUIT GAME" (door icon 0x738, text widget 0x3a8 = locals 131, click -> quit dialog script 128) or
"DOWNLOADABLE CONTENT" (download icon 0x72c, text widget 0x39c, click -> the DLC sub-ring PLAY MISSION / COMMUNITY
INFO / DOWNLOAD CONTENT):
  P1 func 27 (highlight icon)          window +0x6288  local 0xa0
  P2 func 35 (PositionMenuItems, 7)    window +0x9688  local 0x9c
  P4 func 8  (click on hit area 0x138) window +0x188dc local 0xb8
Each window holds one of three forms (7 words):
  pc     PC original:  op00 marker; op09 l; op66 corebase f17 (+0x250, always TRUE on PC); op06 l; op64 n; op00 marker
                       -> QUIT in the main menu and in the pause menu
  f15    tools/menu_dlc_patch.py (A / B): the same with corebase f15 (+0x218, always FALSE on PC)
                       -> DLC in both menus, no QUIT anywhere
  b138   upstream B132+ kit ("pause-menu QUIT" fix): op09 l; op0f 0xacc (uigamedata object); op65 uigamedata f37
                       (+0x470, "in front end"); op06 l; op50 NOT; op64 n-1
                       -> DLC in the main menu, QUIT in the pause menu
Also reported: the uilocalstr word at +0x25934 (member 0xc4c, func 1 labels widget 0x39c with it in the front end):
PC 163 "EXIT", menu_dlc_patch / B138 130 "DOWNLOADABLE CONTENT".

Usage (from the repository root):
  ../bin/pyt -t 300 tools/menu_quit_slot_check.py SOURCE [SOURCE ...] [--expect pc|f15|b138]
  SOURCE as tools/script_func_list.sections: a PC generalbank.drm file, pp / pb (PC patch / bigfile) or pc:generalbank.drm
  exit 0: every site of every source has one known form, the three sites agree (and match --expect when given);
  exit 1 otherwise (unknown words, mixed forms, other expectation).
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL

SID = 7
PH = 0xBEEBBEEB
SITES = [('P1', 'func 27 highlight icon', 0x6288, 0xa0, 13, 0x9f2),
         ('P2', 'func 35 PositionMenuItems case 7', 0x9688, 0x9c, 47, 0xbab),
         ('P4', 'func 8 click on slot 7 (hit area 0x138)', 0x188dc, 0xb8, 334, 0x301)]
COREBASE, UIGAMEDATA = 230, 63
F15, F17, F37 = 0x218, 0x250, 0x470
TEXT_OFF = 0x25934
TEXT = {163: 'EXIT', 130: 'DOWNLOADABLE CONTENT'}
MEANING = {'pc': ('QUIT GAME', 'QUIT GAME'), 'f15': ('DOWNLOADABLE CONTENT', 'DOWNLOADABLE CONTENT'),
           'b138': ('DOWNLOADABLE CONTENT', 'QUIT GAME')}


def classify(d, ext, base, loc, jz, marker):
    w = [struct.unpack_from('<I', d, base + 4 * k)[0] for k in range(7)]
    pc = [marker, 0x09000000 | loc, 0x66000000, PH, 0x06000000 | loc, 0x64000000 | jz, marker + 1]
    b138 = [0x09000000 | loc, 0x0f000acc, 0x65000000, PH, 0x06000000 | loc, 0x50000000, 0x64000000 | (jz - 1)]
    if w == pc:
        t = ext.get(base + 12)
        if t == (8, COREBASE, F17): return 'pc', w
        if t == (8, COREBASE, F15): return 'f15', w
        return 'unknown (pc layout, call target %s)' % (t,), w
    if w == b138:
        t = ext.get(base + 12)
        if t == (8, UIGAMEDATA, F37): return 'b138', w
        return 'unknown (b138 layout, call target %s)' % (t,), w
    return 'unknown', w


def check(src):
    S, e = FL.sections(src)
    if e != 'le':
        print('%s: not a PC (little-endian) source' % src)
        return None, False
    sec = next((q for q in S if q[0] == 8 and q[1] == SID and q[2]), None)
    if sec is None:
        print('%s: script %d not found' % (src, SID))
        return None, False
    d, rl = sec[2], sec[3]
    rel = R.parse(rl, e)
    ext = {so: (S[si][0], S[si][1], do) for si, so, do in rel.external}
    it = dict(rel.internal)
    print('== %s  script %d  %d B' % (src, SID, len(d)))
    forms = []
    for key, what, base, loc, jz, marker in SITES:
        f, w = classify(d, ext, base, loc, jz, marker)
        forms.append(f)
        print('  %s +0x%05x %-40s %-6s %s' % (key, base, what, f, ' '.join('%08x' % x for x in w)))
    tw = struct.unpack_from('<I', d, TEXT_OFF)[0]
    tok = it.get(TEXT_OFF - 4) == TEXT_OFF and struct.unpack_from('<I', d, TEXT_OFF - 0x10)[0] == 131
    print('  text +0x%05x member 0xc4c: %d %s%s' % (TEXT_OFF, tw, TEXT.get(tw, '?'),
                                                    '' if tok else '  (layout NOT as on PC - word not checked)'))
    one = len(set(forms)) == 1 and forms[0] in MEANING
    if one:
        mm, pm = MEANING[forms[0]]
        print('  -> slot 7 (bottom left, last ring entry): main menu = %s, pause menu = %s%s' % (
            mm, pm, '' if 'QUIT' in mm else '; the main menu has NO quit entry'))
    else:
        print('  -> sites disagree or unknown: %s' % ', '.join(forms))
    return (forms[0] if one else None), one


def main(argv):
    expect = None
    if '--expect' in argv:
        k = argv.index('--expect'); expect = argv[k + 1]; del argv[k:k + 2]
        if expect not in MEANING:
            print('--expect must be one of %s' % ', '.join(MEANING))
            return 2
    if not argv:
        print(__doc__)
        return 2
    ok = True
    for src in argv:
        form, good = check(src)
        ok &= good and (expect is None or form == expect)
        if good and expect is not None and form != expect:
            print('  EXPECTED %s, got %s' % (expect, form))
    print('result: %s' % ('ok' if ok else 'NOT ok'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
