"""Which section types does work/generic/idmap.json map, and how many ids each (read-only)."""
import json
d = json.load(open('work/generic/idmap.json'))
print({k: len(v) for k, v in d.items()})
