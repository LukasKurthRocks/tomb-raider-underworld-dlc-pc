"""Evaluate the THRALLLINK hits of a cdb log (thrall link crash tru+0x1976a3, tests 50i / 50j / 50k; docs
Befund-Thrall-Absturz.md). Two session files are understood:
  * session_thrall_watch.cdb (02.11.): hardware write breakpoints (`ba w4`) on the +4 links of four FIXED pool
    addresses 0x00cf1074 / 0x00cf1364 / 0x00cf1654 / 0x00cf1944, labelled "slot53..56" (old numbering from
    0x00ce74c0; real slots 110..113 of the pool at 0x00cdcd50). Per write:
        THRALLLINK slotNN / .time / dd <link> L1 / r eip / u @eip-8 L4 / kv 6
  * session_thrall_watch2.cdb (03.11.): dynamic watches - `THRALLLINK dyn1` (+4 of the category-0x3f instance being
    removed), `dyn2` / `dyn3` (+4 of the last two category-0x3f spawns), `THRALLHEAD` (+4 of the category head
    0x00d98f58) - and the event blocks THRALLSPAWN / THRALLREMOVE / THRALLUNLINK / THRALLREINSERT (r esi + dd).
A value that is a slot address minus 1 (e.g. 0x00cf135f) is the damage. Engine facts (static analysis 03.11.): +4 =
link to the next OLDER instance of the category list, +0 = the newer one or the head; push = tru+0x197670, unlink =
tru+0x197690 (crash +0x1976a3), pop = tru+0x1976c0 - these primitives only COPY a bad value ("carrier"); the root is a
decrement of the removed thrall's own +4 during its removal (before the unlink call tru+0x1bc70d).

Output: one row per hit (time, slot, old -> new value, class, writer eip + instruction + function, stack top), a
summary per writer, the thrall list events (session 2), the candidate table (built-in sites + --names + --dec-scan,
with the hits / stack frames that fall into them), the crash markers (AV2NDCHANCE / FASTFAIL / STACKOVERFLOW /
TERMINATEPROCESS, dump lines; run folder: the files in dumps\\), one VERDICT line and one NEXT line.
Classes: "slot NN" (a pool slot start = valid link), "FAULTY slot NN - 1", "head" (a category head), "zero",
"odd/unaligned" (suspicious, not a slot - 1), "other" (aligned, outside the pool - not judged).
Limits: a hardware write breakpoint stops AFTER the write, so eip is the instruction after the writer; the writer is
the disassembled instruction that ends at eip (`u @eip-8` can start mid-instruction: then "?" and the raw lines).
The old value is the previous hit's new value of the same address ("?" for the first hit). Read-only.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/thrall_link_report.py LOG_OR_RUN_FOLDER [--md OUT.md] [--names FILE] [--dec-scan FILE]
                   [--pool-start 0x00cdcd50] [--stride 0x2f0] [--pool-slots 1024]
  --names FILE    lines "0xOFFSET name" (tru-relative), added to the candidate table (NEAR match 0x100)
  --dec-scan FILE output of `tools/pe_reach_dec.py tru.exe --global --no-byte` (absolute VAs): a writer that is one of
                  these static decrement sites is marked [static dec site: class]
  Old numbering of session 1 / the synthetic test: --pool-start 0x00ce74c0 --pool-slots 120
  e.g. ../bin/pyt -t 60 tools/thrall_link_report.py ../runs/<time>_regress_shadowlara_50l_radial2
Exit code: 0 = evaluated, 2 = usage error / log not found.
"""
import sys, os, re, argparse, collections

MARKERS = ('AV2NDCHANCE', 'FASTFAIL', 'STACKOVERFLOW', 'TERMINATEPROCESS', 'EXITPROCESS', 'D3DFAIL',
           'MESSAGEBOX_A', 'MESSAGEBOX_W')
CRASH = ('AV2NDCHANCE', 'FASTFAIL', 'STACKOVERFLOW')
EVENTS = ('THRALLSPAWN', 'THRALLREMOVE', 'THRALLUNLINK', 'THRALLREINSERT')
HEADS, NHEADS = 0x00d98d60, 64          # category list heads 0xd98d60 + 8*k (thralls: k 0x3f = 0x00d98f58)
# known code sites, offsets relative to tru (tr8_win32_gm.exe, base 0x00400000); NEAR-matched (old table, --names)
KNOWN = {
    0x197690: 'instance list unlink (+0 next / +4 prev; crash site +0x1976a3 in 50i / 50j)',
    0x1bc70d: 'instance removal (active list 0xd98d54 -> free list 0xd98d5c, then second list +0 / +4)',
    0x18bd30: 'unload callback type 13 (TruDataGuard 0.2 false-alarm site)',
}
NEAR = 0x100   # a site counts as "in / near" a known entry up to this distance
# candidate table: (tru offset, size, role, name). role "carrier" = list primitive that only copies a link value.
CANDIDATES = [
    (0x197670, 0x1d, 'carrier', 'list push / insert-before(anchor, node): node+0 = anchor, node+4 = [anchor+4], '
                                '[anchor+4]+0 = node, anchor+4 = node'),
    (0x197690, 0x24, 'carrier', KNOWN[0x197690]),
    (0x1976c0, 0x2e, 'carrier', 'list pop (unlinks [anchor+4], returns it)'),
    (0x1bc4e0, 0x6bf, 'removal', 'INSTANCE_ReallyRemoveInstance(inst, flag): callbacks, active -> free list, unlink '
                                 'call +0x22d (the decrement must happen before it)'),
    (0x1bcba0, 0x05, 'removal', 'jmp to the removal (entry used by the unit unload)'),
    (0x1bcbb0, 0x7c, 'removal', 'remove every active instance flagged +0x14 bit 0x20'),
    (0x1c1c70, 0xae, 'removal', 'unit unload: flag the instances of a unit (+0xe0 / +0xe4), remove them newest first'),
    (0x1d1750, 0x200, 'removal', 'stream unit dump (calls the unit unload at +0x1a9 = tru+0x1d18f9)'),
    (0x1bb160, 0x380, 'spawn', 'instance introduce: category index +0x185 from the object flag byte, push at '
                               'tru+0x1bb479'),
    (0x1b2f40, 0x56, 'spawn', 're-insert into the category list (object flag byte -> 0xd98d60 + 8*k)'),
    (0x1b2ef0, 0x4e, 'spawn', 'instance alloc: free list 0xd98d5c (LIFO) -> active list 0xd98d54'),
    (0x2187c0, 0x33, 'enemy', 'type "enemy" query +0x11c (removal asks 0x172) -> tru+0x2164d0'),
    (0x227a80, 0x3c, 'enemy', 'type "enemy" message +0x120 (removal sends 0x22) -> tru+0x2254b0'),
    (0x2254b0, 0x86, 'enemy', 'enemy message dispatch: brain [inst+0x2ec], behaviours +0x1254, callback +0x1c44'),
    (0x271250, 0x80, 'enemy', 'enemy behaviour pair dispatch (vtable +0x28)'),
    (0x1b2de0, 0x50, 'removal', 'instance wake (also called by TruShadowPower before message 0x1f4 / 0x1f5)'),
    (0x1977d0, 0x36, 'weakref', 'weak handle release: u16 index into [0xcda0c0], add [node+4], -1, target = 0'),
    (0x31ca43, 0x2c, 'weakref', 'weak reference get / release inline (player +0x20): add [node+4], -1'),
    (0x197780, 0x39, 'other', 'ring stack pop (dec [this+4] and [this]) - would fault on an instance, not the writer'),
]
CARRIER_SITES = 'tru+0x19767d / +0x197687 / +0x197689 (push), +0x19769d / +0x1976a3 / +0x1976ac (unlink)'

THRALL = re.compile(r'^\s*THRALLLINK\s+slot(\d+)\s*$')
DYN = re.compile(r'^\s*(THRALLLINK\s+dyn(\d+)|THRALLHEAD)\s*$')
EVENT = re.compile(r'^\s*(' + '|'.join(EVENTS) + r')\s*$')
MARKER = re.compile(r'^\s*(' + '|'.join(MARKERS) + r')\s*$')
BA_CMD = re.compile(r'ba\s+w4\s+(?:0x)?([0-9a-fA-F]{8})\s+"\.echo THRALLLINK slot(\d+)')
TIME = re.compile(r'^Debug session time: \w{3} +(\w{3} +\d+) +([\d:.]+) +(\d{4})')
DD = re.compile(r'^([0-9a-f]{8})\s+([0-9a-f]{8}|\?{8})\s*$')
DDN = re.compile(r'^([0-9a-f]{8})((?:\s+(?:[0-9a-f]{8}|\?{8}))+)\s*$')
ESI = re.compile(r'^esi=([0-9a-f]{8})\s*$')
EIP = re.compile(r'^eip=([0-9a-f]{8})\s*$')
EIP_ANY = re.compile(r'\beip=([0-9a-f]{8})')
LABEL = re.compile(r'^([A-Za-z0-9_.]+(?:!\S+)?(?:\+0x[0-9a-f]+)?):\s*$')
INSN = re.compile(r'^([0-9a-f]{8}) ([0-9a-f]{2,30})\s+(\S.*?)\s*$')
CHILD = re.compile(r'^ChildEBP\s+RetAddr')
FRAME = re.compile(r'^([0-9a-f]{8}) ([0-9a-f]{8})\s+(?:[0-9a-f]{8} ){3}([^\s].*?)\s*$')
MODLOAD = re.compile(r'^ModLoad: ([0-9a-f]{8}) ([0-9a-f]{8})\s+(.+?)\s*$')
DUMPLINE = re.compile(r'^(Creating .+ dump|Dump successfully written|.*[Dd]ump.*(?:failed|error).*)\s*$')
BPERR = re.compile(r'(Couldn\'t resolve error|Unable to set breakpoint|Too many data breakpoints|'
                   r'data breakpoint.*(?:error|fail)|Bp expression .* could not be resolved|Syntax error|'
                   r'Numeric expression missing|Extra character error|Unable to set .*breakpoint)', re.I)


class Modules:
    """module ranges from the ModLoad lines; tr8_win32_gm is shown as tru"""

    def __init__(self, lines):
        self.ranges = []
        for l in lines:
            m = MODLOAD.match(l)
            if m:
                name = os.path.splitext(os.path.basename(m.group(3).replace('\\', '/')))[0]
                self.ranges.append((int(m.group(1), 16), int(m.group(2), 16), name))
        if not any(r[2].lower() == 'tr8_win32_gm' for r in self.ranges):
            self.ranges.append((0x00400000, 0x01236000, 'tr8_win32_gm'))   # default image base of the Steam build

    def name(self, addr):
        for lo, hi, n in reversed(self.ranges):
            if lo <= addr < hi:
                return ('tru' if n.lower() == 'tr8_win32_gm' else n), addr - lo
        return None, None

    def text(self, addr):
        n, off = self.name(addr)
        return '%s+0x%x' % (n, off) if n else '0x%08x' % addr


def short(text):
    """cdb symbol text: tr8_win32_gm -> tru"""
    return re.sub(r'\btr8_win32_gm(?=[+!])', 'tru', text)


def candidate_of(off):
    for start, size, role, name in CANDIDATES:
        if start <= off < start + size:
            return start, role, name
    return None


def function_of(mods, addr, known, decscan=None):
    n, off = mods.name(addr)
    if n != 'tru':
        return ('plugin / other module %s' % n) if n and n.lower().startswith('tru') else ''
    extra = ' [static dec site: %s]' % decscan[addr] if decscan and addr in decscan else ''
    c = candidate_of(off)
    if c:
        start, role, name = c
        return ('%s (tru+0x%x +0x%x)' % (name, start, off - start) if off != start else name) + extra
    best = max((k for k in known if k <= off), default=None)
    if best is not None and off - best <= NEAR:
        return ('%s (tru+0x%x +0x%x)' % (known[best], best, off - best) if off != best else known[best]) + extra
    return extra.strip()


def is_carrier(mods, addr):
    n, off = mods.name(addr)
    c = candidate_of(off) if n == 'tru' else None
    return bool(c and c[1] == 'carrier')


def load_names(path, known):
    for l in open(path, encoding='utf-8', errors='replace'):
        l = l.strip()
        if not l or l.startswith('#'):
            continue
        parts = l.split(None, 1)
        try:
            known[int(parts[0], 16)] = parts[1] if len(parts) > 1 else '?'
        except ValueError:
            pass


def load_decscan(path):
    out = {}
    for l in open(path, encoding='utf-8', errors='replace'):
        p = l.split()
        if len(p) >= 2 and p[0].startswith('0x'):
            try:
                out[int(p[0], 16)] = p[1]
            except ValueError:
                pass
    return out


def block_end(lines, i):
    j = i + 1
    while j < len(lines) and not THRALL.match(lines[j]) and not DYN.match(lines[j]) and not EVENT.match(lines[j]) \
            and not MARKER.match(lines[j]):
        j += 1
    return j


def parse_hit(lines, i, end, slot, watch):
    h = {'line': i + 1, 'slot': slot, 'time': '?', 'value': None, 'eip': None, 'insns': [], 'frames': [],
         'cut': end >= len(lines) and end - i < 4, 'addr': watch}
    phase = 'head'
    for l in lines[i + 1:end]:
        s = l.rstrip()
        m = TIME.match(s)
        if m and h['time'] == '?':
            h['time'] = m.group(2); continue
        m = DD.match(s)
        if m and phase == 'head' and h['value'] is None and (watch is None or int(m.group(1), 16) == watch):
            h['value'] = None if m.group(2).startswith('?') else int(m.group(2), 16)
            h['addr'] = int(m.group(1), 16)
            continue
        m = EIP.match(s)
        if m and h['eip'] is None:
            h['eip'] = int(m.group(1), 16); phase = 'disasm'; continue
        if CHILD.match(s):
            phase = 'stack'; continue
        if phase == 'disasm':
            m = INSN.match(s)
            if m:
                h['insns'].append((int(m.group(1), 16), m.group(2), re.sub(r'\s+', ' ', m.group(3))))
        elif phase == 'stack':
            m = FRAME.match(s)
            if m:
                h['frames'].append((int(m.group(2), 16), m.group(3)))
    return h


def parse_event(lines, i, end):
    e = {'line': i + 1, 'name': lines[i].strip(), 'time': '?', 'inst': None, 'dd': {}, 'frames': []}
    for l in lines[i + 1:end]:
        s = l.rstrip()
        m = TIME.match(s)
        if m and e['time'] == '?':
            e['time'] = m.group(2); continue
        m = ESI.match(s)
        if m and e['inst'] is None:
            e['inst'] = int(m.group(1), 16); continue
        m = DDN.match(s)
        if m:
            vals = [None if v.startswith('?') else int(v, 16) for v in m.group(2).split()]
            e['dd'][int(m.group(1), 16)] = vals
            continue
        m = FRAME.match(s)
        if m:
            e['frames'].append((int(m.group(2), 16), m.group(3)))
    if e['inst'] is None and e['dd']:           # THRALLREINSERT: no `r esi`, the first dd is the instance
        e['inst'] = next(iter(e['dd']))
    return e


def writer_of(h):
    """the disassembled instruction that ends at eip (a data breakpoint stops after the write)"""
    if h['eip'] is None:
        return None
    for a, b, t in h['insns']:
        if a + len(b) // 2 == h['eip']:
            return a, b, t
    return None


def classify(v, slots):
    if v is None:
        return '?', 'not read'
    if v == 0:
        return 'zero', 'zero'
    if v in slots:
        return 'valid', 'slot %d' % slots[v]
    if v + 1 in slots:
        return 'FAULTY', 'FAULTY slot %d - 1' % slots[v + 1]
    if HEADS <= v < HEADS + 8 * NHEADS and (v - HEADS) % 8 == 0:
        return 'valid', 'head %02x' % ((v - HEADS) // 8)
    if v & 3:
        return 'odd', 'odd/unaligned'
    return 'other', 'other'


def crash_block(lines, i, end, mods):
    name = lines[i].strip()
    d = {'name': name, 'line': i + 1, 'time': '?', 'eip': None, 'insn': '', 'frames': [], 'dumps': []}
    after_label = False
    for l in lines[i + 1:end]:
        s = l.rstrip()
        m = TIME.match(s)
        if m and d['time'] == '?':
            d['time'] = m.group(2)
        m = EIP_ANY.search(s)
        if m and d['eip'] is None:
            d['eip'] = int(m.group(1), 16)
        if LABEL.match(s):
            after_label = True; continue
        if after_label and not d['insn']:
            m = INSN.match(s)
            if m:
                d['insn'] = re.sub(r'\s+', ' ', m.group(3))
            after_label = False
        m = FRAME.match(s)
        if m and len(d['frames']) < 4:
            d['frames'].append(m.group(3))
        if DUMPLINE.match(s) or s in ('FULLDUMP', 'DUMPDONE'):
            d['dumps'].append(s)
    return d


def main(argv):
    ap = argparse.ArgumentParser(description='THRALLLINK evaluator (read-only)', add_help=True)
    ap.add_argument('source', help='cdb log file or run folder (uses <folder>\\cdb.log)')
    ap.add_argument('--md', help='also write the report as Markdown to this file')
    ap.add_argument('--names', help='extra function names: lines "0xOFFSET name" (tru-relative)')
    ap.add_argument('--dec-scan', help='output of tools/pe_reach_dec.py --global (static decrement sites)')
    ap.add_argument('--pool-start', default='0x00cdcd50')
    ap.add_argument('--stride', default='0x2f0')
    ap.add_argument('--pool-slots', type=int, default=1024)
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    src = a.source
    folder = src if os.path.isdir(src) else None
    log = os.path.join(src, 'cdb.log') if folder else src
    if not os.path.isfile(log):
        print('log not found: %s' % log)
        return 2
    known = dict(KNOWN)
    if a.names:
        load_names(a.names, known)
    decscan = load_decscan(a.dec_scan) if a.dec_scan else {}
    start, stride = int(a.pool_start, 16), int(a.stride, 16)
    slots = {start + k * stride: k for k in range(a.pool_slots)}
    lines = open(log, encoding='utf-8', errors='replace').read().splitlines()
    mods = Modules(lines)
    synthetic = any('SYNTHETIC' in l for l in lines[:20])

    def slot_label(v):
        if v is None:
            return '?'
        if v in slots:
            return 'slot%d' % slots[v]
        if v + 1 in slots:
            return 'slot%d-1' % slots[v + 1]
        if HEADS <= v < HEADS + 8 * NHEADS and (v - HEADS) % 8 == 0:
            return 'head%02x' % ((v - HEADS) // 8)
        return '0x%08x' % v

    armed = {}
    bperr = []
    for idx, l in enumerate(lines):
        m = BA_CMD.search(l)
        if m and l.lstrip().startswith(('0:', 'ba')):
            armed[int(m.group(2))] = int(m.group(1), 16)
        if BPERR.search(l):
            bperr.append((idx + 1, l.strip()[:160]))

    hits, crashes, others, events = [], [], [], []
    last = {}
    for idx, l in enumerate(lines):
        m = THRALL.match(l)
        md_ = DYN.match(l) if not m else None
        if m or md_:
            if m:
                label = int(m.group(1))
                watch = armed.get(label, start + label * stride + 4)
            else:
                label = 'dyn%s' % md_.group(2) if md_.group(2) else 'head3f'
                watch = HEADS + 8 * 0x3f + 4 if not md_.group(2) else None
            h = parse_hit(lines, idx, block_end(lines, idx), label, watch)
            base = h['addr'] - 4 if h['addr'] is not None else None
            if base in slots:
                h['slotno'] = slots[base]
            h['old'] = last.get(h['addr'])
            if h['value'] is not None and h['addr'] is not None:
                last[h['addr']] = h['value']
            h['cls'], h['label'] = classify(h['value'], slots)
            h['writer'] = writer_of(h)
            hits.append(h)
            continue
        m = EVENT.match(l)
        if m:
            events.append(parse_event(lines, idx, block_end(lines, idx)))
            continue
        m = MARKER.match(l)
        if m:
            c = crash_block(lines, idx, block_end(lines, idx), mods)
            (crashes if c['name'] in CRASH else others).append(c)

    def slot_col(h):
        if isinstance(h['slot'], int):
            return str(h.get('slotno', h['slot']))
        return '%s %s' % (h['slot'], ('slot%d' % h['slotno']) if 'slotno' in h else
                          ('@0x%08x' % h['addr'] if h['addr'] is not None else '?'))

    def where(h):
        return ('slot %s' % slot_col(h)) if isinstance(h['slot'], int) else slot_col(h)

    out = []
    p = out.append
    p('# THRALLLINK report: %s' % log)
    if synthetic:
        p('')
        p('**SYNTHETIC test log** (marked in its header) - parser check only, no game data.')
    p('')
    p('Pool: start 0x%08x, stride 0x%x, %d slots (slot 55 = 0x%08x). Breakpoints armed in the log: %s.'
      % (start, stride, a.pool_slots, start + 55 * stride,
         ', '.join('slot%d @0x%08x' % (k, v) for k, v in sorted(armed.items())) or 'none found'))
    for n, t in bperr:
        p('* breakpoint problem, line %d: `%s`' % (n, t))
    p('')
    p('## Hits (%d)' % len(hits))
    p('')
    p('| # | line | time | slot | old -> new | class | writer eip | writer instruction | function | stack top |')
    p('|---|---|---|---|---|---|---|---|---|---|')
    for k, h in enumerate(hits, 1):
        w = h['writer']
        wa = w[0] if w else None
        old = '0x%08x' % h['old'] if h['old'] is not None else '?'
        new = '0x%08x' % h['value'] if h['value'] is not None else '?'
        eip_t = mods.text(h['eip']) if h['eip'] is not None else '?'
        w_t = '%s `%s`' % (mods.text(wa), w[2]) if w else ('? (no instruction ends at eip%s)' % (
            '; disasm: ' + ' / '.join('%s %s' % (mods.text(x[0]), x[2]) for x in h['insns']) if h['insns'] else ''))
        fn = function_of(mods, wa if wa is not None else (h['eip'] or 0), known, decscan)
        stack = ' <- '.join(short(f[1]) for f in h['frames'][1:4]) or '-'
        cls = '**%s**' % h['label'] if h['cls'] in ('FAULTY', 'odd') else h['label']
        p('| %d | %d | %s | %s | %s -> %s | %s | %s | %s | %s | %s |'
          % (k, h['line'], h['time'], slot_col(h), old, new, cls, eip_t, w_t, fn or '-', stack))
    if not hits:
        p('| - | - | - | - | - | none | - | - | - | - |')

    p('')
    p('## Writers')
    p('')
    p('| writer | instruction | function | hits | slots | classes |')
    p('|---|---|---|---|---|---|')
    groups = collections.OrderedDict()
    for h in hits:
        w = h['writer']
        key = w[0] if w else ('eip', h['eip'])
        g = groups.setdefault(key, {'w': w, 'eip': h['eip'], 'n': 0, 'slots': set(), 'cls': collections.Counter()})
        g['n'] += 1; g['slots'].add(slot_col(h)); g['cls'][h['label'] if h['cls'] != 'valid' else 'valid slot'] += 1
    for key, g in groups.items():
        w = g['w']
        site = mods.text(w[0]) if w else ('? (eip %s)' % (mods.text(g['eip']) if g['eip'] is not None else '?'))
        fn = function_of(mods, w[0] if w else (g['eip'] or 0), known, decscan)
        p('| %s | %s | %s | %d | %s | %s |' % (site, '`%s`' % w[2] if w else '?', fn or '-', g['n'],
                                               ', '.join(sorted(g['slots'], key=lambda s: (len(s), s))),
                                               ', '.join('%s x%d' % kv for kv in g['cls'].items())))
    if not groups:
        p('| - | - | - | 0 | - | - |')

    unlink_bad = []
    if events:
        p('')
        p('## Thrall list events (%d)' % len(events))
        p('')
        p('| line | time | event | instance | +0 | +4 | object / flags | note |')
        p('|---|---|---|---|---|---|---|---|')
        for e in events:
            inst = e['inst']
            v = e['dd'].get(inst, [None, None]) if inst is not None else [None, None]
            v0, v4 = (v + [None, None])[:2]
            of = e['dd'].get(inst + 0x10, None) if inst is not None else None
            note = ''
            c4 = classify(v4, slots)[0] if v4 is not None else '?'
            if c4 == 'FAULTY':
                note = '**+4 already slot - 1**'
                if e['name'] == 'THRALLUNLINK':
                    unlink_bad.append((e, v4))
            if v0 is not None and v0 not in slots and not (HEADS <= v0 < HEADS + 8 * NHEADS) and v0 != 0:
                note += ' +0 not a slot / head'
            p('| %d | %s | %s | %s | %s | %s | %s | %s |' % (
                e['line'], e['time'], e['name'], slot_label(inst), slot_label(v0), slot_label(v4),
                ' / '.join('0x%08x' % x for x in of if x is not None) if of else '-', note.strip() or '-'))

    p('')
    p('## Candidates')
    p('')
    p('Built-in sites (static analysis 03.11., docs Befund-Thrall-Absturz.md)%s%s; "seen" = hits whose writer lies in the'
      ' range / stack frames (return addresses) of hits and events that lie in it.' % (
          ' + %d --names entries' % (len(known) - len(KNOWN)) if len(known) > len(KNOWN) else '',
          ' + %d static decrement sites (--dec-scan)' % len(decscan) if decscan else ''))
    p('')
    p('| site | size | role | name | writer hits | stack frames |')
    p('|---|---|---|---|---|---|')
    allframes = [f[0] for h in hits for f in h['frames']] + [f[0] for e in events for f in e['frames']]
    for st, size, role, name in CANDIDATES:
        lo, hi = 0x400000 + st, 0x400000 + st + size
        wh = sum(1 for h in hits if h['writer'] and lo <= h['writer'][0] < hi)
        fr = sum(1 for x in allframes if lo <= x < hi)
        p('| tru+0x%x | 0x%x | %s | %s | %s | %s |' % (st, size, role, name, wh or '-', fr or '-'))
    for off in sorted(set(known) - set(KNOWN)):
        lo = 0x400000 + off
        wh = sum(1 for h in hits if h['writer'] and lo <= h['writer'][0] < lo + NEAR)
        fr = sum(1 for x in allframes if lo <= x < lo + NEAR)
        p('| tru+0x%x | ~0x%x | names | %s | %s | %s |' % (off, NEAR, known[off], wh or '-', fr or '-'))

    p('')
    p('## Crash / end markers')
    p('')
    for c in crashes + others:
        site = mods.text(c['eip']) if c['eip'] is not None else '?'
        if site == 'tru+0x1976a3':
            site += ' (= the 50i / 50j thrall link crash site)'
        p('* %s (line %d, %s): eip %s `%s`; stack %s' % (c['name'], c['line'], c['time'], site, c['insn'] or '-',
                                                       ' <- '.join(short(x) for x in c['frames'][:4]) or '-'))
        for dl in c['dumps']:
            p('  * dump: %s' % dl)
    if not crashes and not others:
        p('* none (no AV2NDCHANCE / FASTFAIL / STACKOVERFLOW / TERMINATEPROCESS line)')
    if folder:
        dd = os.path.join(folder, 'dumps')
        files = sorted(os.listdir(dd)) if os.path.isdir(dd) else []
        p('* run folder dumps\\: %s' % (', '.join('%s (%d MB)' % (f, os.path.getsize(os.path.join(dd, f)) // 1048576)
                                                 for f in files) or 'none'))

    faulty = [h for h in hits if h['cls'] == 'FAULTY']
    root = [h for h in faulty if not (h['writer'] and is_carrier(mods, h['writer'][0]))]
    carried = [h for h in faulty if h not in root]
    odd = [h for h in hits if h['cls'] == 'odd']
    site_crash = [c for c in crashes if c['eip'] is not None and mods.text(c['eip']) == 'tru+0x1976a3']
    p('')
    nxt = ''
    if root:
        f = root[0]
        w = f['writer']
        who = '%s `%s`' % (mods.text(w[0]), w[2]) if w else 'eip %s (writer instruction not resolved)' % (
            mods.text(f['eip']) if f['eip'] is not None else '?')
        writers = sorted({mods.text(h['writer'][0]) if h['writer'] else '?' for h in root})
        v = 'VERDICT: FAULTY WRITER CAUGHT - %s wrote slot-1 value(s) %d time(s); first: %s = 0x%08x at %s (line %d); writers: %s' % (
            who, len(root), where(f), f['value'], f['time'], f['line'], ', '.join(writers))
        fn = function_of(mods, w[0] if w else (f['eip'] or 0), known, decscan)
        nxt = ('NEXT: disassemble the writer\'s function (tools/pe_dis.py EXE --func 0x%08x) and its caller chain from '
               'the stack (%s); find where the decremented pointer comes from (a holder that should point to a '
               'refcounted node / weak reference but holds the instance)%s' % (
                   w[0] if w else (f['eip'] or 0), ' <- '.join(short(x[1]) for x in f['frames'][:4]) or 'no stack',
                   '; candidate: ' + fn if fn else ''))
    elif carried:
        f = carried[0]
        w = f['writer']
        v = ('VERDICT: FAULTY VALUE PROPAGATED - %s `%s` (list primitive) copied slot-1 value(s) %d time(s); first: '
             '%s = 0x%08x at %s (line %d) - the root decrement happened earlier on the link that was copied' % (
                 mods.text(w[0]), w[2], len(carried), where(f), f['value'], f['time'], f['line']))
        nxt = ('NEXT: look for an earlier FAULTY / odd hit on THRALLHEAD or dyn1-3; if none: run session_thrall_watch2.cdb '
               '(watch on the removed instance\'s own +4)')
    elif unlink_bad:
        e, v4 = unlink_bad[0]
        v = ('VERDICT: DAMAGE PRESENT AT UNLINK, writer not caught - %s +4 = 0x%08x (%s) at THRALLUNLINK line %d (%s)'
             % (slot_label(e['inst']), v4, slot_label(v4), e['line'], e['time']))
        nxt = ('NEXT: the decrement happened outside the watched window (before the removal started?): compare the '
               'THRALLREMOVE line of that instance; widen the watch (spawn watches dyn2 / dyn3)')
    elif odd:
        v = 'VERDICT: no slot-1 write, but %d odd/unaligned value(s) (first %s = 0x%08x at %s) - check those writers' % (
            len(odd), where(odd[0]), odd[0]['value'], odd[0]['time'])
        nxt = 'NEXT: check the writers of the odd values (tools/pe_dis.py --func)'
    elif hits:
        v = 'VERDICT: no faulty write caught (%d hit(s): %s)' % (
            len(hits), ', '.join('%s x%d' % kv for kv in collections.Counter(h['label'] for h in hits).items()))
        if site_crash:
            v += ' - BUT the crash tru+0x1976a3 happened: the damage came through another link (other slots / +0 next)'
            nxt = ('NEXT: tools/instance_lists_dump.py on the dump (where were the thralls?), then '
                   'session_thrall_watch2.cdb')
        else:
            nxt = 'NEXT: no damage in the watched links; repeat with an unload (level.load / quit) while thralls exist'
    else:
        v = 'VERDICT: no THRALLLINK hits (%s)' % (
            'breakpoints armed, the watched links were never written' if armed or events else
            'no ba w4 THRALLLINK commands in the log - was session_thrall_watch.cdb used?')
        if site_crash:
            v += ' - crash tru+0x1976a3 happened'
            nxt = ('NEXT: %s tools/instance_lists_dump.py on the dump shows where the thralls were; then '
                   'session_thrall_watch2.cdb (dynamic watches)' % (
                       'the thralls were not at the watched addresses (or the decrement hit unwatched slots):'
                       if armed or events else 'no THRALLLINK breakpoints in this run;'))
        else:
            nxt = 'NEXT: were thralls loaded and removed (unit change / quit) in this session?'
    if crashes:
        v += '; crash markers: %s' % ', '.join('%s %s' % (c['name'], mods.text(c['eip']) if c['eip'] is not None else '?')
                                              for c in crashes)
    if synthetic:
        v += ' [SYNTHETIC LOG]'
    p(v)
    if nxt:
        p(nxt)

    text = '\n'.join(out)
    print(text)
    if a.md:
        with open(a.md, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text + '\n')
        print('\nMarkdown written: %s' % a.md)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
