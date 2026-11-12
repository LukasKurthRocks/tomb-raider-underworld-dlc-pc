"""Q113 Paket R: compare a TruTrace.log session with the expected unit chain (read-only, own code).

Reads TruTrace.log ONLY from one session header ('=== <date time> TruTrace <version> session start (pid N) ===') to the
next header (or the end) and takes the player's way out of it:
  * start unit: 'PLACEMENT in unit <id> '<name>'' (level load / restore) before the first move,
  * every unit change: 'MOVE into a new stream unit: <id> '<a>' -> <id> '<b>'' (game loop 0x5dfc8e),
  * the portal that caused it: 'HIT stream portal <k> (record ...) in unit <a> to unit <b> by ... (player)',
  * checkpoints: 'SAVE_SaveGame(n) by CHECKPOINT reached ...: inst .. obj .. <object> intro <id> ...' and the
    following 'SAVE_SaveGame done: checkpoint copy now unit '<u>', checkpoint id +0x90 <id>',
  * level requests ('REQUEST level change to ...'), other saves, rate-limit notes.
Then it lines the visits up with the expectation (paket_r_expected.tsv from q113_chain.py: step, unit, unit_id, from,
from_id, hit index in the from unit, checkpoints in walking order, cinematics, chapter, sure, note) and prints
  OK    visit as expected (unit, portal index, checkpoints in the expected order),
  DIFF  unit missing / extra / other unit, other portal index, checkpoint of another unit or against the walking order,
  INFO  no HIT before a MOVE (unit change without a portal, e.g. a cutscene), expected checkpoint not reached, repeats.

Usage (from trudlcport):
  ../bin/pyt -t 120 work/q113_chain_1211/compare_trutrace.py LOG [--session TEXT|last|N] [--expected TSV] [--out FILE]
    --session  part of the header line (e.g. 'pid 1234' or '2026-11-12 21:03'), 'last' (default) or the n-th header (1 = first)
    --expected default: paket_r_expected.tsv next to this script
Exit code: 0 = no DIFF, 1 = at least one DIFF, 2 = usage error / no session / nothing to compare.
"""
import sys, os, re, difflib

HEADER = re.compile(r'^=== (.*?) TruTrace (\S+) session start \(pid (\d+)\) ===')
STAMP = r'^(?:(\d{4}-\d{2}-\d{2}) )?(\d{2}:\d{2}:\d{2}\.\d{3}) \[[^\]]*\] (\w+): '
UNIT = r"(\d+) (?:'([^']*)'|\(not loaded\))"
R_MOVE = re.compile(STAMP + r'MOVE into a new stream unit: ' + UNIT + ' -> ' + UNIT)
R_HIT = re.compile(STAMP + r"HIT stream portal (\d+) \(record 0x[0-9a-fA-F]+ '([^']*)'\) in unit " + UNIT + ' to unit ' + UNIT +
                   r' by (.*?) at ')
R_SAVE = re.compile(STAMP + r'SAVE_SaveGame\((\d+)\) by (.*?); active data')
R_CP = re.compile(r'CHECKPOINT reached .*?: inst 0x[0-9a-fA-F]+ obj -?\d+ (\S+) intro (-?\d+)')
R_DONE = re.compile(STAMP + r"SAVE_SaveGame done: checkpoint copy now unit '([^']*)', checkpoint id \+0x90 (\d+)")
R_PLACE = re.compile(STAMP + r'PLACEMENT in unit ' + UNIT)
R_REQ = re.compile(STAMP + r"REQUEST level change to '([^']*)'")
R_LIMIT = re.compile(r'MaxLinesPerCategory|suppressed by the rate limit')


def opt(argv, name, default):
    if name in argv:
        k = argv.index(name)
        if k + 1 >= len(argv): sys.exit(2)
        v = argv[k + 1]; del argv[k:k + 2]; return v
    return default


def read_session(path, which):
    lines = open(path, 'rb').read().decode('utf-8', 'replace').splitlines()
    heads = [i for i, ln in enumerate(lines) if HEADER.match(ln)]
    if not heads: return None, None, 'no session header in %s' % path
    if which == 'last': start = heads[-1]
    elif which.isdigit():
        n = int(which)
        if not 1 <= n <= len(heads): return None, None, 'session %d: the log has %d headers' % (n, len(heads))
        start = heads[n - 1]
    else:
        hit = [i for i in heads if which in lines[i]]
        if len(hit) != 1: return None, None, 'session "%s": %d matching headers (of %d)' % (which, len(hit), len(heads))
        start = hit[0]
    end = next((i for i in heads if i > start), len(lines))
    return lines[start:end], start + 1, None


def name(g_id, g_name):
    return g_name if g_name else 'id%s' % g_id


def parse(sess, first_line):
    """visits [{unit, line, time, via (hit or None), from, saves[(cp id, time, line)], notes[]}], other notes"""
    visits, notes, pending_hit, last_cp = [], [], None, None
    for k, ln in enumerate(sess):
        no = first_line + k
        if R_LIMIT.search(ln): notes.append('INFO  line %d: log limit reached - lines may be missing: %s' % (no, ln[24:150]))
        m = R_PLACE.match(ln)
        if m:
            u = name(m.group(4), m.group(5))
            if not visits or visits[-1]['unit'] != u:
                visits.append(dict(unit=u, line=no, time=m.group(2), via='level load / restore (PLACEMENT)', frm='', hit=None,
                                   saves=[], placed=True))
            continue
        m = R_HIT.match(ln)
        if m:
            if '(player)' not in m.group(10): continue
            pending_hit = dict(idx=int(m.group(4)), frm=name(m.group(6), m.group(7)), to=name(m.group(8), m.group(9)), line=no,
                               time=m.group(2))
            continue
        m = R_MOVE.match(ln)
        if m:
            a, b = name(m.group(4), m.group(5)), name(m.group(6), m.group(7))
            if visits and visits[-1]['unit'] == b:       # e.g. the first move after a level load (-1 -> the placed unit)
                notes.append('INFO  line %d %s: MOVE %s -> %s into the unit Lara is already in (merged)' % (no, m.group(2), a, b))
                pending_hit = None
                continue
            hit = pending_hit if pending_hit and pending_hit['frm'] == a and pending_hit['to'] == b else None
            visits.append(dict(unit=b, line=no, time=m.group(2), via='MOVE', frm=a, hit=hit, saves=[], placed=False))
            pending_hit = None
            continue
        m = R_SAVE.match(ln)
        if m:
            c = R_CP.search(m.group(5))
            if c:
                last_cp = (int(c.group(2)), m.group(2), no, c.group(1))
                if visits: visits[-1]['saves'].append(last_cp)
                else: notes.append('INFO  line %d: checkpoint %s before the first unit line' % (no, c.group(2)))
            else:
                notes.append('INFO  line %d %s: SAVE_SaveGame(%s) by %s' % (no, m.group(2), m.group(4), m.group(5)[:90]))
            continue
        m = R_DONE.match(ln)
        if m and last_cp and int(m.group(5)) != last_cp[0]:
            notes.append('INFO  line %d: checkpoint copy +0x90 %s != checkpoint intro %d of the save before' % (no, m.group(5), last_cp[0]))
            continue
        m = R_REQ.match(ln)
        if m: notes.append('INFO  line %d %s: REQUEST level change to %s' % (no, m.group(2), m.group(4)))
    return visits, notes


def load_expected(path):
    rows = []
    for ln in open(path, encoding='utf-8'):
        if ln.startswith('#') or not ln.strip(): continue
        f = ln.rstrip('\n').split('\t')
        f += [''] * (11 - len(f))
        rows.append(dict(step=int(f[0]), unit=f[1], frm=f[3], hit=[int(x) for x in f[5].split(' / ') if x.strip()],
                         cps=[int(x) for x in f[6].split(',') if x], cines=f[7], chapter=f[8], sure=f[9], note=f[10]))
    return rows


def compare(visits, exp, out):
    diffs = 0
    a = [v['unit'] for v in visits]
    b = [e['unit'] for e in exp]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    seen_cps = {}
    ops = sm.get_opcodes()
    for tag, i1, i2, j1, j2 in ops:
        if tag == 'equal':
            for i, j in zip(range(i1, i2), range(j1, j2)):
                v, e = visits[i], exp[j]
                head = 'step %2d %-26s line %6d %s' % (e['step'], v['unit'], v['line'], v['time'])
                bad = []
                info = []
                if v['via'] == 'MOVE':
                    if v['hit'] is None: info.append('MOVE without a player HIT before it (unit change not through a portal)')
                    elif e['hit'] and v['hit']['idx'] not in e['hit']:
                        bad.append('portal %d, expected %s' % (v['hit']['idx'], ' / '.join(map(str, e['hit']))))
                    if e['frm'] and v['frm'] != e['frm']: bad.append('came from %s, expected %s' % (v['frm'], e['frm']))
                got = [s[0] for s in v['saves']]
                earlier = seen_cps.get(v['unit'], [])
                own = [c for c in got if c in e['cps']]
                rep = [c for c in got if c not in e['cps'] and c in earlier]
                other = [c for c in got if c not in e['cps'] and c not in earlier]
                if other: bad.append('checkpoint(s) %s not expected in this visit' % other)
                if rep: info.append('checkpoint(s) %s again (already reached on an earlier visit)' % rep)
                pos = [e['cps'].index(c) for c in own]
                inv = sum(1 for x in range(len(pos)) for y in range(x + 1, len(pos)) if pos[x] > pos[y])
                if inv: bad.append('checkpoints %s against the walking order %s (%d swapped pair(s))' % (own, e['cps'], inv))
                miss = [c for c in e['cps'] if c not in got]
                if miss and e['cps']: info.append('expected checkpoint(s) %s not reached' % miss)
                seen_cps[v['unit']] = earlier + got
                cp_txt = ('checkpoints %s' % got) if got else 'no checkpoint'
                if bad:
                    diffs += 1
                    out.append('DIFF  %s: %s; %s' % (head, '; '.join(bad), cp_txt))
                else:
                    out.append('OK    %s: %s%s, %s' % (head, 'portal %d' % v['hit']['idx'] if v.get('hit') else v['via'],
                                                       ' (expected %s)' % e['sure'] if e['sure'] != '✅' else '', cp_txt))
                for t in info: out.append('INFO  %s: %s' % (head, t))
        elif tag == 'delete':
            for i in range(i1, i2):
                v = visits[i]
                diffs += 1
                out.append('DIFF  extra visit %-26s line %6d %s (from %s, %s) - not in the expectation here; checkpoints %s' % (
                    v['unit'], v['line'], v['time'], v['frm'] or '-', 'portal %d' % v['hit']['idx'] if v['hit'] else v['via'],
                    [s[0] for s in v['saves']]))
        elif tag == 'insert':
            before_start = i1 == 0 and ops[0] is not None and (tag, i1, i2, j1, j2) == ops[0]
            after_end = i1 == len(visits)
            for j in range(j1, j2):
                e = exp[j]
                if before_start: out.append('INFO  step %2d %-26s before the first visit of this session (not compared)' % (e['step'], e['unit']))
                elif after_end: out.append('INFO  step %2d %-26s after the last visit of this session (not reached)' % (e['step'], e['unit']))
                else:
                    diffs += 1
                    out.append('DIFF  step %2d %-26s expected here, missing in the log' % (e['step'], e['unit']))
        else:   # replace
            for i in range(i1, i2):
                v = visits[i]
                out.append('DIFF  visit %-26s line %6d %s (from %s) where the expectation has %s' % (
                    v['unit'], v['line'], v['time'], v['frm'] or '-', ', '.join(exp[j]['unit'] for j in range(j1, j2))))
                diffs += 1
            if j2 - j1 > i2 - i1:
                for j in range(j1 + (i2 - i1), j2):
                    diffs += 1
                    out.append('DIFF  step %2d %-26s expected, missing in the log' % (exp[j]['step'], exp[j]['unit']))
    return diffs


def main(argv):
    which = opt(argv, '--session', 'last')
    expected = opt(argv, '--expected', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'paket_r_expected.tsv'))
    outp = opt(argv, '--out', None)
    if len(argv) != 1: print(__doc__); return 2
    sess, first, err = read_session(argv[0], which)
    if err: print('ERROR ' + err); return 2
    exp = load_expected(expected)
    visits, notes = parse(sess, first)
    out = ['session: %s (line %d, %d lines)' % (sess[0], first, len(sess)),
           'expected: %s (%d steps)' % (os.path.basename(expected), len(exp)),
           'visits in the log: %s' % (' -> '.join(v['unit'] for v in visits) or 'none')]
    if not visits:
        out.append('ERROR no PLACEMENT / MOVE line in this session (TruTrace [Level] on?)')
        print('\n'.join(out)); return 2
    diffs = compare(visits, exp, out)
    out += notes
    ok = sum(1 for x in out if x.startswith('OK'))
    out.append('summary: %d OK, %d DIFF, %d INFO' % (ok, diffs, sum(1 for x in out if x.startswith('INFO'))))
    text = '\n'.join(out)
    print(text)
    if outp: open(outp, 'w', encoding='utf-8', newline='\n').write(text + '\n')
    return 1 if diffs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
