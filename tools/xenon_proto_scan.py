"""Read-only scans of a decrypted Xbox 360 prototype image (TR8 dev-kit build, from tools/xex_extract.py with the
dev-kit key) together with its linker .map file (MSVC "Publics by Value" + "Static symbols").

The image is in memory layout (file offset = VA - 0x82000000), big-endian. Nothing is executed; the map is parsed as
plain text. Used for docs/Befund-Prototyp-2007.md.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/xenon_proto_scan.py menus PE MAP           every DebugMenuLine table named in the map
                                                                     (rows of 0x18 bytes: type, min, max, label*,
                                                                     target, mask/callback) with symbol names
  ../bin/pyt -t 120 tools/xenon_proto_scan.py find PE MAP WORD [...]  printable ASCII strings (len >= 4) that contain
                                                                     WORD (case-insensitive), with VA and the
                                                                     owning map symbol / object file
  ../bin/pyt -t 120 tools/xenon_proto_scan.py dwords PE MAP VA [...]  where the big-endian dword VA occurs in the
                                                                     image (data references / jump tables)
  ../bin/pyt -t 120 tools/xenon_proto_scan.py table PE MAP VA N      N big-endian dwords from VA with symbol names
  ../bin/pyt -t 120 tools/xenon_proto_scan.py objstat MAP           symbol count per object file (top 60) and
                                                                     source paths found in string names
  ../bin/pyt -t 120 tools/xenon_proto_scan.py sym MAP REGEX          map symbols whose raw name matches REGEX
"""
import sys, re, struct, bisect

BASE = 0x82000000
ROW = 0x18


def load_map(path):
    syms = []  # (va, raw, obj, is_func)
    for line in open(path, 'r', encoding='latin-1'):
        p = line.split()
        if len(p) < 4 or not re.match(r'^[0-9a-f]{4}:[0-9a-f]{8}$', p[0]):
            continue
        if not re.match(r'^[0-9a-f]{8}$', p[2]):
            continue
        va = int(p[2], 16)
        if va < BASE:
            continue
        syms.append((va, p[1], p[-1], 'f' in p[3:-1]))
    syms.sort()
    return syms


def demangle(raw):
    """Very small MSVC demangler: '?name@Class@ns@@...' -> 'ns::Class::name'; strings get '<str>'."""
    if raw.startswith('??_C@'):
        return '<str>'
    if raw.startswith('?') and not raw.startswith('??'):
        head = raw[1:].split('@@')[0]
        parts = [x for x in head.split('@') if x]
        return '::'.join(reversed(parts))
    if raw.startswith('??0') or raw.startswith('??1'):
        head = raw[3:].split('@@')[0]
        parts = [x for x in head.split('@') if x]
        return '::'.join(reversed(parts)) + ('::ctor' if raw[2] == '0' else '::dtor')
    return raw


class Img:
    def __init__(self, pe, mapf):
        self.d = open(pe, 'rb').read()
        self.syms = load_map(mapf) if mapf else []
        self.vas = [s[0] for s in self.syms]
        self.exact = {}
        for va, raw, obj, fn in self.syms:
            self.exact.setdefault(va, []).append((raw, obj))

    def u32(self, va):
        o = va - BASE
        if 0 <= o <= len(self.d) - 4:
            return struct.unpack_from('>I', self.d, o)[0]
        return None

    def cstr(self, va, maxlen=120):
        o = va - BASE
        if not (0 <= o < len(self.d)):
            return None
        e = self.d.find(b'\0', o, o + maxlen)
        if e < 0:
            return None
        s = self.d[o:e]
        if not all(32 <= c < 127 or c == 9 for c in s):
            return None
        return s.decode('ascii')

    def owner(self, va):
        i = bisect.bisect_right(self.vas, va) - 1
        if i < 0:
            return '-', '-'
        s = self.syms[i]
        return '%s+0x%x' % (demangle(s[1]), va - s[0]), s[2]

    def name(self, va):
        if va in self.exact:
            raw, obj = self.exact[va][0]
            return demangle(raw)
        return None

    def fmt(self, v):
        s = self.cstr(v) if BASE <= v < BASE + len(self.d) else None
        n = self.name(v)
        out = '0x%08x' % v
        if n and n != '<str>':
            out += ' ' + n
        if s is not None and (n is None or n == '<str>') and len(s) > 0:
            out += ' "%s"' % s
        elif n is None and BASE <= v < BASE + len(self.d):
            out += ' (%s)' % self.owner(v)[0][:48]
        return out


def cmd_menus(img):
    tabs = [(va, raw) for va, raw, obj, fn in img.syms if 'DebugMenuLine@@' in raw and '@@3' in raw]
    tabs.sort()
    for i, (va, raw) in enumerate(tabs):
        nxt = tabs[i + 1][0] if i + 1 < len(tabs) else va + 0x2000
        print('== %s @ 0x%08x (%s)' % (demangle(raw), va, img.owner(va)[1]))
        a = va
        n = 0
        while a + ROW <= nxt and n < 200:
            t, mn, mx, lab, tgt, msk = [img.u32(a + 4 * k) for k in range(6)]
            label = img.cstr(lab) if lab else ''
            if label is None:
                label = '?0x%08x' % lab
            mns = img.fmt(mn) if mn >= BASE and mn < BASE + len(img.d) else '%d' % struct.unpack('>i', struct.pack('>I', mn))[0]
            print('  +0x%03x type 0x%02x min %-10s max %-10d %-34s tgt %s  m/cb %s' % (
                a - va, t, mns, struct.unpack('>i', struct.pack('>I', mx))[0],
                '"%s"' % label, img.fmt(tgt), img.fmt(msk) if msk > 0xffff else '0x%x' % msk))
            n += 1
            a += ROW
            if t == 0x10:
                # skip the trailing empty slots of the same table silently
                break


def cmd_find(img, words):
    d = img.d
    words_l = [w.lower().encode('ascii') for w in words]
    for m in re.finditer(rb'[\x20-\x7e\t]{4,}', d):
        s = m.group(0)
        sl = s.lower()
        for w in words_l:
            if w in sl:
                va = BASE + m.start()
                own, obj = img.owner(va)
                print('0x%08x  %-60s  [%s | %s]' % (va, s.decode('ascii')[:160], own[:70], obj))
                break


def cmd_dwords(img, vas):
    for v in vas:
        pat = struct.pack('>I', v)
        hits = [BASE + m.start() for m in re.finditer(re.escape(pat), img.d) if m.start() % 4 == 0]
        print('0x%08x: %d hits' % (v, len(hits)))
        for h in hits[:40]:
            own, obj = img.owner(h)
            print('   at 0x%08x  [%s | %s]' % (h, own[:70], obj))


def cmd_objstat(mapf):
    syms = load_map(mapf)
    cnt = {}
    for va, raw, obj, fn in syms:
        cnt[obj] = cnt.get(obj, 0) + 1
    for obj, c in sorted(cnt.items(), key=lambda x: -x[1])[:60]:
        print('%6d  %s' % (c, obj))
    paths = set()
    for va, raw, obj, fn in syms:
        if raw.startswith('??_C@') and '?2' in raw:
            # MSVC string-literal names keep the start of the text; '?2' = backslash, '?4' = '.'
            body = raw.split('@', 3)[-1]
            body = body.replace('?2', '\\').replace('?4', '.').replace('?3', ':').replace('?5', ' ').replace('?9', '-')
            m = re.match(r'([A-Za-z0-9_\\.:-]+)', body)
            if m and '\\' in m.group(1):
                paths.add((m.group(1), obj))
    print('== %d source-path string literals (prefix as kept in the mangled name)' % len(paths))
    for p, obj in sorted(paths):
        print('  %-70s %s' % (p, obj))


def cmd_sym(mapf, rx):
    r = re.compile(rx)
    for va, raw, obj, fn in load_map(mapf):
        if r.search(raw):
            print('0x%08x %s %-60s %s' % (va, 'f' if fn else 'd', demangle(raw)[:60], obj))


def main(a):
    if len(a) < 2:
        sys.exit(__doc__)
    if a[0] == 'menus':
        cmd_menus(Img(a[1], a[2]))
    elif a[0] == 'find':
        cmd_find(Img(a[1], a[2]), a[3:])
    elif a[0] == 'dwords':
        cmd_dwords(Img(a[1], a[2]), [int(x, 16) for x in a[3:]])
    elif a[0] == 'table':
        img = Img(a[1], a[2])
        va, n = int(a[3], 16), int(a[4])
        for k in range(n):
            print('  [%2d] 0x%08x: %s' % (k, va + 4 * k, img.fmt(img.u32(va + 4 * k))))
    elif a[0] == 'objstat':
        cmd_objstat(a[1])
    elif a[0] == 'sym':
        cmd_sym(a[1], a[2])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
