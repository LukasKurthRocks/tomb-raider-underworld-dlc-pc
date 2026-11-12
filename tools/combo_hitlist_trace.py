"""Lara's punch combo against the player's hit list: which chart record each hit landed on and what state 1004 did
to the 8-slot hit list (player +0xa4) at every record change (read only; TODO N18 K-8, 2026-11-10).

Why: Lara's contact hit (PC 0x719050 = TU 0x823e1488) sends the hit message 0x11c only if the target is not yet in
the player's hit list: PC 0x7190ad `call 0x6e6990` (add-if-absent, al = 0 when present) = TU 0x823e152c..0x823e1580
(same loop inline). The list is cleared by state 1004 (record 756 holds it for the combo records 752..762). TU
machine 1 state table 0x82757948 entry 1004 = {0x8245efc8, 0x8245efc8, 0x8245f050}: slot 1 (enter while 1004 was
already active in the previous record) clears it again unless parameter 0x415 is set; retail / PC have no slot 1.
TruShadowCombat 0.5.1 logs that slot as `state 1004 slot 1 (...): off (would): parameter 0x415 P, hit list slots
used U -> TU: list cleared ...` (switch [States] Translate1004=0) or `ON: ...` (=1).

Input (one or more, any order; log files collect many sessions, so only the LAST session that has lines inside
--since / --until is used - a session ends where the time of day jumps back by more than 60 s):
  --menu TruMenu.log          `combo:` lines (TruMenu 0.22.9 combo.trace 1): Lara's records since the last hit, the
                              last one is the record the hit landed on
  --xbox hits_<time>.log      TruXenia hit log (same `combo:` layout) - the Xbox reference
  --combat TruShadowCombat.log  `state 1004 slot` lines, `0.6.8 impulse gate` lines, `0.6.7 hit:` lines
  --fight TruFight.log        Lara's record (column lara_rec0) changes, for the timeline
  --since HH:MM:SS --until HH:MM:SS   window (log time of day); --timeline prints every event in time order

Output: per side the hits by the record they landed on (and the damage), the record chains between two hits; for
TruShadowCombat the re-enter lines of state 1004 slot 1 (hit list used / cleared or not / switch on or off) and, with
--menu and --fight, how many of them were followed by a hit on the re-entered record. Exit 0, 2 usage / no input.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/combo_hitlist_trace.py --menu TruMenu.log --combat TruShadowCombat.log --fight TruFight.log
        --since 21:31:00 --until 21:31:25 [--xbox ../logs/truxenia/hits_20261109_192244.log] [--timeline]
"""
import collections
import re
import sys

TS = r'(?:[0-9]{4}-[0-9]{2}-[0-9]{2} )?([0-9]{2}[:][0-9]{2}[:][0-9]{2}[.][0-9]{3})'   # [YYYY-MM-DD ]HH:MM:SS.mmm (Q107)
COMBO = re.compile(r'^' + TS + r' combo: Lara records (\S*) -> (.+?) (-?\d+) LP (-?[\d.]+) -> (-?[\d.]+) '
                   r'\(-(-?[\d.]+)\).*?state at the hit (\S+), reaction (\S+)')
S1004 = re.compile(r'^' + TS + r' state 1004 slot ([01]) .*?\(call (\d+)\): (ON:|off \(would\):) parameter 0x415 '
                   r'([01]), hit list slots used (\d+) -> TU: (list cleared|list kept)')
GATE = re.compile(r'^' + TS + r' 0\.6\.8 impulse gate: (0x[0-9a-f]+) obj (\d+) \S+ type (\d+) force A\+0x10 ([\d.]+)')
HIT67 = re.compile(r'^' + TS + r' 0\.6\.7 hit: (0x[0-9a-f]+) obj (\d+) \S+ type (\d+) .*?amount ([\d.]+)')


def secs(ts):
    h, m, s = ts.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def bound(x, end):
    if x is None:
        return None
    return secs(x + ('.999' if end else '.000') if len(x) == 8 else x)


def last_session(path, since, until):
    """lines (stripped) of the last session holding a time stamp inside the window"""
    sessions, cur, prev = [], [], None
    for line in open(path, encoding='utf-8', errors='replace'):
        mm = re.match(TS, line)
        if mm:
            t = secs(mm.group(1))
            if prev is not None and t < prev - 60:
                sessions.append(cur)
                cur = []
            prev = t
        cur.append(line.rstrip('\r\n'))
    sessions.append(cur)
    lo, hi = bound(since, False), bound(until, True)

    def inside(line):
        mm = re.match(TS, line)
        if not mm:
            return False
        t = secs(mm.group(1))
        return (lo is None or t >= lo) and (hi is None or t <= hi)
    for s in reversed(sessions):
        got = [x for x in s if inside(x)]
        if got:
            return got
    return []


def combos(path, since, until):
    out = []
    for line in last_session(path, since, until):
        mm = COMBO.match(line)
        if mm:
            g = mm.groups()
            recs = g[1].split('>')
            out.append({'t': g[0], 'recs': recs, 'at': recs[-1] if recs else '?', 'enemy': g[2],
                        'lp0': float(g[4]), 'lp': float(g[5]), 'amount': float(g[6]), 'state': g[7].rstrip(','),
                        'reaction': g[8]})
    return out


def report_hits(name, hits):
    print('## %s: %d hit(s)' % (name, len(hits)))
    if not hits:
        return
    by = collections.OrderedDict()
    for h in hits:
        by.setdefault(h['at'], []).append(h['amount'])
    print('| record at the hit | hits | damage |')
    print('|---|---|---|')
    for r, a in by.items():
        print('| %s | %d | %s |' % (r, len(a), ' / '.join('%g' % x for x in a)))
    print('')
    print('| time | records since the last hit | damage | state at the hit | reaction |')
    print('|---|---|---|---|---|')
    for h in hits:
        print('| %s | %s | -%g | %s | %s |' % (h['t'], '>'.join(h['recs']), h['amount'], h['state'], h['reaction']))
    print('')


def fight_records(path, since, until):
    out, last = [], None
    lines = last_session(path, since, until)
    for line in lines:
        f = line.split('\t')
        if len(f) < 12 or not re.match(TS, f[0]):
            continue
        r = f[11]
        if r != last:
            out.append((f[0], r))
            last = r
    return out


def main():
    a = sys.argv[1:]
    opt = {}
    timeline = '--timeline' in a
    a = [x for x in a if x != '--timeline']
    k = 0
    while k < len(a):
        if a[k] in ('--menu', '--xbox', '--combat', '--fight', '--since', '--until') and k + 1 < len(a):
            opt[a[k][2:]] = a[k + 1]
            k += 2
        else:
            print(__doc__)
            return 2
    if not any(x in opt for x in ('menu', 'xbox', 'combat', 'fight')):
        print(__doc__)
        return 2
    since, until = opt.get('since'), opt.get('until')
    events = []
    pc_hits, recs = [], []
    if 'menu' in opt:
        pc_hits = combos(opt['menu'], since, until)
        report_hits('PC (TruMenu combo lines)', pc_hits)
        events += [(secs(h['t']), h['t'], 'HIT  at %s -%g (%s -> %s)' % (h['at'], h['amount'], h['state'],
                                                                            h['reaction'])) for h in pc_hits]
    if 'xbox' in opt:
        report_hits('Xbox (TruXenia hit log)', combos(opt['xbox'], since if 'menu' not in opt else None,
                                                      until if 'menu' not in opt else None))
    if 'fight' in opt:
        recs = fight_records(opt['fight'], since, until)
        print('## Lara record changes (TruFight lara_rec0): %d' % len(recs))
        print(' '.join('%s@%s' % (r, t) for t, r in recs))
        print('')
        events += [(secs(t), t, 'REC  %s' % r) for t, r in recs]
    if 'combat' in opt:
        lines = last_session(opt['combat'], since, until)
        re_enter = []
        for line in lines:
            mm = S1004.match(line)
            if mm:
                t, slot, call, mode, p415, used, tu = mm.groups()
                on = mode == 'ON:'
                re_enter.append({'t': t, 'slot': int(slot), 'on': on, 'p415': int(p415), 'used': int(used), 'tu': tu})
                events.append((secs(t), t, '1004 slot %s %s p0x415 %s used %s -> TU %s%s' % (
                    slot, 'ON ' if on else 'off', p415, used, tu, '' if on or slot == '0' else ' (PC: nothing)')))
                continue
            mm = GATE.match(line)
            if mm:
                events.append((secs(mm.group(1)), mm.group(1), 'GATE obj %s type %s force %s: impulse 0x91 not sent' % (
                    mm.group(3), mm.group(4), mm.group(5))))
                continue
            mm = HIT67.match(line)
            if mm:
                events.append((secs(mm.group(1)), mm.group(1), '0x11c obj %s type %s amount %s (hit reaction)' % (
                    mm.group(3), mm.group(4), mm.group(5))))
        s1 = [r for r in re_enter if r['slot'] == 1]
        print('## state 1004 slot 1 (re-enter) lines: %d' % len(s1))
        kept_full = [r for r in s1 if not r['on'] and r['used'] > 0 and r['tu'] == 'list cleared']
        print('- switch off, list occupied, TU would clear it (PC keeps it): %d' % len(kept_full))
        print('- switch on (ON:): %d, of them list cleared: %d' % (
            sum(1 for r in s1 if r['on']), sum(1 for r in s1 if r['on'] and r['tu'] == 'list cleared')))
        print('- parameter 0x415 set (TU keeps the list too): %d' % sum(1 for r in s1 if r['p415']))
        if pc_hits and recs:
            # the record a re-enter belongs to = the first TruFight record change within 0.3 s after the line (the
            # trace samples later than the plugin logs); a hit "landed on it" = a combo line with that record as
            # its last one, before Lara's next record change
            changes = [(secs(t), r) for t, r in recs]
            followed, known = 0, 0
            for r in kept_full:
                t0 = secs(r['t'])
                nxt = [c for c in changes if t0 <= c[0] <= t0 + 0.3]
                if not nxt:
                    continue
                known += 1
                rec_t, rec = nxt[0]
                later = [c[0] for c in changes if c[0] > rec_t]
                t1 = later[0] if later else rec_t + 3.0
                if any(h['at'] == rec and t0 < secs(h['t']) <= t1 for h in pc_hits):
                    followed += 1
            print('- of the %d "PC keeps it" re-enters (record known for %d), a hit landed on the re-entered record: '
                  '%d' % (len(kept_full), known, followed))
        print('')
    if timeline and events:
        print('## timeline')
        for _, t, text in sorted(events):
            print('%s  %s' % (t, text))
    return 0


if __name__ == '__main__':
    sys.exit(main())
