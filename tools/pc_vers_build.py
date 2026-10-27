"""Build work/generic/pc_vers.json and pc_vers_content.json (missing glue, reconstructed).

dlc_generic.convert_drm gives converted base-content sections the section 'ver' the PC uses (Script ver = content
version id). It reads two tables that no script in the repository writes:
  pc_vers.json          {'type:pcid': ver}   runtime version per PC section id: most frequent over all PC DRMs,
                                             a section in patch.000 wins (runtime authoritative)
  pc_vers_content.json  {'type:pcid:md5(data)[:16]': ver} for the generic types (2, 7, 8, 11) and, for Scripts,
                        also {'8:pcid:n' + md5(script_conv.deps_normalized(data, reloc))[:16]: ver}
Sources: work/idx_pc.json (every PC DRM, section headers incl. ver; from tools/index_all.py) for pc_vers, the PC side
of the pair caches (work/generic/pairs.pkl + pairs_patch.pkl, data kept for the generic types) for pc_vers_content.

Usage (from the repository root):  ..\\bin\\venv\\Scripts\\python.exe -I tools/pc_vers_build.py
"""
import sys, os, json, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_conv as SC
from generic_cache import load_pairs

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic')
GENERIC = (2, 7, 8, 11)


def most_common(votes, patch):
    out = {}
    for k, c in votes.items():
        out[k] = patch[k] if k in patch else c.most_common(1)[0][0]
    return out


def main():
    st = collections.Counter()
    # runtime version per PC section id, from the index of every PC DRM
    votes, patch = collections.defaultdict(collections.Counter), {}
    for rec in json.load(open(os.path.join(W, '..', 'idx_pc.json'))):
        path, secs = rec[0], rec[5]
        if not isinstance(secs, list): continue
        for t, i, size, nreloc, spec, ver, flags in secs:
            k = '%d:%d' % (t, i)
            votes[k][ver] += 1
            if path.endswith('patch.000'): patch[k] = ver
        st['pc_drms_indexed'] += 1
    pv = most_common(votes, patch)
    st['pc_vers'] = len(pv)
    st['pc_vers_multi'] = sum(1 for c in votes.values() if len(c) > 1)
    st['pc_vers_patch'] = len(patch)

    # content version per (type, pcid, data md5) from the PC side of the pairs
    cvotes, cpatch = collections.defaultdict(collections.Counter), {}
    P = load_pairs()
    for nm, (x, p) in P.items():
        for s in p[1]:
            if s['type'] not in GENERIC or s['data'] is None: continue
            keys = ['%d:%d:%s' % (s['type'], s['id'], hashlib.md5(s['data']).hexdigest()[:16])]
            if s['type'] == 8:
                nk = hashlib.md5(SC.deps_normalized(s['data'], R.parse(s['reloc'], 'le'))).hexdigest()[:16]
                keys.append('8:%d:n%s' % (s['id'], nk))
            for k in keys:
                cvotes[k][s['ver']] += 1
                if nm.startswith('patch:'): cpatch[k] = s['ver']
    pvc = most_common(cvotes, cpatch)
    st['pc_vers_content'] = len(pvc)
    st['pc_vers_content_multi'] = sum(1 for c in cvotes.values() if len(c) > 1)

    json.dump(pv, open(os.path.join(W, 'pc_vers.json'), 'w'))
    json.dump(pvc, open(os.path.join(W, 'pc_vers_content.json'), 'w'))
    for k, v in sorted(st.items()): print(k, v)
    print('wrote pc_vers.json, pc_vers_content.json')


if __name__ == '__main__':
    main()
