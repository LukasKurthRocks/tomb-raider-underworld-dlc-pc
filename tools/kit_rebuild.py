"""Rebuild the files of an upstream format-2 release kit (B269 / B270, kit/manifest.json + kit/patches/*.bsdiff) OFFLINE
from our own inputs, without running any code of the kit (2026-11-05, docs Befund-B270-Kit-0511.md).

Format 2, as read from the kit's install_dlc.py (text only):
  every manifest file has a source (Xbox pack record, or a PC archive record) or none (port-authored text, shipped as
  is under kit/authored/); mode 'plain': old = source bytes (+ PC record bytes when aux has 'pc');
  mode 'cdrm': old = decompressed source DRM (+ the source's Xbox texture sections converted to PC layout, appended,
  when aux has 'tex'; + the decompressed PC record when aux has 'pc'); new = bspatch(old, patch); for 'cdrm' new must
  have raw_md5 and is recompressed (CDRM, little endian, zlib level 9, 256 KiB blocks); the result must have md5.
  Checks on the way: source md5, old_md5 (the converted source), tex_md5 (the converted textures alone).
Everything here is our own code: bspatch in numpy (bsdiff4 layout: 'BSDIFF40', 3 offtin lengths, bz2 control / diff /
extra), the archive reader (tools/archive.py), the texture converter tools/tex_convert.py (byte-identical to the
kit's tex_convert.py apart from line endings, checked with diff --strip-trailing-cr).

Usage (from the repository root):
  ../bin/pyt -t 7200 tools/kit_rebuild.py KIT_DIR OUT_DIR [--pc DIR] [--pack10 P] [--pack11 P] [--jobs N]
        [--only a,b] [--report R.tsv] [--exe-old FILE --exe-out FILE]
  KIT_DIR  the extracted kit folder (manifest.json, patches/, authored/)
  OUT_DIR  mods-style output folder (manifest 'rel' paths); a file is written only when its md5 matches the manifest
           ('exact'), or when the decompressed content matches raw_md5 but the recompression differs ('equivalent',
           other zlib build) - both are listed in the report
  --pc     PC game folder read-only for patch.000 / bigfile.000 (default ../data/pc)
  --only   only manifest files whose rel contains one of the comma separated parts
  --exe-old the Steamless output of tru.exe (md5 must be the manifest's exe source md5); without it the exe is skipped
Exit code 0 when every selected file is exact or equivalent.
Library: parse_patch(bytes), bspatch(old, patch), crc(name), drm_sections(raw, endian), cdrm_decode / cdrm_encode.
"""
import sys, os, json, struct, zlib, bz2, hashlib, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
from archive import Archive

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
_C = os.path.join(ROOT, 'data', 'Xenia-SteveRepack', 'Content', '534307EC', '00000002')
PACK10 = os.path.join(_C, '9CA70CF0EDA43654D158C2E37470D301DFA850E753', 'pack10.000')   # as tools/dlc_names.py PACKS
PACK11 = os.path.join(_C, '600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153', 'pack11.000')
PC = os.path.join(ROOT, 'data', 'pc')
CDRM_BLOCK = 0x40000


def md5(b): return hashlib.md5(b).hexdigest()


def md5_file(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''): h.update(blk)
    return h.hexdigest()


def crc(s):
    """bigfile name hash: CRC-32/BZIP2 of the lower-case name"""
    h = 0xffffffff
    for c in s.lower():
        h ^= ord(c) << 24
        for _ in range(8):
            h = ((h << 1) ^ 0x4c11db7) & 0xffffffff if h & 0x80000000 else (h << 1) & 0xffffffff
    return ~h & 0xffffffff


# ------------------------------------------------------------------ bsdiff4 patch format
def offtin(b):
    y = int.from_bytes(b[:7] + bytes([b[7] & 0x7f]), 'little')
    return -y if b[7] & 0x80 else y


def parse_patch(d):
    """-> dict(new=size, tri=[(diff_len, extra_len, seek)], diff=bytes, extra=bytes, size=len(patch))"""
    if d[:8] != b'BSDIFF40': raise ValueError('not a bsdiff4 patch')
    lc, ld, nsz = offtin(d[8:16]), offtin(d[16:24]), offtin(d[24:32])
    ctrl = bz2.decompress(d[32:32 + lc]); diff = bz2.decompress(d[32 + lc:32 + lc + ld]); extra = bz2.decompress(d[32 + lc + ld:])
    tri = [(offtin(ctrl[i:i + 8]), offtin(ctrl[i + 8:i + 16]), offtin(ctrl[i + 16:i + 24])) for i in range(0, len(ctrl), 24)]
    return dict(new=nsz, tri=tri, diff=diff, extra=extra, size=len(d))


def bspatch(old, patch):
    """our own bspatch (same result as bsdiff4.patch): new[i] = old[j] + diff[k] (mod 256) runs, then extra runs"""
    p = parse_patch(patch) if isinstance(patch, (bytes, bytearray)) else patch
    o = np.frombuffer(old, dtype=np.uint8); df = np.frombuffer(p['diff'], dtype=np.uint8)
    new = np.zeros(p['new'], dtype=np.uint8)
    np_, op, dp, ep = 0, 0, 0, 0
    for x, y, z in p['tri']:
        if x:
            seg = np.zeros(x, dtype=np.uint8)
            lo, hi = max(op, 0), min(op + x, len(o))           # old bytes outside the old file count as 0 (bspatch)
            if hi > lo: seg[lo - op:hi - op] = o[lo:hi]
            new[np_:np_ + x] = seg + df[dp:dp + x]
            np_ += x; op += x; dp += x
        if y:
            new[np_:np_ + y] = np.frombuffer(p['extra'][ep:ep + y], dtype=np.uint8)
            np_ += y; ep += y
        op += z
    if np_ != p['new']: raise ValueError('patch control does not fill the new file (%d of %d)' % (np_, p['new']))
    return new.tobytes()


# ------------------------------------------------------------------ DRM container
def cdrm_decode(d, endian):
    if d[:4] not in (b'CDRM', b'MRDC'): return d
    e = '>' if endian == 'be' else '<'
    n, = struct.unpack(e + 'I', d[8:12])
    ents = [struct.unpack(e + 'II', d[16 + 8 * i:24 + 8 * i]) for i in range(n)]
    pos = (16 + 8 * n + 15) & ~15; out = bytearray()
    for u, c in ents:
        blk = d[pos:pos + c]
        out += zlib.decompress(blk) if (u & 0xff) == 2 else blk
        pos = (pos + c + 15) & ~15
    return bytes(out)


def cdrm_encode(raw, block=CDRM_BLOCK, level=9):
    blocks = [raw[i:i + block] for i in range(0, len(raw), block)] or [b'']
    comp = [zlib.compress(b, level) for b in blocks]
    out = bytearray(struct.pack('<4sIII', b'CDRM', 0, len(blocks), 0))
    for b, c in zip(blocks, comp): out += struct.pack('<II', len(b) << 8 | 2, len(c))
    for c in comp:
        out += b'\0' * (-len(out) % 16); out += c
    return bytes(out)


def drm_sections(raw, endian):
    """-> [(type, id, data)] of a decompressed DRM (header, section table, names, relocations skipped)"""
    e = '>' if endian == 'be' else '<'
    ver, namesz, padsz, u0, u1, n = struct.unpack(e + 'iiiiii', raw[:24])
    secs, p = [], 24
    for _ in range(n):
        size, typ, pad, vid, packed, sid, spec = struct.unpack(e + 'iBBHIII', raw[p:p + 20]); p += 20
        secs.append((size, typ, packed >> 8, sid))
    p += namesz + padsz; out = []
    for size, typ, rel, sid in secs:
        p += rel; out.append((typ, sid, raw[p:p + size])); p += size
    return out


def tex_aux(raw_be):
    """the Xbox texture sections of a DRM converted to PC layout (tools/tex_convert.py), concatenated; a section the
    converter rejects contributes nothing (as the format defines it)"""
    import tex_convert as TC
    out = bytearray()
    for typ, sid, data in drm_sections(raw_be, 'be'):
        if typ == 5:
            try: out += TC.convert(data)
            except Exception: pass
    return bytes(out)


# ------------------------------------------------------------------ sources
class Sources:
    def __init__(self, pc, pack10, pack11):
        self.paths = {'pack10.000': (pack10, 'be'), 'pack11.000': (pack11, 'be'),
                      'patch.000': (os.path.join(pc, 'patch.000'), 'le'), 'bigfile.000': (os.path.join(pc, 'bigfile.000'), 'le')}
        self.arcs = {}

    def read(self, archive, name, spec):
        if archive not in self.arcs:
            p, e = self.paths.get(archive, (None, None))
            self.arcs[archive] = Archive(p, e) if p and os.path.isfile(p) else None
        a = self.arcs[archive]
        if a is None: return None
        for r in a.find(crc(name), spec):
            return a.read(r)
        return None


_S = {}


def _init(pc, pack10, pack11):
    _S['src'] = Sources(pc, pack10, pack11)


def build_old(f, sb, pb):
    if f['mode'] == 'cdrm':
        raw = cdrm_decode(sb, 'be' if f['source']['kind'] == 'xbox' else 'le')
        old = bytearray(raw); tex = None
        if 'tex' in f['aux']: tex = tex_aux(raw); old += tex
        if 'pc' in f['aux'] and pb is not None: old += cdrm_decode(pb, 'le')
        return bytes(old), tex
    old = bytearray(sb)
    if 'pc' in f['aux'] and pb is not None: old += pb
    return bytes(old), None


def process(job):
    """one manifest file -> dict(rel, status, detail, md5, raw_ok); writes OUT/rel for exact / equivalent"""
    f, kit, out = job
    r = dict(rel=f['rel'], dlc=f.get('dlc'), mode=f['mode'], aux=','.join(f['aux']), archive='', status='', detail='', md5='')
    try:
        s = f['source']
        if s is None:
            tb = open(os.path.join(kit, f['patch']), 'rb').read()
            if md5(tb) != f['md5']: r.update(status='FAIL', detail='authored file md5 differs'); return r
            st = 'exact'; r['archive'] = 'authored'
        else:
            r['archive'] = s['archive']
            sb = _S['src'].read(s['archive'], s['name'], s['spec'])
            if sb is None: r.update(status='FAIL', detail='source missing: %s %s' % (s['archive'], s['name'])); return r
            if md5(sb) != s['md5']: r.update(status='FAIL', detail='source md5 differs: %s' % s['name']); return r
            pb = None
            q = f.get('pc_also')
            if q:
                pb = _S['src'].read(q['archive'], q['name'], q['spec'])
                if pb is None or md5(pb) != q['md5']: r.update(status='FAIL', detail='pc_also missing / differs: %s' % q['name']); return r
            old, tex = build_old(f, sb, pb)
            if f.get('old_md5') and md5(old) != f['old_md5']:
                why = 'old_md5 differs'
                if tex is not None and f.get('tex_md5'): why += ' (tex_md5 %s)' % ('ok' if md5(tex) == f['tex_md5'] else 'differs')
                r.update(status='FAIL', detail=why); return r
            new = bspatch(old, open(os.path.join(kit, f['patch']), 'rb').read())
            if f['mode'] == 'cdrm':
                if md5(new) != f['raw_md5']: r.update(status='FAIL', detail='raw md5 differs after patch'); return r
                tb = cdrm_encode(new)
                st = 'exact' if md5(tb) == f['md5'] else 'equivalent'
            else:
                if md5(new) != f['md5']: r.update(status='FAIL', detail='md5 differs after patch'); return r
                tb, st = new, 'exact'
        p = os.path.join(out, f['rel'].replace('/', os.sep)); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as fo: fo.write(tb)
        h = md5_file(p)
        if h != md5(tb): r.update(status='FAIL', detail='written file differs from memory'); return r
        r.update(status=st, md5=h)
        if st == 'equivalent': r['detail'] = 'raw content = raw_md5, recompressed md5 %s != %s' % (h, f['md5'])
    except Exception as e:
        r.update(status='FAIL', detail='%s: %s' % (type(e).__name__, e))
    return r


def arg(argv, key, default=None):
    if key in argv:
        k = argv.index(key); v = argv[k + 1]; del argv[k:k + 2]; return v
    return default


def main(argv):
    pc = arg(argv, '--pc', PC); p10 = arg(argv, '--pack10', PACK10); p11 = arg(argv, '--pack11', PACK11)
    jobs = int(arg(argv, '--jobs', '4')); only = arg(argv, '--only'); rep = arg(argv, '--report')
    exe_old = arg(argv, '--exe-old'); exe_out = arg(argv, '--exe-out')
    kit, out = argv[0], argv[1]
    man = json.load(open(os.path.join(kit, 'manifest.json'), encoding='utf-8'))
    print('kit %s format %s: %d files' % (man.get('build'), man.get('format'), len(man['files'])))
    print('python %s, zlib %s (runtime %s), numpy %s' % (sys.version.split()[0], zlib.ZLIB_VERSION,
                                                      getattr(zlib, 'ZLIB_RUNTIME_VERSION', '?'), np.__version__))
    if man.get('format') != 2: sys.exit('only kit format 2 is supported')
    todo = man['files']
    if only: todo = [f for f in todo if any(o.lower() in f['rel'].lower() for o in only.split(','))]
    for k, p in (('pack10.000', p10), ('pack11.000', p11), ('patch.000', os.path.join(pc, 'patch.000')), ('bigfile.000', os.path.join(pc, 'bigfile.000'))):
        print('  source %-12s %s %s' % (k, 'ok' if os.path.isfile(p) else 'MISSING', os.path.basename(p)))
    t0 = time.time(); res = []
    jl = [(f, kit, out) for f in todo]
    if jobs <= 1:
        _init(pc, p10, p11)
        for j in jl: res.append(process(j))
    else:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=jobs, initializer=_init, initargs=(pc, p10, p11)) as ex:
            for k, r in enumerate(ex.map(process, jl, chunksize=1)):
                res.append(r)
                if (k + 1) % 50 == 0: print('  %d/%d  %.0fs' % (k + 1, len(jl), time.time() - t0), flush=True)
    cnt = {}
    for r in res: cnt[r['status']] = cnt.get(r['status'], 0) + 1
    print('\nresult (%d files, %.0fs): %s' % (len(res), time.time() - t0, ', '.join('%s %d' % kv for kv in sorted(cnt.items()))))
    by = {}
    for r in res:
        k = (r['dlc'], r['status']); by[k] = by.get(k, 0) + 1
    for k in sorted(by, key=str): print('  %-7s %-10s %d' % (k[0], k[1], by[k]))
    for r in res:
        if r['status'] not in ('exact',): print('  %-10s %s  %s' % (r['status'], r['rel'], r['detail']))
    x = man.get('exe')
    if x:
        if not exe_old:
            print('\nexe %s (%s, md5 %s): skipped - needs the Steamless output of tru.exe, md5 %s (not available here)' % (
                x['rel'], x.get('name'), x['md5'], x['source']['md5']))
        else:
            ob = open(exe_old, 'rb').read()
            if md5(ob) != x['source']['md5']: print('\nexe: --exe-old has md5 %s, needs %s: skipped' % (md5(ob), x['source']['md5']))
            else:
                nb = bspatch(ob, open(os.path.join(kit, x['patch']), 'rb').read())
                ok = md5(nb) == x['md5']; print('\nexe: %s' % ('exact' if ok else 'md5 differs'))
                if ok and exe_out:
                    with open(exe_out, 'wb') as fo: fo.write(nb)
    if rep:
        with open(rep, 'w', encoding='utf-8', newline='\n') as fo:
            fo.write('rel\tdlc\tmode\taux\tarchive\tstatus\tmd5\tdetail\n')
            for r in res: fo.write('\t'.join(str(r[k]) for k in ('rel', 'dlc', 'mode', 'aux', 'archive', 'status', 'md5', 'detail')) + '\n')
        print('report:', rep)
    sys.exit(0 if all(r['status'] in ('exact', 'equivalent') for r in res) else 1)


if __name__ == '__main__':
    main(sys.argv[1:])
