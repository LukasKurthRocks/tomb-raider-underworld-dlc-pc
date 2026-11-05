"""Base-pair evidence for single DTP words (read-only; kit-rest tasks 2 / 4, workspace docs Befund-Kit-Reste-0511.md).

For each Xbox DLC DTP word (NAME, Xbox DTP id, offset) three kinds of evidence from the genuine base-game Xbox / PC
pairs (tools/dtp_audit.base_pairs: same size, same internal pointers):
  key    the dtp_audit fingerprint key of the word (offset in region, slot mask, Xbox value shape, parent slot): all
         base samples with that key - informative count and per permutation (s32 / s16 / raw / b2s16 / s16b2), up
         to 6 examples (Xbox DTP id, offset, Xbox bytes, PC bytes). dtp_audit rules a key at >= 20 / 0 exceptions.
  loose  the same without the value shape (offset in region, slot mask, parent slot)
  twin   tools/dtpid_sweep.analog_of: the nearest base Xbox DTP with the same size + relocation layout and a PC twin;
         the word at the same offset there, Xbox / PC, with its permutation (only when Xbox word is informative)
Permutations are listed by name; a sample counts as informative when exactly the PC bytes are not reachable by all
five (not palindromic) and at least one fits.

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/kitrest_fp_stats.py NAME:XID:OFF[,OFF..] [NAME:XID:OFF ...] [--pack pack10|pack11]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import tuning_word_audit as TA
import dtp_audit as DA
import dtpid_sweep as DS


def names(c):
    return '/'.join(DA.NAMES[i] for i in range(5) if c >> i & 1) or 'none'


def main(a):
    pack = 'pack10'
    if '--pack' in a: k = a.index('--pack'); pack = a[k + 1]; del a[k:k + 2]
    TA.ORDER = (pack, 'pack11' if pack == 'pack10' else 'pack10', 'tu', 'xbase2', 'xbase')
    targets = []                      # (label, xd, xrel, offsets, key per offset)
    want, wloose = collections.defaultdict(list), collections.defaultdict(list)
    st, ids = DS.ctx()
    for spec in a:
        name, xid, offs = spec.split(':')
        xs, src = TA.load_x(name.replace('/', chr(92)) + ('' if name.endswith('.drm') else '.drm'))
        sec = [s for s in xs if s['type'] == 7 and s['id'] == int(xid)]
        if not sec: sys.exit('Xbox DTP %s not in %s' % (xid, name))
        s = sec[0]; xd = s['data']; xr = R.parse(s['reloc'], 'be')
        keys = dict(DA.word_keys(xd, xr))
        ol = [int(x, 16) for x in offs.split(',')]
        lab = '%s Xbox DTP %s (%s, %d bytes)' % (name, xid, src, len(xd))
        targets.append((lab, s, xd, ol, keys))
        for o in ol:
            k = keys.get(o)
            if k is None: continue
            want[k].append((lab, o)); wloose[(k[0], k[1], k[3])].append((lab, o))
    stat = collections.defaultdict(lambda: [0, collections.Counter(), []])
    lstat = collections.defaultdict(lambda: [0, collections.Counter(), []])
    npairs = 0
    for x, p, xb, pc, xr in DA.base_pairs():
        npairs += 1
        xd, pd = xb['data'], pc['data']
        for o, k in DA.word_keys(xd, xr):
            lk = (k[0], k[1], k[3])
            if k not in want and lk not in wloose: continue
            c = DA.cls(xd[o:o + 4], pd[o:o + 4])
            if c == DA.ALL or c == 0: continue
            for tbl, kk, ok in ((stat, k, k in want), (lstat, lk, lk in wloose)):
                if not ok: continue
                v = tbl[kk]; v[0] += 1; v[1][names(c)] += 1
                if len(v[2]) < 6: v[2].append('%d+0x%x %s->%s %s' % (x, o, xd[o:o + 4].hex(), pd[o:o + 4].hex(), names(c)))
    print('base pairs read: %d (dtp_audit.base_pairs)' % npairs)
    for lab, s, xd, ol, keys in targets:
        print('\n=== ' + lab)
        an = DS.analog_of(s, st, ids)
        if an: print('  twin: base Xbox DTP %d (%d differing words of %d)' % (an[1], an[0], len(xd) // 4))
        else: print('  twin: none (no base DTP with the same size + relocation layout)')
        for o in ol:
            k = keys.get(o)
            print('  +0x%x xbox %s  key %s' % (o, xd[o:o + 4].hex(), k))
            if k is None: print('     (slot word: pointer / id reference)'); continue
            v = stat.get(k)
            print('     key  : n=%d %s %s' % ((v[0], dict(v[1]), '| ' + '; '.join(v[2])) if v else (0, '-', '')))
            lv = lstat.get((k[0], k[1], k[3]))
            print('     loose: n=%d %s %s' % ((lv[0], dict(lv[1]), '| ' + '; '.join(lv[2])) if lv else (0, '-', '')))
            if an:
                ax, ap = an[2][o:o + 4], an[3][o:o + 4]
                c = DA.cls(ax, ap)
                print('     twin : %s -> %s %s' % (ax.hex(), ap.hex(), 'palindromic (no evidence)' if c == DA.ALL else names(c)))


if __name__ == '__main__':
    main(sys.argv[1:])
