"""List the engine addresses of finding files (Markdown) that docs/ENGINE.md does not mention yet (read-only, no network).

docs/ENGINE.md is the engine reference; its rule is that every new engine fact gets its row there in the same commit.
This tool helps the end-of-session cross-check: it collects the addresses a finding names and reports which of them
do not occur anywhere in ENGINE.md. It does not decide what belongs there - the list is a reading aid, not a to-do.

Recognised forms (case-insensitive):
  * ``tru+0x237590``                      -> PC VA 0x637590 (image base 0x400000 added)
  * absolute PC VAs 0x500000..0x8fffff    -> e.g. ``0x637590`` (6 hex digits after 0x, first digit 5..8)
  * Xbox TU addresses 0x82000000..0x82ffffff -> e.g. ``0x8235e998`` (8 hex digits)
A number is "mentioned" when ENGINE.md contains the same value in any of these forms (``tru+X`` there counts too).
Field offsets (``+0x2c``) and short constants are ignored. Expect false positives: data values that look like
addresses (``0x7fffff``, colours, float bit patterns) and code addresses that are only a site inside a known function.

Usage (from the repository root):
  ../bin/pyt tools/engine_md_check.py FINDING.md [FINDING.md ...] [--engine docs/ENGINE.md] [--context] [--json OUT]
  ../bin/pyt tools/engine_md_check.py --selftest
Exit code: 0 = every address is mentioned, 1 = some are missing, 2 = usage / input error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

IMAGE_BASE = 0x400000
PC_LO, PC_HI = 0x500000, 0x8fffff
TU_LO, TU_HI = 0x82000000, 0x82ffffff

# tru+0x... (relative) first, then plain hex numbers that are not part of a longer token
_RE_TRU = re.compile(r'tru\s*\+\s*0x([0-9a-f]{1,8})\b', re.IGNORECASE)
_RE_HEX = re.compile(r'(?<![0-9a-z_+])0x([0-9a-f]{6}|[0-9a-f]{8})(?![0-9a-z_])', re.IGNORECASE)


@dataclass(frozen=True)
class Hit:
    kind: str      # 'pc' or 'tu'
    value: int     # absolute VA (PC) or Xbox address (TU)
    file: str
    line: int
    text: str      # the source line, stripped


@dataclass
class Report:
    engine: str
    files: List[str]
    total: int = 0
    missing: Dict[Tuple[str, int], List[Hit]] = field(default_factory=dict)


def classify(value: int) -> Optional[str]:
    """'pc' for a PC VA in the engine range, 'tu' for a TU address, None for anything else."""
    if PC_LO <= value <= PC_HI:
        return 'pc'
    if TU_LO <= value <= TU_HI:
        return 'tu'
    return None


def addresses_in_text(text: str) -> Iterable[Tuple[str, int, int]]:
    """Yield (kind, value, start offset) for every recognised address in ``text``."""
    taken: List[Tuple[int, int]] = []
    for m in _RE_TRU.finditer(text):
        va = int(m.group(1), 16) + IMAGE_BASE
        taken.append(m.span())
        kind = classify(va)
        if kind == 'pc':
            yield kind, va, m.start()
    for m in _RE_HEX.finditer(text):
        if any(a <= m.start() < b for a, b in taken):
            continue
        value = int(m.group(1), 16)
        kind = classify(value)
        if kind is not None:
            yield kind, value, m.start()


def known_values(engine_text: str) -> Set[Tuple[str, int]]:
    return {(k, v) for k, v, _ in addresses_in_text(engine_text)}


def scan(engine_path: str, files: Sequence[str]) -> Report:
    with open(engine_path, encoding='utf-8-sig') as f:
        known = known_values(f.read())
    rep = Report(engine=engine_path, files=list(files))
    for path in files:
        with open(path, encoding='utf-8-sig', errors='replace') as f:
            for no, line in enumerate(f, 1):
                for kind, value, _ in addresses_in_text(line):
                    rep.total += 1
                    if (kind, value) not in known:
                        rep.missing.setdefault((kind, value), []).append(
                            Hit(kind, value, os.path.basename(path), no, line.strip()))
    return rep


def fmt_addr(kind: str, value: int) -> str:
    return '0x%08x' % value if kind == 'tu' else '0x%06x' % value


def print_report(rep: Report, context: bool) -> None:
    try:
        shown_engine = os.path.relpath(rep.engine)
    except ValueError:                      # other drive on Windows
        shown_engine = os.path.basename(rep.engine)
    print('engine reference: %s' % shown_engine)
    print('finding files: %d, address mentions: %d, distinct addresses not in the reference: %d'
          % (len(rep.files), rep.total, len(rep.missing)))
    for kind in ('pc', 'tu'):
        keys = sorted(k for k in rep.missing if k[0] == kind)
        if not keys:
            continue
        print('')
        print('%s addresses missing (%d):' % ('PC' if kind == 'pc' else 'Xbox TU', len(keys)))
        for key in keys:
            hits = rep.missing[key]
            where = sorted({'%s:%d' % (h.file, h.line) for h in hits})
            shown = ', '.join(where[:4]) + (' (+%d)' % (len(where) - 4) if len(where) > 4 else '')
            print('  %s  %dx  %s' % (fmt_addr(*key), len(hits), shown))
            if context:
                text = hits[0].text
                print('      | %s' % (text if len(text) <= 160 else text[:157] + '...'))


def write_json(rep: Report, out: str) -> None:
    data = {
        'engine': os.path.basename(rep.engine), 'files': [os.path.basename(p) for p in rep.files],
        'mentions': rep.total,
        'missing': [{'kind': k, 'address': fmt_addr(k, v),
                     'hits': [{'file': h.file, 'line': h.line} for h in hits]}
                    for (k, v), hits in sorted(rep.missing.items())],
    }
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, indent=1)


def selftest() -> int:
    text = ('call tru+0x237590 and 0x637590; TU 0x8235e998; offset +0x2c; field +0x5030; '
            'value 0x0fffffff; 0x41c80000; 0xe7f088; id_0x600000x; 0x4726e0')
    got = sorted((k, v) for k, v, _ in addresses_in_text(text))
    want = [('pc', 0x637590), ('pc', 0x637590), ('tu', 0x8235e998)]
    ok = got == want
    print('selftest addresses_in_text: %s (got %s)' % ('ok' if ok else 'FAILED',
                                                       [fmt_addr(k, v) for k, v in got]))
    known = known_values('Enter tru+0x27ed20, TU 0x8235dff8')
    ok2 = ('pc', 0x67ed20) in known and ('tu', 0x8235dff8) in known
    print('selftest known_values (tru+ form counts): %s' % ('ok' if ok2 else 'FAILED'))
    return 0 if ok and ok2 else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description='Report PC (tru+0x..., 0x5xxxxx-0x8xxxxx) and Xbox TU (0x82xxxxxx) addresses of finding files '
                    'that docs/ENGINE.md does not mention. Read-only; prints a list, changes nothing.')
    ap.add_argument('files', nargs='*', help='finding files (Markdown) to scan')
    ap.add_argument('--engine', default=os.path.normpath(os.path.join(here, '..', 'docs', 'ENGINE.md')),
                    help='engine reference to compare against (default: docs/ENGINE.md next to tools/)')
    ap.add_argument('--context', action='store_true', help='print the first source line of every missing address')
    ap.add_argument('--json', metavar='OUT', help='also write the result as JSON')
    ap.add_argument('--selftest', action='store_true', help='run the built-in pattern checks and exit')
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.files:
        ap.error('give at least one finding file')
    for p in [args.engine] + list(args.files):
        if not os.path.isfile(p):
            print('engine_md_check: file not found: %s' % p, file=sys.stderr)
            return 2
    rep = scan(args.engine, args.files)
    print_report(rep, args.context)
    if args.json:
        write_json(rep, args.json)
        print('written %s' % args.json)
    return 1 if rep.missing else 0


if __name__ == '__main__':
    sys.exit(main())
