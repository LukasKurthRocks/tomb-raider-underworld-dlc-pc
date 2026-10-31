// TruDlc2Player.asi - DLC 2 "Lara's Shadow": make the doppelganger the player object, as the Xbox title update (TU)
// does, for the PC tru.exe (Steam, image base 0x400000).
//
// How the Xbox TU gets object 857 doppelganger_casual (and with it object 858 player_tru_dlc2_extension) loaded:
//   1. data: the mission screen starts dlc_level2_start without costume selection (TU generalbank script 134; PC
//      script 104 - tools/dlc2_player_fix.py);
//   2. exe, TU 0x82297d30 GAMELOOP_LevelLoadAndInit (retail 0x8229b3f0 = PC tru+0x1de2b0): after the costume name is
//      chosen (chosen costume, else the unit's default - dlc_level2_start: object 11 lara_doppelganger), the TU added
//          if (strcmp(name, "lara_doppelganger") == 0) { name = "doppelganger_casual"; costume id = id of name; }
//      before GAMELOOP_RequestPlayerCostumeLoad(name) (TU 0x82297a88);
//   3. exe data, TU player type table 0x8275ae38 (records {name, init, f2..f6}; an object's type is the record whose
//      name equals the object's name, PC tru+0x1bf0e0): the TU added the record "doppelganger_casual" {init
//      DoppelgangerInit 0x82412c48, f2..f6 the player's}. The PC table (0x8aba28) has no such record - an object of
//      that name would get type -1, i.e. no player functions at all;
//   4. TU 0x82412c48 DoppelgangerInit: base player init (TU 0x82412ca0 = PC tru+0x321f80), then if the instance flag
//      0x20000 at +0x14 is clear, gameTracker+0x1244 = 1 ("DoppelgangerInit finished");
//   5. object 857's child id list (chart DTP +0x48) holds 858, so the object loader loads the extension with it (data;
//      tools/dlc2_player_fix.py ids fixes two base ids of that list).
//
// This plugin translates 2-4:
//   * costume: a 6-byte detour at tru+0x1de3a3 (push esi; call print - all costume paths meet there with esi = the
//     name, right before the id lookup tru+0x1bf770 and the costume load request tru+0x1c1760) applies the TU's
//     substitution; the PC then computes the id from the new name exactly as the TU's 0x82297a88 does.
//   * type table: a copy of the PC table with the TU's record appended after the last PC record (PC indices 0-38
//     unchanged; the TU inserted it at 35 and shifted four debug records - the PC code keeps its own indices), the 11
//     code operands that address the table pointed at the copy (tru+0x1bf00a .. 0x1c547b, all checked first).
//   * DoppelgangerInit: base init tru+0x321f80, then the flag; the PC game tracker has no +0x1244 field, the plugin
//     keeps the flag (export TruDlc2PlayerDoppelganger) for later readers (dlc2data f0, TU-only code - not on PC).
// Every patched byte is compared with the expected code / data first; on a mismatch that part is left alone and the
// reason is logged. Options: TruDlc2Player.ini, log TruDlc2Player.log.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>

namespace {

const DWORD kImageBase = 0x00400000;

// ---- costume substitution (TU 0x82297d30) ----
const DWORD kLevelLoadInit = 0x005de2b0;   // PC GAMELOOP_LevelLoadAndInit
const BYTE kLevelLoadInitBytes[] = {0x55, 0x8b, 0x6c, 0x24, 0x08, 0x55, 0xe8, 0xe5, 0x74, 0x06, 0x00};
const DWORD kCostumeSite = 0x005de3a3;     // push esi; call 6457A0h | push esi; call 5BF770h; push eax; mov [0E7F1C8h],eax
const BYTE kCostumeSiteBytes[] = {0x56, 0xe8, 0xf7, 0x73, 0x06, 0x00, 0x56, 0xe8, 0xc1, 0x13, 0xfe, 0xff,
                                  0x50, 0xa3, 0xc8, 0xf1, 0xe7, 0x00};
const DWORD kCostumeBack = 0x005de3a9;     // continue at the id lookup
const DWORD kPrint = 0x006457a0;           // debug print (a plain ret in the retail build)
const DWORD kGameData = 0x00c59264;        // pointer: +0x1f4 mode, +0x20c / +0x210 chosen costume (object id)
const DWORD kCostumeId = 0x00e7f1c8;       // costume object id written by the PC after the lookup (TU 0x82efb598)
const char kFromName[] = "lara_doppelganger";
const char kToName[] = "doppelganger_casual";

// ---- player type table (TU 0x8275ae38, record 35 "doppelganger_casual") ----
const DWORD kTypeTable = 0x008aba28;       // 39 records {name, init, f2..f6} + a zero record
const int kTypeCount = 39;
struct TypeRec { const char *name; DWORD init, f[5]; };
struct Operand { DWORD at, value; };       // imm32 operands that address the table (instruction operand address)
const Operand kTypeOperands[] = {
    {0x005bf00a, 0x008aba34}, {0x005bf03a, 0x008aba40}, {0x005bf06a, 0x008aba30}, {0x005bf09a, 0x008aba38},
    {0x005bf0ca, 0x008aba3c}, {0x005bf123, 0x008aba28}, {0x005bf12a, 0x008aba28}, {0x005bf14f, 0x008aba28},
    {0x005bf157, 0x008aba28}, {0x005bf169, 0x008aba28}, {0x005c547b, 0x008aba2c}};
const int kTypeOperandCount = sizeof(kTypeOperands) / sizeof(kTypeOperands[0]);
const DWORD kBaseInit = 0x00721f80;        // PC player init (TU 0x82412ca0): push ebp; mov ebp,esp; and esp,-16
const BYTE kBaseInitBytes[] = {0x55, 0x8b, 0xec, 0x83, 0xe4, 0xf0, 0x83, 0xec, 0x24, 0x8b, 0x45, 0x0c};
const DWORD kPlayerFn[5] = {0x007228e0, 0x006ee4b0, 0x00709fd0, 0x0071ffe0, 0x0071bfa0};   // f2..f6 of every player record

// options (TruDlc2Player.ini, section [Dlc2Player])
int g_enabled = 1, g_logLevel = 1, g_costume = 1, g_typeRecord = 1;

char g_logPath[MAX_PATH];
CRITICAL_SECTION g_logLock;
TypeRec g_types[kTypeCount + 2];           // PC records, the TU record, the zero record
volatile LONG g_doppelganger = 0;          // TU gameTracker+0x1244
volatile LONG g_costumeCalls = 0;

void Log(int level, const char *fmt, ...) {
    if (level > g_logLevel || !g_logPath[0]) return;
    char line[600];
    SYSTEMTIME t;
    GetLocalTime(&t);
    int n = _snprintf_s(line, sizeof(line), _TRUNCATE, "%02d:%02d:%02d.%03d ", t.wHour, t.wMinute, t.wSecond,
                        t.wMilliseconds);
    va_list ap;
    va_start(ap, fmt);
    if (n > 0) _vsnprintf_s(line + n, sizeof(line) - n, _TRUNCATE, fmt, ap);
    va_end(ap);
    EnterCriticalSection(&g_logLock);
    FILE *f = nullptr;
    if (fopen_s(&f, g_logPath, "a") == 0 && f) {
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

bool ReadWord(DWORD address, WORD *value) {
    __try {
        *value = *reinterpret_cast<const WORD *>(address);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool SafeName(const char *p, char *out, size_t size) {
    __try {
        size_t i = 0;
        for (; i + 1 < size && p[i]; ++i) out[i] = p[i];
        out[i] = 0;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        out[0] = 0;
        return false;
    }
}

bool WriteCode(DWORD address, const void *bytes, size_t length) {
    DWORD old = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(address), length, PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "VirtualProtect failed (%lu) at 0x%08lx", GetLastError(), address);
        return false;
    }
    memcpy(reinterpret_cast<void *>(address), bytes, length);
    DWORD dummy = 0;
    VirtualProtect(reinterpret_cast<void *>(address), length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(address), length);
    return true;
}

// ---------------------------------------------------------------------------------------------------------------
// costume: TU 0x82297d30, the added name test before GAMELOOP_RequestPlayerCostumeLoad
extern "C" const char *__cdecl ChooseCostume(const char *name) {
    LONG call = InterlockedIncrement(&g_costumeCalls);
    char shown[64];
    SafeName(name ? name : "", shown, sizeof(shown));
    DWORD game = 0;
    WORD mode = 0, chosen0 = 0, chosen1 = 0;
    if (ReadDword(kGameData, &game) && game) {
        ReadWord(game + 0x1f4, &mode);
        ReadWord(game + 0x20c, &chosen0);
        ReadWord(game + 0x210, &chosen1);
    }
    const char *result = name;
    if (g_costume && name && strcmp(shown, kFromName) == 0) result = kToName;
    Log(1, "level load %ld: costume \"%s\"%s%s (game data +0x1f4 %u, chosen +0x20c %u / +0x210 %u)", call, shown,
        result != name ? " -> " : "", result != name ? kToName : "", mode, chosen0, chosen1);
    return result;
}

__declspec(naked) void CostumeDetour() {
    __asm {
        pushad
        push esi
        call ChooseCostume
        add esp, 4
        mov [esp + 4], eax        // saved esi in the pushad frame
        popad
        push esi                  // the two replaced instructions: push esi; call print
        mov eax, kPrint
        call eax
        mov eax, kCostumeBack     // eax is overwritten by the id lookup that follows
        jmp eax
    }
}

bool PatchCostume() {
    if (!BytesAt(kLevelLoadInit, kLevelLoadInitBytes, sizeof(kLevelLoadInitBytes)) ||
        !BytesAt(kCostumeSite, kCostumeSiteBytes, sizeof(kCostumeSiteBytes))) {
        Log(0, "costume: GAMELOOP_LevelLoadAndInit at 0x%08lx / 0x%08lx does not match - not patched", kLevelLoadInit,
            kCostumeSite);
        return false;
    }
    BYTE jmp[6] = {0xe9, 0, 0, 0, 0, 0x90};
    DWORD rel = reinterpret_cast<DWORD>(&CostumeDetour) - (kCostumeSite + 5);
    memcpy(jmp + 1, &rel, 4);
    if (!WriteCode(kCostumeSite, jmp, sizeof(jmp))) return false;
    Log(1, "costume: \"%s\" -> \"%s\" at level load (detour at 0x%08lx)", kFromName, kToName, kCostumeSite);
    return true;
}

// ---------------------------------------------------------------------------------------------------------------
// DoppelgangerInit (TU 0x82412c48), called by the object init (PC tru+0x1c5489) as init(instance, 0E7F088h)
typedef void(__cdecl *InitFn)(void *, void *);
extern "C" void __cdecl DoppelgangerInit(void *instance, void *arg) {
    reinterpret_cast<InitFn>(kBaseInit)(instance, arg);
    DWORD flags = 0;
    if (ReadDword(reinterpret_cast<DWORD>(instance) + 0x14, &flags) && !(flags & 0x20000)) {
        if (InterlockedExchange(&g_doppelganger, 1) == 0)
            Log(1, "DoppelgangerInit finished (instance 0x%08lx)", reinterpret_cast<DWORD>(instance));
    }
}

bool PatchTypeTable() {
    if (!BytesAt(kBaseInit, kBaseInitBytes, sizeof(kBaseInitBytes))) {
        Log(0, "type table: player init 0x%08lx does not match - not patched", kBaseInit);
        return false;
    }
    const TypeRec *t = reinterpret_cast<const TypeRec *>(kTypeTable);
    int n = 0;
    for (; n <= kTypeCount && t[n].name; ++n) {
        char nm[40];
        SafeName(t[n].name, nm, sizeof(nm));
        if (strcmp(nm, kToName) == 0) { Log(0, "type table: \"%s\" already present - not patched", kToName); return false; }
    }
    char last[40];
    SafeName(t[kTypeCount - 1].name, last, sizeof(last));
    if (n != kTypeCount || strcmp(last, "lara_placeholder") != 0) {
        Log(0, "type table at 0x%08lx: %d records, last \"%s\" (expected 39, lara_placeholder) - not patched", kTypeTable,
            n, last);
        return false;
    }
    // the player records (e.g. 2 lara_casual) carry the init / f2..f6 the TU record uses
    if (t[2].init != kBaseInit || memcmp(t[2].f, kPlayerFn, sizeof(kPlayerFn)) != 0) {
        Log(0, "type table: record 2 is not the player record expected - not patched");
        return false;
    }
    for (int i = 0; i < kTypeOperandCount; ++i) {
        DWORD v = 0;
        if (!ReadDword(kTypeOperands[i].at, &v) || v != kTypeOperands[i].value) {
            Log(0, "type table: operand at 0x%08lx is 0x%08lx, expected 0x%08lx - not patched", kTypeOperands[i].at, v,
                kTypeOperands[i].value);
            return false;
        }
    }
    memcpy(g_types, t, sizeof(TypeRec) * kTypeCount);
    g_types[kTypeCount].name = kToName;
    g_types[kTypeCount].init = reinterpret_cast<DWORD>(&DoppelgangerInit);
    memcpy(g_types[kTypeCount].f, kPlayerFn, sizeof(kPlayerFn));
    memset(&g_types[kTypeCount + 1], 0, sizeof(TypeRec));
    DWORD base = reinterpret_cast<DWORD>(g_types);
    int done = 0;
    for (; done < kTypeOperandCount; ++done) {
        DWORD v = base + (kTypeOperands[done].value - kTypeTable);
        if (!WriteCode(kTypeOperands[done].at, &v, 4)) break;
    }
    if (done != kTypeOperandCount) {      // put back what was changed
        for (int i = 0; i < done; ++i) WriteCode(kTypeOperands[i].at, &kTypeOperands[i].value, 4);
        Log(0, "type table: patch incomplete - original operands restored");
        return false;
    }
    Log(1, "type table: record %d \"%s\" (init DoppelgangerInit 0x%08lx, f2..f6 of the player) added; copy at 0x%08lx, "
           "%d operands moved", kTypeCount, kToName, g_types[kTypeCount].init, base, kTypeOperandCount);
    return true;
}

void ReadOptions(const char *dir) {
    char ini[MAX_PATH];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruDlc2Player.ini", dir);
    g_enabled = GetPrivateProfileIntA("Dlc2Player", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("Dlc2Player", "LogLevel", 1, ini);
    g_costume = GetPrivateProfileIntA("Dlc2Player", "Costume", 1, ini);
    g_typeRecord = GetPrivateProfileIntA("Dlc2Player", "TypeRecord", 1, ini);
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruDlc2Player.log", dir);
    ReadOptions(dir);
    Log(1, "TruDlc2Player 0.1 loaded (enabled %d, log level %d, costume %d, type record %d)", g_enabled, g_logLevel,
        g_costume, g_typeRecord);
    if (!g_enabled) { Log(1, "disabled by TruDlc2Player.ini - nothing patched"); return; }
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - not patched", base, kImageBase); return; }
    // the record first: a substituted costume without its type record would be an object without player functions
    bool types = g_typeRecord ? PatchTypeTable() : false;
    if (g_costume) {
        if (types) PatchCostume();
        else Log(0, "costume: not patched because the type record \"%s\" is missing (an object of that name would "
                    "get no player functions)", kToName);
    }
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

// exported: plugin identification, and the TU's gameTracker+0x1244 for other plugins (1 after DoppelgangerInit)
extern "C" __declspec(dllexport) const char *TruDlc2PlayerVersion() {
    return "TruDlc2Player 0.1 (DLC 2 doppelganger player object)";
}

extern "C" __declspec(dllexport) int TruDlc2PlayerDoppelganger() {
    return g_doppelganger ? 1 : 0;
}
