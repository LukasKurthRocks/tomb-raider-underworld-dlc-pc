"""P4.8 (2026-11-14): the Xbox-side walker label of the PW.1 marker words (PC userType 4697 is a PC Symbol; the
converter labels the Xbox section). Prints for every Xbox script of the DRM the ('init', 10, ...) labels whose high u16
is one of the given ids, and the userType counts of all ('init', 10) labels. Read-only.
Usage: ../bin/pyt -t 600 work/p48_1411/p48_label_probe.py NAME.drm [id,id,..]"""
import sys, os, struct, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import convert_dlc as CD, drm_write as DW, drm_reloc as R, script_conv as SC
name = sys.argv[1]
want = {int(v) for v in (sys.argv[2] if len(sys.argv) > 2 else '9622,9621,9602,9623').split(',')}
X = DW.read(CD.raw_dlc(name)[0], 'be')
uts = collections.Counter()
for s in X.sections:
    if s.type != 8 or not s.data: continue
    W = SC.walk(bytes(s.data), R.parse(bytes(s.reloc), 'be'))
    for o, lab in W.lab.items():
        if not (isinstance(lab, tuple) and len(lab) >= 5 and lab[0] == 'init' and lab[1] == 10): continue
        uts[lab[4]] += 1
        a = struct.unpack_from('>H', s.data, o)[0]
        if a in want: print('script %d +0x%x %s word %s' % (s.id, o, lab, bytes(s.data[o:o + 4]).hex()))
print('userTypes of (init, 10) labels:', uts.most_common(20))
