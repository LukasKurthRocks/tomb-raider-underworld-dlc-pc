"""Q74: build the commit versions of docs/ENGINE.md and CHANGELOG.md = HEAD + only the Q74 lines (other agents'
uncommitted hunks in the working tree stay out). Same method as work/q73_trigger_1111/q73_commit_blobs.py: HEAD copies
written by `git show`, working-tree lines taken byte-exact, LF output (core.autocrlf).

Usage (from the repository root):
  ../bin/pyt -t 60 work/q74_spots_1111/q74_commit_blobs.py HEAD_ENGINE HEAD_CHANGELOG OUT_DIR
"""
import sys, os


def lines(p):
    return open(p, 'rb').read().replace(b'\r\n', b'\n').split(b'\n')


def main(argv):
    head_eng, head_chg, out = argv
    wt_eng = lines('docs/ENGINE.md')
    wt_chg = lines('CHANGELOG.md')
    he = lines(head_eng)
    # section 2: the patch 1.1 row after the "File system: [0x9ce278]" row
    r2 = [l for l in wt_eng if l.startswith(b'| **PC patch 1.1 data = `patch.000`** (Q74')]
    assert len(r2) == 1
    j = next(k for k, l in enumerate(he) if l.startswith(b'| File system: [0x9ce278]'))
    he = he[:j + 1] + r2 + he[j + 1:]
    # section 9: the five (Q74) rows after the "Script classes" row
    r9 = [l for l in wt_eng if l.startswith(b'| ') and b'(Q74' in l and not l.startswith(b'| **PC patch 1.1')]
    assert len(r9) == 5, len(r9)
    j = next(k for k, l in enumerate(he) if l.startswith(b'| Script classes | `uberobjectcommand`'))
    he = he[:j + 1] + r9 + he[j + 1:]
    open(os.path.join(out, 'ENGINE.md'), 'wb').write(b'\n'.join(he))
    row = [l for l in wt_chg if l.startswith(b'| 2026-11-11 | **Single dead-end sites** (Q74')]
    assert len(row) == 1
    hc = lines(head_chg)
    last = max(k for k, l in enumerate(hc) if l.startswith(b'| 2026-11-11 |'))
    hc = hc[:last + 1] + row + hc[last + 1:]
    open(os.path.join(out, 'CHANGELOG.md'), 'wb').write(b'\n'.join(hc))
    print('ENGINE rows %d + %d, CHANGELOG row after HEAD line %d' % (len(r2), len(r9), last + 1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
