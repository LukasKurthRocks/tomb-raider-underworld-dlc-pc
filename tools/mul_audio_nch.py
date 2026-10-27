"""Real audio for .mul streams with any channel count, encoded for the game's IMA decoder (fix for B43/B138).

mul_audio.swap (B43) always writes stereo (block = first half L, second half R) with the FSB nibble convention. The
base game shows (docs/WINDOWS_REBUILD.md, finding 18):
  * PC channel count = Xbox stream count (1, 2, 4 or 6); every audio block holds the channels one after another,
    each as nbytes / channels bytes of 36-byte IMA blocks (64 samples); PC channel k = Xbox stream k.
  * The game's decoder outputs the block header sample, then nibbles 1..63 (nibble 0 is ignored).
So for the 19 non-stereo DLC .mul (voice lines, layered music) the B43/B138 audio is scrambled across the channel
slots. This module encodes every Xbox stream into its own slot with the game convention; stub size and every
non-audio byte stay the same.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I tools/mul_audio_nch.py XBOX.mul PC_IN.mul PC_OUT.mul
As a library: job((src, out, rel)) - same arguments and report fields as mul_audio_batch.job (used by dlc_audio_build).
"""
import sys, os, struct
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mul_audio as MA
from wave_convert import _enc_step


def ima_encode_game(pcm):
    """int 1-D samples -> [nblocks, 36] uint8 IMA blocks for the game's decoder (header sample + nibbles 1..63).
    Same encoder as wave_convert.ima_encode_fsb (index warm-up from the previous block); only the nibble positions
    differ: the nibble of sample j (1..63) goes to position j, position 0 stays 0."""
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


def swap(xd, pd):
    """replace the IMA data of every audio block of pd (silent stub) with the decoded Xbox streams, one per channel"""
    rate, total, pcm = MA.xb_pcm(xd)
    nch = struct.unpack_from('<I', pd, 12)[0]
    if pcm.shape[1] != nch:
        raise ValueError('channels: Xbox streams %d, PC header %d' % (pcm.shape[1], nch))
    blocks = MA.pc_audio_blocks(pd)
    n = max(a + (struct.unpack_from('<I', p, 0)[0] // (36 * nch)) * 64 for t, a, p in blocks)
    if len(pcm) < n: pcm = np.vstack([pcm, np.zeros((n - len(pcm), nch), dtype=np.int32)])
    enc = [ima_encode_game(pcm[:n, k]) for k in range(nch)]
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
    return bytes(out), dict(rate=rate, xb_total=total, samples=len(pcm), channels=nch, blocks=nsw, convention='game')


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
    xd = open(sys.argv[1], 'rb').read(); pd = open(sys.argv[2], 'rb').read()
    o, info = swap(xd, pd); open(sys.argv[3], 'wb').write(o); print(info)
