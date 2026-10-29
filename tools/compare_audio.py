"""Compare the audio of a mods/ tree with a reference tree (e.g. the installed B138) as decoded samples, not bytes.

Wave sections (type 6) of every DRM: sections paired as in compare_sections.py; both payloads are decoded with
audio_parse.ima_decode_fsb (FSB convention, what FMOD plays) and compared sample by sample.
.mul streams (cinstream/, music/, audio/streams/): decoded with the channel count of the header (finding 18) under two
IMA conventions - 'fsb' (block header sample, then nibbles 0..62) and 'game' (header sample, nibble 0 ignored, nibbles
1..63; the game's own decoder) - and compared with the reference and with the decoded Xbox source (ground truth;
per channel, the worst channel is reported).

Per item: samples, differing samples, max |diff|, SNR in dB (reference RMS / difference RMS; inf = identical).
Totals on the console, every item in work/rebuild/audio_<label>.json.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I tools/compare_audio.py MODS_DIR [LABEL] [--ref REF_MODS_DIR] [--xbox-only]
  default REF_MODS_DIR: ../data/pc/mods (the installed B138 tree)
  --xbox-only: no reference tree (DLC 2): only the .mul streams against the decoded Xbox source, waves skipped
"""
import sys, os, json, struct, collections
import numpy as np
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audio_parse import IMA_STEP, IMA_IDX

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'rebuild')


def ima_decode(data, skip_first):
    """mono 36-byte IMA blocks -> int16 samples; skip_first=False: FSB (nibbles 0..62), True: game (nibbles 1..63)"""
    nb = len(data) // 36
    if nb == 0: return np.zeros(0, dtype=np.int16)
    b = np.frombuffer(data[:nb * 36], dtype=np.uint8).reshape(nb, 36)
    pred = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8)); pred = np.where(pred >= 32768, pred - 65536, pred)
    idx = np.clip(b[:, 2].astype(np.int32), 0, 88)
    nib = np.empty((nb, 64), dtype=np.int32)
    nib[:, 0::2] = b[:, 4:] & 15; nib[:, 1::2] = b[:, 4:] >> 4
    out = np.empty((nb, 64), dtype=np.int32); out[:, 0] = pred
    step_t, idx_t = np.array(IMA_STEP), np.array(IMA_IDX)
    first = 1 if skip_first else 0
    for i in range(63):
        n = nib[:, i + first]
        step = step_t[idx]
        diff = (step >> 3) + np.where(n & 1, step >> 2, 0) + np.where(n & 2, step >> 1, 0) + np.where(n & 4, step, 0)
        pred = np.clip(pred + np.where(n & 8, -diff, diff), -32768, 32767)
        idx = np.clip(idx + idx_t[n & 7], 0, 88)
        out[:, i + 1] = pred
    return out.reshape(-1).astype(np.int16)


def stats(a, b):
    n = min(len(a), len(b))
    a = a[:n].astype(np.int64); b = b[:n].astype(np.int64)
    d = a - b
    rd = float(np.sqrt(np.mean(d * d))) if n else 0.0
    rs = float(np.sqrt(np.mean(b * b))) if n else 0.0
    # nothing to compare (one side decoded to 0 samples) is not "identical": snr_db None, counted as the worst case
    snr = None if not n else float('inf') if rd == 0 else (20 * np.log10(rs / rd) if rs > 0 else 0.0)
    return {'samples': int(n), 'len_ours': int(len(a)), 'len_ref': int(len(b)), 'differ': int(np.count_nonzero(d)),
            'max_abs': int(np.abs(d).max()) if n else 0, 'snr_db': snr}


def _snr_key(s):
    return float('-inf') if s['snr_db'] is None else s['snr_db']


def _json_safe(o):
    """inf -> "inf" (json.dump would write Infinity, which strict JSON readers reject)"""
    if isinstance(o, float) and o in (float('inf'), float('-inf')): return 'inf' if o > 0 else '-inf'
    if isinstance(o, dict): return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, list): return [_json_safe(v) for v in o]
    return o


def wave_file(args):
    import compare_drm as C, audio_parse as AP
    rel, ours, ref = args
    so, sp = C.load(open(ours, 'rb').read()), C.load(open(ref, 'rb').read())
    out = []
    for i, j, how in C.section_matches(so, sp):
        a, b = so[i], sp[j]
        if a['type'] != 6 or a['data'] == b['data']: continue
        pa, pb = AP.parse_pc(a['data']), AP.parse_pc(b['data'])
        r = {'file': rel, 'id': a['id'], 'channels': pa['nch'], 'header_equal': pa['data'] == pb['data'] or
             {k: v for k, v in pa.items() if k != 'data'} == {k: v for k, v in pb.items() if k != 'data'}}
        if pa['nch'] == 1:
            r.update(stats(ima_decode(pa['data'], False), ima_decode(pb['data'], False)))
        else:
            r['skipped'] = 'not mono'
        out.append(r)
    return out


def mul_pcm(pd, skip_first):
    """PC .mul -> [samples, channels]; channel count from the header (word 3), each audio block holds the channels
    one after another (finding 18). An earlier version split every block into two halves (L/R), which is wrong
    for the 1-, 4- and 6-channel files."""
    import mul_convert as M
    nch = max(1, struct.unpack_from('<I', pd, 12)[0])
    seg = []
    for t, a, b, p in M.blocks(pd, '<'):
        if t != 0: continue
        nbytes = struct.unpack_from('<I', p, 0)[0]
        d = p[16:16 + nbytes]; per = len(d) // nch
        seg.append((a, np.stack([ima_decode(d[k * per:(k + 1) * per], skip_first) for k in range(nch)], 1)))
    if not seg: return np.zeros((0, nch), dtype=np.int16)
    n = max(a + len(s) for a, s in seg)
    out = np.zeros((n, nch), dtype=np.int16)
    for a, s in seg: out[a:a + len(s)] = s
    return out


def mul_file(args):
    """ours vs reference (both conventions) and, as ground truth, ours/reference (game convention) vs the decoded
    Xbox source, per channel (worst channel reported)"""
    rel, ours, ref = args
    po = open(ours, 'rb').read(); pr = open(ref, 'rb').read() if ref else None
    r = {'file': rel, 'bytes_equal': po == pr, 'channels': struct.unpack_from('<I', po, 12)[0]}
    if pr is not None:
        for conv_o, conv_r in (('fsb', 'fsb'), ('fsb', 'game'), ('game', 'game')):
            a = mul_pcm(po, conv_o == 'game').reshape(-1); b = mul_pcm(pr, conv_r == 'game').reshape(-1)
            r['ours_%s_vs_ref_%s' % (conv_o, conv_r)] = stats(a, b)
    try:
        import mul_audio as MA, mul_audio_batch as MAB
        xd = MAB.find_xb(rel)[0]
        rate, total, xb = MA.xb_pcm(xd)
        for name, pd in (('ours', po), ('ref', pr)):
            if pd is None: continue
            pc = mul_pcm(pd, True)
            per = [stats(pc[:, k], xb[:, k]) for k in range(min(pc.shape[1], xb.shape[1]))]
            r['%s_game_vs_xbox' % name] = min(per, key=_snr_key) if per else None
    except Exception as e:
        r['xbox_error'] = '%s: %s' % (type(e).__name__, e)
    return r


def main(argv):
    ref = '../data/pc/mods'
    if '--ref' in argv:
        k = argv.index('--ref'); ref = argv[k + 1]; del argv[k:k + 2]
    xbox_only = '--xbox-only' in argv
    if xbox_only: argv.remove('--xbox-only')
    mods = argv[0]
    from build_util import require_dir
    require_dir(mods, 'MODS_DIR')
    if not xbox_only: require_dir(ref, 'REF_MODS_DIR')
    label = argv[1] if len(argv) > 1 else os.path.basename(os.path.dirname(os.path.abspath(mods)))
    drms, muls = [], []
    for dp, dn, fn in os.walk(mods):
        for f in fn:
            p = os.path.join(dp, f); rel = os.path.relpath(p, mods).replace(os.sep, '/'); r = os.path.join(ref, rel)
            if xbox_only:
                if f.endswith('.mul'): muls.append((rel, p, None))
                continue
            if not os.path.exists(r): continue
            if f.endswith('.drm'): drms.append((rel, p, r))
            elif f.endswith('.mul'): muls.append((rel, p, r))
    waves, mres = [], []
    with ProcessPoolExecutor(max_workers=int(os.environ.get('TRUDLC_JOBS_LIGHT') or os.cpu_count())) as ex:
        for res in ex.map(wave_file, sorted(drms)): waves.extend(res)
        mres = list(ex.map(mul_file, sorted(muls)))

    print('== wave sections that differ: %d (DRMs compared: %d)' % (len(waves), len(drms)))
    empty = [w for w in waves if 'snr_db' in w and w['snr_db'] is None]
    if empty: print('   EMPTY decode on one side (not compared): %d, e.g. %s' % (len(empty), empty[0].get('file', '?')))
    mono = [w for w in waves if 'snr_db' in w and w['snr_db'] is not None]
    if mono:
        snr = np.array([w['snr_db'] for w in mono]); mx = np.array([w['max_abs'] for w in mono])
        dif = sum(w['differ'] for w in mono); tot = sum(w['samples'] for w in mono)
        print('   decoded mono %d, header equal %d, length equal %d' % (len(mono), sum(1 for w in mono if w['header_equal']),
              sum(1 for w in mono if w['len_ours'] == w['len_ref'])))
        print('   differing samples %d of %d (%.4f %%)' % (dif, tot, 100.0 * dif / tot if tot else 0))
        print('   max |diff| median %d, max %d; SNR dB min %.1f, median %.1f' % (np.median(mx), mx.max(), snr.min(), np.median(snr)))
        print('   max |diff| buckets', dict(collections.Counter('<=16' if m <= 16 else '<=256' if m <= 256 else '<=4096' if m <= 4096 else '>4096' for m in mx)))
    print('   not decoded:', sum(1 for w in waves if 'skipped' in w))

    print('== .mul streams: %d (bytes equal %d)' % (len(mres), sum(1 for r in mres if r['bytes_equal'])))
    for key in ('ours_fsb_vs_ref_fsb', 'ours_fsb_vs_ref_game', 'ours_game_vs_ref_game', 'ours_game_vs_xbox', 'ref_game_vs_xbox'):
        for chans, tag in ((None, 'all'), ((2,), 'stereo'), ((1, 4, 6), 'other')):
            rows = [r[key] for r in mres if r.get(key) and (chans is None or r['channels'] in chans)]
            s = [x['snr_db'] for x in rows if x['snr_db'] is not None]
            empty = len(rows) - len(s); lenx = sum(1 for x in rows if x['len_ours'] != x['len_ref'])
            if s: print('   %-24s %-6s n %2d  SNR dB (worst channel) min %.1f  median %.1f  max %.1f%s%s' % (
                key, tag, len(s), min(s), float(np.median(s)), max(s),
                '  EMPTY %d' % empty if empty else '', '  length differs %d' % lenx if lenx else ''))
            elif empty: print('   %-24s %-6s EMPTY %d (nothing decoded on one side)' % (key, tag, empty))
    errs = [r for r in mres if 'xbox_error' in r]
    if errs: print('   Xbox source errors:', [(r['file'], r['xbox_error']) for r in errs])
    os.makedirs(W, exist_ok=True)
    rep = os.path.join(W, 'audio_%s.json' % label)
    json.dump(_json_safe({'ref': ref, 'waves': waves, 'mul': mres}), open(rep, 'w'), indent=1)
    print('report', os.path.abspath(rep))


if __name__ == '__main__':
    main(sys.argv[1:])
