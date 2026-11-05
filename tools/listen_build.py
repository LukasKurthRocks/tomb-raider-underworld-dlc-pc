"""Listening copies (16-bit WAV) for offline A/B tests of the DLC audio (read-only on game data; outputs below
work/listen/, git-excluded). Docs: ../docs/Hoervergleich.md (workspace), Befund-DLC-Musik.md, Befund-Versteckte-Inhalte.md.

Modes (run from the repository root):
  ../bin/pyt -t 3600 tools/listen_build.py music [--installed ../data/pc/mods] [--alt work/rebuild/dlc_test50l_music/mods]
                                                 [--out work/listen/music] [--names a,b,..]
      per srmusic track of the installed tree (music\\<d>\\<d>.mul):
        xbox.wav          the Xbox source (first DLC pack with the name, as music_convert / mul_audio_batch.find_xb),
                          XMA1 per stream decoded with mul_audio.xb_pcm (ffmpeg) - the reference
        pc_installed.wav  the installed PC .mul decoded with the game's IMA convention (compare_audio.mul_pcm,
                          header sample + nibbles 1..63, what tru.exe plays)
        pc_50l.wav        only where the --alt tree has a .mul with other bytes than the installed one (the 6 DLC 1
                          tracks of test 50l): the same decode of the alternative file
      Rate and channel count are those of the files (no resampling / downmix); channel k = Xbox stream k.
  ../bin/pyt -t 1800 tools/listen_build.py unnamed [--pack pack11] [--tsv work/cut_scan/unnamed.tsv] [--out work/listen/unnamed]
      every unnamed audio-stream record of the pack listed in the hidden_scan table (hash, spec): one WAV per distinct
      (hash, language) as <hash>_<lang>.wav (lang: all = unlocalised spec ffffffff, en ffffffe1, fr ffffe002,
      de ffffe004, it ffffe008, es ffffe010; tools/mul_lang_build.LANG); records that are no .mul stream (images) are
      listed and skipped; duplicate index entries with identical bytes are written once. Header word 1 is
      0xffffffff for one-shot streams and the loop start sample for looping streams (both accepted).
  ../bin/pyt -t 1800 tools/listen_build.py match [--unnamed DIR] [--music DIR] [--snip 4]
      after music + unnamed: does a 4 s piece (middle) of each unnamed _all / _en stream occur in a DLC music track
      (every stereo pair of xbox.wav)? max normalised cross-correlation, 11 kHz mono -> unnamed/match_music.json
  ../bin/pyt -t 300 tools/listen_build.py head PACK HASH[,HASH..] [NBYTES]   header words + first block headers
  ../bin/pyt -t 120 tools/listen_build.py table music|unnamed [DIR]          Markdown tables from report.json

Per file it measures (printed + work/listen/<mode>/report.json + report.tsv):
  rate, channels, samples, seconds, RMS / peak per channel, silent channels (RMS < 2), leading / trailing silence
  (all channels |x| <= 32), and two click indicators on the sample-to-sample step |x[n] - x[n-1]| (worst channel):
  'jumps' = steps > 12000, 'edge' = mean step across the 64-sample IMA block borders / mean step elsewhere
  (about 1.0 when the borders are inaudible; clearly above 1 = a tick every 64 samples). For music the PC files
  are also compared with the Xbox decode: length difference and SNR (worst channel, compare_audio.stats).
"""
import sys, os, struct, json, hashlib, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LANG = {0xffffffff: 'all', 0xffffffe1: 'en', 0xffffe002: 'fr', 0xffffe004: 'de', 0xffffe008: 'it', 0xffffe010: 'es'}
SILENT_ABS = 32          # |sample| at or below this counts as silence (leading / trailing)
JUMP = 12000             # a step this large between two neighbour samples is a click candidate
BLOCK = 64               # IMA block length (samples per channel)


def arg(argv, key, default):
    if key in argv:
        k = argv.index(key); v = argv[k + 1]; del argv[k:k + 2]; return v
    return default


def write_wav(path, rate, pcm):
    pcm = np.asarray(pcm)
    if pcm.ndim == 1: pcm = pcm[:, None]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, 'wb') as w:
        w.setnchannels(pcm.shape[1]); w.setsampwidth(2); w.setframerate(int(rate))
        w.writeframes(np.clip(pcm, -32768, 32767).astype('<i2').tobytes())


def measure(pcm, rate):
    """level / silence / click figures of [n, ch] samples"""
    pcm = np.asarray(pcm)
    if pcm.ndim == 1: pcm = pcm[:, None]
    n, ch = pcm.shape
    r = {'rate': int(rate), 'channels': int(ch), 'samples': int(n), 'seconds': round(n / float(rate or 1), 3)}
    rms, peak, jumps, edge = [], [], 0, 0.0
    loud = np.zeros(n, dtype=bool)
    for k in range(ch):
        x = pcm[:, k].astype(np.int32)
        rms.append(int(round(float(np.sqrt(np.mean(x.astype(np.float64) ** 2))))) if n else 0)
        peak.append(int(np.abs(x).max()) if n else 0)
        loud |= np.abs(x) > SILENT_ABS
        if n > 2 * BLOCK:
            d = np.abs(np.diff(x))                     # d[i] = |x[i+1] - x[i]|; block border when (i+1) % 64 == 0
            jumps += int(np.count_nonzero(d > JUMP))
            border = d[BLOCK - 1::BLOCK]
            m_all = float(d.mean())
            m_in = (m_all * len(d) - float(border.sum())) / max(1, len(d) - len(border))
            if m_in > 0: edge = max(edge, float(border.mean()) / m_in)
            del d, border
        del x
    nz = np.flatnonzero(loud)
    r.update({'rms': rms, 'peak': peak, 'silent_channels': [k for k, v in enumerate(rms) if v < 2],
              'lead_silence_s': round((nz[0] if len(nz) else n) / float(rate or 1), 3),
              'trail_silence_s': round((n - 1 - nz[-1] if len(nz) else n) / float(rate or 1), 3),
              'jumps': jumps, 'edge': round(edge, 3)})
    return r


def snr_vs(pc, xb):
    """worst-channel SNR (dB) of pc against xb over the common length and channels"""
    import compare_audio as CA
    per = [CA.stats(pc[:, k], xb[:, k]) for k in range(min(pc.shape[1], xb.shape[1]))]
    w = min(per, key=CA._snr_key) if per else None
    v = w['snr_db'] if w else None
    return None if v is None else ('inf' if v == float('inf') else round(v, 1))


def md5f(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def save_report(out, rows, cols):
    os.makedirs(out, exist_ok=True)
    json.dump(rows, open(os.path.join(out, 'report.json'), 'w', encoding='utf-8'), indent=1)
    with open(os.path.join(out, 'report.tsv'), 'w', encoding='utf-8') as f:
        f.write('\t'.join(cols) + '\n')
        for r in rows:
            f.write('\t'.join(str(r.get(c, '')) for c in cols) + '\n')
    print('report', os.path.abspath(os.path.join(out, 'report.json')))


def cmd_music(argv):
    import compare_audio as CA, mul_audio as MA, mul_audio_batch as MAB
    inst = arg(argv, '--installed', '../data/pc/mods')
    alt = arg(argv, '--alt', 'work/rebuild/dlc_test50l_music/mods')
    out = arg(argv, '--out', 'work/listen/music')
    names = set(x for x in arg(argv, '--names', '').split(',') if x)
    md = os.path.join(inst, 'music')
    rows = []
    for d in sorted(os.listdir(md)):
        if names and d not in names: continue
        pi = os.path.join(md, d, d + '.mul')
        if not os.path.isfile(pi): continue
        od = os.path.join(out, d)
        xd, pack, sp, specs = MAB.find_xb('music\\%s\\%s.mul' % (d, d))
        if xd is None: print(d, 'no Xbox source'); continue
        xrate, xtotal, xb = MA.xb_pcm(xd)
        xb = np.clip(xb, -32768, 32767).astype(np.int16)
        write_wav(os.path.join(od, 'xbox.wav'), xrate, xb)
        files = [('xbox', None, xrate, xb, int(xtotal), '%s %s' % (pack, '%08x' % sp))]
        pd = open(pi, 'rb').read()
        prate, _, ptotal, pch = struct.unpack_from('<4I', pd, 0)
        pc = CA.mul_pcm(pd, True)
        write_wav(os.path.join(od, 'pc_installed.wav'), prate, pc)
        files.append(('pc_installed', md5f(pi), prate, pc, int(ptotal), pi))
        pa = os.path.join(alt, 'music', d, d + '.mul')
        if os.path.isfile(pa) and md5f(pa) != md5f(pi):
            ad = open(pa, 'rb').read()
            arate, _, atotal, ach = struct.unpack_from('<4I', ad, 0)
            al = CA.mul_pcm(ad, True)
            write_wav(os.path.join(od, 'pc_50l.wav'), arate, al)
            files.append(('pc_50l', md5f(pa), arate, al, int(atotal), pa))
        for tag, md5, rate, pcm, total, src in files:
            m = measure(pcm, rate)
            r = {'track': d, 'file': tag + '.wav', 'source': src, 'header_samples': total, 'mul_md5': md5 or ''}
            r.update(m)
            if tag != 'xbox':
                r['len_diff_vs_xbox'] = int(len(pcm)) - int(len(xb))
                r['rate_equal'] = rate == xrate
                r['channels_equal'] = pcm.shape[1] == xb.shape[1]
                r['snr_vs_xbox_db'] = snr_vs(pcm, xb)
            rows.append(r)
            print('%-34s %-17s %5d Hz ch %d %9d smp %7.2f s rms %-30s silentCh %s lead %.3f trail %.3f jumps %5d edge %.2f%s'
                  % (d, r['file'], rate, m['channels'], m['samples'], m['seconds'], ','.join(map(str, m['rms'])),
                     m['silent_channels'] or '-', m['lead_silence_s'], m['trail_silence_s'], m['jumps'], m['edge'],
                     '' if tag == 'xbox' else '  len-diff %+d  SNR %s dB' % (r['len_diff_vs_xbox'], r['snr_vs_xbox_db'])),
                  flush=True)
        del xb, pc, files
    save_report(out, rows, ['track', 'file', 'rate', 'channels', 'samples', 'seconds', 'header_samples', 'len_diff_vs_xbox',
                            'rate_equal', 'channels_equal', 'snr_vs_xbox_db', 'rms', 'peak', 'silent_channels',
                            'lead_silence_s', 'trail_silence_s', 'jumps', 'edge', 'mul_md5', 'source'])
    print('tracks %d, wav files %d' % (len({r['track'] for r in rows}), len(rows)))


def cmd_unnamed(argv):
    import mul_audio as MA
    from archive import Archive
    from convert_dlc import R, PACKS
    pack = arg(argv, '--pack', 'pack11')
    tsv = arg(argv, '--tsv', 'work/cut_scan/unnamed.tsv')
    out = arg(argv, '--out', 'work/listen/unnamed')
    want = {}
    for line in open(tsv, encoding='utf-8'):
        if line.startswith('#') or not line.strip(): continue
        f = line.rstrip('\n').split('\t')
        if f[0] != pack: continue
        h, _, sp = f[1].partition('@')
        want.setdefault(int(h, 16), set()).add(int(sp, 16) if sp else 0xffffffff)
    path = [R + p for p in PACKS if p.endswith('/%s.000' % pack)][0]
    A = Archive(path, 'be')
    rows, skipped = [], []
    for h in sorted(want):
        recs = {}
        for r in A.idx:
            if r['hash'] == h and r['spec'] in want[h]: recs.setdefault(r['spec'], []).append(r)
        for sp in sorted(recs, key=lambda s: (s != 0xffffffff, s != 0xffffffe1, s)):
            datas = [A.read(r) for r in recs[sp]]
            md5s = sorted({hashlib.md5(x).hexdigest() for x in datas})
            xd = datas[0]
            w = struct.unpack_from('>4I', xd, 0) if len(xd) >= 16 else (0, 0, 0, 0)
            # word 1 = 0xffffffff (one-shot) or the loop start sample (< word 2) for looping streams
            if not (8000 <= w[0] <= 48000 and (w[1] == 0xffffffff or w[1] < w[2]) and 1 <= w[3] <= 8):
                skipped.append('0x%08x spec %08x: no .mul stream (%d bytes, starts %s)' % (h, sp, len(xd), xd[:4].hex()))
                continue
            rate, total, pcm = MA.xb_pcm(xd)
            pcm = np.clip(pcm, -32768, 32767).astype(np.int16)
            lang = LANG.get(sp, '%08x' % sp)
            name = '%08x_%s.wav' % (h, lang)
            write_wav(os.path.join(out, name), rate, pcm)
            m = measure(pcm, rate)
            r = {'hash': '0x%08x' % h, 'spec': '%08x' % sp, 'lang': lang, 'file': name, 'header_rate': w[0],
                 'header_samples': w[2], 'loop_start': '' if w[1] == 0xffffffff else w[1],
                 'loop_start_s': '' if w[1] == 0xffffffff else round(w[1] / float(w[0]), 3), 'header_channels': w[3], 'streams': int(pcm.shape[1]), 'bytes': len(xd),
                 'index_entries': len(recs[sp]), 'identical_entries': len(md5s) == 1, 'md5': md5s[0]}
            r.update(m)
            rows.append(r)
            print('%s %-3s %-22s %5d Hz ch %d (hdr %d) %8d smp %6.2f s (hdr %6.2f s) rms %-24s silentCh %s lead %.3f trail %.3f '
                  'jumps %d edge %.2f entries %d same %s loop %s'
                  % (r['hash'], lang, name, rate, m['channels'], w[3], m['samples'], m['seconds'], w[2] / float(w[0]),
                     ','.join(map(str, m['rms'])), m['silent_channels'] or '-', m['lead_silence_s'], m['trail_silence_s'],
                     m['jumps'], m['edge'], len(recs[sp]), len(md5s) == 1,
                     '-' if w[1] == 0xffffffff else '%d (%.2f s)' % (w[1], w[1] / float(w[0]))), flush=True)
            del pcm
    for s in skipped: print('SKIP', s)
    # identical audio across languages (same md5 of the record)
    by_md5 = {}
    for r in rows: by_md5.setdefault(r['md5'], []).append(r['file'])
    for k, v in by_md5.items():
        if len(v) > 1: print('SAME BYTES', ' = '.join(v))
    save_report(out, rows, ['hash', 'lang', 'spec', 'file', 'rate', 'channels', 'header_channels', 'samples', 'seconds',
                            'header_samples', 'loop_start', 'loop_start_s', 'rms', 'peak', 'silent_channels', 'lead_silence_s', 'trail_silence_s', 'jumps',
                            'edge', 'bytes', 'index_entries', 'identical_entries', 'md5'])
    print('hashes %d, wav files %d, skipped %d' % (len({r['hash'] for r in rows}), len(rows), len(skipped)))


def read_wav(path):
    with wave.open(path, 'rb') as w:
        n, ch, rate = w.getnframes(), w.getnchannels(), w.getframerate()
        return rate, np.frombuffer(w.readframes(n), dtype='<i2').reshape(-1, ch)


def mono_dec(x, k=4):
    """mean of the given channels, then mean of k neighbour samples (44.1 kHz -> 11.025 kHz), float32"""
    m = x.astype(np.float32).mean(1)
    n = len(m) // k * k
    return m[:n].reshape(-1, k).mean(1)


def ncc_max(track, snip):
    """max normalised cross-correlation of snip slid along track (FFT; local energy of the track window)"""
    n, m = len(track), len(snip)
    if m < 16 or n < m: return 0.0, 0
    s = snip - snip.mean()
    N = 1 << int(np.ceil(np.log2(n + m)))
    c = np.fft.irfft(np.fft.rfft(track, N) * np.conj(np.fft.rfft(s, N)), N)[:n - m + 1]
    cs = np.concatenate([[0.0], np.cumsum(track.astype(np.float64))])
    cs2 = np.concatenate([[0.0], np.cumsum(track.astype(np.float64) ** 2)])
    wsum, wsq = cs[m:] - cs[:-m], cs2[m:] - cs2[:-m]
    var = np.maximum(wsq - wsum ** 2 / m, 1e-9)
    v = np.abs(c) / (np.sqrt(var) * float(np.linalg.norm(s)) + 1e-9)
    k = int(np.argmax(v))
    return float(v[k]), k


def cmd_match(argv):
    """match [--unnamed work/listen/unnamed] [--music work/listen/music] [--snip 4]: does an unnamed stream (a 4 s
    piece from its middle, mono, 11 kHz) occur in one of the DLC music tracks (xbox.wav, every stereo pair)?"""
    ud = arg(argv, '--unnamed', 'work/listen/unnamed')
    mdir = arg(argv, '--music', 'work/listen/music')
    sec = float(arg(argv, '--snip', '4'))
    tracks = []
    for d in sorted(os.listdir(mdir)):
        p = os.path.join(mdir, d, 'xbox.wav')
        if not os.path.isfile(p): continue
        rate, x = read_wav(p)
        for j in range(0, x.shape[1], 2):
            tracks.append(('%s ch%d-%d' % (d, j + 1, min(j + 2, x.shape[1])), mono_dec(x[:, j:j + 2])))
        del x
    print('music layers: %d' % len(tracks), flush=True)
    rows = []
    # positive controls first: the PC decode (other codec) of two music tracks must be found in their Xbox decode
    ctl = [os.path.join(mdir, t, 'pc_installed.wav') for t in ('dlc2_level2_start_mus_01', 'dlc_water_wheel_mus_01')]
    files = [p for p in ctl if os.path.isfile(p)] + [os.path.join(ud, f) for f in sorted(os.listdir(ud))
                                                      if f.endswith('_all.wav') or f.endswith('_en.wav')]
    for fp in files:
        f = os.path.basename(fp) if fp.startswith(ud) else 'CONTROL ' + os.path.basename(os.path.dirname(fp))
        rate, x = read_wav(fp)
        if f.startswith('CONTROL'): x = x[:, 2:4] if x.shape[1] >= 4 else x
        u = mono_dec(x); m = int(sec * rate / 4)
        a = max(0, len(u) // 2 - m // 2); snip = u[a:a + m]
        best = sorted(((ncc_max(t, snip), name) for name, t in tracks), key=lambda z: -z[0][0])[:2]
        del x
        rows.append({'file': f, 'best': best[0][1], 'ncc': round(best[0][0][0], 3),
                     'at_s': round(best[0][0][1] * 4 / float(rate), 2), 'second': best[1][1], 'ncc2': round(best[1][0][0], 3)})
        print('%-22s best %-48s ncc %.3f at %7.2f s | 2nd %-48s %.3f' % (f, best[0][1], best[0][0][0],
              best[0][0][1] * 4 / float(rate), best[1][1], best[1][0][0]), flush=True)
    json.dump(rows, open(os.path.join(ud, 'match_music.json'), 'w', encoding='utf-8'), indent=1)


def cmd_table(argv):
    """table music|unnamed [DIR]: Markdown tables (German headings, for docs/Hoervergleich.md) from report.json"""
    kind = argv[0]
    d = argv[1] if len(argv) > 1 else 'work/listen/' + kind
    rows = json.load(open(os.path.join(d, 'report.json'), encoding='utf-8'))
    fmt = lambda v, p=3: ('%.*f' % (p, v)).replace('.', ',') if isinstance(v, float) else str(v)
    if kind == 'music':
        by = {}
        for r in rows: by.setdefault(r['track'], {})[r['file'][:-4]] = r
        print('| Stück | Kanäle | Hz | Länge Xbox (s) | Länge PC inst. (s) | Δ Samples inst. | SNR inst. (dB) | edge Xbox / inst. '
              '| Δ Samples 50l | SNR 50l (dB) | edge 50l | Auffällig |')
        print('|---|---|---|---|---|---|---|---|---|---|---|---|')
        for t in sorted(by):
            x, i, a = by[t].get('xbox'), by[t].get('pc_installed'), by[t].get('pc_50l')
            odd = []
            for r in (i, a):
                if not r: continue
                tag = 'inst.' if r is i else '50l'
                if not r['rate_equal']: odd.append('%s Rate' % tag)
                if not r['channels_equal']: odd.append('%s Kanäle' % tag)
                if r['silent_channels']: odd.append('%s stumme Kanäle %s' % (tag, r['silent_channels']))
                if r['edge'] >= 1.1: odd.append('%s Blockkanten-Ticks (edge %s)' % (tag, fmt(r['edge'], 2)))
                if x and r['jumps'] > 2 * x['jumps'] + 50: odd.append('%s Sprünge %d (Xbox %d)' % (tag, r['jumps'], x['jumps']))
                if x and abs(r['lead_silence_s'] - x['lead_silence_s']) > 0.05: odd.append('%s Anfangsstille' % tag)
            print('| %s | %d | %d | %s | %s | %+d | %s | %s / %s | %s | %s | %s | %s |' % (
                t, x['channels'], x['rate'], fmt(x['seconds']), fmt(i['seconds']), i['len_diff_vs_xbox'],
                fmt(i['snr_vs_xbox_db'], 1), fmt(x['edge'], 2), fmt(i['edge'], 2),
                '%+d' % a['len_diff_vs_xbox'] if a else '-', fmt(a['snr_vs_xbox_db'], 1) if a else '-',
                fmt(a['edge'], 2) if a else '-', ', '.join(odd) or '-'))
        # summary over all PC files against their Xbox decode
        pcs = [(r, by[r['track']]['xbox']) for r in rows if r['file'] != 'xbox.wav']
        dev = max(abs(a - b) / float(b) * 100 for r, x in pcs for a, b in zip(r['rms'], x['rms']) if b)
        print('\nSUMMARY pc files %d | rate equal %d | channels equal %d | files with silent channels %d | max RMS '
              'deviation %.2f %% | max |len diff| %d samples | max |lead silence diff| %.3f s | max |trail silence diff| '
              '%.3f s | edge >= 1.1: %s' % (
                  len(pcs), sum(r['rate_equal'] for r, x in pcs), sum(r['channels_equal'] for r, x in pcs),
                  sum(1 for r in rows if r['silent_channels']), dev, max(abs(r['len_diff_vs_xbox']) for r, x in pcs),
                  max(abs(r['lead_silence_s'] - x['lead_silence_s']) for r, x in pcs),
                  max(abs(r['trail_silence_s'] - x['trail_silence_s']) for r, x in pcs),
                  ', '.join('%s/%s' % (r['track'], r['file']) for r, x in pcs if r['edge'] >= 1.1) or '-'))
    else:
        by = {}
        for r in rows: by.setdefault(r['hash'], []).append(r)
        print('| Hash | Sprachen | Kanäle | Hz | Länge (s) | Schleife ab (s) | RMS (L, R) | Stille Anfang / Ende (s) | Dateien |')
        print('|---|---|---|---|---|---|---|---|---|')
        for h in sorted(by):
            rs = by[h]
            langs = ', '.join(r['lang'] for r in rs)
            secs = sorted({r['seconds'] for r in rs})
            ln = fmt(secs[0], 2) if len(secs) == 1 else '%s - %s' % (fmt(secs[0], 2), fmt(secs[-1], 2))
            loop = rs[0]['loop_start_s']
            print('| `%s` | %s | %d | %d | %s | %s | %s | %s / %s | %s |' % (
                h, langs, rs[0]['channels'], rs[0]['rate'], ln, '-' if loop == '' else fmt(loop, 2),
                ', '.join(map(str, rs[0]['rms'])) + (' (en)' if len(rs) > 1 else ''),
                fmt(max(r['lead_silence_s'] for r in rs)), fmt(max(r['trail_silence_s'] for r in rs)),
                ', '.join('`%s`' % r['file'] for r in rs) if len(rs) <= 1 else '`%s_*.wav` (%d)' % (h[2:], len(rs))))


def cmd_head(argv):
    """head PACK HASH[,HASH..] [NBYTES]: header words (big endian) of the records and the first block headers at 0x800"""
    from archive import Archive
    from convert_dlc import R, PACKS
    path = [R + p for p in PACKS if p.endswith('/%s.000' % argv[0])][0]
    A = Archive(path, 'be'); nb = int(argv[2]) if len(argv) > 2 else 64
    for h in [int(x, 16) for x in argv[1].split(',')]:
        for r in A.find(h):
            d = A.read(r)
            print('0x%08x spec %08x %d bytes clen %d' % (h, r['spec'], len(d), r['clen']))
            print('   head  ', ' '.join('%08x' % w for w in struct.unpack_from('>%dI' % (min(nb, len(d)) // 4), d, 0)))
            o = 0x800; k = 0
            while o + 16 <= len(d) and k < 4:
                t, sz, a, b = struct.unpack_from('>4I', d, o)
                print('   block @%x type %d size %d a %d b %d  next words %s' % (o, t, sz, a, b, ' '.join(
                    '%08x' % w for w in struct.unpack_from('>4I', d, o + 16))))
                if sz == 0 or sz > len(d): break
                o += 16 + sz; k += 1


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in ('music', 'unnamed', 'head', 'match', 'table'): sys.exit(__doc__)
    {'music': cmd_music, 'unnamed': cmd_unnamed, 'head': cmd_head, 'match': cmd_match,
     'table': cmd_table}[sys.argv[1]](sys.argv[2:])
