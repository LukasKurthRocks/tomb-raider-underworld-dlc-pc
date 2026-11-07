"""Chunkdoll piece records of an object DRM, PC (little-endian) against Xbox (big-endian), read-only
(docs/Befund-ChunkDoll-Absturz-0711.md, "ChunkDoll: failed to create geom").

Engine path (PC tru.exe, same layout in the Xbox retail / TU exe):
  create chunkdoll tru+0x296f90 (retail 0x823769a0, TU 0x823766c0): object data D = [[object]+0xc8]
    D+0x10 s32  minimum piece count (< 0: no check)      D+0x14 s32  pieces that may be dropped (< 0: no check)
    D+0x18 s32  piece count N                            D+0x1c ptr  N piece records of 0x14 bytes
  spawn piece tru+0x296b90 (retail 0x823761d0, TU 0x82375ea0) reads per record:
    +0x00 u8   model index -> body create tru+0x97270(inst, model, +0x0c, 0, 0.0) (retail 0x82136790)
    +0x02 s16  bone A of the parent       +0x04 s16  bone B of the parent   +0x08 f32  lerp A -> B
    +0x0c u32  argument 3 of the body create                                +0x10 u32  flags (bit 0)
The chain object section -> DTP is followed through the relocations: the object section's id reference at offset 0
names the DTP (the engine resolves it to a pointer), the DTP's internal / external pointer at +0xc8 gives D, the
pointer at D+0x1c the records. Values are decoded per field type (u8 / s16 / f32 / u32), so a byte-order error in the
conversion shows as a value difference.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/chunkdoll_records.py PC.drm [XBOX.drm]
  XBOX.drm: a raw big-endian DRM, e.g. written by tools/dlc_xbox_dump.py
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def load(path, endian):
    D = DW.read(open(path, 'rb').read(), endian)
    rel = [R.parse(s.reloc, endian) for s in D.sections]
    return D.sections, rel


def ptr_at(secs, rel, si, off):
    """target (section index, offset) of the pointer stored at section si + off, or None"""
    for o, t in rel[si].internal:
        if o == off: return si, t
    for di, s, d in rel[si].external:
        if s == off: return di, d
    return None


def chunk_data(path, endian):
    e = '>' if endian == 'be' else '<'
    secs, rel = load(path, endian)
    oi = next(i for i, s in enumerate(secs) if s.type == 11)
    obj = secs[oi]
    ids = {o: t for t, o in rel[oi].idref}
    if 0 not in ids: raise SystemExit('%s: object section has no id reference at +0' % path)
    dtp_id = struct.unpack_from(e + 'I', obj.data, 0)[0]
    di = next(i for i, s in enumerate(secs) if s.type == ids[0] and s.id == dtp_id)
    p = ptr_at(secs, rel, di, 0xc8)
    if p is None: raise SystemExit('%s: DTP %d has no pointer at +0xc8' % (path, dtp_id))
    si, so = p
    d = secs[si].data
    hdr = struct.unpack_from(e + '7i', d, so)
    q = ptr_at(secs, rel, si, so + 0x1c)
    recs = []
    if q is not None:
        ri, ro = q
        rd = secs[ri].data
        for k in range(max(hdr[6], 0)):
            b = ro + 0x14 * k
            raw = rd[b:b + 0x14]
            m, b1 = raw[0], raw[1]
            ba, bb, w6 = struct.unpack_from(e + 'hhh', raw, 2)
            lerp, = struct.unpack_from(e + 'f', raw, 8)
            a3, fl = struct.unpack_from(e + 'II', raw, 0xc)
            recs.append(dict(model=m, b1=b1, boneA=ba, boneB=bb, w6=w6, lerp=lerp, arg3=a3, flags=fl, raw=raw.hex()))
    return dict(obj_id=obj.id, dtp=dtp_id, sec=(secs[si].type, secs[si].id), off=so, hdr=hdr,
                rec_at=q and (secs[q[0]].type, secs[q[0]].id, q[1]), recs=recs)


def show(tag, c):
    print('%s: object %d -> DTP %d +0xc8 -> section (%d, %d) +0x%x' % (tag, c['obj_id'], c['dtp'], c['sec'][0],
                                                                       c['sec'][1], c['off']))
    h = c['hdr']
    print('  D+0x00..0x18: %s   (min pieces %d, droppable %d, piece count %d)' % (
        ' '.join('%d' % v for v in h), h[4], h[5], h[6]))
    print('  records at %s' % (c['rec_at'],))
    for k, r in enumerate(c['recs']):
        print('  #%-2d model %3d  b1 %3d  bones %3d %3d  w6 %5d  lerp %8.4f  arg3 %10d  flags 0x%08x  raw %s' % (
            k, r['model'], r['b1'], r['boneA'], r['boneB'], r['w6'], r['lerp'], r['arg3'], r['flags'], r['raw']))


def main(argv):
    if not argv: sys.exit(__doc__)
    pc = chunk_data(argv[0], 'le')
    show('PC  ' + os.path.basename(argv[0]), pc)
    if len(argv) > 1:
        xb = chunk_data(argv[1], 'be')
        show('XBOX ' + os.path.basename(argv[1]), xb)
        diffs = 0
        if pc['hdr'][4:7] != xb['hdr'][4:7]:
            print('  DIFF header counts: PC %s Xbox %s' % (pc['hdr'][4:7], xb['hdr'][4:7])); diffs += 1
        for k, (a, b) in enumerate(zip(pc['recs'], xb['recs'])):
            for f in ('model', 'b1', 'boneA', 'boneB', 'w6', 'lerp', 'arg3', 'flags'):
                if a[f] != b[f]:
                    print('  DIFF record #%d %s: PC %r Xbox %r' % (k, f, a[f], b[f])); diffs += 1
        print('  result: %d field difference(s) in %d / %d records' % (diffs, len(pc['recs']), len(xb['recs'])))


if __name__ == '__main__':
    main(sys.argv[1:])
