"""Which of some TARGET functions are reachable through direct calls from ROOT functions in a 32-bit PE such as
tru.exe, with the call depth and the shortest call path (read-only; F10 / B29 shotgun stutter, 04.11.2026: does a
shot reach instance birth / removal, i.e. the cdb breakpoints of session_thrall_watch2?).

Uses the traversal of tools/pe_reach_dec.py (direct calls, tail jumps and jump tables are followed; calls through
registers / vtables / instance callbacks are NOT followed - their count per function is printed).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/pe_reach_calls.py EXE ROOT[,ROOT..] TARGET[,TARGET..] [--depth 6] [--max-funcs 6000]
  e.g. ../bin/pyt -t 900 tools/pe_reach_calls.py ../data/pc/tru.exe 0x6c9e50 0x5bd0f0,0x5bd270,0x5ba650,0x5bc4e0
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_reach_dec as RD


def main(argv):
    argv = list(argv)
    depth = int(RD.opt(argv, '--depth', '6'))
    max_funcs = int(RD.opt(argv, '--max-funcs', '6000'))
    if len(argv) < 3:
        print(__doc__)
        return 2
    img = RD.Image(argv[0])
    roots = [int(x, 16) for x in argv[1].split(',')]
    targets = [int(x, 16) for x in argv[2].split(',')]
    funcs, hits, indirect = RD.explore(img, roots, depth, 0x4, max_funcs, True)
    print('roots %s, depth <= %d: %d functions reached, %d indirect calls not followed' % (
        ','.join('0x%x' % r for r in roots), depth, len(funcs), sum(indirect.values())))
    for t in targets:
        if t in funcs:
            print('0x%x reached at depth %d: %s' % (t, funcs[t][0], RD.path_of(funcs, t)))
        else:
            print('0x%x NOT reached through direct calls' % t)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
