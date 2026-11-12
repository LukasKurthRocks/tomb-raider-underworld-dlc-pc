"""Q105 (2026-11-12, group B): which base-game script calls generalbank script 72 (chapter title card,
SetChapterUIData(level, chapter), Befund-17i NOTES item 2/3) with which constant arguments (read-only).

Input: the refs list of tools/drm_script_refs.py (UNITDIR 72) and the intro list of tools/manor_gate_scan.py intros
(--grep "checkpoint|cinematic_object"), both written by the q105 run. For every distinct caller script the
disassembly of tools/script_dis.py is taken (first unit that carries it) and, per call into (8,72), the op03
(push int) constants of the 14 code words before it are printed, plus the intros whose +0x7c is that script.

Usage (from trudlcport): ../bin/pyt -t 900 work/b_nav_1211/q105_chapter_calls.py UNITDIR REFS.txt INTROS.txt
"""
import sys, os, io, re, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import script_dis as SD


def main(unitdir, refs, intros):
    callers = {}
    unit = None
    for line in open(refs, encoding='utf-8', errors='replace'):
        m = re.match(r'^(\S+\.drm)\s', line)
        if m: unit = m.group(1); continue
        m = re.match(r'^\s+script\s+(\d+)\s', line)
        if m: callers.setdefault(int(m.group(1)), []).append(unit)
    owner = {}
    unit = None
    for line in open(intros, encoding='utf-8', errors='replace'):
        m = re.match(r'^== (\S+):', line)
        if m: unit = m.group(1); continue
        m = re.match(r'^\s+intro\s+(\d+)\s+(\S+).*\+0x52\s+(\d+)\s+script\s+(\d+)', line)
        if m: owner.setdefault(int(m.group(4)), []).append('%s intro %s %s +0x52 %s' % (unit, m.group(1), m.group(2), m.group(3)))
    for sid in sorted(callers):
        units = sorted(set(callers[sid]))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            SD.main([os.path.join(unitdir, units[0]), str(sid)])
        lines = buf.getvalue().splitlines()
        calls = []
        for i, l in enumerate(lines):
            if '->ext (8,72)' not in l: continue
            consts = []
            for p in lines[max(0, i - 14):i]:
                m = re.match(r'^\s+[0-9a-f]{4}\s+[0-9a-f]{8}\s+op03\s+(-?\d+)', p)
                if m: consts.append(m.group(1))
            calls.append('%s [%s]' % (l.split('->ext')[1].strip(), ' '.join(consts)))
        print('script %5d  in %d unit(s): %s' % (sid, len(units), ', '.join(u[:-4] for u in units)))
        for o in owner.get(sid, ['(no checkpoint / cinematic intro owns it)']):
            print('    owner: %s' % o)
        for c in calls:
            print('    call %s' % c)


if __name__ == '__main__':
    main(*sys.argv[1:4])
