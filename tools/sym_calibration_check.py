"""Check the B138 symbol calibration against base-game evidence (finding 43, DLC 2 test 4).

The learned symbol map lacks some Xbox Symbols; docs/data/b138_symbol_calibration.json fills them from B138's DLC 1
words (findings 33, 35). The base game gives independent evidence for function/prototype NAME Symbols: the same script
exists on the Xbox (retail layers) and on PC, and script_conv.offset_map pairs its functions/prototypes; pairs whose
Xbox name the learned map does not know vote xbox symbol -> PC symbol (positional runs of equal length, or by
structure). Example: generalbank script 6, function 1 has Xbox name 515 and PC name 517 (same slot, same 45 code
words), but the calibration maps 515 -> 333.

Reports per Symbol with base evidence: calibration agrees / disagrees / has no entry, and writes
work/rebuild/sym_base_evidence.json = {"symbols": {xbox: pc}} (majority vote, the calibration overridden where the base
disagrees) - usable as TRUDLC_SYM_EXTRA for converting base-game scripts (title-update generalbank).

Usage (from the repository root; loads the id store):
  ..\\bin\\venv\\Scripts\\python.exe -u -I -X utf8 tools/sym_calibration_check.py [NAME.drm ...]   (default generalbank.drm)
"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtp_word_classes as C, dlc_generic as DG, drm_reloc as R, script_conv as SC

BS = chr(92)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'rebuild', 'sym_base_evidence.json')


def main(argv):
    names = argv or ['generalbank.drm']
    ids = DG.DlcIds(); symmap = ids.base.get(DG.SYM, {})
    cal = json.load(open(DG.DlcIds.SYM_CALIBRATION)); cal = {int(a): b for a, b in cal.get('symbols', cal).items()}
    votes = collections.defaultdict(collections.Counter); scripts = 0
    for name in names:
        xs = C.find(C.BASE[1:], 'be', 'xenon-w' + BS + name); ps = C.find(C.PC, 'le', 'pc-w' + BS + name)
        if not xs or not ps: print('%s: missing on %s' % (name, 'Xbox' if not xs else 'PC')); continue
        pc = {s['id']: s for s in ps if s['type'] == 8 and s['data']}
        for x in xs:
            if x['type'] != 8 or not x['data']: continue
            p = pc.get(ids(8, x['id']))
            if p is None: continue
            try:
                SC.offset_map(x['data'], R.parse(x['reloc'], 'be'), p['data'], R.parse(p['reloc'], 'le'), symmap, votes)
                scripts += 1
            except Exception as e:
                print('%s script %d: offset map failed: %s' % (name, x['id'], e))
    best = {}; rows = collections.Counter(); conv = collections.Counter(); bad = []
    for xsym, c in sorted(votes.items()):
        if xsym in symmap: continue                     # known to the learned map - not the calibration's business
        psym, n = c.most_common(1)[0]
        best[xsym] = psym
        conv['converter (DlcIds.sym) right' if ids.sym(xsym) == psym else 'converter (DlcIds.sym) WRONG'] += 1
        if xsym not in cal: rows['no calibration entry'] += 1
        elif cal[xsym] == psym: rows['calibration agrees'] += 1
        else: rows['calibration DISAGREES'] += 1; bad.append((xsym, cal[xsym], psym, n, len(c)))
    print('%d scripts paired in %s; %d Xbox name Symbols outside the learned map with base evidence' % (
        scripts, ', '.join(names), len(best)))
    for k, n in sorted(rows.items()) + sorted(conv.items()): print('  %-32s %d' % (k, n))
    print('  converter rule used for them: %s' % dict(ids.sym_stats))
    for xsym, c, p, n, k in bad:
        print('  xbox %d: calibration %d, base %d (%d votes%s)' % (xsym, c, p, n, '' if k == 1 else ', %d candidates' % k))
    merged = dict(cal); merged.update(best)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({'symbols': {str(k): v for k, v in sorted(merged.items())}}, open(OUT, 'w'), indent=0)
    print('-> %s (%d entries: calibration with %d base overrides/additions)' % (os.path.normpath(OUT), len(merged), len(best)))


if __name__ == '__main__':
    main(sys.argv[1:])
