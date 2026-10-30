"""Language variants of the DLC cinematic streams (cinstream .mul; finding 43 follow-up, DLC intro in English).

The Xbox packs, like the PC base game (38 cinematics), keep every cinematic .mul once per language: spec 0xffffffe1
(English), 0xffffe002 (French), 0xffffe004 (German), 0xffffe008 (Italian), 0xffffe010 (Spanish); the speech AND the
subtitles (text tails of the cine blocks) differ. The kit / our audio step build one file from the English record.
The ModLoader loads a language-specific file as '<name>_%03d' with the language number (as local\\locals.bin_004),
so each variant is written as cinstream\\<name>_NNN (001 EN, 002 FR, 004 DE, 008 IT, 016 ES) next to the plain name.

Per variant: tools/mul_convert.convert (PC container with silent audio) + tools/mul_audio_nch.swap (the decoded Xbox
streams, one channel slot each, game IMA convention) - the same two steps as stages 1 and 2a for the English file.

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/mul_lang_build.py OUT_MODS_DIR pack10|pack11 [NAME.mul ...] [--check]
  without NAME: every cinstream .mul of the pack; --check: list the variants only
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc
from convert_dlc import R, PACKS

LANG = {0xffffffe1: 1, 0xffffe002: 2, 0xffffe004: 4, 0xffffe008: 8, 0xffffe010: 16}
CINE = {'pack10': ['pdlc1_010_intro.mul', 'pdlc1_030_finale.mul'],
        'pack11': ['pdlc2_000_fight.mul', 'pdlc2_020_ghoul.mul', 'pdlc2_030_pod.mul', 'pdlc2_040_podon.mul',
                   'pdlc2_045_finale.mul', 'pdlc2_050_crush.mul']}


def main(argv):
    check = '--check' in argv
    argv = [a for a in argv if a != '--check']
    out, pack = argv[0], argv[1]
    names = argv[2:] or CINE[pack]
    A = Archive(R + [p for p in PACKS if p.endswith('/%s.000' % pack)][0], 'be')
    import mul_convert as M, mul_audio_nch as MN, dlc_generic as DG
    ids = DG.DlcIds(None, None)
    st = collections.Counter()
    for nm in names:
        recs = A.find(crc('xenon-w\\cinstream\\' + nm))
        specs = {r['spec']: r for r in recs}
        print('%s: %s' % (nm, ' '.join('%08x' % s for s in sorted(specs))))
        if check: continue
        for spec, r in sorted(specs.items()):
            if spec not in LANG: st['skipped spec %08x' % spec] += 1; continue
            xd = A.read(r)
            pd = M.convert(xd, ids)
            o, info = MN.swap(xd, pd)
            q = os.path.join(out, 'cinstream', '%s_%03d' % (nm, LANG[spec]))
            os.makedirs(os.path.dirname(q), exist_ok=True); open(q, 'wb').write(o)
            st['written'] += 1
            print('  %-34s %9d bytes  channels %s  rate %s' % (os.path.basename(q), len(o), info.get('channels'), info.get('rate')))
    print(dict(st))


if __name__ == '__main__':
    main(sys.argv[1:])
