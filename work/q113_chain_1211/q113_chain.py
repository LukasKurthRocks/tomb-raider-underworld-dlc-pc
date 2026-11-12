"""Q113 (2026-11-12): the complete base-game level chain without "rings" (read-only, data only).

The owner's rule: Lara's entry point per area (level load = player start / chapter-start cinematic) plus the END triggers
(portal to the next unit, level change by script) give the direction through every "ring"; two parallel corridors are
ALTERNATIVES (both listed, marked), and where the data stays ambiguous the list order is kept (marked 🔶).

CHAIN below is the play order as a list of VISITS (a unit can be visited more than once: way back, side trip). The
script PROVES what can be proved from the data and prints a problem otherwise:
  P1  every visit enters / leaves through a portal the unit really has (tools/stream_unit_graph.py output), or through a
      level load (START), a level change (LEVEL:<unit>, the script calls uigamedata f27 - q113_level_links.txt) or END;
  P2  consecutive visits fit together (leave of k = unit of k+1, enter of k+1 = unit of k; LEVEL:<x> -> next area
      starts in x);
  P3  every cinematic_object of all 81 units is claimed by exactly one visit (its own unit, or a portal neighbour for a
      cinematic placed at the shared portal), and the claimed cinematic numbers (+0x52 = story order, group J 2.2) never
      go down along the chain (listed exceptions: a number used twice);
  P4  every extracted unit is visited;
  P5  every chapter heading sits at the unit of its title-card caller (script 72, q105_chapter_calls.txt + the
      callers owned by no cinematic: 1.2 / 2.3 / 5.2, groups B / J);
  P6  every LEVEL:<x> leave has a level-change caller in that unit whose target is x (q113_level_links.txt).
Then per visit the checkpoints (object 'checkpoint') in WALKING order: key = d_in / (d_in + d_out) with d = 3D distance
to the entry portal / exit portal (START: the player intro or the start cinematic; LEVEL / END: the last claimed
cinematic; side trip with entry = exit: d_in only). A unit visited twice gives each checkpoint to the visit whose path
it lies nearest to (detour d_in + d_out - |in - out|; ties = the earlier visit) - marked 🔶.

Outputs: OUT_MD (markdown table area -> visit -> checkpoints, proof column), OUT_CP (unit TAB checkpoint ids in walking
order, input of the TruMenu generator work/b_nav_1211/q105_order_table.py), OUT_R (Paket R expectation, TSV).

Usage (from trudlcport):
  ../bin/pyt -t 300 work/q113_chain_1211/q113_chain.py INTROS PORTALS LINKS CALLS OUT_MD OUT_CP OUT_R
"""
import sys, os, re, math, collections

# ---- the chain ------------------------------------------------------------------------------------------------------
# V(unit, enter, leave, cines, head, sure, proof, alt)
#   enter: 'START' (level load) or the unit Lara comes from; leave: next unit, 'LEVEL:<unit>' or 'END'
#   cines: claimed cinematic numbers (own unit first, then portal neighbours)
#   head : chapter (level, chapter) or ('text', DE)
#   sure : '✅' (the data fixes it) or '🔶' (inferred, reason in proof)
#   alt  : text of an alternative way (parallel corridor / second door), listed in the table


def V(unit, enter, leave, cines=(), head=None, sure='✅', proof='', alt=''):
    return dict(unit=unit, enter=enter, leave=leave, cines=list(cines), head=head, sure=sure, proof=proof, alt=alt)


BACK = 'Rückweg (einziger Weg zum nächsten Ziel), Checkpoints s. Hinweg'
CHAIN = collections.OrderedDict()
CHAIN['Prolog (l3, Croft Manor brennt)'] = [
    V('l3_main_bedroom', 'START', 'l3_bedroom_hall', [1], ('text', 'Prolog', 'Prologue'), proof='neues Spiel; Szene 1 (Intro 4483)'),
    V('l3_bedroom_hall', 'l3_main_bedroom', 'l3_main_hall'),
    V('l3_main_hall', 'l3_bedroom_hall', 'LEVEL:l1_seatop', [10],
      proof='Szene 10 (Intro 4106, Skript 11568 f0): uigamedata f27, Text "SPECIAL LOAD INTO LEVEL L1_SEATOP"'),
]
CHAIN['l1 Mittelmeer'] = [
    V('l1_seatop', 'START', 'l1_seafloor', [30], (1, 1), proof='Levelstart; Szene 30 = Titelkarte 1.1'),
    V('l1_seafloor', 'l1_seatop', 'l1_norse_hallway_a'),
    V('l1_norse_hallway_a', 'l1_seafloor', 'l1_kraken_entrance'),
    V('l1_kraken_entrance', 'l1_norse_hallway_a', 'l1_krakenstairs_a', [40], (1, 2),
      proof='Szene 40 (Intro 696, Eingangstor) 26 m vor dem Portal zu krakenstairs_a = Titelkarte 1.2 (Skript 5321 f1 -> 5273 f2)'),
    V('l1_krakenstairs_a', 'l1_kraken_entrance', 'l1_krakenstairs_b'),
    V('l1_krakenstairs_b', 'l1_krakenstairs_a', 'l1_kraken_room'),
    V('l1_kraken_room', 'l1_krakenstairs_b', 'l1_baldrsstairs_a', [45, 49], sure='🔶',
      proof='Ring aufgelöst: Szene 45 an der Seite von krakenstairs_b (Ankunft), Szene 49 + Grabtür ms_ani_tombdoor 29 m am '
            'Portal baldrsstairs_a -> Tür öffnet erst nach dem Kraken-Rätsel; danach 50 / 51 im Grab'),
    V('l1_baldrsstairs_a', 'l1_kraken_room', 'l1_baldrsstairs_b', sure='🔶', proof='Ring-Richtung wie oben'),
    V('l1_baldrsstairs_b', 'l1_baldrsstairs_a', 'l1_baldrs_tomb', sure='🔶', proof='Ring-Richtung wie oben'),
    V('l1_baldrs_tomb', 'l1_baldrsstairs_b', 'l1_baldrs_sideroom', [50, 51], (1, 3), sure='🔶',
      proof='Szene 50 = Titelkarte 1.3 (Panzerhandschuh), Ebene 224 -> Szene 51 + Sticky 43 (Q73); Ausgang = zweites Portal'),
    V('l1_baldrs_sideroom', 'l1_baldrs_tomb', 'l1_baldrs_hall', sure='🔶', proof='Ring-Richtung wie oben'),
    V('l1_baldrs_hall', 'l1_baldrs_sideroom', 'l1_kraken_room', sure='🔶',
      proof='Ring schließt sich: Halle -> obere Ebene des Kraken-Raums (Portal z 5827)'),
    V('l1_kraken_room', 'l1_baldrs_hall', 'l1_krakenstairs_b', sure='🔶', proof=BACK + ' (Boot nur über seafloor -> seatop)'),
    V('l1_krakenstairs_b', 'l1_kraken_room', 'l1_krakenstairs_a', sure='🔶', proof=BACK),
    V('l1_krakenstairs_a', 'l1_krakenstairs_b', 'l1_kraken_entrance', sure='🔶', proof=BACK),
    V('l1_kraken_entrance', 'l1_krakenstairs_a', 'l1_norse_hallway_a', sure='🔶', proof=BACK),
    V('l1_norse_hallway_a', 'l1_kraken_entrance', 'l1_seafloor', sure='🔶', proof=BACK),
    V('l1_seafloor', 'l1_norse_hallway_a', 'l1_seatop', sure='🔶', proof=BACK),
    V('l1_seatop', 'l1_seafloor', 'l1_cineseatop', sure='🔶',
      proof='Boot-Volumen 1840 (OnIn, nur mit Sticky 43 aus dem Grab) spielt Szene 52 in l1_cineseatop (Q73); '
            'Wechsel in die Szenen-Unit: Portal oder Szene - Live-Log klärt'),
    V('l1_cineseatop', 'l1_seatop', 'l1_ship_exterior', [52], (1, 4), proof='Szene 52 (Intro 1780, Skript 8003) = Titelkarte 1.4'),
    V('l1_ship_exterior', 'l1_cineseatop', 'l1_ship_upper_hallway_a'),
    V('l1_ship_upper_hallway_a', 'l1_ship_exterior', 'l1_ship_upper_hallway_b'),
    V('l1_ship_upper_hallway_b', 'l1_ship_upper_hallway_a', 'l1_ship_upper_hallway'),
    V('l1_ship_upper_hallway', 'l1_ship_upper_hallway_b', 'l1_ship_engine_hall', [55], proof='Szene 55 6 m vor engine_hall'),
    V('l1_ship_engine_hall', 'l1_ship_upper_hallway', 'l1_ship_natla_room'),
    V('l1_ship_natla_room', 'l1_ship_engine_hall', 'l1_ship_lower_hallway', [60], (1, 5), proof='Szene 60 = Titelkarte 1.5'),
    V('l1_ship_lower_hallway', 'l1_ship_natla_room', 'l1_ship_sinking_hall'),
    V('l1_ship_sinking_hall', 'l1_ship_lower_hallway', 'l1_cine_ship_sinking'),
    V('l1_cine_ship_sinking', 'l1_ship_sinking_hall', 'LEVEL:l2_cliffclimb', [70],
      proof='Szene 70 (Intro 1005, Skript 6003 f0): uigamedata f27 "l2_cliffclimb"'),
]
CHAIN['l2 Thailand'] = [
    V('l2_cliffclimb', 'START', 'l2_cliffhall', [80], (2, 1), proof='Levelstart; Szene 80 = Titelkarte 2.1'),
    V('l2_cliffhall', 'l2_cliffclimb', 'l2_cliffhall_b'),
    V('l2_cliffhall_b', 'l2_cliffhall', 'l2_junglehub', sure='🔶',
      proof='Checkpoint 3681 38 m am Portal junglehub, keiner am Direkt-Portal hubhall (>= 211 m)',
      alt='alternativ: cliffhall_b -> hubhall direkt (eigenes Portal, ohne Checkpoint dort)'),
    V('l2_junglehub', 'l2_cliffhall_b', 'l2_hubhall', sure='🔶', proof='Spieler-Intro 47 m am Portal cliffhall_b',
      alt='alternativ übersprungen (Direkt-Portal cliffhall_b -> hubhall)'),
    V('l2_hubhall', 'l2_junglehub', 'l2_puzzleroom', sure='🔶', proof='Checkpoint 3098 11 m / Spieler-Intro 12 m am Portal junglehub'),
    V('l2_puzzleroom', 'l2_hubhall', 'l2_norsehall', [90, 91], (2, 2), sure='🔶',
      proof='Szene 90 31 m vom Eingang hubhall = Titelkarte 2.2; Szene 91 auf der unteren Ebene (z -16953) bei den zwei '
            'Türen zu norsehall (z -15852 / -15506), danach 92 in norsehall',
      alt='zwei parallele Türen puzzleroom -> norsehall (Portale 2 / 3, je ein Checkpoint 2827 / 2826 davor) = alternativ'),
    V('l2_norsehall', 'l2_puzzleroom', 'l2_norsehub', [92], sure='🔶', proof='Szene 92; Eingangs-Checkpoints 2454 / 2453 je an einer Tür',
      alt='Eingang durch Tür links oder rechts (alternativ)'),
    V('l2_norsehub', 'l2_norsehall', 'l2_towerconnector', [92], sure='🔶', proof='Szene 92 (gleiche Nummer wie norsehall)'),
    V('l2_towerconnector', 'l2_norsehub', 'l2_towerroom', sure='🔶', proof='Ring-Richtung aus 91 -> 92 (keine Szene in den Türmen)'),
    V('l2_towerroom', 'l2_towerconnector', 'l2_upperhallway', sure='🔶', proof='Ring-Richtung wie oben'),
    V('l2_upperhallway', 'l2_towerroom', 'l2_puzzleroom', sure='🔶', proof='Ring schließt sich: obere Ebene des Rätselraums (Portal z -9913)'),
    V('l2_puzzleroom', 'l2_upperhallway', 'l2_shrineroom', sure='🔶', proof='zurück im Rätselraum; Portal shrineroom unten (z -15483)'),
    V('l2_shrineroom', 'l2_puzzleroom', 'l2_maproom', head=(2, 3), proof='Titelkarte 2.3 = Skript 9934 (Intro 2794 sa_uo_naga_statue)'),
    V('l2_maproom', 'l2_shrineroom', 'l2_flushtunnel', [95, 100, 105], (2, 4),
      proof='Szenen 95 (73 m vom Eingang) -> 100 -> 105 (60 m vor flushtunnel) = Titelkarte 2.4: Richtung belegt'),
    V('l2_flushtunnel', 'l2_maproom', 'l2_cliffclimb'),
    V('l2_cliffclimb', 'l2_flushtunnel', 'LEVEL:l3_caverns_start', [110],
      proof='Szene 110 (Intro 2565, Skript 9515 f1): uigamedata f27 "l3_caverns_start"'),
]
CHAIN['l3 Croft Manor'] = [
    V('l3_caverns_start', 'START', 'l3_chapel', [120], (3, 1), proof='Levelstart; Szene 120 = Titelkarte 3.1'),
    V('l3_chapel', 'l3_caverns_start', 'l3_stairhall'),
    V('l3_stairhall', 'l3_chapel', 'l3_secretchamber'),
    V('l3_secretchamber', 'l3_stairhall', 'l3_chamberrockhall', [130, 145], proof='Szene 145 10 m vor chamberrockhall'),
    V('l3_chamberrockhall', 'l3_secretchamber', 'l3_main_bedroom',
      proof='Hebel 4617 -> Geheimtür 4528 (l3_main_bedroom), Volumen 4619 setzt Szene 1 zurück (Q73)'),
    V('l3_main_bedroom', 'l3_chamberrockhall', 'l3_bedroom_hall', sure='🔶',
      proof='zweiter Besuch: Szene 1 erneut (zurückgesetzt, keine neue Nummer), Unit-Skript 12059 "level zero is done"'),
    V('l3_bedroom_hall', 'l3_main_bedroom', 'l3_main_hall', sure='🔶', proof='zweiter Besuch'),
    V('l3_main_hall', 'l3_bedroom_hall', 'l3_mansion_exterior_afterburn', [150, 160], proof='Szenen 150 / 160 (Rückkehr)'),
    V('l3_mansion_exterior_afterburn', 'l3_main_hall', 'LEVEL:l4_trailstart', [170],
      proof='Szene 170 (Intro 4070, Skript 11393 f4): uigamedata f27 "L4_trailstart"'),
]
CHAIN['l4 Mexiko'] = [
    V('l4_trailstart', 'START', 'l4_trailtube', [180], (4, 1), proof='Levelstart; Szene 180 = Titelkarte 4.1'),
    V('l4_trailtube', 'l4_trailstart', 'l4_ballcourt'),
    V('l4_ballcourt', 'l4_trailtube', 'l4_templepath', [185, 186], (4, 2), sure='🔶',
      proof='Szenen 185 / 186 = Titelkarte 4.2; Abstecher zum Tempel in 4.2 (Kopfschmuck-Schlüssel, Gruppe J), Reihenfolge '
            'der vier Kalender-Teile frei'),
    V('l4_templepath', 'l4_ballcourt', 'l4_temple', sure='🔶', proof='Abstecher (Sackgasse)'),
    V('l4_temple', 'l4_templepath', 'l4_templepath', sure='🔶', proof='Sackgasse: nur ein Portal'),
    V('l4_templepath', 'l4_temple', 'l4_ballcourt', sure='🔶', proof='Rückweg vom Abstecher'),
    V('l4_ballcourt', 'l4_templepath', 'l4_staircase_upper', [190], (4, 3),
      proof='Szene 190 (52 m vor staircase_upper) = Titelkarte 4.3; Weg nach Xibalbá offen nach "both calendars solved"'),
    V('l4_staircase_upper', 'l4_ballcourt', 'l4_staircase_xibalba'),
    V('l4_staircase_xibalba', 'l4_staircase_upper', 'l4_traprooms'),
    V('l4_traprooms', 'l4_staircase_xibalba', 'l4_staircase_mictlan', [195]),
    V('l4_staircase_mictlan', 'l4_traprooms', 'l4_ragnarok_room'),
    V('l4_ragnarok_room', 'l4_staircase_mictlan', 'l4_pool'),
    V('l4_pool', 'l4_ragnarok_room', 'l4_ragnarok_room', [198, 200, 210], (4, 4), sure='🔶',
      proof='Szenen 198 (pool) -> 200 (ragnarok_room, 31 m am Pool-Portal) -> 210 = Titelkarte 4.4; Sackgasse'),
    V('l4_ragnarok_room', 'l4_pool', 'l4_staircase_mictlan', sure='🔶',
      proof='Rückweg zum Ballspielplatz (Szene 220 dort, 47 m am Portal staircase_upper); kein Level-Wechsel in pool / '
            'ragnarok_room - ob gelaufen oder per Szene versetzt: Live-Log'),
    V('l4_staircase_mictlan', 'l4_ragnarok_room', 'l4_traprooms', sure='🔶', proof='Rückweg wie oben'),
    V('l4_traprooms', 'l4_staircase_mictlan', 'l4_staircase_xibalba', sure='🔶', proof='Rückweg wie oben'),
    V('l4_staircase_xibalba', 'l4_traprooms', 'l4_staircase_upper', sure='🔶', proof='Rückweg wie oben'),
    V('l4_staircase_upper', 'l4_staircase_xibalba', 'l4_ballcourt', sure='🔶', proof='Rückweg wie oben'),
    V('l4_ballcourt', 'l4_staircase_upper', 'LEVEL:l5_startsnow', [220],
      proof='Szene 220 (Intro 5483, Skript 13923 f1): uigamedata f27 "L5_startsnow"'),
]
CHAIN['l5 Jan Mayen'] = [
    V('l5_startsnow', 'START', 'l5_valgrind_tunnel', [230], (5, 1), proof='Levelstart; Szene 230 = Titelkarte 5.1'),
    V('l5_valgrind_tunnel', 'l5_startsnow', 'l5_valgrind'),
    V('l5_valgrind', 'l5_valgrind_tunnel', 'l5_valaskjalf_entry', [235, 240], (5, 2),
      proof='Szene 235 61 m am Eingang, 240 65 m vor valaskjalf_entry; Titelkarte 5.2 = Skript 17329 (Intro 7332 reveal_object)'),
    V('l5_valaskjalf_entry', 'l5_valgrind', 'l5_valaskjalf_entryb', [230], proof='Intro 7295 trägt die Nummer 230 ein zweites Mal'),
    V('l5_valaskjalf_entryb', 'l5_valaskjalf_entry', 'l5_valaskjalf'),
    V('l5_valaskjalf', 'l5_valaskjalf_entryb', 'LEVEL:l6_ship_exterior', [242, 245, 250],
      proof='Szene 250 (Intro 6846, Skript 16274 f1): uigamedata f27 "L6_ship_exterior"'),
]
CHAIN['l6 Andamanensee'] = [
    V('l6_ship_exterior', 'START', 'l6_ship_upper_hallway_a', [260], (6, 1), proof='Levelstart; Szene 260 = Titelkarte 6.1'),
    V('l6_ship_upper_hallway_a', 'l6_ship_exterior', 'l6_ship_upper_hallway_b'),
    V('l6_ship_upper_hallway_b', 'l6_ship_upper_hallway_a', 'l6_ship_upper_hallway'),
    V('l6_ship_upper_hallway', 'l6_ship_upper_hallway_b', 'l6_ship_engine_hall'),
    V('l6_ship_engine_hall', 'l6_ship_upper_hallway', 'l6_ship_natla_room'),
    V('l6_ship_natla_room', 'l6_ship_engine_hall', 'LEVEL:l7_thin_ice', [270],
      proof='Szene 270 (Intro 1387, Skript 7017 f0): uigamedata f27 "L7_thin_ice"'),
]
CHAIN['l7 Arktisches Meer'] = [
    V('l7_thin_ice', 'START', 'l7_arctic_sea', [275], (7, 1), proof='Levelstart; Szene 275 = Titelkarte 7.1'),
    V('l7_arctic_sea', 'l7_thin_ice', 'l7_helheim_hall01'),
    V('l7_helheim_hall01', 'l7_arctic_sea', 'l7_helheim_hall02'),
    V('l7_helheim_hall02', 'l7_helheim_hall01', 'l7_helheim01'),
    V('l7_helheim01', 'l7_helheim_hall02', 'l7_helheim02', [280, 290], (7, 2), proof='Szene 290 = Titelkarte 7.2, 49 m vor helheim02'),
    V('l7_helheim02', 'l7_helheim01', 'l7_helheim03'),
    V('l7_helheim03', 'l7_helheim02', 'l7_yggdrasil'),
    V('l7_yggdrasil', 'l7_helheim03', 'l7_yggdrasil_hall01', [300], proof='Szene 300 (Amelia, Q73 Nr. 11)'),
    V('l7_yggdrasil_hall01', 'l7_yggdrasil', 'l7_yggdrasil_hall02'),
    V('l7_yggdrasil_hall02', 'l7_yggdrasil_hall01', 'l7_yggdrasil_end'),
    V('l7_yggdrasil_end', 'l7_yggdrasil_hall02', 'l7_monastery', [320, 330, 340], (7, 3), proof='Szene 320 = Titelkarte 7.3'),
    V('l7_monastery', 'l7_yggdrasil_end', 'l7_himalaya_end', [342]),
    V('l7_himalaya_end', 'l7_monastery', 'END', [343], proof='letzte Szene 343, kein Level-Wechsel (Spielende)'),
]
# (unit, n-th visit) that claim no checkpoint: ways back over units already walked (their checkpoints stay with the
# first visit; a checkpoint may fire again there - TruTrace shows it) and the last ballcourt visit (arrives at the
# staircase_upper portal, Szene 220 follows 47 m later)
NOCP = {('l1_kraken_room', 2), ('l1_krakenstairs_b', 2), ('l1_krakenstairs_a', 2), ('l1_kraken_entrance', 2),
        ('l1_norse_hallway_a', 2), ('l1_seafloor', 2), ('l1_seatop', 2), ('l4_templepath', 2), ('l4_ragnarok_room', 2),
        ('l4_staircase_mictlan', 2), ('l4_traprooms', 2), ('l4_staircase_xibalba', 2), ('l4_staircase_upper', 2),
        ('l4_ballcourt', 3)}
# a cinematic number used twice: (unit, number) may break the ascending order
DUP_OK = {('l5_valaskjalf_entry', 230): 'Intro 7295 trägt 230 wie die Startszene 5.1 (l5_startsnow 7530)'}
OWNER_EXTRA = {(1, 2): 'l1_kraken_entrance', (2, 3): 'l2_shrineroom', (5, 2): 'l5_valgrind'}
NOT_LOADABLE = ['l1_rutlands_ship_m1', 'l2_mapconnector', 'l2_puzzleconnector']
PAKET_R = ('l1_norse_hallway_a', 'l1_ship_exterior')     # expectation from the first to the second visit of these units


def parse_intros(path):
    units, u = {}, None
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'^== (\S+):', ln)
        if m: u = units.setdefault(m.group(1), {'portals': [], 'intros': []}); continue
        m = re.match(r'^\s+portal -> (\S+)\s+centre as stored \((\S+) (\S+) (\S+)\)', ln)
        if m and u is not None:
            u['portals'].append((m.group(1), (float(m.group(2)), float(m.group(3)), float(m.group(4))))); continue
        m = re.match(r'^\s+intro\s+(\d+)\s+(\S+)\s+live \(\s*(\S+)\s+(\S+)\s+(\S+)\)\s+\+0x52\s+(\d+)\s+script\s+(\S+)', ln)
        if m and u is not None:
            u['intros'].append(dict(uid=int(m.group(1)), name=m.group(2), pos=(float(m.group(3)), float(m.group(4)),
                                    float(m.group(5))), w52=int(m.group(6)), script=m.group(7)))
    return units


def parse_portals(path):
    """unit -> (id, [(index, target, own)]) in the order of the Terrain portal array (= TruTrace's HIT index)"""
    out, u = {}, None
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'^== (\S+)\s+id (\d+)', ln)
        if m: u = m.group(1); out[u] = (int(m.group(2)), []); continue
        m = re.match(r'^\s+-> (\S+)\s+own\s+(\d+)', ln)
        if m and u: out[u][1].append((len(out[u][1]), m.group(1), int(m.group(2))))
    return out


def parse_links(path):
    """(unit, target) of every level-change caller owned by an intro"""
    out = set()
    for ln in open(path, encoding='utf-8'):
        m = re.match(r'^(\S+)\s+script\s+\d+\s+owner (intro \d+ cinematic_object.*?)\s+-> (.*?)( \(same script also in an earlier unit\))?$',
                     ln.rstrip())
        if not m: continue
        for t in m.group(3).split(' | '):
            if not t.startswith('text:'): out.add((m.group(1), t.strip().lower()))
    return out


def parse_calls(path):
    chap, owner = {}, None
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'^\s+owner: (\S+) intro', ln)
        if m: owner = m.group(1); continue
        if ln.startswith('script'): owner = None; continue
        m = re.match(r'^\s+call \(8,72\)\+0x6a54 fNone \[(\d+) (\d+)\]', ln)
        if m and owner: chap.setdefault((int(m.group(1)), int(m.group(2))), owner)
    for k, v in OWNER_EXTRA.items(): chap.setdefault(k, v)
    return chap


def main(intros, portals, links, calls, out_md, out_cp, out_r):
    U = parse_intros(intros)
    P = parse_portals(portals)
    L = parse_links(links)
    C = parse_calls(calls)
    problems = []
    flat = [(area, k, v) for area, vs in CHAIN.items() for k, v in enumerate(vs)]
    # P1 / P2 / P4 / P5 / P6
    for i, (area, k, v) in enumerate(flat):
        u = v['unit']
        if u not in U: problems.append('%s: %s not extracted' % (area, u)); continue
        targets = [t for t, _ in U[u]['portals']]
        if v['enter'] != 'START' and v['enter'] not in targets: problems.append('%s: %s has no portal to %s (enter)' % (area, u, v['enter']))
        lv = v['leave']
        if lv.startswith('LEVEL:'):
            if (u, lv[6:]) not in L: problems.append('%s: %s has no level-change caller to %s' % (area, u, lv[6:]))
        elif lv != 'END' and lv not in targets: problems.append('%s: %s has no portal to %s (leave)' % (area, u, lv))
        if i + 1 < len(flat):
            nv = flat[i + 1][2]
            if lv.startswith('LEVEL:'):
                if nv['enter'] != 'START' or nv['unit'] != lv[6:]: problems.append('%s: level change to %s, next visit %s / %s' % (area, lv[6:], nv['unit'], nv['enter']))
            elif lv != nv['unit'] or nv['enter'] != u: problems.append('%s: %s -> %s, next visit %s from %s' % (area, u, lv, nv['unit'], nv['enter']))
        if isinstance(v['head'], tuple) and len(v['head']) == 2:
            if C.get(v['head']) != u: problems.append('%s: chapter %d.%d at %s, title card caller in %s' % (area, v['head'][0], v['head'][1], u, C.get(v['head'])))
    for ch, cu in C.items():
        if not any(v['head'] == ch for _, _, v in flat): problems.append('chapter %d.%d (caller %s) has no heading' % (ch[0], ch[1], cu))
    visited = {v['unit'] for _, _, v in flat}
    for u in sorted(set(U) - visited): problems.append('extracted unit %s is never visited' % u)
    # P3 cinematics
    claimed = {}
    last, seq = -1, []
    for area, k, v in flat:
        u = v['unit']
        neigh = [u] + [t for t, _ in U[u]['portals']]
        v['cine_objs'] = []
        for num in v['cines']:
            hit = None
            for nu in neigh:
                for it in U.get(nu, {'intros': []})['intros']:
                    if it['name'] == 'cinematic_object' and it['w52'] == num and (nu, it['uid']) not in claimed:
                        hit = (nu, it); break
                if hit: break
            if not hit: problems.append('%s: cinematic %d not found in %s or its neighbours (or claimed twice)' % (area, num, u)); continue
            claimed[(hit[0], hit[1]['uid'])] = (area, k)
            v['cine_objs'].append(hit)
            if num < last and (u, num) not in DUP_OK: problems.append('%s: cinematic %d after %d (order goes down)' % (area, num, last))
            if (u, num) not in DUP_OK: last = max(last, num)
            seq.append(num)
    for u, d in U.items():
        for it in d['intros']:
            if it['name'] == 'cinematic_object' and (u, it['uid']) not in claimed:
                problems.append('cinematic %d (intro %d) in %s is claimed by no visit' % (it['w52'], it['uid'], u))
    # checkpoints in walking order
    def point(v, which):
        u = v['unit']
        tgt = v['enter'] if which == 'in' else v['leave']
        if tgt == 'START':
            pl = [it for it in U[u]['intros'] if it['name'] == 'player']
            if v['cine_objs']: return v['cine_objs'][0][1]['pos'], 'Startszene %d' % v['cine_objs'][0][1]['w52']
            return pl[0]['pos'], 'Spieler-Intro %d' % pl[0]['uid']
        if tgt.startswith('LEVEL:') or tgt == 'END':
            c = v['cine_objs'][-1][1]
            return c['pos'], 'Szene %d' % c['w52']
        ps = [p for t, p in U[u]['portals'] if t == tgt]
        return ps, 'Portal %s' % tgt
    def dist(pos, pts):
        if isinstance(pts, list): return min(math.dist(pos, p) for p in pts)
        return math.dist(pos, pts)
    visits_of = collections.defaultdict(list)
    seen = collections.Counter()
    for idx, (area, k, v) in enumerate(flat):
        seen[v['unit']] += 1
        if (v['unit'], seen[v['unit']]) not in NOCP: visits_of[v['unit']].append(idx)
    for idx, (area, k, v) in enumerate(flat):
        v['pin'], v['pin_t'] = point(v, 'in')
        v['pout'], v['pout_t'] = point(v, 'out')
        v['cps'] = []
    for u, idxs in visits_of.items():
        for it in U[u]['intros']:
            if it['name'] != 'checkpoint': continue
            best = None
            for idx in idxs:
                v = flat[idx][2]
                a, b = dist(it['pos'], v['pin']), dist(it['pos'], v['pout'])
                ab = 0.0 if v['enter'] == v['leave'] else min(math.dist(p, q) for p in (v['pin'] if isinstance(v['pin'], list) else [v['pin']])
                                                                for q in (v['pout'] if isinstance(v['pout'], list) else [v['pout']]))
                detour = a + b - ab
                if best is None or detour < best[0] - 1.0: best = (detour, idx)
            v = flat[best[1]][2]
            a, b = dist(it['pos'], v['pin']), dist(it['pos'], v['pout'])
            key = a if v['enter'] == v['leave'] else a / (a + b) if a + b else 0.0
            v['cps'].append((key, it['uid'], a / 100, b / 100, it['w52']))
    for _, _, v in flat: v['cps'].sort()
    # outputs
    md = ['| # | Gebiet | Unit (Besuch) | herein von | hinaus nach (End-Trigger) | Szenen | Kapitel | Checkpoints in Laufrichtung (Abstand Eingang / Ausgang m) | Sicher | Beleg |',
          '|---|---|---|---|---|---|---|---|---|---|']
    nvis = collections.Counter()
    cp_order = collections.OrderedDict()
    for n, (area, k, v) in enumerate(flat, 1):
        u = v['unit']
        nvis[u] += 1
        lv = v['leave']
        if lv.startswith('LEVEL:'):
            out = '**Level-Wechsel** -> `%s`' % lv[6:]
        elif lv == 'END':
            out = 'Spielende'
        else:
            idxs = [i for i, t, own in P[u][1] if t == lv]
            out = '`%s` (Portal %s)' % (lv, ' / '.join(str(i) for i in idxs))
        ent = 'Level-Laden' if v['enter'] == 'START' else '`%s`' % v['enter']
        cines = ', '.join('%d%s' % (it['w52'], '' if nu == u else ' (in %s)' % nu) for nu, it in v['cine_objs']) or '-'
        if isinstance(v['head'], tuple) and len(v['head']) == 2: head = '**%d.%d**' % v['head']
        elif v['head']: head = v['head'][1]
        else: head = ''
        cps = ', '.join('%d (%.0f / %.0f)' % (cid, a, b) for _, cid, a, b, _ in v['cps']) or ('s. Hinweg' if nvis[u] > 1 else '-')
        proof = v['proof'] + ((' · ' + v['alt']) if v['alt'] else '')
        md.append('| %d | %s | `%s`%s | %s | %s | %s | %s | %s | %s | %s |' % (
            n, area.split(' ')[0], u, ' (%d.)' % nvis[u] if nvis[u] > 1 else '', ent, out, cines, head, cps, v['sure'], proof or '-'))
        cp_order.setdefault(u, [])
        cp_order[u] += [cid for _, cid, _, _, _ in v['cps']]
    for u in NOT_LOADABLE: cp_order.setdefault(u, [])
    open(out_md, 'w', encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')
    with open(out_cp, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# Q113 (work/q113_chain_1211/q113_chain.py): unit TAB checkpoint intro ids in walking order\n')
        for u, ids in cp_order.items(): f.write('%s\t%s\n' % (u, ' '.join(str(i) for i in ids)))
    # Paket R expectation
    a = next(i for i, (_, _, v) in enumerate(flat) if v['unit'] == PAKET_R[0])
    b = next(i for i, (_, _, v) in enumerate(flat) if v['unit'] == PAKET_R[1])
    rows = ['# Q113 Paket R: expected unit visits (TruTrace MOVE / HIT / SAVE) - written by q113_chain.py',
            '# step\tunit\tunit_id\tfrom\tfrom_id\thit_index_in_from\tcheckpoints_walking_order\tcinematics\tchapter\tsure\tnote']
    for i in range(a, b + 1):
        area, k, v = flat[i]
        u = v['unit']
        fr = v['enter'] if v['enter'] != 'START' else ''
        hit = ' / '.join(str(j) for j, t, own in P[fr][1] if t == u) if fr in P else ''
        ch = '%d.%d' % v['head'] if isinstance(v['head'], tuple) and len(v['head']) == 2 else ''
        rows.append('\t'.join([str(i - a + 1), u, str(P[u][0]), fr, str(P[fr][0]) if fr in P else '', hit,
                               ','.join(str(c) for _, c, _, _, _ in v['cps']),
                               ','.join(str(it['w52']) for _, it in v['cine_objs']), ch, v['sure'],
                               v['proof'].replace('\t', ' ')]))
    open(out_r, 'w', encoding='utf-8', newline='\n').write('\n'.join(rows) + '\n')
    ncp = sum(len(v['cps']) for _, _, v in flat)
    print('%d areas, %d visits, %d units visited (%d extracted), %d cinematics claimed (%d cinematic objects), %d checkpoints '
          'placed, Paket R %d steps' % (len(CHAIN), len(flat), len(visited), len(U), len(claimed),
                                        sum(1 for d in U.values() for it in d['intros'] if it['name'] == 'cinematic_object'),
                                        ncp, b - a + 1))
    print('cinematic order along the chain: ' + ' '.join(str(s) for s in seq))
    for p in problems: print('PROBLEM ' + p)
    return 1 if problems else 0


if __name__ == '__main__':
    if len(sys.argv) < 8: sys.exit(__doc__)
    sys.exit(main(*sys.argv[1:8]))
