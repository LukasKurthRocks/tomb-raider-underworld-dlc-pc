"""P5 helper: rewrite one text file as UTF-8 with BOM and CRLF line ends (workspace report rule). Usage (from trudlcport):
../bin/pyt -t 60 work/p5_menu_1311/to_bom_crlf.py FILE"""
import sys

path = sys.argv[1]
text = open(path, encoding='utf-8-sig').read().replace('\r\n', '\n')
open(path, 'w', encoding='utf-8-sig', newline='\r\n').write(text)
print('%s: %d lines, UTF-8 BOM + CRLF' % (path, text.count('\n')))
