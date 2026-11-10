"""Read-only InstallShield v5+ cabinet reader (data1.hdr + dataN.cab), 64-bit offsets.

Written for this project because unshield 1.4 reads the file offsets of IS 12+ cabinets as 32-bit values and
silently fails on everything stored beyond 4 GB in a volume. Never writes into the cabinet folder; output only
goes to --out.

Format (as used by IS 12+, header version word 0x0200xxxx / 0x0400xxxx with xxxx/100 >= 6):
  common header (20 bytes): 'ISc(' | u32 version | u32 volume info | u32 cab descriptor offset | u32 size
  cab descriptor: +0x0c u32 file table offset, +0x14 u32 file table size, +0x18 u32 size2,
                  +0x1c u32 directory count, +0x28 u32 file count, +0x2c u32 file table offset2
  file table (at cab descriptor + file table offset): u32 name offset per directory
  file descriptor (0x57 bytes, at cab descriptor + file table offset + offset2 + index * 0x57):
      u16 flags | u64 expanded size | u64 compressed size | u64 data offset | md5[16] | 16 unknown |
      u32 name offset | u16 directory index | 12 unknown | u32 link prev | u32 link next | u8 link flags |
      u16 volume
  flags: 1 split, 2 obfuscated, 4 compressed, 8 invalid
  volume header (dataN.cab, after the 20-byte common header):
      u32 data offset | u32 unknown | u32 first file index | u32 last file index |
      6 x (u32 low, u32 high): first file offset / expanded / compressed, last file offset / expanded / compressed
  compressed data: a series of u16 chunk length + raw-deflate chunk (each chunk inflates on its own).
  entries with data offset 0 (setup.exe, setup.inx, ...) are support files next to the cabinet, not in it.

usage:
  is_cab_extract.py HDR --list
  is_cab_extract.py HDR --verify [NAME|INDEX ...]          (all files when none given; md5 + sha256, nothing written)
  is_cab_extract.py HDR --extract NAME|INDEX ... --out DIR [--strip N] [--force]
  e.g. is_cab_extract.py cab/data1.hdr --extract "Movies\\intro.bik" 12 --out out
NAME matches the full path (dir\\name, case-insensitive) or a bare file name when that is unique.
"""
import argparse, hashlib, os, re, struct, sys, time, zlib

FILE_SPLIT, FILE_OBFUSCATED, FILE_COMPRESSED, FILE_INVALID = 1, 2, 4, 8
SIG = b'ISc('


def cstr(buf, off):
    end = buf.index(b'\0', off)
    return buf[off:end].decode('cp1252', 'replace')


def major_version(ver):
    if ver >> 24 == 1:
        return (ver >> 12) & 0xf
    if ver >> 24 in (2, 4):
        m = ver & 0xffff
        return m // 100 if m else 0
    return 0


class Header:
    def __init__(self, hdr_path):
        self.hdr_path = hdr_path
        with open(hdr_path, 'rb') as f:
            self.data = f.read()
        d = self.data
        sig, self.version, self.volume_info, self.cd_off, self.cd_size = struct.unpack_from('<4s4I', d, 0)
        if sig != SIG:
            raise SystemExit(f'not an InstallShield header (signature {sig!r})')
        self.major = major_version(self.version)
        if self.major < 6:
            raise SystemExit(f'header major version {self.major} (0x{self.version:08x}): only v6+ descriptors supported')
        p = self.cd_off
        self.ft_off, = struct.unpack_from('<I', d, p + 0x0c)
        self.ft_size, self.ft_size2, self.dir_count = struct.unpack_from('<3I', d, p + 0x14)
        self.file_count, self.ft_off2 = struct.unpack_from('<2I', d, p + 0x28)
        base = self.cd_off + self.ft_off
        self.file_table = struct.unpack_from(f'<{self.dir_count}I', d, base)
        self.dirs = [cstr(d, base + o) for o in self.file_table]
        self.files = [self._fd(i) for i in range(self.file_count)]

    def _fd(self, i):
        d = self.data
        base = self.cd_off + self.ft_off
        p = base + self.ft_off2 + i * 0x57
        flags, exp, comp, doff = struct.unpack_from('<HQQQ', d, p)
        md5 = d[p + 26:p + 42]
        name_off, dir_idx = struct.unpack_from('<IH', d, p + 58)
        link_prev, link_next, link_flags, volume = struct.unpack_from('<IIBH', d, p + 76)
        name = cstr(d, base + name_off) if name_off else ''
        dname = self.dirs[dir_idx] if dir_idx < len(self.dirs) else f'?dir{dir_idx}'
        path = f'{dname}\\{name}' if dname else name
        return dict(index=i, flags=flags, expanded=exp, compressed=comp, offset=doff, md5=md5,
                    name=name, dir=dname, path=path, volume=volume, link_flags=link_flags,
                    link_prev=link_prev, link_next=link_next)

    def volume_path(self, n):
        stem = re.sub(r'\d+$', '', os.path.splitext(os.path.basename(self.hdr_path))[0])
        return os.path.join(os.path.dirname(self.hdr_path), f'{stem}{n}.cab')


def read_volume_header(path):
    with open(path, 'rb') as f:
        h = f.read(20 + 0x40)
    sig, ver = struct.unpack_from('<4sI', h, 0)
    if sig != SIG:
        raise SystemExit(f'{path}: not an InstallShield cabinet')
    data_off, _unk, first_idx, last_idx = struct.unpack_from('<4I', h, 20)
    v = struct.unpack_from('<12I', h, 36)
    q = [v[k] | (v[k + 1] << 32) for k in range(0, 12, 2)]
    return dict(data_offset=data_off, first_index=first_idx, last_index=last_idx,
                first_offset=q[0], first_expanded=q[1], first_compressed=q[2],
                last_offset=q[3], last_expanded=q[4], last_compressed=q[5])


class Reader:
    """Byte stream of one file's stored data, following it across volumes (split files)."""

    def __init__(self, hdr, fd):
        self.hdr, self.fd = hdr, fd
        self.vol = fd['volume']
        self.f = None
        self.seed = 0
        self._open(self.vol)

    def _open(self, n):
        if self.f:
            self.f.close()
        path = self.hdr.volume_path(n)
        vh = read_volume_header(path)
        fd = self.fd
        comp = fd['flags'] & FILE_COMPRESSED
        if fd['index'] == vh['last_index'] and vh['last_offset'] != 0x7fffffff and vh['last_offset']:
            off, left = vh['last_offset'], (vh['last_compressed'] if comp else vh['last_expanded'])
        elif fd['index'] == vh['first_index'] and vh['first_offset']:
            off, left = vh['first_offset'], (vh['first_compressed'] if comp else vh['first_expanded'])
        else:
            off, left = fd['offset'], (fd['compressed'] if comp else fd['expanded'])
        self.f = open(path, 'rb')
        self.f.seek(off)  # Python seeks are 64-bit
        self.left = left
        self.vol = n

    def read(self, size):
        out = []
        while size > 0:
            if self.left <= 0:
                self._open(self.vol + 1)
                continue
            n = min(size, self.left)
            b = self.f.read(n)
            if len(b) != n:
                raise IOError(f'short read in volume {self.vol}: {len(b)} of {n}')
            self.left -= n
            size -= n
            out.append(b)
        data = b''.join(out)
        if self.fd['flags'] & FILE_OBFUSCATED:
            data = self._deobfuscate(data)
        return data

    def _deobfuscate(self, data):
        s = self.seed
        out = bytearray(len(data))
        for i, c in enumerate(data):
            x = c ^ 0xd5
            out[i] = (((x >> 2) | (x << 6)) - ((s + i) % 0x47)) & 0xff
        self.seed = s + len(data)
        return bytes(out)

    def close(self):
        if self.f:
            self.f.close()


def iter_file(hdr, fd, chunk=1 << 20):
    """Yield the expanded data of one file."""
    r = Reader(hdr, fd)
    try:
        if fd['flags'] & FILE_COMPRESSED:
            left = fd['compressed']
            while left > 0:
                n, = struct.unpack('<H', r.read(2))
                left -= 2
                block = r.read(n)
                left -= n
                dec = zlib.decompressobj(-15)  # every chunk is a raw-deflate stream of its own
                yield dec.decompress(block) + dec.flush()
            if left != 0:
                raise IOError(f'chunk lengths overran the compressed size by {-left}')
        else:
            left = fd['expanded']
            while left > 0:
                n = min(chunk, left)
                yield r.read(n)
                left -= n
    finally:
        r.close()


def process(hdr, fd, out_path=None, label=''):
    md5, sha = hashlib.md5(), hashlib.sha256()
    total, t0 = 0, time.time()
    fo = open(out_path + '.part', 'wb') if out_path else None
    try:
        last = 0
        for b in iter_file(hdr, fd):
            md5.update(b); sha.update(b)
            total += len(b)
            if fo:
                fo.write(b)
            if total - last >= 256 << 20:
                last = total
                print(f'  {label} {total / (1 << 20):.0f} / {fd["expanded"] / (1 << 20):.0f} MB', flush=True)
    finally:
        if fo:
            fo.close()
    want = fd['md5'].hex()
    md5_ok = (want == '0' * 32) or md5.hexdigest() == want
    size_ok = total == fd['expanded']
    ok = md5_ok and size_ok
    if out_path:
        if ok:
            os.replace(out_path + '.part', out_path)
        else:
            print(f'  kept partial output {out_path}.part for inspection')
    return dict(ok=ok, size=total, size_ok=size_ok, md5=md5.hexdigest(), md5_header=want, md5_ok=md5_ok,
                sha256=sha.hexdigest(), seconds=time.time() - t0)


def select(hdr, keys):
    sel = []
    for k in keys:
        if k.isdigit():
            sel.append(hdr.files[int(k)])
            continue
        kl = k.replace('/', '\\').lower()
        m = [fd for fd in hdr.files if fd['path'].lower() == kl]
        if not m:
            m = [fd for fd in hdr.files if fd['name'].lower() == kl]
        if len(m) != 1:
            raise SystemExit(f'{k!r}: {len(m)} matches (use the full path or the index)')
        sel.append(m[0])
    return sel


def is_external(fd):
    """Support files (setup.exe, setup.inx, ...) are listed with data offset 0: they lie next to the cabinet on
    the disc, not inside it (cabinet data starts after the volume header)."""
    return fd['offset'] == 0 and fd['expanded'] > 0


def flag_str(f):
    return ''.join(c if f & b else '-' for c, b in (('s', 1), ('o', 2), ('c', 4), ('i', 8)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('hdr', help='dataN.hdr of the cabinet set')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--list', action='store_true')
    g.add_argument('--verify', nargs='*', metavar='FILE')
    g.add_argument('--extract', nargs='+', metavar='FILE')
    ap.add_argument('--out', help='output folder for --extract')
    ap.add_argument('--strip', type=int, default=0, help='drop N leading directory components of the stored path')
    ap.add_argument('--force', action='store_true', help='overwrite existing output files')
    a = ap.parse_args()

    hdr = Header(a.hdr)
    if a.list:
        print(f'version 0x{hdr.version:08x} (major {hdr.major}), {hdr.dir_count} dirs, {hdr.file_count} files')
        for n in sorted({fd['volume'] for fd in hdr.files if not fd['flags'] & FILE_INVALID}):
            p = hdr.volume_path(n)
            if os.path.exists(p):
                vh = read_volume_header(p)
                print(f'volume {n}: {os.path.basename(p)} {os.path.getsize(p)} bytes, files {vh["first_index"]}..'
                      f'{vh["last_index"]}, data at 0x{vh["data_offset"]:x}, first/last split offsets '
                      f'0x{vh["first_offset"]:x} / 0x{vh["last_offset"]:x}')
            else:
                print(f'volume {n}: {os.path.basename(p)} MISSING')
        print('idx  flags vol      expanded    compressed          offset  md5                               path')
        for fd in hdr.files:
            if fd['flags'] & FILE_INVALID or not fd['name']:
                continue
            print(f'{fd["index"]:3d}  {flag_str(fd["flags"])}  {fd["volume"]:3d} {fd["expanded"]:13d} '
                  f'{fd["compressed"]:13d} {fd["offset"]:#15x}  {fd["md5"].hex()}  {fd["path"]}'
                  + ('  (not in the cabinet)' if is_external(fd) else ''))
        return 0

    if a.extract is not None:
        if not a.out:
            ap.error('--extract needs --out')
        sel = select(hdr, a.extract)
    else:
        sel = select(hdr, a.verify) if a.verify else [fd for fd in hdr.files
                                                       if fd['name'] and not fd['flags'] & FILE_INVALID]
    bad = skipped = 0
    for fd in sel:
        if is_external(fd):
            print(f'{fd["index"]:3d} {fd["path"]}: not stored in the cabinet (support file next to it), skipped')
            skipped += 1
            continue
        out_path = None
        if a.extract is not None:
            parts = [p for p in fd['path'].split('\\') if p]
            parts = parts[a.strip:] if len(parts) > a.strip else parts[-1:]
            if any(p in ('.', '..') or ':' in p for p in parts):
                raise SystemExit(f'unsafe stored path {fd["path"]!r}')
            out_root = os.path.abspath(a.out)
            out_path = os.path.join(out_root, *parts)
            if os.path.exists(out_path) and not a.force:
                print(f'SKIP {fd["path"]}: {out_path} exists (use --force)')
                continue
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
        print(f'{fd["index"]:3d} {fd["path"]} ({fd["expanded"]} bytes, {flag_str(fd["flags"])}, volume {fd["volume"]})',
              flush=True)
        r = process(hdr, fd, out_path, fd['name'])
        status = 'OK' if r['ok'] else 'FAIL'
        bad += not r['ok']
        print(f'  {status} size {r["size"]} ({"=" if r["size_ok"] else "!="} header {fd["expanded"]}), md5 {r["md5"]} '
              f'({"matches header" if r["md5_ok"] and r["md5_header"] != "0" * 32 else "no header md5" if r["md5_ok"] else "header " + r["md5_header"]}), '
              f'sha256 {r["sha256"]}, {r["seconds"]:.1f} s' + (f' -> {out_path}' if out_path else ''), flush=True)
    print(f'{len(sel) - bad - skipped} ok, {bad} failed, {skipped} not in the cabinet')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
