// TruShadowCombat.asi - DLC 2 "Lara's Shadow" combat (target list, target conditions, shadow-strike gate) for the PC
// tru.exe (Steam, image base 0x400000). Translation of the Xbox title update (TU), docs/Befund-Schattenkampf.md.
//
// 1. Target list: the TU grew the player's targeter array from 7 to 10 entries (retail -> TU: `li/cmpwi 7` -> 0xa at
//    every loop over it, candidate mask 0x71 -> 0x3f1, array 0x1c -> 0x28 bytes) and gave the targeters their
//    parameters through the new helper 0x82402208: index 0..5 as retail, 6 -> the parameters of 2 (+0x468), 7 -> the
//    old 6 (+0x478), 8 / 9 -> none, and for every index an override from the DLC 2 player tuning (object 858, table
//    tuning +0x90 / +0x94 count: entries for 8 and 9). The PC still has the retail list ([0xfadfac], 7 entries). The
//    plugin patches the same constants at the PC sites (tools/tu_imm_change_sites.py, PC loops tru+0x31dc78 ctor,
//    tru+0x316946 / +0x3169d0 instance add + masks tru+0x316915 / +0x3169a2, tru+0x31aca9, tru+0x31dcce, destroy
//    tru+0x316843, per-frame update tru+0x3228a3, alloc tru+0x322631) and replaces the PC parameter function
//    tru+0x2ecc10 (= retail 0x823ff7d8, the TU's 0x82402208) with the TU logic. PC slots 0..6 keep their retail
//    meaning (PC code passes those indices); the TU-only targeters live in the new slots: slot 7 = TU 6, 8 = TU 8,
//    9 = TU 9 (TU 7 = the old 6 = PC slot 6). Every TU index below is mapped through SlotOf().
// 2. Lara's conditions (both state machines, as the TU tables): 2005 / 2006 / 2013 (TU-only predicates 0x8246e8e0 /
//    0x8246eb08 / 0x8246ea30), 2011 (TU 0x8246f140: doppelganger branch with targeter 9) and 538 (TU 0x8246faa8:
//    doppelganger -> meter flag 8). Outside doppelganger mode the PC predicates (retail) answer.
// 3. State 1014 (shadow strike, TU slots 0 / 2 / 3 -> 0x823d8978 / 0x823d9210 / 0x823d8d18 in doppelganger mode): not
//    translated yet (needs the meter object owned by TruShadowPower, see MeterApi). In doppelganger mode the PC's
//    retail strike (tru+0x31d3c0 / +0x318fd0 / +0x318d00, player fields) is NOT run ([Strike] Gate=1) - logged.
// 4. 0.5: states 1019 / 1020 (TU 0x8245f420 / 0x8245f540 / 0x8245f398 + 0x8245f2a8 / 0x82463c18 / 0x82463eb8, VMX128
//    bodies decoded), registered log-only; [States] Translate1019 / Translate1020 = 1 makes them act.
// 5. 0.5.1: TU table differences of states 231 (slots 0 / 1 = 0x82464160, the move helper with the doppelganger branch)
//    and 1004 (slots 0 / 1 = 0x8245efc8, hit list kept with parameter 0x415); PC handlers unless [States]
//    Translate231Slot0 / Translate231Slot1 / Translate1004 = 1.
// 6. 0.5.2 (F21, log only, [Diag]): who fills / clears targeter 9 (TU index 9) - candidate add, per-frame sort, select,
//    set, remove, the target list array build / destroy - and every evaluation of condition 2011 with its inputs.
// 7. 0.6 (K14): the enemy damage function tru+0x237590 - entry probe counting the incoming damage types ([Damage]
//    Log=1, changes nothing) and the TU's extension of its type switch 0..16 -> 0..27 ([Damage] Translate=1).
// 8. 0.6.1: the LP <= 0 branch of the enemy impulse handler tru+0x224c60 (message 0x91, sent from Lara's contact
//    callback inside the physics step) as the TU 0x82305ba0: death switch kind 7 instead of creating the chunkdoll at
//    once (whose rigid bodies the locked physics step refuses -> fatal "ChunkDoll: failed to create geom")
//    ([Chunk] Translate=1, default on; [Chunk] Log=1 burst lines).
// 9. 0.6.2 (K9): CombatManager::MeleeSplashDamage tru+0x2e68b0 as the TU 0x823e1220 - the main target (CM+0x48) gets
//    no extra splash hit (area damage tru+0x29f1e0 skips it as TU 0x8237ae88), and in doppelganger mode the splash type
//    is remapped through object 858's pair table (0x1a -> 0x10, 0x10 -> 0x16) while the K14 switch is extended
//    ([Splash] Translate=1, default on; [Splash] Log=1 burst lines).
// 10. 0.6.3 (P1a, T3 of the TU's thrall death): notification 33 (TRScriptUnitManager::PlayNotification tru+0x37a540)
//    before EnterRegenerateDeath in the death check tru+0x220380, as the TU 0x822f6578 ([Death] TranslateNotify33=1,
//    default on); [Damage] Translate (K14) now on by default (live 07.11.: thralls die, the hall02 wall breaks).
// 11. 0.6.4 (P1b, T-M1 / T-M2): the enemy state MeleeAttack as the TU - messages 0x15 / 0x8a / 0xbe end the attack only
//    without a data pointer (message slot tru+0x266350 = TU 0x82330d40), and Enter sets brain+0xc bit 0 when record+8
//    bit 2 is clear (tru+0x25c7b0 = TU 0x8232fb48) ([Melee] Translate=1, default on). T-M3 (interruption) needs T4.
// 12. 0.6.5 (P1d): the thrall's companion (T4, TU-only instance 0x822da800 / reader 0x822da918) as a stateless lookup
//    in the object table ([Companion] Translate / Log) and what the TU hangs on it: notification 34 at every exit of
//    RegenerateDeath (H6), the finisher block with notification 38 in RegenerateDeath / Regenerate (H7 / H8), the
//    companion's regeneration list in ShouldRegenerate (H1), T2 Land with LP <= 0 + Land slot 13 + T3's Land exception
//    (H3 / H4 / H3b) and T-M3, the MeleeAttack interruption by Vaulted / RegenerateDeath (H5). All default on.
// 13. 0.6.6 (N4c): T5 - a lethal, not regenerating hit on an enemy with a companion dies at once (death kind 7) in the
//    hit reaction tru+0x23ad50 as the TU 0x823038d8 ([Death] TranslateT5); P1c - the Vaulted Enter of the TU
//    (0x8232b630: companion step animation, state data +0xb8, brain+0x2c7c) with the chain that feeds its new data
//    field +0x44 (records 0xbe / 0xf4, switch, data copier) ([Death] TranslateVaulted); the step table is read only
//    from FIXED extension data (tools/thrall_extension_fix.py); the Vaulted clock (5 s without slow motion, brain+0xc
//    bit 0x10 / +0x5080 / +0x5084 kept by the plugin) in the Enter and the enemy update tru+0x238d40 ([Death]
//    TranslateVaultedClock). All default on, live.
// 14. 0.6.8 (K-1b): Lara's contact-hit sender tru+0x319050 sends the impulse message 0x91 after the hit message 0x11c
//    (tru+0x3192da); the TU 0x823e1870 skips it for targets with flag 0x400000 in [[inst+0x10]]+4 (enemies with a
//    brain) - [Hit] TranslateImpulseGate, default on, live.
// 15. 0.6.9 (K-8 / melee kill, log only): three call sites log what they did - the chunkdoll build of the Death state
//    (tru+0x26c9f9), the hit-list add of Lara's contact hit (tru+0x3190ad) and the death switch tru+0x241650 (entry) -
//    [Hit] Log / [Death] Log, live. The TU death switch 0x823258c8 only inlines retail's request helper 0x8230e290
//    (= PC tru+0x23d6e0): the same request through brain+0x1254, nothing to translate.
// 16. 0.6.10 (K-8b): Lara's contact-hit sender tru+0x319050 gives the hit message 0x11c msg+0x44 = (int) A+0x10 (the
//    attack force) and msg+0x48 = (int) A+0x14 as the TU 0x823e169c..0x823e16c8 (retail / PC: 0 / 0); the knockback
//    tru+0x220650 takes msg+0x44 as its speed when > 0, so records with s+0x30 = 0 (types 21 / 26) knock back again -
//    [Hit] TranslateHitSpeed, default on, live. Still open: the TU's type-27 substitute record [CM+0xc8] of the same
//    block (0x823e160c..0x823e1674).
// 17. 0.6.11 (Q19, finisher Y past the target / out of the world): state 1008 as the TU table entry {0x8245f7b0, 0,
//    0x82455a38, 0x8245fa40, 0, 0} - enter / tick steer Lara's motion channel onto the target of targeter TU 7 (PC slot
//    6), the PC's slot 4 tru+0x36d9a0 (retail, removed by the TU) is not run - [States] Translate1008, default off,
//    live; every level (the TU has no doppelganger test there).
// 18. 0.6.12 (Q37, the thrall got up again after the finisher Y): the TU-new exit of state 1015 0x8245fe58
//    ("ThrallFatalityEnd") - the finisher's target in CM+0x48 still valid -> death switch kind 0 (LP 0, Death state)
//    with v = Lara - target, z = 0, then the retail clear (PC slot 2 tru+0x35e0f0) - [States] Translate1015Exit,
//    default off, live.
// 19. 0.6.13 (group C, PC-side only): Q108 read-only adrenaline log ([Adrenaline] Log, default on: poll thread + lines at
//    the Vaulted Enter, the 1014 enter and the strike shot); Q109 pointer assist (call 0x70d863, [Adrenaline]
//    AssistPointer, default off, live); Q68 lock-on switch input (calls 0x71cd07 / 0x71cd20, [Lock] MouseSwitch /
//    RightKey / LeftKey, the game's by default, live); Q99 option A (byte 0x696f69, [Chunk] RemoveLastPiece, default
//    off, live). PC options, not TU translations (section "group C").
// 20. 0.6.14 (group L, F6, PC-side only): adrenaline fill / drain on the game's own rules - message 0xd9 (damage
//    dealt) x [Adrenaline] FillPercent at its post 0x63b03a, drain rates player data +0x2d4 / +0x2d8 x DrainPercent /
//    DrainModePercent at the bar's loads 0x6f2965 / 0x6f2972 (100 = the data), condition 538 (meter full, the first
//    condition of the vault-off strike) answered 1 with StrikeWithoutFullMeter=1; log lines per 0xd9 fill and per
//    strike prompt (CM+0x1fc bit 28 from condition 2302). All defaults = the game, all live (section "group L").
//
// Every engine address is byte-checked before use; a failed check switches the affected part off with a logged
// reason. Options: TruShadowCombat.ini next to the .asi (README.md).

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <math.h>
#include <intrin.h>
#include "../TruLog.h"                      // Q107: date + time in every log line, session header
#pragma intrinsic(_ReturnAddress, _AddressOfReturnAddress)

namespace {

const char kVersion[] = "TruShadowCombat 0.6.14 (TU target list 7 -> 10, conditions 2005 / 2006 / 2011 / 2013 / 538, "
                        "states 1017 / 244 / 1007, shadow strike 1014 (Translate, TruShadowPowerMeterApi v1-v3), "
                        "finisher 1013 probe + doppelganger translation (Translate1013); 0.4.1: both switches read "
                        "again at run time; 0.5: states 1019 / 1020 (Translate1019 / Translate1020, log only by default); 0.5.1: states 231 / 1004 slots 0 / 1 "
                        "(Translate231Slot0 / Translate231Slot1 / Translate1004, PC handler by default), strike look off "
                        "0x823d9050 through TruShadowPowerMeterApi v4; 0.5.2: F21 diagnostics of targeter 9 / condition "
                        "2011, log only ([Diag]); 0.5.3: read-only export TscTargeterSnapshot (targeter 9 buckets / "
                        "rejected with reason / target, hit list, last condition 2011) for TruMenu's thrall labels, "
                        "WHY walks the rejected list by its next link +4; 0.6: K14 damage-type switch tru+0x237590 - burst log of "
                        "the incoming damage types ([Damage] Log) and the TU switch 0..27 ([Damage] Translate, off by "
                        "default); 0.6.1: lethal impulse tru+0x224c60 as the TU 0x82305ba0 - death switch instead of a "
                        "chunkdoll inside the physics step ([Chunk] Translate, on by default); 0.6.2: MeleeSplashDamage "
                        "tru+0x2e68b0 as the TU 0x823e1220 - main target excluded from the splash, doppelganger type "
                        "remap with the K14 switch ([Splash] Translate, on by default); 0.6.3: notification 33 before "
                        "EnterRegenerateDeath tru+0x2203fb as the TU 0x822f6578 ([Death] TranslateNotify33, on by "
                        "default), [Damage] Translate on by default; 0.6.4: enemy MeleeAttack as the TU - messages "
                        "0x15 / 0x8a / 0xbe only without a data pointer (T-M1, TU 0x82330d40), Enter sets brain+0xc "
                        "bit 0 unless record+8 bit 2 (T-M2, TU 0x8232fb48) ([Melee] Translate, on by default); "
                        "0.6.5: thrall companion (T4) as a stateless object-table lookup ([Companion] Translate / "
                        "Log), notification 34 at the RegenerateDeath exit (TranslateNotify34), finisher block + "
                        "notification 38 in RegenerateDeath / Regenerate (TranslateNotify38), companion regeneration "
                        "list (TranslateRegenList), T2 Land + Land slot 13 + Land exception (TranslateLand), T-M3 "
                        "MeleeAttack interruption ([Melee] TranslateInterrupt), all on by default; 0.6.6: T5 immediate "
                        "death kind 7 in the hit reaction tru+0x23ad50 (TU 0x823038d8, [Death] TranslateT5), P1c "
                        "Vaulted Enter as the TU 0x8232b630 with the step chain 0xbe / 0xf4 records, switch, data "
                        "copier ([Death] TranslateVaulted; step table only from fixed extension data), Vaulted clock "
                        "5 s without slow motion in the Enter and the enemy update tru+0x238d40 ([Death] "
                        "TranslateVaultedClock), all on by default; 0.6.7: hit structures for damage types 18..27 "
                        "from the companion's hit records as the TU 0x82301dc0 ([Hit] Translate), knockback force per "
                        "type from record +0x40 as the TU 0x822f77e4 ([Hit] TranslateKnockback), one log line per hit "
                        "decision ([Hit] Log), chunkdoll limit 4 -> 8 as the TU 0x82376700 ([Chunk] Limit8, start "
                        "only), all on by default; 0.6.8: no impulse message 0x91 from Lara's contact hit "
                        "tru+0x3192da to targets with flag 0x400000 as the TU 0x823e1870 ([Hit] "
                        "TranslateImpulseGate, on by default), hit line prints the subtype msg+0x64; 0.6.9: log points "
                        "(nothing changed in the game) at the Death state's chunkdoll build tru+0x26c9f9 ([Death] Log), "
                        "the hit-list add of Lara's contact hit tru+0x3190ad ([Hit] Log) and the death switch "
                        "tru+0x241650 ([Death] Log); 0.6.10: Lara's contact hit gives the hit message msg+0x44 / "
                        "+0x48 = (int) A+0x10 / A+0x14 as the TU 0x823e169c (tru+0x319169, knockback speed; [Hit] "
                        "TranslateHitSpeed, on by default); 0.6.11: state 1008 (finisher Y move) as the TU 0x8245f7b0 / "
                        "0x8245fa40 - steer onto the target of targeter TU 7 every tick, PC slot 4 tru+0x36d9a0 not run "
                        "([States] Translate1008, off by default); 0.6.12: state 1015 exit as the TU 0x8245fe58 - death "
                        "switch kind 0 on the finisher's target before the PC clear ([States] Translate1015Exit, off by "
                        "default); 0.6.13: group C - Q108 read-only adrenaline log (poll of CM+0x1fc bits 21 / 22 / 27, "
                        "reticle bits 6 / 7, pointer / radius, world / player time scale; lines at the Vaulted Enter, the "
                        "1014 enter and the strike shot; [Adrenaline] Log, on by default), Q109 pointer assist "
                        "([Adrenaline] AssistPointer, off by default), Q68 lock-on switch input ([Lock] MouseSwitch / "
                        "RightKey / LeftKey, the game's by default), Q99 option A ([Chunk] RemoveLastPiece, off by "
                        "default); 0.6.14: group L - F6 adrenaline fill / drain percent on the game's 0xd9 fill and "
                        "the data drain rates ([Adrenaline] FillPercent / DrainPercent / DrainModePercent, 100 by "
                        "default), strike without a full meter (StrikeWithoutFullMeter, off by default), fill and "
                        "strike-prompt log lines)";
const DWORD kImageBase = 0x00400000;

// ---------------------------------------------------------------- options / log
int g_enabled = 1;
int g_logLevel = 1;          // 0 errors, 1 info, 2 + every result change, 3 + every call (rate-limited)
int g_targetList = 1;        // [TargetList] Enabled
int g_conditions = 1;        // [Conditions] Enabled
int g_strikeGate = 1;        // [Strike] Gate
int g_statesOn = 1;          // 0.2 [States] Enabled: TU states 1017 / 244 / 1007 (slots 4 / 5)

char g_logPath[MAX_PATH];
char g_iniPath[MAX_PATH];    // 0.4.1: read again at run time (ReadSwitches)
CRITICAL_SECTION g_logLock;

void Log(int level, const char *fmt, ...) {
    if (level > g_logLevel || !g_logPath[0]) return;
    char line[700];
    int n = TruLogStamp(line, sizeof(line));     // Q107: "YYYY-MM-DD HH:MM:SS.mmm "
    va_list ap;
    va_start(ap, fmt);
    if (n > 0) _vsnprintf_s(line + n, sizeof(line) - n, _TRUNCATE, fmt, ap);
    va_end(ap);
    EnterCriticalSection(&g_logLock);
    FILE *f = nullptr;
    if (fopen_s(&f, g_logPath, "a") == 0 && f) {
        TruLogSessionStart(f, "TruShadowCombat", kVersion);
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

// hex string, spaces ignored
size_t ParseHex(const char *hex, BYTE *out, size_t size) {
    size_t n = 0;
    for (const char *p = hex; *p && p[1] && n < size;) {
        if (*p == ' ') { ++p; continue; }
        char two[3] = {p[0], p[1], 0};
        out[n++] = static_cast<BYTE>(strtoul(two, nullptr, 16));
        p += 2;
    }
    return n;
}

bool HexAt(DWORD address, const char *hex) {
    BYTE buf[256];
    size_t n = ParseHex(hex, buf, sizeof(buf));
    return BytesAt(address, buf, n);
}

bool WriteCode(DWORD address, const void *bytes, size_t length) {
    DWORD old = 0;
    void *p = reinterpret_cast<void *>(address);
    if (!VirtualProtect(p, length, PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "VirtualProtect failed (%lu) at 0x%08lx", GetLastError(), address);
        return false;
    }
    memcpy(p, bytes, length);
    DWORD dummy = 0;
    VirtualProtect(p, length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), p, length);
    return true;
}

bool WriteJump(DWORD from, const void *to) {
    BYTE j[5] = {0xe9};
    DWORD rel = reinterpret_cast<DWORD>(to) - (from + 5);
    memcpy(j + 1, &rel, 4);
    return WriteCode(from, j, 5);
}

// rate-limited probe: first call always, then every result change at level 2, every 2 s at level 3
struct Probe { const char *name; volatile LONG calls; LONG lastResult; DWORD lastTick; };
void Hit(Probe &p, int result, const char *fmt = nullptr, DWORD a = 0, DWORD b = 0, DWORD c = 0) {
    LONG n = InterlockedIncrement(&p.calls);
    char detail[200] = "";
    if (fmt) _snprintf_s(detail, sizeof(detail), _TRUNCATE, fmt, a, b, c);
    DWORD now = GetTickCount();
    if (n == 1) {
        Log(1, "%s: first call -> %d%s%s", p.name, result, detail[0] ? " - " : "", detail);
    } else if (result != p.lastResult) {
        Log(2, "%s: -> %d (call %ld)%s%s", p.name, result, n, detail[0] ? " - " : "", detail);
    } else if (g_logLevel >= 3 && now - p.lastTick >= 2000) {
        Log(3, "%s: still %d (call %ld)%s%s", p.name, result, n, detail[0] ? " - " : "", detail);
    } else {
        p.lastResult = result;
        return;
    }
    p.lastResult = result;
    p.lastTick = now;
}

// ---------------------------------------------------------------- engine globals (PC = TU)
const DWORD kGameTrackerPtr = 0x00fadb58;    // TU 0x829892b0
const DWORD kPlayerPtr = 0x00e7f094;         // TU 0x82efb464 (= [0x82efb458 + 0xc])
const DWORD kListPtr = 0x00fadfac;           // TU 0x829ca648 / retail 0x829ca560: targeter array
const DWORD kParamBase = 0x00fad764;         // TU / retail 0x82998ebc: player globals, +0x460.. targeter params
const DWORD kFreeList = 0x00cda0c4;          // TU 0x829beb64: free list of the weak-reference nodes

BYTE *GameTracker() { return *reinterpret_cast<BYTE *const *>(kGameTrackerPtr); }
BYTE *Player() { return *reinterpret_cast<BYTE *const *>(kPlayerPtr); }

// TruDlc2Player's doppelganger flag (TU gameTracker+0x1244)
typedef int(__cdecl *DoppelgangerFn)();
DoppelgangerFn g_dgFn = nullptr;
int g_dgLooked = 0;
int Doppelganger() {
    if (!g_dgFn && g_dgLooked < 100) {
        ++g_dgLooked;
        HMODULE m = GetModuleHandleA("TruDlc2Player.asi");
        if (m) g_dgFn = reinterpret_cast<DoppelgangerFn>(GetProcAddress(m, "TruDlc2PlayerDoppelganger"));
        if (!g_dgFn && g_dgLooked == 100) Log(0, "TruDlc2Player.asi / TruDlc2PlayerDoppelganger not found - doppelganger mode never seen");
    }
    return g_dgFn ? g_dgFn() : 0;
}

// The TU meter object (gameTracker+0x508) is owned by TruShadowPower (its translation of 0x823d7700..). It does not
// export it yet; this is the interface the strike / condition 538 need (proposal, docs Befund-Schattenkampf.md 5).
struct TruShadowPowerMeter {
    DWORD size;                       // sizeof the exporter's struct
    DWORD version;                    // 1
    volatile DWORD *flags;            // TU meter +0x04 (1 active, 2 strike, 4 strike look, 8 value >= tuning +0x2c, ..)
    float *value;                     // +0x08
    float *startValue;                // +0x0c
    float (*request)[2];              // +0x40: 7 time-scale request slots {player, world}
    void(__cdecl *selector)();        // 0x823d7520
    void(__cdecl *drain)(float amount);   // 0x823d8380
    // version 2 (TruShadowPower 0.11; layout only, not used here)
    float *delay;
    void(__cdecl *delayStart)();
    char(__cdecl *strikeReady)();
    char(__cdecl *canStart)();
    float(__cdecl *delayLeft)();
    // version 3 (proposal, docs Befund-Schattenkampf.md section 5): TruShadowPower's gameTracker+0x1280 copy
    volatile LONG *gt1280;
    // version 4 (TruShadowPower 0.14): TU 0x823d9050 (strike look off; returns at once unless meter flag 4, as the TU)
    void(__cdecl *strikeLookOff)();
};
const DWORD kMeterV1Size = 8 * 4;
const DWORD kMeterV3Size = 14 * 4;     // up to gt1280 (0.5.1: no longer sizeof - the struct grew with version 4)
const DWORD kMeterV4Size = 15 * 4;     // up to strikeLookOff (60)
typedef const TruShadowPowerMeter *(__cdecl *MeterApiFn)();
const TruShadowPowerMeter *g_meter = nullptr;
int g_meterLooked = 0;
const TruShadowPowerMeter *Meter() {
    if (!g_meter && g_meterLooked < 50) {
        ++g_meterLooked;
        HMODULE m = GetModuleHandleA("TruShadowPower.asi");
        MeterApiFn fn = m ? reinterpret_cast<MeterApiFn>(GetProcAddress(m, "TruShadowPowerMeterApi")) : nullptr;
        const TruShadowPowerMeter *api = fn ? fn() : nullptr;
        if (api && api->version >= 1 && api->size >= kMeterV1Size && api->flags && api->value && api->startValue &&
            api->request && api->selector && api->drain) {
            g_meter = api;
            Log(1, "TruShadowPower meter interface found (version %lu, size %lu)%s", api->version, api->size,
                (api->version >= 3 && api->size >= kMeterV3Size && api->gt1280)
                    ? " - gameTracker+0x1280 shared"
                    : " - no gameTracker+0x1280 (version 3): state 244 keeps its step count locally, condition 1048 "
                      "(TruShadowPower) does not see it");
            Log(1, "meter interface: strike look off (TU 0x823d9050) %s", (api->version >= 4 && api->size >= kMeterV4Size &&
                api->strikeLookOff) ? "found (version 4) - called by the strike tick / end as the TU"
                                    : "not offered (version < 4 or size < 60) - the strike skips it");
        } else if (fn && api && g_meterLooked == 1) {
            Log(0, "TruShadowPowerMeterApi returned an incomplete interface (version %lu, size %lu, expected >= %lu) - "
                   "not used", api->version, api->size, kMeterV1Size);
            g_meterLooked = 50;
        } else if (g_meterLooked == 50) {
            Log(1, "no meter interface: TruShadowPower.asi exports no TruShadowPowerMeterApi (0.9 does not) - the "
                   "doppelganger branch of condition 538 (meter flag 8) answers 0, the shadow strike is not run, "
                   "states 244 keep gameTracker+0x1280 locally");
        }
    }
    return g_meter;
}

// ---------------------------------------------------------------- tuning (object 858, as TruShadowPower)
// TU 0x82415518 returns the extension instance's data; the PC keeps the same data at the loaded object (+0x5c) of the
// object table entry id 858, state 2, data type 60 at +2 (checks of TU 0x82412b44..0x82412b7c).
const DWORD kFindObject = 0x0054e930;        // PC lookup that walks the table (checked: base / stride / count)
const char *const kFindObjectHex = "8b542404 33c0 b90c74db00";
const DWORD kFindObjectLoop = 0x0054e951;
const char *const kFindObjectLoopHex = "83c124 3dcc000000";
const DWORD kObjectTable = 0x00db7400;
const int kObjectCount = 0xcc;
const SHORT kExtensionObject = 858;
const WORD kTuningType = 60;
bool g_tableOk = false;

const BYTE *Tuning() {
    if (!g_tableOk) return nullptr;
    __try {
        for (int i = 0; i < kObjectCount; ++i) {
            const BYTE *entry = reinterpret_cast<const BYTE *>(kObjectTable + i * 0x24);
            if (*reinterpret_cast<const SHORT *>(entry + 0xc) != kExtensionObject) continue;
            if (*reinterpret_cast<const WORD *>(entry + 0xe) != 2) return nullptr;
            const BYTE *object = *reinterpret_cast<const BYTE *const *>(entry + 8);
            if (!object) return nullptr;
            const BYTE *data = *reinterpret_cast<const BYTE *const *>(object + 0x5c);
            if (!data || !*reinterpret_cast<const DWORD *>(object + 0x60)) return nullptr;
            if (*reinterpret_cast<const WORD *>(data + 2) != kTuningType) return nullptr;
            return data;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return nullptr;
}

// ---------------------------------------------------------------- 1. target list
const int kRetailTargeters = 7, kTuTargeters = 10;
bool g_listOk = false;       // patches applied: [0xfadfac] arrays are built with 10 entries

// TU index -> PC slot (slots 0..6 keep the PC / retail meaning)
int SlotOf(int tu) {
    if (tu == 6) return 7;
    if (tu == 7) return 6;
    return tu;
}
int TuOf(int slot) { return SlotOf(slot); }   // the mapping is its own inverse

struct Patch { DWORD at; const char *expect; DWORD write; const char *with; const char *what; };
const Patch kListPatches[] = {
    {0x00722630, "6a1c ffd0 3bc3 740e 8bc8 e8f1b5ffff", 0x00722631, "28", "player init: array 0x1c -> 0x28 bytes (TU 0x824135f0)"},
    {0x0071dc78, "83fe07 7cc3", 0x0071dc7a, "0a", "list ctor tru+0x31dc30: 7 -> 10 targeters (TU 0x8240633c)"},
    {0x00716915, "bd71000000", 0x00716916, "f1030000", "instance add tru+0x316860: candidate mask 0x71 -> 0x3f1 (TU 0x824064a4)"},
    {0x00716946, "83fe07 7ce6", 0x00716948, "0a", "instance add tru+0x316860: marker loop 7 -> 10 (TU 0x824064dc)"},
    {0x007169a2, "bf71000000", 0x007169a3, "f1030000", "instance add tru+0x316860: mask 0x71 -> 0x3f1 (TU 0x8240656c)"},
    {0x007169d0, "83fe07 7ceb", 0x007169d2, "0a", "instance add tru+0x316860: loop 7 -> 10 (TU 0x82406594)"},
    {0x0071aca9, "83fe07 7ce9", 0x0071acab, "0a", "tru+0x31ac80 (all targeters, from tru+0x31f1d0 = TU 0x823ed958): 7 -> 10"},
    {0x0071dcce, "83fe07 7ced", 0x0071dcd0, "0a", "tru+0x31dcb0 (all targeters, TU 0x823c3eb8 / 0x823c6790 / 0x822ebc58 / 0x823ed958): 7 -> 10"},
    {0x00716843, "83f807 89442410 7c95", 0x00716845, "0a", "list destroy tru+0x3167d0: 7 -> 10 (TU 0x82412f4c)"},
    {0x007228a3, "83fe07 7ce8", 0x007228a5, "0a", "player update: per-frame targeter loop 7 -> 10 (TU 0x82412878)"},
};

// PC parameter function tru+0x2ecc10 (retail 0x823ff7d8): cdecl(s8 index), switch 0..6 over [0xfad764] +0x460..
const DWORD kParamFn = 0x006ecc10;
const char *const kParamFnHex = "0fbe442404 83f806 775f ff24857ccc6e00 a164d7fa00 8b8060040000 c3 8b0d64d7fa00 8b8164040000 c3 "
                                "8b1564d7fa00 8b8268040000 c3 a164d7fa00 8b806c040000 c3 8b0d64d7fa00 8b8170040000 c3 "
                                "8b1564d7fa00 8b8274040000 c3 a164d7fa00 8b8078040000 c3 33c0 c3";
const DWORD kParamFnCaller = 0x0071dc5c;     // its only caller: push esi; call; add esp, 4 (list ctor)
const char *const kParamFnCallerHex = "56 e8aeeffcff 83c404 50 56 8bcf e892fcffff";

volatile LONG g_paramLogs = 0;

// TU 0x82402208(s8 index): with a player, a game tracker and the tuning, the first entry of tuning +0x90 (count
// +0x94; 8-byte entries {u8 index, 3 bytes, param}) with that index wins; otherwise 0..5 -> +0x460 + 4 i, 6 -> +0x468,
// 7 -> +0x478, else 0.
DWORD __cdecl ParamHook(int arg) {
    const int slot = static_cast<signed char>(arg);
    const int tu = TuOf(slot);
    DWORD param = 0;
    const char *source = "none";
    __try {
        const BYTE *tuning = (Player() && GameTracker()) ? Tuning() : nullptr;
        if (tuning) {
            const DWORD count = *reinterpret_cast<const DWORD *>(tuning + 0x94);
            const BYTE *table = *reinterpret_cast<const BYTE *const *>(tuning + 0x90);
            if (count > 64) {
                // the converted file of 50k has 0x200 here (u32 2 converted as a u16 pair) - tree 50l fixes it
                Log(0, "tuning +0x94 = %lu entries - implausible (converter error, fixed in tree dlc_test50l_combat): "
                       "table not used for targeter slot %d", count, slot);
            } else if (count && table) {
                for (DWORD i = 0; i < count; ++i) {
                    if (static_cast<signed char>(table[i * 8]) == tu) {
                        param = *reinterpret_cast<const DWORD *>(table + i * 8 + 4);
                        source = "DLC 2 tuning table (object 858 +0x90)";
                        break;
                    }
                }
            }
        }
        if (!param && strcmp(source, "none") == 0) {
            const BYTE *base = *reinterpret_cast<const BYTE *const *>(kParamBase);
            int offset = -1;
            if (tu >= 0 && tu <= 5) offset = 0x460 + 4 * tu;
            else if (tu == 6) offset = 0x468;
            else if (tu == 7) offset = 0x478;
            if (offset >= 0) {
                param = *reinterpret_cast<const DWORD *>(base + offset);
                source = tu == 6 ? "default +0x468 (TU: index 6 takes the parameters of 2)" : "default (retail table)";
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "targeter slot %d: access fault in the parameter lookup - no parameters", slot);
        param = 0;
        source = "fault";
    }
    if (InterlockedIncrement(&g_paramLogs) <= 40 || g_logLevel >= 2)
        Log(1, "targeter slot %d (TU index %d): parameters 0x%08lx - %s", slot, tu, param, source);
    return param;
}

bool SetupTargetList() {
    if (!g_targetList) { Log(1, "target list: off ([TargetList] Enabled=0) - conditions 2005 / 2006 / 2011 (doppelganger) / 2013 answer 0"); return false; }
    for (const Patch &p : kListPatches)
        if (!HexAt(p.at, p.expect)) {
            Log(0, "target list: bytes at 0x%08lx do not match (%s) - nothing patched", p.at, p.what);
            return false;
        }
    if (!HexAt(kParamFn, kParamFnHex) || !HexAt(kParamFnCaller, kParamFnCallerHex) ||
        !HexAt(kFindObject, kFindObjectHex) || !HexAt(kFindObjectLoop, kFindObjectLoopHex)) {
        Log(0, "target list: parameter function tru+0x2ecc10 / its caller / the object table lookup do not match - nothing patched");
        return false;
    }
    __try {
        if (*reinterpret_cast<const DWORD *>(kListPtr) != 0) {
            Log(0, "target list: [0xfadfac] is already built (0x%08lx) - too late, nothing patched",
                *reinterpret_cast<const DWORD *>(kListPtr));
            return false;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    // parameter function first (only the ctor calls it), then the constants
    if (!WriteJump(kParamFn, reinterpret_cast<const void *>(&ParamHook))) return false;
    for (const Patch &p : kListPatches) {
        BYTE b[8];
        size_t n = ParseHex(p.with, b, sizeof(b));
        if (!WriteCode(p.write, b, n)) {
            Log(0, "target list: write at 0x%08lx failed - the game may be inconsistent, restart without the plugin", p.write);
            return false;
        }
        Log(2, "target list: 0x%08lx patched (%s)", p.write, p.what);
    }
    Log(1, "target list: %d -> %d targeters (TU 0x824062c8 / 0x82406390 / 0x82412ca0 / 0x824126d8), %d sites patched, "
           "parameter function tru+0x2ecc10 = TU 0x82402208 (slot 7 = TU 6, 8 / 9 = TU 8 / 9)",
        kRetailTargeters, kTuTargeters, static_cast<int>(sizeof(kListPatches) / sizeof(kListPatches[0])));
    return true;
}

// ---------------------------------------------------------------- PC building blocks of the target code
typedef BYTE *(__fastcall *TargetOfFn)(BYTE *player, int, int index);        // tru+0x31caf0 = TU 0x823dd260
typedef DWORD *(__fastcall *TargeterTargetFn)(BYTE *targeter, int);          // tru+0x319f00 = TU 0x82404568
typedef int(__fastcall *AcceptsFn)(BYTE **list, int, BYTE *target, int idx); // tru+0x313760 = TU 0x82406618
typedef int(__cdecl *QueryArgFn)(BYTE *inst, int id, void *arg);             // tru+0x1b3720 (query + [0xd98f9c] = arg)
typedef char(__fastcall *TargetCheckPcFn)(BYTE *player, int);                // tru+0x2f2800 = TU 0x823df8f8 (retail)
typedef char(__cdecl *PredFn)(const BYTE *record);
typedef char(__cdecl *CondTemplateFn)(void *agent, void *cache, const BYTE *record, PredFn pred);
typedef char(__cdecl *CondFn)(void *agent, void *cache, const BYTE *record);
typedef void(__cdecl *StateFn)(void *agent);

const DWORD kTargetOf = 0x0071caf0;
const char *const kTargetOfHex = "8b442404 50 e8a6feffff 85c0 740c 50 e8cc6ee9ff 83c404 c20400";
const DWORD kTargetOfInner = 0x0071c9a0;     // = TU 0x823dd138: bit 11, bit 6 (+0x20), +0x788, bit 10 -> list[0], list[idx]
const char *const kTargetOfInnerHex = "83ec08 53 8bd9 8b83fc010000 55 c1e80b 33ed a801";
const DWORD kTargetOfIndex = 0x0071cac4;     // mov ecx, [0xfadfac]; mov ecx, [ecx + eax*4]; call 0x719f00
const char *const kTargetOfIndexHex = "8b0dacdffa00 8b0c81 e82ed4ffff";
const DWORD kTargeterTarget = 0x00719f00;
const char *const kTargeterTargetHex = "56 8bf1 8b8690000000 85c0 7438 83c008 50 e88a2dfdff";
const DWORD kAccepts = 0x00713760;
const char *const kAcceptsHex = "8b442404 53 8b5c240c 56 57 8bf9 8b0c9f 6a00 50 e8a897fdff 8bf0 85f6 7432 56 e81c95fdff";
const DWORD kQueryArg = 0x005b3720;
const char *const kQueryArgHex = "8b4c2404 8b44240c 8d9110010000 85d2 a39c8fd900 740a 8b811c010000 85c0";
const DWORD kWeakRefInline = 0x0071ca5c;     // the PC inline of TU 0x8237e050 on player +0x20 (same node / free list)
const char *const kWeakRefInlineHex = "834004ff 750d 8b15c4a0cd00 8910 a3c4a0cd00";
const DWORD kCondTemplate = 0x00782d70;      // = TU 0x82487718
const char *const kCondTemplateHex = "51 53 55 8b6c2418 56 8b742418 8b5e08 57 8b7c2418 393e c644241300 750b 8b4604 3b870c050000 7423 55 ff542428";
// TU 0x823df8f8 = tru+0x2f2800 (retail body) + the TU's doppelganger branch (same translation as TruShadowPower 0.9)
const DWORD kTargetCheckPc = 0x006f2800;
const char *const kTargetCheckPcHex =
    "53 8b1d58dbfa00 8b8300050000 56 8bb034010000 83fe0c 57 8bf9 0f8491000000 83fe07 0f8488000000 83fe03 747d "
    "83fe04 7478 e898f6ffff 84c0 756f 8b87fc010000 8bc8 c1e91e f6c101 755f 8bd0 c1ea15 f6c201 7555 c1e818 a801 754e "
    "83feff 744f d9ee d89b88050000 dfe0 f6c405 7b3a 803de6b48a0000 7437 f60544f1e70001 752e 803d43f1e70004 7425 "
    "a1682ba000 8b4818 8b11 8b8230060000 2404 33c9 3c04 0f94c1 8bc1 85c0 7406 5f 5e b001 5b c3 5f 5e 32c0 5b c3";
// PC (retail) condition handlers / predicates replaced in doppelganger mode
const DWORD kCond2011Pc = 0x007659e0, kPred2011Pc = 0x00765970;
const char *const kCond2011PcHex = "8b44240c 8b4c2408 8b542404 6870597600";
const char *const kPred2011PcHex = "51 a158dbfa00 8b8804050000 8b91fc010000 c1ea0a f6c201 7504 32c0 59 c3 56 6a05 e85a71fbff";
const DWORD kCond538Pc = 0x00765fb0, kPred538Pc = 0x00765fa0;
const char *const kCond538PcHex = "8b44240c 8b4c2408 8b542404 68a05f7600";
const char *const kPred538PcHex = "a158dbfa00 8b8804050000 e91007f8ff";

bool g_blocksOk = false;

BYTE **List() { return *reinterpret_cast<BYTE **const *>(kListPtr); }

// object of a handle {object, id} if still valid (PC tru+0x1b39d0 = the TU's inline `+0x44 == id`)
BYTE *HandleObject(const DWORD *h) {
    if (!h) return nullptr;
    BYTE *o = reinterpret_cast<BYTE *>(h[0]);
    if (!o || *reinterpret_cast<const DWORD *>(o + 0x44) != h[1]) return nullptr;
    return o;
}

bool Excluded(const BYTE *o) { return (*reinterpret_cast<const DWORD *>(o + 0x14) & 0x400000) != 0; }

// TU 0x8237e050(x): weak reference node at x+0xc {handle *, count}: handle -> return it; else count - 1, at 0 the
// node goes to the free list [0xcda0c4] (TU 0x829beb64), x+0xc = 0, return 0
DWORD *WeakRef(BYTE *x) {
    DWORD *node = *reinterpret_cast<DWORD **>(x + 0xc);
    if (!node) return nullptr;
    if (node[0]) return reinterpret_cast<DWORD *>(node[0]);
    if (--node[1] == 0) {
        node[0] = *reinterpret_cast<DWORD *>(kFreeList);
        *reinterpret_cast<DWORD *>(kFreeList) = reinterpret_cast<DWORD>(node);
    }
    *reinterpret_cast<DWORD **>(x + 0xc) = nullptr;
    return nullptr;
}

// TU 0x82404568(list[tu]) + handle check
BYTE *TargeterObject(int tu) {
    BYTE **list = List();
    if (!list) return nullptr;
    BYTE *t = list[SlotOf(tu)];
    if (!t) return nullptr;
    return HandleObject(reinterpret_cast<TargeterTargetFn>(kTargeterTarget)(t, 0));
}

// TU 0x823dd260(player, tu)
BYTE *TargetOf(BYTE *player, int tu) {
    return reinterpret_cast<TargetOfFn>(kTargetOf)(player, 0, SlotOf(tu));
}

// TU 0x82406618(list, target, tu)
bool Accepts(BYTE *target, int tu) {
    BYTE **list = List();
    if (!list || !list[SlotOf(tu)]) return false;
    return reinterpret_cast<AcceptsFn>(kAccepts)(list, 0, target, SlotOf(tu)) != 0;
}

// TU 0x823df8f8 with the doppelganger branch (0x823df918..0x823df970)
bool InputWord(DWORD offset, DWORD *value) {
    const BYTE *p = *reinterpret_cast<const BYTE *const *>(0x00a02b68);   // TU 0x8286dd90
    if (!p) return false;
    const BYTE *list = *reinterpret_cast<const BYTE *const *>(p + 0x18);
    if (!list) return false;
    const BYTE *rec = *reinterpret_cast<const BYTE *const *>(list);
    if (!rec) return false;
    *value = *reinterpret_cast<const DWORD *>(rec + offset);
    return true;
}

bool TargetCheck(const BYTE *gt, BYTE *player) {
    if (!Doppelganger()) return reinterpret_cast<TargetCheckPcFn>(kTargetCheckPc)(player, 0) != 0;
    const int mode = *reinterpret_cast<const int *>(*reinterpret_cast<const BYTE *const *>(gt + 0x500) + 0x134);
    if (mode == 0xc || mode == 7) return false;
    const DWORD w = *reinterpret_cast<const DWORD *>(player + 0x1fc);
    if (((w >> 9) & 1) || ((w >> 10) & 1)) return true;
    if ((w >> 30) & 1) return true;
    if ((w >> 24) & 1) return true;
    if (mode == -1) return false;
    if (0.0f < *reinterpret_cast<const float *>(gt + 0x588)) return true;
    if (*reinterpret_cast<const volatile BYTE *>(0x008ab4e6) == 0) return false;   // TU 0x8275422a
    if (*reinterpret_cast<const volatile BYTE *>(0x00e7f144) & 1) return false;    // TU 0x82efb514
    if (*reinterpret_cast<const volatile BYTE *>(0x00e7f143) == 4) return false;   // TU 0x82efb513
    DWORD word = 0;
    if (!InputWord(0x630, &word)) return false;
    return (word & 4) == 4;
}

bool CheckBlocks() {
    struct { DWORD at; const char *hex; const char *what; } const checks[] = {
        {kTargetOf, kTargetOfHex, "tru+0x31caf0 (TU 0x823dd260)"},
        {kTargetOfInner, kTargetOfInnerHex, "tru+0x31c9a0 (TU 0x823dd138)"},
        {kTargetOfIndex, kTargetOfIndexHex, "tru+0x31cac4 list[index]"},
        {kTargeterTarget, kTargeterTargetHex, "tru+0x319f00 (TU 0x82404568)"},
        {kAccepts, kAcceptsHex, "tru+0x313760 (TU 0x82406618)"},
        {kQueryArg, kQueryArgHex, "tru+0x1b3720 (query with argument)"},
        {kWeakRefInline, kWeakRefInlineHex, "free list [0xcda0c4] (TU 0x8237e050)"},
        {kCondTemplate, kCondTemplateHex, "condition template tru+0x382d70 (TU 0x82487718)"},
        {kTargetCheckPc, kTargetCheckPcHex, "tru+0x2f2800 (TU 0x823df8f8)"},
        {0x006f1ed0, "8b81fc010000 8bc8 c1e909 f6c101 750a c1e80a a801 7503 33c0 c3 b801000000 c3", "tru+0x2f1ed0 (bits 9 / 10)"},
        {0x00718c39, "8b0d682ba000 8b5118 8b0a 8b91f0060000 80e210", "input chain [[0xa02b68]+0x18]->[0]"},
        {kCond2011Pc, kCond2011PcHex, "condition 2011 tru+0x3659e0"},
        {kPred2011Pc, kPred2011PcHex, "predicate 2011 tru+0x365970"},
        {kCond538Pc, kCond538PcHex, "condition 538 tru+0x365fb0"},
        {kPred538Pc, kPred538PcHex, "predicate 538 tru+0x365fa0"},
    };
    for (const auto &c : checks)
        if (!HexAt(c.at, c.hex)) {
            Log(0, "conditions: %s at 0x%08lx does not match - conditions not translated", c.what, c.at);
            return false;
        }
    return true;
}

// ---------------------------------------------------------------- 0.5.2: F21 diagnostics, part 1 (log only)
// Live (los15e, 05.11.2026): condition 2011 found targeter 9 empty, the finisher 1013 never ran. TU and PC fill the
// targeters with the same code (docs Befund-F21-Finisher-Log-0511.md, main workspace): tru+0x316860 (TU 0x82406390,
// mask 0x71 -> 0x3f1, patched) offers an instance to every targeter, tru+0x3164d0 (TU 0x82404650) takes it when the
// mask has the targeter's bit (+4 = 1 << index); every frame tru+0x31a270 (TU 0x82404c60) sorts each candidate into
// the bucket of the first filter group it passes (eligibility tru+0x2ecca0, filter tru+0x312090) or into the
// rejected list +0x3c; tru+0x316590 (TU 0x82405b90) picks the first bucket entry that passes the sight test,
// tru+0x316730 (TU 0x82406190) sets the target node +0x90, tru+0x319f80 removes a node. The diagnostics only read
// and log (slot 9 = TU index 9); every original runs with the same arguments. [Diag] in TruShadowCombat.ini.
// Targeter layout (PC ctor tru+0x31d900, all byte-checked below): +0 index, +4 mask, +8 flags, +0xc candidates,
// +0x34 parameters {flags, groups, group pointers}, +0x38 buckets (0x14 each: +0 head, +8 count), +0x3c rejected list
// (+0x44 count), +0x50 frame, +0x90 target node; node: +0 next, +8 handle {object, id}, +0x14 marker data.
int g_diagT9 = 1;                  // [Diag] Targeter9
int g_diagWhy = 1;                 // [Diag] Targeter9Why
int g_diag2011 = 1;                // [Diag] Condition2011
int g_diagMax = 4000;              // [Diag] MaxLines
int g_diagSnap = 1;                // 0.5.3 [Diag] Snapshot (TscTargeterSnapshot export; built only while asked for)
volatile LONG g_diagLines = 0;
bool g_namesOk = false;            // object name table [0xdb94d0] (same check as TruTrace: tru+0x1bcff9)
const DWORD kObjNames = 0x00db94d0;

// every diagnostic line counts against [Diag] MaxLines; the line that reaches it says so once
bool DiagLog(const char *fmt, ...) {
    LONG n = InterlockedIncrement(&g_diagLines);
    if (n > g_diagMax) {
        if (n == g_diagMax + 1) Log(1, "0.5.2 diag: [Diag] MaxLines %d reached - no more diagnostic lines", g_diagMax);
        return false;
    }
    char line[640];
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf_s(line, sizeof(line), _TRUNCATE, fmt, ap);
    va_end(ap);
    Log(1, "%s", line);
    return true;
}

DWORD Rd(const void *p) {
    __try {
        return p ? *reinterpret_cast<const volatile DWORD *>(p) : 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
}

// "0x.. obj 1004 viking_thrall_tutorial_dlc2_" (object id = object +0x14 low word, as TruTrace)
void Describe(const BYTE *inst, char *out, size_t size) {
    if (!inst) { _snprintf_s(out, size, _TRUNCATE, "0"); return; }
    const BYTE *obj = reinterpret_cast<const BYTE *>(Rd(inst + 0x10));
    DWORD id = obj ? (Rd(obj + 0x14) & 0xffff) : 0;
    char name[64] = "?";
    if (g_namesOk && id) {
        const BYTE *table = reinterpret_cast<const BYTE *>(Rd(reinterpret_cast<const void *>(kObjNames)));
        DWORD count = table ? Rd(table) : 0;
        const char *s = (table && count < 8192 && id <= count) ? reinterpret_cast<const char *>(Rd(table + id * 8)) : nullptr;
        __try {
            if (s) {
                size_t i = 0;
                for (; s[i] && i + 1 < sizeof(name); ++i) name[i] = s[i];
                name[i] = 0;
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            strcpy_s(name, sizeof(name), "?");
        }
    }
    _snprintf_s(out, size, _TRUNCATE, "0x%08lx obj %lu %s", reinterpret_cast<DWORD>(inst), id, name);
}

// targeter state: target node / object, flags, candidates, bucket counts, rejected count
struct TState { DWORD node; BYTE *obj; DWORD flags, total, pflags, groups, bucket[4], rejected; };
bool IsSlot9(const BYTE *t) { return t && Rd(t) == 9; }
void ReadT(const BYTE *t, TState *s) {
    memset(s, 0, sizeof(*s));
    if (!t) return;
    s->node = Rd(t + 0x90);
    __try {
        s->obj = s->node ? HandleObject(reinterpret_cast<const DWORD *>(s->node + 8)) : nullptr;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        s->obj = nullptr;
    }
    s->flags = Rd(t + 8);
    s->total = Rd(t + 0xc);
    const BYTE *params = reinterpret_cast<const BYTE *>(Rd(t + 0x34));
    s->pflags = params ? Rd(params) : 0;
    s->groups = params ? Rd(params + 4) : 0;
    const BYTE *buckets = reinterpret_cast<const BYTE *>(Rd(t + 0x38));
    for (DWORD b = 0; buckets && b < s->groups && b < 4; ++b) s->bucket[b] = Rd(buckets + b * 0x14 + 8);
    s->rejected = Rd(t + 0x44);
}
void FormatT(const TState &s, char *out, size_t size) {
    char obj[96];
    Describe(s.obj, obj, sizeof(obj));
    _snprintf_s(out, size, _TRUNCATE, "+0x90 node 0x%08lx (target %s), flags 0x%lx, candidates %lu = buckets %lu/%lu/%lu/%lu "
                "(groups %lu) + rejected %lu, parameter flags 0x%08lx", s.node, obj, s.flags, s.total, s.bucket[0],
                s.bucket[1], s.bucket[2], s.bucket[3], s.groups, s.rejected, s.pflags);
}
BYTE *Slot9() {
    BYTE **list = g_listOk ? List() : nullptr;
    return list ? reinterpret_cast<BYTE *>(Rd(list + 9)) : nullptr;
}

// condition 2011 inputs (Pred2011): state of targeter 9 before / after the get call tru+0x319f00 (TU 0x82404568)
struct Diag2011 { BYTE *t; TState before, after; int query, excluded; };
volatile LONG g_d2011Calls = 0;
DWORD g_d2011Last[4] = {0xffffffff, 0, 0, 0};
DWORD g_d2011Tick = 0;
void Diag2011Log(const BYTE *record, const Diag2011 &d, DWORD path, BYTE *target, int r) {
    LONG n = InterlockedIncrement(&g_d2011Calls);
    DWORD now = GetTickCount();
    DWORD key[4] = {path, reinterpret_cast<DWORD>(target), d.after.node, static_cast<DWORD>(d.query)};
    bool changed = memcmp(key, g_d2011Last, sizeof(key)) != 0;
    if (!changed && now - g_d2011Tick < 2000) return;
    memcpy(g_d2011Last, key, sizeof(key));
    g_d2011Tick = now;
    char before[300], after[300], obj[96];
    FormatT(d.before, before, sizeof(before));
    FormatT(d.after, after, sizeof(after));
    Describe(target, obj, sizeof(obj));
    DiagLog("0.5.2 diag condition 2011 %s (call %ld): record 0x%08lx {+0 %u, +2 id %u, +4 value %u, +6 flags 0x%02x} -> %d, "
            "path %lu (1 targeter 9 empty / excluded, 2 query 0x161 = 0, 3 ok, 9 list off), target %s, excluded %d, query "
            "0x161 %d (-1 = not asked); targeter 9 0x%08lx before get: %s", changed ? "changed" : "still", n,
            reinterpret_cast<DWORD>(record), record ? (Rd(record) & 0xffff) : 0, record ? (Rd(record) >> 16) : 0,
            record ? (Rd(record + 4) & 0xffff) : 0, record ? ((Rd(record + 4) >> 16) & 0xff) : 0, r, path, obj, d.excluded,
            d.query, reinterpret_cast<DWORD>(d.t), before);
    if (d.after.node != d.before.node || d.after.flags != d.before.flags)
        DiagLog("0.5.2 diag condition 2011: targeter 9 after get (tru+0x319f00): %s", after);
}

// 0.5.3: the last condition 2011 evaluation in doppelganger mode, for TscTargeterSnapshot. Written by Pred2011 and
// copied by SnapBuild - both on the game thread (chart condition / targeter update).
struct Last2011 { DWORD calls, tick, path, result; LONG query; BYTE *target; };
Last2011 g_last2011 = {0, 0, 0, 0, -1, nullptr};

// ---------------------------------------------------------------- 2. predicates
Probe g_p2005 = {"condition 2005 (TU 0x8246e8e0: aim target / targeter 6 agree)"};
Probe g_p2006 = {"condition 2006 (TU 0x8246eb08: target is a data-type 0x4f / 0xb00b instance)"};
Probe g_p2013 = {"condition 2013 (TU 0x8246ea30: target of state 1017 = targeter 6)"};
Probe g_p2011 = {"condition 2011 (TU 0x8246f140: doppelganger -> targeter 9 + query 0x161)"};
Probe g_p538 = {"condition 538 (TU 0x8246faa8: doppelganger -> meter flag 8)"};

// TU-only gameTracker +0x1284 / +0x1288 (handle {object, id} of state 1017's target; the PC uses those offsets for
// other data). Zeroed with every new tracker on the TU (memset 0x82413878); only 1017 writes it - not ported in 0.1.
DWORD g_gt1284[2] = {0, 0};

bool IsBooBType(const BYTE *o) {
    const BYTE *d = *reinterpret_cast<const BYTE *const *>(o + 0x50);
    return d && *reinterpret_cast<const WORD *>(d + 4) == 0xb00b && *reinterpret_cast<const WORD *>(d + 2) == 0x4f;
}

char __cdecl Pred2005(const BYTE *) {
    char r = 0;
    DWORD why = 0;
    __try {
        BYTE *gt = GameTracker();
        BYTE *player = *reinterpret_cast<BYTE **>(gt + 0x504);
        if (!g_listOk) { why = 9; goto done; }
        if ((*reinterpret_cast<const DWORD *>(player + 0x1fc) >> 10) & 1) {
            if (WeakRef(player)) {
                BYTE *aim = HandleObject(WeakRef(player));
                if (aim && !Excluded(aim)) { why = 1; r = Accepts(aim, 6) ? 1 : 0; goto done; }
            }
        }
        BYTE *t = TargetOf(player, 6);
        if (!t || Excluded(t)) { why = 2; goto done; }
        BYTE *o = TargeterObject(6);
        if (!o || Excluded(o)) { why = 3; goto done; }
        why = 4;
        r = (o == t) ? 1 : 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        why = 8;
        r = 0;
    }
done:
    Hit(g_p2005, r, "path %lu (1 aim, 2 no target 6, 3 targeter 6 empty, 4 compare, 8 fault, 9 list off)", why);
    return r;
}

char __cdecl Pred2006(const BYTE *) {
    char r = 0;
    DWORD why = 0;
    __try {
        BYTE *gt = GameTracker();
        BYTE *player = *reinterpret_cast<BYTE **>(gt + 0x504);
        if (!g_listOk) { why = 9; goto done; }
        if (TargetCheck(gt, player) && WeakRef(player)) {
            BYTE *o = HandleObject(WeakRef(player));
            why = 1;
            // the TU reads +0x50 of a null object here (guest memory); the PC would fault - 0 is the TU's result there
            r = (o && IsBooBType(o)) ? 1 : 0;
        } else {
            BYTE *t = TargetOf(player, 6);
            why = 2;
            if (t && !Excluded(t)) {
                BYTE *o = TargeterObject(6);
                why = 3;
                if (o && !Excluded(o) && t == o && IsBooBType(t)) r = 1;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        why = 8;
        r = 0;
    }
done:
    Hit(g_p2006, r, "path %lu (1 check + aim, 2 no target 6, 3 targeter 6, 8 fault, 9 list off)", why);
    return r;
}

char __cdecl Pred2013(const BYTE *) {
    char r = 0;
    __try {
        BYTE *o = HandleObject(g_gt1284);
        if (g_listOk && o && !Excluded(o)) {
            BYTE *t = TargeterObject(6);
            r = (t && !Excluded(t) && t == o) ? 1 : 0;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        r = 0;
    }
    Hit(g_p2013, r, "state-1017 target 0x%08lx (state 1017 not ported in 0.1)", g_gt1284[0]);
    return r;
}

char __cdecl Pred2011(const BYTE *record) {
    const int dg = Doppelganger();
    if (!dg) return reinterpret_cast<PredFn>(kPred2011Pc)(record);      // retail = PC
    char r = 0;
    DWORD why = 0;
    BYTE *target = nullptr;
    Diag2011 d;                                                         // 0.5.2: log only
    memset(&d, 0, sizeof(d));
    d.query = -1;
    __try {
        if (!g_listOk) { why = 9; goto done; }
        if (g_diag2011) { d.t = Slot9(); ReadT(d.t, &d.before); }
        // TU 0x8246f170..: doppelganger -> targeter 9
        target = TargeterObject(9);
        if (g_diag2011) { ReadT(d.t, &d.after); d.excluded = (target && Excluded(target)) ? 1 : 0; }
        if (!target || Excluded(target)) { why = 1; goto done; }
        BYTE *player = Player();
        void *arg = player;                                             // TU [0x829bffa4] = &{player}
        why = 2;
        d.query = reinterpret_cast<QueryArgFn>(kQueryArg)(target, 0x161, &arg);
        if (d.query) { why = 3; r = 1; }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        why = 8;
        r = 0;
    }
done:
    Hit(g_p2011, r, "doppelganger, target 0x%08lx, path %lu (1 targeter 9 empty, 2 query 0x161 = 0, 3 ok, 8 fault, 9 list off)",
        reinterpret_cast<DWORD>(target), why);
    if (g_diag2011) Diag2011Log(record, d, why, target, r);
    ++g_last2011.calls;                                                 // 0.5.3: for TscTargeterSnapshot (no log)
    g_last2011.tick = GetTickCount();
    g_last2011.path = why;
    g_last2011.result = r ? 1 : 0;
    g_last2011.query = d.query;
    g_last2011.target = target;
    return r;
}

// 0.6.14 (group L, F6): [Adrenaline] StrikeWithoutFullMeter (PC option, default 0 = the game). Condition 538 = CM+0x1fc
// bit 22 (meter full) is the first condition of the only transition into the vault-off strike (chart record 786 =
// state 1014, from the combat records 711 / 724 / 730: {500,538,1} {2000,2001,1} {2000,2011,1} {700,701,0}
// {1500,1502,0} {2300,2302,1} {150,150,46}); its other use {150,150,46} {500,538,0} {2300,2304,1} is the "not full"
// feedback (Lara event 0x38). With 1 the main-game answer is 1 (the strike empties the meter itself, 0x71d5e2).
volatile LONG g_strikeAnyMeter = 0;
DWORD g_strikeAnyTick = 0;

char __cdecl Pred538(const BYTE *record) {
    const int dg = Doppelganger();
    if (!dg) {
        const char full = reinterpret_cast<PredFn>(kPred538Pc)(record);  // player +0x1fc bit 22 (retail = PC)
        if (full || !g_strikeAnyMeter) return full;
        const DWORD now = GetTickCount();
        if (now - g_strikeAnyTick > 5000) {
            g_strikeAnyTick = now;
            Log(1, "0.6.14 F6 condition 538 (meter full, CM+0x1fc bit 22) answered 1 without a full meter "
                   "([Adrenaline] StrikeWithoutFullMeter=1; at most one line per 5 s)");
        }
        return 1;
    }
    const TruShadowPowerMeter *m = Meter();
    char r = m ? static_cast<char>((*m->flags >> 3) & 1) : 0;
    if (m)
        Hit(g_p538, r, "doppelganger, meter flags 0x%03lx", *m->flags);
    else
        Hit(g_p538, r, "doppelganger, no meter interface (TruShadowPowerMeterApi) - 0");
    return r;
}

#define COND_HANDLER(name, pred)                                                              \
    char __cdecl name(void *agent, void *cache, const BYTE *record) {                         \
        char r = 0;                                                                           \
        __try {                                                                               \
            r = reinterpret_cast<CondTemplateFn>(kCondTemplate)(agent, cache, record, &pred); \
        } __except (EXCEPTION_EXECUTE_HANDLER) {                                              \
            r = 0;                                                                            \
        }                                                                                     \
        return r;                                                                             \
    }
COND_HANDLER(Cond2005, Pred2005)   // TU 0x8246ea20
COND_HANDLER(Cond2006, Pred2006)   // TU 0x8246ec68
COND_HANDLER(Cond2013, Pred2013)   // TU 0x8246eaf8
COND_HANDLER(Cond2011, Pred2011)   // TU 0x8246f270
COND_HANDLER(Cond538, Pred538)     // TU 0x8246fae0

// ---------------------------------------------------------------- 3. state 1014 gate
// TU 0x8245fd70 / 0x8245fdc0 / 0x8245fd98: gameTracker+0x1244 -> meter functions 0x823d8978 / 0x823d9210 /
// 0x823d8d18, else the player functions (= PC tru+0x31d3c0 / +0x318fd0 / +0x318d00 through tru+0x35e0b0 / d0 / c0).
const DWORD kState1014Pc[3] = {0x0075e0b0, 0x0075e0d0, 0x0075e0c0};   // slots 0, 2, 3
const char *const kState1014PcHex[3] = {"a158dbfa00 8b8804050000 e900f3fbff", "a158dbfa00 8b8804050000 e9f0aefbff",
                                        "a158dbfa00 8b8804050000 e930acfbff"};
StateFn g_orig1014[3] = {nullptr, nullptr, nullptr};
Probe g_p1014[3] = {{"state 1014 slot 0 (TU 0x823d8978 shadow strike start)"},
                    {"state 1014 slot 2 (TU 0x823d9210 shadow strike end)"},
                    {"state 1014 slot 3 (TU 0x823d8d18 shadow strike tick)"}};

// ---------------------------------------------------------------- 0.2: PC building blocks of the states / strike
const float kZero = 0.0f, kOne = 1.0f, kMinusOne = -1.0f, kHundred = 100.0f, kShortMove = 200.0f;   // TU 0x8207d538,
// 0x8207d544, 0x82052664, 0x8207d53c, 0x8206af90
const double kPerHundred = 0.01;    // TU 0x8207dd48 (double)
const float kMeterStart = 1000.0f;  // TU 0x8206af78

typedef void *(__fastcall *ParamNodeFn)(void *agent, int, int id);             // tru+0x383f50 = TU 0x82482d28
typedef BYTE *(__fastcall *ParamFindFn)(void *node, int, int id);              // tru+0x384b30 = TU 0x82488680
typedef float *(__cdecl *FaceFn)(float *out, const BYTE *inst, const float *dir);   // tru+0x30b8a0 = TU 0x8241b1e8
typedef float *(__fastcall *AxisAngleFn)(float *out, int, const float *axis, float angle);   // tru+0x49dfd0 = 0x8213e760
typedef void(__fastcall *ToRotFn)(const float *src, int, float *out);         // tru+0x49d450 = TU 0x820ef928
typedef void(__fastcall *ChanMode2Fn)(BYTE *chan, int, const float *vec, float frames);     // tru+0x438d00
typedef void(__fastcall *ChanMode3Fn)(BYTE *chan, int, const float *rot, const float *pos, float frames);  // +0x438dc0
typedef void(__fastcall *AnimSetFn)(BYTE *chan, int, int anim, void *object);  // tru+0x444ba0 = TU 0x820e0560
typedef BYTE *(__cdecl *RecordFn)(BYTE *target, BYTE *player, const float *pos, const float *rot, float frames);  // +0x645e40
typedef void(__cdecl *MessageFn)(BYTE *inst, int msg, void *arg);              // tru+0x1b3750 (wake + message)
typedef void(__cdecl *PlayerEventFn)(BYTE *inst, int type, int all, int channel);   // tru+0x318780 = TU 0x82418158
typedef void(__cdecl *HudUpdateFn)();                                          // tru+0x37da70
typedef void(__fastcall *HitFn)(BYTE *hit, int, BYTE *attacker, int a, int b, int c, int d);   // tru+0x1b4de0
typedef BYTE *(__fastcall *VGetFn)(BYTE *self, int);                           // virtual getters

const DWORD kParamNode = 0x00783f50, kParamFind = 0x00784b30, kFace = 0x0070b8a0, kAxisAngle = 0x0049dfd0,
            kToRot = 0x0049d450, kChanMode2 = 0x00438d00, kChanMode3 = 0x00438dc0, kAnimSet = 0x00444ba0,
            kRecord = 0x00645e40, kMessage = 0x005b3750, kPlayerEvent = 0x00718780, kHudUpdate = 0x0077da70,
            kHit = 0x005b4de0, kCameraMgr = 0x00e804f0, kAimObjPtr = 0x00fadfb0, kHudStrikeByte = 0x00fae8ae;
bool g_statesOk = false, g_strikeOk = false;

bool CheckStateBlocks() {
    struct { DWORD at; const char *hex; const char *what; } const s[] = {
        {kParamNode, "56 8bf1 8b8620050000 85c0", "state parameter node tru+0x383f50"},
        {kParamFind, "0fb701 53 56 57 8b7c2410 33db", "state parameter record tru+0x384b30"},
        {0x0075f470, "83ec08 56 57 8b7c241c 8b4704 0fb77002 8b4f08 69f620030000 8b9180020000 037214", "channel (tru+0x35f470)"},
        {0x00438970, "0fb681f8000000 6bc070 038180000000", "animation entry tru+0x38970"},
        {kFace, "55 8bec 83e4f0 83ec6c f30f101d1c118400 8b4510 0f2800 f30f103534118400 f30f100d30118400", "facing tru+0x30b8a0 (TU 0x8241b1e8)"},
        {0x0070b9e0, "8b442408 8b0d94f0e700 56 8b742408 50 51 56 e8a9feffff", "facing wrapper tru+0x30b9e0"},
        {kAxisAngle, "55 8bec 83e4f0 83ec18 d9450c 56 dc0dc0138400", "axis / angle tru+0x49dfd0"},
        {kChanMode2, "55 8bec 83e4f0 83ec10 f30f100534118400 d9450c", "channel mode 2 tru+0x38d00"},
        {0x00438d59, "c7402402000000", "channel mode 2 store"},
        {0x005e7770, "b8f004e800 c3", "camera manager getter (0xe804f0)"},
        {0x00855bc4, "b03a4300", "camera manager vtable slot 0xe0 -> tru+0x33ab0"},
        {0x00433ab0, "8b4144 c3", "camera manager slot 0xe0: mov eax, [ecx+0x44] (TU 0x822a9fd8 lwz r3, 0x44(r3))"},
        {0x0071388f, "d94710", "[0xfadfb0] +0xb0 use (tru+0x3137c0 = retail 0x82404bc0)"},
    };
    for (const auto &c : s)
        if (!HexAt(c.at, c.hex)) { Log(0, "states 1017 / 244 / 1007: %s at 0x%08lx does not match - not translated", c.what, c.at); return false; }
    return true;
}

bool CheckStrikeBlocks() {
    struct { DWORD at; const char *hex; const char *what; } const s[] = {
        {kToRot, "55 8bec 83e4f0 8b4508 83ec5c 56 8bf1 50", "rotation from facing tru+0x49d450 (TU 0x820ef928)"},
        {kChanMode3, "55 8bec 83e4f0 d94510 8bc1 8b4d08 0f2801 8b4d0c 0f294010", "channel mode 3 tru+0x38dc0"},
        {0x00438df1, "c7402403000000", "channel mode 3 store"},
        {kAnimSet, "83ec2c a1e8d78b00 33c4 89442428", "animation set tru+0x44ba0 (TU 0x820e0560)"},
        {kRecord, "55 8bec 83e4f0 6a40 e8c3acf7ff d94518", "message record tru+0x245e40"},
        {kMessage, "56 8b742408 8d8610010000 85c0 7422 57 8bbe20010000", "wake + message tru+0x1b3750"},
        {kPlayerEvent, "51 817c240cff000000 0f84f2000000", "player event walker tru+0x318780"},
        {kHudUpdate, "8b0d20e9fa00 8b01 8b500c ffe2", "HUD update tru+0x37da70"},
        {0x00718e23, "c605aee8fa0001", "HUD strike byte [0xfae8ae] (retail strike tick tru+0x318d00)"},
        {kHit, "55 8bec 83e4f0 83ec24 8a550c 53 668b5d18 56 8bf1 8b4e40 57 8b7d08 8b8718020000 89464c", "hit tru+0x1b4de0 (TU 0x8226f5c8)"},
        {0x005b4efd, "c21400", "hit: ret 0x14"},
    };
    for (const auto &c : s)
        if (!HexAt(c.at, c.hex)) { Log(0, "shadow strike: %s at 0x%08lx does not match - not translated", c.what, c.at); return false; }
    return true;
}

BYTE *Channel(const BYTE *agent) {
    const BYTE *instance = *reinterpret_cast<const BYTE *const *>(agent + 8);
    const BYTE *anim = *reinterpret_cast<const BYTE *const *>(instance + 0x280);
    WORD index = *reinterpret_cast<const WORD *>(*reinterpret_cast<const BYTE *const *>(agent + 4) + 2);
    return *reinterpret_cast<BYTE *const *>(anim + 0x14) + 0x320 * index;
}
const BYTE *AnimEntry(const BYTE *chan) { return *reinterpret_cast<const BYTE *const *>(chan + 0x80) + 0x70 * chan[0xf8]; }

const BYTE *ParamRecord(void *agent, int id) {
    void *node = reinterpret_cast<ParamNodeFn>(kParamNode)(agent, 0, id);
    return node ? reinterpret_cast<ParamFindFn>(kParamFind)(node, 0, id) : nullptr;
}

typedef __declspec(align(16)) float Vec4[4];
void Copy4(float *d, const float *s) { for (int i = 0; i < 4; ++i) d[i] = s[i]; }
// TU normalisation (vdot3fp, vrsqrtefp + one Newton step, vsel): xyz / |xyz|, w = w / |xyz|; a zero length gives
// the zero vector (the squared length). sqrtf instead of the estimate - differs in the last bits only.
void Normalize3(float *v) {
    float sq = v[0] * v[0] + v[1] * v[1] + v[2] * v[2];
    if (sq == kZero) { v[0] = v[1] = v[2] = v[3] = kZero; return; }
    float r = 1.0f / sqrtf(sq);
    for (int i = 0; i < 4; ++i) v[i] *= r;
}
float Length3(const float *v) { return sqrtf(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]); }

// gameTracker+0x1280: TruShadowPower's copy through the interface, else a local one (condition 1048 then lacks it)
LONG g_local1280 = 0;
volatile LONG *Gt1280() {
    const TruShadowPowerMeter *m = Meter();
    return (m && m->version >= 3 && m->size >= kMeterV3Size && m->gt1280) ? m->gt1280 : &g_local1280;
}

// 0.5.1: TU 0x823d9050 (strike look off) through the meter interface v4 (TruShadowPower 0.14). It returns at once
// unless meter flag 4 is set - on the TU as in TruShadowPower's StrikeLookOffBody. Without version 4 it is skipped
// (logged once): then a strike look ([Look] StrikeLook=1 in TruShadowPower) can leave flag 4 set after the strike.
volatile LONG g_lookOffMissing = 0;
void LookOff(const TruShadowPowerMeter *m, const char *where) {
    if (m->version >= 4 && m->size >= kMeterV4Size && m->strikeLookOff) {
        const DWORD before = *m->flags;
        m->strikeLookOff();
        if (before & 4) Log(1, "shadow strike %s: strike look off (TU 0x823d9050 via meter interface v4), meter flags 0x%03lx -> 0x%03lx",
                            where, before, *m->flags);
        return;
    }
    if (InterlockedIncrement(&g_lookOffMissing) == 1)
        Log(1, "shadow strike %s: TU 0x823d9050 (strike look off) skipped - meter interface version %lu, size %lu (needs "
               "version >= 4, size >= %lu: TruShadowPower 0.14); logged once", where, m->version, m->size, kMeterV4Size);
}

// TU 0x82457b28(out, target, flag): flag set and no / excluded target -> [0x829ca64c] (= PC [0xfadfb0]) +0xb0: +0x18 >
// 0 -> rotation about (0, 0, 1, 0) [0x8207db00] by +0x8 (0x8213e760 = tru+0x49dfd0), else face along -row 1 of the
// player matrix; otherwise face the target from the player matrix position (+0x90 -> +0x30). The TU's calls of
// 0x8213fbe8 / 0x820d7948 before that have their results overwritten (f1 / v1 reloaded) - not made here.
float *FaceTarget(float *out, BYTE *target, int flag) {
    BYTE *player = Player();
    const BYTE *matrix = *reinterpret_cast<const BYTE *const *>(player + 0x90);
    Vec4 dir;
    if (flag && (!target || Excluded(target))) {
        const BYTE *aim = *reinterpret_cast<const BYTE *const *>(kAimObjPtr);
        const BYTE *sub = *reinterpret_cast<const BYTE *const *>(aim + 0xb0);
        if (kZero < *reinterpret_cast<const float *>(sub + 0x18)) {
            static __declspec(align(16)) const float axis[4] = {0.0f, 0.0f, 1.0f, 0.0f};
            return reinterpret_cast<AxisAngleFn>(kAxisAngle)(out, 0, axis, *reinterpret_cast<const float *>(sub + 8));
        }
        const float *row = reinterpret_cast<const float *>(matrix + 0x10);
        for (int i = 0; i < 4; ++i) dir[i] = row[i] * kMinusOne;
        return reinterpret_cast<FaceFn>(kFace)(out, player, dir);
    }
    if (!target) { Copy4(out, reinterpret_cast<const float *>(player + 0x30)); return out; }   // TU would read 0x20
    const float *t = reinterpret_cast<const float *>(target + 0x20);
    const float *p = reinterpret_cast<const float *>(matrix + 0x30);
    for (int i = 0; i < 3; ++i) dir[i] = t[i] - p[i];
    dir[3] = kZero;
    Normalize3(dir);
    return reinterpret_cast<FaceFn>(kFace)(out, player, dir);
}

// ---------------------------------------------------------------- 0.2: state 1017 slot 4 (TU 0x8245f5a0)
Probe g_p1017 = {"state 1017 slot 4 (TU 0x8245f5a0: pick / face the target)"};
void __cdecl State1017Slot4(void *agent) {
    __try {
        const BYTE *rec = ParamRecord(agent, 0x40f);
        if (!rec) { Hit(g_p1017, -1, "parameter 0x40f missing - nothing done (the TU would read address 4)"); return; }
        const int index = static_cast<signed char>(rec[4]);
        BYTE *gt = GameTracker();
        BYTE *player = *reinterpret_cast<BYTE **>(gt + 0x504);
        float *v1270 = reinterpret_cast<float *>(gt + 0x1270), *v1260 = reinterpret_cast<float *>(gt + 0x1260);
        Vec4 face;
        BYTE *o = nullptr;
        if (((*reinterpret_cast<const DWORD *>(player + 0x1fc) >> 10) & 1) && WeakRef(player)) {
            BYTE *aim = HandleObject(WeakRef(player));
            if (aim && !Excluded(aim)) {
                o = aim;
                Copy4(v1270, FaceTarget(face, o, 0));
                Copy4(v1260, reinterpret_cast<const float *>((Accepts(o, index) ? o : Player()) + 0x20));
                g_gt1284[0] = reinterpret_cast<DWORD>(o);
                g_gt1284[1] = *reinterpret_cast<const DWORD *>(o + 0x44);
                Hit(g_p1017, 1, "aim target 0x%08lx, list index %lu", reinterpret_cast<DWORD>(o), static_cast<DWORD>(index));
                return;
            }
        }
        o = TargeterObject(index);
        if (o) {
            Copy4(v1270, FaceTarget(face, o, 0));
            Copy4(v1260, reinterpret_cast<const float *>(o + 0x20));
            g_gt1284[0] = reinterpret_cast<DWORD>(o);
            g_gt1284[1] = *reinterpret_cast<const DWORD *>(o + 0x44);
            Hit(g_p1017, 2, "targeter (TU index %lu) target 0x%08lx", static_cast<DWORD>(index), reinterpret_cast<DWORD>(o));
            return;
        }
        // no target: face along the current camera's +0x10 matrix row +0x20 ((*0x82efc780)->vtbl[0xe0]()->vtbl[0x38]())
        BYTE *mgr = reinterpret_cast<BYTE *>(kCameraMgr);
        BYTE *cam = (*reinterpret_cast<VGetFn *const *>(mgr))[0xe0 / 4](mgr, 0);
        BYTE *m = (*reinterpret_cast<VGetFn *const *>(cam))[0x38 / 4](cam, 0);
        Vec4 dir;
        Copy4(dir, reinterpret_cast<const float *>(m + 0x20));
        Copy4(v1270, reinterpret_cast<FaceFn>(kFace)(face, Player(), dir));
        g_gt1284[0] = g_gt1284[1] = 0;
        Hit(g_p1017, 0, "no target (TU index %lu): camera direction", static_cast<DWORD>(index));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1017 slot 4: access fault - skipped");
    }
}

// ---------------------------------------------------------------- 0.2: state 244 (TU 0x82464198 / 0x824642a8)
Probe g_p244a = {"state 244 slot 0 (TU 0x82464198: dash to the state-1017 target)"};
Probe g_p244d = {"state 244 slot 3 (TU 0x824642a8: dash update)"};

bool Busy244(const BYTE *gt) {     // gameTracker+0x31c set, byte +0x320 set, (+0x31c)->u16 +0x40 == 2
    if (!gt) return false;
    const BYTE *p = *reinterpret_cast<const BYTE *const *>(gt + 0x31c);
    return p && gt[0x320] && *reinterpret_cast<const WORD *>(p + 0x40) == 2;
}
float Radius(const BYTE *inst) {   // (inst +0x288) -> +0x65c (same on PC: tru+0x2f3ec5)
    const BYTE *p = *reinterpret_cast<const BYTE *const *>(inst + 0x288);
    return *reinterpret_cast<const float *>(p + 0x65c);
}
// point next to the target: target pos + normalise(player pos - target pos) x (radius target + radius player)
void StandOff(float *out, const BYTE *target, const BYTE *player) {
    const float *t = reinterpret_cast<const float *>(target + 0x20), *p = reinterpret_cast<const float *>(player + 0x20);
    Vec4 d;
    for (int i = 0; i < 4; ++i) d[i] = p[i] - t[i];
    Normalize3(d);
    float r = Radius(target) + Radius(player);
    for (int i = 0; i < 4; ++i) out[i] = d[i] * r + t[i];
}

// TU 0x82463fc8(agent, point): n = floor(|point - player| / tuning +0x68); n > 2: +0x1280 = n, frames = n x 100, else
// +0x1280 = 2, frames = 200; channel mode 2 {point, (0, 0, 0, 1), frames} (= tru+0x38d00)
void Dash(void *agent, const float *point) {
    BYTE *chan = Channel(static_cast<BYTE *>(agent));
    const BYTE *tuning = Tuning();
    if (!tuning) { Log(1, "state 244: no tuning (object 858) - skipped (the TU would read address 0x68)"); return; }
    const float *p = reinterpret_cast<const float *>(Player() + 0x20);
    Vec4 d;
    for (int i = 0; i < 4; ++i) d[i] = point[i] - p[i];
    float len = Length3(d);
    int n = static_cast<int>(static_cast<float>(floor(static_cast<double>(len / *reinterpret_cast<const float *>(tuning + 0x68)))));
    float frames = kShortMove;
    if (n > 2) { *Gt1280() = n; frames = static_cast<float>(n) * kHundred; }
    else *Gt1280() = 2;
    Vec4 v;
    Copy4(v, point);
    reinterpret_cast<ChanMode2Fn>(kChanMode2)(chan, 0, v, frames);
}

void __cdecl State244Slot0(void *agent) {
    __try {
        BYTE *gt = GameTracker();
        BYTE *t = HandleObject(g_gt1284);
        if (!t || Busy244(gt)) { Hit(g_p244a, 0, "target 0x%08lx, busy %lu", reinterpret_cast<DWORD>(t), Busy244(gt) ? 1 : 0); return; }
        Vec4 point;
        StandOff(point, t, Player());
        Dash(agent, point);
        Hit(g_p244a, 1, "target 0x%08lx, steps %ld", reinterpret_cast<DWORD>(t), static_cast<DWORD>(*Gt1280()));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 244 slot 0: access fault - skipped");
    }
}

void __cdecl State244Slot3(void *agent) {
    __try {
        BYTE *gt = GameTracker();
        BYTE *chan = Channel(static_cast<BYTE *>(agent));
        if (Busy244(gt)) {     // stop: mode 2 at the instance position, frames = animation +0x28 - 1
            const BYTE *inst = *reinterpret_cast<const BYTE *const *>(static_cast<BYTE *>(agent) + 8);
            float frames = *reinterpret_cast<const float *>(AnimEntry(chan) + 0x28) - kOne;
            reinterpret_cast<ChanMode2Fn>(kChanMode2)(chan, 0, reinterpret_cast<const float *>(inst + 0x20), frames);
            Hit(g_p244d, 2, "busy: stop");
            return;
        }
        BYTE *t = HandleObject(g_gt1284);
        if (!t) return;
        Vec4 point;
        StandOff(point, t, Player());
        const BYTE *tuning = Tuning();
        if (!tuning) return;
        const float *p = reinterpret_cast<const float *>(Player() + 0x20);
        Vec4 d;
        for (int i = 0; i < 4; ++i) d[i] = point[i] - p[i];
        int n = static_cast<int>(static_cast<float>(floor(static_cast<double>(Length3(d) / *reinterpret_cast<const float *>(tuning + 0x68)))));
        if (n <= 0) return;
        const LONG g = *Gt1280();
        // steps still to go: (g x 100 - animation time) x 0.01
        int m = static_cast<int>((static_cast<float>(g) * kHundred - *reinterpret_cast<const float *>(AnimEntry(chan) + 0x28)) * kPerHundred);
        if (m < 0 || n == m) return;
        LONG ng = g - m + n;
        *Gt1280() = ng;
        reinterpret_cast<ChanMode2Fn>(kChanMode2)(chan, 0, point, static_cast<float>(ng) * kHundred);
        Hit(g_p244d, 1, "steps %ld -> %ld (to go %ld)", static_cast<DWORD>(g), static_cast<DWORD>(ng), static_cast<DWORD>(m));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 244 slot 3: access fault - skipped");
    }
}

// ---------------------------------------------------------------- 0.2: state 1007 slots 4 / 5 (TU 0x8245f068)
// doppelganger mode only; outside it the PC handler of slot 4 (tru+0x36d930, retail) runs and slot 5 stays empty
StateFn g_orig1007Slot4 = nullptr;
Probe g_p1007 = {"state 1007 slot 4 / 5 (TU 0x8245f068: face target 5, doppelganger)"};
void State1007(void *agent, int slot) {
    if (!Doppelganger()) { if (slot == 4 && g_orig1007Slot4) g_orig1007Slot4(agent); return; }
    __try {
        BYTE *gt = GameTracker();
        BYTE *player = *reinterpret_cast<BYTE **>(gt + 0x504);
        float *v1260 = reinterpret_cast<float *>(gt + 0x1260), *v1270 = reinterpret_cast<float *>(gt + 0x1270);
        BYTE *t = TargetOf(player, 5);
        if (t && ((*reinterpret_cast<const DWORD *>(player + 0x1fc) >> 10) & 1) && !Accepts(t, 5)) t = TargeterObject(5);
        if (t) {
            const BYTE *inst = *reinterpret_cast<const BYTE *const *>(static_cast<BYTE *>(agent) + 8);
            const float *tp = reinterpret_cast<const float *>(t + 0x20), *ip = reinterpret_cast<const float *>(inst + 0x20);
            float r = Radius(inst);
            if (*reinterpret_cast<const DWORD *>(t + 0x288)) r += Radius(t);
            Vec4 d;
            for (int i = 0; i < 4; ++i) d[i] = ip[i] - tp[i];
            Normalize3(d);
            for (int i = 0; i < 4; ++i) v1260[i] = d[i] * r + tp[i];
            if (IsBooBType(t)) { v1260[2] = ip[2]; v1260[3] = kZero; }   // TU: x, y of the point, z of Lara (+0x28)
        } else {
            Copy4(v1260, reinterpret_cast<const float *>(Player() + 0x20));
        }
        Vec4 face;
        Copy4(v1270, FaceTarget(face, t, 1));
        Hit(g_p1007, t ? 1 : 0, "slot %lu, target 0x%08lx", static_cast<DWORD>(slot), reinterpret_cast<DWORD>(t));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1007 slot %d: access fault - skipped", slot);
    }
}
// ---------------------------------------------------------------- 0.5: states 1019 / 1020 (TU 0x8245f420 / 0x8245f540 /
// 0x8245f398, their TU-new helper 0x8245f2a8 and the channel helpers 0x82463c18 / 0x82463eb8). VMX128 bodies decoded
// with tools/ppc_dis128.py and cross-checked against Xenia's decoder tables by tools/vmx128_xenia_check.py (77 / 77
// words the same; docs Befund-Schattenkampf-0411b.md). TU table 0x82757948: 1019 = {0x8245f420, 0x8245f420, 0,
// 0x8245f540, 0, 0}, 1020 = {0x8245f398, 0x8245f398, 0, 0, 0, 0}. Chart (doppelganger_casual DTP 20212): 1019 in record
// #756 (the combat hub, parent 711), 1020 in #748 (after the finisher #741, activity 1039 = list index 8).
// Behaviour only with [States] Translate1019 / Translate1020 = 1 (default 0, read again at run time at most once per
// second); with 0 the records are still registered ([Probe] States1019=1) and only log what the TU would do - the
// PC had no handler for these ids (the generic default tru+0x381d10 formats a debug text and drops it), so that is
// the PC behaviour.
int g_translate1019 = 0, g_translate1020 = 0;    // [States] Translate1019 / Translate1020
int g_probe1019 = 1;                             // [Probe] States1019: register 1019 / 1020 (log-only when off)
bool g_s1019Ok = false;                          // building blocks below verified
bool g_reg1019 = false, g_reg1020 = false;       // records in Lara's state table copy
void ReadSwitches();                             // 0.4.1 / 0.5, defined with the strike below

typedef void(__fastcall *ChanVecFn)(BYTE *chan, int, const float *vec);                       // tru+0x3e400 / +0x3e370
typedef void(__fastcall *ChanVec2Fn)(BYTE *chan, int, const float *face, const float *point); // tru+0x3e480
typedef void *(__cdecl *AnimFramesFn)(int *out, void *agent);                                 // tru+0x35f3e0
typedef char(__fastcall *ParamBoolFn)(void *node, int, int id, char *out);                    // tru+0x384c20
const DWORD kChanMode1 = 0x00438d70, kChanMode1Anim = 0x0043e400, kChanMode2Anim = 0x0043e370,
            kChanMode3Anim = 0x0043e480, kAnimFrames = 0x0075f3e0, kParamBool = 0x00784c20;

bool CheckState1019Blocks() {
    struct { DWORD at; const char *hex; const char *what; } const s[] = {
        {kChanMode1, "55 8bec 83e4f0 83ec10 d9450c 8bc1 8b4d08 0f2801 0f294010", "channel mode 1 tru+0x38d70 (TU 0x82463eb8 stores)"},
        {0x00438db1, "c7402401000000", "channel mode 1 store"},
        {kChanMode1Anim, "55 8bec 83e4f0 83ec20 8bc1 8b8880000000 8b4924 0fbf5134 0fbf4932", "channel mode 1, animation frames tru+0x3e400"},
        {0x0043e464, "c7402401000000", "channel mode 1 (animation) store"},
        {kChanMode2Anim, "55 8bec 83e4f0 83ec20 f30f100534118400 8bc1 8b8880000000 8b4924 0fbf5134 0fbf4932", "channel mode 2, animation frames tru+0x3e370 (TU 0x820e47f8)"},
        {0x0043e3ec, "c7402402000000", "channel mode 2 (animation) store"},
        {kChanMode3Anim, "55 8bec 83e4f0 83ec10 8bc1 8b8880000000 8b4924 0fbf5134 0fbf4932", "channel mode 3, animation frames tru+0x3e480"},
        {0x0043e4d5, "c7402403000000", "channel mode 3 (animation) store"},
        {kChanMode3, "55 8bec 83e4f0 d94510 8bc1 8b4d08 0f2801 8b4d0c 0f294010", "channel mode 3 tru+0x38dc0"},
        {0x00438df1, "c7402403000000", "channel mode 3 store"},
        {0x00841134, "0000803f", "1.0f [0x841134] (w of the mode-2 vector, TU 0x8207d544)"},
        {0x0084111c, "00000000", "0.0f [0x84111c] (TU 0x8207d538 / zero vector 0x8207db30)"},
        {kAnimFrames, "56 57 8b7c2410 681b010000 681b010000 8bcf e8594b0200 8bc8 e832570200 8bf0 6683 7e0223", "frame count tru+0x35f3e0 (= TU 0x82463af8 flag 0)"},
        {0x0075f42e, "d94004 dc0d08048500", "frame count: time x 0.01 [0x850408] (TU 0x8207dd48)"},
        {0x00850408, "7b14ae47e17a843f", "0.01 (double) [0x850408]"},
        {kParamBool, "8b442404 50 e806ffffff 85c0 7505 32c0 c20800 50 e837ebffff", "bool parameter tru+0x384c20 (TU 0x82484b88 via 0x823d7230)"},
        {0x0075f4ad, "681d010000 681d010000", "tru+0x35f470 reads parameter 0x11d as TU 0x82463c18 / 0x82463eb8"},
    };
    for (const auto &c : s)
        if (!HexAt(c.at, c.hex)) { Log(0, "states 1019 / 1020: %s at 0x%08lx does not match - not registered", c.what, c.at); return false; }
    return true;
}

// rate-limited decision log: every enter (event) at level 1 up to 400 lines per state (then level 2), a tick only
// when its decision changes (level 1, same cap) or every 2 s at level 3
struct Trace { const char *name; volatile LONG calls; LONG lastDecision; DWORD lastTick; volatile LONG lines; };
void TraceLog(Trace &t, bool event, int decision, const char *fmt, ...) {
    LONG n = InterlockedIncrement(&t.calls);
    char detail[400] = "";
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf_s(detail, sizeof(detail), _TRUNCATE, fmt, ap);
    va_end(ap);
    DWORD now = GetTickCount();
    const bool changed = n == 1 || decision != t.lastDecision;
    int level = 0;
    if (event || changed) level = (InterlockedIncrement(&t.lines) <= 400) ? 1 : 2;
    else if (now - t.lastTick >= 2000) level = 3;
    t.lastDecision = decision;
    if (!level) return;
    t.lastTick = now;
    Log(level, "%s (call %ld): %s", t.name, n, detail);
}

// TU 0x82463eb8(agent, v1 face) - TU-new: unless the bool parameter 0x11d is set: n = 0x82463af8(&n, agent, 0)
// (= PC tru+0x35f3e0); n > 0 -> channel +0x10 = face, +0 = zero vector 0x8207db30, +0x20 = (float) n (no x 100 here),
// +0x24 = 1 (= PC tru+0x38d70); else the same with the animation's frame count (= PC tru+0x3e400). Returns the path
// (1 parameter 0x11d set: nothing, 2 n frames, 3 animation frames); apply = 0 only computes it.
int FaceOnly(void *agent, const float *face, bool apply, int *frames) {
    char keep = 0;
    void *node = reinterpret_cast<ParamNodeFn>(kParamNode)(agent, 0, 0x11d);
    if (node) reinterpret_cast<ParamBoolFn>(kParamBool)(node, 0, 0x11d, &keep);
    if (keep) return 1;
    int n = 0;
    reinterpret_cast<AnimFramesFn>(kAnimFrames)(&n, agent);
    *frames = n;
    BYTE *chan = Channel(static_cast<BYTE *>(agent));
    if (n > 0) {
        if (apply) reinterpret_cast<ChanMode2Fn>(kChanMode1)(chan, 0, face, static_cast<float>(n));
        return 2;
    }
    if (apply) reinterpret_cast<ChanVecFn>(kChanMode1Anim)(chan, 0, face);
    return 3;
}

// TU 0x82463c18(agent, v1 face, v2 point) = retail 0x8245f930 (PC tru+0x35f470) plus a TU-new doppelganger branch:
//   n = 0x82463af8(&n, agent, 0) (PC tru+0x35f3e0), flag = bool parameter 0x11d, t = animation entry +0x28 (f29)
//   n > 0: frames = n x 100.0f [0x8207d53c]; frames > t: flag -> mode 2 {point, (0, 0, 0, 1), frames}, else mode 3
//          {face, point, frames} (the retail path); else (TU-new 0x82463d74): no doppelganger -> nothing; the call
//          0x82463af8(.., 1) (parameter 0x11e) only fills a stack word that is overwritten unread - not made; t >= 0
//          (or NaN) -> nothing; else flag -> mode 2 with t + 100, else mode 3 with frames + 100
//   n <= 0: flag -> 0x820e47f8 (mode 2, animation frames = PC tru+0x3e370), else mode 3 with animation frames
//          (PC tru+0x3e480)
// Returns the path (1 / 2 retail mode 2 / 3, 3 TU branch without doppelganger, 4 TU branch t >= 0, 5 / 6 TU branch
// mode 2 / 3, 7 / 8 animation frames mode 2 / 3).
int MoveTo(void *agent, const float *face, const float *point, bool apply, int *frames, float *time) {
    BYTE *chan = Channel(static_cast<BYTE *>(agent));
    int n = 0;
    reinterpret_cast<AnimFramesFn>(kAnimFrames)(&n, agent);
    char flag = 0;
    void *node = reinterpret_cast<ParamNodeFn>(kParamNode)(agent, 0, 0x11d);
    if (node) reinterpret_cast<ParamBoolFn>(kParamBool)(node, 0, 0x11d, &flag);
    const float t = *reinterpret_cast<const float *>(AnimEntry(chan) + 0x28);
    *frames = n;
    *time = t;
    if (n > 0) {
        const float f = static_cast<float>(n) * kHundred;
        if (f > t) {
            if (flag) { if (apply) reinterpret_cast<ChanMode2Fn>(kChanMode2)(chan, 0, point, f); return 1; }
            if (apply) reinterpret_cast<ChanMode3Fn>(kChanMode3)(chan, 0, face, point, f);
            return 2;
        }
        if (!Doppelganger()) return 3;
        if (!(t < kZero)) return 4;
        if (flag) { if (apply) reinterpret_cast<ChanMode2Fn>(kChanMode2)(chan, 0, point, t + kHundred); return 5; }
        if (apply) reinterpret_cast<ChanMode3Fn>(kChanMode3)(chan, 0, face, point, f + kHundred);
        return 6;
    }
    if (flag) { if (apply) reinterpret_cast<ChanVecFn>(kChanMode2Anim)(chan, 0, point); return 7; }
    if (apply) reinterpret_cast<ChanVec2Fn>(kChanMode3Anim)(chan, 0, face, point);
    return 8;
}

// TU 0x8245f2a8(o, agent) - TU-new: point next to o seen from the agent's instance, facing o, then 0x82463c18:
//   d = instance +0x20 - o +0x20 (vsubfp128, 4 lanes); r = radius(instance) + (o +0x288 ? radius(o) : 0)
//   face = 0x82457b28(o, 1); d = d x rsqrt(dot3(d, d)) (vrsqrtefp128 + one Newton step, vsel: 0 for a zero length)
//   point = d x r + o +0x20 (vmaddcfp128); 0x82463c18(agent, face, point)
int StandOffMove(BYTE *o, void *agent, bool apply, char *text, size_t size) {
    if (!o || !agent) { _snprintf_s(text, size, _TRUNCATE, "no object"); return 0; }
    const BYTE *inst = *reinterpret_cast<const BYTE *const *>(static_cast<BYTE *>(agent) + 8);
    const float *ip = reinterpret_cast<const float *>(inst + 0x20), *op = reinterpret_cast<const float *>(o + 0x20);
    __declspec(align(16)) float d[4], point[4], face[4];
    for (int i = 0; i < 4; ++i) d[i] = ip[i] - op[i];
    float r = Radius(inst);
    if (*reinterpret_cast<const DWORD *>(o + 0x288)) r = Radius(o) + r;
    FaceTarget(face, o, 1);
    Normalize3(d);
    for (int i = 0; i < 4; ++i) point[i] = d[i] * r + op[i];
    int frames = 0;
    float time = 0.0f;
    const int path = MoveTo(agent, face, point, apply, &frames, &time);
    _snprintf_s(text, size, _TRUNCATE, "object 0x%08lx, point %.1f %.1f %.1f (radius %.1f), frame count %d, animation "
                "+0x28 %.1f, move path %d (1 / 2 mode 2 / 3, 3 / 4 TU branch skipped, 5 / 6 TU branch, 7 / 8 animation "
                "frames)", reinterpret_cast<DWORD>(o), point[0], point[1], point[2], r, frames, time, path);
    return path;
}

// TU meter +0x20 / +0x24 (handle {object, id} of 1019's target). Only 1019 reads / writes it
// (tools/ppc_ptr_field_users.py: 5 uses, all in 0x8245f420 / 0x8245f540; the meter methods called with the meter in
// r3 use neither field); the TU zeroes it when it builds the meter in the player init (0x82409c78 in 0x82409418, called
// from 0x82412ca0, which also allocates the target list). Kept here; a new target list ([0xfadfac] changed, PC player
// init tru+0x322631) counts as that new meter. "meter present" (TU gameTracker+0x508 != 0) = TruShadowPower's meter
// interface found.
DWORD g_m1019[2] = {0, 0};
BYTE **g_m1019List = nullptr;
DWORD *Handle1019() {
    if (g_m1019List != List()) { g_m1019[0] = g_m1019[1] = 0; g_m1019List = List(); }
    return g_m1019;
}

Trace g_t1019e = {"state 1019 slot 0 / 1 (TU 0x8245f420: target 5 into the meter, step next to it)"};
Trace g_t1019t = {"state 1019 slot 3 (TU 0x8245f540: follow the meter target)"};
Trace g_t1020 = {"state 1020 slot 0 / 1 (TU 0x8245f398: step next to the target of the list index of parameter 0x40f)"};
volatile LONG g_ticks1019 = 0;

void State1019Enter(void *agent, int slot) {
    ReadSwitches();
    const bool apply = g_translate1019 != 0;
    const LONG ticks = InterlockedExchange(&g_ticks1019, 0);
    char text[300] = "";
    __try {
        BYTE *gt = GameTracker();
        BYTE *player = *reinterpret_cast<BYTE **>(gt + 0x504);
        BYTE *t = TargetOf(player, 5);
        const int dg = Doppelganger();
        const bool meter = dg && Meter() != nullptr;
        DWORD *h = Handle1019();
        if (meter && apply) h[0] = h[1] = 0;
        int why = 0;      // 1 not doppelganger, 2 no target 5, 3 0x4f / 0xb00b target, 4 aiming, not accepted by targeter 5
        if (!dg) why = 1;
        else if (!t) why = 2;
        else if (IsBooBType(t)) why = 3;
        else if (((*reinterpret_cast<const DWORD *>(player + 0x1fc) >> 10) & 1) && !Accepts(t, 5)) why = 4;
        if (!why) {
            const int path = StandOffMove(t, agent, apply, text, sizeof(text));
            if (meter && apply) { h[0] = reinterpret_cast<DWORD>(t); h[1] = *reinterpret_cast<const DWORD *>(t + 0x44); }
            TraceLog(g_t1019e, true, 10 + path, "%s slot %d, %lu ticks since the last enter: target 5 0x%08lx -> step next "
                     "to it (0x8245f2a8), meter handle %s; %s", apply ? "ON" : "off (would)", slot, ticks,
                     reinterpret_cast<DWORD>(t), meter ? (apply ? "set" : "would be set") : "none (no meter interface)", text);
            return;
        }
        __declspec(align(16)) float face[4];
        FaceTarget(face, t, 1);
        int frames = 0;
        const int path = FaceOnly(agent, face, apply, &frames);
        TraceLog(g_t1019e, true, why * 10 + path, "%s slot %d, %lu ticks since the last enter: target 5 0x%08lx, reason "
                 "%d (1 not doppelganger, 2 no target, 3 0x4f / 0xb00b target, 4 aiming, not accepted) -> face only "
                 "(0x82457b28 + 0x82463eb8), path %d (1 parameter 0x11d: nothing, 2 frames %d, 3 animation frames), "
                 "meter handle %s", apply ? "ON" : "off (would)", slot, ticks, reinterpret_cast<DWORD>(t), why, path,
                 frames, meter ? (apply ? "cleared" : "would be cleared") : "none");
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1019 slot %d: access fault - skipped", slot);
    }
}
void __cdecl State1019Slot0(void *agent) { State1019Enter(agent, 0); }
void __cdecl State1019Slot1(void *agent) { State1019Enter(agent, 1); }

void __cdecl State1019Slot3(void *agent) {
    InterlockedIncrement(&g_ticks1019);
    ReadSwitches();
    const bool apply = g_translate1019 != 0;
    char text[300] = "";
    __try {
        const int dg = Doppelganger();
        const bool meter = Meter() != nullptr;
        BYTE *o = HandleObject(Handle1019());
        if (!dg || !meter || !o) {
            TraceLog(g_t1019t, false, !dg ? 1 : !meter ? 2 : 3, "%s nothing (%s)", apply ? "ON:" : "off:",
                     !dg ? "not doppelganger" : !meter ? "no meter interface" : "no valid meter target");
            return;
        }
        const int path = StandOffMove(o, agent, apply, text, sizeof(text));
        TraceLog(g_t1019t, false, 10 + path, "%s follow the meter target: %s", apply ? "ON" : "off (would)", text);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1019 slot 3: access fault - skipped");
    }
}

void State1020(void *agent, int slot) {
    ReadSwitches();
    const bool apply = g_translate1020 != 0;
    char text[300] = "";
    __try {
        const BYTE *rec = ParamRecord(agent, 0x40f);
        if (!rec) { TraceLog(g_t1020, true, 1, "slot %d: parameter 0x40f missing - nothing (the TU would read address 4)", slot); return; }
        const int index = static_cast<signed char>(rec[4]);
        BYTE **list = List();
        if (index < 0 || index >= kTuTargeters || !list || !list[SlotOf(index)]) {
            TraceLog(g_t1020, true, 2, "slot %d: list index %d - no targeter (the TU reads the entry unchecked) - nothing",
                     slot, index);
            return;
        }
        DWORD *h = reinterpret_cast<TargeterTargetFn>(kTargeterTarget)(list[SlotOf(index)], 0);
        BYTE *o = HandleObject(h);
        if (!o) {
            TraceLog(g_t1020, true, 3, "slot %d: targeter (TU index %d) %s - nothing", slot, index,
                     h ? "handle no longer valid" : "has no target");
            return;
        }
        const int path = StandOffMove(o, agent, apply, text, sizeof(text));
        TraceLog(g_t1020, true, 10 + path, "%s slot %d: targeter (TU index %d) -> step next to it (0x8245f2a8): %s",
                 apply ? "ON" : "off (would)", slot, index, text);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1020 slot %d: access fault - skipped", slot);
    }
}
void __cdecl State1020Slot0(void *agent) { State1020(agent, 0); }
void __cdecl State1020Slot1(void *agent) { State1020(agent, 1); }

// ---------------------------------------------------------------- 0.5.1: states 231 and 1004 (TU table differences)
// Slot meaning (PC record setter tru+0x3843a0 / enter loop tru+0x385a30): slot 0 = enter; slot 1 = enter while the
// state was already active in the previous chart record (getter tru+0x384790, called when tru+0x381dc0(previous
// record, id) is true); a null slot is skipped (`test eax, eax` before the call), so a handler that does nothing is
// the same as no handler.
// 231: TU {0x82464160, 0x82464160, 0, ..} = 0x82463c18(agent, v1 = gameTracker+0x1270, v2 = gameTracker+0x1260) (the
//      helper with the doppelganger branch, MoveTo above); PC {tru+0x35f550, 0, ..} = tru+0x35f470 (retail 0x8245f930,
//      without the branch). Slot 0 differs from the PC only on MoveTo paths 3..6 (frames n x 100 <= animation +0x28:
//      the TU then does nothing outside doppelganger mode and runs its branch inside); slot 1 is TU-only.
// 1004: TU {0x8245efc8, 0x8245efc8, 0x8245f050, ..}: 0x8245efc8 = unless the bool parameter 0x415 is set: clear the
//      8-slot hit list player +0xa4 (the list state 1013 fills); then 0x823dfc98(player) (moved-equal = retail
//      0x823ddaf8 = PC tru+0x3036c0). PC {tru+0x35e020, 0, tru+0x35e060, ..}: tru+0x35e020 = clear (tru+0x2e6950) +
//      print stub + tru+0x3036c0 always (= retail 0x8245ba70); slot 2 is the same on all three (player +0xc4 = 0).
// Switches [States] Translate231Slot0 / Translate231Slot1 / Translate1004 (default 0, read again at run time): 0 = the
// PC handler runs (slot 1: nothing) and a line says what the TU would do differently ("off (would)").
int g_translate231s0 = 0, g_translate231s1 = 0, g_translate1004 = 0;
int g_probe231 = 1;                              // [Probe] States231And1004: wrap / add the slots at all
bool g_s231Ok = false, g_reg231 = false, g_reg1004 = false;
int g_translate1008 = 0;                         // 0.6.11 [States] Translate1008 (read again at run time)
bool g_reg1008 = false;                          // 0.6.11: record 1008 of Lara's table copy wrapped
int g_translate1015Exit = 0;                     // 0.6.12 [States] Translate1015Exit (read again at run time)
bool g_reg1015 = false;                          // 0.6.12: slot 2 of record 1015 of Lara's table copy wrapped
const DWORD kState231Pc = 0x0075f550, kState1004Pc = 0x0075e020, kState1004PcSlot2 = 0x0075e060,
            kClearHitList = 0x006e6950, kAfter1004 = 0x007036c0;
typedef void(__fastcall *PlayerFn)(BYTE *player, int);    // tru+0x2e6950 / tru+0x3036c0 (thiscall, no arguments)
StateFn g_orig231 = nullptr, g_orig1004 = nullptr;

bool CheckState231Blocks() {
    struct { DWORD at; const char *hex; const char *what; } const s[] = {
        {kState231Pc, "8b442404 50 a158dbfa00 8d8860120000 51 0570120000 50 e804ffffff 83c40c c3",
         "state 231 slot 0 tru+0x35f550 (tru+0x35f470(gT+0x1270, gT+0x1260, agent))"},
        {kState1004Pc, "a158dbfa00 8b8804050000 e82089f8ff 8b0d58dbfa00 8b9104050000 8b0a e85d77eeff a158dbfa00 "
                       "8b8804050000 e96d56faff", "state 1004 slot 0 tru+0x35e020"},
        {kState1004PcSlot2, "a158dbfa00 8b8804050000 c781c400000000000000 c3", "state 1004 slot 2 tru+0x35e060"},
        {kClearHitList, "33c0 8981a4000000 8981a8000000 8981ac000000 8981b0000000 8981b4000000 8981b8000000 "
                        "8981bc000000 8981c0000000 c3", "hit list clear tru+0x2e6950 (player +0xa4..+0xc0)"},
        {kAfter1004, "57 8bf9 8b470c 85c0 7457 8b08 85c9 751c 834004ff", "tru+0x3036c0 (TU 0x823dfc98)"},
        {0x006457a0, "c3", "print stub tru+0x2457a0"},
    };
    for (const auto &c : s)
        if (!HexAt(c.at, c.hex)) { Log(0, "states 231 / 1004: %s at 0x%08lx does not match - not wrapped", c.what, c.at); return false; }
    return true;
}

Trace g_t231[2] = {{"state 231 slot 0 (TU 0x82464160 = 0x82463c18 to gameTracker+0x1260, facing +0x1270)"},
                   {"state 231 slot 1 (TU 0x82464160, TU-only slot: re-enter)"}};
void State231(void *agent, int slot) {
    ReadSwitches();
    const bool apply = slot == 0 ? g_translate231s0 != 0 : g_translate231s1 != 0;
    bool runPc = !apply && slot == 0;
    __try {
        BYTE *gt = GameTracker();
        __declspec(align(16)) float face[4], point[4];
        Copy4(face, reinterpret_cast<const float *>(gt + 0x1270));
        Copy4(point, reinterpret_cast<const float *>(gt + 0x1260));
        int frames = 0;
        float time = 0.0f;
        const int path = MoveTo(agent, face, point, apply, &frames, &time);
        const bool differs = slot == 1 || (path >= 3 && path <= 6);
        if (apply || differs)
            TraceLog(g_t231[slot], true, path, "%s point %.1f %.1f %.1f, frame count %d, animation +0x28 %.1f, move path %d "
                     "(1 / 2 mode 2 / 3 as the PC, 3 / 4 TU: nothing, 5 / 6 TU doppelganger branch, 7 / 8 animation frames)%s",
                     apply ? "ON:" : "off (would):", point[0], point[1], point[2], frames, time, path,
                     runPc ? " - the PC handler runs instead" : "");
        else if (g_logLevel >= 2)
            TraceLog(g_t231[slot], false, path, "off: move path %d = the PC path", path);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 231 slot %d: access fault - %s", slot, runPc ? "PC handler runs" : "skipped");
    }
    if (runPc && g_orig231) g_orig231(agent);
}
void __cdecl State231Slot0(void *agent) { State231(agent, 0); }
void __cdecl State231Slot1(void *agent) { State231(agent, 1); }

Trace g_t1004[2] = {{"state 1004 slot 0 (TU 0x8245efc8: hit list +0xa4 kept with parameter 0x415)"},
                    {"state 1004 slot 1 (TU 0x8245efc8, TU-only slot: re-enter)"}};
void State1004(void *agent, int slot) {
    ReadSwitches();
    const bool apply = g_translate1004 != 0;
    char keep = 0;
    BYTE *player = nullptr;
    DWORD used = 0;
    __try {
        void *node = reinterpret_cast<ParamNodeFn>(kParamNode)(agent, 0, 0x415);
        if (node) reinterpret_cast<ParamBoolFn>(kParamBool)(node, 0, 0x415, &keep);
        player = *reinterpret_cast<BYTE **>(GameTracker() + 0x504);
        for (int k = 0; k < 8; ++k)
            if (reinterpret_cast<const DWORD *>(player + 0xa4)[k]) ++used;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1004 slot %d: access fault reading parameter 0x415 / the hit list", slot);
        player = nullptr;
    }
    // TU: keep -> the list stays; slot 1 runs the same function. PC: slot 0 always clears, slot 1 nothing.
    const bool differs = slot == 1 || keep;
    if (apply || differs)
        TraceLog(g_t1004[slot], true, (slot == 1 ? 10 : 0) + (keep ? 1 : 0), "%s parameter 0x415 %d, hit list slots used "
                 "%lu -> TU: %s, then tru+0x3036c0 (TU 0x823dfc98)%s", apply ? "ON:" : "off (would):", keep ? 1 : 0, used,
                 keep ? "list kept" : "list cleared",
                 apply ? "" : slot == 0 ? " - PC: list cleared (tru+0x35e020 runs)" : " - PC: no slot 1, nothing runs");
    if (!apply || !player) {
        if (slot == 0 && g_orig1004) g_orig1004(agent);
        return;
    }
    __try {
        if (!keep) reinterpret_cast<PlayerFn>(kClearHitList)(player, 0);
        reinterpret_cast<PlayerFn>(kAfter1004)(player, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1004 slot %d: access fault in the translation", slot);
    }
}
void __cdecl State1004Slot0(void *agent) { State1004(agent, 0); }
void __cdecl State1004Slot1(void *agent) { State1004(agent, 1); }

// ---------------------------------------------------------------- 0.3: state 1013 slot 0 probe (finisher)
// TU 0x823e0a88 (= retail 0x823de6d0 = PC tru+0x31d600 via tru+0x35e090): the finisher on a target (query 0x162
// animation, 0x80-byte hit record, message 0xf4). The TU takes the target from targeter 9 in doppelganger mode
// (0x823e0ac8..0x823e0b0c, else 0x823dd260(player, 5)) and writes the hit record +0x68 from the attack data (player
// +0xc4) +1 instead of retail's 0xff (0x823e0dc4 / 0x823e0e4c). Not translated yet (VMX body); this probe only logs
// what the TU would hit and what the PC hits, then runs the PC handler.
const DWORD kState1013Pc = 0x0075e090;
const char *const kState1013PcHex = "a158dbfa00 8b8804050000 e960f5fbff";
StateFn g_orig1013 = nullptr;
int g_probe1013 = 1;               // [Probe] State1013
Probe g_p1013 = {"state 1013 slot 0 (finisher, PC tru+0x31d600; TU 0x823e0a88)"};
void __cdecl State1013Slot0(void *agent) {
    __try {
        int dg = Doppelganger();
        BYTE *player = *reinterpret_cast<BYTE **>(GameTracker() + 0x504);
        BYTE *pcTarget = TargetOf(player, 5);
        BYTE *tuTarget = dg ? (g_listOk ? TargeterObject(9) : nullptr) : pcTarget;
        const BYTE *attack = *reinterpret_cast<const BYTE *const *>(player + 0xc4);
        Hit(g_p1013, dg, "PC target (targeter 5) 0x%08lx, TU target (doppelganger: targeter 9) 0x%08lx, attack data "
                         "0x%08lx", reinterpret_cast<DWORD>(pcTarget), reinterpret_cast<DWORD>(tuTarget),
            reinterpret_cast<DWORD>(attack));
        if (dg && attack) Log(2, "state 1013: attack data +1 (TU hit record +0x68) = %u, retail 0xff", attack[1]);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    if (g_orig1013) g_orig1013(agent);
}

// ---------------------------------------------------------------- 0.4: state 1013 slot 0, doppelganger branch
// TU 0x823e0a88 = retail 0x823de6d0 = PC tru+0x31d600 except (Befund-Schattenkampf section 10 / 11):
//   1. 0x823e0ac8..0x823e0b0c: doppelganger -> the handle of targeter 9 (if non-null) instead of 0x823dd260(player, 5)
//   2. 0x823e0bac..0x823e0be4: the target goes into the player's 8-slot hit list +0xa4 (first empty slot, unless
//      present) - the same loop retail has in another attack function (retail 0x823defd4 / TU 0x823e1530)
//   3. 0x823e0dc4 / 0x823e0e4c: hit record +0x68 = attack data (player +0xc4) byte +1, retail 0xff
//   4. 0x823e0e84: message record +0x3c = 0 (retail leaves it)
// +0x34 (gameTracker+0x858 -> +0x50 -> +8, retail r24 = TU r23 = PC ebx) and +0x38 (hit record) are the same on all.
// The PC function runs; three call / push sites in it are redirected (only with [States] Translate1013=1):
//   tru+0x31d610 call tru+0x31c9a0 (target, 1.), tru+0x31d825 push 0xff (22nd argument of the hit record builder
//   tru+0x23c9b0 = record +0x68, 3.), tru+0x31d895 call tru+0x245de0 (message record, 2. + 4.).
// Outside doppelganger mode every site does exactly what the PC code did.
// 0.4.1: the three sites are patched at the start whenever their byte checks pass (also with Translate1013=0, then
// every site runs the PC path - the same as outside doppelganger mode), so the switch can be turned on / off at run
// time (ReadSwitches, at most once per second; the decision is taken per call at the target site).
int g_translate1013 = 0;           // [States] Translate1013
bool g_t1013Patched = false;       // 0.4.1: the three sites are redirected
volatile LONG g_t1013Active = 0;   // set per call of tru+0x31d600 by the target site
void ReadSwitches();               // 0.4.1, defined with the strike below
DWORD g_back1013 = 0x0071d82a;
Probe g_p1013t = {"state 1013 translation (TU 0x823e0a88 doppelganger branch)"};
typedef DWORD *(__fastcall *TargetInnerFn)(BYTE *player, int, int index);     // tru+0x31c9a0 = TU 0x823dd138
typedef BYTE *(__cdecl *Record1013Fn)(BYTE *target, BYTE *player, const float *pos, const float *rot, float frames,
                                      DWORD x34, BYTE *hit);                    // tru+0x245de0

DWORD *__fastcall Target1013(BYTE *player, int, int index) {
    DWORD *h = reinterpret_cast<TargetInnerFn>(0x0071c9a0)(player, 0, index);
    ReadSwitches();
    LONG active = (g_translate1013 && g_listOk && Doppelganger()) ? 1 : 0;
    InterlockedExchange(&g_t1013Active, active);
    if (!active) return h;
    __try {
        BYTE **list = List();
        DWORD *h9 = (list && list[9]) ? reinterpret_cast<TargeterTargetFn>(kTargeterTarget)(list[9], 0) : nullptr;
        if (h9) {
            Hit(g_p1013t, 1, "target of targeter 9: 0x%08lx (PC targeter 5: 0x%08lx)",
                reinterpret_cast<DWORD>(HandleObject(h9)), reinterpret_cast<DWORD>(HandleObject(h)));
            return h9;
        }
        Hit(g_p1013t, 0, "targeter 9 has no handle - the targeter-5 target 0x%08lx stays (as the TU)",
            reinterpret_cast<DWORD>(HandleObject(h)));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1013 translation: access fault at the target - PC target kept");
    }
    return h;
}

DWORD __cdecl Class1013() {
    if (!g_t1013Active) return 0xff;
    DWORD v = 0xff;
    __try {
        const BYTE *player = *reinterpret_cast<const BYTE *const *>(GameTracker() + 0x504);
        const BYTE *attack = *reinterpret_cast<const BYTE *const *>(player + 0xc4);
        v = attack[1];
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        v = 0xff;
    }
    Log(2, "state 1013 translation: hit record +0x68 = %lu (attack data +1), PC 0xff", v);
    return v;
}

// replaces `push 0xff` at tru+0x31d825 (eax = the facing just returned, ecx / edx / xmm dead there)
__declspec(naked) void PushClass1013() {
    __asm {
        push eax
        call Class1013
        xchg eax, [esp]
        jmp dword ptr [g_back1013]
    }
}

// 0.6.6 P1c link E (section 0.6.6 below): with the Vaulted chain placed and [Death] TranslateVaulted=1 the record
// gets +0x3c = 0 in every mode, as the TU 0x823e0e84 (stw r30 = 0, outside the doppelganger branch); 0.4 wrote it only
// with the doppelganger translation. B reads +0x3c as the Vaulted step.
int g_translateVaulted = 1;        // [Death] TranslateVaulted (0.6.6, live through P1dReadSwitches)
int g_translateT5 = 1;             // [Death] TranslateT5 (0.6.6, live through P1dReadSwitches)
int g_translateClock = 1;          // [Death] TranslateVaultedClock (0.6.6, live through P1dReadSwitches)
bool g_vaultChain = false;         // 0.6.6: all six links of the Vaulted chain placed
int g_hitTranslate = 1;            // [Hit] Translate (0.6.7, live through P1dReadSwitches)
int g_hitKnock = 1;                // [Hit] TranslateKnockback (0.6.7, live)
int g_hitLog = 1;                  // [Hit] Log (0.6.7, live)
int g_hitImpulseGate = 1;          // [Hit] TranslateImpulseGate (0.6.8, live)
int g_deathLog = 1;                // [Death] Log (0.6.9, live): chunkdoll build + death switch lines
int g_hitSpeed = 1;                // [Hit] TranslateHitSpeed (0.6.10, live): msg+0x44 / +0x48 from A+0x10 / A+0x14

BYTE *__cdecl Record1013(BYTE *target, BYTE *player, const float *pos, const float *rot, float frames, DWORD x34,
                         BYTE *hit) {
    BYTE *rec = reinterpret_cast<Record1013Fn>(0x00645de0)(target, player, pos, rot, frames, x34, hit);
    if (rec && g_vaultChain && g_translateVaulted) *reinterpret_cast<DWORD *>(rec + 0x3c) = 0;   // 0.6.6 link E
    if (!g_t1013Active) return rec;
    __try {
        if (rec) *reinterpret_cast<DWORD *>(rec + 0x3c) = 0;
        BYTE *p = *reinterpret_cast<BYTE **>(GameTracker() + 0x504);
        DWORD *slots = reinterpret_cast<DWORD *>(p + 0xa4);
        int k = 0;
        for (; k < 8; ++k) {
            if (slots[k] == 0) { slots[k] = reinterpret_cast<DWORD>(target); break; }
            if (slots[k] == reinterpret_cast<DWORD>(target)) break;
        }
        Log(1, "state 1013 translation: message 0xf4 to 0x%08lx, hit list slot %d, record +0x3c = 0",
            reinterpret_cast<DWORD>(target), k);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1013 translation: access fault after the message record");
    }
    InterlockedExchange(&g_t1013Active, 0);
    return rec;
}

bool WriteCall(DWORD at, const void *to) {
    BYTE c[5] = {0xe8};
    DWORD rel = reinterpret_cast<DWORD>(to) - (at + 5);
    memcpy(c + 1, &rel, 4);
    return WriteCode(at, c, 5);
}

void SetupTranslate1013() {
    if (!g_listOk || !g_blocksOk) {
        Log(g_translate1013 ? 0 : 1, "state 1013 translation: target list / building blocks not active - off%s",
            g_translate1013 ? "" : " ([States] Translate1013=0; the switch has no effect in this run)");
        g_translate1013 = 0;
        return;
    }
    struct { DWORD at; const char *hex; const char *what; } const s[] = {
        {0x0071d600, "55 8bec 83e4f0 83ec64 53 56 57 6a05 8bf9 e88bf3ffff 85c0", "tru+0x31d600 head / target call"},
        {0x0071d825, "68ff000000 6a00 6a00 0f2800 8b87c4000000", "push 0xff (hit record +0x68) / attack data +0xc4"},
        {0x0071d895, "e84685f2ff 50 68f4000000 56 e8aa5ee9ff", "message record call / message 0xf4"},
        {0x0063ca36, "8b542460 88486f 8b4c243c 83c404 85c9 895068", "hit record builder: 22nd argument -> +0x68"},
        {0x00645de0, "55 8bec 83e4f0 6a40 e8", "message record builder tru+0x245de0"},
        {0x00645e2b, "894834 895038", "message record +0x34 / +0x38"},
    };
    for (const auto &c : s)
        if (!HexAt(c.at, c.hex)) { Log(0, "state 1013 translation: %s at 0x%08lx does not match - off", c.what, c.at); g_translate1013 = 0; return; }
    if (!WriteCall(0x0071d610, reinterpret_cast<const void *>(&Target1013)) ||
        !WriteJump(0x0071d825, reinterpret_cast<const void *>(&PushClass1013)) ||
        !WriteCall(0x0071d895, reinterpret_cast<const void *>(&Record1013))) {
        Log(0, "state 1013 translation: patch failed - restart without the plugin");
        return;
    }
    g_t1013Patched = true;
    if (g_translate1013)
        Log(1, "state 1013 translation: ON (tru+0x31d610 target, tru+0x31d825 hit class, tru+0x31d895 message record; "
               "doppelganger mode only; [States] Translate1013 read again at most once per second)");
    else
        Log(1, "state 1013 translation: off ([States] Translate1013=0) - sites tru+0x31d610 / +0x31d825 / +0x31d895 "
               "patched but they run the PC path; the switch turns it on at run time (read again at most once per second)");
}

// ---------------------------------------------------------------- 0.5.2: F21 diagnostics, part 2 (log only)
// Entry hooks: a 5-byte jmp at the function entry to a wrapper with the same calling convention; the wrapper calls the
// original through a trampoline (the relocated, position-independent prologue + jmp back) with the same arguments and
// returns its eax. Two call sites (the target list array build / destroy, one caller each) are redirected the same
// way as the 1013 sites. Only targeter slot 9 is logged. Nothing is written into game data.
typedef DWORD(__fastcall *AddFn)(BYTE *t, int, BYTE *inst, DWORD mask, DWORD marker);   // tru+0x3164d0, ret 0xc
typedef DWORD(__fastcall *SetFn)(BYTE *t, int, BYTE *node);                             // tru+0x316730, ret 4
typedef DWORD(__fastcall *SelectFn)(BYTE *t, int);                                      // tru+0x316590, ret
typedef DWORD(__fastcall *RemoveFn)(BYTE *t, int, BYTE *list, BYTE *node);              // tru+0x319f80, ret 8
typedef DWORD(__fastcall *UpdateFn)(BYTE *t, int, DWORD dt);                            // tru+0x31a270, ret 4 (float)
typedef BYTE **(__fastcall *ListBuildFn)(BYTE **mem, int);                              // tru+0x31dc30
typedef DWORD(__fastcall *ListDestroyFn)(BYTE **list, int);                             // tru+0x3167d0
typedef char(__cdecl *EligFn)(const DWORD *handle);                                     // tru+0x2ecca0 = TU 0x82403918
AddFn g_oAdd = nullptr;
SetFn g_oSet = nullptr;
SelectFn g_oSelect = nullptr;
RemoveFn g_oRemove = nullptr;
UpdateFn g_oUpdate = nullptr;
const DWORD kEligibility = 0x006ecca0, kFilter = 0x00712090;
BYTE *g_diagCode = nullptr;        // trampolines, 32 bytes each
DWORD g_t9Seen = 0;                // last +0x90 of slot 9 seen by a hook (changes elsewhere are reported)
volatile LONG g_t9Adds = 0, g_t9Offers = 0, g_t9Removes = 0, g_t9Sets = 0;
DWORD g_t9LastSel = 0xffffffff, g_t9SelTick = 0, g_t9SnapTick = 0, g_t9WhyTick = 0;
TState g_t9Snap;
bool g_t9SnapValid = false;

// one entry hook: trampoline (copy whole instructions, then jmp at + copy) - the jmp is written by EntryPatch
struct EntryHook { DWORD at; const char *hex; int copy; const void *to; void **orig; const char *what; };
bool EntryPrepare(int k, const EntryHook &h) {
    if (!HexAt(h.at, h.hex)) { Log(0, "0.5.2 diag: %s at 0x%08lx does not match - diagnostics off", h.what, h.at); return false; }
    BYTE *tr = g_diagCode + k * 32;
    memcpy(tr, reinterpret_cast<const void *>(h.at), static_cast<size_t>(h.copy));
    tr[h.copy] = 0xe9;
    DWORD rel = (h.at + static_cast<DWORD>(h.copy)) - (reinterpret_cast<DWORD>(tr) + static_cast<DWORD>(h.copy) + 5);
    memcpy(tr + h.copy + 1, &rel, 4);
    *h.orig = tr;
    return true;
}
bool EntryPatch(const EntryHook &h) {
    BYTE j[16];
    memset(j, 0x90, sizeof(j));
    j[0] = 0xe9;
    DWORD rel = reinterpret_cast<DWORD>(h.to) - (h.at + 5);
    memcpy(j + 1, &rel, 4);
    return WriteCode(h.at, j, static_cast<size_t>(h.copy));
}

// a change of slot 9's +0x90 that no hooked function made (seen at the entry of the next hook)
void T9Seen(const BYTE *t, const char *where) {
    DWORD now = Rd(t + 0x90);
    if (now == g_t9Seen) return;
    char obj[96] = "?";
    __try {
        Describe(now ? HandleObject(reinterpret_cast<const DWORD *>(now + 8)) : nullptr, obj, sizeof(obj));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    DiagLog("0.5.2 diag targeter 9: +0x90 0x%08lx -> 0x%08lx (%s) changed outside the hooked functions (seen at %s)",
            g_t9Seen, now, obj, where);
    g_t9Seen = now;
}

const char *OuterName(DWORD ret) {
    switch (ret) {
    case 0x005ba5a8: return "instance init tru+0x1ba5a3 (TU 0x822723a8)";
    case 0x005ba806: return "instance init tru+0x1ba801 (TU 0x82272660)";
    case 0x006d612b: return "tru+0x2d6126 (TU 0x823c6e98)";
    case 0x0071dc98: return "target list ctor tru+0x31dc30 (all instances, TU 0x824062c8)";
    case 0x0071f943: return "player message 0x1dc tru+0x31f93e (TU 0x823eeaec)";
    default: return "?";
    }
}

// tru+0x3164d0 (TU 0x82404650): candidate offered to one targeter; taken when mask & [t+4]
DWORD __fastcall DiagAdd(BYTE *t, int edx, BYTE *inst, DWORD mask, DWORD marker) {
    const DWORD ret = reinterpret_cast<DWORD>(_ReturnAddress());
    const DWORD *entry = reinterpret_cast<const DWORD *>(_AddressOfReturnAddress());
    const bool s9 = g_diagT9 && IsSlot9(t);
    DWORD before = s9 ? Rd(t + 0xc) : 0;
    if (s9) T9Seen(t, "candidate add");
    DWORD r = g_oAdd(t, edx, inst, mask, marker);
    if (!s9) return r;
    __try {
        // outer caller: the return of tru+0x316860 at [esp + 0x38] when called from its two loops (0x71693e / 0x7169c8)
        DWORD outer = (ret == 0x00716943 || ret == 0x007169cd) ? entry[0x38 / 4] : 0;
        DWORD bit = Rd(t + 4);
        bool taken = (mask & bit) != 0;
        LONG n = InterlockedIncrement(taken ? &g_t9Adds : &g_t9Offers);
        char who[96];
        Describe(inst, who, sizeof(who));
        if (taken ? (n <= 300 || n % 100 == 0) : (n <= 60 || n % 500 == 0))
            DiagLog("0.5.2 diag targeter 9 candidate %s (%s %ld): %s, marker data 0x%08lx, mask 0x%03lx (slot bit 0x%03lx), "
                    "candidates %lu -> %lu; caller 0x%08lx, outer 0x%08lx %s", taken ? "TAKEN" : "not offered (mask)",
                    taken ? "add" : "offer", n, who, marker, mask, bit, before, Rd(t + 0xc), ret, outer,
                    outer ? OuterName(outer) : (ret == 0x00776c00 ? "script native tru+0x376ba0 (TU 0x824788a8, index 1)" : ""));
        g_t9Seen = Rd(t + 0x90);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return r;
}

// tru+0x316730 (TU 0x82406190): set the target node +0x90
DWORD __fastcall DiagSet(BYTE *t, int edx, BYTE *node) {
    const DWORD ret = reinterpret_cast<DWORD>(_ReturnAddress());
    const bool s9 = g_diagT9 && IsSlot9(t);
    DWORD before = s9 ? Rd(t + 0x90) : 0;
    if (s9) T9Seen(t, "set target");
    DWORD r = g_oSet(t, edx, node);
    if (!s9) return r;
    __try {
        DWORD after = Rd(t + 0x90);
        LONG n = InterlockedIncrement(&g_t9Sets);
        if (after != before || n <= 20) {
            char obj[96];
            Describe(node ? HandleObject(reinterpret_cast<const DWORD *>(node + 8)) : nullptr, obj, sizeof(obj));
            DiagLog("0.5.2 diag targeter 9 SET target (tru+0x316730, call %ld): node 0x%08lx (%s), +0x90 0x%08lx -> 0x%08lx, "
                    "flags 0x%lx; caller 0x%08lx", n, reinterpret_cast<DWORD>(node), obj, before, after, Rd(t + 8), ret);
        }
        g_t9Seen = after;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return r;
}

// tru+0x316590 (TU 0x82405b90): pick the first bucket entry that passes eligibility / exclusion / sight test
DWORD __fastcall DiagSelect(BYTE *t, int edx) {
    const DWORD ret = reinterpret_cast<DWORD>(_ReturnAddress());
    const bool s9 = g_diagT9 && IsSlot9(t);
    if (s9) T9Seen(t, "select");
    DWORD r = g_oSelect(t, edx);
    if (!s9) return r;
    __try {
        DWORD now = GetTickCount();
        if (r != g_t9LastSel || now - g_t9SelTick >= 5000) {
            TState s;
            ReadT(t, &s);
            DWORD inBuckets = s.bucket[0] + s.bucket[1] + s.bucket[2] + s.bucket[3];
            char obj[96], st[300];
            Describe(r ? HandleObject(reinterpret_cast<const DWORD *>(r + 8)) : nullptr, obj, sizeof(obj));
            FormatT(s, st, sizeof(st));
            DiagLog("0.5.2 diag targeter 9 SELECT (tru+0x316590): -> node 0x%08lx (%s)%s; %s; caller 0x%08lx", r, obj,
                    (!r && inBuckets) ? " - bucket entries present but none passed eligibility / gameTracker+0x610 "
                                        "exclusion / sight test tru+0x313200" : "", st, ret);
            g_t9LastSel = r;
            g_t9SelTick = now;
        }
        g_t9Seen = Rd(t + 0x90);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return r;
}

// tru+0x319f80: remove a node from a bucket / the rejected list (clears +0x90 when it is the target)
DWORD __fastcall DiagRemove(BYTE *t, int edx, BYTE *list, BYTE *node) {
    const DWORD ret = reinterpret_cast<DWORD>(_ReturnAddress());
    const bool s9 = g_diagT9 && IsSlot9(t);
    DWORD before = s9 ? Rd(t + 0x90) : 0;
    char obj[96] = "";
    if (s9) {
        T9Seen(t, "remove");
        __try {
            Describe(node ? HandleObject(reinterpret_cast<const DWORD *>(node + 8)) : nullptr, obj, sizeof(obj));
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
    DWORD r = g_oRemove(t, edx, list, node);
    if (!s9) return r;
    __try {
        DWORD after = Rd(t + 0x90);
        LONG n = InterlockedIncrement(&g_t9Removes);
        if (after != before || n <= 100)
            DiagLog("0.5.2 diag targeter 9 REMOVE (tru+0x319f80, call %ld): node 0x%08lx (%s; object gone = 0) from list "
                    "0x%08lx (%s)%s; candidates now %lu; caller 0x%08lx", n, reinterpret_cast<DWORD>(node), obj,
                    reinterpret_cast<DWORD>(list), reinterpret_cast<DWORD>(list) == reinterpret_cast<DWORD>(t) + 0x3c ?
                    "rejected list" : "bucket", after != before ? " - it was the TARGET, +0x90 cleared" : "", Rd(t + 0xc), ret);
        g_t9Seen = after;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return r;
}

// tru+0x312090 (filter of one group): ecx = frame (targeter +0x50), edx = handle, one stack argument the caller removes
__declspec(naked) char __cdecl CallFilter(DWORD /*frame*/, DWORD /*handle*/, DWORD /*group*/) {
    __asm {
        mov ecx, [esp + 4]
        mov edx, [esp + 8]
        push dword ptr [esp + 12]
        mov eax, 0x00712090
        call eax
        add esp, 4
        ret
    }
}

// [Diag] Targeter9Why: for the first rejected candidates the game's own eligibility / filter (same functions the
// update calls for them every frame) - which test sends them to the rejected list
// 0.5.3: the walk follows node +4 (next). The list append tru+0x2ecd40 links tail +4 -> new node and new +0 -> old tail
// (+0 = prev), the select walk tru+0x3166f3 reads `mov esi, [esi+4]`; 0.5.2 followed +0 from the head (prev = 0) and so
// reported only the first rejected candidate.
struct WhyLast { DWORD obj, result; DWORD tick; } g_why[8];
void DiagWhy(BYTE *t, const TState &s) {
    const BYTE *params = reinterpret_cast<const BYTE *>(Rd(t + 0x34));
    BYTE *player = Player();
    BYTE *node = reinterpret_cast<BYTE *>(Rd(t + 0x3c));
    for (int k = 0; node && k < 4; ++k, node = reinterpret_cast<BYTE *>(Rd(node + 4))) {
        const DWORD *handle = reinterpret_cast<const DWORD *>(node + 8);
        BYTE *obj = HandleObject(handle);
        char elig = reinterpret_cast<EligFn>(kEligibility)(handle);
        DWORD pass = 0;
        for (DWORD g = 0; elig && params && g < s.groups && g < 8; ++g)
            if (CallFilter(reinterpret_cast<DWORD>(t) + 0x50, reinterpret_cast<DWORD>(handle), Rd(params + 8 + g * 4)))
                pass |= 1u << g;
        DWORD result = (elig ? 0x100 : 0) | pass, now = GetTickCount();
        WhyLast &w = g_why[k];
        if (w.obj == reinterpret_cast<DWORD>(obj) && w.result == result && now - w.tick < 10000) continue;
        w.obj = reinterpret_cast<DWORD>(obj);
        w.result = result;
        w.tick = now;
        char who[96];
        Describe(obj, who, sizeof(who));
        float d[3] = {0, 0, 0}, dist = -1.0f;
        if (obj && player) {
            for (int i = 0; i < 3; ++i)
                d[i] = reinterpret_cast<const float *>(obj + 0x20)[i] - reinterpret_cast<const float *>(player + 0x20)[i];
            dist = sqrtf(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
        }
        DiagLog("0.5.2 diag targeter 9 WHY rejected #%d: %s, marker data 0x%08lx, node +0x18 %lu: eligibility tru+0x2ecca0 "
                "%d (queries 0x14c / 0xca / 0x185 / 0x1d), filter groups passed 0x%02lx of %lu (tru+0x312090: distance / "
                "angle records); instance - Lara (+0x20): %.1f %.1f %.1f, distance %.1f", k, who, Rd(node + 0x14),
                Rd(node + 0x18), elig ? 1 : 0, pass, s.groups, d[0], d[1], d[2], dist);
    }
}

// ---------------------------------------------------------------- 0.5.3: TscTargeterSnapshot (read-only export)
// TruMenu 0.13 (Thrall-Labels, debug view stage S1) draws per instance whether it sits in a bucket of targeter 9, in its
// rejected list (with the last WHY result of DiagWhy) or is the target, whether it is in the player's hit list, and
// the last condition 2011. The copy is built on the game thread at the end of slot 9's per-frame update (DiagUpdate,
// after the original ran) and only while a reader asked within the last 2 s; the export copies it under a sequence
// counter (odd = being written). Nothing is written into game data, no game function is called for it.
// Lists (list append tru+0x2ecd40): +0 head, +4 tail, +8 count; node +0 prev, +4 next, +8 handle {object, id},
// +0x14 marker data. Hit list: [[0xfadb58]+0x504] +0xa4, 8 slots (state 1004 slot 0 tru+0x35e020 clears it through
// tru+0x2e6950 with ecx = that object).
const int kSnapEntries = 24;
struct TscT9Entry {
    const void *instance;    // object of the node's handle (0 = stale handle)
    DWORD where;             // 0x10 + g = bucket of filter group g, 0x20 = rejected list
    DWORD why;               // rejected only: last WHY result (0x100 = eligibility passed, low byte = groups passed);
                             // 0xffffffff = not evaluated (WHY looks at the first 4 rejected, once per second)
    DWORD whyTick;           // GetTickCount of that WHY result (0 = none)
    DWORD marker;            // node +0x14
};
struct TscTargeterSnapshotV1 {
    DWORD size, version;     // sizeof(TscTargeterSnapshotV1), 1
    DWORD tick, built;       // GetTickCount of the copy, copies built so far
    const void *targeter;    // slot 9 (TU index 9)
    const void *target;      // object of +0x90 (0 = none / stale handle)
    DWORD node, flags, candidates, groups, bucket[4], rejected;
    DWORD count, truncated;  // entries used; 1 = more nodes than kSnapEntries
    TscT9Entry entries[kSnapEntries];
    const void *hitList[8];  // [[0xfadb58]+0x504] +0xa4
    DWORD c2011Calls, c2011Tick, c2011Path, c2011Result;   // last condition 2011 (doppelganger branch; path as the log)
    LONG c2011Query;         // answer to query 0x161 (-1 = not asked)
    const void *c2011Target;
};
// version 1 layout = TruMenu 0.13's LblTscSnap (same static_assert there); a change needs version 2
static_assert(sizeof(TscT9Entry) == 20 && sizeof(TscTargeterSnapshotV1) == 604, "TscTargeterSnapshot v1 layout");
TscTargeterSnapshotV1 g_snap;            // written by SnapBuild (game thread) only
volatile LONG g_snapSeq = 0;             // odd while SnapBuild writes
volatile LONG g_snapAsked = 0;           // GetTickCount | 1 of the last export call (0 = never asked)
bool g_diagOn = false;                   // the 0.5.2 hooks are placed
bool g_snapHitOk = false;                // hit list facts checked (SetupDiag)

void SnapList(TscTargeterSnapshotV1 &s, const BYTE *list, DWORD where) {
    const BYTE *node = reinterpret_cast<const BYTE *>(Rd(list));
    for (int guard = 0; node && guard < 256; ++guard, node = reinterpret_cast<const BYTE *>(Rd(node + 4))) {
        if (s.count >= static_cast<DWORD>(kSnapEntries)) { s.truncated = 1; return; }
        TscT9Entry &e = s.entries[s.count++];
        e.instance = HandleObject(reinterpret_cast<const DWORD *>(node + 8));
        e.where = where;
        e.marker = Rd(node + 0x14);
        e.why = 0xffffffff;
        e.whyTick = 0;
        if (where != 0x20) continue;
        for (const WhyLast &w : g_why)
            if (w.tick && w.obj == reinterpret_cast<DWORD>(e.instance)) { e.why = w.result; e.whyTick = w.tick; break; }
    }
}
void SnapBuild(BYTE *t, const TState &st) {
    InterlockedIncrement(&g_snapSeq);    // odd: being written
    TscTargeterSnapshotV1 &s = g_snap;
    DWORD built = s.built;
    memset(&s, 0, sizeof(s));
    s.size = sizeof(s);
    s.version = 1;
    s.built = built + 1;
    __try {
        s.targeter = t;
        s.target = st.obj;
        s.node = st.node;
        s.flags = st.flags;
        s.candidates = st.total;
        s.groups = st.groups;
        memcpy(s.bucket, st.bucket, sizeof(s.bucket));
        s.rejected = st.rejected;
        const BYTE *buckets = reinterpret_cast<const BYTE *>(Rd(t + 0x38));
        for (DWORD g = 0; buckets && g < st.groups && g < 4; ++g) SnapList(s, buckets + g * 0x14, 0x10 + g);
        SnapList(s, t + 0x3c, 0x20);
        const BYTE *gt = GameTracker();
        const BYTE *owner = (g_snapHitOk && gt) ? reinterpret_cast<const BYTE *>(Rd(gt + 0x504)) : nullptr;
        for (int k = 0; owner && k < 8; ++k) s.hitList[k] = reinterpret_cast<const void *>(Rd(owner + 0xa4 + 4 * k));
        s.c2011Calls = g_last2011.calls;
        s.c2011Tick = g_last2011.tick;
        s.c2011Path = g_last2011.path;
        s.c2011Result = g_last2011.result;
        s.c2011Query = g_last2011.query;
        s.c2011Target = g_last2011.target;
        s.tick = GetTickCount();
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        s.count = 0;
        s.tick = 0;                      // the export answers 0 for this copy
    }
    InterlockedIncrement(&g_snapSeq);    // even: complete
}

// tru+0x31a270 (TU 0x82404c60): per-frame update of one targeter (re-sort, clear stale / lost target)
DWORD __fastcall DiagUpdate(BYTE *t, int edx, DWORD dt) {
    const DWORD ret = reinterpret_cast<DWORD>(_ReturnAddress());
    const bool s9 = g_diagT9 && IsSlot9(t);
    DWORD before = s9 ? Rd(t + 0x90) : 0;
    if (s9) T9Seen(t, "update");
    DWORD r = g_oUpdate(t, edx, dt);
    if (!s9) return r;
    __try {
        TState s;
        ReadT(t, &s);
        DWORD now = GetTickCount();
        if (s.node != before) {
            char obj[96];
            Describe(s.obj, obj, sizeof(obj));
            DiagLog("0.5.2 diag targeter 9 target changed in the per-frame update tru+0x31a270: +0x90 0x%08lx -> 0x%08lx "
                    "(%s), flags 0x%lx; caller 0x%08lx", before, s.node, obj, s.flags, ret);
        }
        bool counts = !g_t9SnapValid || memcmp(s.bucket, g_t9Snap.bucket, sizeof(s.bucket)) != 0 ||
                      s.rejected != g_t9Snap.rejected || s.total != g_t9Snap.total;
        if ((counts && now - g_t9SnapTick >= 1000) || now - g_t9SnapTick >= 10000) {
            if (counts || s.total || Doppelganger()) {
                char st[300];
                FormatT(s, st, sizeof(st));
                DiagLog("0.5.2 diag targeter 9 state%s (doppelganger %d): %s; adds %ld, not offered %ld, removes %ld",
                        counts ? " changed" : "", Doppelganger(), st, g_t9Adds, g_t9Offers, g_t9Removes);
            }
            g_t9Snap = s;
            g_t9SnapValid = true;
            g_t9SnapTick = now;
        }
        if (g_diagWhy && s.rejected && now - g_t9WhyTick >= 1000) {
            g_t9WhyTick = now;
            DiagWhy(t, s);
        }
        g_t9Seen = Rd(t + 0x90);
        // 0.5.3: the copy for TscTargeterSnapshot, only while a reader (TruMenu's labels) asked within 2 s
        const DWORD asked = static_cast<DWORD>(g_snapAsked);
        if (g_diagSnap && asked && now - asked < 2000) SnapBuild(t, s);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "0.5.2 diag: access fault while logging targeter 9 (update) - the game code ran unchanged");
    }
    return r;
}

// the target list array (7 -> 10 targeters): build at the player init (tru+0x322638) and destroy (tru+0x32219c)
BYTE **__fastcall DiagListBuild(BYTE **mem, int edx) {
    BYTE **list = reinterpret_cast<ListBuildFn>(0x0071dc30)(mem, edx);
    __try {
        BYTE *t = list ? list[9] : nullptr;
        TState s;
        ReadT(t, &s);
        char st[300];
        FormatT(s, st, sizeof(st));
        DiagLog("0.5.2 diag target list BUILT (tru+0x31dc30 from the player init): array 0x%08lx, slots 0..9 = %08lx %08lx "
                "%08lx %08lx %08lx %08lx %08lx %08lx %08lx %08lx; slot 9: index %lu, bit 0x%03lx, parameters 0x%08lx, %s",
                reinterpret_cast<DWORD>(list), Rd(list), Rd(list + 1), Rd(list + 2), Rd(list + 3), Rd(list + 4),
                Rd(list + 5), Rd(list + 6), Rd(list + 7), Rd(list + 8), Rd(list + 9), Rd(t), Rd(t + 4), Rd(t + 0x34), st);
        g_t9Seen = Rd(t + 0x90);
        g_t9SnapValid = false;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return list;
}
DWORD __fastcall DiagListDestroy(BYTE **list, int edx) {
    DiagLog("0.5.2 diag target list DESTROYED (tru+0x3167d0): array 0x%08lx, slot 9 0x%08lx (adds %ld, removes %ld, sets %ld "
            "so far)", reinterpret_cast<DWORD>(list), Rd(list + 9), g_t9Adds, g_t9Removes, g_t9Sets);
    g_t9Seen = 0;
    g_t9SnapValid = false;
    return reinterpret_cast<ListDestroyFn>(0x007167d0)(list, edx);
}

void SetupDiag() {
    if (!g_diagT9) { Log(1, "0.5.2 diag: [Diag] Targeter9=0 - targeter 9 hooks not placed"); return; }
    if (!g_listOk || !g_blocksOk) { Log(1, "0.5.2 diag: target list / building blocks not active - targeter 9 hooks not placed"); return; }
    // layout facts the log relies on (read only)
    struct { DWORD at; const char *hex; const char *what; } const facts[] = {
        {0x0071d913, "8b4d08 890f b801000000 d3e0 33c9 3bd9 894f08 894704 894f0c 895f30 895f34 894f38 894f3c 894f40 894f44",
         "targeter ctor tru+0x31d900: +0 index, +4 bit 1 << index, +8 / +0xc, +0x34 parameters, +0x38 / +0x3c / +0x44"},
        {0x0071d97d, "898f90000000", "targeter ctor: +0x90 target node"},
        {0x00716524, "8d7e08 55 57 e8c2d4e9ff 8b4c2424 83c408 894e14", "candidate node +8 handle, +0x14 marker data"},
        {0x00716548, "8b4b34 85c9 7421 0fb6c0 3b4104 7419 8d1480 8b4338 8d0c90", "bucket index == groups -> rejected list, buckets 0x14"},
        {0x00716570, "8d4b3c 56 e8c767fdff 016b0c", "rejected list +0x3c, candidates +0xc"},
        {0x007131c8, "837e0400 57 7626 8b7c241c 33c0 8b448608 50 8bcf 8bd5 e8adeeffff 83c404", "stage tru+0x3131a0: groups +4, "
         "group pointers +8, filter tru+0x312090 (ecx frame, edx handle, caller removes 4)"},
        {0x00719faf, "015a08", "list count +8"},
        {kEligibility, "57 8b7c2408 f6471001 7504 32c0 5f c3", "eligibility tru+0x2ecca0 (cdecl handle)"},
        {kFilter, "55 8bec 83e4f0 81ecd4010000 53 56 57 8b7d08 0fb64708 8bf2", "filter tru+0x312090"},
        {0x005bcff9, "8b0dd094db00 52 8b14c1", "object name table [0xdb94d0] (as TruTrace)"},
        {0x00722638, "8bc8 e8f1b5ffff a3acdffa00", "target list build call tru+0x32263a"},
        {0x0072219c, "8bf9 e82d46ffff 8b0dac9ccd00", "target list destroy call tru+0x32219e"},
        {0x00716938, "8b0cb1 50 55 53 e88dfbffff 83c601", "instance add loop 1 call tru+0x31693e (return 0x716943)"},
        {0x007169c0, "8b4cb500 6aff 57 53 e803fbffff 83c601", "instance add loop 2 call tru+0x3169c8 (return 0x7169cd)"},
        {0x00716860, "83ec18 53 8b5c2420 3b1d94f0e700 55 8be9 896c241c", "instance add frame (0x18 + 4 registers)"},
        {0x00716891, "56 57", "instance add: esi / edi pushed before both loops"},
        // 0.5.3: list links (WHY walk, snapshot): append tru+0x2ecd40 (tail +4 -> node +4, node +0 = old tail, node +4 =
        // 0, count +8), the select walk tru+0x3166f3 (next = node +4)
        {0x006ecd4b, "894204 8b5104 8910 c7400400000000 83410801", "list append tru+0x2ecd40: node +4 next, +0 prev, +8 count"},
        {0x007166f3, "8b7604 85f6 0f8559ffffff", "select walk tru+0x3166f3: next = node +4"},
    };
    for (const auto &f : facts)
        if (!HexAt(f.at, f.hex)) { Log(0, "0.5.2 diag: %s at 0x%08lx does not match - diagnostics off", f.what, f.at); return; }
    g_namesOk = true;
    const EntryHook hooks[5] = {
        {0x007164d0, "53 55 8b6c240c 85ed 8bd9 0f849e000000 8b442410 854304", 6, &DiagAdd, reinterpret_cast<void **>(&g_oAdd),
         "candidate add tru+0x3164d0"},
        {0x00716730, "a158dbfa00 56 8bf1 8b8804050000 8b09 f6414001", 5, &DiagSet, reinterpret_cast<void **>(&g_oSet),
         "set target tru+0x316730"},
        {0x00716590, "83ec08 55 8be9 8b4534 834d0802 85c0 7505", 6, &DiagSelect, reinterpret_cast<void **>(&g_oSelect),
         "select tru+0x316590"},
        {0x00719f80, "53 56 57 8b7c2414 83cbff 85ff 8bf1 7422", 7, &DiagRemove, reinterpret_cast<void **>(&g_oRemove),
         "remove node tru+0x319f80"},
        {0x0071a270, "51 d9ee 56 8bf1 d89694000000 dfe0", 6, &DiagUpdate, reinterpret_cast<void **>(&g_oUpdate),
         "per-frame update tru+0x31a270"},
    };
    g_diagCode = static_cast<BYTE *>(VirtualAlloc(nullptr, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    if (!g_diagCode) { Log(0, "0.5.2 diag: no code page (%lu) - diagnostics off", GetLastError()); return; }
    for (int k = 0; k < 5; ++k)
        if (!EntryPrepare(k, hooks[k])) return;
    DWORD old = 0;
    if (!VirtualProtect(g_diagCode, 4096, PAGE_EXECUTE_READ, &old)) {
        Log(0, "0.5.2 diag: code page protection failed (%lu) - diagnostics off", GetLastError());
        return;
    }
    // all checks passed: from here every write is a jmp / call to a wrapper that runs the original unchanged
    for (int k = 0; k < 5; ++k)
        if (!EntryPatch(hooks[k])) { Log(0, "0.5.2 diag: patch %s failed - restart without the plugin", hooks[k].what); return; }
    if (!WriteCall(0x0072263a, reinterpret_cast<const void *>(&DiagListBuild)) ||
        !WriteCall(0x0072219e, reinterpret_cast<const void *>(&DiagListDestroy))) {
        Log(0, "0.5.2 diag: patch of the list build / destroy calls failed - restart without the plugin");
        return;
    }
    Log(1, "0.5.2 diag: targeter 9 (log only) - entries tru+0x3164d0 add, +0x316730 set, +0x316590 select, +0x319f80 "
           "remove, +0x31a270 update; calls tru+0x32263a list build, +0x32219e destroy; why %d, condition 2011 %d, max %d lines",
        g_diagWhy, g_diag2011, g_diagMax);
    g_diagOn = true;
    // 0.5.3 snapshot: the hit list owner [[0xfadb58]+0x504] (state 1004 slot 0) and its 8 slots +0xa4..+0xc0 (clear)
    g_snapHitOk = HexAt(0x0075e020, "a158dbfa00 8b8804050000 e82089f8ff") &&
                  HexAt(0x006e6950, "33c0 8981a4000000 8981a8000000 8981ac000000 8981b0000000 8981b4000000 8981b8000000 "
                                    "8981bc000000 8981c0000000 c3");
    Log(1, "0.5.3 snapshot: TscTargeterSnapshot (read-only export for TruMenu's thrall labels) %s, hit list %s",
        g_diagSnap ? "on - built only while a reader asks" : "off ([Diag] Snapshot=0)",
        g_snapHitOk ? "verified" : "bytes differ - left empty");
}

void __cdecl State1007Slot4(void *agent) { State1007(agent, 4); }
void __cdecl State1007Slot5(void *agent) { State1007(agent, 5); }

// ---------------------------------------------------------------- 0.2: the shadow strike (state 1014, doppelganger)
// TU meter fields the strike owns (+0x15 look latch, +0x18 / +0x1c target handle, +0x28 strike count, +0x2c
// frames) are kept here; flags / value / requests / drain come from TruShadowPower (TruShadowPowerMeterApi).
struct Strike { BYTE latch; DWORD target[2]; LONG count; float frames; } g_strike = {0, {0, 0}, 0, 0.0f};
int g_strikeTranslate = 0;          // [Strike] Translate
Probe g_pStrike = {"shadow strike (TU 0x823d86a8: placement + message 0xbe)"};

// ---------------------------------------------------------------- 0.4.1: the two switches at run time
// TruMenu's TO TEST switches (sc-strike, sc-translate1013) write TruShadowCombat.ini at once. [Strike] Translate and
// [States] Translate1013 are read again from it at most once per second, from the code they switch (state 1014
// slots, the 1013 target site) - so a change counts from the next strike / finisher. Nothing new is built: they
// only turn the code on / off that the start installed and byte-checked (1014 wrappers, 1013 sites); without it a
// change is logged as "no effect". A strike that runs keeps the translation until its end (slot 2 clears meter flag
// 2) - else its end would never run. A missing key / file keeps the current value.
volatile LONG g_switchTick = 0;
int g_strikeWaitLogged = 0;

void ReadSwitches() {
    if (!g_iniPath[0]) return;
    const LONG now = static_cast<LONG>(GetTickCount() | 1);
    const LONG last = g_switchTick;
    if (static_cast<DWORD>(now) - static_cast<DWORD>(last) < 1000) return;
    if (InterlockedCompareExchange(&g_switchTick, now, last) != last) return;
    int strike = GetPrivateProfileIntA("Strike", "Translate", g_strikeTranslate, g_iniPath) ? 1 : 0;
    if (strike != (g_strikeTranslate ? 1 : 0)) {
        const TruShadowPowerMeter *m = g_strikeTranslate ? g_meter : nullptr;
        if (m && (*m->flags & 2)) {
            if (!g_strikeWaitLogged)
                Log(1, "0.4.1 switch: [Strike] Translate %d -> %d waits - a translated strike runs (meter flags 0x%03lx)",
                    g_strikeTranslate ? 1 : 0, strike, *m->flags);
            g_strikeWaitLogged = 1;
        } else {
            Log(1, "0.4.1 switch: [Strike] Translate %d -> %d (read again from TruShadowCombat.ini)%s",
                g_strikeTranslate ? 1 : 0, strike,
                !g_orig1014[0] ? " - state 1014 not wrapped at the start: no effect in this run"
                : (strike && !g_strikeOk) ? " - strike building blocks not verified: no effect in this run" : "");
            g_strikeTranslate = strike;
            g_strikeWaitLogged = 0;
        }
    }
    int t1013 = GetPrivateProfileIntA("States", "Translate1013", g_translate1013, g_iniPath) ? 1 : 0;
    if (t1013 != (g_translate1013 ? 1 : 0)) {
        Log(1, "0.4.1 switch: [States] Translate1013 %d -> %d (read again from TruShadowCombat.ini)%s",
            g_translate1013 ? 1 : 0, t1013,
            g_t1013Patched ? "" : " - the 1013 sites are not patched: no effect in this run");
        g_translate1013 = t1013;      // only the patched target site reads it
    }
    // 0.5: states 1019 / 1020 (the handlers are registered at the start whenever their checks pass; the switch only
    // decides whether they act or only log)
    int t1019 = GetPrivateProfileIntA("States", "Translate1019", g_translate1019, g_iniPath) ? 1 : 0;
    if (t1019 != (g_translate1019 ? 1 : 0)) {
        Log(1, "0.5 switch: [States] Translate1019 %d -> %d (read again from TruShadowCombat.ini)%s", g_translate1019 ? 1 : 0,
            t1019, g_reg1019 ? "" : " - state 1019 not registered (yet): no effect until it is");
        g_translate1019 = t1019;
    }
    int t1020 = GetPrivateProfileIntA("States", "Translate1020", g_translate1020, g_iniPath) ? 1 : 0;
    if (t1020 != (g_translate1020 ? 1 : 0)) {
        Log(1, "0.5 switch: [States] Translate1020 %d -> %d (read again from TruShadowCombat.ini)%s", g_translate1020 ? 1 : 0,
            t1020, g_reg1020 ? "" : " - state 1020 not registered (yet): no effect until it is");
        g_translate1020 = t1020;
    }
    // 0.5.1: states 231 / 1004
    // 0.6.11: state 1008 (same handling: the wrappers decide per call)
    // 0.6.12: state 1015 exit (same handling)
    struct { const char *key; int *value; bool *reg; } const sw[5] = {
        {"Translate231Slot0", &g_translate231s0, &g_reg231}, {"Translate231Slot1", &g_translate231s1, &g_reg231},
        {"Translate1004", &g_translate1004, &g_reg1004}, {"Translate1008", &g_translate1008, &g_reg1008},
        {"Translate1015Exit", &g_translate1015Exit, &g_reg1015}};
    for (const auto &s : sw) {
        int v = GetPrivateProfileIntA("States", s.key, *s.value, g_iniPath) ? 1 : 0;
        if (v == (*s.value ? 1 : 0)) continue;
        Log(1, "0.5.1 switch: [States] %s %d -> %d (read again from TruShadowCombat.ini)%s", s.key, *s.value ? 1 : 0, v,
            *s.reg ? "" : " - state not wrapped (yet): no effect until it is");
        *s.value = v;
    }
}

// TU 0x823d86a8(meter, target, arg) - the retail finisher block (PC twin tru+0x31d40e..+0x31d5dd), meter storage
bool StrikeAt(BYTE *target, int arg) {
    int anim = reinterpret_cast<QueryArgFn>(kQueryArg)(target, 0x165, reinterpret_cast<void *>(arg));
    if (!anim) return false;
    BYTE *player = Player();
    BYTE *chan = *reinterpret_cast<BYTE **>(*reinterpret_cast<BYTE **>(player + 0x280) + 0x14);
    if (!chan) return false;
    reinterpret_cast<AnimSetFn>(kAnimSet)(chan, 0, anim, *reinterpret_cast<void **>(target + 0x10));
    Vec4 dir, point, face, tface, neg;
    const float *tp = reinterpret_cast<const float *>(target + 0x20), *pp = reinterpret_cast<const float *>(player + 0x20);
    for (int i = 0; i < 3; ++i) dir[i] = tp[i] - pp[i];
    dir[3] = kZero;
    Normalize3(dir);
    float dist = static_cast<float>(static_cast<DWORD>(reinterpret_cast<QueryArgFn>(kQueryArg)(target, 0x166, reinterpret_cast<void *>(arg))));
    float frames = static_cast<float>(static_cast<DWORD>(reinterpret_cast<QueryArgFn>(kQueryArg)(target, 0x167, reinterpret_cast<void *>(arg))));
    for (int i = 0; i < 4; ++i) point[i] = tp[i] - dir[i] * dist;
    reinterpret_cast<FaceFn>(kFace)(face, player, dir);
    if (kZero < frames) {
        // TU 0x823d8860..0x823d8880: channel {+0x10 face, +0 point, +0x24 3, +0x20 frames x 100}, meter +0x2c = frames
        reinterpret_cast<ChanMode3Fn>(kChanMode3)(chan, 0, face, point, frames * kHundred);
        g_strike.frames = frames;
    } else {
        Copy4(reinterpret_cast<float *>(player + 0x20), point);
        Vec4 rot;
        reinterpret_cast<ToRotFn>(kToRot)(face, 0, rot);
        Copy4(reinterpret_cast<float *>(player + 0x30), rot);
        g_strike.frames = kZero;
    }
    for (int i = 0; i < 4; ++i) neg[i] = dir[i] * kMinusOne;
    reinterpret_cast<FaceFn>(kFace)(tface, target, neg);
    // TU 0x823d88b4 reloads v126 = target +0x20: the record carries the target's own position (as the PC twin
    // tru+0x31d571), its facing towards the player, the frames and the argument
    Vec4 tpos;
    Copy4(tpos, tp);
    BYTE *record = reinterpret_cast<RecordFn>(kRecord)(target, player, tpos, tface, frames);
    if (record) *reinterpret_cast<int *>(record + 0x34) = arg;          // TU record +0x34 = arg
    if (*reinterpret_cast<void **>(target + 0x120)) reinterpret_cast<MessageFn>(kMessage)(target, 0xbe, record);
    Hit(g_pStrike, 1, "target 0x%08lx, animation %lu, frames %lu", reinterpret_cast<DWORD>(target), static_cast<DWORD>(anim),
        static_cast<DWORD>(frames));
    return true;
}

// TU 0x823d8978 (slot 0)
void StrikeStart(const TruShadowPowerMeter *m) {
    if (*m->flags & 2) return;
    BYTE *t = TargetOf(*reinterpret_cast<BYTE **>(GameTracker() + 0x504), 5);
    if (!t || Excluded(t)) return;
    g_strike.target[0] = reinterpret_cast<DWORD>(t);
    g_strike.target[1] = *reinterpret_cast<const DWORD *>(t + 0x44);
    g_strike.count = 1;
    if (!StrikeAt(t, 1)) return;
    const BYTE *tuning = Tuning();
    if (tuning) {
        m->drain(*reinterpret_cast<const float *>(tuning + 0x34));
        m->request[1][0] = *reinterpret_cast<const float *>(tuning + 0x48);
        m->request[1][1] = *reinterpret_cast<const float *>(tuning + 0x44);
        m->selector();
    }
    *m->startValue = *m->value;
    // TU [0x829ca3d0] = 1 (the "Adren Result" UI call of the exit, retail 0x822a5d28) - compiled out on PC (tru+0x319035)
    *m->flags = (*m->flags & ~0x108u) | 0x12u;
    Log(1, "shadow strike start: target 0x%08lx, meter flags 0x%03lx", g_strike.target[0], *m->flags);
}

// TU 0x823d8d18 (slot 3, every frame)
void StrikeTick(const TruShadowPowerMeter *m) {
    if (!(*m->flags & 2)) return;
    BYTE *gt = GameTracker();
    BYTE *player = *reinterpret_cast<BYTE **>(gt + 0x504);
    DWORD word = 0;
    const DWORD flags = *m->flags;      // TU 0x823d8d28: r10 = flags once, tested again at 0x823d8dfc
    if (*reinterpret_cast<const volatile BYTE *>(0x008ab4e6) && !(*reinterpret_cast<const volatile BYTE *>(0x00e7f144) & 1) &&
        *reinterpret_cast<const volatile BYTE *>(0x00e7f143) != 4 && InputWord(0x1ad0, &word) && (word & 0x10)) {
        const BYTE *model = *reinterpret_cast<BYTE **>(player);
        if (!((*reinterpret_cast<const WORD *>(model + 0x40) >> 7) & 1)) {
            // TU 0x823d8dfc..0x823d8e1c: flag 4 -> 0x823d84d0(1.0) (drain all), then 0x823d9050 (look off)
            if (flags & 4) {
                const BYTE *tu = Tuning();
                if (tu) m->drain(*reinterpret_cast<const float *>(tu + 0x10));
                LookOff(m, "tick (end by input)");
            }
        } else {
            // TU 0x823d8db0: 0x823d9050 (look off; nothing unless flag 4) before the second strike
            LookOff(m, "tick (second strike)");
            BYTE *t = HandleObject(g_strike.target);
            if (!t) return;
            ++g_strike.count;
            if (!StrikeAt(t, g_strike.count)) return;
        }
    }
    const BYTE *model = *reinterpret_cast<BYTE **>(player);
    const bool on = (*m->flags & 2) && ((*reinterpret_cast<const WORD *>(model + 0x40) >> 7) & 1);
    if (on && !g_strike.latch) {
        reinterpret_cast<PlayerEventFn>(kPlayerEvent)(Player(), 0x34, 0xff, 0);
        *reinterpret_cast<volatile BYTE *>(kHudStrikeByte) = 1;
        reinterpret_cast<HudUpdateFn>(kHudUpdate)();
    } else if (!on && g_strike.latch) {
        reinterpret_cast<PlayerEventFn>(kPlayerEvent)(Player(), 0x35, 0xff, 0);
        *reinterpret_cast<volatile BYTE *>(kHudStrikeByte) = 0;
        reinterpret_cast<HudUpdateFn>(kHudUpdate)();
    }
    BYTE *t = HandleObject(g_strike.target);
    if (t && !(*m->flags & 0x100)) {
        // 0x8226f958: same root (+0x214 chain) as the player -> no hit
        const BYTE *a = Player(), *b = t;
        bool same = false;
        if (a != b) {
            while (*reinterpret_cast<const BYTE *const *>(a + 0x214)) a = *reinterpret_cast<const BYTE *const *>(a + 0x214);
            while (*reinterpret_cast<const BYTE *const *>(b + 0x214)) b = *reinterpret_cast<const BYTE *const *>(b + 0x214);
            same = a == b;
        }
        BYTE *pc = *reinterpret_cast<BYTE **>(*reinterpret_cast<BYTE **>(Player() + 0x280) + 0x14);
        if (!same && *reinterpret_cast<const float *>(AnimEntry(pc) + 0x28) > g_strike.frames * kHundred) {
            const SHORT id = *reinterpret_cast<const SHORT *>(*reinterpret_cast<const BYTE *const *>(Player() + 0x50) + 0x214);
            reinterpret_cast<HitFn>(kHit)(t + 0x1d0, 0, Player(), 0, id, 0, 0);
            *m->flags |= 0x100;
            Log(1, "shadow strike hit: target 0x%08lx (tru+0x1b4de0, id %d)", reinterpret_cast<DWORD>(t), id);
        }
    }
    g_strike.latch = on ? 1 : 0;
}

// TU 0x823d9210 (slot 2)
void StrikeEnd(const TruShadowPowerMeter *m) {
    if (!(*m->flags & 2)) return;
    BYTE *t = HandleObject(g_strike.target);
    BYTE *gt = GameTracker();
    if (t && *reinterpret_cast<const int *>(*reinterpret_cast<const BYTE *const *>(gt + 0xf10) + 0x24) < 1 &&
        *reinterpret_cast<void **>(t + 0x120))
        reinterpret_cast<MessageFn>(kMessage)(t, 0x3f, nullptr);
    g_strike.target[0] = g_strike.target[1] = 0;
    // TU 0x823d92ac..0x823d92d0: flag 4 -> 0x823d9050 (look off) first, then 0x823d84d0(1.0) (drain all)
    if (*m->flags & 4) {
        LookOff(m, "end");
        const BYTE *tu = Tuning();
        if (tu) m->drain(*reinterpret_cast<const float *>(tu + 0x10));
    }
    if (Tuning()) {
        m->request[1][0] = m->request[1][1] = kMinusOne;
        m->selector();
    }
    *m->flags &= ~0x12u;
    *m->startValue = kMeterStart;
    Log(1, "shadow strike end: message 0x3f %s, meter flags 0x%03lx", t ? "sent" : "not sent", *m->flags);
}

void Q108Run1014(int k, void *agent, StateFn orig);   // 0.6.13 (section "group C" below)
void State1014(int k, void *agent) {
    ReadSwitches();
    if (Doppelganger()) {
        const TruShadowPowerMeter *m = (g_strikeTranslate && g_strikeOk) ? Meter() : nullptr;
        if (m) {
            Hit(g_p1014[k], 1, "doppelganger mode: TU strike translation");
            __try {
                if (k == 0) StrikeStart(m);
                else if (k == 1) StrikeEnd(m);
                else StrikeTick(m);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                Log(0, "state 1014 slot %d: access fault in the strike - skipped", k == 0 ? 0 : k == 1 ? 2 : 3);
            }
            return;
        }
        if (g_strikeGate) {
            Hit(g_p1014[k], 0, g_strikeTranslate ? "doppelganger mode: no meter interface / blocks - strike not run"
                                                 : "doppelganger mode: [Strike] Translate=0 - strike not run");
            return;
        }
    }
    Q108Run1014(k, agent, g_orig1014[k]);   // 0.6.13: the PC handler, with the Q108 log lines around slots 0 / 3
}
void __cdecl State1014Slot0(void *agent) { State1014(0, agent); }
void __cdecl State1014Slot2(void *agent) { State1014(1, agent); }
void __cdecl State1014Slot3(void *agent) { State1014(2, agent); }

// ---------------------------------------------------------------- 0.6.11: state 1008 (finisher Y move) as the TU
// Q19 (main workspace docs\Befund-Sturz-durch-Welt-1111.md, docs\Befund-Translate1008-1111.md): chart record 743 [1008]
// under 742 [1004 1015] = the finisher Y on a downed thrall. PC = retail: table entry 1008 at tru.exe 0x8b19bc (machine-1
// state table 0x8b0a50 = push operand at tru+0x368b99, + 141 x 28 bytes) = {1008, 0, 0, 0, 0, tru+0x36d9a0, 0};
// tru+0x36d9a0 (= retail 0x8245bb30, slot 4) takes targeter 6 (tru+0x31caf0) and writes only gameTracker+0x1270 (facing,
// tru+0x36a750) and +0x1260 (target +0x20, player +0x20 for [t+0x14] & 0x400000). It does not move Lara: the leap is the
// animation's root motion (PC live 2026-11-10: 340..660 units, up to 345 past the target, out of the world at an edge).
// TU table 0x82758940: 1008 = {0x8245f7b0, 0, 0x82455a38, 0x8245fa40, 0, 0} - slot 4 removed, slot 2 = 0x82455a38 (blr).
//   slot 0 (enter) 0x8245f7b0: h = 0x823dd138(player, 7) (= PC tru+0x31c9a0, TU 7 = PC slot 6); h != 0 -> agent +0x4f4 /
//     +0x4f8 = h[0] / h[1] (the only writer of +0x4f4 in the state code, tools/ppc_field_writes.py; kept here as
//     g_h1008), t = h[0] when [h[0]+0x44] == h[1], else 0; then the empty print 0x82455a38 (its arguments
//     [[t+0x10]+0x60] / [t+0x58] read address 0x10 when t = 0 - not made); h == 0 -> t = 0, +0x4f4 unchanged.
//   slot 3 (tick) 0x8245fa40: t = the kept handle's object when its +0x44 still equals the id, else 0.
//   both then: Busy244(gameTracker) -> channel mode 2 {instance +0x20, (0, 0, 0, 1), animation entry +0x28 - 1.0f}
//     (= tru+0x38d00); else t == 0 -> nothing; else face = 0x82457b28(t, 1) (FaceTarget), point = t +0x20 (player +0x20
//     when [t+0x14] & 0x400000), n = 0x82463af8(&n, agent, 0) (= tru+0x35f3e0); n > 0 -> channel mode 3 {face, point,
//     (float) n x 100.0f [0x8207d53c]} (= tru+0x38dc0), else mode 3 with the animation's frame count (s16
//     [[chan+0x80]+0x24]+0x34 x +0x32, = tru+0x3e480). Every tick re-aims the channel at the target's current position.
// Neither function tests the doppelganger flag: every level, as the TU. [States] Translate1008 (default 0, read again at
// run time): 0 = PC slot 4 runs, slots 0 / 3 only log what the TU would do ("off (would)"); 1 = slots 0 / 3 act and the
// PC slot 4 is not run (the TU has none). Slot 2 is the TU's empty function plus the end line (both settings).
// Not part of it: 1015 slot 2 (TU-new 0x8245fe58: death switch on the 1015 target CM+0x48 at the attack's end) - other
// data (CM+0x48 / +0x4c, not agent +0x4f4), other object (the target, not Lara's channel); docs Befund-Translate1008.
// It is ported separately in 0.6.12 ([States] Translate1015Exit, section "0.6.12: state 1015 exit").
int g_probe1008 = 1;                             // [Probe] State1008: wrap record 1008 at all
bool g_s1008Ok = false;                          // building blocks below verified
const DWORD kState1008Entry = 0x008b19bc, kState1008PcSlot4 = 0x0076d9a0;
StateFn g_orig1008Slot4 = nullptr;

// 0.6.12: state 1015 exit (TU 0x8245fe58) - the section "0.6.12: state 1015 exit" below; registered in ExtendStates
// (g_translate1015Exit / g_reg1015 are defined with g_translate1008 above ReadSwitches). No [Probe] key: with
// Translate1015Exit=0 the wrapper only adds a log line before the PC slot 2 (TruMenu's switch list is at 159 of 160 rows)
bool g_s1015Ok = false;
const DWORD kState1015Pc = 0x0075e0e0, kState1015PcSlot2 = 0x0075e0f0;
StateFn g_orig1015Slot2 = nullptr;
void __cdecl State1015Slot2(void *agent);

bool CheckState1008Blocks() {
    struct { DWORD at; const char *hex; const char *what; } const s[] = {
        {kState1008Entry, "f0030000 00000000 00000000 00000000 00000000 a0d97600 00000000",
         "PC table entry 1008 {1008, 0, 0, 0, 0, tru+0x36d9a0, 0} (tru.exe 0x8b19bc)"},
        {0x00768b99, "68 500a8b00", "machine-1 state table push 0x8b0a50 (tru+0x368b99; another plugin may have moved it)"},
        {kState1008PcSlot4, "55 8bec 83e4f0 a158dbfa00 8b8804050000 83ec1c 56 6a06 e834f1faff 8bf0 8d4c2410 56 51 e887cdffff",
         "PC 1008 slot 4 tru+0x36d9a0 (targeter 6, facing tru+0x36a750)"},
        {0x0076d9d7, "0f298270120000", "PC 1008 slot 4: gameTracker+0x1270 store"},
        {0x0076d9e0, "f7461400004000 7505 8d4620 eb08 a194f0e700 83c020", "PC 1008 slot 4: point = t+0x20 / player+0x20"},
        {0x0076d9fe, "81c160120000", "PC 1008 slot 4: gameTracker+0x1260 store"},
        {kTargetOf, kTargetOfHex, "tru+0x31caf0 calls tru+0x31c9a0 (handle) then the object check"},
    };
    for (const auto &c : s) {
        if (c.at == 0x00768b99 && !HexAt(c.at, c.hex)) {   // only informative: the copy is checked at registration
            Log(1, "state 1008: %s at 0x%08lx differs - the record is checked again in the registered table", c.what, c.at);
            continue;
        }
        if (!HexAt(c.at, c.hex)) { Log(0, "state 1008: %s at 0x%08lx does not match - not wrapped", c.what, c.at); return false; }
    }
    return true;
}

// TU agent +0x4f4 / +0x4f8 (handle {object, id} of 1008's target); a new target list ([0xfadfac] changed, PC player
// init tru+0x322631) counts as a new agent - as g_m1019
DWORD g_h1008[2] = {0, 0};
BYTE **g_h1008List = nullptr;
DWORD *Handle1008() {
    if (g_h1008List != List()) { g_h1008[0] = g_h1008[1] = 0; g_h1008List = List(); }
    return g_h1008;
}

// one run of the state (enter .. exit) for the log
struct Run1008 { DWORD enterTick, lastLine; LONG ticks, lines; int path; float enter[4], point[4]; } g_run1008;
Trace g_t1008e = {"state 1008 slot 0 (TU 0x8245f7b0: finisher Y - target TU 7, steer onto it)"};
Trace g_t1008x = {"state 1008 slot 2 (TU 0x82455a38 empty: end)"};
Trace g_t1008s4 = {"state 1008 slot 4 (PC tru+0x36d9a0, not in the TU table)"};

const float *Pos(const BYTE *o) { return reinterpret_cast<const float *>(o + 0x20); }
float Dist3(const float *a, const float *b) {
    const float d[3] = {a[0] - b[0], a[1] - b[1], a[2] - b[2]};
    return sqrtf(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
}
float DistXY(const float *a, const float *b) {
    const float d[2] = {a[0] - b[0], a[1] - b[1]};
    return sqrtf(d[0] * d[0] + d[1] * d[1]);
}

// common body of TU 0x8245f7b0 (from 0x8245f84c) / 0x8245fa40 (from 0x8245faa0). Returns the path: 1 Busy244 -> mode 2
// stop at the instance, 2 no target -> nothing, 3 mode 3 frames n x 100, 4 mode 3 animation frames. apply = 0 only
// computes (the channel is not written).
int Move1008(void *agent, BYTE *t, bool apply, float *point, int *frames) {
    BYTE *chan = Channel(static_cast<BYTE *>(agent));
    const BYTE *inst = *reinterpret_cast<const BYTE *const *>(static_cast<BYTE *>(agent) + 8);
    *frames = 0;
    if (Busy244(GameTracker())) {
        const float f = *reinterpret_cast<const float *>(AnimEntry(chan) + 0x28) - kOne;
        Copy4(point, Pos(inst));
        if (apply) reinterpret_cast<ChanMode2Fn>(kChanMode2)(chan, 0, Pos(inst), f);
        return 1;
    }
    if (!t) return 2;
    Vec4 face;
    FaceTarget(face, t, 1);
    Copy4(point, Pos(Excluded(t) ? Player() : t));
    int n = 0;
    reinterpret_cast<AnimFramesFn>(kAnimFrames)(&n, agent);
    *frames = n;
    if (n > 0) {
        if (apply) reinterpret_cast<ChanMode3Fn>(kChanMode3)(chan, 0, face, point, static_cast<float>(n) * kHundred);
        return 3;
    }
    if (apply) reinterpret_cast<ChanVec2Fn>(kChanMode3Anim)(chan, 0, face, point);
    return 4;
}

const char kPath1008[] = "1 Busy244: mode 2 stop, 2 no target: nothing, 3 mode 3 n x 100 frames, 4 mode 3 animation frames";

void __cdecl State1008Slot0(void *agent) {
    ReadSwitches();
    const bool apply = g_translate1008 != 0;
    __try {
        BYTE *player = *reinterpret_cast<BYTE **>(GameTracker() + 0x504);
        DWORD *h = reinterpret_cast<TargetInnerFn>(kTargetOfInner)(player, 0, SlotOf(7));
        DWORD *kept = Handle1008();
        BYTE *t = nullptr;
        if (h) {
            kept[0] = h[0];
            kept[1] = h[1];
            t = HandleObject(h);
        }
        const BYTE *inst = *reinterpret_cast<const BYTE *const *>(static_cast<BYTE *>(agent) + 8);
        Vec4 point;
        int frames = 0;
        const int path = Move1008(agent, t, apply, point, &frames);
        g_run1008.enterTick = g_run1008.lastLine = GetTickCount();
        g_run1008.ticks = g_run1008.lines = 0;
        g_run1008.path = path;
        Copy4(g_run1008.enter, Pos(inst));
        Copy4(g_run1008.point, point);
        TraceLog(g_t1008e, true, path, "%s handle %s, target 0x%08lx%s; Lara %.1f %.1f %.1f, distance %.1f -> path %d (%s), "
                 "steering point %.1f %.1f %.1f, frames %d", apply ? "ON:" : "off (would):",
                 h ? "taken" : "none (kept handle unchanged)", reinterpret_cast<DWORD>(t),
                 t && Excluded(t) ? " (excluded: point = player)" : "", Pos(inst)[0], Pos(inst)[1], Pos(inst)[2],
                 t ? Dist3(Pos(inst), Pos(t)) : -1.0f, path, kPath1008, point[0], point[1], point[2], frames);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1008 slot 0: access fault - skipped");
    }
}

void __cdecl State1008Slot3(void *agent) {
    ReadSwitches();
    const bool apply = g_translate1008 != 0;
    __try {
        BYTE *t = HandleObject(Handle1008());
        const BYTE *inst = *reinterpret_cast<const BYTE *const *>(static_cast<BYTE *>(agent) + 8);
        Vec4 point;
        int frames = 0;
        const int path = Move1008(agent, t, apply, point, &frames);
        const LONG k = ++g_run1008.ticks;
        const bool changed = path != g_run1008.path;
        g_run1008.path = path;
        Copy4(g_run1008.point, point);
        // steering line: on a path change, else every 250 ms; at most 8 per run (level 1), the rest at level 3
        const DWORD now = GetTickCount();
        if (changed || now - g_run1008.lastLine >= 250) {
            g_run1008.lastLine = now;
            Log(++g_run1008.lines <= 8 ? 1 : 3, "state 1008 slot 3 (TU 0x8245fa40: steer onto the target) %s tick %ld "
                "(%lu ms): target 0x%08lx, path %d%s, steering point %.1f %.1f %.1f, frames %d; Lara %.1f %.1f %.1f, "
                "distance %.1f", apply ? "ON" : "off (would)", k, now - g_run1008.enterTick, reinterpret_cast<DWORD>(t),
                path, changed ? " (changed)" : "", point[0], point[1], point[2], frames, Pos(inst)[0], Pos(inst)[1],
                Pos(inst)[2], t ? Dist3(Pos(inst), Pos(t)) : -1.0f);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1008 slot 3: access fault - skipped");
    }
}

// TU slot 2 = 0x82455a38 (blr): nothing happens there; the line is the plugin's
void __cdecl State1008Slot2(void *agent) {
    __try {
        BYTE *t = HandleObject(Handle1008());
        const BYTE *inst = *reinterpret_cast<const BYTE *const *>(static_cast<BYTE *>(agent) + 8);
        const float *l = Pos(inst);
        char where[160] = "no valid target";
        if (t)
            _snprintf_s(where, sizeof(where), _TRUNCATE, "target 0x%08lx at %.1f %.1f %.1f: END DISTANCE %.1f (horizontal "
                        "%.1f)", reinterpret_cast<DWORD>(t), Pos(t)[0], Pos(t)[1], Pos(t)[2], Dist3(l, Pos(t)),
                        DistXY(l, Pos(t)));
        TraceLog(g_t1008x, true, t ? 1 : 0, "%s, %ld ticks, %lu ms; Lara %.1f %.1f %.1f, %.1f units from the enter point "
                 "(horizontal %.1f); %s; last path %d, steering point %.1f %.1f %.1f",
                 g_translate1008 ? "Translate1008 1" : "Translate1008 0 (PC root motion)", g_run1008.ticks,
                 GetTickCount() - g_run1008.enterTick, l[0], l[1], l[2], Dist3(l, g_run1008.enter),
                 DistXY(l, g_run1008.enter), where, g_run1008.path, g_run1008.point[0], g_run1008.point[1],
                 g_run1008.point[2]);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1008 slot 2: access fault in the end line");
    }
}

void __cdecl State1008Slot4(void *agent) {
    ReadSwitches();
    if (!g_translate1008) {
        if (g_orig1008Slot4) g_orig1008Slot4(agent);
        return;
    }
    TraceLog(g_t1008s4, false, 1, "ON: not run (the TU table has no slot 4 for 1008; gameTracker+0x1260 / +0x1270 "
             "not written)");
}

// ---------------------------------------------------------------- Lara's tables at registration time
// TU 0x82473b50 = PC tru+0x368b60 (virtual, the only reference is the vtable slot 0x85e1d4) registers the tables of
// the two machines (gameTracker+0xf10 / +0xf14) through `push table` operands. TruShadowPower (machine 1) points
// them at its copies when it loads - after this plugin (alphabetical) and with byte checks over that code, so the
// tables are extended here only when the registration runs: the current operand (original or another plugin's copy)
// is copied with this plugin's records.
const DWORD kRegSlot = 0x0085e1d4, kRegFn = 0x00768b60;
const char *const kRegFnHex = "a158dbfa00 56 c70574dafa0048000000 8bb0100f0000 8bce e8c3a80100 85c0 7524";
const DWORD kM1CondPush = 0x00768b81, kM1StatePush = 0x00768b99, kM2CondPush = 0x00768bd6;
const char *const kM1CondTailHex = "8bce e893c50100";     // after the push imm32: mov ecx, esi; call 0x785120
const char *const kM1StateTailHex = "8bce e85bca0100";    // call 0x785600
const char *const kM2CondTailHex = "8bce e83ec50100";     // call 0x785120
const DWORD kGenericCondPush = 0x00787343, kGenericCondTable = 0x008b57e0;
const DWORD kGenericStatePush = 0x0078736a;
typedef void(__fastcall *RegFn)(void *self, void *edx, DWORD a, DWORD b);
RegFn g_origReg = nullptr;
bool g_regPatched = false;

DWORD g_m1Cond[(400 + 8) * 3], g_m2Cond[(400 + 8) * 3], g_m1State[(260 + 4) * 7];

int Count(const DWORD *t, int stride, int limit) {
    for (int i = 0; i < limit; ++i)
        if (t[i * stride] == 0) return i;
    return -1;
}
int Find(const DWORD *t, int stride, int count, DWORD id) {
    for (int i = 0; i < count; ++i)
        if (t[i * stride] == id) return i;
    return -1;
}

bool GenericHas(DWORD pushOperand, DWORD original, int stride, DWORD id) {
    DWORD table = *reinterpret_cast<const DWORD *>(pushOperand);
    if (table == original) return false;
    const DWORD *t = reinterpret_cast<const DWORD *>(table);
    int n = Count(t, stride, 3000);
    return n > 0 && Find(t, stride, n, id) >= 0;
}

struct CondAdd { DWORD id; const void *fn; DWORD expectOld; };

// copy of the condition table at the operand with: replaced handlers (only when they are still the PC ones) and
// added ids (only when absent here and present in the generic registry - else the registration loop crashes)
bool ExtendConds(DWORD pushAt, DWORD *copy, int capacity, const CondAdd *adds, int addCount, int machine) {
    DWORD *operand = reinterpret_cast<DWORD *>(pushAt + 1);
    if (*operand == reinterpret_cast<DWORD>(copy)) return true;           // already ours (next level)
    const DWORD *t = reinterpret_cast<const DWORD *>(*operand);
    int n = Count(t, 3, capacity - addCount - 1);
    if (n <= 0) { Log(0, "machine %d conditions: table 0x%08lx unreadable / too long - not extended", machine, *operand); return false; }
    memcpy(copy, t, (n + 1) * 3 * sizeof(DWORD));
    int added = 0, replaced = 0;
    char done[300] = "";
    for (int k = 0; k < addCount; ++k) {
        const CondAdd &a = adds[k];
        int i = Find(copy, 3, n, a.id);
        char item[40];
        if (a.expectOld) {
            if (i < 0) { Log(0, "machine %d: condition %lu not in the table - not replaced", machine, a.id); continue; }
            if (copy[i * 3 + 2] != a.expectOld) {
                Log(0, "machine %d: condition %lu handler is 0x%08lx, expected the PC 0x%08lx (another plugin?) - not "
                       "replaced", machine, a.id, copy[i * 3 + 2], a.expectOld);
                continue;
            }
            copy[i * 3 + 2] = reinterpret_cast<DWORD>(a.fn);
            ++replaced;
            _snprintf_s(item, sizeof(item), _TRUNCATE, " %lu (replaced)", a.id);
        } else {
            if (i >= 0) { Log(0, "machine %d: condition %lu already registered (0x%08lx) - not added", machine, a.id, copy[i * 3 + 2]); continue; }
            if (!GenericHas(kGenericCondPush, kGenericCondTable, 3, a.id)) {
                Log(0, "machine %d: condition %lu is not in the generic registry (TruDoppelganger.asi not active?) - not "
                       "added (the registration would crash)", machine, a.id);
                continue;
            }
            memmove(copy + (n + 1) * 3, copy + n * 3, 3 * sizeof(DWORD));   // closing record one further
            copy[n * 3] = a.id;
            copy[n * 3 + 1] = 2000;                                           // group 2000 as in the TU tables
            copy[n * 3 + 2] = reinterpret_cast<DWORD>(a.fn);
            ++n;
            ++added;
            _snprintf_s(item, sizeof(item), _TRUNCATE, " %lu (added)", a.id);
        }
        strncat_s(done, sizeof(done), item, _TRUNCATE);
    }
    DWORD value = reinterpret_cast<DWORD>(copy);
    if (!WriteCode(reinterpret_cast<DWORD>(operand), &value, 4)) return false;
    Log(1, "machine %d conditions:%s - table copy 0x%08lx (%d records, from 0x%08lx)", machine, done[0] ? done : " none",
        reinterpret_cast<DWORD>(copy), n, reinterpret_cast<DWORD>(t));
    return added + replaced > 0;
}

bool ExtendStates() {
    DWORD *operand = reinterpret_cast<DWORD *>(kM1StatePush + 1);
    if (*operand == reinterpret_cast<DWORD>(g_m1State)) return true;
    const DWORD *t = reinterpret_cast<const DWORD *>(*operand);
    int n = Count(t, 7, 260);
    if (n <= 0) { Log(0, "machine 1 states: table 0x%08lx unreadable / too long - state 1014 not gated", *operand); return false; }
    memcpy(g_m1State, t, (n + 1) * 7 * sizeof(DWORD));
    char done[400] = "";
    // 1014 (strike gate / translation)
    if (g_strikeGate || g_strikeTranslate) {
        int i = Find(g_m1State, 7, n, 1014);
        DWORD *rec = i >= 0 ? g_m1State + i * 7 : nullptr;
        const int slots[3] = {0, 2, 3};
        const void *wrap[3] = {&State1014Slot0, &State1014Slot2, &State1014Slot3};
        bool ok = rec != nullptr;
        for (int k = 0; ok && k < 3; ++k)
            if (rec[1 + slots[k]] != kState1014Pc[k]) {
                Log(0, "machine 1 state 1014 slot %d is 0x%08lx, expected the PC 0x%08lx - not wrapped", slots[k],
                    rec[1 + slots[k]], kState1014Pc[k]);
                ok = false;
            }
        if (ok) {
            for (int k = 0; k < 3; ++k) {
                g_orig1014[k] = reinterpret_cast<StateFn>(rec[1 + slots[k]]);
                rec[1 + slots[k]] = reinterpret_cast<DWORD>(wrap[k]);
            }
            strncat_s(done, sizeof(done), g_strikeTranslate ? " 1014 (slots 0 / 2 / 3 wrapped: strike translation)"
                                                            : " 1014 (slots 0 / 2 / 3 gated)", _TRUNCATE);
        }
    }
    if (g_probe1013 && g_blocksOk) {
        int i = Find(g_m1State, 7, n, 1013);
        if (i >= 0 && g_m1State[i * 7 + 1] == kState1013Pc && HexAt(kState1013Pc, kState1013PcHex)) {
            g_orig1013 = reinterpret_cast<StateFn>(g_m1State[i * 7 + 1]);
            g_m1State[i * 7 + 1] = reinterpret_cast<DWORD>(&State1013Slot0);
            strncat_s(done, sizeof(done), " 1013 (slot 0 probe)", _TRUNCATE);
        } else {
            Log(0, "machine 1 state 1013 slot 0 is not the PC 0x%08lx - no probe", kState1013Pc);
        }
    }
    if (g_statesOn && g_statesOk && g_listOk) {
        // 1007: slot 4 = PC tru+0x36d930 kept for the main game, slot 5 (TU-only) added - both doppelganger-only TU code
        int i = Find(g_m1State, 7, n, 1007);
        if (i >= 0 && g_m1State[i * 7 + 5] == 0x0076d930 && g_m1State[i * 7 + 6] == 0) {
            g_orig1007Slot4 = reinterpret_cast<StateFn>(g_m1State[i * 7 + 5]);
            g_m1State[i * 7 + 5] = reinterpret_cast<DWORD>(&State1007Slot4);
            g_m1State[i * 7 + 6] = reinterpret_cast<DWORD>(&State1007Slot5);
            strncat_s(done, sizeof(done), " 1007 (slots 4 / 5)", _TRUNCATE);
        } else {
            Log(0, "machine 1 state 1007 is not {.., 0x0076d930, 0} - not wrapped");
        }
        // 1017 {0, 0, 0, 0, f, 0} and 244 {f, 0, 0, g, 0, 0} as in the TU table 0x82757948
        struct { DWORD id; DWORD fn[6]; } const adds[2] = {
            {1017, {0, 0, 0, 0, reinterpret_cast<DWORD>(&State1017Slot4), 0}},
            {244, {reinterpret_cast<DWORD>(&State244Slot0), 0, 0, reinterpret_cast<DWORD>(&State244Slot3), 0, 0}}};
        for (const auto &a : adds) {
            if (Find(g_m1State, 7, n, a.id) >= 0) { Log(0, "machine 1 state %lu already registered - not added", a.id); continue; }
            if (!GenericHas(kGenericStatePush, 0x008b4200, 7, a.id)) {
                Log(0, "machine 1 state %lu is not in the generic registry (TruDoppelganger.asi?) - not added", a.id);
                continue;
            }
            memmove(g_m1State + (n + 1) * 7, g_m1State + n * 7, 7 * sizeof(DWORD));
            g_m1State[n * 7] = a.id;
            for (int k = 0; k < 6; ++k) g_m1State[n * 7 + 1 + k] = a.fn[k] ? a.fn[k] : 0;
            ++n;
            char item[24];
            _snprintf_s(item, sizeof(item), _TRUNCATE, " %lu (added)", a.id);
            strncat_s(done, sizeof(done), item, _TRUNCATE);
        }
    }
    if (g_statesOn && g_statesOk && g_listOk && g_s1019Ok && g_probe1019) {
        // 0.5: 1019 {e, e, 0, t, 0, 0} and 1020 {e, e, 0, 0, 0, 0} as in the TU table 0x82757948 (records 143 / 153)
        struct { DWORD id; DWORD fn[6]; bool *reg; } const adds[2] = {
            {1019, {reinterpret_cast<DWORD>(&State1019Slot0), reinterpret_cast<DWORD>(&State1019Slot1), 0,
                    reinterpret_cast<DWORD>(&State1019Slot3), 0, 0}, &g_reg1019},
            {1020, {reinterpret_cast<DWORD>(&State1020Slot0), reinterpret_cast<DWORD>(&State1020Slot1), 0, 0, 0, 0}, &g_reg1020}};
        for (const auto &a : adds) {
            if (Find(g_m1State, 7, n, a.id) >= 0) {
                Log(0, "machine 1 state %lu already registered (0x%08lx, another plugin?) - not added", a.id,
                    g_m1State[Find(g_m1State, 7, n, a.id) * 7 + 1]);
                continue;
            }
            if (!GenericHas(kGenericStatePush, 0x008b4200, 7, a.id)) {
                Log(0, "machine 1 state %lu is not in the generic registry (TruDoppelganger.asi?) - not added", a.id);
                continue;
            }
            if (n + 2 > 260) { Log(0, "machine 1 state table copy full - state %lu not added", a.id); continue; }
            memmove(g_m1State + (n + 1) * 7, g_m1State + n * 7, 7 * sizeof(DWORD));
            g_m1State[n * 7] = a.id;
            for (int k = 0; k < 6; ++k) g_m1State[n * 7 + 1 + k] = a.fn[k];
            ++n;
            *a.reg = true;
            char item[48];
            _snprintf_s(item, sizeof(item), _TRUNCATE, " %lu (added, %s)", a.id,
                        (a.id == 1019 ? g_translate1019 : g_translate1020) ? "ON" : "log only");
            strncat_s(done, sizeof(done), item, _TRUNCATE);
        }
    } else if (g_statesOn && g_probe1019) {
        Log(0, "machine 1 states 1019 / 1020: not added (building blocks %d, target list %d, states blocks %d)",
            g_s1019Ok ? 1 : 0, g_listOk ? 1 : 0, g_statesOk ? 1 : 0);
    }
    if (g_statesOn && g_statesOk && g_s1019Ok && g_s231Ok && g_probe231) {
        // 0.5.1: 231 {PC 0 -> wrapper, 0 -> TU slot 1}, 1004 {PC 0 -> wrapper, 0 -> TU slot 1, PC slot 2 kept}
        int i = Find(g_m1State, 7, n, 231);
        const DWORD *r = i >= 0 ? g_m1State + i * 7 : nullptr;
        if (r && r[1] == kState231Pc && r[2] == 0) {
            g_orig231 = reinterpret_cast<StateFn>(r[1]);
            g_m1State[i * 7 + 1] = reinterpret_cast<DWORD>(&State231Slot0);
            g_m1State[i * 7 + 2] = reinterpret_cast<DWORD>(&State231Slot1);
            g_reg231 = true;
            strncat_s(done, sizeof(done), g_translate231s0 || g_translate231s1 ? " 231 (slots 0 / 1, ON)"
                                                                                : " 231 (slots 0 / 1, log only)", _TRUNCATE);
        } else {
            Log(0, "machine 1 state 231 is not {0x%08lx, 0, ..} (%s) - not wrapped", kState231Pc,
                r ? "other handlers - another plugin?" : "missing");
        }
        i = Find(g_m1State, 7, n, 1004);
        r = i >= 0 ? g_m1State + i * 7 : nullptr;
        if (r && r[1] == kState1004Pc && r[2] == 0 && r[3] == kState1004PcSlot2) {
            g_orig1004 = reinterpret_cast<StateFn>(r[1]);
            g_m1State[i * 7 + 1] = reinterpret_cast<DWORD>(&State1004Slot0);
            g_m1State[i * 7 + 2] = reinterpret_cast<DWORD>(&State1004Slot1);
            g_reg1004 = true;
            strncat_s(done, sizeof(done), g_translate1004 ? " 1004 (slots 0 / 1, ON)" : " 1004 (slots 0 / 1, log only)", _TRUNCATE);
        } else {
            Log(0, "machine 1 state 1004 is not {0x%08lx, 0, 0x%08lx, ..} (%s) - not wrapped", kState1004Pc,
                kState1004PcSlot2, r ? "other handlers - another plugin?" : "missing");
        }
    } else if (g_statesOn && g_probe231) {
        Log(0, "machine 1 states 231 / 1004: not wrapped (building blocks 231 / 1004 %d, 1019 %d, states %d)",
            g_s231Ok ? 1 : 0, g_s1019Ok ? 1 : 0, g_statesOk ? 1 : 0);
    }
    if (g_statesOn && g_s1008Ok && g_probe1008) {
        // 0.6.11: 1008 {0, 0, 0, 0, PC slot 4, 0} -> {TU slot 0, 0, slot 2 (TU: empty), TU slot 3, wrapper of slot 4, 0}
        int i = Find(g_m1State, 7, n, 1008);
        const DWORD *r = i >= 0 ? g_m1State + i * 7 : nullptr;
        if (r && r[1] == 0 && r[2] == 0 && r[3] == 0 && r[4] == 0 && r[5] == kState1008PcSlot4 && r[6] == 0) {
            g_orig1008Slot4 = reinterpret_cast<StateFn>(r[5]);
            g_m1State[i * 7 + 1] = reinterpret_cast<DWORD>(&State1008Slot0);
            g_m1State[i * 7 + 3] = reinterpret_cast<DWORD>(&State1008Slot2);
            g_m1State[i * 7 + 4] = reinterpret_cast<DWORD>(&State1008Slot3);
            g_m1State[i * 7 + 5] = reinterpret_cast<DWORD>(&State1008Slot4);
            g_reg1008 = true;
            strncat_s(done, sizeof(done), g_translate1008 ? " 1008 (slots 0 / 2 / 3 / 4, ON)" : " 1008 (slots 0 / 2 / 3 / 4, log only)",
                      _TRUNCATE);
        } else {
            Log(0, "machine 1 state 1008 is not {0, 0, 0, 0, 0x%08lx, 0} (%s) - not wrapped", kState1008PcSlot4,
                r ? "other handlers - another plugin?" : "missing");
        }
    } else if (g_statesOn && g_probe1008) {
        Log(0, "machine 1 state 1008: not wrapped (building blocks 1008 %d, 1019 %d, states %d)", g_s1008Ok ? 1 : 0,
            g_s1019Ok ? 1 : 0, g_statesOk ? 1 : 0);
    }
    if (g_statesOn && g_s1015Ok) {
        // 0.6.12: 1015 {PC slot 0, 0, PC slot 2, 0, 0, 0} -> slot 2 = wrapper (TU 0x8245fe58 = kill, then the PC clear);
        // slot 0 stays the PC's (TU 0x8245fde8 = retail with targeter TU 7 = PC slot 6)
        int i = Find(g_m1State, 7, n, 1015);
        const DWORD *r = i >= 0 ? g_m1State + i * 7 : nullptr;
        if (r && r[1] == kState1015Pc && r[2] == 0 && r[3] == kState1015PcSlot2 && r[4] == 0 && r[5] == 0 && r[6] == 0) {
            g_orig1015Slot2 = reinterpret_cast<StateFn>(r[3]);
            g_m1State[i * 7 + 3] = reinterpret_cast<DWORD>(&State1015Slot2);
            g_reg1015 = true;
            strncat_s(done, sizeof(done), g_translate1015Exit ? " 1015 (slot 2, ON)" : " 1015 (slot 2, log only)", _TRUNCATE);
        } else {
            Log(0, "machine 1 state 1015 is not {0x%08lx, 0, 0x%08lx, 0, 0, 0} (%s) - not wrapped", kState1015Pc,
                kState1015PcSlot2, r ? "other handlers - another plugin?" : "missing");
        }
    } else if (g_statesOn) {
        Log(0, "machine 1 state 1015: not wrapped (building blocks 1015 exit %d)", g_s1015Ok ? 1 : 0);
    }
    if (!done[0]) return false;
    DWORD value = reinterpret_cast<DWORD>(g_m1State);
    if (!WriteCode(reinterpret_cast<DWORD>(operand), &value, 4)) return false;
    Log(1, "machine 1 states:%s - table copy 0x%08lx (%d records, from 0x%08lx)", done, value, n, reinterpret_cast<DWORD>(t));
    return true;
}

volatile LONG g_regCalls = 0;
void __fastcall RegHook(void *self, void *edx, DWORD a, DWORD b) {
    LONG call = InterlockedIncrement(&g_regCalls);
    __try {
        if (g_conditions && g_blocksOk) {
            const CondAdd m1[] = {{2005, &Cond2005, 0}, {2013, &Cond2013, 0}, {2006, &Cond2006, 0},
                                  {2011, &Cond2011, kCond2011Pc}, {538, &Cond538, kCond538Pc}};
            const CondAdd m2[] = {{2005, &Cond2005, 0}, {2013, &Cond2013, 0},
                                  {2011, &Cond2011, kCond2011Pc}, {538, &Cond538, kCond538Pc}};
            ExtendConds(kM1CondPush, g_m1Cond, sizeof(g_m1Cond) / 12, m1, 5, 1);
            ExtendConds(kM2CondPush, g_m2Cond, sizeof(g_m2Cond) / 12, m2, 4, 2);
        }
        if (g_strikeGate || g_strikeTranslate || g_statesOn) ExtendStates();
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "Lara registration hook: access fault while extending the tables - original tables kept where not yet written");
    }
    if (call == 1) Log(1, "Lara state-machine registration (tru+0x368b60) reached - tables checked / extended");
    g_origReg(self, edx, a, b);
}

bool SetupRegistration() {
    if (!g_conditions && !g_strikeGate && !g_strikeTranslate && !g_statesOn) {
        Log(1, "conditions, states and strike off - Lara's tables untouched");
        return false;
    }
    if (*reinterpret_cast<const DWORD *>(kRegSlot) != kRegFn || !HexAt(kRegFn, kRegFnHex) ||
        *reinterpret_cast<const BYTE *>(kM1CondPush) != 0x68 || !HexAt(kM1CondPush + 5, kM1CondTailHex) ||
        *reinterpret_cast<const BYTE *>(kM1StatePush) != 0x68 || !HexAt(kM1StatePush + 5, kM1StateTailHex) ||
        *reinterpret_cast<const BYTE *>(kM2CondPush) != 0x68 || !HexAt(kM2CondPush + 5, kM2CondTailHex)) {
        Log(0, "Lara registration tru+0x368b60 / vtable slot 0x%08lx / push operands do not match - tables untouched", kRegSlot);
        return false;
    }
    for (int k = 0; k < 3; ++k)
        if (!HexAt(kState1014Pc[k], kState1014PcHex[k])) {
            Log(0, "state 1014 handler 0x%08lx does not match - strike gate off", kState1014Pc[k]);
            g_strikeGate = 0;
        }
    g_origReg = reinterpret_cast<RegFn>(kRegFn);
    DWORD hook = reinterpret_cast<DWORD>(&RegHook);
    if (!WriteCode(kRegSlot, &hook, 4)) return false;
    Log(1, "Lara registration: vtable slot 0x%08lx -> hook (tables are extended when tru+0x368b60 runs)", kRegSlot);
    return true;
}

// ---------------------------------------------------------------- 0.6: K14 - the damage-type switch of the enemy
// damage function tru+0x237590 (TU 0x822f60e0, retail 0x822f87d8; docs Befund-K14-Schadensarten-0611.md).
// cdecl (instance, hit vector, float amount, bool, int type, int subtype, int flags): brain = [[inst+0x2d0]]+0x2ec;
// brain +8 bit 0x800 -> returns at once; then a switch over the type: bound 16 (`cmp esi, 0x10` tru+0x237619), byte
// table 0x6376c4 (17 entries) -> jump table 0x6376b8 {0x637630 damage (health component brain+0x2c60, tru+0x22e370)
// + death check (tru+0x220380, flags bit 0: LP <= 0 -> regenerate or die), 0x637685 stamina (tru+0x220ea0) +
// tru+0x25a860 (flags bit 1), 0x6376b1 nothing}. The TU bounds the type at 0x1b; its 28-word table 0x822f61e4 has 0..16 as retail / PC, 17 -> nothing,
// 18..27 -> damage + death check (the same case body). Lara's DLC 2 attack records (doppelganger_casual DTP 20212,
// activity 1005 -> CombatManager+0xc4, record +0x0c) use 17..27, so on the PC those hits do nothing at all.
// [Damage] Translate=1 extends the PC switch exactly so: the byte-table operand of `movzx edx, byte [esi + table]`
// (tru+0x237625) points at kTuDamageCase (plugin .rdata), then the bound becomes 0x1b. Jump table and case bodies stay
// the game's. Write order keeps every intermediate state valid (table first, bound last; off: bound first).
// [Damage] Log=1 (default, changes nothing): an entry hook counts the incoming types per target and caller and logs
// them as burst lines every 2 s while hits happen.
const DWORD kDamageFn = 0x00637590;
const char kDamageEntryHex[] = "55 8b6c2408 8b85d0020000 85c0 57 7504 33ff eb08 8b00 8bb8ec020000 8b4f08 c1e90b f6c101 "
                               "0f85f7000000";
const DWORD kDamageBound = 0x0063761b;          // imm8 of cmp esi, 0x10
const DWORD kDamageTableOperand = 0x00637625;   // disp32 of movzx edx, byte [esi + 0x6376c4]
const DWORD kDamagePcTable = 0x006376c4;
const BYTE kDamagePcBound = 0x10, kDamageTuBound = 0x1b;
// TU 0x822f61e4 (28 words): 0x822f6254 -> 0 (damage + death check = PC 0x637630), 0x822f62c0 -> 1 (stamina = PC
// 0x637685), 0x822f62e8 -> 2 (nothing = PC 0x6376b1)
const BYTE kTuDamageCase[28] = {0, 0, 0, 2, 0, 2, 0, 2, 0, 2, 0, 1, 2, 0, 0, 2, 0,   // 0..16 = PC 0x6376c4
                                2,                                                 // 17
                                0, 0, 0, 0, 0, 0, 0, 0, 0, 0};                     // 18..27
typedef DWORD(__cdecl *DamageFn)(BYTE *inst, void *vec, float amount, DWORD reset, DWORD type, DWORD sub, DWORD flags);
DamageFn g_oDamage = nullptr;
int g_dmgTranslate = 1;            // [Damage] Translate (0.6.3: default 1) (read again at run time, at most once per second, while hits come)
int g_dmgLog = 1;                  // [Damage] Log
int g_dmgMax = 3000;               // [Damage] MaxLines
bool g_dmgHooked = false;          // entry hook placed (all checks passed)
bool g_dmgApplied = false;         // switch extended (bound 0x1b, TU table)
bool g_dmgBroken = false;          // the switch bytes are neither ours nor the game's - switch frozen
bool g_dmgLabels = false;          // the three call sites below verified (names in the log)
bool g_dmgFlusher = false;         // flush thread runs
BYTE *g_dmgCode = nullptr;         // trampoline page
DWORD g_dmgSwitchTick = 0;
volatile LONG g_dmgLines = 0;
CRITICAL_SECTION g_dmgLock;

enum { kVSkip = 0, kVDamage = 1, kVStamina = 2, kVNothing = 3, kVDropped = 4 };
const char *const kVerdict[5] = {"no effect (brain flag 0x800: returns at once)", "damage + death check", "stamina",
                                 "nothing (case)", "DROPPED (above the bound)"};
int DamageCase(DWORD type, bool tu) {
    if (type > (tu ? 27u : 16u)) return kVDropped;
    const BYTE c = kTuDamageCase[type];
    return c == 0 ? kVDamage : c == 1 ? kVStamina : kVNothing;
}

// game state of the switch: 0 = the game's (bound 0x10, table 0x6376c4), 1 = ours, 2 = half ours (table ours, bound
// still 0x10 - valid: indices 0..16 read the same values), -1 = anything else
int DamageSwitchState() {
    const DWORD cmp = Rd(reinterpret_cast<const void *>(kDamageBound - 2));     // 83 fe <bound> 0f
    const DWORD op = Rd(reinterpret_cast<const void *>(kDamageTableOperand));
    const BYTE bound = static_cast<BYTE>(cmp >> 16);
    if ((cmp & 0xff00ffff) != 0x0f00fe83) return -1;
    if (bound == kDamagePcBound && op == kDamagePcTable) return 0;
    if (bound == kDamageTuBound && op == reinterpret_cast<DWORD>(kTuDamageCase)) return 1;
    if (bound == kDamagePcBound && op == reinterpret_cast<DWORD>(kTuDamageCase)) return 2;
    return -1;
}

// one store (a byte, or a dword inside one cache line: 0x637625..0x637628 lie in 0x637600..0x63763f)
bool WriteSmall(DWORD at, DWORD value, size_t length) {
    DWORD old = 0;
    void *p = reinterpret_cast<void *>(at);
    if (!VirtualProtect(p, length, PAGE_EXECUTE_READWRITE, &old)) {
        Log(0, "VirtualProtect failed (%lu) at 0x%08lx", GetLastError(), at);
        return false;
    }
    if (length == 1) *static_cast<volatile BYTE *>(p) = static_cast<BYTE>(value);
    else *static_cast<volatile DWORD *>(p) = value;
    DWORD dummy = 0;
    VirtualProtect(p, length, old, &dummy);
    FlushInstructionCache(GetCurrentProcess(), p, length);
    return true;
}

// extend (on) / restore (off) the switch; all or nothing - a partial result (one write failed) is still a valid
// switch (table first / bound last), it is reported and the switch is frozen
bool DamageSet(bool on, const char *when) {
    const int st = DamageSwitchState();
    if (st < 0) {
        g_dmgBroken = true;
        Log(0, "0.6 damage switch (%s): bytes at tru+0x237619 / +0x237625 are neither the game's nor ours - left alone, "
               "[Damage] Translate frozen at %d", when, g_dmgApplied ? 1 : 0);
        return false;
    }
    if (st == (on ? 1 : 0)) { g_dmgApplied = on; return true; }
    bool ok;
    if (on) ok = WriteSmall(kDamageTableOperand, reinterpret_cast<DWORD>(kTuDamageCase), 4) &&
                 WriteSmall(kDamageBound, kDamageTuBound, 1);
    else ok = WriteSmall(kDamageBound, kDamagePcBound, 1) && WriteSmall(kDamageTableOperand, kDamagePcTable, 4);
    const int now = DamageSwitchState();
    g_dmgApplied = now == 1;
    if (!ok || now != (on ? 1 : 0)) {
        g_dmgBroken = true;
        Log(0, "0.6 damage switch (%s): %s failed (state %d) - switch frozen", when, on ? "extend" : "restore", now);
        return false;
    }
    Log(1, "0.6 damage switch (%s): %s - tru+0x23761b bound 0x%02x, byte table tru+0x237625 -> 0x%08lx%s", when,
        on ? "EXTENDED as the TU (0..27: 17 nothing, 18..27 damage + death check)" : "the game's (0..16, above dropped)",
        on ? kDamageTuBound : kDamagePcBound, on ? reinterpret_cast<DWORD>(kTuDamageCase) : kDamagePcTable,
        on ? " (plugin table, 28 entries)" : "");
    return true;
}

// [Damage] Translate again from the INI, at most once per second, on the game thread (from the entry hook, before the
// original runs - so the hit that notices the change already uses it)
void DamageReadSwitch() {
    if (!g_iniPath[0] || g_dmgBroken) return;
    const DWORD now = GetTickCount();
    if (now - g_dmgSwitchTick < 1000) return;
    g_dmgSwitchTick = now;
    const int t = GetPrivateProfileIntA("Damage", "Translate", g_dmgTranslate, g_iniPath) ? 1 : 0;
    if (t == (g_dmgTranslate ? 1 : 0)) return;
    Log(1, "0.6 switch: [Damage] Translate %d -> %d (read again from TruShadowCombat.ini)", g_dmgTranslate ? 1 : 0, t);
    g_dmgTranslate = t;
    DamageSet(t != 0, "run time");
}

float RdFloat(const void *p) {
    const DWORD v = Rd(p);
    float f;
    memcpy(&f, &v, 4);
    return f;
}

BYTE *DamageBrain(const BYTE *inst) {
    const BYTE *h = reinterpret_cast<const BYTE *>(Rd(inst ? inst + 0x2d0 : nullptr));
    const BYTE *b = h ? reinterpret_cast<const BYTE *>(Rd(h)) : nullptr;
    return b ? reinterpret_cast<BYTE *>(Rd(b + 0x2ec)) : nullptr;
}

const char *DamageCaller(DWORD ret) {
    if (!g_dmgLabels) return nullptr;
    switch (ret) {
    case 0x0063ab6b: return "hit message 0x11c (tru+0x23aaa0)";
    case 0x0063772c: return "kill (tru+0x2376e0, amount = LP)";
    case 0x0065afa1: return "fall (EnemyState_Fall tru+0x25adb0)";
    default: return nullptr;
    }
}

// burst counters: one slot per target / type / subtype / caller / verdict / switch state, flushed every 2 s
struct DmgSlot {
    BYTE *inst; DWORD type, sub, ret, flags, count; int verdict; bool applied;
    float amount, lpBefore, lpAfter; char who[96];
};
const int kDmgSlots = 24;
DmgSlot g_dmgSlot[kDmgSlots];
int g_dmgUsed = 0;
LONG g_dmgMissed = 0;
DWORD g_dmgStart = 0;

void DamageLine(const DmgSlot &s) {
    LONG n = InterlockedIncrement(&g_dmgLines);
    if (n > g_dmgMax) {
        if (n == g_dmgMax + 1) Log(1, "0.6 damage types: [Damage] MaxLines %d reached - no more lines", g_dmgMax);
        return;
    }
    char via[48];
    const char *name = DamageCaller(s.ret);
    if (name) strcpy_s(via, sizeof(via), name);
    else _snprintf_s(via, sizeof(via), _TRUNCATE, "return 0x%08lx", s.ret);
    const int pc = DamageCase(s.type, false), tu = DamageCase(s.type, true);
    char what[160];
    if (s.verdict == kVSkip)
        _snprintf_s(what, sizeof(what), _TRUNCATE, "%s", kVerdict[kVSkip]);
    else if (s.applied)
        _snprintf_s(what, sizeof(what), _TRUNCATE, "switch as TU: %s%s%s%s", kVerdict[tu], pc != tu ? " (PC alone: " : "",
                    pc != tu ? kVerdict[pc] : "", pc != tu ? ")" : "");
    else
        _snprintf_s(what, sizeof(what), _TRUNCATE, "PC: %s%s%s%s", kVerdict[pc], pc != tu ? " (TU: " : "",
                    pc != tu ? kVerdict[tu] : "", pc != tu ? ")" : "");
    Log(1, "0.6 damage types: %s type %lu sub %ld x%lu via %s, amount %.1f, flags 0x%lx, LP %.0f -> %.0f: %s", s.who,
        s.type, static_cast<long>(s.sub), s.count, via, s.amount, s.flags, s.lpBefore, s.lpAfter, what);
}

void DamageFlush(bool force) {
    DmgSlot copy[kDmgSlots];
    int n = 0;
    LONG missed = 0;
    EnterCriticalSection(&g_dmgLock);
    if (g_dmgUsed && (force || GetTickCount() - g_dmgStart >= 2000)) {
        n = g_dmgUsed;
        memcpy(copy, g_dmgSlot, sizeof(DmgSlot) * static_cast<size_t>(n));
        missed = g_dmgMissed;
        g_dmgUsed = 0;
        g_dmgMissed = 0;
    }
    LeaveCriticalSection(&g_dmgLock);
    for (int k = 0; k < n; ++k) DamageLine(copy[k]);
    if (missed) Log(1, "0.6 damage types: %ld more hits in this window not counted (more than %d target / type pairs)",
                    missed, kDmgSlots);
}

// flushes the burst counters every 250 ms once their window is 2 s old (no game memory read or written here)
DWORD WINAPI DamageFlushThread(LPVOID) {
    for (;;) {
        Sleep(250);
        DamageFlush(false);
    }
}

// game thread, after the original: count the hit (names resolved once per new slot, every read SEH-guarded)
void DamageRecord(BYTE *inst, DWORD type, DWORD sub, DWORD ret, DWORD flags, float amount, float before, float after,
                  int verdict) {
    EnterCriticalSection(&g_dmgLock);
    if (!g_dmgUsed) g_dmgStart = GetTickCount();
    int k = 0;
    for (; k < g_dmgUsed; ++k) {
        const DmgSlot &s = g_dmgSlot[k];
        if (s.inst == inst && s.type == type && s.sub == sub && s.ret == ret && s.verdict == verdict &&
            s.applied == g_dmgApplied) break;
    }
    if (k == g_dmgUsed) {
        if (g_dmgUsed < kDmgSlots) {
            DmgSlot &s = g_dmgSlot[g_dmgUsed++];
            memset(&s, 0, sizeof(s));
            s.inst = inst; s.type = type; s.sub = sub; s.ret = ret; s.verdict = verdict; s.applied = g_dmgApplied;
            s.lpBefore = before;
            Describe(inst, s.who, sizeof(s.who));
        } else {
            ++g_dmgMissed;
            k = -1;
        }
    }
    if (k >= 0) {
        DmgSlot &s = g_dmgSlot[k];
        ++s.count;
        s.flags = flags;
        s.amount = amount;
        s.lpAfter = after;
    }
    const bool flushNow = !g_dmgFlusher && GetTickCount() - g_dmgStart >= 2000;
    LeaveCriticalSection(&g_dmgLock);
    if (flushNow) DamageFlush(false);
}

// entry hook of tru+0x237590: the original runs with the same arguments; the type is only counted
DWORD __cdecl DamageHook(BYTE *inst, void *vec, float amount, DWORD reset, DWORD type, DWORD sub, DWORD flags) {
    const DWORD ret = reinterpret_cast<DWORD>(_ReturnAddress());
    DamageReadSwitch();
    BYTE *brain = DamageBrain(inst);
    const float before = brain ? RdFloat(brain + 0x2c64) : 0.0f;
    const bool skip = brain && (Rd(brain + 8) & 0x800) != 0;
    const int verdict = skip ? kVSkip : DamageCase(type, g_dmgApplied);
    const DWORD r = g_oDamage(inst, vec, amount, reset, type, sub, flags);
    if (g_dmgLog) DamageRecord(inst, type, sub, ret, flags, amount, before, brain ? RdFloat(brain + 0x2c64) : 0.0f, verdict);
    return r;
}

void SetupDamage() {
    if (!g_dmgLog && !g_dmgTranslate) {
        Log(1, "0.6 damage: [Damage] Log=0 and Translate=0 - tru+0x237590 untouched (a later Translate=1 needs a restart)");
        return;
    }
    // the function as analysed (read only); a mismatch leaves it untouched
    struct { DWORD at; const char *hex; const char *what; } const facts[] = {
        {kDamageFn, kDamageEntryHex, "entry tru+0x237590 (brain [[inst+0x2d0]]+0x2ec, flag 0x800 -> return)"},
        {0x00637614, "56 8b742420 83fe10 0f878f000000 0fb696c4766300 ff2495b8766300",
         "switch tru+0x237614: type = argument 4, bound 0x10, byte table 0x6376c4, jump table 0x6376b8"},
        {0x006376b8, "30766300 85766300 b1766300", "jump table 0x6376b8 {0x637630, 0x637685, 0x6376b1}"},
        {0x006376c4, "00 00 00 02 00 02 00 02 00 02 00 01 02 00 00 02 00", "byte table 0x6376c4 (17 entries = TU 0..16)"},
        {0x00637630, "d9442418 56 51 8d8f602c0000 d91c24 e82c6dffff 83fe06 740a 83fe08 c644241000 7505 c644241001 "
                     "f644242801 7452 8b44241c 8b4c2424 8b542410 6a00 6a00 50 8b442420 51 56 52 50 55 e8028dfeff "
                     "83c420 5e 5f 5d c3",
         "case 0x637630: health component tru+0x22e370(amount, type), 6 / 8 flag, flags bit 0 -> death check tru+0x220380"},
        {0x00637685, "d9442418 51 8d8f602c0000 d91c24 e80898feff 8b4c2428 d1e9 f6c101 740e 8b542414 52 55 e8b2310200 "
                     "83c408 5e 5f 5d c3",
         "case 0x637685: stamina tru+0x220ea0(amount), flags bit 1 -> tru+0x25a860; 0x6376b1 = return"},
        {0x0062e370, "8b542408 83faff 8bc1 7424 56 8bca 83e11f be01000000 d3e6 c1fa05 8574901c",
         "health component tru+0x22e370: type = bit index into the mask +0x1c (types up to 31)"},
        {0x006376e0, "8b542404 8b82d0020000 85c0 7504 33c9 eb08 8b00 8b88ec020000 51 8bc4 c70003000000 d981642c0000",
         "kill tru+0x2376e0: same brain path, LP = brain +0x2c64"},
    };
    for (const auto &f : facts)
        if (!HexAt(f.at, f.hex)) {
            Log(0, "0.6 damage: %s at 0x%08lx does not match - damage probe and switch off", f.what, f.at);
            return;
        }
    if (!BytesAt(kDamagePcTable, kTuDamageCase, 17)) {
        Log(0, "0.6 damage: PC byte table differs from the TU table 0..16 - damage probe and switch off");
        return;
    }
    if (DamageSwitchState() != 0) {
        Log(0, "0.6 damage: switch bytes are not the game's - damage probe and switch off");
        return;
    }
    // names in the log: the object name table as TruTrace / 0.5.2 (read only)
    if (HexAt(0x005bcff9, "8b0dd094db00 52 8b14c1")) g_namesOk = true;
    // call sites (labels only): kill tru+0x237727, hit message tru+0x23ab66 (+0x50 -> type, +0x64 -> subtype), fall
    g_dmgLabels = HexAt(0x00637727, "e864feffff") && HexAt(0x0063ab66, "e825caffff") && HexAt(0x0065af9c, "e8efc5fdff") &&
                  HexAt(0x0063ab50, "8b5664 8b4650");
    g_dmgCode = static_cast<BYTE *>(VirtualAlloc(nullptr, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    if (!g_dmgCode) { Log(0, "0.6 damage: no code page (%lu) - damage probe and switch off", GetLastError()); return; }
    memcpy(g_dmgCode, reinterpret_cast<const void *>(kDamageFn), 5);    // push ebp; mov ebp, [esp+8]
    g_dmgCode[5] = 0xe9;
    const DWORD rel = (kDamageFn + 5) - (reinterpret_cast<DWORD>(g_dmgCode) + 10);
    memcpy(g_dmgCode + 6, &rel, 4);
    DWORD old = 0;
    if (!VirtualProtect(g_dmgCode, 4096, PAGE_EXECUTE_READ, &old)) {
        Log(0, "0.6 damage: code page protection failed (%lu) - damage probe and switch off", GetLastError());
        return;
    }
    g_oDamage = reinterpret_cast<DamageFn>(g_dmgCode);
    InitializeCriticalSection(&g_dmgLock);
    if (!WriteJump(kDamageFn, reinterpret_cast<const void *>(&DamageHook))) {
        Log(0, "0.6 damage: entry hook tru+0x237590 failed - damage probe and switch off");
        return;
    }
    g_dmgHooked = true;
    if (g_dmgLog) {
        HANDLE t = CreateThread(nullptr, 0, &DamageFlushThread, nullptr, 0, nullptr);
        if (t) { g_dmgFlusher = true; CloseHandle(t); }
    }
    Log(1, "0.6 damage: entry hook tru+0x237590 placed - log %d (burst lines every 2 s, max %d, %s), call sites %s; "
           "switch: [Damage] Translate %d (read again at run time at most once per second while hits come)",
        g_dmgLog, g_dmgMax, g_dmgFlusher ? "flush thread" : "flushed by the next hit",
        g_dmgLabels ? "named" : "by return address", g_dmgTranslate);
    if (g_dmgTranslate) DamageSet(true, "start");
    else Log(1, "0.6 damage switch (start): the game's (0..16, types 17..27 dropped) - [Damage] Translate=0");
}

// ---------------------------------------------------------------- 0.6.1: lethal impulse -> Death state (TU), no
// chunkdoll inside the physics step (docs Befund-ChunkDoll-Physikschritt-0711.md)
// Chain (PC, static + live stack 07.11.): PhysicsSystem::Step tru+0xf0ab0 sets the lock [phys+0x20f8] = 3 ->
// tru+0x70530 -> contact pairs tru+0x6d200 -> pair callback [phys+0x20+(a*32+b)*8] = tru+0x92980 (geometry types 3 / 9,
// registered tru+0x96b8f) -> message 0x26 to Lara -> CombatManager contact hit tru+0x319050: message 0x11c (damage,
// with [Damage] Translate=1 Lara's types 18..27 bring LP <= 0) and message 0x91 (impulse) to the enemy -> enemy handler
// tru+0x227a80 -> tru+0x2254b0 -> default handler brain+0x1c44 = tru+0x23b330, case 0x91 -> tru+0x224c60.
// tru+0x224c60 = retail 0x82307ea8: LP <= 0 and a chunk record (+0x46) -> chunkdoll create tru+0x296f90 at once ->
// rigid body tru+0x97270 -> AllocBody refuses while the lock bit 0 is set -> fatal "ChunkDoll: failed to create geom".
// The TU (0x82305ba0, same size) removed that block: LP <= 0 -> if not IsInDeathState(inst) (0x82324700: brain+0x125c
// is Death / LandDeath / DeferredInstantDie / DrownDeath / Fade) {v = 0; 0x8230e5c0(&v, inst, msg); death switch
// 0x823258c8(inst, 1, 0, 1, kind 7, 1, v); return} else the hit-reaction path. The chunkdoll then comes from the Death
// state's per-frame slot 8 (tru+0x26c950 = TU 0x8232cd50, same record +0x46 check) - in the enemy update, outside the
// physics step. PC twins: IsDeathState tru+0x240e90 on [brain+0x125c] (the game does the same at tru+0x21f17c),
// tru+0x256430 = retail 0x82310710 = TU 0x8230e5c0 (equal), death switch tru+0x241650 = retail 0x82327a18 / TU
// 0x823258c8 (cdecl inst, vec16*, u8 -> data +0x18, ptr -> +0x10, u8 -> +0x1a, kind -> +0x14, u8 -> +0x1b).
// [Chunk] Translate=1 (default): the first instruction of the PC branch (tru+0x224caa, mov eax, [edi+0x168], 6 bytes)
// jumps to ChunkStub; Translate=0 at run time runs that instruction and the PC branch unchanged. [Chunk] Log=1: burst
// lines (every 2 s, own thread) with the physics lock read at the moment.
const DWORD kImpulseFn = 0x00624c60;          // retail 0x82307ea8, TU 0x82305ba0
const DWORD kImpulseLethal = 0x00624caa;      // LP <= 0 branch: mov eax, [edi+0x168] (6 bytes) - patched
const DWORD kImpulseLethalNext = 0x00624cb0;  // PC branch after that instruction
const DWORD kImpulseAlive = 0x00624ccd;       // hit-reaction path (retail 0x82307f88, TU 0x82305c80)
const DWORD kImpulseReturn = 0x00624cf1;      // pop edi; pop esi; mov esp, ebp; pop ebp; ret
const DWORD kIsDeathState = 0x00640e90;       // cdecl int(state)
const DWORD kHitVector = 0x00656430;          // cdecl (out vec16 aligned, inst, message)
const DWORD kDeathSwitch = 0x00641650;        // cdecl (inst, vec16 aligned *, u8, ptr, u8, kind, u8)
const DWORD kPhysPtr = 0x00a037f4;            // physics system; +0x20f8 lock (bit 0 = inside Step tru+0xf0ab0)
const DWORD kTuDeathKind = 7;                 // TU 0x82305c58 li r7, 7
typedef int(__cdecl *IsDeathStateFn)(DWORD state);
typedef void(__cdecl *HitVectorFn)(float *out, BYTE *inst, void *message);
typedef DWORD(__cdecl *DeathSwitchFn)(BYTE *inst, const float *vec, DWORD a2, DWORD a3, DWORD a4, DWORD kind, DWORD a6);
int g_chunkTranslate = 1;          // [Chunk] Translate (read again at run time, at most once per second, while it is hit)
int g_chunkLog = 1;                // [Chunk] Log
int g_chunkMax = 2000;             // [Chunk] MaxLines
bool g_chunkHooked = false;
bool g_chunkFlusher = false;
DWORD g_chunkSwitchTick = 0;
DWORD g_chunkAliveTo = kImpulseAlive, g_chunkReturnTo = kImpulseReturn, g_chunkNextTo = kImpulseLethalNext;
volatile LONG g_chunkLines = 0;
CRITICAL_SECTION g_chunkLock;

enum { kCDeath = 0, kCDying = 1, kCPc = 2 };
struct ChunkSlot { BYTE *inst; int outcome, record; DWORD lock, count; float lp; char who[96]; };
const int kChunkSlots = 16;
ChunkSlot g_chunkSlot[kChunkSlots];
int g_chunkUsed = 0;
LONG g_chunkMissed = 0;
DWORD g_chunkStart = 0;

// read only, as tru+0x214610 / the inlined loop at tru+0x224caa: first entry of the list [brain+0x168] with +0x64,
// its record word +0x46 (0 = no chunkdoll); -1 = no list (the game then asks the print stub tru+0x2457a0)
int ChunkRecord(const BYTE *brain) {
    const BYTE *e = brain ? reinterpret_cast<const BYTE *>(Rd(brain + 0x168)) : nullptr;
    if (!e) return -1;
    for (int i = 0; e && i < 64; ++i) {
        const BYTE *r = reinterpret_cast<const BYTE *>(Rd(e + 0x64));
        if (r) return (Rd(r + 0x44) >> 16) != 0 ? 1 : 0;
        e = reinterpret_cast<const BYTE *>(Rd(e + 0x1c));
    }
    return 0;
}

void ChunkLine(const ChunkSlot &s) {
    LONG n = InterlockedIncrement(&g_chunkLines);
    if (n > g_chunkMax) {
        if (n == g_chunkMax + 1) Log(1, "0.6.1 chunk: [Chunk] MaxLines %d reached - no more lines", g_chunkMax);
        return;
    }
    char lock[64];
    if (s.lock == 0xffffffff) strcpy_s(lock, sizeof(lock), "physics lock unread");
    else _snprintf_s(lock, sizeof(lock), _TRUNCATE, "physics lock 0x%lx (%s)", s.lock,
                     (s.lock & 1) ? "INSIDE the physics step" : "outside the step");
    const char *rec = s.record > 0 ? "chunk record yes" : s.record == 0 ? "chunk record no" : "no record list";
    const char *pc = s.record > 0 ? ((s.lock != 0xffffffff && (s.lock & 1))
                                         ? "PC alone: chunkdoll NOW, bodies refused in the step -> fatal"
                                         : "PC alone: chunkdoll now")
                                  : "PC alone: hit reaction";
    const char *what = s.outcome == kCDeath ? "TU: death switch (Death, kind 7) - chunkdoll left to the Death state"
                     : s.outcome == kCDying ? "TU: already in a death state -> hit-reaction path"
                                            : "PC branch ([Chunk] Translate=0)";
    Log(1, "0.6.1 chunk: %s x%lu lethal impulse (message 0x91, tru+0x224c60) at LP %.0f, %s, %s: %s (%s)", s.who, s.count,
        s.lp, lock, rec, what, pc);
}

void ChunkFlush(bool force) {
    ChunkSlot copy[kChunkSlots];
    int n = 0;
    LONG missed = 0;
    EnterCriticalSection(&g_chunkLock);
    if (g_chunkUsed && (force || GetTickCount() - g_chunkStart >= 2000)) {
        n = g_chunkUsed;
        memcpy(copy, g_chunkSlot, sizeof(ChunkSlot) * static_cast<size_t>(n));
        missed = g_chunkMissed;
        g_chunkUsed = 0;
        g_chunkMissed = 0;
    }
    LeaveCriticalSection(&g_chunkLock);
    for (int k = 0; k < n; ++k) ChunkLine(copy[k]);
    if (missed) Log(1, "0.6.1 chunk: %ld more lethal impulses in this window not counted", missed);
}

// writes the burst lines every 250 ms once their window is 2 s old (no game memory read or written here)
DWORD WINAPI ChunkFlushThread(LPVOID) {
    for (;;) {
        Sleep(250);
        ChunkFlush(false);
    }
}

// game thread: count the event (name resolved once per new slot, every read SEH-guarded)
void ChunkRecordEvent(BYTE *inst, const BYTE *brain, int outcome) {
    const BYTE *phys = reinterpret_cast<const BYTE *>(Rd(reinterpret_cast<const void *>(kPhysPtr)));
    const DWORD lock = phys ? Rd(phys + 0x20f8) : 0xffffffff;
    const int record = ChunkRecord(brain);
    const float lp = brain ? RdFloat(brain + 0x2c64) : 0.0f;
    EnterCriticalSection(&g_chunkLock);
    if (!g_chunkUsed) g_chunkStart = GetTickCount();
    int k = 0;
    for (; k < g_chunkUsed; ++k) {
        const ChunkSlot &s = g_chunkSlot[k];
        if (s.inst == inst && s.outcome == outcome && s.lock == lock && s.record == record) break;
    }
    if (k == g_chunkUsed) {
        if (g_chunkUsed < kChunkSlots) {
            ChunkSlot &s = g_chunkSlot[g_chunkUsed++];
            memset(&s, 0, sizeof(s));
            s.inst = inst; s.outcome = outcome; s.lock = lock; s.record = record;
            Describe(inst, s.who, sizeof(s.who));
        } else {
            ++g_chunkMissed;
            k = -1;
        }
    }
    if (k >= 0) {
        ++g_chunkSlot[k].count;
        g_chunkSlot[k].lp = lp;
    }
    LeaveCriticalSection(&g_chunkLock);
}

// [Chunk] Translate again from the INI, at most once per second, on the game thread (when the branch is reached)
void ChunkReadSwitch() {
    if (!g_iniPath[0]) return;
    const DWORD now = GetTickCount();
    if (now - g_chunkSwitchTick < 1000) return;
    g_chunkSwitchTick = now;
    const int t = GetPrivateProfileIntA("Chunk", "Translate", g_chunkTranslate, g_iniPath) ? 1 : 0;
    if (t == g_chunkTranslate) return;
    Log(1, "0.6.1 switch: [Chunk] Translate %d -> %d (read again from TruShadowCombat.ini) - %s", g_chunkTranslate, t,
        t ? "lethal impulse as the TU (death switch kind 7)" : "the PC branch (chunkdoll at once)");
    g_chunkTranslate = t;
}

// the TU's LP <= 0 branch of 0x82305ba0 on the PC; returns 1 = done (function returns), 0 = hit-reaction path,
// 2 = run the PC branch (Translate=0)
int __cdecl ChunkLethal(BYTE *brain, BYTE *inst, void *message) {
    ChunkReadSwitch();
    if (!g_chunkTranslate) {
        if (g_chunkLog) ChunkRecordEvent(inst, brain, kCPc);
        return 2;
    }
    // TU 0x82305c18: IsInDeathState(inst) = the layer-0 state brain+0x125c is one of the five death states
    if (reinterpret_cast<IsDeathStateFn>(kIsDeathState)(*reinterpret_cast<const DWORD *>(brain + 0x125c)) != 0) {
        if (g_chunkLog) ChunkRecordEvent(inst, brain, kCDying);
        return 0;
    }
    if (g_chunkLog) ChunkRecordEvent(inst, brain, kCDeath);    // before the switch: LP / record as the hit left them
    // TU 0x82305c2c..0x82305c70: v = 0 vector (0x8207db30 = PC [0x84111c] 0.0), 0x8230e5c0(&v, inst, msg),
    // 0x823258c8(inst, 1, 0, 1, 7, 1, v)
    __declspec(align(16)) float v[4] = {0.0f, 0.0f, 0.0f, 0.0f};
    reinterpret_cast<HitVectorFn>(kHitVector)(v, inst, message);
    reinterpret_cast<DeathSwitchFn>(kDeathSwitch)(inst, v, 1, 0, 1, kTuDeathKind, 1);
    return 1;
}

// jumped to from tru+0x224caa: esi = instance, edi = brain, [ebp+0xc] = message (as the PC code at tru+0x224d39 /
// tru+0x224c69); FPU stack empty (fcomp popped the LP); eax / ecx / edx are free (reloaded by every target)
__declspec(naked) void ChunkStub() {
    __asm {
        push dword ptr [ebp + 0xc]
        push esi
        push edi
        call ChunkLethal
        add esp, 12
        cmp eax, 1
        je chunk_done
        cmp eax, 2
        je chunk_pc
        jmp dword ptr [g_chunkAliveTo]
    chunk_done:
        jmp dword ptr [g_chunkReturnTo]
    chunk_pc:
        mov eax, dword ptr [edi + 0x168]
        jmp dword ptr [g_chunkNextTo]
    }
}

void SetupChunk() {
    if (!g_chunkTranslate && !g_chunkLog) {
        Log(1, "0.6.1 chunk: [Chunk] Translate=0 and Log=0 - tru+0x224c60 untouched (a later Translate=1 needs a restart)");
        return;
    }
    // everything the branch and the replacement rely on (read only); a mismatch leaves the game untouched
    struct { DWORD at; const char *hex; const char *what; } const facts[] = {
        {kImpulseFn,
         "55 8bec 83e4f0 83ec78 8b450c 56 8b7508 89442408 8b86d0020000 85c0 57 7504 33ff eb08 8b08 8bb9ec020000 85c0 7408 "
         "8b10 8b82ec020000 d980642c0000 dc1db8148400 dfe0 f6c441 7a23 8b8768010000 85c0 750c e8e70a0200 85c0 7410 8d4900 "
         "83786400 7531 8b401c 85c0 75f3 8b8768010000 85c0 750d e8c40a0200 85c0 0f8455010000 83785000 754f 8b401c 85c0 "
         "75f3 5f 5e 8be5 5d c3 8b4064 85c0 74cf 6683784600 74c8 56 e885220700 83c404 84c0 74bb d905ac3c8400 51 8d4620 "
         "d91c24 50 56 e8aa230700 56 e8e4750400 83c410 834e1420 5f 5e 8be5 5d c3",
         "tru+0x224c60: brain in edi, LP <= 0.0 -> record +0x64 / +0x46 -> chunkdoll tru+0x296f90, else hit reaction "
         "tru+0x224ccd, return tru+0x224cf1"},
        {0x00624d39, "8b4c240c f30f10051c118400 51 8d542414",
         "hit-reaction path: message = [esp+0xc], zero vector [0x84111c]"},
        {0x00624d6a, "56 52 c787c811000000000000 c787cc11000000000000 0f2944241c e8a6160300 83c40c",
         "hit-reaction path: tru+0x256430(&v, inst, message)"},
        {0x0084111c, "00000000", "0.0f at 0x84111c"},
        {0x0063b3dd, "6a17 8d4d08 e819b2fdff 84c0 74e8 8b5604 52 57 e86b98feff 83c408",
         "enemy handler tru+0x23b330 case 0x91 -> tru+0x224c60(inst, message)"},
        {kIsDeathState, "8b442404 3d04e98a00 741f 3d28e98a00 7418 3d7cef8a00 7411 3d34ef8a00 740a 3d4ce98a00 7403 33c0 c3 "
                        "b801000000 c3",
         "IsDeathState tru+0x240e90: Death, LandDeath, DeferredInstantDie, DrownDeath, Fade (= TU 0x82324700 order)"},
        {0x0061f17c, "8b865c120000 50 e8081d0200", "the game's own IsDeathState([brain+0x125c]) at tru+0x21f17c"},
        {kHitVector, "55 8bec 83e4f0 81ecc4000000 8b4508 8b4d0c 53 56 8b7510 0f57c0 0f2900",
         "tru+0x256430(out, inst, message): out zeroed with movaps (16-byte aligned)"},
        {kDeathSwitch,
         "55 8bec 83e4f0 83ec24 53 8b5d0c 56 8b7514 57 8b7d08 85ff 0f84ad000000 8b87d0020000 85c0 0f849f000000 8b00 "
         "8b80ec020000 85c0 0f848f000000 d9ee 51 8d88602c0000 d91c24 e8b461ffff 8b4d1c 8bc1 83e805 7409 83e802 7404 32c0 "
         "eb02 b001 85f6 f30f100530118400 0f280b 894c2424 8a4d10 0fc6c000 0f59c1 0f29442410 c744242000000000 884c2428 "
         "88442429 c644242b01 7404 89742420 807d2000 7505 c644242b00 8a5518 6a00 8d442414 50 6804e98a00 57 8854243a "
         "e8d0bfffff 83c410 5f 5e 5b 8be5 5d c3",
         "death switch tru+0x241650 (cdecl 7 arguments, EnemyState_Death 0x8ae904 via tru+0x23d6e0)"},
        {0x004963ba, "a3f437a000", "physics system pointer [0xa037f4] (log only)"},
        {0x004f0ab4, "c786f820000003000000", "Step tru+0xf0ab0: lock [phys+0x20f8] = 3 (log only)"},
    };
    for (const auto &f : facts)
        if (!HexAt(f.at, f.hex)) {
            Log(0, "0.6.1 chunk: %s at 0x%08lx does not match - lethal impulse left to the game (PC branch)", f.what, f.at);
            return;
        }
    if (HexAt(0x005bcff9, "8b0dd094db00 52 8b14c1")) g_namesOk = true;
    InitializeCriticalSection(&g_chunkLock);
    BYTE j[6] = {0xe9, 0, 0, 0, 0, 0x90};
    const DWORD rel = reinterpret_cast<DWORD>(&ChunkStub) - (kImpulseLethal + 5);
    memcpy(j + 1, &rel, 4);
    if (!WriteCode(kImpulseLethal, j, sizeof(j))) {
        Log(0, "0.6.1 chunk: jump at tru+0x224caa failed - lethal impulse left to the game (PC branch)");
        return;
    }
    g_chunkHooked = true;
    if (g_chunkLog) {
        HANDLE t = CreateThread(nullptr, 0, &ChunkFlushThread, nullptr, 0, nullptr);
        if (t) { g_chunkFlusher = true; CloseHandle(t); }
    }
    Log(1, "0.6.1 chunk: tru+0x224caa (LP <= 0 branch of the impulse handler tru+0x224c60, message 0x91) -> plugin - "
           "[Chunk] Translate %d (%s), log %d (burst lines every 2 s, max %d%s); read again at run time at most once per "
           "second", g_chunkTranslate,
        g_chunkTranslate ? "TU 0x82305ba0: death switch kind 7, the chunkdoll comes from the Death state outside the "
                           "physics step" : "PC branch: chunkdoll at once",
        g_chunkLog, g_chunkMax, g_chunkFlusher ? "" : ", no flush thread - lines only at the cap");
}

// ---------------------------------------------------------------- 0.6.2: K9 - CombatManager::MeleeSplashDamage as the
// title update (docs Befund-TU-K9-K11-0711.md in the main workspace; K9 in Befund-Exe-Stellen-K8-K14-0611.md)
// PC tru+0x2e68b0 (thiscall, this = CombatManager [[0xfadb58]+0x504]; called by the event dispatcher tru+0x316f30
// case 75 at tru+0x316fbb) = retail 0x823dedc0 = TU 0x823e1220 (name from the TU debug string 0x820721f0
// "[CombatManager::MeleeSplashDamage] Applying Splash Damage (%f)"). For every splash record of the current attack
// ([CM+0xc4]: +0x0c type, +0x20 count, +0x24 records of 0x1c bytes) it calls the area damage function tru+0x29f1e0
// (retail 0x8237b2a8, TU 0x8237ae88; cdecl, 17 arguments; argument 13 = the damage type, which becomes +0x50 of the hit
// message 0x11c, the type K14's switch tru+0x237590 sees). The TU added two things:
//  (a) doppelganger mode (gameTracker+0x1244) and a valid extension handle gameTracker+0x1314 (instance of object 858,
//      spawned by the TU-only 0x82412ab0): the type is replaced through the pair table [inst+0x50]+0x78 (count +0x7c,
//      8-byte entries {from, to}, signed compare, the first match wins). Data: player_tru_dlc2_extension DTP 22497,
//      block +0xf0 (= the tuning TU 0x82415518 returns) +0x78 -> +0x1b0, count 2: {0x1a -> 0x10}, {0x10 -> 0x16}.
//  (b) always (also outside doppelganger mode): the main target (handle CM+0x48, resolved inline as the PC's
//      tru+0x1b39d0: instance != 0 and [instance+0x44] == handle+4) is passed as an 18th argument, and the area function
//      skips that instance right after its self test (TU 0x8237af64..0x8237af6c; retail / PC test only instance ==
//      source). The nine other TU callers of 0x8237ae88 store their zero register there (no exclusion).
// PC twins: the doppelganger byte is the same field ([[0xfadb58]+0x1244], read by larabase f36 tru+0x377dc0, written by
// TruDlc2Player 0.4 as the TU's DoppelgangerInit); the PC has no extension instance, so the table comes from the loaded
// object 858 (Tuning(), the same data TruShadowPower / the target list read for TU 0x82415518); the handle resolver
// tru+0x1b39d0; the area function's loop test tru+0x29f224 (cmp esi, edi; je tru+0x29f7ed = next instance) is the place
// of the TU's added test.
// Port: the call at tru+0x2e692d goes to SplashCallStub (remap argument 13 in place, note the main target, then JUMP to
// tru+0x29f1e0, so its return address stays tru+0x2e6932); tru+0x29f224 jumps to AreaLoopStub, which skips the noted
// target only in a call that returns to tru+0x2e6932 ([ebp+4]) - the nine other callers of tru+0x29f1e0 are unchanged,
// as on the TU.
// The remap runs only while the K14 switch is extended (0.6 [Damage] Translate=1): 0x16 = 22 is a type only the TU switch
// accepts, so the remap without it would drop the 1015 splash (16 -> 22) - a state neither the TU nor the PC has. With
// [Damage] Translate=0 the doppelganger records keep their type (logged as "held back").
// Data note (converter): the PC trees hold the four pair words partly unswapped (+0x1b0 / +0x1b8 / +0x1bc read
// 0x1a000000 / 0x10000000 / 0x16000000), so the loaded table is compared with the Xbox values; [Splash] Fallback=1
// (default) uses the Xbox values then and says so (as TruShadowPower's tuning fallback).
const DWORD kSplashFn = 0x006e68b0;           // retail 0x823dedc0, TU 0x823e1220
const DWORD kSplashCall = 0x006e692d;         // call tru+0x29f1e0 (e8 rel32) - patched
const DWORD kSplashRet = 0x006e6932;          // its return address (AreaLoopStub compares [ebp+4] with it)
const DWORD kAreaFn = 0x0069f1e0;             // retail 0x8237b2a8, TU 0x8237ae88
const DWORD kAreaLoop = 0x0069f224;           // cmp esi, edi; je 0x69f7ed (8 bytes) - patched
const DWORD kAreaLoopGo = 0x0069f22c;         // the instance is processed
const DWORD kAreaNext = 0x0069f7ed;           // mov edi, [edi+8] (next instance)
const DWORD kHandleFn = 0x005b39d0;           // cdecl instance(handle *): inst && [inst+0x44] == handle+4
const LONG kXboxSplashPairs[2][2] = {{0x1a, 0x10}, {0x10, 0x16}};   // x_player_tru_dlc2_extension DTP 22497 +0x1b0
typedef BYTE *(__cdecl *HandleFn)(const void *handle);
int g_splashTranslate = 1;         // [Splash] Translate (read again at run time, at most once per second, while splashes come)
int g_splashFallback = 1;          // [Splash] Fallback: Xbox pair values when the loaded table differs from them
int g_splashLog = 1;               // [Splash] Log
int g_splashMax = 2000;            // [Splash] MaxLines
bool g_splashHooked = false;
bool g_splashFlusher = false;
DWORD g_splashSwitchTick = 0;
volatile DWORD g_splashTarget = 0; // main target of the running splash call (0 = none); read by AreaLoopStub
volatile LONG g_splashSkips = 0;   // area hits held back from the main target (AreaLoopStub)
volatile LONG g_splashLines = 0;
DWORD g_areaFnTo = kAreaFn, g_areaGoTo = kAreaLoopGo, g_areaNextTo = kAreaNext;
int g_splashTableSource = -1;      // last logged table source
CRITICAL_SECTION g_splashLock;

enum { kSOff = 0, kSNotDg, kSNoTable, kSNoMatch, kSRemap, kSHeld };
const char *const kSplashHow[6] = {
    "[Splash] Translate=0: PC (type kept, main target not excluded)",
    "not in doppelganger mode (gameTracker+0x1244 = 0): type kept",
    "doppelganger mode, no pair table (object 858 not loaded or table empty - TU: no extension, type kept)",
    "doppelganger mode, no pair for this type: kept",
    "doppelganger mode: REMAPPED as TU 0x823e1220",
    "doppelganger mode: the TU remaps it, HELD BACK - damage switch is the PC's ([Damage] Translate=0)"};
enum { kTNone = 0, kTObject = 1, kTFallback = 2, kTLoaded = 3, kTEmpty = 4 };
const char *const kTableSource[5] = {"none (object 858 not loaded)", "object 858 (= the Xbox values)",
                                     "Xbox values (FALLBACK: the loaded table differs)",
                                     "object 858 as loaded (differs from the Xbox values, [Splash] Fallback=0)",
                                     "object 858: table pointer / count 0"};

// the pair table the remap uses now: TU [inst+0x50]+0x78 / +0x7c = here Tuning() +0x78 / +0x7c
int SplashTable(const LONG **pairs, DWORD *count) {
    *pairs = nullptr;
    *count = 0;
    const BYTE *tuning = Tuning();
    if (!tuning) return kTNone;
    const LONG *table = reinterpret_cast<const LONG *>(Rd(tuning + 0x78));
    const DWORD n = Rd(tuning + 0x7c);
    if (!table || !n) return kTEmpty;
    bool same = n == 2;
    for (DWORD i = 0; same && i < 2; ++i)
        same = static_cast<LONG>(Rd(table + 2 * i)) == kXboxSplashPairs[i][0] &&
               static_cast<LONG>(Rd(table + 2 * i + 1)) == kXboxSplashPairs[i][1];
    int source = same ? kTObject : (g_splashFallback ? kTFallback : kTLoaded);
    if (source != g_splashTableSource) {
        g_splashTableSource = source;
        char loaded[160] = "";
        int w = 0;
        for (DWORD i = 0; i < n && i < 4 && w >= 0 && w < static_cast<int>(sizeof(loaded)) - 40; ++i)
            w += _snprintf_s(loaded + w, sizeof(loaded) - w, _TRUNCATE, "%s{0x%lx -> 0x%lx}", i ? ", " : "",
                             Rd(table + 2 * i), Rd(table + 2 * i + 1));
        Log(1, "0.6.2 splash table: object 858 tuning 0x%08lx +0x78 -> 0x%08lx, count %lu: %s%s - used: %s",
            reinterpret_cast<DWORD>(tuning), reinterpret_cast<DWORD>(table), n, loaded, n > 4 ? " ..." : "",
            source == kTObject ? "these (= Xbox DTP 22497 +0x1b0)"
            : source == kTFallback ? "the Xbox values {0x1a -> 0x10}, {0x10 -> 0x16} (DTP 22497 +0x1b0; the converted "
                                     "file holds words unswapped - converter fix pending)"
                                   : "these as loaded ([Splash] Fallback=0)");
    }
    if (source == kTFallback) {
        *pairs = &kXboxSplashPairs[0][0];
        *count = 2;
    } else {
        *pairs = table;
        *count = n > 64 ? 64 : n;
    }
    return source;
}

struct SplashSlot { DWORD typeIn, typeOut, target, count; int how, source; bool applied; char who[96]; };
const int kSplashSlots = 16;
SplashSlot g_splashSlot[kSplashSlots];
int g_splashUsed = 0;
LONG g_splashMissed = 0;
DWORD g_splashStart = 0;

void SplashLine(const SplashSlot &s) {
    LONG n = InterlockedIncrement(&g_splashLines);
    if (n > g_splashMax) {
        if (n == g_splashMax + 1) Log(1, "0.6.2 splash: [Splash] MaxLines %d reached - no more lines", g_splashMax);
        return;
    }
    char type[96];
    if (s.typeOut != s.typeIn)
        _snprintf_s(type, sizeof(type), _TRUNCATE, "type %lu -> %lu", s.typeIn, s.typeOut);
    else if (s.how == kSHeld)
        _snprintf_s(type, sizeof(type), _TRUNCATE, "type %lu (TU: -> %lu)", s.typeIn, s.target);
    else
        _snprintf_s(type, sizeof(type), _TRUNCATE, "type %lu", s.typeIn);
    const int verdict = DamageCase(s.typeOut, s.applied);
    Log(1, "0.6.2 splash: x%lu record %s - %s%s%s; main target %s; enemy switch %s: %s", s.count, type, kSplashHow[s.how],
        s.how == kSRemap || s.how == kSHeld || s.how == kSNoMatch ? ", table " : "",
        s.how == kSRemap || s.how == kSHeld || s.how == kSNoMatch ? kTableSource[s.source] : "",
        s.how == kSOff ? "not excluded" : s.who, s.applied ? "as TU (0..27)" : "PC (0..16)", kVerdict[verdict]);
}

void SplashFlush(bool force) {
    SplashSlot copy[kSplashSlots];
    int n = 0;
    LONG missed = 0, skips = 0;
    EnterCriticalSection(&g_splashLock);
    if (g_splashUsed && (force || GetTickCount() - g_splashStart >= 2000)) {
        n = g_splashUsed;
        memcpy(copy, g_splashSlot, sizeof(SplashSlot) * static_cast<size_t>(n));
        missed = g_splashMissed;
        g_splashUsed = 0;
        g_splashMissed = 0;
        skips = InterlockedExchange(&g_splashSkips, 0);
    }
    LeaveCriticalSection(&g_splashLock);
    for (int k = 0; k < n; ++k) SplashLine(copy[k]);
    if (skips && InterlockedCompareExchange(&g_splashLines, 0, 0) <= g_splashMax)
        Log(1, "0.6.2 splash: %ld area hit(s) on the main target held back in this window (TU 0x8237af64: the main "
               "target gets no extra splash hit)", skips);
    if (missed) Log(1, "0.6.2 splash: %ld more splash records in this window not counted", missed);
}

// writes the burst lines every 250 ms once their window is 2 s old (no game memory read or written here)
DWORD WINAPI SplashFlushThread(LPVOID) {
    for (;;) {
        Sleep(250);
        SplashFlush(false);
    }
}

// game thread: count one splash record (names resolved once per new slot, every read SEH-guarded)
void SplashRecord(DWORD typeIn, DWORD typeOut, DWORD tuTo, int how, int source, BYTE *target) {
    EnterCriticalSection(&g_splashLock);
    if (!g_splashUsed) g_splashStart = GetTickCount();
    const DWORD key = how == kSHeld ? tuTo : reinterpret_cast<DWORD>(target);
    int k = 0;
    for (; k < g_splashUsed; ++k) {
        const SplashSlot &s = g_splashSlot[k];
        if (s.typeIn == typeIn && s.typeOut == typeOut && s.how == how && s.source == source &&
            s.applied == g_dmgApplied && s.target == key)
            break;
    }
    if (k == g_splashUsed) {
        if (g_splashUsed < kSplashSlots) {
            SplashSlot &s = g_splashSlot[g_splashUsed++];
            memset(&s, 0, sizeof(s));
            s.typeIn = typeIn; s.typeOut = typeOut; s.how = how; s.source = source; s.applied = g_dmgApplied;
            s.target = key;                       // kSHeld: the TU's type (shown in the line); else the target
            if (target) Describe(target, s.who, sizeof(s.who));
            else strcpy_s(s.who, sizeof(s.who), "none (handle CM+0x48 empty / stale)");
        } else {
            ++g_splashMissed;
            k = -1;
        }
    }
    if (k >= 0) ++g_splashSlot[k].count;
    const bool flushNow = !g_splashFlusher && GetTickCount() - g_splashStart >= 2000;
    LeaveCriticalSection(&g_splashLock);
    if (flushNow) SplashFlush(false);
}

// [Splash] Translate again from the INI, at most once per second, on the game thread (from SplashPrepare)
void SplashReadSwitch() {
    if (!g_iniPath[0]) return;
    const DWORD now = GetTickCount();
    if (now - g_splashSwitchTick < 1000) return;
    g_splashSwitchTick = now;
    const int t = GetPrivateProfileIntA("Splash", "Translate", g_splashTranslate, g_iniPath) ? 1 : 0;
    if (t == g_splashTranslate) return;
    Log(1, "0.6.2 switch: [Splash] Translate %d -> %d (read again from TruShadowCombat.ini) - %s", g_splashTranslate, t,
        t ? "splash as the TU (main target excluded, doppelganger remap)" : "the PC splash");
    g_splashTranslate = t;
}

// TU 0x823e1220 per record, before the area call: (a) remap argument 13, (b) note the main target for AreaLoopStub
void __cdecl SplashPrepare(BYTE *cm, DWORD *args) {
    SplashReadSwitch();
    g_splashTarget = 0;
    const DWORD typeIn = args[13];
    DWORD typeOut = typeIn, tuTo = typeIn;
    int how = kSOff, source = kTNone;
    BYTE *target = nullptr;
    if (g_splashTranslate) {
        __try {
            target = reinterpret_cast<HandleFn>(kHandleFn)(cm + 0x48);          // TU 0x823e1324..0x823e1348
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            target = nullptr;
        }
        g_splashTarget = reinterpret_cast<DWORD>(target);
        const BYTE *gt = GameTracker();
        const bool dg = gt && (Rd(gt + 0x1244) & 0xff) != 0;                   // TU 0x823e1270 lbz 0x1244
        if (!dg) {
            how = kSNotDg;
        } else {
            const LONG *pairs = nullptr;
            DWORD n = 0;
            source = SplashTable(&pairs, &n);
            if (!pairs || !n) {
                how = kSNoTable;
            } else {
                how = kSNoMatch;
                for (DWORD i = 0; i < n; ++i)                                  // TU 0x823e12f8..0x823e1320
                    if (static_cast<LONG>(Rd(pairs + 2 * i)) == static_cast<LONG>(typeIn)) {
                        tuTo = Rd(pairs + 2 * i + 1);
                        how = g_dmgApplied ? kSRemap : kSHeld;
                        break;
                    }
                if (how == kSRemap) {
                    typeOut = tuTo;
                    args[13] = typeOut;
                }
            }
        }
    }
    if (g_splashLog) SplashRecord(typeIn, typeOut, tuTo, how, source, target);
}

// called from tru+0x2e692d instead of tru+0x29f1e0: [esp] = tru+0x2e6932, [esp+4..] = the 17 arguments, edi =
// CombatManager (tru+0x2e68b2). The FPU stack is empty there; eax / ecx / edx are not used after the call.
__declspec(naked) void SplashCallStub() {
    __asm {
        lea eax, [esp + 4]
        push eax
        push edi
        call SplashPrepare
        add esp, 8
        jmp dword ptr [g_areaFnTo]
    }
}

// jumped to from tru+0x29f224 (area function loop, esi = source instance, edi = candidate, ebp = its frame): the PC
// self test, then the TU's main-target test - only for the splash call (return address tru+0x2e6932). The flags are
// not used by either target (both set them again before any branch).
__declspec(naked) void AreaLoopStub() {
    __asm {
        cmp esi, edi
        je area_next
        cmp dword ptr [ebp + 4], 0x006e6932
        jne area_go
        cmp edi, dword ptr [g_splashTarget]
        jne area_go
        lock inc dword ptr [g_splashSkips]
    area_next:
        jmp dword ptr [g_areaNextTo]
    area_go:
        jmp dword ptr [g_areaGoTo]
    }
}

void SetupSplash() {
    if (!g_splashTranslate && !g_splashLog) {
        Log(1, "0.6.2 splash: [Splash] Translate=0 and Log=0 - tru+0x2e68b0 / tru+0x29f1e0 untouched (a later "
               "Translate=1 needs a restart)");
        return;
    }
    // everything the two patches rely on (read only); a mismatch leaves the game untouched
    struct { DWORD at; const char *hex; const char *what; } const facts[] = {
        {kSplashFn,
         "53 57 8bf9 8b87c4000000 33db 395820 0f8683000000 55 56 33ed 8da42400000000 8b87c4000000 8b7024 d9042e 8b480c "
         "83ec0c d95c2408 03f5 d94610 d95c2404 d94608 d91c24 51 d94618 6a00 6a00 6a00 e81ce41200 d94614 50 e813e41200 "
         "d94604 8b1594f0e700 50 6a00 6a00 6a00 51 d91c24 6a00 d9460c 6a00 51 d91c24 52 e8ae88fbff 8b87c4000000 83c301 "
         "83c444 83c51c 3b5820 728a 5e 5d 5f 5b c3",
         "MeleeSplashDamage tru+0x2e68b0: CM in edi, records [CM+0xc4]+0x24 (0x1c each), type +0x0c = argument 13, call "
         "tru+0x29f1e0 at tru+0x2e692d (17 arguments, add esp 0x44)"},
        {0x00716fb5, "8b8904050000 e8f0f8fcff", "event dispatcher case 75: tru+0x2e68b0 on [gameTracker+0x504]"},
        {kAreaFn,
         "55 8bec 83e4f0 d9ee 81ec84000000 d85d0c 53 56 8b7508 33db 57 dfe0 f6c405 0f8af4050000 d94518 8b3d548dd900 3bfb "
         "dcc8 d95c2428 d94548 dcc8 d95c242c 0f84d4050000 3bf7 0f84c1050000",
         "area damage tru+0x29f1e0: ebp frame, source esi = argument 0, instance list [0xd98d54] in edi, ebx = 0, loop "
         "test tru+0x29f224 cmp esi, edi / je tru+0x29f7ed"},
        {kAreaNext, "8b7f08 3bfb 0f852cfaffff", "area damage: next instance tru+0x29f7ed, back to the loop test"},
        {0x0069f82f, "5f 5e 5b 8be5 5d c3", "area damage epilogue (no float result)"},
        {0x0069f584, "8b553c", "area damage: argument 13 (type) -> hit message (static path)"},
        {0x0069f597, "8915e033ed00", "area damage: type -> message 0xed3390 +0x50"},
        {0x0069f4ab, "8b453c", "area damage: argument 13 (type) -> message build tru+0x23c9b0 (player path)"},
        {kHandleFn, "8b4c2404 85c9 740e 8b01 85c0 7408 8b5044 3b5104 7402 33c0 c3",
         "handle resolver tru+0x1b39d0 (= TU inline 0x823e1324..0x823e1348)"},
        {0x006e6843, "8d4648 57 50 e883d1ecff", "main target = handle CM+0x48 (tru+0x2e6840 resolves it the same way)"},
        {0x00777dc0, "a158dbfa00 8a8044120000 c3", "doppelganger byte [[0xfadb58]+0x1244] (larabase f36 tru+0x377dc0)"},
    };
    for (const auto &f : facts)
        if (!HexAt(f.at, f.hex)) {
            Log(0, "0.6.2 splash: %s at 0x%08lx does not match - splash left to the game", f.what, f.at);
            return;
        }
    if (!g_tableOk)
        Log(0, "0.6.2 splash: object table lookup not verified - no pair table (the remap keeps the type; the main "
               "target is still excluded)");
    if (HexAt(0x005bcff9, "8b0dd094db00 52 8b14c1")) g_namesOk = true;
    InitializeCriticalSection(&g_splashLock);
    BYTE call[5] = {0xe8};
    DWORD rel = reinterpret_cast<DWORD>(&SplashCallStub) - (kSplashCall + 5);
    memcpy(call + 1, &rel, 4);
    BYTE jump[8] = {0xe9, 0, 0, 0, 0, 0x90, 0x90, 0x90};
    rel = reinterpret_cast<DWORD>(&AreaLoopStub) - (kAreaLoop + 5);
    memcpy(jump + 1, &rel, 4);
    // the loop test first: with no target noted it does exactly the PC test, so it is safe before the call site
    if (!WriteCode(kAreaLoop, jump, sizeof(jump))) {
        Log(0, "0.6.2 splash: jump at tru+0x29f224 failed - splash left to the game");
        return;
    }
    if (!WriteCode(kSplashCall, call, sizeof(call))) {
        Log(0, "0.6.2 splash: call at tru+0x2e692d failed - splash left to the game (the loop test stays: no target is "
               "ever noted, so it is the PC test)");
        return;
    }
    g_splashHooked = true;
    if (g_splashLog) {
        HANDLE t = CreateThread(nullptr, 0, &SplashFlushThread, nullptr, 0, nullptr);
        if (t) { g_splashFlusher = true; CloseHandle(t); }
    }
    Log(1, "0.6.2 splash: tru+0x2e692d (MeleeSplashDamage -> area damage) and tru+0x29f224 (area loop test) -> plugin - "
           "[Splash] Translate %d (%s), fallback %d, log %d (burst lines every 2 s, max %d%s); read again at run time "
           "at most once per second", g_splashTranslate,
        g_splashTranslate ? "TU 0x823e1220 / 0x8237ae88: main target excluded; doppelganger remap 0x1a -> 0x10, 0x10 -> "
                            "0x16 while [Damage] Translate=1" : "PC splash",
        g_splashFallback, g_splashLog, g_splashMax, g_splashFlusher ? "" : ", no flush thread - lines only at the cap");
}

// ---------------------------------------------------------------- 0.6.3: P1a - notification 33 of the TU's lethal-hit
// handler (T3 of docs Befund-Thrall-Felder-0611.md 3.2; docs Befund-P1a-ThrallTod-0711.md in the main workspace)
// The enemy death check tru+0x220380 (retail 0x822f8c88, TU 0x822f6578; reached from the damage case tru+0x237630 with
// flags bit 0) asks ShouldRegenerate tru+0x27f040 (retail 0x8235f0c8, TU 0x8235ece8) and, when it says yes, calls
// EnterRegenerateDeath tru+0x282780 (= retail 0x8235efd8: query 0x182, then state RegenerateDeath 0x8afa4c). The TU
// replaced that call by: TRScriptUnitManager::PlayNotification(33) (TU 0x8247b0f0 with [0x829ca684] = PC tru+0x37a540
// with [0xfae880], the pair the script event handler TU 0x82473928 / PC tru+0x368a20 uses), then "no switch while the
// enemy is in state Land" (T2 takes over at the landing) and its own switch into RegenerateDeath. Notification 33 goes
// to the level scripts (hall02: 23101 f3 shows hint_17, the finisher hint, once). Only the notification is translated
// here: the Land exception belongs to T2, which needs the companion instance of T4 (TU brain+0x5090, missing on the
// PC), and the TU's own switch feeds the TU's changed RegenerateDeath state (2-byte data, Enter 0x8235dff8) - the PC
// state is retail, so the PC keeps tru+0x282780. [Death] TranslateNotify33=1: the call at tru+0x2203fb goes to
// LethalRegen, which sends 33 first (as the TU, before the query / switch) and then calls tru+0x282780 with the same
// arguments; 0 = the call alone (PC). Read again at run time at most once per second when the site is reached.
const DWORD kLethalFn = 0x00620380;           // retail 0x822f8c88, TU 0x822f6578
const DWORD kLethalRegenCall = 0x006203fb;    // call tru+0x282780 (5 bytes) - patched
const DWORD kEnterRegenDeath = 0x00682780;    // retail 0x8235efd8 (the TU inlined its own variant)
const DWORD kPlayNotification = 0x0077a540;   // TU 0x8247b0f0, thiscall (manager, notification), ret 4
const DWORD kScriptUnitMgr = 0x00fae880;      // TU [0x829ca684]
const DWORD kStateLand = 0x008ae808;          // EnemyState_Land (TU 0x8206a338 "Land", T3's exception)
const int kTuNotifyRegen = 33;                // TU 0x822f6638 li r4, 0x21
typedef DWORD(__cdecl *EnterRegenFn)(BYTE *inst, DWORD a1, DWORD a2);
typedef void(__thiscall *PlayNotificationFn)(void *manager, int notification);
int g_notify33 = 1;                // [Death] TranslateNotify33 (read again at run time, at most once per second)
bool g_deathHooked = false;
DWORD g_deathSwitchTick = 0;
volatile LONG g_deathLines = 0;
const LONG kDeathMaxLines = 1000;

// 0.6.5 (P1d) switches (section below SetupMelee); T3's Land exception (H3b) in LethalRegen uses [Death] TranslateLand
int g_compTranslate = 1;           // [Companion] Translate
int g_compLog = 1;                 // [Companion] Log
int g_notify34 = 1;                // [Death] TranslateNotify34 (H6)
int g_notify38 = 1;                // [Death] TranslateNotify38 (H7 / H8)
int g_regenList = 1;               // [Death] TranslateRegenList (H1)
int g_translateLand = 1;           // [Death] TranslateLand (H3 / H4 / H3b)
int g_meleeInterrupt = 1;          // [Melee] TranslateInterrupt (H5)
bool g_landHooked = false;         // H3 + H4 placed: T2 decides at the landing - only then the Land exception H3b
void P1dReadSwitches();
void CompanionNote(const BYTE *inst, const char *where);

void DeathReadSwitch() {
    if (!g_iniPath[0]) return;
    const DWORD now = GetTickCount();
    if (now - g_deathSwitchTick < 1000) return;
    g_deathSwitchTick = now;
    const int t = GetPrivateProfileIntA("Death", "TranslateNotify33", g_notify33, g_iniPath) ? 1 : 0;
    if (t == g_notify33) return;
    Log(1, "0.6.3 switch: [Death] TranslateNotify33 %d -> %d (read again from TruShadowCombat.ini) - %s", g_notify33, t,
        t ? "notification 33 as the TU 0x822f6578" : "no notification (PC)");
    g_notify33 = t;
}

// called instead of tru+0x282780 from tru+0x2203fb (cdecl, same arguments, the result goes back unchanged)
// 0.6.5 (H3b): with [Death] TranslateLand=1 and T2 placed, an enemy in state Land gets notification 33 but no switch
// (TU 0x822f6644..0x822f6660: 0x822d60d0(inst, 0, "Land") = layer-0 state brain+0x125c named Land -> return 0)
DWORD __cdecl LethalRegen(BYTE *inst, DWORD a1, DWORD a2) {
    DeathReadSwitch();
    P1dReadSwitches();
    CompanionNote(inst, "lethal regenerate hit");
    const bool send = g_notify33 != 0;
    const BYTE *b = reinterpret_cast<const BYTE *>(Rd(inst + 0x2d0));
    const BYTE *brain = b ? reinterpret_cast<const BYTE *>(Rd(b + 0x2ec)) : nullptr;
    const DWORD state = brain ? Rd(brain + 0x125c) : 0;
    const bool landStay = state == kStateLand && g_translateLand && g_landHooked;
    const LONG n = InterlockedIncrement(&g_deathLines);
    if (n <= kDeathMaxLines) {
        char who[96];
        Describe(inst, who, sizeof(who));
        Log(1, "0.6.3 death: %s lethal hit, ShouldRegenerate yes (LP %.0f, state %s): %s; then %s", who,
            brain ? RdFloat(brain + 0x2c64) : 0.0f, state == kStateLand ? "Land" : state ? "not Land" : "none",
            send ? "notification 33 sent (TU 0x822f6638)" : "no notification ([Death] TranslateNotify33=0)",
            landStay ? "no switch in Land, return 0 (0.6.5 H3b, TU 0x822f6654; T2 decides at the landing)"
            : state == kStateLand ? (g_landHooked ? "RegenerateDeath tru+0x282780 (PC; [Death] TranslateLand=0)"
                                                  : "RegenerateDeath tru+0x282780 (PC; T2 not placed)")
                                  : "RegenerateDeath tru+0x282780 (PC)");
        if (n == kDeathMaxLines) Log(1, "0.6.3 death: %ld lines - no more", kDeathMaxLines);
    }
    if (send)
        reinterpret_cast<PlayNotificationFn>(kPlayNotification)(
            reinterpret_cast<void *>(Rd(reinterpret_cast<const void *>(kScriptUnitMgr))), kTuNotifyRegen);
    if (landStay) return 0;
    return reinterpret_cast<EnterRegenFn>(kEnterRegenDeath)(inst, a1, a2);
}

void SetupDeath() {
    struct { DWORD at; const char *hex; const char *what; } const facts[] = {
        {kLethalFn,
         "56 8b742408 8b86d0020000 85c0 0f84a3000000 8b08 8b89ec020000 85c9 0f8493000000 8b510c d1ea f6d2 f6c201 "
         "0f8483000000 85c0 7408 8b00 8b80ec020000 d980642c0000 dc1db8148400 dfe0 f6c441 7a64 8b4c2418 53 8b5c2418 57 "
         "8b7c2424 57 51 53 56 e857ec0500 83c410 84c0 7417 8b542418 8b442414 52 50 56 e880230600 83c40c 5f 5b 5e c3 "
         "6a01 53 57 56 e82f37ffff",
         "death check tru+0x220380: LP <= 0 -> ShouldRegenerate tru+0x27f040 -> EnterRegenerateDeath tru+0x282780 "
         "(call at tru+0x2203fb), else death kind tru+0x213b40"},
        {kEnterRegenDeath, "55 8bec 83e4f0 83ec28 56 8b7508 57 8b7d0c 6882010000 56 e8540ff3ff 83c408 85c0 7563",
         "EnterRegenerateDeath tru+0x282780 (cdecl inst, vector, byte; query 0x182 first)"},
        {0x006827d1, "684cfa8a00", "EnterRegenerateDeath: state RegenerateDeath 0x8afa4c"},
        {kPlayNotification,
         "56 57 8b7c240c be08acdb00 eb03 8d4900 80be3cffffff02 7510 8b06 57 8d4c2410 89442410 e8e7300200 81c6d8000000 "
         "81fe08c7db00 7cd9 5f 5e c20400",
         "PlayNotification tru+0x37a540 (stream table state 2 -> unit event, ret 4)"},
        {0x00768a20, "8b442408 6683780220 7513 8b4004 85c0 7e0c 8b0d80e8fa00 50 e8021b0100 c3",
         "script event handler tru+0x368a20: PlayNotification([0xfae880], n)"},
        {kStateLand, "5c8c8500 06000000", "EnemyState_Land 0x8ae808 (vtable 0x858c5c)"},
    };
    for (const auto &f : facts)
        if (!HexAt(f.at, f.hex)) {
            Log(0, "0.6.3 death: %s at 0x%08lx does not match - lethal hit left to the game (no notification 33)", f.what,
                f.at);
            return;
        }
    if (HexAt(0x005bcff9, "8b0dd094db00 52 8b14c1")) g_namesOk = true;
    if (!WriteCall(kLethalRegenCall, reinterpret_cast<const void *>(&LethalRegen))) {
        Log(0, "0.6.3 death: call at tru+0x2203fb failed - lethal hit left to the game (no notification 33)");
        return;
    }
    g_deathHooked = true;
    Log(1, "0.6.3 death: tru+0x2203fb (death check tru+0x220380 -> EnterRegenerateDeath) -> plugin - [Death] "
           "TranslateNotify33 %d (%s); read again at run time at most once per second. T2 (Land: notification 33 + "
           "RegenerateDeath) and the Land exception: 0.6.5 [Death] TranslateLand (line \"0.6.5 land\")", g_notify33,
        g_notify33 ? "TU 0x822f6578: notification 33 before the switch" : "PC: no notification");
}

// ---------------------------------------------------------------- 0.6.4: P1b - the TU's changes to the enemy state
// MeleeAttack (T-M1 / T-M2 of docs Befund-Thrall-MeleeAttack-Freeze-0711.md section 4; docs Befund-P1b-MeleeAttack-0711.md
// in the main workspace). State object 0x8aea00 "MeleeAttack", vtable 0x85912c (retail 0x82779a74 -> vtable 0x8206d160,
// TU 0x82779cf4 -> vtable 0x8206d450). State data = (brain+0x1273 + ([brain+0x18d4+4i] + 2i) * 0x19c) & ~0xf on all
// three exes (TU: brain+0x1254 + 0x680 / +0x1f), record = [data+0x50]; brain = [[inst+0x2d0]]+0x2ec.
// T-M1 message slot 10 (PC tru+0x266350, retail 0x82331c28, TU 0x82330d40): messages 0x15 / 0x8a (anim end / anim kind
//      8) and 0xbe set data+0xa4 = 2 (the update tru+0x265f10 then leaves the state). Retail = PC: 0x15 / 0x8a always,
//      0xbe unless the data pointer points at the instance itself. TU 0x82331164..0x8233117c: all three only when the
//      message data pointer is 0. Translation: jump table tru+0x26672c entries 0 (cases 0x15 / 0x8a -> tru+0x2663c7) and
//      5 (case 0xbe -> tru+0x2663b8) go to MeleeMsgStub: data != 0 -> the switch default tru+0x266721 (return 0, as the
//      TU's 0x82331578 li r3, 0), data == 0 -> tru+0x2663c7 (+0xa4 = 2 and the PC code behind it, unchanged).
// T-M2 Enter slot 7 (PC tru+0x25c7b0, retail 0x82330a88, TU 0x8232fb48): after "record+8 bit 24 -> brain+8 |= 0x800000"
//      (PC tru+0x25c9da / tru+0x2224c0, retail 0x82330ca4 / 0x82330ca8) the TU added (0x8232fd6c..0x8232fd8c)
//      "if (!(record+8 & 4)) brain+0xc |= 1" - the same bit message 0xcb sets (PC tru+0x26670e, TU 0x8233155c).
//      Translation: tru+0x25c9ea (mov eax, [esi+0x50]; movsx ecx, word [eax+0x1f8], 10 bytes) jumps to MeleeEnterStub,
//      which does the TU test, then the two moved instructions, back to tru+0x25c9f4.
// T-M3 (interruption slot 13, TU 0x82330830: Vaulted, and RegenerateDeath only with the companion instance 0x822da918)
//      is NOT translated here: the RegenerateDeath clause needs T4 (the TU's companion instance, missing on the PC) -
//      0.6.5 translates it with the companion lookup (H5, [Melee] TranslateInterrupt, section below).
// [Melee] Translate=1 (default) places both at the start; 0 = nothing patched (a change needs a restart).
const DWORD kMeleeEnterFn = 0x0065c7b0;     // slot 7, retail 0x82330a88, TU 0x8232fb48
const DWORD kMeleeEnterSite = 0x0065c9ea;   // 10 bytes moved into MeleeEnterStub
const DWORD kMeleeEnterBack = 0x0065c9f4;   // push ecx (record+0x1f8) / push ebx / call tru+0x218ee0
const DWORD kMeleeMsgFn = 0x00666350;       // slot 10, retail 0x82331c28, TU 0x82330d40
const DWORD kMeleeByteTable = 0x00666764;   // byte index per (message - 0x15), 0xe3 entries
const DWORD kMeleeJumpTable = 0x0066672c;   // 14 targets
const DWORD kMeleeCaseSet = 0x006663c7;     // +0xa4 = 2 (cases 0x15 / 0x8a; 0xbe after its self check)
const DWORD kMeleeCaseBe = 0x006663b8;      // case 0xbe: self check
const DWORD kMeleeDefault = 0x00666721;     // switch default: return 0
int g_meleeTranslate = 1;                   // [Melee] Translate (0.6.4, start only)
bool g_meleeMsgHooked = false, g_meleeEnterHooked = false;
DWORD g_meleeSetTo = kMeleeCaseSet, g_meleeDefaultTo = kMeleeDefault, g_meleeEnterBackTo = kMeleeEnterBack;
volatile LONG g_meleeMsgLines = 0, g_meleeEnterLines = 0;
const LONG kMeleeMaxLines = 300;

// T-M1: called on the skip path only (message 0x15 / 0x8a / 0xbe with a data pointer) - log line, nothing else
void __cdecl MeleeMsgSkipped(BYTE *inst, DWORD message, DWORD data) {
    const LONG n = InterlockedIncrement(&g_meleeMsgLines);
    if (n > kMeleeMaxLines) return;
    char who[96];
    Describe(inst, who, sizeof(who));
    const bool self = message == 0xbe && Rd(reinterpret_cast<const void *>(data)) == reinterpret_cast<DWORD>(inst);
    Log(1, "0.6.4 melee: %s MeleeAttack message 0x%02lx with data 0x%08lx ignored as the TU 0x82331164%s", who, message,
        data, self ? " (data = the instance: the PC ignores it too)" : " (the PC would set +0xa4 = 2 and end the attack)");
    if (n == kMeleeMaxLines) Log(1, "0.6.4 melee: %ld message lines - no more", kMeleeMaxLines);
}

// T-M2: TU 0x8232fd80..0x8232fd8c (the stub has tested record+8 bit 2 = 0)
void __cdecl MeleeEnterSet(BYTE *inst, BYTE *brain) {
    DWORD *flags = reinterpret_cast<DWORD *>(brain + 0xc);
    const DWORD before = *flags;
    *flags = before | 1;
    const LONG n = InterlockedIncrement(&g_meleeEnterLines);
    if (n > kMeleeMaxLines) return;
    char who[96];
    Describe(inst, who, sizeof(who));
    Log(1, "0.6.4 melee: %s MeleeAttack Enter, record+8 bit 2 clear -> brain+0xc |= 1 as the TU 0x8232fd8c (bit was %lu)",
        who, before & 1);
    if (n == kMeleeMaxLines) Log(1, "0.6.4 melee: %ld Enter lines - no more", kMeleeMaxLines);
}

// jump table entries 0 / 5 of the message switch: ebp frame of tru+0x266350 ([ebp+8] inst, [ebp+0x10] message,
// [ebp+0x14] data), ecx = inst, esi = state data, edi = record, ebx = brain; eax / edx are free (index registers)
__declspec(naked) void MeleeMsgStub() {
    __asm {
        cmp dword ptr [ebp + 0x14], 0
        jne melee_skip
        jmp dword ptr [g_meleeSetTo]
    melee_skip:
        push dword ptr [ebp + 0x14]
        push dword ptr [ebp + 0x10]
        push dword ptr [ebp + 8]
        call MeleeMsgSkipped
        add esp, 12
        jmp dword ptr [g_meleeDefaultTo]
    }
}

// jumped to from tru+0x25c9ea: esi = state data, edi = brain, ebx = inst; eax / ecx / edx are loaded again by the moved
// instructions and by tru+0x25c9fb, flags are not live
__declspec(naked) void MeleeEnterStub() {
    __asm {
        mov eax, dword ptr [esi + 0x50]
        test dword ptr [eax + 8], 4
        jne enter_moved
        push edi
        push ebx
        call MeleeEnterSet
        add esp, 8
    enter_moved:
        mov eax, dword ptr [esi + 0x50]
        movsx ecx, word ptr [eax + 0x1f8]
        jmp dword ptr [g_meleeEnterBackTo]
    }
}

void SetupMelee() {
    if (!g_meleeTranslate) {
        Log(1, "0.6.4 melee: [Melee] Translate=0 - MeleeAttack tru+0x25c7b0 / tru+0x266350 untouched (PC = retail)");
        return;
    }
    struct { DWORD at; const char *hex; const char *what; } const facts[] = {
        {0x00859148, "b0c76500 b0877900 105f6600 50636600", "MeleeAttack vtable 0x85912c slots 7 / 8 / 9 / 10"},
        {0x008aea00, "2c918500", "state object MeleeAttack 0x8aea00 (vtable 0x85912c)"},
        {kMeleeMsgFn,
         "55 8bec 83e4f0 83ec74 8b4d08 8b81d0020000 85c0 53 56 57 894c2418 7504 33db eb08 8b00 8b98ec020000 8b450c "
         "8b9483d4180000 8d0442 69c09c010000 8db41873120000 8b4510 83e6f0 8b7e50 83c0eb 3de2000000 0f8777030000 "
         "0fb69064676600 ff24952c676600",
         "message slot tru+0x266350: brain ebx, state data esi, record edi, switch (message - 0x15) <= 0xe2"},
        {kMeleeCaseBe, "8b4514 85c0 7408 3b08 0f845a030000 c786a400000002000000",
         "case 0xbe tru+0x2663b8: self check, then tru+0x2663c7 +0xa4 = 2"},
        {kMeleeDefault, "5f 5e 32c0 5b 8be5 5d c21000", "switch default tru+0x266721: return 0"},
        {kMeleeJumpTable, "c7636600", "jump table entry 0 -> tru+0x2663c7"},
        {kMeleeJumpTable + 5 * 4, "b8636600", "jump table entry 5 -> tru+0x2663b8"},
        {0x0066670e, "834b0c01", "case 0xcb: brain+0xc |= 1 (TU 0x8233155c)"},
        {kMeleeEnterFn,
         "55 8bec 83e4f0 81ec84000000 53 8b5d08 8b83d0020000 85c0 56 57 895c241c 7504 33ff eb08 8b00 8bb8ec020000 "
         "8b450c 8b8c87d4180000 8d1441 8b4514 69d29c010000 8db43a73120000 83e6f0",
         "Enter slot tru+0x25c7b0: inst ebx, brain edi, state data esi"},
        {0x0065c9da, "8b5650 f6420b01 7407 8bcf e8d65afcff 8b4650 0fbf88f8010000 51 53 e8e5c4fbff",
         "Enter tru+0x25c9da: record+8 bit 24 -> tru+0x2224c0(brain), then record+0x1f8 -> tru+0x218ee0"},
        {0x006224c0, "81490800008000 c3", "tru+0x2224c0: brain+8 |= 0x800000 (retail 0x82330ca8 stw 8(r27))"},
    };
    for (const auto &f : facts)
        if (!HexAt(f.at, f.hex)) {
            Log(0, "0.6.4 melee: %s at 0x%08lx does not match - MeleeAttack left to the game (PC)", f.what, f.at);
            return;
        }
    // index 0 must belong to exactly the cases 0x15 / 0x8a, index 5 to exactly 0xbe (tools/pe_switch.py; same case
    // sets in the retail / TU tables 0x82331cbc / 0x82330dd8)
    const BYTE *bt = reinterpret_cast<const BYTE *>(kMeleeByteTable);
    int odd = 0;
    for (int m = 0x15; m <= 0xf7; ++m) {
        const BYTE k = bt[m - 0x15];
        const bool want0 = m == 0x15 || m == 0x8a, want5 = m == 0xbe;
        if ((k == 0) != want0 || (k == 5) != want5) ++odd;
    }
    if (odd) {
        Log(0, "0.6.4 melee: byte table tru+0x266764 differs in %d entries - MeleeAttack left to the game (PC)", odd);
        return;
    }
    if (HexAt(0x005bcff9, "8b0dd094db00 52 8b14c1")) g_namesOk = true;
    const DWORD stub = reinterpret_cast<DWORD>(&MeleeMsgStub);
    if (WriteCode(kMeleeJumpTable, &stub, 4) && WriteCode(kMeleeJumpTable + 5 * 4, &stub, 4)) {
        g_meleeMsgHooked = true;
    } else {
        const DWORD set = kMeleeCaseSet, be = kMeleeCaseBe;
        WriteCode(kMeleeJumpTable, &set, 4);
        WriteCode(kMeleeJumpTable + 5 * 4, &be, 4);
        Log(0, "0.6.4 melee: jump table tru+0x26672c could not be written - T-M1 off (PC)");
    }
    BYTE j[10] = {0xe9, 0, 0, 0, 0, 0x90, 0x90, 0x90, 0x90, 0x90};
    const DWORD rel = reinterpret_cast<DWORD>(&MeleeEnterStub) - (kMeleeEnterSite + 5);
    memcpy(j + 1, &rel, 4);
    if (WriteCode(kMeleeEnterSite, j, sizeof(j))) g_meleeEnterHooked = true;
    else Log(0, "0.6.4 melee: jump at tru+0x25c9ea failed - T-M2 off (PC)");
    Log(1, "0.6.4 melee: [Melee] Translate 1 - T-M1 %s (messages 0x15 / 0x8a / 0xbe end MeleeAttack only without a data "
           "pointer, TU 0x82330d40), T-M2 %s (Enter: record+8 bit 2 clear -> brain+0xc |= 1, TU 0x8232fb48); T-M3 "
           "(interruption by Vaulted / RegenerateDeath, TU 0x82330830): 0.6.5 [Melee] TranslateInterrupt",
        g_meleeMsgHooked ? "on" : "OFF", g_meleeEnterHooked ? "on" : "OFF");
}

// ---------------------------------------------------------------- 0.6.5: P1d - the thrall's companion (T4) and what
// the TU hangs on it (docs Befund-P1d-Begleiter-0711.md section 3 in the main workspace; T1 / T2 of
// Befund-Thrall-Felder-0611.md 3.2, T-M3 of Befund-P1b-MeleeAttack-0711.md, notifications 34 / 38 of
// Befund-Hall02-Tutorial-Stufe2-0711.md). TU state objects by name / offset: RegenerateDeath 0x8277a7b8 = PC 0x8afa4c,
// Death 0x82779bf8 = 0x8ae904, Vaulted 0x82779bb0 = 0x8ae8bc, Land 0x82779afc = 0x8ae808.
// H0 CompanionData(inst): the TU builds a companion instance in the enemy init (TU-only 0x822da800, called from
//    0x822da970 = PC tru+0x23c190 after the brain exists): the first id of the thrall object's child list
//    [[inst+0x10]+0x2c] (u16, 0-terminated) whose object table entry (0xdb7400 = TU 0x82979280, 0xcc entries of 0x24:
//    +8 object, +0xc id, +0xe state == 2) has [o+0x5c] != 0, [o+0x60] != 0 and u16 [[o+0x5c]+2] == 0x3d -> instance
//    (0x82272998 = PC tru+0x1bd270), handle brain+0x5090 / +0x5094. Its readers (0x822da918) only ask "is it there" and
//    take its data [comp+0x50] = [o+0x5c] (PC tru+0x1ba84c / tru+0x1ba857: instance +0x50 = object +0x5c). The PC loads
//    the same children (870 viking / tutorial viking, 932 yeti, 944 armoured yeti) but makes no instance; its brain
//    (0x5040 bytes) has no handle. CompanionData answers 0x822da918's question from the object table on every call and
//    keeps nothing (no lifetime): [o+0x60] is the loaded object's name pointer on the PC (tru+0x1bf0fb), set for every
//    loaded object. Not rebuilt: the instance itself (TU: bit 0x20 of +0x14 with the thrall at death / removal), its
//    serial check and the TU's "no instance" cases (pool full).
// H6 RegenerateDeath slot 12 = Exit (vtable 0x85b104 = tru+0x27eeb0, retail 0x8235ea38): TU 0x8235e338 = the same body,
//    then PlayNotification(34) (0x8235e384). No companion involved.
// H7 / H8 RegenerateDeath / Regenerate slot 10 = messages (vtable 0x85b0fc = tru+0x282490, 0x85b15c = tru+0x282680; TU
//    0x8235e3a8 / 0x8235e998, TU-new first block 0x8235e3ec..0x8235e470 / 0x8235e9b8..0x8235ea3c): message 0x11c (hit)
//    with data, a companion and data+0x50 == 0x10 or (data+0x64 == 1 and data+0x50 == 1) -> death switch
//    0x823258c8(inst, 1, 0, 1, kind 7, 0, v1 = (0, 0, 1, 0) [0x8207db00]) = tru+0x241650(inst, &v, 1, 0, 1, 7, 0), then
//    PlayNotification(38), return 1; else the PC handler (the TU's other differences in these slots - 0x15 / 0x8a with a
//    companion, the sound 0x82399b48 - are a later package).
// H1 ShouldRegenerate (T1, TU 0x8235ece8 / PC tru+0x27f040 = retail): after the same preconditions (brain, tune record
//    = first node of the list [brain+0x168] with +0x64 (tru+0x214610 = TU 0x822d3d38), not both anim words +0x22 /
//    +0x26 = 0xffff) the TU asks the companion's regeneration list (+0x40 count, +0x44 entries of 0xc {type, -1 = any;
//    subtype, 0 = any; flag bit 0 == the flag byte}) before the tune list (+0x64 / +0x68). The three PC calls - tru+0x2203e4
//    (death check), tru+0x2824b9 (RegenerateDeath slot 10), tru+0x2826d3 (Regenerate slot 10) = the TU's callers
//    0x822f6578 / 0x8235e3a8 / 0x8235e998 - go to RegenListHook; the function itself is not patched (TruMenu byte-checks
//    its head and calls it for its kill prediction). Data (DTP of the three extensions): 1 entry {2 Heavy, 0, 0}.
// H3 T2 Land slot 9 (tru+0x25afe0, TU 0x82328aa0): LP <= 0 (tru+0x220350) and a companion whose data byte +0x18 is 0 ->
//    notification 33 (0x82328d4c) and RegenerateDeath with the 2-byte data {([state data+0x30] >> 1) & 1, 1} (TU
//    0x8230c050 by name = PC tru+0x23d4a0(inst, 0x8afa4c, data, 0), the helper the Getup branch beside it uses; the PC's
//    retail RegenerateDeath has the empty data copier tru+0x3987b0 in slot 3 and an Enter that reads no data), then the
//    function returns; else LandDeath (PC = TU without companion). tru+0x25b181 (6 bytes) jumps to LandStub. The 33
//    here follows [Death] TranslateNotify33 as well (33 / 34 / 38 belong together for the hall02 hint).
// H4 Land slot 13 (tru+0x241d30, vtable 0x858c90; TU-only 0x82329060): where the PC answers -1, the TU answers 6 for
//    RegenerateDeath and Death when the enemy has a companion. Without it the state machine (tru+0x271080: current
//    state's slot 13 -1 = refused) would refuse H3's switch, so H3 is placed only together with H4.
// H3b T3's Land exception (TU 0x822f6654): in LethalRegen (0.6.3 section) - 33, then no switch, return 0.
// H5 T-M3 MeleeAttack slot 13 (tru+0x242f40, vtable 0x859160; TU 0x82330830): where the PC answers -1, the TU also lets
//    Vaulted and - with a companion - RegenerateDeath interrupt: tru+0x270400(next) (= next ? [next+4] : 0, the same
//    tail the PC uses for its own states, TU 0x82330920..0x8233092c).
// Switches (start + again at run time at most once per second, from the hooks): [Companion] Translate (0 = never a
// companion = the TU without one = PC for H1 / H3 / H4 / H7 / H8 / RegenerateDeath part of H5), [Companion] Log,
// [Death] TranslateNotify34 / TranslateNotify38 / TranslateRegenList / TranslateLand, [Melee] TranslateInterrupt.
// The hooks are placed at the start whenever their byte checks pass; with a switch at 0 a hook runs exactly the PC code.
const DWORD kStateRegenDeath = 0x008afa4c;     // RegenerateDeath (vtable 0x85b0d4)
const DWORD kStateDeath = 0x008ae904;          // Death (vtable 0x858edc)
const DWORD kStateVaulted = 0x008ae8bc;        // Vaulted (vtable 0x858e14)
const DWORD kRdExitSlot = 0x0085b104, kRdExitFn = 0x0067eeb0;        // RegenerateDeath slot 12 (Exit)
const DWORD kRdMsgSlot = 0x0085b0fc, kRdMsgFn = 0x00682490;          // RegenerateDeath slot 10 (messages)
const DWORD kRgMsgSlot = 0x0085b15c, kRgMsgFn = 0x00682680;          // Regenerate slot 10 (messages)
const DWORD kLandIntSlot = 0x00858c90, kLandIntFn = 0x00641d30;      // Land slot 13 (interruption)
const DWORD kMeleeIntSlot = 0x00859160, kMeleeIntFn = 0x00642f40;    // MeleeAttack slot 13 (interruption)
const DWORD kShouldRegen = 0x0067f040;         // cdecl (inst, type, subtype, flag byte) -> al
const DWORD kRegenCalls[3] = {0x006203e4, 0x006824b9, 0x006826d3};
const char *const kRegenCallWhere[3] = {"death check tru+0x2203e4", "RegenerateDeath slot 10 tru+0x2824b9",
                                        "Regenerate slot 10 tru+0x2826d3"};
const DWORD kLandSite = 0x0065b181;            // mov eax, [edi+0x2d0] (6 bytes) - patched
const DWORD kLandBack = 0x0065b187;            // the PC LandDeath branch after that instruction
const DWORD kLandEnd = 0x0065b1af;             // pop edi; pop esi; pop ebx; mov esp, ebp; pop ebp; ret 8
const DWORD kSwitchWithData = 0x0063d4a0;      // cdecl (inst, state, 2-byte data *, int) (TU 0x8230bf78)
const DWORD kStateValue = 0x00670400;          // cdecl (state) -> state ? [state+4] : 0
const WORD kCompanionType = 0x3d;              // TU 0x822da8a4 cmplwi r11, 0x3d
const int kTuNotifyExit = 34;                  // TU 0x8235e384 li r4, 0x22
const int kTuNotifyFinisher = 38;              // TU 0x8235e45c / 0x8235ea28 li r4, 0x26
const DWORD kTuFinisherKind = 7;               // TU 0x8235e43c li r7, 7
typedef DWORD(__thiscall *StateSlotFn)(void *state, BYTE *inst, DWORD layer, DWORD a3, DWORD a4);
typedef DWORD(__cdecl *ShouldRegenFn)(BYTE *inst, DWORD type, DWORD subtype, DWORD flag);
typedef DWORD(__cdecl *SwitchWithDataFn)(BYTE *inst, DWORD state, const BYTE *data, DWORD flag);
typedef DWORD(__cdecl *StateValueFn)(DWORD state);
bool g_compOk = false;             // object table + loader facts verified (else CompanionData answers 0)
bool g_h6 = false, g_h7 = false, g_h8 = false, g_h4 = false, g_h5 = false;
int g_h1 = 0;                      // H1 call sites placed (0 or 3)
DWORD g_p1dSwitchTick = 0;
DWORD g_landBackTo = kLandBack, g_landEndTo = kLandEnd;
volatile LONG g_compLines = 0, g_p1dLines = 0;
const LONG kCompMaxLines = 400, kP1dMaxLines = 1500;

struct P1dKey { const char *section, *key; int *value; const char *on, *off, *ver; };   // ver 0 = "0.6.5"
const P1dKey kP1dKeys[] = {
    {"Companion", "Translate", &g_compTranslate, "companion lookup as the TU 0x822da918",
     "no companion (TU without one = PC)"},
    {"Companion", "Log", &g_compLog, "one line per new thrall", "no companion lines"},
    {"Death", "TranslateNotify34", &g_notify34, "notification 34 at the RegenerateDeath exit (TU 0x8235e338)",
     "no notification 34 (PC)"},
    {"Death", "TranslateNotify38", &g_notify38, "finisher block + notification 38 (TU 0x8235e3a8 / 0x8235e998)",
     "PC message handlers"},
    {"Death", "TranslateRegenList", &g_regenList, "companion regeneration list first (TU 0x8235ece8)",
     "PC ShouldRegenerate"},
    {"Death", "TranslateLand", &g_translateLand, "T2 / Land slot 13 / Land exception as the TU", "PC Land"},
    {"Melee", "TranslateInterrupt", &g_meleeInterrupt, "T-M3 as the TU 0x82330830", "PC MeleeAttack slot 13"},
    // 0.6.6 (N4c)
    {"Death", "TranslateT5", &g_translateT5, "T5: lethal hit, companion, no regeneration -> death kind 7 (TU 0x823038d8)",
     "PC hit reaction", "0.6.6"},
    {"Death", "TranslateVaulted", &g_translateVaulted,
     "Vaulted Enter + step chain as the TU 0x8232b630 (step table only from fixed extension data)", "PC Vaulted",
     "0.6.6"},
    {"Death", "TranslateVaultedClock", &g_translateClock,
     "Vaulted clock as the TU (5 s without slow motion: Enter 0x8232b698, enemy update 0x822db1e8 / 0x822db4e0)",
     "no clock (PC)", "0.6.6"},
    // 0.6.7 (K-1)
    {"Hit", "Translate", &g_hitTranslate,
     "hit structures from the companion's hit records first (TU 0x82301dc0: damage types 18..27 and the extension's "
     "0 / 1 / 2 / 4)", "PC selector tru+0x2159a0 (types 0..16 only)", "0.6.7"},
    {"Hit", "TranslateKnockback", &g_hitKnock, "knockback force per damage type from the hit record +0x40 (TU 0x822f77e4)",
     "fixed 3.0 (PC)", "0.6.7"},
    {"Hit", "Log", &g_hitLog, "one line per hit decision / knockback / gated impulse", "no hit lines", "0.6.7"},
    // 0.6.8 (K-1b)
    {"Hit", "TranslateImpulseGate", &g_hitImpulseGate,
     "no impulse 0x91 from Lara's contact hit to targets with flag 0x400000 (TU 0x823e1870)",
     "impulse 0x91 to every target (PC)", "0.6.8"},
    // 0.6.9 (K-8 / melee kill, log only)
    {"Death", "Log", &g_deathLog, "one line per chunkdoll build of the Death state and per death switch",
     "no chunkdoll / death switch lines", "0.6.9"},
    // 0.6.10 (K-8b)
    {"Hit", "TranslateHitSpeed", &g_hitSpeed,
     "Lara's contact hit: msg+0x44 / +0x48 = (int) A+0x10 / A+0x14 (TU 0x823e169c, knockback speed)",
     "msg+0x44 / +0x48 = 0 / 0 (PC)", "0.6.10"},
};

void P1dReadSwitches() {
    if (!g_iniPath[0]) return;
    const DWORD now = GetTickCount();
    if (now - g_p1dSwitchTick < 1000) return;
    g_p1dSwitchTick = now;
    for (const auto &k : kP1dKeys) {
        const int v = GetPrivateProfileIntA(k.section, k.key, *k.value, g_iniPath) ? 1 : 0;
        if (v == *k.value) continue;
        Log(1, "%s switch: [%s] %s %d -> %d (read again from TruShadowCombat.ini) - %s", k.ver ? k.ver : "0.6.5",
            k.section, k.key, *k.value, v, v ? k.on : k.off);
        *k.value = v;
    }
}

bool P1dLine() {
    const LONG n = InterlockedIncrement(&g_p1dLines);
    if (n > kP1dMaxLines) return false;
    if (n == kP1dMaxLines) Log(1, "0.6.5: %ld event lines - this is the last one", kP1dMaxLines);
    return true;
}

void P1dNotify(int notification) {
    reinterpret_cast<PlayNotificationFn>(kPlayNotification)(
        reinterpret_cast<void *>(Rd(reinterpret_cast<const void *>(kScriptUnitMgr))), notification);
}

BYTE RdByte(const void *p) {
    __try {
        return p ? *reinterpret_cast<const volatile BYTE *>(p) : 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
}

const BYTE *P1dBrain(const BYTE *inst) {
    const BYTE *h = reinterpret_cast<const BYTE *>(Rd(inst ? inst + 0x2d0 : nullptr));
    const BYTE *b = h ? reinterpret_cast<const BYTE *>(Rd(h)) : nullptr;
    return b ? reinterpret_cast<const BYTE *>(Rd(b + 0x2ec)) : nullptr;
}

// name of an object id (the name table [0xdb94d0] as Describe), "?" without
void ObjName(DWORD id, char *out, size_t size) {
    strcpy_s(out, size, "?");
    if (!g_namesOk || !id) return;
    const BYTE *table = reinterpret_cast<const BYTE *>(Rd(reinterpret_cast<const void *>(kObjNames)));
    const DWORD count = table ? Rd(table) : 0;
    const char *s = (table && count < 8192 && id <= count) ? reinterpret_cast<const char *>(Rd(table + id * 8)) : nullptr;
    __try {
        if (s) {
            size_t i = 0;
            for (; s[i] && i + 1 < size; ++i) out[i] = s[i];
            out[i] = 0;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        strcpy_s(out, size, "?");
    }
}

enum CompWhy { kCwFound, kCwOff, kCwNoFacts, kCwNoInst, kCwNoBrain, kCwNoObject, kCwNoList, kCwNone, kCwFault };
const char *const kCompWhy[] = {"found", "[Companion] Translate=0", "object table / loader not verified", "no instance",
                                "no brain", "no object", "no child list", "no child of data type 0x3d loaded",
                                "exception while reading"};

void Append(char *out, size_t size, const char *fmt, ...) {
    if (!out || !size) return;
    const size_t used = strlen(out);
    if (used + 1 >= size) return;
    va_list ap;
    va_start(ap, fmt);
    _vsnprintf_s(out + used, size - used, _TRUNCATE, fmt, ap);
    va_end(ap);
}

// TU 0x822da800 (search) + 0x822da918 (data): the companion's data [o+0x5c] or 0. detail (optional): every child id
// with the reason it was skipped. Read only, SEH-guarded, nothing kept.
const BYTE *CompanionScan(const BYTE *inst, int *why, char *detail, size_t size, DWORD *companionId) {
    if (detail && size) detail[0] = 0;
    if (companionId) *companionId = 0;
    if (!g_compTranslate) { *why = kCwOff; return nullptr; }
    if (!g_compOk) { *why = kCwNoFacts; return nullptr; }
    if (!inst) { *why = kCwNoInst; return nullptr; }
    __try {
        if (!P1dBrain(inst)) { *why = kCwNoBrain; return nullptr; }      // the TU builds it in the enemy init only
        const BYTE *obj = *reinterpret_cast<const BYTE *const *>(inst + 0x10);
        if (!obj) { *why = kCwNoObject; return nullptr; }
        const WORD *ids = *reinterpret_cast<const WORD *const *>(obj + 0x2c);
        if (!ids || !ids[0]) { *why = kCwNoList; return nullptr; }
        for (int n = 0; ids[n] && n < 64; ++n) {
            const WORD id = ids[n];
            // TU 0x822da848..0x822da878: the first entry with state 2 and this id
            const BYTE *entry = nullptr;
            for (int i = 0; i < kObjectCount && !entry; ++i) {
                const BYTE *e = reinterpret_cast<const BYTE *>(kObjectTable + i * 0x24);
                if (*reinterpret_cast<const WORD *>(e + 0xe) == 2 && *reinterpret_cast<const WORD *>(e + 0xc) == id)
                    entry = e;
            }
            if (!entry) { Append(detail, size, "%s%u not loaded", n ? ", " : "", id); continue; }
            const BYTE *o = *reinterpret_cast<const BYTE *const *>(entry + 8);
            const BYTE *data = o ? *reinterpret_cast<const BYTE *const *>(o + 0x5c) : nullptr;
            if (!o || !data || !*reinterpret_cast<const DWORD *>(o + 0x60)) {
                Append(detail, size, "%s%u %s", n ? ", " : "", id, !o ? "no object" : !data ? "+0x5c = 0" : "+0x60 = 0");
                continue;
            }
            const WORD type = *reinterpret_cast<const WORD *>(data + 2);
            if (type != kCompanionType) { Append(detail, size, "%s%u type 0x%x", n ? ", " : "", id, type); continue; }
            Append(detail, size, "%s%u type 0x3d = companion", n ? ", " : "", id);
            if (companionId) *companionId = id;
            *why = kCwFound;
            return data;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        *why = kCwFault;
        return nullptr;
    }
    *why = kCwNone;
    return nullptr;
}

const BYTE *CompanionData(const BYTE *inst) {
    int why = 0;
    return CompanionScan(inst, &why, nullptr, 0, nullptr);
}

// [Companion] Log: one line per thrall instance (instance + serial +0x44) the first time a 0.6.5 hook sees it - game
// thread only (state machine / damage path)
struct CompSeen { const BYTE *inst; DWORD serial; };
CompSeen g_compSeen[256];
int g_compSeenNext = 0;

void CompanionNote(const BYTE *inst, const char *where) {
    if (!g_compLog || !inst) return;
    const DWORD serial = Rd(inst + 0x44);
    for (const auto &s : g_compSeen)
        if (s.inst == inst && s.serial == serial) return;
    g_compSeen[g_compSeenNext].inst = inst;
    g_compSeen[g_compSeenNext].serial = serial;
    g_compSeenNext = (g_compSeenNext + 1) & 255;
    const LONG n = InterlockedIncrement(&g_compLines);
    if (n > kCompMaxLines) return;
    char who[96], detail[320], name[64];
    int why = 0;
    DWORD id = 0;
    Describe(inst, who, sizeof(who));
    const BYTE *data = CompanionScan(inst, &why, detail, sizeof(detail), &id);
    if (data) {
        ObjName(id, name, sizeof(name));
        const DWORD count = Rd(data + 0x40);
        const BYTE *list = reinterpret_cast<const BYTE *>(Rd(data + 0x44));
        Log(1, "0.6.5 companion: %s serial 0x%08lx (first seen: %s) - companion object %lu %s, data 0x%08lx (type 0x3d), "
               "byte +0x18 = %u, regeneration list count %lu, entry 0 {%ld, %ld, %lu}%s; children: %s", who, serial,
            where, id, name, reinterpret_cast<DWORD>(data), RdByte(data + 0x18), count,
            list && count ? static_cast<LONG>(Rd(list)) : 0, list && count ? static_cast<LONG>(Rd(list + 4)) : 0,
            list && count ? Rd(list + 8) : 0, list && count ? "" : " (no list)", detail);
    } else {
        Log(1, "0.6.5 companion: %s serial 0x%08lx (first seen: %s) - none: %s%s%s", who, serial, where, kCompWhy[why],
            detail[0] ? "; children: " : "", detail);
    }
    if (n == kCompMaxLines) Log(1, "0.6.5 companion: %ld lines - no more", kCompMaxLines);
}

// ---- H6: RegenerateDeath Exit (thiscall state, ret 0x10)
DWORD __fastcall RdExitHook(void *self, void *, BYTE *inst, DWORD layer, DWORD a3, DWORD a4) {
    const DWORD r = reinterpret_cast<StateSlotFn>(kRdExitFn)(self, inst, layer, a3, a4);
    P1dReadSwitches();
    CompanionNote(inst, "RegenerateDeath exit");
    if (g_notify34) P1dNotify(kTuNotifyExit);
    if (P1dLine()) {
        char who[96];
        Describe(inst, who, sizeof(who));
        Log(1, "0.6.5 death: %s leaves RegenerateDeath: %s", who,
            g_notify34 ? "notification 34 sent (TU 0x8235e38c)" : "no notification ([Death] TranslateNotify34=0)");
    }
    return r;
}

// ---- H7 / H8: the TU-new first block of RegenerateDeath / Regenerate slot 10; true = done (return 1)
bool Finisher38(BYTE *inst, DWORD message, const BYTE *data, const char *state, const char *tu) {
    P1dReadSwitches();
    CompanionNote(inst, state);
    if (message != 0x11c || !data) return false;
    const LONG type = static_cast<LONG>(Rd(data + 0x50)), sub = static_cast<LONG>(Rd(data + 0x64));
    if (!(type == 0x10 || (sub == 1 && type == 1))) return false;
    if (!CompanionData(inst)) return false;
    if (!g_notify38) {
        if (P1dLine()) {
            char who[96];
            Describe(inst, who, sizeof(who));
            Log(1, "0.6.5 death: %s %s hit type %ld subtype %ld with companion - [Death] TranslateNotify38=0: PC handler "
                   "(the TU would switch to Death kind 7 and send 38, %s)", who, state, type, sub, tu);
        }
        return false;
    }
    // TU: 0x823258c8(inst, 1, 0, 1, 7, 0, v1 = [0x8207db00] = (0, 0, 1, 0)) = PC tru+0x241650 (cdecl inst, vec16 aligned *,
    // u8, ptr, u8, kind, u8), then PlayNotification([0x829ca684], 38)
    __declspec(align(16)) float v[4] = {0.0f, 0.0f, 1.0f, 0.0f};
    reinterpret_cast<DeathSwitchFn>(kDeathSwitch)(inst, v, 1, 0, 1, kTuFinisherKind, 0);
    P1dNotify(kTuNotifyFinisher);
    if (P1dLine()) {
        char who[96];
        Describe(inst, who, sizeof(who));
        Log(1, "0.6.5 death: %s %s hit type %ld subtype %ld with companion -> death switch kind 7 and notification 38 as "
               "the TU %s", who, state, type, sub, tu);
    }
    return true;
}

DWORD __fastcall RdMsgHook(void *self, void *, BYTE *inst, DWORD layer, DWORD message, DWORD data) {
    if (Finisher38(inst, message, reinterpret_cast<const BYTE *>(data), "RegenerateDeath", "0x8235e3ec..0x8235e468"))
        return 1;
    return reinterpret_cast<StateSlotFn>(kRdMsgFn)(self, inst, layer, message, data);
}

DWORD __fastcall RgMsgHook(void *self, void *, BYTE *inst, DWORD layer, DWORD message, DWORD data) {
    if (Finisher38(inst, message, reinterpret_cast<const BYTE *>(data), "Regenerate", "0x8235e9b8..0x8235ea34"))
        return 1;
    return reinterpret_cast<StateSlotFn>(kRgMsgFn)(self, inst, layer, message, data);
}

// ---- H1: TU 0x8235ed04..0x8235ede0 - the companion's regeneration list; 1 = an entry matches (index in *entry)
int CompanionRegen(BYTE *inst, DWORD type, DWORD sub, DWORD flag, int *entry, DWORD *count) {
    *entry = -1;
    *count = 0;
    __try {
        const BYTE *brain = P1dBrain(inst);
        if (!brain) return 0;
        // tru+0x214610 (TU 0x822d3d38): first node of the list [brain+0x168] with +0x64, next +0x1c (an empty list asks
        // the print stub tru+0x2457a0 = ret, eax 0 -> no record)
        const BYTE *rec = nullptr;
        const BYTE *p = *reinterpret_cast<const BYTE *const *>(brain + 0x168);
        for (int guard = 0; p && guard < 256 && !rec; ++guard) {
            rec = *reinterpret_cast<const BYTE *const *>(p + 0x64);
            p = *reinterpret_cast<const BYTE *const *>(p + 0x1c);
        }
        if (!rec) return 0;
        if (*reinterpret_cast<const WORD *>(rec + 0x22) == 0xffff && *reinterpret_cast<const WORD *>(rec + 0x26) == 0xffff)
            return 0;
        const BYTE *comp = CompanionData(inst);
        if (!comp) return 0;
        const DWORD n = *reinterpret_cast<const DWORD *>(comp + 0x40);
        const BYTE *list = *reinterpret_cast<const BYTE *const *>(comp + 0x44);
        *count = n;
        if (!n || !list) return 0;
        if (n > 64) return 0;                               // a misconverted count (as +0x2c of these files) - logged
        for (DWORD i = 0; i < n; ++i) {
            const BYTE *e = list + i * 0xc;
            const LONG t = *reinterpret_cast<const LONG *>(e), s = *reinterpret_cast<const LONG *>(e + 4);
            const bool typeOk = t == -1 || t == static_cast<LONG>(type);
            const bool subOk = s == 0 || s == static_cast<LONG>(sub);
            if (typeOk && subOk && (*reinterpret_cast<const DWORD *>(e + 8) & 1) == (flag & 0xff)) {
                *entry = static_cast<int>(i);
                return 1;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
    return 0;
}

DWORD __cdecl RegenListHook(BYTE *inst, DWORD type, DWORD sub, DWORD flag) {
    const DWORD ret = reinterpret_cast<DWORD>(_ReturnAddress()) - 5;
    const char *where = ret == kRegenCalls[0] ? kRegenCallWhere[0] : ret == kRegenCalls[1] ? kRegenCallWhere[1]
                                                                    : ret == kRegenCalls[2] ? kRegenCallWhere[2] : "?";
    P1dReadSwitches();
    CompanionNote(inst, where);
    if (g_regenList) {
        int entry = -1;
        DWORD count = 0;
        const int yes = CompanionRegen(inst, type, sub, flag, &entry, &count);
        if (count > 64 && P1dLine()) {
            char who[96];
            Describe(inst, who, sizeof(who));
            Log(0, "0.6.5 regen: %s companion regeneration list count %lu implausible (converted data?) - ignored", who,
                count);
        }
        if (yes) {
            if (P1dLine()) {
                // log only: what the PC tune list alone says (a pure read, the same call the PC makes)
                const DWORD pc = reinterpret_cast<ShouldRegenFn>(kShouldRegen)(inst, type, sub, flag) & 0xff;
                char who[96];
                Describe(inst, who, sizeof(who));
                Log(1, "0.6.5 regen: %s %s type %lu subtype %lu flag %lu: companion regeneration list entry %d -> "
                       "ShouldRegenerate yes as the TU 0x8235ed5c (the PC tune list says %s)", who, where, type, sub,
                    flag & 0xff, entry, pc ? "yes too" : "no");
            }
            return 1;
        }
    }
    return reinterpret_cast<ShouldRegenFn>(kShouldRegen)(inst, type, sub, flag);
}

// ---- H3: T2 at the landing; 1 = done (the function returns), 0 = the PC LandDeath branch
int __cdecl LandLethal(BYTE *inst, const BYTE *stateData) {
    P1dReadSwitches();
    CompanionNote(inst, "Land, LP <= 0");
    if (!g_translateLand) return 0;
    const BYTE *comp = CompanionData(inst);
    const BYTE b18 = comp ? RdByte(comp + 0x18) : 0;
    char who[96];
    if (!comp || b18 != 0) {
        if (P1dLine()) {
            Describe(inst, who, sizeof(who));
            Log(1, "0.6.5 land: %s lands with LP <= 0 - %s: LandDeath (PC = TU 0x82328db0)", who,
                comp ? "companion byte +0x18 != 0" : "no companion");
        }
        return 0;
    }
    // TU 0x82328d40..0x82328d74
    if (g_notify33) P1dNotify(kTuNotifyRegen);
    const BYTE data[2] = {static_cast<BYTE>((Rd(stateData + 0x30) >> 1) & 1), 1};
    const DWORD r = reinterpret_cast<SwitchWithDataFn>(kSwitchWithData)(inst, kStateRegenDeath, data, 0);
    if (P1dLine()) {
        Describe(inst, who, sizeof(who));
        Log(1, "0.6.5 land: %s lands with LP <= 0, companion byte +0x18 = 0: %s, RegenerateDeath with data {%u, 1} as the "
               "TU 0x82328d24..0x82328d74 (switch answered %lu)", who,
            g_notify33 ? "notification 33 sent" : "no notification 33 ([Death] TranslateNotify33=0)", data[0], r & 0xff);
    }
    return 1;
}

// jumped to from tru+0x25b181 (Land slot 9 after IsDead = yes): edi = instance, esi = state data, ebx = brain; eax is
// loaded again by the moved instruction, ecx / edx are set before use on both targets, the FPU stack is empty
__declspec(naked) void LandStub() {
    __asm {
        push esi
        push edi
        call LandLethal
        add esp, 8
        test eax, eax
        jne land_done
        mov eax, dword ptr [edi + 0x2d0]
        jmp dword ptr [g_landBackTo]
    land_done:
        jmp dword ptr [g_landEndTo]
    }
}

// ---- H4: Land slot 13 (thiscall state, (inst, layer, next, data), ret 0x10)
DWORD __fastcall LandIntHook(void *self, void *, BYTE *inst, DWORD layer, DWORD next, DWORD data) {
    const DWORD r = reinterpret_cast<StateSlotFn>(kLandIntFn)(self, inst, layer, next, data);
    if (static_cast<LONG>(r) != -1 || (next != kStateRegenDeath && next != kStateDeath)) return r;
    P1dReadSwitches();
    CompanionNote(inst, "Land slot 13");
    if (!g_translateLand || !CompanionData(inst)) return r;
    if (P1dLine()) {
        char who[96];
        Describe(inst, who, sizeof(who));
        Log(1, "0.6.5 land: %s in Land, %s may interrupt (companion) -> 6 as the TU 0x82329148 (PC -1)", who,
            next == kStateDeath ? "Death" : "RegenerateDeath");
    }
    return 6;
}

// ---- H5: MeleeAttack slot 13 (thiscall state, (inst, layer, next, data), ret 0x10)
DWORD __fastcall MeleeIntHook(void *self, void *, BYTE *inst, DWORD layer, DWORD next, DWORD data) {
    const DWORD r = reinterpret_cast<StateSlotFn>(kMeleeIntFn)(self, inst, layer, next, data);
    P1dReadSwitches();
    CompanionNote(inst, "MeleeAttack slot 13");
    if (static_cast<LONG>(r) != -1 || !g_meleeInterrupt) return r;
    const bool vaulted = next == kStateVaulted;
    if (!vaulted && !(next == kStateRegenDeath && CompanionData(inst))) return r;
    const DWORD v = reinterpret_cast<StateValueFn>(kStateValue)(next);
    if (P1dLine()) {
        char who[96];
        Describe(inst, who, sizeof(who));
        Log(1, "0.6.5 melee: %s in MeleeAttack, %s may interrupt -> %ld as the TU 0x823308f4..0x82330908 (PC -1)", who,
            vaulted ? "Vaulted" : "RegenerateDeath (companion)", static_cast<LONG>(v));
    }
    return v;
}

struct Fact { DWORD at; const char *hex; const char *what; };
bool FactsOk(const Fact *f, size_t count, const char *part) {
    for (size_t i = 0; i < count; ++i)
        if (!HexAt(f[i].at, f[i].hex)) {
            Log(0, "0.6.5 %s: %s at 0x%08lx does not match - not placed (PC)", part, f[i].what, f[i].at);
            return false;
        }
    return true;
}

bool WriteSlot(DWORD slot, const void *to) {
    const DWORD v = reinterpret_cast<DWORD>(to);
    return WriteCode(slot, &v, 4);
}

// the PlayNotification facts of SetupDeath (also needed when that part is off)
const Fact kNotifyFacts[] = {
    {kPlayNotification,
     "56 57 8b7c240c be08acdb00 eb03 8d4900 80be3cffffff02 7510 8b06 57 8d4c2410 89442410 e8e7300200 81c6d8000000 "
     "81fe08c7db00 7cd9 5f 5e c20400",
     "PlayNotification tru+0x37a540"},
    {0x00768a20, "8b442408 6683780220 7513 8b4004 85c0 7e0c 8b0d80e8fa00 50 e8021b0100 c3",
     "script event handler tru+0x368a20: PlayNotification([0xfae880], n)"},
};
// the death switch of 0.6.1 (checked there only when [Chunk] is on)
const Fact kDeathSwitchFacts[] = {
    {kDeathSwitch,
     "55 8bec 83e4f0 83ec24 53 8b5d0c 56 8b7514 57 8b7d08 85ff 0f84ad000000 8b87d0020000 85c0 0f849f000000 8b00 "
     "8b80ec020000 85c0 0f848f000000 d9ee 51 8d88602c0000 d91c24 e8b461ffff 8b4d1c 8bc1 83e805 7409 83e802 7404 32c0 "
     "eb02 b001 85f6 f30f100530118400 0f280b 894c2424 8a4d10 0fc6c000 0f59c1 0f29442410 c744242000000000 884c2428 "
     "88442429 c644242b01 7404 89742420 807d2000 7505 c644242b00 8a5518 6a00 8d442414 50 6804e98a00 57 8854243a "
     "e8d0bfffff 83c410 5f 5e 5b 8be5 5d c3",
     "death switch tru+0x241650 (cdecl 7 arguments, movaps from the vector)"},
};

void SetupCompanion() {
    if (HexAt(0x005bcff9, "8b0dd094db00 52 8b14c1")) g_namesOk = true;
    // H0: object table (g_tableOk: base / stride / count of the PC lookup tru+0x14e930) and the loader fields
    const Fact comp[] = {
        {0x0054e22e, "8b4748 89462c", "object loader tru+0x14e231: object +0x2c = child id list (DTP +0x48)"},
        {0x0054e667, "8b88c8000000 3bcd 7409 8d5060 894e5c 895658",
         "object loader tru+0x14e674: object +0x5c = data (main DTP +0xc8)"},
        {0x005bf0ed, "8b0dd094db00 8b4314 8b04c1 8b0b 894360", "tru+0x1bf0fb: object +0x60 = its name pointer"},
        {0x005ba84c, "8b435c 8b7c2434 8b6c2438 894650", "instance init tru+0x1ba84c: instance +0x50 = object +0x5c"},
    };
    g_compOk = g_tableOk && FactsOk(comp, sizeof(comp) / sizeof(comp[0]), "companion");
    Log(1, "0.6.5 companion: %s - [Companion] Translate %d, Log %d (one line per new thrall, at most %ld)",
        g_compOk ? "lookup ready (object table 0xdb7400, child list +0x2c, data +0x5c type 0x3d = TU 0x822da800 / "
                   "0x822da918)"
                 : g_tableOk ? "loader facts differ - never a companion (TU without one = PC)"
                             : "object table lookup tru+0x14e930 differs - never a companion (TU without one = PC)",
        g_compTranslate, g_compLog, kCompMaxLines);
    const bool notifyOk = FactsOk(kNotifyFacts, sizeof(kNotifyFacts) / sizeof(kNotifyFacts[0]), "notification");
    const bool deathOk = FactsOk(kDeathSwitchFacts, sizeof(kDeathSwitchFacts) / sizeof(kDeathSwitchFacts[0]), "death switch");
    const Fact states[] = {
        {kStateRegenDeath, "d4b08500 06000000", "state object RegenerateDeath 0x8afa4c (vtable 0x85b0d4)"},
        {0x008afa70, "34b18500 06000000", "state object Regenerate 0x8afa70 (vtable 0x85b134)"},
        {kStateDeath, "dc8e8500 06000000", "state object Death 0x8ae904 (vtable 0x858edc)"},
        {kStateVaulted, "148e8500 05000000", "state object Vaulted 0x8ae8bc (vtable 0x858e14)"},
        {kStateLand, "5c8c8500 06000000", "state object Land 0x8ae808 (vtable 0x858c5c)"},
    };
    const bool statesOk = FactsOk(states, sizeof(states) / sizeof(states[0]), "states");

    // H6
    const Fact h6[] = {
        {kRdExitSlot, "b0ee6700", "RegenerateDeath vtable slot 12 0x85b104 = tru+0x27eeb0"},
        {kRdExitFn, "56 8b742408 8b86d0020000 85c0 7408 8b00 8b80ec020000 8b8868010000 51 c680802c000001 e88658f9ff "
                    "6a00 50 56 e80d2efaff 83c410 5e c21000",
         "RegenerateDeath Exit tru+0x27eeb0 (= retail 0x8235ea38 / TU 0x8235e338 body, ret 0x10)"},
    };
    if (notifyOk && statesOk && FactsOk(h6, sizeof(h6) / sizeof(h6[0]), "H6") &&
        WriteSlot(kRdExitSlot, reinterpret_cast<const void *>(&RdExitHook)))
        g_h6 = true;

    // H7 / H8
    const Fact h7[] = {
        {0x0085b0fc, "90246800", "RegenerateDeath vtable slot 10 0x85b0fc = tru+0x282490"},
        {kRdMsgFn,
         "817c240c1c010000 56 57 756c 8b742418 85f6 7464 807e6e00 8b4e64 8b5650 8b7c240c 0f95c0 50 51 52 57 e882cbffff "
         "83c410 84c0 7443 56 e81517f9ff 83c404 84c0 742f 8b87d0020000 85c0 7512 8d88804b0000 e8f929f9ff 5f b001 5e c21000 "
         "8b00 8b80ec020000 8d88804b0000 e8df29f9ff 5f b001 5e c21000 5f 32c0 5e c21000",
         "RegenerateDeath slot 10 tru+0x282490 (inst, layer, message, data; ret 0x10)"},
    };
    const Fact h8[] = {
        {kRgMsgSlot, "80266800", "Regenerate vtable slot 10 0x85b15c = tru+0x282680"},
        {kRgMsgFn,
         "8b44240c 83f815 56 0f848b000000 3d1c010000 757e 8b742414 85f6 7476 53 57 8b7c2410 8b87d0020000 85c0 7504 33db "
         "eb08 8b00 8b98ec020000 80bbe80f000000 743d 807e6e00 8b5664 8b4650 0f95c1 51 52 50 57 e868c9ffff 83c410 84c0 "
         "7420 56 e8fb14f9ff 83c404 84c0 740b 8d8b804b0000 e8e927f9ff 5f 5b b001 5e c21000 6a01 56 57 e87885fdff 83c40c "
         "5f 5b b001 5e c21000 32c0 5e c21000",
         "Regenerate slot 10 tru+0x282680 (inst, layer, message, data; ret 0x10)"},
    };
    if (notifyOk && deathOk && statesOk && FactsOk(h7, sizeof(h7) / sizeof(h7[0]), "H7") &&
        WriteSlot(kRdMsgSlot, reinterpret_cast<const void *>(&RdMsgHook)))
        g_h7 = true;
    if (notifyOk && deathOk && statesOk && FactsOk(h8, sizeof(h8) / sizeof(h8[0]), "H8") &&
        WriteSlot(kRgMsgSlot, reinterpret_cast<const void *>(&RgMsgHook)))
        g_h8 = true;

    // H1 (the function head as TruMenu checks it; the three calls with their argument pushes)
    const Fact h1[] = {
        {kShouldRegen, "8b442404 8b80d0020000 85c0 740c 8b08 8b81ec020000 85c0 7503 32c0 c3 8b9068010000 52 e8a755f9ff "
                       "83c404 85c0 74ea",
         "ShouldRegenerate tru+0x27f040: brain, tune record tru+0x214610([brain+0x168])"},
        {0x0067f070, "b9ffff0000 66394822 7506 66394826 74d9 53 55 56 57 8b7864 33f6 85ff 7652 8a5c2420 8b6c2418 "
                     "8d486c",
         "ShouldRegenerate: anim words +0x22 / +0x26, tune list +0x64 / +0x68, flag byte"},
        {0x00614610, "8b442404 85c0 7509 e883110300 85c0 740d 83786400 750a 8b401c 85c0 75f3 33c0 c3 8b4064 c3",
         "tune record tru+0x214610: first node with +0x64, next +0x1c"},
        {0x006457a0, "c3", "print stub tru+0x2457a0 (ret)"},
        {0x006203dc, "8b7c2424 57 51 53 56 e857ec0500 83c410 84c0 7417", "death check: call ShouldRegenerate tru+0x2203e4"},
        {0x006824a4, "807e6e00 8b4e64 8b5650 8b7c240c 0f95c0 50 51 52 57 e882cbffff 83c410 84c0 7443",
         "RegenerateDeath slot 10: call ShouldRegenerate tru+0x2824b9"},
        {0x006826c2, "807e6e00 8b5664 8b4650 0f95c1 51 52 50 57 e868c9ffff 83c410 84c0 7420",
         "Regenerate slot 10: call ShouldRegenerate tru+0x2826d3"},
    };
    if (FactsOk(h1, sizeof(h1) / sizeof(h1[0]), "H1")) {
        int placed = 0;
        for (int i = 0; i < 3; ++i)
            if (WriteCall(kRegenCalls[i], reinterpret_cast<const void *>(&RegenListHook))) ++placed;
        if (placed == 3) {
            g_h1 = 3;
        } else {
            for (int i = 0; i < 3; ++i) WriteCall(kRegenCalls[i], reinterpret_cast<const void *>(kShouldRegen));
            Log(0, "0.6.5 H1: only %d of 3 calls written - all three back to tru+0x27f040 (PC)", placed);
        }
    }

    // H4 + H3 (H3 only with H4: without it Land refuses the switch)
    const Fact h4[] = {
        {kLandIntSlot, "301d6400", "Land vtable slot 13 0x858c90 = tru+0x241d30"},
        {kLandIntFn,
         "8b44240c 3d78e78a00 750c 50 e8bfe60200 83c404 c21000 3d9ce78a00 7422 3d2ce88a00 741b 3d28e98a00 7414 "
         "3d34ef8a00 740d 3d7cef8a00 7406 83c8ff c21000 b806000000 c21000",
         "Land slot 13 tru+0x241d30: HostAnimation -> tru+0x270400, Fall / Getup / LandDeath / DrownDeath / "
         "DeferredInstantDie -> 6, else -1 (= retail / TU 0x82329060 without the companion clause)"},
    };
    const Fact h3[] = {
        {0x0065b174, "57 e8d651fcff 83c404 84c0 7437 8b87d0020000 85c0 7408 8b00 8b80ec020000 6a00 6a00 6828e98a00 "
                     "8d88e0110000 51 57 8d8854120000 e8816b0100 5f 5e 5b 8be5 5d c20800",
         "Land slot 9 tru+0x25b174: IsDead(inst edi) -> LandDeath 0x8ae928 (tru+0x271d30), return"},
        {0x0065b1b8, "8b83a0110000 8bd0 d1ea f6c201 7434 8bc8 c1e902 f6c101 752a 8b5630 6a00 8d44241f 50 d1ea 80e201 "
                     "682ce88a00 57 8854242b e8b122feff 83c410",
         "Land slot 9 tru+0x25b1b8: Getup with the 2-byte data {([esi+0x30] >> 1) & 1, ..} via tru+0x23d4a0"},
        {kSwitchWithData,
         "8b4c2404 8b81d0020000 83ec0c 85c0 7408 8b00 8b80ec020000 8b542418 891424 8b54241c 52 8d542404 52 8b54241c 52 "
         "8d90e0110000 52 51 8d8854120000 c744241850888500 c744241c01000000 e83e480300 83c40c c3",
         "state switch with data tru+0x23d4a0 (cdecl inst, state, data *, int; type 0x858850)"},
        {0x0085b0e0, "b0877900", "RegenerateDeath slot 3 = tru+0x3987b0 (empty data copier)"},
        {0x007987b0, "c20800", "tru+0x3987b0: ret 8"},
        {0x00620350, "8b442404 8b80d0020000 85c0 7408 8b08 8b81ec020000 d980642c0000",
         "IsDead tru+0x220350: LP brain+0x2c64"},
    };
    if (statesOk && FactsOk(h4, sizeof(h4) / sizeof(h4[0]), "H4") &&
        WriteSlot(kLandIntSlot, reinterpret_cast<const void *>(&LandIntHook))) {
        g_h4 = true;
        if (notifyOk && FactsOk(h3, sizeof(h3) / sizeof(h3[0]), "H3")) {
            BYTE j[6] = {0xe9, 0, 0, 0, 0, 0x90};
            const DWORD rel = reinterpret_cast<DWORD>(&LandStub) - (kLandSite + 5);
            memcpy(j + 1, &rel, 4);
            if (WriteCode(kLandSite, j, sizeof(j))) g_landHooked = true;
            else Log(0, "0.6.5 H3: jump at tru+0x25b181 failed - T2 off (PC LandDeath)");
        }
    }

    // H5
    const Fact h5[] = {
        {kMeleeIntSlot, "402f6400", "MeleeAttack vtable slot 13 0x859160 = tru+0x242f40"},
        {kMeleeIntFn,
         "8b442404 8b80d0020000 85c0 7408 8b08 8b81ec020000 8b4c2408 8b9488d4180000 8d0c4a 69c99c010000 "
         "8d940173120000 83e2f0 8b4250 f6400804 8b44240c 753e 3d04e98a00 7437 3d28e98a00 7430 3d7cef8a00 7429 "
         "3d34ef8a00 7422 3d4ce98a00 741b 3d9ce78a00 7414 3d08e88a00 740d 3d20eb8a00 7406 83c8ff c21000 50 e83bd40200 "
         "83c404 c21000",
         "MeleeAttack slot 13 tru+0x242f40 (= retail 0x82331750: record+8 bit 2, death states, Fall / Land / "
         "FinishAttack -> tru+0x270400, else -1)"},
        {kStateValue, "8b442404 85c0 7501 c3 8b4004 c3", "tru+0x270400: state ? [state+4] : 0"},
    };
    if (statesOk && FactsOk(h5, sizeof(h5) / sizeof(h5[0]), "H5") &&
        WriteSlot(kMeleeIntSlot, reinterpret_cast<const void *>(&MeleeIntHook)))
        g_h5 = true;

    Log(1, "0.6.5: H6 notification 34 %s, H7 / H8 finisher 38 %s / %s, H1 regeneration list %s (%d of 3 calls), "
           "H4 Land slot 13 %s, H3 T2 Land %s, H3b Land exception %s, H5 T-M3 %s - switches [Death] TranslateNotify34 %d, "
           "TranslateNotify38 %d, TranslateRegenList %d, TranslateLand %d (T2's 33 also needs TranslateNotify33, now %d), "
           "[Melee] TranslateInterrupt %d; read again at run time at most once per second",
        g_h6 ? "on" : "OFF", g_h7 ? "on" : "OFF", g_h8 ? "on" : "OFF", g_h1 ? "on" : "OFF", g_h1, g_h4 ? "on" : "OFF",
        g_landHooked ? "on" : "OFF",
        g_landHooked && g_deathHooked ? "on" : "OFF (needs T2 and the 0.6.3 death hook)", g_h5 ? "on" : "OFF",
        g_notify34, g_notify38, g_regenList, g_translateLand, g_notify33, g_meleeInterrupt);
}

// ---------------------------------------------------------------- 0.6.6 (N4c): T5 and P1c (docs
// Befund-P1d-Begleiter-0711.md section 2 rows T5 / P1c in the main workspace; the TU / retail / PC disassemblies of this
// section are in work\combat066_0711\).
// T5  hit reaction TU 0x823038d8 = retail 0x82305d40 = PC tru+0x23ad50 (cdecl inst, hit data, a3, a4 -> float amount).
//     The TU inserted at its start (0x8230390c..0x82303a78, between the brain lookup and the "[data+0x64] == 1" block
//     that retail 0x82305d8c / PC tru+0x23ad85 begin with):
//       comp = 0x822da918(inst); LP = brain+0x2c64; amount = data+0x4c; type = data+0x50
//       if (comp && !(LP > amount) && !ShouldRegenerate(inst, type, data+0x64, data+0x6e != 0)) {     // 0x8235ece8
//         v = (data+0x70 ? data+0x10 : [data+0x30]+0x20) - (data+0x72 ? data+0x00 : inst+0x20); v.z = 0 (0x8207d538)
//         0x8213e838(&v): v / |v.xyz| (all four words), the zero vector unless |v.xyz|^2 is finite and > FLT_MIN
//                     (0x820d7be8 -> 0x820d78a0, [0x82053664] = 0x00800000)
//         type 0x19: v = v x (0, 0, -1, 0) ([0x8207db80]; vpermwi128 0x63 / 0x87, vmulfp128, vnmsubfp)
//         0x823258c8(inst, 1, 0, 1, kind 7, 0, v) = PC tru+0x241650(inst, &v, 1, 0, 1, 7, 0) (as H7 / H8)
//         return amount (0x8230443c f1 = f31; the normal end's brain+0x2c50 = 0 at 0x82304438 is skipped)
//       }
//     The companion is only asked "is it there" - no field of its data is read (T5 needs no extension data fix).
//     ShouldRegenerate = the TU's (H1: companion regeneration list, then the PC function) while [Death]
//     TranslateRegenList=1, else the PC function. PC twins of the fields: the PC's own hit vector code
//     tru+0x23cad4..0x23cb0d (+0x70 -> +0x10 / [+0x30]+0x20, +0x72 -> +0x00 / inst+0x20), amount fld [edi+0x4c]
//     tru+0x23adcc, epilogue tru+0x23b312. tru+0x23ad82 (mov edi, [ebp+0xc]; cmp dword [edi+0x64], 1 - 7 bytes) jumps
//     to T5Stub. [Death] TranslateT5=1 (default, live); 0 = the PC code.
// P1c Vaulted Enter (TU-only 0x8232b630; retail 0x8232cb18 = PC tru+0x24fcf0, vtable 0x858e14 slot 7) and the chain
//     that feeds its new data field +0x44 (the companion step):
//   F  the retail strike's 0xbe record (TU 0x823dffc8 = retail 0x823ddd68, PC call tru+0x31d5cc -> tru+0x245e40): the
//      TU added record +0x34 = 0 (0x823e0294; retail / PC leave the ring-buffer word).
//   E  the finisher 1013's 0xf4 record (TU 0x823e0e84): +0x3c = 0 in every mode (Record1013, 0.4 section).
//   A  enemy message handler case 0xbe (TU 0x823068b8 = retail 0x82308bc0 = PC tru+0x23b330, case tru+0x23b402): its
//      copy of the record (PC tru+0x245de0, +0x34 / +0x38 = 0) gets +0x3c = the incoming record's +0x34 (TU
//      0x8230743c) - the step the TU strike 0x823d86a8 writes there (StrikeAt above: record +0x34 = arg).
//   B  switch into Vaulted from a record (TU 0x82304460 = retail 0x82306770 = PC tru+0x223f50, cases 0xbe / 0xf4): the
//      Vaulted data (EnemyVaultedSwitchData 0x85682c, 0x50 bytes) gets +0x44 = record +0x3c (TU 0x8230447c /
//      0x823044dc); the PC data has no such field (its ctor tru+0x240010 leaves the word).
//   D  Vaulted slot 3 (data copier, TU 0x82322f48 = retail 0x82325038 = PC tru+0x25a470): the TU copies +0x44 too
//      (0x8232300c; its ctor sets 0 at 0x82322fa8, overwritten by the copy) - the PC copy tru+0x24d350 stops at +0x40.
//   C  Enter: state data +0xb8 = data +0x44 (TU 0x8232b694 / 0x8232b748; state data 0xc0 bytes on both, the PC never
//      uses +0xb8), the animation choice 0x8232b3f8(inst, data+0x3c, data+0x34, data+0x40, step = data+0x44): step 0 =
//      the retail choice (PC inline tru+0x24fdb9..0x24fdef, left to the PC), step != 0 = the companion's step table
//      entry [comp+0x20] + (step - 1) * 0x14 when step <= [comp+0x24], else 0 (no animation - as the TU, also without a
//      companion); with a companion brain+0x2c7c = 0x0fffffff (0x8232b7d8; the PC writes this field (tru+0x23419c /
//      tru+0x2375f7) but never reads it, its TU readers 0x82327594 / 0x8232bf4c are TU-only code - written here before
//      the animation call instead of after it, nothing reads it in between). tru+0x24fdb9 (mov edx, [eax+0x3c];
//      xor ecx, ecx - 5 bytes) jumps to VaultedAnimStub.
//      Data guard: the step table is read only when the companion data is the FIXED layout (record count +0x2c <= 64,
//      step count +0x24 <= 64, table pointer set, every step entry's thrall anim pair +0 / +2 < 0x1000) - the converted
//      files (count 0x000f0000 / 0x000e0000) fail: logged once, the PC choice runs.
//   K  the clock (the TU's "5 s without slow motion" of a vaulting enemy; [Death] TranslateVaultedClock, needs the
//      chain): globals [0x82efb458] = PC 0xe7f088 (+0xc = the player 0xe7f094): +0xd4 = 0xe7f15c (ms counter, written
//      by tru+0x1d3e5c), +0x100 = 0xe7f188 (time multiplier), +0x118 = 0xe7f1a0 (slow motion factor) - the PC player
//      update uses the same idiom (tru+0x3228e9: save 0xe7f188, *= 1 / 0xe7f1a0, restored at tru+0x3229eb).
//      Enter (TU 0x8232b698..0x8232b6dc, in VaultedAnim): if brain+0xc bit 0x10 is clear: set it, clock = [+0xd4],
//        [+0x100] = [+0x100] / [+0x118].
//      enemy update 0x822db190 = PC tru+0x238d40: after the brain (0x822db1e8): brain+0x5084 = [+0x100]; bit 0x10 set
//        -> now - clock >= 5000 (unsigned): clock = 0, bit cleared; else [+0x100] *= 1.0 / [+0x118] (double 1.0
//        [0x8206eb78]); at the end of the main path (0x822db4e0, after the health print) [+0x100] = brain+0x5084; the
//        exit on brain+8 bit 0x20000 (0x822db364 = PC tru+0x238e7f) and the inst+0x14 bit 0x20 exit skip the restore.
//      brain+0x5080 / +0x5084 lie in the TU brain's added block (the TU's +0x5088 is the PC's +0x5030: update 0x822db368
//      / tru+0x238e81 before the twins 0x82311620 / tru+0x262ce0) - no PC room: the plugin keeps them.
//      Plugin state (game thread only): the clock word per instance in g_clock[64] {instance, serial +0x44, clock}, an
//      entry exists only while the instance's bit 0x10 runs; it ends when the update clears the bit (>= 5000 ms), when
//      the instance's serial differs (instance reused: unload / level change / respawn - the old entry is dropped at
//      the next look-up), or when the table is full (the oldest is dropped = its clock ends at its next update, logged).
//      A missing entry reads 0 = expired (the TU's clock word is only ever set together with the bit). The +0x5084 save
//      is one slot {instance, value, valid} set by the update start and used by its own end (updates do not nest; a
//      different instance at the end = no restore, logged).
//      Sites: tru+0x238d6f (call tru+0x2e7710 -> ClockStartStub, right after TruMenu's checked bytes tru+0x238d59..6e),
//      tru+0x238e76 (11 bytes, the bit 0x20000 exit -> ClockExitStub), tru+0x238efb (epilogue, 7 bytes ->
//      ClockEndStub, reached by the main path and both exits; it restores only after a start without that exit).
//      Not translated: the two script commands of 0x822d61e0 that set / clear the clock (0x822d6844 / 0x822d6880).
//   Not in 0.6.6: Vaulted slot 10 case 0xbe (the next step, TU 0x8232be54), slot 11 0x8232c068, Exit 0x8232b930, the
//      step queries 0x165..0x167 (0x823093a0 -> 0x82308850).
//   [Death] TranslateVaulted=1 (default, live): every link checks it; the six links are placed together or not at all.
const DWORD kT5Site = 0x0063ad82, kT5Back = 0x0063ad89;
const DWORD kT5Type = 0x19;                                  // TU 0x82303a1c cmpwi r31, 0x19
const float kT5Axis[4] = {0.0f, 0.0f, -1.0f, 0.0f};          // TU [0x8207db80]
const DWORD kFltMinBits = 0x00800000;                        // TU [0x82053664]
const DWORD kVaultAnimSite = 0x0064fdb9, kVaultAnimBack = 0x0064fdbe, kVaultAnimFlow = 0x0064fdf2;
const DWORD kRecCopyCall = 0x0063b421, kRecCopyFn = 0x00645de0;       // A
const DWORD kVaultSwitchCall = 0x00623fa2, kVaultSwitchFn = 0x0060ed80;   // B
const DWORD kVaultCopyCall = 0x0065a4a2, kVaultCopyFn = 0x0064d350;   // D
const DWORD kStrikeRecCall = 0x0071d5cc;                     // F (-> kRecord tru+0x245e40)
const DWORD kVaultCompMark = 0x0fffffff;                     // TU 0x8232b7d0 lis 0xfff / ori 0xffff
typedef BYTE *(__cdecl *RecCopyFn)(DWORD inst, DWORD from, const BYTE *p10, const BYTE *p20, float frames, DWORD x34,
                                   DWORD x38);
bool g_t5 = false;
DWORD g_t5BackTo = kT5Back, g_vaultAnimBackTo = kVaultAnimBack, g_vaultAnimFlowTo = kVaultAnimFlow;
DWORD g_vaultSwitchTo = kVaultSwitchFn, g_vaultCopyTo = kVaultCopyFn;
volatile LONG g_extUnfixedLogged = 0, g_n4cLines = 0;
const LONG kN4cMaxLines = 1500;

bool N4cLine() {
    const LONG n = InterlockedIncrement(&g_n4cLines);
    if (n > kN4cMaxLines) return false;
    if (n == kN4cMaxLines) Log(1, "0.6.6: %ld event lines - this is the last one", kN4cMaxLines);
    return true;
}

bool FactsOk66(const Fact *f, size_t count, const char *part) {
    for (size_t i = 0; i < count; ++i)
        if (!HexAt(f[i].at, f[i].hex)) {
            Log(0, "0.6.6 %s: %s at 0x%08lx does not match - not placed (PC)", part, f[i].what, f[i].at);
            return false;
        }
    return true;
}

// ---- T5
// TU 0x8213e838 with its test 0x820d7be8: zero vector unless |xyz|^2 is a finite number > FLT_MIN; else all four
// words times 1 / |xyz| (the TU's vrsqrtefp + one Newton step; sqrtf differs in the last bits only)
void NormalizeChecked(float *v) {
    const float sq = v[0] * v[0] + v[1] * v[1] + v[2] * v[2];
    DWORD bits = 0;
    memcpy(&bits, &sq, 4);
    float minNormal = 0.0f;
    memcpy(&minNormal, &kFltMinBits, 4);
    if ((bits & 0x7f800000) == 0x7f800000 || !(sq > minNormal)) { v[0] = v[1] = v[2] = v[3] = kZero; return; }
    const float r = 1.0f / sqrtf(sq);
    for (int i = 0; i < 4; ++i) v[i] *= r;
}

// the TU's ShouldRegenerate 0x8235ece8 as H1 has it (companion list first while TranslateRegenList, then the PC)
DWORD ShouldRegenTu(BYTE *inst, DWORD type, DWORD sub, DWORD flag, int *entry) {
    *entry = -1;
    if (g_regenList) {
        DWORD count = 0;
        if (CompanionRegen(inst, type, sub, flag, entry, &count)) return 1;
    }
    return reinterpret_cast<ShouldRegenFn>(kShouldRegen)(inst, type, sub, flag) & 0xff;
}

// 1 = the TU's T5 block ran (the stub returns the amount), 0 = the PC code goes on
int __cdecl T5Lethal(BYTE *inst, const BYTE *data) {
    P1dReadSwitches();
    if (!g_translateT5 || !inst || !data) return 0;
    const BYTE *brain = P1dBrain(inst);
    if (!brain) return 0;                     // the TU reads brain+0x2c64 unconditionally; the PC code checks
    CompanionNote(inst, "hit reaction (T5)");
    if (!CompanionData(inst)) return 0;
    float lp = 0.0f, amount = 0.0f;
    DWORD type = 0, sub = 0, flag = 0;
    __declspec(align(16)) float v[4] = {0.0f, 0.0f, 0.0f, 0.0f};
    __try {
        lp = *reinterpret_cast<const float *>(brain + 0x2c64);
        amount = *reinterpret_cast<const float *>(data + 0x4c);
        type = *reinterpret_cast<const DWORD *>(data + 0x50);
        sub = *reinterpret_cast<const DWORD *>(data + 0x64);
        flag = data[0x6e] ? 1 : 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
    if (lp > amount) return 0;                // TU 0x8230398c fcmpu f29, f31 / bgt: not lethal
    int entry = -1;
    if (ShouldRegenTu(inst, type, sub, flag, &entry)) return 0;   // TU 0x823039c0: regenerates -> the retail path
    bool fault = false;
    __try {
        const float *a = data[0x70] ? reinterpret_cast<const float *>(data + 0x10)
                                    : reinterpret_cast<const float *>(*reinterpret_cast<const BYTE *const *>(data + 0x30) + 0x20);
        const float *b = data[0x72] ? reinterpret_cast<const float *>(data) : reinterpret_cast<const float *>(inst + 0x20);
        for (int i = 0; i < 4; ++i) v[i] = a[i] - b[i];
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        fault = true;
    }
    if (fault) {
        if (N4cLine()) Log(0, "0.6.6 T5: access fault reading the hit vector of hit data 0x%08lx - PC code",
                           reinterpret_cast<DWORD>(data));
        return 0;
    }
    v[2] = kZero;                             // TU 0x82303a14 stfs 0 -> +8
    NormalizeChecked(v);
    if (type == kT5Type) {                    // TU 0x82303a24..0x82303a4c: v x (0, 0, -1, 0)
        const float x = v[1] * kT5Axis[2] - v[2] * kT5Axis[1], y = v[2] * kT5Axis[0] - v[0] * kT5Axis[2],
                    z = v[0] * kT5Axis[1] - v[1] * kT5Axis[0], w = v[3] * kT5Axis[3] - v[3] * kT5Axis[3];
        v[0] = x; v[1] = y; v[2] = z; v[3] = w;
    }
    reinterpret_cast<DeathSwitchFn>(kDeathSwitch)(inst, v, 1, 0, 1, kTuFinisherKind, 0);
    if (N4cLine()) {
        char who[96];
        Describe(inst, who, sizeof(who));
        Log(1, "0.6.6 T5: %s lethal hit type %lu subtype %lu flag %lu (amount %.1f, LP %.1f) with companion, "
               "ShouldRegenerate no -> death switch kind 7 as the TU 0x82303a74, direction (%.2f, %.2f, %.2f)%s", who,
            type, sub, flag, amount, lp, v[0], v[1], v[2], type == kT5Type ? " (type 0x19: crossed with (0, 0, -1))" : "");
    }
    return 1;
}

// jumped to from tru+0x23ad82: esi = instance, ebx = brain, pushes ebx / esi / edi done; eax / ecx / edx are free (the
// PC code loads them again), the FPU stack is empty
__declspec(naked) void T5Stub() {
    __asm {
        mov edi, dword ptr [ebp + 0xc]
        push edi
        push esi
        call T5Lethal
        add esp, 8
        test eax, eax
        jne t5_done
        cmp dword ptr [edi + 0x64], 1
        jmp dword ptr [g_t5BackTo]
    t5_done:
        fld dword ptr [edi + 0x4c]
        pop edi
        pop esi
        pop ebx
        mov esp, ebp
        pop ebp
        ret
    }
}

// ---- P1c
// data guard: true = the FIXED layout of tools/thrall_extension_fix.py (else logged once)
bool ExtFixed(const BYTE *comp) {
    DWORD recs = 0, steps = 0;
    const BYTE *table = nullptr;
    bool ok = false;
    __try {
        recs = *reinterpret_cast<const DWORD *>(comp + 0x2c);
        steps = *reinterpret_cast<const DWORD *>(comp + 0x24);
        table = *reinterpret_cast<const BYTE *const *>(comp + 0x20);
        ok = recs <= 64 && steps <= 64 && (steps == 0 || table);
        for (DWORD i = 0; ok && i < steps; ++i) {
            const WORD *e = reinterpret_cast<const WORD *>(table + i * 0x14);
            ok = e[0] < 0x1000 && e[1] < 0x1000;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = false;
    }
    if (!ok && InterlockedIncrement(&g_extUnfixedLogged) == 1)
        Log(0, "0.6.6: extension data not fixed - install work\\extfix_0711 / thrall_extension_fix (companion data "
               "0x%08lx: record count +0x2c 0x%08lx, step count +0x24 0x%08lx, step table 0x%08lx) - the Vaulted step "
               "table is not read, the PC animation choice runs (logged once)", reinterpret_cast<DWORD>(comp), recs, steps,
            reinterpret_cast<DWORD>(table));
    return ok;
}

// ---- K: the clock (TU brain+0xc bit 0x10 / +0x5080 / +0x5084)
const DWORD kClockStartCall = 0x00638d6f, kDifficultyFn = 0x006e7710;   // call tru+0x2e7710 (no arguments)
const DWORD kClockExitSite = 0x00638e76, kClockMain = 0x00638e81, kClockEpilogue = 0x00638efb;
const DWORD kTimeMs = 0x00e7f15c, kTimeMult = 0x00e7f188, kSlowMo = 0x00e7f1a0;   // TU [0x82efb458] +0xd4 / +0x100 / +0x118
const DWORD kClockBit = 0x10, kClockSpan = 5000;           // TU 0x822db1f4 / 0x822db20c cmplwi 0x1388
struct ClockEntry { const BYTE *inst; DWORD serial, clock; };
ClockEntry g_clock[64];
bool g_clockPlaced = false;
struct ClockSave { const BYTE *inst; float value; bool valid; } g_clockSave = {nullptr, 0.0f, false};
DWORD g_clockMainTo = kClockMain, g_clockEpilogueTo = kClockEpilogue, g_clockDifficultyTo = kDifficultyFn;
volatile LONG g_clockScaled = 0;

bool ClockOn() { return g_clockPlaced && g_vaultChain && g_translateVaulted && g_translateClock; }

ClockEntry *ClockFind(const BYTE *inst) {
    const DWORD serial = Rd(inst + 0x44);
    for (auto &e : g_clock)
        if (e.inst == inst) {
            if (e.serial == serial) return &e;
            e.inst = nullptr;                                  // the instance was reused: its old clock is gone
        }
    return nullptr;
}

void ClockSet(const BYTE *inst, DWORD clock) {
    ClockEntry *e = ClockFind(inst);
    if (!e) {
        ClockEntry *oldest = nullptr;
        for (auto &c : g_clock) {
            if (!c.inst) { e = &c; break; }
            if (!oldest || static_cast<LONG>(c.clock - oldest->clock) < 0) oldest = &c;
        }
        if (!e) {
            e = oldest;
            if (N4cLine()) Log(1, "0.6.6 clock: table full (64) - the clock of 0x%08lx ends at its next update",
                               reinterpret_cast<DWORD>(e->inst));
        }
    }
    e->inst = inst;
    e->serial = Rd(inst + 0x44);
    e->clock = clock;
}

// TU 0x822db1e8..0x822db248 (enemy update after the brain): save the multiplier, run / end the clock
void __cdecl ClockStart(BYTE *inst, BYTE *brain) {
    g_clockSave.valid = false;
    P1dReadSwitches();
    if (!ClockOn() || !inst || !brain) return;
    float *mult = reinterpret_cast<float *>(kTimeMult);
    g_clockSave.inst = inst;
    g_clockSave.value = *mult;                                 // brain+0x5084 = [+0x100]
    g_clockSave.valid = true;
    DWORD *flags = reinterpret_cast<DWORD *>(brain + 0xc);
    if (!(*flags & kClockBit)) return;
    const DWORD now = *reinterpret_cast<const DWORD *>(kTimeMs);
    ClockEntry *e = ClockFind(inst);
    const DWORD clock = e ? e->clock : 0;
    if (now - clock >= kClockSpan) {                           // TU 0x822db214..0x822db224
        if (e) e->inst = nullptr;
        *flags &= ~kClockBit;
        if (N4cLine()) {
            char who[96];
            Describe(inst, who, sizeof(who));
            Log(1, "0.6.6 clock: %s clock ended after %lu ms (brain+0xc bit 0x10 cleared as the TU 0x822db224)%s", who,
                now - clock, e ? "" : " - no clock entry (dropped)");
        }
        return;
    }
    const float slow = *reinterpret_cast<const float *>(kSlowMo);
    const float inv = static_cast<float>(1.0 / static_cast<double>(slow));   // TU 0x822db23c fdiv, frsp
    *mult = *mult * inv;                                       // TU 0x822db244 fmuls
    InterlockedIncrement(&g_clockScaled);
}

// TU 0x822db4e0: restore at the end of the main path
void __cdecl ClockEnd(BYTE *inst, BYTE *) {
    if (!g_clockSave.valid) return;
    g_clockSave.valid = false;
    if (g_clockSave.inst != inst) {
        if (N4cLine()) Log(0, "0.6.6 clock: update end of 0x%08lx after the start of 0x%08lx - time multiplier not "
                              "restored", reinterpret_cast<DWORD>(inst), reinterpret_cast<DWORD>(g_clockSave.inst));
        return;
    }
    *reinterpret_cast<float *>(kTimeMult) = g_clockSave.value;
}

// replaces `call tru+0x2e7710` at tru+0x238d6f: edi = instance, esi = brain (or 0); the call has no arguments, eax /
// ecx / edx are not live before it
__declspec(naked) void ClockStartStub() {
    __asm {
        push esi
        push edi
        call ClockStart
        add esp, 8
        jmp dword ptr [g_clockDifficultyTo]
    }
}

// jumped to from tru+0x238e76 (mov ecx, [esi+8]; shr ecx, 0x11; test cl, 1; jne tru+0x238efb): the TU's exit at
// 0x822db364 skips the restore
__declspec(naked) void ClockExitStub() {
    __asm {
        mov ecx, dword ptr [esi + 8]
        shr ecx, 0x11
        test cl, 1
        jne clock_exit
        jmp dword ptr [g_clockMainTo]
    clock_exit:
        mov byte ptr [g_clockSave.valid], 0
        jmp dword ptr [g_clockEpilogueTo]
    }
}

// jumped to from tru+0x238efb (pop edi; pop esi; pop ebx; mov esp, ebp; pop ebp; ret): edi = instance, esi = brain
__declspec(naked) void ClockEndStub() {
    __asm {
        push eax
        push esi
        push edi
        call ClockEnd
        add esp, 8
        pop eax
        pop edi
        pop esi
        pop ebx
        mov esp, ebp
        pop ebp
        ret
    }
}

// C: called from VaultedAnimStub (tru+0x24fdb9) with the Enter's inst, data and state data (ebx); 0xffffffff = the PC
// choice (step 0, switch off or unfixed data), else the TU 0x8232b3f8 result for step != 0 (0 = no animation)
void Q108Vault(const BYTE *inst);   // 0.6.13 (section "group C" below)
DWORD __cdecl VaultedAnim(BYTE *inst, const BYTE *data, BYTE *sd) {
    Q108Vault(inst);                   // 0.6.13: one read-only line per Vaulted Enter, independent of the switches
    P1dReadSwitches();
    if (!g_translateVaulted || !g_vaultChain) return 0xffffffff;
    const DWORD step = Rd(data + 0x44);
    *reinterpret_cast<DWORD *>(sd + 0xb8) = step;              // TU 0x8232b694 (0) / 0x8232b748 (data +0x44)
    CompanionNote(inst, "Vaulted Enter");
    const BYTE *comp = CompanionData(inst);
    BYTE *brain = const_cast<BYTE *>(P1dBrain(inst));
    if (brain && ClockOn()) {                                  // K: TU 0x8232b698..0x8232b6dc
        DWORD *flags = reinterpret_cast<DWORD *>(brain + 0xc);
        if (!(*flags & kClockBit)) {
            *flags |= kClockBit;
            const DWORD now = *reinterpret_cast<const DWORD *>(kTimeMs);
            ClockSet(inst, now);
            float *mult = reinterpret_cast<float *>(kTimeMult);
            const float before = *mult, slow = *reinterpret_cast<const float *>(kSlowMo);
            *mult = static_cast<float>(static_cast<double>(before) / static_cast<double>(slow));   // fdiv, frsp
            if (N4cLine()) {
                char who[96];
                Describe(inst, who, sizeof(who));
                Log(1, "0.6.6 clock: %s Vaulted Enter: brain+0xc bit 0x10 set, clock %lu ms, time multiplier %.4f -> "
                       "%.4f (slow motion factor %.4f) as the TU 0x8232b6c0..0x8232b6dc", who, now, before, *mult, slow);
            }
        }
    }
    if (comp && brain) *reinterpret_cast<DWORD *>(brain + 0x2c7c) = kVaultCompMark;   // TU 0x8232b7c4..0x8232b7d8
    if (!step) return 0xffffffff;                              // TU 0x8232b40c: step 0 = the retail choice (PC)
    DWORD r = 0;
    const char *how = "no companion -> no animation";
    if (comp) {
        if (!ExtFixed(comp)) return 0xffffffff;
        const DWORD count = Rd(comp + 0x24);
        if (count < step) {
            how = "step beyond the step table -> no animation";
        } else {
            r = Rd(comp + 0x20) + step * 0x14 - 0x14;          // TU 0x8232b4a4..0x8232b4b8 (1-based)
            how = "companion step table entry";
        }
    }
    if (N4cLine()) {
        char who[96];
        Describe(inst, who, sizeof(who));
        char pair[48] = "";
        if (r) {
            const DWORD w = Rd(reinterpret_cast<const void *>(r));
            _snprintf_s(pair, sizeof(pair), _TRUNCATE, " 0x%08lx (anim pair {%lu, %lu})", r, w & 0xffff, w >> 16);
        }
        Log(1, "0.6.6 vaulted: %s Vaulted Enter step %lu: %s%s%s as the TU 0x8232b3f8", who, step, how, pair,
            comp ? ", brain+0x2c7c = 0x0fffffff" : "");
    }
    return r;
}

// jumped to from tru+0x24fdb9: eax = data, ebx = state data, [esp+0xc] = inst, [esp+0x14] = data; edx / ecx are set by
// the moved instructions, the FPU stack is empty
__declspec(naked) void VaultedAnimStub() {
    __asm {
        push ebx
        push eax
        push dword ptr [esp + 0x14]
        call VaultedAnim
        add esp, 12
        cmp eax, 0xffffffff
        je va_pc
        mov ecx, eax
        jmp dword ptr [g_vaultAnimFlowTo]
    va_pc:
        mov eax, dword ptr [esp + 0x14]
        mov edx, dword ptr [eax + 0x3c]
        xor ecx, ecx
        jmp dword ptr [g_vaultAnimBackTo]
    }
}

// A: the call tru+0x23b421 -> tru+0x245de0 (cdecl inst, from, &rec[0x10], &rec[0x20], frames, 0, 0) of case 0xbe;
// the incoming record is p10 - 0x10 (lea edx, [eax+0x10] at tru+0x23b418)
BYTE *__cdecl RecCopyHook(DWORD inst, DWORD from, const BYTE *p10, const BYTE *p20, float frames, DWORD x34, DWORD x38) {
    BYTE *rec = reinterpret_cast<RecCopyFn>(kRecCopyFn)(inst, from, p10, p20, frames, x34, x38);
    P1dReadSwitches();
    if (!rec || !g_translateVaulted || !g_vaultChain || p20 != p10 + 0x10) return rec;
    const DWORD step = Rd(p10 - 0x10 + 0x34);
    *reinterpret_cast<DWORD *>(rec + 0x3c) = step;           // TU 0x823073d8 / 0x8230743c
    if (step && N4cLine()) {
        char who[96];
        Describe(reinterpret_cast<const BYTE *>(inst), who, sizeof(who));
        Log(1, "0.6.6 vaulted: %s message 0xbe with step %lu (record +0x34) -> copy +0x3c as the TU 0x8230743c", who, step);
    }
    return rec;
}

// B: SwitchToVaulted tru+0x20ed80(inst, "Vaulted", data) from tru+0x223fa2; record = [ebp+0xc] of tru+0x223f50
void __cdecl VaultSwitchLink(const BYTE *record, BYTE *data) {
    P1dReadSwitches();
    if (!g_translateVaulted || !g_vaultChain || !record || !data) return;
    *reinterpret_cast<DWORD *>(data + 0x44) = Rd(record + 0x3c);   // TU 0x8230447c / 0x823044dc
}

__declspec(naked) void VaultSwitchStub() {
    __asm {
        push dword ptr [esp + 0xc]
        push dword ptr [ebp + 0xc]
        call VaultSwitchLink
        add esp, 8
        jmp dword ptr [g_vaultSwitchTo]
    }
}

// D: the copy tru+0x24d350 (thiscall dst, src; ret 4) from Vaulted slot 3 tru+0x25a4a2
void __cdecl VaultCopyLink(BYTE *dst, const BYTE *src) {
    if (!g_translateVaulted || !g_vaultChain || !dst || !src) return;
    *reinterpret_cast<DWORD *>(dst + 0x44) = Rd(src + 0x44);       // TU 0x8232300c
}

__declspec(naked) void VaultCopyStub() {
    __asm {
        push ecx
        push dword ptr [esp + 8]
        push ecx
        call VaultCopyLink
        add esp, 8
        pop ecx
        jmp dword ptr [g_vaultCopyTo]
    }
}

// F: the retail strike's record tru+0x245e40 from tru+0x31d5cc, +0x34 = 0 as the TU 0x823e0294
void Q108StrikeRecord(const BYTE *target);   // 0.6.13 (section "group C" below)
BYTE *__cdecl StrikeRecordHook(BYTE *target, BYTE *player, const float *pos, const float *rot, float frames) {
    Q108StrikeRecord(target);                    // 0.6.13: read-only line (the 0xbe record of the vault-off strike)
    BYTE *rec = reinterpret_cast<RecordFn>(kRecord)(target, player, pos, rot, frames);
    if (rec && g_translateVaulted && g_vaultChain) *reinterpret_cast<DWORD *>(rec + 0x34) = 0;
    return rec;
}

void SetupN4c() {
    if (HexAt(0x005bcff9, "8b0dd094db00 52 8b14c1")) g_namesOk = true;
    const bool deathOk = FactsOk66(kDeathSwitchFacts, sizeof(kDeathSwitchFacts) / sizeof(kDeathSwitchFacts[0]), "death switch");
    const Fact regen[] = {
        {kShouldRegen, "8b442404 8b80d0020000 85c0 740c 8b08 8b81ec020000 85c0 7503 32c0 c3 8b9068010000 52 e8a755f9ff "
                       "83c404 85c0 74ea",
         "ShouldRegenerate tru+0x27f040 (cdecl inst, type, subtype, flag byte)"},
    };
    const bool regenOk = FactsOk66(regen, 1, "T5");
    // T5
    const Fact t5[] = {
        {0x0063ad50, "55 8bec 83e4f0 81ec24010000 53 56 8b7508 8b86d0020000 85c0 57 7508 33db 895c2414 eb0e 8b00 "
                     "8b88ec020000 894c2414 8bd9",
         "hit reaction tru+0x23ad50: inst esi, brain ebx, pushes ebx / esi / edi"},
        {kT5Site, "8b7d0c 837f6401 750b 8d8b902c0000 e82a50feff",
         "tru+0x23ad82: data edi, the [data+0x64] == 1 block (= retail 0x82305d8c)"},
        {0x0063adcc, "d9474c", "tru+0x23adcc: fld [edi+0x4c] (amount)"},
        {0x0063b312, "d944241c 5f c686502c000000 5e 5b 8be5 5d c3", "hit reaction epilogue tru+0x23b312"},
        {0x0063cad4, "80797000 8b4508 56 7405 8d5110 eb06 8b5130 83c220 80797200",
         "PC hit vector tru+0x23cad4: +0x70 -> +0x10 / [+0x30]+0x20, then +0x72"},
        {0x0063cb08, "7506 8b4d0c 83c120", "PC hit vector tru+0x23cb08: +0x72 = 0 -> inst+0x20"},
    };
    if (g_compOk && deathOk && regenOk && FactsOk66(t5, sizeof(t5) / sizeof(t5[0]), "T5")) {
        BYTE j[7] = {0xe9, 0, 0, 0, 0, 0x90, 0x90};
        const DWORD rel = reinterpret_cast<DWORD>(&T5Stub) - (kT5Site + 5);
        memcpy(j + 1, &rel, 4);
        if (WriteCode(kT5Site, j, sizeof(j))) g_t5 = true;
        else Log(0, "0.6.6 T5: jump at tru+0x23ad82 failed - PC hit reaction");
    }

    // P1c: every link's facts first, then all six written (or none)
    const Fact vault[] = {
        // C
        {0x00858e30, "f0fc6400", "Vaulted vtable 0x858e14 slot 7 = Enter tru+0x24fcf0"},
        {0x0064fcf0, "55 8bec 83e4f0 83ec54 8b4508 53 89442404 8b80d0020000 85c0 56 57 7506 89442410 eb0e 8b00 "
                     "8b88ec020000 894c2410 8bc1 8b4d0c 8b9488d4180000 8d0c4a 8b5514 69c99c010000 8d9c0173120000 83e3f0",
         "Vaulted Enter tru+0x24fcf0: inst [esp+0xc], brain, state data ebx"},
        {0x0064fd55, "8b02 83783800 89442414", "Vaulted Enter tru+0x24fd55: data eax = [esp+0x14]"},
        {kVaultAnimSite, "8b503c 33c9 85d2 7430 384840 7405 8d4a2c eb26 8b4034 83e801 7414 83e801 740a 83e801 7511 "
                         "8d4a24 eb08 8d4a20 eb03 8d4a28 85c9 7503 8d4a1c 85c9 890b 0f84cc000000",
         "Vaulted Enter tru+0x24fdb9: the retail animation choice (= TU 0x8232b414..0x8232b474), result ecx -> [ebx]"},
        {0x0064fdfe, "8b54240c", "Vaulted Enter tru+0x24fdfe: inst [esp+0xc]"},
        {0x0063419c, "899e7c2c0000", "brain+0x2c7c written by tru+0x23419c (no PC reader)"},
        {0x006375f7, "c7877c2c000000000000", "brain+0x2c7c written by tru+0x2375f7 (no PC reader)"},
        // F
        {0x0071d5c5, "50 56 0f29442464 e86f88f2ff 50 68be000000 56 e87361e9ff",
         "retail strike tru+0x31d5cc: record tru+0x245e40, message 0xbe"},
        {kRecord, "55 8bec 83e4f0 6a40 e8c3acf7ff d94518", "message record tru+0x245e40 (0x40 bytes, ring tru+0x1c0b10)"},
        {0x00645e7f, "d95830 83c404 8be5 5d c3", "message record tru+0x245e40: last store +0x30"},
        // A
        {0x0063b33a, "8b8fd0020000 33db", "enemy message handler tru+0x23b330: ebx = 0"},
        {0x0063c048, "1a", "enemy message handler: byte table 0x63bf8c, 0xbe -> index 26"},
        {0x0063bf24, "02b46300", "enemy message handler: jump table 0x63bebc index 26 -> tru+0x23b402"},
        {0x0063c07e, "32", "enemy message handler: byte table 0x63bf8c, 0xf4 -> index 50"},
        {0x0063bf84, "4bb46300", "enemy message handler: jump table 0x63bebc index 50 -> tru+0x23b44b"},
        {0x0063b402, "8b4604 8b08 3bf9 75c8 d94030 53 53 51 8d5020 d91c24 52 8d5010 8b4004 52 50 51 e8baa90000 6a01 50 57 "
                     "e8218bfeff 8b4e04 51 68be000000 57 e8429e0100",
         "case 0xbe tru+0x23b402: record copy tru+0x245de0, Vaulted tru+0x223f50, message 0xbe"},
        {kRecCopyFn, "55 8bec 83e4f0 6a40 e823adf7ff", "record copy tru+0x245de0 (cdecl, 7 arguments)"},
        {0x00645e2b, "894834 895038 8be5 5d c3", "record copy tru+0x245de0: +0x34 / +0x38 from the arguments, +0x3c left"},
        // B
        {0x00623f50, "55 8bec 83e4f0 8b550c 83ec5c 56 8b7508 3b32 7546", "tru+0x223f50 (inst, record [ebp+0xc], flag)"},
        {0x00623f9b, "50 684c7d8500 56 e8d9adfeff 83c410", "tru+0x223fa2: SwitchToVaulted(inst, \"Vaulted\", data)"},
        {kVaultSwitchFn, "8b4c2404 8b81d0020000 83ec0c", "SwitchToVaulted tru+0x20ed80"},
        {0x0060edbd, "c74424182c688500 c744241c50000000", "SwitchToVaulted: EnemyVaultedSwitchData 0x85682c, 0x50 bytes"},
        // D
        {0x00858e20, "70a46500", "Vaulted vtable slot 3 = data copier tru+0x25a470"},
        {0x0065a470, "56 57 8b7c240c 8d770f 83e6f0 7407 8bce e88b5bfeff 8b442410 c787900100002c688500 "
                     "c7879401000050000000 8b08 51 8bce e8a92effff 5f 5e c20800",
         "Vaulted data copier tru+0x25a470: ctor tru+0x240010, copy tru+0x24d350"},
        {0x0064d397, "8b513c 89503c 8a4940 884840 8be5 5d c20400", "copy tru+0x24d350: last field +0x40, ret 4"},
    };
    bool vOk = g_t1013Patched && FactsOk66(vault, sizeof(vault) / sizeof(vault[0]), "P1c");
    if (!g_t1013Patched) Log(0, "0.6.6 P1c: the 0.4 finisher site tru+0x31d895 is not patched (link E) - Vaulted chain off (PC)");
    if (vOk) {
        BYTE j[5] = {0xe9, 0, 0, 0, 0};
        const DWORD rel = reinterpret_cast<DWORD>(&VaultedAnimStub) - (kVaultAnimSite + 5);
        memcpy(j + 1, &rel, 4);
        int placed = 0;
        if (WriteCall(kStrikeRecCall, reinterpret_cast<const void *>(&StrikeRecordHook))) ++placed;
        if (WriteCall(kRecCopyCall, reinterpret_cast<const void *>(&RecCopyHook))) ++placed;
        if (WriteCall(kVaultSwitchCall, reinterpret_cast<const void *>(&VaultSwitchStub))) ++placed;
        if (WriteCall(kVaultCopyCall, reinterpret_cast<const void *>(&VaultCopyStub))) ++placed;
        if (WriteCode(kVaultAnimSite, j, sizeof(j))) ++placed;
        if (placed == 5) {
            g_vaultChain = true;
        } else {
            WriteCall(kStrikeRecCall, reinterpret_cast<const void *>(kRecord));
            WriteCall(kRecCopyCall, reinterpret_cast<const void *>(kRecCopyFn));
            WriteCall(kVaultSwitchCall, reinterpret_cast<const void *>(kVaultSwitchFn));
            WriteCall(kVaultCopyCall, reinterpret_cast<const void *>(kVaultCopyFn));
            const BYTE orig[5] = {0x8b, 0x50, 0x3c, 0x33, 0xc9};
            WriteCode(kVaultAnimSite, orig, sizeof(orig));
            Log(0, "0.6.6 P1c: only %d of 5 sites written - all back to the PC code", placed);
        }
    }

    // K: the clock (only with the chain: its Enter lines live in link C)
    const Fact clock[] = {
        {0x00638d40, "55 8bec 83e4f0 83ec24 53 56 57 8b7d08 f6471420 0f85a2010000 8b87d0020000 85c0 7504 33f6 eb08 8b00 "
                     "8bb0ec020000 e89ce90a00 85f6",
         "enemy update tru+0x238d40: inst edi, bit 0x20 exit, brain esi, call tru+0x2e7710 at tru+0x238d6f"},
        {kDifficultyFn, "a16492c500 8b8098ef0300 c3", "tru+0x2e7710 (no arguments)"},
        {kClockExitSite, "8b4e08 c1e911 f6c101 757a 83be3050000000 7409",
         "enemy update tru+0x238e76: brain+8 bit 0x20000 exit (TU 0x822db358..0x822db364), then brain+0x5030 (TU +0x5088)"},
        {0x00638ed4, "803dfc1fe90000 741e", "enemy update tru+0x238ed4: health print or the epilogue (TU 0x822db4ac)"},
        {0x00638ef3, "e80897feff 83c418", "enemy update tru+0x238ef3: health print tru+0x222600, then the epilogue"},
        {kClockEpilogue, "5f 5e 5b 8be5 5d c3", "enemy update epilogue tru+0x238efb"},
        {0x007228e9, "d90588f1e700 a158dbfa00 d9542404 56 d905a0f1e700 8b750c d9e8 57 def1 8b7d08 51 dec9 d91d88f1e700",
         "player update tru+0x3228e9: time multiplier 0xe7f188 saved, *= 1 / slow motion 0xe7f1a0 (the same idiom)"},
        {0x007229e1, "d9442414 8b0d58dbfa00 d91d88f1e700", "player update tru+0x3229e1: time multiplier restored"},
        {0x005d3e5c, "891d5cf1e700", "tru+0x1d3e5c: ms counter 0xe7f15c (TU [0x82efb458+0xd4])"},
    };
    if (g_vaultChain && FactsOk66(clock, sizeof(clock) / sizeof(clock[0]), "clock")) {
        BYTE e[7] = {0xe9, 0, 0, 0, 0, 0x90, 0x90};
        DWORD rel = reinterpret_cast<DWORD>(&ClockEndStub) - (kClockEpilogue + 5);
        memcpy(e + 1, &rel, 4);
        BYTE x[11] = {0xe9, 0, 0, 0, 0, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90};
        rel = reinterpret_cast<DWORD>(&ClockExitStub) - (kClockExitSite + 5);
        memcpy(x + 1, &rel, 4);
        int placed = 0;
        if (WriteCode(kClockEpilogue, e, sizeof(e))) ++placed;
        if (WriteCode(kClockExitSite, x, sizeof(x))) ++placed;
        if (WriteCall(kClockStartCall, reinterpret_cast<const void *>(&ClockStartStub))) ++placed;
        if (placed == 3) {
            g_clockPlaced = true;
        } else {
            const BYTE oe[7] = {0x5f, 0x5e, 0x5b, 0x8b, 0xe5, 0x5d, 0xc3};
            const BYTE ox[11] = {0x8b, 0x4e, 0x08, 0xc1, 0xe9, 0x11, 0xf6, 0xc1, 0x01, 0x75, 0x7a};
            WriteCall(kClockStartCall, reinterpret_cast<const void *>(kDifficultyFn));
            WriteCode(kClockExitSite, ox, sizeof(ox));
            WriteCode(kClockEpilogue, oe, sizeof(oe));
            Log(0, "0.6.6 clock: only %d of 3 sites written - all back to the PC code", placed);
        }
    }
    Log(1, "0.6.6: T5 %s (tru+0x23ad82, [Death] TranslateT5 %d), P1c Vaulted chain %s (F tru+0x31d5cc, E tru+0x31d895, A "
           "tru+0x23b421, B tru+0x223fa2, D tru+0x25a4a2, C tru+0x24fdb9; [Death] TranslateVaulted %d; step table only from "
           "fixed extension data), clock %s (tru+0x238d6f / +0x238e76 / +0x238efb; [Death] TranslateVaultedClock %d); "
           "read again at run time at most once per second. Not in 0.6.6: Vaulted 0xbe next step, step queries "
           "0x165..0x167, the clock's script commands",
        g_t5 ? "on" : "OFF", g_translateT5, g_vaultChain ? "on" : "OFF", g_translateVaulted,
        g_clockPlaced ? "on" : "OFF", g_translateClock);
}

// ---------------------------------------------------------------- 0.6.7: K-1 hit structures / knockback, K-7 chunks
// K-1 (docs Befund-K1-Umfallen-0911, ENGINE.md 13): the hit reaction tru+0x23ad50 picks a hit structure with the
//    selector tru+0x2159a0 (= retail 0x823042a8, cdecl (&s, msg, D)): msg+0x6e -> D+0x53c, else a table for damage
//    types 0..16 only, then tru+0x213c70(msg, s) may redirect to D+0x758; returns bit 30 of s+0x14. Lara's DLC 2 melee
//    types 18..27 get no structure, so the decision tru+0x223410 skips its flag tests (s = 0 -> heavy reaction).
//    The TU selector 0x82301dc0 takes the instance as well and, without +0x6e, first searches the companion's hit
//    records (0x822da918: [comp+0x2c] count, [comp+0x28] base, 0xc4 bytes each, +0 type == msg+0x50) and uses
//    record+0xc (0x82301de8..0x82301e48); only without a match the table; the D+0x758 redirect and the return are the
//    same (0x82301f08..0x82301fa8). The extension 870 holds records for 18..27 and 0 / 1 / 2 / 4 (Xbox = PC data).
//    Translated at the three PC callers: tru+0x223429 (decision, inst = argument 1), tru+0x23b157 (hit reaction,
//    inst = esi), tru+0x24f338 (tru+0x24f230 = TU 0x82329810, which got the instance as a new argument r10; on the PC
//    the instance is known only on the path from the knockback tru+0x220650 (return 0x6206e8, its [ebp+8]); the two
//    other callers tru+0x24f5ad / tru+0x25215d keep the PC selector - not 1:1, named).
//    Knockback tru+0x220650 (= retail 0x822f9990, TU 0x822f73a8): force factor fixed 3.0 (fmul qword [0x8415e8] at
//    tru+0x220940, fld dword [0x845338] = -3.0 at tru+0x220971); the TU takes record+0x40 of the same companion record
//    (0x822f77e4..0x822f783c, default [0x820526e8] = 3.0) for both (fneg at 0x822f7894). Not translated: the TU's
//    sideways direction for type 25 with a companion (0x822f7558..0x822f75bc) and brain+0x1254 |= 1 before the second
//    call (0x822f788c) - not checked against the PC.
// K-7: chunkdoll limit `cmp [0xecfc70], 4` at tru+0x296fa8 -> 8 as the TU 0x82376700 (retail 0x823769e0: 4). The
//    counter has no array behind it (only inc tru+0x2970b8 / dec tru+0x296e5c / this compare); the rest of the TU
//    function's head differs in its object call (not ported). Start only.
int g_hitMax = 3000;               // [Hit] MaxLines
int g_chunkLimit8 = 1;             // [Chunk] Limit8 (start only)
volatile LONG g_hitLines = 0;
bool g_hitSelPlaced = false, g_hitKbPlaced = false, g_hitDecPlaced = false, g_chunk8Placed = false;
const DWORD kHitSelect = 0x006159a0, kHitRedirect = 0x00613c70, kHitDecide = 0x00623410;
const DWORD kSelCallDecide = 0x00623429, kSelCallReaction = 0x0063b157, kSelCallLaunch = 0x0064f338;
const DWORD kDecideCall = 0x0063b183;
const DWORD kKbMulSite = 0x00620940, kKbNegSite = 0x00620971;
DWORD g_kbMulBack = 0x00620946, g_kbNegBack = 0x00620977;
const DWORD kChunkLimitImm = 0x00696fae;
typedef DWORD(__cdecl *HitSelectFn)(BYTE **s, BYTE *msg, BYTE *d);
typedef DWORD(__cdecl *HitRedirectFn)(BYTE *msg, BYTE *s);
typedef DWORD(__cdecl *HitDecideFn)(BYTE *inst, BYTE *msg, BYTE *d, float amount);
double g_kbForce = 3.0, g_kbA = 0.0, g_kbX = 0.0;
float g_kbNeg = -3.0f;
// the last selection, for the decision line (game thread only)
const BYTE *g_selInst = nullptr;
int g_selSource = 0;               // 0 none, 1 PC (table / +0x53c / redirect), 2 companion record (TU path)
DWORD g_selFlags = 0;
const char *const kSelSource[] = {"no structure", "PC table", "companion record (TU)"};

bool HitLine() {
    if (!g_hitLog) return false;
    const LONG n = InterlockedIncrement(&g_hitLines);
    if (n > g_hitMax) return false;
    if (n == g_hitMax) Log(1, "0.6.7: %ld hit lines - this is the last one ([Hit] MaxLines)", static_cast<LONG>(g_hitMax));
    return true;
}

// TU 0x82301de8..0x82301e48 / 0x822f77e4..0x822f783c: the first companion hit record whose +0 equals msg+0x50
const BYTE *CompanionHitRecord(const BYTE *inst, const BYTE *msg) {
    const BYTE *comp = CompanionData(inst);
    if (!comp || !msg) return nullptr;
    __try {
        const DWORD count = Rd(comp + 0x2c);
        const BYTE *base = *reinterpret_cast<const BYTE *const *>(comp + 0x28);
        if (!count || !base || count > 256) return nullptr;     // 256: plugin guard, the TU has none
        const LONG type = *reinterpret_cast<const LONG *>(msg + 0x50);
        for (DWORD i = 0; i < count; ++i)
            if (*reinterpret_cast<const LONG *>(base + i * 0xc4) == type) return base + i * 0xc4;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return nullptr;
}

DWORD __cdecl HitSelectTU(BYTE **s, BYTE *msg, BYTE *d, BYTE *inst, DWORD site) {
    P1dReadSwitches();
    const BYTE *rec = nullptr;
    if (g_hitTranslate && inst && msg && !msg[0x6e]) rec = CompanionHitRecord(inst, msg);
    DWORD r = 0;
    if (!rec) {
        r = reinterpret_cast<HitSelectFn>(kHitSelect)(s, msg, d) & 0xff;
        g_selSource = *s ? 1 : 0;
    } else {
        *s = const_cast<BYTE *>(rec) + 0xc;                                   // TU 0x82301e44
        if (reinterpret_cast<HitRedirectFn>(kHitRedirect)(msg, *s) & 0xff) *s = d + 0x758;   // 0x82301f08..0x82301f80
        r = *s ? (Rd(*s + 0x14) >> 30) & 1 : 0;                               // 0x82301f84..0x82301fa8
        g_selSource = (*s == d + 0x758) ? 1 : 2;
    }
    g_selInst = inst;
    g_selFlags = *s ? Rd(*s + 0x14) : 0;
    (void)site;
    return r;
}

// tru+0x223429: inside tru+0x223410(inst, msg, D, amount) - at entry of this stub inst is [esp+0x1c]
__declspec(naked) void HitSelStubDecide() {
    __asm {
        push 1
        push dword ptr [esp + 0x20]
        push dword ptr [esp + 0x14]
        push dword ptr [esp + 0x14]
        push dword ptr [esp + 0x14]
        call HitSelectTU
        add esp, 0x14
        ret
    }
}

// tru+0x23b157: inside the hit reaction tru+0x23ad50, esi = inst (tru+0x23ad5e)
__declspec(naked) void HitSelStubReaction() {
    __asm {
        push 2
        push esi
        push dword ptr [esp + 0x14]
        push dword ptr [esp + 0x14]
        push dword ptr [esp + 0x14]
        call HitSelectTU
        add esp, 0x14
        ret
    }
}

// tru+0x24f338: inside tru+0x24f230 (ebp frame); its caller tru+0x220650 (return 0x6206e8, ebp frame) has inst at
// [its ebp+8]; any other caller: inst 0 = the PC selector
__declspec(naked) void HitSelStubLaunch() {
    __asm {
        push 3
        mov eax, dword ptr [ebp + 4]
        cmp eax, 0x006206e8
        jne hl_other
        mov eax, dword ptr [ebp]
        mov eax, dword ptr [eax + 8]
        jmp hl_have
    hl_other:
        xor eax, eax
    hl_have:
        push eax
        push dword ptr [esp + 0x14]
        push dword ptr [esp + 0x14]
        push dword ptr [esp + 0x14]
        call HitSelectTU
        add esp, 0x14
        ret
    }
}

// tru+0x23b183: the decision tru+0x223410 (cdecl, returns al: 1 = heavy -> tru+0x220650, 0 = light -> tru+0x25ac80)
DWORD __cdecl HitDecideHook(BYTE *inst, BYTE *msg, BYTE *d, float amount) {
    g_selInst = nullptr;
    const DWORD r = reinterpret_cast<HitDecideFn>(kHitDecide)(inst, msg, d, amount) & 0xff;
    if (HitLine()) {
        char who[96];
        Describe(inst, who, sizeof(who));
        // 0.6.8: sub = msg+0x64 (the subtype, builder argument 17, fixed 2 at tru+0x31914b); msg+0x54 (argument 16,
        // fixed -1 at tru+0x31914d, only the entry list in tru+0x24f230 reads it) under its own name
        // 0.6.10: msg+0x44 (builder argument 5, the knockback speed when > 0) / msg+0x48 (argument 6) - Lara's contact
        // hit gives (int) A+0x10 / A+0x14 with [Hit] TranslateHitSpeed=1, else 0 / 0
        LONG type = -1, sub = -1, m54 = -1, m44 = -1, m48 = -1;
        __try {
            type = *reinterpret_cast<const LONG *>(msg + 0x50);
            sub = *reinterpret_cast<const LONG *>(msg + 0x64);
            m54 = *reinterpret_cast<const LONG *>(msg + 0x54);
            m44 = *reinterpret_cast<const LONG *>(msg + 0x44);
            m48 = *reinterpret_cast<const LONG *>(msg + 0x48);
        } __except (EXCEPTION_EXECUTE_HANDLER) {}
        const int src = (g_selInst == inst) ? g_selSource : 0;
        Log(1, "0.6.7 hit: %s type %ld sub %ld msg+0x54 %ld amount %.1f msg+0x44 %ld msg+0x48 %ld - structure: %s (flags "
               "+0x14 0x%08lx) -> %s ([Hit] Translate %d, TranslateHitSpeed %d)",
            who, type, sub, m54, amount, m44, m48, kSelSource[src], src ? g_selFlags : 0,
            r ? "HEAVY (knockback tru+0x220650)" : "light (MoveHit tru+0x25ac80)", g_hitTranslate, g_hitSpeed);
    }
    return r;
}

// tru+0x220940: TU 0x822f77e4..0x822f783c + fneg 0x822f7894 - record+0x40 or 3.0 for both factors
void __cdecl KnockbackForce(BYTE *inst, BYTE *msg) {
    P1dReadSwitches();
    float f = 3.0f;                                                          // TU [0x820526e8] = 0x40400000
    const BYTE *rec = g_hitKnock ? CompanionHitRecord(inst, msg) : nullptr;
    if (rec) {
        __try { f = *reinterpret_cast<const float *>(rec + 0x40); }
        __except (EXCEPTION_EXECUTE_HANDLER) { rec = nullptr; f = 3.0f; }
    }
    g_kbForce = f;
    g_kbNeg = -f;
    if (HitLine()) {
        char who[96];
        Describe(inst, who, sizeof(who));
        LONG type = -1;
        __try { type = *reinterpret_cast<const LONG *>(msg + 0x50); } __except (EXCEPTION_EXECUTE_HANDLER) {}
        Log(1, "0.6.7 knockback: %s type %ld force %.1f (%s, [Hit] TranslateKnockback %d)", who, type, f,
            rec ? "companion record +0x40 (TU)" : "3.0 (PC / no record)", g_hitKnock);
    }
}

// jumped to from tru+0x220940 (6 bytes): st0 = the factor ([esp+0x54]), st1 = the divisor; ebp = tru+0x220650's frame
__declspec(naked) void KbMulStub() {
    __asm {
        fstp qword ptr [g_kbA]
        fstp qword ptr [g_kbX]
        pushad
        pushfd
        push dword ptr [ebp + 0xc]
        push dword ptr [ebp + 8]
        call KnockbackForce
        add esp, 8
        popfd
        popad
        fld qword ptr [g_kbX]
        fld qword ptr [g_kbA]
        fmul qword ptr [g_kbForce]
        jmp dword ptr [g_kbMulBack]
    }
}

// jumped to from tru+0x220971 (6 bytes): the second factor, -force (TU fneg f1, f13)
__declspec(naked) void KbNegStub() {
    __asm {
        fld dword ptr [g_kbNeg]
        jmp dword ptr [g_kbNegBack]
    }
}

void SetupHit() {
    const Fact sel[] = {
        {kHitSelect, "8b4c2408 80796e00 56 8b742408 57 8b7c2414 7408 8d873c050000",
         "selector tru+0x2159a0 (cdecl &s, msg, D; msg+0x6e -> D+0x53c)"},
        {0x00615a1f, "8b16 52 51 e848e2ffff 83c408 84c0 7408 81c758070000 893e 8b36 85f6 7411 8b4614 c1e81e 83e001",
         "selector: redirect tru+0x213c70(msg, s) -> D+0x758, return bit 30 of s+0x14"},
        {0x00623410, "51 8b442410 57 8b7c2410 50 8d4c2408 57 51 c744241000000000 e87225ffff 8b442410",
         "decision tru+0x223410: selector call tru+0x223429, inst = argument 1"},
        {0x0063ad50, "55 8bec 83e4f0 81ec24010000 53 56 8b7508", "hit reaction tru+0x23ad50: esi = inst"},
        {0x0063b148, "50 8d542424 57 52 c744242c00000000 e844a8fdff 8b44242c",
         "hit reaction: selector call tru+0x23b157"},
        {0x0063b178, "51 8b4c242c d91c24 51 57 56 e88882feff 83c410 84c0 0f84a1000000",
         "hit reaction: decision call tru+0x23b183 (inst, msg, D, amount)"},
        {0x0064f230, "55 8bec 83e4f0 81ecc4000000", "tru+0x24f230: ebp frame"},
        {0x0064f32f, "56 0f298424d0000000 e86366fcff d9ee", "tru+0x24f230: selector call tru+0x24f338"},
        {0x00620650, "55 8bec 83e4f0 83ec54 8b4510 53 56 8b7508 57 8b7d0c",
         "knockback tru+0x220650: ebp frame, inst [ebp+8], msg [ebp+0xc]"},
        {0x006206e3, "e848eb0200", "knockback: call tru+0x24f230 (return 0x6206e8)"},
        {0x0062093c, "d9442454 dc0de8158400 def1", "knockback: factor 3.0 at tru+0x220940"},
        {0x0062096c, "e8df6bffff d90538538400 8b442460", "knockback: -3.0 at tru+0x220971"},
        {0x008415e8, "0000000000000840", "double 3.0 at 0x8415e8"},
        {0x00845338, "000040c0", "float -3.0 at 0x845338"},
    };
    if (!g_compOk) {
        Log(0, "0.6.7 hit: companion lookup not verified (0.6.5) - hit structures / knockback stay PC");
    } else if (FactsOk66(sel, sizeof(sel) / sizeof(sel[0]), "0.6.7 hit")) {
        int placed = 0;
        if (WriteCall(kSelCallDecide, reinterpret_cast<const void *>(&HitSelStubDecide))) ++placed;
        if (WriteCall(kSelCallReaction, reinterpret_cast<const void *>(&HitSelStubReaction))) ++placed;
        if (WriteCall(kSelCallLaunch, reinterpret_cast<const void *>(&HitSelStubLaunch))) ++placed;
        if (WriteCall(kDecideCall, reinterpret_cast<const void *>(&HitDecideHook))) ++placed;
        BYTE j1[6] = {0xe9, 0, 0, 0, 0, 0x90}, j2[6] = {0xe9, 0, 0, 0, 0, 0x90};
        DWORD rel = reinterpret_cast<DWORD>(&KbMulStub) - (kKbMulSite + 5);
        memcpy(j1 + 1, &rel, 4);
        rel = reinterpret_cast<DWORD>(&KbNegStub) - (kKbNegSite + 5);
        memcpy(j2 + 1, &rel, 4);
        if (WriteCode(kKbMulSite, j1, sizeof(j1))) ++placed;
        if (WriteCode(kKbNegSite, j2, sizeof(j2))) ++placed;
        if (placed == 6) {
            g_hitSelPlaced = g_hitDecPlaced = g_hitKbPlaced = true;
        } else {
            WriteCall(kSelCallDecide, reinterpret_cast<const void *>(kHitSelect));
            WriteCall(kSelCallReaction, reinterpret_cast<const void *>(kHitSelect));
            WriteCall(kSelCallLaunch, reinterpret_cast<const void *>(kHitSelect));
            WriteCall(kDecideCall, reinterpret_cast<const void *>(kHitDecide));
            const BYTE o1[6] = {0xdc, 0x0d, 0xe8, 0x15, 0x84, 0x00}, o2[6] = {0xd9, 0x05, 0x38, 0x53, 0x84, 0x00};
            WriteCode(kKbMulSite, o1, sizeof(o1));
            WriteCode(kKbNegSite, o2, sizeof(o2));
            Log(0, "0.6.7 hit: only %d of 6 sites written - all back to the PC code", placed);
        }
    }
    if (g_chunkLimit8) {
        if (HexAt(0x00696fa8, "833d70fcec0004 7c14 8b4710")) {
            const BYTE eight = 8;
            g_chunk8Placed = WriteCode(kChunkLimitImm, &eight, 1);
        } else {
            Log(0, "0.6.7 chunk: tru+0x296fa8 is not `cmp [0xecfc70], 4` - limit stays 4");
        }
    }
    Log(1, "0.6.7: hit structures %s (selector calls tru+0x223429 / +0x23b157 / +0x24f338 -> companion hit records as the "
           "TU 0x82301dc0, [Hit] Translate %d), decision log %s (tru+0x23b183), knockback %s (tru+0x220940 / +0x220971 "
           "-> record +0x40 as the TU 0x822f77e4, [Hit] TranslateKnockback %d), [Hit] Log %d (max %d lines); chunkdoll "
           "limit %s ([Chunk] Limit8 %d, start only). Not in 0.6.7: type-25 sideways knockback, brain+0x1254 |= 1 "
           "(0x822f788c), the instance for tru+0x24f230's callers tru+0x24f5ad / +0x25215d",
        g_hitSelPlaced ? "on" : "OFF", g_hitTranslate, g_hitDecPlaced ? "on" : "OFF", g_hitKbPlaced ? "on" : "OFF",
        g_hitKnock, g_hitLog, g_hitMax, g_chunk8Placed ? "8 (TU 0x82376700)" : "4 (PC)", g_chunkLimit8);
}

// ---------------------------------------------------------------- 0.6.8: K-1b impulse gate
// docs Befund-K1b-Entscheidung-0911 section 3: Lara's contact-hit sender tru+0x319050 (ecx = CombatManager, edi; ebx =
// the hit instance, receiver of 0x11c and 0x91; attack data A = [edi+0xc4]) sends, when A+0x10 > 0 and no special body
// was hit, the impulse message 0x91 (tru+0x3192da..+0x319394, send tru+0x31938c) and then continues at tru+0x319398.
// The TU 0x823e1870..0x823e1884 tests [[r28+0x10]]+4 bit 0x00400000 before that branch and jumps to 0x823e1934 (= PC
// tru+0x319398) when it is set; retail 0x823df318 and the PC have no such test. The impulse receiver tru+0x224c60
// throws the enemy up (tru+0x20eeb0) -> Fall on every punch. tru+0x3192da (lea edx, [esp+0x20]; push edx - 5 bytes)
// -> jmp ImpulseGateStub; FPU stack empty and esp equal at both ends (tru+0x3192d5 also jumps to tru+0x319398).
// Switch off = the two moved instructions and back to tru+0x3192df (PC).
const DWORD kImpulseSite = 0x007192da;
DWORD g_impulseBack = 0x007192df, g_impulseSkip = 0x00719398;
bool g_impulsePlaced = false;
volatile LONG g_impulseGated = 0;

// 1 = skip the impulse (TU), 0 = send it (PC)
DWORD __cdecl ImpulseGate(const BYTE *mgr, const BYTE *inst) {
    P1dReadSwitches();
    if (!g_hitImpulseGate || !inst) return 0;
    const BYTE *o = reinterpret_cast<const BYTE *>(Rd(inst + 0x10));      // TU lwz r11, 0x10(r28)
    const BYTE *d = o ? reinterpret_cast<const BYTE *>(Rd(o)) : nullptr;   // lwz r10, 0(r11)
    const DWORD flags = d ? Rd(d + 4) : 0;                                 // lwz r9, 4(r10)
    if (!(flags & 0x00400000)) return 0;                                   // rlwinm r8, r9, 0, 9, 9; bne
    const LONG n = InterlockedIncrement(&g_impulseGated);
    if (HitLine()) {
        char who[96];
        Describe(inst, who, sizeof(who));
        LONG type = -1;
        float force = 0.0f;
        __try {
            const BYTE *a = *reinterpret_cast<const BYTE *const *>(mgr + 0xc4);
            type = *reinterpret_cast<const LONG *>(a + 0xc);
            force = *reinterpret_cast<const float *>(a + 0x10);
        } __except (EXCEPTION_EXECUTE_HANDLER) {}
        Log(1, "0.6.8 impulse gate: %s type %ld force A+0x10 %.1f, [[inst+0x10]]+4 0x%08lx -> impulse 0x91 not sent "
               "(TU 0x823e1870, #%ld, [Hit] TranslateImpulseGate %d)", who, type, force, flags, n, g_hitImpulseGate);
    }
    return 1;
}

// jumped to from tru+0x3192da (5 bytes): ebx = the hit instance, edi = the CombatManager
__declspec(naked) void ImpulseGateStub() {
    __asm {
        pushad
        pushfd
        push ebx
        push edi
        call ImpulseGate
        add esp, 8
        test eax, eax
        jnz ig_skip
        popfd
        popad
        lea edx, [esp + 0x20]
        push edx
        jmp dword ptr [g_impulseBack]
    ig_skip:
        popfd
        popad
        jmp dword ptr [g_impulseSkip]
    }
}

void SetupImpulseGate() {
    const Fact f[] = {
        {0x0071907a, "8b5e04 f7431400004000 7403 8b5b4c", "sender tru+0x319050: ebx = hit instance"},
        {0x00719183, "681c010000 53 e8c2a5e9ff", "sender: hit message 0x11c to ebx"},
        {0x00719193, "8b87c4000000 d85010 dfe0 f6c405 0f8aef010000", "sender: A+0x10 > 0 test"},
        {0x007191fe, "0f84d6000000", "sender: branch to tru+0x3192da"},
        {0x00719212, "0f85c2000000", "sender: branch to tru+0x3192da"},
        {0x007192d5, "e9be000000 8d542420 52 e8dc5cd8ff", "sender: message 7 -> tru+0x319398; impulse branch tru+0x3192da"},
        {0x00719386, "6891000000 53 e8bfa3e9ff 83c454 eb02 ddd8 8b97c4000000", "sender: impulse 0x91 to ebx, tru+0x319398"},
    };
    if (!FactsOk66(f, sizeof(f) / sizeof(f[0]), "0.6.8 impulse gate")) {
        Log(0, "0.6.8 impulse gate: not placed - Lara's contact hit sends the impulse 0x91 to every target (PC)");
        return;
    }
    BYTE j[5] = {0xe9, 0, 0, 0, 0};
    const DWORD rel = reinterpret_cast<DWORD>(&ImpulseGateStub) - (kImpulseSite + 5);
    memcpy(j + 1, &rel, 4);
    g_impulsePlaced = WriteCode(kImpulseSite, j, sizeof(j));
    Log(1, "0.6.8 impulse gate %s (tru+0x3192da: no impulse 0x91 to targets with [[inst+0x10]]+4 bit 0x400000 as the TU "
           "0x823e1870, [Hit] TranslateImpulseGate %d, read again at run time at most once per second; one line per "
           "skipped impulse with [Hit] Log %d)",
        g_impulsePlaced ? "on" : "OFF (write failed)", g_hitImpulseGate, g_hitLog);
}

// ---------------------------------------------------------------- 0.6.9: K-8 / melee kill log points (log only)
// docs Befund-K8-Kombo-1011 sections 5 / 6.3 (main workspace). Each part calls the original code with the same
// arguments and only writes a line; nothing in the game changes.
// 1. Death state slot 8 tru+0x26c950 (TU 0x8232cd50): after the state timer the tune record r = tru+0x214610
//    (brain+0x168) (edi from tru+0x26c9dc); r+0x46 (u16) != 0 -> chunkdoll build tru+0x296f90(inst) at tru+0x26c9f9
//    (cdecl, al = built; TU 0x823766c0). Call redirected to ChunkBuildStub. Line: instance, r+0x46 / +0x48 / +0x4c,
//    result, chunkdoll counter [0xecfc70] before / after, physics lock [[0xa037f4]+0x20f8], LP. [Death] Log.
// 2. Lara's contact-hit sender tru+0x319050: tru+0x3190ad calls the hit-list add tru+0x2e6990 (thiscall ecx = the
//    CombatManager edi, argument = target ebx, ret 4): the first empty of the 8 slots +0xa4..+0xc0 takes the target,
//    al = 0 when it is already in the list or the list is full - only al = 1 lets the hit message 0x11c / the impulse
//    go out (tru+0x3190b4). Call redirected to HitListStub. Line: target, result (added slot k / refused: already in
//    slot k / list full), the 8 slots, Lara's chart record (machine 1 [[0xfadb58]+0xf10], record [machine+0x510],
//    index = position in [[machine+4]+0xc], as TruMenu combo.trace), attack data A = [edi+0xc4] (+4 damage, +0xc type,
//    +0x10 force), [States] Translate1004. The same target / result / record again within 1 s is counted, not logged.
//    [Hit] Log (cap [Hit] MaxLines, shared with the 0.6.7 / 0.6.8 hit lines).
// 3. The death switch tru+0x241650 (= retail 0x82327a18, TU 0x823258c8; cdecl inst, vec16 *, u8, ptr, u8, kind, u8):
//    entry hook (6 bytes push ebp; mov ebp, esp; and esp, -16 into a trampoline). It ends in tru+0x23d6e0(inst,
//    EnemyState_Death 0x8ae904, &data, 0) at tru+0x24170b (= retail 0x8230e290): a request {data,
//    "EnemyDeathSwitchData", 0x20} to the enemy's state machine brain+0x1254 through tru+0x271d30 (= retail 0x82349b90
//    = TU 0x82349468: tru+0x271080 files the request, then unless the current state's slot +0x40 (inst, 1) says no,
//    machine+4 |= 1 and tru+0x271c10 switches at once). Line: enemy, kind (data +0x14), layer-0 state before -> after
//    the call (after = the switch happened inside the call), LP, result al, caller (tru+0x... or this plugin's own
//    0.6.1 / 0.6.5 / 0.6.6 calls). The call site tru+0x24170b itself is not patched: TruMenu's ai.kill checks its
//    bytes. [Death] Log.
// Task 2 (TU 0x823258c8 against retail 0x82327a18 / PC tru+0x241650): the TU inlined retail's helper 0x8230e290 - the
//    same call 0x82349468(brain+0x1254, inst, brain+0x11e0, Death 0x82779bf8, {data, "EnemyDeathSwitchData", 0x20}, 0)
//    as retail 0x82349b90(...) - the rest differs only in stack offsets and shifted constants with equal values
//    ([0x8207d538] = 0, [0x82052664] = -1.0f). The PC calls the same helper (tru+0x23d6e0 -> tru+0x271d30), so the
//    request through brain+0x1254 is already the PC's way: nothing to translate, no [Death] TranslateSwitchRequest.
const DWORD kChunkBuild = 0x00696f90, kChunkBuildCall = 0x0066c9f9, kChunkCount = 0x00ecfc70;
const DWORD kHitListAdd = 0x006e6990, kHitListCall = 0x007190ad;
const DWORD kDeathCheckRet = 0x0062042f;      // the game's death check tru+0x220380 calls the switch at tru+0x22042a
typedef DWORD(__cdecl *ChunkBuildFn)(BYTE *inst);
typedef DWORD(__fastcall *HitListAddFn)(BYTE *mgr, int edx, BYTE *target);   // thiscall, ret 4
bool g_chunkBuildPlaced = false, g_hitListPlaced = false, g_switchPlaced = false;
bool g_k8MachineOk = false;        // Lara's chart machine 1 at [[0xfadb58]+0xf10] (TruMenu combo.trace check)
DeathSwitchFn g_oDeathSwitch = nullptr;
BYTE *g_k8Code = nullptr;
HMODULE g_self = nullptr;
DWORD g_imageEnd = 0;
volatile LONG g_k8Lines = 0, g_chunkBuilds = 0, g_switches = 0;
const LONG kK8MaxLines = 2000;
CRITICAL_SECTION g_k8Lock;

bool K8DeathLine() {
    if (!g_deathLog) return false;
    const LONG n = InterlockedIncrement(&g_k8Lines);
    if (n > kK8MaxLines) return false;
    if (n == kK8MaxLines) Log(1, "0.6.9: %ld chunk build / death switch lines - this is the last one", kK8MaxLines);
    return true;
}

bool InImage(DWORD p) { return p >= kImageBase && p < g_imageEnd; }

// name of a state object ((char *)[obj+8], as TruMenu's enemy labels); "(none)" for 0, "0x..." when not readable
void StateName(DWORD obj, char *out, size_t size) {
    if (!obj) { strcpy_s(out, size, "(none)"); return; }
    _snprintf_s(out, size, _TRUNCATE, "0x%08lx", obj);
    if (!InImage(obj)) return;
    const DWORD name = Rd(reinterpret_cast<const void *>(obj + 8));
    if (!InImage(name)) return;
    char s[32];
    size_t i = 0;
    __try {
        const char *p = reinterpret_cast<const char *>(name);
        for (; i + 1 < sizeof(s) && p[i]; ++i) {
            if (p[i] < 0x20 || p[i] > 0x7e) return;
            s[i] = p[i];
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
    s[i] = 0;
    if (i >= 2) strcpy_s(out, size, s);
}

// Lara's chart machine 1: record index (position in [[machine+4]+0xc]) of [machine+0x510]; -1 unknown
int LaraRecord() {
    if (!g_k8MachineOk) return -1;
    const BYTE *gt = reinterpret_cast<const BYTE *>(Rd(reinterpret_cast<const void *>(kGameTrackerPtr)));
    const BYTE *machine = gt ? reinterpret_cast<const BYTE *>(Rd(gt + 0xf10)) : nullptr;
    const DWORD rec = machine ? Rd(machine + 0x510) : 0;
    const BYTE *defs = machine ? reinterpret_cast<const BYTE *>(Rd(machine + 4)) : nullptr;
    const BYTE *arr = defs ? reinterpret_cast<const BYTE *>(Rd(defs + 0xc)) : nullptr;
    if (!rec || !arr) return -1;
    __try {
        for (int i = 0; i < 4096; ++i)
            if (reinterpret_cast<const DWORD *>(arr)[i] == rec) return i;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return -1;
}

DWORD PhysLock() {
    const BYTE *phys = reinterpret_cast<const BYTE *>(Rd(reinterpret_cast<const void *>(kPhysPtr)));
    return phys ? Rd(phys + 0x20f8) : 0xffffffff;
}

// ---- 1. chunkdoll build of the Death state
DWORD __cdecl ChunkBuildLog(BYTE *inst, const BYTE *record) {
    P1dReadSwitches();
    const LONG before = static_cast<LONG>(Rd(reinterpret_cast<const void *>(kChunkCount)));
    const DWORD lock = PhysLock();
    const DWORD r = reinterpret_cast<ChunkBuildFn>(kChunkBuild)(inst);
    const LONG n = InterlockedIncrement(&g_chunkBuilds);
    if (K8DeathLine()) {
        char who[96];
        Describe(inst, who, sizeof(who));
        const BYTE *brain = P1dBrain(inst);
        const DWORD w44 = Rd(record + 0x44), w48 = Rd(record + 0x48);
        Log(1, "0.6.9 chunk build: %s in the Death state (tru+0x26c9f9 -> tru+0x296f90, TU 0x8232ce28 -> 0x823766c0): record "
               "+0x46 %lu, +0x48 %lu, +0x4c %.2f -> %s; chunkdoll count [0xecfc70] %ld -> %ld (limit %d), physics lock "
               "0x%lx%s, LP %.1f (#%ld, [Death] Log %d)",
            who, w44 >> 16, w48 & 0xff, RdFloat(record + 0x4c), (r & 0xff) ? "BUILT" : "not built (al 0)", before,
            static_cast<LONG>(Rd(reinterpret_cast<const void *>(kChunkCount))), g_chunk8Placed ? 8 : 4, lock,
            (lock != 0xffffffff && (lock & 1)) ? " (inside the physics step!)" : "",
            brain ? RdFloat(brain + 0x2c64) : 0.0f, n, g_deathLog);
    }
    return r;
}

// tru+0x26c9f9: [esp+4] = inst (the pushed argument), edi = the tune record
__declspec(naked) void ChunkBuildStub() {
    __asm {
        push edi
        push dword ptr [esp + 8]
        call ChunkBuildLog
        add esp, 8
        ret
    }
}

// ---- 2. hit-list add of Lara's contact hit
struct HitListSeen { const BYTE *target; int cls, rec; DWORD tick; LONG same; };
HitListSeen g_hlSeen[4];
int g_hlNext = 0;
volatile LONG g_hlContacts = 0;

void HitListLine(const BYTE *mgr, const BYTE *target, DWORD r, const DWORD *before) {
    DWORD after[8] = {0};
    int slot = -1, cls = 0;                    // 0 added, 1 already in, 2 full, 3 refused (other)
    __try {
        for (int k = 0; k < 8; ++k) after[k] = reinterpret_cast<const DWORD *>(mgr + 0xa4)[k];
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    const DWORD t = reinterpret_cast<DWORD>(target);
    for (int k = 0; k < 8 && slot < 0; ++k)
        if (r ? (!before[k] && after[k] == t) : before[k] == t) slot = k;
    if (r) cls = 0;
    else if (slot >= 0) cls = 1;
    else {
        int used = 0;
        for (int k = 0; k < 8; ++k) if (before[k]) ++used;
        cls = used == 8 ? 2 : 3;
    }
    const int rec = LaraRecord();
    const DWORD now = GetTickCount();
    const LONG contact = InterlockedIncrement(&g_hlContacts);
    LONG same = 0;
    EnterCriticalSection(&g_k8Lock);
    int i = 0;
    for (; i < 4; ++i)
        if (g_hlSeen[i].target == target) break;
    if (i < 4 && g_hlSeen[i].cls == cls && g_hlSeen[i].rec == rec && now - g_hlSeen[i].tick < 1000) {
        ++g_hlSeen[i].same;
        LeaveCriticalSection(&g_k8Lock);
        return;
    }
    if (i == 4) {
        i = g_hlNext;
        g_hlNext = (g_hlNext + 1) % 4;
        g_hlSeen[i].same = 0;
    }
    same = g_hlSeen[i].same;
    g_hlSeen[i].target = target;
    g_hlSeen[i].cls = cls;
    g_hlSeen[i].rec = rec;
    g_hlSeen[i].tick = now;
    g_hlSeen[i].same = 0;
    LeaveCriticalSection(&g_k8Lock);
    if (!HitLine()) return;
    char who[96], list[200], res[48];
    Describe(target, who, sizeof(who));
    list[0] = 0;
    size_t used = 0;
    for (int k = 0; k < 8; ++k) {
        const int w = _snprintf_s(list + used, sizeof(list) - used, _TRUNCATE, "%s%s", k ? " " : "",
                                  after[k] == 0 ? "-" : after[k] == t ? "T" : "x");
        if (w > 0) used += static_cast<size_t>(w);
    }
    if (cls == 0) _snprintf_s(res, sizeof(res), _TRUNCATE, "added in slot %d", slot);
    else if (cls == 1) _snprintf_s(res, sizeof(res), _TRUNCATE, "REFUSED: already in slot %d", slot);
    else if (cls == 2) strcpy_s(res, sizeof(res), "REFUSED: list full");
    else strcpy_s(res, sizeof(res), "REFUSED (al 0)");
    LONG type = -1;
    float damage = 0.0f, force = 0.0f;
    __try {
        const BYTE *a = *reinterpret_cast<const BYTE *const *>(mgr + 0xc4);
        if (a) {
            damage = *reinterpret_cast<const float *>(a + 4);
            type = *reinterpret_cast<const LONG *>(a + 0xc);
            force = *reinterpret_cast<const float *>(a + 0x10);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    Log(1, "0.6.9 hit list: contact -> %s at Lara record %d, attack type %ld damage %.1f force %.1f -> %s (tru+0x3190ad -> "
           "tru+0x2e6990%s); list +0xa4 [%s] (T = this target, x = other); %ld repeat(s) of this target's previous line "
           "not logged; [States] Translate1004 %d (contact #%ld)",
        who, rec, type, damage, force, res, r ? ": hit message 0x11c follows" : ": no hit message", list, same,
        g_translate1004, contact);
}

DWORD __cdecl HitListLog(BYTE *mgr, BYTE *target) {
    P1dReadSwitches();
    const bool want = g_hitLog != 0;
    DWORD before[8] = {0};
    if (want) {
        __try {
            for (int k = 0; k < 8; ++k) before[k] = reinterpret_cast<const DWORD *>(mgr + 0xa4)[k];
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
    const DWORD r = reinterpret_cast<HitListAddFn>(kHitListAdd)(mgr, 0, target);
    if (want) HitListLine(mgr, target, r & 0xff, before);
    return r;
}

// tru+0x3190ad: thiscall ecx = the CombatManager, [esp+4] = the target; the original returns with ret 4
__declspec(naked) void HitListStub() {
    __asm {
        push dword ptr [esp + 4]
        push ecx
        call HitListLog
        add esp, 8
        ret 4
    }
}

// ---- 3. the death switch (entry hook; the original runs through the trampoline with the same arguments)
DWORD __cdecl DeathSwitchHook(BYTE *inst, const float *vec, DWORD a2, DWORD a3, DWORD a4, DWORD kind, DWORD a6) {
    const DWORD ret = reinterpret_cast<DWORD>(_ReturnAddress());
    P1dReadSwitches();
    const bool want = g_deathLog != 0;
    const BYTE *brain = want ? P1dBrain(inst) : nullptr;
    const DWORD stateBefore = brain ? Rd(brain + 0x125c) : 0;
    const float lp = brain ? RdFloat(brain + 0x2c64) : 0.0f;
    const DWORD r = g_oDeathSwitch(inst, vec, a2, a3, a4, kind, a6);
    const LONG n = InterlockedIncrement(&g_switches);
    if (want && K8DeathLine()) {
        char who[96], before[32], after[32], caller[64];
        Describe(inst, who, sizeof(who));
        StateName(stateBefore, before, sizeof(before));
        const DWORD stateAfter = brain ? Rd(brain + 0x125c) : 0;
        StateName(stateAfter, after, sizeof(after));
        MEMORY_BASIC_INFORMATION mi;
        const bool ours = VirtualQuery(reinterpret_cast<const void *>(ret), &mi, sizeof(mi)) &&
                          mi.AllocationBase == reinterpret_cast<void *>(g_self);
        if (ours) _snprintf_s(caller, sizeof(caller), _TRUNCATE, "TruShadowCombat (0x%08lx)", ret);
        else if (ret == kDeathCheckRet) strcpy_s(caller, sizeof(caller), "death check tru+0x220380");
        else _snprintf_s(caller, sizeof(caller), _TRUNCATE, "tru+0x%lx", ret - 5 - kImageBase);
        Log(1, "0.6.9 death switch: %s kind %lu (args %lu / 0x%lx / %lu / %lu) from %s, LP %.1f, state %s -> %s%s, request "
               "to brain+0x1254 %s (tru+0x241650 = TU 0x823258c8, #%ld, [Death] Log %d)",
            who, kind, a2 & 0xff, a3, a4 & 0xff, a6 & 0xff, caller, lp, before, after,
            stateAfter != stateBefore ? " (switched inside the call)" : " (not switched yet)",
            (r & 0xff) ? "accepted (al 1)" : "al 0", n, g_deathLog);
    }
    return r;
}

bool FactsOk69(const Fact *f, size_t count, const char *part) {
    for (size_t i = 0; i < count; ++i)
        if (!HexAt(f[i].at, f[i].hex)) {
            Log(0, "0.6.9 %s: %s at 0x%08lx does not match - log point not placed", part, f[i].what, f[i].at);
            return false;
        }
    return true;
}

void SetupK8Log() {
    g_imageEnd = kImageBase;
    __try {
        const BYTE *b = reinterpret_cast<const BYTE *>(kImageBase);
        const IMAGE_NT_HEADERS32 *nt = reinterpret_cast<const IMAGE_NT_HEADERS32 *>(b + Rd(b + 0x3c));
        g_imageEnd = kImageBase + nt->OptionalHeader.SizeOfImage;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    InitializeCriticalSection(&g_k8Lock);
    // the chart machine (as TruMenu combo.trace kCtChecks): [[0xfadb58]+0xf10] / +0xf14 into the per-frame update
    g_k8MachineOk = HexAt(0x00768c50, "a158dbfa00 56 8bb0100f0000 57 8bb8140f0000 8bce e8f6f10100");
    const Fact chunk[] = {
        {0x0066c95c, "8b7d08 8b87d0020000 85c0 897c240c", "Death slot 8 tru+0x26c950: inst = [ebp+8] -> [esp+0xc]"},
        {0x0066c9d0, "8b8368010000 50 e8347cfaff 8bf8 83c404 85ff 0f84f2000000 66837f4600 0f84e7000000 8b4c240c 51 "
                     "e892a50200 83c404 84c0 0f84ce000000",
         "Death slot 8: record tru+0x214610(brain+0x168) in edi, +0x46 != 0 -> call tru+0x296f90(inst) at tru+0x26c9f9"},
        {kChunkBuild, "51 57 8b7c240c 6880010000 57 e84fc7f1ff", "chunkdoll build tru+0x296f90 (cdecl inst)"},
        {0x00696fa8, "833d70fcec00", "chunkdoll build: counter [0xecfc70]"},
    };
    const Fact hit[] = {
        {0x00719061, "8bf9", "sender tru+0x319050: edi = ecx = the CombatManager"},
        {0x007190aa, "53 8bcf e8ded8fcff 84c0 0f8439030000", "sender: hit-list add tru+0x2e6990(ebx) at tru+0x3190ad"},
        {kHitListAdd, "53 8b5c2408 56 32c0 57 33d2 8db1a4000000 8b3e 85ff 7415 3bfb 741a 83c201 83c604 83fa08 7ceb 5f 5e "
                      "5b c20400 899c91a4000000 b001 5f 5e 5b c20400",
         "hit-list add tru+0x2e6990 (thiscall, 8 slots +0xa4, ret 4)"},
    };
    if (!g_k8MachineOk) Log(0, "0.6.9: chart machine read at 0x768c50 does not match - hit-list lines without Lara's record");
    if (FactsOk69(chunk, sizeof(chunk) / sizeof(chunk[0]), "chunk build"))
        g_chunkBuildPlaced = WriteCall(kChunkBuildCall, reinterpret_cast<const void *>(&ChunkBuildStub));
    if (FactsOk69(hit, sizeof(hit) / sizeof(hit[0]), "hit list"))
        g_hitListPlaced = WriteCall(kHitListCall, reinterpret_cast<const void *>(&HitListStub));
    if (FactsOk69(kDeathSwitchFacts, sizeof(kDeathSwitchFacts) / sizeof(kDeathSwitchFacts[0]), "death switch")) {
        g_k8Code = static_cast<BYTE *>(VirtualAlloc(nullptr, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
        if (g_k8Code) {
            memcpy(g_k8Code, reinterpret_cast<const void *>(kDeathSwitch), 6);   // push ebp; mov ebp, esp; and esp, -16
            g_k8Code[6] = 0xe9;
            const DWORD rel = (kDeathSwitch + 6) - (reinterpret_cast<DWORD>(g_k8Code) + 11);
            memcpy(g_k8Code + 7, &rel, 4);
            DWORD old = 0;
            if (VirtualProtect(g_k8Code, 4096, PAGE_EXECUTE_READ, &old)) {
                g_oDeathSwitch = reinterpret_cast<DeathSwitchFn>(g_k8Code);
                BYTE j[6] = {0xe9, 0, 0, 0, 0, 0x90};
                const DWORD to = reinterpret_cast<DWORD>(&DeathSwitchHook) - (kDeathSwitch + 5);
                memcpy(j + 1, &to, 4);
                g_switchPlaced = WriteCode(kDeathSwitch, j, sizeof(j));
            } else {
                Log(0, "0.6.9 death switch: code page protection failed (%lu) - not placed", GetLastError());
            }
        } else {
            Log(0, "0.6.9 death switch: no code page (%lu) - not placed", GetLastError());
        }
    }
    Log(1, "0.6.9 log points (nothing changed in the game): chunkdoll build of the Death state %s (tru+0x26c9f9), hit-list "
           "add of Lara's contact hit %s (tru+0x3190ad, Lara's record %s), death switch %s (entry tru+0x241650); [Hit] Log "
           "%d, [Death] Log %d (live). TU 0x823258c8 = retail 0x82327a18 with the request helper 0x8230e290 (= PC "
           "tru+0x23d6e0) inlined: the PC already requests Death through brain+0x1254 - nothing to translate",
        g_chunkBuildPlaced ? "on" : "OFF", g_hitListPlaced ? "on" : "OFF", g_k8MachineOk ? "read" : "not read",
        g_switchPlaced ? "on" : "OFF", g_hitLog, g_deathLog);
}

// ---------------------------------------------------------------- 0.6.10: K-8b knockback speed of Lara's contact hit
// docs Befund-K8b-Art21-1011 sections 3 / 5 (main workspace). Lara's contact-hit sender tru+0x319050 (= retail
// 0x823def28, TU 0x823e1488) builds the hit message 0x11c with tru+0x23c9b0 (= TU 0x8230afd8; argument 5 -> msg+0x44,
// argument 6 -> msg+0x48, argument 7 -> msg+0x40: tru+0x23c9d4..+0x23c9e6). Retail and the PC push 0 / 0 / 0 at
// tru+0x319169..+0x31916e (`6a 00` x 3: argument 7, 6, 5 in push order). The TU passes
// r7 = (int) A+0x10 (fctiwz f28, 0x823e169c..0x823e16a8) and r8 = (int) A+0x14 (fctiwz f29, 0x823e16ac..0x823e16c8),
// r9 = 0; A = the attack data (TU: its 10-word copy at r1+0x100; PC: eax = [CombatManager+0xc4] from tru+0x319133,
// st0 = A+4 for the `fstp [esp]` at tru+0x319170). The knockback tru+0x220650 (= TU 0x822f73a8) takes v = (int)
// msg+0x44 when > 0, else the record's s+0x30 (fild [edi+0x44] tru+0x220716..+0x22073e); records with s+0x30 = 0
// (types 21 / 26) never knocked back on the PC. Every other receiver of this 0x11c gets the values too - as on the Xbox.
// tru+0x319169 (6 bytes, three `push 0`) -> jmp HitSpeedStub + nop; the stub pushes the same three dwords (TU values or
// 0 / 0 / 0) and returns to tru+0x31916f. FPU stack untouched (cvttss2si is SSE), esp the same as the PC at the return,
// ecx is only the placeholder pushed at tru+0x31916f and overwritten by `fstp [esp]`, the flags are dead (push / fstp /
// mov / call follow). No branch in tru+0x319050..+0x319400 and no rel32 call / jmp in the exe targets
// tru+0x31916a..+0x31916f (pe_dis.py + pe_callers.py, 10.11.).
// cvttss2si truncates toward zero as fctiwz; for NaN / out of range it gives 0x80000000 (fctiwz: 0x7fffffff for large
// positive values) - irrelevant for Lara's forces 0..1250.
// Not 1:1 / still open: the TU's type-27 substitute record [CM+0xc8] of the same block (0x823e160c..0x823e1674) - the
// TU copies it over A for type 27 first; the stub reads A as the PC does. Once that substitute is ported, A+0x10 /
// A+0x14 come from the substitute copy.
const DWORD kHitSpeedSite = 0x00719169;
DWORD g_hitSpeedBack = 0x0071916f;
bool g_hitSpeedPlaced = false;

// jumped to from tru+0x319169: eax = A, st0 = A+4; switch read again by P1dReadSwitches (every contact through the
// 0.6.9 hit-list hook and every hit selection)
__declspec(naked) void HitSpeedStub() {
    __asm {
        cmp dword ptr [g_hitSpeed], 0
        je hs_pc
        push 0                                  // argument 7 -> msg+0x40 (TU r9 = 0)
        cvttss2si ecx, dword ptr [eax + 0x14]   // TU fctiwz f29 (A+0x14)
        push ecx                                // argument 6 -> msg+0x48 (TU r8)
        cvttss2si ecx, dword ptr [eax + 0x10]   // TU fctiwz f28 (A+0x10, the attack force)
        push ecx                                // argument 5 -> msg+0x44 (TU r7)
        jmp dword ptr [g_hitSpeedBack]
    hs_pc:
        push 0
        push 0
        push 0
        jmp dword ptr [g_hitSpeedBack]
    }
}

void SetupHitSpeed() {
    const Fact f[] = {
        {0x00719133, "8bc1 ddd8 0fb64801 d94004 51 8b4c2418 6a00 6a00 6a00 6a00 6a02 6aff 51 8b4c2438 8b4904 51 "
                     "8d4c2474 51 8b480c",
         "sender tru+0x319050: eax = A (tru+0x319133, not written up to tru+0x319169), st0 = A+4"},
        {0x00719160, "6a00 6aff 6a00 51 6aff 6a00 6a00 6a00 51 d91c24 6a00 52 8b1594f0e700 52 e82e38f2ff",
         "sender: push 0 / 0 / 0 at tru+0x319169 (arguments 7 / 6 / 5), builder call tru+0x31917d"},
        {0x0063c9b0, "56 6880000000 e85541f8ff d9442418", "builder tru+0x23c9b0: argument 1 at [esp+0xc]"},
        {0x0063c9d4, "8b54241c 894838 8b4c2420 895044 8b542424 894848 8b4c2428 895040",
         "builder: argument 5 -> msg+0x44, 6 -> msg+0x48, 7 -> msg+0x40"},
    };
    if (!FactsOk66(f, sizeof(f) / sizeof(f[0]), "0.6.10 hit speed")) {
        Log(0, "0.6.10 hit speed: not placed - Lara's contact hit gives msg+0x44 / +0x48 = 0 / 0 (PC)");
        return;
    }
    BYTE j[6] = {0xe9, 0, 0, 0, 0, 0x90};
    const DWORD rel = reinterpret_cast<DWORD>(&HitSpeedStub) - (kHitSpeedSite + 5);
    memcpy(j + 1, &rel, 4);
    g_hitSpeedPlaced = WriteCode(kHitSpeedSite, j, sizeof(j));
    Log(1, "0.6.10 hit speed %s (tru+0x319169: Lara's contact hit gives the hit message 0x11c msg+0x44 = (int) A+0x10 and "
           "msg+0x48 = (int) A+0x14 as the TU 0x823e169c..0x823e16c8 - the knockback tru+0x220650 runs with msg+0x44 when "
           "> 0, else s+0x30; [Hit] TranslateHitSpeed %d, read again at run time at most once per second; the values "
           "show in the `0.6.7 hit:` line). Not ported: the TU's type-27 substitute record [CM+0xc8] of the same block",
        g_hitSpeedPlaced ? "on" : "OFF (write failed)", g_hitSpeed);
}

// ---------------------------------------------------------------- 0.6.12: state 1015 exit (finisher Y kill) as the TU
// Q37 (main workspace docs\Befund-Translate1015Exit-1111.md; follows docs\Befund-Translate1008-1111.md section 4).
// Record 742 [1004 1015] = the finisher Y attack on a downed thrall (743 [1008] = the move after it, 0.6.11).
// PC = retail: table entry 1015 at tru.exe 0x8b1a48 = {1015, tru+0x35e0e0, 0, tru+0x35e0f0, 0, 0, 0}. Slot 0 ->
// tru+0x31d8c0 (CM = [gameTracker+0x504]: targeter 6 object -> handle CM+0x48 / +0x4c through tru+0x1b39f0 unless
// [t+0x14] & 0x400000; CM+0x1fc |= 0x40000000), slot 2 -> tru+0x2e66d0 (handle CM+0x48 cleared, CM+0x1fc &=
// ~0x40000000) = retail 0x8245bcd8 / 0x8245bd48.
// TU table 0x827589cc = {0x8245fde8 (= retail with targeter TU 7 = PC slot 6), 0, 0x8245fe58, 0, 0, 0}. The TU-new exit
// 0x8245fe58 ("[CombatManager::ThrallFatalityEnd] Enemy Didn't Chunk from Fatality, Chunking them explicitly on exit."
// at 0x82072148, an argument of the empty print 0x82455a38; the string is not in the PC exe): handle CM+0x48 valid
// ([object+0x44] == CM+0x4c) -> v = player +0x20 - target +0x20 (all 4 lanes, vsubfp128), lane 2 (z) = 0.0
// ([0x8207d538]); death switch 0x823258c8(target, r4 0, r5 0, r6 0, kind r7 0, r8 1, v1 = v) = PC tru+0x241650(target,
// &v, 0, 0, 0, 0, 1) (argument mapping of 0.6.1); then the retail clear (= tru+0x2e66d0, the PC slot 2 run after it).
// Death kind 0 (static, both exes): the switch sets LP 0 (PC tru+0x237850 / TU inline + 0x822f8dd8 = tru+0x22e180) and
// fills data +0x14 = 0, +0x19 = (kind 5 or 7) = 0, +0x1a = 0, +0x1b = 1 (TU 0x82325930..0x82325998, the same
// stores in PC tru+0x241650); the Death Enter (PC tru+0x26c500, TU 0x8232c818, retail 0x8232d820) plays the effect "death"
// (kind 5 = "vehicle death") and, with +0x19 = 0, takes the default orientation instead of the hit vector. The PC-only
// +0x19 call tru+0x218020 (only when inst+0x298 == 0, and it returns at once then) is not reached with kind 0. The PC
// itself uses kind 0 for damage type 0xe (tru+0x213b40). So kind 0 = LP 0 + Death state + "death" effect on both.
// [States] Translate1015Exit (default 0, read again at run time): 0 = only the PC slot 2 (clear), the line says what
// the TU would do ("off (would)"); 1 = the kill as the TU, then the PC slot 2. One line per exit with a valid target
// (target, LP and layer-0 state before / after, Lara's chart record). [States] Enabled=0: record untouched.
Trace g_t1015x = {"state 1015 slot 2 (TU 0x8245fe58 ThrallFatalityEnd: kill the finisher's target, then the clear)"};

bool CheckState1015Blocks() {
    struct { DWORD at; const char *hex; const char *what; } const s[] = {
        {0x008b1a48, "f7030000 e0e07500 00000000 f0e07500 00000000 00000000 00000000",
         "PC table entry 1015 {1015, tru+0x35e0e0, 0, tru+0x35e0f0, 0, 0, 0} (tru.exe 0x8b1a48)"},
        {kState1015Pc, "a158dbfa00 8b8804050000 e9d0f7fbff", "PC 1015 slot 0 tru+0x35e0e0 -> tru+0x31d8c0([gameTracker+0x504])"},
        {0x0071d8c0, "56 6a06 8bf1 e8d6f0ffff 85c0 7423 50 e8fc60e9ff 83c404 85c0 7416 f7401400004000 750d 50 8d4648 50 "
                     "e80261e9ff 83c408 818efc01000000000040 5e c3",
         "tru+0x31d8c0: targeter 6 object -> handle CM+0x48 / +0x4c unless flag 0x400000"},
        {kState1015PcSlot2, "a158dbfa00 8b8804050000 e9d085f8ff", "PC 1015 slot 2 tru+0x35e0f0 -> tru+0x2e66d0([gameTracker+0x504])"},
        {0x006e66d0, "56 8bf1 8d4648 6a00 50 e812d3ecff 81a6fc010000ffffffbf 83c408 5e c3",
         "tru+0x2e66d0: handle CM+0x48 cleared, CM+0x1fc &= ~0x40000000"},
        {0x005b39d0, "8b4c2404 85c9 740e 8b01 85c0 7408 8b5044 3b5104 7402 33c0 c3",
         "handle check tru+0x1b39d0 ([object+0x44] == id, as HandleObject)"},
        {0x005b39f0, "8b442408 85c0 8b4c2404 8901 7407 8b4044 894104 c3 c7410400000000 c3",
         "handle set tru+0x1b39f0 ({object, object+0x44})"},
        {0x0076d9e0, "f7461400004000 7505 8d4620 eb08 a194f0e700 83c020", "player pointer [0xe7f094] + 0x20 (tru+0x36d9ee)"},
        {kDeathSwitch, kDeathSwitchFacts[0].hex, "death switch tru+0x241650 (cdecl 7 arguments, data +0x14 kind, +0x19 = "
                                                 "kind 5 / 7, +0x1a / +0x1b)"},
        {0x0066c844, "807b1b00 7417 837c243005 57 7507 e829c6faff eb05 e8f2c5faff",
         "Death Enter tru+0x26c844: data +0x1b -> kind 5 \"vehicle death\" tru+0x218e80, else \"death\" tru+0x218e50"},
    };
    for (const auto &c : s)
        if (!HexAt(c.at, c.hex)) {
            Log(0, "state 1015 exit: %s at 0x%08lx does not match - not wrapped", c.what, c.at);
            return false;
        }
    return true;
}

// TU 0x8245fe58 (slot 2 = exit of state 1015)
void __cdecl State1015Slot2(void *agent) {
    ReadSwitches();
    const bool apply = g_translate1015Exit != 0;
    __try {
        BYTE *cm = *reinterpret_cast<BYTE **>(GameTracker() + 0x504);
        BYTE *t = cm ? HandleObject(reinterpret_cast<const DWORD *>(cm + 0x48)) : nullptr;
        if (t) {
            BYTE *player = Player();
            __declspec(align(16)) float v[4];
            const float *pp = Pos(player), *tp = Pos(t);
            for (int k = 0; k < 4; ++k) v[k] = pp[k] - tp[k];     // vsubfp128 v61 = player +0x20 - target +0x20
            v[2] = kZero;                                         // stfs [0x8207d538] into lane 2
            const BYTE *brain = P1dBrain(t);
            const float lpBefore = brain ? RdFloat(brain + 0x2c64) : 0.0f;
            const DWORD stateBefore = brain ? Rd(brain + 0x125c) : 0;
            DWORD r = 0;
            if (apply) r = reinterpret_cast<DeathSwitchFn>(kDeathSwitch)(t, v, 0, 0, 0, 0, 1);
            const float lpAfter = brain ? RdFloat(brain + 0x2c64) : 0.0f;
            const DWORD stateAfter = brain ? Rd(brain + 0x125c) : 0;
            char who[96], before[32], after[32];
            Describe(t, who, sizeof(who));
            StateName(stateBefore, before, sizeof(before));
            StateName(stateAfter, after, sizeof(after));
            if (apply)
                TraceLog(g_t1015x, true, 1, "ON: target %s, death switch kind 0 (target, &v, 0, 0, 0, 0, 1), v = %.1f %.1f "
                         "%.1f -> al %lu; LP %.1f -> %.1f, state %s -> %s; Lara record %d; then the PC clear tru+0x2e66d0",
                         who, v[0], v[1], v[2], r & 0xff, lpBefore, lpAfter, before, after, LaraRecord());
            else
                TraceLog(g_t1015x, true, 0, "off (would): target %s, LP %.1f, state %s - the TU would switch it to Death "
                         "kind 0 now (v = %.1f %.1f %.1f); Lara record %d; only the PC clear tru+0x2e66d0", who, lpBefore,
                         before, v[0], v[1], v[2], LaraRecord());
        } else {
            TraceLog(g_t1015x, true, 2, "%s no valid target in CM+0x48 (empty or stale handle) - nothing, as the TU; the PC "
                     "clear tru+0x2e66d0", apply ? "ON:" : "off:");
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log(0, "state 1015 slot 2: access fault - kill skipped, the PC clear runs");
    }
    if (g_orig1015Slot2) g_orig1015Slot2(agent);
}

// ---------------------------------------------------------------- 0.6.13: group C (Q108 log, Q109 assist, Q68, Q99 A)
// Main workspace docs\Befund-Gruppe-C-1211.md (static, PC tru.exe = retail logic; VAs):
//  * adrenaline mode = CM+0x1fc bit 27 (start 0x7189c0 / end 0x718ad0 from the tick 0x718bd0, which needs action 37:
//    generalbank DTP 47 binding #105, set 17 <- source 9 = pad code 9 = XINPUT_GAMEPAD_RIGHT_THUMB = R3; keyboard = the
//    key in registry value "9" of HKCU\Software\Crystal Dynamics\Tomb Raider: Underworld\Input);
//  * vault-off strike = state 1014 slot 0 0x71d3c0: target of targeter 5, enemy query 0x165 (answered by the enemy query
//    0x632200 from its tune chain brain+0x168, record +0x54 - in every enemy state), message 0xbe, meter empty, bit 21.
//    Entered (0.6.14, group L: chart RECORD 786 holds state id 1014) from the combat records 711 / 724 / 730 by
//    {500,538,1} meter full, {2000,2001,1}, {2000,2011,1}, {700,701,0}, {1500,1502,0}, {2300,2302,1} (prompt) and
//    {150,150,46} = action 46 held (pad code 1 = X). Group C read the transitions into chart RECORD 1014 (state 612,
//    {500,518,1} = message 0x1c9 <= 100 ms + animation end / time >= chart parameter 354 = 5 ticks) - not the strike;
//  * circle = reticle [CM+0] word +0x40 bit 6 (set at the strike look 0x70db20), pointer +0x20 / +0x24 (start 0x6e6a70:
//    random point at distance 256 - radius), radius +0x30 = [0xfae8d0] (script native setter 0x77a7d0); bit 7 =
//    |pointer| < radius, computed in 0x6f2f20 every frame before the stick (actions 2 / 3 x tuning +0x454 x frame ms /
//    1000) and mouse (actions 0x10 / 0x11 x 5.0) move it;
//  * shot = RT edge (action 33, +0x630 & 0x10) in the 1014 tick 0x718d00 -> message 0x19b; success = bit 7 when the
//    bullet hit 0x7198d0 runs (0x719ce8: event 0x36 + reticle reset 0x6e6ca0, else event 0x37 + strike end 0x718fd0);
//  * lock-on target switch 0x71cb10 (hard lock, bit 10, not bit 21): right stick (actions 2 / 3) + an accumulator of the
//    MOUSE axes (0x71cd07 / 0x71cd20, actions 0x10 / 0x11, CM+0x20c / +0x210, clamp +-1.5, decay 2.0 x [0xe7f194]);
//    |v| >= tuning +0x2a0 (0.2) -> search in that direction 0x71a740 + switch 0x714e80;
//  * permanent chunk piece: 0x696f69 `75 0f` (record bit 0 -> body release 0x48ea80, the piece stays) - Q99 option A.
const DWORD kQ108Tune = 0x00fad764, kQ108Radius = 0x00fae8d0, kQ108HudCircle = 0x00fae8ae, kQ108World = 0x00e7f1a0,
            kQ108Player = 0x00e7f1d4, kQ108Actions = 0x00a02b68;
const DWORD kQ108ReticleCall = 0x0070d863, kQ108ReticleFn = 0x006f2f20;
const DWORD kQ108LockCallX = 0x0071cd07, kQ108LockCallY = 0x0071cd20, kQ108Analog = 0x00480e50;
const DWORD kQ108ChunkJcc = 0x00696f69;
const DWORD kQ108BitWindow = 0x00200000, kQ108BitFull = 0x00400000, kQ108BitMode = 0x08000000, kQ108BitLock = 0x400;

int g_adrLog = 1;                         // [Adrenaline] Log (read-only lines; start only)
volatile LONG g_adrAssist = 0;            // [Adrenaline] AssistPointer (Q109; read again at run time)
volatile LONG g_lockMouse = 1;            // [Lock] MouseSwitch (Q68; 1 = the game: mouse moves switch targets)
volatile LONG g_lockKeyRight = 0, g_lockKeyLeft = 0;   // [Lock] RightKey / LeftKey (virtual-key code, 0 = off)
volatile LONG g_chunkRemoveLast = 0;      // [Chunk] RemoveLastPiece (Q99 option A; read again at run time)
bool g_q108ReadOk = false, g_assistHooked = false, g_lockHooked = false, g_chunkJccOk = false;
BYTE g_chunkJccNow = 0x75;                // the byte at 0x696f69 as this plugin left it
typedef SHORT(WINAPI *KeyStateFn)(int);
typedef HWND(WINAPI *ForegroundFn)();
typedef DWORD(WINAPI *WindowPidFn)(HWND, DWORD *);
KeyStateFn g_keyState = nullptr;          // user32 resolved at run time (the plugin imports only kernel32)
ForegroundFn g_foreground = nullptr;
WindowPidFn g_windowPid = nullptr;

struct Q108State {
    bool ok;
    DWORD flags;                          // CM+0x1fc
    float meter, max;                     // CM+0x3c, [[0xfad764]+0x2d0]
    DWORD ret;                            // reticle [CM+0] word +0x40
    float px, py, pz, radius;             // reticle +0x20 / +0x24 / +0x28 pointer, +0x30 radius
    DWORD hud;                            // byte 0xfae8ae (circle highlight, 0x718e23 / 0x718e57)
    float world, player;                  // [0xe7f1a0] world time scale, [0xe7f1d4] player time scale
    DWORD dopp;                           // byte [gameTracker+0x1244]
};

void Q108Read(Q108State *s) {
    memset(s, 0, sizeof(*s));
    const BYTE *gt = reinterpret_cast<const BYTE *>(Rd(reinterpret_cast<const void *>(kGameTrackerPtr)));
    const BYTE *cm = gt ? reinterpret_cast<const BYTE *>(Rd(gt + 0x504)) : nullptr;
    if (!cm) return;
    s->ok = true;
    s->flags = Rd(cm + 0x1fc);
    s->meter = RdFloat(cm + 0x3c);
    const BYTE *tune = reinterpret_cast<const BYTE *>(Rd(reinterpret_cast<const void *>(kQ108Tune)));
    s->max = tune ? RdFloat(tune + 0x2d0) : 0.0f;
    const BYTE *r = reinterpret_cast<const BYTE *>(Rd(cm));
    if (r) {
        s->ret = Rd(r + 0x40) & 0xffff;
        s->px = RdFloat(r + 0x20);
        s->py = RdFloat(r + 0x24);
        s->pz = RdFloat(r + 0x28);
        s->radius = RdFloat(r + 0x30);
    }
    s->hud = Rd(reinterpret_cast<const void *>(kQ108HudCircle)) & 0xff;
    s->world = RdFloat(reinterpret_cast<const void *>(kQ108World));
    s->player = RdFloat(reinterpret_cast<const void *>(kQ108Player));
    s->dopp = Rd(gt + 0x1244) & 0xff;
}

double Q108Dist(const Q108State &s) {
    return sqrt(static_cast<double>(s.px) * s.px + static_cast<double>(s.py) * s.py + static_cast<double>(s.pz) * s.pz);
}

void Q108Text(const Q108State &s, char *out, size_t size) {
    _snprintf_s(out, size, _TRUNCATE,
                "meter %.1f / %.0f, CM+0x1fc 0x%08lx (full %d, mode %d, window %d, hard lock %d), reticle 0x%04lx (circle "
                "%d, in zone %d), pointer %.1f %.1f |%.1f| radius %.1f, HUD 0xfae8ae %lu, world %.3f, player %.3f, "
                "doppelganger %lu, Lara record %d",
                s.meter, s.max, s.flags, (s.flags & kQ108BitFull) ? 1 : 0, (s.flags & kQ108BitMode) ? 1 : 0,
                (s.flags & kQ108BitWindow) ? 1 : 0, (s.flags & kQ108BitLock) ? 1 : 0, s.ret, (s.ret & 0x40) ? 1 : 0,
                (s.ret & 0x80) ? 1 : 0, s.px, s.py, Q108Dist(s), s.radius, s.hud, s.world, s.player, s.dopp, LaraRecord());
}

// game thread: Vaulted Enter of an enemy (VaultedAnim, the 0.6.6 stub at 0x64fdb9)
void Q108Vault(const BYTE *inst) {
    if (!g_adrLog || !g_q108ReadOk) return;
    Q108State s;
    Q108Read(&s);
    char who[96], text[420];
    Describe(inst, who, sizeof(who));
    Q108Text(s, text, sizeof(text));
    Log(1, "0.6.13 Q108 vault: %s enters Vaulted (5 s enemy window) - %s", who, text);
}

// game thread: the 0xbe record of the vault-off strike (state 1014 slot 0, call 0x71d5cc): the strike reached its
// message - next 0x6e6670 empties the meter and bit 21 is set (0x71d5e2 / 0x71d5e7)
void Q108StrikeRecord(const BYTE *target) {
    if (!g_adrLog || !g_q108ReadOk) return;
    char who[96];
    Describe(target, who, sizeof(who));
    Log(1, "0.6.13 Q108 strike 1014: message 0xbe record for %s (0x71d5cc) - the meter is emptied and bit 21 set next",
        who);
}

// game thread: state 1014 slots 0 / 2 / 3 (k = 0 / 1 / 2) outside the TU strike - the PC handler with lines around it
void Q108Run1014(int k, void *agent, StateFn orig) {
    if (!g_adrLog || !g_q108ReadOk) {
        if (orig) orig(agent);
        return;
    }
    Q108State a;
    Q108Read(&a);
    bool shot = false;
    if (k == 2 && a.ok) {   // the shot conditions of 0x718d00 (0x718d03..0x718d69): bit 21, reticle bit 6, gates, RT edge
        const BYTE *dev = reinterpret_cast<const BYTE *>(Rd(reinterpret_cast<const void *>(kQ108Actions)));
        const BYTE *list = dev ? reinterpret_cast<const BYTE *>(Rd(dev + 0x18)) : nullptr;
        const BYTE *act = list ? reinterpret_cast<const BYTE *>(Rd(list)) : nullptr;
        const DWORD rt = act ? Rd(act + 0x630) : 0;
        const bool gates = (Rd(reinterpret_cast<const void *>(0x008ab4e6)) & 0xff) != 0 &&
                           !(Rd(reinterpret_cast<const void *>(0x00e7f144)) & 1) &&
                           (Rd(reinterpret_cast<const void *>(0x00e7f143)) & 0xff) != 4;
        shot = (a.flags & kQ108BitWindow) && (a.ret & 0x40) && (rt & 0x10) && gates;
    }
    if (orig) orig(agent);
    if (k == 0) {
        Q108State b;
        Q108Read(&b);
        char before[420], after[420];
        Q108Text(a, before, sizeof(before));
        Q108Text(b, after, sizeof(after));
        const bool started = !(a.flags & kQ108BitWindow) && (b.flags & kQ108BitWindow);
        Log(1, "0.6.13 Q108 state 1014 enter (vault-off strike 0x71d3c0): %s - before: %s; after: %s", started
            ? "STARTED (0xbe sent, meter emptied, bit 21 set)"
            : (a.flags & kQ108BitWindow) ? "nothing - bit 21 was already set (one strike per meter filling)"
                                         : "nothing - no target of targeter 5, target flag 0x400000, query 0x165 = 0 or "
                                           "[[0xe7f094]+0x280]+0x14 = 0 (not told apart)",
            before, after);
    } else if (shot) {
        const double d = Q108Dist(a);
        Log(1, "0.6.13 Q108 headshot SHOT (RT edge in the 1014 tick 0x718d00 -> message 0x19b): pointer %.1f %.1f |%.1f| "
               "radius %.1f -> %s; meter %.1f, world %.3f, player %.3f",
            a.px, a.py, d, a.radius, (a.ret & 0x80) ? "IN the zone (bit 7) - success when the hit lands with bit 7"
                                                   : "OUT of the zone (bit 7 clear) - the hit ends the strike (event 0x37)",
            a.meter, a.world, a.player);
    }
}

// game thread, Q109: 0x70d863 calls 0x6f2f20 (thiscall, reticle) only while reticle bit 6 is set; with
// [Adrenaline] AssistPointer=1 the pointer is pulled to at most half the radius before the game's bit-7 test
typedef void(__fastcall *ReticleFn)(BYTE *reticle, int);
DWORD g_assistLastTick = 0;
LONG g_assistPulls = 0;
void __fastcall AssistReticle(BYTE *r, int edx) {
    if (g_adrAssist && r) {
        __try {
            const WORD f = *reinterpret_cast<const WORD *>(r + 0x40);
            float *p = reinterpret_cast<float *>(r + 0x20);
            const float rad = *reinterpret_cast<const float *>(r + 0x30);
            const DWORD now = GetTickCount();
            const bool fresh = now - g_assistLastTick > 500;   // the call runs every frame while the circle is up
            g_assistLastTick = now;
            if (fresh) g_assistPulls = 0;
            if ((f & 0x40) && rad > 0.0f) {
                const double d = sqrt(static_cast<double>(p[0]) * p[0] + static_cast<double>(p[1]) * p[1] +
                                      static_cast<double>(p[2]) * p[2]);
                const double keep = 0.5 * rad;
                if (d > keep) {
                    const double s = d > 0.0 ? keep / d : 0.0;
                    if (++g_assistPulls == 1)
                        Log(1, "0.6.13 Q109 assist: pointer %.1f %.1f |%.1f| pulled to |%.1f| (radius %.1f) - bit 7 stays "
                               "set ([Adrenaline] AssistPointer=1)", p[0], p[1], d, keep, rad);
                    p[0] = static_cast<float>(p[0] * s);
                    p[1] = static_cast<float>(p[1] * s);
                    p[2] = static_cast<float>(p[2] * s);
                }
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
    reinterpret_cast<ReticleFn>(kQ108ReticleFn)(r, edx);
}

// game thread, Q68: the two analog reads of the lock-on target switch 0x71cb10 (0x71cd07 action 0x10 / 0x71cd20 action
// 0x11 = mouse x / y). MouseSwitch=0 -> 0 (the mouse no longer switches targets; the camera keeps its own mouse read);
// RightKey / LeftKey pressed -> one frame +1.0 / -1.0 on x, the game's own threshold / search / switch / sound
typedef float(__fastcall *AnalogFn)(void *input, int, int action);
bool GameInForeground() {
    if (!g_foreground || !g_windowPid) return false;
    HWND w = g_foreground();
    DWORD pid = 0;
    if (w) g_windowPid(w, &pid);
    return pid == GetCurrentProcessId();
}
float __fastcall LockAxis(void *input, int edx, int action) {
    float v = reinterpret_cast<AnalogFn>(kQ108Analog)(input, edx, action);
    if (!g_lockMouse) v = 0.0f;
    if (action == 0x10 && g_keyState) {
        static bool rightWas = false, leftWas = false;
        const int kr = static_cast<int>(g_lockKeyRight), kl = static_cast<int>(g_lockKeyLeft);
        const bool fg = (kr || kl) && GameInForeground();
        const bool right = kr && fg && (g_keyState(kr) & 0x8000);
        const bool left = kl && fg && (g_keyState(kl) & 0x8000);
        if (right && !rightWas) {
            v = 1.0f;
            Log(1, "0.6.13 Q68 lock: key 0x%02x -> target switch to the right (mouse x +1.0 for one frame)", kr);
        } else if (left && !leftWas) {
            v = -1.0f;
            Log(1, "0.6.13 Q68 lock: key 0x%02x -> target switch to the left (mouse x -1.0 for one frame)", kl);
        }
        rightWas = right;
        leftWas = left;
    }
    return v;
}

// Q99 option A: 0x696f69 jne (keep the permanent piece) <-> jmp (remove it like every other piece)
void Q108ChunkApply(const char *why) {
    if (!g_chunkJccOk) return;
    const BYTE want = g_chunkRemoveLast ? 0xeb : 0x75;
    if (want == g_chunkJccNow) return;
    const BYTE cur = *reinterpret_cast<const volatile BYTE *>(kQ108ChunkJcc);
    if (cur != g_chunkJccNow) {
        Log(0, "0.6.13 Q99 chunk: byte at 0x%08lx is 0x%02x, not 0x%02x as left by this plugin - [Chunk] RemoveLastPiece "
               "off for this run", kQ108ChunkJcc, cur, g_chunkJccNow);
        g_chunkJccOk = false;
        return;
    }
    if (WriteCode(kQ108ChunkJcc, &want, 1)) {
        g_chunkJccNow = want;
        Log(1, "0.6.13 Q99 chunk (%s): 0x%08lx = %02x 0f - %s", why, kQ108ChunkJcc, want,
            want == 0xeb ? "the permanent piece (record bit 0) is removed after its lifetime like the others (PC option, "
                           "not TU)"
                         : "the game's jne: the permanent piece stays (retail / TU)");
    }
}

// ---------------------------------------------------------------- 0.6.14: group L (F6 adrenaline options)
// Main workspace docs\Befund-Gruppe-L-1211.md, docs\Befund-Gruppe-F-1211.md 4.3 (static, PC tru.exe = retail logic):
//  * fill: the enemy damage path 0x63ad50 posts message 0xd9 to the player when Lara is the attacker (0x63afe2) with
//    the damage dealt, (int)(LP before - max(LP after, 0)) (0x63b02e..0x63b03a, INSTANCE_Post 0x5b3750, synchronous);
//    the player handler 0x71f1d0 case 217 (0x71f4f4) skips it while CM+0x1fc bit 21 (headshot window), else 0x6f28c0
//    adds it unless bit 22 (full); max = player data +0x2d0 (lara DTP 850: 500). [Adrenaline] FillPercent scales that
//    amount at the post (the call 0x63b03a) - the game's fill rule, only the factor is the PC option;
//  * drain: the bar 0x6f2930 (tail-jumped from CombatManager::Update): meter -= [0xe7f188] x 1/30 x rate, rate = player
//    data +0x2d8 (225) in adrenaline mode (bit 27, load at 0x6f2965) else +0x2d4 (20, load at 0x6f2972).
//    [Adrenaline] DrainModePercent / DrainPercent multiply those data values (100 = the data);
//  * strike prompt: condition 2302 (0x7663d0) sets CM+0x1fc bit 28 + byte 0xfae8d8 = 1 + HUD group 1 when the strike's
//    conditions before it hold (meter full, activity 1002, hard-lock target, 701 / 1502 clear; the condition list stops
//    at the first false, 0x785920); the level loop clears both every frame (0x5dfda1). Logged from the poll (latch).
// Sites not touched by TruShadowPower (0x71f500 / 0x6f28c0 / 0x6f2930 head / 0x6f29b2) or TruMenu (0x6f28c0 / 0x6f2930).
const DWORD kL14FillCall = 0x0063b03a, kL14Post = 0x005b3750;
const DWORD kL14RateMode = 0x006f2965, kL14RateNormal = 0x006f2972;
const DWORD kL14BitPrompt = 0x10000000;
volatile LONG g_fillPercent = 100, g_drainPercent = 100, g_drainModePercent = 100;
float g_drainFactor = 1.0f, g_drainModeFactor = 1.0f;   // read by the rate stubs (aligned 32-bit stores)
bool g_fillHooked = false, g_drainHooked = false;
volatile LONG g_fillLines = 0;

LONG L14Clamp(LONG v, LONG lo, LONG hi) { return v < lo ? lo : v > hi ? hi : v; }

void L14ReadSwitches(bool report) {
    const char *ini = g_iniPath;
    const LONG fill = L14Clamp(GetPrivateProfileIntA("Adrenaline", "FillPercent", 100, ini), 0, 1000);
    const LONG drain = L14Clamp(GetPrivateProfileIntA("Adrenaline", "DrainPercent", 100, ini), 0, 1000);
    const LONG drainMode = L14Clamp(GetPrivateProfileIntA("Adrenaline", "DrainModePercent", 100, ini), 0, 1000);
    const LONG any = GetPrivateProfileIntA("Adrenaline", "StrikeWithoutFullMeter", 0, ini) ? 1 : 0;
    if (report && (fill != g_fillPercent || drain != g_drainPercent || drainMode != g_drainModePercent ||
                   any != g_strikeAnyMeter))
        Log(1, "0.6.14 switches (run time): [Adrenaline] FillPercent %ld, DrainPercent %ld, DrainModePercent %ld, "
               "StrikeWithoutFullMeter %ld", fill, drain, drainMode, any);
    InterlockedExchange(&g_fillPercent, fill);
    InterlockedExchange(&g_drainPercent, drain);
    InterlockedExchange(&g_drainModePercent, drainMode);
    InterlockedExchange(&g_strikeAnyMeter, any);
    g_drainFactor = static_cast<float>(drain) / 100.0f;
    g_drainModeFactor = static_cast<float>(drainMode) / 100.0f;
}

// game thread: the call 0x63b03a = INSTANCE_Post(player, 0xd9, damage dealt) of the enemy damage path (cdecl, the
// caller pops 12 bytes); the amount is scaled by FillPercent, one line per post (the first 80 at level 1)
typedef void(__cdecl *PostFn)(void *inst, DWORD msg, DWORD data);
void __cdecl FillPost(void *player, DWORD msg, DWORD amount) {
    const LONG pct = g_fillPercent;
    DWORD give = amount;
    if (msg == 0xd9 && pct != 100) {
        const double v = static_cast<double>(static_cast<int>(amount)) * pct / 100.0;
        give = static_cast<DWORD>(static_cast<int>(v >= 0.0 ? v + 0.5 : v - 0.5));
    }
    Q108State a;
    memset(&a, 0, sizeof(a));
    const bool logIt = g_adrLog && g_q108ReadOk && msg == 0xd9;
    if (logIt) Q108Read(&a);
    reinterpret_cast<PostFn>(kL14Post)(player, msg, give);
    if (!logIt) return;
    Q108State b;
    Q108Read(&b);
    const LONG n = InterlockedIncrement(&g_fillLines);
    Log(n <= 80 ? 1 : 2, "0.6.14 F6 fill: message 0xd9 (damage Lara dealt) %d x FillPercent %ld -> %d; meter %.1f -> %.1f "
                         "/ %.0f%s", static_cast<int>(amount), pct, static_cast<int>(give), a.meter, b.meter, b.max,
        (a.flags & kQ108BitWindow) ? " (skipped: bit 21, headshot window - 0x71f50b)"
        : (a.flags & kQ108BitFull) ? " (not added: bit 22, meter held full - 0x6f28d1)" : "");
}

// game thread: the bar 0x6f2930 loads its drain rate here (FPU: st0 = 0.0 below; the stub pushes one value like the
// replaced fld). 0x6f2965 `mov eax,[0xfad764]; fld [eax+0x2d8]` (11 B), 0x6f2972 `mov edx,[0xfad764]; fld [edx+0x2d4]`
// (12 B) - same registers, the factor read from the plugin (1.0 = the data value exactly)
__declspec(naked) void RateModeStub() {
    __asm {
        mov eax, dword ptr ds:[0x00fad764]
        fld dword ptr [eax + 0x2d8]
        fmul dword ptr [g_drainModeFactor]
        ret
    }
}
__declspec(naked) void RateNormalStub() {
    __asm {
        mov edx, dword ptr ds:[0x00fad764]
        fld dword ptr [edx + 0x2d4]
        fmul dword ptr [g_drainFactor]
        ret
    }
}

bool L14WriteCallPad(DWORD at, const void *to, size_t length) {
    BYTE c[16];
    if (length < 5 || length > sizeof(c)) return false;
    memset(c, 0x90, sizeof(c));
    c[0] = 0xe8;
    const DWORD rel = reinterpret_cast<DWORD>(to) - (at + 5);
    memcpy(c + 1, &rel, 4);
    return WriteCode(at, c, length);
}

// poll thread: the strike prompt (bit 28, set by condition 2302 while the strike could start, cleared every frame) as
// a latch - ON when seen, OFF when not seen for 300 ms
void L14PollPrompt(const Q108State &s, DWORD now) {
    static bool on = false;
    static DWORD seen = 0, since = 0;
    static LONG lines = 0;
    if (s.flags & kL14BitPrompt) {
        seen = now;
        if (!on) {
            on = true;
            since = now;
            if (++lines <= 200) {
                char text[420];
                Q108Text(s, text, sizeof(text));
                Log(1, "0.6.14 F6 strike prompt ON (CM+0x1fc bit 28 from condition 2302: meter full, activity 1002, "
                       "hard-lock target (2011), 701 / 1502 clear) - holding action 46 (pad X = code 1) starts the "
                       "vault-off strike (chart record 786 = state 1014) - %s", text);
            }
        }
    } else if (on && now - seen > 300) {
        on = false;
        if (lines <= 200) Log(1, "0.6.14 F6 strike prompt OFF after %lu ms (Lara record %d)", seen - since, LaraRecord());
    }
}

void SetupL14() {
    struct Check { DWORD at; const char *hex; const char *what; };
    const Check fillFacts[] = {
        {0x0063afe2, "3b1d94f0e700 755c", "0x63ad50: attacker == player [0xe7f094]"},
        {0x0063b02e, "e8ed9c1d00 50 68d9000000 53 e81187f7ff 83c40c", "0x63ad50: INSTANCE_Post(player, 0xd9, (int) damage)"},
        {kL14Post, "56 8b742408 8d8610010000 85c0 7422 57 8bbe20010000", "INSTANCE_Post 0x5b3750 (cdecl, handler +0x120)"},
        {0x0071f4f4, "8b1558dbfa00 8b8a04050000", "player handler case 217 (0x71f4f4)"},
        {0x0071f511, "db4604 51 d91c24 e8a333fdff", "case 217: 0x6f28c0((float) amount)"},
    };
    bool ok = true;
    for (const auto &c : fillFacts)
        if (!HexAt(c.at, c.hex)) {
            Log(0, "0.6.14 F6: %s at 0x%08lx does not match - FillPercent / fill log not placed", c.what, c.at);
            ok = false;
            break;
        }
    if (ok) g_fillHooked = WriteCall(kL14FillCall, reinterpret_cast<const void *>(&FillPost));
    const Check drainFacts[] = {
        {0x006f294d, "d90588f1e700 c1ea1b f6c201 dc0db03c8400 d95c2404 740d a164d7fa00 d980d8020000 eb0c 8b1564d7fa00 "
                     "d982d4020000 d91c24 d9413c", "bar 0x6f2930: rate = player data +0x2d8 (bit 27) / +0x2d4"},
        {0x006f2930, "8b91fc010000 d9ee 83ec08 f7c200004000 756f d8513c",
         "bar 0x6f2930 head (bit 22 gate, CM+0x3c)"},
    };
    ok = true;
    for (const auto &c : drainFacts)
        if (!HexAt(c.at, c.hex)) {
            Log(0, "0.6.14 F6: %s at 0x%08lx does not match - DrainPercent / DrainModePercent not placed", c.what, c.at);
            ok = false;
            break;
        }
    if (ok) {
        const bool m = L14WriteCallPad(kL14RateMode, reinterpret_cast<const void *>(&RateModeStub), 11);
        const bool n = m && L14WriteCallPad(kL14RateNormal, reinterpret_cast<const void *>(&RateNormalStub), 12);
        if (m && !n) {
            const BYTE orig[11] = {0xa1, 0x64, 0xd7, 0xfa, 0x00, 0xd9, 0x80, 0xd8, 0x02, 0x00, 0x00};
            WriteCode(kL14RateMode, orig, sizeof(orig));
        }
        g_drainHooked = m && n;
    }
    Log(1, "0.6.14 group L (F6): fill %s (call 0x63b03a, FillPercent %ld), drain %s (0x6f2965 / 0x6f2972, DrainPercent "
           "%ld, DrainModePercent %ld; 100 = player data +0x2d4 / +0x2d8), StrikeWithoutFullMeter %ld (condition 538 %s), "
           "strike prompt log %s; switches read again at run time (<= 1 / s)",
        g_fillHooked ? "placed" : "NOT placed", g_fillPercent, g_drainHooked ? "placed" : "NOT placed", g_drainPercent,
        g_drainModePercent, g_strikeAnyMeter, (g_conditions && g_blocksOk) ? "registered" : "NOT registered - no effect",
        (g_adrLog && g_q108ReadOk) ? "on" : "off");
}

void Q108ReadSwitches(bool report) {
    const char *ini = g_iniPath;
    const LONG assist = GetPrivateProfileIntA("Adrenaline", "AssistPointer", 0, ini) ? 1 : 0;
    const LONG mouse = GetPrivateProfileIntA("Lock", "MouseSwitch", 1, ini) ? 1 : 0;
    const LONG right = GetPrivateProfileIntA("Lock", "RightKey", 0, ini) & 0xff;
    const LONG left = GetPrivateProfileIntA("Lock", "LeftKey", 0, ini) & 0xff;
    const LONG chunk = GetPrivateProfileIntA("Chunk", "RemoveLastPiece", 0, ini) ? 1 : 0;
    if (report && (assist != g_adrAssist || mouse != g_lockMouse || right != g_lockKeyRight || left != g_lockKeyLeft ||
                   chunk != g_chunkRemoveLast))
        Log(1, "0.6.13 switches (run time): [Adrenaline] AssistPointer %ld, [Lock] MouseSwitch %ld RightKey 0x%02lx "
               "LeftKey 0x%02lx, [Chunk] RemoveLastPiece %ld", assist, mouse, right, left, chunk);
    InterlockedExchange(&g_adrAssist, assist);
    InterlockedExchange(&g_lockMouse, mouse);
    InterlockedExchange(&g_lockKeyRight, right);
    InterlockedExchange(&g_lockKeyLeft, left);
    InterlockedExchange(&g_chunkRemoveLast, chunk);
    L14ReadSwitches(report);   // 0.6.14: F6 fill / drain percent, strike without a full meter
}

// poll thread (every 10 ms, reads only, faults caught by Rd): one line per change of adrenaline mode / window / full,
// circle / zone and every world or player slow motion with its factor; the switches again at most once per second
void Q108Scale(const char *what, float before, float now, DWORD tick, DWORD *since, float *lowest, float *logged,
               int *lines) {
    const bool wasSlow = fabs(before - 1.0f) > 0.001f, isSlow = fabs(now - 1.0f) > 0.001f;
    if (!wasSlow && isSlow) {
        *since = tick;
        *lowest = now;
        *logged = now;
        *lines = 0;
        Log(1, "0.6.13 Q108 slow motion START: %s time scale %.3f -> %.3f (Lara record %d)", what, before, now,
            LaraRecord());
    } else if (wasSlow && !isSlow) {
        Log(1, "0.6.13 Q108 slow motion END: %s time scale %.3f -> %.3f after %lu ms (lowest %.3f)", what, before, now,
            tick - *since, *lowest);
    } else if (isSlow) {
        if (now < *lowest) *lowest = now;
        if (fabs(now - *logged) >= 0.05f && *lines < 12) {
            ++*lines;
            *logged = now;
            Log(1, "0.6.13 Q108 slow motion: %s time scale now %.3f (%lu ms since the start)", what, now, tick - *since);
        }
    }
}

DWORD WINAPI Q108Thread(LPVOID) {
    Q108State prev;
    memset(&prev, 0, sizeof(prev));
    bool have = false;
    DWORD lastIni = GetTickCount(), tMode = 0, tWindow = 0, tCircle = 0, tFull = 0, sW = 0, sP = 0;
    float lowW = 1.0f, lowP = 1.0f, logW = 1.0f, logP = 1.0f;
    int linesW = 0, linesP = 0, zoneLines = 0;
    for (;;) {
        Sleep(10);
        const DWORD now = GetTickCount();
        if (now - lastIni >= 1000) {
            lastIni = now;
            Q108ReadSwitches(true);
            Q108ChunkApply("run time");
        }
        if (!g_adrLog || !g_q108ReadOk) continue;
        Q108State s;
        Q108Read(&s);
        if (!s.ok) {
            if (have) Log(2, "0.6.13 Q108: no combat manager ([[0xfadb58]+0x504] = 0) - level change / menu");
            have = false;
            continue;
        }
        if (!have) {
            prev = s;
            have = true;
            continue;
        }
        char text[420];
        text[0] = 0;
        const DWORD ch = s.flags ^ prev.flags;
        if (ch & (kQ108BitMode | kQ108BitWindow | kQ108BitFull) || ((s.ret ^ prev.ret) & 0x40)) Q108Text(s, text, sizeof(text));
        if (ch & kQ108BitFull) {
            if (s.flags & kQ108BitFull) { tFull = now; Log(1, "0.6.13 Q108 meter FULL (bit 22) - %s", text); }
            else Log(1, "0.6.13 Q108 meter full OFF after %lu ms - %s", now - tFull, text);
        }
        if (ch & kQ108BitMode) {
            if (s.flags & kQ108BitMode) { tMode = now; Log(1, "0.6.13 Q108 adrenaline mode ON (bit 27, R3 = action 37) - %s", text); }
            else Log(1, "0.6.13 Q108 adrenaline mode OFF after %lu ms - %s", now - tMode, text);
        }
        if (ch & kQ108BitWindow) {
            if (s.flags & kQ108BitWindow) { tWindow = now; Log(1, "0.6.13 Q108 headshot window ON (bit 21, vault-off strike 1014) - %s", text); }
            else Log(1, "0.6.13 Q108 headshot window OFF after %lu ms (reticle bit 9 0x200 = %d: set by the hit "
                        "0x719d4e on a success) - %s", now - tWindow, (s.ret & 0x200) ? 1 : 0, text);
        }
        if ((s.ret ^ prev.ret) & 0x40) {
            if (s.ret & 0x40) { tCircle = now; zoneLines = 0; Log(1, "0.6.13 Q108 circle ON (reticle bit 6) - %s", text); }
            else Log(1, "0.6.13 Q108 circle OFF after %lu ms - %s", now - tCircle, text);
        }
        if (((s.ret ^ prev.ret) & 0x80) && (s.ret & 0x40) && zoneLines < 40) {
            ++zoneLines;
            Log(1, "0.6.13 Q108 pointer %s the zone (bit 7): %.1f %.1f |%.1f| radius %.1f, HUD 0xfae8ae %lu",
                (s.ret & 0x80) ? "IN" : "OUT of", s.px, s.py, Q108Dist(s), s.radius, s.hud);
        }
        Q108Scale("world", prev.world, s.world, now, &sW, &lowW, &logW, &linesW);
        Q108Scale("player", prev.player, s.player, now, &sP, &lowP, &logP, &linesP);
        L14PollPrompt(s, now);   // 0.6.14: strike prompt (bit 28) as a latch
        prev = s;
    }
}

void SetupQ108() {
    HMODULE user32 = GetModuleHandleA("user32.dll");
    if (user32) {
        g_keyState = reinterpret_cast<KeyStateFn>(GetProcAddress(user32, "GetAsyncKeyState"));
        g_foreground = reinterpret_cast<ForegroundFn>(GetProcAddress(user32, "GetForegroundWindow"));
        g_windowPid = reinterpret_cast<WindowPidFn>(GetProcAddress(user32, "GetWindowThreadProcessId"));
    }
    struct Check { DWORD at; const char *hex; const char *what; };
    const Check logFacts[] = {
        {0x00718d03, "8b87fc010000 c1e815 a801 0f847b010000 8b0f 8a5140 c0ea06 f6c201",
         "1014 tick 0x718d00: CM+0x1fc bit 21, reticle [CM] +0x40 bit 6"},
        {0x00718d4c, "a1682ba000 8b4818 8b11 8b8230060000 2410", "1014 tick: RT = action 33 record +0x630 & 0x10"},
        {0x006f2f67, "d94630 ded9 dfe0 f6c441 7508 81c980000000", "0x6f2f20: bit 7 = |pointer| < reticle +0x30"},
        {0x0077a7c0, "d905d0e8fa00 c3", "radius getter 0x77a7c0 = [0xfae8d0]"},
        {0x006e6a80, "e83b3d0900 d95c2414 d9442414 d95730", "strike start 0x6e6a70: reticle +0x30 = radius"},
        {0x0071d5e2, "e88990fcff 818ffc01000000002000", "1014 0x71d3c0: meter empty 0x6e6670, bit 21 set"},
        {0x00719ce8, "0fb74240 8ac8 c0e906 f6c101 0f848a000000 c0e807", "hit 0x7198d0: success = reticle bit 7"},
        {0x007189ea, "818efc01000000000008", "adrenaline start 0x7189c0: bit 27 set"},
        {0x005da595, "d91da0f1e700", "world time scale [0xe7f1a0] written by 0x5da595"},
        {0x007760b2, "d905d4f1e700", "player time scale [0xe7f1d4] read by 0x7760b2"},
    };
    bool ok = true;
    for (const auto &c : logFacts)
        if (!HexAt(c.at, c.hex)) {
            Log(0, "0.6.13 Q108: %s at 0x%08lx does not match - adrenaline log off", c.what, c.at);
            ok = false;
            break;
        }
    g_q108ReadOk = ok;
    const Check assistFacts[] = {
        {0x0070d85a, "c0e806 a801 7407 8bce e8b856feff", "0x70d810: bit 6 -> call 0x6f2f20 at 0x70d863"},
        {kQ108ReticleFn, "55 8bec 83e4f0 83ec2c 56 8bf1 0fb74e40 8ac1 c0e806 a801", "0x6f2f20 head (thiscall reticle)"},
        {0x006f2f3d, "0f284620 0f59c0", "0x6f2f20: pointer = reticle +0x20 (16 bytes)"},
        {0x006f2f67, "d94630 ded9 dfe0 f6c441 7508 81c980000000", "0x6f2f20: bit 7 = |pointer| < reticle +0x30"},
        {0x006f30f5, "5e 8be5 5d c3", "0x6f2f20: plain ret (no stack arguments)"},
    };
    ok = true;
    for (const auto &c : assistFacts)
        if (!HexAt(c.at, c.hex)) {
            Log(0, "0.6.13 Q109: %s at 0x%08lx does not match - pointer assist not placed", c.what, c.at);
            ok = false;
            break;
        }
    if (ok) g_assistHooked = WriteCall(kQ108ReticleCall, reinterpret_cast<const void *>(&AssistReticle));
    const Check lockFacts[] = {
        {0x0071ccff, "8b0d682ba000 6a10 e84441d6ff d8860c020000 6a11 d99e0c020000 8b0d682ba000 e82b41d6ff d88610020000",
         "target switch 0x71cb10: mouse actions 0x10 / 0x11 into CM+0x20c / +0x210"},
        {kQ108Analog, "8b442404 8b4914 8d0440 c1e004 d90408 c20400", "analog getter 0x480e50 (thiscall action, ret 4)"},
        {0x0071ceaa, "d982a0020000 dcc8 ded9", "switch threshold tuning +0x2a0 squared"},
    };
    ok = true;
    for (const auto &c : lockFacts)
        if (!HexAt(c.at, c.hex)) {
            Log(0, "0.6.13 Q68: %s at 0x%08lx does not match - lock switch input not placed", c.what, c.at);
            ok = false;
            break;
        }
    if (ok) {
        const bool x = WriteCall(kQ108LockCallX, reinterpret_cast<const void *>(&LockAxis));
        const bool y = x && WriteCall(kQ108LockCallY, reinterpret_cast<const void *>(&LockAxis));
        if (x && !y) WriteCall(kQ108LockCallX, reinterpret_cast<const void *>(kQ108Analog));
        g_lockHooked = x && y;
    }
    g_chunkJccOk = HexAt(0x00696f63, "83e101 80f901 750f 56 e80f7bdfff 83c404");
    if (!g_chunkJccOk) Log(0, "0.6.13 Q99: 0x696f63 does not match `83 e1 01 80 f9 01 75 0f` - [Chunk] RemoveLastPiece off");
    Q108ReadSwitches(false);
    Q108ChunkApply("start");
    HANDLE t = CreateThread(nullptr, 0, &Q108Thread, nullptr, 0, nullptr);
    if (t) CloseHandle(t);
    Log(1, "0.6.13 group C: Q108 adrenaline log %s ([Adrenaline] Log %d; poll every 10 ms%s); Q109 pointer assist %s "
           "(AssistPointer %ld, call 0x70d863); Q68 lock switch input %s (MouseSwitch %ld, RightKey 0x%02lx, LeftKey "
           "0x%02lx, calls 0x71cd07 / 0x71cd20%s); Q99 RemoveLastPiece %ld (%s); switches read again at run time (<= 1 / s)",
        g_q108ReadOk ? "on" : "OFF (byte checks)", g_adrLog, t ? "" : ", thread NOT started",
        g_assistHooked ? "placed" : "NOT placed", g_adrAssist, g_lockHooked ? "placed" : "NOT placed", g_lockMouse,
        g_lockKeyRight, g_lockKeyLeft, g_keyState ? "" : ", no GetAsyncKeyState", g_chunkRemoveLast,
        g_chunkJccOk ? "byte checked" : "byte check failed");
}

// ---------------------------------------------------------------- start
void ReadOptions(const char *dir) {
    char *ini = g_iniPath;
    _snprintf_s(g_iniPath, sizeof(g_iniPath), _TRUNCATE, "%sTruShadowCombat.ini", dir);
    g_enabled = GetPrivateProfileIntA("ShadowCombat", "Enabled", 1, ini);
    g_logLevel = GetPrivateProfileIntA("ShadowCombat", "LogLevel", 1, ini);
    g_targetList = GetPrivateProfileIntA("TargetList", "Enabled", 1, ini);
    g_conditions = GetPrivateProfileIntA("Conditions", "Enabled", 1, ini);
    g_strikeGate = GetPrivateProfileIntA("Strike", "Gate", 1, ini);
    g_strikeTranslate = GetPrivateProfileIntA("Strike", "Translate", 0, ini);
    g_statesOn = GetPrivateProfileIntA("States", "Enabled", 1, ini);
    g_probe1013 = GetPrivateProfileIntA("Probe", "State1013", 1, ini);
    g_translate1013 = GetPrivateProfileIntA("States", "Translate1013", 0, ini);
    g_translate1019 = GetPrivateProfileIntA("States", "Translate1019", 0, ini) ? 1 : 0;
    g_translate1020 = GetPrivateProfileIntA("States", "Translate1020", 0, ini) ? 1 : 0;
    g_probe1019 = GetPrivateProfileIntA("Probe", "States1019", 1, ini);
    g_translate231s0 = GetPrivateProfileIntA("States", "Translate231Slot0", 0, ini) ? 1 : 0;
    g_translate231s1 = GetPrivateProfileIntA("States", "Translate231Slot1", 0, ini) ? 1 : 0;
    g_translate1004 = GetPrivateProfileIntA("States", "Translate1004", 0, ini) ? 1 : 0;
    g_probe231 = GetPrivateProfileIntA("Probe", "States231And1004", 1, ini);
    g_translate1008 = GetPrivateProfileIntA("States", "Translate1008", 0, ini) ? 1 : 0;   // 0.6.11
    g_probe1008 = GetPrivateProfileIntA("Probe", "State1008", 1, ini);
    g_translate1015Exit = GetPrivateProfileIntA("States", "Translate1015Exit", 0, ini) ? 1 : 0;   // 0.6.12
    g_diagT9 = GetPrivateProfileIntA("Diag", "Targeter9", 1, ini);
    g_diagWhy = GetPrivateProfileIntA("Diag", "Targeter9Why", 1, ini);
    g_diag2011 = GetPrivateProfileIntA("Diag", "Condition2011", 1, ini);
    g_diagMax = GetPrivateProfileIntA("Diag", "MaxLines", 4000, ini);
    g_diagSnap = GetPrivateProfileIntA("Diag", "Snapshot", 1, ini) ? 1 : 0;   // 0.5.3
    g_dmgTranslate = GetPrivateProfileIntA("Damage", "Translate", 1, ini) ? 1 : 0;   // 0.6 (0.6.3: default 1)
    g_notify33 = GetPrivateProfileIntA("Death", "TranslateNotify33", 1, ini) ? 1 : 0;   // 0.6.3
    g_meleeTranslate = GetPrivateProfileIntA("Melee", "Translate", 1, ini) ? 1 : 0;      // 0.6.4
    for (const auto &k : kP1dKeys)                                                       // 0.6.5 (all default 1)
        *k.value = GetPrivateProfileIntA(k.section, k.key, 1, ini) ? 1 : 0;
    g_dmgLog = GetPrivateProfileIntA("Damage", "Log", 1, ini) ? 1 : 0;
    g_dmgMax = GetPrivateProfileIntA("Damage", "MaxLines", 3000, ini);
    if (g_dmgMax < 0) g_dmgMax = 0;
    g_chunkTranslate = GetPrivateProfileIntA("Chunk", "Translate", 1, ini) ? 1 : 0;   // 0.6.1
    g_chunkLog = GetPrivateProfileIntA("Chunk", "Log", 1, ini) ? 1 : 0;
    g_chunkMax = GetPrivateProfileIntA("Chunk", "MaxLines", 2000, ini);
    if (g_chunkMax < 0) g_chunkMax = 0;
    g_splashTranslate = GetPrivateProfileIntA("Splash", "Translate", 1, ini) ? 1 : 0;   // 0.6.2
    g_splashFallback = GetPrivateProfileIntA("Splash", "Fallback", 1, ini) ? 1 : 0;
    g_splashLog = GetPrivateProfileIntA("Splash", "Log", 1, ini) ? 1 : 0;
    g_splashMax = GetPrivateProfileIntA("Splash", "MaxLines", 2000, ini);
    g_hitMax = GetPrivateProfileIntA("Hit", "MaxLines", 3000, ini);                 // 0.6.7
    if (g_hitMax < 0) g_hitMax = 0;
    g_chunkLimit8 = GetPrivateProfileIntA("Chunk", "Limit8", 1, ini) ? 1 : 0;       // 0.6.7 (start only)
    if (g_splashMax < 0) g_splashMax = 0;
    if (g_diagMax < 0) g_diagMax = 0;
    g_adrLog = GetPrivateProfileIntA("Adrenaline", "Log", 1, ini) ? 1 : 0;   // 0.6.13 (the run-time switches: Q108ReadSwitches)
}

void Start(HMODULE self) {
    char dir[MAX_PATH];
    DWORD len = GetModuleFileNameA(self, dir, MAX_PATH);
    while (len > 0 && dir[len - 1] != '\\' && dir[len - 1] != '/') --len;
    dir[len] = 0;
    _snprintf_s(g_logPath, sizeof(g_logPath), _TRUNCATE, "%sTruShadowCombat.log", dir);
    g_self = self;                    // 0.6.9: the death switch line names this plugin's own calls
    ReadOptions(dir);
    Log(1, "%s loaded (enabled %d, log level %d, target list %d, conditions %d, states %d, strike gate %d, strike "
           "translate %d)", kVersion, g_enabled, g_logLevel, g_targetList, g_conditions, g_statesOn, g_strikeGate,
        g_strikeTranslate);
    if (!g_enabled) { Log(1, "disabled by TruShadowCombat.ini - nothing patched"); return; }
    DWORD base = static_cast<DWORD>(reinterpret_cast<DWORD_PTR>(GetModuleHandleA(nullptr)));
    if (base != kImageBase) { Log(0, "image base 0x%08lx, expected 0x%08lx - nothing patched", base, kImageBase); return; }
    g_tableOk = HexAt(kFindObject, kFindObjectHex) && HexAt(kFindObjectLoop, kFindObjectLoopHex);
    g_listOk = SetupTargetList();
    g_blocksOk = CheckBlocks();       // also the building blocks of the states / strike (list, targets, template)
    if (g_conditions && !g_blocksOk) g_conditions = 0;
    g_statesOk = g_blocksOk && CheckStateBlocks();
    if (g_statesOn && !g_statesOk) Log(0, "states 1017 / 244 / 1007: building blocks not verified - not registered");
    g_strikeOk = g_statesOk && CheckStrikeBlocks();
    g_s1019Ok = g_statesOk && CheckState1019Blocks();
    if (g_statesOn && g_probe1019)
        Log(1, "states 1019 / 1020 (TU 0x8245f420 / 0x8245f540 / 0x8245f398): %s - Translate1019 %d, Translate1020 %d "
               "(0 = registered, log only; read again at run time at most once per second)",
            g_s1019Ok ? "building blocks verified, registered with Lara's tables" : "building blocks NOT verified - not registered",
            g_translate1019, g_translate1020);
    g_s231Ok = g_s1019Ok && CheckState231Blocks();
    if (g_statesOn && g_probe231)
        Log(1, "states 231 / 1004 (TU 0x82464160 / 0x8245efc8, slots 0 / 1): %s - Translate231Slot0 %d, Translate231Slot1 %d, "
               "Translate1004 %d (0 = PC handler + \"off (would)\" lines; read again at run time)",
            g_s231Ok ? "building blocks verified, wrapped at Lara's registration" : "building blocks NOT verified - PC handlers",
            g_translate231s0, g_translate231s1, g_translate1004);
    g_s1008Ok = g_blocksOk && g_s1019Ok && CheckState1008Blocks();   // 0.6.11
    if (g_statesOn && g_probe1008)
        Log(1, "state 1008 (finisher Y move, TU 0x8245f7b0 / 0x8245fa40, slot 4 removed): %s - Translate1008 %d (0 = PC "
               "slot 4 + \"off (would)\" lines; 1 = steer onto the target of targeter TU 7 every tick, every level; read "
               "again at run time)", g_s1008Ok ? "building blocks verified, wrapped at Lara's registration"
                                             : "building blocks NOT verified - PC handler", g_translate1008);
    g_s1015Ok = CheckState1015Blocks();   // 0.6.12 (before SetupK8Log places its entry hook on the death switch)
    if (g_statesOn)
        Log(1, "state 1015 exit (finisher Y kill, TU 0x8245fe58 ThrallFatalityEnd): %s - Translate1015Exit %d (0 = PC "
               "clear + \"off (would)\" lines; 1 = death switch kind 0 on the CM+0x48 target, then the PC clear; read "
               "again at run time)", g_s1015Ok ? "building blocks verified, wrapped at Lara's registration"
                                             : "building blocks NOT verified - PC handler", g_translate1015Exit);
    if (g_strikeTranslate)
        Log(1, "shadow strike translation %s ([Strike] Translate=1; also needs TruShadowPowerMeterApi at run time)",
            g_strikeOk ? "ready" : "OFF: building blocks not verified");
    if (g_conditions && !g_listOk)
        Log(1, "conditions: target list not active - 2005 / 2006 / 2013 and the doppelganger branch of 2011 answer 0 "
               "(the TU's targeters 6 / 9 do not exist)");
    SetupTranslate1013();
    SetupRegistration();
    SetupDiag();                      // 0.5.2: after every other byte check of this plugin
    SetupDamage();                    // 0.6: K14 (independent of the parts above)
    SetupChunk();                     // 0.6.1: lethal impulse as the TU (independent of the parts above)
    SetupSplash();                    // 0.6.2: K9 splash as the TU (after SetupDamage: the remap follows its switch)
    SetupDeath();                     // 0.6.3: notification 33 of the TU's death check (independent of the parts above)
    SetupMelee();                     // 0.6.4: MeleeAttack T-M1 / T-M2 (independent of the parts above)
    SetupCompanion();                 // 0.6.5: P1d (after SetupDeath: the Land exception H3b lives in its hook)
    SetupN4c();                       // 0.6.6: T5 + P1c (after SetupCompanion: companion facts; after SetupTranslate1013)
    SetupHit();                       // 0.6.7: K-1 hit structures / knockback + K-7 chunk limit (after SetupCompanion)
    SetupImpulseGate();               // 0.6.8: K-1b impulse 0x91 gate of Lara's contact hit (independent)
    SetupK8Log();                     // 0.6.9: log points (last: the death switch facts are checked by 0.6.1 / 0.6.5 too)
    SetupHitSpeed();                  // 0.6.10: K-8b msg+0x44 / +0x48 of Lara's contact hit (independent)
    SetupQ108();                      // 0.6.13: group C - Q108 log, Q109 assist, Q68 lock input, Q99 option A
    SetupL14();                       // 0.6.14: group L - F6 fill / drain percent, strike without a full meter
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

extern "C" __declspec(dllexport) const char *TruShadowCombatVersion() { return kVersion; }

// the strike's TU meter fields (+0x15 latch, +0x18 / +0x1c target handle, +0x28 count, +0x2c frames) for the owner of
// the strike look (TU 0x823d8a80 / 0x823d9050, player anim events 5 / 4) - docs Befund-Schattenkampf.md section 5
struct TruShadowCombatStrike { DWORD size, version; BYTE *latch; DWORD *target; LONG *count; float *frames; };
extern "C" __declspec(dllexport) const TruShadowCombatStrike *__cdecl TruShadowCombatStrikeState() {
    static const TruShadowCombatStrike s = {sizeof(TruShadowCombatStrike), 1, &g_strike.latch, g_strike.target,
                                            &g_strike.count, &g_strike.frames};
    return &s;
}

// 0.5.3: copy of the targeter snapshot (see TscTargeterSnapshotV1 above) into out (at most outSize bytes; the caller
// checks the returned version 1 and out->size == sizeof its struct). Returns 1 = a copy built on the game thread within
// the last frames, 0 = none (index other than 9, [Diag] Targeter9=0 / Snapshot=0, hooks not placed, no frame since the
// first request, or the copy was being written). Every call marks "asked": the game thread builds copies for 2 s.
extern "C" __declspec(dllexport) DWORD __cdecl TscTargeterSnapshot(DWORD tuIndex, void *out, DWORD outSize) {
    if (!out || outSize < 8) return 0;
    InterlockedExchange(&g_snapAsked, static_cast<LONG>(GetTickCount() | 1));
    memset(out, 0, outSize);
    DWORD *head = static_cast<DWORD *>(out);
    head[0] = sizeof(TscTargeterSnapshotV1);         // a smaller caller struct still learns size and version
    head[1] = 1;
    if (outSize < sizeof(TscTargeterSnapshotV1) || tuIndex != 9 || !g_diagSnap || !g_diagOn) return 0;
    TscTargeterSnapshotV1 *s = static_cast<TscTargeterSnapshotV1 *>(out);
    for (int tries = 0; tries < 4; ++tries) {
        const LONG before = InterlockedCompareExchange(&g_snapSeq, 0, 0);
        if (before & 1) continue;
        memcpy(s, &g_snap, sizeof(g_snap));
        MemoryBarrier();
        if (InterlockedCompareExchange(&g_snapSeq, 0, 0) == before) {
            s->size = sizeof(TscTargeterSnapshotV1);     // also before the first copy was built (g_snap still 0)
            s->version = 1;
            return s->tick ? 1 : 0;
        }
    }
    memset(s, 0, sizeof(*s));
    s->size = sizeof(TscTargeterSnapshotV1);
    s->version = 1;
    return 0;
}

// TU target of a targeter by TU index (0..9) for diagnostics (TruMenu / tests): object pointer or 0
extern "C" __declspec(dllexport) void *__cdecl TruShadowCombatTarget(int tuIndex) {
    if (!g_listOk || tuIndex < 0 || tuIndex >= kTuTargeters) return nullptr;
    __try {
        return TargeterObject(tuIndex);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return nullptr;
    }
}
