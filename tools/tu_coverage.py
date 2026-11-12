"""TU coverage list: every changed and every new function of the title update (Xbox, TU vs retail) with a topic, a PC
partner where one is mapped, its changed blocks, and a status (ported / partial / explained / irrelevant / open) -
read-only (TODO N20, 09.11.2026; changed blocks + status partial 10.11.2026).

Inputs (all workspace-relative):
  work/xenia_dump/retail_image_82000000.bin, work/xenia_dump/tu_image_82000000.bin   Xenia image dumps
      -> functions aligned exactly like tools/xbox_func_diff.py (equal / changed / new)
  work/xmap/xbox_pc_map.tsv            retail -> PC function map (tier verified / anchor / unverified / contradicted)
  work/proto2007/proto_retail_pc_names.tsv   2007 prototype names (name, obj) per retail function
  src/asi/<plugin>/*.cpp|*.md|*.ini    TU / retail addresses our plugins translate (TruGuard is never read)
  docs/ENGINE.md, ../docs/Befund-*.md  TU / retail addresses mentioned in findings (local docs, if present)
  docs/data/tu_coverage_overrides.tsv  hand-kept statuses (tu_addr, status, basis, plugin, note, pc) for functions
                                       and for single changed blocks - win over everything (format: file header)

Functions and pairing (Q49, 12.11.2026): both images are cut into the .pdata functions plus the bl targets without a
.pdata entry (leaf functions, tools/tu_func_pair.cached_all; ~1 900 per image, end found by a scan that hits 99.8 % of
the .pdata ends). After the address-order alignment, unpaired new TU / removed retail functions pair as class `moved`
when their normalised body hash is equal and unique on both sides (the linker moved them), then through the call sites
of paired functions (a removed retail callee always facing the same new TU callee). Late pairs without any changed
block are not listed; empty new functions (`blr` only) neither. A retail-labelled address does not name a TU function
across a pair with a size ratio > 2 (split / inlined / guessed pair). A plugin address counts as "not ported" when its
line or the sentence before it (across comment lines, up to the last '. ', blank line, bullet or table border) says
so ("not ported", "Not in 0.6.6", ...).

Changed blocks (changed functions): the TU and retail bodies are aligned instruction by instruction (difflib on a
register-free skeleton; relocations masked: b / bl by callee identity, bc / jump tables by target, lis / address
halves). Every differing run (runs <= 2 instructions apart merge) is a block, a TU address range with a kind:
  code / operands / deleted     real differences (another instruction sequence / an immediate, condition or callee /
                                retail code gone) - these must be translated or explained
  alloc / layout / reorder      register allocation, stack frame, hoisted zero, empty debug-print stubs, moved field
                                displacements, the same instructions in another order - listed, NOT counted as gaps
                                (very likely no behaviour change; not proven)
  new function                  the whole body of a TU-new function (no retail body to diff)
A block is covered when a plugin source / README names a TU address inside it (or a range `0x82a..0x82b` overlapping
it, or a retail-labelled address inside its retail range); a plain function-start address names the function, not a
block. A block > 128 B covered by one single address is marked WEAK. Block overrides (status covered / noport /
uncovered) add evidence the text scan cannot see (e.g. the PC address a plugin patches, with its byte check, or a
"not translated" that stands on the line above the address).
Status rules (honest: unknown = open):
  ported      a plugin names the function and every code / operands / deleted block is covered (or noport)
  partial     a plugin names the function, but at least one such block is not covered (column uncovered_blocks)
  explained   only via the override file (a finding says no port is needed)
  irrelevant  prototype object of an Xbox platform library (xmedia, xam, xui, xnet, live, storage, Xenos d3d) -
              basis heuristic; or via override
  open        everything else; `refs` lists findings / ENGINE.md that mention it (known but not ported)
Topic: from the prototype object of the retail partner, else a vote of the named callers / callees, else strings,
else data marks (doppelganger flag disp 0x1244, meter +0x508, TU global 0x827754ac); `topic_basis` says which.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/tu_coverage.py [--out docs/data/tu_coverage.tsv] [--summary FILE] [--ref REV]
                                          [--compare OLD.tsv]
  --ref REV           read plugin sources + docs/ENGINE.md as committed at REV (git show) instead of the working copy
  --compare OLD.tsv   add a status transition table (old -> new) to the summary
  --why A[,A..]       print every finding / plugin line that names the functions containing A, and their blocks
  --show A[,A..]      as --why plus retail / TU disassembly of every open code block side by side (--all: every block)
  --out FILE          write the TSV there (the list in the repo: --out docs/data/tu_coverage.tsv); without --out no
                      TSV is written at all - the run only prints the summary (and writes --summary if given)
  --why / --show alone print only (no summary; the TSV is written only with --out)
Output: the TSV (--out only; one row per changed / new TU function; block columns blocks, blocks_open, bytes_open,
uncovered_blocks (range, kind, size, {hint: callees, compare / li constants, built addresses}), covered_blocks (range:
evidence)) and a summary (counts per status / topic, biggest open topics) on stdout and in --summary. Only addresses,
names, constants and counts are written - no game bytes (--show prints disassembly to stdout only).
"""
import sys, os, re, struct, difflib, collections, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xbox_func_diff as XD
import tu_func_pair as TP
import ppc_xrefs as P

BASE = 0x82000000
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
WS = os.path.normpath(os.path.join(ROOT, '..'))
RETAIL = os.path.join(ROOT, 'work', 'xenia_dump', 'retail_image_82000000.bin')
TU = os.path.join(ROOT, 'work', 'xenia_dump', 'tu_image_82000000.bin')
XMAP = os.path.join(ROOT, 'work', 'xmap', 'xbox_pc_map.tsv')
PROTO = os.path.join(ROOT, 'work', 'proto2007', 'proto_retail_pc_names.tsv')
OVR = os.path.join(ROOT, 'docs', 'data', 'tu_coverage_overrides.tsv')

PLATFORM = ('xmedia:', 'xam', 'xui', 'xnet', 'xonline', 'xhv', 'xapilib', 'xboxkrnl', 'xgraphics', 'd3d9:', 'd3d9i:',
            'xbdm', 'xcontent', 'xstorage', 'xlive', 'xact', 'x3daudio', 'xaudio', 'fmodxbox360', 'xenonsave')
TOPICS = [  # (topic, keywords in prototype name / object, lower case) - first hit wins
    ('enemy / combat', ('enemy', 'thrall', 'combat', 'sense', 'behavior', 'behaviour', 'attack', 'melee', 'damage',
                        'health', 'chunk', 'targeting', 'targeter', 'creature', 'yeti', 'soldier')),
    ('player / chart', ('player', 'lara', 'playersc', 'statechart', 'chart', 'doppel', 'shadow')),
    ('camera', ('camera',)),
    ('physics', ('physics', 'multibody', 'ntmultibody', 'collide', 'collision', 'chuckable', 'ragdoll', 'rigid',
                 'sweepandprune', 'geom', 'joint', 'body', 'contact')),
    ('markup / navigation', ('markup', 'navmesh', 'navgraph', 'nav', 'path', 'jump', 'ledge', 'climb', 'grab',
                             'parabola', 'solvecubic', 'trmarkup')),
    ('animation / cloth', ('anim', 'cloth', 'hair', 'skeleton', 'bone', 'ik')),
    ('render / fx', ('render', 'draw', 'shader', 'light', 'texture', 'material', 'vertex', 'effect', 'fx', 'particle',
                     'scene', 'model', 'blur', 'reticle', 'decal', 'shadowmap', 'gpu', 'nga')),
    ('sound', ('sound', 'audio', 'fmod', 'music', 'voice', 'dialog')),
    ('ui / hud', ('ui', 'hud', 'menu', 'pda', 'screen', 'font', 'text', 'subtitle', 'local', 'objective', 'hint')),
    ('script', ('script', 'native', 'cdcscript', 'scenums')),
    ('streaming / save', ('stream', 'load', 'unit', 'level', 'drm', 'file', 'save', 'resource', 'memory', 'heap',
                          'archive', 'objectlist')),
    ('input', ('input', 'pad', 'controller', 'rumble', 'button')),
]
MARKS = {0x1244: 'doppelganger flag disp 0x1244', 0x508: 'meter +0x508'}
GLOBAL_MARKS = {0x827754ac: 'TU global 0x827754ac', 0x827754cc: 'TU global 0x827754cc'}
ADDR_RE = re.compile(r'0x82[0-9a-fA-F]{6}')


def topic_of(text):
    """keywords of <= 3 letters must be a whole word token (CamelCase / non-letters split), longer ones a substring"""
    t = text.lower()
    tokens = set(w.lower() for w in re.findall(r'[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+', text))
    for name, keys in TOPICS:
        if any((k in tokens) if len(k) <= 3 else (k in t) for k in keys):
            return name
    return ''


def is_platform(obj):
    o = obj.lower()
    return any(o.startswith(p) or (':' in o and p.rstrip(':') in o.split(':')[0]) for p in PLATFORM)


def _opseq(d, fs, fe):
    """order key per instruction for the pairing: primary opcode (+ extended opcode for 19 / 31 / 59 / 63)"""
    out = []
    for a in range(fs, fe, 4):
        w = _word(d, a)
        op = w >> 26
        out.append(op * 1024 + ((w >> 1) & 0x3ff) if op in EXT_OPS else op * 1024)
    return out


def pair_run(rd, rfs, td, tfs, threshold=0.5):
    """pairs inside one replaced run of the function alignment: an order-keeping best match (dynamic programming over
    the opcode-sequence similarity, pairs below `threshold` not taken) instead of xbox_func_diff's position pairing,
    which shifts as soon as the TU split a function or inserted one (10.11.: 163 pairs with a size ratio > 2)"""
    n, m = len(rfs), len(tfs)
    if n * m > 4000:                               # too big for the matrix: keep the position pairing
        k = min(n, m)
        return [(i, i) for i in range(k)]
    rs = [_opseq(rd, s, e) for s, e in rfs]
    ts = [_opseq(td, s, e) for s, e in tfs]
    sim = [[0.0] * m for _ in range(n)]
    for i in range(n):
        for j in range(m):
            a, b = len(rs[i]), len(ts[j])
            if min(a, b) * 3 < max(a, b):
                continue
            sm = difflib.SequenceMatcher(None, rs[i], ts[j], autojunk=False)
            if sm.real_quick_ratio() >= threshold and sm.quick_ratio() >= threshold:
                r = sm.ratio()
                sim[i][j] = r if r >= threshold else 0.0
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            best[i][j] = max(best[i + 1][j], best[i][j + 1], (sim[i][j] + best[i + 1][j + 1]) if sim[i][j] else 0.0)
    out, i, j = [], 0, 0
    while i < n and j < m:
        if sim[i][j] and best[i][j] == sim[i][j] + best[i + 1][j + 1]:
            out.append((i, j))
            i, j = i + 1, j + 1
        elif best[i][j] == best[i + 1][j]:
            i += 1
        else:
            j += 1
    return out


def align():
    """functions of both images (.pdata + the bl targets without .pdata, tu_func_pair.functions_all - Q49), aligned in
    address order (equal / changed / new / removed); then the still unpaired new TU and removed retail functions pair
    as 'moved' when their normalised body hash (xbox_func_diff.norm_hash) is equal and unique on both sides - a
    function the TU linker only moved (Q17: ~253 of the 'new' ones). Returns ..., moved [(retail, tu)], ambiguous
    (hash groups with several candidates on a side, left unpaired)"""
    rd, rf, rh = TP.functions_all(RETAIL)
    td, tf, th = TP.functions_all(TU)
    sm = difflib.SequenceMatcher(None, rh, th, autojunk=False)
    equal, changed, new, removed = [], [], [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            equal += [(rf[i], tf[j]) for i, j in zip(range(i1, i2), range(j1, j2))]
        elif tag == 'insert':
            new += tf[j1:j2]
        elif tag == 'delete':
            removed += rf[i1:i2]
        else:
            pairs = pair_run(rd, rf[i1:i2], td, tf[j1:j2])
            changed += [(rf[i1 + a], tf[j1 + b]) for a, b in pairs]
            new += [tf[j] for j in range(j1, j2) if j - j1 not in {b for a, b in pairs}]
            removed += [rf[i] for i in range(i1, i2) if i - i1 not in {a for a, b in pairs}]
    hr = dict(zip((f[0] for f in rf), rh))
    ht = dict(zip((f[0] for f in tf), th))
    rby, tby = collections.defaultdict(list), collections.defaultdict(list)
    for r in removed:
        rby[hr[r[0]]].append(r)
    for t in new:
        tby[ht[t[0]]].append(t)
    moved, ambiguous = [], 0
    for h, ts in tby.items():
        rs = rby.get(h)
        if rs and len(rs) == 1 and len(ts) == 1:
            moved.append((rs[0], ts[0]))
        elif rs:
            ambiguous += len(ts)
    mt, mr = {t[0] for r, t in moved}, {r[0] for r, t in moved}
    new = [t for t in new if t[0] not in mt]
    removed = [r for r in removed if r[0] not in mr]
    via_calls = callsite_pairs(equal + changed + moved, new, removed)
    ct, cr = {t[0] for r, t in via_calls}, {r[0] for r, t in via_calls}
    new = [t for t in new if t[0] not in ct]
    removed = [r for r in removed if r[0] not in cr]
    return rd, rf, td, tf, equal, changed + via_calls, new, removed, sorted(moved, key=lambda p: p[1][0]), ambiguous, \
        {t[0] for r, t in via_calls}


def callsite_pairs(pairs, new, removed, rounds=4):
    """Q49: pair still unpaired functions through the call sites of paired ones. For every pair the ordered bl
    callee lists of both bodies are aligned (difflib on the callee identity: a paired callee is its TU start); where a
    run differs with the same length, an unpaired retail callee (removed) facing an unpaired TU callee (new) is one
    vote. A pair is taken when the votes agree both ways (the retail function always faces that TU function and vice
    versa) and the sizes fit (0.4 .. 2.5) - e.g. TU-changed leaf lookups the TU calls where retail called the old
    one. Returns [(retail (start, end), tu (start, end))]"""
    _, rres = TP.cached_all(RETAIL)
    _, tres = TP.cached_all(TU)
    newd, remd = {t[0]: t for t in new}, {r[0]: r for r in removed}
    r2t = {r[0]: t[0] for r, t in pairs}
    t2r = {t[0]: r[0] for r, t in pairs}
    pr = [(r[0], t[0]) for r, t in pairs]
    out = []
    for _ in range(rounds):
        votes = collections.defaultdict(collections.Counter)
        back = collections.defaultdict(collections.Counter)
        for ra, ta in pr:
            cr = [v for a, k, v in rres.get(ra, ()) if k == 'call']
            ct = [v for a, k, v in tres.get(ta, ()) if k == 'call']
            kr = [r2t.get(v, ('r', v)) for v in cr]
            kt = [v if v in t2r else ('t', v) for v in ct]
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, kr, kt, autojunk=False).get_opcodes():
                if tag == 'replace' and i2 - i1 == j2 - j1:
                    for x, y in zip(cr[i1:i2], ct[j1:j2]):
                        if x in remd and y in newd:
                            votes[x][y] += 1
                            back[y][x] += 1
        got = []
        for x, c in votes.items():
            if len(c) == 1:
                y = next(iter(c))
                if len(back[y]) == 1 and y not in t2r and x not in r2t:
                    sr, st = remd[x][1] - x, newd[y][1] - y
                    if 0.4 <= st / float(max(4, sr)) <= 2.5:
                        got.append((remd[x], newd[y]))
        if not got:
            break
        for r, t in got:
            r2t[r[0]], t2r[t[0]] = t[0], r[0]
        out += got
        pr = [(r[0], t[0]) for r, t in got]       # next round: only the new pairs' call sites
    return out


def read_tsv(path):
    if not os.path.exists(path):
        return []
    lines = open(path, encoding='utf-8-sig').read().splitlines()
    rows = [l.split('\t') for l in lines if l.strip() and not l.startswith('#')]
    head = rows[0]
    return [dict(zip(head, r + [''] * (len(head) - len(r)))) for r in rows[1:]]


def cstring(d, a):
    o = a - BASE
    if o < 0 or o >= len(d) - 4:
        return None
    e = d.find(b'\0', o, o + 96)
    if e < 0 or e - o < 5:
        return None
    s = d[o:e]
    if all(32 <= c < 127 for c in s) and sum(chr(c).isalpha() for c in s) >= 3:
        t = s.decode('ascii')
        if ':\\' in t or '\\' in t or ':/' in t:      # file paths of the Xbox build: not needed, kept out of the repo
            return None
        return t
    return None


NEGATED = re.compile(r'not (yet )?(translated|ported)|untranslated|nicht (übersetzt|portiert)|no port|'
                     r'not in (this build|0\.\d)|stays? (the )?PC\b', re.I)
# sentence starts for the negation scope: after '. ' / '.\n' (not inside 0.6.6 / 0x..), a blank (comment) line, a
# bullet or heading line, a table cell border
SENT_END = re.compile(r'\.(?=\s)|\n[ \t]*(?://+|#+|;+)?[ \t]*\n|\n[ \t]*(?://+|#+)?[ \t]*(?=[*-] |\d+\. |#)|'
                      r'(?<=\s)\|(?=\s)')
RANGE_RE = re.compile(r'(0x82[0-9a-fA-F]{6}) ?(?:\.\.|-|–|—) ?(?:0x)?(82[0-9a-fA-F]{6})\b')
HIT_LINES = collections.defaultdict(list)   # (source label, address) -> the text lines naming it (for --why)
REF_TEXT = {}                                 # path -> committed text (--ref REV)
SWITCH_RE = re.compile(r'\[([A-Za-z][A-Za-z0-9_]*)\] ?`?([A-Z][A-Za-z0-9_]+)')


def harvest(paths, label):
    """[(address, kind tu/retail/unlabeled, source label, negated, end, switch)] from text files; negated = the same
    line says the address is NOT translated / ported (then it only counts as a mention); end = exclusive end of the
    named code (a + 4, or the last address + 4 of a range `0x82a..0x82b` / `0x82a-0x82b`); switch = the first ini
    switch `[Section] Key` on the same line (README / source comment), '' if none"""
    out = []
    for p in paths:
        if p in REF_TEXT:                              # --ref: the committed text instead of the working copy
            t = REF_TEXT[p]
        else:
            try:
                t = open(p, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
        ends = {}
        for m in RANGE_RE.finditer(t):
            a, b = int(m.group(1), 16), int(m.group(2), 16)
            if a <= b < a + 0x2000:
                ends[m.start(1)] = b + 4
        for m in ADDR_RE.finditer(t):
            pre = t[max(0, m.start() - 16):m.start()]
            kind = 'retail' if 'retail' in pre.lower() else ('tu' if re.search(r'\bTU\b', pre) else 'unlabeled')
            ls, le = t.rfind('\n', 0, m.start()) + 1, t.find('\n', m.end())
            line = t[ls:le if le >= 0 else len(t)]
            # negated: the line says so (anywhere), or the sentence the address stands in says so BEFORE the address
            # (Q49: "Not part of the mapping, not ported: ... (TU 0x821ff514 ...)" spans comment lines; "Not in
            # 0.6.6: ..., the step queries (0x823093a0 -> 0x82308850)." - the address is on a later line)
            ss = max((b.end() for b in SENT_END.finditer(t, max(0, m.start() - 700), m.start())),
                     default=max(0, m.start() - 700))
            neg = bool(NEGATED.search(line)) or bool(NEGATED.search(t[ss:m.start()]))
            sw = SWITCH_RE.search(line)
            a = int(m.group(0), 16)
            if len(HIT_LINES[(label(p), a)]) < 4:
                HIT_LINES[(label(p), a)].append(line.strip()[:240])
            out.append((a, kind, label(p), neg, ends.get(m.start(), a + 4),
                        ('[%s] %s' % sw.groups()) if sw else ''))
    return out


# ---- changed blocks inside one function (TU vs retail), TODO N20 stage "partial" (10.11.2026) ----
EXT_OPS = (19, 31, 59, 63)
BLOCK_STATUS = ('covered', 'noport', 'uncovered')   # override rows for one changed block (tu_addr inside it)
NOGAP = ('alloc', 'layout', 'reorder')   # block kinds that do not make a function "partial" (listed, not counted)


def _word(d, a):
    return struct.unpack_from('>I', d, a - BASE)[0]


def _bdisp(w):
    """relative branch displacement of b (op 18) / bc (op 16)"""
    if w >> 26 == 18:
        li = w & 0x03fffffc
        return li - 0x04000000 if li & 0x02000000 else li
    bd = w & 0xfffc
    return bd - 0x10000 if bd & 0x8000 else bd


def _is_frame(w, helper=False):
    """stack-frame bookkeeping: r1-relative load / store (register saves, stwu r1), addi rX,r1,n (frame / local
    buffer address), mr rA,rS; helper=True: the first word of a save / restore helper (r1- or r12-relative store /
    load, __savegprlr / __savefpr / __savevmx families)"""
    op = w >> 26
    if (op in P.LOADSTORE or op in (58, 62)) and (w >> 16) & 31 in ((1, 12) if helper else (1,)):
        return True
    if helper:
        return op == 4 and (w & 0x7f3) in (0x0c3, 0x1c3)       # lvx128 / stvx128 (vector register saves)
    if op == 14 and (w >> 16) & 31 == 1:
        return True
    if op == 14 and (w >> 16) & 31 == 0 and (w >> 21) & 31 in (0, 12) and 0xfc00 <= (w & 0xffff) <= 0xfff0 and \
            not (w & 0xf):
        return True                                # li r0 / r12, -n: offset of a vector register save slot
    if op == 4 and (w >> 16) & 31 == 1 and (w & 0x7f3) in (0x0c3, 0x1c3):
        return True                                # lvx128 / stvx128 vN, r1, r0 / r12: vector register save
    return op == 31 and (w >> 1) & 0x3ff == 444 and (w >> 21) & 31 == (w >> 11) & 31


RA_WRITERS = {20, 21, 23, 24, 25, 26, 27, 28, 29, 30}            # rlwimi .. rld*: the result goes to rA
X_RA_WRITERS = {24, 26, 27, 28, 60, 124, 284, 316, 412, 444, 476, 536, 539, 792, 794, 824, 826, 922, 954, 986}


def gpr_writes(w):
    """general registers an instruction writes (conservative: unknown forms count as writing rD)"""
    op, rd, ra = w >> 26, (w >> 21) & 31, (w >> 16) & 31
    xo = (w >> 1) & 0x3ff
    if op in RA_WRITERS or (op == 31 and xo in X_RA_WRITERS):
        return (ra,)
    if op == 46:                                       # lmw
        return tuple(range(rd, 32))
    if op in (16, 18, 19, 36, 37, 38, 39, 44, 45, 47, 48, 50, 52, 53, 54, 55, 62, 10, 11, 4, 5, 6, 59, 63):
        return (ra,) if op in (37, 39, 45, 49, 51, 53, 55) else ()
    if op == 31 and xo in (0, 32, 151, 183, 215, 247, 407, 439, 663, 695, 727, 759, 918, 662, 467, 144):
        return ()
    return (rd,)


def block_tokens(d, fs, fe, reloc, callee_id, hoisted):
    """one token per instruction: relocation-free (b / bl to a function -> callee identity, bc / in-function b ->
    displacement masked, lis / address halves (lo halves found by ppc_xrefs) -> immediate masked), else the raw word.
    Hoisted zero: `mr rX,Z` while the last write of Z in address order was `li Z,0` -> token `li rX,0` (the TU
    compiler keeps 0 in a register where retail wrote `li rX,0` at each use); hoisted[0] = True when that happened"""
    out = []
    zero = set()
    for a in range(fs, fe, 4):
        w = _word(d, a)
        op = w >> 26
        is_li0 = op == 14 and (w >> 16) & 31 == 0 and w & 0xffff == 0
        is_mr = op == 31 and (w >> 1) & 0x3ff == 444 and (w >> 21) & 31 == (w >> 11) & 31
        tok = None
        if is_mr and (w >> 21) & 31 in zero:
            tok = ('w', 0x38000000 | (((w >> 16) & 31) << 21))
            hoisted[0] = True
        if is_li0:
            zero.add((w >> 21) & 31)
        else:
            zero.difference_update(gpr_writes(w))
        if op == 18 and (w & 1):                       # a call clobbers the volatile registers r0 / r3..r12
            zero.difference_update(range(0, 13))
        if tok is not None:
            out.append(tok)
        elif fs <= w < fe and not (w & 3):               # jump table entry inside the code (absolute in-function address)
            out.append(('tab',))
        elif op == 18 and not (w & 2):
            t = (a + _bdisp(w)) & 0xffffffff
            if not (fs <= t < fe) and 0 <= t - BASE <= len(d) - 4 and _is_frame(_word(d, t), True):
                out.append(('frame', w & 3))            # __savegprlr_N / __restgprlr_N (entry = register count)
            elif (w & 1) and 0 <= t - BASE <= len(d) - 4 and _word(d, t) == 0x4e800020:
                out.append(('stub',))                   # call of an empty function (debug print stub: blr only)
            else:
                out.append(('b', w & 3, 'in') if (fs <= t < fe and not (w & 1)) else ('b', w & 3, callee_id(t)))
        elif op == 16:
            out.append(('bc', w & 0xffff0003))
        elif (op == 15 and (w >> 16) & 31 == 0) or a in reloc:
            out.append(('w', w & 0xffff0000))
        else:
            out.append(('w', w))
    return out


def skeleton(tok, w):
    """the token without register numbers (alignment key): D-form = opcode + immediate (r1-relative: opcode only),
    X / XO / A-form = opcode + extended opcode, VMX128 = opcode + form bits"""
    if tok[0] != 'w':
        return tok
    w = tok[1]
    op = w >> 26
    if op in EXT_OPS:
        return ('s', op, (w >> 1) & 0x3ff, w & 1)
    if op == 4:
        return ('s', 4, w & 0x7f3)
    if op in (5, 6):
        return ('s', op, w & 0x3d0)
    if (w >> 16) & 31 == 1 and (op in (14, 58, 62) or op in P.LOADSTORE):
        return ('s', op, 'sp')
    return ('s', op, w & 0xffff)


def changed_blocks(rd, rs, re_, td, ts, te, rreloc, treloc, rcallee, tcallee, gap=2):
    """[(tu_start, tu_end, retail_start, retail_end, kind)] where the TU body differs from the retail body.
    Instruction alignment with difflib on block_tokens; equal pairs whose in-function branch (b / bc) lands on
    instructions that do not pair up count as changed too; runs closer than `gap` instructions merge.
    kind (see pair_kind): 'alloc' (same length and opcodes, only register numbers / stack-frame offsets differ -
    register allocation, very likely no behaviour change, not proven), 'layout' (as alloc, plus field displacements
    of loads / stores / addi off a pointer register moved - the TU structure layout changed, the PC keeps its own),
    'reorder' (after dropping frame bookkeeping / hoisted zeros / empty-stub calls the same instructions in another
    order - scheduling; immediates other than field displacements must match), 'operands' (same length and opcodes,
    an immediate / branch condition / callee differs), 'deleted' (retail code with no TU counterpart), else 'code'."""
    hoisted = [False]
    rt = block_tokens(rd, rs, re_, rreloc, rcallee, hoisted)
    tt = block_tokens(td, ts, te, treloc, tcallee, hoisted)
    hoist = hoisted[0]                             # a side keeps 0 in a register somewhere (mr rX,Z seen)

    def droppable(tok, w):                         # frame bookkeeping; zero materialisation only with hoisting
        return tok[0] == 'frame' or _is_frame(w) or (hoist and tok == ('w', w) and w >> 26 == 14 and
                                                     (w >> 16) & 31 == 0 and w & 0xffff == 0)
    rsk = [skeleton(t, _word(rd, rs + 4 * i)) for i, t in enumerate(rt)]
    tsk = [skeleton(t, _word(td, ts + 4 * j)) for j, t in enumerate(tt)]
    sm = difflib.SequenceMatcher(None, rsk, tsk, autojunk=False)   # align on the register-free skeleton
    ops = sm.get_opcodes()
    pair = {}
    runs = []
    for tag, i1, i2, j1, j2 in ops:
        if tag == 'equal':
            pair.update(zip(range(i1, i2), range(j1, j2)))
            k = 0
            while k < i2 - i1:                     # same skeleton, other registers: alloc runs
                if rt[i1 + k] != tt[j1 + k]:
                    k0 = k
                    while k < i2 - i1 and rt[i1 + k] != tt[j1 + k]:
                        k += 1
                    runs.append((j1 + k0, j1 + k, i1 + k0, i1 + k))
                else:
                    k += 1
        else:
            runs.append((j1, j2, i1, i2))
    nr, nt = len(rt), len(tt)
    for i, j in pair.items():                      # branches inside equal code that now land elsewhere
        if rt[i][0] == 'bc' or (rt[i][0] == 'b' and rt[i][2] == 'in') or rt[i][0] == 'tab':
            if rt[i][0] == 'tab':
                ti, tj = (_word(rd, rs + 4 * i) - rs) // 4, (_word(td, ts + 4 * j) - ts) // 4
            else:
                ti = i + _bdisp(_word(rd, rs + 4 * i)) // 4
                tj = j + _bdisp(_word(td, ts + 4 * j)) // 4
            if 0 <= ti < nr and 0 <= tj < nt and ti in pair and pair[ti] != tj:
                runs.append((j, j + 1, i, i + 1))
    runs.sort()
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] <= gap and r[2] - merged[-1][3] <= gap:
            m = merged[-1]
            merged[-1] = (m[0], max(m[1], r[1]), min(m[2], r[2]), max(m[3], r[3]))
        else:
            merged.append(r)
    def strip(ids, toks, d, base):
        """drop frame bookkeeping, hoisted-zero li, and empty-stub calls with their argument setup (the contiguous
        instructions right before the call that only write r3..r12)"""
        keep = [k for k in ids if not droppable(toks[k], _word(d, base + 4 * k))]
        drop = set()
        for n, k in enumerate(keep):
            if toks[k] == ('stub',):
                drop.add(k)
                m = n - 1
                while m >= 0 and n - m <= 6 and toks[keep[m]][0] == 'w':
                    wr = gpr_writes(_word(d, base + 4 * keep[m]))
                    if not wr or not all(3 <= r <= 12 for r in wr):
                        break
                    drop.add(keep[m])
                    m -= 1
        return [k for k in keep if k not in drop]

    def loose(tok):
        """order-free key: opcode + extended opcode / immediate; field displacements and branch targets dropped"""
        if tok[0] == 'bc':
            return ('bc',)
        if tok[0] != 'w':
            return tok
        w = tok[1]
        op, ra = w >> 26, (w >> 16) & 31
        if op in EXT_OPS:
            return (op, (w >> 1) & 0x3ff)
        if op == 4:
            return (4, w & 0x7f3)
        if op in (5, 6):
            return (op, w & 0x3d0)
        if ra != 0 and (op in P.LOADSTORE or op in (58, 62) or op == 14):
            return (op, 'field')
        return (op, w & 0xffff)

    out = []
    for j1, j2, i1, i2 in merged:
        ri, tj = list(range(i1, i2)), list(range(j1, j2))
        if len(ri) != len(tj) or ('stub',) in [rt[i] for i in ri] + [tt[j] for j in tj]:
            ri, tj = strip(ri, rt, rd, rs), strip(tj, tt, td, ts)
        kind = 'code'
        if len(ri) == len(tj):
            kinds = {pair_kind(_word(rd, rs + 4 * i), _word(td, ts + 4 * j), rt[i], tt[j]) for i, j in zip(ri, tj)}
            kind = 'code' if 'code' in kinds else ('operands' if 'operands' in kinds else (
                'layout' if 'layout' in kinds else 'alloc'))
            if kind == 'code' and collections.Counter(loose(rt[i]) for i in ri) == \
                    collections.Counter(loose(tt[j]) for j in tj):
                kind = 'reorder'                   # the same instructions in another order (scheduling)
        if kind == 'code' and j1 == j2:
            kind = 'deleted'
        out.append((ts + 4 * j1, ts + 4 * j2, rs + 4 * i1, rs + 4 * i2, kind))
    return out


def pair_kind(wr, wt, tokr, tokt):
    """one retail / TU instruction pair at the same place in a block: 'same' (equal after relocation masking),
    'alloc' (same opcode, only register numbers differ, or a stack-frame offset: rA = r1 / stwu r1), 'layout' (a
    field displacement off a pointer register differs), 'operands' (an immediate, shift, condition or callee
    differs), 'code' (another opcode)"""
    if tokr == tokt:
        return 'same'
    if _is_frame(wr) and _is_frame(wt):
        return 'alloc'                            # both stack-frame bookkeeping (another frame size / save slot)
    op = wt >> 26
    if op != wr >> 26 or (op in EXT_OPS and ((wr >> 1) & 0x3ff) != ((wt >> 1) & 0x3ff)):
        return 'code'
    if op == 4 and (wr & 0x7f3) != (wt & 0x7f3):
        return 'code'
    if op in (16, 18, 19):                       # condition / target / callee of a branch
        return 'operands'
    x = wr ^ wt
    if op in EXT_OPS:
        return 'alloc' if not (x & 0x7ff) else 'operands'
    if op == 4:
        return 'alloc' if not (x & 0x7f3) else 'operands'
    if op in (5, 6):                              # VMX128: register bits are spread over the word
        return 'alloc' if not (x & 0x3d0) else 'operands'
    if not (x & 0xffff):
        return 'alloc'
    ra_r, ra_t = (wr >> 16) & 31, (wt >> 16) & 31
    if ra_r == 1 and ra_t == 1 and (op in (14, 58, 62) or op in P.LOADSTORE):
        return 'alloc'                            # r1-relative: stack frame layout
    if ra_r not in (0, 1) and ra_t not in (0, 1):
        if op in P.LOADSTORE or op in (58, 62):
            return 'layout'                       # field displacement moved (the TU structure grew / shifted)
        sr, st = wr & 0xffff, wt & 0xffff
        if op == 14 and min(sr, st) >= 0x40 and max(sr, st) < 0x8000:
            return 'layout'                       # field address addi rX,rY,off (offsets >= 0x40 only)
    return 'operands'


def block_hint(td, b, name_of_tu, items):
    """short evidence of what TU code in a block does: callees (prototype names where known), compare immediates,
    li constants (message ids / types), built global addresses - read from the TU instructions only"""
    tb, te = b[0], b[1]
    calls, cmps, lis, glob_ = [], [], [], []
    for a in range(tb, te, 4):
        w = _word(td, a)
        op, imm = w >> 26, w & 0xffff
        simm = imm - 0x10000 if imm & 0x8000 else imm
        if op == 18 and (w & 3) == 1:
            t = (a + _bdisp(w)) & 0xffffffff
            if 0 <= t - BASE <= len(td) - 4 and _is_frame(_word(td, t), True):
                continue                               # register save / restore helper
            n = name_of_tu(t) or '0x%08x' % t
            if n not in calls:
                calls.append(n)
        elif op in (10, 11):
            v = ('cmp 0x%x' % imm) if op == 10 else ('cmp %d' % simm)
            if v not in cmps:
                cmps.append(v)
        elif op == 14 and (w >> 16) & 31 == 0 and abs(simm) >= 2:
            v = 'li 0x%x' % (simm & 0xffffffff if simm >= 0 else simm & 0xffff)
            if v not in lis:
                lis.append(v)
    for a, k, v in items:
        if tb <= a < te and k == 'addr' and '0x%08x' % v not in glob_:
            glob_.append('0x%08x' % v)
    parts = []
    if calls:
        parts.append('calls ' + ', '.join(calls[:3]) + (' +%d' % (len(calls) - 3) if len(calls) > 3 else ''))
    if cmps:
        parts.append(', '.join(cmps[:3]))
    if lis:
        parts.append(', '.join(lis[:3]))
    if glob_:
        parts.append('addr ' + ', '.join(glob_[:2]))
    return '; '.join(parts)


_CS = []


def dis(d, a):
    """one instruction as text (capstone, VMX128 forms via ppc_dis128); branch targets are absolute addresses"""
    import ppc_dis128 as D
    if not _CS:
        import capstone
        _CS.append(capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN))
    w = _word(d, a)
    text = D.vmx128(w) if (w >> 26) in (5, 6) or ((w >> 26) == 4 and (w & 0x7f3) in D.LS128) else None
    if text is None:
        ins = list(_CS[0].disasm(struct.pack('>I', w), a, 1))
        text = ('%s %s' % (ins[0].mnemonic, ins[0].op_str)) if ins else (D.vmx128(w) or '.long 0x%08x' % w)
    return text


def show_block(rd, td, b, rp, fs, rpe, fe, name_of_tu, td_strings=(), ctx=2):
    """retail and TU instructions of one changed block side by side (ctx instructions of equal code around it)"""
    tb, te, rb, re2, kind = b
    ra = [(a, dis(rd, a)) for a in range(max(rp, rb - 4 * ctx), min(rpe, re2 + 4 * ctx), 4)]
    ta = [(a, dis(td, a)) for a in range(max(fs, tb - 4 * ctx), min(fe, te + 4 * ctx), 4)]
    for k in range(max(len(ra), len(ta))):
        l = ('%s%08x  %-34s' % ('*' if rb <= ra[k][0] < re2 else ' ', ra[k][0], ra[k][1][:34])) if k < len(ra) \
            else ' ' * 45
        r = ('%s%08x  %s' % ('*' if tb <= ta[k][0] < te else ' ', ta[k][0], ta[k][1])) if k < len(ta) else ''
        if k < len(ta) and ta[k][1].startswith('bl '):
            try:
                n = name_of_tu(int(ta[k][1].split()[1], 16))
            except ValueError:
                n = ''
            r += ('   ; ' + n) if n else ''
        print('    ' + l + ' | ' + r)


def block_hits(blk, hits, fs, rp):
    """hits [(a, kind, src, neg, end, switch)] that name code inside the block; a single address equal to the function
    start (TU or retail) names the whole function, not a block, and is skipped"""
    tb, tend, rb, rend, kind = blk
    lo, hi = (tb - 4, tb + 4) if tb == tend else (tb, tend)
    out = []
    for a, k, src, neg, e, sw in hits:
        if e == a + 4 and (a == fs or (rp is not None and a == rp)):
            continue
        if k == 'retail':
            if rb < rend and a < rend and e > rb:
                out.append((a, src, sw, e))
        elif a < hi and e > lo:
            out.append((a, src, sw, e))
    return out


PLUGIN_TOPIC = {'TruShadowCombat': 'enemy / combat', 'TruShadowPower': 'player / chart', 'TruRockVein':
                'markup / navigation', 'TruShadowHud': 'ui / hud', 'TruDlc2Player': 'player / chart',
                'TruDoppelganger': 'player / chart'}
WEAK = ('', '2nd-ring neighbours (weak)', 'callers / callees', 'strings', 'data marks')


def main(argv):
    out = None                                     # Q43: the TSV is written only with --out (as the help says)
    summ = None
    if '--out' in argv:
        out = argv[argv.index('--out') + 1]
    if '--summary' in argv:
        summ = argv[argv.index('--summary') + 1]
    rd, rf, td, tf, equal, changed, new, removed, moved, ambiguous, via_calls = align()
    stubs = {t[0] for t in new if t[1] - t[0] == 4 and _word(td, t[0]) == TP.BLR}
    new = [t for t in new if t[0] not in stubs]    # empty functions (blr only, debug-print stubs): nothing to port
    moved_t = {t[0] for r, t in moved}
    changed = changed + moved                      # moved pairs are diffed like changed ones (class 'moved')
    tu_starts = [f[0] for f in tf]
    tu_end = dict(tf)
    rt_starts = [f[0] for f in rf]
    rt_end = dict(rf)
    # forced pairs from the override file (column retail: a finding / plugin names the retail partner)
    forced = {}
    for r in read_tsv(OVR):
        if r.get('retail'):
            try:
                ta, ra = int(r['tu_addr'], 16), int(r['retail'], 16)
            except ValueError:
                continue
            if ta in tu_end and ra in rt_end:
                forced[ta] = ra
            else:
                print('override retail pair 0x%08x -> 0x%08x: not two function starts - ignored' % (ta, ra))
    if forced:
        fr = set(forced.values())
        keep = []
        for r, t in changed:
            if t[0] in forced or r[0] in fr:
                if t[0] not in forced:
                    new.append(t)
                if r[0] not in fr:
                    removed.append(r)
            else:
                keep.append((r, t))
        equal = [(r, t) for r, t in equal if t[0] not in forced and r[0] not in fr]
        new = [t for t in new if t[0] not in forced]
        removed = [r for r in removed if r[0] not in fr]
        changed = keep + [((ra, rt_end[ra]), (ta, tu_end[ta])) for ta, ra in sorted(forced.items())]
    tu2rt = {t[0]: r[0] for r, t in equal + changed}
    rt2tu = {r[0]: t[0] for r, t in equal + changed}
    cls = {t[0]: ('moved' if t[0] in moved_t and t[0] not in forced else 'changed') for r, t in changed}
    cls.update({t[0]: 'new' for t in new})
    xmap = {}
    for r in read_tsv(XMAP):
        try:
            xmap[int(r['xbox_retail'], 16)] = (r['pc'], r['tier'])
        except (KeyError, ValueError):
            pass
    proto = {}
    for r in read_tsv(PROTO):
        if r.get('retail'):
            try:
                proto.setdefault(int(r['retail'], 16), (r['name'], r['obj']))
            except ValueError:
                pass
    funcs, res = TP.cached_all(TU)                 # Q49: with the functions without .pdata
    nopdata = TP.nopdata_starts(TU)
    callers = collections.defaultdict(set)
    for fs, items in res.items():
        for a, k, v in items:
            if k == 'call':
                callers[v].add(fs)

    def name_of_tu(fs):
        rp = tu2rt.get(fs)
        return proto.get(rp, ('', ''))[0] if rp else ''

    def obj_of_tu(fs):
        rp = tu2rt.get(fs)
        return proto.get(rp, ('', ''))[1] if rp else ''

    def owner(starts, ends, a):
        i = __import__('bisect').bisect_right(starts, a) - 1
        if i >= 0 and starts[i] <= a < ends[starts[i]]:
            return starts[i]
        return None

    # where our plugins / findings name addresses
    plugin_files = []
    if '--ref' in argv:                            # plugin sources + ENGINE.md as committed at REV (git, read-only)
        import subprocess
        rev = argv[argv.index('--ref') + 1]
        git = lambda *a: subprocess.run(('git', '-C', ROOT) + a, capture_output=True, check=True).stdout
        for rel in git('ls-tree', '-r', '--name-only', rev, '--', 'src/asi', 'docs/ENGINE.md').decode().splitlines():
            if 'TruGuard' in rel or 'third_party' in rel:
                continue
            if rel == 'docs/ENGINE.md' or (rel.count('/') == 3 and rel.lower().endswith(
                    ('.cpp', '.h', '.md', '.ini', '.txt'))):
                p = os.path.join(ROOT, *rel.split('/'))
                REF_TEXT[p] = git('show', '%s:%s' % (rev, rel)).decode('utf-8', errors='replace')
                if rel != 'docs/ENGINE.md':
                    plugin_files.append(p)
    else:
        for p in glob.glob(os.path.join(ROOT, 'src', 'asi', '*', '*')):
            if 'TruGuard' in p or 'third_party' in p:
                continue
            if p.lower().endswith(('.cpp', '.h', '.md', '.ini', '.txt')):
                plugin_files.append(p)
    hits_plugin = harvest(plugin_files, lambda p: os.path.basename(os.path.dirname(p)))
    doc_files = [os.path.join(ROOT, 'docs', 'ENGINE.md')] + sorted(glob.glob(os.path.join(WS, 'docs', 'Befund-*.md')))
    hits_doc = harvest(doc_files, lambda p: os.path.basename(p))
    plug_by_fn = collections.defaultdict(set)
    doc_by_fn = collections.defaultdict(set)
    hits_doc += [(a, k, 'plugin ' + s + ' (not ported)', n, e, sw) for a, k, s, n, e, sw in hits_plugin if n]
    hits_plugin = [h for h in hits_plugin if not h[3]]
    plug_hits_by_fn = collections.defaultdict(list)
    why = set()
    if '--why' in argv:
        for x in argv[argv.index('--why') + 1].split(','):
            f = owner(tu_starts, tu_end, int(x, 16))
            if f is not None:
                why.add(f)
    show = set()
    if '--show' in argv:
        for x in argv[argv.index('--show') + 1].split(','):
            f = owner(tu_starts, tu_end, int(x, 16))
            if f is not None:
                show.add(f)
    for hits, target in ((hits_plugin, plug_by_fn), (hits_doc, doc_by_fn)):
        for a, kind, src, neg, e, sw in hits:
            if why:
                fw = owner(tu_starts, tu_end, a) if kind != 'retail' else None
                rw = owner(rt_starts, rt_end, a) if kind == 'retail' else None
                w_ = fw if fw in why else (rt2tu.get(rw) if rw is not None and rt2tu.get(rw) in why else None)
                if w_ is not None:
                    print('why 0x%08x: 0x%08x (%s) from %s%s' % (w_, a, kind, src, ''.join(
                        '\n      | ' + l for l in HIT_LINES.get((src, a), [])[:2]) if target is plug_by_fn else ''))
            fn = None
            if kind in ('tu', 'unlabeled'):          # unlabeled addresses are read as TU addresses only
                fn = owner(tu_starts, tu_end, a)
            elif kind == 'retail':
                rfn = owner(rt_starts, rt_end, a)
                if rfn is not None:
                    fn = rt2tu.get(rfn)
                    # Q49: a retail address does not name a TU function across an unreliable pair (size ratio > 2:
                    # a split / inlined function or a positional guess inside a rewritten run, e.g. retail getters
                    # 0x821666c0 / 0x821669a0, which the TU inlined)
                    if fn is not None and max(tu_end[fn] - fn, rt_end[rfn] - rfn) > \
                            2 * min(tu_end[fn] - fn, rt_end[rfn] - rfn):
                        fn = None
            if fn is not None and fn in cls:
                target[fn].add(src)
                if target is plug_by_fn:
                    plug_hits_by_fn[fn].append((a, kind, src, neg, e, sw))
    ovr, ovr_blk = {}, collections.defaultdict(list)
    for r in read_tsv(OVR):
        try:
            a = int(r['tu_addr'], 16)
        except (KeyError, ValueError):
            continue
        fn = owner(tu_starts, tu_end, a)          # any address inside the function names it
        if fn is None:
            print('override 0x%08x: not inside a TU function - ignored' % a)
        elif r.get('status') in BLOCK_STATUS:     # block rows: the changed block that contains tu_addr
            ovr_blk[fn].append((a, r))
        else:
            ovr[fn] = r

    # changed blocks of every changed function (relocation-free instruction diff, see changed_blocks)
    _, rres = TP.cached_all(RETAIL)
    rreloc = {a for items in rres.values() for a, k, v in items if k == 'addr'}
    treloc = {a for items in res.values() for a, k, v in items if k == 'addr'}
    rhash = dict(zip(rt_starts, (XD.norm_hash(rd, s, e) for s, e in rf)))
    thash = dict(zip(tu_starts, (XD.norm_hash(td, s, e) for s, e in tf)))
    rcallee = lambda t: rt2tu[t] if t in rt2tu else rhash.get(t, 'x')
    tcallee = lambda t: t if t in tu2rt else thash.get(t, 'x')
    blocks = {}
    for fs in cls:
        if cls[fs] == 'new':
            blocks[fs] = [(fs, tu_end[fs], 0, 0, 'new function')]
        else:
            rp = tu2rt[fs]
            blocks[fs] = changed_blocks(rd, rp, rt_end[rp], td, fs, tu_end[fs], rreloc, treloc, rcallee, tcallee)
    moved_same = [fs for fs in cls if cls[fs] == 'moved' and not blocks[fs]]
    calls_same = [fs for fs in cls if fs in via_calls and not blocks[fs]]
    for fs in moved_same + calls_same:             # paired late and no changed block at all: not a TU change
        del cls[fs]

    rows = []
    for fs in sorted(cls):
        fe = tu_end[fs]
        rp = tu2rt.get(fs)
        pc, tier = xmap.get(rp, ('', '')) if rp else ('', '')
        pname, pobj = proto.get(rp, ('', '')) if rp else ('', '')
        items = res.get(fs, [])
        callees = sorted({v for a, k, v in items if k == 'call'})
        built = sorted({v for a, k, v in items if k == 'addr'})
        strs = []
        for v in built:
            s = cstring(td, v)
            if s and s not in strs:
                strs.append(s)
        marks = []
        for a in range(fs, fe, 4):
            w = struct.unpack_from('>I', td, a - BASE)[0]
            if (w >> 26) in P.LOADSTORE and (w & 0xffff) in MARKS and MARKS[w & 0xffff] not in marks:
                marks.append(MARKS[w & 0xffff])
        marks += [GLOBAL_MARKS[v] for v in built if v in GLOBAL_MARKS and GLOBAL_MARKS[v] not in marks]
        neigh = [n for n in (name_of_tu(c) for c in callees) if n] + \
                [n for n in (name_of_tu(c) for c in callers.get(fs, ())) if n]
        nobj = [o for o in (obj_of_tu(c) for c in list(callees) + list(callers.get(fs, ()))) if o]
        topic, tb = '', ''
        if pname or pobj:
            topic, tb = topic_of(pobj + ' ' + pname), 'proto name'
            if not topic and pobj and is_platform(pobj):
                topic, tb = 'xbox platform library', 'proto object'
        if not topic and neigh and all(n.startswith('FMOD::') for n in neigh):
            topic, tb = 'xbox platform library', 'callers / callees (FMOD only)'
        if not topic and (neigh or nobj):
            votes = collections.Counter(t for t in (topic_of(x) for x in neigh + nobj) if t)
            if votes:
                topic, tb = votes.most_common(1)[0][0], 'callers / callees'
            elif nobj and all(is_platform(o) for o in nobj):
                topic, tb = 'xbox platform library', 'callers / callees'
        if not topic:
            ring = set()
            for c in list(callees) + list(callers.get(fs, ())):
                ring.update(v for a, k, v in res.get(c, []) if k == 'call')
                ring.update(callers.get(c, ()))
            ring.discard(fs)
            r2 = [x for x in ([name_of_tu(c) for c in ring] + [obj_of_tu(c) for c in ring]) if x]
            votes = collections.Counter(t for t in (topic_of(x) for x in r2) if t)
            if votes and votes.most_common(1)[0][1] >= 2:
                topic, tb = votes.most_common(1)[0][0], '2nd-ring neighbours (weak)'
        if not topic and strs:
            t = topic_of(' '.join(strs))
            if t:
                topic, tb = t, 'strings'
        if not topic and marks:
            topic, tb = ('player / chart' if any('doppel' in m or 'meter' in m or 'global' in m for m in marks)
                         else ''), 'data marks'
        if not topic:
            topic, tb = '?', ''
        # per changed block: covered (a plugin names code inside it / block override), noport (block override), open
        bstate = []
        for b in blocks[fs]:
            if b[4] == 'new function':                 # no retail body to diff: any plugin address covers it
                ev = [(a, s, sw, e) for a, k, s, n, e, sw in plug_hits_by_fn.get(fs, [])]
            else:
                ev = block_hits(b, plug_hits_by_fn.get(fs, []), fs, rp)
            evs = sorted({'%s%s 0x%08x' % (s, (' ' + sw) if sw else '', a) for a, s, sw, e in ev})
            st_b = 'covered' if evs else 'open'
            if evs and b[4] != 'new function' and b[1] - b[0] > 128 and len({a for a, s, sw, e in ev}) <= 1 and \
                    all(e == a + 4 for a, s, sw, e in ev):
                evs.insert(0, 'WEAK (one address for %d B)' % (b[1] - b[0]))   # covered, but thinly
            lo, hi = (b[0] - 4, b[0] + 4) if b[0] == b[1] else (b[0], b[1])
            for a, r in ovr_blk.get(fs, ()):
                if lo <= a < hi:
                    st_b = {'covered': 'covered', 'noport': 'noport'}.get(r['status'], 'open')
                    if st_b == 'open':                 # 'uncovered': a plugin names it, but does not translate it
                        evs = []
                    evs.append('override %s%s: %s' % (r['status'], (' ' + r['plugin']) if r.get('plugin') else '',
                                                      r.get('note', '')[:80]))
            bstate.append((b, st_b, evs))
        ob_plugins = sorted({r['plugin'] for a, r in ovr_blk.get(fs, ()) if r['status'] == 'covered' and
                             r.get('plugin')})
        status, basis, plugin, note = 'open', 'heuristic', '', ''
        if plug_by_fn.get(fs) or ob_plugins:
            plugs = sorted(set(plug_by_fn.get(fs, ())) | set(ob_plugins))
            gaps = [x for x in bstate if x[1] == 'open' and x[0][4] not in NOGAP]
            status, basis, plugin = ('partial' if gaps else 'ported'), 'doc', ','.join(plugs)
            if cls[fs] == 'new':
                basis = 'doc (new function: named by a plugin, body not diffed)'
            pt = [PLUGIN_TOPIC[p] for p in plugs if p in PLUGIN_TOPIC]
            if pt and tb in WEAK:
                topic, tb = pt[0], 'plugin that ports it'
        elif topic == 'xbox platform library' or (pobj and is_platform(pobj)):
            status, basis, note = 'irrelevant', 'heuristic', 'Xbox platform library (%s; the PC has its own)' % (
                pobj or tb)
        if fs in ovr:
            o = ovr[fs]
            status = o.get('status') or status
            basis = o.get('basis') or basis
            plugin = o.get('plugin') or plugin
            note = o.get('note') or note
            if o.get('pc'):                            # PC partner from a finding beats the map
                pc, tier = o['pc'], 'override (map: %s %s)' % (pc or '-', tier or '-')
            if o.get('status') in ('ported', 'explained', 'irrelevant'):   # hand check: the whole function is done
                bstate = [(b, 'override' if s == 'open' else s, e) for b, s, e in bstate]

        def bfmt(b):
            tb_, te_, rb_, re2, k = b
            if tb_ == te_:
                return '@0x%08x deleted (retail 0x%08x..0x%08x %dB)' % (tb_, rb_, re2 - 4, re2 - rb_)
            return '0x%08x..0x%08x %s %dB' % (tb_, te_ - 4, k, te_ - tb_)
        if fs in why or fs in show:
            print('== 0x%08x %s %s (retail %s, pc %s %s) %s' % (fs, cls[fs], pname, ('0x%08x' % rp) if rp else '-',
                                                              pc or '-', tier or '-', status))
            for b, s, e in bstate:
                print('block %-60s %-8s %s' % (bfmt(b), s, '; '.join(e) or (
                    '{%s}' % block_hint(td, b, name_of_tu, items) if b[0] < b[1] else '')))
                if fs in show and b[4] != 'new function' and (s == 'open' and b[4] not in NOGAP or '--all' in argv):
                    show_block(rd, td, b, rp, fs, rt_end[rp], tu_end[fs], name_of_tu, td_strings=strs)
        uo = [b for b, s, e in bstate if s == 'open' and b[4] not in NOGAP]
        na = collections.Counter(b[4] for b, s, e in bstate if s == 'open' and b[4] in NOGAP)
        unc = []
        for b in uo:
            h = block_hint(td, b, name_of_tu, items) if b[0] < b[1] else ''
            unc.append(bfmt(b) + (' {%s}' % h if h else ''))
        cov = ['%s: %s' % (bfmt(b), '; '.join(e[:3])) for b, s, e in bstate if s != 'open' and e]
        blk_cols = ['%d' % len(bstate), '%d' % len(uo), '%d' % sum(b[1] - b[0] for b in uo),
                    ' | '.join(unc[:12]) + (' | +%d more' % (len(unc) - 12) if len(unc) > 12 else '') +
                    (' (+%s)' % ', '.join('%d %s' % (na[k], k) for k in NOGAP if na[k]) if na else ''),
                    ' | '.join(cov[:8]) + (' | +%d more' % (len(cov) - 8) if len(cov) > 8 else '')]
        if fs in nopdata:
            note = ((note + '; ') if note else '') + 'no .pdata (bl target, end found by scan)'
        if fs in via_calls:
            note = ((note + '; ') if note else '') + 'retail partner from the call sites of paired functions (Q49)'
        if rp and max(fe - fs, rt_end[rp] - rp) > 2 * min(fe - fs, rt_end[rp] - rp):
            note = ((note + '; ') if note else '') + 'size ratio TU %d B / retail %d B: split function or wrong ' \
                'pairing - blocks unreliable' % (fe - fs, rt_end[rp] - rp)
        rows.append([
            '0x%08x' % fs, cls[fs], str(fe - fs), ('0x%08x' % rp) if rp else '',
            str(rt_end[rp] - rp) if rp else '', pc, tier, pname, pobj, topic, tb, '; '.join(marks),
            ' | '.join(s[:40] for s in strs[:3]), ', '.join(sorted(set(neigh))[:4]), status, plugin, basis,
            ', '.join(sorted(doc_by_fn.get(fs, ())))[:200], note] + blk_cols)
    head = ['tu_addr', 'class', 'size', 'retail', 'retail_size', 'pc', 'pc_tier', 'proto_name', 'proto_obj', 'topic',
            'topic_basis', 'marks', 'strings', 'named_neighbours', 'status', 'plugin', 'basis', 'refs', 'note',
            'blocks', 'blocks_open', 'bytes_open', 'uncovered_blocks', 'covered_blocks']
    if (show or why) and out is None:
        return 0                                   # inspection run: print only, no TSV, no summary
    if out is not None:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\t'.join(head) + '\n')
            for r in rows:
                f.write('\t'.join(c.replace('\t', ' ').replace('\n', ' ') for c in r) + '\n')

    size = lambda r: int(r[2])
    lines = ['TU coverage (retail -> TU): equal %d, changed %d, new %d, removed %d; listed %d (changed + moved + new), '
             '%d B' % (len(equal), len(changed) - len(moved), len(new), len(removed), len(rows), sum(map(size, rows))),
             'moved (new TU / removed retail with an equal unique body hash, Q49): %d pairs, %d without any changed '
             'block (not listed), %d listed as class moved; %d new TU functions share a hash with several candidates '
             '(left unpaired)' % (len(moved), len(moved_same), sum(1 for r in rows if r[1] == 'moved'), ambiguous),
             'functions without .pdata (bl targets, Q49): TU %d / retail %d added; listed %d; empty new functions '
             '(blr only) not listed: %d' % (len(nopdata), len(TP.nopdata_starts(RETAIL)),
                                            sum(1 for r in rows if int(r[0], 16) in nopdata), len(stubs)),
             'paired through call sites of paired functions (Q49): %d (%d without any changed block, not listed; '
             'listed %d)' % (len(via_calls), len(calls_same), sum(1 for r in rows if int(r[0], 16) in via_calls))]
    st = collections.Counter(r[14] for r in rows)
    sb = collections.Counter()
    for r in rows:
        sb[r[14]] += size(r)
    lines.append('status: ' + ', '.join('%s %d (%d B)' % (k, st[k], sb[k]) for k in ('ported', 'partial', 'explained',
                                                                                     'irrelevant', 'open')))
    lines.append('changed blocks: %d in %d functions (%s); open blocks in partial functions %d (%d B)' % (
        sum(int(r[19]) for r in rows), len(rows), ', '.join('%s %d' % kv for kv in collections.Counter(
            b[4] for bl in blocks.values() for b in bl).most_common()),
        sum(int(r[20]) for r in rows if r[14] == 'partial'), sum(int(r[21]) for r in rows if r[14] == 'partial')))
    lines.append('thinly covered blocks (WEAK: > 128 B named by one address): %d, in ported functions: %d' % (
        sum(r[23].count('WEAK') for r in rows), sum(r[23].count('WEAK') for r in rows if r[14] == 'ported')))
    lines.append('changed pairs with a size ratio > 2 (split function or wrong pairing, blocks unreliable): %d' %
                 sum(1 for r in rows if 'size ratio' in r[18]))
    lines.append('partial by topic: ' + ', '.join('%s %d' % kv for kv in collections.Counter(
        r[9] for r in rows if r[14] == 'partial').most_common()))
    lines.append('basis: ' + ', '.join('%s %d' % kv for kv in collections.Counter(r[16] for r in rows).most_common()))
    lines.append('documented in findings / ENGINE.md (any status): %d' % sum(1 for r in rows if r[17]))
    lines.append('open but documented (known, not ported): %d' % sum(1 for r in rows if r[14] == 'open' and r[17]))
    lines.append('PC partner mapped: %d (tiers %s)' % (sum(1 for r in rows if r[5]), dict(collections.Counter(
        r[6] for r in rows if r[5]))))
    lines.append('topic (all rows / open rows / open bytes):')
    tall = collections.Counter(r[9] for r in rows)
    topen = collections.Counter(r[9] for r in rows if r[14] == 'open')
    tob = collections.Counter()
    for r in rows:
        if r[14] == 'open':
            tob[r[9]] += size(r)
    for t, n in tall.most_common():
        lines.append('  %-24s %5d %5d %8d' % (t, n, topen[t], tob[t]))
    lines.append('topic basis: ' + ', '.join('%s %d' % (k or '-', v) for k, v in
                                           collections.Counter(r[10] for r in rows).most_common()))
    lines.append('biggest open functions:')
    for r in sorted((r for r in rows if r[14] == 'open'), key=size, reverse=True)[:15]:
        lines.append('  %s %-7s %6s B  %-22s %s %s' % (r[0], r[1], r[2], r[9], r[7][:40], ('refs: ' + r[17][:60])
                                                       if r[17] else ''))
    # pairing check: "TU 0x82a = retail 0x82b" / "retail 0x82b, TU 0x82a" (only ' =,/(' between) in plugin sources /
    # ENGINE.md where both are function starts - does the alignment pair them the same way?
    said = {}
    pair_re = re.compile(r'TU (0x82[0-9a-fA-F]{6})[ =,/(]{1,6}retail (0x82[0-9a-fA-F]{6})|'
                         r'retail (0x82[0-9a-fA-F]{6})[ =,/(]{1,6}TU (0x82[0-9a-fA-F]{6})')
    for p in plugin_files + [os.path.join(ROOT, 'docs', 'ENGINE.md')]:
        t = REF_TEXT.get(p)
        if t is None:
            try:
                t = open(p, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
        for m in pair_re.finditer(t):
            tu_a, rt_a = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
            tu_a, rt_a = int(tu_a, 16), int(rt_a, 16)
            if tu_a in tu_end and rt_a in rt_end:
                said[tu_a] = rt_a
    agree = sum(1 for a, b in said.items() if tu2rt.get(a) == b)
    lines.append('pairing vs "TU x = retail y" statements in plugins / ENGINE.md (both function starts): %d, agree %d%s'
                 % (len(said), agree, (', differ: ' + ', '.join('TU 0x%08x said retail 0x%08x, paired %s' % (
                     a, b, ('0x%08x' % tu2rt[a]) if a in tu2rt else '-') for a, b in sorted(said.items())
                     if tu2rt.get(a) != b)[:600]) if agree < len(said) else ''))
    if '--compare' in argv:                        # status transitions against an older TSV (e.g. the previous list)
        old = {r['tu_addr']: r.get('status', '') for r in read_tsv(argv[argv.index('--compare') + 1])}
        tr = collections.Counter((old.get(r[0], '-'), r[14]) for r in rows)
        lines.append('status old -> new (vs %s):' % os.path.basename(argv[argv.index('--compare') + 1]))
        for (a, b), n in sorted(tr.items()):
            lines.append('  %-10s -> %-10s %5d' % (a, b, n))
    lines.append('TSV: %s' % (out if out is not None else 'not written (no --out; the list in the repo is written with '
                                                          '--out docs/data/tu_coverage.tsv)'))
    text = '\n'.join(lines)
    print(text)
    if summ:
        open(summ, 'w', encoding='utf-8').write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
