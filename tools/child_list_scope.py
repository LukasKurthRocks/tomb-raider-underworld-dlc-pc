"""Child object id lists of all converted DLC objects vs the Xbox originals (read-only; object 858 investigation).

An object's state-chart DTP (first section id named by the object's type-11 header) holds at +0x48 a pointer to a
0-terminated u16 list of object ids the loader loads together with the object (doppelganger_casual 20212: Xbox
{69, 68, 70, 858, 71}). Base ids (< 822) must be remapped Xbox -> PC by name (tools/objlists.py), DLC ids stay.
This lists every object of a PC tree whose list differs from the remapped Xbox list.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/child_list_scope.py PC_MODS_DIR [--pack ack11.000] [--xlist XOBJECTLIST]
  Xbox originals from work/generic/dlc_drms.pkl (decoded sections; the pointer at +0x48 is taken from the PC file's
  relocation, the list offset is the same on both platforms - checked per object).
"""
import sys, os, pickle, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import objlists as OL

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic')


def plist(D):
    head = next((x for x in D.sections if x.type == 11), None)
    if head is None or len(head.data) < 4:
        return None
    root = struct.unpack_from('<I', head.data, 0)[0]
    s = next((x for x in D.sections if x.type == 7 and x.id == root), None)
    if s is None:
        return None
    it = dict(R.parse(bytes(s.reloc), 'le').internal)
    if 0x48 not in it:
        return root, None, []
    a = it[0x48]; ids = []
    while a + 2 * len(ids) + 2 <= len(s.data):
        v = struct.unpack_from('<H', s.data, a + 2 * len(ids))[0]
        if v == 0:
            break
        ids.append(v)
    return root, a, ids


def main(argv):
    pack = 'ack11.000'
    xlist = os.path.join(W, 'lists', 'dlc_pack11_objectlist.txt')
    if '--pack' in argv:
        k = argv.index('--pack'); pack = argv[k + 1]; del argv[k:k + 2]
    if '--xlist' in argv:
        k = argv.index('--xlist'); xlist = argv[k + 1]; del argv[k:k + 2]
    mods = argv[0]
    po = OL.read_objectlist(open(os.path.join(mods, 'tr8', 'pc-w', 'objectlist.txt'), 'rb').read())
    xo = OL.read_objectlist(open(xlist, 'rb').read())
    byname = {v: k for k, v in po.items()}
    C = pickle.load(open(os.path.join(W, 'dlc_drms.pkl'), 'rb'))
    base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
    xb = {}
    for k, v in C.items():
        if k[0] == pack:
            xb.setdefault(base(k[1]), v[1])
    n = bad = 0
    for fn in sorted(os.listdir(mods)):
        if not fn.lower().endswith('.drm'):
            continue
        nm = fn[:-4].lower()
        if nm not in xb:
            continue
        D = DW.read(open(os.path.join(mods, fn), 'rb').read(), 'le')
        r = plist(D)
        if r is None or r[1] is None:
            continue
        root, a, ids = r
        xs = next((s for s in xb[nm] if s['type'] == 7 and s['id'] == root), None)
        if xs is None:
            print('%s: Xbox DTP %d missing' % (fn, root)); continue
        xd = xs['data']; xids = []
        while a + 2 * len(xids) + 2 <= len(xd):
            v = struct.unpack_from('>H', xd, a + 2 * len(xids))[0]
            if v == 0:
                break
            xids.append(v)
        want = [byname.get(xo.get(i), i) for i in xids]
        n += 1
        if want != ids:
            bad += 1
            print('%s DTP %d +0x%x: Xbox %s | PC %s | want %s' % (fn, root, a, xids, ids, want))
    print('%s: %d objects with a child list, %d differ from the remapped Xbox list' % (pack, n, bad))


if __name__ == '__main__':
    main(sys.argv[1:])
