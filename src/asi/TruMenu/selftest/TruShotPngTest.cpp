// TruShotPngTest.cpp - offline check of TruShotPng.h (TruMenu 0.10.5 screenshots): builds back-buffer-like test
// images in every supported pixel format (with row padding = a D3D pitch), converts and encodes them exactly as the shot
// worker does, and writes into <out dir>: test_<n>.png, test_<n>.src (the raw source pixels) and manifest.txt
// ("n w h kind pitch encode_ms png_bytes"). tools/png_selftest_check.py then decodes every PNG on its own (CRC, zlib,
// filters) and compares it with its own conversion of the .src pixels.
// Not part of TruMenu.asi. Build (x86, the same compiler as Build-TruAsi.ps1):
//   cl /nologo /O2 /MT /W4 /EHsc TruShotPngTest.cpp /Fe<out>\TruShotPngTest.exe
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../TruShotPng.h"

static unsigned long g_seed = 12345;
static unsigned Rand() {                         // fixed sequence: the same files every run
    g_seed = g_seed * 1103515245UL + 12345UL;
    return static_cast<unsigned>((g_seed >> 16) & 0x7fff);
}

// one source pixel (r, g, b 0..255) in <kind> at <p>
static void PutPixel(unsigned char *p, trushot::PixelKind kind, unsigned r, unsigned g, unsigned b, unsigned a) {
    if (kind == trushot::kPixXrgb8888) {
        p[0] = static_cast<unsigned char>(b); p[1] = static_cast<unsigned char>(g);
        p[2] = static_cast<unsigned char>(r); p[3] = static_cast<unsigned char>(a);
    } else if (kind == trushot::kPixArgb2101010) {
        unsigned long v = ((static_cast<unsigned long>(a) & 3) << 30) | ((static_cast<unsigned long>(r) * 4 + (r >> 6)) << 20) |
                          ((static_cast<unsigned long>(g) * 4 + (g >> 6)) << 10) | (static_cast<unsigned long>(b) * 4 + (b >> 6));
        p[0] = static_cast<unsigned char>(v); p[1] = static_cast<unsigned char>(v >> 8);
        p[2] = static_cast<unsigned char>(v >> 16); p[3] = static_cast<unsigned char>(v >> 24);
    } else if (kind == trushot::kPixRgb565) {
        unsigned v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
        p[0] = static_cast<unsigned char>(v); p[1] = static_cast<unsigned char>(v >> 8);
    } else {
        unsigned v = ((a & 1) << 15) | ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3);
        p[0] = static_cast<unsigned char>(v); p[1] = static_cast<unsigned char>(v >> 8);
    }
}

// pattern: gradient, a noise band, flat areas, a repeating stripe pattern, a single bright line
static void Fill(unsigned char *src, size_t pitch, int w, int h, trushot::PixelKind kind, int bpp, int style) {
    memset(src, 0xcd, pitch * static_cast<size_t>(h));   // padding bytes must never reach the PNG
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            unsigned r, g, b;
            if (style == 1) { r = g = b = 0; }                                   // all black (long runs)
            else if (y < h / 4) { r = (x * 255) / (w > 1 ? w - 1 : 1); g = (y * 255) / (h > 1 ? h - 1 : 1); b = 128; }
            else if (y < h / 2) { r = Rand() & 255; g = Rand() & 255; b = Rand() & 255; }   // noise
            else if (y < 3 * h / 4) { r = 30; g = 60; b = (x / 16) % 2 ? 200 : 20; }      // stripes
            else { r = 240; g = 240; b = 240; }                                    // flat
            if (style == 0 && x == w / 2) { r = 255; g = 0; b = 0; }
            PutPixel(src + pitch * static_cast<size_t>(y) + static_cast<size_t>(x) * static_cast<size_t>(bpp), kind, r, g, b,
                     static_cast<unsigned>(x + y) & 255);
        }
    }
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: TruShotPngTest <out dir>\n"); return 2; }
    struct Case { int w, h; unsigned d3dFormat; int extraPitch; int style; } cases[] = {
        {640, 360, 22, 64, 0},     // X8R8G8B8 with padding
        {1920, 1080, 21, 0, 0},    // A8R8G8B8 full HD (timing)
        {1280, 720, 22, 0, 1},     // all black
        {33, 17, 23, 6, 0},        // R5G6B5, odd size
        {31, 9, 25, 2, 0},         // A1R5G5B5
        {7, 5, 35, 4, 0},          // A2R10G10B10
        {1, 1, 22, 0, 0},          // smallest
        {300, 2, 24, 0, 0},        // X1R5G5B5, two rows
    };
    char path[MAX_PATH];
    _snprintf_s(path, sizeof(path), _TRUNCATE, "%s\\manifest.txt", argv[1]);
    FILE *manifest = fopen(path, "w");
    if (!manifest) { fprintf(stderr, "cannot write %s\n", path); return 1; }
    trushot::Crc32(0, nullptr, 0);               // table once, as TruMenu does at start
    LARGE_INTEGER freq;
    QueryPerformanceFrequency(&freq);
    int failed = 0;
    for (int n = 0; n < static_cast<int>(sizeof(cases) / sizeof(cases[0])); ++n) {
        const Case &c = cases[n];
        int bpp = 0;
        trushot::PixelKind kind = trushot::KindOfD3dFormat(c.d3dFormat, &bpp);
        size_t pitch = static_cast<size_t>(c.w) * static_cast<size_t>(bpp) + static_cast<size_t>(c.extraPitch);
        unsigned char *src = static_cast<unsigned char *>(malloc(pitch * static_cast<size_t>(c.h)));
        unsigned char *rgb = static_cast<unsigned char *>(malloc(static_cast<size_t>(c.w) * 3 * static_cast<size_t>(c.h)));
        Fill(src, pitch, c.w, c.h, kind, bpp, c.style);
        LARGE_INTEGER t0, t1;
        QueryPerformanceCounter(&t0);
        trushot::ToRgb(src, pitch, c.w, c.h, kind, rgb);
        trushot::Buf png;
        trushot::BufInit(png);
        bool ok = trushot::EncodePng(rgb, c.w, c.h, png);
        QueryPerformanceCounter(&t1);
        double ms = 1000.0 * static_cast<double>(t1.QuadPart - t0.QuadPart) / static_cast<double>(freq.QuadPart);
        if (!ok) { ++failed; fprintf(stderr, "case %d: encode failed\n", n); }
        _snprintf_s(path, sizeof(path), _TRUNCATE, "%s\\test_%d.png", argv[1], n);
        FILE *f = fopen(path, "wb");
        if (f) { fwrite(png.p, 1, png.n, f); fclose(f); } else ++failed;
        _snprintf_s(path, sizeof(path), _TRUNCATE, "%s\\test_%d.src", argv[1], n);
        f = fopen(path, "wb");
        if (f) { fwrite(src, 1, pitch * static_cast<size_t>(c.h), f); fclose(f); } else ++failed;
        fprintf(manifest, "%d %d %d %d %u %.1f %u\n", n, c.w, c.h, static_cast<int>(kind), static_cast<unsigned>(pitch), ms,
                static_cast<unsigned>(png.n));
        printf("case %d: %dx%d format %u kind %d pitch %u -> %u bytes PNG in %.1f ms (raw RGB %u bytes)\n", n, c.w, c.h,
               c.d3dFormat, static_cast<int>(kind), static_cast<unsigned>(pitch), static_cast<unsigned>(png.n), ms,
               static_cast<unsigned>(c.w * 3 * c.h));
        trushot::BufFree(png);
        free(src);
        free(rgb);
    }
    fclose(manifest);
    printf("%s\n", failed ? "FAILED" : "done");
    return failed ? 1 : 0;
}
