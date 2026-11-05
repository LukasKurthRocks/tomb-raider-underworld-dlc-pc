"""Does a title-update port convert every Xbox word the way Crystal's PC script does (read-only)? Shadow meter HUD
(workspace Befund-Schattenleiste-HUD.md).

The retail control (the retail Xbox script through the same port chain, equal to Crystal's PC script after the
fixes) gives, per label kind, the PC word for each Xbox word: e.g. a member userType 0x343 is 0x347 on PC, a symbol
pair 0x0527 / 0x012f is 0x0544 / 0x0131. In the title-update port every non-relocated word whose (label kind, Xbox word)
occurs in the control must have the control's PC word; a different word is a conversion the PC does not use
(the converter's 'guess_lower' userType 0x343 -> 0x345 was such a case). Words whose Xbox value the control does not
have are counted per kind (title-update data: converter maps).

Label kind = the walker label without the element index: array fields (members+0x4 ...), init words by base type,
depth, offset and userType, code words by opcode.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/script_port_consistency.py PORT.drm SCRIPT_ID XBOX XBOX_ID CONTROL.drm CONTROL_ID XBOX_CONTROL XBOX_CONTROL_ID [--max N]
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_port_check as PC
import script_func_list as FL


def words(src, sid, xsrc, xid):
    """{offset: (kind, xbox word, pc word)} for the non-relocated words of the common part"""
    import script_conv as SC
    P = PC.load(src, sid); X = PC.load(xsrc, xid)
    S, e = FL.sections(src)
    d, rl = next((q[2], q[3]) for q in S if q[0] == 8 and q[1] == sid)
    W = SC.Walk(d, R.parse(rl, e), e); W.run()
    reloc = set(P['it']) | set(P['ext']) | set(P['ida']) | set(P['idr']) | set(X['it']) | set(X['ext']) | \
        set(X['ida']) | set(X['idr'])
    out = {}
    for o in range(0, min(len(P['d']), len(X['d'])) // 4 * 4, 4):
        if o in reloc: continue
        lab = W.lab.get(o)
        if lab is None: kind = '-'
        elif lab[0] == 'init': kind = str(lab)
        elif lab[0] in ('code.op', 'code.arg'): kind = str(lab[:2])
        else:
            s = PC.label(P, o)
            kind = re.sub(r'\[\d+\]', '', s) if s != '-' else str(lab[:1])
        out[o] = (kind, X['d'][o:o + 4], P['d'][o:o + 4])
    return out


def main(argv):
    mx = 60
    if '--max' in argv: k = argv.index('--max'); mx = int(argv[k + 1]); del argv[k:k + 2]
    if len(argv) != 8: sys.exit(__doc__)
    T = words(argv[0], int(argv[1]), argv[2], int(argv[3]))
    C = words(argv[4], int(argv[5]), argv[6], int(argv[7]))
    ref = collections.defaultdict(set)
    for kind, xw, pw in C.values(): ref[kind, xw].add(pw)
    amb = sum(1 for v in ref.values() if len(v) > 1)
    st = collections.Counter(); bad = []; new = collections.Counter()
    for o, (kind, xw, pw) in sorted(T.items()):
        r = ref.get((kind, xw))
        if r is None: st['Xbox word not in the control (title-update value)'] += 1; new[kind] += 1; continue
        if pw in r: st['as the control'] += 1; continue
        if len(r) > 1: st['control ambiguous for this word, port value not among them'] += 1
        else: st['DIFFERENT from the control'] += 1
        bad.append((o, kind, xw, pw, r))
    print('port %s %s: %d words; control %d words, %d (kind, Xbox word) keys with more than one PC word' % (
        argv[0], argv[1], len(T), len(C), amb))
    print(dict(st))
    for o, kind, xw, pw, r in bad[:mx]:
        print('  +%#06x %-40s Xbox %s port %s control %s' % (o, kind[:40], xw.hex(), pw.hex(), ' / '.join(x.hex() for x in r)))
    if len(bad) > mx: print('  ... %d more' % (len(bad) - mx))
    print('title-update values by kind (top 15): %s' % new.most_common(15))


if __name__ == '__main__':
    main(sys.argv[1:])
