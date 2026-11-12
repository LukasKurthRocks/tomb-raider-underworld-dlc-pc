"""Group L 12.11. (read-only): find an ASCII text in the (decompressed) sections of PC DRM files.
Usage (from trudlcport): ../bin/pyt work/l_combat_1211/drm_find_text.py TEXT DRM [DRM ...]"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW

t = sys.argv[1].encode('ascii')
hits = 0
for p in sys.argv[2:]:
    try:
        D = DW.read(open(p, 'rb').read(), 'le')
    except Exception as ex:
        print('%s: unreadable (%s)' % (p, ex))
        continue
    for k, s in enumerate(D.sections):
        o = s.data.find(t)
        while o >= 0:
            hits += 1
            print('%s section %d type %d id %d +0x%x' % (os.path.basename(p), k, s.type, s.id, o))
            o = s.data.find(t, o + 1)
print('# %d hit(s)' % hits)
