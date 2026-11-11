"""Extract objectlist.txt / unitlist.txt / objlist.dat of every platform version into work/generic/lists/
(missing glue, reconstructed: tools/objlists.py loads <prefix>_<file> from there, no script writes them).

Prefixes and sources (the first archive that has the file wins = runtime authoritative):
  pc          ../data/pc/patch.000, ../data/pc/bigfile.000             \\tr8\\pc-w\\<file>
  xbox        layer1.000, layer2.000                                    \\tr8\\xenon-w\\<file>   (developer only)
  xboxtu      the title-update lists, read from pack11.000 (plan Spielerweg P1, 2026-11-11): the three
              TitleUpdate.000 records are byte-identical to pack11's (work/playerpath_1011/tu_vs_dlc.tsv: objectlist
              28 009 B c76f8fd1..., unitlist 3 533 B 2203e9bd..., objlist.dat 29 222 B 7b4ab79a...), so the player
              path needs no title update for them; --check-tu compares the pack11 copy with TitleUpdate.000
  dlc_pack10  pack10.000 (Beneath the Ashes)
  dlc_pack11  pack11.000 (Lara's Shadow)
  dlc_pack1   pack1.000  (costume pack Wetsuit)
  dlc_pack2   pack2.000  (costume pack Classic)
  dlc_pack20  pack20.000 (costume pack Designer)
Several records of one name (specMask variants) must have identical content.

Player mode (TRU_PLAYER_MODE report / enforce, tools/player_guard.py): the prefix "xbox" (Xbox base game layer1 /
layer2) is skipped - its lists are developer-only (consumers: unit_ids, the Fixes scans / proofs that compare with the
Xbox base, plan P5 / P9); an existing xbox_* file in the output folder is left as it is.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/objlists_extract.py [--out DIR] [--only PREFIX,...]
  ../bin/pyt -t 300 tools/objlists_extract.py --check-tu
  --out DIR       write <prefix>_<file> to DIR (default work/generic/lists)
  --only P,...    only these prefixes
  --check-tu      developer check (reads TitleUpdate.000, writes nothing): the xboxtu lists from pack11 = the title
                  update's records byte for byte, exit 1 on a difference
"""
import sys, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc

X = '../data/TombRaiderUnderworld_Patched/'
C = '../data/Xenia-SteveRepack/Content/534307EC/00000002/'
PACK11 = C + '600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153/pack11.000'
TU = X + 'TitleUpdate.000'
XFOLDER = '\\tr8\\xenon-w\\'
SOURCES = {
    'pc':         ([('../data/pc/patch.000', 'le'), ('../data/pc/bigfile.000', 'le')], '\\tr8\\pc-w\\'),
    'xbox':       ([(X + 'layer1.000', 'be'), (X + 'layer2.000', 'be')], XFOLDER),
    'xboxtu':     ([(PACK11, 'be')], XFOLDER),
    'dlc_pack10': ([(C + '9CA70CF0EDA43654D158C2E37470D301DFA850E753/pack10.000', 'be')], XFOLDER),
    'dlc_pack11': ([(PACK11, 'be')], XFOLDER),
    'dlc_pack1':  ([(C + 'E5AFB2B959A72C52120D73678AED11BD8752686753/pack1.000', 'be')], XFOLDER),
    'dlc_pack2':  ([(C + '9FDDD06617D1016DE468ACF53AC663E8BA2AD41853/pack2.000', 'be')], XFOLDER),
    'dlc_pack20': ([(C + 'AC0089F81B621CD0E0C156B6176EFCC6C844705D53/pack20.000', 'be')], XFOLDER),
}
DEVELOPER_ONLY = ('xbox',)          # Xbox base game: skipped in player mode
FILES = ('objectlist.txt', 'unitlist.txt', 'objlist.dat')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic', 'lists')


def player_mode():
    """the guard mode of this process ('off' / 'report' / 'enforce'; player_guard only reads the variable here)"""
    import player_guard
    return player_guard.mode_from_env()


def read_one(a, path, folder, fn, prefix):
    """(bytes, record count) of folder + fn in archive a, None when absent; all records must be equal"""
    recs = a.find(crc(folder + fn))
    if not recs: return None
    datas = {a.read(r) for r in recs}
    assert len(datas) == 1, '%s %s: %d different contents in %s' % (prefix, fn, len(datas), path)
    return datas.pop(), len(recs)


def check_tu():
    """developer: the xboxtu lists read from pack11 = the TitleUpdate.000 records (byte for byte)"""
    tu, pk, bad = Archive(TU, 'be'), Archive(PACK11, 'be'), 0
    for fn in FILES:
        a, b = read_one(tu, TU, XFOLDER, fn, 'tu'), read_one(pk, PACK11, XFOLDER, fn, 'pack11')
        ok = a is not None and b is not None and a[0] == b[0]
        bad += not ok
        print('check-tu %-15s TU %s pack11 %s %s' % (fn, hashlib.md5(a[0]).hexdigest() if a else 'MISSING',
                                                   hashlib.md5(b[0]).hexdigest() if b else 'MISSING',
                                                   'equal' if ok else 'DIFFERENT'))
    return bad == 0


def main(argv):
    out, only = OUT, None
    if '--out' in argv: k = argv.index('--out'); out = argv[k + 1]; del argv[k:k + 2]
    if '--only' in argv: k = argv.index('--only'); only = argv[k + 1].split(','); del argv[k:k + 2]
    if argv == ['--check-tu']: sys.exit(0 if check_tu() else 1)
    if argv: sys.exit(__doc__)
    if only and set(only) - set(SOURCES): sys.exit('unknown prefix: %s' % ', '.join(sorted(set(only) - set(SOURCES))))
    mode = player_mode()
    os.makedirs(out, exist_ok=True)
    missing = []
    for prefix, (archives, folder) in SOURCES.items():
        if only and prefix not in only: continue
        if mode != 'off' and prefix in DEVELOPER_ONLY:
            print('%-11s skipped (player mode %s: Xbox base game, developer only)' % (prefix, mode))
            continue
        opened = [(path, Archive(path, e)) for path, e in archives]
        for fn in FILES:
            for path, a in opened:
                got = read_one(a, path, folder, fn, prefix)
                if got is None: continue
                data, n = got
                open(os.path.join(out, '%s_%s' % (prefix, fn)), 'wb').write(data)
                print('%-11s %-15s %8d bytes from %s (%d records) md5 %s' % (
                    prefix, fn, len(data), os.path.basename(path), n, hashlib.md5(data).hexdigest()))
                break
            else:
                missing.append('%s_%s' % (prefix, fn))
                print('%-11s %-15s MISSING' % (prefix, fn))
    if missing:
        sys.exit('missing: ' + ', '.join(missing))


if __name__ == '__main__':
    main(sys.argv[1:])
