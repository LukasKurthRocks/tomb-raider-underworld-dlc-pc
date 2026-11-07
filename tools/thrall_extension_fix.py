"""Thrall extension data (object data type 0x3d): typed byte-order rule, proof, gate and fix (N4b, 2026-11-07; finding
docs Befund-P1d-Begleiter-0711.md section 1, workspace work/p1d_0711 + work/extfix_0711).

Why: the DLC 2 thralls carry an `_extension` object (viking / tutorial viking 870, yeti 932, armoured yeti 944): the
first child with object data type 0x3d. The TU creates a companion instance from it (0x822da800) and reads its data
(`[comp+0x50]` = object data, DTP +0xc8 -> root) at 47 places. The converter typed several of its words wrong (u32 /
u16 pair / raw mixed per word, one anim id remapped as an object id 108 -> 124); TruShadowCombat 0.6.5 does not read
the data yet, P1c (Vaulted) and T5 (lethal hit -> death kind 7) will.

Layout of the extension data (root R = target of the internal pointer at DTP +0xc8, u16 R+2 == 0x3d), every field typed
by its TU reader (Xbox 360 TU image, work/xenia_dump/tu_image_82000000.bin; the instruction words are checked by
`proof`) or - for the embedded hit reaction struct - by Eidos' own PC conversion of the base game:
  header R+0x00 .. +0x4f
    +00 {u16 1, u16 0x3d}   lhz +2 (0x822da8a0 cmplwi 0x3d)
    +04 u16 0xb00b (+06 unread) generic object data header: lhz +4 == 0xb00b 0x823277a4 / 0x8233e21c (there on the
                            data of a type 0x21 object; no extension-specific reader)
    +08                     no reader found (judged only when byte-order invariant; left alone otherwise)
    +0c u8 (+0d..0f unread) lbz +0x0c 0x82328494
    +10 {u16, u16} anim     lwz +0x10, lhz halves vs current anim 0x8235e568..e58c
    +14 {u16, u16} anim     lhz +0x16 0x8235e184, lwz +0x14 0x8235e190
    +18 u8 (+19..1b unread) lbz +0x18 0x82328d34 (T2)
    +1c u8 (+1d..1f unread) lbz +0x1c 0x823277c0 (r31 = companion data since 0x823276c8) / 0x8233e238 (r30, 0x8233e11c),
                            compared with 0xff
    +20 ptr / +24 u32 n     step table, entries of 0x14 (lwz +0x24 0x8232b498 / 0x823088fc, lwz +0x20 0x8232b4a8)
    +28 ptr / +2c u32 n     hit records of 0xc4 (lwz +0x2c 0x822f77f8 / 0x82301dfc / 0x82329ce8)
    +30 ptr / +34 u32 n     {kind, value} pairs of 8 (lwz +0x34 0x822f6830)
    +38 u8 lbz +0x38 0x8235e1b4 (r11 = companion data, same function as the +0x14 reader); +39 unread;
    +3a {u16, u16} anim pair at +0x3a / +0x3c: addi +0x3a 0x8235e824, lhz +0x3c 0x8235e828, lhz +0x3a 0x8235e834
                            (compared with the current anim brain+0xe22 / +0xe24); +3e unread
    +40 u32 n / +44 ptr     regeneration list, entries of 0xc (lwz +0x40 0x8235ed5c, +0x44 0x8235ed6c)
    +48 ptr, +4c            (+4c no reader found)
  step entry (0x14, 1-based index: 0x8232b4b8 addi -0x14 / 0x8230891c ..)
    +00 {u16, u16} anim     the entry pointer goes to 0x822d8100 (lhz +0 0x822d813c, lhz +2 0x822d8130)
    +04 {u16, u16} anim     lhz +6 0x82308928 (cmplwi 0xffff), +4 handed on as anim pair (0x8230891c)
    +08 u32                 lwz 0x82308920 (-> fcfid)
    +0c f32                 lfs 0x82308924
    +10 u8 (+11..13 unread) lbz 0x8230892c / 0x8232c108
  hit record (0xc4, looked up by +00 == hit damage type: lwz 0x822f7814 / 0x82301e18 / 0x82329d04, stride
  addi 0xc4 0x822f7824)
    +00 u32 damage type, +04 u8 (lbz 0x82329d38; +05..07 unread), +08 ptr or 0 (lwz 0x82329dac)
    +0c .. +3f = hit reaction struct +0x00 .. +0x33: 0x82301e44 hands rec+0x0c to the same consumer that gets
         D+0x50 + k*0xb4 of the enemy hit switch data D (0x82301ec0 .. 0x82301f7c; PC twin 0x6159a0 the same table);
         TU readers there: struct +0x14 lwz (bit tests 0x82301f90), +0x1c / +0x1d / +0x1e lbz (0x82301f44 /
         0x82301f58 / 0x82301f30)
    +40 f32 (new in the record, not in D): lfs rec+0x40 0x822f783c (Xbox 3.0)
    +44 .. +c3 = hit reaction struct +0x34 .. +0xb3 (the record's struct is the D struct with one f32 inserted at
         struct +0x34: base / DLC enemy D slots hold 0x64 (100) at +0x34 and the 0000ffff blocks at +0x50 / +0x78 /
         +0xa0, the records 3.0 at rec+0x40, 0x64 at rec+0x44 and the blocks at rec+0x60 / +0x88 / +0xb0 - see
         work/extfix_0711/struct_cmp.py); both parts typed per word by the base-game pairs (BSTRUCT_TEXT, `proof`)
  pair (8): +00 u32 kind (lwz 0x822f684c), +04 f32 (lfs 0x822f6878)
  regeneration entry (0xc): three u32 (lwz 0x8235ed70 / 0x8235ed8c / 0x8235edc0)

Rule: every TU-read field is stored on the PC with its own width in little-endian (u8 raw, u16 swapped on its own, u32
/ f32 reversed) and the Xbox VALUE (an anim id is no object id: the TU compares +0x3a / +0x3c with the playing anim;
anim pairs keep their value in every base-game hit struct, see `proof`). Bytes no reader touches are only judged when
the candidate orders give the same bytes (e.g. zero padding); else the word is UNJUDGED and left alone. As in
tools/generator_intro_fix.py a word is set only when the PC word is wrong; a PC word that is no byte order of the Xbox
word is VALUE (fixed only for the reader-typed u16 anim ids, key h+3c / h+38 and the anim keys in VALUE_FIX) or
UNEXPECTED (fix_drm raises SystemExit, the gate fails). Pointers / relocations are never written.

Modes (from the repository root; read-only except `fix`):
  ../bin/pyt -t 1800 tools/thrall_extension_fix.py proof [--report R.json]
        (a) TU image instruction words of every reader above (and the PC twin 0x6159a0), (b) the hit reaction struct
        table from every base-game enemy with hit switch data, Xbox (tu / xbase2 / xbase) x PC (pcpatch / pcbig)
  ../bin/pyt -t 1800 tools/thrall_extension_fix.py scan LIST_OR_DIR [--pack PACK] [--all] [--enemy] [--report R.json]
        PC DRMs (folder / list / .drm, several joined with ','; later name wins); every type-7 section with data
        type 0x3d is planned against its Xbox section; --enemy also checks the hit switch structs of every enemy data
        block (0xdaf00018) with the proven table; exit 1 when any word is wrong / unexpected (the gate)
  ../bin/pyt -t 1800 tools/thrall_extension_fix.py fix LIST_OR_DIR OUTDIR [NAME ...] [--pack PACK]
        writes the DRMs with wrong words to OUTDIR, proves each (only the planned bytes differ, headers / relocations
        identical, re-plan 0); md5.tsv (+ sha256) and thrall_extension_fix.log.txt in OUTDIR's parent folder
  ../bin/pyt -t 1800 tools/thrall_extension_fix.py verify OLD.drm NEW.drm [--pack PACK]
"""
import sys, os, struct, collections, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_write as DW

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
TU_IMAGE = os.path.join(ROOT, 'work', 'xenia_dump', 'tu_image_82000000.bin')
PC_EXE = os.path.join(ROOT, '..', 'data', 'pc', 'tru.exe')
TU_BASE = 0x82000000

ORDERS = {'raw': (0, 1, 2, 3), 'u32': (3, 2, 1, 0), 'u16x2': (1, 0, 3, 2), 'u8u8u16': (0, 1, 3, 2), 'u16u8u8': (1, 0, 2, 3)}
ALL = frozenset(ORDERS)
U32 = frozenset(['u32'])
U16X2 = frozenset(['u16x2'])
U8_ = frozenset(['raw', 'u8u8u16'])         # u8 at byte 0, bytes 1..3 unread (byte 0 stays, 2/3 may swap)
U8_U16 = frozenset(['u8u8u16'])             # u8 at byte 0, byte 1 unread, u16 at bytes 2..3
U16_ = frozenset(['u16x2', 'u16u8u8'])      # u16 at bytes 0..1, bytes 2..3 unread

EXT_TYPE = 0x3d
HDR = 0x50
STEP, REC, PAIR, REGEN = 0x14, 0xc4, 0x8, 0xc
BSTRUCT_AT, BSTRUCT = 0x0c, 0xb4             # hit reaction struct inside a record
REC_INS = 0x40                               # record +0x40: f32 inserted before struct +0x34 (record = 0xc + 0xb4 + 4)
ENEMY_MAGIC = 0xdaf00018                     # enemy data root (u32 on Xbox), [root+0xd4] -> hit switch data D
D_PTR, D_SLOT0, D_SLOTS = 0xd4, 0x50, 11     # D+0x50 + k*0xb4, k = 0..10 (0x82301ec0 .. 0x82301f7c)

# key -> (orders, reader); 'h' header, 's' step entry, 'r' record outside the struct, 'p' pair, 'g' regen entry
LAYOUT = {
    'h+00': (U16X2, 'lhz +2 == 0x3d 0x822da8a0'),
    'h+04': (U16_, 'lhz +4 == 0xb00b 0x823277a4 / 0x8233e21c (generic data header)'),
    'h+08': (ALL, 'no reader found'),
    'h+0c': (U8_, 'lbz +0x0c 0x82328494'),
    'h+10': (U16X2, 'lwz +0x10 / lhz halves 0x8235e568..e58c'),
    'h+14': (U16X2, 'lhz +0x16 0x8235e184, lwz +0x14 0x8235e190'),
    'h+18': (U8_, 'lbz +0x18 0x82328d34'),
    'h+1c': (U8_, 'lbz +0x1c 0x823277c0 / 0x8233e238'),
    'h+20': (U32, 'pointer step table'),
    'h+24': (U32, 'lwz +0x24 0x8232b498'),
    'h+28': (U32, 'pointer records'),
    'h+2c': (U32, 'lwz +0x2c 0x822f77f8'),
    'h+30': (U32, 'pointer pairs'),
    'h+34': (U32, 'lwz +0x34 0x822f6830'),
    'h+38': (U8_U16, 'lbz +0x38 0x8235e1b4, lhz +0x3a 0x8235e834 (+0x39 unread)'),
    'h+3c': (U16_, 'lhz +0x3c 0x8235e828 (+0x3e unread)'),
    'h+40': (U32, 'lwz +0x40 0x8235ed5c'),
    'h+44': (U32, 'pointer regen list'),
    'h+48': (U32, 'pointer'),
    'h+4c': (ALL, 'no reader found'),
    's+00': (U16X2, 'anim pair lhz +0 / +2 0x822d813c / 0x822d8130'),
    's+04': (U16X2, 'anim pair lhz +6 0x82308928'),
    's+08': (U32, 'lwz 0x82308920'),
    's+0c': (U32, 'lfs 0x82308924'),
    's+10': (U8_, 'lbz 0x8230892c / 0x8232c108'),
    'r+00': (U32, 'lwz damage type 0x822f7814'),
    'r+04': (U8_, 'lbz +4 0x82329d38'),
    'r+08': (U32, 'lwz +8 0x82329dac (pointer or 0)'),
    'r+40': (U32, 'lfs rec+0x40 0x822f783c'),
    'p+00': (U32, 'lwz kind 0x822f684c'),
    'p+04': (U32, 'lfs value 0x822f6878'),
    'g+00': (U32, 'lwz 0x8235ed70'),
    'g+04': (U32, 'lwz 0x8235ed8c'),
    'g+08': (U32, 'lwz 0x8235edc0'),
}
# Hit reaction struct (0xb4): key 'b+XX' -> orders that explain every base-game word (Xbox x genuine PC, relocated
# words excluded), derived by `proof` (measured 2026-11-07: 21 pairs, 209 structs, 9405 words, 0 contradicting);
# ALL = every base word byte-order invariant there (no evidence: judged only when the orders agree on the bytes);
# NOTU32 = every order except u32 (base words such as 0000ffff stay 00 00 ff ff, two u16 / bytes, never one u32).
BSTRUCT_TEXT = """
b+00 u16x2
b+04 u16x2
b+08 u16x2
b+0c u16x2
b+10 u16x2
b+14 u32
b+18 u32
b+1c raw u8u8u16
b+20 u32
b+24 u32
b+28 u32
b+2c u32
b+30 u32
b+34 u32
b+38 u32
b+3c ALL
b+40 ALL
b+44 ALL
b+48 ALL
b+4c ALL
b+50 NOTU32
b+54 NOTU32
b+58 NOTU32
b+5c NOTU32
b+60 ALL
b+64 ALL
b+68 ALL
b+6c ALL
b+70 ALL
b+74 ALL
b+78 NOTU32
b+7c NOTU32
b+80 NOTU32
b+84 NOTU32
b+88 ALL
b+8c ALL
b+90 ALL
b+94 ALL
b+98 ALL
b+9c ALL
b+a0 NOTU32
b+a4 NOTU32
b+a8 NOTU32
b+ac NOTU32
b+b0 ALL
"""
# TU readers inside the struct, used only when the base table leaves orders that give different bytes
CODE_TIE = {'b+14': 'u32', 'b+1c': 'raw', 'b+34': 'u32'}
# reader-typed u16 anim ids the converter remapped as object ids: the Xbox value is the PC value (TU compares them
# with the playing anim brain+0xe22 / +0xe24); a VALUE row on one of these keys is fixed, on any other key it is not
VALUE_FIX = {'h+38', 'h+3c', 'h+10', 'h+14', 's+00', 's+04'}

# instruction words the layout relies on (TU image address -> big-endian word, text); checked by `proof`
TU_INSNS = [
    (0x822da8a0, 0xa16b0002, 'lhz r11, 2(r11)  (data type)'), (0x822da8a4, 0x2b0b003d, 'cmplwi cr6, r11, 0x3d'),
    (0x82328494, 0x896b000c, 'lbz r11, 0xc(r11)  (h+0c)'),
    (0x8235e568, 0x81630010, 'lwz r11, 0x10(r3)  (h+10)'), (0x8235e570, 0xa1610062, 'lhz r11, 0x62(r1)'),
    (0x8235e57c, 0xa1010060, 'lhz r8, 0x60(r1)'),
    (0x8235e184, 0xa14b0016, 'lhz r10, 0x16(r11)  (h+14)'), (0x8235e190, 0x816b0014, 'lwz r11, 0x14(r11)'),
    (0x8235e160, 0x816b0050, 'lwz r11, 0x50(r11)  (companion data)'), (0x8235e19c, 0xa14b0012, 'lhz r10, 0x12(r11)'),
    (0x8235e1b4, 0x896b0038, 'lbz r11, 0x38(r11)  (h+38)'),
    (0x823277a4, 0xa14b0004, 'lhz r10, 4(r11)  (data header)'), (0x823277a8, 0x2b0ab00b, 'cmplwi cr6, r10, 0xb00b'),
    (0x8233e21c, 0xa14b0004, 'lhz r10, 4(r11)'),
    (0x823276c8, 0x7d7f5b78, 'mr r31, r11  (companion data)'), (0x823277c0, 0x889f001c, 'lbz r4, 0x1c(r31)  (h+1c)'),
    (0x8233e11c, 0x7d7e5b78, 'mr r30, r11  (companion data)'), (0x8233e238, 0x889e001c, 'lbz r4, 0x1c(r30)  (h+1c)'),
    (0x82328d34, 0x89630018, 'lbz r11, 0x18(r3)  (h+18)'),
    (0x8232b498, 0x81630024, 'lwz r11, 0x24(r3)  (h+24)'), (0x8232b4a8, 0x81630020, 'lwz r11, 0x20(r3)'),
    (0x8232b4b8, 0x386bffec, 'addi r3, r11, -0x14  (step entry, 1-based)'),
    (0x822d8130, 0xa09d0002, 'lhz r4, 2(r29)  (anim pair +2)'), (0x822d813c, 0xa39d0000, 'lhz r28, 0(r29)  (+0)'),
    (0x823088fc, 0x81630024, 'lwz r11, 0x24(r3)'), (0x8230891c, 0x3bcbfff0, 'addi r30, r11, -0x10  (s+04)'),
    (0x82308920, 0x80ebfff4, 'lwz r7, -0xc(r11)  (s+08)'), (0x82308924, 0xc3ebfff8, 'lfs f31, -8(r11)  (s+0c)'),
    (0x82308928, 0xa10bfff2, 'lhz r8, -0xe(r11)  (s+06)'), (0x8230892c, 0x8b8bfffc, 'lbz r28, -4(r11)  (s+10)'),
    (0x8232c108, 0x88aafffc, 'lbz r5, -4(r10)  (s+10)'),
    (0x822f77f8, 0x8123002c, 'lwz r9, 0x2c(r3)  (h+2c)'), (0x822f7814, 0x80cb0000, 'lwz r6, 0(r11)  (r+00)'),
    (0x822f7824, 0x396b00c4, 'addi r11, r11, 0xc4  (record stride)'), (0x822f783c, 0xc1ab0040, 'lfs f13, 0x40(r11)'),
    (0x82301dfc, 0x8103002c, 'lwz r8, 0x2c(r3)'), (0x82301e18, 0x806b0000, 'lwz r3, 0(r11)'),
    (0x82301e44, 0x396b000c, 'addi r11, r11, 0xc  (record +0x0c = hit struct)'),
    (0x82301ec0, 0x39650050, 'addi r11, r5, 0x50  (D slot 0)'), (0x82301f7c, 0x39650758, 'addi r11, r5, 0x758'),
    (0x82301f30, 0x896b001e, 'lbz r11, 0x1e(r11)'), (0x82301f44, 0x896b001c, 'lbz r11, 0x1c(r11)'),
    (0x82301f58, 0x896b001d, 'lbz r11, 0x1d(r11)'), (0x82301f90, 0x816b0014, 'lwz r11, 0x14(r11)'),
    (0x82329ce8, 0x815b002c, 'lwz r10, 0x2c(r27)'), (0x82329d04, 0x80eb0000, 'lwz r7, 0(r11)'),
    (0x82329d38, 0x894b0004, 'lbz r10, 4(r11)  (r+04)'), (0x82329dac, 0x816b0008, 'lwz r11, 8(r11)  (r+08)'),
    (0x822f6830, 0x81230034, 'lwz r9, 0x34(r3)  (h+34)'), (0x822f684c, 0x808b0000, 'lwz r4, 0(r11)  (p+00)'),
    (0x822f685c, 0x396b0008, 'addi r11, r11, 8  (pair stride)'), (0x822f6878, 0xc00b0004, 'lfs f0, 4(r11)  (p+04)'),
    (0x8235e824, 0x388b003a, 'addi r4, r11, 0x3a'), (0x8235e828, 0xa16b003c, 'lhz r11, 0x3c(r11)'),
    (0x8235e834, 0xa1440000, 'lhz r10, 0(r4)'), (0x8235e838, 0xa13e0e22, 'lhz r9, 0xe22(r30)  (playing anim)'),
    (0x8235ed5c, 0x80e30040, 'lwz r7, 0x40(r3)  (h+40)'), (0x8235ed6c, 0x81430044, 'lwz r10, 0x44(r3)'),
    (0x8235ed70, 0x816a0000, 'lwz r11, 0(r10)  (g+00)'), (0x8235ed8c, 0x816a0004, 'lwz r11, 4(r10)  (g+04)'),
    (0x8235edc0, 0x816a0008, 'lwz r11, 8(r10)  (g+08)'),
]
# PC twin of 0x82301dc0 (hit switch slot select): the same D table and the struct +0x14 bit test
PC_INSNS = [(0x6159d2, '8d4750', 'lea eax, [edi + 0x50]'), (0x615a17, '8d8720030000', 'lea eax, [edi + 0x320]'),
            (0x6159b4, '8d873c050000', 'lea eax, [edi + 0x53c]'), (0x615a2f, '81c758070000', 'add edi, 0x758'),
            (0x615a3d, '8b4614', 'mov eax, dword ptr [esi + 0x14]')]
PROOF_EXPECT = {'tu_insn_bad': 0, 'pc_insn_bad': 0, 'contradicting': 0, 'retail_wrong': 0, 'unpaired': 0}
# base-game objects with enemy data (0xdaf00018) and an Xbox + PC copy (amanda / natla_end: other data, lara_mom_thrall /
# lara_doppelganger: no pair in the sources; checked 2026-11-07)
BASE_ENEMIES = ['viking_thrall', 'yeti_thrall', 'yeti_thrall_yggdrasil', 'mayan_thrall', 'panther_thrall', 'merc',
                'merc_deux', 'bat_enemy', 'tiger', 'cat_panther', 'small_albino_spider', 'small_brown_spider',
                'small_brown_spider_no_jump', 'shark_blueshark', 'shark_greenland']


def btable():
    t = {}
    for line in BSTRUCT_TEXT.strip().splitlines():
        k, v = line.split(None, 1)
        v = v.strip()
        t[k] = ALL if v == 'ALL' else (ALL - U32 if v == 'NOTU32' else frozenset(v.split()))
    return t


BTYPES = btable()


def perm(w, p):
    return bytes(w[i] for i in p)


def orders_of(xw, pw):
    return frozenset(n for n, p in ORDERS.items() if perm(xw, p) == pw)


def orders_for(key):
    if key.startswith('b+'): return BTYPES.get(key, ALL)
    return LAYOUT[key][0]


def want_of(key, xw):
    """-> (wanted bytes or None, note)"""
    cands = orders_for(key)
    outs = {perm(xw, ORDERS[c]) for c in cands}
    if len(outs) == 1: return next(iter(outs)), ''
    if key in CODE_TIE and CODE_TIE[key] in cands: return perm(xw, ORDERS[CODE_TIE[key]]), 'code tie-break %s' % CODE_TIE[key]
    return None, 'orders %s give different bytes' % '/'.join(sorted(cands))


def judge(key, xw, pw):
    """-> (status, wanted, note): ok / fix:<PC order> / VALUE / UNEXPECTED / UNJUDGED"""
    want, note = want_of(key, xw)
    if want is not None and pw == want: return 'ok', want, note
    od = orders_of(xw, pw)
    if want is None: return ('UNJUDGED' if od else 'UNEXPECTED'), None, note
    if od: return 'fix:%s' % '/'.join(sorted(od)), want, note
    return ('VALUE' if key in VALUE_FIX else 'UNEXPECTED'), want, note


# ---------------------------------------------------------------- sections
class Sec:
    """one type-7 section: data, endian, pointer slot set, internal pointer map"""
    def __init__(self, typ, sid, data, reloc, endian):
        self.type, self.id, self.data, self.e = typ, sid, bytes(data), endian
        self.E = '>' if endian == 'be' else '<'
        r = R.parse(bytes(reloc), endian)
        self.it = dict(r.internal)
        self.slots = set(r.pointer_offsets()) | set(r.id_offsets())

    def u32(self, o):
        return struct.unpack_from(self.E + 'I', self.data, o)[0]

    def root(self):
        return self.it.get(0xc8)


def secs_of(D, endian):
    return [Sec(s.type, s.id, s.data, s.reloc, endian) if s.type == 7 else None for s in D.sections]


def ext_root(S):
    """root offset when the section holds extension data (type 0x3d), else None"""
    if S is None: return None
    b = S.root()
    if b is None or b + HDR > len(S.data): return None
    return b if struct.unpack_from(S.E + 'H', S.data, b + 2)[0] == EXT_TYPE else None


def enemy_d(S):
    """offset of the hit switch data D when the section holds enemy data (Xbox: u32 root == 0xdaf00018)"""
    if S is None: return None
    b = S.root()
    if b is None or b + D_PTR + 4 > len(S.data): return None
    if S.e == 'be' and S.u32(b) != ENEMY_MAGIC: return None
    if S.e == 'le' and S.data[b:b + 4] not in (struct.pack('<I', ENEMY_MAGIC), struct.pack('<HH', 0xdaf0, 0x18)): return None
    d = S.it.get(b + D_PTR)
    if d is None or d + D_SLOT0 + D_SLOTS * BSTRUCT > len(S.data): return None
    return d


def rec_key(o):
    """record offset -> key: r+00 / r+04 / r+08, b+00 .. b+30 (rec +0x0c .. +0x3f), r+40 (inserted f32), b+34 .. b+b0
    (rec +0x44 .. +0xc3)"""
    if o < BSTRUCT_AT: return 'r+%02x' % o
    if o < REC_INS: return 'b+%02x' % (o - BSTRUCT_AT)
    if o == REC_INS: return 'r+%02x' % o
    return 'b+%02x' % (o - BSTRUCT_AT - 4)


def ext_words(S, b):
    """[(key, offset)] of the extension data at root b, from the section's own pointers / counts (Xbox side)"""
    out = [('h+%02x' % o, b + o) for o in range(0, HDR, 4)]

    def table(poff, coff, esz, keys):
        p = S.it.get(b + poff)
        n = S.u32(b + coff)
        if p is None or not 0 < n < 0x100 or p + n * esz > len(S.data): return 0 if p is None and n == 0 else None
        for j in range(n):
            for o in range(0, esz, 4): out.append((keys(o), p + j * esz + o))
        return n
    ns = table(0x20, 0x24, STEP, lambda o: 's+%02x' % o)
    nr = table(0x28, 0x2c, REC, rec_key)
    npr = table(0x30, 0x34, PAIR, lambda o: 'p+%02x' % o)
    ng = table(0x44, 0x40, REGEN, lambda o: 'g+%02x' % o)
    return out, dict(steps=ns, records=nr, pairs=npr, regen=ng)


def pair_sections(XD, PD, pick):
    """[(Xbox Sec, PC Sec, PC index)] for sections where pick(Xbox Sec) is not None: same id + size + internal pointer
    layout first, else unique size + layout"""
    xs, ps = secs_of(XD, 'be'), secs_of(PD, 'le')
    lay = collections.defaultdict(list)
    for k, s in enumerate(ps):
        if s is not None: lay[len(s.data), tuple(sorted(s.it.items()))].append(k)
    out, used, unpaired = [], set(), []
    for x in xs:
        if x is None or pick(x) is None: continue
        cand = [k for k in lay.get((len(x.data), tuple(sorted(x.it.items()))), []) if k not in used]
        same = [k for k in cand if ps[k].id == x.id]
        k = same[0] if same else (cand[0] if len(cand) == 1 else None)
        if k is None: unpaired.append(x.id); continue
        used.add(k); out.append((x, ps[k], k))
    return out, unpaired


# ---------------------------------------------------------------- plan
def plan(XD, PD, enemy=False):
    """-> dict(rows=[(PC section index, section id, offset, key, Xbox word, PC word, wanted, status, note, what)],
    exts=[...], unpaired=[...], layout=[...])"""
    res = dict(rows=[], exts=[], unpaired=[], layout=[], enemies=[])
    prs, un = pair_sections(XD, PD, ext_root)
    res['unpaired'] += ['ext DTP %d' % i for i in un]
    for x, p, k in prs:
        b = ext_root(x)
        if ext_root(p) != b: res['layout'].append('DTP %d: PC root %s' % (x.id, ext_root(p))); continue
        words, cnt = ext_words(x, b)
        if None in cnt.values(): res['layout'].append('DTP %d: table counts %s' % (x.id, cnt)); continue
        res['exts'].append(dict(id=x.id, pid=p.id, si=k, root=b, **cnt))
        for key, o in words:
            if o in x.slots or o in p.slots:
                if (o in x.slots) != (o in p.slots): res['layout'].append('DTP %d +0x%x: relocation on one side' % (x.id, o))
                continue
            xw, pw = x.data[o:o + 4], p.data[o:o + 4]
            st, want, note = judge(key, xw, pw)
            res['rows'].append((k, p.id, o, key, xw, pw, want, st, note, 'ext'))
    if enemy:
        prs, un = pair_sections(XD, PD, enemy_d)
        res['unpaired'] += ['enemy DTP %d' % i for i in un]
        for x, p, k in prs:
            d = enemy_d(x)
            if enemy_d(p) != d: res['layout'].append('enemy DTP %d: PC D %s' % (x.id, enemy_d(p))); continue
            res['enemies'].append(dict(id=x.id, pid=p.id, si=k, d=d))
            for j in range(D_SLOTS):
                for w in range(0, BSTRUCT, 4):
                    o = d + D_SLOT0 + j * BSTRUCT + w
                    if o in x.slots or o in p.slots: continue
                    xw, pw = x.data[o:o + 4], p.data[o:o + 4]
                    st, want, note = judge('b+%02x' % w, xw, pw)
                    res['rows'].append((k, p.id, o, 'b+%02x' % w, xw, pw, want, st, note, 'enemy D slot %d' % j))
    return res


def todo_rows(info):
    return [r for r in info['rows'] if r[7].startswith('fix:') or r[7] == 'VALUE']


def fix_drm(XD, raw, enemy=False):
    """-> (new raw or None, changes [(section index, offset, old, new, section id, key, what)], plan info)"""
    PD = DW.read(raw, 'le')
    info = plan(XD, PD, enemy)
    bad = [r for r in info['rows'] if r[7] == 'UNEXPECTED']
    if bad:
        raise SystemExit('thrall_extension_fix: %d UNEXPECTED word(s): %s' % (len(bad), ', '.join(
            'DTP %d +%#x %s Xbox %s PC %s' % (r[1], r[2], r[3], r[4].hex(), r[5].hex()) for r in bad[:10])))
    todo = todo_rows(info)
    if not todo: return None, [], info
    secs, changes = {}, []
    for k, sid, o, key, xw, pw, want, st, note, what in todo:
        b = secs.setdefault(k, bytearray(PD.sections[k].data))
        assert bytes(b[o:o + 4]) == pw
        b[o:o + 4] = want
        changes.append((k, o, pw, want, sid, key, what))
    for k, b in secs.items(): PD.sections[k].data = bytes(b)
    new = PD.write('le')
    if raw[:4] == b'CDRM': new = DW.cdrm_encode(new, 'le')
    verify(raw, new, changes, XD, enemy)
    return new, changes, info


def verify(raw, new, changes, XD, enemy=False):
    """assert: decoded files differ only in the planned bytes, section headers / relocation blobs / names identical,
    re-plan finds 0 words to fix -> number of differing bytes"""
    A, B = DW.read(raw, 'le'), DW.read(new, 'le')
    assert len(A.sections) == len(B.sections) and A.names == B.names and A.pad == B.pad, 'file layout changed'
    planned = {(k, q + j) for k, q, a, b, *_ in changes for j in range(4) if a[j] != b[j]}
    got = set()
    for k, (a, b) in enumerate(zip(A.sections, B.sections)):
        assert (a.type, a.id, a.flags, a.ver, a.spec, a.pad, bytes(a.reloc), len(a.data)) == \
               (b.type, b.id, b.flags, b.ver, b.spec, b.pad, bytes(b.reloc), len(b.data)), 'section %d header changed' % k
        if a.data != b.data: got |= {(k, i) for i in range(len(a.data)) if a.data[i] != b.data[i]}
    assert got == planned, '%d bytes differ, %d planned' % (len(got), len(planned))
    dec0, dec1 = DW.cdrm_decode(raw, 'le'), DW.cdrm_decode(new, 'le')
    assert len(dec0) == len(dec1), 'decoded size changed'
    nd = sum(1 for i in range(len(dec0)) if dec0[i] != dec1[i])
    assert nd == len(planned), 'decoded byte diff %d != planned %d' % (nd, len(planned))
    again = todo_rows(plan(XD, B, enemy)) + [r for r in plan(XD, B, enemy)['rows'] if r[7] == 'UNEXPECTED']
    assert not again, 're-plan finds %d words' % len(again)
    return len(got)


# ---------------------------------------------------------------- proof
def check_insns():
    bad, lines = [], []
    if os.path.exists(TU_IMAGE):
        img = open(TU_IMAGE, 'rb').read()
        for a, w, t in TU_INSNS:
            got = struct.unpack_from('>I', img, a - TU_BASE)[0]
            ok = got == w
            lines.append('  TU 0x%08x %08x %s %s' % (a, got, 'ok ' if ok else 'BAD', t))
            if not ok: bad.append(('tu', a))
    else:
        lines.append('  TU image missing: %s' % TU_IMAGE); bad.append(('tu', 'image'))
    pbad = []
    if os.path.exists(PC_EXE):
        import pe_callers as PE
        exe = open(PC_EXE, 'rb').read()
        _, secs = PE.sections(exe)
        for a, hx, t in PC_INSNS:
            off = next((rp + a - va for _, va, rp, sz, _ in secs if va <= a < va + sz), None)
            got = exe[off:off + len(hx) // 2].hex() if off is not None else '?'
            ok = got == hx
            lines.append('  PC 0x%08x %s %s %s' % (a, got, 'ok ' if ok else 'BAD', t))
            if not ok: pbad.append(a)
    else:
        lines.append('  PC exe missing: %s' % PC_EXE); pbad.append('exe')
    return bad, pbad, lines


def base_sections(name, src):
    import dtp_twin_field as TW
    import locals as LC
    secs, s = TW.load_named(name, (src,), LC.SRC[src][1])
    if not secs: return None
    e = LC.SRC[src][1]
    D = DW.Drm([DW.Section(x['type'], x['id'], x['data'] or b'', x['reloc'] or b'') for x in secs])
    return D, e


def proof(report=None):
    tbad, pbad, lines = check_insns()
    for l in lines: print(l)
    print('instruction words: TU %d checked, %d bad; PC %d checked, %d bad' % (len(TU_INSNS), len(tbad), len(PC_INSNS), len(pbad)))
    sets, seen, informative = {}, collections.Counter(), collections.Counter()
    contra, wrong, unpaired, pairs = [], [], [], []
    values = collections.defaultdict(collections.Counter)
    for name in BASE_ENEMIES:
        xs = {s: base_sections(name, s) for s in ('tu', 'xbase2', 'xbase')}
        ps = {s: base_sections(name, s) for s in ('pcpatch', 'pcbig')}
        for p, PV in ps.items():
            if PV is None: continue
            for x, XV in xs.items():
                if XV is None: continue
                prs, un = pair_sections(XV[0], PV[0], enemy_d)
                unpaired += ['%s %s/%s DTP %d' % (name, p, x, i) for i in un]
                nst = 0
                for X, P, k in prs:
                    d = enemy_d(X)
                    if enemy_d(P) != d: unpaired.append('%s %s/%s DTP %d: PC D differs' % (name, p, x, X.id)); continue
                    for j in range(D_SLOTS):
                        nst += 1
                        for w in range(0, BSTRUCT, 4):
                            o = d + D_SLOT0 + j * BSTRUCT + w
                            if o in X.slots or o in P.slots: continue
                            key = 'b+%02x' % w
                            xw, pw = X.data[o:o + 4], P.data[o:o + 4]
                            od = orders_of(xw, pw)
                            seen[key] += 1
                            if len(od) < len(ORDERS): informative[key] += 1
                            if w in (0x00, 0x04, 0x08, 0x0c, 0x54, 0x58): values[key][xw.hex()] += 1
                            sets[key] = sets.get(key, ALL) & od
                            if not od: contra.append((name, p, x, X.id, j, key, xw.hex(), pw.hex()))
                            st, want, note = judge(key, xw, pw)
                            if st != 'ok': wrong.append((name, p, x, X.id, j, key, xw.hex(), pw.hex(), st))
                pairs.append('%s %s/%s: %d enemy data sections, %d structs' % (name, p, x, len(prs), nst))
                print(pairs[-1], flush=True)
    diff = sorted(k for k in set(sets) | set(BTYPES) if sets.get(k) != BTYPES.get(k))
    for k in sorted(set(sets) | set(BTYPES)):
        print('  %-5s words %5d informative %5d  derived %-34s table %-34s %s' % (
            k, seen[k], informative[k], ' '.join(sorted(sets.get(k, ()))) or '-', ' '.join(sorted(BTYPES.get(k, ()))) or '-',
            'ok' if sets.get(k) == BTYPES.get(k) else 'DIFFERS'))
    for k in sorted(values): print('  Xbox values %s %s' % (k, dict(values[k].most_common(8))))
    for c in contra[:20]: print('  CONTRADICTS %s %s/%s DTP %d slot %d %s Xbox %s PC %s' % c)
    for w in wrong[:20]: print('  BASE WORD NOT OK %s %s/%s DTP %d slot %d %s Xbox %s PC %s %s' % w)
    for u in unpaired[:20]: print('  UNPAIRED %s' % u)
    got = {'tu_insn_bad': len(tbad), 'pc_insn_bad': len(pbad), 'contradicting': len(contra), 'retail_wrong': len(wrong),
           'unpaired': len(unpaired)}
    nstructs = sum(int(p.split(', ')[1].split()[0]) for p in pairs)
    ok = got == PROOF_EXPECT and not diff and nstructs > 0
    print('pairs %d, structs %d, words %d; table differences %s' % (len(pairs), nstructs, sum(seen.values()), diff or 'none'))
    print('rule typed thrall extension data: %s  %s (expected %s)' % ('PROVEN' if ok else 'FAILED', got, PROOF_EXPECT))
    if report:
        json.dump(dict(result='PROVEN' if ok else 'FAILED', counts=got, pairs=pairs, insns=lines,
                       table={k: sorted(v) for k, v in sets.items()}, seen=dict(seen), informative=dict(informative),
                       contradicting=contra, retail_wrong=wrong, unpaired=unpaired,
                       values={k: dict(v) for k, v in values.items()}), open(report, 'w', encoding='utf-8'), indent=1)
    return 0 if ok else 1


# ---------------------------------------------------------------- files
def file_list(spec):
    import soundplex_sequence_fix as SQ
    return SQ.file_list(spec)


def interesting(PD, enemy):
    ps = secs_of(PD, 'le')
    return any(ext_root(s) is not None or (enemy and enemy_d(s) is not None) for s in ps)


def check_file(path, pack=None, enemy=False):
    import soundplex_sequence_fix as SQ
    PD = DW.read(open(path, 'rb').read(), 'le')
    if not interesting(PD, enemy): return 'nothing', None, None, None
    cands = SQ.xbox_candidates(path, pack)
    if not cands: return 'no Xbox source', None, None, None
    best = None
    for XD, pk in cands:
        info = plan(XD, PD, enemy)
        score = (len(info['exts']) + len(info['enemies']), -len(info['unpaired']), -len(todo_rows(info)))
        if best is None or score > best[0]: best = (score, XD, pk, info)
    _, XD, pk, info = best
    return 'ok (%s)' % pk, info, XD, pk


def row_text(r):
    k, sid, o, key, xw, pw, want, st, note, what = r
    return '%s DTP %d sec %d +%#07x %-5s Xbox %s PC %s rule %s %s%s' % (
        what, sid, k, o, key, xw.hex(), pw.hex(), want.hex() if want else '?',
        'ok' if st == 'ok' else ('WRONG (PC = %s)' % st[4:] if st.startswith('fix:') else st), (' [%s]' % note) if note else '')


def scan(paths, show_all, pack=None, enemy=False):
    tot = collections.Counter(); lines = []; files = []

    def say(t):
        print(t, flush=True); lines.append(t)
    for path in paths:
        st, info, XD, pk = check_file(path, pack, enemy)
        if info is None:
            if st != 'nothing': say('%s: %s' % (path, st)); tot['no xbox'] += 1
            continue
        tot['files'] += 1
        bad = [r for r in info['rows'] if r[7] != 'ok']
        for r in info['rows']:
            tot['words ' + r[9].split(' slot')[0]] += 1
            if r[7] != 'ok': tot[('wrong' if r[7].startswith('fix:') else r[7].lower()) + ' ' + r[9].split(' slot')[0]] += 1
        tot['unpaired'] += len(info['unpaired']); tot['layout'] += len(info['layout'])
        tot['ext sections'] += len(info['exts']); tot['enemy sections'] += len(info['enemies'])
        if todo_rows(info) or any(r[7] == 'UNEXPECTED' for r in bad): files.append(path.replace(chr(92), '/'))
        say('%s: %s, ext %s, enemy D %s, %d words, %d not ok (%d to fix)' % (
            path, st, ['DTP %d root +0x%x steps %d records %d pairs %d regen %d' % (e['id'], e['root'], e['steps'], e['records'],
                                                                                   e['pairs'], e['regen']) for e in info['exts']],
            ['DTP %d D +0x%x' % (e['id'], e['d']) for e in info['enemies']], len(info['rows']), len(bad), len(todo_rows(info))))
        for u in info['unpaired']: say('   UNPAIRED %s' % u)
        for u in info['layout']: say('   LAYOUT %s' % u)
        for r in (info['rows'] if show_all else bad): say('   ' + row_text(r))
    res = 'FAIL' if any(k.startswith(('wrong', 'value', 'unexpected')) for k in tot) or tot['unpaired'] or tot['layout'] else 'ok'
    say('TOTAL %s' % dict(sorted(tot.items()))); say('scan: %s' % res)
    return res, dict(tot), files, lines


def fix(spec, outdir, only, pack, enemy=False):
    os.makedirs(outdir, exist_ok=True)
    top = os.path.dirname(os.path.abspath(outdir))
    log = open(os.path.join(top, 'thrall_extension_fix.log.txt'), 'w', encoding='utf-8', newline='\r\n')
    sums = ['md5\tsha256\tpath\tsource_md5\tsource_sha256']
    for path in file_list(spec):
        name = os.path.basename(path)
        if only and name not in only: continue
        st, info, XD, pk = check_file(path, pack, enemy)
        if info is None or not todo_rows(info): continue
        raw = open(path, 'rb').read()
        new, changes, info = fix_drm(XD, raw, enemy)
        if new is None: continue
        for k, q, pw, want, sid, key, what in changes:
            line = '%s %s DTP %d %s: section %d +%#07x %s -> %s' % (name, what, sid, key, k, q, pw.hex(), want.hex())
            print(line); log.write(line + '\n')
        dst = os.path.join(outdir, name)
        open(dst, 'wb').write(new)
        back = open(dst, 'rb').read()
        assert back == new, 'read-back differs'
        nd = verify(raw, back, changes, XD, enemy)
        h, h0 = hashlib.md5(new).hexdigest(), hashlib.md5(raw).hexdigest()
        s, s0 = hashlib.sha256(new).hexdigest(), hashlib.sha256(raw).hexdigest()
        line = '%s (%s): %d words, %d bytes differ from %s (md5 %s sha256 %s; all inside the planned words), headers + ' \
               'relocations identical, re-plan 0; new md5 %s sha256 %s' % (name, pk, len(changes), nd, path, h0, s0, h, s)
        print(line); log.write(line + '\n')
        sums.append('%s\t%s\t%s\t%s\t%s' % (h, s, name, h0, s0))
    open(os.path.join(top, 'md5.tsv'), 'w', encoding='utf-8', newline='\n').write('\n'.join(sums) + '\n')
    log.close()
    print('files written', len(sums) - 1)


def verify_pair(old, new, pack, enemy=False):
    raw, nraw = open(old, 'rb').read(), open(new, 'rb').read()
    st, info, XD, pk = check_file(old, pack, enemy)
    if info is None: print('%s: %s' % (old, st)); return 1
    changes = [(r[0], r[2], r[5], r[6], r[1], r[3], r[9]) for r in todo_rows(info)]
    try:
        n = verify(raw, nraw, changes, XD, enemy)
    except AssertionError as e:
        print('verify %s -> %s: FAILED %s' % (old, new, e)); return 1
    print('verify %s -> %s: ok, %d planned words, %d bytes differ, re-plan 0; md5 %s -> %s, sha256 %s -> %s' % (
        old, new, len(changes), n, hashlib.md5(raw).hexdigest(), hashlib.md5(nraw).hexdigest(),
        hashlib.sha256(raw).hexdigest(), hashlib.sha256(nraw).hexdigest()))
    return 0


def opt(a, key):
    if key in a:
        k = a.index(key); v = a[k + 1]; del a[k:k + 2]; return v
    return None


def main(a):
    if not a: sys.exit(__doc__)
    pack = opt(a, '--pack') or 'pack11'; report = opt(a, '--report')
    show_all = '--all' in a; enemy = '--enemy' in a
    a = [x for x in a if x not in ('--all', '--enemy')]
    if a[0] == 'proof': return proof(report)
    if a[0] == 'scan' and len(a) >= 2:
        r, tot, files, lines = scan(file_list(a[1]), show_all, pack, enemy)
        if report:
            os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
            json.dump(dict(result=r, spec=a[1], pack=pack, enemy=enemy, totals=tot, files=files, lines=lines),
                      open(report, 'w', encoding='utf-8'), indent=1)
        return 1 if r != 'ok' else 0
    if a[0] == 'fix' and len(a) >= 3: fix(a[1], a[2], set(a[3:]), pack, enemy); return 0
    if a[0] == 'verify' and len(a) == 3: return verify_pair(a[1], a[2], pack, enemy)
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
