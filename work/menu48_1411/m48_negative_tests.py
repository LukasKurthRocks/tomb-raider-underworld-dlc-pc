"""0.22.48 (2026-11-14): negative tests of trumenu_ini_check.check_02248 - each case breaks one rule in a copy of
TruMenu.cpp (read_cpp is replaced in memory) or of TruMenu.switches.txt (a mutated copy next to this script, removed
again) and must yield at least one problem; the unchanged sources none. Every pattern must occur exactly once (else the
case counts as failed).

Usage (from the repository root):
  ../bin/pyt -t 300 work/menu48_1411/m48_negative_tests.py
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import trumenu_ini_check as T

SRC = T.read_cpp()
SW = T.SWITCHES
SW_TEXT = open(SW, encoding='utf-8').read()
CPP_CASES = [
    ('version', 'const char *const kVersion = "TruMenu 0.22.48 (adrenaline at Lara + sonar full map,',
     'const char *const kVersion = "TruMenu 0.22.48 (adrenaline at Lara,'),
    ('check row changed', '{0x006e3b1b, "8b0dbc03ee00 2403 3c01 0f94c3', '{0x006e3b1b, "8b0dbc03ee00 2403 3c01 0f94c2'),
    ('check row dropped', '    {0x006e55f0, "a1c803ee00 83c0ff 83f803 773a ff248538566e00"},\n', ''),
    ('SoCheck table', 'g_soOk = DvChecks(kSoChecks,', 'g_soOk = true || DvChecks(kSoChecks,'),
    ('load order', '    SoCheck();                                // 0.22.48', '    // SoCheck();                             // 0.22.48'),
    ('options order', '    SoReadOptions(ini);  ', '    // SoReadOptions(ini);'),
    ('PadHook tick', '    SoTick();                                 // 0.22.48', '    // SoTick();                              // 0.22.48'),
    ('site bytes', 'kSoC2New[5] = {0xc6, 0x44, 0x24, 0x11, 0x01}', 'kSoC2New[5] = {0xc6, 0x44, 0x24, 0x11, 0x00}'),
    ('site address', 'kSoC4 = 0x006e40c6', 'kSoC4 = 0x006e40c8'),
    ('game bytes', 'kSoH3Game[5] = {0x8b, 0x41, 0x44, 0x85, 0xc0}', 'kSoH3Game[5] = {0x8b, 0x41, 0x48, 0x85, 0xc0}'),
    ('stub vertex test', '        cmp dword ptr [ecx + 0x48], 56\n', ''),
    ('stub register', '        xor eax, eax\n    so_keep:', '        xor eax, eax\n        push edx\n        pop edx\n    so_keep:'),
    ('stub call', 'g_soH3New[0] = 0xe8;', 'g_soH3New[0] = 0xe9;'),
    ('filter without full', 'wantH = wantC && g_soHide != 0,', 'wantH = g_soHide != 0,'),
    ('markers without full', 'wantM = wantC && g_soMarkers != 0;', 'wantM = g_soMarkers != 0;'),
    ('no read back', '&& WriteBytes(at, to, len) && SoBytesAre(at, to, len);', '&& WriteBytes(at, to, len);'),
    ('cap tick writes', '    ++g_soCapHits;\n', '    ++g_soCapHits;\n    WriteBytes(kSoTriRefused, &drawn, 4);\n'),
    ('option A site', '    ReadDword(kSoMode, &mode);\n    Out(o, n, "full', '    ReadDword(0x006deed5, &mode);\n    Out(o, n, "full'),
    ('tick read rate', 'if (now - g_soReadTick >= 1000) { g_soReadTick = now; SoReadSwitch(); }',
     'if (now - g_soReadTick >= 100) { g_soReadTick = now; SoReadSwitch(); }'),
    ('read key', 'GetPrivateProfileIntA("Sonar", "FloorMarkers"', 'GetPrivateProfileIntA("Sonar", "FloorMarker"'),
    ('not kept', '    IniKeepInt("Sonar", key, on ? 1 : 0);', '    // kept'),
    ('item thread', 'HidePlaceholder, kept", true, ValSoHide, RunSoHide},', 'HidePlaceholder, kept", false, ValSoHide, RunSoHide},'),
    ('item help', '{"sonar.markers", "", "', '{"sonar.markerz", "", "'),
    ('key default', '{"Sonar", "HidePlaceholder", "1", ', '{"Sonar", "HidePlaceholder", "0", '),
    ('settings row', '"sonar.markers", "", kQbBool, -1, kQcNone, 0,\n     kQbBlue, 0},',
     '"sonar.full", "", kQbBool, -1, kQcNone, 0,\n     kQbBlue, 0},'),
    ('Lara switch row', '"TruShadowCombat:Adrenaline:DrainModePercent", kQbSwitch',
     '"TruShadowCombat:Adrenaline:DrainPercent", kQbSwitch'),
    ('Lara conditions row', '"TruShadowCombat:Conditions:Enabled", kQbSwitch', '"TruShadowCombat:States:Enabled", kQbSwitch'),
    ('Lara note', '"Ohne X / ohne volle Leiste: braucht [Conditions] Enabled=1"', '"Ohne X / ohne volle Leiste: Bedingungen an"'),
    ('Lara group key', '"Adrenaline (Lara)", "-", "fig_adren", kQbGroup', '"Adrenaline (Lara)", "-", "fig_adrenalin", kQbGroup'),
    ('Tests own source', '"TruShadowCombat:Adrenaline:StrikeWithoutFullMeter", kQbSwitch, -1, kQcNone, 0, 0, kQfTg}',
     '"TruShadowCombat:Adrenaline:Log2", kQbSwitch, -1, kQcNone, 0, 0, kQfTg}'),
    ('Paket A copy', '"TruShadowCombat:Adrenaline:ModeWithoutTarget", kQbSwitch, -1, kQcNone, 0, 0, kQfTg}',
     '"TruMenu:Input:DeviceGlyphs", kQbSwitch, -1, kQcNone, 0, 0, kQfTg}'),
    ('17p string', 'de ? "nie gebaut" : "never built")', 'de ? "nie gebaut (17p)" : "never built")'),
]
SW_CASES = [
    ('switch restart', 'TruShadowCombat | Adrenaline | ModeWithoutTarget | bool | Adrenalin-Modus ohne Ziel (Test) | '
                       'Adrenaline mode without target (test) | live |',
     'TruShadowCombat | Adrenaline | ModeWithoutTarget | bool | Adrenalin-Modus ohne Ziel (Test) | '
     'Adrenaline mode without target (test) | restart |'),
    ('hint without Conditions', 'Schlag ohne X; braucht [Conditions] Enabled=1 // Strike without X; needs [Conditions] Enabled=1',
     'Schlag ohne X // Strike without X'),
    ('sonar row restart', 'Full sonar map | live | 0 |', 'Full sonar map | restart | 0 |'),
    ('sonar default', 'Full map: hide the MAP placeholder | live | 1 |', 'Full map: hide the MAP placeholder | live | 0 |'),
    ('sonar group', 'group | tmsonar | ', 'group | tmsonarx | '),
]


def main():
    bad = 0
    T.read_cpp = lambda: SRC
    p, _ = T.check_02248(SW)
    print('positive (unchanged sources): %d problem(s) %s' % (len(p), 'ok' if not p else 'FAIL ' + '; '.join(p)))
    bad += 1 if p else 0
    for name, old, new in CPP_CASES:
        if SRC.count(old) != 1:
            print('case %-24s: pattern found %d times (need 1) - FAIL' % (name, SRC.count(old))); bad += 1; continue
        mutated = SRC.replace(old, new, 1)
        T.read_cpp = lambda m=mutated: m
        p, _ = T.check_02248(SW)
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-24s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    T.read_cpp = lambda: SRC
    copy = os.path.join(HERE, 'm48_switches_mutated.txt')
    for name, old, new in SW_CASES:
        if SW_TEXT.count(old) != 1:
            print('case %-24s: pattern found %d times (need 1) - FAIL' % (name, SW_TEXT.count(old))); bad += 1; continue
        with open(copy, 'w', encoding='utf-8', newline='') as f:
            f.write(SW_TEXT.replace(old, new, 1))
        p, _ = T.check_02248(copy)
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-24s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    if os.path.exists(copy): os.remove(copy)
    print('%d cases + 1 positive, %d failed' % (len(CPP_CASES) + len(SW_CASES), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
