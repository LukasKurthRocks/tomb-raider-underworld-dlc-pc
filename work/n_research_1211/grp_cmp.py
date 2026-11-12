"""Group N 12.11.2026 (read-only): print the full 0x84-byte entries of chosen sound groups side by side (word by
word, only rows where the groups differ) for one or more globalsoundinfo sources.

Usage (from trudlcport):
  ../bin/pyt -t 300 work/n_research_1211/grp_cmp.py GSI[,GSI..] G1,G2[,..]
  GSI as in tools/sound_groups.py (pcbig:globalsoundinfo.drm, tu:globalsoundinfo.drm, retail:globalsoundinfo.drm)
"""
import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
import sound_groups as SG


def main(argv):
    srcs = argv[0].split(','); gs = [int(x) for x in argv[1].split(',')]
    for src in srcs:
        T = SG.gsi_table(src)
        print('== %s: %d groups, pause list %s, death %s, fall %s, cats %s' % (src, T['count'], T['pause'], T['death'],
                                                                               T['fall'], T['cats']))
        rows = [T['groups'][g]['words'] for g in gs]
        print('   off  ' + '  '.join('g%-8d' % g for g in gs))
        for k in range(len(rows[0])):
            vals = [r[k] for r in rows]
            if len(set(vals)) > 1:
                print('  +0x%02x  %s' % (4 * k, '  '.join('%-9s' % v for v in vals)))
        print('  (rows not shown are equal)')


if __name__ == '__main__':
    main(sys.argv[1:])
