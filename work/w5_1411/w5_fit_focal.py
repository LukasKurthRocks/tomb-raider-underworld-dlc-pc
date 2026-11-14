"""W5 (2026-11-14): the 21:20:12 fit again with the focal length free (the game may widen the view when the camera looks
up; w5_line_search.py kept 463.53 of the 21:20:05 log line). Gate hypothesis (cavern gate object ledges drawn at the
world origin) vs the best markup2 triple, with Lara's feet as seventh point.

Usage (from the repository root):
  ../bin/pyt -t 600 work/w5_1411/w5_fit_focal.py
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w5_line_search as LS

CASES = {
    'cavern gates 2312 / 2310 / 2309 at the origin': [((-55.0, 562.0, 1418.0), (-55.0, -575.0, 1418.0)),
                                                       ((-55.0, 562.0, 1100.0), (-55.0, -575.0, 1100.0)),
                                                       ((-55.0, 562.0, 468.0), (-55.0, -575.0, 468.0))],
}


def main():
    S = np.array([p for line in LS.SHOT for p in line] + [LS.LARA_SHOT], dtype=float)
    for name, lines in CASES.items():
        for flip in (False, True):
            P = []
            for a, b in lines:
                a, b = np.array(a), np.array(b)
                if flip: a, b = b, a
                P.extend([a, b])
            P.append(LS.LARA)
            P = np.array(P)
            best = None
            for f in np.arange(250.0, 900.0, 25.0):
                LS.F = f
                e, a, b, t = LS.grid_fit(P, S, step=2.0)
                e, a, b, t = LS.grid_fit(P, S, step=0.1, a0=a, b0=b, span=2.0)
                if best is None or e < best[0]: best = (e, f, np.degrees(a), np.degrees(b))
            print('%s%s: best worst error %.1f px at focal %.0f (logged 463.53), yaw %.1f pitch %.1f' % (
                name, ' (flipped)' if flip else '', best[0], best[1], best[2], best[3]))


if __name__ == '__main__':
    main()
