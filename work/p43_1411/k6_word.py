r"""P4.4 K-6 (14.11.): one word of a type-13 section in several PC trees vs the Xbox source (K-6: dlc_watertunnel_map
+0x1e420, Xbox 0x236, converter 0x169) - is it covered by the P4.9 map rule (tools/map_mesh_fix.py)?
Usage: ../bin/pyt -t 600 work/p43_1411/k6_word.py NAME.drm OFFSET TREE[,TREE..]"""
import sys, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm_write as DW
from convert_dlc import raw_dlc
from drm import cdrm_decode


def main(a):
    name, off, trees = a[0], int(a[1], 0), a[2].split(',')
    xr, src = raw_dlc(name)
    XD = DW.read(cdrm_decode(xr, 'be'), 'be')
    xs = [s for s in XD.sections if s.type == 13]
    for s in xs:
        if off + 4 <= len(s.data): print('Xbox %s type 13 id %d (%d B): %s' % (src, s.id, len(s.data), bytes(s.data[off:off + 4]).hex()))
    for t in trees:
        p = None
        for dp, dn, fn in os.walk(t):
            for f in fn:
                if f.lower() == name.lower(): p = os.path.join(dp, f)
        if p is None: print('%s: no file' % t); continue
        D = DW.read(cdrm_decode(open(p, 'rb').read(), 'le'), 'le')
        for s in D.sections:
            if s.type == 13 and off + 4 <= len(s.data): print('%s: type 13 id %d (%d B): %s' % (t, s.id, len(s.data), bytes(s.data[off:off + 4]).hex()))


if __name__ == '__main__':
    main(sys.argv[1:])
