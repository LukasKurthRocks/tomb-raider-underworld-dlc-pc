"""List the built-in FMOD Ex DSP units linked into a 32-bit PE (tru.exe): FMOD DSP type number, unit name and the
parameter table (index, name, label, min, max, default) - read-only (sound groups 77 / 78 DSP decode, 2026-11-11).

FMOD Ex is linked into tru.exe (tools/pe_fmod_api_map.py). Every built-in unit has a small getDescription function
that fills a static description block (FMOD_DSP_DESCRIPTION_EX) at run time:
    push 0x88; push 0; mov esi, DESC; push esi; call memset
    push NAME ("FMOD Chorus"); push esi; call strcpy
    mov dword ptr [DESC + 0x3c], NUMPARAMS; mov dword ptr [DESC + 0x40], PARAMDESC; ...; mov dword ptr [DESC + 0x6c], TYPE
SystemI::createDSPByType (0x7bdd9f in tru.exe 1.0 PC) walks the registered units and picks the one whose desc + 0x6c
equals the requested type (cmp [eax + 0x6c], ecx at 0x7bde52), so desc + 0x6c is the type number the game passes to
createDSPByType. The parameter table PARAMDESC is initialised data: 48 B per parameter
{f32 min, f32 max, f32 default, char name[16], char label[16], char *description}.
The tool finds every "FMOD ..." string pushed right after a `mov esi, imm32`, reads the immediate stores up to the
next `ret` and decodes the table from the file bytes.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/pe_fmod_dsp_desc.py EXE [--type N] [--desc]     --desc also prints the description texts
"""
import sys, os, struct
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def off_of(secs, a):
    for _, sva, rptr, size, _ in secs:
        if sva <= a < sva + size: return rptr + a - sva
    return -1


def cstr(exe, secs, va, mx=200):
    o = off_of(secs, va)
    if o < 0: return None
    e = exe.find(b'\0', o, o + mx)
    return exe[o:e if e >= 0 else o + mx].decode('latin-1')


def units(exe, secs):
    """yield (getter VA, desc VA, name, {desc offset: imm})"""
    text = [s for s in secs if s[0] == '.text'][0]
    _, tva, trp, tsz, _ = text
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    pos = 0
    rd = exe
    while True:
        i = rd.find(b'FMOD ', pos)
        if i < 0: break
        pos = i + 1
        va = None          # no NUL test before the name: some names follow float constants directly (Highpass)
        for _, sva, rptr, size, _ in secs:
            if rptr <= i < rptr + size: va = sva + i - rptr
        if va is None: continue
        name = cstr(exe, secs, va)
        pat = b'\x68' + struct.pack('<I', va)          # push imm32 NAME
        j = trp
        while True:
            j = rd.find(pat, j, trp + tsz)
            if j < 0: break
            ref = tva + j - trp
            j += 1
            # the description base: `mov esi, imm32` (be xx xx xx xx) within 0x20 bytes before the push
            win = rd[j - 1 - 0x20:j - 1]
            k = next((k for k in range(len(win) - 6, -1, -1) if win[k] == 0xbe and win[k + 5] == 0x56), -1)
            if k < 0: continue                         # `mov esi, DESC; push esi` not found
            desc = struct.unpack_from('<I', win, k + 1)[0]
            stores = {}
            o = j - 1
            for ins in md.disasm(rd[o:o + 0x200], ref):
                if ins.mnemonic in ('ret', 'int3'): break
                b = ins.bytes
                if len(b) == 10 and b[0] == 0xc7 and b[1] == 0x05:          # mov dword ptr [abs], imm32
                    a, v = struct.unpack_from('<II', b, 2)
                    if desc <= a < desc + 0x88: stores[a - desc] = v
            yield ref, desc, name, stores


def main(argv):
    if not argv: sys.exit(__doc__)
    exe = open(argv[0], 'rb').read()
    want = int(argv[argv.index('--type') + 1], 0) if '--type' in argv else None
    show_desc = '--desc' in argv
    base, secs = PE.sections(exe)
    rows = []
    for ref, desc, name, st in units(exe, secs):
        if 0x6c not in st: continue
        rows.append((st[0x6c], name, ref, desc, st))
    rows.sort()
    for typ, name, ref, desc, st in rows:
        if want is not None and typ != want: continue
        n, tab = st.get(0x3c, 0), st.get(0x40, 0)
        print('type %2d  %-26s desc 0x%08x (name push 0x%08x)  %d parameters, table 0x%08x' % (typ, name, desc, ref, n, tab))
        o = off_of(secs, tab) if tab else -1
        for p in range(n if o >= 0 else 0):
            mn, mx, df = struct.unpack_from('<fff', exe, o + 48 * p)
            pn = exe[o + 48 * p + 12:o + 48 * p + 28].split(b'\0')[0].decode('latin-1')
            lb = exe[o + 48 * p + 28:o + 48 * p + 44].split(b'\0')[0].decode('latin-1')
            dp = struct.unpack_from('<I', exe, o + 48 * p + 44)[0]
            print('    [%d] %-16s %-8s min %-10g max %-10g default %g' % (p, pn, lb, mn, mx, df))
            if show_desc and dp: print('        %s' % cstr(exe, secs, dp, 400))


if __name__ == '__main__':
    main(sys.argv[1:])
