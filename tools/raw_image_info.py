"""Header info of Xbox '!WAR' images (.raw) in the DLC packs and the base game (read-only).

Lists every '!WAR' record of the DLC packs (pack1/2/10/11/20) and of the Xbox base game (layer1/layer2/TitleUpdate)
with width, height, format word, flags, data size, md5 and the name (DLC: from a dlc_names.txt; base: Xbox filelist).
For the hashes given with --hash it also writes a PNG (decoded with raw_image_convert) to --png-dir and prints which
other records have the same size / same dimensions / identical bytes, plus a pixel comparison (mean absolute
difference per channel) against same-sized named DLC images.
Header layout: see tools/raw_image_convert.py (32 u32 big-endian; [3] format, [4] flags, [5] width, [6] height).
Note: the '!WAR' images have no mip chain (one surface; data size word [2] = padded w*h*4).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/raw_image_info.py [--names work/generic/dlc_names.txt] [--hash 0x753ecefd ...]
        [--png-dir work/names_0511/png] [--all]
  --all prints every image record (default: only the summary per size and the --hash details)
"""
import sys, os, struct, hashlib, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive import Archive
from names import load, L
from locals import SRC
import raw_image_convert as ric

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'generic')
DLC = ('pack10', 'pack11', 'pack1', 'pack2', 'pack20')
BASE = ('xbase', 'xbase2', 'tu')


def hdr(b):
    h = struct.unpack('>32I', b[:128])
    return {'fmt': h[3], 'flags': h[4], 'w': h[5], 'h': h[6], 'datasize': h[2], 'pitch': h[7], 'bpp': h[8],
            'tail': ' '.join('%x' % v for v in h[17:32] if v)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--names', default=os.path.join(W, 'dlc_names.txt'))
    ap.add_argument('--hash', nargs='*', default=[])
    ap.add_argument('--png-dir', default=None)
    ap.add_argument('--png-names', nargs='*', default=[], help='also write PNGs of these named records (substring match)')
    ap.add_argument('--all', action='store_true')
    a = ap.parse_args()
    targets = {int(x, 16) for x in a.hash}
    names = {}
    for l in open(a.names, encoding='latin1'):
        t = l.split()
        if len(t) >= 6 and t[0].startswith('0x') and t[5] != '?': names[int(t[0], 16)] = t[5]
    xn = load(L + 'Tomb Raider Underworld (Xenon).txt')
    recs = []   # (src, hash, size, hdr, md5, name, bytes or None)
    for k in DLC + BASE:
        A = Archive(SRC[k][0], SRC[k][1])
        for r in A.idx:
            if r['spec'] != 0xffffffff and k in DLC: continue
            b = A.read(r)
            if b[:4] != ric.MAGIC: continue
            nm = names.get(r['hash']) if k in DLC else None
            nm = nm or xn.get(r['hash'], '?')
            recs.append((k, r['hash'], len(b), hdr(b), hashlib.md5(b).hexdigest(), nm, r['spec'], b))
    print('image records', len(recs), 'dlc', sum(1 for r in recs if r[0] in DLC), 'base', sum(1 for r in recs if r[0] in BASE))
    if a.all:
        for k, h, size, hd, md5, nm, spec, _ in sorted(recs, key=lambda r: (r[2], r[5])):
            print('IMG %-6s 0x%08x spec=%08x %8d %4dx%-4d fmt=%d flags=%x md5=%s %s' % (k, h, spec, size, hd['w'], hd['h'], hd['fmt'], hd['flags'], md5[:12], nm))
    # summary by dimensions
    dims = collections.defaultdict(list)
    for r in recs: dims[r[3]['w'], r[3]['h']].append(r)
    print('--- dimensions (w x h): count, example names')
    for (w, h), lst in sorted(dims.items(), key=lambda kv: -len(kv[1])):
        ex = sorted({r[5].split('\\')[-1] for r in lst})
        print('DIM %4dx%-4d n=%-4d sizes=%s %s%s' % (w, h, len(lst), sorted({r[2] for r in lst}), ', '.join(ex[:12]), ' ...' if len(ex) > 12 else ''))
    if a.png_dir: os.makedirs(a.png_dir, exist_ok=True)
    for t in sorted(targets):
        mine = [r for r in recs if r[1] == t]
        for k, h, size, hd, md5, nm, spec, b in mine:
            print('=== TARGET 0x%08x %s size=%d %dx%d fmt=%d flags=0x%x datasize=%d pitch=%d bpp=%d tail=[%s] md5=%s' % (
                h, k, size, hd['w'], hd['h'], hd['fmt'], hd['flags'], hd['datasize'], hd['pitch'], hd['bpp'], hd['tail'], md5))
            same = [r for r in recs if r[4] == md5 and r[1] != h]
            print('  identical bytes:', ', '.join('%s %s' % (r[0], r[5]) for r in same) or 'none')
            sd = sorted({(r[0], r[5]) for r in recs if r[3]['w'] == hd['w'] and r[3]['h'] == hd['h'] and r[1] != h})
            print('  same dimensions (%d):' % len(sd), ', '.join('%s:%s' % (s, n.split('\\')[-1]) for s, n in sd[:40]))
            _, px = ric.decode_xbox(b)
            pxf = px.astype('float64')
            # pixel statistics: unique colours, mean per channel (B,G,R,A), alpha range
            print('  pixels: unique colours %d, mean BGRA %s, alpha min/max %d/%d' % (
                len({tuple(v) for v in px.reshape(-1, 4)[::97]}), [round(float(v), 1) for v in pxf.reshape(-1, 4).mean(0)],
                int(px[..., 3].min()), int(px[..., 3].max())))
            for r in recs:
                if r[1] == h or r[3]['w'] != hd['w'] or r[3]['h'] != hd['h'] or r[5] == '?': continue
                try: _, q = ric.decode_xbox(r[7])
                except Exception: continue
                d = abs(q.astype('float64') - pxf).reshape(-1, 4).mean(0)
                # same without an 8-pixel border (the menu previews carry a white frame)
                dd = abs(q.astype('float64') - pxf)[8:-8, 8:-8].reshape(-1, 4).mean(0)
                print('  diff vs %-6s %-45s mean|d| BGRA %s  inner(-8px) %s' % (r[0], r[5].split('\\')[-1], [round(float(v), 1) for v in d],
                                                                               [round(float(v), 1) for v in dd]))
            if a.png_dir:
                p = os.path.join(a.png_dir, 'UNNAMED_%08x_%s.png' % (h, k))
                ric.to_png(ric.xbox_to_pc(b), p); print('  png', p)
    if a.png_dir:
        for sub in a.png_names:
            for k, h, size, hd, md5, nm, spec, b in recs:
                if sub.lower() in nm.lower():
                    p = os.path.join(a.png_dir, '%s_%s.png' % (nm.split('\\')[-1][:-4], k))
                    try: ric.to_png(ric.xbox_to_pc(b), p); print('png', p)
                    except Exception as e: print('png failed', nm, e)


if __name__ == '__main__':
    main()
