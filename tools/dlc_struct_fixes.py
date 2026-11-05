"""Proven structure fixes of converted DLC DRMs as tree steps (2026-11-01, Befund-Felsrinne.md "Structure audit of the
DLC 2 player and pipeline steps"; pipeline: tools/dlc_fixes_build.py fixes after `statechart`). Each step uses the
layout proven on the base Xbox / PC pairs by its own tool and changes only the words that tool proves wrong:

  translist  tools/state_translist_fix.py   u16 transition-index lists of the player chart's state records
  actlist    tools/state_actlist_fix.py     state record headers, activity entries, u16 lists +0x18 / +0x20 (test 48)
  eventlist  tools/obj_eventlist_fix.py     the object event list (type-11 object +4) of every object (test 48c)
  reclist    tools/model_reclist_fix.py     model DTP record list 36 -> 40 bytes where the PC kept the Xbox stride (48d)
  animfx     tools/animfx_list_fix.py       anim event lists (u32 0 head) of every DRM (test 48g ledge crash); lists of
             renumbered base DTPs (Xbox partner by position has another id) are skipped (2026-11-03, finding 44)
  childids   tools/dlc2_player_fix.py ids   object child id list (chart +0x48) remapped by name (DLC 2 objects)
  fadeslots  tools/fade_slots_translate.py  own fade (odd-slot) pixel-shader libraries for the TU-drawn player
             objects FADE_OBJECTS (test 48e-48g): build from the file's libraries with empty odd slots, new ids from
             FADE_FIRST_ID in library order, then apply (materials' PS slots old -> new)
  markup     tools/markup_fix.py            object markup records (0x5c bytes; DLC 2 machine column ids, 2026-11-01)
  vmliteral  tools/vm_literal_fix.py        VM literals after opcode 2 = one u32 (test 48l crash, 48m)
  objtex     tools/objdata_fx_fix.py        object data DTP (object +8) texture group counts {u32 n, ids} at D+0x68 =
             the Xbox u32 (F16 2026-11-04: a raw 0x03000000 made tru+0x12b360 AND 0x1fff over 50 M dwords)
  objrec     tools/objdata_fx_fix.py        0x17c particle records of the object data DTP by the 66 byte classes
             proven on the base pairs (F3 / B24 2026-11-04: +0x148 anim byte 0x41 = 65 -> crash tru+0x42e62); every
             copy of the DTP; only words whose PC bytes are another byte order of the Xbox word
  objid      tools/objdata_idword_fix.py    player data block (DTP +0xc8 pointer) +0x94 / +0x98 breath-sound section ids
             = one u32 where the converter wrote two u16 and the Xbox u32 names a section of the same file (N8
             2026-11-04: doppelganger_casual DTP 20212 0x68f40000 -> 26868, TruDataGuard 'invalid id' at tru+0x194cad);
             the generic u16-pair candidates of objdata_idword_fix scan are NOT repaired
  twins     tools/dlc_structure_audit.py   base-twin truth for every same-size section of TWIN_FILES (the DLC 2
             player objects): only byte-order errors, re-authored words are left alone; runs first (before the
             layout steps, so a proven layout always has the last word - e.g. the u16 transition list word +0x4c550
             of DTP 20212, where the twins' raw block disagrees with state_translist_fix / state_actlist_fix)
  condlist   tools/chart_condlist_fix.py    every condition record a transition of the player chart lists, by the
             proven transition / record layouts (2026-11-02: 134 records such as {800,501}, {500,1} left u32-swapped
             by the id-based statechart_cond_fix; = tree dlc_test50a_chart)
Order in the pipeline (tools/dlc_fixes_build.py, after `statechart`): twins, childids, translist, actlist, condlist,
eventlist, reclist, fadeslots, animfx, markup, objtex, objrec, objid, vmliteral (objtex / objrec / objid since
2026-11-04, agent N11: they touch only the object data DTP / its player data block, no other step does; the trees
dlc_test51c_objfx / dlc_test51e_dgids were built with the stand-alone tools on finished DRMs and are reproduced by these
steps, docs Befund-Pipeline-Integration-0411.md). Diagnostic builds (e.g. 48i_tex MaterialParams[1] = 0 of
material 25521) are never steps.
Check mode (objtex / objrec / objid only; tools/Invoke-TruPipeline.ps1 after Fixes and per costume pack):
  ../bin/pyt -t 3600 tools/dlc_struct_fixes.py check TREE [--steps objtex,objrec,objid] [--pack pack11] [--report R.json]
        nothing is written; exit 1 when any DRM would still change (counts of DRMs / words per step), 0 = ok;
        objtex also runs the pack-independent structural check of tools/objdata_texlist_check.py on every DRM (a DTP
        whose Xbox copy of the chosen pack has another layout is skipped by the comparison, 2026-11-05 dlc_dungeon)

translist / actlist / condlist run only on player charts (>= statechart_fix_tree.MIN_COND condition records of the title update's
ids; DLC 2 doppelganger_casual DTP 20212) with the base pair lara.drm (Xbox layer2 12647 / PC 850, extracted on demand).
The Xbox source of a DRM: convert_dlc.raw_dlc (TRUDLC_PACK_FIRST honoured, as statechart_fix_tree).

Usage (from the repository root; read-only on SRC, writes changed DRMs to OUT):
  ../bin/pyt -t 5400 tools/dlc_struct_fixes.py SRC_TREE OUT_TREE --steps animfx[,eventlist,...] [--names a.drm,b.drm]
        [--pack pack11]          (twins: ~20 min for the corpus pass, the other steps a few minutes per tree)
Library: Steps(tmp).process(rel, path, steps, log, st) -> new raw bytes or None.
"""
import sys, os, io, contextlib, collections, shutil, tempfile, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_write as DW, drm_reloc as R

W = os.path.join(HERE, '..', 'work')
ALL = ('twins', 'translist', 'actlist', 'condlist', 'eventlist', 'reclist', 'animfx', 'childids', 'fadeslots', 'markup',
       'objtex', 'objrec', 'objid', 'vmliteral')
TWIN_FILES = ('doppelganger_casual.drm', 'player_tru_dlc2_extension.drm')
MARKUP_TYPES = {1, 22, 23}    # markup type chars of the DLC 2 object markup (markup_level.py --objects; 23 = TU type)
FADE_OBJECTS = ('doppelganger_casual.drm', 'player_tru_dlc2_extension.drm')
FADE_FIRST_ID = 2494          # section_id_free.py 9 2494 45 ... (test 48g): 2494-2531 free; 2491-2493 = test 46
XOBJLIST = os.path.join(W, 'generic', 'lists', 'dlc_pack11_objectlist.txt')


def quiet(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = fn(*a)
    return r, buf.getvalue()


def encode(PD, like):
    raw = PD.write('le')
    return DW.cdrm_encode(raw, 'le') if like[:4] == b'CDRM' else raw


class Steps:
    def __init__(self, tmp, objlist=None):
        self.tmp = tmp; self._oe = self._af = None; self._refs = None; self._ids = None
        self.objlist = objlist; self._objrules = None

    # ---- shared inputs, built once per run
    def oe_table(self):
        if self._oe is None:
            import obj_eventlist_fix as OE
            self._oe = quiet(OE.proof_table, 'all', 'x')[0][0]
        return self._oe

    def af_table(self):
        if self._af is None:
            import animfx_list_fix as AF
            self._af = quiet(AF.proof_table, 'all', 'x')[0][0]
        return self._af

    def lara_refs(self):
        if self._refs is None:
            import bigfile_extract as BE
            xl, pl = os.path.join(self.tmp, 'x_lara.drm'), os.path.join(self.tmp, 'pc_lara.drm')
            quiet(BE.main, ['xbase2', 'lara.drm', xl]); quiet(BE.main, ['pcbig', 'lara.drm', pl])
            self._refs = (xl, pl)
        return self._refs

    def tu_ids(self):
        if self._ids is None:
            import statechart_fix_tree as SF, statechart_cond_fix as SC
            self._ids = SC.tu_ids(open(SF.TU_IMAGE, 'rb').read()) if os.path.exists(SF.TU_IMAGE) else False
        return self._ids

    def player_charts(self, XD):
        import statechart_corpus as CO, statechart_cond_fix as SC, statechart_fix_tree as SF
        ids = self.tu_ids()
        if not ids: return None
        out = []
        for s in XD.sections:
            if s.type != 7 or s.id < 20000 or CO.fam_be(bytes(s.data), s.id) != 'chart': continue
            r = R.parse(bytes(s.reloc), 'be')
            if len(SC.records(bytes(s.data), '>', ids, set(r.pointer_offsets()) | set(r.id_offsets()))) >= SF.MIN_COND:
                out.append(s.id)
        return out

    # ---- steps: each returns (new raw or None, log line or None)
    def s_translist(self, rel, xf, XD, cur):
        import state_translist_fix as TL
        return self._chart_step(rel, xf, XD, cur, 'translist', lambda a: TL.main(a))

    def s_actlist(self, rel, xf, XD, cur):
        import state_actlist_fix as AL
        return self._chart_step(rel, xf, XD, cur, 'actlist', lambda a: AL.check_main(a))

    def s_condlist(self, rel, xf, XD, cur):
        import chart_condlist_fix as CL
        return self._chart_step(rel, xf, XD, cur, 'condlist', lambda a: CL.main(a))

    def _chart_step(self, rel, xf, XD, cur, name, fn):
        pcs = self.player_charts(XD)
        if pcs is None: return None, '%s %s: no title-update image - player charts not identified, step skipped' % (name, rel)
        if not pcs: return None, None
        # only a PC section of the same id and size (e.g. lara_doppelganger 25048 is the PC base chart, 550 112 bytes)
        PD = DW.read(cur, 'le'); xsz = {s.id: len(s.data) for s in XD.sections if s.type == 7}
        same = {s.id for s in PD.sections if s.type == 7 and xsz.get(s.id) == len(s.data)}
        skipped = [sid for sid in pcs if sid not in same]
        pcs = [sid for sid in pcs if sid in same]
        if not pcs: return None, '%s %s: player chart(s) %s with a PC section of another size - not this layout, skipped' % (
            name, rel, skipped)
        xl, pl = self.lara_refs()
        raw = None; notes = []
        for sid in pcs:
            src = os.path.join(self.tmp, 'in_%s.drm' % name); dst = os.path.join(self.tmp, 'out_%s.drm' % name)
            open(src, 'wb').write(cur if raw is None else raw)
            if os.path.exists(dst): os.remove(dst)
            try:
                _, txt = quiet(fn, [xl, pl, '12647', '850', xf, src, str(sid), '--out', dst])
            except SystemExit as e:
                notes.append('DTP %d: tool stopped (%s), nothing changed' % (sid, e)); continue
            if os.path.exists(dst):
                new = open(dst, 'rb').read()
                raw = new
            notes.append('DTP %d: %s' % (sid, ' / '.join(l.strip() for l in txt.splitlines()
                                                          if 'wrong' in l or l.startswith('written') or 'differ' in l)[:600]))
        if raw is not None and DW.read(raw, 'le').write('le') == DW.read(cur, 'le').write('le'): raw = None
        return raw, '%s %s: %s' % (name, rel, '; '.join(notes))

    def s_eventlist(self, rel, xf, XD, cur):
        import obj_eventlist_fix as OE
        T = self.oe_table(); PD = DW.read(cur, 'le')
        res = quiet(OE.check_lists, T, XD, PD, False)[0]
        n = 0
        for oid, xl, pl, wk, diffs, unk in res:
            if not diffs: continue
            b = bytearray(pl.data)
            for o, kk, x4, p4, want in diffs: b[o:o + 4] = want; n += 1
            pl.data = bytes(b)
            fw = OE.walk(pl.data, 'le')
            assert [(a, h) for a, h, _ in fw[0]] == [(a, struct.unpack_from('>H', xl.data, a)[0]) for a, _, _ in wk[1]]
        if not n: return None, None
        new = encode(PD, cur)
        again = quiet(OE.check_lists, T, XD, DW.read(new, 'le'), False)[0]
        return new, 'eventlist %s: %d words in %d lists set; re-check %d words differ' % (
            rel, n, sum(1 for r in res if r[4]), sum(len(r[4]) for r in again))

    def s_animfx(self, rel, xf, XD, cur):
        import animfx_list_fix as AF
        import converter_faults_fix as CF
        T = self.af_table(); PD = DW.read(cur, 'le')
        res = AF.check_lists(T, XD, PD)
        # check_lists pairs the lists by DTP id; a PC list whose Xbox partner by position (the converter keeps the
        # section order, CF.pairs_by_position) has another id is a renumbered base DTP, and the Xbox list of the same
        # id is an unrelated one (id coincidence: dlc_costume_* / lara_doppelganger DTPs 1183, 1444, 1799, 2012 got
        # foreign frames, 2026-11-03 finding 44) - skipped; tools/converter_faults_fix.py animlist checks them
        own = {id(p) for k, x, p in CF.pairs_by_position(XD, PD) if x.id == p.id}
        skipped = sum(1 for r in res if r[2] is not None and r[3] and id(r[1]) not in own)
        res = [r for r in res if id(r[1]) in own]
        n = nl = 0
        for xl, pl, wk, diffs, unk in res:
            if wk is None or not diffs: continue
            b = bytearray(pl.data)
            for o, kk, x4, p4, want in diffs: b[o:o + 4] = want; n += 1
            pl.data = bytes(b); nl += 1
        note = ('; %d base-mapped list(s) with an id-coincident Xbox list skipped' % skipped) if skipped else ''
        if not n: return None, (('animfx %s: 0 words set' % rel) + note) if skipped else None
        new = encode(PD, cur)
        ND = DW.read(new, 'le')
        own2 = {id(p) for k, x, p in CF.pairs_by_position(XD, ND) if x.id == p.id}
        again = [r for r in AF.check_lists(T, XD, ND) if id(r[1]) in own2]
        crash = 0
        for xl, pl, wk, diffs, unk in again:
            if wk is None: continue
            crash += sum(1 for b in AF.branch_report(xl.data, pl.data, wk[1]) if b[3] == 1 and b[1] < 3)
        return new, 'animfx %s: %d words in %d lists set; re-check %d words differ, %d effect records with < 3 words%s' % (
            rel, n, nl, sum(len(r[3]) for r in again), crash, note)

    def s_reclist(self, rel, xf, XD, cur):
        import model_reclist_fix as MR
        PD = DW.read(cur, 'le')
        todo = []
        for oid, s in MR.model_dtps(PD, 'le'):
            m = MR.model_list(s, 'le')
            if m is not None and MR.stride(*m) == MR.XS: todo.append(s.id)
        if not todo: return None, None
        raw = cur; notes = []
        for sid in todo:
            src = os.path.join(self.tmp, 'in_reclist.drm'); dst = os.path.join(self.tmp, 'out_reclist.drm')
            open(src, 'wb').write(raw)
            _, txt = quiet(MR.fix, [src, dst, str(sid), '--words', xf])
            raw = open(dst, 'rb').read()
            notes.append('DTP %d: %s' % (sid, ' / '.join(l.strip() for l in txt.splitlines())))
        if cur[:4] != b'CDRM': raw = DW.read(raw, 'le').write('le')
        return raw, 'reclist %s: %s' % (rel, '; '.join(notes))

    def s_childids(self, rel, xf, XD, cur):
        import dlc2_player_fix as PF, objlists as OL
        if not self.objlist or not os.path.exists(self.objlist) or not os.path.exists(XOBJLIST): return None, None
        PD = DW.read(cur, 'le')
        if not any(s.type == 11 for s in PD.sections): return None, None
        try:
            _, xa, xids = PF.child_list(XD, '>'); ps, pa, pids = PF.child_list(PD, '<')
        except StopIteration:
            return None, None
        if xa is None or pa is None or xa != pa or len(xids) != len(pids): return None, None
        xo = OL.read_objectlist(open(XOBJLIST, 'rb').read()); po = OL.read_objectlist(open(self.objlist, 'rb').read())
        byname = {v: k for k, v in po.items()}
        want = [byname.get(xo.get(i), i) for i in xids]
        bad = [k for k in range(len(want)) if want[k] != pids[k]]
        if not bad: return None, None
        d = bytearray(ps.data)
        for k in bad: struct.pack_into('<H', d, pa + 2 * k, want[k])
        ps.data = bytes(d)
        return encode(PD, cur), 'childids %s: DTP %d child list %s -> %s' % (rel, ps.id, pids, want)

    def s_fadeslots(self, rel, xf, XD, cur):
        import fade_slots_translate as FS, shaderlib as SL
        if os.path.basename(rel).lower() not in FADE_OBJECTS: return None, None
        PD = DW.read(cur, 'le')
        if any(s.type == 9 and FADE_FIRST_ID <= s.id < FADE_FIRST_ID + 45 for s in PD.sections):
            return None, 'fadeslots %s: own fade libs already present - skipped' % rel
        used = set()
        for s in PD.sections:
            if s.type != 10: continue
            refs = set(R.parse(s.reloc, 'le').idref)
            for k in range(3):
                if (9, 0x28 + 4 * k) in refs: used.add(struct.unpack_from('<I', s.data, 0x28 + 4 * k)[0])
        libs = []
        for s in PD.sections:
            if s.type != 9 or s.id not in used: continue
            lib = SL.parse(s.data, 'le')
            if lib['kind'] != 1: continue
            if any(lib['slots'][k] == FS.NONE and lib['slots'][k - 1] != FS.NONE for k in range(1, len(lib['slots']), 2)):
                libs.append(s.id)
        if not libs: return None, None
        libs = sorted(set(libs))
        outd = os.path.join(self.tmp, 'fade_' + os.path.basename(rel)[:-4])
        src = os.path.join(self.tmp, 'in_fade.drm'); dst = os.path.join(self.tmp, 'out_fade.drm')
        open(src, 'wb').write(cur)
        _, t1 = quiet(FS.cmd_build, src, xf, outd, FADE_FIRST_ID, libs)
        _, t2 = quiet(FS.cmd_apply, src, dst, outd, None)
        new = open(dst, 'rb').read()
        if cur[:4] != b'CDRM': new = DW.read(new, 'le').write('le')
        last = [l for l in t2.splitlines() if l.startswith('readback') or l.startswith('wrote')]
        return new, 'fadeslots %s: libs %s -> own ids from %d; %s' % (rel, libs, FADE_FIRST_ID, ' / '.join(last))

    def s_markup(self, rel, xf, XD, cur):
        """object markup records (tools/markup_fix.py layout, proven on ar_uo_valgrind_column_floor{a,b}_ringa): only
        DTPs with a markup array (+0x54 count, +0x58 records) whose Xbox records carry a markup type char seen in the
        DLC 2 markup scan (MARKUP_TYPES) - the 0xe0-byte look-alike arrays (types 0 / 97 / 112 / 191) are not markup"""
        import markup_fix as MF
        PD = DW.read(cur, 'le'); n_all = 0; notes = []
        xby = collections.defaultdict(list)
        for x in XD.sections:
            if x.type == 7: xby[x.id].append(x)
        for s in PD.sections:
            d = bytearray(s.data)
            if s.type != 7 or len(d) < 0x5c: continue
            r = R.parse(bytes(s.reloc), 'le')
            relocated = set(o for o, _ in r.internal) | set(o for _, o, _ in r.external)
            ro = dict(r.internal).get(0x58); n = struct.unpack_from('<I', d, 0x54)[0]
            if ro is None or not 1 <= n <= 1000 or ro + n * MF.STRIDE > len(d): continue
            if not all(struct.unpack_from('<I', d, ro + k * MF.STRIDE + 0x28)[0] == 0 for k in range(n)): continue
            xs = xby.get(s.id, [])
            if len(xs) != 1 or len(xs[0].data) != len(d): continue
            xd = bytes(xs[0].data)
            if struct.unpack_from('>I', xd, 0x54)[0] != n: continue
            types = {xd[ro + k * MF.STRIDE + 0x33] for k in range(n)}
            if not types <= MARKUP_TYPES:
                notes.append('DTP %d skipped (record types %s: not markup)' % (s.id, sorted(types))); continue
            # every markup record points at its poly line (+0x58 relocated, on both platforms)
            xin = dict(R.parse(bytes(xs[0].reloc), 'be').internal); pin = dict(r.internal)
            if not all(ro + k * MF.STRIDE + 0x58 in xin and ro + k * MF.STRIDE + 0x58 in pin for k in range(n)):
                notes.append('DTP %d skipped (records without a poly-line pointer at +0x58: not markup)' % s.id); continue
            ch = 0
            for k in range(n):
                o = ro + k * MF.STRIDE
                for w in range(0, 0x58, 4):
                    if o + w in relocated: continue
                    new = MF.conv(xd[o + w:o + w + 4], w)
                    if bytes(d[o + w:o + w + 4]) != new: d[o + w:o + w + 4] = new; ch += 1
            if ch:
                s.data = bytes(d); n_all += ch; notes.append('DTP %d: %d records, %d words' % (s.id, n, ch))
        if not n_all: return None, ('markup %s: %s' % (rel, '; '.join(notes))) if notes else None
        return encode(PD, cur), 'markup %s: %s' % (rel, '; '.join(notes))

    def s_objtex(self, rel, xf, XD, cur):
        return self._objdata(rel, XD, cur, 'objtex', 'texcount')

    def s_objrec(self, rel, xf, XD, cur):
        return self._objdata(rel, XD, cur, 'objrec', 'rec')

    def _objdata(self, rel, XD, cur, name, step):
        """tools/objdata_fx_fix.py step on one DRM; the written bytes are proven (decoded DRM differs only in the planned
        bytes, headers / relocations identical, re-check 0) - a failed proof leaves the DRM unchanged"""
        import objdata_fx_fix as OF
        if step == 'rec' and self._objrules is None: self._objrules = OF.load_rules()
        PD = DW.read(cur, 'le')
        changes, notes = OF.fix_drm(XD, PD, [step], self._objrules or {})
        odd = [n for n in notes if 'words set' not in n]
        if not changes:
            return None, ('%s %s: 0 words; %s' % (name, rel, '; '.join(odd))) if odd else None
        new = encode(PD, cur)
        try:
            proof = OF.verify(cur, new, changes, XD, [step], self._objrules or {})
        except AssertionError as e:
            return None, '%s %s: proof failed (%s) - nothing changed' % (name, rel, e)
        return new, '%s %s: %d words (%s);%s' % (name, rel, len(changes),
                                               '; '.join(n for n in notes if 'words set' in n and ': 0 words' not in n),
                                               proof[0].replace('  proof:', ''))

    def s_objid(self, rel, xf, XD, cur):
        """player data breath-sound ids +0x94 / +0x98 of the +0xc8 data block (tools/objdata_idword_fix.fix_drm, N8
        2026-11-04: doppelganger_casual DTP 20212 0x68f40000 -> 26868); proven class only. Proof: the decoded DRM
        differs from the input only in the planned bytes, headers / relocations identical, re-check plans 0 words"""
        import objdata_idword_fix as IW
        PD = DW.read(cur, 'le')
        changes, lines, cnt = IW.fix_drm(XD, PD)
        if not changes: return None, None
        new = encode(PD, cur)
        D0, D1 = DW.read(cur, 'le'), DW.read(new, 'le')
        planned = {(k, o + j) for k, o, a, b in changes for j in range(4) if a[j] != b[j]}
        got = set()
        for k, (a, b) in enumerate(zip(D0.sections, D1.sections)):
            if (a.type, a.id, a.flags, a.ver, a.spec, a.pad, bytes(a.reloc), len(a.data)) != \
               (b.type, b.id, b.flags, b.ver, b.spec, b.pad, bytes(b.reloc), len(b.data)):
                return None, 'objid %s: proof failed (section %d header / relocation changed) - nothing changed' % (rel, k)
            got |= {(k, i) for i in range(len(a.data)) if a.data[i] != b.data[i]}
        if got != planned or len(D0.sections) != len(D1.sections) or (D0.names, D0.pad) != (D1.names, D1.pad):
            return None, 'objid %s: proof failed (%d bytes differ, %d planned) - nothing changed' % (rel, len(got), len(planned))
        again = IW.fix_drm(XD, DW.read(new, 'le'))[0]
        if again: return None, 'objid %s: proof failed (re-check plans %d words) - nothing changed' % (rel, len(again))
        return new, 'objid %s: %d words (%s); proof: %d bytes differ = planned, headers + relocations identical, ' \
                    're-check 0' % (rel, len(changes), ', '.join('DTP %d +0x%x %s -> %s' % (
                        PD.sections[k].id, o, a.hex(), b.hex()) for k, o, a, b in changes), len(got))

    def s_vmliteral(self, rel, xf, XD, cur):
        """VM literals after opcode 2 (tools/vm_literal_fix.py, test 48l: one u32 whatever it holds)"""
        # the check of vm_literal_fix.check, but only byte-order errors are set: a literal whose PC value is no byte
        # order of the Xbox u32 was re-numbered on purpose (e.g. lara_doppelganger DTP 2242 = the PC base copy)
        import vm_literal_fix as VL
        PD = DW.read(cur, 'le')
        xs = {s.id: s for s in XD.sections if s.type == 7}
        n = 0; notes = []; kept = 0
        for ps in PD.sections:
            if ps.type != 7 or ps.id not in xs: continue
            x, p = bytes(xs[ps.id].data), bytearray(ps.data)
            if len(x) != len(p): continue
            if not any(struct.unpack_from('>I', x, o)[0] == VL.CALL for o in range(0, len(x) - 3, 4)): continue
            it = VL.rel(ps, 'le'); ch = False
            for o in range(0, len(x) - 7, 4):
                if struct.unpack_from('>I', x, o)[0] != VL.PUSH or struct.unpack_from('<I', p, o)[0] != VL.PUSH: continue
                q = o + 4
                if q in it: continue
                want = x[q:q + 4][::-1]; got = bytes(p[q:q + 4])
                if got == want: continue
                m = VL.mode(x[q:q + 4], got)
                if m == 'other': kept += 1; continue
                p[q:q + 4] = want; n += 1; ch = True
                notes.append('DTP %d +0x%x %s -> u32 0x%08x' % (ps.id, q, m, struct.unpack('<I', want)[0]))
            if ch: ps.data = bytes(p)
        if not n:
            return None, ('vmliteral %s: %d literals re-numbered on the PC (no byte order) kept' % (rel, kept)) if kept else None
        return encode(PD, cur), 'vmliteral %s: %d literals set (%s); %d re-numbered kept' % (rel, n, ', '.join(notes[:20]), kept)

    def process(self, rel, path, steps, log, st):
        from convert_dlc import raw_dlc
        from drm import cdrm_decode
        raw, _ = raw_dlc(rel.replace('/', '\\'))
        if raw is None: raw, _ = raw_dlc(os.path.basename(rel))
        if raw is None: return None
        xraw = cdrm_decode(raw, 'be'); XD = DW.read(xraw, 'be')
        xf = os.path.join(self.tmp, 'x_' + os.path.basename(rel)); open(xf, 'wb').write(xraw)
        cur = open(path, 'rb').read(); orig = cur
        for name in steps:
            new, line = getattr(self, 's_' + name)(rel, xf, XD, cur)
            if line: log.append(line)
            if new is not None:
                cur = new; st[name] += 1
        return cur if cur != orig else None


def run_tree(srcs, out, steps, names=None, objlist=None, write_in_place=False):
    """srcs: folders (later wins); changed DRMs are written to out. Returns (files, log)."""
    import dtp_audit as DA
    tmpdir = os.path.join(W, 'statechart'); os.makedirs(tmpdir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='struct_', dir=tmpdir)
    st = collections.Counter(); files, log = [], []
    try:
        if 'twins' in steps:
            files, log = run_twins(srcs, out, names, tmp)
            steps = [s for s in steps if s != 'twins']
            srcs = list(srcs) + [out]          # the following steps read the twins output
        S = Steps(tmp, objlist)
        for rel, path in sorted(DA.overlay([os.path.abspath(s) for s in srcs], names).items()):
            if steps == ['fadeslots'] and os.path.basename(rel).lower() not in FADE_OBJECTS: continue
            if not steps: break
            new = S.process(rel, path, steps, log, st)
            if new is not None:
                q = os.path.join(out, rel); os.makedirs(os.path.dirname(q), exist_ok=True); open(q, 'wb').write(new)
                DW.read(open(q, 'rb').read(), 'le')
                if rel not in files: files.append(rel)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    log.append('total %s' % dict(st))
    return files, log


def run_twins(srcs, out, names, tmp):
    """step 'twins': tools/dlc_structure_audit.py check --out over TWIN_FILES (one base-corpus pass for all of them):
    words of every same-size section whose PC bytes the base twins prove (leave-one-DRM-out precision >= 99.9 % per
    family / level, every 5th base DRM) and the converter wrote in another byte order; re-authored values stay"""
    import dtp_audit as DA, dlc_structure_audit as AU
    from convert_dlc import raw_dlc
    from drm import cdrm_decode
    files, log, argv = [], [], ['check']
    todo = sorted((rel, p) for rel, p in DA.overlay([os.path.abspath(s) for s in srcs], names).items()
                  if os.path.basename(rel).lower() in TWIN_FILES)
    for rel, path in todo:
        raw, _ = raw_dlc(rel.replace('/', '\\'))
        if raw is None: raw, _ = raw_dlc(os.path.basename(rel))
        if raw is None: continue
        xf = os.path.join(tmp, 'twx_' + os.path.basename(rel)); open(xf, 'wb').write(cdrm_decode(raw, 'be'))
        argv += [xf, path]
    if len(argv) == 1: return files, ['twins: none of %s in the tree' % (TWIN_FILES,)]
    od = os.path.join(tmp, 'twins_out'); rep = os.path.join(tmp, 'twins_report.txt')
    _, txt = quiet(AU.main, argv + ['--out', od, '--report', rep, '--list', '20'])
    log += [l for l in open(rep, encoding='utf-8').read().splitlines() if l.strip()]
    for rel, path in todo:
        p = os.path.join(od, os.path.basename(rel))
        if not os.path.exists(p): continue
        new = open(p, 'rb').read()
        if DW.read(new, 'le').write('le') == DW.read(open(path, 'rb').read(), 'le').write('le'): continue
        q = os.path.join(out, rel); os.makedirs(os.path.dirname(q), exist_ok=True); open(q, 'wb').write(new)
        files.append(rel)
    return files, log


CHECK_STEPS = ('objtex', 'objrec', 'objid')   # steps with a check mode (no tool run, no shared corpus pass)


def run_check(tree, steps, names=None, report=None):
    """check mode (2026-11-04, agent N11): run the steps on every DRM of TREE in memory, write nothing; exit code 1 when
    any DRM would change (a fix left out), 0 otherwise. Report: JSON {step: {files, lines}}."""
    import dtp_audit as DA, json
    tmpdir = os.path.join(W, 'statechart'); os.makedirs(tmpdir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='structchk_', dir=tmpdir)
    rep = {s: {'files': [], 'lines': []} for s in steps}; n = 0; nox = []
    from convert_dlc import raw_dlc
    try:
        S = Steps(tmp, None)
        for rel, path in sorted(DA.overlay([os.path.abspath(tree)], names).items()):
            n += 1
            if 'objtex' in steps and rel.lower().endswith('.drm'):
                # pack-independent structural check (agent F25 2026-11-05): the Xbox comparison above skips a DTP whose
                # Xbox copy has another layout - e.g. the DLC 2 (pack11) dlc_fx_cine_thrall_death checked against the
                # pack10 copy ("u16 group count +0x64 Xbox 4 PC 7", 0 words, check ok) - so a raw group count
                # (0x04000000, crash tru+0x12b4a0 in DLC 1 dlc_dungeon) passed; objdata_texlist_check walks the groups
                # of the PC file alone and fails on a count > 64 / byte-swapped / past the DTP end
                import objdata_texlist_check as TLC
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    _, nbad_tl = TLC.check_drm(path, 64, False)
                if nbad_tl:
                    rep['objtex']['files'].append(rel)
                    rep['objtex']['lines'] += ['objtex %s: structural (pack independent): %s' % (
                        rel, ' | '.join(x.strip() for x in buf.getvalue().splitlines()))]
            if raw_dlc(rel.replace('/', '\\'))[0] is None and raw_dlc(os.path.basename(rel))[0] is None:
                nox.append(rel); continue
            for s in steps:
                log = []
                if S.process(rel, path, [s], log, collections.Counter()) is not None and rel not in rep[s]['files']:
                    rep[s]['files'].append(rel)
                rep[s]['lines'] += log
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = sum(len(v['files']) for v in rep.values())
    print('check %s: %d DRMs, %d without an Xbox original (not checked)%s' % (
        tree, n, len(nox), (': ' + ', '.join(nox[:10])) if nox else ''))
    import re
    for s in steps:
        rep[s]['words'] = sum(int(m.group(1)) for m in (re.match(r'%s \S+: (\d+) words' % s, l) for l in rep[s]['lines']) if m)
        print('check %-7s %d of %d DRMs would change, %d words%s' % (s, len(rep[s]['files']), n, rep[s]['words'],
                                                          (': ' + ', '.join(rep[s]['files'][:20])) if rep[s]['files'] else ''))
        for l in rep[s]['lines'][:200]: print('   ', l[:400])
    print('check: %s' % ('FAIL - %d file/step pair(s) still to fix' % bad if bad else 'ok (%d DRMs, steps %s)' % (n, ','.join(steps))))
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        json.dump(dict(tree=tree, drms=n, no_xbox_original=nox, steps=list(steps), result='fail' if bad else 'ok', per_step=rep),
                  open(report, 'w', encoding='utf-8'), indent=1)
    return 1 if bad else 0


def main(argv):
    names = None; steps = None
    if '--names' in argv: k = argv.index('--names'); names = set(argv[k + 1].split(',')); del argv[k:k + 2]
    if '--steps' in argv: k = argv.index('--steps'); steps = argv[k + 1].split(','); del argv[k:k + 2]
    if '--pack' in argv: k = argv.index('--pack'); os.environ['TRUDLC_PACK_FIRST'] = argv[k + 1]; del argv[k:k + 2]
    if argv and argv[0] == 'check':
        rep = None
        if '--report' in argv: k = argv.index('--report'); rep = argv[k + 1]; del argv[k:k + 2]
        steps = steps or list(CHECK_STEPS)
        if len(argv) != 2 or any(s not in CHECK_STEPS for s in steps): raise SystemExit(__doc__)
        sys.exit(run_check(argv[1], [s for s in ALL if s in steps], names, rep))
    if len(argv) != 2 or not steps or any(s not in ALL for s in steps): raise SystemExit(__doc__)
    ol = os.path.join(argv[0], 'tr8', 'pc-w', 'objectlist.txt')
    files, log = run_tree([argv[0]], argv[1], [s for s in ALL if s in steps], names, ol if os.path.exists(ol) else None)
    for l in log: print(l)
    print('written %d files to %s: %s' % (len(files), argv[1], ', '.join(files)))


if __name__ == '__main__':
    main(sys.argv[1:])
