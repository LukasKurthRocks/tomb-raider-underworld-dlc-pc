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
  22 input_map_tu_fix        input map DTP 47: the title update's 6 bindings of Lara's set 17 (141 RB, 142 X, 143 Y,
                             145 LB, 146 Y, 147 X) appended (2026-11-04, F4 / B26 shadow combat: the DLC 2 chart's
                             attack requests {150,152,142/143/147} never fired on the PC; docs Befund-Schattenkampf.md);
                             --done-ok: a base that already has them passes unchanged
  23 dlc2_player_fix gb      mission screen script 104 function 9 (2026-11-05, owner's decision S104): DLC 2
                             (dlc_level2_start) is started like levels 4-6 with uigamedata "load level"(unit, 0, 0, 1),
                             no costume / weapon selection - the title update's level test (4, 5, 6, 2) of its script
                             134 function 9 in an appended block; every PC word at the site checked first
     dlc2_player_fix verify  the check of step 23: the result = step 22 + exactly that fix (every other section
                             byte-identical, every changed word explained, the block = the TU script 134 test),
                             report OUT/steps/23_script104_check.json
The output of step 21 is compared with the played test 38 file (EXPECT21) and step 22 with EXPECT22 (always; a
difference stops the build unless --expect none), the result (step 23) with --expect (default EXPECT: step 22 + the
script 104 fix = the played hand-built tree dlc_test50l_input, which the test packages install; first proven
2026-11-04, docs Befund-Pipeline-Volllauf-0411b.md section 5).

Usage (from the repository root; steps 2 and 8 load the generic store, ~16 GB RAM each, one after the other):
  ../bin/pyt -t 7200 tools/generalbank_build.py OUT_DIR [--base B138_GENERALBANK] [--expect MD5|none] [--from N]
                                                [--no-script104]
  OUT_DIR below work/rebuild (replaced unless --from N > 1), e.g. work/rebuild/generalbank_build
  --base: default work/rebuild/b138_pristine/mods/generalbank.drm (pipeline step Repair, tools/b138_snapshot.py)
  --from N: resume at step N with the step files of an earlier run in OUT_DIR/steps
  --no-script104: stop after step 22 (the file before the S104 decision, EXPECT22 5c6c468d...)
  -> OUT_DIR/mods/generalbank.drm (install with Install-TruTree.ps1 -Source OUT_DIR/mods), OUT_DIR/build_log.txt
"""
import sys, os, shutil, subprocess, hashlib, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_util as BU

EXPECT21 = '57f5226610903c8b58a1d911d53fc65a'    # step 21 = test 38 (played 2026-10-30 21:19): titles, hint box, menu style
EXPECT22 = '5c6c468dd16327a275b2001e6a30da4e'    # step 22 = EXPECT21 + the 6 TU input bindings (2026-11-04, not played)
EXPECT = '66efd71d19aed26ec458cbb3f8f25421'      # step 23 = EXPECT22 + script 104 = dlc_test50l_input (played packages)
SYM = 'work/rebuild/sym_base_evidence.json'     # base evidence symbol names (finding 42, sym_calibration_check.py)
LOCMAP = 'work/rebuild/stage1/locmap_xbox_to_pc.json'      # Xbox -> PC locals string ids (pipeline step Media)


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def steps(base, st, out, s104=True):
    """[(number, title, [tool, args...], output file, extra environment)]"""
    S = lambda n: os.path.join(st, n)
    out22 = S('22_input.drm') if s104 else out
    s104_steps = [
        (23, 'script 104: DLC 2 without costume selection', ('dlc2_player_fix.py', 'gb', out22, out), out, None),
        (23, 'script 104: check', ('dlc2_player_fix.py', 'verify', out22, out, '--tu', S('10_tu_be.drm'), '--report',
                                   S('23_script104_check.json')), S('23_script104_check.json'), None),
    ] if s104 else []
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
        (21, 'script 9: DLC 2 flag stub', ('script_dlc2_flag_stub.py', S('20_f0true.drm'), S('21_stub.drm')),
         S('21_stub.drm'), None),
        (22, 'input map: TU bindings of set 17', ('input_map_tu_fix.py', S('21_stub.drm'), out22, '--done-ok'), out22,
         None),
    ] + s104_steps


def main(argv):
    base = 'work/rebuild/b138_pristine/mods/generalbank.drm'; start = 1
    s104 = '--no-script104' not in argv
    argv = [a for a in argv if a != '--no-script104']
    expect = EXPECT if s104 else EXPECT22
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
    plan = steps(base, st, out, s104)
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
        if n == 21:     # the played test 38 file - every later step builds on it
            ok21 = md5(made) == EXPECT21
            msg = '        step 21 %s the played test 38 file %s' % ('identical to' if ok21 else 'DIFFERS from', EXPECT21)
            print(msg, flush=True); log.write(msg + '\n')
            if not ok21 and expect.lower() != 'none': log.close(); sys.exit('step 21 differs from the played test 38 file')
        if n == 22 and s104:    # the input bindings file of 2026-11-04 - step 23 builds on it
            ok22 = md5(made) == EXPECT22
            msg = '        step 22 %s the step 22 file of 2026-11-04 %s' % ('identical to' if ok22 else 'DIFFERS from',
                                                                            EXPECT22)
            print(msg, flush=True); log.write(msg + '\n')
            if not ok22 and expect.lower() != 'none': log.close(); sys.exit('step 22 differs from %s' % EXPECT22)
    got = md5(out)
    if expect.lower() == 'none':
        res = 'result %s md5 %s (not compared)' % (out, got)
    elif got == expect:
        res = 'result %s md5 %s identical to the expected file (step 21 = played test 38 + step 22%s)' % (
            out, got, ' + step 23 = dlc_test50l_input' if s104 else '')
    else:
        res = 'result %s md5 %s DIFFERS from the expected %s' % (out, got, expect)
    print(res); log.write(res + '\n'); log.close()
    if expect.lower() != 'none' and got != expect: sys.exit(1)


if __name__ == '__main__':
    main(sys.argv[1:])
