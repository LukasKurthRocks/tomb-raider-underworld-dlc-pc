"""Put chosen sections of a donor DRM into a base DRM (replace or add), e.g. the converted title-update loading screen
script of generalbank.drm into the installed PC generalbank (finding 42). Read-only on the inputs, writes OUT.

Each listed section (type:id, ids as in the donor = PC ids) replaces the base section with the same key or is
appended. Its external relocations address sections by their index in the donor file; they are remapped to the
index of the same (type, id) in the result - a donor section that refers to a section the base does not have is
reported (use --add-missing to append those too). The result is read back and every section's relocations are
bounds-checked.

LIMIT (learned the hard way, DLC 2 test 2): only the target SECTION of an external relocation is remapped, not the
OFFSET inside it. Calls from a script into another script address a function/member at an offset of that script; if
the base's version of the target script has another layout than the donor's, the offset is wrong (213 of the 1 020
external relocations of the converted title-update loading screen -> the game jumped to address 2 and crashed).
Safe only when every target section is laid out the same in donor and base.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/drm_put_sections.py BASE_DRM DONOR_DRM OUT_DRM 8:6,8:21239 [--add-missing] [--xbox NAME]
  --xbox NAME (e.g. generalbank.drm): remap call offsets into scripts whose base version has another layout, with
  script_conv.offset_map (Xbox title-update script -> base script, elements matched by name); unmatched offsets are
  reported as UNRESOLVED (the donor calls something the base script does not have)
  --retail: with --xbox, take the Xbox scripts from the retail layers instead of the title update (for a donor
  converted from retail, e.g. as a control test)
  --symbols JSON: names the learned symbol map lacks ({"symbols": {xbox: pc}}, tools/sym_calibration_check.py) - without
  it unknown names are paired by position, which picked the neighbour of look-alike natives (DLC 2 test 5c:
  10 calls into scripts 63 / 87 went to the wrong engine function -> crash)
NOTE: data/pc is a junction to the game folder - after a test install, data/pc/mods/<name> is the TEST file. Use a
saved copy of the installed file as BASE (e.g. the Install-TruTree backup).
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def put_keys(put):
    return {(n.type, n.id) for n in put}


def offset_maps(xbox_name, dsec, bsec, retail=False, symbols=None):
    """{(8, PC id): {donor (Xbox-layout) offset -> base (PC-layout) offset}} for every script of the donor that the base
    has in another version - script_conv.offset_map on the Xbox source script (title update, then retail layers) and
    the base script; elements are matched by name Symbol through the learned base symbol map, extended by `symbols`
    (JSON {"symbols": {xbox: pc}}, e.g. work/rebuild/sym_base_evidence.json) for names the map does not know"""
    import json, dtp_word_classes as C, dlc_generic as DG, script_conv as SC
    ids = DG.DlcIds()
    xsecs = C.find(C.BASE[1:] if retail else C.BASE, 'be', 'xenon-w' + chr(92) + xbox_name)
    by_pc = {}
    for s in xsecs:
        if s['type'] == 8 and s['data']: by_pc[(8, ids(8, s['id']))] = s
    symmap = dict(ids.base.get(DG.SYM, {}))
    if symbols:
        extra = {int(a): b for a, b in json.load(open(symbols))['symbols'].items() if int(a) not in symmap}
        symmap.update(extra); print('symbol map for offset matching: +%d names from %s' % (len(extra), symbols))
    out = {}
    for k, b in bsec.items():
        if k[0] != 8 or k not in by_pc or k not in dsec or dsec[k].data == b.data: continue
        x = by_pc[k]
        try:
            out[k] = SC.offset_map(x['data'], R.parse(x['reloc'], 'be'), b.data, R.parse(b.reloc, 'le'), symmap)
        except Exception as e:
            print('offset map failed for %d:%d: %s' % (k[0], k[1], e))
    return out


def main(argv):
    add_missing = '--add-missing' in argv; argv = [a for a in argv if a != '--add-missing']
    xbox_name = None
    if '--xbox' in argv: k = argv.index('--xbox'); xbox_name = argv[k + 1]; del argv[k:k + 2]
    retail = '--retail' in argv; argv = [a for a in argv if a != '--retail']   # donor converted from the retail layers
    symbols = None
    if '--symbols' in argv: k = argv.index('--symbols'); symbols = argv[k + 1]; del argv[k:k + 2]
    base, donor, out = argv[0], argv[1], argv[2]
    want = [tuple(int(v) for v in x.split(':')) for x in argv[3].split(',')]
    B = DW.read(open(base, 'rb').read(), 'le'); Dn = DW.read(open(donor, 'rb').read(), 'le')
    dkey = [(s.type, s.id) for s in Dn.sections]; dsec = {(s.type, s.id): s for s in Dn.sections}
    st = collections.Counter(); todo = list(want); done = set(); put = []
    while todo:
        k = todo.pop(0)
        if k in done: continue
        done.add(k)
        if k not in dsec: sys.exit('donor has no section %d:%d' % k)
        s = dsec[k]
        i = next((n for n, b in enumerate(B.sections) if (b.type, b.id) == k), None)
        n = DW.Section(s.type, s.id, s.data, s.reloc, flags=s.flags, ver=s.ver, spec=s.spec)
        if i is None: B.sections.append(n); st['added'] += 1
        else: B.sections[i] = n; st['replaced'] += 1
        put.append(n)
        have = {(b.type, b.id) for b in B.sections}
        for si, a, d in R.parse(s.reloc, 'le').external:
            tk = dkey[si]
            if tk in have: continue
            if add_missing: todo.append(tk); st['missing target added'] += 1
            else: st['missing target %d:%d' % tk] += 1
    idx = {(b.type, b.id): n for n, b in enumerate(B.sections)}
    bsec = {(b.type, b.id): b for b in B.sections}
    omap = offset_maps(xbox_name, dsec, bsec, retail, symbols) if xbox_name else None
    unresolved = collections.Counter()
    for n in put:
        r = R.parse(n.reloc, 'le')
        if r.external:
            ext = []
            for si, a, d in r.external:
                tk = dkey[si]; tb = bsec.get(tk); td = dsec.get(tk)
                if omap is not None and tb is not None and td is not None and tb.data != td.data and tk not in put_keys(put):
                    m = omap.get(tk)
                    if m is None: st['offset kept: target %d:%d not a mappable script' % tk] += 1
                    elif d in m:
                        if m[d] != d: st['call offsets remapped'] += 1
                        d = m[d]
                    else: unresolved[tk] += 1
                ext.append((idx.get(tk, si), a, d))
            r.external = ext
            n.reloc = R.write(r, 'le'); st['relocations remapped'] += 1
    if unresolved:
        st['UNRESOLVED call offsets'] = sum(unresolved.values())
        print('unresolved call offsets per target script (no matching function/member on PC):',
              ', '.join('%d:%d x%d' % (k[0], k[1], v) for k, v in unresolved.most_common()))
    raw = B.write('le')
    E = DW.read(DW.cdrm_encode(raw, 'le'), 'le')
    infos = [dict(size=len(x.data)) for x in E.sections]
    bad = sum(bool(R.check(R.parse(x.reloc, 'le'), len(x.data), infos)) for x in E.sections)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(DW.cdrm_encode(raw, 'le'))
    print(dict(st))
    print('written %s: %d sections (base %d), read back ok, sections with relocations out of bounds: %d' % (
        out, len(E.sections), len(DW.read(open(base, 'rb').read(), 'le').sections), bad))


if __name__ == '__main__':
    main(sys.argv[1:])
