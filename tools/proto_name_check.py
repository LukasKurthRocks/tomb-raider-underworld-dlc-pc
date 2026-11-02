"""Calibrate the prototype -> retail -> PC name chain against independently known PC names (read-only).

TRLAU (TheIndra55's TR Legend/Anniversary/Underworld menu, sources cited in docs/Menue-Funktionen-Katalog.md) names
PC tru.exe functions from its own reverse engineering. Those names are independent of our matching, so they measure
how often the chain prototype name -> retail -> PC (tools/proto_retail_map.py + work/xmap/xbox_pc_map.tsv) gives the
right PC address. For each known (name, PC address):
  agree     - the prototype function of that name chains to exactly that PC address
  disagree  - it chains to another PC address
  reverse   - not reached forward, but PC -> retail (reverse xbox_pc_map) -> prototype gives that name
  wrong-rev - reverse chain reaches a prototype function with another name
  open      - no chain in either direction
Counts per prototype tier (A/B/C/D/X) and per retail->PC tier.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/proto_name_check.py
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proto_chain as PCH

# (name as in the prototype map, PC address) - from docs/Menue-Funktionen-Katalog.md sections 1-9 (TRLAU citations)
KNOWN = [
    ('INSTANCE_Post', 0x5B3750), ('INSTANCE_ReallyRemoveInstance', 0x5BC4E0),
    ('INSTANCE_HideUnhideDrawGroup', 0x5B3DD0), ('INSTANCE_BirthObjectNoParent', 0x5BD0F0),
    ('OBTABLE_GetObjectID', 0x5BF770), ('STREAM_GetObjectTrackerByName', 0x5C17D0),
    ('STREAM_PollLoadQueue', 0x5C1DA0), ('LOAD_UnitFileName', 0x477970),
    ('GAMELOOP_RequestLevelChangeByName', 0x5DF8C0), ('GAMELOOP_IsWipeDone', 0x52E880),
    ('GAMELOOP_SetScreenWipe', 0x52E8B0), ('GAMELOOP_Process', 0x5DFBE0), ('DeathState::Entry', 0x75AA50),
    ('DeathState::Process', 0x75AF90), ('CAMERA_SetMode', 0x5F39F0),
    ('G2EmulationInstanceSetAnimation', 0x5B1EA0), ('G2EmulationInstanceSetMode', 0x5B1F50),
    ('G2EmulationInstanceQueryAnimation', 0x5B1FC0), ('TRANS_RotTransPersVectorf', 0x49F630),
    ('DRAW_DrawQuads', 0x5BFB20), ('DRAW_DrawLines', 0x5BFCD0), ('DRAW_DrawTriangles', 0x5BFA40),
    ('MarkUpBox::GetSegmentPos', 0x5C39D0), ('MAIN_DoMainInit', 0x5DEF70), ('MainG2_ErrorHandler', 0x478B00),
    ('ScriptObject::CallFunction', 0x57B380), ('cdc::Matrix::Build', 0x49DD70),
]


def main(argv):
    C = PCH.Chain()
    byname = collections.defaultdict(list)
    for r in C.names:
        byname[r['name']].append(r)
    res = collections.Counter()
    per_tier = collections.defaultdict(collections.Counter)
    for name, pc in KNOWN:
        rows = byname.get(name, [])
        fwd = [r for r in rows if r['pc']]
        st, detail = None, ''
        if fwd:
            r = fwd[0]
            st = 'agree' if int(r['pc'], 16) == pc else 'disagree'
            detail = 'proto %s -> retail %s (%s/%s) -> PC %s (%s)' % (r['proto'], r['retail'], r['method'], r['tier'],
                                                                     r['pc'], r['pc_tier'])
            per_tier[r['tier']][st] += 1
        else:
            x = C.pcx.get(pc)
            if x:
                pr = C.by_retail.get(int(x['xbox_retail'], 16), [])
                if pr:
                    ok = any(p['name'] == name for p in pr)
                    st = 'reverse' if ok else 'wrong-rev'
                    detail = 'PC -> retail %s (%s) -> proto %s %s (%s/%s)' % (
                        x['xbox_retail'], x['tier'], pr[0]['proto'], ' | '.join(p['name'] for p in pr)[:60],
                        pr[0]['method'], pr[0]['tier'])
                    per_tier[pr[0]['tier']][st] += 1
                else:
                    st, detail = 'open', 'PC -> retail %s, no prototype partner' % x['xbox_retail']
            else:
                st = 'open'
                detail = ('prototype has the name at %s, retail %s' % (rows[0]['proto'], rows[0]['retail'] or '-')
                          if rows else 'name not in the prototype map')
        res[st] += 1
        print('%-36s PC 0x%06x  %-9s %s' % (name, pc, st, detail))
    print('summary: %s' % dict(res))
    print('by prototype tier: %s' % dict((k, dict(v)) for k, v in sorted(per_tier.items())))


if __name__ == '__main__':
    main(sys.argv[1:])
