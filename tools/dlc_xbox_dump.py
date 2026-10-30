"""Write one decoded Xbox DLC DRM from work/generic/dlc_drms.pkl as a raw big-endian DRM file, so the tools that
take an XBOX.drm path (terrain_batches.py, shader_peer_report.py, drm_sections.py --endian be) can read it.
Read-only towards the cache; the name / padding block is not in the cache and is written as zero bytes of the
original length. Finding 43 follow-up (DLC 2 rock vein).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/dlc_xbox_dump.py NAME OUT.drm [--pack ack11.000]
  NAME = DRM name without .drm (e.g. dlc_level2_start)
"""
import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic')


def main(argv):
    pack = 'ack11.000'
    if '--pack' in argv:
        k = argv.index('--pack'); pack = argv[k + 1]; argv = argv[:k] + argv[k + 2:]
    name, out = argv
    C = pickle.load(open(os.path.join(W, 'dlc_drms.pkl'), 'rb'))
    base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
    hits = [(k, v) for k, v in C.items() if k[0] == pack and base(k[1]) == name.lower()]
    if not hits: raise SystemExit('no %s in %s' % (name, pack))
    h, secs = hits[0][1]
    S = [DW.Section(s['type'], s['id'], s['data'], s['reloc'], s['flags'], s['ver'], s['spec']) for s in secs]
    D = DW.Drm(S, b'\0' * h['namesz'], b'\0' * h['padsz'], h['ver'], h['u0'], h['u1'])
    open(out, 'wb').write(D.write('be'))
    print('wrote %s (%s, %d sections)' % (out, hits[0][0][1], len(S)))


if __name__ == '__main__':
    main(sys.argv[1:])
