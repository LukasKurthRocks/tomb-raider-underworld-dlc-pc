"""Group K: build the commit versions of the shared files CHANGELOG.md / docs/ENGINE.md = the HEAD text + only group K's
rows (other agents' uncommitted lines in the working tree stay out). Read only on the inputs.

Usage (from trudlcport):
  ../bin/pyt work/k_menu_1211/my_hunks.py HEAD_FILE WORK_FILE OUT_FILE
Rows of group K = table lines of WORK_FILE containing "(group K" / "group K;" (the CHANGELOG row: "0.22.33 (group K");
each is inserted into HEAD_FILE right after the line that precedes it in WORK_FILE (that anchor line must exist once
in HEAD_FILE, else the line before it, and so on). Lines are compared without CR; OUT_FILE gets LF line ends like the
repository blob (core.autocrlf = true: blobs LF, working tree CRLF).
"""
import sys


def is_mine(line):
    return line.startswith('| ') and ('(Q78, group K)' in line or '(Q83, group K)' in line or
                                       '`TruMenu` 0.22.33 (group K;' in line)


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip())
        return 2
    head = open(argv[0], encoding='utf-8', newline='').read().replace('\r\n', '\n').split('\n')
    work = open(argv[1], encoding='utf-8', newline='').read().replace('\r\n', '\n').split('\n')
    out = list(head)
    added = 0
    for i, line in enumerate(work):
        if not is_mine(line):
            continue
        if line in out:
            continue
        j = i - 1
        while j >= 0:
            anchor = work[j]
            if not is_mine(anchor) and out.count(anchor) == 1:
                break
            if is_mine(anchor) and anchor in out:
                break
            j -= 1
        if j < 0:
            print('no anchor for: %s' % line[:80])
            return 1
        k = out.index(work[j])
        out.insert(k + 1, line)
        added += 1
        print('row after HEAD line %d: %s' % (k + 1, line[:90]))
    with open(argv[2], 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(out))
    print('%d rows added' % added)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
