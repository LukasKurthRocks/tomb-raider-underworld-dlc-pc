"""Group N 12.11.2026: apply group N's ENGINE.md rows / corrections to one copy of docs/ENGINE.md (working tree or a
HEAD copy for the temporary-index commit). Idempotent: a row already present is skipped. Keeps the file's own line
ends / BOM.

Usage (from trudlcport):
  ../bin/pyt -t 60 work/n_research_1211/engine_rows.py FILE
"""
import sys

ROWS = [  # (anchor = start of the line after which the row goes, row)
    ('| DLC copies of base sections (Q112) |',
     '| Checkpoint chime DTP 906 / PC 3512 (group N) | DTP 3512 is the checkpoint\'s SoundPlex tree (only user: '
     'script 3482 member +0x290): root Assign (data +0x10) -> Envelope -> wave leaf 926 (`ui_checkpoint`, priority 99). '
     'Word +0x50 = Assign data +0x40 = **sound group**: base 55, DLC 1 units 5. Reader = the Assign ctor, retail '
     '0x822443d8 (0x8224465c `lwz r10,0x40(r30)`), TU 0x822428a8 (0x82242b2c), read at every start of the sound; an '
     'outer Assign with a group (not 0 / -1) wins. Groups 5 and 55 differ only in the parent: 55 -> 14 -> 6 (pause '
     'list) -> 5 -> 4, so 55 pauses with the pause menu and follows world fades, 5 does not. DTP table: the first '
     'loaded copy wins (TU 0x821f2d10, retail 0x821f4c38, table 0x8287ba80) - the DLC unit registers its copy before '
     'it requests the checkpoint object -> 5 on the Xbox 🔶 | PC 0x590b16 (`mov eax,[edi+0x40]` in 0x590970) / '
     '0x54dd10; the patch generalbank (and our kit generalbank) holds DTP 3512 (55) and script 3482 -> always 55 | '
     'nothing built; option: per-unit plugin write of 5 into `[[0xc36f28+3512*4]+0x10]+0x50` in the 10 DLC 1 units '
     '(pipeline renumbering would need script 3482 / object 83 too); workspace `Befund-Gruppe-N-1211.md` ✅ data / 🔶 '
     'audible only when pausing during the chime |'),
    ('| `corebase` | f7 print 0x795e30,',
     '| `corebase` f15 / f16 (group N) | binder 0x7b3920 (vtable 0x861eec slot 3): f15 and f16 = **0x79eb10** -> '
     '0x60d630 `xor al,al` = **false** | **f16 = isPlatformXenon()** (debug text before the call in the swan-dive '
     'scripts): retail 0x82497c38 / TU 0x824c9fc8 store **1** (binders 0x82497210 / 0x8249d150, TU slot +0x1d4); f15 '
     '= 0 on all three (retail 0x824c6a60, TU 0x824c09e0; scripts 7 / 8 / 44 / 121, "legal_demo" - isDemo 🔶). f16 '
     'users (81 PC units + generalbank, `tools/script_ref_find.py 230 0x234`): every achievement script (22: 5, 4715, '
     '4716, 7745, 7746, 11224, 13910, 13911, 15545, 17178, 17210, 17444, 17510, 11568, 6003, 9515, 11393, 13923, '
     '16274, 7017, 17834, 18497) and the non-achievement scripts 7 (pause menu), 8 (main menu controller port), 42 '
     '(DialogNoInput), 77 (saving screen, in every unit). So on PC no `achievement` native is ever reached; a '
     'global true would also switch 7 / 8 / 42 / 77 to their Xbox paths | ✅ |'),
    ('| `corebase` f15 / f16 (group N) |',
     '| GameGlobals (script 5) achievement checks (I-3, group N) | f1 (proto +0x27d0): isPlatformXenon && stickybool '
     'm100 && m128 && m156 -> `achievement` f12 (27); f2 (proto +0x27ec): n = f3() = set count of m184 / m212 / m240, '
     'n == 1 / 2 / 3 -> f13 (14) / f14 (17) / f15 (18) (op45 = int `==` 0x57da66). Setters: m100 `l4_ballcourt` '
     '15545 (< 45 s, then f9), m128 `l5_valgrind` 17444 (< 50 s, f10), m156 `l5_valaskjalf_entryb` 17178 (< 40 s, '
     'f11) - each calls f1; m212 `l1_kraken_room` 4716 (dive_from_top), m184 `l1_ship_exterior` 7745 / 7746, m240 '
     '`l2_cliffclimb` 11224 - each calls f2; all behind isPlatformXenon | stickies = save data ("in one adventure") '
     '| ✅ |'),
    ('| GameGlobals (script 5) achievement checks (I-3, group N) |',
     '| Exe-awarded achievements (I-4, group N) | PC keeps every function without its award block: chapter end '
     '**0x5561e0** (flags `[0xc59264]+0x424 + k*20`, hook after 0x55627d), reward pickup **0x5db6a0** (hook 0x5db783, '
     'esi = reward record, kind [esi] 1 treasure / 2 relic, counts `[0xc59264]+0x3ee90 + (kind*16+chapter)*4`, totals '
     '0xe7b9b8 🔶), enemy hit **0x63aaa0** (LP `[ebx+0x2c64]` before 0x63ab40 / after 0x63ab6b), chimney jump '
     '**0x75e350** (counter +0x4ec, hook 0x75e386) | Xbox (retail / TU): chapter end 0x822018d8 / 0x821ff9b8 (from the '
     'level exit; table 0x82052aa0 chapter 0..7 -> 1, 40..46 = the "register" id, doubles f0-f7); rewards 0x822a2e80 '
     '/ 0x8229fc08 (treasures 10 / 50 / 100 / all -> 4 / 5 / 9 / 10, relics 1 / 3 / 6 -> 11 / 12 / 13, TU chapters 8 / '
     '9 -> 48-53; counts 0x822a0188, totals 0x822a01e0 / 0x8297c3c0); enemy hit 0x822f9058 / 0x822f6a50 (= PC 0x63aaa0; '
     'a kill = LP > 0 before and <= 0 after; static block 0x827799a4: grenade kills per grenade 2 / 3 -> 30 / 31, '
     'attacker == vehicle `[[0x829892b0]+0xf00]` (PC `[[0xfadb58]+0xf00]` 🔶) 1 / 5 -> 28 / 29, no projectile + hit '
     '+0x6e 1 / 10 -> 37 / 38); chimney jump 0x8245c778 / 0x82460920 (state 0x395, thresholds player data bytes +0x844 '
     '/ +0x845 -> 21 / 22); all need a signed-in profile (0x8301b360 + idx*0x328 +0x10) | ✅ Xbox / 🔶 single PC fields |'),
    ('| Object request of a new kind, anim pool free (Q83, group K) |',
     '| Extra object reference across a level change (Q83, group N) | A ref taken with 0x5c1760 is never dropped by '
     'the engine: `STREAM_LevelLoadAndInit` **0x5d30d0** loads the new unit (0x5d23f0), waits in 0x5d2870 (ends with '
     '`jmp 0x5c75e0` = every status-1 entry cancelled by 0x5c1a00, "Cancelling load of object: %s") and dumps the other '
     'units with **0x5d1a10** -> 0x5d1750 ("Dumping unit: %s") -> 0x5c1900 = one release per intro (player id '
     '`[0xe7f1c4]` skipped). Draining every entry (`while [entry]: 0x54f020`, NO_DUMP 0x20000 cleared) is **0x5c1a80**, '
     'called only by the shutdown 0x5df975; exit to the menu = `STREAM_DumpAllLevels` 0x5d1a80 + 0x5c1790(player). So '
     'an `arena.load` kind stays resident (status 2, children too) after a level change; one still loading is '
     'cancelled | ✅ static |'),
    ('| Screenshot frame without HUD (Q78, group K) |',
     '| Screenshot capture chain (Q78, group N) | 0x774aa0 = **CaptureAndSaveTask** run (vtable 0x85fcd4, ctor 0x774a20, '
     'SaveAsNewFileTask 0x7748b0 at +0xc); device vf+0xd4 = **0x5077e0** (`[0xa1407c]`, vtable 0x8492cc): '
     'CreateOffscreenPlainSurface(w, h, A8R8G8B8, SYSTEMMEM) + **GetFrontBufferData** + LockRect, windowed = desktop-'
     'size surface cropped to the client rect, packed w*h*4 buffer (vf+0x90 0x507480 frees it); encoder **0x695ae0**'
     '(pixels, w, h, &size, 85) = libjpeg 6b (`jpeg_CreateCompress` 0x683de0 with 62 / 0x168), RGB, **quality 85**, '
     'rows 0x695a10 (XRGB -> RGB, width <= 4096), returns the JPEG buffer; file "Screenshot%i.raw" (0x85fc24, '
     'GenerateUniqueFilenameTask) = serializer 0x774d00 {u8 title len, title, u16 text len, text, u32 size, JPEG}. '
     'PC SavingTask 0x774f70 serializes, calls the done callback and frees - **no write**; TU SavingTask 0x82476168 '
     'writes through 0x8248b278 after a free-space check (0x8248ac68); TU CaptureAndSave run 0x82476a78 | ✅ static |'),
]

REPL = [  # (old, new) substring corrections
    ('Task 0x774ba0 = capture 0x7745a0 (vtable 0x85fbac) + SaveAsNewFile 0x774650',
     'Task 0x774ba0 = SetInfoTask (LoadingTask 0x7745a0, vtable 0x85fbac + SavingTask 0x774650; corrected by group N)'),
    ('reward code 0x8229fc08 missing on PC',
     'reward code 0x8229fc08 = PC 0x5db6a0 without its achievement block (group N)'),
]


def main(argv):
    p = argv[0]
    raw = open(p, 'rb').read()
    bom = raw.startswith(b'\xef\xbb\xbf')
    t = raw.decode('utf-8-sig')
    nl = '\r\n' if '\r\n' in t else '\n'
    lines = t.split(nl)
    added = 0
    for anchor, row in ROWS:
        if any(l == row for l in lines):
            continue
        idx = [i for i, l in enumerate(lines) if l.startswith(anchor)]
        if len(idx) != 1:
            sys.exit('anchor not unique / missing (%d): %s' % (len(idx), anchor))
        lines.insert(idx[0] + 1, row)
        added += 1
    t = nl.join(lines)
    rep = 0
    for old, new in REPL:
        if new in t:
            continue
        if t.count(old) != 1:
            sys.exit('replacement text not unique / missing: %s' % old)
        t = t.replace(old, new); rep += 1
    open(p, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + t.encode('utf-8'))
    print('%s: %d rows added, %d corrections' % (p, added, rep))


if __name__ == '__main__':
    main(sys.argv[1:])
