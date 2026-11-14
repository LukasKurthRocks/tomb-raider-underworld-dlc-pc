"""0.22.47 (2026-11-14): negative tests of trumenu_ini_check.check_02247 - each case breaks one rule in a copy of
TruMenu.cpp (read_cpp is replaced in memory, no file is written) and must yield at least one problem; the unchanged
source none. Every pattern must occur exactly once in the source (else the case counts as failed).

Usage (from the repository root):
  ../bin/pyt -t 300 work/sndui_1411/w7_negative_tests.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import trumenu_ini_check as T

SRC = T.read_cpp()
SW = T.SWITCHES
CASES = [
    ('version', 'const char *const kVersion = "TruMenu 0.22.47 (sound monitor,',
     'const char *const kVersion = "TruMenu 0.22.47 (sound monitr,'),
    ('check row changed', '{0x0059133f, "8b4b04 50 e89812ffff 8b5b04', '{0x0059133f, "8b4b04 50 e89812ffff 8b5b05'),
    ('check row dropped', '    {0x0059079b, "c21400"},', ''),
    ('W7Check table', 'g_w7Ok = g_w6Ok && DvChecks(kW7Checks,', 'g_w7Ok = DvChecks(kW7Checks,'),
    ('load order', '    W7Check();                                // 0.22.47', '    // W7Check();                             // 0.22.47'),
    ('options order', '    W7ReadOptions(ini, dir);', '    // W7ReadOptions(ini, dir);'),
    ('SnBuild old wave', '            v.wave = W7Wave(v.sample);\n            SnClassify(',
     '            v.wave = static_cast<int>((v.sample - 0) / 0x18);\n            SnClassify('),
    ('W6VoiceTick old emitter', '            v.emitter = W7Emitter(v.params);   // 0.22.47: voice +0x1c',
     '            v.emitter = W6Emitter(v.params);   // 0.22.47: voice +0x1c'),
    ('map entry +4', 'ReadDword(entry + 4, &sample)', 'ReadDword(entry + 8, &sample)'),
    ('map loaded test', 'ReadDword(entry, &loaded) || !loaded', 'ReadDword(entry, &loaded)'),
    ('emitter +0x74', 'ReadDword(p + 0x74, &up)', 'ReadDword(p + 0x70, &up)'),
    ('emitter depth', 'p >= 0x10000 && depth < 4; ++depth', 'p >= 0x10000 && depth < 40; ++depth'),
    ('sonar want', '            if (!want && sonar && W7SonarWave(v.wave)) want = true;', '            // sonar'),
    ('sonar group', 'if (W7SonarMode() == 2 && wn < kW6CgMax) want[wn++] = kW7SonarGroup;',
     'if (W7SonarMode() && wn < kW6CgMax) want[wn++] = kW7SonarGroup;'),
    ('sonar group id', 'const int kW7SonarGroup = 57;', 'const int kW7SonarGroup = 53;'),
    ('sonar waves default', 'int g_w7SonarWaves[8] = {914, 915, 916,', 'int g_w7SonarWaves[8] = {914, 915, 917,'),
    ('sonar not kept', '    IniKeepInt("Sound", "SonarMute", mode);', '    // kept'),
    ('style not kept', '    IniKeepInt("Sound", "OverlayStyle", g_w7Style);', '    // kept'),
    ('log overlay', '    if (g_w7Style == 1) { DrawSoundLog(); return; }', '    if (false) { DrawSoundLog(); return; }'),
    ('icon glyph', '    case kW7Voice:                           // speech bubble\n',
     '    case kW7Voice:                           // speech bubble\n        dl->AddText(p, c, "\\360\\237\\222\\254");\n'),
    ('SnTick monitor', '    if (g_snOk && !g_snOn && W7SnapWanted()) { W7SnapTick(); return; }', '    // monitor'),
    ('present tick', '    W7PresentTick(padIdle);', '    // W7PresentTick(padIdle);'),
    ('present thread', 'const int state = !g_snGameThread || g_snGameThread == me ? 1 : 0;', 'const int state = 1;'),
    ('QbBuild rows', '        if (r.kind == kQbSndMon) {           // 0.22.47', '        if (false) {           // 0.22.47'),
    ('QuickTick order', '    if (g_qbView[row].src <= kQbSmSrc) {     // 0.22.47', '    if (false) {     // 0.22.47'),
    ('long menu', '        W7MenuRows(r.arg, page, index);', '        ImGui::TextDisabled("-");'),
    ('writes memory', '    g_w7SeenN = g_w7SeenNextN;', '    g_w7SeenN = g_w7SeenNextN;\n    WriteDword(0, 0);'),
    ('item thread', 'muted; [Sound] SonarMute=2, kept", true, ValW7Sonar57, RunW7Sonar57},',
     'muted; [Sound] SonarMute=2, kept", false, ValW7Sonar57, RunW7Sonar57},'),
    ('item dropped', '    {"snd.history", "action", "0.22.47', '    {"snd.histry", "action", "0.22.47'),
    ('key default', '{"Sound", "SonarMute", "0", ', '{"Sound", "SonarMute", "1", '),
    ('settings row', '"Sonar: whole group 57 off (fallback)", "snd.sonar57", "", kQbBool',
     '"Sonar: whole group 57 off (fallback)", "snd.sonar5", "", kQbBool'),
    ('Paket B check', '"tgB.sonar", kQbCheck', '"tgB.sonr", kQbCheck'),
    ('built-in name', '{914, "computer_hum_12"}', '{914, "computer_hum"}'),
]


def main():
    bad = 0
    T.read_cpp = lambda: SRC
    p, _ = T.check_02247(SW)
    print('positive (unchanged source): %d problem(s) %s' % (len(p), 'ok' if not p else 'FAIL ' + '; '.join(p)))
    bad += 1 if p else 0
    for name, old, new in CASES:
        if SRC.count(old) != 1:
            print('case %-22s: pattern found %d times (need 1) - FAIL' % (name, SRC.count(old))); bad += 1; continue
        mutated = SRC.replace(old, new, 1)
        T.read_cpp = lambda m=mutated: m
        p, _ = T.check_02247(SW)
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-22s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    print('%d cases + 1 positive, %d failed' % (len(CASES), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
