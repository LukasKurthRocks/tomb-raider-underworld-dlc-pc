"""Shared helpers of our build and compare tools (code review M2, M5).

replace_tree(src, out)  copy SRC to a fresh OUT; an existing OUT is removed first, but only when it lies strictly
                        below work/rebuild (never work/rebuild itself) and is neither SRC nor inside or above SRC
require_dir(path, what) stop with a clear message when an input folder does not exist (os.walk would silently
                        yield nothing and the tool would overwrite its report with an empty one)
"""
import os, sys, shutil

REBUILD = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'rebuild'))


def _below(path, root):
    """path inside root (or equal); False on different drives instead of commonpath's ValueError"""
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def check_out(out, src=None, must_be_below=False):
    o = os.path.realpath(out)
    if src is not None:
        s = os.path.realpath(src)
        if _below(o, s) or _below(s, o): sys.exit('OUT must not be SRC, inside SRC or above SRC: ' + out)
    if (must_be_below or os.path.exists(o)) and (o == REBUILD or not _below(o, REBUILD)):
        sys.exit('OUT must be a folder below work/rebuild (it is replaced; remove other folders yourself): ' + out)
    return o


def replace_tree(src, out, must_be_below=False):
    require_dir(src, 'SRC')
    check_out(out, src, must_be_below)
    if os.path.exists(out):
        print('replacing previous output', out, flush=True)
        shutil.rmtree(out)
    shutil.copytree(src, out)


def require_dir(path, what):
    if not os.path.isdir(path): sys.exit('%s not found: %s' % (what, path))
    return path
