"""Camera comparison Xbox (Xenia) / PC: reads a TruXenia camera trace (`tools/truxenia.py --camtrace`, cam_<time>.tsv)
and a TruShadowPower 0.25 camera trace (TruCam.log, [Camera] Trace=1) - the same TSV columns (truxenia.CAM_COLS) -,
aligns both runs on an event (default: the first power-on) and writes a Markdown report:

  * start orientation: the first row of each run (camera yaw, Lara yaw, delta_yaw; e.g. the DLC 2 spawn),
  * delta_yaw over time from the alignment point, side by side in bins (default 0.5 s), as the offset from the
    reference "behind Lara" (--ref, default 180: live Xbox 2026-11-10 21:48 at the DLC 2 spawn the camera stood behind
    Lara with camera yaw 25.9 / Lara yaw -154.1, i.e. delta_yaw = -180; --ref auto = the median delta_yaw of the
    Xbox run's last 2 s),
  * re-centre time per side: from the last look input after the alignment point (recenter clock cam_clock drops, PC also
    pad_rx / pad_ry beyond the dead zone) to the first time |offset| <= --tol degrees (default 15) for --hold s
    (default 1.0); plus the time until the recenter weight reaches 1 (clock >= delay + ramp), the settings used and the
    count of INSTANT recentres (the game sets the clock to delay + ramp: PC 0x602290 / TU 0x822c2130 - live Xbox
    2026-11-10 often while climbing),
  * shadow meter per side: refill rate (meter units per second while the power is off and the meter rises), drain
    rate while the power is on, world time scale while on.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/cam_compare.py --xbox ../logs/truxenia/cam_<time>.tsv --pc <game>/TruCam.log
      [--align power|first|time] [--xbox-at HH:MM:SS] [--pc-at HH:MM:SS] [--window 30] [--bin 0.5] [--ref 180|auto]
      [--tol 15] [--hold 1.0] [--run last|N] [--out ../logs/cam_compare_<time>.md]
  ../bin/pyt -t 120 tools/cam_compare.py --selftest
A file may hold several runs (a header line at every start); --run last (default) takes the last, N the N-th (1 = first).
--align time uses --xbox-at / --pc-at (host time of the row to align on). Either side may be omitted (one-sided report).
Exit codes: 0 ok, 1 no usable rows, 2 usage. Read-only; writes only the report (and the selftest's own temp files under
<workspace>/logs/cam_compare_selftest/).
"""
import argparse
import math
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
DEAD_ZONE = 7849                      # XInput's right-stick dead zone (XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE)
NUM = ('t', 'cam_x', 'cam_y', 'cam_z', 'lara_x', 'lara_y', 'lara_z', 'cam_yaw', 'cam_pitch', 'lara_yaw', 'delta_yaw',
       'cam_dir', 'cam_dist', 'cam_fov_deg', 'cam_clock', 'cam_delay', 'cam_ramp', 'cam_weight', 'world_scale',
       'world_dt', 'meter', 'pad_rx', 'pad_ry')


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def fnum(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def read_runs(path):
    """list of runs; a run = list of row dicts (numbers converted, '-' -> None)"""
    runs, cols = [], None
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            parts = line.rstrip('\r\n').split('\t')
            if parts and parts[0] == 'host_time':
                cols = parts
                runs.append([])
                continue
            if not cols or len(parts) != len(cols):
                continue
            r = dict(zip(cols, parts))
            for k in NUM:
                if k in r:
                    r[k] = fnum(r[k])
            r['power'] = r.get('power') == '1'
            runs[-1].append(r)
    return [r for r in runs if r]


def pick_run(runs, which):
    if not runs:
        return []
    if which == 'last':
        return runs[-1]
    i = int(which)
    return runs[i - 1] if 1 <= i <= len(runs) else []


def align_index(rows, how, at):
    if how == 'first':
        return 0
    if how == 'time':
        for i, r in enumerate(rows):
            if r['host_time'] >= at:
                return i
        return None
    for i in range(1, len(rows)):
        if rows[i]['power'] and not rows[i - 1]['power']:
            return i
    return None


def look_inputs(rows):
    """indices where a look input happened: the recenter clock dropped to (near) 0 - the look step's reset (PC 0x5ffe80,
    TU 0x822c2ca0) - or the PC pad's right stick is outside the dead zone"""
    out = []
    for i in range(1, len(rows)):
        a, b = rows[i - 1].get('cam_clock'), rows[i].get('cam_clock')
        rx, ry = rows[i].get('pad_rx'), rows[i].get('pad_ry')
        stick = rx is not None and ry is not None and max(abs(rx), abs(ry)) > DEAD_ZONE
        if stick or (a is not None and b is not None and b < a - 1e-4 and b < 0.2):
            out.append(i)
    return out


def instant_recentres(rows):
    """indices where the clock was SET DOWN to delay + ramp (+-0.1 s) - the instant recenter (PC vslot +0x6c 0x602290 /
    TU slot 0x80 0x822c2130: t = S+0xb4 + S+0xb8), not a look input. Live Xbox 2026-11-10: often while climbing"""
    out = []
    for i in range(1, len(rows)):
        a, b = rows[i - 1].get('cam_clock'), rows[i].get('cam_clock')
        d, r = rows[i].get('cam_delay'), rows[i].get('cam_ramp')
        if a is not None and b is not None and d is not None and r is not None and b < a - 1e-4 and \
                abs(b - (d + r)) <= 0.1:
            out.append(i)
    return out


def side_report(name, rows, i0, window, ref, tol, hold):
    """dict with the per-side numbers from alignment index i0"""
    t0 = rows[i0]['t']
    seg = [r for r in rows[i0:] if r['t'] is not None and r['t'] - t0 <= window]
    rep = {'name': name, 't0': t0, 'host0': rows[i0]['host_time'], 'rows': len(seg), 'seg': seg}
    looks = [i for i in look_inputs(rows) if i >= i0 and rows[i]['t'] - t0 <= window]
    rel = looks[-1] if looks else i0
    rep['release_t'] = rows[rel]['t'] - t0
    rep['looks'] = len(looks)
    inst = [i for i in instant_recentres(rows) if i >= i0 and rows[i]['t'] - t0 <= window]
    rep['instant'] = len(inst)
    on = [r for r in seg if r['power']]
    rep['instant_on'] = sum(1 for i in inst if rows[i]['power'])
    rep['on_s'] = (len(on) * (seg[-1]['t'] - seg[0]['t']) / max(len(seg) - 1, 1)) if len(seg) > 1 else 0.0
    rec = None
    run_start = None
    for r in rows[rel:]:
        if r['t'] - t0 > window:
            break
        d = r.get('delta_yaw')
        ok = d is not None and abs(wrap(d - ref)) <= tol
        if ok:
            if run_start is None:
                run_start = r['t']
            if r['t'] - run_start >= hold:
                rec = run_start - rows[rel]['t']
                break
        else:
            run_start = None
    rep['recentre_s'] = rec
    wfull = None
    for r in rows[rel:]:
        if r['t'] - t0 > window:
            break
        if r.get('cam_weight') is not None and r['cam_weight'] >= 0.999:
            wfull = r['t'] - rows[rel]['t']
            break
    rep['weight1_s'] = wfull
    sets = [r.get('cam_settings') for r in seg if r.get('cam_settings') not in (None, '-', '?')]
    rep['settings'] = max(set(sets), key=sets.count) if sets else '-'
    dl = [r['cam_delay'] for r in seg if r.get('cam_delay') is not None]
    rp = [r['cam_ramp'] for r in seg if r.get('cam_ramp') is not None]
    rep['delay'] = statistics.median(dl) if dl else None
    rep['ramp'] = statistics.median(rp) if rp else None
    ws = [r['world_scale'] for r in seg if r['power'] and r.get('world_scale') is not None]
    rep['world_on'] = statistics.median(ws) if ws else None
    steps = [r.get('cam_step') for r in seg if r.get('cam_step')]
    rep['cam_step'] = steps[0] if steps else '-'
    last = [r['delta_yaw'] for r in seg if r.get('delta_yaw') is not None]
    rep['final_offset'] = wrap(last[-1] - ref) if last else None
    return rep


def meter_rates(rows):
    """refill rate (power off, meter rising) and drain rate (power on, meter falling), units per second; medians of the
    per-segment slopes (segments of >= 0.5 s)"""
    def slopes(on, sign):
        out, seg = [], []
        for i in range(1, len(rows) + 1):
            ok = False
            if i < len(rows):
                a, b = rows[i - 1], rows[i]
                ok = (a['power'] == on and b['power'] == on and a.get('meter') is not None and
                      b.get('meter') is not None and a['t'] is not None and b['t'] is not None and
                      (b['meter'] - a['meter']) * sign > 1e-6)
            if ok:
                if not seg:
                    seg = [rows[i - 1]]
                seg.append(rows[i])
                continue
            if len(seg) >= 2 and seg[-1]['t'] - seg[0]['t'] >= 0.5:
                out.append(abs(seg[-1]['meter'] - seg[0]['meter']) / (seg[-1]['t'] - seg[0]['t']))
            seg = []
        return out
    up = slopes(False, 1.0)
    down = slopes(True, -1.0)
    return (statistics.median(up) if up else None, len(up), statistics.median(down) if down else None, len(down))


def fmt(v, f='%.2f'):
    return '-' if v is None else f % v


def build_report(args, sides):
    L = ['# Kamera-Vergleich Xbox / PC (tools/cam_compare.py)', '',
         'Erzeugt %s. Ausrichtung: %s; Fenster %.0f s; Referenz "hinter Lara" delta_yaw = %.1f Grad; Toleranz %.0f Grad, '
         'Haltezeit %.1f s.' % (time.strftime('%Y-%m-%d %H:%M:%S'), args.align, args.window, args.ref_value, args.tol,
                                args.hold), '']
    L += ['| Datei | Seite | Lauf-Zeilen | Ausrichtung bei |', '|---|---|---|---|']
    for s in sides:
        L.append('| `%s` | %s | %d | %s |' % (s['path'], s['name'], len(s['rows']), s['rep']['host0'] if s['rep'] else '-'))
    L += ['', '## Start-Ausrichtung (erste Zeile des Laufs mit Kamera- und Lara-Yaw, z. B. der DLC-2-Startpunkt)', '',
          '| Seite | Zeit | Kamera-Yaw | Lara-Yaw | delta_yaw | Abweichung von "hinter Lara" | Abstand | Settings |',
          '|---|---|---|---|---|---|---|---|']
    for s in sides:
        r = next((x for x in s['rows'] if x.get('delta_yaw') is not None), s['rows'][0])
        d = r.get('delta_yaw')
        L.append('| %s | %s | %s | %s | %s | %s | %s | %s |' % (
            s['name'], r['host_time'], fmt(r.get('cam_yaw'), '%.1f'), fmt(r.get('lara_yaw'), '%.1f'), fmt(d, '%.1f'),
            fmt(None if d is None else wrap(d - args.ref_value), '%+.1f'), fmt(r.get('cam_dist'), '%.0f'),
            r.get('cam_settings', '-')))
    L += ['', '## Rückführung (ab der letzten Blick-Eingabe nach der Ausrichtung)', '',
          '| Seite | Settings | Wartezeit / Einblendzeit | Zeitschritt | Welt bei Kraft | Blick-Eingaben | letzte bei | '
          'hinter Lara nach | Gewicht 1 nach | Abweichung am Ende | Sofort-Rückführungen (davon mit Kraft) | '
          'Kraft-Zeit |', '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for s in sides:
        p = s['rep']
        if not p:
            L.append('| %s | (keine Ausrichtung gefunden) | | | | | | | | | | |' % s['name'])
            continue
        L.append('| %s | %s | %s / %s s | %s | %s | %d | %s s | %s | %s | %s | %d (%d) | %.1f s |' % (
            s['name'], p['settings'], fmt(p['delay']), fmt(p['ramp']), p['cam_step'], fmt(p['world_on'], '%.2f'),
            p['looks'], fmt(p['release_t'], '%.2f'), fmt(p['recentre_s'], '%.2f s'), fmt(p['weight1_s'], '%.2f s'),
            fmt(p['final_offset'], '%+.1f'), p['instant'], p['instant_on'], p['on_s']))
    L += ['', '## Abweichung von "hinter Lara" über die Zeit (Grad, Mittel je %.1f s)' % args.bin, '']
    head = '| t [s] | ' + ' | '.join('%s Abw. | %s Uhr | %s Kraft' % (s['name'], s['name'], s['name']) for s in sides) + ' |'
    L += [head, '|' + '---|' * (1 + 3 * len(sides))]
    nb = int(args.window / args.bin) + 1
    for k in range(nb):
        lo, hi = k * args.bin, (k + 1) * args.bin
        cells = []
        for s in sides:
            p = s['rep']
            if not p:
                cells += ['-', '-', '-']
                continue
            sel = [r for r in p['seg'] if lo <= r['t'] - p['t0'] < hi]
            ds = [wrap(r['delta_yaw'] - args.ref_value) for r in sel if r.get('delta_yaw') is not None]
            cs = [r['cam_clock'] for r in sel if r.get('cam_clock') is not None]
            pw = [r['power'] for r in sel]
            cells += [fmt(sum(ds) / len(ds) if ds else None, '%+.1f'), fmt(cs[-1] if cs else None, '%.2f'),
                      ('an' if any(pw) else 'aus') if pw else '-']
        if any(c != '-' for c in cells):
            L.append('| %.1f | %s |' % (lo, ' | '.join(cells)))
    L += ['', '## Schattenleiste', '', '| Seite | Auffüllen [Einheiten/s] (Abschnitte) | Verbrauch [Einheiten/s] '
          '(Abschnitte) | Welt bei Kraft |', '|---|---|---|---|']
    for s in sides:
        up, nu, down, nd = meter_rates(s['rows'])
        ws = [r['world_scale'] for r in s['rows'] if r['power'] and r.get('world_scale') is not None]
        L.append('| %s | %s (%d) | %s (%d) | %s |' % (s['name'], fmt(up, '%.1f'), nu, fmt(down, '%.1f'), nd,
                                                    fmt(statistics.median(ws) if ws else None)))
    L += ['', 'Hinweise: delta_yaw = Kamera-Yaw - Lara-Yaw (beide Euler z); "hinter Lara" = --ref (Live-Beleg Xbox '
          '2026-11-10: -180). Blick-Eingabe = Rückführ-Uhr fällt auf ~0 (beide Seiten) oder rechter Stick außerhalb der '
          'Totzone (nur PC); Sofort-Rückführung = das Spiel setzt die Uhr auf Wartezeit + Einblendzeit (PC 0x602290, TU '
          '0x822c2130). Auffüll-/Verbrauchsrate in den Einheiten des Meters (TU meter +8) pro Sekunde Echtzeit.', '']
    return '\n'.join(L)


def load_side(name, path, args, at):
    runs = read_runs(path)
    rows = pick_run(runs, args.run)
    if not rows:
        return None
    i0 = align_index(rows, args.align, at)
    return {'name': name, 'path': path, 'rows': rows, 'i0': i0}


def run(args):
    sides = []
    for name, path, at in (('Xbox', args.xbox, args.xbox_at), ('PC', args.pc, args.pc_at)):
        if not path:
            continue
        s = load_side(name, path, args, at)
        if not s:
            print('no rows in %s' % path)
            continue
        sides.append(s)
    if not sides:
        return 1, ''
    if args.ref == 'auto':
        xb = next((s for s in sides if s['name'] == 'Xbox' and s['i0'] is not None), None)
        if xb:
            tail = [r['delta_yaw'] for r in xb['rows'] if r.get('delta_yaw') is not None and
                    r['t'] >= xb['rows'][-1]['t'] - 2.0]
            args.ref_value = statistics.median(tail) if tail else 180.0
        else:
            args.ref_value = 180.0
    else:
        args.ref_value = float(args.ref)
    for s in sides:
        s['rep'] = side_report(s['name'], s['rows'], s['i0'], args.window, args.ref_value, args.tol, args.hold) \
            if s['i0'] is not None else None
    text = build_report(args, sides)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, 'w', encoding='utf-8-sig', newline='\r\n') as f:
            f.write(text + '\n')
        print('report %s' % args.out)
    else:
        print(text)
    return 0, text


COLS = ('host_time', 't', 'side', 'cam_mode', 'cam_obj', 'cam_x', 'cam_y', 'cam_z', 'lara_x', 'lara_y', 'lara_z',
        'cam_yaw', 'cam_pitch', 'lara_yaw', 'delta_yaw', 'cam_dir', 'cam_dist', 'cam_fov_deg', 'cam_clock',
        'cam_delay', 'cam_ramp', 'cam_weight', 'cam_settings', 'world_scale', 'world_dt', 'power', 'meter', 'dopp',
        'lara_rec0', 'cam_step', 'pad_rx', 'pad_ry', 'pad_buttons')


def synth(path, side, delay, ramp, scale_cam, settings, refill):
    """a climb: 2 s standing (power off, meter refilling), power on at 2 s, a stick input at 3 s turns the camera 60
    degrees off, then auto-recenter: clock += dt * scale_cam, weight = clamp((clock - delay) / ramp), the offset decays
    with the weight"""
    rows = ['\t'.join(COLS)]
    clock, off, meter = 10.0, 0.0, 600.0
    for k in range(0, 600):
        t = k * 0.05
        power = 2.0 <= t < 26.0
        ws = 0.3 if power else 1.0
        if abs(t - 3.0) < 1e-9:
            clock, off = 0.0, 60.0
        else:
            clock += 0.05 * (scale_cam if power else 1.0)
        w = min(max((clock - delay) / ramp, 0.0), 1.0)
        off *= (1.0 - 0.25 * w)
        meter = meter + refill * 0.05 if not power else meter - 40.0 * 0.05
        lara = -154.1
        cam = wrap(lara + 180.0 + off)
        stick = 20000 if (side == 'pc' and abs(t - 3.0) < 1e-9) else 0
        vals = ('12:00:%02d.%03d' % (int(t), int(round((t % 1) * 1000))), '%.3f' % t, side, '1', 'gameplay', '0', '0', '0',
                '0', '0', '0', '%.2f' % cam, '0', '%.2f' % lara, '%.2f' % wrap(cam - lara), '0', '1000', '45.0',
                '%.3f' % clock, '%.2f' % delay, '%.2f' % ramp, '%.3f' % w, settings, '%.3f' % ws, '0.5', int(power),
                '%.1f' % meter, '1', '40', 'tu' if side == 'xbox' else 'retail',
                stick if side == 'pc' else '-', 0 if side == 'pc' else '-', '0x0000' if side == 'pc' else '-')
        rows.append('\t'.join(str(v) for v in vals))
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(rows) + '\n')


def selftest():
    d = os.path.join(ROOT, 'logs', 'cam_compare_selftest')
    os.makedirs(d, exist_ok=True)
    xb, pc, out = os.path.join(d, 'xbox.tsv'), os.path.join(d, 'pc.tsv'), os.path.join(d, 'report.md')
    synth(xb, 'xbox', 0.25, 5.0, 1.0 / 0.3, 'GI+0x14c id 21237', 30.0)
    synth(pc, 'pc', 5.0, 2.0, 1.0, 'GI+0x144 id 20', 15.0)
    a = argparse.Namespace(xbox=xb, pc=pc, xbox_at=None, pc_at=None, align='power', window=30.0, bin=0.5, ref='180',
                           tol=15.0, hold=1.0, run='last', out=out)
    code, text = run(a)
    ok = code == 0
    xs = [s for s in text.splitlines() if s.startswith('| Xbox | GI+0x14c id 21237')]
    ps = [s for s in text.splitlines() if s.startswith('| PC | GI+0x144 id 20')]
    checks = [(len(xs) == 1 and len(ps) == 1, 'settings rows'),
              ('0.25 / 5.00 s' in text and '5.00 / 2.00 s' in text, 'delay / ramp'),
              ('| Xbox | 30.0 (1) |' in text or '| Xbox | 30.0 (' in text, 'Xbox refill 30/s'),
              ('| PC | 15.0 (' in text, 'PC refill 15/s')]
    rx = xs[0].split('|')[8].strip() if xs else '-'
    rp = ps[0].split('|')[8].strip() if ps else '-'
    try:
        checks.append((float(rx.split()[0]) < float(rp.split()[0]), 'Xbox re-centres faster (%s vs %s)' % (rx, rp)))
    except (ValueError, IndexError):
        checks.append((False, 'recentre times %r / %r' % (rx, rp)))
    for good, what in checks:
        print('%s %s' % ('ok  ' if good else 'FAIL', what))
        ok = ok and good
    print('selftest %s' % ('PASSED' if ok else 'FAILED'))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='camera comparison Xbox (TruXenia --camtrace) / PC (TruCam.log)')
    ap.add_argument('--xbox')
    ap.add_argument('--pc')
    ap.add_argument('--align', choices=('power', 'first', 'time'), default='power')
    ap.add_argument('--xbox-at')
    ap.add_argument('--pc-at')
    ap.add_argument('--window', type=float, default=30.0)
    ap.add_argument('--bin', type=float, default=0.5)
    ap.add_argument('--ref', default='180')
    ap.add_argument('--tol', type=float, default=15.0)
    ap.add_argument('--hold', type=float, default=1.0)
    ap.add_argument('--run', default='last')
    ap.add_argument('--out')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.xbox and not a.pc:
        ap.print_usage()
        return 2
    if a.align == 'time' and not (a.xbox_at or a.pc_at):
        print('--align time needs --xbox-at and / or --pc-at')
        return 2
    return run(a)[0]


if __name__ == '__main__':
    sys.exit(main())
