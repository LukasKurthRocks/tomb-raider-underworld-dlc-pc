"""Resolve an enemy's animation requests the way the PC engine does at run time, read only (N22 stage 2, animation lab).

Run-time chain (tru.exe Steam, static, docs/ENGINE.md section 13 "Enemy animation"):
  request record {u16 type, u16 index}; type 1 = index into the object's ANIM SLOT list:
    0x626f10 (anim controller brain+0xc70) -> 0x4325d0(inst, i): 0 <= i < u16 Object+0x38 (= object DTP +0x5c),
    entry = [[Object+0x58]] + i * 0x24 (= object DTP +0x60 list); entry +0x14 u16 = playback speed in 4.12 fixed point
    (0x444c62 / 0x617c7d: * 1/4096 [0x843078] -> 0x438c40), 0 = refused (0x626f45);
    0x616850(Object, entry, 0): entry +0x10 count > 0 -> u16 of the 4-byte list at entry +0xc, else entry +8 count ->
    u16 list at entry +4 -> TABLE index k -> 0x5b4290(Object, k): [Object+0x44] + k * 12 = object DTP +0x58 anim table
    {u16 anim section id (0 = none), s16 run-time slot} -> loaded anim [0x8c1244 + slot * 8].
So the index of a melee / state record is a SLOT index (count +0x5c), not a table index (count +0x54).

This tool reads the object DTP(s) of a PC (little-endian) DRM, resolves every slot i -> table index -> anim section id ->
segment count (type-2 section +0x36 when it is in this DRM), and resolves the melee records both ways (slot = the
engine, table = the stage-1 report `character_anim_report.py`) so differences show.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/anim_slot_resolve.py LABEL=PATH.drm [LABEL=PATH.drm ...] [--slots] [--tsv OUT]
    --slots  print every slot (default: summary + melee + the first 12 slots)
    --tsv    write one line per slot: label, object DTP, slot, list kind, table index, section id, segments, speed
Exit 0 when every melee record resolves to the same section both ways, 1 when at least one differs (printed), 2 usage.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import character_anim_report as CAR


def slot_table(raw):
    """[(object DTP id, [slot dicts], table [section ids], anim_sections)] for every object DTP with both lists"""
    d = DW.read(raw, 'le')
    sections = CAR.analyse(raw, 'le')['anim_sections']
    out = []
    for s in d.sections:
        if s.type != 7 or len(s.data) < 0xcc:
            continue
        dd = bytes(s.data)
        it = dict(R.parse(bytes(s.reloc), 'le').internal)
        if 0x58 not in it or 0x60 not in it:
            continue
        na = struct.unpack_from('<I', dd, 0x54)[0]
        ns = struct.unpack_from('<I', dd, 0x5c)[0]
        pt, ps = it[0x58], it[0x60]
        if not (0 < na < 4000) or not (0 < ns < 4000) or pt + 12 * na > len(dd) or ps + 0x24 * ns > len(dd):
            continue
        table = [struct.unpack_from('<H', dd, pt + 12 * k)[0] for k in range(na)]
        slots = []
        for i in range(ns):
            e = ps + 0x24 * i
            cnt_a, cnt_b = struct.unpack_from('<I', dd, e + 8)[0], struct.unpack_from('<I', dd, e + 0x10)[0]
            speed = struct.unpack_from('<H', dd, e + 0x14)[0]
            kind, lst, stride, cnt = ('B', it.get(e + 0xc), 4, cnt_b) if cnt_b > 0 else ('A', it.get(e + 4), 2, cnt_a)
            idx = []
            if lst is not None and cnt:
                for q in range(min(cnt, 16)):
                    if lst + stride * q + 2 <= len(dd):
                        idx.append(struct.unpack_from('<H', dd, lst + stride * q)[0])
            k0 = idx[0] if idx else None
            sid = table[k0] if k0 is not None and k0 < na else None
            seg = sections[sid]['segments'] if sid in sections else None
            slots.append({'slot': i, 'kind': kind, 'count': cnt, 'table': idx, 'section': sid, 'segments': seg,
                          'speed': speed})
        out.append((s.id, slots, table, sections))
    return out


def main():
    a = sys.argv[1:]
    specs = [x for x in a if '=' in x and not x.startswith('--')]
    if not specs:
        print(__doc__)
        return 2
    tsv = open(a[a.index('--tsv') + 1], 'w', encoding='utf-8', newline='\n') if '--tsv' in a else None
    if tsv:
        tsv.write('label\tobject_dtp\tslot\tlist\ttable_index\tsection\tsegments\tspeed_4_12\n')
    differ = 0
    for sp in specs:
        label, path = sp.split('=', 1)
        raw = open(path, 'rb').read()
        rep = CAR.analyse(raw, 'le')
        for oid, slots, table, sections in slot_table(raw):
            if oid != rep.get('object_dtp'):
                continue
            zero = sum(1 for x in slots if x['speed'] == 0)
            unresolved = sum(1 for x in slots if x['section'] is None)
            segc = {}
            for x in slots:
                segc[x['segments']] = segc.get(x['segments'], 0) + 1
            print('%s: object DTP %d: %d slots (bound of a type-1 request), table %d; speed 0 (refused) %d; '
                  'no table entry %d; slot segment counts %s' % (label, oid, len(slots), len(table), zero, unresolved,
                                                                 dict(sorted(segc.items(), key=lambda z: str(z[0])))))
            for m in rep['melee']:
                for ty, ix, via_table in m['refs']:
                    if ty != 1:
                        continue
                    via_slot = slots[ix]['section'] if ix < len(slots) else 'OUT OF RANGE'
                    same = via_slot == via_table
                    differ += 0 if same else 1
                    print('    melee%-2d tune %d {1, %3d}: slot -> table %s -> section %s | stage-1 table reading -> %s%s'
                          % (m['slot'], m['tune'], ix, slots[ix]['table'] if ix < len(slots) else '-', via_slot,
                             via_table, '' if same else '   <-- DIFFERS'))
            for x in (slots if '--slots' in a else slots[:12]):
                print('    slot %4d: list %s x%d -> table %s -> section %s (%s seg), speed 0x%04x' % (
                    x['slot'], x['kind'], x['count'], x['table'][:4], x['section'], x['segments'], x['speed']))
            if tsv:
                for x in slots:
                    tsv.write('%s\t%d\t%d\t%s\t%s\t%s\t%s\t%d\n' % (label, oid, x['slot'], x['kind'],
                              x['table'][0] if x['table'] else '', x['section'] if x['section'] is not None else '',
                              x['segments'] if x['segments'] is not None else '', x['speed']))
    if tsv:
        tsv.close()
    print('melee references that resolve differently (slot vs table reading): %d' % differ)
    return 1 if differ else 0


if __name__ == '__main__':
    sys.exit(main())
