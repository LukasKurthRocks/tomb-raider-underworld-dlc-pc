| # | Gebiet | Unit (Besuch) | herein von | hinaus nach (End-Trigger) | Szenen | Kapitel | Checkpoints in Laufrichtung (Abstand Eingang / Ausgang m) | Sicher | Beleg |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Prolog | `l3_main_bedroom` | Level-Laden | `l3_bedroom_hall` (Portal 0) | 1 | Prolog | 4453 (9 / 173) | ✅ | neues Spiel; Szene 1 (Intro 4483) |
| 2 | Prolog | `l3_bedroom_hall` | `l3_main_bedroom` | `l3_main_hall` (Portal 1) | - |  | 4342 (10 / 96), 4343 (41 / 68), 4344 (85 / 27) | ✅ | - |
| 3 | Prolog | `l3_main_hall` | `l3_bedroom_hall` | **Level-Wechsel** -> `l1_seatop` | 10 |  | 4082 (9 / 67), 4084 (45 / 39) | ✅ | Szene 10 (Intro 4106, Skript 11568 f0): uigamedata f27, Text "SPECIAL LOAD INTO LEVEL L1_SEATOP" |
| 4 | l1 | `l1_seatop` | Level-Laden | `l1_seafloor` (Portal 1) | 30 | **1.1** | 1000 (79 / 503) | ✅ | Levelstart; Szene 30 = Titelkarte 1.1 |
| 5 | l1 | `l1_seafloor` | `l1_seatop` | `l1_norse_hallway_a` (Portal 0) | - |  | 234 (454 / 102) | ✅ | - |
| 6 | l1 | `l1_norse_hallway_a` | `l1_seafloor` | `l1_kraken_entrance` (Portal 0) | - |  | 779 (10 / 253), 780 (42 / 233) | ✅ | - |
| 7 | l1 | `l1_kraken_entrance` | `l1_norse_hallway_a` | `l1_krakenstairs_a` (Portal 0) | 40 | **1.2** | - | ✅ | Szene 40 (Intro 696, Eingangstor) 26 m vor dem Portal zu krakenstairs_a = Titelkarte 1.2 (Skript 5321 f1 -> 5273 f2) |
| 8 | l1 | `l1_krakenstairs_a` | `l1_kraken_entrance` | `l1_krakenstairs_b` (Portal 1) | - |  | 633 (14 / 100), 634 (103 / 15) | ✅ | - |
| 9 | l1 | `l1_krakenstairs_b` | `l1_krakenstairs_a` | `l1_kraken_room` (Portal 0) | - |  | 593 (17 / 98), 594 (89 / 14) | ✅ | - |
| 10 | l1 | `l1_kraken_room` | `l1_krakenstairs_b` | `l1_baldrsstairs_a` (Portal 0) | 45, 49 |  | 75 (22 / 224), 76 (170 / 114), 56 (247 / 134), 58 (241 / 123), 77 (221 / 103), 78 (221 / 100), 74 (200 / 91), 73 (202 / 88), 46 (232 / 30) | 🔶 | Ring aufgelöst: Szene 45 an der Seite von krakenstairs_b (Ankunft), Szene 49 + Grabtür ms_ani_tombdoor 29 m am Portal baldrsstairs_a -> Tür öffnet erst nach dem Kraken-Rätsel; danach 50 / 51 im Grab |
| 11 | l1 | `l1_baldrsstairs_a` | `l1_kraken_room` | `l1_baldrsstairs_b` (Portal 0) | - |  | 270 (15 / 113), 271 (112 / 17) | 🔶 | Ring-Richtung wie oben |
| 12 | l1 | `l1_baldrsstairs_b` | `l1_baldrsstairs_a` | `l1_baldrs_tomb` (Portal 1) | - |  | 239 (13 / 111), 240 (108 / 13) | 🔶 | Ring-Richtung wie oben |
| 13 | l1 | `l1_baldrs_tomb` | `l1_baldrsstairs_b` | `l1_baldrs_sideroom` (Portal 0) | 50, 51 | **1.3** | 140 (41 / 68), 72 (61 / 72), 141 (82 / 5) | 🔶 | Szene 50 = Titelkarte 1.3 (Panzerhandschuh), Ebene 224 -> Szene 51 + Sticky 43 (Q73); Ausgang = zweites Portal |
| 14 | l1 | `l1_baldrs_sideroom` | `l1_baldrs_tomb` | `l1_baldrs_hall` (Portal 1) | - |  | 91 (10 / 124), 92 (128 / 10) | 🔶 | Ring-Richtung wie oben |
| 15 | l1 | `l1_baldrs_hall` | `l1_baldrs_sideroom` | `l1_kraken_room` (Portal 1) | - |  | 5 (11 / 98), 6 (100 / 11) | 🔶 | Ring schließt sich: Halle -> obere Ebene des Kraken-Raums (Portal z 5827) |
| 16 | l1 | `l1_kraken_room` (2.) | `l1_baldrs_hall` | `l1_krakenstairs_b` (Portal 2) | - |  | s. Hinweg | 🔶 | Rückweg (einziger Weg zum nächsten Ziel), Checkpoints s. Hinweg (Boot nur über seafloor -> seatop) |
| 17 | l1 | `l1_krakenstairs_b` (2.) | `l1_kraken_room` | `l1_krakenstairs_a` (Portal 1) | - |  | s. Hinweg | 🔶 | Rückweg (einziger Weg zum nächsten Ziel), Checkpoints s. Hinweg |
| 18 | l1 | `l1_krakenstairs_a` (2.) | `l1_krakenstairs_b` | `l1_kraken_entrance` (Portal 0) | - |  | s. Hinweg | 🔶 | Rückweg (einziger Weg zum nächsten Ziel), Checkpoints s. Hinweg |
| 19 | l1 | `l1_kraken_entrance` (2.) | `l1_krakenstairs_a` | `l1_norse_hallway_a` (Portal 1) | - |  | s. Hinweg | 🔶 | Rückweg (einziger Weg zum nächsten Ziel), Checkpoints s. Hinweg |
| 20 | l1 | `l1_norse_hallway_a` (2.) | `l1_kraken_entrance` | `l1_seafloor` (Portal 1) | - |  | s. Hinweg | 🔶 | Rückweg (einziger Weg zum nächsten Ziel), Checkpoints s. Hinweg |
| 21 | l1 | `l1_seafloor` (2.) | `l1_norse_hallway_a` | `l1_seatop` (Portal 1) | - |  | s. Hinweg | 🔶 | Rückweg (einziger Weg zum nächsten Ziel), Checkpoints s. Hinweg |
| 22 | l1 | `l1_seatop` (2.) | `l1_seafloor` | `l1_cineseatop` (Portal 0) | - |  | s. Hinweg | 🔶 | Boot-Volumen 1840 (OnIn, nur mit Sticky 43 aus dem Grab) spielt Szene 52 in l1_cineseatop (Q73); Wechsel in die Szenen-Unit: Portal oder Szene - Live-Log klärt |
| 23 | l1 | `l1_cineseatop` | `l1_seatop` | `l1_ship_exterior` (Portal 1) | 52 | **1.4** | - | ✅ | Szene 52 (Intro 1780, Skript 8003) = Titelkarte 1.4 |
| 24 | l1 | `l1_ship_exterior` | `l1_cineseatop` | `l1_ship_upper_hallway_a` (Portal 1) | - |  | 1554 (667 / 394), 1555 (681 / 386), 1556 (722 / 386), 1557 (762 / 389), 1558 (680 / 274), 1560 (607 / 100), 1559 (652 / 104), 1561 (701 / 100), 1562 (660 / 11) | ✅ | - |
| 25 | l1 | `l1_ship_upper_hallway_a` | `l1_ship_exterior` | `l1_ship_upper_hallway_b` (Portal 0) | - |  | 1524 (11 / 56), 1525 (59 / 6) | ✅ | - |
| 26 | l1 | `l1_ship_upper_hallway_b` | `l1_ship_upper_hallway_a` | `l1_ship_upper_hallway` (Portal 0) | - |  | 1488 (7 / 54), 1489 (50 / 7) | ✅ | - |
| 27 | l1 | `l1_ship_upper_hallway` | `l1_ship_upper_hallway_b` | `l1_ship_engine_hall` (Portal 1) | 55 |  | 1447 (7 / 71), 1448 (66 / 9) | ✅ | Szene 55 6 m vor engine_hall |
| 28 | l1 | `l1_ship_engine_hall` | `l1_ship_upper_hallway` | `l1_ship_natla_room` (Portal 1) | - |  | 1412 (7 / 81), 1411 (82 / 7) | ✅ | - |
| 29 | l1 | `l1_ship_natla_room` | `l1_ship_engine_hall` | `l1_ship_lower_hallway` (Portal 0) | 60 | **1.5** | 1292 (9 / 65), 1354 (67 / 6) | ✅ | Szene 60 = Titelkarte 1.5 |
| 30 | l1 | `l1_ship_lower_hallway` | `l1_ship_natla_room` | `l1_ship_sinking_hall` (Portal 1) | - |  | 1295 (6 / 82), 1294 (80 / 8) | ✅ | - |
| 31 | l1 | `l1_ship_sinking_hall` | `l1_ship_lower_hallway` | `l1_cine_ship_sinking` (Portal 1) | - |  | 1054 (15 / 793), 1055 (118 / 833) | ✅ | - |
| 32 | l1 | `l1_cine_ship_sinking` | `l1_ship_sinking_hall` | **Level-Wechsel** -> `l2_cliffclimb` | 70 |  | - | ✅ | Szene 70 (Intro 1005, Skript 6003 f0): uigamedata f27 "l2_cliffclimb" |
| 33 | l2 | `l2_cliffclimb` | Level-Laden | `l2_cliffhall` (Portal 0) | 80 | **2.1** | 3835 (0 / 214), 3832 (148 / 83), 3834 (197 / 29) | ✅ | Levelstart; Szene 80 = Titelkarte 2.1 |
| 34 | l2 | `l2_cliffhall` | `l2_cliffclimb` | `l2_cliffhall_b` (Portal 0) | - |  | 3755 (25 / 188), 3754 (83 / 125), 3756 (165 / 76) | ✅ | - |
| 35 | l2 | `l2_cliffhall_b` | `l2_cliffhall` | `l2_junglehub` (Portal 2) | - |  | 3680 (74 / 199), 3679 (54 / 124), 3681 (144 / 38) | 🔶 | Checkpoint 3681 38 m am Portal junglehub, keiner am Direkt-Portal hubhall (>= 211 m) · alternativ: cliffhall_b -> hubhall direkt (eigenes Portal, ohne Checkpoint dort) |
| 36 | l2 | `l2_junglehub` | `l2_cliffhall_b` | `l2_hubhall` (Portal 1) | - |  | 3219 (47 / 185), 3214 (106 / 143), 3218 (218 / 175), 3215 (189 / 120), 3217 (171 / 80), 3216 (161 / 70), 3220 (192 / 12) | 🔶 | Spieler-Intro 47 m am Portal cliffhall_b · alternativ übersprungen (Direkt-Portal cliffhall_b -> hubhall) |
| 37 | l2 | `l2_hubhall` | `l2_junglehub` | `l2_puzzleroom` (Portal 2) | - |  | 3098 (11 / 183), 3096 (44 / 147), 3097 (122 / 87), 3099 (180 / 86), 3100 (171 / 24) | 🔶 | Checkpoint 3098 11 m / Spieler-Intro 12 m am Portal junglehub |
| 38 | l2 | `l2_puzzleroom` | `l2_hubhall` | `l2_norsehall` (Portal 2 / 3) | 90, 91 | **2.2** | 2817 (16 / 100), 2818 (86 / 120), 2824 (68 / 88), 2821 (108 / 94), 2827 (110 / 20), 2826 (110 / 19) | 🔶 | Szene 90 31 m vom Eingang hubhall = Titelkarte 2.2; Szene 91 auf der unteren Ebene (z -16953) bei den zwei Türen zu norsehall (z -15852 / -15506), danach 92 in norsehall · zwei parallele Türen puzzleroom -> norsehall (Portale 2 / 3, je ein Checkpoint 2827 / 2826 davor) = alternativ |
| 39 | l2 | `l2_norsehall` | `l2_puzzleroom` | `l2_norsehub` (Portal 0) | 92 |  | 2454 (29 / 287), 2453 (31 / 287), 2451 (136 / 182), 2452 (190 / 145), 2455 (308 / 12) | 🔶 | Szene 92; Eingangs-Checkpoints 2454 / 2453 je an einer Tür · Eingang durch Tür links oder rechts (alternativ) |
| 40 | l2 | `l2_norsehub` | `l2_norsehall` | `l2_towerconnector` (Portal 1) | 92 |  | 2085 (14 / 88), 2089 (70 / 148), 2091 (79 / 128), 2087 (120 / 148), 2088 (121 / 148), 2083 (92 / 107), 2082 (114 / 96), 2081 (115 / 67), 2080 (64 / 36), 2084 (70 / 33), 2090 (120 / 51), 2086 (106 / 38), 2092 (79 / 22) | 🔶 | Szene 92 (gleiche Nummer wie norsehall) |
| 41 | l2 | `l2_towerconnector` | `l2_norsehub` | `l2_towerroom` (Portal 1) | - |  | 2002 (15 / 170), 2001 (119 / 107), 2003 (191 / 20) | 🔶 | Ring-Richtung aus 91 -> 92 (keine Szene in den Türmen) |
| 42 | l2 | `l2_towerroom` | `l2_towerconnector` | `l2_upperhallway` (Portal 1) | - |  | 1892 (10 / 111), 1901 (74 / 100), 1903 (85 / 82), 1890 (113 / 81), 1902 (74 / 49), 1891 (119 / 69), 1904 (106 / 11) | 🔶 | Ring-Richtung wie oben |
| 43 | l2 | `l2_upperhallway` | `l2_towerroom` | `l2_puzzleroom` (Portal 0) | - |  | 1866 (10 / 144), 1865 (43 / 127), 1867 (127 / 29) | 🔶 | Ring schließt sich: obere Ebene des Rätselraums (Portal z -9913) |
| 44 | l2 | `l2_puzzleroom` (2.) | `l2_upperhallway` | `l2_shrineroom` (Portal 1) | - |  | 2820 (11 / 147), 2825 (42 / 139), 2819 (46 / 140), 2064 (45 / 109), 2068 (92 / 133), 2822 (105 / 94), 2067 (131 / 110), 2074 (112 / 66), 2823 (179 / 92) | 🔶 | zurück im Rätselraum; Portal shrineroom unten (z -15483) |
| 45 | l2 | `l2_shrineroom` | `l2_puzzleroom` | `l2_maproom` (Portal 0) | - | **2.3** | 2769 (48 / 73) | ✅ | Titelkarte 2.3 = Skript 9934 (Intro 2794 sa_uo_naga_statue) |
| 46 | l2 | `l2_maproom` | `l2_shrineroom` | `l2_flushtunnel` (Portal 0) | 95, 100, 105 | **2.4** | 2592 (61 / 301), 2590 (151 / 201), 2591 (219 / 133), 2589 (316 / 49), 2593 (349 / 13) | ✅ | Szenen 95 (73 m vom Eingang) -> 100 -> 105 (60 m vor flushtunnel) = Titelkarte 2.4: Richtung belegt |
| 47 | l2 | `l2_flushtunnel` | `l2_maproom` | `l2_cliffclimb` (Portal 1) | - |  | 2505 (10 / 282), 2506 (269 / 16) | ✅ | - |
| 48 | l2 | `l2_cliffclimb` (2.) | `l2_flushtunnel` | **Level-Wechsel** -> `l3_caverns_start` | 110 |  | 3833 (113 / 235), 3831 (122 / 198), 2569 (252 / 63) | ✅ | Szene 110 (Intro 2565, Skript 9515 f1): uigamedata f27 "l3_caverns_start" |
| 49 | l3 | `l3_caverns_start` | Level-Laden | `l3_chapel` (Portal 0) | 120 | **3.1** | 4302 (14 / 76), 4303 (69 / 9) | ✅ | Levelstart; Szene 120 = Titelkarte 3.1 |
| 50 | l3 | `l3_chapel` | `l3_caverns_start` | `l3_stairhall` (Portal 1) | - |  | 4735 (12 / 160), 4737 (92 / 92), 4738 (102 / 65), 4736 (137 / 85), 4739 (159 / 37) | ✅ | - |
| 51 | l3 | `l3_stairhall` | `l3_chapel` | `l3_secretchamber` (Portal 0) | - |  | 4698 (29 / 56), 4699 (75 / 11) | ✅ | - |
| 52 | l3 | `l3_secretchamber` | `l3_stairhall` | `l3_chamberrockhall` (Portal 0) | 130, 145 |  | 4621 (7 / 119), 4622 (94 / 62), 4598 (113 / 13) | ✅ | Szene 145 10 m vor chamberrockhall |
| 53 | l3 | `l3_chamberrockhall` | `l3_secretchamber` | `l3_main_bedroom` (Portal 0) | - |  | 4599 (11 / 223), 4600 (213 / 11) | ✅ | Hebel 4617 -> Geheimtür 4528 (l3_main_bedroom), Volumen 4619 setzt Szene 1 zurück (Q73) |
| 54 | l3 | `l3_main_bedroom` (2.) | `l3_chamberrockhall` | `l3_bedroom_hall` (Portal 0) | - |  | 4454 (160 / 28), 4455 (174 / 16) | 🔶 | zweiter Besuch: Szene 1 erneut (zurückgesetzt, keine neue Nummer), Unit-Skript 12059 "level zero is done" |
| 55 | l3 | `l3_bedroom_hall` (2.) | `l3_main_bedroom` | `l3_main_hall` (Portal 1) | - |  | s. Hinweg | 🔶 | zweiter Besuch |
| 56 | l3 | `l3_main_hall` (2.) | `l3_bedroom_hall` | `l3_mansion_exterior_afterburn` (Portal 1) | 150, 160 |  | 4085 (66 / 57), 4083 (78 / 25) | ✅ | Szenen 150 / 160 (Rückkehr) |
| 57 | l3 | `l3_mansion_exterior_afterburn` | `l3_main_hall` | **Level-Wechsel** -> `l4_trailstart` | 170 |  | - | ✅ | Szene 170 (Intro 4070, Skript 11393 f4): uigamedata f27 "L4_trailstart" |
| 58 | l4 | `l4_trailstart` | Level-Laden | `l4_trailtube` (Portal 0) | 180 | **4.1** | 5486 (72 / 280), 6622 (339 / 262), 6620 (388 / 275), 5485 (370 / 145), 6621 (328 / 119), 6619 (335 / 24) | ✅ | Levelstart; Szene 180 = Titelkarte 4.1 |
| 59 | l4 | `l4_trailtube` | `l4_trailstart` | `l4_ballcourt` (Portal 0) | - |  | 6562 (25 / 541), 6563 (429 / 134), 6561 (542 / 17) | ✅ | - |
| 60 | l4 | `l4_ballcourt` | `l4_trailtube` | `l4_templepath` (Portal 1) | 185, 186 | **4.2** | 6120 (21 / 526), 6124 (199 / 457), 6121 (229 / 322), 5478 (250 / 324), 6125 (383 / 462), 6126 (457 / 287) | 🔶 | Szenen 185 / 186 = Titelkarte 4.2; Abstecher zum Tempel in 4.2 (Kopfschmuck-Schlüssel, Gruppe J), Reihenfolge der vier Kalender-Teile frei |
| 61 | l4 | `l4_templepath` | `l4_ballcourt` | `l4_temple` (Portal 1) | - |  | 5326 (32 / 411), 5327 (426 / 13) | 🔶 | Abstecher (Sackgasse) |
| 62 | l4 | `l4_temple` | `l4_templepath` | `l4_templepath` (Portal 0) | - |  | 4974 (53 / 53), 4973 (288 / 288), 4971 (328 / 328), 4976 (362 / 362), 4975 (364 / 364), 4972 (368 / 368) | 🔶 | Sackgasse: nur ein Portal |
| 63 | l4 | `l4_templepath` (2.) | `l4_temple` | `l4_ballcourt` (Portal 0) | - |  | s. Hinweg | 🔶 | Rückweg vom Abstecher |
| 64 | l4 | `l4_ballcourt` (2.) | `l4_templepath` | `l4_staircase_upper` (Portal 0) | 190 | **4.3** | 6123 (30 / 408), 6127 (206 / 392), 6128 (384 / 494), 6129 (347 / 321), 6130 (293 / 184), 5479 (316 / 161), 6122 (420 / 17) | ✅ | Szene 190 (52 m vor staircase_upper) = Titelkarte 4.3; Weg nach Xibalbá offen nach "both calendars solved" |
| 65 | l4 | `l4_staircase_upper` | `l4_ballcourt` | `l4_staircase_xibalba` (Portal 1) | - |  | 6059 (19 / 327), 6057 (226 / 111), 6058 (299 / 40) | ✅ | - |
| 66 | l4 | `l4_staircase_xibalba` | `l4_staircase_upper` | `l4_traprooms` (Portal 0) | - |  | 6023 (36 / 201), 6021 (54 / 182), 6020 (111 / 129), 6022 (230 / 11) | ✅ | - |
| 67 | l4 | `l4_traprooms` | `l4_staircase_xibalba` | `l4_staircase_mictlan` (Portal 0) | 195 |  | 5704 (24 / 109), 5785 (75 / 153), 5786 (94 / 164), 5736 (54 / 91), 5733 (55 / 89), 5722 (54 / 79), 5790 (168 / 216), 5788 (167 / 214), 5791 (221 / 172), 5789 (221 / 171), 5784 (171 / 99), 5787 (170 / 96), 5735 (105 / 42), 5734 (108 / 42), 5792 (128 / 17) | ✅ | - |
| 68 | l4 | `l4_staircase_mictlan` | `l4_traprooms` | `l4_ragnarok_room` (Portal 0) | - |  | 5737 (18 / 378), 5738 (386 / 22) | ✅ | - |
| 69 | l4 | `l4_ragnarok_room` | `l4_staircase_mictlan` | `l4_pool` (Portal 1) | - |  | 5668 (22 / 534), 5669 (534 / 25) | ✅ | - |
| 70 | l4 | `l4_pool` | `l4_ragnarok_room` | `l4_ragnarok_room` (Portal 0) | 198, 200 (in l4_ragnarok_room), 210 | **4.4** | 5502 (24 / 24), 5508 (110 / 110), 5498 (125 / 125), 5499 (140 / 140), 5505 (148 / 148), 5497 (167 / 167), 5503 (171 / 171), 5507 (179 / 179), 5506 (181 / 181), 5504 (200 / 200), 5501 (220 / 220), 5500 (223 / 223) | 🔶 | Szenen 198 (pool) -> 200 (ragnarok_room, 31 m am Pool-Portal) -> 210 = Titelkarte 4.4; Sackgasse |
| 71 | l4 | `l4_ragnarok_room` (2.) | `l4_pool` | `l4_staircase_mictlan` (Portal 0) | - |  | s. Hinweg | 🔶 | Rückweg zum Ballspielplatz (Szene 220 dort, 47 m am Portal staircase_upper); kein Level-Wechsel in pool / ragnarok_room - ob gelaufen oder per Szene versetzt: Live-Log |
| 72 | l4 | `l4_staircase_mictlan` (2.) | `l4_ragnarok_room` | `l4_traprooms` (Portal 1) | - |  | s. Hinweg | 🔶 | Rückweg wie oben |
| 73 | l4 | `l4_traprooms` (2.) | `l4_staircase_mictlan` | `l4_staircase_xibalba` (Portal 1) | - |  | s. Hinweg | 🔶 | Rückweg wie oben |
| 74 | l4 | `l4_staircase_xibalba` (2.) | `l4_traprooms` | `l4_staircase_upper` (Portal 1) | - |  | s. Hinweg | 🔶 | Rückweg wie oben |
| 75 | l4 | `l4_staircase_upper` (2.) | `l4_staircase_xibalba` | `l4_ballcourt` (Portal 0) | - |  | s. Hinweg | 🔶 | Rückweg wie oben |
| 76 | l4 | `l4_ballcourt` (3.) | `l4_staircase_upper` | **Level-Wechsel** -> `l5_startsnow` | 220 |  | s. Hinweg | ✅ | Szene 220 (Intro 5483, Skript 13923 f1): uigamedata f27 "L5_startsnow" |
| 77 | l5 | `l5_startsnow` | Level-Laden | `l5_valgrind_tunnel` (Portal 0) | 230 | **5.1** | 7527 (8 / 286) | ✅ | Levelstart; Szene 230 = Titelkarte 5.1 |
| 78 | l5 | `l5_valgrind_tunnel` | `l5_startsnow` | `l5_valgrind` (Portal 1) | - |  | 7369 (172 / 142) | ✅ | - |
| 79 | l5 | `l5_valgrind` | `l5_valgrind_tunnel` | `l5_valaskjalf_entry` (Portal 0) | 235, 240 | **5.2** | 7353 (54 / 276), 7436 (132 / 183), 7321 (156 / 173), 7435 (185 / 134), 7325 (200 / 127), 7437 (235 / 122), 7328 (249 / 100), 7329 (293 / 64) | ✅ | Szene 235 61 m am Eingang, 240 65 m vor valaskjalf_entry; Titelkarte 5.2 = Skript 17329 (Intro 7332 reveal_object) |
| 80 | l5 | `l5_valaskjalf_entry` | `l5_valgrind` | `l5_valaskjalf_entryb` (Portal 1) | 230 |  | 7281 (18 / 356), 7282 (420 / 406), 7283 (363 / 35) | ✅ | Intro 7295 trägt die Nummer 230 ein zweites Mal |
| 81 | l5 | `l5_valaskjalf_entryb` | `l5_valaskjalf_entry` | `l5_valaskjalf` (Portal 0) | - |  | 7172 (36 / 361), 7173 (283 / 367) | ✅ | - |
| 82 | l5 | `l5_valaskjalf` | `l5_valaskjalf_entryb` | **Level-Wechsel** -> `l6_ship_exterior` | 242, 245, 250 |  | 7066 (19 / 320), 7068 (89 / 263), 7074 (166 / 244), 7078 (191 / 280), 7065 (199 / 273), 7075 (215 / 275), 7064 (243 / 309), 7073 (178 / 222), 7069 (174 / 208), 7077 (214 / 249), 7076 (214 / 226), 7070 (226 / 208), 7079 (290 / 263), 7067 (315 / 256), 7071 (281 / 220), 7072 (291 / 219) | ✅ | Szene 250 (Intro 6846, Skript 16274 f1): uigamedata f27 "L6_ship_exterior" |
| 83 | l6 | `l6_ship_exterior` | Level-Laden | `l6_ship_upper_hallway_a` (Portal 0) | 260 | **6.1** | 7655 (9 / 384), 7666 (125 / 271), 7667 (286 / 104), 7669 (292 / 96), 7668 (296 / 96), 7670 (326 / 76), 7671 (340 / 76), 7672 (393 / 11) | ✅ | Levelstart; Szene 260 = Titelkarte 6.1 |
| 84 | l6 | `l6_ship_upper_hallway_a` | `l6_ship_exterior` | `l6_ship_upper_hallway_b` (Portal 0) | - |  | 7636 (11 / 56), 7637 (59 / 6) | ✅ | - |
| 85 | l6 | `l6_ship_upper_hallway_b` | `l6_ship_upper_hallway_a` | `l6_ship_upper_hallway` (Portal 0) | - |  | 7618 (7 / 54), 7619 (50 / 7) | ✅ | - |
| 86 | l6 | `l6_ship_upper_hallway` | `l6_ship_upper_hallway_b` | `l6_ship_engine_hall` (Portal 1) | - |  | 7583 (7 / 71), 7584 (66 / 9) | ✅ | - |
| 87 | l6 | `l6_ship_engine_hall` | `l6_ship_upper_hallway` | `l6_ship_natla_room` (Portal 1) | - |  | 7557 (7 / 81), 7556 (82 / 7) | ✅ | - |
| 88 | l6 | `l6_ship_natla_room` | `l6_ship_engine_hall` | **Level-Wechsel** -> `l7_thin_ice` | 270 |  | - | ✅ | Szene 270 (Intro 1387, Skript 7017 f0): uigamedata f27 "L7_thin_ice" |
| 89 | l7 | `l7_thin_ice` | Level-Laden | `l7_arctic_sea` (Portal 0) | 275 | **7.1** | 9069 (33 / 33) | ✅ | Levelstart; Szene 275 = Titelkarte 7.1 |
| 90 | l7 | `l7_arctic_sea` | `l7_thin_ice` | `l7_helheim_hall01` (Portal 0) | - |  | 9094 (14 / 776), 9109 (407 / 426), 9110 (483 / 329), 9124 (626 / 262), 9111 (576 / 237), 9223 (765 / 165), 9225 (770 / 165), 9221 (780 / 113), 9222 (784 / 112), 9112 (696 / 90), 9224 (735 / 93) | ✅ | - |
| 91 | l7 | `l7_helheim_hall01` | `l7_arctic_sea` | `l7_helheim_hall02` (Portal 0) | - |  | 9170 (7 / 387) | ✅ | - |
| 92 | l7 | `l7_helheim_hall02` | `l7_helheim_hall01` | `l7_helheim01` (Portal 0) | - |  | - | ✅ | - |
| 93 | l7 | `l7_helheim01` | `l7_helheim_hall02` | `l7_helheim02` (Portal 0) | 280, 290 | **7.2** | 8939 (120 / 300), 8940 (328 / 91) | ✅ | Szene 290 = Titelkarte 7.2, 49 m vor helheim02 |
| 94 | l7 | `l7_helheim02` | `l7_helheim01` | `l7_helheim03` (Portal 1) | - |  | 8884 (18 / 89) | ✅ | - |
| 95 | l7 | `l7_helheim03` | `l7_helheim02` | `l7_yggdrasil` (Portal 1) | - |  | 8844 (17 / 261) | ✅ | - |
| 96 | l7 | `l7_yggdrasil` | `l7_helheim03` | `l7_yggdrasil_hall01` (Portal 0) | 300 |  | 8792 (15 / 52) | ✅ | Szene 300 (Amelia, Q73 Nr. 11) |
| 97 | l7 | `l7_yggdrasil_hall01` | `l7_yggdrasil` | `l7_yggdrasil_hall02` (Portal 1) | - |  | 8775 (36 / 95) | ✅ | - |
| 98 | l7 | `l7_yggdrasil_hall02` | `l7_yggdrasil_hall01` | `l7_yggdrasil_end` (Portal 1) | - |  | - | ✅ | - |
| 99 | l7 | `l7_yggdrasil_end` | `l7_yggdrasil_hall02` | `l7_monastery` (Portal 0) | 320, 330, 340 | **7.3** | 8176 (18 / 824), 8154 (223 / 842), 8242 (220 / 808), 8244 (220 / 737), 8155 (228 / 765), 8157 (250 / 817), 8243 (254 / 819), 8158 (256 / 749), 8245 (256 / 718), 8179 (259 / 700), 8248 (323 / 832), 8177 (344 / 831), 8178 (347 / 784), 8159 (390 / 813), 8156 (351 / 720), 8180 (370 / 741) | ✅ | Szene 320 = Titelkarte 7.3 |
| 100 | l7 | `l7_monastery` | `l7_yggdrasil_end` | `l7_himalaya_end` (Portal 0) | 342 |  | - | ✅ | - |
| 101 | l7 | `l7_himalaya_end` | `l7_monastery` | Spielende | 343 |  | - | ✅ | letzte Szene 343, kein Level-Wechsel (Spielende) |
