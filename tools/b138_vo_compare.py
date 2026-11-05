"""B138's own .mul streams against the versions we ship over them, all decoded the way tru.exe decodes .mul (the MMX
IMA decoder with the step capped at 8191, tools/f13_sibilants.decode_game), each against the decoded Xbox source.
Read-only on every tree and on the Xbox packs; writes only below work/b138_vo_compare and work/listen/streams.
Never reads the game folder (the "installed" column comes from N10's report, measured there on 2026-11-04).

Background (workspace docs/Befund-S-Laute.md, F13 / N10): B138's files were encoded for the real decoder; on 2026-10-30
some of them were replaced by our encodes (plain name of the 5 DLC 1 voice lines, the 19 DLC 2 music pieces) and the
ModLoader serves `<path>_001` (English) before the plain path (HookFileSystem::FindFile, WINDOWS_REBUILD.md), so an
English game plays our `_001` copies of the intro / finale / voice lines instead of B138's plain-name file.

For every .mul B138 ships (PRISTINE = work/rebuild/b138_pristine/mods, 39 files) and both slots a game can load for it
(plain name, `_001` = English), every candidate tree that has the slot is decoded (identical bytes only once, by md5):
  b138     B138's original (plain name only)
  rep30    work/rebuild/b138_fixes/mods                       (repair tree of 2026-10-30, the installed language files)
  dlc2s2b  work/rebuild/dlc2_asm_stage2b/mods                 (DLC 2 stage 2b, our 2026-10-30 music encodes)
  rep0411c work/rebuild/pipeline_full_0411c_repair/b138_fixes/mods  (pipeline Repair 2026-11-04, game-model encoder)
  t51f     work/rebuild/dlc_test51f_audio/mods                (N10 re-encode, installed last by the test packages)
"English slot" = what an English game loads from a tree: `_001` when the tree (or an earlier one) has it, else the plain
name. The reference is the English / neutral Xbox record (f13_sibilants.xbox_for: plain name -> mul_audio_batch.find_xb,
_001 -> spec 0xffffffe1). Per file: worst-channel SNR (f13_sibilants.compare), SNR above 4 kHz, |error| > 4096,
and listen_game_model.layer_metrics over all channels (segsnr = median frame SNR, clicks).
"installed" = snr_inst_min of work/f13_sibilants/n10_report.tsv (measured by N10 on the game folder, 2026-11-04 ~01:27).

Usage (from the repository root; one process, below-normal priority):
  ../bin/pyt -t 3600 tools/b138_vo_compare.py measure [--only REL,REL]
        -> work/b138_vo_compare/compare.tsv (one row per file / slot / tree), summary.tsv (one row per B138 file:
           B138 | installed | 51f English slot | delta | recommendation) and compare.log
  ../bin/pyt -t 1800 tools/b138_vo_compare.py wav NAME=REL [NAME=REL ...]
        listening copies like the game into work/listen/streams/NAME/: 1_xbox.wav (Xbox source), 2_b138_wie_spiel.wav
        (B138's plain-name file), 3_pc_51f_wie_spiel.wav (51f's English slot), cut to the common length; report.txt
Recommendation: "take B138" when B138's worst channel is more than 0.05 dB above the 51f English slot, else "keep 51f".
"""
import sys, os, hashlib, json, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
OUT = os.path.join(ROOT, 'work', 'b138_vo_compare')
LISTEN = os.path.join(ROOT, 'work', 'listen', 'streams')
PRISTINE = os.path.join(ROOT, 'work', 'rebuild', 'b138_pristine', 'mods')
TREES = [('rep30', 'work/rebuild/b138_fixes/mods'), ('dlc2s2b', 'work/rebuild/dlc2_asm_stage2b/mods'),
         ('rep0411c', 'work/rebuild/pipeline_full_0411c_repair/b138_fixes/mods'),
         ('t51f', 'work/rebuild/dlc_test51f_audio/mods')]
N10 = os.path.join(ROOT, 'work', 'f13_sibilants', 'n10_report.tsv')
MARGIN = 0.05


def below_normal():
    """lower our own priority (children such as ffmpeg inherit it) - the owner plays a test run at the same time"""
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)       # BELOW_NORMAL_PRIORITY_CLASS
    except Exception as e:
        print('priority not changed: %s' % e)


def md5f(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def b138_files():
    out = []
    for dp, dn, fn in os.walk(PRISTINE):
        for f in fn:
            if '.mul' in f: out.append(os.path.relpath(os.path.join(dp, f), PRISTINE).replace('\\', '/'))
    return sorted(out)


def group(rel):
    if rel.startswith('audio/streams/vo/'): return 'vo'
    if rel.startswith('cinstream/'): return 'cine'
    if rel.startswith('music/'): return 'music'
    return 'stream'


def n10_installed():
    """file -> (snr_inst_min, snr_inst per channel) from N10's report (installed files, game folder, 2026-11-04)"""
    d = {}
    if not os.path.isfile(N10): return d
    rows = open(N10, encoding='utf-8').read().splitlines()
    head = rows[0].split('\t')
    for line in rows[1:]:
        c = dict(zip(head, line.split('\t')))
        if c.get('snr_inst_min'): d[c['file']] = (float(c['snr_inst_min']), c['snr_inst'])
    return d


def decode(path):
    import f13_sibilants as F
    rate, total, nch, segs = F.channel_blocks(open(path, 'rb').read())
    return rate, segs, [F.decode_channel(s, F.decode_game) for s in segs]


def measure_file(path, xb, xrate):
    import f13_sibilants as F, listen_game_model as L
    rate, segs, chans = decode(path)
    if rate != xrate: return dict(error='rate %d != xbox %d' % (rate, xrate))
    per = []
    for k, g in enumerate(chans):
        ref = xb[:, min(k, xb.shape[1] - 1)]
        per.append(F.compare(ref, F.all_blocks(segs[k]), g, xrate))
    n = min(min(len(c) for c in chans), len(xb))
    pc = np.stack([c[:n] for c in chans], axis=1)
    xr = np.stack([xb[:n, min(k, xb.shape[1] - 1)] for k in range(len(chans))], axis=1)
    lm = L.layer_metrics(pc.astype(np.int32), xr.astype(np.int32), xrate)
    return dict(snr=[c['snr'] for c in per], snr_min=min(c['snr'] for c in per), snr_hf_min=min(c['snr_hf'] for c in per),
                big_err=sum(c['big_err'] for c in per), nib_ge75=max(c['nib_idx_ge75_pct'] for c in per),
                segsnr=round(lm['segsnr'], 2), clicks=lm['clicks'], channels=len(chans))


def cmd_measure(argv):
    import f13_sibilants as F
    only = None
    if '--only' in argv: k = argv.index('--only'); only = set(argv[k + 1].split(',')); del argv[k:k + 2]
    os.makedirs(OUT, exist_ok=True)
    logf = open(os.path.join(OUT, 'compare.log'), 'w', encoding='utf-8', newline='\r\n')

    def log(s):
        print(s, flush=True); logf.write(s + '\n'); logf.flush()

    log('b138_vo_compare measure %s (pristine %s)' % (time.strftime('%Y-%m-%d %H:%M:%S'), PRISTINE))
    inst = n10_installed()
    rows, summ = [], []
    for rel in b138_files():
        if only and rel not in only: continue
        t0 = time.time()
        try:
            xrate, xtotal, xb, spec = F.xbox_for(rel)
        except SystemExit as e:
            log('%s: %s' % (rel, e)); continue
        cache = {}
        cand = [('b138', '', os.path.join(PRISTINE, rel))]
        for name, tree in TREES:
            for slot in ('', '_001'):
                p = os.path.join(ROOT, tree, rel + slot)
                if os.path.isfile(p): cand.append((name, slot, p))
        res = {}
        for name, slot, p in cand:
            h = md5f(p)
            if h not in cache: cache[h] = measure_file(p, xb, xrate)
            r = dict(cache[h]); r['md5'] = h; res[(name, slot)] = r
            rows.append([rel, group(rel), name, slot or 'plain', h, str(r.get('channels', '')),
                         ','.join('%.2f' % v for v in r.get('snr', [])), '%.2f' % r.get('snr_min', float('nan')),
                         '%.2f' % r.get('snr_hf_min', float('nan')), str(r.get('big_err', '')), str(r.get('nib_ge75', '')),
                         str(r.get('segsnr', '')), str(r.get('clicks', '')), r.get('error', '')])
            log('  %-70s %-8s %-5s md5 %s  SNR %s  (min %.2f, >4k %.2f, big %s, segsnr %s, clicks %s)' % (
                rel, name, slot or 'plain', h[:12], ','.join('%.2f' % v for v in r.get('snr', [])), r.get('snr_min', float('nan')),
                r.get('snr_hf_min', float('nan')), r.get('big_err'), r.get('segsnr'), r.get('clicks')))
        b = res[('b138', '')]
        # English slot of the test packages: 51f installed last over the base install; _001 wins over the plain name
        e51 = res.get(('t51f', '_001')) or res.get(('t51f', ''))
        e51slot = '_001' if ('t51f', '_001') in res else ('plain' if ('t51f', '') in res else None)
        iv = inst.get(rel + '_001') or inst.get(rel)
        islot = '_001' if (rel + '_001') in inst else ('plain' if rel in inst else None)
        # which tree the installed English slot most likely came from (same SNR as N10 measured, +-0.01 dB)
        src = '-'
        if iv:
            for (name, slot), r in res.items():
                if name != 't51f' and abs(r.get('snr_min', -99) - iv[0]) <= 0.011 and (slot or 'plain') == islot:
                    src = name; break
        if e51 is None:
            ours = None; rec = 'B138 only (no other version shipped)' if not iv or src == 'b138' else 'installed only'
        else:
            ours = e51['snr_min']; rec = 'take B138' if b['snr_min'] > ours + MARGIN else 'keep 51f'
        summ.append([rel, group(rel), '%.2f' % b['snr_min'], ('%.2f' % iv[0]) if iv else '-', islot or '-', src,
                     ('%.2f' % ours) if ours is not None else '-', e51slot or '-',
                     ('%+.2f' % (ours - b['snr_min'])) if ours is not None else '-',
                     '%.2f' % b['segsnr'], ('%.2f' % e51['segsnr']) if e51 else '-', str(b['clicks']),
                     str(e51['clicks']) if e51 else '-', rec])
        log('%s: B138 %.2f | installed %s (%s, = %s) | 51f %s (%s) -> %s  [%.0f s]' % (
            rel, b['snr_min'], ('%.2f' % iv[0]) if iv else '-', islot, src, ('%.2f' % ours) if ours is not None else '-',
            e51slot, rec, time.time() - t0))
    head = ['file', 'group', 'tree', 'slot', 'md5', 'channels', 'snr', 'snr_min', 'snr_hf_min', 'big_err', 'nib_ge75_pct',
            'segsnr', 'clicks', 'error']
    with open(os.path.join(OUT, 'compare.tsv'), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\t'.join(head) + '\n' + '\n'.join('\t'.join(r) for r in rows) + '\n')
    sh = ['file', 'group', 'b138_snr_min', 'installed_snr_min_n10', 'installed_slot', 'installed_from_tree',
          't51f_snr_min', 't51f_slot', 'delta_51f_minus_b138', 'b138_segsnr', 't51f_segsnr', 'b138_clicks',
          't51f_clicks', 'recommendation']
    with open(os.path.join(OUT, 'summary.tsv'), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\t'.join(sh) + '\n' + '\n'.join('\t'.join(r) for r in summ) + '\n')
    cnt = {}
    for r in summ: cnt[r[-1]] = cnt.get(r[-1], 0) + 1
    log('summary: %d B138 files, %s' % (len(summ), json.dumps(cnt)))
    log('written %s, %s' % (os.path.join(OUT, 'compare.tsv'), os.path.join(OUT, 'summary.tsv')))
    logf.close()


def cmd_wav(argv):
    import f13_sibilants as F, listen_game_model as L
    t51 = os.path.join(ROOT, dict(TREES)['t51f'])
    for item in argv:
        name, rel = item.split('=', 1)
        d = os.path.join(LISTEN, name); os.makedirs(d, exist_ok=True)
        xrate, xtotal, xb, spec = F.xbox_for(rel)
        pb = os.path.join(PRISTINE, rel)
        pn = os.path.join(t51, rel + '_001') if os.path.isfile(os.path.join(t51, rel + '_001')) else os.path.join(t51, rel)
        if not os.path.isfile(pn): raise SystemExit('%s: no 51f file' % rel)
        rb, _, cb = decode(pb); rn, _, cn = decode(pn)
        if rb != xrate or rn != xrate: raise SystemExit('%s: rate mismatch' % rel)
        nch = len(cb)
        n = min(len(xb), min(len(c) for c in cb), min(len(c) for c in cn))
        x = np.stack([xb[:n, min(k, xb.shape[1] - 1)] for k in range(nch)], axis=1)
        b = np.stack([c[:n] for c in cb], axis=1); w = np.stack([c[:n] for c in cn[:nch]], axis=1)
        L.write_wav(os.path.join(d, '1_xbox.wav'), xrate, x)
        L.write_wav(os.path.join(d, '2_b138_wie_spiel.wav'), xrate, b)
        L.write_wav(os.path.join(d, '3_pc_51f_wie_spiel.wav'), xrate, w)
        mb = L.layer_metrics(b.astype(np.int32), x.astype(np.int32), xrate)
        mn = L.layer_metrics(w.astype(np.int32), x.astype(np.int32), xrate)
        lines = ['%s (%s, %d ch, %.1f s, %d Hz), decoded like tru.exe (cap 8191), against the Xbox source' % (
                     name, rel, nch, n / xrate, xrate),
                 '1_xbox.wav              Xbox source (English / neutral record)',
                 '2_b138_wie_spiel.wav    B138 plain-name file (work/rebuild/b138_pristine)  md5 %s' % md5f(pb),
                 '3_pc_51f_wie_spiel.wav  51f %s (what an English game with the test packages loads)  md5 %s' % (
                     os.path.relpath(pn, ROOT).replace('\\', '/'), md5f(pn)),
                 'worst-channel SNR       B138 %.2f dB   51f %.2f dB' % (L.snr_db(b, x), L.snr_db(w, x)),
                 'segsnr / hf>6k / clicks B138 %.2f / %.2f / %d   51f %.2f / %.2f / %d' % (
                     mb['segsnr'], mb['hf'], mb['clicks'], mn['segsnr'], mn['hf'], mn['clicks'])]
        with open(os.path.join(d, 'report.txt'), 'w', encoding='utf-8', newline='\r\n') as f:
            f.write('\n'.join(lines) + '\n')
        for l in lines: print(l)
        print('written', d)


def main(argv):
    below_normal()
    if not argv: raise SystemExit(__doc__)
    cmd, rest = argv[0], argv[1:]
    if cmd == 'measure': return cmd_measure(rest)
    if cmd == 'wav': return cmd_wav(rest)
    raise SystemExit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
