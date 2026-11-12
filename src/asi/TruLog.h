// TruLog.h - the shared log line stamp of the Tru* plugins (Q107, 12.11.2026). Own code, header only.
//
// Every log line starts with the local date and time "YYYY-MM-DD HH:MM:SS.mmm " (GetLocalTime - the one clock all
// plugins use), and the first line a process writes into its log is preceded by one session header
//   === YYYY-MM-DD HH:MM:SS.mmm <plugin> <version> session start (pid N) ===
// so a log that grows over several days can be cut per session (before Q107 the lines had the time only, and lines of
// an earlier day were read as today's). Readers accept both forms: an optional "YYYY-MM-DD " before "HH:MM:SS.mmm ".
#pragma once
#include <windows.h>
#include <stdio.h>
#include <string.h>

// "YYYY-MM-DD HH:MM:SS.mmm " (with the trailing space) into out; returns the length (< 0 = cut)
inline int TruLogStamp(char *out, size_t size) {
    SYSTEMTIME t;
    GetLocalTime(&t);
    return _snprintf_s(out, size, _TRUNCATE, "%04d-%02d-%02d %02d:%02d:%02d.%03d ", t.wYear, t.wMonth, t.wDay, t.wHour,
                       t.wMinute, t.wSecond, t.wMilliseconds);
}

// the version token of a version text: "TruMenu 0.22.29 (...)" / "0.3" -> the first word that starts with a digit
inline void TruLogVersionWord(const char *text, char *out, size_t size) {
    out[0] = 0;
    for (const char *p = text; p && *p; ++p) {
        if ((p == text || p[-1] == ' ') && *p >= '0' && *p <= '9') {
            size_t n = 0;
            while (p[n] && p[n] != ' ' && n + 1 < size) ++n;
            memcpy(out, p, n);
            out[n] = 0;
            return;
        }
    }
    strncpy_s(out, size, "?", _TRUNCATE);
}

// the session header line (without line end) into out; returns the length (< 0 = cut)
inline int TruLogHeader(char *out, size_t size, const char *plugin, const char *versionText) {
    char stamp[32], version[32];
    TruLogStamp(stamp, sizeof(stamp));
    size_t len = strlen(stamp);
    if (len && stamp[len - 1] == ' ') stamp[len - 1] = 0;
    TruLogVersionWord(versionText, version, sizeof(version));
    return _snprintf_s(out, size, _TRUNCATE, "=== %s %s %s session start (pid %lu) ===", stamp, plugin, version,
                       GetCurrentProcessId());
}

// once per process, before the first line goes into the opened log <f> (callers hold their log lock);
// binary = the file is opened "ab" (the line end is written as CR LF by hand)
inline void TruLogSessionStart(FILE *f, const char *plugin, const char *versionText, bool binary = false) {
    static bool written = false;
    if (written || !f) return;
    written = true;
    char line[160];
    if (TruLogHeader(line, sizeof(line), plugin, versionText) > 0) {
        fputs(line, f);
        fputs(binary ? "\r\n" : "\n", f);
    }
}
