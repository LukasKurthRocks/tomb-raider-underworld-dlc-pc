"""Dump records of the model record list (model DTP header +0x34 count / +0x38 pointer) of an Xbox and / or a PC DRM,
decoded with the field layout the PC reads in tru+0x135cc0 (anim event kind 1 sub 0xb = new instance effect type 0x85,
the full-screen colour effect drawn by tru+0x1469a0 -> tru+0x12b860) - read-only (Look finding 2026-11-03).

PC record (40 bytes; Xbox 36 bytes, the same nine words without the trailing u32 0):
  +0x00 byte  flags0          +0x01 byte  flags (bit 0 tested with the event's 'only if' argument)
  +0x02 s16   fade-in time (x 256 -> effect +0x20)
  +0x04 u32   colour 0xAARRGGBB (-> effect +0x30; alpha 0x80 -> blend mode 1, else 2 in tru+0x1469a0)
  +0x08 byte  ?               +0x09 s8    effect id (-> effect +0x14)
  +0x0a s16   end time (x 256, added to the start -> +0x28)
  +0x0c u16   hold time (0xffff = none -> +0x24 = -1)
  +0x0e s16   (x [0x849670] -> effect +0x38)        +0x10 u16 radius (-> +0x3c, 0 = full screen, no distance fade)
  +0x12 s16   (x [0x843078] -> effect +0x40)
  +0x14 u32   object / DTP id (-> effect +0x34; != 0 -> the distance branch, no full-screen quad)
  +0x18 f32   (-> effect +0x44)
  +0x1c u32   (-> effect +0x4c; != 0 -> the distance branch with tru+0x146340)
  +0x20 byte  bit 0 (-> effect +0x50)
  +0x24 u32   PC only (0)

Usage (from the repository root):
  ../bin/pyt -t 300 tools/model_reclist_dump.py DRM be|le DTP_ID [REC[,REC..]]    one file (be = Xbox, le = PC)
  ../bin/pyt -t 300 tools/model_reclist_dump.py --pair XBOX.drm PC.drm DTP_ID [REC[,REC..]]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import model_reclist_fix as MF


def records(path, e, sid):
    D = DW.read(open(path, 'rb').read(), e)
    s = next((x for x in D.sections if x.type == 7 and x.id == sid), None)
    if s is None: sys.exit('%s: no DTP %d' % (path, sid))
    m = MF.model_list(s, e)
    if m is None: sys.exit('%s: DTP %d has no +0x34 / +0x38 list' % (path, sid))
    L, n, nxt = m
    st = MF.stride(L, n, nxt)
    return s, L, n, nxt, st


def decode(r, f):
    """fields as tru+0x135cc0 reads them (f = struct byte order of the file)"""
    g = lambda fmt, o: struct.unpack_from(f + fmt, r, o)[0]
    return ('flags %02x/%02x fadein %d colour %08x id %d end %d hold %d s0e %d radius %d s12 %d obj %d f18 %g '
            'w7 %08x b20 %d' % (r[0], r[1], g('h', 2), g('I', 4), struct.unpack('b', r[9:10])[0], g('h', 0xa),
                                g('H', 0xc), g('h', 0xe), g('H', 0x10), g('h', 0x12), g('I', 0x14), g('f', 0x18),
                                g('I', 0x1c), r[0x20] & 1))


def dump(path, e, sid, want):
    s, L, n, nxt, st = records(path, e, sid)
    f = '>' if e == 'be' else '<'
    print('%s (%s): DTP %d, %d records at +%#x, next block +%#x, stride %s' % (os.path.basename(path), e, sid, n, L,
                                                                              nxt, st))
    st = st or (MF.XS if e == 'be' else MF.PS)
    for k in (want if want else range(n)):
        r = s.data[L + k * st:L + (k + 1) * st]
        print('  rec %2d  %s' % (k, r.hex(' ', 4)))
        print('          %s' % decode(r, f))


def main(argv):
    if len(argv) < 3: sys.exit(__doc__)
    if argv[0] == '--pair':
        want = [int(x) for x in argv[4].split(',')] if len(argv) > 4 else None
        dump(argv[1], 'be', int(argv[3]), want)
        dump(argv[2], 'le', int(argv[3]), want)
        return
    want = [int(x) for x in argv[3].split(',')] if len(argv) > 3 else None
    dump(argv[0], argv[1], int(argv[2]), want)


if __name__ == '__main__':
    main(sys.argv[1:])
