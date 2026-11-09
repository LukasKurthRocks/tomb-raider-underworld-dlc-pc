"""Compare one section (by type-independent section id) between PC DRM files byte for byte, optionally against the
PC base-game copy of a base unit (read-only; N15 / package E 2026-11-09: DTP 18577 environment colour LUT of
dlc_yggdrasil_end - installed vs pipeline tree vs the PC base copy, ENGINE.md "Base-id DTPs in DLC copies").

Usage (from the repository root):
  ../bin/pyt -t 900 tools/drm_section_cmp.py SID A.drm B.drm [...] [--base REL BASE_SID] [--len N]
    prints size / md5 of the section payload in every file, the number of differing 4-byte words against the first
    file and (with --base) against the PC base section BASE_SID of base unit REL (bigfile, like
    work/endb270_0811/unit_dtp.load('pc', REL)); --len compares only the first N bytes (hex).
"""
import sys, os, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm


def section(d, e, sid):
    S = drm.sections_with_data(drm.cdrm_decode(d, e), e)[1]
    for s in S:
        if s.get('id') == sid:
            return bytes(s['data'])
    return None


def words_diff(a, b, n):
    m = min(len(a), len(b), n)
    return sum(1 for w in range(0, m - 3, 4) if a[w:w + 4] != b[w:w + 4])


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__)
        return 2
    n = int(a[a.index('--len') + 1], 16) if '--len' in a else 1 << 30
    base = None
    if '--base' in a:
        i = a.index('--base')
        sys.path.insert(0, os.path.join(HERE, '..', 'work', 'endb270_0811'))
        import unit_dtp as UD
        base = section(UD.load('pc', a[i + 1])[0], 'le', int(a[i + 2]))
        a = a[:i] + a[i + 3:]
    if '--len' in a:
        i = a.index('--len')
        a = a[:i] + a[i + 2:]
    if a[0] == 'xword':
        # xword XBOX_BE.drm SID OFF [OFF ..]: the big-endian words of one section of an Xbox DRM
        s = section(open(a[1], 'rb').read(), 'be', int(a[2]))
        for o in a[3:]:
            w = int(o, 16)
            print('Xbox sec %s +%#06x %s' % (a[2], w, s[w:w + 4].hex() if s is not None else 'missing'))
        return 0
    if a[0] == 'all':
        # every section of two files by index: (index, type, id, size, differing words)
        A = drm.sections_with_data(drm.cdrm_decode(open(a[1], 'rb').read(), 'le'), 'le')[1]
        B = drm.sections_with_data(drm.cdrm_decode(open(a[2], 'rb').read(), 'le'), 'le')[1]
        print('sections %d / %d' % (len(A), len(B)))
        nd = 0
        for k, (x, y) in enumerate(zip(A, B)):
            dx, dy = bytes(x['data']), bytes(y['data'])
            if dx != dy:
                nd += 1
                print('  sec %3d type %s id %s size %#x / %#x: %d words differ' % (
                    k, x.get('type'), x.get('id'), len(dx), len(dy), words_diff(dx, dy, n)))
                if '--words' in sys.argv and len(dx) == len(dy) and words_diff(dx, dy, n) <= 16:
                    for w in range(0, len(dx) - 3, 4):
                        if dx[w:w + 4] != dy[w:w + 4]:
                            print('      +%#06x %s -> %s' % (w, dx[w:w + 4].hex(), dy[w:w + 4].hex()))
        print('differing sections: %d' % nd)
        return 0
    sid, files = int(a[0]), a[1:]
    secs = [(f, section(open(f, 'rb').read(), 'le', sid)) for f in files]
    first = secs[0][1]
    for f, s in secs:
        if s is None:
            print('%s: section %d missing' % (f, sid))
            continue
        line = '%s: size %#x md5 %s, words differing vs first %d' % (
            f, len(s), hashlib.md5(s).hexdigest()[:12], words_diff(first, s, n))
        if base is not None:
            line += ', vs PC base %d (base size %#x)' % (words_diff(base, s, n), len(base))
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
