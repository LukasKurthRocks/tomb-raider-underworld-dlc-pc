"""Listening copies decoded the way tru.exe decodes .mul streams (the MMX IMA decoder with the step capped at 8191,
tools/f13_sibilants.decode_game), plus playlists in a sensible order. Read-only on game data and trees; writes only
below work/listen/ (git-excluded). Background: ../docs/Befund-S-Laute.md (workspace) - the pc_installed.wav /
pc_50l.wav of listen_build.py use the old decoder model (compare_audio) and do not sound like the game.

Modes (run from the repository root):
  ../bin/pyt -t 3600 tools/listen_game_model.py music [--listen work/listen/music] [--installed ../data/pc/mods]
                                                      [--alt work/rebuild/dlc_test50l_music/mods]
                                                      [--new work/rebuild/dlc_test51f_audio/mods]
      per track folder of work/listen/music that has xbox.wav:
        pc_installiert_wie_spiel.wav   installed .mul, decoded like tru.exe
        pc_51f_wie_spiel.wav           the --new tree's .mul (N10 re-encode for the real decoder), if it has the track
        pc_50l_wie_spiel.wav           the --alt tree's .mul, only where its bytes differ from the installed file
      cut to the Xbox length; worst-channel SNR against xbox.wav -> work/listen/music/report_wie_spiel.tsv
  ../bin/pyt -t 1800 tools/listen_game_model.py measure [--listen work/listen/music]
      after 'music': per track, PC file (installiert / 51f / 50l) and stereo layer (channels 1/2, 3/4, 5/6) against
      xbox.wav, in frames of 2048 samples:
        snr       global SNR of the layer (dB)
        segsnr    median of the per-frame SNR over frames with signal (closer to what the ear judges than snr)
        quiet     SNR over the quietest quarter of the frames with signal (noise / graininess in soft passages)
        hf        SNR of the band above 6 kHz only (hiss / sizzle on cymbals, bright sounds)
        clicks    samples where the PC step differs from the Xbox step by more than 8000 (audible ticks)
      -> work/listen/music/measure_wie_spiel.tsv and a short ranking (what is worth listening to) on stdout
  ../bin/pyt -t 600 tools/listen_game_model.py where TRACK FILE LAYER [--listen work/listen/music] [--top 6]
      where the difference of one layer (e.g. dlc2_ceremony_room_amb_02 installiert 3/4) sits: error per frequency
      band (octaves, error vs. Xbox energy in dB), the worst 1-s windows (time, Xbox level, SNR) and the click times
  ../bin/pyt -t 900 tools/listen_game_model.py stream XBOXWAV REL [--installed ../data/pc/mods]
                                                        [--new work/rebuild/dlc_test51f_audio/mods] [--head 1.0]
      one stream (e.g. a reveal from work/listen/unnamed): installed and --new tree's REL (path below mods) decoded like
      tru.exe next to the Xbox WAV (work/listen/streams/<name>/), whole-file and first --head seconds compared:
      SNR, peak, clicks (PC step differs from Xbox step by > 8000) and the largest single step in the head of each file
  ../bin/pyt -t 3600 tools/listen_game_model.py scan
      'stream' for every named non-speech stream of work/listen/unnamed (names: work/proto_dlc2_ls_20090207/
      audio_names_final.txt) -> work/listen/streams/scan_effekte.tsv, sorted by the installed file's head SNR
  ../bin/pyt -t 120 tools/listen_game_model.py playlists [--listen work/listen] [--f13 work/f13_sibilants/wav]
      writes work/listen/playlists/*.m3u8 (UTF-8, relative paths) and work/listen/playlists/README.txt
"""
import sys, os, struct, hashlib, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def arg(argv, key, default):
    if key in argv:
        k = argv.index(key); v = argv[k + 1]; del argv[k:k + 2]; return v
    return default


def md5f(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def read_wav(path):
    with wave.open(path, 'rb') as w:
        n, ch, rate = w.getnframes(), w.getnchannels(), w.getframerate()
        return rate, np.frombuffer(w.readframes(n), dtype='<i2').reshape(-1, ch)


def write_wav(path, rate, pcm):
    with wave.open(path, 'wb') as w:
        w.setnchannels(pcm.shape[1]); w.setsampwidth(2); w.setframerate(int(rate))
        w.writeframes(np.clip(pcm, -32768, 32767).astype('<i2').tobytes())


def decode_like_game(path):
    import f13_sibilants as F
    rate, total, nch, segs = F.channel_blocks(open(path, 'rb').read())
    chans = [F.decode_channel(s, F.decode_game) for s in segs]
    n = min(len(c) for c in chans)
    return rate, np.stack([c[:n] for c in chans], axis=1)


def snr_db(pc, xb):
    """worst channel: 10 log10(sum x^2 / sum (pc - x)^2) over the common length / channels"""
    n = min(len(pc), len(xb)); worst = None
    for k in range(min(pc.shape[1], xb.shape[1])):
        x = xb[:n, k].astype(np.float64); e = pc[:n, k].astype(np.float64) - x
        s, d = float(np.sum(x * x)), float(np.sum(e * e))
        v = float('inf') if d == 0 else (10 * np.log10(s / d) if s > 0 else float('-inf'))
        worst = v if worst is None else min(worst, v)
    return worst


def cmd_music(argv):
    listen = arg(argv, '--listen', 'work/listen/music')
    inst = arg(argv, '--installed', '../data/pc/mods')
    alt = arg(argv, '--alt', 'work/rebuild/dlc_test50l_music/mods')
    new = arg(argv, '--new', 'work/rebuild/dlc_test51f_audio/mods')
    rows = ['track\tchannels\tseconds\tsnr_installed_db\tsnr_51f_db\tsnr_50l_db\tmd5_installed\tmd5_51f\tmd5_50l']
    for d in sorted(os.listdir(listen)):
        xw = os.path.join(listen, d, 'xbox.wav')
        if not os.path.isfile(xw): continue
        xrate, xb = read_wav(xw)
        out = {}
        for key, root, cond in (('installiert', inst, None), ('51f', new, None), ('50l', alt, 'differs')):
            p = os.path.join(root, 'music', d, d + '.mul')
            if not os.path.isfile(p): continue
            if cond == 'differs' and md5f(p) == md5f(os.path.join(inst, 'music', d, d + '.mul')): continue
            rate, pc = decode_like_game(p)
            if rate != xrate: print(d, key, 'rate', rate, '!= xbox', xrate); continue
            pc = pc[:len(xb)]
            write_wav(os.path.join(listen, d, 'pc_%s_wie_spiel.wav' % key), rate, pc)
            out[key] = (snr_db(pc, xb), md5f(p))
        fmt = lambda k: '-' if k not in out else ('%.1f' % out[k][0])
        md = lambda k: '-' if k not in out else out[k][1]
        rows.append('\t'.join([d, str(xb.shape[1]), '%.3f' % (len(xb) / xrate), fmt('installiert'), fmt('51f'),
                               fmt('50l'), md('installiert'), md('51f'), md('50l')]))
        print(rows[-1])
    with open(os.path.join(listen, 'report_wie_spiel.tsv'), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\n'.join(rows) + '\n')
    print('report', os.path.join(listen, 'report_wie_spiel.tsv'))


FRAME = 2048            # analysis frame (46 ms at 44.1 kHz)
SIGNAL_RMS = 64.0       # frames with Xbox RMS below this count as silence (not judged)
HF_HZ = 6000.0          # lower edge of the 'hf' band
CLICK = 8000            # |PC step - Xbox step| above this = click candidate


def db(s, n):
    return float('inf') if n <= 0 else (10 * np.log10(s / n) if s > 0 else float('-inf'))


def layer_metrics(pc, xb, rate):
    """pc, xb: [n, 2] or [n, 1] int16 of one stereo layer (same length) -> dict of the five measures"""
    x = xb.astype(np.float64); e = pc.astype(np.float64) - x
    nf = len(x) // FRAME
    xf = x[:nf * FRAME].reshape(nf, FRAME, -1); ef = e[:nf * FRAME].reshape(nf, FRAME, -1)
    xs = np.sum(xf * xf, axis=(1, 2)); es = np.sum(ef * ef, axis=(1, 2))
    rms = np.sqrt(xs / (FRAME * x.shape[1]))
    sig = rms >= SIGNAL_RMS
    per = np.array([db(a, b) for a, b in zip(xs[sig], es[sig])]) if np.any(sig) else np.array([])
    per = per[np.isfinite(per)]
    seg = float(np.median(per)) if len(per) else float('nan')
    if np.any(sig):
        cut = np.quantile(rms[sig], 0.25); q = sig & (rms <= cut)
        quiet = db(float(np.sum(xs[q])), float(np.sum(es[q])))
    else:
        quiet = float('nan')
    win = np.hanning(FRAME)[None, :, None]
    k0 = int(HF_HZ * FRAME / rate)
    XF = np.fft.rfft(xf * win, axis=1)[:, k0:, :]; EF = np.fft.rfft(ef * win, axis=1)[:, k0:, :]
    hf = db(float(np.sum(np.abs(XF[sig]) ** 2)), float(np.sum(np.abs(EF[sig]) ** 2))) if np.any(sig) else float('nan')
    dstep = np.abs(np.diff(pc.astype(np.int32), axis=0) - np.diff(xb.astype(np.int32), axis=0))
    return {'snr': db(float(np.sum(x * x)), float(np.sum(e * e))), 'segsnr': seg, 'quiet': quiet, 'hf': hf,
            'clicks': int(np.sum(np.max(dstep, axis=1) > CLICK))}


def cmd_measure(argv):
    listen = arg(argv, '--listen', 'work/listen/music')
    cols = ['snr', 'segsnr', 'quiet', 'hf', 'clicks']
    rows = ['track\tfile\tlayer\t' + '\t'.join(cols)]
    best = {}                                    # (track, layer) -> {file: metrics}
    for d in sorted(os.listdir(listen)):
        xw = os.path.join(listen, d, 'xbox.wav')
        if not os.path.isfile(xw): continue
        rate, xb = read_wav(xw)
        for key in ('installiert', '51f', '50l'):
            pw = os.path.join(listen, d, 'pc_%s_wie_spiel.wav' % key)
            if not os.path.isfile(pw): continue
            _, pc = read_wav(pw)
            n = min(len(pc), len(xb))
            for L in range(0, min(pc.shape[1], xb.shape[1]), 2):
                m = layer_metrics(pc[:n, L:L + 2], xb[:n, L:L + 2], rate)
                lay = '%d/%d' % (L + 1, L + 2)
                best.setdefault((d, lay), {})[key] = m
                rows.append('\t'.join([d, key, lay] + [('%d' % m[c]) if c == 'clicks' else ('%.1f' % m[c]) for c in cols]))
    out = os.path.join(listen, 'measure_wie_spiel.tsv')
    with open(out, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\n'.join(rows) + '\n')
    print('written', out, len(rows) - 1, 'rows')
    print('\nlayer                                        file          snr  segsnr  quiet     hf  clicks')
    for (d, lay), fs in sorted(best.items(), key=lambda kv: min(v['quiet'] for v in kv[1].values())):
        for key, m in fs.items():
            print('%-38s %-5s %-12s %6.1f %7.1f %6.1f %6.1f %7d' % (d, lay, key, m['snr'], m['segsnr'], m['quiet'], m['hf'], m['clicks']))


def cmd_where(argv):
    listen = arg(argv, '--listen', 'work/listen/music')
    top = int(arg(argv, '--top', '6'))
    track, key, lay = argv[0], argv[1], argv[2]
    L = int(lay.split('/')[0]) - 1
    rate, xb = read_wav(os.path.join(listen, track, 'xbox.wav'))
    _, pc = read_wav(os.path.join(listen, track, 'pc_%s_wie_spiel.wav' % key))
    n = min(len(pc), len(xb)); xb = xb[:n, L:L + 2]; pc = pc[:n, L:L + 2]
    x = xb.astype(np.float64); e = pc.astype(np.float64) - x
    print('%s %s layer %s: %.1f s, %d ch' % (track, key, lay, n / rate, x.shape[1]))
    # error spectrum per octave band (whole file, Welch-style mean of windowed frames)
    nf = n // FRAME; win = np.hanning(FRAME)[None, :, None]
    XS = np.mean(np.abs(np.fft.rfft(x[:nf * FRAME].reshape(nf, FRAME, -1) * win, axis=1)) ** 2, axis=(0, 2))
    ES = np.mean(np.abs(np.fft.rfft(e[:nf * FRAME].reshape(nf, FRAME, -1) * win, axis=1)) ** 2, axis=(0, 2))
    f = np.fft.rfftfreq(FRAME, 1.0 / rate)
    print('\nband (Hz)        Xbox level (dB)  error level (dB)  SNR in band (dB)')
    edges = [0, 125, 250, 500, 1000, 2000, 4000, 8000, 16000, rate / 2]
    ref = float(np.sum(XS))
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (f >= lo) & (f < hi)
        xs, es = float(np.sum(XS[m])), float(np.sum(ES[m]))
        print('%6d - %-6d   %14.1f  %16.1f  %16.1f' % (lo, hi, db(xs, ref), db(es, ref), db(xs, es)))
    # worst 1-s windows by error energy, and by SNR among windows with signal
    W = rate; nw = n // W
    xw = np.sum((x[:nw * W] ** 2).reshape(nw, W, -1), axis=(1, 2)); ew = np.sum((e[:nw * W] ** 2).reshape(nw, W, -1), axis=(1, 2))
    lvl = lambda s: 10 * np.log10(max(s / (W * x.shape[1]), 1e-9) / 32768.0 ** 2)
    print('\nloudest error (1-s windows):  time    Xbox level dBFS  error level dBFS  SNR dB')
    for i in np.argsort(-ew)[:top]:
        print('                             %3d:%02d  %15.1f  %16.1f  %6.1f' % (i // 60, i % 60, lvl(xw[i]), lvl(ew[i]), db(xw[i], ew[i])))
    sig = np.where(xw / (W * x.shape[1]) >= SIGNAL_RMS ** 2)[0]
    print('\nworst SNR (1-s windows with signal): time  Xbox level dBFS  error level dBFS  SNR dB')
    for i in sorted(sig, key=lambda i: db(xw[i], ew[i]))[:top]:
        print('                                     %3d:%02d  %15.1f  %16.1f  %6.1f' % (i // 60, i % 60, lvl(xw[i]), lvl(ew[i]), db(xw[i], ew[i])))
    dstep = np.max(np.abs(np.diff(pc.astype(np.int32), axis=0) - np.diff(xb.astype(np.int32), axis=0)), axis=1)
    ck = np.where(dstep > CLICK)[0]
    if len(ck):
        secs = sorted(set(int(c // rate) for c in ck))
        print('\nclicks: %d samples in %d seconds: %s' % (len(ck), len(secs), ', '.join('%d:%02d' % (s // 60, s % 60) for s in secs[:30])))
    else:
        print('\nclicks: none')


def cmd_stream(argv):
    inst = arg(argv, '--installed', '../data/pc/mods')
    new = arg(argv, '--new', 'work/rebuild/dlc_test51f_audio/mods')
    head = float(arg(argv, '--head', '1.0'))
    xw, rel = argv[0], argv[1]
    name = os.path.splitext(os.path.basename(rel))[0]
    out = os.path.join('work', 'listen', 'streams', name); os.makedirs(out, exist_ok=True)
    rate, xb = read_wav(xw)
    write_wav(os.path.join(out, '1_xbox.wav'), rate, xb)
    files = [('1_xbox', xb)]
    for key, root in (('2_pc_installiert_wie_spiel', inst), ('3_pc_51f_wie_spiel', new)):
        p = os.path.join(root, rel)
        if not os.path.isfile(p): print('missing', p); continue
        prate, pc = decode_like_game(p)
        if prate != rate: print(key, 'rate', prate, '!= xbox', rate); continue
        n = min(len(pc), len(xb)); pc = pc[:n]
        write_wav(os.path.join(out, key + '.wav'), rate, pc); files.append((key, pc))
    hn = int(head * rate)
    print('%s: %.2f s, %d ch, %d Hz -> %s' % (name, len(xb) / rate, xb.shape[1], rate, out))
    print('\nfile                          head peak  head max step (at ms)   head first nonzero (ms)  clipped head / all')
    for key, a in files:
        h = a[:hn].astype(np.int32); st = np.max(np.abs(np.diff(h, axis=0)), axis=1)
        k = int(np.argmax(st)); nz = np.where(np.max(np.abs(h), axis=1) > 32)[0]
        clip = lambda z: int(np.sum(np.max(np.abs(z.astype(np.int32)), axis=1) >= 32767))
        print('%-28s %10d  %13d (%6.1f)   %10s  %10d / %d' % (key, int(np.max(np.abs(h))), int(st[k]), k * 1000.0 / rate,
              '%.1f' % (nz[0] * 1000.0 / rate) if len(nz) else '-', clip(a[:hn]), clip(a)))
    print('\nagainst Xbox                  SNR all  SNR head  clicks all  clicks head (ms)')
    for key, a in files[1:]:
        n = min(len(a), len(xb))
        def snr(p, x):
            x = x.astype(np.float64); e = p.astype(np.float64) - x
            return db(float(np.sum(x * x)), float(np.sum(e * e)))
        d = np.max(np.abs(np.diff(a[:n].astype(np.int32), axis=0) - np.diff(xb[:n].astype(np.int32), axis=0)), axis=1)
        ck = np.where(d > CLICK)[0]; ckh = ck[ck < hn]
        print('%-28s %8.1f  %8.1f  %10d  %d %s' % (key, snr(a[:n], xb[:n]), snr(a[:hn], xb[:hn]), len(ck), len(ckh),
                                                ', '.join('%.1f' % (c * 1000.0 / rate) for c in ckh[:10])))


def cmd_scan(argv):
    """all named non-speech streams of work/listen/unnamed (names from the prototype work) through cmd_stream;
    summary table sorted by the worst head SNR of the installed file"""
    import io, contextlib
    names = os.path.join('work', 'proto_dlc2_ls_20090207', 'audio_names_final.txt')
    rows = []
    for line in open(names, encoding='utf-8', errors='replace'):
        if not line.startswith('0x') or ' = ' not in line or '\\vo\\' in line: continue
        h, p = line.strip().split(' = ', 1)
        rel = p.split('\\', 1)[1].replace('\\', '/')
        xw = os.path.join('work', 'listen', 'unnamed', '%s_all.wav' % h[2:].lower())
        if not os.path.isfile(xw): continue
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try: cmd_stream([xw, rel, '--head', '1.0'])
            except Exception as ex: print('ERROR', ex)
        txt = buf.getvalue()
        name = os.path.splitext(os.path.basename(rel))[0]
        with open(os.path.join('work', 'listen', 'streams', name, 'report.txt'), 'w', encoding='utf-8') as f: f.write(txt)
        vals = {}
        for l in txt.splitlines():
            c = l.split()
            if c and c[0] in ('2_pc_installiert_wie_spiel', '3_pc_51f_wie_spiel') and len(c) >= 5:
                try: vals[c[0]] = (float(c[1]), float(c[2]), int(c[3]), int(c[4]))
                except ValueError: pass
            if c and c[0] == '1_xbox' and len(c) >= 7: vals['clip'] = c[-3]
        i = vals.get('2_pc_installiert_wie_spiel'); n = vals.get('3_pc_51f_wie_spiel')
        rows.append((name, i, n, vals.get('clip', '?')))
        print(name, 'installiert', i, '51f', n, 'xbox clipped head', vals.get('clip', '?'))
    rows.sort(key=lambda r: r[1][1] if r[1] else 99)
    out = ['stream\tsnr_all_inst\tsnr_head_inst\tclicks_inst\tsnr_all_51f\tsnr_head_51f\tclicks_51f\txbox_clipped_head']
    for name, i, n, clip in rows:
        f = lambda v, k, fmt: (fmt % v[k]) if v else '-'
        out.append('\t'.join([name, f(i, 0, '%.1f'), f(i, 1, '%.1f'), f(i, 2, '%d'), f(n, 0, '%.1f'), f(n, 1, '%.1f'), f(n, 2, '%d'), clip]))
    with open(os.path.join('work', 'listen', 'streams', 'scan_effekte.tsv'), 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write('\n'.join(out) + '\n')
    print('\n'.join(out))


def read_report(listen):
    p = os.path.join(listen, 'music', 'report_wie_spiel.tsv')
    out = {}
    for line in open(p, encoding='utf-8').read().splitlines()[1:]:
        c = line.split('\t'); out[c[0]] = c
    return out


def num(v):
    return None if v in ('-', '') else float(v)


def cmd_playlists(argv):
    listen = arg(argv, '--listen', 'work/listen')
    f13 = arg(argv, '--f13', 'work/f13_sibilants/wav')
    pl = os.path.join(listen, 'playlists'); os.makedirs(pl, exist_ok=True)
    rel = lambda p: os.path.relpath(p, pl).replace('/', '\\')
    # players such as KMPlayer show the file name, not the #EXTINF title, and the music files are all called
    # xbox.wav / pc_*.wav: every entry gets a uniquely named hard link (no extra space) below playlists/dateien
    linkdir = os.path.join(pl, 'dateien'); os.makedirs(linkdir, exist_ok=True)
    safe = lambda s: ''.join(ch if ch.isalnum() or ch in '-_.' else '_' for ch in s).strip('_')

    def write(name, title, entries):
        lines = ['#EXTM3U']      # no #PLAYLIST line: KMPlayer reads it as a file entry (title kept in the log only)
        print('playlist', name, '-', title)
        nr = 0
        for label, path in entries:
            if not os.path.isfile(path): print('missing', path); continue
            nr += 1
            link = os.path.join(linkdir, '%s_%02d_%s.wav' % (name[:2], nr, safe(label.replace(' - ', '_'))))
            if os.path.exists(link) and not os.path.samefile(link, path): os.remove(link)
            if not os.path.exists(link): os.link(path, link)
            rate, x = read_wav(path)
            lines.append('#EXTINF:%d,%s' % (round(len(x) / rate), label)); lines.append(rel(link))
        with open(os.path.join(pl, name), 'w', encoding='utf-8', newline='\r\n') as f:
            f.write('\n'.join(lines) + '\n')
        print('written', os.path.join(pl, name), (len(lines) - 1) // 2, 'entries')

    # 1 S-sounds: per clip Xbox -> PC today (like the game) -> 51f (like the game); control clip last
    clips = [('pdlc1_010_intro_de', 'DLC-1-Intro deutsch'), ('dlc2_doppelganger_mach_02', 'Doppelgaengerin DLC 2'),
             ('lara_2_water_01_de', 'Lara DLC 1 deutsch'), ('lara_1_invasion_01', 'Lara englisch, leise (Kontrolle)')]
    e = []
    for c, label in clips:
        e += [('%s - 1 Xbox' % label, os.path.join(f13, c + '_1_xbox.wav')),
              ('%s - 2 PC heute (wie Spiel)' % label, os.path.join(f13, c + '_2_pc_jetzt_wie_spiel.wav')),
              ('%s - 3 PC neu 51f (wie Spiel)' % label, os.path.join(f13, c + '_5_neu_gebaut_wie_spiel.wav'))]
    e += [('DLC-1-Intro englisch B138 (wie Spiel) - Gegenprobe sauber', os.path.join(f13, 'pdlc1_010_intro_en_B138_wie_spiel.wav'))]
    write('01_S-Laute.m3u8', 'S-Laute: Xbox / PC heute / PC neu', e)

    rep = read_report(listen); md = os.path.join(listen, 'music')
    dlc1 = [t for t in rep if not t.startswith('dlc2_')]
    dlc2 = [t for t in rep if t.startswith('dlc2_')]
    # 2 DLC 2 music: biggest expected change first (51f minus installed SNR, then lowest installed SNR)
    def gain(t):
        a, b = num(rep[t][3]), num(rep[t][4])
        return -(b - a) if a is not None and b is not None else 0.0
    e = []
    for t in sorted(dlc2, key=lambda t: (gain(t), num(rep[t][3]) or 0)):
        e += [('%s - 1 Xbox' % t, os.path.join(md, t, 'xbox.wav')),
              ('%s - 2 PC heute (wie Spiel, %s dB)' % (t, rep[t][3]), os.path.join(md, t, 'pc_installiert_wie_spiel.wav'))]
        if rep[t][4] != '-':
            e.append(('%s - 3 PC neu 51f (wie Spiel, %s dB)' % (t, rep[t][4]), os.path.join(md, t, 'pc_51f_wie_spiel.wav')))
    write('02_Musik_DLC2.m3u8', 'Musik DLC 2: Xbox / PC heute / PC neu 51f', e)
    # 3 DLC 1 music: installed (B138, built for the real decoder) vs 50l (ours, old encoder)
    e = []
    for t in sorted(dlc1, key=lambda t: num(rep[t][3]) or 0):
        e += [('%s - 1 Xbox' % t, os.path.join(md, t, 'xbox.wav')),
              ('%s - 2 PC heute B138 (wie Spiel, %s dB)' % (t, rep[t][3]), os.path.join(md, t, 'pc_installiert_wie_spiel.wav'))]
        if rep[t][5] != '-':
            e.append(('%s - 3 PC 50l (wie Spiel, %s dB)' % (t, rep[t][5]), os.path.join(md, t, 'pc_50l_wie_spiel.wav')))
    write('03_Musik_DLC1.m3u8', 'Musik DLC 1: Xbox / PC heute (B138) / 50l', e)
    # 4 unnamed streams: loops, one-shots (longest first), language streams (en, de); names resolved later from the
    # prototype work (work/proto_dlc2_ls_20090207/audio_names_final.txt: '0xHASH = xenon-w\\...\\name.mul')
    ud = os.path.join(listen, 'unnamed')
    names = {}
    nf = os.path.join(listen, '..', 'proto_dlc2_ls_20090207', 'audio_names_final.txt')
    if os.path.isfile(nf):
        for line in open(nf, encoding='utf-8', errors='replace'):
            if line.startswith('0x') and ' = ' in line:
                h, p = line.strip().split(' = ', 1)
                names[h[2:].lower()] = os.path.splitext(p.replace('/', '\\').split('\\')[-1])[0]
    nm = lambda h: (' ' + names[h]) if h in names else ''
    loops, shots, lang = [], [], []
    for f in sorted(os.listdir(ud)):
        if not f.endswith('.wav'): continue
        h, l = f[:-4].split('_', 1)
        rate, x = read_wav(os.path.join(ud, f)); sec = len(x) / rate
        if l != 'all':
            if l in ('en', 'de'): lang.append((h, l, sec, f))
        elif sec >= 40: loops.append((h, l, sec, f))
        else: shots.append((h, l, sec, f))
    e = [('Schleife %s%s (%.0f s)' % (h, nm(h), s), os.path.join(ud, f)) for h, l, s, f in sorted(loops, key=lambda r: -r[2])]
    e += [('Einmal %s%s (%.0f s)' % (h, nm(h), s), os.path.join(ud, f)) for h, l, s, f in sorted(shots, key=lambda r: -r[2])]
    e += [('Sprache %s%s %s (%.0f s)' % (h, nm(h), l, s), os.path.join(ud, f)) for h, l, s, f in sorted(lang, key=lambda r: (r[0], r[1] != 'en'))]
    write('04_Unbenannte_Stroeme.m3u8', 'Unbenannte Stroeme pack11', e)
    # 5 single streams compared with 'stream': per folder 1 Xbox -> 2 PC today -> 3 PC 51f
    sd = os.path.join(listen, 'streams')
    if os.path.isdir(sd):
        e = []
        for d in sorted(os.listdir(sd)):
            for f, lab in (('1_xbox.wav', '1 Xbox'), ('2_pc_installiert_wie_spiel.wav', '2 PC heute (wie Spiel)'),
                           ('2_b138_wie_spiel.wav', '2 B138 (wie Spiel)'), ('3_pc_51f_wie_spiel.wav', '3 PC neu 51f (wie Spiel)')):
                if os.path.isfile(os.path.join(sd, d, f)): e.append(('%s - %s' % (d, lab), os.path.join(sd, d, f)))
        if e: write('05_Einzelstroeme.m3u8', 'Einzelstroeme Xbox / PC heute / 51f', e)


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] not in ('music', 'measure', 'where', 'stream', 'scan', 'playlists'): print(__doc__); sys.exit(2)
    {'music': cmd_music, 'measure': cmd_measure, 'where': cmd_where, 'stream': cmd_stream, 'scan': cmd_scan,
     'playlists': cmd_playlists}[a[0]](a[1:])
