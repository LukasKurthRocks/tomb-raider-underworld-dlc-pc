"""Peek at the record layout of the section indices (read-only)."""
import json, collections, sys
for f in ('work/idx_dlc.json', 'work/idx_xbox_base.json', 'work/idx_pc.json'):
    d = json.load(open(f)); c = collections.Counter(len(r) for r in d)
    print(f, len(d), dict(c))
    for r in d[:3]: print('  ', [x if not isinstance(x, list) else 'list%d' % len(x) for x in r])
    for r in d:
        if len(r) == 7: print('  7:', [x if not isinstance(x, list) else 'list%d' % len(x) for x in r]); break
