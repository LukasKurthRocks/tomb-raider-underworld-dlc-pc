"""Word diff of a fixed DRM against its input, read-only: proves a fix changed only the words it should.

Both files (PC, little-endian, CDRM or raw) are decoded; the section lists must have the same length and are paired
by position (section order must not change). Per section it compares the header (type, id, flags, ver, spec, pad,
data / reloc size), the relocation bytes and every 32-bit word of the data. A changed data word whose old value is OLD
and new value is NEW (--allow OLD:NEW, repeatable) counts as an "allowed" word, every other changed word as "other";
a changed header id OLD -> NEW is an allowed header change, any other header change is "other". Written for the
thrall base-class fix on the 50o stack (docs Befund-Thrall-Absturz.md section 12): 12433 -> 26884 must be the only
change of the script step; the animfx step adds "other" words in the 4 thrall DRMs only (listed per section).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/fix_word_diff.py INPUT.drm FIXED.drm [--allow 12433:26884] [--v]
  ../bin/pyt -t 1800 tools/fix_word_diff.py --dirs INPUT_DIR FIXED_DIR [--allow 12433:26884] [--v]
        every *.drm of FIXED_DIR against the same name in INPUT_DIR
Last line per file: "<name>: sections N, changed S, allowed words A, other words O, allowed headers H, other headers
X, reloc changes R, order ok"; --v lists every changed word.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW


def diff(pa, pb, allow, verbose):
    A = DW.read(open(pa, 'rb').read(), 'le'); B = DW.read(open(pb, 'rb').read(), 'le')
    name = os.path.basename(pb)
    if len(A.sections) != len(B.sections):
        print('%s: section count %d vs %d - not comparable' % (name, len(A.sections), len(B.sections)))
        return False
    st = dict(changed=0, allowed=0, other=0, hdr_allowed=0, hdr_other=0, reloc=0)
    if A.names != B.names or A.pad != B.pad or (A.ver, A.u0, A.u1) != (B.ver, B.u0, B.u1):
        st['hdr_other'] += 1; print('  file header / names / pad differ')
    for i, (s, t) in enumerate(zip(A.sections, B.sections)):
        ha = (s.type, s.flags, s.ver, s.spec, s.pad, len(s.data), len(s.reloc))
        hb = (t.type, t.flags, t.ver, t.spec, t.pad, len(t.data), len(t.reloc))
        ch = False
        if ha != hb:
            st['hdr_other'] += 1; ch = True
            print('  #%d (%d, %d): header %s -> %s' % (i, s.type, s.id, ha, hb))
        if s.id != t.id:
            ch = True
            if (s.id, t.id) in allow: st['hdr_allowed'] += 1
            else: st['hdr_other'] += 1
            print('  #%d type %d: section id %d -> %d (%s)' % (i, s.type, s.id, t.id, 'allowed' if (s.id, t.id) in allow else 'OTHER'))
        if s.reloc != t.reloc:
            st['reloc'] += 1; ch = True
            print('  #%d (%d, %d): relocations differ' % (i, s.type, s.id))
        if s.data != t.data:
            ch = True
            na = no = 0
            m = min(len(s.data), len(t.data))
            for o in range(0, m - 3, 4):
                x, y = s.data[o:o + 4], t.data[o:o + 4]
                if x == y: continue
                vx, vy = struct.unpack('<I', x)[0], struct.unpack('<I', y)[0]
                ok = (vx, vy) in allow
                if ok: na += 1
                else: no += 1
                if verbose: print('    #%d (%d, %d) +0x%05x %08x -> %08x %s' % (i, s.type, s.id, o, vx, vy, 'allowed' if ok else 'OTHER'))
            tail = m - (m & ~3)
            if tail and s.data[m - tail:m] != t.data[m - tail:m]: no += 1
            st['allowed'] += na; st['other'] += no
            print('  #%d (%d, %d -> %d): %d allowed word(s), %d other word(s)' % (i, s.type, s.id, t.id, na, no))
        if ch: st['changed'] += 1
    print('%s: sections %d, changed %d, allowed words %d, other words %d, allowed headers %d, other headers %d, '
          'reloc changes %d, order ok' % (name, len(A.sections), st['changed'], st['allowed'], st['other'],
                                          st['hdr_allowed'], st['hdr_other'], st['reloc']))
    return True


def main(argv):
    verbose = '--v' in argv
    if verbose: argv.remove('--v')
    allow = set()
    while '--allow' in argv:
        k = argv.index('--allow'); a, b = argv[k + 1].split(':'); allow.add((int(a), int(b))); del argv[k:k + 2]
    if argv and argv[0] == '--dirs':
        din, dout = argv[1], argv[2]
        for fn in sorted(os.listdir(dout)):
            if fn.lower().endswith('.drm'): diff(os.path.join(din, fn), os.path.join(dout, fn), allow, verbose)
    elif len(argv) == 2:
        diff(argv[0], argv[1], allow, verbose)
    else:
        print(__doc__); return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
