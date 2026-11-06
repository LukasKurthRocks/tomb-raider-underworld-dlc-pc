"""Damage types of the attack records a player state chart hands to the CombatManager (read-only; K14 damage-type
switch 2026-11-06, docs Befund-K14-Schadensarten-0611.md: which damage types Lara's doppelganger hits send).

Chain in tru.exe (Steam build), proven by code:
* activity 1005 (0x3ed) is registered in Lara's activity table 0x8b2280 (entry 0x8b2590 {0x3ed, 0x767e90}) and in the
  second machine's 0x8b26e0 (entry 0x8b2738); handler tru+0x367e90: `[[0xfadb58]+0x504]+0xc4 = [entry+4]` - the
  4 value bytes of the activity entry are a pointer to an attack record (relocated in the DRM).
* CombatManager readers of +0xc4 (tru+0x2e6840 hit on the main target, tru+0x31917d, tru+0x31d871, MeleeSplashDamage
  tru+0x2e68b0): record +0x04 float amount, +0x0c damage type (-> hit message +0x50 = argument 8 of the message
  builder tru+0x23c9b0 -> type argument of the enemy damage function tru+0x237590 via tru+0x23aaa0), byte +0x01
  (argument 21), +0x20 count / +0x24 pointer of the splash records (0x1c bytes).

For every state record (tools/state_actlist_fix.records) with an activity of id ACT (default 1005) whose value bytes
carry an internal relocation, the attack record is printed: state ids of the chart record, record offset, +0x00..+0x0f
as words, the type +0x0c, the amount +0x04, splash count +0x20 / pointer +0x24. At the end the damage types with
their counts. Only offsets, ids and numbers are printed (no game bytes beyond the record words).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/chart_attack_damage_types.py DRM ENDIAN SID [--act 1005] [--words 12]
  e.g. work/rockvein/ref/x_doppelganger_casual.drm be 20212
       work/rockvein/ref/pc_lara.drm le 850
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import state_actlist_fix as SA
import state_translist_fix as ST


def main(argv):
    act, nwords = 1005, 12
    if '--act' in argv:
        k = argv.index('--act'); act = int(argv[k + 1]); del argv[k:k + 2]
    if '--words' in argv:
        k = argv.index('--words'); nwords = int(argv[k + 1]); del argv[k:k + 2]
    if len(argv) < 3:
        print(__doc__); return 2
    e = argv[1]; sid = int(argv[2])
    f = '>' if e == 'be' else '<'
    _, s = ST.load(argv[0], e, sid)
    d = bytes(s.data)
    it = dict(R.parse(bytes(s.reloc), e).internal)
    recs = SA.records(s, e)
    types = collections.Counter()
    seen = {}
    n_entries = n_noptr = 0
    for r, sid_, hdr, p14, p18, *_ in recs:
        ids = [struct.unpack_from(f + 'H', d, p18 + 2 * k)[0] for k in range(hdr[6])]
        for k in range(hdr[5]):
            a = p14 + 8 * k
            aid, typ = struct.unpack_from(f + 'HH', d, a)
            if aid != act: continue
            n_entries += 1
            tgt = it.get(a + 4)
            if tgt is None:
                n_noptr += 1
                print('rec +0x%05x id %d states %s: act %d type %d value %s (no relocation)' % (
                    r, sid_, ids, aid, typ, d[a + 4:a + 8].hex()))
                continue
            w = [struct.unpack_from(f + 'I', d, tgt + 4 * j)[0] for j in range(nwords) if tgt + 4 * j + 4 <= len(d)]
            amount = struct.unpack_from(f + 'f', d, tgt + 4)[0]
            dtype = w[3] if len(w) > 3 else None
            cnt = w[8] if len(w) > 8 else None
            p24 = it.get(tgt + 0x24)
            first = tgt not in seen
            seen.setdefault(tgt, []).append(ids)
            if first: types[dtype] += 1
            print('rec +0x%05x id %d states %s: act %d type %d -> attack +0x%05x%s byte1 %d amount %g damage type %s'
                  ' splash count %s ptr %s | words %s' % (
                      r, sid_, ids, aid, typ, tgt, '' if first else ' (again)', d[tgt + 1], amount, dtype, cnt,
                      ('+0x%05x' % p24) if p24 is not None else '-', ' '.join('%08x' % x for x in w)))
    print('== %d activity entries with id %d, %d without relocation, %d distinct attack records' % (
        n_entries, act, n_noptr, len(seen)))
    print('== damage types (distinct records): %s' % ', '.join('%s x%d' % (t, c) for t, c in sorted(
        types.items(), key=lambda x: (x[0] is None, x[0] or 0))))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
