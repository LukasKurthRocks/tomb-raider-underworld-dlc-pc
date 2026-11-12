"""Q105 (2026-11-12, group B): base-game play order per level with chapter starts and checkpoints (read-only).

Inputs (written by the q105 run, see docs/Befund-Gruppe-B-1211.md):
  PORTALS  tools/stream_unit_graph.py over the 81 extracted base units (lines '== unit ...' / '   -> target ...')
  INTROS   tools/manor_gate_scan.py intros ... --grep "checkpoint|cinematic_object" (lines '   intro N checkpoint ...
           +0x52 K script S')
  CALLS    work/b_nav_1211/q105_chapter_calls.txt (SetChapterUIData callers: 'script S' + 'owner: unit intro N' +
           'call (8,72)+0x6a54 fNone [level chapter]')
ORDER below is the play order chosen from the portal graph + the chapter starts; the script PROVES for every unit that
(a) it is a unit of the extracted set or one of the not-loadable names of the q105 TSV, (b) it has a portal to a unit
listed before it in the same level - except the first unit of a level and a unit that opens a chapter whose title card
caller (script 72) sits in that unit (a cutscene start), and (c) every extracted unit of the level is listed (nothing
lost). It then prints the kChapOrder rows for TruMenu (checkpoint intros of object 'checkpoint' per unit, ordered by
their +0x52 index, then id) and a markdown table.

Usage (from trudlcport): ../bin/pyt -t 300 work/b_nav_1211/q105_order_table.py PORTALS INTROS CALLS OUT_CPP OUT_MD
"""
import sys, re, collections

NOT_LOADABLE = {'l1_rutlands_ship_m1', 'l2_mapconnector', 'l2_puzzleconnector'}
# chapter (level, chapter) -> (DE, EN) title, generalbank script 72 table (work/menu17i_0811/s72_chapters_out.txt)
TITLE = {(1, 1): ('Der Weg nach Avalon', 'The Path to Avalon'), (1, 2): ('Niflheim', 'Niflheim'),
         (1, 3): ('Das Nordische Äquivalent', 'The Norse Connection'), (1, 4): ('Gott des Donners', 'God of Thunder'),
         (1, 5): ('Reich der Toten', 'Realm of the Dead'), (2, 1): ('Überreste', 'Remnants'),
         (2, 2): ('Bhogavati', 'Bhogavati'), (2, 3): ('Die Antike Welt', 'The Ancient World'),
         (2, 4): ('Keine Puppe mehr', 'Puppet No Longer'), (3, 1): ('Beschützt von den Toten', 'Protected by the Dead'),
         (4, 1): ('Die Unglückstage', 'The Unnamed Days'), (4, 2): ('Xibalbá', 'Xibalba'),
         (4, 3): ('Die Midgardschlange', 'The Midgard Serpent'), (4, 4): ('Land der Toten', 'Land of the Dead'),
         (5, 1): ('Tor der Toten', 'Gate of the Dead'), (5, 2): ('Walhall', 'Valhalla'), (6, 1): ('Alte Rituale', 'Rituals Old'),
         (7, 1): ('Helheim', 'Helheim'), (7, 2): ('Yggdrasil', 'Yggdrasil'), (7, 3): ('Keine Zeit', 'Out of Time')}
# play order: (unit, heading) - heading = None, a chapter key (level, chapter), or ('text', DE, EN)
LOOP = ('text', 'Rundweg ab l1_kraken_room (Richtung nicht in den Daten)', 'Loop from l1_kraken_room (direction not in the data)')
ORDER = {
    'Base game l1': [('l1_seatop', (1, 1)), ('l1_seafloor', None), ('l1_norse_hallway_a', (1, 2)), ('l1_kraken_entrance', None),
                     ('l1_krakenstairs_a', None), ('l1_krakenstairs_b', None), ('l1_kraken_room', None),
                     ('l1_baldrsstairs_a', LOOP), ('l1_baldrsstairs_b', None), ('l1_baldrs_tomb', (1, 3)),
                     ('l1_baldrs_sideroom', None), ('l1_baldrs_hall', None), ('l1_cineseatop', (1, 4)),
                     ('l1_ship_exterior', None), ('l1_ship_upper_hallway_a', None), ('l1_ship_upper_hallway_b', None),
                     ('l1_ship_upper_hallway', None), ('l1_ship_engine_hall', None), ('l1_ship_natla_room', (1, 5)),
                     ('l1_ship_lower_hallway', None), ('l1_ship_sinking_hall', None), ('l1_cine_ship_sinking', None),
                     ('l1_rutlands_ship_m1', None)],
    'Base game l2': [('l2_cliffclimb', (2, 1)), ('l2_cliffhall', None), ('l2_cliffhall_b', None), ('l2_junglehub', None),
                     ('l2_hubhall', None), ('l2_puzzleroom', (2, 2)), ('l2_norsehall', None), ('l2_norsehub', None),
                     ('l2_towerconnector', None), ('l2_towerroom', None), ('l2_upperhallway', None),
                     ('l2_shrineroom', (2, 3)), ('l2_maproom', (2, 4)), ('l2_flushtunnel', None),
                     ('l2_mapconnector', None), ('l2_puzzleconnector', None)],
    'Base game l3': [('l3_main_bedroom', ('text', 'Prolog (Croft Manor brennt)', 'Prologue (Croft Manor burning)')),
                     ('l3_bedroom_hall', None), ('l3_main_hall', None), ('l3_mansion_exterior_afterburn', None),
                     ('l3_caverns_start', (3, 1)), ('l3_chapel', None), ('l3_stairhall', None), ('l3_secretchamber', None),
                     ('l3_chamberrockhall', None)],
    'Base game l4': [('l4_trailstart', (4, 1)), ('l4_trailtube', None),
                     ('l4_ballcourt', ('text', 'Kapitel 4.2 Xibalbá + 4.3 Die Midgardschlange (beide in l4_ballcourt)',
                                       'Chapter 4.2 Xibalba + 4.3 The Midgard Serpent (both in l4_ballcourt)')),
                     ('l4_templepath', None),
                     ('l4_temple', None), ('l4_staircase_upper', None), ('l4_staircase_xibalba', None), ('l4_traprooms', None),
                     ('l4_staircase_mictlan', None), ('l4_ragnarok_room', None), ('l4_pool', (4, 4))],
    'Base game l5': [('l5_startsnow', (5, 1)), ('l5_valgrind_tunnel', None), ('l5_valgrind', (5, 2)),
                     ('l5_valaskjalf_entry', None), ('l5_valaskjalf_entryb', None), ('l5_valaskjalf', None)],
    'Base game l6': [('l6_ship_exterior', (6, 1)), ('l6_ship_upper_hallway_a', None), ('l6_ship_upper_hallway_b', None),
                     ('l6_ship_upper_hallway', None), ('l6_ship_engine_hall', None), ('l6_ship_natla_room', None)],
    'Base game l7': [('l7_thin_ice', (7, 1)), ('l7_arctic_sea', None), ('l7_helheim_hall01', None), ('l7_helheim_hall02', None),
                     ('l7_helheim01', (7, 2)), ('l7_helheim02', None), ('l7_helheim03', None), ('l7_yggdrasil', None),
                     ('l7_yggdrasil_hall01', None), ('l7_yggdrasil_hall02', None), ('l7_yggdrasil_end', (7, 3)),
                     ('l7_monastery', None), ('l7_himalaya_end', None)],
}
# where a chapter heading sits although its title-card caller is elsewhere (none; 4.2 / 4.3 share one heading text at
# l4_ballcourt, 1.2 has no unit-bound caller)
HEAD_AT_OTHER = {}
# callers owned by an intro that is neither a checkpoint nor a cinematic object (tools/manor_gate_scan.py intros without
# --grep, 2026-11-12): script 9934 = l2_shrineroom intro 2794 sa_uo_naga_statue, script 17329 = l5_valgrind intro 7332
# reveal_object. Script 5273 (1.2) is carried by 14 units and owned by no intro of them (a class script).
OWNER_EXTRA = {(2, 3): ('l2_shrineroom', 2794), (5, 2): ('l5_valgrind', 7332)}


def esc(s):
    """C string literal body: non-ASCII as octal UTF-8 escapes (the TruMenu rule)"""
    out = []
    for ch in s:
        if ord(ch) < 128:
            out.append('\\"' if ch == '"' else ch)
        else:
            out.extend('\\%03o' % b for b in ch.encode('utf-8'))
    return ''.join(out)


def main(portals, intros, calls, out_cpp, out_md):
    adj = collections.defaultdict(set)
    units = set()
    unit = None
    for line in open(portals, encoding='utf-8', errors='replace'):
        m = re.match(r'^== (\S+)\s', line)
        if m: unit = m.group(1); units.add(unit); continue
        m = re.match(r'^\s+-> (\S+)', line)
        if m and unit: adj[unit].add(m.group(1)); adj[m.group(1)].add(unit)
    cps = collections.defaultdict(list)
    unit = None
    for line in open(intros, encoding='utf-8', errors='replace'):
        m = re.match(r'^== (\S+):', line)
        if m: unit = m.group(1); continue
        m = re.match(r'^\s+intro\s+(\d+)\s+checkpoint\s.*\+0x52\s+(\d+)', line)
        if m: cps[unit].append((int(m.group(2)), int(m.group(1))))
    chap_unit = {}
    owner = None
    for line in open(calls, encoding='utf-8', errors='replace'):
        m = re.match(r'^\s+owner: (\S+) intro (\d+)', line)
        if m: owner = (m.group(1), int(m.group(2))); continue
        if line.startswith('script'): owner = None; continue
        m = re.match(r'^\s+call \(8,72\)\+0x6a54 fNone \[(\d+) (\d+)\]', line)
        if m: chap_unit.setdefault((int(m.group(1)), int(m.group(2))), owner)
    for k, v in OWNER_EXTRA.items():
        if chap_unit.get(k) is None: chap_unit[k] = v
    problems = []
    listed = set()
    rows, md = [], ['| Gruppe | # | Unit | Kapitel-Start (Skript 72) | CP | Checkpoint-Intros (+0x52-Reihenfolge) |',
                    '|---|---|---|---|---|---|']
    for group, order in ORDER.items():
        before = []
        for k, (u, head) in enumerate(order):
            listed.add(u)
            if u not in units and u not in NOT_LOADABLE: problems.append('%s: %s neither extracted nor a known not-loadable name' % (group, u))
            chap = head if isinstance(head, tuple) and len(head) == 2 else None
            caller = chap_unit.get(chap) if chap else None
            starts_here = caller is not None and caller[0] == u
            if k and u not in NOT_LOADABLE and not (adj[u] & set(before)) and not starts_here:
                problems.append('%s: %s has no portal to an earlier unit (%s)' % (group, u, ', '.join(sorted(adj[u]))))
            if chap and caller is not None and caller[0] != u and HEAD_AT_OTHER.get(chap) != caller[0]:
                problems.append('%s: chapter %d.%d heading at %s, title card caller in %s' % (group, chap[0], chap[1], u, caller[0]))
            before.append(u)
            ids = [i for _, i in sorted(cps.get(u, []))]
            if head is None: hd = ''
            elif head[0] == 'text': hd = '%s|%s' % (head[1], head[2])
            else:
                de, en = TITLE[head]
                where = ''
                if caller is None: where = ' (Start unklar: Klassen-Skript 5273)|%s (start unclear: class script 5273)' % ''
                elif caller[0] != u: where = ' (Start in %s)|%s (start in %s)' % (caller[0], '', caller[0])
                if where:
                    a, b = where.split('|')
                    hd = 'Kapitel %d.%d %s%s|Chapter %d.%d %s%s' % (head[0], head[1], de, a, head[0], head[1], en, b.replace('%s', ''))
                else:
                    hd = 'Kapitel %d.%d %s|Chapter %d.%d %s' % (head[0], head[1], de, head[0], head[1], en)
            rows.append('    {"%s", "%s", false, "%s", %s},' % (group, u, ' '.join(str(i) for i in ids),
                                                               '"%s"' % esc(hd) if hd else 'nullptr'))
            cs = ''
            if chap: cs = '%d.%d %s' % (chap[0], chap[1], TITLE[chap][0]) + (' (Intro %d in %s)' % (caller[1], caller[0]) if caller else ' (Klassen-Skript 5273, Unit offen)')
            md.append('| %s | %d | `%s`%s | %s | %d | %s |' % (group.replace('Base game ', ''), k + 1, u,
                      ' (nicht ladbar)' if u in NOT_LOADABLE else '', cs, len(ids), ' '.join(str(i) for i in ids) or '-'))
    for u in sorted(units - listed):
        problems.append('extracted unit %s is in no ORDER list' % u)
    open(out_cpp, 'w', encoding='utf-8', newline='\n').write('\n'.join(rows) + '\n')
    open(out_md, 'w', encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')
    n_cp = sum(len(cps.get(u, [])) for g in ORDER.values() for u, _ in g)
    print('%d groups, %d units listed (%d extracted, %d not loadable), %d checkpoints, %d chapter callers' % (
        len(ORDER), len(listed), len(units), len(listed & NOT_LOADABLE), n_cp, len(chap_unit)))
    for p in problems: print('PROBLEM ' + p)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:6]))
