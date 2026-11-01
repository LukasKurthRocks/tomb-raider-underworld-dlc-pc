"""Proven structure fixes of converted DLC DRMs as tree steps (2026-11-01, Befund-Felsrinne.md "Structure audit of the
DLC 2 player and pipeline steps"; pipeline: tools/dlc_fixes_build.py fixes after `statechart`). Each step uses the
layout proven on the base Xbox / PC pairs by its own tool and changes only the words that tool proves wrong:

  translist  tools/state_translist_fix.py   u16 transition-index lists of the player chart's state records
  actlist    tools/state_actlist_fix.py     state record headers, activity entries, u16 lists +0x18 / +0x20 (test 48)
  eventlist  tools/obj_eventlist_fix.py     the object event list (type-11 object +4) of every object (test 48c)
  reclist    tools/model_reclist_fix.py     model DTP record list 36 -> 40 bytes where the PC kept the Xbox stride (48d)
  animfx     tools/animfx_list_fix.py       anim event lists (u32 0 head) of every DRM (test 48g ledge crash)
  childids   tools/dlc2_player_fix.py ids   object child id list (chart +0x48) remapped by name (DLC 2 objects)
  fadeslots  tools/fade_slots_translate.py  own fade (odd-slot) pixel-shader libraries for the TU-drawn player
             objects FADE_OBJECTS (test 48e-48g): build from the file's libraries with empty odd slots, new ids from
             FADE_FIRST_ID in library order, then apply (materials' PS slots old -> new)

translist / actlist run only on player charts (>= statechart_fix_tree.MIN_COND condition records of the title update's
ids; DLC 2 doppelganger_casual DTP 20212) with the base pair lara.drm (Xbox layer2 12647 / PC 850, extracted on demand).
The Xbox source of a DRM: convert_dlc.raw_dlc (TRUDLC_PACK_FIRST honoured, as statechart_fix_tree).

Usage (from the repository root; read-only on SRC, writes changed DRMs to OUT):
  ../bin/pyt -t 3600 tools/dlc_struct_fixes.py SRC_TREE OUT_TREE --steps animfx[,eventlist,...] [--names a.drm,b.drm]
        [--pack pack11]
Library: Steps(tmp).process(rel, path, steps, log, st) -> new raw bytes or None.
"""
import sys, os, io, contextlib, collections, shutil, tempfile, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drm_write as DW, drm_reloc as R

W = os.path.join(HERE, '..', 'work')
ALL = ('translist', 'actlist', 'eventlist', 'reclist', 'animfx', 'childids', 'fadeslots')
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
        self.objlist = objlist

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
        T = self.af_table(); PD = DW.read(cur, 'le')
        res = AF.check_lists(T, XD, PD)
        n = nl = 0
        for xl, pl, wk, diffs, unk in res:
            if wk is None or not diffs: continue
            b = bytearray(pl.data)
            for o, kk, x4, p4, want in diffs: b[o:o + 4] = want; n += 1
            pl.data = bytes(b); nl += 1
        if not n: return None, None
        new = encode(PD, cur)
        again = AF.check_lists(T, XD, DW.read(new, 'le'))
        crash = 0
        for xl, pl, wk, diffs, unk in again:
            if wk is None: continue
            crash += sum(1 for b in AF.branch_report(xl.data, pl.data, wk[1]) if b[3] == 1 and b[1] < 3)
        return new, 'animfx %s: %d words in %d lists set; re-check %d words differ, %d effect records with < 3 words' % (
            rel, n, nl, sum(len(r[3]) for r in again), crash)

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
        S = Steps(tmp, objlist)
        for rel, path in sorted(DA.overlay([os.path.abspath(s) for s in srcs], names).items()):
            new = S.process(rel, path, steps, log, st)
            if new is not None:
                q = os.path.join(out, rel); os.makedirs(os.path.dirname(q), exist_ok=True); open(q, 'wb').write(new)
                DW.read(open(q, 'rb').read(), 'le')
                files.append(rel)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    log.append('total %s' % dict(st))
    return files, log


def main(argv):
    names = None; steps = None
    if '--names' in argv: k = argv.index('--names'); names = set(argv[k + 1].split(',')); del argv[k:k + 2]
    if '--steps' in argv: k = argv.index('--steps'); steps = argv[k + 1].split(','); del argv[k:k + 2]
    if '--pack' in argv: k = argv.index('--pack'); os.environ['TRUDLC_PACK_FIRST'] = argv[k + 1]; del argv[k:k + 2]
    if len(argv) != 2 or not steps or any(s not in ALL for s in steps): raise SystemExit(__doc__)
    ol = os.path.join(argv[0], 'tr8', 'pc-w', 'objectlist.txt')
    files, log = run_tree([argv[0]], argv[1], [s for s in ALL if s in steps], names, ol if os.path.exists(ol) else None)
    for l in log: print(l)
    print('written %d files to %s: %s' % (len(files), argv[1], ', '.join(files)))


if __name__ == '__main__':
    main(sys.argv[1:])
