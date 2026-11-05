"""Script sections (type 8) of a DLC DRM across our copies, his B270 copy, the Xbox source and the resident PC
generalbank (read-only; kit-rest task 3, workspace docs Befund-Kit-Reste-0511.md).

Per NAME:SID: size and md5 of the section data + relocation blob in every copy; whether a copy equals the resident
PC generalbank section of the same id (the engine keeps the first loaded section of an id - finding 45 - so a DLC
copy of a resident id is never used); word count that differs between the copies (common part); and the words at
the given offsets (LE dword as the PC reads it, Xbox BE dword) - e.g. the inline u16 arrays of tools/
script_u16array_check.py.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/kitrest_script_cmp.py NAME:SID[:OFF,OFF..] [...] [--tree TAG=DIR ...]
"""
import sys, os, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import tuning_word_audit as TA

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
TREES = [('b138', 'work/rebuild/b138_pristine/mods'), ('repair', 'work/rebuild/b138_fixes/mods'),
         ('own2b', 'work/rebuild/asm_stage2b_ach/mods'), ('inst', '../data/pc/mods'), ('his', 'work/b270_kit/mods')]


def pcgb():
    import dtp_word_classes as C
    return {s['id']: s for s in C.find(C.PC, 'le', 'pc-w' + chr(92) + 'generalbank.drm') if s['type'] == 8}


def h(b): return hashlib.md5(b).hexdigest()[:8]


def main(a):
    while '--tree' in a:
        k = a.index('--tree'); tg, dd = a[k + 1].split('=', 1); TREES.insert(-1, (tg, dd)); del a[k:k + 2]
    gb = pcgb()
    TA.ORDER = ('pack10', 'pack11', 'tu', 'xbase2', 'xbase')
    for spec in a:
        p = spec.split(':'); rel = p[0] + ('' if p[0].endswith('.drm') else '.drm'); sid = int(p[1])
        offs = [int(x, 16) for x in p[2].split(',')] if len(p) > 2 else []
        xs, src = TA.load_x(rel.replace('/', chr(92)))
        xsec = [s for s in xs if s['type'] == 8 and s['id'] == sid]
        cps = {}
        for tag, d in TREES:
            f = os.path.join(ROOT, d, rel)
            if not os.path.isfile(f): continue
            ss = [s for s in TA.load_p(f) if s['type'] == 8 and s['id'] == sid]
            if ss: cps[tag] = ss[0]
        res = gb.get(sid)
        print('\n=== %s script %d (Xbox %s: %s) | resident PC generalbank: %s' % (
            rel, sid, src, ('%d bytes' % len(xsec[0]['data'])) if xsec else 'none',
            ('%d bytes data %s reloc %s' % (len(res['data']), h(res['data']), h(res['reloc']))) if res else 'NOT resident'))
        for t, s in cps.items():
            eq = ''
            if res: eq = ' | = resident: data %s, reloc %s' % (s['data'] == res['data'], s['reloc'] == res['reloc'])
            print('  %-7s %6d bytes data %s reloc %s%s' % (t, len(s['data']), h(s['data']), h(s['reloc']), eq))
        tags = list(cps)
        for i in range(len(tags)):
            for j in range(i + 1, len(tags)):
                x, y = cps[tags[i]]['data'], cps[tags[j]]['data']
                n = min(len(x), len(y)); dw = sum(1 for o in range(0, n - 3, 4) if x[o:o + 4] != y[o:o + 4])
                if dw or len(x) != len(y): print('  diff %s vs %s: %d words in common part, sizes %d / %d' % (tags[i], tags[j], dw, len(x), len(y)))
        if res:
            for t in tags:
                x = cps[t]['data']; y = res['data']; n = min(len(x), len(y))
                dw = sum(1 for o in range(0, n - 3, 4) if x[o:o + 4] != y[o:o + 4])
                print('  %s vs resident: %d words differ in common part, sizes %d / %d' % (t, dw, len(x), len(y)))
        import dtp_twin_field as TF
        xg = {}
        for layer in ('tu', 'xbase2', 'xbase'):
            secs, _ = TF.load_named('generalbank', [layer], 'be')
            ss = [s for s in (secs or []) if s['type'] == 8 and s['id'] == sid]
            if ss:
                xg[layer] = ss[0]['data']
                print('  Xbox generalbank (%s) script %d: %d bytes, = DLC Xbox copy: %s' % (
                    layer, sid, len(ss[0]['data']), bool(xsec) and ss[0]['data'] == xsec[0]['data']))
        for o in offs:
            cells = ['xbox=%s' % xsec[0]['data'][o:o + 4].hex() if xsec and o + 4 <= len(xsec[0]['data']) else 'xbox=-']
            for layer, xd in xg.items():
                cells.append('x%s=%s' % (layer, xd[o:o + 4].hex() if o + 4 <= len(xd) else '-'))
            if res and o + 4 <= len(res['data']): cells.append('resident=%08x' % struct.unpack_from('<I', res['data'], o)[0])
            for t, s in cps.items():
                cells.append('%s=%08x' % (t, struct.unpack_from('<I', s['data'], o)[0]) if o + 4 <= len(s['data']) else '%s=-' % t)
            print('  +0x%x %s' % (o, ' '.join(cells)))


if __name__ == '__main__':
    main(sys.argv[1:])
