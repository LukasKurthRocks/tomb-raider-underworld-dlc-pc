"""Port shader library helpers for our shader tools (shader_const_fix, shader_lib_check, shader_find).

Copied unchanged from upstream's tools/native_test/native_extract.py as of 72b4ceb (B138): upstream's native test v3
(merged 2026-11-05, 7761890) no longer has NEW_LIBS / shader_sections, so our tools keep their own copy here instead of
importing the test script. Standard library only.
"""
import struct, zlib

# the port's own (generated) shader libraries; everything else in a DRM is copied from the PC game
NEW_LIBS = {2173} | set(range(2720, 2784))


def cdrm_decode(d):
    if d[:4] not in (b'CDRM', b'MRDC'): return d
    n, = struct.unpack('<I', d[8:12])
    ents = [struct.unpack('<II', d[16 + 8 * i:24 + 8 * i]) for i in range(n)]
    pos = (16 + 8 * n + 15) & ~15
    out = bytearray()
    for u, c in ents:
        blk = d[pos:pos + c]
        out += zlib.decompress(blk) if (u & 0xff) == 2 else blk
        pos = (pos + c + 15) & ~15
    return bytes(out)


def shader_sections(raw):
    ver, namesz, padsz, u0, u1, n = struct.unpack('<iiiiii', raw[:24])
    secs, p = [], 24
    for _ in range(n):
        size, typ, pad, vid, packed, sid, spec = struct.unpack('<iBBHIII', raw[p:p + 20]); p += 20
        secs.append((size, typ, packed >> 8, sid))
    p += namesz + padsz
    for size, typ, nreloc, sid in secs:
        p += nreloc
        if typ == 9: yield sid, raw[p:p + size]
        p += size


def lib_blobs(d):
    """ShaderLib section: u8 kind, 3 pad, u32 tableBytes, u32 dataSize, u32 slot[]; entry @4+off: u32 junk, u32 size, u64 hash, bytecode."""
    tb, = struct.unpack_from('<I', d, 4)
    for slot, off in enumerate(struct.unpack_from('<%dI' % (tb // 4), d, 12)):
        if off == 0xffffffff: continue
        size, = struct.unpack_from('<I', d, 4 + off + 4)
        code = d[4 + off + 16:4 + off + 8 + size]
        for i in range(0, len(code) - 3, 4):   # cut at the END token
            if code[i:i + 4] == b'\xff\xff\x00\x00': code = code[:i + 4]; break
        yield slot, code
