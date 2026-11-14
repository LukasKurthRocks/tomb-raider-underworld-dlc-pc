"""W1 (2026-11-14): check the collision BVH nodes of unit / map DRMs (read-only).

Why: the PDA sonar hang 13.11. 21:03 (dump tru_notfall_16252) loops in the ray-vs-mesh walk tru 0x46c450 on a node
outside the node array of the mesh of dlc_yggdrasil_hall01_map.drm. The walk (0x46c566) treats a node as a leaf only
when byte +0x0d != 0; an inner node's far child is node + u32(+0x08) * 16, the near child node + 16.

Node (16 B): +0 / +4 float split values, +8 u32 child offset (inner) or first face (leaf), +0xc u8 axis, +0xd u8 leaf
face count, +0xe / +0xf u8 (unknown). Mesh header layout: tools/collision_faces.py.

Usage (from the repository root):
  ../bin/pyt -t 600 work/w1_1411/w1_map_bvh.py file PATH.drm [PATH.drm ...]   (PC little-endian file)
  ../bin/pyt -t 600 work/w1_1411/w1_map_bvh.py xbox NAME.drm [...]             (Xbox DLC source, big-endian)
  ../bin/pyt -t 600 work/w1_1411/w1_map_bvh.py pc NAME.drm [...]               (PC base game, little-endian)
  add --raw N to print the first N suspicious nodes with their bytes
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_reloc as R


SHOW = []   # --nodes k1,k2: print these nodes raw


class Sec(object):
    def __init__(self, t, i, data, reloc):
        self.type, self.id, self.data, self.reloc = t, i, data, reloc


def load_file(path):
    import drm_write as DW
    D = DW.read(open(path, 'rb').read(), 'le')
    return [Sec(s.type, s.id, s.data, s.reloc) for s in D.sections], 'le'


def load_xbox(name):
    import convert_dlc as CD
    import drm_write as DW
    raw, pk = CD.raw_dlc(name)
    if raw is None: return None, None
    D = DW.read(raw, 'be')
    return [Sec(s.type, s.id, s.data, s.reloc) for s in D.sections], 'be'


def load_pc(name):
    import dtp_word_classes as C
    secs = C.find(C.PC, 'le', 'pc-w' + C.BS + name)
    if secs is None: return None, None
    return [Sec(s['type'], s['id'], s['data'], s['reloc']) for s in secs], 'le'


def rels(S, e):
    out = []
    for s in S:
        r = R.parse(s.reloc, e)
        out.append((dict(r.internal), {so: (si, do) for si, so, do in r.external}))
    return out


def target(rel, si, o):
    itn, ext = rel[si]
    if o in itn: return si, itn[o]
    if o in ext: return ext[o]
    return None


def meshes(S, rel, e):
    E = '<' if e == 'le' else '>'
    t = target(rel, 0, 0)
    if t is None: return []
    ti, to = t
    td = S[ti].data
    ntg = struct.unpack_from(E + 'i', td, to + 8)[0]
    groups = []
    g = target(rel, ti, to + 0xc)
    if g is not None: groups += [(g[0], g[1] + 0x50 * k) for k in range(ntg)]
    g2 = target(rel, ti, to + 0x10)
    if g2 is not None and g2 not in groups: groups.append(g2)
    out, seen = [], set()
    for gi, (gs, go) in enumerate(groups):
        m = target(rel, gs, go + 0x38)
        if m is None or m in seen: continue
        seen.add(m)
        ms, mo = m; md = S[ms].data
        nn, nf = struct.unpack_from(E + '2I', md, mo + 0x40)
        out.append((gi, ms, mo, nn, nf, target(rel, ms, mo + 0x38)))
    return out


def scan_meshes(S, rel, e):
    """map DRMs have no Level in section 0: find mesh headers by their three pointers +0x30 / +0x34 / +0x38"""
    E = '<' if e == 'le' else '>'
    out = []
    for si, s in enumerate(S):
        itn, ext = rel[si]
        ptr = set(itn) | set(ext)
        for o in sorted(ptr):
            h = o - 0x38
            if h < 0 or (h + 0x30) not in ptr or (h + 0x34) not in ptr or h + 0x4c > len(s.data): continue
            nn, nf, nv = struct.unpack_from(E + '3I', s.data, h + 0x40)
            if not (0 < nn < 2000000 and 0 < nf < 2000000 and 0 < nv < 2000000): continue
            out.append(('s%d+0x%x' % (si, h), si, h, nn, nf, target(rel, si, h + 0x38)))
    return out


def check(label, S, e, raw):
    E = '<' if e == 'le' else '>'
    rel = rels(S, e)
    M = meshes(S, rel, e) or scan_meshes(S, rel, e)
    tot_bad = 0
    print('%s (%s): %d collision meshes' % (label, e, len(M)))
    for gi, ms, mo, nn, nf, nref in M:
        if nref is None: print('  group %s: no node array' % gi); continue
        ns, no = nref; nd = S[ns].data
        leaf = inner = bad = eonly = selfref = 0
        shown = 0
        for k in range(nn):
            o = no + 16 * k
            if o + 16 > len(nd): bad += 1; continue
            idx = struct.unpack_from(E + 'I', nd, o + 8)[0]
            b = nd[o + 0xc:o + 0x10]
            if b[1] != 0:
                leaf += 1
                if idx + b[1] > nf: bad += 1
                continue
            if b[2] != 0: eonly += 1
            far = k + idx
            if idx == 0: selfref += 1
            if far >= nn or idx == 0 or k + 1 >= nn:
                bad += 1
                if shown < raw:
                    shown += 1
                    print('    node %d: %s' % (k, nd[o:o + 16].hex()))
            else:
                inner += 1
        for k in SHOW:
            if k < nn: print('    show node %d: %s' % (k, nd[no + 16 * k:no + 16 * k + 16].hex()))
        tot_bad += bad
        print('  group %s: nodes %d faces %d | leaf %d, inner ok %d, BAD %d (of them +0xd==0 && +0xe!=0: %d, child offset 0: %d)'
              % (gi, nn, nf, leaf, inner, bad, eonly, selfref))
    print('  => %s: bad nodes total %d' % (label, tot_bad))


def compare(pc_path, xname, quiet=False):
    """byte +0xc..+0xf of every node: PC file vs Xbox source (same order) - kept / u32-swapped / other"""
    S1, e1 = load_file(pc_path); S2, e2 = load_xbox(xname)
    R1, R2 = rels(S1, e1), rels(S2, e2)
    # TerrainGroup collision meshes (unit DRMs, Level in section 0) first; the pointer scan only for *_map.drm
    # (the scan also hits unrelated structures in object DRMs, so it is not used there)
    M1, M2 = meshes(S1, R1, e1), meshes(S2, R2, e2)
    if not M1 and not M2 and pc_path.lower().endswith('_map.drm'):
        M1, M2 = scan_meshes(S1, R1, e1), scan_meshes(S2, R2, e2)
    total = 0
    for (l1, _, _, nn, nf, r1), (l2, _, _, nn2, _, r2) in zip(M1, M2):
        d1 = S1[r1[0]].data; d2 = S2[r2[0]].data
        kept = swapped = other = both = 0
        kinds = {}
        sw_idx = []
        for k in range(min(nn, nn2)):
            a = d1[r1[1] + 16 * k + 0xc:r1[1] + 16 * k + 0x10]; b = d2[r2[1] + 16 * k + 0xc:r2[1] + 16 * k + 0x10]
            leaf = 'leaf' if b[1] else 'inner'
            if a == b and a == b[::-1]: both += 1; key = 'same+sym'
            elif a == b: kept += 1; key = 'kept'
            elif a == b[::-1]: swapped += 1; key = 'u32-swapped'; sw_idx.append(k)
            else: other += 1; key = 'other'
            kinds[(leaf, key)] = kinds.get((leaf, key), 0) + 1
        if nn != nn2: print("    NODE COUNT DIFFERS %s: pc %d xbox %d" % (l1, nn, nn2))
        if quiet and not swapped: continue
        print('%s mesh %s: nodes %d: kept %d, u32-swapped %d, symmetric %d, other %d' % (os.path.basename(pc_path), l1, nn, kept, swapped, both, other))
        for kk in sorted(kinds): print('    %s %s: %d' % (kk[0], kk[1], kinds[kk]))
        if sw_idx:
            print('    swapped node index range %d..%d (section offsets 0x%x..0x%x)' % (
                sw_idx[0], sw_idx[-1], r1[1] + 16 * sw_idx[0], r1[1] + 16 * sw_idx[-1]))
        total += swapped
    if len(M1) != len(M2): print('    MESH COUNT DIFFERS: pc %d xbox %d' % (len(M1), len(M2)))
    return total


def compare_dir(d):
    """every *.drm of DIR (PC tree) against its Xbox DLC source: meshes with u32-swapped node flag bytes"""
    tot = files = 0
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith('.drm'): continue
        try:
            import convert_dlc as CD
            if CD.raw_dlc(f)[0] is None: continue
            files += 1
            n = compare(os.path.join(d, f), f, quiet=True)
        except Exception as ex:
            print('  %s: error %s' % (f, ex)); continue
        if n: print('SWAPPED %s: %d nodes' % (f, n))
        tot += n
    print('dir %s: %d DRMs with an Xbox source, swapped nodes total %d' % (d, files, tot))


def main(argv):
    raw = 0
    if argv and argv[0] == 'compare':
        compare(argv[1], argv[2]); return
    if argv and argv[0] == 'dir':
        for d in argv[1:]: compare_dir(d)
        return
    if '--nodes' in argv:
        k = argv.index('--nodes'); SHOW.extend(int(x) for x in argv[k + 1].split(',')); del argv[k:k + 2]
    if '--raw' in argv:
        k = argv.index('--raw'); raw = int(argv[k + 1]); del argv[k:k + 2]
    mode, names = argv[0], argv[1:]
    for n in names:
        if mode == 'file': S, e = load_file(n)
        elif mode == 'xbox': S, e = load_xbox(n)
        else: S, e = load_pc(n)
        if S is None: print('%s:%s not found' % (mode, n)); continue
        check('%s:%s' % (mode, os.path.basename(n)), S, e, raw)


if __name__ == '__main__':
    main(sys.argv[1:])
