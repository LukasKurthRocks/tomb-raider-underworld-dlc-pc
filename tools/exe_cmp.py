"""Compare two builds of tru.exe section by section and explain every changed code region (read-only; upstream B270
exe vs. its Steamless base, docs Befund-Exe-Vergleich-0511.md).

Both files are only read as bytes (never loaded or run). Steps:
  1. PE header fields and section tables of OLD and NEW; sections only in NEW are listed with size / flags.
  2. Common sections are compared byte by byte by VA (bytes past the raw size count as zero); differing bytes closer
     than --gap are merged into regions.
  3. Every region in an executable section is disassembled (capstone, x86-32) in OLD and NEW from the function start
     before it (int3 padding heuristic), with branch / call targets classified by section.
  4. New executable sections are disassembled by recursive descent from every entry that patched code or patched
     data (vtable / function-pointer / jump-table dwords) points to; call targets inside new sections become routines
     of their own. Per routine: calls into the old code, exits back into the old code, absolute data references (with
     the dword / float stored there), immediates, absolute writes. Unreached non-zero bytes are listed as data.
  5. Mapping: the PC function around each region and every PC callee of a new routine -> Xbox retail function
     (work/xmap/xbox_pc_map.tsv) -> title-update function (work/tu_funcdiff/pairs.tsv). For new routines the TU
     function is searched by callee sets in the TU image (functions whose calls contain the most mapped callees).
     Plugin sites (tru+0x... / const DWORD k... in src/asi, TruGuard skipped like tools/kit_inspect.py) inside the
     patched PC function and plugin TU addresses (0x82xxxxxx) inside the TU function are listed.
  6. --ref EXE (e.g. our installed tru.exe): per region, whether REF has the OLD bytes there (else REF is patched too).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/exe_cmp.py OLD.exe NEW.exe OUT_DIR [--gap 8] [--ref REF.exe] [--xmap TSV] [--pairs TSV]
      [--tu TU_IMAGE.bin] [--asi DIR]
  defaults: --xmap work/xmap/xbox_pc_map.tsv --pairs work/tu_funcdiff/pairs.tsv
            --tu work/xenia_dump/dlc2_shadow_off_image.bin --asi src/asi
  OUT_DIR: summary.txt (= console), sections.tsv, regions.tsv, regions_dis.txt, newcode.txt, routines.tsv
Only addresses, instruction text and counts are written (no blocks of game bytes beyond single instructions).
"""
import sys, os, re, struct, bisect, collections
import numpy as np
import capstone
from capstone import x86 as CX
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
SKIP_PLUGINS = ('TruGuard',)          # belongs to a colleague: never read
IMAGE_SCN_EXEC = 0x20000000


# ---------------------------------------------------------------- PE
class PE:
    def __init__(self, path):
        self.path = path
        self.b = b = open(path, 'rb').read()
        pe = struct.unpack_from('<I', b, 0x3c)[0]
        self.pe = pe
        nsec = struct.unpack_from('<H', b, pe + 6)[0]
        opt = struct.unpack_from('<H', b, pe + 20)[0]
        self.base = struct.unpack_from('<I', b, pe + 24 + 28)[0]
        self.secs = []
        for i in range(nsec):
            o = pe + 24 + opt + 40 * i
            name = b[o:o + 8].rstrip(b'\0').decode('latin1')
            vsz, va, rsz, raw = struct.unpack_from('<IIII', b, o + 8)
            ch = struct.unpack_from('<I', b, o + 36)[0]
            self.secs.append(dict(name=name, va=self.base + va, vsz=vsz, raw=raw, rsz=rsz, ch=ch))
        f = pe + 24
        self.hdr = collections.OrderedDict([
            ('FileHeader.Characteristics', struct.unpack_from('<H', b, pe + 22)[0]),
            ('NumberOfSections', nsec),
            ('SizeOfCode', struct.unpack_from('<I', b, f + 4)[0]),
            ('SizeOfInitializedData', struct.unpack_from('<I', b, f + 8)[0]),
            ('AddressOfEntryPoint', struct.unpack_from('<I', b, f + 16)[0]),
            ('ImageBase', self.base),
            ('SectionAlignment', struct.unpack_from('<I', b, f + 32)[0]),
            ('FileAlignment', struct.unpack_from('<I', b, f + 36)[0]),
            ('SizeOfImage', struct.unpack_from('<I', b, f + 56)[0]),
            ('SizeOfHeaders', struct.unpack_from('<I', b, f + 60)[0]),
            ('CheckSum', struct.unpack_from('<I', b, f + 64)[0]),
            ('DllCharacteristics', struct.unpack_from('<H', b, f + 70)[0]),
        ])
        ndir = struct.unpack_from('<I', b, f + 92)[0]
        for k in range(min(ndir, 16)):
            self.hdr['DataDirectory[%d]' % k] = '0x%x/0x%x' % struct.unpack_from('<II', b, f + 96 + 8 * k)

    def sec(self, va):
        for s in self.secs:
            if s['va'] <= va < s['va'] + max(s['vsz'], s['rsz']):
                return s
        return None

    def secname(self, va):
        s = self.sec(va)
        return s['name'] if s else ('header' if self.base <= va < self.base + 0x1000 else '-')

    def is_exec(self, va):
        s = self.sec(va)
        return bool(s and s['ch'] & IMAGE_SCN_EXEC)

    def read(self, va, n):
        s = self.sec(va)
        if not s:
            return b'\0' * n
        o = va - s['va']
        out = self.b[s['raw'] + o:s['raw'] + min(o + n, s['rsz'])] if o < s['rsz'] else b''
        return out + b'\0' * (n - len(out))

    def sec_array(self, s, n):
        return np.frombuffer(self.read(s['va'], n), dtype=np.uint8)

    def dword(self, va):
        return struct.unpack('<I', self.read(va, 4))[0]


def fl(v):
    f = struct.unpack('<f', struct.pack('<I', v & 0xffffffff))[0]
    if v == 0:
        return '0'
    if f != f or abs(f) > 1e9 or (abs(f) < 1e-6):
        return ''
    return '%.6g' % f


# ---------------------------------------------------------------- disassembly helpers
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
MD.detail = True


def dis_one(pe, va):
    code = pe.read(va, 16)
    for ins in MD.disasm(code, va):
        return ins
    return None


def func_start(pe, va, maxback=0x4000):
    """first byte after a run of >= 2 int3 before va (same heuristic as tools/pe_dis.py)"""
    lo = max(pe.sec(va)['va'], va - maxback)
    blob = pe.read(lo, va - lo)
    i = len(blob)
    while i > 2:
        if blob[i - 1] == 0xcc and blob[i - 2] == 0xcc:
            return lo + i
        i -= 1
    return lo


def ins_refs(ins):
    """-> (branch_target or None, [abs mem (disp, access)], [imm values])"""
    br, mems, imms = None, [], []
    for op in ins.operands:
        if op.type == CX.X86_OP_IMM:
            if ins.group(capstone.CS_GRP_JUMP) or ins.group(capstone.CS_GRP_CALL):
                br = op.imm & 0xffffffff
            else:
                imms.append(op.imm & 0xffffffff)
        elif op.type == CX.X86_OP_MEM:
            if op.mem.base == 0 and op.mem.disp:
                mems.append((op.mem.disp & 0xffffffff, op.access, op.mem.index != 0))
    return br, mems, imms


def fmt(ins):
    return '%08x  %-22s %s %s' % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str)


def lin_dis(pe, lo, hi):
    out, a = [], lo
    while a < hi:
        ins = dis_one(pe, a)
        if ins is None:
            out.append(None); a += 1; continue
        out.append(ins); a += ins.size
    return out


# ---------------------------------------------------------------- mapping tables
class Maps:
    def __init__(self, xmap, pairs, tu_img, asi, log):
        self.pc = []                         # (pc_start, pc_size, retail, tier, method)
        if os.path.exists(xmap):
            for ln in open(xmap, encoding='utf-8').read().splitlines()[1:]:
                c = ln.split('\t')
                self.pc.append((int(c[1], 16), int(c[6]), int(c[0], 16), c[8], c[2]))
        self.pc.sort()
        self.pcs = [r[0] for r in self.pc]
        self.r2t, self.t2r, self.tinfo = {}, {}, {}
        if os.path.exists(pairs):
            for ln in open(pairs, encoding='utf-8').read().splitlines()[1:]:
                c = ln.split('\t')
                t = int(c[0], 16) if c[0].startswith('0x') else None
                r = int(c[1], 16) if c[1].startswith('0x') else None
                if t is not None:
                    self.tinfo[t] = (c[2], c[8], int(c[6]) if c[6].isdigit() else 0)
                if t is not None and r is not None:
                    self.r2t[r] = t; self.t2r[t] = r
        log('maps: %d PC<->retail pairs, %d retail->TU pairs, %d TU functions with info' % (
            len(self.pc), len(self.r2t), len(self.tinfo)))
        self.tu = None
        if tu_img and os.path.exists(tu_img):
            import xbox_pc_funcmap as XM
            self.tu = XM.Xbox(tu_img)
            self.tstarts = self.tu.starts
            log('TU image: %d functions' % len(self.tu.funcs))
        # plugin sites
        self.sites = collections.defaultdict(set)
        self.tusites = collections.defaultdict(set)
        for d in sorted(os.listdir(asi)):
            if d in SKIP_PLUGINS or d == 'third_party' or not os.path.isdir(os.path.join(asi, d)):
                continue
            for fn in sorted(os.listdir(os.path.join(asi, d))):
                if not (fn.endswith('.cpp') or fn.endswith('.h') or fn == 'README.md'):
                    continue
                t = open(os.path.join(asi, d, fn), encoding='utf-8', errors='replace').read()
                for m in re.finditer(r'const\s+(?:DWORD|uintptr_t|uint32_t)\s+(k\w+)\s*=\s*0x0*([4-9a-f][0-9a-f]{5})\b', t, re.I):
                    self.sites[int(m.group(2), 16)].add('%s:%s' % (d, m.group(1)))
                for m in re.finditer(r'tru\+0x([0-9a-f]{4,6})\b', t, re.I):
                    self.sites[0x400000 + int(m.group(1), 16)].add('%s:tru+0x%s' % (d, m.group(1).lower()))
                for m in re.finditer(r'\b0x(8[23][0-9a-f]{6})\b', t, re.I):
                    self.tusites[int(m.group(1), 16)].add(d)
        self.sitekeys = sorted(self.sites)
        log('plugin sites (TruGuard skipped): %d PC addresses, %d TU addresses' % (len(self.sites), len(self.tusites)))

    def pc_func(self, va):
        i = bisect.bisect_right(self.pcs, va) - 1
        if i >= 0:
            s, n, r, tier, meth = self.pc[i]
            if s <= va < s + max(n, 1):
                return self.pc[i]
        return None

    def tu_func(self, a):
        if not self.tu:
            return None
        i = bisect.bisect_right(self.tstarts, a) - 1
        if i >= 0 and a < self.tstarts[i] + self.tu.size[self.tstarts[i]]:
            return self.tstarts[i]
        return None

    def chain(self, va):
        """PC address -> 'pc_func retail tu (status/class) tier'"""
        f = self.pc_func(va)
        if not f:
            return None
        s, n, r, tier, meth = f
        t = self.r2t.get(r)
        ti = self.tinfo.get(t, ('', '', 0)) if t else ('', '', 0)
        return dict(pc=s, pc_size=n, retail=r, tu=t, tier=tier, method=meth, status=ti[0], cls=ti[1])

    def sites_in(self, lo, hi):
        i = bisect.bisect_left(self.sitekeys, lo)
        out = []
        while i < len(self.sitekeys) and self.sitekeys[i] < hi:
            out.append((self.sitekeys[i], sorted(self.sites[self.sitekeys[i]]))); i += 1
        return out

    def plugins_on_tu(self, t):
        if t is None or not self.tu:
            return []
        hi = t + self.tu.size.get(t, 4)
        out = set()
        for a, ps in self.tusites.items():
            if t <= a < hi:
                out |= ps
        return sorted(out)

    def tu_by_callees(self, tu_callees, top=3):
        if not self.tu or not tu_callees:
            return []
        S = set(tu_callees)
        cand = collections.Counter()
        for c in S:
            for f in self.tu.callers.get(c, ()):
                cand[f] += 1
        out = []
        for f, k in cand.most_common():
            if k < min(2, len(S)):
                break
            out.append((f, k, len(set(self.tu.calls.get(f, [])))))
        out.sort(key=lambda x: (-x[1], x[2]))
        return out[:top]


# ---------------------------------------------------------------- main
def main(argv):
    def opt(key, default=None):
        if key in argv:
            k = argv.index(key); v = argv[k + 1]; del argv[k:k + 2]; return v
        return default
    gap = int(opt('--gap', '8'))
    ref = opt('--ref')
    xmap = opt('--xmap', os.path.join(HERE, '..', 'work', 'xmap', 'xbox_pc_map.tsv'))
    pairs = opt('--pairs', os.path.join(HERE, '..', 'work', 'tu_funcdiff', 'pairs.tsv'))
    tu_img = opt('--tu', os.path.join(HERE, '..', 'work', 'xenia_dump', 'dlc2_shadow_off_image.bin'))
    asi = opt('--asi', os.path.join(HERE, '..', 'src', 'asi'))
    if len(argv) != 3:
        sys.exit(__doc__)
    O, N = PE(argv[0]), PE(argv[1])
    R = PE(ref) if ref else None
    out = argv[2]
    os.makedirs(out, exist_ok=True)
    lines = []

    def log(s=''):
        print(s, flush=True); lines.append(s)

    import hashlib
    for tag, p in (('OLD', O), ('NEW', N)) + ((('REF', R),) if R else ()):
        log('%s %s: %d bytes, md5 %s, image base 0x%x' % (tag, os.path.basename(p.path), len(p.b),
                                                        hashlib.md5(p.b).hexdigest(), p.base))

    # 1. header + sections
    log('\n== header fields that differ')
    for k in O.hdr:
        if O.hdr[k] != N.hdr.get(k):
            a, b = O.hdr[k], N.hdr.get(k)
            log('  %-28s OLD %s  NEW %s' % (k, ('0x%x' % a) if isinstance(a, int) else a, ('0x%x' % b) if isinstance(b, int) else b))
    log('\n== sections')
    oset = {s['name']: s for s in O.secs}
    with open(os.path.join(out, 'sections.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('exe\tname\tva\tvsize\traw\trsize\tchars\n')
        for tag, p in (('OLD', O), ('NEW', N)):
            for s in p.secs:
                f.write('%s\t%s\t0x%x\t0x%x\t0x%x\t0x%x\t0x%08x\n' % (tag, s['name'], s['va'], s['vsz'], s['raw'], s['rsz'], s['ch']))
    for s in N.secs:
        o = oset.get(s['name'])
        if not o:
            nz = int(np.count_nonzero(N.sec_array(s, s['vsz'])))
            log('  NEW  %-8s va 0x%06x vsize 0x%05x (%d) raw 0x%06x rsize 0x%05x chars 0x%08x %s, %d non-zero bytes' % (
                s['name'], s['va'], s['vsz'], s['vsz'], s['raw'], s['rsz'], s['ch'],
                'exec' if s['ch'] & IMAGE_SCN_EXEC else 'data', nz))
        else:
            diff = [k for k in ('va', 'vsz', 'rsz', 'ch') if o[k] != s[k]]
            log('  same %-8s va 0x%06x vsize 0x%05x chars 0x%08x%s' % (
                s['name'], s['va'], s['vsz'], s['ch'],
                ('  CHANGED ' + ', '.join('%s 0x%x -> 0x%x' % (k, o[k], s[k]) for k in diff)) if diff else ''))

    # 2. regions
    regions = []
    for s in N.secs:
        o = oset.get(s['name'])
        if not o or o['va'] != s['va']:
            continue
        n = max(o['vsz'], s['vsz'])
        a, b = O.sec_array(o, n), N.sec_array(s, n)
        idx = np.flatnonzero(a != b)
        if not len(idx):
            continue
        st = pv = int(idx[0])
        for i in idx[1:]:
            i = int(i)
            if i - pv > gap:
                regions.append((s['name'], s['va'] + st, s['va'] + pv + 1, bool(s['ch'] & IMAGE_SCN_EXEC))); st = i
            pv = i
        regions.append((s['name'], s['va'] + st, s['va'] + pv + 1, bool(s['ch'] & IMAGE_SCN_EXEC)))
    cnt = collections.Counter(r[0] for r in regions)
    nb = collections.Counter()
    for r in regions:
        nb[r[0]] += r[2] - r[1]
    log('\n== changed regions (gap %d): %d; per section: %s' % (gap, len(regions), ', '.join(
        '%s %d (%d B)' % (k, cnt[k], nb[k]) for k in sorted(cnt))))

    M = Maps(xmap, pairs, tu_img, asi, log)
    newsec = [s for s in N.secs if s['name'] not in oset]
    newexec = [s for s in newsec if s['ch'] & IMAGE_SCN_EXEC]

    # code caves: changed regions of executable sections whose OLD bytes were all zero (padding at a section end)
    caves = [(lo, hi) for sn, lo, hi, ex in regions if ex and not any(O.read(lo, hi - lo))]
    cave_set = set(caves)
    log('code caves in old executable sections (OLD bytes all zero): %d, %d bytes: %s' % (
        len(caves), sum(h - l for l, h in caves), ', '.join('%s 0x%x..0x%x' % (N.secname(l), l, h) for l, h in caves)))

    def in_cave(va):
        # whole tail from the first cave to the section end counts (gaps between caves are zero padding)
        for l, h in caves:
            if l <= va < h:
                return True
        return False

    def in_new(va):
        return any(s['va'] <= va < s['va'] + s['vsz'] for s in newsec) or in_cave(va)

    def in_newexec(va):
        return any(s['va'] <= va < s['va'] + s['vsz'] for s in newexec) or in_cave(va)

    def cls(va):
        return N.secname(va) + ('(cave)' if in_cave(va) else '')

    # 3. disassemble regions
    entries = collections.OrderedDict()           # new-section entry -> [source descriptions]
    imm_cand = collections.OrderedDict()          # immediates into new code areas: code entry or data table
    dis = open(os.path.join(out, 'regions_dis.txt'), 'w', encoding='utf-8', newline='\n')
    rows = []
    for k, (sn, lo, hi, ex) in enumerate(regions):
        row = dict(i=k + 1, sec=sn, lo=lo, hi=hi, n=hi - lo, kind='', targets=[], fs=None, chain=None, sites=[],
                   ref='')
        if R:
            ob, rb = O.read(lo, hi - lo), R.read(lo, hi - lo)
            nbv = N.read(lo, hi - lo)
            row['ref'] = 'old' if rb == ob else ('new' if rb == nbv else 'other')
        dis.write('\n#%d %s 0x%06x..0x%06x (%d B, tru+0x%x)%s\n' % (k + 1, sn, lo, hi, hi - lo, lo - 0x400000,
                                                                   ('  REF=' + row['ref']) if R else ''))
        if ex and (lo, hi) in cave_set:
            dis.write('  code cave (OLD bytes all zero): new code, see newcode.txt\n')
            row['kind'] = 'cave'
        elif ex:
            fs = func_start(O, lo)
            row['fs'] = fs
            c = M.chain(lo)
            row['chain'] = c
            fe = (c['pc'] + c['pc_size']) if c else hi + 0x40
            row['sites'] = [x for x in M.sites_in(min(fs, lo - 16), max(fe, hi + 16))]
            oi = [i for i in lin_dis(O, fs, hi + 16) if i is not None and i.address + i.size > lo - 6 and i.address < hi + 6]
            ni = [i for i in lin_dis(N, fs, hi + 16) if i is not None and i.address + i.size > lo - 6 and i.address < hi + 6]
            dis.write('  function start (int3 heuristic) 0x%06x' % fs)
            if c:
                dis.write('; map: PC 0x%06x size %d -> retail 0x%08x -> TU %s %s/%s (%s, %s)' % (
                    c['pc'], c['pc_size'], c['retail'], ('0x%08x' % c['tu']) if c['tu'] else '-', c['status'], c['cls'],
                    c['tier'], c['method']))
            dis.write('\n  OLD:\n')
            for i in oi:
                dis.write('    ' + fmt(i) + '\n')
            dis.write('  NEW:\n')
            kinds = set()
            for i in ni:
                br, mems, imms = ins_refs(i)
                note = ''
                if br is not None:
                    note = '  -> %s' % cls(br)
                    if in_newexec(br):
                        entries.setdefault(br, []).append('#%d %s @0x%06x' % (k + 1, i.mnemonic, i.address))
                        kinds.add(i.mnemonic + '->new')
                    row['targets'].append('%s 0x%x (%s)' % (i.mnemonic, br, cls(br)))
                for d, acc, idx in mems:
                    if in_new(d):
                        note += '  [%s 0x%x]' % (cls(d), d)
                for v in imms:
                    if in_new(v):
                        note += '  imm->%s 0x%x' % (cls(v), v)
                        if in_newexec(v):
                            imm_cand.setdefault(v, []).append('#%d imm @0x%06x' % (k + 1, i.address))
                dis.write('    ' + fmt(i) + note + '\n')
            # jump-table / pointer dwords inside code (e.g. a switch table entry redirected into a new section)
            a = (lo - 3) & ~3
            while a < hi:
                vo, vn = O.dword(a), N.dword(a)
                if vo != vn and in_newexec(vn) and O.is_exec(vo):
                    dis.write('    dword 0x%06x: 0x%08x -> 0x%08x (%s, table entry)\n' % (a, vo, vn, cls(vn)))
                    entries.setdefault(vn, []).append('#%d table dword @0x%06x' % (k + 1, a))
                    kinds.add('table->new')
                    row['targets'].append('dword 0x%x: 0x%x->0x%x' % (a, vo, vn))
                a += 4
            row['kind'] = ','.join(sorted(kinds)) or 'inline'
        else:
            # data region: dwords pointing into new exec sections / old exec
            a = lo & ~3
            while a < hi:
                vo, vn = O.dword(a), N.dword(a)
                if vo != vn:
                    dis.write('  0x%06x: 0x%08x -> 0x%08x  (%s -> %s)%s\n' % (a, vo, vn, O.secname(vo), cls(vn),
                              ('  float %s -> %s' % (fl(vo), fl(vn))) if fl(vn) and not N.sec(vn) else ''))
                    if in_newexec(vn):
                        entries.setdefault(vn, []).append('#%d dword @0x%06x (%s)' % (k + 1, a, sn))
                    row['targets'].append('0x%x: 0x%x->0x%x' % (a, vo, vn))
                a += 4
            row['kind'] = 'data'
        rows.append(row)
    dis.close()

    # 4. new code, recursive descent
    routines = collections.OrderedDict()
    owner = {}
    work = list(entries)
    for e in work:
        routines.setdefault(e, dict(src=entries[e], ins=[], calls_new=[], calls_old=[], exits=[], mems=[], imms=[],
                                    ind=[]))

    def plausible_code(a, limit=0x1000):
        """linear decode from a until ret / jmp; reject data-looking bytes (00 00 = add [eax],al, invalid)"""
        e, n = a, 0
        while e < a + limit and in_newexec(e):
            ins = dis_one(N, e)
            if ins is None or ins.bytes[:2] == b'\0\0' or ins.mnemonic in ('int3', 'hlt', 'in', 'out', 'insb', 'insd',
                                                                            'outsb', 'outsd', 'arpl', 'bound', 'into'):
                return False
            n += 1
            if ins.mnemonic in ('ret', 'jmp'):
                return n >= 2
            e += ins.size
        return False

    def descend(q):
        while q:
            descend_one(q)

    def descend_one(q):
        e = q.pop(0)
        r = routines[e]
        if r['ins']:
            return
        todo, seen = [e], set()
        while todo:
            a = todo.pop()
            while a not in seen and in_newexec(a):
                if a in owner and owner[a] != e:
                    break
                ins = dis_one(N, a)
                if ins is None:
                    break
                seen.add(a); owner[a] = e
                r['ins'].append(ins)
                br, mems, imms = ins_refs(ins)
                for d, acc, idx in mems:
                    r['mems'].append((ins.address, d, acc, idx, ins.mnemonic))
                for v in imms:
                    r['imms'].append((ins.address, v, ins.mnemonic))
                m = ins.mnemonic
                if m == 'call':
                    if br is None:
                        r['ind'].append(fmt(ins))
                    elif in_newexec(br):
                        r['calls_new'].append(br)
                        if br not in routines:
                            routines[br] = dict(src=['call from 0x%x' % ins.address], ins=[], calls_new=[], calls_old=[],
                                                exits=[], mems=[], imms=[], ind=[])
                            q.append(br)
                    else:
                        r['calls_old'].append((ins.address, br))
                elif m == 'jmp':
                    if br is None:
                        r['ind'].append(fmt(ins)); break
                    if in_newexec(br):
                        todo.append(br); break
                    r['exits'].append((ins.address, br)); break
                elif ins.group(capstone.CS_GRP_JUMP) and br is not None:
                    if in_newexec(br):
                        todo.append(br)
                    else:
                        r['exits'].append((ins.address, br))
                elif ins.group(capstone.CS_GRP_RET) or m in ('int3', 'hlt', 'ud2'):
                    break
                a = ins.address + ins.size

    def new_routine(a, src):
        if a not in routines and a not in owner:
            routines[a] = dict(src=[src], ins=[], calls_new=[], calls_old=[], exits=[], mems=[], imms=[], ind=[])
            return True
        if a in routines and src not in routines[a]['src'] and len(routines[a]['src']) < 12:
            routines[a]['src'].append(src)
        return False

    imm_tables = collections.OrderedDict()
    for v, src in imm_cand.items():
        if plausible_code(v):
            for s_ in src:
                new_routine(v, s_)
        else:
            imm_tables[v] = src
    descend(list(routines))
    stats = collections.Counter()
    for rnd in range(1, 20):
        q = []
        # (a) immediates / absolute operands of reached code that point at plausible code in new sections
        for e, r in list(routines.items()):
            for a, v, m in r['imms']:
                if in_newexec(v) and v not in owner and plausible_code(v) and new_routine(v, 'imm @0x%x' % a):
                    q.append(v); stats['imm'] += 1
            for a, d, acc, idx, m in r['mems']:
                if in_new(d) and not idx and m in ('call', 'jmp'):
                    v = N.dword(d)
                    if in_newexec(v) and v not in owner and new_routine(v, 'ptr [0x%x] @0x%x' % (d, a)):
                        q.append(v); stats['ptr'] += 1
        # (b) aligned dwords in new sections outside reached code that point at plausible code
        for s in newsec:
            for a in range(s['va'], s['va'] + s['vsz'] - 3, 4):
                if any(x in owner for x in range(a, a + 4)):
                    continue
                v = N.dword(a)
                if in_newexec(v) and v not in owner and plausible_code(v) and new_routine(v, 'table dword @0x%x' % a):
                    q.append(v); stats['table'] += 1
        # (c) old-code dwords in changed data regions already handled; old .text calls into new code too
        if not q:
            break
        descend(q)
    log('  extra entries: %s' % dict(stats))
    for v, src in imm_tables.items():
        log('  table pushed / loaded by patched code (data, not code): 0x%x (%s) from %s' % (v, cls(v), '; '.join(src)))
    # coverage
    log('\n== new code: %d entries from patched code / data, %d routines' % (len(entries), len(routines)))
    nc = open(os.path.join(out, 'newcode.txt'), 'w', encoding='utf-8', newline='\n')
    for s in newsec:
        arr = N.sec_array(s, s['vsz'])
        nz = np.flatnonzero(arr)
        reached = set(a - s['va'] for a, e in owner.items() if s['va'] <= a < s['va'] + s['vsz'])
        rb = 0
        for a in owner:
            if s['va'] <= a < s['va'] + s['vsz']:
                rb += 1
        # count reached bytes (instruction lengths)
        cov = np.zeros(len(arr), dtype=bool)
        for e, r in routines.items():
            for ins in r['ins']:
                o = ins.address - s['va']
                if 0 <= o < len(arr):
                    cov[o:o + ins.size] = True
        un = np.flatnonzero((arr != 0) & ~cov)
        runs = []
        if len(un):
            st = pv = int(un[0])
            for i in un[1:]:
                i = int(i)
                if i - pv > 16:
                    runs.append((st, pv + 1)); st = i
                pv = i
            runs.append((st, pv + 1))
        log('  %-7s %s: %d non-zero bytes, %d reached as code, %d non-zero bytes not reached in %d runs' % (
            s['name'], 'exec' if s['ch'] & IMAGE_SCN_EXEC else 'data', len(nz), int(cov.sum()), len(un), len(runs)))
        nc.write('\n== %s unreached non-zero runs (data or code without a found entry)\n' % s['name'])
        for a, b in runs:
            va = s['va'] + a
            nc.write('  0x%06x..0x%06x (%d B)\n' % (va, s['va'] + b, b - a))
            for k in range(0, min(b - a, 64), 4):
                v = N.dword(va + k)
                nc.write('     +%02x 0x%08x %s %s\n' % (k, v, cls(v) if N.sec(v) else '', fl(v)))
    rt = open(os.path.join(out, 'routines.tsv'), 'w', encoding='utf-8', newline='\n')
    rt.write('entry\tsection\tsource\tinstructions\tcalls_old\texits\tabs_refs\ttu_candidates\n')
    tu_hits = {}
    for e, r in routines.items():
        r['ins'].sort(key=lambda i: i.address)
        nc.write('\n== routine 0x%06x (%s) from %s: %d instructions\n' % (e, cls(e), '; '.join(r['src'][:6]), len(r['ins'])))
        tcal = []
        for a, t in r['calls_old']:
            c = M.chain(t)
            nc.write('   call 0x%06x @0x%06x  %s\n' % (t, a, (
                'PC 0x%06x -> retail 0x%08x -> TU %s (%s)' % (c['pc'], c['retail'], ('0x%08x' % c['tu']) if c['tu'] else '-',
                                                              c['tier'])) if c and c['pc'] == t else (
                ('inside PC 0x%06x' % c['pc']) if c else 'unmapped')))
            if c and c['pc'] == t and c['tu']:
                tcal.append(c['tu'])
        for a, t in r['exits']:
            nc.write('   exit -> 0x%06x @0x%06x (%s)\n' % (t, a, cls(t)))
        for a, d, acc, idx, m in r['mems']:
            v = N.dword(d)
            nc.write('   %s [0x%06x%s] @0x%06x %s (%s) value 0x%08x %s\n' % (
                'W' if acc & capstone.CS_AC_WRITE else 'R', d, '+idx' if idx else '', a, m, cls(d), v, fl(v)))
        for a, v, m in r['imms']:
            if v >= 0x10000 or v in (3000, 0x40, 0x80):
                nc.write('   imm 0x%08x @0x%06x %s %s %s\n' % (v, a, m, cls(v) if N.sec(v) else '', fl(v)))
        for x in r['ind']:
            nc.write('   indirect: %s\n' % x)
        cand = M.tu_by_callees(tcal)
        tu_hits[e] = cand
        cs = ['0x%08x (%d of %d mapped callees; %s; plugins %s)' % (f, k, len(set(tcal)),
              '/'.join(M.tinfo.get(f, ('?', '?', 0))[:2]), ','.join(M.plugins_on_tu(f)) or '-') for f, k, n in cand]
        if cs:
            nc.write('   TU candidates by callees: %s\n' % '; '.join(cs))
        nc.write('   --\n')
        for ins in r['ins']:
            nc.write('   ' + fmt(ins) + '\n')
        rt.write('0x%x\t%s\t%s\t%d\t%s\t%s\t%s\t%s\n' % (
            e, cls(e), '; '.join(r['src'][:4]), len(r['ins']), ' '.join('0x%x' % t for a, t in r['calls_old']),
            ' '.join('0x%x' % t for a, t in r['exits']),
            ' '.join(sorted(set('0x%x' % d for a, d, acc, idx, m in r['mems']))), ' '.join(cs)))
    nc.close(); rt.close()

    # 5. regions table
    with open(os.path.join(out, 'regions.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('#\tsection\tva\tend\tbytes\tkind\tfunc_start\tpc_map\tretail\ttu\ttu_status\ttier\tplugin_sites_in_func'
                '\tplugins_on_tu\tref\ttargets\n')
        for r in rows:
            c = r['chain']
            f.write('%d\t%s\t0x%x\t0x%x\t%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                r['i'], r['sec'], r['lo'], r['hi'], r['n'], r['kind'], ('0x%x' % r['fs']) if r['fs'] else '',
                ('0x%x' % c['pc']) if c else '', ('0x%x' % c['retail']) if c else '',
                ('0x%x' % c['tu']) if c and c['tu'] else '', ('%s/%s' % (c['status'], c['cls'])) if c else '',
                c['tier'] if c else '', ' '.join('0x%x=%s' % (a, '+'.join(l)) for a, l in r['sites']),
                ','.join(M.plugins_on_tu(c['tu'])) if c else '', r['ref'], ' | '.join(r['targets'][:8])))
    ex = [r for r in rows if r['fs']]
    log('\n== code regions: %d; kinds %s' % (len(ex), dict(collections.Counter(r['kind'] for r in ex))))
    log('   mapped to a PC function of the Xbox map: %d; with a TU partner: %d; with plugin sites in the same function: %d'
        % (sum(1 for r in ex if r['chain']), sum(1 for r in ex if r['chain'] and r['chain']['tu']),
           sum(1 for r in ex if r['sites'])))
    if R:
        log('   REF bytes at the regions: %s' % dict(collections.Counter(r['ref'] for r in rows)))
    by_plugin = collections.defaultdict(set)
    for r in ex:
        for a, l in r['sites']:
            for x in l:
                by_plugin[x.split(':')[0]].add(r['i'])
    log('   regions per plugin (site inside the patched function): %s' % ', '.join(
        '%s %d' % (k, len(v)) for k, v in sorted(by_plugin.items())))
    log('   data regions: %d' % sum(1 for r in rows if r['kind'] == 'data'))
    log('\noutputs: sections.tsv regions.tsv regions_dis.txt newcode.txt routines.tsv summary.txt in %s' % out)
    with open(os.path.join(out, 'summary.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
