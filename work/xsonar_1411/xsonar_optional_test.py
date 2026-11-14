"""xsonar 1411: negative test of the "optional" proof sections in tools/truxenia.py (offline, simulated memory).

Flips one proof word of sonar_triangles in the selftest memory, then checks: the core result stays True, only
sonar_triangles is False, the sonar answer shows its values as '?' and the other sections still read.
Usage (from trudlcport): ../bin/pyt work/xsonar_1411/xsonar_optional_test.py   (exit 0 = ok)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import truxenia as X  # noqa: E402
import xenia_combat_sampler as S  # noqa: E402


def main():
    log = S.Log(os.path.join(HERE, 'optional_test.log'), False, False, False)
    A = json.load(open(X.ADDR_FILE, encoding='utf-8'))
    mem = X.FakeMem(A, log)
    addr = next(iter(A['sonar_triangles']['proof']))
    mem.w32(S.h(addr), S.h(A['sonar_triangles']['proof'][addr]) ^ 1)
    opt = {}
    core = X.check_all_proof(mem, A, log, opt)
    model = X.Model(mem, A, log)
    model.optional_ok = opt
    lines = model.sonar_lines()
    checks = [(core is True, 'core proof result %r' % core),
              (opt.get('sonar_triangles') is False, 'sonar_triangles %r' % opt.get('sonar_triangles')),
              (all(opt.get(k) for k in ('sonar', 'sonar_units', 'sonar_reveal')), 'other sections %r' % opt),
              ('drawn ? ' in lines[1] and 'limit ?' in lines[1], 'triangle line %r' % lines[1]),
              ('mode 3' in lines[0] and any('dlc_yggdrasil_hall01' in x for x in lines), 'other values %r' % lines[:3])]
    bad = 0
    for ok, what in checks:
        print('%s %s' % ('OK  ' if ok else 'FAIL', what))
        bad += 0 if ok else 1
    print('%d checks, %d failed (flipped %s)' % (len(checks), bad, addr))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
