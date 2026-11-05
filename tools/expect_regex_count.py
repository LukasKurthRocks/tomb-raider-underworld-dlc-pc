"""Count the lines of log files that an expect pattern of a test profile matches (read-only).

Invoke-TruTestRun.ps1 matches an expect's "pattern" per line, case-sensitive (.NET regex). This tool does the same with
Python's re for one or more patterns, so a changed pattern can be tried on the logs of earlier runs before a profile
is changed (the simple patterns of the profiles - anchors, classes, alternation, \\s, \\b - behave the same in both).
Per file and pattern: number of matching lines, the first matching line number, and the distinct matches grouped by
their first two words (e.g. "THRALLLINK dyn1").

Usage (from the repository root):
  ../bin/pyt -t 60 tools/expect_regex_count.py --pattern REGEX [--pattern REGEX ...] FILE_OR_RUN_FOLDER [...]
  A run folder means its cdb.log; use --log NAME for another file of the folder (e.g. TruMenu.log).
Exit code: 0 = counted, 2 = usage error / file not found.
"""
import sys, os, re, argparse, collections


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--pattern', action='append', required=True)
    ap.add_argument('--log', default='cdb.log')
    ap.add_argument('paths', nargs='+')
    a = ap.parse_args(argv)
    try:
        rxs = [(p, re.compile(p)) for p in a.pattern]
    except re.error as e:
        print('pattern does not compile: %s' % e); return 2
    rc = 0
    for path in a.paths:
        f = os.path.join(path, a.log) if os.path.isdir(path) else path
        if not os.path.isfile(f):
            print('not found: %s' % f); rc = 2; continue
        lines = open(f, 'rb').read().decode('utf-8', 'replace').replace('\r\n', '\n').replace('\r', '\n').split('\n')
        print('== %s (%d lines)' % (f, len(lines)))
        for p, rx in rxs:
            hits = [(n, l) for n, l in enumerate(lines, 1) if rx.search(l)]
            kinds = collections.Counter(' '.join(l.split()[:2]) for _, l in hits)
            first = hits[0][0] if hits else '-'
            print('  %-50s %6d lines, first %s' % (p, len(hits), first))
            for k, c in sorted(kinds.items()):
                print('      %6d  %s' % (c, k))
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
