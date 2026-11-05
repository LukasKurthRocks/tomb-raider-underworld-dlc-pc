"""Init words that hold two Symbols (u16 pairs, e.g. the member paths of UI timeline descriptors) in a title-update
port, checked / fixed with the converter's own Symbol map (read-only on the inputs; --fix writes OUT). Shadow meter HUD
(workspace Befund-Schattenleiste-HUD.md).

Learned from the retail control (equal to Crystal's PC script): an init label kind (base type, offset in the node,
userType - at any depth: the title update chains the same pairs deeper) is a "Symbol pair" kind when every control
word of it with a non-zero Xbox value is, on PC, the two Xbox u16 halves each mapped by dlc_generic.DlcIds.sym in
place (Xbox 0x0527 / 0x012f -> PC 0x0544 / 0x0131), at least 3
such words and no exception. In the title-update port every word of those kinds must be that pair map of its Xbox
word; the converter leaves some title-update words byte-reversed (s32) or keeps a title-update Symbol unmapped
(0x46f1 instead of 0x48d1 = the name the port's own member got) - listed, and set with --fix.

The Symbol map is the converter's (base map + TRUDLC_SYM_EXTRA, e.g. work/rebuild/sym_base_evidence.json, as in
pipeline step 2 of tools/generalbank_build.py); title-update-only Symbols take its 'dlc_new_shift' route.

Usage (from the repository root, TRUDLC_SYM_EXTRA set as for the conversion):
  ../bin/pyt -t 600 tools/script_symbol_pairs.py PORT.drm SCRIPT_ID XBOX XBOX_ID CONTROL.drm CONTROL_ID XBOX_CONTROL XBOX_CONTROL_ID [--fix OUT.drm]
"""
import sys, os, ast, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import script_port_consistency as SPC


def nodepth(kind):
    """init label string -> (base type, offset, userType) without the depth"""
    if not kind.startswith("('init'"): return kind
    lab = ast.literal_eval(kind)
    return str((lab[1], lab[3], lab[4]))


def pair_map(ids, xw):
    """Xbox big-endian word (bytes) -> PC little-endian bytes with both u16 halves mapped in place"""
    a, b = struct.unpack('>HH', xw)
    pa, pb = ids.sym(a) if a else 0, ids.sym(b) if b else 0
    if pa > 0xffff or pb > 0xffff: return None          # no u16 Symbol (a float, a colour ...)
    return struct.pack('<HH', pa, pb)


def main(argv):
    out = None
    if '--fix' in argv: k = argv.index('--fix'); out = argv[k + 1]; del argv[k:k + 2]
    if len(argv) != 8: sys.exit(__doc__)
    import dlc_generic as DG
    ids = DG.DlcIds()
    print('symbol map: %s' % ids.sym_info)
    T = SPC.words(argv[0], int(argv[1]), argv[2], int(argv[3]))
    C = SPC.words(argv[4], int(argv[5]), argv[6], int(argv[7]))
    seen = collections.Counter(); ok = collections.Counter(); deepest = {}
    for kind, xw, pw in C.values():
        if not kind.startswith("('init'"): continue
        if xw == b'\0\0\0\0': continue
        lab = ast.literal_eval(kind)
        deepest[nodepth(kind)] = max(deepest.get(nodepth(kind), 0), lab[2])     # deepest non-zero level
        seen[kind] += 1
        if pw == pair_map(ids, xw): ok[kind] += 1
    # a kind: all its control words pair-mapped and at least 3 of them, or (fewer) the next level of a chain whose
    # shallower level is a kind (the control has single pair words at depths 5 / 6 below the 16 + 3 of depths 3 / 4)
    kinds = set()
    for k in sorted(seen, key=lambda q: ast.literal_eval(q)[2]):
        lab = ast.literal_eval(k)
        up = str(lab[:2] + (lab[2] - 1,) + lab[3:])
        if ok[k] == seen[k] and (seen[k] >= 3 or up in kinds): kinds.add(k)
    print('Symbol pair kinds (control: every non-zero word = pair map): %s' % ', '.join(
        '%s x%d' % (k, seen[k]) for k in sorted(kinds)))
    near = [(k, ok[k], seen[k]) for k in seen if 0 < ok[k] < seen[k]]
    if near: print('kinds with pair-mapped words and exceptions (not used): %s' % near)
    # a chain deeper than the control's deepest level of a (base type, offset, userType) continues that level's kind
    deeper = set()
    for k in kinds:
        lab = ast.literal_eval(k)
        if lab[2] == deepest.get(nodepth(k)): deeper.add(nodepth(k))
    if deeper: print('extended to deeper title-update levels: %s (control deepest levels %s)' % (
        sorted(deeper), {k: deepest[k] for k in sorted(deeper)}))
    fixes = []; st = collections.Counter()
    for o, (kind, xw, pw) in sorted(T.items()):
        if not kind.startswith("('init'") or xw == b'\0\0\0\0': continue
        lab = ast.literal_eval(kind)
        if kind not in kinds and not (nodepth(kind) in deeper and lab[2] > deepest[nodepth(kind)]): continue
        want = pair_map(ids, xw)
        if pw == want: st['pair-mapped'] += 1; continue
        st['not pair-mapped'] += 1; fixes.append((o, kind, xw, pw, want))
    print('port: %s' % dict(st))
    for o, kind, xw, pw, want in fixes:
        print('  +%#06x %s Xbox %s port %s -> %s' % (o, kind, xw.hex(), pw.hex(), want.hex()))
    if out:
        raw = open(argv[0], 'rb').read(); D = DW.read(raw, 'le')
        s = next(x for x in D.sections if x.type == 8 and x.id == int(argv[1]))
        d = bytearray(s.data)
        for o, kind, xw, pw, want in fixes: d[o:o + 4] = want
        s.data = bytes(d)
        o = D.write('le')
        if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        open(out, 'wb').write(o)
        print('%d words set -> %s' % (len(fixes), out))


if __name__ == '__main__':
    main(sys.argv[1:])
