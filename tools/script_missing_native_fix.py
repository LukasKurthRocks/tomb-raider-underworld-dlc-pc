"""Neutralise script calls into natives the PC exe does not implement (stage-2b fix, finding 43 follow-up).

The Xbox title update added natives to some native script types (e.g. `achievement`: 16 functions on PC, 21 in the
TU). DLC scripts that call one of the TU-only natives reach an offset of the PC type script that is no function
entry - at run time the call would go through a null native pointer, like `dlc2data` did in test 33 (access
violation at tru+0x17deae). This tool finds such calls generically: every `op65` (native call) whose operand has an
external relocation into a native type script (taken from REF, normally the installed generalbank, which the engine
loads first) at an offset that is not a function entry of the PC version. The call sequence - all instructions
after the preceding line marker (op00) up to and including the call and its operand - is replaced by that line
marker (no stack effect, as tools/script_nop_call.py does) and its relocations are dropped.

Safety: a sequence is only replaced when it consists of plain pushes (op02 / op03 / op04 / op05 / op06 / op08 /
op0c / op0d / op0e / op0f / op10) plus the call, and when no argument is a local address (op09 = an out parameter:
the call would have written a result the script reads later). Anything else is reported and left alone.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/script_missing_native_fix.py MODS_DIR REF.drm OUT_DIR [--types achievement,...] [--check]
  MODS_DIR  a mods tree (PC DRMs); only changed DRMs are written to OUT_DIR (same file names)
  REF.drm   a generalbank.drm, or 'pc' for the original PC game's generalbank (what the pipeline fix `achievement` of
            tools/dlc_fixes_build.py uses)
  --types   native type names to fix (default: achievement); 'all' = every native type
  --check   report only, write nothing
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import menu_dlc_probe as P
import script_conv as SC
from native_calls_check import func_table

CALL = 0x65
SAFE = {0x02, 0x03, 0x04, 0x05, 0x06, 0x08, 0x0c, 0x0d, 0x0e, 0x0f, 0x10}


def native_types(ref):
    """{script id: (native type name, PC function table)} of the native type scripts of REF: a generalbank.drm, or
    'pc' = the original PC game's generalbank (patch.000 / bigfile.000; read-only, the same in every run - the
    pipeline's choice)"""
    if ref == 'pc':
        import dtp_word_classes as C
        secs = [(s['type'], s['id'], s['data'], s['reloc']) for s in C.find(C.PC, 'le', 'pc-w' + chr(92) + 'generalbank.drm')]
    else:
        secs = [(s.type, s.id, s.data, s.reloc) for s in DW.read(open(ref, 'rb').read(), 'le').sections]
    out = {}
    for typ, sid, data, reloc in secs:
        if typ != 8 or not data: continue
        info = P.script_info({'data': data, 'reloc': reloc}, 'le')[:2]
        if info[0]: out[sid] = (info[1], func_table(data, reloc))
    return out


def process(rel, path, nat, types, report):
    """the fixed DRM bytes of one file, or None when it has no such call (report gets the FIX / SKIP / NOTE lines)"""
    D = DW.read(open(path, 'rb').read(), 'le')
    n = sum(fix_section(D, s, nat, types, True, rel, report) for s in D.sections if s.type == 8 and s.data)
    return DW.cdrm_encode(D.write('le'), 'le') if n else None


def instructions(d, rel):
    """[(code start, [(offset, opcode, n extra words)])] for every function with code"""
    W = SC.Walk(d, rel, '<').run(); it = dict(rel.internal); res = []
    for name, t, n, sz in W.arrays:
        if name != 'funcs': continue
        for k in range(n):
            ct = it.get(t + k * sz + 0x18)
            if ct is None: continue
            cn = struct.unpack_from('<I', d, ct - 4)[0]; ins = []; j = 0
            while j < cn:
                o = ct + 4 * j; op = struct.unpack_from('<I', d, o)[0] >> 24
                extra = SC.Walk.EXTRA.get(op, 1 if op == P.PUSHF else 0)
                ins.append((o, op, extra)); j += 1 + extra
            res.append((ct, ins))
    return res


def fix_section(D, s, nat, types, apply, where, report):
    d = bytearray(s.data); rel = R.parse(s.reloc, 'le')
    ext = {so: (si, do) for si, so, do in rel.external}
    drop = set(); n = 0
    for ct, ins in instructions(bytes(d), rel):
        for i, (o, op, extra) in enumerate(ins):
            if extra < 1 or o + 4 not in ext: continue
            si, do = ext[o + 4]; t = D.sections[si]
            if t.type != 8 or t.id not in nat: continue
            tname, ft = nat[t.id]
            if types != 'all' and tname not in types: continue
            if do in ft: continue
            if op != CALL:
                report.append('NOTE op%02x operand -> %s +0x%x at %s:%d+0x%x (not a native call, left alone)' % (
                    op, tname, do, where, s.id, o + 4))
                continue
            j = i - 1
            while j >= 0 and ins[j][1] != 0x00: j -= 1
            tag = '%s:%d+0x%x -> %s +0x%x' % (where, s.id, o + 4, tname, do)
            if j < 0:
                report.append('SKIP no line marker before ' + tag); continue
            seq = ins[j + 1:i + 1]
            ops = [q[1] for q in seq[:-1]]
            if 0x09 in ops:
                report.append('SKIP out parameter (op09) ' + tag); continue
            if any(q not in SAFE for q in ops):
                report.append('SKIP non-push op %s in %s' % (sorted(set(ops) - SAFE), tag)); continue
            marker = struct.unpack_from('<I', d, ins[j][0])[0]
            words = [q[0] + 4 * e for q in seq for e in range(q[2] + 1)]
            old = ' '.join('%08x' % struct.unpack_from('<I', d, w)[0] for w in words)
            report.append('FIX  %s: %d words (%s) -> line marker %08x' % (tag, len(words), old, marker))
            n += 1
            if apply:
                for w in words: struct.pack_into('<I', d, w, marker)
                drop.update(words)
    if apply and n:
        rel.external = [x for x in rel.external if x[1] not in drop]
        rel.internal = [x for x in rel.internal if x[0] not in drop]
        rel.idref = [x for x in rel.idref if x[1] not in drop]
        rel.idref_a = [x for x in rel.idref_a if x[1] not in drop]
        s.data = bytes(d); s.reloc = R.write(rel, 'le')
    return n


def main(argv):
    check = '--check' in argv; argv = [a for a in argv if a != '--check']
    types = {'achievement'}
    if '--types' in argv:
        k = argv.index('--types'); v = argv[k + 1]; del argv[k:k + 2]
        types = 'all' if v == 'all' else set(v.split(','))
    mods, ref, out = argv
    if not check and os.path.realpath(out) == os.path.realpath(mods):
        sys.exit('OUT_DIR is MODS_DIR - would overwrite the input tree in place; use a separate test tree')
    nat = native_types(ref)
    report = []; files = 0; total = 0
    for f in sorted(os.listdir(mods)):
        if not f.endswith('.drm'): continue
        raw = open(os.path.join(mods, f), 'rb').read(); D = DW.read(raw, 'le')
        n = sum(fix_section(D, s, nat, types, not check, f, report)
                for s in D.sections if s.type == 8 and s.data)
        if n:
            files += 1; total += n
            if not check:
                os.makedirs(out, exist_ok=True)
                open(os.path.join(out, f), 'wb').write(DW.cdrm_encode(D.write('le'), 'le'))
    for line in report: print(line)
    print('%d call(s) %s in %d file(s)%s' % (total, 'found' if check else 'neutralised', files,
                                            '' if check else ' -> ' + out))


if __name__ == '__main__':
    main(sys.argv[1:])
