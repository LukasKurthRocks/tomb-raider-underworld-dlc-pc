"""Which script classes deriving from script 93 (`uiscreen`) put what into vtable slot 31 - read-only.

Night 04.11. (workspace docs Befund-Restrisiken-0411.md, task A). The PC exe calls uiscreen's script vtable slot
NATIVELY by index: the uiscreen binder (tru+0x3b7951) stores the vtIndex of prototype 111 of the resident script 93
(PC: 31, function f111, empty) in [0x105b7f4]; cdc::ScriptUIScreen's C++ slot 80 (tru+0xbe090, the only caller
tru+0x1a6db8 = UIMenuWdgt C++ slot 54, mouse move over a menu) calls that slot on the screen's own script class
(tru+0x175fb0 = vtable[index] of the OBJECT's type). A class compiled against the Xbox 93 (31 slots) has its own
first virtual function in slot 31 (or no slot 31 at all), so on PC that native call reaches the wrong function
(or reads past the table).

For every type-8 section of each SOURCE whose base chain reaches 93 (bases resolved like the engine: RESIDENT first,
then the same file, then any other scanned file) it prints: vtableSize, the slot-31 VTE targets (own function fK with
its prototype name Symbol / argument count, or the external target script+offset), and a verdict:
  ok-inherit   slot 31 -> script 93 +0xcc8 (f111) - PC layout
  ok-override  slot 31 -> own function whose prototype name is Symbol 2582 (the f111 name) with vtIndex 31
  SHIFTED      slot 31 -> another function (Xbox layout: the native mouse call runs it)
  SHORT        vtableSize <= 31 (the native call reads past the table)
  other        anything else (printed)

Usage (from the repository root):
  ../bin/pyt -t 900 tools/script_slot31_users.py RESIDENT SOURCE [SOURCE ...] [--out FILE] [--json FILE]
  RESIDENT  installed generalbank.drm or pc:generalbank.drm (its own classes are reported too)
  SOURCE    a PC DRM file or a folder (every *.drm below it)
"""
import sys, os, struct, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R
import script_func_list as FL
import script_vtable_list as VL
import script_layout_clash as LC

UI = 93
SLOT = 31
F111_OFF = 0xcc8
F111_SYM = 2582


def files(src):
    if os.path.isdir(src):
        for p, rel in LC.drms(src): yield p
    else:
        yield src


def protos_funcs(d, rl, e):
    import script_conv as SC
    E = '>' if e == 'be' else '<'
    rel = R.parse(rl, e); it = dict(rel.internal)
    W = SC.Walk(d, rel, e).run()
    protos = {}; funcs = {}
    for name, t, n, sz in W.arrays:
        if name == 'protos':
            for k in range(n):
                a = t + k * sz
                at = it.get(a + 0xc)
                nargs = struct.unpack_from(E + 'I', d, at - 4)[0] if at else 0
                protos[a] = dict(k=k, vt=struct.unpack_from(E + 'H', d, a + 6)[0],
                                 sym=struct.unpack_from(E + 'H', d, a + 8)[0], nargs=nargs)
    for name, t, n, sz in W.arrays:
        if name == 'funcs':
            for k in range(n):
                a = t + k * sz
                pr = it.get(a)
                ct = it.get(a + 0x18)
                funcs[k] = dict(proto=protos.get(pr), native=ct is None,
                                words=struct.unpack_from(E + 'I', d, ct - 4)[0] if ct else 0)
    return funcs


def main(argv):
    def opt(name):
        if name in argv:
            k = argv.index(name); v = argv[k + 1]; del argv[k:k + 2]; return v
    out = opt('--out'); js = opt('--json')
    if len(argv) < 2: sys.exit(__doc__)
    res_spec, srcs = argv[0], argv[1:]
    lines = []; rows = []; st = collections.Counter()
    res = LC.load_resident(res_spec)
    loaded = [(res_spec, FL.sections(res_spec))]
    for s in srcs:
        for p in files(s):
            try: loaded.append((p, FL.sections(p)))
            except SystemExit: lines.append('skip %s (not readable)' % p)
    anywhere = {}
    for p, (S, e) in loaded:
        for q in S:
            if q[0] == 8 and q[2] and q[1] not in anywhere:
                anywhere[q[1]] = LC.lay(q[2], q[3], e)
    for n_file, (p, (S, e)) in enumerate(loaded):
        own = {q[1]: LC.lay(q[2], q[3], e) for q in S if q[0] == 8 and q[2]}
        for q in S:
            if q[0] != 8 or not q[2] or q[1] == UI: continue
            if n_file > 0 and q[1] in res:      # the engine keeps the resident copy, this one is dropped
                st['dropped (resident id)'] += 1; continue
            L = own[q[1]]
            if L is None: continue
            chain = []; b = L['base']; seen = set()
            while b is not None and b not in seen and len(chain) < 24:
                seen.add(b); chain.append(b)
                if b == UI: break
                if b in res: B = res[b]['lay']
                elif b in own: B = own[b]
                else: B = anywhere.get(b)
                if B is None: break
                b = B['base']
            if UI not in chain: continue
            size = L['vt']
            try: vt = VL.vtable(S, e, q[1])
            except KeyError: vt = []        # no vtable pointer (root 0x44 unrelocated)
            if len(vt) <= SLOT: size = min(size, len(vt))
            funcs = protos_funcs(q[2], q[3], e)
            own_hi = sorted({f['proto']['vt'] for f in funcs.values() if f['proto'] and f['proto']['vt'] != 0xffff
                             and f['proto']['vt'] >= SLOT})
            if size <= SLOT:
                verdict = 'SHORT'; tg = []
            else:
                tg = vt[SLOT][2]
                t0 = tg[0] if tg else None
                if t0 and t0[0] == 'x' and t0[1] == UI and t0[2] == F111_OFF: verdict = 'ok-inherit'
                elif t0 and t0[0] == 'f':
                    pr = funcs[t0[1]]['proto']
                    verdict = 'ok-override' if pr and pr['sym'] == F111_SYM and pr['vt'] == SLOT else 'SHIFTED'
                else: verdict = 'other'
            desc = []
            for t in tg:
                if t and t[0] == 'f':
                    f = funcs[t[1]]; pr = f['proto'] or {}
                    desc.append('f%d(sym %s, vt %s, %s args, %s)' % (t[1], pr.get('sym'), pr.get('vt'), pr.get('nargs'),
                                                                   'native' if f['native'] else '%d words' % f['words']))
                elif t and t[0] == 'x': desc.append('s%d+%#x' % (t[1], t[2]))
                else: desc.append(str(t))
            # does the class use the menu types (uimenu / uimenuitem)? the native call comes from UIMenuWdgt only
            rel = R.parse(q[3], e); used = set()
            for si, so, do in rel.external:
                if si < len(S) and S[si][0] == 8:
                    tid = S[si][1]
                    T = res[tid]['lay'] if tid in res else own.get(tid) or anywhere.get(tid)
                    if T and T['native']: used.add(T['native'])
            # every C++ UIMenuWdgt is created lazily by a native of a menu type (uimenu, uimenuitem, the bool / enum
            # items embed one: tru+0x1af520 callers), so any native type with 'menu' in its name counts
            menu = sorted(n for n in used if 'menu' in n.lower())
            st[verdict] += 1
            if verdict in ('SHIFTED', 'SHORT') and menu: st[verdict + ' with menu'] += 1
            name = os.path.basename(p)
            lines.append('%-11s %-34s script %5d vt %2d chain %s slot31 [%s] own vtIndex>=31 %s menu %s' % (
                verdict, name, q[1], size, '>'.join(map(str, chain)), ', '.join(desc), own_hi, menu or '-'))
            rows.append(dict(file=p, script=q[1], vt=size, chain=chain, slot31=desc, verdict=verdict, own_hi=own_hi,
                             menu=menu))
    lines.append('summary: %s' % dict(st))
    text = '\n'.join(lines) + '\n'
    if out: open(out, 'w', encoding='utf-8').write(text)
    sys.stdout.write(text if not out else 'summary: %s -> %s\n' % (dict(st), out))
    if js: json.dump(rows, open(js, 'w', encoding='utf-8'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
