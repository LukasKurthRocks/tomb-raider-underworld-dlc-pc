"""Locate a memory block from the crash dump (written by cdb .writemem) inside the sections of DRM files.
Read-only. Usage (repo root): ../bin/pyt work/crash_gpda_1411/locate_mem.py MEM.bin MEM_BASE_HEX ADDR_HEX LEN_HEX DRM...
DRM = a file path, or 'pc:<name>' for the PC archive copy (patch.000 / bigfile.000).
Prints every section holding the bytes [ADDR, ADDR+LEN) and the section start address implied by the match."""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_write as DW
import dtp_word_classes as C

BS = chr(92)


def sections(spec):
    if spec.startswith('pc:'):
        S = C.find(C.PC, 'le', 'pc-w' + BS + spec[3:])
        return [(s['type'], s['id'], s['data'] or b'') for s in S]
    return [(s.type, s.id, s.data) for s in DW.read(open(spec, 'rb').read(), 'le').sections]


def main(argv):
    mem = open(argv[0], 'rb').read()
    base, addr, ln = int(argv[1], 16), int(argv[2], 16), int(argv[3], 16)
    pat = mem[addr - base:addr - base + ln]
    print('pattern %d bytes at 0x%x: %s' % (len(pat), addr, pat[:32].hex()))
    for spec in argv[4:]:
        hits = 0
        for t, i, d in sections(spec):
            o = d.find(pat)
            while o >= 0:
                hits += 1
                print('%s: type %d id %d size 0x%x: match at +0x%x -> section start 0x%x' % (spec, t, i, len(d), o, addr - o))
                o = d.find(pat, o + 1)
        print('%s: %d hit(s)' % (spec, hits))


if __name__ == '__main__':
    main(sys.argv[1:])
