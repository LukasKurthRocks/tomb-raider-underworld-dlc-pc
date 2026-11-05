"""How did Crystal's own PC build store a word of a given Xbox structure? Base-game pair check for the generic
u16-pair id candidates (read-only; night 04.11., workspace docs Befund-Restrisiken-0411.md, task B).

Every type-7 section (DTP) of the Xbox base-game file NAME (title update first, then layer1 / layer2) is searched for
PATTERN (Xbox bytes, hex, '..' = any byte) at 4-aligned offsets; for each match the word at match + REL is compared
with the same offset of the paired PC section (pc-w, patch.000 first; sections paired by position like the converter,
tools/converter_faults_fix.pairs_by_position). Printed: Xbox / PC bytes, the byte class (same / s32 = u32 swapped /
s16 = u16 halves swapped / raw / other), the value as Xbox u32, and whether that value names a section of the Xbox /
PC file (and the PC u32 value names a PC section). A field that Crystal stored as u32 (s32) in the base game is a u32
on the PC; one stored as s16 is two u16.

Usage (from the repository root):
  ../bin/pyt -t 900 tools/idcand_basepair.py NAME PATTERN [--rel 0xC] [--max 40] [--out FILE]
  e.g. viking_thrall.drm "50......00000000030000000000" --rel 0xc
"""
import sys, os, re, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtp_word_classes as C
import converter_faults_fix as CF


class Sec:
    __slots__ = ('type', 'id', 'data', 'reloc')

    def __init__(self, s):
        self.type, self.id, self.data, self.reloc = s['type'], s['id'], bytes(s['data'] or b''), s['reloc']


class Doc:
    def __init__(self, secs): self.sections = [Sec(s) for s in secs]


def wclass(xb, pb):
    if pb == xb: return 'same' if xb == xb[::-1] else 'raw'
    if pb == xb[::-1]: return 's32'
    if pb == xb[1::-1] + xb[3:1:-1]: return 's16'
    return 'other'


def main(argv):
    def opt(n, d):
        if n in argv:
            k = argv.index(n); v = argv[k + 1]; del argv[k:k + 2]; return v
        return d
    rel = int(opt('--rel', '0'), 16); mx = int(opt('--max', '40')); out = opt('--out', None)
    win = int(opt('--window', '0'), 16)        # also print the words [w - win, w + win] of each match
    name, pat = argv[0], argv[1].lower()
    rx = re.compile(b''.join(b'.' if pat[i:i + 2] == '..' else re.escape(bytes.fromhex(pat[i:i + 2]))
                             for i in range(0, len(pat), 2)), re.S)
    X = C.find(C.BASE, 'be', 'xenon-w' + C.BS + name); P = C.find(C.PC, 'le', 'pc-w' + C.BS + name)
    if X is None or P is None: sys.exit('base pair not found for %s (Xbox %s, PC %s)' % (name, X is not None, P is not None))
    XD, PD = Doc(X), Doc(P)
    xids = {s.id for s in XD.sections}; pids = {s.id for s in PD.sections}
    L = ['%s: Xbox %d sections, PC %d sections' % (name, len(XD.sections), len(PD.sections))]
    st = collections.Counter(); n = 0
    for k, x, p in CF.pairs_by_position(XD, PD):
        if x.type != 7 or len(x.data) != len(p.data): continue
        for m in rx.finditer(x.data):
            o = m.start()
            if o & 3: continue
            w = o + rel
            if w + 4 > len(x.data): continue
            xb, pb = x.data[w:w + 4], p.data[w:w + 4]
            c = wclass(xb, pb); st[c] += 1; n += 1
            xv = struct.unpack('>I', xb)[0]; pv = struct.unpack('<I', pb)[0]
            if n <= mx:
                L.append('  X 7:%-6d / PC 7:%-6d +0x%05x  X %s  PC %s  %-5s Xbox u32 %d%s; PC u32 0x%x%s' % (
                    x.id, p.id, w, xb.hex(), pb.hex(), c, xv, ' (Xbox section)' if xv in xids else '',
                    pv, ' (PC section)' if pv in pids else ''))
                for q in range(max(0, w - win), min(len(x.data) - 3, w + win + 1), 4) if win else ():
                    a, b = x.data[q:q + 4], p.data[q:q + 4]
                    L.append('      %s+0x%05x  X %s  PC %s  %s' % ('>' if q == w else ' ', q, a.hex(), b.hex(), wclass(a, b)))
    L.append('matches %d, classes %s' % (n, dict(st)))
    text = '\n'.join(L) + '\n'
    if out: open(out, 'w', encoding='utf-8').write(text)
    sys.stdout.write(text)


if __name__ == '__main__':
    main(sys.argv[1:])
