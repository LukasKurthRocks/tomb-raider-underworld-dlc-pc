# Dear ImGui (third-party, MIT)

Unmodified copy of the files TruMenu.asi needs from **Dear ImGui v1.91.9** by Omar Cornut and contributors, license in
[LICENSE.txt](LICENSE.txt) (MIT).

| | |
|---|---|
| Source | <https://github.com/ocornut/imgui/archive/refs/tags/v1.91.9.tar.gz> (downloaded 2026-10-31) |
| Archive sha256 | `3872a5f90df78fced023c1945f4466b654fd74573370b77b17742149763a7a7c` |
| Tag / commit | `v1.91.9` = `97428e8ac99e339ce05eee531cf55b77b29ea709` |
| Files | `imgui*.cpp/.h`, `imconfig.h`, `imstb_*.h`, `LICENSE.txt`, `backends/imgui_impl_dx9.*`, `backends/imgui_impl_win32.*` |

Build options are passed as defines by `scripts\windows\Build-TruAsi.ps1` (`imconfig.h` stays as shipped):
`IMGUI_IMPL_WIN32_DISABLE_GAMEPAD` (TruMenu feeds the pad itself), `IMGUI_DISABLE_WIN32_DEFAULT_IME_FUNCTIONS`,
`IMGUI_DISABLE_DEFAULT_SHELL_FUNCTIONS` (no imm32 / shell32 imports), `IMGUI_DISABLE_DEMO_WINDOWS`.
To update: replace the files from a newer tag of the same repository and update this table.
