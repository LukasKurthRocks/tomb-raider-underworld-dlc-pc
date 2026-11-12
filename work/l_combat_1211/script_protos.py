"""Group L 12.11. (read-only): function index -> prototype offset (internal pointer at function entry +0) of one script
section, and every op68 (own virtual call, operand = prototype) in that script whose prototype is the one of FUNC.
Usage (from trudlcport): ../bin/pyt work/l_combat_1211/script_protos.py DRM SCRIPT_ID [FUNC]"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import drm_reloc as R
import script_func_list as FL
import script_dis as SD

S, e = FL.sections(sys.argv[1])
E = '>' if e == 'be' else '<'
sid = int(sys.argv[2])
d, rl = next((q[2], q[3]) for q in S if q[0] == 8 and q[1] == sid and q[2])
rel = R.parse(rl, e)
it = dict(rel.internal)
ents = SD.func_entries(d, rl, e)
proto = {}
for o, i in sorted(ents.items(), key=lambda x: x[1]):
    proto[i] = it.get(o)
    if len(sys.argv) <= 3:
        print('f%d entry 0x%x proto %s' % (i, o, hex(it[o]) if o in it else None))
if len(sys.argv) > 3:
    f = int(sys.argv[3])
    p = proto.get(f)
    print('f%d prototype 0x%x' % (f, p))
    # code ranges
    for o, i in ents.items():
        ct = it.get(o + 0x18)
        if ct is None:
            continue
        cn = struct.unpack_from(E + 'I', d, ct - 4)[0]
        for j in range(cn):
            a = ct + 4 * j
            w = struct.unpack_from(E + 'I', d, a)[0]
            if (w >> 24) in (0x68, 0x6e, 0x67, 0x6d) and it.get(a + 4) == p or it.get(a + 8) == p and (w >> 24) in (0x67, 0x6d):
                print('  called by f%d at +0x%x (op%02x)' % (i, a, w >> 24))
