"""Where and how do our Script sections (type 8) still differ from B138? (read-only analysis for stage 2b)

For every DRM of a rebuilt tree with a B138 counterpart, the Script sections are paired with the Xbox section
(dtp_audit.section_pairs) and with B138 (same type and id, same size). Each differing word is classified by how it
came from the Xbox word, in ours and in B138:
  s32 (byte-reversed), s16 (u16 halves swapped), raw (unchanged), u8u8u16 / u16u8u8, reloc (word is a pointer or
  id slot in the Xbox relocations), other (no byte permutation - a different value)
The pairs (ours class, B138 class) show which rule is missing. Also counted: words where B138 = Xbox value of a
DLC id that our id map changed ('other' on both sides with equal Xbox words is listed per file).

Output: totals per class pair, per file, and work/rebuild/script_diff_<label>.json with every differing word.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/script_diff.py [MODS_DIR] [LABEL] [--ref REF_MODS_DIR]
  defaults: work/rebuild/stage2b/mods, stage2b, ../data/pc/mods
"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'rebuild')
PERMS = {'s32': (3, 2, 1, 0), 's16': (1, 0, 3, 2), 'raw': (0, 1, 2, 3), 'u8u8u16': (0, 1, 3, 2), 'u16u8u8': (1, 0, 2, 3)}


def cls(x, p):
    for name, pm in PERMS.items():
        if bytes(x[i] for i in pm) == p: return name
    return 'other'


def scan_file(args):
    import dtp_audit as DA, drm_write as DW, drm_reloc as R
    rel, path, ref = args
    xs = DA.xsecs(rel)
    if xs is None: return rel, None
    D = DW.read(open(path, 'rb').read(), 'le'); B = DW.read(open(ref, 'rb').read(), 'le')
    bmap = {(s.type, s.id): s for s in B.sections}
    words = []
    pairs = [(x, i) for x, i in DA.section_pairs(xs, D) if x['type'] == 8]
    x8 = [x for x in xs if x['type'] == 8]; p8 = [i for i, s in enumerate(D.sections) if s.type == 8]
    if len(pairs) < len(x8) and len(x8) == len(p8):
        # section_pairs pairs by index only when the whole layout matches, else only DTPs; the assemble route replaces
        # shader sections, so pair the Script sections by their order (it is kept) - finding 34
        pairs = list(zip(x8, p8))
    for x, i in pairs:
        sec = D.sections[i]
        if x['data'] is None: continue
        b = bmap.get((8, sec.id))
        if b is None or len(b.data) != len(sec.data) or len(x['data']) != len(sec.data) or b.data == sec.data: continue
        xr = R.parse(x['reloc'], 'be'); slots = set(xr.pointer_offsets()) | set(xr.id_offsets())
        xd = x['data']
        for k in range(0, len(sec.data) - 3, 4):
            o, r = sec.data[k:k + 4], b.data[k:k + 4]
            if o == r: continue
            xw = xd[k:k + 4]
            co = 'reloc' if k in slots else cls(xw, o)
            cr = 'reloc' if k in slots else cls(xw, r)
            words.append((sec.id, k, xw.hex(), o.hex(), r.hex(), co, cr))
    return rel, words


def main(argv):
    ref = '../data/pc/mods'
    if '--ref' in argv:
        k = argv.index('--ref'); ref = argv[k + 1]; del argv[k:k + 2]
    mods = argv[0] if argv else 'work/rebuild/stage2b/mods'
    label = argv[1] if len(argv) > 1 else 'stage2b'
    jobs = []
    for dp, dn, fn in os.walk(mods):
        for f in fn:
            if not f.endswith('.drm'): continue
            p = os.path.join(dp, f); rel = os.path.relpath(p, mods).replace(os.sep, '/')
            if os.path.exists(os.path.join(ref, rel)): jobs.append((rel, p, os.path.join(ref, rel)))
    from concurrent.futures import ProcessPoolExecutor
    tot, per_file, out = collections.Counter(), collections.Counter(), {}
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        for rel, words in ex.map(scan_file, sorted(jobs)):
            if not words: continue
            out[rel] = words
            per_file[rel] = len(words)
            tot.update((w[5], w[6]) for w in words)
    print('differing script words: %d in %d files' % (sum(per_file.values()), len(per_file)))
    print('(ours class, B138 class) -> words:')
    for (a, b), n in tot.most_common(): print('   %-8s %-8s %6d' % (a, b, n))
    print('files with most differing words:')
    for rel, n in per_file.most_common(12): print('   %6d  %s' % (n, rel))
    # 'other' on both sides: is it a value mapping (the same ours -> B138 pair again and again, e.g. ids numbered
    # differently) or scattered values? Little-endian u32 values, also as two u16 halves.
    import struct
    pairs, halves = collections.Counter(), collections.Counter()
    for words in out.values():
        for sid, k, xw, o, r, co, cr in words:
            if co != 'other' or cr != 'other': continue
            ov, rv = struct.unpack('<I', bytes.fromhex(o))[0], struct.unpack('<I', bytes.fromhex(r))[0]
            pairs[(ov, rv)] += 1
            for h in (0, 1):
                a, b = (ov >> (16 * h)) & 0xffff, (rv >> (16 * h)) & 0xffff
                if a != b: halves[(h, a, b)] += 1
    n = sum(pairs.values())
    if n:
        top = pairs.most_common(15)
        print('other/other words: %d, distinct (ours, B138) value pairs: %d; top 15 cover %d' % (n, len(pairs), sum(c for _, c in top)))
        for (ov, rv), c in top: print('   %5d  ours %08x  B138 %08x' % (c, ov, rv))
        lo = sum(c for (h, a, b), c in halves.items() if h == 0); hi = sum(c for (h, a, b), c in halves.items() if h == 1)
        print('differing u16 halves: low %d, high %d; distinct half pairs %d' % (lo, hi, len(halves)))
        for (h, a, b), c in halves.most_common(10): print('   %5d  %s half ours %04x  B138 %04x' % (c, 'high' if h else 'low', a, b))
        # how far apart are the differing halves? (a constant delta = an id numbering offset)
        delta = collections.Counter()
        for (h, a, b), c in halves.items(): delta[a - b] += c
        dsum = sum(delta.values())
        print('differing u16 halves by delta (ours - B138), top 10 of %d:' % dsum)
        for d, c in delta.most_common(10): print('   %+6d  %5d  (%.1f %%)' % (d, c, 100.0 * c / dsum))
        big = sum(c for (h, a, b), c in halves.items() if a - b == 1 and b >= 16828)
        print('delta +1 with B138 value >= 16828 (DLC-new symbol range): %d' % big)
        # which Xbox values (BE u16 halves) are behind the most frequent differing pairs?
        src = collections.defaultdict(collections.Counter)
        for words in out.values():
            for sid, k, xw, o, r, co, cr in words:
                if co != 'other' or cr != 'other': continue
                xb = bytes.fromhex(xw); ob = bytes.fromhex(o); rb = bytes.fromhex(r)
                for h in (0, 1):
                    a = struct.unpack_from('<H', ob, 2 * h)[0]; b = struct.unpack_from('<H', rb, 2 * h)[0]
                    if a != b: src[(a, b)][struct.unpack_from('>H', xb, 2 - 2 * h)[0]] += 1
        print('Xbox u16 behind the most frequent differing halves (ours / B138 <- Xbox: count):')
        for (a, b), c in sorted(src.items(), key=lambda kv: -sum(kv[1].values()))[:12]:
            print('   ours %5d  B138 %5d  <- %s' % (a, b, ', '.join('%d: %d' % kv for kv in c.most_common(3))))
    os.makedirs(W, exist_ok=True)
    rep = os.path.join(W, 'script_diff_%s.json' % label)
    json.dump(out, open(rep, 'w'), indent=0)
    print('report', os.path.abspath(rep))


if __name__ == '__main__':
    main(sys.argv[1:])
