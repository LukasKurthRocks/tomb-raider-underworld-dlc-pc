"""Sound 1411 / TruMenu 0.22.52: READ-ONLY live walk of the WHOLE FMOD Ex DSP graph (both directions) plus the voice
pool's reverb sends (TruLink read only, the whitelist of work/fmod_1411/fmod_live.py: read / read32 / readf).

Usage (from trudlcport):
  ../bin/pyt -t 900 work/menu52_1411/dspwalk_live.py OUT.txt

Layout (live 14.11. 21:02 dumps, work/ton_1411/live_dspgraph_1.txt.raw.txt; static 0x7b93ec / 0x801ead):
  DSPI +0x10 system, +0x24 INPUT list sentinel (node = DSPConnectionI +0x0; next +0, prev +4, data +8),
       +0x30 OUTPUT list sentinel (node = DSPConnectionI +0xc), +0x3c input count, +0x40 output count,
       +0x54 description (name 32 B; +0x54+0x3c = +0x90 parameter count; +0x54+0x6c = +0xc0 FMOD DSP type),
       +0xf4 flags (bit 1 = active, DSP::setActive 0x7b93ec)
  DSPConnectionI +0xe0 source (input unit), +0xe4 target (output unit), +0xec mix
  ChannelSoftware (real) +0x98 channel DSP head, +0x2f8 dry connection (head -> channel group head)
  Seeds: master group head, the game reverb [[0xccde98]], every used channel's head, every game group's head
  (table [0x8a80d8], entry +0x64 -> +0x6c ChannelGroupI -> +0x10). BFS over inputs and outputs, at most 600 units.
"""
import os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'fmod_1411'))
import fmod_live as FL   # noqa: E402

FL.TMP = os.path.join(HERE, 'live_tmp')
DSPLEN = 0x100
TYPES = {0: 'unknown/mixer', 1: 'mixer', 2: 'oscillator', 3: 'lowpass', 4: 'itlowpass', 5: 'highpass', 6: 'echo',
         7: 'flange', 8: 'distortion', 9: 'normalize', 10: 'parameq', 11: 'pitchshift', 12: 'chorus', 13: 'reverb',
         14: 'vstplugin', 15: 'winampplugin', 16: 'itecho', 17: 'compressor', 18: 'sfxreverb', 19: 'lowpass_simple',
         20: 'delay', 21: 'tremolo'}


def name_of(m, d):
    b = m.get(d + 0x54, 32)
    if not b:
        return '?'
    s = b.split(b'\0')[0].decode('latin-1', 'replace')
    return s if s else '-'


def walk_list(m, sent, back, tag):
    """the connections of one list: sentinel address, node offset inside the connection"""
    out, p, k = [], m.u32(sent), 0
    while p and p != sent and k < 600:
        m.fetch([(p - back, 0x100)], tag)
        out.append(p - back)
        p = m.u32(p)
        k += 1
    return out


def main(out):
    t0 = time.time()
    m = FL.Mem()
    L = []
    P = L.append
    m.fetch([(0xcc9f80, 4), (0xccde98, 4), (0x8a8108, 0x10), (0xcd3bc0, 4), (0x8a80d8, 8)], 'w_roots')
    sysp, holder = m.u32(0xcc9f80), m.u32(0xccde98)
    m.fetch([(sysp + 0x140, 0x10), (sysp + 0x9560, 0x10), (holder, 4)], 'w_sys')
    nch, arr, master = m.u32(sysp + 0x148), m.u32(sysp + 0x14c), m.u32(sysp + 0x9568)
    rev = m.u32(holder) if holder else 0
    m.fetch([(master, 0x60)], 'w_master')
    mhead = m.u32(master + 0x10)
    m.fetch([(arr, nch * 0x1b8)], 'w_chanarr')
    used = [i for i in range(nch) if m.u32(arr + i * 0x1b8 + 0x30)]
    reals = {i: m.u32(arr + i * 0x1b8 + 0x30) for i in used}
    m.fetch([(r, 0x300) for r in reals.values()], 'w_reals')
    heads = {m.u32(r + 0x98): i for i, r in reals.items() if m.u32(r + 0x98)}
    drys = {i: m.u32(r + 0x2f8) for i, r in reals.items()}
    # game groups
    gt, gn = m.u32(0x8a80d8), m.u32(0x8a80dc)
    ghead, gcg = {}, {}
    if gt and gn and gn < 256:
        m.fetch([(gt, gn * 0x84)], 'w_gtab')
        objs = [m.u32(gt + k * 0x84 + 0x64) for k in range(gn)]
        m.fetch([(o, 0x80) for o in objs if o], 'w_gobj')
        cgs = [(k, m.u32(o + 0x6c)) for k, o in enumerate(objs) if o and m.u32(o + 0x6c)]
        m.fetch([(c, 0x60) for _, c in cgs], 'w_gcg')
        for k, c in cgs:
            gcg[c] = k
            h = m.u32(c + 0x10)
            if h:
                ghead[h] = k
    # BFS both directions
    seeds = set([mhead, rev] + list(heads) + list(ghead))
    seeds.discard(0)
    seeds.discard(None)
    seen, conns, frontier, rounds = set(), {}, sorted(seeds), 0
    while frontier and len(seen) < 600 and rounds < 40:
        m.fetch([(d, DSPLEN) for d in frontier], 'w_dsp%d' % rounds)
        nxt = set()
        # all lists of this round in lockstep: one TruLink call per list position
        cur = []
        for d in frontier:
            seen.add(d)
            for sent, back in ((d + 0x24, 0x0), (d + 0x30, 0xc)):
                p = m.u32(sent)
                if p and p != sent:
                    cur.append((sent, back, p))
        found, step = [], 0
        while cur and step < 600:
            m.fetch([(p - back, 0x100) for _, back, p in cur], 'w_l%d_%d' % (rounds, step))
            nc = []
            for sent, back, p in cur:
                found.append(p - back)
                q = m.u32(p)
                if q and q != sent:
                    nc.append((sent, back, q))
            cur = nc
            step += 1
        if True:
            for c in found:
                if c in conns:
                    continue
                src, dst, mix = m.u32(c + 0xe0), m.u32(c + 0xe4), m.f32(c + 0xec)
                conns[c] = (src, dst, mix)
                for x in (src, dst):
                    if x and x not in seen:
                        nxt.add(x)
        frontier = sorted(nxt - seen)
        rounds += 1

    def role(d):
        if d == mhead:
            return 'head of FMOD master group'
        if d == rev:
            return 'GAME REVERB [[0xccde98]]'
        if d in heads:
            return 'head of ch %d' % heads[d]
        if d in ghead:
            return 'head of g%d' % ghead[d]
        return ''

    P('FMOD DSP graph (whole, both directions) %s: system 0x%08x, master 0x%08x head 0x%08x, reverb 0x%08x' % (
        time.strftime('%Y-%m-%d %H:%M:%S'), sysp or 0, master or 0, mhead or 0, rev or 0))
    P('channels in use %d; game groups with a channel group %d; DSP units %d; connections %d' % (
        len(used), len(ghead), len(seen), len(conns)))
    P('')
    P('== DSP units: address, type, flags (bit 1 active), inputs/outputs, name, role')
    bytype = {}
    for d in sorted(seen):
        ty, fl = m.u32(d + 0xc0), m.u32(d + 0xf4)
        nin, nout = m.u32(d + 0x3c), m.u32(d + 0x40)
        nm = name_of(m, d)
        key = '%s / %s' % (TYPES.get(ty, ty), nm.split(':')[0] if nm.startswith('ChannelGroup') else nm)
        bytype[key] = bytype.get(key, 0) + 1
        P('dsp 0x%08x type %-3s %-14s flags 0x%x in %s out %s  %-34s %s' % (
            d, ty, TYPES.get(ty, '?'), fl or 0, nin, nout, nm[:34], role(d)))
    P('')
    P('== units by type / name')
    for k in sorted(bytype):
        P('  %4d  %s' % (bytype[k], k))
    P('')
    P('== connections that are NOT channel head -> its group head (sends, effects, system links)')
    sends = 0
    for c, (src, dst, mix) in sorted(conns.items()):
        if src in heads and dst in ghead:
            continue
        if src in ghead and dst in ghead:
            continue
        if src in heads and dst == rev:
            sends += 1
            continue
        P('conn 0x%08x 0x%08x [%s / %s] -> 0x%08x [%s / %s] mix %s' % (
            c, src or 0, name_of(m, src) if src else '-', role(src) if src else '', dst or 0,
            name_of(m, dst) if dst else '-', role(dst) if dst else '', '%.4f' % mix if mix is not None else '-'))
    P('channel head -> game reverb sends: %d' % sends)
    P('')
    # pool voices
    end = m.u32(0xcd3bc0)
    node, hops, voices = m.u32(0x8a8108 + 8), 0, []
    while node and node != end and hops < 600:
        m.fetch([(node, 8)], 'w_pool%d' % hops)
        v = m.u32(node + 4)
        if v:
            voices.append(v)
        node = m.u32(node)
        hops += 1
    m.fetch([(v, 0x40) for v in voices], 'w_voices')
    want = []
    for v in voices:
        if m.u32(v + 8):
            want.append((m.u32(v + 8), 0x100))
        if m.u32(v + 0x1c):
            want.append((m.u32(v + 0x1c), 0x20))
    m.fetch(want, 'w_vdetail')
    pool_slots = set()
    P('== pool voices (%d): handle slot | FMOD flags (bit 3 eff. mute) | send conn mix | params +0 vol, +0xc send level' % len(voices))
    nosend = zero = withsend = 0
    for v in voices:
        h, sc, par, hold = m.u32(v + 4), m.u32(v + 8), m.u32(v + 0x1c), m.u32(v + 0xc)
        slot = (h >> 16) & 0xfff if h else -1
        pool_slots.add(slot)
        ci = arr + slot * 0x1b8 if 0 <= slot < nch else 0
        fl = m.u32(ci + 0x74) if ci else None
        mix = m.f32(sc + 0xec) if sc else None
        pv = m.f32(par) if par else None
        ps = m.f32(par + 0xc) if par else None
        if not sc:
            nosend += 1
        elif ps == 0.0:
            zero += 1
        else:
            withsend += 1
        P('voice 0x%08x h 0x%08x ch %4d fl %s | holder 0x%08x send 0x%08x mix %s | params 0x%08x vol %s send %s | grp cg %s' % (
            v, h or 0, slot, '0x%x' % fl if fl is not None else '-', hold or 0, sc or 0,
            '%.4f' % mix if mix is not None else '-', par or 0, '%.3f' % pv if pv is not None else '-',
            '%.3f' % ps if ps is not None else '-',
            ('g%d' % gcg[m.u32(ci + 0x8c)]) if ci and m.u32(ci + 0x8c) in gcg else '-'))
    P('pool voices: %d with a send > 0 level, %d with send level 0 (params +0xc), %d without a send connection' % (
        withsend, zero, nosend))
    P('')
    P('== used channels outside the pool (no game send by construction)')
    for i in used:
        if i in pool_slots:
            continue
        ci = arr + i * 0x1b8
        r = reals[i]
        hd = m.u32(r + 0x98)
        outs = [(c, s, d, x) for c, (s, d, x) in conns.items() if s == hd]
        ins = [(c, s, d, x) for c, (s, d, x) in conns.items() if d == hd]
        P('ch %4d h 0x%08x fl 0x%x vol %s mode 0x%x grp %s | head ins %s | outs %s' % (
            i, m.u32(ci + 0x70) or 0, m.u32(ci + 0x74) or 0, '%.3f' % (m.f32(ci + 0xb8) or 0), m.u32(r + 0x64) or 0,
            ('g%d' % gcg[m.u32(ci + 0x8c)]) if m.u32(ci + 0x8c) in gcg else '0x%08x' % (m.u32(ci + 0x8c) or 0),
            ['%s %.3f' % (name_of(m, s), x if x is not None else -1) for _, s, _, x in ins],
            ['%s %.3f' % (role(d) or name_of(m, d), x if x is not None else -1) for _, _, d, x in outs]))
    P('TruLink calls %d, %.1f s' % (m.n, time.time() - t0))
    with open(out, 'w', encoding='utf-8-sig', newline='\r\n') as h:
        h.write('\n'.join(L) + '\n')
    with open(out + '.raw.txt', 'w', encoding='ascii', newline='\r\n') as h:
        for d in sorted(seen):
            b = m.get(d, DSPLEN)
            h.write('Dsp 0x%08x %s\n' % (d, b.hex() if b else '-'))
        for c in sorted(conns):
            b = m.get(c, 0x100)
            h.write('Conn 0x%08x %s\n' % (c, b.hex() if b else '-'))
        for v in voices:
            b = m.get(v, 0x40)
            h.write('Voice 0x%08x %s\n' % (v, b.hex() if b else '-'))
    print('\n'.join(L[:12]))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
