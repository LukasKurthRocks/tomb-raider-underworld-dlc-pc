// TruFlowCore.h - TruMenu 0.11 "Ablauf" (guided test runs): the flow file parser, the small pattern matcher and the
// line watch test. Own code, no game access and no Windows calls: TruMenu.cpp holds the run time (steps, counters,
// ring, overlay); selftest/TruFlowCoreTest.cpp checks this header offline against the PowerShell parser of
// Invoke-TruTestRun.ps1 / Test-TruPreflight.ps1 (same records, same patterns).
//
// TruMenu.flow.txt (next to tru.exe, UTF-8 with or without BOM, one record per line, fields separated by " | "):
//   # comment                                         empty lines and lines starting with '#' are skipped
//   flow    | <id> | <title>                           once, optional
//   counter | <id> | <source> | <target> | <text>      target 0 = only counted
//   step    | <id> | action|observe|mark | <text> [| key=value ...]
// step keys: do=<cmd>;<cmd>  (action only, the regression-shortcut rules: at most 12 commands / 319 characters, no
//            game.quit), after=<cond> (all of them, repeatable, at most 4), check=<cond> (any of them marks the step
//            ok, at most 4), fail=<cond> (any of them marks it failed, at most 4), count=<counter>[,<counter>] (at most
//            4, the first one shows in the status line), skip=<reason> (skipped when reached), hint=<text>.
// conditions: step:<id> (that step ok), done:<id> (ok / fail / skip), counter:<id> (target reached), mark:<name>
//             (a marker of that name while the step is current), log:<TruX.log>:<pattern>, trace:<category>:<pattern>
//             (TruTrace.log lines "time [unit] <category>: text"; empty pattern = any line of the category).
// counter sources: units[:<unit>] (TruTrace stream slot became loaded), levels[:<unit>] (TruTrace
//             STREAM_LevelLoadAndInit result), deaths (DeathState entered), restores (TruTrace SAVE_RestoreGame
//             result), toggle:<switch id>, item:<item id>, mark:<name>, log:<TruX.log>:<pattern>,
//             trace:<category>:<pattern>.
// pattern: plain text = substring (case-sensitive); "re:<expr>" = a regex subset: literals, '.', escapes \d \w \s
//          \D \W \S and \<punctuation>, classes [abc] [a-z] [^...] (with the escapes inside), the postfix
//          quantifiers * + ?, anchors ^ (first) and $ (last). No groups, no alternation, no {n}. Matching is a
//          state-set simulation (linear in the line length, no backtracking).
// Texts are shown in ASCII (the menu font): UTF-8 umlauts become ae / oe / ue / ss, other non-ASCII characters '?'.
#pragma once
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <stdio.h>

namespace truflow {

const int kMaxSteps = 64, kMaxCounters = 16, kMaxConds = 4, kMaxCount = 4, kMaxWatches = 48, kMaxAtoms = 63;
const int kIdLen = 32, kTextLen = 160, kDoLen = 320, kPatLen = 128, kFileLen = 40, kCatLen = 16, kMaxLine = 1000;
const int kMaxCmds = 12;

enum Kind { kKindAction = 0, kKindObserve = 1, kKindMark = 2 };
enum CondType { kCondStep = 1, kCondDone = 2, kCondCounter = 3, kCondMark = 4, kCondWatch = 5 };
enum Source { kSrcUnits = 1, kSrcLevels, kSrcDeaths, kSrcRestores, kSrcToggle, kSrcItem, kSrcMark, kSrcWatch };

const char *const kKindNames[3] = {"action", "observe", "mark"};
const char *const kCondNames[6] = {"?", "step", "done", "counter", "mark", "watch"};
const char *const kSrcNames[9] = {"?", "units", "levels", "deaths", "restores", "toggle", "item", "mark", "watch"};
// TruTrace 0.2 categories (kCatName in TruTrace.cpp)
const char *const kTraceCats[] = {"trace", "sound", "teleport", "chart", "power", "spawn", "obj", "timevec", "level",
                                  "portal", "stream", "save", "progress", "message", "gamedata"};
const int kTraceCatCount = sizeof(kTraceCats) / sizeof(kTraceCats[0]);

// ---- pattern: substring or the regex subset ----
enum AtomType { kAtLit = 0, kAtAny, kAtSet };
struct Atom {
    unsigned char type, quant, ch;          // quant: 0 = once, '?' , '*'
    unsigned char set[32];                  // kAtSet: bit per byte
};
struct Pattern {
    bool regex, anchorStart, anchorEnd;
    int count;                              // atoms
    Atom atoms[kMaxAtoms];
    char text[kPatLen];                     // the substring (regex = false) / the source after "re:"
};

inline void SetBit(unsigned char *s, int c) { s[(c & 0xff) >> 3] |= static_cast<unsigned char>(1u << (c & 7)); }
inline bool HasBit(const unsigned char *s, int c) { return (s[(c & 0xff) >> 3] >> (c & 7)) & 1; }
inline void SetClass(unsigned char *s, char cls) {   // \d \w \s (ASCII)
    for (int c = 0; c < 128; ++c) {
        bool in = cls == 'd' ? (c >= '0' && c <= '9')
                : cls == 'w' ? ((c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_')
                : (c == ' ' || c == '\t' || c == '\r' || c == '\n' || c == '\f' || c == '\v');
        if (in) SetBit(s, c);
    }
}
inline bool IsEscapable(char c) { return c && strchr("\\.[]()*+?^$|{}-/:'\"#&%!=<>,;@~`", c) != nullptr; }

// compiles "re:" source; false + reason on a construct outside the subset
inline bool CompileRegex(const char *src, Pattern &p, char *why, size_t whySize) {
    p.count = 0;
    p.anchorStart = p.anchorEnd = false;
    const char *s = src;
    if (*s == '^') { p.anchorStart = true; ++s; }
    while (*s) {
        if (*s == '$' && !s[1]) { p.anchorEnd = true; break; }
        if (strchr("()|{}", *s)) { _snprintf_s(why, whySize, _TRUNCATE, "'%c' is not in the pattern subset (no groups, alternation or {n})", *s); return false; }
        if (*s == '*' || *s == '+' || *s == '?') { _snprintf_s(why, whySize, _TRUNCATE, "quantifier '%c' without an atom", *s); return false; }
        if (*s == '^' || *s == '$') { _snprintf_s(why, whySize, _TRUNCATE, "anchor '%c' only at the start / end", *s); return false; }
        Atom a;
        memset(&a, 0, sizeof(a));
        if (*s == '.') { a.type = kAtAny; ++s; }
        else if (*s == '\\') {
            char e = s[1];
            if (!e) { _snprintf_s(why, whySize, _TRUNCATE, "pattern ends with '\\'"); return false; }
            if (e == 'd' || e == 'w' || e == 's' || e == 'D' || e == 'W' || e == 'S') {
                a.type = kAtSet;
                SetClass(a.set, static_cast<char>(tolower(static_cast<unsigned char>(e))));
                if (isupper(static_cast<unsigned char>(e))) for (int i = 0; i < 32; ++i) a.set[i] = static_cast<unsigned char>(~a.set[i]);
            } else if (IsEscapable(e)) { a.type = kAtLit; a.ch = static_cast<unsigned char>(e); }
            else { _snprintf_s(why, whySize, _TRUNCATE, "escape '\\%c' is not in the pattern subset", e); return false; }
            s += 2;
        } else if (*s == '[') {
            ++s;
            bool neg = false;
            if (*s == '^') { neg = true; ++s; }
            a.type = kAtSet;
            bool first = true;
            while (*s && (*s != ']' || first)) {
                int lo;
                if (*s == '\\') {
                    char e = s[1];
                    if (!e) break;
                    if (e == 'd' || e == 'w' || e == 's') {
                        SetClass(a.set, e);
                        s += 2;
                        first = false;
                        if (*s == '-' && s[1] && s[1] != ']') { _snprintf_s(why, whySize, _TRUNCATE, "a range cannot start at \\%c", e); return false; }
                        continue;
                    }
                    if (!IsEscapable(e)) { _snprintf_s(why, whySize, _TRUNCATE, "escape '\\%c' in a class is not in the subset", e); return false; }
                    lo = static_cast<unsigned char>(e);
                    s += 2;
                } else {
                    if (*s == '[') { _snprintf_s(why, whySize, _TRUNCATE, "'[' inside a class must be escaped"); return false; }
                    lo = static_cast<unsigned char>(*s++);
                }
                first = false;
                if (*s == '-' && s[1] && s[1] != ']') {
                    int hi;
                    if (s[1] == '\\') {
                        if (!s[2] || !IsEscapable(s[2]) || strchr("dws", s[2])) { _snprintf_s(why, whySize, _TRUNCATE, "bad range end in a class"); return false; }
                        hi = static_cast<unsigned char>(s[2]);
                        s += 3;
                    } else { hi = static_cast<unsigned char>(s[1]); s += 2; }
                    if (hi < lo) { _snprintf_s(why, whySize, _TRUNCATE, "range %c-%c is reversed", lo, hi); return false; }
                    for (int c = lo; c <= hi; ++c) SetBit(a.set, c);
                } else SetBit(a.set, lo);
            }
            if (*s != ']') { _snprintf_s(why, whySize, _TRUNCATE, "class without ']'"); return false; }
            ++s;
            if (neg) for (int i = 0; i < 32; ++i) a.set[i] = static_cast<unsigned char>(~a.set[i]);
        } else if (*s == ']') { _snprintf_s(why, whySize, _TRUNCATE, "']' must be escaped"); return false; }
        else { a.type = kAtLit; a.ch = static_cast<unsigned char>(*s++); }
        char q = *s;
        int copies = 1;
        if (q == '*' || q == '?') { a.quant = static_cast<unsigned char>(q); ++s; }
        else if (q == '+') { copies = 2; ++s; }               // x+ = x x*
        if (*s == '*' || *s == '+' || *s == '?') { _snprintf_s(why, whySize, _TRUNCATE, "two quantifiers in a row"); return false; }
        for (int k = 0; k < copies; ++k) {
            if (p.count >= kMaxAtoms) { _snprintf_s(why, whySize, _TRUNCATE, "more than %d atoms", kMaxAtoms); return false; }
            p.atoms[p.count] = a;
            if (copies == 2) p.atoms[p.count].quant = k ? '*' : 0;
            ++p.count;
        }
    }
    if (!p.count && !p.anchorStart && !p.anchorEnd) { _snprintf_s(why, whySize, _TRUNCATE, "empty regex"); return false; }
    return true;
}

inline bool CompilePattern(const char *text, Pattern &p, char *why, size_t whySize) {
    memset(&p, 0, sizeof(p));
    if (!strncmp(text, "re:", 3)) {
        p.regex = true;
        if (strlen(text + 3) >= sizeof(p.text)) { _snprintf_s(why, whySize, _TRUNCATE, "pattern longer than %d", kPatLen - 1); return false; }
        strncpy_s(p.text, sizeof(p.text), text + 3, _TRUNCATE);
        return CompileRegex(p.text, p, why, whySize);
    }
    if (strlen(text) >= sizeof(p.text)) { _snprintf_s(why, whySize, _TRUNCATE, "pattern longer than %d", kPatLen - 1); return false; }
    strncpy_s(p.text, sizeof(p.text), text, _TRUNCATE);
    return true;
}

inline bool AtomMatches(const Atom &a, unsigned char c) {
    if (a.type == kAtAny) return c != '\n';
    if (a.type == kAtLit) return a.ch == c;
    return HasBit(a.set, c);
}
typedef unsigned long long Bits;
inline Bits Closure(const Pattern &p, Bits s) {
    for (int i = 0; i < p.count; ++i)
        if ((s >> i) & 1 && p.atoms[i].quant) s |= 1ull << (i + 1);
    return s;
}
inline bool RegexSearch(const Pattern &p, const char *text) {
    const Bits accept = 1ull << p.count;
    const Bits start = Closure(p, 1);
    Bits s = start;
    for (const unsigned char *t = reinterpret_cast<const unsigned char *>(text);; ++t) {
        if (!p.anchorEnd && (s & accept)) return true;
        if (!*t) break;
        Bits next = 0;
        for (int i = 0; i < p.count; ++i) {
            if (!((s >> i) & 1) || !AtomMatches(p.atoms[i], *t)) continue;
            next |= p.atoms[i].quant == '*' ? (1ull << i) : (1ull << (i + 1));
        }
        s = Closure(p, next);
        if (!p.anchorStart) s |= start;
        else if (!s) return false;
    }
    return (s & accept) != 0;
}
inline bool PatternMatches(const Pattern &p, const char *text) {
    return p.regex ? RegexSearch(p, text) : (!p.text[0] || strstr(text, p.text) != nullptr);
}

// ---- watches: a pattern on one log file (and for TruTrace.log one category) ----
struct Watch {
    char file[kFileLen];                    // "TruTrace.log"
    char cat[kCatLen];                      // TruTrace category or ""
    char source[kPatLen + 4];               // the pattern text as written (with "re:")
    Pattern pat;
};

// "HH:MM:SS.mmm [unit] cat: text" -> the text after "] <cat>: " (null = not this category)
inline const char *TraceText(const char *line, const char *cat) {
    char key[kCatLen + 4];
    _snprintf_s(key, sizeof(key), _TRUNCATE, "] %s: ", cat);
    const char *p = strstr(line, key);
    return p ? p + strlen(key) : nullptr;
}
inline bool WatchMatches(const Watch &w, const char *line) {
    if (w.cat[0]) {
        const char *text = TraceText(line, w.cat);
        return text && PatternMatches(w.pat, text);
    }
    return PatternMatches(w.pat, line);
}

// ---- flow records ----
struct Cond {
    int type;
    char ref[kIdLen];                       // step / counter id, mark name
    int index;                              // resolved step / counter / watch index
};
struct Counter {
    char id[kIdLen];
    int source;
    char arg[kPatLen + 48];                 // unit name, switch / item id, mark name; watch: "file:pattern"
    int target;
    int watch;                              // kSrcUnits / Levels / Restores / Watch: the watch index, else -1
    char text[kTextLen];
};
struct Step {
    char id[kIdLen];
    int kind;
    char text[kTextLen];                    // ASCII (transliterated)
    char hint[kTextLen];
    char cmds[kDoLen];
    char skip[kTextLen];
    Cond after[kMaxConds], check[kMaxConds], fail[kMaxConds];
    int nAfter, nCheck, nFail;
    char countIds[kMaxCount][kIdLen];
    int counters[kMaxCount], nCount;
    int line;
};
struct Flow {
    char id[kIdLen];
    char title[kTextLen];
    bool hasHeader;
    Step steps[kMaxSteps];
    int nSteps;
    Counter counters[kMaxCounters];
    int nCounters;
    Watch watches[kMaxWatches];
    int nWatches;
    int errors;
};

// error sink: line number + message
typedef void (*ErrorFn)(void *ctx, int line, const char *message);

inline void Trim(char *s) {
    size_t n = strlen(s);
    while (n && (s[n - 1] == ' ' || s[n - 1] == '\t' || s[n - 1] == '\r' || s[n - 1] == '\n')) s[--n] = 0;
    size_t i = 0;
    while (s[i] == ' ' || s[i] == '\t') ++i;
    if (i) memmove(s, s + i, n - i + 1);
}

// UTF-8 -> ASCII for the menu font (umlauts spelled out, a few punctuation marks mapped, anything else '?')
inline void Ascii(const char *in, char *out, size_t size) {
    size_t o = 0;
    const unsigned char *p = reinterpret_cast<const unsigned char *>(in);
    auto put = [&](const char *s) { while (*s && o + 1 < size) out[o++] = *s++; };
    while (*p && o + 1 < size) {
        unsigned char c = *p;
        if (c < 0x80) { out[o++] = static_cast<char>(c); ++p; continue; }
        int len = (c & 0xe0) == 0xc0 ? 2 : (c & 0xf0) == 0xe0 ? 3 : (c & 0xf8) == 0xf0 ? 4 : 1;
        unsigned cp = len == 2 ? c & 0x1f : len == 3 ? c & 0x0f : len == 4 ? c & 0x07 : '?';
        int k = 1;
        for (; k < len && (p[k] & 0xc0) == 0x80; ++k) cp = (cp << 6) | (p[k] & 0x3f);
        if (k < len) { put("?"); ++p; continue; }
        p += len;
        switch (cp) {
        case 0xe4: put("ae"); break; case 0xf6: put("oe"); break; case 0xfc: put("ue"); break;
        case 0xc4: put("Ae"); break; case 0xd6: put("Oe"); break; case 0xdc: put("Ue"); break;
        case 0xdf: put("ss"); break; case 0xb7: put("-"); break; case 0x2013: case 0x2014: put("-"); break;
        case 0x201e: case 0x201c: case 0x201d: put("\""); break; case 0x2018: case 0x2019: put("'"); break;
        case 0x2026: put("..."); break; case 0xa0: put(" "); break; case 0x2192: put("->"); break;
        default: put("?"); break;
        }
    }
    out[o] = 0;
}

inline bool ValidId(const char *s) {
    size_t n = strlen(s);
    if (!n || n >= static_cast<size_t>(kIdLen)) return false;
    for (const char *p = s; *p; ++p)
        if (!isalnum(static_cast<unsigned char>(*p)) && *p != '_' && *p != '.' && *p != '-') return false;
    return true;
}
inline bool ValidName(const char *s) {                   // unit names, item / switch ids in sources
    size_t n = strlen(s);
    if (!n || n > 63) return false;
    for (const char *p = s; *p; ++p)
        if (!isalnum(static_cast<unsigned char>(*p)) && *p != '_' && *p != '.' && *p != '-' && *p != ':') return false;
    return true;
}
inline bool ValidLogFile(const char *s) {               // Tru<Name>.log
    size_t n = strlen(s);
    if (n < 8 || n >= static_cast<size_t>(kFileLen) || strncmp(s, "Tru", 3) || _stricmp(s + n - 4, ".log")) return false;
    for (const char *p = s + 3; p < s + n - 4; ++p) if (!isalnum(static_cast<unsigned char>(*p))) return false;
    return true;
}
inline bool KnownTraceCat(const char *s) {
    for (int i = 0; i < kTraceCatCount; ++i) if (!strcmp(kTraceCats[i], s)) return true;
    return false;
}

// a watch (file, category, pattern) - an equal one is shared; -1 + reason on a bad pattern / too many
inline int AddWatch(Flow &f, const char *file, const char *cat, const char *pattern, char *why, size_t whySize) {
    for (int i = 0; i < f.nWatches; ++i)
        if (!_stricmp(f.watches[i].file, file) && !strcmp(f.watches[i].cat, cat) && !strcmp(f.watches[i].source, pattern)) return i;
    if (f.nWatches >= kMaxWatches) { _snprintf_s(why, whySize, _TRUNCATE, "more than %d log patterns", kMaxWatches); return -1; }
    Watch &w = f.watches[f.nWatches];
    memset(&w, 0, sizeof(w));
    strncpy_s(w.file, sizeof(w.file), file, _TRUNCATE);
    strncpy_s(w.cat, sizeof(w.cat), cat, _TRUNCATE);
    strncpy_s(w.source, sizeof(w.source), pattern, _TRUNCATE);
    if (!CompilePattern(pattern, w.pat, why, whySize)) return -1;
    return f.nWatches++;
}

// "log:<File>:<pattern>" / "trace:<cat>:<pattern>" -> watch index (-1 + reason)
inline int ParseWatchRef(Flow &f, const char *text, char *why, size_t whySize) {
    char kind[8] = "", a[kFileLen] = "";
    const char *c1 = strchr(text, ':');
    if (!c1 || c1 - text >= static_cast<int>(sizeof(kind))) { _snprintf_s(why, whySize, _TRUNCATE, "expected log:<file>:<pattern> or trace:<category>:<pattern>"); return -1; }
    memcpy(kind, text, static_cast<size_t>(c1 - text));
    const char *c2 = strchr(c1 + 1, ':');
    if (!c2) { _snprintf_s(why, whySize, _TRUNCATE, "'%s' needs <name>:<pattern>", kind); return -1; }
    if (c2 - c1 - 1 >= static_cast<int>(sizeof(a))) { _snprintf_s(why, whySize, _TRUNCATE, "name too long"); return -1; }
    memcpy(a, c1 + 1, static_cast<size_t>(c2 - c1 - 1));
    a[c2 - c1 - 1] = 0;
    const char *pat = c2 + 1;
    if (!strcmp(kind, "log")) {
        if (!ValidLogFile(a)) { _snprintf_s(why, whySize, _TRUNCATE, "log file '%s' must be Tru<Name>.log", a); return -1; }
        if (!*pat) { _snprintf_s(why, whySize, _TRUNCATE, "empty log pattern"); return -1; }
        return AddWatch(f, a, "", pat, why, whySize);
    }
    if (!strcmp(kind, "trace")) {
        if (!KnownTraceCat(a)) { _snprintf_s(why, whySize, _TRUNCATE, "unknown TruTrace category '%s'", a); return -1; }
        return AddWatch(f, "TruTrace.log", a, pat, why, whySize);
    }
    _snprintf_s(why, whySize, _TRUNCATE, "expected log: or trace:, got '%s:'", kind);
    return -1;
}

// one condition (references resolved later by Resolve)
inline bool ParseCond(Flow &f, const char *text, Cond &c, char *why, size_t whySize) {
    memset(&c, 0, sizeof(c));
    c.index = -1;
    struct { const char *prefix; int type; } simple[] = {{"step:", kCondStep}, {"done:", kCondDone}, {"counter:", kCondCounter}, {"mark:", kCondMark}};
    for (auto &s : simple) {
        size_t n = strlen(s.prefix);
        if (strncmp(text, s.prefix, n)) continue;
        c.type = s.type;
        const char *ref = text + n;
        if (s.type == kCondMark ? (!*ref || strlen(ref) >= static_cast<size_t>(kIdLen)) : !ValidId(ref)) {
            _snprintf_s(why, whySize, _TRUNCATE, "bad %s reference '%s'", s.prefix, ref);
            return false;
        }
        Ascii(ref, c.ref, sizeof(c.ref));
        return true;
    }
    if (!strncmp(text, "log:", 4) || !strncmp(text, "trace:", 6)) {
        c.type = kCondWatch;
        c.index = ParseWatchRef(f, text, why, whySize);
        return c.index >= 0;
    }
    _snprintf_s(why, whySize, _TRUNCATE, "unknown condition '%.40s' (step: done: counter: mark: log: trace:)", text);
    return false;
}

inline bool ParseSource(Flow &f, const char *text, Counter &c, char *why, size_t whySize) {
    c.watch = -1;
    c.arg[0] = 0;
    char name[80] = "";
    const char *colon = strchr(text, ':');
    size_t head = colon ? static_cast<size_t>(colon - text) : strlen(text);
    auto is = [&](const char *w) { return strlen(w) == head && !strncmp(text, w, head); };
    if (colon) strncpy_s(name, sizeof(name), colon + 1, _TRUNCATE);
    if (is("units") || is("levels")) {
        bool units = is("units");
        c.source = units ? kSrcUnits : kSrcLevels;
        if (colon && !ValidName(name)) { _snprintf_s(why, whySize, _TRUNCATE, "bad unit name '%s'", name); return false; }
        strncpy_s(c.arg, sizeof(c.arg), name, _TRUNCATE);
        char pat[kPatLen + 8];
        if (units) {
            if (name[0]) _snprintf_s(pat, sizeof(pat), _TRUNCATE, "'%s' state 2 = loaded", name);
            else strncpy_s(pat, sizeof(pat), "' state 2 = loaded", _TRUNCATE);
        } else if (name[0]) {
            char esc[140];
            size_t o = 0;
            for (const char *p = name; *p && o + 2 < sizeof(esc); ++p) {
                if (*p == '.' || *p == '-' || *p == ':') esc[o++] = '\\';
                esc[o++] = *p;
            }
            esc[o] = 0;
            _snprintf_s(pat, sizeof(pat), _TRUNCATE, "re:STREAM_LevelLoadAndInit '%s' \\(.*\\) -> unit entry", esc);
        } else strncpy_s(pat, sizeof(pat), ") -> unit entry 0x", _TRUNCATE);
        c.watch = AddWatch(f, "TruTrace.log", units ? "stream" : "level", pat, why, whySize);
        return c.watch >= 0;
    }
    if (is("restores")) {
        if (colon) { _snprintf_s(why, whySize, _TRUNCATE, "restores takes no argument"); return false; }
        c.source = kSrcRestores;
        c.watch = AddWatch(f, "TruTrace.log", "save", "re:SAVE_RestoreGame\\(\\d+\\) -> ", why, whySize);
        return c.watch >= 0;
    }
    if (is("deaths")) {
        if (colon) { _snprintf_s(why, whySize, _TRUNCATE, "deaths takes no argument"); return false; }
        c.source = kSrcDeaths;
        return true;
    }
    if (is("toggle") || is("item")) {
        c.source = is("toggle") ? kSrcToggle : kSrcItem;
        if (!ValidName(name)) { _snprintf_s(why, whySize, _TRUNCATE, "bad %.*s id '%s'", static_cast<int>(head), text, name); return false; }
        strncpy_s(c.arg, sizeof(c.arg), name, _TRUNCATE);
        return true;
    }
    if (is("mark")) {
        c.source = kSrcMark;
        if (!name[0] || strlen(name) >= static_cast<size_t>(kIdLen)) { _snprintf_s(why, whySize, _TRUNCATE, "bad mark name"); return false; }
        Ascii(name, c.arg, kIdLen);
        return true;
    }
    if (is("log") || is("trace")) {
        c.source = kSrcWatch;
        c.watch = ParseWatchRef(f, text, why, whySize);
        if (c.watch >= 0) strncpy_s(c.arg, sizeof(c.arg), text, _TRUNCATE);
        return c.watch >= 0;
    }
    _snprintf_s(why, whySize, _TRUNCATE, "unknown counter source '%.40s' (units levels deaths restores toggle: item: mark: log: trace:)", text);
    return false;
}

inline int FindStep(const Flow &f, const char *id) {
    for (int i = 0; i < f.nSteps; ++i) if (!_stricmp(f.steps[i].id, id)) return i;
    return -1;
}
inline int FindCounter(const Flow &f, const char *id) {
    for (int i = 0; i < f.nCounters; ++i) if (!_stricmp(f.counters[i].id, id)) return i;
    return -1;
}

// splits on '|' into at most 24 trimmed fields (in place)
inline int SplitFields(char *line, char **fields, int max) {
    int n = 0;
    char *p = line;
    while (n < max) {
        char *bar = strchr(p, '|');
        if (bar) *bar = 0;
        Trim(p);
        fields[n++] = p;
        if (!bar) break;
        p = bar + 1;
    }
    return n;
}

// one record into f (steps / counters appended); false + reason (f unchanged then)
inline bool ParseRecord(Flow &f, const char *text, char *why, size_t whySize) {
    if (strlen(text) > static_cast<size_t>(kMaxLine)) { _snprintf_s(why, whySize, _TRUNCATE, "line longer than %d", kMaxLine); return false; }
    char line[kMaxLine + 2];
    strncpy_s(line, sizeof(line), text, _TRUNCATE);
    char *fl[24];
    int n = SplitFields(line, fl, 24);
    int watchesBefore = f.nWatches;
    auto fail = [&](const char *fmt, const char *a) {
        _snprintf_s(why, whySize, _TRUNCATE, fmt, a);
        f.nWatches = watchesBefore;            // watches added by this line go again
        return false;
    };
    if (!_stricmp(fl[0], "flow")) {
        if (f.hasHeader) return fail("a second flow record%s", "");
        if (n < 2 || !ValidId(fl[1])) return fail("flow | <id> | <title>: bad id '%s'", n > 1 ? fl[1] : "");
        if (n > 3) return fail("flow record with more than 3 fields%s", "");
        if (n > 2 && strlen(fl[2]) >= static_cast<size_t>(kTextLen)) return fail("title longer than 159 bytes%s", "");
        strncpy_s(f.id, sizeof(f.id), fl[1], _TRUNCATE);
        Ascii(n > 2 ? fl[2] : "", f.title, sizeof(f.title));
        f.hasHeader = true;
        return true;
    }
    if (!_stricmp(fl[0], "counter")) {
        if (n < 4 || n > 5) return fail("counter | <id> | <source> | <target> | <text>%s", "");
        if (!ValidId(fl[1])) return fail("bad counter id '%s'", fl[1]);
        if (FindCounter(f, fl[1]) >= 0) return fail("counter id '%s' twice", fl[1]);
        if (f.nCounters >= kMaxCounters) return fail("more than 16 counters%s", "");
        Counter c;
        memset(&c, 0, sizeof(c));
        strncpy_s(c.id, sizeof(c.id), fl[1], _TRUNCATE);
        char reason[200];
        if (!ParseSource(f, fl[2], c, reason, sizeof(reason))) return fail("%s", reason);
        const char *t = fl[3];
        if (!*t || strlen(t) > 5) return fail("counter target '%s' must be 0..99999", t);
        for (const char *p = t; *p; ++p) if (!isdigit(static_cast<unsigned char>(*p))) return fail("counter target '%s' must be 0..99999", t);
        c.target = atoi(t);
        if (n > 4 && strlen(fl[4]) >= static_cast<size_t>(kTextLen)) return fail("counter text longer than 159 bytes%s", "");
        Ascii(n > 4 ? fl[4] : "", c.text, sizeof(c.text));
        f.counters[f.nCounters++] = c;
        return true;
    }
    if (!_stricmp(fl[0], "step")) {
        if (n < 4) return fail("step | <id> | <kind> | <text> [| key=value ...]%s", "");
        if (!ValidId(fl[1])) return fail("bad step id '%s'", fl[1]);
        if (FindStep(f, fl[1]) >= 0) return fail("step id '%s' twice", fl[1]);
        if (f.nSteps >= kMaxSteps) return fail("more than 64 steps%s", "");
        static Step s;                              // large: not on the stack
        memset(&s, 0, sizeof(s));
        strncpy_s(s.id, sizeof(s.id), fl[1], _TRUNCATE);
        s.kind = -1;
        for (int k = 0; k < 3; ++k) if (!_stricmp(fl[2], kKindNames[k])) s.kind = k;
        if (s.kind < 0) return fail("step kind '%s' must be action, observe or mark", fl[2]);
        if (!fl[3][0]) return fail("step without text%s", "");
        if (strlen(fl[3]) >= static_cast<size_t>(kTextLen)) return fail("step text longer than 159 bytes%s", "");
        Ascii(fl[3], s.text, sizeof(s.text));
        bool haveDo = false, haveCount = false, haveSkip = false, haveHint = false;
        char reason[200];
        for (int i = 4; i < n; ++i) {
            char *eq = strchr(fl[i], '=');
            if (!eq) return fail("field '%.40s' is not key=value", fl[i]);
            *eq = 0;
            char *key = fl[i], *val = eq + 1;
            Trim(key);
            Trim(val);
            if (!_stricmp(key, "do")) {
                if (haveDo) return fail("do= twice%s", "");
                haveDo = true;
                if (s.kind != kKindAction) return fail("do= only in an action step%s", "");
                if (strlen(val) > 319) return fail("do= longer than 319 characters%s", "");
                char copy[kDoLen];
                strncpy_s(copy, sizeof(copy), val, _TRUNCATE);
                int cmds = 0;
                char *ctx = nullptr;
                for (char *c = strtok_s(copy, ";", &ctx); c; c = strtok_s(nullptr, ";", &ctx)) {
                    Trim(c);
                    if (!*c) continue;
                    if (*c == '#') return fail("do= must not hold a #title%s", "");
                    if (!_strnicmp(c, "game.quit", 9) && (!c[9] || c[9] == ' ')) return fail("game.quit is never run by a flow%s", "");
                    ++cmds;
                }
                if (!cmds) return fail("do= without a command%s", "");
                if (cmds > kMaxCmds) return fail("do= with more than 12 commands%s", "");
                strncpy_s(s.cmds, sizeof(s.cmds), val, _TRUNCATE);
            } else if (!_stricmp(key, "after") || !_stricmp(key, "check") || !_stricmp(key, "fail")) {
                Cond *list = !_stricmp(key, "after") ? s.after : !_stricmp(key, "check") ? s.check : s.fail;
                int *cnt = !_stricmp(key, "after") ? &s.nAfter : !_stricmp(key, "check") ? &s.nCheck : &s.nFail;
                if (*cnt >= kMaxConds) return fail("more than 4 %s= conditions", key);
                if (!ParseCond(f, val, list[*cnt], reason, sizeof(reason))) return fail("%s", reason);
                ++*cnt;
            } else if (!_stricmp(key, "count")) {
                if (haveCount) return fail("count= twice%s", "");
                haveCount = true;
                char copy[200];
                strncpy_s(copy, sizeof(copy), val, _TRUNCATE);
                char *ctx = nullptr;
                for (char *c = strtok_s(copy, ",", &ctx); c; c = strtok_s(nullptr, ",", &ctx)) {
                    Trim(c);
                    if (!*c) continue;
                    if (!ValidId(c)) return fail("bad counter id '%s' in count=", c);
                    if (s.nCount >= kMaxCount) return fail("more than 4 counters in count=%s", "");
                    strncpy_s(s.countIds[s.nCount], kIdLen, c, _TRUNCATE);
                    s.counters[s.nCount++] = -1;
                }
                if (!s.nCount) return fail("count= without a counter%s", "");
            } else if (!_stricmp(key, "skip")) {
                if (haveSkip) return fail("skip= twice%s", "");
                haveSkip = true;
                if (!*val) return fail("skip= needs a reason%s", "");
                if (strlen(val) >= static_cast<size_t>(kTextLen)) return fail("skip reason longer than 159 bytes%s", "");
                Ascii(val, s.skip, sizeof(s.skip));
            } else if (!_stricmp(key, "hint")) {
                if (haveHint) return fail("hint= twice%s", "");
                haveHint = true;
                if (strlen(val) >= static_cast<size_t>(kTextLen)) return fail("hint longer than 159 bytes%s", "");
                Ascii(val, s.hint, sizeof(s.hint));
            } else return fail("unknown key '%s' (do after check fail count skip hint)", key);
        }
        if (s.kind == kKindAction && !haveDo) return fail("an action step needs do=%s", "");
        f.steps[f.nSteps++] = s;
        return true;
    }
    return fail("unknown record '%.20s' (flow, counter, step)", fl[0]);
}

// references of steps [from, nSteps): counters / steps by id; false + reason at the first bad one (step index in *bad)
inline bool Resolve(Flow &f, int from, int *bad, char *why, size_t whySize) {
    for (int i = from; i < f.nSteps; ++i) {
        Step &s = f.steps[i];
        *bad = i;
        for (int k = 0; k < s.nCount; ++k) {
            s.counters[k] = FindCounter(f, s.countIds[k]);
            if (s.counters[k] < 0) { _snprintf_s(why, whySize, _TRUNCATE, "count=: no counter '%s'", s.countIds[k]); return false; }
        }
        Cond *lists[3] = {s.after, s.check, s.fail};
        int counts[3] = {s.nAfter, s.nCheck, s.nFail};
        for (int l = 0; l < 3; ++l)
            for (int k = 0; k < counts[l]; ++k) {
                Cond &c = lists[l][k];
                if (c.type == kCondStep || c.type == kCondDone) {
                    c.index = FindStep(f, c.ref);
                    if (c.index < 0) { _snprintf_s(why, whySize, _TRUNCATE, "no step '%s'", c.ref); return false; }
                    if (c.index == i) { _snprintf_s(why, whySize, _TRUNCATE, "step '%s' refers to itself", c.ref); return false; }
                } else if (c.type == kCondCounter) {
                    c.index = FindCounter(f, c.ref);
                    if (c.index < 0) { _snprintf_s(why, whySize, _TRUNCATE, "no counter '%s'", c.ref); return false; }
                    if (f.counters[c.index].target < 1) { _snprintf_s(why, whySize, _TRUNCATE, "counter '%s' has no target (0)", c.ref); return false; }
                }
            }
    }
    return true;
}

// the whole file text (BOM skipped); returns the number of errors (each reported through err with its line)
inline int ParseText(Flow &f, const char *text, ErrorFn err, void *ctx) {
    memset(&f, 0, sizeof(f));
    if (!strncmp(text, "\xef\xbb\xbf", 3)) text += 3;
    int lineNo = 0;
    const char *p = text;
    char why[240];
    while (*p) {
        const char *e = strchr(p, '\n');
        size_t len = e ? static_cast<size_t>(e - p) : strlen(p);
        const char *next = e ? e + 1 : p + len;
        if (len && p[len - 1] == '\r') --len;
        ++lineNo;
        char line[kMaxLine + 2];
        bool tooLong = len > static_cast<size_t>(kMaxLine);
        size_t copy = tooLong ? static_cast<size_t>(kMaxLine) : len;
        memcpy(line, p, copy);
        line[copy] = 0;
        Trim(line);
        p = next;
        if (!line[0] || line[0] == '#') continue;
        if (tooLong) { ++f.errors; if (err) err(ctx, lineNo, "line longer than 1000 characters"); continue; }
        int stepsBefore = f.nSteps;
        if (!ParseRecord(f, line, why, sizeof(why))) { ++f.errors; if (err) err(ctx, lineNo, why); continue; }
        if (f.nSteps > stepsBefore) f.steps[f.nSteps - 1].line = lineNo;
    }
    // references: every bad step is reported (and dropped)
    int i = 0;
    while (i < f.nSteps) {
        int bad = -1;
        if (Resolve(f, i, &bad, why, sizeof(why))) break;
        ++f.errors;
        if (err) err(ctx, f.steps[bad].line, why);
        for (int k = bad; k + 1 < f.nSteps; ++k) f.steps[k] = f.steps[k + 1];
        --f.nSteps;
        i = 0;                                  // indices moved: resolve again from the start
    }
    return f.errors;
}

}  // namespace truflow
