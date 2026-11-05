"""Self test of `dlc2_player_fix.py gb` / `verify` (S104, 2026-11-05): the fix rebuilt from BEFORE must give AFTER
byte for byte, `verify` must pass the real pair and refuse every tampered AFTER (one unexplained word / byte /
relocation each). Tampered files are written to OUT_DIR (below work/rebuild); nothing else is written.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/s104_selftest.py BEFORE AFTER TU_GENERALBANK_BE OUT_DIR
  e.g. BEFORE = .../steps/22_input.drm, AFTER = .../mods/generalbank.drm, TU = .../steps/10_tu_be.drm
Exit 0 = every case as expected.
"""
import sys, os, struct, hashlib, io, contextlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import dlc2_player_fix as F


def load(p):
    return DW.read(open(p, 'rb').read(), 'le')


def save(D, p):
    open(p, 'wb').write(DW.cdrm_encode(D.write('le'), 'le'))


def s104(D):
    return next(x for x in D.sections if x.type == 8 and x.id == F.MISSION)


def set_word(s, off, val):
    d = bytearray(s.data); struct.pack_into('<I', d, off, val); s.data = bytes(d)


def run_verify(before, after, tu):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            F.verify([before, after, '--tu', tu]); code = 0
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 2
    lines = [x for x in buf.getvalue().splitlines() if x.strip()]
    probs = [x.strip() for x in lines if 'PROBLEM' in x]
    return code, (probs[0] if probs else lines[-1] if lines else '')


def main(argv):
    if len(argv) != 4:
        sys.exit(__doc__)
    before, after, tu, out = argv
    if not os.path.realpath(out).startswith(os.path.realpath('work/rebuild') + os.sep):
        sys.exit('OUT_DIR must be below work/rebuild')
    os.makedirs(out, exist_ok=True)
    bad = 0
    # 1. gb rebuilt in memory from BEFORE = AFTER
    D = load(before)
    with contextlib.redirect_stdout(io.StringIO()):
        F.fix_mission(D)
    regen = os.path.join(out, 'gb_regen.drm'); save(D, regen)
    same = open(regen, 'rb').read() == open(after, 'rb').read()
    print('case gb rebuilt from BEFORE: md5 %s, AFTER md5 %s - %s' % (
        hashlib.md5(open(regen, 'rb').read()).hexdigest(), hashlib.md5(open(after, 'rb').read()).hexdigest(),
        'byte-identical' if same else 'DIFFERENT'))
    bad += not same
    A0 = load(after); sa0 = s104(A0)
    ra0 = R.parse(sa0.reloc, 'le'); it0 = dict(ra0.internal)
    block, levels, _ = F.decode_fix(sa0.data, it0)
    jump_back = block + 4 * 19
    dtp47 = next(i for i, x in enumerate(A0.sections) if x.type != 8 and x.id == 47)

    def t_member(D): set_word(s104(D), block, F.op(0x0e, F.UNIT_MEMBER + 1))
    def t_dead(D): set_word(s104(D), F.SITE + 8, 0x05000001)
    def t_other(D):
        s = D.sections[dtp47]; d = bytearray(s.data); d[0] ^= 1; s.data = bytes(d)
    def t_reloc(D):
        s = s104(D); r = R.parse(s.reloc, 'le')
        p2 = block + 4 * 16                       # pointer word of test 4 (dlc_level2_start)
        p4 = block + 8
        t4 = dict(r.internal)[p4]
        r.internal = [(a, t4 if a == p2 else t) for a, t in r.internal]; s.reloc = R.write(r, 'le')
    def t_back(D): set_word(s104(D), jump_back, F.op(0x63, F.s24(struct.unpack_from('<I', sa0.data, jump_back)[0]) + 1))
    def t_append(D):
        s = s104(D); s.data = s.data + struct.pack('<I', F.op(0x00, 252))
    def t_or(D): set_word(s104(D), block + 4 * 8, F.op(0x51))
    cases = [
        ('real pair', before, None, 0),
        ('block: member 652 -> 653', before, t_member, 1),
        ('dead PC test word +0x23c4 changed', before, t_dead, 1),
        ('other section (DTP 47) one byte', before, t_other, 1),
        ('test 4 string pointer -> dlc_level4_start', before, t_reloc, 1),
        ('jump back +4 bytes off', before, t_back, 1),
        ('extra word after the block', before, t_append, 1),
        ('op52 -> op51 in test 2', before, t_or, 1),
        ('fix missing (AFTER = BEFORE)', before, 'before', 1),
        ('BEFORE already fixed (AFTER, AFTER)', after, None, 1),
    ]
    for k, (name, b, tamper, want) in enumerate(cases):
        if tamper is None:
            a = after
        elif tamper == 'before':
            a = before
        else:
            D = load(after); tamper(D)
            a = os.path.join(out, 'tamper_%02d.drm' % k); save(D, a)
        code, why = run_verify(b, a, tu)
        ok = (code == 0) == (want == 0)
        bad += not ok
        print('case %-45s expect %-7s got exit %d %s  %s' % (name, 'ok' if want == 0 else 'refuse', code,
                                                             'as expected' if ok else 'WRONG', why[:160]))
    print('self test: %d cases + gb rebuild, %d wrong' % (len(cases), bad))
    if bad:
        sys.exit(1)


if __name__ == '__main__':
    main(sys.argv[1:])
