"""Q112 (b), read-only: detail per changed base section of the DLC packs (rows of q112_changed.tsv, types 0 / 13 left
out - they carry no global id).

Per row (pack, DRM, type, Xbox id):
  diff   DLC section vs one Xbox base copy (TU first, then retail): size equal?, data bytes equal?, relocation blob
         equal?, number of differing 32-bit words (same size only)
  pc     PC id (work/generic/idmap.json), PC base holders (work/idx_pc.json, names from the PC file list), PC base data
         md5 of up to 3 holders (patch.000 first)
  ours   the converted file of our trees (pack10 -> TREE/dlc1/mods, pack11 -> TREE/dlc2/mods, costume packs ->
         COSTUMES/<pack>/stage2b/mods): section (type, PC id) present? data = a PC base copy ('pcbase') or not ('own')
Writes OUT_DIR/q112_detail.tsv and prints a summary per pack / type.

Usage (from trudlcport): ../bin/pyt -t 3000 work/j_data_1211/q112_detail.py OUT_DIR TREE COSTUMES
  e.g. OUT_DIR = a scratch folder outside the repository,  TREE work/rebuild/pipeline_check_1111c  COSTUMES work/rebuild/costumes_0913
"""
import sys, os, json, hashlib, collections, csv
sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
from archive import Archive
from names import load, L, crc
import drm_write as DW

BASE = ['../data/TombRaiderUnderworld_Patched/' + f for f in ('TitleUpdate.000', 'layer1.000', 'layer2.000')]
PCA = ['../data/pc/patch.000', '../data/pc/bigfile.000']
DLC_ROOT = '../data/Xenia-SteveRepack/Content/534307EC/00000002/'
PACKS = {'pack10': '9CA70CF0EDA43654D158C2E37470D301DFA850E753/pack10.000',
         'pack11': '600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153/pack11.000',
         'pack1': 'E5AFB2B959A72C52120D73678AED11BD8752686753/pack1.000',
         'pack2': '9FDDD06617D1016DE468ACF53AC663E8BA2AD41853/pack2.000',
         'pack20': 'AC0089F81B621CD0E0C156B6176EFCC6C844705D53/pack20.000'}
ARC = {}


def arc(p, e):
    a = ARC.get(p)
    if a is None: a = ARC[p] = Archive(p, e)
    return a


CACHE = collections.OrderedDict()


def secs_of(key, loader):
    if key in CACHE: CACHE.move_to_end(key); return CACHE[key]
    v = loader()
    CACHE[key] = v
    while len(CACHE) > 24: CACHE.popitem(last=False)
    return v


def read_rec(paths, endian, name):
    h = crc(name)
    for p in paths:
        a = arc(p, endian)
        r = [x for x in a.idx if x['hash'] == h and x['spec'] == 0xffffffff]
        if r:
            d = DW.read(a.read(r[0]), endian)
            return {(s.type, s.id): (s.data or b'', s.reloc) for s in d.sections}
    return None


def read_file(path):
    if not os.path.exists(path): return None
    d = DW.read(open(path, 'rb').read(), 'le')
    return {(s.type, s.id): (s.data or b'', s.reloc) for s in d.sections}


def main(out, tree, costumes):
    idmap = {int(t): {int(a): b for a, b in m.items()} for t, m in json.load(open('work/generic/idmap.json')).items()}
    pcn = load(L + 'Tomb Raider Underworld (PC).txt')
    pc_hold = collections.defaultdict(list)
    for rec in json.load(open('work/idx_pc.json')):
        if isinstance(rec[5], list):
            for s in rec[5]: pc_hold[(s[0], s[1])].append((rec[0], rec[2]))
    rows = list(csv.DictReader(open(os.path.join(out, 'q112_changed.tsv'), encoding='utf-8'), delimiter='\t'))
    rows = [r for r in rows if r['type'] not in ('0', '13')]
    rows.sort(key=lambda r: (r['pack'], r['drm']))
    res = []
    summ = collections.defaultdict(collections.Counter)
    for r in rows:
        t, xid, pk, drm = int(r['type']), int(r['xbox_id']), r['pack'], r['drm']
        dl = secs_of(('dlc', pk, drm), lambda: read_rec([DLC_ROOT + PACKS[pk]], 'be', drm))
        ds = dl.get((t, xid)) if dl else None
        bs = None; bholder = ''
        for hname in r['base_holders'].split(';'):
            if hname.startswith('+'): continue
            b = secs_of(('base', hname), lambda: read_rec(BASE, 'be', hname))
            if b and (t, xid) in b: bs = b[(t, xid)]; bholder = hname; break
        size_eq = data_eq = reloc_eq = '?'; nwd = ''
        if ds and bs:
            size_eq = 'y' if len(ds[0]) == len(bs[0]) else 'n'
            data_eq = 'y' if ds[0] == bs[0] else 'n'
            reloc_eq = 'y' if ds[1] == bs[1] else 'n'
            if size_eq == 'y':
                nwd = str(sum(1 for i in range(0, len(ds[0]) - 3, 4) if ds[0][i:i + 4] != bs[0][i:i + 4]))
        pcid = idmap.get(t, {}).get(xid)
        holders = pc_hold.get((t, pcid), []) if pcid is not None else []
        hnames = [pcn.get(h, '%08x' % h) for _, h in holders]
        pcmd5 = set()
        for (p, h) in sorted(holders, key=lambda x: 0 if 'patch' in x[0] else 1)[:3]:
            nm = pcn.get(h)
            if not nm: continue
            P = secs_of(('pc', nm), lambda: read_rec([p], 'le', nm))
            if P and (t, pcid) in P: pcmd5.add(hashlib.md5(P[(t, pcid)][0]).hexdigest())
        base = os.path.basename(drm.replace('\\', '/'))
        sub = drm.replace('\\', '/').split('xenon-w/', 1)[-1]
        if pk == 'pack10': f = os.path.join(tree, 'dlc1', 'mods', sub)
        elif pk == 'pack11': f = os.path.join(tree, 'dlc2', 'mods', sub)
        else: f = os.path.join(costumes, pk, 'stage2b', 'mods', sub)
        O = secs_of(('ours', f), lambda: read_file(f))
        if O is None: ours = 'no-file'
        elif pcid is None: ours = 'no-pcid'
        elif (t, pcid) not in O: ours = 'missing'
        else:
            om = hashlib.md5(O[(t, pcid)][0]).hexdigest()
            ours = 'pcbase' if om in pcmd5 else ('own' if pcmd5 else 'own(no-pc-holder-read)')
        res.append((t, xid, pk, drm, r['size'], bholder, size_eq, data_eq, reloc_eq, nwd, pcid, len(holders),
                    ';'.join(hnames[:4]), ours))
        summ[(pk, t)][('size' + size_eq, 'data' + data_eq, 'reloc' + reloc_eq, ours)] += 1
    with open(os.path.join(out, 'q112_detail.tsv'), 'w', encoding='utf-8') as fo:
        fo.write('type\txbox_id\tpack\tdrm\tsize\tbase_holder\tsize_eq\tdata_eq\treloc_eq\twords_diff\tpc_id\tpc_holders\t'
                 'pc_holder_names\tours\n')
        for x in res: fo.write('\t'.join(str(v) for v in x) + '\n')
    for k in sorted(summ):
        print(k, dict(summ[k]))


if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    main(*sys.argv[1:4])
