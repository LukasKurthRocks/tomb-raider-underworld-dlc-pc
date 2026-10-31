"""Find section ids of one type that no known DRM uses (read-only): the PC bigfile index (work/idx_pc.json), the
Xbox DLC index (work/idx_dlc.json; DLC ids are kept on PC) and every DRM of the given mods folders. The engine loads
each (type, id) once, so a new section (e.g. a material copy) needs an id nobody else has. Finding 43, test 44.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/section_id_free.py TYPE START [COUNT] [MODS_DIR ...]
Prints the first COUNT (default 5) free ids >= START and the highest used id of that type.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def used_from_index(path, typ):
    out = set()
    if not os.path.exists(path): return out
    for entry in json.load(open(path)):
        for sec in entry[5] or []:
            if sec[0] == typ: out.add(sec[1])
    return out


def main(argv):
    typ, start = int(argv[0]), int(argv[1]); count = 5; rest = argv[2:]
    if rest and rest[0].isdigit(): count = int(rest[0]); rest = rest[1:]
    used = used_from_index('work/idx_pc.json', typ) | used_from_index('work/idx_dlc.json', typ)
    print('index files: %d used ids of type %d' % (len(used), typ))
    for d in rest:
        for root, _ds, fs in os.walk(d):
            for n in fs:
                if not n.lower().endswith('.drm'): continue
                try:
                    D = DW.read(open(os.path.join(root, n), 'rb').read(), 'le')
                except Exception:
                    continue
                used |= {s.id for s in D.sections if s.type == typ}
    print('with mods folders: %d used, highest %d' % (len(used), max(used) if used else -1))
    free = []; k = start
    while len(free) < count:
        if k not in used: free.append(k)
        k += 1
    print('free ids >= %d: %s' % (start, ' '.join(map(str, free))))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
