"""Upstream-only DTP byte-order corrections (B270 kit, 22 DLC 1 files) against our copies and the base-pair rules
(read-only; kit-rest task 2, workspace docs Befund-Kit-Reste-0511.md).

For each named DRM: the Xbox source (pack10 first, as the kit builds DLC 1), his B270 file and our copies (B138
pristine, our B138 repair tree, our own stage-2b conversion, the installed game file) are read; type-7 sections are
paired to the Xbox section via tools/tuning_word_audit.pair (same DTP id, else same size + internal pointer
offsets). Words: every word in which his section differs from B138 (B138 = his base), unless offsets are given.
Per word and copy: the value and its class against the Xbox bytes (u32 / u16pair / raw / u8u8u16 / other), and the
base-pair rule of tools/dtp_audit.py for that word (FP key = offset in region, slot mask, value shape, parent slot;
RULED = >= 20 informative base Xbox / PC samples that all agree, rules in work/generic/dtp_audit_rules.pkl).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/kitrest_dtp_words.py [NAME[:DTP[:OFF,OFF..]] ...] [-v]
      default: the 13 files of the task (adrenaline trap x2, sluice falls, puddle, water wheel, 2 glare FX, intro
      cinematic, costumes b c e j o); -v prints every word, else the first 12 per section + the summary
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import tuning_word_audit as TA
import dtp_audit as DA

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
TREES = [('b138', 'work/rebuild/b138_pristine/mods'), ('repair', 'work/rebuild/b138_fixes/mods'),
         ('own2b', 'work/rebuild/asm_stage2b_ach/mods'), ('inst', '../data/pc/mods'), ('his', 'work/b270_kit/mods')]
DEFAULT = ['dlc1_uo_adren_trap', 'ma_ani_adren_trap', 'dlc1_uo_sluice_falls', 'fx_mex_puddle_ist',
           'dlc1_uo_water_wheel', 'dlc_fx_glare_simple_hallb_ist', 'dlc_fx_glare_simple_waterwhl_ist',
           'cinstream/pdlc1_010_intro', 'dlc_costume_b', 'dlc_costume_c', 'dlc_costume_e', 'dlc_costume_j',
           'dlc_costume_o']


def load_x(name):
    TA.ORDER = ('pack10', 'pack11', 'tu', 'xbase2', 'xbase')
    return TA.load_x(name.replace('/', chr(92)))


def rule_of(xd, xrel):
    rl = DA.rules()
    return {o: rl.get(k) for o, k in DA.word_keys(xd, xrel)}


def main(a):
    verbose = '-v' in a; a = [x for x in a if x != '-v']
    while '--tree' in a:            # extra copy: --tree TAG=DIR (relative to the repository root)
        k = a.index('--tree'); tg, dd = a[k + 1].split('=', 1); TREES.insert(-1, (tg, dd)); del a[k:k + 2]
    specs = []
    for s in a or DEFAULT:
        p = s.split(':')
        specs.append((p[0], int(p[1]) if len(p) > 1 else None, [int(x, 16) for x in p[2].split(',')] if len(p) > 2 else None))
    tot = collections.Counter()
    for name, want_id, offs in specs:
        rel = name + '.drm'
        xs, src = load_x(rel)
        copies = {}
        for tag, d in TREES:
            p = os.path.join(ROOT, d, rel)
            if os.path.isfile(p): copies[tag] = TA.load_p(p)
        print('\n=== %s (Xbox %s) copies: %s' % (rel, src, ' '.join(copies)))
        prs = {tag: TA.pair(xs, ps) for tag, ps in copies.items()}
        for i, (x, ph) in enumerate(prs['his']):
            pb = prs['b138'][i][1]
            if ph is None or pb is None: continue
            if want_id is not None and ph['id'] != want_id: continue
            n = min(len(ph['data']), len(pb['data']), len(x['data']))
            ws = offs if offs is not None else [o for o in range(0, n - 3, 4) if ph['data'][o:o + 4] != pb['data'][o:o + 4]]
            if not ws: continue
            xd = x['data']; xrel = R.parse(x['reloc'], 'be')
            slots = set(xrel.pointer_offsets()) | set(xrel.id_offsets())
            rules = rule_of(xd, xrel)
            print('-- DTP Xbox %d / his %d / b138 %d: %d word(s), copies paired: %s' % (
                x['id'], ph['id'], pb['id'], len(ws), ' '.join('%s=%s' % (t, prs[t][i][1]['id'] if prs[t][i][1] else '-')
                                                              for t in copies)))
            summ = collections.Counter()
            for k, o in enumerate(ws):
                xw = xd[o:o + 4]
                r = rules.get(o); rname = DA.NAMES[r] if r is not None else ('slot' if o in slots else '-')
                his_c = TA.cls(xw, ph['data'][o:o + 4])
                cells = []
                for t in copies:
                    q = prs[t][i][1]
                    if q is None or o + 4 > len(q['data']): cells.append('%s=?' % t); continue
                    pw = q['data'][o:o + 4]
                    c = TA.cls(xw, pw)
                    cells.append('%s=%s(%s)' % (t, pw[::-1].hex(), c))
                    summ[(t, 'same as his' if pw == ph['data'][o:o + 4] else 'differs')] += 1
                summ[('rule', rname)] += 1
                summ[('his class', his_c)] += 1
                summ[('his = rule', str(his_c.replace('u32', 's32').replace('u16pair', 's16') == rname) if r is not None else 'no rule')] += 1
                if verbose or k < 12:
                    print('  +0x%05x xbox %s | rule %-5s | %s' % (o, xw.hex(), rname, ' '.join(cells)))
            if not verbose and len(ws) > 12: print('  ... %d more' % (len(ws) - 12))
            for key in sorted(summ):
                print('  summary %-10s %-12s %d' % (key[0], key[1], summ[key]))
                tot[(rel,) + key] += summ[key]


if __name__ == '__main__':
    main(sys.argv[1:])
