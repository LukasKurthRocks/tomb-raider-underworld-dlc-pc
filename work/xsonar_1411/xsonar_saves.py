"""xsonar 1411 (read-only): which level / unit each Xenia TRU save holds - prints the UTF-16 display name of each
save header and the unit-like ASCII names (dlc_*, dlc2_*, l<digit>_*) found in the save data, with the file date.

Usage (from trudlcport): ../bin/pyt work/xsonar_1411/xsonar_saves.py DIR [DIR ...]
  DIR = a folder holding 534307EC (Xenia content profile folder or a save-library entry); only opens files to read.
"""
import os
import re
import sys
import time

UNIT = re.compile(rb'(?:dlc2?_[a-z0-9_]{3,40}|l[0-9]{1,2}_[a-z0-9_]{3,40})')


def utf16_strings(b, minlen=4):
    out, cur = [], []
    for i in range(0, len(b) - 1, 2):
        c = (b[i] << 8) | b[i + 1]                       # Xbox headers are big-endian UTF-16
        if 32 <= c < 127:
            cur.append(chr(c))
        else:
            if len(cur) >= minlen:
                out.append(''.join(cur))
            cur = []
    if len(cur) >= minlen:
        out.append(''.join(cur))
    return out


def main(dirs):
    for d in dirs:
        t = os.path.join(d, '534307EC')
        if not os.path.isdir(t):
            print('%s: no 534307EC' % d)
            continue
        sd = os.path.join(t, '00000001')
        for slot in sorted(os.listdir(sd)):
            f = os.path.join(sd, slot, slot)
            if not os.path.isfile(f):
                continue
            hdr = os.path.join(t, 'Headers', '00000001', slot + '.header')
            hb = open(hdr, 'rb').read() if os.path.isfile(hdr) else b''
            data = open(f, 'rb').read()
            names = {}
            for mo in UNIT.finditer(data):
                n = mo.group(0).decode('ascii')
                names[n] = names.get(n, 0) + 1
            top = sorted(names.items(), key=lambda x: -x[1])[:8]
            print('%s | %s | %s | header %s | units %s' % (
                os.path.basename(d.rstrip('\\/')), slot,
                time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(f))),
                ' / '.join(utf16_strings(hb)) or '-', ', '.join('%s x%d' % x for x in top) or '-'))


if __name__ == '__main__':
    main(sys.argv[1:])
