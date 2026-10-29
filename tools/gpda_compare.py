"""Compare the versions of a DRM that the base game and the DLC packs both ship (default g_pda.drm), section by section.
(read-only; plan for merging DLC sections into the PC version instead of replacing the PC file)

Versions: Xbox base (title update first, then layers), PC base (patch.000 first), pack10, pack11, and optionally a
converted file of ours. Sections are keyed by (type, Xbox id); PC ids are mapped with dlc_generic.DlcIds.
Classes of each pack section against the Xbox base:
  base-same   the pack ships the base section unchanged -> on PC the PC base section can be used as it is
  changed     the pack changed a base section           -> must come from the conversion (or be merged by hand)
  new         only in the pack                           -> must come from the conversion
For base-same sections the converted file (if given) is compared with the PC base section: equal = the converter
already reproduces the PC bytes; different = merging takes the PC bytes (PC-only patches survive).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/gpda_compare.py [NAME] [--ours CONVERTED_DRM] [--pack pack11]
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtp_word_classes as C
import drm_write as DW

BS = chr(92)
TYPES = {0: 'general', 2: 'type2', 5: 'texture', 6: 'wave', 7: 'DTP', 8: 'script', 9: 'shader', 10: 'material',
         11: 'Obj', 12: 'mesh', 13: 'type13'}


def secs_xbox(paths, name):
    S = C.find(paths, 'be', 'xenon-w' + BS + name)
    return None if S is None else {(s['type'], s['id']): s['data'] for s in S}


def main(argv):
    ours = None; pack = 'pack11'
    if '--ours' in argv: k = argv.index('--ours'); ours = argv[k + 1]; del argv[k:k + 2]
    if '--pack' in argv: k = argv.index('--pack'); pack = argv[k + 1]; del argv[k:k + 2]
    name = argv[0] if argv else 'g_pda.drm'
    import dlc_generic as DG
    ids = DG.DlcIds()
    xb = secs_xbox(C.BASE, name)
    pc = {(s['type'], s['id']): s['data'] for s in C.find(C.PC, 'le', 'pc-w' + BS + name)}
    pk = {p: secs_xbox([C.DLC_ROOT + q for q in C.PACKS if q.endswith('/%s.000' % p)], name) for p in ('pack10', 'pack11')}
    print('%s sections: Xbox base %d, PC base %d, pack10 %s, pack11 %s' % (name, len(xb), len(pc),
          len(pk['pack10']) if pk['pack10'] else '-', len(pk['pack11']) if pk['pack11'] else '-'))
    print('Xbox base sections without a PC section of the mapped id: %d' % sum(1 for (t, i) in xb if (t, ids(t, i)) not in pc))
    o = None
    if ours:
        o = {(s.type, s.id): s.data for s in DW.read(open(ours, 'rb').read(), 'le').sections}
    for p in ('pack10', 'pack11'):
        P = pk[p]
        if not P: continue
        cls = collections.Counter(); bytype = collections.defaultdict(collections.Counter); conv = collections.Counter()
        for k, d in P.items():
            c = 'new' if k not in xb else 'base-same' if xb[k] == d else 'changed'
            cls[c] += 1; bytype[c][TYPES.get(k[0], k[0])] += 1
            if o is not None and p == pack and c == 'base-same':
                pk_ = (k[0], ids(k[0], k[1]))
                if pk_ not in pc: conv['no PC section'] += 1
                elif pk_ not in o: conv['not in ours'] += 1
                elif o[pk_] == pc[pk_]: conv['ours = PC'] += 1
                else:
                    conv['ours != PC'] += 1; conv['ours != PC, %s%s' % (TYPES.get(k[0], k[0]),
                                                  ', same size' if len(o[pk_]) == len(pc[pk_]) else ', size differs')] += 1
        print('%s vs Xbox base: %s' % (p, dict(cls)))
        for c in ('changed', 'new'):
            print('   %-8s %s' % (c, dict(bytype[c].most_common())))
        if conv: print('   base-same sections in our converted file vs PC base: %s' % dict(conv))
        only_base = [k for k in xb if k not in P]
        if only_base: print('   in Xbox base but not in %s: %d' % (p, len(only_base)))


if __name__ == '__main__':
    main(sys.argv[1:])
