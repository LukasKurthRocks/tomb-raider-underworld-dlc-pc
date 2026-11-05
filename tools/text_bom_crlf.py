"""Rewrite text files as UTF-8 with BOM and CRLF line ends (the workspace rule for new .md / .ps1 files).

Reads each file as UTF-8 (an existing BOM is dropped first), turns CRLF / CR / LF into CRLF, writes it back with a BOM
and prints the line count and the CR / LF counts after the rewrite. Files that are already BOM + CRLF are left as they
are (reported as `unchanged`).

Usage (from the repository root):
  ../bin/pyt -t 60 tools/text_bom_crlf.py FILE [FILE ...]
"""
import sys

BOM = b'\xef\xbb\xbf'


def convert(path):
    raw = open(path, 'rb').read()
    body = raw[3:] if raw.startswith(BOM) else raw
    text = body.decode('utf-8')
    norm = text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')
    out = BOM + norm.encode('utf-8')
    state = 'unchanged' if out == raw else 'rewritten'
    if out != raw:
        open(path, 'wb').write(out)
    print('%-9s %s: %d lines, CR %d, LF %d, BOM yes' % (state, path, norm.count('\r\n'), out.count(b'\r'),
                                                         out.count(b'\n')))


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    for p in argv:
        convert(p)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
