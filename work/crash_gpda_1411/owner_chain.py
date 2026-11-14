"""Read-only: which member / argument / local of a script owns an offset (reverse internal-pointer chain up to the
20-byte entry whose init pointer (+16) starts the tree), plus the entry with a given name.
Usage (repo root): ../bin/pyt work/crash_gpda_1411/owner_chain.py DRM SCRIPT_ID OFF_HEX [NAME_HEX ...]"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm_write as DW, drm_reloc as R
import script_member_pairs as MP


def main(argv):
    D = DW.read(open(argv[0], 'rb').read(), 'le')
    s = [x for x in D.sections if x.type == 8 and x.id == int(argv[1])][0]
    rel = R.parse(s.reloc, 'le')
    back = {}
    for o, t in rel.internal: back.setdefault(t, []).append(o)
    _, E = MP.entries(s.data, s.reloc, 'le')
    init_of = {}
    for kind, lst in E.items():
        for q in lst:
            if q['init'] is not None: init_of[q['init']] = (kind, q)
    off = int(argv[2], 16)
    # walk back: nearest pointer target at or below off, then who points to it
    seen = set(); frontier = [off]; depth = 0
    while frontier and depth < 12:
        nxt = []
        for a in frontier:
            tg = max((t for t in back if t <= a and a - t < 0x400), default=None)
            if tg is None or tg in seen: continue
            seen.add(tg)
            if tg in init_of:
                kind, q = init_of[tg]
                print('owner: %s #%d name 0x%x tag %d userType %d entry +0x%x init +0x%x (offset +0x%x is +0x%x into the tree node chain)' % (
                    kind, q['k'], q['name'], q['tag'], q['ut'], q['a'], tg, off, a - tg))
            for o in back[tg]:
                print('  depth %d: +0x%x -> +0x%x (target for +0x%x)' % (depth, o, tg, a))
                nxt.append(o)
        frontier = nxt; depth += 1
    for nm in argv[3:]:
        v = int(nm, 16)
        for kind, lst in E.items():
            for q in lst:
                if q['name'] == v: print('name 0x%x: %s #%d tag %d userType %d entry +0x%x' % (v, kind, q['k'], q['tag'], q['ut'], q['a']))


if __name__ == '__main__':
    main(sys.argv[1:])
