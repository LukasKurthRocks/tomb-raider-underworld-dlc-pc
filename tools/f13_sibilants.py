"""F13 "S-Laute": exact model of tru.exe's own IMA decoder for .mul streams and what it does to our DLC speech
(read-only on game data; writes only reports / listening WAVs under work/f13_sibilants).

The decoder (found with tools/f13_ima_tables.py, tru.exe 0x5957a0, tables prepared once at 0x595670, called from the
sound init 0x587002; caller 0x5964be decodes 36-byte mono blocks into 64 samples):
  * step table (int32, 0x8a9588) is CAPPED at 8191 and multiplied by 4 at start-up (cmp/jle 0x1fff, shl 2), so the
    steps of index 75..88 (8630..32767 in standard IMA) all become 8191;
  * per nibble a 16-bit multiplier 2048 * (2 * (n & 7) + 1), negated for n & 8 (table 0xcd3fd0 / 0xcd3bd0),
    diff = pmulhw(mult, 4 * step) = floor(mult * 4 * step / 65536) = floor(+-(2n+1) * step / 8);
  * block header: sample (int16) + index (byte 2); lane 0 multiplier masked (0x8a96f0 = 0000 ffff ffff ffff) =
    nibble 0 ignored, output = header sample, then nibbles 1..63 ("game convention", finding 18);
  * 4 samples at a time (MMX): v = d + [prev,0,0,0]; v += v << 1 lane; v += v << 2 lanes, every add saturating
    (paddsw) - equal to the sequential sum unless a partial sum overflows.
Our encoders (tools/mul_audio_nch.ima_encode_game, ima_encoder_check lookahead) and our check decoder
(compare_audio.ima_decode) use the standard IMA steps up to 32767 and shift-sum diffs.

Usage (from the repository root, outputs under work/f13_sibilants):
  ../bin/pyt -t 1800 tools/f13_sibilants.py measure REL [REL ...]      installed ../data/pc/mods/REL vs decoded Xbox source
        REL e.g. cinstream/pdlc1_010_intro.mul_004 (suffix _NNN = language spec 0xffffeNNN, decimal) or
        audio/streams/vo/dlc1/lara/c_lara_1_pdlc1_invasion_01.mul
  ../bin/pyt -t 7200 tools/f13_sibilants.py measure_all                 every installed .mul* vs Xbox -> measure_all.tsv
        (verdict: cap-aware = game model > old model + 1 dB, i.e. encoded for the real decoder; cap-blind = the reverse)
  ../bin/pyt -t 120  tools/f13_sibilants.py summary                     counts from the scan / measure_all outputs
  ../bin/pyt -t 600  tools/f13_sibilants.py decwav REL TAG             installed REL decoded game / old model -> wav/TAG_*.wav
  ../bin/pyt -t 600  tools/f13_sibilants.py newwav DIR REL TAG         DIR/mods/REL (N10 re-encode, e.g.
        work/f13_sibilants/n10_reencoded) decoded like tru.exe -> wav/TAG_5_neu_gebaut_wie_spiel.wav
  ../bin/pyt -t 3600 tools/f13_sibilants.py scan                    every installed .mul*: index >= 75 share, game vs old
  ../bin/pyt -t 1800 tools/f13_sibilants.py base music [N]            Crystal's base-game PC music .mul (first N pairs)
  ../bin/pyt -t 1800 tools/f13_sibilants.py base cine NAME.mul [SPEC]  Crystal's base PC cinematic (default ffffe004)
  ../bin/pyt -t 3600 tools/f13_sibilants.py fix REL [--enc beam|greedy] [--k 16] [--wav TAG] [--cut S0 S1]
        re-encode the Xbox source with an encoder that models the game decoder (cap + rounding; default beam search
        per block, greedy = exhaustive start index + best single nibble per sample), measure it under the
        game decoder; --wav writes TAG_1_xbox / _2_pc_jetzt_wie_spiel / _3_pc_jetzt_altes_modell / _4_fix_wie_spiel
        .wav into work/f13_sibilants/wav (optional --cut: only seconds S0..S1)
Measured per channel: SNR (full band and above 4 kHz) of the PC stream decoded with the game model and with the old
model against the Xbox source, share of nibbles decoded with step index >= 75 (where the cap bites), error RMS in
blocks with / without such nibbles, samples with |error| > 4096, clipped samples.
"""
import sys, os, struct, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audio_parse import IMA_STEP, IMA_IDX

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'work', 'f13_sibilants')
MODS = os.path.join(HERE, '..', '..', 'data', 'pc', 'mods')
STEP = np.array(IMA_STEP, dtype=np.int64)
STEP_GAME = np.minimum(STEP, 8191)                 # what tru.exe really uses (x4 then /65536*2048 = /8)
IDXT = np.array(IMA_IDX * 2, dtype=np.int64)
CAP_IDX = int(np.argmax(STEP > 8191))              # 75


def blocks_of(data):
    nb = len(data) // 36
    return np.frombuffer(data[:nb * 36], dtype=np.uint8).reshape(nb, 36)


def nibbles(b):
    nib = np.empty((len(b), 64), dtype=np.int64)
    nib[:, 0::2] = b[:, 4:] & 15; nib[:, 1::2] = b[:, 4:] >> 4
    return nib


def index_track(b):
    """step index used for each nibble position 1..63 (column 0 = header index, unused) - depends only on nibbles"""
    nib = nibbles(b); used = np.empty((len(b), 64), dtype=np.int64)
    idx = b[:, 2].astype(np.int64); used[:, 0] = idx
    for j in range(1, 64):
        used[:, j] = idx
        idx = np.clip(idx + IDXT[nib[:, j]], 0, 88)
    return used


def _sat(x):
    return np.clip(x, -32768, 32767)


def decode_game(b):
    """exact model of tru.exe 0x5957a0 for mono blocks [nb, 36] -> int16 samples"""
    nb = len(b)
    if nb == 0: return np.zeros(0, dtype=np.int16)
    nib = nibbles(b); used = index_track(b)
    m = nib & 7
    mult = 2048 * (2 * m + 1); mult = np.where(nib & 8, -mult, mult)
    d = (mult * (4 * STEP_GAME[used])) >> 16              # pmulhw: floor of the signed product / 65536
    d[:, 0] = 0                                             # lane 0 masked (nibble 0 ignored)
    hdr = (b[:, 0].astype(np.int64) | (b[:, 1].astype(np.int64) << 8)); prev = np.where(hdr >= 32768, hdr - 65536, hdr)
    out = np.empty((nb, 64), dtype=np.int64)
    for g in range(16):
        v = d[:, 4 * g:4 * g + 4].copy()
        v[:, 0] = _sat(v[:, 0] + prev)
        w = v.copy(); w[:, 1:] = _sat(v[:, 1:] + v[:, :-1])
        o = w.copy(); o[:, 2:] = _sat(w[:, 2:] + w[:, :-2])
        out[:, 4 * g:4 * g + 4] = o; prev = o[:, 3]
    return out.reshape(-1).astype(np.int16)


def decode_old(b):
    from compare_audio import ima_decode_old          # the old model (compare_audio.ima_decode is the game model since N10)
    return ima_decode_old(b.tobytes(), True)


def channel_blocks(pd):
    """PC .mul -> header (rate, total, nch) and per channel a list of (start sample, blocks [nb, 36])"""
    import mul_convert as M
    rate, w1, total, nch = struct.unpack_from('<4I', pd, 0)
    nch = max(1, nch); segs = [[] for _ in range(nch)]
    for t, a, bb, p in M.blocks(pd, '<'):
        if t != 0: continue
        nbytes = struct.unpack_from('<I', p, 0)[0]
        d = p[16:16 + nbytes]; per = len(d) // nch
        for k in range(nch): segs[k].append((a, blocks_of(d[k * per:(k + 1) * per])))
    return rate, total, nch, segs


def decode_channel(segs, fn):
    n = max(a + 64 * len(b) for a, b in segs)
    out = np.zeros(n, dtype=np.int16)
    for a, b in segs: out[a:a + 64 * len(b)] = fn(b)
    return out


def all_blocks(segs):
    return np.concatenate([b for a, b in sorted(segs, key=lambda s: s[0])])


def hf_snr(ref, err, rate, lo=4000.0, n=2048):
    """SNR in dB restricted to the band above lo Hz (frames of n samples, Hann window)"""
    m = (min(len(ref), len(err)) // n) * n
    if m == 0: return None
    win = np.hanning(n)
    R = np.abs(np.fft.rfft(ref[:m].reshape(-1, n) * win, axis=1)) ** 2
    E = np.abs(np.fft.rfft(err[:m].reshape(-1, n) * win, axis=1)) ** 2
    f = np.fft.rfftfreq(n, 1.0 / rate); sel = f >= lo
    return float(10 * np.log10(R[:, sel].sum() / max(1e-9, E[:, sel].sum())))


def snr(ref, err):
    return float(10 * np.log10((ref.astype(np.float64) ** 2).mean() / max(1e-9, (err.astype(np.float64) ** 2).mean())))


def compare(ref, blocks_seq, dec, rate):
    """ref: Xbox samples of one channel, dec: decoded PC channel; blocks_seq: blocks in sample order for index stats"""
    n = min(len(ref), len(dec)); r = ref[:n].astype(np.int64); e = dec[:n].astype(np.int64) - r
    used = index_track(blocks_seq)[:, 1:]
    hot = (used >= CAP_IDX).any(axis=1)
    nb = min(len(hot), n // 64)
    eb = e[:nb * 64].reshape(nb, 64)
    rms = lambda x: float(np.sqrt((x.astype(np.float64) ** 2).mean())) if x.size else 0.0
    return dict(snr=round(snr(r, e), 2), snr_hf=round(hf_snr(r.astype(np.float64), e.astype(np.float64), rate), 2),
                max_err=int(np.abs(e).max()), big_err=int((np.abs(e) > 4096).sum()),
                nib_idx_ge75_pct=round(100.0 * (used >= CAP_IDX).mean(), 3), blocks_idx_ge75_pct=round(100.0 * hot.mean(), 3),
                max_idx=int(used.max()), err_rms_hot=round(rms(eb[hot[:nb]]), 1), err_rms_cold=round(rms(eb[~hot[:nb]]), 1),
                dec_clipped=int((np.abs(dec[:n].astype(np.int64)) >= 32767).sum()))


def xbox_for(rel):
    """decoded Xbox source for an installed REL (language suffix _NNN -> spec 0xffffe000 | NNN)"""
    import mul_audio as MA
    xd, spec = xbox_raw_for(rel)
    rate, total, pcm = MA.xb_pcm(xd)
    return rate, total, np.clip(pcm, -32768, 32767), spec


def xbox_raw_for(rel):
    """Xbox .mul record (bytes) and language spec for an installed REL - the lookup of xbox_for"""
    import mul_audio_batch as MAB
    from archive import Archive
    from names import crc
    from convert_dlc import R, PACKS
    base, ext = os.path.splitext(rel)
    spec = None
    if ext.startswith('.mul_'):        # mul_lang_build.LANG: _001 = English = spec 0xffffffe1 (not 0xffffe001; N10)
        spec = 0xffffffe1 if int(ext[5:]) == 1 else 0xffffe000 | int(ext[5:]); rel = base + '.mul'
    if spec is None:
        xd = MAB.find_xb(rel)[0]
    else:
        xd = None
        for p in PACKS:
            A = Archive(R + p, 'be')
            rr = [x for x in A.find(crc('xenon-w\\' + rel.replace('/', '\\'))) if x['spec'] == spec]
            if rr: xd = A.read(rr[0]); break
    if xd is None:               # not in pack10 / pack11: try the other packs and the base / TU archives
        import locals as LC
        for src in ('pack1', 'pack2', 'pack20', 'tu', 'xbase', 'xbase2'):
            path, e, pre = LC.SRC[src]
            if not os.path.exists(path): continue
            A = Archive(path, e); rr = A.find(crc(pre + '\\' + rel.replace('/', '\\')))
            if spec is not None: rr = [x for x in rr if x['spec'] == spec]
            if rr: xd = A.read(rr[0]); print('  (Xbox source from %s)' % src); break
    if xd is None: raise SystemExit('no Xbox source for %s' % rel)
    return xd, spec


def measure(rel):
    pd = open(os.path.join(MODS, rel), 'rb').read()
    prate, ptotal, nch, segs = channel_blocks(pd)
    xrate, xtotal, xb, spec = xbox_for(rel)
    res = dict(file=rel, spec=hex(spec) if spec else None, pc_rate=prate, xbox_rate=xrate, pc_total=ptotal,
               xbox_total=xtotal, pc_channels=nch, xbox_channels=int(xb.shape[1]),
               xbox_clipped=int((np.abs(xb) >= 32767).sum()), channels=[])
    for k in range(nch):
        bs = all_blocks(segs[k]); ref = xb[:, min(k, xb.shape[1] - 1)]
        g = decode_channel(segs[k], decode_game); o = decode_channel(segs[k], decode_old)
        res['channels'].append(dict(game=compare(ref, bs, g, xrate), old_model=compare(ref, bs, o, xrate),
                                    game_vs_old_snr=round(snr(o.astype(np.int64), g.astype(np.int64) - o), 2)))
    return res


def coarse_lag(pc, xb, rate):
    """lag of the PC stream against the Xbox one (FFT cross-correlation, first ~23 s, +-1 s), refined +-3 by SNR"""
    n = 1 << 20; a = np.zeros(2 * n); b = np.zeros(2 * n)
    a[:min(n, len(pc))] = pc[:n]; b[:min(n, len(xb))] = xb[:n]
    cc = np.fft.irfft(np.fft.rfft(a) * np.conj(np.fft.rfft(b)))
    lags = np.r_[0:rate + 1, -rate:0]
    c0 = int(lags[np.argmax(cc[lags])]); best = None
    for lag in range(c0 - 3, c0 + 4):
        p = pc[max(0, lag):].astype(np.int64); x = xb[max(0, -lag):].astype(np.int64); m = min(len(p), len(x))
        s = snr(x[:m], p[:m] - x[:m])
        if best is None or s > best[0]: best = (s, lag)
    return best[1]


def base(argv):
    """Crystal's own PC encodes: index usage and game vs old decoder against the Xbox source"""
    import mul_audio as MA
    rows = []
    if argv[0] == 'music':
        import music_convert as MC
        pairs = MC.base_pairs(); names = sorted(pairs)[:int(argv[1])] if len(argv) > 1 else sorted(pairs)
        items = [(nm, pairs[nm]['mul'][0], pairs[nm]['mul'][1]) for nm in names]
    else:
        import mul_convention_check as MCC
        spec = int(argv[2], 16) if len(argv) > 2 else 0xffffe004
        pd = MCC.read('pcpatch', argv[1], spec) or MCC.read('pcbig', argv[1], spec)
        xd = MCC.read('xbase', argv[1], spec) or MCC.read('xbase2', argv[1], spec) or MCC.read('tu', argv[1], spec)
        items = [(argv[1] + ' %08x' % spec, xd, pd)]
    for nm, xd, pd in items:
        prate, ptotal, nch, segs = channel_blocks(pd)
        xrate, xtotal, xb = MA.xb_pcm(xd); xb = np.clip(xb, -32768, 32767)
        lag = coarse_lag(decode_channel(segs[0], decode_game), xb[:, 0], xrate) if argv[0] != 'music' else 0
        r = dict(name=nm, pc_rate=prate, xbox_rate=xrate, pc_channels=nch, lag=lag, channels=[])
        for k in range(nch):
            bs = all_blocks(segs[k]); ref = xb[:, min(k, xb.shape[1] - 1)]
            g = decode_channel(segs[k], decode_game); o = decode_channel(segs[k], decode_old)
            if lag > 0:          # PC is late by lag samples: drop them from the PC side (block stats stay approximate)
                g, o = g[lag:], o[lag:]
            elif lag < 0:
                ref = ref[-lag:]
            r['channels'].append(dict(game=compare(ref, bs, g, xrate), old_model=compare(ref, bs, o, xrate)))
        rows.append(r)
        c = r['channels']
        print('lag %+d  ' % lag, end='')
        print('%-40s ch %d  maxidx %s  nib>=75 %s %%  SNR game %s / old %s dB  HF game %s / old %s dB' % (
            nm, nch, max(x['game']['max_idx'] for x in c), max(x['game']['nib_idx_ge75_pct'] for x in c),
            min(x['game']['snr'] for x in c), min(x['old_model']['snr'] for x in c),
            min(x['game']['snr_hf'] for x in c), min(x['old_model']['snr_hf'] for x in c)))
    return rows


# ---- encoder for the game decoder -------------------------------------------------------------------------------
def _game_step(pred, idx, nib):
    m = nib & 7
    mult = 2048 * (2 * m + 1); mult = np.where(nib & 8, -mult, mult)
    pred = _sat(pred + ((mult * (4 * STEP_GAME[idx])) >> 16))
    return pred, np.clip(idx + IDXT[nib], 0, 88)


def _greedy(xb, pred, idx, j):
    """best of the 16 nibbles for sample j under the game decoder (exhaustive, exact rounding)"""
    best = np.full(len(pred), np.inf); bn = np.zeros(len(pred), dtype=np.int64)
    for a in range(16):
        p1, _ = _game_step(pred, idx, np.full(len(pred), a))
        e = (xb[:, j] - p1).astype(np.float64) ** 2
        msk = e < best; best[msk] = e[msk]; bn[msk] = a
    return bn


def encode_game_model(pcm, starts=range(89)):
    """IMA blocks for tru.exe's decoder: header sample, start index searched over `starts`, nibbles 1..63 chosen
    greedily against the EXACT game model (step cap 8191, pmulhw rounding). Sequential model; the 4-lane saturation
    only differs when a partial sum overflows (checked afterwards with decode_game)."""
    pcm = np.clip(np.asarray(pcm, dtype=np.int64), -32768, 32767)
    n = len(pcm); nb = max(1, -(-n // 64))
    x = np.empty(nb * 64, dtype=np.int64); x[:n] = pcm; x[n:] = pcm[-1] if n else 0
    xb = x.reshape(nb, 64)
    best_err = np.full(nb, np.inf); best_idx = np.zeros(nb, dtype=np.int64)
    for c in starts:
        pred = xb[:, 0].copy(); idx = np.full(nb, c, dtype=np.int64); err = np.zeros(nb)
        for j in range(1, 64):
            nib = _greedy(xb, pred, idx, j)
            pred, idx = _game_step(pred, idx, nib)
            err += (xb[:, j] - pred).astype(np.float64) ** 2
        msk = err < best_err; best_err[msk] = err[msk]; best_idx[msk] = c
    pred = xb[:, 0].copy(); idx = best_idx.copy(); nibs = np.zeros((nb, 64), dtype=np.int64)
    for j in range(1, 64):
        nib = _greedy(xb, pred, idx, j); nibs[:, j] = nib
        pred, idx = _game_step(pred, idx, nib)
    out = np.zeros((nb, 36), dtype=np.uint8)
    p16 = xb[:, 0].astype(np.int16).view(np.uint16)
    out[:, 0] = p16 & 255; out[:, 1] = p16 >> 8; out[:, 2] = best_idx
    out[:, 4:] = (nibs[:, 0::2] | (nibs[:, 1::2] << 4)).astype(np.uint8)
    return out


def encode_beam(pcm, K=16, chunk=4096):
    """IMA blocks for tru.exe's decoder by beam search per block: all 89 start indices, every step the K cheapest
    (squared error so far) of K x 16 continuations under the exact game step (cap 8191, pmulhw rounding). Unlike the
    greedy choice it sees that driving the index above 75 (no larger step there, the cap) costs many samples of too
    large steps on the way back down."""
    pcm = np.clip(np.asarray(pcm, dtype=np.int64), -32768, 32767)
    n = len(pcm); nb = max(1, -(-n // 64))
    x = np.empty(nb * 64, dtype=np.int64); x[:n] = pcm; x[n:] = pcm[-1] if n else 0
    X = x.reshape(nb, 64)
    out = np.zeros((nb, 36), dtype=np.uint8)
    A = np.arange(16, dtype=np.int64)
    MULT = np.where(A & 8, -2048 * (2 * (A & 7) + 1), 2048 * (2 * (A & 7) + 1))       # [16]
    for c0 in range(0, nb, chunk):
        xb = X[c0:c0 + chunk]; m = len(xb)
        pred = np.repeat(xb[:, :1], 89, axis=1); idx = np.tile(np.arange(89, dtype=np.int64), (m, 1))
        cost = np.zeros((m, 89)); start = idx.copy(); hist = np.zeros((m, 89, 64), dtype=np.uint8)
        rows = np.arange(m)[:, None]
        for j in range(1, 64):
            S = pred.shape[1]
            d = (MULT[None, None, :] * (4 * STEP_GAME[idx])[:, :, None]) >> 16                # [m, S, 16]
            p1 = _sat(pred[:, :, None] + d); i1 = np.clip(idx[:, :, None] + IDXT[None, None, :], 0, 88)
            c1 = cost[:, :, None] + ((xb[:, j][:, None, None] - p1).astype(np.float64)) ** 2
            c1 = c1.reshape(m, S * 16); keep = min(K, S * 16)
            sel = np.argpartition(c1, keep - 1, axis=1)[:, :keep]
            par, nibsel = sel // 16, sel % 16
            pred = p1.reshape(m, S * 16)[rows, sel]; idx = i1.reshape(m, S * 16)[rows, sel]; cost = c1[rows, sel]
            start = start[rows, par]; hist = hist[rows, par]; hist[:, :, j] = nibsel
        best = np.argmin(cost, axis=1)
        h = hist[np.arange(m), best]; st = start[np.arange(m), best]
        p16 = xb[:, 0].astype(np.int16).view(np.uint16)
        o = out[c0:c0 + m]
        o[:, 0] = p16 & 255; o[:, 1] = p16 >> 8; o[:, 2] = st
        o[:, 4:] = (h[:, 0::2] | (h[:, 1::2] << 4)).astype(np.uint8)
    return out


def write_wav(path, chans, rate):
    import wave
    n = min(len(c) for c in chans)
    data = np.stack([np.asarray(c[:n]) for c in chans], axis=1).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(data.shape[1]); w.setsampwidth(2); w.setframerate(rate); w.writeframes(data.tobytes())
    print('written %s (%d ch, %.1f s)' % (os.path.relpath(path, os.path.join(HERE, '..')), data.shape[1], n / rate))


def fix(argv):
    rel = argv[0]
    tag = argv[argv.index('--wav') + 1] if '--wav' in argv else None
    cut = (float(argv[argv.index('--cut') + 1]), float(argv[argv.index('--cut') + 2])) if '--cut' in argv else None
    enc = argv[argv.index('--enc') + 1] if '--enc' in argv else 'beam'
    K = int(argv[argv.index('--k') + 1]) if '--k' in argv else 16
    pd = open(os.path.join(MODS, rel), 'rb').read()
    prate, ptotal, nch, segs = channel_blocks(pd)
    xrate, xtotal, xb, spec = xbox_for(rel)
    print('encoder: %s%s' % (enc, ' K=%d' % K if enc == 'beam' else ''))
    res = dict(file=rel, encoder=enc, K=K, channels=[]); wavs = {'1_xbox': [], '2_pc_jetzt_wie_spiel': [], '3_pc_jetzt_altes_modell': [],
                                               '4_fix_wie_spiel': []}
    lp = float(argv[argv.index('--lowpass') + 1]) if '--lowpass' in argv else None
    gain = float(argv[argv.index('--gain') + 1]) if '--gain' in argv else 0.0
    if lp or gain: print('pre-conditioning: lowpass %s Hz, gain %+.1f dB (SNR below is against the ORIGINAL source)' % (lp, gain))
    res.update(lowpass=lp, gain=gain)
    for k in range(nch):
        ref = xb[:, min(k, xb.shape[1] - 1)]
        cur_g = decode_channel(segs[k], decode_game); cur_o = decode_channel(segs[k], decode_old)
        src = ref.astype(np.float64)
        if lp:                   # raised-cosine low-pass over lp-1000 .. lp+1000 Hz (FFT, whole channel)
            F = np.fft.rfft(src); f = np.fft.rfftfreq(len(src), 1.0 / xrate)
            w = np.clip((lp + 1000 - f) / 2000.0, 0, 1); F *= 0.5 - 0.5 * np.cos(np.pi * w)
            src = np.fft.irfft(F, len(src))
        if gain: src = src * 10 ** (gain / 20.0)
        src = np.clip(np.round(src), -32768, 32767).astype(np.int64)
        fb = encode_beam(src, K) if enc == 'beam' else encode_game_model(src); fg = decode_game(fb)
        c = dict(installed_game=compare(ref, all_blocks(segs[k]), cur_g, xrate), fixed_game=compare(ref, fb, fg, xrate),
                 fixed_old_model=compare(ref, fb, decode_old(fb), xrate))
        res['channels'].append(c)
        print('channel %d: installed (game decoder) SNR %.1f / >4k %.1f dB, max err %d, |err|>4096 %d | fixed (game decoder) '
              'SNR %.1f / >4k %.1f dB, max err %d, |err|>4096 %d' % (k, c['installed_game']['snr'], c['installed_game']['snr_hf'],
              c['installed_game']['max_err'], c['installed_game']['big_err'], c['fixed_game']['snr'], c['fixed_game']['snr_hf'],
              c['fixed_game']['max_err'], c['fixed_game']['big_err']))
        for key, sig in (('1_xbox', ref), ('2_pc_jetzt_wie_spiel', cur_g), ('3_pc_jetzt_altes_modell', cur_o), ('4_fix_wie_spiel', fg)):
            wavs[key].append(np.asarray(sig[:len(ref)], dtype=np.int16))
    if tag:
        d = os.path.join(OUT, 'wav'); os.makedirs(d, exist_ok=True)
        for key, chans in wavs.items():
            if cut: chans = [c[int(cut[0] * xrate):int(cut[1] * xrate)] for c in chans]
            write_wav(os.path.join(d, '%s_%s.wav' % (tag, key)), chans, xrate)
    return res


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    cmd = argv[0]
    if cmd == 'measure':
        allr = []
        for rel in argv[1:]:
            r = measure(rel); allr.append(r)
            print('%s  spec %s  rate PC %d / Xbox %d  total PC %d / Xbox %d  ch PC %d / Xbox %d  Xbox clipped %d' % (
                rel, r['spec'], r['pc_rate'], r['xbox_rate'], r['pc_total'], r['xbox_total'], r['pc_channels'],
                r['xbox_channels'], r['xbox_clipped']))
            for k, c in enumerate(r['channels']):
                for lab in ('game', 'old_model'):
                    m = c[lab]
                    print('  ch %d %-9s SNR %5.1f dB  >4k %5.1f dB  max err %5d  |err|>4096 %5d  nib idx>=75 %6.3f %%  '
                          'blocks %6.3f %%  err rms hot/cold %7.1f / %6.1f  clipped %d' % (
                              k, lab, m['snr'], m['snr_hf'], m['max_err'], m['big_err'], m['nib_idx_ge75_pct'],
                              m['blocks_idx_ge75_pct'], m['err_rms_hot'], m['err_rms_cold'], m['dec_clipped']))
                print('  ch %d game vs old decode: SNR %.1f dB' % (k, c['game_vs_old_snr']))
        tag = 'measure_%d' % len(allr)
        json.dump(allr, open(os.path.join(OUT, 'measure.json'), 'w'), indent=1)
    elif cmd == 'summary':       # counts from scan_installed.json and measure_all.tsv (written by scan / measure_all)
        def group(f):
            return ('cinstream' if f.startswith('cinstream/') else 'vo' if '/vo/' in f else
                    'music' if f.startswith('music/') or '/music/' in f else 'other')
        rows = json.load(open(os.path.join(OUT, 'scan_installed.json')))
        print('scan: %d files' % len(rows))
        for gname in ('cinstream', 'vo', 'music', 'other'):
            g = [r for r in rows if group(r['file']) == gname]
            if not g: continue
            print('  %-9s %3d files  game vs old < 20 dB: %3d  < 30 dB: %3d  any nibble at index >= 75: %3d  median nib>=75 %.3f %%' % (
                gname, len(g), sum(r['game_vs_old'] < 20 for r in g), sum(r['game_vs_old'] < 30 for r in g),
                sum(r['nib_ge75'] > 0 for r in g), float(np.median([r['nib_ge75'] for r in g]))))
        bm = os.path.join(OUT, 'base_music.log')      # console output of 'base music' (json only if it finished)
        if os.path.exists(bm):
            import re
            R = [re.search(r'^(\S+).*?nib>=75 ([\d.]+) %.*?SNR game (-?[\d.]+) / old (-?[\d.]+) dB', l)
                 for l in open(bm, encoding='utf-8')]
            R = [(m.group(1), *map(float, m.groups()[1:])) for m in R if m]
            d = [g - o for _, _, g, o in R]
            print('base music (Crystal): %d tracks, SNR game >= old: %d, game - old min / max %+.2f / %+.2f dB; '
                  'with nibbles at index >= 75: %d, there game - old: %s' % (
                      len(R), sum(x >= 0 for x in d), min(d), max(d), sum(r[1] > 0 for r in R),
                      ', '.join('%s %+.1f' % (r[0], r[2] - r[3]) for r in R if r[1] > 0)))
        p = os.path.join(OUT, 'measure_all.tsv')
        if os.path.exists(p):
            L = [l.rstrip('\n').split('\t') for l in open(p, encoding='utf-8')][1:]
            print('measure_all: %d files with an Xbox source' % len(L))
            for gname in ('cinstream', 'vo', 'music', 'other'):
                g = [l for l in L if group(l[0]) == gname]
                if not g: continue
                cnt = {v: sum(l[10] == v for l in g) for v in ('cap-aware', 'cap-blind', 'same')}
                print('  %-9s %3d  cap-aware %3d  cap-blind %3d  same %3d  SNR game min / median %.1f / %.1f dB  old min / median %.1f / %.1f dB' % (
                    gname, len(g), cnt['cap-aware'], cnt['cap-blind'], cnt['same'], min(float(l[3]) for l in g),
                    float(np.median([float(l[3]) for l in g])), min(float(l[4]) for l in g), float(np.median([float(l[4]) for l in g]))))
            print('  worst under the game decoder:')
            for l in sorted(L, key=lambda l: float(l[3]))[:15]:
                print('    %-66s game %5s dB  old %5s dB  %s' % (l[0], l[3], l[4], l[10]))
    elif cmd == 'diag':          # diag REL CH [S0 S1]: why does even the cap-aware encode keep large errors?
        rel, k = argv[1], int(argv[2])
        xrate, xtotal, xb, spec = xbox_for(rel)
        ref = xb[:, min(k, xb.shape[1] - 1)].astype(np.int64)
        if len(argv) > 4: ref = ref[int(float(argv[3]) * xrate):int(float(argv[4]) * xrate)]
        dx = np.abs(np.diff(ref)); lim = 15 * 8191 // 8
        print('source: %d samples, |x[j]-x[j-1]| > %d (more than the capped decoder can move in one sample): %d; '
              '> 8000: %d; |x| >= 32000: %d' % (len(ref), lim, int((dx > lim).sum()), int((dx > 8000).sum()),
                                                int((np.abs(ref) >= 32000).sum())))
        fb = encode_game_model(ref); ex = decode_game(fb).astype(np.int64)[:len(ref)]
        # the encoder's own sequential model (clamp per sample) for comparison with the exact 4-lane decoder
        nib = nibbles(fb); used = index_track(fb); m = nib & 7
        mult = np.where(nib & 8, -2048 * (2 * m + 1), 2048 * (2 * m + 1)); d = (mult * (4 * STEP_GAME[used])) >> 16
        hdr = (fb[:, 0].astype(np.int64) | (fb[:, 1].astype(np.int64) << 8)); pred = np.where(hdr >= 32768, hdr - 65536, hdr)
        seq = np.empty((len(fb), 64), dtype=np.int64); seq[:, 0] = pred
        for j in range(1, 64):
            pred = _sat(pred + d[:, j]); seq[:, j] = pred
        seq = seq.reshape(-1)[:len(ref)]
        e = ex - ref; es = seq - ref
        print('cap-aware encode: exact decoder SNR %.1f dB, |err|>4096 %d, max %d | sequential model SNR %.1f dB, '
              '|err|>4096 %d | exact vs sequential differ in %d samples (max %d)' % (
                  snr(ref, e), int((np.abs(e) > 4096).sum()), int(np.abs(e).max()), snr(ref, es),
                  int((np.abs(es) > 4096).sum()), int((ex != seq).sum()), int(np.abs(ex - seq).max())))
        big = np.abs(e) > 4096
        if big.any():
            near = np.convolve(np.abs(ref) >= 30000, np.ones(129), 'same') > 0
            print('  big errors within 64 samples of |x| >= 30000: %d of %d; next to a source step > %d: %d' % (
                int((big & near).sum()), int(big.sum()), lim, int((big & np.r_[False, dx > lim]).sum())))
    elif cmd == 'slope':         # slope dlc REL | slope base NAME.mul [SPEC]: steep steps + band levels, Xbox vs PC
        import mul_audio as MA
        if argv[1] == 'dlc':
            xrate, xtotal, xb, spec = xbox_for(argv[2]); rate = xrate
            pc = np.stack([decode_channel(s, decode_game) for s in channel_blocks(open(os.path.join(MODS, argv[2]), 'rb').read())[3]], 1)
            lag = 0; label = argv[2]
        else:
            import mul_convention_check as MCC
            spec = int(argv[3], 16) if len(argv) > 3 else 0xffffe004
            pd = MCC.read('pcpatch', argv[2], spec) or MCC.read('pcbig', argv[2], spec)
            xd = MCC.read('xbase', argv[2], spec) or MCC.read('xbase2', argv[2], spec) or MCC.read('tu', argv[2], spec)
            rate, total, xb = MA.xb_pcm(xd); xb = np.clip(xb, -32768, 32767)
            pc = np.stack([decode_channel(s, decode_game) for s in channel_blocks(pd)[3]], 1)
            lag = coarse_lag(pc[:, 0], xb[:, 0], rate); label = '%s %08x (Crystal PC, lag %+d)' % (argv[2], spec, lag)
        if lag > 0: pc = pc[lag:]
        elif lag < 0: xb = xb[-lag:]
        n = min(len(pc), len(xb)); pc = pc[:n].astype(np.int64); xb = xb[:n].astype(np.int64)
        lim = 15 * 8191 // 8; edges = [0, 2000, 4000, 6000, 8000, 10000, 12000, 14000, 16000, 22050]
        print(label)
        for k in range(min(pc.shape[1], xb.shape[1])):
            for nm, s in (('Xbox', xb[:, k]), ('PC  ', pc[:, k])):
                dx = np.abs(np.diff(s)); N = 2048; m = (len(s) // N) * N
                P = (np.abs(np.fft.rfft(s[:m].reshape(-1, N) * np.hanning(N), axis=1)) ** 2).sum(axis=0)
                f = np.fft.rfftfreq(N, 1.0 / rate)
                bands = [P[(f >= a) & (f < b)].sum() for a, b in zip(edges[:-1], edges[1:])]
                tot = sum(bands)
                print('  ch %d %s rms %6.0f  steps > %d: %6d  > 8000: %6d  band share %%: %s' % (
                    k, nm, np.sqrt((s.astype(np.float64) ** 2).mean()), lim, int((dx > lim).sum()), int((dx > 8000).sum()),
                    ' '.join('%d-%dk %.2f' % (a // 1000, b // 1000, 100 * v / tot) for a, b, v in zip(edges[:-1], edges[1:], bands))))
    elif cmd == 'decwav':        # decwav REL TAG: installed file decoded with the game model and the old model -> WAVs
        rel, tag = argv[1], argv[2]
        rate, total, nch, segs = channel_blocks(open(os.path.join(MODS, rel), 'rb').read())
        d = os.path.join(OUT, 'wav'); os.makedirs(d, exist_ok=True)
        for key, fn in (('wie_spiel', decode_game), ('altes_modell', decode_old)):
            write_wav(os.path.join(d, '%s_%s.wav' % (tag, key)), [decode_channel(s, fn) for s in segs], rate)
    elif cmd == 'newwav':        # newwav DIR REL TAG: DIR/mods/REL (e.g. the N10 re-encode) decoded like tru.exe -> TAG_5_neu_gebaut_wie_spiel.wav
        src, rel, tag = argv[1], argv[2], argv[3]
        rate, total, nch, segs = channel_blocks(open(os.path.join(src, 'mods', rel), 'rb').read())
        xrate, xtotal, xb, spec = xbox_for(rel)          # cut to the Xbox length like the _1 .. _4 WAVs
        chans = [decode_channel(s, decode_game)[:len(xb)] for s in segs]
        ref = [xb[:, min(k, xb.shape[1] - 1)] for k in range(nch)]
        for k, c in enumerate(chans):
            print('  ch %d: SNR against Xbox %.2f dB' % (k, snr(ref[k][:len(c)].astype(np.int64), c.astype(np.int64) - ref[k][:len(c)])))
        d = os.path.join(OUT, 'wav'); os.makedirs(d, exist_ok=True)
        write_wav(os.path.join(d, '%s_5_neu_gebaut_wie_spiel.wav' % tag), chans, rate)
    elif cmd == 'measure_all':   # every installed .mul* with an Xbox source: worst channel, game vs old model -> TSV
        rels = []
        for dp, dn, fn in os.walk(MODS):
            rels += [os.path.relpath(os.path.join(dp, f), MODS).replace('\\', '/') for f in sorted(fn) if '.mul' in f]
        tsv = open(os.path.join(OUT, 'measure_all.tsv'), 'w', encoding='utf-8')
        tsv.write('file\tchannels\tseconds\tsnr_game\tsnr_old\tsnr_hf_game\tsnr_hf_old\tbig_err_game\tbig_err_old\tnib_ge75_pct\tverdict\n')
        for rel in sorted(rels):
            try:
                r = measure(rel)
            except BaseException as e:
                print('%-70s SKIP %s' % (rel, str(e)[:80])); continue
            ch = r['channels']
            g = min(c['game']['snr'] for c in ch); o = min(c['old_model']['snr'] for c in ch)
            gh = min(c['game']['snr_hf'] for c in ch); oh = min(c['old_model']['snr_hf'] for c in ch)
            bg = sum(c['game']['big_err'] for c in ch); bo = sum(c['old_model']['big_err'] for c in ch)
            nib = max(c['game']['nib_idx_ge75_pct'] for c in ch)
            verdict = 'cap-aware' if g > o + 1 else 'cap-blind' if o > g + 1 else 'same'
            line = '%s\t%d\t%.1f\t%.1f\t%.1f\t%.1f\t%.1f\t%d\t%d\t%.3f\t%s' % (rel, r['pc_channels'], r['pc_total'] / r['pc_rate'],
                                                                         g, o, gh, oh, bg, bo, nib, verdict)
            tsv.write(line + '\n'); tsv.flush(); print(line)
    elif cmd == 'scan':          # every installed .mul*: where does the cap bite? (no Xbox source needed)
        rows = []
        for dp, dn, fn in os.walk(MODS):
            for f in sorted(fn):
                if '.mul' not in f: continue
                p = os.path.join(dp, f); rel = os.path.relpath(p, MODS).replace('\\', '/')
                try:
                    rate, total, nch, segs = channel_blocks(open(p, 'rb').read())
                except Exception as e:
                    print('%-70s SKIP %s' % (rel, str(e)[:60])); continue
                worst = None
                for k in range(nch):
                    bs = all_blocks(segs[k]); used = index_track(bs)[:, 1:]
                    g = decode_game(bs).astype(np.int64); o = decode_old(bs).astype(np.int64)
                    c = dict(nib_ge75=100.0 * (used >= CAP_IDX).mean(), blocks_ge75=100.0 * (used >= CAP_IDX).any(axis=1).mean(),
                             game_vs_old=snr(o, g - o), big=int((np.abs(g - o) > 4096).sum()))
                    if worst is None or c['game_vs_old'] < worst['game_vs_old']: worst = c
                rows.append(dict(file=rel, rate=rate, channels=nch, seconds=round(total / max(1, rate), 1), **worst))
                print('%-70s %5d Hz %d ch %6.1f s  nib>=75 %6.3f %%  blocks %6.3f %%  game vs old %6.1f dB  |diff|>4096 %6d' % (
                    rel, rate, nch, total / max(1, rate), worst['nib_ge75'], worst['blocks_ge75'], worst['game_vs_old'], worst['big']))
        json.dump(rows, open(os.path.join(OUT, 'scan_installed.json'), 'w'), indent=1)
    elif cmd == 'base':
        rows = base(argv[1:])
        json.dump(rows, open(os.path.join(OUT, 'base_%s.json' % argv[1]), 'w'), indent=1)
    elif cmd == 'fix':
        r = fix(argv[1:])
        nm = os.path.basename(argv[1]).replace('.', '_')
        json.dump(r, open(os.path.join(OUT, 'fix_%s.json' % nm), 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
