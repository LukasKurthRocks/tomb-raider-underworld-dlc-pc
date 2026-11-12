"""TruMenu 0.22.31 (build work/asi/menu0254, group B 2026-11-12): checks of the Q105 / Q106 parts (read-only).

  1. bytes   every kJtChecks row of TruMenu.cpp against the PC tru.exe (file offsets via the PE sections)
  2. table   the base-game rows of kChapOrder = work/b_nav_1211/q105_chaporder_rows.txt (the proven generator output)
  3. names   kUnitsNoArchive + kUnitsNoData = the 15 names with loadable_pc = NO of work/q97_q105_1111/q105_units.tsv
  4. source  version line, joint.set item (game thread) + danger row, JtTick in PadHook, JtCheck after UberCheck,
             cp.jump force form, the dlc rows of kChapOrder unchanged (0.21.9 form), QbPzRows in QbChapRows
Exit code 0 = all ok, 1 = a problem (each printed).

Usage (from trudlcport): ../bin/pyt -t 120 work/b_nav_1211/check_0254.py [TRU.EXE] [--cpp FILE]
"""
import sys, os, re, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import pe_callers as PE

EXE = os.path.join(ROOT, '..', 'data', 'pc', 'tru.exe')   # the workspace copy of the PC exe (= the installed one)


def va_bytes(exe, secs, va, n):
    for s in secs:
        sva, rptr, size = s[1], s[2], s[3]
        if sva <= va < sva + size: return exe[rptr + va - sva:rptr + va - sva + n]
    return None


def main(argv):
    exe_path, cpp = EXE, os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.cpp')
    args = list(argv)
    if '--cpp' in args:
        i = args.index('--cpp'); cpp = args[i + 1]; del args[i:i + 2]
    if args: exe_path = args[0]
    src = open(cpp, encoding='utf-8').read()
    exe = open(exe_path, 'rb').read()
    secs = PE.sections(exe)[1]
    problems = []
    # 1. bytes
    block = src[src.index('const NavCheckBytes kJtChecks[] = {'):]
    block = block[:block.index('\n};')]
    rows = re.findall(r'\{0x([0-9a-fA-F]{8}),\s*((?:"[^"]*"\s*)+)\}', block)
    for at, lits in rows:
        hexs = ''.join(re.findall(r'"([^"]*)"', lits)).replace(' ', '')
        want = bytes.fromhex(hexs)
        have = va_bytes(exe, secs, int(at, 16), len(want))
        if have != want: problems.append('bytes 0x%s: want %s have %s' % (at, want.hex(), have.hex() if have else None))
    print('bytes: %d kJtChecks rows checked against %s' % (len(rows), exe_path))
    if len(rows) != 27: problems.append('kJtChecks has %d rows (0.22.31: 27)' % len(rows))
    if '27 byte checks' not in src[:src.index('\n', src.index('kVersion = '))]:
        problems.append('kVersion must say "27 byte checks"')
    # 2. table
    order = src[src.index('const ChapOrder kChapOrder[] = {'):]
    order = order[:order.index('\n};')]
    have_rows = re.findall(r'\{"(Base game l\d)", "(\w+)", false, "([0-9 ]*)",\s*((?:"[^"]*"\s*)+|nullptr)\}', order)
    have = [(g, u, c, ''.join(re.findall(r'"([^"]*)"', h)) if h != 'nullptr' else None) for g, u, c, h in have_rows]
    want = []
    for line in open(os.path.join(HERE, 'q105_chaporder_rows.txt'), encoding='utf-8'):
        m = re.match(r'\s*\{"(Base game l\d)", "(\w+)", false, "([0-9 ]*)", (?:"(.*)"|nullptr)\},$', line.rstrip())
        if m: want.append((m.group(1), m.group(2), m.group(3), m.group(4)))
    if have != want:
        for i in range(max(len(have), len(want))):
            a = have[i] if i < len(have) else None
            b = want[i] if i < len(want) else None
            if a != b: problems.append('kChapOrder base row %d: source %s, generator %s' % (i, a, b)); break
    print('table: %d base rows in kChapOrder, %d in q105_chaporder_rows.txt' % (len(have), len(want)))
    dlc = re.findall(r'\{"DLC [12]", "\w+", (?:true|false), "[0-9 ]*"\}', order)   # one-line rows (machine_room spans two)
    if len(dlc) != 22: problems.append('kChapOrder DLC rows: %d (0.21.9: 22 one-line rows, without a head)' % len(dlc))
    # 3. names
    tsv = os.path.join(ROOT, 'work', 'q97_q105_1111', 'q105_units.tsv')
    no = sorted({l.split('\t')[1] for l in open(tsv, encoding='utf-8').read().splitlines()[1:] if l.split('\t')[3] == 'NO'})
    def names(var):
        b = src[src.index('const char *const %s[] = {' % var):]
        return re.findall(r'"(\w+)"', b[:b.index('};')])
    got = sorted(names('kUnitsNoArchive') + names('kUnitsNoData'))
    if got != no: problems.append('names: kUnitsNoArchive + kUnitsNoData %s != TSV %s' % (got, no))
    print('names: %d not-loadable names in the TSV, %d in the source tables' % (len(no), len(got)))
    # 4. source
    ver = src[src.index('kVersion = '):src.index('\n', src.index('kVersion = '))]
    for part in ('"TruMenu 0.22.31 (level navigation + puzzles, group B', '0.22.30 (log dates, device glyphs, drawn guards'):
        if part not in ver: problems.append('kVersion lacks %s' % part)
    for s, why in (('{"joint.set", "action", "0.22.31 <intro> <joint index> <value>|stop', 'joint.set item'),
                   ('node (solved) or 6 s; uber.dump / page Kapitel group Raetsel list them", true, ValJointSet', 'joint.set on the game thread'),
                   ('{"joint.set", "R\\303\\244tsel-Cheat (bewegt ein Gelenk)"', 'joint.set danger row'),
                   ('        JtTick();                             // 0.22.31', 'JtTick in PadHook'),
                   ('    UberCheck();                              // 0.21.7 uber labels (precheck_0217.txt)\n    JtCheck();', 'JtCheck after UberCheck'),
                   ('"save.backup kapitel;unit.go %s;wait.unit %s;cheat.flight 1;player.goto %ld force"', 'cp.jump force steps'),
                   ('"save.backup kapitel;unit.go %s;wait.unit %s;dbg.cpgo %ld"', 'cp.jump 0.21.9 steps'),
                   ('n += QbPzRows(v, d, max, de);', 'QbPzRows in QbChapRows'),
                   ('if (UnitNameNoDrm(unit)) { UnitRefusal(unit, o, n); return false; }   // 0.22.31 (Q105)', 'unit.go refusal'),
                   ('if (cand[i].state) JtDumpLines(cand[i].state, name, static_cast<LONG>(intro));', 'uber.dump joint lines'),
                   ('case kQdPz:', 'QbSpecialAct kQdPz')):
        if s not in src: problems.append('source: %s missing' % why)
    pad = src[src.index('DWORD WINAPI PadHook') if 'DWORD WINAPI PadHook' in src else 0:]
    print('source: %d rules' % 11)
    for p in problems: print('PROBLEM ' + p)
    print('check_0254: %s' % ('ok' if not problems else '%d problem(s)' % len(problems)))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
