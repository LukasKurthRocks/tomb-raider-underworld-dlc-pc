"""Find state-chart records by their +0x18 state-id list and print header, all activities ({u16 id, u16 type,
4 value bytes}) and the state ids (read-only; night analysis N5 04.11.2026, F5: which activities run in the wall-run
records of the doppelganger chart, e.g. the record with Lara states [236 230 2102] = TruRockVein "record 1477").

Records as tools/state_actlist_fix.py records() finds them (0x28-byte records, pointers +0x14/+0x18/+0x1c/+0x20).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/chart_rec_by_states.py DRM ENDIAN DTP_ID STATES [STATES ...]
    STATES = comma-separated state ids that the +0x18 list must equal (e.g. 236,230,2102), or 'id=N' for the records
    whose header id (+0x00) is N
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state_actlist_fix as SA
import state_translist_fix as ST


def main():
    a = sys.argv[1:]
    if len(a) < 4:
        sys.exit(__doc__)
    e = a[1]
    f = '>' if e == 'be' else '<'
    _, s = ST.load(a[0], e, int(a[2]))
    d = bytes(s.data)
    recs = SA.records(s, e)
    for want in a[3:]:
        print('== %s' % want)
        for r, sid, hdr, p14, p18, p1c, p20 in recs:
            ids = [struct.unpack_from(f + 'H', d, p18 + 2 * k)[0] for k in range(hdr[6])]
            if want.startswith('id='):
                if sid != int(want[3:]):
                    continue
            elif ids != [int(x) for x in want.split(',')]:
                continue
            print('rec +0x%05x id %d hdr %s states %s' % (r, sid, ' '.join('%04x' % h for h in hdr), ids))
            for k in range(hdr[5]):
                aid, typ = struct.unpack_from(f + 'HH', d, p14 + 8 * k)
                v = d[p14 + 8 * k + 4:p14 + 8 * k + 8]
                print('    act %4d type %3d value %s (u32 %d)' % (aid, typ, v.hex(), struct.unpack(f + 'I', v)[0]))


if __name__ == '__main__':
    main()
