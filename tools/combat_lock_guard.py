#!/usr/bin/env python3
"""combat_lock_guard.py - the fourth guard of the B138 tru.exe: lock-on target check at the entry of
playerDrawCombatLock 0x71e710 (2026-11-10, docs Befund-Kit-Unabhaengigkeit-1011.md section 3, ENGINE.md 18.5).

Upstream shipped this guard inside the B138 exe without a tool (the other three: fmod_init_guard.py,
light_tex_guard.py, soundplex_guard.py). This tool rebuilds it byte for byte; the bytes below were read from the B138
exe (md5 5560abac...) at VA 0x71e710 (6) and 0x83dfd0 (44) and are generated here from the instructions, not copied.

Facts (static, Steamless exe md5 56d1ce2d...):
  0x71e710 playerDrawCombatLock(this = ecx), thiscall. Its first three instructions build an aligned frame:
      55              push ebp
      8B EC           mov ebp,esp
      83 E4 F0        and esp,0xfffffff0
  0x71e716 is `mov eax,[0xfadfb0]` (A1 B0 DF FA 00); eax and edx are written before they are read in the function,
  ecx (this) is copied to esi at 0x71e720.
  [this+8] is a pointer to a handle pair {object*, serial}. The handle resolver 0x5b39d0 (cdecl, one argument, result
  in eax; it writes ecx / edx) returns the object when the pointer, the object and `[object+0x44] == serial` are all
  valid, else 0:
      mov ecx,[esp+4] ; test ecx,ecx ; je zero ; mov eax,[ecx] ; test eax,eax ; je zero ;
      mov edx,[eax+0x44] ; cmp edx,[ecx+4] ; je done ; zero: xor eax,eax ; done: ret

Patch (6 bytes at the site + a 44-byte cave in the zero tail of .text, after soundplex_guard's 0x83df00..0x83dfcf):
  0x71e710: 55 8B EC 83 E4 F0                 push ebp ; mov ebp,esp ; and esp,-16
        ->  E9 BB F8 11 00 90                 jmp 0x83dfd0 ; nop
  cave 0x83dfd0:
      85 C9              test ecx,ecx            this == 0       -> keep
      74 1D              je   tail
      8B 41 08           mov  eax,[ecx+8]        no lock target  -> keep
      85 C0              test eax,eax
      74 16              je   tail
      51                 push ecx                save this (the resolver writes ecx / edx)
      50                 push eax                argument: the handle pair pointer
      E8 EE 59 D7 FF     call 0x5b39d0           resolver
      83 C4 04           add  esp,4              cdecl: caller pops
      59                 pop  ecx
      85 C0              test eax,eax            target still alive -> keep
      75 07              jne  tail
      C7 41 08 00 00 00 00  mov dword [ecx+8],0  stale / dead target: drop the lock-on pointer
    tail:
      55                 push ebp                the three displaced instructions
      8B EC              mov  ebp,esp
      83 E4 F0           and  esp,0xfffffff0
      E9 1A 07 EE FF     jmp  0x71e716           back into the function
  Effect: the same stack frame as the original; ecx / ebx / esi / edi / ebp preserved; eax, edx and the flags may
  differ, and the function overwrites eax (0x71e716) and edx (0x71e725) before reading them. The guard does not
  protect against a [this+8] that points to freed memory (the resolver reads through it), only against a pair whose
  object is gone or was reused (serial mismatch).
  No counters, no .text write: independent of the other three guards (other bytes), applicable in any order.
  TruShadowPower `kRingEntry` hooks 0x71e716, right behind this site (src/asi/TruShadowPower).

Usage (from the repository root):
  ../bin/pyt -t 120 tools/combat_lock_guard.py IN.exe OUT.exe     apply, verify byte by byte, selftest
  ../bin/pyt -t 120 tools/combat_lock_guard.py --check IN.exe     original / patched / DIFFERENT (exit 0 / 0 / 1)
  ../bin/pyt -t 120 tools/combat_lock_guard.py --selftest         run the cave on synthetic memory (7 cases)
Never writes IN.exe. Refuses when the expected bytes are not there. Applying to an already patched exe refuses too
(the output would be the same; use --check). Prints addresses, instruction text and md5 prefixes only.
"""
import sys, os, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import light_tex_guard as L       # Asm, text_hdr, va2off (same PE helpers as the upstream guards)

SITE = 0x71E710
RESUME = 0x71E716
CAVE = 0x83DFD0
RESOLVER = 0x5B39D0
ORIG = bytes.fromhex('558bec83e4f0')                # push ebp ; mov ebp,esp ; and esp,0xfffffff0
NEXT = bytes.fromhex('a1b0dffa00')                  # mov eax,[0xfadfb0] at 0x71e716 (must stay intact)
RESOLVER_HEAD = bytes.fromhex('8b4c240485c9740e8b0185c07408' '8b50443b51047402' '33c0c3')


def rel32(src_next, dst): return struct.pack('<i', dst - src_next)


def cave_code():
    a = L.Asm(CAVE)
    a.raw('85 c9'); a.jcc(0x74, 'tail')              # test ecx,ecx ; je tail
    a.raw('8b 41 08')                                # mov eax,[ecx+8]
    a.raw('85 c0'); a.jcc(0x74, 'tail')              # test eax,eax ; je tail
    a.raw('51')                                      # push ecx
    a.raw('50')                                      # push eax
    a.raw('e8'); a.b += rel32(CAVE + len(a.b) + 4, RESOLVER)   # call 0x5b39d0
    a.raw('83 c4 04')                                # add esp,4
    a.raw('59')                                      # pop ecx
    a.raw('85 c0'); a.jcc(0x75, 'tail')              # test eax,eax ; jne tail
    a.raw('c7 41 08'); a.d32(0)                      # mov dword [ecx+8],0
    a.label('tail')
    a.b += ORIG                                      # push ebp ; mov ebp,esp ; and esp,-16
    a.raw('e9'); a.b += rel32(CAVE + len(a.b) + 4, RESUME)     # jmp 0x71e716
    return a.done()


def site_patch(): return b'\xe9' + rel32(SITE + 5, CAVE) + b'\x90'


def regions(d):
    c = cave_code()
    return [(L.va2off(d, SITE), 6, ORIG, site_patch()), (L.va2off(d, CAVE), len(c), bytes(len(c)), c)]


def preconditions(d):
    """bytes the patch relies on but does not change: the instruction after the site and the resolver."""
    o = L.va2off(d, RESUME); r = L.va2off(d, RESOLVER)
    bad = []
    if d[o:o + len(NEXT)] != NEXT: bad.append('0x71e716 is %s, expected %s' % (d[o:o + 5].hex(), NEXT.hex()))
    if d[r:r + len(RESOLVER_HEAD)] != RESOLVER_HEAD: bad.append('resolver 0x5b39d0 differs')
    return bad


def state(d):
    r = regions(d)
    if preconditions(d): return 'DIFFERENT (%s)' % '; '.join(preconditions(d))
    if all(d[o:o + n] == orig for o, n, orig, new in r): return 'original'
    if all(d[o:o + n] == new for o, n, orig, new in r): return 'patched'
    return 'DIFFERENT (%s)' % ', '.join('%#x:%s' % (o, d[o:o + min(n, 8)].hex()) for o, n, _, _ in r)


def apply(d):
    s = state(d)
    if s != 'original': raise SystemExit('refused: ' + s)
    b = bytearray(d)
    for o, n, orig, new in regions(d): b[o:o + n] = new
    return bytes(b)


def verify(orig, new):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    allowed = set(); [allowed.update(range(o, o + n)) for o, n, _, _ in regions(orig)]
    diff = [i for i in range(len(orig)) if orig[i] != new[i]]
    assert len(orig) == len(new) and set(diff) <= allowed, 'bytes changed outside the two regions'
    o = L.va2off(new, SITE)
    pre = [(i.mnemonic, i.op_str) for i in md.disasm(orig[o:o + 6], SITE)]
    assert pre == [('push', 'ebp'), ('mov', 'ebp, esp'), ('and', 'esp, 0xfffffff0')], pre
    ins = list(md.disasm(new[o:o + 6], SITE))
    assert [i.mnemonic for i in ins] == ['jmp', 'nop'] and int(ins[0].op_str, 16) == CAVE, ins
    assert new[o + 6:o + 11] == NEXT, 'instruction at 0x71e716 changed'
    c = cave_code(); oc = L.va2off(new, CAVE)
    dis = list(md.disasm(new[oc:oc + len(c)], CAVE)); assert sum(i.size for i in dis) == len(c)
    for i in dis:
        if i.mnemonic in ('je', 'jne'): assert CAVE <= int(i.op_str, 16) < CAVE + len(c), i
        if i.mnemonic == 'call': assert int(i.op_str, 16) == RESOLVER, i
    assert dis[-1].mnemonic == 'jmp' and int(dis[-1].op_str, 16) == RESUME
    tail = [(i.mnemonic, i.op_str) for i in dis[-4:-1]]
    assert tail == pre, ('displaced instructions differ', tail)
    return len(diff), [(hex(i.address), i.mnemonic, i.op_str) for i in dis]


# ------------------------------------------------------------------------------------------------ selftest
class Mini:
    """interpreter for the x86 subset of the cave and the original three instructions (no external emulator).
    `call 0x5b39d0` runs the resolver's documented semantics and then scrambles ecx / edx like the real one may."""
    REGS = ('eax', 'ecx', 'edx', 'ebx', 'esi', 'edi', 'ebp', 'esp')

    def __init__(self, mem, regs):
        self.m = dict(mem); self.r = dict.fromkeys(self.REGS, 0); self.r.update(regs); self.zf = False
        self.calls = 0

    def rd(self, a):
        if a not in self.m: raise KeyError('unmapped read %#x' % a)
        return self.m[a]

    def ea(self, e):
        e = e.replace(' ', '')
        for rn in self.REGS:
            if e.startswith(rn): return (self.r[rn] + (int(e[len(rn) + 1:], 0) if len(e) > len(rn) else 0)) & 0xFFFFFFFF
        return int(e, 0)

    def val(self, s):
        s = s.strip()
        if s.startswith('dword ptr ['): return self.rd(self.ea(s[11:-1]))
        if s in self.r: return self.r[s]
        return int(s, 0) & 0xFFFFFFFF

    def push(self, v): self.r['esp'] = (self.r['esp'] - 4) & 0xFFFFFFFF; self.m[self.r['esp']] = v

    def pop(self): v = self.rd(self.r['esp']); self.r['esp'] = (self.r['esp'] + 4) & 0xFFFFFFFF; return v

    def resolver(self):
        p = self.rd(self.r['esp'] + 4); res = 0
        if p:
            obj = self.rd(p)
            if obj and self.rd(obj + 0x44) == self.rd(p + 4): res = obj
        self.r.update(eax=res, ecx=0xDEAD0001, edx=0xDEAD0002); self.calls += 1

    def run(self, code, base, stop):
        import capstone
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        ins = {i.address: i for i in md.disasm(code, base)}; pc = base
        for _ in range(100):
            if pc == stop: return pc
            if pc not in ins: return pc
            i = ins[pc]; m, o = i.mnemonic, [x.strip() for x in i.op_str.split(',', 1)]; pc += i.size
            if m == 'mov':
                v = self.val(o[1])
                if o[0] in self.r: self.r[o[0]] = v
                else: self.m[self.ea(o[0].split('[', 1)[1][:-1])] = v
            elif m == 'push': self.push(self.val(o[0]))
            elif m == 'pop': self.r[o[0]] = self.pop()
            elif m == 'test': self.zf = (self.val(o[0]) & self.val(o[1])) == 0
            elif m == 'add': self.r[o[0]] = (self.r[o[0]] + self.val(o[1])) & 0xFFFFFFFF
            elif m == 'and': self.r[o[0]] = self.r[o[0]] & self.val(o[1])
            elif m == 'call':
                assert int(o[0], 16) == RESOLVER, i
                self.push(pc); self.resolver(); pc = self.pop()
            elif m in ('je', 'jne', 'jmp'):
                t = int(o[0], 16)
                if m == 'jmp' or (m == 'je' and self.zf) or (m == 'jne' and not self.zf): pc = t
            else: raise NotImplementedError(i)
        raise RuntimeError('too many instructions')


def selftest():
    code = cave_code()
    THIS, PAIR, OBJ, ESP0 = 0x20000000, 0x21000000, 0x22000000, 0x0019F7A4
    cases = [  # name, this, [this+8], object in pair, serial in pair, [object+0x44], expected [this+8] afterwards, calls
        ('this == 0 -> unchanged, no call', 0, None, None, None, None, None, 0),
        ('no lock target ([this+8] == 0) -> unchanged, no call', THIS, 0, None, None, None, 0, 0),
        ('target alive (serial matches) -> unchanged', THIS, PAIR, OBJ, 7, 7, PAIR, 1),
        ('target reused (serial differs) -> [this+8] = 0', THIS, PAIR, OBJ, 7, 8, 0, 1),
        ('target gone (object 0) -> [this+8] = 0', THIS, PAIR, 0, 7, None, 0, 1),
        ('target alive, serial 0 -> unchanged', THIS, PAIR, OBJ, 0, 0, PAIR, 1),
        ('stack pointer already 16-aligned -> same frame', THIS, PAIR, OBJ, 3, 3, PAIR, 1),
    ]
    for k, (name, this, field, obj, serial, live, want, ncalls) in enumerate(cases):
        mem = {}
        if this: mem[THIS + 8] = field
        if field: mem[PAIR] = obj; mem[PAIR + 4] = serial
        if obj: mem[OBJ + 0x44] = live
        esp = ESP0 if k != 6 else 0x0019F7B0
        regs = dict(eax=0x1111, ecx=this, edx=0x2222, ebx=0x3333, esi=0x4444, edi=0x5555, ebp=0x6666, esp=esp)
        mi = Mini(mem, regs); end = mi.run(code, CAVE, RESUME)
        ref = Mini({}, regs); ref_end = ref.run(ORIG + b'\xe9' + rel32(SITE + 11, RESUME), SITE, RESUME)
        assert end == RESUME and ref_end == RESUME, (name, hex(end), hex(ref_end))
        for rn in ('ecx', 'ebx', 'esi', 'edi', 'ebp', 'esp'):
            assert mi.r[rn] == ref.r[rn], (name, rn, hex(mi.r[rn]), hex(ref.r[rn]))
        assert mi.m[ref.r['ebp']] == 0x6666, (name, 'saved ebp')
        assert mi.calls == ncalls, (name, mi.calls)
        if this: assert mi.m[THIS + 8] == want, (name, hex(mi.m[THIS + 8]))
        print('  OK  %s' % name)
    print('selftest: %d cases OK, cave %d bytes' % (len(cases), len(code)))


def main():
    a = sys.argv[1:]
    if a and a[0] == '--selftest': selftest(); return 0
    if a and a[0] == '--check':
        s = state(open(a[1], 'rb').read()); print(s); return 0 if s in ('original', 'patched') else 1
    if len(a) != 2: raise SystemExit(__doc__)
    d = open(a[0], 'rb').read(); n = apply(d); nd, dis = verify(d, n)
    selftest()
    open(a[1], 'wb').write(n)
    print('written %s: %d bytes changed; in md5 %s out md5 %s' % (a[1], nd, hashlib.md5(d).hexdigest()[:8], hashlib.md5(n).hexdigest()[:8]))
    for x in dis: print('  %s  %-5s %s' % x)
    return 0


if __name__ == '__main__':
    sys.exit(main())
