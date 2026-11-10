"""One-off (2026-11-11, TruShadowPower 0.26, climb camera modes): decode the per-mode tables of the camera settings
DTPs - TU generalbank DTP 21237 (doppelganger default, big endian) against the PC generalbank DTP 20 (retail default,
little endian, PC patch.000 / bigfile.000 as tools/dtp_word_classes.py) - read-only.

PC code that reads them (tru.exe, S = lookup 0x54df80 result + 0x10 = section data + 0x10):
  table A  S+0x134 count / S+0x138 pointer, 16-byte entries {u32 nModes, u32 *modes, u32 nParams, rec *params};
           0x5f99f0 (eax = S, edi = mode) returns the first entry whose mode list holds the mode and nParams > 0;
           0x601d30 (apply, called by SetMode vslot 0x60 0x6020e0) -> 0x5ff080 applies the 0x18-byte param records
           {u32 kind 1..0x1c, payload} (jump table 0x5ff2a8).
  table B  S+0x13c count / S+0x140 pointer, 12-byte entries {i8 key, pad, u32 nModes, u32 *modes}; 0x5f9960(S, key,
           mode) - key = byte +0x4d of the focus object's +0x24 record (0x5fe800 / 0x5fe8c0, SetMode).
Pointers are resolved through the section's INTERNAL relocations (tools/drm_reloc.py: data+offset -> target).

Helper of tools/tu_dg_modes_inc.py (moved from work/power026_1111 in night package Q26, 2026-11-11, rules unchanged).
Usage (from the repository root): ../bin/pyt -t 300 tools/cam_mode_tables.py [MODE,MODE,..]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtp_word_classes as C  # noqa: E402
import drm_reloc as R  # noqa: E402

BS = chr(92)
# kind -> jump table 0x5ff2a8[kind - 1] (checked against the disassembly of 0x5ff080 .. 0x5ff2a4)
KIND = {1: 'curve 0xda0 (0x5f98e0)', 2: 'float -> +0x1320', 3: 'centre curve 0x1248 (0x5fe7d0)',
        4: 'curve 0x1278 (0x5f9910)', 5: 'inline curve 0x1248', 6: 'inline curve 0x1278', 7: 'curve 0x890',
        8: 'curve 0x8c4', 9: 'float -> +0x133c', 10: 'set 0x3b0 (0x5f9940)', 11: 'set 0x620 (0x5f9940)',
        12: 'flag +0xd', 13: 'float +0x1320 / opt +0x1340', 14: '+0x1324 = 0', 15: 'u32 -> +0x1328',
        16: 'curve 0x8f8 (0x5f98b0)', 17: 'GI+0x160 record (0x5fec00)', 18: '+0x1338 = 0', 19: '+0x1338 = 1',
        20: 'float -> 0x1350 (0x5e8e90)', 21: 'float * k -> +0x132c', 22: 'flag +4 only', 23: 'flag +5 only',
        24: 'flag +6 only', 25: 'flag +7 only', 26: 'flag +8 only', 27: 'flag +9 only', 28: 'flag +0xa only'}


TU_SECS = None
PC_SECS = None


def tu_dtp(i):
    global TU_SECS
    if TU_SECS is None:
        TU_SECS = C.find(C.BASE, 'be', 'xenon-w' + BS + 'generalbank.drm')
    return next(s for s in TU_SECS if s['type'] == 7 and s['id'] == i)


def pc_dtp(i):
    global PC_SECS
    if PC_SECS is None:
        PC_SECS = C.find(C.PC, 'le', 'pc-w' + BS + 'generalbank.drm')
    return next(s for s in PC_SECS if s['type'] == 7 and s['id'] == i)


def camera_settings_like(secs, e):
    """type-7 sections with the head of a camera settings DTP (word0 0xb, S+0 = 3, S+4 = 130.0 as DTP 20 / 21237)"""
    out = []
    for s in secs:
        d = s['data']
        if s['type'] == 7 and len(d) > 0x150 and struct.unpack_from(e + '3I', d, 0)[0] == 0xb and \
                struct.unpack_from(e + 'I', d, 0x10)[0] == 3 and struct.unpack_from(e + 'I', d, 0x14)[0] == 0x43020000:
            out.append(s['id'])
    return out


def load():
    tu_dtp(21237)
    pc_dtp(20)
    tu_ids = camera_settings_like(TU_SECS, '>')
    pc_ids = camera_settings_like(PC_SECS, '<')
    print('camera-settings-like DTPs: TU generalbank %s, PC generalbank %s' % (tu_ids, pc_ids))
    other = [i for i in tu_ids if i != 21237]
    out = [('TU 21237', tu_dtp(21237), '>'), ('PC 20', pc_dtp(20), '<')]
    if len(other) == 1:
        out.append(('TU %d' % other[0], tu_dtp(other[0]), '>'))
    return out


def idrefs(sec, e):
    """{offset: (type, referenced id)} of the section's resource id references (drm_reloc idref / idref_a)"""
    r = R.parse(sec['reloc'], 'be' if e == '>' else 'le')
    d = sec['data']
    return {o: (t, struct.unpack_from(e + 'I', d, o)[0]) for t, o in list(r.idref) + list(r.idref_a)}


def set_records(sec, e):
    """a 'set' DTP as 0x5f9940 reads it: data+0 count, data+4 pointer to 0x6c-byte records"""
    d = sec['data']
    n = struct.unpack_from(e + 'I', d, 0)[0]
    p = ptrs(sec, e)[4]
    return [struct.unpack_from(e + '27I', d, p + 0x6c * k) for k in range(n)]


def ptrs(sec, e):
    r = R.parse(sec['reloc'], 'be' if e == '>' else 'le')
    return {o: t for o, t in r.internal}


def decode(name, sec, e):
    d = sec['data']
    p = ptrs(sec, e)
    refs = idrefs(sec, e)

    def u(o):
        return struct.unpack_from(e + 'I', d, o)[0]

    def ptr(o):
        if o not in p:
            raise ValueError('%s: no internal reloc at +0x%x' % (name, o))
        return p[o]

    S = 0x10
    out = {'A': [], 'B': []}
    nA, aA = u(S + 0x134), ptr(S + 0x138)
    for i in range(nA):
        o = aA + 16 * i
        nm, npar = u(o), u(o + 8)
        modes = [struct.unpack_from(e + 'i', d, ptr(o + 4) + 4 * k)[0] for k in range(nm)] if nm else []
        recs = []
        if npar:
            po = ptr(o + 12)
            for k in range(npar):
                ro = po + 0x18 * k
                recs.append((u(ro), d[ro + 4:ro + 0x18], refs.get(ro + 4)))
        out['A'].append((modes, recs))
    nB, aB = u(S + 0x13c), ptr(S + 0x140)
    for i in range(nB):
        o = aB + 12 * i
        key = struct.unpack_from('b', d, o)[0]
        nm = u(o + 4)
        modes = [struct.unpack_from(e + 'i', d, ptr(o + 8) + 4 * k)[0] for k in range(nm)] if nm else []
        out['B'].append((key, modes))
    return out


def rec_text(kind, payload, e, ref=None):
    f = struct.unpack(e + '5f', payload)
    w = struct.unpack(e + '5I', payload)
    if ref:
        return 'kind %2d %-30s DTP %d [%d]' % (kind, KIND.get(kind, '?'), ref[1], w[1])
    return 'kind %2d %-30s words %s floats %s' % (kind, KIND.get(kind, '?'), ' '.join('%08x' % x for x in w),
                                                  ' '.join('%.4g' % x for x in f))


def set_text(r, e):
    f = struct.unpack(e + '%df' % len(r), struct.pack(e + '%dI' % len(r), *r))
    return ' '.join('%.4g' % x if (w & 0x7f800000) not in (0, 0x7f800000) or w == 0 else '%08x' % w
                    for w, x in zip(r, f))


def main(argv):
    want = [int(x) for x in argv[0].split(',')] if argv else [61, 62, 60, 11, 8, 46, 1, 37]
    res = {}
    for name, sec, e in load():
        res[name] = (decode(name, sec, e), e)
        t = res[name][0]
        print('== %s (%d bytes): table A %d entries, table B %d entries' % (name, len(sec['data']), len(t['A']),
                                                                          len(t['B'])))
        for i, (modes, recs) in enumerate(t['A']):
            print('  A[%2d] modes %s: %d param records' % (i, modes, len(recs)))
            for kind, pl, ref in recs:
                print('        ' + rec_text(kind, pl, e, ref))
        for i, (key, modes) in enumerate(t['B']):
            print('  B[%2d] key %d modes %s' % (i, key, modes))
    print()
    print('== per mode: first table-A entry (0x5f99f0 picks the first with params) and table-B keys')
    for m in want:
        for name in res:
            t, e = res[name]
            hit = next(((i, recs) for i, (modes, recs) in enumerate(t['A']) if m in modes and recs), None)
            keys = [key for key, modes in t['B'] if m in modes]
            if hit:
                print('mode %2d %-8s A[%d] %d records; B keys %s' % (m, name, hit[0], len(hit[1]), keys))
                for kind, pl, ref in hit[1]:
                    print('             ' + rec_text(kind, pl, e, ref))
            else:
                print('mode %2d %-8s no table-A entry (base settings only); B keys %s' % (m, name, keys))

    # the 'set' DTPs the kind 10 / 11 records name (0x6c-byte records, 0x5f9940), by value
    sets = {}
    for name in res:
        t, e = res[name]
        for modes, recs in t['A']:
            for kind, pl, ref in recs:
                if ref and (name[:2], ref[1]) not in sets:
                    sec = tu_dtp(ref[1]) if name.startswith('TU') else pc_dtp(ref[1])
                    sets[(name[:2], ref[1])] = (set_records(sec, e), e)
    print()
    print('== set DTPs (kind 10 / 11 targets): %s' % ', '.join('%s %d: %d records' % (k[0], k[1], len(v[0]))
                                                            for k, v in sorted(sets.items())))

    def set_val(side, ref_id, idx):
        """record words 1..7 only (the seven float parameters); word 0 is a u16 pair and words 8.. hold byte tables /
        curve data whose PC conversion swapped bytes differently, so they are not comparable as u32"""
        recs, e = sets[(side, ref_id)]
        return recs[idx][1:8] if idx < len(recs) else None

    def same_set(a, b):
        """two 0x6c-byte records equal as numbers (both are already unpacked in their own endian)"""
        return a is not None and b is not None and a == b

    # mode-by-mode comparison by VALUE: kind 10 / 11 compared through the record they select
    def entry_val(side, recs):
        out = []
        for kind, pl, ref in recs:
            if ref:
                w = struct.unpack(('>' if side == 'TU' else '<') + '5I', pl)
                out.append((kind, ('set', set_val(side, ref[1], w[1]))))
            else:
                w = struct.unpack(('>' if side == 'TU' else '<') + '5I', pl)
                # a payload word is a number (float / u32: equal as numbers) or a byte field (u8 flags: equal as raw
                # bytes); canonical form = the smaller of the number and its byte swap, so both kinds compare equal
                out.append((kind, tuple(min(x, struct.unpack('<I', struct.pack('>I', x))[0]) for x in w)))
        return sorted(out, key=lambda x: (x[0], repr(x[1])))

    print()
    print('== modes: TU 21237 (doppelganger) vs PC 20 vs the TU retail default, table-A entry by value (set records by '
          'their 7 floats)')
    allmodes = sorted({m for name in res for modes, _ in res[name][0]['A'] for m in modes} |
                      {m for name in res for _, modes in res[name][0]['B'] for m in modes})
    differ = []
    for m in allmodes:
        vals = {}
        for name in res:
            t, e = res[name]
            hit = next((recs for modes, recs in t['A'] if m in modes and recs), None)
            vals[name] = entry_val(name[:2], hit) if hit else None
        third = [n for n in res if n not in ('TU 21237', 'PC 20')]
        a, b = vals['TU 21237'], vals['PC 20']
        c = vals[third[0]] if third else None
        bk = {name: sorted(key for key, modes in res[name][0]['B'] if m in modes) for name in res}
        print('mode %2d: TU 21237 %-6s PC 20 %-6s %s %-6s | 21237 == PC 20: %-3s | %s == PC 20: %-3s | B keys %s' % (
            m, 'entry' if a else 'none', 'entry' if b else 'none', third[0] if third else '-',
            'entry' if c else 'none', 'yes' if a == b else 'NO', third[0] if third else '-',
            'yes' if c == b else 'NO', ' / '.join('%s %s' % (n, bk[n]) for n in res)))
        if a != b:
            differ.append(m)
    print('modes whose TU 21237 table-A entry differs from PC 20 by value: %s' % differ)

    print()
    print('== set records the climb modes select')
    for m in want:
        for name in res:
            t, e = res[name]
            hit = next((recs for modes, recs in t['A'] if m in modes and recs), None)
            for kind, pl, ref in hit or ():
                if not ref:
                    continue
                idx = struct.unpack(e + '5I', pl)[1]
                r = set_val(name[:2], ref[1], idx)
                print('mode %2d %-8s kind %d DTP %d [%d]: %s' % (m, name, kind, ref[1], idx,
                                                                set_text(r, e) if r else 'INDEX OUT OF RANGE'))
                if name.startswith('TU') and r:
                    pcs = [i for i, x in enumerate(sets.get(('PC', 30), ([], '<'))[0]) if same_set(x[1:8], r)]
                    print('             PC DTP 30 records with the same 7 floats: %s' % (pcs or 'none'))


if __name__ == '__main__':
    main(sys.argv[1:])
