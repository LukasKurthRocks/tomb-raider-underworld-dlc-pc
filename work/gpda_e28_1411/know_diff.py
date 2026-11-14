"""E2-8 one-off (read-only): gpda_port knowledge G20261111-3 (learned 2026-11-11 09:42, before the Q58 Symbol twin map)
vs the knowledge re-learned 2026-11-14 with the current maps - rules, ui rules, PC prompt ids, learn stats, member twins.
Based on work/q55_members_1111/know_diff.py; adds member_twins / member_twin_stats.
usage: ../bin/pyt -t 60 work/gpda_e28_1411/know_diff.py OLD.json NEW.json
"""
import sys, json, collections


def main(a, b):
    A = json.load(open(a)); B = json.load(open(b))
    print('version %s -> %s' % (A['version'], B['version']))
    for name in ('rules', 'ui_rules'):
        ra, rb = A[name], B[name]
        ch = [(k, ra.get(k), rb.get(k)) for k in sorted(set(ra) | set(rb)) if ra.get(k) != rb.get(k)]
        c = collections.Counter('%s -> %s' % (x, y) for _, x, y in ch)
        print('%s: %d -> %d, differing keys %d: %s' % (name, len(ra), len(rb), len(ch), dict(c.most_common(20))))
        for k, x, y in ch[:80]: print('   %-45s %s -> %s' % (k, x, y))
    print('text_id_pc: %s -> %s' % (A['text_id_pc'], B['text_id_pc']))
    sa, sb = A['learn_stats'], B['learn_stats']
    for k in sorted(set(sa) | set(sb)):
        if sa.get(k) != sb.get(k): print('stat %-100s %s -> %s' % (k, sa.get(k), sb.get(k)))
    ua, ub = A.get('ui_learn_stats', {}), B.get('ui_learn_stats', {})
    for k in sorted(set(ua) | set(ub)):
        if ua.get(k) != ub.get(k): print('ui stat %-97s %s -> %s' % (k, ua.get(k), ub.get(k)))
    print('changed_members equal: %s' % (A['changed_members'] == B['changed_members']))
    for k in ('recipes', 'reasons', 'base_same', 'pack_md5', 'pc_md5'): print('%s equal: %s' % (k, A.get(k) == B.get(k)))
    ta, tb = A.get('member_twins', {}), B.get('member_twins', {})
    for s in sorted(set(ta) | set(tb)):
        x = {p[0]: p[1] for p in ta.get(s, [])}; y = {p[0]: p[1] for p in tb.get(s, [])}
        diff = [(o, x.get(o), y.get(o)) for o in sorted(set(x) | set(y)) if x.get(o) != y.get(o)]
        print('member_twins %s: %d -> %d entries, differing %d %s' % (s, len(x), len(y), len(diff), diff[:10]))
    sta, stb = A.get('member_twin_stats', {}), B.get('member_twin_stats', {})
    for s in sorted(set(sta) | set(stb)):
        for k in sorted(set(sta.get(s, {})) | set(stb.get(s, {}))):
            va, vb = sta.get(s, {}).get(k), stb.get(s, {}).get(k)
            if va != vb: print('twin stat %s %-90s %s -> %s' % (s, k, va, vb))


if __name__ == '__main__':
    main(*sys.argv[1:3])
