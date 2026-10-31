"""DLC 2 player object (doppelganger_casual, object 857, and its extension object 858) - data part of the title
update's chain, translated for the PC (object 858 investigation, 2026-10-31).

How the Xbox title update (TU) makes DLC 2's player the doppelganger and loads object 858:
  1. mission screen (Xbox TU generalbank script 134, function 9): for dlc_level4/5/6 AND dlc_level2_start the level is
     started with uigamedata "load level"(unit, 0, 0, 1) - no costume / weapon selection; the PC script 104 (B138)
     passes 0 only for levels 4-6, so DLC 2 gets (1, 0, 1) and the costume selection's costume (lara_casual).
  2. exe (TU 0x82297d30 GAMELOOP_LevelLoadAndInit): the unit's default costume of dlc_level2_start is object 11
     lara_doppelganger; the TU replaces the name "lara_doppelganger" by "doppelganger_casual" - code, see
     src/asi/TruDlc2Player.
  3. object 857's child id list (state chart DTP +0x48 -> u16 list, 0-terminated) names the objects loaded with it:
     Xbox {69 bullet_hit, 68 fx_saving_grab_prompt, 70 camerashakes, 858 player_tru_dlc2_extension, 71 g_healthpack}.
     Our converted file holds {53, 52, 70, 858, 71}: the last two base ids were not remapped (PC 70 / 71 are
     pr_spear_concentrated / pr_thorbolt; right: 54 camerashakes, 55 g_healthpack).

Commands (read-only unless an output path is given):
  gb  IN_GENERALBANK OUT_GENERALBANK [--stub-select0]
      script 104 function 9: the TU's level test (4, 5, 6, 2) in an appended block, reached from the debug line
      marker before the PC test (+0x23bc) and returning to the PC's conditional jump (+0x23f8); every word checked
      first. --stub-select0: in a direct-start test generalbank (tools/script_directstart_stub.py) the stub's
      f27(dlc_level2_start, 1, 0, 1) becomes f27(dlc_level2_start, 0, 0, 1) - what the TU passes for DLC 2.
  ids XBOX.drm PC.drm XOBJECTLIST PCOBJECTLIST [OUT.drm]
      compare (and with OUT fix) the child id list of the object: Xbox ids remapped by name (base objects) or kept
      (DLC objects >= 822), as tools/objlists.py builds the merged list.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/dlc2_player_fix.py gb mods/generalbank.drm out/generalbank.drm --stub-select0
  ../bin/pyt -t 120 tools/dlc2_player_fix.py ids x_doppelganger_casual.drm mods/doppelganger_casual.drm \
        work/generic/lists/dlc_pack11_objectlist.txt mods/tr8/pc-w/objectlist.txt out/doppelganger_casual.drm
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import objlists as OL

PLACEHOLDER = 0xBEEBBEEB
MISSION = 104                 # PC generalbank script: mission screen (Xbox TU 134)
SITE = 0x23bc                 # function 9: debug line marker (op00 252) before the level test
TEST_END = 0x23f8             # op64 9: jump to the "with costume selection" call when the test is false
UNIT_MEMBER = 652             # member holding the unit name
F27 = (63, 0x358)             # uigamedata "load level" (PC f27; Xbox TU f26)


def op(o, n=0):
    return ((o & 0xff) << 24) | (n & 0xffffff)


def cstr(d, a):
    e = d.index(b'\0', a)
    return d[a:e].decode('latin-1')


def save(D, out):
    raw = D.write('le'); C = DW.read(DW.cdrm_encode(raw, 'le'), 'le')
    infos = [dict(size=len(x.data)) for x in C.sections]
    bad = sum(bool(R.check(R.parse(x.reloc, 'le'), len(x.data), infos)) for x in C.sections)
    if bad:
        sys.exit('%d sections with relocations out of bounds - %s NOT written' % (bad, out))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(DW.cdrm_encode(raw, 'le'))
    print('written %s (sections with relocations out of bounds: 0)' % out)


def fix_mission(D):
    s = next(x for x in D.sections if x.type == 8 and x.id == MISSION)
    d = bytearray(s.data); r = R.parse(s.reloc, 'le')
    it = dict(r.internal)
    w = lambda a: struct.unpack_from('<I', d, a)[0]
    # op05 is followed by its string pointer word (internal relocation), None = that pointer word
    want = [op(0x00, 252), op(0x0e, UNIT_MEMBER), op(0x05), None, op(0x4f), op(0x0e, UNIT_MEMBER), op(0x05), None,
            op(0x4f), op(0x52), op(0x0e, UNIT_MEMBER), op(0x05), None, op(0x4f), op(0x52), op(0x64, 9)]
    if SITE + 4 * (len(want) - 1) != TEST_END:
        sys.exit('internal layout error')
    have = [w(SITE + 4 * i) for i in range(len(want))]
    names = {}
    for i, k in ((3, 4), (7, 5), (12, 6)):
        a = SITE + 4 * i
        if a not in it:
            sys.exit('script %d +0x%x: no string relocation - nothing written' % (MISSION, a))
        names[k] = it[a]
    strings = {k: cstr(d, v) for k, v in names.items()}
    ok = all(x is None or h == x for h, x in zip(have, want))
    print('script %d function 9 at +0x%x: %s; strings %s' % (MISSION, SITE, ' '.join('%08x' % h for h in have), strings))
    if not ok or strings != {4: 'dlc_level4_start', 5: 'dlc_level5_start', 6: 'dlc_level6_start'}:
        sys.exit('unexpected code - nothing written')
    # existing 'dlc_level2_start' string in the script (function 8 stores the unit names), else append one
    lvl2 = None
    for a, t in sorted(it.items()):
        if 0 <= t < len(d) - 16 and d[t:t + 17] == b'dlc_level2_start\0':
            lvl2 = t; break
    while len(d) % 4: d.append(0)
    if lvl2 is None:
        lvl2 = len(d); d += b'dlc_level2_start\0'
        while len(d) % 4: d.append(0)
    block = len(d)
    S = lambda t: [(op(0x05), None), (PLACEHOLDER, t)]          # push string: op05 + relocated pointer word
    code = ([(op(0x0e, UNIT_MEMBER), None)] + S(names[4]) + [(op(0x4f), None)] +
            [(op(0x0e, UNIT_MEMBER), None)] + S(names[5]) + [(op(0x4f), None), (op(0x52), None)] +
            [(op(0x0e, UNIT_MEMBER), None)] + S(names[6]) + [(op(0x4f), None), (op(0x52), None)] +
            [(op(0x0e, UNIT_MEMBER), None)] + S(lvl2) + [(op(0x4f), None), (op(0x52), None)])
    back = block + 4 * len(code)
    code.append((op(0x63, (TEST_END - (back + 4)) // 4), None))
    for i, (word, target) in enumerate(code):
        a = block + 4 * i
        d += struct.pack('<I', word)
        if target is not None:
            r.internal.append((a, target))
    struct.pack_into('<I', d, SITE, op(0x63, (block - (SITE + 4)) // 4))
    s.data = bytes(d); s.reloc = R.write(r, 'le')
    print('script %d: +0x%x -> block +0x%x (test 4, 5, 6, 2 as Xbox TU script 134 function 9), back to +0x%x; '
          "'dlc_level2_start' at +0x%x" % (MISSION, SITE, block, TEST_END, lvl2))


def fix_stub(D):
    """direct-start stub (test generalbank): f27('dlc_level2_start', 1, 0, 1) -> (.., 0, 0, 1)"""
    idx = {i: x for i, x in enumerate(D.sections)}
    sec63 = next(i for i, x in idx.items() if x.type == 8 and x.id == F27[0])
    n = 0
    for s in D.sections:
        if s.type != 8:
            continue
        d = bytearray(s.data); r = R.parse(s.reloc, 'le')
        it = dict(r.internal); ext = {so: (si, to) for si, so, to in r.external}
        w = lambda a: struct.unpack_from('<I', d, a)[0]
        for a in range(0, len(d) - 32, 4):
            if a not in it or w(a - 4) != op(0x05) and w(a - 4) >> 24 != 5:
                continue
            t = it[a]
            if not (0 <= t < len(d)) or d[t:t + 17] != b'dlc_level2_start\0':
                continue
            seq = [w(a + 4 * k) for k in range(1, 7)]
            if seq[0:3] == [op(0x04, 1), op(0x04, 0), op(0x04, 1)] and seq[3] >> 24 == 0x0f and seq[4] == op(0x65) \
                    and ext.get(a + 24) == (sec63, F27[1]):
                struct.pack_into('<I', d, a + 4, op(0x04, 0))
                print('script %d +0x%x: f27(dlc_level2_start, 1, 0, 1) -> (0, 0, 1)' % (s.id, a + 4))
                n += 1
        s.data = bytes(d)
    if n != 1:
        sys.exit('direct-start stub: %d matches (expected 1) - nothing written' % n)


def child_list(D, f):
    head = next(x for x in D.sections if x.type == 11)
    root = struct.unpack_from(f + 'I', head.data, 0)[0]
    s = next(x for x in D.sections if x.type == 7 and x.id == root)
    r = R.parse(bytes(s.reloc), 'be' if f == '>' else 'le')
    it = dict(r.internal)
    if 0x48 not in it:
        return s, None, []
    a = it[0x48]; ids = []
    while True:
        v = struct.unpack_from(f + 'H', s.data, a + 2 * len(ids))[0]
        if v == 0:
            break
        ids.append(v)
    return s, a, ids


def fix_ids(argv):
    X = DW.read(open(argv[0], 'rb').read(), 'be')
    P = DW.read(open(argv[1], 'rb').read(), 'le')
    xo = OL.read_objectlist(open(argv[2], 'rb').read())
    po = OL.read_objectlist(open(argv[3], 'rb').read())
    byname = {v: k for k, v in po.items()}
    _, xa, xids = child_list(X, '>')
    ps, pa, pids = child_list(P, '<')
    want = [byname.get(xo.get(i), i) for i in xids]
    print('object %s: DTP %d child list +0x%s' % (po.get(struct.unpack_from('<I', next(
        x for x in P.sections if x.type == 11).data, 0x14)[0]), ps.id, '%x' % pa if pa is not None else '-'))
    print('  Xbox: %s' % ', '.join('%d %s' % (i, xo.get(i, '?')) for i in xids))
    print('  PC:   %s' % ', '.join('%d %s' % (i, po.get(i, '?')) for i in pids))
    print('  want: %s' % ', '.join('%d %s' % (i, po.get(i, '?')) for i in want))
    if xa != pa or len(xids) != len(pids):
        sys.exit('list position / length differ - nothing written')
    bad = [k for k in range(len(want)) if want[k] != pids[k]]
    print('  %d of %d ids wrong%s' % (len(bad), len(want), (' at ' + ', '.join('+0x%x' % (pa + 2 * k) for k in bad)) if bad else ''))
    if len(argv) > 4 and bad:
        d = bytearray(ps.data)
        for k in bad:
            struct.pack_into('<H', d, pa + 2 * k, want[k])
        ps.data = bytes(d)
        save(P, argv[4])


def main(argv):
    if argv[0] == 'gb':
        stub = '--stub-select0' in argv
        argv = [a for a in argv if a != '--stub-select0']
        D = DW.read(open(argv[1], 'rb').read(), 'le')
        fix_mission(D)
        if stub:
            fix_stub(D)
        save(D, argv[2])
    elif argv[0] == 'ids':
        fix_ids(argv[1:])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
