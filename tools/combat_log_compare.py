"""Put a PC fight and an Xbox (Xenia) fight side by side (TODO N18 "Kampf wie Xbox"), read only.

PC side: TruMenu.log `combo:` lines (TruMenu 0.22.9 `combo.trace 1`) joined with TruShadowCombat.log `damage types`
lines of the same time (+-0.15 s, same LP before) for type / sub / amount. Xbox side: TruXenia's hit log
(tools/truxenia.py, same `combo:` text plus `| xbox: dist .., meter .. active .., time scale ..`).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/combat_log_compare.py --pc-menu TruMenu.log [--pc-combat TruShadowCombat.log]
        --xbox ../logs/truxenia/hits_<time>.log [--since HH:MM:SS] [--until HH:MM:SS] [--xbox-since ..] [--xbox-until ..]
        [--out compare.md]
Output: a Markdown table (hit n of each side in one row) and a summary per side: hits, mean / min / max damage,
reactions (counted), share of hits with a knock-down state (Fall / Vaulted / Knockdown / RegenerateDeath in the name).
Log files collect many sessions; --since / --until (HH:MM:SS of the log) pick the fight. Exit 0, 2 usage.
"""
import argparse
import collections
import re
import sys

TS = r'([0-9]{2}[:][0-9]{2}[:][0-9]{2}[.][0-9]{3})'           # HH:MM:SS.mmm
COMBO = re.compile(r'^' + TS + r' combo: Lara records (\S*) -> (.+?) (-?\d+) LP (-?[\d.]+) -> (-?[\d.]+) '
                   r'\(-(-?[\d.]+)\), stamina (\S+) -> (\S+), state at the hit (\S+), reaction (\S+)(.*)$')
DMG = re.compile(r'^' + TS + r' .*damage types: (0x[0-9a-f]+) obj (\d+) (\S+) type (\d+) sub (\d+) .*?'
                 r'amount (-?[\d.]+), flags (\S+), LP (-?[\d.]+) -> (-?[\d.]+)')
DOWN = ('fall', 'vault', 'knock', 'regeneratedeath', 'land')


def secs(ts):
    h, m, s = ts.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def in_range(ts, since, until):
    t = secs(ts)
    return (since is None or t >= secs(since + '.000' if len(since) == 8 else since)) and \
        (until is None or t <= secs(until + '.999' if len(until) == 8 else until))


def read_combo(path, since, until):
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        mm = COMBO.match(line.strip())
        if mm and in_range(mm.group(1), since, until):
            g = mm.groups()
            out.append({'t': g[0], 'path': g[1], 'enemy': g[2], 'id': g[3], 'lp0': float(g[4]), 'lp': float(g[5]),
                        'amount': float(g[6]), 'st0': g[7], 'st': g[8].rstrip(','), 'hit': g[9].rstrip(','),
                        'reaction': g[10], 'extra': g[11].strip(' |'), 'type': '', 'sub': ''})
    return out


def join_damage(hits, path, since, until):
    if not path:
        return
    dm = []
    for line in open(path, encoding='utf-8', errors='replace'):
        mm = DMG.match(line.strip())
        if mm and in_range(mm.group(1), since, until):
            g = mm.groups()
            dm.append((secs(g[0]), int(g[4]), int(g[5]), float(g[6]), float(g[8])))
    for h in hits:
        t = secs(h['t'])
        best = None
        for d in dm:
            if abs(d[0] - t) <= 0.15 and abs(d[4] - h['lp0']) < 0.05:
                if best is None or abs(d[0] - t) < abs(best[0] - t):
                    best = d
        if best:
            h['type'], h['sub'] = str(best[1]), str(best[2])


def summary(name, hits):
    if not hits:
        return ['- %s: no hits' % name]
    am = [h['amount'] for h in hits]
    rc = collections.Counter(h['reaction'] for h in hits)
    down = sum(1 for h in hits if any(k in h['reaction'].lower() for k in DOWN))
    return ['- %s: %d hits, damage mean %.1f (min %.1f, max %.1f); knock-down reactions %d / %d (%.0f %%); reactions %s'
            % (name, len(hits), sum(am) / len(am), min(am), max(am), down, len(hits), 100.0 * down / len(hits),
               ', '.join('%s %d' % kv for kv in rc.most_common()))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pc-menu')
    ap.add_argument('--pc-combat')
    ap.add_argument('--xbox')
    ap.add_argument('--since')
    ap.add_argument('--until')
    ap.add_argument('--xbox-since')
    ap.add_argument('--xbox-until')
    ap.add_argument('--out')
    a = ap.parse_args()
    if not (a.pc_menu or a.xbox):
        print(__doc__)
        return 2
    pc = read_combo(a.pc_menu, a.since, a.until) if a.pc_menu else []
    join_damage(pc, a.pc_combat, a.since, a.until)
    xb = read_combo(a.xbox, a.xbox_since, a.xbox_until) if a.xbox else []
    lines = ['# Fight comparison PC vs Xbox (Xenia)', '',
             'PC: `%s`%s; Xbox: `%s`' % (a.pc_menu, (' + `%s`' % a.pc_combat) if a.pc_combat else '', a.xbox), '',
             '| # | PC time | PC enemy | PC LP | PC dmg (type/sub) | PC stamina | PC at hit -> reaction | Xbox time | '
             'Xbox enemy | Xbox LP | Xbox dmg | Xbox stamina | Xbox at hit -> reaction | Xbox extra |',
             '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for i in range(max(len(pc), len(xb))):
        p = pc[i] if i < len(pc) else None
        x = xb[i] if i < len(xb) else None
        cp = (p['t'], '%s %s' % (p['enemy'], p['id']), '%.0f->%.0f' % (p['lp0'], p['lp']),
              '%.0f (%s/%s)' % (p['amount'], p['type'] or '?', p['sub'] or '?'), '%s->%s' % (p['st0'], p['st']),
              '%s -> %s' % (p['hit'], p['reaction'])) if p else ('',) * 6
        cx = (x['t'], '%s %s' % (x['enemy'], x['id']), '%.0f->%.0f' % (x['lp0'], x['lp']), '%.0f' % x['amount'],
              '%s->%s' % (x['st0'], x['st']), '%s -> %s' % (x['hit'], x['reaction']), x['extra']) if x else ('',) * 7
        lines.append('| %d | %s |' % (i + 1, ' | '.join(cp + cx)))
    lines += ['', '## Summary', ''] + summary('PC', pc) + summary('Xbox', xb)
    text = '\n'.join(lines) + '\n'
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(text)
        print('written %s (%d PC hits, %d Xbox hits)' % (a.out, len(pc), len(xb)))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
