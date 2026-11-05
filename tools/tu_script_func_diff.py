"""Compare two versions of one script section (type 8) function by function, read-only: e.g. Xbox retail vs Xbox
title update (what did the TU change in a UI script?), or Xbox TU vs PC (what would a port have to merge?).

Functions are paired by their prototype name Symbol (stable across versions; unnamed helpers, Symbol 65535 / 230,
in order of appearance). Every code word is normalised before the diff: opcode + 24-bit operand, extra words as
internal string ("str 'text'"), internal pointer ("int"), external target ((type, id) + native type name and callee
function index), id reference (type + value) or raw value; float literals of op02 as floats. Both sides must use the
same id space for the external / id comparison to be meaningful (Xbox vs Xbox), Xbox vs PC still shows the structure.

Also printed: strings only in A / only in B, id references (all of the section, e.g. textures type 5) only in A / B,
native calls (type name + function index) only in A / B, vtable size and function counts.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/tu_script_func_diff.py A_SRC A_ID B_SRC B_ID [--diff N] [--funcs i,j] [--words]
  SRC   a PC (little-endian) DRM file, a tools/menu_dlc_probe.py variant (xl / xt / pb / pp, generalbank only),
        or ARCHIVE:NAME.drm with ARCHIVE = xtu / xret (Xbox base, TU first / retail) / pc / pack10 / pack11
  ../bin/pyt -t 600 tools/tu_script_func_diff.py --list SRC   scripts of a DRM: id, size, functions, native type
  --diff N   print at most N diff lines per changed function (default 60; 0 = summary only)
  --funcs    only these function indexes of B in the detailed diff
  --words    also print the raw offsets (A / B) next to the diff lines
  --mask H,H opcodes (hex) whose operand is ignored, e.g. 0f,10 (member offsets shift when a script gains members)
"""
import sys, os, struct, difflib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL
import menu_dlc_probe as P


MASK = set()      # opcodes whose 24-bit operand is masked (--mask), e.g. member offsets that shift when members grow


def printable(t):
    return t is not None and len(t) >= 3 and all(32 <= ord(c) < 127 for c in t)


def sections(src):
    """[(type, id, data, reloc)], endian. SRC = PC DRM file, probe variant (generalbank), or ARCHIVE:NAME.drm with
    ARCHIVE = xtu (Xbox base, title update first) / xret (Xbox retail layers) / pc (patch.000, bigfile.000) /
    pack10 / pack11 / pack1 / pack2 / pack20"""
    if ':' in src and not os.path.exists(src):
        import dtp_word_classes as C
        kind, name = src.split(':', 1)
        if kind == 'pc':
            S = C.find(C.PC, 'le', 'pc-w' + C.BS + name); e = 'le'
        else:
            paths = {'xtu': C.BASE, 'xret': C.BASE[1:]}.get(kind) or [
                C.DLC_ROOT + q for q in C.PACKS if q.endswith('/%s.000' % kind)]
            S = C.find(paths, 'be', 'xenon-w' + C.BS + name); e = 'be'
        if S is None: sys.exit('%s not found' % src)
        return [(s['type'], s['id'], s['data'], s['reloc']) for s in S], e
    return FL.sections(src)


class Script:
    def __init__(self, src, sid):
        import script_conv as SC
        self.src, self.sid = src, sid
        S, e = sections(src)
        self.S, self.e = S, e
        E = self.E = '>' if e == 'be' else '<'
        d, rl = next((q[2], q[3]) for q in S if q[0] == 8 and q[1] == sid and q[2])
        self.d = d
        rel = R.parse(rl, e)
        self.it = dict(rel.internal)
        self.ext = {so: (S[si][0], S[si][1], do) for si, so, do in rel.external}
        self.ids = rel.id_offsets()
        self.W = SC.Walk(d, rel, e).run()
        self.vt = struct.unpack_from(E + 'H', d, 0x3c)[0]
        self.byid = {q[1]: q for q in S if q[0] == 8 and q[2]}
        self._entries = {}
        self._names = {}
        protos = {}
        for name, t, n, sz in self.W.arrays:
            if name == 'protos':
                for k in range(n):
                    a = t + k * sz
                    protos[a] = struct.unpack_from(E + 'HH', d, a + 8)
        self.funcs = []                       # [(index, key, code offset, n words)]
        unnamed = 0
        for name, t, n, sz in self.W.arrays:
            if name != 'funcs':
                continue
            for k in range(n):
                a = t + k * sz
                pr = self.it.get(a)
                sym = protos.get(pr) if pr is not None else None
                ct = self.it.get(a + 0x18)
                cn = struct.unpack_from(E + 'I', d, ct - 4)[0] if ct is not None else 0
                if sym is None or sym[0] in (65535, 230):
                    key = ('unnamed', unnamed); unnamed += 1
                else:
                    key = ('sym', sym[0])
                self.funcs.append((k, key, ct, cn))

    def entries(self, tid):
        if tid not in self._entries:
            import script_dis as SD
            q = self.byid.get(tid)
            self._entries[tid] = SD.func_entries(q[2], q[3], self.e) if q else {}
            self._names[tid] = P.script_info({'data': q[2], 'reloc': q[3]}, self.e)[1] if q else None
        return self._entries[tid], self._names[tid]

    def ext_text(self, ty, tid, do):
        if ty == 8:
            ent, nat = self.entries(tid)
            fi = ent.get(do)
            return 'ext (8,%d)%s f%s' % (tid, ' ' + nat if nat else '', fi if fi is not None else '+0x%x' % do), nat, fi
        return 'ext (%d,%d)+0x%x' % (ty, tid, do), None, None

    def code(self, ct, cn):
        """[(offset, normalised text, native call or None)]"""
        import script_conv as SC
        d, E = self.d, self.E
        out = []
        j = 0
        while j < cn:
            o = ct + 4 * j
            w = struct.unpack_from(E + 'I', d, o)[0]
            op = w >> 24; arg = w & 0xffffff
            extra = SC.Walk.EXTRA.get(op, 1 if op == P.PUSHF else 0)
            ann = []; nat = None
            for q in range(1, extra + 1):
                ao = o + 4 * q
                if ao + 4 > len(d):
                    break
                aw = struct.unpack_from(E + 'I', d, ao)[0]
                if ao in self.it:
                    txt = P.cstr(d, self.it[ao])
                    ann.append('str %r' % txt[:70] if printable(txt) else 'int')
                elif ao in self.ext:
                    t, n_, fi = self.ext_text(*self.ext[ao])
                    ann.append(t)
                    if n_ and op in (0x65, 0x66):
                        nat = (n_, fi)
                elif ao in self.ids:
                    ann.append('id type%d %d' % (self.ids[ao], aw))
                elif op == P.PUSHF:
                    ann.append('float %g' % struct.unpack(E + 'f', struct.pack(E + 'I', aw))[0])
                else:
                    ann.append('raw 0x%x' % aw)
            sarg = arg if arg < 0x800000 else arg - 0x1000000
            out.append((o, 'op%02x %s %s' % (op, '*' if op in MASK else sarg, ' | '.join(ann)), nat))
            j += 1 + extra
        return out

    def strings(self):
        s = set()
        for so, to in self.it.items():
            t = P.cstr(self.d, to)
            if printable(t) and len(t) >= 5:
                s.add(t)
        return s

    def idrefs(self):
        return collections.Counter((t, struct.unpack_from(self.E + 'I', self.d, o)[0]) for o, t in self.ids.items()
                                   if o + 4 <= len(self.d))

    def natives(self):
        c = collections.Counter()
        for k, key, ct, cn in self.funcs:
            if ct is None:
                continue
            for o, txt, nat in self.code(ct, cn):
                if nat:
                    c[nat] += 1
        return c


def list_scripts(src, other=None):
    """one line per script of SRC: id, size, functions, native type, a few strings; vs OTHER (same id): same / changed
    / new"""
    S, e = sections(src)
    O = {q[1]: q[2] for q in sections(other)[0] if q[0] == 8} if other else None
    for t, i, d, rl in S:
        if t != 8 or not d:
            continue
        rel = R.parse(rl, e); it = dict(rel.internal)
        pk, nat, _ = P.script_info({'data': d, 'reloc': rl}, e)
        strs = []
        for so in sorted(it):
            tx = P.cstr(d, it[so])
            if printable(tx) and len(tx) >= 6 and tx not in strs and '/' not in tx:
                strs.append(tx)
        st = ''
        if O is not None:
            st = 'new' if i not in O else 'same' if bytes(O[i]) == bytes(d) else 'changed %d->%d' % (len(O[i]), len(d))
        print('  8:%-6d %7d B  %-16s %-14s %s' % (i, len(d), nat or '-', st, ' | '.join(s[:50] for s in strs[:3])))


def main(argv):
    if argv and argv[0] == '--list':
        return list_scripts(argv[1], argv[2] if len(argv) > 2 else None)
    nd = 60; only = None; words = '--words' in argv
    argv = [a for a in argv if a != '--words']
    if '--diff' in argv: k = argv.index('--diff'); nd = int(argv[k + 1]); del argv[k:k + 2]
    if '--funcs' in argv: k = argv.index('--funcs'); only = {int(x) for x in argv[k + 1].split(',')}; del argv[k:k + 2]
    if '--mask' in argv: k = argv.index('--mask'); MASK.update(int(x, 16) for x in argv[k + 1].split(',')); del argv[k:k + 2]
    if len(argv) != 4: sys.exit(__doc__)
    A = Script(argv[0], int(argv[1])); B = Script(argv[2], int(argv[3]))
    for X in (A, B):
        print('%s script %d: %d B, %d functions, vtable %d slots, native type %s' % (
            X.src, X.sid, len(X.d), len(X.funcs), X.vt, X.entries(X.sid)[1]))
        print('   arrays: %s' % ', '.join('%s %d' % (name, n) for name, t, n, sz in X.W.arrays))
    ka = {key: (k, ct, cn) for k, key, ct, cn in A.funcs}
    kb = {key: (k, ct, cn) for k, key, ct, cn in B.funcs}
    print('\n-- function pairing (by name Symbol)')
    tally = collections.Counter()
    changed = []
    for k, key, ct, cn in B.funcs:
        if key not in ka:
            print('  B f%-3d %-16s ONLY IN B  (%d words)' % (k, key, cn)); tally['only B'] += 1; changed.append((None, k, key)); continue
        ia, cta, cna = ka[key]
        if ct is None or cta is None:
            st = 'native' if ct is None and cta is None else 'native on one side'
            print('  A f%-3d B f%-3d %-16s %s' % (ia, k, key, st)); tally[st] += 1; continue
        la = [t for o, t, n in A.code(cta, cna)]; lb = [t for o, t, n in B.code(ct, cn)]
        if la == lb:
            tally['equal'] += 1; continue
        sm = difflib.SequenceMatcher(None, la, lb, autojunk=False)
        ins = sum(j2 - j1 for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag in ('insert', 'replace'))
        dele = sum(i2 - i1 for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag in ('delete', 'replace'))
        print('  A f%-3d B f%-3d %-16s CHANGED  %d -> %d words, +%d / -%d instructions' % (ia, k, key, cna, cn, ins, dele))
        tally['changed'] += 1; changed.append((ia, k, key))
    for k, key, ct, cn in A.funcs:
        if key not in kb:
            print('  A f%-3d %-16s ONLY IN A  (%d words)' % (k, key, cn)); tally['only A'] += 1
    print('  totals: %s' % dict(tally))

    sa, sb = A.strings(), B.strings()
    print('\n-- strings only in B (%d)' % len(sb - sa))
    for t in sorted(sb - sa): print('   + %r' % t)
    print('-- strings only in A (%d)' % len(sa - sb))
    for t in sorted(sa - sb): print('   - %r' % t)
    ia, ib = A.idrefs(), B.idrefs()
    print('\n-- id references only in B: %s' % sorted((ib - ia).items()))
    print('-- id references only in A: %s' % sorted((ia - ib).items()))
    na, nb = A.natives(), B.natives()
    print('\n-- native calls only in B / more often in B: %s' % sorted((nb - na).items(), key=str))
    print('-- native calls only in A / more often in A: %s' % sorted((na - nb).items(), key=str))

    if nd == 0:
        return
    for ia_, k, key in changed:
        if only is not None and k not in only:
            continue
        ct, cn = kb[key][1], kb[key][2]
        lb = B.code(ct, cn)
        if ia_ is None:
            print('\n== B f%d %s (only in B)' % (k, key))
            for o, t, n in lb[:nd]: print('   + %s%s' % ('%05x ' % o if words else '', t))
            if len(lb) > nd: print('   ... %d more' % (len(lb) - nd))
            continue
        la = A.code(ka[key][1], ka[key][2])
        print('\n== A f%d / B f%d %s' % (ia_, k, key))
        sm = difflib.SequenceMatcher(None, [t for o, t, n in la], [t for o, t, n in lb], autojunk=False)
        n = 0
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                continue
            print('   @@ A %d..%d  B %d..%d %s' % (i1, i2, j1, j2, tag))
            for o, t, _ in la[i1:i2]:
                if n < nd: print('   - %s%s' % ('%05x ' % o if words else '', t))
                n += 1
            for o, t, _ in lb[j1:j2]:
                if n < nd: print('   + %s%s' % ('%05x ' % o if words else '', t))
                n += 1
        if n > nd: print('   ... %d more diff lines' % (n - nd))


if __name__ == '__main__':
    main(sys.argv[1:])
