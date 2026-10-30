"""For the materials of one Xbox DLC DRM: which shader libraries they use, how tools/shader_map.py mapped each
(class A / B = exact, C1-C3 / D = surrogate), the constant + sampler names of the DLC library, and the most similar
base Xbox libraries with the base objects (DRM names) whose materials use them at the same tuple position.
Read-only. Finding 43 follow-up ("base shader for variant objects": the grapple ring was cured by the base object's
own PC shaders; this lists such base peers for any DLC object, e.g. the DLC 2 waterfall dlc2_goo_spout).

Usage (from the repository root; needs work/render/shaderlibs.pkl, dlc_shader_map.json, material_x2p.pkl,
work/idx_xbox_base.json, work/idx_pc.json):
  ../bin/pyt -t 900 tools/shader_peer_report.py XBOX_DLC.drm [--top N] [--material ID] [--words N] [--pc PC.drm]
  --summary: one line per material (tuple, map class per lib, count of base materials with the same tuple)
  --words N: header words +0x40..+0x5f (render state) of the DLC material (Xbox, and PC with --pc) and of N base
             materials with the same shader tuple, Xbox and PC - how the base game converts them
"""
import sys, os, json, pickle, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import shader_map as SM
from shaderlib import constants, norm_name
from bigfile import read_index
from names import load as load_names, L as NAME_DIR

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work')
POS = ('ps0', 'ps1', 'ps2', 'vs')


def owners(idx_file, names_file, mtype=10):
    """section id -> sorted DRM names that hold a section of that type (from tools/index_all.py's index)"""
    nm = load_names(NAME_DIR + names_file); hashes = {}; out = collections.defaultdict(set)
    for rec in json.load(open(idx_file)):
        path, i, secs = rec[0], rec[1], rec[5]
        if not secs: continue
        if path not in hashes: hashes[path] = read_index(path, 'be' if 'Patched' in path else 'le')
        h = hashes[path][i]['hash']
        name = nm.get(h, '%08x' % h).split('\\')[-1]
        for s in secs:
            if s[0] == mtype: out[s[1]].add(name)
    return out


def ctab(lib):
    """per occupied slot entry: sorted (norm name, regset, reg, count); union over slots"""
    seen = set()
    for s in lib['slots']:
        if s == 0xffffffff: continue
        _, c = constants(lib['entries'][s]['blob'], 'x')
        for n, rs, ri, rc in c: seen.add((norm_name(n), rs, ri, rc))
    return sorted(seen, key=lambda t: (t[1], t[2], t[0]))


def hexw(d, e):
    return ' '.join('%08x' % w for w in struct.unpack_from(e + '8I', d, 0x40))


def main(argv):
    top = 5; only = None; words = 0; PCD = None
    if '--top' in argv: k = argv.index('--top'); top = int(argv[k + 1]); del argv[k:k + 2]
    if '--material' in argv: k = argv.index('--material'); only = int(argv[k + 1]); del argv[k:k + 2]
    if '--words' in argv: k = argv.index('--words'); words = int(argv[k + 1]); del argv[k:k + 2]
    summary = '--summary' in argv; argv = [a for a in argv if a != '--summary']
    if '--pc' in argv:
        k = argv.index('--pc'); PCD = {x.id: x.data for x in DW.read(open(argv[k + 1], 'rb').read(), 'le').sections if x.type == 10}
        del argv[k:k + 2]
    D0 = DW.read(open(argv[0], 'rb').read(), 'be')
    L = SM.load_libs(); X, D, XM = L['X'], L['D'], L['XM']
    smap = json.load(open(os.path.join(W, 'render', 'dlc_shader_map.json')))
    mx2p = pickle.load(open(os.path.join(W, 'render', 'material_x2p.pkl'), 'rb'))
    xown = owners(os.path.join(W, 'idx_xbox_base.json'), 'Tomb Raider Underworld (Xenon).txt')
    FX = {k: SM.features(l) for k, l in X.items()}
    use = collections.defaultdict(set)          # (base lib, tuple position) -> base Xbox material ids
    for mid, (d, r) in XM.items():
        for p, s in enumerate(SM.tuple_of(d)):
            if s: use[(s, p)].add(mid)
    for s in D0.sections:
        if s.type != 10 or (only is not None and s.id != only): continue
        t = SM.tuple_of(s.data)
        same = sorted(mid for mid, (d, r) in XM.items() if SM.tuple_of(d) == t)
        if summary:   # one line: tuple with map class per lib, number of base materials with the same tuple
            print('material %6d  %s  same-tuple base mats %d' % (s.id, '  '.join('%s:%s/%s' % (
                POS[p], x, smap.get(str(x), {}).get('cls', '?')) if x else '%s:-' % POS[p] for p, x in enumerate(t)), len(same)))
            continue
        print('== material %d  tuple %s' % (s.id, ' '.join('%s:%s' % (POS[p], x or '-') for p, x in enumerate(t))))
        if same:      # base materials with exactly this shader tuple (Xbox ids; the DLC material itself if it is a base one)
            print('  same tuple in base: %d materials, e.g. %s' % (len(same), '; '.join(
                '%d (PC %s, %s)' % (mid, mx2p.get(mid), ','.join(sorted(xown.get(mid, ()))[:3])) for mid in same[:6])))
        if words:     # header words +0x40..+0x5f: Xbox -> PC of this material and of the base materials with this tuple
            pcm = PCD.get(s.id) if PCD else None
            print('  words +40..+5c  DLC xbox %s' % hexw(s.data, '>'))
            if pcm is not None: print('  words +40..+5c  DLC pc   %s' % hexw(pcm, '<'))
            for mid in same[:words]:
                pm = L['PM'].get(mx2p.get(mid))
                print('  words +40..+5c  base %5d xbox %s  pc %s' % (mid, hexw(XM[mid][0], '>'),
                                                                    hexw(pm[0], '<') if pm else '-'))
        for p, lid in enumerate(t):
            if not lid: continue
            m = smap.get(str(lid), {})
            lib = D.get(lid) or X.get(lid)
            print('  %s lib %d  class %s -> PC %s  (%s%s)' % (POS[p], lid, m.get('cls', '?'), m.get('pc'), m.get('basis', ''),
                                                          ', score %s' % m['score'] if 'score' in m else ''))
            if lib is None: print('    (lib not in shaderlibs.pkl)'); continue
            for n, rs, ri, rc in ctab(lib):
                print('    %s%-3d x%d  %s' % ('csbs'[rs] if rs < 4 else '?', ri, rc, n))
            if m.get('cls') in ('A', 'B'): continue
            fd = SM.features(lib)
            cand = sorted(((SM.sim(fd, FX[b]), b) for b in X if FX[b]['kind'] == fd['kind'] and use.get((b, p))), reverse=True)[:top]
            for sc, b in cand:
                mats = sorted(use[(b, p)])
                objs = sorted(set(o for mid in mats for o in xown.get(mid, ())))
                pcm = sorted(set(mx2p[mid] for mid in mats if mid in mx2p))
                print('    peer base lib %d  sim %.3f  %s  materials %s  PC mats %s  objects %s' % (
                    b, sc, '<- surrogate' if b == m.get('surrogate') else '', mats[:6], pcm[:6],
                    ', '.join(objs[:8]) + (' ...' if len(objs) > 8 else '')))


if __name__ == '__main__':
    main(sys.argv[1:])
