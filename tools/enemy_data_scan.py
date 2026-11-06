"""Enemy object data records per object: behaviour tree type and the first header words (read-only; 2026-11-06 enemy
senses - can one hook make enemies ignore Lara, and do all enemy kinds share the same perception code?
docs Befund-Gegner-Wahrnehmung-0611.md).

Engine facts this tool relies on (tru.exe Steam, md5 5560abacbc6968cdc17871c3ec8ca21c, static):
  * the enemy init 0x63c190 reads the instance data block `[inst+0x50]`; it builds the enemy brain (0x5040 bytes,
    stored at `[[inst+0x2d0]]+0x2ec`) only when the block starts with the magic u32 0xdaf00018 and byte +0x18 > 0;
  * the behaviour tree is chosen by the signed byte +0x0c: 1 = EnemyBehaviorTree_Creature, 2 =
    EnemyBehaviorTree_CreatureVolumetric, 3 = EnemyBehaviorTree_Thrall, anything else = EnemyBehaviorTree_Soldier
    (code 0x63c2e2..0x63c31c, tree objects 0x8acf90 / 98 / a0 / a8);
  * the senses (EnemySensesControl at brain+0x170) are initialised for every such brain (0x63c277 -> 0x64bd20).
This tool finds every aligned u32 0xdaf00018 in the sections of an object DRM (PC = little endian) and prints the
record's tree byte, byte +0x18 and the first header words. That the found record is the one `[inst+0x50]` points at
is an assumption (one hit per object is the expected case; more hits are all printed).

Sources: object names (default: every name of the merged PC object list work/generic/merged/tr8/pc-w/objectlist.txt
matching --grep) are read from the PC archives (pcpatch first, then pcbig) without writing anything; DLC objects that
exist only in converted trees are read from DRM files / folders given with --dir.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/enemy_data_scan.py [--grep REGEX] [--dir PATH ...] [--all]
  ../bin/pyt -t 300 tools/enemy_data_scan.py --src SOURCE NAME [NAME ...]     one archive of tools/locals.py, e.g.
                                                                              pack11 natla_thrall (Xbox: big endian)
     --grep  object name filter (Python re, case-insensitive; default: every object of the list)
     --dir   also scan *.drm in these folders (recursively) - converted DLC trees, e.g. work/rebuild/asm_stage2a/mods
     --all   also print objects without an enemy record (default: only objects with one)
  tree / +0x18 are the bytes at +0x0c / +0x18 (byte fields: the same offset in Xbox and PC files).
"""
import sys, os, re, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC
import drm_write as DW
from archive import Archive
from names import crc
from drm import cdrm_decode

MAGIC = 0xdaf00018
TREES = {1: 'Creature', 2: 'CreatureVolumetric', 3: 'Thrall'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBJLIST = os.path.join(ROOT, 'work', 'generic', 'merged', 'tr8', 'pc-w', 'objectlist.txt')


def objnames(path=OBJLIST):
    out = []
    for line in open(path, encoding='utf-8', errors='replace').read().splitlines()[1:]:
        if ',' in line:
            i, n = line.split(',', 1)
            out.append((int(i), n.strip()))
    return out


def records(raw, e='le'):
    D = DW.read(raw, e)
    f = '<' if e == 'le' else '>'
    hits = []
    for si, s in enumerate(D.sections):
        d = bytes(s.data)
        for o in range(0, len(d) - 0x40, 4):
            if struct.unpack_from(f + 'I', d, o)[0] != MAGIC: continue
            w = struct.unpack_from(f + '16I', d, o)
            # byte fields (same byte offset on Xbox and PC: the converter swaps the u16 / u32 fields around them)
            tree = struct.unpack_from('b', d, o + 0x0c)[0]
            b18 = d[o + 0x18]
            hits.append((s.type, s.id, o, tree, b18, w))
    return hits


def show(label, hits, show_all):
    if not hits:
        if show_all: print('%-44s no enemy record' % label)
        return 0
    for typ, sid, o, tree, b18, w in hits:
        print('%-44s sec type %2d id %6d +0x%05x  tree %d %-18s +0x18=%3d  words %s' % (
            label, typ, sid, o, tree, TREES.get(tree, 'Soldier'), b18, ' '.join('%08x' % x for x in w[1:10])))
    return 1


def main(argv):
    grep = None; dirs = []; show_all = '--all' in argv
    argv = [a for a in argv if a != '--all']
    if '--grep' in argv: k = argv.index('--grep'); grep = re.compile(argv[k + 1], re.I); del argv[k:k + 2]
    while '--dir' in argv: k = argv.index('--dir'); dirs.append(argv[k + 1]); del argv[k:k + 2]
    if '--src' in argv:
        # names from another tools/locals.py archive (e.g. pack11 = Xbox DLC 2, big endian), no object list needed
        k = argv.index('--src'); src = argv[k + 1]; names = argv[k + 2:]
        path, e, pre = LC.SRC[src]
        A = Archive(path, e)
        for name in names:
            recs = A.find(crc(pre + '\\' + name + '.drm'))
            if not recs: print('%-44s not in %s' % (name, src)); continue
            show('%s [%s, %s endian]' % (name, src, e), records(cdrm_decode(A.read(recs[-1]), e), e), True)
        return
    arch = []
    for src in ('pcpatch', 'pcbig'):
        path, e, pre = LC.SRC[src]
        arch.append((src, Archive(path, e), e, pre))
    n_obj = n_enemy = 0
    for oid, name in objnames():
        if grep and not grep.search(name): continue
        raw = None
        for src, A, e, pre in arch:
            recs = A.find(crc(pre + '\\' + name + '.drm'))
            if recs:
                raw = cdrm_decode(A.read(recs[-1]), e); where = src; break
        if raw is None:
            if show_all: print('%-44s not in pcpatch / pcbig' % ('%d %s' % (oid, name)))
            continue
        n_obj += 1
        try:
            n_enemy += show('%d %s [%s]' % (oid, name, where), records(raw), show_all)
        except Exception as ex:
            print('%d %s [%s] parse error %s' % (oid, name, where, ex))
    for d in dirs:
        for base, _, files in os.walk(d):
            for f in sorted(files):
                if not f.lower().endswith('.drm'): continue
                if grep and not grep.search(f): continue
                n_obj += 1
                p = os.path.join(base, f)
                try:
                    n_enemy += show(os.path.relpath(p, d), records(open(p, 'rb').read()), show_all)
                except Exception as ex:
                    print('%s parse error %s' % (p, ex))
    print('%d objects read, %d with an enemy record (magic 0x%08x)' % (n_obj, n_enemy, MAGIC))


if __name__ == '__main__':
    main(sys.argv[1:])
