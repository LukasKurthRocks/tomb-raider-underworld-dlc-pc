"""Group F (12.11.2026): insert the group-F rows into docs/ENGINE.md or CHANGELOG.md (CRLF / LF kept), by anchor lines,
so the same rows go into the HEAD blob (temporary index commit) and into the shared working-tree file.

Usage (from the repository root):
  ../bin/pyt work/f_func_1211/insert_rows.py engine|changelog IN OUT
Exit 0 = every anchor found once and no row present before; 1 = anchor missing / row already there.
"""
import sys

ENGINE = [
    ('| Lara anims on other figures (Q89) |',
     '| Animal skeletons (Q89, group F) | mesh bone counts (`work/q89_skeleton_1111/skeleton_compare.py`): `tiger` / '
     '`cat_panther` 41, `panther_thrall` 43 -> 51, `shark_blueshark` 34, `bat_enemy` 88, `giant_albino_tarantula` 65, '
     '`small_brown_spider` 28, `jellyfish_a` 2; no dog / wolf object in the PC object list. Tiger rig (parents / pivots, '
     'inferred): 0 root, 1 pelvis, 2 rear hip, 3-7 / 8-12 hind legs, 13-18 tail, 19-21 spine, 22 chest, 23-28 / 29-34 '
     'front legs, 35-36 neck, 37 head, 38 jaw. All < 113: a model on Lara\'s instance (way A) lets the player code read '
     'bone 108 / cloth 116-152 outside the matrix block -> refuse; the puppet (way B) writes only its own indices | '
     '✅ counts / \U0001f536 roles |'),
    ('| Adrenaline meter (Q65) |',
     '| Adrenaline fill (Q77, group F) | the meter fills with the **damage Lara deals**: the enemy damage path 0x63ad50 '
     'posts message **0xd9** to the player when the attacker is `[0xe7f094]` (0x63afe2), data = (int)(LP before - '
     'max(LP after, 0)) (0x63b02e..0x63b03a); player handler 0x71f1d0 (vtable 0x85e2ac) case 217 -> 0x71f4f4: skipped '
     'while CM+0x1fc bit 21, else 0x6f28c0(amount): 0xfae8af = 1, unless bit 22 meter += amount, >= max -> max and '
     '0x6e6630. Player data (`lara` DTP 850): max +0x2d0 = 500, drain +0x2d4 = 20, in adrenaline mode +0x2d8 = 225. '
     'Cases 210 (0xd2) -> 0x6e66f0 and 235 (0xeb) -> 0x6f2ab0 not read | ✅ static |'),
    ('| Camera manager |',
     '| FreeCamera (mode 5, Q78, group F) | object mgr+0xe4b0 = 0xe8e9a0 in slot `[mgr+0x18]` (0x5f3bc8), vtable 0x855e54. '
     'Activate (+0x1c) 0x5f91b0 copies position / rotation / transform / inverse of the old camera and turns player '
     'control off (0x5d5f60: byte 0x8ab4e6 = 0); deactivate (+0x20) 0x5f91a0 turns it on (0x5d5f40). Update 0x5f9770: '
     'input 0x5f92e0 (dt = `[0xe7f188]` / 30; left stick actions 0 / 1 via 0x5e9a10, right stick 2 / 3 + mouse 0x10 / '
     '0x11 via 0x5ed4a0; action 21 held = slow pair, 19 = fast pair, 20 / 22 = vertical -/+), move 0x5f94a0 (unless '
     '+0x134), look at the bone of instance +0xd4 (0x5f9570) else free rotation 0x5f96a0, transform 0x5e0970, inverse '
     '0x49be10. Tuning = generalbank **DTP 16** = GlobalInfo +0x134 (GlobalInfo `[0xe7ee50]` = DTP 2 data + 0xf0; word 0 '
     '= 5): FOV +0x6c = 50 deg, slow pair +0x74 / +0x7c = 0.25 / 0.25, fast pair +0x78 / +0x80 = 10 / 2, vertical +0x70 '
     '= 200. **`CAMERA_SetMode` 0x5f39f0 handles only 6 / 11 / 12** - mode 5 is entered through the base layer '
     '0x5edd70 (thiscall mgr, mode, blend; mgr+0x7c set = only stored) and left with 0x5edf50 | ✅ static / '
     '⬜ live |'),
    ('| Photo call sites in the PC data (Q66) |',
     '| Photo system gate (Q78, group F) | every screenshot entry point tests byte **0xfae80d** (0x774cf2, 0x775220, '
     '0x7752a0, 0x775300, 0x775340, 0x775380, 0x7753a0, 0x7753c0, 0x7753ee, 0x775430); no instruction writes it and it '
     'lies in .bss -> always 0 on the PC. The storage getter 0x7753a0 (used by `screenshot` f2 0x77a890 / f4 0x77a8c0) '
     'returns 0 on both paths and CaptureAndSave 0x7752a0 returns on 0. Natives: `screenshotsystem` (binder 0x7b6b20) '
     'f0 0x775340 list, f2 0x774cf0 is-enabled, f3 byte 0xfae80c, f4 0x775380 photo count (`[0xfae83c]` when state '
     '`[0xfae834]` = 2), f7 0x775300, f8 0x77a940; `screenshot` (binder 0x7adc40) f2 capture-and-save, f4 0x775430. '
     'Task 0x774ba0 = capture 0x7745a0 (vtable 0x85fbac) + SaveAsNewFile 0x774650; pools 0x7744e0: `savegame%02d.sav` '
     '10 x 0x140000, `Screenshot%03d.ss` 100 x 0x80000, `profile.pro`. No frame grab found in 0x774560..0x775490 | '
     '✅ static |'),
    ('| Photo call sites in the PC data (Q66) |',
     '| Lara photo poses, field camera flag (Q78, group F) | `screen_capture_01..07` = anim table entries **1604..1598** '
     'of `lara` DTP 850 (table +0xf0, 12-byte records {u16 section, s16 slot, u32, char* name}) -> anim sections '
     '**1551..1545**, all in `lara.drm`; none of the 1502 anim slots (`tools/anim_slot_resolve.py`) refers to them, so '
     'no chart state plays a pose. Field camera on 0x6b1280 (gear slot 7 via 0x6e7b90): bytes **0xed0091** / 0xed0092 = '
     '1; off 0x6a3060; binocular gear family 1 (table 0x8afc84): 0x6b11d0, process 0x6a2b20, 0x6cba30, query 0x6c5110; '
     'script object `[0xed0110]` (g_binoculars 3243) called through 0x7a50e0 / 0x7a5100 / 0x7a5160 / 0x7a58a0 '
     '(`ScriptObject::CallFunction` 0x57b380) | ✅ static |'),
]

CHANGELOG_ROW = (
    '| 2026-11-12 | **New functions, analysis only** (group F: Q89 / Q78 / Q77; offline, no plugin source changed, '
    'nothing installed, no game started). Q78: the game\'s **FreeCamera** (mode 5) is a complete fly camera with its own '
    'input and data (generalbank DTP 16, FOV 50 deg) and turns Lara\'s control off itself, but `CAMERA_SetMode` ignores '
    'mode 5 (the base layer 0x5edd70 enters it); the cut photo path is dead on the PC (gate byte 0xfae80d never '
    'written, storage getter 0x7753a0 returns 0); the poses `screen_capture_01..07` are anim table 1598-1604 / sections '
    '1545-1551 without a chart slot. Q77: adrenaline fills with the damage Lara deals (message 0xd9 from 0x63ad50, max '
    '500); field camera flag 0xed0091; RAD marks and the grapple pull are build plans. Q89: animal skeletons (tiger 41 '
    '... jellyfish 2, no dog) and the model swap plan with six guards. One-off tools `work/f_func_1211/` '
    '(`globalinfo_ids.py`, `anim_name_index.py`, `f_natives.py`, `insert_rows.py`); ENGINE.md 5 rows |')


def main(argv):
    if len(argv) != 3 or argv[0] not in ('engine', 'changelog'):
        print(__doc__); return 2
    raw = open(argv[1], 'rb').read()
    bom = raw.startswith(b'\xef\xbb\xbf')
    text = raw[3:].decode('utf-8') if bom else raw.decode('utf-8')
    nl = '\r\n' if '\r\n' in text else '\n'      # working tree CRLF, git blob LF (core.autocrlf=true)
    lines = text.split(nl)
    if argv[0] == 'engine':
        # insert each row after the LAST already inserted row following its anchor (keeps the order of ENGINE)
        for anchor, row in ENGINE:
            if any(l == row for l in lines):
                print('row already present: %s' % row[:60]); return 1
            idx = [i for i, l in enumerate(lines) if l.startswith(anchor)]
            if len(idx) != 1:
                print('anchor %r found %d times' % (anchor, len(idx))); return 1
            k = idx[0] + 1
            while k < len(lines) and any(lines[k] == r for _, r in ENGINE): k += 1
            lines.insert(k, row)
            print('inserted after line %d: %s' % (k, row[:50]))
    else:
        if any(l == CHANGELOG_ROW for l in lines):
            print('row already present'); return 1
        stop = [i for i, l in enumerate(lines) if l.startswith('State of DLC 1 against B138')]
        if not stop:
            print('anchor "State of DLC 1 against B138" missing'); return 1
        rows = [i for i in range(stop[0]) if lines[i].startswith('| 2026-11-12 |')]
        if not rows:
            print('no 2026-11-12 row before the anchor'); return 1
        lines.insert(rows[-1] + 1, CHANGELOG_ROW)
        print('inserted after line %d' % (rows[-1] + 1))
    out = nl.join(lines).encode('utf-8')
    open(argv[2], 'wb').write((b'\xef\xbb\xbf' if bom else b'') + out)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
