"""Field type proof from a genuine base-game pair: follow the pointer path of a DLC DTP field (root offset -> pointer
field -> ... -> field) in a base-game object of the same kind, Xbox original vs. genuine PC file, and show how the
real PC port stores that word (read-only; thrall floats 2026-11-05: the DLC 2 thrall objects are built like the base
game's viking_thrall / yeti_thrall; the genuine PC files say whether a field is a float (u32 byte-reversed) or two
u16).

Path: the chain dtp_field_path.py prints, written root first as pointer-field offsets, e.g. for yeti_thrall_dlc2_
DTP 24577 +0x619c: c8,1c,4,94:300 = DTP +0xc8 -> block, its +0x1c -> block, its +0x4 -> block, its +0x94 -> block,
field +0x300. The tool follows the same path in every type-7 DTP of the base files whose relocations allow it (each
step must be an internal pointer on both sides) and prints Xbox / PC word, conversion class and float values.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/dtp_twin_field.py dlcpath XBOX_DLC_NAME DLC_PC.drm DTP OFF[,OFF..]
        print the root-first path of each DLC field (pointer field offsets) - input for 'follow'
  ../bin/pyt -t 600 tools/dtp_twin_field.py follow BASE_NAME PATH[;PATH..] [--dtp ID]
        BASE_NAME: base-game DRM name, read from the Xbox layers (xbase / tu) and the PC archives (pcpatch / pcbig)
        PATH: hex pointer fields separated by ',' then ':' and the field offset (e.g. c8,1c,4,94:300)
Sources (tools/locals.py SRC): Xbox 'tu', 'xbase2', 'xbase'; PC 'pcpatch', 'pcbig' (read-only).
"""
import sys, os, struct, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import tuning_word_audit as TA
from drm import cdrm_decode, sections_with_data


def cls(xw, pw):
    if xw == pw and xw == xw[::-1]: return 'same'
    if xw[::-1] == pw: return 'u32'
    if xw[1::-1] + xw[:1:-1] == pw: return 'u16pair'
    if xw == pw: return 'raw'
    return 'other'


def fval(b, e):
    v = struct.unpack(e + 'f', b)[0]
    return '%.6g' % v if math.isfinite(v) else 'nan'


def load_named(name, order, endian):
    import locals as LC
    from archive import Archive
    from names import crc
    n = name if name.endswith('.drm') else name + '.drm'
    for src in order:
        path, e, pre = LC.SRC[src]
        if e != endian or not os.path.exists(path): continue
        A = Archive(path, e)
        r = [x for x in A.find(crc(pre + '\\' + n)) if x['spec'] == 0xffffffff]
        if r:
            return sections_with_data(cdrm_decode(A.read(r[0]), e), e)[1], src
    return None, None


def blocks(secs, sid):
    for s in secs:
        if s['type'] == 7 and s['id'] == sid: return s
    return None


def dlc_path(argv):
    xsecs, src = TA.load_x(argv[0])
    psecs = TA.load_p(argv[1])
    sid = int(argv[2])
    sp = blocks(psecs, sid)
    ip = dict(R.parse(bytes(sp['reloc']), 'le').internal)
    targets = sorted(set(ip.values()) | {0})
    refs = {}
    for o, t in ip.items(): refs.setdefault(t, []).append(o)

    def block_of(o):
        b = 0
        for t in targets:
            if t <= o: b = t
            else: break
        return b
    for off in [int(x, 16) for x in argv[3].split(',')]:
        b = block_of(off)
        chain = []
        cur, seen = b, set()
        while cur != 0 and cur in refs and cur not in seen:
            seen.add(cur)
            r = sorted(refs[cur])[0]
            rb = block_of(r)
            chain.insert(0, r - rb)
            cur = rb
        root_ok = cur == 0
        print('DTP %d +0x%x: path %s:%x%s' % (sid, off, ','.join('%x' % c for c in chain), off - b,
                                              '' if root_ok else '  (chain does not reach the DTP start)'))


def follow(argv):
    name = argv[0]
    paths = []
    for p in argv[1].split(';'):
        a, f = p.split(':')
        paths.append(([int(x, 16) for x in a.split(',') if x], int(f, 16), p))
    want = None
    if '--dtp' in argv: want = int(argv[argv.index('--dtp') + 1])
    xs, xsrc = load_named(name, ('tu', 'xbase2', 'xbase'), 'be')
    ps, psrc = load_named(name, ('pcpatch', 'pcbig'), 'le')
    if not xs or not ps: sys.exit('%s: Xbox %s, PC %s' % (name, xsrc, psrc))
    print('base %s: Xbox from %s (%d sections), PC from %s (%d sections)' % (name, xsrc, len(xs), psrc, len(ps)))
    pdtp = {s['id']: s for s in ps if s['type'] == 7}
    xdtp = [s for s in xs if s['type'] == 7]
    # Xbox -> PC DTP pairing: same id, else same size and the same internal pointer offsets
    for sx in xdtp:
        if want is not None and sx['id'] != want: continue
        rx = dict(R.parse(bytes(sx['reloc']), 'be').internal)
        cand = [pdtp[sx['id']]] if sx['id'] in pdtp else []
        if not cand:
            cand = [s for s in pdtp.values() if len(s['data']) == len(sx['data']) and
                    sorted(dict(R.parse(bytes(s['reloc']), 'le').internal).items()) == sorted(rx.items())]
        if len(cand) != 1: continue
        sp = cand[0]
        rp = dict(R.parse(bytes(sp['reloc']), 'le').internal)
        xd, pd = bytes(sx['data']), bytes(sp['data'])
        for chain, field, txt in paths:
            cur, ok = 0, True
            for c in chain:
                a = cur + c
                if a not in rx or a not in rp or rx[a] != rp[a]: ok = False; break
                cur = rx[a]
            if not ok: continue
            o = cur + field
            if o + 4 > len(xd) or o + 4 > len(pd): continue
            xw, pw = xd[o:o + 4], pd[o:o + 4]
            print('  Xbox DTP %d / PC DTP %d (0x%x bytes) path %s -> +0x%x: Xbox %s (f %s) PC %s (f %s) %s' % (
                sx['id'], sp['id'], len(xd), txt, o, xw.hex(), fval(xw, '>'), pw.hex(), fval(pw, '<'), cls(xw, pw)))


def main(argv):
    if len(argv) < 3: sys.exit(__doc__)
    if argv[0] == 'dlcpath': return dlc_path(argv[1:])
    if argv[0] == 'follow': return follow(argv[1:])
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
