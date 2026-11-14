"""Hex view of one section range in several DRMs, with internal relocations marked. Read-only.
Usage (repo root): ../bin/pyt work/crash_gpda_1411/sec_hex.py TYPE ID OFF_HEX LEN_HEX SPEC...
SPEC = file path (le), 'pc:<name>' (PC archive, le), 'pack:<name>' (pack11, be), 'xbase:<name>' (Xbox base, be)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW, drm_reloc as R
import dtp_word_classes as C

BS = chr(92)


def load(spec):
    if spec.startswith('pc:'):
        return 'le', [(s['type'], s['id'], s['data'] or b'', s['reloc'] or b'') for s in C.find(C.PC, 'le', 'pc-w' + BS + spec[3:])]
    if spec.startswith('pack:'):
        paths = [C.DLC_ROOT + q for q in C.PACKS if q.endswith('/pack11.000')]
        return 'be', [(s['type'], s['id'], s['data'] or b'', s['reloc'] or b'') for s in C.find(paths, 'be', 'xenon-w' + BS + spec[5:])]
    if spec.startswith('xbase:'):
        return 'be', [(s['type'], s['id'], s['data'] or b'', s['reloc'] or b'') for s in C.find(C.BASE, 'be', 'xenon-w' + BS + spec[6:])]
    return 'le', [(s.type, s.id, s.data, s.reloc) for s in DW.read(open(spec, 'rb').read(), 'le').sections]


def main(argv):
    t, i, off, ln = int(argv[0]), int(argv[1]), int(argv[2], 16), int(argv[3], 16)
    for spec in argv[4:]:
        e, S = load(spec)
        hit = [s for s in S if s[0] == t and s[1] == i]
        if not hit:
            print('%s: no section %d:%d' % (spec, t, i)); continue
        _, _, d, rl = hit[0]
        rel = R.parse(rl, e)
        it = dict(rel.internal)
        ext = {so: (si, do) for si, so, do in rel.external}
        print('== %s (%s) %d:%d size 0x%x' % (spec, e, t, i, len(d)))
        for a in range(off, min(off + ln, len(d)), 16):
            row = []
            for w in range(a, min(a + 16, len(d)), 4):
                s = d[w:w + 4].hex()
                if w in it: s += '->%x' % it[w]
                elif w in ext: s += '=>ext%s' % (ext[w],)
                row.append(s)
            print('  +%05x  %s' % (a, '  '.join(row)))


if __name__ == '__main__':
    main(sys.argv[1:])
