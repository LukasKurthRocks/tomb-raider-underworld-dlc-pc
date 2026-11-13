"""DLC 1 start warp probe (read-only): for each given PC dlc_level1_start.drm print the target of the op 0x6a call in
script 20068 (external relocation at source 0x6c4: Xbox / correct = Cinematic_Object 3523 Prototype +0x2410 vtIndex 57
PlayCinematic; CINE_SKIP = 23175 Prototype +0x5f8 vtIndex 61 = 'warping lara' handler) and the init word +0x894
(the dead-bit uid 29392 vs. the remapped 12241).

Usage (from trudlcport): ../bin/pyt -t 300 work/dlc1warp_1311/cine_call_probe.py A.drm [B.drm ...]
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW, drm_reloc as R


def probe(p):
    D = DW.read(open(p, 'rb').read(), 'le')
    S = D.sections
    s = next((q for q in S if q.type == 8 and q.id == 20068), None)
    if s is None:
        return 'no script 20068'
    r = R.parse(s.reloc, 'le')
    e = [(si, so, do) for si, so, do in r.external if so == 0x6c4]
    tgt = '-'
    if e:
        si, so, do = e[0]
        t = S[si]
        vt = struct.unpack_from('<H', t.data, do + 4)[0] if t.data and do + 8 <= len(t.data) else None
        vt2 = struct.unpack_from('<H', t.data, do + 6)[0] if t.data and do + 8 <= len(t.data) else None
        tgt = '(%d,%d)+0x%x proto halves %s/%s' % (t.type, t.id, do, vt, vt2)
        tgt += '  => ' + ('PlayCinematic (Xbox form)' if (t.id, do) == (3523, 0x2410) else
                          'CINE_SKIP warp handler' if (t.id, do) == (23175, 0x5f8) else 'other')
    w = struct.unpack_from('<I', s.data, 0x894)[0] if len(s.data) >= 0x898 else None
    return '%s | init +0x894 = %s' % (tgt, w)


def main(argv):
    for p in argv:
        try:
            print('%-70s %s' % (p, probe(p)))
        except Exception as ex:      # keep going over a list of trees
            print('%-70s ERROR %s' % (p, ex))


if __name__ == '__main__':
    main(sys.argv[1:])
