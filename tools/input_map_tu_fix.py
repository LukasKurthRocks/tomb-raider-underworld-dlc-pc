"""Add the title update's input bindings to the PC generalbank input map (data translation, writes only OUT;
shadow combat night 2026-11-04, docs/Befund-Schattenkampf.md "Nacht 04.11.: Angriffs-Anforderung 152").

Finding: Lara's chart conditions 150 / 151 / 152 / 153 test bit 4 / not 4 / 0x10 / 0x20 of input action record
<value> (PC tru+0x360b50 / +0x360bc0 / +0x360c40 / +0x360cb0, TU 0x82466890 / 0x82466968 / 0x82466a40 / 0x82466b18,
same code). The records belong to the action map of GlobalInfo +0x1c (generalbank: PC DTP 47, Xbox DTP 48). The
Xbox TU's DTP 48 has 6 bindings more than retail - all in set 17 (Lara): action 141 <- source 32, 142 <- 3, 143 <- 2,
145 <- 33, 146 <- 2, 147 <- 3. The PC map (PC-authored, 167 bindings, 63 sources) has none of them, so records
142 / 143 / 147 (the DLC 2 chart's attack requests {150,152,142/143/147}) and 141 / 145 (the TU shadow-power
buttons) stay at their default 8 (= up, tru+0x80a50) whatever the pad does.

What the tool does (every value read from the files, nothing typed in):
  1. TU-only bindings = (tu:generalbank.drm DTP 48) minus (retail:generalbank.drm DTP 48), as bytes {action, set,
     source A, source B} (Xbox originals, big endian, read in memory order as the Xbox lbz does).
  2. Every source they use must have the same descriptor on the PC (PC DTP record k = {u8, u8, u16 code, ...} in
     little endian vs the Xbox record in big endian, all 0x18 bytes compared field by field) - else stop.
  3. None of these bindings may already be in the PC map (same 4 bytes) - else stop (already fixed).
  4. The bindings are appended after the PC's last binding (PC binding indices 0..166 stay as they are, so a PC
     key remapping that refers to a binding index is not shifted); the source records move up by 4 x n bytes, the
     internal pointer +0x0c follows, the count +0x00 grows. No other section may hold an external pointer into the map
     DTP (checked) - its id references from DTP 2 resolve by id.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/input_map_tu_fix.py IN_generalbank.drm OUT_generalbank.drm [--dtp 47] [--check] [--done-ok]
  --check   only report (no output written); exit code 0 = would change, 3 = nothing to do
  --done-ok (pipeline, idempotent) all bindings already there: copy IN to OUT unchanged, exit 0 (else exit 3)
  ../bin/pyt -t 300 tools/input_map_tu_fix.py --verify generalbank.drm [--report R.json]
            pipeline check (2026-11-04, agent N11): exit 0 = all TU bindings present, 1 = missing (nothing written)
Pipeline: tools/generalbank_build.py step 22 (after the played test-38 chain, so every generalbank built from it -
the test variants autostart / HUD / pause included - carries the bindings); tools/generalbank_hud_build.py step T10
(its base autostart_gb predates step 22, 2026-11-04 agent N15); scripts/windows/Invoke-TruPipeline.ps1
runs --verify after Generalbank / Repair.
"""
import sys, os, struct, collections, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, drm_idrefs as IR


def xbox_map(spec):
    secs, e = IR.load(spec)
    s = next(s for s in secs if s[0] == 7 and s[1] == 48)
    d = bytes(s[2]); it = dict(R.parse(bytes(s[3]), e).internal)
    n, n2 = struct.unpack_from('>I', d, 0)[0], struct.unpack_from('>I', d, 8)[0]
    binds = [bytes(d[it[4] + 4 * k:it[4] + 4 * k + 4]) for k in range(n)]
    srcs = [struct.unpack_from('>BBH5I', d, it[0xc] + 0x18 * k) for k in range(n2)]
    return binds, srcs


def main(argv):
    check = '--check' in argv; verify = '--verify' in argv; done_ok = '--done-ok' in argv
    argv = [a for a in argv if a not in ('--check', '--verify', '--done-ok')]
    dtp = 47; report = None
    if '--dtp' in argv: k = argv.index('--dtp'); dtp = int(argv[k + 1]); del argv[k:k + 2]
    if '--report' in argv: k = argv.index('--report'); report = argv[k + 1]; del argv[k:k + 2]
    if len(argv) != 2 and not ((check or verify) and len(argv) == 1): sys.exit(__doc__)
    raw = open(argv[0], 'rb').read()
    D = DW.read(raw, 'le')
    tu_b, tu_s = xbox_map('tu:generalbank.drm')
    rt_b, _ = xbox_map('retail:generalbank.drm')
    extra = list((collections.Counter(tu_b) - collections.Counter(rt_b)).elements())
    extra.sort(key=tu_b.index)                       # TU order
    print('TU-only bindings (Xbox DTP 48: TU %d, retail %d): %d' % (len(tu_b), len(rt_b), len(extra)))
    for b in extra: print('  action %d set %d source %s / %s' % (b[0], b[1], b[2], 'none' if b[3] == 0xff else b[3]))
    si = next(i for i, s in enumerate(D.sections) if s.type == 7 and s.id == dtp)
    s = D.sections[si]; d = bytearray(s.data)
    r = R.parse(bytes(s.reloc), 'le'); it = dict(r.internal)
    n, n2 = struct.unpack_from('<I', d, 0)[0], struct.unpack_from('<I', d, 8)[0]
    b0, s0 = it.get(4), it.get(0xc)
    if b0 != 0x10 or s0 != 0x10 + 4 * n or s0 + 0x18 * n2 != len(d) or sorted(it) != [4, 0xc] or r.external:
        sys.exit('PC DTP %d layout not as expected (bindings +0x%x, sources +0x%s, %d / %d, size 0x%x, relocs %r)'
                 % (dtp, b0 or 0, '%x' % s0 if s0 is not None else '-', n, n2, len(d), r))
    pc_b = [bytes(d[b0 + 4 * k:b0 + 4 * k + 4]) for k in range(n)]
    pc_s = [struct.unpack_from('<BBH5I', d, s0 + 0x18 * k) for k in range(n2)]
    print('PC DTP %d: %d bindings, %d sources, 0x%x bytes' % (dtp, n, n2, len(d)))
    for src in sorted(set(x for b in extra for x in b[2:4] if x != 0xff)):
        if src >= n2 or src >= len(tu_s) or pc_s[src] != tu_s[src]:
            sys.exit('source %d differs: PC %r, TU %r - not translated' % (src, pc_s[src] if src < n2 else None,
                                                                          tu_s[src] if src < len(tu_s) else None))
        print('  source %d: PC = TU (u8 %d, u8 0x%x, code %d, ...)' % (src, pc_s[src][0], pc_s[src][1], pc_s[src][2]))
    have = [b for b in extra if b in pc_b]
    if verify:
        res = 'ok' if len(have) == len(extra) else 'fail'
        print('verify: %d of %d TU bindings in PC DTP %d (%d bindings) - %s' % (len(have), len(extra), dtp, n,
              'ok' if res == 'ok' else 'FAIL - run tools/input_map_tu_fix.py (generalbank_build step 22)'))
        if report:
            json.dump(dict(file=argv[0], md5=hashlib.md5(raw).hexdigest(), dtp=dtp, bindings=n, tu_only=len(extra),
                           present=len(have), result=res), open(report, 'w', encoding='utf-8'), indent=1)
        sys.exit(0 if res == 'ok' else 1)
    if have and done_ok and len(have) == len(extra):
        os.makedirs(os.path.dirname(os.path.abspath(argv[1])), exist_ok=True)
        if os.path.abspath(argv[1]) != os.path.abspath(argv[0]): open(argv[1], 'wb').write(raw)
        print('already in the PC map: %d of %d - input copied unchanged (--done-ok), md5 %s' % (
            len(have), len(extra), hashlib.md5(raw).hexdigest()))
        return
    if have:
        print('already in the PC map: %d of %d - nothing written' % (len(have), len(extra)))
        sys.exit(3)
    for oi, o in enumerate(D.sections):
        if oi == si or not o.reloc: continue
        if any(t == si for t, _, _ in R.parse(bytes(o.reloc), 'le').external):
            sys.exit('section %d (type %d id %d) points into DTP %d - not changed' % (oi, o.type, o.id, dtp))
    if check:
        print('check: %d bindings would be appended (PC indices %d..%d)' % (len(extra), n, n + len(extra) - 1))
        return
    add = b''.join(extra)
    nd = bytearray(d[:s0]) + add + d[s0:]
    struct.pack_into('<I', nd, 0, n + len(extra))
    r.internal = [(o, t + len(add) if o == 0xc else t) for o, t in r.internal]
    D.sections[si] = DW.Section(s.type, s.id, bytes(nd), R.write(r, 'le'), s.flags, s.ver, s.spec, s.pad)
    out = D.write('le')
    if raw[:4] == b'CDRM': out = DW.cdrm_encode(out, 'le')
    # read back
    D2 = DW.read(out, 'le'); s2 = next(x for x in D2.sections if x.type == 7 and x.id == dtp)
    it2 = dict(R.parse(bytes(s2.reloc), 'le').internal); d2 = bytes(s2.data)
    n_new = struct.unpack_from('<I', d2, 0)[0]
    ok = (n_new == n + len(extra) and it2[0xc] == s0 + len(add) and d2[s0 + len(add):] == bytes(d[s0:])
          and d2[0x10:s0] == bytes(d[0x10:s0]) and d2[s0:s0 + len(add)] == add
          and all(a.data == b.data for a, b in zip(D.sections, D2.sections)))
    if not ok: sys.exit('read-back failed - nothing written')
    os.makedirs(os.path.dirname(os.path.abspath(argv[1])), exist_ok=True)
    open(argv[1], 'wb').write(out)
    print('written %s: DTP %d %d -> %d bindings, sources at +0x%x -> +0x%x, size 0x%x -> 0x%x; md5 %s'
          % (argv[1], dtp, n, n_new, s0, it2[0xc], len(d), len(d2), hashlib.md5(out).hexdigest()))


if __name__ == '__main__':
    main(sys.argv[1:])
