"""Enemy tunes of a DLC enemy DRM, Xbox original against the converted PC DRM: every tune word and every sub-record a
tune points to (senses, spawn, meleeController, ...), word by word with the byte order the converter used, plus an
optional second enemy for a field-by-field Xbox comparison (read-only; K-2 2026-11-09: why does the hall02 tutorial
thrall never start an attack on PC?).

Engine (docs Befund-Thrall-Felder-0611.md 1, ENGINE.md 13): enemy data = [DTP + 0xc8] (magic 0xdaf00018), byte +0x18
tune count, +0x1c tune array, +0x20 default tune; tune +0x1c = parent tune; tune +0x30 senses, +0x3c health,
+0x58 wrestle, +0x64 directionalDeath, +0x68..+0x70 rangedAttack1..3, +0x80..+0xac meleeAttack1..12, +0x11c spawn,
+0x13c meleeController (names from the retail EnemyObjectDataControl getters).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/enemy_tune_compare.py XBOX_NAME PC_DRM [--other XBOX_NAME2] [--sub 0x60]
    XBOX_NAME  e.g. viking_thrall_tutorial_dlc2_ (Xbox DLC original, as tools/melee_link_record_check.py)
    PC_DRM     the converted PC file
    --other    a second enemy (Xbox only): its default tune is printed next to the first one's (same offsets)
    --sub N    bytes dumped per sub-record (default 0x60; melee records are skipped - melee_link_record_check covers them)
Output: per tune and sub-record one line per word: offset, Xbox word, PC word, matching byte orders, float reading.
Exit 0 = done, 2 = structure not found.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import tuning_word_audit as TA
import melee_link_record_check as M

NAMES = {0x1c: 'parent', 0x30: 'senses', 0x3c: 'health', 0x58: 'wrestle', 0x64: 'directionalDeath',
         0x68: 'rangedAttack1', 0x6c: 'rangedAttack2', 0x70: 'rangedAttack3', 0x11c: 'spawn', 0x13c: 'meleeController'}
TUNE_LEN = 0x140


def fl(w):
    v = struct.unpack('>f', w)[0]
    return ('%g' % v) if (v == 0 or 1e-6 < abs(v) < 1e7) else '-'


def tunes_of(d, ip, root):
    _recs, tunes = M.walk(d, ip, root)
    default = ip.get(root + 0x20)
    return tunes, default


def dump_words(xd, pd, start, length, reloc, label):
    print('  %s (DTP +0x%x, 0x%x bytes)' % (label, start, length))
    for off in range(0, length, 4):
        o = start + off
        if o + 4 > len(xd): break
        if o in reloc:
            print('     +0x%03x pointer' % off)
            continue
        xw, pw = xd[o:o + 4], pd[o:o + 4]
        od = M.orders_of(xw, pw)
        print('     +0x%03x Xbox %s PC %s (%s) f=%s u=%d' % (off, xw.hex(), pw.hex(), '/'.join(od) or 'OTHER', fl(xw),
                                                             struct.unpack('>I', xw)[0]))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    xname, pfile = argv[0], argv[1]
    other = argv[argv.index('--other') + 1] if '--other' in argv else None
    sub = int(argv[argv.index('--sub') + 1], 0) if '--sub' in argv else 0x60
    xs, src = TA.load_x(xname)
    ps = M.load_pc(pfile)
    found = M.enemy_dtps(xs)
    if not found:
        print('%s: no enemy data' % xname)
        return 2
    for xsec, xip, root in found:
        psec = next((s for s in ps if s['type'] == 7 and s['id'] == xsec['id']), None)
        if psec is None:
            print('%s DTP %d: not in the PC file' % (xname, xsec['id']))
            continue
        xd, pd = bytes(xsec['data']), bytes(psec['data'])
        pip = dict(R.parse(bytes(psec['reloc']), 'le').internal)
        reloc = set(xip) | set(pip)
        tunes, default = tunes_of(xd, xip, root)
        print('%s (%s) DTP %d: enemy data +0x%x, tune count %d, default tune +0x%s, tunes %s' % (
            xname, src, xsec['id'], root, xd[root + 0x18], '%x' % default if default is not None else '-',
            ', '.join('+0x%x' % t for t in tunes)))
        dump_words(xd, pd, root, 0x24, reloc, 'enemy data')
        for t in tunes:
            dump_words(xd, pd, t, TUNE_LEN, reloc, 'tune +0x%x' % t)
            for f in sorted(set(range(0, TUNE_LEN, 4)) - set(M.MELEE)):
                r = xip.get(t + f)
                if r is None or f == 0x1c: continue
                dump_words(xd, pd, r, sub, reloc, 'tune +0x%x field +0x%x %s -> record' % (t, f, NAMES.get(f, '?')))
    if other:
        os_, osrc = TA.load_x(other)
        of = M.enemy_dtps(os_)
        if of:
            osec, oip, oroot = of[0]
            od = bytes(osec['data'])
            _r, otunes = M.walk(od, oip, oroot)
            odef = oip.get(oroot + 0x20)
            print('== other %s (%s) DTP %d default tune +0x%s: Xbox words of the default tune and its sub-records' % (
                other, osrc, osec['id'], '%x' % odef if odef is not None else '-'))
            if odef is not None:
                for off in range(0, TUNE_LEN, 4):
                    o = odef + off
                    print('     +0x%03x %s' % (off, 'pointer' if o in oip else od[o:o + 4].hex()))
                for f in sorted(set(range(0, TUNE_LEN, 4)) - set(M.MELEE)):
                    r = oip.get(odef + f)
                    if r is None or f == 0x1c: continue
                    print('  other field +0x%x %s -> record +0x%x: %s' % (
                        f, NAMES.get(f, '?'), r, ' '.join(od[r + k:r + k + 4].hex() for k in range(0, sub, 4))))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
