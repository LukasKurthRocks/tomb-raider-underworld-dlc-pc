"""Xbox 360 STFS package (CON / LIVE / PIRS) reader: metadata, file table, block-hash verification, extraction.
Read-only on the package; only writes into the OUT_DIR given to `extract`. Pure data parser (nothing in the package is
executed). Written for the TRU DLC prototype packages (docs/Befund-Prototyp-DLC.md); lets the installer accept a raw
LIVE package instead of a pre-extracted pack10.000 / pack11.000 (scripts/windows/TruDlcPackage.psm1 runs `identify`,
`verify` and `extract`; docs/RELATED_WORK.md, "Accept the raw LIVE package").

Format (Free60 "STFS", Velocity StfsPackage.cpp; all big endian unless noted):
  0x000 magic 'CON ' / 'LIVE' / 'PIRS'; 0x22C 16 license entries (u64 id, u32 bits, u32 flags); 0x32C header SHA-1
  (= content id; SHA-1 of 0x344 .. align4K(header size)); 0x340 header size; 0x344 content type; 0x348 metadata
  version; 0x34C content size (u64); 0x354 media id; 0x358 version; 0x35C base version; 0x360 title id;
  0x379 volume descriptor (0x24 bytes): u8 size, u8 reserved, u8 block separation, u16 LE file-table block count,
  u24 LE file-table first block, 20 bytes top hash-table SHA-1, u32 allocated blocks, u32 unallocated blocks;
  0x39D data file count, 0x3A1 data file size (u64); 0x411 display names (UTF-16BE, 0x100 bytes per locale,
  9 locales en ja de fr es it ko zh pt), 0xD11 descriptions (same layout), 0x1611 publisher, 0x1691 title name, 0x1711 transfer flags, 0x1712 / 0x1716 thumbnail sizes,
  0x171A thumbnail, 0x571A title thumbnail.
  Data area: 0x1000-byte blocks from align4K(header size). Hash tables: every 170 (0xAA) data blocks one level-0
  table (170 entries of 0x18 bytes: SHA-1 of the block, u8 status, u24 next block); every 170 level-0 tables one
  level-1 table, one level-2 table above (top level by allocated block count: <=0xAA -> 0, <=0x70E4 -> 1, else 2);
  the top table's SHA-1 is in the volume descriptor. Block separation bit 0 clear = "male" package: every table has
  two copies, the active one chosen by bit 0x40 of the parent entry (top table: block separation bit 1).
  File table: 0x40-byte entries: name[0x28], u8 flags (0x3F name length, 0x40 consecutive blocks, 0x80 directory),
  u24 LE blocks, u24 LE blocks (copy), u24 LE first block, s16 parent entry (-1 = root), u32 size, u32 update time,
  u32 access time (FAT date/time). Non-consecutive files follow the next-block field of the hash entries.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/stfs_extract.py list PACKAGE [--json OUT.json]
        metadata, licenses, volume descriptor, header-hash check, file table (size, blocks, times)
  ../bin/pyt -t 600 tools/stfs_extract.py verify PACKAGE
        whole hash tree: every hash table against its parent / the top hash, every allocated data block against
        its level-0 entry; mismatches are listed
  ../bin/pyt -t 1800 tools/stfs_extract.py extract PACKAGE OUT_DIR
        writes every file below OUT_DIR (directories kept), verifies each block it reads and the hash tree, writes
        OUT_DIR.manifest.json (metadata, files with size / blocks / times / md5 / sha1, mismatch counts)
  ../bin/pyt -t 300 tools/stfs_extract.py identify PACKAGE [--known LIST.json] [--json OUT.json]
        header only (fast, reads no data blocks besides the file table): magic, title id 534307EC, content type 2,
        header SHA-1 (= content id) against the header bytes and against the file name (an Xbox content file is
        named <content id, 40 hex><2 hex>, e.g. ...E753), truncation check, file table, and the match in the
        known-packages list (default scripts/windows/TruDlcPackages.json): name, role, file names and sizes.
        Exit 0 = known package, all checks passed; 3 = intact TRU package, but not in the list (or its files differ
        from the list); 1 = damaged or foreign (not STFS, other title / content type, header hash wrong, truncated,
        file name contradicts the header).
  ../bin/pyt -t 900 tools/stfs_extract.py catalog OUT.json [NAME=]DIR [[NAME=]DIR ...] [--base LIST.json]
        writes a known-packages list from extracted package folders (NAME defaults to the folder name): per file
        relative path, size, md5, sha1; content id = the first 40 characters of NAME. Roles, display names and
        notes are carried over from --base (matched by name). Hashes and names only - no game bytes, no paths.
Exit code 1 when a hash mismatch was found (extract: also when a file came out short).
"""
import sys, os, struct, hashlib, json, datetime, re

BLK = 0x1000
PER = 0xAA        # entries per hash table
PER1 = 0x70E4     # blocks covered by one level-1 table (170 * 170)
CONTENT_TYPES = {0x1: 'saved game', 0x2: 'marketplace content', 0x3: 'publisher', 0x1000: 'Xbox 360 title',
                 0x2000: 'IPTV pause buffer', 0x4000: 'installed game', 0x5000: 'Xbox original game',
                 0x7000: 'game on demand', 0x9000: 'avatar item', 0x10000: 'profile', 0x20000: 'gamer picture',
                 0x30000: 'theme', 0x40000: 'cache file', 0x50000: 'storage download', 0x60000: 'Xbox saved game',
                 0x70000: 'Xbox download', 0x80000: 'game demo', 0x90000: 'video', 0xA0000: 'game title',
                 0xB0000: 'installer', 0xC0000: 'game trailer', 0xD0000: 'arcade title', 0xE0000: 'XNA',
                 0xF0000: 'license store', 0x100000: 'movie', 0x200000: 'TV', 0x300000: 'music video',
                 0x400000: 'game video', 0x500000: 'podcast video', 0x600000: 'viral video', 0x2000000: 'community game'}
LOCALES = ['en', 'ja', 'de', 'fr', 'es', 'it', 'ko', 'zh', 'pt']   # 0x100 bytes (UTF-16BE) per locale


def u24le(b, o): return b[o] | b[o + 1] << 8 | b[o + 2] << 16


def u24be(b, o): return b[o] << 16 | b[o + 1] << 8 | b[o + 2]


def fat_time(v):
    """FAT date/time word (u32: date high, time low) -> ISO string, '' for 0"""
    if not v: return ''
    y, mo, d = (v >> 25) + 1980, (v >> 21) & 0xF, (v >> 16) & 0x1F
    h, mi, s = (v >> 11) & 0x1F, (v >> 5) & 0x3F, (v & 0x1F) * 2
    return '%04d-%02d-%02d %02d:%02d:%02d' % (y, mo, d, h, mi, s)


def utf16(b):
    s = b.decode('utf-16-be', 'replace')
    return s.split('\0', 1)[0]


class Stfs:
    def __init__(self, path):
        self.path = path
        self.f = open(path, 'rb')
        self.fsize = os.path.getsize(path)
        h = self.f.read(0x971A)
        self.magic = h[:4].decode('latin-1')
        if self.magic not in ('CON ', 'LIVE', 'PIRS'): raise SystemExit('not an STFS package: magic %r' % h[:4])
        self.hdr = h
        g = lambda fmt, o: struct.unpack_from('>' + fmt, h, o)[0]
        self.header_sha1 = h[0x32C:0x340].hex()
        self.header_size = g('I', 0x340)
        self.content_type = g('I', 0x344)
        self.meta_version = g('I', 0x348)
        self.content_size = g('Q', 0x34C)
        self.media_id = g('I', 0x354)
        self.version = g('I', 0x358)
        self.base_version = g('I', 0x35C)
        self.title_id = g('I', 0x360)
        self.platform, self.exe_type, self.disc_no, self.disc_set = h[0x364], h[0x365], h[0x366], h[0x367]
        self.savegame_id = g('I', 0x368)
        self.console_id = h[0x36C:0x371].hex()
        self.profile_id = h[0x371:0x379].hex()
        vd = h[0x379:0x379 + 0x24]
        self.vd_size, self.block_sep = vd[0], vd[2]
        self.ft_count = vd[3] | vd[4] << 8
        self.ft_block = u24le(vd, 5)
        self.top_sha1 = vd[8:0x1C]
        self.alloc = struct.unpack_from('>I', vd, 0x1C)[0]
        self.unalloc = struct.unpack_from('>I', vd, 0x20)[0]
        self.data_file_count = g('I', 0x39D)
        self.data_file_size = g('Q', 0x3A1)
        self.descriptor_type = g('I', 0x3A9)
        self.device_id = h[0x3FD:0x411].hex()
        self.names = [utf16(h[0x411 + 0x100 * i:0x511 + 0x100 * i]) for i in range(9)]
        self.descs = [utf16(h[0xD11 + 0x100 * i:0xE11 + 0x100 * i]) for i in range(9)]
        self.publisher = utf16(h[0x1611:0x1691])
        self.title_name = utf16(h[0x1691:0x1711])
        self.transfer_flags = h[0x1711]
        self.thumb_size = g('I', 0x1712)
        self.title_thumb_size = g('I', 0x1716)
        self.thumb_sha1 = hashlib.sha1(h[0x171A:0x171A + min(self.thumb_size, 0x4000)]).hexdigest()
        self.title_thumb_sha1 = hashlib.sha1(h[0x571A:0x571A + min(self.title_thumb_size, 0x4000)]).hexdigest()
        self.licenses = []
        for i in range(16):
            lid, bits, flags = struct.unpack_from('>QII', h, 0x22C + 16 * i)
            if lid or bits or flags: self.licenses.append((lid, bits, flags))
        self.sex = (~self.block_sep) & 1          # 0 female (one copy per table), 1 male (two copies)
        self.step = (0xAB, 0x718F) if self.sex == 0 else (0xAC, 0x723A)
        self.first = (self.header_size + 0xFFF) & ~0xFFF
        self.top = 0 if self.alloc <= PER else (1 if self.alloc <= PER1 else 2)
        self._tables = {}
        self.mismatch = []

    # --- block geometry (Velocity's formulas) ---
    def backing_data(self, b):
        r = (((b + PER) // PER) << self.sex) + b
        if b < PER: return r
        if b < PER1: return r + (((b + PER1) // PER1) << self.sex)
        return (1 << self.sex) + r + (((b + PER1) // PER1) << self.sex)

    def backing_table(self, level, idx):
        """backing block number of the (first copy of the) hash table of a level and index"""
        if level == 0:
            b = idx * PER
            if b < PER: return 0
            n = (b // PER) * self.step[0] + (((b // PER1) + 1) << self.sex)
            return n if b // PER1 == 0 else n + (1 << self.sex)
        if level == 1:
            b = idx * PER1
            if b < PER1: return self.step[0]
            return (1 << self.sex) + (b // PER1) * self.step[1]
        return self.step[1]

    def addr(self, backing): return self.first + (backing << 12)

    def read_at(self, pos, n):
        self.f.seek(pos)
        d = self.f.read(n)
        return d + b'\0' * (n - len(d))

    def table(self, level, idx):
        """bytes (0x1000) of the active copy of a hash table"""
        k = (level, idx)
        if k in self._tables: return self._tables[k]
        pos = self.addr(self.backing_table(level, idx))
        if self.sex == 1:
            if level == self.top: pos += (self.block_sep & 2) << 0xB
            else:
                st = self.entry(level + 1, idx)[1]
                pos += (st & 0x40) << 6
        t = self.read_at(pos, BLK)
        if len(self._tables) > 4096: self._tables.clear()
        self._tables[k] = t
        return t

    def entry(self, level, idx):
        """hash entry that covers item idx of `level` (level 0: a data block; level 1: a level-0 table; ...)
        -> (sha1 bytes, status, next block)"""
        t = self.table(level, idx // PER)
        o = (idx % PER) * 0x18
        return t[o:o + 0x14], t[o + 0x14], u24be(t, o + 0x15)

    def block(self, b): return self.read_at(self.addr(self.backing_data(b)), BLK)

    # --- verification ---
    def verify_tree(self):
        """every hash table against its parent entry / the top hash; returns (checked, bad list)"""
        bad = []; n = 0
        counts = [(self.alloc + PER - 1) // PER]
        counts.append((counts[0] + PER - 1) // PER)
        counts.append(1)
        top_t = self.table(self.top, 0)
        n += 1
        if hashlib.sha1(top_t).digest() != self.top_sha1: bad.append(('top table level %d' % self.top, 0))
        for level in range(self.top - 1, -1, -1):
            for i in range(counts[level]):
                n += 1
                if hashlib.sha1(self.table(level, i)).digest() != self.entry(level + 1, i)[0]:
                    bad.append(('table level %d' % level, i))
        return n, bad

    def verify_blocks(self, blocks=None):
        """data blocks against their level-0 entries; returns (checked, bad block list, status counts)"""
        bad = []; st = {}
        rng = range(self.alloc) if blocks is None else blocks
        n = 0
        for b in rng:
            sha, s, _ = self.entry(0, b)
            st[s] = st.get(s, 0) + 1
            n += 1
            if hashlib.sha1(self.block(b)).digest() != sha: bad.append(b)
        return n, bad, st

    def header_hash_ok(self):
        end = (self.header_size + 0xFFF) & 0xF000
        if self.header_size > 0xFFFF: end = (self.header_size + 0xFFF) & ~0xFFF
        return hashlib.sha1(self.read_at(0x344, end - 0x344)).hexdigest() == self.header_sha1

    # --- file table ---
    def chain(self, start, count, consecutive):
        if consecutive: return list(range(start, start + count))
        out = []; b = start
        for _ in range(count):
            out.append(b)
            b = self.entry(0, b)[2]
        return out

    def files(self):
        ents2 = []; slot = -1
        for b in self.chain(self.ft_block, self.ft_count, False):
            d = self.block(b)
            for o in range(0, BLK, 0x40):
                slot += 1          # entry index = slot in the table (parents refer to it; empty slots count)
                e = d[o:o + 0x40]
                fl = e[0x28]
                if not fl & 0x3F: continue
                name = e[:fl & 0x3F].decode('latin-1')
                ents2.append(dict(index=slot, name=name, dir=bool(fl & 0x80), consecutive=bool(fl & 0x40),
                                 blocks=u24le(e, 0x29), blocks2=u24le(e, 0x2C), start=u24le(e, 0x2F),
                                 parent=struct.unpack_from('>h', e, 0x32)[0],
                                 size=struct.unpack_from('>I', e, 0x34)[0],
                                 updated=fat_time(struct.unpack_from('>I', e, 0x38)[0]),
                                 accessed=fat_time(struct.unpack_from('>I', e, 0x3C)[0])))
        by = {e['index']: e for e in ents2}
        for e in ents2:
            parts = [e['name']]; p = e['parent']; guard = 0
            while p != -1 and p in by and guard < 64:
                parts.insert(0, by[p]['name']); p = by[p]['parent']; guard += 1
            e['path'] = '/'.join(parts)
        return ents2

    def meta(self):
        return dict(path=os.path.abspath(self.path), file_size=self.fsize, magic=self.magic,
                    header_sha1=self.header_sha1, header_hash_ok=self.header_hash_ok(),
                    header_size=self.header_size, content_type=self.content_type,
                    content_type_name=CONTENT_TYPES.get(self.content_type, '?'), meta_version=self.meta_version,
                    content_size=self.content_size, media_id='%08X' % self.media_id, version=self.version,
                    base_version=self.base_version, title_id='%08X' % self.title_id, platform=self.platform,
                    savegame_id='%08X' % self.savegame_id, console_id=self.console_id, profile_id=self.profile_id,
                    block_separation=self.block_sep, package_sex='female' if self.sex == 0 else 'male',
                    file_table_blocks=self.ft_count, file_table_first=self.ft_block, top_hash=self.top_sha1.hex(),
                    allocated_blocks=self.alloc, unallocated_blocks=self.unalloc, top_level=self.top,
                    data_file_count=self.data_file_count, data_file_size=self.data_file_size,
                    descriptor_type=self.descriptor_type, device_id=self.device_id,
                    display_names={LOCALES[i]: s for i, s in enumerate(self.names) if s},
                    descriptions={LOCALES[i]: s for i, s in enumerate(self.descs) if s},
                    publisher=self.publisher, title_name=self.title_name, transfer_flags=self.transfer_flags,
                    thumbnail=dict(size=self.thumb_size, sha1=self.thumb_sha1),
                    title_thumbnail=dict(size=self.title_thumb_size, sha1=self.title_thumb_sha1),
                    licenses=[dict(id='%016X' % a, bits='%08X' % b, flags='%08X' % c) for a, b, c in self.licenses])


def print_meta(m):
    for k, v in m.items():
        if isinstance(v, dict) and k in ('display_names', 'descriptions'):
            for loc, s in v.items(): print('%-20s %-5s %s' % (k, loc, s))
        else: print('%-20s %s' % (k, v))


def print_files(fs):
    print('%-4s %-48s %12s %7s %7s %-3s %-19s %-19s' % ('idx', 'path', 'size', 'blocks', 'start', 'cns', 'updated',
                                                          'accessed'))
    for e in fs:
        print('%-4d %-48s %12s %7d %7d %-3s %-19s %-19s' % (e['index'], e['path'] + ('/' if e['dir'] else ''),
              '' if e['dir'] else e['size'], e['blocks'], e['start'], 'y' if e['consecutive'] else 'n',
              e['updated'], e['accessed']))


def safe_join(root, rel):
    parts = [p for p in rel.replace('\\', '/').split('/') if p not in ('', '.', '..')]
    parts = [''.join(c if (c.isalnum() or c in '._- ()') else '_' for c in p) for p in parts]
    return os.path.join(root, *parts)


def extract(S, out):
    fs = S.files()
    os.makedirs(out, exist_ok=True)
    bad_blocks = []; checked = 0; recs = []
    for e in fs:
        dst = safe_join(out, e['path'])
        if e['dir']:
            os.makedirs(dst, exist_ok=True); continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        blocks = S.chain(e['start'], e['blocks'], e['consecutive'])
        md5, sha = hashlib.md5(), hashlib.sha1()
        left = e['size']; fbad = []
        with open(dst, 'wb') as o:
            for b in blocks:
                d = S.block(b)
                checked += 1
                if hashlib.sha1(d).digest() != S.entry(0, b)[0]: fbad.append(b)
                part = d[:min(left, BLK)]
                o.write(part); md5.update(part); sha.update(part); left -= len(part)
                if left <= 0: break
        bad_blocks += fbad
        r = dict(e, md5=md5.hexdigest(), sha1=sha.hexdigest(), bad_blocks=len(fbad), short=left > 0)
        recs.append(r)
        print('%-48s %12d  md5 %s  bad blocks %d%s' % (e['path'], e['size'], r['md5'], len(fbad),
                                                       '  SHORT' if left > 0 else ''))
    n_t, bad_t = S.verify_tree()
    print('hash tree: %d tables checked, %d mismatches %s' % (n_t, len(bad_t), bad_t[:10]))
    print('data blocks read and checked: %d, mismatches %d %s' % (checked, len(bad_blocks), bad_blocks[:10]))
    man = dict(meta=S.meta(), files=recs, tables_checked=n_t, table_mismatches=[list(x) for x in bad_t],
               blocks_checked=checked, block_mismatches=bad_blocks,
               extracted=datetime.datetime.now().isoformat(timespec='seconds'), tool='tools/stfs_extract.py')
    mp = os.path.abspath(out).rstrip('\\/') + '.manifest.json'
    json.dump(man, open(mp, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('manifest', mp)
    short = [r['path'] for r in recs if r['short']]
    if short: print('SHORT files (package truncated?): %s' % short)
    return 1 if (bad_blocks or bad_t or short) else 0


# --- identify / catalog (installer: accept raw Xbox LIVE packages) ---
TRU_TITLE_ID = 0x534307EC
MARKETPLACE = 0x2
NAME_RE = re.compile(r'^[0-9A-Fa-f]{42}$')
DEFAULT_KNOWN = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'windows',
                             'TruDlcPackages.json')


def load_known(path):
    if not path or not os.path.isfile(path): return None
    with open(path, 'r', encoding='utf-8-sig') as f: return json.load(f)


def identify(pkg, known_path):
    """header-level identification of one package file -> (exit code, result dict)"""
    res = dict(file=os.path.basename(pkg), file_size=os.path.getsize(pkg), checks=[], problems=[], known=False)
    with open(pkg, 'rb') as f: magic = f.read(4)
    if magic not in (b'CON ', b'LIVE', b'PIRS'):
        res['problems'].append('not an STFS package (magic %r)' % magic)
        return 1, res
    if res['file_size'] < 0xB000:
        res['problems'].append('file too small for an STFS header (%d bytes)' % res['file_size'])
        return 1, res
    S = Stfs(pkg)
    res.update(magic=S.magic, title_id='%08X' % S.title_id, content_type='%08X' % S.content_type,
               content_type_name=CONTENT_TYPES.get(S.content_type, '?'), header_sha1=S.header_sha1,
               display_name=S.names[0], title_name=S.title_name, package_sex='female' if S.sex == 0 else 'male',
               allocated_blocks=S.alloc)
    bad = res['problems']; ok = res['checks']

    def check(cond, good, fail):
        (ok if cond else bad).append(good if cond else fail)
        return cond

    check(S.magic == 'LIVE', 'magic LIVE', 'magic %r (purchased DLC is a LIVE package)' % S.magic)
    check(S.title_id == TRU_TITLE_ID, 'title id 534307EC', 'title id %08X is not Tomb Raider: Underworld' % S.title_id)
    check(S.content_type == MARKETPLACE, 'content type 00000002 (marketplace content)',
          'content type %08X (%s), expected 00000002' % (S.content_type, res['content_type_name']))
    check(S.header_hash_ok(), 'header SHA-1 matches the header bytes',
          'header SHA-1 does not match the header (damaged or modified package)')
    # file name = content id (40 hex) + 2 hex; a file renamed by the user is allowed (the header identifies it)
    base = res['file']
    res['name_is_content_name'] = bool(NAME_RE.match(base))
    res['name_matches_header'] = res['name_is_content_name'] and base[:40].lower() == S.header_sha1
    if res['name_is_content_name']:
        check(res['name_matches_header'], 'file name = content id', 'file name %s does not match the header SHA-1 %s'
              % (base, S.header_sha1))
    else:
        ok.append('file name %r is not a content name (renamed copy?) - identified by the header only' % base)
    last = S.addr(S.backing_data(S.alloc - 1)) + BLK if S.alloc else S.first
    check(S.fsize >= last, 'file size covers all %d allocated blocks' % S.alloc,
          'file is truncated: %d bytes, the last allocated block ends at %d' % (S.fsize, last))
    try:
        files = [dict(path=e['path'], size=e['size']) for e in S.files() if not e['dir']]
    except Exception as ex:                      # a broken file table is a damaged package, not a crash
        files = []
        bad.append('file table unreadable: %s' % ex)
    res['files'] = files
    if bad: return 1, res
    known = load_known(known_path)
    res['known_list'] = os.path.basename(known_path) if known_path else None
    entry = None
    for p in (known or {}).get('packages', []):
        if p.get('content_id', '').lower() == S.header_sha1: entry = p; break
    if entry is None:
        bad.append('intact Tomb Raider: Underworld package, but not in the known-packages list%s'
                   % ('' if known else ' (list not found: %s)' % known_path))
        return 3, res
    res.update(known=True, name=entry['name'], role=entry.get('role'), known_display_name=entry.get('display_name'))
    ok.append('known package %s (%s)' % (entry['name'], entry.get('role')))
    if res['name_is_content_name'] and base.upper() != entry['name'].upper():
        bad.append('file name suffix differs from the known name %s' % entry['name'])
    want = {f['path'].lower(): f['size'] for f in entry.get('files', [])}
    have = {f['path'].lower(): f['size'] for f in files}
    if want != have:
        bad.append('files differ from the list: package %s, list %s' % (sorted(have.items()), sorted(want.items())))
    else:
        ok.append('file names and sizes match the list (%d files)' % len(want))
    return (3 if bad else 0), res


def digest(path):
    m, s = hashlib.md5(), hashlib.sha1()
    with open(path, 'rb') as f:
        while True:
            b = f.read(1 << 22)
            if not b: break
            m.update(b); s.update(b)
    return m.hexdigest(), s.hexdigest()


def catalog(argv):
    out = argv[0]
    base = None
    if '--base' in argv:
        i = argv.index('--base'); base = load_known(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    by_name = {p['name'].upper(): p for p in (base or {}).get('packages', [])}
    pkgs = []
    for spec in argv[1:]:
        name, _, d = spec.partition('=') if '=' in spec else (os.path.basename(os.path.normpath(spec)), '', spec)
        if not NAME_RE.match(name): raise SystemExit('catalog: %r is not a 42-character content name' % name)
        files = []
        for dp, dn, fn in os.walk(d):
            dn.sort()
            for n in sorted(fn):
                q = os.path.join(dp, n)
                md5, sha1 = digest(q)
                files.append(dict(path=os.path.relpath(q, d).replace(os.sep, '/'), size=os.path.getsize(q), md5=md5,
                                  sha1=sha1))
        old = by_name.get(name.upper(), {})
        p = dict(name=name.upper(), content_id=name[:40].lower(), role=old.get('role', 'unknown'),
                 display_name=old.get('display_name', ''))
        for k, v in old.items():
            if k not in p and k != 'files': p[k] = v
        p['files'] = files
        pkgs.append(p)
        print('%s  %-18s %d files  %s' % (p['name'], p['role'], len(files),
                                          ', '.join('%s %d %s' % (f['path'], f['size'], f['md5']) for f in files)))
    doc = {k: v for k, v in (base or {}).items() if k != 'packages'}
    doc.setdefault('schema', 1)
    doc.setdefault('title_id', '534307EC')
    doc.setdefault('content_type', '00000002')
    doc['packages'] = pkgs
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(doc, indent=1, ensure_ascii=True) + '\n')
    print('wrote', out, '(%d packages)' % len(pkgs))
    return 0


def main(argv):
    if len(argv) < 2: print(__doc__); return 2
    cmd, pkg = argv[0], argv[1]
    if cmd == 'catalog': return catalog(argv[1:])
    if cmd == 'identify':
        kp = argv[argv.index('--known') + 1] if '--known' in argv else os.path.normpath(DEFAULT_KNOWN)
        code, res = identify(pkg, kp)
        res['exit_code'] = code
        for k in ('file', 'file_size', 'magic', 'title_id', 'content_type', 'header_sha1', 'display_name', 'name',
                  'role'):
            if k in res: print('%-14s %s' % (k, res[k]))
        for f in res.get('files', []): print('%-14s %s %d' % ('file entry', f['path'], f['size']))
        for c in res['checks']: print('ok             %s' % c)
        for c in res['problems']: print('PROBLEM        %s' % c)
        print('result         %s' % {0: 'known package, OK', 1: 'damaged or foreign package',
                                     3: 'not a known package'}[code])
        if '--json' in argv:
            jp = argv[argv.index('--json') + 1]
            with open(jp, 'w', encoding='utf-8', newline='\n') as f: f.write(json.dumps(res, indent=1) + '\n')
        return code
    S = Stfs(pkg)
    if cmd == 'list':
        m = S.meta(); fs = S.files()
        print_meta(m); print(); print_files(fs)
        if '--json' in argv:
            json.dump(dict(meta=m, files=fs), open(argv[argv.index('--json') + 1], 'w', encoding='utf-8'), indent=1,
                      ensure_ascii=False)
        return 0
    if cmd == 'verify':
        n_t, bad_t = S.verify_tree()
        print('hash tree: %d tables checked, %d mismatches %s' % (n_t, len(bad_t), bad_t[:20]))
        n, bad, st = S.verify_blocks()
        print('data blocks: %d checked, %d mismatches %s; status counts %s' % (
            n, len(bad), bad[:20], {'%02X' % k: v for k, v in sorted(st.items())}))
        print('header hash ok: %s' % S.header_hash_ok())
        return 1 if (bad or bad_t) else 0
    if cmd == 'extract':
        return extract(S, argv[2])
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
