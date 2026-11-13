r"""DLC 1 start path gate (P4.1, 2026-11-13, workspace docs Befund-DLC1-Startwarp-1311.md / Befund-P4s-Pipeline-1311.md).

Why: the retired converter rule CINE_SKIP (tools/dlc_generic.py, 2026-10-09 .. 2026-11-13) bent the op 0x6a virtual call of
the dlc_level1_start unit script 20068 (state-1 Run, call at +0x6c0, external relocation source +0x6c4) from the
Cinematic_Object 3523 Prototype +0x2410 (vtIndex 57 = PlayCinematic; Xbox: class 941 +0x2410) to the 23175 Prototype
+0x5f8 (vtIndex 61 = the cine-end handler 'warping lara to dlc_caverns checkpoint90001'). On PC today the intro cinematic
plays; with the skip the warp comes while Lara is still in the fall state -> she slides ~280 units down -> the game
reloads the checkpoint every ~6 s (live 13.11., 42 SAVE_RestoreGame in 4 min).

Gate: in <tree>/dlc_level1_start.drm, script 20068 has 'op 0x6a' at +0x6c0 and its relocation +0x6c4 points into
section (8, 3523) at a Prototype whose class word is 3523 and whose vtIndex (u16 at +6) is 57.
  check TREE[,TREE..] [--optional] [--report R.json]
        exit 1 when a tree's dlc_level1_start.drm has another target (e.g. the CINE_SKIP form 23175 +0x5f8) or the file
        is missing (unless --optional, for trees without DLC 1); the first tree that holds the file is judged.
  restore SRC.drm OUT.drm
        writes SRC with only that relocation set back to 3523 +0x2410 (refuses anything but the CINE_SKIP form); the
        same function dlc_patch.py fix 'cine_play' uses for already converted trees.
Usage (from the repository root): ../bin/pyt -t 300 tools/cine_call_gate.py check work/rebuild/asm_stage2b/mods
"""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

FILE = 'dlc_level1_start.drm'
SCRIPT = 20068          # PC id = Xbox id (DLC-new unit script)
SRC = 0x6c4             # relocation source; the op word sits at SRC - 4
OP = bytes.fromhex('0000006a')      # LE op word as stored in the converted script (0x6a000000)
GOOD = (3523, 0x2410, 57)           # Cinematic_Object Prototype, vtIndex 57 PlayCinematic (Xbox 941 +0x2410)
SKIP = (23175, 0x5f8, 61)           # the retired CINE_SKIP target (cine-end / warp handler)


def _proto(sec, do):
    """(class word, vtIndex) of the Prototype at sec.data + do, or None"""
    d = sec.data
    if d is None or do + 8 > len(d): return None
    return struct.unpack_from('<I', d, do)[0], struct.unpack_from('<H', d, do + 6)[0]


def probe(D):
    """dict: state 'ok' / 'cine_skip' / 'other' / 'no_script' / 'no_call', target, proto"""
    S = D.sections
    k = next((i for i, q in enumerate(S) if q.type == 8 and q.id == SCRIPT), None)
    if k is None: return dict(state='no_script')
    s = S[k]
    if s.data[SRC - 4:SRC] != OP: return dict(state='no_call', op=s.data[SRC - 4:SRC].hex())
    e = [(si, so, do) for si, so, do in R.parse(s.reloc, 'le').external if so == SRC]
    if len(e) != 1: return dict(state='no_call', relocs=len(e))
    si, _, do = e[0]
    t = S[si]; pr = _proto(t, do)
    res = dict(target=[t.type, t.id, hex(do)], proto=list(pr) if pr else None)
    if t.type == 8 and (t.id, do) == GOOD[:2] and pr == (GOOD[0], GOOD[2]): res['state'] = 'ok'
    elif t.type == 8 and (t.id, do) == SKIP[:2]: res['state'] = 'cine_skip'
    else: res['state'] = 'other'
    return res


def restore(D):
    """retarget the CINE_SKIP form back to 3523 +0x2410 in place; returns True if changed (False if already ok);
    raises ValueError on any other form"""
    st = probe(D)
    if st['state'] == 'ok': return False
    if st['state'] != 'cine_skip': raise ValueError('20068 +0x%x: not the CINE_SKIP form: %r' % (SRC, st))
    S = D.sections
    k = next(i for i, q in enumerate(S) if q.type == 8 and q.id == SCRIPT)
    j = next((i for i, q in enumerate(S) if q.type == 8 and q.id == GOOD[0]), None)
    if j is None or _proto(S[j], GOOD[1]) != (GOOD[0], GOOD[2]):
        raise ValueError('section (8, %d) +0x%x is not the vtIndex-%d Prototype' % GOOD)
    r = R.parse(S[k].reloc, 'le')
    r.external = [(j, so, GOOD[1]) if so == SRC else (si, so, do) for si, so, do in r.external]
    S[k].reloc = R.write(r, 'le')
    return True


def check(trees, optional, report):
    rows = []; bad = 0
    for tree in trees:
        p = os.path.join(tree, FILE)
        if not os.path.isfile(p):
            rows.append(dict(tree=tree, state='missing'))
            continue
        st = probe(DW.read(open(p, 'rb').read(), 'le'))
        st.update(tree=tree, file=p); rows.append(st)
        break
    judged = next((r for r in rows if r['state'] != 'missing'), None)
    if judged is None:
        verdict = 'skip' if optional else 'FAIL'
        print('%s: no %s in %s' % (verdict, FILE, ', '.join(trees)))
        bad = 0 if optional else 1
    else:
        ok = judged['state'] == 'ok'
        bad = 0 if ok else 1
        print('%s: %s script %d +0x%x -> %s proto %s (%s)' % ('ok' if ok else 'FAIL', judged['file'], SCRIPT, SRC,
              judged.get('target'), judged.get('proto'), judged['state']))
        if judged['state'] == 'cine_skip':
            print('  the retired CINE_SKIP form (23175 +0x5f8 = warp handler): DLC 1 start reload loop; '
                  'fix: dlc_patch.py --only=cine_play or tools/cine_call_gate.py restore')
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        json.dump(dict(gate='cine_call', expect=dict(section=[8, GOOD[0]], offset=hex(GOOD[1]), vtIndex=GOOD[2]),
                       rows=rows, exit=bad), open(report, 'w', encoding='utf-8'), indent=1)
    return bad


def main(a):
    if not a: sys.exit(__doc__)
    report = None
    if '--report' in a:
        k = a.index('--report'); report = a[k + 1]; del a[k:k + 2]
    optional = '--optional' in a
    a = [x for x in a if x != '--optional']
    if a[0] == 'check' and len(a) == 2:
        return check(a[1].split(','), optional, report)
    if a[0] == 'restore' and len(a) == 3:
        src, dst = a[1], a[2]
        if os.path.abspath(src) == os.path.abspath(dst): sys.exit('refusing to overwrite the source')
        raw = open(src, 'rb').read()
        D = DW.read(raw, 'le')
        if not restore(D): print('already ok, nothing written'); return 0
        data = D.write('le')
        if raw[:4] == b'CDRM': data = DW.cdrm_encode(data, 'le')
        os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
        open(dst, 'wb').write(data)
        print('written', dst, len(data), 'bytes; %d +0x%x -> (8,%d)+0x%x' % (SCRIPT, SRC, GOOD[0], GOOD[1]))
        return 0
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
