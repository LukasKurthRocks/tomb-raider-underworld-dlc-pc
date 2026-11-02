"""Read-only: which DRMs contain sections (TYPE, ID): the Xbox DLC index (work/idx_dlc.json, per bigfile), the PC
base index (work/idx_pc.json, --pc) or every DRM of a mods folder (--mods DIR; for materials also the shader tuple
+0x28). Test 50a: scope of the doppelganger's TU materials / shader libs in other DLC objects.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/section_where.py TYPE ID[,ID] [--pc] [--mods DIR]
"""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main(a):
    typ = int(a[0]); ids = {int(x) for x in a[1].split(',')}
    mods = a[a.index('--mods') + 1] if '--mods' in a else None
    idx = [] if mods else ['work/idx_dlc.json'] + (['work/idx_pc.json'] if '--pc' in a else [])
    for path in idx:
        if not os.path.exists(path): print('%s missing' % path); continue
        hits = {}
        for entry in json.load(open(path)):
            for sec in entry[5] or []:
                if sec[0] == typ and sec[1] in ids: hits.setdefault(sec[1], []).append(entry[0])
        for i in sorted(ids):
            names = sorted(set(map(str, hits.get(i, []))))
            print('%s: %d:%d in %d entries %s' % (os.path.basename(path), typ, i, len(names), ' '.join(names)))
    if mods:
        import drm_write as DW
        hits = {}
        for root, _ds, fs in os.walk(mods):
            for n in fs:
                if not n.lower().endswith('.drm'): continue
                try: D = DW.read(open(os.path.join(root, n), 'rb').read(), 'le')
                except Exception: continue
                for s in D.sections:
                    if s.type == typ and s.id in ids:
                        extra = ' libs %s' % (struct.unpack_from('<4I', s.data, 0x28),) if typ == 10 else ''
                        hits.setdefault(s.id, []).append(os.path.relpath(os.path.join(root, n), mods) + extra)
        for i in sorted(ids):
            print('%d:%d in %d DRMs: %s' % (typ, i, len(hits.get(i, [])), '; '.join(hits.get(i, []))))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
