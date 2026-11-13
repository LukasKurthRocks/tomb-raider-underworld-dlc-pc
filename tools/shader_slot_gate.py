r"""Pipeline step "Shaders", slot / surrogate gate (P4a, 2026-11-13, workspace docs Befund-P4a-Shader-1311.md).

Why: a material whose pass-2 pixel shader stays a converter surrogate (shader_translate refused the group) kept it
SILENTLY. Two live finds 13.11. (Befund-DLC1-Schleusentor-1311.md): sluice gate 21087 (Xbox 2188) drew the RGB blend
mask on s5 as colour with surrogate 1698; DLC 1 water 23171 / 23172 (Xbox 2195) drew nothing - surrogate 1008 has no
permutation slot 1 (Xbox 2195 uses slots 0 and 1).

Per effective DRM of a layer stack (later layer wins) that has an Xbox twin in the tu_batch xdump folder, per material
pair (tu_shader_night.mats_of) with an Xbox pass-2 lib of the DLC shader map:
  SLOT GAP  (ERROR, exit 1): the PC pass-2 lib lacks an occupied permutation slot of the Xbox lib (slot index compare,
            as tools/shaderlib_slot_audit.py). Class A (byte-identical base twin) is exempt - base-game gaps of the same
            pairs exist in the retail PC game too (1026 -> 1448, 277 -> 333).
  SURROGATE (WARNING): Xbox lib untranslated (C1-C3 / D) and the PC pass-2 lib a converter surrogate; with the static
            role check of tu_batch.binding_check (vm=False): record roles the Xbox shader samples that the surrogate
            does not, or reads in another role (e.g. 1698 on 21087: blend mask read as light map). Printed as
            'WARNING SURR_ROLE', never silent.
--known FILE (tsv rel / mat / xlib / note): slot gaps accepted on purpose (printed as WARNING KNOWN_GAP, no exit 1).
Exit 1 on any unaccepted slot gap, 0 otherwise.

Usage (from the repository root):
  ../bin/pyt -t 1800 tools/shader_slot_gate.py check --layers L1[,L2,...] [--xbox work/sg_audit_0511/xbox]
        [--known FILE.tsv] [--only REL[,REL]] [--report FILE.json] [--no-roles]
Developer data (not on the player path yet): the Xbox xdump folder, work/render/shaderlibs.pkl, the shader map.
"""
import sys, os, json, struct, collections, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def arg(argv, key, default=None):
    if key in argv:
        j = argv.index(key); v = argv[j + 1]; del argv[j:j + 2]; return v
    return default


def occ(lib):
    return {i for i, o in enumerate(lib['slots']) if o != 0xffffffff}


def check(argv):
    layers = (arg(argv, '--layers') or '').split(',')
    xdir = arg(argv, '--xbox', 'work/sg_audit_0511/xbox'); knp = arg(argv, '--known'); rep = arg(argv, '--report')
    only = arg(argv, '--only'); roles = '--no-roles' not in argv
    only = {x.lower() for x in only.split(',')} if only else None
    if not layers[0]: raise SystemExit(__doc__)
    known = {}
    if knp:
        for l in open(knp, encoding='utf-8').read().splitlines()[1:]:
            c = l.split('\t')
            if len(c) >= 3: known[(c[0].lower(), int(c[1]), int(c[2]))] = c[3] if len(c) > 3 else ''
    t0 = time.time()
    gaps, surr, ok, nfiles, errors = scan(layers, xdir, only, roles, known)
    return report(layers, gaps, surr, ok, nfiles, errors, t0, rep)


def scan(layers, xdir='work/sg_audit_0511/xbox', only=None, roles=True, known=None):
    """-> (slot gaps, surrogate copies, pairs ok, files, errors); also used by shader_translate --scope-gaps"""
    import shaderlib as SL, tu_batch as TB, tu_light_transplant as TLT, tu_shader_night as TN
    from tu_light_transplant import libs
    known = known or {}
    eff = {}
    for L in layers:
        if not os.path.isdir(L): raise SystemExit('layer not found: %s' % L)
        for dp, dn, fn in os.walk(L):
            dn[:] = [d for d in dn if 'truguard' not in d.lower()]
            for f in fn:
                if f.lower().endswith('.drm') and 'truguard' not in f.lower():
                    rel = os.path.relpath(os.path.join(dp, f), L).replace('\\', '/')
                    eff[rel.lower()] = (rel, os.path.join(dp, f))
    def xfile(rel):
        b = os.path.basename(rel).lower()
        for pk in ('ack11', 'ack10'):
            q = os.path.join(xdir, pk, b)
            if os.path.isfile(q): return q
        return None
    L = libs()
    gaps = []; surr = []; ok = 0; nfiles = 0; errors = []
    for k in sorted(eff):
        rel, path = eff[k]
        if only is not None and k not in only: continue
        xf = xfile(rel)
        if xf is None: continue
        try:
            P = TLT.load(path, 'le')[1]; X = TLT.load(xf, 'be')[1]
        except Exception as ex:
            errors.append('%s: not readable %s' % (rel, ex)); continue
        nfiles += 1
        for pm, xm, _ in TN.mats_of(P, X):
            if (10, pm) not in P or (10, xm) not in X: continue
            pt = struct.unpack_from('<4I', P[(10, pm)].data, 0x28); xt = struct.unpack_from('>4I', X[(10, xm)].data, 0x28)
            xl, pl = xt[2], pt[2]
            if xl in (0, 0xffffffff): continue
            cl = TN.cls(xl)
            if cl in ('A', 'base', '-'): continue
            xlib = SL.parse(X[(9, xl)].data, 'be') if (9, xl) in X else L['D'].get(xl)
            plib = SL.parse(P[(9, pl)].data, 'le') if (9, pl) in P else L['P'].get(pl)
            e = dict(rel=rel, mat=pm, xmat=xm, xlib=xl, cls=cl, pc=pl)
            if xlib is None or plib is None:
                e['why'] = 'lib not found (Xbox %s / PC %s)' % (xlib is not None, plib is not None); gaps.append(e); continue
            miss = sorted(occ(xlib) - occ(plib))
            e.update(xocc=sorted(occ(xlib)), pocc=sorted(occ(plib)))
            sur = cl in TB.UNTR and TB.is_surrogate_lib(pl)
            if sur:
                e['probs'] = []
                if roles:
                    try:
                        _, pr = TB.binding_check(P, X, pm, xm, xl, P[(9, pl)].data if (9, pl) in P else None, bool(TB.lit_lib(xl)), vm=False) \
                            if (9, pl) in P else (None, ['surrogate %d not in the file (base lib): role check needs the file section' % pl])
                        e['probs'] = pr
                    except Exception as ex:
                        e['probs'] = ['role check error %s %s' % (type(ex).__name__, str(ex)[:100])]
                surr.append(e)
            if miss:
                e['missing'] = miss
                kk = (rel.lower(), pm, xl)
                if kk in known: e['known'] = known[kk]
                gaps.append(e)
            else: ok += 1
    return gaps, surr, ok, nfiles, errors


def report(layers, gaps, surr, ok, nfiles, errors, t0, rep):
    bad = [g for g in gaps if 'known' not in g]
    for g in gaps:
        print('%s %s:%d Xbox %d (%s) -> PC %s: %s' % ('WARNING KNOWN_GAP' if 'known' in g else 'ERROR SLOT_GAP', g['rel'], g['mat'], g['xlib'], g['cls'], g['pc'],
              g.get('why') or 'Xbox slots %s, PC slots %s, missing %s%s' % (g['xocc'], g['pocc'], g['missing'], (' (' + g['known'] + ')') if 'known' in g else '')))
    for s in surr:
        print('WARNING %s %s:%d Xbox %d (%s) keeps converter surrogate %d%s' % ('SURR_ROLE' if s['probs'] else 'SURROGATE', s['rel'], s['mat'], s['xlib'], s['cls'], s['pc'],
              (': ' + '; '.join(s['probs'][:3])) if s['probs'] else ''))
    for x in errors: print('ERROR ' + x)
    print('SUMMARY shader_slot_gate: %d files, %d pass-2 pairs ok, %d slot gaps (%d accepted), %d surrogates (%d with role problems), %d errors, %.0f s -> %s' % (
        nfiles, ok, len(gaps), len(gaps) - len(bad), len(surr), sum(1 for s in surr if s['probs']), len(errors), time.time() - t0,
        'FAIL' if bad or errors else 'PASS'))
    if rep:
        os.makedirs(os.path.dirname(os.path.abspath(rep)), exist_ok=True)
        json.dump(dict(layers=layers, gaps=gaps, surrogates=surr, errors=errors, ok=ok, files=nfiles), open(rep, 'w', encoding='utf-8'), indent=1, default=str)
    return 1 if bad or errors else 0


def main(argv):
    if not argv or argv[0] != 'check': raise SystemExit(__doc__)
    return check(list(argv[1:]))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
