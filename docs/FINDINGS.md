# Verified technical findings -> moved to ENGINE.md

This file used to hold a compact list of verified facts ("verified" = checked against base-game Xbox / PC pairs, against
decompiled engine code, or in a running game). Since 2026-11-08 all of it lives in **[ENGINE.md](ENGINE.md)**, the engine
reference by topic; entries taken from here are marked "from FINDINGS.md" there. Do not add new facts to this file:
every new engine fact goes into the matching ENGINE.md section in the same commit (ENGINE.md section 26).

| Former topic here | Now in ENGINE.md |
|---|---|
| Containers and ids (sections, relocations, texture cache, same-id rule, dead bits, own lib id per translated material) | section 2 |
| Materials (header offsets, MaterialParams role mapping, DXN normals) | sections 17.1, 17.4 |
| Shaders (light transplant, lib 242 slots, fog read, harness rules, sampler limit s0..s15) | sections 17.3, 17.4 |
| Engine functions and crashes (fmod / light / SoundPlex guards, D3D boot crash, uber command list, script VM) | sections 7.1, 9, 16, 18.1, 18.5 |
| Cutscene command lists, grapple ring records (tag 0x404) | section 2 |
| Audio history (silence first, then XMA -> IMA ADPCM), u16-swapped SoundPlex type words | sections 18.1, 18.4 |
