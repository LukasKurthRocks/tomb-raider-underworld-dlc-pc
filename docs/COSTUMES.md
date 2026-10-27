# Xbox 360 costume packs - notes

Not handled by upstream (no mention in STATUS/FINDINGS/INVESTIGATION; `tools/costume_cmp.py` compares DLC costume
objects with the Xbox base `lara_*` objects).

## Which pack is which (from the data, 2026-10-27)

Each pack has 13 records: two costume DRMs, their outfit preview images, the object/unit lists and six
`locals.bin` (one per language). Content folders under `Content/534307EC/00000002/`:

| Pack | Content folder | Costume DRMs | Preview (outfit select image) | Pack |
|---|---|---|---|---|
| `pack1.000` | `E5AFB2B959A72C52120D73678AED11BD8752686753` | `dlc_costume_k`, `dlc_costume_p` | red wetsuit / blue wetsuit with shorts | Wetsuit Costume Pack |
| `pack2.000` | `9FDDD06617D1016DE468ACF53AC663E8BA2AD41853` | `dlc_costume_a`, `dlc_costume_h` | classic Lara (teal top, shorts) / olive top + shorts | Classic Costumes |
| `pack20.000` | `AC0089F81B621CD0E0C156B6176EFCC6C844705D53` | `dlc_costume_l`, `dlc_costume_m` | white/grey outfit / black catsuit with blue belt | Designer Costume Pack |

Previews are `xenon-w\image\dlc_outfit_costume_<x>.raw` ('!WAR' images), converted with
`raw_image_convert.xbox_to_pc` + `to_png`. Each costume DRM is ~31-32 MB.

English costume names in the packs' `locals.bin` (spec 0xfffff7e1, pack20 version, 1407 strings):
48 "Wetsuit", 61 "Classic Lara", 62-70 bikinis (Blue, Black and White, Red, Camo, Bright Blue, Gold),
72 "Fashion Winner", 73 "People's Choice", 76 "Blue Wetsuit", 77-80 "Dopple Costume 1-4".
Open: which string index belongs to which costume object (l/m, name of h) - to be found in the outfit table
(the loading screen script, Script id 6, loads "all DLC Costume images" and lists `dlc_costume_a..p.drm` and
`dlc_doppel_costume_a..d.drm`).

## In game (Xbox, Xenia)

Outfits are chosen on the level start screen; in a first playthrough PDA -> Revisit Location is greyed out, so the
costume menu needs a finished game (Treasure Hunt). pack20 also brings a Doppelganger costume
(`dlc_doppel_costume_a` in its object list).
