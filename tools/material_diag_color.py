"""DIAGNOSTIC tool (test 51j, 2026-11-04): give single materials of a PC DRM an unmistakable colour, so it can be seen in
game where a material is drawn (e.g. "is the DLC 2 light beam material 23157?", "where do the 9 materials that stay on
surrogate shaders appear?"). Two kinds of change, both only inside the named material records:

  tint:MAT:IDX:X,Y,Z,W     set lanes of PS MaterialParams[IDX] (block pointer +0x5C, count +0x58); '=' keeps a lane.
                           For materials whose pass-2 PS multiplies the texture by that vector (check the disassembly).
  paint:MAT:TEXID:RRGGBB   add ONE flat-colour texture section TEXID (PCD9 DXT1 4x4 + 2 mips, the layout of the
                           engine's 4x4 white texture 255; section header fields copied from the file's texture 255)
                           (without 255 in the file: texture 255 of the --template PC DRM)
                           and point the PS texture records of MAT at it - only records whose sampler register is
                           declared dcl_2d by every PS lib of the material (+0x28 / +0x2C / +0x30) that uses it, is
                           sampled by the pass-2 PS (+0x30) and is not a normal-map sampler (CTAB name '_Normal_').
                           Records on cube samplers, normal maps, unsampled registers and the extra records after the
                           first +0x52 (other texture group) stay unchanged.

Every other byte of the file stays the same: the tool re-reads the output and requires (a) the original sections in
the same order with identical headers / relocations, (b) data differences only at the intended offsets (MP lanes or
texture-id words of painted records), (c) only the new texture sections appended. It prints every changed offset
(section-relative and in the decoded DRM) and old / new value.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/material_diag_color.py IN.drm OUT.drm SPEC [SPEC ...] [--dry] [--template PC.drm]
  --dry       only report what would change (writes nothing)
  --template  PC DRM whose texture 255 gives the section header fields when IN has no texture 255
"""
import sys, os, struct, re, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import shader_disasm as SD
from shader_const_fix import lib_parse, split_end


def rgb565(h):
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return ((r * 31 + 127) // 255) << 11 | ((g * 63 + 127) // 255) << 5 | ((b * 31 + 127) // 255)


def flat_texture(c565):
    """PCD9 DXT1 4x4, mips 2 (4x4, 2x2, 1x1 = 3 blocks), flags 3 - texture 255's header with another colour"""
    blocks = struct.pack('<HHI', c565, c565, 0) * 3
    return struct.pack('<4sIIIHHBBH', b'PCD9', 0x31545844, len(blocks), 0, 4, 4, 0, 2, 3) + blocks


def lib_samplers(D, lid):
    """-> {sampler reg: (set of dcl kinds over all entries, CTAB name)} for PS lib lid of D, None if not in D"""
    hit = [s for s in D.sections if s.type == 9 and s.id == lid]
    if not hit: return None
    _h, _tb, _offs, ents, _ds = lib_parse(hit[0].data)
    out = {}
    for o, (_a, _hh, code, _at) in sorted(ents.items()):
        body, _ = split_end(code)
        t = SD.disasm(body)
        names = {int(m.group(2)): m.group(1) for m in re.finditer(r'^//\s+(\S+)\s+s(\d+)\s+\d+\s*$', t, re.M)}
        for m in re.finditer(r'^\s*dcl_(2d|cube|volume)\s+s(\d+)', t, re.M):
            k, reg = m.group(1), int(m.group(2))
            kinds, nm = out.get(reg, (set(), names.get(reg, '?')))
            kinds.add(k); out[reg] = (kinds, nm)
    return out


def plan(D, specs, template=None):
    """-> list of changes (section index, data offset, old bytes, new bytes, note), new texture sections"""
    changes, new_tex = [], []
    tmpl = [s for s in D.sections if s.type == 5 and s.id == 255]
    if not tmpl and template:   # no 255 in the file: header fields of texture 255 of another PC DRM
        tmpl = [s for s in DW.read(open(template, 'rb').read(), 'le').sections if s.type == 5 and s.id == 255]
        if tmpl: print('   texture 255 header taken from %s' % os.path.basename(template))
    for sp in specs:
        p = sp.split(':')
        kind, mid = p[0], int(p[1])
        idx = [i for i, s in enumerate(D.sections) if s.type == 10 and s.id == mid]
        if len(idx) != 1: raise SystemExit('material %d found %d times' % (mid, len(idx)))
        i = idx[0]; s = D.sections[i]; ip = dict(R.parse(s.reloc, 'le').internal)
        if kind == 'tint':
            k = int(p[2]); vals = p[3].split(',')
            n = struct.unpack_from('<I', s.data, 0x58)[0]
            if 0x5C not in ip or k >= n: raise SystemExit('material %d: no PS params block / index %d >= %d' % (mid, k, n))
            base = ip[0x5C] + 16 * k
            old = struct.unpack_from('<4f', s.data, base)
            for lane in range(4):
                if vals[lane] == '=': continue
                nv = struct.pack('<f', float(vals[lane]))
                ob = s.data[base + 4 * lane:base + 4 * lane + 4]
                if ob != nv:
                    changes.append((i, base + 4 * lane, ob, nv, 'material %d PS MP[%d].%s %g -> %g' % (
                        mid, k, 'xyzw'[lane], old[lane], float(vals[lane]))))
        elif kind == 'paint':
            tid, col = int(p[2]), p[3]
            if any(x.type == 5 and x.id == tid for x in D.sections): raise SystemExit('texture %d already in the file' % tid)
            if not tmpl: raise SystemExit('no texture 255 in the file (give --template PC.drm that has it)')
            libs = struct.unpack_from('<4I', s.data, 0x28)
            samp = {pos: lib_samplers(D, libs[pos]) for pos in (0, 1, 2) if libs[pos]}
            if samp.get(2) is None: raise SystemExit('material %d: pass-2 PS lib %d not in the file' % (mid, libs[2]))
            nrec = s.data[0x52]; rec0 = ip.get(0x54)
            painted = 0
            for kk in range(nrec):
                ro = rec0 + 16 * kk
                otid = struct.unpack_from('<I', s.data, ro)[0]; slot = s.data[ro + 13]
                kinds = set(); nm = '?'
                for pos, sm in samp.items():
                    if sm and slot in sm: kinds |= sm[slot][0]; nm = sm[slot][1] if pos == 2 else nm
                used2 = slot in samp[2]
                why = None
                if not used2: why = 'not sampled by the pass-2 PS'
                elif kinds != {'2d'}: why = 'declared %s' % '/'.join(sorted(kinds))
                elif '_Normal_' in nm: why = 'normal-map sampler %s' % nm
                if why:
                    print('   material %d record %d s%d texture %d kept (%s)' % (mid, kk, slot, otid, why)); continue
                changes.append((i, ro, struct.pack('<I', otid), struct.pack('<I', tid),
                                'material %d record %d s%d (%s) texture %d -> %d' % (mid, kk, slot, nm, otid, tid)))
                painted += 1
            if not painted: raise SystemExit('material %d: no record qualifies for painting' % mid)
            t = tmpl[0]
            new_tex.append(DW.Section(5, tid, flat_texture(rgb565(col)), b'', t.flags, t.ver, t.spec, t.pad))
            print('   texture %d = flat #%s (565 %#06x), section header fields of texture %d (flags %d ver %d spec %#x pad %d)' % (
                tid, col, rgb565(col), t.id, t.flags, t.ver, t.spec, t.pad))
        else:
            raise SystemExit('unknown spec %s' % sp)
    return changes, new_tex


def main(argv):
    dry = '--dry' in argv
    argv = [a for a in argv if a != '--dry']
    template = None
    if '--template' in argv: k = argv.index('--template'); template = argv[k + 1]; del argv[k:k + 2]
    if len(argv) < 3: sys.exit(__doc__)
    inp, out, specs = argv[0], argv[1], argv[2:]
    raw = open(inp, 'rb').read()
    dec = DW.cdrm_decode(raw, 'le') if raw[:4] == b'CDRM' else raw
    D = DW.read(raw, 'le')
    if D.write('le') != dec: raise SystemExit('%s: decoded DRM does not round-trip byte-identical - refusing' % inp)
    print('%s: %d sections, decoded %d bytes, round trip ok' % (os.path.basename(inp), len(D.sections), len(dec)))
    changes, new_tex = plan(D, specs, template)
    for i, off, ob, nb, note in changes:
        print('   change sec#%d (type %d id %d) +%#x: %s -> %s  %s' % (
            i, D.sections[i].type, D.sections[i].id, off, ob.hex(), nb.hex(), note))
    if dry: print('dry run: %d changes, %d new textures' % (len(changes), len(new_tex))); return
    n_orig = len(D.sections)
    for i, off, ob, nb, note in changes:
        d = bytearray(D.sections[i].data)
        if bytes(d[off:off + len(ob)]) != ob: raise SystemExit('unexpected old bytes at sec#%d +%#x' % (i, off))
        d[off:off + len(nb)] = nb; D.sections[i].data = bytes(d)
    D.sections.extend(new_tex)
    o = D.write('le')
    data = DW.cdrm_encode(o, 'le') if raw[:4] == b'CDRM' else o
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(data)
    # readback proof against the input
    A = DW.read(raw, 'le'); B = DW.read(open(out, 'rb').read(), 'le')
    want = {(i, off + k) for i, off, ob, nb, _ in changes for k in range(len(ob)) if ob[k] != nb[k]}
    if len(B.sections) != n_orig + len(new_tex): raise SystemExit('readback: section count %d' % len(B.sections))
    other = 0; seen = set()
    for i in range(n_orig):
        x, y = A.sections[i], B.sections[i]
        if (x.type, x.id, x.flags, x.ver, x.spec, x.pad, len(x.data), x.reloc) != (y.type, y.id, y.flags, y.ver, y.spec, y.pad, len(y.data), y.reloc):
            other += 1; print('   READBACK header / reloc differs sec#%d' % i); continue
        if x.data != y.data:
            for k in range(len(x.data)):
                if x.data[k] != y.data[k]:
                    if (i, k) in want: seen.add((i, k))
                    else: other += 1; print('   READBACK unexpected byte sec#%d +%#x' % (i, k))
    for j, t in enumerate(new_tex):
        y = B.sections[n_orig + j]
        if (y.type, y.id, y.data) != (t.type, t.id, t.data): other += 1; print('   READBACK new texture %d differs' % t.id)
    # file-level offsets of the changed bytes in the decoded DRM (output is the input + appended sections)
    decB = DW.cdrm_decode(data, 'le') if data[:4] == b'CDRM' else data
    for i, off, ob, nb, note in changes:
        sec = B.sections[i].data
        hits = [m.start() for m in re.finditer(re.escape(sec[max(0, off - 12):off + 16]), decB)]
        print('   decoded-file offset of sec#%d +%#x: %s' % (i, off, ','.join('%#x' % (h + min(12, off)) for h in hits[:3]) or '?'))
    print('readback: %d original sections, %d new textures, changed bytes %d / intended %d, other differences %d' % (
        n_orig, len(new_tex), len(seen), len(want), other))
    if other or seen != want: raise SystemExit('readback FAILED')
    print('%s  %d bytes  md5 %s' % (out, len(data), hashlib.md5(data).hexdigest()))


if __name__ == '__main__':
    main(sys.argv[1:])
