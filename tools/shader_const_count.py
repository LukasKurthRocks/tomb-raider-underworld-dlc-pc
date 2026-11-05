"""Read-only count of the pixel-shader form that Direct3D 9 rejects with X5584 "2 different constant registers read by
instruction" (finding 43; the form tools/shader_const_fix.py removes) in every shader library of a mods-style tree,
any library id (2026-11-05: also the upstream B270 kit, whose own libraries have other ids than ours).

The shader view is the one of shader_const_fix.py (lib_parse: slot table and entries, split_end: token walk to the END
token, parse: instruction tokens), copied here because shader_const_fix.py cannot be imported since the upstream merge
(it imports NEW_LIBS from tools/native_test/native_extract.py, which upstream's v3 of that file no longer defines);
an instruction counts when its source tokens name two or more DISTINCT constant registers c# (no relative addressing).
Shaders whose md5 is a PC game shader (tools/native_test/pc_shader_md5.txt) are counted apart.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/shader_const_count.py MODS_DIR [--list N] [--libs a,b-c]
  --list N  print the first N affected shaders (file, library, slot, instruction count)
Output: per file the affected shaders / instructions, per library id, and unique totals (by shader md5).
Exit code 0 = no affected port shader, 1 = at least one.
"""
import sys, os, struct, hashlib, collections, types
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'native_test'))
import native_extract as NE

# --- copied from tools/shader_const_fix.py (same constants and token walk)
DCL, DEF, DEFI, DEFB, END, COMMENT = 0x1F, 0x51, 0x30, 0x2F, 0xFFFF, 0xFFFE
NO_DST = {0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x60}
CONST = 2


def regtype(t): return ((t >> 28) & 7) | ((t >> 8) & 0x18)
def regnum(t): return t & 0x7FF


def parse(w):
    out = []; i = 1
    while i < len(w):
        t = w[i]; op = t & 0xFFFF
        if op == END: break
        if op == COMMENT: n = (t >> 16) & 0x7FFF; out.append((i, op, w[i:i + 1 + n])); i += 1 + n; continue
        n = (t >> 24) & 0xF
        out.append((i, op, w[i:i + 1 + n])); i += 1 + n
    return out, i


def split_end(code):
    w = struct.unpack('<%dI' % (len(code) // 4), code[:len(code) // 4 * 4])
    _, i = parse(w)
    if i >= len(w) or w[i] & 0xFFFF != END: return code, b''
    return code[:4 * (i + 1)], code[4 * (i + 1):]


def lib_parse(d):
    tb, ds = struct.unpack_from('<II', d, 4)
    offs = list(struct.unpack_from('<%dI' % (tb // 4), d, 12))
    ents = {}
    for o in offs:
        if o == 0xffffffff or o in ents: continue
        a, size, h = struct.unpack_from('<IIQ', d, 4 + o)
        ents[o] = (a, h, d[4 + o + 16:4 + o + size], o)
    return d[:4], tb, offs, ents, ds


SCF = types.SimpleNamespace(DCL=DCL, DEF=DEF, DEFI=DEFI, DEFB=DEFB, COMMENT=COMMENT, NO_DST=NO_DST, CONST=CONST,
                            regtype=regtype, regnum=regnum, parse=parse, split_end=split_end, lib_parse=lib_parse)


def two_const_instrs(body):
    w = list(struct.unpack('<%dI' % (len(body) // 4), body[:len(body) // 4 * 4]))
    ins, _ = SCF.parse(w); n = 0
    for _, op, toks in ins:
        if op in (SCF.COMMENT, SCF.DCL, SCF.DEF, SCF.DEFI, SCF.DEFB): continue
        params = list(toks[1:]); k = 0 if op in SCF.NO_DST else 1; consts = set()
        while k < len(params):
            t = params[k]
            if SCF.regtype(t) == SCF.CONST and not (t & (1 << 13)): consts.add(SCF.regnum(t))
            k += 2 if t & (1 << 13) else 1
        if len(consts) > 1: n += 1
    return n


def main(argv):
    root = argv[0]
    lst = int(argv[argv.index('--list') + 1]) if '--list' in argv else 0
    pcmd5 = set(l.strip() for l in open(os.path.join(HERE, 'native_test', 'pc_shader_md5.txt')) if l.strip())
    per_file = collections.Counter(); per_file_i = collections.Counter(); per_lib = collections.Counter()
    uniq = {}; tot = collections.Counter(); shown = 0
    for dp, dn, fn in os.walk(root):
        for f in sorted(fn):
            if not f.lower().endswith('.drm'): continue
            p = os.path.join(dp, f); rel = os.path.relpath(p, root).replace(os.sep, '/')
            raw = NE.cdrm_decode(open(p, 'rb').read())
            for typ, sid, data in NE.sections(raw):
                if typ != 9 or len(data) < 12: continue
                try: head, tb, offs, ents, ds = SCF.lib_parse(data)
                except Exception: tot['libraries not parsed'] += 1; continue
                tot['libraries'] += 1
                for o, (a, h, code, at) in ents.items():
                    if code[2:4] != b'\xff\xff': continue
                    body, tail = SCF.split_end(code)
                    md = hashlib.md5(body).hexdigest()
                    tot['pixel shaders (entries)'] += 1
                    if md not in uniq: uniq[md] = (two_const_instrs(body), md in pcmd5)
                    n, ispc = uniq[md]
                    if not n: continue
                    key = 'pc' if ispc else 'port'
                    tot['affected entries (%s)' % key] += 1
                    if key == 'port':
                        per_file[rel] += 1; per_file_i[rel] += n; per_lib[sid] += 1
                        if shown < lst: print('  %s lib %d entry +%#x: %d instructions' % (rel, sid, o, n)); shown += 1
    up = [v for v in uniq.values()]
    print('tree %s: %s' % (root, ', '.join('%s %d' % kv for kv in sorted(tot.items()))))
    print('unique pixel shaders %d; with two different constant registers in one instruction: port %d (instructions %d), '
          'PC game shaders %d' % (len(up), sum(1 for n, pc in up if n and not pc), sum(n for n, pc in up if n and not pc),
                                   sum(1 for n, pc in up if n and pc)))
    print('files with affected port shaders: %d' % len(per_file))
    for rel in sorted(per_file, key=lambda r: (-per_file[r], r)):
        print('  %4d shaders %5d instr  %s' % (per_file[rel], per_file_i[rel], rel))
    print('libraries (id: affected entries over all files): ' + ', '.join('%d: %d' % kv for kv in sorted(per_lib.items())))
    sys.exit(1 if per_file else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
