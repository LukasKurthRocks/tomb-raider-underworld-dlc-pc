r"""P4a: section diff own tree -> test tree (read-only). Per file: sections changed (type:id, words changed, offsets of
the first changes), sections added / removed; material +0x30 / +0x34 before -> after.
Usage: ../bin/pyt -t 900 work/p4a_shader_1311/verify_p4a.py OWN_MODS TEST_MODS OUT.txt"""
import sys, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import drm_write as DW


def main(a):
    own, test, outp = a[0], a[1], a[2]
    out = open(outp, 'w', encoding='utf-8', newline='\n'); bad = 0; n = 0
    for dp, dn, fn in os.walk(test):
        dn[:] = [d for d in dn if 'truguard' not in d.lower()]
        for f in sorted(fn):
            if not f.lower().endswith('.drm'): continue
            rel = os.path.relpath(os.path.join(dp, f), test); n += 1
            A = DW.read(open(os.path.join(own, rel), 'rb').read(), 'le'); B = DW.read(open(os.path.join(dp, f), 'rb').read(), 'le')
            ka = {(s.type, s.id): s for s in A.sections}; kb = {(s.type, s.id): s for s in B.sections}
            added = sorted(set(kb) - set(ka)); removed = sorted(set(ka) - set(kb))
            ch = []
            for k in sorted(set(ka) & set(kb)):
                x, y = ka[k], kb[k]
                if x.data == y.data and x.reloc == y.reloc: continue
                w = [i for i in range(0, min(len(x.data), len(y.data)) - 3, 4) if x.data[i:i + 4] != y.data[i:i + 4]]
                extra = ''
                if k[0] == 10:
                    extra = ' pass2 %d->%d vs %d->%d' % (struct.unpack_from('<I', x.data, 0x30)[0], struct.unpack_from('<I', y.data, 0x30)[0],
                                                         struct.unpack_from('<I', x.data, 0x34)[0], struct.unpack_from('<I', y.data, 0x34)[0])
                ch.append('%d:%d len %d->%d words %d first %s reloc %s%s' % (k[0], k[1], len(x.data), len(y.data), len(w), [hex(i) for i in w[:6]],
                                                                       'same' if x.reloc == y.reloc else 'DIFF', extra))
            order_ok = [k for k in [(s.type, s.id) for s in B.sections] if k not in added] == [(s.type, s.id) for s in A.sections]
            unexpected = [c for c in ch if not c.startswith('10:')] + (['removed %s' % (removed,)] if removed else []) + ([] if order_ok else ['section order changed'])
            bad += bool(unexpected) or any(t != 9 for t, _ in added)
            out.write('%s: %d sections -> %d, added %s, changed %d%s\n' % (rel, len(A.sections), len(B.sections), added, len(ch),
                                                                     ' UNEXPECTED %s' % unexpected if unexpected else ''))
            for c in ch: out.write('   %s\n' % c)
    out.write('SUMMARY %d files, %d with unexpected changes\n' % (n, bad)); out.close()
    print('SUMMARY %d files, %d with unexpected changes -> %s' % (n, bad, outp))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
