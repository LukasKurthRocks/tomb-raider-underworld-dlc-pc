"""Build the shadow meter HUD generalbank (DLC 2): the title update's HUD script 38 (PC script 37) and its 74-entry
larabase native type script 211 (PC 213) plus its two new textures 7899 / 7036 in a PC generalbank, step by step with
the existing tools; every step checks the words it replaces. Workspace docs: Befund-Schattenleiste-HUD.md,
Plan-Nacht-Analysen-2026-11-03.md section 2; code side: src/asi/TruShadowHud (binds larabase f70-f73 and dlc2data f0
- WITHOUT that plugin the engine calls null natives from this HUD script).

Proof by control: the same chain is run on the RETAIL Xbox script 38 (the control); it ends equal to Crystal's PC
script 37 except the dependency-list order (17 words, same set) and the old, unused vtable at the end (6 words) -
tools/script_port_check.py, printed at the end. The control is also the donor of step T7 (init nodes whose Xbox words
equal a retail node take Crystal's words) and the reference of tools/script_symbol_pairs.py.

Steps (C = control from the converted retail generalbank, T = title update; intermediate files in OUT/steps/):
  C1 / T1  drm_put_sections       converted script 37 + 213 into BASE (--xbox call remap, --symbols)
  C2 / T2  script_vtable_insert   script 37: the PC parent's extra vtable slot 31
  C3 / T3  script_word_set        script 37: userType of the four members of Xbox type 0x343: converter 0x345
                                  ('guess_lower') -> 0x347 (Crystal's PC value of the same four members)
  C4 / T4  script_init_from_pc    script 37: member / local init values from Crystal's PC script 37
  C5 / T5  script_init_guard      undo what T4 wrote over array counts (TU: 5 code counts, 1 sfi count)
  C6 / T6  script_word_set        the 0.35 floats of the 0x343 members (an unlabelled node the init step cannot copy;
                                  Crystal: = the Xbox value); T6 also member 9's UI element node (title update:
                                  60 words, no twin) as in Crystal's member 9 / the twin-fixed node of the same type
  T7       script_init_twin       init nodes with a retail twin -> Crystal's words (control C6 as donor)
  T8       script_symbol_pairs    Symbol pair words with the converter's Symbol map (title-update member paths)
  T9       generalbank_tu_textures  textures 7899 / 7036 (--add-missing); compared with EXPECT_T9 (the first build,
                                  tree dlc_test50l_hud; a difference stops the build unless --expect none)
  T10      input_map_tu_fix       input map DTP 47: the title update's 6 bindings of Lara's set 17 (141 RB, 142 X,
                                  143 Y, 145 LB, 146 Y, 147 X) appended - the same step as tools/generalbank_build.py
                                  step 22 (BASE predates it; docs Befund-Schattenkampf.md, WINDOWS_REBUILD finding 48);
                                  --done-ok: a base that already has them passes unchanged
  check    script_port_check C6 vs BASE (control = Crystal), script_init_twin of the result (0 changes), tree /
           native checks are separate (tools/tree_check.py, tools/native_calls_check.py)

Inputs: BASE = the clean generalbank without the direct-start test patch (work/rebuild/test50l_look_work/autostart_gb,
md5 586c37ad378691d534f0aab2cee3c439); --tu-conv = the converted title-update generalbank (pipeline step 2 of
tools/generalbank_build.py, work/rebuild/generalbank_build/steps/02_tu_generalbank.drm), --retail-conv = the converted
retail generalbank (tools/base_convert_check.py generalbank.drm retail, work/rebuild/base_convert/retail_generalbank.drm);
the converter runs (~16 GB RAM each) are not repeated here.

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/generalbank_hud_build.py OUT_DIR [--base FILE] [--tu-conv FILE] [--retail-conv FILE] [--expect MD5|none]
  -> OUT_DIR/mods/generalbank.drm, OUT_DIR/build_log.txt
"""
import sys, os, shutil, subprocess, hashlib, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_util as BU

BASE = 'work/rebuild/test50l_look_work/autostart_gb/mods/generalbank.drm'
TU_CONV = 'work/rebuild/generalbank_build/steps/02_tu_generalbank.drm'
RETAIL_CONV = 'work/rebuild/base_convert/retail_generalbank.drm'
SYM = 'work/rebuild/sym_base_evidence.json'
LOCMAP = 'work/rebuild/stage1/locmap_xbox_to_pc.json'
EXPECT_T9 = '62efb0ee7fc2a21093e5e27e246dfe8b'   # step T9 = first build 2026-11-03 (tree dlc_test50l_hud), not played
EXPECT = '2ff716288e69a6ba8baca595f9c6f354'      # step T10 = T9 + the 6 TU input bindings (tree dlc_test50l_hud_input,
                                                 # hand-built 2026-11-03 by agent N4; in this build since 2026-11-04 N15)

# userType words of the four members of Xbox type 0x343 (retail members 83-86, title update 85-88)
TYPES_C = 'ce44=345:347,ce58=345:347,ce6c=345:347,ce80=345:347'
TYPES_T = 'df4c=345:347,df60=345:347,df74=345:347,df88=345:347'
# 0.35 floats (Xbox 0x3eb33333) of those members' init nodes; T: also member 9's node (Crystal's member 9 values)
FLOATS_C = '10a34=3333343a:3eb33333,10a44=3333343a:3eb33333'
FLOATS_T = ('12184=3333343a:3eb33333,12194=3333343a:3eb33333,12834=00010000:00000001,12868=cccd334f:3dcccccd,'
            '1286c=cccd334f:3dcccccd,12880=ffff4ddf:4bffffff,12888=ffff4ddf:4bffffff,1288c=60600140:ff606060')


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def steps(base, tu, rt, st, out):
    S = lambda n: os.path.join(st, n)
    put = lambda donor, o, *x: ('drm_put_sections.py', base, donor, o, '8:37,8:213', '--xbox', 'generalbank.drm') + x + (
        '--symbols', SYM)
    init = lambda i, o, *x: ('script_init_from_pc.py', i, base, o, '37', '--xbox', 'generalbank.drm') + x + (
        '--xbox-id', '38', '--locmap', LOCMAP)
    return [
        ('C1', 'control: put retail 37 / 213', put(rt, S('c1_put.drm'), '--retail'), S('c1_put.drm')),
        ('C2', 'control: vtable slot 31', ('script_vtable_insert.py', S('c1_put.drm'), base, S('c2_vt.drm'), '37', '31'),
         S('c2_vt.drm')),
        ('C3', 'control: userType 0x343 members', ('script_word_set.py', S('c2_vt.drm'), S('c3_types.drm'), '37', TYPES_C),
         S('c3_types.drm')),
        ('C4', 'control: init values', init(S('c3_types.drm'), S('c4_init.drm'), '--retail'), S('c4_init.drm')),
        ('C5', 'control: guard counts', ('script_init_guard.py', S('c3_types.drm'), S('c4_init.drm'), S('c5_guard.drm'),
                                         '37'), S('c5_guard.drm')),
        ('C6', 'control: 0.35 floats', ('script_word_set.py', S('c5_guard.drm'), S('c6_control.drm'), '37', FLOATS_C),
         S('c6_control.drm')),
        ('T1', 'put TU 37 / 213', put(tu, S('t1_put.drm')), S('t1_put.drm')),
        ('T2', 'vtable slot 31', ('script_vtable_insert.py', S('t1_put.drm'), base, S('t2_vt.drm'), '37', '31', '--ref-any'),
         S('t2_vt.drm')),
        ('T3', 'userType 0x343 members', ('script_word_set.py', S('t2_vt.drm'), S('t3_types.drm'), '37', TYPES_T),
         S('t3_types.drm')),
        ('T4', 'init values', init(S('t3_types.drm'), S('t4_init.drm')), S('t4_init.drm')),
        ('T5', 'guard counts', ('script_init_guard.py', S('t3_types.drm'), S('t4_init.drm'), S('t5_guard.drm'), '37'),
         S('t5_guard.drm')),
        ('T6', 'floats / member 9 node', ('script_word_set.py', S('t5_guard.drm'), S('t6_words.drm'), '37', FLOATS_T),
         S('t6_words.drm')),
        ('T7', 'init nodes from retail twins', ('script_init_twin.py', S('t6_words.drm'), '37', 'xt', '38',
                                                S('c6_control.drm'), '37', 'xl', '38', S('t7_twin.drm')), S('t7_twin.drm')),
        ('T8', 'Symbol pairs', ('script_symbol_pairs.py', S('t7_twin.drm'), '37', 'xt', '38', S('c6_control.drm'), '37',
                                'xl', '38', '--fix', S('t8_pairs.drm')), S('t8_pairs.drm')),
        ('T9', 'textures 7899 / 7036', ('generalbank_tu_textures.py', S('t8_pairs.drm'), S('t9_textures.drm'), '7899,7036',
                                        '--add-missing'), S('t9_textures.drm')),
        ('T10', 'input map: TU bindings of set 17', ('input_map_tu_fix.py', S('t9_textures.drm'), out, '--done-ok'), out),
        ('check', 'control vs Crystal', ('script_port_check.py', S('c6_control.drm'), base, '37', '--max', '30'), None),
        ('check', 'twins of the result', ('script_init_twin.py', out, '37', 'xt', '38', S('c6_control.drm'), '37', 'xl',
                                          '38', S('check_twin.drm')), S('check_twin.drm')),
    ]


def main(argv):
    base, tu, rt, expect = BASE, TU_CONV, RETAIL_CONV, EXPECT
    for flag in ('--base', '--tu-conv', '--retail-conv', '--expect'):
        if flag in argv:
            k = argv.index(flag); v = argv[k + 1]; del argv[k:k + 2]
            if flag == '--base': base = v
            elif flag == '--tu-conv': tu = v
            elif flag == '--retail-conv': rt = v
            else: expect = v
    if len(argv) != 1: sys.exit(__doc__)
    outdir = argv[0]
    BU.check_out(outdir, must_be_below=True)
    for p, what in ((base, '--base'), (tu, '--tu-conv'), (rt, '--retail-conv'), (SYM, 'symbol names'), (LOCMAP, 'locals map')):
        if not os.path.isfile(p): sys.exit('%s not found: %s' % (what, p))
    if os.path.exists(outdir):
        print('replacing previous output', outdir, flush=True); shutil.rmtree(outdir)
    st = os.path.join(outdir, 'steps'); os.makedirs(st)
    out = os.path.join(outdir, 'mods', 'generalbank.drm'); os.makedirs(os.path.dirname(out))
    tools = os.path.dirname(os.path.abspath(__file__))
    log = open(os.path.join(outdir, 'build_log.txt'), 'w', encoding='utf-8')
    log.write('=== generalbank_hud_build %s\nbase %s md5 %s\ntu-conv %s md5 %s\nretail-conv %s md5 %s\n' % (
        time.strftime('%Y-%m-%d %H:%M:%S'), base, md5(base), tu, md5(tu), rt, md5(rt)))
    env = dict(os.environ); env['TRUDLC_SYM_EXTRA'] = SYM        # the converter's symbol map (script_symbol_pairs)
    for n, title, cmd, made in steps(base, tu, rt, st, out):
        line = '[%s] %s: %s' % (n, title, ' '.join(cmd))
        print(line, flush=True); log.write(line + '\n')
        r = subprocess.run([sys.executable, '-u', '-I', '-X', 'utf8', os.path.join(tools, cmd[0])] + list(cmd[1:]),
                           env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                           errors='replace')
        log.write(r.stdout); log.flush()
        for x in [x for x in r.stdout.splitlines() if x.strip()][-4:]: print('        ' + x[:220], flush=True)
        if r.returncode != 0 or (made and not os.path.isfile(made)):
            sys.exit('step %s failed (exit %d), see %s' % (n, r.returncode, os.path.join(outdir, 'build_log.txt')))
        if made:
            msg = '        -> %s md5 %s' % (os.path.relpath(made), md5(made))
            print(msg, flush=True); log.write(msg + '\n')
        if n == 'T9':   # the first build (tree dlc_test50l_hud) - step T10 builds on it
            ok9 = md5(made) == EXPECT_T9
            msg = '        step T9 %s the first build %s' % ('identical to' if ok9 else 'DIFFERS from', EXPECT_T9)
            print(msg, flush=True); log.write(msg + '\n')
            if not ok9 and expect.lower() != 'none': log.close(); sys.exit('step T9 differs from the first build')
    got = md5(out)
    if expect.lower() == 'none': res = 'result %s md5 %s (not compared)' % (out, got)
    elif got == expect: res = 'result %s md5 %s identical to the expected file' % (out, got)
    else: res = 'result %s md5 %s DIFFERS from the expected %s' % (out, got, expect)
    print(res); log.write(res + '\n'); log.close()
    if expect.lower() != 'none' and got != expect: sys.exit(1)


if __name__ == '__main__':
    main(sys.argv[1:])
