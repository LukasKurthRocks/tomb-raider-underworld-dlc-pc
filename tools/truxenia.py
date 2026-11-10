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
    # stage 1b
    'objects': ('Objekte', 'Objects'), 'loaded': ('Geladene Daten', 'Loaded data'), 'cat': ('Art', 'Kind'),
    'attack': ('Angriff', 'Attack'), 'fly': ('Flug', 'Flight'), 'kohandle': ('Ko-Griff', 'Ko handle'),
    'vel': ('Tempo', 'Speed'), 'legend': ('Legende', 'Legend'),
    'laralp': ('Lara LP', 'Lara LP'), 'larastates': ('Lara-Zustände', 'Lara states'),
    'camera': ('Kamera', 'Camera'), 'requests': ('Zeit-Anforderungen', 'Time requests'),
    'aim': ('Zielen (Lock)', 'Aim (lock)'),
    'ramps': ('Rampen Spieler / Welt', 'Ramps player / world'),
    'objtable': ('Objekttabelle (0x82979280)', 'Object table (0x82979280)'),
    'loadplan': ('Einheiten, Sektionen, Shader: noch nicht belegt - Plan in docs/TRUXENIA.md',
                 'Units, sections, shaders: not proven yet - plan in docs/TRUXENIA.md'),
}

# object kinds (stage 1b): evidence = object name (+ the TU enemy brain test); unknown = other, never guessed
CATS = (('lara', '#000000', 'Lara', 'Lara'),
        ('tutorial', '#e07000', 'Tutorial-Thrall', 'tutorial thrall'),
        ('thrall', '#d02020', 'Thrall', 'thrall'),
        ('yeti', '#9000c0', 'Yeti', 'yeti'),
        ('goo', '#209020', 'Goo (Tropfen, Kugeln, Quellen)', 'goo (drips, balls, spawners)'),
        ('generator', '#808000', 'Generator', 'generator'),
        ('chunkdoll', '#707070', 'Chunkdoll (Splitter)', 'chunkdoll (pieces)'),
        ('natla', '#1060d0', 'Natla / Skript-Figur', 'Natla / scripted actor'),
        ('pickup', '#008c8c', 'Aufnehmbar / Bedienbar', 'pickup / interactable'),
        ('other', '#909090', 'Sonstiges', 'other'))
CAT_KEYS = tuple(c[0] for c in CATS)
PICKUP_WORDS = ('pickup', 'medipack', 'health', 'ammo', 'treasure', 'reward', 'lever', 'switch', 'button', 'door',
                'chest', 'relic')
FLY_STATES = ('Fall', 'Splat', 'Land')


def classify(name, enemy, is_lara):
    """kind of an instance from its object name; `enemy` = the TU enemy brain test passed"""
    n = (name or '').lower()
    if is_lara:
        return 'lara'
    if 'chunkdoll' in n:
        return 'chunkdoll'
    if 'generator' in n:
        return 'generator'
    if 'goo' in n:
        return 'goo'
    if enemy:
        if 'natla' in n:
            return 'natla'
        if 'yeti' in n:
            return 'yeti'
        if 'tutorial' in n and 'thrall' in n:
            return 'tutorial'
        if 'thrall' in n:
            return 'thrall'
    if 'natla' in n:
        return 'natla'
    if any(w in n for w in PICKUP_WORDS):
        return 'pickup'
    return 'other'


def u16(m, a):
    b = m.read(a, 2) if a else None
    return struct.unpack('>H', b)[0] if b and len(b) == 2 else None


def u8(m, a):
    b = m.read(a, 1) if a else None
    return b[0] if b else None


def tr(key, lang):
    return T[key][0 if lang == 'de' else 1]


def now_ts():
    t = time.time()
    return time.strftime('%H:%M:%S', time.localtime(t)) + '.%03d' % int((t % 1) * 1000)


# ---------------------------------------------------------------------------------------------------------- memory
class FakeMem:
    """--selftest: a small simulated guest memory with the TU layout (two thralls, a goo spawner without a brain, Lara,
    chart machines with record arrays, meter with time-scale requests, object table, trackers)"""

    def __init__(self, A, log):
        self.A, self.log, self.pid, self.base = A, log, 0, 0
        self.mem = {}
        self.t0 = time.time()
        for sec, v in A.items():                       # proof words
            if isinstance(v, dict):
                for a, w in v.get('proof', {}).items():
                    self.w32(S.h(a), S.h(w))
        il, ob, br = A['instance_list'], A['object'], A['brain']
        self.states = {}
        for i, nm in enumerate(('CombatIdle', 'MeleeAttack', 'Hit', 'CombatStepIdle', 'Fall', 'Land', 'Getup',
                                'RegenerateDeath')):
            a = 0x40001000 + i * 0x100
            self.wstr(a + 0x40, nm)
            self.w32(a + 8, a + 0x40)
            self.states[nm] = a
        self.insts = []
        prev = None
        specs = (('viking_thrall_tutorial_dlc2_', 1004, True), ('viking_thrall_dlc2_', 927, True),
                 ('dlc2_uo_goo_drips_spawned', 929, False))
        for i, (name, oid, enemy) in enumerate(specs):
            inst = 0x41000000 + i * 0x1000
            if prev is None:
                self.w32(S.h(il['head']), inst)
            else:
                self.w32(prev + S.h(il['next_offset']), inst)
            prev = inst
            obj, holder, h0, brain, data = inst + 0x800, inst + 0x900, inst + 0x940, 0x42000000 + i * 0x10000, inst + 0xa00
            self.w32(inst + S.h(ob['instance_object_offset']), obj)
            self.w32(obj + S.h(ob['object_id_offset']), oid)
            self.w32(obj + S.h(ob['object_name_ptr_offset']), inst + 0xc00)   # name outside obj / holder
            self.wstr(inst + 0xc00, name)
            self.w32(inst + 0x50, data)
            self.w32(data, 0xdaf00018 if enemy else 0x12345678)
            self.mem[data + 0x18] = 1 if enemy else 0
            self.w32(inst + 0x2d0, holder); self.w32(holder, h0); self.w32(h0 + 0x2ec, brain)
            self.wf(brain + S.h(br['lp']), 500.0); self.wf(brain + S.h(br['stamina']), 40.0)
            self.w32(brain + S.h(br['state_layer0']), self.states['CombatStepIdle'])
            self.w32(brain + S.h(br['state_layer1']), 0)
            self.w32(brain + 0x18f8, 0)
            self.w32(brain + 0x18d4, 0)                  # MeleeAttack data slot 0 of layer 0
            self.w32(brain + 0x2fc4 + 4, 0)              # coordinator requester handle: none
            self.wf(inst + 0x20, 100.0 * i); self.wf(inst + 0x24, 0.0); self.wf(inst + 0x28, 0.0)
            self.w32(inst + 0x44, 7)                     # allocation stamp
            self.insts.append((inst, brain))
        self.w32(S.h(il['struct']), len(specs))
        self.w32(prev + S.h(il['next_offset']), 0)                      # end of the instance list
        # melee attack record for thrall 0: data = (brain+0x1254 + 0*0x19c + 0x1f) & ~0xf
        b0 = self.insts[0][1]
        self.mraw = b0 + 0x1254                          # slot block sm + (slot + 2*layer)*0x19c, slot 0 / layer 0
        self.mdata = (self.mraw + 0x1f) & ~0xf
        self.mrec = 0x44000000
        self.w32(self.mdata + 0x50, self.mrec)
        for k, v in enumerate((1, 50, 1, 51, 0, 0)):
            self.mem[self.mrec + 0x78 + 2 * k] = (v >> 8) & 0xff
            self.mem[self.mrec + 0x79 + 2 * k] = v & 0xff
        # Lara: player tracker, chart machines with charts / record arrays / records, meter; game tracker
        trk, mac0, mac1, meter, lara = 0x43000000, 0x43100000, 0x43200000, 0x43300000, 0x43400000
        lc, pt, gt = A['lara_chart'], A['player_tracker'], A['game_tracker']
        chart, arr = 0x45000000, 0x45100000
        self.w32(chart + 0xc, arr)
        self.recptr = {}
        for idx in range(1500):
            self.w32(arr + 4 * idx, 0x46000000 + idx * 0x40)
        for idx in (1477, 1482, 1488, 1492):
            rec = 0x46000000 + idx * 0x40
            self.recptr[idx] = rec
            ids = {1477: (236, 230, 2102), 1482: (420, 572, 1900), 1488: (), 1492: ()}[idx]
            self.mem[rec + 0xc], self.mem[rec + 0xd] = 0, len(ids)
            self.w32(rec + 0x18, rec + 0x30)
            for k, sid in enumerate(ids):
                self.mem[rec + 0x30 + 2 * k], self.mem[rec + 0x31 + 2 * k] = (sid >> 8) & 0xff, sid & 0xff
        for mac in (mac0, mac1):
            self.w32(mac + 4, chart)
        self.w32(S.h(lc['player_tracker_ptr']), trk)
        self.w32(trk + S.h(lc['machine0_offset']), mac0); self.w32(trk + S.h(lc['machine1_offset']), mac1)
        self.w32(mac0 + S.h(lc['record_offset']), self.recptr[1482]); self.w32(mac1 + S.h(lc['record_offset']), 0)
        self.w32(trk + S.h(pt['meter_object']), meter)
        self.mem[trk + S.h(pt['doppelganger_flag'])] = 1
        # 2026-11-10 aim: CM +0x1fc with bits 10 / 18 / 19, targeter 0 locked on thrall 0 (stamp 7)
        am, cm, tlist, t0, node = A['aim'], 0x43500000, 0x43600000, 0x43610000, 0x43620000
        self.w32(trk + S.h(pt['combat_manager']), cm)
        self.w32(cm + S.h(am['combat_manager_bits']), (1 << 10) | (1 << 18) | (1 << 19))
        self.w32(S.h(am['targeter_list']), tlist); self.w32(tlist, t0)
        self.w32(t0 + S.h(am['targeter_flags']), 1); self.w32(t0 + S.h(am['targeter_target_node']), node)
        self.w32(node + S.h(am['node_handle']), self.insts[0][0]); self.w32(node + S.h(am['node_handle']) + 4, 7)
        self.wf(trk + 0x628, 1000.0); self.wf(trk + 0x630, 1000.0)
        self.w32(meter + 4, 0); self.wf(meter + 8, 1000.0); self.wf(meter + 0xc, 1000.0)
        for k in range(14):
            self.wf(meter + 0x40 + 4 * k, 0.0)
        self.wf(S.h(A['meter_requests']['ramp_player']), 1.0); self.wf(S.h(A['meter_requests']['ramp_world']), 1.0)
        g = S.h(gt['address'])
        self.w32(g + S.h(gt['player_instance']), lara); self.wf(g + S.h(gt['world_time_scale']), 1.0)
        self.wf(lara + 0x20, 50.0); self.wf(lara + 0x24, 0.0); self.wf(lara + 0x28, 0.0)
        cam = S.h(A['camera']['manager'])
        self.w32(cam + 0x54, 3); self.w32(cam + 0x7c, 4)
        # object table: 0xcc entries of 0x24; two loaded objects
        ot = S.h(A['object_table']['address'])
        for i in range(0xcc):
            self.w32(ot + i * 0x24 + 8, 0); self.mem[ot + i * 0x24 + 0xc] = 0; self.mem[ot + i * 0x24 + 0xd] = 0
            self.mem[ot + i * 0x24 + 0xe] = 0; self.mem[ot + i * 0x24 + 0xf] = 0
            for k in (0, 4, 0x10, 0x14, 0x18, 0x1c, 0x20):
                self.w32(ot + i * 0x24 + k, 0)
        for i, (oid, objp) in enumerate(((927, self.insts[1][0] + 0x800), (1004, self.insts[0][0] + 0x800))):
            e = ot + i * 0x24
            self.w32(e + 8, objp)
            self.mem[e + 0xc], self.mem[e + 0xd] = (oid >> 8) & 0xff, oid & 0xff
            self.mem[e + 0xe], self.mem[e + 0xf] = 0, 2
        self.mac0, self.meter, self.gt = mac0, meter, g
        self.script = [(0.3, 'rec', 1477), (0.5, 'rec', 1488), (0.6, 'hit', 0, 20.0, 'Hit'),
                       (0.9, 'state', 0, 'CombatStepIdle'), (1.0, 'state', 0, 'MeleeAttack'),
                       (1.2, 'rec', 1492), (1.3, 'hit', 0, 20.0, 'MeleeAttack'), (1.6, 'power', 1),
                       (1.7, 'hit', 1, 95.0, 'Fall'), (1.8, 'move', 1, 300.0), (2.0, 'state', 1, 'Land'),
                       (2.1, 'move', 1, 420.0), (2.3, 'state', 1, 'Getup'), (2.4, 'regen', 1),
                       (2.6, 'hit', 1, 500.0, 'RegenerateDeath')]
        self.done = 0
        log.w('I', 'selftest memory: 2 thralls + goo spawner, Lara, charts, meter, object table (%d bytes)' % len(self.mem))

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
                self.w32(self.mac0 + 0x520, self.recptr[ev[2]])
            elif ev[1] == 'hit':
                inst, brain = self.insts[ev[2]]
                lp = struct.unpack('>f', self.read(brain + 0x2c64, 4))[0]
                self.wf(brain + 0x2c64, lp - ev[3])
                self.w32(brain + 0x125c, self.states[ev[4]])
            elif ev[1] == 'state':
                inst, brain = self.insts[ev[2]]
                self.w32(brain + 0x125c, self.states[ev[3]])
                if ev[3] == 'MeleeAttack' and ev[2] == 0:
                    self.w32(self.mraw + 0x1a8, self.states['MeleeAttack'])   # TU switch: stw r30, 0x1a8(slot block)
            elif ev[1] == 'move':
                self.wf(self.insts[ev[2]][0] + 0x20, ev[3])
            elif ev[1] == 'regen':                       # RegenerateDeath Enter: LP := maximum (TU 0x8235dff8)
                inst, brain = self.insts[ev[2]]
                self.w32(brain + 0x125c, self.states['RegenerateDeath'])
                self.wf(brain + 0x2c64, 500.0)
            elif ev[1] == 'power':
                self.w32(self.meter + 4, ev[2]); self.wf(self.gt + 0x118, 0.3)
                self.wf(self.meter + 0x40, 1.2); self.wf(self.meter + 0x44, 0.3)        # slot 0
                self.wf(self.meter + 0x60, 0.02); self.wf(self.meter + 0x64, 1.0)       # slot 4
                self.wf(S.h(self.A['meter_requests']['ramp_world']), 1.0)
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
        self.snap = {'time': '', 'enemies': [], 'lara': {}, 'objects': [], 'loaded': {}}
        self.prev = {}                                # inst -> (lp, stamina, state0)
        self.pending = {}                             # inst -> open hit
        self.hits = []                                # finished hit lines (dicts)
        self.recs = []                                # (time, record index) of machine 0
        self.hitlog = None
        self.watch = None
        self.ko = '?'
        self.arrays = {}                              # record array address -> tuple of record pointers
        self.lastpos = {}                             # inst -> (time, pos)
        self.flights = {}                             # inst -> {'t', 'start', 'max', 'states'}
        self.lastfly = {}                             # inst -> 'N u in S s'
        self.loaded_t = 0.0

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

    def _aim(self, trk):
        """2026-11-10 K-5 lock-on path (section "aim" of the address file; PC side TruMenu 0.22.15 aim.trace): CM+0x1fc
        bits 9 soft lock / 10 lock / 11 / 18 / 19 / 20 / 21 and targeter 0 (flags +8, target = node +0x90 -> handle
        {instance, stamp} checked against instance +0x44) - read only"""
        m, A = self.mem, self.A
        pt, am = A['player_tracker'], A['aim']
        out = {'aim_w': None, 'aim_bits': '?', 'aim_t0_flags': None, 'aim_target': '?'}
        cm = S.u32(m, trk + S.h(pt['combat_manager'])) if trk else None
        w = S.u32(m, cm + S.h(am['combat_manager_bits'])) if cm else None
        if w is not None:
            out['aim_w'] = w
            out['aim_bits'] = ' '.join('%d:%d' % (b, (w >> b) & 1) for b in (9, 10, 11, 18, 19, 20, 21))
        lst = S.u32(m, S.h(am['targeter_list']))
        t0 = S.u32(m, lst) if lst else None
        if not t0:
            return out
        out['aim_t0_flags'] = S.u32(m, t0 + S.h(am['targeter_flags']))
        node = S.u32(m, t0 + S.h(am['targeter_target_node']))
        if not node:
            out['aim_target'] = '-'
            return out
        h = node + S.h(am['node_handle'])
        inst, stamp = S.u32(m, h), S.u32(m, h + 4)
        cur = S.u32(m, inst + S.h(A['instance_ext']['stamp']['offset'])) if inst else None
        if not inst or cur is None or cur != stamp:
            out['aim_target'] = '(stale node 0x%08x)' % node
            return out
        oid, name = self._obj_name(inst)
        out['aim_target'] = '%s 0x%08x' % (name or '?', inst)
        return out

    def _vec(self, a):
        b = self.mem.read(a, 12) if a else None
        return struct.unpack('>3f', b) if b and len(b) == 12 else None

    def _obj_name(self, inst):
        ob = self.A['object']
        obj = S.u32(self.mem, inst + S.h(ob['instance_object_offset'])) if inst else None
        oid = S.u32(self.mem, obj + S.h(ob['object_id_offset'])) if obj else None
        name = S.cstr(self.mem, S.u32(self.mem, obj + S.h(ob['object_name_ptr_offset']))) if obj else None
        return oid, name

    def _enemy_test(self, inst):
        """TU enemy init 0x822da9ac: [inst+0x50] word 0 == 0xdaf00018 and byte +0x18 != 0"""
        et = self.A['enemy_test']
        data = S.u32(self.mem, inst + S.h(et['data_offset']))
        if not data:
            return False
        return S.u32(self.mem, data) == S.h(et['magic']) and (u8(self.mem, data + S.h(et['count_byte'])) or 0) > 0

    def _record_index(self, mac, rec):
        """position of a chart record pointer in the record array [[machine+4]+0xc] (TU 0x8248282c..0x8248285c)"""
        if not mac or not rec:
            return None
        lr = self.A['lara_record']
        chart = S.u32(self.mem, mac + S.h(lr['chart_offset']))
        arr = S.u32(self.mem, chart + S.h(lr['record_array_offset'])) if chart else None
        if not arr:
            return None
        words = self.arrays.get(arr)
        if words is None:
            raw = b''
            for k in range(8):                        # up to 8 x 1024 records, stop at the first unreadable block
                b = self.mem.read(arr + k * 4096, 4096)
                if not b or len(b) < 4096:
                    break
                raw += b
            words = struct.unpack('>%dI' % (len(raw) // 4), raw) if raw else ()
            self.arrays[arr] = words
        try:
            return words.index(rec)
        except ValueError:
            return None

    def _record_states(self, rec):
        lr = self.A['lara_record']
        if not rec:
            return '-'
        n = u16(self.mem, rec + S.h(lr['record_state_count_offset']))
        lst = S.u32(self.mem, rec + S.h(lr['record_state_list_offset']))
        if n is None or not lst or n > 32:
            return '?'
        ids = [u16(self.mem, lst + 2 * i) for i in range(n)]
        return ' '.join(str(i) for i in ids if i is not None)

    def _melee(self, brain, layer, state_obj):
        """attack record of a running MeleeAttack: slot block raw = brain+0x1254 + (slot + 2*layer)*0x19c with
        slot = [brain+0x18d4+4*layer]; state data = (raw + 0x1f) & ~0xf, record = [data+0x50] (TU MeleeAttack Enter
        0x8232fb48). Self-check: the state switch 0x82349600 stores the state object at raw+0x1a8 (`stw r30,
        0x1a8(r11)` 0x82349704, r11 = raw) and passes raw+0x10 - NOT at aligned data+0x198: the brain is 16-aligned, so
        raw (+0x...4) is not, and data+0x198 sat 4 bytes before the state object (live 09.11.: always '?(data)')"""
        me = self.A['melee']
        slot = S.u32(self.mem, brain + S.h(me['slot_index_offset']) + 4 * layer)
        if slot is None or slot > 64:
            return '?'
        sm = brain + S.h(me['state_machine_offset'])
        raw = sm + (slot + 2 * layer) * S.h(me['data_stride'])
        data = (raw + S.h(me['data_bias'])) & ~0xf
        if S.u32(self.mem, raw + S.h(me.get('raw_state_object_offset', '0x1a8'))) != state_obj:
            return '?(data)'
        rec = S.u32(self.mem, data + S.h(me['data_record_offset']))
        if not rec:
            return '-'
        refs = self.mem.read(rec + S.h(me['record_anim_refs_offset']), 12)
        if not refs or len(refs) < 12:
            return 'rec %08x' % rec
        r = struct.unpack('>6H', refs)
        return 'rec %08x anim %d/%d %d/%d %d/%d' % ((rec,) + r)

    def _ko_handle(self, brain, lara_inst):
        """raw: whom the coordinator requester handle {[brain+0x2fc4+4] instance, +8 stamp} points at"""
        co = self.A['coordinator']
        req = brain + S.h(co['requester_offset'])
        hi = S.u32(self.mem, req + S.h(co['handle_instance']))
        hs = S.u32(self.mem, req + S.h(co['handle_stamp']))
        if not hi:
            return '-'
        if S.u32(self.mem, hi + 0x44) != hs:
            return 'stale'
        if hi == lara_inst:
            return 'Lara'
        oid, name = self._obj_name(hi)
        return name or '0x%08x' % hi

    def _fly(self, inst, t, s0, pos):
        """flight while the state is Fall / Splat / Land: largest horizontal distance from the start position"""
        f = self.flights.get(inst)
        if s0 in FLY_STATES and pos:
            if not f:
                f = self.flights[inst] = {'t': t, 'start': pos, 'max': 0.0, 'states': s0}
            d = ((pos[0] - f['start'][0]) ** 2 + (pos[1] - f['start'][1]) ** 2) ** 0.5
            f['max'] = max(f['max'], d)
            if not f['states'].endswith(s0):
                f['states'] += '>' + s0
            return '%.0f' % f['max']
        if f:
            del self.flights[inst]
            self.lastfly[inst] = '%.0f u in %.1f s (%s)' % (f['max'], t - f['t'], f['states'])
            self.log.w('I', 'fly: 0x%08x %s' % (inst, self.lastfly[inst]))
        return '-'

    def _meter_requests(self, meter):
        mr = self.A['meter_requests']
        out = {'slots': '?', 'win_player': '?', 'win_world': '?', 'selected': '?', 'ramp_player': None,
               'ramp_world': None}
        # a slot counts when its value is > 0.0 (selector 0x823d7578 fcmpu with [0x8207d538] = 0.0, ble -> skip),
        # so both 0 and the -1 TruMenu reads as "empty" are empty
        if meter:
            b = self.mem.read(meter + S.h(mr['offset']), 8 * mr['slots'])
            if b and len(b) == 8 * mr['slots']:
                v = struct.unpack('>%df' % (2 * mr['slots']), b)
                used = ['%d:%.2f/%.2f' % (i, v[2 * i], v[2 * i + 1]) for i in range(mr['slots'])
                        if v[2 * i] > 0 or v[2 * i + 1] > 0]
                out['slots'] = ' '.join(used) or '-'
                wp = [i for i in range(mr['slots']) if v[2 * i] > 0]
                ww = [i for i in range(mr['slots']) if v[2 * i + 1] > 0]
                out['win_player'] = ('%d' % wp[-1]) if wp else '-'
                out['win_world'] = ('%d' % ww[-1]) if ww else '-'
                # same text as TruMenu 0.22.11 pc_ts_selected: `P1.20(s0) W0.30(s0)`
                out['selected'] = '%s %s' % (('P%.2f(s%d)' % (v[2 * wp[-1]], wp[-1])) if wp else 'P-',
                                             ('W%.2f(s%d)' % (v[2 * ww[-1] + 1], ww[-1])) if ww else 'W-')
        out['ramp_player'] = S.f32(self.mem, S.h(mr['ramp_player']))
        out['ramp_world'] = S.f32(self.mem, S.h(mr['ramp_world']))
        return out

    def _loaded(self):
        """object tracker table 0x82979280 (TU 0x8214684c): 0xcc entries of 0x24, +8 object, +0xc id, +0xe state"""
        ot = self.A['object_table']
        base, n, stride = S.h(ot['address']), S.h(ot['entries']), S.h(ot['stride'])
        raw = self.mem.read(base, n * stride)
        if not raw or len(raw) < n * stride:
            return {'error': 'object table unreadable'}
        counts = {}
        objs = []
        for i in range(n):
            e = raw[i * stride:(i + 1) * stride]
            obj, oid, st = struct.unpack_from('>I', e, S.h(ot['object_offset']))[0], \
                struct.unpack_from('>H', e, S.h(ot['id_offset']))[0], struct.unpack_from('>H', e, S.h(ot['state_offset']))[0]
            if not oid and not st:
                continue
            counts[st] = counts.get(st, 0) + 1
            if st == ot['loaded_state']:
                nm = S.cstr(self.mem, S.u32(self.mem, obj + S.h(self.A['object']['object_name_ptr_offset']))) if obj else None
                objs.append((oid, nm or '?'))
        return {'counts': counts, 'objects': sorted(objs), 'time': now_ts()}

    def sample(self):
        m, A = self.mem, self.A
        if isinstance(m, FakeMem):
            m.tick()
        t = time.time()
        il, br = A['instance_list'], A['brain']
        gt, pt, me, lc = A['game_tracker'], A['player_tracker'], A['meter'], A['lara_chart']
        g = S.h(gt['address'])
        lara_inst = S.u32(m, g + S.h(gt['player_instance']))
        lpos = self._vec(lara_inst + 0x20) if lara_inst else None
        enemies, objects = [], []
        inst = S.u32(m, S.h(il['head']))
        seen = set()
        while inst and inst not in seen and len(seen) < S.MAX_INST:
            seen.add(inst)
            oid, name = self._obj_name(inst)
            is_enemy = self._enemy_test(inst)
            pos = self._vec(inst + 0x20)
            dist = (sum((a - b) ** 2 for a, b in zip(pos, lpos)) ** 0.5) if (pos and lpos) else None
            cat = classify(name, is_enemy, inst == lara_inst)
            objects.append({'inst': inst, 'oid': oid, 'name': name or '?', 'cat': cat, 'enemy': is_enemy,
                            'pos': pos, 'dist': '?' if dist is None else '%.0f' % dist})
            holder = S.u32(m, inst + 0x2d0) if is_enemy else None
            h0 = S.u32(m, holder) if holder else None
            brain = S.u32(m, h0 + 0x2ec) if h0 else None
            if is_enemy and brain:
                so0 = S.u32(m, brain + S.h(br['state_layer0']))
                so1 = S.u32(m, brain + S.h(br['state_layer1']))
                e = {'inst': inst, 'oid': oid, 'name': name or '?', 'cat': cat, 'lp': S.f32(m, brain + S.h(br['lp'])),
                     'stamina': S.f32(m, brain + S.h(br['stamina'])),
                     's0': self._state_name(so0), 's1': self._state_name(so1)}
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
                e['ko_handle'] = self._ko_handle(brain, lara_inst)
                e['dist'] = '?' if dist is None else '%.0f' % dist
                e['pos'] = pos
                lp_prev = self.lastpos.get(inst)
                e['vel'] = '?'
                if pos and lp_prev and t > lp_prev[0]:
                    e['vel'] = '%.0f' % (sum((a - b) ** 2 for a, b in zip(pos, lp_prev[1])) ** 0.5 / (t - lp_prev[0]))
                if pos:
                    self.lastpos[inst] = (t, pos)
                e['fly'] = self._fly(inst, t, e['s0'], pos)
                e['lastfly'] = self.lastfly.get(inst, '-')
                e['attack'] = '-'
                if e['s0'] == 'MeleeAttack':
                    e['attack'] = self._melee(brain, 0, so0)
                elif e['s1'] == 'MeleeAttack':
                    e['attack'] = 'L1 ' + self._melee(brain, 1, so1)
                e['lp_note'] = 'max (RegenerateDeath)' if e['s0'] == 'RegenerateDeath' else '-'
                enemies.append(e)
            inst = S.u32(m, inst + S.h(il['next_offset']))
        trk = S.u32(m, S.h(lc['player_tracker_ptr']))
        recs, rptrs = [], []
        for k in ('machine0_offset', 'machine1_offset'):
            mac = S.u32(m, trk + S.h(lc[k])) if trk else None
            r = S.u32(m, mac + S.h(lc['record_offset'])) if mac else None
            rptrs.append(r)
            idx = self._record_index(mac, r)
            recs.append(idx if idx is not None else ('-' if not r else '?'))
        meter = S.u32(m, trk + S.h(pt['meter_object'])) if trk else None
        mflags = S.u32(m, meter + S.h(me['flags'])) if meter else None
        dopp = m.read(trk + S.h(pt['doppelganger_flag']), 1) if trk else None
        lh = A['lara_health']
        cam = A['camera']
        mgr = S.h(cam['manager'])
        req = self._meter_requests(meter)
        lara = {'rec0': recs[0], 'rec1': recs[1], 'meter': S.f32(m, meter + S.h(me['value'])) if meter else None,
                'mflags': mflags, 'active': None if mflags is None else bool(mflags & 1),
                'scale': S.f32(m, g + S.h(gt['world_time_scale'])), 'dopp': None if dopp is None else dopp[0],
                'inst': lara_inst, 'pos': lpos,
                'lp': S.f32(m, trk + S.h(lh['offset'])) if trk else None,
                'lp_max': S.f32(m, trk + S.h(lh['max_offset'])) if trk else None,
                'states': self._record_states(rptrs[0]), 'states1': self._record_states(rptrs[1]),
                'req_slots': req['slots'], 'win_player': req['win_player'], 'win_world': req['win_world'],
                'req_selected': req['selected'],
                'ramp_player': req['ramp_player'], 'ramp_world': req['ramp_world'],
                'cam_mode': S.u32(m, mgr + S.h(cam['mode_offset'])), 'cam_flags': S.u32(m, mgr + S.h(cam['flags_offset'])),
                'cam_pos': '?', 'cam_fov': '?'}
        lara.update(self._aim(trk))
        loaded = self.snap.get('loaded') or {}
        if t - self.loaded_t >= 1.0:
            loaded = self._loaded()
            self.loaded_t = t
        ts = now_ts()
        with self.lock:
            self.snap = {'time': ts, 'enemies': enemies, 'lara': lara, 'objects': objects, 'loaded': loaded}
            self._hits(ts, enemies, lara)
            if self.watch:
                self.watch.row(ts, enemies, lara)
        return self.snap

    # -- hit log (same text as TruMenu combo.trace, plus Xbox extras)
    def _hits(self, ts, enemies, lara):
        t = time.time()
        if lara['rec0'] not in (None, '?', '-') and (not self.recs or self.recs[-1][1] != lara['rec0']):
            self.recs.append((t, lara['rec0']))
            self.recs = self.recs[-12:]
        for e in enemies:
            p = self.prev.get(e['inst'])
            if p and e['lp'] is not None and p[0] is not None and e['lp'] < p[0] - 0.01:
                path = '>'.join(str(r) for tt, r in self.recs if t - tt <= PATH_WINDOW)[-60:] or str(lara['rec0'])
                regen = p[2] == 'RegenerateDeath' or e['s0'] == 'RegenerateDeath'
                self.pending[e['inst']] = {'t': t, 'ts': ts, 'name': e['name'], 'oid': e['oid'], 'lp0': p[0],
                                           'lp': e['lp'], 'st0': p[1], 'st': e['stamina'], 'hitstate': p[2],
                                           's_after': e['s0'], 'path': path, 'reaction': None,
                                           'dist': e.get('dist', '?'), 'meter': lara['meter'],
                                           'active': lara['active'], 'scale': lara['scale'], 'regen': regen,
                                           'attack': e.get('attack', '-'), 'lara_lp': lara.get('lp'),
                                           'lara_states': lara.get('states'), 'cat': e.get('cat', '?'),
                                           'req_slots': lara.get('req_slots'), 'ramp_world': lara.get('ramp_world')}
            q = self.pending.get(e['inst'])
            if q:
                if q['reaction'] is None and e['s0'] != q['hitstate'] and e['s0'] != '-':
                    q['reaction'] = e['s0']
                if e['lp'] is not None:
                    q['lp'] = min(q['lp'], e['lp']) if t - q['t'] < 0.05 else q['lp']
                if t - q['t'] >= HIT_WINDOW:
                    q['fly'] = e.get('fly', '-')
                    self._finish(e['inst'], q)
            self.prev[e['inst']] = (e['lp'], e['stamina'], e['s0'])

    def _finish(self, inst, q):
        del self.pending[inst]
        reaction = q['reaction'] or '-'
        if q.get('regen'):
            reaction = 'finisher-in-RegenerateDeath'          # LP held the restored maximum, not damage (TU 0x8235dff8)
        line = ('%s combo: Lara records %s -> %s %s LP %.1f -> %.1f (-%.1f), stamina %s -> %s, state at the hit %s, '
                'reaction %s | xbox: dist %s, meter %s active %s, time scale %s | xbox+: kind %s, attack %s, fly %s, '
                'last flight %s, Lara LP %s, Lara states [%s], time requests %s, world ramp %s' % (
                    q['ts'], q['path'], q['name'], q['oid'], q['lp0'], q['lp'], q['lp0'] - q['lp'],
                    S.fmt(q['st0']), S.fmt(q['st']), q['hitstate'], reaction, q['dist'],
                    S.fmt(q['meter']), q['active'], S.fmt(q['scale'], '%.2f'), q.get('cat', '?'), q.get('attack', '-'),
                    q.get('fly', '-'), self.lastfly.get(inst, '-'), S.fmt(q.get('lara_lp')), q.get('lara_states'),
                    q.get('req_slots'), S.fmt(q.get('ramp_world'), '%.2f')))
        self.hits.append(line)
        self.hits = self.hits[-500:]
        if self.hitlog:
            self.hitlog.write(line + '\n')
            self.hitlog.flush()
        self.log.w('I', line)


WATCH_COLS = ('host_time', 'inst', 'obj_id', 'obj_name', 'lp', 'stamina', 'state0', 'state1', 'req', 'target', 'dist',
              'lara_rec0', 'lara_rec1', 'meter', 'active', 'time_scale',
              # stage 1b (appended; lara_rec0 / lara_rec1 are now record INDICES like the PC chart log)
              'kind', 'pos_x', 'pos_y', 'pos_z', 'speed', 'fly', 'last_flight', 'attack', 'ko_handle', 'lp_note',
              # ts_requests / ts_selected: same text as TruMenu 0.22.11 pc_ts_requests / pc_ts_selected
              'lara_lp', 'lara_states', 'lara_pos', 'ts_requests', 'ts_selected', 'ramp_player',
              'ramp_world', 'cam_mode', 'cam_flags',
              # 2026-11-10 lock-on path (K-5; PC side TruMenu 0.22.15 TruAim.log cm1fc / b9.. / t0_flags / t0_target)
              'aim_cm1fc', 'aim_bits', 'aim_t0_flags', 'aim_t0_target')


class Watch:
    def __init__(self, path, seconds):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.f = open(path, 'a', encoding='utf-8')
        if self.f.tell() == 0:
            self.f.write('\t'.join(WATCH_COLS) + '\n')
        self.until = time.time() + seconds
        self.path = path
        self.rows = 0

    def row(self, ts, enemies, lara):
        if time.time() > self.until:
            return
        lp = lara.get('pos')
        lpos = '%.0f %.0f %.0f' % lp if lp else '?'
        for e in enemies:
            pos = e.get('pos') or ('?', '?', '?')
            vals = (ts, '0x%08x' % e['inst'], e['oid'], e['name'], S.fmt(e['lp']), S.fmt(e['stamina'], '%.2f'), e['s0'],
                    e['s1'], e['req'], e['target'], e['dist'], lara['rec0'], lara['rec1'], S.fmt(lara['meter']),
                    lara['active'], S.fmt(lara['scale'], '%.2f'),
                    e.get('cat', '?'), *(('%.1f' % v) if isinstance(v, float) else v for v in pos), e.get('vel', '?'),
                    e.get('fly', '-'), e.get('lastfly', '-'), e.get('attack', '-'), e.get('ko_handle', '?'),
                    e.get('lp_note', '-'), S.fmt(lara.get('lp')), lara.get('states', '?'), lpos,
                    lara.get('req_slots', '?'), lara.get('req_selected', '?'),
                    S.fmt(lara.get('ramp_player'), '%.3f'), S.fmt(lara.get('ramp_world'), '%.3f'),
                    lara.get('cam_mode'), lara.get('cam_flags'),
                    S.fmt(lara.get('aim_w'), '0x%08x'), lara.get('aim_bits', '?'),
                    S.fmt(lara.get('aim_t0_flags'), '0x%x'), lara.get('aim_target', '?'))
            self.f.write('\t'.join(str(v) for v in vals) + '\n')
            self.rows += 1
        self.f.flush()

    def done(self):
        return time.time() > self.until


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
            return ['0x%08x %s %s [%s] LP %s%s st %s s0 %s s1 %s req %s target %s dist %s ko %s ko-handle %s '
                    'attack %s fly %s last-flight %s' % (
                        e['inst'], e['oid'], e['name'], e.get('cat', '?'), S.fmt(e['lp']),
                        '' if e.get('lp_note', '-') == '-' else ' (%s)' % e['lp_note'], S.fmt(e['stamina'], '%.2f'),
                        e['s0'], e['s1'], e['req'], e['target'], e['dist'], e['ko'], e.get('ko_handle', '?'),
                        e.get('attack', '-'), e.get('fly', '-'), e.get('lastfly', '-'))
                    for e in snap['enemies']] or ['no enemies']
        if c == 'lara':
            l = snap['lara']
            return ['records %s / %s, states [%s] / [%s], LP %s (max %s), pos %s, meter %s flags %s active %s, '
                    'time scale %s, doppelganger %s, time requests %s (winner player %s / world %s), ramps %s / %s, '
                    'camera mode %s flags %s position %s FOV %s, aim CM+0x1fc %s [%s] targeter 0 flags %s target %s' % (
                        l.get('rec0'), l.get('rec1'), l.get('states'), l.get('states1'), S.fmt(l.get('lp')),
                        S.fmt(l.get('lp_max')), ('%.0f %.0f %.0f' % l['pos']) if l.get('pos') else '?',
                        S.fmt(l.get('meter')), l.get('mflags'), l.get('active'), S.fmt(l.get('scale'), '%.2f'),
                        l.get('dopp'), l.get('req_slots'), l.get('win_player'), l.get('win_world'),
                        S.fmt(l.get('ramp_player'), '%.3f'), S.fmt(l.get('ramp_world'), '%.3f'), l.get('cam_mode'),
                        l.get('cam_flags'), l.get('cam_pos'), l.get('cam_fov'), S.fmt(l.get('aim_w'), '0x%08x'),
                        l.get('aim_bits'), S.fmt(l.get('aim_t0_flags'), '0x%x'), l.get('aim_target'))]
        if c == 'objects':
            want = parts[1].lower() if len(parts) > 1 else None
            return ['0x%08x %s %s [%s]%s dist %s' % (o['inst'], o['oid'], o['name'], o['cat'],
                                                    ' enemy' if o['enemy'] else '', o['dist'])
                    for o in snap.get('objects', []) if not want or o['cat'] == want] or ['no objects']
        if c == 'loaded':
            ld = snap.get('loaded') or {}
            if 'error' in ld:
                return [ld['error']]
            return ['object table %s: states %s, loaded %d' % (ld.get('time'), ld.get('counts'), len(ld.get('objects', [])))] + \
                ['%5s %s' % o for o in ld.get('objects', [])]
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
    root.geometry('1280x560')
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
    colour = {c[0]: c[1] for c in CATS}
    # page enemies
    pe = ttk.Frame(nb)
    nb.add(pe, text='')
    cols = ('cat', 'name', 'lp', 'stamina', 'state0', 'state1', 'req', 'target', 'dist', 'ko', 'kohandle', 'attack',
            'fly')
    tv = ttk.Treeview(pe, columns=cols, show='headings', height=16)
    for c, w in zip(cols, (110, 220, 55, 55, 130, 100, 100, 60, 55, 30, 90, 200, 110)):
        tv.column(c, width=w, anchor='w')
    for k in CAT_KEYS:
        tv.tag_configure(k, foreground=colour[k])
    tv.pack(fill='both', expand=True)
    # page objects (kinds with symbols, legend, filter)
    po = ttk.Frame(nb)
    nb.add(po, text='')
    fbar = ttk.Frame(po)
    fbar.pack(fill='x')
    fvars = {}
    fboxes = {}
    for k, col, de, en in CATS:
        v = tk.BooleanVar(value=True)
        fvars[k] = v
        cb = tk.Checkbutton(fbar, variable=v, fg=col, selectcolor='white')
        cb.pack(side='left', padx=2)
        fboxes[k] = cb
    ocols = ('cat', 'name', 'oid', 'enemy', 'dist')
    ov = ttk.Treeview(po, columns=ocols, show='headings', height=16)
    for c, w in zip(ocols, (190, 330, 70, 60, 70)):
        ov.column(c, width=w, anchor='w')
    for k in CAT_KEYS:
        ov.tag_configure(k, foreground=colour[k])
    ov.pack(fill='both', expand=True)
    # page lara
    pl = ttk.Frame(nb)
    nb.add(pl, text='')
    lara_txt = tk.StringVar()
    ttk.Label(pl, textvariable=lara_txt, justify='left', font=('Consolas', 11)).pack(anchor='nw', padx=8, pady=8)
    # page loaded data
    pd = ttk.Frame(nb)
    nb.add(pd, text='')
    ld_head = tk.StringVar()
    ttk.Label(pd, textvariable=ld_head, justify='left').pack(anchor='nw', padx=6, pady=4)
    ld_box = tk.Text(pd, height=18, font=('Consolas', 9))
    ld_box.pack(fill='both', expand=True)
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

    def cat_label(k, L):
        c = next(x for x in CATS if x[0] == k)
        return '● ' + (c[2] if L == 'de' else c[3])

    def texts():
        L = st['lang']
        root.title(tr('title', L))
        for i, k in enumerate(('enemies', 'objects', 'lara', 'loaded', 'loglink', 'saves')):
            nb.tab(i, text=tr(k, L))
        for c in cols:
            tv.heading(c, text=tr(c, L))
        for c in ocols:
            ov.heading(c, text=tr({'oid': 'name', 'enemy': 'enemies'}.get(c, c), L) if c not in ('oid', 'enemy')
                       else ('Id' if c == 'oid' else tr('enemies', L)))
        for k in CAT_KEYS:
            fboxes[k].config(text=cat_label(k, L))
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
    shown = [0, '']

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
            k = e.get('cat', 'other')
            tv.insert('', 'end', tags=(k,), values=(
                cat_label(k, L), '%s %s' % (e['name'], e['oid']),
                S.fmt(e['lp']) + ('*' if e.get('lp_note', '-') != '-' else ''), S.fmt(e['stamina'], '%.1f'),
                e['s0'], e['s1'], e['req'], e['target'], e['dist'], e['ko'], e.get('ko_handle', '?'),
                e.get('attack', '-'), e.get('fly', '-') if e.get('fly', '-') != '-' else e.get('lastfly', '-')))
        ov.delete(*ov.get_children())
        for o in snap.get('objects', []):
            if not fvars.get(o['cat'], fvars['other']).get():
                continue
            ov.insert('', 'end', tags=(o['cat'],), values=(cat_label(o['cat'], L), o['name'], o['oid'],
                                                           'x' if o['enemy'] else '', o['dist']))
        l = snap['lara']
        pos = ('%.0f %.0f %.0f' % l['pos']) if l.get('pos') else '?'
        lara_txt.set('%s: %s / %s   [%s] / [%s]\n%s: %s (max %s)\n%s: %s\n%s: %s (%s %s, flags %s)\n%s: %s\n'
                     '%s: %s  (player %s / world %s)\n%s: %s / %s\n%s: %s\n%s: mode %s, flags %s, position %s, FOV %s'
                     '\n%s: CM+0x1fc %s [%s], Z0 flags %s, %s %s' % (
                         tr('records', L), l.get('rec0'), l.get('rec1'), l.get('states'), l.get('states1'),
                         tr('laralp', L), S.fmt(l.get('lp')), S.fmt(l.get('lp_max')), tr('pos', L), pos,
                         tr('meter', L), S.fmt(l.get('meter')), tr('active', L), l.get('active'), l.get('mflags'),
                         tr('scale', L), S.fmt(l.get('scale'), '%.2f'), tr('requests', L), l.get('req_slots'),
                         l.get('win_player'), l.get('win_world'), tr('ramps', L), S.fmt(l.get('ramp_player'), '%.3f'),
                         S.fmt(l.get('ramp_world'), '%.3f'), tr('dopp', L), l.get('dopp'), tr('camera', L),
                         l.get('cam_mode'), l.get('cam_flags'), l.get('cam_pos'), l.get('cam_fov'),
                         tr('aim', L), S.fmt(l.get('aim_w'), '0x%08x'), l.get('aim_bits'),
                         S.fmt(l.get('aim_t0_flags'), '0x%x'), tr('target', L), l.get('aim_target')))
        ld = snap.get('loaded') or {}
        key = ld.get('time', '') if isinstance(ld, dict) else ''
        if key != shown[1]:
            shown[1] = key
            if 'error' in ld:
                ld_head.set(ld['error'])
            else:
                ld_head.set('%s: %s %s, %d %s\n%s' % (tr('objtable', L), 'states', ld.get('counts'),
                                                       len(ld.get('objects', [])), 'loaded (state 2)', tr('loadplan', L)))
            ld_box.delete('1.0', 'end')
            ld_box.insert('end', '\n'.join('%5s  %s' % o for o in ld.get('objects', [])))
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
    while time.time() - t0 < 3.6:                     # the last scripted event (2.6 s) + the hit window
        model.sample()
        time.sleep(0.05)
    import truxenia_cmd as C
    ok = True
    out = {}
    for cmd in ('status', 'enemies', 'lara', 'hits 9', 'saves', 'set 0x41000000 lp 1', 'objects', 'objects goo',
                'loaded'):
        out[cmd] = C.send(cmd, args.port)
        log.w('I', 'selftest link %s -> %s' % (cmd, ' | '.join(out[cmd])))

    def need(cond, what):
        nonlocal ok
        if not cond:
            ok = False
            log.w('E', 'selftest: %s' % what)

    allhits = '\n'.join(model.hits)
    need(len(model.hits) >= 4, 'expected >= 4 hit lines, got %d' % len(model.hits))
    need('reaction Hit ' in allhits or 'reaction Hit,' in allhits or 'reaction Hit |' in allhits,
         'no hit with reaction Hit')
    need(any('locked' in x for x in out['set 0x41000000 lp 1']), 'set was not refused while locked')
    need('1477>1488' in allhits, 'Lara record indices (1477>1488) not in the combo path')
    need('reaction finisher-in-RegenerateDeath' in allhits, 'RegenerateDeath finisher not labelled')
    need('attack rec 44000000 anim 1/50 1/51' in allhits, 'MeleeAttack record / anims not logged')
    need(any('[goo]' in x and 'enemy' not in x for x in out['objects goo']), 'goo spawner not classified as goo / non-enemy')
    need(not any('goo' in x for x in out['enemies']), 'goo spawner listed as enemy (brain test failed)')
    need(any('states [420 572 1900]' in x or 'states [' in x for x in out['lara']), 'Lara states missing')
    need(any('LP 1000.0' in x for x in out['lara']), 'Lara LP missing')
    need(any('0:1.20/0.30' in x and '4:0.02/1.00' in x and 'world 4' in x for x in out['lara']),
         'time-scale request slots / winner missing')
    need(model.snap['lara'].get('req_selected') == 'P0.02(s4) W1.00(s4)',
         'ts_selected %r, expected the TruMenu text P0.02(s4) W1.00(s4)' % model.snap['lara'].get('req_selected'))
    need('ts_requests' in WATCH_COLS and WATCH_COLS[:16][-1] == 'time_scale', 'watch columns: PC-compatible part changed')
    need(any('aim CM+0x1fc 0x000c0400 [9:0 10:1 11:0 18:1 19:1 20:0 21:0] targeter 0 flags 0x1 target '
             'viking_thrall_tutorial_dlc2_ 0x41000000' in x for x in out['lara']), 'aim: lock bits / targeter 0 target missing')
    wpath = os.path.join(os.path.dirname(os.path.abspath(args.log)), 'watch_selftest_%s.tsv' % time.strftime('%H%M%S'))
    w = Watch(wpath, 60)
    w.row(model.snap['time'], model.snap['enemies'], model.snap['lara'])
    w.f.close()
    wl = open(wpath, encoding='utf-8').read().splitlines()
    need(len(wl) >= 2 and all(len(r.split('\t')) == len(WATCH_COLS) for r in wl),
         'watch TSV: rows do not have %d fields' % len(WATCH_COLS))
    need(any('loaded 2' in x for x in out['loaded']), 'object table: expected 2 loaded objects')
    need(any('fly' in h for h in model.hits) and any(v != '-' for v in model.lastfly.values()), 'no flight measured')
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
