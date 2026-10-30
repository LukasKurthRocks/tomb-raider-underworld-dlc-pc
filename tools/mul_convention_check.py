"""Which IMA nibble convention does the PC game use for its CINEMATIC streams? (read-only; finding 43 follow-up: in
game Lara's "s" sounds crackle in the German DLC 1 intro, while our decoded WAVs sound like the Xbox source).
Finding 18 fixed the convention ('game': header sample, nibbles 1..63) on base-game MUSIC; this checks base-game
cinematics (Crystal's own PC encodes): the PC .mul decoded with both conventions against the decoded Xbox record
of the same name and language, per channel (coarse lag by cross-correlation, then +-3 samples); plus the same on the first difference of the
signal (high frequencies - where a convention mismatch hurts most, e.g. sibilants).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/mul_convention_check.py NAME.mul [SPEC_HEX]     (default ffffe004 = German)
"""
import sys, os, struct
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC, mul_audio as MA
from archive import Archive
from names import crc
from compare_audio import mul_pcm


def read(src, name, spec):
    path, e, pre = LC.SRC[src]
    A = Archive(path, e)
    r = [x for x in A.find(crc('%s\\cinstream\\%s' % (pre, name))) if x['spec'] == spec]
    return A.read(r[-1]) if r else None


def snr(a, b):
    n = min(len(a), len(b)); a = a[:n].astype(np.float64); b = b[:n].astype(np.float64)
    return 10 * np.log10((b ** 2).mean() / max(1e-9, ((a - b) ** 2).mean()))


def main(argv):
    name = argv[0]; spec = int(argv[1], 16) if len(argv) > 1 else 0xffffe004
    pd = read('pcpatch', name, spec) or read('pcbig', name, spec)
    xd = read('xbase', name, spec) or read('xbase2', name, spec) or read('tu', name, spec)
    if pd is None or xd is None: raise SystemExit('%s spec %08x: PC %s, Xbox %s' % (name, spec, pd is not None, xd is not None))
    rate, total, xb = MA.xb_pcm(xd)
    print('%s spec %08x: %d Hz, Xbox %d samples x %d, PC channels %d' % (name, spec, rate, len(xb), xb.shape[1], struct.unpack_from('<I', pd, 12)[0]))
    # coarse lag of PC vs Xbox (the streams can be offset): FFT cross-correlation of channel 0, first ~23 s, +-1 s
    pc0 = mul_pcm(pd, True)[:, 0].astype(np.float64); x0 = xb[:, 0].astype(np.float64)
    n = 1 << 20; a = np.zeros(2 * n); b = np.zeros(2 * n)
    a[:min(n, len(pc0))] = pc0[:n]; b[:min(n, len(x0))] = x0[:n]
    cc = np.fft.irfft(np.fft.rfft(a) * np.conj(np.fft.rfft(b)))
    lags = np.r_[0:rate + 1, -rate:0]
    coarse = int(lags[np.argmax(cc[lags])])
    print('  coarse lag (PC vs Xbox): %+d samples' % coarse)
    for conv in ('game', 'fsb'):
        pc = mul_pcm(pd, conv == 'game')
        for k in range(min(pc.shape[1], xb.shape[1])):
            best = None
            for lag in range(coarse - 3, coarse + 4):
                a = pc[max(0, lag):, k]; b = xb[max(0, -lag):, k]
                s = snr(a, b)
                if best is None or s > best[0]: best = (s, lag, snr(np.diff(a.astype(np.int64)), np.diff(b.astype(np.int64))))
            print('  %-4s channel %d: SNR %5.1f dB at lag %+d, high-frequency (1st difference) SNR %5.1f dB' % (conv, k, best[0], best[1], best[2]))


if __name__ == '__main__':
    main(sys.argv[1:])
