"""P1 (2026-11-13): class chain of per-instance scripts (read-only).

Script section root (ENGINE.md 7.1, tools/script_conv.py): +0x08 name (pointer), +0x14 self id, +0x18 super id. A
per-instance script of 104 / 120 / 184 B has no own functions - its behaviour is the class it derives from. This tool
prints for each given script id the chain self -> super -> ... with name, size, function count, and (with --describe)
the tools/manor_gate_scan.py summary (members, calls, strings, sticky access) of every script in the chain that has
functions. Scripts not in the unit DRM are looked up in the extra DRMs given with --also (e.g. generalbank.drm or an
object DRM).

Usage (from trudlcport):
  ../bin/pyt -t 300 work/p1_med_1311/p1_script_class.py UNIT.drm SID[,SID..] [--describe] [--also A.drm,B.drm]
"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import manor_gate_scan as MG
import drm_reloc as R


def opt(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


class Lib:
    """type-8 sections by id over several DRMs (first file wins)"""

    def __init__(self, paths):
        import drm_write as DW
        self.secs = {}
        for p in paths:
            D = DW.read(open(p, 'rb').read(), 'le')
            for s in D.sections:
                if s.type == 8 and s.id not in self.secs:
                    self.secs[s.id] = (os.path.basename(p), s)

    def root(self, sid):
        if sid not in self.secs: return None
        fn, s = self.secs[sid]
        d = bytes(s.data)
        rel = R.parse(bytes(s.reloc), 'le')
        it = dict(rel.internal)
        nm = ''
        p = it.get(8)
        if p is not None:
            z = d.find(b'\0', p, p + 80)
            nm = d[p:z].decode('ascii', 'replace')
        selfid, sup = struct.unpack_from('<II', d, 0x14)
        return dict(file=fn, size=len(d), name=nm, self=selfid, super=sup)


def main(argv):
    describe = '--describe' in argv
    if describe: argv.remove('--describe')
    also = opt(argv, '--also', '')
    if len(argv) < 2:
        print(__doc__); return 2
    unit = argv[0]
    sids = [int(x) for x in argv[1].split(',')]
    lib = Lib([unit] + [a for a in also.split(',') if a])
    us = MG.UnitScan(unit, MG.load_names(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'generic',
                                                       'lists', 'pc_objectlist.txt')))
    for sid in sids:
        chain, cur, seen = [], sid, set()
        while cur and cur not in seen and len(chain) < 12:
            seen.add(cur)
            r = lib.root(cur)
            if r is None:
                chain.append('%d (not in the given DRMs)' % cur); break
            chain.append('%d %s [%s, %d B]' % (cur, r['name'] or '-', r['file'], r['size']))
            cur = r['super']
        print('script %d owner %s: %s' % (sid, MG.owner_text(us, sid), ' -> '.join(chain)))
        if describe:
            for c in chain:
                cid = int(c.split()[0])
                if cid not in lib.secs or lib.secs[cid][0] != os.path.basename(unit): continue
                sc = us.script(cid)
                if sc is None or sc.info[1]: continue        # native classes (instance, gamebase ...): no script code
                out = []
                MG.describe_script(us, cid, out)
                if any(l.strip().startswith('f') for l in out):
                    print('\n'.join(out))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
