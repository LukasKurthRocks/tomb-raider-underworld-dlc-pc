"""TruMenu 0.22.52 analysis: offline report of a dspwalk_live.py raw dump (no TruLink; reads OUT.txt.raw.txt only).

Usage (from trudlcport):
  ../bin/pyt -t 120 work/menu52_1411/dspwalk_report.py RAW.txt OUT.txt

Every value is taken from the block of its own unit / connection (the live walk's in-memory lookup could pick a
neighbour's overlapping block). Layout: see dspwalk_live.py.
"""
import struct, sys

TYPES = {0: 'mixer/head', 2: 'oscillator', 3: 'lowpass', 5: 'highpass', 6: 'echo', 7: 'flange', 8: 'distortion',
         9: 'normalize', 10: 'parameq', 11: 'pitchshift', 12: 'chorus', 13: 'reverb', 17: 'compressor', 18: 'sfxreverb',
         19: 'lowpass_simple', 1000: 'codec'}


def u32(b, o):
    return struct.unpack_from('<I', b, o)[0] if b and o + 4 <= len(b) else None


def f32(b, o):
    return struct.unpack_from('<f', b, o)[0] if b and o + 4 <= len(b) else None


def main(raw, out):
    dsp, conn, voice = {}, {}, {}
    for line in open(raw, encoding='ascii'):
        p = line.split()
        if len(p) != 3 or p[2] == '-':
            continue
        a, b = int(p[1], 16), bytes.fromhex(p[2])
        {'Dsp': dsp, 'Conn': conn, 'Voice': voice}.get(p[0], {})[a] = b
    L = []
    P = L.append

    def name(d):
        b = dsp.get(d)
        if not b:
            return '?'
        return b[0x54:0x74].split(b'\0')[0].decode('latin-1', 'replace') or '-'

    edges = []
    for c, b in conn.items():
        src, dst, mix = u32(b, 0xe0), u32(b, 0xe4), f32(b, 0xec)
        if src in dsp and dst in dsp:
            edges.append((c, src, dst, mix))
    ins, outs = {}, {}
    for c, s, d, x in edges:
        outs.setdefault(s, []).append((d, x, c))
        ins.setdefault(d, []).append((s, x, c))
    P('units %d, connections with both ends known %d (of %d dumps)' % (len(dsp), len(edges), len(conn)))
    P('')
    P('== every unit that is not a channel head / wave table / channel group head')
    for d in sorted(dsp):
        nm, ty = name(d), u32(dsp[d], 0xc0)
        if nm.startswith('FMOD Channel DSPHead') or nm.startswith('FMOD WaveTable') or nm.startswith('ChannelGroup'):
            continue
        P('0x%08x %-30s type %s (%s) flags 0x%x' % (d, nm, ty, TYPES.get(ty, '?'), u32(dsp[d], 0xf4) or 0))
        for s, x, c in ins.get(d, []):
            P('    <- 0x%08x %-30s mix %.4f  (conn 0x%08x)' % (s, name(s), x, c))
        for t, x, c in outs.get(d, []):
            P('    -> 0x%08x %-30s mix %.4f  (conn 0x%08x)' % (t, name(t), x, c))
    P('')
    P('== channel heads: outputs (dry to a group head / send to the reverb / other)')
    nh = ns = 0
    for d in sorted(dsp):
        if not name(d).startswith('FMOD Channel DSPHead'):
            continue
        nh += 1
        o = outs.get(d, [])
        kinds = ['%s %.4f' % (name(t)[:24], x) for t, x, _ in o]
        if any(name(t) == 'SFX Reverb' for t, _, _ in o):
            ns += 1
        P('0x%08x outs %d: %s | ins: %s' % (d, len(o), kinds, ['%s %.3f' % (name(s)[:20], x) for s, x, _ in ins.get(d, [])]))
    P('channel heads %d, with a send into SFX Reverb %d' % (nh, ns))
    P('')
    P('== group heads that feed something other than a group head (inserts, effects)')
    for d in sorted(dsp):
        if not name(d).startswith('ChannelGroup'):
            continue
        for t, x, c in outs.get(d, []):
            if not name(t).startswith('ChannelGroup'):
                P('0x%08x %s -> 0x%08x %s mix %.4f' % (d, name(d), t, name(t), x))
    with open(out, 'w', encoding='utf-8-sig', newline='\r\n') as h:
        h.write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
