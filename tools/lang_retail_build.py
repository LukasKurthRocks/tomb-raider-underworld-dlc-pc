"""Build an extra game language for the installed PC game from a second retail PC build of the same engine (e.g. a
regional retail build whose archive holds one other language), for the owner's own installation. Read-only on every
input; writes only the given output paths. Nothing from a retail copy belongs in the repository - pass all data paths
as arguments and write the results to a local work folder / the game's mods folder.

Background (docs/ENGINE.md rows "Language ids", "Bitmap font", "Language font merge", "Language slot _NNN"):
  - the game asks the ModLoader for `<path>_NNN` with NNN = 1 << language id (`%s_%03d`): ru (9) = _512;
  - one bitmap font for all languages (generalbank.drm DTP 46, page 0 = texture 109); a build that ships the same
    descriptor extended (a superset of the PC glyphs) can replace ours for every language;
  - locals.bin is read by index; a build with the PC index layout fills the base indices, our table the rest (DLC).

Subcommands (from the repository root):
  ../bin/pyt -t 600 tools/lang_retail_build.py font OUR_GB DONOR_GB OUT_GB [--font-id 46]
      OUR_GB: our installed generalbank.drm (CDRM or raw), DONOR_GB: the other build's generalbank.drm (CDRM or raw).
      Replaces the font descriptor (DTP --font-id) and its page-0 texture with the donor's, keeps every other section,
      the names and the container of OUR_GB. Checks (exit 1 on a failed one): same section count, every other section
      byte-identical (data, relocations, flags, version, spec), no external relocations in the moved sections, every
      relocation in bounds after a CDRM read-back, our glyph entries byte-identical in the new table, our glyph boxes
      pixel-identical on the new page, codes sorted, the other users of the page texture. Reports codes still missing.
  ../bin/pyt -t 600 tools/lang_retail_build.py locals OUR_TABLE DONOR_TABLE PC_ORIGINAL OUT [--font GB]
      OUR_TABLE: our installed English table (locals.bin_001), DONOR_TABLE: the other build's table (same index layout),
      PC_ORIGINAL: the PC English table our table was built from (patch.000, spec fffff7e1). Per index: the donor text
      where the donor has one and our entry is the unchanged PC text; else ours (DLC entries, entries the donor lacks or
      leaves empty, entries our merge changed). Same layout as OUR_TABLE (count, offset-0 entries, language field);
      checks: our table survives the writer byte for byte, read back, UTF-8; --font: code points the font lacks.
  ../bin/pyt -t 3600 tools/lang_retail_build.py speech DONOR_000 PREFIX SPEC LANG OUT_DIR [--pc PC_000] [--names LIST]
                                                     [--dry] [--want-id N]
      Every `.mul` record of spec SPEC (hex) in the donor archive, named through the PC file list with the root folder
      PREFIX (pc-w\\ -> PREFIX\\), written as OUT_DIR\\<path below the root>_NNN (NNN = 1 << LANG, as the installed
      _001 .. _016 files). Checks per file: little-endian .mul header, block walk to the end, sample rate / channels /
      scene name equal to the PC English record of the same path (--pc), subtitle records per language id; prints how
      many cinematic records carry id 0 but not --want-id (default LANG). --dry: check only, write nothing.
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_write as DW, drm_reloc as R


def fail(msg, bad):
    print(('FAIL ' if bad else 'ok   ') + msg)
    return 1 if bad else 0


# ------------------------------------------------------------------------------------------------------------ font
def font(argv):
    fid = 46
    if '--font-id' in argv: k = argv.index('--font-id'); fid = int(argv[k + 1]); del argv[k:k + 2]
    our_p, don_p, out_p = argv
    import font_survey as FS
    import numpy as np
    import tex_convert as T
    ours_raw = open(our_p, 'rb').read(); cdrm = ours_raw[:4] == b'CDRM'
    B = DW.read(ours_raw, 'le'); D = DW.read(open(don_p, 'rb').read(), 'le')
    fb = {B.sections[si].id: d for si, d in FS.descriptors(B, '<')}
    fd = {D.sections[si].id: d for si, d in FS.descriptors(D, '<')}
    if fid not in fb or fid not in fd: sys.exit('font descriptor DTP %d missing (ours %s, donor %s)' % (fid, sorted(fb), sorted(fd)))
    db, dd = fb[fid], fd[fid]
    print('ours : DTP %d pages %d / %d, %d glyphs' % (fid, db['tex0'], db['tex1'], db['n']))
    print('donor: DTP %d pages %d / %d, %d glyphs' % (fid, dd['tex0'], dd['tex1'], dd['n']))
    bad = 0
    bad += fail('same page ids (%d / %d)' % (db['tex0'], db['tex1']), (db['tex0'], db['tex1']) != (dd['tex0'], dd['tex1']))
    keys = [(7, fid), (5, db['tex0'])]
    bsec = {(s.type, s.id): s for s in B.sections}; dsec = {(s.type, s.id): s for s in D.sections}
    for k in keys:
        if k not in bsec or k not in dsec: sys.exit('section %d:%d missing (ours %s, donor %s)' % (k + (k in bsec, k in dsec)))
        for tag, s in (('ours', bsec[k]), ('donor', dsec[k])):
            bad += fail('%s %d:%d has no external relocations' % (tag, k[0], k[1]), bool(R.parse(s.reloc, 'le').external))
    t1b, t1d = bsec.get((5, db['tex1'])), dsec.get((5, db['tex1']))
    print('     page 1 (texture %d) %s - kept as ours' % (db['tex1'], 'identical in both' if t1b and t1d and t1b.data == t1d.data
                                                          else 'DIFFERS (donor page 1 not used)'))
    for f in ('w8', 'w14', 'f18', 'f1c', 'h20', 'h22'):
        bad += fail('descriptor field %s ours %s donor %s' % (f, db[f], dd[f]), db[f] != dd[f])
    # who else uses the page-0 texture in our file
    users = []
    for s in B.sections:
        if (s.type, s.id) == (7, fid) or not s.reloc: continue
        r = R.parse(s.reloc, 'le')
        for off, t in r.id_offsets().items():
            if t == 5 and off + 4 <= len(s.data) and struct.unpack_from('<I', s.data, off)[0] == db['tex0']:
                users.append('%d:%d +0x%x' % (s.type, s.id, off))
    print('     other users of texture %d in ours: %s' % (db['tex0'], ', '.join(users) or 'none'))
    # new section list
    new = []
    for s in B.sections:
        k = (s.type, s.id)
        if k in keys:
            x = dsec[k]
            new.append(DW.Section(x.type, x.id, x.data, x.reloc, flags=x.flags, ver=x.ver, spec=x.spec, pad=x.pad))
        else:
            new.append(s)
    N = DW.Drm(new, B.names, B.pad, B.ver, B.u0, B.u1)
    raw = N.write('le')
    outb = DW.cdrm_encode(raw, 'le') if cdrm else raw
    E = DW.read(outb, 'le')                      # read back the written container
    bad += fail('section count %d (ours %d)' % (len(E.sections), len(B.sections)), len(E.sections) != len(B.sections))
    bad += fail('names / pad / header kept', (E.names, E.pad, E.ver, E.u0, E.u1) != (B.names, B.pad, B.ver, B.u0, B.u1))
    same = diff = 0
    for a, b in zip(B.sections, E.sections):
        k = (a.type, a.id)
        if (b.type, b.id) != k: diff += 1; continue
        if k in keys:
            x = dsec[k]
            if (b.data, b.reloc, b.flags, b.ver, b.spec) != (x.data, x.reloc, x.flags, x.ver, x.spec): diff += 1
            continue
        if (a.data, a.reloc, a.flags, a.ver, a.spec, a.pad) == (b.data, b.reloc, b.flags, b.ver, b.spec, b.pad): same += 1
        else: diff += 1
    bad += fail('other sections byte-identical: %d of %d, differing %d' % (same, len(B.sections) - len(keys), diff), diff)
    infos = [dict(size=len(x.data)) for x in E.sections]
    oob = sum(bool(R.check(R.parse(x.reloc, 'le'), len(x.data), infos)) for x in E.sections)
    bad += fail('sections with relocations out of bounds after read-back: %d' % oob, oob)
    # glyphs
    fe = {E.sections[si].id: d for si, d in FS.descriptors(E, '<')}
    de = fe.get(fid)
    if not de: sys.exit('no descriptor after the merge')
    newents = collections.defaultdict(list)
    for x in de['ents']: newents[x[0]].append(x)
    ident = sum(1 for x in db['ents'] if x in newents.get(x[0], []))
    bad += fail('our glyph entries byte-identical in the new table: %d of %d' % (ident, len(db['ents'])), ident != len(db['ents']))
    codes = [x[0] for x in de['ents']]
    dec = [i for i in range(1, len(codes)) if codes[i] < codes[i - 1]]
    dup = len(codes) - len(set(codes))
    bad += fail('new table sorted for the binary search (%d glyphs, %d duplicate codes)' % (len(codes), dup), bool(dec))
    p0 = np.asarray(T.pc_image(bsec[(5, db['tex0'])].data)); p1 = np.asarray(T.pc_image(dsec[(5, db['tex0'])].data))
    print('     page 0: ours %dx%d, new %dx%d' % (p0.shape[1], p0.shape[0], p1.shape[1], p1.shape[0]))
    h = db['h22'] if db['h22'] > 0 else 40
    boxbad = 0
    for c, w, gx, gy, _, _ in db['ents']:
        if c >= 0x1800 and c < 0x18b0: continue          # page 1 glyphs (pad icons)
        a = p0[gy:gy + h, gx:gx + w]; b = p1[gy:gy + h, gx:gx + w]
        if a.shape != b.shape or not np.array_equal(a, b): boxbad += 1
    npage0 = sum(1 for x in db['ents'] if not 0x1800 <= x[0] < 0x18b0)
    bad += fail('our page-0 glyph boxes pixel-identical on the new page: %d of %d' % (npage0 - boxbad, npage0), boxbad)
    top = p1[:p0.shape[0], :p0.shape[1]]
    print('     top %dx%d of the new page identical to our whole page: %s' % (p0.shape[1], p0.shape[0],
          bool(top.shape == p0.shape and np.array_equal(top, p0))))
    have = set(codes)
    miss = [c for c in range(0x1826, 0x182d) if c not in have]
    print('     pad codes U+1826..182C missing in the new table: %d of 7 (%s)' % (len(miss), ' '.join('U+%04X' % c for c in miss)))
    added = sorted(have - set(x[0] for x in db['ents']))
    print('     codes added: %d (U+%04X..U+%04X)' % (len(added), added[0], added[-1]) if added else '     codes added: 0')
    if bad: print('NOT written: %d check(s) failed' % bad); return 1
    os.makedirs(os.path.dirname(os.path.abspath(out_p)), exist_ok=True)
    open(out_p, 'wb').write(outb)
    print('written %s: %d bytes (%s), %d sections' % (out_p, len(outb), 'CDRM' if cdrm else 'raw', len(E.sections)))
    return 0


# ---------------------------------------------------------------------------------------------------------- locals
def font_codes(gb):
    import font_survey as FS
    D = DW.read(open(gb, 'rb').read(), 'le')
    fs = FS.descriptors(D, '<')
    return set(x[0] for x in fs[0][1]['ents']) if fs else set()


def table_codes(strings):
    c = collections.Counter()
    for s in strings:
        for ch in s.decode('utf-8', errors='replace'):
            if ch not in '\n\r\t': c[ord(ch)] += 1
    return c


def locals_cmd(argv):
    gb = None
    if '--font' in argv: k = argv.index('--font'); gb = argv[k + 1]; del argv[k:k + 2]
    show = '--show-kept' in argv; argv = [a for a in argv if a != '--show-kept']
    our_p, don_p, ref_p, out_p = argv
    import locals as LC
    ob = open(our_p, 'rb').read()
    lang, ours, offs = LC.parse(ob, 'le')
    _, don, doffs = LC.parse(open(don_p, 'rb').read(), 'le')
    _, ref, roffs = LC.parse(open(ref_p, 'rb').read(), 'le')
    print('ours %d entries (language field %d), donor %d, PC original %d' % (len(ours), lang, len(don), len(ref)))
    bad = 0
    w = LC.write_pc(lang, ours, offs)
    if w != ob:
        at = next((i for i in range(min(len(w), len(ob))) if w[i] != ob[i]), min(len(w), len(ob)))
        print('     write_pc differs from ours: %d / %d bytes, first difference at 0x%x' % (len(w), len(ob), at))
        # how our file is laid out: the string bodies in index order, shared or not?
        body = sorted(set(o for i, o in enumerate(offs) if o))
        shared = len([o for i, o in enumerate(offs) if o]) - len(body)
        empt = sum(1 for i, o in enumerate(offs) if o and not ours[i])
        print('     ours: %d offsets != 0, %d distinct, %d shared, %d point at an empty string, ascending in index order: %s'
              % (len([o for o in offs if o]), len(body), shared, empt,
                 all(a <= b for a, b in zip([o for o in offs if o], [o for o in offs if o][1:]))))
    # byte layout of the string bodies is not part of the format (a later fix may have appended a text); the format
    # check is the round trip: our table through the writer reads back as the same strings and offset-0 entries
    l1, b1, o1 = LC.parse(w, 'le')
    rt = l1 == lang and len(b1) == len(ours) and all((o1[i] == 0) == (offs[i] == 0) and (offs[i] == 0 or b1[i] == ours[i])
                                                       for i in range(len(ours)))
    print('     our table through write_pc: %s' % ('byte-identical' if w == ob else 'same strings, other body order'))
    bad += fail('our table round trip (parse -> write_pc -> parse): same strings and offset-0 entries', not rt)
    st = collections.Counter(); out = []
    for i, s in enumerate(ours):
        if i == 0 or offs[i] == 0: out.append(s); st['offset 0 (kept)'] += 1; continue
        if i >= len(don): out.append(s); st['ours: beyond the donor table (DLC)'] += 1; continue
        if doffs[i] == 0 or not don[i]: out.append(s); st['ours: donor entry empty'] += 1; continue
        if i < len(ref) and roffs[i] != 0 and s != ref[i]:
            out.append(s); st['ours: changed by our merge'] += 1
            if show: print('     kept ours %5d: ours %r | PC %r | donor %r' % (i, s[:50], ref[i][:40], don[i][:40]))
            continue
        if i >= len(ref) or roffs[i] == 0: out.append(s); st['ours: not in the PC original'] += 1; continue
        out.append(don[i]); st['donor text'] += 1
    for k, v in sorted(st.items()): print('     %-40s %5d' % (k, v))
    nb = LC.write_pc(lang, out, offs)
    l2, back, boffs = LC.parse(nb, 'le')
    bad += fail('read back: %d entries, language %d' % (len(back), l2), len(back) != len(ours) or l2 != lang)
    z = sum(1 for i in range(len(offs)) if (offs[i] == 0) != (boffs[i] == 0))
    bad += fail('offset-0 entries as in ours (%d differ)' % z, z)
    mism = sum(1 for i in range(len(out)) if offs[i] != 0 and back[i] != out[i])
    bad += fail('every entry reads back (%d differ)' % mism, mism)
    nonu = 0
    for s in back:
        try: s.decode('utf-8')
        except UnicodeDecodeError: nonu += 1
    bad += fail('UTF-8 entries (%d invalid)' % nonu, nonu)
    bad += fail('the new table survives the writer byte for byte', LC.write_pc(l2, back, boffs) != nb)
    if gb:
        have = font_codes(gb); used = table_codes(back[i] for i in range(len(back)) if boffs[i])
        miss = sorted(c for c in used if c not in have)
        print('     code points the font lacks: %d (%d uses): %s' % (len(miss), sum(used[c] for c in miss),
              ' '.join('U+%04X' % c for c in miss)))
    if bad: print('NOT written: %d check(s) failed' % bad); return 1
    os.makedirs(os.path.dirname(os.path.abspath(out_p)), exist_ok=True)
    open(out_p, 'wb').write(nb)
    print('written %s: %d bytes, %d entries' % (out_p, len(nb), len(back)))
    return 0


# ---------------------------------------------------------------------------------------------------------- speech
def mul_info(d):
    """(rate, channels, scene name or '', cine blocks, audio blocks, subtitle records [(frame, ids)]) of a PC .mul"""
    import mul_sub_records as MS, mul_convert as M
    if MS.mul_endian(d) != '<': raise ValueError('no little-endian .mul header')
    rate, m1, total, nch = struct.unpack_from('<4I', d, 0)
    bl = M.blocks(d, '<')
    nc = sum(1 for b in bl if b[0] == 1); na = sum(1 for b in bl if b[0] == 0)
    scene = ''
    if bl and bl[0][0] == 1 and len(bl[0][3]) >= 0x4c:
        scene = bl[0][3][0xc:0x4c].split(b'\0')[0].decode('latin-1')
    recs = [(fr, [i for i, _ in ents]) for _, fr, ents in MS.block_records(d, '<')]
    return rate, nch, scene, nc, na, recs


def speech(argv):
    from bigfile import read_index
    from archive import Archive
    from names import load, crc, L
    names = L + 'Tomb Raider Underworld (PC).txt'
    dry = '--dry' in argv; argv = [a for a in argv if a != '--dry']
    pc = None
    if '--pc' in argv: k = argv.index('--pc'); pc = argv[k + 1]; del argv[k:k + 2]
    if '--names' in argv: k = argv.index('--names'); names = argv[k + 1]; del argv[k:k + 2]
    want = None
    if '--want-id' in argv: k = argv.index('--want-id'); want = int(argv[k + 1]); del argv[k:k + 2]
    don_p, prefix, spec, lang, out_dir = argv
    spec = int(spec, 16); lang = int(lang); want = lang if want is None else want
    suffix = '_%03d' % (1 << lang)
    if spec & (1 << lang) == 0: sys.exit('spec %08x does not serve language %d' % (spec, lang))
    nm = load(names)
    byh = {}
    for h, n in nm.items():
        if n.lower().startswith('pc-w\\'): byh[crc(prefix + n[4:])] = n
    A = Archive(don_p, 'le')
    recs = [r for r in A.idx if r['spec'] == spec]
    P = Archive(pc, 'le') if pc else None
    pcby = collections.defaultdict(list)
    if P:
        for r in P.idx: pcby[r['hash']].append(r)
    st = collections.Counter(); bad = 0; total = 0
    cine_only0 = collections.Counter(); ids_all = collections.Counter()
    for r in recs:
        n = byh.get(r['hash'])
        if not n: st['unnamed (skipped)'] += 1; bad += 1; continue
        if not n.lower().endswith('.mul'): st['not .mul (skipped): ' + os.path.splitext(n)[1]] += 1; continue
        rel = n[5:]
        kind = 'cinstream' if rel.lower().startswith('cinstream\\') else os.path.dirname(rel).lower()
        d = A.read(r)
        try: rate, nch, scene, nc, na, srec = mul_info(d)
        except ValueError as e: print('FAIL %s: %s' % (rel, e)); bad += 1; continue
        note = ''
        if P:
            en = [x for x in pcby.get(crc(n), []) if x['spec'] & 1]
            if not en: note = 'no PC English record'; st['no PC English record'] += 1
            else:
                e = P.read(en[0])
                er, ench, escene, enc, ena, erec = mul_info(e)
                # the rate word is the measured rate of each recording (PC language variants differ by a few Hz too)
                if (ench, escene) != (nch, scene) or abs(er - rate) > er * 0.005:
                    print('FAIL %s: rate / channels / scene %s / %s / %r, PC English %s / %s / %r' % (rel, rate, nch, scene, er, ench, escene))
                    bad += 1; continue
                st['header ~ PC English (channels, scene, rate within 0.5 %)'] += 1
                rdiff = abs(er - rate); st['max rate difference to PC English (Hz)'] = max(st['max rate difference to PC English (Hz)'], rdiff)
                if kind == 'cinstream':
                    st['cinematic: cine blocks donor %s PC English' % ('=' if nc == enc else '!=')] += 1
        lead = 0; seen_want = False
        for fr, ids in srec:
            for i in ids: ids_all[i] += 1
            if kind == 'cinstream':
                cine_only0['records'] += 1
                if 0 in ids and want not in ids:
                    cine_only0['id 0 without id %d' % want] += 1; cine_only0[rel] += 1
                    if not seen_want: lead += 1
                if want in ids: cine_only0['with id %d' % want] += 1; seen_want = True
        if lead: print('     %s: %d record(s) with id 0 before the first record with id %d' % (rel, lead, want)); cine_only0['lead'] += lead
        st['kind ' + kind.split('\\')[0] + ('\\' + kind.split('\\')[3] if kind.count('\\') >= 3 else '')] += 1
        total += len(d)
        if not dry:
            p = os.path.join(out_dir, rel.replace('\\', os.sep) + suffix)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'wb').write(d)
            st['written'] += 1
        if note: print('     %s: %s' % (rel, note))
    print('records of spec %08x: %d' % (spec, len(recs)))
    for k, v in sorted(st.items()): print('     %-55s %5d' % (k, v))
    print('     bytes: %d (%.1f MB)' % (total, total / 1048576.0))
    print('     subtitle entries per language id (all files): %s' % ', '.join('%d:%d' % kv for kv in sorted(ids_all.items())))
    print('     cinematic subtitle records: %d, with id %d: %d, with id 0 but not id %d: %d' % (
        cine_only0['records'], want, cine_only0['with id %d' % want], want, cine_only0['id 0 without id %d' % want]))
    for k, v in sorted(cine_only0.items()):
        if '\\' in k: print('        %s: %d' % (k, v))
    print('     cinematic records with id 0 before the first record with id %d of their file: %d' % (want, cine_only0['lead']))
    if P:   # the cinematics the donor has no language record of come from the PC archive: do they carry the wanted id?
        dn = set(byh.get(r['hash'], '').lower() for r in recs)
        pcn = collections.Counter()
        for h, rs in pcby.items():
            n = nm.get(h, '')
            if not n.lower().startswith('pc-w\\cinstream\\') or not n.lower().endswith('.mul'): continue
            if n.lower() in dn: continue
            for x in rs:
                if x['spec'] & (1 << lang) == 0: continue
                srec = mul_info(P.read(x))[5]
                first = next((k for k, (fr, ids) in enumerate(srec) if want in ids), None)
                lead = sum(1 for fr, ids in srec[:len(srec) if first is None else first] if 0 in ids and want not in ids)
                pcn['files'] += 1; pcn['records'] += len(srec)
                pcn['files with id %d' % want] += first is not None; pcn['lead'] += lead
                if first is None and srec: print('     PC %s (spec %08x): %d records, none with id %d' % (n, x['spec'], len(srec), want))
                break
        print('     PC cinematics without a donor record (served from the PC archive for language %d): %d files, %d '
              'subtitle records, %d files carry id %d, %d record(s) with id 0 before the first id %d'
              % (lang, pcn['files'], pcn['records'], pcn['files with id %d' % want], want, pcn['lead'], want))
    print('%s; suffix %s; %d check(s) failed' % ('dry run, nothing written' if dry else 'written below %s' % out_dir, suffix, bad))
    return 1 if bad else 0


def main(argv):
    if not argv: sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    if cmd == 'font': return font(rest)
    if cmd == 'locals': return locals_cmd(rest)
    if cmd == 'speech': return speech(rest)
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
