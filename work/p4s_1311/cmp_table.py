"""Compare two aidata tables (pickled {offset: [n, set(classes)]}) by content. Usage: pyt cmp_table.py A.pkl B.pkl"""
import sys, pickle
a = pickle.load(open(sys.argv[1], 'rb')); b = pickle.load(open(sys.argv[2], 'rb'))
na = {k: (v[0], sorted(v[1])) for k, v in a.items()}; nb = {k: (v[0], sorted(v[1])) for k, v in b.items()}
print('offsets', len(na), len(nb), 'equal content', na == nb)
for k in sorted(set(na) | set(nb)):
    if na.get(k) != nb.get(k): print(hex(k), na.get(k), nb.get(k))
