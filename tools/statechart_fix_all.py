"""Re-convert the DLC 2 player state chart (doppelganger_casual.drm DTP 20212) in five steps (finding 43, rock vein).
Writes OUT_DIR/doppelganger_casual.drm plus the intermediate files; the input is never changed.

  1. tools/statechart_typed.py   - field byte orders learned from the base pair lara.drm 12647 (Xbox) / 850 (PC) along
                                   the pointer graph (checked: never changes a word that the proven rules call right)
  2. tools/param_record_proof.py - parameter records {u16 id, u16 type, value}: value byte order per type, only types
                                   proven on the base pair (>= 98 % of >= 5 records, e.g. type 2 raw 3 149 / 3 183,
                                   type 12 float 249 / 249, type 35 u32 790 / 790)
  3. tools/shape_proof.py        - the chart's top state-machine block (0x50 bytes): "wwhhppppppwhhphhppppppw", from the
                                   single base instance (all non-id words identical)
  4. tools/statechart_cond_fix.py - condition records {u16 key, u16 id, u16 value, u8 flags, u8}, proven on the base
                                   pair (6 427 of 6 427 records identical)
  5. tools/shape_proof.py        - transitions (20 bytes, pointers at +8 / +0xc): "hhhhppw", proven on the base pair
                                   (2 573 of 2 574 Xbox transitions identical on PC)
  The proven layouts (4, 5) run last, so they win where a learned / per-type step touched the same word.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/statechart_fix_all.py TU_IMAGE REF_DIR PC_DOPPELGANGER.drm OUT_DIR
  REF_DIR holds x_lara.drm (Xbox layer2), pc_lara.drm (PC bigfile), x_doppelganger_casual.drm (pack11), extracted
  with tools/bigfile_extract.py (xbase2 / pcbig / pack11).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import statechart_typed, shape_proof, statechart_cond_fix, param_record_proof

SID = '20212'
TRANSITION = ('14', '8,c', 'hhhhppw')
MACHINE = ('50', 'c,10,14,18,1c,20,2c,34,38,3c,40,44,48', 'wwhhppppppwhhphhppppppw')


def main(argv):
    img, ref, pc, out = argv
    xl, pl, xd = (os.path.join(ref, n) for n in ('x_lara.drm', 'pc_lara.drm', 'x_doppelganger_casual.drm'))
    run(img, xl, pl, xd, pc, out, SID)


def run(img, xl, pl, xd, pc, out, sid=SID, check=True):
    """the five steps for DTP sid of the PC file pc (Xbox source xd; base pair xl / pl = lara.drm 12647 / 850);
    writes out/<name of pc> plus the step files and returns its path (also called by tools/statechart_fix_tree.py)"""
    SID = str(sid)
    os.makedirs(out, exist_ok=True)
    nm = os.path.basename(pc)
    s1, s2, s3, s4 = (os.path.join(out, 'step%d_%s' % (k, nm)) for k in (1, 2, 3, 4))
    final = os.path.join(out, nm)
    print('== step 1: typed (learned on the base pair)')
    statechart_typed.main([xl, pl, '12647', '850', xd, pc, SID, '--show', '0', '--check', img, '--out', s1])
    print('== step 2: typed parameter records {u16 id, u16 type, value} (before the proven layouts, which win on overlap)')
    param_record_proof.main([img, xl, pl, '12647', '850', xd, s1, SID, '--out', s2])
    print('== step 3: state-machine block')
    shape_proof.main([xl, pl, '12647', '850', xd, s2, SID] + list(MACHINE) + ['--show', '0', '--out', s3])
    print('== step 4: condition records')
    statechart_cond_fix.main([img, xl, pl, '12647', '850', xd, s3, SID, '--list', '0', '--out', s4])
    print('== step 5: transitions (proven layout, applied last together with the condition records)')
    shape_proof.main([xl, pl, '12647', '850', xd, s4, SID] + list(TRANSITION) + ['--show', '0', '--out', final])
    if check:
        print('== check: condition records and transitions of the result')
        statechart_cond_fix.main([img, xl, pl, '12647', '850', xd, final, SID, '--list', '0'])
        shape_proof.main([xl, pl, '12647', '850', xd, final, SID] + list(TRANSITION) + ['--show', '0'])
    return final


if __name__ == '__main__':
    main(sys.argv[1:])
