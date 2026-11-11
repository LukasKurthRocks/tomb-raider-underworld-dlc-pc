"""locals.bin (localised string table) reader/writer + DLC merge for PC.

Format (Yura LocaleFile; verified by byte-exact round trip below): platform endian
  u32 language, u32 n, u32 offset[n] (absolute file offsets), then NUL-terminated UTF-8 strings.
One file per language; bigfile entries share the name hash and differ by specMask (language bits):
  0xffffffe0 / 0xfffff7e1 / 0xfffff7e2 / 0xfffff7e4 / 0xfffff7e8 / 0xfffff7f0.
Strings are referenced by INDEX from game data, so the merge keeps PC indices and only fills indices that PC lacks.

Usage: python3 -I tools/locals.py survey      (compare all versions)
       python3 -I tools/locals.py build [out]  -> <out>/mods/local/locals.bin_<NNN> (ModLoader per-language name:
            '%s_%03d' % (path, specMask & ~0x80000000); NNN = 001/002/004/008/016 from the spec low bits, 032 for 0xffffffe0;
            languages (table field, checked 2026-11-10 on the installed tables): 001 English (0), 002 French (1),
            004 German (3), 008 Italian (2), 016 Spanish (4), 032 Dutch (5, text only - no Dutch speech in the .mul))
            + <out>/locmap_xbox_to_pc.json (Xbox TU string index -> PC string id, for the data converters)
            Text rules of the installed (played) tables, applied by build (2026-11-11, R9): merged() also replaces
            localised placeholders (same_slot_number), unfilled_from_packs() (PC 5211; skip with --no-pack-fill =
            the Xbox TU state, empty / 'KEIN TEXT'), unwrap_descriptions() (PC 456 / 457). No text is stored here:
            every string comes from the player's archives at build time. Gate: tools/locals_text_gate.py.
            --pad-glyph-names (Q9, 2026-11-11, opt-in until played): pad_glyph_names() - the PC names of the
            Xbox 360 pad's Start / Back buttons become their button glyphs U+1810 / U+1811 (TU look of
            "Press [Back]" prompts such as 5182 / 5201 / 1301; see pad_glyph_names()).
       python3 -I tools/locals.py padnames IN_DIR OUT_DIR  -> the same rule on existing tables (e.g. the installed
            ones, read only): OUT_DIR/locals.bin_<NNN> for the six languages, nothing else changed.
"""
import sys, os, re, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc

B = '../data/'
C = B + 'Xenia-SteveRepack/Content/534307EC/00000002/'
SRC = {'xbase': (B + 'TombRaiderUnderworld_Patched/layer1.000', 'be', 'xenon-w'), 'xbase2': (B + 'TombRaiderUnderworld_Patched/layer2.000', 'be', 'xenon-w'),
       'tu': (B + 'TombRaiderUnderworld_Patched/TitleUpdate.000', 'be', 'xenon-w'),
       'pcbig': (B + 'pc/bigfile.000', 'le', 'pc-w'), 'pcpatch': (B + 'pc/patch.000', 'le', 'pc-w'),
       'pack10': (C + '9CA70CF0EDA43654D158C2E37470D301DFA850E753/pack10.000', 'be', 'xenon-w'),
       'pack11': (C + '600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153/pack11.000', 'be', 'xenon-w'),
       'pack1': (C + 'E5AFB2B959A72C52120D73678AED11BD8752686753/pack1.000', 'be', 'xenon-w'),
       'pack2': (C + '9FDDD06617D1016DE468ACF53AC663E8BA2AD41853/pack2.000', 'be', 'xenon-w'),
       'pack20': (C + 'AC0089F81B621CD0E0C156B6176EFCC6C844705D53/pack20.000', 'be', 'xenon-w')}
# The PC tables are built from the PC patch table + the title-update table (merged()). The title update's 6 locals.bin
# records are byte-identical to pack11's (work/playerpath_1011/tu_vs_dlc.tsv; the survey prints "pack11 diff(tu) 0"),
# so build reads that table from pack11 (TU_TABLE, plan Spielerweg P1, 2026-11-11): the player path needs no
# TitleUpdate.000 here. build opens only BUILD_SRC; survey (developer) opens every source incl. 'tu'.
TU_TABLE = 'pack11'
BUILD_SRC = ('xbase', 'pcbig', 'pcpatch', TU_TABLE, 'pack1', 'pack2')

def parse(b, endian):
    e = '>' if endian == 'be' else '<'
    lang, n = struct.unpack_from(e + 'II', b, 0)
    offs = struct.unpack_from(e + '%dI' % n, b, 8)
    out = []
    for o in offs:
        z = b.index(b'\0', o)
        out.append(b[o:z])
    return lang, out, offs

def write(lang, strings, endian, dedup=False):
    e = '>' if endian == 'be' else '<'
    n = len(strings)
    hdr = 8 + 4 * n
    body = bytearray(); offs = []; seen = {}
    for s in strings:
        if dedup and s in seen: offs.append(seen[s]); continue
        offs.append(hdr + len(body)); seen[s] = offs[-1]
        body += s + b'\0'
    return struct.pack(e + 'II', lang, n) + struct.pack(e + '%dI' % n, *offs) + bytes(body)

def files(src):
    path, e, pre = SRC[src]
    a = Archive(path, e)
    return {r['spec']: a.read(r) for r in a.find(crc(pre + '\\local\\locals.bin'))}, e

def survey(srcs=SRC):
    V = {}
    for s in srcs:
        f, e = files(s)
        if not f: continue
        V[s] = {}
        for spec, b in sorted(f.items()):
            lang, st, offs = parse(b, e)
            exact = write(lang, st, e) == b
            dexact = write(lang, st, e, dedup=True) == b
            V[s][spec] = (lang, st)
            print('%-8s spec %08x lang %3d strings %5d bytes %7d  roundtrip %s dedup-roundtrip %s' % (s, spec, lang, len(st), len(b), exact, dexact))
    return V

def compare(V):
    for spec in sorted(V['pcpatch']):
        pc = V['pcpatch'][spec][1]; pb = V['pcbig'][spec][1] if spec in V.get('pcbig', {}) else None
        xb = V['xbase'][spec][1]; tu = V['tu' if 'tu' in V else TU_TABLE][spec][1]
        d = lambda a, b: sum(1 for i in range(min(len(a), len(b))) if a[i] != b[i])
        line = 'spec %08x: n pcbig %s pcpatch %d xbase %d tu %d' % (spec, len(pb) if pb else '-', len(pc), len(xb), len(tu))
        line += ' | diff(xbase,pcbig) %s diff(tu,pcpatch) %d diff(xbase,tu) %d' % (d(xb, pb) if pb else '-', d(tu, pc), d(xb, tu))
        for p in ('pack10', 'pack11', 'pack1'):
            if spec in V.get(p, {}):
                line += ' | %s n %d diff(tu) %d' % (p, len(V[p][spec][1]), d(V[p][spec][1], tu))
        print(line)

SPECS = (0xfffff7e1, 0xfffff7e2, 0xfffff7e4, 0xfffff7e8, 0xfffff7f0, 0xffffffe0)

def build_map(V):
    """Xbox TU string index -> PC string id.
    1. base indices: unique-string equality Xbox base table vs PC patch table, voted over the 6 languages (>=4 votes)
    2. indices inside a consistent span of mapped neighbours (m[b]-m[a]==b-a) are interpolated
    3. everything else (TU/DLC-new indices >= 1284 and base indices without a PC counterpart) is APPENDED after the
       PC table (new ids 5136+), in Xbox index order. Index 0 is the null entry (0 -> 0)."""
    votes = collections.defaultdict(collections.Counter)
    for spec in SPECS:
        X = V['xbase'][spec][1]; P = V['pcpatch'][spec][1]
        offs = parse(files_cache['pcpatch'][spec], 'le')[2]
        idx = collections.defaultdict(list)
        for i, s in enumerate(P):
            if offs[i] != 0: idx[s].append(i)
        for i, s in enumerate(X):
            c = idx.get(s)
            if s and c and len(c) == 1: votes[i][c[0]] += 1
    m = {0: 0}
    for x, c in votes.items():
        (p, n), = c.most_common(1)
        if n >= 4: m[x] = p
    inv = collections.Counter(m.values()); m = {k: v for k, v in m.items() if inv[v] == 1}
    nbase = len(V['xbase'][SPECS[0]][1]); ntu = len(V[TU_TABLE][SPECS[0]][1])
    ks = sorted(m); interp = 0
    for a, b in zip(ks, ks[1:]):
        if b - a > 1 and m[b] - m[a] == b - a:
            for x in range(a + 1, b): m[x] = m[a] + x - a; interp += 1
    npc = len(V['pcpatch'][SPECS[0]][1]); nxt = npc; appended = []
    for x in range(1, ntu):
        if x not in m: m[x] = nxt; nxt += 1; appended.append(x)
    return m, dict(matched=len(votes), mapped_by_string=len(ks), interpolated=interp, appended=len(appended),
                   appended_base=sum(1 for x in appended if x < nbase), appended_dlc=sum(1 for x in appended if x >= nbase), pc_n=npc, tu_n=ntu)

_NUM = re.compile(rb'^(.*\S)\s+(\d+)$')


def same_slot_number(pc_text, base_text):
    """True when the PC text is the PC's own localised name of the same numbered Xbox base placeholder: both end in
    the same slot number after a non-empty stem ('Traje Extra 11' / 'Extra Costume 11', 'Mision Extra 1' /
    'DLC Mission 1'). A real PC name ('Roter Trockenanzug Leicht') has no slot number and is kept."""
    a, b = _NUM.match(pc_text.strip()), _NUM.match(base_text.strip())
    return bool(a and b and a.group(2) == b.group(2))


def merged(V, spec, m):
    """PC patch table + TU strings: appended ids get the TU text; a mapped base id whose PC text equals the Xbox
    BASE text (placeholder like 'DLC TEST MISSION 2' / 'Extra Costume 1') but changed in the TU gets the TU text;
    so does one whose PC text is a LOCALISED placeholder of the same slot (same_slot_number: Spanish PC 93 / 98 /
    450 'Traje Extra 11' / 'Traje Extra 16' / 'Mision Extra 1' -> TU 'Traje seco rojo' / ... / 'BAJO LAS CENIZAS';
    the rule of the former tools/locals_fix_dlcimg.py, which listed these three ids by hand)."""
    pc = list(V['pcpatch'][spec][1]); lang = V['pcpatch'][spec][0]
    X = V['xbase'][spec][1]; T = V[TU_TABLE][spec][1]
    n = max(m.values()) + 1
    pc += [b''] * (n - len(pc))
    st = collections.Counter()
    for x, p in m.items():
        if x == 0: continue
        if p >= len(V['pcpatch'][spec][1]): pc[p] = T[x]; st['appended'] += 1
        elif x < len(X) and T[x] != X[x] and pc[p] == X[x]: pc[p] = T[x]; st['placeholder_replaced'] += 1
        elif x < len(X) and T[x] != X[x] and pc[p] != T[x] and same_slot_number(pc[p], X[x]):
            pc[p] = T[x]; st['localised_placeholder_replaced'] += 1
        elif x < len(X) and T[x] != X[x]: st['tu_changed_but_pc_differs_kept_pc'] += 1
    return lang, pc, st


# Costume packs (Xbox marketplace) whose string table is an OLDER layout of the DLC range (1376 entries; their
# 1296-1353 are a DLC 1 hint list the title update replaced) - read only for unfilled_from_packs().
COSTUME_PACKS = ('pack1', 'pack2')
# PC ids of the DLC 1 / DLC 2 mission descriptions (Xbox TU 459 / 460), see unwrap_descriptions()
DESC_IDS = {459: 456, 460: 457}


def unfilled_from_packs(V, m, spec, strings, en_spec=0xfffff7e1):
    """Installed-state rule (B138 kit, played 27.10.): a DLC id (Xbox index >= base table size) whose title-update
    entry is EMPTY in English is an unfilled slot (the other languages hold '' / 'KEIN TEXT' / 'NO TEXT'); it takes,
    in every language, the entry of the costume packs' tables at the same index when that is non-empty in English and
    all present packs agree. Today exactly one id: Xbox 1326 = PC 5211. Note: on the Xbox (TU = pack11 table) the
    slot stays empty - the packs' text there is a DLC 1 hint line of their older layout, not a TU string."""
    st = collections.Counter()
    nbase = len(V['xbase'][spec][1]); T = V[TU_TABLE][spec][1]; TE = V[TU_TABLE][en_spec][1]
    packs = [k for k in COSTUME_PACKS if k in V and spec in V[k] and en_spec in V[k]]
    for x, p in m.items():
        if x < nbase or x >= len(T) or TE[x] != b'': continue
        st['tu_empty_slots'] += 1
        cand = [(V[k][en_spec][1][x], V[k][spec][1][x]) for k in packs if x < len(V[k][spec][1])]
        cand = [c for c in cand if c[0] != b'']
        if not packs: st['no_costume_pack'] += 1; continue
        if not cand: st['pack_empty_too'] += 1; continue
        if len({c[1] for c in cand}) != 1: st['packs_disagree'] += 1; continue
        strings[p] = cand[0][1]; st['filled_from_pack'] += 1
    return st


def unwrap_descriptions(m, strings):
    """Installed-state rule (tools/dlc_text_unwrap.py, played 27.10., docs/DLC_MENU.md): with the Xbox TU text style
    the mission description box wraps by itself, so every hard line break of the two DLC descriptions becomes a
    space (FR / DE / IT / ES / NL carry Xbox breaks every 47-52 characters; English has none). Same length."""
    st = collections.Counter()
    for x, p in DESC_IDS.items():
        assert m.get(x) == p, 'description id map changed: Xbox %d -> %s, expected %d' % (x, m.get(x), p)
        if b'\n' in strings[p]:
            strings[p] = strings[p].replace(b'\n', b' '); st['description_unwrapped'] += 1
    return st

# Button names of the Xbox 360 pad on PC (tru.exe 1.1, static 2026-11-11, docs/ENGINE.md "Button glyphs in text"):
# the name loader 0x47a2c0 sets the name of input code 0x40 + c (XInput button c, pad codes as in ENGINE.md section 21)
# to GetLocalString(PAD_NAME_FIRST + c) for c = 0..15 when the pad is an "Xbox 360 Controller". cdc::UIText draws its
# text through 0x5a7c20, which replaces every U+1800..U+182E by ESC + name of the bound button + ESC; the pad code of
# a code point comes from the table at 0x8a9ef8 (index = code point - 0x1800). PAD_GLYPH is that table inverted for
# the 16 XInput buttons (code point whose table entry is c).
PAD_NAME_FIRST = 5061
PAD_GLYPH = {0: 0x1801, 1: 0x1800, 2: 0x1802, 3: 0x1803, 4: 0x1805, 5: 0x1807, 6: 0x1804, 7: 0x1806,
             8: 0x180e, 9: 0x180f, 10: 0x1810, 11: 0x1811, 12: 0x1808, 13: 0x1809, 14: 0x180b, 15: 0x180a}


def _pad_glyphs(b):
    return [ord(ch) for ch in b.decode('utf-8', 'replace') if 0x1800 <= ord(ch) <= 0x18ff]


def pad_glyph_names(strings):
    """Rule (Q9, opt-in --pad-glyph-names / subcommand padnames): a PC pad button name (PAD_NAME_FIRST + c) that
    holds no button glyph - in the PC 1.1 tables only Start (c = 10, 5071) and Back (c = 11, 5072), in all six
    languages ('Start Button' / 'START', 'Back Button' / 'BACK', ...) - becomes the one glyph the substitution
    table maps to that pad code, U+1810 / U+1811 (both in the PC font, page 1: the Xbox Start / Back icons).
    The other 14 names are glyphs already (12 equal PAD_GLYPH; L3 / R3 use the plain stick icons U+180C / U+180D)
    and stay. Effect: every UIText prompt with U+1810 / U+1811 shows the icon like the Xbox title update instead of
    the word (DLC 2 banner 5182 / 5201, hint 5287, base 1301); keyboard / mouse names are not touched."""
    st = collections.Counter()
    for c, cp in sorted(PAD_GLYPH.items()):
        i = PAD_NAME_FIRST + c
        if i >= len(strings): st['pad_name_missing'] += 1; continue
        if _pad_glyphs(strings[i]): st['pad_name_glyph_kept'] += 1; continue
        if not strings[i] or strings[i] == b'\x03': st['pad_name_empty_kept'] += 1; continue
        strings[i] = chr(cp).encode('utf-8'); st['pad_name_to_glyph'] += 1
    return st


def pad_names_dir(src, dst):
    """padnames subcommand: pad_glyph_names() on the six tables in src (read only), written to dst. The source
    bytes stay as they are; each changed string is appended at the end and only its offset word is repointed
    (other ids that share the old string keep it). Checks: same count / language, only the rule's ids differ,
    every other offset and every source byte unchanged."""
    os.makedirs(dst, exist_ok=True)
    ok = True
    for sfx in ('001', '002', '004', '008', '016', '032'):
        raw = open(os.path.join(src, 'locals.bin_' + sfx), 'rb').read()
        lang, st, offs = parse(raw, 'le')
        new = list(st); stat = pad_glyph_names(new)
        b = bytearray(raw); offs2 = list(offs)
        for i in range(len(st)):
            if new[i] != st[i]:
                offs2[i] = len(b); b += new[i] + b'\0'
                struct.pack_into('<I', b, 8 + 4 * i, offs2[i])
        b = bytes(b)
        lang2, back, offs3 = parse(b, 'le')
        diff = [i for i in range(len(st)) if back[i] != st[i]]
        moved = [i for i in range(len(st)) if offs3[i] != offs[i]]
        words = {8 + 4 * i + k for i in diff for k in range(4)}   # the repointed offset words
        kept = all(b[k] == raw[k] for k in range(len(raw)) if k not in words)
        ok &= (lang2 == lang and len(back) == len(st) and diff == moved and kept
               and all(PAD_NAME_FIRST <= i < PAD_NAME_FIRST + 16 for i in diff))
        open(os.path.join(dst, 'locals.bin_' + sfx), 'wb').write(b)
        print('locals.bin_%s lang %d n %d changed %s source bytes kept %s %s' % (sfx, lang, len(st), diff, kept, dict(stat)))
    print('padnames: %s' % ('ok' if ok else 'FAIL'))
    return ok


def write_pc(lang, strings, offs_pc):
    """PC layout: index 0 and PC 'missing' ids point at offset 0 (the header) like the shipped PC file."""
    n = len(strings); hdr = 8 + 4 * n
    body = bytearray(); offs = []; seen = {}
    for i, s in enumerate(strings):
        if i == 0 or (i < len(offs_pc) and offs_pc[i] == 0): offs.append(0); continue
        if s in seen: offs.append(seen[s]); continue
        offs.append(hdr + len(body)); seen[s] = offs[-1]; body += s + b'\0'
    return struct.pack('<II', lang, n) + struct.pack('<%dI' % n, *offs) + bytes(body)

files_cache = {}

if __name__ == '__main__':
    import json
    if sys.argv[1:2] == ['padnames']:
        sys.exit(0 if pad_names_dir(sys.argv[2], sys.argv[3]) else 1)
    no_pack_fill = '--no-pack-fill' in sys.argv
    if no_pack_fill: sys.argv.remove('--no-pack-fill')
    pad_names = '--pad-glyph-names' in sys.argv
    if pad_names: sys.argv.remove('--pad-glyph-names')
    srcs = BUILD_SRC if sys.argv[1:2] == ['build'] else SRC
    for k in srcs:
        f, e = files(k)
        if f: files_cache[k] = f
    V = survey(srcs)
    compare(V)
    if sys.argv[1:2] == ['build']:
        out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(B, 'trudlcport/work/generic/locals')
        m, info = build_map(V)
        print('map', info)
        os.makedirs(out, exist_ok=True)
        json.dump({'rule': build_map.__doc__, 'info': info, 'map': {str(k): v for k, v in sorted(m.items())}},
                  open(os.path.join(out, 'locmap_xbox_to_pc.json'), 'w'))
        d = os.path.join(out, 'mods', 'local'); os.makedirs(d, exist_ok=True)
        for spec in SPECS:
            lang, strings, st = merged(V, spec, m)
            if not no_pack_fill: st.update(unfilled_from_packs(V, m, spec, strings))
            st.update(unwrap_descriptions(m, strings))
            if pad_names: st.update(pad_glyph_names(strings))
            offs_pc = parse(files_cache['pcpatch'][spec], 'le')[2]
            b = write_pc(lang, strings, offs_pc)
            back = parse(b, 'le')[1]
            ok = all(back[i] == strings[i] for i in range(len(strings)) if not (i == 0 or (i < len(offs_pc) and offs_pc[i] == 0)))
            # unchanged PC entries must survive
            pcs = V['pcpatch'][spec][1]
            keep = sum(1 for i in range(len(pcs)) if back[i] == pcs[i])
            suffix = (spec & 0x1f) if spec != 0xffffffe0 else 32
            fn = os.path.join(d, 'locals.bin_%03d' % suffix)
            open(fn, 'wb').write(b)
            print('wrote', fn, 'spec %08x lang %d n %d' % (spec, lang, len(strings)), dict(st), 'readback ok', ok, 'PC entries unchanged %d/%d' % (keep, len(pcs)))
