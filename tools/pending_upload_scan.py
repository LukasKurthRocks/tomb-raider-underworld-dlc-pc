"""Upload check for the NOT yet committed paths of the repository (read-only).

scripts/windows/Test-TruUploadReady.ps1 scans committed history only (origin/main..windows). This tool applies the same
finding groups to what `git status` lists now, so a commit plan can name the findings before anything is committed:
  * modified tracked files: only the lines the working tree adds against HEAD (`git diff -U0 HEAD`)
  * untracked files (every file, `-uall`): every line
The patterns Path / Email / Secret / Hardware are read from Test-TruUploadReady.ps1 itself (one source), Machine /
Identity are built at run time as there (COMPUTERNAME, USERNAME, git user.name / user.email), Local from
scripts/windows/Test-TruUploadReady.local.txt when it exists. Nothing personal is stored in this file.
Per path it also reports: status, size, binary / media file, UTF-8 BOM and CR / LF counts (.ps1 / .psm1 / .md / .py /
.cpp / .h / .ini / .txt / .json). git runs with --no-optional-locks (no index refresh); nothing is written except the
optional --out report.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/pending_upload_scan.py [--prefix P ...] [--skip-prefix P ...] [--findings] [--out FILE]
  --prefix P       only paths starting with P (repeatable)
  --skip-prefix P  leave out paths starting with P (repeatable; e.g. work/ to see the source part only)
  --findings       print every finding line (default: counts per path and group only)
  --out FILE       also write the report to FILE (UTF-8)
Exit code: 0 = scanned, 2 = usage error / scanner script not found.
Since TruMenu 0.21 (2026-11-07) also the group Owner: the owner's own arachnophobia picture (any `*.arachno*.png`, e.g.
TruMenu.arachno.png) and everything below `work/arachno_owner/` are private and never go into the repository or a release
- such a pending path is an ERROR finding (exit code 1); .gitignore keeps them out of `git status`, so this catches a
force-add or a changed .gitignore.
"""
import sys, os, re, subprocess, argparse, collections

SCANNER = 'scripts/windows/Test-TruUploadReady.ps1'
LOCAL = 'scripts/windows/Test-TruUploadReady.local.txt'
SELF = 'tools/pending_upload_scan.py'
MEDIA = ('.wav', '.mp3', '.ogg', '.xma', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.dds', '.tga', '.mp4', '.avi',
         '.mkv', '.webm')
BINARY = ('.zip', '.7z', '.exe', '.dll', '.asi', '.bin', '.drm', '.pkl', '.npz', '.ico', '.pdf', '.dmp', '.pdb',
          '.obj', '.lib')
TEXT_ENC = ('.ps1', '.psm1', '.md', '.py', '.cpp', '.h', '.ini', '.txt', '.json', '.cdb', '.tsv')
SCAN_SKIP = re.compile(r'\.(png|jpe?g|gif|zip|bin)$', re.I)    # as the scanner
OWNER = re.compile(r'(^|/)work/arachno_owner/|(^|/)[^/]*\.arachno[^/]*\.png$', re.I)   # 0.21: the owner's picture


def git(args, root):
    p = subprocess.run(['git', '--no-optional-locks', '-C', root, '-c', 'core.quotepath=off'] + args,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError('git %s: %s' % (' '.join(args), p.stderr.decode('utf-8', 'replace').strip()))
    return p.stdout


def ps_patterns(root):
    """Path / Email / Secret / Hardware regexes from the $patterns block of the scanner (PowerShell '' -> ')."""
    path = os.path.join(root, SCANNER)
    if not os.path.isfile(path):
        return None
    out = collections.OrderedDict()
    for line in open(path, encoding='utf-8-sig'):
        m = re.match(r"^\s+(Path|Email|Secret|Hardware)\s+=\s+'(.*)'\s*$", line.rstrip('\r\n'))
        if m:
            out[m.group(1)] = m.group(2).replace("''", "'")
    return out


def alternation(values):
    vals = sorted(set(v for v in values if v))
    return '(?i)(' + '|'.join(re.escape(v) for v in vals) + ')' if vals else '(?!)'


def build_patterns(root):
    base = ps_patterns(root)
    if base is None or len(base) != 4:
        return None, 'scanner patterns not found in %s' % SCANNER
    name = git(['config', 'user.name'], root).decode('utf-8', 'replace').strip()
    mail = git(['config', 'user.email'], root).decode('utf-8', 'replace').strip()
    ident = [os.environ.get('USERNAME', '')] + name.split() + [mail, mail.split('@')[-1] if mail else '']
    ident = sorted(set(v for v in ident if v and len(v) >= 4))
    comp = os.environ.get('COMPUTERNAME', '')
    machine = [comp] + [v for v in re.split(r'[-_.]', comp) if len(v) >= 4 and v not in ident]
    pats = collections.OrderedDict()
    pats['Path'] = base['Path']
    pats['Machine'] = alternation(machine)
    pats['Identity'] = alternation(ident)
    pats['Email'] = base['Email']
    pats['Secret'] = base['Secret']
    pats['Hardware'] = base['Hardware']
    local = '(?!)'
    lp = os.path.join(root, LOCAL)
    if os.path.isfile(lp):
        lines = [l.strip() for l in open(lp, encoding='utf-8-sig') if l.strip() and not l.strip().startswith('#')]
        if lines:
            local = '(?i)(' + '|'.join(lines) + ')'
    pats['Local'] = local
    comp_ = collections.OrderedDict()
    for k, v in pats.items():
        try:
            comp_[k] = re.compile(v)
        except re.error as e:
            return None, 'pattern %s does not compile in Python: %s' % (k, e)
    return comp_, None


def status_entries(root):
    raw = git(['status', '--porcelain=v1', '-z', '-uall'], root)
    items = raw.split(b'\0')
    out = []
    i = 0
    while i < len(items):
        it = items[i]
        i += 1
        if not it:
            continue
        code = it[:2].decode('ascii', 'replace')
        path = it[3:].decode('utf-8', 'replace')
        if code[0] in 'RC':
            i += 1   # the next item is the source path
        out.append((code, path))
    return out


def added_lines(root, path):
    raw = git(['diff', '-U0', '--no-color', 'HEAD', '--', path], root).decode('utf-8', 'replace')
    n = 0
    for line in raw.split('\n'):
        if line.startswith('+++ '):
            continue
        m = re.match(r'^@@ -\S+ \+(\d+)', line)
        if m:
            n = int(m.group(1))
            continue
        if line.startswith('+'):
            yield n, line[1:].rstrip('\r')
            n += 1


def file_lines(full):
    text = open(full, 'rb').read().decode('utf-8', 'replace')
    if text.startswith('﻿'):
        text = text[1:]
    for n, line in enumerate(text.replace('\r\n', '\n').replace('\r', '\n').split('\n'), 1):
        yield n, line


def main(argv):
    ap = argparse.ArgumentParser(add_help=True, description=__doc__.split('\n')[0])
    ap.add_argument('--prefix', action='append', default=[])
    ap.add_argument('--skip-prefix', action='append', default=[])
    ap.add_argument('--findings', action='store_true')
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    root = os.getcwd()
    if not os.path.isdir(os.path.join(root, '.git')):
        print('run from the repository root'); return 2
    pats, err = build_patterns(root)
    if err:
        print(err); return 2
    report = []
    say = report.append
    entries = status_entries(root)
    sel = [(c, p) for c, p in entries
           if (not a.prefix or any(p.startswith(x) for x in a.prefix))
           and not any(p.startswith(x) for x in a.skip_prefix)]
    say('pending paths: %d in git status, %d selected' % (len(entries), len(sel)))
    totals = collections.Counter()
    kinds = collections.Counter()
    findings = []
    rows = []
    for code, path in sel:
        full = os.path.join(root, path.replace('/', os.sep))
        ext = os.path.splitext(path)[1].lower()
        size = os.path.getsize(full) if os.path.isfile(full) else -1
        st = 'M' if 'M' in code else ('new' if code == '??' else code.strip())
        kinds[st] += 1
        flags = []
        if ext in MEDIA:
            flags.append('media')
        head = open(full, 'rb').read(8192) if size >= 0 else b''
        is_bin = ext in BINARY or (b'\0' in head and ext not in TEXT_ENC)
        if is_bin and ext not in MEDIA:
            flags.append('binary')
        if size > 1024 * 1024:
            flags.append('>1MB')
        enc = ''
        if ext in TEXT_ENC and size >= 0:
            data = open(full, 'rb').read()
            cr, lf = data.count(b'\r'), data.count(b'\n')
            enc = 'BOM %s CR %d LF %d' % ('yes' if data.startswith(b'\xef\xbb\xbf') else 'no', cr, lf)
        per = collections.Counter()
        if OWNER.search(path):                # 0.21: private, never uploaded - an error whatever the content
            per['Owner'] += 1
            totals['Owner'] += 1
            findings.append('%-9s %s  [owner picture / work/arachno_owner - ERROR: never commit or release]' % ('Owner', path))
        if size >= 0 and not is_bin and ext not in MEDIA and path != SELF and path != SCANNER \
                and not SCAN_SKIP.search(path):
            src = added_lines(root, path) if st == 'M' else file_lines(full)
            for n, line in src:
                for k, rx in pats.items():
                    m = rx.search(line)
                    if m:
                        per[k] += 1
                        totals[k] += 1
                        snip = line.strip()
                        if len(snip) > 140:
                            snip = snip[:140] + '...'
                        findings.append('%-9s %s:%d  [%s]  %s' % (k, path, n, m.group(0), snip))
        for f in flags:
            totals['flag ' + f] += 1
        rows.append('%-4s %9d  %-22s %-26s %s  %s' % (st, size, ','.join(flags), enc, path,
                                                     ' '.join('%s=%d' % kv for kv in sorted(per.items()))))
    say('status: ' + ', '.join('%s %d' % kv for kv in sorted(kinds.items())))
    say('--- paths (status, bytes, flags, encoding, path, findings) ---')
    report.extend(rows)
    if a.findings:
        say('--- findings ---')
        report.extend(sorted(findings))
    say('--- summary ---')
    for k in list(pats.keys()) + ['Owner', 'flag media', 'flag binary', 'flag >1MB']:
        say('%-12s %d' % (k, totals[k]))
    say('total findings %d' % (sum(totals[k] for k in pats.keys()) + totals['Owner']))
    if totals['Owner']:
        say('ERROR: %d owner picture path(s) pending (*.arachno*.png / work/arachno_owner/) - remove them from the index'
            % totals['Owner'])
    text = '\n'.join(report)
    sys.stdout.buffer.write((text + '\n').encode('utf-8', 'replace'))
    if a.out:
        open(a.out, 'w', encoding='utf-8', newline='\n').write(text + '\n')
    return 1 if totals['Owner'] else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
