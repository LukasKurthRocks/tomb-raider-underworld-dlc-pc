"""Symbol inventory of the Xbox 360 dev-kit prototype of 16.08.2007 (TR8, read-only; docs/Befund-Prototyp-2007.md).

The prototype archive carries six executables (decrypted to memory-layout images with tools/xex_extract.py, file
offset = VA - 0x82000000) but only ONE linker map: tr8_Content.map (MSVC "Publics by Value" + "Static symbols", with
the Lib:Object of every symbol). This tool
  * pehdr     - reports per image what symbol information it carries: COFF symbol table pointer / count, the debug
                directory (CodeView RSDS PDB path), timestamp, .pdata function count, RTTI type names, source-path
                strings - so it is clear which build flavour can be named and which only by matching;
  * inventory - parses the map, gives every symbol a size (functions: the exact .pdata length; data: the distance to
                the next symbol of the same section, marked "gap"), a kind and a demangled name, and writes a TSV
                (address, size, size_src, kind, name, raw, obj); prints counts per kind / object file / library;
  * lookup    - names for addresses (nearest map symbol + offset), for reading menus / disassembly.
Only addresses, names and counts are written - no prototype bytes.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/proto_symbols.py pehdr work/proto2007/pe/*/*.pe
  ../bin/pyt -t 300 tools/proto_symbols.py inventory work/proto2007/map/tr8_Content.map \
        work/proto2007/pe/content/tr8_Content.pe work/proto2007/proto_symbols.tsv
  ../bin/pyt -t 120 tools/proto_symbols.py lookup work/proto2007/map/tr8_Content.map 0x82108258 [...]
"""
import sys, os, re, struct, bisect, collections

BASE = 0x82000000


# ---------------------------------------------------------------- small MSVC demangler (names only, no types)
def _ident_list(s, i):
    """parse '@'-separated name fragments until '@@' (end of qualified name); handles '?$tmpl@args@' loosely
    and back-reference digits. Returns (parts, index after '@@')."""
    parts = []
    while i < len(s):
        if s.startswith('@', i):
            return parts, i + 1
        if s[i].isdigit():                 # back-reference to an earlier name fragment
            parts.append('#%s' % s[i])
            i += 1
            continue
        if s.startswith('?$', i):          # template: ?$Name@<args>@  - keep the name, skip the args roughly
            j = s.find('@', i + 2)
            name = s[i + 2:j]
            # args end at the next '@' that is followed by a name start or '@'; approximate: skip to '@@' or
            # to the first '@' after a type code run
            k = j + 1
            depth = 0
            while k < len(s):
                if s.startswith('?$', k):
                    depth += 1
                    k += 2
                    continue
                if s[k] == '@':
                    if depth == 0:
                        break
                    depth -= 1
                k += 1
            parts.append(name + '<>')
            i = k + 1
            continue
        if s.startswith('?', i):           # nested special name (e.g. ?A0x... anonymous namespace)
            j = s.find('@', i + 1)
            frag = s[i + 1:j]
            parts.append('`anon`' if frag.startswith('A0x') else frag)
            i = j + 1
            continue
        j = s.find('@', i)
        if j < 0:
            parts.append(s[i:])
            return parts, len(s)
        parts.append(s[i:j])
        i = j + 1
    return parts, i


SPECIAL = {'0': 'ctor', '1': 'dtor', '2': 'operator new', '3': 'operator delete', '4': 'operator=',
           '_7': 'vftable', '_8': 'vbtable', '_E': 'vector deleting dtor', '_G': 'scalar deleting dtor',
           '_R0': 'RTTI type', '_R1': 'RTTI base', '_R2': 'RTTI base array', '_R3': 'RTTI hierarchy',
           '_R4': 'RTTI locator', '__E': 'dynamic initializer', '__F': 'atexit destructor', 'R': 'operator()',
           '8': 'operator==', '9': 'operator!=', 'A': 'operator[]', 'C': 'operator->', 'D': 'operator*',
           'H': 'operator+', 'G': 'operator-', 'Y': 'operator+=', 'M': 'operator<', 'O': 'operator>',
           'B': 'operator cast'}


def demangle(raw):
    """'?LoseHealth@PlayerHealth@@...' -> 'PlayerHealth::LoseHealth'; strings -> '<str>'; C names unchanged"""
    if raw.startswith('??_C@'):
        return '<str>'
    if not raw.startswith('?'):
        return raw
    s = raw
    if s.startswith('??'):
        # special member: ??0 ctor, ??_7 vftable, ??__E dyn init ...
        for code in sorted(SPECIAL, key=len, reverse=True):
            if s.startswith('??' + code):
                rest = s[2 + len(code):]
                if code in ('__E', '__F'):
                    inner = rest[1:] if rest.startswith('?') else rest
                    parts, _ = _ident_list(inner, 0)
                    return '::'.join(reversed(parts)) + '::<' + SPECIAL[code] + '>'
                if code in ('_R0',):
                    return '<RTTI type ' + rest[:60] + '>'
                parts, _ = _ident_list(rest, 0)
                cls = '::'.join(reversed(parts))
                return cls + '::' + SPECIAL[code]
        return raw
    parts, _ = _ident_list(s, 1)
    return '::'.join(reversed(parts))


def str_text(raw):
    """the start of a string literal as kept in its mangled name ('??_C@_0..@hash@text')"""
    if not raw.startswith('??_C@'):
        return None
    body = raw.split('@', 3)[-1]
    rep = {'?5': ' ', '?2': '\\', '?4': '.', '?3': ':', '?9': '-', '?0': ',', '?1': '/', '?6': '\n', '?7': '\t',
           '?8': "'", '?$AA@': '', '?$CF': '%', '?$CI': '(', '?$CJ': ')', '?$DN': '=', '?$CB': '!', '?$DP': '?',
           '?$CL': '+', '?$CK': '*', '?$DO': '>', '?$DM': '<', '?$FL': '[', '?$FN': ']', '?$CC': '"',
           '?$CD': '#', '?$CG': '&', '?$HL': '{', '?$HN': '}', '?$HM': '|'}
    for k, v in rep.items():
        body = body.replace(k, v)
    return body


# ---------------------------------------------------------------- map
def load_map(path):
    """[(va, raw, obj, is_func, sec, static)] from both map tables"""
    out = []
    static = False
    for line in open(path, 'r', encoding='latin-1'):
        if line.startswith(' Static symbols'):
            static = True
        p = line.split()
        if len(p) < 4 or not re.match(r'^[0-9a-f]{4}:[0-9a-f]{8}$', p[0]):
            continue
        if not re.match(r'^[0-9a-f]{8}$', p[2]):
            continue
        va = int(p[2], 16)
        if va < BASE:
            continue
        flags = p[3:-1]
        out.append((va, p[1], p[-1], 'f' in flags, int(p[0][:4], 16), static))
    out.sort(key=lambda x: (x[0], x[1]))
    return out


def kind_of(raw, is_func, obj):
    if raw.startswith('??_C@'):
        return 'string'
    if raw.startswith('__imp_'):
        return 'import'
    if raw.startswith('??_7'):
        return 'vftable'
    if raw.startswith('??_R'):
        return 'rtti'
    if is_func:
        return 'func'
    if raw.startswith('__real@') or raw.startswith('__xmm@'):
        return 'const'
    return 'data'


def lib_of(obj):
    return obj.split(':')[0] if ':' in obj else '(game)'


# ---------------------------------------------------------------- PE image
def pe_sections(d):
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    nsec = struct.unpack_from('<H', d, pe + 6)[0]
    opt = struct.unpack_from('<H', d, pe + 20)[0]
    out = []
    for i in range(nsec):
        o = pe + 24 + opt + 40 * i
        name = d[o:o + 8].rstrip(b'\0').decode('latin-1')
        vsize, vaddr = struct.unpack_from('<II', d, o + 8)
        ch = struct.unpack_from('<I', d, o + 36)[0]
        out.append((name, BASE + vaddr, vsize, ch))
    return pe, out


def pdata_lengths(d, secs):
    p = [s for s in secs if s[0] == '.pdata']
    out = {}
    if not p:
        return out
    off = p[0][1] - BASE
    for i in range(p[0][2] // 8):
        b, w = struct.unpack_from('>II', d, off + 8 * i)
        if b:
            out[b] = 4 * ((w >> 8) & 0x3fffff)
    return out


def cmd_pehdr(paths):
    print('image\ttimestamp\tcoff_symptr\tcoff_nsyms\tdebug_dir\tpdata_funcs\trtti_names\tsrc_paths\tobj_names')
    for path in paths:
        d = open(path, 'rb').read()
        pe, secs = pe_sections(d)
        ts = struct.unpack_from('<I', d, pe + 8)[0]
        symptr, nsym = struct.unpack_from('<II', d, pe + 12)
        opt = pe + 24
        magic = struct.unpack_from('<H', d, opt)[0]
        ddoff = opt + (96 if magic == 0x10b else 112)
        dbg_rva, dbg_sz = struct.unpack_from('<II', d, ddoff + 8 * 6)
        dbg = []
        for k in range(dbg_sz // 28 if dbg_sz else 0):
            e = dbg_rva + 28 * k                  # memory-layout image: RVA = file offset
            if e + 28 > len(d):
                break
            typ, size, addr, ptr = struct.unpack_from('<IIII', d, e + 12)
            txt = 'type%d' % typ
            if typ == 2 and addr and addr + 24 < len(d) and d[addr:addr + 4] == b'RSDS':
                pdb = d[addr + 24:addr + size].split(b'\0')[0].decode('latin-1')
                txt = 'RSDS ' + pdb
            elif typ == 2 and addr and addr < len(d):
                txt = 'CV ' + d[addr:addr + 4].decode('latin-1', 'replace')
            dbg.append(txt)
        nfun = len(pdata_lengths(d, secs))
        rtti = len(set(re.findall(rb'\.\?A[VU][A-Za-z0-9_@?$]{2,}@@', d)))
        srcp = len(set(re.findall(rb'[A-Za-z]:\\[A-Za-z0-9_\\. ]{3,}\.(?:cpp|h|c)\x00', d, re.I)))
        objn = len(set(re.findall(rb'[A-Za-z0-9_]{2,}\.obj\x00', d)))
        print('%s\t%s\t0x%x\t%d\t%s\t%d\t%d\t%d\t%d' % (
            os.path.relpath(path).replace('\\', '/'), '%08x' % ts, symptr, nsym, '; '.join(dbg) or '-', nfun, rtti,
            srcp, objn))


def cmd_inventory(mapf, pe, out):
    syms = load_map(mapf)
    d = open(pe, 'rb').read()
    _, secs = pe_sections(d)
    plen = pdata_lengths(d, secs)
    # next distinct address per section, for gap sizes
    by_sec = collections.defaultdict(list)
    for s in syms:
        by_sec[s[4]].append(s[0])
    nxt = {}
    for sec, vas in by_sec.items():
        u = sorted(set(vas))
        for a, b in zip(u, u[1:]):
            nxt[(sec, a)] = b - a
    kinds = collections.Counter()
    objs = collections.Counter()
    libs = collections.Counter()
    named_funcs = set()
    rows = 0
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('address\tsize\tsize_src\tkind\tname\traw\tobj\tscope\n')
        for va, raw, obj, fn, sec, static in syms:
            k = kind_of(raw, fn, obj)
            if va in plen and fn:
                size, src = plen[va], 'pdata'
                named_funcs.add(va)
            else:
                size, src = nxt.get((sec, va), 0), 'gap'
            name = demangle(raw)
            if k == 'string':
                t = str_text(raw) or ''
                name = '"' + t[:60].replace('\t', ' ').replace('\n', ' ') + '"'
            f.write('0x%08x\t%d\t%s\t%s\t%s\t%s\t%s\t%s\n' % (va, size, src, k, name, raw, obj,
                                                         'static' if static else 'public'))
            kinds[k] += 1
            libs[lib_of(obj)] += 1
            if lib_of(obj) == '(game)':
                objs[obj] += 1
            rows += 1
    print('map symbols: %d (public %d, static %d) -> %s' % (rows, sum(1 for s in syms if not s[5]),
                                                          sum(1 for s in syms if s[5]), out))
    print('by kind: ' + ', '.join('%s %d' % kv for kv in kinds.most_common()))
    print('pdata functions in the image: %d; with a map name: %d (%.1f %%)' % (
        len(plen), len(named_funcs), 100.0 * len(named_funcs) / max(1, len(plen))))
    fn_game = sum(1 for s in syms if s[3] and lib_of(s[2]) == '(game)')
    print('function symbols from game objects (no lib prefix): %d; from libraries: %d' % (
        fn_game, sum(1 for s in syms if s[3]) - fn_game))
    print('object files: game %d, libraries %d' % (len(objs), len(libs) - 1))
    print('top libraries: ' + ', '.join('%s %d' % kv for kv in libs.most_common(12)))
    print('top game objects: ' + ', '.join('%s %d' % kv for kv in objs.most_common(25)))


def cmd_lookup(mapf, vas):
    syms = load_map(mapf)
    keys = [s[0] for s in syms]
    for v in vas:
        i = bisect.bisect_right(keys, v) - 1
        if i < 0:
            print('0x%08x  -' % v)
            continue
        s = syms[i]
        print('0x%08x  %s+0x%x  [%s]' % (v, demangle(s[1]), v - s[0], s[2]))


def main(a):
    if len(a) < 2:
        sys.exit(__doc__)
    if a[0] == 'pehdr':
        cmd_pehdr(a[1:])
    elif a[0] == 'inventory' and len(a) == 4:
        cmd_inventory(a[1], a[2], a[3])
    elif a[0] == 'lookup':
        cmd_lookup(a[1], [int(x, 16) for x in a[2:]])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
