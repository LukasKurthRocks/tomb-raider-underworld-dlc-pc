"""srmusic tracks of a mods tree (music\\<d>\\<d>.{mus,sam,mul}): is the audio real, does it match the Xbox source, and
does the PC loader accept the files (read-only; DLC music finding 2026-11-03, docs Befund-DLC-Musik.md).

Per track:
  .mul  PC header (rate, total samples, channels) and the audio decoded with the game's IMA convention
        (tools/compare_audio.mul_pcm, nibbles 1..63) -> decoded length, RMS / peak per channel; a silent stub
        (music_convert.convert_mul alone) decodes to exactly 0. Xbox source (same pack lookup as music_convert /
        mul_audio_batch.find_xb: first DLC pack that has the name) decoded with mul_audio.xb_pcm (XMA1 per stream,
        ffmpeg) -> rate, header total, stream count, decoded length, RMS; SNR of the PC decode against it (worst
        channel, compare_audio.stats).
  .mus  the loader check of tru.exe 0x580EAC: `cmp dword [mus + 8], 0x114` else "The musicfile %s has an incorrect
        version! (rebuild music)" (0x850520, pushed at 0x580EBA); magic, header words 0..11 against the base PC files;
        per track record (offset = header word 9): rate and total samples against the .mul header.
  .sam  FSB4 magic, size, differing bytes against the base PC .sam (only the 16-byte FSB GUID differs between base files).

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/music_audio_report.py TREE [LABEL] [--names a,b,..] [--jobs N] [--no-xbox]
      TREE    a mods folder (with music\\ below it) or a folder that has music\\ directly
      LABEL   report name: work/media/music_audio_<LABEL>.json (default: the folder name)
  ../bin/pyt -t 3600 tools/music_audio_report.py --base [--jobs N]
      the 32 base tracks of the PC bigfile (reference values: version word, header words, channels, RMS)
"""
import sys, os, struct, json, hashlib
import numpy as np
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, 'work', 'media')
PCB = os.path.join(ROOT, '..', 'data', 'pc', 'bigfile.000')
MUS_VERSION = 0x114          # tru.exe 0x580EAC
BASE_SAM_TRACK = 'l3_chapel_mus_01'   # music_convert takes this track's PC .sam


def arg(argv, key, default):
    if key in argv:
        k = argv.index(key); v = argv[k + 1]; del argv[k:k + 2]; return v
    return default


def rms_list(pcm):
    return [int(round(float(np.sqrt(np.mean(pcm[:, k].astype(np.float64) ** 2))))) if len(pcm) else 0
            for k in range(pcm.shape[1])]


def mus_info(m, mul_rate, mul_total):
    w = struct.unpack_from('<12I', m, 0) if len(m) >= 48 else ()
    r = {'bytes': len(m), 'magic': m[:4].decode('latin-1'), 'version': w[2] if w else None,
         'version_ok': bool(w) and w[2] == MUS_VERSION, 'words_0_11': ['%08x' % x for x in w]}
    if w:
        A = w[9]; recs = []
        t = 0
        while A + 0x58 * (t + 1) <= len(m):
            rate, z, two, loop, total = struct.unpack_from('<5I', m, A + 0x58 * t)
            recs.append({'rate': rate, 'w2': two, 'loop': loop, 'total': total}); t += 1
        r['records'] = recs
        r['records_rate_ok'] = all(x['rate'] == mul_rate for x in recs) if recs else None
        r['records_total_ok'] = all(x['total'] == mul_total for x in recs) if recs else None
    return r


def sam_info(s, base_sam):
    r = {'bytes': len(s), 'magic': s[:4].decode('latin-1')}
    if base_sam is not None:
        r['differ_vs_base_pc'] = (sum(1 for a, b in zip(s, base_sam) if a != b) + abs(len(s) - len(base_sam)))
        r['differ_offsets'] = sorted({o for o, (a, b) in enumerate(zip(s, base_sam)) if a != b})[:2] if s != base_sam else []
    return r


def track(args):
    """(name, files {ext: bytes}, base_sam, with_xbox) -> report dict"""
    import compare_audio as CA
    name, files, base_sam, with_xbox = args
    r = {'track': name, 'md5': {e: hashlib.md5(b).hexdigest() for e, b in files.items()}}
    pd = files.get('mul')
    if pd is None: r['error'] = 'no .mul'; return r
    rate, w1, total, nch = struct.unpack_from('<4I', pd, 0)
    pc = CA.mul_pcm(pd, True)
    r['pc'] = {'rate': rate, 'total': total, 'channels': nch, 'decoded': int(len(pc)), 'rms': rms_list(pc),
               'peak': int(np.abs(pc.astype(np.int32)).max()) if len(pc) else 0, 'bytes': len(pd)}
    r['silent'] = r['pc']['peak'] == 0
    if 'mus' in files: r['mus'] = mus_info(files['mus'], rate, total)
    if 'sam' in files: r['sam'] = sam_info(files['sam'], base_sam)
    if with_xbox:
        try:
            import mul_audio as MA, mul_audio_batch as MAB
            xd, pack, sp, specs = MAB.find_xb('music\\%s\\%s.mul' % (name, name))
            if xd is None: raise ValueError('no Xbox source in the DLC packs')
            xr, x1, xt, xch = struct.unpack_from('>4I', xd, 0)
            xrate, xtotal, xb = MA.xb_pcm(xd)
            per = [CA.stats(pc[:, k], xb[:, k]) for k in range(min(pc.shape[1], xb.shape[1]))]
            worst = min(per, key=CA._snr_key) if per else None
            r['xbox'] = {'pack': pack, 'spec': hex(sp), 'md5': hashlib.md5(xd).hexdigest(), 'rate': xr, 'total': xt,
                         'header_channels': xch, 'streams': int(xb.shape[1]), 'decoded': int(len(xb)), 'rms': rms_list(xb)}
            r['check'] = {
                'rate_equal': xr == rate,
                'channels_equal': int(xb.shape[1]) == nch,
                # PC total = Xbox total rounded to 256 samples (music_convert docstring, the base-pair rule)
                'total_rule': total == ((xt + 128) // 256) * 256,
                'total_diff_samples': int(total) - int(xt),
                'decoded_diff_samples': int(len(pc)) - int(len(xb)),
                'snr_db_worst_channel': worst['snr_db'] if worst else None,
            }
        except Exception as e:
            r['xbox_error'] = '%s: %s' % (type(e).__name__, e)
    return r


def tree_jobs(tree, names):
    md = os.path.join(tree, 'music') if os.path.isdir(os.path.join(tree, 'music')) else tree
    if not os.path.isdir(md): sys.exit('no music folder below ' + tree)
    jobs = []
    for d in sorted(os.listdir(md)):
        fp = os.path.join(md, d)
        if not os.path.isdir(fp) or (names and d not in names): continue
        files = {}
        for e in ('mus', 'sam', 'mul'):
            f = os.path.join(fp, '%s.%s' % (d, e))
            if os.path.isfile(f): files[e] = open(f, 'rb').read()
        jobs.append((d, files))
    return jobs


def base_jobs():
    from archive import Archive
    from names import crc
    import music_list as ML
    A = Archive(PCB, 'le'); jobs = []
    for d in ML.base_names():
        files = {}
        for e in ('mus', 'sam', 'mul'):
            rr = A.find(crc('pc-w\\music\\%s\\%s.%s' % (d, d, e)))
            if rr: files[e] = A.read(rr[0])
        if len(files) == 3: jobs.append((d, files))
    return jobs


def base_sam():
    from archive import Archive
    from names import crc
    A = Archive(PCB, 'le')
    rr = A.find(crc('pc-w\\music\\%s\\%s.sam' % (BASE_SAM_TRACK, BASE_SAM_TRACK)))
    return A.read(rr[0]) if rr else None


def fmt_db(v):
    return '-' if v is None else ('inf' if v == float('inf') else '%.1f' % v)


def main(argv):
    argv = list(argv)
    jobs_n = int(arg(argv, '--jobs', '2'))
    names = set(x for x in arg(argv, '--names', '').split(',') if x)
    with_xbox = '--no-xbox' not in argv
    if '--no-xbox' in argv: argv.remove('--no-xbox')
    bsam = base_sam()
    if '--base' in argv:
        label = 'base_pc'; jobs = base_jobs(); with_xbox = False
    else:
        tree = argv[0]
        label = argv[1] if len(argv) > 1 else os.path.basename(os.path.abspath(tree).rstrip('\\/'))
        jobs = tree_jobs(tree, names)
    reps = []
    with ProcessPoolExecutor(max_workers=max(1, jobs_n)) as ex:
        for r in ex.map(track, [(d, f, bsam, with_xbox) for d, f in jobs]):
            reps.append(r)
            pc = r.get('pc', {}); mu = r.get('mus', {}); sa = r.get('sam', {}); xb = r.get('xbox', {}); ck = r.get('check', {})
            print('%-36s pc %5s Hz ch %s total %8s dec %8s rms %-22s | mus v%s %s rec rate/total %s/%s | sam %s diff %s'
                  '%s' % (r['track'], pc.get('rate'), pc.get('channels'), pc.get('total'), pc.get('decoded'),
                          ','.join(map(str, pc.get('rms', []))), '%x' % mu['version'] if mu.get('version') is not None else '-',
                          'ok' if mu.get('version_ok') else 'BAD', mu.get('records_rate_ok'), mu.get('records_total_ok'),
                          sa.get('magic'), sa.get('differ_vs_base_pc'),
                          (' | xbox %s %s Hz streams %s total %s dec %s rms %s | rate %s ch %s total-rule %s dec-diff %s SNR %s' % (
                              xb.get('pack'), xb.get('rate'), xb.get('streams'), xb.get('total'), xb.get('decoded'),
                              ','.join(map(str, xb.get('rms', []))), ck.get('rate_equal'), ck.get('channels_equal'),
                              ck.get('total_rule'), ck.get('decoded_diff_samples'), fmt_db(ck.get('snr_db_worst_channel'))))
                          if xb else (' | ' + r['xbox_error'] if 'xbox_error' in r else '')), flush=True)
    n = len(reps)
    s = {'tracks': n,
         'silent': sum(1 for r in reps if r.get('silent')),
         'rms_gt_0_all_channels': sum(1 for r in reps if r.get('pc') and all(x > 0 for x in r['pc']['rms'])),
         'mus_version_ok': sum(1 for r in reps if r.get('mus', {}).get('version_ok')),
         'mus_records_rate_ok': sum(1 for r in reps if r.get('mus', {}).get('records_rate_ok')),
         'mus_records_total_ok': sum(1 for r in reps if r.get('mus', {}).get('records_total_ok')),
         'sam_fsb4': sum(1 for r in reps if r.get('sam', {}).get('magic') == 'FSB4')}
    if with_xbox:
        ck = [r['check'] for r in reps if 'check' in r]
        snr = [c['snr_db_worst_channel'] for c in ck if c['snr_db_worst_channel'] is not None]
        s.update({'xbox_found': len(ck), 'rate_equal': sum(c['rate_equal'] for c in ck),
                  'channels_equal': sum(c['channels_equal'] for c in ck), 'total_rule': sum(c['total_rule'] for c in ck),
                  'decoded_diff_max_abs': max([abs(c['decoded_diff_samples']) for c in ck] or [0]),
                  'snr_db_min': min(snr) if snr else None, 'snr_db_median': float(np.median(snr)) if snr else None})
    print('SUMMARY', json.dumps(s))
    os.makedirs(OUTDIR, exist_ok=True)
    rep = os.path.join(OUTDIR, 'music_audio_%s.json' % label)
    safe = json.loads(json.dumps({'summary': s, 'tracks': reps}, default=str).replace('Infinity', '"inf"'))
    json.dump(safe, open(rep, 'w', encoding='utf-8'), indent=1)
    print('report', os.path.abspath(rep))


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
