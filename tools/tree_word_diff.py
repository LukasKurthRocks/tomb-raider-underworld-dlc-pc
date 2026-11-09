"""Word-level diff of two trees of PC DRM files (read-only; 2026-11-09 uiinit): per DRM of the same name the decoded
sections are compared - type, id, relocation table and every 4-byte data word. With --expect REPORT.json (a report
of tools/ui_init_fix.py apply / scan: rows {drm, script, off, old, new}) the differing words must be exactly the
planned ones (section type 8 of that script, offset, old -> new) and nothing else may differ.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/tree_word_diff.py BEFORE_TREE AFTER_TREE [--expect R.json [R2.json ...]]
    per DRM with a difference: 'NAME: words W (planned P, unplanned U), sections with other relocations / size N'
    last line: 'drms D, differing X, words W, planned P, unplanned U, planned-but-missing M'
    exit 1 when anything unplanned differs or a planned word is missing (with --expect), else 0
"""
import sys, os, json, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_write as DW


def files(tree):
    out = {}
    for r, _, fs in os.walk(tree):
        for f in fs:
            if f.lower().endswith('.drm'): out[f.lower()] = os.path.join(r, f)
    return out


def main(argv):
    exp = None
    if '--expect' in argv:
        k = argv.index('--expect'); paths = argv[k + 1:]; argv = argv[:k]
        exp = collections.defaultdict(dict)
        for p in paths:
            for r in json.load(open(p))['rows']:
                exp[r['drm'].lower()][(r['script'], r['off'])] = (bytes.fromhex(r['old']), bytes.fromhex(r['new']))
    if len(argv) != 2:
        print(__doc__); return 2
    A, B = files(argv[0]), files(argv[1])
    tot = collections.Counter()
    for name in sorted(set(A) | set(B)):
        tot['drms'] += 1
        if name not in A or name not in B:
            tot['unplanned'] += 1; print('%s: only in %s' % (name, 'after' if name in B else 'before')); continue
        a, b = open(A[name], 'rb').read(), open(B[name], 'rb').read()
        if a == b:
            if exp and exp.get(name): tot['missing'] += len(exp[name]); print('%s: planned words missing (file equal)' % name)
            continue
        DA, DB = DW.read(a, 'le'), DW.read(b, 'le')
        st = collections.Counter(); want = dict(exp.get(name, {})) if exp is not None else {}
        if len(DA.sections) != len(DB.sections): st['section count'] += 1
        for sa, sb in zip(DA.sections, DB.sections):
            if (sa.type, sa.id, sa.reloc, len(sa.data)) != (sb.type, sb.id, sb.reloc, len(sb.data)): st['sections with other relocations / size'] += 1; continue
            if sa.data == sb.data: continue
            for o in range(0, len(sa.data), 4):
                wa, wb = sa.data[o:o + 4], sb.data[o:o + 4]
                if wa == wb: continue
                st['words'] += 1
                key = (sa.id, o)
                if exp is not None and sa.type == 8 and key in want and want[key] == (bytes(wa), bytes(wb)):
                    st['planned'] += 1; del want[key]
                else:
                    st['unplanned'] += 1
        if exp is not None: st['missing'] += len(want)
        tot['differing'] += 1
        for k in ('words', 'planned', 'unplanned', 'missing', 'section count', 'sections with other relocations / size'):
            tot[k] += st[k]
        print('%s: words %d (planned %d, unplanned %d, missing %d), sections with other relocations / size %d' % (
            name, st['words'], st['planned'], st['unplanned'], st['missing'], st['sections with other relocations / size']))
    print('drms %d, differing %d, words %d, planned %d, unplanned %d, planned-but-missing %d' % (
        tot['drms'], tot['differing'], tot['words'], tot['planned'],
        tot['unplanned'] + tot['section count'] + tot['sections with other relocations / size'], tot['missing']))
    bad = tot['unplanned'] + tot['section count'] + tot['sections with other relocations / size']
    if exp is not None: bad += tot['missing']
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
