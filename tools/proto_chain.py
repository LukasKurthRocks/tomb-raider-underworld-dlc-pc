"""Look up the prototype 2007 <-> Xbox retail <-> Xbox TU <-> PC chain (read-only; docs/Befund-Prototyp-2007.md).

Reads the outputs of tools/proto_retail_map.py (work/proto2007/proto_retail_pc_names.tsv, proto_retail_pc_data.tsv),
tools/xbox_pc_funcmap.py (work/xmap/xbox_pc_map.tsv, xbox_pc_data.tsv) and the TU <-> retail pairing of the TU agent
(work/tu_funcdiff/pairs.tsv, read only). Every printed pair carries its method / tier from those files.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/proto_chain.py name REGEX              prototype function names matching REGEX (Python re,
                                                                 case-insensitive) with retail / TU / PC partners
  ../bin/pyt -t 120 tools/proto_chain.py data REGEX              prototype globals (map names) with retail / PC partners
  ../bin/pyt -t 120 tools/proto_chain.py retail ADDR [...]       from Xbox retail function addresses
  ../bin/pyt -t 120 tools/proto_chain.py tu ADDR [...]           from Xbox TU function addresses (via pairs.tsv)
  ../bin/pyt -t 120 tools/proto_chain.py pc ADDR [...]           from PC tru.exe function addresses (reverse map)
  ../bin/pyt -t 300 tools/proto_chain.py ctx PROTO_ADDR [...]    callers and callees of a prototype function with
                                                                 their names and partners (for manual pairing)
  ../bin/pyt -t 300 tools/proto_chain.py rctx RETAIL_ADDR [...]  the same for a retail function (names via the map)
  ../bin/pyt -t 300 tools/proto_chain.py refs NAME|ADDR [...]     prototype functions building the address of a
                                                                 global (map data name; any offset inside its size)
Paths are fixed to the repository layout (run from the repository root).
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

NAMES = 'work/proto2007/proto_retail_pc_names.tsv'
PDATA = 'work/proto2007/proto_retail_pc_data.tsv'
SYMS = 'work/proto2007/proto_symbols.tsv'
XPC = 'work/xmap/xbox_pc_map.tsv'
TUP = 'work/tu_funcdiff/pairs.tsv'
PROTO = 'work/proto2007/pe/content/tr8_Content.pe'
RETAIL = 'work/xenia_dump/retail_image_82000000.bin'


def rows(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        head = f.readline().rstrip('\n').split('\t')
        return [dict(zip(head, l.rstrip('\n').split('\t'))) for l in f]


class Chain:
    def __init__(self):
        self.names = rows(NAMES)
        self.by_proto = collections.defaultdict(list)
        self.by_retail = collections.defaultdict(list)
        for r in self.names:
            self.by_proto[int(r['proto'], 16)].append(r)
            if r['retail']:
                self.by_retail[int(r['retail'], 16)].append(r)
        self.xpc = dict((int(r['xbox_retail'], 16), r) for r in rows(XPC))
        self.pcx = dict((int(r['pc'], 16), r) for r in self.xpc.values())
        self.tu2r, self.r2tu = {}, {}
        for r in rows(TUP):
            if r.get('retail') and r.get('tu'):
                t, x = int(r['tu'], 16), int(r['retail'], 16)
                self.tu2r[t] = (x, r['status'], r['confidence'])
                self.r2tu[x] = t

    def fmt_retail(self, x, tu=None):
        pr = self.by_retail.get(x, [])
        nm = ' | '.join(sorted(set('%s [%s]' % (r['name'], r['obj']) for r in pr)))[:150] or '-'
        p0 = pr[0] if pr else None
        pc = self.xpc.get(x)
        t = tu if tu is not None else self.r2tu.get(x)
        return 'retail 0x%08x  TU %s  proto %s (%s/%s)  PC %s (%s/%s)  %s' % (
            x, ('0x%08x' % t) if t else '-', p0['proto'] if p0 else '-', p0['method'] if p0 else '',
            p0['tier'] if p0 else '', pc['pc'] if pc else '-', pc['method'] if pc else '', pc['tier'] if pc else '',
            nm)


def cmd_name(C, rx):
    r = re.compile(rx, re.I)
    for row in C.names:
        if r.search(row['name']):
            x = int(row['retail'], 16) if row['retail'] else None
            tu = C.r2tu.get(x) if x else None
            print('%-58s %-24s proto %s %5s B  retail %-10s %-9s %-1s %-5s TU %-10s PC %-10s %s' % (
                row['name'][:58], row['obj'][:24], row['proto'], row['size'], row['retail'] or '-', row['method'],
                row['tier'], row['callee_agreement'], ('0x%08x' % tu) if tu else '-', row['pc'] or '-',
                row['pc_tier']))


def cmd_data(rx):
    r = re.compile(rx, re.I)
    pd = dict((r2['proto'], r2) for r2 in rows(PDATA))
    for row in rows(SYMS):
        if row['kind'] in ('data', 'vftable', 'const') and r.search(row['name']):
            m = pd.get(row['address'])
            print('%-50s %-22s proto %s %5s B  retail %s (%s votes)  PC %s' % (
                row['name'][:50], row['obj'][:22], row['address'], row['size'], m['retail'] if m else '-',
                m['votes'] if m else '', (m['pc'] or '-') if m else '-'))




def cmd_ctx(C, addrs, retail_side):
    import ppc_xrefs as P
    path = RETAIL if retail_side else PROTO
    d, secs = P.load(path)
    funcs, res = P.cached(path)
    starts = set(f[0] for f in funcs)
    for a in addrs:
        f = P.func_of(funcs, a)
        if not f:
            print('0x%08x: no function' % a)
            continue
        fs = f[0]
        callees = []
        for x, k, v in res[fs]:
            if k == 'call' and v in starts and v not in callees:
                callees.append(v)
        callers = sorted(set(s for s, items in res.items() for x, k, v in items if k == 'call' and v == fs))
        def show(v):
            if retail_side:
                return C.fmt_retail(v)
            rs = C.by_proto.get(v, [])
            nm = ' | '.join(sorted(set(r['name'] for r in rs)))[:90] or '?'
            r0 = rs[0] if rs else {}
            return 'proto 0x%08x %-90s retail %-10s %s %s PC %s' % (v, nm, r0.get('retail') or '-',
                                                                  r0.get('method', ''), r0.get('tier', ''),
                                                                  r0.get('pc') or '-')
        print('== %s 0x%08x (%d B)' % ('retail' if retail_side else 'proto', fs, f[1] - fs))
        print('   self:   ' + show(fs))
        for v in callers:
            print('   caller: ' + show(v))
        for v in callees:
            print('   callee: ' + show(v))


def cmd_refs(C, names):
    """prototype functions that build the address of a global (any offset inside the symbol's size)"""
    import ppc_xrefs as P
    syms = dict((r['name'], r) for r in rows(SYMS) if r['kind'] in ('data', 'const', 'vftable', 'string'))
    funcs, res = P.cached(PROTO)
    for nm in names:
        if nm.startswith('0x'):
            lo, hi = int(nm, 16), int(nm, 16) + 4
        else:
            r = syms.get(nm)
            if not r:
                print('%s: not a data symbol' % nm)
                continue
            lo = int(r['address'], 16)
            hi = lo + max(4, int(r['size']))
        print('== %s 0x%08x..0x%08x' % (nm, lo, hi))
        for fs, items in sorted(res.items()):
            for x, k, v in items:
                if k == 'addr' and lo <= v < hi:
                    rs = C.by_proto.get(fs, [])
                    r0 = rs[0] if rs else {}
                    print('   0x%08x (+0x%x) in %-60s 0x%08x  retail %s %s PC %s' % (
                        x, v - lo, (' | '.join(sorted(set(q['name'] for q in rs))) or '?')[:60], fs,
                        r0.get('retail') or '-', r0.get('tier', ''), r0.get('pc') or '-'))


def main(a):
    if len(a) < 2:
        sys.exit(__doc__)
    C = Chain()
    if a[0] == 'name':
        cmd_name(C, a[1])
    elif a[0] == 'data':
        cmd_data(a[1])
    elif a[0] == 'retail':
        for x in a[1:]:
            print(C.fmt_retail(int(x, 16)))
    elif a[0] == 'tu':
        for x in a[1:]:
            t = int(x, 16)
            r = C.tu2r.get(t)
            print(('TU 0x%08x (%s/%s) -> ' % (t, r[1], r[2]) + C.fmt_retail(r[0], t)) if r else
                  'TU 0x%08x: no retail partner in pairs.tsv' % t)
    elif a[0] == 'pc':
        for x in a[1:]:
            p = int(x, 16)
            r = C.pcx.get(p)
            print(('PC 0x%08x (%s/%s) <- ' % (p, r['method'], r['tier']) + C.fmt_retail(int(r['xbox_retail'], 16)))
                  if r else 'PC 0x%08x: no retail partner in xbox_pc_map.tsv' % p)
    elif a[0] == 'refs':
        cmd_refs(C, a[1:])
    elif a[0] in ('ctx', 'rctx'):
        cmd_ctx(C, [int(x, 16) for x in a[1:]], a[0] == 'rctx')
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
