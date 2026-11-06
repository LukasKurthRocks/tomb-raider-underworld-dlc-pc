"""Who gates what in the Croft Manor units: intros, per-instance scripts, their instance references, calls and
strings (read-only; finding 2026-11-06 manor prologue, workspace docs\\Befund-Manor-Prolog-0611.md).

Question (owner, after a speedrun): in the prologue (new game, Croft Manor burning) a runner jumped over the fire and
reached the place where Alister dies later in the story. Are the triggers / objects / scripts of that later chapter
already loaded in the prologue, and what keeps them from firing?

What is read (layouts and their sources):
  * Intros (tools/unit_debug_map.py: 0x90-byte records of the unit DTP, Level+0x74): +0x10 position (printed in the
    live frame = data - Level+0x80 origin, as TruMenu's position overlay), +0x50 u16 object id (named with
    work/generic/lists/pc_objectlist.txt), +0x52 u16 (printed raw; for the manor cinematic objects / triggers it
    equals the cinematic number, meaning not verified), +0x58 u32 unique id, +0x7c u32 = id of the per-instance
    script section (8, id) in the same DRM (seen: every non-zero +0x7c is a script section of the unit),
    trigger data (IntroDataTrigger +0x30 shape, +0x34 half extents, +0x40 radius) for objects named *trigger*.
  * Script sections (type 8) with tools/script_conv.Walk: functions (prototype index, vtable slot, name Symbol),
    every code word with an external relocation (callee script + function / prototype), `op7e` id references
    (type 8 id) and internal pointers to C strings - as tools/script_dis.py prints them.
  * Instance references: members whose DataType points to {51 = `instanceref`, -> {0x3b, Symbol, script id}} and
    whose init block points to the unique id of the referenced intro (layout read in l3_main_hall script 11575 with
    tools/drm_words_at.py: init +0x6c0 -> +0x6c4 = 4107 = cinematic_object whose +0x7c is 11569).
  * Sticky members: members of type `stickybool` (script 69) / `stickyint` (script 68) with their instance offset.
Interpreter facts used for reading (tru.exe jump table 0x57e52c, tools/pe_dis.py 2026-11-06): op43 int <, op44 int <=,
op45 int ==, op46 byte ==, op50 NOT, op51 AND, op52 OR (plus docs\\Befund-Test33-Native.md for the rest).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/manor_gate_scan.py intros UNIT.drm [UNIT.drm ...] [--grep REGEX]
  ../bin/pyt -t 900 tools/manor_gate_scan.py intros UNIT.drm [...] --uid N[,N..]   raw words of those intro records
        (0x90 bytes) and of the first 0x50 bytes of their intro data, to compare flag words
  ../bin/pyt -t 900 tools/manor_gate_scan.py scripts UNIT.drm [UNIT.drm ...] [--sid N[,N..]] [--grep REGEX] [--all]
        per-instance scripts (owner intro), or only the given section ids; --grep filters on the owner object name;
        --all adds every other non-native script section (level scripts, script classes)
  ../bin/pyt -t 900 tools/manor_gate_scan.py who UNIT.drm [UNIT.drm ...] (--uid N | --sid N | --text TEXT)
        every script function that references intro N (through an instance reference member it uses), script
        section N (op7e or a call into it) or a C string containing TEXT
  --names FILE   object names (default work/generic/lists/pc_objectlist.txt)
Exit code: 0 = done, 2 = usage error.
"""
import sys, os, re, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import menu_dlc_probe as P
import unit_debug_map as UDM

STICKY = {69: 'stickybool', 68: 'stickyint'}


def opt(argv, name, default):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


def load_names(path):
    d = {}
    for l in open(path, encoding='utf8', errors='ignore'):
        p = l.strip().split(',', 1)
        if len(p) == 2 and p[0].isdigit(): d[int(p[0])] = p[1]
    return d


class Script:
    """one type-8 section: functions, calls, id refs, strings, instance refs, sticky members"""

    def __init__(self, unit, si):
        import script_conv as SC
        s = unit.D.sections[si]
        self.id = s.id
        self.d = d = bytes(s.data)
        rl = bytes(s.reloc)
        self.rel = rel = R.parse(rl, 'le')
        self.it = it = dict(rel.internal)
        secs = unit.D.sections
        self.ext = {so: (secs[xi].type, secs[xi].id, do) for xi, so, do in rel.external}
        self.ids = rel.id_offsets()
        self.info = P.script_info({'data': d, 'reloc': rl}, 'le')[:2]
        self.W = SC.Walk(d, rel, 'le').run()
        self.size = len(d)

    def u32(self, o):
        return struct.unpack_from('<I', self.d, o)[0]

    def arrays(self, which):
        return [(t, n, sz) for name, t, n, sz in self.W.arrays if name == which]

    def protos(self):
        """{entry offset: (index, vtable slot, name Symbol)}"""
        out = {}
        for t, n, sz in self.arrays('protos'):
            for k in range(n):
                a = t + k * sz
                out[a] = (k, struct.unpack_from('<H', self.d, a + 6)[0], struct.unpack_from('<H', self.d, a + 8)[0])
        return out

    def funcs(self):
        """[(index, entry offset, proto (k, vt, sym) or None, code offset or None, word count)]"""
        pr = self.protos()
        out = []
        for t, n, sz in self.arrays('funcs'):
            for k in range(n):
                a = t + k * sz
                p = self.it.get(a)
                ct = self.it.get(a + 0x18)
                cn = self.u32(ct - 4) if ct is not None else 0
                out.append((k, a, pr.get(p) if p is not None else None, ct, cn))
        return out

    def members(self):
        """[(offset, name Symbol, script type id or None, instanceref (target script, uid) or None)]"""
        out = []
        for t, n, sz in self.arrays('members'):
            for k in range(n):
                a = t + k * sz
                tag, ut = struct.unpack_from('<IH', self.d, a)
                off, nm = struct.unpack_from('<HH', self.d, a + 12)
                typ = self.u32(a + 8) if (a + 8) in self.ids else None
                iref = None
                p = self.it.get(a + 8)
                if p is not None and p + 8 <= len(self.d) and self.u32(p) == 51 and (p + 4) in self.it:
                    q = self.it[p + 4]
                    tsid = self.u32(q + 8)
                    ini = self.it.get(a + 16)
                    uid = self.u32(self.it[ini]) if ini is not None and ini in self.it else None
                    iref = (tsid, uid)
                out.append((off, nm, typ, iref))
        return out

    def code(self, fn, other_protos):
        """[(code offset, opcode, operand, [annotations])] of one function; annotations are tuples:
        ('call', type, id, offset, label), ('id', type, id), ('str', text)"""
        k, a, pr, ct, cn = fn
        out = []
        if ct is None: return out
        import script_conv as SC
        j = 0
        while j < cn:
            o = ct + 4 * j
            w = self.u32(o)
            op = w >> 24; arg = w & 0xffffff
            extra = SC.Walk.EXTRA.get(op, 1 if op == P.PUSHF else 0)
            ann = []
            for q in range(1, extra + 1):
                ao = o + 4 * q
                if ao in self.it:
                    txt = P.cstr(self.d, self.it[ao])
                    if txt and all(32 <= ord(c) < 127 for c in txt): ann.append(('str', txt))
                elif ao in self.ext:
                    ty, tid, do = self.ext[ao]
                    ann.append(('call', ty, tid, do, other_protos(tid, do)))
                elif ao in self.ids:
                    ann.append(('id', self.ids[ao], self.u32(ao)))
            out.append((o, op, arg if arg < 0x800000 else arg - 0x1000000, ann))
            j += 1 + extra
        return out


class UnitScan:
    def __init__(self, path, names):
        self.path = path
        self.name = os.path.basename(path).rsplit('.', 1)[0]
        self.U = UDM.Unit(path)
        if self.U.L is None: raise SystemExit('%s: not a unit DRM' % path)
        self.origin = self.U.f(0, 0x80, 3)
        self.intros = UDM.intros(self.U, names)
        for it in self.intros:
            si, o = next((si, o) for si, o in self.U.L['intros'] if self.U.u(si, o + 0x58) == it['uid'])
            it['script'] = self.U.u(si, o + 0x7c)
        self.by_uid = {it['uid']: it for it in self.intros}
        self.by_script = {it['script']: it for it in self.intros if it['script']}
        self.sec_index = {s.id: i for i, s in enumerate(self.U.D.sections) if s.type == 8}
        self.cache = {}

    def script(self, sid):
        if sid not in self.cache:
            si = self.sec_index.get(sid)
            self.cache[sid] = Script(self.U, si) if si is not None else None
        return self.cache[sid]

    def label(self, tid, do):
        """'name.fN' / 'name.pN(vt V)' for a relocation into script tid at offset do"""
        sc = self.script(tid)
        if sc is None: return 'script%d+0x%x' % (tid, do)
        nm = sc.info[1] or ('script%d' % tid)
        for k, a, pr, ct, cn in sc.funcs():
            if a == do: return '%s.f%d' % (nm, k)
        pr = sc.protos()
        if do in pr:
            k, vt, sym = pr[do]
            fk = next((f[0] for f in sc.funcs() if f[2] and f[2][0] == k), None)
            return '%s.p%d(vt %d, f%s)' % (nm, k, vt, fk)
        return '%s+0x%x' % (nm, do)

    def live(self, p):
        return tuple(p[i] - self.origin[i] for i in range(3))


def sticky_access(us, sc, fn):
    """['get|set|fN stickybool <where>+OFF'] for every stickybool / stickyint call of one function.
    Patterns (read in l3_main_hall 11544 f9 / 11575 f1): own member `op0f OFF; op65 sticky.fN`; member of another
    instance `op0f M; op65 instanceref.f7; op0a L; op7e id S; op14 OFF; op65 sticky.fN` (S = that instance's script).
    f0 = set (the value is pushed first), f2 = get (address of the result local) - read from the cheat / trigger code."""
    out = []
    code = sc.code(fn, us.label)
    for i, (o, op, arg, ann) in enumerate(code):
        call = next((x for x in ann if x[0] == 'call' and x[1] == 8 and x[2] in STICKY), None)
        if call is None or i == 0: continue
        kind = {0x8c: 'get', 0x54: 'set'}.get(call[3], call[4])
        po, pop, parg, pann = code[i - 1]
        where = '?'
        if pop == 0x0f:
            where = 'own +%d' % parg
        elif pop == 0x14:
            sid = None
            for q in range(i - 2, max(-1, i - 5), -1):
                ida = next((x for x in code[q][3] if x[0] == 'id' and x[1] == 8), None)
                if ida: sid = ida[2]; break
            it = us.by_script.get(sid)
            where = 'script %s (%s) +%d' % (sid, ('intro %d %s' % (it['uid'], it['name'])) if it else 'other unit / class', parg)
        out.append('%s %s %s' % (kind, STICKY[call[2]], where))
    return out


def owner_text(us, sid):
    it = us.by_script.get(sid)
    return ('intro %d %s' % (it['uid'], it['name'])) if it else 'no intro (class / level script)'


def describe_script(us, sid, out):
    sc = us.script(sid)
    if sc is None:
        out.append('  script %d: not in %s' % (sid, us.name)); return
    out.append('  script %d (%d B, native %s) owner: %s' % (sid, sc.size, sc.info, owner_text(us, sid)))
    for off, nm, typ, iref in sc.members():
        if iref:
            tsid, uid = iref
            tgt = us.by_uid.get(uid)
            out.append('    member +%d (Symbol %d) instanceref -> intro %s %s (script %d)' % (
                off, nm, uid, tgt['name'] if tgt else '(not in this unit)', tsid))
        elif typ in STICKY:
            out.append('    member +%d (Symbol %d) %s' % (off, nm, STICKY[typ]))
    for fn in sc.funcs():
        k, a, pr, ct, cn = fn
        calls, ids, strs = [], [], []
        for o, op, arg, ann in sc.code(fn, us.label):
            for x in ann:
                if x[0] == 'call' and x[1] == 8: calls.append('op%02x %s' % (op, x[4]))
                elif x[0] == 'id': ids.append('%d' % x[2])
                elif x[0] == 'str': strs.append(x[1])
        out.append('    f%d proto %s, %d words' % (k, ('p%d vt %d Symbol %d' % pr) if pr else None, cn))
        if calls: out.append('      calls: %s' % ', '.join(calls))
        if ids: out.append('      op7e script ids: %s' % ', '.join(ids))
        if strs: out.append('      strings: %s' % ' | '.join(repr(s[:90]) for s in strs))
        acc = sticky_access(us, sc, fn)
        if acc: out.append('      sticky: %s' % '; '.join(acc))


def cmd_raw(units, uids):
    """the 0x90-byte intro records and the first 0x50 bytes of their intro data, as words (to compare flags)"""
    for us in units:
        for si, o in us.U.L['intros']:
            uid = us.U.u(si, o + 0x58)
            if uid not in uids: continue
            d = us.U.secs[si]['data']
            w = struct.unpack_from('<36I', d, o)
            print('%s intro %d (%s) record sec %d +0x%x:' % (us.name, uid, us.by_uid[uid]['name'], si, o))
            for r in range(0, 36, 8):
                print('   +0x%02x %s' % (4 * r, ' '.join('%08x' % x for x in w[r:r + 8])))
            dt = us.U.target(si, o + 0x78)
            if dt is not None:
                dsi, do = dt
                dd = us.U.secs[dsi]['data']
                n = min(20, (len(dd) - do) // 4)
                w = struct.unpack_from('<%dI' % n, dd, do)
                print('   data sec %d +0x%x: %s' % (dsi, do, ' '.join('%08x' % x for x in w)))


def cmd_intros(units, grep):
    for us in units:
        print('== %s: origin (%.1f %.1f %.1f), %d intros, %d portals' % (
            us.name, *us.origin, len(us.intros), len(us.U.L['portals'])))
        for pt in UDM.portals(us.U):
            c = [sum(q[i] for q in pt['pts']) / 6 for i in range(3)]
            print('   portal -> %-30s centre as stored (%.0f %.0f %.0f)' % (pt['name'], *c))
        for it in us.intros:
            if grep and not re.search(grep, it['name'], re.I): continue
            p = us.live(it['pos'])
            tr = ''
            if it['trig']:
                tr = ' shape %d half (%.1f %.1f %.1f) r %.1f' % (it['trig']['shape'], *it['trig']['ext'], it['trig']['radius'])
            print('   intro %6d %-36s live (%8.1f %8.1f %8.1f) +0x52 %5d script %5s%s' % (
                it['uid'], it['name'], p[0], p[1], p[2], it['w52'], it['script'] or '-', tr))


def cmd_scripts(units, sids, grep, every=False):
    for us in units:
        out = ['== %s' % us.name]
        if sids: todo = sids
        elif every:     # also the level / class scripts: every non-native script section of the unit
            todo = [s for s in sorted(us.sec_index) if us.script(s) and us.script(s).info[1] is None]
        else: todo = sorted(us.by_script)
        for sid in todo:
            it = us.by_script.get(sid)
            if grep and not (it and re.search(grep, it['name'], re.I)): continue
            if sids and sid not in us.sec_index: continue
            describe_script(us, sid, out)
        print('\n'.join(out))


def cmd_who(units, uid, sid, text):
    for us in units:
        hits = []
        for s in sorted(us.sec_index):
            sc = us.script(s)
            if sc is None: continue
            irefs = {off: r for off, nm, typ, r in sc.members() if r}
            via = [off for off, r in irefs.items() if uid is not None and r[1] == uid]
            if via:
                hits.append('  script %d (%s): member(s) %s -> intro %d' % (s, owner_text(us, s), ', '.join('+%d' % v for v in via), uid))
            for fn in sc.funcs():
                lines = []
                for o, op, arg, ann in sc.code(fn, us.label):
                    for x in ann:
                        if sid is not None and ((x[0] == 'id' and x[2] == sid) or (x[0] == 'call' and x[2] == sid)):
                            lines.append('+0x%x op%02x %s' % (o, op, x[4] if x[0] == 'call' else 'id %d' % x[2]))
                        if text is not None and x[0] == 'str' and text.lower() in x[1].lower():
                            lines.append('+0x%x %r' % (o, x[1][:90]))
                if lines:
                    hits.append('  script %d f%d (%s): %s' % (s, fn[0], owner_text(us, s), '; '.join(lines)))
        print('== %s: %d hits' % (us.name, len(hits)))
        for h in hits: print(h)


def main(argv):
    argv = list(argv)
    names = load_names(opt(argv, '--names', 'work/generic/lists/pc_objectlist.txt'))
    grep = opt(argv, '--grep', None)
    sids = opt(argv, '--sid', None)
    uid = opt(argv, '--uid', None)
    text = opt(argv, '--text', None)
    every = '--all' in argv
    argv = [a for a in argv if a != '--all']
    if len(argv) < 2 or argv[0] not in ('intros', 'scripts', 'who'):
        print(__doc__); return 2
    units = [UnitScan(p, names) for p in argv[1:]]
    if argv[0] == 'intros' and uid is not None:
        cmd_raw(units, set(int(x) for x in uid.split(',')))
    elif argv[0] == 'intros':
        cmd_intros(units, grep)
    elif argv[0] == 'scripts':
        cmd_scripts(units, [int(x) for x in sids.split(',')] if sids else None, grep, every)
    else:
        if uid is None and sids is None and text is None: print(__doc__); return 2
        cmd_who(units, int(uid) if uid else None, int(sids) if sids else None, text)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
