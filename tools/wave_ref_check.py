"""Wave references of converted (PC) DRMs: does every SoundPlex Wave leaf point at a loaded wave section? (Q4 2026-11-11)

The leaf handler 0x591220 looks its wave id (data +0, no relocation) up among the loaded wave sections (type 6) - an id
that no loaded DRM holds is a silent leaf (no crash, no log). Leaves are found as in tools/soundplex_wave_id_fix.py
(SoundPlex DTPs: root node at DTP +0, nodes reachable over the child pointers, type 2; on the PC side without the value
filter, so byte-swapped ids are seen too).

Per DRM: Wave leaves, null ids (0 / -1), refs that resolve to a wave section of the same DRM, refs that resolve only
through --also (other DRMs, e.g. a resident bank or the level), unresolved refs (listed per DTP). With --xbox the Xbox
original (convert_dlc.raw_dlc, --pack first) is paired and refs that resolve but differ from the proven rule
(soundplex_wave_id_fix: ids(6, Xbox id)) are counted as 'wrong target' (they play another sound).

Usage (from the repository root, read-only):
  ../bin/pyt -t 900 tools/wave_ref_check.py DRM_OR_DIR[,..] [--also DRM_OR_DIR[,..]] [--xbox] [--pack PACK] [--report R.json]
Exit 1 when any ref is unresolved (or, with --xbox, points at the wrong wave), 0 otherwise.
"""
import sys, os, struct, collections, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import soundplex_wave_id_fix as WF


def waves_of(D):
    return {s.id for s in D.sections if s.type == 6}


def check_drm(path, also_ids, xbox=False, pack=None):
    D = DW.read(open(path, 'rb').read(), 'le')
    own = waves_of(D)
    r = collections.Counter(); unresolved = collections.defaultdict(list); via_also = collections.defaultdict(list)
    wrong = []
    for s in D.sections:
        if s.type != 7: continue
        for tg in WF.wave_leaves(bytes(s.data), bytes(s.reloc), 'le', max_id=None):
            v = struct.unpack_from('<I', s.data, tg)[0]
            r['leaves'] += 1
            if v in WF.NULLS: r['null'] += 1
            elif v in own: r['resolved_own'] += 1
            elif v in also_ids:
                r['resolved_also'] += 1; via_also[s.id].append((tg, v, also_ids[v]))
            else:
                r['unresolved'] += 1; unresolved[s.id].append((tg, v))
    if xbox:
        XD, pk = WF.xbox_of(path, pack)
        if XD is None: r['no_xbox_source'] = 1
        else:
            info = WF.plan(XD, D)
            for k, sid, tg, f, xw, pw, ww, cls in info['rows']:
                if f != 0 or cls == 'ok': continue
                pv = struct.unpack('<I', pw)[0]
                if pv in own or pv in also_ids:
                    wrong.append((sid, tg, struct.unpack('>I', xw)[0], pv, struct.unpack('<I', ww)[0]))
            r['wrong_target'] = len(wrong)
            r['rule_rows_not_ok'] = sum(1 for row in info['rows'] if row[7] != 'ok')
    return dict(file=path, counts=dict(r), unresolved={k: v for k, v in unresolved.items()},
                via_also={k: v for k, v in via_also.items()}, wrong=wrong, waves=len(own))


def main(a):
    a = list(a)
    also = WF.opt(a, '--also'); pack = WF.opt(a, '--pack'); report = WF.opt(a, '--report')
    xbox = '--xbox' in a
    a = [x for x in a if x != '--xbox']
    if len(a) != 1: sys.exit(__doc__)
    import soundplex_sequence_fix as SQ
    also_ids = {}
    if also:
        for p in SQ.file_list(also):
            try: D = DW.read(open(p, 'rb').read(), 'le')
            except Exception as e: print('also: skip %s (%s)' % (p, e)); continue
            for w in waves_of(D): also_ids.setdefault(w, os.path.basename(p))
    out = []; bad = 0
    for p in SQ.file_list(a[0]):
        res = check_drm(p, also_ids, xbox, pack)
        c = res['counts']; out.append(res)
        n_un = c.get('unresolved', 0); n_wr = c.get('wrong_target', 0)
        bad += n_un + n_wr
        print('%s: %d wave sections; leaves %d, null %d, resolved in the DRM %d, via --also %d, UNRESOLVED %d%s' % (
            p, res['waves'], c.get('leaves', 0), c.get('null', 0), c.get('resolved_own', 0), c.get('resolved_also', 0), n_un,
            (', wrong target %d (rule rows not ok %d)' % (n_wr, c.get('rule_rows_not_ok', 0))) if xbox else ''))
        for sid, lst in sorted(res['unresolved'].items()):
            print('   unresolved DTP %d: %d leaves, ids %s' % (sid, len(lst), sorted({v for _, v in lst})))
        for sid, lst in sorted(res['via_also'].items()):
            print('   via --also DTP %d: %s' % (sid, sorted({(v, f) for _, v, f in lst})))
        for sid, tg, xv, pv, want in res['wrong'][:80]:
            print('   wrong target DTP %d leaf +%#x: Xbox %d -> PC %d (rule %d)' % (sid, tg, xv, pv, want))
    print('wave_ref_check: %s' % ('ok' if not bad else 'FAIL (%d unresolved / wrong refs)' % bad))
    if report:
        json.dump(out, open(report, 'w', encoding='utf-8'), indent=1, default=str)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
