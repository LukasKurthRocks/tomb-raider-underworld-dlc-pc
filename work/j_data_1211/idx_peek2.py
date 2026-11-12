"""Is field 2 of the index records the archive name hash? (read-only)"""
import json, sys, os
sys.path.insert(0, 'tools')
from archive import Archive
for f, e in (('work/idx_dlc.json', 'be'), ('work/idx_xbox_base.json', 'be')):
    d = json.load(open(f)); arcs = {}; ok = bad = 0
    for r in d:
        a = arcs.get(r[0]) or arcs.setdefault(r[0], Archive(r[0], e))
        x = a.idx[r[1]]
        if x['hash'] == r[2] and x['spec'] == r[3]: ok += 1
        else:
            bad += 1
            if bad < 3: print(' mismatch', r[:5], hex(x['hash']), hex(x['spec']), x['size'])
    print(f, 'hash/spec equal', ok, 'different', bad)
