"""Neutralise one call in a converted script: replace its words with line markers (op00) and drop its relocation.

Use case (finding 43): the title-update loading screen (generalbank script 6, function 3) starts with
    op04 0 / op0f 1024 / op65 -> uigamedata function 93 (a native only the Xbox title update's exe has)
which overwrites local 0 ("CURRENT LEVEL", a debug print) with the native's result. The retail version of function 3
has no such call and uses the parameter. Replacing the call sequence with op00 words (the debug line markers found
all over script code; no stack effect) restores the retail behaviour for that value; the DLC branches (background
image by level number 101/102 from script 86, intro trigger by level name via uigamedata function 33) do not use it.

The words to replace are checked against the expected values first (platform byte order of the file: PC = LE).

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/script_nop_call.py IN_DRM OUT_DRM SCRIPT_ID START_OFFSET EXPECTED_WORDS
  e.g. work/rebuild/base_convert/tu_generalbank.drm work/rebuild/dlc2_gb4/tu_generalbank_nof93.drm 6 0x7928 04000000,0f000400,65000000,*
  EXPECTED_WORDS: comma-separated hex words in instruction order; '*' = any value (an operand with a relocation)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def main(argv):
    src, out, sid, start = argv[0], argv[1], int(argv[2]), int(argv[3], 0)
    expect = argv[4].split(',')
    D = DW.read(open(src, 'rb').read(), 'le')
    s = next(x for x in D.sections if x.type == 8 and x.id == sid)
    data = bytearray(s.data)
    offs = [start + 4 * k for k in range(len(expect))]
    for o, e in zip(offs, expect):
        w = struct.unpack_from('<I', data, o)[0]
        if e != '*' and w != int(e, 16): sys.exit('word at %#x is %08x, expected %s - not patched' % (o, w, e))
    marker = struct.unpack_from('<I', data, start - 4)[0]
    if marker >> 24 != 0: sys.exit('word before %#x (%08x) is not a line marker - not patched' % (start, marker))
    r = R.parse(s.reloc, 'le')
    before = len(r.external) + len(r.internal) + len(r.idref) + len(r.idref_a)
    r.external = [x for x in r.external if x[1] not in offs]
    r.internal = [x for x in r.internal if x[0] not in offs]
    r.idref = [x for x in r.idref if x[1] not in offs]
    r.idref_a = [x for x in r.idref_a if x[1] not in offs]
    dropped = before - (len(r.external) + len(r.internal) + len(r.idref) + len(r.idref_a))
    for o in offs: struct.pack_into('<I', data, o, marker)       # repeat the preceding line marker
    s.data = bytes(data); s.reloc = R.write(r, 'le')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(DW.cdrm_encode(D.write('le'), 'le'))
    print('script %d: %d words from %#x replaced by line marker %08x, %d relocation(s) dropped -> %s' % (
        sid, len(offs), start, marker, dropped, out))


if __name__ == '__main__':
    main(sys.argv[1:])
