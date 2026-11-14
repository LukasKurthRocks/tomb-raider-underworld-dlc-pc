"""W2 (2026-11-14): negative tests of trumenu_ini_check.check_02244 - each case breaks one rule in a copy of TruMenu.cpp
(read_cpp is replaced in memory) or of README.md / Set-TruMenu.ps1 / TruMenu.switches.txt (the module's open is
replaced for that one path); no file is written. Each case must yield at least one problem, the unchanged sources none.

Usage (from the repository root):
  ../bin/pyt -t 300 work/w2_1411/w2_negative_tests.py
"""
import builtins
import io
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import trumenu_ini_check as T

SRC = T.read_cpp()
CASES = [
    ('version', '"TruMenu 0.22.44 (W2 order', '"TruMenu 0.22.44 (W2 ordr'),
    ('no TG block', '// ---- TG 1411 begin', '// ---- TG 1411 bgn'),
    ('TG not first', '    // ---- TG 1411 begin',
     '    {"Teleport", "Teleport", "-", "ts_x", kQbGroup, -1, kQcNone, 0, kQbPlayer, 0},\n    // ---- TG 1411 begin'),
    ('row without kQfTg', '"adren.fill", "", kQbAction, -1, kQcNone, 0, kQbCheat, kQfTg}',
     '"adren.fill", "", kQbAction, -1, kQcNone, 0, kQbCheat, 0}'),
    ('kQfTg outside', '"ts_teleport", kQbGroup, -1, kQcNone, 0, kQbPlayer, 0}',
     '"ts_teleport", kQbGroup, -1, kQcNone, 0, kQbPlayer, kQfTg}'),
    ('enum value', 'kQfTg = 32 };', 'kQfTg = 64 };'),
    ('A lacks adren.keep',
     '    {"Adrenalin voll halten", "Keep adrenaline full", "adren.keep", "", kQbBool, -1, kQcNone, 0, kQbCheat, kQfTg},\n', ''),
    ('B lacks snd.dump', '"snd.dump", "", kQbAction, -1, kQcNone, 0, kQbSound,\n     kQfTg}',
     '"snd.list", "", kQbAction, -1, kQcNone, 0, kQbSound,\n     kQfTg}'),
    ('check of other pkg', '"tgB.wave10"', '"tgA.wave10"'),
    ('check id twice', '"tgF.pillar"', '"tgF.spiders"'),
    ('check id form', '"tgD.near"', '"tpD.near"'),
    ('not closed', '"tg_d", "tg_e"', '"tg_e"'),
    ('label not guide', '"Paket D: Debug-Ansicht", "Package D', '"Paket D: Debug", "Package D'),
    ('group key', '"Package E: markup / pillar / water (old tree)", "-", "tg_e"',
     '"Package E: markup / pillar / water (old tree)", "-", "tg_g"'),
    ('note with arg', '"Any time; F11 = shot + mark", "-", ""', '"Any time; F11 = shot + mark", "-", "x"'),
    ('switch unknown', '"TruMenu:Input:DeviceGlyphs", kQbSwitch, -1,\n     kQcNone, 0, 0, kQfTg}',
     '"TruMenu:Input:DeviceGlyphz", kQbSwitch, -1,\n     kQcNone, 0, 0, kQfTg}'),
    ('no archive', '"ts_archive", kQbGroup', '"ts_archiv2", kQbGroup'),
    ('archive sub level', '"ts_spots", kQbGroup, -1, kQcNone, 0, kQbRed, kQfSub}',
     '"ts_spots", kQbGroup, -1, kQcNone, 0, kQbRed, 0}'),
    ('archive not closed', '"ts_archive", "acc_planned"}', '"acc_planned"}'),
    ('old row lost', '"fix.hall02", "", kQbAction', '"fix.hall03", "", kQbAction'),
    ('QbTestsRows tg', '(!strncmp(t.id, "tp", 2) || !strncmp(t.id, "tg", 2))', '(!strncmp(t.id, "tp", 2))'),
    ('tag 1411', '!_strnicmp(r.arg, "tg", 2) ? "1411" : "Q90"', '!_strnicmp(r.arg, "tp", 2) ? "1411" : "Q90"'),
    ('kQbViewMax', 'const int kQbViewMax = 256;', 'const int kQbViewMax = 192;'),
    ('page too long', '    // ---- TG 1411 end\n', '    // ---- TG 1411 end\n' +
     '    {"Teleport", "Teleport", "-", "", kQbNote, -1, kQcNone, 0, kQbGrey, 0},\n' * 20),
    ('access space', '{"Spinnen-Modell aus", "Spider model off"', '{"  Spinnen-Modell aus", "  Spider model off"'),
    ('planned outside', '    {"Gott voll (Hilfe)", "Full god mode (assist)"',
     '    {"Reaktions-Momente", "Reaction moments", "-", "a|b", kQbPlanned, -1, kQcNone, 0, 0, 0},\n'
     '    {"Gott voll (Hilfe)", "Full god mode (assist)"'),
    ('planned not closed', '"ts_archive", "acc_planned"}', '"ts_archive"}'),
    ('arachno not sub', '"acc_arachno", kQbGroup, -1, kQcNone, 0, kQbPhobia, kQfSub}',
     '"acc_arachno", kQbGroup, -1, kQcNone, 0, kQbPhobia, 0}'),
    ('planned prefix', 'label ? "-- " : "", de ? r.de : r.en);', 'label ? "-- " : "   ", de ? r.de : r.en);'),
    ('old INI rule gone', 'if (g_menuOldIni) g_menuWindow = 0;', 'if (g_menuOldIni) {}'),
    ('old INI unloads', 'if (g_menuOldIni) g_menuWindow = 0;',
     'if (g_menuOldIni) { g_enabled = g_menuWindow; g_menuWindow = 0; }'),
    ('probe key', '("Menu", "Load", "", probe', '("Menu", "Enabled", "", probe'),
    ('start line', 'TruMenu.ini has no [Menu] Load (written before 0.22.18)', 'TruMenu.ini is old'),
    ('toggle reason', 'g_menuOldIni ? "TruMenu.ini without [Menu] Load', 'false ? "TruMenu.ini without [Menu] Load'),
    ('glyph row gone', '"TruMenu:Input:DeviceGlyphs", kQbSwitch, -1, kQcNone, 0, 0, 0}',
     '"TruMenu:Input:DeviceGlyph", kQbSwitch, -1, kQcNone, 0, 0, 0}'),
]
README = os.path.normcase(os.path.abspath(os.path.join(T.ROOT, 'src', 'asi', 'TruMenu', 'README.md')))
PS1 = os.path.normcase(os.path.abspath(os.path.join(T.ROOT, 'scripts', 'windows', 'Set-TruMenu.ps1')))
SWITCHES = os.path.normcase(os.path.abspath(T.SWITCHES))
FILE_CASES = [
    ('README TO TEST', README, '\n### TO TEST 0.22.44', '\n### TO TST 0.22.44'),
    ('PS1 hash', PS1, T.W2_HASH_02243, '0' * 64),
    ('switches row', SWITCHES, 'TruMenu | Input | DeviceGlyphs |', 'TruMenu | Input | DeviceGlyphz |'),
]


def patched_open(path, old, new):
    real = builtins.open

    def fake(p, *a, **k):
        if os.path.normcase(os.path.abspath(p)) == path:
            enc = k.get('encoding', 'utf-8')
            return io.StringIO(real(p, *a, **k).read().replace(old, new, 1)) if enc else real(p, *a, **k)
        return real(p, *a, **k)
    return fake


def main():
    bad = 0
    T.read_cpp = lambda: SRC
    p, summary = T.check_02244(T.SWITCHES)
    print('positive (unchanged sources): %d problem(s) %s' % (len(p), 'ok' if not p else 'FAIL ' + '; '.join(p)))
    print('  %s' % summary)
    bad += 1 if p else 0
    for name, old, new in CASES:
        if SRC.count(old) < 1:
            print('case %-20s: pattern not found - FAIL' % name); bad += 1; continue
        mutated = SRC.replace(old, new, 1)
        T.read_cpp = lambda m=mutated: m
        p, _ = T.check_02244(T.SWITCHES)
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-20s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    T.read_cpp = lambda: SRC
    for name, path, old, new in FILE_CASES:
        if old not in builtins.open(path, encoding='utf-8-sig').read():
            print('case %-20s: pattern not found - FAIL' % name); bad += 1; continue
        T.open = patched_open(path, old, new)
        try:
            p, _ = T.check_02244(T.SWITCHES)
        finally:
            del T.open
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-20s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    n = len(CASES) + len(FILE_CASES)
    print('%d cases + 1 positive, %d failed' % (n, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
