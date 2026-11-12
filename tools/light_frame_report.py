"""Read TruMenu light captures offline and name the lights (read-only; N7 throne light #94, 2026-11-10).

Two inputs, both written by TruMenu (README 0.21.11 / 0.22.2 / 0.22.10):
  * a `TruMenu.lightframe.txt` dump (`light.frame`): per frame the light instances E (0x80 bytes each) - decoded here:
    E+0x00 light L, E+0x10 position (vec4), E+0x20 direction (vec4), E+0x3c resource slot (f32, (slot + 0.5) / 128),
    E+0x40 / +0x44 two floats, E+0x50..+0x5c colour R, G, B and a fourth float (colour x flicker, ENGINE.md 16),
    E+0x60 slot in the frame list, E+0x64 / +0x65 run-time flags;
  * a copy of `TruMenu.log` with `light.list` / `light.cut` lines: the light index `#n` (place in the scene array
    [scene+0x1c]), address, kind and position of every light, and per captured frame the light sets that dropped a
    light (`+` kept, `-` dropped, `.` not looked at).

Lights are matched across the two by position (addresses change with every level load; the scene index #n stays as long
as the same lights are created in the same order). Only reads the given files.

Usage (from the repository root):
  ../bin/pyt -t 300 tools/light_frame_report.py frames LIGHTFRAME.txt [--log TruMenu.log] [--tol 2.0]
      per light of the dump: position, direction, colour (mean, min..max of R, G, B, w over all frames), the two
      floats E+0x40 / +0x44, and the `#n` / kind of the `light.list` / `light.cut` light at the same position
  ../bin/pyt -t 300 tools/light_frame_report.py cuts TruMenu.log [--from HH:MM:SS] [--to HH:MM:SS] [--only 90,93,94]
      per `light.cut` frame: every distinct cut set (caller, offered order with +/-) once per frame and how often it
      occurred; with --only just the sets that contain one of these indexes; ends with the dropped lights per frame
"""
import sys, os, re, struct, collections

TIME = r'(?:[0-9]{4}-[0-9]{2}-[0-9]{2} )?([0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]+)'   # log stamp [YYYY-MM-DD ]HH:MM:SS.mmm (Q107)
CUT_RE = re.compile(r'^' + TIME + r' light\.cut f(\d+) caller (0x[0-9a-f]+): (\d+) offered -> (\d+) kept '
                    r'\(([^)]*)\) drop (\d+), not looked at (\d+) \| list (.*)$')
ITEM_RE = re.compile(r'([+\-.])#(\d+) (0x[0-9a-f]+) ([a-z ]+?) \((-?[\d.]+) (-?[\d.]+) (-?[\d.]+)\)')
LIST_RE = re.compile(r'^' + TIME + r' light\.list #(\d+) (0x[0-9a-f]+) type (\d+) \+0xc5 (0x[0-9a-f]+).*?'
                     r'res (0x[0-9a-f]+) \+0x42c (\d+).*?CastsShadow (\d).*?pos (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)')


def f32(b, o):
    return struct.unpack_from('<f', b, o)[0]


def read_frames(path):
    """lightframe dump -> list of frames, each {light address: E bytes}."""
    frames, cur = [], None
    for ln in open(path, encoding='latin-1'):
        p = ln.split()
        if not p: continue
        if p[0] == 'F':
            cur = {}; frames.append(cur)
        elif p[0] == 'E' and cur is not None and len(p) >= 6 and p[3] == 'L':
            cur[p[4]] = bytes.fromhex(p[5])
    return frames


def decode(e):
    return dict(pos=tuple(f32(e, 0x10 + 4 * i) for i in range(3)), dir=tuple(f32(e, 0x20 + 4 * i) for i in range(3)),
                rslot=f32(e, 0x3c), a40=f32(e, 0x40), a44=f32(e, 0x44),
                col=tuple(f32(e, 0x50 + 4 * i) for i in range(4)), slot=struct.unpack_from('<I', e, 0x60)[0],
                fl=(e[0x64], e[0x65]))


def log_lights(path):
    """TruMenu.log -> {index: (kind text, position, address, source)} from light.list and light.cut lines."""
    out = {}
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = LIST_RE.match(ln.rstrip('\n'))
        if m:
            kind = 'type %s, CastsShadow %s, +0xc5 %s, res+0x42c %s' % (m.group(4), m.group(8), m.group(5), m.group(7))
            out.setdefault(int(m.group(2)), (kind, tuple(float(m.group(k)) for k in (9, 10, 11)), m.group(3), 'list'))
            continue
        m = CUT_RE.match(ln.rstrip('\n'))
        if m:
            for it in ITEM_RE.finditer(m.group(9)):
                out.setdefault(int(it.group(2)), (it.group(4), tuple(float(it.group(k)) for k in (5, 6, 7)), it.group(3), 'cut'))
    return out


def frames_cmd(a):
    path = a[0]
    tol = float(a[a.index('--tol') + 1]) if '--tol' in a else 2.0
    known = log_lights(a[a.index('--log') + 1]) if '--log' in a else {}
    frames = read_frames(path)
    lights = collections.OrderedDict()
    for fr in frames:
        for L, e in fr.items(): lights.setdefault(L, []).append(decode(e))
    print('%s: %d frames, %d lights' % (os.path.basename(path), len(frames), len(lights)))
    for L, ds in lights.items():
        d0 = ds[0]
        cols = list(zip(*[d['col'] for d in ds]))
        mean = [sum(c) / len(c) for c in cols]
        rng = ['%.3f..%.3f' % (min(c), max(c)) for c in cols]
        tag = ''
        for idx, (kind, pos, addr, src) in sorted(known.items()):
            if max(abs(pos[i] - d0['pos'][i]) for i in range(3)) <= tol:
                tag = '#%d (%s, %s %s)' % (idx, kind, src, addr); break
        rgb = mean[:3]
        hue = 'cool' if rgb[2] > rgb[0] * 1.15 else 'warm' if rgb[0] > rgb[2] * 1.15 else 'neutral'
        print('light %s in %d frames  pos %.1f %.1f %.1f  dir %.3f %.3f %.3f  %s' % (
            L, len(ds), *d0['pos'], *d0['dir'], tag or '(no log light at this position)'))
        print('    colour mean R %.3f G %.3f B %.3f w %.3f -> %s | ranges R %s G %s B %s w %s | E+0x40 %.1f E+0x44 %.1f | '
              'slot %s | E+0x3c %s' % (*mean, hue, *rng, d0['a40'], d0['a44'],
                                       sorted(set(d['slot'] for d in ds)), sorted(set(round(d['rslot'] * 128 - 0.5) for d in ds))))
    return 0


def cuts_cmd(a):
    path = a[0]
    t0 = a[a.index('--from') + 1] if '--from' in a else '00:00:00'
    t1 = a[a.index('--to') + 1] if '--to' in a else '99:99:99'
    only = set(int(x) for x in a[a.index('--only') + 1].split(',')) if '--only' in a else None
    per = collections.OrderedDict()
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = CUT_RE.match(ln.rstrip('\n'))
        if not m or not (t0 <= m.group(1)[:8] <= t1): continue
        items = [(it.group(1), int(it.group(2)), it.group(4)) for it in ITEM_RE.finditer(m.group(9))]
        if only and not any(i in only for _, i, _ in items): continue
        key = (m.group(3), ' '.join('%s#%d' % (s, i) for s, i, _ in items), m.group(6))
        per.setdefault((int(m.group(2)), m.group(1)[:8]), collections.Counter())[key] += 1
    drops = []
    for (f, t), C in per.items():
        print('frame %d (%s): %d distinct cut sets' % (f, t, len(C)))
        dset = set()
        for (caller, order, cat), n in C.items():
            print('  %dx caller %s (%s): %s' % (n, caller, cat, order))
            dset |= set(int(x[2:]) for x in order.split() if x.startswith('-#'))
        drops.append((f, t, sorted(dset)))
    print('dropped per frame:')
    for f, t, d in drops: print('  f%d %s: %s' % (f, t, ' '.join('#%d' % i for i in d)))
    return 0


def main():
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ('frames', 'cuts'):
        print(__doc__)
        return 2
    return frames_cmd(a[1:]) if a[0] == 'frames' else cuts_cmd(a[1:])


if __name__ == '__main__':
    sys.exit(main())
