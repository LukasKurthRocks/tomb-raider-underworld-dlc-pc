"""Print the plain header fields of an Xbox 360 XEX2 executable or XEXP patch (read-only; nothing is decrypted).

Finding 43 follow-up (DLC 2 shadow power): is the title update's default.xexp a delta patch of default.xex, how big
is the image, where is it loaded - the facts needed to plan a guest-memory dump of the patched image from Xenia.

Shown: module flags (title / patch / delta / full), data offset, image size and load address, entry point, the
optional header list (id -> value or offset), the file format info (encryption 0 none / 1 normal, compression
0 none / 1 basic / 2 normal (LZX) / 3 delta) and, for patches, the delta patch descriptor (target / source version,
new image size).

Usage (from the repository root):
  ../bin/pyt -t 60 tools/xex_info.py FILE.xex|FILE.xexp [...]
"""
import sys, struct

FLAGS = {0x1: 'title', 0x2: 'exports_to_title', 0x4: 'system_debugger', 0x8: 'dll', 0x10: 'module_patch',
         0x20: 'patch_full', 0x40: 'patch_delta', 0x80: 'user_mode'}
NAMES = {0x000002ff: 'resource_info', 0x000003ff: 'file_format_info', 0x000005ff: 'delta_patch_descriptor',
         0x00010001: 'original_base_address', 0x00010100: 'entry_point', 0x00010201: 'image_base_address',
         0x000103ff: 'import_libraries', 0x00018002: 'checksum_timestamp', 0x00018102: 'enabled_for_callcap',
         0x00018200: 'enabled_for_fastcap', 0x000183ff: 'original_pe_name', 0x000200ff: 'static_libraries',
         0x00020104: 'tls_info', 0x00020200: 'default_stack_size', 0x00020301: 'default_filesystem_cache_size',
         0x00020401: 'default_heap_size', 0x00028002: 'page_heap_size_and_flags', 0x00030000: 'system_flags',
         0x00040006: 'execution_info', 0x00040201: 'title_workspace_size', 0x00040310: 'game_ratings',
         0x00040404: 'lan_key', 0x000405ff: 'xbox360_logo', 0x000406ff: 'multidisc_media_ids',
         0x000407ff: 'alternate_title_ids', 0x00040801: 'additional_title_memory', 0x00e10402: 'exports_by_name'}
U32 = lambda d, o: struct.unpack_from('>I', d, o)[0]


def info(path):
    d = open(path, 'rb').read()
    print('==', path, len(d), 'bytes')
    if d[:4] != b'XEX2':
        print('  not an XEX2 file'); return
    flags, data_off, sec_off, count = U32(d, 4), U32(d, 8), U32(d, 0x10), U32(d, 0x14)
    print('  module flags 0x%08x (%s), data offset 0x%x, security info 0x%x, %d optional headers'
          % (flags, ', '.join(n for b, n in FLAGS.items() if flags & b), data_off, sec_off, count))
    if sec_off + 8 <= len(d):
        print('  image size 0x%x (%.1f MB)' % (U32(d, sec_off + 4), U32(d, sec_off + 4) / 1048576.0))
    for i in range(count):
        hid, val = U32(d, 0x18 + 8 * i), U32(d, 0x1c + 8 * i)
        print('  header 0x%08x %-26s 0x%08x' % (hid, NAMES.get(hid, '?'), val))
        if hid == 0x000003ff and val + 8 <= len(d):
            enc, comp = struct.unpack_from('>HH', d, val + 4)
            print('    file format: encryption %d, compression %d' % (enc, comp))
        if hid == 0x000005ff and val + 0x40 <= len(d):
            size, tgt, src = U32(d, val), U32(d, val + 4), U32(d, val + 8)
            # descriptor: size, target version, source version, digest (20), key (16), size of target headers,
            # delta headers source offset / size, delta image source offset / size, delta image target offset
            print('    delta patch: descriptor size 0x%x, target version 0x%08x, source version 0x%08x' % (size, tgt, src))
            print('    words after the digest/key: %s' % ' '.join('%08x' % U32(d, val + 0x30 + 4 * k) for k in range(8)))


if __name__ == '__main__':
    for p in sys.argv[1:]:
        info(p)
