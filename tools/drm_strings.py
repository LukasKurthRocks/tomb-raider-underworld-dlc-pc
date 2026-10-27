"""List the sections of one DRM and the readable strings in them (read-only survey of an unknown DRM).

Per section: type, id, size; then every ASCII string of at least MINLEN characters found in the section data
(identifiers, script/member names, file names). Works on PC (LE) DRMs of a rebuilt tree.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/drm_strings.py PATH.drm [--min N] [--grep REGEX] [--diff OTHER.drm]
  --diff: only sections that are new in PATH or differ in size from OTHER (e.g. DLC 2 vs DLC 1 version of a DRM)
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW

TYPES = {0: 'general', 2: '2', 5: 'texture', 6: 'wave', 7: 'DTP', 8: 'script', 9: 'shader lib', 10: 'material',
         11: 'Obj', 12: 'mesh', 13: '13'}


def main(argv):
    minlen = 5; pat = None
    if '--min' in argv:
        k = argv.index('--min'); minlen = int(argv[k + 1]); del argv[k:k + 2]
    if '--grep' in argv:
        k = argv.index('--grep'); pat = re.compile(argv[k + 1], re.I); del argv[k:k + 2]
    other = None
    if '--diff' in argv:
        k = argv.index('--diff'); other = argv[k + 1]; del argv[k:k + 2]
    D = DW.read(open(argv[0], 'rb').read(), 'le')
    print('sections', len(D.sections), dict(collections.Counter(TYPES.get(s.type, s.type) for s in D.sections)))
    if other:
        # only the sections that are new in this DRM or differ in size from the other one
        O = {(s.type, s.id): len(s.data) for s in DW.read(open(other, 'rb').read(), 'le').sections}
        keep = [s for s in D.sections if O.get((s.type, s.id)) != len(s.data)]
        print('vs %s: %d sections new or of another size' % (os.path.basename(other), len(keep)))
        for s in keep:
            print('   %-10s id %6d size %7d (other: %s)' % (TYPES.get(s.type, s.type), s.id, len(s.data), O.get((s.type, s.id), 'absent')))
        D.sections = keep
    rx = re.compile(rb'[\x20-\x7e]{%d,}' % minlen)
    for s in D.sections:
        strs = [m.group().decode('ascii') for m in rx.finditer(s.data)]
        if pat: strs = [x for x in strs if pat.search(x)]
        if not strs and pat: continue
        print('== %-10s id %6d size %7d  strings %d' % (TYPES.get(s.type, s.type), s.id, len(s.data), len(strs)))
        for x in strs[:60]: print('     ', x)


if __name__ == '__main__':
    main(sys.argv[1:])
