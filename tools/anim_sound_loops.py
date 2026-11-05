"""Anim-event sounds that can loop forever (F5 groan / kick loop, test questions 2026-11-05), read-only.

Engine facts used (tru.exe PC 6905b046, tools/pe_dis.py, tools/pe_rtti_vtable.py):
  anim event record {u16 h, s16 frame, u8 b4, 3 bytes, payload}; kind (h & 3) 0 -> 0x5b99c0(payload):
    payload byte 0 == 0: sound, *(u32 *)(payload + 4) = pointer to a SoundPlex NODE {u32 type, ptr data, u32 id}
      (0x5935d0 -> walker 0x5920b0); kept in the instance sound list [inst+0x248] only if payload byte 1 bit 0
      (or channel != -1 and parameter != -1), else the handle is dropped at once (fire and forget)
    payload byte 0 == 1: sound by section id (0x5953e0 -> 0x54df80(id)), never kept
  SoundPlex walker 0x5920b0, jump table 0x5923cc (RTTI class of the object each case builds):
     0 TimeIn (0x583bf0)        1 indirect: data -> u32 DTP id of another plex (0x54df80)
     2 Wave (0x591220)          3 Stream (0x591080)       4 Assignment (0x590970)   5 Envelope (0x590ce0)
     6 list: first child that builds (0x587920)          7 MaterialList (0x58dfc0) 8 0x583490 (byte +0x46)
     9 Reaction (0x590f30)     10 Sequence (0x58e070)    11 Overlap (0x58b570)     12 Effect (0x58def0)
    13 Oscillator (0x587c60)
  Wave node data: +0 u32 wave id (-> [0xc56fe0] vtbl+0x64), +4 u8, +6 u16.

Modes (from the repository root):
  ../bin/pyt -t 300 tools/anim_sound_loops.py waves XBOX_NAME PC.drm
        wave sections (type 6) of both files: pre-header words, XMA fmt loop fields (Xbox), FSB4 sample mode /
        loop points (PC) - to find which field carries 'loop'
  ../bin/pyt -t 600 tools/anim_sound_loops.py events XBOX_NAME PC.drm [--all]
        every anim event list of both files, sound events (kind 0) with payload bytes Xbox / PC, list bit, the
        SoundPlex tree they start (node types, wave ids, loop flag of the wave) - only looping ones unless --all
XBOX_NAME: name of the DRM in the Xbox DLC packs (convert_dlc.raw_dlc, DLC 2 names: pack11 first) or a path.
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('TRUDLC_PACK_FIRST', 'pack11')
import drm_reloc as R
from drm import cdrm_decode, sections_with_data

NODE = {0: 'TimeIn', 1: 'Indirect', 2: 'Wave', 3: 'Stream', 4: 'Assign', 5: 'Envelope', 6: 'List', 7: 'MatList',
        8: 'Type8', 9: 'Reaction', 10: 'Sequence', 11: 'Overlap', 12: 'Effect', 13: 'Oscillator'}


def load(spec, en):
    if os.path.isfile(spec):
        raw = open(spec, 'rb').read()
    else:
        from convert_dlc import raw_dlc
        raw, _ = raw_dlc(spec)
        if raw is None: sys.exit('not found in the Xbox packs: ' + spec)
    return sections_with_data(cdrm_decode(raw, en), en)[1]


def xma_info(riff):
    """RIFF chunks; XMA1 fmt (0x165) LoopCount + per stream LoopStart / LoopEnd (both byte orders tried)"""
    out = {}
    p = 12
    while p + 8 <= len(riff):
        cid = riff[p:p + 4]
        szl = struct.unpack_from('<I', riff, p + 4)[0]; szb = struct.unpack_from('>I', riff, p + 4)[0]
        sz = szl if szl <= len(riff) else szb
        body = riff[p + 8:p + 8 + sz]
        out.setdefault('chunks', []).append(cid.decode('latin-1'))
        if cid == b'fmt ':
            for e in '<>':
                tag = struct.unpack_from(e + 'H', body, 0)[0]
                if tag == 0x165:
                    ns = struct.unpack_from(e + 'H', body, 8)[0]; lc = body[10]
                    st = [struct.unpack_from(e + 'IIII', body, 12 + 20 * k) for k in range(min(ns, 4))]
                    out['fmt'] = dict(endian=e, streams=ns, loopcount=lc, loops=[(s[2], s[3]) for s in st],
                                      rate=[s[1] for s in st])
                    break
            else:
                out['fmt_raw'] = body[:24].hex()
        if cid == b'smpl': out['smpl'] = body[:60].hex()
        p += 8 + sz + (sz & 1)
    return out


def fsb_info(d):
    f = d[16:]
    if f[:4] != b'FSB4': return None
    shsz = struct.unpack_from('<I', f, 8)[0]
    h = f[0x30:0x30 + shsz]
    length, comp, ls, le, smode = struct.unpack_from('<IIIII', h, 32)
    return dict(length=length, ls=ls, le=le, smode=smode)


def waves(xs, ps):
    xw = {s['id']: s for s in xs if s['type'] == 6}
    pw = {s['id']: s for s in ps if s['type'] == 6}
    print('Xbox waves', len(xw), 'PC waves', len(pw))
    stat = collections.Counter()
    for i, s in sorted(xw.items()):
        d = s['data']
        pre = struct.unpack_from('>IIII', d, 0)
        xi = xma_info(d[16:]) if d[16:20] == b'RIFF' else {}
        fm = xi.get('fmt', {})
        print('X %6d pre %s loopcount %s loops %s chunks %s %s' % (i, pre, fm.get('loopcount'), fm.get('loops'),
              xi.get('chunks'), ('smpl ' + xi['smpl']) if 'smpl' in xi else ''))
        stat['x_pre2_%d' % pre[2]] += 1; stat['x_loopcount_%s' % fm.get('loopcount')] += 1
    for i, s in sorted(pw.items()):
        d = s['data']
        pre = struct.unpack_from('<IIII', d, 0)
        fi = fsb_info(d)
        print('P %6d pre %s fsb %s' % (i, pre, fi))
        stat['p_pre2_%d' % pre[2]] += 1
        if fi: stat['p_smode_%#x' % fi['smode']] += 1
    print(dict(stat))


# ------------------------------------------------------------------------------------------- anim event lists
def walk(d, e):
    if len(d) < 8 or bytes(d[:4]) != b'\0\0\0\0': return None
    f = '>' if e == 'be' else '<'
    a = 4; recs = []
    while a + 4 <= len(d):
        h, fr = struct.unpack_from(f + 'Hh', d, a)
        if h == 0xffff: return recs if recs else None
        sz = (h >> 12) * 4 + 8
        if fr < 0 or not 1 <= (h >> 12) <= 8 or a + sz > len(d): return None
        recs.append((a, h, fr, sz)); a += sz
    return None


class XWorld:
    """Xbox sections by (type, id) from the section indexes work/idx_xbox_base.json + work/idx_dlc.json (TitleUpdate
    and the DLC packs first); DRMs are read lazily from the archives (read-only)."""
    ORDER = ('TitleUpdate', 'pack11', 'pack10', 'layer2', 'layer1', 'pack1', 'pack2', 'pack20')

    def __init__(self):
        import json
        W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work')
        self.where = collections.defaultdict(list)
        for fn in ('idx_xbox_base.json', 'idx_dlc.json'):
            p = os.path.join(W, fn)
            if not os.path.exists(p): continue
            for rec in json.load(open(p)):
                if not isinstance(rec[5], list): continue
                for t, i, *_ in rec[5]:
                    if t in (6, 7): self.where[t, i].append((rec[0], rec[1]))
        self.arch = {}; self.drms = {}

    def _rank(self, path):
        for k, n in enumerate(self.ORDER):
            if n in path: return k
        return 99

    def section(self, t, i):
        """(secs, k) of the first DRM holding (t, i), or None"""
        locs = sorted(self.where.get((t, i), []), key=lambda pi: self._rank(pi[0]))
        for path, ent in locs[:3]:
            key = (path, ent)
            if key not in self.drms:
                try:
                    from archive import Archive
                    if path not in self.arch: self.arch[path] = Archive(path, 'be')
                    raw = self.arch[path].read(self.arch[path].idx[ent])
                    self.drms[key] = sections_with_data(cdrm_decode(raw, 'be'), 'be')[1]
                except Exception as ex:
                    self.drms[key] = None
            secs = self.drms[key]
            if not secs: continue
            for k, s in enumerate(secs):
                if s['type'] == t and s['id'] == i: return secs, k
        return None


XW = None


class EnvRef:
    """Envelope node data (0x590ce0): D {+0 ptr child node, +4 u32 COUNT, +8 ptr -> COUNT ptrs to C};
    C {+0 u16 parameter index, +2 u16 flag, +4 ptr -> K}; K {+0 s32 (< 0 with C+2 != 0 on every curve keeps the
    'sustain' byte [obj+0x24] = 1), +4 f32 start value, +8 u32 N, +0xc N points x 12 bytes (+8 u8 flags bit0/bit1)}"""
    def __init__(self, pl, k, dp): self.pl, self.k, self.dp = pl, k, dp
    def __str__(self): return ''

    def words(self):
        """[(label, offset, 4 raw bytes)] in the file's own byte order"""
        pl, k = self.pl, self.k
        d = pl.secs[k]['data']; it = dict(pl.r(k).internal)
        out = []
        def w(lab, o):
            if 0 <= o and o + 4 <= len(d): out.append((lab, o, d[o:o + 4]))
        w('D+4 count', self.dp + 4)
        n = pl.u32(k, self.dp + 4) or 0
        arr = it.get(self.dp + 8)
        if arr is None or n > 64: return out
        for c in range(n):
            cp = it.get(arr + 4 * c)
            if cp is None: continue
            w('C%d+0 u16 param, u16 flag' % c, cp)
            kp = it.get(cp + 4)
            if kp is None: continue
            w('K%d+0 s32' % c, kp); w('K%d+4 f32 start' % c, kp + 4); w('K%d+8 u32 N' % c, kp + 8)
            npt = pl.u32(k, kp + 8) or 0
            for q in range(min(npt, 32)):
                for j in range(3):
                    w('K%d pt%d +%d' % (c, q, 4 * j), kp + 0xc + 12 * q + 4 * j)
        return out


def word_class(xw, pw):
    if xw[::-1] == pw: return 'u32'
    if xw[1::-1] + xw[:1:-1] == pw: return 'u16pair'
    if xw == pw: return 'raw'
    if xw[:2] + xw[:1:-1] == pw: return 'u8u8u16'
    return 'other'


def xworld():
    global XW
    if XW is None: XW = XWorld()
    return XW


def wave_is_loop_x(d):
    """Xbox wave section payload -> (loop, text). pre-header [rate, loop start, loop end, pre3]; loop end != 0
    goes with XMA LoopCount 255 on every DLC wave seen (doppelganger_casual: 15 / 15)"""
    pre = struct.unpack_from('>IIII', d, 0)
    fm = xma_info(d[16:]).get('fmt', {}) if d[16:20] == b'RIFF' else {}
    lc = fm.get('loopcount')
    return (pre[2] != 0 or lc == 255), 'pre %s xma loopcount %s' % (pre, lc)


class Plex:
    """SoundPlex tree reader on one file (by section index + offset); follows internal relocs and type-1 ids
    (Xbox side: ids missing in the file are looked up in the whole Xbox game + DLC through XWorld)"""
    def __init__(self, secs, en):
        self.secs = secs; self.en = en; self.f = '>' if en == 'be' else '<'
        self.rel = {}
        self.by_id = collections.defaultdict(list)
        for k, s in enumerate(secs):
            self.by_id[s['type'], s['id']].append(k)
        self.waves = {s['id']: s for s in secs if s['type'] == 6}
        self.sub = {}                  # (t, id) -> Plex of the DRM that holds it (Xbox world)

    def resolve(self, t, i):
        """(plex, k) for section (t, i): this file first, then (Xbox only) the world"""
        ks = self.by_id.get((t, i))
        if ks: return self, ks[0]
        if self.en != 'be': return None
        if (t, i) not in self.sub:
            r = xworld().section(t, i)
            self.sub[t, i] = (Plex(r[0], 'be'), r[1]) if r else None
        return self.sub[t, i]

    def wave_loop(self, wid):
        r = self.resolve(6, wid)
        if r is None: return None, 'wave %s not found' % wid
        pl, k = r
        d = pl.secs[k]['data']
        if self.en == 'be':
            lp, txt = wave_is_loop_x(d)
            return lp, txt + ('' if pl is self else ' (other DRM)')
        pre = struct.unpack_from('<IIII', d, 0)
        fi = fsb_info(d)
        return pre[2] != 0, 'pre %s fsb smode %s' % (pre, hex(fi['smode']) if fi else None)

    def r(self, k):
        if k not in self.rel:
            self.rel[k] = R.parse(self.secs[k]['reloc'], self.en)
        return self.rel[k]

    def u32(self, k, o):
        d = self.secs[k]['data']
        return struct.unpack_from(self.f + 'I', d, o)[0] if 0 <= o and o + 4 <= len(d) else None

    def tree(self, k, node, depth=0, seen=None, ext=None):
        """[(depth, type, data_off, extra)] of the plex rooted at node offset `node` of section k"""
        seen = set() if seen is None else seen
        if (k, node) in seen or depth > 40: return []
        seen.add((k, node))
        it = dict(self.r(k).internal)
        t = self.u32(k, node)
        if t is None or t > 13: return [(depth, 'bad_type', node, t)]
        dp = it.get(node + 4)
        out = [(depth, t, dp, None)]
        if dp is None: return out
        if t == 1:
            pid = self.u32(k, dp)
            r = self.resolve(7, pid)
            out[-1] = (depth, t, dp, 'id %s%s' % (pid, '' if r is None or r[0] is self else ' ext'))
            if r:
                out += r[0].tree(r[1], 0, depth + 1, seen if r[0] is self else None)
            else:
                out.append((depth + 1, 'missing', None, pid))
            return out
        if t == 2:
            wid = self.u32(k, dp)
            if dp in set(self.r(k).pointer_offsets()) or wid == 0xbeebbeeb:
                out[-1] = (depth, 'not_a_wave', dp, None)
                return out
            lp, txt = self.wave_loop(wid)
            out[-1] = (depth, t, dp, (wid, lp, txt))
            return out
        if t == 5:
            out[-1] = (depth, t, dp, EnvRef(self, k, dp))
        # every pointer inside the data record that points at a node {type <= 13, ptr} -> child
        d = self.secs[k]['data']
        # data record extent: up to the next pointer target after dp (conservative 0x60)
        for o in range(dp, min(dp + 0x60, len(d)), 4):
            tg = it.get(o)
            if tg is None: continue
            tt = self.u32(k, tg)
            if tt is not None and tt <= 13 and (tg + 4) in it:
                out += self.tree(k, tg, depth + 1, seen)
            else:
                # pointer to an array of node pointers / nodes (lists, sequences)
                for q in range(tg, min(tg + 0x100, len(d)), 4):
                    t2 = it.get(q)
                    if t2 is None:
                        tq = self.u32(k, q)
                        if q > tg + 8 and tq is not None and tq > 13: break
                        continue
                    t3 = self.u32(k, t2)
                    if t3 is not None and t3 <= 13 and (t2 + 4) in it:
                        out += self.tree(k, t2, depth + 1, seen)
        return out


def wave_loop(ws, wid, en):
    s = ws.get(wid)
    if s is None: return 'wave %s not in file' % wid
    d = s['data']
    if en == 'be':
        pre = struct.unpack_from('>IIII', d, 0)
        fm = xma_info(d[16:]).get('fmt', {}) if d[16:20] == b'RIFF' else {}
        return 'pre %s xma loopcount %s loops %s' % (pre, fm.get('loopcount'), fm.get('loops'))
    pre = struct.unpack_from('<IIII', d, 0)
    fi = fsb_info(d)
    return 'pre %s fsb smode %s ls %s le %s len %s' % (pre, hex(fi['smode']) if fi else None, fi and fi['ls'],
                                                      fi and fi['le'], fi and fi['length'])


def events(xs, ps, show_all):
    X = Plex(xs, 'be'); P = Plex(ps, 'le')
    pidx = collections.defaultdict(list)
    for k, s in enumerate(ps):
        if s['type'] == 7: pidx[s['id']].append(k)
    xcopy = collections.Counter()
    n_lists = n_snd = 0
    psig = None
    for k, s in enumerate(xs):
        if s['type'] != 7 or s['data'] is None: continue
        w = walk(s['data'], 'be')
        if w is None: continue
        c = xcopy[s['id']]; xcopy[s['id']] += 1
        pk = pidx.get(s['id'], [])
        pk = pk[c] if c < len(pk) else None
        if pk is None:
            # base ids are renumbered on PC: unique PC list with the same record layout (offset, h, frame)
            sig = [(a, h, fr) for a, h, fr, _ in w]
            if psig is None:
                psig = collections.defaultdict(list)
                for q, ss in enumerate(ps):
                    if ss['type'] != 7: continue
                    pw0 = walk(ss['data'], 'le')
                    if pw0: psig[tuple((a, h, fr) for a, h, fr, _ in pw0), len(ss['data'])].append(q)
            cand = psig.get((tuple(sig), len(s['data'])), [])
            if len(cand) == 1: pk = cand[0]; STATS['paired_by_layout'] += 1
            else: STATS['unpaired_lists'] += 1
        n_lists += 1
        it = dict(X.r(k).internal)
        pw = walk(ps[pk]['data'], 'le') if pk is not None else None
        pit = dict(P.r(pk).internal) if pk is not None else {}
        for a, h, fr, sz in w:
            if (h & 3) != 0 or (h >> 12) < 2: continue
            pay = s['data'][a + 8:a + sz]
            if pay[0] not in (0, 1): continue
            n_snd += 1
            ppay = ps[pk]['data'][a + 8:a + sz] if pk is not None and a + sz <= len(ps[pk]['data']) else b''
            line = 'DTP %d list@%d rec %#x h %04x frame %d kind0 byte0 %d byte1 X %#04x PC %s' % (
                s['id'], k, a, h, fr, pay[0], pay[1], ('%#04x' % ppay[1]) if len(ppay) > 1 else '-')
            listbit_x = pay[1] & 1
            listbit_p = (ppay[1] & 1) if len(ppay) > 1 else None
            info = []
            loops = False; ploops = None; unknown = 0
            def fmt(tr):
                return ' '.join('%s%s%s' % ('.' * dd, NODE.get(t, t), '' if ex is None else
                                            '(%s)' % (('w%d%s' % (ex[0], ' LOOP' if ex[1] else '' if ex[1] is not None else ' ?'))
                                                      if t == 2 else ex)) for dd, t, _, ex in tr)
            def loopset(tr):
                lp = [ex for dd, t, _, ex in tr if t == 2]
                return [e for e in lp if e[1]], [e for e in lp if e[1] is None], sum(1 for dd, t, _, ex in tr if t == 3)
            xroot = proot = None
            if pay[0] == 0:
                node = it.get(a + 12)
                if node is not None: xroot = (X, k, node)
                pnode = pit.get(a + 12)
                if pk is not None and pnode is not None: proot = (P, pk, pnode)
            else:
                sid = struct.unpack_from('>I', pay, 8)[0] if len(pay) >= 12 else None
                r = X.resolve(7, sid) if sid is not None else None
                if r: xroot = (r[0], r[1], 0)
                info.append('X sound-by-id %s%s' % (sid, '' if r else ' (not found)'))
                if len(ppay) >= 12:
                    psid = struct.unpack_from('<I', ppay, 8)[0]
                    r = P.resolve(7, psid)
                    if r: proot = (r[0], r[1], 0)
                    info.append('PC sound-by-id %s%s' % (psid, '' if r else ' (not in the PC file)'))
            if xroot:
                pl, kk, nd = xroot
                tr = pl.tree(kk, nd)
                lw, uw, nst = loopset(tr)
                loops = bool(lw); unknown = len(uw)
                info.append('X plex id %s: %s' % (pl.u32(kk, nd + 8) if pay[0] == 0 else '-', fmt(tr)))
                for e in lw: info.append('  X loop wave %d: %s' % (e[0], e[2]))
                if nst: info.append('  X streams in the tree: %d (loop flag not decoded)' % nst)
            if proot:
                pl, kk, nd = proot
                tr = pl.tree(kk, nd)
                lw, uw, nst = loopset(tr)
                ploops = bool(lw)
                info.append('PC plex: %s' % fmt(tr))
                for e in lw: info.append('  PC loop wave %d: %s' % (e[0], e[2]))
            if (loops or ploops) and xroot and proot:
                xe = [ex for dd, t, _, ex in xroot[0].tree(xroot[1], xroot[2]) if t == 5]
                pe = [ex for dd, t, _, ex in proot[0].tree(proot[1], proot[2]) if t == 5]
                info.append('  envelopes X %d PC %d' % (len(xe), len(pe)))
                for q, (ex, ep) in enumerate(zip(xe, pe)):
                    xw = ex.words(); pw = {lab: b for lab, o, b in ep.words()}
                    for lab, o, b in xw:
                        p = pw.get(lab)
                        cl = word_class(b, p) if p is not None else 'missing'
                        STATS['env_' + cl] += 1
                        fx = struct.unpack('>f', b)[0]; ix = struct.unpack('>i', b)[0]
                        fp = struct.unpack('<f', p)[0] if p else float('nan'); ip = struct.unpack('<i', p)[0] if p else 0
                        info.append('    env%d %-28s X %s (i %d f %.6g)  PC %s (i %d f %.6g)  %s' % (
                            q, lab, b.hex(), ix, fx, p.hex() if p else '-', ip, fp, cl))
            diff = ppay and (pay[:2] != ppay[:2])
            if show_all or loops or diff or listbit_x != listbit_p or (ploops and not loops):
                STATS['printed'] += 1
                print(line, 'listbit X %d PC %s' % (listbit_x, listbit_p), 'LOOP' if loops else '',
                      'PC_LOOP' if ploops else '', 'BYTE01_DIFF' if diff else '', ('unresolved_waves %d' % unknown) if unknown else '')
                for q in info: print('   ', q)
            STATS['loop_x'] += loops; STATS['loop_pc'] += bool(ploops); STATS['listbit_x'] += listbit_x
            STATS['byte01_diff'] += bool(diff); STATS['unresolved_waves'] += unknown
            STATS['byte0_%d' % pay[0]] += 1
    print('lists', n_lists, 'sound events', n_snd, dict(STATS))


STATS = collections.Counter()


def pcloops(ps):
    """PC file only: every anim-event sound whose SoundPlex (resolved inside the file) reaches a looping wave"""
    P = Plex(ps, 'le'); n = 0; hits = 0
    for k, s in enumerate(ps):
        if s['type'] != 7: continue
        w = walk(s['data'], 'le')
        if not w: continue
        it = dict(P.r(k).internal)
        for a, h, fr, sz in w:
            if (h & 3) != 0 or (h >> 12) < 2: continue
            pay = s['data'][a + 8:a + sz]
            if pay[0] not in (0, 1): continue
            n += 1
            if pay[0] == 0:
                nd = it.get(a + 12)
                if nd is None: continue
                tr = P.tree(k, nd)
            else:
                if len(pay) < 12: continue
                r = P.resolve(7, struct.unpack_from('<I', pay, 8)[0])
                if not r: continue
                tr = r[0].tree(r[1], 0)
            lw = [ex[0] for dd, t, _, ex in tr if t == 2 and ex[1]]
            if lw:
                hits += 1
                print('PC DTP %d rec %#x h %04x frame %d byte0 %d byte1 %#04x listbit %d loop waves %s' % (
                    s['id'], a, h, fr, pay[0], pay[1], pay[1] & 1, lw))
    print('PC sound events', n, 'with a looping wave', hits)


def animmap(secs, en, want=None):
    """{event list DTP id: [(table DTP, offset, anim id)]}: table entries {u32 list id, ptr, u16 anim, u16 0xffff}
    (state chart 20212 of doppelganger_casual +0x3c0.. holds them; anim id = Animation section id)"""
    f = '>' if en == 'be' else '<'
    lists = {s['id'] for s in secs if s['type'] == 7 and walk(s['data'], en)}
    out = collections.defaultdict(list)
    for s in secs:
        if s['type'] != 7: continue
        d = s['data']; ptrs = set(R.parse(s['reloc'], en).pointer_offsets())
        for o in range(0, len(d) - 11, 4):
            v = struct.unpack_from(f + 'I', d, o)[0]
            if v not in lists or (want and v not in want) or (o + 4) not in ptrs: continue
            a, b = struct.unpack_from(f + 'HH', d, o + 8)
            if b != 0xffff: continue
            out[v].append((s['id'], o, a))
    return out


def where(t, i):
    """Xbox DRMs (base + DLC packs) that hold section (t, i), with names from the yura file lists + DLC name list"""
    import names as N
    nm = {}
    for fn in os.listdir(N.L):
        if 'Underworld' in fn: nm.update(N.load(os.path.join(N.L, fn)))
    dl = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic', 'dlc_names.txt')
    if os.path.exists(dl):
        for l in open(dl, encoding='utf8', errors='ignore'):
            l = l.strip()
            if l:
                for pre in ('xenon-w\\', ''):
                    nm[N.crc(pre + l)] = l
    import json
    W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work')
    for fn in ('idx_xbox_base.json', 'idx_dlc.json'):
        for rec in json.load(open(os.path.join(W, fn))):
            if isinstance(rec[5], list) and any(s[0] == t and s[1] == i for s in rec[5]):
                print('%-60s entry %5d  %s' % (os.path.basename(rec[0]), rec[1], nm.get(rec[2], '#%08x' % rec[2])))


if __name__ == '__main__':
    if len(sys.argv) >= 4 and sys.argv[1] == 'where':
        where(int(sys.argv[2]), int(sys.argv[3])); sys.exit()
    if len(sys.argv) < 4: sys.exit(__doc__)
    cmd, xn, pn = sys.argv[1:4]
    xs = load(xn, 'be'); ps = load(pn, 'le')
    if cmd == 'pair':
        # pair XBOX_NAME PC.drm SECTION_ID OFF LEN [TYPE]: Xbox and PC words side by side (u32 BE / LE)
        sid, off, ln = int(sys.argv[4]), int(sys.argv[5], 16), int(sys.argv[6], 16)
        typ = int(sys.argv[7]) if len(sys.argv) > 7 else 7
        xsec = [s for s in xs if s['type'] == typ and s['id'] == sid]
        psec = [s for s in ps if s['type'] == typ and s['id'] == sid]
        print('Xbox copies', len(xsec), 'PC copies', len(psec), 'sizes', [len(s['data']) for s in xsec], [len(s['data']) for s in psec])
        if xsec and psec:
            xd, pd = xsec[0]['data'], psec[0]['data']
            xi = dict(R.parse(xsec[0]['reloc'], 'be').internal); pi = dict(R.parse(psec[0]['reloc'], 'le').internal)
            for o in range(off, min(off + ln, len(xd), len(pd)), 4):
                xw = xd[o:o + 4]; pw = pd[o:o + 4]
                same = 'same' if xw[::-1] == pw else ('raw' if xw == pw else 'DIFF')
                print('+%#07x  X %s (%10d | %5d %5d)%s  PC %s (%10d | %5d %5d)%s  %s' % (
                    o, xw.hex(), struct.unpack('>I', xw)[0], *struct.unpack('>HH', xw), (' ->%#x' % xi[o]) if o in xi else '',
                    pw.hex(), struct.unpack('<I', pw)[0], *struct.unpack('<HH', pw)[::-1], (' ->%#x' % pi[o]) if o in pi else '', same))
    elif cmd == 'animmap':
        # animmap XBOX_NAME PC.drm [LIST_ID,..]: which anim each event list belongs to, Xbox vs PC
        want = set(int(v) for v in sys.argv[4].split(',')) if len(sys.argv) > 4 else None
        mx = animmap(xs, 'be', want); mp = animmap(ps, 'le', want)
        nd = 0
        for v in sorted(set(mx) | set(mp)):
            a, b = sorted(mx.get(v, [])), sorted(mp.get(v, []))
            if want or a != b:
                print('list %d  X %s  PC %s %s' % (v, a, b, '' if a == b else 'DIFF'))
            nd += a != b
        print('event lists in tables X %d PC %d, differing %d' % (len(mx), len(mp), nd))
    elif cmd == 'pcloops': pcloops(ps)
    elif cmd == 'waves': waves(xs, ps)
    elif cmd == 'events': events(xs, ps, '--all' in sys.argv)
    else: sys.exit(__doc__)
