"""Read-only proof for a diagnostic / recolour tree built on known base files (test 51j / 51k, 2026-11-04): per file of
TREE/bases.tsv (file, base folder or '(game mods)', base md5, new md5, change spec) the base and the tree file are
decoded and compared INDEPENDENTLY of the build tool:

  * md5 of base / tree file == bases.tsv
  * sections paired by (type, id): headers + relocations of every shared section identical, sections only in the
    tree file listed (must be type 5 textures with a PCD9 header), no section missing
  * every differing byte of a shared section listed (section, offset in the section, offset in the decoded tree DRM,
    old / new); grouped to 32-bit words; a word is "expected" when it is a texture-id word of a texture record
    (+0x54 block, 16 bytes per record) or a PS MaterialParams lane (+0x5C block) of a material named in the spec
  * when base and tree decode to the same length, a plain decoded byte diff is done as well (count must equal)
  * the changed materials still parse: every texture id they reference is in the tree file or was referenced before

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/diag_tree_byte_diff.py TREE_DIR --game GAME_MODS_DIR [--out TSV]
Last line: "files N, ok K, unexpected words U, missing sections M".
"""
import sys, os, struct, hashlib, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def offsets(D):
    """data start offset of every section in the decoded DRM (the layout drm_write.write produces)"""
    p = 24 + 20 * len(D.sections) + len(D.names) + len(D.pad); out = []
    for s in D.sections:
        p += len(s.reloc); out.append(p); p += len(s.data)
    return out


def expected_words(s):
    """{offset: kind} of texture-record id words and PS MaterialParams lanes of a material section"""
    ip = dict(R.parse(s.reloc, 'le').internal); out = {}
    if 0x54 in ip:
        n = max(s.data[0x4F], s.data[0x52])
        for k in range(n): out[ip[0x54] + 16 * k] = 'texture record %d id' % k
    if 0x5C in ip:
        n = struct.unpack_from('<I', s.data, 0x58)[0]
        for k in range(n):
            for lane in range(4): out[ip[0x5C] + 16 * k + 4 * lane] = 'PS MP[%d].%s' % (k, 'xyzw'[lane])
    return out


def main(argv):
    tree = argv[0]; game = argv[argv.index('--game') + 1]
    outp = argv[argv.index('--out') + 1] if '--out' in argv else None
    repo = os.getcwd()
    rows = [l.rstrip('\r\n').split('\t') for l in open(os.path.join(tree, 'bases.tsv'), encoding='utf-8')][1:]
    nfiles = nok = unexp = missing = 0; tsv = ['file\tsection\toffset_in_section\toffset_in_decoded_drm\told\tnew\tkind']
    for f, base, bmd5, nmd5, spec in rows:
        nfiles += 1
        bp = os.path.join(game, f) if base.startswith('(game') else os.path.join(repo, base, f)
        tp = os.path.join(tree, 'mods', f)
        rb, rt = open(bp, 'rb').read(), open(tp, 'rb').read()
        m1, m2 = hashlib.md5(rb).hexdigest(), hashlib.md5(rt).hexdigest()
        bad = 0
        if m1 != bmd5 or m2 != nmd5: print('%s: md5 mismatch base %s / %s tree %s / %s' % (f, m1, bmd5, m2, nmd5)); bad += 1
        mats = {int(x.split(':')[1]) for x in spec.split()}
        A, B = DW.read(rb, 'le'), DW.read(rt, 'le')
        oB = offsets(B)
        ka = {(s.type, s.id): s for s in A.sections}; kb = {(s.type, s.id): (i, s) for i, s in enumerate(B.sections)}
        if len(ka) != len(A.sections) or len(kb) != len(B.sections): print('%s: duplicate (type, id) - paired by first' % f)
        miss = [k for k in ka if k not in kb]; missing += len(miss)
        if miss: print('%s: MISSING sections %s' % (f, miss)); bad += 1
        added = [k for k in kb if k not in ka]
        for k in added:
            s = kb[k][1]
            ok = k[0] == 5 and s.data[:4] == b'PCD9'
            w, h, mips = struct.unpack_from('<HHxB', s.data, 0x10) if ok else (0, 0, 0)
            print('%s: added section %d:%d %d bytes %s' % (f, k[0], k[1], len(s.data),
                  'PCD9 %dx%d mips %d first block %s' % (w, h, mips, s.data[24:32].hex()) if ok else 'NOT A PC TEXTURE'))
            if not ok: bad += 1
        nbytes = 0
        for k, a in ka.items():
            if k not in kb: continue
            i, b = kb[k]
            if (a.flags, a.ver, a.spec, a.pad, a.reloc, len(a.data)) != (b.flags, b.ver, b.spec, b.pad, b.reloc, len(b.data)):
                print('%s: section %d:%d header / relocations / size differ' % (f, k[0], k[1])); bad += 1; continue
            if a.data == b.data: continue
            exp = expected_words(b) if k[0] == 10 and k[1] in mats else {}
            words = sorted({o - o % 4 for o in range(len(a.data)) if a.data[o] != b.data[o]})
            for wo in words:
                old, new = a.data[wo:wo + 4], b.data[wo:wo + 4]
                nbytes += sum(1 for q in range(4) if old[q] != new[q])
                kind = exp.get(wo)
                if kind is None: unexp += 1; bad += 1; kind = 'UNEXPECTED'
                print('%s: %d:%d +%#x (decoded %#x) %s -> %s  %s' % (f, k[0], k[1], wo, oB[i] + wo, old.hex(), new.hex(), kind))
                tsv.append('%s\t%d:%d\t%#x\t%#x\t%s\t%s\t%s' % (f, k[0], k[1], wo, oB[i] + wo, old.hex(), new.hex(), kind))
            # the changed material still parses: its texture ids exist in the tree file (or did before)
            ids_b = {s.id for s in B.sections if s.type == 5}; ids_a = {s.id for s in A.sections if s.type == 5}
            for t, o in R.parse(b.reloc, 'le').idref:
                if t != 5: continue
                v = struct.unpack_from('<I', b.data, o)[0]; ov = struct.unpack_from('<I', a.data, o)[0]
                if v not in ids_b and not (v == ov and v not in ids_a):
                    print('%s: material %d texture %d at +%#x not in the file' % (f, k[1], v, o)); bad += 1
        da, db = DW.cdrm_decode(rb, 'le'), DW.cdrm_decode(rt, 'le')
        if len(da) == len(db):
            import numpy as np
            nd = int(np.count_nonzero(np.frombuffer(da, np.uint8) != np.frombuffer(db, np.uint8)))
            print('%s: same decoded length %d, plain byte diff %d bytes (section diff %d)' % (f, len(da), nd, nbytes))
            if nd != nbytes: bad += 1
        print('%s: %s (%d changed bytes, %d added sections)' % (f, 'OK' if not bad else 'PROBLEMS %d' % bad, nbytes, len(added)))
        nok += not bad
    if outp:
        open(outp, 'w', encoding='utf-8', newline='\n').write('\n'.join(tsv) + '\n')
    print('files %d, ok %d, unexpected words %d, missing sections %d' % (nfiles, nok, unexp, missing))


if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    main(sys.argv[1:])
