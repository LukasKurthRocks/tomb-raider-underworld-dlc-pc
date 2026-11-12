"""Group L 12.11. (read-only): list the script sections (type 8) of a PC DRM with id, native package / name and size;
optional substring filter on package / name.
Usage (from trudlcport): ../bin/pyt work/l_combat_1211/script_list.py DRM [TEXT]"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import script_func_list as FL
import menu_dlc_probe as P

S, e = FL.sections(sys.argv[1])
flt = sys.argv[2] if len(sys.argv) > 2 else None
n = 0
for k, q in enumerate(S):
    if q[0] != 8 or not q[2]:
        continue
    n += 1
    pkg, nat, size = P.script_info({'data': q[2], 'reloc': q[3]}, e)
    line = 'section %4d id %6d pkg %s name %s size %d' % (k, q[1], pkg, nat, size)
    if flt is None or flt in line:
        print(line)
print('# %d scripts' % n)
