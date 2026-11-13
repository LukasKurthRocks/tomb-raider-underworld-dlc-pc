"""Find the DTP section (id) whose record contains a given address, from a cdb 'dd 0xc36f28 L8000' log.
Usage: pyt find_dtp.py <dtptable.txt> <hexaddr> [<hexaddr>...]"""
import sys
ents = []
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    p = line.split()
    if len(p) < 2 or len(p[0]) != 8: continue
    try: base = int(p[0], 16)
    except ValueError: continue
    if base < 0xc36f28 or base >= 0xc36f28 + 0x20000: continue
    for k, w in enumerate(p[1:5]):
        try: v = int(w, 16)
        except ValueError: continue
        if v: ents.append(((base - 0xc36f28) // 4 + k, v))
print('entries', len(ents))
s = sorted(ents, key=lambda e: e[1])
for a in sys.argv[2:]:
    addr = int(a, 16)
    best = [e for e in s if e[1] <= addr]
    nxt = [e for e in s if e[1] > addr]
    b = best[-1]
    print('addr 0x%08x: section id %d (0x%x) record 0x%08x data 0x%08x -> offset 0x%x; next record 0x%08x (id %d)' % (
        addr, b[0], b[0], b[1], b[1] + 0x10, addr - b[1] - 0x10, nxt[0][1] if nxt else 0, nxt[0][0] if nxt else -1))
