"""Shader form gate (2026-11-08, stage 2 of the AMD plan): counts, in every shader library of one or more mods-style
trees, the pixel / vertex shader forms that Windows' own Direct3D 9 or a GPU driver refuses, and fails a build or an
install on them when enforced. Read-only.

Hard forms (port shaders only; shaders whose md5 is a PC game shader are counted apart and never fail the gate):
  ABS_CONST    abs / -abs source modifier on a constant register (`cmp r0, -|c221|, ...`): the AMD driver refused it on
               20 Oct 2026 (NVIDIA accepts it)
  SINCOS_SAME  sincos whose destination is also its source (D3DX9 X5767)
  X5584        one instruction reads two or more DIFFERENT constant registers (D3DX9 X5584; B138 failed on a real GPU
               with it on 30 Oct 2026, finding 43)
  ERR          a ps_3_0 / vs_3_0 rule broken (tools/native_test/sm3check.py)
Warnings (never fail the gate): NEW_FORM (an opcode / register / modifier combination the 5000+ PC game shaders never
use, tools/native_test/pc_features.txt), LONG (more than 512 instruction slots).

The classification is the one of tools/native_test/native_extract.py (analyze) plus the X5584 count of
tools/shader_const_count.py (distinct constant registers among the plain sources of one instruction).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/shader_form_gate.py check TREE [TREE ...] [--enforce] [--list N] [--report FILE.json]
  ../bin/pyt tools/shader_form_gate.py selftest
  check     every *.drm below each TREE; a TREE may also be one .drm file
  --enforce exit 1 when a port shader carries a hard form (without it the gate only reports "would fail", exit 0)
  --list N  print the first N affected port shaders per hard form (library, slot, DRM, first instruction)
  --report  write the counts and the affected shaders as JSON
Exit code: 0 = pass (or not enforced), 1 = enforced and a hard form found, 2 = a tree or DRM could not be read.
"""
import collections, hashlib, json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
NT = os.path.join(HERE, 'native_test')
sys.path.insert(0, NT)
import native_extract as NE   # noqa: E402
import sm3check as S          # noqa: E402

HARD = ('ABS_CONST', 'SINCOS_SAME', 'X5584', 'ERR')
WARN = ('NEW_FORM', 'LONG')


def x5584_count(items):
    """instructions that read two or more distinct constant registers (rt 2) as plain sources (relative ones excluded)"""
    n = 0
    for x in items:
        if x.op in ('dcl', 'def', 'defi', 'defb'): continue
        consts = set(s.num for s in x.src if s.rt == 2 and not s.rel)
        if len(consts) > 1: n += 1
    return n


def classify(code, pc_feats):
    """-> (set of forms, first suspicious instruction text)"""
    r = NE.analyze(code, pc_feats)
    forms = set(r['findings'])
    first = r['first']
    kind, ver, items, errs, info = S.decode(code)
    if x5584_count(items):
        forms.add('X5584')
        if not first:
            for x in items:
                if x5584_count([x]): first = 'instr %d: %s' % (x.idx, NE.ins_text(x)); break
    return forms, first


def drm_files(tree):
    if os.path.isfile(tree): yield tree, os.path.basename(tree); return
    for dp, dn, fn in os.walk(tree):
        dn.sort()
        for f in sorted(fn):
            if f.lower().endswith('.drm'):
                p = os.path.join(dp, f)
                yield p, os.path.relpath(p, tree).replace('\\', '/')


def load_tables():
    pcm, pcf = set(), set()
    p = os.path.join(NT, 'pc_shader_md5.txt')
    if os.path.isfile(p): pcm = set(open(p).read().split())
    p = os.path.join(NT, 'pc_features.txt')
    if os.path.isfile(p): pcf = set(open(p).read().splitlines())
    return pcm, pcf


def scan_tree(tree, pcm, pcf, cache):
    """-> dict with counts per form (unique port shaders), PC-shader counts, affected list, unreadable DRMs"""
    res = dict(tree=tree, drms=0, unreadable=[], unique_port=0, unique_pc=0, port=collections.Counter(),
               pc=collections.Counter(), affected=collections.defaultdict(list))
    seen = set()
    for p, rel in drm_files(tree):
        res['drms'] += 1
        try:
            raw = NE.cdrm_decode(open(p, 'rb').read())
            secs = list(NE.sections(raw))
        except Exception as e:
            res['unreadable'].append('%s: %r' % (rel, e)); continue
        for typ, sid, data in secs:
            if typ != 9 or len(data) < 12: continue
            try: blobs = list(NE.lib_blobs(data))
            except Exception as e:
                res['unreadable'].append('%s lib %d: %r' % (rel, sid, e)); continue
            for slot, code in blobs:
                md = hashlib.md5(code).hexdigest()
                if md not in cache: cache[md] = classify(code, pcf)
                forms, first = cache[md]
                ispc = md in pcm
                if md not in seen:
                    seen.add(md)
                    if ispc: res['unique_pc'] += 1
                    else: res['unique_port'] += 1
                    for f in forms: (res['pc'] if ispc else res['port'])[f] += 1
                if ispc: continue
                for f in forms:
                    if f in HARD:
                        res['affected'][f].append(dict(drm=rel, lib=sid, slot=slot, md5=md[:8], first=first))
    return res


def cmd_check(argv):
    enforce = '--enforce' in argv
    lst = int(argv[argv.index('--list') + 1]) if '--list' in argv else 0
    report = argv[argv.index('--report') + 1] if '--report' in argv else None
    skip = set()
    for opt in ('--list', '--report'):
        if opt in argv: skip.add(argv.index(opt) + 1)
    trees = [a for i, a in enumerate(argv) if not a.startswith('--') and i not in skip]
    if not trees: print(__doc__); return 2
    pcm, pcf = load_tables()
    print('shader_form_gate: PC reference tables %s (%d md5, %d forms); enforce=%s'
          % ('yes' if pcm and pcf else 'MISSING', len(pcm), len(pcf), enforce))
    cache = {}; out = []; hard_total = 0; bad = False
    for t in trees:
        if not os.path.exists(t):
            print('tree %s: not found' % t); bad = True; continue
        r = scan_tree(t, pcm, pcf, cache)
        hard = {f: r['port'][f] for f in HARD}
        hard_total += sum(hard.values())
        print('tree %s: %d DRMs, unique shaders port %d / PC %d' % (t, r['drms'], r['unique_port'], r['unique_pc']))
        print('  hard (unique port shaders): ' + ', '.join('%s %d' % (f, hard[f]) for f in HARD))
        print('  warnings: ' + ', '.join('%s %d' % (f, r['port'][f]) for f in WARN)
              + '; PC game shaders with a hard form: %d (never fail)' % sum(r['pc'][f] for f in HARD))
        for f in HARD:
            if not r['affected'][f]: continue
            libs = sorted(set(a['lib'] for a in r['affected'][f]))
            print('  %s in %d entries, libraries %s' % (f, len(r['affected'][f]), ' '.join(str(x) for x in libs[:40])
                                                         + (' ...' if len(libs) > 40 else '')))
            for a in r['affected'][f][:lst]:
                print('    %s lib %d slot %d %s | %s' % (a['drm'], a['lib'], a['slot'], a['md5'], a['first']))
        if r['unreadable']:
            bad = True
            print('  unreadable: %d (first: %s)' % (len(r['unreadable']), r['unreadable'][0]))
        out.append(dict(tree=t, drms=r['drms'], unique_port=r['unique_port'], unique_pc=r['unique_pc'],
                        port=dict(r['port']), pc=dict(r['pc']), unreadable=r['unreadable'],
                        affected={f: v for f, v in r['affected'].items()}))
    verdict = 'PASS' if not hard_total else ('FAIL' if enforce else 'WOULD FAIL (not enforced)')
    print('gate: %s - %d hard-form port shaders over %d tree(s)' % (verdict, hard_total, len(trees)))
    if report:
        with open(report, 'w', encoding='utf-8') as fo:
            json.dump(dict(gate=verdict, enforce=enforce, hard_total=hard_total, trees=out), fo, indent=1)
        print('report: %s' % report)
    if bad: return 2
    return 1 if (enforce and hard_total) else 0


# ------------------------------------------------------------------ selftest (synthetic ps_3_0 token streams)
def _ps(*instr):
    toks = [0xFFFF0300]
    for ins in instr: toks += ins
    toks.append(0x0000FFFF)
    return struct.pack('<%dI' % len(toks), *toks)


R0_DST = 0x800F0000                     # r0.xyzw
OC0_DST = 0x800F0800                    # oC0.xyzw (register type 8)
def _c(n, smod=0): return 0xA0E40000 | (smod << 24) | n     # cN.xyzw, source modifier smod (11 abs, 12 -abs)
def _r(n, swz=0xE4): return 0x80000000 | (swz << 16) | n
MOV = 0x02000001; ADD = 0x03000002; CMP = 0x04000058; SINCOS = 0x02000025


def cmd_selftest():
    pcm, pcf = load_tables()
    cases = [
        ('clean mov oC0, c0', _ps([MOV, OC0_DST, _c(0)]), set()),
        ('X5584 add r0, c0, c1', _ps([ADD, R0_DST, _c(0), _c(1)], [MOV, OC0_DST, _r(0)]), {'X5584'}),
        ('same constant twice is fine', _ps([ADD, R0_DST, _c(3), _c(3)], [MOV, OC0_DST, _r(0)]), set()),
        ('ABS_CONST cmp r0, -|c221|, r1, r1', _ps([CMP, R0_DST, _c(221, 12), _r(1), _r(1)], [MOV, OC0_DST, _r(0)]),
         {'ABS_CONST'}),
        ('SINCOS_SAME sincos r0.xy, r0.x', _ps([SINCOS, 0x80030000, _r(0, 0x00)], [MOV, OC0_DST, _r(0)]),
         {'SINCOS_SAME'}),
    ]
    fails = 0
    for name, code, want in cases:
        got, first = classify(code, pcf)
        got_h = set(f for f in got if f in HARD)
        ok = got_h == want
        fails += not ok
        print('%-4s %-38s hard %s (want %s)%s' % ('ok' if ok else 'FAIL', name, sorted(got_h) or '-', sorted(want) or '-',
                                               '' if ok else ' | ' + first))
    probe = os.path.join(NT, 'probes', 'feat_ps_cmp_absnegmod.bin')
    if os.path.isfile(probe):
        got, _ = classify(open(probe, 'rb').read(), pcf)
        ok = 'ABS_CONST' in got
        fails += not ok
        print('%-4s %-38s hard %s (want ABS_CONST)' % ('ok' if ok else 'FAIL', 'probe feat_ps_cmp_absnegmod.bin',
                                                         sorted(f for f in got if f in HARD) or '-'))
    print('selftest: %d / %d ok' % (len(cases) + 1 - fails, len(cases) + 1))
    return 1 if fails else 0


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(2)
    if a[0] == 'selftest': sys.exit(cmd_selftest())
    if a[0] == 'check': sys.exit(cmd_check(a[1:]))
    print(__doc__); sys.exit(2)
