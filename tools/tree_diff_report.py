"""Compare two mods trees file by file (MD5) and list EVERY difference (tools/tree_compare.py stops after 20), grouped
by kind; for a .drm present in both, the differing sections (type, id, sizes, words) as tools/drm_section_compare.py
prints them. Read-only (agent D3, 2026-11-04: pipeline full runs against the hand-built / earlier trees).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/tree_diff_report.py DIR_A DIR_B [--no-sections] [--max-sections N]
  kinds: 'mul language variant' (<name>.mul_NNN), 'mul', 'drm', other extension
  exit 0 = identical trees, 1 = differences
"""
import sys, os, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def files(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            h = hashlib.md5()
            with open(p, 'rb') as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b''): h.update(chunk)
            out[os.path.relpath(p, root).replace(os.sep, '/')] = (h.hexdigest(), os.path.getsize(p))
    return out


def kind(rel):
    base = rel.rsplit('/', 1)[-1]
    if '.mul_' in base: return 'mul language variant'
    ext = os.path.splitext(base)[1].lower()
    return ext[1:] if ext else '(none)'


def sections(pa, pb, limit):
    """differing sections of two PC DRMs: list of text lines"""
    try:
        A = DW.read(open(pa, 'rb').read(), 'le'); B = DW.read(open(pb, 'rb').read(), 'le')
    except Exception as e:                       # not a readable PC DRM (e.g. a cinstream container)
        return ['    (not readable as a PC DRM: %s)' % e.__class__.__name__]
    lines = []
    if len(A.sections) != len(B.sections): lines.append('    section count differs: %d / %d' % (len(A.sections), len(B.sections)))
    same = 0; bad = []
    for i, (a, b) in enumerate(zip(A.sections, B.sections)):
        if (a.type, a.id, a.data, a.reloc, a.flags) == (b.type, b.id, b.data, b.reloc, b.flags):
            same += 1; continue
        n = sum(1 for o in range(0, min(len(a.data), len(b.data)) - 3, 4) if a.data[o:o + 4] != b.data[o:o + 4])
        bad.append('    section %d type %d id %d: size %d / %d, reloc %s, %d words' % (
            i, a.type, a.id, len(a.data), len(b.data), 'same' if a.reloc == b.reloc else 'DIFFERENT', n))
    lines += bad[:limit]
    if len(bad) > limit: lines.append('    ... %d more sections' % (len(bad) - limit))
    lines.append('    %d of %d sections identical; header/names %s' % (same, len(A.sections),
                 'same' if (A.names, A.pad, A.ver) == (B.names, B.pad, B.ver) else 'DIFFERENT'))
    return lines


def main(argv):
    secs = '--no-sections' not in argv; argv = [x for x in argv if x != '--no-sections']
    limit = 20
    if '--max-sections' in argv: k = argv.index('--max-sections'); limit = int(argv[k + 1]); del argv[k:k + 2]
    if len(argv) != 2: sys.exit(__doc__)
    a, b = files(argv[0]), files(argv[1])
    same = [k for k in a if k in b and a[k][0] == b[k][0]]
    diff = sorted(k for k in a if k in b and a[k][0] != b[k][0])
    only_a = sorted(set(a) - set(b)); only_b = sorted(set(b) - set(a))
    print('A %s\nB %s' % (argv[0], argv[1]))
    print('files A %d, B %d: identical %d, different %d, only in A %d, only in B %d'
          % (len(a), len(b), len(same), len(diff), len(only_a), len(only_b)))
    for title, keys in (('different', diff), ('only in A', only_a), ('only in B', only_b)):
        by = collections.defaultdict(list)
        for k in keys: by[kind(k)].append(k)
        for kd in sorted(by):
            print('%s, kind %s: %d' % (title, kd, len(by[kd])))
            for k in by[kd]:
                if title == 'different':
                    print('  %s  %s / %s  %d / %d B' % (k, a[k][0], b[k][0], a[k][1], b[k][1]))
                    if secs and kd == 'drm':
                        for l in sections(os.path.join(argv[0], k), os.path.join(argv[1], k), limit): print(l)
                else:
                    m = (a if title == 'only in A' else b)[k]
                    print('  %s  %s  %d B' % (k, m[0], m[1]))
    sys.exit(0 if not diff and not only_a and not only_b else 1)


if __name__ == '__main__':
    main(sys.argv[1:])
