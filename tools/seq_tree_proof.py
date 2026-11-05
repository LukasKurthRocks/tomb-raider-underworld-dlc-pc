"""Proof of a seqrepeat fix tree against its inputs (read-only; agent Seq-Baeume 2026-11-05, WINDOWS_REBUILD finding 49).

For every .drm of INPUT_DIR and the same name in TREE (its mods folder when present): both decoded (tools/drm_write);
file header / names / section headers / relocations must be identical; every differing data byte must lie in the word
data +0xc..+0xf of a SoundPlex Sequence node that tools/soundplex_sequence_fix.plan lists as wrong (not 'ok') for the
INPUT copy, and the new word must be the Xbox word; a re-plan of the TREE copy must find 0 wrong words. An INPUT file
with wrong words that TREE does not carry is reported as MISSING, a TREE file without an INPUT as EXTRA.
Xbox source as soundplex_sequence_fix.check_file (--pack PACK first, else the best of every pack holding the name).

Usage (from the repository root):
  ../bin/pyt -t 900 tools/seq_tree_proof.py INPUT_DIR TREE_DIR [--pack PACK]
Per file: words changed (with the repeat byte +0xc / only +0xd..+0xf), changed bytes per offset +0xc..+0xf, other
bytes, header / relocation changes, re-plan count. Exit 1 on any finding that is not a planned Sequence word.
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW
import soundplex_sequence_fix as SQ


def drms(d):
    return {f.lower(): os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith('.drm')}


def prove(pin, pout, pack):
    st, info, XD = SQ.check_file(pin, pack)
    if info is None: return ['no Xbox source'], collections.Counter(), 0, 0
    planned = {(r[0], r[2] + 0xc): r for r in info['rows'] if r[6] != 'ok'}
    A = DW.read(open(pin, 'rb').read(), 'le'); B = DW.read(open(pout, 'rb').read(), 'le')
    probs = []
    if len(A.sections) != len(B.sections) or A.names != B.names or A.pad != B.pad or \
            (A.ver, A.u0, A.u1) != (B.ver, B.u0, B.u1):
        return ['file header / names / section count differ'], collections.Counter(), 0, 0
    words, cnt, other = set(), collections.Counter(), 0
    for k, (s, t) in enumerate(zip(A.sections, B.sections)):
        if (s.type, s.id, s.flags, s.ver, s.spec, s.pad, len(s.data)) != (t.type, t.id, t.flags, t.ver, t.spec, t.pad, len(t.data)):
            probs.append('section %d header differs' % k); continue
        if bytes(s.reloc) != bytes(t.reloc): probs.append('section %d (DTP %d) relocations differ' % (k, s.id))
        if s.data == t.data: continue
        a, b = bytes(s.data), bytes(t.data)
        for i in range(len(a)):
            if a[i] == b[i]: continue
            q = next((i - j for j in range(4) if (k, i - j) in planned), None)
            if q is None:
                other += 1
                if other <= 10: probs.append('section %d (type %d, id %d) +%#x: byte not in a planned Sequence word' % (k, s.type, s.id, i))
                continue
            words.add((k, q)); cnt['+0x%x' % (0xc + i - q)] += 1
    for k, q in sorted(words):
        r = planned[(k, q)]
        if bytes(B.sections[k].data[q:q + 4]) != r[4]:
            probs.append('DTP %d +%#x: new word %s is not the Xbox word %s' % (r[1], q, bytes(B.sections[k].data[q:q + 4]).hex(), r[4].hex()))
    left = [key for key in planned if key not in words]
    if left: probs.append('%d planned word(s) left unchanged' % len(left))
    again = [r for r in SQ.plan(XD, B)['rows'] if r[6] != 'ok']
    if again: probs.append('re-plan of the tree copy: %d wrong word(s)' % len(again))
    rep = sum(1 for key in words if planned[key][4][0] != planned[key][5][0])
    if other > 10: probs.append('... %d other bytes in total' % other)
    return probs, cnt, len(words), rep


def main(a):
    pack = None
    if '--pack' in a: k = a.index('--pack'); pack = a[k + 1]; del a[k:k + 2]
    if len(a) != 2: sys.exit(__doc__)
    din, tree = a
    root = os.path.join(tree, 'mods') if os.path.isdir(os.path.join(tree, 'mods')) else tree
    ins, outs = drms(din), drms(root)
    nbad = 0; tot = collections.Counter()
    for n in sorted(outs):
        if n not in ins: print('%s: EXTRA (no input copy)' % n); nbad += 1
    for n in sorted(ins):
        if n not in outs:
            st, info, XD = SQ.check_file(ins[n], pack)
            wrong = [r for r in info['rows'] if r[6] != 'ok'] if info else []
            if wrong: print('%s: MISSING - input has %d wrong Sequence word(s), the tree does not carry it' % (n, len(wrong))); nbad += 1
            else: print('%s: no wrong Sequence word, not in the tree (ok)' % n)
            continue
        probs, cnt, nw, rep = prove(ins[n], outs[n], pack)
        tot['files'] += 1; tot['words'] += nw; tot['words_repeat_byte'] += rep; tot['words_pad_only'] += nw - rep
        for k, v in cnt.items(): tot['bytes' + k] += v
        print('%s: %d Sequence words (%d with the repeat byte +0xc, %d only +0xd..+0xf), changed bytes %s, '
              'headers + relocations identical: %s, re-plan 0: %s, %s' % (
                  n, nw, rep, nw - rep, dict(sorted(cnt.items())) or '-',
                  'no' if any('header' in p or 'reloc' in p for p in probs) else 'yes',
                  'no' if any('re-plan' in p for p in probs) else 'yes', 'OK' if not probs else 'FAIL'))
        for p in probs: print('   ', p)
        if probs: nbad += 1
    print('TOTAL %s, problems %d' % (dict(tot), nbad))
    print('proof: %s' % ('ok' if not nbad else 'FAIL'))
    return 1 if nbad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
