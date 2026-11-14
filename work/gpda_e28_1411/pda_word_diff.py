"""E2-8 one-off (read-only): every section of two PC g_pda.drm builds (old e1e03e13 = knowledge G20261111-3, new =
G20261114-4) - which differ, and per differing script the changed 32-bit words with the walker label of the old
section (member entry / init node / code) and the entry they belong to (members / args / locals: name, tag, userType).
Also the risk lists of the two build reports.
usage: ../bin/pyt -t 600 work/gpda_e28_1411/pda_word_diff.py OLD.drm NEW.drm [OLD_REPORT.json NEW_REPORT.json]
"""
import sys, os, struct, json, collections
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.realpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
import drm_write as DW, drm_reloc as R, script_conv as SC
import script_member_pairs as MP


def owner_map(d, rl):
    """{byte offset: (kind, k, tag, ut, name, part)} for entries and the leaves of their init trees"""
    import script_init_from_pc as SIP
    W, ents = MP.entries(d, rl, 'le')
    own = {}
    for kind, lst in ents.items():
        for q in lst:
            info = (kind, q['k'], q['tag'], q['ut'], q['name'])
            for o in range(q['a'], q['a'] + 20, 4): own[o] = info + ('entry +%d' % (o - q['a']),)
            if q['init'] is not None:
                for p, o in SIP.leaves(W, W.it, q['init']): own[o - o % 4] = info + ('init %s' % (list(p),),)
    return W, own


def main(argv):
    a, b = argv[0], argv[1]
    A = {(s.type, s.id): s for s in DW.read(open(a, 'rb').read(), 'le').sections}
    B = {(s.type, s.id): s for s in DW.read(open(b, 'rb').read(), 'le').sections}
    print('sections: old %d, new %d; only old %s; only new %s' % (len(A), len(B), sorted(set(A) - set(B)), sorted(set(B) - set(A))))
    total = 0
    for k in sorted(set(A) & set(B)):
        x, y = A[k], B[k]
        if x.data == y.data and x.reloc == y.reloc: continue
        nd = 0; rows = []
        m = min(len(x.data), len(y.data))
        own, lab = {}, {}
        if k[0] == 8:
            W, own = owner_map(x.data, x.reloc); lab = W.lab
        for o in range(0, m - 3, 4):
            if x.data[o:o + 4] != y.data[o:o + 4]:
                nd += 1
                rows.append((o, x.data[o:o + 4].hex(), y.data[o:o + 4].hex(), own.get(o), lab.get(o)))
        total += nd
        print('section %s: %d -> %d bytes, %d words differ, relocations %s' % (
            k, len(x.data), len(y.data), nd, 'equal' if x.reloc == y.reloc else 'DIFFER'))
        cls = collections.Counter((r[3][0] + ' ' + r[3][5].split(' [')[0] if r[3] else 'not in an entry / init') for r in rows)
        print('   by place: %s' % dict(cls))
        for r in rows:
            print('   +0x%05x %s -> %s  %s  %s' % (r[0], r[1], r[2], r[3], r[4]))
    print('words differing in total: %d' % total)
    if len(argv) >= 4:
        ra = json.load(open(argv[2])); rb = json.load(open(argv[3]))
        def risks(r):
            out = []
            for sk, v in r.get('per_script', {}).items():
                for x in v.get('risks', []): out.append(x if isinstance(x, str) else json.dumps(x))
            return out
        xa, xb = risks(ra), risks(rb)
        print('risks old %d, new %d' % (len(xa), len(xb)))
        for x in sorted(set(xa) - set(xb)): print('   gone: %s' % x)
        for x in sorted(set(xb) - set(xa)): print('   new:  %s' % x)
        for key in ('risks', 'risk', 'summary'):
            if key in ra: print('report key %s present' % key)


if __name__ == '__main__':
    main(sys.argv[1:])
