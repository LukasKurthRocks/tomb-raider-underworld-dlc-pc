"""P4.8 (2026-11-14): the base-type-10 init words (first word of each init block, every userType) that differ between
two PC trees (own <-> old), per Xbox userType: how many the new rule (script_learn.instref) touches, how many the gate
(tools/instref_gate.py: Xbox high u16 = an intro / marker id of a unit of the tree) judges, and which tree the
rule's word agrees with. Also lists the userType-4261 words whose Xbox value is no intro / marker id. Read-only.

Usage (from the repository root):
  ../bin/pyt -t 3000 work/p48_1411/p48_ut_table.py OWN_DIR OLD_DIR [--pack pack10] [--glob dlc*]
"""
import sys, os, struct, collections, fnmatch
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
argv = sys.argv[1:]
pat = 'dlc*.drm'
if '--pack' in argv:
    i = argv.index('--pack'); os.environ['TRUDLC_PACK_FIRST'] = argv[i + 1]; del argv[i:i + 2]
if '--glob' in argv:
    i = argv.index('--glob'); pat = argv[i + 1]; del argv[i:i + 2]
own, old = argv
import drm_write as DW, instref_gate as IG, script_learn as SL, dlc_generic as DG
from convert_dlc import raw_dlc
ids = DG.DlcIds()
pm, pc_all, notes = IG.intro_pairs([own], raw_dlc)
T = collections.defaultdict(collections.Counter)
files = collections.defaultdict(set)
notintro = collections.Counter()
for nm in IG.tree_names([own]):
    if not fnmatch.fnmatch(os.path.basename(nm), pat): continue
    q = os.path.join(old, nm)
    if not os.path.isfile(q): continue
    XD, PD = IG.load_pair([own], nm, raw_dlc)
    if XD is None: continue
    OD = DW.read(open(q, 'rb').read(), 'le')
    opool = {(s.type, s.id): s for s in OD.sections}
    for pid, xid, o, lab, xw, pw in IG.ref_words(XD, PD, ids, -1):
        t = opool.get((8, pid))
        if t is None or o + 4 > len(t.data): continue
        ow = bytes(t.data[o:o + 4])
        ut = lab[4]
        if ut == SL.INSTREF_UT and IG.judge(xw, pw, pm) == 'not_intro':
            notintro[(os.path.basename(nm), xid, struct.unpack('>H', xw[:2])[0])] += 1
        if pw == ow: continue
        r = T[ut]; r['diff'] += 1; files[ut].add(os.path.basename(nm))
        touched = SL.instref(lab, xw)
        nw = SL.apply_word(xw, SL.INSTREF_CLASS, ids) if touched else pw
        if touched: r['rule_touches'] += 1
        j = IG.judge(xw, nw, pm)
        r['gate_' + j] += 1
        r['new=old' if nw == ow else 'new=own' if nw == pw else 'new=neither'] += 1
print('%-8s %-6s %5s %5s %6s %6s %6s %6s %6s %6s  %s' % ('ut_xbox', 'ut_pc', 'diff', 'rule', 'g_ok', 'g_wrong', 'g_noint', 'g_null',
                                                       'new=old', 'new=own', 'files'))
tot = collections.Counter()
for ut, r in sorted(T.items(), key=lambda kv: -kv[1]['diff']):
    tot.update(r)
    print('%-8d %-6d %5d %5d %6d %6d %6d %6d %6d %6d  %d' % (ut, ids.sym(ut), r['diff'], r['rule_touches'], r['gate_ok'],
          r['gate_wrong'], r['gate_not_intro'], r['gate_null'], r['new=old'], r['new=own'], len(files[ut])))
print('total', dict(tot))
print('\nuserType-%d reference words whose Xbox value is no intro / marker id of a unit of %s (file, Xbox script, value):'
      % (SL.INSTREF_UT, own))
byv = collections.defaultdict(list)
for (f, x, v), n in sorted(notintro.items()): byv[(x, v)].append(f)
for (x, v), fs in sorted(byv.items()):
    print('  script %5d value %5d (0x%04x) in %d DRMs: %s' % (x, v, v, len(fs), ', '.join(fs[:4]) + (' ...' if len(fs) > 4 else '')))
