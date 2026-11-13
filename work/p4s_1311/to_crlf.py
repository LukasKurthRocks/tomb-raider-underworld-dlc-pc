"""LF -> CRLF for the given text files (idempotent, no BOM added). Usage: pyt to_crlf.py FILE..."""
import sys
for p in sys.argv[1:]:
    b = open(p, 'rb').read()
    n = b.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    if n != b: open(p, 'wb').write(n)
    print(p, 'crlf', n.count(b'\r\n'), 'changed' if n != b else 'same')
