"""Compare a TruMenu precheck file (work/asi/<build>/precheck_*.txt, one `ADDR HEX...` per line, the input of
tools/pe_bytes_check.py --file) with the byte checks of one section of src/asi/TruMenu/TruMenu.cpp (read-only;
TruMenu 0.12 Debug-Zeichnung: every line pinned against the Steam exe must be a check the plugin does at load, and the
other way round).

Source checks found in the section: `HexBytesAt(0xADDR, "hex")`, `HexBytesAt(kName, "hex")` with `kName = 0xADDR`
defined anywhere in the file, and table rows `{0xADDR, "hex"}`. Hex is compared without spaces, lower case.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/trumenu_precheck_match.py PRECHECK.txt [--from TEXT] [--to TEXT] [--cpp FILE]
     --from / --to   the section of TruMenu.cpp (first line containing TEXT .. the next line containing TEXT);
                     default "---- 0.12 Debug-Zeichnung" .. "---- favourites"
Exit 0 = both sets equal, 1 = a difference (listed).
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CPP = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.cpp')


def opt(argv, name, default):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


def norm(h):
    return re.sub(r'\s+', '', h).lower()


def main(argv):
    start = opt(argv, '--from', '---- 0.12 Debug-Zeichnung')
    end = opt(argv, '--to', '---- favourites')
    cpp = opt(argv, '--cpp', CPP)
    if not argv:
        print(__doc__)
        return 2
    pinned = []
    for n, line in enumerate(open(argv[0], encoding='utf-8'), 1):
        line = line.split('#')[0].strip()
        if not line: continue
        a, _, h = line.partition(' ')
        pinned.append((int(a, 16), norm(h)))
    src = open(cpp, encoding='utf-8').read()
    consts = {}
    for m in re.finditer(r'\b(k[A-Za-z0-9_]+)\s*=\s*(0x[0-9a-fA-F]+)', src):
        consts.setdefault(m.group(1), int(m.group(2), 16))
    lines = src.split('\n')
    i0 = next((i for i, l in enumerate(lines) if start in l), None)
    if i0 is None:
        print('section start "%s" not found in %s' % (start, cpp))
        return 1
    i1 = next((i for i in range(i0 + 1, len(lines)) if end in lines[i]), len(lines))
    section = '\n'.join(lines[i0:i1])
    found = []
    for m in re.finditer(r'HexBytesAt\(\s*(0x[0-9a-fA-F]+|k[A-Za-z0-9_]+)\s*,\s*"([0-9a-fA-F ]+)"\)', section):
        a = m.group(1)
        if a.startswith('k'):
            if a not in consts:
                print('constant %s not found in %s' % (a, cpp))
                return 1
            a = consts[a]
        else:
            a = int(a, 16)
        found.append((a, norm(m.group(2))))
    for m in re.finditer(r'\{\s*(0x[0-9a-fA-F]+)\s*,\s*"([0-9a-fA-F ]+)"\s*\}', section):
        found.append((int(m.group(1), 16), norm(m.group(2))))
    sp, sf = set(pinned), set(found)
    print('precheck file %s: %d lines (%d distinct); %s lines %d..%d: %d checks (%d distinct)' % (
        argv[0], len(pinned), len(sp), os.path.basename(cpp), i0 + 1, i1, len(found), len(sf)))
    for a, h in sorted(sp - sf): print('ONLY IN PRECHECK 0x%08x %s' % (a, h))
    for a, h in sorted(sf - sp): print('ONLY IN SOURCE   0x%08x %s' % (a, h))
    same = len(sp & sf)
    print('%d equal, %d only in the precheck file, %d only in the source' % (same, len(sp - sf), len(sf - sp)))
    return 0 if sp == sf else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
