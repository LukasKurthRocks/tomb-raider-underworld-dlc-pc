"""Re-encode the installed DLC .mul streams with the game-model IMA encoder (fix N10) and build a test tree with only
the files that got better under tru.exe's decoder.

Per installed ../data/pc/mods/REL (*.mul and the language variants *.mul_NNN):
  * Xbox source as the measurements use it (tools/f13_sibilants.xbox_raw_for: plain name = mul_audio_batch.find_xb,
    _NNN = language record, _001 = English 0xffffffe1);
  * the stage-2a audio step on the installed file as the container: mul_audio_nch.swap (default encoder 'game'),
    which only replaces the IMA payload of every audio block (length and all other bytes stay; swap checks it);
  * measured per channel with the exact game decoder (mul_audio_nch.decode_game) against the decoded Xbox source:
    new file and installed file (SNR, SNR above 4 kHz, |error| > 4096);
  * every re-encoded file goes to STAGE/mods/REL; the tree OUT/mods gets it only when it is better: worst channel
    SNR new > installed + 0.05 dB and no channel worse than installed - 0.05 dB. B138's files (b138_set: measure_all.tsv
    verdict cap-aware = already encoded for the real decoder, plus installed files identical to b138_pristine) are
    skipped unless --with-b138 (then measured, never in the tree).
Writes OUT/md5.tsv (md5, path below mods/), OUT/n10_report.tsv and work/f13_sibilants/n10_report.tsv.

Usage (from the repository root):
  ../bin/pyt -t 14400 tools/mul_reencode_tree.py [--out work/rebuild/dlc_test51f_audio] [--stage work/f13_sibilants/n10_reencoded]
                                                 [--jobs 10] [--with-b138] [--cut] [--only REL ...]
  --cut: only the two cut-content streams of test 50k (prototype source, PROTO below) into work/rebuild/dlc_test51f_audio_cut
         (they are left out of the main tree; report n10_report_dlc_test51f_audio_cut.tsv)
  ../bin/pyt -t 600 tools/mul_reencode_tree.py --select-only     (tree + md5 again from STAGE and the report, no encoding)
  ../bin/pyt -t 600 tools/mul_reencode_tree.py --verify [--cut]  (tree files vs installed: only IMA payload bytes differ)
  --ref work/rebuild/b138_pristine: also measure B138's original of every file (game decoder vs Xbox); where it is not
         the installed file and at least as good as the new encode, the file stays out of the tree (restore B138's)
"""
import sys, os, json, time, shutil, hashlib
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f13_sibilants as F

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
# cut content of test 50k (docs/Befund-Prototyp-DLC.md): no retail Xbox record, the source is the Lara's Shadow
# prototype pack11 (records saved by proto_audio_convert --xbox-out). Only with --cut, into a tree of its own.
PROTO_SRC = os.path.join(ROOT, 'work', 'proto_dlc2_ls_20090207', 'xbox_src')
PROTO = {'audio/streams/music/stingers/mystery_stinger_01.mul': 'mystery_stinger_01.mul',
         'audio/streams/vo/dlc2/doppelganger/i_dg_pdlc2_mach_01.mul': 'UNNAMED_ac1eae71.mul'}
COLS = ['file', 'channels', 'seconds', 'spec', 'status', 'decision', 'snr_inst_min', 'snr_new_min', 'gain_db',
        'snr_inst', 'snr_new', 'snr_hf_inst', 'snr_hf_new', 'big_inst', 'big_new', 'sec_encode']


def job(args):
    rel, stage = args
    import mul_audio as MA, mul_audio_nch as MN
    t0 = time.time()
    r = dict(file=rel)
    pd = open(os.path.join(F.MODS, rel), 'rb').read()
    try:
        if rel in PROTO: xd, spec = open(os.path.join(PROTO_SRC, PROTO[rel]), 'rb').read(), None
        else: xd, spec = F.xbox_raw_for(rel)
    except BaseException as e:
        r.update(status='SKIP no Xbox source (%s)' % str(e)[:60]); return r
    r['spec'] = hex(spec) if spec else ''
    try:
        new, info = MN.swap(xd, pd)
    except Exception as e:
        r.update(status='SKIP swap %s: %s' % (type(e).__name__, str(e)[:100])); return r
    if len(new) != len(pd):
        r.update(status='SKIP size'); return r
    rate, total, xb = MA.xb_pcm(xd); xb = np.clip(xb, -32768, 32767)
    _, ptotal, nch, seg_i = F.channel_blocks(pd)
    _, _, _, seg_n = F.channel_blocks(new)
    ch = []
    for k in range(nch):
        ref = xb[:, min(k, xb.shape[1] - 1)]
        ci = F.compare(ref, F.all_blocks(seg_i[k]), F.decode_channel(seg_i[k], MN.decode_game), rate)
        cn = F.compare(ref, F.all_blocks(seg_n[k]), F.decode_channel(seg_n[k], MN.decode_game), rate)
        ch.append((ci, cn))
    q = os.path.join(stage, 'mods', rel); os.makedirs(os.path.dirname(q), exist_ok=True); open(q, 'wb').write(new)
    r.update(status='OK', channels=nch, seconds=round(ptotal / max(1, rate), 1), same_bytes=new == pd,
             snr_inst=[c[0]['snr'] for c in ch], snr_new=[c[1]['snr'] for c in ch],
             snr_hf_inst=[c[0]['snr_hf'] for c in ch], snr_hf_new=[c[1]['snr_hf'] for c in ch],
             big_inst=sum(c[0]['big_err'] for c in ch), big_new=sum(c[1]['big_err'] for c in ch),
             sec_encode=round(time.time() - t0, 1))
    r['snr_inst_min'] = min(r['snr_inst']); r['snr_new_min'] = min(r['snr_new'])
    r['gain_db'] = round(r['snr_new_min'] - r['snr_inst_min'], 2)
    return r


def job_ref(args):
    """the same file in a reference tree (B138's original, b138_pristine) under the game decoder vs the Xbox source"""
    rel, refdir = args
    import mul_audio as MA, mul_audio_nch as MN
    p = os.path.join(refdir, 'mods', rel)
    pd = open(p, 'rb').read(); inst = open(os.path.join(F.MODS, rel), 'rb').read()
    xd, spec = F.xbox_raw_for(rel)
    rate, total, xb = MA.xb_pcm(xd); xb = np.clip(xb, -32768, 32767)
    _, _, nch, seg = F.channel_blocks(pd)
    snr = [F.compare(xb[:, min(k, xb.shape[1] - 1)], F.all_blocks(seg[k]), F.decode_channel(seg[k], MN.decode_game), rate)['snr']
           for k in range(nch)]
    return rel, dict(snr_ref=snr, ref_equals_installed=pd == inst)


def b138_set():
    """B138's files still installed: measure_all.tsv verdict cap-aware (13) plus every installed .mul that is byte-identical
    to B138's original tree work/rebuild/b138_pristine (adds 2 with verdict 'same': dlc_pillar_of_doom_water_stereo,
    burning_stinger_2_dlc)"""
    p = os.path.join(F.OUT, 'measure_all.tsv')
    L = [l.rstrip('\n').split('\t') for l in open(p, encoding='utf-8')][1:]
    s = {l[0] for l in L if l[10] == 'cap-aware'}
    pr = os.path.join(ROOT, 'work', 'rebuild', 'b138_pristine', 'mods')
    for dp, dn, fn in os.walk(pr):
        for f in fn:
            if '.mul' not in f: continue
            q = os.path.join(dp, f); rel = os.path.relpath(q, pr).replace('\\', '/'); i = os.path.join(F.MODS, rel)
            if os.path.isfile(i) and open(i, 'rb').read() == open(q, 'rb').read(): s.add(rel)
    return s


def decide(r, b138):
    if r['status'] != 'OK': return 'no file (%s)' % r['status']
    if r['file'] in b138: return 'B138 - kept installed'
    if r['same_bytes']: return 'identical - not needed'
    if 'snr_ref' in r and not r['ref_equals_installed'] and min(r['snr_ref']) >= r['snr_new_min'] - 0.05:
        return 'B138 original (b138_pristine) better or equal - not in tree, restore B138 file'
    if r['snr_new_min'] > r['snr_inst_min'] + 0.05 and all(n >= i - 0.05 for n, i in zip(r['snr_new'], r['snr_inst'])):
        return 'TREE'
    return 'installed not worse - kept installed'


def fmt(v):
    if isinstance(v, list): return ','.join('%.2f' % x for x in v)
    if isinstance(v, float): return '%.2f' % v
    return str(v)


def select(rows, b138, out, stage):
    mods = os.path.join(out, 'mods')
    if os.path.isdir(mods): shutil.rmtree(mods)
    md5 = []
    for r in rows:
        r['decision'] = decide(r, b138)
        if r['decision'] != 'TREE': continue
        s = os.path.join(stage, 'mods', r['file']); q = os.path.join(mods, r['file'])
        os.makedirs(os.path.dirname(q), exist_ok=True); shutil.copyfile(s, q)
        md5.append((hashlib.md5(open(q, 'rb').read()).hexdigest(), r['file']))
    with open(os.path.join(out, 'md5.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('md5\tpath\n')
        for h, p in sorted(md5, key=lambda x: x[1]): f.write('%s\t%s\n' % (h, p))
    tag = 'n10_report' + _suffix(out)
    for p in (os.path.join(out, tag + '.tsv'), os.path.join(F.OUT, tag + '.tsv')):
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\t'.join(COLS) + '\n')
            for r in sorted(rows, key=lambda r: r['file']): f.write('\t'.join(fmt(r.get(c, '')) for c in COLS) + '\n')
    json.dump(rows, open(os.path.join(F.OUT, tag + '.json'), 'w'), indent=1)
    return md5


def verify(out):
    """every tree file against the installed one: same length, and with the IMA payload of every audio block
    (type 0, bytes 16..16+nbytes of the block data) blanked on both sides byte-identical - only audio changed"""
    import struct
    mods = os.path.join(out, 'mods'); n = bad = 0
    for dp, dn, fn in os.walk(mods):
        for f in fn:
            q = os.path.join(dp, f); rel = os.path.relpath(q, mods).replace('\\', '/')
            a = bytearray(open(q, 'rb').read()); b = bytearray(open(os.path.join(F.MODS, rel), 'rb').read()); n += 1
            ok = len(a) == len(b)
            if ok:
                o = 0x800
                while o + 16 <= len(b):
                    t, sz = struct.unpack_from('<2I', b, o)
                    if t == 0:
                        nbytes = struct.unpack_from('<I', b, o + 16)[0]
                        a[o + 32:o + 32 + nbytes] = bytes(nbytes); b[o + 32:o + 32 + nbytes] = bytes(nbytes)
                    o += 16 + sz
                ok = a == b
            if not ok: bad += 1; print('VERIFY FAIL', rel)
    print('verify: %d files, only audio payload differs: %d, other differences: %d' % (n, n - bad, bad))


def _suffix(out):
    """report name: n10_report for the default tree, n10_report_<tree name> for any other"""
    b = os.path.basename(os.path.normpath(out))
    return '' if b == 'dlc_test51f_audio' else '_' + b


def summary(rows):
    def group(f):
        return ('cinstream' if f.startswith('cinstream/') else 'vo' if '/vo/' in f else
                'music' if f.startswith('music/') or '/music/' in f else 'other')
    print('== decisions:', {d: sum(r['decision'] == d for r in rows) for d in sorted({r['decision'] for r in rows})})
    for g in ('cinstream', 'vo', 'music', 'other'):
        rr = [r for r in rows if r['status'] == 'OK' and group(r['file']) == g]
        if not rr: continue
        t = [r for r in rr if r['decision'] == 'TREE']
        print('  %-9s measured %3d  tree %3d  SNR worst ch installed min/median %.1f / %.1f  new %.1f / %.1f dB  '
              'gain min/median/max %+.1f / %+.1f / %+.1f dB' % (
                  g, len(rr), len(t), min(r['snr_inst_min'] for r in rr), float(np.median([r['snr_inst_min'] for r in rr])),
                  min(r['snr_new_min'] for r in rr), float(np.median([r['snr_new_min'] for r in rr])),
                  min(r['gain_db'] for r in rr), float(np.median([r['gain_db'] for r in rr])), max(r['gain_db'] for r in rr)))
    for r in rows:
        if r['decision'] not in ('TREE',): print('   %-72s %s%s' % (r['file'], r['decision'],
            '  (installed %.2f / new %.2f dB)' % (r['snr_inst_min'], r['snr_new_min']) if r['status'] == 'OK' else ''))


def main(argv):
    def opt(name, default):
        if name in argv:
            k = argv.index(name); v = argv[k + 1]; del argv[k:k + 2]; return v
        return default
    cut = '--cut' in argv
    if '--verify' in argv:
        argv.remove('--verify')
        verify(os.path.join(ROOT, opt('--out', 'work/rebuild/dlc_test51f_audio_cut' if cut else 'work/rebuild/dlc_test51f_audio')))
        return
    out = os.path.join(ROOT, opt('--out', 'work/rebuild/dlc_test51f_audio_cut' if cut else 'work/rebuild/dlc_test51f_audio'))
    stage = os.path.join(ROOT, opt('--stage', 'work/f13_sibilants/n10_reencoded'))
    jobs = int(opt('--jobs', '10'))
    refdir = opt('--ref', None)
    with_b138 = '--with-b138' in argv; sel_only = '--select-only' in argv
    argv = [a for a in argv if a not in ('--with-b138', '--select-only', '--cut')]
    only = argv[argv.index('--only') + 1:] if '--only' in argv else None
    b138 = b138_set()
    os.makedirs(out, exist_ok=True); os.makedirs(stage, exist_ok=True)
    if sel_only:
        rows = json.load(open(os.path.join(F.OUT, 'n10_report%s.json' % _suffix(out))))
    else:
        rels = []
        for dp, dn, fn in os.walk(F.MODS):
            rels += [os.path.relpath(os.path.join(dp, f), F.MODS).replace('\\', '/') for f in fn if '.mul' in f]
        rels = [r for r in rels if (r in PROTO) == cut]           # cut content only in its own tree (--cut)
        if only: rels = [r for r in rels if r in only]
        todo = [r for r in rels if with_b138 or r not in b138]
        skipped = [dict(file=r, status='SKIP B138 (not re-encoded)') for r in rels if r not in todo]
        todo.sort(key=lambda r: -os.path.getsize(os.path.join(F.MODS, r)))      # biggest first
        print('files %d, to encode %d, B138 skipped %d, jobs %d' % (len(rels), len(todo), len(skipped), jobs), flush=True)
        rows = list(skipped); t0 = time.time()
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            fut = {ex.submit(job, (r, stage)): r for r in todo}
            for f in as_completed(fut):
                try:
                    r = f.result()
                except Exception as e:
                    r = dict(file=fut[f], status='ERROR %s: %s' % (type(e).__name__, str(e)[:100]))
                rows.append(r)
                if r['status'] == 'OK':
                    print('%5.0f s  %-72s ch %d  installed %s  new %s dB  (%+.2f)  %.0f s' % (
                        time.time() - t0, r['file'], r['channels'], fmt(r['snr_inst']), fmt(r['snr_new']), r['gain_db'],
                        r['sec_encode']), flush=True)
                else:
                    print('%5.0f s  %-72s %s' % (time.time() - t0, r['file'], r['status']), flush=True)
    if refdir:                   # B138's originals of the files the 30.10. decision replaced by ours
        refdir = os.path.join(ROOT, refdir)
        todo = [(r['file'], refdir) for r in rows if r['status'] == 'OK' and os.path.isfile(os.path.join(refdir, 'mods', r['file']))]
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            got = dict(ex.map(job_ref, todo))
        for r in rows:
            if r['file'] in got: r.update(got[r['file']])
        for r in sorted((r for r in rows if r['file'] in got), key=lambda r: r['file']):
            print('ref %-72s B138 %s  installed %s  new %s dB%s' % (r['file'], fmt(r['snr_ref']), fmt(r['snr_inst']),
                  fmt(r['snr_new']), '  (B138 = installed)' if r['ref_equals_installed'] else ''), flush=True)
    md5 = select(rows, b138, out, stage)
    summary(rows)
    print('tree %s: %d files' % (os.path.abspath(os.path.join(out, 'mods')), len(md5)))


if __name__ == '__main__':
    main(sys.argv[1:])
