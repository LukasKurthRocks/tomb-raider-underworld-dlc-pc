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
Q113 (2026-11-12, TruMenu 0.22.35): with CP_ORDER (work/q113_chain_1211/q113_cp_order.txt, 'unit TAB ids' from
q113_chain.py) the checkpoints of each unit come in WALKING order (entry portal -> exit portal) instead of +0x52 (group J:
+0x52 is no walking order); the script proves that every unit's id set is the same as before (nothing lost / added).

P5 (2026-11-13, TruMenu 0.22.37; docs/Befund-PaketR-Mittelmeer-1211.md, docs/Befund-P1-Mittelmeer-Objekte-1311.md): the
Paket R run (TruTrace SAVE lines 12.11. 20:35-22:50) corrects l1: CP 76 belongs to the RETURN visit of l1_kraken_room,
the tomb saves at the cinematic objects 160 (scene 50) and 42 (scene 51), the gate cinematic 696 and the kraken room
cinematic 84 save too, checkpoint_l1_going_in (672 / 673 / 781) saves on the way in, checkpoint_l1_going_out (674 / 675 /
782) on the way back; the return visits are rows of their own (visit 2). PAKET_R_FWD / PAKET_R_RET below; the script
PROVES that every id of a corrected or return row is an intro of that unit (object checkpoint* or cinematic_object in
INTROS) and that a unit's rows together still hold every one of its 'checkpoint' ids (nothing lost). With OUT_ROOMS it
writes the readable room names (DE / EN, kRoomNames rows) of every unit of the level list.

Usage (from trudlcport): ../bin/pyt -t 300 work/b_nav_1211/q105_order_table.py PORTALS INTROS CALLS OUT_CPP OUT_MD [CP_ORDER
[OUT_ROOMS]]
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
# Q113 (docs/Befund-Q113-Levelkette-1211.md): loop directions from the cutscene numbers (45 / 49 at the tomb door, then
# 50 / 51; puzzleroom 91 -> 92), the l4_temple side trip (group J: headdress key in 4.2), the prologue units come again
LOOP = ('text', 'Rundweg ab l1_kraken_room: Treppen -> Grab -> Seitenraum -> Halle -> zurück (Szenen 45 / 49 / 50, gefolgert)',
        'Loop from l1_kraken_room: stairs -> tomb -> side room -> hall -> back (cutscenes 45 / 49 / 50, inferred)')
LOOP2 = ('text', 'Rundweg ab l2_puzzleroom: norsehall -> Türme -> upperhallway -> zurück; zwei Türen = alternativ (gefolgert)',
         'Loop from l2_puzzleroom: norsehall -> towers -> upperhallway -> back; two doors = alternatives (inferred)')
TEMPLE = ('text', 'Abstecher in 4.2: Tempel (Kopfschmuck-Schlüssel), dann zurück zum Ballspielplatz',
          'Side trip in 4.2: temple (headdress key), then back to the ball court')
BACK = ('text', 'Rückweg zum Boot (Paket R): Kraken-Raum -> Treppen -> Eingang -> Gang -> Meeresgrund -> Boot',
        'Return to the boat (Paket R): kraken room -> stairs -> entrance -> hallway -> sea floor -> boat')
# P5 (Paket R, TruTrace SAVE lines 12.11.): walking order of the first visit where the run corrected Q113, and the
# return visits (visit 2) with the saves seen on the way back (ids space separated; '' = no save on that visit)
PAKET_R_FWD = {'l1_kraken_room': '75 84 56 58 77 78 74 73 46',     # 76 -> return visit; 84 = cinematic (scene 45) saves
               'l1_kraken_entrance': '672 673 696',               # going_in 672 / 673, gate cinematic 696 (title card 1.2)
               'l1_norse_hallway_a': '779 780 781',               # 781 checkpoint_l1_going_in at the exit portal
               'l1_baldrs_tomb': '140 72 160 42 141'}             # cinematics 160 (scene 50) / 42 (scene 51) save
PAKET_R_RET = {'l1_kraken_room': '76 75', 'l1_krakenstairs_b': '594 593', 'l1_krakenstairs_a': '634 633',
               'l1_kraken_entrance': '675 674', 'l1_norse_hallway_a': '782 779', 'l1_seafloor': '234', 'l1_seatop': ''}
ORDER = {
    'Base game l1': [('l1_seatop', (1, 1)), ('l1_seafloor', None), ('l1_norse_hallway_a', None), ('l1_kraken_entrance', (1, 2)),
                     ('l1_krakenstairs_a', None), ('l1_krakenstairs_b', None), ('l1_kraken_room', None),
                     ('l1_baldrsstairs_a', LOOP), ('l1_baldrsstairs_b', None), ('l1_baldrs_tomb', (1, 3)),
                     ('l1_baldrs_sideroom', None), ('l1_baldrs_hall', None),
                     ('l1_kraken_room', BACK, 2), ('l1_krakenstairs_b', None, 2), ('l1_krakenstairs_a', None, 2),
                     ('l1_kraken_entrance', None, 2), ('l1_norse_hallway_a', None, 2), ('l1_seafloor', None, 2),
                     ('l1_seatop', None, 2), ('l1_cineseatop', (1, 4)),
                     ('l1_ship_exterior', None), ('l1_ship_upper_hallway_a', None), ('l1_ship_upper_hallway_b', None),
                     ('l1_ship_upper_hallway', None), ('l1_ship_engine_hall', None), ('l1_ship_natla_room', (1, 5)),
                     ('l1_ship_lower_hallway', None), ('l1_ship_sinking_hall', None), ('l1_cine_ship_sinking', None),
                     ('l1_rutlands_ship_m1', None)],
    'Base game l2': [('l2_cliffclimb', (2, 1)), ('l2_cliffhall', None), ('l2_cliffhall_b', None), ('l2_junglehub', None),
                     ('l2_hubhall', None), ('l2_puzzleroom', (2, 2)), ('l2_norsehall', LOOP2), ('l2_norsehub', None),
                     ('l2_towerconnector', None), ('l2_towerroom', None), ('l2_upperhallway', None),
                     ('l2_shrineroom', (2, 3)), ('l2_maproom', (2, 4)), ('l2_flushtunnel', None),
                     ('l2_mapconnector', None), ('l2_puzzleconnector', None)],
    'Base game l3': [('l3_main_bedroom', ('text', 'Prolog (Croft Manor brennt; nach 3.1 dieselben 3 Units erneut)',
                                          'Prologue (Croft Manor burning; the same 3 units again after 3.1)')),
                     ('l3_bedroom_hall', None), ('l3_main_hall', None), ('l3_mansion_exterior_afterburn', None),
                     ('l3_caverns_start', (3, 1)), ('l3_chapel', None), ('l3_stairhall', None), ('l3_secretchamber', None),
                     ('l3_chamberrockhall', None)],
    'Base game l4': [('l4_trailstart', (4, 1)), ('l4_trailtube', None),
                     ('l4_ballcourt', ('text', 'Kapitel 4.2 Xibalbá + 4.3 Die Midgardschlange (beide in l4_ballcourt)',
                                       'Chapter 4.2 Xibalba + 4.3 The Midgard Serpent (both in l4_ballcourt)')),
                     ('l4_templepath', TEMPLE),
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
# l4_ballcourt)
HEAD_AT_OTHER = {}
# callers owned by an intro that is neither a checkpoint nor a cinematic object (tools/manor_gate_scan.py intros without
# --grep, 2026-11-12): script 9934 = l2_shrineroom intro 2794 sa_uo_naga_statue, script 17329 = l5_valgrind intro 7332
# reveal_object. Script 5273 (1.2) is carried by 14 units and owned by no intro of them: it is the level script of
# l1_kraken_entrance, its title-card function f2 is called by script 5321 f1 = l1_kraken_entrance intro 696
# cinematic_object +0x52 40 (gate cutscene; group J, docs/Befund-Gruppe-J-1211.md 2.1, work/j_data_1211/script_owner_refs.py).
OWNER_EXTRA = {(1, 2): ('l1_kraken_entrance', 696), (2, 3): ('l2_shrineroom', 2794), (5, 2): ('l5_valgrind', 7332)}
# P5 (TruMenu 0.22.37, owner wish: "Kraken-Raum" instead of l1_kraken_room on the labels): readable room names DE / EN of every
# unit of the level list - a plain reading of the unit name (the game has no room names), no game data
ROOMS = {
    'l1_seatop': ('Meeresoberfläche (Boot)', 'Sea surface (boat)'), 'l1_seafloor': ('Meeresgrund', 'Sea floor'),
    'l1_norse_hallway_a': ('Nordischer Gang', 'Norse hallway'), 'l1_kraken_entrance': ('Kraken-Eingang', 'Kraken entrance'),
    'l1_krakenstairs_a': ('Kraken-Treppe A', 'Kraken stairs A'), 'l1_krakenstairs_b': ('Kraken-Treppe B', 'Kraken stairs B'),
    'l1_kraken_room': ('Kraken-Raum', 'Kraken room'), 'l1_baldrsstairs_a': ('Baldr-Treppe A', 'Baldr stairs A'),
    'l1_baldrsstairs_b': ('Baldr-Treppe B', 'Baldr stairs B'), 'l1_baldrs_tomb': ('Baldrs Grab', "Baldr's tomb"),
    'l1_baldrs_sideroom': ('Baldr-Nebenraum', 'Baldr side room'), 'l1_baldrs_hall': ('Baldr-Halle', 'Baldr hall'),
    'l1_cineseatop': ('Meeresoberfläche (Szene)', 'Sea surface (cutscene)'),
    'l1_ship_exterior': ('Schiff außen', 'Ship exterior'),
    'l1_ship_upper_hallway_a': ('Schiff oberer Gang A', 'Ship upper hallway A'),
    'l1_ship_upper_hallway_b': ('Schiff oberer Gang B', 'Ship upper hallway B'),
    'l1_ship_upper_hallway': ('Schiff oberer Gang', 'Ship upper hallway'),
    'l1_ship_engine_hall': ('Schiff Maschinenhalle', 'Ship engine hall'),
    'l1_ship_natla_room': ('Schiff Natla-Raum', 'Ship Natla room'),
    'l1_ship_lower_hallway': ('Schiff unterer Gang', 'Ship lower hallway'),
    'l1_ship_sinking_hall': ('Schiff sinkende Halle', 'Ship sinking hall'),
    'l1_cine_ship_sinking': ('Schiff sinkt (Szene)', 'Ship sinking (cutscene)'),
    'l1_rutlands_ship_m1': ('Rutlands Schiff (nicht ladbar)', "Rutland's ship (not loadable)"),
    'l2_cliffclimb': ('Klippe', 'Cliff climb'), 'l2_cliffhall': ('Klippenhalle', 'Cliff hall'),
    'l2_cliffhall_b': ('Klippenhalle B', 'Cliff hall B'), 'l2_junglehub': ('Dschungel-Knoten', 'Jungle hub'),
    'l2_hubhall': ('Knotenhalle', 'Hub hall'), 'l2_puzzleroom': ('Rätselraum', 'Puzzle room'),
    'l2_norsehall': ('Nordische Halle', 'Norse hall'), 'l2_norsehub': ('Nordischer Knoten', 'Norse hub'),
    'l2_towerconnector': ('Turm-Verbindung', 'Tower connector'), 'l2_towerroom': ('Turmraum', 'Tower room'),
    'l2_upperhallway': ('Oberer Gang', 'Upper hallway'), 'l2_shrineroom': ('Schreinraum', 'Shrine room'),
    'l2_maproom': ('Kartenraum', 'Map room'), 'l2_flushtunnel': ('Spültunnel', 'Flush tunnel'),
    'l2_mapconnector': ('Karten-Verbindung (nicht ladbar)', 'Map connector (not loadable)'),
    'l2_puzzleconnector': ('Rätsel-Verbindung (nicht ladbar)', 'Puzzle connector (not loadable)'),
    'l3_main_bedroom': ('Schlafzimmer', 'Main bedroom'), 'l3_bedroom_hall': ('Flur am Schlafzimmer', 'Bedroom hall'),
    'l3_main_hall': ('Eingangshalle', 'Main hall'),
    'l3_mansion_exterior_afterburn': ('Anwesen außen (nach dem Brand)', 'Mansion exterior (after the fire)'),
    'l3_caverns_start': ('Höhlen-Start', 'Caverns start'), 'l3_chapel': ('Kapelle', 'Chapel'),
    'l3_stairhall': ('Treppenhalle', 'Stair hall'), 'l3_secretchamber': ('Geheimkammer', 'Secret chamber'),
    'l3_chamberrockhall': ('Felskammer-Halle', 'Chamber rock hall'),
    'l4_trailstart': ('Pfad-Start', 'Trail start'), 'l4_trailtube': ('Pfad-Röhre', 'Trail tube'),
    'l4_ballcourt': ('Ballspielplatz', 'Ball court'), 'l4_templepath': ('Tempelpfad', 'Temple path'),
    'l4_temple': ('Tempel', 'Temple'), 'l4_staircase_upper': ('Obere Treppe', 'Upper staircase'),
    'l4_staircase_xibalba': ('Xibalbá-Treppe', 'Xibalba staircase'), 'l4_traprooms': ('Fallenräume', 'Trap rooms'),
    'l4_staircase_mictlan': ('Mictlan-Treppe', 'Mictlan staircase'), 'l4_ragnarok_room': ('Ragnarök-Raum', 'Ragnarok room'),
    'l4_pool': ('Becken', 'Pool'),
    'l5_startsnow': ('Schnee-Start', 'Snow start'), 'l5_valgrind_tunnel': ('Valgrind-Tunnel', 'Valgrind tunnel'),
    'l5_valgrind': ('Valgrind', 'Valgrind'), 'l5_valaskjalf_entry': ('Valaskjalf-Eingang', 'Valaskjalf entry'),
    'l5_valaskjalf_entryb': ('Valaskjalf-Eingang B', 'Valaskjalf entry B'), 'l5_valaskjalf': ('Valaskjalf', 'Valaskjalf'),
    'l6_ship_exterior': ('Schiff außen', 'Ship exterior'),
    'l6_ship_upper_hallway_a': ('Schiff oberer Gang A', 'Ship upper hallway A'),
    'l6_ship_upper_hallway_b': ('Schiff oberer Gang B', 'Ship upper hallway B'),
    'l6_ship_upper_hallway': ('Schiff oberer Gang', 'Ship upper hallway'),
    'l6_ship_engine_hall': ('Schiff Maschinenhalle', 'Ship engine hall'),
    'l6_ship_natla_room': ('Schiff Natla-Raum', 'Ship Natla room'),
    'l7_thin_ice': ('Dünnes Eis', 'Thin ice'), 'l7_arctic_sea': ('Arktisches Meer', 'Arctic sea'),
    'l7_helheim_hall01': ('Helheim-Halle 1', 'Helheim hall 1'), 'l7_helheim_hall02': ('Helheim-Halle 2', 'Helheim hall 2'),
    'l7_helheim01': ('Helheim 1', 'Helheim 1'), 'l7_helheim02': ('Helheim 2', 'Helheim 2'),
    'l7_helheim03': ('Helheim 3', 'Helheim 3'), 'l7_yggdrasil': ('Yggdrasil', 'Yggdrasil'),
    'l7_yggdrasil_hall01': ('Yggdrasil-Halle 1', 'Yggdrasil hall 1'),
    'l7_yggdrasil_hall02': ('Yggdrasil-Halle 2', 'Yggdrasil hall 2'),
    'l7_yggdrasil_end': ('Yggdrasil-Ende', 'Yggdrasil end'), 'l7_monastery': ('Kloster', 'Monastery'),
    'l7_himalaya_end': ('Himalaya (Ende)', 'Himalaya (end)'),
    # DLC units (TruMenu kUnits groups DLC 1 / DLC 2 / other starts)
    'dlc_level1_start': ('DLC 1 Start', 'DLC 1 start'), 'dlc_caverns': ('Höhlen', 'Caverns'),
    'dlc_caverns_hall': ('Höhlenhalle', 'Caverns hall'), 'dlc_water_wheel': ('Wasserrad', 'Water wheel'),
    'dlc_pillory': ('Pranger', 'Pillory'), 'dlc_dungeonhalla': ('Kerkerhalle A', 'Dungeon hall A'),
    'dlc_dungeonhallb': ('Kerkerhalle B', 'Dungeon hall B'), 'dlc_watertunnel': ('Wassertunnel', 'Water tunnel'),
    'dlc_dungeon': ('Kerker', 'Dungeon'), 'dlc_treasureroom': ('Schatzkammer', 'Treasure room'),
    'dlc_level1_left': ('DLC 1 links (ungenutzt)', 'DLC 1 left (unused)'),
    'dlc_level1_right': ('DLC 1 rechts (ungenutzt)', 'DLC 1 right (unused)'),
    'dlc_level2_start': ('DLC 2 Start', 'DLC 2 start'), 'dlc_yggdrasil_hall01': ('Yggdrasil-Halle 1', 'Yggdrasil hall 1'),
    'dlc_yggdrasil_hall02': ('Yggdrasil-Halle 2', 'Yggdrasil hall 2'), 'dlc_yggdrasil_end': ('Yggdrasil-Ende', 'Yggdrasil end'),
    'dlc2_ceremony_room': ('Zeremonienraum', 'Ceremony room'),
    'dlc2_hall_machine_ceremony': ('Gang Maschine - Zeremonie', 'Hall machine - ceremony'),
    'dlc2_machine_room': ('Maschinenraum', 'Machine room'),
    'dlc2_hall_goo_machine': ('Gang Schleim - Maschine', 'Hall goo - machine'), 'dlc2_goo_room': ('Schleimraum', 'Goo room'),
    'dlc2_hall_ceremony_goo': ('Gang Zeremonie - Schleim', 'Hall ceremony - goo'),
    'dlc2_treasure_room_cine': ('Schatzkammer (Szene)', 'Treasure room (cutscene)'),
    'dlc_level3_start': ('DLC 3 Start (ungenutzt)', 'DLC 3 start (unused)'),
    'dlc_level4_start': ('DLC 4 Start (ungenutzt)', 'DLC 4 start (unused)'),
    'dlc_level5_start': ('DLC 5 Start (ungenutzt)', 'DLC 5 start (unused)'),
    'dlc_level6_start': ('DLC 6 Start (ungenutzt)', 'DLC 6 start (unused)'),
}


def esc(s):
    """C string literal body: non-ASCII as octal UTF-8 escapes (the TruMenu rule)"""
    out = []
    for ch in s:
        if ord(ch) < 128:
            out.append('\\"' if ch == '"' else ch)
        else:
            out.extend('\\%03o' % b for b in ch.encode('utf-8'))
    return ''.join(out)


def main(portals, intros, calls, out_cpp, out_md, cp_order=None, out_rooms=None):
    walk = {}
    if cp_order:            # Q113: unit TAB checkpoint ids in walking order
        for line in open(cp_order, encoding='utf-8'):
            if line.startswith('#') or not line.strip(): continue
            u, _, ids = line.rstrip('\n').partition('\t')
            walk[u] = [int(x) for x in ids.split()]
    adj = collections.defaultdict(set)
    units = set()
    unit = None
    for line in open(portals, encoding='utf-8', errors='replace'):
        m = re.match(r'^== (\S+)\s', line)
        if m: unit = m.group(1); units.add(unit); continue
        m = re.match(r'^\s+-> (\S+)', line)
        if m and unit: adj[unit].add(m.group(1)); adj[m.group(1)].add(unit)
    cps = collections.defaultdict(list)
    saves = collections.defaultdict(dict)   # P5: unit -> intro id -> object (checkpoint* / cinematic_object)
    unit = None
    for line in open(intros, encoding='utf-8', errors='replace'):
        m = re.match(r'^== (\S+):', line)
        if m: unit = m.group(1); continue
        m = re.match(r'^\s+intro\s+(\d+)\s+checkpoint\s.*\+0x52\s+(\d+)', line)
        if m: cps[unit].append((int(m.group(2)), int(m.group(1))))
        m = re.match(r'^\s+intro\s+(\d+)\s+(checkpoint\S*|cinematic_object)\s', line)
        if m: saves[unit][int(m.group(1))] = m.group(2)
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
    rows, md = [], ['| Gruppe | # | Unit | Kapitel-Start (Skript 72) | CP | Checkpoint-Intros (%s) |' % (
                        'Laufrichtung, Q113' if cp_order else '+0x52-Reihenfolge'),
                    '|---|---|---|---|---|---|']
    n_fix = n_ret = n_added = 0
    for group, order in ORDER.items():
        before = []
        for k, entry in enumerate(order):
            u, head = entry[0], entry[1]
            visit = entry[2] if len(entry) > 2 else 1
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
            if cp_order:
                if u not in walk: problems.append('%s: %s missing in %s' % (group, u, cp_order))
                elif sorted(walk[u]) != sorted(ids): problems.append('%s: %s walking order %s is not the id set %s' % (group, u, walk[u], ids))
                else: ids = walk[u]
            # P5 (Paket R): corrected first visits and the return visits; every id must be a save intro of the unit, the
            # unit's rows together must keep every 'checkpoint' id
            fix = PAKET_R_RET.get(u) if visit == 2 else PAKET_R_FWD.get(u) if cp_order else None
            if visit == 2 and fix is None: problems.append('%s: %s visit 2 without PAKET_R_RET' % (group, u))
            if fix is not None and cp_order:
                new = [int(x) for x in fix.split()]
                bad = [i for i in new if i not in saves.get(u, {})]
                if bad: problems.append('%s: %s Paket R ids %s are no checkpoint* / cinematic_object intro of the unit' % (group, u, bad))
                if visit == 1:
                    lost = sorted(set(ids) - set(new) - set(int(x) for x in PAKET_R_RET.get(u, '').split()))
                    if lost: problems.append('%s: %s Paket R rows lose checkpoint ids %s' % (group, u, lost))
                    n_added += len(set(new) - set(ids))
                    n_fix += 1
                else:
                    n_ret += 1
                ids = new
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
            rows.append('    {"%s", "%s", false, "%s", %s%s},' % (group, u, ' '.join(str(i) for i in ids),
                                                                 '"%s"' % esc(hd) if hd else 'nullptr',
                                                                 ', %d' % visit if visit > 1 else ''))
            cs = ''
            if chap: cs = '%d.%d %s' % (chap[0], chap[1], TITLE[chap][0]) + (' (Intro %d in %s)' % (caller[1], caller[0]) if caller else ' (Klassen-Skript 5273, Unit offen)')
            md.append('| %s | %d | `%s`%s%s | %s | %d | %s |' % (group.replace('Base game ', ''), k + 1, u,
                      ' (nicht ladbar)' if u in NOT_LOADABLE else '', ' (Rückweg)' if visit > 1 else '', cs, len(ids),
                      ' '.join(str(i) + ('' if saves.get(u, {}).get(i, 'checkpoint') == 'checkpoint' else
                                         ' (%s)' % saves[u][i]) for i in ids) or '-'))
    for u in sorted(units - listed):
        problems.append('extracted unit %s is in no ORDER list' % u)
    open(out_cpp, 'w', encoding='utf-8', newline='\n').write('\n'.join(rows) + '\n')
    open(out_md, 'w', encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')
    if out_rooms:           # P5: kRoomNames rows of every unit of the level list (base ORDER + the DLC names)
        base = [u for g in ORDER.values() for u in dict.fromkeys(e[0] for e in g)]
        missing = [u for u in base if u not in ROOMS]
        if missing: problems.append('ROOMS lacks %s' % ', '.join(missing))
        open(out_rooms, 'w', encoding='utf-8', newline='\n').write(''.join(
            '    {"%s", "%s", "%s"},\n' % (u, esc(de), esc(en)) for u, (de, en) in ROOMS.items()))
        print('P5: %d room names (%d base units), %d Paket R rows corrected (%d save ids added), %d return rows' % (
            len(ROOMS), len(base), n_fix, n_added, n_ret))
    n_cp = sum(len(cps.get(e[0], [])) for g in ORDER.values() for e in g if len(e) < 3)
    print('%d groups, %d units listed (%d extracted, %d not loadable), %d checkpoints, %d chapter callers' % (
        len(ORDER), len(listed), len(units), len(listed & NOT_LOADABLE), n_cp, len(chap_unit)))
    for p in problems: print('PROBLEM ' + p)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:8]))
