"""Character set of a localised string table against a font (read-only): language field, string count, empty /
invalid UTF-8 entries, code points used (by Unicode block) and which of them the font has no glyph for.
Built for the language-variant survey (could a table of another language be shown with the PC font?).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/locals_charset.py TABLE [--font FILE.drm] [--be] [--missing N]
      TABLE: a locals.bin file, or SOURCE:SPEC with SOURCE as in tools/locals.py (e.g. pcpatch:fffff7e4)
      --font: DRM with the font descriptor (tools/font_survey.py), e.g. an extracted generalbank.drm
      --missing N: list up to N missing code points with an example entry index (default 40)
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as LC
import font_survey as FS


def load_table(arg, en):
    if os.path.exists(arg):
        return LC.parse(open(arg, 'rb').read(), en)
    src, spec = arg.split(':')
    f, e = LC.files(src)
    return LC.parse(f[int(spec, 16)], e)


def main(argv):
    en = 'be' if '--be' in argv else 'le'; argv = [a for a in argv if a != '--be']
    font = None; nmiss = 40
    if '--font' in argv: k = argv.index('--font'); font = argv[k + 1]; del argv[k:k + 2]
    if '--missing' in argv: k = argv.index('--missing'); nmiss = int(argv[k + 1]); del argv[k:k + 2]
    other = None
    if '--compare' in argv: k = argv.index('--compare'); other = argv[k + 1]; del argv[k:k + 2]
    if len(argv) != 1: sys.exit(__doc__)
    lang, strs, _ = load_table(argv[0], en)
    if other:                                   # index-by-index against a second table
        _, s2, _ = load_table(other, en)
        n = min(len(strs), len(s2))
        real = lambda b: b not in (b'', b'\x01')
        same = sum(1 for i in range(n) if strs[i] == s2[i] and real(strs[i]))
        both = sum(1 for i in range(n) if real(strs[i]) and real(s2[i]))
        print('compare: %d / %d entries; both non-empty %d, identical %d; only first %d, only second %d'
              % (len(strs), len(s2), both, same, sum(1 for i in range(n) if real(strs[i]) and not real(s2[i])),
                 sum(1 for i in range(n) if real(s2[i]) and not real(strs[i]))))
        # by text: where does each non-empty entry of the first table sit in the second (index shift)?
        pos = collections.defaultdict(list)
        for j, b in enumerate(s2):
            if real(b): pos[b].append(j)
        shift = collections.Counter(); uniq = amb = none = 0; runs = []
        for i, b in enumerate(strs):
            if not real(b): continue
            js = pos.get(b, [])
            if len(js) == 1:
                uniq += 1; d = js[0] - i; shift[d] += 1
                if runs and runs[-1][2] == d: runs[-1][1] = i
                else: runs.append([i, i, d])
            elif js: amb += 1
            else:
                none += 1
                if none <= 12: print('  not in the second table: entry %d %r' % (i, b[:60]))
        print('by text: %d entries found once in the second table, %d several times, %d not at all' % (uniq, amb, none))
        print('  index shift (second - first): %s' % ', '.join('%+d x%d' % kv for kv in shift.most_common(8)))
        big = [r for r in runs if r[1] - r[0] >= 20]
        print('  shift runs of >= 20 entries: %s' % ', '.join('%d..%d %+d' % tuple(r) for r in big[:20]))
    bad = []; used = collections.Counter(); first = {}
    for i, b in enumerate(strs):
        try: t = b.decode('utf-8')
        except UnicodeDecodeError: bad.append(i); continue
        for ch in t:
            c = ord(ch)
            used[c] += 1
            first.setdefault(c, i)
    print('table: language field %d, %d strings, %d empty, %d invalid UTF-8, %d bytes of text'
          % (lang, len(strs), sum(1 for s in strs if not s), len(bad), sum(len(s) for s in strs)))
    print('code points used: %d distinct' % len(used))
    for k, v in sorted(FS.block_counts(used).items()): print('    %-42s %d' % (k, v))
    # the PC text layout (0x475c00) breaks lines only at U+0020; long entries without one cannot wrap
    texts = [b.decode('utf-8') for i, b in enumerate(strs) if i not in set(bad) and b not in (b'', b'\x01')]
    for lim in (20, 40):
        nos = [t for t in texts if len(t) > lim and ' ' not in t]
        print('  entries longer than %d characters without an ASCII space: %d (of %d non-empty)' % (lim, len(nos), len(texts)))
    ctl = sorted(c for c in used if c < 0x20)
    if ctl: print('  control codes: %s' % ' '.join('0x%02x x%d' % (c, used[c]) for c in ctl))
    if font:
        import drm_write as DW
        D = DW.read(open(font, 'rb').read(), en)
        ds = FS.descriptors(D, '>' if en == 'be' else '<')
        if not ds: sys.exit('no font descriptor in %s' % font)
        have = set(x[0] for x in ds[0][1]['ents'])
        miss = sorted(c for c in used if c >= 0x20 and c not in have and c != 0xa0)
        occ = sum(used[c] for c in miss)
        print('font: %d glyphs; missing code points: %d distinct, %d occurrences (shown as the U+18AF fallback glyph)'
              % (len(have), len(miss), occ))
        for k, v in sorted(FS.block_counts(miss).items()): print('    %-42s %d' % (k, v))
        for c in sorted(miss, key=lambda c: -used[c])[:nmiss]:
            print('    U+%04X x%-5d first in entry %d' % (c, used[c], first[c]))


if __name__ == '__main__':
    main(sys.argv[1:])
