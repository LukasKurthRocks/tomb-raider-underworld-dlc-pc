"""Arena from the main menu (2026-11-14, TruMenu 0.22.46): negative tests of trumenu_ini_check.check_02246 - each case
breaks one rule in a copy of TruMenu.cpp (read_cpp is replaced in memory, no file is written) and must yield at least
one problem; the unchanged source none. Every pattern must occur exactly once in the source (else the case counts as
failed).

Usage (from the repository root):
  ../bin/pyt -t 300 work/arena_1411/arena_negative_tests.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import trumenu_ini_check as T

SRC = T.read_cpp()
CASES = [
    ('version', 'const char *const kVersion = "TruMenu 0.22.46 (arena from the main menu',
     'const char *const kVersion = "TruMenu 0.22.46 (arena from the menu'),
    ('check row changed', '{0x005de864, "381d41f1e700 7406 881d41f1e700"}', '{0x005de864, "381d41f1e700 7406 881d41f1e701"}'),
    ('check row dropped', '    {0x005e0180, "4f015e00"},', ''),
    ('FeCheck order', '    FeCheck();                                // 0.22.46', '    // FeCheck();                             // 0.22.46'),
    ('FeCheck no pending', 'g_feOk = g_mainStateOk && g_pendingOk;', 'g_feOk = g_mainStateOk;'),
    ('stale any state', 'return g_feOk && g_mainStateOk && ReadDword(kMainState, &state) && state == 10;',
     'return g_feOk && g_mainStateOk && ReadDword(kMainState, &state);'),
    ('front end 1', 'return g_feOk && g_mainStateOk && ReadDword(kMainState, state) && (*state == 6 || *state == 10);',
     'return g_feOk && g_mainStateOk && ReadDword(kMainState, state) && (*state == 6 || *state == 1);'),
    ('pending ignores b9', 'if (((busy >> 8) & 0xff) && !FeStaleRequest()) {', 'if (false) {'),
    ('load not refused', '    if (FeInFrontEnd(&feState)) {\n        Out(o, n, "refused: front end',
     '    if (false) {\n        Out(o, n, "refused: front end'),
    ('select ignored', 'int select = given >= 0 ? given : MissionSelectArg(unit);', 'int select = MissionSelectArg(unit);'),
    ('select 0 unchecked', 'if (given == 0 && !g_outfitRuleOk) {', 'if (false) {'),
    ('select any word', 'if (words > 2 || (words == 2 && given < 0) || !StartUnitName(first, name, sizeof(name))) {',
     'if (!StartUnitName(first, name, sizeof(name))) {'),
    ('runner no unit', '                             static_cast<unsigned>(sizeof(s2))) == 2 && !StartUnitName(u, g_scWaitUnit, sizeof(g_scWaitUnit)))',
     '                             static_cast<unsigned>(sizeof(s2))) == 2 && !StartUnitName(u, s2, sizeof(s2)))'),
    ('runner no log', '"shortcut \'%s\': level up - unit %s, player present', '"shortcut \'%s\': level ok - unit %s, player present'),
    ('menu branch late', '    if (stateOk && state == 10) return ArenaGoMenu(a, o, n);\n', ''),
    ('no level allowed', '    if (!InLevel()) {\n        Out(o, n, "refused: no level to start from',
     '    if (false) {\n        Out(o, n, "refused: no level to start from'),
    ('cutscene allowed', '    if (CinematicNow()) {                    // 0.22.46', '    if (false) {                    // 0.22.46'),
    ('in-level steps', '"save.backup kapitel;%s %s;wait.unit %s;cheat.flight 1;player.goto %ld force;arena.mode %s"',
     '"save.backup kapitel;%s %s;wait.unit %s;cheat.flight 1;player.goto %ld;arena.mode %s"'),
    ('menu steps load', '"save.backup kapitel;level.start %s 0;wait.unit %s;', '"save.backup kapitel;level.load %s;wait.unit %s;'),
    ('menu select 1', '"save.backup kapitel;level.start %s 0;wait.unit %s;', '"save.backup kapitel;level.start %s 1;wait.unit %s;'),
    ('menu no ohk', 'ohk ? "cheat.onehitkill 0;" : ""', 'ohk ? "" : ""'),
    ('ohk without gate', 'const bool ohk = g_cheatsEnabled && g_ohkOk;', 'const bool ohk = true;'),
    ('menu no gates', 'if (!g_feOk || !g_missionOk || !g_experimental) {\n        Out(o, n, "refused: main menu',
     'if (!g_feOk) {\n        Out(o, n, "refused: main menu'),
    ('menu any fe state', '    if (fe != 3) {', '    if (fe == 0xff) {'),
    ('menu movie ok', 'movie && ReadByte(kW3BinkLoop, &loop) && !loop', 'movie && ReadByte(kW3BinkLoop, &loop) && loop'),
    ('menu writes', '    ReadByte(kGameTracker + 0xb9, &stale);', '    ReadByte(kGameTracker + 0xb9, &stale);\n    PutByte(kGameTracker + 0xb9, 0);'),
    ('mode no ohk', 'one-hit kill byte 0x%08lx = %d%s', 'one-hit kill 0x%08lx = %d%s'),
    ('Paket A note', '{"Hauptmenue oder Hauptspiel; One-Hit-Kill geht aus"', '{"Aus dem Hauptspiel; One-Hit-Kill geht aus"'),
]


def main():
    bad = 0
    T.read_cpp = lambda: SRC
    p, _ = T.check_02246()
    print('positive (unchanged source): %d problem(s) %s' % (len(p), 'ok' if not p else 'FAIL ' + '; '.join(p)))
    bad += 1 if p else 0
    for name, old, new in CASES:
        if SRC.count(old) != 1:
            print('case %-20s: pattern found %d times (need 1) - FAIL' % (name, SRC.count(old))); bad += 1; continue
        mutated = SRC.replace(old, new, 1)
        T.read_cpp = lambda m=mutated: m
        p, _ = T.check_02246()
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-20s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    print('%d cases + 1 positive, %d failed' % (len(CASES), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
