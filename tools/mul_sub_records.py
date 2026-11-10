"""Subtitle records of cinematic streams (.mul) as the reader 0x4538d0 sees them (read-only; TruMenu 0.22.14 sub.lang
instant switch, 2026-11-10).

The cinematic handler update 0x457100 copies a frame's subtitle text (<= 0xfff bytes, NUL at its end) to 0x9ccfa0 and
calls the reader 0x4538d0 with it. The reader walks '<id>\\r<text>\\r<id>\\r<text>\\r...' (atoi of the id line, then the
next line up to '\\r', 255 bytes at most). Per record this tool prints the cine frame (time = frame / 30 s), the ids,
the text bytes per language (non-ASCII as \\xNN) and whether the non-ASCII bytes form valid UTF-8 - the evidence for the
text encoding the game hands to the subtitle box.

Block mode (default for a file that parses as a .mul): walks the stream blocks (header 0x800, then {u32 type, size,
a, b} + payload, endian from the header's sample rate; tools/mul_convert.py) and reads the {u32 len, text} subtitle
tail of every cine block (type 1) - the whole record, also when it holds one language only. A record need not carry
every language: each language has its own cue times (pdlc2_030_pod: French at frame 956, English / Dutch / Italian at
959, German at 962), and a record without the chosen id leaves the shown line as it is.
Pattern mode (--raw, or a file that is no .mul): a run of at least two '<digits>\\r<text>\\r' entries in the raw bytes
(misses one-language records; can cut a record at an odd byte).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/mul_sub_records.py FILE_OR_DIR [--max N] [--grep TEXT] [--raw]
    FILE_OR_DIR: one .mul (also .mul_NNN language variants), or a folder (every *.mul / *.mul_NNN, not recursive)
    --max N: print at most N records per file (default 6; 0 = all); the summary counts all
    --grep TEXT: print only records containing TEXT (ASCII)
    --raw: pattern mode instead of block mode
    --xbox SRC: compare every file's records with its Xbox original in archive SRC (tools/locals.py, e.g. pack11;
                plain name / _001 = spec ffffffe1, _002 / _004 / _008 / _016 = ffffe002 / 004 / 008 / 010)
Exit code 0 = read, 2 = usage / file error.
"""
import sys, os, re, struct

ENTRY = re.compile(rb'(?:(?<=[\x00\r\n\s])|^)((?:\d{1,2}\r[^\r\x00]{1,400}\r?){2,})')
MUL = re.compile(r'\.mul(_\d{3})?$', re.I)


def utf8_state(b):
    if all(c < 0x80 for c in b): return 'ascii'
    try:
        b.decode('utf-8')
        return 'utf8'
    except UnicodeDecodeError:
        return 'not-utf8'


def entries(blob):
    """[(id, text)] of '<id>\\r<text>\\r...' up to the first part that is no id"""
    parts = blob.split(b'\r')
    out = []
    i = 0
    while i + 1 < len(parts):
        idt, txt = parts[i].strip(b' \t\n'), parts[i + 1]
        if not idt.isdigit(): break
        out.append((int(idt), txt))
        i += 2
    return out


def raw_records(data):
    """pattern mode: (file offset, frame None, entries) of every run of >= 2 entries"""
    for m in ENTRY.finditer(data):
        out = entries(m.group(1))
        if len(out) >= 2: yield m.start(1), None, out


def texty(b):
    b = b.rstrip(b'\0')
    if len(b) < 2: return False
    s = b.decode('utf-8', errors='replace')
    good = sum(ch.isprintable() or ch in '\r\n\t' for ch in s if ch != '�')
    return good >= 0.9 * len(s) and '\r' in s


def tail_at(p, E):
    """offset of the {u32 len, text} subtitle tail of a cine block payload (endian E), or None (as cine_mul_info.py)"""
    for w in range(8, len(p) - 4, 4):
        L = struct.unpack_from(E + 'I', p, w)[0]
        e = w + 4 + L
        if 2 <= L and len(p) - 16 < e <= len(p) and not p[e:].strip(b'\0') and texty(p[w + 4:e]):
            return w
    return None


def mul_endian(d):
    """'<' / '>' when d starts like a .mul header (word 1 = -1, plausible sample rate), else None"""
    if len(d) < 0x810: return None
    for E in ('<', '>'):
        rate, minus1 = struct.unpack_from(E + '2I', d, 0)
        if minus1 == 0xffffffff and 8000 <= rate <= 96000: return E
    return None


def block_records(data, E):
    """block mode: (file offset of the text, cine frame, entries) of every cine block with a subtitle tail"""
    o, frame = 0x800, 0
    while o + 16 <= len(data):
        t, sz, a, b = struct.unpack_from(E + '4I', data, o)
        if o + 16 + sz > len(data): raise ValueError('bad block at 0x%x' % o)
        if t == 1:
            p = data[o + 16:o + 16 + sz]
            w = tail_at(p, E)
            if w is not None:
                L = struct.unpack_from(E + 'I', p, w)[0]
                ents = entries(p[w + 4:w + 4 + L].rstrip(b'\0'))
                if ents: yield o + 16 + w + 4, frame, ents
            frame += 1
        o += 16 + sz
    if o != len(data): raise ValueError('trailing bytes at 0x%x' % o)


VARIANT_SPEC = {'': 0xffffffe1, '_001': 0xffffffe1, '_002': 0xffffe002, '_004': 0xffffe004, '_008': 0xffffe008,
                '_016': 0xffffe010}           # ModLoader suffix (EN FR DE IT ES) -> Xbox archive spec word


def xbox_records(src, fname):
    """block records of the Xbox original of fname (name.mul[_NNN]) in archive src (tools/locals.py SRC), or None"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import locals as LC
    from archive import Archive
    from names import crc
    m = MUL.search(fname)
    base, suf = fname[:m.start()] + '.mul', (m.group(1) or '')
    apath, e, pre = LC.SRC[src]
    A = Archive(apath, e)
    recs = [r for r in (A.find(crc(pre + '\\cinstream\\' + base)) or []) if r['spec'] == VARIANT_SPEC.get(suf)]
    if not recs: return None
    d = A.read(recs[0])
    return list(block_records(d, mul_endian(d) or '>'))


def show(b):
    s = []
    for c in b:
        if c == 0x0a: s.append('\\n')
        elif 32 <= c < 127: s.append(chr(c))
        else: s.append('\\x%02x' % c)
    return ''.join(s)


def main(argv):
    if len(argv) < 2: print(__doc__); return 2
    path = argv[1]
    mx, grep, raw = 6, None, '--raw' in argv
    if '--max' in argv: mx = int(argv[argv.index('--max') + 1])
    if '--grep' in argv: grep = argv[argv.index('--grep') + 1].encode('ascii')
    xsrc = argv[argv.index('--xbox') + 1] if '--xbox' in argv else None
    if os.path.isfile(path): files = [path]
    elif os.path.isdir(path): files = sorted(os.path.join(path, f) for f in os.listdir(path) if MUL.search(f))
    else: files = []
    if not files: print('no .mul files at', path); return 2
    tot = {'records': 0, 'ascii': 0, 'utf8': 0, 'not-utf8': 0, 'multi-line': 0}
    for f in files:
        data = open(f, 'rb').read()
        E = None if raw else mul_endian(data)
        mode = 'blocks %s' % ('LE' if E == '<' else 'BE') if E else 'pattern'
        try: recs = list(block_records(data, E)) if E else list(raw_records(data))
        except ValueError as e:
            print('%s: block walk failed (%s), pattern mode' % (os.path.basename(f), e))
            mode, recs = 'pattern', list(raw_records(data))
        ids_seen = {}
        n = 0
        for off, frame, ents in recs:
            for i, _ in ents: ids_seen[i] = ids_seen.get(i, 0) + 1
            if grep and not any(grep in t for _, t in ents): continue
            tot['records'] += 1
            for _, t in ents:
                tot[utf8_state(t)] += 1
                if b'\n' in t: tot['multi-line'] += 1
            if mx == 0 or n < mx:
                at = '' if frame is None else ' frame %d (%.2f s)' % (frame, frame / 30.0)
                print('%s @0x%x%s: ids %s' % (os.path.basename(f), off, at, ','.join(str(i) for i, _ in ents)))
                for i, t in ents: print('   %2d [%s] %s' % (i, utf8_state(t), show(t)))
            n += 1
        print('%s: %s, %d records; cues per language id: %s' % (os.path.basename(f), mode, len(recs),
              ', '.join('%d:%d' % kv for kv in sorted(ids_seen.items())) or '-'))
        if xsrc:
            xr = xbox_records(xsrc, os.path.basename(f))
            if xr is None: print('   xbox %s: no record of that name / language spec' % xsrc); continue
            pc = [(fr, ents) for _, fr, ents in recs]
            xb = [(fr, ents) for _, fr, ents in xr]
            same = sum(1 for a, b in zip(pc, xb) if a == b)
            print('   xbox %s: %d records, %d identical to PC (frame, ids, text bytes)%s' % (
                xsrc, len(xb), same, '' if same == len(xb) == len(pc) else ' - DIFFERS'))
            for a, b in zip(pc, xb):
                if a != b: print('     pc frame %s ids %s / xbox frame %s ids %s' % (
                    a[0], ','.join(str(i) for i, _ in a[1]), b[0], ','.join(str(i) for i, _ in b[1])))
    print('summary: %d records; language entries: %d ascii, %d valid UTF-8 with non-ASCII, %d non-ASCII not UTF-8; '
          '%d entries hold a \\n (more than one box line)' % (tot['records'], tot['ascii'], tot['utf8'], tot['not-utf8'],
                                                          tot['multi-line']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
