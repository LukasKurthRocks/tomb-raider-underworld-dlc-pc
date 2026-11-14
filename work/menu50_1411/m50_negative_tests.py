r"""0.22.50 (2026-11-14): negative tests of trumenu_ini_check.check_02250 - each case breaks one rule in a copy of
TruMenu.cpp (read_cpp is replaced in memory) or of TruMenu.switches.txt (a mutated copy in _archiv\ next to this script,
overwritten per case and kept) and must yield at least one problem; the unchanged sources none. Every pattern must occur
exactly once (else the case counts as failed).

Usage (from the repository root):
  ../bin/pyt -t 300 work/menu50_1411/m50_negative_tests.py
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import trumenu_ini_check as T

SRC = T.read_cpp()
SW = T.SWITCHES
SW_TEXT = open(SW, encoding='utf-8').read()
CPP_CASES = [
    ('version', 'const char *const kVersion = "TruMenu 0.22.50 (sound log readable + FMOD channels + source hooks,',
     'const char *const kVersion = "TruMenu 0.22.50 (sound log,'),
    ('check row changed', '{0x007c9c82, "83486820"},', '{0x007c9c82, "83486821"},'),
    ('check row dropped', '    {0x007c4acf, "897e1c"},                                               // addGroup: +0x1c = the parent\n', ''),
    ('check order', '    W8Check();                                // 0.22.50', '    // W8Check();'),
    ('V1 other target', '{0x00591351, 0x0058bfc0, true, "V1 voice -> emitter 0x591351", 0, 0, false},',
     '{0x00591351, 0x0058bfc1, true, "V1 voice -> emitter 0x591351", 0, 0, false},'),
    ('E1 other site', 'const DWORD kW8E1 = 0x005b99fc;', 'const DWORD kW8E1 = 0x005b99f7;'),
    ('E1 game bytes', 'kW8E1Game[6] = {0x8b, 0x44, 0x24, 0x18, 0x85, 0xc0}', 'kW8E1Game[6] = {0x8b, 0x44, 0x24, 0x1c, 0x85, 0xc0}'),
    ('create call patched', '    {0x00591351, 0x0058bfc0, true, "V1 voice -> emitter 0x591351", 0, 0, false},\n',
     '    {0x00591351, 0x0058bfc0, true, "V1 voice -> emitter 0x591351", 0, 0, false},\n'
     '    {0x005b99f7, 0x005935d0, true, "E1", 0, 0, false},\n'),
    ('E1 no read back', 'if (!W8E1Bytes(from) || !WriteBytes(kW8E1, to, 6) || !W8E1Bytes(to)) return false;',
     'if (!WriteBytes(kW8E1, to, 6)) return false;'),
    ('E1 nop missing', '    g_w8E1New[5] = 0x90;\n', ''),
    ('hook rel32 wrong', 'g_w8Patches[0].hook = reinterpret_cast<DWORD>(&W8PlayStub) - (g_w8Patches[0].site + 5);',
     'g_w8Patches[0].hook = reinterpret_cast<DWORD>(&W8PlayStub) - g_w8Patches[0].site;'),
    ('V1 not put back', '    for (AiPatch &p : g_w8Patches) AiPatchOff(p);\n    W8E1Set(false);\n    g_w8HooksOn = false;\n',
     '    W8E1Set(false);\n    g_w8HooksOn = false;\n'),
    ('E1 not put back', '    for (AiPatch &p : g_w8Patches) AiPatchOff(p);\n    W8E1Set(false);\n    g_w8HooksOn = false;\n',
     '    for (AiPatch &p : g_w8Patches) AiPatchOff(p);\n    g_w8HooksOn = false;\n'),
    ('detach without W8', '        W8Shutdown();                                 // 0.22.50', '        // 0.22.50'),
    ('play stub ret', '        call W8OnPlay\n        popfd\n        popad\n        ret 4\n',
     '        call W8OnPlay\n        popfd\n        popad\n        ret\n'),
    ('play stub no copy', '        push dword ptr [esp + 4]\n        call dword ptr [g_w8PlayFn]\n',
     '        call dword ptr [g_w8PlayFn]\n'),
    ('emit stub offset', '        mov eax, dword ptr [esp + 0x1c]\n', '        mov eax, dword ptr [esp + 0x18]\n'),
    ('emit stub no test', '        call W8OnEmit\n        popfd\n        popad\n        test eax, eax\n        ret\n',
     '        call W8OnEmit\n        popfd\n        popad\n        ret\n'),
    ('callback cdecl', 'void __stdcall W8OnPlay(DWORD voice, DWORD node) {', 'void __cdecl W8OnPlay(DWORD voice, DWORD node) {'),
    ('W8 writes memory', '    ReadDword(em + 0xc, &sid);\n    ReadDword(inst + 0x58, &intro);\n',
     '    ReadDword(em + 0xc, &sid);\n    WriteDword(em + 0xc, 0);\n    ReadDword(inst + 0x58, &intro);\n'),
    ('slot mask', 'const DWORD slot = (handle >> 16) & 0xfff;', 'const DWORD slot = (handle >> 16) & 0xff;'),
    ('handle not compared', 'if (!ReadDword(c + 0x70, &h) || h != handle ||', 'if (!ReadDword(c + 0x70, &h) ||'),
    ('used list head', 'const DWORD head = sys + 0x150;', 'const DWORD head = sys + 0x14c;'),
    ('extras after publish', '    W8Extras(cats, groups);                  // 0.22.50', '    // W8Extras'),
    ('mute from rule', 'const bool muted = x.fmOk ? x.fmMute : x.ours || W7Muted(x.wave, x.emitter, x.sid);',
     'const bool muted = x.ours || W7Muted(x.wave, x.emitter, x.sid);'),
    ('square old meaning', 'view(name, state, count, c, muted ? red : grey, muted ? 2 : 1,',
     'view(name, state, count, c, muted ? red : grey, muted ? 1 : 2,'),
    ('box from rule', 'W8Box(dl, p, h, !e.fmMute, c);', 'W8Box(dl, p, h, true, c);'),
    ('loop as glyph', 'dl->PathStroke(c, 0, s * 0.11f);', 'dl->AddText(m, c, "\\342\\206\\273");'),
    ('collapse key', 'if (a.wave == h.wave && !strcmp(a.src, h.src) && (h.wave >= 0 || !strcmp(a.name, h.name))) { at = i; break; }',
     'if (a.wave == h.wave) { at = i; break; }'),
    ('owner every 250 ms', '(!g_w7OwnAt || now - g_w7OwnAt > 1000) && W8Visible()', '(!g_w7OwnAt || now - g_w7OwnAt > 250)'),
    ('owner before hook', '    if (emitter && W8EmitterInst(emitter, &er)) { W8InstText(er.inst, er.intro, er.objectId, de, o, n); return; }\n', ''),
    ('cat groups gone', 'wn += W8CatPureGroups(static_cast<int>(g_w6Rules[i].value), want + wn, kW6CgMax - wn);', 'wn += 0;'),
    ('no extra mutes', '    if (catRule || g_w6SoloOn) W8ExtraMutes(poolCh, poolN, tgroups, catRule);', '    // no extras'),
    ('foreign mute bit', '            if (fl & 2) return;                  // its own mute bit', '            // its own mute bit'),
    ('ambience old item', '"beds ([Media] MuteAmbient, kept)", true, ValW6Amb, RunW6Amb},',
     '"beds ([Media] MuteAmbient, kept)", false, ValMuteAmbient, RunMuteAmbient},'),
    ('duplicate music row', '    // 0.22.50 C: "Umgebung aus (Ambience)" (snd.ambmute) and',
     '    {"Musik aus (Kanaele)", "Music off (channels)", "music.mute", "", kQbBool, -1, kQcNone, 0, kQbSound, 0},\n'
     '    // 0.22.50 C: "Umgebung aus (Ambience)" (snd.ambmute) and'),
    ('ambience not kept', '    if (r.kind == kW6Amb) IniKeep("Media", "MuteAmbient", on ? "1" : "0");', '    // not kept'),
    ('chapter DLC as unit', 'if (dlcStart) Out(steps, n, "save.backup kapitel;level.start %s", dlc);',
     'if (dlcStart) Out(steps, n, "save.backup kapitel;level.start %s 0", unit);'),
    ('chapter DLC in a level', '    if (dlcStart && InLevel()) {', '    if (false) {'),
    ('chapter row old path', '!_stricmp(r.id, "level.load") && !ChapSteps(r.arg, steps, sizeof(steps), &menu, o, sizeof(o))',
     'false'),
    ('cp.jump unit.go', 'if (menu) Out(go, sizeof(go), "level.start %s 0", unit);', 'if (menu) Out(go, sizeof(go), "unit.go %s", unit);'),
    ('item thread', '"channels outside the pool muted (music = media.mutemusic)", true, ValW6Mutes, RunW8CatMute},',
     '"channels outside the pool muted (music = media.mutemusic)", false, ValW6Mutes, RunW8CatMute},'),
    ('item help', '{"snd.solonew", "", "', '{"snd.solonuw", "", "'),
    ('key default', '{"Sound", "LogCollapse", "1", ', '{"Sound", "LogCollapse", "0", '),
    ('settings row', '{"Solo: Sprache", "Solo: speech", "snd.catsolo", "speech", kQbBool, -1, kQcNone, 0, kQbSound, 0},',
     '{"Solo: Sprache", "Solo: speech", "snd.catsolo", "lara", kQbBool, -1, kQcNone, 0, kQbSound, 0},'),
    ('category key', 'const char *const kW8CatKey[kW8Cats] = {"lara", "enemies",', 'const char *const kW8CatKey[kW8Cats] = {"lara", "enemy",'),
]
SW_CASES = [
    ('hooks live', 'Exact sound source (2 hooks) | restart | 1 |', 'Exact sound source (2 hooks) | live | 1 |'),
    ('collapse default', 'Sound log: collapse repetitions | live | 1 |', 'Sound log: collapse repetitions | live | 0 |'),
    ('dist restart', 'Sound log: at most this far (m) | live | 0 |', 'Sound log: at most this far (m) | restart | 0 |'),
    ('lara since', 'Lara\'s body, gear, weapons | TruMenu 0.22.50', 'Lara\'s body, gear, weapons | TruMenu 0.22.49'),
    ('group gone', 'group | tmtonlog | Ton-Log (TruMenu) | Sound log (TruMenu)', 'group | tmtonlug | Ton-Log (TruMenu) | Sound log (TruMenu)'),
]


def main():
    bad = 0
    T.read_cpp = lambda: SRC
    p, _ = T.check_02250(SW)
    print('positive (unchanged sources): %d problem(s) %s' % (len(p), 'ok' if not p else 'FAIL ' + '; '.join(p)))
    bad += 1 if p else 0
    for name, old, new in CPP_CASES:
        if SRC.count(old) != 1:
            print('case %-24s: pattern found %d times (need 1) - FAIL' % (name, SRC.count(old))); bad += 1; continue
        mutated = SRC.replace(old, new, 1)
        T.read_cpp = lambda m=mutated: m
        p, _ = T.check_02250(SW)
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-24s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    T.read_cpp = lambda: SRC
    os.makedirs(os.path.join(HERE, '_archiv'), exist_ok=True)
    copy = os.path.join(HERE, '_archiv', 'm50_switches_mutated.txt')
    for name, old, new in SW_CASES:
        if SW_TEXT.count(old) != 1:
            print('case %-24s: pattern found %d times (need 1) - FAIL' % (name, SW_TEXT.count(old))); bad += 1; continue
        with open(copy, 'w', encoding='utf-8', newline='') as f:
            f.write(SW_TEXT.replace(old, new, 1))
        p, _ = T.check_02250(copy)
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-24s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    print('%d cases + 1 positive, %d failed' % (len(CPP_CASES) + len(SW_CASES), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
