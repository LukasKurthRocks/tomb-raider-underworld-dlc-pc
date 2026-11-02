"""Anim event lists (DTP: u32 0, then records {u16 h, s16 frame, u8 type, .., payload}, end u16 0xffff; tools/animfx.py
walk) against the byte-order rules proven on the base pair's object event lists (tools/obj_eventlist_fix.py
proof_table: key (kind, payload words, word index[, payload byte 0]) -> u16 / u32 / raw / u8u8u16 / u16u8u8);
check, and with --fix repair (read-only unless --fix; test 50h crash 2026-11-02 20:42:58, AV tru+0x14df84 eax
0x00652000: viking_thrall_dlc2_ DTP 24470, kind-0 record payload word 0 converted as u16 pair -> payload byte 0 = 1
instead of 0, so tru+0x1b99c0 took the 7-word "type 1" path (tru+0x1b9b3b) on a 2-word record and passed the next
record's header as a section id to tru+0x1953e0 -> tru+0x14df80).

Reader: tru+0x1b99c0(payload): `movsx eax, byte [esi]`: 0 -> sound / fx pointer at payload +4 (2-word records),
1 -> [esi+4] s16, [esi+6] / [esi+7] bytes, [esi+8] u32 id, floats +0xc..+0x18 (7-word records).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/animlist_check.py proof XREF.drm PREF.drm        rules applied to the base pair's own anim
        lists (sections paired by order) - every non-pointer word must come out equal
  ../bin/pyt -t 600 tools/animlist_check.py check XREF.drm PREF.drm XBOX.drm PC.drm [--fix OUT.drm]
  ../bin/pyt -t 2400 tools/animlist_check.py tree XREF.drm PREF.drm DIR [DIR ..] [--fix-dir OUT] [--skip NAME,..]
        PC .drm vs dlc_drms.pkl (sections by id); --fix-dir writes every file with wrong words repaired; --skip names
        files whose PC sections are base-derived copies (id coincidences, e.g. lara_doppelganger, dlc_costume_*)
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import obj_eventlist_fix as OE
import animfx as AF


def list_words(xs):
    """[(offset, key)] of an Xbox anim list section; None if it is not one"""
    w = AF.walk(xs.data, '>')
    if w is None: return None
    rel = R.parse(xs.reloc, 'be')
    skip = set(rel.pointer_offsets()) | set(rel.id_offsets())
    out = []
    for a, h, fr, sz in w[0]:
        for k in range(sz // 4):
            o = a + 4 * k
            if o in skip: continue
            out.append((o, OE.key(xs.data, 'be', a, h, k), a))
    out.append((w[1], 'T', None))
    return out


def expected(T, xs, o, kk, a=None):
    x4 = bytes(xs.data[o:o + 4])
    c = OE.rule(T, kk)
    # kind 1 sub 0x32: payload word 1 is one u32 section id (reader tru+0x1486b2, tools/eventlist_idword_fix.py)
    if kk != 'T' and kk[0] == 1 and kk[2] == 3 and a is not None and struct.unpack_from('>H', xs.data, a + 8)[0] == 0x32:
        c = 'u32'
    if c is None: return None, None
    if kk == 'T': return OE.conv(x4[:2] + b'\0\0', 'u16')[:2], c
    return OE.conv(x4, c), c


def check_sec(T, xs, ps, label, fix):
    lw = list_words(xs)
    if lw is None or len(xs.data) != len(ps.data): return None
    cnt = collections.Counter()
    d = bytearray(ps.data) if fix is not None else None
    for o, kk, a in lw:
        exp, c = expected(T, xs, o, kk, a)
        if exp is None: cnt['no rule'] += 1; continue
        got = bytes(ps.data[o:o + len(exp)])
        if got == exp: cnt['ok'] += 1; continue
        cnt['wrong'] += 1
        print('%s7:%-6d +0x%04x key %-16s rule %-8s Xbox %s PC %s expected %s' % (
            label, ps.id, o, kk, c, xs.data[o:o + 4].hex(), got.hex(), exp.hex()))
        if d is not None: d[o:o + len(exp)] = exp
    if d is not None and cnt['wrong']: fix[id(ps)] = bytes(d)
    return cnt


def write_fixed(path, D, fix, out):
    for k, s in enumerate(D.sections):
        if id(s) in fix:
            D.sections[k] = DW.Section(s.type, s.id, fix[id(s)], s.reloc, s.flags, s.ver, s.spec, s.pad)
    raw = D.write('le')
    if open(path, 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(raw)
    DR = DW.read(open(out, 'rb').read(), 'le')
    assert [(a.type, a.id, a.data, a.reloc) for a in DR.sections] == [(b.type, b.id, b.data, b.reloc) for b in D.sections]
    print('wrote %s (%d sections changed), readback ok' % (out, len(fix)))


def pairs_by_id(DX, DP):
    xs = {}
    for s in DX.sections:
        if s.type == 7: xs.setdefault(s.id, s)
    return [(xs[s.id], s) for s in DP.sections if s.type == 7 and s.id in xs]


def main(argv):
    if len(argv) < 3: print(__doc__); return 2
    T, st = OE.proof_table(argv[1], argv[2])
    tot = collections.Counter()
    if argv[0] == 'proof':
        DX = DW.read(open(argv[1], 'rb').read(), 'be'); DP = DW.read(open(argv[2], 'rb').read(), 'le')
        xv = [s for s in DX.sections if s.type == 7 and AF.walk(s.data, '>') is not None]
        pv = [s for s in DP.sections if s.type == 7 and AF.walk(s.data, '<') is not None]
        print('anim lists: Xbox %d, PC %d (paired by order)' % (len(xv), len(pv)))
        for x, p in zip(xv, pv):
            c = check_sec(T, x, p, '', None)
            if c: tot.update(c)
            else: tot['size differs'] += 1
    elif argv[0] == 'check':
        DX = DW.read(open(argv[3], 'rb').read(), 'be'); DP = DW.read(open(argv[4], 'rb').read(), 'le')
        fix = {} if '--fix' in argv else None
        for x, p in pairs_by_id(DX, DP):
            c = check_sec(T, x, p, '', fix)
            if c: tot.update(c)
        if fix is not None: write_fixed(argv[4], DP, fix, argv[argv.index('--fix') + 1])
    elif argv[0] == 'tree':
        import pickle
        fixdir = skip = None
        if '--fix-dir' in argv: k = argv.index('--fix-dir'); fixdir = argv[k + 1]; del argv[k:k + 2]
        skip = set()
        if '--skip' in argv: k = argv.index('--skip'); skip = set(argv[k + 1].lower().split(',')); del argv[k:k + 2]
        C = pickle.load(open(os.path.join(OE.W, 'dlc_drms.pkl'), 'rb'))
        base = lambda n: os.path.splitext(n.replace('\\', '/').split('/')[-1])[0].lower()
        byname = {}
        for k, v in C.items(): byname.setdefault(base(k[1]), []).append(v)
        for top in argv[3:]:
            for dp, dn, fn in os.walk(top):
                for f in sorted(fn):
                    if not f.lower().endswith('.drm') or base(f) not in byname: continue
                    DP = DW.read(open(os.path.join(dp, f), 'rb').read(), 'le')
                    h, secs = byname[base(f)][0]
                    DX = DW.Drm([DW.Section(s['type'], s['id'], s['data'], s['reloc'], s['flags'], s['ver'], s['spec'])
                                 for s in secs if s['type'] == 7])
                    if base(f) in skip: print('%s: skipped (--skip)' % f); continue
                    fc = collections.Counter()
                    fix = {} if fixdir else None
                    for x, p in pairs_by_id(DX, DP):
                        c = check_sec(T, x, p, f + ' ', fix)
                        if c: fc.update(c)
                    if fc: print('%s: %s' % (f, dict(fc)))
                    if fix: write_fixed(os.path.join(dp, f), DP, fix, os.path.join(fixdir, f))
                    tot.update(fc)
    print('total: %s' % dict(tot))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
