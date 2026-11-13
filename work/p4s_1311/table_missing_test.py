"""P4.2 check: aidata_fix.table() with a missing table must stop the tool with exit 1 (no silent {}).
Points aidata_fix.TABLE at a path that does not exist (the real table stays untouched), then calls fix() on a tiny
Xbox-like record so the call goes through table(). Usage: pyt table_missing_test.py   (expected: exit 1 + message)"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
import aidata_fix as A, drm_reloc as R
A.TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'no_such_aidata_table.pkl')
assert not os.path.exists(A.TABLE)
class Rel:          # minimal relocation view: one internal pointer source +0x28 -> record at 0
    internal = [(0x28, 0)]
    def pointer_offsets(self): return [0x28]
    def id_offsets(self): return []
xd = bytearray(A.SIZE); struct.pack_into('>I', xd, 0, A.SIG)
print('records detected', A.detect(bytes(xd), Rel()))
A.fix(bytes(xd), Rel(), bytearray(len(xd)), lambda t, v: v)
print('NOT STOPPED - fix() returned without the table')
