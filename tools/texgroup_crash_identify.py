"""Identify the object, DTP and field behind a crash in the texture-id mask loop of tru+0x12b360 (read-only; agent
F25, 05.11.2026, crash after level.load dlc_dungeon in run paket17a; class of F16, docs/WINDOWS_REBUILD.md finding 47).

Engine facts (tru.exe, tools/pe_dis.py): tru+0x14e89c (object tracker post-load, object table 0xdb7400, entry stride
0x24, index = ebx) calls tru+0x12b360(object). That function takes D = [object + 8] (the object data DTP) and ANDs
texture ids with 0x1fff; the last loop walks u16 [D+0x64] groups at [D+0x68]: {u32 n, u32 textureId[n]}:
  tru+0x12b490  mov ecx, [eax]          ; n of the group
  tru+0x12b492  sub edx, 1              ; groups left
  tru+0x12b4a0  and dword [eax], 0x1fff ; inner loop, ecx = ids left
A byte-swapped group count (Xbox 00000004 -> PC 0x04000000) makes the inner loop run over game memory until it hits
an unmapped page (write AV at tru+0x12b4a0) or ruins whatever lies behind (F16: FMOD mixer object).

What the tool reads from a full or TruGuard minidump (exception context of the faulting thread):
  * eip in the inner loop, esi = D, edx = groups left, ecx = ids left, eax = write pointer,
  * the object argument [esp + 8] (return address [esp + 4] must be tru+0x14e8a1), object id u16 [object + 0x14],
    the object table entry (0xdb7400 + 0x24 * k, [+8] = object, u16 [+0xc] = id),
  * the group list in memory: per group offset in D, count, and which group the write pointer is in;
    start of the masked run = eax - 4 * (n - ecx) must equal the group's first id slot,
  * with --drm FILE: the object section with that id, its DTP; compares D in memory with the DTP data dword by dword
    over [0, end of the faulty group header) - relocated pointer / id slots skipped, other dwords must be equal.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/texgroup_crash_identify.py DUMP.dmp [--drm FILE.drm] [--table 0xdb7400]
Exit code: 0 = identified (and, with --drm, the memory matches the file), 1 = not this crash class / mismatch.
"""
import sys, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from minidump_read import Minidump

LOOP = (0x52b490, 0x52b4b0)      # tru+0x12b490 .. tru+0x12b4b0 (group loop + inner loop)
RET = 0x54e8a1                   # return address of the call at tru+0x14e89c


def arg(a, name, default):
    if name in a:
        return a[a.index(name) + 1]
    return default


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    m = Minidump(a[0])
    table = int(arg(a, '--table', '0xdb7400'), 16)
    drm_path = arg(a, '--drm', None)
    e = m.exception
    if not e:
        print('no exception stream'); return 1
    r = m.regs(e['ctx'])
    print('exception %08x at %08x (%s) info %s' % (e['code'], e['addr'], m.module_of(e['addr']),
                                                    ' '.join('%x' % x for x in e['info'])))
    print('  ' + ' '.join('%s=%08x' % kv for kv in r.items()))
    if not (LOOP[0] <= r['eip'] < LOOP[1]):
        print('NOT the mask loop of tru+0x12b360 (eip %08x)' % r['eip']); return 1
    st = m.read(r['esp'], 12)
    saved_esi, ret, obj = struct.unpack('<III', st)
    print('stack: saved esi %08x, return %08x (%s), object argument %08x' % (saved_esi, ret, m.module_of(ret), obj))
    ok = True
    if ret != RET:
        print('  WARN return address is not tru+0x14e8a1'); ok = False
    D = m.u32(obj + 8)
    oid = m.u32(obj + 0x14) & 0xffff
    print('object %08x: [+8] D = %08x (esi %08x %s), id u16 [+0x14] = %d' % (obj, D, r['esi'],
                                                                         'same' if D == r['esi'] else 'DIFFERENT', oid))
    for k in range(4096):
        ent = m.read(table + 0x24 * k, 0x24)
        if ent is None:
            break
        if struct.unpack_from('<I', ent, 8)[0] == obj:
            print('object table entry %d at %08x: id %d, state u16 %d (ebx %d)' % (
                k, table + 0x24 * k, struct.unpack_from('<H', ent, 0xc)[0], struct.unpack_from('<H', ent, 0xe)[0],
                r['ebx']))
            break
    else:
        print('  WARN object not found in the object table')
    hdr = m.read(D, 0x6c)
    ngroups = struct.unpack_from('<H', hdr, 0x64)[0]
    gp = struct.unpack_from('<I', hdr, 0x68)[0]
    print('D+0x64 groups %d, D+0x68 -> %08x (D+0x%x)' % (ngroups, gp, gp - D))
    p = gp
    bad = None
    for g in range(ngroups):
        n = m.u32(p)
        if n is None:
            print('  group %d header at %08x not in the dump' % (g, p)); break
        left = ngroups - 1 - g
        mark = ''
        if p + 4 <= r['eax'] < p + 4 + 4 * n and left == r['edx']:
            done = n - r['ecx']
            start = r['eax'] - 4 * done
            mark = ' <== faulting group: %d of %d ids done, masked run %08x..%08x (%d bytes), first id slot %s' % (
                done, n, start, r['eax'], r['eax'] - start, 'matches' if start == p + 4 else 'DIFFERS')
            if start != p + 4:
                ok = False
            bad = (g, p - D, n)
        print('  group %d at D+0x%x: n = 0x%08x (%d)%s' % (g, p - D, n, n, mark))
        if n > 0x10000:
            break
        p += 4 + 4 * n
    if bad is None:
        print('faulting group not found'); return 1
    g, off, n = bad
    sw = struct.unpack('>I', struct.pack('<I', n))[0]
    print('RESULT object %d, D = %08x, group %d count at D+0x%x = 0x%08x (byte-swapped value %d)' % (oid, D, g, off, n, sw))
    if drm_path:
        import drm_write as DW, drm_reloc as R
        drm = DW.read(open(drm_path, 'rb').read(), 'le')
        by = {(s.type, s.id): s for s in drm.sections}
        sec = by.get((11, oid))
        if sec is None:
            print('DRM %s: no object section %d' % (os.path.basename(drm_path), oid)); return 1
        did = struct.unpack_from('<I', sec.data, 8)[0]
        d = by.get((7, did))
        rel = R.parse(d.reloc, 'le') if d.reloc else R.Reloc()
        skip = set(rel.pointer_offsets()) | set(rel.id_offsets())
        end = off + 4
        mem = m.read(D, end)
        same = diff = skipped = 0
        for o in range(0, end, 4):
            if o in skip:
                skipped += 1; continue
            if mem[o:o + 4] == d.data[o:o + 4]:
                same += 1
            else:
                diff += 1
                print('  diff D+0x%x memory %s file %s' % (o, mem[o:o + 4].hex(), d.data[o:o + 4].hex()))
        print('DRM %s: object %d -> DTP %d (size 0x%x); D+0..0x%x: %d dwords equal, %d different, %d pointer / id '
              'slots skipped; file bytes at +0x%x = %s (u32 LE 0x%08x)' % (
                  os.path.basename(drm_path), oid, did, len(d.data), end, same, diff, skipped, off,
                  d.data[off:off + 4].hex(), struct.unpack_from('<I', d.data, off)[0]))
        if diff:
            ok = False
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
