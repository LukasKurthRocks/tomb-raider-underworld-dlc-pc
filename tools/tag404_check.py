"""Check the raft/grapple ring records (DTP record tag 0x404) of a rebuilt tree against B138 (B33 fix).

FINDINGS.md: "Physics records for custom-range grapple rings (tag 0x404): the enable byte at +4 must stay raw".
For every 0x404 record in the Xbox DTPs of the DLC DRMs (tag found as BE word, not a pointer/id word) the word at +4
is compared: ours, B138, and the Xbox bytes raw / byte-swapped.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/tag404_check.py [MODS_DIR] [--ref REF_MODS_DIR] [--all]
  --all lists every record, not only the differing ones
  defaults: work/rebuild/stage2b/mods, ../data/pc/mods
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtp_audit as DA, drm_write as DW, drm_reloc as R

TAG = struct.pack('>I', 0x404)


def main(argv):
    ref = '../data/pc/mods'
    if '--ref' in argv:
        k = argv.index('--ref'); ref = argv[k + 1]; del argv[k:k + 2]
    show_all = '--all' in argv; argv = [a for a in argv if a != '--all']
    mods = argv[0] if argv else 'work/rebuild/stage2b/mods'
    from build_util import require_dir
    require_dir(mods, 'MODS_DIR'); require_dir(ref, 'REF_MODS_DIR')
    st = collections.Counter(); rows = []
    for rel, path in sorted(DA.overlay([os.path.abspath(mods)], None).items()):
        xs = DA.xsecs(rel)
        rp = os.path.join(ref, rel)
        if xs is None or not os.path.exists(rp): continue
        D = DW.read(open(path, 'rb').read(), 'le'); B = DW.read(open(rp, 'rb').read(), 'le')
        bmap = {(s.type, s.id): s for s in B.sections}
        for x, i in DA.section_pairs(xs, D):
            sec = D.sections[i]
            if x['type'] != 7 or len(sec.data) != len(x['data']): continue
            b = bmap.get((7, sec.id))
            xd = x['data']; xr = R.parse(x['reloc'], 'be'); sl = set(xr.pointer_offsets()) | set(xr.id_offsets())
            for o in range(0, len(xd) - 8, 4):
                if xd[o:o + 4] != TAG or o in sl: continue
                w = xd[o + 4:o + 8]; ours = sec.data[o + 4:o + 8]
                b138 = b.data[o + 4:o + 8] if b is not None and len(b.data) == len(sec.data) else None
                st['records'] += 1
                st['ours == B138'] += ours == b138
                st['ours raw'] += ours == w
                st['B138 raw'] += b138 == w
                if ours != b138 or show_all:
                    rows.append('%s DTP %d +%#x xbox %s ours %s B138 %s' % (rel, sec.id, o + 4, w.hex(), ours.hex(),
                                                                         b138.hex() if b138 else '-'))
    print(dict(st))
    for r in rows: print('  ' + ('record:' if show_all else 'differs:'), r)


if __name__ == '__main__':
    main(sys.argv[1:])
