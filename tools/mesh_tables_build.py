"""Learn the two mesh tables that mesh_convert.py reads but no upstream tool writes (finding 37).

  work/render/pc_vdecl_hash.pkl  {((sem, off, pctype), ...): 8-byte PC vertex-declaration hash}
                                 every vertex format of every PC base Mesh section (pairs_render.pkl, PC side)
  work/render/dec3n_lut.pkl      [1024] Xbox DEC3N 10-bit component -> PC UBYTE4N byte
                                 majority vote over the base pairs: Mesh sections paired by position (as
                                 mesh_validate.py does), batches with the same vertex count, Xbox element type
                                 0x11 against PC type 5 at the same offset (bytes x>>20, x>>10, x -> b0, b1, b2);
                                 every Xbox Mesh id counts once (its first pair, like mesh_validate's unique ids)
                                 - this reproduces B138's mapping exactly (tools/dec3n_check.py --variants)
Without them mesh_convert falls back to a synthetic md5 hash and a formula ("89 % agreement").

Usage (from the repository root, needs work/render/pairs_render.pkl from tools/rend_extract.py pairs):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/mesh_tables_build.py
"""
import sys, os, pickle, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mesh_convert as MC

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'render')


def main():
    pairs = pickle.load(open(os.path.join(W, 'pairs_render.pkl'), 'rb'))
    decl = {}; conflicts = collections.Counter(); votes = [collections.Counter() for _ in range(1024)]
    st = collections.Counter()
    by = collections.defaultdict(lambda: [collections.Counter() for _ in range(1024)]); seen_x = set()
    for nm, X, P in pairs:
        if X is None or not isinstance(P, list): continue
        for a, b in zip(X, P):
            if a['type'] != 12 or b['type'] != 12 or a['data'][0x10:0x14] != b'hseM': continue
            st['mesh_pairs'] += 1
            try:
                Mp = MC.parse(b['data'], 'le', b['reloc']); Mx = MC.parse(a['data'], 'be', a['reloc'])
            except Exception:
                st['parse_error'] += 1; continue
            if Mp['empty'] or Mx['empty']: continue
            first = a['id'] not in seen_x; seen_x.add(a['id']); sizeok = len(a['data']) == len(b['data'])
            for pb in Mp['batches']:
                vf = pb['vf']
                if not vf: continue
                k = tuple((s, eo, t) for s, eo, t, _ in vf['elems'])
                if k in decl and decl[k] != vf['hash']: conflicts[k] += 1
                decl.setdefault(k, vf['hash'])
            if len(Mx['batches']) != len(Mp['batches']): st['batching_differs'] += 1; continue
            for xb, pb in zip(Mx['batches'], Mp['batches']):
                if not xb['vf'] or not pb['vf'] or xb['numVerts'] != pb['numVerts']: st['batch_skipped'] += 1; continue
                xs, ps = xb['vf']['stride'], pb['vf']['stride']
                pt = {eo: t for s, eo, t, _ in pb['vf']['elems']}
                for s, eo, t, _ in xb['vf']['elems']:
                    if t != 0x11 or pt.get(eo) != 5: continue
                    xd, pd = xb['vdata'], pb['vdata']
                    for v in range(xb['numVerts']):
                        x = struct.unpack_from('>I', xd, v * xs + eo)[0]
                        q = pd[v * ps + eo:v * ps + eo + 3]
                        for ci, (c, byte) in enumerate(zip(((x >> 20) & 0x3ff, (x >> 10) & 0x3ff, x & 0x3ff), q)):
                            if first: votes[c][byte] += 1
                            by[(s, ci, sizeok, first)][c][byte] += 1
                    st['dec3n_elements'] += first
    fallback = [max(0, min(255, int(127.5 + ((v - 1024 if v >= 512 else v) / 4.0)))) for v in range(1024)]
    lut, agree, total, unseen = [], 0, 0, 0
    for v in range(1024):
        if votes[v]:
            byte, n = votes[v].most_common(1)[0]; lut.append(byte); agree += n; total += sum(votes[v].values())
        else:
            lut.append(fallback[v]); unseen += 1
    pickle.dump(decl, open(os.path.join(W, 'pc_vdecl_hash.pkl'), 'wb'))
    pickle.dump(lut, open(os.path.join(W, 'dec3n_lut.pkl'), 'wb'))
    pickle.dump(votes, open(os.path.join(W, 'dec3n_votes.pkl'), 'wb'))   # for tools/dec3n_check.py
    # votes split by (semantic, component 0-2, Xbox/PC section same size, first pair of this Xbox id): dec3n_check --variants
    pickle.dump(dict(by), open(os.path.join(W, 'dec3n_votes_by.pkl'), 'wb'))
    print('stats', dict(st))
    print('pc_vdecl_hash: %d vertex formats, %d with conflicting hashes' % (len(decl), len(conflicts)))
    print('dec3n_lut: %d components voted, majority agreement %.2f %%, %d of 1024 values unseen (formula used),'
          ' %d values differ from the formula' % (total, 100.0 * agree / total if total else 0, unseen,
                                                  sum(1 for a, b in zip(lut, fallback) if a != b)))


if __name__ == '__main__':
    main()
