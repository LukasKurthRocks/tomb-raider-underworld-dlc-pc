"""Melee attack records of an enemy DRM, Xbox original against the converted PC DRM: are the records that are reached
ONLY through the follow-up link of another attack (record +0x1c0 / +0x1c4 / +0x1c8) converted with the same byte
order per field as the records the tune points to? (read-only; melee freeze 2026-11-07, docs
Befund-Thrall-MeleeAttack-Freeze-0711.md).

Engine (PC tru.exe; offsets of the enemy data / tune: docs Befund-Thrall-Felder-0611.md section 1):
  enemy data   = [DTP + 0xc8] (magic 0xdaf00018), byte +0x18 tune count, +0x1c tune array, +0x20 default tune;
                 tune +0x1c = parent tune; tune +0x80 .. +0xac = meleeAttack1..12 (pointer to a record)
  melee record = 0x21c bytes + s16 array (count at +0x218, entries from +0x21c)
  follow-up    = MeleeAttack update tru+0x265f10 -> after the attack (state data +0xa4 == 2, record +0x146 <= 0)
                 tru+0x25bc10: record +0x1c0 / +0x1c4 -> state Attack, +0x1c8 -> state MeleeAttack again with the
                 linked record (tru+0x23d5c0)
  the follow-up record's +0x78 {u16 type, u16 anim} is played by tru+0x2276c0 -> tru+0x226f10 (type 1 = anim index
  of the object's list); with record +0x136 = -1 the attack ends only when that animation reports its end
  (message 0x15, anim callback tru+0x225c60), so a wrong +0x78 freezes the enemy in MeleeAttack.

Rule: per word offset of a record, the byte order the converter used on the TUNE-referenced records (only words whose
Xbox value tells the orders apart) is the reference ("profile"). A word of any record whose PC bytes are another byte
order than the profile's is reported (WRONG, with the wanted PC bytes); a PC word that is no byte order of the Xbox
word is UNEXPECTED. Relocated words are skipped. Offsets without an unanimous profile are listed as MIXED (not judged).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/melee_link_record_check.py XBOX_NAME_OR_FILE PC_DRM [XBOX2 PC2 ...] [--all] [--report R.json]
     e.g. viking_thrall_dlc2_ path/to/mods/viking_thrall_dlc2_.drm
     PC_DRM may be pc:NAME = the base game's own PC conversion (patch.000 / bigfile.000), the proof pairs:
     e.g. yeti_thrall pc:yeti_thrall (Xbox layer / TU against Eidos' PC file)
  --all    print every record word, not only the findings
Exit 0 = no WRONG / UNEXPECTED word, 1 = findings, 2 = structure not found.
"""
import sys, os, struct, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import tuning_word_audit as TA

MAGIC = 0xdaf00018
MELEE = range(0x80, 0xb0, 4)
LINKS = (0x1c0, 0x1c4, 0x1c8)
CORE = 0x21c
ORDERS = {'raw': (0, 1, 2, 3), 'u32': (3, 2, 1, 0), 'u16p': (1, 0, 3, 2), 'u8u8u16': (0, 1, 3, 2),
          'u16u8u8': (1, 0, 2, 3)}


def perm(w, p): return bytes(w[i] for i in p)


def orders_of(xw, pw):
    return [n for n, p in ORDERS.items() if perm(xw, p) == pw]


def distinguishing(xw):
    """the Xbox word gives different PC bytes for raw / u32 / u16p"""
    return len({perm(xw, ORDERS[n]) for n in ('raw', 'u32', 'u16p')}) == 3


def enemy_dtps(secs):
    out = []
    for s in secs:
        if s['type'] != 7: continue
        ip = dict(R.parse(bytes(s['reloc']), 'be').internal)
        r = ip.get(0xc8)
        d = bytes(s['data'])
        if r is not None and r + 0x24 <= len(d) and struct.unpack_from('>I', d, r)[0] == MAGIC:
            out.append((s, ip, r))
    return out


def walk(d, ip, root):
    """-> {record offset: set of origins ('tune+0x8c' / 'link +0x1c8 of +0x44b0')}, tune offsets"""
    tunes = []
    arr = ip.get(root + 0x1c)
    if arr is not None:
        for k in range(d[root + 0x18]):
            t = ip.get(arr + 4 * k)
            if t is not None: tunes.append(t)
    if ip.get(root + 0x20) is not None: tunes.append(ip[root + 0x20])
    seen_t, todo = [], list(tunes)
    while todo:                                   # tunes and their parents
        t = todo.pop()
        if t in seen_t: continue
        seen_t.append(t)
        p = ip.get(t + 0x1c)
        if p is not None: todo.append(p)
    recs = {}
    for t in seen_t:
        for f in MELEE:
            r = ip.get(t + f)
            if r is not None: recs.setdefault(r, set()).add('tune +0x%x (tune at +0x%x)' % (f, t))
    todo = list(recs)
    while todo:                                   # follow-up links, recursively
        r = todo.pop()
        for f in LINKS:
            q = ip.get(r + f)
            if q is None: continue
            new = q not in recs
            recs.setdefault(q, set()).add('link +0x%x of record +0x%x' % (f, r))
            if new: todo.append(q)
    return recs, sorted(seen_t)


def rec_len(d, r):
    n = struct.unpack_from('>I', d, r + 0x218)[0] if r + 0x21c <= len(d) else 0
    n = n if n < 64 else 0
    return CORE + ((2 * n + 3) // 4) * 4


def load_pc(spec):
    """a PC DRM file, or pc:NAME = the base game's PC archives (patch first, then bigfile)"""
    if spec.startswith('pc:'):
        import dtp_twin_field as TW
        secs, _src = TW.load_named(spec[3:], ('pcpatch', 'pcbig'), 'le')
        if not secs: sys.exit('not in the PC archives: ' + spec[3:])
        return secs
    return TA.load_p(spec)


def check(xname, pfile, show_all=False):
    xs, src = TA.load_x(xname)
    ps = load_pc(pfile)
    res = dict(xbox=xname, xbox_source=src, pc=pfile, dtps=[], findings=0)
    found = enemy_dtps(xs)
    if not found:
        print('%s: no enemy data (DTP +0xc8 -> 0x%08x)' % (xname, MAGIC)); res['skip'] = 'no enemy data'; return res
    for xsec, xip, root in found:
        psec = next((s for s in ps if s['type'] == 7 and s['id'] == xsec['id']), None)
        if psec is None:                          # base game: the PC renumbered the DTPs -> same size + same root
            cand = [s for s in ps if s['type'] == 7 and len(s['data']) == len(xsec['data'])
                    and dict(R.parse(bytes(s['reloc']), 'le').internal).get(0xc8) == root]
            psec = cand[0] if len(cand) == 1 else None
            if psec is not None:
                print('%s DTP %d: PC twin by size / enemy data offset = DTP %d' % (xname, xsec['id'], psec['id']))
        if psec is None:
            print('%s DTP %d: not in the PC file' % (xname, xsec['id'])); continue
        xd, pd = bytes(xsec['data']), bytes(psec['data'])
        pip = dict(R.parse(bytes(psec['reloc']), 'le').internal)
        reloc = set(xip) | set(pip)
        recs, tunes = walk(xd, xip, root)
        tune_recs = [r for r, o in recs.items() if any(x.startswith('tune') for x in o)]
        link_only = sorted(r for r in recs if r not in tune_recs)
        # profile: per offset, the byte orders seen on tune-referenced records (distinguishing words only)
        prof = {}
        for r in tune_recs:
            for off in range(0, rec_len(xd, r), 4):
                o = r + off
                if o in reloc or o + 4 > len(xd): continue
                xw, pw = xd[o:o + 4], pd[o:o + 4]
                if not distinguishing(xw): continue
                od = orders_of(xw, pw)
                prof.setdefault(off, set()).add(od[0] if od else 'other')
        mixed = sorted(off for off, s in prof.items() if len(s) > 1)
        print('%s DTP %d: enemy data +0x%x, %d tune(s), %d melee record(s) (%d tune-referenced, %d only via a link: %s); '
              'profile %d offsets, mixed %s' % (xname, xsec['id'], root, len(tunes), len(recs), len(tune_recs),
              len(link_only), ', '.join('+0x%x' % r for r in link_only) or '-', len(prof),
              ', '.join('+0x%x' % m for m in mixed) or '-'))
        drec = dict(dtp=xsec['id'], root=root, records=[])
        for r in sorted(recs):
            rows = []
            for off in range(0, rec_len(xd, r), 4):
                o = r + off
                if o in reloc or o + 4 > len(xd): continue
                xw, pw = xd[o:o + 4], pd[o:o + 4]
                od = orders_of(xw, pw)
                p = prof.get(off)
                if not od: st = 'UNEXPECTED'
                elif not distinguishing(xw) or p is None: st = 'ok?'          # cannot be judged
                elif len(p) > 1: st = 'MIXED'
                else:
                    want = next(iter(p))
                    st = 'ok' if want in od else 'WRONG (want %s %s)' % (want, perm(xw, ORDERS[want]).hex() if want in ORDERS else '?')
                if show_all or st.startswith(('WRONG', 'UNEXPECTED')):
                    rows.append((off, xw.hex(), pw.hex(), '/'.join(od) or '-', st))
            bad = [x for x in rows if x[4].startswith(('WRONG', 'UNEXPECTED'))]
            res['findings'] += len(bad)
            kind = 'tune' if r in tune_recs else 'LINK ONLY'
            print('  record +0x%x (%s; %s): %d finding(s)' % (r, kind, '; '.join(sorted(recs[r])), len(bad)))
            for off, xh, ph, od, st in rows:
                print('     +0x%03x (DTP +0x%x) Xbox %s PC %s (%s) %s' % (off, r + off, xh, ph, od, st))
            drec['records'].append(dict(offset=r, kind=kind, origins=sorted(recs[r]),
                                        findings=[dict(off=x[0], xbox=x[1], pc=x[2], status=x[4]) for x in bad]))
        res['dtps'].append(drec)
    return res


def main(argv):
    show_all = '--all' in argv
    argv = [a for a in argv if a != '--all']
    rep = None
    if '--report' in argv: k = argv.index('--report'); rep = argv[k + 1]; del argv[k:k + 2]
    if len(argv) < 2 or len(argv) % 2: sys.exit(__doc__)
    out = [check(argv[i], argv[i + 1], show_all) for i in range(0, len(argv), 2)]
    if rep:
        with open(rep, 'w', encoding='utf-8') as f: json.dump(out, f, indent=1)
    if any(o.get('skip') for o in out) and not any(o['dtps'] for o in out): return 2
    return 1 if any(o['findings'] for o in out) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
