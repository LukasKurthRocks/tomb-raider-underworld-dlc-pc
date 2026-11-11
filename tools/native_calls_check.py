"""Calls from the scripts of a mods tree into NATIVE script types, checked against the PC versions of those types
(read-only). For every external relocation of a script section that points into a native type script (package +
name, e.g. game/script/game/game instance): does the target offset land on a function entry of the PC version
(taken from REF.drm, normally the installed generalbank, which the engine loads first), and is that function a
native? An offset that hits no function entry, or a function whose name Symbol the PC version lacks, is a call
the PC exe cannot serve (the TU-only natives of finding 42/43). Finding 43 follow-up (DLC 2 rock vein).
Only relocations that are the operand of a call instruction count as calls; other references (type / vtable / header
data) are listed only with --all - without that filter the 2026-10-30 run reported thousands of "+0x44"-style
references that are no calls.

Call instructions (Q75, 2026-11-11 - read from the PC interpreter 0x57ce50, jump table 0x57e52c indexed by opcode - 1;
before only op65 / op66 counted, Q66 saw op69 calls into screenshotsystem 3248):
  operand = function entry (checked: the target offset is a function entry of the PC version)
    op65 native call (0x57de34, calls [entry+0x14]), op66 on self (0x57deb8 -> CallFunction 0x57ad10),
    op69 on a popped object (0x57df5a -> 0x57ad10), op71 on a popped object (0x57dfd3, 0x574960),
    op6b on a popped object (0x57e2b0, 0x574960, leaves the loop), op6c on self (0x57e335 -> 0x57af00, leaves),
    op6f on a popped object (0x57e3da -> 0x57af00, leaves)
  operand = prototype (virtual call: u16 vtable index at prototype +6 resolved by 0x574990; checked: the target offset
  is a prototype of the PC version)
    op68 on self (0x57df06), op6a on a popped object (0x57df7d, vtable [[obj+8]+0x3c]), op6e on self (0x57e3c4,
    leaves), op70 on a popped object (0x57e419, leaves); op67 / op6d (0x57dec9 / 0x57e35e, on self) take two words:
    a vtable-size pointer (its u16 is compared with the index; counted as "vtsize", target offset listed with --ops)
    and the prototype
--ops prints the calls per opcode / operand kind.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/native_calls_check.py MODS_DIR REF.drm [--glob PREFIX] [--verbose] [--all] [--ops]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import menu_dlc_probe as P
import script_conv as SC

ENTRY_OPS = (0x65, 0x66, 0x69, 0x6b, 0x6c, 0x6f, 0x71)   # operand word = function entry
PROTO_OPS = (0x68, 0x6a, 0x6e, 0x70)                     # operand word = prototype (virtual call)
PAIR_OPS = (0x67, 0x6d)                                  # two words: vtable-size pointer, prototype


def func_proto_tables(d, rl):
    """({entry offset: (index, name Symbol, native?)} of a script's function array, {prototype offset: name Symbol})"""
    rel = R.parse(rl, '<'); it = dict(rel.internal)
    W = SC.Walk(d, rel, '<').run()
    protos = {}
    for name, t, n, sz in W.arrays:
        if name == 'protos':
            for k in range(n): protos[t + k * sz] = struct.unpack_from('<H', d, t + k * sz + 8)[0]
    out = {}
    for name, t, n, sz in W.arrays:
        if name == 'funcs':
            for k in range(n):
                a = t + k * sz
                out[a] = (k, protos.get(it.get(a)), it.get(a + 0x18) is None)
    return out, protos


def func_table(d, rl):
    """{entry offset: (index, name Symbol, native?)} of a script's function array (imported by
    tools/kitrest_ach_desc.py and tools/script_missing_native_fix.py)"""
    return func_proto_tables(d, rl)[0]


def call_kind(data, so):
    """(opcode, 'entry' / 'proto' / 'vtsize') when the word at so is the operand of a call instruction, else None"""
    op1 = struct.unpack_from('<I', data, so - 4)[0] >> 24 if so >= 4 else None
    if op1 in ENTRY_OPS: return op1, 'entry'
    if op1 in PROTO_OPS: return op1, 'proto'
    if op1 in PAIR_OPS: return op1, 'vtsize'
    op2 = struct.unpack_from('<I', data, so - 8)[0] >> 24 if so >= 8 else None
    if op2 in PAIR_OPS: return op2, 'proto'
    return None


def main(argv):
    pre = ''; verbose = '--verbose' in argv; show_all = '--all' in argv; show_ops = '--ops' in argv
    argv = [a for a in argv if a not in ('--verbose', '--all', '--ops')]
    if '--glob' in argv:
        k = argv.index('--glob'); pre = argv[k + 1]; argv = argv[:k] + argv[k + 2:]
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    mods, ref = argv
    REF = {s.id: s for s in DW.read(open(ref, 'rb').read(), 'le').sections if s.type == 8 and s.data}
    native = {}
    for sid, s in REF.items():
        info = P.script_info({'data': s.data, 'reloc': s.reloc}, 'le')[:2]
        if info[0]: native[sid] = (info, func_proto_tables(s.data, s.reloc))
    calls = collections.Counter(); bad = collections.defaultdict(set)
    ops = collections.Counter(); vts = collections.Counter()
    for root, _, files in os.walk(mods):
        for f in sorted(files):
            if not f.endswith('.drm') or not f.startswith(pre): continue
            D = DW.read(open(os.path.join(root, f), 'rb').read(), 'le')
            for s in D.sections:
                if s.type != 8 or not s.data: continue
                rel = R.parse(s.reloc, 'le')
                for si, so, do in rel.external:
                    t = D.sections[si]
                    if t.type != 8 or t.id not in native: continue
                    info, (ft, pt) = native[t.id]
                    ck = call_kind(s.data, so)
                    if not ck and not show_all: continue
                    calls[t.id] += 1
                    where = '%s:%d+0x%x%s' % (f, s.id, so, '' if ck else ' (no call)')
                    if ck:
                        ops[ck] += 1
                        if ck[1] == 'vtsize':
                            vts[do] += 1
                            continue
                        if ck[1] == 'proto':
                            if do not in pt: bad[(t.id, info[1], do, 'NO PROTOTYPE     ')].add(where + ' op%02x' % ck[0])
                            continue
                    if do in ft: continue
                    # offsets into a function entry's fields (+4 .. +0x18) are data reads, not calls
                    base = max((a for a in ft if a <= do), default=None)
                    if base is not None and do - base < 0x1c and do != base: continue
                    if do < min(ft, default=0): continue          # root fields / header
                    bad[(t.id, info[1], do, 'NO FUNCTION ENTRY')].add(where + (' op%02x' % ck[0] if ck else ''))
    print('calls into %d native types (PC versions from %s): %d' % (len(calls), os.path.basename(ref), sum(calls.values())))
    for (tid, name, do, what), where in sorted(bad.items()):
        print('  %s  script %5d %-26s +0x%04x  from %d places, e.g. %s' % (
            what, tid, name, do, len(where), ', '.join(sorted(where)[:3])))
    if verbose:
        for tid, n in calls.most_common(): print('  %5d %-26s %d' % (tid, native[tid][0][1], n))
    if show_ops:
        for (op, kind), n in sorted(ops.items()): print('  op%02x %-6s %d' % (op, kind, n))
        if vts: print('  vtsize target offsets: %s' % ', '.join('+0x%x x%d' % kv for kv in sorted(vts.items())))
    print('%d target offsets without a function entry / prototype' % len(bad))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
