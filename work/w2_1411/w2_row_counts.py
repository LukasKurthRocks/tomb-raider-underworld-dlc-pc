"""W2 (2026-11-14): row counts of the bar pages Tests / Barrierefreiheit (static rows qb_rows parses, by kind) - the
number quoted in docs/Befund-W2-TruMenu-Ordnung-1411.md for kQbViewMax.

Usage (from the repository root):
  ../bin/pyt -t 120 work/w2_1411/w2_row_counts.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import trumenu_ini_check as T

src = T.read_cpp()
for table in ('kQbTests', 'kQbAccess'):
    rows = [r for r in T.qb_rows(src, True) if r[0] == table]
    kinds = {}
    for r in rows: kinds[r[4]] = kinds.get(r[4], 0) + 1
    print('%s: %d static rows (%s)' % (table, len(rows), ', '.join('%s %d' % kv for kv in sorted(kinds.items()))))
    raw = src[src.find('const QbRow %s[] = {' % table):]
    raw = raw[:raw.find('\n};')]
    print('  row starts in the table text: %d' % raw.count('\n    {"'))
