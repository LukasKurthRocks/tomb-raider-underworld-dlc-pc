"""Offline replay of the second crash of 2026-11-14 (21:50, OBJECTIVES screen, tru.exe 0x4ca2a0 -> 0x5a4ce0 ->
call [[obj]+4] = 0x02000000; dump tru.exe.64032.dmp). Read-only.

0x4ca2a0 (native thunk 0x7a2dbe) walks a widget list: count [w+0x21c], records [w+0x220]. In the crash the widget
was 3347 member #20 (name 0x130e, userType 361) and its init node = {u32 count 15, records *}. Records are
variable-sized {u32 a, u32 n, u16 *path (-> the next word), u16[n] padded}, stride (2n + 0xf) & ~3 (0x4ca2d0); each
path goes to 0x4d08e0 (element 0 = a member of the screen script, else a function up the class chain) and the result
to 0x5a4ce0, which calls through the result's vtable.

The replay takes every init node of every member / arg / local whose first word is a count 1..256 and whose second
word points to a record {a, n, ptr -> record + 0xc} (shape test on the record's pointer, not on n), walks the records
exactly so and reports a record whose path count is implausible (> 64 - e.g. 0x02000000, an Xbox count with the byte
order kept, makes 0x4d08e0 run past the path), whose path pointer is not the next word, or whose element 0 names no
member / function.
Usage (repo root): ../bin/pyt -t 900 work/crash_gpda_1411/emulate_4ca2a0.py SPEC [SCRIPT_ID,... | all]
  SPEC = a g_pda.drm path or pc:g_pda.drm; default = the ported / new scripts. Exit 1 on any bad record."""
import sys, os, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
from sec_hex import load
from emulate_4c9410 import protos
import drm_reloc as R
import script_member_pairs as MP

DEFAULT = [3347, 3360, 3365, 3367, 3368, 3384, 26427, 26428, 24318]


def main(argv):
    e, S = load(argv[0])
    sec = {i: (d, rl) for t, i, d, rl in S if t == 8 and d}
    if len(argv) > 1 and argv[1] == 'all': ids = sorted(sec)
    else: ids = [int(x) for x in argv[1].split(',')] if len(argv) > 1 else DEFAULT
    st = collections.Counter(); bad = []; uts = collections.Counter()
    for sid in ids:
        if sid not in sec: continue
        d, rl = sec[sid]
        rel = R.parse(rl, 'le'); it = dict(rel.internal)
        _, E = MP.entries(d, rl, 'le')
        names = collections.Counter(q['name'] for q in E['members'])
        fns, cur, hops = set(), sid, 0
        while cur in sec and hops < 16:
            cd, crl = sec[cur]; fns |= protos(cd, crl)
            r = R.parse(crl, 'le')
            cur = struct.unpack_from('<I', cd, 0x18)[0] if 0x18 in r.id_offsets() else None; hops += 1
        u32 = lambda o: struct.unpack_from('<I', d, o)[0]
        resolves = lambda v: names[v] > 0 or v in fns
        seen = set()
        for kind, lst in E.items():
            for q in lst:
                n1 = it.get(q['init']) if q['init'] is not None else None
                if n1 is None or n1 in seen or n1 + 8 > len(d): continue
                seen.add(n1)
                cnt, rec = u32(n1), it.get(n1 + 4)
                if not 1 <= cnt <= 256 or rec is None or rec + 12 > len(d) or it.get(rec + 8) != rec + 12: continue
                st['record lists'] += 1; uts[q['ut']] += 1
                p = rec
                for k in range(cnt):
                    st['records'] += 1
                    if p + 12 > len(d): bad.append('%d +0x%x record %d beyond the section' % (sid, n1, k)); break
                    rn = u32(p + 4); pp = it.get(p + 8)
                    where = '%d %s 0x%x (#%d, ut %d) list +0x%x record %d +0x%x' % (sid, kind, q['name'], q['k'], q['ut'], n1, k, p)
                    if rn > 64:
                        bad.append('%s: path count 0x%x (bytes %s) - 0x4d08e0 runs past the path' % (where, rn, d[p + 4:p + 8].hex()))
                        st['records with an implausible path count'] += 1; break
                    if rn and pp != p + 12:
                        bad.append('%s: path pointer %s, not the next word' % (where, pp)); st['records with a bad path pointer'] += 1
                    elif rn and not resolves(struct.unpack_from('<H', d, p + 12)[0]):
                        bad.append('%s: element 0 = 0x%04x names no member / function' % (where, struct.unpack_from('<H', d, p + 12)[0]))
                        st['records whose element 0 is unresolved'] += 1
                    p += (2 * rn + 0xf) & ~3
    for b in bad[:40]: print(' ', b)
    print(argv[0], dict(st), 'userTypes', dict(uts), 'bad', len(bad))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
