"""P4.9 (2026-11-14): archive name hashes '0x%08x' of xenon-w\\NAME for the given names (dlc_convert_all shows names
missing from the Xenon file list as their hash, so a single-file conversion selects them by hash). Read-only.
Usage: ../bin/pyt work/p48_1411/p49_map_hashes.py NAME.drm [...]"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))
from names import crc
print(' '.join('0x%08x' % crc('xenon-w\\' + n) for n in sys.argv[1:]))
