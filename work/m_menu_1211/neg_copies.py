"""Group M (TruMenu 0.22.34): write mutated copies of TruMenu.cpp for negative tests of check_02234 (read only on the
source; every mutation must hit exactly one place).

Usage (from trudlcport):  ../bin/pyt work/m_menu_1211/neg_copies.py OUTDIR
then per copy:            ../bin/pyt tools/trumenu_ini_check.py --cpp OUTDIR/neg_<n>.cpp   (exit 1 expected)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CPP = os.path.join(HERE, '..', '..', 'src', 'asi', 'TruMenu', 'TruMenu.cpp')

MUTATIONS = [
    ('pose_outside_photo', '    if (!g_pmActive) { Out(o, n, "refused: only in the photo mode (photo.on first)"); return false; }\n',
     ''),
    ('pose_no_section_test', 'if (section != kPpLastSection + 1 - pose) {', 'if (false) {'),
    ('undo_in_cutscene', '} else if (LevelChangePending(pending, sizeof(pending)) || CinematicNow()) {',
     '} else if (false) {'),
    ('leave_without_undo', '        PpUndo(reason, pose, sizeof(pose));\n', ''),
    ('ach_id_changed', '{27, 10, "Master Speed Demon", true}', '{26, 10, "Master Speed Demon", true}'),
    ('ach_byte_row_changed', '{0x007abc5f, "6820667900 6a0f 8bce e883acdcff"}', '{0x007abc5f, "6820667900 6a0e 8bce e883acdcff"}'),
    ('ach_patch_without_checks', 'g_achOk = DvChecks(kAchChecks, sizeof(kAchChecks) / sizeof(kAchChecks[0]), &at);',
     'g_achOk = true;'),
    ('spawn_warn_refuses', '    if (kidWarn[0]) Log(1, "ai.spawn %s: WARNING %s", name, kidWarn);\n',
     '    if (kidWarn[0]) { Log(1, "ai.spawn %s: WARNING %s", name, kidWarn); return false; }\n'),
    ('chapter_back_to_norse', '{"Base game l1", "l1_norse_hallway_a", false, "779 780", nullptr},',
     '{"Base game l1", "l1_norse_hallway_a", false, "779 780", "Kapitel 1.2 Niflheim|Chapter 1.2 Niflheim"},'),
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
