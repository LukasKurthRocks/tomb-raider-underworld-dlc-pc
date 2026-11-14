"""TruMenu 0.22.52 sonar fade: READ-ONLY live read of the sonar's draw materials (TruLink read only, the whitelist of
work/fmod_1411/fmod_live.py: read / read32 / readf).

Usage (from trudlcport):
  ../bin/pyt -t 900 work/menu52_1411/sonar_material_live.py OUT.txt

Static (work/menu52_1411/_archiv/dis_sonar.txt, 0x6e4c1e..0x6e4c83): the sonar view copies the tuning [0xee03e0]
+0x34 .. +0x50 to 0xee03f0 .. 0xee040c and puts tuning +0x34 / +0x40 / +0x4c / +0x50 into the four batches' material
field (batch +0x29044: 0xf09534 faces A, 0xf32580 faces B, 0xf5b5cc, 0xf84618); the flush 0x6df9e0 hands batch +0x29044
to the device's primitive call (vtable 0x8492cc +0x4c = 0x503fa0 -> 0x503990, material +4 -> data, +0x44 flags).
ENGINE 17.2: MaterialSection hash {buckets [0x8a6ebc], nodes [0x8a6ec4]} node {next, id, PCMaterial*, data, refs, size};
ShaderLibSection hash {[0x8a6ef0], [0x8a6ef8]} (node layout assumed the same); PCMaterial 0x1c B (vtable 0x849018);
material data +0x28..+0x34 = PS0 / PS1 / PS2 / VS (PCShaderLib* at run time), +0x38 blend, +0x58 / +0x5c PS params
(count / pointer, PS c100), +0x68 / +0x6c VS params (VS c25).
"""
import os, struct, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'fmod_1411'))
import fmod_live as FL   # noqa: E402

FL.TMP = os.path.join(HERE, 'live_tmp')


def hash_walk(m, cnt_at, tab_at, tag, want):
    """reverse lookup: {pointer: id} for the values in want, walking every bucket chain in lockstep"""
    m.fetch([(cnt_at, 4), (tab_at, 4)], tag + '_h')
    n, tab = m.u32(cnt_at), m.u32(tab_at)
    found, nodes = {}, 0
    if not n or not tab or n > 200000:
        return found, n, 0
    m.fetch([(tab, n * 4)], tag + '_t')
    cur = [m.u32(tab + 4 * i) for i in range(n)]
    cur = [p for p in cur if p]
    step = 0
    while cur and step < 32:
        m.fetch([(p, 0x18) for p in cur], '%s_n%d' % (tag, step))
        nxt = []
        for p in cur:
            nodes += 1
            ident, obj, data = m.u32(p + 4), m.u32(p + 8), m.u32(p + 0xc)
            if obj in want:
                found[obj] = (ident, data, p)
            q = m.u32(p)
            if q:
                nxt.append(q)
        cur = nxt
        step += 1
    return found, n, nodes


def main(out):
    t0 = time.time()
    m = FL.Mem()
    L = []
    P = L.append
    m.fetch([(0xee03e0, 4), (0xee03c8, 4), (0xf09534, 4), (0xf32580, 4), (0xf5b5cc, 4), (0xf84618, 4),
             (0xdb6a54, 4), (0xdb73e0, 4)], 's_roots')
    tun = m.u32(0xee03e0)
    m.fetch([(tun, 0x80)], 's_tuning')
    mats = {}
    for off in range(0x34, 0x54, 4):
        mats['tuning+0x%02x' % off] = m.u32(tun + off)
    for nm, at in (('batch A (0xf09534)', 0xf09534), ('batch B (0xf32580)', 0xf32580), ('batch C (0xf5b5cc)', 0xf5b5cc),
                   ('batch D (0xf84618)', 0xf84618)):
        mats[nm] = m.u32(at)
    P('sonar materials %s: sonar mode [0xee03c8] = %s, tuning 0x%08x, fog near/far globals [0xdb6a54] %s / [0xdb73e0] %s' % (
        time.strftime('%Y-%m-%d %H:%M:%S'), m.u32(0xee03c8), tun or 0, m.f32(0xdb6a54), m.f32(0xdb73e0)))
    P('tuning +0x00..+0x7c: %s' % ' '.join('%08x' % (m.u32(tun + o) or 0) for o in range(0, 0x80, 4)))
    ptrs = set(v for v in mats.values() if v)
    m.fetch([(p, 0x1c) for p in ptrs], 's_pcmat')
    found, nb, nn = hash_walk(m, 0x8a6ebc, 0x8a6ec4, 's_mh', ptrs)
    P('material hash: %s buckets, %d nodes walked' % (nb, nn))
    datas = {}
    for k, v in mats.items():
        f = found.get(v)
        P('  %-20s PCMaterial 0x%08x vt 0x%08x | id %s data 0x%08x' % (k, v or 0, m.u32(v) or 0 if v else 0,
                                                                     f[0] if f else '-', f[1] if f else 0))
        if v and m.u32(v + 4):               # PCMaterial +4 = the material data (0x503fdb: [mat+4] +0x44 flags)
            datas[v] = m.u32(v + 4)
    m.fetch([(d, 0x80) for d in datas.values()], 's_matdata')
    libs = set()
    for v, d in datas.items():
        for o in (0x28, 0x2c, 0x30, 0x34):
            if m.u32(d + o):
                libs.add(m.u32(d + o))
    lfound, lb, ln = hash_walk(m, 0x8a6ef0, 0x8a6ef8, 's_lh', libs)
    P('shader lib hash: %s buckets, %d nodes walked' % (lb, ln))
    pblocks = []
    for v, d in datas.items():
        pblocks += [(m.u32(d + 0x5c), 16 * (m.u32(d + 0x58) or 0)), (m.u32(d + 0x6c), 16 * (m.u32(d + 0x68) or 0))]
    m.fetch([(a, min(n, 0x400)) for a, n in pblocks if a and n], 's_params')
    P('')
    for v, d in datas.items():
        name = [k for k, x in mats.items() if x == v]
        P('material 0x%08x (id %s) used by %s; PCMaterial +0..+0x18: %s' % (
            v, found[v][0] if v in found else '-', ', '.join(name),
            ' '.join('%08x' % (m.u32(v + o) or 0) for o in range(0, 0x1c, 4))))
        P('  data +0x00..+0x7c: %s' % ' '.join('%08x' % (m.u32(d + o) or 0) for o in range(0, 0x80, 4)))
        for o, role in ((0x28, 'PS pass 0'), (0x2c, 'PS pass 1'), (0x30, 'PS pass 2 (colour)'), (0x34, 'VS')):
            lp = m.u32(d + o)
            lf = lfound.get(lp)
            P('  %-18s PCShaderLib 0x%08x -> shader lib id %s' % (role, lp or 0, lf[0] if lf else '-'))
        P('  blend +0x38 %s, +0x40 0x%x, +0x44 0x%x' % (m.u32(d + 0x38), m.u32(d + 0x40) or 0, m.u32(d + 0x44) or 0))
        for cnt_o, ptr_o, reg, what in ((0x58, 0x5c, 100, 'PS'), (0x68, 0x6c, 25, 'VS')):
            n, a = m.u32(d + cnt_o) or 0, m.u32(d + ptr_o) or 0
            vals = []
            for i in range(min(n, 16)):
                b = m.get(a + 16 * i, 16)
                vals.append('c%d (%s)' % (reg + i, ' '.join('%.4g' % x for x in struct.unpack('<4f', b)) if b else '-'))
            P('  %s MaterialParams %d at 0x%08x: %s' % (what, n, a, '; '.join(vals)))
    P('TruLink calls %d, %.1f s' % (m.n, time.time() - t0))
    with open(out, 'w', encoding='utf-8-sig', newline='\r\n') as h:
        h.write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
