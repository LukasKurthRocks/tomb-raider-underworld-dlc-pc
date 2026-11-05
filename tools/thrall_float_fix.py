"""Thrall object data: floats the DLC converter wrote as u16 pairs / left raw - find them, prove the field type on the
genuine base-game pair and repair only the proven words (typed fix step like tools/objdata_fx_fix.py; finisher /
thrall analysis 2026-11-05, docs Befund-Testfragen-0511.md section 2).

Candidates: every word of the object DTP that is no pointer / id slot, whose Xbox big-endian value is a plausible float
(finite, 1e-3 <= |v| <= 1e7, not a small-integer / u16 -1 bit pattern) and whose PC bytes are NOT the byte-reversed
Xbox bytes.

Proof on the genuine base game (Xbox original from layer1 / layer2 / title update, genuine PC file from bigfile /
patch, read-only): the twin field = the word at the same place of the same data in a base DTP, found by a window
alignment: the 12 words before and after the candidate (non-zero, no pointers / ids) vote with every equal Xbox word
of a base DTP for an offset shift; a shift with at least 4 votes and at least MATCH (default 60 %) of the window words
is a twin (the record arrays are permuted between objects and records are split by inner pointers, so neither a
pointer path nor a block match is enough - armored yeti vs. yeti). Only the best alignments are kept (score >= best
- 15 points). Second source: the record's shortest pointer path from the DTP start, followed in the base DTP, used only
when the twin word there is the SAME Xbox word (records at the end of the DTP without a matching window). The twin
field is evidence:
  byte-reversed in the genuine PC file and a plausible Xbox float  -> float (u32)
  halves reversed (u16 pair) / unchanged, not symmetric             -> not a float
  symmetric word (0, 0xffffffff, ...)                               -> no evidence
Verdicts: FLOAT (only float evidence - repaired: PC := byte-reversed Xbox bytes), NOT-FLOAT (only non-float evidence -
left alone), CONFLICT (both - left alone), UNPROVEN (no twin record / no evidence - left alone, reported).
Only the DTP's data words change; relocations, sizes and every other section stay as they are (checked on read-back).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/thrall_float_fix.py XBOX_NAME PC.drm DTP BASE[,BASE..] [--out FIXED.drm] [--all] [--match P]
    XBOX_NAME  DLC DRM name in the Xbox archives (e.g. yeti_thrall_dlc2_) or an Xbox file
    PC.drm     converted PC file (the base the packages install last)
    BASE       base-game objects to take twin records from (e.g. yeti_thrall,yeti_thrall_yggdrasil,viking_thrall)
    --all      print the NOT-FLOAT / UNPROVEN candidates too (default: counts + FLOAT / CONFLICT lines)
    --match P  minimum share of agreeing non-zero record words (default 0.6)
Exit code: 0 ok, 3 nothing to repair, 2 usage / input error.
"""
import sys, os, struct, math, hashlib, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import drm_write as DW
import tuning_word_audit as TA
import dtp_twin_field as TW


WIN = 12          # words before / after the field that vote for the twin alignment
MINVOTES = 4      # at least this many agreeing words (and at least --match of the window)


def plaus(b):
    v = struct.unpack('>f', b)[0]
    if not math.isfinite(v) or v == 0: return False
    u = struct.unpack('>I', b)[0]
    if u < 0x01000000 or (u & 0xffff) == 0xffff: return False
    return 1e-3 <= abs(v) <= 1e7


def cls(xw, pw):
    if xw[::-1] == pw: return 'u32'
    if xw[1::-1] + xw[:1:-1] == pw: return 'u16pair'
    if xw == pw: return 'raw'
    return 'other'


def fv(b, e):
    v = struct.unpack(e + 'f', b)[0]
    return '%.6g' % v if math.isfinite(v) else 'nan'


def block_list(internal, size):
    t = sorted(set(internal.values()) | {0})
    return t, [(a, (t[i + 1] if i + 1 < len(t) else size) - a) for i, a in enumerate(t)]


def main(argv):
    if len(argv) < 4: print(__doc__); return 2
    out = argv[argv.index('--out') + 1] if '--out' in argv else None
    show_all = '--all' in argv
    match = float(argv[argv.index('--match') + 1]) if '--match' in argv else 0.6
    xname, pcfile, sid, bases = argv[0], argv[1], int(argv[2]), argv[3].split(',')
    xsecs, xsrc = TA.load_x(xname)
    praw = open(pcfile, 'rb').read()
    psecs = TA.load_p(pcfile)
    sx, sp = TW.blocks(xsecs, sid), TW.blocks(psecs, sid)
    if not sx or not sp: print('DTP %d missing (Xbox %s, PC %s)' % (sid, bool(sx), bool(sp))); return 2
    xd, pd = bytes(sx['data']), bytes(sp['data'])
    rlx, rlp = R.parse(bytes(sx['reloc']), 'be'), R.parse(bytes(sp['reloc']), 'le')
    ix, ip = dict(rlx.internal), dict(rlp.internal)
    if len(xd) != len(pd) or ix != ip:
        print('DTP %d: Xbox / PC layout differs - stop' % sid); return 2
    skip = set(rlp.pointer_offsets()) | set(rlp.id_offsets()) | set(rlx.pointer_offsets()) | set(rlx.id_offsets())
    print('DLC %s (Xbox %s) DTP %d 0x%x bytes; PC %s md5 %s; match >= %.0f %%' % (
        xname, xsrc, sid, len(xd), pcfile, hashlib.md5(praw).hexdigest(), 100 * match))
    targets, _ = block_list(ip, len(pd))

    def block_of(o):
        b = targets[bisect.bisect_right(targets, o) - 1]
        k = bisect.bisect_right(targets, o)
        return b, (targets[k] if k < len(targets) else len(pd)) - b
    # shortest root-first pointer path (block-relative pointer field offsets) of every block, BFS from the DTP start
    by_block = {}
    for src_o, tg in ip.items(): by_block.setdefault(block_of(src_o)[0], []).append((src_o, tg))
    paths, queue = {0: []}, [0]
    while queue:
        bb = queue.pop(0)
        for src_o, tg in sorted(by_block.get(bb, [])):
            if tg not in paths:
                paths[tg] = paths[bb] + [src_o - bb]
                queue.append(tg)
    # base twin DTPs: Xbox / PC paired by id, else by size + the same internal pointers; blocks by size
    twins = []
    for bname in bases:
        bx, bxsrc = TW.load_named(bname, ('tu', 'xbase2', 'xbase'), 'be')
        bp, bpsrc = TW.load_named(bname, ('pcpatch', 'pcbig'), 'le')
        if not bx or not bp: print('base %s not found (Xbox %s, PC %s)' % (bname, bxsrc, bpsrc)); return 2
        bpd = {s['id']: s for s in bp if s['type'] == 7}
        n = 0
        for s in bx:
            if s['type'] != 7: continue
            rxl = R.parse(bytes(s['reloc']), 'be')
            rx = dict(rxl.internal)
            c = [bpd[s['id']]] if s['id'] in bpd else [t for t in bpd.values() if len(t['data']) == len(s['data']) and
                                                        dict(R.parse(bytes(t['reloc']), 'le').internal) == rx]
            if len(c) != 1 or len(c[0]['data']) != len(s['data']): continue
            if dict(R.parse(bytes(c[0]['reloc']), 'le').internal) != rx: continue
            txd = bytes(s['data'])
            s['_rx'] = rx
            c[0]['_rp'] = dict(R.parse(bytes(c[0]['reloc']), 'le').internal)
            tskip = set(rxl.pointer_offsets()) | set(rxl.id_offsets())
            index = {}
            for a in range(0, len(txd) // 4 * 4, 4):
                w = txd[a:a + 4]
                if a in tskip or w == b'\0\0\0\0': continue
                index.setdefault(w, []).append(a)
            twins.append((bname, s, c[0], tskip, index))
            n += 1
        print('base %s: Xbox %s, PC %s, %d paired DTPs' % (bname, bxsrc, bpsrc, n))
    cands = []
    for o in range(0, len(xd) // 4 * 4, 4):
        if o in skip: continue
        xw, pw = xd[o:o + 4], pd[o:o + 4]
        if xw[::-1] == pw or not plaus(xw): continue
        cands.append(o)
    print('%d candidate words (plausible Xbox float, PC not byte-reversed)' % len(cands))
    fix = bytearray(pd)
    counts = {'FLOAT': 0, 'NOT-FLOAT': 0, 'CONFLICT': 0, 'UNPROVEN': 0}
    rec_cache = {}
    for o in cands:
        xw, pw = xd[o:o + 4], pd[o:o + 4]
        b, ln = block_of(o)
        # window of WIN words before / after the field (no pointers / ids, no zero words, not the field itself);
        # every equal Xbox word of a twin DTP votes for an alignment (twin offset - DLC offset)
        words = [(k, xd[k:k + 4]) for k in range(max(0, o - 4 * WIN), min(len(xd), o + 4 * WIN + 4), 4)
                 if k != o and k not in skip and xd[k:k + 4] != b'\0\0\0\0']
        nwords = len(words)
        found = []
        for bname, tx, tp, tskip, index in twins:
            votes = {}
            for k, w in words:
                for a in index.get(w, ()):
                    votes[a - k] = votes.get(a - k, 0) + 1
            for shift, v in votes.items():
                if nwords and v >= max(MINVOTES, match * nwords) and 0 <= o + shift < len(tx['data']) - 3:
                    found.append((v / nwords, bname, tx, tp, tskip, o + shift))
        found.sort(key=lambda f: -f[0])
        if found:                         # repeated record patterns give several alignments: keep the best ones only
            best = found[0][0]
            found = [f for f in found if f[0] >= best - 0.15]
        # second source: the root-first pointer path of the record, followed in the base DTPs; used only when the twin
        # word there is the SAME Xbox word (a different value at the end of a path is no proof of the same field)
        chain = paths.get(b)
        if chain is not None:
            for bname, tx, tp, tskip, index in twins:
                rx = tx['_rx']; rp = tp['_rp']
                cur, ok = 0, True
                for fo in chain:
                    a = cur + fo
                    if a not in rx or a not in rp or rx[a] != rp[a]: ok = False; break
                    cur = rx[a]
                t = cur + (o - b)
                if ok and t + 4 <= len(tx['data']) and bytes(tx['data'][t:t + 4]) == xw and t not in tskip:
                    found.append((-1.0, bname, tx, tp, tskip, t))
        yes, no, none = [], [], []
        for score, bname, tx, tp, tskip, t in found:
            a = t - (o - b)
            if t in tskip: continue
            twx, twp = bytes(tx['data'][t:t + 4]), bytes(tp['data'][t:t + 4])
            c = cls(twx, twp)
            how = ('pointer path %s:%x' % (','.join('%x' % p for p in chain), o - b)) if score < 0 else \
                  ('window: %.0f %% of %d words agree' % (100 * score, nwords))
            desc = '%s Xbox DTP %d / PC DTP %d +0x%x (%s): Xbox %s (f %s) PC %s %s%s' % (
                bname, tx['id'], tp['id'], t, how, twx.hex(), fv(twx, '>'), twp.hex(), c,
                ', same Xbox value' if twx == xw else '')
            if twx == twx[::-1]: none.append(desc + ' (symmetric: no evidence)')
            elif c == 'u32' and plaus(twx): yes.append(desc)
            elif c in ('u16pair', 'raw'): no.append(desc)
            else: none.append(desc + ' (no evidence)')
        if yes and no: verdict, why = 'CONFLICT', yes[0] + ' || ' + no[0]
        elif yes: verdict, why = 'FLOAT', yes[0] + ('' if len(yes) == 1 else ' (+%d more twin record(s) agree)' % (len(yes) - 1))
        elif no: verdict, why = 'NOT-FLOAT', no[0] + ('' if len(no) == 1 else ' (+%d more)' % (len(no) - 1))
        elif none: verdict, why = 'UNPROVEN', none[0] + ('' if len(none) == 1 else ' (+%d more)' % (len(none) - 1))
        else: verdict, why = 'UNPROVEN', 'record +0x%x (0x%x bytes, %d words): no twin record in the base objects' % (b, ln, nwords)
        counts[verdict] += 1
        if verdict == 'FLOAT': fix[o:o + 4] = xw[::-1]
        if verdict in ('FLOAT', 'CONFLICT') or show_all:
            print('%-9s +0x%04x (record +0x%x field +0x%x) Xbox %s (f %s) PC %s (f %s, %s) -> %s | %s' % (
                verdict, o, b, o - b, xw.hex(), fv(xw, '>'), pw.hex(), fv(pw, '<'), cls(xw, pw),
                xw[::-1].hex() if verdict == 'FLOAT' else 'unchanged', why))
    print('verdicts: %s' % ', '.join('%s %d' % kv for kv in counts.items()))
    changed = [o for o in range(0, len(pd), 4) if fix[o:o + 4] != pd[o:o + 4]]
    print('words to repair: %d (%s)' % (len(changed), ', '.join('+0x%x' % o for o in changed)))
    if not out:
        return 0 if changed else 3
    if not changed:
        print('nothing to repair - no file written'); return 3
    D = DW.read(praw, 'le')
    k = [i for i, s in enumerate(D.sections) if s.type == 7 and s.id == sid]
    if len(k) != 1: print('DTP %d not unique in the PC file' % sid); return 2
    s = D.sections[k[0]]
    D.sections[k[0]] = DW.Section(s.type, s.id, bytes(fix), s.reloc, s.flags, s.ver, s.spec, s.pad)
    raw = D.write('le')
    if praw[:4] == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(raw)
    D0, D1 = DW.read(praw, 'le'), DW.read(open(out, 'rb').read(), 'le')
    diff_secs = [y.id for x, y in zip(D0.sections, D1.sections) if (x.type, x.id, x.data, x.reloc) != (y.type, y.id, y.data, y.reloc)]
    assert len(D0.sections) == len(D1.sections) and diff_secs == [sid], diff_secs
    d1 = bytes(D1.sections[k[0]].data)
    diff_words = [o for o in range(0, len(pd), 4) if d1[o:o + 4] != pd[o:o + 4]]
    assert diff_words == changed, (diff_words, changed)
    for o in changed: assert d1[o:o + 4] == xd[o:o + 4][::-1]
    data = open(out, 'rb').read()
    print('wrote %s md5 %s sha256 %s: sections changed %s, %d words of DTP %d differ from the input, each = Xbox '
          'byte-reversed, readback ok' % (out, hashlib.md5(data).hexdigest(), hashlib.sha256(data).hexdigest(),
                                         diff_secs, len(diff_words), sid))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
