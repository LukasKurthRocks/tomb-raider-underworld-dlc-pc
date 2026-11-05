"""Make the port's generated pixel shaders valid for Direct3D 9: at most ONE constant register per instruction
(finding 43: the driver rejected 272 of 396 B138 DLC 1 shaders, D3DX9 error X5584 "2 different constant registers
read by instruction"; the Xbox GPU allows two).

Fix per instruction that reads more than one distinct constant register c#: for every constant after the first,
insert `mov rT, c#` (rT = a temp register the shader does not use) before the instruction and read rT instead
(swizzle and source modifier kept). Shader model 3 has r0-r31; a shader without a free temp is left unchanged and
reported. Every changed shader is disassembled (d3dcompiler_47 D3DDisassemble) and reassembled (d3dx9_43
D3DXAssembleShader) - it must assemble without error, otherwise the file is not written.

ShaderLib section (DRM type 9), as read by upstream's tools/native_test/native_extract.py and checked here:
  u8 kind, 3 pad | u32 tableBytes | u32 dataSize (= section length - 4) | u32 slot offset[tableBytes/4]
  (relative to byte 4; 0xffffffff = empty) | entries, tightly packed: u32 0, u32 entrySize, u64 hash, bytecode
  (entrySize - 16 bytes). Rebuilding a library without changes is byte-identical (checked for every library).
Only the port's own libraries are touched (ids 2173, 2720-2783, native_extract.NEW_LIBS).

Usage (from the repository root; IN_DIR / OUT_DIR = mods-style folders, sub folders kept):
  ../bin/pyt -t 1800 tools/shader_const_fix.py IN_DIR OUT_DIR
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import shader_disasm as SD, shader_validate as SV
from shader_libs import NEW_LIBS              # one list for the check (shader_lib_check) and the fix
DCL, DEF, DEFI, DEFB, END, COMMENT, MOV = 0x1F, 0x51, 0x30, 0x2F, 0xFFFF, 0xFFFE, 0x01
# instructions without a destination token: call, callnz, loop, ret, endloop, label, rep, endrep, if, ifc, else,
# endif, break, breakc, breakp (D3DSIO_* 25-30, 38-45, 96)
NO_DST = {0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x60}
CONST = 2


def regtype(t): return ((t >> 28) & 7) | ((t >> 8) & 0x18)
def regnum(t): return t & 0x7FF


def parse(w):
    """-> list of (start index, opcode, tokens) after the version token, up to (excluding) END"""
    out = []; i = 1
    while i < len(w):
        t = w[i]; op = t & 0xFFFF
        if op == END: break
        if op == COMMENT: n = (t >> 16) & 0x7FFF; out.append((i, op, w[i:i + 1 + n])); i += 1 + n; continue
        n = (t >> 24) & 0xF
        out.append((i, op, w[i:i + 1 + n])); i += 1 + n
    return out, i


def split_end(code):
    """-> (bytecode up to and including the END token, trailing bytes of the entry); END found by walking the token
    stream (aligned; comment blocks and def data skipped), not by a byte search"""
    w = struct.unpack('<%dI' % (len(code) // 4), code[:len(code) // 4 * 4])
    _, i = parse(w)
    if i >= len(w) or w[i] & 0xFFFF != END: return code, b''
    return code[:4 * (i + 1)], code[4 * (i + 1):]


def fix_shader(code):
    """-> (new bytes or None if unchanged, number of movs inserted, problem text or '')"""
    w = list(struct.unpack('<%dI' % (len(code) // 4), code[:len(code) // 4 * 4]))
    ins, end = parse(w)
    used = set()
    for _, op, toks in ins:
        if op in (COMMENT,): continue
        for t in toks[1:]:
            if t & 0x80000000 and regtype(t) == 0: used.add(regnum(t))
    free = [r for r in range(32) if r not in used]
    out = [w[0]]; added = 0
    for _, op, toks in ins:
        if op in (COMMENT, DCL, DEF, DEFI, DEFB):
            out += toks; continue
        params = list(toks[1:])
        # source tokens: everything after the destination; relative addressing (bit 13) adds one token
        first_src = 0 if op in NO_DST else 1
        srcs = []; k = first_src
        while k < len(params):
            srcs.append(k)
            k += 2 if params[k] & (1 << 13) else 1
        consts = []
        for k in srcs:
            t = params[k]
            if regtype(t) == CONST and not (t & (1 << 13)) and regnum(t) not in consts: consts.append(regnum(t))
        if len(consts) <= 1:
            out += toks; continue
        need = consts[1:]
        if len(free) < len(need): return None, 0, 'no free temp register'
        tmap = {}
        for j, c in enumerate(need):      # the temps are read right away: the same free temps serve every instruction
            r = free[j]; tmap[c] = r
            out += [0x02000000 | MOV, 0x800F0000 | r, 0xA0E40000 | c]      # mov rR, cC (all components)
            added += 1
        for k in srcs:
            t = params[k]
            if regtype(t) == CONST and not (t & (1 << 13)) and regnum(t) in tmap:
                params[k] = (t & ~((7 << 28) | (3 << 11) | 0x7FF)) | tmap[regnum(t)]     # register type 0 = temp
        out += [toks[0]] + params
    if not added: return None, 0, ''
    out += w[end:]
    return struct.pack('<%dI' % len(out), *out), added, ''


def lib_parse(d):
    """-> head, tableBytes, slot offsets, entries {offset: (u32 a, hash, code, offset)} - slots may share an entry
    (e.g. lib 2776 of dlc_caverns_hall: 8 slots, 2 entries)"""
    tb, ds = struct.unpack_from('<II', d, 4)
    offs = list(struct.unpack_from('<%dI' % (tb // 4), d, 12))
    ents = {}
    for o in offs:
        if o == 0xffffffff or o in ents: continue
        a, size, h = struct.unpack_from('<IIQ', d, 4 + o)
        ents[o] = (a, h, d[4 + o + 16:4 + o + size], o)
    return d[:4], tb, offs, ents, ds


def lib_build(head, tb, offs, ents, order):
    body = bytearray(); moved = {}
    pos = 12 + tb
    for o in order:
        a, h, code, _ = ents[o]
        moved[o] = pos - 4
        e = struct.pack('<IIQ', a, 16 + len(code), h) + code
        body += e; pos += len(e)
    new_offs = [o if o == 0xffffffff else moved[o] for o in offs]
    d = bytearray(head) + struct.pack('<II', tb, 8 + tb + len(body)) + struct.pack('<%dI' % len(new_offs), *new_offs) + body
    return bytes(d)


def fix_lib(d, st, sid, fname):
    head, tb, offs, ents, ds = lib_parse(d)
    order = sorted(ents)
    if lib_build(head, tb, offs, ents, order) != d: raise SystemExit('%s lib %d: rebuild is not byte-identical' % (fname, sid))
    changed = False
    for k in order:
        a, h, code, at = ents[k]
        if code[2:4] != b'\xff\xff': continue                     # pixel shaders only (vs_3_0 = 0xfffe)
        body, tail = split_end(code)
        new, n, prob = fix_shader(body)
        if prob: st['shaders not fixable (%s)' % prob] += 1; continue
        if new is None: st['shaders already valid'] += 1; continue
        ok, msg = SV.assemble(SD.disasm(new))
        if not ok: st['FIX FAILED validation'] += 1; print('  %s lib %d slot %d: %s' % (fname, sid, k, msg.strip()[:200])); continue
        ents[k] = (a, h, new + tail, at); changed = True
        st['shaders fixed'] += 1; st['movs inserted'] += n
    return lib_build(head, tb, offs, ents, order) if changed else None


def main(argv):
    src, dst = argv[0], argv[1]
    st = collections.Counter(); files = 0
    for dp, dn, fn in os.walk(src):
        for f in sorted(fn):
            if not f.lower().endswith('.drm'): continue
            p = os.path.join(dp, f); rel = os.path.relpath(p, src)
            raw = open(p, 'rb').read(); D = DW.read(raw, 'le'); changed = False
            for s in D.sections:
                if s.type != 9 or s.id not in NEW_LIBS: continue
                st['libraries'] += 1
                nd = fix_lib(s.data, st, s.id, rel)
                if nd is not None: s.data = nd; changed = True
            if not changed: continue
            out = D.write('le')
            if raw[:4] in (b'CDRM', b'MRDC'): out = DW.cdrm_encode(out, 'le')
            q = os.path.join(dst, rel); os.makedirs(os.path.dirname(q), exist_ok=True)
            open(q, 'wb').write(out); files += 1
    print('files written: %d; %s' % (files, dict(st)))


if __name__ == '__main__':
    main(sys.argv[1:])
