"""Real audio for .mul streams with any channel count, encoded for the game's IMA decoder (fix for B43/B138).

mul_audio.swap (B43) always writes stereo (block = first half L, second half R) with the FSB nibble convention. The
base game shows (docs/WINDOWS_REBUILD.md, finding 18):
  * PC channel count = Xbox stream count (1, 2, 4 or 6); every audio block holds the channels one after another,
    each as nbytes / channels bytes of 36-byte IMA blocks (64 samples); PC channel k = Xbox stream k.
  * The game's decoder outputs the block header sample, then nibbles 1..63 (nibble 0 is ignored).
So for the 19 non-stereo DLC .mul (voice lines, layered music) the B43/B138 audio is scrambled across the channel
slots. This module encodes every Xbox stream into its own slot with the game convention; stub size and every
non-audio byte stay the same.

Encoder (fix N10, docs/Befund-S-Laute.md in the workspace, WINDOWS_REBUILD finding 18 note "game-model IMA encoder"):
tru.exe decodes .mul streams with its own MMX IMA decoder (0x5957a0, tables built at 0x595670) that CAPS the step at
8191 (index 75..88 all become 8191), computes diff = pmulhw(+-2048*(2n+1), 4*step) = floor(+-(2n+1)*step/8) and adds
4 samples at a time with saturating prefix sums. The default encoder ('game') models exactly that decoder: beam
search per block (all 89 start indices, a wider beam for the first samples, then the K best paths) on the exact
4-lane decoder, plus per block the better of that and the old encode under the same decoder. Its internal decoder
model equals decode_game sample for sample (checked by tools/ima_game_encoder_test.py). The old cap-blind encoder
(standard IMA steps up to 32767, shift-sum diffs) stays as ima_encode_blind: environment TRUDLC_IMA_ENCODER=blind or
swap(..., encoder='blind') selects it (only for reproducing old builds / numbers).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I tools/mul_audio_nch.py XBOX.mul PC_IN.mul PC_OUT.mul [--encoder game|blind]
As a library: job((src, out, rel)) - same arguments and report fields as mul_audio_batch.job (used by dlc_audio_build).
"""
import sys, os, struct
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mul_audio as MA
from wave_convert import _enc_step
from audio_parse import IMA_STEP, IMA_IDX

# ---- tru.exe's .mul IMA decoder (0x5957a0) --------------------------------------------------------------------------
STEP_GAME = np.minimum(np.array(IMA_STEP, dtype=np.int64), 8191)   # cap at start-up (cmp 0x1fff / jle), then x4
IDX16 = np.array(IMA_IDX * 2, dtype=np.int64)
_A16 = np.arange(16, dtype=np.int64)
MULT16 = np.where(_A16 & 8, -2048 * (2 * (_A16 & 7) + 1), 2048 * (2 * (_A16 & 7) + 1))   # table 0xcd3fd0


def _sat(x):
    return np.clip(x, -32768, 32767)


def decode_game(blocks):
    """exact model of tru.exe 0x5957a0: mono IMA blocks ([nb, 36] uint8 or bytes) -> int16 samples (64 per block).
    Header: sample (int16) + step index (byte 2); nibble 0 is ignored (lane 0 masked), samples 1..63 from nibbles
    1..63; step min(IMA_STEP[i], 8191); diff = (mult * 4 * step) >> 16; per group of 4 samples (MMX)
    o0 = sat(prev + d0), o1 = sat(o0 + d1), o2 = sat(o0 + sat(d1 + d2)), o3 = sat(o1 + sat(d2 + d3))."""
    b = blocks if isinstance(blocks, np.ndarray) else np.frombuffer(blocks[:len(blocks) // 36 * 36], dtype=np.uint8).reshape(-1, 36)
    nb = len(b)
    if nb == 0: return np.zeros(0, dtype=np.int16)
    nib = np.empty((nb, 64), dtype=np.int64)
    nib[:, 0::2] = b[:, 4:] & 15; nib[:, 1::2] = b[:, 4:] >> 4
    idx = np.clip(b[:, 2].astype(np.int64), 0, 88)
    d = np.zeros((nb, 64), dtype=np.int64)
    for j in range(1, 64):
        d[:, j] = (MULT16[nib[:, j]] * (4 * STEP_GAME[idx])) >> 16
        idx = np.clip(idx + IDX16[nib[:, j]], 0, 88)
    hdr = b[:, 0].astype(np.int64) | (b[:, 1].astype(np.int64) << 8); prev = np.where(hdr >= 32768, hdr - 65536, hdr)
    out = np.empty((nb, 64), dtype=np.int64)
    for g in range(16):
        v = d[:, 4 * g:4 * g + 4].copy()
        v[:, 0] = _sat(v[:, 0] + prev)
        w = v.copy(); w[:, 1:] = _sat(v[:, 1:] + v[:, :-1])
        o = w.copy(); o[:, 2:] = _sat(w[:, 2:] + w[:, :-2])
        out[:, 4 * g:4 * g + 4] = o; prev = o[:, 3]
    return out.reshape(-1).astype(np.int16)


def _pad_blocks(pcm):
    pcm = np.clip(np.asarray(pcm, dtype=np.int64), -32768, 32767)
    n = len(pcm); nb = max(1, -(-n // 64))
    x = np.empty(nb * 64, dtype=np.int64); x[:n] = pcm; x[n:] = pcm[-1] if n else 0
    return x.reshape(nb, 64)


def _pack(xb0, start, nibs):
    out = np.zeros((len(xb0), 36), dtype=np.uint8)
    p16 = xb0.astype(np.int16).view(np.uint16)
    out[:, 0] = p16 & 255; out[:, 1] = p16 >> 8; out[:, 2] = start
    out[:, 4:] = (nibs[:, 0::2] | (nibs[:, 1::2] << 4)).astype(np.uint8)
    return out


def encode_game_beam(pcm, K=16, K0=128, J0=8, chunk=2048, model=False):
    """IMA blocks for tru.exe's decoder by beam search per block on the EXACT decoder (cap 8191, pmulhw rounding,
    4-lane saturating sums). State per path: last output o[j-1], o[j-2], last diff d[j-1], step index; the base of
    sample j is o[j-1] for j % 4 in (0, 1) and o[j-2] + d[j-1] for j % 4 in (2, 3) (see decode_game). All 89 start
    indices, the K0 cheapest paths (squared error so far) for samples 1..J0-1, then K. model=True also returns the
    encoder's own decoded samples (must equal decode_game of the blocks) and the squared error per block."""
    X = _pad_blocks(pcm); nb = len(X)
    out = np.zeros((nb, 36), dtype=np.uint8); dec = np.zeros((nb, 64), dtype=np.int64); sse = np.zeros(nb)
    for c0 in range(0, nb, chunk):
        xb = X[c0:c0 + chunk]; m = len(xb); rows = np.arange(m)[:, None]
        idx = np.tile(np.arange(89, dtype=np.int64), (m, 1))
        o1 = np.repeat(xb[:, :1], 89, axis=1); o2 = o1.copy(); dl = np.zeros_like(o1)
        cost = np.zeros((m, 89)); start = idx.copy()
        hist = np.zeros((m, 89, 64), dtype=np.uint8); outs = np.zeros((m, 89, 64), dtype=np.int16); outs[:, :, 0] = xb[:, :1]
        for j in range(1, 64):
            S = idx.shape[1]
            d = (MULT16[None, None, :] * (4 * STEP_GAME[idx])[:, :, None]) >> 16                 # [m, S, 16]
            base = o1 if j % 4 in (0, 1) else o2 + dl
            p1 = _sat(base[:, :, None] + d)
            c1 = (cost[:, :, None] + ((xb[:, j][:, None, None] - p1).astype(np.float64)) ** 2).reshape(m, S * 16)
            keep = min(K0 if j < J0 else K, S * 16)
            sel = np.argpartition(c1, keep - 1, axis=1)[:, :keep]
            par, nsel = sel // 16, sel % 16
            o2 = o1[rows, par]; dl = d.reshape(m, S * 16)[rows, sel]; o1 = p1.reshape(m, S * 16)[rows, sel]
            idx = np.clip(idx[rows, par] + IDX16[nsel], 0, 88); cost = c1[rows, sel]
            start = start[rows, par]; hist = hist[rows, par]; hist[:, :, j] = nsel
            outs = outs[rows, par]; outs[:, :, j] = o1
        best = np.argmin(cost, axis=1); r = np.arange(m)
        out[c0:c0 + m] = _pack(xb[:, 0], start[r, best], hist[r, best].astype(np.int64))
        dec[c0:c0 + m] = outs[r, best]; sse[c0:c0 + m] = cost[r, best]
    return (out, dec.reshape(-1), sse) if model else out


def ima_encode_blind(pcm):
    """OLD encoder (cap-blind): int 1-D samples -> [nblocks, 36] uint8 IMA blocks, header sample + nibbles 1..63.
    Same encoder as wave_convert.ima_encode_fsb (index warm-up from the previous block, standard IMA steps up to
    32767); only the nibble positions differ: the nibble of sample j (1..63) goes to position j, position 0 stays 0.
    tru.exe caps the step at 8191, so loud high-frequency parts (sibilants) crackle with this encode."""
    pcm = np.asarray(pcm, dtype=np.int32)
    n = len(pcm); nb = max(1, -(-n // 64))
    x = np.empty(nb * 64, dtype=np.int32); x[:n] = pcm; x[n:] = pcm[-1] if n else 0
    x = np.clip(x, -32768, 32767).reshape(nb, 64)
    idx = np.zeros(nb, dtype=np.int32)
    if nb > 1:
        pred = x[:-1, 0].copy(); i2 = np.zeros(nb - 1, dtype=np.int32)
        for j in range(1, 64):
            pred, i2, _ = _enc_step(x[:-1, j], pred, i2)
        idx[1:] = i2
    pred = x[:, 0].copy()
    out = np.zeros((nb, 36), dtype=np.uint8)
    p16 = pred.astype(np.int16).view(np.uint16)
    out[:, 0] = p16 & 255; out[:, 1] = p16 >> 8; out[:, 2] = idx
    nibs = np.zeros((nb, 64), dtype=np.uint8)
    for j in range(1, 64):
        pred, idx, nib = _enc_step(x[:, j], pred, idx)
        nibs[:, j] = nib
    out[:, 4:] = nibs[:, 0::2] | (nibs[:, 1::2] << 4)
    return out


def encode_game(pcm, K=16, model=False):
    """default encoder: per block the better (squared error under decode_game) of encode_game_beam and the old
    blind encode decoded by the game - never worse than the old encode in any block"""
    X = _pad_blocks(pcm)
    bb, bd, bs = encode_game_beam(pcm, K=K, model=True)
    ob = ima_encode_blind(pcm); od = decode_game(ob).astype(np.int64).reshape(-1, 64)
    os_ = ((X - od).astype(np.float64) ** 2).sum(axis=1)
    use = os_ < bs
    out = np.where(use[:, None], ob, bb); dec = np.where(use[:, None], od, bd.reshape(-1, 64))
    return (out, dec.reshape(-1)) if model else out


def ima_encode_game(pcm, encoder=None):
    """int 1-D samples -> [nblocks, 36] uint8 IMA blocks for the game's decoder (header sample + nibbles 1..63).
    encoder: 'game' (default, models tru.exe's decoder exactly) or 'blind' (the old encoder); None = environment
    TRUDLC_IMA_ENCODER, else 'game'. ima_encoder_check.py replaces this function for its experiments."""
    enc = encoder or os.environ.get('TRUDLC_IMA_ENCODER') or 'game'
    if enc == 'blind': return ima_encode_blind(pcm)
    if enc != 'game': raise ValueError('encoder must be game or blind, not %r' % enc)
    return encode_game(pcm)


def swap(xd, pd, encoder=None):
    """replace the IMA data of every audio block of pd (silent stub) with the decoded Xbox streams, one per channel"""
    rate, total, pcm = MA.xb_pcm(xd)
    nch = struct.unpack_from('<I', pd, 12)[0]
    if pcm.shape[1] != nch:
        raise ValueError('channels: Xbox streams %d, PC header %d' % (pcm.shape[1], nch))
    blocks = MA.pc_audio_blocks(pd)
    n = max(a + (struct.unpack_from('<I', p, 0)[0] // (36 * nch)) * 64 for t, a, p in blocks)
    if len(pcm) < n: pcm = np.vstack([pcm, np.zeros((n - len(pcm), nch), dtype=np.int32)])
    encn = encoder or os.environ.get('TRUDLC_IMA_ENCODER') or 'game'
    enc = [ima_encode_game(pcm[:n, k]) if encoder is None else ima_encode_game(pcm[:n, k], encoder) for k in range(nch)]
    out = bytearray(pd); o = 0x800; nsw = 0
    while o + 16 <= len(out):
        t, sz, a, b = struct.unpack_from('<4I', out, o)
        if t == 0:
            nbytes = struct.unpack_from('<I', out, o + 16)[0]
            k0, nb = a // 64, nbytes // (36 * nch)
            assert a % 64 == 0 and nbytes % (36 * nch) == 0 and 16 + nbytes <= sz
            out[o + 32:o + 32 + nbytes] = b''.join(e[k0:k0 + nb].tobytes() for e in enc); nsw += 1
        o += 16 + sz
    assert o == len(out) and len(out) == len(pd)
    return bytes(out), dict(rate=rate, xb_total=total, samples=len(pcm), channels=nch, blocks=nsw, convention='game',
                            encoder=encn)


def job(args):
    """(src, out, rel) -> report dict, like mul_audio_batch.job"""
    import mul_audio_batch as MAB
    src, out, rel = args
    pd = open(src, 'rb').read()
    xd, pack, sp, specs = MAB.find_xb(rel)
    r = dict(file=rel, pack=pack, spec=hex(sp) if sp else None, variants=specs)
    if xd is None: r['status'] = 'SKIP no Xbox source'; return r
    try:
        o, info = swap(xd, pd)
    except Exception as e:
        r['status'] = 'SKIP ' + str(e)[:120]; return r
    r.update(info)
    if len(o) != len(pd): r['status'] = 'SKIP size'; return r
    os.makedirs(os.path.dirname(out), exist_ok=True); open(out, 'wb').write(o)
    r['status'] = 'OK'; return r


if __name__ == '__main__':
    a = sys.argv[1:]; e = None
    if '--encoder' in a:
        k = a.index('--encoder'); e = a[k + 1]; del a[k:k + 2]
    xd = open(a[0], 'rb').read(); pd = open(a[1], 'rb').read()
    o, info = swap(xd, pd, e); open(a[2], 'wb').write(o); print(info)
