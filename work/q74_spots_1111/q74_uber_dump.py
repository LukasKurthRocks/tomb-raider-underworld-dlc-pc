"""Q74 (2026-11-11): dump the uberobject state graphs of ONE DRM in its own byte order (read-only).

Same layout as work/gates_0711/uber_graph_dump.py / work/r17e_0811/uber_actions_dump.py (ENGINE.md section 9), but for a
single file (base-game PC LE or Xbox BE; Xbox and PC base DTP ids differ, so the paired dumpers cannot be used):
  DESC 0x54 B: +4 n_nodes, +8 -> nodes, +0xc n_trans, +0x10 -> transitions, +0x14 start node
  NODE 28 B:   +0 / +4 f32, +8 -> name, +0xc n_trans, +0x10 -> array of ptr to TRANS, +0x14 n_act, +0x18 -> actions
  TRANS:       +0 from, +4 to (node index), +8 f32, +0x18 cond, +0x1c arg, +0x28 / +0x2a u16 anim mode / anim,
               +0x34 byte flags (1 play anim, 2 wait for anim)
  action 0x10 B: +0 kind (0x4d86a0 jump table 0x4d8a78), +4.. args
Condition codes (0x4d31e0): 1 time in node >= arg (f32), 3 immediately, 9 object / instance check, 11 / 12 +0x90 & 6
== 2 / 4, 0x10 uber command == arg; anything else is false in 0x4d31e0. Event conditions (Q74): 14 / 15 = joint range
entered / left (0x4d5a50, matched on TRANS +0x20 joint and +0x24 range record {?, min, max} in degrees, printed),
13 = broadcast event (0x4d5b30), other codes = message kind 2 with that value (0x4d4be0). Descriptors are found with a little-endian
port of tools/dtp_schema.find_D (same checks).
Also prints the DTP command table (+0x100 count / +0x104 list of {?, 1, ptr -> message {?, kind +4, value +8}}) when
the words look like one (ENGINE.md 9; message kind 1 set node, 4 command).

Usage (from the repository root):
  ../bin/pyt -t 300 work/q74_spots_1111/q74_uber_dump.py FILE.drm [le|be]
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW
import drm_reloc as R

COND = {1: 'time>=', 3: 'immediately', 9: 'object check', 11: 'flag90==2', 12: 'flag90==4', 0x10: 'command=='}


def cstr(d, o):
    if o is None or o >= len(d): return None
    z = d.find(b'\0', o, o + 80)
    return d[o:z].decode('ascii', 'replace') if z > o else ''


def find_desc(d, it, e):
    u = lambda o: struct.unpack_from(e + 'I', d, o)[0]
    out = []
    for o8, t1 in sorted(it.items()):
        o = o8 - 8
        if o < 0 or o + 0x54 > len(d) or (o + 0x10) not in it or d[o:o + 4] in (b'\xbe\xeb\xbe\xeb', b'\xeb\xbe\xeb\xbe'):
            continue
        n = u(o + 4)
        if not 1 <= n <= 64 or t1 + 28 * n > len(d): continue
        ok = True
        for k in range(n):
            nb = t1 + 28 * k
            nm = cstr(d, it.get(nb + 8))
            if not nm or not all(32 <= ord(c) < 127 for c in nm): ok = False; break
            nt = u(nb + 0xc); na = u(nb + 0x14)
            if nt > 64 or na > 64 or (nt and (it.get(nb + 0x10) is None or any((it[nb + 0x10] + 4 * q) not in it for q in range(nt)))):
                ok = False; break
        if ok: out.append(o)
    return out


def main(argv):
    if not argv:
        print(__doc__); return 2
    e = '<' if (argv[1] if len(argv) > 1 else 'le') == 'le' else '>'
    D = DW.read(open(argv[0], 'rb').read(), 'le' if e == '<' else 'be')
    for s in D.sections:
        if s.type != 7: continue
        d = bytes(s.data); rl = R.parse(bytes(s.reloc), 'le' if e == '<' else 'be'); it = dict(rl.internal)
        ext = {so: (si, do) for si, so, do in rl.external}
        descs = find_desc(d, it, e)
        if not descs: continue
        u = lambda o: struct.unpack_from(e + 'I', d, o)[0]
        f = lambda o: struct.unpack_from(e + 'f', d, o)[0]
        print('== DTP %d (%d B), %d descriptor(s)' % (s.id, len(d), len(descs)))
        if 0x108 <= len(d):
            cnt = u(0x100)
            if 0 < cnt < 64 and 0x104 in it:
                lst = it[0x104]
                print('  command table +0x100: %d entries @0x%x' % (cnt, lst))
                for k in range(cnt):
                    eo = lst + 12 * k
                    if eo + 12 > len(d): break
                    w = struct.unpack_from(e + '3I', d, eo)
                    m = it.get(eo + 8)
                    msg = ' msg @0x%x {%s}' % (m, ' '.join('%08x' % v for v in struct.unpack_from(e + '4I', d, m))) if m is not None and m + 16 <= len(d) else ''
                    print('    cmd %d: %08x %08x%s' % (k, w[0], w[1], msg))
        for o in descs:
            n = u(o + 4); nodes = it[o + 8]
            print('  DESC @0x%x: %d nodes, start node %d, words +0x18.. %s' % (
                o, n, u(o + 0x14), ' '.join('%08x' % u(o + x) for x in range(0x18, 0x54, 4))))
            for k in range(n):
                nb = nodes + 28 * k
                nm = cstr(d, it.get(nb + 8))
                nt = u(nb + 0xc); na = u(nb + 0x14)
                print('    node %d "%s" (f %.3g %.3g) trans %d act %d' % (k, nm, f(nb), f(nb + 4), nt, na))
                ta = it.get(nb + 0x10)
                for q in range(nt):
                    tt = it.get(ta + 4 * q)
                    if tt is None or tt + 0x38 > len(d): continue
                    w = struct.unpack_from(e + '14I', d, tt)
                    c = w[6]
                    arg = ('%.3f' % f(tt + 0x1c)) if c == 1 else str(w[7])
                    a28 = struct.unpack_from(e + '2H', d, tt + 0x28)
                    rng = ''
                    if c == 9 and (tt + 0x1c) in it:
                        r = it[tt + 0x1c]
                        n = u(r + 4) if r + 12 <= len(d) else 0
                        lst = it.get(r + 8)
                        ent = []
                        if lst is not None and n < 16:
                            for k in range(n):
                                ent.append('{%s}' % ' '.join('%08x' % u(lst + 4 * (3 * k + j)) for j in range(3)))
                        rng = '  check @0x%x {%08x n=%d} %s' % (r, u(r), n, ' '.join(ent))
                    if c in (14, 15) and (tt + 0x24) in it:
                        r = it[tt + 0x24]
                        rng = '  joint @0x%x range @0x%x [%.1f, %.1f]' % (it.get(tt + 0x20, -1), r, f(r + 4), f(r + 8)) \
                            if r + 12 <= len(d) else ''
                    print('      trans %d @0x%x: %d -> %d  cond %d %s %s  +8 %.3f  anim {%d, %d} flags %02x  raw %s%s' % (
                        q, tt, w[0], w[1], c, COND.get(c, '?'), arg, f(tt + 8), a28[0], a28[1], d[tt + 0x34],
                        ' '.join('%08x' % v for v in w[2:6] + w[8:10]), rng))
                ac = it.get(nb + 0x18)
                for a in range(na):
                    if ac is None: break
                    ao = ac + 0x10 * a
                    w = struct.unpack_from(e + '4I', d, ao)
                    extra = []
                    for x in range(0, 0x10, 4):
                        if ao + x in it:
                            t = it[ao + x]
                            extra.append('+0x%x -> 0x%x {%s} "%s"' % (x, t, ' '.join('%08x' % v for v in struct.unpack_from(e + '4I', d, t)) if t + 16 <= len(d) else '', cstr(d, t) or ''))
                        if ao + x in ext:
                            extra.append('+0x%x -> ext %s' % (x, ext[ao + x]))
                    print('      action %d: kind %d  %s %s' % (a, w[0], ' '.join('%08x' % v for v in w[1:]), '; '.join(extra)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
