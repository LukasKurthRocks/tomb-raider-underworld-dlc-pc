"""Put a PC fight trace and an Xbox (Xenia) fight trace side by side, read only (TODO N18 "Kampf wie Xbox").

Both sides write the same TSV column layout (header line, tab separated):
  host_time inst obj_id obj_name lp stamina state0 state1 req target dist lara_rec0 lara_rec1 meter active time_scale [..]
PC: TruMenu 0.22.11 `fight.trace 1` -> TruFight.log next to TruMenu.log (columns pc_* after the shared ones).
Xbox: TruXenia `watch <s> <file.tsv>` (tools/truxenia.py; its own extra columns after the shared ones).
Only the shared columns are compared; extra columns are kept per side and listed when asked (--show COL[,COL..]).

The same rules on both sides:
  * enemy rows = rows with an inst other than "-"; per instance the samples are collapsed to changes of
    (lp, state0, state1);
  * a hit = an LP drop of an instance; its reaction = the first other state0 within 1.5 s after the drop
    (else "-"); the hit's state = state0 at the drop;
  * power rows (any row): changes of (active, time_scale) give the power phases (slow < 0.99, fast = active at >= 0.99).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/fight_trace_compare.py --pc TruFight.log --xbox ../logs/truxenia/<file>.tsv
        [--since HH:MM:SS] [--until HH:MM:SS] [--xbox-since ..] [--xbox-until ..] [--enemy NAME_PART]
        [--show COL[,COL..]] [--out compare.md]
Output: Markdown - the hits of both sides in one table (n-th hit PC | n-th hit Xbox), per side the state sequence of
each instance, reaction counts, damage per hit and the power phases. Exit 0, 2 usage / no input.
"""
import argparse
import collections
import csv
import sys

SHARED = ['host_time', 'inst', 'obj_id', 'obj_name', 'lp', 'stamina', 'state0', 'state1', 'req', 'target', 'dist',
          'lara_rec0', 'lara_rec1', 'meter', 'active', 'time_scale']


def secs(ts):
    try:
        h, m, s = ts.split(':')
        return int(h) * 3600 + int(m) * 60 + float(s)
    except ValueError:
        return None


def bound(v):
    if v is None:
        return None
    return secs(v if '.' in v else v + '.000')


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def read(path, since, until):
    rows = []
    with open(path, encoding='utf-8', errors='replace', newline='') as f:
        rd = csv.reader(f, delimiter='\t')
        head = None
        for r in rd:
            if not r:
                continue
            if r[0] == 'host_time':
                head = r                       # files collect sessions: a header may repeat
                continue
            if head is None:
                continue
            row = dict(zip(head, r))
            t = secs(row.get('host_time', ''))
            if t is None:
                continue
            if since is not None and t < since:
                continue
            if until is not None and t > until:
                continue
            row['_t'] = t
            rows.append(row)
    return rows


def enemies(rows, part):
    by = collections.OrderedDict()
    for r in rows:
        if r.get('inst', '-') in ('-', ''):
            continue
        if part and part.lower() not in r.get('obj_name', '').lower():
            continue
        by.setdefault(r['inst'], []).append(r)
    return by


def sequence(rs):
    out, last = [], None
    for r in rs:
        k = (r.get('lp'), r.get('state0'), r.get('state1'))
        if k != last:
            out.append(r)
            last = k
    return out


def hits(by):
    out = []
    for inst, rs in by.items():
        prev = None
        for i, r in enumerate(rs):
            lp = fnum(r.get('lp'))
            if prev is not None and lp is not None and lp < prev - 0.01:
                react = '-'
                for q in rs[i + 1:]:
                    if q['_t'] - r['_t'] > 1.5:
                        break
                    if q.get('state0') != r.get('state0'):
                        react = q.get('state0')
                        break
                out.append({'t': r['host_time'], '_t': r['_t'], 'inst': inst, 'name': r.get('obj_name'),
                            'amount': prev - lp, 'lp0': prev, 'lp': lp, 'state': r.get('state0'), 'reaction': react})
            if lp is not None:
                prev = lp
    out.sort(key=lambda h: h['_t'])
    return out


def phases(rows):
    out, last = [], None
    for r in rows:
        act = r.get('active')
        ts = fnum(r.get('time_scale'))
        if act not in ('True', 'False') or ts is None:
            continue
        mode = 'off' if act == 'False' else ('slow' if ts < 0.99 else 'fast')
        if mode != last:
            out.append((r['host_time'], mode, r.get('meter'), r.get('time_scale')))
            last = mode
    return out


def side_summary(name, hs, by):
    lines = ['### %s' % name, '']
    if hs:
        am = [h['amount'] for h in hs]
        rc = collections.Counter(h['reaction'] for h in hs)
        lines.append('- %d hits, damage %s; reactions %s' % (
            len(hs), ' / '.join('%.0f' % a for a in am[:20]) + (' ..' if len(am) > 20 else ''),
            ', '.join('%s %d' % kv for kv in rc.most_common())))
    else:
        lines.append('- no hits')
    for inst, rs in by.items():
        seq = sequence(rs)
        lines.append('- %s %s: %s' % (rs[0].get('obj_name'), inst, ' > '.join(
            '%s(%s)' % (r.get('state0'), r.get('lp')) for r in seq[:40]) + (' ..' if len(seq) > 40 else '')))
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pc')
    ap.add_argument('--xbox')
    ap.add_argument('--since')
    ap.add_argument('--until')
    ap.add_argument('--xbox-since')
    ap.add_argument('--xbox-until')
    ap.add_argument('--enemy')
    ap.add_argument('--show')
    ap.add_argument('--out')
    a = ap.parse_args()
    if not (a.pc or a.xbox):
        print(__doc__)
        return 2
    pc = read(a.pc, bound(a.since), bound(a.until)) if a.pc else []
    xb = read(a.xbox, bound(a.xbox_since), bound(a.xbox_until)) if a.xbox else []
    pbe, xbe = enemies(pc, a.enemy), enemies(xb, a.enemy)
    ph, xh = hits(pbe), hits(xbe)
    show = [c for c in (a.show or '').split(',') if c]
    lines = ['# Fight trace PC vs Xbox (Xenia)', '', 'PC: `%s` (%d rows); Xbox: `%s` (%d rows)' % (
        a.pc, len(pc), a.xbox, len(xb)), '', '## Hits (n-th hit of each side)', '',
        '| # | PC time | PC enemy | PC LP | PC dmg | PC at hit -> reaction | Xbox time | Xbox enemy | Xbox LP | '
        'Xbox dmg | Xbox at hit -> reaction |', '|---|---|---|---|---|---|---|---|---|---|---|']
    for i in range(max(len(ph), len(xh))):
        p = ph[i] if i < len(ph) else None
        x = xh[i] if i < len(xh) else None
        cp = (p['t'], p['name'], '%.0f->%.0f' % (p['lp0'], p['lp']), '%.0f' % p['amount'],
              '%s -> %s' % (p['state'], p['reaction'])) if p else ('',) * 5
        cx = (x['t'], x['name'], '%.0f->%.0f' % (x['lp0'], x['lp']), '%.0f' % x['amount'],
              '%s -> %s' % (x['state'], x['reaction'])) if x else ('',) * 5
        lines.append('| %d | %s |' % (i + 1, ' | '.join(cp + cx)))
    lines += ['', '## Per side', ''] + side_summary('PC', ph, pbe) + [''] + side_summary('Xbox', xh, xbe)
    lines += ['', '## Power phases (active / time scale)', '']
    for name, rows in (('PC', pc), ('Xbox', xb)):
        lines.append('- %s: %s' % (name, '; '.join('%s %s (meter %s, ts %s)' % p for p in phases(rows)) or '-'))
    if show:
        lines += ['', '## Extra columns', '']
        for name, rows in (('PC', pc), ('Xbox', xb)):
            for c in show:
                vals = collections.Counter(r.get(c, '') for r in rows if c in r)
                if vals:
                    lines.append('- %s %s: %s' % (name, c, ', '.join('%s %d' % kv for kv in vals.most_common(12))))
    text = '\n'.join(lines) + '\n'
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(text)
        print('written %s (%d PC hits, %d Xbox hits)' % (a.out, len(ph), len(xh)))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
