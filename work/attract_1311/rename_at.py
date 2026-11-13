"""Q126 / TruMenu 0.22.39 (2026-11-13): the first draft of the attract icon used the prefix Ai / g_ai, which the 0.19
"dumb AI" section already uses (AiTick, ValAi, RunAi). This one-off renames the icon's names to At / g_at in the files of
this change: names new in 0.22.39 (count 0 in HEAD) everywhere, the three clashing ones only in their 0.22.39 contexts.
Byte-exact otherwise (line ends kept). Usage (from trudlcport): ../bin/pyt -t 60 work/attract_1311/rename_at.py"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES = ['src/asi/TruMenu/TruMenu.cpp', 'tools/trumenu_ini_check.py', 'src/asi/TruMenu/README.md',
         'src/asi/TruMenu/TruMenu.switches.txt']
NEW = ['g_aiWant', 'g_aiText', 'g_aiSkipped', 'g_aiStarted', 'g_aiBlinks', 'g_aiBlinkTick', 'g_aiIniOn', 'g_aiIniText',
       'g_aiReadTick', 'AiOnLimit', 'AiReadSwitch', 'AiWantsDraw', 'AiFraction', 'AiSector', 'DrawAi', 'kAiBlinkMs',
       'kAiBlinkPhaseMs', 'aiDraw', 'AI_KEYS_02239']
CONTEXT = [   # (old, new) exact strings, each must occur exactly once in TruMenu.cpp / the checker
    ('void AiTick();                               // game thread (NaTick)', 'void AtTick();                               // game thread (NaTick)'),
    ('    AiTick();                                // 0.22.39', '    AtTick();                                // 0.22.39'),
    ("void AiTick() {                              // NaTick's thread", "void AtTick() {                              // NaTick's thread"),
    ('void ValAi(char *o, size_t n) {\r\n    const bool held = g_naWant && g_naOn;\r\n    float shown',
     'void ValAt(char *o, size_t n) {\r\n    const bool held = g_naWant && g_naOn;\r\n    float shown'),
    ('bool RunAi(const char *arg, char *o, size_t n) {\r\n    if (!arg || !arg[0]) { ValAi(o, n); return true; }   // no argument = report, never a flip\r\n    bool on;\r\n    if (!strcmp(arg, "1") || !_stricmp(arg, "on") || !_stricmp(arg, "true")) on = true;\r\n    else if (!strcmp(arg, "0") || !_stricmp(arg, "off") || !_stricmp(arg, "false")) on = false;\r\n    else { Out(o, n, "usage: menu.attracticon',
     'bool RunAt(const char *arg, char *o, size_t n) {\r\n    if (!arg || !arg[0]) { ValAt(o, n); return true; }   // no argument = report, never a flip\r\n    bool on;\r\n    if (!strcmp(arg, "1") || !_stricmp(arg, "on") || !_stricmp(arg, "true")) on = true;\r\n    else if (!strcmp(arg, "0") || !_stricmp(arg, "off") || !_stricmp(arg, "false")) on = false;\r\n    else { Out(o, n, "usage: menu.attracticon'),
    ('     false, ValAi, RunAi},\r\n    // 0.21.4', '     false, ValAt, RunAt},\r\n    // 0.21.4'),
]
CHECKER = [   # strings in tools/trumenu_ini_check.py
    ("'void AiTick('", "'void AtTick('"), ("'TruMenu.cpp: AiTick must", "'TruMenu.cpp: AtTick must"),
    ("tick.find('AiTick();')", "tick.find('AtTick();')"), ("must call AiTick and", "must call AtTick and"),
    ("'void ValAi('", "'void ValAt('"), ("false, ValAi, RunAi\\}", "false, ValAt, RunAt\\}"),
    ("(bool, ValAi / RunAi)", "(bool, ValAt / RunAt)"), ("'bool RunAi('", "'bool RunAt('"),
    ("'if (!arg || !arg[0]) { ValAi(o, n); return true; }'", "'if (!arg || !arg[0]) { ValAt(o, n); return true; }'"),
    ("RunAi must hold", "RunAt must hold"), ("RunAi must not use", "RunAt must not use"),
]


def main():
    total = 0
    for rel in FILES:
        path = os.path.join(ROOT, rel)
        text = open(path, encoding='utf-8', newline='').read()
        before = text
        for name in NEW:
            new = name.replace('g_ai', 'g_at', 1).replace('Ai', 'At', 1).replace('aiDraw', 'atDraw').replace('kAi', 'kAt')
            if name == 'AI_KEYS_02239': new = 'AT_KEYS_02239'
            text, n = re.subn(r'\b%s\b' % re.escape(name), new, text)
            total += n
        if rel.endswith('.py'):              # the clashing names only inside check_02239 (all of them are the icon's)
            a = text.find('\ndef check_02239(')
            b = text.find('\n\n\n', a)
            if a < 0 or b < 0:
                print('%s: check_02239 not found' % rel)
                return 1
            body = re.sub(r'\b(AiTick|ValAi|RunAi)\b', lambda m: m.group(1).replace('Ai', 'At'), text[a:b])
            total += 1
            text = text[:a] + body + text[b:]
        pairs = CONTEXT if rel.endswith('TruMenu.cpp') and 'void AtTick() {' not in text else []
        for old, new in pairs:
            if text.count(old) != 1:
                print('%s: context found %d times: %r' % (rel, text.count(old), old[:70]))
                return 1
            text = text.replace(old, new)
            total += 1
        if text != before:
            open(path, 'w', encoding='utf-8', newline='').write(text)
        print('%s: %s' % (rel, 'changed' if text != before else 'unchanged'))
    print('%d replacements' % total)
    return 0


if __name__ == '__main__':
    sys.exit(main())
