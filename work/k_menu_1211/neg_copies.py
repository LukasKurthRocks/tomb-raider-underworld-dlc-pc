"""Group K (TruMenu 0.22.33): write mutated copies of TruMenu.cpp for negative tests of check_02233 (read only on the
source; every mutation must hit exactly one place).

Usage (from trudlcport):  ../bin/pyt work/k_menu_1211/neg_copies.py OUTDIR
then per copy:            ../bin/pyt tools/trumenu_ini_check.py --cpp OUTDIR/neg_<n>.cpp   (exit 1 expected)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CPP = os.path.join(HERE, '..', '..', 'src', 'asi', 'TruMenu', 'TruMenu.cpp')

MUTATIONS = [
    ('no_spawn_block', 'QlSpawnBlock(id, qlWhy, sizeof(qlWhy));', 'qlWhy[0] = 0;'),
    ('pause_not_ours', 'g_pmPauseOurs && ReadDword(kStreamFlags, &flags) && (flags & 0x1000)',
     'ReadDword(kStreamFlags, &flags) && (flags & 0x1000)'),
    ('pool_no_reserve', 'animFree < q.anims + 100', 'animFree < q.anims'),
    ('byte_row_changed', '{0x005d47a7, "c60543f1e70006"}', '{0x005d47a7, "c60543f1e70007"}'),
    ('shutdown_game_call', '    if (g_pmUiOurs) *reinterpret_cast<volatile BYTE *>(kUiHidden) = 0;\n    InterlockedExchange(&g_pmActive, 0);\n}\n// ---- end of 0.22.33 photo mode',
     '    if (g_pmUiOurs) *reinterpret_cast<volatile BYTE *>(kUiHidden) = 0;\n    reinterpret_cast<CameraRestoreFn>(kCameraRestore)(reinterpret_cast<void *>(kCameraManager), 0);\n    InterlockedExchange(&g_pmActive, 0);\n}\n// ---- end of 0.22.33 photo mode'),
]


def main(argv):
    if not argv:
        print(__doc__.strip())
        return 2
    out = argv[0]
    os.makedirs(out, exist_ok=True)
    src = open(CPP, encoding='utf-8', newline='').read().replace('\r\n', '\n')
    bad = 0
    for i, (name, old, new) in enumerate(MUTATIONS, 1):
        n = src.count(old)
        if n != 1:
            print('mutation %s: %d hits (need 1)' % (name, n))
            bad += 1
            continue
        path = os.path.join(out, 'neg_%d_%s.cpp' % (i, name))
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(src.replace(old, new).replace('\n', '\r\n'))
        print('wrote %s' % path)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
