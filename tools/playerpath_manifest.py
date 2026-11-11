"""Player-path manifest (plan Spielerweg P0): what a player brings and what knowledge we ship - names and hashes only.

docs/data/playerpath_manifest.json lists
  player_inputs  the PC game files the pipeline reads (bigfile.000 - .003, patch.000) and tru.exe, the Xbox DLC
                 content folders (DLC 1 pack10, DLC 2 pack11, costume packs pack1 / pack2 / pack20: every file with size
                 and md5) and TitleUpdate.000 (whole-file md5 + the raw md5 of its generalbank record from
                 docs/data/generalbank_pc.json), each with the reference it was checked against
  knowledge      every file of docs/data (size and md5 with LF line ends for text files - the same on every checkout -,
                 its own version / schema field when it has one)
  guard          the access guard rules (docs/data/playerpath_guard.json) and the developer-only inputs it refuses
No game byte is written; the game folder is never listed (fixed file names only).

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/playerpath_manifest.py build [--out JSON] [--pc DIR] [--dlc DIR] [--tu FILE]
        hashes the inputs on this PC and writes the manifest (default docs/data/playerpath_manifest.json); a PC
        archive whose md5 differs from docs/data/pc_game_files.tsv is reported (exit 1, manifest still written)
  ../bin/pyt -t 1800 tools/playerpath_manifest.py check [--manifest JSON] [--pc DIR] [--dlc DIR] [--tu FILE]
                                                       [--skip-pc] [--knowledge-only]
        gate G1: re-hashes the player's inputs (default the workspace junctions) and the knowledge files and compares
        them with the manifest; exit 0 = all equal, 1 = a difference / a missing file (list printed)
Defaults: --pc ../data/pc, --dlc ../data/Xenia-SteveRepack/Content/534307EC/00000002,
          --tu ../data/TombRaiderUnderworld_Patched/TitleUpdate.000
"""
import sys, os, json, hashlib, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.realpath(os.path.join(HERE, '..'))
DATA = os.path.join(REPO, 'docs', 'data')
OUT = os.path.join(DATA, 'playerpath_manifest.json')
PC_DIR = '../data/pc'
DLC_DIR = '../data/Xenia-SteveRepack/Content/534307EC/00000002'
TU_FILE = '../data/TombRaiderUnderworld_Patched/TitleUpdate.000'
VERSION = 'M20261111-1'
PC_FILES = ('bigfile.000', 'bigfile.001', 'bigfile.002', 'bigfile.003', 'patch.000', 'tru.exe')
# content folder -> what it is (Invoke-TruPipeline step Index, docs/WINDOWS_REBUILD.md)
DLC = [('9CA70CF0EDA43654D158C2E37470D301DFA850E753', 'pack10', 'DLC 1 Beneath the Ashes'),
       ('600A12643FCDAC84003E6E0DBD0A1A8F7DAE9DD153', 'pack11', "DLC 2 Lara's Shadow"),
       ('E5AFB2B959A72C52120D73678AED11BD8752686753', 'pack1', 'costume pack'),
       ('9FDDD06617D1016DE468ACF53AC663E8BA2AD41853', 'pack2', 'costume pack'),
       ('AC0089F81B621CD0E0C156B6176EFCC6C844705D53', 'pack20', 'costume pack')]
# developer-only inputs (never on the player path; refused by tools/player_guard.py in player mode)
DEV_ONLY = ['Xbox base game layer1.000 / .001, layer2.000 / .001, default.xex, default.xexp, $SystemUpdate, movies',
            'Xenia memory images work/xenia_dump (retail / title update exe)',
            'developer intermediate data: work/generic/pairs.pkl, pairs_patch.pkl, store.pkl (xb_store part), '
            'work/idx_xbox_base.json, work/script/pairs_*.pkl, work/render/pairs_render.pkl, shaderlibs.pkl, '
            'work/ws/cine/pairs.pkl']


def digest(p):
    m = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''): m.update(b)
    return m.hexdigest(), os.path.getsize(p)


def pc_reference():
    ref = {}
    for l in open(os.path.join(DATA, 'pc_game_files.tsv'), encoding='utf-8'):
        f = l.rstrip('\r\n').split('\t')
        if len(f) == 3 and f[0] != 'file': ref[f[0].lower()] = (int(f[1]), f[2])
    return ref


def dlc_files(root, folder):
    d = os.path.join(root, folder)
    out = []
    for dp, dn, fn in os.walk(d):
        dn.sort()
        for n in sorted(fn):
            q = os.path.join(dp, n)
            m, s = digest(q)
            out.append(dict(file=os.path.relpath(q, d).replace('\\', '/'), size=s, md5=m))
    return out


TEXT = ('.json', '.tsv', '.txt', '.md')


def digest_lf(p):
    """md5 / size of a knowledge file; text files with CRLF -> LF first (the same on every checkout, autocrlf)"""
    b = open(p, 'rb').read()
    if p.lower().endswith(TEXT): b = b.replace(b'\r\n', b'\n')
    return hashlib.md5(b).hexdigest(), len(b)


def knowledge(skip=('playerpath_manifest.json',)):
    rows = []
    for n in sorted(os.listdir(DATA), key=str.lower):
        p = os.path.join(DATA, n)
        if not os.path.isfile(p) or n in skip or 'truguard' in n.lower(): continue
        m, s = digest_lf(p)
        row = dict(file='docs/data/' + n, size_lf=s, md5_lf=m)
        if n.endswith('.json'):
            try:
                d = json.load(open(p, encoding='utf-8'))
                if isinstance(d, dict):
                    for k in ('version', 'schema'):
                        if k in d and isinstance(d[k], (str, int)): row[k] = d[k]
            except ValueError:
                row['note'] = 'not valid JSON'
        rows.append(row)
    return rows


def opt(argv, k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


def cmd_build(argv):
    out = opt(argv, '--out', OUT); pc = opt(argv, '--pc', PC_DIR); dlc = opt(argv, '--dlc', DLC_DIR)
    tu = opt(argv, '--tu', TU_FILE)
    t0, bad = time.time(), []
    ref = pc_reference()
    pcrows = []
    for n in PC_FILES:
        p = os.path.join(pc, n)
        r = dict(name=n)
        if n.lower() in ref: r['reference_size'], r['reference_md5'] = ref[n.lower()]
        if os.path.isfile(p):
            m, s = digest(p)
            if n == 'tru.exe':      # not an input of the archive steps; the folder's exe may be an installed build
                r['measured_md5_here'], r['measured_size_here'] = m, s
                r['match'] = m == r.get('reference_md5')
                r['note'] = ('not gated: the Exe step reads the Steamless-unpacked Steam exe; reference_md5 = '
                             'docs/data/pc_game_files.tsv (initial import), the measured exe here is ' +
                             ('the reference' if r['match'] else 'another build (installed)'))
            else:
                r['md5'], r['size'] = m, s
                r['match'] = m == r.get('reference_md5')
                if not r['match']: bad.append('PC %s md5 %s != reference %s' % (n, m, r.get('reference_md5')))
            print('pc   %-12s %s  %s' % (n, m, 'ok' if r['match'] else 'differs from reference'))
        else:
            r['missing'] = True; bad.append('PC %s missing' % n)
            print('pc   %-12s missing' % n)
        pcrows.append(r)
    dlcrows = []
    for folder, pack, what in DLC:
        files = dlc_files(dlc, folder) if os.path.isdir(os.path.join(dlc, folder)) else None
        if files is None: bad.append('DLC folder %s missing' % folder)
        dlcrows.append(dict(content=folder, pack=pack, what=what, files=files or []))
        print('dlc  %-7s %-42s %d files' % (pack, folder, len(files or [])))
    gb = json.load(open(os.path.join(DATA, 'generalbank_pc.json'), encoding='utf-8'))['tu']
    tum, tus = digest(tu)
    print('tu   TitleUpdate.000 %s (%d bytes)' % (tum, tus))
    guard = json.load(open(os.path.join(DATA, 'playerpath_guard.json'), encoding='utf-8'))
    allow = [a for a in guard['allow'] if a['ws'].endswith('titleupdate.000')]
    if allow and allow[0]['md5'] != tum: bad.append('TitleUpdate.000 md5 %s != guard allow list %s' % (tum, allow[0]['md5']))
    man = dict(
        schema=1, version=VERSION, generated=time.strftime('%Y-%m-%d'),
        about=('Player-path manifest (plan Spielerweg P0): the inputs a player brings (PC game, own Xbox DLC packs, own '
               'TitleUpdate.000) and the knowledge files of the repository, by name and hash only (no game bytes). '
               'Written by tools/playerpath_manifest.py build; gate G1 = tools/playerpath_manifest.py check.'),
        player_inputs=dict(
            pc_game=dict(where='Steam game folder (workspace junction data/pc)', reference='docs/data/pc_game_files.tsv',
                         note=('the pipeline reads the archives bigfile.000 - .003 and patch.000; tru.exe: the Exe step '
                               'reads the Steamless-unpacked Steam exe (md5 56d1ce2dffa62f16354063da2df44d5a, '
                               'tools/exe_build.py), the tru.exe of a played game folder may already be a patched one'),
                         files=pcrows),
            xbox_dlc=dict(where='Xbox 360 content folder 534307EC/00000002 (workspace junction '
                                'data/Xenia-SteveRepack/Content/534307EC/00000002), Xenia-extracted folders',
                          packs=dlcrows),
            title_update=dict(name='TitleUpdate.000', where='workspace data/TombRaiderUnderworld_Patched (the player '
                                                            'supplies only this file of the Xbox game folder)',
                              size=tus, md5=tum, generalbank_record=dict(name=gb['name'], raw_md5=gb['raw_md5'],
                                                                         raw_size=gb['raw_size'],
                                                                         checked_by='tools/generalbank_pc_build.py'))),
        knowledge=knowledge(),
        guard=dict(rules='docs/data/playerpath_guard.json', version=guard['version'],
                   tool='tools/player_guard.py', switch='TRU_PLAYER_MODE=report|enforce, Invoke-TruPipeline '
                                                        '-PlayerMode Report|Enforce (-Player)',
                   developer_only=DEV_ONLY),
        problems=bad)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(man, f, indent=1, ensure_ascii=False); f.write('\n')
    print('wrote %s: %d PC files, %d DLC files, %d knowledge files, %d problem(s), %.0f s' % (
        out, len(pcrows), sum(len(d['files']) for d in dlcrows), len(man['knowledge']), len(bad), time.time() - t0))
    for b in bad: print('  PROBLEM', b)
    return 1 if bad else 0


def cmd_check(argv):
    man = json.load(open(opt(argv, '--manifest', OUT), encoding='utf-8'))
    pc = opt(argv, '--pc', PC_DIR); dlc = opt(argv, '--dlc', DLC_DIR); tu = opt(argv, '--tu', TU_FILE)
    only_k = '--knowledge-only' in argv
    diff, n = [], 0

    def cmp(label, p, want, lf=False):
        nonlocal n
        n += 1
        if not os.path.isfile(p): diff.append('%s missing' % label); return
        m, _ = digest_lf(p) if lf else digest(p)
        if m != want: diff.append('%s md5 %s != %s' % (label, m, want))
    if not only_k:
        if '--skip-pc' not in argv:
            for r in man['player_inputs']['pc_game']['files']:
                if r['name'] == 'tru.exe' or r.get('missing'): continue
                cmp('PC ' + r['name'], os.path.join(pc, r['name']), r['md5'])
        for d in man['player_inputs']['xbox_dlc']['packs']:
            for f in d['files']:
                cmp('%s %s' % (d['pack'], f['file']), os.path.join(dlc, d['content'], f['file']), f['md5'])
        cmp('TitleUpdate.000', tu, man['player_inputs']['title_update']['md5'])
    for k in man['knowledge']:
        cmp(k['file'], os.path.join(REPO, k['file']), k['md5_lf'], lf=True)
    for x in diff: print('  DIFF', x)
    print('G1 check: %d files compared, %d difference(s)' % (n, len(diff)))
    return 1 if diff else 0


def main(argv):
    if not argv or argv[0] not in ('build', 'check'):
        sys.stderr.write(__doc__); return 2
    return cmd_build(argv[1:]) if argv[0] == 'build' else cmd_check(argv[1:])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
