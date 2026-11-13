"""Build a test candidate (NOT installed): the own-tree dlc_level1_start.drm with only the CINE_SKIP relocation of
script 20068 undone - the op 0x6a call at +0x6c0 points again at Cinematic_Object 3523 Prototype +0x2410
(vtIndex 57 PlayCinematic, Xbox form 941 +0x2410) instead of 23175 Prototype +0x5f8 (vtIndex 61, warp handler).
Everything else stays byte-identical (uid 29392 kept), so a live test isolates the call.

Usage (from trudlcport): ../bin/pyt -t 300 work/dlc1warp_1311/make_nocineskip.py OWN.drm OUT.drm
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW, drm_reloc as R


def main(argv):
    src, dst = argv[0], argv[1]
    if os.path.abspath(src) == os.path.abspath(dst):
        sys.exit('refusing to overwrite the source')
    raw = open(src, 'rb').read()
    D = DW.read(raw, 'le')
    S = D.sections
    k = next(i for i, q in enumerate(S) if q.type == 8 and q.id == 20068)
    j3523 = next(i for i, q in enumerate(S) if q.type == 8 and q.id == 3523)
    r = R.parse(S[k].reloc, 'le')
    hit = [(si, so, do) for si, so, do in r.external if so == 0x6c4]
    if len(hit) != 1 or (S[hit[0][0]].id, hit[0][2]) != (23175, 0x5f8):
        sys.exit('not the CINE_SKIP form: %r' % (hit,))
    if S[k].data[0x6c0:0x6c4] != bytes.fromhex('0000006a'):
        sys.exit('no op 0x6a at +0x6c0')
    p = S[j3523].data
    if p[0x2410:0x2414] != (3523).to_bytes(4, 'little') or p[0x2416:0x2418] != (57).to_bytes(2, 'little'):
        sys.exit('3523 +0x2410 is not the vtIndex-57 prototype')
    r.external = [(j3523, so, 0x2410) if so == 0x6c4 else (si, so, do) for si, so, do in r.external]
    S[k].reloc = R.write(r, 'le')
    data = D.write('le')
    if raw[:4] == b'CDRM':
        data = DW.cdrm_encode(data, 'le')
    open(dst, 'wb').write(data)
    print('written', dst, len(data), 'bytes; 20068 +0x6c4 -> (8,3523)+0x2410 (section index %d)' % j3523)


if __name__ == '__main__':
    main(sys.argv[1:])
