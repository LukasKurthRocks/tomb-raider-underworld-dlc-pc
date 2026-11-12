"""Read-only: does a PC DRM file hold section (TYPE, ID)? Prints size and md5 per file.
Usage (from trudlcport): ../bin/pyt -t 300 work/j_data_1211/drm_has_section.py TYPE ID FILE.drm [FILE.drm ...]
"""
import sys, os, hashlib
sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
import drm_write as DW

t, i = int(sys.argv[1]), int(sys.argv[2])
for f in sys.argv[3:]:
    d = DW.read(open(f, 'rb').read(), 'le')
    hit = [s for s in d.sections if s.type == t and s.id == i]
    print('%s: %s' % (f, ', '.join('%d B md5 %s' % (len(s.data or b''), hashlib.md5(s.data or b'').hexdigest()[:8]) for s in hit) or 'absent'))
