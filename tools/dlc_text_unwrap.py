"""Remove the hard line breaks from the DLC mission descriptions in all locals.bin files.

The DLC 1 / DLC 2 descriptions (string index 456 / 457) carry hard line breaks every 47-52 characters in every
language. With the Xbox title-update text style (tools/dlc_screen_text_style.py) the description box auto-wraps;
English happens to fit the hard breaks, the longer lines of the other languages overflow and leave a single word on
its own line ("meinem", "Geheimkammer"). Replacing each '\\n' of these two strings by a space lets the game wrap
them itself - one rule for every language. Same length, so offsets do not change.

Usage (from the repository root):  ..\\bin\\venv\\Scripts\\python.exe -I tools/dlc_text_unwrap.py [src dir]
  src dir defaults to ../data/pc/mods/local/ (the installed build)
  -> work/dlc_text/local/locals.bin_<NNN> (+ md5.txt, patch_log.txt)
Pipeline: since 2026-11-11 the same rule runs inside `tools/locals.py build` (unwrap_descriptions); this tool stays
for patching an existing set of tables.
"""
import sys, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals as L

SRC = sys.argv[1] if len(sys.argv) > 1 else '../data/pc/mods/local/'
OUT = 'work/dlc_text/local/'
INDICES = (456, 457)
LANGS = ('001', '002', '004', '008', '016', '032')


def main():
    log, md5s = [], []
    os.makedirs(OUT, exist_ok=True)
    _, en, _ = L.parse(open(os.path.join(SRC, 'locals.bin_001'), 'rb').read(), 'le')
    assert en[456].startswith(b'Recently I have come across') and en[457].startswith(b"Jormungandr's awakening")
    for lang in LANGS:
        name = 'locals.bin_' + lang
        raw = open(os.path.join(SRC, name), 'rb').read()
        _, strs, offs = L.parse(raw, 'le')
        out = bytearray(raw)
        targets = {strs[i] for i in INDICES}
        changed = 0
        for k, s in enumerate(strs):
            if s in targets and b'\n' in s:
                o = offs[k]
                assert raw[o:o + len(s)] == s
                out[o:o + len(s)] = s.replace(b'\n', b' ')
                changed += 1
        assert len(out) == len(raw)
        _, strs2, _ = L.parse(bytes(out), 'le')
        assert all(b'\n' not in strs2[i] for i in INDICES)
        open(OUT + name, 'wb').write(out)
        md5 = hashlib.md5(out).hexdigest()
        md5s.append('%s  %s' % (md5, name))
        log.append('%s: source md5 %s, %d strings unwrapped -> md5 %s' % (name, hashlib.md5(raw).hexdigest(), changed, md5))
    open(OUT + 'md5.txt', 'w').write('\n'.join(md5s) + '\n')
    open(OUT + 'patch_log.txt', 'w').write('\n'.join(log) + '\n')
    print('\n'.join(log))


if __name__ == '__main__':
    main()
