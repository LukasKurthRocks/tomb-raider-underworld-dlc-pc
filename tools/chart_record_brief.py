"""One line per chart record index (record-array index, as TruRockVein / TruXenia log it): parent chain, Lara state
ids, activities, transition count - read only (N22 stage 1: what are Lara's combat records 752 / 755 / 718 ...).
Usage: ../bin/pyt -t 300 tools/chart_record_brief.py DRM ENDIAN DTP IDX [IDX ...]"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chart_state_path as CP


def brief(C, idx, depth=0):
    ks = CP.targets(C, idx)
    if not ks:
        return '%d: (none)' % idx
    r, hdr, acts, sids, tr, l20 = C.state(ks[0])
    parent = hdr[3] - 0x10000 if hdr[3] & 0x8000 else hdr[3]
    a = ' '.join('%d/t%d=%s' % (i, ty, CP.fmt_val(C.f, ty, v)) for i, ty, v in acts)
    return '%d: parent %d sids %s trans %d acts %s' % (idx, parent, sids, len(tr), a)


def main():
    a = sys.argv[1:]
    if len(a) < 4:
        print(__doc__)
        return 2
    C = CP.Chart(a[0], a[1], int(a[2]))
    for x in a[3:]:
        line = brief(C, int(x))
        print(line)
        # parent chain sids (the state ids often sit on the parent)
        ks = CP.targets(C, int(x))
        seen = 0
        while ks and seen < 4:
            r, hdr, acts, sids, tr, l20 = C.state(ks[0])
            parent = hdr[3] - 0x10000 if hdr[3] & 0x8000 else hdr[3]
            if parent < 0:
                break
            print('      ^ ' + brief(C, parent))
            ks = CP.targets(C, parent)
            seen += 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
