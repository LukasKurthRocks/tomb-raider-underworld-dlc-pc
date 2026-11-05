"""Compare one script section (type 8) of two PC DRMs word by word, read-only: a ported / converted script against a
reference (Crystal's PC script, or an earlier port). Shadow meter HUD (docs: workspace Befund-Schattenleiste-HUD.md):
the control conversion of the RETAIL Xbox HUD script 38 must end equal to Crystal's PC script 37, so that the same
chain applied to the title-update script 38 is trustworthy.

Per word of the common part (or of the function code with --code): equal, or different with the walker label of
the word (array / element / byte offset) on both sides, the value on both sides and the relocation kind there
(internal target, external (type, id, offset), id reference). Relocations are compared as sets:
internal targets, external targets by (type, id, offset), id references by (type, offset).

--code: compare function by function (paired by index) - code words, with external call targets shown by
(type, id, offset) instead of the raw word; good for scripts of different size (title update vs retail).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/script_port_check.py A.drm B.drm SCRIPT_ID [--b-id N] [--max N] [--code] [--funcs 15,16]
  A, B   PC (little-endian) DRM files, or tools/menu_dlc_probe.py variants (xl / xt / pb / pp)
  --b-id the script id in B when it differs (e.g. Xbox 38 = PC 37)
  --max  print at most N differing words (default 80; the counts are always complete)
  --at   HEX[,HEX]: only print the word, label and relocation at these offsets in A and B
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL


def load(src, sid):
    import script_conv as SC
    S, e = FL.sections(src)
    E = '>' if e == 'be' else '<'
    q = next((q for q in S if q[0] == 8 and q[1] == sid and q[2]), None)
    if q is None: sys.exit('script %d not in %s' % (sid, src))
    d, rl = q[2], q[3]
    rel = R.parse(rl, e)
    W = SC.Walk(d, rel, e).run()
    return dict(d=d, E=E, rel=rel, it=dict(rel.internal),
                ext={so: (S[si][0], S[si][1], do) for si, so, do in rel.external},
                ida={o: t for t, o in rel.idref_a}, idr={o: t for t, o in rel.idref},
                arrays=list(W.arrays), bad=W.bad)


def label(X, o):
    for name, t, n, sz in X['arrays']:
        if t <= o < t + n * sz: return '%s[%d]+%#x' % (name, (o - t) // sz, (o - t) % sz)
    return '-'


def relkind(X, o):
    if o in X['it']: return 'int->+%#x' % X['it'][o]
    if o in X['ext']: return 'ext->%s' % (X['ext'][o],)
    if o in X['ida']: return 'idA(%d)' % X['ida'][o]
    if o in X['idr']: return 'id(%d)' % X['idr'][o]
    return ''


def word(X, o):
    return struct.unpack_from(X['E'] + 'I', X['d'], o)[0]


def funcs(X):
    """[(index, code start, word count)] of the functions (None start = native)"""
    out = []
    for name, t, n, sz in X['arrays']:
        if name != 'funcs': continue
        for k in range(n):
            ct = X['it'].get(t + k * sz + 0x18)
            out.append((k, ct, word(X, ct - 4) if ct is not None else 0))
    return out


def code_words(X, start, n):
    """code words with relocated operands replaced by their target, so two files compare by meaning"""
    out = []
    for i in range(n):
        o = start + 4 * i
        if o in X['ext']: out.append(('ext',) + X['ext'][o])
        elif o in X['it']: out.append(('int',))           # internal target offsets differ between layouts
        elif o in X['idr']: out.append(('id', X['idr'][o], word(X, o)))
        elif o in X['ida']: out.append(('idA', X['ida'][o], word(X, o)))
        else: out.append(word(X, o))
    return out


def main(argv):
    mx = 80; bid = None; code = False; only = None
    if '--max' in argv: k = argv.index('--max'); mx = int(argv[k + 1]); del argv[k:k + 2]
    if '--b-id' in argv: k = argv.index('--b-id'); bid = int(argv[k + 1]); del argv[k:k + 2]
    if '--funcs' in argv: k = argv.index('--funcs'); only = {int(x) for x in argv[k + 1].split(',')}; del argv[k:k + 2]
    if '--code' in argv: code = True; argv.remove('--code')
    at = None
    if '--at' in argv: k = argv.index('--at'); at = [int(x, 16) for x in argv[k + 1].split(',')]; del argv[k:k + 2]
    if len(argv) != 3: sys.exit(__doc__)
    sid = int(argv[2])
    A = load(argv[0], sid); B = load(argv[1], bid if bid is not None else sid)
    if at:                                  # --at HEX[,HEX]: the word, label and relocation at these offsets
        for o in at:
            print('+%#06x A %08x %-22s %-26s | B %08x %-22s %s' % (o, word(A, o), label(A, o), relkind(A, o),
                                                                  word(B, o), label(B, o), relkind(B, o)))
        return
    print('A %s script %d: %d bytes, walker problems %s' % (argv[0], sid, len(A['d']), A['bad'][:3]))
    print('B %s script %d: %d bytes, walker problems %s' % (argv[1], bid if bid is not None else sid, len(B['d']), B['bad'][:3]))
    if code:
        fa, fb = funcs(A), funcs(B)
        print('functions: A %d, B %d' % (len(fa), len(fb)))
        same = 0
        for k in range(max(len(fa), len(fb))):
            if only is not None and k not in only: continue
            if k >= len(fa) or k >= len(fb):
                print('  f%-3d only in %s' % (k, 'A' if k < len(fa) else 'B')); continue
            (_, sa, na), (_, sb, nb) = fa[k], fb[k]
            if sa is None or sb is None:
                print('  f%-3d native A %s / B %s' % (k, sa is None, sb is None)); same += (sa is None) == (sb is None); continue
            ca, cb = code_words(A, sa, na), code_words(B, sb, nb)
            if ca == cb: same += 1; continue
            diff = [i for i in range(min(na, nb)) if ca[i] != cb[i]]
            print('  f%-3d code A %d / B %d words, %d of the common %d differ%s' % (
                k, na, nb, len(diff), min(na, nb), ': first at word %d A %s B %s' % (
                    diff[0], ca[diff[0]], cb[diff[0]]) if diff else ''))
        print('functions with identical code (operands by target): %d' % same)
        return
    n = min(len(A['d']), len(B['d'])) // 4 * 4
    diff = [o for o in range(0, n, 4) if word(A, o) != word(B, o)]
    print('common part 0x%x bytes: %d of %d words differ' % (n, len(diff), n // 4))
    cnt = collections.Counter(label(A, o).split('[')[0] for o in diff)
    print('differing words by array (A labels): %s' % dict(cnt))
    for o in diff[:mx]:
        print('  +%#06x A %08x %-22s %-26s | B %08x %-22s %s' % (o, word(A, o), label(A, o), relkind(A, o), word(B, o),
                                                                label(B, o), relkind(B, o)))
    if len(diff) > mx: print('  ... %d more' % (len(diff) - mx))
    for name, ka, kb in (('internal targets', set(A['rel'].internal), set(B['rel'].internal)),
                         ('external targets', set(A['ext'].items()), set(B['ext'].items())),
                         ('id references', set(A['rel'].idref), set(B['rel'].idref)),
                         ('id references A', set(A['rel'].idref_a), set(B['rel'].idref_a))):
        print('%s: A %d, B %d, only A %d, only B %d' % (name, len(ka), len(kb), len(ka - kb), len(kb - ka)))
        for x in sorted(ka - kb, key=str)[:12]: print('    only A %s' % (x,))
        for x in sorted(kb - ka, key=str)[:12]: print('    only B %s' % (x,))


if __name__ == '__main__':
    main(sys.argv[1:])
