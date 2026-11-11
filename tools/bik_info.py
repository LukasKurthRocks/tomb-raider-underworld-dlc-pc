"""Bink 1 movie headers side by side - read-only (2026-11-11, Q42: our credits_DLC1.bik against the installed one).

RAD conversions of the same source differ byte-wise (encoder build, rate control), so two .bik files are compared by
their header fields: magic (BIKf..i), size, frame count, largest frame, width / height, frame rate, flags, audio
tracks (sample rate, flags, track id) and the duration (frames / fps). The fields are read as scripts/credits_convert.py
validate_bik reads them (header 44 bytes + per audio track: max decoded size, rate / flags, track id).
--ffprobe EXE additionally runs ffprobe on every file (format duration, stream count, video codec) - read only.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/bik_info.py FILE.bik [FILE.bik ...] [--ffprobe ffprobe.exe] [--out REPORT.txt]
Exit 0 = every file is a Bink 1 f-i header with a consistent file size; 1 otherwise. The last column block says which
header fields are equal over all files.
"""
import sys, os, struct, hashlib, json, subprocess


def arg(argv, key, default=None):
    if key in argv:
        k = argv.index(key); v = argv[k + 1]; del argv[k:k + 2]; return v
    return default


def md5_file(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()


def header(p):
    d = open(p, 'rb').read(4096)
    r = dict(file=p, file_size=os.path.getsize(p), md5=md5_file(p), magic=d[:4].decode('latin-1'))
    r['bink1'] = d[:3] == b'BIK' and d[3:4] in (b'f', b'g', b'h', b'i')
    size, frames, largest, _f2, w, h, fn, fd, flags, ntr = struct.unpack_from('<IIIIIIIIII', d, 4)
    r.update(size_field=size, size_ok=(r['file_size'] - 8 == size), frames=frames, largest_frame=largest, width=w,
             height=h, fps_num=fn, fps_den=fd, fps=(fn / fd if fd else 0.0), flags='0x%x' % flags, audio_tracks=ntr)
    r['duration_s'] = round(frames * fd / fn, 3) if fn else 0.0
    tr = []
    for i in range(ntr):
        info, = struct.unpack_from('<I', d, 44 + 4 * ntr + 4 * i)
        tid, = struct.unpack_from('<I', d, 44 + 8 * ntr + 4 * i)
        tr.append('%d Hz flags 0x%x id %d' % (info & 0xffff, info >> 16, tid))
    r['audio'] = '; '.join(tr) or '-'
    return r


def ffprobe(exe, p):
    q = subprocess.run([exe, '-v', 'error', '-show_entries', 'format=duration,nb_streams:stream=codec_name,codec_type,nb_frames',
                        '-of', 'json', p], capture_output=True, text=True)
    if q.returncode != 0: return 'ffprobe exit %d: %s' % (q.returncode, q.stderr.strip()[-200:])
    j = json.loads(q.stdout)
    st = ', '.join('%s %s' % (s.get('codec_type'), s.get('codec_name')) for s in j.get('streams', []))
    f = j.get('format', {})
    return 'duration %s s, %s streams (%s)' % (f.get('duration'), f.get('nb_streams'), st)


def main(argv):
    fp = arg(argv, '--ffprobe')
    out = arg(argv, '--out')
    if not argv: raise SystemExit(__doc__)
    rows = [header(p) for p in argv]
    keys = ['md5', 'file_size', 'magic', 'size_field', 'size_ok', 'frames', 'largest_frame', 'width', 'height', 'fps_num',
            'fps_den', 'fps', 'flags', 'audio_tracks', 'audio', 'duration_s']
    L = []
    for i, r in enumerate(rows):
        L.append('[%d] %s' % (i, r['file']))
        for k in keys: L.append('    %-14s %s' % (k, r[k]))
        if fp: L.append('    %-14s %s' % ('ffprobe', ffprobe(fp, r['file'])))
    if len(rows) > 1:
        same = [k for k in keys if len({str(r[k]) for r in rows}) == 1]
        diff = [k for k in keys if k not in same]
        L.append('equal over all files: ' + (', '.join(same) or '-'))
        L.append('different: ' + (', '.join('%s (%s)' % (k, ' / '.join(str(r[k]) for r in rows)) for k in diff) or '-'))
    bad = [r['file'] for r in rows if not (r['bink1'] and r['size_ok'])]
    L.append('result: %s' % ('ok - every file is Bink 1 f-i with a consistent size' if not bad else 'NOT ok: ' + ', '.join(bad)))
    text = '\n'.join(L)
    print(text)
    if out:
        with open(out, 'w', encoding='utf-8', newline='\n') as f: f.write(text + '\n')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
