"""Subtitle records of cinematic streams (.mul) as the reader 0x4538d0 sees them (read-only; TruMenu 0.22.14 sub.lang
instant switch, 2026-11-10).

The cinematic handler update 0x457100 copies a frame's subtitle text (<= 0xfff bytes, NUL at its end) to 0x9ccfa0 and
calls the reader 0x4538d0 with it. The reader walks '<id>\\r<text>\\r<id>\\r<text>\\r...' (atoi of the id line, then the
next line up to '\\r', 255 bytes at most). This tool finds such records in the raw file bytes (a run of at least two
'<digits>\\r<text>\\r' entries), and prints per record the ids, the text bytes per language (non-ASCII as \\xNN) and
whether the non-ASCII bytes form valid UTF-8 - the evidence for the text encoding the game hands to the subtitle box.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/mul_sub_records.py FILE_OR_DIR [--max N] [--grep TEXT]
    FILE_OR_DIR: one .mul, or a folder (every *.mul in it, not recursive)
    --max N: print at most N records per file (default 6); the summary counts all
    --grep TEXT: print only records containing TEXT (ASCII)
Exit code 0 = read, 2 = usage / file error.
"""
import sys, os, re

ENTRY = re.compile(rb'(?:(?<=[\x00\r\n\s])|^)((?:\d{1,2}\r[^\r\x00]{1,400}\r?){2,})')


def utf8_state(b):
    if all(c < 0x80 for c in b): return 'ascii'
    try:
        b.decode('utf-8')
        return 'utf8'
    except UnicodeDecodeError:
        return 'not-utf8'


def records(data):
    for m in ENTRY.finditer(data):
        blob = m.group(1)
        parts = blob.split(b'\r')
        out = []
        i = 0
        while i + 1 < len(parts):
            idt, txt = parts[i], parts[i + 1]
            if not idt.isdigit(): break
            out.append((int(idt), txt))
            i += 2
        if len(out) >= 2: yield m.start(1), out


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
    mx, grep = 6, None
    if '--max' in argv: mx = int(argv[argv.index('--max') + 1])
    if '--grep' in argv: grep = argv[argv.index('--grep') + 1].encode('ascii')
    files = [path] if os.path.isfile(path) else sorted(
        os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith('.mul'))
    if not files: print('no .mul files at', path); return 2
    tot = {'records': 0, 'ascii': 0, 'utf8': 0, 'not-utf8': 0, 'multi-line': 0}
    for f in files:
        data = open(f, 'rb').read()
        n = 0
        for off, ents in records(data):
            if grep and not any(grep in t for _, t in ents): continue
            tot['records'] += 1
            for _, t in ents:
                tot[utf8_state(t)] += 1
                if b'\n' in t: tot['multi-line'] += 1
            if n < mx:
                print('%s @0x%x: ids %s' % (os.path.basename(f), off, ','.join(str(i) for i, _ in ents)))
                for i, t in ents: print('   %2d [%s] %s' % (i, utf8_state(t), show(t)))
            n += 1
    print('summary: %d records; language entries: %d ascii, %d valid UTF-8 with non-ASCII, %d non-ASCII not UTF-8; '
          '%d entries hold a \\n (more than one box line)' % (tot['records'], tot['ascii'], tot['utf8'], tot['not-utf8'],
                                                          tot['multi-line']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
