"""Which sections refer to the textures / DTPs the Xbox title update (TU) changed or added in a base-game DRM?
(read-only; docs: TU coverage audit)

For every TU section of the given types that is new or differs from Xbox retail, the TU sections that refer to it
(section relocation or id reference, as tools/drm_idrefs.py reads them), and whether the PC game has a section with
the mapped id. Without any reference it may still be used by id in plain words - listed as "no reloc".

Usage (from the repository root):
  ../bin/pyt -t 300 tools/tu_section_users.py [NAME] [--types 5,7]
  NAME default generalbank.drm; ids >= 1000 are also searched as aligned u32 words in the TU scripts and DTPs
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import dtp_word_classes as C

BS = chr(92)


def main(argv):
    types = {5, 7}
    if '--types' in argv: k = argv.index('--types'); types = {int(x) for x in argv[k + 1].split(',')}; del argv[k:k + 2]
    name = argv[0] if argv else 'generalbank.drm'
    import dlc_generic as DG
    ids = DG.DlcIds()
    tu = C.find([C.BASE[0]], 'be', 'xenon-w' + BS + name)
    rt = {(s['type'], s['id']): s['data'] for s in C.find(C.BASE[1:], 'be', 'xenon-w' + BS + name)}
    pc = {(s['type'], s['id']) for s in C.find(C.PC, 'le', 'pc-w' + BS + name)}
    users = collections.defaultdict(set)
    for s in tu:
        if not s['reloc']: continue
        rel = R.parse(s['reloc'], 'be')
        for si, so, do in rel.external:
            if si < len(tu): users[(tu[si]['type'], tu[si]['id'])].add('%d:%d' % (s['type'], s['id']))
        for t, o in list(rel.idref_a) + list(rel.idref):     # id references (drm_idrefs.py): the id is the u32 at o
            if o + 4 <= len(s['data']):
                users[(t, struct.unpack_from('>I', s['data'], o)[0])].add('%d:%d' % (s['type'], s['id']))
    words = collections.defaultdict(set)    # id as an aligned big-endian u32 in a script / DTP (a by-id reference)
    want = {s['id'] for s in tu if s['type'] in types and rt.get((s['type'], s['id'])) != s['data']}
    for s in tu:
        if s['type'] not in (7, 8) or not s['data']: continue
        d = s['data']
        for v in set(struct.unpack_from('>%dI' % (len(d) // 4), d)) & want:
            words[v].add('%d:%d' % (s['type'], s['id']))
    rows = collections.Counter()
    for s in tu:
        k = (s['type'], s['id'])
        if k[0] not in types or rt.get(k) == s['data']: continue
        c = 'new' if k not in rt else 'changed'
        pid = ids(k[0], k[1])
        on_pc = 'PC yes (%s)' % pid if (k[0], pid) in pc else 'PC no'
        u = sorted(users.get(k, ()))
        rows[(k[0], c, bool(u))] += 1
        w = sorted(words.get(k[1], ())) if k[1] >= 1000 else []     # small ids are too common as plain words
        print('%d:%-6d %-7s %6d B  %-14s used by %s; id word in %s' % (
            k[0], k[1], c, len(s['data'] or b''), on_pc, ' '.join(u[:12]) + (' ...' if len(u) > 12 else '') if u else 'no reloc',
            ' '.join(w[:12]) if w else ('-' if k[1] >= 1000 else 'not searched (id < 1000)')))
    print('summary (type, class, has reloc users):', dict(rows))


if __name__ == '__main__':
    main(sys.argv[1:])
