"""Scan the script sections (type 8) of PC DRM files for UI text-element init blocks and judge their byte order
(read-only; N15 package H 2026-11-09). Anchor: the colour word 0xff606060 followed by {u16 text id, u16 0} and the
u32 field 4 (base-game PC: 0x00000004; a block converted as 2 x u16 gives 0x00040000). Also counts the float 0.1
(0x3dcccccd) and its broken form 0xcccd334f, and -1.0 (0xbf800000) / 0x0000c160, anywhere in the section.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/ui_text_init_scan.py DIR_OR_DRM [...]
    per section with anchors: 'FILE script ID anchors N ok A broken B (text ids ...) f0.1 ok/broken f-1 ok/broken'
    last line: 'files F sections S anchors N ok A broken B'; exit 1 when any broken anchor was found
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import script_func_list as FL


def drms(paths):
    for p in paths:
        if os.path.isdir(p):
            for r, _, fs in os.walk(p):
                for f in sorted(fs):
                    if f.lower().endswith('.drm'):
                        yield os.path.join(r, f)
        else:
            yield p


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    tf = ts = ta = tok = tbad = 0
    for f in drms(argv):
        try:
            S, e = FL.sections(f)
        except Exception as ex:
            print('%s: not read (%s)' % (f, ex))
            continue
        tf += 1
        for ty, sid, d, rl in S:
            if ty != 8 or not d:
                continue
            ok = bad = 0
            tids = []
            for o in range(0, len(d) - 11, 4):
                if struct.unpack_from('<I', d, o)[0] != 0xff606060:
                    continue
                w1, w2 = struct.unpack_from('<II', d, o + 4)
                if w2 == 4:
                    ok += 1; tids.append(w1 & 0xffff)
                elif w2 == 0x40000:
                    bad += 1; tids.append(w1 & 0xffff)
            words = [struct.unpack_from('<I', d, o)[0] for o in range(0, len(d) - 3, 4)]
            f1 = (words.count(0x3dcccccd), words.count(0xcccd334f))
            fm = (words.count(0xbf800000), words.count(0x0000c160))
            if ok or bad:
                ts += 1; ta += ok + bad; tok += ok; tbad += bad
                print('%s script %d anchors %d ok %d broken %d (text ids %s) f0.1 %d/%d f-1 %d/%d' % (
                    os.path.basename(f), sid, ok + bad, ok, bad, ','.join(str(t) for t in tids[:8]),
                    f1[0], f1[1], fm[0], fm[1]))
    print('files %d sections %d anchors %d ok %d broken %d' % (tf, ts, ta, tok, tbad))
    return 1 if tbad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
