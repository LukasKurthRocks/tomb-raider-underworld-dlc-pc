"""Calls from the scripts of a mods tree into NATIVE script types, checked against the PC versions of those types
(read-only). For every external relocation of a script section that points into a native type script (package +
name, e.g. game/script/game/game instance): does the target offset land on a function entry of the PC version
(taken from REF.drm, normally the installed generalbank, which the engine loads first), and is that function a
native? An offset that hits no function entry, or a function whose name Symbol the PC version lacks, is a call
the PC exe cannot serve (the TU-only natives of finding 42/43). Finding 43 follow-up (DLC 2 rock vein).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/native_calls_check.py MODS_DIR REF.drm [--glob PREFIX] [--verbose]
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
import menu_dlc_probe as P
import script_conv as SC


def func_table(d, rl):
    """{entry offset: (index, name Symbol, native?)} of a script's function array"""
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
    return out


def main(argv):
    pre = ''; verbose = '--verbose' in argv
    argv = [a for a in argv if a != '--verbose']
    if '--glob' in argv:
        k = argv.index('--glob'); pre = argv[k + 1]; argv = argv[:k] + argv[k + 2:]
    mods, ref = argv
    REF = {s.id: s for s in DW.read(open(ref, 'rb').read(), 'le').sections if s.type == 8 and s.data}
    native = {}
    for sid, s in REF.items():
        info = P.script_info({'data': s.data, 'reloc': s.reloc}, 'le')[:2]
        if info[0]: native[sid] = (info, func_table(s.data, s.reloc))
    calls = collections.Counter(); bad = collections.defaultdict(set)
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
                    info, ft = native[t.id]
                    calls[t.id] += 1
                    if do in ft: continue
                    # offsets into a function entry's fields (+4 .. +0x18) are data reads, not calls
                    base = max((a for a in ft if a <= do), default=None)
                    if base is not None and do - base < 0x1c and do != base: continue
                    if do < min(ft, default=0): continue          # root fields / header
                    bad[(t.id, info[1], do)].add('%s:%d+0x%x' % (f, s.id, so))
    print('calls into %d native types (PC versions from %s): %d' % (len(calls), os.path.basename(ref), sum(calls.values())))
    for (tid, name, do), where in sorted(bad.items()):
        print('  NO FUNCTION ENTRY  script %5d %-26s +0x%04x  from %d places, e.g. %s' % (
            tid, name, do, len(where), ', '.join(sorted(where)[:3])))
    if verbose:
        for tid, n in calls.most_common(): print('  %5d %-26s %d' % (tid, native[tid][0][1], n))
    print('%d target offsets without a function entry' % len(bad))


if __name__ == '__main__':
    main(sys.argv[1:])
