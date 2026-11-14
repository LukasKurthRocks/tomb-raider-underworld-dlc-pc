"""W7 (2026-11-14): which strings carry the stick glyphs U+180C / U+180D (and the other pad glyphs the PC keeps,
table 0x8a9ef8 entry -1), and which words the PC uses where the Xbox base text has a stick glyph. Read only.

Usage (from the repository root):
  ../bin/pyt -t 300 work/w7_1411/stick_glyph_survey.py INSTALLED_LOCAL_DIR > work/w7_1411/stick_glyph_survey.txt
INSTALLED_LOCAL_DIR = the game's mods\\local folder (locals.bin_001 / _004 are read, nothing written).
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import locals as L  # noqa: E402  (tools/locals.py)

# code points of page 1 that 0x5a7c20 keeps as glyphs (table 0x8a9ef8 = -1): sticks U+180C / U+180D, U+1812..U+1825
KEEP = [0x180C, 0x180D] + list(range(0x1812, 0x1826))
STICK = {0x180C: 'L-stick', 0x180D: 'R-stick'}


def cps(b):
    try:
        s = b.decode('utf-8')
    except UnicodeDecodeError:
        return set()
    return {ord(c) for c in s if 0x1800 <= ord(c) < 0x18B0}


def show(b):
    s = b.decode('utf-8', 'replace')
    out = []
    for c in s:
        o = ord(c)
        if 0x1800 <= o < 0x18B0:
            out.append('<U+%04X%s>' % (o, (' ' + STICK[o]) if o in STICK else ''))
        elif c == '\n':
            out.append('\\n')
        elif c == '\x1b':
            out.append('<ESC>')
        else:
            out.append(c)
    return ''.join(out)


def main():
    local_dir = sys.argv[1]
    # 1. installed tables: every string with a kept glyph
    for nnn, name in (('001', 'English'), ('004', 'German')):
        b = open(os.path.join(local_dir, 'locals.bin_' + nnn), 'rb').read()
        lang, st, offs = L.parse(b, 'le')
        print('== installed locals.bin_%s (%s): %d strings' % (nnn, name, len(st)))
        for i, s in enumerate(st):
            k = cps(s) & set(KEEP)
            if k:
                print('  id %5d keeps %s: %s' % (i, ','.join('U+%04X' % c for c in sorted(k)), show(s)))
    # 2. the PC's own words where the Xbox base text has a stick glyph (same string index in the base range)
    xb, xe = L.files('xbase')
    pc, pe = L.files('pcpatch')
    words = (b'ledge', b'Sims', b'stick', b'Stick', b'WASD', b'movement', b'Bewegung', b'shimmy', b'hangel')
    for spec in (0xfffff7e1, 0xfffff7e4):
        if spec not in xb or spec not in pc:
            print('spec %08x missing in xbase or pcpatch' % spec)
            continue
        X = L.parse(xb[spec], xe)[1]
        P = L.parse(pc[spec], pe)[1]
        print('== spec %08x: Xbox base strings with a stick glyph (%d strings)' % (spec, len(X)))
        n = 0
        for i, s in enumerate(X):
            if cps(s) & {0x180C, 0x180D}:
                n += 1
                print('  xbox %5d: %s' % (i, show(s)))
        print('  %d Xbox base strings with a stick glyph' % n)
        print('== spec %08x: PC patch strings with a stick glyph or a ledge / stick / movement word (%d strings)'
              % (spec, len(P)))
        n = 0
        for i, s in enumerate(P):
            if (cps(s) & {0x180C, 0x180D}) or any(w in s for w in words):
                n += 1
                print('  pc %5d: %s' % (i, show(s)))
        print('  %d PC strings listed' % n)


if __name__ == '__main__':
    main()
