"""RAM per pipeline step from a Measure-TruProcessMemory CSV and the Invoke-TruPipeline logs (read-only; agent pv0511,
2026-11-05).

The CSV (scripts/windows/Measure-TruProcessMemory.ps1: time,pid,start,tool,private_mb,workingset_mb,free_ram_mb) holds
only the time of day; rows are in order, so the date starts at --date and moves on by one day when the time goes back
by more than an hour. Each LOG gives a window: the first and the last time stamp line ("YYYY-MM-DD HH:MM:SS.fff ...").
Per window: number of samples, peak sum of the private memory of all python processes at one sample (without the
--exclude tools, default lsp_server.py = the editor's isort server), peak of one process (its tool name; pool
workers show as '(no script)'), lowest free RAM, and the processes seen.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/mem_steps.py CSV --date YYYY-MM-DD LOG [LOG ...] [--exclude a.py,b.py]
"""
import sys, re, datetime, collections

TS = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)')


def window(log):
    first = last = None
    for line in open(log, encoding='utf-8', errors='replace'):
        m = TS.match(line.lstrip('\ufeff'))
        if m:
            t = datetime.datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')
            if first is None: first = t
            last = t
    return first, last


def load_csv(path, date):
    rows = []; day = datetime.datetime.strptime(date, '%Y-%m-%d'); prev = None
    for line in open(path, encoding='utf-8-sig', errors='replace'):
        t = line.strip().split(',')
        if len(t) != 7 or t[0] == 'time': continue
        tod = datetime.datetime.strptime(t[0], '%H:%M:%S').time()
        cur = datetime.datetime.combine(day.date(), tod)
        if prev is not None and cur < prev - datetime.timedelta(hours=1):
            day += datetime.timedelta(days=1); cur = datetime.datetime.combine(day.date(), tod)
        prev = cur
        rows.append((cur, int(t[1]), t[3], int(t[4]), int(t[5]), int(t[6])))
    return rows


def main(argv):
    if len(argv) < 4 or '--date' not in argv: sys.exit(__doc__)
    csv = argv[0]; date = argv[argv.index('--date') + 1]
    excl = set(argv[argv.index('--exclude') + 1].split(',')) if '--exclude' in argv else {'lsp_server.py'}
    skip = {0, argv.index('--date'), argv.index('--date') + 1}
    if '--exclude' in argv: skip |= {argv.index('--exclude'), argv.index('--exclude') + 1}
    logs = [a for i, a in enumerate(argv) if i not in skip]
    rows = load_csv(csv, date)
    print('csv %s: %d rows, %s .. %s' % (csv, len(rows), rows[0][0] if rows else '-', rows[-1][0] if rows else '-'))
    for log in logs:
        a, b = window(log)
        if a is None: print('%s: no time stamps' % log); continue
        sel = [r for r in rows if a <= r[0] <= b and r[2] not in excl]
        free = [r[5] for r in rows if a <= r[0] <= b]
        per = collections.defaultdict(int); one = (0, '-')
        tools = collections.Counter()
        for r in sel:
            per[r[0]] += r[3]
            if r[3] > one[0]: one = (r[3], r[2])
            tools[(r[2], r[1])] += 1
        names = collections.Counter(t for t, p in tools)
        print('%s\n  window %s .. %s (%d s), samples %d, peak sum %d MB, peak one %d MB (%s), min free %s MB, processes %s'
              % (log, a, b, int((b - a).total_seconds()), len(set(r[0] for r in rows if a <= r[0] <= b)),
                 max(per.values()) if per else 0, one[0], one[1], min(free) if free else '-', dict(names)))
        # per tool: peak of one process and peak of all its processes at one sample (pool workers: '(no script)')
        tsum = collections.defaultdict(lambda: collections.defaultdict(int)); tone = collections.defaultdict(int)
        for r in sel:
            tsum[r[2]][r[0]] += r[3]; tone[r[2]] = max(tone[r[2]], r[3])
        for t in sorted(tone):
            print('    %-32s pids %3d  peak one %7d MB  peak all %7d MB' % (t, names[t], tone[t], max(tsum[t].values())))


if __name__ == '__main__':
    main(sys.argv[1:])
