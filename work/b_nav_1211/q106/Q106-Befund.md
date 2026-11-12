# Q106 - joint range puzzles: read / write path (static, PC tru.exe)

Date 2026-11-12, static research only (no game start). Exe: the installed PC `tru.exe` (= `data/pc/tru.exe` of the
workspace, 6 422 528 B, 27.10.). Disassembly with `tools/pe_dis.py`; raw dumps in a temp folder outside the repository (dis_*.txt,
uber_sa_uo_mirror_left.txt / _right.txt from `work/q74_spots_1111/q74_uber_dump.py`). Status marks: ✅ = read in the
code / data, 🔶 = suspected (plausible, not proven), ⬜ = open.

## 1. Objects involved

| Name | What | St |
|---|---|---|
| uber `b` | live path `b = [[inst+0x2d0]]+0x2ec - 0x10`, magic 0xF0012345 at b+0x70 (ENGINE 9). Base ctor 0x4d78d0 writes **b+0x74 = inst, b+0x78 = DESC, b+0x7c = X** (0x4d7a1c / 0x4d7a1f / 0x4d7a22) | ✅ |
| multibody object `X` | 0x78-B object, base ctor 0x4d7d50 (vtable 0x847f70, subclass vtable 0x85d55c set in 0x6d5fb7), **X+0x54 = magic 0xFEA51B1E** (0x4d7d9c), **X+0x58 = its instance** (0x4d7dbc), X+0x6c / +0x70 = linked part instances (ENGINE cond 9), **X+0x74 = joint list** (std::list sentinel ptr, 0x4d7d60). Instance class 0x4f (0x6d0a38): process `[inst+0x110]` 0x6d4a80 -> 0x4d1490 -> vtable slot 3 = **0x4d66a0 every frame**, query `[inst+0x11c]` 0x6d4a90. Same X is also reached as `[[b+0x74]+0x4c]` -> +0x2d0 -> +0x2ec - 4 (0x4d2f80) | ✅ |
| joint list node | 0x24 B, `{next +0, prev +4, value +8..}`, appended at the tail (push_back 0x4d7850, 0x4d78a9..0x4d78bc). **node+8 = joint record ptr (DTP)**, node+0x10 = last limits record ptr (action 12, 0x4d6331), node+0x14 = motor record ptr 🔶, **node+0x1c = physics joint J** (0x4d8242 -> value +0x14; returned by query 0xfc at 0x4d710a) | ✅ |
| joint record (DTP) | +0 u8 uber joint type, +4 link index A (-1 = world), +8 link index B, +0xc u8 model, +0xd u8 segment (0x4d804d..0x4d80a3); type 0xb = gear / coupling record {0xb, f32 ratio} (0x4d8037 -> 0x4d7ed0, also appended to the list at 0x4d7fa6) | ✅ |
| uber joint type -> physics type | 0x4d1040: 0->1, 1->2, 2->3, 3->4, 4->5, 5->8, 6->9, 7->10, 8->11, 9->12, 10->17, 11->13 | ✅ |
| physics joint J | **J+0x178 u8 physics type** (0x4d9b10), J+0x174 flags: limit enable bit `2<<axis` (0x4d9f50), motor enable bit `0x10<<axis` (0x4da0c0 / 0x4da130); per axis `J+0xd8+16*axis` lo, `+0xdc+16*axis` hi (0x4d9fc0); motor velocity `J+0x108+8*axis` (0x4da160); J+0x160 body 1, J+0x15c body 2 or 0 = world (0x4da460 / 0x4da930); body +0x80 position, +0x90 rotation | ✅ |
| watcher list | `W = [X+0x58] + 0x250` (embedded in the instance), W+0x10 = instance, **W+0x14 count, W+0x18 capacity, W+0x1c records**, 0x28 B each (add 0x49a5c0, remove 0x493a80, evaluate 0x4937a0) | ✅ |

Watcher record (0x49a5c0, args from 0x4d73e3..0x4d73fe): +0 joint index (list position, 0x4d5c30), +4 axis
(0x4d11e0), +8 uber `b`, +0xc min f32, +0x10 max f32 (copied from the range record, **no unit conversion**),
+0x14 watch kind (= action 20 word +4), +0x18 u8 inside, +0x19 u8 first-evaluation flag (= 1 at arm), +0x1c callback
0x4d5b10, +0x20 joint record ptr, +0x24 range record ptr. ✅

## 2. READ path (how the engine gets the value it compares)

Evaluator **0x4937a0** (this = W), called every frame from X's process 0x4d66a0 (`mov ecx,[esi+0x58]; add ecx,0x250;
call 0x4937a0`), for every record: ✅

1. `J = INSTANCE_Query([W+0x10], 0xfc, rec+0)` (0x4937c7..0x4937d3, 0x5b3720 -> `[inst+0x11c]` 0x6d4a90 -> default
   0x4d7080): query 0xfc on the X instance walks `X+0x74` to position `rec+0` and returns `[node+0x1c]` (0x4d70cd..0x4d710a). J = 0 -> record skipped.
2. First evaluation (`rec+0x19 != 0`): `rec+0x18 = 1`, `rec+0x19 = 0` (0x4937e7..0x4937f0) - **the watcher starts
   as "inside"**: arming a range while the joint is already inside sends **no** enter event; arming while outside sends a
   **leave** (cond 15) on the first frame. (Answers the ⬜ in ENGINE 9.)
3. Value by watch kind `rec+0x14`: 0 = position `0x48f1d0(eax = axis, edi = J)` (custom register convention); 1 = rate
   `0x48f3b0` (uses 0x4e1fd0, 🔶 velocity); 2 = `0x4da010` (thiscall J, axis; level-triggered every frame, no edge).
   All base puzzles in the dumps use kind 0 (46 of 48 action-20 records; 2 use kind 1).
4. Inside test: **min <= v < max** (fcom / fcompp `test ah,1` / `test ah,0x41`, 0x49398c..0x4939a8; NaN = outside).
5. Edge: inside flag 0 -> 1 calls `callback(kind, idx, axis, b, 1, jointrec, rangerec)`, 1 -> 0 the same with 0
   (0x4939b0..0x493a56); **the flag is updated even when the uber drops the event**.
6. Callback 0x4d5b10 -> **0x4d5a50** (this = b): drop if `[b+0x80] != 0` or `[b+0x90] & 9`; else find a TRANS of the
   current node with `+0x18 == (enter ? 14 : 15)`, `+0x20 == jointrec`, `+0x24 == rangerec`, `+0x1c == kind`, extra
   check 0x4d0e10, then start it (0x4d4a00). Matching is by **record pointer**, not by index.

Position getter 0x48f1d0 by physics type (`J+0x178`), axis, units: ✅

| phys (uber) type | axis 0 | axis 1 | axis 2 |
|---|---|---|---|
| 1 (0) hinge | angle 0x4da930 x 57.29578 = **degrees** | - | - |
| 2 (1) slider+hinge 🔶 | position 0x4da460 (units) | angle deg | - |
| 3 (2) slider | **position 0x4da460, world units** | - | - |
| 4 (3) | 0x4da710 units | 0x4da820 units | angle 0x4da930 deg |
| 8 (5) universal 🔶 | 0x4dada0 deg | 0x4daee0 deg | - |
| 9 (6) | 0x4db070 units | 0x4da930 deg | 0x4db190 deg |
| 10 (7) | vector 0x4db4d0 [axis] units | same | same |
| 5, 6, 7, other | 0.0 (fldz) | | |

- Axis comes from the range record (0x4d11e0 on the type byte, which must equal the joint record's type byte,
  0x4d73ad): types 0 / 2 -> axis 0, min +4, max +8; types 1 / 5 -> axis = +4 (0 / 1), min +8, max +0xc; types
  3 / 6 / 7 -> axis = +4 (0..2), min +8, max +0xc; type 4 -> no range (min / max not written). ✅
- Hinge angle 0x4da930 (thiscall J, no stack args, result in st0, radians): `atan2(dot(R1*J+0x50, R2*J+0x30),
  dot(R1*J+0x50, R2*J+0x20))`, R1 = rotation of body [J+0x160], R2 = body [J+0x15c] (identity if 0) -> range
  (-180, 180]; relative to the reference vectors stored in J at creation 🔶 (where J+0x20/0x30/0x50 are written: ⬜).
- Slider position 0x4da460 (thiscall J, no args, st0): `dot(R1*J+0x70, (pos1 + R1*J+0x10) - (pos2 + R2*J+0x00))`
  (with no body 2: J+0x00 as world point 🔶). Computed from body poses on every call - **there is no stored value
  field**; the solver keeps its own copy (limit row 0x4e21c1 reads `J+0xe0+16*axis` 🔶).

**Read chain for TruMenu (pure memory, plus two thiscall leaf calls):**

```
b    = live uber (magic F0012345 at b+0x70)
X    = [b+0x7c]               ; check [X+0x54] == 0xFEA51B1E
for the current node: TRANS t with cond [t+0x18] in {14,15}: jrec = [t+0x20], rrec = [t+0x24], kind = [t+0x1c]
node = [[X+0x74]] ... walk node = [node] until node == [X+0x74]; pick node with [node+8] == jrec
J    = [node+0x1c]            ; type = byte [J+0x178]
axis = from rrec (byte 0: 0/2 -> 0, else dword +4); min/max = rrec+4/+8 (types 0,2) or +8/+0xc
v    = type 1: thiscall 0x4da930(J) * 57.29577951 ; type 3: thiscall 0x4da460(J) (units)
inside = (min <= v && v < max)
```
Identify joints by record pointer (as the engine does), not by list index: the index is the creation order over **all**
kind-9 actions of all ubers sharing X (type-0xb gear records count too), e.g. shiva_left_scale creates joints from 3 DESCs.
For the mirrors the order is hinge @0x300 -> index 0, slider @0x374 -> index 1 🔶 (only one DESC creates joints);
the owner's "joint 0 / joint 2" are the record type bytes (0 = hinge, 2 = slider).

### Byte checks (tru.exe, hex)

| Address | Expected bytes | Meaning |
|---|---|---|
| 0x4d7a22 | `89 4e 7c` | b+0x7c = X (uber ctor) |
| 0x4d7d9c | `c7 46 54 1e 1b a5 fe` | X+0x54 magic |
| 0x4d7dbc | `89 7e 58` | X+0x58 = instance |
| 0x4d5c30 | `8b 54 24 04 8b 4a 74` | joint list at X+0x74 |
| 0x4d710a | `8b 40 1c` | query 0xfc returns node+0x1c |
| 0x4d73a5 | `81 c7 50 02 00 00` | watcher list at inst+0x250 |
| 0x4937a0 | `83 ec 20 55 8b e9 8b 45 14` | evaluator, count W+0x14 |
| 0x4937e7 | `38 5e 19 74 07 c6 46 18 01` | first evaluation = inside |
| 0x493983 | `e8 48 b8 ff ff` | kind 0 -> 0x48f1d0 |
| 0x49398c | `d9 46 0c` / 0x49399e `d9 46 10` | min / max |
| 0x4d5a54 | `83 bd 80 00 00 00 00` | event drop test +0x80 |
| 0x4d5a5f | `f6 85 90 00 00 00 09` | event drop test +0x90 & 9 |
| 0x4d9b10 | `0f b6 81 78 01 00 00 c3` | J+0x178 type |
| 0x48f2db | `e8 10 2c 05 00 dc 0d a8 52 84 00` | hinge: 0x4e1ef0 then x [0x8452a8] |
| 0x8452a8 | `25 cf 03 0d dc a5 4c 40` | 57.29577951 (double) |
| 0x4e1ea0 / 0x4e1ef0 | `e9 bb 85 ff ff` / `e9 3b 8a ff ff` | jmp 0x4da460 / 0x4da930 |
| 0x4da930 | `55 8b ec 83 e4 f0 83 ec 5c 56 8b f1 8b 86 5c 01 00 00` | hinge angle (rad) |
| 0x4da460 | `55 8b ec 83 e4 f0 83 ec 4c a1 e8 d7 8b 00` | slider position |
| 0x4d9fc0 | `8b 44 24 04 d9 44 24 08 c1 e0 04 03 c1 d9 98 d8 00 00 00` | limits lo / hi store |
| 0x4d9f50 | `8b d1 8b 4c 24 04 8a 82 78 01 00 00` | limit enable bit |
| 0x4d2680 | `51 d9 46 04 83 ec 08 dd 05 38 11 84 00` | hinge limits deg -> rad (0x841138 = pi/180) |
| 0x4d8fd0 | `d9 81 08 01 00 00 83 a1 5c 01 00 00 fe d9 99 60 01 00 00 c3` | body wake |

## 3. WRITE path

Options evaluated:

| Option | Verdict |
|---|---|
| Write body pose / joint value directly | ❌ no value field exists (value derived from body poses each call); moving bodies means rewriting position + rotation of the moving part consistently with the joint anchors, velocities, contact cache and render bones - not provable safe |
| Motor (action 13 path 0x4d6350 -> 0x4d45e0 -> 0x4d29f0: vel deg->rad 0x4da160, force 0x4da190, enable 0x4da0c0) | possible, but needs a closed loop in TruMenu (velocity until inside, then stop); the motor velocity also enters the limit row (0x4e2104) - more coupling |
| **Limits [v, v] (action 12 internals)** | **recommended** - it is how the engine itself moves and locks these joints (mirror_left initial hinge [30, 30]; mirror_right initial slider [-790.1, -790.1]; every "locked" node uses lo == hi); the solver pulls the joint to the window, the engine's own watcher sees the crossing and fires the event |
| Set node via message kind 1 (0x4d7680) | fallback only, see below |

**Recommended write (per frame from the pad hook = game thread, outside PhysicsSystem::Step):**

1. Find J for the joint record (read chain), axis 0 for hinge / slider.
2. Save `J+0x174`, `J+0xd8+16*axis`, `J+0xdc+16*axis` once (to restore).
3. Every frame while driving: `J+0xd8+16a = J+0xdc+16a = target` (hinge: **radians** = deg x pi/180; slider: units),
   `J+0x174 |= (2 << a)` (limit on), `J+0x174 &= ~(0x10 << a)` (motor off - the mirror's second uber "lock" / nodes 1 / 5
   set a 1e6 hinge motor that would fight the limit), and wake both bodies like 0x4d8fd0 does:
   `body+0x15c &= ~1; body+0x160 = body+0x108` for `[J+0x160]` and `[J+0x15c]` if non-zero (action 13 wakes
   `[inst+0x274]` the same way before it writes a motor).
4. Stop when the uber node (b+0x84) reaches the wanted node, or after a timeout (e.g. 5 s); then restore the saved
   fields, or leave them if the puzzle should stay solved (node 9 has no actions; the next node entry rewrites them).
   Target the middle of the window (left mirror -60.5 deg, right mirror 120.0 deg, rail ends 2528.45 / +-1264.2).

This is data-equivalent to action 12 (0x4d4510 -> 0x4d2680 / 0x4d9fc0 + 0x4d9f50) except that node+0x10 (limits
record ptr) is not touched, so the save keeps the engine's own record. Proven: the setter fields and that the limit row
0x4e20bd.. reads `J+0x174 & (2<<a)` and `J+0xd8/+0xdc` ✅; that the joint converges in a few frames (ERP-style
correction, engine uses up to 790-unit snaps) 🔶; physics of a part still touched by Lara ⬜.

Risks: (a) **dropped edge**: an enter / leave arriving while `[b+0x80] != 0` or `[b+0x90] & 9` is lost and the watcher
flag is already updated - TruMenu must check the node after the crossing and, if unchanged, drive out of the window and
back in; with a slow drive two edges in one frame are unlikely. (b) Hinge windows near +-180 wrap. (c) Node actions on
entry rewrite limits / motors of other joints (wanted). (d) Do not drive while Lara holds / pushes the object. (e) J+0x174
bits other than the two named are left alone.

**Fallback - message kind 1 (set node) through 0x4d7680**: 0x4d7440 sets b+0x84, runs the node's actions, clears
b+0x80 / b+0x88. It skips: the physical pose (the mirror stays where it is), all limits / motors of the target node's
predecessors stay (node 9 has no actions), and the watcher flags still describe the real pose - node 9's only exit is
"leave [-64, -57]", which cannot fire until the player turns the mirror into and out of the window. Whether the script hook
`mirror_left_on` (script 8773 f1 -> unit script 8742 f6, sets a global sticky bool) runs on a set-node: ⬜.

## 4. Test cases (base game, from the dumps)

Mirrors `sa_uo_mirror_left` (DTP 10415, DESC @0x6a4, intro 2072) / `_right` (DTP 10431, intro 2073), l2_puzzleroom.
Joints: hinge @0x300 {type 0, A -1, B 0} (degrees), slider @0x374 {type 2, A 0, B 1, 0x101} (units). Node graph is the
same in both: 0 initial -> 10 delay (2 s) -> 7 prism_locked_low (left) / 1 rev_locked_low (right); ring
7 -> 6 / 8, 6 -> 5 / 7, 5 -> 4 / 6, 4 -> 3 / 5, 3 -> 2 / 4 / **9 SOLVED**, 2 -> 1 / 3, 1 -> 2 / 8, 8 -> 7 / 1; 9 -> 3 on leave.

| Object | Watched ranges (watch kind 0) | Solve |
|---|---|---|
| mirror_left | hinge [87, 93], [-93, -87], **[-64, -57]**; slider [2519.0, 2537.9] (high end), [-9.5, 9.5] (low end); rail limits [0, 2528.45] | node 3 (slider locked [2528.45, 2528.45]) + hinge enter [-64, -57] -> node 9. From 7: hinge -> +90 (7->6), slider -> 2528 (6->5 on leaving [-9.5,9.5], 5->4 on entering [2519,2538]), hinge -> -60.5 (4->3 on leaving [87,93], 3->9) |
| mirror_right | hinge [87, 93], [-93, -87], **[117, 123]**; slider [1254.7, 1273.7], [-1273.7, -1254.7]; rail [-1264.2, 1264.2] | node 3 (slider [1264.2, 1264.2]) + hinge enter [117, 123] -> 9. From 1 (hinge locked -90): slider -> 1264 (1->2), hinge -> 120 (2->3 on leaving [-93,-87], passes [87,93]: 3->4->3, then 3->9) |
| mirror second uber (left DTP DESC @0x650) | none; motors only: initial -> lock after 5 s (hinge motor 1e6, slider motor 316); command table 0 = msg kind 2 val 2, 1 = command 0 (unpause -> lock), 2 = command 1 (lock -> unpause) | reason for the "motor off" step |
| ca_uo_calendar (DTP 15859) | DESC @0x17fc hinge @0x8f8 [148, 153]: 1/3 -> 2 "solved"; DESC @0x18a4 hinge @0x884 {0, 6, 5} [85, 95]: 1/5 -> 2 "solved"; DESC @0x17a8 hinge @0x96c [-3, 5]: 2 -> 1 "link_joint_engaged_solved" | one-joint cases (good first test) |
| sa_uo_thor_bridge_combo (DTP 9882) | hinge @0x600: [-10, 30], [-4, 80], [81, 176], [177, 179], [-175, -100], [0, 20], [20, 40]; nodes two -> three ([81,176]) -> four ([177,179]) -> five ([-175,-100]) | multi-step dial (wrap near 180!) |
| sa_uo_shiva_left_scale (DTP 10438) | hinge @0x220: scale_down -> scale_up on [-5, 5]; let_down / delay -> waiting_for_arm on [-35, -22] | |
| sa_uo_shiva_right_scales_linked (DTP 10477) | hinge @0x254: low_ready -> delay_two on [16, 50]; high_ready -> delay_one on [-15, 15] | |
| ca_uo_thor_statue_arms (DTP 14419) | hinge @0x2d4 start -> pulled_open on [40, 50]; hinge @0x260 closing -> hammer_closed [2, 6], postWait -> hammer_open [65, 75] | |

## 5. Open points

- ⬜ Live: list order / indices of the mirror joints, J+0x178 types (expect 1 hinge, 3 slider), values at rest.
- ⬜ Live: convergence time of a [v, v] limit on the mirror hinge, and whether contacts (Lara, rail) stop it.
- ⬜ What sends commands to the mirror's second uber (lock / unpause) and whether it re-locks while driving.
- ⬜ Which uber node change runs the mirror scripts' vt 55 / 56 (mirror_*_on / _off) - decides whether the set-node
  fallback lights the beam.
- 🔶 Watch kind 1 (rate, 0x48f3b0) and 2 (0x4da010, level-triggered) semantics; not used by the mirrors.
