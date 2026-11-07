"""Give the PC generalbank the title update's player object list (GlobalInfo +4, generalbank DTP 2): the TU list has
29 ids - the 28 of retail / PC plus 857 `doppelganger_casual` (the DLC 2 player object) - retail, the PC and every
tree of ours have 28 (K12, docs Befund-Exe-Stellen-K8-K14-0611.md; data translation, writes only OUT).

The list (proven on the PC code, tools/globalinfo_player_list.py): GlobalInfo = DTP 2 +0xf0, GlobalInfo +4 -> header
{u16 count; pad; +4 pointer -> u16 ids}. Readers (PC): tru+0x1c1820 / tru+0x1c1900 (a unit's intro objects are
requested / dumped with the unit - EXCEPT the ids in this list), tru+0x1d4166 (intro records whose object id is in the
list are rewritten to the current costume [0xe7f1c8]), tru+0x183441 (index of the current costume), tru+0x2f0acd (next
costume of the cycle), tru+0x1de62d (level init: intro flag 0x80 except for list ids). The Xbox TU reads the same list
with the same code (K12); upstream patched the PC exe instead (append [0xe7f1c8] at level init, tru+0x1de3b5).

What the tool does (every value read from the files, nothing typed in):
  1. TU list (tu:generalbank.drm) and retail list (retail:generalbank.drm), DTP 2, GlobalInfo +4 (Xbox originals).
  2. The PC input list must equal the retail list (same ids, same order) - else stop (another base). TU-only ids =
     the TU list after the retail prefix (the TU only appends: the first 28 TU ids must equal retail - else stop).
  3. Each TU-only id must name the same object on the PC side (Xbox TU objectlist vs a PC objectlist.txt of a DLC
     tree, `--pc-objectlist`; DLC object ids are kept by the port) - else stop.
  4. A new id block = PC ids + TU-only ids (u16, padded to 4 bytes) is appended to the END of DTP 2; the header's
     pointer (+4, internal relocation) moves to it and the count (+0) becomes the TU count. Nothing else moves (the
     old 28-id block stays as unused bytes), so no other pointer / external relocation into DTP 2 changes. The TU
     grew its list in place (+0x1300: 28 -> 29 ids); the list the engine reads is the same.
  5. Proof on the written file: re-read, only DTP 2 differs; its old bytes are unchanged except the count word and the
     header pointer; relocations = old + the one retarget; the list read back = the TU list.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/globalinfo_player_list_fix.py IN_generalbank.drm OUT_generalbank.drm [--pc-objectlist F]
        [--check] [--done-ok]
    --check    only report (nothing written); exit 0 = would change, 3 = nothing to do
    --done-ok  (pipeline, idempotent) list already = TU: copy IN to OUT unchanged, exit 0 (else exit 3)
  ../bin/pyt -t 300 tools/globalinfo_player_list_fix.py --verify generalbank.drm [--report R.json]
        gate: exit 0 = the PC list equals the TU list (ids, order), 1 = not (nothing written)
"""
import sys, os, struct, hashlib, json, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R, objlists as OL
import globalinfo_player_list as GP

HERE = os.path.dirname(os.path.abspath(__file__))
GI = 0xf0
TU_OBJECTLIST = os.path.join(HERE, '..', 'work', 'generic', 'lists', 'xboxtu_objectlist.txt')
PC_OBJECTLISTS = [os.path.join(HERE, '..', 'work', 'rebuild', d, 'mods', 'tr8', 'pc-w', 'objectlist.txt')
                  for d in ('dlc2_asm_stage2b', 'dlc2_asm_stage2a')]


def xbox_lists():
    tu, e1 = GP.player_list('tu:generalbank.drm', GI)
    rt, e2 = GP.player_list('retail:generalbank.drm', GI)
    if e1 or e2: raise SystemExit('Xbox list not readable: TU %s, retail %s' % (e1, e2))
    return tu[2], rt[2]


def names_of(path):
    return OL.read_objectlist(open(path, 'rb').read()) if path and os.path.exists(path) else None


def pc_list(D):
    """(DTP 2 section index, header offset p, ids offset q, ids) of a PC Drm"""
    k = next((i for i, s in enumerate(D.sections) if s.type == 7 and s.id == 2), None)
    if k is None: raise SystemExit('DTP 2 not found')
    s = D.sections[k]; d = bytes(s.data)
    it = dict(R.parse(bytes(s.reloc), 'le').internal)
    p = it.get(GI + 4); q = it.get(p + 4) if p is not None else None
    if p is None or q is None: raise SystemExit('GlobalInfo +4 / list +4 is not a pointer in DTP 2')
    n = struct.unpack_from('<H', d, p)[0]
    return k, p, q, [struct.unpack_from('<H', d, q + 2 * j)[0] for j in range(n)]


def plan(D, pc_objectlist):
    tu, rt = xbox_lists()
    k, p, q, ids = pc_list(D)
    info = dict(tu=tu, retail=rt, pc=ids, header=p, ids_at=q, added=[], names={})
    if ids == tu: info['status'] = 'done'; return info
    if tu[:len(rt)] != rt: raise SystemExit('TU list does not start with the retail list - not a pure append: TU %s retail %s' % (tu, rt))
    if ids != rt: raise SystemExit('PC list differs from the retail list (another base?): PC %s retail %s' % (ids, rt))
    added = tu[len(rt):]
    xn = names_of(TU_OBJECTLIST) or {}
    pl = pc_objectlist or next((f for f in PC_OBJECTLISTS if os.path.exists(f)), None)
    pn = names_of(pl)
    for i in added:
        if pn is None: info['names'][i] = (xn.get(i), None, 'PC objectlist not given - not checked')
        elif xn.get(i) != pn.get(i):
            raise SystemExit('id %d: TU object %r, PC objectlist %s has %r - not the same object' % (i, xn.get(i), pl, pn.get(i)))
        else: info['names'][i] = (xn.get(i), pn.get(i), os.path.relpath(pl, os.path.join(HERE, '..')).replace('\\', '/'))
    info.update(added=added, status='todo', section=k)
    return info


def apply(raw, info):
    D = DW.read(raw, 'le')
    k = info['section']; s = D.sections[k]
    d = bytearray(s.data); p = info['header']
    new_ids = info['pc'] + info['added']
    q2 = (len(d) + 3) & ~3
    blk = struct.pack('<%dH' % len(new_ids), *new_ids)
    blk += b'\0' * ((-len(blk)) % 4)
    d += b'\0' * (q2 - len(d)) + blk
    struct.pack_into('<H', d, p, len(new_ids))
    rel = R.parse(bytes(s.reloc), 'le')
    hits = [j for j, (o, t) in enumerate(rel.internal) if o == p + 4]
    assert len(hits) == 1, 'header pointer relocation not unique'
    rel.internal[hits[0]] = (p + 4, q2)
    # the pointer slot holds the target offset on disk in this format? keep the stored word in step with the relocation
    old_word = struct.unpack_from('<I', d, p + 4)[0]
    if old_word == info['ids_at']: struct.pack_into('<I', d, p + 4, q2)
    D.sections[k] = DW.Section(s.type, s.id, bytes(d), R.write(rel, 'le'), s.flags, s.ver, s.spec, s.pad)
    out = D.write('le')
    if raw[:4] == b'CDRM': out = DW.cdrm_encode(out, 'le')
    return out, q2, old_word


def prove(raw, out, info, q2):
    A, B = DW.read(raw, 'le'), DW.read(out, 'le')
    assert len(A.sections) == len(B.sections) and A.names == B.names and A.pad == B.pad, 'file layout changed'
    k = info['section']; p = info['header']
    for j, (a, b) in enumerate(zip(A.sections, B.sections)):
        if j == k: continue
        assert (a.type, a.id, a.flags, a.ver, a.spec, a.pad, bytes(a.reloc), bytes(a.data)) == \
               (b.type, b.id, b.flags, b.ver, b.spec, b.pad, bytes(b.reloc), bytes(b.data)), 'section %d changed' % j
    a, b = A.sections[k], B.sections[k]
    assert (a.type, a.id, a.flags, a.ver, a.spec, a.pad) == (b.type, b.id, b.flags, b.ver, b.spec, b.pad), 'DTP 2 header changed'
    ad, bd = bytes(a.data), bytes(b.data)
    diff = [i for i in range(len(ad)) if ad[i] != bd[i]]
    assert all(p <= i < p + 2 or p + 4 <= i < p + 8 for i in diff), 'DTP 2 bytes changed outside count / pointer: %s' % diff[:8]
    ra, rb = R.parse(bytes(a.reloc), 'le'), R.parse(bytes(b.reloc), 'le')
    ia, ib = dict(ra.internal), dict(rb.internal)
    assert set(ia) == set(ib) and all(ia[o] == ib[o] for o in ia if o != p + 4) and ib[p + 4] == q2, 'relocations changed'
    assert (ra.external, ra.idref, ra.idref_a) == (rb.external, rb.idref, rb.idref_a), 'external / id relocations changed'
    got = pc_list(B)[3]
    assert got == info['tu'], 'list read back %s != TU %s' % (got, info['tu'])
    return len(diff), len(bd) - len(ad)


def verify(path, report):
    tu, rt = xbox_lists()
    ids = pc_list(DW.read(open(path, 'rb').read(), 'le'))[3]
    ok = ids == tu
    print('%s: PC list %d ids, TU %d ids, retail %d ids -> %s%s' % (path, len(ids), len(tu), len(rt), 'ok (= TU)' if ok else 'NOT the TU list',
                                                                   '' if ok else '; missing %s' % [i for i in tu if i not in ids]))
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        json.dump(dict(file=path.replace('\\', '/'), ok=ok, pc=ids, tu=tu, retail=rt), open(report, 'w'), indent=1)
    return 0 if ok else 1


def main(argv):
    if not argv: sys.exit(__doc__)
    report = None
    if '--report' in argv: k = argv.index('--report'); report = argv[k + 1]; del argv[k:k + 2]
    pol = None
    if '--pc-objectlist' in argv: k = argv.index('--pc-objectlist'); pol = argv[k + 1]; del argv[k:k + 2]
    if argv[0] == '--verify': return verify(argv[1], report)
    check, done_ok = '--check' in argv, '--done-ok' in argv
    argv = [a for a in argv if a not in ('--check', '--done-ok')]
    src, dst = argv[0], (argv[1] if len(argv) > 1 else None)
    raw = open(src, 'rb').read()
    info = plan(DW.read(raw, 'le'), pol)
    print('TU list (%d): %s' % (len(info['tu']), info['tu']))
    print('retail list (%d), PC input list (%d): %s' % (len(info['retail']), len(info['pc']), 'equal' if info['retail'] == info['pc'] else 'differ'))
    if info['status'] == 'done':
        print('the PC list already equals the TU list - nothing to do')
        if done_ok and dst and not check:
            shutil.copyfile(src, dst); print('copied %s -> %s unchanged' % (src, dst)); return 0
        return 3
    for i in info['added']:
        print('TU-only id %d: TU name %r, PC name %r (%s)' % ((i,) + info['names'][i]))
    if check or not dst: return 0
    out, q2, old_word = apply(raw, info)
    ndiff, grow = prove(raw, out, info, q2)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    open(dst, 'wb').write(out)
    assert open(dst, 'rb').read() == out
    print('DTP 2: count +0x%x %d -> %d, pointer +0x%x -> new id block +0x%x (old block +0x%x left as is, stored word was 0x%x), '
          'section +%d bytes' % (info['header'], len(info['pc']), len(info['tu']), info['header'] + 4, q2, info['ids_at'], old_word, grow))
    print('proof: only DTP 2 changed; %d old bytes differ (count / pointer only); relocations = old + 1 retarget; list read back = TU'
          % ndiff)
    print('wrote %s md5 %s (input md5 %s)' % (dst, hashlib.md5(out).hexdigest(), hashlib.md5(raw).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
