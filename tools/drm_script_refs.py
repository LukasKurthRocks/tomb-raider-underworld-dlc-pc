"""Which scripts refer to one script section (e.g. a native type) across a folder of DRM files. Read-only.

For every DRM: whether it carries section (8, TARGET), and every external relocation of a script section that points
into (8, TARGET) - source script id, source offset, target offset (the callee's function entry for a call).
Finding 43, test 37: does a DLC 2 level script call the title update's native `dlc2data` (script 21239)?

Usage (from the repository root):
  ../bin/pyt tools/drm_script_refs.py DIR_OR_DRM TARGET_ID [le|be]      default le (PC); be for Xbox DRMs
  ../bin/pyt tools/drm_script_refs.py SOURCE TARGET_ID NAMES_DIR        an archive of tools/locals.py (pack11, tu,
      xbase, ...): every DRM whose name is a .drm file in NAMES_DIR (e.g. a converted PC tree) is read from it
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import drm_write as DW


def load(path, e):
    """DRM bytes of a file, or of 'SOURCE:name.drm' read from a game archive"""
    if ':' in path and not os.path.exists(path):
        import locals as LC
        from archive import Archive
        from names import crc
        from drm import cdrm_decode
        src, name = path.split(':', 1)
        apath, ae, pre = LC.SRC[src]
        A = load.cache.setdefault(src, Archive(apath, ae))
        recs = A.find(crc(pre + '\\' + name))
        if not recs:
            return None
        return cdrm_decode(A.read(recs[-1]), ae)
    return open(path, 'rb').read()
load.cache = {}


def scan(path, tid, e):
    b = load(path, e)
    if b is None:
        return None, []
    D = DW.read(b, e)
    S = D.sections
    has = any(s.type == 8 and s.id == tid for s in S)
    refs = []
    for s in S:
        if s.type != 8 or not s.reloc:
            continue
        rel = R.parse(s.reloc, e)
        for si, so, do in rel.external:
            if 0 <= si < len(S) and S[si].type == 8 and S[si].id == tid:
                refs.append((s.id, so, do))
    return has, refs


def main(argv):
    src, tid = argv[0], int(argv[1])
    e = argv[2] if len(argv) > 2 and argv[2] in ('le', 'be') else 'le'
    if len(argv) > 2 and argv[2] not in ('le', 'be'):      # archive source + names taken from a folder
        import locals as LC
        e = LC.SRC[src][1]
        files = sorted('%s:%s' % (src, f) for f in os.listdir(argv[2]) if f.lower().endswith('.drm'))
    else:
        files = [src] if os.path.isfile(src) else sorted(
            os.path.join(src, f) for f in os.listdir(src) if f.lower().endswith('.drm'))
    nhas = nref = nmiss = 0
    for f in files:
        try:
            has, refs = scan(f, tid, e)
        except Exception as ex:                             # a file the reader cannot parse: report, go on
            print('%-40s READ ERROR %s' % (os.path.basename(f), ex))
            continue
        if has is None:
            nmiss += 1
            continue
        nhas += has
        if has or refs:
            print('%-40s has (8,%d): %s, references: %d' % (os.path.basename(f), tid, has, len(refs)))
        for sid, so, do in refs:
            nref += 1
            print('    script %6d +0x%04x -> (8,%d)+0x%x' % (sid, so, tid, do))
    print('%d files (%d not in the archive), %d carry (8,%d), %d references' % (len(files), nmiss, nhas, tid, nref))


if __name__ == '__main__':
    main(sys.argv[1:])
