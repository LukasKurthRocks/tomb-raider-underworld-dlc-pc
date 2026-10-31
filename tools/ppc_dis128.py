"""Disassemble Xbox 360 PowerPC code from a Xenia memory image with capstone, plus the VMX128 forms capstone does not
know (read-only; TU state translation of Lara's state machine, docs/Befund-Schattenkraft.md 2026-10-31).

Capstone 5 decodes the scalar / FPU / standard AltiVec instructions. The Xbox-only VMX128 instructions (primary
opcodes 4 / 5 / 6 with 128 vector registers) are decoded here from their encoding:
  VD128 = vd(6..10) | ((word >> 2) & 3) << 5, VA128 = va(11..15) | bit 5 << 5 | bit 10 << 6,
  VB128 = vb(16..20) | (word & 3) << 5.
Load / store forms (op 4, mask 0xfc0007f3) give the field they touch; arithmetic forms are named by their
sub-opcode where the table below knows it, otherwise printed as 'vmx128 op N xo 0x...'. This is enough to see which
memory fields the vector code reads / writes; the arithmetic itself is read by hand.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/ppc_dis128.py IMAGE ADDR N           N instructions from ADDR (hex)
  ../bin/pyt -t 120 tools/ppc_dis128.py IMAGE ADDR --to END     until END (exclusive)
  ../bin/pyt -t 120 tools/ppc_dis128.py IMAGE --words ADDR N    N big-endian words
"""
import sys, struct
import capstone

BASE = 0x82000000

LS128 = {0x003: 'lvsl128', 0x043: 'lvsr128', 0x083: 'lvewx128', 0x0c3: 'lvx128', 0x183: 'stvewx128',
         0x1c3: 'stvx128', 0x2c3: 'lvxl128', 0x3c3: 'stvxl128', 0x403: 'lvlx128', 0x443: 'lvrx128',
         0x503: 'stvlx128', 0x543: 'stvrx128', 0x603: 'lvlxl128', 0x643: 'lvrxl128', 0x703: 'stvlxl128',
         0x743: 'stvrxl128'}
# op 5: xo = word & 0x3d0 (bits 22..25 + 27)
OP5 = {0x010: 'vaddfp128', 0x050: 'vsubfp128', 0x090: 'vmulfp128', 0x0d0: 'vmaddfp128', 0x110: 'vmaddcfp128',
       0x150: 'vnmsubfp128', 0x190: 'vdot3fp128', 0x1d0: 'vdot4fp128', 0x210: 'vand128', 0x250: 'vandc128',
       0x290: 'vnor128', 0x2d0: 'vor128', 0x310: 'vxor128', 0x350: 'vsel128', 0x390: 'vslo128', 0x3d0: 'vsro128'}
# op 6, two-operand forms (mask 0x3f0) and one-operand forms (mask 0x7f0)
OP6A = {0x000: 'vcmpeqfp128', 0x080: 'vcmpgefp128', 0x100: 'vcmpgtfp128', 0x180: 'vcmpbfp128',
        0x200: 'vcmpequw128', 0x050: 'vrlw128', 0x0d0: 'vslw128', 0x150: 'vsraw128', 0x1d0: 'vsrw128',
        0x280: 'vmaxfp128', 0x2c0: 'vminfp128', 0x300: 'vmrghw128', 0x340: 'vmrglw128', 0x380: 'vupkhsb128',
        0x3c0: 'vupklsb128'}
OP6B = {0x230: 'vcfpsxws128', 0x270: 'vcfpuxws128', 0x2b0: 'vcsxwfp128', 0x2f0: 'vcuxwfp128', 0x330: 'vrfim128',
        0x370: 'vrfin128', 0x3b0: 'vrfip128', 0x3f0: 'vrfiz128', 0x630: 'vrefp128', 0x670: 'vrsqrtefp128',
        0x6b0: 'vexptefp128', 0x6f0: 'vlogefp128', 0x710: 'vrlimi128', 0x730: 'vspltw128', 0x770: 'vspltisw128',
        0x7f0: 'vupkd3d128', 0x610: 'vpkd3d128'}


def vd128(w):
    return ((w >> 21) & 31) | ((w >> 2) & 3) << 5


def va128(w):
    # Xenia ppc_instr.h VX128: VA128h = bit 5 (-> << 5), VA128H = bit 10 (-> << 6)
    return ((w >> 16) & 31) | ((w >> 5) & 1) << 5 | ((w >> 10) & 1) << 6


def vb128(w):
    return ((w >> 11) & 31) | (w & 3) << 5


def vmx128(w):
    op = w >> 26
    if op == 4 and (w & 0x7f3) in LS128:
        ra, rb = (w >> 16) & 31, (w >> 11) & 31
        return '%s v%d,r%d,r%d' % (LS128[w & 0x7f3], vd128(w), ra, rb)
    if op == 5:
        if (w & 0x210) == 0:
            return 'vperm128 v%d,v%d,v%d,v%d' % (vd128(w), va128(w), vb128(w), (w >> 6) & 7)
        n = OP5.get(w & 0x3d0)
        if n:
            return '%s v%d,v%d,v%d' % (n, vd128(w), va128(w), vb128(w))
    if op == 6:
        # order as Xenia's decoder: VX128_3 (0x7f0), VX128_4 (0x730: vrlimi128 / vpkd3d128), VX128_P (0x630:
        # vpermwi128), VX128 (0x3d0), VX128_R compares (0x390, bit 0x40 = record form)
        n = OP6B.get(w & 0x7f0)
        if n and n not in ('vrlimi128', 'vpkd3d128'):
            return '%s v%d,v%d,imm 0x%x' % (n, vd128(w), vb128(w), (w >> 16) & 31)
        if (w & 0x730) == 0x710:
            # vD = (vD & ~mask) | (rotl_words(vB, z) & mask); mask bits 8,4,2,1 = words x,y,z,w
            return 'vrlimi128 v%d,v%d,mask 0x%x,rot %d' % (vd128(w), vb128(w), (w >> 16) & 31, (w >> 6) & 3)
        if (w & 0x730) == 0x610:
            return 'vpkd3d128 v%d,v%d,0x%x,%d,%d' % (vd128(w), vb128(w), (w >> 18) & 7, (w >> 16) & 3, (w >> 6) & 3)
        if (w & 0x630) == 0x210:
            return 'vpermwi128 v%d,v%d,0x%02x' % (vd128(w), vb128(w), ((w >> 16) & 31) | ((w >> 6) & 7) << 5)
        n = {0x050: 'vrlw128', 0x0d0: 'vslw128', 0x150: 'vsraw128', 0x1d0: 'vsrw128', 0x280: 'vmaxfp128',
             0x2c0: 'vminfp128', 0x300: 'vmrghw128', 0x340: 'vmrglw128', 0x380: 'vupkhsb128',
             0x3c0: 'vupklsb128'}.get(w & 0x3d0)
        if n:
            return '%s v%d,v%d,v%d' % (n, vd128(w), va128(w), vb128(w))
        n = {0x000: 'vcmpeqfp128', 0x080: 'vcmpgefp128', 0x100: 'vcmpgtfp128', 0x180: 'vcmpbfp128',
             0x200: 'vcmpequw128'}.get(w & 0x390)
        if n:
            return '%s%s v%d,v%d,v%d' % (n, '.' if w & 0x40 else '', vd128(w), va128(w), vb128(w))
    if op in (4, 5, 6):
        return 'vmx128? op%d word 0x%08x' % (op, w)
    return None


def main(argv):
    d = open(argv[0], 'rb').read()
    if argv[1] == '--words':
        a, n = int(argv[2], 16), int(argv[3])
        for k in range(n):
            print('0x%08x  0x%08x' % (a + 4 * k, struct.unpack_from('>I', d, a + 4 * k - BASE)[0]))
        return
    if argv[1] == '--li':
        # --li IMM[,IMM..]: every `li rD,IMM` (addi rD,0,IMM) in the image - finds the index registers of indexed
        # (VMX128) loads / stores of a structure field such as gameTracker+0x1270
        want = set(int(x, 16) for x in argv[2].split(','))
        for o in range(0, len(d) - 3, 4):
            w = struct.unpack_from('>I', d, o)[0]
            if (w >> 26) == 14 and ((w >> 16) & 31) == 0 and (w & 0xffff) in want:
                print('0x%08x  li r%d,0x%x' % (BASE + o, (w >> 21) & 31, w & 0xffff))
        return
    if argv[1] == '--recs':
        # --recs TABLE NWORDS [ID,ID..]: records {id, NWORDS-1 words} until id 0; only the listed ids if given
        a, n = int(argv[2], 16), int(argv[3])
        want = set(int(x) for x in argv[4].split(',')) if len(argv) > 4 else None
        k = 0
        while True:
            rec = struct.unpack_from('>%dI' % n, d, a + 4 * n * k - BASE)
            if want is None or rec[0] in want:
                print('#%d 0x%08x  %d  %s' % (k, a + 4 * n * k, rec[0], ' '.join('0x%08x' % x for x in rec[1:])))
            if rec[0] == 0:
                break
            k += 1
        return
    a = int(argv[1], 16)
    if argv[2] == '--to':
        end = int(argv[3], 16)
    else:
        end = a + 4 * int(argv[2])
    md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
    while a < end:
        w = struct.unpack_from('>I', d, a - BASE)[0]
        text = None
        if (w >> 26) in (5, 6) or ((w >> 26) == 4 and (w & 0x7f3) in LS128):
            text = vmx128(w)
        if text is None:
            ins = list(md.disasm(struct.pack('>I', w), a, 1))
            text = ('%s %s' % (ins[0].mnemonic, ins[0].op_str)) if ins else (vmx128(w) or '.long 0x%08x' % w)
        print('0x%08x  %08x  %s' % (a, w, text))
        a += 4


if __name__ == '__main__':
    main(sys.argv[1:])
