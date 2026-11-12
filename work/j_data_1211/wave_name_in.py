"""Read-only: FSB sample name of wave section (6, ID) in PC DRM files (tools/audio_parse.parse_pc).
Usage (from trudlcport): ../bin/pyt -t 300 work/j_data_1211/wave_name_in.py ID FILE.drm [FILE.drm ...]
"""
import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
import drm_write as DW
import audio_parse as A

wid = int(sys.argv[1])
for f in sys.argv[2:]:
    d = DW.read(open(f, 'rb').read(), 'le')
    for s in d.sections:
        if s.type == 6 and s.id == wid:
            try: nm = A.parse_pc(s.data)['name'].decode('latin-1')
            except Exception as e: nm = 'parse error %r' % e
            print('%s: 6:%d %d B name %s' % (os.path.basename(f), wid, len(s.data), nm))
