"""Read-only survey of one object id in DRMs (test 50k, cut object dlc2_uo_jump_target, object 1042): where a unit
places it, which sections name it, what its own sections contain.

Modes (from the repository root; --be for Xbox big-endian DRMs, default PC little-endian):
  ../bin/pyt -t 300 tools/jump_target_survey.py intros UNIT.drm [--be] [--object ID[,ID]] [--list OBJECTLIST.txt]
      every Intro of the unit (unit_ids.level_info: unit DTP Level+0x74 -> 0x90-byte records, +0x50 u16 object id,
      +0x58 u32 unique id); prints the count per object (names from the object list) and, for the given objects, the
      record as floats / words (+0x00 rotation?, +0x10 position, +0x20 scale? - printed, not interpreted)
  ../bin/pyt -t 300 tools/jump_target_survey.py words DRM TYPE:ID[#N] OFF LEN [--be]
      words of a section (also type 0 sections, #N = the N-th section of that type:id in file order, 0-based) with
      relocation marks: 'P' internal pointer, 'X(t:id+off)' external pointer, 'I(type)' id reference
  ../bin/pyt -t 300 tools/jump_target_survey.py find DRM VALUE[,VALUE] [--be] [--u16]
      every u32 (or, --u16, aligned u16) equal to VALUE (decimal) in every section, with the relocation class of the
      word: an id-reference relocation proves the word is an id (type given by the relocation), a raw word may be anything
  ../bin/pyt -t 300 tools/jump_target_survey.py sections DRM [--be]
      per section: index, type:id, size, relocations, the ids its id relocations name (type:id), printable strings
"""
import sys, os, struct, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import unit_ids as U


def load(path, en):
    return DW.read(open(path, 'rb').read(), en)


def objnames(path):
    d = {}
    if path and os.path.exists(path):
        for l in open(path, encoding='utf8', errors='ignore'):
            p = l.strip().split(',', 1)
            if len(p) == 2 and p[0].isdigit(): d[int(p[0])] = p[1]
    return d


def relmaps(s, en):
    r = R.parse(s.reloc, en)
    ints = dict(r.internal)
    ext = {so: (si, do) for si, so, do in r.external}
    ids = {o: t for t, o in r.idref + r.idref_a}
    return ints, ext, ids


def cmd_intros(argv, en):
    path = argv[0]
    objs = set()
    if '--object' in argv: objs = {int(x) for x in argv[argv.index('--object') + 1].split(',')}
    lst = argv[argv.index('--list') + 1] if '--list' in argv else 'work/generic/lists/dlc_pack11_objectlist.txt'
    names = objnames(lst)
    D = load(path, en)
    secs = [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]
    L = U.level_info(secs, en)
    if L is None: print('not a unit DRM'); return
    E = '>' if en == 'be' else '<'
    cnt = collections.Counter()
    hits = []
    for si, o in L['intros']:
        d = secs[si]['data']
        oid = struct.unpack_from(E + 'H', d, o + 0x50)[0]
        cnt[oid] += 1
        if oid in objs: hits.append((si, o))
    print('%s: %d intros in section %s, %d objects' % (os.path.basename(path), len(L['intros']),
          sorted({si for si, _ in L['intros']}), len(cnt)))
    for oid, n in sorted(cnt.items()):
        print('  object %5d x%-3d %s%s' % (oid, n, names.get(oid, '?'), '   <==' if oid in objs else ''))
    for si, o in hits:
        d = secs[si]['data']
        w = struct.unpack_from(E + '36I', d, o)
        f = struct.unpack_from(E + '36f', d, o)
        print('\nintro at section %d +0x%x: object %d, unique id %d' % (si, o, struct.unpack_from(E + 'H', d, o + 0x50)[0],
              struct.unpack_from(E + 'I', d, o + 0x58)[0]))
        for k in range(0, 36, 4):
            print('  +0x%02x  %s   %s' % (k * 4, ' '.join('%08x' % x for x in w[k:k + 4]),
                                           ' '.join('%12.4f' % x if abs(x) < 1e7 and (x == 0 or abs(x) > 1e-6) else '%12s' % '-' for x in f[k:k + 4])))
        if '--near' in argv:        # other intros within R (position +0x10), nearest first
            rad = float(argv[argv.index('--near') + 1])
            p0 = struct.unpack_from(E + '3f', d, o + 0x10)
            near = []
            for sj, oj in L['intros']:
                if (sj, oj) == (si, o): continue
                dj = secs[sj]['data']; p = struct.unpack_from(E + '3f', dj, oj + 0x10)
                dist = sum((a - b) ** 2 for a, b in zip(p, p0)) ** 0.5
                if dist <= rad:
                    near.append((dist, struct.unpack_from(E + 'H', dj, oj + 0x50)[0], struct.unpack_from(E + 'I', dj, oj + 0x58)[0], p))
            print('  intros within %.0f:' % rad)
            for dist, oid, uid, p in sorted(near):
                print('    %8.1f  object %5d %-40s unique %6d  pos %.1f %.1f %.1f  (dz %+.1f)' % (dist, oid, names.get(oid, '?'), uid, *p, p[2] - p0[2]))
    if objs and not hits: print('\nno intro of object(s) %s' % sorted(objs))


def sec_by_key(D, key):
    m = re.match(r'(\d+):(\d+)(?:#(\d+))?$', key)
    t, i, n = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    c = [k for k, s in enumerate(D.sections) if s.type == t and s.id == i]
    return c[n]


def cmd_words(argv, en):
    D = load(argv[0], en); si = sec_by_key(D, argv[1]); off = int(argv[2], 16); ln = int(argv[3], 16)
    s = D.sections[si]; E = '>' if en == 'be' else '<'
    ints, ext, ids = relmaps(s, en)
    print('section %d %d:%d size %d' % (si, s.type, s.id, len(s.data)))
    for o in range(off & ~3, min(len(s.data) - 3, off + ln), 4):
        v = struct.unpack_from(E + 'I', s.data, o)[0]
        f = struct.unpack_from(E + 'f', s.data, o)[0]
        mark = ''
        if o in ints: mark = 'P->+0x%x' % ints[o]
        elif o in ext: xs, xo = ext[o]; mark = 'X(%d:%d+0x%x)' % (D.sections[xs].type, D.sections[xs].id, xo)
        elif o in ids: mark = 'I(type %d)' % ids[o]
        fs = '%.4f' % f if abs(f) < 1e7 and (f == 0 or abs(f) > 1e-6) else ''
        print('  +0x%05x  %08x  %10d  %-12s %s' % (o, v, v, fs, mark))


def cmd_find(argv, en):
    D = load(argv[0], en); vals = {int(x) for x in argv[1].split(',')}; E = '>' if en == 'be' else '<'
    u16 = '--u16' in argv
    for si, s in enumerate(D.sections):
        ints, ext, ids = relmaps(s, en)
        step = 2 if u16 else 4
        for o in range(0, len(s.data) - step + 1, step):
            v = struct.unpack_from(E + ('H' if u16 else 'I'), s.data, o)[0]
            if v not in vals: continue
            o4 = o & ~3
            cls = 'idref type %d' % ids[o4] if o4 in ids else ('pointer' if o4 in ints or o4 in ext else 'raw')
            print('section %4d %2d:%-6d +0x%06x  %s %d  %s' % (si, s.type, s.id, o, 'u16' if u16 else 'u32', v, cls))


def cmd_sections(argv, en):
    D = load(argv[0], en); E = '>' if en == 'be' else '<'
    for si, s in enumerate(D.sections):
        ints, ext, ids = relmaps(s, en)
        named = collections.Counter()
        for o, t in ids.items():
            if o + 4 <= len(s.data): named['%d:%d' % (t, struct.unpack_from(E + 'I', s.data, o)[0])] += 1
        strs = [x.decode() for x in re.findall(rb'[\x20-\x7e]{5,}', s.data)]
        print('%3d %2d:%-6d %6d B  int %3d ext %3d id %3d  ids %s' % (si, s.type, s.id, len(s.data), len(ints), len(ext),
              len(ids), ' '.join('%s%s' % (k, '' if n == 1 else 'x%d' % n) for k, n in sorted(named.items()))))
        if strs: print('      strings: %s' % ' | '.join(strs[:40]))


def cmd_scanpack(argv, en):
    """every DRM record of a bigfile: intros of the objects, id relocations naming VALUE, raw u32 VALUE count"""
    import json
    from archive import Archive
    pack = argv[0]; vals = {int(x) for x in argv[argv.index('--object') + 1].split(',')}
    names = {}
    for l in open('work/generic/dlc_names.txt', encoding='utf8', errors='ignore'):
        t = l.split()
        if len(t) >= 6: names[int(t[0], 16)] = t[5]
    if '--names' in argv:
        for k, v in json.load(open(argv[argv.index('--names') + 1], encoding='utf8')).items(): names.setdefault(int(k), v)
    A = Archive(pack, en); E = '>' if en == 'be' else '<'
    seen = set(); n = 0
    for r in A.idx:
        if r['hash'] in seen: continue
        try: raw = A.read(r)
        except Exception as e: print('0x%08x read error %s' % (r['hash'], e)); continue
        if raw[:4] != b'CDRM' and (len(raw) < 24 or struct.unpack_from(E + 'i', raw, 0)[0] not in (14, 19, 20, 21, 22)): continue
        try: D = DW.read(raw, en)
        except Exception as e: print('%s: not readable (%s)' % (names.get(r['hash'], '0x%08x' % r['hash']), str(e)[:60])); continue
        seen.add(r['hash']); n += 1
        nm = names.get(r['hash'], '0x%08x' % r['hash'])
        out = []
        secs = [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]
        L = U.level_info(secs, en)
        if L:
            for si, o in L['intros']:
                oid = struct.unpack_from(E + 'H', secs[si]['data'], o + 0x50)[0]
                if oid in vals:
                    pos = struct.unpack_from(E + '3f', secs[si]['data'], o + 0x10)
                    out.append('INTRO object %d unique %d at sec %d +0x%x pos(+0x10) %.1f %.1f %.1f' % (
                        oid, struct.unpack_from(E + 'I', secs[si]['data'], o + 0x58)[0], si, o, *pos))
        raw_hits = collections.Counter()
        for si, s in enumerate(D.sections):
            ints, ext, ids = relmaps(s, en)
            for o, t in ids.items():
                if o + 4 <= len(s.data) and struct.unpack_from(E + 'I', s.data, o)[0] in vals:
                    out.append('IDREF type %d -> %d in %d:%d +0x%x' % (t, struct.unpack_from(E + 'I', s.data, o)[0], s.type, s.id, o))
            for o in range(0, len(s.data) - 3, 4):
                if struct.unpack_from(E + 'I', s.data, o)[0] in vals and o not in ids: raw_hits['%d:%d' % (s.type, s.id)] += 1
            if s.type == 11 and s.id in vals: out.append('OBJECT SECTION 11:%d' % s.id)
        if raw_hits: out.append('raw u32 in ' + ' '.join('%s x%d' % kv for kv in sorted(raw_hits.items())))
        for x in out: print('%-55s %s' % (nm, x))
    print('%d DRMs scanned' % n)


def main(argv):
    en = 'be' if '--be' in argv else 'le'
    argv = [a for a in argv if a != '--be']
    cmd = argv[0]
    {'intros': cmd_intros, 'words': cmd_words, 'find': cmd_find, 'sections': cmd_sections,
     'scanpack': cmd_scanpack}[cmd](argv[1:], en)


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
