"""Constants pushed in script bytecode right before a call (read-only; finding 43, DLC string ids passed as
constants). Script words: opcode in the top byte, operand in the low 24 bits; `op0f N` pushes N, `op00 N` is a line
marker, `op65` calls a native / function whose target is the external relocation on the following word.

For every `op0f N` with LO <= N <= HI in a script (type 8) of the converted DRMs, the next call within --window
words is taken; reports per call target (section id, offset in it) how many constants and which values were
passed. Run it on PC files (little-endian).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/script_const_calls.py DIR LO HI [--window 6] [--min-id 0]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

PUSH, CALL = 0x0f, 0x65


def calls(D, sec, lo, hi, window):
    """-> [(push offset, value, call offset, (target section id, target offset) or None)]"""
    r = R.parse(sec.reloc, 'le')
    ext = {src: (D.sections[si].id if si < len(D.sections) else -1, dst) for si, src, dst in r.external}
    w = sec.data; n = len(w) // 4; out = []
    for k in range(n):
        v = struct.unpack_from('<I', w, 4 * k)[0]
        if v >> 24 != PUSH or not lo <= (v & 0xffffff) <= hi: continue
        tgt = None; co = None
        for j in range(k + 1, min(n - 1, k + 1 + window)):
            u = struct.unpack_from('<I', w, 4 * j)[0]
            if u >> 24 == CALL: co = 4 * j; tgt = ext.get(4 * j + 4); break
        out.append((4 * k, v & 0xffffff, co, tgt))
    return out


def main(argv):
    window = 6; min_id = 0
    if '--window' in argv: k = argv.index('--window'); window = int(argv[k + 1]); del argv[k:k + 2]
    if '--min-id' in argv: k = argv.index('--min-id'); min_id = int(argv[k + 1]); del argv[k:k + 2]
    root, lo, hi = argv[0], int(argv[1]), int(argv[2])
    per_tgt = collections.defaultdict(collections.Counter); where = collections.defaultdict(set)
    for dp, dn, fn in os.walk(root):
        for f in sorted(fn):
            if not f.lower().endswith('.drm'): continue
            p = os.path.join(dp, f)
            try: D = DW.read(open(p, 'rb').read(), 'le')
            except Exception as e: print('  skipped %s: %s' % (p, e)); continue
            for sec in D.sections:
                if sec.type != 8 or sec.id < min_id: continue
                for po, val, co, tgt in calls(D, sec, lo, hi, window):
                    per_tgt[tgt][val] += 1; where[tgt].add(sec.id)
    for tgt, c in sorted(per_tgt.items(), key=lambda kv: -sum(kv[1].values())):
        print('target %s: %d pushes, %d values, scripts %s' % (tgt, sum(c.values()), len(c), sorted(where[tgt])[:10]))
        print('   values: %s' % ' '.join('%d' % v for v in sorted(c)[:30]))


if __name__ == '__main__':
    main(sys.argv[1:])
