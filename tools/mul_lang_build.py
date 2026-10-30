"""Language variants of the DLC cinematic and voice streams (.mul; finding 43 follow-up, DLC intro in English).

The Xbox packs, like the PC base game (38 cinematics), keep every cinematic .mul once per language: spec 0xffffffe1
(English), 0xffffe002 (French), 0xffffe004 (German), 0xffffe008 (Italian), 0xffffe010 (Spanish); the speech AND the
subtitles (text tails of the cine blocks) differ. The kit / our audio step build one file from the English record.
The ModLoader loads a language-specific file as '<name>_%03d' with the language number (as local\\locals.bin_004),
so each variant is written as <path>\\<name>_NNN (001 EN, 002 FR, 004 DE, 008 IT, 016 ES) next to the plain name.

  cinstream  cinstream\\*.mul: tools/mul_convert.convert (PC container with silent audio) + tools/mul_audio_nch.swap
             (the decoded Xbox streams, one channel slot each, game IMA convention) - as stages 1 and 2a
  voice      audio\\streams\\**.mul with more than one language record (the radio lines of Lara / Zip in DLC 1, found
             2026-10-30: B138 ships only the English record, so they stay English on a German game):
             tools/music_convert.convert_mul + mul_audio_nch.swap, as stage 1 (convert_streams) and stage 2a. The
             plain name is written too, from the English record (B138's English voice lines measure 14-33 dB against
             the decoded Xbox source, ours 32-36 dB).

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/mul_lang_build.py OUT_MODS_DIR pack10|pack11 [NAME.mul ...] [--check] [--no-voice]
  without NAME: every cinstream .mul of the pack and every localised voice stream; --check: list the variants only
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
NAMES = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic', 'dlc_names.txt')


def voice_names(pack):
    """xenon-w\\audio\\streams\\...\\*.mul names of the pack (tools/dlc_names.py list)"""
    rows = [l.split() for l in open(NAMES, encoding='utf8', errors='ignore')]
    return sorted({r[-1] for r in rows if len(r) >= 4 and r[1] == pack and 'audio\\streams' in r[-1] and r[-1].endswith('.mul')})


def main(argv):
    check = '--check' in argv; voice = '--no-voice' not in argv
    argv = [a for a in argv if a not in ('--check', '--no-voice')]
    out, pack = argv[0], argv[1]
    jobs = [('cine', 'xenon-w\\cinstream\\' + nm) for nm in (argv[2:] or CINE[pack])]
    if voice and not argv[2:]: jobs += [('voice', nm) for nm in voice_names(pack)]
    A = Archive(R + [p for p in PACKS if p.endswith('/%s.000' % pack)][0], 'be')
    import mul_convert as M, mul_audio_nch as MN, music_convert as MC, dlc_generic as DG
    ids = DG.DlcIds(None, None)
    st = collections.Counter()
    for kind, full in jobs:
        specs = {r['spec']: r for r in A.find(crc(full))}
        langs = sorted(s for s in specs if s in LANG)
        if kind == 'voice' and len(langs) < 2: continue          # not localised (event sounds, stingers)
        rel = os.path.join(*full.split('\\')[1:])
        print('%s: %s' % (rel, ' '.join('%08x' % s for s in sorted(specs))))
        if check: continue
        for spec, r in sorted(specs.items()):
            if spec not in LANG: st['skipped spec %08x' % spec] += 1; continue
            xd = A.read(r)
            pd = M.convert(xd, ids) if kind == 'cine' else MC.convert_mul(xd)[0]
            o, info = MN.swap(xd, pd)
            targets = ['%s_%03d' % (rel, LANG[spec])] + ([rel] if kind == 'voice' and spec == 0xffffffe1 else [])
            for t in targets:
                q = os.path.join(out, t); os.makedirs(os.path.dirname(q), exist_ok=True); open(q, 'wb').write(o)
                st['written %s' % kind] += 1
                print('  %-50s %9d bytes  channels %s  rate %s' % (t, len(o), info.get('channels'), info.get('rate')))
    print(dict(st))


if __name__ == '__main__':
    main(sys.argv[1:])
