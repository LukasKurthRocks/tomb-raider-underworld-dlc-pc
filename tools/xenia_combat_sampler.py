"""Read-only sampler for the Xbox side of the combat comparison (TODO N18): reads enemy LP / stamina / AI state and
Lara's chart record from a running Xenia (title update loaded) every --interval seconds and writes a TSV.

READ ONLY: the process is opened with PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION and only ReadProcessMemory /
GetExitCodeProcess are used - no debugger, no suspend, no write. Addresses and their proof (TU instruction words) come
from docs/data/xenia_tu_combat_addresses.json; before sampling, every proof word is compared with the guest memory and
the sampler refuses on a mismatch (wrong exe / no TU / moved base).

Xenia maps guest address A to host (base + A); base is 0x100000000 unless the MZ header is not found at base+0x82000000,
then 0x200000000 .. 0x800000000 are tried. Pages Xenia protects simply fail to read (logged at --trace, value '-').

Usage (from the repository root):
  ../bin/pyt -t 900 tools/xenia_combat_sampler.py --out ../logs/xenia_combat/run.tsv [--seconds 600] [--interval 0.1]
        [--all] [--verbose] [--debug] [--trace]
  ../bin/pyt -t 60 tools/xenia_combat_sampler.py --once          one snapshot to the console
  ../bin/pyt -t 60 tools/xenia_combat_sampler.py --check         only the proof words
  ../bin/pyt -t 60 tools/xenia_combat_sampler.py --dumpfile work/xenia_dump/dlc2_shadow_off_image.bin --check|--once
        offline: guest image dump (guest base 0x82000000) instead of the process (heap pointers then read as '-')

TSV columns: host_time, sample, inst, obj_id, obj_name, lp, stamina, state0, state1, lara_rec0, lara_rec1.
Default: one row per enemy whenever LP / stamina / state0 / state1 changed (first sample: all), plus a row
'lara' when Lara's chart records change; --all writes every enemy every sample.
Per-run log: --log PATH (default: the --out path + '.log'); --verbose adds per-second status lines to the log,
--debug the pointer chain of each new instance, --trace every failed read.
Exit codes: 0 ok, 1 proof mismatch / no Xenia / open refused, 2 usage.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ADDR_FILE = os.path.join(HERE, '..', 'docs', 'data', 'xenia_tu_combat_addresses.json')
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
TH32CS_SNAPPROCESS = 0x2
MAX_INST = 0x400


def h(x):
    return int(x, 16) if isinstance(x, str) else int(x)


class Log:
    def __init__(self, path, verbose, debug, trace):
        self.f = open(path, 'a', encoding='utf-8') if path else None
        self.verbose, self.debug, self.trace = verbose or debug or trace, debug or trace, trace

    def w(self, level, msg):
        if level == 'V' and not self.verbose: return
        if level == 'D' and not self.debug: return
        if level == 'T' and not self.trace: return
        line = '%s %s %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), level, msg)
        if self.f:
            self.f.write(line + '\n'); self.f.flush()
        if level in ('I', 'E'):
            print(line)


class ProcMem:
    """guest reads from xenia_canary.exe (read only)"""

    def __init__(self, log):
        self.log = log
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.k.OpenProcess.restype = wt.HANDLE
        self.k.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                             ctypes.POINTER(ctypes.c_size_t)]
        self.pid = self.find_pid('xenia_canary.exe')
        if not self.pid:
            raise RuntimeError('xenia_canary.exe is not running')
        self.hp = self.k.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION, False, self.pid)
        if not self.hp:
            raise RuntimeError('OpenProcess refused (error %d)' % ctypes.get_last_error())
        self.base = None
        for b in range(1, 9):
            cand = b << 32
            if self.raw(cand + 0x82000000, 2) == b'MZ':
                self.base = cand
                break
        if self.base is None:
            raise RuntimeError('no MZ header at base+0x82000000 for bases 0x100000000..0x800000000')
        log.w('I', 'Xenia pid %d, guest base 0x%x' % (self.pid, self.base))

    def find_pid(self, name):
        class PE(ctypes.Structure):
            _fields_ = [('dwSize', wt.DWORD), ('cntUsage', wt.DWORD), ('th32ProcessID', wt.DWORD),
                        ('th32DefaultHeapID', ctypes.c_void_p), ('th32ModuleID', wt.DWORD), ('cntThreads', wt.DWORD),
                        ('th32ParentProcessID', wt.DWORD), ('pcPriClassBase', ctypes.c_long), ('dwFlags', wt.DWORD),
                        ('szExeFile', ctypes.c_char * 260)]
        self.k.CreateToolhelp32Snapshot.restype = wt.HANDLE
        snap = self.k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        e = PE(); e.dwSize = ctypes.sizeof(PE)
        pid = 0
        ok = self.k.Process32First(snap, ctypes.byref(e))
        while ok:
            if e.szExeFile.decode('mbcs', 'replace').lower() == name:
                pid = e.th32ProcessID
                break
            ok = self.k.Process32Next(snap, ctypes.byref(e))
        self.k.CloseHandle(snap)
        return pid

    def raw(self, host, n):
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t(0)
        if self.k.ReadProcessMemory(self.hp, ctypes.c_void_p(host), buf, n, ctypes.byref(got)) and got.value == n:
            return buf.raw
        self.log.w('T', 'read failed host 0x%x n %d (error %d)' % (host, n, ctypes.get_last_error()))
        return None

    def read(self, guest, n):
        return self.raw(self.base + guest, n) if guest else None

    def alive(self):
        code = wt.DWORD(0)
        self.k.GetExitCodeProcess(self.hp, ctypes.byref(code))
        return code.value == STILL_ACTIVE


class DumpMem:
    """guest reads from an image dump file (guest base 0x82000000)"""

    def __init__(self, path, log):
        self.d = open(path, 'rb').read()
        self.log = log
        self.pid, self.base = 0, 0
        log.w('I', 'dump %s, %d bytes at guest 0x82000000' % (path, len(self.d)))

    def read(self, guest, n):
        o = guest - 0x82000000
        if guest and 0 <= o and o + n <= len(self.d):
            return self.d[o:o + n]
        self.log.w('T', 'dump: guest 0x%08x outside the image' % guest)
        return None

    def alive(self):
        return True


def u32(m, a):
    b = m.read(a, 4)
    return struct.unpack('>I', b)[0] if b else None


def f32(m, a):
    b = m.read(a, 4)
    return struct.unpack('>f', b)[0] if b else None


def cstr(m, a, maxlen=64):
    if not a: return None
    b = m.read(a, maxlen)
    if not b: return None
    s = b.split(b'\0', 1)[0]
    try:
        t = s.decode('ascii')
    except UnicodeDecodeError:
        return None
    return t if t and all(32 <= ord(c) < 127 for c in t) else None


def check_proof(m, A, log):
    bad = 0
    n = 0
    for sec in ('instance_list', 'object', 'brain', 'lara_chart'):
        for addr, word in A[sec]['proof'].items():
            n += 1
            got = u32(m, h(addr))
            if got != h(word):
                bad += 1
                log.w('E', 'proof %s %s: expected %s, got %s' % (sec, addr, word, 'unreadable' if got is None else '0x%08x' % got))
            else:
                log.w('D', 'proof %s %s ok' % (sec, addr))
    log.w('I', 'proof words: %d checked, %d mismatches' % (n, bad))
    return bad == 0


def fmt(v, f='%.1f'):
    return '-' if v is None else (f % v)


def sample(m, A, log, seen):
    """one snapshot: list of enemy dicts + (rec0, rec1)"""
    il, ob, br, lc = A['instance_list'], A['object'], A['brain'], A['lara_chart']
    out = []
    inst = u32(m, h(il['head']))
    visited = set()
    while inst and inst not in visited and len(visited) < MAX_INST:
        visited.add(inst)
        holder = u32(m, inst + 0x2d0)
        h0 = u32(m, holder) if holder else None
        brain = u32(m, h0 + 0x2ec) if h0 else None
        if brain:
            obj = u32(m, inst + h(ob['instance_object_offset']))
            oid = u32(m, obj + h(ob['object_id_offset'])) if obj else None
            name = cstr(m, u32(m, obj + h(ob['object_name_ptr_offset']))) if obj else None
            st = []
            for k in ('state_layer0', 'state_layer1'):
                so = u32(m, brain + h(br[k]))
                st.append((cstr(m, u32(m, so + h(br['state_name_offset']))) or ('0x%08x' % so)) if so else '-')
            e = {'inst': inst, 'oid': oid, 'name': name or '?', 'lp': f32(m, brain + h(br['lp'])),
                 'stamina': f32(m, brain + h(br['stamina'])), 's0': st[0], 's1': st[1]}
            if inst not in seen:
                log.w('D', 'new enemy inst 0x%08x holder 0x%08x -> 0x%08x brain 0x%08x obj 0x%08x id %s %s' % (
                    inst, holder or 0, h0 or 0, brain, obj or 0, oid, e['name']))
            out.append(e)
        inst = u32(m, inst + h(il['next_offset']))
    trk = u32(m, h(lc['player_tracker_ptr']))
    recs = []
    for k in ('machine0_offset', 'machine1_offset'):
        mac = u32(m, trk + h(lc[k])) if trk else None
        r = u32(m, mac + h(lc['record_offset'])) if mac else None
        recs.append(None if r is None else struct.unpack('>i', struct.pack('>I', r))[0])
    log.w('D', 'walk: %d instances visited, %d with a brain' % (len(visited), len(out)))
    return out, tuple(recs)


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--out')
    ap.add_argument('--log')
    ap.add_argument('--seconds', type=float, default=600.0)
    ap.add_argument('--interval', type=float, default=0.1)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--dumpfile')
    ap.add_argument('--force', action='store_true', help='sample even when proof words differ (not recommended)')
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--debug', action='store_true')
    ap.add_argument('--trace', action='store_true')
    a = ap.parse_args()
    if not (a.out or a.once or a.check):
        print(__doc__)
        return 2
    logpath = a.log or (a.out + '.log' if a.out else None)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    log = Log(logpath, a.verbose, a.debug, a.trace)
    A = json.load(open(ADDR_FILE, encoding='utf-8'))
    log.w('I', 'xenia_combat_sampler start (%s)' % ' '.join(sys.argv[1:]))
    try:
        m = DumpMem(a.dumpfile, log) if a.dumpfile else ProcMem(log)
    except Exception as ex:
        log.w('E', str(ex))
        return 1
    ok = check_proof(m, A, log)
    if a.check:
        return 0 if ok else 1
    if not ok and not a.force:
        log.w('E', 'refusing to sample: proof words differ (use --force only if you know why)')
        return 1
    if a.once:
        head = u32(m, h(A['instance_list']['head']))
        cnt = u32(m, h(A['instance_list']['struct']))
        trk = u32(m, h(A['lara_chart']['player_tracker_ptr']))
        names = u32(m, h(A['object']['name_table']))
        print('globals: instance count %s, head %s, player tracker %s, name table %s' % tuple(
            '-' if v is None else '0x%08x' % v for v in (cnt, head, trk, names)))
        es, recs = sample(m, A, log, set())
        print('lara chart records: %s / %s' % recs)
        for e in es:
            print('0x%08x id %s %-34s LP %s stamina %s state %s / %s' % (
                e['inst'], e['oid'], e['name'], fmt(e['lp']), fmt(e['stamina']), e['s0'], e['s1']))
        print('%d enemies' % len(es))
        return 0
    f = open(a.out, 'a', encoding='utf-8')
    if f.tell() == 0:
        f.write('host_time\tsample\tinst\tobj_id\tobj_name\tlp\tstamina\tstate0\tstate1\tlara_rec0\tlara_rec1\n')
    last, lastrec, seen = {}, None, set()
    t0 = time.time(); n = 0; nextstat = t0 + 1.0; rows = 0
    while time.time() - t0 < a.seconds:
        if not m.alive():
            log.w('I', 'Xenia exited - stop')
            break
        ts = time.strftime('%H:%M:%S') + '.%03d' % int((time.time() % 1) * 1000)
        es, recs = sample(m, A, log, seen)
        n += 1
        for e in es:
            key = (e['lp'], e['stamina'], e['s0'], e['s1'])
            if a.all or last.get(e['inst']) != key:
                f.write('%s\t%d\t0x%08x\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                    ts, n, e['inst'], e['oid'], e['name'], fmt(e['lp']), fmt(e['stamina'], '%.2f'), e['s0'], e['s1'],
                    recs[0], recs[1]))
                rows += 1
                last[e['inst']] = key
            seen.add(e['inst'])
        if recs != lastrec:
            f.write('%s\t%d\tlara\t-\t-\t-\t-\t-\t-\t%s\t%s\n' % (ts, n, recs[0], recs[1]))
            rows += 1
            lastrec = recs
        f.flush()
        if time.time() >= nextstat:
            log.w('V', 'samples %d, enemies %d, rows %d, lara %s / %s' % (n, len(es), rows, recs[0], recs[1]))
            print('\r%s samples %d enemies %d rows %d' % (ts, n, len(es), rows), end='', flush=True)
            nextstat += 1.0
        time.sleep(max(0.0, a.interval))
    print()
    log.w('I', 'done: %d samples, %d rows -> %s' % (n, rows, a.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
