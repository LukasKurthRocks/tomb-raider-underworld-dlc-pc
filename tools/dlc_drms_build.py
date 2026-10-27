"""Build work/generic/dlc_drms.pkl: every DRM of the DLC packs, decoded (missing glue, reconstructed).

The converters read this cache (dlc_generic.DlcIds, dlc_convert_all, param_auto) but no script in the repository
writes it. Format, as the readers use it:
  {(pack, name, spec): (header, sections)}   sections = drm.sections_with_data(raw, 'be')
  pack = last 9 characters of the archive path ('ack10.000' / 'ack11.000', as tools/param_auto.py filters it),
  name = file name from the Yura Xenon file list (or '0x%08x' hash when unknown), spec = specMask of the record.
Packs: pack10 (Beneath the Ashes) and pack11 (Lara's Shadow) - the two that dlc_convert_all converts. The costume
packs (pack1/pack2) are added to the id table later by tools/verify_ids.py extend.

Usage (from the repository root):  ..\\bin\\venv\\Scripts\\python.exe -I tools/dlc_drms_build.py
"""
import sys, os, pickle, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import load, L
from drm import cdrm_decode, sections_with_data

C = '../data/Xenia-SteveRepack/Content/534307EC/00000002/'
PACKS = [C + '9CA70CF0EDA43654D158C2E37470D301DFA850E753/pack10.000',
         C + '600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153/pack11.000']
W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic')


def main():
    xn = load(L + 'Tomb Raider Underworld (Xenon).txt')
    out, st = {}, collections.Counter()
    for path in PACKS:
        A = Archive(path, 'be')
        for r in A.idx:
            f = A.read(r)
            if f[:4] != b'CDRM' and f[:4] != b'\0\0\0\x13':
                st[path[-9:], 'not_drm'] += 1
                continue
            name = xn.get(r['hash'], '0x%08x' % r['hash'])
            key = (path[-9:], name, r['spec'])
            assert key not in out, key
            out[key] = sections_with_data(cdrm_decode(f, 'be'), 'be')
            st[path[-9:], 'drm'] += 1
            st[path[-9:], 'named' if r['hash'] in xn else 'unnamed'] += 1
    os.makedirs(W, exist_ok=True)
    pickle.dump(out, open(os.path.join(W, 'dlc_drms.pkl'), 'wb'))
    for k, v in sorted(st.items()): print(k, v)
    print('wrote dlc_drms.pkl with', len(out), 'DRMs')


if __name__ == '__main__':
    main()
