"""TruXenia - menu + link for the Xbox side in Xenia (TODO N18 / N20 "Kampf wie Xbox"): shows enemy and Lara values of
a running Xenia (Tomb Raider: Underworld with the title update), writes a hit log in the same layout as TruMenu's
`combo.trace` on PC, serves a small command link for scripts (like TruLink on PC) and keeps a library of named Xbox
saves. Mostly read only; value writes exist but are LOCKED by default.

Memory access as tools/xenia_combat_sampler.py: OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION),
ReadProcessMemory only - no debugger, no suspend. Guest address A = host base + A (base found by the MZ header at
base + 0x82000000). TU addresses and their proof words: docs/data/xenia_tu_combat_addresses.json; every proof word is
compared before reading (refuses on a mismatch). Fields marked "proven": false are shown as '?' unless --unproven
(then marked '~').

Usage (from the repository root):
  ../bin/pyt -t 0 tools/truxenia.py                    GUI + link (127.0.0.1:47011) against the running Xenia
  ../bin/pyt -t 0 tools/truxenia.py --nogui            link only (stop with Ctrl+C or the link command `quit`)
  ../bin/pyt -t 60 tools/truxenia.py --check           proof words only
  ../bin/pyt -t 60 tools/truxenia.py --once            one snapshot to the console
  ../bin/pyt -t 60 tools/truxenia.py --dumpfile work/xenia_dump/tu_image_82000000.bin --check|--once
  ../bin/pyt -t 120 tools/truxenia.py --selftest       offline test with a simulated guest memory (hit log, link,
                                                       save library dry run) - no Xenia needed
Options: --port N, --log PATH (default ../logs/truxenia/truxenia_<time>.log), --hitlog PATH (default next to the log),
  --unproven, --allow-write (unlocks `set` after a confirmation), --lang de|en, --verbose, --debug, --trace.
Link commands (tools/truxenia_cmd.py): status | enemies | lara | snapshot <file> | watch <seconds> <file> |
  hits [n] | saves | set <inst> lp|stamina <value> | quit
Exit codes: 0 ok, 1 proof mismatch / no Xenia, 2 usage.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import shutil
import socket
import struct
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xenia_combat_sampler as S  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))          # the workspace (parent of the clone)
ADDR_FILE = os.path.join(HERE, '..', 'docs', 'data', 'xenia_tu_combat_addresses.json')
SAVE_LIB = os.path.join(ROOT, '_archiv', 'xenia-saves')
XENIA_CONTENT = os.path.join(ROOT, 'bin', 'xenia-canary', 'content')
TITLE = '534307EC'
DEFAULT_PORT = 47011
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
HIT_WINDOW = 0.5                       # seconds after an LP drop in which the first state change is the reaction
PATH_WINDOW = 2.0                      # Lara's records within this time before a hit = the combo path (as TruMenu)

T = {
    'title': ('TruXenia - Xbox-Werte', 'TruXenia - Xbox values'),
    'enemies': ('Gegner', 'Enemies'), 'lara': ('Lara', 'Lara'), 'loglink': ('Log / Link', 'Log / Link'),
    'saves': ('Spielstände', 'Saves'), 'name': ('Name', 'Name'), 'lp': ('LP', 'LP'), 'stamina': ('Stamina', 'Stamina'),
    'state0': ('Zustand 0', 'State 0'), 'state1': ('Zustand 1', 'State 1'), 'req': ('Soll', 'Requested'),
    'target': ('Ziel', 'Target'), 'dist': ('Abstand', 'Distance'), 'ko': ('Ko', 'Ko'),
    'records': ('Kombo-Datensätze', 'Combo records'), 'meter': ('Schattenleiste', 'Shadow meter'),
    'active': ('aktiv', 'active'), 'scale': ('Zeitskala', 'Time scale'), 'dopp': ('Doppelgängerin', 'Doppelganger'),
    'pos': ('Position', 'Position'), 'xenia': ('Xenia', 'Xenia'), 'link': ('Link', 'Link'),
    'watch': ('Mitschnitt', 'Recording'), 'start': ('Start', 'Start'), 'stop': ('Stopp', 'Stop'),
    'store': ('Aktuelle Stände ablegen als ...', 'Store current saves as ...'),
    'restore': ('Ausgewählten zurückkopieren', 'Restore selected'),
    'unproven': ('unbelegte Felder zeigen (~)', 'show unproven fields (~)'),
    'hits': ('Treffer', 'Hits'), 'running': ('läuft', 'running'), 'notrun': ('läuft nicht', 'not running'),
    'needclosed': ('Xenia muss geschlossen sein', 'Xenia must be closed'),
    'writelocked': ('Schreiben gesperrt', 'writing locked'),
}


def tr(key, lang):
    return T[key][0 if lang == 'de' else 1]


def now_ts():
    t = time.time()
    return time.strftime('%H:%M:%S', time.localtime(t)) + '.%03d' % int((t % 1) * 1000)


# ---------------------------------------------------------------------------------------------------------- memory
class FakeMem:
    """--selftest: a small simulated guest memory with the TU layout (two thralls, Lara, meter, trackers)"""

    def __init__(self, A, log):
        self.A, self.log, self.pid, self.base = A, log, 0, 0
        self.mem = {}
        self.t0 = time.time()
        for sec, v in A.items():                       # proof words
            if isinstance(v, dict):
                for a, w in v.get('proof', {}).items():
                    self.w32(S.h(a), S.h(w))
        il, ob, br = A['instance_list'], A['object'], A['brain']
        self.states = {'idle': 0x40001000, 'melee': 0x40001100, 'hit': 0x40001200, 'stepidle': 0x40001300}
        for nm, a in (('CombatIdle', 0x40001000), ('MeleeAttack', 0x40001100), ('HitReaction', 0x40001200),
                      ('CombatStepIdle', 0x40001300)):
            self.wstr(a + 0x40, nm)
            self.w32(a + 8, a + 0x40)
        self.insts = []
        prev = S.h(il['head'])
        for i, (name, oid) in enumerate((('viking_thrall_tutorial_dlc2_', 1004), ('viking_thrall_dlc2_', 927))):
            inst = 0x41000000 + i * 0x1000
            self.w32(prev, inst) if i == 0 else self.w32(prev + S.h(il['next_offset']), inst)
            prev = inst
            obj, holder, h0, brain = inst + 0x800, inst + 0x900, inst + 0x940, 0x42000000 + i * 0x10000
            self.w32(inst + S.h(ob['instance_object_offset']), obj)
            self.w32(obj + S.h(ob['object_id_offset']), oid)
            self.w32(obj + S.h(ob['object_name_ptr_offset']), inst + 0xc00)   # name outside obj / holder
            self.wstr(inst + 0xc00, name)
            self.w32(inst + 0x2d0, holder); self.w32(holder, h0); self.w32(h0 + 0x2ec, brain)
            self.wf(brain + S.h(br['lp']), 500.0); self.wf(brain + S.h(br['stamina']), 40.0)
            self.w32(brain + S.h(br['state_layer0']), self.states['stepidle'])
            self.w32(brain + 0x18f8, 0)
            self.wf(inst + 0x20, 100.0 * i); self.wf(inst + 0x24, 0.0); self.wf(inst + 0x28, 0.0)
            self.insts.append((inst, brain))
        self.w32(S.h(il['struct']), 2)
        self.w32(prev + S.h(il['next_offset']), 0)                      # end of the instance list
        # Lara: player tracker, chart machines, meter; game tracker
        trk, mac0, mac1, meter, lara = 0x43000000, 0x43100000, 0x43200000, 0x43300000, 0x43400000
        lc, pt, gt = A['lara_chart'], A['player_tracker'], A['game_tracker']
        self.w32(S.h(lc['player_tracker_ptr']), trk)
        self.w32(trk + S.h(lc['machine0_offset']), mac0); self.w32(trk + S.h(lc['machine1_offset']), mac1)
        self.w32(mac0 + S.h(lc['record_offset']), 1482); self.w32(mac1 + S.h(lc['record_offset']), 0)
        self.w32(trk + S.h(pt['meter_object']), meter)
        self.mem[trk + S.h(pt['doppelganger_flag'])] = 1
        self.w32(meter + 4, 0); self.wf(meter + 8, 1000.0); self.wf(meter + 0xc, 1000.0)
        g = S.h(gt['address'])
        self.w32(g + S.h(gt['player_instance']), lara); self.wf(g + S.h(gt['world_time_scale']), 1.0)
        self.wf(lara + 0x20, 50.0); self.wf(lara + 0x24, 0.0); self.wf(lara + 0x28, 0.0)
        self.mac0, self.meter, self.gt = mac0, meter, g
        self.script = [(0.3, 'rec', 1477), (0.5, 'rec', 1488), (0.6, 'hit', 0, 20.0, 'hit'), (0.9, 'state', 0, 'stepidle'),
                       (1.2, 'rec', 1492), (1.3, 'hit', 0, 20.0, 'melee'), (1.6, 'power', 1), (1.7, 'hit', 1, 95.0, 'hit'),
                       (2.0, 'state', 1, 'stepidle')]
        self.done = 0
        log.w('I', 'selftest memory: 2 thralls, Lara, meter, trackers (%d proof words)' % len(self.mem))

    def w32(self, a, v):
        for i, b in enumerate(struct.pack('>I', v & 0xffffffff)):
            self.mem[a + i] = b

    def wf(self, a, f):
        for i, b in enumerate(struct.pack('>f', f)):
            self.mem[a + i] = b

    def wstr(self, a, s):
        for i, b in enumerate(s.encode('ascii') + b'\0'):
            self.mem[a + i] = b

    def tick(self):
        t = time.time() - self.t0
        while self.done < len(self.script) and self.script[self.done][0] <= t:
            ev = self.script[self.done]
            if ev[1] == 'rec':
                self.w32(self.mac0 + 0x520, ev[2])
            elif ev[1] == 'hit':
                inst, brain = self.insts[ev[2]]
                lp = struct.unpack('>f', self.read(brain + 0x2c64, 4))[0]
                self.wf(brain + 0x2c64, lp - ev[3])
                self.w32(brain + 0x125c, self.states[ev[4]])
            elif ev[1] == 'state':
                self.w32(self.insts[ev[2]][1] + 0x125c, self.states[ev[3]])
            elif ev[1] == 'power':
                self.w32(self.meter + 4, ev[2]); self.wf(self.gt + 0x118, 0.3)
            self.done += 1

    def read(self, guest, n):
        if not guest or guest not in self.mem:
            return None
        return bytes(self.mem.get(guest + i, 0) for i in range(n))      # like real memory past a string's end

    def alive(self):
        return True


class Writer:
    """value writes (LOCKED unless --allow-write and confirmed): OpenProcess with VM_WRITE only then; data words only"""

    def __init__(self, mem, log):
        self.mem, self.log, self.hp = mem, log, None

    def open(self):
        if self.hp or not getattr(self.mem, 'pid', 0):
            return bool(self.hp)
        k = self.mem.k
        k.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.POINTER(ctypes.c_size_t)]
        self.hp = k.OpenProcess(PROCESS_VM_WRITE | PROCESS_VM_OPERATION, False, self.mem.pid)
        if not self.hp:
            self.log.w('E', 'OpenProcess for writing refused (error %d)' % ctypes.get_last_error())
        return bool(self.hp)

    def write_f32(self, guest, value):
        data = struct.pack('>f', value)
        if isinstance(self.mem, FakeMem):
            for i, b in enumerate(data):
                self.mem.mem[guest + i] = b
        else:
            if not self.open():
                return False, 'open refused'
            got = ctypes.c_size_t(0)
            ok = self.mem.k.WriteProcessMemory(self.hp, ctypes.c_void_p(self.mem.base + guest), data, 4, ctypes.byref(got))
            if not ok or got.value != 4:
                return False, 'WriteProcessMemory failed (error %d)' % ctypes.get_last_error()
        back = S.f32(self.mem, guest)
        return (back is not None and abs(back - value) < 1e-3), 'read back %s' % back


# ---------------------------------------------------------------------------------------------------------- model
class Model:
    def __init__(self, mem, A, log, unproven=False):
        self.mem, self.A, self.log = mem, A, log
        self.unproven = unproven
        self.lock = threading.Lock()
        self.snap = {'time': '', 'enemies': [], 'lara': {}}
        self.prev = {}                                # inst -> (lp, stamina, state0)
        self.pending = {}                             # inst -> open hit
        self.hits = []                                # finished hit lines (dicts)
        self.recs = []                                # (time, record) of machine 0
        self.hitlog = None
        self.watch = None
        self.ko = '?'

    # -- reads
    def _state_name(self, so):
        if not so:
            return '-'
        nm = S.cstr(self.mem, S.u32(self.mem, so + S.h(self.A['brain']['state_name_offset'])))
        return nm or '0x%08x' % so

    def _maybe(self, sec, key, fn):
        """read an extended field: proven -> value, unproven -> '?' or ('~', value)"""
        f = self.A[sec][key]
        if f.get('proven'):
            return fn(S.h(f['offset']))
        if not self.unproven:
            return '?'
        v = fn(S.h(f['offset']))
        return '~%s' % (v,)

    def _vec(self, a):
        b = self.mem.read(a, 12)
        return struct.unpack('>3f', b) if b else None

    def sample(self):
        m, A = self.mem, self.A
        if isinstance(m, FakeMem):
            m.tick()
        il, ob, br = A['instance_list'], A['object'], A['brain']
        gt, pt, me, lc = A['game_tracker'], A['player_tracker'], A['meter'], A['lara_chart']
        g = S.h(gt['address'])
        lara_inst = S.u32(m, g + S.h(gt['player_instance']))
        lpos = self._vec(lara_inst + 0x20) if (lara_inst and (A['instance_ext']['position']['proven'] or self.unproven)) else None
        enemies = []
        inst = S.u32(m, S.h(il['head']))
        seen = set()
        while inst and inst not in seen and len(seen) < S.MAX_INST:
            seen.add(inst)
            holder = S.u32(m, inst + 0x2d0)
            h0 = S.u32(m, holder) if holder else None
            brain = S.u32(m, h0 + 0x2ec) if h0 else None
            if brain:
                obj = S.u32(m, inst + S.h(ob['instance_object_offset']))
                oid = S.u32(m, obj + S.h(ob['object_id_offset'])) if obj else None
                name = S.cstr(m, S.u32(m, obj + S.h(ob['object_name_ptr_offset']))) if obj else None
                e = {'inst': inst, 'oid': oid, 'name': name or '?', 'lp': S.f32(m, brain + S.h(br['lp'])),
                     'stamina': S.f32(m, brain + S.h(br['stamina'])),
                     's0': self._state_name(S.u32(m, brain + S.h(br['state_layer0']))),
                     's1': self._state_name(S.u32(m, brain + S.h(br['state_layer1'])))}
                e['req'] = self._maybe('brain_ext', 'requested_state0', lambda o: self._state_name(S.u32(m, brain + o)))
                tg = A['brain_ext']['targeting']
                slot = A['brain_ext']['target_slot']
                if self.unproven:
                    base = brain + S.h(tg['offset']) + S.h(slot['offset'])
                    mode = S.u32(m, base + 4)
                    tinst = S.u32(m, base + 0x20) if mode == 1 else None
                    e['target'] = '~%s' % ('Lara' if tinst and tinst == lara_inst else
                                           ('-' if mode in (None, 0xffffffff) else 'm%d' % mode))
                else:
                    e['target'] = '?'
                e['ko'] = '?'
                pos = self._vec(inst + 0x20) if (A['instance_ext']['position']['proven'] or self.unproven) else None
                if pos and lpos:
                    d = sum((a - b) ** 2 for a, b in zip(pos, lpos)) ** 0.5
                    e['dist'] = ('%.0f' % d) if A['instance_ext']['position']['proven'] else '~%.0f' % d
                else:
                    e['dist'] = '?'
                enemies.append(e)
            inst = S.u32(m, inst + S.h(il['next_offset']))
        trk = S.u32(m, S.h(lc['player_tracker_ptr']))
        recs = []
        for k in ('machine0_offset', 'machine1_offset'):
            mac = S.u32(m, trk + S.h(lc[k])) if trk else None
            r = S.u32(m, mac + S.h(lc['record_offset'])) if mac else None
            recs.append(None if r is None else struct.unpack('>i', struct.pack('>I', r))[0])
        meter = S.u32(m, trk + S.h(pt['meter_object'])) if trk else None
        mflags = S.u32(m, meter + S.h(me['flags'])) if meter else None
        dopp = m.read(trk + S.h(pt['doppelganger_flag']), 1) if trk else None
        lara = {'rec0': recs[0], 'rec1': recs[1], 'meter': S.f32(m, meter + S.h(me['value'])) if meter else None,
                'mflags': mflags, 'active': None if mflags is None else bool(mflags & 1),
                'scale': S.f32(m, g + S.h(gt['world_time_scale'])), 'dopp': None if dopp is None else dopp[0],
                'inst': lara_inst, 'pos': lpos, 'lp': '?', 'states': '?'}
        ts = now_ts()
        with self.lock:
            self.snap = {'time': ts, 'enemies': enemies, 'lara': lara}
            self._hits(ts, enemies, lara)
            if self.watch:
                self.watch.row(ts, enemies, lara)
        return self.snap

    # -- hit log (same text as TruMenu combo.trace, plus Xbox extras)
    def _hits(self, ts, enemies, lara):
        t = time.time()
        if lara['rec0'] is not None and (not self.recs or self.recs[-1][1] != lara['rec0']):
            self.recs.append((t, lara['rec0']))
            self.recs = self.recs[-12:]
        for e in enemies:
            p = self.prev.get(e['inst'])
            if p and e['lp'] is not None and p[0] is not None and e['lp'] < p[0] - 0.01:
                path = '>'.join(str(r) for tt, r in self.recs if t - tt <= PATH_WINDOW)[-60:] or str(lara['rec0'])
                self.pending[e['inst']] = {'t': t, 'ts': ts, 'name': e['name'], 'oid': e['oid'], 'lp0': p[0],
                                           'lp': e['lp'], 'st0': p[1], 'st': e['stamina'], 'hitstate': p[2],
                                           's_after': e['s0'], 'path': path, 'reaction': None,
                                           'dist': e.get('dist', '?'), 'meter': lara['meter'],
                                           'active': lara['active'], 'scale': lara['scale']}
            q = self.pending.get(e['inst'])
            if q:
                if q['reaction'] is None and e['s0'] != q['hitstate'] and e['s0'] != '-':
                    q['reaction'] = e['s0']
                if e['lp'] is not None:
                    q['lp'] = min(q['lp'], e['lp']) if t - q['t'] < 0.05 else q['lp']
                if t - q['t'] >= HIT_WINDOW:
                    self._finish(e['inst'], q)
            self.prev[e['inst']] = (e['lp'], e['stamina'], e['s0'])

    def _finish(self, inst, q):
        del self.pending[inst]
        line = ('%s combo: Lara records %s -> %s %s LP %.1f -> %.1f (-%.1f), stamina %s -> %s, state at the hit %s, '
                'reaction %s | xbox: dist %s, meter %s active %s, time scale %s' % (
                    q['ts'], q['path'], q['name'], q['oid'], q['lp0'], q['lp'], q['lp0'] - q['lp'],
                    S.fmt(q['st0']), S.fmt(q['st']), q['hitstate'], q['reaction'] or '-', q['dist'],
                    S.fmt(q['meter']), q['active'], S.fmt(q['scale'], '%.2f')))
        self.hits.append(line)
        self.hits = self.hits[-500:]
        if self.hitlog:
            self.hitlog.write(line + '\n')
            self.hitlog.flush()
        self.log.w('I', line)


class Watch:
    def __init__(self, path, seconds):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.f = open(path, 'a', encoding='utf-8')
        if self.f.tell() == 0:
            self.f.write('host_time\tinst\tobj_id\tobj_name\tlp\tstamina\tstate0\tstate1\treq\ttarget\tdist\t'
                         'lara_rec0\tlara_rec1\tmeter\tactive\ttime_scale\n')
        self.until = time.time() + seconds
        self.path = path
        self.rows = 0

    def row(self, ts, enemies, lara):
        if time.time() > self.until:
            return
        for e in enemies:
            self.f.write('%s\t0x%08x\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                ts, e['inst'], e['oid'], e['name'], S.fmt(e['lp']), S.fmt(e['stamina'], '%.2f'), e['s0'], e['s1'],
                e['req'], e['target'], e['dist'], lara['rec0'], lara['rec1'], S.fmt(lara['meter']), lara['active'],
                S.fmt(lara['scale'], '%.2f')))
            self.rows += 1
        self.f.flush()

    def done(self):
        return time.time() > self.until


# ---------------------------------------------------------------------------------------------------------- saves
def xenia_running():
    try:
        k = ctypes.WinDLL('kernel32', use_last_error=True)
    except OSError:
        return False
    probe = S.ProcMem.__new__(S.ProcMem)
    probe.k = k
    return bool(probe.find_pid('xenia_canary.exe'))


def find_title_dir():
    if not os.path.isdir(XENIA_CONTENT):
        return None
    for prof in sorted(os.listdir(XENIA_CONTENT)):
        d = os.path.join(XENIA_CONTENT, prof, TITLE)
        if os.path.isdir(os.path.join(d, '00000001')):
            return d
    return None


def list_saves():
    if not os.path.isdir(SAVE_LIB):
        return []
    return sorted(n for n in os.listdir(SAVE_LIB) if os.path.isdir(os.path.join(SAVE_LIB, n, TITLE)))


def store_saves(name, log, dry=False):
    src = find_title_dir()
    if not src:
        return False, 'no Xenia save folder %s\\<profile>\\%s' % (XENIA_CONTENT, TITLE)
    if not name or any(c in name for c in '\\/:*?"<>|'):
        return False, 'bad name'
    dst = os.path.join(SAVE_LIB, name)
    if os.path.exists(dst):
        return False, 'exists: %s' % dst
    if dry:
        return True, 'dry run: would copy %s -> %s' % (src, dst)
    shutil.copytree(src, os.path.join(dst, TITLE))
    with open(os.path.join(dst, 'README.txt'), 'w', encoding='utf-8-sig', newline='\r\n') as f:
        f.write('Xbox (Xenia) saves of Tomb Raider: Underworld, stored by TruXenia %s as "%s".\n'
                'Restore: TruXenia page Saves (Xenia closed) or copy %s back to %s.\n' % (
                    time.strftime('%Y-%m-%d %H:%M:%S'), name, TITLE, src))
    log.w('I', 'saves stored: %s -> %s' % (src, dst))
    return True, dst


def restore_saves(name, log, dry=False):
    if xenia_running():
        return False, 'Xenia is running - close it first'
    dst = find_title_dir()
    src = os.path.join(SAVE_LIB, name, TITLE)
    if not dst or not os.path.isdir(src):
        return False, 'missing: %s or the Xenia save folder' % src
    backup = os.path.join(SAVE_LIB, '_vor-restore_%s' % time.strftime('%Y%m%d_%H%M%S'))
    if dry:
        return True, 'dry run: would back up %s -> %s, then copy %s -> %s' % (dst, backup, src, dst)
    shutil.copytree(dst, os.path.join(backup, TITLE))
    shutil.rmtree(dst)
    shutil.copytree(src, dst)
    log.w('I', 'saves restored: %s -> %s (backup %s)' % (src, dst, backup))
    return True, 'restored, backup %s' % backup


# ---------------------------------------------------------------------------------------------------------- link
class Link:
    def __init__(self, model, writer, args, log):
        self.model, self.writer, self.args, self.log = model, writer, args, log
        self.stop = threading.Event()
        self.write_unlocked = False

    def handle(self, line):
        parts = line.strip().split()
        if not parts:
            return ['?']
        c = parts[0].lower()
        snap = self.model.snap
        if c == 'status':
            m = self.model.mem
            return ['xenia pid %s base 0x%x, enemies %d, hits %d, watch %s, write %s' % (
                getattr(m, 'pid', 0), getattr(m, 'base', 0), len(snap['enemies']), len(self.model.hits),
                self.model.watch.path if self.model.watch else '-', 'unlocked' if self.write_unlocked else 'locked')]
        if c == 'enemies':
            return ['0x%08x %s %s LP %s st %s s0 %s s1 %s req %s target %s dist %s ko %s' % (
                e['inst'], e['oid'], e['name'], S.fmt(e['lp']), S.fmt(e['stamina'], '%.2f'), e['s0'], e['s1'],
                e['req'], e['target'], e['dist'], e['ko']) for e in snap['enemies']] or ['no enemies']
        if c == 'lara':
            l = snap['lara']
            return ['records %s / %s, meter %s flags %s active %s, time scale %s, doppelganger %s, LP %s, states %s' % (
                l.get('rec0'), l.get('rec1'), S.fmt(l.get('meter')), l.get('mflags'), l.get('active'),
                S.fmt(l.get('scale'), '%.2f'), l.get('dopp'), l.get('lp'), l.get('states'))]
        if c == 'snapshot' and len(parts) == 2:
            with open(parts[1], 'w', encoding='utf-8') as f:
                json.dump(snap, f, indent=1, default=str)
            return ['snapshot -> %s' % parts[1]]
        if c == 'watch' and len(parts) == 3:
            self.model.watch = Watch(parts[2], float(parts[1]))
            return ['watch %s s -> %s' % (parts[1], parts[2])]
        if c == 'hits':
            n = int(parts[1]) if len(parts) > 1 else 10
            return self.model.hits[-n:] or ['no hits yet']
        if c == 'saves':
            return list_saves() or ['no saves in %s' % SAVE_LIB]
        if c == 'set':
            return [self.set_value(parts[1:])]
        if c == 'quit':
            self.stop.set()
            return ['bye']
        return ['unknown command: %s' % c]

    def set_value(self, p):
        if not (self.args.allow_write and self.write_unlocked):
            return 'writing locked (start with --allow-write, then unlock in the GUI or with `unlock yes`)'
        if len(p) != 3 or p[1] not in ('lp', 'stamina'):
            return 'usage: set <inst> lp|stamina <value>'
        inst = int(p[0], 16)
        e = next((x for x in self.model.snap['enemies'] if x['inst'] == inst), None)
        if not e:
            return 'no enemy 0x%08x' % inst
        m = self.model.mem
        h0 = S.u32(m, S.u32(m, inst + 0x2d0) or 0)
        brain = S.u32(m, h0 + 0x2ec) if h0 else None
        if not brain:
            return 'no brain'
        off = S.h(self.model.A['brain']['lp' if p[1] == 'lp' else 'stamina'])
        ok, msg = self.writer.write_f32(brain + off, float(p[2]))
        self.log.w('I', 'set 0x%08x %s %s: %s (%s)' % (inst, p[1], p[2], 'ok' if ok else 'FAILED', msg))
        return '%s (%s)' % ('ok' if ok else 'FAILED', msg)

    def serve(self, port):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('127.0.0.1', port))
        srv.listen(4)
        srv.settimeout(0.5)
        self.log.w('I', 'link on 127.0.0.1:%d' % port)
        while not self.stop.is_set():
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            with conn:
                conn.settimeout(5)
                data = b''
                while not data.endswith(b'\n'):
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                line = data.decode('utf-8', 'replace').strip()
                if line.lower() == 'unlock yes' and self.args.allow_write:
                    self.write_unlocked = True
                    out = ['writing UNLOCKED for this session']
                else:
                    try:
                        out = self.handle(line)
                    except Exception as ex:          # one bad command must not stop the link
                        out = ['error: %s' % ex]
                self.log.w('V', 'link: %s -> %d line(s)' % (line, len(out)))
                for o in out:
                    self.log.w('D', 'link answer: %s' % o)
                conn.sendall(('\n'.join(out) + '\n.\n').encode('utf-8'))
        srv.close()


# ---------------------------------------------------------------------------------------------------------- GUI
def run_gui(model, link, args, log):
    import tkinter as tk
    from tkinter import ttk, simpledialog, messagebox
    st = {'lang': args.lang}
    root = tk.Tk()
    root.geometry('1040x480')
    top = ttk.Frame(root)
    top.pack(fill='x')
    status = tk.StringVar()
    ttk.Label(top, textvariable=status).pack(side='left', padx=6)
    flag_btn = ttk.Button(top, width=8)
    flag_btn.pack(side='right', padx=4)
    unp = tk.BooleanVar(value=args.unproven)
    unp_cb = ttk.Checkbutton(top, variable=unp, command=lambda: setattr(model, 'unproven', unp.get()))
    unp_cb.pack(side='right', padx=6)
    nb = ttk.Notebook(root)
    nb.pack(fill='both', expand=True)
    # page enemies
    pe = ttk.Frame(nb)
    nb.add(pe, text='')
    cols = ('name', 'lp', 'stamina', 'state0', 'state1', 'req', 'target', 'dist', 'ko')
    tv = ttk.Treeview(pe, columns=cols, show='headings', height=14)
    for c, w in zip(cols, (250, 60, 60, 160, 130, 120, 80, 70, 40)):
        tv.column(c, width=w, anchor='w')
    tv.pack(fill='both', expand=True)
    # page lara
    pl = ttk.Frame(nb)
    nb.add(pl, text='')
    lara_txt = tk.StringVar()
    ttk.Label(pl, textvariable=lara_txt, justify='left', font=('Consolas', 11)).pack(anchor='nw', padx=8, pady=8)
    # page log / link
    pg = ttk.Frame(nb)
    nb.add(pg, text='')
    bar = ttk.Frame(pg)
    bar.pack(fill='x')
    watch_btn = ttk.Button(bar)
    watch_btn.pack(side='left', padx=4, pady=4)
    link_lbl = tk.StringVar()
    ttk.Label(bar, textvariable=link_lbl).pack(side='left', padx=8)
    write_btn = ttk.Button(bar)
    write_btn.pack(side='right', padx=4)
    hits_box = tk.Text(pg, height=16, font=('Consolas', 9))
    hits_box.pack(fill='both', expand=True)
    # page saves
    ps = ttk.Frame(nb)
    nb.add(ps, text='')
    lb = tk.Listbox(ps, height=12)
    lb.pack(fill='both', expand=True, padx=6, pady=6)
    sbar = ttk.Frame(ps)
    sbar.pack(fill='x')
    store_btn = ttk.Button(sbar)
    store_btn.pack(side='left', padx=4, pady=4)
    restore_btn = ttk.Button(sbar)
    restore_btn.pack(side='left', padx=4)
    save_msg = tk.StringVar()
    ttk.Label(ps, textvariable=save_msg).pack(anchor='w', padx=6)

    def texts():
        L = st['lang']
        root.title(tr('title', L))
        for i, k in enumerate(('enemies', 'lara', 'loglink', 'saves')):
            nb.tab(i, text=tr(k, L))
        for c in cols:
            tv.heading(c, text=tr(c, L))
        flag_btn.config(text='DE | EN' if L == 'de' else 'EN | DE')
        unp_cb.config(text=tr('unproven', L))
        watch_btn.config(text='%s %s' % (tr('watch', L), tr('stop' if model.watch else 'start', L)))
        write_btn.config(text=tr('writelocked', L) if not link.write_unlocked else 'set: unlocked')
        store_btn.config(text=tr('store', L))
        restore_btn.config(text=tr('restore', L))

    def flip():
        st['lang'] = 'en' if st['lang'] == 'de' else 'de'      # not saved anywhere (tests run without settings)
        texts()

    def toggle_watch():
        if model.watch:
            model.watch = None
        else:
            p = os.path.join(os.path.dirname(args.log), 'watch_%s.tsv' % time.strftime('%Y%m%d_%H%M%S'))
            model.watch = Watch(p, 3600)
            log.w('I', 'GUI watch -> %s' % p)
        texts()

    def unlock():
        if not args.allow_write:
            messagebox.showinfo('TruXenia', 'start with --allow-write to unlock value writes')
            return
        if messagebox.askyesno('TruXenia', 'Unlock value writes (data words only, read back) for this session?'):
            link.write_unlocked = True
            log.w('I', 'writes unlocked in the GUI')
        texts()

    def refresh_saves():
        lb.delete(0, 'end')
        for n in list_saves():
            lb.insert('end', n)

    def do_store():
        name = simpledialog.askstring('TruXenia', tr('store', st['lang']))
        if name:
            ok, msg = store_saves(name.strip(), log, dry=args.selftest)
            save_msg.set(msg)
            refresh_saves()

    def do_restore():
        sel = lb.curselection()
        if not sel:
            return
        ok, msg = restore_saves(lb.get(sel[0]), log, dry=args.selftest)
        save_msg.set(msg)

    flag_btn.config(command=flip)
    watch_btn.config(command=toggle_watch)
    write_btn.config(command=unlock)
    store_btn.config(command=do_store)
    restore_btn.config(command=do_restore)
    texts()
    refresh_saves()
    shown = [0]

    def tick():
        if link.stop.is_set():
            root.destroy()
            return
        try:
            alive = model.mem.alive()
            snap = model.sample() if alive else model.snap
        except Exception as ex:
            log.w('E', 'sample failed: %s' % ex)
            alive, snap = False, model.snap
        L = st['lang']
        status.set('%s %s | %s %d | %s %d | %s' % (tr('xenia', L), tr('running' if alive else 'notrun', L),
                                                   tr('enemies', L), len(snap['enemies']), tr('hits', L),
                                                   len(model.hits), snap['time']))
        tv.delete(*tv.get_children())
        for e in snap['enemies']:
            tv.insert('', 'end', values=('%s %s' % (e['name'], e['oid']), S.fmt(e['lp']), S.fmt(e['stamina'], '%.1f'),
                                         e['s0'], e['s1'], e['req'], e['target'], e['dist'], e['ko']))
        l = snap['lara']
        lara_txt.set('%s: %s / %s\n%s: %s (%s %s, flags %s)\n%s: %s\n%s: %s\n%s: %s\nLP: %s' % (
            tr('records', L), l.get('rec0'), l.get('rec1'), tr('meter', L), S.fmt(l.get('meter')), tr('active', L),
            l.get('active'), l.get('mflags'), tr('scale', L), S.fmt(l.get('scale'), '%.2f'), tr('dopp', L),
            l.get('dopp'), tr('pos', L), l.get('pos') if l.get('pos') else '?', l.get('lp')))
        link_lbl.set('%s 127.0.0.1:%d' % (tr('link', L), args.port))
        if len(model.hits) != shown[0]:
            hits_box.delete('1.0', 'end')
            hits_box.insert('end', '\n'.join(model.hits[-200:]))
            hits_box.see('end')
            shown[0] = len(model.hits)
        root.after(100, tick)

    root.protocol('WM_DELETE_WINDOW', lambda: (link.stop.set(), root.destroy()))
    root.after(100, tick)
    if args.selftest:
        root.after(int(args.selftest_seconds * 1000), lambda: (link.stop.set(), root.destroy()))
    root.mainloop()


# ---------------------------------------------------------------------------------------------------------- main
def check_all_proof(m, A, log):
    bad = n = 0
    for sec, v in A.items():
        if not isinstance(v, dict) or 'proof' not in v:
            continue
        for addr, word in v['proof'].items():
            n += 1
            got = S.u32(m, S.h(addr))
            if got != S.h(word):
                bad += 1
                log.w('E', 'proof %s %s: expected %s, got %s' % (sec, addr, word,
                                                                 'unreadable' if got is None else '0x%08x' % got))
    log.w('I', 'proof words: %d checked, %d mismatches' % (n, bad))
    return bad == 0


def selftest(model, link, args, log):
    """offline: simulated memory, hit log, link commands over TCP, save library dry run; exit 0 if all pass"""
    th = threading.Thread(target=link.serve, args=(args.port,), daemon=True)
    th.start()
    time.sleep(0.3)
    t0 = time.time()
    while time.time() - t0 < 2.8:
        model.sample()
        time.sleep(0.05)
    import truxenia_cmd as C
    ok = True
    out = {}
    for cmd in ('status', 'enemies', 'lara', 'hits 5', 'saves', 'set 0x41000000 lp 1'):
        out[cmd] = C.send(cmd, args.port)
        log.w('I', 'selftest link %s -> %s' % (cmd, ' | '.join(out[cmd])))
    if len(model.hits) < 3:
        ok = False
        log.w('E', 'selftest: expected >= 3 hit lines, got %d' % len(model.hits))
    if not any('reaction HitReaction' in h for h in model.hits):
        ok = False
        log.w('E', 'selftest: no hit with reaction HitReaction')
    if not any('locked' in x for x in out['set 0x41000000 lp 1']):
        ok = False
        log.w('E', 'selftest: set was not refused while locked')
    okst, msg = store_saves('selftest_dry', log, dry=True)
    log.w('I', 'selftest store (dry): %s %s' % (okst, msg))
    okre, msg = restore_saves('selftest_dry', log, dry=True)
    log.w('I', 'selftest restore (dry): %s %s' % (okre, msg))
    link.stop.set()
    th.join(2)
    log.w('I', 'selftest %s (%d hit lines)' % ('PASSED' if ok else 'FAILED', len(model.hits)))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='TruXenia - Xbox values from Xenia (menu + link)')
    ap.add_argument('--nogui', action='store_true')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--dumpfile')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--selftest-gui', action='store_true', help='selftest with the window open for --selftest-seconds')
    ap.add_argument('--selftest-seconds', type=float, default=4.0)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--log')
    ap.add_argument('--hitlog')
    ap.add_argument('--unproven', action='store_true')
    ap.add_argument('--allow-write', action='store_true')
    ap.add_argument('--lang', choices=('de', 'en'), default='de')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--debug', action='store_true')
    ap.add_argument('--trace', action='store_true')
    a = ap.parse_args()
    if a.selftest_gui:
        a.selftest = True
    logdir = os.path.join(ROOT, 'logs', 'truxenia')
    os.makedirs(logdir, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    a.log = a.log or os.path.join(logdir, 'truxenia_%s%s.log' % (stamp, '_selftest' if a.selftest else ''))
    log = S.Log(a.log, a.verbose, a.debug, a.trace)
    log.w('I', 'TruXenia start (%s), log %s' % (' '.join(sys.argv[1:]), a.log))
    A = json.load(open(ADDR_FILE, encoding='utf-8'))
    try:
        if a.selftest:
            mem = FakeMem(A, log)
        elif a.dumpfile:
            mem = S.DumpMem(a.dumpfile, log)
        else:
            mem = S.ProcMem(log)
    except Exception as ex:
        log.w('E', str(ex))
        return 1
    ok = check_all_proof(mem, A, log)
    if a.check:
        return 0 if ok else 1
    if not ok and not a.force:
        log.w('E', 'refusing: proof words differ (use --force only if you know why)')
        return 1
    model = Model(mem, A, log, a.unproven)
    hp = a.hitlog or os.path.join(os.path.dirname(a.log), 'hits_%s%s.log' % (stamp, '_selftest' if a.selftest else ''))
    model.hitlog = open(hp, 'a', encoding='utf-8')
    log.w('I', 'hit log %s' % hp)
    writer = Writer(mem, log)
    link = Link(model, writer, a, log)
    if a.once:
        snap = model.sample()
        for e in snap['enemies']:
            print('0x%08x %s %-32s LP %s st %s %s / %s req %s target %s dist %s' % (
                e['inst'], e['oid'], e['name'], S.fmt(e['lp']), S.fmt(e['stamina'], '%.2f'), e['s0'], e['s1'],
                e['req'], e['target'], e['dist']))
        print(link.handle('lara')[0])
        print('%d enemies' % len(snap['enemies']))
        return 0
    if a.selftest and not a.selftest_gui:
        return selftest(model, link, a, log)
    th = threading.Thread(target=link.serve, args=(a.port,), daemon=True)
    th.start()
    if a.nogui:
        try:
            while not link.stop.is_set():
                if not mem.alive():
                    log.w('I', 'Xenia exited - stop')
                    break
                model.sample()
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        link.stop.set()
    else:
        run_gui(model, link, a, log)
    log.w('I', 'TruXenia end: %d hit lines' % len(model.hits))
    return 0


if __name__ == '__main__':
    sys.exit(main())
