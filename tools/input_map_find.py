"""Print / compare the game's input action map (generalbank DTP) - read-only; shadow combat night 2026-11-04
(condition 152 = input action record bit 0x10, docs/Befund-Schattenkampf.md "Nacht 04.11.").

Where the map is (proven on the PC code, tru.exe):
  * GlobalInfo = [0xe7ee50], set at tru+0x1df0bd from the generalbank object; GlobalInfo +0x1c -> a list of 4 DTP
    pointers (generalbank DTP 2 +0xf3c on PC / +0xf40 on the converted Xbox files: four id references of type 7);
    the input manager ctor tru+0x868b0 takes M = the first ([[GlobalInfo +0x1c]]) and passes it to the action list
    ctor tru+0x80bc0. PC generalbank: DTP 47; Xbox retail and TU generalbank: DTP 48.
  * M +0x00 u32 count, M +0x04 ptr -> count x 4-byte bindings {u8 action, u8 player, u8 source A, u8 source B}
    (0xff = no source; tru+0x80bc0 / reset tru+0x80b30 read them as bytes 0..3), M +0x08 u32 count2, M +0x0c ptr
    -> count2 x 0x18-byte records (tru+0x80d17 loop).
  * The action records (0x30 bytes, 256 per player at 0x9fcb68 + player x 0x3000) all start as 8 (= up, tru+0x80a50);
    only an action that has a binding ever changes (4 held, 0x10 pressed edge, 0x20 released edge, 8 up).

The 4 binding bytes are read in memory order (the Xbox code reads them with lbz, the PC with movzx byte), so for an
Xbox file use the original (tu:generalbank.drm / retail:generalbank.drm, big endian): a converter that swapped the
binding words as u32 shows them reversed.

Usage (from the repository root; FILE = a PC / converted DRM or tu:NAME / retail:NAME):
  ../bin/pyt -t 120 tools/input_map_find.py FILE.drm DTP_ID [--action A[,A..]] [--sources]   list the bindings
             (--sources: also the 0x18-byte source records as 6 words, with the actions that use each source)
  ../bin/pyt -t 120 tools/input_map_find.py diff A.drm DTP_A B.drm DTP_B              bindings only in A / only in B
"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drm_reloc as R, drm_idrefs as IR


def load_map(path, dtp):
    secs, e = IR.load(path)          # a PC / converted DRM (le) or tu:NAME / retail:NAME (Xbox original, be)
    s = next((s for s in secs if s[0] == 7 and s[1] == dtp), None)
    if s is None: sys.exit('%s: DTP %d not found' % (path, dtp))
    d = bytes(s[2]); f = '>I' if e == 'be' else '<I'
    it = dict(R.parse(bytes(s[3]), e).internal)
    n, n2 = struct.unpack_from(f, d, 0)[0], struct.unpack_from(f, d, 8)[0]
    b0, r0 = it.get(4), it.get(0xc)
    if b0 is None: sys.exit('%s DTP %d: +4 is not a pointer - not an input map' % (path, dtp))
    binds = [tuple(d[b0 + 4 * k:b0 + 4 * k + 4]) for k in range(n)]
    recs = [d[r0 + 0x18 * k:r0 + 0x18 * k + 0x18] for k in range(n2)] if r0 is not None else []
    return len(d), n, b0, n2, r0, binds, recs


def src(x):
    return '--' if x == 0xff else '%3d' % x


def main(argv):
    if len(argv) >= 5 and argv[0] == 'diff':
        A = load_map(argv[1], int(argv[2])); B = load_map(argv[3], int(argv[4]))
        ca, cb = collections.Counter(A[5]), collections.Counter(B[5])
        print('A: %s DTP %s: %d bindings, %d records; B: %s DTP %s: %d bindings, %d records'
              % (argv[1], argv[2], A[1], A[3], argv[3], argv[4], B[1], B[3]))
        for name, x, y in (('only in A', ca, cb), ('only in B', cb, ca)):
            rest = x - y
            print('%s: %d' % (name, sum(rest.values())))
            for e in sorted(rest.elements()):
                print('  action %3d player %d source %s / %s' % (e[0], e[1], src(e[2]), src(e[3])))
        return
    if len(argv) < 2: sys.exit(__doc__)
    acts = None
    if '--action' in argv:
        k = argv.index('--action'); acts = set(int(x) for x in argv[k + 1].split(',')); del argv[k:k + 2]
    size, n, b0, n2, r0, binds, recs = load_map(argv[0], int(argv[1]))
    print('%s DTP %s (0x%x bytes): %d bindings at +0x%x, %d records (0x18) at %s'
          % (argv[0], argv[1], size, n, b0, n2, '+0x%x' % r0 if r0 is not None else '-'))
    per = collections.defaultdict(list)
    for k, e in enumerate(binds): per[e[0]].append((k, e[1], e[2], e[3]))
    print('actions bound: %d (%d..%d)' % (len(per), min(per), max(per)))
    for a in sorted(per):
        if acts is not None and a not in acts: continue
        print('  action %3d: %s' % (a, '  '.join('#%d p%d %s/%s' % (k, p, src(x), src(y)) for k, p, x, y in per[a])))
    if acts:
        for a in sorted(acts - set(per)): print('  action %3d: no binding' % a)
    if '--sources' in sys.argv:
        f = '>6I' if argv[0].startswith(('tu:', 'retail:')) else '<6I'
        used = collections.defaultdict(list)
        for e in binds:
            for x in (e[2], e[3]):
                if x != 0xff: used[x].append('%d(s%d)' % (e[0], e[1]))
        for k, r in enumerate(recs):
            w = struct.unpack(f, r)
            print('  source %2d: %s   used by %s' % (k, ' '.join('%08x' % x for x in w), ' '.join(used.get(k, [])) or '-'))


if __name__ == '__main__':
    main(sys.argv[1:])
