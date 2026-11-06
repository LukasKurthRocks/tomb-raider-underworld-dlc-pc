"""Find ASCII substrings in an Xbox 360 memory image dumped from Xenia (guest base 0x82000000) and print the start
address of every zero-terminated string that contains them (read-only).

2026-11-06 15h crash / finisher: locate the TU / retail names "EnemyVaultedData", "EnemyState_Vaulted" etc. so that
tools/ppc_addr_scan.py can list the code that builds their addresses (the enemy side of message 0xf4).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/xbox_find_str.py IMAGE.bin TEXT[,TEXT..] [--max N]
  IMAGE.bin  e.g. work/xenia_dump/tu_image_82000000.bin
  --max N    print at most N hits per text (default 40)
"""
import sys

BASE = 0x82000000


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    data = open(argv[0], 'rb').read()
    texts = argv[1].split(',')
    limit = int(argv[argv.index('--max') + 1]) if '--max' in argv else 40
    for t in texts:
        needle = t.encode('ascii')
        print('== %r' % t)
        seen = set()
        pos = data.find(needle)
        n = 0
        while pos >= 0 and n < limit:
            start = pos
            while start > 0 and 0x20 <= data[start - 1] < 0x7f:
                start -= 1
            end = data.find(b'\0', pos)
            if start not in seen:
                seen.add(start)
                n += 1
                print('  0x%08x %r' % (BASE + start, data[start:end if end >= 0 else pos + 64][:96].decode('ascii', 'replace')))
            pos = data.find(needle, pos + 1)


if __name__ == '__main__':
    main(sys.argv[1:])
