"""Voice-line reference scan (read-only): every string "vo\\..." (or another regex) inside the DRMs of one game archive,
with the DTP section that holds it, and whether the matching stream audio\\streams\\<string>.mul exists in the archives
(per spec word = language: ffffffe1 EN/default, ffffe002 FR, ffffe004 DE, ffffe008 IT, ffffe010 ES).

A dialogue DTP (section type 7) of TR Underworld names its stream as a plain path without folder prefix and extension,
e.g. "vo\\dlc2\\doppelganger\\I_DG_PDLC2_MACH_02" at +0x80; the archive hash is crc("<pre>\\audio\\streams\\" + s + ".mul").
The scan decodes each DRM record once (streamed record by record, nothing large stays in memory).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/vo_refs_scan.py SRC [--pat REGEX] [--out TSV] [--words N] [--also SRC2,SRC3]
      SRC/--also: archive keys of tools/locals.SRC (pcbig pcpatch pack10 pack11 tu xbase ...); --also = archives that
      are searched for the stream records too (default: SRC itself); --words N = first N header words of the DTP
"""
import sys, os, re, struct, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc, load, L
from drm import cdrm_decode, sections_with_data

LANG = {0xffffffe1: 'en', 0xffffe002: 'fr', 0xffffe004: 'de', 0xffffe008: 'it', 0xffffe010: 'es', 0xffffffff: 'all'}


def archive_of(key):
    import locals as LC
    path, e, pre = LC.SRC[key]
    return Archive(path, e), e, pre


def spec_map(archives, pre):
    """{hash: sorted language tags} over several archives"""
    d = collections.defaultdict(set)
    for A in archives:
        for r in A.idx:
            d[r['hash']].add(LANG.get(r['spec'], '%08x' % r['spec']))
    return d


def scan(key, pat, nwords):
    A, e, pre = archive_of(key)
    E = '>' if e == 'be' else '<'
    names = load(L + ('Tomb Raider Underworld (PC).txt' if pre == 'pc-w' else 'Tomb Raider Underworld (Xenon).txt'))
    rx = re.compile(pat.encode(), re.I)
    seen, hits = set(), []
    for r in A.idx:
        if r['hash'] in seen: continue
        name = names.get(r['hash'], '')
        if name and not name.lower().endswith('.drm'): continue
        if r['size'] > 64 << 20: continue
        try:
            raw = A.read(r)
        except Exception:
            continue
        if raw[:4] in (b'CDRM', b'MRDC'):
            try: raw = cdrm_decode(raw, e)
            except Exception: continue
        if len(raw) < 24 or struct.unpack(E + 'i', raw[:4])[0] not in (19, 20, 21, 22): continue
        seen.add(r['hash'])
        if not rx.search(raw): continue
        try: h, secs = sections_with_data(raw, e)
        except Exception: continue
        for s in secs:
            if s['type'] in (2, 5, 6, 9, 12) or not s['data']: continue
            for m in re.finditer(rb'[\x20-\x7e]{4,}', s['data']):
                t = m.group()
                if not rx.search(t): continue
                o = m.start()
                n = min(nwords, len(s['data']) // 4)
                words = struct.unpack(E + '%dI' % n, s['data'][:4 * n]) if n else ()
                hits.append(dict(drm=name.split('\\')[-1] if name else '0x%08x' % r['hash'], stype=s['type'], sid=s['id'],
                                 off=o, size=s['size'], text=t.decode('latin1'), words=words))
    return hits, pre


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('--pat', default=r'vo\\[A-Za-z0-9_\\]+')
    ap.add_argument('--out')
    ap.add_argument('--words', type=int, default=0)
    ap.add_argument('--also', default='')
    a = ap.parse_args(argv)
    hits, pre = scan(a.src, a.pat, a.words)
    arcs = [archive_of(k)[0] for k in ([a.src] + [x for x in a.also.split(',') if x])]
    langs = spec_map(arcs, pre)
    lines = ['# tools/vo_refs_scan.py %s pat=%s; stream = %s\\audio\\streams\\<text>.mul' % (a.src, a.pat, pre),
             '# drm\tsec type\tsec id\tsec size\toff\ttext\tstream hash\tlanguages\t' + ('header words' if a.words else '')]
    missing = 0
    for h in hits:
        path = pre + '\\audio\\streams\\' + h['text'].strip('\\') + '.mul'
        hh = crc(path)
        lg = ','.join(sorted(langs.get(hh, ()))) or '-'
        if lg == '-': missing += 1
        lines.append('%s\t%d\t%d\t%d\t0x%x\t%s\t%08x\t%s\t%s' % (h['drm'], h['stype'], h['sid'], h['size'], h['off'], h['text'],
                                                           hh, lg, ' '.join('%08x' % w for w in h['words'])))
    lines.append('# hits %d, distinct texts %d, stream not found %d' % (len(hits), len({h['text'].lower() for h in hits}), missing))
    txt = '\n'.join(lines) + '\n'
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        open(a.out, 'w', encoding='utf8').write(txt)
        print(lines[-1], '->', a.out)
    else:
        sys.stdout.write(txt)


if __name__ == '__main__':
    main(sys.argv[1:])
