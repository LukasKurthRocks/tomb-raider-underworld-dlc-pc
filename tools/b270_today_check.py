"""What the upstream B270 kit changed against B138, and whether our trees of today carry it (read-only, 2026-11-07,
docs Befund-Datenfixes-0711.md section B270).

For every kit DRM that also exists in the B138 reference and differs from it (decompressed), the sections are paired by
(type, id). Per differing section of equal size every differing 32-bit word is listed with
  B138 bytes, B270 bytes, the bytes of each TODAY tree at the same place (same section type / id, same size), and the
  Xbox bytes of the same section id (DLC Xbox original, convert_dlc.raw_dlc with --pack first) when it has the same size;
  the byte class of B270 / B138 / today against the Xbox word (raw, u32, u16u16, u8u8u16, u16u8u8, halves; '-' = no
  byte order of it).
Sections of other size are summarised (sizes; today = B270 / = B138 / other); sections only in the kit are looked up in
each TODAY tree by (type, id) (same bytes / other bytes / missing).
Status per word and tree: =B270 (today carries his change), =B138 (not taken), other (a third value).

Usage (from the repository root):
  ../bin/pyt -t 3600 tools/b270_today_check.py KIT_MODS B138_MODS LABEL=DIR[,DIR..] [LABEL=DIR ...]
        [--names a.drm,streamgroups/b.drm] [--pack pack10] [--detail 12] [--tsv OUT.tsv]
  LABEL=DIR[,DIR..]  a today tree; several folders = overlay, the later folder wins (e.g. B138 snapshot + repair tree)
  --names            kit files to look at (default: every kit .drm that exists in B138 and differs from it)
  --detail N         word lines printed per section (default 12; the TSV always has every word)
  ../bin/pyt -t 300 tools/b270_today_check.py window FILE.drm TYPE ID OFF [N]
        N words (default 16) of one PC section around OFF, hex + ASCII (e.g. to read a changed string)
  ../bin/pyt -t 600 tools/b270_today_check.py locals KIT_MODS B138_MODS [TODAY_MODS]
        local/locals.bin_NNN: strings that differ kit / B138, each against the title-update string (line breaks)
"""
import sys, os, struct, collections, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_write as DW

PERMS = (('raw', (0, 1, 2, 3)), ('u32', (3, 2, 1, 0)), ('u16u16', (1, 0, 3, 2)), ('u8u8u16', (0, 1, 3, 2)),
         ('u16u8u8', (1, 0, 2, 3)), ('halves', (2, 3, 0, 1)))


def cls(xw, pw):
    if xw is None or pw is None: return ''
    c = [n for n, pm in PERMS if bytes(xw[i] for i in pm) == pw]
    return '/'.join(c) if c else '-'


def drm_files(root):
    out = {}
    for r, _, fs in os.walk(root):
        for f in fs:
            if f.lower().endswith('.drm'):
                p = os.path.join(r, f)
                out[os.path.relpath(p, root).replace(os.sep, '/').lower()] = p
    return out


def overlay(dirs):
    by = {}
    for d in dirs: by.update(drm_files(d))
    return by


def secmap(path, endian='le'):
    if path is None: return None
    D = DW.read(open(path, 'rb').read(), endian)
    m = {}
    for s in D.sections: m.setdefault((s.type, s.id), s)
    return m


_xcache = {}


def xbox_secs(rel, pack):
    if rel in _xcache: return _xcache[rel]
    import convert_dlc as CD
    saved = os.environ.get('TRUDLC_PACK_FIRST')
    raw = None
    try:
        if pack: os.environ['TRUDLC_PACK_FIRST'] = pack
        for n in (rel.replace('/', '\\'), os.path.basename(rel)):
            raw, pk = CD.raw_dlc(n)
            if raw is not None: break
    finally:
        if saved is None: os.environ.pop('TRUDLC_PACK_FIRST', None)
        else: os.environ['TRUDLC_PACK_FIRST'] = saved
    r = secmap_raw(raw) if raw is not None else None
    _xcache.clear(); _xcache[rel] = r
    return r


def secmap_raw(raw):
    D = DW.read(raw, 'be')
    m = {}
    for s in D.sections: m.setdefault((s.type, s.id), s)
    return m


def status(t, b138, b270):
    if t is None: return 'n/a'
    if t == b270: return '=B270'
    if t == b138: return '=B138'
    return 'other'


def window(a):
    """window FILE.drm TYPE ID OFF [N]: N words (default 16) around OFF of one PC section, hex + ASCII"""
    path, typ, sid, off = a[0], int(a[1]), int(a[2]), int(a[3], 0)
    n = int(a[4]) if len(a) > 4 else 16
    s = secmap(path).get((typ, sid))
    if s is None: sys.exit('section (%d, %d) not in %s' % (typ, sid, path))
    lo = max(0, (off - 4 * (n // 2)) // 4 * 4)
    for o in range(lo, min(len(s.data), lo + 4 * n), 4):
        w = bytes(s.data[o:o + 4])
        print('%s +0x%05x %s %s' % ('>' if o == off else ' ', o, w.hex(), ''.join(chr(c) if 32 <= c < 127 else '.' for c in w)))
    return 0


def locals_cmp(a):
    """locals KIT_MODS B138_MODS [TODAY_MODS]: per local/locals.bin_NNN the strings that differ between kit and B138,
    each with the title-update string of the same text (Xbox TU index via work/rebuild/stage1/locmap_xbox_to_pc.json,
    language by the header word) and which copy has the TU line breaks"""
    import json, locals as LC
    kit, b138 = a[0], a[1]; today = a[2] if len(a) > 2 else None
    lm = json.load(open(os.path.join(HERE, '..', 'work', 'rebuild', 'stage1', 'locmap_xbox_to_pc.json')))['map']
    inv = {}
    for x, p in lm.items(): inv.setdefault(int(p), int(x))
    tu, te = LC.files('tu')
    tu_by_lang = {}
    for spec, b in tu.items():
        lang, st, _ = LC.parse(b, te); tu_by_lang[lang] = st
    tot = collections.Counter()
    for f in sorted(os.listdir(os.path.join(kit, 'local'))):
        pk, pb = os.path.join(kit, 'local', f), os.path.join(b138, 'local', f)
        if not os.path.isfile(pb): continue
        lk, sk, _ = LC.parse(open(pk, 'rb').read(), 'le'); lb, sb, _ = LC.parse(open(pb, 'rb').read(), 'le')
        st_t = None
        if today and os.path.isfile(os.path.join(today, 'local', f)):
            st_t = LC.parse(open(os.path.join(today, 'local', f), 'rb').read(), 'le')[1]
        T = tu_by_lang.get(lk)
        for i in range(min(len(sk), len(sb))):
            if sk[i] == sb[i]: continue
            x = inv.get(i); tw = T[x] if (T is not None and x is not None and x < len(T)) else None
            same_text = lambda s: s is not None and s.replace(b'\n', b' ') == (tw or b'').replace(b'\n', b' ')
            verdict = 'TU string unknown' if tw is None else (
                'kit = TU' if sk[i] == tw else ('B138 = TU' if sb[i] == tw else
                                                ('same words, other breaks than both' if same_text(sk[i]) else 'other text')))
            tv = '' if st_t is None else (' today=%s' % ('kit' if i < len(st_t) and st_t[i] == sk[i] else
                                                         ('B138' if i < len(st_t) and st_t[i] == sb[i] else 'other')))
            tot[verdict] += 1
            print('%s lang %d string %d (TU %s): %s%s' % (f, lk, i, x, verdict, tv))
            for tag, s in (('kit ', sk[i]), ('B138', sb[i]), ('TU  ', tw)):
                if s is not None: print('    %s %r' % (tag, s.decode('utf-8', 'replace')[:300]))
    print('TOTAL', dict(tot))
    return 0


def basewords(a):
    """basewords NAME TYPE OFF N: base-game Xbox (tu / xbase2 / xbase) and genuine PC (pcpatch / pcbig) copies of NAME;
    for every section of TYPE (paired by order) the N words from OFF, Xbox / PC and their byte class"""
    import dtp_twin_field as TW
    name, typ, off, n = a[0], int(a[1]), int(a[2], 0), int(a[3])
    bx, sx = TW.load_named(name, ('tu', 'xbase2', 'xbase'), 'be')
    bp, sp = TW.load_named(name, ('pcpatch', 'pcbig'), 'le')
    if not bx or not bp: sys.exit('%s: Xbox %s, PC %s' % (name, sx, sp))
    xs = [s for s in bx if s['type'] == typ]; ps = [s for s in bp if s['type'] == typ]
    print('%s: Xbox %s %d sections of type %d, PC %s %d' % (name, sx, len(xs), typ, sp, len(ps)))
    for x, p in zip(xs, ps):
        xd, pd = bytes(x['data'] or b''), bytes(p['data'] or b'')
        ws = []
        for o in range(off, min(off + 4 * n, len(xd), len(pd)), 4):
            xw, pw = xd[o:o + 4], pd[o:o + 4]
            ws.append('+0x%x %s>%s %s' % (o, xw.hex(), pw.hex(), cls(xw, pw)))
        print('  Xbox %d / PC %d (%d / %d B): %s' % (x['id'], p['id'], len(xd), len(pd), '; '.join(ws)))
    return 0


def main(a):
    if a and a[0] == 'basewords': return basewords(a[1:])
    if a and a[0] == 'window': return window(a[1:])
    if a and a[0] == 'locals': return locals_cmp(a[1:])
    if len(a) < 3: sys.exit(__doc__)
    def opt(k, d=None):
        if k in a:
            i = a.index(k); v = a[i + 1]; del a[i:i + 2]; return v
        return d
    names = opt('--names'); pack = opt('--pack'); detail = int(opt('--detail', '12')); tsv = opt('--tsv')
    kit, b138 = a[0], a[1]
    trees = []
    for t in a[2:]:
        lab, dirs = t.split('=', 1)
        trees.append((lab, overlay(dirs.split(','))))
    K, B = drm_files(kit), drm_files(b138)
    if names: todo = [n.lower() for n in names.split(',')]
    else:
        todo = []
        for rel in sorted(K):
            if rel not in B: continue
            if DW.cdrm_decode(open(K[rel], 'rb').read(), 'le') != DW.cdrm_decode(open(B[rel], 'rb').read(), 'le'):
                todo.append(rel)
    labs = [l for l, _ in trees]
    rows = [['file', 'type', 'id', 'kind', 'offset', 'xbox', 'b138', 'b270', 'cls_b138', 'cls_b270'] +
            sum([[l, 'st_' + l, 'cls_' + l] for l in labs], [])]
    tot = collections.Counter()
    print('kit %s, B138 %s, today: %s; %d file(s)' % (kit, b138, ', '.join('%s (%d DRMs)' % (l, len(m)) for l, m in trees), len(todo)))
    for rel in todo:
        if rel not in K or rel not in B:
            print('=== %s: not in kit / B138' % rel); continue
        SK, SB = secmap(K[rel]), secmap(B[rel])
        ST = [(l, secmap(m.get(rel))) for l, m in trees]
        try: SX = xbox_secs(rel, pack)
        except Exception as e: SX = None; print('   (Xbox source: %s)' % e)
        print('=== %s  (Xbox original: %s; today: %s)' % (rel, 'yes' if SX else 'no',
                                                         ', '.join('%s %s' % (l, 'yes' if s else 'absent') for l, s in ST)))
        for key in sorted(SK):
            k = SK[key]; b = SB.get(key)
            if b is not None and (k.data, k.reloc) == (b.data, b.reloc): continue
            x = SX.get(key) if SX else None
            if b is None:
                st = []
                for l, s in ST:
                    t = s.get(key) if s else None
                    st.append('%s %s' % (l, 'missing' if t is None else ('same bytes' if (t.data == k.data) else 'other bytes (%d B)' % len(t.data))))
                    tot['newsec_' + l + '_' + ('missing' if t is None else ('same' if t.data == k.data else 'other'))] += 1
                print('  section (%d, %d) only in the kit (%d B): %s' % (key[0], key[1], len(k.data), '; '.join(st)))
                rows.append([rel, key[0], key[1], 'new section', '', '', '', '%d B' % len(k.data), '', ''] +
                            sum([[('-' if (s is None or s.get(key) is None) else ('same' if s.get(key).data == k.data else 'other')), '', ''] for l, s in ST], []))
                continue
            if len(k.data) != len(b.data) or k.data == b.data:
                vals = []
                for l, s in ST:
                    t = s.get(key) if s else None
                    v = 'absent' if t is None else ('=B270' if (t.data, t.reloc) == (k.data, k.reloc) else
                                                   ('=B138' if (t.data, t.reloc) == (b.data, b.reloc) else 'other (%d B)' % len(t.data)))
                    vals.append(v); tot['sizesec_' + l + '_' + v.split(' ')[0]] += 1
                print('  section (%d, %d) %d -> %d B (relocations %s): %s' % (key[0], key[1], len(b.data), len(k.data),
                      'equal' if k.reloc == b.reloc else 'differ', '; '.join('%s %s' % (l, v) for (l, _), v in zip(ST, vals))))
                rows.append([rel, key[0], key[1], 'size/reloc', '', '', '%d B' % len(b.data), '%d B' % len(k.data), '', ''] +
                            sum([['', v, ''] for v in vals], []))
                continue
            offs = [o for o in range(0, len(k.data) // 4 * 4, 4) if k.data[o:o + 4] != b.data[o:o + 4]]
            sec_ct = collections.Counter()
            lines = []
            xd = x.data if (x is not None and len(x.data) == len(k.data)) else None
            for o in offs:
                kw, bw = bytes(k.data[o:o + 4]), bytes(b.data[o:o + 4])
                xw = bytes(xd[o:o + 4]) if xd is not None else None
                row = [rel, key[0], key[1], 'word', '+0x%x' % o, xw.hex() if xw else '', bw.hex(), kw.hex(), cls(xw, bw), cls(xw, kw)]
                parts = []
                for l, s in ST:
                    t = s.get(key) if s else None
                    tw = bytes(t.data[o:o + 4]) if (t is not None and len(t.data) == len(k.data)) else None
                    sv = status(tw, bw, kw)
                    sec_ct[l + ' ' + sv] += 1; tot['word_' + l + '_' + sv] += 1
                    row += [tw.hex() if tw else '', sv, cls(xw, tw)]
                    parts.append('%s %s %s' % (l, tw.hex() if tw else '-', sv))
                rows.append(row)
                lines.append('    +0x%05x Xbox %s  B138 %s (%s)  B270 %s (%s)  | %s' % (
                    o, xw.hex() if xw else '--------', bw.hex(), cls(xw, bw) or '?', kw.hex(), cls(xw, kw) or '?', '; '.join(parts)))
            relnote = '' if k.reloc == b.reloc else ', relocations differ'
            print('  section (%d, %d) %d B: %d word(s) differ%s; Xbox %s; %s' % (
                key[0], key[1], len(k.data), len(offs), relnote,
                'same size' if xd is not None else ('absent' if x is None else 'other size'),
                ', '.join('%s %d' % kv for kv in sorted(sec_ct.items()))))
            for ln in lines[:detail]: print(ln)
            if len(lines) > detail: print('    ... %d more word(s) in the TSV' % (len(lines) - detail))
    print('TOTAL', dict(sorted(tot.items())))
    if tsv:
        os.makedirs(os.path.dirname(os.path.abspath(tsv)), exist_ok=True)
        with open(tsv, 'w', encoding='utf-8', newline='\n') as f:
            for r in rows: f.write('\t'.join(str(c) for c in r) + '\n')
        print('wrote %s (%d rows) md5 %s' % (tsv, len(rows) - 1, hashlib.md5(open(tsv, 'rb').read()).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
