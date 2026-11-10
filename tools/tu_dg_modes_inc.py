"""Generate the per-mode camera tables of the TU doppelganger settings DTP 21237 for the PC stand-in of TruShadowPower
([Camera] DoppelgangerSettings=2) FROM THE PLAYER'S OWN FILES - read-only on the game data, writes one text file and
the C++ include src/asi/TruShadowPower/TruShadowPower_dgmodes.local.inc (gitignored: the tables are converted title
update data, so the repository holds only this generator; owner decision 2026-11-10, night package Q26). Without the
include TruShadowPower builds without the 0.26 tables (the stand-in keeps 0.25's DTP 20 tables and logs why).
Origin: work/power026_1111/make_dg_modes.py (TruShadowPower 0.26, 2026-11-11), moved here unchanged in its rules; the
committed include of ceab0d5 was byte-identical to this tool's output (md5 0b607b6b..., checked 2026-11-11 Q26).
Inputs: TU generalbank (tools/dtp_word_classes.py BASE: the workspace TitleUpdate.000, or --tu PATH) and the PC
generalbank (patch.000 / bigfile.000).

Facts used (work/power026_1111/cam_mode_tables.txt, cam_set_records.txt; helpers tools/cam_mode_tables.py,
tools/cam_set_records.py):
  * table A (S+0x134 / S+0x138, 0x5f99f0 first hit) and table B (S+0x13c / S+0x140, 0x5f9960) of TU 21237 differ from
    the TU retail default DTP 21 (= PC DTP 20 by value for every mode) in the modes listed by MODES_DIFF below plus the
    table-B entry key 22 (modes 60..63);
  * kind 10 / 11 records name the set DTP 22194 (TU) by index; TU 31 (retail) == PC 30 at every index 0..75 (all
    non-pointer words), so an index of 22194 whose record equals TU 31 at that index maps to PC 30 at that index; other
    records (changed or new in 22194) are equal to some PC 30 record in every word except the seven floats 1..7 ->
    built at run time as a copy of that PC 30 record with the TU's seven floats (word 25, the only pointer, is the
    same shared end pointer in every record of a set DTP).
  * payload words of the other kinds are converted per (kind, word) the way the PC conversion did it for the retail
    records (TU 21 vs PC 20, same mode, same kind): 'num' = same number, 'raw' = same bytes (u8 fields), 'u16' = same
    halves; a (kind, word) with a non-zero TU value and no retail evidence stops the generator.

Output: the C++ table text for TruShadowPower.cpp (section "0.26 doppelganger mode tables") plus a self-check that
simulates 0x5f99f0 / 0x5f9960 on the ported table (new entries first, then PC 20's 25 entries) against TU 21237 for
modes 0..127.

Usage (from the repository root): ../bin/pyt -t 300 tools/tu_dg_modes_inc.py OUT.txt [INC] [--tu TITLEUPDATE000]
        OUT.txt = generator log + table text; INC default src/asi/TruShadowPower/TruShadowPower_dgmodes.local.inc
        (written only when both self-checks pass); then scripts/windows/Build-TruAsi.ps1 builds with the tables
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cam_mode_tables as M  # noqa: E402
import cam_set_records as SR  # noqa: E402

INC_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'asi', 'TruShadowPower',
                           'TruShadowPower_dgmodes.local.inc')


# (kind, payload word) -> form, from the PC reader when no retail record shows the word non-zero:
#   kind 13 (0x5ff20c): fld [rec+4] -> +0x1320, `cmp byte ptr [rec+0xc], 0` (0x5ff215) -> payload word 2 is a u8
CODE_RULES = {(13, 2): {'raw'}}


def bswap(x):
    return struct.unpack('<I', struct.pack('>I', x))[0]


def rot16(x):
    return ((x >> 16) | (x << 16)) & 0xffffffff


def words(pl, e):
    return list(struct.unpack(e + '5I', pl))


def first_hit(table, m):
    """0x5f99f0: first entry whose mode list holds m and whose record count is > 0"""
    return next((i for i, (modes, recs) in enumerate(table) if m in modes and recs), None)


def main(argv):
    if '--tu' in argv:
        k = argv.index('--tu'); M.C.BASE[:] = [argv[k + 1]]; del argv[k:k + 2]
    if not argv: sys.exit(__doc__)
    tu = M.decode('TU 21237', M.tu_dtp(21237), '>')
    pc = M.decode('PC 20', M.pc_dtp(20), '<')
    retail = M.decode('TU 21', M.tu_dtp(21), '>')
    t31 = SR.records(M.tu_dtp(31), '>')[0]
    p30 = SR.records(M.pc_dtp(30), '<')[0]
    s22194 = SR.records(M.tu_dtp(22194), '>')[0]
    log = []

    # conversion rule per (kind, word) from the retail pairs (TU 21 vs PC 20, same mode first hit, same kind order)
    rule = {}
    for m in range(128):
        a, b = first_hit(retail['A'], m), first_hit(pc['A'], m)
        if a is None or b is None:
            continue
        ra, rb = retail['A'][a][1], pc['A'][b][1]
        if len(ra) != len(rb):
            continue
        for (ka, pa, refa), (kb, pb, refb) in zip(ra, rb):
            if ka != kb or refa or refb:
                continue
            for k, (x, y) in enumerate(zip(words(pa, '>'), words(pb, '<'))):
                if x == 0 and y == 0:
                    continue
                forms = {f for f, v in (('num', x), ('raw', bswap(x)), ('u16', rot16(x))) if v == y}
                if not forms:
                    sys.exit('retail kind %d word %d: TU %08x PC %08x - no known conversion' % (ka, k, x, y))
                if x == y and bswap(x) == y:
                    continue                                   # symmetric, says nothing
                old = rule.get((ka, k))
                rule[(ka, k)] = forms if old is None else old & forms
                if not rule[(ka, k)]:
                    sys.exit('retail kind %d word %d: conflicting conversions' % (ka, k))
    log.append('conversion rules from retail pairs: ' + ', '.join(
        'kind %d w%d %s' % (k, w, '/'.join(sorted(f))) for (k, w), f in sorted(rule.items())))

    # conversion rule per set-record word from the 76 retail pairs TU 31[i] / PC 30[i]
    setrule = {}
    for (_, wa, rela), (_, wb, relb) in zip(t31, p30):
        for k, (x, y) in enumerate(zip(wa, wb)):
            if k in rela or k in relb or (x == 0 and y == 0):
                continue
            forms = {f for f, v in (('num', x), ('raw', bswap(x)), ('u16', rot16(x))) if v == y}
            if not forms:
                sys.exit('set word %d: TU %08x PC %08x - no known conversion' % (k, x, y))
            if len(forms) > 1 and x == y:
                continue
            old = setrule.get(k)
            setrule[k] = forms if old is None else old & forms
            if not setrule[k]:
                sys.exit('set word %d: conflicting conversions' % k)
    log.append('set record word rules from TU 31 / PC 30: ' + ', '.join(
        'w%d %s' % (k, '/'.join(sorted(f))) for k, f in sorted(setrule.items())))

    # modes whose TU 21237 first hit differs from PC 20 by value (cam_mode_tables.py's comparison)
    def val(table, side, i):
        if i is None:
            return None
        out = []
        for kind, pl, ref in table['A'][i][1]:
            e = '>' if side == 'TU' else '<'
            if ref:
                w = words(pl, e)
                recs = s22194 if side == 'TU' and ref[1] == 22194 else (t31 if side == 'TU' else p30)
                r = recs[w[1]][1] if w[1] < len(recs) else None
                out.append((kind, ('set', tuple(SR.canon(x) for x in r[1:8]) if r else None)))
            else:
                out.append((kind, tuple(min(x, bswap(x)) for x in words(pl, e))))
        return sorted(out, key=repr)
    diff_modes = [m for m in range(128) if val(tu, 'TU', first_hit(tu['A'], m)) != val(pc, 'PC', first_hit(pc['A'], m))]
    entries = sorted({first_hit(tu['A'], m) for m in diff_modes})
    log.append('modes whose TU 21237 table-A first hit differs from PC 20: %s -> TU entries %s' % (diff_modes, entries))
    for i in entries:
        other = [m for m in tu['A'][i][0] if m not in diff_modes]
        if other:
            sys.exit('TU entry %d also holds modes %s that are equal on the PC - a prepended copy would shadow them' % (
                i, other))

    # set references -> PC 30 index or a built record
    synth = []                                                 # (tu index, pc base index, 7 floats)
    setmap = {}

    def map_set(idx):
        if idx in setmap:
            return setmap[idx]
        o, w, rel = s22194[idx]
        if idx < len(t31) and all(SR.canon(x) == SR.canon(y) for k, (x, y) in enumerate(zip(w, t31[idx][1]))
                                  if k not in rel):
            setmap[idx] = ('pc', idx)
            return setmap[idx]
        if list(rel) != [25]:
            sys.exit('22194[%d]: pointer words %s (expected only word 25)' % (idx, list(rel)))
        pw = []
        for k, x in enumerate(w):
            if k == 25:
                pw.append(0)                                   # pointer: taken from PC 30 record 0 at run time
                continue
            forms = setrule.get(k)
            if x and forms is None:
                sys.exit('22194[%d] word %d: %08x - no conversion rule from the 76 retail pairs' % (idx, k, x))
            f = sorted(forms)[0] if forms else 'num'
            pw.append(x if f == 'num' else bswap(x) if f == 'raw' else rot16(x))
        synth.append((idx, pw, [struct.unpack('>f', struct.pack('>I', x))[0] for x in w[1:8]]))
        setmap[idx] = ('synth', len(synth) - 1)
        return setmap[idx]

    recs_out, modes_out, ent_out = [], [], []
    for i in entries:
        modes, recs = tu['A'][i]
        ent_out.append((len(modes_out), len(modes), len(recs_out), len(recs), i))
        modes_out.extend(modes)
        for kind, pl, ref in recs:
            w = words(pl, '>')
            if ref:
                if ref[1] != 22194:
                    sys.exit('entry %d kind %d names DTP %d' % (i, kind, ref[1]))
                where = map_set(w[1])
                if any(w[2:]):
                    sys.exit('entry %d kind %d: payload words 2.. not zero' % (i, kind))
                recs_out.append((kind, [0, w[1], 0, 0, 0], where, i))
                continue
            pw = []
            for k, x in enumerate(w):
                if x == 0:
                    pw.append(0)
                    continue
                forms = rule.get((kind, k)) or CODE_RULES.get((kind, k))
                if forms is None:
                    # no retail evidence: only plain float words are accepted (a value that reads as a finite float
                    # of plausible size); everything else stops the generator
                    f = struct.unpack('>f', struct.pack('>I', x))[0]
                    if (x & 0x7f800000) and (x & 0x7f800000) != 0x7f800000 and 1e-4 <= abs(f) <= 1e6:
                        log.append('entry %d kind %d word %d: %08x = float %.6g kept as a number (no retail evidence;'
                                   ' plausible float)' % (i, kind, k, x, f))
                        pw.append(x)
                        continue
                    sys.exit('entry %d kind %d word %d: %08x - no conversion rule' % (i, kind, k, x))
                f = sorted(forms)[0]
                pw.append(x if f == 'num' else bswap(x) if f == 'raw' else rot16(x))
            recs_out.append((kind, pw, None, i))
    bextra = [(key, modes) for key, modes in tu['B'] if (key, modes) not in pc['B']]
    log.append('table-B entries of TU 21237 not in PC 20: %s' % bextra)
    for idx, pw, fl in synth:
        log.append('set 22194[%d] -> built record (floats 1..7 %s)' % (idx, ' '.join('%.6g' % x for x in fl)))
    # self-check of the built records: converted back they must give the TU words (canonical), and for an index that
    # also exists in TU 31 the PC 30 words where TU 22194 == TU 31
    for idx, pw, fl in synth:
        w = s22194[idx][1]
        if any(SR.canon(a) != SR.canon(b) for k, (a, b) in enumerate(zip(w, pw)) if k != 25):
            sys.exit('built record 22194[%d] does not round-trip' % idx)
    log.append('set 22194 indices mapped to the same PC 30 index: %s' % sorted(k for k, v in setmap.items()
                                                                            if v[0] == 'pc'))

    # self-check: simulate 0x5f99f0 on [ported entries] + PC 20 table A, compare the first hit by value with TU 21237
    def ported_val(m):
        for n, (mo, nm, ro, nr, i) in enumerate(ent_out):
            if m in modes_out[mo:mo + nm] and nr:
                out = []
                for kind, pw, where, _ in recs_out[ro:ro + nr]:
                    if where:
                        r = p30[where[1]][1][1:8] if where[0] == 'pc' else None
                        if r is None:
                            r = synth[where[1]][1][1:8]
                        out.append((kind, ('set', tuple(SR.canon(x) for x in r))))
                    else:
                        out.append((kind, tuple(min(x, bswap(x)) for x in pw)))
                return sorted(out, key=repr)
        return val(pc, 'PC', first_hit(pc['A'], m))
    bad = [m for m in range(128) if ported_val(m) != val(tu, 'TU', first_hit(tu['A'], m))]
    allb = pc['B'] + bextra
    badb = [(key, m) for key in range(-128, 128) for m in range(128)
            if any(k == key and m in mo for k, mo in allb) != any(k == key and m in mo for k, mo in tu['B'])]
    log.append('SELF-CHECK table A (0x5f99f0 first hit by value, modes 0..127): %d mismatches %s' % (len(bad), bad))
    log.append('SELF-CHECK table B (0x5f9960 (key, mode) answers, keys -128..127, modes 0..127): %d mismatches' %
               len(badb))

    # C++ text
    cc = []
    cc.append('// generated by tools/tu_dg_modes_inc.py (TU generalbank DTP 21237 / 22194 vs PC DTP 20 / 30)')
    cc.append('const int kDgModeModes[] = {%s};' % ', '.join(str(m) for m in modes_out))
    cc.append('const DgModeEntry kDgModeEntries[] = {          // {first mode, modes, first record, records} = TU A[i]')
    for mo, nm, ro, nr, i in ent_out:
        cc.append('    {%d, %d, %d, %d},   // TU 21237 A[%d] modes %s' % (mo, nm, ro, nr, i, modes_out[mo:mo + nm]))
    cc.append('};')
    cc.append('const DgModeRec kDgModeRecs[] = {   // {kind, payload words (PC numbers), set: -1 none, 0..75 PC DTP 30 '
              'index, 0x100 + n built set n}')
    for kind, pw, where, i in recs_out:
        s = -1 if not where else (where[1] if where[0] == 'pc' else 0x100 + where[1])
        cc.append('    {%d, {0x%08x, 0x%08x, 0x%08x, 0x%08x, 0x%08x}, %s},   // A[%d] kind %d%s' % (
            kind, pw[0], pw[1], pw[2], pw[3], pw[4], '0x%x' % s if s >= 0x100 else str(s), i, kind,
            '' if not where else ' set 22194[%d]' % pw[1]))
    cc.append('};')
    cc.append('const DWORD kDgModeSets[][27] = {   // built set records (0x6c bytes, PC numbers; word 25 = the shared end '
              'pointer, copied from PC DTP 30 record 0 at run time)')
    for idx, pw, fl in synth:
        cc.append('    // 22194[%d]: floats 1..7 %s' % (idx, ' '.join('%.6g' % x for x in fl)))
        for row in range(3):
            part = ', '.join('0x%08x' % x for x in pw[9 * row:9 * row + 9])
            cc.append('    %s%s%s' % ('{' if row == 0 else ' ', part, '},' if row == 2 else ','))
    cc.append('};')
    for key, modes in bextra:
        cc.append('const int kDgBModes%d[] = {%s};   // TU 21237 table B key %d' % (key, ', '.join(map(str, modes)), key))
    out = '\n'.join(log) + '\n\n' + '\n'.join(cc) + '\n'
    open(argv[0], 'w', encoding='utf-8', newline='\r\n').write(out)
    if len(argv) < 2: argv = argv + [INC_DEFAULT]
    if not (bad or badb):
        head = ['// TruShadowPower 0.26: the per-mode camera tables of the TU doppelganger settings DTP 21237 for the stand-in',
                '// ([Camera] DoppelgangerSettings=2), included by TruShadowPower.cpp (section "0.26 doppelganger mode tables").',
                '// Generated from the player\'s own TitleUpdate.000 + PC patch.000 - never commit it (no game data in the',
                '// repository; .gitignore *.local.inc). Regenerate: ../bin/pyt -t 300 tools/tu_dg_modes_inc.py OUT.txt [INC].',
                '// Self-check of the generator: 0x5f99f0 first hit by value for modes 0..127 = TU 21237 (0 mismatches),',
                '// 0x5f9960 answers for every (key, mode) = TU 21237 (0 mismatches).']
        open(argv[1], 'w', encoding='ascii', newline='\r\n').write('\n'.join(head + cc) + '\n')
    print(out)
    if bad or badb:
        sys.exit(1)


if __name__ == '__main__':
    main(sys.argv[1:])
