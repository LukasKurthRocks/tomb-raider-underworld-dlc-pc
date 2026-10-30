# Related work and techniques

This file collects people, projects and processes that work on the same kind of problem as this port:
converting console-only game content into a format that a PC build of the same engine can load, without
shipping game data. It was compiled on 2026-10-29 from web research (web search plus fetching each project's
README, documentation or forum post). Facts are taken from the linked source. "(unverified)" marks a claim
that comes only from a search snippet or secondary summary, or that could not be confirmed in a primary source.
"Useful for us" lines are our own assessment, not claims by the projects.

## Terminology

| Term | Meaning | How it applies to this project |
|---|---|---|
| Content port | Moving assets/levels/DLC from one platform build of a game to another platform build of the same engine (as opposed to porting the engine). | What trudlcport does: Xbox 360 DLC data into the Steam PC build of TRU. |
| Asset extraction / conversion pipeline | Tooling that reads user-supplied original data and turns it into what the target build loads (e.g. Ship of Harkinian's `.o2r`, sm64's `extract_assets.py`). | Our `install_dlc.py` + kit is such a pipeline (unpack, CDRM, DRM sections, remap, patch). |
| Bring your own data (BYOD) | Repo and releases contain no game data; the user supplies a dump, which is verified and converted locally. | Our distribution model: user supplies `pack10.000` and the DLC credits video. |
| Matching / byte-matching | Decompilation term: rebuilt output is byte-identical to the original binary (dtk, sm64 `COMPARE`, zeldaret/tp). | We "match" our rebuild against the author's B138 build, file by file. |
| Golden master / characterization test | Record the full output of a known-good run and compare later runs against it (term from *Working Effectively with Legacy Code*). | B138 outputs are our golden masters; every pipeline stage is a characterization test. |
| Reproducible build | "Given the same source code, build environment and build instructions, any party can recreate bit-by-bit identical copies of all specified artifacts" (reproducible-builds.org). | Goal for our Windows rebuild: same inputs -> same kit bytes on any machine. |
| Independent oracle | A second, independently written implementation used to cross-check results (xenos-toolchain checks its output against XenosRecomp). | Use Noesis/TRLAU plugin, Yura or Xenia as oracles for our converters. |
| Semantic diff | Compare decoded structures field by field instead of raw bytes (bethesda-multitool `esm semdiff`). | Explains *why* a section differs from B138 when the byte diff fails. |
| Paired data / differential analysis | Compare the same asset as it exists on two platforms (or before/after an edit) to infer the format or a mapping. | How we learn Xbox->PC ID maps and the DEC3N->UBYTE4N table from base-game files present on both platforms. |
| Static recompilation | Translating a console executable ahead of time into C/C++ (XenonRecomp, N64Recomp, ps3recomp, PS2Recomp, xboxrecomp). | Not our approach (we keep the PC exe), but their asset/shader side tools apply. |
| HLE | High-level emulation: reimplementing system libraries instead of emulating hardware. | Not used; relevant only for understanding recomp projects. |
| Endian swap | Big-endian console data (Xbox 360, PS3) -> little-endian PC. Must be type-aware: 16-bit pairs swapped as one 32-bit word end up in the wrong order. | Every DRM section and vertex stream; see XenosRecomp's YXWZ note below. |
| Tiling / swizzling | Console GPUs store textures in non-linear layouts; Xbox 360 uses 32x32 tiles with a micro-tiling address function (Xenia). | Xbox texture sections must be untiled before they match PC data. |
| Vertex declaration | D3D9 array of `D3DVERTEXELEMENT9` (Stream, Offset, Type, Method, Usage, UsageIndex = 8 bytes each) describing a vertex layout. | Our unknown 8-byte decl hash is presumably computed over such elements (unverified). |
| DEC3N / UBYTE4N | `D3DDECLTYPE_DEC3N`: signed 10:10:10, expanded to v/511.0. `UBYTE4N`: 4 bytes each /255.0 (Microsoft docs). | Our normal conversion Xbox DEC3N -> PC UBYTE4N. |
| Xenos microcode | The Xbox 360 GPU's shader instruction format (Adreno-200-derived; Xenia `ucode.h`). | Source format of the DLC ShaderLib sections. |
| STFS (CON/LIVE/PIRS) | Xbox 360 package container for DLC, saves, updates (Free60). | Users' DLC dumps come in LIVE packages before extraction. |
| XMA / XMA2 | Xbox 360 audio codec; decoded in practice via FFmpeg (vgmstream wraps it). | Possible source codec for DLC streams before re-encoding to `.mul`. |
| specMask | Bigfile/DRM bitmask selecting locale or "next gen" variants (cdcengine.re). | Must be carried over correctly when DLC files are merged into the PC set. |

## Projects

### cdcEngine / Tomb Raider (Legend, Anniversary, Underworld) and related cdcEngine games

**cdcengine.re documentation** - https://cdcengine.re/docs/ (maintained alongside TheIndra55/cdcResearch)
- Platform: mostly PC; Legend-era focus.
- What: format docs for Bigfile, Data Ram (`.drm`), IDMap, Image (`.raw`), MultiplexStream (`.mul`), Tiger archives; a hash database of file lists (https://cdcengine.re/hashdb/).
- Relevant: DRM = `SectionList` header (version 14 in Legend), per-section `SectionInfo` (size, type, versionID, packed relocation count `>>8`, id, specMask), relocations before section data, 16-bit relocation type/section field + offset. Section types 0 General ... 5 Texture, 6 Wave, 7 DTPData, 9 ShaderLib. Bigfile: CRC-32 (poly 0x4C11DB7) file-name hashes, 2048-byte sectors, Underworld alignment 0x7FF00000, specMask for locale/next-gen variants; Xbox 360 Legend used zlib compression. `.raw` images: `RAW!` magic, PC mode table (DXT1..5, A8R8G8B8 ...). The `.mul` page only says packets carry audio or cinematic data (no codec detail).
- Useful for us: cross-check our DRM/bigfile notes against this page and contribute TRU-specific (version, Xbox) details back upstream.

**TheIndra55/cdcResearch** - https://github.com/TheIndra55/cdcResearch
- Research notes (Legend/Anniversary) with the caveat that they may contain wrong information. Useful for us: background reading before reversing unknown section fields.

**TheIndra55/cdcEngine** - https://github.com/TheIndra55/cdcEngine
- Decompilation of Tomb Raider: Legend (GPL-3.0, premake). The DRM docs point to its `tr7/game/resolve/Resolve.cpp` as the reference relocation code. Matching status not stated.
- Useful for us: read the resolve and render code for how sections, relocations and (possibly) vertex declarations are processed in the engine family (vertex-decl code presence unverified).

**TheIndra55/Yura** - https://github.com/TheIndra55/Yura
- Bigfile browser (GPL-3.0) for LoK Defiance through Shadow of the TR, incl. Underworld; previews images and locale files; uses `.txt` file lists to name hashed entries.
- Useful for us: independent oracle to open our rebuilt bigfile/DRM output and confirm it parses.

**TheIndra55/TRLAU-menu-hook** - https://github.com/TheIndra55/TRLAU-menu-hook
- In-game menu and patches for Legend/Anniversary/Underworld (GPL-3.0): free camera, level select, instance viewer/spawner, restored debug, collision/markup/portal drawing, mod loader, DEP crash fix.
- Useful for us: level select + instance viewer + debug drawing are ideal for in-game verification of converted DLC levels.

**TombRaiderModding/ModLoader** - https://github.com/TombRaiderModding/ModLoader
- Loads files from a `mods` folder without modifying bigfiles; Legend, Anniversary, Underworld, Guardian of Light (GPL-3.0). Already a dependency of trudlcport.
- Useful for us: keep the mods-overlay model; no bigfile rewriting needed.

**Gh0stBlade/cdcEngineTools** - https://github.com/Gh0stBlade/cdcEngineTools
- CDRM (decompresses Underworld DRM blocks) and DRM (section extractor) tools, plus PCD2DDS and WAVE2WAV folders; repo topics list 360/xenon/ps3/wii/pc. README warns to use the correct game/platform build of the tool.
- Useful for us: second implementation of CDRM decompression and section split to diff our extractor against.

**Gh0stBlade Noesis importer plugins (Tomb Raider Forums)** - https://www.tombraiderforums.com/showthread.php?t=208182
- Thread lists `fmt_TR8_mesh_2_4.py` for Underworld [PC/XENON]; workflow: unpack bigfile, decompress DRM, extract sections; materials limited because "controlled by the shaders". A user (aman11) posted `tr8drmhash` producing `hash2section.bin` for material/texture lookup (from search snippet; unverified - forum not fetchable).
- Useful for us: an existing reader of *Xbox 360* TR8 mesh sections, i.e. a reference for the Xbox vertex layout.

**TRLAU Modding Tools (Raq)** - https://tombraidermodding.com/tool/trulau-mod-tools
- Noesis plugin v1.2 (2024-09-04): import/export for Legend/Anniversary/Underworld/Guardian of Light/Temple of Osiris; `.tr8mesh` (PC) and Xbox 360 textures `.tr8x360` / `.raw` for Underworld.
- Useful for us: independent decoder for Xbox 360 TRU textures - compare its decoded pixels with our untiled/converted PC textures.

**Raq1/cdcEditor** - https://github.com/Raq1/cdcEditor
- Blender toolset (MIT) for Legend/Anniversary/Underworld: models, levels (geometry, collision, signals, placement, lights), animations, cutscenes. Underworld support matrix covers PC, PS2, PS3, Xbox 360, Wii with partial model support (table partly garbled in fetch; check README).
- Useful for us: view converted DLC meshes/levels outside the game; also a documented reader of multiple platform variants.

**Raq1/TR7AE-Mesh-Exporter** - https://github.com/Raq1/TR7AE-Mesh-Exporter
- Noesis plugin exporting custom models to the Legend/Anniversary mesh format (search result only). Useful for us: example of *writing* cdc meshes, i.e. which header fields the engine validates.

**TheSerioliOfNosgoth/ModelEx** - https://github.com/TheSerioliOfNosgoth/ModelEx and **Soul Spiral** - https://thelostworlds.net/Software/Soul_Spiral.html
- ModelEx views/exports models of Soul Reaver 1/2, Defiance, Gex 3, Legend, Anniversary (not Underworld). Soul Spiral unpacks older cdc `bigfile.dat` archives.
- Useful for us: history of the format family; limited direct use for TRU.

**sergen213/openunderworld** - https://github.com/sergen213/openunderworld
- Native Linux reimplementation of the TRU engine in C++20 (OpenGL 4.6/Vulkan 1.3, GPL-3.0-or-later); reads the user's install read-only (tested with GOG `tru.exe` 1.1.0.0); first level walkable; experimental. Releases ship SHA-256 checksums and Ed25519-signed update manifests; CI builds every commit.
- Useful for us: a second, independent TRU DRM/mesh/shader reader; worth comparing notes on PC section layouts. Also a model for signed, checksummed releases.

**rrika/cdcEngineDXHR** - https://github.com/rrika/cdcEngineDXHR and **rrika/dxhr** - https://github.com/rrika/dxhr
- Non-matching decompilation of Deus Ex: Human Revolution DC (IDA, cleaned up), integrating leaked TR2013 debug info (since 2022-07-14); runs with the user's BIGFILE; Linux via dxvk-native. `dxhr` has `drmexplore`, `bigfuse` (mount bigfile), and Blender `cdcmesh.py`/`drm.py`.
- Useful for us: later cdc renderer code with real names - the best public place to look for how cdc builds and hashes vertex declarations (whether it is there is unverified).

**vardonir/pyDXHR** - https://github.com/vardonir/pyDXHR and **Gibbed DeusEx3 tools** - https://www.moddb.com/games/deus-ex-3/downloads/gibbeds-deus-ex-hr-tools
- pyDXHR: bigfile unpack, DRM decompress/unpack, DRM-to-glTF. Gibbed: Unpack/Pack bigfiles, DRMDecompress, DRMEdit, and Demux that converts MUL audio to FSB (from search results; unverified beyond them). cdcengine.re also lists Gibbed's bigfile tool (https://cdcengine.re/docs/tools/gibbed/).
- Useful for us: Demux is an existing MUL parser for a sibling game - reference for our `.mul` writer.

**Earlier TRU DLC port attempt (Tomb Raider Forums, 2013)** - https://www.tombraiderforums.com/archive/index.php/t-198260.html
- "[PC] Beneath the Ashes and Lara's Shadow DLC Pack" thread; per search snippet: textures could be replaced, but swapped model files made the engine allocate the wrong amount of memory and crash; stalled (unverified - forum returned 403). Xenia was the usual way to play the DLC on PC.
- Official status: Tomb Raider Chronicles (2024-04-26) reports a 2021 statement from Crystal Dynamics' community director that legal progress had been made and resources were being considered, then no news (https://www.tombraiderchronicles.com/headlines4873.html).
- The forum now shows threads only to logged-in users and the Wayback Machine excludes it. Two threads were read
  from copies saved by a logged-in user (2026-10-29); quotes below are from those copies:
  * **[PC] TRU DLC Menu** (t=178907, 2011-02-27), Gh0stBlade: "the DLC menus are existant and fully functional ...
    At the moment, it's unknown how to force the executable to load a fake DLC package and run the contents
    inside." Another member: Microsoft paid for the levels in exchange for 360 exclusivity. (trudlcport solved the
    loading part with a mod loader overlay and a patched `tru.exe`.) The thread (175 posts, 2011-2021) goes on:
    - 2011-03: adding fake pack files to the game folder is not detected as DLC. A member who disassembled `tru.exe`
      1.1: "There is no function which searches for DLC packs, BUT ... there is one interesting file patch.000! We
      could add the DLC files into it!" Also found then: XMA vs. PC ADPCM `.mul` audio (the game's ADPCM routine
      was posted), Xenos texture swizzling, CRC-32 file-name hashes (a name grabber hooked the game's hash
      function). 2011-04, Gh0stBlade's list of what a port needs: a bigfile tool that can inject files, "all file
      formats must be known ... for each platform", and locating animations, collision and spawn data.
    - 2020-06: Gh0stBlade, "First X360 Model ported from X360 to PC"; the first screenshot "shows bad bi normals
      normals and tangents" - the same symptom our DEC3N table fixed (finding 37).
    - 2021: another member put a costume (`dlc_costume_n.drm` + its `.raw` image) **into `patch.000`** and the PC
      game used it in the DLC costume slot - the costume slots load from `patch.000` without a mod loader. Their
      progress on the Xbox costumes: materials, animations, objects done; textures unswizzled; audio XMA1 ->
      FSB4; "mesh files => 0% / shader => 0% / DtpData => 0% / script files => 0%".
  * **Beta and Cut Content + Costumes List** (t=204503, 2014-03 to 2019-07): the PC demo data lists costume slots
    `dlc_costume_a` .. `_p` (16) and `dlc_doppel_costume_a` .. `_d`; another member says these are placeholder
    slots, from which he had extracted the 360 DLC costumes. Gh0stBlade (2014-03-16, with his Noesis `.RAW` image
    plugin): `d` and `i` are unreleased recolours, `g` has the same picture as `o`, `n` is unknown (scrambled
    image), the doppelganger images are placeholders; `wp_dlc_gold_shotgun` ships in the Beneath the Ashes pack
    but is unused. On porting (2014-03-08): "I can swap textures ... But..... when it comes to swapping singular
    mesh files... The game just won't have any of it. Until I can find a way of swapping individual meshes without
    the game freezing, I won't be porting the DLC costumes." **Why it stopped** (2019-05-29, another member): "He did
    start, but I think he eventually gave up on it. IIRC shaders were proving to be too much of a hassle".
  * **[PC] Beneath the Ashes and Lara's Shadow DLC Pack** (t=198260, 2013-03 to 2023-01, 234 posts), Gh0stBlade:
    2013-03: the 2011 group never really formed, the unpacker/injector of another member was not finished, and "there
    are no injection/repack tools for the game so sadly, it's not possible at this time". 2014-08-17: "I have made
    out enough of the mesh/drm formats to be able to edit/re-inject files", but swapping the mesh of one costume DRM
    into another still froze the game; "I cannot see the stages being possible on PC ... too much hard-coded";
    "The shaders/material formats are so unknown though, it's making this project hell"; idea: "re-use existing
    shaders that match" (what upstream's `pc_copy` shader route does). His tool set then: Gibbed's bigfile
    extractor, his CDRM decompressor and DRM section extractor, and a Noesis mesh importer (with Chrrox) that
    decodes "Xbox Normals" - an independent check for our DEC3N table (finding 37).
  * **CD trying to bring the DLC to PC** (t=225774, 2021-02 to 2026-10, 169 posts): the 2021 statements of Crystal
    Dynamics (legal progress, resources to be decided), then years of waiting; 2025-03 members point to
    XenonRecomp / XenosRecomp (hedge-dev) as a possible native route; 2026-10 members report fan ports of other
    360-exclusive DLCs to PC (Overlord II "Battle Rock Nemesis", Prince of Persia 2008 "Epilogue"), and one member
    shows an own work-in-progress TRU DLC port ("I'm in-game", 2026-10-12; video 2026-10-17 - whether this is the
    trudlcport author is not stated).
  * Screenshots posted in these threads (shown from the forum members' original uploads on imgur, not copied into
    this repository; checked online 2026-10-29; click for full size):

    | Screenshot | What it shows | Useful for |
    |---|---|---|
    | <a href="https://i.imgur.com/od0lwMJ.png"><img src="https://i.imgur.com/od0lwMJ.png" width="320" alt="Xbox DLC mission screen in Xenia"></a><br>t=198260, 2020 | Xbox DLC mission screen in Xenia: "Beneath the Ashes" selected, title light blue centred above the description, PLAY MISSION / RETURN TO MAIN MENU | independent check of the Xbox reference in `docs/DLC_MENU.md` |
    | <a href="https://i.imgur.com/y98Qy2j.png"><img src="https://i.imgur.com/y98Qy2j.png" width="320" alt="First Xbox model on PC"></a><br>t=178907, 2020-06 | Gh0stBlade's first Lara model converted from Xbox, in the PC game | the state of the earlier attempt |
    | <a href="https://i.imgur.com/XsAcHPW.png"><img src="https://i.imgur.com/XsAcHPW.png" width="320" alt="Noesis trumesh viewer"></a><br>t=198260 | a TRU mesh with skeleton in Noesis ("trumesh") | an independent mesh reader to cross-check converted meshes |
    | <a href="https://i.imgur.com/T5WGw3I.png"><img src="https://i.imgur.com/T5WGw3I.png" width="320" alt="Xbox Marketplace entries"></a><br>t=198260 | Xbox Marketplace: Beneath the Ashes released 2009-02-24, Lara's Shadow 2009-03-10 | background |

    Two 2021 screenshots of a costume loaded from `patch.000` in the PC game (white heavy snow outfit in a DLC
    costume slot) are forum album pictures visible to logged-in users only; they are described above, not linked.
    One shows the level costume menu of Jan Mayen Island on PC listing "Snow Heavy", "Snow Light" and **"Extra
    Costume 14"** (the `patch.000` costume, selected, with its preview image) - the DLC costume slots are already
    wired into the PC game's per-level costume menu; for the costume packs (`docs/COSTUMES.md`) only the converted
    files are missing.
  * External links in these threads (27, checked 2026-10-29; 3 YouTube videos gone, 2 file-host links not opened,
    3 pages unreachable). Worth keeping:
    - [Gh0stBlade/NoesisPlugins](https://github.com/Gh0stBlade/NoesisPlugins), `fmt_TR8_mesh_2_4.py` (TRU and
      Guardian of Light, PC/X360; successor of the 2014 plugin linked in the forum): reads the vertex declaration at
      `meshInfo[9] + 8` after skipping 8 bytes (the 8-byte hash of finding 37, which the plugin ignores), elements of
      8 bytes (u32 semantic hash, u16 offset, u8 type, u8 pad), and names 14 semantic hashes - Position `D2F7D823`,
      Normal `36F5E414`, Tangent `F1ED11C3`, Binormal `64A86F01`, PackedNTB `09B1D4EA`, SkinWeights `48E691C0`,
      SkinIndices `5156D8D3`, Color1 `7E7DD623`, Color2 `733EF0FA`, Texcoord1-4 `8317902A` / `8E54B6F3` /
      `8A95AB44` / `94D2FB41`, InstanceID `E7623ECF`; 360 normals via `decodeNormals32(..., -10, -10, -10)`.
      [Gh0stBlade/cdcEngineTools](https://github.com/Gh0stBlade/cdcEngineTools): CDRM / DRM / PCD2DDS / WAVE2WAV.
    - The trudlcport author's video "Tomb Raider: Underworld DLCs PC Port - Beneath the Ashes intro"
      (https://youtu.be/fsVqw8lTrt0, 2026-10-17) - posted in the thread by a member who calls the port their own
      project (that both are the same person is likely, not stated).
    - Nexus Mods ports of TRU costumes through the `mods/` folder, each adding an extra costume slot (e.g. a Wetsuit
      Costume Pack, https://www.nexusmods.com/tombraiderunderworld/mods/78; pages not readable, search results
      only) and TheIndra55/TRLAU-menu-hook's outfit switch (F9) - check before porting pack1/2/20 ourselves.
    - Xenia (game-compatibility issue #541, 2021): full game and DLC work with `render_target_path_d3d12 = "rov"`;
      a 2021 config uses `license_mask = 1` for the DLC - useful for our Xbox reference runs.
    - Other 360-exclusive DLCs ported to the Steam versions in 2026: Prince of Persia (2008) "Epilogue" and Overlord
      II "Battle Rock Nemesis" (methods not public).
- Why earlier attempts stalled: whole-file or whole-mesh swaps without id remapping, relocation rewriting and
  section-level conversion froze the PC game, and the shaders were the wall. trudlcport's generic converter solved
  the first part; the shaders are our open stage 3 - the same wall.
- Useful for us: costume pack work can start from the slot list above (check against our pack1/2/20 DLC files, not
  against forum posts); the shader stage is where the last attempt ended, so plan it with the references in
  "Techniques worth adopting" (b).

**Tomb Raider 2013 mesh modding (Tomb Raider Forums)** - https://www.tombraiderforums.com/showthread.php?t=213025
- Snippet: the game crashes if vertex or index buffer offsets change; many shader types complicate material work (unverified - forum not fetchable). Community tools for later cdc games reportedly name vertex attributes by 32-bit hashes (unverified; no primary source found).

### Xbox 360 (and original Xbox)

**Xenia** - https://xenia.jp/updates/2021/04/27/leaving-no-pixel-behind-new-render-target-cache-3x3-resolution-scaling.html, https://github.com/xenia-project/xenia/blob/master/docs/gpu.md
- Xbox 360 emulator; the reference for Xenos knowledge. Textures: 2D in 32x32-pixel (or block) tiles with micro-tiling, 3D in 32x32x4 tiles, 4 KB alignment; pitch rounded to 32. Shader tools: `--dump_shaders=path/` writes translated shaders named by input hash plus original microcode; `xe-gpu-shader-compiler` disassembles `.vs/.fs` microcode (`ucode`) or translates it; a Shader Playground turns red when Xenia's disassembly differs from the D3D compiler's; GPU trace dumps (`--trace_gpu_prefix`, F4) for frame-level debugging. 3D-tiling address code reconstructed in issue #1193 (https://github.com/xenia-project/xenia/issues/1193). Xenos has no integer shader ALU; integer fetch results are converted in-shader (xenia-canary PR #577, https://github.com/xenia-canary/xenia-canary/pull/577, search snippet).
- Useful for us: run the DLC in Xenia with `--dump_shaders` to get each DLC shader's microcode + a readable translation, and use GPU traces as the visual reference.

**hedge-dev/XenonRecomp** - https://github.com/hedge-dev/XenonRecomp
- Xbox 360 PPC -> C++ static recompiler (MIT). Endianness: loads byte-swap to little-endian, stores swap back; vector registers are reversed as whole 16-byte vectors so component order flips (e.g. WZY). Tested against Xenia's PPC test binaries via XenonTests.
- Useful for us: the "swap on access, keep a precise rule per type" discipline; their vector-reversal note is a warning for float4 data in our sections.

**hedge-dev/XenosRecomp** - https://github.com/hedge-dev/XenosRecomp
- Converts Xbox 360 shader binaries to HLSL (then DXC -> DXIL/SPIR-V), MIT, explicitly "not out of the box" for other games. Details: shader container holds constant reflection, definitions, interpolators, vertex declarations, instructions (only partly reversed). Constants: VS 256 float4, PS 224 float4, 16 booleans packed into an int. Control flow via `while`+`switch(pc)`. Vertex data endian-swapped as 32-bit words, which swizzles 16-bit formats to YXWZ (fixed per TEXCOORD with a bitmask). R11G11B10 normals/tangents unpacked manually in the VS. Unimplemented: integer constants, dynamic register indexing, mini vertex fetch, 1D textures, memory export, point size. Xenia credited as primary reference. Many forks (one decompresses XMemCompress-wrapped shader archives).
- Useful for us: the most direct starting point for Xenos -> HLSL; would need a Shader Model 3 / D3D9 back end (fxc) instead of DXC.

**hedge-dev/UnleashedRecomp** - https://github.com/hedge-dev/UnleashedRecomp
- Native PC port of Sonic Unleashed (GPL-3.0). Users supply their own 360 dumps (disc, title update, optional DLC); an installer runs "many integrity checks", accepts only original unmodified files, auto-detects content in containers, and generates a patch; `--install-check` validates an existing install (release notes, search snippet). Game files remain the same across versions.
- Useful for us: the installer UX (auto-detect container, refuse modified input, `--check` mode) matches ours; adopt the "install-check" idea for an existing install.

**xenosworks/xenos-toolchain ("xost")** - https://github.com/xenosworks/xenos-toolchain
- Open Xenos shader disassembler/assembler (archived; moved to `xsdk` on 2026-10-14). Verification claims: real XDK blobs disassemble and reassemble byte-identically; encoders fuzz-tested as inverses of the decoder; output cross-checked against XenosRecomp as independent oracle. ISA tables transcribed from Xenia (which derives partly from freedreno).
- Useful for us: a Xenos container parser plus the exact verification pattern we want for shaders (round-trip + independent oracle).

**slfx77/DDXConv** - https://github.com/slfx77/DDXConv (fork of kran27's tool)
- Fallout New Vegas Xbox 360 `.ddx` -> `.dds` (MIT). Untiling code from Xenia, XCompression for decompression; reports 22,148 of 26,123 prototype textures converted correctly; debug switches `--no-untile`, `--no-swap`, `--raw`, `--save-mips`; has a test project.
- Useful for us: per-stage disable switches (untile/swap) make texture bugs bisectable; report success as a count.

**slfx77/bethesda-multitool** - https://github.com/slfx77/bethesda-multitool
- Whole-install Xbox 360 -> PC conversion for Fallout New Vegas (0BSD): NIF meshes with "geometry expansion + endian conversion", schema-driven ESM endian swapping (`SubrecordSchemaRegistry`), XMA -> WAV/MP3 via FFmpeg, BSA repack. Verification: `esm semdiff` against a PC reference ESM, `report validate`/`report consistency`, CI test project. Format docs in `docs/Xbox_360_ESM_Format.md` and `docs/Xbox_360_DDX_Format.md`.
- Useful for us: closest analogue to trudlcport; copy the schema-driven swap and the semantic diff against a PC reference.

**Xbox 360 texture untiling write-ups** - https://reshax.com/topic/846-unswizzling-xbox-360-textures-condemned-2-lithtech-jupiter-ex/
- C versions of `XGAddress2DTiledX/Y` (adapted from RareView); notes the 360 swizzle combines nested tiling, interleaving and parity swapping (search snippet). A GTA IV tool PR (https://github.com/galaxygas/Eyefinder/pull/20) reportedly untiled 27,805 texture levels byte-identically using Xenia's layout code (unverified - page returned 404).
- Useful for us: if the DLC contains textures also present on PC, byte-identical untile counts are a cheap correctness metric.

**SunJaycy/sk83.GLB2ARENA** - https://github.com/SunJaycy/sk83.GLB2ARENA
- Skate 3 custom-model tool for PS3/Xbox: decodes packed Xbox 360 GPU vertex formats (SHORT4N, DEC3N, UBYTE4N, FLOAT16_*), uses 16-byte Xbox `VertexDescriptor` elements with `D3DDECLUSAGE` semantics vs 8-byte PS3 elements, notes reversed blend index/weight byte order on Xbox and a different binormal cross-product convention.
- Useful for us: confirms DEC3N use on 360 in another engine, and that blend data byte order can differ per platform - check BLENDINDICES/BLENDWEIGHT carefully.

**Velocity and STFS tools** - https://github.com/hetelek/Velocity, https://free60.org/System-Software/Formats/STFS/, https://github.com/D221/x360-rs
- STFS (CON/LIVE/PIRS) viewer/extractor; Free60 documents the format (0x1000 blocks, hash table every 170 blocks, SHA-1 per block). x360-rs extracts and verifies every block (search snippet).
- Useful for us: let the installer accept the raw LIVE package and verify block hashes, instead of requiring a pre-extracted `pack10.000`.

**vgmstream** - https://github.com/vgmstream/vgmstream
- Game audio decoder (`vgmstream-cli` -> WAV). XMA1/XMA2 decoding is delegated to FFmpeg, with fixes for sample counts and encoder delay (secondary source: https://deepwiki.com/vgmstream/vgmstream/4.3-ffmpeg-integration; unverified in README).
- Useful for us: reference decoder to check our Xbox audio decode before IMA ADPCM re-encode (sample count, loop points).

**mtolly/onyx** - https://github.com/mtolly/onyx/blob/master/README.md
- Rhythm-game song toolkit (GPL-3.0) converting Rock Band Xbox 360 CON packs to PS3 and other games. Changelog (https://github.com/mtolly/onyxite-customs/blob/master/haskell/CHANGES.md) records a fix where Xbox 360 XMA audio came out twice as long after conversion (search snippet).
- Useful for us: a long-running cross-platform DLC converter; the XMA-length bug is exactly the class of error a duration check catches.

**sp00nznet/xboxrecomp** - https://github.com/sp00nznet/xboxrecomp
- Original Xbox x86 -> C static recompilation (MIT); D3D8 -> D3D11 layer incl. NV2A register-combiner pixel shaders and NV2A vertex microcode -> HLSL, texture unswizzling, 20+ format conversions; no game data in repo.
- Useful for us: another example of console vertex/pixel microcode -> HLSL translation.

**Star Wars Battlefront II Xbox DLC for PC** - https://www.moddb.com/mods/xbox-dlc-content-for-pc and **PrismaticFlower/swbf-unmunge** - https://github.com/PrismaticFlower/swbf-unmunge
- Per the ModDB page (search snippet; page returned 403): in 2020 SleepKiller made a tool to port the original-Xbox DLC maps to PC, iamashaymin rebuilt `Core.lvl` and mission scripts; a limitation remained around loading two heroes' animations. swbf-unmunge (MIT) has `-platform pc|ps2|xbox` and `extract`/`explode`/`assemble` modes.
- Useful for us: the closest precedent of console-exclusive DLC brought to a PC build of the same engine; shows that scripts/core tables often need hand rebuilding, not only format conversion.

### PS2 / PS3

**open-goal/jak-project (OpenGOAL)** - https://github.com/open-goal/jak-project
- Jak & Daxter PC port (ISC): decompiler for GOAL code, new GOAL compiler, asset extraction from the user's PS2 ISO; no assets distributed. Offline reference tests: each finished file's decompiler output is stored as `*_REF.gc` under `test/decompiler/reference/...` and every build re-decompiles and compiles all of them (https://opengoal.dev/docs/developing/decompiling/getting_started/).
- Useful for us: keep a committed reference output per converted DLC file (metadata/hashes only, since no game data may be committed) and re-run all of them on every change.

**ran-j/PS2Recomp** - https://github.com/ran-j/PS2Recomp and **KIexster/god-of-war-recomp** - https://github.com/KIexster/god-of-war-recomp
- PS2 R5900 -> C++ static recompiler with TOML configs (search result); God of War port ships no game files or generated code. Useful for us: TOML-style per-title config instead of hard-coded tables.

**sp00nznet/ps3recomp** - https://github.com/sp00nznet/ps3recomp
- PS3 static recompilation runtime (MIT); lifter tests and C unit tests in CI on three OSes; RPCS3 used as behavioural reference; "five ports are checked against recorded golden outputs before shared-runtime changes land"; no Sony code, keys or game data.
- Useful for us: golden-output gate before any change to shared converter code.

#### Official status of the DLC on PC and of an LAU remaster - news check 2026-10-30

- Tomb Raider Chronicles, 26 April 2024 (https://www.tombraiderchronicles.com/headlines4873.html): the last official
  word is from the Tomb Raider 25 livestream in September 2021 - Meagan Marie (Director of Community) said progress
  had been made on "the legal challenges faced" for a PC release of *Beneath the Ashes* / *Lara's Shadow*, and the
  studio still had to decide whether it could commit resources; "radio silence since then". The 2021 report:
  https://www.tombraiderchronicles.com/headlines4307.html. Both DLCs are still sold on the Xbox Store.
- No later official statement found (searches 2026-10-30). Older fan view: Microsoft paid for Xbox exclusivity and may
  still hold the rights (Steam discussion https://steamcommunity.com/app/8140/discussions/0/619568708420375163/ -
  speculation, not verified).
- LAU remaster: only rumours - Crystal Dynamics teased a 30th-anniversary project with Aspyr (who did Tomb Raider
  I-III and IV-VI Remastered); the leaker "Society of Raiders" suggested an LAU remaster (April 2026:
  https://www.gamingbible.com/news/tomb-raider-legend-trilogy-remaster-collection-463613-20260412,
  https://twistedvoxel.com/tomb-raider-lau-remaster-in-development/,
  https://www.nme.com/news/gaming-news/tomb-raider-30th-anniversary-collaboration-legend-remaster-rumours-3926200).
  No announcement found up to 2026-10-30 (search results reach to about April 2026, so a very recent announcement
  could be missing). Wikipedia lists Legacy of Atlantis (2027) and Catalyst (2028) as upcoming.

#### Tomb Raider: Underworld on PS3 - research 2026-10-30 (idea: the DLCs for the PS3 version, after PC works)

Reference disc: BLUS30718 "The Tomb Raider Trilogy" (Underworld + Legend HD + Anniversary HD). Web research only,
nothing downloaded. [V] = read on the page / in the source, [S] = search snippet only (tombraiderforums.com and the
RPCS3 wiki blocked fetching), [I] = inference.

- **Bigfiles / DRM**
  - TheIndra55/Yura (GPL-3.0, https://github.com/TheIndra55/Yura): browse/extract cdcEngine bigfiles of TRL/TRA/TRU,
    "all platforms", RAW viewer incl. PS3, CLI `-platform pc|wii|ps3`, `-endianness` since 1.4 [V]; extract only, no
    repack. (Version 1.7.2 is already in `<workspace>\bin`.)
  - sephiroth99/gibbedtr (https://github.com/sephiroth99/gibbedtr, abandoned -> LazyBui/gibbedtr): Unpack / **Pack** /
    DRMEdit / RebuildFileLists [V]; a "Tomb Raider 8 (PS3)" project is mentioned only in a forum snippet [S].
  - Gh0stBlade/cdcEngineTools (https://github.com/Gh0stBlade/cdcEngineTools): CDRM / DRM split, PCD2DDS, WAVE2WAV [V];
    issue #9: PS3 TR8 textures, 32-bit type 0x85 looks Morton-swizzled ARGB, open since 2017 [V].
  - Raq1/cdcEditor (MIT, https://github.com/Raq1/cdcEditor): Blender tools; PS3 TRU: animations / cutscenes [V].
  - Raq's TRLAU Modding Tools (Noesis, v1.2, https://tombraidermodding.com/tool/trulau-mod-tools): `.pcd` textures PC
    and PS3 [V].
  - TheIndra55/TRLAU-menu-hook: PC only [V/I]. TRUBigEd / BigFileTool threads on tombraiderforums.com: old, "reads
    PS3" per snippets [S].
- **Formats**
  - Audio: vgmstream `src/meta/mul.c` says "FSB4 w/ mono MP3 [Tomb Raider 8 (PS3)]" - PS3 `.mul` = FSB4 + MP3 [V]
    (an XMA -> PS3 conversion would encode MP3 into FSB4 [I]).
  - Textures: RSX layout, power-of-two textures Morton-swizzled (psdevwiki multimedia formats) [S]; TRU keeps its own
    `.pcd` sections with PS3 pixel types rather than GTF files [I].
  - Shaders: RSX (NV40 family, Cg `.vpo` / `.fpo`); RPCS3/rsx_program_decompiler, PS3DK `rsx-cg-compiler` [S]; no
    cdcEngine-specific PS3 shader tool found - Xenos -> RSX would be new work [I].
- **RPCS3**
  - Folder dumps (`PS3_GAME/USRDIR`) can be edited in place [S]; `patch.yml` `move_file` / `hide_file` redirect loose
    files, folders or partitions, not files inside a bigfile (PR #13483, merged 2023-03-03) [V].
  - Encrypted Redump / 3k3y ISO with a same-named `.dkey` next to it loads directly (PR #18498, merged 2026-04-10) [V].
  - Underworld (BLES00409 / BLUS30224) and the Trilogy (BLES01195 / BLUS30718) rated "Playable", update 01.01 [S].
  - The PS3 game never had DLC, so its executable may have no DLC mount code: content would go into the base data or
    need a PPU patch [I].
- **Disc dumps**: `.ird` (3k3y format: data1 -> disc key, MD5 of every file) and `.dkey` (disc key, 32 hex chars)
  (psdevwiki IRD) [S]; 13xforever/ps3-disc-dumper (decrypted dumps, maintained) [S]; PS3Dec forks al3xtjames/PS3Dec,
  tonyp7/PS3Dec, Rust Redrrx/ps3dec [S].
- **Earlier attempts**: no PS3 port of "Beneath the Ashes" / "Lara's Shadow" found; only wishlist threads [S].
- **PS2 (bonus idea)**: cdcEditor imports PS2 TRU models / cutscenes [V]; nothing found on restoring cut PS2 levels
  (tcrf.net not searched yet).
- Gaps: repacking PS3 bigfiles (only gibbedtr, PS3 unconfirmed), PS3 TR8 mesh / level tools, RSX shader conversion.

### GameCube / Wii / N64

**encounter/decomp-toolkit (dtk)** - https://github.com/encounter/decomp-toolkit and **objdiff** - https://github.com/encounter/objdiff/releases
- dtk: splits DOLs, relinks, `dtk shasum` verifies SHA-1, `dtk disc verify` checks discs against a built-in Redump database, `dtk dol diff` points to the likely cause of a mismatch; disc/archive extraction and Yaz0/Yay0 handling. objdiff: per-function/section diff with match percentages (release notes: avoid rounding 99.995% to 100%).
- Useful for us: report per-section match percentages vs B138 and never round a near-match to 100%.

**zeldaret/tp** - https://github.com/zeldaret/tp
- Twilight Princess decomp (CC0): user disc in `orig/<ID>`, ISO/RVZ/WIA/etc. accepted, no assets or assembly in repo; objdiff integration; public progress page. GameCube versions reported fully matching.
- Useful for us: clear "put your file here" convention and a public progress page.

**n64decomp/sm64** - https://github.com/n64decomp/sm64 and **sm64-port/sm64-port** - https://github.com/sm64-port/sm64-port
- User supplies `baserom.<version>.z64`; `extract_assets.py` pulls assets; per-version `sm64.<version>.sha1` files and `COMPARE=1` check the built ROM's hash. The PC port is a fork reusing the same extraction.
- Useful for us: publish the expected hash of every supported input and of every output file.

**HarbourMasters/Shipwright (Ship of Harkinian)** - https://github.com/HarbourMasters/Shipwright, **Torch** - https://github.com/HarbourMasters/Torch, **zeldaret/ZAPD** - https://github.com/zeldaret/ZAPD
- SoH: user ROM -> `.o2r` archive; supported dumps listed in `docs/supportedHashes.json` (SHA-1). Torch: generic "Resource Conversion Helper" (`torch otr` from `baserom.z64`, `config.yml`, MIT). ZAPD: XML-driven extraction from a baserom, `-crc` writes a CRC per extracted texture, warning levels Off/Warn/Err (MIT).
- Useful for us: describe DLC files/sections declaratively (YAML/XML) and emit a CRC per converted item.

**N64Recomp** - https://github.com/N64Recomp/N64Recomp and **Zelda64Recomp** - https://github.com/Zelda64Recomp/Zelda64Recomp
- MIPS -> C static recompilation driven by ELF + TOML (stubs, skips, single-instruction patches), MIT; Zelda64Recomp (GPL-3.0) accepts only the US Majora's Mask ROM, loads assets from it directly, no assets in repo, mods via drag-and-drop.
- Useful for us: "single-instruction patches" in a config file is the same idea as our exe patch list - keep patches declarative and documented.

**fgsfdsfgs/perfect_dark** - https://github.com/fgsfdsfgs/perfect_dark
- PC port of the Perfect Dark decomp (MIT); ROM in `data/` named per version; MD5 per supported ROM in `checksums.*.md5`.
- Useful for us: simple per-version checksum files next to the installer.

### General methods and references

- **CRC RevEng** - https://reveng.sourceforge.io/ (README https://reveng.sourceforge.io/readme.htm): recovers CRC parameters from message/CRC pairs, tries 113 catalogued presets first; tip: use pairs whose messages differ only in the last byte or two. Not designed for crossed-endian algorithms.
- **awesome-game-file-format-reversing** - https://github.com/VelocityRa/awesome-game-file-format-reversing/: curated list (010 Editor templates, diaphora, XeNTaX backup).
- **FOSDEM 2021 "Reverse-Engineering of (binary) File-Formats"** - https://archive.fosdem.org/2021/schedule/event/reverse_engineering/attachments/slides/4518/export/events/attachments/reverse_engineering/slides/4518/Reverse_Engineering_of_binary_File_Formats.pdf: modify-save-diff loop (differential analysis).
- **Characterization test** - https://en.wikipedia.org/wiki/Characterization_test; **reproducible builds** - https://reproducible-builds.org/docs/definition/.
- **D3D9 references** - https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3ddecltype, https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3dvertexelement9.
- No published write-up was found on *learning conversion tables from paired cross-platform data*; the closest practice is the byte-identical untile counts and semantic diffs above. Our ID-remap and DEC3N table method appears to be undocumented elsewhere (absence of evidence, not proof).

## Techniques worth adopting

Priority: 1 = do next, 2 = soon, 3 = nice to have.

### (a) Vertex-declaration hash / unknown vertex format

1. (1) **Brute-force the hash over candidate serializations.** Build message/hash pairs from PC files (decl bytes -> 8-byte hash). Serialize each declaration as `D3DVERTEXELEMENT9` arrays (8 bytes: Stream, Offset, Type, Method, Usage, UsageIndex) with and without `D3DDECL_END`, with BLENDWEIGHT elements removed (we know it is ignored), in both byte orders. Test each 32-bit half separately against CRC-32 poly 0x4C11DB7 (cdc's file-name hash per cdcengine.re), then whole-value candidates (CRC-64, FNV-1a 64 - cdc used FNV-1a 64 for names in Shadow per cdcengine.re). If it is a CRC, CRC RevEng can recover the parameters from pairs that differ only in the last bytes.
2. (1) **Minimal pairs from paired data.** Pick PC declarations that differ in exactly one element (e.g. one extra TEXCOORD) and diff their hashes; a CRC shows a linear (XOR) relationship, a multiplicative hash does not.
3. (2) **Read engine code instead of guessing.** Search TheIndra55/cdcEngine (Legend) and rrika/cdcEngineDXHR (DXHR with TR2013 names) for the vertex-declaration creation path; the hash routine may be shared across the engine family (unverified).
4. (2) **Endian swap by element type, not by word.** XenosRecomp found that swapping vertex data as 32-bit words turns 16-bit pairs into YXWZ order; check every SHORT2N/FLOAT16_2 texcoord after our swap. Skate 3 tooling also found reversed blend index/weight byte order on Xbox - check BLENDINDICES.
5. (3) **Cross-check with an Xbox mesh reader.** Load a DLC mesh in Gh0stBlade's TR8 [PC/XENON] Noesis plugin or cdcEditor and compare positions/normals with our converted PC mesh.

### (b) Xenos -> D3D9 shader conversion

1. (1) **Reuse PC shaders wherever a pair exists.** Base-game ShaderLib sections exist on both platforms; map Xbox shader -> PC shader by id/content (as we already do for other IDs) and translate only DLC-unique shaders.
2. (1) **Get ground truth from Xenia.** Run the DLC with `--dump_shaders` to collect each microcode blob (named by hash) and Xenia's translation; disassemble with `xe-gpu-shader-compiler --shader_output_type=ucode`.
3. (2) **Start from XenosRecomp, retarget to SM3.** Its container parser, ALU translation and control-flow scheme are reusable; replace DXC/SM6 output with fxc `vs_3_0`/`ps_3_0`. Watch its listed gaps (integer constants, dynamic indexing, mini vertex fetch) and its constant counts (VS 256 / PS 224 float4). Whether D3D9 SM3 limits fit every DLC shader is unverified.
4. (2) **Verify like xenos-toolchain.** Round-trip the container (parse -> write -> byte-identical), and use a second implementation (XenosRecomp vs our translator, or Xenia's Shader Playground disassembly) as independent oracle.
5. (3) **Visual reference.** Compare in-game screenshots against Xenia GPU trace frames of the same scene.

### (c) Texture and audio conversion checks

1. (1) **Untile with Xenia's address functions** (32x32 tiles, micro-tiling, 4 KB alignment, packed mips) and count byte-identical results for textures present on both platforms, as DDXConv reports success counts.
2. (1) **Stage switches.** Add `--no-untile` / `--no-swap` / `--raw` style switches (DDXConv) so a wrong texture can be bisected to one stage.
3. (2) **Independent texture decoder.** Compare our output with Raq's TRLAU Noesis plugin decoding the Xbox `.tr8x360`/`.raw` input.
4. (1) **Audio duration and sample-count checks.** Decode the Xbox stream with vgmstream/FFmpeg as reference; assert duration and sample count of our IMA ADPCM `.mul` output (Onyx shipped an XMA "twice as long" bug). Use Gibbed's Demux (MUL -> FSB) as a second MUL parser.
5. (3) **Accept the raw LIVE package.** Parse STFS and verify its per-block SHA-1s (Free60 spec), then extract `pack10.000` ourselves.

### (d) Verification and regression testing

1. (1) **Golden-master manifest.** Store per-file and per-section SHA-256 of B138 outputs (hashes only, no data) in the repo; every pipeline run diffs against it (OpenGOAL offline tests, ps3recomp golden gate, sm64 `COMPARE`).
2. (1) **Semantic diff on mismatch.** When bytes differ, decode both sides and report the first differing section/field/relocation (bethesda-multitool `semdiff`, `dtk dol diff`).
3. (2) **Match percentage per section type**, never rounded up to 100% (objdiff); track it in STATUS.md over time.
4. (2) **Input verification.** Publish accepted input hashes (`supportedHashes.json` in Ship of Harkinian, `checksums.*.md5` in perfect_dark, `sm64.<ver>.sha1`) and refuse unknown inputs with a clear message (Unleashed Recompiled).
5. (2) **Reproducibility.** Same inputs on two machines must give the same kit bytes (reproducible-builds definition); pin tool versions.
6. (3) **In-game smoke tests** with TRLAU-menu-hook level select and instance viewer.

### (e) Distribution model and documentation style

1. (1) **Keep BYOD + binary patches.** Already the model of Unleashed Recompiled (installer "generates a patch"), Ship of Harkinian, OpenGOAL, Zelda64Recomp; repos state "no game assets" plainly.
2. (2) **`--check` / install-check mode** for an existing install, plus SHA-256 checksums for release assets (openunderworld also signs update manifests).
3. (2) **One document per format** (`docs/Xbox_360_<FORMAT>_Format.md` style of bethesda-multitool) and a declarative file/section list (ZAPD XML, Torch YAML) instead of tables hidden in code.
4. (3) **Contribute upstream.** Send TRU/Xbox-specific DRM, MUL and vertex-declaration findings to cdcengine.re so the community docs cover Underworld.
5. (3) **License hygiene.** Note third-party code provenance (xboxrecomp NOTICE file, bethesda-multitool listing Xenia BSD-3 and nif.xml); Xenia-derived untile code is BSD-3, XenosRecomp MIT, GPL projects (Yura, ModLoader, TRLAU-menu-hook) are tools, not linked code.

## Sources

https://github.com/andrearicci93/trudlcport
https://cdcengine.re/docs/
https://cdcengine.re/docs/files/drm/
https://cdcengine.re/docs/files/bigfile/
https://cdcengine.re/docs/files/image/
https://cdcengine.re/docs/files/multiplexstream/
https://cdcengine.re/docs/files/tiger/
https://cdcengine.re/docs/tools/gibbed/
https://cdcengine.re/docs/tools/modelex/
https://cdcengine.re/hashdb/
https://github.com/TheIndra55/cdcResearch
https://github.com/TheIndra55/cdcEngine
https://github.com/TheIndra55/Yura
https://github.com/TheIndra55/TRLAU-menu-hook
https://github.com/TombRaiderModding/ModLoader
https://github.com/Gh0stBlade/cdcEngineTools
https://www.tombraiderforums.com/showthread.php?t=208182
https://tombraidermodding.com/tool/trulau-mod-tools
https://github.com/Raq1/cdcEditor
https://github.com/Raq1/TR7AE-Mesh-Exporter
https://github.com/TheSerioliOfNosgoth/ModelEx
https://thelostworlds.net/Software/Soul_Spiral.html
https://github.com/sergen213/openunderworld
https://github.com/rrika/cdcEngineDXHR
https://github.com/rrika/dxhr
https://github.com/vardonir/pyDXHR
https://www.moddb.com/games/deus-ex-3/downloads/gibbeds-deus-ex-hr-tools
https://www.tombraiderforums.com/archive/index.php/t-198260.html
https://www.tombraiderforums.com/showthread.php?t=213025
https://www.tombraiderchronicles.com/headlines4873.html
https://xenia.jp/updates/2021/04/27/leaving-no-pixel-behind-new-render-target-cache-3x3-resolution-scaling.html
https://github.com/xenia-project/xenia/blob/master/docs/gpu.md
https://github.com/xenia-project/xenia/issues/1193
https://github.com/xenia-canary/xenia-canary/pull/577
https://github.com/hedge-dev/XenonRecomp
https://github.com/hedge-dev/XenosRecomp
https://github.com/hedge-dev/UnleashedRecomp
https://github.com/hedge-dev/UnleashedRecomp/releases
https://github.com/xenosworks/xenos-toolchain
https://github.com/slfx77/DDXConv
https://github.com/slfx77/bethesda-multitool
https://reshax.com/topic/846-unswizzling-xbox-360-textures-condemned-2-lithtech-jupiter-ex/
https://github.com/galaxygas/Eyefinder/pull/20
https://github.com/SunJaycy/sk83.GLB2ARENA
https://github.com/hetelek/Velocity
https://free60.org/System-Software/Formats/STFS/
https://github.com/D221/x360-rs
https://github.com/vgmstream/vgmstream
https://deepwiki.com/vgmstream/vgmstream/4.3-ffmpeg-integration
https://github.com/mtolly/onyx/blob/master/README.md
https://github.com/mtolly/onyxite-customs/blob/master/haskell/CHANGES.md
https://github.com/sp00nznet/xboxrecomp
https://www.moddb.com/mods/xbox-dlc-content-for-pc
https://github.com/PrismaticFlower/swbf-unmunge
https://github.com/open-goal/jak-project
https://opengoal.dev/docs/developing/decompiling/getting_started/
https://github.com/ran-j/PS2Recomp
https://github.com/KIexster/god-of-war-recomp
https://github.com/sp00nznet/ps3recomp
https://github.com/encounter/decomp-toolkit
https://github.com/encounter/objdiff/releases
https://github.com/zeldaret/tp
https://github.com/n64decomp/sm64
https://github.com/sm64-port/sm64-port
https://github.com/HarbourMasters/Shipwright
https://github.com/HarbourMasters/Torch
https://github.com/zeldaret/ZAPD
https://github.com/N64Recomp/N64Recomp
https://github.com/Zelda64Recomp/Zelda64Recomp
https://github.com/fgsfdsfgs/perfect_dark
https://reveng.sourceforge.io/
https://reveng.sourceforge.io/readme.htm
https://github.com/VelocityRa/awesome-game-file-format-reversing/
https://archive.fosdem.org/2021/schedule/event/reverse_engineering/attachments/slides/4518/export/events/attachments/reverse_engineering/slides/4518/Reverse_Engineering_of_binary_File_Formats.pdf
https://en.wikipedia.org/wiki/Characterization_test
https://reproducible-builds.org/docs/definition/
https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3ddecltype
https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3dvertexelement9
https://www.tombraiderforums.com/showthread.php?t=178907
https://www.tombraiderforums.com/showthread.php?t=204503
https://www.tombraiderforums.com/showthread.php?t=225774
