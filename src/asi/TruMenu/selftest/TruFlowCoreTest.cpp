// TruFlowCoreTest.cpp - offline check of TruFlowCore.h (TruMenu 0.11 flow file parser + pattern matcher).
// Not part of TruMenu.asi. Build (x86, the same compiler as Build-TruAsi.ps1):
//   cl /nologo /O2 /MT /W4 /EHsc TruFlowCoreTest.cpp /Fe<out>\TruFlowCoreTest.exe
// Usage:
//   TruFlowCoreTest parse <flow file> <out file>    normalized dump of the parsed flow (records, watches, error lines)
//   TruFlowCoreTest match <cases file> <out file>   per line "pattern<TAB>text" -> "1" / "0" / "E" (pattern refused)
//   TruFlowCoreTest watch <flow file> <log file> <out file>   per log line the indices of the watches that match
// The workbench test (ClaudeWerkbank\tru-flow-test\Test-FlowRunner.ps1) compares the output with the PowerShell parser
// (Read-TruFlowFile of Invoke-TruTestRun.ps1) and with .NET Regex on the same cases.
#define _CRT_SECURE_NO_WARNINGS
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../TruFlowCore.h"

using namespace truflow;

static char *ReadAll(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return nullptr;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *b = static_cast<char *>(malloc(static_cast<size_t>(n) + 1));
    size_t got = fread(b, 1, static_cast<size_t>(n), f);
    b[got] = 0;
    fclose(f);
    return b;
}

static FILE *g_out = nullptr;
static void OnError(void *, int line, const char *message) { fprintf(g_out, "error line=%d %s\n", line, message); }

static void PutConds(const char *name, const Cond *c, int n) {
    fprintf(g_out, " %s=", name);
    for (int i = 0; i < n; ++i) {
        if (i) fputc(';', g_out);
        if (c[i].type == kCondWatch) fprintf(g_out, "watch:%d", c[i].index);
        else fprintf(g_out, "%s:%s", kCondNames[c[i].type], c[i].ref);
    }
}

static Flow g_flow;

static int Parse(const char *in, const char *out) {
    char *text = ReadAll(in);
    if (!text) { fprintf(stderr, "cannot read %s\n", in); return 2; }
    g_out = fopen(out, "wb");
    if (!g_out) return 2;
    ParseText(g_flow, text, OnError, nullptr);
    const Flow &f = g_flow;
    if (f.hasHeader) fprintf(g_out, "flow id=%s title=%s\n", f.id, f.title);
    for (int i = 0; i < f.nCounters; ++i) {
        const Counter &c = f.counters[i];
        fprintf(g_out, "counter %d id=%s source=%s arg=%s target=%d watch=%d text=%s\n", i, c.id, kSrcNames[c.source],
                c.arg, c.target, c.watch, c.text);
    }
    for (int i = 0; i < f.nWatches; ++i)
        fprintf(g_out, "watch %d file=%s cat=%s pattern=%s\n", i, f.watches[i].file, f.watches[i].cat, f.watches[i].source);
    for (int i = 0; i < f.nSteps; ++i) {
        const Step &s = f.steps[i];
        fprintf(g_out, "step %d id=%s kind=%s line=%d text=%s hint=%s do=%s skip=%s count=", i, s.id, kKindNames[s.kind],
                s.line, s.text, s.hint, s.cmds, s.skip);
        for (int k = 0; k < s.nCount; ++k) fprintf(g_out, "%s%s", k ? "," : "", f.counters[s.counters[k]].id);
        PutConds("after", s.after, s.nAfter);
        PutConds("check", s.check, s.nCheck);
        PutConds("fail", s.fail, s.nFail);
        fputc('\n', g_out);
    }
    fprintf(g_out, "errors=%d\n", f.errors);
    fclose(g_out);
    free(text);
    return 0;
}

static int Match(const char *in, const char *out) {
    char *text = ReadAll(in);
    if (!text) { fprintf(stderr, "cannot read %s\n", in); return 2; }
    FILE *o = fopen(out, "wb");
    if (!o) return 2;
    char *ctx = nullptr;
    static Pattern p;
    for (char *line = strtok_s(text, "\n", &ctx); line; line = strtok_s(nullptr, "\n", &ctx)) {
        size_t n = strlen(line);
        if (n && line[n - 1] == '\r') line[--n] = 0;
        char *tab = strchr(line, '\t');
        if (!tab) { fprintf(o, "E\n"); continue; }
        *tab = 0;
        char why[200];
        if (!CompilePattern(line, p, why, sizeof(why))) { fprintf(o, "E\n"); continue; }
        fprintf(o, "%d\n", PatternMatches(p, tab + 1) ? 1 : 0);
    }
    fclose(o);
    free(text);
    return 0;
}

static int WatchLog(const char *flowPath, const char *logPath, const char *out) {
    char *text = ReadAll(flowPath);
    char *log = ReadAll(logPath);
    if (!text || !log) { fprintf(stderr, "cannot read input\n"); return 2; }
    g_out = stderr;
    ParseText(g_flow, text, nullptr, nullptr);
    FILE *o = fopen(out, "wb");
    if (!o) return 2;
    char *ctx = nullptr;
    for (char *line = strtok_s(log, "\n", &ctx); line; line = strtok_s(nullptr, "\n", &ctx)) {
        size_t n = strlen(line);
        if (n && line[n - 1] == '\r') line[--n] = 0;
        bool any = false;
        for (int w = 0; w < g_flow.nWatches; ++w)
            if (WatchMatches(g_flow.watches[w], line)) { fprintf(o, "%s%d", any ? "," : "", w); any = true; }
        fputc('\n', o);
    }
    fclose(o);
    free(text);
    free(log);
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 4 && !strcmp(argv[1], "parse")) return Parse(argv[2], argv[3]);
    if (argc == 4 && !strcmp(argv[1], "match")) return Match(argv[2], argv[3]);
    if (argc == 5 && !strcmp(argv[1], "watch")) return WatchLog(argv[2], argv[3], argv[4]);
    fprintf(stderr, "usage: TruFlowCoreTest parse <flow> <out> | match <cases> <out> | watch <flow> <log> <out>\n");
    return 1;
}
