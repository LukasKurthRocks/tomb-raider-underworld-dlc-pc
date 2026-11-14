"""Q126c / TruMenu 0.22.41 (2026-11-14): write src/asi/TruMenu/TruMenu.ini = the kOpts defaults table of TruMenu.cpp, as
tools/trumenu_ini_check.py expects it (UTF-8 without BOM, LF). Same as work/attract2_1311/write_ini.py. Usage (from
trudlcport): ../bin/pyt -t 120 work/attract3_1411/write_ini.py"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import trumenu_ini_check as T      # noqa: E402

header, rows = T.table(T.read_cpp())
text = T.text(header, rows)
path = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.ini')
old = open(path, encoding='utf-8', newline='').read()
open(path, 'w', encoding='utf-8', newline='').write(text)
print('%s: %d keys, %d lines (before %d lines)' % (path, len(rows), text.count('\n'), old.count('\n')))
