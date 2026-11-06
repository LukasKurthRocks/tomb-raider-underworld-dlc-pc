// TruMercLang.asi - "the mercenaries speak another language" (fun option) for the PC tru.exe (Steam, image base
// 0x400000). Default OFF (TruMercLang.ini [MercLang] Enabled=0).
//
// The merc barks (vo\enemy\merc\b_mNN_<category>_<g|s>_NN.mul, 669 names) are in bigfile.000 in every language: one
// record per language with the same path (same hash) and its own spec word (ffffffe1 EN, ffffe002 FR, ffffe004 DE,
// ffffe008 IT, ffffe010 ES; ffffffff language-neutral: voice m11 and all gat / some cbr / evg barks - 179 names).
// tru.exe picks the record per file in ArchiveFileSystem::FindEntry (0x4726e0, thiscall, one stack argument = path,
// ret 4): binary search of the path hash in this+0x18 (count this+0x1c), then the first record (this+0x14, 16 bytes,
// spec at +8) with (spec & mask) == mask, where mask = this+8 = 1 << language (SetLanguage 0x49a900 ->
// 0x54f2e0(1 << lang) -> FS->SetSpecialisationMask, vtbl +0x10 = 0x472990). Barks are looked up again on every play
// (stream object 0x58aa40 "%s%s.mul" -> FileExists / OpenFile -> FindEntry). docs\Befund-Tonspuren-Soeldner-0611.md B.
//
// The plugin detours FindEntry. For paths that contain PathFilter (default \vo\enemy\merc\) it runs the normal search
// first; if that finds a record, it searches again with a COPY of the first 0x20 bytes of the file-system object whose
// mask field (+8) holds 1 << chosen language and returns that record when there is one (else the normal one). The real
// object is never written; FindEntry reads only +0x08, +0x14, +0x18, +0x1c of `this` (whole function checked by
// hash) and the record it returns points into the real record table, so RequestRead / FileExists / GetFileSize /
// OpenFile (the four callers) keep working on the real object. Language-neutral barks come back unchanged.
//
// Every address the plugin patches or relies on is byte-checked first; if one check fails nothing is hooked and the
// log says which. Logging (TruMercLang.log next to the .asi): a start line, the check result, one line per distinct
// redirected path the first time (written by a helper thread, never from the hook) and a burst line with the counts
// every 30 s while barks play.
//
// Not handled: files served from mods\ by ModLoader.asi (HookFileSystem sits above the game's file system and answers
// a mods\ file itself, so FindEntry never sees it). The plugin counts such files under PathFilter at start and logs
// which file-system object the game uses, but does not work around it.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <share.h>

namespace {

const char kVersion[] = "TruMercLang 0.1 (merc barks in another language)";
const DWORD kImageBase = 0x00400000;
const DWORD kFindEntry = 0x004726e0;        // ArchiveFileSystem::FindEntry
const DWORD kFindEntryEnd = 0x00472872;     // end of its last ret 4
const DWORD kFindEntryFnv = 0x39269461;     // FNV-1a 32 of [kFindEntry, kFindEntryEnd) in the 2008 Steam build
const int kPrologue = 7;                    // sub esp,0Ch (3) + mov eax,[esp+10h] (4): position independent
const DWORD kGlobalFs = 0x009ce278;         // GetFS 0x472b50 = mov eax,[9CE278h]
const DWORD kVtblArchive = 0x00843fcc, kVtblMulti = 0x008440ec;
const DWORD kSpecNeutral = 0xffffffff;

struct Check { DWORD at; const char *hex; const char *what; };
const Check kChecks[] = {
    {0x004726e0, "83ec0c 8b442410 53 55 56 57 8bd9 50 895c241c e879ffffff", "FindEntry prologue + call hash 0x472670"},
    {0x004726f7, "8b731c", "FindEntry reads this+0x1c (hash count)"},
    {0x00472701, "8b5318", "FindEntry reads this+0x18 (hash table)"},
    {0x004727b4, "8b4714", "FindEntry reads this+0x14 (records)"},
    {0x004727c6, "8b4708 23d8 3bd8", "FindEntry mask read 1: (spec & [this+8]) == [this+8]"},
    {0x004727f0, "8b5708", "FindEntry mask read 2 (backwards over equal hashes)"},
    {0x00472830, "8b7f08", "FindEntry mask read 3 (forwards over equal hashes)"},
    {0x00472990, "8b442404 894108 c20400", "SetSpecialisationMask writes this+8"},
    {0x005247c0, "8b4108 c3", "GetSpecialisationMask reads this+8"},
    {0x00843fcc, "90284700 20304700 20294700 40294700 90294700 c0475200",
     "ArchiveFileSystem vtable: RequestRead, OpenFile, FileExists, GetFileSize, Set/GetSpecialisationMask"},
    {0x0047289e, "e83dfeffff", "RequestRead calls FindEntry"},
    {0x00472925, "e8b6fdffff", "FileExists calls FindEntry"},
    {0x00472945, "e896fdffff", "GetFileSize calls FindEntry"},
    {0x0047302c, "e8aff6ffff", "OpenFile calls FindEntry"},
    {0x0049a91f, "b801000000 d3e0 50 e8b4490b00", "SetLanguage: mask = 1 << language"},
    {0x0047929d, "c705e4008900 01000000", "installer language French = 1"},
    {0x004792c0, "c705e4008900 02000000", "installer language German = 2"},
    {0x004792e3, "c705e4008900 03000000", "installer language Italian = 3"},
    {0x00479306, "c705e4008900 04000000", "installer language Spanish = 4"},
    {0x0084487c, "5370616e69736800", "string \"Spanish\""},
    {0x00472b50, "a178e29c00 c3", "GetFS = [0x9ce278]"},
};

// options (TruMercLang.ini, section [MercLang]); g_filter is fixed before the hook goes in, never changed after
int g_enabled = 0;
int g_live = 0;
int g_logLevel = 1;                         // 0 errors, 1 info, 2 + unchanged / neutral paths, 3 + check details
char g_filter[64];
char g_iniPath[MAX_PATH], g_logPath[MAX_PATH], g_gameDir[MAX_PATH];
CRITICAL_SECTION g_logLock;

volatile LONG g_mask = 0;                   // 0 = pass through, else 1 << chosen language (written by the helper thread)
typedef const BYTE *(__fastcall *FindEntryFn)(const BYTE *fs, void *edx, const char *path);   // thiscall, ret 4
FindEntryFn g_origFindEntry = nullptr;      // trampoline: relocated prologue + jmp 0x4726e7

// per-call counters (hook: InterlockedIncrement; helper thread: InterlockedExchange to 0 every 30 s)
volatile LONG g_nRedirect = 0, g_nSame = 0, g_nFallback = 0, g_nAsIs = 0;

// distinct (path, chosen mask) pairs; filled by the hook under g_seenLock, logged later by the helper thread
enum Kind : BYTE { kRedirect = 0, kSame = 1, kFallback = 2 };
struct Seen { DWORD key; DWORD mask; DWORD from; DWORD to; BYTE kind; BYTE logged; char name[70]; };
const int kSeenSize = 2048;                 // power of two; at most 3/4 used
Seen g_seen[kSeenSize];
int g_seenCount = 0;
volatile LONG g_seenFull = 0;
CRITICAL_SECTION g_seenLock;

void Log(int level, const char *fmt, ...) {
    if (level > g_logLevel || !g_logPath[0]) return;
    char line[640];
    SYSTEMTIME t;
    GetLocalTime(&t);
    int n = _snprintf_s(line, sizeof(line), _TRUNCATE, "%02d:%02d:%02d.%03d ", t.wHour, t.wMinute, t.wSecond,
                        t.wMilliseconds);
    va_list ap;
    va_start(ap, fmt);
    if (n > 0) _vsnprintf_s(line + n, sizeof(line) - n, _TRUNCATE, fmt, ap);
    va_end(ap);
    EnterCriticalSection(&g_logLock);
    // _fsopen with _SH_DENYNO (not fopen_s, which opens exclusively): a reader of the log never blocks a line
    FILE *f = _fsopen(g_logPath, "a", _SH_DENYNO);
    if (f) {
        fputs(line, f);
        fputs("\n", f);
        fclose(f);
    }
    LeaveCriticalSection(&g_logLock);
}

char Lower(char c) { return (c >= 'A' && c <= 'Z') ? static_cast<char>(c + 32) : c; }

// position of g_filter in s (case-insensitive), nullptr if absent
const char *FindFilter(const char *s) {
    for (; *s; ++s) {
        int i = 0;
        while (g_filter[i] && Lower(s[i]) == g_filter[i]) ++i;
        if (!g_filter[i]) return s;
    }
    return nullptr;
}

int HexValue(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

// compare the bytes at `address` with a hex string (spaces ignored); *count = bytes compared
bool HexAt(DWORD address, const char *hex, int *count) {
    BYTE want[64];
    int n = 0;
    for (const char *p = hex; *p && n < 64;) {
        if (*p == ' ') { ++p; continue; }
        int hi = HexValue(p[0]), lo = p[1] ? HexValue(p[1]) : -1;
        if (hi < 0 || lo < 0) return false;
        want[n++] = static_cast<BYTE>(hi * 16 + lo);
        p += 2;
    }
    *count = n;
    __try {
        return memcmp(reinterpret_cast<const void *>(address), want, static_cast<size_t>(n)) == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool Fnv(DWORD from, DWORD to, DWORD *hash) {
    DWORD h = 0x811c9dc5;
    __try {
        for (DWORD a = from; a < to; ++a) h = (h ^ *reinterpret_cast<const BYTE *>(a)) * 0x01000193;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    *hash = h;
    return true;
}

const char *SpecName(DWORD spec) {
    switch (spec) {
    case 0xffffffe1: return "en";
    case 0xffffe002: return "fr";
    case 0xffffe004: return "de";
    case 0xffffe008: return "it";
    case 0xffffe010: return "es";
    case kSpecNeutral: return "all";
    default: return "?";
    }
}

const char *MaskName(DWORD mask) {
    switch (mask) {
    case 0x01: return "en";
    case 0x02: return "fr";
    case 0x04: return "de";
    case 0x08: return "it";
    case 0x10: return "es";
    case 0: return "off";
    default: return "?";
    }
}

// Language value -> mask (0 = off); false if the value is not understood
bool ParseLanguage(const char *v, DWORD *mask) {
    static const char *const names[] = {"en", "fr", "de", "it", "es"};   // the game's language ids 0-4
    char s[16];
    int i = 0;
    for (; v[i] && i < 15; ++i) s[i] = Lower(v[i]);
    s[i] = 0;
    if (!strcmp(s, "off") || !strcmp(s, "0") || !s[0]) { *mask = 0; return true; }
    for (int k = 0; k < 5; ++k)
        if (!strcmp(s, names[k])) { *mask = 1u << k; return true; }
    return false;
}

// ---------------------------------------------------------------- the hook (any thread; no file I/O here)

void Note(const char *at, DWORD mask, DWORD from, DWORD to, Kind kind) {
    // key: FNV-1a of the lower-case path from the filter on, mixed with the chosen mask
    DWORD key = 0x811c9dc5;
    for (const char *p = at; *p; ++p) key = (key ^ static_cast<BYTE>(Lower(*p))) * 0x01000193;
    key ^= mask * 0x9e3779b1u;
    if (!key) key = 1;
    EnterCriticalSection(&g_seenLock);
    int slot = static_cast<int>(key & (kSeenSize - 1));
    for (;;) {
        Seen &s = g_seen[slot];
        if (!s.key) {
            if (g_seenCount >= kSeenSize * 3 / 4) { g_seenFull = 1; break; }
            s.key = key;
            s.mask = mask;
            s.from = from;
            s.to = to;
            s.kind = kind;
            s.logged = 0;
            int i = 0;
            const char *p = *at == '\\' ? at + 1 : at;   // skip the filter's leading backslash
            for (; p[i] && i < static_cast<int>(sizeof(s.name)) - 1; ++i) s.name[i] = Lower(p[i]);
            s.name[i] = 0;
            ++g_seenCount;
            break;
        }
        if (s.key == key && s.mask == mask) break;
        slot = (slot + 1) & (kSeenSize - 1);
    }
    LeaveCriticalSection(&g_seenLock);
}

const BYTE *__fastcall FindEntryHook(const BYTE *fs, void *edx, const char *path) {
    const BYTE *rec = g_origFindEntry(fs, edx, path);
    const DWORD mask = static_cast<DWORD>(g_mask);
    if (!mask || !rec || !path) return rec;      // off, or not in this archive (the not-found path ran once, as always)
    const char *at = FindFilter(path);
    if (!at) return rec;
    if (*reinterpret_cast<const DWORD *>(fs + 8) == mask) {   // the game language is the chosen one already
        InterlockedIncrement(&g_nAsIs);
        return rec;
    }
    // search again with a private copy whose mask field holds the chosen language; the real object is never written
    DWORD copy[8];
    memcpy(copy, fs, sizeof(copy));
    copy[2] = mask;
    const BYTE *alt = g_origFindEntry(reinterpret_cast<const BYTE *>(copy), edx, path);
    const DWORD from = *reinterpret_cast<const DWORD *>(rec + 8);
    if (!alt) {
        InterlockedIncrement(&g_nFallback);
        Note(at, mask, from, 0, kFallback);
        return rec;
    }
    if (alt == rec) {
        InterlockedIncrement(&g_nSame);
        Note(at, mask, from, from, kSame);
        return rec;
    }
    InterlockedIncrement(&g_nRedirect);
    Note(at, mask, from, *reinterpret_cast<const DWORD *>(alt + 8), kRedirect);
    return alt;
}

// ---------------------------------------------------------------- helper thread: logging, live options, FS info

void DrainSeen() {
    Seen batch[64];
    for (;;) {
        int n = 0;
        EnterCriticalSection(&g_seenLock);
        for (int i = 0; i < kSeenSize && n < 64; ++i)
            if (g_seen[i].key && !g_seen[i].logged) {
                g_seen[i].logged = 1;
                batch[n++] = g_seen[i];
            }
        LeaveCriticalSection(&g_seenLock);
        if (!n) return;
        for (int i = 0; i < n; ++i) {
            const Seen &s = batch[i];
            if (s.kind == kRedirect)
                Log(1, "redirect %s: %s (spec %08lx) -> %s (spec %08lx)", s.name, SpecName(s.from), s.from,
                    SpecName(s.to), s.to);
            else if (s.kind == kSame)
                Log(2, "unchanged %s: %s (spec %08lx) - language-neutral", s.name, SpecName(s.from), s.from);
            else
                Log(1, "fallback %s: no %s record, kept %s (spec %08lx)", s.name, MaskName(s.mask), SpecName(s.from),
                    s.from);
        }
    }
}

void Burst() {
    LONG r = InterlockedExchange(&g_nRedirect, 0), s = InterlockedExchange(&g_nSame, 0);
    LONG f = InterlockedExchange(&g_nFallback, 0), a = InterlockedExchange(&g_nAsIs, 0);
    if (!r && !s && !f && !a) return;
    EnterCriticalSection(&g_seenLock);
    int distinct = g_seenCount;
    LeaveCriticalSection(&g_seenLock);
    Log(1, "last 30 s: %ld lookups redirected, %ld unchanged (language-neutral), %ld fallback, %ld already in the "
           "game language; %d distinct paths so far%s", r, s, f, a, distinct,
        g_seenFull ? " (table full - later new paths are counted only)" : "");
}

FILETIME g_iniTime;

void PollIni() {
    WIN32_FILE_ATTRIBUTE_DATA d;
    if (!GetFileAttributesExA(g_iniPath, GetFileExInfoStandard, &d)) return;
    if (CompareFileTime(&d.ftLastWriteTime, &g_iniTime) == 0) return;
    g_iniTime = d.ftLastWriteTime;
    char lang[32];
    int enabled = GetPrivateProfileIntA("MercLang", "Enabled", 0, g_iniPath);
    GetPrivateProfileStringA("MercLang", "Language", "es", lang, sizeof(lang), g_iniPath);
    DWORD mask = 0;
    if (!ParseLanguage(lang, &mask)) {
        Log(0, "live: Language=%s not understood (en fr de it es off) - kept %s", lang, MaskName(static_cast<DWORD>(g_mask)));
        return;
    }
    if (!enabled) mask = 0;
    DWORD old = static_cast<DWORD>(InterlockedExchange(&g_mask, static_cast<LONG>(mask)));
    if (old != mask) Log(1, "live: merc language %s -> %s (from the next bark on)", MaskName(old), MaskName(mask));
}

void CheckFsOnce(bool *done) {
    if (*done) return;
    DWORD fs = 0, vtbl = 0;
    __try {
        fs = *reinterpret_cast<const DWORD *>(kGlobalFs);
        if (fs) vtbl = *reinterpret_cast<const DWORD *>(fs);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
    if (!fs) return;
    *done = true;
    const char *what = vtbl == kVtblMulti ? "MultiFileSystem - no wrapper, every lookup reaches FindEntry"
                       : vtbl == kVtblArchive ? "ArchiveFileSystem"
                                              : "another object - a wrapper such as ModLoader's HookFileSystem; files it "
                                                "serves from mods\\ never reach FindEntry (not handled)";
    Log(1, "game file system 0x%08lx, vtable 0x%08lx (%s); ModLoader.asi %s", fs, vtbl, what,
        GetModuleHandleA("ModLoader.asi") ? "loaded" : "not loaded");
}

DWORD WINAPI Helper(LPVOID) {
    bool fsDone = false;
    for (DWORD tick = 1;; ++tick) {
        Sleep(1000);
        if (g_live) PollIni();
        DrainSeen();
        CheckFsOnce(&fsDone);
        if (tick % 30 == 0) Burst();
    }
}

// ---------------------------------------------------------------- start

// files below <game>\mods whose path contains the filter (ModLoader answers those itself - B.4 risk)
void ScanMods(const char *dir, int depth, int *files, int *hits) {
    if (depth > 12 || *files > 50000) return;
    char pattern[MAX_PATH];
    _snprintf_s(pattern, sizeof(pattern), _TRUNCATE, "%s*", dir);
    WIN32_FIND_DATAA fd;
    HANDLE h = FindFirstFileA(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (!strcmp(fd.cFileName, ".") || !strcmp(fd.cFileName, "..")) continue;
        char path[MAX_PATH];
        _snprintf_s(path, sizeof(path), _TRUNCATE, "%s%s", dir, fd.cFileName);
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            char sub[MAX_PATH];
            _snprintf_s(sub, sizeof(sub), _TRUNCATE, "%s\\", path);
            ScanMods(sub, depth + 1, files, hits);
        } else {
            ++*files;
            const char *rel = path + strlen(g_gameDir) + 4;   // "\audio\streams\..." below <game>\mods
            if (FindFilter(rel)) {
                if (*hits < 5) Log(0, "mods file under the filter: %s - ModLoader serves it, TruMercLang cannot change it", path);
                ++*hits;
            }
        }
    } while (FindNextFileA(h, &fd));
    FindClose(h);
}

bool CheckGame() {
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) {
        Log(0, "image base 0x%08lx, expected 0x%08lx - nothing hooked", base, kImageBase);
        return false;
    }
    int failed = 0, total = 0;
    for (const Check &c : kChecks) {
        int n = 0;
        ++total;
        if (HexAt(c.at, c.hex, &n)) {
            Log(3, "check ok 0x%08lx (%d bytes) %s", c.at, n, c.what);
        } else {
            ++failed;
            Log(0, "check FAILED 0x%08lx (%d bytes) %s", c.at, n, c.what);
        }
    }
    DWORD fnv = 0;
    ++total;
    if (!Fnv(kFindEntry, kFindEntryEnd, &fnv) || fnv != kFindEntryFnv) {
        ++failed;
        Log(0, "check FAILED FindEntry body 0x%08lx-0x%08lx fnv 0x%08lx, expected 0x%08lx (other build or patched)",
            kFindEntry, kFindEntryEnd, fnv, kFindEntryFnv);
    }
    if (failed) {
        Log(0, "checks: %d of %d failed (other tru.exe build, or another plugin patched these bytes) - nothing hooked",
            failed, total);
        return false;
    }
    Log(1, "checks: %d of %d ok (FindEntry body fnv 0x%08lx, mask at this+8, 4 callers, vtable, language ids)", total,
        total, fnv);
    return true;
}

bool WriteJump(DWORD at, const void *to, int length) {
    BYTE code[16];
    memset(code, 0x90, sizeof(code));
    code[0] = 0xe9;
    DWORD rel = reinterpret_cast<DWORD>(to) - (at + 5);
    memcpy(code + 1, &rel, 4);
    DWORD old = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(at), static_cast<SIZE_T>(length), PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "VirtualProtect failed (%lu) at 0x%08lx - nothing hooked", GetLastError(), at);
        return false;
    }
    memcpy(reinterpret_cast<void *>(at), code, static_cast<size_t>(length));
    DWORD dummy = 0;
    VirtualProtect(reinterpret_cast<void *>(at), static_cast<SIZE_T>(length), old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(at), static_cast<SIZE_T>(length));
    return true;
}

bool InstallHook() {
    BYTE *tr = static_cast<BYTE *>(VirtualAlloc(nullptr, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    if (!tr) {
        Log(0, "no code page for the trampoline (%lu) - nothing hooked", GetLastError());
        return false;
    }
    memcpy(tr, reinterpret_cast<const void *>(kFindEntry), kPrologue);
    tr[kPrologue] = 0xe9;
    DWORD rel = (kFindEntry + kPrologue) - (reinterpret_cast<DWORD>(tr) + kPrologue + 5);
    memcpy(tr + kPrologue + 1, &rel, 4);
    DWORD old = 0;
    if (!VirtualProtect(tr, 4096, PAGE_EXECUTE_READ, &old)) {
        Log(0, "trampoline protection failed (%lu) - nothing hooked", GetLastError());
        VirtualFree(tr, 0, MEM_RELEASE);
        return false;
    }
    FlushInstructionCache(GetCurrentProcess(), tr, 16);
    g_origFindEntry = reinterpret_cast<FindEntryFn>(tr);
    if (!WriteJump(kFindEntry, reinterpret_cast<const void *>(&FindEntryHook), kPrologue)) return false;
    Log(1, "hook installed: FindEntry 0x%08lx -> 0x%08lx (trampoline 0x%08lx)", kFindEntry,
        reinterpret_cast<DWORD>(&FindEntryHook), reinterpret_cast<DWORD>(tr));
    return true;
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruMercLang.log", dir);
    _snprintf_s(g_iniPath, sizeof(g_iniPath), _TRUNCATE, "%sTruMercLang.ini", dir);
    len = GetModuleFileNameA(nullptr, g_gameDir, MAX_PATH);
    while (len > 0 && g_gameDir[len - 1] != '\\' && g_gameDir[len - 1] != '/') --len;
    g_gameDir[len] = 0;

    char lang[32], filter[128];
    g_enabled = GetPrivateProfileIntA("MercLang", "Enabled", 0, g_iniPath);
    g_live = GetPrivateProfileIntA("MercLang", "LiveReload", 0, g_iniPath);
    g_logLevel = GetPrivateProfileIntA("MercLang", "LogLevel", 1, g_iniPath);
    GetPrivateProfileStringA("MercLang", "Language", "es", lang, sizeof(lang), g_iniPath);
    GetPrivateProfileStringA("MercLang", "PathFilter", "\\vo\\enemy\\merc\\", filter, sizeof(filter), g_iniPath);
    int fl = 0;
    for (; filter[fl] && fl < static_cast<int>(sizeof(g_filter)) - 1; ++fl)
        g_filter[fl] = filter[fl] == '/' ? '\\' : Lower(filter[fl]);
    g_filter[fl] = 0;
    WIN32_FILE_ATTRIBUTE_DATA d;
    if (GetFileAttributesExA(g_iniPath, GetFileExInfoStandard, &d)) g_iniTime = d.ftLastWriteTime;

    DWORD mask = 0;
    bool langOk = ParseLanguage(lang, &mask);
    Log(1, "---- %s loaded (enabled %d, language %s = mask 0x%02lx, filter %s, live reload %d, log level %d)", kVersion,
        g_enabled, lang, mask, g_filter, g_live, g_logLevel);
    if (!g_enabled) { Log(1, "disabled by TruMercLang.ini (Enabled=0) - nothing hooked"); return; }
    if (!langOk) { Log(0, "Language=%s not understood (en fr de it es off) - nothing hooked", lang); return; }
    if (strlen(filter) >= sizeof(g_filter) || fl < 2) {
        Log(0, "PathFilter '%s' empty or longer than %u characters - nothing hooked", filter,
            static_cast<unsigned>(sizeof(g_filter) - 1));
        return;
    }
    if (!mask && !g_live) { Log(1, "Language=off and LiveReload=0 - nothing hooked"); return; }

    char mods[MAX_PATH];
    _snprintf_s(mods, sizeof(mods), _TRUNCATE, "%smods\\", g_gameDir);
    int files = 0, hits = 0;
    ScanMods(mods, 0, &files, &hits);
    if (hits)
        Log(0, "warning: %d of %d files below mods\\ match the filter - ModLoader answers them before the archive, those "
               "barks keep their language", hits, files);
    else
        Log(1, "mods\\: %d files, none under the filter (every merc bark comes from the archive)", files);

    if (!CheckGame()) return;
    g_mask = static_cast<LONG>(mask);
    if (!InstallHook()) return;
    HANDLE h = CreateThread(nullptr, 0, &Helper, nullptr, 0, nullptr);
    if (h) CloseHandle(h);
    else Log(0, "helper thread failed (%lu) - the hook works, but no redirect / burst lines are logged", GetLastError());
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        InitializeCriticalSection(&g_logLock);
        InitializeCriticalSection(&g_seenLock);
        Start(instance);
    }
    return TRUE;
}

// exported so the loader / tools can identify the plugin (the Ultimate ASI Loader needs no particular export)
extern "C" __declspec(dllexport) const char *TruMercLangVersion() { return kVersion; }
