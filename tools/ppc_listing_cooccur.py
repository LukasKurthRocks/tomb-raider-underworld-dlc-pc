"""Find places in a PPC text listing (lines 'ADDR  WORD  mnemonic operands', e.g. work/.../tu_all.txt) where several
operand patterns occur within a window of instructions (read-only; N7 2026-11-09: the Xbox counterpart of the PC
per-object light gathering 0x56bbc0, which tests light +0x2ca / +0x2cc / +0x188 / +0x174 and calls the device's
SetLights with count, -1).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/ppc_listing_cooccur.py LISTING WINDOW PATTERN [PATTERN ...]
    PATTERN = a plain substring of the operand text, e.g. "0x2ca(" "0x188(" "li r6, -1"
Output: the first address of each window in which every pattern occurs (one line per 0x100-aligned block), with the
addresses of the matches.
"""
import sys


def main():
    a = sys.argv[1:]
    if len(a) < 3:
        print(__doc__)
        return 2
    path, win, pats = a[0], int(a[1], 0), a[2:]
    lines = []
    with open(path, 'r', errors='replace') as f:
        for ln in f:
            p = ln.split(None, 2)
            if len(p) < 3 or not p[0].startswith('0x'):
                continue
            lines.append((int(p[0], 16), p[2].strip()))
    seen = set()
    hits = 0
    for i, (ad, txt) in enumerate(lines):
        if pats[0] not in txt:
            continue
        lo, hi = max(0, i - win), min(len(lines), i + win + 1)
        found = []
        for pat in pats:
            m = [lines[j][0] for j in range(lo, hi) if pat in lines[j][1]]
            if not m:
                break
            found.append(m[0])
        else:
            blk = ad >> 8
            if blk in seen:
                continue
            seen.add(blk)
            print('0x%08x %s' % (ad, ' '.join('0x%08x' % x for x in found)))
            hits += 1
    print('hits %d' % hits)
    return 0


if __name__ == '__main__':
    sys.exit(main())
