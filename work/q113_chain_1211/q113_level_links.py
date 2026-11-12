"""Q113 (2026-11-12): which script of which base-game unit names another unit (level-end / level-change targets).

Read-only. For every unit DRM in UNITDIR: every script section (type 8) whose readable strings name a base-game unit
(l1_..l7_ names of the extracted set, case-insensitive, whole string) other than the unit itself. The owner intro of
the script comes from INTROS (tools/manor_gate_scan.py intros output: '== unit:' / '   intro N name live (...) +0x52 K
script S'). Script strings that are log texts ('load into l1_seatop, godray 0') are listed too (marked 'text').

Usage (from trudlcport): ../bin/pyt -t 600 work/q113_chain_1211/q113_level_links.py UNITDIR INTROS OUT
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
import drm_write as DW


def main(unitdir, intros, out):
    units = sorted(n[:-4].lower() for n in os.listdir(unitdir) if n.lower().endswith('.drm'))
    names = set(units)
    owner = {}
    u = None
    for ln in open(intros, encoding='utf-8', errors='replace'):
        m = re.match(r'^== (\S+):', ln)
        if m: u = m.group(1); continue
        m = re.match(r'^\s+intro\s+(\d+)\s+(\S+)\s+live \(\s*(\S+)\s+(\S+)\s+(\S+)\)\s+\+0x52\s+(\d+)\s+script\s+(\d+)', ln)
        if m and u: owner[(u, int(m.group(7)))] = 'intro %s %s +0x52 %s at (%s %s %s)' % (
            m.group(1), m.group(2), m.group(6), m.group(3), m.group(4), m.group(5))
    rx = re.compile(rb'[\x20-\x7e]{5,}')
    lines, seen = [], set()
    for unit in units:
        D = DW.read(open(os.path.join(unitdir, unit + '.drm'), 'rb').read(), 'le')
        for s in D.sections:
            if s.type != 8: continue
            hits = []
            for m in rx.finditer(s.data):
                t = m.group().decode('ascii')
                tl = t.lower()
                if tl in names and tl != unit: hits.append(t)
                elif tl != unit and any(re.search(r'\b%s\b' % re.escape(n), tl) for n in names if n != unit) and \
                        not tl.endswith(('_mus_01', '_mus_02', '_mus_03')):
                    hits.append('text: ' + t)
            if not hits: continue
            key = (s.id, tuple(hits))
            dup = ' (same script also in an earlier unit)' if key in seen else ''
            seen.add(key)
            lines.append('%-30s script %6d  owner %-70s -> %s%s' % (
                unit, s.id, owner.get((unit, s.id), 'no intro (level / class script)'), ' | '.join(hits), dup))
    open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    print('%d units, %d script hits -> %s' % (len(units), len(lines), out))
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    sys.exit(main(*sys.argv[1:4]))
