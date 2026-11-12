"""Group N 12.11.2026: rewrite one text file as UTF-8 with BOM and CRLF line ends (workspace docs rule).
Usage (from trudlcport): ../bin/pyt -t 60 work/n_research_1211/to_bom_crlf.py FILE"""
import sys
p = sys.argv[1]
t = open(p, encoding='utf-8-sig').read().replace('\r\n', '\n').replace('\n', '\r\n')
open(p, 'w', encoding='utf-8-sig', newline='').write(t)
print('%s: %d characters, BOM + CRLF' % (p, len(t)))
