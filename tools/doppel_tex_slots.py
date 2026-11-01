"""Texture records of the materials of one figure, PC against the Xbox original, read-only: per material the pixel
shader libraries of pass 0 / 2, per texture record the sampler register (record byte 13), the sampler NAME the
PC / Xbox pixel shaders declare at that register (CTAB, regset 3), the texture id, its format (PC PCD9 fourcc / Xbox
low 6 bits) and whether a reference DRM (e.g. pc_lara, resident at the same time) carries a texture / material /
ShaderLib with the same id and other bytes (the engine keeps each (type, id) once).
Test 48h (2026-11-01): the doppelganger (object 857) renders with cyan hair, white trousers with red blotches.

Materials are paired by the order of the material references (type 10) of the figure mesh, PC mesh PCID vs Xbox
mesh XID; materials outside the mesh are paired by equal id when the Xbox file has it.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/doppel_tex_slots.py PC.drm XBOX.drm --mesh PCID[:XID] [--ref REF.drm] [--all] [--params]
  --all: also the materials that are not referenced by the mesh; --params: MaterialParams vec4 values PC / Xbox
Output per material: 'BAD' on a record whose PC sampler name (pass 2, else pass 0) differs from its Xbox sampler name.
"""
import sys, os, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import shaderlib as SL
import material_reslot as MR
NT = MR.name_type()

FOURCC = {0x31545844: 'DXT1', 0x33545844: 'DXT3', 0x35545844: 'DXT5', 0x15: 'ARGB'}
XFMT = {0x12: 'DXT1', 0x13: 'DXT2/3', 0x14: 'DXT4/5', 0x31: 'DXN', 0x06: 'ARGB8', 0x3a: 'DXT5A', 0x3b: 'CTX1'}


def load(path, e):
    D = DW.read(open(path, 'rb').read(), e)
    by = {}
    for s in D.sections: by.setdefault((s.type, s.id), s)
    return D, by


def samplers(by, lid, plat, e):
    """register -> sampler name over all occupied slots of ShaderLib lid (None if the lib is missing)"""
    s = by.get((9, lid))
    if s is None: return None
    lib = SL.parse(s.data, e)
    out = {}
    for o, ent in lib['entries'].items():
        for n, rs, ri, rc in SL.constants(ent['blob'], plat)[1]:
            if rs == 3:
                for j in range(max(1, rc)): out.setdefault(ri + j, SL.norm_name(n))
    return out


def records(s, e):
    r = R.parse(s.reloc, e); tp = dict(r.internal).get(0x54)
    f = e == 'be' and '>' or '<'
    d = s.data; out = []
    if tp is None: return out
    for k in range(d[0x52]):
        tid, u1, typ = struct.unpack_from(f + 'III', d, tp + 16 * k)
        out.append((tid, typ, d[tp + 16 * k + 12], d[tp + 16 * k + 13]))
    return out


def libs_of(s, e):
    f = e == 'be' and '>' or '<'
    return struct.unpack_from(f + '4I', s.data, 0x28)


def texfmt(by, tid, e):
    s = by.get((5, tid))
    if s is None: return '-'
    if e == 'le':
        v = struct.unpack_from('<I', s.data, 4)[0]; w, h = struct.unpack_from('<HH', s.data, 12)
        return '%s %dx%d' % (FOURCC.get(v, hex(v)), w, h)
    v = struct.unpack_from('>I', s.data, 4)[0] & 0x3f
    return XFMT.get(v, hex(v))


def mesh_mats(by, mid, e):
    s = by.get((12, mid))
    if s is None: raise SystemExit('mesh %d not found' % mid)
    r = R.parse(s.reloc, e); f = e == 'be' and '>' or '<'
    return [struct.unpack_from(f + 'I', s.data, o)[0] for t, o in sorted(r.idref, key=lambda x: x[1]) if t == 10]


def same(a, b):
    return a is not None and b is not None and hashlib.md5(a.data).digest() == hashlib.md5(b.data).digest()


def main(argv):
    global SHOWP
    allm = '--all' in argv; SHOWP = '--params' in argv; argv = [a for a in argv if a not in ('--all', '--params')]
    ref = None
    if '--ref' in argv: k = argv.index('--ref'); ref = argv[k + 1]; del argv[k:k + 2]
    k = argv.index('--mesh'); m = argv[k + 1]; del argv[k:k + 2]
    pm, xm = (int(x) for x in m.split(':')) if ':' in m else (int(m), int(m))
    pcf, xf = argv[:2]
    PD, P = load(pcf, 'le'); XD, X = load(xf, 'be')
    RB = load(ref, 'le')[1] if ref else {}
    pl, xl = mesh_mats(P, pm, 'le'), mesh_mats(X, xm, 'be')
    print('mesh PC %d: %d materials, Xbox %d: %d materials' % (pm, len(pl), xm, len(xl)))
    pairs = list(zip(pl, xl))
    if allm:
        seen = set(pl)
        pairs += [(s.id, s.id if (10, s.id) in X else None) for s in PD.sections if s.type == 10 and s.id not in seen]
    nbad = 0
    for i, (pid, xid) in enumerate(pairs):
        ps, xs = P.get((10, pid)), X.get((10, xid)) if xid is not None else None
        if ps is None: print('PC material %d missing' % pid); continue
        pt = libs_of(ps, 'le'); xt = libs_of(xs, 'be') if xs else (0, 0, 0, 0)
        rm = RB.get((10, pid))
        resid = '' if rm is None else ('  REF HAS SAME ID: %s' % ('identical' if same(rm, ps) else 'DIFFERENT BYTES'))
        print('\n#%d PC 10:%d  PS p0 %d p2 %d VS %d | Xbox 10:%s  PS p0 %d p2 %d VS %d%s'
              % (i, pid, pt[0], pt[2], pt[3], xid, xt[0], xt[2], xt[3], resid))
        if rm is not None and not same(rm, ps):
            a, b = ps.data, rm.data
            dw = ['+%#x %08x/%08x' % (o, struct.unpack_from('<I', a, o)[0], struct.unpack_from('<I', b, o)[0])
                  for o in range(0, min(len(a), len(b)) - 3, 4) if a[o:o + 4] != b[o:o + 4]]
            print('    vs REF: %d / %d bytes, %d words differ: %s' % (len(a), len(b), len(dw), ' '.join(dw[:12])))
        # MaterialParams: vec4 count of the material (+0x58) against the count the pass-2 PS reads (CTAB, c100)
        def mpc(by, lid, plat, e):
            s9 = by.get((9, lid)) if lid else None
            if s9 is None: return None
            return max([rc for ent in SL.parse(s9.data, e)['entries'].values()
                        for n, rs, ri, rc in SL.constants(ent['blob'], plat)[1] if n == 'MaterialParams'] or [0])
        pmc, xmc = struct.unpack_from('<I', ps.data, 0x58)[0], struct.unpack_from('>I', xs.data, 0x58)[0] if xs else None
        lp, lx = mpc(P, pt[2], 'p', 'le'), mpc(X, xt[2], 'x', 'be') if xs else None
        print('    MaterialParams: PC material %s vec4, PC p2 lib reads %s | Xbox material %s, Xbox p2 lib reads %s%s'
              % (pmc, lp, xmc, lx, '  PARAMS-LAYOUT' if xs and lp != lx else ''))
        if SHOWP:
            def mpv(s, e):
                f = '>' if e == 'be' else '<'
                o = dict(R.parse(s.reloc, e).internal).get(0x5C); n = struct.unpack_from(f + 'I', s.data, 0x58)[0]
                return [struct.unpack_from(f + '4f', s.data, o + 16 * j) for j in range(n)] if o is not None else []
            for j, v in enumerate(mpv(ps, 'le')): print('      PC   MP[%d] %s' % (j, ' '.join('%.4g' % x for x in v)))
            if xs:
                for j, v in enumerate(mpv(xs, 'be')): print('      Xbox MP[%d] %s' % (j, ' '.join('%.4g' % x for x in v)))
        pn2, pn0 = samplers(P, pt[2], 'p', 'le') or {}, samplers(P, pt[0], 'p', 'le') or {}
        for lid in (pt[0], pt[2]):
            if lid and RB.get((9, lid)) is not None and not same(RB[(9, lid)], P.get((9, lid))):
                print('    ShaderLib %d: REF copy has other bytes' % lid)
        xn2 = samplers(X, xt[2], 'x', 'be') or {} if xs else {}
        xn0 = samplers(X, xt[0], 'x', 'be') or {} if xs else {}
        print('    PC  p2 samplers %s' % ' '.join('s%d=%s' % kv for kv in sorted(pn2.items())))
        if xs: print('    Xbox p2 samplers %s' % ' '.join('s%d=%s' % kv for kv in sorted(xn2.items())))
        pr = records(ps, 'le'); xr = records(xs, 'be') if xs else []
        # every PC sampler register of pass 0 / 2 that is not an engine sampler: full name, expected record type
        # (majority type of that name over the base PC materials, tools/material_reslot.name_type), bound record
        full = {}
        for lid in (pt[0], pt[2]):
            s9 = P.get((9, lid)) if lid else None
            if s9 is None: continue
            for o, ent in SL.parse(s9.data, 'le')['entries'].items():
                for n, rs, ri, rc in SL.constants(ent['blob'], 'p')[1]:
                    if rs == 3 and n not in MR.ENGINE:
                        for j in range(max(1, rc)): full.setdefault(ri + j, set()).add(n)
        bound = {}
        for tid, typ, fl, slot in pr: bound.setdefault(slot, []).append((tid, typ))
        for r in sorted(full):
            exp = {NT.get(n) for n in full[r]} - {None}
            got = bound.get(r)
            flag = 'UNBOUND' if not got else ('TYPE' if exp and not any(t in exp for _, t in got) else '')
            if flag: nbad += 1
            print('    PC s%-2d %-48s expects type %-6s bound %-18s %s'
                  % (r, '/'.join(sorted(full[r]))[:48], ','.join(map(str, sorted(exp))) or '?',
                     ' '.join('%d(t%d)' % g for g in got) if got else '-', flag))
        for j, (tid, typ, fl, slot) in enumerate(pr):
            pname = pn2.get(slot) or pn0.get(slot) or '(unsampled)'
            line = '    rec %d: tex %5d %-14s type %d fl %d  PC s%d %-34s' % (j, tid, texfmt(P, tid, 'le'), typ, fl, slot, pname)
            if j < len(xr):
                xt_, xty, xfl, xsl = xr[j]
                xname = xn2.get(xsl) or xn0.get(xsl) or '(unsampled)'
                bad = pname != xname
                nbad += bad
                line += ' | Xbox tex %5d %-7s s%d %-34s%s' % (xt_, texfmt(X, xt_, 'be'), xsl, xname, '  BAD' if bad else '')
            rt = RB.get((5, tid))
            if rt is not None: line += '  [ref tex %d %s]' % (tid, 'same' if same(rt, P.get((5, tid))) else 'OTHER BYTES')
            print(line)
    print('\n%d records whose PC sampler name differs from the Xbox one' % nbad)


if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    main(sys.argv[1:])
