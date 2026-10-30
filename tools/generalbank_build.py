"""Build our mods\\generalbank.drm (both DLCs) reproducibly from the inputs, step by step with the existing tools
(finding 43: the loading screen, title and hint box of the title update were built by hand in DLC 2 tests 2-38).

The file = B138's generalbank with our DLC mission-screen style, plus the Xbox title update's
  * script 6 (loading screen with the DLC branch, background and intro trigger, DLC titles + descriptions) and
  * script 10 as PC script 9 (hint box: modal box with Lara icon and "press A" in DLC 2, top right elsewhere),
both converted with the DLC converter and repaired where the PC differs (tested in game up to test 38, 2026-10-30).

Steps (each tool checks the old values it replaces; intermediate files in OUT/steps/):
   1 dlc_screen_text_style   B138 kit generalbank -> mission screen in the Xbox text style (docs/DLC_MENU.md)
   2 base_convert_check      title-update generalbank converted (sections 8:6, 8:21239, 8:20082), with the base
                             evidence symbol names (TRUDLC_SYM_EXTRA=work/rebuild/sym_base_evidence.json)
   3 script_nop_call         TU script 6: call of the TU-only native uigamedata 93 removed (+0x7928)
   4 drm_put_sections        TU script 6 + 21239 + 20082 into the base (--xbox call remap, --symbols)
   5 script_vtable_insert    script 6: the PC parent's extra vtable slot 31
   6 script_init_from_pc     script 6: member init blocks from Crystal's PC script, TU-only members by learned
                             field rules, locals string ids mapped (test 38: title flag word 0 = 1 by rule)
   7 script_uitext_fix       script 6: string ids in the ported text records
   8 generalbank_dlc         TU scripts 6 + 10 converted again (script 10 -> PC script 9)
   9 drm_put_sections        script 9 + 21239 from step 8 into step 7 (--add-missing)
  10 bigfile_extract (2x)    TU and retail Xbox generalbank (templates for step 11)
  11 script_record_template  script 9: text element records from Crystal's PC conversion of retail script 10
  12 script_word_set         script 6: title records w2 = PC bit, DLC 2 title id 410 -> 432 (test 32)
  13 script_word_set         script 9: prototype count (test 35)
  14 script_vtable_insert    script 9: PC slot 31 (--ref-any)
  15 script_nop_call (5x)    script 9: the five calls of the TU-only native dlc2data
  16 script_word_set         script 9: the two f0 results as constants (test 35)
  17 script_init_from_pc     script 9: init blocks from PC / learned rules (--xbox-id 10, test 36)
  18 script_word_set         script 9: TU-only text member 17478 and the shared node +0x12e0 (test 36)
  19 script_word_set         script 9: prototype name of f9 (test 36)
  20 script_word_set         script 9: f0 constants 1 (test 36b, the played test 36)
  21 script_dlc2_flag_stub   script 9: "DLC 2 active" = current unit is a DLC 2 unit (test 37b)
The result is compared with --expect (default: the played test 38 file).

Usage (from the repository root; steps 2 and 8 load the generic store, ~16 GB RAM each, one after the other):
  ../bin/pyt -t 7200 tools/generalbank_build.py OUT_DIR [--base B138_GENERALBANK] [--expect MD5|none] [--from N]
  OUT_DIR below work/rebuild (replaced unless --from N > 1), e.g. work/rebuild/generalbank_build
  --base: default work/rebuild/b138_pristine/mods/generalbank.drm (pipeline step Repair, tools/b138_snapshot.py)
  --from N: resume at step N with the step files of an earlier run in OUT_DIR/steps
  -> OUT_DIR/mods/generalbank.drm (install with Install-TruTree.ps1 -Source OUT_DIR/mods), OUT_DIR/build_log.txt
"""
import sys, os, shutil, subprocess, hashlib, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_util as BU

EXPECT = '57f5226610903c8b58a1d911d53fc65a'      # test 38 (played 2026-10-30 21:19): titles, hint box, menu style
SYM = 'work/rebuild/sym_base_evidence.json'     # base evidence symbol names (finding 42, sym_calibration_check.py)
LOCMAP = 'work/rebuild/stage1/locmap_xbox_to_pc.json'      # Xbox -> PC locals string ids (pipeline step Media)


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def steps(base, st, out):
    """[(number, title, [tool, args...], output file, extra environment)]"""
    S = lambda n: os.path.join(st, n)
    B = S('01_menu/generalbank.drm')                    # the base of every later step (also the vtable reference)
    tu6 = S('02_tu_generalbank.drm')
    nop9 = lambda i, o, at, w0: ('script_nop_call.py', i, o, '9', at, '%s,0f000050,65000000,*' % w0)
    return [
        (1, 'mission screen style', ('dlc_screen_text_style.py', base, S('01_menu')), B, None),
        (2, 'convert TU generalbank', ('base_convert_check.py', 'generalbank.drm', 'tu', '--ids', '8:6,8:21239,8:20082',
                                       '--out', tu6), tu6, {'TRUDLC_SYM_EXTRA': SYM}),
        (3, 'script 6: remove uigamedata 93', ('script_nop_call.py', tu6, S('03_nof93.drm'), '6', '0x7928',
                                               '04000000,0f000400,65000000,*'), S('03_nof93.drm'), None),
        (4, 'put script 6 / 21239 / 20082', ('drm_put_sections.py', B, S('03_nof93.drm'), S('04_put.drm'),
                                             '8:6,8:21239,8:20082', '--xbox', 'generalbank.drm', '--symbols', SYM),
         S('04_put.drm'), None),
        (5, 'script 6: vtable slot 31', ('script_vtable_insert.py', S('04_put.drm'), B, S('05_vtable.drm'), '6', '31'),
         S('05_vtable.drm'), None),
        (6, 'script 6: init values', ('script_init_from_pc.py', S('05_vtable.drm'), B, S('06_init.drm'), '6',
                                      '--xbox', 'generalbank.drm', '--locmap', LOCMAP), S('06_init.drm'), None),
        (7, 'script 6: text record ids', ('script_uitext_fix.py', '--ported', S('06_init.drm'), S('07_uitext.drm'), '6',
                                          '--locmap', LOCMAP), S('07_uitext.drm'), None),
        (8, 'convert TU scripts 6 + 10', ('generalbank_dlc.py', S('08_s6_10'), '--scripts', '6,10'),
         S('08_s6_10/generalbank.drm'), None),
        (9, 'put script 9 / 21239', ('drm_put_sections.py', S('07_uitext.drm'), S('08_s6_10/generalbank.drm'),
                                     S('09_put.drm'), '8:9,8:21239', '--add-missing', '--xbox', 'generalbank.drm'),
         S('09_put.drm'), None),
        (10, 'extract TU generalbank', ('bigfile_extract.py', 'tu', 'generalbank.drm', S('10_tu_be.drm')),
         S('10_tu_be.drm'), None),
        (10, 'extract retail Xbox generalbank', ('bigfile_extract.py', 'xbase', 'generalbank.drm', S('10_retail_be.drm')),
         S('10_retail_be.drm'), None),
        (11, 'script 9: text records', ('script_record_template.py', S('10_tu_be.drm'), '10', S('10_retail_be.drm'), '10',
                                        S('07_uitext.drm'), '9', S('09_put.drm'), '9', S('11_records.drm'),
                                        '--locmap', LOCMAP), S('11_records.drm'), None),
        (12, 'script 6: title records', ('script_word_set.py', S('11_records.drm'), S('12_titles.drm'), '6',
                                         'e948=00000000:00010000,ea50=0000019a:000001b0,ea58=00000000:00010000'),
         S('12_titles.drm'), None),
        (13, 'script 9: prototype count', ('script_word_set.py', S('12_titles.drm'), S('13_count.drm'), '9',
                                           '1020=000b0000:0000000b'), S('13_count.drm'), None),
        (14, 'script 9: vtable slot 31', ('script_vtable_insert.py', S('13_count.drm'), B, S('14_vtable.drm'), '9', '31',
                                          '--ref-any'), S('14_vtable.drm'), None),
        (15, 'script 9: dlc2data f1 (1/3)', nop9(S('14_vtable.drm'), S('15a.drm'), '0x754', '04000000'), S('15a.drm'), None),
        (15, 'script 9: dlc2data f1 (2/3)', nop9(S('15a.drm'), S('15b.drm'), '0x864', '04000001'), S('15b.drm'), None),
        (15, 'script 9: dlc2data f1 (3/3)', nop9(S('15b.drm'), S('15c.drm'), '0x9b8', '04000000'), S('15c.drm'), None),
        (15, 'script 9: dlc2data f0 (1/2)', nop9(S('15c.drm'), S('15d.drm'), '0x434', '09000001'), S('15d.drm'), None),
        (15, 'script 9: dlc2data f0 (2/2)', nop9(S('15d.drm'), S('15e.drm'), '0x958', '09000008'), S('15e.drm'), None),
        (16, 'script 9: f0 results 0', ('script_word_set.py', S('15e.drm'), S('16_f0.drm'), '9',
                                        '444=06000001:04000000,968=06000008:04000000'), S('16_f0.drm'), None),
        (17, 'script 9: init values', ('script_init_from_pc.py', S('16_f0.drm'), B, S('17_init.drm'), '9',
                                       '--xbox', 'generalbank.drm', '--xbox-id', '10', '--locmap', LOCMAP),
         S('17_init.drm'), None),
        (18, 'script 9: member 17478, node +0x12e0', ('script_word_set.py', S('17_init.drm'), S('18_words.drm'), '9',
                                                      '0e24=00010000:00000001,0e58=0000350e:3f800000,'
                                                      '0e5c=0000350e:3f800000,12e0=00000003:00000008'),
         S('18_words.drm'), None),
        (19, 'script 9: name of f9', ('script_word_set.py', S('18_words.drm'), S('19_name.drm'), '9',
                                      '1128=014d014d:02050205'), S('19_name.drm'), None),
        (20, 'script 9: f0 results 1', ('script_word_set.py', S('19_name.drm'), S('20_f0true.drm'), '9',
                                        '0444=04000000:04000001,0968=04000000:04000001'), S('20_f0true.drm'), None),
        (21, 'script 9: DLC 2 flag stub', ('script_dlc2_flag_stub.py', S('20_f0true.drm'), out), out, None),
    ]


def main(argv):
    base = 'work/rebuild/b138_pristine/mods/generalbank.drm'; expect = EXPECT; start = 1
    if '--base' in argv: k = argv.index('--base'); base = argv[k + 1]; del argv[k:k + 2]
    if '--expect' in argv: k = argv.index('--expect'); expect = argv[k + 1]; del argv[k:k + 2]
    if '--from' in argv: k = argv.index('--from'); start = int(argv[k + 1]); del argv[k:k + 2]
    if len(argv) != 1: sys.exit(__doc__)
    outdir = argv[0]
    BU.check_out(outdir, must_be_below=True)
    for p, what in ((base, '--base'), (SYM, 'symbol names'), (LOCMAP, 'locals map')):
        if not os.path.isfile(p): sys.exit('%s not found: %s' % (what, p))
    if start == 1 and os.path.exists(outdir):
        print('replacing previous output', outdir, flush=True); shutil.rmtree(outdir)
    st = os.path.join(outdir, 'steps'); os.makedirs(st, exist_ok=True)
    out = os.path.join(outdir, 'mods', 'generalbank.drm'); os.makedirs(os.path.dirname(out), exist_ok=True)
    tools = os.path.dirname(os.path.abspath(__file__))
    log = open(os.path.join(outdir, 'build_log.txt'), 'a', encoding='utf-8')
    log.write('=== generalbank_build %s base %s (md5 %s) from step %d\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), base,
                                                                         md5(base), start))
    plan = steps(base, st, out)
    for n, title, cmd, made, env in plan:
        if n < start:
            if not os.path.isfile(made): sys.exit('--from %d: output of step %d missing: %s' % (start, n, made))
            continue
        line = '[%2d/%d] %s: %s' % (n, plan[-1][0], title, ' '.join(cmd))
        print(line, flush=True); log.write(line + '\n')
        t0 = time.time()
        e = dict(os.environ); e.update(env or {})
        r = subprocess.run([sys.executable, '-u', '-I', '-X', 'utf8', os.path.join(tools, cmd[0])] + list(cmd[1:]),
                           env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                           errors='replace')
        tail = [x for x in r.stdout.splitlines() if x.strip()][-3:]
        for x in tail: print('        ' + x[:240], flush=True)
        log.write(r.stdout); log.flush()
        if r.returncode != 0 or not os.path.isfile(made):
            sys.exit('step %d failed (exit %d, output %s)' % (n, r.returncode, 'present' if os.path.isfile(made) else 'missing'))
        msg = '        -> %s md5 %s (%.0f s)' % (os.path.relpath(made), md5(made), time.time() - t0)
        print(msg, flush=True); log.write(msg + '\n')
    got = md5(out)
    if expect.lower() == 'none':
        res = 'result %s md5 %s (not compared)' % (out, got)
    elif got == expect:
        res = 'result %s md5 %s identical to the expected (played) file' % (out, got)
    else:
        res = 'result %s md5 %s DIFFERS from the expected %s' % (out, got, expect)
    print(res); log.write(res + '\n'); log.close()
    if expect.lower() != 'none' and got != expect: sys.exit(1)


if __name__ == '__main__':
    main(sys.argv[1:])
