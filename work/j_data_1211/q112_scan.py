"""Q112 (b), read-only: do the DLC packs (pack10 DLC 1, pack11 DLC 2, pack1 / pack2 / pack20 costumes) ship their own
version of a base-game section - same (type, Xbox id) as a section of the Xbox base game (TitleUpdate / layer1 /
layer2), other content?

Phase dlc : every DRM record of every pack -> per section (type, id, size, normalised hash).
Phase base: every Xbox base DRM that holds one of those keys (work/idx_xbox_base.json) -> {key: {hash: [(src, name)]}}.
            src = 'tu' (TitleUpdate.000) or 'retail' (layer record not superseded by a TU record of the same name) or
            'retail-old' (layer record that the TU replaces).
Normalised hash = md5 over (internal relocs, external relocs as (target type, id, src, dst), id refs, data) - the
generic_store.norm_hash rule (section-index independent).
Class per DLC section: new (key not in the Xbox base), base-same (hash = a current base content), base-old (hash =
only a retail-old content), changed (key in base, other content).
Record level: a pack record whose (name hash, spec) is also a base record -> raw-content md5 equal / different.

Usage (from trudlcport): ../bin/pyt -t 3000 work/j_data_1211/q112_scan.py OUT_DIR
Writes OUT_DIR/q112_scan.pkl (all data) and prints a summary.
"""
import sys, os, json, pickle, hashlib, collections
sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
from archive import Archive
from names import load, L
import drm_reloc as R
import drm_write as DW

DLC_ROOT = '../data/Xenia-SteveRepack/Content/534307EC/00000002/'
TU = '../data/TombRaiderUnderworld_Patched/TitleUpdate.000'


def nhash(s, secs, endian):
    r = R.parse(s.reloc, endian)
    ext = tuple((secs[si].type, secs[si].id, so, do) for si, so, do in r.external)
    return hashlib.md5(repr((r.internal, ext, r.idref, r.idref_a)).encode() + (s.data or b'')).hexdigest()


def read_drm(arcs, path, i, endian):
    a = arcs.get(path)
    if a is None: a = arcs[path] = Archive(path, endian)
    raw = a.read(a.idx[i])
    return raw, DW.read(raw, endian)


def main(out):
    xn = load(L + 'Tomb Raider Underworld (Xenon).txt')
    dn = {}
    for ln in open('work/generic/dlc_names.txt', encoding='utf-8', errors='replace'):
        p = ln.split(None, 5)
        if len(p) == 6: dn[(int(p[0], 16), p[1])] = p[5].strip()
    arcs = {}
    # ---- phase dlc
    dlc = []           # (pack, recidx, hash, spec, name, [(t, id, size, h)], rawmd5)
    want = set()
    for rec in json.load(open('work/idx_dlc.json')):
        path, i, h, spec, size, secs = rec[:6]
        pk = os.path.basename(path).split('.')[0]
        name = dn.get((h, pk)) or xn.get(h, '%08x' % h)
        if not isinstance(secs, list):
            dlc.append((pk, i, h, spec, name, None, None, path)); continue
        raw, d = read_drm(arcs, path, i, 'be')
        rows = [(s.type, s.id, len(s.data or b''), nhash(s, d.sections, 'be')) for s in d.sections]
        dlc.append((pk, i, h, spec, name, rows, hashlib.md5(raw).hexdigest(), path))
        want.update((t, sid) for t, sid, _, _ in rows)
    print('dlc records %d, DRMs %d, distinct section keys %d' % (len(dlc), sum(1 for x in dlc if x[5]), len(want)))
    # ---- phase base
    bidx = json.load(open('work/idx_xbox_base.json'))
    tu_names = {(r[2], r[3]) for r in bidx if r[0] == TU}
    base = collections.defaultdict(lambda: collections.defaultdict(list))
    basekeys = collections.defaultdict(list)     # key -> [(src, name, size)] from the index (all base DRMs)
    base_rec_md5 = {}                            # (name hash, spec, src) -> raw md5 (for the record-level check)
    dlc_names_set = {(x[2], x[3]) for x in dlc}
    nread = 0
    for rec in bidx:
        path, i, h, spec, size, secs = rec[:6]
        src = 'tu' if path == TU else ('retail-old' if (h, spec) in tu_names else 'retail')
        name = xn.get(h, '%08x' % h)
        if (h, spec) in dlc_names_set:
            a = arcs.get(path) or arcs.setdefault(path, Archive(path, 'be'))
            base_rec_md5[(h, spec, src)] = (hashlib.md5(a.read(a.idx[i])).hexdigest(), name)
        if not isinstance(secs, list): continue
        hit = [s for s in secs if (s[0], s[1]) in want]
        for s in secs: basekeys[(s[0], s[1])].append((src, name, s[2]))
        if not hit: continue
        raw, d = read_drm(arcs, path, i, 'be'); nread += 1
        for s in d.sections:
            k = (s.type, s.id)
            if k in want: base[k][nhash(s, d.sections, 'be')].append((src, name))
    print('base DRMs read %d, keys found in base %d' % (nread, len(base)))
    pickle.dump(dict(dlc=dlc, base={k: dict(v) for k, v in base.items()}, base_rec_md5=base_rec_md5,
                     basekeys={k: v for k, v in basekeys.items() if k in want}), open(os.path.join(out, 'q112_scan.pkl'), 'wb'))
    print('written', os.path.join(out, 'q112_scan.pkl'))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1])
