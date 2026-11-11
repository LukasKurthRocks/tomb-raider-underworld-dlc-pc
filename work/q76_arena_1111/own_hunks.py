"""Q76 commit helper: keep only Q76's changes of a unified diff of TruMenu.cpp (another agent edits the same file).

Usage (from the repository root):
  ../bin/pyt -t 60 work/q76_arena_1111/own_hunks.py IN.diff OUT.diff
Drops '+' lines of the other agent (markers below, whole hunks when nothing of Q76 is left), turns the whitespace-only
change of the PhTick line back into context. Apply OUT.diff with `git apply --cached --recount` on a temporary index.
"""
import sys

FOREIGN = ('0.22.27', 'SvTick', 'SvCheck', 'TruSaveProbe', 'g_svLogOn', 'save.pending', 'save.inv', 'save.waiting',
           'save.find', 'RunSvPending', 'RunSvInv', 'RunSvWaiting', 'RunSvFind', 'ValSvStatus')


def hunks(lines):
    head, cur = [], None
    out = []
    for l in lines:
        if l.startswith('@@'):
            if cur: out.append(cur)
            cur = [l]
        elif cur is None:
            head.append(l)
        else:
            cur.append(l)
    if cur: out.append(cur)
    return head, out


def main(argv):
    lines = open(argv[0], encoding='utf-8', newline='').read().split('\n')
    if lines and lines[-1] == '': lines = lines[:-1]
    head, hs = hunks(lines)
    keep = []
    for h in hs:
        body, foreign_block = [], False
        for l in h[1:]:
            if l.startswith('+'):
                text = l[1:]
                if any(m in text for m in FOREIGN):
                    foreign_block = text.rstrip().endswith(',') is False and not text.rstrip().endswith('}')
                    # a multi-line table entry of the other agent: drop the following '+' continuation lines too
                    foreign_block = not text.rstrip().endswith(('},', '};', ');', '}'))
                    continue
                if foreign_block:
                    foreign_block = not text.rstrip().endswith(('},', '};', ');', '}'))
                    continue
                body.append(l)
            else:
                foreign_block = False
                body.append(l)
        # PhTick: whitespace-only change -> context
        minus = [l for l in body if l.startswith('-') and 'PhTick();' in l]
        plus = [l for l in body if l.startswith('+') and 'PhTick();' in l]
        if minus and plus and minus[0][1:].split() == plus[0][1:].split():
            body = [(' ' + l[1:]) if l is minus[0] else l for l in body if l is not plus[0]]
        if any(l.startswith(('+', '-')) for l in body):
            keep.append([h[0]] + body)
    with open(argv[1], 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(head + [l for h in keep for l in h]) + '\n')
    print('%d of %d hunks kept' % (len(keep), len(hs)))


if __name__ == '__main__':
    main(sys.argv[1:])
