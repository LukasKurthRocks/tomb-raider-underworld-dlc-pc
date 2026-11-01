"""Exception-handling inventory of a 32-bit PE (x86) such as tru.exe (read-only; TruGuard design check).

Answers: does the game use structured exception handling (SEH __try / __except) or C++ catch(...) around its own code,
so that a first-chance access violation inside tru.exe could be expected and handled by the game itself?

Reports
  - imports that belong to exception handling (SetUnhandledExceptionFilter, RtlUnwind, AddVectoredExceptionHandler,
    IsBadReadPtr / IsBadWritePtr - the latter raise and catch AVs internally, in kernel32),
  - the SafeSEH handler table of the load config directory (count),
  - frames built inline with "push -1|-2; push <scopetable>; push <handler>; mov eax, fs:[0]" (_except_handler3/4 style)
    and calls "push <size>; push <scopetable>; call <_SEH_prolog>" (scope table pointers that look like one),
  - per scope table: entries with a filter function (= __except) vs without (= __finally),
  - C++ EH FuncInfo records (magic 0x19930520 / 21 / 22) and how many of their catch blocks are catch(...) (pType 0);
    with magic 0x19930522 and EHFlags bit 0 (/EHs) catch(...) does not catch SEH exceptions.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/pe_seh_scan.py EXE [--list N]     N = how many __except sites to print (default 20)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_callers as PE


def off_of(secs, a):
    for _, sva, rptr, size, _ in secs:
        if sva <= a < sva + size: return rptr + a - sva
    return -1


def u32(exe, o):
    return struct.unpack_from('<I', exe, o)[0] if 0 <= o <= len(exe) - 4 else None


def imports(exe, base, secs):
    pe = u32(exe, 0x3c)
    rva = u32(exe, pe + 24 + 96 + 8)               # data directory 1 = import
    names = []
    o = off_of(secs, base + rva) if rva else -1
    while o >= 0:
        ilt, _, _, name, iat = struct.unpack_from('<IIIII', exe, o)
        if not name: break
        dll = exe[off_of(secs, base + name):].split(b'\0', 1)[0].decode('ascii', 'replace')
        t = off_of(secs, base + (ilt or iat))
        while t >= 0:
            v = u32(exe, t)
            if not v: break
            if not v & 0x80000000:
                n = exe[off_of(secs, base + v) + 2:].split(b'\0', 1)[0].decode('ascii', 'replace')
                names.append((dll, n))
            t += 4
        o += 20
    return names


def load_config(exe, base, secs):
    pe = u32(exe, 0x3c)
    rva = u32(exe, pe + 24 + 96 + 10 * 8)
    if not rva: return None
    o = off_of(secs, base + rva)
    size = u32(exe, o)
    if size is None or size < 0x48: return {'size': size}
    return {'size': size, 'handlers': u32(exe, o + 0x40), 'count': u32(exe, o + 0x44)}


def in_data(secs, a):
    for name, sva, _, size, chars in secs:
        if sva <= a < sva + size and not chars & 0x20000000: return True   # not executable
    return False


def in_code(secs, a):
    for name, sva, _, size, chars in secs:
        if sva <= a < sva + size and chars & 0x20000000: return True
    return False


def scope_entries(exe, secs, st, h4):
    """(filter, handler) pairs of a scope table; handler4 tables start with 16 bytes of GS / EH cookie offsets."""
    o = off_of(secs, st)
    if o < 0: return None
    if h4:
        gs = u32(exe, o)
        if gs not in (0xfffffffe,) and not (0x80000000 <= gs): return None
        o += 16
    out = []
    for k in range(64):
        enc, flt, hnd = struct.unpack_from('<III', exe, o + 12 * k)
        if enc not in (0xffffffff, 0xfffffffe) and enc >= k: break   # -1 handler3, -2 handler4 = outermost
        if not in_code(secs, hnd): break
        if flt and not in_code(secs, flt): break
        out.append((flt, hnd))
    return out or None


def main(argv):
    exe = open(argv[0], 'rb').read()
    nlist = int(argv[argv.index('--list') + 1]) if '--list' in argv else 20
    base, secs = PE.sections(exe)
    print('image base 0x%08x, %d sections' % (base, len(secs)))
    imp = imports(exe, base, secs)
    watch = ('SetUnhandledExceptionFilter', 'UnhandledExceptionFilter', 'RtlUnwind', 'AddVectoredExceptionHandler',
             'RemoveVectoredExceptionHandler', 'IsBadReadPtr', 'IsBadWritePtr', 'IsBadCodePtr', 'IsBadStringPtrA',
             'IsBadStringPtrW', 'RaiseException', '_except_handler3', '_except_handler4_common', '__CxxFrameHandler3',
             '__CxxFrameHandler', '_CxxThrowException', 'MiniDumpWriteDump')
    print('imports (%d), exception related:' % len(imp))
    for dll, n in imp:
        if n in watch or 'xcept' in n.lower(): print('  %s!%s' % (dll, n))
    lc = load_config(exe, base, secs)
    print('load config: %s' % (lc if lc else 'none'))

    code = [(sva, rptr, size) for name, sva, rptr, size, chars in secs if chars & 0x20000000]
    frames = {}                                   # scopetable -> (handler, h4 flag, first site)
    handlers = {}
    for sva, rptr, size in code:
        blob = exe[rptr:rptr + size]
        i = blob.find(b'\x64\xa1\x00\x00\x00\x00')
        while i >= 0:
            # push -1|-2 (6a ff / 6a fe); push imm32 (68); push imm32 (68); mov eax, fs:[0]
            if i >= 12 and blob[i - 12] == 0x6a and blob[i - 10] == 0x68 and blob[i - 5] == 0x68:
                st = struct.unpack_from('<I', blob, i - 9)[0]
                h = struct.unpack_from('<I', blob, i - 4)[0]
                h4 = blob[i - 11] == 0xfe
                frames.setdefault(st, (h, h4, sva + i - 12))
                handlers[h] = handlers.get(h, 0) + 1
            i = blob.find(b'\x64\xa1\x00\x00\x00\x00', i + 1)
    for st, (h, h4, site) in sorted(frames.items(), key=lambda x: x[1][2]):
        print("  inline frame at 0x%08x scopetable 0x%08x handler 0x%08x (%s)" % (site, st, h, "push -2" if h4 else "push -1"))
    print('inline SEH frames: %d sites, %d distinct handlers: %s' % (
        len(frames), len(handlers), ', '.join('0x%08x x%d' % kv for kv in sorted(handlers.items(), key=lambda x: -x[1]))))

    # push imm8/imm32; push <scopetable>; call rel32 - _SEH_prolog style; keep targets called with such pairs often
    prolog_calls = {}
    for sva, rptr, size in code:
        blob = exe[rptr:rptr + size]
        for i in range(0, len(blob) - 12):
            if blob[i] == 0x68 and blob[i + 5] == 0xe8 and (i >= 2 and blob[i - 2] == 0x6a or i >= 5 and blob[i - 5] == 0x68):
                st = struct.unpack_from('<I', blob, i + 1)[0]
                if not in_data(secs, st): continue
                tgt = sva + i + 10 + struct.unpack_from('<i', blob, i + 6)[0]
                prolog_calls.setdefault(tgt, []).append((st, sva + i))
    # a _SEH_prolog function itself reads fs:[0] near its start ("mov eax, fs:[0]" or "push dword ptr fs:[0]")
    seh_prologs = []
    for tgt, uses in prolog_calls.items():
        o = off_of(secs, tgt)
        head = exe[o:o + 0x30] if o >= 0 else b''
        if len(uses) >= 3 and (b'\x64\xa1\x00\x00\x00\x00' in head or b'\x64\xff\x35\x00\x00\x00\x00' in head):
            seh_prologs.append((tgt, uses))
    for tgt, uses in seh_prologs:
        # handler4 scope tables start with GSCookieOffset -2 (checked per table below)
        h4 = all(u32(exe, off_of(secs, st)) == 0xfffffffe for st, _ in uses[:5] if off_of(secs, st) >= 0)
        print('SEH prolog function 0x%08x: %d callers (%s)' % (tgt, len(uses), 'handler4' if h4 else 'handler3'))
        for st, site in uses:
            frames.setdefault(st, (None, h4, site))

    n_except = n_finally = n_tables = 0
    excepts = []
    for st, (h, h4, site) in sorted(frames.items(), key=lambda x: x[1][2]):
        ents = scope_entries(exe, secs, st, h4)
        if ents is None:
            ents = scope_entries(exe, secs, st, not h4)
        if not ents: continue
        n_tables += 1
        for flt, hnd in ents:
            if flt:
                n_except += 1
                excepts.append((site, st, flt, hnd))
            else:
                n_finally += 1
    print('scope tables parsed: %d; entries with a filter (__except): %d; without (__finally): %d' % (
        n_tables, n_except, n_finally))
    for site, st, flt, hnd in excepts[:nlist]:
        print('  __except  frame at 0x%08x  scopetable 0x%08x  filter 0x%08x  handler 0x%08x' % (site, st, flt, hnd))
    if len(excepts) > nlist: print('  ... %d more' % (len(excepts) - nlist))

    # C++ EH FuncInfo: magic, maxState, pUnwindMap, nTryBlocks, pTryBlockMap, ...
    n_fi = n_ell = 0
    magic_count = {}
    ehs = 0
    for name, sva, rptr, size, chars in secs:
        if chars & 0x20000000: continue
        blob = exe[rptr:rptr + size]
        for m in (0x19930520, 0x19930521, 0x19930522):
            pat = struct.pack('<I', m)
            i = blob.find(pat)
            while i >= 0:
                if i % 4 == 0 and i + 20 <= len(blob):
                    maxst, punw, ntry, ptry = struct.unpack_from('<IIII', blob, i + 4)
                    if maxst < 4096 and ntry < 256 and (not ntry or in_data(secs, ptry)):
                        n_fi += 1
                        magic_count[m] = magic_count.get(m, 0) + 1
                        if m == 0x19930522 and i + 36 <= len(blob) and struct.unpack_from('<I', blob, i + 32)[0] & 1:
                            ehs += 1
                        to = off_of(secs, ptry) if ntry else -1
                        for t in range(ntry):
                            lo, hi, cat, ncatch, pcatch = struct.unpack_from('<IIIII', exe, to + 20 * t)
                            co = off_of(secs, pcatch)
                            for c in range(min(ncatch, 64)):
                                if co < 0: break
                                adj, ptype = struct.unpack_from('<II', exe, co + 16 * c)
                                if ptype == 0: n_ell += 1
                i = blob.find(pat, i + 1)
    print('C++ EH FuncInfo records: %d (%s); with /EHs flag: %d; catch(...) blocks: %d' % (
        n_fi, ', '.join('0x%08x x%d' % kv for kv in sorted(magic_count.items())), ehs, n_ell))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
