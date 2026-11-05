"""Static check of the hook / patch sites between two versions of a plugin source (e.g. TruMenu.cpp 0.10.4 vs 0.10.5)
- read-only. Counts per pattern (vtable patches, code / data writes, byte pre-checks, import-slot patches, detours,
Direct3D device calls, thread creation) in OLD and NEW, and prints every ADDED or REMOVED line (difflib) that matches
one of the patterns, so a reviewer sees each new site at once.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/src_hook_sites_diff.py OLD.cpp NEW.cpp
"""
import difflib, re, sys

PATTERNS = [
    ('vtable patch', r'\bPatchVtable\s*\('),
    ('code / data write', r'\b(WriteDword|WriteByte|WriteBytes|WriteCode|PatchBytes|PatchCall|PatchJmp)\s*\('),
    ('VirtualProtect', r'\bVirtualProtect\s*\('),
    ('raw pointer store', r'\*reinterpret_cast<volatile [^>]*\*>\([^)]*\)\s*='),
    ('byte pre-check', r'\bHexBytesAt\s*\('),
    ('import slot / GetProcAddress', r'\b(PatchGetProc|GetProcAddress)\s*\('),
    ('device call', r'\bdevice->\w+\s*\('),
    ('thread', r'\bCreateThread\s*\('),
    ('export', r'__declspec\(dllexport\)'),
]


def count(lines):
    return {name: sum(1 for l in lines if re.search(rx, l)) for name, rx in PATTERNS}


def main(argv):
    if len(argv) != 2: sys.exit(__doc__)
    old = open(argv[0], encoding='utf-8', errors='replace').read().splitlines()
    new = open(argv[1], encoding='utf-8', errors='replace').read().splitlines()
    co, cn = count(old), count(new)
    print('%-30s %6s %6s' % ('pattern', 'old', 'new'))
    for name, _ in PATTERNS: print('%-30s %6d %6d%s' % (name, co[name], cn[name], '' if co[name] == cn[name] else '  <- changed'))
    for d in difflib.unified_diff(old, new, lineterm='', n=0):
        if d.startswith(('+++', '---', '@@')): continue
        for name, rx in PATTERNS:
            if re.search(rx, d[1:]):
                print('%s [%s] %s' % ('ADDED  ' if d[0] == '+' else 'REMOVED', name, d[1:].strip()[:150]))
                break
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
