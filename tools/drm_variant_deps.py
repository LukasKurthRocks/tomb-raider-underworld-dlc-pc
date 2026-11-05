"""Does anything depend on one variant of a DRM? (read-only). Test 51n (2026-11-05): an upstream kit ships a base-game
DRM as a patch of the PC original; before dropping that variant, list the sections that differ and look for
references to them (and for (type, id) collisions) in every file a test package installs.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/drm_variant_deps.py raw SOURCE NAME.drm OUT.drm
      SOURCE as in tools/locals.py (pcbig, pcpatch, xbase, ...). Writes the entry AS STORED in the archive (no CDRM
      decode); prints size / md5 of the stored and of the decoded form, the container magic and whether
      drm_write.cdrm_encode(decoded) gives the stored bytes back.
  ../bin/pyt -t 300 tools/drm_variant_deps.py form FILE [FILE ...]
      container form of each file: CDRM (block count, block sizes, zlib / raw) or plain DRM; md5 stored / decoded.
  ../bin/pyt -t 300 tools/drm_variant_deps.py diff ORIG.drm VARIANT.drm [--words N]
      sections of both (PC, little endian; CDRM or plain): dependency names, section lists, pairs by (type, id,
      occurrence); per pair: size / flags / ver / spec / data / reloc differences, differing 32-bit words (first N per
      section, default 16), relocation entries that differ (internal / external / id refs).
  ../bin/pyt -t 900 tools/drm_variant_deps.py refs ORIG.drm VARIANT.drm --name NAME --obj ID [--obj-files REGEX]
                                              [--exclude TOP[,TOP]] DIR [DIR ...]
      overlay DIR in order (later wins per relative path; top folders in --exclude skipped, default local,padshock).
      For every DRM of the overlay except NAME itself:
        A  id references (reloc kinds A / resource) to a (type, id) of either variant whose content differs or that
           exists in one variant only
        B  (type, id) collisions: the file has a section with the same (type, id) as a section of either variant
           (General type 0 ignored); content equal / different to each variant
        C  dependency-name entry NAME (the names block), the string NAME in any section
        D  u32 value ID (the object id) in DTP sections, only for files whose name matches --obj-files (default
           handgun), as a pointer to the object users
      Outgoing id references of both variants: resolved in the variant itself / the overlay / work/idx_pc.json.
"""
import sys, os, re, struct, hashlib, collections, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import drm_reloc as R

TYPES = {0: 'general', 2: 'anim', 5: 'texture', 6: 'wave', 7: 'dtp', 8: 'script', 9: 'shaderlib', 10: 'material',
         11: 'object', 12: 'mesh', 13: 'unit'}


def md5(b): return hashlib.md5(b).hexdigest()


def load(path):
    raw = open(path, 'rb').read()
    return raw, DW.read(raw, 'le')


def keyed(D):
    """[(key, section)] with key = (type, id, occurrence of that (type, id))."""
    seen = collections.Counter(); out = []
    for s in D.sections:
        k = (s.type, s.id); out.append(((s.type, s.id, seen[k]), s)); seen[k] += 1
    return out


def idrefs(s):
    """[(kind, ref type, offset, ref id)] of one section (kinds A and resource)."""
    if not s.reloc: return []
    r = R.parse(s.reloc, 'le'); out = []
    for kind, lst in (('A', r.idref_a), ('res', r.idref)):
        for t, o in lst:
            if o + 4 <= len(s.data): out.append((kind, t, o, struct.unpack_from('<I', s.data, o)[0]))
    return out


def names_of(D):
    return [n.decode('latin-1') for n in D.names.split(b'\0') if n]


def cmd_raw(argv):
    import locals as LC
    from archive import Archive
    from names import crc
    src, name, out = argv
    path, e, pre = LC.SRC[src]
    A = Archive(path, e)
    recs = A.find(crc(pre + '\\' + name))
    if not recs: raise SystemExit('%s not in %s' % (name, src))
    for r in recs: print('record: %s' % {k: r[k] for k in sorted(r)})
    stored = A.read(recs[-1])
    dec = DW.cdrm_decode(stored, e)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(stored)
    print('%s from %s (%d records, last used) -> %s' % (name, src, len(recs), out))
    print('stored : magic %r size %d md5 %s' % (stored[:4], len(stored), md5(stored)))
    print('decoded: size %d md5 %s' % (len(dec), md5(dec)))
    if stored[:4] == b'CDRM':
        again = DW.cdrm_encode(DW.read(dec, e).write(e), e)
        print('cdrm_encode(read(decoded).write()) == stored: %s' % (again == stored))


def cmd_form(argv):
    for p in argv:
        raw = open(p, 'rb').read()
        dec = DW.cdrm_decode(raw, 'le')
        if raw[:4] == b'CDRM':
            n, = struct.unpack_from('<I', raw, 8)
            blocks = [struct.unpack_from('<II', raw, 16 + 8 * i) for i in range(n)]
            desc = 'CDRM %d block(s) %s' % (n, ' '.join('%s:%d->%d' % ({2: 'zlib', 1: 'raw'}.get(u & 0xff, u & 0xff), c, u >> 8)
                                                       for u, c in blocks))
        else:
            desc = 'plain DRM (version %d)' % struct.unpack_from('<i', raw, 0)[0]
        D = DW.read(raw, 'le')
        print('%s: %s; stored %d md5 %s; decoded %d md5 %s; %d sections; names %s' % (
            p, desc, len(raw), md5(raw), len(dec), md5(dec), len(D.sections), names_of(D)))


def word_diffs(a, b, limit):
    m = min(len(a), len(b)); out = []
    for o in range(0, m - 3, 4):
        if a[o:o + 4] != b[o:o + 4]: out.append(o)
    return out


def reloc_diff(sa, sb):
    ra = R.parse(sa.reloc, 'le'); rb = R.parse(sb.reloc, 'le'); out = []
    for k in R.Reloc.__slots__:
        la, lb = getattr(ra, k), getattr(rb, k)
        if la != lb:
            xa, xb = set(map(tuple, la)) if la and isinstance(la[0], tuple) else set(la), \
                     set(map(tuple, lb)) if lb and isinstance(lb[0], tuple) else set(lb)
            out.append('%s %d -> %d entries (only orig %s, only variant %s)' % (
                k, len(la), len(lb), sorted(xa - xb)[:8], sorted(xb - xa)[:8]))
    return out


def compare(A, B):
    """pairs: {key: (sa or None, sb or None)}, plus ordered key list"""
    ka = keyed(A); kb = keyed(B)
    da = dict(ka); db = dict(kb)
    keys = [k for k, _ in ka] + [k for k, _ in kb if k not in da]
    return keys, {k: (da.get(k), db.get(k)) for k in keys}


def cmd_diff(argv):
    lim = 16
    if '--words' in argv: k = argv.index('--words'); lim = int(argv[k + 1]); del argv[k:k + 2]
    ra, A = load(argv[0]); rb, B = load(argv[1])
    print('orig    %s: stored md5 %s, %d sections, names %s' % (argv[0], md5(ra), len(A.sections), names_of(A)))
    print('variant %s: stored md5 %s, %d sections, names %s' % (argv[1], md5(rb), len(B.sections), names_of(B)))
    print('header: ver %d/%d u0 %d/%d u1 %d/%d pad %d/%d bytes' % (A.ver, B.ver, A.u0, B.u0, A.u1, B.u1, len(A.pad), len(B.pad)))
    print('section order (type:id) equal: %s' % ([(s.type, s.id) for s in A.sections] == [(s.type, s.id) for s in B.sections]))
    keys, pairs = compare(A, B)
    cnt = collections.Counter()
    for k in keys:
        sa, sb = pairs[k]
        tag = '%s %d:%d#%d' % (TYPES.get(k[0], '?'), k[0], k[1], k[2])
        if sa is None: print('ONLY VARIANT %s size %d' % (tag, len(sb.data))); cnt['only_variant'] += 1; continue
        if sb is None: print('ONLY ORIG    %s size %d' % (tag, len(sa.data))); cnt['only_orig'] += 1; continue
        if sa.data == sb.data and sa.reloc == sb.reloc and (sa.flags, sa.ver, sa.spec) == (sb.flags, sb.ver, sb.spec):
            cnt['equal'] += 1; continue
        cnt['differ'] += 1
        w = word_diffs(sa.data, sb.data, lim)
        print('DIFF %s size %d -> %d, flags %d/%d ver %d/%d spec %#x/%#x, data %s (%d words differ in the common part), reloc %s' % (
            tag, len(sa.data), len(sb.data), sa.flags, sb.flags, sa.ver, sb.ver, sa.spec, sb.spec,
            'equal' if sa.data == sb.data else 'DIFF', len(w), 'equal' if sa.reloc == sb.reloc else 'DIFF'))
        for o in w[:lim]:
            print('     +%04x  orig %s  variant %s' % (o, sa.data[o:o + 4].hex(), sb.data[o:o + 4].hex()))
        if len(w) > lim: print('     ... %d more words' % (len(w) - lim))
        if sa.reloc != sb.reloc:
            for line in reloc_diff(sa, sb): print('     reloc ' + line)
    print('summary: %s' % dict(cnt))


def overlay(dirs, exclude):
    eff = {}
    for d in dirs:
        for root, ds, fs in os.walk(d):
            rel_root = os.path.relpath(root, d)
            top = rel_root.split(os.sep)[0].lower()
            if rel_root != '.' and top in exclude: continue
            for n in fs:
                rel = os.path.normpath(os.path.join(rel_root, n)).lower()
                eff[rel] = os.path.join(root, n)
    return eff


def cmd_refs(argv):
    def opt(name, default=None):
        if name in argv:
            k = argv.index(name); v = argv[k + 1]; del argv[k:k + 2]; return v
        return default
    name = opt('--name'); obj = int(opt('--obj', '-1')); objre = re.compile(opt('--obj-files', 'handgun'), re.I)
    exclude = set(opt('--exclude', 'local,padshock').lower().split(','))
    _, A = load(argv[0]); _, B = load(argv[1]); dirs = argv[2:]
    keys, pairs = compare(A, B)
    changed = {}       # (type, id) -> why
    for k in keys:
        sa, sb = pairs[k]
        if k[0] == 0: continue
        if sa is None: changed[k[:2]] = 'only variant'
        elif sb is None: changed[k[:2]] = 'only orig'
        elif sa.data != sb.data or sa.reloc != sb.reloc: changed[k[:2]] = 'content differs'
    allsec = {}
    for tag, D in (('orig', A), ('variant', B)):
        for s in D.sections:
            if s.type != 0: allsec.setdefault((s.type, s.id), {})[tag] = s
    print('dirs (low -> high): %s' % dirs)
    print('changed (type, id) between orig and variant (General type 0 left out): %d' % len(changed))
    for k in sorted(changed): print('  %s %d:%d  %s' % (TYPES.get(k[0], '?'), k[0], k[1], changed[k]))
    eff = overlay(dirs, exclude)
    drms = sorted(r for r in eff if r.endswith('.drm'))
    print('overlay: %d files, %d .drm (excluded top folders %s)' % (len(eff), len(drms), sorted(exclude)))
    own = name.lower() + '.drm'
    if own in eff: print('overlay copy of %s: %s md5 %s' % (own, eff[own], md5(open(eff[own], 'rb').read())))
    st = collections.Counter(); nb = name.encode('latin-1').lower()
    bsum = collections.defaultdict(collections.Counter)      # (type, id) -> {'orig', 'variant', 'both', 'neither'}
    bvar = collections.defaultdict(list)                     # (type, id) -> files equal to the variant only
    afor = collections.Counter()                             # (own copy?, target) -> referencing files
    for rel in drms:
        if rel == own: continue
        path = eff[rel]
        try: raw = open(path, 'rb').read(); D = DW.read(raw, 'le')
        except Exception as ex: print('SKIP %s: %s' % (rel, ex)); st['skip'] += 1; continue
        st['scanned'] += 1
        mine = {(s.type, s.id) for s in D.sections}
        arefs = collections.Counter()
        for s in D.sections:
            for kind, t, o, rid in idrefs(s):
                if (t, rid) in changed: arefs[(t, rid)] += 1
            if s.type != 0 and (s.type, s.id) in allsec:
                v = allsec[(s.type, s.id)]
                eqs = {tag: (x.data == s.data and x.reloc == s.reloc) for tag, x in v.items()}
                eq = ', '.join('%s %s' % (tag, 'equal' if eqs[tag] else 'DIFFERENT') for tag in sorted(eqs))
                print('B  %s  has %s %d:%d (size %d): %s' % (rel, TYPES.get(s.type, '?'), s.type, s.id, len(s.data), eq))
                st['B'] += 1
                if (s.type, s.id) in changed:
                    cls = 'both' if all(eqs.values()) else 'orig' if eqs.get('orig') else 'variant' if eqs.get('variant') else 'neither'
                    bsum[(s.type, s.id)][cls] += 1
                    if cls == 'variant': bvar[(s.type, s.id)].append(rel)
        for (t, rid), c in sorted(arefs.items()):
            has = (t, rid) in mine
            print('A  %s  %d id ref(s) -> %s %d:%d (%s), own copy in the file: %s' % (
                rel, c, TYPES.get(t, '?'), t, rid, changed[(t, rid)], 'yes' if has else 'NO'))
            st['A_refs'] += c; st['A_files_own_copy' if has else 'A_files_NO_own_copy'] += 1
            afor[('own' if has else 'NO own copy', t, rid)] += 1
            if nb in s.data.lower():
                print('C  %s  section %d:%d contains the string %r' % (rel, s.type, s.id, name)); st['C_str'] += 1
            if obj >= 0 and s.type == 7 and objre.search(rel):
                for o in range(0, len(s.data) - 3, 4):
                    if struct.unpack_from('<I', s.data, o)[0] == obj:
                        print('D  %s  dtp %d +%#x = u32 %d' % (rel, s.id, o, obj)); st['D'] += 1
        if name.lower() in [n.lower() for n in names_of(D)]:
            print('C  %s  lists %s in its dependency names %s' % (rel, name, names_of(D))); st['C_dep'] += 1
    # text files (object lists etc.) naming the DRM
    for rel in sorted(r for r in eff if r.endswith('.txt')):
        try: txt = open(eff[rel], 'rb').read().lower()
        except Exception: continue
        if nb in txt:
            for line in txt.decode('latin-1').splitlines():
                if name.lower() in line: print('C  %s  line %r' % (rel, line.strip()))
            st['C_txt'] += 1
    # outgoing references of both variants
    idx = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'idx_pc.json')
    pcset = collections.Counter()
    if os.path.exists(idx):
        for entry in json.load(open(idx)):
            for sec in entry[5] or []: pcset[(sec[0], sec[1])] += 1
    ovl = collections.defaultdict(list)
    wanted = set()
    for tag, D in (('orig', A), ('variant', B)):
        for s in D.sections:
            for kind, t, o, rid in idrefs(s): wanted.add((t, rid))
    for rel in drms:
        if rel == own: continue
        try: D = DW.read(open(eff[rel], 'rb').read(), 'le')
        except Exception: continue
        for s in D.sections:
            if (s.type, s.id) in wanted: ovl[(s.type, s.id)].append(rel)
    for tag, D in (('orig', A), ('variant', B)):
        own_ids = {(s.type, s.id) for s in D.sections}
        refs = sorted({(t, rid) for s in D.sections for kind, t, o, rid in idrefs(s)})
        print('outgoing id refs of %s: %d distinct' % (tag, len(refs)))
        for t, rid in refs:
            where = []
            if (t, rid) in own_ids: where.append('self')
            if ovl.get((t, rid)): where.append('overlay %s' % ovl[(t, rid)][:4])
            if pcset.get((t, rid)): where.append('pc base x%d' % pcset[(t, rid)])
            print('  %s %d:%d  %s' % (TYPES.get(t, '?'), t, rid, '; '.join(where) or 'UNRESOLVED'))
    print('collisions per changed (type, id): overlay files whose copy equals orig / variant / both / neither')
    for k in sorted(changed):
        c = bsum.get(k, {})
        print('  %s %d:%d (%s): orig %d, variant %d, both %d, neither %d%s' % (
            TYPES.get(k[0], '?'), k[0], k[1], changed[k], c.get('orig', 0), c.get('variant', 0), c.get('both', 0),
            c.get('neither', 0), ('; variant-equal: %s' % bvar[k]) if bvar.get(k) else ''))
    print('id refs to changed (type, id) per target: files with / without an own copy')
    for k in sorted(changed):
        print('  %s %d:%d: own copy %d, NO own copy %d' % (TYPES.get(k[0], '?'), k[0], k[1], afor.get(('own',) + k, 0),
                                                          afor.get(('NO own copy',) + k, 0)))
    print('summary: %s' % dict(st))


def main(argv):
    if not argv: sys.exit(__doc__)
    cmd = argv.pop(0)
    {'raw': cmd_raw, 'form': cmd_form, 'diff': cmd_diff, 'refs': cmd_refs}[cmd](argv)


if __name__ == '__main__':
    main(sys.argv[1:])
