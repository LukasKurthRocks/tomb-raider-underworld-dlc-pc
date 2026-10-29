"""Merge a converted DLC DRM with the PC base game's own version of the same file (e.g. g_pda.drm), instead of
replacing the PC file (which would drop PC-only sections and PC bytes the converter does not reproduce exactly).

Starting from the converted file (section order and all DLC sections kept):
  * a section the pack ships unchanged from the Xbox base game (same (type, id) and bytes) takes the PC base section
    (data + relocations) of the mapped PC id;
  * sections the pack changed or added stay as converted;
  * PC base sections that the converted file does not have (PC-only sections, base sections the pack dropped) are
    appended, so PC scripts still find everything they reference.
Then the result is read back and every section's relocations are bounds-checked. Classification: tools/gpda_compare.py.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/drm_merge_pc.py CONVERTED_DRM OUT_DRM --pack pack11 [NAME]
  NAME defaults to the file name of CONVERTED_DRM (e.g. g_pda.drm)
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtp_word_classes as C
import drm_write as DW, drm_reloc as R

BS = chr(92)


def main(argv):
    pack = None
    if '--pack' in argv: k = argv.index('--pack'); pack = argv[k + 1]; del argv[k:k + 2]
    if pack is None: sys.exit('--pack pack10|pack11 is required (which pack the converted file came from)')
    conv, out = argv[0], argv[1]
    name = argv[2] if len(argv) > 2 else os.path.basename(conv)
    import dlc_generic as DG
    ids = DG.DlcIds()
    xb = {(s['type'], s['id']): s['data'] for s in C.find(C.BASE, 'be', 'xenon-w' + BS + name)}
    pk = {(s['type'], s['id']): s['data'] for s in C.find([C.DLC_ROOT + q for q in C.PACKS if q.endswith('/%s.000' % pack)],
                                                          'be', 'xenon-w' + BS + name)}
    pc_secs = C.find(C.PC, 'le', 'pc-w' + BS + name)
    pc = {(s['type'], s['id']): s for s in pc_secs}
    D = DW.read(open(conv, 'rb').read(), 'le')
    # Xbox key of each converted section: the pack sections mapped to PC ids
    to_xbox = {(t, ids(t, i)): (t, i) for (t, i) in pk}
    st = collections.Counter()
    from_pc = []                                 # sections whose bytes come from the PC file (their relocations need remapping)
    for s in D.sections:
        xk = to_xbox.get((s.type, s.id))
        if xk is None: st['unmapped (kept)'] += 1; continue
        if xk in xb and xb[xk] == pk[xk] and (s.type, s.id) in pc:
            p = pc[(s.type, s.id)]
            if s.data == p['data'] and s.reloc == p['reloc']: st['base-same, already = PC'] += 1
            else: st['base-same, PC bytes taken'] += 1; s.data = p['data']; s.reloc = p['reloc']; from_pc.append(s)
        else:
            st['changed/new (converted kept)'] += 1
    have = {(s.type, s.id) for s in D.sections}
    for p in pc_secs:
        if (p['type'], p['id']) in have: continue
        n = DW.Section(p['type'], p['id'], p['data'], p['reloc'], flags=p.get('flags', 0), ver=p.get('ver', 0),
                       spec=p.get('spec', 0xffffffff))
        D.sections.append(n); from_pc.append(n); st['PC-only section appended'] += 1
    # external relocations address other sections by their index in the file: PC index -> index in the merged file
    pc_key = [(p['type'], p['id']) for p in pc_secs]
    idx = {(s.type, s.id): i for i, s in enumerate(D.sections)}
    for s in from_pc:
        r = R.parse(s.reloc, 'le')
        if not r.external: continue
        try:
            r.external = [(idx[pc_key[si]], a, b) for si, a, b in r.external]
        except KeyError as e:
            sys.exit('section %d:%d refers to PC section %s, which the merged file lacks' % (s.type, s.id, e))
        s.reloc = R.write(r, 'le'); st['relocations remapped'] += 1
    raw = D.write('le')
    E = DW.read(DW.cdrm_encode(raw, 'le'), 'le')
    infos = [dict(size=len(s.data)) for s in E.sections]
    bad = sum(bool(R.check(R.parse(s.reloc, 'le'), len(s.data), infos)) for s in E.sections)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(DW.cdrm_encode(raw, 'le'))
    print('%s: %s' % (name, dict(st)))
    print('written %s: %d sections, read back ok, sections with relocations out of bounds: %d' % (out, len(E.sections), bad))


if __name__ == '__main__':
    main(sys.argv[1:])
