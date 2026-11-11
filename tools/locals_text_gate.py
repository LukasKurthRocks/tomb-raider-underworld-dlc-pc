"""Gate for the string tables of `tools/locals.py build` (R9 of the own-tree comparison): compares the produced
`locals.bin_NNN` with a reference set (e.g. the installed tables, read only, explicit file names) string by string.

Reports per language file: string count, language field, every differing id (text and 'missing' offset-0 state),
the R9 ids (456 / 457 descriptions, 5211 unfilled slot, Spanish 93 / 98 / 450) and md5 of both files. Prints no
game text unless --show is given. Exit 0 only when every string of every file is equal.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/locals_text_gate.py PRODUCED_DIR REFERENCE_DIR [--json OUT.json] [--show N]
  both directories hold locals.bin_001 / 002 / 004 / 008 / 016 / 032 (other files are not read)
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as L

SUFFIXES = ('001', '002', '004', '008', '016', '032')
R9_IDS = {'001': (456, 457, 5211), '002': (456, 457, 5211), '004': (456, 457, 5211), '008': (456, 457, 5211),
          '016': (93, 98, 450, 456, 457, 5211), '032': (456, 457, 5211)}


def table(path):
    raw = open(path, 'rb').read()
    lang, st, offs = L.parse(raw, 'le')
    return raw, lang, st, offs


def main(argv):
    out_json, show = None, 0
    if '--json' in argv:
        k = argv.index('--json'); out_json = argv[k + 1]; del argv[k:k + 2]
    if '--show' in argv:
        k = argv.index('--show'); show = int(argv[k + 1]); del argv[k:k + 2]
    prod, ref = argv[0], argv[1]
    res, bad = {}, 0
    for sfx in SUFFIXES:
        name = 'locals.bin_' + sfx
        ra, la, sa, oa = table(os.path.join(prod, name))
        rb, lb, sb, ob = table(os.path.join(ref, name))
        n = max(len(sa), len(sb))
        diff = []
        for i in range(n):
            x = sa[i] if i < len(sa) else None; y = sb[i] if i < len(sb) else None
            za = i < len(oa) and oa[i] == 0; zb = i < len(ob) and ob[i] == 0
            if x != y or za != zb: diff.append(i)
        r9 = {str(i): ('equal' if i not in diff else 'DIFFERENT') for i in R9_IDS[sfx]}
        md5a, md5b = hashlib.md5(ra).hexdigest(), hashlib.md5(rb).hexdigest()
        ok = not diff and la == lb and len(sa) == len(sb)
        bad += not ok
        res[name] = dict(ok=ok, lang=[la, lb], n=[len(sa), len(sb)], differing=diff, r9=r9, md5_equal=md5a == md5b,
                         md5=[md5a, md5b])
        print('%s %s lang %d/%d n %d/%d differing %d %s r9 %s md5 %s' % (
            name, 'ok' if ok else 'FAIL', la, lb, len(sa), len(sb), len(diff), diff[:20],
            ' '.join('%s=%s' % kv for kv in r9.items()), 'equal' if md5a == md5b else '%s / %s' % (md5a[:12], md5b[:12])))
        for i in diff[:show]:
            f = lambda s: None if s is None else s.decode('utf-8', 'replace').replace('\n', '\\n')[:120]
            print('   [%d] produced %r' % (i, f(sa[i] if i < len(sa) else None)))
            print('   [%d] reference %r' % (i, f(sb[i] if i < len(sb) else None)))
    print('gate: %s (%d of %d files differ)' % ('ok' if not bad else 'FAIL', bad, len(SUFFIXES)))
    if out_json:
        json.dump(dict(produced=prod, reference=ref, files=res, ok=not bad), open(out_json, 'w'), indent=1)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
