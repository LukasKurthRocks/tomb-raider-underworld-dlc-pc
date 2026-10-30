"""Find 32-bit words that toggle between a few values across a series of memory snapshots (read-only).

Finding 43 / shadow power: the owner held and released LB in DLC 2 (Xenia) while a series of snapshots of the same
guest region was taken; words that switch between two or three values in step with that are candidates for the time
scale, post-effect strength, meter state or "power active" flags. Words are big-endian (Xbox guest memory).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/snapshot_toggle_words.py GLOB GUEST_BASE_HEX [--max-distinct N] [--limit N]
  GLOB         snapshot files of one region, sorted by name (e.g. work/xenia_dump/shadow_series/state_*.bin)
  GUEST_BASE   guest address of byte 0 of each file (e.g. 82740000)
Output per candidate: guest address, offset, number of value changes, the value sequence (floats shown as such when
plausible) - sorted with float words that include 1.0f first, then by number of changes.
"""
import sys, glob, struct


def as_text(v):
    f = struct.unpack('>f', struct.pack('>I', v))[0]
    if v != 0 and 1e-4 < abs(f) < 1e5:
        return '%.4g' % f
    return '0x%x' % v


def main(argv):
    max_distinct, limit = 3, 60
    if '--max-distinct' in argv:
        k = argv.index('--max-distinct'); max_distinct = int(argv[k + 1]); del argv[k:k + 2]
    if '--limit' in argv:
        k = argv.index('--limit'); limit = int(argv[k + 1]); del argv[k:k + 2]
    files = sorted(glob.glob(argv[0])); base = int(argv[1], 16)
    data = [open(f, 'rb').read() for f in files]
    n = min(len(d) for d in data) // 4 * 4
    print('%d snapshots, %d bytes compared' % (len(data), n))
    cands = []
    for o in range(0, n, 4):
        first = data[0][o:o + 4]
        if all(d[o:o + 4] == first for d in data[1:]):
            continue
        seq = [struct.unpack_from('>I', d, o)[0] for d in data]
        distinct = set(seq)
        if len(distinct) > max_distinct:
            continue
        changes = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
        has_one = 0x3f800000 in distinct
        cands.append((not has_one, -changes, o, seq))
    cands.sort()
    print('%d candidates with 2..%d distinct values' % (len(cands), max_distinct))
    for no_one, negc, o, seq in cands[:limit]:
        print('0x%08x +0x%06x changes %2d  %s' % (base + o, o, -negc, ' '.join(as_text(v) for v in seq)))


if __name__ == '__main__':
    main(sys.argv[1:])
