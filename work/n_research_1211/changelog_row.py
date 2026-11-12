"""Group N 12.11.2026: insert group N's CHANGELOG row after group M's 0.22.34 row (idempotent, keeps BOM / line ends).
Usage (from trudlcport): ../bin/pyt -t 60 work/n_research_1211/changelog_row.py FILE"""
import sys

ANCHOR = '| 2026-11-12 | `TruMenu` 0.22.34 (group M;'
ROW = ('| 2026-11-12 | **Research: checkpoint chime group, isPlatformXenon gate, exe achievements, photo capture chain, '
       'extra object refs** (group N; static, read-only, nothing built, nothing installed, no game started). DTP 906 / '
       'PC 3512 is the checkpoint SoundPlex tree, +0x50 = Assign sound group (base 55 under the pause group, DLC 1 5 '
       'above it; PC always 55 through the patch generalbank). `corebase` f16 = isPlatformXenon (Xbox 1, PC 0) gates '
       'every achievement script; script 5 f1 / f2 decoded (Master Speed Demon, Swan Diver 1 / 2 / 3). The five Xbox '
       'exe award sites and their PC counterparts (chapter end, rewards, enemy kill, chimney jump). 0x774aa0 = '
       'CaptureAndSaveTask: GetFrontBufferData + JPEG quality 85, PC never writes the file. A 0x5c1760 ref survives a '
       'level change (`work/n_research_1211/`, ENGINE.md) |')


def main(argv):
    p = argv[0]
    raw = open(p, 'rb').read()
    bom = raw.startswith(b'\xef\xbb\xbf')
    t = raw.decode('utf-8-sig')
    nl = '\r\n' if '\r\n' in t else '\n'
    lines = t.split(nl)
    if ROW in lines:
        k = lines.index(ROW)
        if k > 0 and lines[k - 1].startswith(ANCHOR):
            print('%s: row present' % p); return
        del lines[k]   # placed after an older anchor: move it
    idx = [i for i, l in enumerate(lines) if l.startswith(ANCHOR)]
    if len(idx) != 1:
        sys.exit('anchor not unique / missing (%d)' % len(idx))
    lines.insert(idx[0] + 1, ROW)
    open(p, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + nl.join(lines).encode('utf-8'))
    print('%s: row added' % p)


if __name__ == '__main__':
    main(sys.argv[1:])
