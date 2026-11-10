"""Voice catalogue of TR Underworld (read-only): every speech stream of a game archive with its language variants,
speaker (where the data says it), English line text (subtitle tails inside the stream) and the DRMs / sections that
name it. Draft input for a TruMenu voice player list (TruMenu.voice.txt) and for subtitle colours per speaker.

Speech streams = cinstream\\*.mul (one stream per cutscene; animation + sound + subtitle tails) and
audio\\streams\\vo\\**\\*.mul (one stream per line). Language variants from the archive index (spec words, see
tools/lang_spec_census.py). Line text: the {u32 len, text} tail of every cine block (tools/cine_mul_info.py), record
'<id>\\r<text>\\r...', id 0 = English. Speaker:
  * the "<Speaker>: " prefix that the subtitle reader 0x4538d0 strips (0x4539e0..0x453a0b) - counted per stream;
  * otherwise only the path: vo\\lara -> Lara, vo\\dlc1\\lara / zip -> Lara / Zip, vo\\dlc2\\doppelganger ->
    doppelganger, vo\\enemy\\merc\\b_mNN -> mercenary voice NN, vo\\kraken -> kraken; a cinematic has several speakers
    and no per-line speaker field (left "-").
References: every printable string in the type-0 / 7 / 8 / 11 sections of the DRMs whose name matches --drm that
equals a stream path (vo\\... without root and extension, the dialogue DTP form) or a cinematic base name.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/voice_catalog.py SRC [--vo REGEX] [--cine REGEX] [--drm REGEX] [--out TSV] [--speakers]
      SRC      archive key of tools/locals.SRC (pcbig, pack10, pack11 ...)
      --vo     only vo streams whose path matches REGEX (default: none; 'vo' = all)
      --cine   only cinematics whose name matches REGEX (default: none; '.' = all)
      --drm    scan the DRMs whose name matches REGEX for references (default: none)
      --out    write the catalogue as TSV (kind, stream, languages, speaker, prefix speakers, lines, first EN line,
               referenced by); default: print a summary only
      --md     write a German markdown table, one row per English line (stream, unit, DRM sections, speaker,
               languages, time in the stream, text); a stream without subtitles gets one row
      --speakers  print every subtitle entry that has a "<name>: " prefix (any language)
      --dump REGEX  print the first subtitle records of the chosen streams whose path matches REGEX
Reads each chosen stream's English (or neutral) record once, by index + seek; nothing large stays in memory.
"""
import sys, os, re, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import load, L
from drm import cdrm_decode, sections_with_data
import cine_mul_info as CMI

SPEC = {0xffffffe1: 'en', 0xffffe002: 'fr', 0xffffe004: 'de', 0xffffe008: 'it', 0xffffe010: 'es', 0xffffffff: 'all'}
PREFIX = re.compile(r'^\s*([^:\r\n]{1,24}):\s+\S')       # what 0x4539e0.. strips: text up to the first ':' + space


def arg(argv, key):
    if key in argv:
        i = argv.index(key); v = argv[i + 1]; del argv[i:i + 2]; return v
    return None


def speaker_of(path):
    p = path.lower()
    if '\\vo\\dlc1\\lara\\' in p: return 'Lara (DLC 1)'
    if '\\vo\\dlc1\\zip\\' in p: return 'Zip (DLC 1, radio)'
    if '\\vo\\dlc2\\doppelganger\\' in p: return 'Doppelganger (DLC 2)'
    if '\\vo\\lara\\' in p: return 'Lara'
    m = re.search(r'\\vo\\enemy\\merc\\b_m(\d+)_', p)
    if m: return 'mercenary voice m%s' % m.group(1)
    if '\\vo\\kraken\\' in p: return 'kraken'
    if '\\cinstream\\' in p: return '-'
    return '?'


def entries(text):
    """[(id, text)] of one subtitle record '<id>\\r<text>\\r...'"""
    out = []
    parts = text.split('\r')
    for i in range(0, len(parts) - 1, 2):
        # the vo line blocks carry an outer {u32 size, u32 0} before the {u32 len, text} tail, and
        # cine_mul_info.subtitle can match the outer size first: keep only the digits at the end of the id part
        m = re.search(r'(\d{1,2})$', parts[i].strip())
        if m: out.append((int(m.group(1)), parts[i + 1].strip('"')))
    return out


def stream_lines(A, r, E):
    d = A.read(r)
    try:
        B, _ = CMI.blocks(d, E)
    except Exception:
        return None, []
    C = [b[3] for b in B if b[0] == 1]
    scene = C[0][0xc:0x4c].split(b'\0')[0].decode('latin1', 'replace') if C else ''
    lines, last = [], None
    for i, p in enumerate(C):
        s = CMI.subtitle(p, E)
        if s and s != last:
            lines.append((i, entries(s))); last = s
    return scene, lines


def refs_scan(A, names, E, e, drm_rx, wanted):
    """{lower stream key: set of 'drm:type:id'} for strings equal to a wanted key"""
    out = collections.defaultdict(set)
    for r in A.idx:
        n = names.get(r['hash'], '')
        if not n.lower().endswith('.drm') or not drm_rx.search(n.split('\\')[-1]): continue
        try:
            raw = A.read(r)
            if raw[:4] in (b'CDRM', b'MRDC'): raw = cdrm_decode(raw, e)
            h, secs = sections_with_data(raw, e)
        except Exception:
            continue
        for s in secs:
            if s['type'] not in (0, 7, 8, 11) or not s['data']: continue
            for m in re.finditer(rb'[\x20-\x7e]{6,}', s['data']):
                k = m.group().decode('latin1').lower().strip('\\')
                if k in wanted: out[k].add('%s:%d:%d' % (n.split('\\')[-1][:-4], s['type'], s['id']))
    return out


def main(argv):
    argv = list(argv)
    vo = arg(argv, '--vo'); cine = arg(argv, '--cine'); drm = arg(argv, '--drm'); outp = arg(argv, '--out')
    mdp = arg(argv, '--md')
    show = '--speakers' in argv; argv = [a for a in argv if a != '--speakers']
    dump = arg(argv, '--dump'); dump = re.compile(dump, re.I) if dump else None
    if not argv: sys.exit(__doc__)
    import locals as LC
    path, e, pre = LC.SRC[argv[0]]
    E = '>' if e == 'be' else '<'
    names = load(L + ('Tomb Raider Underworld (PC).txt' if pre == 'pc-w' else 'Tomb Raider Underworld (Xenon).txt'))
    A = Archive(path, e)
    by = collections.defaultdict(list)
    for r in A.idx:
        n = names.get(r['hash'])
        if n and n.lower().endswith('.mul') and ('\\cinstream\\' in n.lower() or '\\audio\\streams\\vo\\' in n.lower()):
            by[n].append(r)
    vrx = re.compile(vo, re.I) if vo else None
    crx = re.compile(cine, re.I) if cine else None
    rows, pref_total, pref_hits, nlines = [], 0, 0, 0
    pref_names = collections.Counter()
    for n in sorted(by):
        nl = n.lower(); kind = 'cine' if '\\cinstream\\' in nl else 'vo'
        if kind == 'cine' and not (crx and crx.search(n.split('\\')[-1])): continue
        if kind == 'vo' and not (vrx and vrx.search(n)): continue
        recs = by[n]
        langs = sorted({SPEC.get(r['spec'], '%08x' % r['spec']) for r in recs})
        r = ([x for x in recs if x['spec'] == 0xffffffe1] or [x for x in recs if x['spec'] == 0xffffffff] or recs)[0]
        scene, lines = stream_lines(A, r, E)
        pre_sp = collections.Counter()
        for fr, ent in lines:
            for i, t in ent:
                pref_total += 1
                m = PREFIX.match(t)
                if m:
                    pref_hits += 1; pre_sp[m.group(1)] += 1; pref_names[m.group(1)] += 1
                    if show: print('  prefix %-40s frame %5d id %2d  %s' % (n.split('\\')[-1], fr, i, t[:90]))
        if dump and dump.search(n):
            print('  %s spec %08x scene "%s": %d subtitle record(s)' % (n, r['spec'], scene, len(lines)))
            for fr, ent in lines[:4]: print('    frame %5d  %s' % (fr, ' | '.join('%d=%s' % (i, t[:60]) for i, t in ent)))
            d = A.read(r)
            for b in CMI.blocks(d, E)[0]:
                if b[0] != 1: continue
                k = b[3].find(b'\r')
                if k >= 0: print('    raw cine block bytes around the first CR: %r' % b[3][max(0, k - 120):k + 40]); break
        en = [t for fr, ent in lines for i, t in ent if i == 0]
        nlines += len(en)
        key = (nl.split('\\audio\\streams\\', 1)[1][:-4] if kind == 'vo' else nl.split('\\')[-1][:-4])
        rows.append(dict(kind=kind, name=n, key=key, langs=langs, speaker=speaker_of(n), scene=scene,
                         prefix=dict(pre_sp), lines=len(en), first=(en[0] if en else ''), refs=set(), en=en,
                         enf=lines))
    if drm:
        refs = refs_scan(A, names, E, e, re.compile(drm, re.I), {x['key'] for x in rows})
        for x in rows: x['refs'] = refs.get(x['key'], set())
    print('%s: %d speech streams chosen (%d cine, %d vo); English subtitle lines %d; subtitle entries (all languages) %d, '
          'with a "<name>: " prefix %d %s' % (argv[0], len(rows), sum(x['kind'] == 'cine' for x in rows),
                                               sum(x['kind'] == 'vo' for x in rows), nlines, pref_total, pref_hits,
                                               dict(pref_names.most_common(12))))
    if drm:
        print('referenced in DRMs matching %r: %d of %d streams' % (drm, sum(1 for x in rows if x['refs']), len(rows)))
    if outp:
        with open(outp, 'w', encoding='utf-8', newline='\n') as f:
            f.write('# tools/voice_catalog.py %s (read-only catalogue; English = subtitle id 0)\n' % ' '.join(sys.argv[1:]))
            f.write('# kind\tstream\tlanguages\tspeaker\tscene\tprefix speakers\tEN lines\tfirst EN line\treferenced by\n')
            for x in rows:
                f.write('\t'.join([x['kind'], x['key'], ','.join(x['langs']), x['speaker'], x['scene'],
                                   ','.join('%s=%d' % kv for kv in sorted(x['prefix'].items())) or '-', str(x['lines']),
                                   x['first'].replace('\t', ' ').replace('\n', ' / ')[:160] or '-',
                                   ' '.join(sorted(x['refs'])) or '-']) + '\n')
        print('written %s (%d rows)' % (outp, len(rows)))
    if mdp:
        with open(mdp, 'w', encoding='utf-8', newline='\n') as f:
            f.write('<!-- generated by tools/voice_catalog.py %s; English = subtitle id 0; read-only catalogue -->\n\n'
                    % ' '.join(sys.argv[1:]))
            f.write('| # | Art | Strom / Szene | Einheit (Szene) | genannt in (DRM:Typ:Id) | Sprecher | Sprachen | Zeit | Text (EN) |\n')
            f.write('|---|---|---|---|---|---|---|---|---|\n')
            k = 0
            for x in rows:
                frames = [(fr, t) for fr, ent in x['enf'] for i, t in ent if i == 0] or [(None, '')]
                for fr, t in frames:
                    k += 1
                    f.write('| %d | %s | `%s` | %s | %s | %s | %s | %s | %s |\n' % (
                        k, x['kind'], x['key'], x['scene'] or '-', ' '.join(sorted(x['refs'])) or '-', x['speaker'],
                        ' '.join(x['langs']), '-' if fr is None else '%.1f s' % (fr / 30.0),
                        (t.replace('|', '/').replace('\n', ' / ') or '(kein Untertitel)')))
        print('written %s' % mdp)


if __name__ == '__main__':
    main(sys.argv[1:])
