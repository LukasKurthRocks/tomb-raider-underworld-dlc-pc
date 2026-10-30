"""Measure the IMA re-encoding of a DLC cinematic stream against its decoded Xbox source (read-only; finding 43
follow-up: the German intro sounds noisy in places). Encoders compared, both for the game's decoder (header sample,
nibbles 1..63; decoded with tools/compare_audio.ima_decode):
  current  tools/mul_audio_nch.ima_encode_game (start index of a block = warm-up over the previous block)
  search   the same greedy nibbles, but every block's start index (free in the block header) chosen from all 89 by
           the smallest squared error over the block - helps where the signal jumps after a quiet block (speech)
  lookahead  search + per sample the nibble chosen with one sample of lookahead (16 x 16 candidates)
Per channel: SNR in dB, the largest single error, and the share of blocks whose worst error exceeds 4096.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/ima_encoder_check.py pack10|pack11 NAME.mul [SPEC_HEX] [--write OUT]  (default spec ffffe004 = German)
  --write OUT: no measurement, write the PC .mul (as mul_lang_build) with the lookahead encoder - a listening test
  --write extras: --gain DB (scale before encoding, e.g. -6) and --convention fsb (nibbles 0..62, FSB encoder)
  --wav DIR: no measurement, write <name>_<lang>_xbox / _current / _lookahead .wav (listening outside the game);
             NAME may also be a voice stream path, e.g. audiostreamsodlc1aralara_1_pdlc1_invasion_01.mul
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mul_audio as MA, mul_audio_nch as MN
from wave_convert import _enc_step
from compare_audio import ima_decode


def encode_search(pcm):
    """like mul_audio_nch.ima_encode_game, start index per block by exhaustive search (0..88)"""
    pcm = np.asarray(pcm, dtype=np.int32)
    n = len(pcm); nb = max(1, -(-n // 64))
    x = np.empty(nb * 64, dtype=np.int32); x[:n] = pcm; x[n:] = pcm[-1] if n else 0
    x = np.clip(x, -32768, 32767).reshape(nb, 64)
    best_err = np.full(nb, np.inf); best_idx = np.zeros(nb, dtype=np.int32)
    for c in range(89):
        pred = x[:, 0].copy(); idx = np.full(nb, c, dtype=np.int32); err = np.zeros(nb)
        for j in range(1, 64):
            pred, idx, _ = _enc_step(x[:, j], pred, idx)
            err += (x[:, j] - pred).astype(np.float64) ** 2
        m = err < best_err; best_err[m] = err[m]; best_idx[m] = c
    pred = x[:, 0].copy(); idx = best_idx.copy()
    out = np.zeros((nb, 36), dtype=np.uint8)
    p16 = pred.astype(np.int16).view(np.uint16)
    out[:, 0] = p16 & 255; out[:, 1] = p16 >> 8; out[:, 2] = best_idx
    nibs = np.zeros((nb, 64), dtype=np.uint8)
    for j in range(1, 64):
        pred, idx, nib = _enc_step(x[:, j], pred, idx)
        nibs[:, j] = nib
    out[:, 4:] = nibs[:, 0::2] | (nibs[:, 1::2] << 4)
    return out


def _step_nib(s, pred, idx, nib):
    """decoder step with a GIVEN nibble (vectorised) -> new pred, new idx"""
    from wave_convert import _ST, _IX
    step = _ST[idx]
    diff = (step >> 3) + np.where(nib & 1, step >> 2, 0) + np.where(nib & 2, step >> 1, 0) + np.where(nib & 4, step, 0)
    pred = np.clip(pred + np.where(nib & 8, -diff, diff), -32768, 32767)
    return pred, np.clip(idx + _IX[nib & 7], 0, 88)


def encode_lookahead(pcm):
    """start index by search (as encode_search), then per sample the nibble (of 16) that minimises
    e(j)^2 + min over the next nibble e(j+1)^2 - one step of lookahead instead of the greedy choice"""
    pcm = np.asarray(pcm, dtype=np.int32)
    n = len(pcm); nb = max(1, -(-n // 64))
    x = np.empty(nb * 64 + 1, dtype=np.int32); x[:n] = pcm; x[n:] = pcm[-1] if n else 0
    x = np.clip(x, -32768, 32767)
    xb = x[:nb * 64].reshape(nb, 64); nxt = np.append(xb[:, 1:], xb[:, -1:], axis=1)
    idx0 = encode_search(pcm)[:, 2].astype(np.int32)
    pred = xb[:, 0].copy(); idx = idx0.copy()
    nibs = np.zeros((nb, 64), dtype=np.uint8)
    for j in range(1, 64):
        best = np.full(nb, np.inf); bn = np.zeros(nb, dtype=np.int32)
        for a in range(16):
            p1, i1 = _step_nib(None, pred, idx, np.full(nb, a))
            e1 = (xb[:, j] - p1).astype(np.float64) ** 2
            if j < 63:
                e2 = np.full(nb, np.inf)
                for b in range(16):
                    p2, _ = _step_nib(None, p1, i1, np.full(nb, b))
                    e2 = np.minimum(e2, (nxt[:, j] - p2).astype(np.float64) ** 2)
                e1 = e1 + e2
            m = e1 < best; best[m] = e1[m]; bn[m] = a
        pred, idx = _step_nib(None, pred, idx, bn); nibs[:, j] = bn
    out = np.zeros((nb, 36), dtype=np.uint8)
    p16 = xb[:, 0].astype(np.int16).view(np.uint16)
    out[:, 0] = p16 & 255; out[:, 1] = p16 >> 8; out[:, 2] = idx0
    out[:, 4:] = nibs[:, 0::2] | (nibs[:, 1::2] << 4)
    return out


def measure(ref, blocks):
    dec = ima_decode(blocks.tobytes(), True).astype(np.int64)[:len(ref)]
    r = ref.astype(np.int64)[:len(dec)]
    d = r - dec
    snr = 10 * np.log10((r.astype(np.float64) ** 2).mean() / max(1e-9, (d.astype(np.float64) ** 2).mean()))
    nb = len(d) // 64
    worst = np.abs(d[:nb * 64]).reshape(nb, 64).max(axis=1)
    return snr, int(np.abs(d).max()), 100.0 * (worst > 4096).mean()


def main(argv):
    from archive import Archive
    from names import crc
    from convert_dlc import R, PACKS
    out = wav = None
    if '--write' in argv: k = argv.index('--write'); out = argv[k + 1]; del argv[k:k + 2]
    if '--wav' in argv: k = argv.index('--wav'); wav = argv[k + 1]; del argv[k:k + 2]
    gain, conv = 0.0, 'game'
    if '--gain' in argv: k = argv.index('--gain'); gain = float(argv[k + 1]); del argv[k:k + 2]
    if '--convention' in argv: k = argv.index('--convention'); conv = argv[k + 1]; del argv[k:k + 2]
    pack, name = argv[0], argv[1]; spec = int(argv[2], 16) if len(argv) > 2 else 0xffffe004
    A = Archive(R + [p for p in PACKS if p.endswith('/%s.000' % pack)][0], 'be')
    full = 'xenon-w\\' + name if '\\' in name else 'xenon-w\\cinstream\\' + name       # voice: audio\streams\...
    rec = next(r for r in A.find(crc(full)) if r['spec'] == spec)
    if wav:       # listening test outside the game: Xbox source, current encoder, lookahead encoder as WAV files
        import wave
        rate, total, pcm = MA.xb_pcm(A.read(rec))
        base = os.path.join(wav, '%s_%03x' % (os.path.splitext(name.split('\\')[-1])[0], spec & 0xfff))
        os.makedirs(wav, exist_ok=True)
        for label, enc in (('xbox', None), ('current', MN.ima_encode_game), ('lookahead', encode_lookahead)):
            chans = []
            for k in range(pcm.shape[1]):
                ch = np.clip(pcm[:, k], -32768, 32767)
                chans.append(ch if enc is None else ima_decode(enc(ch).tobytes(), True)[:len(ch)])
            data = np.stack(chans, axis=1).astype('<i2')
            with wave.open('%s_%s.wav' % (base, label), 'wb') as w:
                w.setnchannels(data.shape[1]); w.setsampwidth(2); w.setframerate(rate); w.writeframes(data.tobytes())
            print('written %s_%s.wav (%d channel(s), %.1f s)' % (base, label, data.shape[1], len(data) / rate))
        return
    if out:       # listening test: the PC .mul as tools/mul_lang_build.py writes it, but with the lookahead encoder
        import mul_convert as M, dlc_generic as DG
        xd = A.read(rec); pd = M.convert(xd, DG.DlcIds(None, None))
        enc = encode_lookahead
        if conv == 'fsb':        # FSB nibble convention (nibbles 0..62) instead of the game's (finding 18)
            import wave_convert as WC
            enc = lambda p: np.frombuffer(WC.ima_encode_fsb(p)[0], dtype=np.uint8).reshape(-1, 36)
        g = 10 ** (gain / 20.0); base_enc = enc
        enc = (lambda p: base_enc(np.clip(np.round(np.asarray(p) * g), -32768, 32767).astype(np.int32))) if gain else base_enc
        MN.ima_encode_game = enc          # swap() looks the encoder up at call time
        o, info = MN.swap(xd, pd)
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); open(out, 'wb').write(o)
        print('written %s (%d bytes, %s)' % (out, len(o), info))
        return
    rate, total, pcm = MA.xb_pcm(A.read(rec))
    print('%s spec %08x: %d Hz, %d samples, %d channel(s)' % (name, spec, rate, len(pcm), pcm.shape[1]))
    for k in range(pcm.shape[1]):
        ch = np.clip(pcm[:, k], -32768, 32767)
        for label, enc in (('current', MN.ima_encode_game), ('search', encode_search), ('lookahead', encode_lookahead)):
            snr, mx, share = measure(ch, enc(ch))
            print('  channel %d %-9s SNR %5.1f dB  max error %5d  blocks with error > 4096: %.2f %%' % (k, label, snr, mx, share))


if __name__ == '__main__':
    main(sys.argv[1:])
