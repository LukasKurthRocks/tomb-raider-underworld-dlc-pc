"""Localised DLC voice streams (.mul) as language variants for the ModLoader - build, check and "what would the game
load" (2026-11-07, docs Befund-Tonspuren-Soeldner-0611.md A.4: the DLC 2 doppelganger lines
vo\\dlc2\\doppelganger\\i_dg_pdlc2_{mach_02, mach_07, mach_08, cere_02} have five language records in the Xbox pack11,
but every installed tree carries only the plain English file, so a German game plays them in English).

Why they were missing: the plain name comes from the DLC 2 audio route (dlc_audio_build: one file from the English
record); the language variants are written ONLY by tools/mul_lang_build.py, and that runs only inside step Repair
(tools/b138_fix_tree.py part 4 "language", --dlc2 -> pack11) into the B138 repair tree. The usual repair tree
work/rebuild/b138_fixes was last built before the four streams had names in work/generic/dlc_names.txt
(mul_lang_build.voice_names reads that list), the later Repair runs were check runs (-FixesOut) that are never installed,
and the audio test tree dlc_test51f_audio (tools/mul_reencode_tree.py) re-encodes only files that are already installed.
So no installed tree ever held i_dg_pdlc2_*.mul_NNN.

Format (the ModLoader, string "%s_%03d" in ModLoader.asi; tools/mul_lang_build.py): a language file is
<path>\\<name>.mul_NNN with NNN = 001 EN (Xbox spec 0xffffffe1), 002 FR (0xffffe002), 004 DE (0xffffe004),
008 IT (0xffffe008), 016 ES (0xffffe010); the plain <name>.mul is the fallback (English).

The conversion is the voice branch of tools/mul_lang_build.py, unchanged: music_convert.convert_mul(Xbox record)[0]
as the PC container, mul_audio_nch.swap(Xbox record, container) for the audio (default encoder 'game'); the plain name
is written from the English record too. Nothing here edits a DRM.

Modes (from the repository root):
  ../bin/pyt -t 600 tools/vo_lang_variants.py list PACK
        the localised voice streams of PACK (audio\\streams\\**.mul with >= 2 language records; names from
        work/generic/dlc_names.txt as mul_lang_build), with the Xbox header sample count per language
  ../bin/pyt -t 3600 tools/vo_lang_variants.py build OUT_MODS PACK [NAME_SUBSTRING ...]
        writes <rel>_NNN for every language record and <rel> (English) below OUT_MODS; vo_lang_md5.tsv and
        vo_lang_variants.log.txt go to the parent folder of OUT_MODS (nothing but streams lands in a mods tree)
  ../bin/pyt -t 600 tools/vo_lang_variants.py check TREE[,TREE..] PACK [--lang N] [--report R.json]
  ../bin/pyt -t 600 tools/vo_lang_variants.py check --profile PROFILE.json PACK [--base MODS] [--lang N] [--report R.json]
        read-only. TREE: mods folders, overlaid (a later folder wins); --profile: the trees of a test profile in
        install order (later wins, exclude lists honoured), --base: the files below them (e.g. the game's mods folder,
        read only). For every localised stream and every language N (or only --lang N): the file the game loads
        (<rel>_NNN if present, else <rel>), its size / md5 / header sample count, and the language(s) whose Xbox
        record header count lies within TOL samples of it (several when the Xbox records have (nearly) the same count,
        e.g. cere_02 / mach_08 FR = DE = IT = ES, DLC 1 radio lines EN / DE / IT 1 sample apart). --expect MD5.tsv (written by `build`): a variant must also have that md5.
        Verdicts: ok (variant present, its language among the nearest, md5 = expected when given), FALLBACK (no
        variant: the plain file plays), WRONG (variant present but another language / another md5), MISSING (no file).
        Exit 1 unless every stream / language is ok (the gate).
"""
import sys, os, struct, json, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import crc
from convert_dlc import R, PACKS
import mul_lang_build as MLB

LANG = MLB.LANG                                   # Xbox spec -> ModLoader language number
LNAME = {1: 'EN', 2: 'FR', 4: 'DE', 8: 'IT', 16: 'ES'}
SPEC = {n: s for s, n in LANG.items()}
TOL = 256                                         # header sample count tolerance (4 IMA blocks of 64 samples)


def archive(pack):
    p = [p for p in PACKS if p.endswith('/%s.000' % pack)]
    if not p: raise SystemExit('unknown pack %s (convert_dlc.PACKS)' % pack)
    return Archive(R + p[0], 'be')


def streams(pack, A=None):
    """[(full Xbox name, rel path with '/', {language number: archive record})] of the localised voice streams"""
    A = A or archive(pack)
    out = []
    for full in MLB.voice_names(pack):
        recs = {}
        for r in A.find(crc(full)):
            if r['spec'] in LANG: recs.setdefault(LANG[r['spec']], r)      # the index lists some records twice
        if len(recs) < 2: continue                                          # not localised (mul_lang_build rule)
        out.append((full, '/'.join(full.split('\\')[1:]), recs))
    return out


def xb_total(xd):
    return struct.unpack_from('>4I', xd, 0)[2]


def pc_head(pd):
    rate, w1, total, nch = struct.unpack_from('<4I', pd, 0)
    return rate, total, nch


def cmd_list(pack):
    A = archive(pack)
    ss = streams(pack, A)
    for full, rel, recs in ss:
        print('%s: %s' % (rel, '  '.join('%s %s total %d' % ('%03d' % n, LNAME[n], xb_total(A.read(recs[n])))
                                             for n in sorted(recs))))
    print('localised voice streams in %s: %d (%d language records)' % (pack, len(ss), sum(len(r) for _, _, r in ss)))
    return 0


def cmd_build(out, pack, pats):
    import music_convert as MC, mul_audio_nch as MN
    A = archive(pack)
    top = os.path.dirname(os.path.abspath(out))
    os.makedirs(out, exist_ok=True)
    log = open(os.path.join(top, 'vo_lang_variants.log.txt'), 'w', encoding='utf-8', newline='\r\n')
    rows = ['md5\tpath']
    n = 0
    for full, rel, recs in streams(pack, A):
        if pats and not any(p.lower() in rel.lower() for p in pats): continue
        for num in sorted(recs):
            xd = A.read(recs[num])
            pd = MC.convert_mul(xd)[0]
            o, info = MN.swap(xd, pd)
            targets = ['%s_%03d' % (rel, num)] + ([rel] if num == 1 else [])
            for t in targets:
                q = os.path.join(out, *t.split('/'))
                os.makedirs(os.path.dirname(q), exist_ok=True)
                open(q, 'wb').write(o)
                h = hashlib.md5(o).hexdigest()
                rate, total, nch = pc_head(o)
                line = '%-55s %9d bytes  md5 %s  %s spec %08x  Xbox total %d  PC total %d  channels %s  rate %s' % (
                    t, len(o), h, LNAME[num], SPEC[num], xb_total(xd), total, info.get('channels'), info.get('rate'))
                print(line, flush=True); log.write(line + '\n')
                rows.append('%s\t%s' % (h, t)); n += 1
    open(os.path.join(top, 'vo_lang_md5.tsv'), 'w', encoding='utf-8', newline='\n').write('\n'.join(rows) + '\n')
    log.write('files written %d\n' % n); log.close()
    print('files written', n)
    return 0


def overlay(dirs):
    """{rel lower: path}; later folder wins"""
    m = {}
    for d in dirs:
        for r, _, fs in os.walk(d):
            for f in fs:
                p = os.path.join(r, f)
                m[os.path.relpath(p, d).replace('\\', '/').lower()] = p
    return m


def profile_map(profile, base):
    import profile_last_source as PLS
    m = {}
    if base: m.update(overlay([base]))
    for rel, (path, src, k) in PLS.installed_map(profile).items(): m[rel] = path
    return m


def cmd_check(m, pack, langs, report, label, expect=None):
    A = archive(pack)
    tot = collections.Counter(); rows = []
    for full, rel, recs in streams(pack, A):
        xt = {num: xb_total(A.read(r)) for num, r in recs.items()}
        for num in (langs or sorted(recs)):
            if num not in recs: continue
            var = ('%s_%03d' % (rel, num)).lower()
            path = m.get(var) or m.get(rel.lower())
            if path is None:
                v = 'MISSING'; info = {}
            else:
                pd = open(path, 'rb').read()
                rate, total, nch = pc_head(pd)
                near = min(xt, key=lambda k: abs(xt[k] - total))
                # languages with the same Xbox sample count cannot be told apart by the header (e.g. cere_02 FR / DE /
                # IT / ES): then only --expect (md5 list of `build`) decides between them
                # the PC header count is the Xbox count rounded to the PC block layout (measured up to 124 samples off,
                # i_dg_pdlc2_mach_07 EN 299644 -> 299520): every language within TOL counts as a match
                tie = sorted(k for k in xt if abs(xt[k] - total) <= TOL or k == near)
                h = hashlib.md5(pd).hexdigest()
                want = expect.get(var) if expect else None
                if m.get(var) is None: v = 'FALLBACK'
                elif num not in tie: v = 'WRONG'
                elif want is not None and want != h: v = 'WRONG'
                else: v = 'ok'
                info = dict(file=path.replace('\\', '/'), size=len(pd), md5=h, total=total, channels=nch, rate=rate,
                            nearest='/'.join(LNAME[k] for k in tie), xbox_total_own=xt[num], xbox_total_nearest=xt[near],
                            md5_expected=want)
            tot[v] += 1
            rows.append(dict(stream=rel, lang=num, lang_name=LNAME[num], verdict=v, **info))
            print('%-50s %03d %s  %-9s %s' % (rel, num, LNAME[num], v, ('%s  %d bytes  md5 %s  total %d  nearest Xbox '
                  '%s (%d; own %d)' % (info['file'], info['size'], info['md5'], info['total'], info['nearest'],
                                       info['xbox_total_nearest'], info['xbox_total_own'])) if info else '-'))
    res = 'ok' if set(tot) <= {'ok'} and tot else 'fail'
    print('TOTAL %s %s' % (label, dict(tot)))
    print('check: %s' % res)
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        json.dump(dict(result=res, label=label, pack=pack, totals=dict(tot), rows=rows), open(report, 'w', encoding='utf-8'), indent=1)
    return 0 if res == 'ok' else 1


def opt(a, key):
    if key in a:
        k = a.index(key); v = a[k + 1]; del a[k:k + 2]; return v
    return None


def load_expect(path):
    """vo_lang_md5.tsv of `build` -> {rel lower: md5}"""
    if not path: return None
    out = {}
    for line in open(path, encoding='utf-8'):
        p = line.rstrip('\r\n').split('\t')
        if len(p) == 2 and p[0] != 'md5': out[p[1].lower()] = p[0]
    return out


def main(a):
    if not a: sys.exit(__doc__)
    report = opt(a, '--report'); lang = opt(a, '--lang'); profile = opt(a, '--profile'); base = opt(a, '--base')
    expect = load_expect(opt(a, '--expect'))
    langs = [int(lang)] if lang else None
    if a[0] == 'list' and len(a) == 2: return cmd_list(a[1])
    if a[0] == 'build' and len(a) >= 3: return cmd_build(a[1], a[2], a[3:])
    if a[0] == 'check' and profile and len(a) == 2:
        return cmd_check(profile_map(profile, base), a[1], langs, report, os.path.basename(profile), expect)
    if a[0] == 'check' and len(a) == 3:
        return cmd_check(overlay(a[1].split(',')), a[2], langs, report, a[1], expect)
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
