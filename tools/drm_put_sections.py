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
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/drm_put_sections.py BASE_DRM DONOR_DRM OUT_DRM 8:6,8:21239 [--add-missing]
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    add_missing = '--add-missing' in argv; argv = [a for a in argv if a != '--add-missing']
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
    for n in put:
        r = R.parse(n.reloc, 'le')
        if r.external:
            r.external = [(idx.get(dkey[si], si), a, d) for si, a, d in r.external]
            n.reloc = R.write(r, 'le'); st['relocations remapped'] += 1
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
