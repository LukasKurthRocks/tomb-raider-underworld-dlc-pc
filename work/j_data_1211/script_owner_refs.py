"""Group J (B follow-up), read-only: which sections of the given PC unit DRMs point at script section (8, SID)
through a resource id reference (relocation kinds A / 4) or hold it as an external relocation target - to find the
owner of a level / class script that no intro owns (+0x7c).

Usage (from trudlcport): ../bin/pyt -t 600 work/j_data_1211/script_owner_refs.py SID UNIT.drm [UNIT.drm ...]
Prints per DRM: section (type, id, size), offset of the reference, and for type-7 sections the u32 words around it.
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
import drm_reloc as R
import drm_write as DW


def main(sid, files):
    for f in files:
        d = DW.read(open(f, 'rb').read(), 'le')
        hits = []
        for k, s in enumerate(d.sections):
            r = R.parse(s.reloc, 'le')
            for kind, lst in (('idref', r.idref), ('idref_a', r.idref_a)):
                for t, off in lst:
                    if t == 8 and off + 4 <= len(s.data) and struct.unpack_from('<I', s.data, off)[0] == sid:
                        hits.append((s.type, s.id, len(s.data), kind, off))
            for si, so, do in r.external:
                tgt = d.sections[si]
                if tgt.type == 8 and tgt.id == sid:
                    hits.append((s.type, s.id, len(s.data), 'external->+0x%x' % do, so))
        print('== %s: %d references to (8, %d)' % (os.path.basename(f), len(hits), sid))
        for t, i, n, kind, off in hits:
            print('   section (%d, %d) %d B  %s at +0x%x' % (t, i, n, kind, off))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(int(sys.argv[1]), sys.argv[2:])
