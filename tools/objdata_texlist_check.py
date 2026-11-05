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
  ../bin/pyt -t 900 tools/objdata_texlist_check.py PATH [PATH ...] [--maxn 64] [--all]
    PATH = .drm file or folder (not recursive); --all also prints the objects without problems
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

LISTS = [(0x0c, 0x10, 0x17c, (0x110,)), (0x14, 0x18, 0x2c, (0x20,)), (0x1c, 0x20, 0x58, (0x40,)),
         (0x24, 0x28, 0xb8, (0x64, 0x68)), (0x2c, 0x30, 0x64, (0x48,)), (0x54, 0x58, 0x3c, (4, 8))]


def files(paths):
    for p in paths:
        if os.path.isdir(p):
            for n in sorted(os.listdir(p)):
                if n.lower().endswith('.drm'):
                    yield os.path.join(p, n)
        else:
            yield p


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
    a = [x for x in a if x != '--all']
    tot = bad = nf = 0
    for f in files(a):
        nf += 1
        o, b = check_drm(f, maxn, show_all)
        tot += o; bad += b
    print('files %d, objects with object-data DTP %d, with problems %d' % (nf, tot, bad))


if __name__ == '__main__':
    main()
