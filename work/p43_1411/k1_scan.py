r"""P4.4 K-1 (14.11.): fpkeys at the old threshold (100) and the new one (TF.FP_MIN, 20) on a tree - which words the
new threshold adds, and what the kits B270 / B138 have there (same file, same section id / size, same offset).
Classes per new word: kit = want (the kit had it right: K-1 'a' closed), kit = ours before (kit and we were the same;
the word now differs from the kit), other.
Usage: ../bin/pyt -t 3600 work/p43_1411/k1_scan.py TREE OUT.tsv"""
import sys, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import typed_family_fix as TF, drm_write as DW, dtp_audit as DA
from convert_dlc import raw_dlc
from drm import cdrm_decode

KITS = {'B270': os.path.join(ROOT, 'work', 'b270_kit', 'mods'),
        'B138': os.path.join(ROOT, 'work', 'rebuild', 'pipeline_check_1011_repair', 'b138_pristine', 'mods')}


def kit_secs(kdir, rel):
    p = os.path.join(kdir, rel.replace('/', os.sep))
    if not os.path.isfile(p):
        p = os.path.join(kdir, os.path.basename(rel))
        if not os.path.isfile(p): return None
    D = DW.read(cdrm_decode(open(p, 'rb').read(), 'le'), 'le')
    out = {}
    for s in D.sections:
        out.setdefault((s.type, s.id), bytes(s.data))
    return out


def main(a):
    tree, outp = a[0], a[1]
    new_min = int(os.environ.get('K1_MIN', '20')); TF.FP_MIN = new_min
    rows = []; cnt = collections.Counter(); per_dtp = collections.Counter()
    for rel, path in sorted(DA.overlay([os.path.abspath(tree)], None).items()):
        xr, src = raw_dlc(rel.replace('/', '\\'))
        if xr is None: xr, src = raw_dlc(os.path.basename(rel))
        if xr is None: continue
        pack = os.path.basename(src.replace('\\', '/')).split('.')[0]
        XD = DW.read(cdrm_decode(xr, 'be'), 'be'); PD = DW.read(cdrm_decode(open(path, 'rb').read(), 'le'), 'le')
        got = {}
        for lab, th in (('old', 100), ('new', new_min)):
            TF.FP_MIN = th
            info = TF.plan('fpkeys', XD, PD, rel, pack)
            got[lab] = {(PD.sections[k].id, o): (pw, want) for k, o, xw, pw, want, tag in info['rows']}
        TF.FP_MIN = new_min
        cnt['old_words'] += len(got['old'])
        extra = {k: v for k, v in got['new'].items() if k not in got['old']}
        if not extra: continue
        kits = {n: kit_secs(d, rel) for n, d in KITS.items()}
        for (sid, o), (pw, want) in sorted(extra.items()):
            cnt['new_words'] += 1; per_dtp[(rel, sid)] += 1
            r = [rel, str(sid), '%#x' % o, pw.hex(), want.hex()]
            for n in KITS:
                ks = kits[n]
                kw = None if ks is None or (7, sid) not in ks or o + 4 > len(ks[(7, sid)]) else ks[(7, sid)][o:o + 4]
                c = 'nofile' if ks is None else 'nosec' if kw is None else 'kit=want' if kw == want else 'kit=old' if kw == pw else 'other'
                cnt['%s %s' % (n, c)] += 1; r += [kw.hex() if kw else '-', c]
            rows.append(r)
    with open(outp, 'w', encoding='utf-8', newline='\n') as f:
        f.write('rel\tdtp\toff\tours_before\twant\tb270\tb270_class\tb138\tb138_class\n')
        for r in rows: f.write('\t'.join(r) + '\n')
    print('fpkeys threshold 100 -> %d: %s' % (new_min, dict(sorted(cnt.items()))))
    print('DTPs with new words: %d; largest: %s' % (len(per_dtp), per_dtp.most_common(12)))


if __name__ == '__main__':
    main(sys.argv[1:])
