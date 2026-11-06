"""Decode and diff Tomb Raider: Underworld PC save files (*.TRUSave) - story state, sticky script values (read-only).

2026-11-06 save sticky values (workspace docs\\Befund-Saves-Sticky-0611.md): which "sticky" script values (stickybool /
stickyint / stickyfloat members of level scripts, e.g. IsLevelZeroDone = Symbol 10814 on dispatcher intro 4086 in
l3_main_hall) are stored where in a .TRUSave, so two saves can be compared by name. Never writes to any save.

File container (CRCs): tools/trusave_info.py (RGMH header, PCUD/SURT table, CRC-32/BZIP2). The single data entry
(0x140000 bytes) is the engine's SaveInfo object, copied as a whole (layout proven in tru.exe, Steam, base 0x400000):
  0x000000  block arena: blocks {u32 head = savedID (low byte, 1..6, check 0x556319) | (size >> 2) << 8 (0x5563b7);
            payload}; allocator SAVE_GetSavedBlock 0x556310, the used end is the offset at +0x1357f4.
            savedID 6 = the game block (0x41028 bytes, always first; [0xc59264] = it, created 0x556972/0x55698b),
            1 = saved unit (+4 unit key, 0x55659d), 2 = instance extra data (+8 intro unique id, 0x5566da),
            3 = instance with spline / extra (+0x14 unique id, 0x5553ce), 4 = saved instance (+0x14 unique id,
            0x555498), 5 = small instance (+8 unique id, 0x556875).
  0x1357f4  u32 used end of the arena (offset, 0x5557fd / 0x55635a / 0x5563c0)
  0x1357f8  dead-dead bits, 0x7fc bytes, bit = intro unique id (byte id >> 3, bit id & 7; set 0x5559a0 / test
            0x555a10 / mark from instance +0x58 0x555a80)
  sticky store (SAVE_Stickies 0x555820 copies, SAVE_RestoreStickies 0x5558a0 restores; StickyManager [0xa13f18],
  created 0x4b1440: [+0] int storage 0x200 entries, [+4] bool storage 0x1000 entries, [+8] float storage 0x80):
  0x135ff4  bool bits 0x200 bytes (memcpy 0x4ab040; bit = index: byte >> 3, bit & 7, read 0x4b08a0 / 0x7b35a0)
  0x1361f4  bool ids   u32 count + count x {u32 id, u16 key Symbol, u8 kind, u8 0} (CopyIDs 0x4abfd0, 0x4ad530)
  0x13e1f8  int values 0x200 x s32 (0x4ad560)
  0x13e9f8  int ids    (0x4ad540)
  0x13f9fc  float values 0x80 x f32 (0x4ad580)
  0x13fbfc  float ids  (0x4ad550)
  The value of the k-th id is entry k of its storage (StickyFinder::Find 0x4aee30 returns the index; new ids are
  appended). id / kind (sticky owner, 0x7b3450): kind 0 = the instance's intro unique id (instance +0x20 -> +0x58),
  kind 1 = the unit's id (unit script), kind 2 = a global script object: u16 script name Symbol (script header +8)
  | u16 header +0x4e << 16. The key Symbol is the first word of the sticky member's init block in the script data
  (e.g. generalbank script 5 member +16 (stickyint) -> key 195).
Game block (offsets from its start = data offset 0; 0x555be0 checkpoint save, 0x556f38.. restore):
  +0x08 u16 flags (0x2 set 0x555d2f, 0x4 set 0x556270 at a chapter end, 0x40 set 0x5562ba with all chapters
  unlocked), +0x0a u16 version 0xc2c (0x555be5), +0x10 char[0x84] unit name + checkpoint (0x21 dwords copied 0x555c20;
  +0x90 checkpoint id), +0x19c u32 [0xe7f154], +0x1a0 u32 play time (0x555eb8, microsecond counter / 1e6 - unit
  inferred), +0x1f2 s16 current chapter (SAVE_GetCurrentChapter 0x555bd0), +0x20c u16 costume object id
  ([0xe7f1c8], 0x555cb1 / load 0x556fbd), chapter table +0x424 + 20 * n, n < 0x12: +0 u8 chapter done (0x5561f3),
  +2 u8 done with game value 0x22 condition (0x55623a), +4 u32 chapter start time, +0xc u32 chapter time (0x555edf).

Names: give unit / bank DRMs with --drm (repeatable, or a folder) to name stickies: kind 0 -> the intro (unit, object,
per-instance script) and the member that declares the key; kind 2 -> the script whose name Symbol matches. A few
names proven elsewhere are built in (KNOWN).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/trusave_diff.py show SAVE [--drm DRM_OR_DIR ...] [--all]
  ../bin/pyt -t 600 tools/trusave_diff.py diff OLD NEW [--drm DRM_OR_DIR ...] [--max N]
  ../bin/pyt -t 600 tools/trusave_diff.py get SAVE KIND ID KEY      one sticky (KIND 0/1/2, ID / KEY decimal or 0x)
  show --all prints every sticky (default: the named ones + a count); diff prints changed known values by name and
  the unknown changed byte ranges (game block byte diff, arena blocks matched by (savedID, unique id)).
Exit code: 0 = done, 1 = a CRC mismatch was found, 2 = usage error.
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trusave_info as TI

DATA_SIZE = 0x140000
GAME_BLOCK_SIZE = 0x41028
ARENA_END = 0x1357f4
DEAD_BITS, DEAD_LEN = 0x1357f8, 0x7fc
STORES = {  # type: (ids offset, values offset, max entries)
    'bool': (0x1361f4, 0x135ff4, 0x1000),
    'int': (0x13e9f8, 0x13e1f8, 0x200),
    'float': (0x13fbfc, 0x13f9fc, 0x80),
}
BLOCK_NAMES = {1: 'unit', 2: 'instance extra', 3: 'instance spline', 4: 'instance', 5: 'small instance', 6: 'game'}
BLOCK_UID = {2: 8, 3: 0x14, 4: 0x14, 5: 8, 1: 4}  # offset of the key word (unique id / unit key)
CHAPTERS, CHAPTER_TABLE, CHAPTER_STRIDE = 0x12, 0x424, 20
# known names: (kind, id or None = any, key Symbol) -> text; sources in docs\\Befund-Manor-Prolog-0611.md /
# docs\\Befund-Saves-Sticky-0611.md
KNOWN = {
    (0, 4086, 10814): 'l3_main_hall dispatcher 4086 IsLevelZeroDone (cheat text of level script 11544)',
    (0, 4086, 10817): 'l3_main_hall dispatcher 4086 IsL3_Reset_OK (text of setter script 12374)',
    (0, None, 5968): 'cinematic "already played" (base script 3523 stickyint +64; saves show 0 = not played, '
                     '1 = played)',
    (2, 0x012500ba, 195): 'GameGlobals (generalbank script 5) +16 "reached level" stickyint (printed as "GameGlobals reached '
                          'level = "; raised to 1 by the l1_seatop cine 997, 3 by l3_caverns_start cine 4318, 4 by '
                          'l4_trailstart cine 5484; <= 0 -> prologue "level 0")',
    (2, 0x012500ba, 216): 'GameGlobals +328 stickyint (raised with reached level: 15 by cine 4318, 21 by cine 5484; '
                          'meaning inferred: finer progress counter)',
}
GAME_FIELDS = [  # (offset, size, name) - read / written in tru.exe as cited in the header
    (0x08, 2, 'flags'), (0x0a, 2, 'version'), (0x90, 4, 'checkpoint id'), (0x19c, 4, '+0x19c ([0xe7f154])'),
    (0x1a0, 4, 'play time (s, inferred unit)'), (0x1f2, 2, 'current chapter'), (0x20c, 2, 'costume object id'),
    (0x218, 4, '+0x218 (init 0x40000000 at 0x5569e4; runtime id counter?)'),
]


def u32(b, o): return struct.unpack_from('<I', b, o)[0]


def cstr(b, o, n):
    return b[o:o + n].split(b'\0', 1)[0].decode('latin-1')


class Save:
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        d = open(path, 'rb').read()
        self.problems = []
        o = struct.unpack_from('<I', d, 8)[0] if d[:4] == b'RGMH' else 0
        if d[o:o + 4] != b'PCUD':
            raise SystemExit('%s: no PCUD container' % path)
        count, tcrc, hcrc = struct.unpack_from('<III', d, o + 0x10)
        if TI.crc(d[o:o + 0x18]) != hcrc: self.problems.append('header CRC')
        t = o + 0x1c
        if TI.crc(d[t:t + 12 * count]) != tcrc: self.problems.append('table CRC')
        self.entries = []
        for k in range(count):
            size, off, dcrc = struct.unpack_from('<III', d, t + 12 * k)
            if off + size > len(d) or TI.crc(d[off:off + size]) != dcrc: self.problems.append('data CRC entry %d' % k)
            self.entries.append((off, size))
        if count != 1 or self.entries[0][1] != DATA_SIZE:
            raise SystemExit('%s: expected one data entry of 0x%x bytes' % (path, DATA_SIZE))
        off, size = self.entries[0]
        self.b = d[off:off + size]
        self.blocks = self._blocks()
        self.stickies = self._stickies()
        self.dead = self._dead()

    def _blocks(self):
        b = self.b
        end = u32(b, ARENA_END)
        out, o = [], 0
        while o < end:
            h = u32(b, o)
            sid, size = h & 0xff, (h >> 8) * 4
            if sid < 1 or sid > 6 or size < 4 or o + size > end:
                self.problems.append('arena walk stopped at 0x%x (head 0x%08x)' % (o, h))
                break
            key = u32(b, o + BLOCK_UID[sid]) if sid in BLOCK_UID and size >= BLOCK_UID[sid] + 4 else None
            out.append((o, sid, size, key))
            o += size
        if o != end: self.problems.append('arena ends at 0x%x, used end says 0x%x' % (o, end))
        if not out or out[0][1] != 6 or out[0][2] != GAME_BLOCK_SIZE:
            self.problems.append('first block is not the game block (savedID 6, 0x%x bytes)' % GAME_BLOCK_SIZE)
        return out

    def _stickies(self):
        """{(type, kind, id, key): (index, value)}"""
        b, out = self.b, {}
        for typ, (ids, vals, mx) in STORES.items():
            n = u32(b, ids)
            if n > mx:
                self.problems.append('%s sticky count %d > %d' % (typ, n, mx))
                continue
            for k in range(n):
                sid, key, kind, pad = struct.unpack_from('<IHBB', b, ids + 4 + 8 * k)
                if typ == 'bool':
                    v = (b[vals + (k >> 3)] >> (k & 7)) & 1
                elif typ == 'int':
                    v = struct.unpack_from('<i', b, vals + 4 * k)[0]
                else:
                    v = struct.unpack_from('<f', b, vals + 4 * k)[0]
                if (typ, kind, sid, key) in out: self.problems.append('duplicate %s sticky %d/%d/%d' % (typ, kind, sid, key))
                out[(typ, kind, sid, key)] = (k, v)
        return out

    def _dead(self):
        b, out = self.b, set()
        for i in range(DEAD_LEN):
            c = b[DEAD_BITS + i]
            if c:
                for bit in range(8):
                    if c >> bit & 1: out.add(i * 8 + bit)
        return out

    def game(self):
        b = self.b
        g = {'unit': cstr(b, 0x10, 0x80)}
        for o, n, nm in GAME_FIELDS:
            g[nm] = struct.unpack_from('<H' if n == 2 else '<I', b, o)[0]
        g['current chapter'] = struct.unpack_from('<h', b, 0x1f2)[0]
        ch = []
        for n in range(CHAPTERS):
            o = CHAPTER_TABLE + CHAPTER_STRIDE * n
            ch.append((b[o], b[o + 2], u32(b, o + 4), u32(b, o + 0xc)))
        g['chapters'] = ch
        return g

    def known_ranges(self):
        """byte ranges of the data entry that are decoded (excluded from the unknown-bytes diff)"""
        r = [(0x10, 0x94)] + [(o, o + n) for o, n, _ in GAME_FIELDS]
        r += [(CHAPTER_TABLE + CHAPTER_STRIDE * n, CHAPTER_TABLE + CHAPTER_STRIDE * n + 16) for n in range(CHAPTERS)]
        r += [(ARENA_END, ARENA_END + 4), (DEAD_BITS, DEAD_BITS + DEAD_LEN)]
        for typ, (ids, vals, mx) in STORES.items():
            r += [(ids, ids + 4 + 8 * mx), (vals, vals + (mx // 8 if typ == 'bool' else 4 * mx))]
        return r


# ---------------------------------------------------------------- names from DRMs

class Names:
    def __init__(self, paths):
        self.objects = {}
        self.intro = {}    # uid -> (unit, object name, script id)
        self.member = {}   # key Symbol -> [(drm, script id, member offset, type name)]
        self.script_by_name = {}  # (name Symbol, header +0x4e) -> (drm, script id)
        self.unit_names = {}
        if not paths: return
        import manor_gate_scan as MG
        import unit_debug_map as UDM
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        nm = os.path.join(here, 'work', 'generic', 'lists', 'pc_objectlist.txt')
        self.objects = MG.load_names(nm) if os.path.isfile(nm) else {}
        files = []
        for p in paths:
            if os.path.isdir(p):
                for root, _, fs in os.walk(p):
                    files += [os.path.join(root, f) for f in sorted(fs) if f.lower().endswith('.drm')]
            else:
                files.append(p)
        types = {}
        loaded = []
        for f in files:
            try:
                U = UDM.Unit(f)
            except Exception as e:  # not a readable DRM
                print('  names: skipped %s (%s)' % (f, e))
                continue
            loaded.append((f, U))
            import menu_dlc_probe as P
            for s in U.D.sections:
                if s.type == 8 and s.data and len(s.data) >= 0x50:
                    pkg, nat, size = P.script_info({'data': bytes(s.data), 'reloc': bytes(s.reloc)}, 'le')
                    if nat in ('stickybool', 'stickyint', 'stickyfloat'): types[s.id] = nat
        for f, U in loaded:
            base = os.path.basename(f).rsplit('.', 1)[0]
            if U.L is not None:
                try:
                    us = MG.UnitScan(f, self.objects)
                    for it in us.intros:
                        self.intro.setdefault(it['uid'], (base, it.get('name') or str(it.get('obj')), it['script']))
                except Exception as e:
                    print('  names: intros of %s not read (%s)' % (f, e))
            for si, s in enumerate(U.D.sections):
                if s.type != 8 or not s.data or len(s.data) < 0x50: continue
                d = bytes(s.data)
                nsym, hi = struct.unpack_from('<H', d, 8)[0], struct.unpack_from('<H', d, 0x4e)[0]
                self.script_by_name.setdefault((nsym, hi), (base, s.id))
                try:
                    sc = MG.Script(U, si)
                except Exception:
                    continue
                for t, n, sz in sc.arrays('members'):
                    for k in range(n):
                        a = t + k * sz
                        typ = sc.u32(a + 8) if (a + 8) in sc.ids else None
                        if typ not in types: continue
                        ini = sc.it.get(a + 16)
                        if ini is None or ini not in sc.it: continue
                        key = sc.u32(sc.it[ini])
                        off = struct.unpack_from('<H', d, a + 12)[0]
                        lst = self.member.setdefault(key, [])
                        if (base, s.id, off) not in [(x[0], x[1], x[2]) for x in lst]:
                            lst.append((base, s.id, off, types[typ]))
        print('  names: %d DRM(s), %d intros, %d sticky member keys, %d scripts' % (
            len(loaded), len(self.intro), len(self.member), len(self.script_by_name)))

    def label(self, kind, sid, key):
        parts = []
        k = KNOWN.get((kind, sid, key)) or KNOWN.get((kind, None, key))
        if k: parts.append(k)
        if kind == 0:
            it = self.intro.get(sid)
            if it: parts.append('intro %d = %s:%s (script %s)' % (sid, it[0], it[1], it[2]))
        elif kind == 2:
            sc = self.script_by_name.get((sid & 0xffff, sid >> 16))
            if sc: parts.append('global object of script %s:%d' % sc)
        m = self.member.get(key)
        if m:
            seen = {}
            for drm_, sid_, off, typ in m:
                seen.setdefault((sid_, off, typ), drm_)
            parts.append('declared ' + ', '.join('script %d +%d %s (%s)' % (k[0], k[1], k[2], v)
                                                 for k, v in list(seen.items())[:2]) + (' ...' if len(seen) > 2 else ''))
        return '; '.join(parts)


def owner(kind, sid):
    if kind == 2: return 'kind 2 script 0x%04x/0x%04x' % (sid & 0xffff, sid >> 16)
    if kind == 1: return 'kind 1 unit %d' % sid
    return 'kind %d intro %s' % (kind, uid_text(sid))


def uid_text(v):
    """intro unique ids are < 0x40000000 (dead-dead bits refuse larger ones, 0x5559a5); larger = runtime-made id"""
    if v is None: return '-'
    return str(v) if v < 0x40000000 else 'runtime 0x%08x' % v


OBJECTS = {}


def object_name(oid):
    if not OBJECTS:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        p = os.path.join(here, 'work', 'generic', 'lists', 'pc_objectlist.txt')
        if os.path.isfile(p):
            for l in open(p, encoding='utf8', errors='ignore'):
                q = l.strip().split(',', 1)
                if len(q) == 2 and q[0].isdigit(): OBJECTS[int(q[0])] = q[1]
        OBJECTS.setdefault(-1, '')
    return OBJECTS.get(oid, '?')


def fmt_val(typ, v):
    return ('%.4g' % v) if typ == 'float' else str(v)


# ---------------------------------------------------------------- commands

def header_lines(s):
    g = s.game()
    out = ['== %s' % s.name,
           '  CRCs: %s' % ('ok' if not [p for p in s.problems if 'CRC' in p] else ', '.join(s.problems)),
           '  game block: unit %r, checkpoint %d, chapter %d, version 0x%x, flags 0x%x, costume object %d (%s), '
           'play time %d, +0x19c %d' % (g['unit'], g['checkpoint id'], g['current chapter'], g['version'], g['flags'],
                                        g['costume object id'], object_name(g['costume object id']),
                                        g['play time (s, inferred unit)'], g['+0x19c ([0xe7f154])'])]
    done = [n for n, c in enumerate(g['chapters']) if c[0]]
    out.append('  chapter table: done %s; chapter times %s' % (done or '-', ', '.join(
        '%d:%d' % (n, c[3]) for n, c in enumerate(g['chapters']) if c[3]) or '-'))
    cnt = {}
    for o, sid, size, key in s.blocks:
        cnt[sid] = cnt.get(sid, 0) + 1
    out.append('  arena: %d blocks, used end 0x%x (%s)' % (len(s.blocks), u32(s.b, ARENA_END), ', '.join(
        '%d %s x%d' % (k, BLOCK_NAMES[k], v) for k, v in sorted(cnt.items()))))
    per = {}
    for (typ, kind, sid, key) in s.stickies: per[typ] = per.get(typ, 0) + 1
    out.append('  stickies: %s; dead-dead ids: %d' % (', '.join('%s %d' % kv for kv in sorted(per.items())), len(s.dead)))
    other = [p for p in s.problems if 'CRC' not in p]
    if other: out.append('  PROBLEMS: ' + '; '.join(other))
    return out


def cmd_show(path, names, every):
    s = Save(path)
    print('\n'.join(header_lines(s)))
    shown = 0
    for (typ, kind, sid, key), (k, v) in sorted(s.stickies.items(), key=lambda kv: (kv[0][0], kv[1][0])):
        lab = names.label(kind, sid, key)
        known = KNOWN.get((kind, sid, key)) or KNOWN.get((kind, None, key))
        if every or known:
            print('  %-5s #%-4d %-34s key %5d = %-6s %s' % (typ, k, owner(kind, sid), key, fmt_val(typ, v), lab))
            shown += 1
    if not every: print('  (%d named stickies shown; --all for all %d)' % (shown, len(s.stickies)))
    return 1 if [p for p in s.problems if 'CRC' in p] else 0


def ranges(a, b, lo, hi, skip, gap=8):
    out, i = [], lo
    mask = bytearray(hi - lo)
    for x, y in skip:
        for j in range(max(x, lo), min(y, hi)): mask[j - lo] = 1
    while i < hi:
        if a[i] == b[i] or mask[i - lo]:
            i += 1; continue
        s0 = last = i
        while i < hi and i - last <= gap:
            if a[i] != b[i] and not mask[i - lo]: last = i
            i += 1
        out.append((s0, last + 1))
    return out


def cmd_diff(pa, pb, names, mx):
    A, B = Save(pa), Save(pb)
    for s in (A, B): print('\n'.join(header_lines(s)))
    rc = 1 if [p for s in (A, B) for p in s.problems if 'CRC' in p] else 0
    print('== diff %s -> %s' % (A.name, B.name))
    ga, gb = A.game(), B.game()
    for k in ['unit'] + [n for _, _, n in GAME_FIELDS]:
        if ga[k] != gb[k]: print('  game %-28s %r -> %r' % (k, ga[k], gb[k]))
    for n in range(CHAPTERS):
        if ga['chapters'][n] != gb['chapters'][n]:
            print('  chapter %2d (done, done2, start, time) %s -> %s' % (n, ga['chapters'][n], gb['chapters'][n]))
    # stickies
    keys = sorted(set(A.stickies) | set(B.stickies), key=lambda t: (t[0], t[1], t[2], t[3]))
    ch, new, gone = [], [], []
    for t in keys:
        va, vb = A.stickies.get(t), B.stickies.get(t)
        if va and vb and va[1] != vb[1]: ch.append((t, va[1], vb[1]))
        elif vb and not va: new.append((t, vb[1]))
        elif va and not vb: gone.append((t, va[1]))
    same_order = all(A.stickies[t][0] == B.stickies[t][0] for t in keys if t in A.stickies and t in B.stickies)
    print('  stickies: %d changed, %d only in new, %d only in old (common ids keep their index: %s)' % (
        len(ch), len(new), len(gone), 'yes' if same_order else 'no'))
    for (typ, kind, sid, key), x, y in ch:
        print('    CHANGED %-5s %-34s key %5d  %s -> %s  %s' % (typ, owner(kind, sid), key, fmt_val(typ, x),
                                                                 fmt_val(typ, y), names.label(kind, sid, key)))
    for (typ, kind, sid, key), y in new[:mx]:
        print('    NEW     %-5s %-34s key %5d  = %s  %s' % (typ, owner(kind, sid), key, fmt_val(typ, y),
                                                            names.label(kind, sid, key)))
    if len(new) > mx: print('    ... %d more new' % (len(new) - mx))
    for (typ, kind, sid, key), x in gone[:mx]:
        print('    GONE    %-5s %-34s key %5d  was %s  %s' % (typ, owner(kind, sid), key, fmt_val(typ, x),
                                                              names.label(kind, sid, key)))
    if len(gone) > mx: print('    ... %d more gone' % (len(gone) - mx))
    # dead-dead
    add, rem = sorted(B.dead - A.dead), sorted(A.dead - B.dead)
    print('  dead-dead ids: +%d -%d %s%s' % (len(add), len(rem), ' '.join('+%d' % x for x in add[:mx]),
                                           ' ' + ' '.join('-%d' % x for x in rem[:mx]) if rem else ''))
    # arena blocks matched by (savedID, key)
    def bmap(s):
        m = {}
        for o, sid, size, key in s.blocks[1:]:
            m.setdefault((sid, key), []).append((o, size))
        return m
    ma, mb = bmap(A), bmap(B)
    only_a = sorted(k for k in ma if k not in mb)
    only_b = sorted(k for k in mb if k not in ma)
    chg = []
    for k in sorted(set(ma) & set(mb)):
        for (oa, sa), (ob, sb) in zip(ma[k], mb[k]):
            if sa != sb or A.b[oa:oa + sa] != B.b[ob:ob + sb]: chg.append((k, oa, sa, ob, sb))
    print('  arena blocks: %d only in old, %d only in new, %d changed (matched by savedID + unique id)' % (
        len(only_a), len(only_b), len(chg)))
    def short(keys):
        return ' '.join('%s:%s' % (BLOCK_NAMES[sid].split()[-1] if sid != 3 else 'spline', uid_text(key))
                        for sid, key in keys)
    if only_a: print('    old only: %s%s' % (short(only_a[:mx]), ' ...' if len(only_a) > mx else ''))
    if only_b: print('    new only: %s%s' % (short(only_b[:mx]), ' ...' if len(only_b) > mx else ''))
    for (sid, key), oa, sa, ob, sb in chg[:mx]:
        rs = ranges(A.b[oa:oa + sa], B.b[ob:ob + sb], 0, min(sa, sb), [])
        print('    changed %s %s: size 0x%x -> 0x%x, block offsets %s' % (BLOCK_NAMES[sid], uid_text(key), sa, sb, ', '.join(
            '+0x%x..+0x%x' % r for r in rs[:6]) + (' ...' if len(rs) > 6 else '')))
    # unknown bytes: game block + the fixed tail outside the decoded structures
    skip = A.known_ranges()
    rs = ranges(A.b, B.b, 0, GAME_BLOCK_SIZE, skip) + ranges(A.b, B.b, ARENA_END, DATA_SIZE, skip)
    print('  unknown changed byte ranges in the game block / tail: %d' % len(rs))
    for x, y in rs[:mx]:
        print('    0x%06x..0x%06x (%d B)  old %s  new %s' % (x, y, y - x, A.b[x:min(y, x + 12)].hex(),
                                                            B.b[x:min(y, x + 12)].hex()))
    if len(rs) > mx: print('    ... %d more' % (len(rs) - mx))
    return rc


def cmd_get(path, kind, sid, key):
    s = Save(path)
    hit = [(t, v) for t, v in s.stickies.items() if t[1:] == (kind, sid, key)]
    if not hit: print('%s: no sticky kind %d id %d key %d (never set / created in this save)' % (s.name, kind, sid, key))
    for (typ, k_, i_, y_), (k, v) in hit:
        print('%s: %s #%d %s key %d = %s' % (s.name, typ, k, owner(kind, sid), key, fmt_val(typ, v)))
    return 0


def main(argv):
    argv = list(argv)
    drms = []
    while '--drm' in argv:
        i = argv.index('--drm'); drms.append(argv[i + 1]); del argv[i:i + 2]
    every = '--all' in argv
    if every: argv.remove('--all')
    mx = 40
    if '--max' in argv:
        i = argv.index('--max'); mx = int(argv[i + 1]); del argv[i:i + 2]
    if len(argv) < 2:
        print(__doc__); return 2
    cmd = argv[0]
    if cmd == 'get' and len(argv) == 5:
        return cmd_get(argv[1], int(argv[2], 0), int(argv[3], 0), int(argv[4], 0))
    names = Names(drms)
    if cmd == 'show' and len(argv) == 2: return cmd_show(argv[1], names, every)
    if cmd == 'diff' and len(argv) == 3: return cmd_diff(argv[1], argv[2], names, mx)
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
