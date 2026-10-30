"""Inline u16 arrays in Script sections (type 8): how the converter encoded them (read-only; finding 43, crash after
the DLC 2 intro). Pattern on the Xbox source: a count n (1..64), then an internal pointer whose target is the very
next word, then the n u16 values (e.g. the target path of a UI timeline descriptor: {u32 n, u16 *path, u16[n]}).
Each data word is classified PC vs Xbox: s16 (two u16 swapped in place = right for u16 data), s32 (whole word
swapped = the two u16 trade places), same / other. Run it on a reference tree (B138 DLC 1) and on our trees.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/script_u16array_check.py DIR [DIR ...] [--pack pack11] [--show N]
  several DIRs: the FIRST one that has a file wins (e.g. backups of replaced files before the game folder)
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def classify(x, p):
    if x == p: return 'same'
    if x[::-1] == p and x[1::-1] + x[:1:-1] == p: return 's32=s16'     # equal u16 halves: both swaps agree
    if x[::-1] == p: return 's32'
    if x[1::-1] + x[:1:-1] == p: return 's16'
    return 'other'


def arrays(xd, xr):
    """-> [(count offset, n, first data offset, data words)] for the Xbox section data / relocations"""
    out = []
    for o, t in xr.internal:
        if t != o + 4 or o < 4 or o > len(xd): continue      # data cut to a shorter PC section: skip, don't read past
        n = struct.unpack_from('>I', xd, o - 4)[0]
        if not 1 <= n <= 64: continue
        words = (2 * n + 3) // 4
        if t + 4 * words > len(xd): continue
        out.append((o - 4, n, t, words))
    return out


def main(argv):
    show = 5
    if '--show' in argv: k = argv.index('--show'); show = int(argv[k + 1]); del argv[k:k + 2]
    if '--pack' in argv: k = argv.index('--pack'); os.environ['TRUDLC_PACK_FIRST'] = argv[k + 1]; del argv[k:k + 2]
    import dtp_audit as DA, drm_write as DW, drm_reloc as R
    dbg = None
    if '--debug' in argv: k = argv.index('--debug'); dbg = (argv[k + 1], int(argv[k + 2]), int(argv[k + 3], 16)); del argv[k:k + 4]
    files = DA.overlay([os.path.abspath(d) for d in reversed(argv)], None)
    if dbg:      # --debug REL SECTION_ID OFFSET_HEX: relocations of the Xbox section near the offset
        xs = DA.xsecs(dbg[0])
        print('xsecs:', 'None' if xs is None else len(xs))
        for x in xs or []:
            if x['type'] == 8 and x['id'] == dbg[1]:
                xr = R.parse(x['reloc'], 'be')
                print('reloc', xr)
                print('internal near:', [(hex(o), hex(t)) for o, t in xr.internal if abs(o - dbg[2]) < 0x40])
                print('external near:', [(s, hex(o), hex(t)) for s, o, t in xr.external if abs(o - dbg[2]) < 0x40])
        return
    tot = collections.Counter(); per_file = collections.Counter(); shown = 0
    for rel, path in sorted(files.items()):
        xs = DA.xsecs(rel)
        if xs is None: continue
        D = DW.read(open(path, 'rb').read(), 'le')
        pc8 = {s.id: s for s in D.sections if s.type == 8}       # scripts keep their ids (section_pairs pairs
        for x in xs:                                             # only type 7 when the layouts differ)
            sec = pc8.get(x['id']) if x['type'] == 8 and x['data'] is not None else None
            if sec is None or len(sec.data) != len(x['data']): continue
            xd = x['data']; xr = R.parse(x['reloc'], 'be'); pd = sec.data
            ptrs = set(xr.pointer_offsets())
            for co, n, t, words in arrays(xd, xr):
                if any(t + 4 * k in ptrs for k in range(words)): continue
                cls = [classify(xd[t + 4 * k:t + 4 * k + 4], pd[t + 4 * k:t + 4 * k + 4]) for k in range(words)]
                tot['arrays'] += 1
                for c in cls: tot['words ' + c] += 1
                if 's32' in cls:
                    per_file[rel] += 1
                    if shown < show:
                        shown += 1
                        print('  s32 %s script %d +%#x n=%d xbox %s pc %s' % (
                            rel, sec.id, t, n, xd[t:t + 4 * words].hex(), pd[t:t + 4 * words].hex()))
    print('total: %s' % dict(tot))
    print('files with s32-encoded u16 arrays: %d (%s)' % (len(per_file), ', '.join('%s %d' % kv for kv in sorted(per_file.items())[:12])))


if __name__ == '__main__':
    main(sys.argv[1:])
