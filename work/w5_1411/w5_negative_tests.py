"""W5 (2026-11-14): negative tests of trumenu_ini_check.check_02243 - each case breaks one rule in a copy of TruMenu.cpp
(read_cpp is replaced in memory, no file is written) and must yield at least one problem; the unchanged source none.

Usage (from the repository root):
  ../bin/pyt -t 300 work/w5_1411/w5_negative_tests.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import trumenu_ini_check as T

SRC = T.read_cpp()
CASES = [
    ('version', 'const char *const kVersion = "TruMenu 0.22.43 (W5 markup', 'const char *const kVersion = "TruMenu 0.22.43 (W5 marks'),
    ('check row changed', '{0x005be360, "8b510c85d27411', '{0x005be360, "8b510c85d27412'),
    ('W5Check table', 'g_w5MkOk = DvChecks(kW5MkChecks,', 'g_w5MkOk = DvChecks(kW3AtChecks,'),
    ('DrawMarkup old', 'void DrawMarkup() { W5DrawMarkup(); }', 'void DrawMarkup() { }'),
    ('no +0x2d8', 'ReadDword(owner + 0x2d8, &use) || !use) return false;', 'ReadDword(owner + 0x2d8, &use)) return false;'),
    ('bone stride', 'static_cast<short>(bone)) * 0x40', 'static_cast<short>(bone)) * 0x30'),
    ('transform', 'out[c] = p[0] * m[c] + p[1] * m[4 + c] + p[2] * m[8 + c] + m[12 + c];',
     'out[c] = p[0] * m[c] + p[1] * m[4 + c] + p[2] * m[8 + c];'),
    ('skip bit 31', 'if (flags & 0x80000000u) return true;', 'if (flags & 0x40000000u) return true;'),
    ('skip owner flags', '(oflags & 0x20000002u)', '(oflags & 0x20000000u)'),
    ('skip unit +5', 'ReadByte(entry + 5, &b) && b', 'ReadByte(entry + 4, &b) && b'),
    ('no object skip', 'if (local && !xform) { ++skipped; continue; }', 'if (false) { ++skipped; continue; }'),
    ('type item', 'ReadByte(item + 0x4d, &tb)', 'ReadByte(item + 0x4c, &tb)'),
    ('id record', 'ReadWord(rec + 0x2e, &w)', 'ReadWord(rec + 0x2c, &w)'),
    ('occlusion', 'alpha = P5OcclFactor(here, mid);', 'alpha = 1.0f;'),
    ('label place', 'if (!W3LabPlace(&r, l.at, fs + 3.0f)) continue;', 'W3LabPlace(&r, l.at, fs + 3.0f);'),
    ('room off', 'if (!g_p5RoomOnly) return true;', 'if (g_p5RoomOnly) return true;'),
    ('room near', 'nearest <= g_w3RoomNear', 'nearest <= 3000.0f'),
    ('label radius', 'const float kW5LabelNear = 4350.0f;', 'const float kW5LabelNear = 9000.0f;'),
    ('type rows', '    {"Art 21", "type 21", IM_COL32(200, 200, 200, 160)},\n', ''),
    ('load order', '    W5Check();                                // 0.22.43', '    // W5Check();                             // 0.22.43'),
    ('bar order', 'first in their group\n'
                  '    {"Markup", "Markup", "draw.markup", "", kQbBool, -1, kQcMarkup, 0, kQbMarkup},\n'
                  '    {"Nur Kanten", "Ledges only", "draw.ledges", "", kQbBool, -1, kQcNone, 0, kQbMarkup},\n',
     'first in their group\n'),
    ('writes memory', 'g_w5Labels = shown;\n}', 'g_w5Labels = shown;\n    WriteDword(0, 0);\n}'),
]


def main():
    bad = 0
    T.read_cpp = lambda: SRC
    p, _ = T.check_02243()
    print('positive (unchanged source): %d problem(s) %s' % (len(p), 'ok' if not p else 'FAIL ' + '; '.join(p)))
    bad += 1 if p else 0
    for name, old, new in CASES:
        if SRC.count(old) < 1:
            print('case %-18s: pattern not found - FAIL' % name); bad += 1; continue
        mutated = SRC.replace(old, new, 1)
        T.read_cpp = lambda m=mutated: m
        p, _ = T.check_02243()
        ok = len(p) > 0
        bad += 0 if ok else 1
        print('case %-18s: %d problem(s) %s%s' % (name, len(p), 'ok' if ok else 'FAIL', (' - ' + p[0]) if p else ''))
    print('%d cases + 1 positive, %d failed' % (len(CASES), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
