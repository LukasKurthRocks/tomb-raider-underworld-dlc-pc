r"""Rule-owned DRM sections (N3, 2026-11-11): sections that a fix RULE owns, so a generic step that runs over a tree
with the rule already applied (the shader re-translation `tools/tu_batch.py inv / run`, `nativefix`) must leave them
alone - and a check that flags a tree / install stack in which a later step overwrote them.

Why (docs/WINDOWS_REBUILD.md finding 52): the n6b shader re-translation (08.11.) read the installed Repair ring files
as its input. Its inventory takes every material whose Xbox pass-2 lib is untranslated (C1-C3 / D) and whose PC
pass-2 lib is a base lib as a "surrogate" - but the ring's base lib 1706 is there ON PURPOSE (ring rule). n6b re-
translated the far LOD 21164 / 20345 (Xbox lib 2254 -> PS 3421, material rewritten, 1152 -> 1216 bytes; the near LOD
21093 / 20344 = Xbox 2118 / 2052 was refused: records), the AMD step (17r / 17z) copied that, and the stack installed
08.11. 17:08 replaced the ring fix (Repair 06a92469 / f1e2ff94) -> pink / green ring (owner 10.11.).

Rules (OWNED):
  ring   tools/b138_fix_tree.py step ring (tests 22 / 24 / 26a, played 2026-10-30): dlc1_ei_grapple_wall.drm materials
         21164 (far) / 21093 (near), dlc1_ei_grapple_ceiling.drm 20345 / 20344 = the PC base ring material 16637 of
         ar_ei_grapple_wall.drm (data + relocations) with its ShaderLibs 1704-1707 and textures, byte for byte

Usage (from the repository root):
  ../bin/pyt -t 600 tools/rule_owned.py check LAYER [LAYER ...] [--ref REF_MODS] [--report FILE]
      LAYER = mods-style folder, lowest first; the effective copy of a rule file is the one of the last layer that
      has it. Per rule file: every owned material must equal the base material 16637 and every section it references
      (ShaderLib / texture) must equal the base file's section; --ref also compares those sections with REF_MODS' copy
      (e.g. the Repair tree). Rule files that no layer has are listed as "not in the stack" (no error).
      Exit 1 when an owned section was overwritten (the guard; Install-TruTree.ps1 -RuleGate, Invoke-TruPipeline Repair)
  ../bin/pyt -t 900 tools/rule_owned.py apply OUT_MODS LAYER [LAYER ...] [--keep-orphans]
      the rule again on top: every effective rule file that fails the check gets the rule (the same tool calls as
      b138_fix_tree) -> OUT_MODS (a top layer for the stack; OUT_MODS below work/rebuild). ShaderLibs that only the
      replaced owned materials used are dropped afterwards (the earlier step's leftovers, e.g. n6b's 3421), unless
      --keep-orphans; refused when an external pointer of the file targets a section index behind the dropped one.
      The written files are checked again (exit 1 when one still fails)
  ../bin/pyt -t 60 tools/rule_owned.py list
      the owned materials / ShaderLibs per file (what tu_batch inv / run / nativefix skip)
Library use: owned_materials(), owned_libs() (file name lower -> set of ids), apply_ring(...) for b138_fix_tree
"""
import sys, os, json, struct, shutil, contextlib, io, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R

RING = {'dlc1_ei_grapple_wall.drm': (21164, 21093), 'dlc1_ei_grapple_ceiling.drm': (20345, 20344)}    # (far, near)
BASE_RING, BASE_LIBS, BASE_MATERIAL = 'ar_ei_grapple_wall.drm', [1704, 1705, 1706, 1707], 16637
RULES = {'ring': dict(files=RING, base=BASE_RING, libs=BASE_LIBS, material=BASE_MATERIAL,
                      source='tools/b138_fix_tree.py step ring (tests 22 / 24 / 26a, played 2026-10-30)')}
SUBDIRS = ('', 'streamgroups')


def owned_materials():
    """{file name (lower): {material ids}} that a rule owns - generic steps must not change them"""
    return {f.lower(): set(m) for r in RULES.values() for f, m in r['files'].items()}


def owned_libs():
    """{file name (lower): {ShaderLib ids}} the owned materials reference after the rule (base libs)"""
    return {f.lower(): set(r['libs']) for r in RULES.values() for f in r['files']}


def _run(mod, args):
    """call a tool's main() with argv-style arguments, return its printed output (as b138_fix_tree.run)"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = mod.main(list(args))
    if r not in (None, 0): raise SystemExit('%s failed: %s' % (mod.__name__, r))
    return buf.getvalue()


def extract_base(path):
    """the PC base ring DRM (bigfile.000, read-only) CDRM-decoded to PATH (tools/bigfile_extract.py pcbig)"""
    import bigfile_extract as BE
    return _run(BE, ['pcbig', BASE_RING, path])


def apply_ring(cur, dst, base, tmp, name, far, near, log=print):
    """the ring rule on one file (moved unchanged from b138_fix_tree 2026-11-11): far-LOD material FAR gets the base
    ring's PC shaders 1704-1707 (copied from BASE when missing), the near LOD NEAR becomes a copy of it, then both get
    the base MATERIAL 16637 with its textures (tools/material_transplant.py). CUR -> DST, intermediates in TMP."""
    import material_shader_swap as MSS, material_copy as MC, material_transplant as MT
    for slot, lib in enumerate(BASE_LIBS):
        nxt = os.path.join(tmp, '%s.%d' % (name, slot))
        extra = ['--add-libs-from', base, ','.join(map(str, BASE_LIBS))] if slot == 0 else []
        log(_run(MSS, [cur, nxt, str(far), str(slot), str(lib)] + extra).strip().splitlines()[-1])
        cur = nxt
    nxt = os.path.join(tmp, '%s.copy' % name)
    log(_run(MC, [cur, nxt, str(near), str(far)]).strip())
    # base MATERIAL, not only its shaders: the base shaders read the texture slots in the base roles (test 26a)
    for i, mid in enumerate((far, near)):
        d = dst if i == 1 else os.path.join(tmp, '%s.far' % name)
        log(_run(MT, [nxt, d, str(mid), base, str(BASE_MATERIAL)]).strip().splitlines()[-1])
        nxt = d


def effective(layers):
    """{name lower: (path, layer index)} - the last layer that has a DRM wins (mods\\ and mods\\streamgroups\\)"""
    eff = {}
    for li, L in enumerate(layers):
        for sub in SUBDIRS:
            d = os.path.join(L, sub)
            if not os.path.isdir(d): continue
            for f in os.listdir(d):
                if f.lower().endswith('.drm'): eff[f.lower()] = (os.path.join(d, f), li)
    return eff


def _sec(D, typ, sid):
    return next((s for s in D.sections if s.type == typ and s.id == sid), None)


def _tuple(m):
    return list(struct.unpack_from('<4I', m.data, 0x28)) if m is not None and len(m.data) >= 0x38 else None


def owned_keys(B):
    """(type, id) of the base material and every section it references by id (ShaderLibs, textures)"""
    bm = _sec(B, 10, BASE_MATERIAL)
    keys = []
    for kind, off in sorted(R.parse(bm.reloc, 'le').idref):
        k = (kind, struct.unpack_from('<I', bm.data, off)[0])
        if k not in keys: keys.append(k)
    return bm, keys


def check_file(name, raw, B, ref=None):
    """-> dict(ok, problems, tuples, orphans, ref) for one rule file (bytes RAW) against the base DRM B"""
    far, near = RING[name]
    D = DW.read(raw, 'le'); bm, keys = owned_keys(B)
    probs = []; tuples = {}
    for mid in (far, near):
        m = _sec(D, 10, mid); tuples[mid] = _tuple(m)
        if m is None: probs.append('material %d missing' % mid)
        elif (m.data, m.reloc) != (bm.data, bm.reloc):
            probs.append('material %d != base %d (shaders %s, %d bytes; base %s, %d bytes)' % (
                mid, BASE_MATERIAL, tuples[mid], len(m.data), _tuple(bm), len(bm.data)))
    for kind, sid in keys:
        s, b = _sec(D, kind, sid), _sec(B, kind, sid)
        if s is None: probs.append('section type %d id %d missing' % (kind, sid))
        elif (s.data, s.reloc) != (b.data, b.reloc): probs.append('section type %d id %d != base' % (kind, sid))
    used = set()
    for s in D.sections:
        for kind, off in R.parse(s.reloc, 'le').idref:
            if kind == 9: used.add(struct.unpack_from('<I', s.data, off)[0])
    orphans = sorted(s.id for s in D.sections if s.type == 9 and s.id not in used)
    rres = None
    if ref is not None:
        F = DW.read(ref, 'le'); diff = []
        for k in [(10, far), (10, near)] + keys:
            a, b = _sec(D, *k), _sec(F, *k)
            if a is None or b is None or (a.data, a.reloc) != (b.data, b.reloc): diff.append('%d:%d' % k)
        rres = dict(owned_sections=2 + len(keys), differ=diff,
                    md5_equal=hashlib.md5(raw).hexdigest() == hashlib.md5(ref).hexdigest())
    return dict(ok=not probs, problems=probs, tuples=tuples, orphans=orphans, ref=rres)


def base_drm():
    """the base ring DRM read in memory (bigfile.000, read-only)"""
    import locals as LC
    from archive import Archive
    from names import crc
    from drm import cdrm_decode
    path, e, pre = LC.SRC['pcbig']
    A = Archive(path, e); recs = A.find(crc(pre + '\\' + BASE_RING))
    if not recs: raise SystemExit('%s not in pcbig' % BASE_RING)
    return DW.read(cdrm_decode(A.read(recs[-1]), e), 'le')


def drop_orphans(path, before_ids):
    """drop ShaderLibs of PATH that no section references any more and that BEFORE_IDS (the libs the owned materials
    used before the rule) contain; refused when an external pointer targets a section index at or behind one"""
    raw = open(path, 'rb').read(); D = DW.read(raw, 'le')
    used = set()
    for s in D.sections:
        for kind, off in R.parse(s.reloc, 'le').idref:
            if kind == 9: used.add(struct.unpack_from('<I', s.data, off)[0])
    drop = [i for i, s in enumerate(D.sections) if s.type == 9 and s.id in before_ids and s.id not in used and s.id not in BASE_LIBS]
    if not drop: return []
    lo = min(drop)
    for s in D.sections:
        for si, _, _ in R.parse(s.reloc, 'le').external:
            if si >= lo: raise SystemExit('%s: external pointer to section %d (>= %d) - orphan ShaderLibs not dropped' % (path, si, lo))
    ids = [D.sections[i].id for i in drop]
    keep = [s for i, s in enumerate(D.sections) if i not in drop]
    D.sections = keep
    o = D.write('le')
    if raw[:4] in (b'CDRM', b'MRDC'): o = DW.cdrm_encode(o, 'le')
    A = [(s.type, s.id, s.data, s.reloc) for s in keep]; Bk = [(s.type, s.id, s.data, s.reloc) for s in DW.read(o, 'le').sections]
    if A != Bk: raise SystemExit('%s: readback after dropping %s differs' % (path, ids))
    open(path, 'wb').write(o)
    return ids


def cmd_check(layers, ref=None, report=None):
    eff = effective(layers); B = base_drm(); res = {}; bad = 0
    for name in RING:
        if name not in eff:
            print('%-30s not in the stack (no layer has it)' % name); res[name] = dict(state='absent'); continue
        p, li = eff[name]; raw = open(p, 'rb').read()
        rp = os.path.join(ref, name) if ref else None
        if rp and not os.path.isfile(rp): raise SystemExit('--ref: %s missing' % rp)
        r = check_file(name, raw, B, open(rp, 'rb').read() if rp else None)
        r.update(path=p, layer=li, md5=hashlib.md5(raw).hexdigest())
        res[name] = r; bad += not r['ok']
        print('%-30s %s  layer %d %s md5 %s  shaders %s' % (name, 'OK  ' if r['ok'] else 'FAIL', li, p, r['md5'][:8],
              ' '.join('%d=%s' % (k, v) for k, v in r['tuples'].items())))
        for pb in r['problems']: print('    %s' % pb)
        if r['orphans']: print('    unreferenced ShaderLibs: %s' % r['orphans'])
        if r['ref'] is not None:
            print('    vs --ref: %d owned sections, %d differ %s, file md5 %s' % (
                r['ref']['owned_sections'], len(r['ref']['differ']), r['ref']['differ'], 'EQUAL' if r['ref']['md5_equal'] else 'differs'))
    if report: json.dump(dict(layers=layers, ref=ref, files=res, failed=bad), open(report, 'w'), indent=1)
    print('rule gate: %s (%d rule file(s) failed; rule ring, owner %s)' % ('PASS' if not bad else 'FAIL', bad, RULES['ring']['source']))
    return 1 if bad else 0


def cmd_apply(out, layers, keep_orphans=False):
    import build_util as BU
    for L in layers: BU.check_out(out, L, must_be_below=True)
    eff = effective(layers); B = base_drm()
    tmp = out + '_tmp'
    if os.path.isdir(tmp): shutil.rmtree(tmp)
    os.makedirs(tmp); os.makedirs(out, exist_ok=True)
    base = os.path.join(tmp, BASE_RING); extract_base(base)
    n = 0
    for name, (far, near) in RING.items():
        if name not in eff: print('%s: not in the stack - nothing to do' % name); continue
        p, li = eff[name]; raw = open(p, 'rb').read()
        if check_file(name, raw, B)['ok']: print('%s: rule in place (layer %d) - not written' % (name, li)); continue
        D = DW.read(raw, 'le')
        before = {x for m in (far, near) for x in (_tuple(_sec(D, 10, m)) or [])}
        dst = os.path.join(out, name)
        print('== %s (layer %d, md5 %s)' % (name, li, hashlib.md5(raw).hexdigest()[:8]))
        apply_ring(p, dst, base, tmp, name, far, near)
        if not keep_orphans:
            ids = drop_orphans(dst, before)
            if ids: print('dropped ShaderLibs %s (only the replaced owned materials used them)' % ids)
        r = check_file(name, open(dst, 'rb').read(), B)
        if not r['ok']: raise SystemExit('%s: rule check fails after apply: %s' % (dst, r['problems']))
        print('%s -> %s md5 %s, rule check OK' % (name, dst, hashlib.md5(open(dst, 'rb').read()).hexdigest()))
        n += 1
    shutil.rmtree(tmp)
    print('apply: %d file(s) written to %s' % (n, out))
    return 0


def main(argv):
    if not argv: sys.exit(__doc__)
    cmd, a = argv[0], list(argv[1:])
    def opt(k):
        if k in a: j = a.index(k); v = a[j + 1]; del a[j:j + 2]; return v
        return None
    if cmd == 'list':
        for f, m in sorted(owned_materials().items()): print('%-30s materials %s  ShaderLibs %s' % (f, sorted(m), sorted(owned_libs()[f])))
        return 0
    if cmd == 'check':
        ref, rep = opt('--ref'), opt('--report')
        if not a: sys.exit(__doc__)
        return cmd_check(a, ref, rep)
    if cmd == 'apply':
        keep = '--keep-orphans' in a; a = [x for x in a if x != '--keep-orphans']
        if len(a) < 2: sys.exit(__doc__)
        return cmd_apply(os.path.abspath(a[0]), a[1:], keep)
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
