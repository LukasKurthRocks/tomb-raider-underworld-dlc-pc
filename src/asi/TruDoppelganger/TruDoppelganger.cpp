// TruDoppelganger.asi - DLC 2 "Lara's Shadow" player (the doppelganger) for the PC tru.exe (Steam, image base 0x400000).
//
// Lara's moves run through a data-driven state machine. Its builder (Xbox TU 0x82489500, retail 0x82483508, PC
// tru+0x3872f0) fills three id trees once, from three static tables: conditions {id, group, function}, activities
// {id, function} and states {id, 6 functions}; each table ends with an id-0 record that is inserted as well. The Xbox
// title update changed only the tables, not the builder or the handler functions (tools/xbox_func_diff.py: equal),
// and added (tools/xbox_cond_table.py, docs Befund-Felsrinne "DoppelgangerInit"):
//
//   conditions 1048-1056, 2005, 2006, 2013 (group 2000), 2401 (group 2400) -> SCCondFunction_Default
//   activities 286, 1009, 1040-1045 -> TU 0x82488dc0, 1039 -> TU 0x82488d28
//   states     243-245, 1017-1020, 2102 -> TU 0x82482600 in all six slots
//
// The DLC 2 player data (player_tru_dlc2_extension.drm) uses some of them (1018, 1020, 1050, 245 next to 608), the PC
// exe (= Xbox retail tables) registers none. The PC handler of each TU function is the one the PC table holds at the
// ids that share that function on the Xbox (paired by id, one PC function each):
//
//   TU 0x82484db0 SCCondFunction_Default -> PC tru+0x382140 (282 shared ids)
//   TU 0x82488dc0 (b 0x824843c8)         -> PC tru+0x386f30 (243 shared ids)
//   TU 0x82488d28                        -> PC tru+0x384cf0 (79 shared ids)
//   TU 0x82482600                        -> PC tru+0x381d10 (every PC state)
//
// The plugin copies the three PC tables, appends the title update's records (TU order) before the id-0 record and
// points the builder's three `push table` operands at the copies - the builder itself runs unchanged. Every address,
// the builder code, the table sizes and the handlers at known ids are checked first; on any mismatch (or if the
// builder has already run) nothing is patched and the reason is logged. Options: TruDoppelganger.ini.
//
// Not ported: DoppelgangerInit (TU 0x82412c48, init of the TU-only player object type "doppelganger_casual": after the
// base init, if the object's flag bit 0x20000 at +0x14 is clear, gameTracker+0x1244 = 1). Its only readers are the
// dlc2data native f0 and TU-only code that the PC exe does not have, so the flag would change nothing yet.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include "../TruLog.h"                      // Q107: date + time in every log line, session header
extern "C" __declspec(dllexport) const char *TruDoppelgangerVersion(); // Q107 session header (defined at the end)

namespace {

const DWORD kImageBase = 0x00400000;
const DWORD kBuilderCode = 0x00787341;   // push esi; push 8B57E0h; ... call 784FE0h (the three table registrations)
const BYTE kBuilderBytes[] = {0x56, 0x68, 0xe0, 0x57, 0x8b, 0x00, 0x8b, 0xc8, 0xa3, 0x30, 0xf0, 0xfa, 0x00,
                              0xe8, 0x8d, 0xdb, 0xff, 0xff, 0x8b, 0x0d, 0x30, 0xf0, 0xfa, 0x00, 0x68, 0x50, 0x66,
                              0x8b, 0x00, 0xe8, 0xfd, 0xdb, 0xff, 0xff, 0x8b, 0x0d, 0x30, 0xf0, 0xfa, 0x00, 0x68,
                              0x00, 0x42, 0x8b, 0x00, 0xe8, 0x6d, 0xdc, 0xff, 0xff};
const DWORD kBuilderGuard = 0x007872fb;  // mov eax,[0FAF030h]; test eax,eax; jne (built once)
const BYTE kBuilderGuardBytes[] = {0xa1, 0x30, 0xf0, 0xfa, 0x00, 0x85, 0xc0, 0x0f, 0x85};
const DWORD kSingleton = 0x00faf030;     // the state-machine registry, 0 until the builder ran
const DWORD kPushCond = 0x00787343, kPushAct = 0x0078735a, kPushState = 0x0078736a;   // imm32 of the three pushes
const DWORD kCondTable = 0x008b57e0, kActTable = 0x008b6650, kStateTable = 0x008b4200;
const int kCondCount = 307, kActCount = 332, kStateCount = 199;   // records before the id-0 record (2008 Steam build)

// PC handlers (see the header) and their first bytes
const DWORD kCondDefault = 0x00782140;   // sub esp,204h; mov eax,[8BD7E8h]; xor eax,esp
const DWORD kActDefault = 0x00786f30;    // mov eax,[esp+8]; mov ecx,[esp+4]; push eax
const DWORD kActMove = 0x00784cf0;       // sub esp,8; mov eax,[8BD7E8h]; xor eax,esp
const DWORD kStateDefault = 0x00781d10;  // sub esp,204h; mov eax,[8BD7E8h]; xor eax,esp
const BYTE kCondDefaultBytes[] = {0x81, 0xec, 0x04, 0x02, 0x00, 0x00, 0xa1, 0xe8, 0xd7, 0x8b, 0x00, 0x33, 0xc4};
const BYTE kActDefaultBytes[] = {0x8b, 0x44, 0x24, 0x08, 0x8b, 0x4c, 0x24, 0x04, 0x50};
const BYTE kActMoveBytes[] = {0x83, 0xec, 0x08, 0xa1, 0xe8, 0xd7, 0x8b, 0x00, 0x33, 0xc4};
const BYTE kStateDefaultBytes[] = {0x81, 0xec, 0x04, 0x02, 0x00, 0x00, 0xa1, 0xe8, 0xd7, 0x8b, 0x00, 0x33, 0xc4};

struct CondRec { DWORD id, group, fn; };
struct ActRec { DWORD id, fn; };
struct StateRec { DWORD id, fn[6]; };

// title-update records missing on PC, in the TU tables' order (Xbox TU 0x82755f78 / 0x82756e88 / 0x827548b8)
const CondRec kNewCond[] = {
    {1055, 2000, kCondDefault}, {1056, 2000, kCondDefault}, {1048, 2000, kCondDefault}, {1049, 2000, kCondDefault},
    {1050, 2000, kCondDefault}, {1051, 2000, kCondDefault}, {1052, 2000, kCondDefault}, {1053, 2000, kCondDefault},
    {1054, 2000, kCondDefault}, {2005, 2000, kCondDefault}, {2013, 2000, kCondDefault}, {2006, 2000, kCondDefault},
    {2401, 2400, kCondDefault}};
const ActRec kNewAct[] = {
    {286, kActDefault}, {1009, kActDefault}, {1039, kActMove}, {1040, kActDefault}, {1041, kActDefault},
    {1042, kActDefault}, {1043, kActDefault}, {1044, kActDefault}, {1045, kActDefault}};
const DWORD kNewStateIds[] = {243, 244, 245, 1019, 1017, 1018, 1020, 2102};
const int kNewCondCount = sizeof(kNewCond) / sizeof(kNewCond[0]);
const int kNewActCount = sizeof(kNewAct) / sizeof(kNewAct[0]);
const int kNewStateCount = sizeof(kNewStateIds) / sizeof(kNewStateIds[0]);

// spot checks: PC ids whose handler is the one reused above (from the PC tables)
const DWORD kCheckCondId = 21, kCheckActDefaultId = 101, kCheckActMoveId = 203, kCheckStateId = 2;

// options (TruDoppelganger.ini, section [Doppelganger])
int g_enabled = 1;
int g_logLevel = 1;                      // 0 errors, 1 info, 2 + every added id, 3 + check details
int g_addConditions = 1, g_addActivities = 1, g_addStates = 1;

char g_logPath[MAX_PATH];
CRITICAL_SECTION g_logLock;

// the extended copies the builder reads instead of the originals
CondRec g_cond[kCondCount + kNewCondCount + 1];
ActRec g_act[kActCount + kNewActCount + 1];
StateRec g_state[kStateCount + kNewStateCount + 1];

void Log(int level, const char *fmt, ...) {
    if (level > g_logLevel || !g_logPath[0]) return;
    char line[512];
    int n = TruLogStamp(line, sizeof(line));     // Q107: "YYYY-MM-DD HH:MM:SS.mmm "
    va_list ap;
    va_start(ap, fmt);
    if (n > 0) _vsnprintf_s(line + n, sizeof(line) - n, _TRUNCATE, fmt, ap);
    va_end(ap);
    EnterCriticalSection(&g_logLock);
    FILE *f = nullptr;
    if (fopen_s(&f, g_logPath, "a") == 0 && f) {
        TruLogSessionStart(f, "TruDoppelganger", TruDoppelgangerVersion());
        fputs(line, f);
        fputs("\n", f);
        fclose(f);
    }
    LeaveCriticalSection(&g_logLock);
}

bool BytesAt(DWORD address, const BYTE *expected, size_t length) {
    __try {
        return memcmp(reinterpret_cast<const void *>(address), expected, length) == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool ReadDword(DWORD address, DWORD *value) {
    __try {
        *value = *reinterpret_cast<const DWORD *>(address);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// number of records before the id-0 record (stride in DWORDs), -1 if unreadable or longer than limit
int CountRecords(DWORD table, int stride, int limit) {
    for (int i = 0; i <= limit; ++i) {
        DWORD id = 0;
        if (!ReadDword(table + i * stride * 4, &id)) return -1;
        if (id == 0) return i;
    }
    return -1;
}

// handler slot `slot` of the record with this id, 0 if the id is not in the table
DWORD HandlerOf(DWORD table, int stride, int count, DWORD id, int slot) {
    const DWORD *t = reinterpret_cast<const DWORD *>(table);
    for (int i = 0; i < count; ++i)
        if (t[i * stride] == id) return t[i * stride + slot];
    return 0;
}

bool HasId(DWORD table, int stride, int count, DWORD id) {
    const DWORD *t = reinterpret_cast<const DWORD *>(table);
    for (int i = 0; i < count; ++i)
        if (t[i * stride] == id) return true;
    return false;
}

bool CheckGame() {
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - not patched", base, kImageBase); return false; }
    if (!BytesAt(kBuilderGuard, kBuilderGuardBytes, sizeof(kBuilderGuardBytes)) ||
        !BytesAt(kBuilderCode, kBuilderBytes, sizeof(kBuilderBytes))) {
        Log(0, "state-machine builder at 0x%08lx does not match (other tru.exe build, or patched) - not patched", kBuilderCode);
        return false;
    }
    DWORD registry = 1;
    if (!ReadDword(kSingleton, &registry) || registry != 0) {
        Log(0, "the builder has already run (registry 0x%08lx) - too late to add ids, not patched", registry);
        return false;
    }
    int nc = CountRecords(kCondTable, 3, 4096), na = CountRecords(kActTable, 2, 4096), ns = CountRecords(kStateTable, 7, 4096);
    if (nc != kCondCount || na != kActCount || ns != kStateCount) {
        Log(0, "table sizes %d / %d / %d, expected %d / %d / %d - not patched", nc, na, ns, kCondCount, kActCount, kStateCount);
        return false;
    }
    if (HandlerOf(kCondTable, 3, nc, kCheckCondId, 2) != kCondDefault ||
        HandlerOf(kActTable, 2, na, kCheckActDefaultId, 1) != kActDefault ||
        HandlerOf(kActTable, 2, na, kCheckActMoveId, 1) != kActMove) {
        Log(0, "reused handlers not found at the expected ids - not patched");
        return false;
    }
    for (int k = 1; k <= 6; ++k)
        if (HandlerOf(kStateTable, 7, ns, kCheckStateId, k) != kStateDefault) {
            Log(0, "state %lu slot %d is not the default state handler - not patched", kCheckStateId, k);
            return false;
        }
    if (!BytesAt(kCondDefault, kCondDefaultBytes, sizeof(kCondDefaultBytes)) ||
        !BytesAt(kActDefault, kActDefaultBytes, sizeof(kActDefaultBytes)) ||
        !BytesAt(kActMove, kActMoveBytes, sizeof(kActMoveBytes)) ||
        !BytesAt(kStateDefault, kStateDefaultBytes, sizeof(kStateDefaultBytes))) {
        Log(0, "a reused handler's code does not match - not patched");
        return false;
    }
    for (int i = 0; i < kNewCondCount; ++i)
        if (HasId(kCondTable, 3, nc, kNewCond[i].id)) { Log(0, "condition %lu already registered - not patched", kNewCond[i].id); return false; }
    for (int i = 0; i < kNewActCount; ++i)
        if (HasId(kActTable, 2, na, kNewAct[i].id)) { Log(0, "activity %lu already registered - not patched", kNewAct[i].id); return false; }
    for (int i = 0; i < kNewStateCount; ++i)
        if (HasId(kStateTable, 7, ns, kNewStateIds[i])) { Log(0, "state %lu already registered - not patched", kNewStateIds[i]); return false; }
    Log(3, "checks passed (builder code, registry empty, table sizes, reused handlers, new ids absent)");
    return true;
}

// copies of the PC tables with the TU records inserted before the id-0 record
void BuildTables() {
    const CondRec *cond = reinterpret_cast<const CondRec *>(kCondTable);
    const ActRec *act = reinterpret_cast<const ActRec *>(kActTable);
    const StateRec *state = reinterpret_cast<const StateRec *>(kStateTable);
    int n = 0;
    for (int i = 0; i < kCondCount; ++i) g_cond[n++] = cond[i];
    if (g_addConditions)
        for (int i = 0; i < kNewCondCount; ++i) {
            g_cond[n++] = kNewCond[i];
            Log(2, "condition %lu (group %lu) -> 0x%08lx", kNewCond[i].id, kNewCond[i].group, kNewCond[i].fn);
        }
    g_cond[n] = cond[kCondCount];
    n = 0;
    for (int i = 0; i < kActCount; ++i) g_act[n++] = act[i];
    if (g_addActivities)
        for (int i = 0; i < kNewActCount; ++i) {
            g_act[n++] = kNewAct[i];
            Log(2, "activity %lu -> 0x%08lx", kNewAct[i].id, kNewAct[i].fn);
        }
    g_act[n] = act[kActCount];
    n = 0;
    for (int i = 0; i < kStateCount; ++i) g_state[n++] = state[i];
    if (g_addStates)
        for (int i = 0; i < kNewStateCount; ++i) {
            StateRec r;
            r.id = kNewStateIds[i];
            for (int k = 0; k < 6; ++k) r.fn[k] = kStateDefault;
            g_state[n++] = r;
            Log(2, "state %lu -> 0x%08lx (all six slots)", r.id, kStateDefault);
        }
    g_state[n] = state[kStateCount];
}

bool PatchPush(DWORD operand, DWORD expected, DWORD value) {
    DWORD *p = reinterpret_cast<DWORD *>(operand);
    DWORD old = 0;
    if (*p != expected) { Log(0, "push operand at 0x%08lx is 0x%08lx, expected 0x%08lx", operand, *p, expected); return false; }
    if (!VirtualProtect(p, 4, PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "VirtualProtect failed (%lu) at 0x%08lx", GetLastError(), operand);
        return false;
    }
    *p = value;
    DWORD dummy = 0;
    VirtualProtect(p, 4, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), p, 4);
    return true;
}

void ReadOptions(const char *dir) {
    char ini[MAX_PATH];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruDoppelganger.ini", dir);
    g_enabled = GetPrivateProfileIntA("Doppelganger", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("Doppelganger", "LogLevel", 1, ini);
    g_addConditions = GetPrivateProfileIntA("Doppelganger", "AddConditions", 1, ini);
    g_addActivities = GetPrivateProfileIntA("Doppelganger", "AddActivities", 1, ini);
    g_addStates = GetPrivateProfileIntA("Doppelganger", "AddStates", 1, ini);
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruDoppelganger.log", dir);
    ReadOptions(dir);
    Log(1, "TruDoppelganger loaded (enabled %d, log level %d, conditions %d, activities %d, states %d)", g_enabled,
        g_logLevel, g_addConditions, g_addActivities, g_addStates);
    if (!g_enabled) { Log(1, "disabled by TruDoppelganger.ini - nothing patched"); return; }
    if (!CheckGame()) return;
    BuildTables();
    // the builder reads the operands only when it runs (first player state machine), so the order does not matter
    bool ok = PatchPush(kPushCond, kCondTable, reinterpret_cast<DWORD>(g_cond)) &&
              PatchPush(kPushAct, kActTable, reinterpret_cast<DWORD>(g_act)) &&
              PatchPush(kPushState, kStateTable, reinterpret_cast<DWORD>(g_state));
    if (!ok) {   // put back whatever was already changed
        PatchPush(kPushCond, reinterpret_cast<DWORD>(g_cond), kCondTable);
        PatchPush(kPushAct, reinterpret_cast<DWORD>(g_act), kActTable);
        Log(0, "patch incomplete - original tables restored");
        return;
    }
    Log(1, "title-update ids registered: %d conditions, %d activities, %d states (tables at 0x%08lx / 0x%08lx / 0x%08lx)",
        g_addConditions ? kNewCondCount : 0, g_addActivities ? kNewActCount : 0, g_addStates ? kNewStateCount : 0,
        reinterpret_cast<DWORD>(g_cond), reinterpret_cast<DWORD>(g_act), reinterpret_cast<DWORD>(g_state));
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        InitializeCriticalSection(&g_logLock);
        Start(instance);
    }
    return TRUE;
}

// exported so the loader / tools can identify the plugin (the Ultimate ASI Loader needs no particular export)
extern "C" __declspec(dllexport) const char *TruDoppelgangerVersion() {
    return "TruDoppelganger 0.1 (title-update state-machine ids)";
}
