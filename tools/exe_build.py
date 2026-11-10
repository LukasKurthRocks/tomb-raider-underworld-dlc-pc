#!/usr/bin/env python3
"""exe_build.py - build the patched B138 tru.exe ourselves from the Steamless-unpacked Steam exe (pipeline step Exe,
2026-11-10, docs Befund-Kit-Unabhaengigkeit-1011.md stage 1, ENGINE.md 18.5).

Stages (each one checks the bytes it expects first and refuses otherwise; nothing is written until the gate passes):
  1 input        md5 of the Steamless output = 56d1ce2d... (Install-TruAll.ps1 step 8, $md5UnpackedExe)
  2 laa          FileHeader.Characteristics 0x0103 -> 0x0123 (IMAGE_FILE_LARGE_ADDRESS_AWARE, file offset pe+0x16)
  3 fmod         tools/fmod_init_guard.py   0x582200 -> cave 0x83de00 (upstream, unchanged)
  4 lighttex     tools/light_tex_guard.py   0x50a645 / 0x50a683 -> cave 0x83de60, counters 0x83de20; also sets .text
                 writable (0x60000020 -> 0xe0000020) for the counters (upstream, unchanged)
  5 soundplex    tools/soundplex_guard.py   0x5920d5 -> cave 0x83df40, counters 0x83df00 (upstream; needs stage 4)
  6 combatlock   tools/combat_lock_guard.py 0x71e710 -> cave 0x83dfd0 (ours, the B138 bytes rebuilt)
  7 sections     every section header unchanged except .text characteristics = 0xe0000020 (as B138); no section added,
                 same file size
  8 gate         md5 of the result = 5560abacbc6968cdc17871c3ec8ca21c (the B138 exe) -> write OUT
The section flag is set by light_tex_guard (stage 4) and only checked in stage 7: light_tex_guard refuses an exe whose
.text is already writable, so it cannot be set before the guards.

Input: --input FILE, else the first of these (relative to the repository) whose md5 matches:
  ../data/pc/tru.exe.unpacked.exe, ../data/pc/tru.exe.steam_original.unpacked.exe, ../data/pc/tru.exe.steamless_original
  (the names Install-TruAll.ps1 accepts; ../data/pc = the game folder, only read), work/b270_kit/exe/tru_steam_unpacked_realign.exe
The output must not lie in the game folder or next to the input (refused).

Usage (from the repository root):
  ../bin/pyt -t 300 tools/exe_build.py OUT.exe [--input STEAMLESS.exe] [--report OUT.json] [--ref B138.exe]
  ../bin/pyt -t 300 tools/exe_build.py --check EXE [--report OUT.json]
  --check lists every stage's state in EXE (input md5 / LAA bit / each guard original | patched | DIFFERENT / .text flag
  / md5 gate); exit 0 only when EXE is the complete build (= B138). Build: exit 0 = gate passed and OUT written,
  1 = a stage refused or the gate failed (OUT untouched). --ref lists the differing byte ranges against a reference exe
  when the gate fails (offsets and counts only). Prints addresses, md5 values and counts only, never game bytes.
"""
import sys, os, struct, hashlib, json, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fmod_init_guard as F
import light_tex_guard as L
import soundplex_guard as S
import combat_lock_guard as C

STEAMLESS_MD5 = '56d1ce2dffa62f16354063da2df44d5a'
B138_MD5 = '5560abacbc6968cdc17871c3ec8ca21c'
LAA = 0x0020
CHAR_IN, CHAR_OUT = 0x0103, 0x0123
TEXT_IN, TEXT_OUT = 0x60000020, 0xE0000020
GAME_DIR = os.path.join(REPO, '..', 'data', 'pc')
CANDIDATES = [os.path.join('..', 'data', 'pc', n) for n in
              ('tru.exe.unpacked.exe', 'tru.exe.steam_original.unpacked.exe', 'tru.exe.steamless_original')] + \
             [os.path.join('work', 'b270_kit', 'exe', 'tru_steam_unpacked_realign.exe')]


def md5(b): return hashlib.md5(b).hexdigest()


def pe_off(d): return struct.unpack_from('<I', d, 0x3c)[0]


def file_chars(d): return struct.unpack_from('<H', d, pe_off(d) + 22)[0]


def sections(d):
    return [(s['name'], s['va'], s['vs'], s['ro'], s['rs'], s['ch']) for s in L.sec_hdrs(d)]


def guard_state(mod, d):
    """normalise the three spellings: upstream Italian (originale / patchato / DIVERSO) and ours."""
    s = mod.state(d)
    return {'originale': 'original', 'patchato': 'patched'}.get(s, s if not s.startswith('DIVERSO') else 'DIFFERENT' + s[7:])


GUARDS = [('fmod', F, 'fmod_init_guard 0x582200 -> 0x83de00'),
          ('lighttex', L, 'light_tex_guard 0x50a645 / 0x50a683 -> 0x83de60 (+ .text writable)'),
          ('soundplex', S, 'soundplex_guard 0x5920d5 -> 0x83df40'),
          ('combatlock', C, 'combat_lock_guard 0x71e710 -> 0x83dfd0')]


class Stages:
    def __init__(self): self.rows = []

    def add(self, name, ok, detail):
        self.rows.append(dict(stage=name, ok=bool(ok), result=detail))
        print('  [%s] %-10s %s' % ('ok' if ok else 'FAIL', name, detail))
        return ok


def build_bytes(d, st):
    """run stages 2..7 on the input bytes d; returns the result or None after the first failing stage."""
    if file_chars(d) != CHAR_IN:
        st.add('laa', False, 'Characteristics %#06x, expected %#06x' % (file_chars(d), CHAR_IN)); return None
    b = bytearray(d); struct.pack_into('<H', b, pe_off(d) + 22, CHAR_IN | LAA); cur = bytes(b)
    st.add('laa', file_chars(cur) == CHAR_OUT, 'Characteristics %#06x -> %#06x' % (CHAR_IN, file_chars(cur)))
    for name, mod, what in GUARDS:
        before = guard_state(mod, cur)
        if before != 'original':
            st.add(name, False, '%s: refused, state %s' % (what, before)); return None
        try:
            new = mod.apply(cur)
            nd = mod.verify(cur, new)[0]
            if hasattr(mod, 'selftest'):
                print('    selftest %s:' % mod.__name__); mod.selftest()
        except (SystemExit, AssertionError, Exception) as e:   # upstream tools refuse via SystemExit / assert
            st.add(name, False, '%s: %s: %s' % (what, type(e).__name__, e)); return None
        after = guard_state(mod, new)
        if not st.add(name, after == 'patched', '%s: %d bytes changed, state %s' % (what, nd, after)): return None
        cur = new
    si, so = sections(d), sections(cur)
    bad = []
    if len(cur) != len(d): bad.append('size %d -> %d' % (len(d), len(cur)))
    if len(si) != len(so): bad.append('section count %d -> %d' % (len(si), len(so)))
    for a, b2 in zip(si, so):
        want = a[:5] + ((TEXT_OUT,) if a[0] == '.text' else (a[5],))
        if a[0] == '.text' and a[5] != TEXT_IN: bad.append('.text input flags %#x, expected %#x' % (a[5], TEXT_IN))
        if b2 != want: bad.append('%s flags %#x, expected %#x' % (b2[0], b2[5], want[5]))
    text = next(s for s in so if s[0] == '.text')
    if not st.add('sections', not bad, '; '.join(bad) if bad else
                  '%d sections, only .text flags %#x -> %#x, size %d unchanged' % (len(so), TEXT_IN, text[5], len(cur))):
        return None
    return cur


def diff_ranges(a, b, gap=8):
    out = []
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            if out and i - out[-1][1] <= gap: out[-1][1] = i
            else: out.append([i, i])
    return [(s, e - s + 1) for s, e in out]


def same_file(p, q):
    return os.path.normcase(os.path.realpath(p)) == os.path.normcase(os.path.realpath(q))


def find_input(given, st):
    tried = [given] if given else [os.path.join(REPO, c) if not os.path.isabs(c) else c for c in CANDIDATES]
    for p in tried:
        if not os.path.isfile(p):
            print('    input candidate %s: missing' % os.path.relpath(p, REPO)); continue
        d = open(p, 'rb').read(); m = md5(d)
        print('    input candidate %s: md5 %s' % (os.path.relpath(p, REPO), m))
        if m == STEAMLESS_MD5:
            st.add('input', True, '%s (md5 %s, %d bytes)' % (os.path.relpath(p, REPO), m, len(d))); return p, d
    st.add('input', False, 'no Steamless-unpacked exe with md5 %s (run Install-TruAll.ps1 step 8 / Steamless v3.1.0.5, '
           'or pass --input)' % STEAMLESS_MD5)
    return None, None


def write_report(path, data):
    if not path: return
    os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f: json.dump(data, f, indent=1)
    print('report: %s' % path)


def cmd_check(path, report):
    d = open(path, 'rb').read(); m = md5(d); st = Stages()
    print('check %s' % path)
    st.add('input', True, 'md5 %s (%s)' % (m, 'Steamless input' if m == STEAMLESS_MD5 else 'B138' if m == B138_MD5 else 'other'))
    st.add('laa', file_chars(d) & LAA, 'Characteristics %#06x (LARGE_ADDRESS_AWARE %s)' % (file_chars(d), 'set' if file_chars(d) & LAA else 'clear'))
    for name, mod, what in GUARDS:
        s = guard_state(mod, d); st.add(name, s == 'patched', '%s: %s' % (what, s))
    text = next(s for s in sections(d) if s[0] == '.text')
    st.add('sections', text[5] == TEXT_OUT, '.text flags %#x (B138 %#x)' % (text[5], TEXT_OUT))
    st.add('gate', m == B138_MD5, 'md5 %s %s B138 %s' % (m, '=' if m == B138_MD5 else '!=', B138_MD5))
    ok = all(r['ok'] for r in st.rows)
    write_report(report, dict(mode='check', file=path, md5=m, complete=ok, stages=st.rows))
    print('check: %s' % ('complete build (= B138)' if ok else 'not the complete build'))
    return 0 if ok else 1


def cmd_build(out, given, report, ref):
    st = Stages(); print('build %s' % out)
    for bad in (GAME_DIR,):
        if os.path.isdir(bad) and same_file(os.path.dirname(os.path.abspath(out)), bad):
            raise SystemExit('refused: output %s lies in the game folder' % out)
    src, d = find_input(given, st)
    res = None
    if d is not None:
        if same_file(os.path.dirname(os.path.abspath(out)), os.path.dirname(os.path.abspath(src))):
            raise SystemExit('refused: output %s lies next to the input %s' % (out, src))
        res = build_bytes(d, st)
    ok = False; m = None
    if res is not None:
        m = md5(res); ok = st.add('gate', m == B138_MD5, 'md5 %s %s B138 %s' % (m, '=' if m == B138_MD5 else '!=', B138_MD5))
        if not ok and ref and os.path.isfile(ref):
            r = open(ref, 'rb').read(); dr = diff_ranges(res, r)
            print('    against %s: %d differing bytes in %d ranges%s' % (ref, sum(n for _, n in dr), len(dr),
                  '' if len(r) == len(res) else ', size %d vs %d' % (len(res), len(r))))
            for o, n in dr[:40]: print('      file offset %#08x  %d bytes' % (o, n))
    if ok:
        os.makedirs(os.path.dirname(os.path.abspath(out)) or '.', exist_ok=True)
        tmp = out + '.part'
        with open(tmp, 'wb') as f: f.write(res)
        os.replace(tmp, out)
        print('written %s (md5 %s, %d bytes)' % (out, m, len(res)))
    else:
        print('build FAILED: %s not written' % out)
    write_report(report, dict(mode='build', output=out, input=os.path.relpath(src, REPO) if src else None,
                              input_md5=STEAMLESS_MD5 if src else None, output_md5=m, gate_md5=B138_MD5, ok=ok, stages=st.rows))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='build the B138 tru.exe from the Steamless-unpacked Steam exe')
    ap.add_argument('out', nargs='?', help='output exe (build mode)')
    ap.add_argument('--check', metavar='EXE', help='list every stage state of EXE')
    ap.add_argument('--input', help='Steamless-unpacked exe (md5 %s)' % STEAMLESS_MD5)
    ap.add_argument('--report', help='JSON report')
    ap.add_argument('--ref', help='reference exe for a byte-range listing when the gate fails')
    a = ap.parse_args()
    if a.check: return cmd_check(a.check, a.report)
    if not a.out: ap.error('give OUT.exe or --check EXE')
    return cmd_build(a.out, a.input, a.report, a.ref)


if __name__ == '__main__':
    sys.exit(main())
