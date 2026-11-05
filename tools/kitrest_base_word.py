"""Base-game Xbox / PC words of a DTP that a DLC DRM carries under a BASE id (read-only; kit-rest task 2,
workspace docs Befund-Kit-Reste-0511.md).

A DLC DRM can contain a copy of a base-game DTP (Xbox id < 20000, PC id from the base id map). For such a section
this prints, per offset: the DLC Xbox copy's word, the base Xbox word (generic store xb_store), the genuine PC base
word (pc_store, PC id via the base id map) and the permutation classes - i.e. whether a PC value that differs from
the plain byte-order rule is the genuine PC re-authoring of the base resource (then the DLC copy should keep it
only if the DLC Xbox copy equals the base Xbox section).

Usage (from the repository root):
  ../bin/pyt -t 1200 tools/kitrest_base_word.py NAME:XID:OFF[,OFF..] [...] [--pack pack10|pack11]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tuning_word_audit as TA
import dtpid_sweep as DS


def main(a):
    pack = 'pack10'
    if '--pack' in a: k = a.index('--pack'); pack = a[k + 1]; del a[k:k + 2]
    TA.ORDER = (pack, 'pack11' if pack == 'pack10' else 'pack10', 'tu', 'xbase2', 'xbase')
    st, ids = DS.ctx()
    for spec in a:
        name, xid, offs = spec.split(':'); xid = int(xid)
        xs, src = TA.load_x(name.replace('/', chr(92)) + ('' if name.endswith('.drm') else '.drm'))
        sec = [s for s in xs if s['type'] == 7 and s['id'] == xid]
        if not sec: print('%s: Xbox DTP %d not found' % (name, xid)); continue
        d = sec[0]
        xb = st['xb_store'].get((7, xid)); pid = ids.base.get(7, {}).get(xid)
        pc = st['pc_store'].get((7, pid)) if pid is not None else None
        print('=== %s (%s) Xbox DTP %d, %d bytes | base Xbox %s | PC base id %s %s' % (
            name, src, xid, len(d['data']), ('%d bytes, data %s, reloc %s' % (len(xb['data']), 'EQUAL' if xb['data'] == d['data'] else 'differs',
                                                                    'equal' if xb['reloc'] == d['reloc'] else 'differs')) if xb else 'none',
            pid, ('%d bytes' % len(pc['data'])) if pc else '(no PC section)'))
        if xb and xb['data'] != d['data']:
            n = min(len(xb['data']), len(d['data']))
            diff = [o for o in range(0, n - 3, 4) if xb['data'][o:o + 4] != d['data'][o:o + 4]]
            print('  DLC Xbox copy vs base Xbox: %d differing words%s' % (len(diff), (' (first: %s)' % ' '.join('+0x%x' % o for o in diff[:12])) if diff else ''))
        import drm_reloc as R
        idsl = R.parse(d['reloc'], 'be').id_offsets()
        for o in [int(x, 16) for x in offs.split(',')]:
            if o in idsl:
                t = idsl[o]; v = int.from_bytes(d['data'][o:o + 4], 'big')
                m = ids.base.get(t, {}).get(v)
                try: dm = ids(t, v)
                except Exception as e: dm = 'error %s' % str(e)[:40]
                print('  +0x%x is an id reference slot: section type %d, Xbox id %d (0x%x) -> base map %s, DLC map %s' % (
                    o, t, v, v, m, dm))
            dw = d['data'][o:o + 4]
            bw = xb['data'][o:o + 4] if xb and o + 4 <= len(xb['data']) else None
            pw = pc['data'][o:o + 4] if pc and o + 4 <= len(pc['data']) else None
            print('  +0x%x DLC Xbox %s | base Xbox %s | PC base %s (LE %s) class %s' % (
                o, dw.hex(), bw.hex() if bw else '-', pw.hex() if pw else '-', pw[::-1].hex() if pw else '-',
                TA.cls(bw, pw) if bw and pw else '-'))


if __name__ == '__main__':
    main(sys.argv[1:])
