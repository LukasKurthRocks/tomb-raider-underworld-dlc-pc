"""P4.8 (2026-11-14): are the sections of a PC tree DRM in the order of its Xbox source (same type, same size per
index)? Read-only. Usage: ../bin/pyt -t 600 work/p48_1411/p48_align_probe.py [--pack pack11] PC_FILE.drm [...]"""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
argv = sys.argv[1:]
if '--pack' in argv:
    i = argv.index('--pack'); os.environ['TRUDLC_PACK_FIRST'] = argv[i + 1]; del argv[i:i + 2]
import convert_dlc as CD, drm_write as DW
for p in argv:
    P = DW.read(open(p, 'rb').read(), 'le')
    raw, pk = CD.raw_dlc(os.path.basename(p))
    if raw is None: print(os.path.basename(p), 'no xbox source'); continue
    X = DW.read(raw, 'be')
    c = collections.Counter()
    for k, s in enumerate(P.sections):
        if k >= len(X.sections): c['extra_pc'] += 1; continue
        x = X.sections[k]
        if x.type != s.type: c['type_differs x%d->p%d' % (x.type, s.type)] += 1
        elif len(x.data) != len(s.data): c['size_differs t%d' % s.type] += 1
        else: c['same t%d' % s.type] += 1
    print('%-36s pc %4d xbox %4d %s' % (os.path.basename(p), len(P.sections), len(X.sections), dict(c)))
