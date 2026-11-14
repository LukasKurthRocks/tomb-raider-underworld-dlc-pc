"""Offline reproduction of the crash 2026-11-14 20:33 (new base game, tru.exe +0xc94ac; docs
Befund-Absturz-gpda-NeuesSpiel-1411.md). Read-only.

What the exe does (dump tru.exe.53536.dmp, disassembly of 0x4c9410 / 0x4d08e0 / 0x4c8420):
  0x4c9410 (called from 0x4ce810 when [obj+4]+0x1fc != 0) takes the UI text descriptor D = [[obj+4]+0x1fc] (the init
  node of a uitext member) and walks 8 groups {u32 count, record *} at D+0x7c/+0x80, +0x84/+0x88, +0x8c/+0x90,
  +0x94/+0x98, +0x9c/+0xa0, +0xa4/+0xa8, +0xac/+0xb0, +0xb4/+0xb8; a record (0x10 bytes) is {u32 n entries,
  entries * (8 bytes each: {u32 n, u16 *path})}, path {u32 n, u16 *ids}}. Each path goes to 0x4d08e0(screen, path):
  element 0 = the DataMember with that u16 name in the screen's ScriptType ([[screen+8]+8] = the script section,
  members at +0x2c, name at entry +0xe; 0x4c8420), else a function of that name up the class chain (0x4d0850).
  Not found -> 0x4d08e0 returns the address of a zeroed local, the record path then calls [[ret]+8] = NULL+8.

This script applies that walk to the init node of every uitext member (PC userType 301) of the given scripts and
lists every path element 0 that names neither a member of the script nor a function of its class chain.
Usage (repo root): ../bin/pyt -t 900 work/crash_gpda_1411/emulate_4c9410.py SPEC [SCRIPT_ID,... | all]
  SPEC = a g_pda.drm path or pc:g_pda.drm; default scripts = the ported / new ones (3347 3360 3365 3367 3368 3384
  26427 26428 24318). Exit 1 when a record path (the crashing kind) is unresolved."""
import sys, os, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
from sec_hex import load
import drm_reloc as R
import script_member_pairs as MP

GROUPS = [(0x7c, 0x80), (0x84, 0x88), (0x8c, 0x90), (0x94, 0x98), (0x9c, 0xa0), (0xa4, 0xa8), (0xac, 0xb0), (0xb4, 0xb8)]
UITEXT = 301


def protos(d, rl):
    import script_conv as SC
    W = SC.Walk(d, R.parse(rl, 'le'), 'le').run()
    out = set()
    for nm, t, n, sz in W.arrays:
        if nm == 'protos':
            out |= {struct.unpack_from('<H', d, t + sz * k + 8)[0] for k in range(n)}
    return out


def main(argv):
    e, S = load(argv[0])
    sec = {i: (d, rl) for t, i, d, rl in S if t == 8 and d}
    if len(argv) > 1 and argv[1] == 'all': ids = sorted(sec)        # every script of the file (class chain: same file only)
    else: ids = [int(x) for x in argv[1].split(',')] if len(argv) > 1 else [3347, 3360, 3365, 3367, 3368, 3384, 26427, 26428, 24318]
    st = collections.Counter(); bad = []
    for sid in ids:
        if sid not in sec: continue
        d, rl = sec[sid]
        rel = R.parse(rl, 'le'); it = dict(rel.internal)
        _, E = MP.entries(d, rl, 'le')
        names = collections.Counter(q['name'] for q in E['members'])
        fns, cur, hops = set(), sid, 0
        while cur in sec and hops < 16:          # class chain (super id at root +0x18, an id reference)
            cd, crl = sec[cur]; fns |= protos(cd, crl)
            r = R.parse(crl, 'le')
            cur = struct.unpack_from('<I', cd, 0x18)[0] if 0x18 in r.id_offsets() else None; hops += 1
        u32 = lambda o: struct.unpack_from('<I', d, o)[0]
        resolve = lambda v: 'member' if names[v] else 'function' if v in fns else None
        seen = set()
        for q in E['members']:
            if q['ut'] != UITEXT or q['init'] is None: continue
            node = it.get(q['init'])           # init -> node pointer -> descriptor (as [[obj+4]+0x1fc])
            if node is None or node in seen or node + 0xb8 > len(d): continue
            seen.add(node)
            for cnt_o, ptr_o in GROUPS:
                n = u32(node + cnt_o); recs = it.get(node + ptr_o)
                if not n or recs is None: continue
                if n > 64: st['groups with an implausible count (skipped)'] += 1; continue
                for k in range(n):
                    r0 = recs + 0x10 * k
                    pn, pp = u32(r0 + 8), it.get(r0 + 12)
                    if pn and pp is not None:
                        v = struct.unpack_from('<H', d, pp)[0]
                        st['record paths'] += 1
                        if resolve(v) is None:
                            st['record paths UNRESOLVED (NULL vtable call)'] += 1
                            bad.append('%d member 0x%x (#%d) node +0x%x group +0x%x record %d path +0x%x: element 0 = 0x%04x names no member / function'
                                       % (sid, q['name'], q['k'], node, cnt_o, k, pp, v))
                    en, ep = u32(r0), it.get(r0 + 4)
                    for j in range(en if ep is not None and en <= 64 else 0):
                        an, ap = u32(ep + 8 * j), it.get(ep + 8 * j + 4)
                        if not an or ap is None: continue
                        v = struct.unpack_from('<H', d, ap)[0]
                        st['entry paths'] += 1
                        if resolve(v) is None:
                            st['entry paths unresolved (stack address)'] += 1
                            bad.append('%d member 0x%x node +0x%x group +0x%x record %d entry %d path +0x%x: element 0 = 0x%04x unresolved'
                                       % (sid, q['name'], node, cnt_o, k, j, ap, v))
    for b in bad[:40]: print(' ', b)
    print(argv[0], dict(st))
    sys.exit(1 if st['record paths UNRESOLVED (NULL vtable call)'] else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
