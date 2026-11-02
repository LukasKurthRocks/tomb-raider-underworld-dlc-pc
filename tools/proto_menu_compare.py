"""Compare the prototype (2007) DebugMenuLine tree with the developer table left in the PC tru.exe (read-only;
docs/Befund-Prototyp-2007.md section 3g).

Prototype side: work/proto2007/menus.txt (written by tools/xenon_proto_scan.py menus PE MAP: every DebugMenuLine
table named in the map, rows with type, label, target / callback names). PC side: tools/devmenu_dump.walk over the
.data range 0x8aaa6c..0x8ab3f0 (rows with type, label, target, code readers). Rows are matched by label (labels are
unique enough; separators / titles without label are skipped). Output per prototype menu: each labelled row with
"PC" (same label on PC: PC type, target, readers) or "proto only"; then the PC rows whose label the prototype lacks.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/proto_menu_compare.py EXE [MENUS_TXT]
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import devmenu_dump as DM
import pe_callers as PE

ROWRX = re.compile(r'^\s+\+0x([0-9a-f]+) type 0x([0-9a-f]{2}) min (\S+)\s+max (\S+)\s+"(.*?)"\s+tgt (.*?)  m/cb (.*)$')


def proto_rows(path):
    menus, cur = collections.OrderedDict(), None
    for line in open(path, encoding='utf-8', errors='replace'):
        if line.startswith('== '):
            cur = line[3:].split(' @ ')[0]
            menus[cur] = []
            continue
        m = ROWRX.match(line.rstrip('\n'))
        if m and cur:
            menus[cur].append(dict(off=m.group(1), type=int(m.group(2), 16), label=m.group(5), tgt=m.group(6).strip(),
                                   cb=m.group(7).strip()))
    return menus


def main(argv):
    if not argv:
        sys.exit(__doc__)
    exe_path = argv[0]
    menus_txt = argv[1] if len(argv) > 1 else 'work/proto2007/menus.txt'
    exe = open(exe_path, 'rb').read()
    base, secs = PE.sections(exe)
    pc = DM.walk(exe, secs, DM.FROM, DM.TO)
    pcl = collections.defaultdict(list)
    for page, a, t, name, lab, info, readers, r in pc:
        if lab:
            pcl[lab].append((page, a, t, name, info, readers))
    menus = proto_rows(menus_txt)
    seen = set()
    n_both = n_proto = 0
    for menu, rows in menus.items():
        lab_rows = [r for r in rows if r['label']]
        if not lab_rows:
            continue
        print('\n== %s (%d labelled rows)' % (menu, len(lab_rows)))
        for r in lab_rows:
            hits = pcl.get(r['label'])
            if hits:
                seen.add(r['label'])
                n_both += 1
                page, a, t, name, info, readers = hits[0]
                rd = ', '.join('0x%08x' % x[0] for x in readers[:3]) + (' (+%d)' % (len(readers) - 3)
                                                                      if len(readers) > 3 else '')
                print('  PC    t%02x %-34s proto %-44s | PC %-6s %s | readers %s' % (
                    r['type'], '"%s"' % r['label'][:32], r['tgt'][:44], name, info[:60],
                    rd or ('none' if t in (0, 2, 3) else '-')))
            else:
                n_proto += 1
                print('  proto t%02x %-34s proto %-44s cb %s' % (r['type'], '"%s"' % r['label'][:32], r['tgt'][:44],
                                                                r['cb'][:50]))
    only_pc = [lab for lab in pcl if lab not in seen]
    print('\n== PC rows without a prototype row of the same label: %d' % len(only_pc))
    for lab in only_pc:
        page, a, t, name, info, readers = pcl[lab][0]
        print('  0x%08x %-6s "%s" %s' % (a, name, lab, info[:70]))
    print('\nsummary: prototype labelled rows %d, also on PC %d, prototype only %d; PC labelled rows %d, PC only %d'
          % (n_both + n_proto, n_both, n_proto, len(pcl), len(only_pc)))


if __name__ == '__main__':
    main(sys.argv[1:])
