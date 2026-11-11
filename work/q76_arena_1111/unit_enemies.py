"""Q76 test arena: which enemy objects each unit lists in objlist.dat (read-only).

Usage (from the repository root):
  ../bin/pyt -t 120 work/q76_arena_1111/unit_enemies.py OBJECTLIST.TXT OBJLIST.DAT [--all]
Enemy = object name matching the enemy name list below (AI enemies of the base game + DLC; generators / chunkdolls
are shown separately because ai.spawn refuses them). Prints one line per unit with at least one enemy.
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import objlists as OL

ENEMY = re.compile(r'^(merc|merc_deux|bat_enemy|tiger|cat_panther|panther_thrall|mayan_thrall|viking_thrall|yeti_thrall'
                   r'|yeti_thrall_yggdrasil|small_albino_spider|small_brown_spider|small_brown_spider_no_jump'
                   r'|giant_albino_tarantula|giant_albino_tarantula_blind|shark_blueshark|shark_greenland|jellyfish_a'
                   r'|amanda|natla_end|.*thrall.*dlc.*|.*_dlc2?_?thrall.*)$')
SKIP = re.compile(r'generator|chunkdoll|^co_|^ar_|^ms_|^fx_|lying')


def main(argv):
    names = OL.read_objectlist(open(argv[0], 'rb').read())
    recs, _ = OL.read_objlist(open(argv[1], 'rb').read(), 'le')
    for unit, ids in recs:
        en = sorted(names[i] for i in ids if i in names and ENEMY.match(names[i]) and not SKIP.search(names[i]))
        gen = sorted(names[i] for i in ids if i in names and 'generator' in names[i])
        if en or ('--all' in argv and gen):
            print('%-40s enemies: %s%s' % (unit, ', '.join(en) or '-', ('  | generators: ' + ', '.join(gen)) if gen else ''))


if __name__ == '__main__':
    main(sys.argv[1:])
