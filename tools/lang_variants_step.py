r"""Pipeline step Lang (2026-11-11, R10 of the own-tree finding): the language variants <name>.mul_NNN of the DLC
cinematics and the DLC 1 radio lines, built from the player's Xbox packs (pack10 / pack11) with our tools. Before this
step they came only from step Repair (tools/b138_fix_tree.py part 4 -> tools/mul_lang_build.py, into the B138 repair
tree); an own tree without them plays English cinematics / radio lines on every game language (ModLoader rule
"<path>_%03d of the mask, else the plain name", docs/ENGINE.md row "ModLoader 1.2").

What the step writes (60 files, nothing else): every localised stream of
  pack10  cinstream\pdlc1_010_intro, pdlc1_030_finale + the 5 radio lines audio\streams\vo\dlc1\{lara,zip}\*.mul
  pack11  cinstream\pdlc2_020_ghoul, 030_pod, 040_podon, 045_finale, 050_crush (pdlc2_000_fight has only the neutral
          record ffffffff: no variant)
in the five Xbox speech languages, suffix = ModLoader number of the record's language bit: 001 EN (spec ffffffe1),
002 FR (ffffe002), 004 DE (ffffe004), 008 IT (ffffe008), 016 ES (ffffe010). Conversion = tools/mul_lang_build.py
unchanged (cinstream: mul_convert.convert + mul_audio_nch.swap; voice: music_convert.convert_mul + swap, encoder
'game') with --variants-only (the plain names come from the audio steps). Not here: the DLC 2 doppelganger variants
(step Fixes, tools/vo_lang_variants.py build), Russian / Japanese (parked).

Language rule (Dutch / the _032 slot): the suffix is the game's mask 1 << language (tru.exe SetLanguage 0x49a900;
ENGINE.md row "Language ids": ja = 5 -> _032, nl = 11 -> _2048). No pack and no PC archive has a Dutch (or any other
non-EN/FR/DE/IT/ES) speech record (docs: lang_spec_census, 0 records for bit 11); the English record ffffffe1 carries
every bit from 5 up, so the archive plays English for Dutch / Japanese / Polish / ... The step therefore writes NO
.mul_2048 and NO .mul_032: a Dutch game asks the ModLoader for <name>_2048, finds nothing and loads the plain name
(English) - the same speech the archive rule gives. A .mul_032 would be the JAPANESE slot (the mistake of the
installed local\locals.bin_032, which holds the Dutch text); `check` fails on either name.

Modes (from the repository root):
  ../bin/pyt -t 7200 tools/lang_variants_step.py build OUT_MODS [--replace] [--jobs N]
        OUT_MODS below work/rebuild, empty or absent (--replace: remove an existing ...\mods first); 8 mul_lang_build
        processes (one per cinematic, one for the DLC 1 voice lines; 2026-11-11 run: voice 142 s, pdlc2_020 514 s,
        pdlc1_010 1156 s with the 'game' encoder), N at a time (default 3, at most 3; light processes, no converter); writes
        OUT_MODS\..\lang_md5.tsv and OUT_MODS\..\lang_build_<unit>.log.txt
  ../bin/pyt -t 600 tools/lang_variants_step.py check TREE --expect TSV [--installed] [--report R.json]
        read-only gate. Every expected file present with the expected md5 (TSV: docs/data/lang_variants_md5.tsv, the
        installed variants of 2026-11-06, test tree dlc_test51f_audio); no <name>.mul_2048 / .mul_032 of the 12
        streams; without --installed also no other file in TREE (exactly the 60). --installed: TREE is a game mods
        folder, read by explicit names only (no listing). Exit 1 unless every row is ok.
  ../bin/pyt -t 600 tools/lang_variants_step.py names [--carry LIST]
        the 60 names derived from the pack records (language specs); --carry: compare with a carry-over list
        (Switch-TruModsTree -CarryOverFile format, '#' comments, backslashes)
  ../bin/pyt -t 600 tools/lang_variants_step.py record MODS OUT_TSV [--source TEXT]
        writes the expected list (md5, size, path, language, spec) from an installed mods folder, explicit names only
"""
import sys, os, json, hashlib, shutil, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_util as BU

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
EXPECT = os.path.join(ROOT, 'docs', 'data', 'lang_variants_md5.tsv')
LNAME = {1: 'EN', 2: 'FR', 4: 'DE', 8: 'IT', 16: 'ES'}
# pack -> mul_lang_build arguments (pack11 without voice: the doppelganger variants belong to step Fixes)
PACK_ARGS = {'pack10': ['--variants-only'], 'pack11': ['--no-voice', '--variants-only']}
FORBIDDEN = {'_2048': 'Dutch mask 0x800 (no Dutch speech exists: the plain English name is the right fallback)',
             '_032': 'Japanese slot (mask 0x20; the locals.bin_032 naming mistake)'}


def names():
    """[(rel with '/', language number, spec)] of the step, from the pack records (mul_lang_build rules)"""
    import mul_lang_build as MLB
    from archive import Archive
    from names import crc
    from convert_dlc import R, PACKS
    out = []
    for pack in ('pack10', 'pack11'):
        A = Archive(R + [p for p in PACKS if p.endswith('/%s.000' % pack)][0], 'be')
        jobs = [('cine', 'xenon-w\\cinstream\\' + nm) for nm in MLB.CINE[pack]]
        if '--no-voice' not in PACK_ARGS[pack]: jobs += [('voice', nm) for nm in MLB.voice_names(pack)]
        for kind, full in jobs:
            specs = sorted({r['spec'] for r in A.find(crc(full))} & set(MLB.LANG))
            if len(specs) < (1 if kind == 'cine' else 2): continue          # neutral cine / not localised voice
            rel = '/'.join(full.split('\\')[1:])
            out += [('%s_%03d' % (rel, MLB.LANG[s]), MLB.LANG[s], s) for s in specs]
    return sorted(out)


def streams(rows):
    return sorted({r.rsplit('_', 1)[0] for r in rows})


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def read_tsv(path):
    rows = {}
    for l in open(path, encoding='utf-8'):
        if not l.strip() or l.startswith('#') or l.startswith('md5\t'): continue
        f = l.rstrip('\r\n').split('\t')
        rows[f[2]] = dict(md5=f[0], size=int(f[1]))
    return rows


def units():
    """[(label, mul_lang_build arguments after OUT)]: one process per localised cinematic, one for the voice lines"""
    import mul_lang_build as MLB
    want = {r.rsplit('/', 1)[-1].rsplit('_', 1)[0] for r, _, _ in names()}
    u = []
    for pack in PACK_ARGS:
        for nm in MLB.CINE[pack]:
            if nm in want: u.append((nm[:-4], [pack, nm, '--variants-only']))
        if '--no-voice' not in PACK_ARGS[pack]: u.append(('%s_voice' % pack, [pack, '--no-cine', '--variants-only']))
    return u


def run_unit(out, label, args, logdir):
    cmd = [sys.executable, '-u', '-I', '-X', 'utf8', os.path.join(HERE, 'mul_lang_build.py'), out] + args
    log = open(os.path.join(logdir, 'lang_build_%s.log.txt' % label), 'w', encoding='utf-8')
    # the installed variants use the 'game' IMA encoder (tools/mul_audio_nch.py); a TRUDLC_IMA_ENCODER=blind left in
    # the calling shell must not change the step's bytes
    env = dict(os.environ, TRUDLC_IMA_ENCODER='game')
    return subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env), log


def cmd_build(out, replace, jobs):
    o = BU.check_out(out, must_be_below=True)
    if os.path.exists(o) and os.listdir(o):
        if not replace: sys.exit('OUT_MODS is not empty (use --replace): ' + out)
        if os.path.basename(o).lower() != 'mods': sys.exit('--replace removes only a ...\\mods folder: ' + out)
        print('replacing previous output', out, flush=True); shutil.rmtree(o)
    os.makedirs(o, exist_ok=True)
    top = os.path.dirname(o)
    t0 = time.time()
    todo = units()
    rc, running = {}, []
    print('lang step: %d mul_lang_build units, %d at a time' % (len(todo), jobs), flush=True)
    while todo or running:
        while todo and len(running) < jobs:
            label, args = todo.pop(0)
            running.append((label, time.time()) + run_unit(o, label, args, top))
            print('start %s: mul_lang_build %s' % (label, ' '.join(args)), flush=True)
        time.sleep(2)
        for item in list(running):
            label, t1, pr, log = item
            if pr.poll() is None: continue
            running.remove(item); log.close(); rc[label] = pr.returncode
            print('done  %s: exit %d, %.0f s' % (label, pr.returncode, time.time() - t1), flush=True)
            for l in open(os.path.join(top, 'lang_build_%s.log.txt' % label), encoding='utf-8'): print('  ' + l.rstrip())
    if any(rc.values()): sys.exit('mul_lang_build failed: %s' % {k: v for k, v in rc.items() if v})
    want = names()
    lines = ['md5\tsize\tpath\tlanguage\tspec']
    for rel, num, spec in want:
        q = os.path.join(o, *rel.split('/'))
        if not os.path.isfile(q): sys.exit('not written: ' + rel)
        lines.append('%s\t%d\t%s\t%s\t%08x' % (md5(q), os.path.getsize(q), rel, LNAME[num], spec))
    open(os.path.join(top, 'lang_md5.tsv'), 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    print('lang step: %d files in %s, %.0f s; md5 list %s' % (len(want), out, time.time() - t0,
                                                            os.path.join(top, 'lang_md5.tsv')))
    return 0


def cmd_check(tree, expect, installed, report):
    exp = read_tsv(expect)
    want = [r for r, _, _ in names()]
    res = []
    if sorted(exp) != sorted(want):
        res.append(dict(path='(expect list)', verdict='LIST', note='TSV rows %d vs pack-derived names %d, differ: %s' % (
            len(exp), len(want), sorted(set(exp) ^ set(want))[:6])))
    for rel in want:
        q = os.path.join(tree, *rel.split('/'))
        e = exp.get(rel)
        if not os.path.isfile(q): res.append(dict(path=rel, verdict='MISSING')); continue
        h, n = md5(q), os.path.getsize(q)
        ok = e is not None and h == e['md5'] and n == e['size']
        res.append(dict(path=rel, verdict='ok' if ok else 'DIFF', md5=h, size=n,
                        expect_md5=e and e['md5'], expect_size=e and e['size']))
    for s in streams(want):
        for suf, why in FORBIDDEN.items():
            if os.path.exists(os.path.join(tree, *(s + suf).split('/'))):
                res.append(dict(path=s + suf, verdict='FORBIDDEN', note=why))
    if not installed:
        have = set()
        for r, _, fs in os.walk(tree):
            for f in fs: have.add(os.path.relpath(os.path.join(r, f), tree).replace('\\', '/'))
        for rel in sorted(have - set(want)):
            if not any(x['path'] == rel for x in res): res.append(dict(path=rel, verdict='EXTRA'))
    bad = [x for x in res if x['verdict'] != 'ok']
    for x in res:
        if x['verdict'] != 'ok' or '-v' in sys.argv:
            print('%-9s %s %s' % (x['verdict'], x['path'], x.get('note', '') or ('md5 %s expect %s' % (x.get('md5'), x.get('expect_md5')))))
    summ = dict(tree=tree, expect=os.path.relpath(expect, ROOT).replace('\\', '/'), installed_mode=installed,
                files=len(want), ok=sum(x['verdict'] == 'ok' for x in res), bad=len(bad),
                rule='variants 001/002/004/008/016 only; no .mul_2048 (Dutch: plain English) and no .mul_032 (Japanese slot)')
    print('lang check: %d/%d ok, %d not ok (%s)' % (summ['ok'], len(want), len(bad), tree))
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        json.dump(dict(summary=summ, rows=res), open(report, 'w', encoding='utf-8'), indent=1)
    return 1 if bad else 0


def cmd_record(mods, out_tsv, source):
    """the expected list from an installed mods folder, read by explicit names only"""
    lines = ['# language variants of step Lang (tools/lang_variants_step.py): md5 / size of the installed files',
             '# source: %s' % source, 'md5\tsize\tpath\tlanguage\tspec']
    for rel, num, spec in names():
        q = os.path.join(mods, *rel.split('/'))
        if not os.path.isfile(q): sys.exit('missing in %s: %s' % (mods, rel))
        lines.append('%s\t%d\t%s\t%s\t%08x' % (md5(q), os.path.getsize(q), rel, LNAME[num], spec))
    open(out_tsv, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    print('recorded %d rows -> %s' % (len(lines) - 3, out_tsv))
    return 0


def cmd_names(carry):
    want = names()
    for rel, num, spec in want: print('%s\t%s\t%08x' % (rel, LNAME[num], spec))
    print('names: %d (%d streams)' % (len(want), len(streams([r for r, _, _ in want]))))
    if carry:
        c = {l.strip().replace('\\', '/') for l in open(carry, encoding='utf-8-sig') if l.strip() and not l.startswith('#')}
        w = {r for r, _, _ in want}
        print('carry list %s: %d rows, same set: %s; only in carry %s; only derived %s' % (
            carry, len(c), c == w, sorted(c - w), sorted(w - c)))
        return 0 if c == w else 1
    return 0


def main(argv):
    if not argv: print(__doc__); return 2
    a = list(argv)
    def opt(name, default=None):
        if name in a:
            k = a.index(name); v = a[k + 1]; del a[k:k + 2]; return v
        return default
    def flag(name):
        if name in a: a.remove(name); return True
        return False
    mode = a.pop(0)
    if mode == 'build':
        replace = flag('--replace'); jobs = max(1, min(3, int(opt('--jobs', '3'))))
        return cmd_build(a[0], replace, jobs)
    if mode == 'check':
        expect = opt('--expect', EXPECT); report = opt('--report'); installed = flag('--installed'); flag('-v')
        return cmd_check(a[0], expect, installed, report)
    if mode == 'names':
        return cmd_names(opt('--carry'))
    if mode == 'record':
        return cmd_record(a[0], a[1], opt('--source', a[0]))
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
