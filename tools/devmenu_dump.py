"""List the compiled-in Crystal Dynamics developer debug menu tables of the PC tru.exe (TR8, Steam, image base
0x400000) - read-only, for docs / TruMenu 0.3 (the menu driver is gone in retail, the data is still in .data).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/devmenu_dump.py EXE                     every page / row from FROM to TO (default
                                                                  0x8aaa6c .. 0x8ab3f0) with the code readers
  ../bin/pyt -t 120 tools/devmenu_dump.py EXE --raw [FROM TO]     plain 0x18-byte rows with their strings
  ../bin/pyt -t 120 tools/devmenu_dump.py EXE --md                the same as a Markdown table (README)

Row (0x18 bytes, 6 dwords): +0 type, +4 min (int) / argument (action), +8 max (int), +0xC label (char*),
+0x10 target (variable, function or page), +0x14 mask (flag), value (bool) or callback (int).
Types (all that occur): 0x00 flag (u32 [target] & mask), 0x02 bool (byte [target], +0x14 = 0xffffffff),
0x03 int (s32 [target] in [min, max], callback after a change), 0x09 action (cdecl function, +4 = argument),
0x0A page link (target = page), 0x0B page title (target = parent page), 0x10 end of page (label "", target
0xe7f098), 0x11 page header with a text layout string (label "-abs 160 40 -center"), followed by empty slots.
"Readers" = .text instructions that use the target address (imm32 / disp32 of target .. target+3), decoded with
capstone; for flags the mask is compared with the instruction's immediate.
"""
import sys, os, struct, re
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE

ROW = 0x18
FROM, TO = 0x8aaa6c, 0x8ab3f0
NAMES = {0x00: 'flag', 0x02: 'bool', 0x03: 'int', 0x09: 'action', 0x0a: 'page', 0x0b: 'title', 0x10: 'end',
         0x11: 'header'}


def off_of(secs, a):
    for _, sva, rptr, size, _ in secs:
        if sva <= a < sva + size: return rptr + a - sva
    return -1


def sec_of(secs, a):
    for name, sva, rptr, size, _ in secs:
        if sva <= a < sva + size: return name
    return '-'


def cstr(exe, secs, a, maxlen=80):
    if not (0x400000 <= a < 0x2000000): return None
    o = off_of(secs, a)
    if o < 0: return None
    end = exe.find(b'\0', o, o + maxlen)
    if end < 0: return None
    s = exe[o:end]
    if not all(32 <= c < 127 for c in s): return None
    return s.decode('ascii')


def row(exe, secs, a):
    return struct.unpack_from('<6I', exe, off_of(secs, a))


def fmt(exe, secs, v):
    s = cstr(exe, secs, v)
    return '0x%08x "%s"' % (v, s) if s else '0x%08x' % v


class Code:
    def __init__(self, exe, secs):
        self.exe, self.secs = exe, secs
        t = [s for s in secs if s[0] == '.text'][0]
        self.va, self.raw, self.size = t[1], t[2], t[3]
        self.blob = exe[self.raw:self.raw + self.size]
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    def refs(self, target, span=4):
        """[(va, text)] of .text instructions whose 32-bit operand is target .. target+span-1"""
        out = []
        for t in range(target, target + span):
            pat = struct.pack('<I', t)
            i = self.blob.find(pat)
            while i >= 0:
                # prefer the shortest decode that uses the value as a memory operand [addr] (an "add eax, imm32"
                # one byte back is usually a mis-decode of "test / or dword ptr [addr], imm")
                mem = imm = None
                for back in range(1, 8):
                    s = i - back
                    if s < 0: break
                    for ins in self.md.disasm(self.blob[s:s + 16], self.va + s, 1):
                        if ins.address + ins.size > self.va + i + 3 and ('0x%x' % t) in ins.op_str:
                            text = (ins.address, '%s %s' % (ins.mnemonic, ins.op_str))
                            if ('[0x%x]' % t) in ins.op_str:
                                mem = mem or text
                            else:
                                imm = imm or text
                    if mem: break
                text = mem or imm
                out.append(text if text else (self.va + i, 'imm32'))
                i = self.blob.find(pat, i + 1)
        return sorted(set(out))


def mask_match(target, mask, text):
    """does the instruction test / set a bit of mask (address target, any byte offset)?"""
    m = re.search(r'\[0x([0-9a-f]+)\]', text)
    imm = re.findall(r', (0x[0-9a-f]+|\d+)$', text)
    if not m or not imm: return None
    a = int(m.group(1), 16)
    v = int(imm[0], 0)
    shifted = (mask >> (8 * (a - target))) & 0xffffffff
    return bool(v & shifted)


def walk(exe, secs, lo, hi):
    code = Code(exe, secs)
    rows = []
    a = lo
    page = lo
    header = False                       # a 0x11 page: its 0x10 rows are empty slots, not separate pages
    while a + ROW <= hi:
        if header and page != a and row(exe, secs, a)[0] != 0x10:
            header = False
            page = a
        if a == page: header = row(exe, secs, a)[0] == 0x11
        r = row(exe, secs, a)
        if r[0] not in NAMES and a == page:
            # not a row at a page start: a lone dword between two pages (0x8aaa9c holds the root pointer 0x8aaae8)
            print('# 0x%08x: dword 0x%08x between pages (not a row)' % (a, r[0]))
            a += 4
            page = a
            continue
        rows.append((page, a, r))
        if r[0] == 0x10 and not header: page = a + ROW
        a += ROW
    out = []
    for page, a, r in rows:
        t, p1, p2, label, target, p5 = r
        name = NAMES.get(t, 'type 0x%x' % t)
        lab = cstr(exe, secs, label) if label else None
        info = ''
        readers = []
        if t == 0x00:
            readers = [x for x in code.refs(target) if mask_match(target, p5, x[1]) is not False]
            info = '[0x%08x] & 0x%x' % (target, p5)
        elif t == 0x02:
            readers = code.refs(target, 1)
            info = 'byte [0x%08x] (%s), value 0x%x' % (target, sec_of(secs, target), p5)
        elif t == 0x03:
            readers = [x for x in code.refs(target) if x[0] != p5 and not (p5 and p5 <= x[0] < p5 + 0xb0)]
            info = 's32 [0x%08x] %d .. %d%s' % (target, struct.unpack('<i', struct.pack('<I', p1))[0], p2,
                                                ', callback 0x%08x' % p5 if p5 else '')
        elif t == 0x09:
            arg = cstr(exe, secs, p1) if p1 else None
            info = 'call 0x%08x(%s)' % (target, ('"%s"' % arg) if arg else ('0x%x' % p1))
        elif t in (0x0a, 0x0b):
            info = '%s 0x%08x' % ('-> page' if t == 0x0a else 'parent', target)
        elif t == 0x11:
            info = 'layout'
        out.append((page, a, t, name, lab, info, readers, r))
    return out


def main(argv):
    if not argv: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    base, secs = PE.sections(exe)
    if len(argv) > 1 and argv[1] == '--raw':
        lo = int(argv[2], 16) if len(argv) > 2 else FROM
        hi = int(argv[3], 16) if len(argv) > 3 else TO
        a = lo
        while a + ROW <= hi:
            print('%08x  ' % a + '  '.join(fmt(exe, secs, v) for v in row(exe, secs, a)))
            a += ROW
        return
    md = len(argv) > 1 and argv[1] == '--md'
    rows = walk(exe, secs, FROM, TO)
    pages = sorted(set(p for p, *_ in rows))
    counts = {}
    for _, _, t, name, *_ in rows: counts[name] = counts.get(name, 0) + 1
    if md:
        print('| Page | Row | Type | Label | Target / meaning | Code readers (tru.exe) |')
        print('|---|---|---|---|---|---|')
    last = None
    for page, a, t, name, lab, info, readers, r in rows:
        if t == 0x10 and md: continue
        rd = '; '.join('0x%08x %s' % x for x in readers[:4]) + (' (+%d)' % (len(readers) - 4) if len(readers) > 4
                                                                  else '')
        if t in (0x00, 0x02, 0x03) and not readers: rd = 'none found'
        if md:
            print('| 0x%08x | 0x%08x | %s | %s | %s | %s |' % (page, a, name, lab if lab is not None else '-',
                                                             info, rd or '-'))
            continue
        if page != last:
            print('\npage 0x%08x' % page)
            last = page
        print('  %08x  %-6s %-36s %s' % (a, name, ('"%s"' % lab) if lab is not None else '-', info))
        if t in (0x00, 0x02, 0x03): print('            readers: %s' % (rd or '-'))
    print('\n%s%d rows in %d pages (0x%08x .. 0x%08x): %s' % ('' if not md else '\n', len(rows), len(pages), FROM,
          TO, ', '.join('%s %d' % kv for kv in sorted(counts.items()))))


if __name__ == '__main__':
    main(sys.argv[1:])
