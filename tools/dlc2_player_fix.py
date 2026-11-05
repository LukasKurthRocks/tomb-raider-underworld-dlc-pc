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
      Since 2026-11-05 (owner's decision S104) step 23 of tools/generalbank_build.py (pipeline step Generalbank).
  verify BEFORE AFTER [--tu TU_GENERALBANK_BE] [--report R.json]
      the check of `gb` (pipeline gate): AFTER must be BEFORE + exactly this fix. Every section except script 104 and
      the file header byte-identical; every changed / appended word of script 104 must be one the plan from BEFORE
      explains (the PC words at the site are checked again), with exactly the planned old and new value; the appended
      relocations exactly the planned ones; the block is decoded again from AFTER alone (jump at +0x23bc, 4 tests
      unit == dlc_level4/5/6/2_start joined by op52, jump back to +0x23f8). --tu: the same test order and opcodes as
      the Xbox title update's script 134 (big-endian TU generalbank, generalbank_build step 10). Exit 1 = refused.
  ids XBOX.drm PC.drm XOBJECTLIST PCOBJECTLIST [OUT.drm]
      compare (and with OUT fix) the child id list of the object: Xbox ids remapped by name (base objects) or kept
      (DLC objects >= 822), as tools/objlists.py builds the merged list.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/dlc2_player_fix.py gb mods/generalbank.drm out/generalbank.drm --stub-select0
  ../bin/pyt -t 120 tools/dlc2_player_fix.py verify steps/22_input.drm mods/generalbank.drm --tu steps/10_tu_be.drm
  ../bin/pyt -t 120 tools/dlc2_player_fix.py ids x_doppelganger_casual.drm mods/doppelganger_casual.drm \
        work/generic/lists/dlc_pack11_objectlist.txt mods/tr8/pc-w/objectlist.txt out/doppelganger_casual.drm
"""
import sys, os, struct, hashlib, json
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


class Refuse(Exception):
    """the input is not what the step expects - nothing is written (fix) / the check fails (verify)"""


LEVELS = ('dlc_level4_start', 'dlc_level5_start', 'dlc_level6_start', 'dlc_level2_start')   # Xbox TU order


def plan_mission(s, quiet=False):
    """script 104 section s -> (new data, new Reloc, info) of the fix; every PC word at the site is checked first
    (Refuse on any mismatch). info['words'] = {offset: (old word or None, new word, why)} - every word that changes
    or is appended; info['relocs'] = the appended internal relocations [(offset, target)]."""
    d = bytearray(s.data); r = R.parse(s.reloc, 'le')
    n0 = len(r.internal)
    it = dict(r.internal)
    w = lambda a: struct.unpack_from('<I', d, a)[0]
    # op05 is followed by its string pointer word (internal relocation), None = that pointer word
    want = [op(0x00, 252), op(0x0e, UNIT_MEMBER), op(0x05), None, op(0x4f), op(0x0e, UNIT_MEMBER), op(0x05), None,
            op(0x4f), op(0x52), op(0x0e, UNIT_MEMBER), op(0x05), None, op(0x4f), op(0x52), op(0x64, 9)]
    if SITE + 4 * (len(want) - 1) != TEST_END:
        raise Refuse('internal layout error')
    if len(d) < TEST_END + 4:
        raise Refuse('script %d is only %d bytes - not the PC mission screen script' % (MISSION, len(d)))
    have = [w(SITE + 4 * i) for i in range(len(want))]
    names = {}
    for i, k in ((3, 4), (7, 5), (12, 6)):
        a = SITE + 4 * i
        if a not in it:
            raise Refuse('script %d +0x%x: no string relocation - nothing written' % (MISSION, a))
        names[k] = it[a]
    strings = {k: cstr(d, v) for k, v in names.items()}
    ok = all(x is None or h == x for h, x in zip(have, want))
    if not quiet:
        print('script %d function 9 at +0x%x: %s; strings %s' % (MISSION, SITE, ' '.join('%08x' % h for h in have),
                                                                  strings))
    if not ok or strings != {4: LEVELS[0], 5: LEVELS[1], 6: LEVELS[2]}:
        raise Refuse('unexpected code - nothing written')
    old_len = len(d)
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
    S = lambda t, k: [(op(0x05), None, 'push string'), (PLACEHOLDER, t, "string pointer -> '%s'" % k)]
    M = (op(0x0e, UNIT_MEMBER), None, 'push member %d (unit name)' % UNIT_MEMBER)
    EQ = (op(0x4f), None, 'op4f compare (==)')
    OR = (op(0x52), None, 'op52 or')
    code = ([M] + S(names[4], LEVELS[0]) + [EQ] +
            [M] + S(names[5], LEVELS[1]) + [EQ, OR] +
            [M] + S(names[6], LEVELS[2]) + [EQ, OR] +
            [M] + S(lvl2, LEVELS[3]) + [EQ, OR])
    back = block + 4 * len(code)
    code.append((op(0x63, (TEST_END - (back + 4)) // 4), None, 'op63 jump back to the PC test jump +0x%x' % TEST_END))
    words = {}
    # bytes appended before the block (alignment, a new 'dlc_level2_start' string), word by word
    for a in range(old_len - old_len % 4, block, 4):
        words[a] = (None, w(a), 'alignment / appended string dlc_level2_start')
    for i, (word, target, why) in enumerate(code):
        a = block + 4 * i
        d += struct.pack('<I', word)
        words[a] = (None, word, why)
        if target is not None:
            r.internal.append((a, target))
    jump = op(0x63, (block - (SITE + 4)) // 4)
    words[SITE] = (w(SITE), jump, 'debug line marker op00 252 -> op63 jump to the block +0x%x' % block)
    struct.pack_into('<I', d, SITE, jump)
    info = dict(block=block, lvl2=lvl2, back=back, names=names, words=words, relocs=r.internal[n0:])
    return d, r, info


def fix_mission(D):
    s = next(x for x in D.sections if x.type == 8 and x.id == MISSION)
    d, r, info = plan_mission(s)
    s.data = bytes(d); s.reloc = R.write(r, 'le')
    print('script %d: +0x%x -> block +0x%x (test 4, 5, 6, 2 as Xbox TU script 134 function 9), back to +0x%x; '
          "'dlc_level2_start' at +0x%x" % (MISSION, SITE, info['block'], TEST_END, info['lvl2']))


def s24(v):
    v &= 0xffffff
    return v - (1 << 24) if v & 0x800000 else v


def decode_fix(d, it):
    """decode the fix in a FIXED script 104 by itself (not from the plan): the jump at SITE, the 4 tests of the block,
    the jump back - returns (block, [level strings], [opcode bytes of the block]) or raises Refuse"""
    w = lambda a: struct.unpack_from('<I', d, a)[0]
    j = w(SITE)
    if j >> 24 != 0x63:
        raise Refuse('+0x%x is %08x, not an op63 jump (fix missing)' % (SITE, j))
    block = SITE + 4 + 4 * s24(j)
    if not (TEST_END < block <= len(d) - 4 * 20):        # 19 test words + the jump back
        raise Refuse('+0x%x: jump target +0x%x outside the appended area' % (SITE, block))
    a = block; levels = []; ops = []
    for k in range(4):
        seq = [w(a), w(a + 4), w(a + 12)]
        if seq != [op(0x0e, UNIT_MEMBER), op(0x05), op(0x4f)] or (a + 8) not in it:
            raise Refuse('block test %d at +0x%x: %s' % (k + 1, a, ' '.join('%08x' % w(a + 4 * i) for i in range(4))))
        levels.append(cstr(d, it[a + 8]))
        ops += [0x0e, 0x05, None, 0x4f]
        a += 16
        if k:
            if w(a) != op(0x52):
                raise Refuse('block test %d: +0x%x is %08x, not op52 (or)' % (k + 1, a, w(a)))
            ops.append(0x52); a += 4
    j = w(a)
    if j >> 24 != 0x63 or a + 4 + 4 * s24(j) != TEST_END:
        raise Refuse('+0x%x: %08x is not the jump back to +0x%x' % (a, j, TEST_END))
    if w(TEST_END) != op(0x64, 9):
        raise Refuse('+0x%x: %08x is not the PC test jump op64 9' % (TEST_END, w(TEST_END)))
    if a + 4 != len(d):
        raise Refuse('%d bytes after the jump back (block must end the section)' % (len(d) - a - 4))
    return block, levels, ops


def tu_level_test(path):
    """the Xbox title update's level test in its generalbank script 134 (big-endian): the run of
    'push member, push string, op4f [, op52]' around the strings dlc_level4/5/6/2_start -> (levels in order, opcodes)"""
    X = DW.read(open(path, 'rb').read(), 'be')
    s = next((x for x in X.sections if x.type == 8 and x.id == 134), None)
    if s is None:
        raise Refuse('%s: no script 134' % path)
    d = s.data; it = dict(R.parse(s.reloc, 'be').internal)
    w = lambda a: struct.unpack_from('>I', d, a)[0]
    names = {x.encode('latin-1') + b'\0' for x in LEVELS}
    hits = sorted(a for a, t in it.items() if 0 <= t < len(d) and d[t:t + 17] in names and a >= 8
                  and w(a - 4) == op(0x05))
    # group consecutive tests (a test = 4 words, an op52 in between)
    runs = []
    for a in hits:
        if runs and a - runs[-1][-1] in (16, 20):
            runs[-1].append(a)
        else:
            runs.append([a])
    found = []
    for run in runs:
        levels = [cstr(d, it[a]) for a in run]
        if sorted(levels) != sorted(LEVELS):
            continue
        ops = []
        for k, a in enumerate(run):
            ops += [w(a - 8) >> 24, w(a - 4) >> 24, None, w(a + 4) >> 24]
            if k:
                ops.append(w(a + 8) >> 24)
        found.append((run[0] - 8, levels, ops))
    if len(found) != 1:
        raise Refuse('%s script 134: %d level tests with dlc_level4/5/6/2_start (expected 1)' % (path, len(found)))
    return found[0]


def verify(argv):
    """BEFORE AFTER [--tu TU_GENERALBANK_BE] [--report R.json]: AFTER must be BEFORE + exactly this fix - every other
    section and header byte-identical, every changed / appended word of script 104 explained by the plan from BEFORE,
    the appended relocations exactly the planned ones, the block decoded from AFTER by itself = the TU's test"""
    report = tu = None
    if '--report' in argv: k = argv.index('--report'); report = argv[k + 1]; del argv[k:k + 2]
    if '--tu' in argv: k = argv.index('--tu'); tu = argv[k + 1]; del argv[k:k + 2]
    if len(argv) != 2:
        sys.exit(__doc__)
    rb, ra = open(argv[0], 'rb').read(), open(argv[1], 'rb').read()
    B, A = DW.read(rb, 'le'), DW.read(ra, 'le')
    bad = []; rep = dict(before=argv[0], after=argv[1], md5_before=hashlib.md5(rb).hexdigest(),
                         md5_after=hashlib.md5(ra).hexdigest(), script=MISSION)
    for k in ('ver', 'names', 'pad', 'u0', 'u1'):
        if getattr(B, k) != getattr(A, k):
            bad.append('file header %s differs' % k)
    if len(B.sections) != len(A.sections):
        bad.append('section count %d -> %d' % (len(B.sections), len(A.sections)))
    idx = None; same = 0
    for i, (b, a) in enumerate(zip(B.sections, A.sections)):
        hdr = [k for k in ('type', 'id', 'flags', 'ver', 'spec', 'pad') if getattr(b, k) != getattr(a, k)]
        if hdr:
            bad.append('section %d (%d:%d): header %s differs' % (i, b.type, b.id, ', '.join(hdr)))
        elif b.type == 8 and b.id == MISSION and idx is None:
            idx = i
        elif b.data != a.data or b.reloc != a.reloc:
            bad.append('section %d (%d:%d): %s differs - unexplained' % (i, b.type, b.id,
                       'data' if b.data != a.data else 'relocations'))
        else:
            same += 1
    rep['sections'] = len(B.sections); rep['sections_identical'] = same
    words = []
    if idx is None:
        bad.append('no script %d' % MISSION)
    else:
        sb, sa = B.sections[idx], A.sections[idx]
        try:
            ed, er, info = plan_mission(sb, quiet=True)          # BEFORE: every PC word at the site checked
        except Refuse as e:
            bad.append('BEFORE: ' + str(e)); info = None
        if info:
            da = sa.data
            if len(da) != len(ed):
                bad.append('script %d: size %d -> %d, the plan gives %d' % (MISSION, len(sb.data), len(da), len(ed)))
            db = sb.data
            n = max(len(db), len(da))
            for off in range(0, n - n % 4, 4):
                old = struct.unpack_from('<I', db, off)[0] if off + 4 <= len(db) else None
                new = struct.unpack_from('<I', da, off)[0] if off + 4 <= len(da) else None
                if old == new and off not in info['words']:
                    continue
                exp = info['words'].get(off)
                if exp is None:
                    bad.append('script %d +0x%x: %s -> %s - unexplained word' % (MISSION, off,
                               '%08x' % old if old is not None else '-', '%08x' % new if new is not None else '-'))
                elif new != exp[1] or (exp[0] is not None and old != exp[0]):
                    bad.append('script %d +0x%x: %s -> %s, the plan says %s -> %08x (%s)' % (
                        MISSION, off, '%08x' % old if old is not None else '-', '%08x' % new if new is not None else '-',
                        '%08x' % exp[0] if exp[0] is not None else '-', exp[1], exp[2]))
                else:
                    words.append(dict(offset='0x%x' % off, old='%08x' % old if old is not None else None,
                                      new='%08x' % new, why=exp[2]))
            ra_, rb_ = R.parse(sa.reloc, 'le'), R.parse(sb.reloc, 'le')
            for k in ('external', 'idref_a', 'unk3', 'idref'):
                if getattr(ra_, k) != getattr(rb_, k):
                    bad.append('script %d relocations %s differ - unexplained' % (MISSION, k))
            n0 = len(rb_.internal)
            if ra_.internal[:n0] != rb_.internal:
                bad.append('script %d: existing internal relocations changed - unexplained' % MISSION)
            if ra_.internal[n0:] != info['relocs']:
                bad.append('script %d: appended relocations %s, the plan gives %s' % (
                    MISSION, ra_.internal[n0:], info['relocs']))
            rep['relocations_added'] = ['+0x%x -> +0x%x' % x for x in ra_.internal[n0:]]
            try:                                                # AFTER decoded by itself
                block, levels, ops = decode_fix(da, dict(ra_.internal))
                rep['block'] = '0x%x' % block; rep['levels'] = levels
                if levels != list(LEVELS):
                    bad.append('block tests %s, expected %s' % (levels, list(LEVELS)))
                if tu:
                    at, tl, tops = tu_level_test(tu)
                    rep['tu'] = dict(file=tu, script=134, at='0x%x' % at, levels=tl, ops=['%02x' % o if o is not None
                                                                                        else 'ptr' for o in tops])
                    if tl != levels or tops != ops:
                        bad.append('block %s / ops %s differ from the TU script 134 test at +0x%x: %s / %s' % (
                            levels, ops, at, tl, tops))
            except Refuse as e:
                bad.append('AFTER: ' + str(e))
    rep['words'] = words; rep['problems'] = bad; rep['result'] = 'ok' if not bad else 'REFUSED'
    for x in words:
        print('  +%s %s -> %s  %s' % (x['offset'], x['old'] or '--------', x['new'], x['why']))
    for x in bad:
        print('  PROBLEM: ' + x)
    print('verify script %d: %d words changed / appended, all explained: %s; %d of %d other sections identical; '
          'relocations added %d; block tests %s%s - %s' % (
              MISSION, len(words), 'yes' if not bad else 'no', same, max(len(B.sections) - 1, 0),
              len(rep.get('relocations_added', [])), ', '.join(rep.get('levels', [])) or '-',
              ('; TU script 134 test at +%s: same order and opcodes' % rep['tu']['at']) if 'tu' in rep and not bad
              else '', rep['result']))
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        json.dump(rep, open(report, 'w', encoding='utf-8'), indent=1)
    if bad:
        sys.exit(1)


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
    if not argv:
        sys.exit(__doc__)
    if argv[0] == 'gb':
        stub = '--stub-select0' in argv
        argv = [a for a in argv if a != '--stub-select0']
        if len(argv) != 3:
            sys.exit(__doc__)
        D = DW.read(open(argv[1], 'rb').read(), 'le')
        try:
            fix_mission(D)
        except Refuse as e:
            sys.exit(str(e))
        if stub:
            fix_stub(D)
        save(D, argv[2])
    elif argv[0] == 'verify':
        verify(argv[1:])
    elif argv[0] == 'ids':
        fix_ids(argv[1:])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
