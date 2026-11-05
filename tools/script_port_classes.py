"""How every data word of a ported script came from the Xbox word at the same offset (read-only). Shadow meter HUD
(workspace Befund-Schattenleiste-HUD.md): a script converted from the Xbox keeps the Xbox offsets (script_vtable_insert
appends; script_init_from_pc / script_word_set change words in place), so each non-relocated PC word can be compared
with the Xbox word at the same offset. Classes (as tools/script_diff.py): s32 (byte-reversed = a 32-bit value), s16
(u16 halves swapped in place), raw (bytes unchanged), u8u8u16 / u16u8u8, other (no byte permutation: a value map -
symbol, string / glyph id, script id - or a wrong conversion). Counted per walker label kind; with --list CLASS the
words of that class are printed with their label (e.g. --list other for review).

Run it on the retail control (Crystal's PC script = the ground truth after the port chain) and on the title-update
port: a label kind that is 'other' only in the title-update port, or many more 'other' words of a kind, points at a
conversion the control does not cover.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/script_port_classes.py PORT.drm SCRIPT_ID XBOX XBOX_ID [--list CLASS] [--kinds K1,K2] [--max N]
  XBOX = tools/menu_dlc_probe.py variant xl (retail) / xt (title update)
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import script_port_check as PC

PERMS = {'s32': (3, 2, 1, 0), 's16': (1, 0, 3, 2), 'raw': (0, 1, 2, 3), 'u8u8u16': (0, 1, 3, 2), 'u16u8u8': (1, 0, 2, 3)}


def cls(x, p):
    if x == p: return 'raw'
    for name, pm in PERMS.items():
        if bytes(x[i] for i in pm) == p: return name
    return 'other'




def main(argv):
    lst = None; kinds = None; mx = 200
    if '--list' in argv: k = argv.index('--list'); lst = argv[k + 1]; del argv[k:k + 2]
    if '--kinds' in argv: k = argv.index('--kinds'); kinds = set(argv[k + 1].split(',')); del argv[k:k + 2]
    if '--max' in argv: k = argv.index('--max'); mx = int(argv[k + 1]); del argv[k:k + 2]
    if len(argv) != 4: sys.exit(__doc__)
    import script_conv as SC, drm_reloc as R, script_func_list as FL
    port, sid, xv, xid = argv[0], int(argv[1]), argv[2], int(argv[3])
    P = PC.load(port, sid); X = PC.load(xv, xid)
    # full walker labels of the port (the Xbox labels are the same words - same offsets)
    S, e = FL.sections(port)
    d, rl = next((q[2], q[3]) for q in S if q[0] == 8 and q[1] == sid)
    W = SC.Walk(d, R.parse(rl, e), e); W.run()
    n = min(len(P['d']), len(X['d'])) // 4 * 4
    reloc = set(P['it']) | set(P['ext']) | set(P['ida']) | set(P['idr'])
    xreloc = set(X['it']) | set(X['ext']) | set(X['ida']) | set(X['idr'])
    cnt = collections.Counter(); per = collections.defaultdict(collections.Counter); hits = []
    for o in range(0, n, 4):
        if o in reloc or o in xreloc: cnt['relocated'] += 1; continue
        lab = W.lab.get(o)
        k = '-' if lab is None else '%s' % (lab[0] if lab[0] not in ('init', 'code.op', 'code.arg') else
                                            '%s.%s' % (lab[0], lab[1]))
        c = cls(X['d'][o:o + 4], P['d'][o:o + 4])
        cnt[c] += 1; per[k][c] += 1
        if lst and c == lst and (kinds is None or k in kinds): hits.append((o, k, lab))
    print('%s script %d vs %s %d: %d words compared (%s)' % (port, sid, xv, xid, n // 4, dict(cnt)))
    for k in sorted(per, key=lambda q: -sum(per[q].values())):
        print('  %-24s %s' % (k, dict(per[k])))
    for o, k, lab in hits[:mx]:
        print('  +%#06x %-14s Xbox %s PC %s  %s' % (o, k, X['d'][o:o + 4].hex(), P['d'][o:o + 4].hex(), lab))
    if len(hits) > mx: print('  ... %d more' % (len(hits) - mx))


if __name__ == '__main__':
    main(sys.argv[1:])
