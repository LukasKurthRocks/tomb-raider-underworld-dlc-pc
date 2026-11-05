"""Check the texture-id lists of the object data DTP (the DTP an object section names at +8) in PC DRMs
(read-only; night analysis N5 04.11.2026, F16 crash after level.load dlc2_machine_room).

Engine facts (tru.exe, read with tools/pe_dis.py):
  tru+0x14e200 (object tracker post-load, object table 0xdb7400) calls tru+0x12b360 with the object; that function
  takes D = [object + 8] (the DTP named at object section +8) and ANDs texture ids with 0x1fff in place:
    u16 [D+0x0c] x 0x17c-byte records at [D+0x10] (field +0x110), u16 [D+0x14] x 0x2c at [D+0x18] (+0x20),
    u16 [D+0x1c] x 0x58 at [D+0x20] (+0x40), u16 [D+0x24] x 0xb8 at [D+0x28] (+0x64, +0x68),
    u16 [D+0x2c] x 0x64 at [D+0x30] (+0x48), u16 [D+0x54] x 0x3c at [D+0x58] (+4, +8),
    u16 [D+0x64] variable groups at [D+0x68]: {u32 n, u32 textureId[n]} repeated.
  A group count n that is not little-endian (e.g. 0x03000000 instead of 3) makes the last loop AND 0x1fff over
  n dwords of memory (F16: 0x03000000 dwords from 0x03ff0d78, i.e. the whole game pool behind the object).

For every object section (type 11) of every DRM given (files or folders), the tool resolves D through the id
reference at object +8, follows the internal pointers of D (relocation table) and reports:
  BAD  group count n > MAXN (default 64) or a group running past the end of the DTP
  BE   any count (u16 list counts, group counts) that looks byte-swapped (u32 0x0N000000 / u16 0xNN00)
  ok   summary per object with the number of groups and texture ids

Usage (from the repository root):
  ../bin/pyt -t 900 tools/objdata_texlist_check.py PATH [PATH ...] [--maxn 64] [--all] [-r] [--dedupe]
    PATH = .drm file or folder (not recursive unless -r); --all also prints the objects without problems;
    --dedupe checks each file content (md5) once and prints the unique problem files at the end
  ../bin/pyt -t 900 tools/objdata_texlist_check.py --profile PROFILE.json [--profile ...] [--base DIR]
    (agent F25, 05.11.2026, crash paket17a in dlc_dungeon) what a test profile ends up installing: the last source of
    every .drm (the tree order of Install-TruTree, tools/profile_last_source.py), plus with --base the .drm files of
    DIR (recursive, e.g. the game mods folder) that no tree of the profile brings. PROFILE may be a glob
    ("tests/profiles/paket*.json"); one result line per profile. Note: --base is taken as it stands - a game folder
    that still holds the trees of an earlier run is not the clean base install.
Exit code: 0 = no problem found, 1 = at least one problem (usable as a gate before a package is built).
"""
import sys, os, struct, glob, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

LISTS = [(0x0c, 0x10, 0x17c, (0x110,)), (0x14, 0x18, 0x2c, (0x20,)), (0x1c, 0x20, 0x58, (0x40,)),
         (0x24, 0x28, 0xb8, (0x64, 0x68)), (0x2c, 0x30, 0x64, (0x48,)), (0x54, 0x58, 0x3c, (4, 8))]


def files(paths, recursive=False):
    for p in paths:
        if os.path.isdir(p):
            if recursive:
                for r, _, fs in sorted(os.walk(p)):
                    for n in sorted(fs):
                        if n.lower().endswith('.drm'):
                            yield os.path.join(r, n)
                continue
            for n in sorted(os.listdir(p)):
                if n.lower().endswith('.drm'):
                    yield os.path.join(p, n)
        else:
            yield p


def profile_files(profile, base):
    """.drm paths a profile ends up installing (last tree source), plus the base files no tree brings."""
    import profile_last_source as PLS
    m = PLS.installed_map(profile)
    out = [path for rel, (path, src, k) in sorted(m.items()) if rel.endswith('.drm')]
    nbase = 0
    if base:
        for path in files([base], True):
            rel = os.path.relpath(path, base).replace('\\', '/').lower()
            if rel not in m:
                out.append(path); nbase += 1
    return out, nbase


def check_drm(path, maxn, show_all):
    try:
        drm = DW.read(open(path, 'rb').read(), 'le')
    except Exception as ex:
        print('SKIP %s: %s' % (os.path.basename(path), ex))
        return 0, 0
    by = {(s.type, s.id): s for s in drm.sections}
    nobj = nbad = 0
    for s in drm.sections:
        if s.type != 11 or len(s.data) < 12:
            continue
        r = R.parse(s.reloc, 'le') if s.reloc else R.Reloc()
        refs = {off: t for t, off in r.idref}
        if refs.get(8) != 7:
            continue
        did = struct.unpack_from('<I', s.data, 8)[0]
        d = by.get((7, did))
        if d is None:
            continue
        nobj += 1
        dr = R.parse(d.reloc, 'le') if d.reloc else R.Reloc()
        ptr = dict(dr.internal)
        data = d.data
        u16 = lambda o: struct.unpack_from('<H', data, o)[0]
        u32 = lambda o: struct.unpack_from('<I', data, o)[0]
        msgs = []
        if len(data) < 0x6c:
            continue
        for co, po, stride, fields in LISTS:
            c = u16(co)
            if c and (c & 0xff) == 0 and c >= 0x100:
                msgs.append('BE  u16 count at +0x%x = 0x%04x (byte-swapped?)' % (co, c))
            if c and po not in ptr:
                msgs.append('BAD u16 count at +0x%x = %d but +0x%x is no internal pointer' % (co, c, po))
        groups = u16(0x64)
        nids = 0
        if groups:
            if 0x68 not in ptr:
                msgs.append('BAD groups %d but +0x68 is no internal pointer' % groups)
            else:
                p = ptr[0x68]
                for g in range(groups):
                    if p + 4 > len(data):
                        msgs.append('BAD group %d header past the DTP end (+0x%x, size 0x%x)' % (g, p, len(data)))
                        break
                    n = u32(p)
                    if n > maxn or p + 4 + 4 * n > len(data):
                        tag = 'BE ' if (n & 0x00ffffff) == 0 else 'BAD'
                        msgs.append('%s group %d count at +0x%x = 0x%08x (engine would AND 0x1fff over %d dwords)'
                                    % (tag, g, p, n, n))
                        break
                    nids += n
                    p += 4 + 4 * n
        name = os.path.basename(path)
        if msgs:
            nbad += 1
            print('%s object %d -> DTP %d (size 0x%x, groups %d):' % (name, s.id, did, len(data), groups))
            for m in msgs:
                print('    ' + m)
        elif show_all:
            print('ok  %s object %d -> DTP %d groups %d ids %d' % (name, s.id, did, groups, nids))
    return nobj, nbad


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    maxn = 64
    if '--maxn' in a:
        k = a.index('--maxn'); maxn = int(a[k + 1]); del a[k:k + 2]
    show_all = '--all' in a
    recursive = '-r' in a
    dedupe = '--dedupe' in a
    a = [x for x in a if x not in ('--all', '-r', '--dedupe')]
    base = None
    if '--base' in a:
        k = a.index('--base'); base = a[k + 1]; del a[k:k + 2]
    profiles = []
    while '--profile' in a:
        k = a.index('--profile')
        pat = a[k + 1]; del a[k:k + 2]
        profiles += sorted(glob.glob(pat)) or [pat]
    if profiles:
        nbadp = 0
        for p in profiles:
            fl, nbase = profile_files(p, base)
            tot = bad = 0
            for f in fl:
                o, b = check_drm(f, maxn, show_all)
                tot += o; bad += b
            nbadp += 1 if bad else 0
            print('PROFILE %s: files %d (%d from the base), objects with object-data DTP %d, with problems %d'
                  % (os.path.basename(p), len(fl), nbase, tot, bad))
        print('profiles %d, with problems %d' % (len(profiles), nbadp))
        return 1 if nbadp else 0
    tot = bad = nf = 0
    seen = {}
    badfiles = []
    for f in files(a, recursive):
        if dedupe:
            h = hashlib.md5(open(f, 'rb').read()).hexdigest()
            if h in seen:
                continue
            seen[h] = f
        nf += 1
        o, b = check_drm(f, maxn, show_all)
        tot += o; bad += b
        if b and dedupe:
            badfiles.append((h, f))
    print('files %d%s, objects with object-data DTP %d, with problems %d' % (
        nf, ' (unique md5)' if dedupe else '', tot, bad))
    for h, f in badfiles:
        print('UNIQUE-BAD %s %s' % (h, f.replace('\\', '/')))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
