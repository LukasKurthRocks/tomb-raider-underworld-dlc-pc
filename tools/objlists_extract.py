"""Extract objectlist.txt / unitlist.txt / objlist.dat of every platform version into work/generic/lists/
(missing glue, reconstructed: tools/objlists.py loads <prefix>_<file> from there, no script writes them).

Prefixes and sources (the first archive that has the file wins = runtime authoritative):
  pc          ../data/pc/patch.000, ../data/pc/bigfile.000             \\tr8\\pc-w\\<file>
  xbox        layer1.000, layer2.000                                    \\tr8\\xenon-w\\<file>
  xboxtu      TitleUpdate.000
  dlc_pack10  pack10.000 (Beneath the Ashes)
  dlc_pack11  pack11.000 (Lara's Shadow)
  dlc_pack1   pack1.000  (costume pack)
Several records of one name (specMask variants) must have identical content.

Usage (from the repository root):  ..\\bin\\venv\\Scripts\\python.exe -I tools/objlists_extract.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc

X = '../data/TombRaiderUnderworld_Patched/'
C = '../data/Xenia-SteveRepack/Content/534307EC/00000002/'
SOURCES = {
    'pc':         ([('../data/pc/patch.000', 'le'), ('../data/pc/bigfile.000', 'le')], '\\tr8\\pc-w\\'),
    'xbox':       ([(X + 'layer1.000', 'be'), (X + 'layer2.000', 'be')], '\\tr8\\xenon-w\\'),
    'xboxtu':     ([(X + 'TitleUpdate.000', 'be')], '\\tr8\\xenon-w\\'),
    'dlc_pack10': ([(C + '9CA70CF0EDA43654D158C2E37470D301DFA850E753/pack10.000', 'be')], '\\tr8\\xenon-w\\'),
    'dlc_pack11': ([(C + '600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153/pack11.000', 'be')], '\\tr8\\xenon-w\\'),
    'dlc_pack1':  ([(C + 'E5AFB2B959A72C52120D73678AED11BD8752686753/pack1.000', 'be')], '\\tr8\\xenon-w\\'),
}
FILES = ('objectlist.txt', 'unitlist.txt', 'objlist.dat')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic', 'lists')


def main():
    os.makedirs(OUT, exist_ok=True)
    missing = []
    for prefix, (archives, folder) in SOURCES.items():
        opened = [(path, Archive(path, e)) for path, e in archives]
        for fn in FILES:
            h = crc(folder + fn)
            for path, a in opened:
                recs = a.find(h)
                if not recs: continue
                datas = {a.read(r) for r in recs}
                assert len(datas) == 1, '%s %s: %d different contents in %s' % (prefix, fn, len(datas), path)
                data = datas.pop()
                open(os.path.join(OUT, '%s_%s' % (prefix, fn)), 'wb').write(data)
                print('%-11s %-15s %8d bytes from %s (%d records)' % (prefix, fn, len(data), os.path.basename(path), len(recs)))
                break
            else:
                missing.append('%s_%s' % (prefix, fn))
                print('%-11s %-15s MISSING' % (prefix, fn))
    if missing:
        sys.exit('missing: ' + ', '.join(missing))


if __name__ == '__main__':
    main()
