"""Write the TruMenu tour file (TruMenu 0.10.1 / 0.10.2, radial menu level Tests/Rundgang) from the shader tour
document (workspace docs/Shader-Rundgang.md) - read-only on the document, writes only the output file.

The document has an overview table (| Nr | Einheit | Befehl | Gruppen | Ort | Stand |) and one "### NN - title" heading
per stop below a "## <section>" heading. Each stop becomes one entry "path | label | item id [argument]" in the radial
file format (TruMenu.radial.txt):
  path   the section heading, shortened ("DLC 2 - Maschinenraum (`dlc2_machine_room`)" -> "DLC 2/Maschinenraum"), so
         the ring level is Tests/Rundgang/DLC 2/<room> for the "DLC 2 - " sections (TruMenu 0.10.2, F8: eight DLC 2
         rooms no longer fill the Rundgang level) and Tests/Rundgang/<section> for the others (DLC 1, Versteckt,
         Paket-Ziele, Nur in Zwischensequenzen)
  label  "NN <title>" (ASCII: umlauts transliterated, the menu font has none), "(?)" appended when the Ort column says
         "unverifiziert", at most 47 characters
  item   the stop's TruMenu command from the Befehl column: player.goto <id>, level.start <dlc>; a stop that also needs
         a level.load gets an entry "Laden <unit>" (level.load <unit>) in front of it, once per unit and section; a
         stop whose only command is a level.load is that entry itself (label "NN <title>"); a stop without a command
         (cutscene, "RB halten") runs status.unit (shows the unit, changes nothing). 0.10.2 (F8, los7 21:22:37: the
         level.start entry said "err main menu only" in a level): level.start works from the main menu only, so a
         level.start stop also gets "Laden <start unit>" (dlc2 -> dlc_level2_start, dlc1 -> dlc_level1_start, as
         TruMenu's StartUnitName) in front of it - the entry for use in a level (no intro); TruMenu 0.10.2 greys the
         level.start entry out outside the main menu
Never game.quit / cmd.run (tools/trumenu_ini_check.py checks the written file).
Several documents (2026-11-03: docs/Shader-Rundgang.md, then docs/Versteckte-Inhalte-Rundgang.md) are read in the
given order, each with its own overview table; their stops are appended.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/tour_from_rundgang.py DOC.md [DOC2.md ..] OUT.txt      write OUT.txt (LF), print a summary
  ../bin/pyt -t 60 tools/tour_from_rundgang.py DOC.md [DOC2.md ..] --print      print the entries only
"""
import re, sys

UMLAUT = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue', 'ß': 'ss', '–': '-', '—': '-', '’': "'",
          '„': '"', '“': '"', '”': '"', '→': '->', '…': '...'}
ITEMS = ('player.goto', 'level.load', 'level.start')
START_UNITS = {'': 'dlc_level2_start', 'dlc2': 'dlc_level2_start', 'dlc1': 'dlc_level1_start'}   # TruMenu StartUnitName
DLC2_FOLDER = 'DLC 2'


def ascii_text(s):
    for k, v in UMLAUT.items(): s = s.replace(k, v)
    return s.encode('ascii', 'replace').decode('ascii').replace('|', '/')


def section_name(heading):
    """'DLC 2 - Maschinenraum (`dlc2_machine_room`)' -> 'DLC 2/Maschinenraum'; other headings stay one level; only path
    characters [A-Za-z0-9 _().-] per segment, at most 47 each"""
    h = ascii_text(heading)
    h = re.sub(r'\(`[^`]*`\)', '', h)
    dlc2 = re.match(r'^DLC 2 - ', h) is not None
    h = re.sub(r'^DLC 2 - ', '', h).strip()
    h = re.sub(r'[^A-Za-z0-9 _().-]', '', h).strip()
    h = h[:47] or 'Rundgang'
    return '%s/%s' % (DLC2_FOLDER, h) if dlc2 else h


def parse(doc):
    """[(nr, section, title, commands [(item, arg)], unverified)] in document order"""
    lines = doc.splitlines()
    table = {}
    for line in lines:
        m = re.match(r'\|\s*(\d\d)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|', line)
        if not m: continue
        nr, unit, cmd, groups, place = m.groups()
        cmds = []
        for snippet in re.findall(r'`([^`]+)`', cmd):
            word, _, arg = snippet.strip().partition(' ')
            if word in ITEMS: cmds.append((word, arg.strip()))
        table[nr] = (cmds, 'unverifiziert' in place)
    stops, section = [], 'Rundgang'
    for line in lines:
        m2 = re.match(r'^## (.+)$', line)
        if m2:
            section = section_name(m2.group(1))
            continue
        m3 = re.match(r'^### (\d\d) [-–] (.+)$', line)
        if m3 and m3.group(1) in table:
            nr = m3.group(1)
            cmds, unverified = table[nr]
            stops.append((nr, section, ascii_text(m3.group(2)).strip(), cmds, unverified))
    return stops


def entries(stops):
    out, loaded = [], set()
    for nr, section, title, cmds, unverified in stops:
        suffix = ' (?)' if unverified else ''
        room = 47 - len(nr) - 1 - len(suffix)
        short = title
        if len(short) > room:                # cut at the last space that fits, drop a dangling "(" part
            short = short[:room + 1]
            short = short[:short.rfind(' ')] if ' ' in short else short[:room]
            if short.count('(') > short.count(')'): short = short[:short.rfind('(')]
            short = re.sub(r'\s+(und|mit|der|die|das)$', '', short.rstrip(' ,:-')).rstrip(' ,:-')
        label = '%s %s%s' % (nr, short, suffix)
        stop_cmd = None
        if len(cmds) == 1 and cmds[0][0] == 'level.load':      # load-only stop: the stop is the load entry
            out.append((section, label, 'level.load %s' % cmds[0][1]))
            loaded.add((section, cmds[0][1]))
            continue
        for word, arg in cmds:
            if word == 'level.start':                          # 0.10.2: the in-level twin of a mission start
                unit = START_UNITS.get(arg.lower(), arg)
                if (section, unit) not in loaded:
                    out.append((section, ('Laden %s' % unit)[:47], 'level.load %s' % unit))
                    loaded.add((section, unit))
            if word == 'level.load':
                if (section, arg) not in loaded:
                    out.append((section, ('Laden %s' % arg)[:47], 'level.load %s' % arg))
                    loaded.add((section, arg))
            elif stop_cmd is None:
                stop_cmd = '%s %s' % (word, arg) if arg else word
        if stop_cmd is None:
            stop_cmd = 'status.unit'
        out.append((section, label, stop_cmd))
    return out


def main(argv):
    if len(argv) < 2: sys.exit(__doc__)
    docs, out = argv[:-1], argv[-1]
    stops = []
    for path in docs:
        stops += parse(open(path, encoding='utf-8').read())
    rows = entries(stops)
    names = ' + '.join('docs/' + re.split(r'[\\/]', p)[-1] for p in docs)
    text = ['# TruMenu tour (TruMenu 0.10.2) - Set-TruMenu.ps1 copies it next to tru.exe as TruMenu.tour.txt.',
            '# Written by tools/tour_from_rundgang.py from the workspace %s (%d stops); do not edit' % (names, len(stops)),
            '# by hand - run the tool again. Radial menu: Tests / Rundgang / <section> (DLC 2 rooms: Tests / Rundgang /',
            '# DLC 2 / <room>); "(?)" = place unverified in the document; level.start = main menu only, its "Laden"',
            '# entry is for use in a level. One entry per line: path | label | item id [argument] (path below',
            '# Tests/Rundgang).']
    for section, label, cmd in rows:
        text.append('%s | %s | %s' % (section, label, cmd))
    body = '\n'.join(text) + '\n'
    if out == '--print':
        sys.stdout.write(body)
        return 0
    with open(out, 'w', encoding='ascii', newline='\n') as f:
        f.write(body)
    unverified = sum(1 for s in stops if s[4])
    print('%s: %d stops (%d unverified), %d entries in %d sections' % (out, len(stops), unverified, len(rows),
                                                                      len({r[0] for r in rows})))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
