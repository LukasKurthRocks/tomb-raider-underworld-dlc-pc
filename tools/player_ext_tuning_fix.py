"""DLC 2 player tuning (object 858 `player_tru_dlc2_extension`, DTP 22497, tuning struct at +0xf0): typed rule for the
words the title-update code reads - the targeter 8 / 9 parameter table (tuning +0x90 / +0x94) and the K9 splash
damage-type pair table (tuning +0x78 / +0x7c) - as a pipeline rule, with gate and fix (2026-11-07, docs
Befund-Datenfixes-0711.md fixes 5 / 6; Befund-Schattenkampf.md section 6, Befund-TU-K9-K11-0711.md section 9).

Field types (from the code that reads them):
  targeter table: tools/tuning_target_fix.FIELDS (46 words; TU 0x82402248 `lwz` count, 0x82402264 `lbz` index,
    0x82403b48 `lwz` flags; PC targeter ctor tru+0x31d900 `cmp dword` / `movzx word` / `movss`; the record's second
    u16 and first float have no PC reader - their type comes from the identical sibling records, as that tool says)
  K9 pair table: TU MeleeSplashDamage 0x823e1220 reads tuning +0x78 (pointer) / +0x7c (count) and loops over 8-byte
    entries {from, to} with `lwz` + `cmpw` (signed 32-bit) -> count and every entry word are s32
  -> expected PC bytes = the Xbox bytes in the field's little-endian order (tuning_target_fix.expect).

Why the tree holds wrong words: the DTP has no base twin of its layout, so it takes the generic 'convert' route (the
learned type-7 table, generic_type0.lookup: class by label key + value shape); words such as count 2 (`00 00 00 02`,
shape 'H0' / 'B3') came out as u16 pairs, `08 00 00 00` as u32 etc. The targeter words were repaired only by hand for
the test tree dlc_test50l_combat (tuning_target_fix.py --out, 2026-11-03) - never as a pipeline rule, so every new
pipeline run (Convert -> dlc2_asm_stage2a) brings them back; the `twins` step of dlc_fixes_build repairs 7 of the
words (those a base twin covers), the rest stay wrong.

Rule: a word is set only where the PC word is another byte order of the Xbox word (raw / u32 / u16u16 / u8u8u16 /
u16u8u8); a PC word that is no byte order of it -> UNEXPECTED (fix_drm raises SystemExit, the gate fails). Pointers
must be relocated identically on both sides (checked); nothing else of the DRM changes (proven on every write).

Modes (from the repository root; read-only except `fix`):
  ../bin/pyt -t 600 tools/player_ext_tuning_fix.py scan LIST_OR_DIR [--pack PACK] [--all] [--report R.json]
        exit 1 when any word is wrong or unexpected (the gate); LIST_OR_DIR as tools/soundplex_sequence_fix.py
  ../bin/pyt -t 600 tools/player_ext_tuning_fix.py fix LIST_OR_DIR OUTDIR [--pack PACK]
        writes the fixed DRM to OUTDIR (md5.tsv + player_ext_tuning_fix.log.txt in OUTDIR's parent)
Library (planned step `exttuning` of tools/dlc_struct_fixes.py): plan(XD, PD, rel), fix_drm(XD, raw, rel)
"""
import sys, os, struct, collections, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_write as DW
import tuning_target_fix as TT

NAME = 'player_tru_dlc2_extension.drm'
SID = TT.SID
TUNING = TT.BASE
ORDERS = {'raw': (0, 1, 2, 3), 'u32': (3, 2, 1, 0), 'u16u16': (1, 0, 3, 2), 'u8u8u16': (0, 1, 3, 2), 'u16u8u8': (1, 0, 2, 3)}


def order_of(xw, pw):
    for n, p in ORDERS.items():
        if bytes(xw[i] for i in p) == pw: return n
    return None


def fields(xd, xin):
    """[(offset, kind, why)]: tuning_target_fix.FIELDS + the K9 pair table found through the Xbox relocation"""
    out = list(TT.FIELDS)
    pt, cnt = TUNING + 0x78, TUNING + 0x7c
    out.append((cnt, 'u32', 'tuning +0x7c: K9 pair count (TU 0x823e1220 lwz)'))
    tab = xin.get(pt)
    n = struct.unpack_from('>i', xd, cnt)[0]
    if tab is not None and 0 < n <= 64 and tab + 8 * n <= len(xd):
        for k in range(n):
            out.append((tab + 8 * k, 'u32', 'K9 pair %d: from (s32, TU lwz + cmpw)' % k))
            out.append((tab + 8 * k + 4, 'u32', 'K9 pair %d: to (s32, TU lwz)' % k))
    return out


def plan(XD, PD, rel=NAME):
    res = dict(rows=[], skip=None)
    if os.path.basename(rel.replace('\\', '/')).lower() != NAME: res['skip'] = 'not %s' % NAME; return res
    sx = next((s for s in XD.sections if s.type == 7 and s.id == SID), None)
    kp = next((k for k, s in enumerate(PD.sections) if s.type == 7 and s.id == SID), None)
    if sx is None or kp is None: res['skip'] = 'DTP %d missing (Xbox %s, PC %s)' % (SID, sx is not None, kp is not None); return res
    sp = PD.sections[kp]
    xd, pd = bytes(sx.data), bytes(sp.data)
    xin, pin = dict(R.parse(bytes(sx.reloc), 'be').internal), dict(R.parse(bytes(sp.reloc), 'le').internal)
    if len(xd) != len(pd) or xin != pin: res['skip'] = 'layout differs (size / internal relocations)'; return res
    if struct.unpack_from('>HH', xd, TUNING) != (1, 60): res['skip'] = 'no tuning struct {1, 60} at +0x%x' % TUNING; return res
    for off, kind, why in fields(xd, xin):
        if off in xin: res['skip'] = '+0x%x is a pointer - layout assumption wrong' % off; res['rows'] = []; return res
        xw, pw = xd[off:off + 4], pd[off:off + 4]
        want = TT.expect(xw, kind)
        if want is None: st = 'UNEXPECTED'
        elif pw == want: st = 'ok'
        else:
            od = order_of(xw, pw)
            st = 'fix:%s' % od if od else 'UNEXPECTED'
        res['rows'].append((kp, SID, off, kind, why, xw, pw, want, st))
    return res


def fix_drm(XD, raw, rel=NAME):
    PD = DW.read(raw, 'le')
    info = plan(XD, PD, rel)
    bad = [r for r in info['rows'] if r[8] == 'UNEXPECTED']
    if bad:
        raise SystemExit('exttuning %s: %d UNEXPECTED word(s): %s' % (rel, len(bad), ', '.join(
            '+%#x Xbox %s PC %s' % (r[2], r[5].hex(), r[6].hex()) for r in bad[:10])))
    todo = [r for r in info['rows'] if r[8].startswith('fix:')]
    if not todo: return None, [], info
    changes = []
    for k, sid, off, kind, why, xw, pw, want, st in todo:
        s = PD.sections[k]; b = bytearray(s.data)
        assert bytes(b[off:off + 4]) == pw
        b[off:off + 4] = want; s.data = bytes(b)
        changes.append((k, off, pw, want, sid))
    new = PD.write('le')
    if raw[:4] == b'CDRM': new = DW.cdrm_encode(new, 'le')
    verify(raw, new, changes, XD, rel)
    return new, changes, info


def verify(raw, new, changes, XD, rel=NAME):
    A, B = DW.read(raw, 'le'), DW.read(new, 'le')
    assert len(A.sections) == len(B.sections) and A.names == B.names and A.pad == B.pad, 'file layout changed'
    planned = {(k, q + j) for k, q, a, b, sid in changes for j in range(4) if a[j] != b[j]}
    got = set()
    for k, (a, b) in enumerate(zip(A.sections, B.sections)):
        assert (a.type, a.id, a.flags, a.ver, a.spec, a.pad, bytes(a.reloc), len(a.data)) == \
               (b.type, b.id, b.flags, b.ver, b.spec, b.pad, bytes(b.reloc), len(b.data)), 'section %d header changed' % k
        if a.data != b.data: got |= {(k, i) for i in range(len(a.data)) if a.data[i] != b.data[i]}
    assert got == planned, '%d bytes differ, %d planned' % (len(got), len(planned))
    again = [r for r in plan(XD, B, rel)['rows'] if r[8] != 'ok']
    assert not again, 're-plan finds %d words' % len(again)
    return len(got)


def file_list(spec):
    import soundplex_sequence_fix as SQ
    return [p for p in SQ.file_list(spec) if os.path.basename(p).lower() == NAME]


def check_file(path, pack=None):
    import soundplex_sequence_fix as SQ
    PD = DW.read(open(path, 'rb').read(), 'le')
    cands = SQ.xbox_candidates(path, pack or 'pack11')
    if not cands: return 'no Xbox source', None, None
    best = None
    for XD, pk in cands:
        info = plan(XD, PD, path)
        score = (info['skip'] is None, len(info['rows']))
        if best is None or score > best[0]: best = (score, XD, pk, info)
    return 'ok (%s)' % best[2], best[3], best[1]


def scan(paths, show_all, pack):
    tot = collections.Counter(); lines = []; files = []
    for path in paths:
        st, info, XD = check_file(path, pack)
        tot['files'] += 1
        if info is None or info['skip']:
            tot['skipped'] += 1; ln = '%s: %s%s' % (path, st, ('; ' + info['skip']) if info and info['skip'] else '')
            print(ln); lines.append(ln); continue
        bad = [r for r in info['rows'] if r[8] != 'ok']
        tot['words'] += len(info['rows'])
        tot['wrong'] += sum(1 for r in bad if r[8].startswith('fix:'))
        tot['unexpected'] += sum(1 for r in bad if r[8] == 'UNEXPECTED')
        if bad: files.append(path.replace('\\', '/'))
        ln = '%s: %s, DTP %d, %d words, %d not ok' % (path, st, SID, len(info['rows']), len(bad))
        print(ln); lines.append(ln)
        for r in (info['rows'] if show_all else bad):
            ln = '   +0x%03x %-6s Xbox %s PC %s rule %s %s  (%s)' % (r[2], r[3], r[5].hex(), r[6].hex(),
                                                                   r[7].hex() if r[7] else '-', r[8], r[4])
            print(ln); lines.append(ln)
    res = 'FAIL' if tot['wrong'] or tot['unexpected'] else 'ok'
    print('TOTAL %s' % dict(tot)); print('scan: %s' % res)
    return res, dict(tot), files, lines


def fix(spec, outdir, pack):
    os.makedirs(outdir, exist_ok=True)
    top = os.path.dirname(os.path.abspath(outdir))
    log = open(os.path.join(top, 'player_ext_tuning_fix.log.txt'), 'w', encoding='utf-8', newline='\r\n')
    md5s = ['md5\tpath']
    for path in file_list(spec):
        st, info, XD = check_file(path, pack)
        if info is None or info['skip'] or not any(r[8] != 'ok' for r in info['rows']): continue
        raw = open(path, 'rb').read()
        new, changes, info = fix_drm(XD, raw, path)
        if new is None: continue
        for k, q, pw, w, sid in changes:
            why = next(r[4] for r in info['rows'] if r[2] == q)
            line = '%s DTP %d +%#05x: %s -> %s (%s)' % (NAME, sid, q, pw.hex(), w.hex(), why)
            print(line); log.write(line + '\n')
        dst = os.path.join(outdir, NAME)
        open(dst, 'wb').write(new)
        nd = verify(raw, open(dst, 'rb').read(), changes, XD, path)
        h = hashlib.md5(new).hexdigest()
        line = '%s: %d words, %d bytes differ from %s (md5 %s), headers + relocations identical, re-plan 0; new md5 %s sha256 %s' % (
            NAME, len(changes), nd, path, hashlib.md5(raw).hexdigest(), h, hashlib.sha256(new).hexdigest())
        print(line); log.write(line + '\n'); md5s.append('%s\t%s' % (h, NAME))
    open(os.path.join(top, 'md5.tsv'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md5s) + '\n')
    log.close()
    print('files written', len(md5s) - 1)


def main(a):
    if not a: sys.exit(__doc__)
    def opt(key):
        if key in a:
            k = a.index(key); v = a[k + 1]; del a[k:k + 2]; return v
    pack = opt('--pack'); report = opt('--report')
    show_all = '--all' in a
    a = [x for x in a if x != '--all']
    if a[0] == 'scan' and len(a) >= 2:
        r, tot, files, lines = scan(file_list(a[1]), show_all, pack)
        if report:
            os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
            json.dump(dict(result=r, spec=a[1], totals=tot, files=files, lines=lines), open(report, 'w', encoding='utf-8'), indent=1)
        return 1 if r != 'ok' else 0
    if a[0] == 'fix' and len(a) >= 3: fix(a[1], a[2], pack); return 0
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
