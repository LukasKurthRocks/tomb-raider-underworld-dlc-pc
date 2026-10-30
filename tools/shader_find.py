"""Find a shader that was dumped from the running game (e.g. with cdb .writemem at a failing CreatePixelShader call)
in the DRM files of a folder: reports every ShaderLib section (DRM type 9) entry whose bytecode equals the dump
(compared up to and including the END token) - file, section id, whether the id is one of the port's own libraries
(native_extract.NEW_LIBS) and the entry offset. Read-only (finding 43, DLC 1 test of 30.10.2026).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/shader_find.py DUMP.bin DIR [DIR ...]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
from shader_const_fix import split_end, lib_parse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'native_test'))
from native_extract import NEW_LIBS


def main(argv):
    dump = open(argv[0], 'rb').read()
    want, _ = split_end(dump)
    print('dump: %d bytes up to END, version token %08x' % (len(want), struct.unpack_from('<I', want)[0]))
    hits = 0; files = 0
    for top in argv[1:]:
        for dp, dn, fn in os.walk(top):
            for f in sorted(fn):
                if not f.lower().endswith('.drm'): continue
                p = os.path.join(dp, f); files += 1
                try: D = DW.read(open(p, 'rb').read(), 'le')
                except Exception as e: print('  skipped %s: %s' % (p, e)); continue
                for s in D.sections:
                    if s.type != 9: continue
                    _, _, offs, ents, _ = lib_parse(s.data)
                    for o, (a, h, code, at) in sorted(ents.items()):
                        body, _ = split_end(code)
                        if body == want:
                            hits += 1
                            print('HIT %s lib %d (%s) entry %d hash %016x slots %s' % (
                                p, s.id, 'port' if s.id in NEW_LIBS else 'NOT in NEW_LIBS', o, h,
                                [i for i, x in enumerate(offs) if x == o]))
    print('files: %d, hits: %d' % (files, hits))


if __name__ == '__main__':
    main(sys.argv[1:])
