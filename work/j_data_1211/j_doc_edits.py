"""Group J (12.11.): the ENGINE.md lines and the CHANGELOG row of the Q112 / B follow-up work, applied by anchor
(each anchor must match exactly once; CRLF and UTF-8 kept). Used on the working tree and on HEAD blobs for the
commit, so only these hunks go in.

Usage (from trudlcport): ../bin/pyt -t 60 work/j_data_1211/j_doc_edits.py engine|changelog IN_FILE OUT_FILE
"""
import sys

ROW_Q112 = ('| DLC copies of base sections (Q112) | Every DRM of pack10 / pack11 / pack1 / pack2 / pack20 against the Xbox '
            'base (TU + layers), key (type, Xbox id), normalised hash: **1 494 base keys carried with other content** (DTP '
            '1 362, texture 72, script 41, wave 14, mesh 3; id-less types 0 / 13 left out). Record level: only `g_pda.drm` '
            '(pack10 / 11) and `camerashakes.drm` (pack11) besides lists / locals / images (`override_merge`, '
            '`objlist_merge`). Textures: all 110 changed contents decode to identical pixels (PSNR 99) -> the PC base copy '
            'is right. DTPs: our trees ship the converted DLC version everywhere (0 PC copies); same-size changes are 1-2 '
            'words; the DLC Lara generation (costumes, `lara_doppelganger`, also `knight_thrall`, `yeti_thrall_dlc2_`) '
            'replaces one DTP reference 1 504 times (Xbox 0x483 = DTP 1155 -> 0x9f8 = DTP 2552; DLC 2552 140 B, base 2552 32 B '
            'in `lara*.drm`, so the player object decides which one is resident - on both platforms 🔶). **PC-only '
            'shadowing** (the always-loaded PC generalbank holds the id, the Xbox one does not): wave 6:10 (the TU removed '
            '`ui_drop_04`, DLC 2 reuses id 10 in 14 DRMs; PC patch and our generalbank still hold `ui_drop_04`), DTP 906 '
            '(PC 3512, held by `checkpoint.drm`; +0x50 55 -> 5 in 10 DLC 1 units), scripts 878 / 941 / 999 / 1015 / 1044 '
            '(unit scripts of the patch generalbank; every function equal -> harmless), 8453 (`scriptclash`) | ✅ data / '
            '🔶 effect of 6:10 and 906 | `work/j_data_1211/q112_*.py`, workspace `Befund-Gruppe-J-1211.md` |')

ENGINE = [
    ('| Base-game DATA in the TU (Q60) |', None, ROW_Q112),          # insert ROW_Q112 after the line holding the anchor
    ('not +0x52 | ✅ data / 🔶 meaning of +0x52 |',
     'not +0x52. Base game (group J, 12.11.): one counter per object kind (checkpoints, jellyfish, weight plates ... from '
     '24465; other series 1, 4465, 14465, 30001, 44465, 0; equal values in 6 units) - not the walking order: of 56 '
     'units with >= 2 checkpoints and a known entry portal 26 follow the entry distance, 3 are reversed, 27 mixed '
     '(pairs 567 / 380, `work/j_data_1211/cp_order_direction.py`); for `cinematic_object` it is the cinematic number '
     '= story order (1 ... 343, revisits included) | ✅ data / 🔶 meaning of +0x52 |', None),
    ('l7_arctic_sea script 19599 -> (7, 1));',
     'l7_arctic_sea script 19599 -> (7, 1)); (1, 2): script 5273 = level script of `l1_kraken_entrance` (dependency '
     'copies in 13 more units), f2 shows the card when GameGlobals (script 5) stickyint +116 < 8 and sets it, called by '
     'script 5321 f1 = intro 696 `cinematic_object` +0x52 40 (entrance gate cinematic, the script of the PC patch\'s '
     'Niflheim door fix; group J 12.11.);', None),
]

CHANGELOG_ROW = ('| 2026-11-12 | **Research: DLC / TU versions of base-game files and sections (Q112), chapter 1.2 owner, '
                 'checkpoint order** (group J; static, read-only, nothing built, nothing installed, no game started). '
                 'Besides `g_pda` / `camerashakes` (merged) and lists / locals / images, the packs carry 1 494 base section '
                 'ids with other content; textures are pixel-identical, DTPs ship converted, `scriptclash` covers 8453; two '
                 'PC-only shadowings remain open (wave 6:10 in 14 DLC 2 DRMs vs the generalbank `ui_drop_04`, checkpoint '
                 'DTP 906 / PC 3512 in 10 DLC 1 units). Chapter 1.2 starts at `l1_kraken_entrance` cinematic 40; '
                 'checkpoint +0x52 is a per-object counter, not the walking order (`work/j_data_1211/`, ENGINE.md) |')


def engine(t):
    for anchor, repl, after in ENGINE:
        if t.count(anchor) != 1: raise SystemExit('anchor not unique (%d): %s' % (t.count(anchor), anchor[:60]))
        if repl is not None:
            t = t.replace(anchor, repl)
        else:
            i = t.index(anchor); j = t.index('\r\n', i) + 2
            t = t[:j] + after + '\r\n' + t[j:]
    return t


def changelog(t):
    end = t.index('\r\n## B270')
    lines = t[:end].split('\r\n')
    k = max(i for i, l in enumerate(lines) if l.startswith('| 2026-'))
    lines.insert(k + 1, CHANGELOG_ROW)
    return '\r\n'.join(lines) + t[end:]


if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    mode, src, dst = sys.argv[1:4]
    raw = open(src, 'rb').read()
    bom = raw.startswith(b'\xef\xbb\xbf')
    t = raw.decode('utf-8-sig')
    if 'DLC copies of base sections (Q112)' in t or 'chapter 1.2 owner, checkpoint order' in t:
        raise SystemExit('already applied')
    t = engine(t) if mode == 'engine' else changelog(t)
    open(dst, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + t.encode('utf-8'))
    print('written', dst)
