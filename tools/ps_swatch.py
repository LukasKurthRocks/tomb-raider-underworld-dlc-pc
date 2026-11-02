"""Offline look preview of a material's pass-2 pixel shader (read-only, no window, no game): runs one PC PS slot in the
SM3 VM (upstream work/ws/shader4/sm3vm) over a UV grid with the material's REAL textures (decoded PCD9, nearest,
wrap), its MaterialParams and a neutral environment, and writes a PNG. Test 50a: the doppelganger's translated TU
shaders (Xbox params) against the surrogates of 48m (copied params) - which colour to expect in game.

Environment (stated, not measured from the game): flat tangent frame (texcoord2 / 3 / 4 = identity rows, normal +z),
world position (0.1, 0.2, 0.3) with fog 0, camera at (3, 2, 10) (g_CameraPosition; not along the normal - view exactly along the normal gives normalize(0) = NaN in the fabric term of the TU cloth shaders), MaterialOpacity 1, no fog, irradiance = uniform white ambient
(IrradianceStateBase 1, Red0..Blue1 0, g_Ambient 1), every other constant 0. Slot 0 = no dynamic light (light bools off);
--light: slot 2 (PC b3 = first non-shadow light) with one white light along the normal (constants of that light =
derived from the donor CTAB names, see `consts`).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/ps_swatch.py PC.drm MATERIAL OUT.png [--lib ID] [--slot K] [--params Xbox.drm] [--size N]
  ../bin/pyt -t 600 tools/ps_swatch.py consts PC.drm LIB SLOT     constants the entry reads, with PC CTAB names
  ../bin/pyt -t 900 tools/ps_swatch.py sheet OLD.drm NEW.drm MAT[,MAT] OUT.png AMB IRR   old | new | new normalised
  options: --amb G (g_Ambient), --irr B (IrradianceStateBase), --dump R,R (temps at the end), --nan (first NaN writes),
           --tex REG=r,g,b,a (constant for a sampler without a material record, e.g. the terrain Setup map s0; repeatable)
"""
import sys, os, struct, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'shader4')); sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'xenos'))
import drm_write as DW, drm_reloc as R, shaderlib as SL, tex_convert as TC
import sm3asm, sm3dis, sm3vm
from f3_common import pc_names, inputs_of


def load(path, e):
    D = DW.read(open(path, 'rb').read(), e)
    return {(s.type, s.id): s for s in D.sections}


def mparams(s, e):
    f = '>' if e == 'be' else '<'
    o = dict(R.parse(s.reloc, e).internal).get(0x5C); n = struct.unpack_from(f + 'I', s.data, 0x58)[0]
    return [struct.unpack_from(f + '4f', s.data, o + 16 * j) for j in range(n)] if o is not None else []


def records(s):
    r = R.parse(s.reloc, 'le'); tp = dict(r.internal).get(0x54); out = []
    for k in range(s.data[0x52]):
        tid = struct.unpack_from('<I', s.data, tp + 16 * k)[0]
        out.append((tid, s.data[tp + 16 * k + 13]))
    return out


def reg_names():
    out = {}
    for n, regs in pc_names().items():
        (ri, rc), _ = regs[0]
        for j in range(rc): out.setdefault(ri + j, '%s[%d]' % (n, j))
    return out


def entry(by, lib, slot):
    L = SL.parse(by[(9, lib)].data, 'le'); o = L['slots'][slot]
    if o == 0xffffffff: raise SystemExit('lib %d slot %d empty' % (lib, slot))
    b = L['entries'][o]['blob']
    return sm3asm.decode(b[:sm3dis.bytecode_len(b)])


def consts_read(prog):
    return sorted({o.num for i in prog.instrs() for o in i.ops if o.rtype == sm3asm.RT_CONST and not o.isdst} -
                  {i.ops[0].num for i in prog.instrs() if i.op == 'def'})


def cmd_consts(pcf, lib, slot):
    by = load(pcf, 'le'); prog = entry(by, lib, slot); rn = reg_names()
    print('lib %d slot %d reads: %s' % (lib, slot, ', '.join('c%d=%s' % (r, rn.get(r, '?')) for r in consts_read(prog))))
    ins, vmap = inputs_of(prog); print('inputs %s' % sorted(ins, key=str))


def env_consts(prog, mp, light, amb=1.0, irr=1.0):
    rn = reg_names(); c = {r: np.zeros(4, np.float32) for r in range(256)}
    for j, v in enumerate(mp): c[100 + j] = np.array(v, np.float32)
    for r, n in rn.items():
        if n.startswith('IrradianceStateBase'): c[r] = np.array([irr, irr, irr, irr], np.float32)
        elif n.startswith('g_Ambient'): c[r] = np.array([amb, amb, amb, amb], np.float32)
        elif n.startswith('MaterialOpacity'): c[r] = np.array([1, 1, 1, 1], np.float32)
        elif n.startswith('g_CameraPosition'): c[r] = np.array([3, 2, 10, 1], np.float32)
    if light:
        # NonShadowLights c193 x15 (3 lights x 5 vec4): position, direction, attenuation, ..., colour - set from the
        # donor's reading pattern: position at +z, colour white, no attenuation / cone (see Befund 50a)
        base = 193
        c[base] = np.array([0, 0, 10, 0], np.float32)          # position
        c[base + 1] = np.array([0, 0, -1, 0], np.float32)      # direction
        c[base + 2] = np.array([0, 0, 1, 0.5], np.float32)     # attenuation scale / offset (texcoord into s15: (1, 0.5))
        c[base + 3] = np.array([1, 0, 0, 0], np.float32)       # cone scale / bias -> saturate(1)
        c[base + 4] = np.array([1, 1, 1, 0], np.float32)       # colour
    return c


def swatch(by, mat, lib, slot, mp, size, light=False, amb=1.0, irr=1.0):
    prog = entry(by, lib, slot)
    texs = {}
    for tid, reg in records(by[(10, mat)]):
        s = by.get((5, tid))
        if s is None: continue
        im = TC.pc_image(s.data).astype(np.float32) / 255.0
        if im.shape[-1] == 3: im = np.concatenate([im, np.ones(im.shape[:2] + (1,), np.float32)], axis=-1)
        texs[reg] = im
    def tex(num, coords, mode):
        im = texs.get(num)
        n = coords.shape[0]
        if im is None:
            if num in CONST_TEX:   # --tex REG=r,g,b,a: constant for a sampler without a material record (test 50c)
                return np.tile(np.float32(CONST_TEX[num]), (n, 1))
            if num == 15:   # AttenuationSampler: fog lookup (y = HeightFogParams.z = 0) -> 0 = no fog; light attenuation (y = 0.5) -> 1
                return np.repeat((coords[:, 1:2] > 0.25).astype(np.float32), 4, axis=1)
            return np.full((n, 4), 0.5, np.float32)
        h, w = im.shape[:2]
        x = (np.floor(np.mod(coords[:, 0], 1.0) * w).astype(int)) % w
        y = (np.floor(np.mod(coords[:, 1], 1.0) * h).astype(int)) % h
        return im[y, x]
    N = size * size
    u, v = np.meshgrid((np.arange(size) + 0.5) / size, (np.arange(size) + 0.5) / size)
    uv = np.stack([u.ravel(), v.ravel(), np.zeros(N), np.zeros(N)], axis=1).astype(np.float32)
    ins, vmap = inputs_of(prog)
    val = {(5, 0): uv, (5, 2): np.tile(np.float32([1, 0, 0, 0]), (N, 1)), (5, 3): np.tile(np.float32([0, 1, 0, 0]), (N, 1)),
           (5, 4): np.tile(np.float32([0, 0, 1, 0]), (N, 1)), (5, 5): np.tile(np.float32([0.1, 0.2, 0.3, 0]), (N, 1)),
           (5, 6): np.zeros((N, 4), np.float32), (10, 0): np.ones((N, 4), np.float32)}
    inp = {(sm3asm.RT_INPUT, vmap[s]): val.get(s, np.zeros((N, 4), np.float32)) for s in vmap if s[0] != 'misc'}
    inp[(sm3asm.RT_MISC, 0)] = np.zeros((N, 4), np.float32); inp[(sm3asm.RT_MISC, 1)] = np.ones((N, 4), np.float32)
    c = env_consts(prog, mp, light, amb, irr)
    bools = {3: True} if light else {}
    if NANS:
        class NV(sm3vm.VM):
            first = []
            def write(self, d, val, m):
                if np.isnan(val[m]).any() and len(NV.first) < 6:
                    NV.first.append(sm3asm.fmt_instr(self._cur, 'ps'))
                return sm3vm.VM.write(self, d, val, m)
            def _alu(self, it, srcs):
                self._cur = it
                if any(np.isnan(s).any() for s in srcs): self._srcnan = True
                return sm3vm.VM._alu(self, it, srcs)
        vm = NV(prog, N, dict(inp), c, tex, bools); vm.exec()
        print('   first NaN-producing instructions: %s' % NV.first)
    if DUMP:
        vm = sm3vm.VM(prog, N, dict(inp), c, tex, bools); vm.exec()
        for r in DUMP: print("   r%d end: mean %s min %s max %s" % (r, np.round(np.nanmean(vm.reg[(0, r)], 0), 3), np.round(np.nanmin(vm.reg[(0, r)], 0), 3), np.round(np.nanmax(vm.reg[(0, r)], 0), 3)))
    out = sm3vm.run(prog, inp, c, tex, N, bools)
    col = np.nan_to_num(out.get('oC0', np.zeros((N, 4), np.float32)))
    return col.reshape(size, size, 4)


DUMP = []; NANS = False; CONST_TEX = {}


def main(a):
    global DUMP, NANS
    NANS = "--nan" in a
    while '--tex' in a:      # --tex REG=r,g,b,a (repeatable)
        k = a.index('--tex'); r, v = a[k + 1].split('='); CONST_TEX[int(r)] = [float(x) for x in v.split(',')]; del a[k:k + 2]
    if "--dump" in a: DUMP = [int(x) for x in a[a.index("--dump") + 1].split(",")]
    if a and a[0] == "consts": cmd_consts(a[1], int(a[2]), int(a[3])); return
    if a and a[0] == "sheet": cmd_sheet(a[1], a[2], [int(x) for x in a[3].split(",")], a[4], float(a[5]), float(a[6])); return
    pcf, mat, outp = a[0], int(a[1]), a[2]
    by = load(pcf, 'le')
    m = by[(10, mat)]
    lib = int(a[a.index('--lib') + 1]) if '--lib' in a else struct.unpack_from('<4I', m.data, 0x28)[2]
    slot = int(a[a.index('--slot') + 1]) if '--slot' in a else 0
    size = int(a[a.index('--size') + 1]) if '--size' in a else 128
    mp = mparams(m, 'le')
    if '--params' in a: mp = mparams(load(a[a.index('--params') + 1], 'be')[(10, mat)], 'be')
    amb = float(a[a.index('--amb') + 1]) if '--amb' in a else 1.0; irr = float(a[a.index('--irr') + 1]) if '--irr' in a else 1.0
    img = swatch(by, mat, lib, slot, mp, size, light='--light' in a, amb=amb, irr=irr)
    rgb = np.clip(img[..., :3], 0, 1)
    from PIL import Image
    Image.fromarray((rgb * 255 + 0.5).astype(np.uint8)).save(outp)
    print('material %d lib %d slot %d%s: mean rgb %s, min %s, max %s, alpha mean %.3f -> %s'
          % (mat, lib, slot, ' (light)' if '--light' in a else '', np.round(img[..., :3].reshape(-1, 3).mean(0), 3),
             np.round(img[..., :3].reshape(-1, 3).min(0), 3), np.round(img[..., :3].reshape(-1, 3).max(0), 3), float(img[..., 3].mean()), outp))




def cmd_sheet(pcf_old, pcf_new, mats, outp, amb, irr):
    """contact sheet: per material old (48m) raw | new raw | new normalised to its 99th percentile (hue)"""
    from tex_dlc import contact_sheet
    bo, bn = load(pcf_old, 'le'), load(pcf_new, 'le'); cells = []
    for m in mats:
        for tag, by in (('old', bo), ('new', bn)):
            lib = struct.unpack_from('<4I', by[(10, m)].data, 0x28)[2]
            img = swatch(by, m, lib, 0, mparams(by[(10, m)], 'le'), 96, amb=amb, irr=irr)[..., :3]
            cells.append(('%d %s %d' % (m, tag, lib), (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)))
            if tag == 'new':
                k = max(float(np.percentile(img, 99)), 1e-6)
                cells.append(('%d new /%.2f' % (m, k), (np.clip(img / k, 0, 1) * 255 + 0.5).astype(np.uint8)))
    contact_sheet(cells, outp, cell=96, cols=6)
    print('sheet %s: %d cells' % (outp, len(cells)))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
