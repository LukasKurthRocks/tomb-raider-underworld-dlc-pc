"""Check a commit plan (Markdown) against `git status` (read-only).

A commit plan lists its groups as `### <name>` headings, each with a fenced block holding one or more lines
`git add <path> <path> ...`. Paths that stay out of the repository are listed in fenced blocks as lines
`skip <path-or-prefix>` (a prefix ends with '/'). The tool compares that with
`git status --porcelain -uall` (git runs with --no-optional-locks, no index refresh) and prints:
  * per group: the number of paths, and how many of them are modified / new / not in git status
  * every pending path that no group and no skip line covers ("unassigned")
  * every path that is in two groups, or in a group and a skip line ("twice")
  * every group path that git status does not list (already committed, renamed or gone)
Run it right before committing: a path that appeared after the plan was written shows up as unassigned.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/commit_plan_check.py PLAN.md [--list]
  --list   also print the paths of every group
Exit code: 0 = every pending path is covered exactly once, 1 = unassigned / twice / missing paths, 2 = usage error.
"""
import sys, os, re, subprocess, collections


def git_status(root):
    p = subprocess.run(['git', '--no-optional-locks', '-C', root, '-c', 'core.quotepath=off', 'status',
                        '--porcelain=v1', '-z', '-uall'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode('utf-8', 'replace'))
    items = p.stdout.split(b'\0')
    out = collections.OrderedDict()
    i = 0
    while i < len(items):
        it = items[i]
        i += 1
        if not it:
            continue
        code = it[:2].decode('ascii', 'replace')
        if code[0] in 'RC':
            i += 1
        out[it[3:].decode('utf-8', 'replace')] = code
    return out


def read_plan(path):
    groups = collections.OrderedDict()
    skips = []
    group = '(before the first group)'
    fence = False
    for raw in open(path, encoding='utf-8-sig'):
        line = raw.rstrip('\r\n')
        if line.startswith('```'):
            fence = not fence
            continue
        if not fence and line.startswith('### '):
            group = line[4:].strip()
            continue
        if fence and line.startswith('git add '):
            groups.setdefault(group, []).extend(line[8:].split())
        elif fence and line.startswith('skip '):
            skips.append(line[5:].strip())
    return groups, skips


def skipped(path, skips):
    return any(path == s or (s.endswith('/') and path.startswith(s)) for s in skips)


def main(argv):
    if not argv or argv[0].startswith('-'):
        print(__doc__); return 2
    plan = argv[0]
    show = '--list' in argv[1:]
    root = os.getcwd()
    if not os.path.isdir(os.path.join(root, '.git')) or not os.path.isfile(plan):
        print('run from the repository root with an existing plan file'); return 2
    status = git_status(root)
    groups, skips = read_plan(plan)
    owner = collections.defaultdict(list)
    for g, paths in groups.items():
        for p in paths:
            owner[p].append(g)
    total = 0
    print('plan %s: %d groups, %d skip lines; git status: %d paths' % (plan, len(groups), len(skips), len(status)))
    for g, paths in groups.items():
        m = sum(1 for p in paths if status.get(p, '').strip() == 'M')
        n = sum(1 for p in paths if status.get(p) == '??')
        gone = sum(1 for p in paths if p not in status)
        total += len(paths)
        print('  %-70s %3d paths (%d modified, %d new, %d not pending)' % (g[:70], len(paths), m, n, gone))
        if show:
            for p in paths:
                print('      %s %s' % (status.get(p, '--'), p))
    covered_skip = [p for p in status if skipped(p, skips)]
    print('group paths %d, skipped pending paths %d' % (total, len(covered_skip)))
    bad = 0
    una = [p for p in status if p not in owner and not skipped(p, skips)]
    print('unassigned (%d):' % len(una))
    for p in una:
        print('  %s %s' % (status[p], p)); bad += 1
    two = [(p, gs) for p, gs in owner.items() if len(gs) > 1 or skipped(p, skips)]
    print('twice (%d):' % len(two))
    for p, gs in two:
        print('  %s: %s%s' % (p, ' | '.join(gs), ' | skip' if skipped(p, skips) else '')); bad += 1
    miss = [p for p in owner if p not in status]
    print('in the plan, not pending (%d):' % len(miss))
    for p in miss:
        print('  %s (%s)' % (p, ' | '.join(owner[p]))); bad += 1
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
