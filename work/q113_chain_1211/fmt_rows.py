"""Q113 helper: format the generator rows (work/b_nav_1211/q105_chaporder_rows.txt) like the kChapOrder block in
TruMenu.cpp (lines <= 120 characters: a long heading goes to a continuation line, split into adjacent C strings).
Read-only; prints to OUT. Usage (from trudlcport): ../bin/pyt -t 60 work/q113_chain_1211/fmt_rows.py ROWS OUT
"""
import sys, re


def split_c(s, width):
    """split the C string body s into pieces of <= width characters, never inside an escape (\\303)"""
    out = []
    while len(s) > width:
        cut = width
        while cut > 0 and (s[cut - 1] == '\\' or re.match(r'\\\d{0,2}$', s[max(0, cut - 3):cut]) or s[cut - 1] != ' '):
            cut -= 1
        if cut <= 0: cut = width
        out.append(s[:cut]); s = s[cut:]
    out.append(s)
    return out


def main(rows, out):
    lines = []
    for ln in open(rows, encoding='utf-8'):
        ln = ln.rstrip('\n')
        if len(ln) <= 120: lines.append(ln); continue
        m = re.match(r'^(\s*\{"[^"]*", "[^"]*", false, "[0-9 ]*",) (nullptr|"(.*)")\},$', ln)
        head = m.group(3)
        if m.group(2) == 'nullptr':
            lines += [m.group(1), '     nullptr},']; continue
        if len(m.group(1)) + len(head) + 5 <= 120:
            lines += [m.group(1) + ' "%s"},' % head]; continue
        lines.append(m.group(1))
        parts = split_c(head, 110)
        for k, p in enumerate(parts):
            lines.append('     "%s"%s' % (p, '},' if k == len(parts) - 1 else ''))
    open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    print('%d lines, longest %d' % (len(lines), max(len(x) for x in lines)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
