"""Native script types referenced by a mods tree, checked against an exe (read-only). Every script section that
names a native package ('game/script/.../...') and a type name is collected per tree; a type whose name string
does not occur in the exe has no native code on that platform - its functions keep null pointers (as the
title update's `dlc2data` in finding 43, test 33). Finding 43 follow-up (DLC 2 rock vein: which DLC 2 mechanics
need code the PC exe does not have?).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/native_types_check.py MODS_DIR EXE [--glob PREFIX]
  --glob PREFIX: only .drm files whose name starts with PREFIX (e.g. dlc2_)
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW

PKG = re.compile(rb'(game/script/[a-z0-9_/]+)\x00+([a-z0-9_]+)\x00')


def main(argv):
    pre = ''
    if '--glob' in argv:
        k = argv.index('--glob'); pre = argv[k + 1]; argv = argv[:k] + argv[k + 2:]
    mods, exe = argv
    blob = open(exe, 'rb').read()
    seen = collections.defaultdict(set)          # (package, type) -> {file}
    for root, _, files in os.walk(mods):
        for f in files:
            if not f.endswith('.drm') or not f.startswith(pre): continue
            p = os.path.join(root, f)
            try: D = DW.read(open(p, 'rb').read(), 'le')
            except Exception: continue
            for s in D.sections:
                if s.type != 8: continue
                for m in PKG.finditer(s.data):
                    seen[(m.group(1).decode(), m.group(2).decode())].add(f)
    missing = 0
    for (pkg, name), fs in sorted(seen.items()):
        ok = (name.encode() + b'\x00') in blob
        if not ok: missing += 1
        if not ok or '--all' in argv:
            print('%-8s %-30s %-26s %d files, e.g. %s' % ('ok' if ok else 'MISSING', pkg, name, len(fs),
                                                          ', '.join(sorted(fs)[:3])))
    print('%d native types referenced, %d without a name string in the exe' % (len(seen), missing))


if __name__ == '__main__':
    main(sys.argv[1:])
