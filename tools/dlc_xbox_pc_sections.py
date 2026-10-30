"""Section inventory of one DLC DRM: the decoded Xbox original (work/generic/dlc_drms.pkl) next to a converted PC
file (read-only). Per section type the count and total size on both sides; with --list every section in file
order (Xbox id / PC id, size). Ids are not compared (the converter remaps them), the order is the same unless
sections were added or dropped. Finding 43 follow-up (DLC 2 rock vein: does the start unit lose a section?).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/dlc_xbox_pc_sections.py NAME PC.drm [--pack ack11.000] [--list] [--type N]
  NAME = DRM name without .drm as in the Yura Xenon list (e.g. dlc_level2_start)
"""
import sys, os, pickle, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic')
TYPES = {0: 'general', 2: 'empty/anim', 5: 'texture', 6: 'wave', 7: 'dtp', 8: 'script', 9: 'shaderlib',
         10: 'material', 11: 'object', 12: 'mesh', 13: 'unit/obj'}


def xbox_sections(name, pack):
    C = pickle.load(open(os.path.join(W, 'dlc_drms.pkl'), 'rb'))
    base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
    hits = [(k, v) for k, v in C.items() if k[0] == pack and base(k[1]) == name.lower()]
    if not hits: raise SystemExit('no %s in %s of dlc_drms.pkl' % (name, pack))
    if len(hits) > 1: print('note: %d records, using spec %s' % (len(hits), hits[0][0][2]))
    return [(s['type'], s['id'], s['size'], s['data']) for s in hits[0][1][1]]


def relation(x, p):
    """how a PC section's bytes relate to the Xbox ones: same / swapped32 (every u32 byte-swapped) / share of
    equal u32 words after a 32-bit swap"""
    if x == p: return 'identical bytes'
    if len(x) != len(p): return 'size differs'
    n = len(x) // 4
    sw = sum(1 for k in range(n) if x[4 * k:4 * k + 4][::-1] == p[4 * k:4 * k + 4])
    same = sum(1 for k in range(n) if x[4 * k:4 * k + 4] == p[4 * k:4 * k + 4])
    return 'u32 swapped %d/%d, unchanged %d/%d' % (sw, n, same, n)


def main(argv):
    pack = 'ack11.000'; lst = False; only = None; args = []
    it = iter(argv)
    for a in it:
        if a == '--pack': pack = next(it)
        elif a == '--list': lst = True
        elif a == '--type': only = int(next(it))
        else: args.append(a)
    name, pc = args
    X = xbox_sections(name, pack)
    P = [(s.type, s.id, len(s.data), s.data) for s in DW.read(open(pc, 'rb').read(), 'le').sections]
    print('%s: Xbox %d sections, PC %d sections' % (name, len(X), len(P)))
    cx, cp = collections.Counter(), collections.Counter()
    sx, sp = collections.Counter(), collections.Counter()
    for t, _, n, _ in X: cx[t] += 1; sx[t] += n
    for t, _, n, _ in P: cp[t] += 1; sp[t] += n
    for t in sorted(set(cx) | set(cp)):
        mark = '' if cx[t] == cp[t] else '   <-- count differs'
        print('  type %2d %-10s Xbox %4d (%9d B)  PC %4d (%9d B)%s' % (
            t, TYPES.get(t, '?'), cx[t], sx[t], cp[t], sp[t], mark))
    if lst:
        for k in range(max(len(X), len(P))):
            x = X[k] if k < len(X) else None; p = P[k] if k < len(P) else None
            if only is not None and (x or p)[0] != only: continue
            fx = '%2d %6d %8d' % x[:3] if x else '-'
            fp = '%2d %6d %8d' % p[:3] if p else '-'
            rel = relation(x[3], p[3]) if (x and p and x[0] == p[0]) else 'type differs'
            print('  %4d  xbox %-20s  pc %-20s  %s' % (k, fx, fp, rel))


if __name__ == '__main__':
    main(sys.argv[1:])
