"""List the player object type table (records {name, init, f2..f6}) of an Xbox 360 image or of the PC tru.exe
(read-only; finding 43, DLC 2 rock vein / doppelganger).

The table is indexed by the object data's type index ((obj+0x10)->+0x34 on the Xbox); the title update inserted a
record ("doppelganger_casual", init DoppelgangerInit) - this tool shows where, and whether the records after it moved
(objects converted from Xbox TU data would then carry a PC index that names a different record).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/player_type_table.py xbox DUMP TABLE_VA         (DUMP: guest image based at 0x82000000)
  ../bin/pyt -t 120 tools/player_type_table.py pc   TRU_EXE TABLE_VA
  ../bin/pyt -t 120 tools/player_type_table.py find-xbox DUMP NAME         (table start from a record name)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

BASE = 0x82000000


def cstr(blob, off):
    if off < 0 or off >= len(blob): return None
    end = blob.find(b'\0', off, off + 80)
    if end <= off: return None
    s = blob[off:end]
    return s.decode('ascii') if all(32 <= c < 127 for c in s) else None


def xbox_records(d, va):
    out = []
    while True:
        o = va - BASE
        w = struct.unpack_from('>7I', d, o)
        name = cstr(d, w[0] - BASE) if BASE <= w[0] < BASE + len(d) else None
        if not name: break
        out.append((va, name) + w[1:]); va += 28
    return out


def pc_records(exe, va):
    base, secs = PE.sections(exe)

    def off(a):
        for _, sva, rptr, size, _ in secs:
            if sva <= a < sva + size: return rptr + a - sva
        return -1
    out = []
    while True:
        o = off(va)
        if o < 0: break
        w = struct.unpack_from('<7I', exe, o)
        name = cstr(exe, off(w[0])) if off(w[0]) >= 0 else None
        if not name: break
        out.append((va, name) + w[1:]); va += 28
    return out


def main(argv):
    mode, path = argv[0], argv[1]
    blob = open(path, 'rb').read()
    if mode == 'find-xbox':
        s = blob.find(argv[2].encode() + b'\0')
        while s >= 0:
            ptr = struct.pack('>I', BASE + s)
            r = blob.find(ptr)
            while r >= 0:
                if r % 4 == 0:
                    # walk back over records whose first word is a string pointer
                    o = r
                    while o >= 28 and cstr(blob, struct.unpack_from('>I', blob, o - 28)[0] - BASE): o -= 28
                    print('name 0x%08x referenced at 0x%08x, table start candidate 0x%08x' % (BASE + s, BASE + r, BASE + o))
                r = blob.find(ptr, r + 1)
            s = blob.find(argv[2].encode() + b'\0', s + 1)
        return
    va = int(argv[2], 0)
    recs = xbox_records(blob, va) if mode == 'xbox' else pc_records(blob, va)
    for i, r in enumerate(recs):
        print('%3d 0x%08x %-28s init 0x%08x  f2..f6 %s' % (i, r[0], r[1], r[2], ' '.join('0x%08x' % x for x in r[3:])))


if __name__ == '__main__':
    main(sys.argv[1:])
