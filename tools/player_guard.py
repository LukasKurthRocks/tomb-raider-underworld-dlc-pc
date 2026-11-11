"""Player-path access guard (plan Spielerweg P0, gate G2): in "player mode" no tool may read the Xbox base game.

A player builds the port from the PC game + his own Xbox DLC packs + his TitleUpdate.000 + our recorded knowledge
(docs/Befund-Wissen-nur-Verweise-1111.md); the Xbox base game (layer1 / layer2, default.xex ...) and the developer
intermediate data made from it (pairs.pkl, store.pkl, idx_xbox_base.json, ...) are developer-only. This module checks
every file open / directory listing / process start of a Python tool process against the rules in
docs/data/playerpath_guard.json and logs each match.

Switch (environment, inherited by child processes): TRU_PLAYER_MODE
    unset / 0 / off   guard off (default; importing this module then does nothing but read the variable)
    report            log every match, refuse nothing (dry run: which steps would touch base-game paths)
    1 / on / enforce  refuse (PermissionError) every match of a category with action "refuse", log it
    anything else     treated as enforce (fail closed) with a warning
TRU_PLAYER_LOG = access log (TSV, appended by every process; default <workspace>/logs/player_guard_access.tsv).
Columns: time, pid, tool, mode, action (refused / would-refuse / logged / allowed / summary), category, event, count,
path. The first match of each (action, category, event, path) is written at once (and to stderr), a summary line
with the count of each at process exit.

Central hook: the common read helpers bigfile.py / archive.py / drm_reloc.py / drm_write.py import this module, so
every tool process (and its multiprocessing / subprocess children, which inherit the variable) that imports one of
them is guarded; Invoke-TruPipeline -PlayerMode runs every tool through "player_guard.py run" so a tool that imports
none of them is guarded too. Python audit hooks cannot be removed: once on, on for the life of the process.
The title update is a player input: only the file in the rules' "allow" list passes, after a raw md5 check (once per
process); any other file of the Xbox game folder is refused.

Usage (from the repository root):
  ../bin/pyt -t SEC tools/player_guard.py run [--mode report|enforce] TOOL.py [tool arguments ...]
        runs TOOL.py as __main__ with the guard on (--mode overrides TRU_PLAYER_MODE, default enforce); exit 2 when
        the guard refused anything in enforce mode, else the tool's exit code
  ../bin/pyt -t 60 tools/player_guard.py check PATH [PATH ...]
        prints the category / action of each path (no file is opened); exit 1 if any path would be refused
  ../bin/pyt -t 60 tools/player_guard.py summary LOG [--json OUT.json]
        counts per tool / action / category / event from an access log (uses the processes' summary lines)
  ../bin/pyt -t 120 tools/player_guard.py selftest
        classification of known paths + an enforce-mode open of layer1.000 that must be refused before the OS
        opens it (no base-game byte is read) + the title update allow path (md5); exit 1 on any failure
"""
import sys, os, re, json, hashlib, threading, time, atexit

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.realpath(os.path.join(HERE, '..'))
WS = os.path.dirname(REPO)
RULES_PATH = os.path.join(REPO, 'docs', 'data', 'playerpath_guard.json')
ENV_MODE, ENV_LOG = 'TRU_PLAYER_MODE', 'TRU_PLAYER_LOG'
MODES = {'': 'off', '0': 'off', 'off': 'off', 'report': 'report', '1': 'enforce', 'on': 'enforce', 'enforce': 'enforce'}
EVENTS = ('open', 'os.listdir', 'os.scandir', 'shutil.copyfile', 'shutil.copytree', 'os.startfile',
          'subprocess.Popen', '_winapi.CreateProcess', 'os.system', 'os.exec', 'os.spawn', 'os.posix_spawn')


def _slash(p):
    return p.replace('\\', '/').rstrip('/').lower()


def mode_from_env():
    v = os.environ.get(ENV_MODE, '').strip().lower()
    if v in MODES: return MODES[v]
    sys.stderr.write('player_guard: unknown %s=%r - treated as enforce\n' % (ENV_MODE, v))
    return 'enforce'


class Rules:
    """the categories / allow list of docs/data/playerpath_guard.json; classify() opens no file"""
    def __init__(self, path=RULES_PATH):
        with open(path, encoding='utf-8') as f: d = json.load(f)
        if d.get('schema') != 1: raise ValueError('%s: schema %r, expected 1' % (path, d.get('schema')))
        self.version, self.cats = d.get('version'), []
        for name, c in d['categories'].items():
            if c['action'] not in ('refuse', 'log'): raise ValueError('%s: action %r' % (name, c['action']))
            self.cats.append((name, c['action'], [p.lower() for p in c.get('ws', [])],
                              [p.lower() for p in c.get('repo', [])], [re.compile(x, re.I) for x in c.get('name', [])]))
        self.allow = {a['ws'].lower(): a for a in d.get('allow', [])}
        self.ws, self.repo = _slash(os.path.realpath(WS)), _slash(REPO)
        self.cache = {}

    @staticmethod
    def _hit(rel, pats):
        for p in pats:
            if p.endswith('/'):
                if rel == p[:-1] or rel.startswith(p): return p
            elif rel.startswith(p):
                return p
        return None

    def _rels(self, p, cwd=None):
        """[(path, rel workspace, rel repository)] as written and with junctions resolved (resolved one first)"""
        if cwd and not os.path.isabs(p): p = os.path.join(cwd, p)
        forms = []
        try: forms.append(_slash(os.path.realpath(p)))
        except (OSError, ValueError): pass
        a = _slash(os.path.abspath(p))
        if a not in forms: forms.append(a)
        out = []
        for f in forms:
            rw = f[len(self.ws) + 1:] if f.startswith(self.ws + '/') else None
            rr = f[len(self.repo) + 1:] if f.startswith(self.repo + '/') else None
            out.append((f, rw, rr))
        return out

    def classify(self, p, cwd=None):
        """(category, action, rule, real path) or None; category 'allow' = the allow list (action = its md5)"""
        key = (p, cwd)
        if key in self.cache: return self.cache[key]
        res, forms = None, self._rels(p, cwd)
        for f, rw, rr in forms:
            if rw is not None and rw in self.allow:
                res = ('allow', self.allow[rw]['md5'], rw, forms[0][0])
                break
        if res is None:
            for name, action, wsp, rp, nm in self.cats:
                for f, rw, rr in forms:
                    hit = (rw is not None and self._hit(rw, wsp)) or (rr is not None and self._hit(rr, rp)) or \
                        next((x.pattern for x in nm if x.search(f.rsplit('/', 1)[-1])), None)
                    if hit:
                        res = (name, action, hit, f); break
                if res: break
        if len(self.cache) < 200000: self.cache[key] = res
        return res


class Guard:
    def __init__(self):
        self.mode, self.rules, self.log = 'off', None, None
        self.tool = os.path.basename(sys.argv[0]) if sys.argv and sys.argv[0] else '?'
        self.counts, self.order, self.tu_ok = {}, [], {}
        self.refused = 0
        self.tls = threading.local()

    # ---------------------------------------------------------------- log
    def _write(self, rows):
        if not self.log: return
        self.tls.busy = True
        try:
            new = not os.path.exists(self.log)
            os.makedirs(os.path.dirname(self.log), exist_ok=True)
            fd = os.open(self.log, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, 'O_BINARY', 0), 0o644)
            try:
                txt = ''.join('\t'.join(str(x) for x in r) + '\n' for r in rows)
                if new: txt = 'time\tpid\ttool\tmode\taction\tcategory\tevent\tcount\tpath\n' + txt
                os.write(fd, txt.encode('utf-8'))
            finally:
                os.close(fd)
        except OSError as e:
            sys.stderr.write('player_guard: access log not written (%s)\n' % e)
        finally:
            self.tls.busy = False

    def _record(self, action, cat, event, path):
        k = (action, cat, event, path)
        n = self.counts.get(k, 0)
        self.counts[k] = n + 1
        if n == 0:
            self.order.append(k)
            now = time.strftime('%Y-%m-%d %H:%M:%S')
            self._write([(now, os.getpid(), self.tool, self.mode, action, cat, event, 1, path)])
            if action != 'allowed':
                sys.stderr.write('player_guard: %s %s %s %s (%s)\n' % (action, cat, event, path, self.tool))

    def summary(self):
        if not self.order: return
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        self._write([(now, os.getpid(), self.tool, self.mode, 'summary:' + k[0], k[1], k[2], self.counts[k], k[3])
                     for k in self.order])

    # ---------------------------------------------------------------- decision
    def _tu_md5_ok(self, real, want):
        if real not in self.tu_ok:
            self.tls.busy = True
            try:
                m = hashlib.md5()
                with open(real, 'rb') as f:
                    for b in iter(lambda: f.read(1 << 20), b''): m.update(b)
                self.tu_ok[real] = m.hexdigest() == want
            except OSError:
                self.tu_ok[real] = False
            finally:
                self.tls.busy = False
        return self.tu_ok[real]

    def decide(self, event, path, cwd=None):
        """classify one path; record it; raise PermissionError when it is refused in enforce mode"""
        c = self.rules.classify(path, cwd)
        if c is None: return
        cat, action, rule, real = c
        if cat == 'allow':
            if self._tu_md5_ok(real, action):
                self._record('allowed', 'tu_allow', event, real); return
            cat, action = 'xbox_base', 'refuse'
            real += ' (md5 differs from the allow list)'
        if action == 'log':
            self._record('logged', cat, event, real); return
        if self.mode == 'enforce':
            self.refused += 1
            self._record('refused', cat, event, real)
            raise PermissionError('player_guard refused (%s, %s): %s' % (cat, event, path))
        self._record('would-refuse', cat, event, real)

    def hook(self, event, args):
        if event not in EVENTS or getattr(self.tls, 'busy', False): return
        self.tls.busy = True
        try:
            paths, cwd = [], None
            if event in ('subprocess.Popen', '_winapi.CreateProcess', 'os.exec', 'os.spawn', 'os.posix_spawn'):
                # (executable, args, cwd, env) / (application, command line, cwd) / (path, args, env): every
                # argument that names a path (a command line string is split at blanks)
                argv = args[1] if len(args) > 1 else None
                if isinstance(argv, bytes): argv = argv.decode('utf-8', 'replace')
                if isinstance(argv, str): argv = [t.strip('"\'') for t in argv.split()]
                elif isinstance(argv, os.PathLike): argv = [argv]
                if event in ('subprocess.Popen', '_winapi.CreateProcess') and len(args) > 2 and isinstance(args[2], str):
                    cwd = args[2]
                paths = [a for a in (argv or []) if isinstance(a, (str, bytes, os.PathLike))]
            elif event == 'os.system':
                paths = [t.strip('"\'') for t in str(args[0]).split()] if args else []
            elif event in ('shutil.copyfile', 'shutil.copytree'):
                paths = [args[0]] if args else []
            else:
                p = args[0] if args else None
                if p is None and event in ('os.listdir', 'os.scandir'): p = '.'
                paths = [p]
            for p in paths:
                if p is None or isinstance(p, int): continue
                if isinstance(p, os.PathLike): p = os.fspath(p)
                if isinstance(p, bytes): p = p.decode('utf-8', 'replace')
                if not p or p.startswith('-'): continue
                try:
                    self.decide(event, p, cwd)
                except PermissionError:
                    raise
                except Exception as e:          # a guard bug must not change a tool's result; it is logged
                    self._record('guard-error', type(e).__name__, event, str(p))
        finally:
            self.tls.busy = False


GUARD = Guard()
_INSTALLED = False


def install(mode, log=None):
    """switch the guard on for this process (idempotent; the mode can only get stricter)"""
    global _INSTALLED
    if mode == 'off': return GUARD
    if GUARD.rules is None:
        try:
            GUARD.rules = Rules()
        except Exception as e:      # fail closed: player mode without readable rules must not run unguarded
            sys.stderr.write('player_guard: rules not readable (%s): %s\n' % (RULES_PATH, e))
            raise SystemExit(2)
    if GUARD.mode != 'enforce': GUARD.mode = mode
    GUARD.log = log or os.environ.get(ENV_LOG) or os.path.join(WS, 'logs', 'player_guard_access.tsv')
    if not _INSTALLED:
        sys.addaudithook(GUARD.hook)
        atexit.register(GUARD.summary)
        _INSTALLED = True
        # evidence that this process ran guarded (a run without any match leaves only these lines)
        GUARD._write([(time.strftime('%Y-%m-%d %H:%M:%S'), os.getpid(), GUARD.tool, GUARD.mode, 'guard-on', '-',
                       'start', 1, GUARD.rules.version)])
    return GUARD


def activate_from_env():
    m = mode_from_env()
    if m != 'off': install(m)
    return m


# ---------------------------------------------------------------- command line
def cmd_run(argv):
    mode = None
    if argv[:1] == ['--mode']:
        mode = argv[1].lower(); argv = argv[2:]
        if mode not in ('report', 'enforce'): sys.exit('--mode report|enforce')
    if not argv: sys.exit(__doc__)
    tool = argv[0]
    m = mode or mode_from_env()
    if m == 'off': m = 'enforce'                 # "run" always guards; without a mode it enforces
    os.environ[ENV_MODE] = m                     # child processes of the tool inherit it
    GUARD.tool = os.path.basename(tool)
    install(m)
    import runpy
    sys.argv = [tool] + argv[1:]
    sys.path.insert(0, os.path.dirname(os.path.abspath(tool)))
    code = 0
    try:
        runpy.run_path(tool, run_name='__main__')
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        if not isinstance(e.code, (int, type(None))): sys.stderr.write('%s\n' % e.code)
    except Exception:
        import traceback
        traceback.print_exc()
        code = 1
    if GUARD.mode == 'enforce' and GUARD.refused:
        sys.stderr.write('player_guard: %d access(es) refused in %s - exit 2\n' % (GUARD.refused, GUARD.tool))
        code = 2
    sys.stdout.flush()
    return code


def cmd_check(paths):
    r, bad = Rules(), 0
    for p in paths:
        c = r.classify(p)
        if c is None: print('%-14s %-8s %s' % ('-', 'ok', p)); continue
        cat, action, rule, real = c
        if cat == 'allow': print('%-14s %-8s %s  (md5 %s checked on open)' % ('tu_allow', 'allow', p, action)); continue
        print('%-14s %-8s %s  (rule %s)' % (cat, action, p, rule))
        bad += action == 'refuse'
    return 1 if bad else 0


def cmd_summary(log, out=None):
    rows = [l.rstrip('\n').split('\t') for l in open(log, encoding='utf-8') if l.strip()]
    rows = [r for r in rows[1:] if len(r) >= 9 and r[0] != 'time']
    agg, first = {}, {}
    pids_with_summary = {r[1] for r in rows if r[4].startswith('summary:')}
    for r in rows:
        t, pid, tool, mode, action, cat, ev, n, path = r[:9]
        if action.startswith('summary:'): action, n = action[8:], int(n)
        elif action == 'guard-on': n, path = 1, 'processes (rules %s)' % path
        elif pid in pids_with_summary: continue           # counted by that process's summary line
        else: n = 1
        k = (tool, action, cat, ev)
        a = agg.setdefault(k, dict(count=0, paths=set()))
        a['count'] += n; a['paths'].add(path)
    res = []
    for (tool, action, cat, ev), a in sorted(agg.items()):
        res.append(dict(tool=tool, action=action, category=cat, event=ev, count=a['count'], paths=sorted(a['paths'])))
        print('%-28s %-13s %-13s %-17s %7d  %s' % (tool, action, cat, ev, a['count'],
                                                    ', '.join(sorted(a['paths'])[:3]) + (' ...' if len(a['paths']) > 3 else '')))
    if not res: print('no matches in', log)
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, 'w', encoding='utf-8') as f: json.dump(dict(log=log, rows=res), f, indent=1)
    return 0


def cmd_selftest():
    r, fails = Rules(), []
    data = os.path.join(WS, 'data')
    cases = [
        (os.path.join(data, 'TombRaiderUnderworld_Patched', 'layer1.000'), 'xbox_base'),
        (os.path.join(WS, 'input', 'xbox-game', 'layer2.001'), 'xbox_base'),
        (os.path.join(WS, 'input', 'xbox-game', 'default.xex'), 'xbox_base'),
        (os.path.join(WS, 'input', 'xbox-game'), 'xbox_base'),
        (os.path.join(data, 'TombRaiderUnderworld_Patched', 'TitleUpdate.000'), 'allow'),
        (os.path.join(REPO, 'work', 'generic', 'pairs.pkl'), 'xbox_derived'),
        (os.path.join(REPO, 'work', 'generic', 'store.pkl'), 'xbox_derived'),
        (os.path.join(REPO, 'work', 'script', 'pairs_8.pkl'), 'xbox_derived'),
        (os.path.join(REPO, 'work', 'idx_xbox_base.json'), 'xbox_derived'),
        (os.path.join(REPO, 'work', 'xenia_dump', 'tu_image_82000000.bin'), 'xbox_derived'),
        (os.path.join(REPO, 'ref', 'yura-release', 'FileLists', 'x.txt'), 'yura'),
        (os.path.join(REPO, 'work', 'generic', 'idmap.json'), None),
        (os.path.join(REPO, 'work', 'generic', 'mask_table.pkl'), None),
        (os.path.join(REPO, 'work', 'idx_pc.json'), None),
        (os.path.join(data, 'pc', 'patch.000'), None),
        (os.path.join(data, 'Xenia-SteveRepack', 'Content', '534307EC', '00000002'), None),
        (os.path.join(REPO, 'docs', 'data', 'generalbank_pc.json'), None),
    ]
    for p, want in cases:
        c = r.classify(p)
        got = c[0] if c else None
        ok = got == want
        print('%-4s %-13s %s' % ('ok' if ok else 'FAIL', got, os.path.relpath(p, WS)))
        if not ok: fails.append(p)
    # enforce: the hook must refuse before the OS opens the file (no base-game byte is read)
    log = os.path.join(WS, 'logs', 'player_guard_selftest.tsv')
    if os.path.exists(log): os.remove(log)
    install('enforce', log=log)
    GUARD.tool = 'player_guard_selftest'
    layer = os.path.join(data, 'TombRaiderUnderworld_Patched', 'layer1.000')
    try:
        open(layer, 'rb').close(); print('FAIL enforce: layer1.000 opened'); fails.append('enforce open')
    except PermissionError as e:
        print('ok   enforce refused open:', e)
    try:
        os.listdir(os.path.join(WS, 'input', 'xbox-game')); print('FAIL enforce: listing allowed'); fails.append('list')
    except PermissionError:
        print('ok   enforce refused listing of the Xbox game folder')
    tu = os.path.join(data, 'TombRaiderUnderworld_Patched', 'TitleUpdate.000')
    if os.path.exists(tu):
        try:
            with open(tu, 'rb') as f: f.read(4)
            print('ok   title update allowed (md5 checked)')
        except PermissionError as e:
            print('FAIL title update refused:', e); fails.append('tu')
    else:
        print('skip title update (not present)')
    with open(os.path.join(REPO, 'docs', 'data', 'playerpath_guard.json'), 'rb') as f: f.read(1)
    print('ok   ordinary file opened')
    if GUARD.refused != 2: fails.append('refused count %d' % GUARD.refused)
    print('refused %d (expected 2), log %s' % (GUARD.refused, log))
    print('selftest:', 'FAILED %d' % len(fails) if fails else 'ok')
    return 1 if fails else 0


def main(argv):
    if not argv: sys.exit(__doc__)
    cmd = argv[0]
    if cmd == 'run': return cmd_run(argv[1:])
    if cmd == 'check': return cmd_check(argv[1:])
    if cmd == 'summary':
        out = argv[argv.index('--json') + 1] if '--json' in argv else None
        return cmd_summary(argv[1], out)
    if cmd == 'selftest': return cmd_selftest()
    sys.exit(__doc__)


if __name__ == '__main__':
    # the helpers' "import player_guard" must get this module, not a second copy with a second hook
    sys.modules.setdefault('player_guard', sys.modules['__main__'])
    sys.exit(main(sys.argv[1:]))
else:
    activate_from_env()
