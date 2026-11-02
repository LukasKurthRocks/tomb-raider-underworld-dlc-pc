"""Convert single audio-stream records (.mul) of an Xbox bigfile (e.g. a prototype pack extracted under work/) to PC,
the same two steps as the DLC music / stream route: tools/music_convert.convert_mul (silent PC stub, PC sample count
and block table) then tools/mul_audio_nch.swap (real audio: one channel slot per Xbox stream, the game's IMA
convention). Read-only on the bigfile. Test 50k: prototype-only `mystery_stinger_01.mul` and the unnamed stream
0xac1eae71 of the Lara's Shadow prototype.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/proto_audio_convert.py convert PACK OUT_MODS_DIR KEY[=REL] [KEY[=REL] ...] [--list FILE] [--xbox-out DIR]
      KEY  = a name below xenon-w (e.g. audio\\streams\\music\\stingers\\mystery_stinger_01.mul) or 0xHASH
      REL  = path of the PC file below OUT_MODS_DIR (e.g. audio/streams/music/stingers/mystery_stinger_01.mul)
      --xbox-out DIR: also save the Xbox record there (by the bare file name of REL), e.g. for TRUDLC_EXTRA_XBOX
      prints per stream: specs present, Xbox header (rate, sample count, stream count), duration, PC bytes / md5
  ../bin/pyt -t 900 tools/proto_audio_convert.py refs PACK HASH [TEXT ...] [--names NAMES.json]
      every record of PACK whose decoded bytes contain the u32 HASH (big or little endian) or one of the ASCII
      TEXTs (case-insensitive) - which DRM / list could name the stream; prints the whole strings that contain a TEXT
  ../bin/pyt -t 300 tools/proto_audio_convert.py wav XBOX.mul OUT.wav       listening copy of an Xbox stream (XMA decode)
  ../bin/pyt -t 900 tools/proto_audio_convert.py name PACK HASH[,HASH]   name an unnamed stream: crc of every stream-like
      string of the pack's DRMs under xenon-w/audio/streams/ (backslashes; and variants) compared with HASH
"""
import sys, os, struct, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc


def rec_bytes(A, key):
    h = int(key, 16) if key.lower().startswith('0x') else crc('xenon-w\\' + key)
    rr = {r['spec']: r for r in A.idx if r['hash'] == h}
    if not rr: return h, None, []
    # same choice as music_convert.convert_streams: unlocalised record, else the English + fallback VO variant
    sp = 0xffffffff if 0xffffffff in rr else (0xffffffe1 if 0xffffffe1 in rr else sorted(rr)[0])
    return h, A.read(rr[sp]), sorted(rr)


def cmd_convert(argv):
    import music_convert as MC, mul_audio_nch as MN, mul_audio as MA
    xo = None
    if '--xbox-out' in argv: k = argv.index('--xbox-out'); xo = argv[k + 1]; del argv[k:k + 2]
    keys = []
    if '--list' in argv:        # a file with one KEY or KEY=REL per line
        k = argv.index('--list'); keys = [l.strip() for l in open(argv[k + 1], encoding='utf8') if l.strip()]; del argv[k:k + 2]
    A = Archive(argv[0], 'be'); out = argv[1]
    for kv in argv[2:] + keys:
        # KEY alone: REL = KEY with '/' (a name below xenon-w is also the path below mods)
        key, rel = kv.split('=', 1) if '=' in kv else (kv, kv.replace('\\', '/'))
        h, xd, specs = rec_bytes(A, key)
        if xd is None: print('%s (0x%08x): not in %s' % (key, h, argv[0])); continue
        rate, w1, xt, ch = struct.unpack_from('>4I', xd, 0)
        nst = len(MA.xb_channels(xd)[3])
        silent, T = MC.convert_mul(xd)
        pc, info = MN.swap(xd, silent)
        dst = os.path.join(out, *rel.replace('\\', '/').split('/')); os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(pc)
        if xo:
            os.makedirs(xo, exist_ok=True); open(os.path.join(xo, os.path.basename(dst)), 'wb').write(xd)
        print('%s (0x%08x) specs %s: xbox %d bytes md5 %s, header rate %d word1 %d samples %d word3 %d, streams %s, '
              'duration %.3f s -> PC %d samples (%.3f s), %d bytes md5 %s, swap %s -> %s'
              % (key, h, ' '.join('%08x' % s for s in specs), len(xd), hashlib.md5(xd).hexdigest(), rate, w1, xt, ch,
                 nst, xt / float(rate or 1), T, T / float(rate or 1), len(pc), hashlib.md5(pc).hexdigest(), info, rel))


def cmd_refs(argv):
    from drm import cdrm_decode
    names = {}
    if '--names' in argv:
        k = argv.index('--names'); names = {int(a): b for a, b in json.load(open(argv[k + 1], encoding='utf8')).items()}
        del argv[k:k + 2]
    A = Archive(argv[0], 'be'); hv = int(argv[1], 16)
    pats = [struct.pack('>I', hv), struct.pack('<I', hv)] + [t.lower().encode() for t in argv[2:]]
    seen = set()
    for r in A.idx:
        key = (r['hash'], r['spec'])
        if key in seen: continue
        seen.add(key)
        try: b = A.read(r)
        except Exception as e: print('0x%08x read error %s' % (r['hash'], e)); continue
        try: b = cdrm_decode(b, 'be')
        except Exception: pass
        low = b.lower()
        hit = [p for p in pats if (p in b if len(p) == 4 else p in low)]
        if hit:
            import re
            full = set()            # the whole printable strings that contain a TEXT
            for p in hit:
                if len(p) == 4: continue
                for m in re.finditer(rb'[\x20-\x7e]*' + re.escape(p) + rb'[\x20-\x7e]*', low):
                    full.add(b[m.start():m.end()].decode('ascii', 'replace'))
            print('%-70s spec %08x %9d B: %s%s' % (names.get(r['hash'], '0x%08x' % r['hash']), r['spec'], len(b),
                  ', '.join(('u32 %s' % p.hex()) if len(p) == 4 else p.decode() for p in hit),
                  ('  strings: ' + ' | '.join(sorted(full))) if full else ''))


def cmd_wav(argv):
    """Xbox .mul -> 16-bit WAV (listening copy of the source audio: mul_audio.xb_pcm, the XMA decode that
    mul_audio_nch.swap encodes into the PC file)"""
    import wave, numpy as np, mul_audio as MA
    rate, total, pcm = MA.xb_pcm(open(argv[0], 'rb').read())
    pcm = np.asarray(pcm)
    if pcm.ndim == 1: pcm = pcm[:, None]
    with wave.open(argv[1], 'wb') as w:
        w.setnchannels(pcm.shape[1]); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(np.clip(pcm, -32768, 32767).astype('<i2').tobytes())
    print('%s -> %s: %d Hz, %d channel(s), %d samples, peak %d' % (argv[0], argv[1], rate, pcm.shape[1], len(pcm),
          int(np.abs(pcm).max()) if len(pcm) else 0))


def cmd_name(argv):
    """try to name an unnamed stream hash: every printable string of the pack's DRMs that looks like a stream path
    (contains a backslash or an underscore), as xenon-w\\audio\\streams\\<s>.mul and a few variants"""
    import re
    from drm import cdrm_decode
    A = Archive(argv[0], 'be'); want = {int(x, 16) for x in argv[1].split(',')}
    cand = set(); seen = set()
    for r in A.idx:
        if r['hash'] in seen: continue
        seen.add(r['hash'])
        try: b = cdrm_decode(A.read(r), 'be')
        except Exception: continue
        if b[:4] == b'RIFF' or len(b) < 64: continue
        for m in re.finditer(rb'[A-Za-z0-9_\\/().\- ]{4,120}', b):
            s = m.group().decode().strip().replace('/', '\\')
            if '\\' in s or '_' in s: cand.add(s.lower())
    print('%d candidate strings' % len(cand))
    pre = ('xenon-w\\audio\\streams\\', 'xenon-w\\', 'xenon-w\\audio\\streams\\music\\stingers\\',
           'xenon-w\\audio\\streams\\event_triggered\\', 'xenon-w\\audio\\streams\\vo\\')
    found = 0
    for s in sorted(cand):
        for p in pre:
            for suf in ('.mul', ''):
                h = crc(p + s + suf)
                if h in want: print('0x%08x = %s' % (h, p + s + suf)); found += 1
    if not found: print('no candidate matches %s' % ', '.join('0x%08x' % h for h in sorted(want)))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    {'convert': cmd_convert, 'refs': cmd_refs, 'wav': cmd_wav, 'name': cmd_name}[sys.argv[1]](sys.argv[2:])
