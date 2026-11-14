"""PK1-8 (2026-11-14): the owner's real DLC 2 runs as a per-session timeline (read-only, log copies only).
Copy of work/pk1_1411/pk1_trace_dlc1.py with the DLC 2 unit set, DLC 2 story texts (unit script strings, PK1-8 scripts
scan) and the first-reach block for every DLC 2 unit instead of dlc_pillory.

Reads a TruTrace.log copy (sessions '=== <date time> TruTrace <ver> session start (pid N) ===') and the TruMenu.log copy of
the same day and prints, per session that touches a DLC 2 unit (dlc_level2_start, dlc_yggdrasil_* , dlc2_*), the
events the level chain is checked against:
  LOAD   STREAM_LevelLoadAndInit through the level load (0x5dded0) = main load (new game / level.load / reload)
  REQ    REQUEST level change (TruTrace 'level: REQUEST level change ...')
  PLACE  player placement: unit + picked checkpoint intro + why (after a level load / restore path)
  HIT    stream portal hit by the player: portal index, from unit -> to unit
  MOVE   MOVE into a new stream unit A -> B (no HIT just before = not through a portal: cutscene / teleport / jump)
  SAVE   SAVE_SaveGame(0) by CHECKPOINT reached: intro id, object, unit +0xe0 (and 'placement found no checkpoint')
  REST   SAVE_RestoreGame(0): restored unit + checkpoint id (reload after death or a menu load)
  TP     teleport JUMP (TruTrace teleport watch; TruMenu teleports / script warps), one line per jump
  MENU   TruMenu commands: item level.load / cp.jump / pos.portal / unit.go / dbg.cpgo, shortcut starts, cheat.flight
         on / off (the owner's menu use, so a MOVE after them is no walked portal)
  STORY  TruMenu 'script:' lines with a DLC 1 story text of the unit scripts (bats pass 1 / 2, prep pillory visit 2,
         dungeon second visit, gate number n closed, set balcony checkpoint, cinematic start / end, credits ...)
Then a per-session summary: units in first-visit order, portal hits per unit pair, checkpoint saves per unit in order
(first time each), how each DLC 2 unit was first reached (the 6 events before its first MOVE / PLACE / LOAD).

Usage (from trudlcport):
  ../bin/pyt -t 300 work/pk2_1411/pk2_trace_dlc2.py TRUTRACE TRUMENU OUT [--from HH:MM] [--to HH:MM] [--day YYYY-MM-DD]
Exit code 0 = done, 2 = usage / no session.
"""
import sys, re, collections

DLC1 = ('dlc_level2_start', 'dlc_yggdrasil_hall01', 'dlc_yggdrasil_hall02', 'dlc_yggdrasil_end', 'dlc2_ceremony_room',
        'dlc2_hall_machine_ceremony', 'dlc2_machine_room', 'dlc2_hall_goo_machine', 'dlc2_goo_room',
        'dlc2_hall_ceremony_goo', 'dlc2_treasure_room_cine')
CLOCK = r'([0-9]{2}[:][0-9]{2}[:][0-9]{2}\.[0-9]{3})'      # hh:mm:ss.mmm (classes keep the upload scan quiet)
TS = r'^(\d{4}-\d\d-\d\d) ' + CLOCK + ' '
R_SESS = re.compile(r'^=== (\d{4}-\d\d-\d\d) ' + CLOCK + r' TruTrace (\S+) session start \(pid (\d+)\) ===')
R_LOAD = re.compile(TS + r"\[[^\]]*\] level: STREAM_LevelLoadAndInit '([^']+)' from \S+ \(level load 0x5dded0\)")
R_REQ = re.compile(TS + r"\[[^\]]*\] level: REQUEST level change(.*)")
R_PLACE = re.compile(TS + r"\[[^\]]*\] level: PLACEMENT in unit (\d+) '([^']+)' \(from \S+ ([^)]*)\).*?-> (.*?): intro #\d+ id (\d+) obj \d+ (\S+)")
R_HIT = re.compile(TS + r"\[[^\]]*\] portal: HIT stream portal (\d+) \(record \S+ '([^']+)'\) in unit (\d+) '([^']+)' to unit (\d+) '([^']+)' by .*\(player\)")
R_MOVE = re.compile(TS + r"\[[^\]]*\] level: MOVE into a new stream unit: (-?\d+) '([^']*)' -> (\d+) '([^']+)'")
R_SAVE = re.compile(TS + r"\[[^\]]*\] save: SAVE_SaveGame\(0\) by CHECKPOINT reached [^:]*: inst \S+ obj \d+ (\S+) intro (\d+) at .*?, unit \+0xe0 (\d+)")
R_SAVE0 = re.compile(TS + r"\[([^\]]*)\] save: SAVE_SaveGame\(0\) by the player placement found no checkpoint intro")
R_REST = re.compile(TS + r"\[([^\]]*)\] save: SAVE_RestoreGame\(0\) from .*?restores the checkpoint copy unit '([^']*)', checkpoint id \+0x90 (\d+)")
R_TP = re.compile(TS + r"\[([^\]]*)\] teleport: JUMP of (\d+) units in \d+ ms \(TeleportUnits \d+\) - (.*)")
R_MENU = re.compile(TS + r"(item (?:level\.load|cp\.jump|pos\.portal|unit\.go|level\.start): .*|shortcut '[^']*' started: .*|"
                    r"dbg\.cpgo \d+: .*|item cheat\.flight: .*)")
# DLC 2 story markers the unit scripts print (TruMenu 'script:' lines; texts from the unit scripts, PK1-8 scripts scan)
R_STORY = re.compile(TS + r"script: (.*(?:[Vv]isit ?[123]|EndVisit|SetUpVisit|prep visit|Machine power|machine power|"
                     r"credits|CREDITS|warp|Warp|StartCinematic called|Cine_End event starting|natlapod|"
                     r"Objectives Dispatcher|dlc obj count|ceremony|goo room|machine_room|treasure|"
                     r"Loading DLC|MainMenu:  Inside Open).*)")


def opt(argv, name, default=None):
    if name in argv:
        i = argv.index(name); v = argv[i + 1]; del argv[i:i + 2]; return v
    return default


def sessions(path):
    out, cur = [], None
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = R_SESS.match(ln)
        if m:
            cur = dict(day=m.group(1), start=m.group(2), ver=m.group(3), pid=m.group(4), ev=[])
            out.append(cur); continue
        if cur is None: continue
        e = None
        m = R_LOAD.match(ln)
        if m: e = ('LOAD', m.group(3))
        if e is None and (m := R_REQ.match(ln)): e = ('REQ', m.group(3).strip()[:160])
        if e is None and (m := R_PLACE.match(ln)):
            e = ('PLACE', "%s cp %s %s (%s; %s)" % (m.group(4), m.group(7), m.group(8), m.group(5), m.group(6)[:70]))
        if e is None and (m := R_HIT.match(ln)):
            e = ('HIT', "portal %s in %s -> %s" % (m.group(3), m.group(6), m.group(8)))
        if e is None and (m := R_MOVE.match(ln)): e = ('MOVE', "%s -> %s" % (m.group(4) or '(none)', m.group(6)))
        if e is None and (m := R_SAVE.match(ln)): e = ('SAVE', "%s %s (unit +0xe0 %s)" % (m.group(4), m.group(3), m.group(5)))
        if e is None and (m := R_SAVE0.match(ln)): e = ('SAVE', "no checkpoint intro (placement) in %s" % m.group(3))
        if e is None and (m := R_REST.match(ln)): e = ('REST', "%s cp %s" % (m.group(4), m.group(5)))
        if e is None and (m := R_TP.match(ln)): e = ('TP', "%s units in %s (%s)" % (m.group(4), m.group(3), m.group(5)[:60]))
        if e: cur['ev'].append((m.group(1), m.group(2)) + e)
    return out


def menu_events(path):
    ev = []
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = R_MENU.match(ln)
        if m: ev.append((m.group(1), m.group(2), 'MENU', m.group(3)[:170])); continue
        m = R_STORY.match(ln)
        if m: ev.append((m.group(1), m.group(2), 'STORY', m.group(3)[:170]))
    return ev


def main(argv):
    t_from, t_to, day = opt(argv, '--from', '00:00'), opt(argv, '--to', '99:99'), opt(argv, '--day')
    if len(argv) < 4: print(__doc__); return 2
    trace, menu, out = argv[1:4]
    S = sessions(trace)
    M = menu_events(menu)
    lines, nsel = [], 0
    for i, s in enumerate(S):
        if day and s['day'] != day: continue
        if not (t_from <= s['start'][:5] <= t_to): continue
        units = [e for e in s['ev'] if e[2] in ('MOVE', 'PLACE', 'LOAD')]
        touched = any(any(u in e[3] for u in DLC1) for e in units)
        if not touched: continue
        nsel += 1
        end = S[i + 1]['day'] + ' ' + S[i + 1]['start'] if i + 1 < len(S) else '9999'
        beg = s['day'] + ' ' + s['start']
        ev = list(s['ev']) + [e for e in M if beg <= e[0] + ' ' + e[1] < end]
        ev.sort(key=lambda e: (e[0], e[1]))
        lines.append('=' * 100)
        lines.append('SESSION pid %s  TruTrace %s  start %s %s  (%d events, %d TruMenu lines)' % (
            s['pid'], s['ver'], s['day'], s['start'], len(s['ev']), len(ev) - len(s['ev'])))
        # timeline, consecutive TP / flight lines compressed
        last_key, rep = None, 0
        for e in ev:
            key = (e[2], e[3]) if e[2] in ('TP',) or 'cheat.flight' in e[3] else None
            if key and key == last_key:
                rep += 1; continue
            if rep: lines.append('      ... same line %d more time(s)' % rep); rep = 0
            last_key = key
            lines.append('  %s %-5s %s' % (e[1][:12], e[2], e[3]))
        if rep: lines.append('      ... same line %d more time(s)' % rep)
        # summary
        order, hits, prev_hit = [], collections.Counter(), None
        moves_nohit = collections.Counter()
        for k, e in enumerate(ev):
            if e[2] == 'MOVE':
                a, b = e[3].split(' -> ')
                if b not in order: order.append(b)
                h = prev_hit
                if not (h and h[3].endswith('in %s -> %s' % (a, b))): moves_nohit['%s -> %s' % (a, b)] += 1
                prev_hit = None
            elif e[2] == 'HIT':
                hits[e[3]] += 1; prev_hit = e
            elif e[2] == 'PLACE':
                u = e[3].split(' ', 1)[0]
                if u not in order: order.append(u)
        lines.append('  -- units in first-visit order: ' + ' > '.join(order))
        lines.append('  -- portal hits (player):')
        for h, n in sorted(hits.items()): lines.append('       %3d x %s' % (n, h))
        lines.append('  -- MOVEs without a portal hit just before (cutscene / teleport / menu):')
        for h, n in sorted(moves_nohit.items()): lines.append('       %3d x %s' % (n, h))
        # checkpoint saves per unit (first time), with the unit Lara was in (last MOVE / PLACE target)
        cur_u, per = None, collections.OrderedDict()
        for e in ev:
            if e[2] == 'MOVE': cur_u = e[3].split(' -> ')[1]
            elif e[2] == 'PLACE': cur_u = e[3].split(' ', 1)[0]
            elif e[2] == 'SAVE' and e[3].split(' ')[0].isdigit():
                cp = e[3].split(' ')[0]
                lst = per.setdefault(cur_u, [])
                if cp not in lst: lst.append(cp)
        lines.append('  -- checkpoint saves per unit (first time each, in log order):')
        for u, l in per.items(): lines.append('       %-20s %s' % (u, ' '.join(l)))
        # how each DLC 2 unit was first reached
        for un in DLC1:
            for k, e in enumerate(ev):
                if (e[2] == 'MOVE' and e[3].endswith('-> ' + un)) or (e[2] in ('PLACE', 'LOAD') and e[3].split(' ', 1)[0] == un):
                    lines.append('  -- first %s event at %s %s; the 6 events before it:' % (un, e[1][:12], e[2]))
                    for f in ev[max(0, k - 6):k + 1]: lines.append('       %s %-5s %s' % (f[1][:12], f[2], f[3]))
                    break
    open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    print('%d sessions in the log, %d with DLC 2 units selected -> %s' % (len(S), nsel, out))
    return 0 if nsel else 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
