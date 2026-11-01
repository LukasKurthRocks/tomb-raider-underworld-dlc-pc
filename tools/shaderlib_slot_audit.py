"""Occupied permutation slots of every ShaderLib a converted object's materials use: Xbox library vs the PC library
the converter put in its place (read-only). Materials (type 10) are paired by section position (the converter keeps
the section order); the 4 shader slots at +0x28..+0x34 (ps pass 0-2, vs) give the Xbox -> PC library pairs. A PC
library that lacks a slot the Xbox library has means the PC engine cannot build that permutation (finding 43: it
falls back or gets no bytecode). Also: PC libraries whose slot table is shorter than the Xbox one, empty entries,
and bytecode that is not a D3D9 shader (version token).
Test 48d (2026-10-31): D3D device error with the doppelganger figure ~10 s after DoppelgangerInit (lazy shader
creation at the first draw of a permutation).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/shaderlib_slot_audit.py XBOX.drm PC.drm [--all]
  --all: print every pair (default: pairs with a difference)
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R
from shaderlib import parse


def mats(D, en):
    e = '>' if en == 'be' else '<'
    out = []
    for s in D.sections:
        if s.type != 10: continue
        refs = set(R.parse(s.reloc, en).idref)
        sl = []
        for k in range(4):
            o = 0x28 + 4 * k
            v = struct.unpack_from(e + 'I', s.data, o)[0] if o + 4 <= len(s.data) else None
            sl.append(v if (9, o) in refs else None)
        out.append((s.id, sl))
    return out


def libs(D, en):
    res = {}
    for s in D.sections:
        if s.type != 9: continue
        lib = parse(s.data, en)
        occ = [i for i, o in enumerate(lib['slots']) if o != 0xffffffff]
        vers = collections.Counter()
        for o in set(x for x in lib['slots'] if x != 0xffffffff):
            ent = lib['entries'][o]
            blob = ent.get('code') or ent.get('blob') or b''
            vers[blob[:4].hex() if blob else '?'] += 1
        res[s.id] = dict(kind=lib['kind'], n=len(lib['slots']), occ=set(occ), vers=vers)
    return res


def main(argv):
    every = '--all' in argv; argv = [a for a in argv if a != '--all']
    X = DW.read(open(argv[0], 'rb').read(), 'be'); P = DW.read(open(argv[1], 'rb').read(), 'le')
    xm, pm = mats(X, 'be'), mats(P, 'le')
    xl, pl = libs(X, 'be'), libs(P, 'le')
    print('materials Xbox %d / PC %d, shader libs Xbox %d / PC %d' % (len(xm), len(pm), len(xl), len(pl)))
    pairs = collections.defaultdict(set)
    for (xid, xs), (pid, ps) in zip(xm, pm):
        for k in range(4):
            if xs[k] is None and ps[k] is None: continue
            pairs[(xs[k], ps[k])].add('%d/%d s%d' % (xid, pid, k))
    nd = 0
    for (xa, pa), users in sorted(pairs.items(), key=lambda t: (t[0][1] or 0, t[0][0] or 0)):
        a = xl.get(xa); b = pl.get(pa)
        why = []
        if a is None and xa is not None: why.append('Xbox lib %s not in file' % xa)
        if b is None and pa is not None: why.append('PC lib %s not in file' % pa)
        if xa is None and pa is not None: why.append('slot empty on Xbox')
        if pa is None and xa is not None: why.append('slot EMPTY on PC')
        if a and b:
            if a['kind'] != b['kind']: why.append('kind %d -> %d' % (a['kind'], b['kind']))
            if b['n'] < a['n']: why.append('table %d -> %d slots' % (a['n'], b['n']))
            miss = sorted(a['occ'] - b['occ'])
            if miss: why.append('%d Xbox slots missing on PC %s' % (len(miss), miss[:24]))
        if why: nd += 1
        if why or every:
            print('Xbox %-5s -> PC %-5s  %s  occ %s -> %s  users %d (%s)  %s'
                  % (xa, pa, ('vs' if b and b['kind'] == 0 else 'ps') if b else '?',
                     len(a['occ']) if a else '-', len(b['occ']) if b else '-', len(users),
                     ', '.join(sorted(users)[:3]), '; '.join(why) or 'ok'))
    print('%d lib pairs, %d with a difference' % (len(pairs), nd))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
