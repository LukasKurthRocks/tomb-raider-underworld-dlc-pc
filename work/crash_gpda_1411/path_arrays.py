"""Read-only: every inline u16 array {u32 n, ptr -> next word, u16[n]} (UI target paths, tru.exe 0x4d08e0) of the
ported / new scripts in a built g_pda, compared with the pack11 Xbox original at the same offset.
Per element: Xbox value, built value (u16 LE), whether the Xbox value is a member name of the Xbox script, the final
member name the built script gives that member (= what the engine must find), and the encoding of the built word.
Usage (repo root): ../bin/pyt -t 1800 work/crash_gpda_1411/path_arrays.py BUILT_G_PDA [--all]"""
import sys, os, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import gpda_port as GP
import drm_write as DW, drm_reloc as R
import script_member_pairs as MP
from script_u16array_check import arrays, classify


def main(argv):
    show_all = '--all' in argv; argv = [a for a in argv if a != '--all']
    K = GP.load_knowledge()
    I = GP.ids()
    PK = GP.read_pack(); pk = {(s['type'], s['id']): s for s in PK}
    inv = {(t, I(t, x)): (t, x) for (t, x) in pk}
    D = DW.read(open(argv[0], 'rb').read(), 'le'); sec = {(s.type, s.id): s for s in D.sections}
    targets = sorted((k for k, r in K['recipes'].items() if r in ('port', 'new93', 'new')), key=lambda q: int(q.split(':')[1]))
    tot = collections.Counter()
    for key in targets:
        t, sid = map(int, key.split(':'))
        if (t, sid) not in sec or (t, sid) not in inv: continue
        s = sec[(t, sid)]; xs = pk[inv[(t, sid)]]
        xd = xs['data']; xr = R.parse(xs['reloc'], 'be')
        d = s.data
        _, ex = MP.entries(xd, xs['reloc'], 'be')
        _, eb = MP.entries(d, s.reloc, 'le')
        xname_at = {q['a']: q['name'] for q in ex['members']}
        final_at = {q['a']: q['name'] for q in eb['members']}
        x_by_name = {}
        for q in ex['members']: x_by_name.setdefault(q['name'], q['a'])
        built_names = set(final_at.values())
        ptrs = set(xr.pointer_offsets())
        for co, n, at, words in arrays(xd, xr):
            if any(at + 4 * k in ptrs for k in range(words)): continue
            if at + 4 * words > len(d): continue
            xv = list(struct.unpack_from('>%dH' % (2 * words), xd, at))[:n]
            bv = list(struct.unpack_from('<%dH' % (2 * words), d, at))[:n]
            enc = [classify(xd[at + 4 * k:at + 4 * k + 4], d[at + 4 * k:at + 4 * k + 4]) for k in range(words)]
            want = []
            for v in xv:
                a = x_by_name.get(v)
                want.append(final_at[a] if a is not None else None)
            mem = [v in x_by_name for v in xv]
            ok = all(w is None or w == b for w, b in zip(want, bv))
            found = [b in built_names for b in bv]
            tot['arrays'] += 1
            tot['arrays n=%d' % n] += 1
            if not ok: tot['arrays with a member element not = final member name'] += 1
            if mem[0] and not found[0]: tot['arrays whose first (member) element names no member of the built script'] += 1
            if show_all or not ok:
                print('%s +0x%x n=%d xbox %s built %s enc %s | xbox elem is member %s | want %s | built elem is member %s | %s' % (
                    key, at, n, ' '.join('%04x' % v for v in xv), ' '.join('%04x' % v for v in bv), enc, mem,
                    ['%04x' % w if w is not None else '-' for w in want], found, 'ok' if ok else 'BAD'))
    print(dict(tot))


if __name__ == '__main__':
    main(sys.argv[1:])
