"""Read-only check for the cloth iteration-count fault (finding 43, DLC 2 intro in slow motion): the same detection as
step `cloth` of tools/dlc_fixes_build.py (fix_cloth), without writing (2026-11-05, upstream B270 kit check).

Cloth parameter block of the character-model DTPs (type 7, id >= 20000), Xbox layout {u32, ptr, u32, ptr, f32, f32,
u32 iterations, u32, u32, u32, ...}: candidate word o when the Xbox relocations have pointers at o-20 and o-12, no
pointer / id at o-8 .. o+12, and the four Xbox words at o .. o+12 are small integers (0 < w < 0x100). The PC word is
classified: s32 (right), s16 (two u16 halves swapped in place = the fault, 4 -> 0x00040000 = 262 144 passes), raw
(Xbox bytes) or other. The Xbox source is looked up as in fix_cloth (tools/dtp_audit.xsecs, TRUDLC_PACK_FIRST honoured).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/cloth_count_check.py MODS_DIR [NAME.drm ...]
Exit code 1 when any candidate word is s16-encoded.
"""
import sys, os, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main(argv):
    import dtp_audit as DA, drm_write as DW, drm_reloc as R
    root = argv[0]; names = set(argv[1:]) or None
    st = collections.Counter(); bad = []
    for rel, path in sorted(DA.overlay([os.path.abspath(root)], names).items()):
        xs = DA.xsecs(rel)
        if xs is None: st['no Xbox source'] += 1; continue
        st['files'] += 1
        D = DW.read(open(path, 'rb').read(), 'le')
        for x, i in DA.section_pairs(xs, D):
            sec = D.sections[i]
            if x['type'] != 7 or sec.id < 20000 or len(sec.data) != len(x['data']): continue
            xd = x['data']; xr = R.parse(x['reloc'], 'be'); ptrs = set(xr.pointer_offsets()); sl = ptrs | set(xr.id_offsets())
            pd = sec.data
            for o in range(20, len(xd) - 15, 4):
                if o - 20 not in ptrs or o - 12 not in ptrs or any(k in sl for k in (o - 8, o - 4, o, o + 4, o + 8, o + 12)): continue
                v = [struct.unpack_from('>I', xd, o + d)[0] for d in (0, 4, 8, 12)]
                if not all(0 < w < 0x100 for w in v): continue
                xw = xd[o:o + 4]; pw = pd[o:o + 4]
                if pw == struct.pack('<I', v[0]): k = 's32'
                elif pw == xw[1::-1] + xw[:1:-1]: k = 's16'
                elif pw == xw: k = 'raw'
                else: k = 'other'
                st['candidates ' + k] += 1
                if k != 's32': bad.append('%s DTP %d +%#x: Xbox %s PC %s (%s, iterations %d)' % (rel, sec.id, o, xw.hex(), pw.hex(), k, v[0]))
    print('tree %s: %s' % (root, ', '.join('%s %d' % kv for kv in sorted(st.items()))))
    for b in bad: print('  ' + b)
    sys.exit(1 if st['candidates s16'] else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
