"""Second, independent VMX128 decoder for Xbox 360 code, built from Xenia's public decoder tables, with the operand
semantics of each form (read-only; 2026-11-04, TU states 1019 / 1020, docs Befund-Schattenkampf-0411b.md).

tools/ppc_dis128.py decodes VMX128 with masks in LSB bit numbering. This tool re-implements, for the forms the
shadow-combat states use, the decoder of the Xenia emulator as published (github.com/xenia-project/xenia, BSD
licence, files src/xenia/cpu/ppc/ppc_opcode_lookup_gen.cc - opcode keys in IBM bit numbering, ExtractBits(code, a,
b) = (code >> (31 - b)) & ((1 << (b - a + 1)) - 1) -, ppc_instr.h - VX128 / VX128_1 / VX128_3 / VX128_4 / VX128_R
field layout - and ppc_emit_altivec.cc - the operation of each form, read 2026-11-04). For every 32-bit word with
primary opcode 4 / 5 / 6 in an address range it prints both decodings (this one and ppc_dis128's) and the operation,
and counts disagreements and words this table does not know. Exit code 1 if any decoding disagrees or is unknown.

Operations (Xenia ppc_emit_altivec.cc; note the VMX128 multiply-add forms reuse VD as an operand):
  vmaddfp128   vD = vA * vB + vD          (InstrEmit_vmaddfp_(VD, VA, VD, VB), helper: va * vc + vb)
  vmaddcfp128  vD = vA * vD + vB
  vnmsubfp128  vD = vD - vA * vB          (InstrEmit_vnmsubfp_(VD, VA, VD, VB), helper: -(va * vc - vb))
  vmsum3fp128  vD.xyzw = vA.x*vB.x + vA.y*vB.y + vA.z*vB.z (splat)   (ppc_dis128 calls it vdot3fp128)
  vrlimi128    vD.e = rotl_words(vB, z).e for the elements e whose mask bit is set: 8 = x, 4 = y, 2 = z, 1 = w
  lvlx128      bytes from EA to the end of its 16-byte block into the left part of vD, rest 0
  vcsxwfp128   vD = float(vB as int32) / 2^IMM; vspltisw128 vD = splat(sign-extended IMM); vspltw128 vD = splat(vB.IMM)
  vsel (op 4)  vD = (vC bit 0) ? vA : vB per bit

Usage (from the repository root):
  ../bin/pyt -t 120 tools/vmx128_xenia_check.py IMAGE FROM TO [FROM TO ...]     address ranges, TO exclusive (hex)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_dis128 as D

BASE = 0x82000000


def bits(code, a, b):
    """Xenia ExtractBits: IBM bit numbering (bit 0 = most significant)"""
    return (code >> (32 - 1 - b)) & ((1 << (b - a + 1)) - 1)


OPS = {
    'vmaddfp128': 'vD = vA * vB + vD', 'vmaddcfp128': 'vD = vA * vD + vB', 'vnmsubfp128': 'vD = vD - vA * vB',
    'vmulfp128': 'vD = vA * vB', 'vsubfp128': 'vD = vA - vB', 'vaddfp128': 'vD = vA + vB',
    'vmsum3fp128': 'vD.xyzw = dot3(vA, vB)', 'vor128': 'vD = vA | vB (copy if vA == vB)',
    'vperm128': 'vD = permute(vA, vB, vC)', 'vrsqrtefp128': 'vD = 1 / sqrt(vB) (estimate)',
    'vcsxwfp128': 'vD = float(vB int) / 2^IMM', 'vspltisw128': 'vD = splat(simm5)', 'vspltw128': 'vD = splat(vB[IMM])',
    'vrlimi128': 'vD.e = rotl(vB, z).e where mask bit e (8 x, 4 y, 2 z, 1 w)', 'vcmpeqfp128': 'vD = (vA == vB) ? ~0 : 0',
    'lvx128': 'vD = mem16[EA & ~15]', 'stvx128': 'mem16[EA & ~15] = vD', 'lvlx128': 'vD = left part from EA, rest 0',
}


def xenia_name(w):
    op = bits(w, 0, 5)
    if op == 4:
        k = (bits(w, 21, 27) << 4) | bits(w, 30, 31)
        return {0b00011000011: 'lvx128', 0b00111000011: 'stvx128', 0b10000000011: 'lvlx128'}.get(k)
    if op == 5:
        if ((bits(w, 22, 22) << 5) | bits(w, 27, 27)) == 0:
            return 'vperm128'
        k = (bits(w, 22, 25) << 2) | bits(w, 27, 27)
        return {0b000101: 'vsubfp128', 0b001001: 'vmulfp128', 0b001101: 'vmaddfp128', 0b010001: 'vmaddcfp128',
                0b010101: 'vnmsubfp128', 0b011001: 'vmsum3fp128', 0b101101: 'vor128'}.get(k)
    if op == 6:
        k = bits(w, 21, 27)
        n = {0b0101011: 'vcsxwfp128', 0b1100111: 'vrsqrtefp128', 0b1110011: 'vspltw128',
             0b1110111: 'vspltisw128'}.get(k)
        if n:
            return n
        if ((bits(w, 21, 23) << 4) | bits(w, 26, 27)) == 0b1110001:
            return 'vrlimi128'
        if ((bits(w, 22, 24) << 3) | bits(w, 27, 27)) == 0:
            return 'vcmpeqfp128'
    return None


def fields(w, name):
    """register / immediate fields from the Xenia struct layouts (ppc_instr.h)"""
    vd = bits(w, 6, 10) | (bits(w, 28, 29) << 5)                      # VD128l | VD128h << 5
    vb = bits(w, 16, 20) | (bits(w, 30, 31) << 5)                     # VB128l | VB128h << 5
    va = bits(w, 11, 15) | (bits(w, 26, 26) << 5) | (bits(w, 21, 21) << 6)   # VA128l | VA128h << 5 | VA128H << 6
    if name in ('lvx128', 'stvx128', 'lvlx128'):                     # VX128_1: RA, RB
        return 'v%d, r%d, r%d' % (vd, bits(w, 11, 15), bits(w, 16, 20))
    if name in ('vcsxwfp128', 'vrsqrtefp128', 'vspltw128', 'vspltisw128'):   # VX128_3: IMM in the VA128l place
        return 'v%d, v%d, imm %d' % (vd, vb, bits(w, 11, 15))
    if name == 'vrlimi128':                                          # VX128_4: IMM mask, z rotation
        return 'v%d, v%d, mask 0x%x, rot %d' % (vd, vb, bits(w, 11, 15), bits(w, 24, 25))
    return 'v%d, v%d, v%d' % (vd, va, vb)


def main(argv):
    if len(argv) < 3 or len(argv) % 2 == 0:
        print(__doc__); return 2
    d = open(argv[0], 'rb').read()
    seen = bad = unknown = 0
    for k in range(1, len(argv), 2):
        a, end = int(argv[k], 16), int(argv[k + 1], 16)
        while a < end:
            w = struct.unpack_from('>I', d, a - BASE)[0]
            if (w >> 26) in (4, 5, 6):
                mine = D.vmx128(w) if ((w >> 26) in (5, 6) or (w & 0x7f3) in D.LS128) else None
                name = xenia_name(w)
                if (w >> 26) == 4 and name is None and mine is None:
                    a += 4
                    continue            # a standard AltiVec op-4 instruction (capstone's job), e.g. vsel
                seen += 1
                mine_name = (mine or '').split(' ')[0].replace('vdot3fp128', 'vmsum3fp128')
                text = '%s %s' % (name, fields(w, name)) if name else 'UNKNOWN'
                if name is None:
                    unknown += 1; flag = 'UNKNOWN'
                elif mine_name != name:
                    bad += 1; flag = 'DIFFERS'
                else:
                    flag = 'same'
                print('0x%08x  %08x  %-44s | ppc_dis128: %-40s %-7s %s' % (a, w, text, mine, flag,
                                                                          OPS.get(name, '') if name else ''))
            a += 4
    print('VMX128 words: %d, decoded the same: %d, differing: %d, unknown to this table: %d' % (
        seen, seen - bad - unknown, bad, unknown))
    return 1 if bad or unknown else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
