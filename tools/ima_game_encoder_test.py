"""Round-trip test of the game-model IMA encoder (tools/mul_audio_nch.encode_game, fix N10).

For every file: the decoded Xbox source of an installed ../data/pc/mods/REL (tools/f13_sibilants.xbox_for), per channel
  * encoded with encode_game (default) and with the old ima_encode_blind;
  * BIT-EXACT check: the encoder's own decoder model (model=True) must equal f13_sibilants.decode_game (the reference
    model of tru.exe 0x5957a0 from the finding) and mul_audio_nch.decode_game sample for sample;
  * error statistics of decode_game(encode(x)) against x: SNR, SNR above 4 kHz, max |error|, |error| > 4096.
Plus synthetic signals that drive the decoder into saturation (full-scale square waves, clipped noise), where the
4-lane MMX sums differ from a sequential model.

Usage (from the repository root, output work/f13_sibilants/n10_roundtrip.json):
  ../bin/pyt -t 1800 tools/ima_game_encoder_test.py [REL ...] [--k 16]
  default REL: the 4 listening examples of docs/Befund-S-Laute.md + the English Zip radio line
"""
import sys, os, json, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mul_audio_nch as MN
import f13_sibilants as F

DEFAULT = ['cinstream/pdlc1_010_intro.mul_004', 'audio/streams/vo/dlc2/doppelganger/i_dg_pdlc2_mach_02.mul',
           'audio/streams/vo/dlc1/lara/c_lara_1_pdlc1_invasion_01.mul', 'audio/streams/vo/dlc1/lara/c_lara_2_pdlc1_water_01.mul_004',
           'audio/streams/vo/dlc1/zip/c_zip_1_pdlc1_invasion_01.mul']


def stats(x, dec, rate):
    n = len(x); r = np.asarray(x, dtype=np.int64); e = dec[:n].astype(np.int64) - r
    return dict(snr=round(F.snr(r, e), 2), snr_hf=round(F.hf_snr(r.astype(np.float64), e.astype(np.float64), rate), 2)
                if n >= 2048 else None, max_err=int(np.abs(e).max()), big_err=int((np.abs(e) > 4096).sum()))


def check(x, rate, K):
    t0 = time.time()
    blocks, model = MN.encode_game(x, K=K, model=True)
    t1 = time.time()
    ref = F.decode_game(blocks).astype(np.int64); mine = MN.decode_game(blocks).astype(np.int64)
    exact = bool(np.array_equal(model.astype(np.int64), ref)) and bool(np.array_equal(mine, ref))
    beam_b, beam_m, _ = MN.encode_game_beam(x, K=K, model=True)
    exact_beam = bool(np.array_equal(beam_m.astype(np.int64), F.decode_game(beam_b).astype(np.int64)))
    old = MN.ima_encode_blind(x)
    res = dict(samples=len(x), seconds_encode=round(t1 - t0, 1), model_equals_decode_game=exact,
               beam_model_equals_decode_game=exact_beam,
               model_mismatch=int((model.astype(np.int64) != ref).sum()),
               new_game=stats(x, ref, rate), beam_only_game=stats(x, F.decode_game(beam_b), rate),
               old_game=stats(x, F.decode_game(old), rate), old_old_model=stats(x, F.decode_old(old), rate),
               blocks_from_old=None)
    res['blocks_from_old'] = int(np.all(blocks == old, axis=1).sum())
    return res


def synthetic():
    rng = np.random.default_rng(1104)
    sig = {'square_full_scale_1k': np.where(np.arange(44100) // 22 % 2, 32767, -32768),
           'square_full_scale_5k': np.where(np.arange(44100) // 4 % 2, 32767, -32768),
           'noise_clipped': np.clip(rng.normal(0, 30000, 44100), -32768, 32767).astype(np.int64),
           'sine_8k_full': np.round(32767 * np.sin(2 * np.pi * 8000 * np.arange(44100) / 44100)).astype(np.int64),
           'silence': np.zeros(44100, dtype=np.int64)}
    return sig


def main(argv):
    K = 16
    if '--k' in argv:
        k = argv.index('--k'); K = int(argv[k + 1]); del argv[k:k + 2]
    rels = argv or DEFAULT
    out = dict(K=K, files=[], synthetic={})
    allok = True
    for nm, x in synthetic().items():
        r = check(x, 44100, K); out['synthetic'][nm] = r; allok &= r['model_equals_decode_game'] and r['beam_model_equals_decode_game']
        print('synthetic %-22s exact %s / beam %s  mismatch %d  new SNR %6.2f dB  old (game decoder) %6.2f dB  %.1f s' % (
            nm, r['model_equals_decode_game'], r['beam_model_equals_decode_game'], r['model_mismatch'],
            r['new_game']['snr'], r['old_game']['snr'], r['seconds_encode']), flush=True)
    for rel in rels:
        rate, total, xb, spec = F.xbox_for(rel)
        fr = dict(file=rel, rate=rate, channels=[])
        for k in range(xb.shape[1]):
            r = check(xb[:, k], rate, K); fr['channels'].append(r)
            allok &= r['model_equals_decode_game'] and r['beam_model_equals_decode_game']
            print('%s ch %d: exact %s / beam %s (mismatch %d) | new SNR %.2f / >4k %.2f dB max %d big %d | beam only %.2f | '
                  'old under game %.2f (old model %.2f) | blocks taken from old %d | %.1f s' % (
                      rel, k, r['model_equals_decode_game'], r['beam_model_equals_decode_game'], r['model_mismatch'],
                      r['new_game']['snr'], r['new_game']['snr_hf'], r['new_game']['max_err'], r['new_game']['big_err'],
                      r['beam_only_game']['snr'], r['old_game']['snr'], r['old_old_model']['snr'], r['blocks_from_old'],
                      r['seconds_encode']), flush=True)
        out['files'].append(fr)
    out['all_exact'] = bool(allok)
    print('ALL BIT-EXACT' if allok else 'MISMATCH FOUND')
    os.makedirs(F.OUT, exist_ok=True)
    json.dump(out, open(os.path.join(F.OUT, 'n10_roundtrip.json'), 'w'), indent=1)
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
