"""PW.1 (2026-11-13, Q124): scan two PC trees for script init words whose walker label is ('init', 10, depth, k,
USERTYPE) (default userType 4697 = the instance / marker reference of the dungeon water scripts; --usertype -1 = every
userType, first init word only) and report where the
trees differ, with both u16 readings and whether the value is an intro / marker id of the same DRM.

Read-only (copy the trees' files elsewhere first if they live in the game folder - this tool only opens files).
Usage (from the repository root):
  ../bin/pyt -t 1800 work/pw1_1311/pw1_instref_scan.py OWN_DIR OLD_DIR [--usertype 4697] [--glob dlc*]
Prints one line per differing word and a summary per DRM. Exit code 0.
"""
import sys, os, glob, struct, collections
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import drm_write as DW, drm_reloc as R, unit_ids as U
import script_conv as SC


def intro_ids(D):
    secs = [dict(type=s.type, data=s.data, reloc=s.reloc, size=len(s.data)) for s in D.sections]
    try:
        L = U.level_info(secs, 'le')
    except Exception:
        return set()
    if not L: return set()
    ids = set()
    for si, o in L['intros']:
        ids.add(struct.unpack_from('<I', secs[si]['data'], o + 0x58)[0])
    # second intro list (unit DTP root +0x1c count / +0x20 records, object 0xfffa markers)
    si = L['intros'][0][0] if L['intros'] else None
    if si is not None:
        d = secs[si]['data']; ri = dict(R.parse(secs[si]['reloc'], 'le').internal)
        n = struct.unpack_from('<I', d, 0x1c)[0]; t = ri.get(0x20)
        if t is not None and n < 4096:
            for k in range(n):
                if t + 0x90 * k + 0x5c <= len(d):
                    ids.add(struct.unpack_from('<I', d, t + 0x90 * k + 0x58)[0])
    return ids


def main(argv):
    argv = list(argv)
    ut = 4697; pat = 'dlc*.drm'
    if '--usertype' in argv:
        i = argv.index('--usertype'); ut = int(argv[i + 1]); del argv[i:i + 2]
    if '--glob' in argv:
        i = argv.index('--glob'); pat = argv[i + 1]; del argv[i:i + 2]
    own, old = argv
    tot = collections.Counter()
    for p in sorted(glob.glob(os.path.join(own, pat))):
        q = os.path.join(old, os.path.basename(p))
        if not os.path.isfile(q): continue
        A = DW.read(open(p, 'rb').read(), 'le'); B = DW.read(open(q, 'rb').read(), 'le')
        bmap = {(s.type, s.id): s for s in B.sections}
        ids_a = intro_ids(A)
        n = 0
        for s in A.sections:
            if s.type != 8: continue
            t = bmap.get((8, s.id))
            if t is None or len(t.data) != len(s.data): continue
            try:
                W = SC.Walk(s.data, R.parse(s.reloc, 'le'), 'le').run()
            except Exception:
                continue
            for o, lab in W.lab.items():
                if not (isinstance(lab, tuple) and lab[:2] == ('init', 10) and len(lab) >= 5 and
                        (lab[4] == ut or (ut < 0 and lab[3] == 0))):
                    continue
                tot['ut %d' % lab[4]] += 0
                wa, wb = s.data[o:o + 4], t.data[o:o + 4]
                tot['words'] += 1
                if wa == wb: continue
                n += 1; tot['diff'] += 1
                va = struct.unpack('<H', wa[:2])[0]; vb = struct.unpack('<H', wb[:2])[0]
                ka = 'intro' if va in ids_a else '-'
                kb = 'intro' if vb in ids_a else '-'
                tot['own_is_intro' if ka == 'intro' else 'own_not_intro'] += 1
                tot['old_is_intro' if kb == 'intro' else 'old_not_intro'] += 1
                print('  %-34s script %5d +0x%04x own %s (u16 %5d %s) old %s (u16 %5d %s)' % (
                    os.path.basename(p), s.id, o, wa.hex(), va, ka, wb.hex(), vb, kb))
        if n: print('== %s: %d differing userType-%d init words' % (os.path.basename(p), n, ut))
    print('\nsummary:', dict(tot))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
