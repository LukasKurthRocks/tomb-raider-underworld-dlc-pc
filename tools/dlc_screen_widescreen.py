"""Port the Xbox title-update widescreen layout of the DLC mission screen to the PC generalbank.drm.

Symptom on PC: in DOWNLOADABLE CONTENT -> mission screen the level title is drawn on top of the description text.
Finding: the DLC mission screen script (Xbox Script id 134, PC Script id 104; it loads dlc_level*_preview) is the
retail version on PC. The Xbox title update (TitleUpdate.000) changed its function 1 (open: disableSound ...):
  if (uiscreen.f10() > 1.5)            # native, returns float (aspect ratio check)
      uitext.f26(...) on four text widgets, uirenderimage.f7/f4(...) on two image widgets
It also added two data members (new first member at 0x004 -> all later member offsets +0xc on Xbox TU) and a float
local in function 1. The PC script keeps its retail member layout, so the port maps member offsets back (-0xc).

How (no other data moves): the translated function-1 code and a 2-entry locals array are APPENDED to the PC section;
function 1's code / locals SArray pointers are retargeted to them, its size 8 -> 12 and stack 9 -> 10 (as on Xbox TU).
The old code stays in the section, unused.

Call targets (Xbox TU section index + offset -> PC section index + offset, checked by prototype name order):
  messagechannel 70+0x8c -> 74+0x8c, uiscreen 100+0x1bc/0x14c/0xa0c -> 103+0x1bc/0x14c/0xa7c,
  uitext 98+0x35c -> 102+0x35c, uirenderimage 92+0x138/0xe4 -> 96+0x138/0xe4, uimenu 93+0x368 -> 97+0x3a0

Usage (from the repository root):  ..\\bin\\venv\\Scripts\\python.exe -I tools/dlc_screen_widescreen.py [src]
  src defaults to ../data/pc/mods/generalbank.drm (the installed menu_dlc build).
  -> work/dlc_screen/generalbank.drm (+ md5.txt, patch_log.txt, f1_pc_new.txt)
"""
import sys, os, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import menu_dlc_probe as P
import drm_reloc as R
import drm_write as DW
import script_conv as SC

SRC = sys.argv[1] if len(sys.argv) > 1 else '../data/pc/mods/generalbank.drm'
OUT = 'work/dlc_screen/'
XT_ID, PC_ID, FIDX = 134, 104, 1
MEMBER_SHIFT = 0xc                       # Xbox TU inserted one 12-byte member at 0x004
LOCAL_SWAP = {0: 4, 4: 0}                # TU: new float local at 0, old at 4 -> PC: old stays at 0, new at 4
EXT_MAP = {(70, 0x8c): (74, 0x8c), (100, 0x1bc): (103, 0x1bc), (100, 0x14c): (103, 0x14c),
           (100, 0xa0c): (103, 0xa7c), (98, 0x35c): (102, 0x35c), (92, 0x138): (96, 0x138),
           (92, 0xe4): (96, 0xe4), (93, 0x368): (97, 0x3a0)}
PC_SCRIPT_NAMES = {74: b'messagechannel', 103: b'uiscreen', 102: b'uitext', 96: b'uirenderimage', 97: b'uimenu'}
EXTRA = dict(SC.Walk.EXTRA)
EXTRA[0x02] = 1                          # push 32-bit literal: the next word is data (float / int)
NEW_LOCAL_NAME = 0xf7                    # TU: new 0xf6 / old 0xf7; PC old local is 0xf8 -> symbol order kept


def func_code(W, d, fa):
    """[(offset, word, extra_index or None)] for the code of the Function struct at fa."""
    ct = W.tgt(fa + 0x18)
    n = W.u32(ct - 4)
    out, k = [], 0
    while k < n:
        o = ct + 4 * k
        w = W.u32(o)
        op = w >> 24
        out.append((o, w, None))
        for j in range(EXTRA.get(op, 0)):
            out.append((o + 4 * (j + 1), W.u32(o + 4 * (j + 1)), (op, j)))
        k += 1 + EXTRA.get(op, 0)
    assert len(out) == n, (len(out), n)
    return ct, out


def main():
    log = []
    # ---- Xbox title update section (big endian)
    C = P.cache()
    xs = [s for s in P.secs(C, 'xt') if s['type'] == 8 and s['id'] == XT_ID and s['data']]
    assert len(xs) == 1
    xd, xrel = xs[0]['data'], R.parse(xs[0]['reloc'], 'be')
    XW = SC.walk(xd, xrel, 'be')
    xft = [a for a in XW.arrays if a[0] == 'funcs'][0][1]
    xfa = xft + 28 * FIDX
    xext = {so: (si, do) for si, so, do in xrel.external}
    _, xcode = func_code(XW, xd, xfa)

    # ---- PC generalbank (installed menu_dlc build)
    raw_in = open(SRC, 'rb').read()
    drm = DW.read(raw_in, 'le')
    idx = [i for i, s in enumerate(drm.sections) if s.type == 8 and s.id == PC_ID]
    assert len(idx) == 1
    si_pc = idx[0]
    sec = drm.sections[si_pc]
    pd, prel = bytearray(sec.data), R.parse(sec.reloc, 'le')
    size_before = len(pd)
    PW = SC.walk(bytes(pd), prel, 'le')
    assert not PW.bad
    for k, nm in PC_SCRIPT_NAMES.items():
        s = drm.sections[k]
        r = R.parse(s.reloc, 'le')
        t = dict(r.internal).get(0x10)
        assert s.type == 8 and t is not None and s.data[t:s.data.find(b'\0', t)] == nm, (k, nm)
    pft = [a for a in PW.arrays if a[0] == 'funcs'][0][1]
    pfa = pft + 28 * FIDX
    pint = dict(prel.internal)
    pext = {so: (si, do) for si, so, do in prel.external}
    _, pcode = func_code(PW, bytes(pd), pfa)
    log.append('source %s md5 %s, section #%d (8,%d) size %d' % (SRC, hashlib.md5(raw_in).hexdigest(), si_pc, PC_ID, len(pd)))

    # PC pointer targets reused by the translated code: the string of op 05 and the data blocks of op 68
    pc_ptr = {}
    for o, w, ex in pcode:
        if ex and o in pint:
            pc_ptr.setdefault(ex[0], []).append(pint[o])
    ext_raw = {w for o, w, ex in pcode if ex and o in pext}
    assert len(ext_raw) == 1, ext_raw
    ext_raw = ext_raw.pop()

    # ---- translate the TU code
    words, new_int, new_ext = [], [], []        # new_*: (index into words, ...)
    used68 = 0
    for o, w, ex in xcode:
        op, arg = w >> 24, w & 0xffffff
        if ex is None:
            if op == 0x0f:
                assert arg >= 0x10, 'TU-only member 0x%x used' % arg
                w = op << 24 | (arg - MEMBER_SHIFT)
            elif op == 0x09:
                w = op << 24 | LOCAL_SWAP[arg]
            words.append(w)
            continue
        xop, j = ex
        if o in xext:
            tgt = EXT_MAP[xext[o]]
            new_ext.append((len(words), tgt))
            words.append(ext_raw)
        elif XW.tgt(o) is not None:
            if xop == 0x05:
                new_int.append((len(words), pc_ptr[0x05][0]))
            elif xop == 0x68:
                new_int.append((len(words), pc_ptr[0x68][used68])); used68 += 1
            else:
                raise AssertionError('unexpected pointer operand op %02x at +0x%x' % (xop, o))
            words.append(0)
        else:
            assert xop == 0x02, 'unexpected raw operand op %02x' % xop
            words.append(w)                       # literal: same u32 value, written little endian below
    assert used68 == len(pc_ptr[0x68]) == 2
    log.append('f1: Xbox TU %d words -> PC %d words (PC retail %d), %d calls, %d pointers'
               % (len(xcode), len(words), len(pcode), len(new_ext), len(new_int)))

    # ---- locals: PC old local (+ its id reference) and the new float local
    plt = PW.tgt(pfa + 12)
    assert PW.u32(plt - 4) == 1
    old_local = bytes(pd[plt:plt + 20])
    idrefs_old = [(t, off) for t, off in prel.idref if plt <= off < plt + 20]
    new_local = struct.pack('<IIIHHI', 0x33, 0, 0, 4, NEW_LOCAL_NAME, 0)

    # ---- append: [count][2 locals] [count][code]
    while len(pd) % 4: pd.append(0)
    loc_at = len(pd) + 4
    pd += struct.pack('<I', 2) + old_local + new_local
    code_at = len(pd) + 4
    pd += struct.pack('<I', len(words)) + b''.join(struct.pack('<I', w) for w in words)

    internal = [(o, t) for o, t in prel.internal if o not in (pfa + 12, pfa + 0x18)]
    internal += [(pfa + 12, loc_at), (pfa + 0x18, code_at)]
    internal += [(code_at + 4 * i, t) for i, t in new_int]
    external = list(prel.external) + [(si, code_at + 4 * i, do) for i, (si, do) in new_ext]
    idref = list(prel.idref) + [(t, off - plt + loc_at) for t, off in idrefs_old]
    struct.pack_into('<H', pd, pfa + 6, 12)          # Function.size  8 -> 12 (as Xbox TU)
    struct.pack_into('<H', pd, pfa + 10, 10)         # Function.stack 9 -> 10 (as Xbox TU)
    nrel = R.Reloc(sorted(internal), sorted(external, key=lambda x: x[1]), list(prel.idref_a), list(prel.unk3), idref)
    bad = R.check(nrel, len(pd))
    assert not bad, bad[:5]
    sec.data, sec.reloc = bytes(pd), R.write(nrel, 'le')

    # ---- verify: re-walk the new section, round-trip the DRM
    W2 = SC.walk(sec.data, R.parse(sec.reloc, 'le'), 'le')
    assert not W2.bad, W2.bad[:5]
    raw = drm.write('le')
    again = DW.read(raw, 'le')
    assert [(s.type, s.id, len(s.data)) for s in again.sections] == [(s.type, s.id, len(s.data)) for s in drm.sections]
    enc = DW.cdrm_encode(raw, 'le')
    assert DW.cdrm_decode(enc, 'le') == raw
    os.makedirs(OUT, exist_ok=True)
    open(OUT + 'generalbank.drm', 'wb').write(enc)
    md5 = hashlib.md5(enc).hexdigest()
    open(OUT + 'md5.txt', 'w').write('%s  generalbank.drm\n' % md5)
    _, ncode = func_code(W2, sec.data, pfa)
    open(OUT + 'f1_pc_new.txt', 'w').write('\n'.join('+0x%05x %08x %s' % (o, w, ex or '') for o, w, ex in ncode) + '\n')
    log.append('section #%d size %d -> %d, reloc %d B' % (si_pc, size_before, len(sec.data), len(sec.reloc)))
    log.append('output %sgeneralbank.drm CDRM %d B md5 %s' % (OUT, len(enc), md5))
    open(OUT + 'patch_log.txt', 'w').write('\n'.join(log) + '\n')
    print('\n'.join(log))


if __name__ == '__main__':
    main()
