"""Skeleton + animation report of character DRMs, PC and Xbox, read only (N22 stage 1, Animations-Labor).

Per DRM:
  skeleton  every model DTP (word0 0x04c20453): segment count and the parent list (segment +0x38 = parent index,
            -1 = root; layout tools/model_skeleton_dump.py) -> signature = (count, parents)
  anims     the object DTP's anim table (+0x54 count, +0x58 ptr: 12-byte entries {u16 anim section id, u16 -1,
            u32 DTP id (idref), ptr}); per anim the type-2 section header if it is in this DRM: +0x30 u16 id,
            +0x32 u16 (probably key frames), +0x34 u16 (meaning open, printed as 'frames'), +0x36 u8 segment count
  slots     the object DTP's anim slot list (+0x5c count, +0x60 ptr, 0x24-byte entries; Anim request 0x444ba0)
  melee     enemy data (u32 0xdaf00018 in the object DTP; +0x18 tune count, +0x1c tune ptr array), per tune the 12
            meleeAttack record pointers (+0x80..+0xac), per record the anim refs +0x78 / +0x7c / +0x80 / +0x88 windup
            {u16 type (1 = object anim table index), u16 index} -> anim section id
Then a compatibility table: which skeletons are identical (same count + parent list) and, per character, how many of
its anims match its own / another skeleton's segment count.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/character_anim_report.py LABEL=SRC:NAME [LABEL=SRC:NAME ...] [--anims] [--json OUT]
    SRC = pc (game folder mods, path from env TRU_GAME_MODS or the argument as a path), raw-le / raw-be (file path),
          pcbase / xbase / xdlc (archives, see tools/model_skeleton_dump.py load())
    --anims lists every anim (id, frames, segments); default: counts only
Exit 0; prints the report.
"""
import sys, os, struct, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import model_skeleton_dump as M


def read_any(src, name):
    if src == 'pc':
        base = os.environ.get('TRU_GAME_MODS', '')
        p = os.path.join(base, name) if base and not os.path.isabs(name) else name
        return open(p, 'rb').read(), 'le'
    if src == 'raw-le':
        return open(name, 'rb').read(), 'le'
    if src == 'raw-be':
        return open(name, 'rb').read(), 'be'
    return M.load(src, name), ('be' if src in ('xbase', 'xdlc') else 'le')


def analyse(raw, e):
    f = '>' if e == 'be' else '<'
    d = DW.read(raw, e)
    res = {'skeletons': [], 'anims': [], 'slots': 0, 'melee': [], 'anim_sections': {}}
    for sid, n, hdr, segs, size in M.models(raw, e):
        parents = tuple((s[15] if s[15] != 0xffffffff else -1) for s in segs)
        res['skeletons'].append({'dtp': sid, 'segments': n, 'parents': parents})
    for s in d.sections:
        if s.type == 2 and len(s.data) >= 0x38:
            dd = bytes(s.data)
            # +0x30 u16 id, +0x32 u16 (probably the key-frame count: 4 / 15 / 24 / 30 / 60), +0x34 u16 (100..210,
            # meaning open - called 'frames' in the output only as a field name), +0x36 u8 segment count
            res['anim_sections'][s.id] = {'frames': struct.unpack_from(f + 'H', dd, 0x34)[0],
                                          'h32': struct.unpack_from(f + 'H', dd, 0x32)[0],
                                          'segments': dd[0x36],
                                          'size': len(dd)}
    for s in d.sections:
        if s.type != 7 or len(s.data) < 0xcc:
            continue
        dd = bytes(s.data)
        rel = R.parse(bytes(s.reloc), e)
        it = dict(rel.internal)
        if 0x58 not in it or 0x60 not in it:
            continue
        na = struct.unpack_from(f + 'I', dd, 0x54)[0]
        p = it[0x58]
        if not (0 < na < 2000) or p + 12 * na > len(dd):
            continue
        res['object_dtp'] = s.id
        res['slots'] = struct.unpack_from(f + 'I', dd, 0x5c)[0]
        table = [struct.unpack_from(f + 'H', dd, p + 12 * k)[0] for k in range(na)]
        res['anims'] = table
        o = dd.find(struct.pack(f + 'I', 0xdaf00018))
        while o >= 0 and o % 4:
            o = dd.find(struct.pack(f + 'I', 0xdaf00018), o + 1)
        if o >= 0 and (o + 0x1c) in it:
            nt = struct.unpack_from(f + 'I', dd, o + 0x18)[0]
            arr = it[o + 0x1c]
            for k in range(min(nt, 8)):
                tp = it.get(arr + 4 * k)
                if tp is None:
                    continue
                for j in range(12):
                    m = it.get(tp + 0x80 + 4 * j)
                    if m is None or m + 0x8c > len(dd):
                        continue
                    refs = []
                    for q in (0x78, 0x7c, 0x80, 0x88):
                        ty, ix = struct.unpack_from(f + 'HH', dd, m + q)
                        refs.append((ty, ix, table[ix] if ty == 1 and ix < len(table) else None))
                    res['melee'].append({'tune': k, 'slot': j + 1, 'record': m,
                                         'flags': struct.unpack_from(f + 'I', dd, m + 8)[0], 'refs': refs})
        break
    return res


def main():
    a = sys.argv[1:]
    specs = [x for x in a if '=' in x and not x.startswith('--')]
    if not specs:
        print(__doc__)
        return 2
    out = {}
    for sp in specs:
        label, rest = sp.split('=', 1)
        src, name = rest.split(':', 1)
        try:
            raw, e = read_any(src, name)
            out[label] = analyse(raw, e)
        except Exception as ex:          # missing file / archive entry: report, go on
            out[label] = {'error': str(ex)}
    sigs = {}
    for label, r in out.items():
        if 'error' in r:
            print('%-28s ERROR %s' % (label, r['error']))
            continue
        sk = r['skeletons']
        main_sk = max(sk, key=lambda x: x['segments']) if sk else None
        segc = collections.Counter(v['segments'] for v in r['anim_sections'].values())
        inlist = [i for i in r['anims'] if i in r['anim_sections']]
        print('%-28s models %s | object DTP %s: anim table %d (in this DRM %d), slots %d, melee records %d | anim segment counts %s' % (
            label, ','.join('%d:%dseg' % (x['dtp'], x['segments']) for x in sk) or '-', r.get('object_dtp', '-'),
            len(r['anims']), len(inlist), r['slots'], len(r['melee']), dict(segc)))
        if main_sk:
            sigs[label] = (main_sk['segments'], main_sk['parents'])
        if '--anims' in a:
            for k, i in enumerate(r['anims']):
                h = r['anim_sections'].get(i)
                print('    anim[%3d] id %5d %s' % (k, i, ('frames %d segments %d' % (h['frames'], h['segments'])) if h else '(other DRM)'))
        for m in r['melee']:
            print('    melee%-2d tune %d rec +0x%x flags %08x refs %s' % (m['slot'], m['tune'], m['record'], m['flags'],
                  ' '.join('%d:%d->%s' % (t, i, s) for t, i, s in m['refs'] if t)))
    print('\nskeleton groups (identical segment count + parent list):')
    groups = collections.defaultdict(list)
    for label, sg in sigs.items():
        groups[sg].append(label)
    for k, (sg, labels) in enumerate(sorted(groups.items(), key=lambda x: -x[0][0])):
        print('  group %d: %d segments: %s' % (k + 1, sg[0], ', '.join(sorted(labels))))
    if '--json' in a:
        p = a[a.index('--json') + 1]
        json.dump({k: {kk: (vv if kk != 'anim_sections' else {str(x): y for x, y in vv.items()}) for kk, vv in v.items()}
                   for k, v in out.items()}, open(p, 'w'), indent=1, default=list)
    return 0


if __name__ == '__main__':
    sys.exit(main())
