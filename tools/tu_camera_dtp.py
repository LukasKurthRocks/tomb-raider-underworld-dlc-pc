"""The title update's DLC 2 camera settings DTPs for the PC generalbank (developer tool, reads Xbox data; Q2 addition
2026-11-11, docs Befund-Generalbank-PC-Basis-1111.md section 7, ENGINE "Doppelganger camera settings (TU)").

The TU generalbank has three DTPs the PC (and the retail Xbox) file lacks:
  21237  Lara camera settings in doppelganger mode (TU GlobalInfo +0x14c; twin = retail Xbox 21 = PC DTP 20)
  21238  combat camera settings in doppelganger mode (TU GlobalInfo +0x150; twin = retail Xbox 22 = PC DTP 21)
  22194  86 curve records referenced (id references) by both - without it their references point nowhere
None of them is in a DLC pack (pack10 / pack11 scanned); no PC / DLC / installed DRM uses these ids.

Word forms (Xbox big endian -> PC little endian), each proven on the retail <-> PC base pairs Xbox 21 / PC 20 and
Xbox 22 / PC 21 (same size, same pointer and id-reference lists; Xbox id = PC id + 1 in this range):
  u32 swap      every word unless one of the rules below says otherwise (floats, ints, pointer placeholders)
  idref         section ids of DTP references: Xbox -> PC id (31 -> 30 = the base pairs' own references);
                22194 stays 22194 (added under its TU id, as 8:21239 / 8:20082)
  u8            the 64-byte curve lookup tables (bytes kept; base pairs: Xbox 21 +0xf8, Xbox 22 +0x34 ... -> PC
                byte-equal) and the single-byte words b000000 (base pairs: 01000000 -> PC bytes 01 00 00 00)
  u16           the u16 pair at Xbox 21 +0xdc (00140000 -> PC 14 00 00 00)
Per DTP:
  21237 / 21238  word LCS on the Xbox words against the twin; an aligned TU word takes the twin's PC word (the same
                Xbox value gives the same PC bytes); unaligned words: idref -> map, b000000 -> u8, else u32
  22194         no twin: 86 records of 0x6c from +0x10 (count 0x56 at +0x0, list pointer +0x4); record r+0x00 =
                u16 pair (values 3 / 0x11 / 0x6c; our converter chose u16 in 86 / 86 records), r+0x20..+0x5f = the
                64-byte LUT (monotone non-decreasing bytes in 86 / 86 records), r+0x64 pointer, r+0x68 = u8 (0..3),
                the rest u32 (floats / zero)
Relocations: the TU lists, written little endian (internal pointer targets unchanged, id references unchanged).
Section header: type 7, the TU's ver word kept (as the shipped TU sections 8:21239 / 8:20082 keep theirs).
Checks: every 64-byte LUT of the result is monotone as PC bytes; the result is compared with our generic converter's
TU generalbank (work/rebuild/base_convert/tu_generalbank.drm, if present): the differing words are listed by form
(the converter mixed u8 / u32 inside the LUTs - 14 of 17 LUT words of 21237's head swapped).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/tu_camera_dtp.py convert OUT.drm [--report R.json]
        -> OUT.drm: a DRM with just the three PC sections (input of generalbank_pc_build.py learn --add-sections)
"""
import sys, os, struct, json, difflib, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC
from archive import Archive
from names import crc
import drm_write as DW, drm_reloc as R

TWINS = {21237: 21, 21238: 22}           # TU id -> retail Xbox twin id (PC id = Xbox id - 1)
XBOX_TO_PC = {31: 30, 21: 20, 22: 21}    # DTP ids referenced / twins (Xbox id = PC id + 1, base pairs)
KEEP_IDS = {22194}
REC0, RECSZ, NREC = 0x10, 0x6c, 86


def load(src, name='generalbank.drm'):
    path, e, pre = LC.SRC[src]
    for p in [path] + ([LC.SRC['xbase2'][0]] if src == 'xbase' else []):
        A = Archive(p, e)
        r = [x for x in A.find(crc(pre + '\\' + name)) if x['spec'] == 0xffffffff]
        if r: return {(s.type, s.id): s for s in DW.read(A.read(r[-1]), e).sections}
    raise SystemExit('%s not in %s' % (name, src))


def pc_sections():
    A = Archive(LC.SRC['pcpatch'][0], 'le')
    return {(s.type, s.id): s for s in DW.read(A.read(A.find(crc('pc-w\\generalbank.drm'))[0]), 'le').sections}


def put(out, o, a, f):
    """write Xbox value a at offset o in PC form f"""
    b = struct.pack('>I', a)
    if f == 'u8': out[o:o + 4] = b
    elif f == 'u16': out[o:o + 4] = struct.pack('<HH', *struct.unpack('>HH', b))
    else: out[o:o + 4] = struct.pack('<I', a)


def single_byte(a):
    """b000000 with 0 < b < 0x20: as a float below 1e-29, as an int > 16 million - a byte field (base pairs: 01000000)"""
    return a & 0x00ffffff == 0 and 0 < (a >> 24) < 0x20


def convert_one(tid, t, X, P, rep):
    rel = R.parse(t.reloc, 'be')
    ptr = {o for o, _ in rel.internal}
    ids = {o: ty for ty, o in rel.idref}
    if rel.external or rel.idref_a or rel.unk3: raise SystemExit('%d: unexpected relocation kinds' % tid)
    n = len(t.data) // 4
    if len(t.data) % 4: raise SystemExit('%d: size not a multiple of 4' % tid)
    tw = struct.unpack('>%dI' % n, t.data)
    out = bytearray(len(t.data))
    forms = {}
    lut = []
    if tid in TWINS:
        xs, ps = X[(7, TWINS[tid])], P[(7, XBOX_TO_PC[TWINS[tid]])]
        if len(xs.data) != len(ps.data): raise SystemExit('twin sizes differ')
        xw = struct.unpack('>%dI' % (len(xs.data) // 4), xs.data)
        sm = difflib.SequenceMatcher(None, tw, xw, autojunk=False)
        al = {}
        for a, b, m in sm.get_matching_blocks():
            for k in range(m): al[a + k] = b + k
        xids = {o for ty, o in R.parse(xs.reloc, 'be').idref}
        for k in range(n):
            o = 4 * k
            if o in ids: continue
            if k in al and 4 * al[k] not in xids:
                out[o:o + 4] = ps.data[4 * al[k]:4 * al[k] + 4]; forms['twin'] = forms.get('twin', 0) + 1
            elif single_byte(tw[k]) and o not in ptr:
                put(out, o, tw[k], 'u8'); forms['u8 single byte'] = forms.get('u8 single byte', 0) + 1
            else:
                put(out, o, tw[k], 'u32'); forms['u32 (unaligned)'] = forms.get('u32 (unaligned)', 0) + 1
        # check: an unaligned word that is neither zero / pad / pointer / id nor a plausible int or float would be a
        # field of unknown form (e.g. a changed LUT) - there must be none besides the single-byte words
        def plausible(w):
            ex = (w >> 23) & 0xff
            return w in (0, 0xbeebbeeb, 0xffffffff) or w < 0x10000 or 0x60 <= ex <= 0x9f or single_byte(w)
        unk = ['+0x%x=%08x' % (4 * k, tw[k]) for k in range(n)
               if k not in al and 4 * k not in ptr and 4 * k not in ids and not plausible(tw[k])]
        rep.setdefault(str(tid), {})['unaligned_unknown_form'] = unk
        if unk: raise SystemExit('%d: unaligned words of unknown form: %s' % (tid, unk[:10]))
    elif tid == 22194:
        if tw[0] != NREC or 4 in ids: raise SystemExit('22194: unexpected head')
        for k in range(n):
            o = 4 * k
            if o in ids: continue
            f = 'u32'
            if REC0 <= o < REC0 + NREC * RECSZ:
                r = (o - REC0) % RECSZ
                if r == 0x00: f = 'u16'
                elif 0x20 <= r < 0x60: f = 'u8'; lut.append(o)
                elif r == 0x68: f = 'u8'
            put(out, o, tw[k], f); forms[f] = forms.get(f, 0) + 1
    else:
        raise SystemExit('no rule for %d' % tid)
    for o, ty in ids.items():
        v = tw[o // 4]
        if ty != 7: raise SystemExit('%d: id reference of type %d' % (tid, ty))
        if v in KEEP_IDS: pv = v
        elif v in XBOX_TO_PC: pv = XBOX_TO_PC[v]
        else: raise SystemExit('%d +0x%x: no PC id for Xbox DTP %d' % (tid, o, v))
        struct.pack_into('<I', out, o, pv); forms['idref'] = forms.get('idref', 0) + 1
    # monotone check of the 64-byte LUTs (consecutive LUT words form one table)
    tables, cur = [], []
    for o in sorted(lut):
        if cur and o == cur[-1] + 4: cur.append(o)
        else:
            if cur: tables.append(cur)
            cur = [o]
    if cur: tables.append(cur)
    bad = []
    for tb in tables:
        b = bytes(out[tb[0]:tb[-1] + 4])
        if any(b[i] > b[i + 1] for i in range(len(b) - 1)): bad.append('+0x%x' % tb[0])
    rep.setdefault(str(tid), {}).update(size=len(t.data), forms=forms, idrefs=sorted(set(tw[o // 4] for o in ids)),
                                        lut_tables=len(tables), lut_bytes=4 * len(lut), lut_not_monotone=bad)
    if tid == 22194 and bad: raise SystemExit('22194: LUT not monotone at %s' % bad)
    return DW.Section(7, tid, bytes(out), R.write(rel, 'le'), t.flags, t.ver, t.spec, t.pad)


def main(argv):
    rp = None
    if '--report' in argv: k = argv.index('--report'); rp = argv[k + 1]; del argv[k:k + 2]
    if len(argv) != 2 or argv[0] != 'convert': sys.exit(__doc__)
    T, X, P = load('tu'), load('xbase'), pc_sections()
    for i in (21237, 21238, 22194):
        if (7, i) in P: raise SystemExit('the PC generalbank has DTP %d already' % i)
    rep = {}
    secs = [convert_one(i, T[(7, i)], X, P, rep) for i in (21237, 21238, 22194)]
    conv = 'work/rebuild/base_convert/tu_generalbank.drm'
    if os.path.isfile(conv):
        C = {(s.type, s.id): s for s in DW.read(open(conv, 'rb').read(), 'le').sections}
        for s in secs:
            c = C.get((7, s.id))
            if c is None: continue
            t = T[(7, s.id)]
            d = [o for o in range(0, len(s.data), 4) if s.data[o:o + 4] != c.data[o:o + 4]]
            kinds = {}
            for o in d:
                tb, ob, cb = t.data[o:o + 4], s.data[o:o + 4], c.data[o:o + 4]
                if ob == tb and cb == tb[::-1]: kk = 'bytes kept here, u32-swapped by the converter'
                elif cb == tb and ob == tb[::-1]: kk = 'u32 here, bytes kept by the converter'
                elif ob == struct.pack('<HH', *struct.unpack('>HH', tb)): kk = 'u16 here'
                else: kk = 'other'
                kinds[kk] = kinds.get(kk, 0) + 1
                if kk == 'other':
                    rep[str(s.id)].setdefault('other_words', []).append('+0x%x TU %s here %s converter %s' % (
                        o, tb.hex(), ob.hex(), cb.hex()))
            rep[str(s.id)]['vs_generic_converter'] = dict(words_differ=len(d), reloc_same=c.reloc == s.reloc,
                                                         kinds=kinds, first=['+0x%x' % o for o in d[:12]])
    D = DW.Drm(secs)
    raw = D.write('le')
    os.makedirs(os.path.dirname(os.path.abspath(argv[1])), exist_ok=True)
    open(argv[1], 'wb').write(DW.cdrm_encode(raw, 'le'))
    for s in secs:
        rep[str(s.id)]['md5'] = hashlib.md5(s.data).hexdigest()
        rep[str(s.id)]['reloc_bytes'] = len(s.reloc)
    print(json.dumps(rep, indent=1))
    if rp:
        json.dump(rep, open(rp, 'w', encoding='utf-8'), indent=1)
    bad = [k for k, v in rep.items() if v['lut_not_monotone']]
    print('wrote %s (%d sections); LUT tables not monotone: %s' % (argv[1], len(secs), bad or 'none'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
