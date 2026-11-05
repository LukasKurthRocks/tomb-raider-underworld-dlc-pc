// TruShotPng.h - small PNG writer for TruMenu 0.10.5 screenshots (own code, no third-party source).
// 8-bit RGB (colour type 2), one IDAT chunk; per row the PNG filter (None / Sub / Up / Average / Paeth) with the
// smallest sum of absolute signed bytes (the usual heuristic); zlib stream = one deflate block with the fixed Huffman
// codes of RFC 1951 3.2.6 and LZ77 matches from a hash chain over the 32 KB window; CRC-32 (PNG) and Adler-32 (zlib).
// Also the back-buffer pixel conversion (X8R8G8B8 / A8R8G8B8, R5G6B5, X1R5G5B5 / A1R5G5B5, A2R10G10B10 -> RGB).
// Used on TruMenu's shot worker thread only; checked offline by selftest/TruShotPngTest.cpp + tools/png_selftest_check.py.
#pragma once
#include <stdlib.h>
#include <string.h>

namespace trushot {

struct Buf {
    unsigned char *p;
    size_t n, cap;
    bool ok;
};

inline void BufInit(Buf &b) { b.p = nullptr; b.n = b.cap = 0; b.ok = true; }
inline void BufFree(Buf &b) { free(b.p); b.p = nullptr; b.n = b.cap = 0; }
inline void BufPut(Buf &b, const void *data, size_t n) {
    if (!b.ok) return;
    if (b.n + n > b.cap) {
        size_t c = b.cap ? b.cap : 65536;
        while (c < b.n + n) c *= 2;
        unsigned char *q = static_cast<unsigned char *>(realloc(b.p, c));
        if (!q) { b.ok = false; return; }
        b.p = q;
        b.cap = c;
    }
    memcpy(b.p + b.n, data, n);
    b.n += n;
}
inline void BufByte(Buf &b, unsigned v) {
    if (b.ok && b.n < b.cap) { b.p[b.n++] = static_cast<unsigned char>(v); return; }
    unsigned char c = static_cast<unsigned char>(v);
    BufPut(b, &c, 1);
}
inline void BufBe32(Buf &b, unsigned long v) {
    BufByte(b, (v >> 24) & 0xff);
    BufByte(b, (v >> 16) & 0xff);
    BufByte(b, (v >> 8) & 0xff);
    BufByte(b, v & 0xff);
}

inline unsigned long Crc32(unsigned long crc, const unsigned char *p, size_t n) {
    static unsigned long table[256];
    static bool ready = false;
    if (!ready) {                                // same table on every thread; a race writes the same values
        for (unsigned long i = 0; i < 256; ++i) {
            unsigned long c = i;
            for (int k = 0; k < 8; ++k) c = (c & 1) ? 0xedb88320UL ^ (c >> 1) : c >> 1;
            table[i] = c;
        }
        ready = true;
    }
    crc = ~crc & 0xffffffffUL;
    for (size_t i = 0; i < n; ++i) crc = table[(crc ^ p[i]) & 0xff] ^ (crc >> 8);
    return ~crc & 0xffffffffUL;
}

inline unsigned long Adler32(const unsigned char *p, size_t n) {
    unsigned long a = 1, b = 0;
    while (n) {
        size_t k = n < 5552 ? n : 5552;          // largest block without a 32-bit overflow before the modulo
        n -= k;
        while (k--) { a += *p++; b += a; }
        a %= 65521UL;
        b %= 65521UL;
    }
    return (b << 16) | a;
}

// ---- deflate (fixed Huffman codes, RFC 1951 3.2.5 / 3.2.6) ----
struct Bits {
    Buf *out;
    unsigned long acc;
    int count;
};
inline void BitsPut(Bits &w, unsigned long value, int len) {   // LSB first
    w.acc |= value << w.count;
    w.count += len;
    while (w.count >= 8) {
        BufByte(*w.out, w.acc & 0xff);
        w.acc >>= 8;
        w.count -= 8;
    }
}
inline unsigned long Reverse(unsigned long code, int len) {     // Huffman codes are packed MSB first
    unsigned long r = 0;
    for (int i = 0; i < len; ++i) { r = (r << 1) | (code & 1); code >>= 1; }
    return r;
}
inline void PutSymbol(Bits &w, unsigned s) {                     // literal / length alphabet 0..287
    if (s <= 143) BitsPut(w, Reverse(0x30 + s, 8), 8);
    else if (s <= 255) BitsPut(w, Reverse(0x190 + (s - 144), 9), 9);
    else if (s <= 279) BitsPut(w, Reverse(s - 256, 7), 7);
    else BitsPut(w, Reverse(0xc0 + (s - 280), 8), 8);
}
const unsigned short kLenBase[29] = {3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99,
                                     115, 131, 163, 195, 227, 258};
const unsigned char kLenExtra[29] = {0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0};
const unsigned short kDistBase[30] = {1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025,
                                      1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577};
const unsigned char kDistExtra[30] = {0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12,
                                      12, 13, 13};
inline void PutMatch(Bits &w, unsigned len, unsigned dist) {
    int i = 28;
    while (kLenBase[i] > len) --i;               // the largest base <= len (258 = symbol 285, no extra bits)
    PutSymbol(w, 257 + i);
    if (kLenExtra[i]) BitsPut(w, len - kLenBase[i], kLenExtra[i]);
    int d = 29;
    while (kDistBase[d] > dist) --d;
    BitsPut(w, Reverse(static_cast<unsigned long>(d), 5), 5);
    if (kDistExtra[d]) BitsPut(w, dist - kDistBase[d], kDistExtra[d]);
}

const int kHashBits = 15, kWindow = 32768, kMaxChain = 24, kMaxMatch = 258;
inline unsigned Hash3(const unsigned char *p) {
    unsigned long v = (static_cast<unsigned long>(p[0]) << 16) | (static_cast<unsigned long>(p[1]) << 8) | p[2];
    return static_cast<unsigned>(((v * 2654435761UL) & 0xffffffffUL) >> (32 - kHashBits));
}

// zlib stream (RFC 1950: 0x78 0x01, one final fixed-Huffman block, Adler-32) of <data>; false when out of memory
inline bool ZlibCompress(const unsigned char *data, size_t n, Buf &out) {
    int *head = static_cast<int *>(malloc(sizeof(int) * (1u << kHashBits)));
    int *prev = static_cast<int *>(malloc(sizeof(int) * kWindow));
    if (!head || !prev) { free(head); free(prev); return false; }
    for (unsigned i = 0; i < (1u << kHashBits); ++i) head[i] = -1;
    BufByte(out, 0x78);
    BufByte(out, 0x01);
    Bits w = {&out, 0, 0};
    BitsPut(w, 1, 1);                            // BFINAL
    BitsPut(w, 1, 2);                            // BTYPE 01 = fixed Huffman codes
    size_t i = 0;
    while (i < n) {
        size_t best = 0, bestDist = 0;
        if (i + 3 <= n) {
            size_t maxLen = n - i < static_cast<size_t>(kMaxMatch) ? n - i : static_cast<size_t>(kMaxMatch);
            int p = head[Hash3(data + i)];
            int chain = kMaxChain;
            while (p >= 0 && chain-- > 0) {
                size_t dist = i - static_cast<size_t>(p);
                if (dist > static_cast<size_t>(kWindow)) break;
                if (data[p + best] == data[i + best]) {   // best < maxLen here, so both reads are inside
                    size_t len = 0;
                    while (len < maxLen && data[p + len] == data[i + len]) ++len;
                    if (len > best) {
                        best = len;
                        bestDist = dist;
                        if (len == maxLen) break;
                    }
                }
                int q = prev[p & (kWindow - 1)];
                if (q >= p) break;               // the slot was reused by a newer position: chain ends
                p = q;
            }
        }
        size_t step = best >= 3 ? best : 1;
        if (best >= 3) PutMatch(w, static_cast<unsigned>(best), static_cast<unsigned>(bestDist));
        else PutSymbol(w, data[i]);
        for (size_t k = 0; k < step; ++k, ++i) { // every position passed goes into the chains
            if (i + 3 > n) continue;
            unsigned h = Hash3(data + i);
            prev[i & (kWindow - 1)] = head[h];
            head[h] = static_cast<int>(i);
        }
    }
    PutSymbol(w, 256);                           // end of block
    if (w.count) BitsPut(w, 0, 8 - w.count);     // pad to a byte
    BufBe32(out, Adler32(data, n));
    free(head);
    free(prev);
    return out.ok;
}

// ---- PNG ----
inline int Paeth(int a, int b, int c) {
    int p = a + b - c, pa = abs(p - a), pb = abs(p - b), pc = abs(p - c);
    if (pa <= pb && pa <= pc) return a;
    return pb <= pc ? b : c;
}

inline void PngChunk(Buf &out, const char *type, const unsigned char *data, size_t n) {
    BufBe32(out, static_cast<unsigned long>(n));
    size_t start = out.n;
    BufPut(out, type, 4);
    if (n) BufPut(out, data, n);
    if (!out.ok) return;
    BufBe32(out, Crc32(0, out.p + start, 4 + n));
}

// <rgb> = w * h * 3 bytes, rows top to bottom; the whole file into <out> (caller frees with BufFree)
inline bool EncodePng(const unsigned char *rgb, int w, int h, Buf &out) {
    if (w <= 0 || h <= 0) return false;
    size_t row = static_cast<size_t>(w) * 3, stride = row + 1;
    unsigned char *raw = static_cast<unsigned char *>(malloc(stride * static_cast<size_t>(h)));
    unsigned char *trial = static_cast<unsigned char *>(malloc(row * 5));
    if (!raw || !trial) { free(raw); free(trial); return false; }
    for (int y = 0; y < h; ++y) {
        const unsigned char *cur = rgb + row * static_cast<size_t>(y);
        const unsigned char *up = y ? cur - row : nullptr;
        unsigned long bestSum = 0xffffffffUL;
        int bestType = 0;
        for (int t = 0; t < 5; ++t) {
            unsigned char *f = trial + row * static_cast<size_t>(t);
            unsigned long sum = 0;
            for (size_t x = 0; x < row; ++x) {
                int a = x >= 3 ? cur[x - 3] : 0, b = up ? up[x] : 0, c = (x >= 3 && up) ? up[x - 3] : 0;
                int pred = t == 0 ? 0 : t == 1 ? a : t == 2 ? b : t == 3 ? (a + b) / 2 : Paeth(a, b, c);
                unsigned char v = static_cast<unsigned char>(cur[x] - pred);
                f[x] = v;
                sum += v < 128 ? v : 256 - v;
            }
            if (sum < bestSum) { bestSum = sum; bestType = t; }
        }
        unsigned char *dst = raw + stride * static_cast<size_t>(y);
        dst[0] = static_cast<unsigned char>(bestType);
        memcpy(dst + 1, trial + row * static_cast<size_t>(bestType), row);
    }
    free(trial);
    Buf z;
    BufInit(z);
    bool ok = ZlibCompress(raw, stride * static_cast<size_t>(h), z);
    free(raw);
    if (!ok) { BufFree(z); return false; }
    static const unsigned char sig[8] = {0x89, 'P', 'N', 'G', 0x0d, 0x0a, 0x1a, 0x0a};
    BufPut(out, sig, 8);
    unsigned char ihdr[13];
    unsigned long uw = static_cast<unsigned long>(w), uh = static_cast<unsigned long>(h);
    ihdr[0] = static_cast<unsigned char>(uw >> 24); ihdr[1] = static_cast<unsigned char>(uw >> 16);
    ihdr[2] = static_cast<unsigned char>(uw >> 8);  ihdr[3] = static_cast<unsigned char>(uw);
    ihdr[4] = static_cast<unsigned char>(uh >> 24); ihdr[5] = static_cast<unsigned char>(uh >> 16);
    ihdr[6] = static_cast<unsigned char>(uh >> 8);  ihdr[7] = static_cast<unsigned char>(uh);
    ihdr[8] = 8;                                 // bit depth
    ihdr[9] = 2;                                 // colour type RGB
    ihdr[10] = ihdr[11] = ihdr[12] = 0;          // deflate, adaptive filtering, no interlace
    PngChunk(out, "IHDR", ihdr, 13);
    PngChunk(out, "IDAT", z.p, z.n);
    PngChunk(out, "IEND", nullptr, 0);
    BufFree(z);
    return out.ok;
}

// ---- back-buffer pixels -> RGB ----
enum PixelKind { kPixNone = 0, kPixXrgb8888 = 1, kPixRgb565 = 2, kPixXrgb1555 = 3, kPixArgb2101010 = 4 };
// D3DFORMAT values (d3d9types.h): 21 A8R8G8B8, 22 X8R8G8B8, 23 R5G6B5, 24 X1R5G5B5, 25 A1R5G5B5, 35 A2R10G10B10
inline PixelKind KindOfD3dFormat(unsigned format, int *bytesPerPixel) {
    switch (format) {
    case 21: case 22: *bytesPerPixel = 4; return kPixXrgb8888;
    case 23: *bytesPerPixel = 2; return kPixRgb565;
    case 24: case 25: *bytesPerPixel = 2; return kPixXrgb1555;
    case 35: *bytesPerPixel = 4; return kPixArgb2101010;
    default: *bytesPerPixel = 0; return kPixNone;
    }
}
// <src> rows of <pitch> bytes (little-endian pixels) -> <rgb> (w * h * 3)
inline void ToRgb(const unsigned char *src, size_t pitch, int w, int h, PixelKind kind, unsigned char *rgb) {
    for (int y = 0; y < h; ++y) {
        const unsigned char *s = src + pitch * static_cast<size_t>(y);
        unsigned char *d = rgb + static_cast<size_t>(w) * 3 * static_cast<size_t>(y);
        for (int x = 0; x < w; ++x, d += 3) {
            if (kind == kPixXrgb8888) {          // memory order B G R X
                d[0] = s[4 * x + 2]; d[1] = s[4 * x + 1]; d[2] = s[4 * x];
            } else if (kind == kPixArgb2101010) {
                unsigned long v = s[4 * x] | (s[4 * x + 1] << 8) | (static_cast<unsigned long>(s[4 * x + 2]) << 16) |
                                  (static_cast<unsigned long>(s[4 * x + 3]) << 24);
                d[0] = static_cast<unsigned char>((v >> 22) & 0xff);
                d[1] = static_cast<unsigned char>((v >> 12) & 0xff);
                d[2] = static_cast<unsigned char>((v >> 2) & 0xff);
            } else {
                unsigned v = s[2 * x] | (s[2 * x + 1] << 8);
                unsigned r, g, b;
                if (kind == kPixRgb565) {
                    r = (v >> 11) & 31; g = (v >> 5) & 63; b = v & 31;
                    d[1] = static_cast<unsigned char>((g << 2) | (g >> 4));
                } else {
                    r = (v >> 10) & 31; g = (v >> 5) & 31; b = v & 31;
                    d[1] = static_cast<unsigned char>((g << 3) | (g >> 2));
                }
                d[0] = static_cast<unsigned char>((r << 3) | (r >> 2));
                d[2] = static_cast<unsigned char>((b << 3) | (b >> 2));
            }
        }
    }
}

}  // namespace trushot
