// TruRockVein.asi - DLC 2 "Lara's Shadow" rock veins for the PC tru.exe (Steam, image base 0x400000).
//
// Lara's moves run through a data-driven state machine; transitions test numbered conditions. The Xbox title update
// added two markup conditions to SCCondTest_MarkupType (Xbox TU 0x82486dd8, retail 0x82480e78; docs Befund-Felsrinne
// "step 3.4"): 607 = "the player's markup has type 23", 608 = "... type 22" - most likely the rock vein and its jump
// target. The PC exe (like the Xbox retail exe) has no case for them: its jump table sends 604-609 to the default
// "unhandled condition" case, so every state transition that needs them is false and LB/RB + A at a rock vein does
// nothing. This plugin adds the two cases with exactly the title update's logic:
//
//   Xbox TU 607 / 608: ctx == 0 -> false; markup = [ctx+0x24] ? type byte +0x4d : ([ctx+0x20] ? type byte +0x33 : -)
//                      result = (signed char)type == 23 (607) / 22 (608)
//   PC   tru+0x1be340  the same getter already exists (thiscall: [ecx+24h]->+4Dh, else [ecx+20h]->+33h, else 0)
//   PC   tru+0x382810  SCCondTest_MarkupType (cdecl; after its push ebx / push esi: [esp+14h] condition record,
//                      [esp+18h] markup flags, [esp+1Ch] the context the TU code reads)
//   PC   tru+0x382a54  jump table for ids 601-628 (index = id - 601), default case tru+0x382a19 ("unhandled
//                      condition (%d)"), common exit tru+0x382a3f (result in bl, negation flag of the record applied)
//
// The two table entries (index 6 = 607, 7 = 608) are pointed at small stubs that compute bl and jump to the common
// exit. Optionally every other "unhandled" entry is pointed at a stub that logs the id once and then runs the
// original default case - so the next missing title-update condition shows up in TruRockVein.log.
// Every address is checked against the expected bytes first; on any mismatch nothing is patched and the reason is
// logged. Loaded by the Ultimate ASI Loader the installed game ships as binkw32.dll. Options: TruRockVein.ini.
//
// 0.2 (2026-10-31) - diagnostics for the morning test (docs Befund-Felsrinne "Rock vein: why 607/608 are never
// evaluated"). 607 / 608 are not condition ids but the u16 VALUE (+4) of a condition record {u16 key, u16 id, u16
// value, u8 flags}; the record id (610..613) selects the handler from Lara's link array, which passes the record to
// SCCondTest_MarkupType. Our converted DLC 2 state chart had these values in Xbox byte order (608 -> 24578), so the
// dispatch went to the default before the jump table and the 0.1 stubs never ran. Two read-only probes, no change of
// the game's results:
//   * LogBadValues: a 5-byte detour on `sub eax,259h` at tru+0x38288d logs every markup value > 628 (except the
//     special 1000) once - with a correct chart there are none; and at LogLevel 2 the first call of each 601..628.
//   * LogDefaultConditions: a detour on the entry of the condition default handler tru+0x382140 (Xbox
//     SCCondFunction_Default 0x82484db0: formats "You must add a condition function ...", returns true) logs each
//     condition id that reaches it once, with record key / value and the agent's state name - the title-update
//     conditions Lara's own link array lacks (TU-Abdeckung.md: 1048-1056, 2005, 2006, 2013, 2401) show up here.
//
// 0.3 (2026-11-01, docs Befund-Felsrinne "Rock vein: no markup context at the wall") - live 607 / 608 ran with ctx 0:
// the PC disables every markup of type 22 / 23 when it is added (type -> flag mapper tru+0x5d70a0 = Xbox retail, only
// types 1..21; the title update 0x822a12e8 maps 22 / 23 to flag class 1). PatchMarkupTypes adds the two cases.
//
// 0.4 (2026-11-01, docs Befund-Felsrinne "Wall run: crash on entering the attach state (tru+0x1dba2d)") - with 0.3 the
// condition 608 was true and the game crashed 237 ms later in TRMarkupManager slot +0x08 (tru+0x1dba20, the wall normal
// of a box) with box = NULL. A box of flag class 1 carries none of the move bits, so on PC the attach dispatcher
// tru+0x307b90 (box = gameTracker+0xa64) finds neither slot 0 ("wall", bits 0x04480010) nor slot 1 (bits 0x61870000)
// nor bit 0x8000 true and never sets the attach box gameTracker+0xc94; the next state code reads +0xc94 = 0. The title
// update added the new types to exactly these slots (TU vtable 0x8206827c): slot 0 0x822a0bc8 "... || type == 22",
// slot 1 0x822a0c68 "... || type == 23", slot +0x08 0x822a0d08 takes the edge (cross product) path also for type 22.
// PatchSlots translates the three 1:1 (type = second markup +0x4d, else record +0x33, as the TU code reads it).
// NullBoxGuard (diagnostic, not a translation - the TU would read address 0x28 too): slot +0x08 with box 0 logs the
// return addresses (into the wrapper tru+0x1c3cc0 and its caller) and returns a zero vector instead of crashing.
//
// 0.5 (2026-11-01, live test 48j with 0.4: guard fired from tru+0x32ba5b, +0xc94 = 0, then AV in tru+0x1c39e2 with
// the same box 0) - the attach box is set by PLAYER_AttachToJumpTarget (PC tru+0x307b90 = TU 0x823fd178, unchanged),
// and the title update calls it for the new markup action 608: the markup-action selector (PC tru+0x372ca0 = TU
// 0x82463538) switches on the state parameter 0x19a; the TU added case 608 (0x82463a28: if gameTracker+0xa64 != 0 ->
// PLAYER_AttachToJumpTarget(zero vector, 0.0) and gameTracker+0xca0 = gameTracker+0xd90), every other case of
// 601..629 has the same target pattern on PC and TU. The PC sends 608 to its default ("unknown", print compiled out),
// so no attach happens and state 572 (parameter 0x1e1 = 611) reads +0xc94 = 0. PatchSelector adds the case.
// NullBoxGuard also covers tru+0x32ba40 (attach point on a box, cdecl(out, box)), the second crash site's caller.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>

namespace {

const DWORD kImageBase = 0x00400000;
const DWORD kDispatch = 0x0078288d;     // sub eax,259h; cmp eax,1Bh; ja default; jmp [table+eax*4]
const BYTE kDispatchBytes[] = {0x2d, 0x59, 0x02, 0x00, 0x00, 0x83, 0xf8, 0x1b, 0x0f, 0x87, 0x7e, 0x01, 0x00, 0x00,
                               0xff, 0x24, 0x85, 0x54, 0x2a, 0x78, 0x00};
const DWORD kTable = 0x00782a54;        // 28 entries, ids 601-628
const int kTableCount = 28;
const DWORD kDefault = 0x00782a19;      // cmp dx,3E8h ... "--- SCCondTest_MarkupType unhandled condition (%d) ---"
const BYTE kDefaultBytes[] = {0x66, 0x81, 0xfa, 0xe8, 0x03};
const DWORD kExit = 0x00782a3f;         // test byte [esi+6],1; je ...; test bl,bl; pop esi
const BYTE kExitBytes[] = {0xf6, 0x46, 0x06, 0x01, 0x74, 0x08, 0x84, 0xdb, 0x5e};
const DWORD kCtxUse = 0x007828c3;       // case 603: mov eax,[esp+1Ch]; push eax (the context argument)
const BYTE kCtxUseBytes[] = {0x8b, 0x44, 0x24, 0x1c, 0x50};
const DWORD kGetType = 0x005be340;      // markup type getter (thiscall), same logic as the TU's 607 / 608
const BYTE kGetTypeBytes[] = {0x8b, 0x41, 0x24, 0x85, 0xc0, 0x74, 0x05, 0x0f, 0xbe, 0x40, 0x4d, 0xc3,
                              0x8b, 0x49, 0x20, 0x85, 0xc9, 0x74, 0x05, 0x0f, 0xbe, 0x41, 0x33, 0xc3};
// the original table (tru.exe 2008 Steam build) - every entry is checked before anything is written
const DWORD kTableOriginal[kTableCount] = {
    0x007829da, 0x00782938, 0x007828b1, 0x00782a19, 0x00782a19, 0x00782a19, 0x00782a19, 0x00782a19,  // 601-608
    0x00782a19, 0x007828db, 0x00782923, 0x007828a2, 0x0078295a, 0x00782969, 0x00782978, 0x00782987,  // 609-616
    0x00782997, 0x007829a6, 0x00782a19, 0x007829b5, 0x00782a19, 0x00782a19, 0x007829c2, 0x007829ce,  // 617-624
    0x00782a0d, 0x00782978, 0x00782a19, 0x007828ea};                                                  // 625-628

// 0.2 probes
const DWORD kDispatchNext = 0x00782892; // cmp eax,1Bh (after the 5-byte sub eax,259h we detour)
const DWORD kCondDefault = 0x00782140;  // condition default handler: sub esp,204h; mov eax,[__security_cookie] ...
const BYTE kCondDefaultBytes[] = {0x81, 0xec, 0x04, 0x02, 0x00, 0x00, 0xa1, 0xe8, 0xd7, 0x8b, 0x00, 0x33, 0xc4,
                                  0x89, 0x84, 0x24, 0x00, 0x02, 0x00, 0x00, 0x8b, 0x84, 0x24, 0x10, 0x02, 0x00, 0x00,
                                  0x0f, 0xbf, 0x40, 0x02};   // ... mov eax,[esp+210h] (record); movsx eax,word [eax+2]
const DWORD kCondDefaultNext = 0x00782146;
// 0.3: markup type -> flag class, TRMarkupManager vtable 0x855214 slot +0x20 (called by the markup add loop
// tru+0x5ce55b for every record whose +0x28 is 0). PC = Xbox retail 0x822a42d8: types 1..21 only, any other type
// returns 0x80000000 = "Bad Markup Type, disabling markup" (the print is compiled out on PC) and the query loops skip
// a box with a negative flag word (tru+0x5ce459 js). The title update 0x822a12e8 accepts 1..23 and returns 1 for the
// two new types 22 / 23 (the DLC 2 rock-vein markup of the pistons / machine column / goo converter objects).
const DWORD kTypeFlagsSlot = 0x00855234;     // vtable 0x855214 + 0x20
const DWORD kTypeFlags = 0x005d70a0;
const BYTE kTypeFlagsBytes[] = {0x8b, 0x4c, 0x24, 0x04, 0x83, 0xc1, 0xff, 0x33, 0xc0, 0x83, 0xf9, 0x14, 0x77, 0x17,
                                0xff, 0x24, 0x8d, 0xd0, 0x70, 0x5d, 0x00, 0xb8, 0x01, 0x00, 0x00, 0x00, 0xc2, 0x04, 0x00};
const DWORD kTypeFlagsLimit = 0x005d70ab;    // imm8 of cmp ecx,14h (index = type - 1)
const DWORD kTypeFlagsTable = 0x005d70d0;    // 21 entries, then 12 bytes int3 padding
const DWORD kTypeFlagsOne = 0x005d70b5;      // mov eax,1; ret 4
const DWORD kTypeFlagsTableOriginal[21] = {
    0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5,
    0x005d70ca, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70b5, 0x005d70bd, 0x005d70bd, 0x005d70bd,
    0x005d70bd, 0x005d70bd, 0x005d70ca};
const BYTE kTypeFlagsPad[8] = {0xcc, 0xcc, 0xcc, 0xcc, 0xcc, 0xcc, 0xcc, 0xcc};
const BYTE kFormatPush[] = {0x68, 0xa8, 0x06, 0x86, 0x00};  // tru+0x382182 push "You must add a condition ..." format
const DWORD kFormatPushAt = 0x00782182;

// 0.4: TRMarkupManager vtable 0x855214 slots 0 / 1 / +0x08 (Xbox TU 0x822a0bc8 / 0x822a0c68 / 0x822a0d08)
const DWORD kSlot0At = 0x00855214, kSlot0 = 0x005d6e50;   // thiscall(mgr, box): [box+28h] & 4480010h || 0x741720(box)
const DWORD kSlot1At = 0x00855218, kSlot1 = 0x005d6e80;   // thiscall(mgr, box): [box+28h] & 61870000h || 0x733f60(box)
const DWORD kSlot8At = 0x0085521c, kSlot8 = 0x005dba20;   // thiscall(mgr, out, box, segment), ret 0Ch
const BYTE kSlot0Bytes[] = {0x8b, 0x44, 0x24, 0x04, 0xf7, 0x40, 0x28, 0x10, 0x00, 0x48, 0x04, 0x75, 0x10, 0x50, 0xe8,
                            0xbd, 0xa8, 0x16, 0x00, 0x83, 0xc4, 0x04, 0x84, 0xc0, 0x75, 0x03, 0xc2, 0x04, 0x00, 0xb0,
                            0x01, 0xc2, 0x04, 0x00};
const BYTE kSlot1Bytes[] = {0x8b, 0x44, 0x24, 0x04, 0xf7, 0x40, 0x28, 0x00, 0x00, 0x87, 0x61, 0x75, 0x10, 0x50, 0xe8,
                            0xcd, 0xd0, 0x15, 0x00, 0x83, 0xc4, 0x04, 0x84, 0xc0, 0x75, 0x03, 0xc2, 0x04, 0x00, 0xb0,
                            0x01, 0xc2, 0x04, 0x00};
// slot +0x08 entry up to the branch: ... mov ebx,[ebp+0Ch]; test dword [ebx+28h],20408000h; push esi;
// mov esi,[ebp+8]; push edi; mov edi,[ebx+20h]; je 0x5dbac8 (6 bytes at 0x5dba3c)
const BYTE kSlot8Bytes[] = {0x55, 0x8b, 0xec, 0x83, 0xe4, 0xf0, 0x83, 0xec, 0x24, 0x53, 0x8b, 0x5d, 0x0c, 0xf7, 0x43,
                            0x28, 0x00, 0x80, 0x40, 0x20, 0x56, 0x8b, 0x75, 0x08, 0x57, 0x8b, 0x7b, 0x20, 0x0f, 0x84,
                            0x86, 0x00, 0x00, 0x00};
const DWORD kSlot8Branch = 0x005dba3c;  // je 0x5dbac8 -> jmp Slot8Branch; nop
const DWORD kSlot8Edge = 0x005dba42;    // mask bits set: normal of the poly-line edge (cross product)
const DWORD kSlot8Other = 0x005dbac8;   // no mask bit: the retail fallback (player position based)
const DWORD kWrapperRet = 0x005c3cda;   // return address inside the wrapper tru+0x1c3cc0 (box in ecx)

// 0.5: markup-action selector tru+0x372ca0, second switch (values 601..629, ebx = state parameter 0x19a, esi = agent)
const DWORD kSelSwitch = 0x00772f8a;    // lea eax,[ebx-259h]; cmp eax,1Ch; ja default; movzx edx,byte [eax+77316Ch]; jmp
const BYTE kSelSwitchBytes[] = {0x8d, 0x83, 0xa7, 0xfd, 0xff, 0xff, 0x83, 0xf8, 0x1c, 0x0f, 0x87, 0x01, 0x01, 0x00,
                                0x00, 0x0f, 0xb6, 0x90, 0x6c, 0x31, 0x77, 0x00, 0xff, 0x24, 0x95, 0x28, 0x31, 0x77, 0x00};
const DWORD kSelNext = 0x00772f90;      // cmp eax,1Ch (after the 6-byte lea we detour)
const DWORD kSelIndex608 = 0x00773173;  // byte table entry of 608: 0x10 = the default target
const DWORD kSelDefaultEntry = 0x00773168;   // jump table entry 16 = 0x77309a (default)
const DWORD kSelDefault = 0x0077309a;
const DWORD kSelExit = 0x007730af;      // after the switch: push 191h (state parameter 0x191 ...)
const BYTE kSelExitBytes[] = {0x68, 0x91, 0x01, 0x00, 0x00};
const DWORD kAttachToJumpTarget = 0x00707b90;   // cdecl(const vec4 *, float), PC of TU 0x823fd178
const BYTE kAttachBytes[] = {0xa1, 0x58, 0xdb, 0xfa, 0x00, 0x8b, 0x88, 0x64, 0x0a, 0x00, 0x00, 0x56, 0x8b, 0x71, 0x28,
                             0xe8, 0xec, 0x67, 0xeb, 0xff};
const DWORD kGameTracker = 0x00fadb58;
// tru+0x32ba40: attach point on a box, cdecl(out, box) (e.g. state 572 tru+0x36ddab with box = gameTracker+0xc94)
const DWORD kPointOnBox = 0x0072ba40;
const BYTE kPointOnBoxBytes[] = {0x55, 0x8b, 0xec, 0x83, 0xe4, 0xf0, 0x83, 0xec, 0x18, 0x56, 0x8b, 0x75, 0x08, 0x57,
                                 0x8b, 0x7d, 0x0c};
const DWORD kPointOnBoxNext = 0x0072ba46;

typedef void(__cdecl *AttachFn)(const float *vec, float value);
typedef int(__fastcall *GetTypeFn)(void *ctx, void *unused);   // thiscall getter, no stack arguments
typedef char(__thiscall *BoxPredFn)(void *mgr, void *box);

// options (TruRockVein.ini, section [RockVein])
int g_enabled = 1;
int g_logLevel = 1;                     // 0 errors, 1 info + first unhandled ids, 2 result changes, 3 every call
int g_logUnhandled = 1;
int g_type607 = 23, g_type608 = 22;     // Xbox title update values
int g_logBadValues = 1;                 // 0.2: markup values outside 601..628 (data in the wrong byte order)
int g_logDefaultConditions = 1;         // 0.2: condition ids answered by the default handler
int g_markupTypes = 1;                  // 0.3: accept the title-update markup types 22 / 23 (flag class 1)
int g_markupSlots = 1;                  // 0.4: TU type checks in TRMarkupManager slots 0 / 1 / +0x08
int g_nullBoxGuard = 1;                 // 0.4: diagnostic guard for slot +0x08 with box 0 (logs the caller)
DWORD g_slot8Orig = kSlot8, g_slot8Edge = kSlot8Edge, g_slot8Other = kSlot8Other;
volatile LONG g_slotHits[3] = {0, 0, 0};   // slot 0 / 1 / +0x08 answered by the TU type check
volatile LONG g_nullBoxCalls = 0;
DWORD g_nullBoxCallers[16];
int g_markupAction608 = 1;              // 0.5: TU markup action 608 (attach to the jump target)
DWORD g_selNext = kSelNext, g_selExit = kSelExit, g_pointOnBoxNext = kPointOnBoxNext;
volatile LONG g_action608Calls = 0;
DWORD g_dispatchNext = kDispatchNext;
DWORD g_condDefaultNext = kCondDefaultNext;
volatile LONG g_valueSeen[29];          // 601..628 first-call flags (index value - 600)
volatile LONG g_badSeen = 0;            // number of distinct bad values logged
WORD g_badValues[64];
volatile LONG g_defaultSeen[65536 / 32];   // bit per condition id
volatile LONG g_defaultCount = 0;

char g_logPath[MAX_PATH];
char g_dir[MAX_PATH];                   // folder of the plugin (= game folder), with trailing backslash
CRITICAL_SECTION g_logLock;
DWORD g_exitAddress = kExit;            // jump targets read by the stubs
DWORD g_defaultAddress = kDefault;
int g_last[2] = {-2, -2};               // last logged (type, result) per condition, packed
LONG g_calls[2] = {0, 0};
LONG g_unhandledSeen[64];               // per table index: calls of an unhandled id

void Log(int level, const char *fmt, ...) {
    if (level > g_logLevel || !g_logPath[0]) return;
    char line[512];
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

int SafeType(void *ctx, int *ok) {
    __try {
        *ok = 1;
        return reinterpret_cast<GetTypeFn>(kGetType)(ctx, nullptr);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        *ok = 0;
        return -1;
    }
}

// called from the stubs on the game thread: 1 if the context's markup has the wanted type (TU 607 / 608 semantics)
int __stdcall CheckType(void *ctx, int id, int want) {
    int slot = id == 607 ? 0 : 1;
    LONG calls = InterlockedIncrement(&g_calls[slot]);
    int type = -1, ok = 1, result = 0;
    if (ctx) {
        type = SafeType(ctx, &ok);
        result = ok && type == want;
    }
    int packed = (type & 0xff) | (result << 8) | (ctx ? 0 : 0x10000) | (ok ? 0 : 0x20000);
    if (g_logLevel >= 3)
        Log(3, "condition %d: ctx 0x%08lx type %d -> %d (call %ld)", id, reinterpret_cast<DWORD>(ctx), type, result, calls);
    else if (packed != g_last[slot])
        Log(2, "condition %d: ctx 0x%08lx type %d -> %d%s (call %ld)", id, reinterpret_cast<DWORD>(ctx), type, result,
            ok ? "" : " (read failed)", calls);
    if (calls == 1) Log(1, "condition %d is now evaluated (first call: type %d -> %d)", id, type, result);
    g_last[slot] = packed;
    return result;
}

void __stdcall LogUnhandled(int index) {
    if (index < 0 || index >= 64) return;
    LONG n = InterlockedIncrement(&g_unhandledSeen[index]);
    if (n == 1 || (g_logLevel >= 2 && (n & (n - 1)) == 0))   // first call, then 2, 4, 8 ... at level 2
        Log(1, "unhandled markup condition %d (call %ld) - not implemented on PC", 601 + index, n);
}

// jump-table targets: run inside SCCondTest_MarkupType's frame (after its push ebx / push esi), so the context
// argument is [esp+1Ch]; after pushad (32 bytes) it is [esp+32+1Ch].
__declspec(naked) void Cond607() {
    __asm {
        pushad
        mov eax, [esp + 32 + 0x1c]
        push dword ptr [g_type607]
        push 607
        push eax
        call CheckType
        mov [esp + 16], eax             // saved EBX of pushad -> bl = result
        popad
        jmp dword ptr [g_exitAddress]
    }
}

__declspec(naked) void Cond608() {
    __asm {
        pushad
        mov eax, [esp + 32 + 0x1c]
        push dword ptr [g_type608]
        push 608
        push eax
        call CheckType
        mov [esp + 16], eax
        popad
        jmp dword ptr [g_exitAddress]
    }
}

// for the other unhandled ids: eax = id - 601 (the dispatch index) - log, then the original default case
__declspec(naked) void CondUnhandled() {
    __asm {
        pushad
        push eax
        call LogUnhandled
        popad
        jmp dword ptr [g_defaultAddress]
    }
}

// ---- 0.2 probes (read only; the game's own code runs unchanged after them) ----

bool ReadRecord(const BYTE *record, WORD *out4, BYTE *flags) {
    __try {
        for (int i = 0; i < 3; ++i) out4[i] = reinterpret_cast<const WORD *>(record)[i];
        *flags = record[6];
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// from the dispatch detour: value = the markup subtest SCCondTest_MarkupType switches on (> 600 here)
void __stdcall CheckValue(int value, const BYTE *record) {
    WORD r[3] = {0, 0, 0};
    BYTE fl = 0;
    if (value >= 601 && value <= 628) {
        if (g_logLevel >= 2 && InterlockedExchange(&g_valueSeen[value - 600], 1) == 0) {
            ReadRecord(record, r, &fl);
            Log(2, "markup subtest %d first evaluated (record {%u, %u, %u, flags %u})", value, r[0], r[1], r[2], fl);
        }
        return;
    }
    if (value == 1000 || !g_logBadValues) return;
    LONG n = g_badSeen;                                 // game thread only; the list is just a log filter
    for (LONG i = 0; i < n && i < 64; ++i)
        if (g_badValues[i] == static_cast<WORD>(value)) return;
    if (n >= 64) return;
    g_badValues[n] = static_cast<WORD>(value);
    g_badSeen = n + 1;
    bool ok = ReadRecord(record, r, &fl);
    Log(1, "markup record value %d (0x%04x) is no subtest 601..628: record at 0x%08lx {%u, %u, %u, flags %u}%s - "
           "state chart data in the wrong byte order? (Xbox order of %d would be %d)",
        value, value & 0xffff, reinterpret_cast<DWORD>(record), r[0], r[1], r[2], fl, ok ? "" : " (read failed)", value,
        ((value & 0xff) << 8) | ((value >> 8) & 0xff));
}

// from the default-handler detour: agent = 1st argument, record = 3rd (as tru+0x382154 / +0x382160 read them)
void __stdcall LogDefault(const BYTE *agent, const BYTE *record) {
    if (!g_logDefaultConditions) return;
    WORD r[3] = {0, 0, 0};
    BYTE fl = 0;
    if (!ReadRecord(record, r, &fl)) return;
    int id = static_cast<short>(r[1]);
    LONG bit = 1L << (id & 31);
    if (InterlockedOr(&g_defaultSeen[(id & 0xffff) >> 5], bit) & bit) return;
    char state[64] = "?";
    WORD proc = 0;
    __try {
        const BYTE *sm = *reinterpret_cast<const BYTE *const *>(agent + 0x510);
        const char *name = sm ? *reinterpret_cast<const char *const *>(sm + 0x24) : nullptr;
        if (name) { strncpy_s(state, sizeof(state), name, _TRUNCATE); }
        const BYTE *p = *reinterpret_cast<const BYTE *const *>(agent + 4);
        if (p) proc = *reinterpret_cast<const WORD *>(p + 2);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    LONG n = InterlockedIncrement(&g_defaultCount);
    Log(1, "condition %d answered by the default handler (true): record {%u, %d, %u, flags %u}, agent 0x%08lx "
           "(AnimProcID %u) in state \"%s\" [%ld distinct]", id, r[0], id, r[2], fl, reinterpret_cast<DWORD>(agent), proc,
        state, n);
}

// detour of `sub eax,259h` (5 bytes) at tru+0x38288d: eax = value, esi = record (tru+0x382812)
__declspec(naked) void DispatchProbe() {
    __asm {
        pushad
        push esi
        push eax
        call CheckValue
        popad
        sub eax, 0x259
        jmp dword ptr [g_dispatchNext]
    }
}

// detour of `sub esp,204h` (6 bytes) at the default handler's entry: [esp+4] agent, [esp+0Ch] record
__declspec(naked) void DefaultProbe() {
    __asm {
        pushad
        push dword ptr [esp + 32 + 0x0c]      // record
        push dword ptr [esp + 32 + 0x04 + 4]  // agent (one push above)
        call LogDefault
        popad
        sub esp, 0x204
        jmp dword ptr [g_condDefaultNext]
    }
}

bool WriteJump(DWORD at, const void *to, int length) {
    BYTE code[8] = {0xe9, 0, 0, 0, 0, 0x90, 0x90, 0x90};
    DWORD rel = reinterpret_cast<DWORD>(to) - (at + 5);
    memcpy(code + 1, &rel, 4);
    DWORD old = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(at), length, PAGE_EXECUTE_READWRITE, &old)) return false;
    memcpy(reinterpret_cast<void *>(at), code, length);
    DWORD dummy = 0;
    VirtualProtect(reinterpret_cast<void *>(at), length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void *>(at), length);
    return true;
}

void InstallProbes() {
    if (g_logBadValues || g_logLevel >= 2) {
        // the dispatch bytes were verified in Start (kDispatchBytes starts with the 5-byte sub eax,259h)
        if (WriteJump(kDispatch, &DispatchProbe, 5))
            Log(1, "probe: markup values outside 601..628 are logged (detour at 0x%08lx)", kDispatch);
        else
            Log(0, "probe at 0x%08lx not written (VirtualProtect %lu)", kDispatch, GetLastError());
    }
    if (g_logDefaultConditions) {
        // TruDoppelganger.asi verifies the first bytes of this handler before it registers its ids; the ASI loader
        // loads alphabetically, so it normally runs first - if its file is there but it is not loaded yet, our detour
        // would make its check fail: then the probe stays off
        char other[MAX_PATH];
        _snprintf_s(other, sizeof(other), _TRUNCATE, "%sTruDoppelganger.asi", g_dir);
        if (GetFileAttributesA(other) != INVALID_FILE_ATTRIBUTES && !GetModuleHandleA("TruDoppelganger.asi")) {
            Log(0, "default-condition probe off: TruDoppelganger.asi is present but not loaded yet (load order)");
            return;
        }
        if (!BytesAt(kCondDefault, kCondDefaultBytes, sizeof(kCondDefaultBytes)) ||
            !BytesAt(kFormatPushAt, kFormatPush, sizeof(kFormatPush))) {
            Log(0, "condition default handler at 0x%08lx does not match - default-condition probe off", kCondDefault);
        } else if (WriteJump(kCondDefault, &DefaultProbe, 6)) {
            Log(1, "probe: conditions answered by the default handler are logged (detour at 0x%08lx)", kCondDefault);
        } else {
            Log(0, "probe at 0x%08lx not written (VirtualProtect %lu)", kCondDefault, GetLastError());
        }
    }
}

void ReadOptions(const char *dir) {
    char ini[MAX_PATH];
    _snprintf_s(ini, sizeof(ini), _TRUNCATE, "%sTruRockVein.ini", dir);
    g_enabled = GetPrivateProfileIntA("RockVein", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("RockVein", "LogLevel", 1, ini);
    g_logUnhandled = GetPrivateProfileIntA("RockVein", "LogUnhandled", 1, ini);
    g_type607 = GetPrivateProfileIntA("RockVein", "Type607", 23, ini);
    g_type608 = GetPrivateProfileIntA("RockVein", "Type608", 22, ini);
    g_logBadValues = GetPrivateProfileIntA("RockVein", "LogBadValues", 1, ini);
    g_logDefaultConditions = GetPrivateProfileIntA("RockVein", "LogDefaultConditions", 1, ini);
    g_markupTypes = GetPrivateProfileIntA("RockVein", "MarkupTypes", 1, ini);
    g_markupSlots = GetPrivateProfileIntA("RockVein", "MarkupSlots", 1, ini);
    g_nullBoxGuard = GetPrivateProfileIntA("RockVein", "NullBoxGuard", 1, ini);
    g_markupAction608 = GetPrivateProfileIntA("RockVein", "MarkupAction608", 1, ini);
}

// 0.3: the title update's markup types 22 / 23 -> flag class 1 (Xbox TU 0x822a12e8 table entries 21 / 22 = li r3,1).
// Two new table entries in the int3 padding right after the 21-entry table, then the bound 0x14 -> 0x16.
bool PatchMarkupTypes() {
    if (*reinterpret_cast<const DWORD *>(kTypeFlagsSlot) != kTypeFlags || !BytesAt(kTypeFlags, kTypeFlagsBytes,
            sizeof(kTypeFlagsBytes)) || !BytesAt(kTypeFlagsTable, reinterpret_cast<const BYTE *>(kTypeFlagsTableOriginal),
            sizeof(kTypeFlagsTableOriginal)) || !BytesAt(kTypeFlagsTable + sizeof(kTypeFlagsTableOriginal),
            kTypeFlagsPad, sizeof(kTypeFlagsPad))) {
        Log(0, "markup type mapper at 0x%08lx does not match - markup types 22 / 23 not added", kTypeFlags);
        return false;
    }
    BYTE *from = reinterpret_cast<BYTE *>(kTypeFlags);
    DWORD length = kTypeFlagsTable + sizeof(kTypeFlagsTableOriginal) + sizeof(kTypeFlagsPad) - kTypeFlags;
    DWORD old = 0;
    if (!VirtualProtect(from, length, PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "VirtualProtect failed (%lu) - markup types 22 / 23 not added", GetLastError());
        return false;
    }
    DWORD *table = reinterpret_cast<DWORD *>(kTypeFlagsTable);
    table[21] = kTypeFlagsOne;                 // type 22
    table[22] = kTypeFlagsOne;                 // type 23
    *reinterpret_cast<BYTE *>(kTypeFlagsLimit) = 0x16;
    DWORD dummy = 0;
    VirtualProtect(from, length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), from, length);
    Log(1, "markup types 22 / 23 accepted (flag class 1, as the title update; mapper 0x%08lx)", kTypeFlags);
    return true;
}

// ---- 0.4: title-update type checks in TRMarkupManager slots 0 / 1 / +0x08 ----

// TU slot 0 0x822a0bc8 / slot 1 0x822a0c68: (flags & mask) || predicate(box) || type == 22 / 23
void LogSlotHit(int slot, void *box, int type) {
    LONG n = InterlockedIncrement(&g_slotHits[slot]);
    if (n == 1 || (g_logLevel >= 2 && (n & (n - 1)) == 0))
        Log(1, "markup slot %s true by the title-update type check: box 0x%08lx type %d (call %ld)",
            slot == 0 ? "0 (wall, type 22)" : slot == 1 ? "1 (type 23)" : "+0x08 (edge normal, type 22)",
            reinterpret_cast<DWORD>(box), type, n);
}

char __fastcall Slot0(void *mgr, void *, void *box) {
    if (reinterpret_cast<BoxPredFn>(kSlot0)(mgr, box)) return 1;
    int ok = 0, type = SafeType(box, &ok);
    if (!ok || type != 22) return 0;
    LogSlotHit(0, box, type);
    return 1;
}

char __fastcall Slot1(void *mgr, void *, void *box) {
    if (reinterpret_cast<BoxPredFn>(kSlot1)(mgr, box)) return 1;
    int ok = 0, type = SafeType(box, &ok);
    if (!ok || type != 23) return 0;
    LogSlotHit(1, box, type);
    return 1;
}

void __stdcall LogSlot8Edge(void *box) { LogSlotHit(2, box, 22); }

// replaces `je 0x5dbac8` at tru+0x1dba3c; flags still from `test [ebx+28h],20408000h`, ebx = box, edi = [ebx+20h].
// TU 0x822a0d40..0x822a0d68: mask bits set or type 22 -> edge path, else the retail fallback.
__declspec(naked) void Slot8Branch() {
    __asm {
        jne edge
        push eax
        mov eax, [ebx + 0x24]
        test eax, eax
        jz use20
        movsx eax, byte ptr [eax + 0x4d]
        jmp compare
    use20:
        test edi, edi
        jz other_pop
        movsx eax, byte ptr [edi + 0x33]
    compare:
        cmp eax, 22
        jne other_pop
        pushad
        push ebx
        call LogSlot8Edge
        popad
        pop eax
    edge:
        jmp dword ptr [g_slot8Edge]
    other_pop:
        pop eax
        jmp dword ptr [g_slot8Other]
    }
}

// diagnostic: who calls slot +0x08 with box 0 (the crash of test 48i at tru+0x1dba2d)
void __stdcall LogNullBox(DWORD ret, DWORD outer) {
    LONG n = InterlockedIncrement(&g_nullBoxCalls);
    DWORD caller = ret == kWrapperRet ? outer : ret;   // through the wrapper tru+0x1c3cc0: its caller
    bool known = false;
    for (int i = 0; i < 16; ++i) {
        if (g_nullBoxCallers[i] == caller) { known = true; break; }
        if (!g_nullBoxCallers[i]) { g_nullBoxCallers[i] = caller; break; }
    }
    DWORD gt = 0, a64 = 0, c94 = 0;
    __try {
        gt = *reinterpret_cast<const DWORD *>(0x00fadb58);
        if (gt) { a64 = *reinterpret_cast<const DWORD *>(gt + 0xa64); c94 = *reinterpret_cast<const DWORD *>(gt + 0xc94); }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    if (!known || (g_logLevel >= 2 && (n & (n - 1)) == 0))
        Log(1, "markup slot +0x08 called with box 0 from 0x%08lx (return 0x%08lx, call %ld): gameTracker 0x%08lx "
               "+0xa64 0x%08lx +0xc94 0x%08lx - zero vector returned instead of the crash", caller, ret, n, gt, a64, c94);
}

// vtable slot +0x08: [esp+4] out, [esp+8] box, [esp+0Ch] segment; via the wrapper [esp+14h] = the wrapper's caller
__declspec(naked) void Slot8Guard() {
    __asm {
        cmp dword ptr [esp + 8], 0
        je null_box
        jmp dword ptr [g_slot8Orig]
    null_box:
        pushad
        push dword ptr [esp + 32 + 0x14]
        push dword ptr [esp + 32 + 4]
        call LogNullBox
        popad
        mov eax, [esp + 4]
        mov dword ptr [eax], 0
        mov dword ptr [eax + 4], 0
        mov dword ptr [eax + 8], 0
        mov dword ptr [eax + 12], 0
        ret 0x0c
    }
}

// ---- 0.5: markup action 608 (TU 0x82463a28) and the point-on-box guard ----

void ReadAttachState(DWORD *gt, DWORD *a64, DWORD *c94) {
    *gt = *a64 = *c94 = 0;
    __try {
        *gt = *reinterpret_cast<const DWORD *>(kGameTracker);
        if (*gt) { *a64 = *reinterpret_cast<const DWORD *>(*gt + 0xa64); *c94 = *reinterpret_cast<const DWORD *>(*gt + 0xc94); }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

// TU selector case 608: gameTracker+0xa64 != 0 -> PLAYER_AttachToJumpTarget(zero vector 0x8207db30, 0.0f [0x8207d538]);
// then gameTracker+0xca0 = gameTracker+0xd90 (16 bytes; both fields are the same on PC: +0xca0 is written by the attach
// functions tru+0x307530 = TU 0x823fcb28, +0xd90 by the player process tru+0x31ffe0 = retail 0x8240b560)
void __stdcall Action608(const BYTE *agent) {
    LONG n = InterlockedIncrement(&g_action608Calls);
    DWORD gt = *reinterpret_cast<const DWORD *>(kGameTracker);
    DWORD box = gt ? *reinterpret_cast<const DWORD *>(gt + 0xa64) : 0;
    if (box) {
        __declspec(align(16)) float zero[4] = {0.0f, 0.0f, 0.0f, 0.0f};
        reinterpret_cast<AttachFn>(kAttachToJumpTarget)(zero, 0.0f);
        gt = *reinterpret_cast<const DWORD *>(kGameTracker);
        memcpy(reinterpret_cast<void *>(gt + 0xca0), reinterpret_cast<const void *>(gt + 0xd90), 16);
    }
    if (n == 1 || (g_logLevel >= 2 && (n & (n - 1)) == 0)) {
        DWORD g = 0, a64 = 0, c94 = 0;
        ReadAttachState(&g, &a64, &c94);
        Log(1, "markup action 608 (attach to jump target, title update) call %ld: agent 0x%08lx, box 0x%08lx -> "
               "gameTracker+0xc94 0x%08lx%s", n, reinterpret_cast<DWORD>(agent), box, c94, box ? "" : " (no box, nothing done)");
    }
}

// replaces `lea eax,[ebx-259h]` (6 bytes) at tru+0x372f8a: ebx = action value, esi = agent
__declspec(naked) void SelectorProbe() {
    __asm {
        cmp ebx, 608
        jne other
        pushad
        push esi
        call Action608
        popad
        jmp dword ptr [g_selExit]
    other:
        lea eax, [ebx - 0x259]
        jmp dword ptr [g_selNext]
    }
}

void __stdcall LogNullPoint(DWORD ret) {
    LONG n = InterlockedIncrement(&g_nullBoxCalls);
    DWORD gt, a64, c94;
    ReadAttachState(&gt, &a64, &c94);
    if (n == 1 || (g_logLevel >= 2 && (n & (n - 1)) == 0))
        Log(1, "attach point tru+0x32ba40 called with box 0 from 0x%08lx (call %ld): gameTracker 0x%08lx +0xa64 0x%08lx "
               "+0xc94 0x%08lx - zero vector returned instead of the crash", ret, n, gt, a64, c94);
}

// tru+0x32ba40 cdecl(out, box): [esp+4] out, [esp+8] box; returns out
__declspec(naked) void PointOnBoxGuard() {
    __asm {
        cmp dword ptr [esp + 8], 0
        je null_box
        push ebp
        mov ebp, esp
        and esp, 0xfffffff0
        jmp dword ptr [g_pointOnBoxNext]
    null_box:
        pushad
        push dword ptr [esp + 32]
        call LogNullPoint
        popad
        mov eax, [esp + 4]
        mov dword ptr [eax], 0
        mov dword ptr [eax + 4], 0
        mov dword ptr [eax + 8], 0
        mov dword ptr [eax + 12], 0
        ret
    }
}

void PatchSelector() {
    if (!BytesAt(kSelSwitch, kSelSwitchBytes, sizeof(kSelSwitchBytes)) || !BytesAt(kSelExit, kSelExitBytes, sizeof(kSelExitBytes)) ||
        *reinterpret_cast<const BYTE *>(kSelIndex608) != 0x10 || *reinterpret_cast<const DWORD *>(kSelDefaultEntry) != kSelDefault ||
        !BytesAt(kAttachToJumpTarget, kAttachBytes, sizeof(kAttachBytes))) {
        Log(0, "markup-action selector at 0x%08lx does not match - markup action 608 not added", kSelSwitch);
        return;
    }
    if (WriteJump(kSelSwitch, &SelectorProbe, 6))
        Log(1, "markup action 608 added (title-update case: attach to the jump target; selector 0x%08lx)", kSelSwitch);
    else
        Log(0, "markup action 608 not written (VirtualProtect %lu)", GetLastError());
}

void PatchPointOnBox() {
    if (!BytesAt(kPointOnBox, kPointOnBoxBytes, sizeof(kPointOnBoxBytes))) {
        Log(0, "attach point function at 0x%08lx does not match - its null-box guard is off", kPointOnBox);
        return;
    }
    if (WriteJump(kPointOnBox, &PointOnBoxGuard, 6))
        Log(1, "null-box guard on the attach point function 0x%08lx (diagnostic)", kPointOnBox);
    else
        Log(0, "null-box guard at 0x%08lx not written (VirtualProtect %lu)", kPointOnBox, GetLastError());
}

bool WriteDword(DWORD at, DWORD value) {
    DWORD old = 0, dummy = 0;
    if (!VirtualProtect(reinterpret_cast<void *>(at), 4, PAGE_READWRITE, &old)) return false;
    *reinterpret_cast<DWORD *>(at) = value;
    VirtualProtect(reinterpret_cast<void *>(at), 4, old, &dummy);
    return true;
}

void PatchSlots() {
    const DWORD *vt = reinterpret_cast<const DWORD *>(kSlot0At);
    if (vt[0] != kSlot0 || vt[1] != kSlot1 || vt[2] != kSlot8 || !BytesAt(kSlot0, kSlot0Bytes, sizeof(kSlot0Bytes)) ||
        !BytesAt(kSlot1, kSlot1Bytes, sizeof(kSlot1Bytes)) || !BytesAt(kSlot8, kSlot8Bytes, sizeof(kSlot8Bytes))) {
        Log(0, "TRMarkupManager slots 0 / 1 / +0x08 at 0x%08lx do not match - title-update type checks not added", kSlot0At);
        return;
    }
    if (g_markupSlots) {
        bool ok = WriteDword(kSlot0At, reinterpret_cast<DWORD>(&Slot0)) && WriteDword(kSlot1At, reinterpret_cast<DWORD>(&Slot1)) &&
                  WriteJump(kSlot8Branch, &Slot8Branch, 6);
        if (ok)
            Log(1, "markup slots: 0 also true for type 22, 1 for type 23, +0x08 edge normal for type 22 (as the title "
                   "update; vtable 0x%08lx, branch 0x%08lx)", kSlot0At, kSlot8Branch);
        else
            Log(0, "markup slots not (fully) written (VirtualProtect %lu)", GetLastError());
    }
    if (g_nullBoxGuard) {
        if (WriteDword(kSlot8At, reinterpret_cast<DWORD>(&Slot8Guard)))
            Log(1, "null-box guard on markup slot +0x08 (diagnostic; vtable entry 0x%08lx)", kSlot8At);
        else
            Log(0, "null-box guard not written (VirtualProtect %lu)", GetLastError());
    }
}

bool PatchTable() {
    DWORD *table = reinterpret_cast<DWORD *>(kTable);
    DWORD old = 0;
    if (!VirtualProtect(table, kTableCount * sizeof(DWORD), PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "VirtualProtect failed (%lu) - not patched", GetLastError());
        return false;
    }
    table[607 - 601] = reinterpret_cast<DWORD>(&Cond607);
    table[608 - 601] = reinterpret_cast<DWORD>(&Cond608);
    int logged = 0;
    if (g_logUnhandled) {
        for (int i = 0; i < kTableCount; ++i) {
            if (i == 607 - 601 || i == 608 - 601 || kTableOriginal[i] != kDefault) continue;
            table[i] = reinterpret_cast<DWORD>(&CondUnhandled);
            ++logged;
        }
    }
    DWORD dummy = 0;
    VirtualProtect(table, kTableCount * sizeof(DWORD), old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), table, kTableCount * sizeof(DWORD));
    Log(1, "jump table patched: 607 -> 0x%08lx (type %d), 608 -> 0x%08lx (type %d), %d unhandled ids logged",
        reinterpret_cast<DWORD>(&Cond607), g_type607, reinterpret_cast<DWORD>(&Cond608), g_type608, logged);
    return true;
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruRockVein.log", dir);
    strncpy_s(g_dir, sizeof(g_dir), dir, _TRUNCATE);
    ReadOptions(dir);
    Log(1, "TruRockVein 0.5 loaded (enabled %d, log level %d, log unhandled %d, bad values %d, default conditions %d, "
        "markup types %d, markup slots %d, null-box guard %d, markup action 608 %d)", g_enabled, g_logLevel, g_logUnhandled,
        g_logBadValues, g_logDefaultConditions, g_markupTypes, g_markupSlots, g_nullBoxGuard, g_markupAction608);
    if (!g_enabled) { Log(1, "disabled by TruRockVein.ini - nothing patched"); return; }
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - not patched", base, kImageBase); return; }
    if (g_markupTypes) PatchMarkupTypes();
    if (g_markupSlots || g_nullBoxGuard) PatchSlots();
    if (g_markupAction608) PatchSelector();
    if (g_nullBoxGuard) PatchPointOnBox();
    if (!BytesAt(kDispatch, kDispatchBytes, sizeof(kDispatchBytes)) || !BytesAt(kDefault, kDefaultBytes, sizeof(kDefaultBytes)) ||
        !BytesAt(kExit, kExitBytes, sizeof(kExitBytes)) || !BytesAt(kCtxUse, kCtxUseBytes, sizeof(kCtxUseBytes))) {
        Log(0, "SCCondTest_MarkupType at 0x%08lx does not match (other tru.exe build?) - not patched", kDispatch);
        return;
    }
    if (!BytesAt(kGetType, kGetTypeBytes, sizeof(kGetTypeBytes))) {
        Log(0, "markup type getter at 0x%08lx does not match - not patched", kGetType);
        return;
    }
    if (!BytesAt(kTable, reinterpret_cast<const BYTE *>(kTableOriginal), sizeof(kTableOriginal))) {
        Log(0, "condition jump table at 0x%08lx is not the original (patched by something else?) - not patched", kTable);
        return;
    }
    Log(3, "code checks passed (dispatch, default case, exit, context use, type getter, table)");
    if (PatchTable()) InstallProbes();
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
extern "C" __declspec(dllexport) const char *TruRockVeinVersion() { return "TruRockVein 0.5 (markup conditions 607 / 608, chart probes, markup types 22 / 23, TU slot type checks, markup action 608)"; }
