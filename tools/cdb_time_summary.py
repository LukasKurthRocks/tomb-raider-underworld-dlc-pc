"""Summarise a cdb log that times calls with breakpoints at a function's entry and return (finding 43, cloth
stepper tru.exe +0x601c0 / +0x601f8): the entry prints TIN, the hit number, the object (ecx) and `.time`; the
return prints TOUT and `.time`. Reports the duration of every call per object (ms, from the "Debug session time"
lines, 1 ms resolution; breakpoint overhead of about 1-2 ms included). Read-only.
Limit: TIN / TOUT are paired in log order without the thread id - valid when the timed function runs on one thread
(the cloth stepper ran on the main thread in every captured stack); a TIN without its TOUT is dropped.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/cdb_time_summary.py LOG [LOG ...]
"""
import sys, re, collections, datetime

EVAL = re.compile(r'^Evaluate expression: (-?\d+) = ([0-9a-f]{8})')
TIME = re.compile(r'^Debug session time: \w{3} (\w{3} +\d+ [\d:.]+ \d{4})')


def stamp(line):
    m = TIME.match(line)
    return datetime.datetime.strptime(re.sub(' +', ' ', m.group(1)), '%b %d %H:%M:%S.%f %Y') if m else None


def main(argv):
    for p in argv:
        lines = open(p, encoding='utf-8', errors='replace').read().splitlines()
        calls = collections.OrderedDict(); cur = None
        for i, l in enumerate(lines):
            s = l.strip()
            if s == 'TIN':
                if i + 2 >= len(lines): break                  # log cut off (game ended while the breakpoint fired)
                hit = EVAL.match(lines[i + 1]); obj = EVAL.match(lines[i + 2])
                t = next((stamp(x) for x in lines[i + 3:i + 8] if stamp(x)), None)
                cur = (int(obj.group(2), 16), t) if hit and obj and t else None
            elif s == 'TOUT' and cur:
                t = next((stamp(x) for x in lines[i + 1:i + 6] if stamp(x)), None)
                if t: calls.setdefault(cur[0], []).append((t - cur[1]).total_seconds() * 1000)
                cur = None
        n = sum(len(v) for v in calls.values())
        print('== %s: %d timed calls, %d objects' % (p, n, len(calls)))
        for o, d in calls.items():
            print('  object %08x  calls %3d  ms min %7.0f  max %7.0f  mean %7.1f' % (o, len(d), min(d), max(d), sum(d) / len(d)))


if __name__ == '__main__':
    main(sys.argv[1:])
