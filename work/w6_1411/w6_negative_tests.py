"""W6 (2026-11-14): negative tests of trumenu_ini_check.check_02245 - each case breaks one rule in a copy of TruMenu.cpp
(read_cpp is replaced in memory, no file is written) and must yield at least one problem; the unchanged source none.
Every pattern must occur exactly once in the source (else the case counts as failed).

Usage (from the repository root):
  ../bin/pyt -t 300 work/w6_1411/w6_negative_tests.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import trumenu_ini_check as T

SRC = T.read_cpp()
SW = T.SWITCHES
CASES = [
    ('version', 'const char *const kVersion = "TruMenu 0.22.45 (W6 sound switches',
     'const char *const kVersion = "TruMenu 0.22.45 (W6 sound switch'),
    ('check row changed', '{0x007c92b5, "55 8bec 51 53 56 8bf1 57', '{0x007c92b5, "55 8bec 51 53 56 8bf1 56'),
    ('check row dropped', '    {0x0058d85b, "8b3e 3b3db83bcd00"},', ''),
    ('W6Check table', 'g_w6Ok = g_snOk && g_smOk && DvChecks(kW6Checks,', 'g_w6Ok = g_snOk && DvChecks(kW6Checks,'),
    ('load order', '    W6Check();                                // 0.22.45',
     '    // W6Check();                             // 0.22.45'),
    ('options order', '    W6ReadOptions(ini);                                                              // 0.22.45',
     '    // W6ReadOptions(ini);'),
    ('SnTick order', '    W6Tick();                                // 0.22.45 W6 sound switches + wave log',
     '    // W6Tick();                             // 0.22.45 W6 sound switches + wave log'),
    ('setMute address', 'kW6ChSetMute = 0x007c92b5', 'kW6ChSetMute = 0x007c92b6'),
    ('no validate', 'if (reinterpret_cast<W6ValidateFn>(kW6ChValidate)(handle, &chan) != 0 || !chan) return false;\n'
                    '        reinterpret_cast<W6ChMuteFn>', 'chan = handle;\n        reinterpret_cast<W6ChMuteFn>'),
    ('emitter offset', 'ReadDword(params - 0x14, &vt) || vt != kW6EmitterVtbl) return 0;',
     'ReadDword(params - 0x10, &vt) || vt != kW6EmitterVtbl) return 0;'),
    ('emitter no vtable', 'ReadDword(params - 0x14, &vt) || vt != kW6EmitterVtbl) return 0;',
     'ReadDword(params - 0x14, &vt)) return 0;'),
    ('owner slot stride', 'ReadDword(slots + i * 0xc, &handle)', 'ReadDword(slots + i * 8, &handle)'),
    ('owner list offset', 'ReadDword(x.addr + 0x248, &list)', 'ReadDword(x.addr + 0x244, &list)'),
    ('owner list end', 'for (int guard = 0; node && node != listEnd && guard < 64; ++guard) {',
     'for (int guard = 0; node && guard < 64; ++guard) {'),
    ('foreign channel', '                if (W6ChMuted(v.channel, &already) && already) continue;   // muted by someone else: not ours\n', ''),
    ('extra unmute', '            } else if (want) {\n                g_w6Chan[r].seen = true;',
     '            } else if (want) {\n                W6ChMute(v.channel, false);\n                g_w6Chan[r].seen = true;'),
    ('foreign group undone', 'if (c.cg != cg) { c.cg = cg; c.ours = false; }', 'if (c.cg != cg) { c.cg = cg; c.ours = true; }'),
    ('ambience group', 'else if (g_w6Rules[i].kind == kW6Amb) want[wn++] = kW6AmbGroup;',
     'else if (g_w6Rules[i].kind == kW6Amb) want[wn++] = 16;'),
    ('track stop path', '        const bool ok = SndStopSlot(s);\n        Log(1, "snd.mute: srmusic slot',
     '        const bool ok = true;\n        Log(1, "snd.mute: srmusic slot'),
    ('back without gate', '        if (!MusicPlace(why, sizeof(why))) {\n            Log(1, "snd.mute: srmusic slot %d \'%s\' not restarted',
     '        if (false) {\n            Log(1, "snd.mute: srmusic slot %d \'%s\' not restarted'),
    ('amb beds', 'if (g_w6Rules[i].kind == kW6Amb && SndAmbName(name)) return true;',
     'if (g_w6Rules[i].kind == kW6Amb) return true;'),
    ('wave dedupe', 'g_w6Seen[i].channel == v.channel', 'g_w6Seen[i].voice != 0'),
    ('wave cap', 'if (g_w6WaveMax > 0 && g_w6WaveLines >= g_w6WaveMax) {', 'if (false) {'),
    ('now thread', '    if (GetCurrentThreadId() != g_snGameThread) {   // as snd.dump: the FMOD queries only on the game thread',
     '    if (false) {   // as snd.dump: the FMOD queries only on the game thread'),
    ('apply off thread', 'if (GetCurrentThreadId() == g_snGameThread) W6Tick();', 'W6Tick();'),
    ('writes memory', '    g_w6SeenN = seenNew;\n}', '    g_w6SeenN = seenNew;\n    WriteDword(0, 0);\n}'),
    ('item thread', '"a music track name; \'all 0\' = every rule and the solo off", true, ValW6Mutes, RunW6Mute},',
     '"a music track name; \'all 0\' = every rule and the solo off", false, ValW6Mutes, RunW6Mute},'),
    ('item dropped', '    {"music.mute", "bool", "0.22.45: = media.mutemusic', '    {"music.mutx", "bool", "0.22.45: = media.mutemusic'),
    ('key default', '{"Sound", "WaveIds", "10", ', '{"Sound", "WaveIds", "11", '),
    ('Paket B row', '    {"Nur Welle 10 (Solo an / aus)", "Wave 10 only (solo on / off)", "snd.solo", "10", kQbAction, -1, kQcNone, 0, kQbSound,\n     kQfTg},\n', ''),
    ('Paket B check', '"test.mark", "tgB.wave10log"', '"test.mark", "tgB.wave10lg"'),
    ('settings row', '"Next music", "music.next", "", kQbAction', '"Next music", "music.nxt", "", kQbAction'),
]


def main():
    bad = 0
    T.read_cpp = lambda: SRC
    p, _ = T.check_02245(SW)
    print('positive (unchanged source): %d problem(s) %s' % (len(p), 'ok' if not p else 'FAIL ' + '; '.join(p)))
    bad += 1 if p else 0
    for name, old, new in CASES:
        if SRC.count(old) != 1:
            print('case %-20s: pattern found %d times (need 1) - FAIL' % (name, SRC.count(old))); bad += 1; continue
        mutated = SRC.replace(old, new, 1)
        T.read_cpp = lambda m=mutated: m
        p, _ = T.check_02245(SW)
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-20s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    print('%d cases + 1 positive, %d failed' % (len(CASES), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
