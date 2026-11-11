"""hall02 combat tutorial episodes from one-shot copies of TruMenu.log and TruShadowCombat.log (read-only; 2026-11-11,
night package Q18: which move sets `tutorial` = 2, why the third tutorial thrall does not come).

For every "Tutorial Text shown" line in TruMenu.log: the matching TruShadowCombat session (paired by plugin start time
of day, so give logs of the same days), Lara's attack records / types on tutorial thralls (0.6.9 'hit list: contact
... added' lines, else '0.6.7 hit:' lines), notification 33 / 34 / 38 lines, and the script lines tutorial /
deathcount / population / clear (repeated dump values printed once per change).

Usage (from the repository root; copy the logs once - never read the live files while the game writes them):
  ../bin/pyt -t 120 tools/hall02_tutorial_episodes.py TRUMENU_LOG TSC_LOG [OUT]
"""
import re
import sys

T = re.compile(r'^(\d\d):(\d\d):(\d\d)\.(\d\d\d) ')


def secs(line):
    m = T.match(line)
    if not m:
        return None
    h, mi, s, ms = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + s + ms / 1000.0


def sessions(lines, start_re):
    """split a log into sessions at its plugin start lines; each = (start seconds, [(seconds, line)])"""
    out = []
    cur = None
    for ln in lines:
        t = secs(ln)
        if t is None:
            continue
        if start_re.search(ln):
            cur = (t, [])
            out.append(cur)
        if cur is not None:
            cur[1].append((t, ln.rstrip('\n')))
    return out


def main(argv):
    tm = open(argv[0], encoding='utf-8', errors='replace').readlines()
    ts = open(argv[1], encoding='utf-8', errors='replace').readlines()
    out = open(argv[2], 'w', encoding='utf-8') if len(argv) > 2 else sys.stdout
    tm_s = sessions(tm, re.compile(r' TruMenu 0\.\d+\.\d+ \('))
    ts_s = sessions(ts, re.compile(r' TruShadowCombat 0\.\d+\.\d+ \('))
    used = set()
    hit_re = re.compile(r'hit list: contact -> (0x[0-9a-f]+) obj 1004 viking_thrall_tutorial\S* at Lara record (\d+), '
                        r'attack type (\d+) .*-> added')
    hit2_re = re.compile(r'0\.6\.7 hit: (0x[0-9a-f]+) obj 1004 viking_thrall_tutorial\S* type (\d+) ')
    note_re = re.compile(r'notification (3[348]) sent|notification 38 as the TU|TranslateNotify33: .*-> ?\d')
    scr_re = re.compile(r'script: (tutorial is \d|deathcount is \d|population is \d|clear|Tutorial Text shown|'
                        r'death count is \d)')
    for k, (st, body) in enumerate(tm_s):
        # pair with the TruShadowCombat session started within 5 s after / 2 s before this TruMenu start
        pair = None
        for j, (st2, b2) in enumerate(ts_s):
            if j not in used and -2.0 <= st2 - st <= 5.0:
                pair = j
                break
        if pair is not None:
            used.add(pair)
        starts = [i for i, (t, ln) in enumerate(body) if 'Tutorial Text shown' in ln]
        for n, i0 in enumerate(starts):
            t0 = body[i0][0]
            t_end = body[starts[n + 1]][0] if n + 1 < len(starts) else body[-1][0]
            print('=' * 100, file=out)
            print('TruMenu session %d start %s, episode %d: tutorial text %s .. %s, TSC session %s'
                  % (k, body[0][1][:12], n + 1, body[i0][1][:12], '%02d:%02d:%06.3f' % (t_end // 3600, t_end % 3600 // 60, t_end % 60),
                     ts_s[pair][1][0][1][:12] if pair is not None else 'none'), file=out)
            ev = []
            last = {}
            for t, ln in body:
                if t0 <= t <= t_end and scr_re.search(ln):
                    key = scr_re.search(ln).group(1)
                    # keep only changes of the repeated dump lines
                    name = key.rsplit(' ', 1)[0]
                    if name in ('tutorial is', 'deathcount is', 'population is', 'death count is'):
                        if last.get(name) == key:
                            continue
                        last[name] = key
                    ev.append((t, 'S ' + key))
            if pair is not None:
                have69 = any('hit list: contact' in ln for t, ln in ts_s[pair][1])
                for t, ln in ts_s[pair][1]:
                    if not (t0 <= t <= t_end):
                        continue
                    m = hit_re.search(ln) if have69 else hit2_re.search(ln)
                    if m:
                        if have69:
                            ev.append((t, 'H %s record %s type %s' % (m.group(1), m.group(2), m.group(3))))
                        else:
                            ev.append((t, 'H %s type %s (0.6.7 hit line)' % (m.group(1), m.group(2))))
                    elif note_re.search(ln):
                        ev.append((t, 'N ' + ln[13:200]))
            ev.sort(key=lambda e: e[0])
            for t, e in ev:
                print('  %02d:%02d:%06.3f %s' % (t // 3600, t % 3600 // 60, t % 60, e), file=out)
    if out is not sys.stdout:
        out.close()


if __name__ == '__main__':
    main(sys.argv[1:])
