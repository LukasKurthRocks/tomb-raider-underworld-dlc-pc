"""State records of a player state chart: header (10 u16), activity list (+0x14, count +0x0a, 8-byte entries) and
the u16 lists +0x18 (state ids, count +0x0c), +0x1c (transition indices, count +0x0e), +0x20 (count +0x10) - check
their byte order against the Xbox original and the PC registries, and with --out repair them (read-only unless --out;
test 48 crash 2026-10-31, AV tru+0x385dc6 with id 0x29).

Readers in tru.exe (2008 Steam build):
* 0x785cc0 thiscall(machine, state record, depth) - called from 0x785e70 (machine start 0x787e00 and every update):
  ebp = [rec+0x14], loop u16 [rec+0x0a] times, ebp += 8: `movsx esi, word [ebp]` is looked up in the machine's
  registry tree [machine+0x520] (0x782f70 / 0x783d00), then in the generic tree [[0xfaf030]+8]; the node is used
  without a null check (`mov edx, [edi+0x4c]` at 0x785dc6 - the test 48 crash); `word [ebp+2] == 0x2b` makes
  0x785b90 take a state-parameter value; the node's function (0x784570 -> node +0x1c) is called cdecl(agent, entry).
  Then the parent state (s16 [rec+6], index into [[machine+4]+0xc]) gets the same loop.
  -> activity entry = 8 bytes {u16 id, u16 type, 4 bytes value}.
* 0x7857d0 / 0x7859a0 / 0x785a30 / 0x785ae0: ebx = [rec+0x18], loop u16 [rec+0x0c] times, ebx += 2:
  `movzx esi, word [ebx]` -> 0x783f50(machine, id) (same trees; falls back to the generic root, no crash) -> node
  slot function (0x7849e0 +0x34, 0x784910, 0x784790 / 0x784600, 0x784850 / 0x7846d0).
  -> state-id list = u16 ids.
All three registrations of a machine (conditions 0x785120, activities 0x785390, states 0x785600) insert into the same
tree [machine+0x520]; the generic builder (0x787341: 0x784ee0 / 0x784f60 / 0x784fe0) into [[0xfaf030]+8]. So an id is
"found" when it is in any of the machine's three tables or any of the three generic tables (one node per id with a slot
per kind; a machine node copies the generic node first, so a generic activity reaches a machine-only condition id).
The record set here is wider than state_translist_fix.state_records: records with a non-empty +0x20 list (+0x10 != 0)
are included (DTP 20212: 1621 instead of 1488, among them the root state +0x36250 with 283 activities).

Modes (from the repository root):
  ../bin/pyt -t 300 tools/state_actlist_fix.py dump DRM ENDIAN SID [N]
  ../bin/pyt -t 300 tools/state_actlist_fix.py proof XBOX_REF.drm PC_REF.drm XREF_ID PCREF_ID
        base pair, records matched by index: which byte order turns the Xbox fields into the PC fields
  ../bin/pyt -t 300 tools/state_actlist_fix.py check XBOX_REF.drm PC_REF.drm XREF_ID PCREF_ID XBOX.drm PC.drm SID
        [--exe tru.exe] [--out OUT.drm] [--list N]
  e.g. work/rockvein/ref/x_lara.drm work/rockvein/ref/pc_lara.drm 12647 850 work/rockvein/ref/x_doppelganger_casual.drm
       work/rebuild/dlc_test48_combined/mods/doppelganger_casual.drm 20212 --exe ".../tru.exe"
  --exe: read the registries from tru.exe (Lara's machine gameTracker+0xf10: conditions 0x8b2ce8, activities 0x8b2280,
  states 0x8b0a50; second machine +0xf14: 0x8b2838 / 0x8b26e0 / 0x8b1e00; generic 0x8b57e0 / 0x8b6650 / 0x8b4200)
  plus the ids the ASIs add (TruShadowPower 0.5 Lara tables, TruDoppelganger generic tables).
Repair (--out): headers as 10 u16 and the lists +0x18 / +0x20 as u16 (proven on the base pair: every field that is
not byte-order invariant reads equal as u16, 0 raw, 0 u32 swaps), +0x1c as u16 with the Xbox indices (layout proof of
state_translist_fix; the base PC re-orders transition indices, so no per-entry equality there); activity entries:
u16 id and u16 type always (proven), the 4 value bytes by the per-type rule
proven on the base pair; a type without a unique rule keeps the converter's value bytes (reported).
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import state_translist_fix as ST
import pe_callers as PE

# registries in tru.exe: (name, VA, record size in dwords)
EXE_TABLES = [
    ('lara.cond', 0x8b2ce8, 3), ('lara.act', 0x8b2280, 2), ('lara.state', 0x8b0a50, 7),
    ('m2.cond', 0x8b2838, 3), ('m2.act', 0x8b26e0, 2), ('m2.state', 0x8b1e00, 7),
    ('gen.cond', 0x8b57e0, 3), ('gen.act', 0x8b6650, 2), ('gen.state', 0x8b4200, 7)]
# ids added by our ASIs (TruShadowPower 0.5 -> Lara's tables; TruDoppelganger -> generic tables)
ASI_IDS = {
    'asi.sp.cond': [1048, 1049, 1050, 1051, 1052, 1053, 1054, 1056, 2401], 'asi.sp.act': [1009, 1039],
    'asi.sp.state': [243, 245, 1018],
    'asi.dg.cond': [1048, 1049, 1050, 1051, 1052, 1053, 1054, 1055, 1056, 2005, 2006, 2013, 2401],
    'asi.dg.act': [286, 1009, 1039, 1040, 1041, 1042, 1043, 1044, 1045],
    'asi.dg.state': [243, 244, 245, 1017, 1018, 1019, 1020, 2102]}
TU_IDS = set(i for v in ASI_IDS.values() for i in v)


def exe_ids(path):
    exe = open(path, 'rb').read()
    base, secs = PE.sections(exe)
    def off(va):
        for _, sva, rptr, size, _ in secs:
            if sva <= va < sva + size: return rptr + va - sva
        raise SystemExit('VA 0x%x not in the exe' % va)
    out = {}
    for name, va, n in EXE_TABLES:
        o = off(va); ids = []
        while True:
            i = struct.unpack_from('<I', exe, o)[0]
            if i == 0 or len(ids) > 2000: break
            ids.append(i); o += 4 * n
        out[name] = set(ids)
    for k, v in ASI_IDS.items(): out[k] = set(v)
    return out


def records(s, e, narrow=False):
    """[(rec, sid, hdr, p14, p18, p1c, p20)] for every state record: 0x28 bytes, relocated pointers at +0x14 / +0x18 /
    +0x1c / +0x20 and nowhere else in the record; hdr = 10 u16 (+0x00..+0x12; +0x0a / +0x0c / +0x0e / +0x10 count the
    lists +0x14 (8-byte entries) / +0x18 (u16) / +0x1c (u16) / +0x20 (u16)).
    state_translist_fix.state_records additionally wants +0x10 == 0 and +0x1c == +0x20 and so misses the records
    with a non-empty +0x20 list - among them the root state +0x36250 of DTP 20212 (283 activities). narrow=True
    gives that older set."""
    f = '>' if e == 'be' else '<'
    d = bytes(s.data)
    it = dict(R.parse(bytes(s.reloc), e).internal)
    out = []
    if narrow:
        for r, sid, cnt, lo in ST.state_records(s, e):
            out.append((r, sid, struct.unpack_from(f + '10H', d, r), it[r + 0x14], it[r + 0x18], it[r + 0x1c],
                        it[r + 0x20]))
        return out
    for o in sorted(it):
        r = o - 0x14
        if r < 0 or r % 8 or r + 0x28 > len(d): continue
        if struct.unpack_from(f + 'I', d, r + 0x24)[0]: continue
        if not all((r + k) in it for k in (0x14, 0x18, 0x1c, 0x20)): continue
        if any((r + k) in it for k in (0, 4, 8, 0xc, 0x10, 0x24)): continue
        hdr = struct.unpack_from(f + '10H', d, r)
        p = [it[r + k] for k in (0x14, 0x18, 0x1c, 0x20)]
        if p[0] + 8 * hdr[5] > len(d) or p[1] + 2 * hdr[6] > len(d) or p[2] + 2 * hdr[7] > len(d) or \
                p[3] + 2 * hdr[8] > len(d): continue
        out.append((r, hdr[0], hdr) + tuple(p))
    return out


def dump(argv):
    e = argv[1]; sid = int(argv[2]); n = int(argv[3]) if len(argv) > 3 else 8
    _, s = ST.load(argv[0], e, sid)
    d = bytes(s.data)
    recs = records(s, e)
    print('%d state records' % len(recs))
    for r, sid_, hdr, p14, p18, *_ in recs[:n]:
        print('rec +0x%05x id %d hdr %s p14 +0x%05x p18 +0x%05x' % (r, sid_, ' '.join('%04x' % h for h in hdr), p14, p18))
        print('   +0x14 activities: %s' % d[p14:p14 + 8 * min(hdr[5], 6)].hex(' ', 2))
        print('   +0x18 state ids : %s' % d[p18:p18 + 2 * min(hdr[6], 12)].hex(' ', 2))


def value_forms(x4):
    """{name: PC bytes} for the 4 value bytes of an activity entry"""
    return {'u32': struct.pack('<I', *struct.unpack('>I', x4)), 'u16x2': struct.pack('<2H', *struct.unpack('>2H', x4)),
            'raw': bytes(x4)}


HDR_NAMES = ['+0x00 id', '+0x02', '+0x04', '+0x06 parent', '+0x08', '+0x0a n14', '+0x0c n18', '+0x0e n1c',
             '+0x10 n20', '+0x12']
U16_LISTS = ((1, 6, '+0x18 state ids'), (2, 7, '+0x1c transitions'), (3, 8, '+0x20 list'))   # (pointer, count field)


def base_rules(xb, pb):
    """base pair proof: header fields, activity entries (+ per-type rule of the value bytes), u16 lists"""
    xr, pr = records(xb, 'be'), records(pb, 'le')
    assert len(xr) == len(pr) and [s for _, s, *_ in xr] == [s for _, s, *_ in pr], 'base records differ'
    xd, pd = bytes(xb.data), bytes(pb.data)
    per_type = collections.defaultdict(collections.Counter)
    f = collections.Counter(); bad_entries = []
    hf = [collections.Counter() for _ in range(10)]
    lists = {n: collections.Counter() for _, _, n in U16_LISTS}
    for x, p in zip(xr, pr):
        r, sid, h = x[:3]; ph = p[2]
        for i in range(10):
            xb2 = xd[r + 2 * i:r + 2 * i + 2]; pb2 = pd[p[0] + 2 * i:p[0] + 2 * i + 2]
            hf[i]['n'] += 1
            if xb2 == xb2[::-1]: hf[i]['invariant'] += 1
            elif pb2 == xb2[::-1]: hf[i]['u16 swap'] += 1
            elif pb2 == xb2:
                hf[i]['raw (u8 pair)'] += 1
                if os.environ.get('SAF_DEBUG'): print('   raw header field %s: state %d Xbox +0x%05x %s PC +0x%05x %s' % (
                    HDR_NAMES[i], sid, r, xd[r:r + 20].hex(' ', 2), p[0], pd[p[0]:p[0] + 20].hex(' ', 2)))
            else: hf[i]['other value'] += 1
        a14, b14 = x[3], p[3]
        if h[5] == ph[5]:
            for k in range(h[5]):
                x8, p8 = xd[a14 + 8 * k:a14 + 8 * k + 8], pd[b14 + 8 * k:b14 + 8 * k + 8]
                f['act entries'] += 1
                f['id u16 swap'] += struct.unpack('>H', x8[:2]) == struct.unpack('<H', p8[:2])
                f['type u16 swap'] += struct.unpack('>H', x8[2:4]) == struct.unpack('<H', p8[2:4])
                f['id/type u32 swap'] += x8[:4][::-1] == p8[:4]
                t = struct.unpack('>H', x8[2:4])[0]
                hits = [n for n, v in value_forms(x8[4:]).items() if v == p8[4:]]
                if len(hits) == 3: per_type[t]['invariant'] += 1
                elif hits: per_type[t]['+'.join(hits)] += 1
                else:
                    per_type[t]['none'] += 1; bad_entries.append((sid, k, x8.hex(), p8.hex()))
        for pi, ci, name in U16_LISTS:
            if h[ci] != ph[ci]: continue
            for k in range(h[ci]):
                xb2 = xd[x[3 + pi] + 2 * k:x[3 + pi] + 2 * k + 2]; pb2 = pd[p[3 + pi] + 2 * k:p[3 + pi] + 2 * k + 2]
                c = lists[name]; c['entries'] += 1
                if xb2 == xb2[::-1]: c['invariant'] += 1
                elif pb2 == xb2[::-1]: c['u16 swap'] += 1
                elif pb2 == xb2: c['raw'] += 1
                else: c['other value'] += 1
    rules = {}
    for t, c in per_type.items():
        forms = [k for k in c if k not in ('invariant', 'none')]
        single = set.intersection(*[set(k.split('+')) for k in forms]) if forms else set()
        if not forms and c['invariant'] and not c['none']: rules[t] = ('invariant', c)   # reads the same in any order
        elif len(single) == 1: rules[t] = (sorted(single)[0], c)
        else: rules[t] = (None, c)          # ambiguous (only values that read the same as u32 and u16x2) or re-authored
    return xr, f, rules, bad_entries, (hf, lists)


def proof(argv):
    _, xb = ST.load(argv[0], 'be', int(argv[2]))
    _, pb = ST.load(argv[1], 'le', int(argv[3]))
    xr, f, rules, bad, (hf, lists) = base_rules(xb, pb)
    print('base: %d state records on both sides (same order and ids; %d with the older narrow detector)' % (
        len(xr), len(records(xb, 'be', narrow=True))))
    print('header u16 fields (Xbox bytes -> PC bytes):')
    for i, c in enumerate(hf): print('  %-13s %s' % (HDR_NAMES[i], dict(c)))
    print('activity list +0x14: %d entries; id u16-swapped equal %d, type u16-swapped equal %d, id/type as one u32 '
          'swap equal %d' % (f['act entries'], f['id u16 swap'], f['type u16 swap'], f['id/type u32 swap']))
    print('value bytes +4 per type (rule = the one byte order every non-invariant entry of the type agrees on):')
    for t in sorted(rules):
        print('  type %3d (0x%02x): rule %-9s %s' % (t, t, rules[t][0], dict(rules[t][1])))
    print('  entries no byte order explains (re-authored on PC): %d; distinct (id, type, Xbox value -> PC value): %s' % (
        len(bad), sorted(set((int(x[:4], 16), int(x[4:8], 16), '0x%x -> 0x%x' % (int(x[8:], 16), struct.unpack('<I', bytes.fromhex(p[8:]))[0])) for s, k, x, p in bad))))
    for name, c in lists.items(): print('u16 list %s: %s' % (name, dict(c)))


def check(argv):
    out_path = None; nlist = 30; exe = None
    if '--out' in argv: k = argv.index('--out'); out_path = argv[k + 1]; del argv[k:k + 2]
    if '--list' in argv: k = argv.index('--list'); nlist = int(argv[k + 1]); del argv[k:k + 2]
    if '--exe' in argv: k = argv.index('--exe'); exe = argv[k + 1]; del argv[k:k + 2]
    _, xb = ST.load(argv[0], 'be', int(argv[2]))
    _, pb = ST.load(argv[1], 'le', int(argv[3]))
    _, f, rules, _, _ = base_rules(xb, pb)
    XD, xs = ST.load(argv[4], 'be', int(argv[6]))
    PD, ps = ST.load(argv[5], 'le', int(argv[6]))
    if len(xs.data) != len(ps.data): raise SystemExit('sizes differ - not the same layout')
    xr = records(xs, 'be')
    narrow = set(r for r, *_ in records(xs, 'be', narrow=True))
    pit = dict(R.parse(bytes(ps.reloc), 'le').internal)
    xd = bytes(xs.data); pdat = bytearray(ps.data)
    reg = exe_ids(exe) if exe else None
    def kinds(i): return ','.join(k for k in sorted(reg) if i in reg[k]) or 'NOT REGISTERED'
    print('target DTP %s: %d state records (%d new against the narrow detector of state_translist_fix)' % (
        argv[6], len(xr), len(xr) - len(narrow & set(r for r, *_ in xr))))
    # pointers equal on PC?
    ptr_diff = [r for r, *_ in xr if [pit.get(r + k) for k in (0x14, 0x18, 0x1c, 0x20)] !=
                [it_ for it_ in _ptrs(xs, r)]]
    print('  records whose PC pointers differ: %d' % len(ptr_diff))
    # 1. headers: 10 u16
    hwrong = []; hcls = collections.Counter()
    for r, sid, hdr, *_ in xr:
        want = struct.pack('<10H', *hdr); got = bytes(pdat[r:r + 20])
        if got != want:
            fields = [HDR_NAMES[i] for i in range(10) if got[2 * i:2 * i + 2] != want[2 * i:2 * i + 2]]
            hcls[' '.join(fields)] += 1
            hwrong.append((sid, r, got, want, fields))
    print('1. headers: %d of %d differ from the u16 conversion; fields: %s' % (len(hwrong), len(xr), dict(hcls)))
    for sid, r, got, want, fields in hwrong[:nlist]:
        print('   state %5d +0x%05x PC %s -> %s  (PC reads parent %d count14 %d; right %d / %d)%s' % (
            sid, r, got.hex(' ', 2), want.hex(' ', 2), struct.unpack_from('<h', got, 6)[0],
            struct.unpack_from('<H', got, 10)[0], struct.unpack_from('<h', want, 6)[0],
            struct.unpack_from('<H', want, 10)[0], '' if r in narrow else '  [new record]'))
    # 2. activity entries
    n_act = 0; wrong = []; norule = collections.Counter(); cls = collections.Counter(); norule_e = []
    for r, sid, hdr, p14, *_ in xr:
        for k in range(hdr[5]):
            o = p14 + 8 * k
            x8 = xd[o:o + 8]; got = bytes(pdat[o:o + 8])
            t = struct.unpack('>H', x8[2:4])[0]
            rule = rules.get(t, (None, None))[0]
            head = struct.pack('<2H', *struct.unpack('>2H', x8[:4]))
            if rule in ('u32', 'u16x2', 'raw'): val = value_forms(x8[4:])[rule]
            elif rule == 'invariant': val = value_forms(x8[4:])['u32']
            elif t in rules and set(k2 for k2 in rules[t][1] if k2 != 'invariant') == {'u32+u16x2'} and \
                    value_forms(x8[4:])['u32'] == value_forms(x8[4:])['u16x2']:
                val = value_forms(x8[4:])['u32']   # type only seen as u32 = u16x2 on the base, and so is this value
            else:
                val = got[4:]; norule[t] += 1; norule_e.append((sid, r, k, o, x8, got))
            want = head + val
            n_act += 1
            if got != want:
                c = ('id/type ok' if got[:4] == head else ('id/type as u32 swap' if got[:4] == x8[:4][::-1] else
                     ('id/type raw' if got[:4] == x8[:4] else 'id/type other')),
                     'value ok' if got[4:] == val else 'value wrong (%s)' % ' '.join(
                         n for n, v in value_forms(x8[4:]).items() if v == got[4:]))
                cls[c] += 1
                wrong.append((sid, r, k, o, x8, got, want))
    print('2. activity list +0x14: %d entries, %d differ from the proven conversion of the Xbox bytes' % (
        n_act, len(wrong)))
    print('   classes: %s' % dict(cls))
    if norule: print('   types without a base rule (value bytes kept as converted): %s' % dict(norule))
    for sid, r, k, o, x8, got in norule_e[:nlist]:
        print('     kept: state %5d rec +0x%05x entry %3d at +0x%05x: Xbox %s  PC %s' % (sid, r, k, o, x8.hex(' ', 2), got.hex(' ', 2)))
    for sid, r, k, o, x8, got, want in wrong[:nlist]:
        print('   state %5d rec +0x%05x entry %3d at +0x%05x: Xbox %s  PC %s  -> %s  (PC reads id %d, right id %d)%s' % (
            sid, r, k, o, x8.hex(' ', 2), got.hex(' ', 2), want.hex(' ', 2), struct.unpack('<H', got[:2])[0],
            struct.unpack('<H', want[:2])[0], '' if r in narrow else '  [new record]'))
    # 3. u16 lists
    uwrong = []
    for pi, ci, name in U16_LISTS:
        n = 0; w = []
        for x in xr:
            r, sid, hdr = x[:3]; p = x[3 + pi]
            for k in range(hdr[ci]):
                o = p + 2 * k
                n += 1
                if bytes(pdat[o:o + 2]) != xd[o:o + 2][::-1]:
                    w.append((sid, r, o, struct.unpack_from('>H', xd, o)[0], struct.unpack_from('<H', pdat, o)[0]))
        uwrong += [(name,) + e for e in w]
        print('3. u16 list %s: %d entries, %d differ from the u16 conversion%s' % (name, n, len(w), ''.join(
            '\n   state %d rec +0x%05x at +0x%05x: right %d, PC reads %d%s' % (s, r, o, a, b,
            '' if r in narrow else ' [new record]') for s, r, o, a, b in w[:nlist])))
    return xr, xd, pdat, reg, kinds, hwrong, wrong, uwrong, XD, PD, ps, out_path, argv


def _ptrs(s, r):
    it = _ptrs.cache.get(id(s))
    if it is None: it = _ptrs.cache[id(s)] = dict(R.parse(bytes(s.reloc), 'be').internal)
    return [it.get(r + k) for k in (0x14, 0x18, 0x1c, 0x20)]
_ptrs.cache = {}


def check_main(argv):
    xr, xd, pdat, reg, kinds, hwrong, wrong, uwrong, XD, PD, ps, out_path, argv = check(argv)
    if reg is not None:
        for name, items in (('activity ids (+0x14)', [(sid, r, struct.unpack('>H', xd[p14 + 8 * k:p14 + 8 * k + 2])[0],
                                                       struct.unpack('<H', bytes(pdat[p14 + 8 * k:p14 + 8 * k + 2]))[0])
                                                      for r, sid, hdr, p14, p18, *_ in xr for k in range(hdr[5])]),
                            ('state ids (+0x18)', [(sid, r, struct.unpack_from('>H', xd, p18 + 2 * k)[0],
                                                   struct.unpack_from('<H', pdat, p18 + 2 * k)[0])
                                                  for r, sid, hdr, p14, p18, *_ in xr for k in range(hdr[6])])):
            allreg = set().union(*reg.values())
            now = collections.Counter(p for s, r, x, p in items if p not in allreg)
            right = collections.Counter(x for s, r, x, p in items if x not in allreg)
            kc = collections.Counter('/'.join(sorted(set(k.split('.')[1] for k in reg if k[:3] != 'asi' and x in reg[k]))) or 'TU only (ASI)' if x in allreg else 'none'
                                     for s, r, x, p in items)
            print('%s: %d entries, %d distinct right ids; exe table kinds of the right ids: %s' % (
                name, len(items), len(set(x for s, r, x, p in items)), dict(kc)))
            print('  not registered as the PC reads them now: %d entries, ids %s' % (
                sum(now.values()), sorted(now.items())[:40]))
            print('  not registered with the right ids: %d entries, ids %s' % (sum(right.values()), sorted(right.items())))
            for i in sorted(right):
                where = sorted(set((s, '+0x%05x' % r) for s, r, x, p in items if x == i))
                print('    id %d: %d entries in states %s' % (i, right[i], where[:10]))
            # per kind: the slot the reader calls (activity list -> node +0x1c activity, state-id list -> state slots)
            want_kind = 'act' if '+0x14' in name else 'state'
            kind_ids = set().union(*[v for k, v in reg.items() if k.endswith('.' + want_kind) and k[:2] != 'm2'])
            nok = collections.Counter(x for s, r, x, p in items if x not in kind_ids)
            print('  right ids with no %s record in Lara / generic tables (exe + ASIs): %d entries, %s' % (
                want_kind, sum(nok.values()), ['%d (%s) x%d' % (i, kinds(i), n) for i, n in sorted(nok.items())]))
            tu = sorted(set(x for s, r, x, p in items if x in TU_IDS))
            for i in tu:
                where = sorted(set(s for s, r, x, p in items if x == i))
                print('    TU id %d (%s): %d entries, states %s' % (i, kinds(i), sum(1 for s, r, x, p in items if x == i),
                                                                    where[:12]))
    if out_path:
        for sid, r, k, o, x8, got, want in wrong: pdat[o:o + 8] = want
        for sid, r, got, want, fields in hwrong: pdat[r:r + 20] = want
        for name, sid, r, o, a, b in uwrong: pdat[o:o + 2] = struct.pack('<H', a)
        ps.data = bytes(pdat)
        raw = PD.write('le')
        if open(argv[5], 'rb').read(4) == b'CDRM': raw = DW.cdrm_encode(raw, 'le')
        open(out_path, 'wb').write(raw)
        chk = DW.read(open(out_path, 'rb').read(), 'le')
        assert len(chk.sections) == len(PD.sections)
        print('written %s (%d bytes, read back ok; set: %d headers, %d activity entries, %d u16 list entries)' % (
            out_path, len(raw), len(hwrong), len(wrong), len(uwrong)))


def scan(argv):
    """scan XBOX.drm PC.drm SID [--exe tru.exe] [--type T]: headers of the state records that differ from a u16
    conversion (raw bytes), and every 4-aligned word of the whole DTP whose Xbox bytes are {u16 X, u16 T} and whose PC
    bytes are the u32 swap (PC reads id T) - activity entries outside the detected records included"""
    exe = None; typ = 0x29
    if '--exe' in argv: k = argv.index('--exe'); exe = argv[k + 1]; del argv[k:k + 2]
    if '--type' in argv: k = argv.index('--type'); typ = int(argv[k + 1], 0); del argv[k:k + 2]
    _, xs = ST.load(argv[0], 'be', int(argv[2]))
    _, ps = ST.load(argv[1], 'le', int(argv[2]))
    xd, pd = bytes(xs.data), bytes(ps.data)
    if exe:
        reg = exe_ids(exe)
        print('registry sizes: %s' % {k: len(v) for k, v in reg.items()})
    xr = records(xs, 'be')
    nd = 0
    for r, sid, hdr, p14, p18, *_ in xr:
        want = struct.pack('<10H', *hdr)
        if pd[r:r + 20] != want:
            nd += 1
            if nd <= 20:
                print('  hdr state %5d +0x%05x Xbox %s PC %s (u16 conv %s)' % (sid, r, xd[r:r + 20].hex(' ', 2),
                                                                         pd[r:r + 20].hex(' ', 2), want.hex(' ', 2)))
    print('%d state records, %d headers differ from the u16 conversion' % (len(xr), nd))
    hits = []
    for o in range(0, len(xd) - 3, 4):
        a, t = struct.unpack_from('>2H', xd, o)
        if t == typ and a != typ and pd[o:o + 4] == xd[o:o + 4][::-1]: hits.append((o, a))
    print('words {u16 X, u16 0x%x} u32-swapped on PC (PC reads 0x%x first): %d %s' % (
        typ, typ, len(hits), ['+0x%05x X=%d' % h for h in hits[:30]]))
    # which state record list holds them; else the nearest pointer target at or below and its pointer sources
    it = R.parse(bytes(xs.reloc), 'be').internal
    by_t = collections.defaultdict(list)
    for src, t in it: by_t[t].append(src)
    targets = sorted(by_t)
    import bisect
    for o, a in hits:
        own = [(sid, '+0x%05x' % r, (o - p14) // 8) for r, sid, hdr, p14, p18, *_ in xr
               if p14 <= o < p14 + 8 * max(hdr[5], 1)]
        t = targets[bisect.bisect_right(targets, o) - 1]
        srcs = by_t[t]
        recs = [(sid, '+0x%05x' % r, '+0x%02x' % (s - r)) for s in srcs for r, sid, hdr, p14, p18, *_ in xr
                if r <= s < r + 0x28]
        print('    +0x%05x: activity list of %s; nearest target +0x%05x (entry %s) from %s %s' % (
            o, own or '-', t, (o - t) / 8, ['+0x%05x' % s for s in srcs[:4]], recs[:3]))


if __name__ == '__main__':
    a = sys.argv[1:]
    {'dump': dump, 'proof': proof, 'check': check_main, 'scan': scan}[a[0]](a[1:])
