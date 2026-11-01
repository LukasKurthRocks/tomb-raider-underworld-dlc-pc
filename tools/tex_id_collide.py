"""Which other DRM files carry sections of the same (type, id) as a given DRM with OTHER bytes, read-only.
The engine keeps each (type, id) once: whichever file loaded it first wins, so a figure whose texture / material /
ShaderLib ids are also used by a resident level or object with other content draws the other content.
Test 48h (2026-11-01): the doppelganger (object 857) renders with cyan hair and white trousers.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/tex_id_collide.py FILE.drm [--types 5,9,10] [--ids ID,ID] DIR_OR_FILE [...]
Output per colliding (type, id): the other files, 'same' / 'OTHER' bytes, and for textures format and size.
"""
import sys, os, struct, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW

FOURCC = {0x31545844: 'DXT1', 0x33545844: 'DXT3', 0x35545844: 'DXT5', 0x15: 'ARGB'}


def files(paths):
    for p in paths:
        if os.path.isdir(p):
            for dp, dn, fn in os.walk(p):
                for n in sorted(fn):
                    if n.lower().endswith('.drm'): yield os.path.join(dp, n)
        else:
            yield p


def tinfo(s):
    if s.type != 5 or len(s.data) < 16: return ''
    v = struct.unpack_from('<I', s.data, 4)[0]; w, h = struct.unpack_from('<HH', s.data, 16)
    return ' %s %dx%d' % (FOURCC.get(v, hex(v)), w, h)


def main(argv):
    types = {5, 9, 10}; ids = None
    if '--types' in argv: k = argv.index('--types'); types = {int(x) for x in argv[k + 1].split(',')}; del argv[k:k + 2]
    if '--ids' in argv: k = argv.index('--ids'); ids = {int(x) for x in argv[k + 1].split(',')}; del argv[k:k + 2]
    src = argv[0]
    D = DW.read(open(src, 'rb').read(), 'le')
    mine = {}
    for s in D.sections:
        if s.type in types and (ids is None or s.id in ids):
            mine.setdefault((s.type, s.id), (hashlib.md5(s.data).hexdigest(), tinfo(s)))
    hits = collections.defaultdict(list)
    for f in files(argv[1:]):
        if os.path.abspath(f) == os.path.abspath(src): continue
        try: O = DW.read(open(f, 'rb').read(), 'le')
        except Exception: continue
        for s in O.sections:
            k = (s.type, s.id)
            if k in mine:
                hits[k].append((os.path.basename(f), 'same' if hashlib.md5(s.data).hexdigest() == mine[k][0] else 'OTHER', tinfo(s)))
    other = 0
    for k in sorted(hits):
        o = [h for h in hits[k] if h[1] == 'OTHER']
        if not o: continue
        other += 1
        print('%d:%-6d mine%s | OTHER in %d file(s): %s' % (k[0], k[1], mine[k][1], len(o),
              ', '.join('%s%s' % (h[0], h[2]) for h in o[:8])))
    print('%d of %d (type, id) of %s occur elsewhere, %d with other bytes'
          % (len(hits), len(mine), os.path.basename(src), other))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
