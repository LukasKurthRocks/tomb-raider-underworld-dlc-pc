// TruSaveProbe.h - TruMenu 0.22.27 save / checkpoint probe (Q79, 2026-11-11; follow-up P1 of
// docs\Befund-Checkpoint-Zustand-Q72-1111.md in the workspace, ENGINE.md 6.4). Included by TruMenu.cpp inside its
// anonymous namespace right before the item table: it uses TruMenu's helpers (ReadDword / ReadWord / ReadByte /
// ReadString, HexBytesAt, DvChecks, Log, Out, LabelAdd, AiPatch / M21PatchGroup, ForInstances, ObjectName,
// HandleInstance, InstanceObjectName, PlayerState, ModuleOf, OptDefault, g_iniPath, g_logLevel) and adds no file of
// its own to the build.
//
// READ ONLY. The items save.pending / save.inv / save.waiting / save.find only read game memory (no game function is
// called, nothing is written). The one write is optional: [Log] Save=1 (default 0, re-read about once a second)
// points the rel32 of the two memcpy calls 0x557127 (SAVE_SaveGame) / 0x5571a3 (SAVE_RestoreGame) at SvSaveCopy /
// SvRestoreCopy - each calls the game's memcpy 0x8148a0 with the same arguments and writes one summary to TruMenu.log
// (put back when the key goes to 0; only while the dword is the game's, M21PatchGroup).
//
// Data model (all static, tru.exe Steam; Q72 + the disassembly in work\q79_saveprobe_1111, byte checks kSvChecks):
//   arenas      live SaveInfo [0xc59258], checkpoint snapshot [0xc5925c] (memcpy 0x140004 bytes, 0x557114 / 0x55718f);
//               check word 0xdeadbeef at +0x140000
//   blocks      from arena+0 to arena+[arena+0x1357f4] (bytes used); head = type | (size / 4) << 8, size with the head
//               (SAVE_GetSavedBlock 0x5563a7, walker 0x555730); types 1 unit, 2 instance extra (+8 intro), 3 instance
//               (+4 current unit = inst+0xe0, +8 object id, +0xc birth unit inst+0xe4, +0x10 link parent inst+0x228,
//               +0x14 intro id, +0x18 / +0x1c iflags, +0x20 position relative to the unit, +0x2c rotation; writer
//               0x555370), 4 placed instance (+4 birth unit, +8 / +0xc iflags, +0x10 link parent, +0x14 intro id,
//               +0x18 / +0x1a u16 position / rotation saved; writer 0x555470), 5 anim state (+8 intro), 6 game block
//   game block  live [0xc59264], snapshot [0xc5925c]'s block 6 = [0xc59268] (0x556969); +0x10 unit name, +0x90
//               checkpoint id, +0x1a8 player unit (0x70a28b); inventory at +0x34c (0x70a243): +4 / +8 / +0xc = player
//               state P+0x640 / +0x968 / +0x96c, +0x44 byte (WM+0 != 0), +0x48 15 intro ids (WM+4+16i -> inst+0x58),
//               +0x84 8 intro ids (WM+0xf4+8i), +0xa4 6 u16 counts, +0xbc 6 floats P+0x528.., +0xd4 byte (0x6f5910);
//               written only by the player query 0x17 inside SAVE_SaveGame(0); read back by 0x715ef0
//   buffer      0xc57258, 0x800 block pointers, count [0xc59260] (0x555584); pass 0x555640: unit [blk+4] loaded
//               (stream table 0xdbab40, 32 x 0xd8, +0 id, +4 state 2, +8 level, +0xc name), then block 3 0x5bb160 /
//               block 4 0x5bb640: instance of the intro exists -> dropped; object not loaded (tracker 0xdb7400, 0xcc x
//               0x24, +0xc s16 id, +0xe u16 status 2; block 4 takes the object u16 +0x50 of the unit's intro record
//               [[unit+8]+0x74] lists +0xc / +0x10 and +0x1c / +0x20, 0x90 each, +0x58 unique id) or link parent
//               [blk+0x10] not found -> back into the buffer (0x5bb1df..0x5bb207, 0x5bb6af..0x5bb6d7)
//   find        INSTANCE_Find 0x5b3950: id < 0x4000 -> u16 index [0xd99000 + 2 id], instance [0xd98f60] + (index - 1)
//               * 0x2f0; else index of id in the 0x400 dwords at 0xda1000, instance [0xd98f60] + index * 0x2f0; none
//               when byte inst+0x14 & 0x20 (being removed)
//   dead bits   arena + 0x1357f8 + id / 8, bit id & 7, for id <= 0x3fffffff and id / 8 < 0x7fc (0x555a18)
//   waiting     0xc592a8, 64 x 0x14 {handle (instance, stamp = inst+0x44), +8 intro id, +0xc callback, +0x10 flag}
//               (0x5550a4 / 0x5550f6); a slot whose handle no longer resolves (0x5b39d0) is free
//   inventory   restore 0x715ef0: each id >= 1 -> 0x555f60(player [0xe7f094], id, 0x715e90, 0 / 1) (0x715f27)

// ---- 0.22.27 save probe (byte checks of this section: work\asi\menu0250\precheck_02227_sv.txt)
const DWORD kSvLive = 0x00c59258, kSvSnap = 0x00c5925c, kSvGbLive = 0x00c59264, kSvGbSnap = 0x00c59268;
const DWORD kSvUsed = 0x1357f4, kSvDead = 0x1357f8, kSvDeadBytes = 0x7fc, kSvCheckWord = 0x140000;
const DWORD kSvBuffer = 0x00c57258, kSvBufferCount = 0x00c59260, kSvBufferSlots = 0x800;
const DWORD kSvWait = 0x00c592a8, kSvWaitSize = 0x14, kSvWaitSlots = 64;
const DWORD kSvInstIndex = 0x00d99000, kSvInstBase = 0x00d98f60, kSvInstHigh = 0x00da1000, kSvInstSize = 0x2f0;
const DWORD kSvInv = 0x34c, kSvInvCallback = 0x00715e90, kSvCopy = 0x008148a0;
const int kSvLogMax = 400;                     // log lines of one save.pending all / save.find answer

const DvCheck kSvChecks[] = {
    {0x00557114, "8b0d5892c500 8b155c92c500 6804001400 51 52"},                     // live / snapshot, 0x140004
    {0x005563a7, "8b87f4571300 8bce c1f902 0fb6d3 03c7 c1e108 8818 0bca 8908 01b7f4571300"},   // used, block head
    {0x00555730, "8bc1 56 8bb0f4571300 03f0 3bc6 57 732c 8b7c240c 8b08 8bd1 81e2ff000000 83fa03 7505 397814 7416 "
                 "83fa04 7505 397814 740c c1e908 8d0488"},                          // walk, blocks 3 / 4 intro +0x14
    {0x00556969, "8b0d5892c500 83c410 6828100400 6a06 e892f9ffff 8b0d5c92c500 6828100400 6a06 a36492c500 e87bf9ffff "
                 "d9ee a36892c500"},                                               // game block live / snapshot
    {0x00555584, "813d6092c50000080000"},                                          // buffer 0x800 slots
    {0x0055564c, "be5872c500 bb01000000 81fe5892c500 7d62 8b06 85c0 c744240800000000 7448 8b4004 50 e8dbc40600 83c404 "
                 "85c0 7427 8b0e 803903"},                                         // pass: unit +4, type 3 / 4
    {0x005bb1b5, "8b5714 52 e89287ffff 83c404 85c0 0f8564040000 8b4708 6aff 50 e85c650000 83c408 85c0 0f84de030000"},
    {0x005bb1df, "6683780e02 8b4808 894c2420 0f85cc030000 8b4710 85c0 7415 50 e85287ffff 83c404 85c0 89442424 "
                 "0f84b0030000"},                                                  // block 3: object status 2, parent
    {0x005bb650, "8b5d08 8b5314 56 57 89442434 8b4008 52 33f6 50 894c2440 89742438 89442434 e8ec81ffff"},
    {0x005bb684, "8b4758 50 e8c382ffff 83c404 85c0 0f85a8030000 0fb74f50 6aff 51 e88c600000 83c408 85c0 0f8457030000"},
    {0x005bb6af, "6683780e02 8b5008 8954243c 0f8545030000 8b4310 85c0 7421 50 e88282ffff 83c404 85c0 89442430 "
                 "0f8429030000"},                                                  // block 4: object status 2, parent
    {0x005b3872, "8b7a74 8b570c 33c9 85d2 7623 8b5f10 8d7358 3b2e 740f 83c101 81c690000000 3bca 72ef"},   // intro list 1
    {0x005b38a1, "8b771c 33c9 85f6 761f 8b5720 8d4900 3b6a58 7412 83c101 81c290000000 3bce"},             // intro list 2
    {0x005b3950, "8b4c2404 f7c100c0ffff 7536 0fb7044d0090d900 6685c0 743e 8b0d608fd900 0fbfc0 69c0f0020000 8a940824fdffff "
                 "8d840810fdffff 80e220"},                                         // INSTANCE_Find, low ids
    {0x005b3992, "33c0 390c850010da00 740d 83c001 3d00040000 7ced 33c0 c3 69c0f0020000 0305608fd900 8a4814 80e120"},
    {0x005c1579, "b80074db00 33f6 6683780e00 7408 0fbf500c 3bd5 7410 83c601 83c024 81fecc000000 7ce3"},   // tracker
    {0x005c1b50, "56 8b742408 33c0 33d2 b940abdb00 8bff 80790402 7504 3931 7413 81c1d8000000 83c201 81f940c6db00"},
    {0x00555a18, "81feffffff3f 57 8bf9 774d 8bc6 99 83e207 03c2 8bce 83e107 ba01000000 c1f803 d3e2 3dfc070000 7d15 "
                 "0fb68438f8571300 23c2"},                                         // dead bit test
    {0x005550a4, "bea892c500 8da42400000000 56 e81ae90500 83c404 85c0 7411 83c614 83c701 81fea897c500 7ce5"},   // wait
    {0x005550f6, "8996b092c500 8986b492c500 898eb892c500"},                       // wait slot +8 / +0xc / +0x10
    {0x005b39d0, "8b4c2404 85c9 740e 8b01 85c0 7408 8b5044 3b5104 7402 33c0 c3"},  // handle {instance, stamp +0x44}
    {0x006f5921, "0f95c0 884744 33f6 83c748 8d5d04"},                              // inventory +0x44, +0x48, WM+4
    {0x006f595f, "8b4058 eb02 33c0 8907 83c601 83c704 83c310 83fe0f"},             // intro id inst+0x58, 15 slots
    {0x006f597c, "81c784000000 8d9df4000000"},                                     // +0x84, WM+0xf4
    {0x006f59b7, "be28050000 81c3a4000000"},                                       // +0xa4 counts, P+0x528
    {0x006f59d8, "d99c3094fbffff"},                                                // floats +0xbc
    {0x006f59ff, "8881d4000000"},                                                  // +0xd4
    {0x00715eff, "8b3d6492c500 81c74c030000 896c2414 897c241c 8d7748 bb0f000000"}, // restore: live game block +0x34c
    {0x00715f27, "6a00 68905e7100 50 a194f0e700 50 e82600e4ff"},                   // 0x555f60(player, id, 0x715e90, 0)
    {0x00715f45, "8db784000000 bb08000000"},
    {0x0070a232, "8b0d58dbfa00 8b9140060000 a16492c500 054c030000 895004 8b0d58dbfa00 8b9168090000 895008 8b0d58dbfa00 "
                 "8b916c090000 89500c"},                                           // query 0x17: P+0x640 / +0x968 / +0x96c
    {0x0070a27a, "8b0d94f0e700 8b91e0000000 a16492c500 8990a8010000"},             // game block +0x1a8 = player unit
};
// [Log] Save: the stack between each function's entry and its copy call (no other push), and the two calls. The
// prologues (0x5570f0 5 bytes, 0x557130 8 bytes) are TruTrace's hook places - tested apart: game bytes or a jmp
const DvCheck kSvHookChecks[] = {
    {0x005570f5, "751d a19092c500 68d8d98400 50 e899e60e00 83c408 e8b1f7ffff e8cceaffff"},
    {0x00557127, "e874d72b00 83c40c c3"},
    {0x00557138, "53 55 56 57 68fcd98400 50 e859e60e00 a16492c500 810db8f0e70000002000 8b88e4010000 8b90e8010000 "
                 "8b98d8010000"},
    {0x00557168, "8bb0dc010000 8ba8e0010000 8b3d5892c500 894c2428 8b88ec010000 8954242c 0fbf9008020000"},
    {0x0055718f, "a15c92c500 6804001400 50 57 894c243c 89542424 e8f8d62b00 6800200000"},
};

bool g_svChecked = false, g_svOk = false, g_svHookOk = false;
char g_svWhy[96] = "not checked yet", g_svHookWhy[160] = "not checked yet";
volatile LONG g_svLogOn = 0;                  // [Log] Save (ReadOptions, then SvReadSwitch about once a second)
bool g_svRead = false, g_svPatchOn = false, g_svRefused = false, g_svNotedNoHook = false;
DWORD g_svReadTick = 0;
volatile LONG g_svSaves = 0, g_svRestores = 0;
AiPatch g_svPatches[2] = {
    {0x00557127, kSvCopy, true, "S1 SAVE_SaveGame copy call 0x557127", 0, 0, false},
    {0x005571a3, kSvCopy, true, "S2 SAVE_RestoreGame copy call 0x5571a3", 0, 0, false},
};
void *__cdecl SvSaveCopy(void *d, const void *s, size_t n);      // below
void *__cdecl SvRestoreCopy(void *d, const void *s, size_t n);

bool SvCheck() {
    if (g_svChecked) return g_svOk;
    g_svChecked = true;
    DWORD at = 0;
    g_svOk = DvChecks(kSvChecks, sizeof(kSvChecks) / sizeof(kSvChecks[0]), &at);
    if (g_svOk) Out(g_svWhy, sizeof(g_svWhy), "ok");
    else Out(g_svWhy, sizeof(g_svWhy), "save code differs at 0x%08lx", at);
    const bool saveHead = HexBytesAt(0x005570f0, "807c240400"), restoreHead = HexBytesAt(0x00557130, "83ec1c");
    BYTE j1 = 0, j2 = 0;                       // or a 5-byte jmp (e9) of another plugin's prologue hook (TruTrace)
    const bool heads = (saveHead || (ReadByte(0x005570f0, &j1) && j1 == 0xe9)) &&
                       (restoreHead || (ReadByte(0x00557130, &j2) && j2 == 0xe9));
    g_svHookOk = g_svOk && heads && DvChecks(kSvHookChecks, sizeof(kSvHookChecks) / sizeof(kSvHookChecks[0]), &at);
    if (g_svHookOk) Out(g_svHookWhy, sizeof(g_svHookWhy), "ok (prologues %s / %s)", saveHead ? "game" : "jmp of another plugin",
                        restoreHead ? "game" : "jmp of another plugin");
    else if (!g_svOk) Out(g_svHookWhy, sizeof(g_svHookWhy), "reads off (%s)", g_svWhy);
    else if (!heads) Out(g_svHookWhy, sizeof(g_svHookWhy), "a SAVE_* prologue holds neither the game's bytes nor a jmp");
    else Out(g_svHookWhy, sizeof(g_svHookWhy), "copy call code differs at 0x%08lx", at);
    for (AiPatch &p : g_svPatches) p.game = p.target - (p.site + 5);
    g_svPatches[0].hook = reinterpret_cast<DWORD>(&SvSaveCopy) - (g_svPatches[0].site + 5);
    g_svPatches[1].hook = reinterpret_cast<DWORD>(&SvRestoreCopy) - (g_svPatches[1].site + 5);
    Log(g_svOk ? 1 : 0, "0.22.27: save probe %s (kSvChecks %u); [Log] Save lines %s (kSvHookChecks %u), [Log] Save=%ld (live)",
        g_svWhy, static_cast<unsigned>(sizeof(kSvChecks) / sizeof(kSvChecks[0])), g_svHookWhy,
        static_cast<unsigned>(sizeof(kSvHookChecks) / sizeof(kSvHookChecks[0])), g_svLogOn);
    return g_svOk;
}

// ---- unit names: the loaded stream units by id, remembered for the session (an unloaded unit keeps its name)
struct SvUnitName { DWORD id; char name[40]; };
SvUnitName g_svUnits[128];
int g_svUnitN = 0, g_svUnitNext = 0;
SRWLOCK g_svUnitLock = SRWLOCK_INIT;
DWORD SvUnitEntry(DWORD id) {                 // the loaded stream unit entry of an id (as 0x5c1b50), 0 = not loaded
    for (DWORD e = kStreamUnits; e < kStreamUnitsEnd; e += kStreamUnitSize) {
        DWORD eid = 0;
        BYTE state = 0;
        if (!ReadDword(e, &eid) || !ReadByte(e + 4, &state)) return 0;
        if (state == 2 && eid == id) return e;
    }
    return 0;
}
bool SvUnitPrintable(const char *s) {
    if (!s[0]) return false;
    for (const char *p = s; *p; ++p)
        if (static_cast<unsigned char>(*p) < 32 || static_cast<unsigned char>(*p) > 126) return false;
    return true;
}
void SvUnitCacheTick() {                      // game thread, about once a second: remember every loaded unit's name
    for (DWORD e = kStreamUnits; e < kStreamUnitsEnd; e += kStreamUnitSize) {
        DWORD id = 0;
        BYTE state = 0;
        char name[40];
        if (!ReadDword(e, &id) || !ReadByte(e + 4, &state)) return;
        if (state != 2 || !ReadString(e + 0xc, name, sizeof(name)) || !SvUnitPrintable(name)) continue;
        AcquireSRWLockExclusive(&g_svUnitLock);
        int i = 0;
        while (i < g_svUnitN && g_svUnits[i].id != id) ++i;
        if (i == g_svUnitN) {
            if (g_svUnitN < 128) ++g_svUnitN;
            else { i = g_svUnitNext; g_svUnitNext = (g_svUnitNext + 1) % 128; }
        }
        g_svUnits[i].id = id;
        strcpy_s(g_svUnits[i].name, sizeof(g_svUnits[i].name), name);
        ReleaseSRWLockExclusive(&g_svUnitLock);
    }
}
// "<name> (loaded)" / "<name> (not loaded)" / "unit <id> (not loaded, name not seen)"; *loaded = the unit is loaded
void SvUnitText(DWORD id, char *o, size_t n, bool *loaded = nullptr) {
    char name[40] = "";
    const DWORD e = SvUnitEntry(id);
    if (loaded) *loaded = e != 0;
    if (e && ReadString(e + 0xc, name, sizeof(name)) && SvUnitPrintable(name)) { Out(o, n, "%s (loaded)", name); return; }
    AcquireSRWLockShared(&g_svUnitLock);
    for (int i = 0; i < g_svUnitN; ++i)
        if (g_svUnits[i].id == id) { strcpy_s(name, sizeof(name), g_svUnits[i].name); break; }
    ReleaseSRWLockShared(&g_svUnitLock);
    if (name[0]) Out(o, n, "%s (%s)", name, e ? "loaded" : "not loaded");
    else Out(o, n, "#%lu (%s)", id, e ? "loaded, no name" : "not loaded, name not seen this session");
}

// ---- the game's lookups, done with reads
DWORD SvInstFind(DWORD id, bool *removing = nullptr) {    // INSTANCE_Find 0x5b3950
    if (removing) *removing = false;
    DWORD base = 0, inst = 0;
    if (!ReadDword(kSvInstBase, &base) || !base) return 0;
    if (!(id & 0xffffc000)) {
        WORD index = 0;
        if (!ReadWord(kSvInstIndex + id * 2, &index) || !index) return 0;
        inst = base + static_cast<DWORD>(static_cast<LONG>(static_cast<short>(index)) * static_cast<LONG>(kSvInstSize)) -
               kSvInstSize;
    } else {
        DWORD i = 0, v = 0;
        for (; i < 0x400; ++i) {
            if (!ReadDword(kSvInstHigh + i * 4, &v)) return 0;
            if (v == id) break;
        }
        if (i == 0x400) return 0;
        inst = base + i * kSvInstSize;
    }
    BYTE flags = 0;
    if (!ReadByte(inst + 0x14, &flags)) return 0;
    if (flags & 0x20) { if (removing) *removing = true; return 0; }
    return inst;
}
int SvTracker(DWORD objectId) {               // object tracker status (0x5c1579; 2 = loaded), -1 = no entry
    for (int i = 0; i < kObjectEntries; ++i) {
        const DWORD e = kObjectTable + static_cast<DWORD>(i) * 0x24;
        WORD status = 0, oid = 0;
        if (!ReadWord(e + 0xe, &status) || !ReadWord(e + 0xc, &oid)) return -1;
        if (status && static_cast<LONG>(static_cast<short>(oid)) == static_cast<LONG>(objectId)) return status;
    }
    return -1;
}
DWORD SvIntroRecord(DWORD unitEntry, DWORD intro) {    // 0x5b3860(level [entry+8], intro id): record or 0
    DWORD level = 0, c = 0;
    if (!unitEntry || !ReadDword(unitEntry + 8, &level) || !level || !ReadDword(level + 0x74, &c) || !c) return 0;
    for (int list = 0; list < 2; ++list) {
        DWORD count = 0, arr = 0;
        if (!ReadDword(c + (list ? 0x1c : 0xc), &count) || !ReadDword(c + (list ? 0x20 : 0x10), &arr) || !arr) continue;
        for (DWORD i = 0; i < count && i < 20000; ++i) {
            DWORD v = 0;
            if (!ReadDword(arr + i * 0x90 + 0x58, &v)) break;
            if (v == intro) return arr + i * 0x90;
        }
    }
    return 0;
}
int SvDeadBit(DWORD arena, DWORD id) {        // dead bit (0x555a18): 0 / 1, -1 = outside the table / unreadable
    BYTE b = 0;
    if (!arena || id > 0x3fffffff || (id >> 3) >= kSvDeadBytes || !ReadByte(arena + kSvDead + (id >> 3), &b)) return -1;
    return (b >> (id & 7)) & 1;
}
DWORD SvArena(bool snapshot) {
    DWORD a = 0;
    ReadDword(snapshot ? kSvSnap : kSvLive, &a);
    return a;
}
void SvObjText(DWORD objectId, char *o, size_t n) {
    char name[64];
    if (ObjectName(static_cast<int>(objectId & 0xffff), name, sizeof(name))) Out(o, n, "%lu %s", objectId, name);
    else Out(o, n, "%lu", objectId);
}
void SvInstName(DWORD inst, char *o, size_t n) {
    if (!InstanceObjectName(inst, o, n)) Out(o, n, "?");
}

// ---- the arena walk: fn(block address, type, size) -> false stops; returns the block count, -1 = no arena
struct SvWalkEnd { DWORD used, stopAt; bool cut; };
template <typename F> int SvWalk(DWORD arena, F fn, SvWalkEnd *end = nullptr) {
    DWORD used = 0;
    if (end) { end->used = 0; end->stopAt = 0; end->cut = false; }
    if (!arena || !ReadDword(arena + kSvUsed, &used) || used > kSvUsed) return -1;
    if (end) end->used = used;
    int count = 0;
    for (DWORD off = 0; off < used;) {
        DWORD head = 0;
        const DWORD size = ReadDword(arena + off, &head) ? (head >> 8) * 4 : 0;
        if (!size || off + size > used) { if (end) { end->stopAt = off; end->cut = true; } break; }
        ++count;
        if (!fn(arena + off, static_cast<int>(head & 0xff), size)) break;
        off += size;
    }
    return count;
}
// the restore verdict of a block 3 / 4 (the pass 0x555640 with 0x5bb160 / 0x5bb640, read only); *ready = would come
// back at the next pass. The pass removes a slot when the unit is not loaded (0x55567a) or the restore returned an
// instance / set the out flag (0x55569b); "instance exists" (0x5bb1c3 / 0x5bb692) and the wait paths (0x5bb5bd /
// 0x5bba06) return 0 with the flag 0 - the slot stays (0x5556a1)
void SvVerdict(DWORD blk, int type, char *o, size_t n, bool *ready = nullptr, bool buffered = false) {
    if (ready) *ready = false;
    DWORD unit = 0, intro = 0, parent = 0, objectId = 0;
    ReadDword(blk + 4, &unit);
    ReadDword(blk + 0x10, &parent);
    ReadDword(blk + 0x14, &intro);
    char u[80];
    bool loaded = false;
    SvUnitText(unit, u, sizeof(u), &loaded);
    if (!loaded) {
        if (buffered) Out(o, n, "unit %s - the next pass takes it out of the buffer (the unit's next load buffers it "
                                "again, 0x5556d0)", u);
        else Out(o, n, "waits for its unit %s to load", u);
        return;
    }
    bool removing = false;
    if (SvInstFind(intro, &removing)) {
        Out(o, n, "instance exists - no restore%s", buffered ? " (the pass returns 0 and keeps the slot)" : "");
        return;
    }
    if (type == 3) {
        ReadDword(blk + 8, &objectId);
    } else {
        const DWORD rec = SvIntroRecord(SvUnitEntry(unit), intro);
        WORD w = 0;
        if (!rec || !ReadWord(rec + 0x50, &w)) { Out(o, n, "no intro record %lu in its unit - the pass keeps it", intro); return; }
        objectId = w;
    }
    const int st = SvTracker(objectId);
    char obj[80];
    SvObjText(objectId, obj, sizeof(obj));
    if (st != 2) {
        if (st < 0) Out(o, n, "waits: object %s not loaded (no tracker entry - the pass asks the loader)", obj);
        else Out(o, n, "waits: object %s not loaded (tracker status %d)", obj, st);
        return;
    }
    if (parent) {
        bool pr = false;
        if (!SvInstFind(parent, &pr)) {
            const int dl = SvDeadBit(SvArena(false), parent);
            Out(o, n, "waits: link parent %lu missing%s (dead bit %s)", parent, pr ? " (being removed)" : "",
                dl < 0 ? "-" : dl ? "1" : "0");
            return;
        }
    }
    if (ready) *ready = true;
    Out(o, n, "ready - restores at the next pass%s", removing ? " (old instance being removed)" : "");
}
// one block in words
void SvBlockText(DWORD blk, int type, DWORD size, DWORD arena, char *o, size_t n) {
    DWORD w[8] = {};
    for (int i = 1; i < 8 && static_cast<DWORD>(i * 4) < size; ++i) ReadDword(blk + i * 4, &w[i]);
    char u[80], b[80], obj[80];
    const DWORD off = blk - arena;
    switch (type) {
    case 1: Out(o, n, "+0x%lx block 1 (unit) %lu B, unit %lu", off, size, w[1]); break;
    case 2: Out(o, n, "+0x%lx block 2 (instance extra) intro %lu, %lu B", off, w[2], size); break;
    case 3: {
        float pos[3] = {};
        ReadFloats(blk + 0x20, pos, 3);
        SvUnitText(w[1], u, sizeof(u));
        SvUnitText(w[3], b, sizeof(b));
        SvObjText(w[2], obj, sizeof(obj));
        Out(o, n, "+0x%lx block 3 intro %lu object %s, unit %s, birth unit %s%s, link parent %lu, iflags 0x%08lx "
            "0x%08lx, position %.0f %.0f %.0f (unit-relative)", off, w[5], obj, u, b, w[1] != w[3] ? " (MOVED)" : "",
            w[4], w[6], w[7], pos[0], pos[1], pos[2]);
        break;
    }
    case 4: {
        WORD pf = 0, rf = 0;
        ReadWord(blk + 0x18, &pf);
        ReadWord(blk + 0x1a, &rf);
        SvUnitText(w[1], u, sizeof(u));
        Out(o, n, "+0x%lx block 4 intro %lu, birth unit %s, link parent %lu, iflags 0x%08lx 0x%08lx, position saved %u, "
            "rotation saved %u", off, w[5], u, w[4], w[2], w[3], pf, rf);
        break;
    }
    case 5: Out(o, n, "+0x%lx block 5 (anim state) intro %lu", off, w[2]); break;
    case 6: Out(o, n, "+0x%lx block 6 (game block) %lu B", off, size); break;
    default: Out(o, n, "+0x%lx block %d, %lu B", off, type, size); break;
    }
}
// the intro id a block belongs to (types 2 / 5: +8, 3 / 4: +0x14), 0 = none
DWORD SvBlockIntro(DWORD blk, int type) {
    DWORD v = 0;
    if (type == 2 || type == 5) ReadDword(blk + 8, &v);
    else if (type == 3 || type == 4) ReadDword(blk + 0x14, &v);
    return v;
}
// a long answer into TruMenu.log in pieces of at most 1800 characters
void SvLogLong(const char *tag, const char *text) {
    const size_t len = strlen(text);
    const int parts = static_cast<int>((len + 1799) / 1800);
    for (int i = 0; i < parts && i < kSvLogMax; ++i)
        Log(1, "%s (%d/%d): %.1800s", tag, i + 1, parts, text + static_cast<size_t>(i) * 1800);
}

// ---- inventory
const char *const kSvWm = "WeaponManager [[0xfadb58]+0x500]";
// state of one inventory intro id: the instance, else its block / waiting slot / dead bit
void SvIdState(DWORD id, char *o, size_t n) {
    bool removing = false;
    const DWORD inst = SvInstFind(id, &removing);
    char name[64];
    if (inst) { SvInstName(inst, name, sizeof(name)); Out(o, n, "%lu %s", id, name); return; }
    size_t used = 0;
    o[0] = 0;
    LabelAdd(o, n, &used, "%lu NO INSTANCE%s", id, removing ? " (being removed)" : "");
    const DWORD live = SvArena(false);
    int blocks = 0;
    SvWalk(live, [&](DWORD blk, int type, DWORD size) {
        if ((type == 3 || type == 4) && SvBlockIntro(blk, type) == id && blocks < 2) {
            DWORD unit = 0;
            ReadDword(blk + 4, &unit);
            char u[80];
            SvUnitText(unit, u, sizeof(u));
            LabelAdd(o, n, &used, ", block %d +0x%lx unit %s", type, blk - live, u);
            ++blocks;
        }
        (void)size;
        return true;
    });
    if (!blocks) LabelAdd(o, n, &used, ", no block 3 / 4");
    for (DWORD i = 0; i < kSvWaitSlots; ++i) {
        const DWORD e = kSvWait + i * kSvWaitSize;
        DWORD wid = 0;
        if (HandleInstance(e) && ReadDword(e + 8, &wid) && wid == id) LabelAdd(o, n, &used, ", waiting slot %lu", i);
    }
    const int dl = SvDeadBit(live, id);
    if (dl > 0) LabelAdd(o, n, &used, ", dead bit 1");
}
// the inventory area of one game block; compare = the other block's area (0 = none)
void SvInvText(DWORD gb, const char *which, char *o, size_t n, size_t *used) {
    if (!gb) { LabelAdd(o, n, used, "%s game block: none", which); return; }
    const DWORD inv = gb + kSvInv;
    BYTE b44 = 0, bd4 = 0;
    DWORD f4 = 0, f8 = 0, fc = 0, unit = 0;
    ReadByte(inv + 0x44, &b44);
    ReadByte(inv + 0xd4, &bd4);
    ReadDword(inv + 4, &f4);
    ReadDword(inv + 8, &f8);
    ReadDword(inv + 0xc, &fc);
    ReadDword(gb + 0x1a8, &unit);
    char u[80], unitName[64] = "", cp[16] = "?";
    SvUnitText(unit, u, sizeof(u));
    ReadString(gb + 0x10, unitName, sizeof(unitName));
    DWORD cpId = 0;
    if (ReadDword(gb + 0x90, &cpId)) Out(cp, sizeof(cp), "%lu", cpId);
    LabelAdd(o, n, used, "%s game block 0x%08lx (unit '%s', checkpoint %s, player unit +0x1a8 %s): +0x44 %u, +4/+8/+0xc "
             "0x%08lx 0x%08lx 0x%08lx; 15 ids:", which, gb, SvUnitPrintable(unitName) ? unitName : "?", cp, u, b44, f4,
             f8, fc);
    for (int part = 0; part < 2; ++part) {
        const int count = part ? 8 : 15;
        const DWORD at = inv + (part ? 0x84 : 0x48);
        int shown = 0;
        if (part) LabelAdd(o, n, used, " 8 ids:");
        for (int i = 0; i < count; ++i) {
            DWORD id = 0;
            if (!ReadDword(at + i * 4, &id) || static_cast<LONG>(id) < 1) continue;
            char s[220];
            SvIdState(id, s, sizeof(s));
            LabelAdd(o, n, used, " [%d] %s;", i, s);
            ++shown;
        }
        if (!shown) LabelAdd(o, n, used, " none;");
    }
    LabelAdd(o, n, used, " counts +0xa4:");
    for (int i = 0; i < 6; ++i) {
        WORD c = 0;
        ReadWord(inv + 0xa4 + i * 2, &c);
        LabelAdd(o, n, used, " %u", c);
    }
    float fl[6] = {};
    ReadFloats(inv + 0xbc, fl, 6);
    LabelAdd(o, n, used, "; floats +0xbc: %g %g %g %g %g %g; +0xd4 %u", fl[0], fl[1], fl[2], fl[3], fl[4], fl[5], bd4);
}
// the live inventory: WeaponManager slots (right hand WM+4+16i, gear WM+0xf4+8i) as intro ids
void SvWmText(char *o, size_t n, size_t *used) {
    DWORD p = PlayerState(), wm = 0, wm0 = 0;
    if (!p || !ReadDword(p + 0x500, &wm) || !wm) { LabelAdd(o, n, used, "%s: none (no player)", kSvWm); return; }
    ReadDword(wm, &wm0);
    LabelAdd(o, n, used, "%s 0x%08lx (+0 %s): 15 slots:", kSvWm, wm, wm0 ? "set" : "0");
    for (int part = 0; part < 2; ++part) {
        int shown = 0;
        if (part) LabelAdd(o, n, used, " 8 gear:");
        for (int i = 0; i < (part ? 8 : 15); ++i) {
            const DWORD inst = HandleInstance(wm + (part ? 0xf4 + 8 * i : 4 + 16 * i));
            if (!inst) continue;
            DWORD id = 0;
            char name[64];
            ReadDword(inst + 0x58, &id);
            SvInstName(inst, name, sizeof(name));
            LabelAdd(o, n, used, " [%d] %lu %s;", i, id, name);
            ++shown;
        }
        if (!shown) LabelAdd(o, n, used, " none;");
    }
}
bool SvSameInv(DWORD a, DWORD b) {            // the inventory areas (0x34c .. 0x420) of two game blocks equal
    if (!a || !b) return false;
    for (DWORD off = 0; off < 0xd8; off += 4) {
        DWORD x = 0, y = 0;
        if (!ReadDword(a + kSvInv + off, &x) || !ReadDword(b + kSvInv + off, &y) || x != y) return false;
    }
    return true;
}

// ---- items (TruLink thread, read only)
bool SvReady(char *o, size_t n) {
    if (!SvCheck()) { Out(o, n, "disabled: pre-check failed (%s)", g_svWhy); return false; }
    if (!SvArena(false) || !SvArena(true)) { Out(o, n, "no SaveInfo arenas yet ([0xc59258] / [0xc5925c] = 0)"); return false; }
    return true;
}
void ValSvStatus(char *o, size_t n) {
    Out(o, n, "%s; [Log] Save %ld, lines %s (%s); saves %ld, restores %ld seen with lines on", g_svOk ? "checks ok" :
        g_svWhy, g_svLogOn, g_svPatchOn ? "on" : g_svRefused ? "refused" : "off", g_svHookWhy, g_svSaves, g_svRestores);
}
// save.pending [all]: the buffered blocks (0xc57258) with their restore verdict; then the blocks 3 / 4 of the live
// arena without an instance that moved unit (block 3, +4 != +0xc) or hang on a link parent (+0x10) - all = every
// block 3 / 4 without an instance
bool RunSvPending(const char *arg, char *o, size_t n) {
    if (!SvReady(o, n)) return false;
    const bool all = arg && !_stricmp(arg, "all");
    size_t used = 0;
    o[0] = 0;
    DWORD count = 0;
    ReadDword(kSvBufferCount, &count);
    LabelAdd(o, n, &used, "buffered [0xc59260] = %lu of %lu:", count, kSvBufferSlots);
    int listed = 0, ready = 0;
    const DWORD live = SvArena(false);
    for (DWORD i = 0; i < kSvBufferSlots; ++i) {
        DWORD blk = 0, head = 0;
        if (!ReadDword(kSvBuffer + i * 4, &blk) || !blk || !ReadDword(blk, &head)) continue;
        const int type = static_cast<int>(head & 0xff);
        char text[600], v[200];
        bool r = false;
        SvBlockText(blk, type, (head >> 8) * 4, live, text, sizeof(text));
        if (type == 3 || type == 4) SvVerdict(blk, type, v, sizeof(v), &r, true);
        else Out(v, sizeof(v), "type %d - not a restore block", type);
        if (r) ++ready;
        LabelAdd(o, n, &used, " slot %lu: %s -> %s;", i, text, v);
        ++listed;
    }
    if (!listed) LabelAdd(o, n, &used, " none;");
    else LabelAdd(o, n, &used, " %d listed, %d ready;", listed, ready);
    int suspects = 0, noInst = 0, b34 = 0;
    LabelAdd(o, n, &used, " live arena blocks 3 / 4 without an instance%s:", all ? "" : " that moved unit or hang on a "
             "link parent");
    SvWalkEnd end = {};
    const int blocks = SvWalk(live, [&](DWORD blk, int type, DWORD size) {
        if (type != 3 && type != 4) return true;
        ++b34;
        const DWORD intro = SvBlockIntro(blk, type);
        if (SvInstFind(intro)) return true;
        ++noInst;
        DWORD unit = 0, birth = 0, parent = 0;
        ReadDword(blk + 4, &unit);
        ReadDword(blk + 0xc, &birth);
        ReadDword(blk + 0x10, &parent);
        const bool moved = type == 3 && unit != birth;
        if (!all && !moved && !parent) return true;
        ++suspects;
        if (used + 900 < n) {
            char text[600], v[200];
            SvBlockText(blk, type, size, live, text, sizeof(text));
            SvVerdict(blk, type, v, sizeof(v));
            LabelAdd(o, n, &used, " %s -> %s;", text, v);
        }
        return true;
    }, &end);
    LabelAdd(o, n, &used, " %d of %d without an instance listed (%d blocks 3 / 4, %d blocks, used 0x%lx%s)", suspects,
             noInst, b34, blocks, end.used, end.cut ? ", walk stopped early" : "");
    if (used + 2 >= n) LabelAdd(o, n, &used, " ... (cut)");
    SvLogLong("save.pending", o);
    return true;
}
// save.inv: the inventory area of the live and the snapshot game block, and the live WeaponManager slots
bool RunSvInv(const char *, char *o, size_t n) {
    if (!SvReady(o, n)) return false;
    size_t used = 0;
    o[0] = 0;
    DWORD gbl = 0, gbs = 0;
    ReadDword(kSvGbLive, &gbl);
    ReadDword(kSvGbSnap, &gbs);
    SvInvText(gbl, "live", o, n, &used);
    if (SvSameInv(gbl, gbs)) LabelAdd(o, n, &used, " | snapshot game block 0x%08lx: inventory area equal to live", gbs);
    else { LabelAdd(o, n, &used, " | "); SvInvText(gbs, "snapshot", o, n, &used); }
    LabelAdd(o, n, &used, " | now: ");
    SvWmText(o, n, &used);
    SvLogLong("save.inv", o);
    return true;
}
// save.waiting: the 64 slots of 0xc592a8 (items waiting for their instance)
bool RunSvWaiting(const char *, char *o, size_t n) {
    if (!SvReady(o, n)) return false;
    size_t used = 0;
    o[0] = 0;
    int live = 0, stale = 0;
    DWORD player = 0;
    ReadDword(kPlayerPtr, &player);
    LabelAdd(o, n, &used, "waiting table 0xc592a8:");
    for (DWORD i = 0; i < kSvWaitSlots; ++i) {
        const DWORD e = kSvWait + i * kSvWaitSize;
        DWORD owner = 0, id = 0, cb = 0, flag = 0;
        if (!ReadDword(e, &owner) || !owner) continue;
        ReadDword(e + 8, &id);
        ReadDword(e + 0xc, &cb);
        ReadDword(e + 0x10, &flag);
        const DWORD inst = HandleInstance(e);
        if (!inst) { ++stale; continue; }    // a free slot for 0x5550a0
        ++live;
        DWORD oid = 0;
        char oname[64], st[220];
        ReadDword(inst + 0x58, &oid);
        SvInstName(inst, oname, sizeof(oname));
        SvIdState(id, st, sizeof(st));
        LabelAdd(o, n, &used, " [%lu] owner %lu %s%s, id %s, callback 0x%08lx%s, flag %lu;", i, oid, oname,
                 inst == player ? " (Lara)" : "", st, cb, cb == kSvInvCallback ? " (inventory 0x715e90)" : "", flag);
    }
    LabelAdd(o, n, &used, " %d waiting of %lu, %d stale handles (owner gone = free slot)", live, kSvWaitSlots, stale);
    SvLogLong("save.waiting", o);
    return true;
}
// save.find <id>: where an intro / instance id appears
bool RunSvFind(const char *arg, char *o, size_t n) {
    if (!SvReady(o, n)) return false;
    char *endp = nullptr;
    const DWORD id = arg && arg[0] ? strtoul(arg, &endp, 0) : 0;
    if (!id || !endp || *endp) { Out(o, n, "usage: save.find <intro id> (decimal or 0x hex)"); return false; }
    size_t used = 0;
    o[0] = 0;
    LabelAdd(o, n, &used, "id %lu:", id);
    // instance list
    int inList = 0;
    ForInstances([&](const InstInfo &x) {
        if (static_cast<DWORD>(x.intro) != id) return true;
        DWORD e0 = 0, e4 = 0, link = 0, fl = 0;
        ReadDword(x.addr + 0xe0, &e0);
        ReadDword(x.addr + 0xe4, &e4);
        ReadDword(x.addr + 0x228, &link);
        ReadDword(x.addr + 0x14, &fl);
        char u[80], b[80];
        SvUnitText(e0, u, sizeof(u));
        SvUnitText(e4, b, sizeof(b));
        LabelAdd(o, n, &used, " instance 0x%08lx %s at %.0f %.0f %.0f, unit +0xe0 %s, birth +0xe4 %s, link parent +0x228 "
                 "%lu, iflags 0x%08lx;", x.addr, x.name, x.pos[0], x.pos[1], x.pos[2], u, b, link, fl);
        ++inList;
        return true;
    });
    bool removing = false;
    const DWORD found = SvInstFind(id, &removing);
    LabelAdd(o, n, &used, " INSTANCE_Find: %s", found ? "" : removing ? "none (being removed)" : "none");
    if (found) LabelAdd(o, n, &used, "0x%08lx", found);
    if (!inList) LabelAdd(o, n, &used, ", not in the instance list");
    LabelAdd(o, n, &used, ";");
    // both arenas: blocks of the id and blocks that hang on it (link parent)
    for (int s = 0; s < 2; ++s) {
        const DWORD arena = SvArena(s != 0);
        int hits = 0, kids = 0;
        LabelAdd(o, n, &used, " %s arena 0x%08lx:", s ? "snapshot" : "live", arena);
        SvWalk(arena, [&](DWORD blk, int type, DWORD size) {
            DWORD parent = 0;
            if ((type == 3 || type == 4) && ReadDword(blk + 0x10, &parent) && parent == id && kids < 8) {
                LabelAdd(o, n, &used, " child block %d intro %lu at +0x%lx;", type, SvBlockIntro(blk, type), blk - arena);
                ++kids;
            }
            if (SvBlockIntro(blk, type) != id) return true;
            char text[600];
            SvBlockText(blk, type, size, arena, text, sizeof(text));
            LabelAdd(o, n, &used, " %s", text);
            if (!s && (type == 3 || type == 4)) {
                char v[200];
                SvVerdict(blk, type, v, sizeof(v));
                LabelAdd(o, n, &used, " [restore: %s]", v);
            }
            LabelAdd(o, n, &used, ";");
            ++hits;
            return true;
        });
        const int dl = SvDeadBit(arena, id);
        LabelAdd(o, n, &used, " %d block(s), dead bit %s;", hits, dl < 0 ? "- (outside the table)" : dl ? "1" : "0");
    }
    // buffer, waiting table
    int buf = 0;
    for (DWORD i = 0; i < kSvBufferSlots; ++i) {
        DWORD blk = 0, head = 0;
        if (!ReadDword(kSvBuffer + i * 4, &blk) || !blk || !ReadDword(blk, &head)) continue;
        if (SvBlockIntro(blk, static_cast<int>(head & 0xff)) == id) { LabelAdd(o, n, &used, " buffered in slot %lu;", i); ++buf; }
    }
    if (!buf) LabelAdd(o, n, &used, " not buffered;");
    int wait = 0;
    for (DWORD i = 0; i < kSvWaitSlots; ++i) {
        const DWORD e = kSvWait + i * kSvWaitSize;
        DWORD wid = 0, oid = 0;
        const DWORD owner = HandleInstance(e);
        if (!owner || !ReadDword(e + 8, &wid) || wid != id) continue;
        ReadDword(owner + 0x58, &oid);
        LabelAdd(o, n, &used, " waiting slot %lu (owner %lu);", i, oid);
        ++wait;
    }
    if (!wait) LabelAdd(o, n, &used, " not in the waiting table;");
    // inventory areas and the live slots
    for (int s = 0; s < 2; ++s) {
        DWORD gb = 0;
        ReadDword(s ? kSvGbSnap : kSvGbLive, &gb);
        for (int i = 0; gb && i < 23; ++i) {
            DWORD v = 0;
            if (ReadDword(gb + kSvInv + (i < 15 ? 0x48 + i * 4 : 0x84 + (i - 15) * 4), &v) && v == id)
                LabelAdd(o, n, &used, " %s inventory %s[%d];", s ? "snapshot" : "live", i < 15 ? "15 ids" : "8 ids",
                         i < 15 ? i : i - 15);
        }
    }
    DWORD p = PlayerState(), wm = 0;
    if (p && ReadDword(p + 0x500, &wm) && wm)
        for (int i = 0; i < 23; ++i) {
            const DWORD inst = HandleInstance(wm + (i < 15 ? 4 + 16 * i : 0xf4 + 8 * (i - 15)));
            DWORD v = 0;
            if (inst && ReadDword(inst + 0x58, &v) && v == id)
                LabelAdd(o, n, &used, " %s %s[%d] now;", kSvWm, i < 15 ? "slot" : "gear", i < 15 ? i : i - 15);
        }
    SvLogLong("save.find", o);
    return true;
}

// ---- [Log] Save: one summary per SAVE_SaveGame / SAVE_RestoreGame (game thread, inside the save)
struct SvSum { DWORD used; int blocks, type[8], moved, dead; bool cut; };
void SvSummarize(DWORD arena, SvSum *s) {
    memset(s, 0, sizeof(*s));
    SvWalkEnd end = {};
    s->blocks = SvWalk(arena, [&](DWORD blk, int type, DWORD) {
        ++s->type[type & 7];
        DWORD unit = 0, birth = 0;
        if (type == 3 && ReadDword(blk + 4, &unit) && ReadDword(blk + 0xc, &birth) && unit != birth) ++s->moved;
        return true;
    }, &end);
    s->used = end.used;
    s->cut = end.cut;
    for (DWORD i = 0; arena && i < kSvDeadBytes; i += 4) {
        DWORD v = 0;
        if (ReadDword(arena + kSvDead + i, &v))
            for (; v; v &= v - 1) ++s->dead;
    }
}
void SvSumText(const SvSum &s, char *o, size_t n) {
    Out(o, n, "used 0x%lx, %d blocks (1:%d 2:%d 3:%d 4:%d 5:%d 6:%d%s), %d moved block 3, %d dead bits", s.used, s.blocks,
        s.type[1], s.type[2], s.type[3], s.type[4], s.type[5], s.type[6], s.cut ? ", walk stopped early" : "", s.moved,
        s.dead);
}
void SvCallerText(DWORD ret, char *o, size_t n) {
    static const struct { DWORD ret; const char *what; } kKnown[] = {
        {0x006a1e17, "call 0x6a1e12 in 0x6a1a70"},
        {0x005dfbbc, "dev.reload_current_unit 0x5dfba0"},
        {0x005de6fa, "player spawn 0x5d40c0 (jmp 0x5d4330) after the death reload 0x5de480 (0x5de6f5)"},
        {0x005de179, "player spawn 0x5d40c0 (jmp 0x5d4330) from 0x5de040 (0x5de174)"},
        {0x005de53c, "death reload 0x5de480 (0x5de537)"},
        {0x0078b00f, "save file load 0x78ab60 (0x78b00a)"},
        {0x0078b0fa, "0x78ab60 (0x78b0f5)"},
        {0x0078b21c, "0x78ab60 (0x78b217)"},
    };
    for (const auto &k : kKnown)
        if (k.ret == ret) { Out(o, n, "0x%08lx = %s", ret, k.what); return; }
    char mod[64];
    ModuleOf(reinterpret_cast<const void *>(ret), mod, sizeof(mod));
    Out(o, n, "0x%08lx (%s)", ret, mod);
}
// the inventory ids of a game block with the block each id has in the arena: "15 [i]=id t<type> <unit>; ..."
void SvInvBlocks(DWORD gb, DWORD arena, char *o, size_t n) {
    size_t used = 0;
    o[0] = 0;
    if (!gb) { Out(o, n, "no game block"); return; }
    DWORD ids[23] = {}, units[23] = {};
    int types[23] = {}, k = 0;
    for (int i = 0; i < 23; ++i)
        if (ReadDword(gb + kSvInv + (i < 15 ? 0x48 + i * 4 : 0x84 + (i - 15) * 4), &ids[i]) && static_cast<LONG>(ids[i]) >= 1)
            ++k;
        else ids[i] = 0;
    if (k) SvWalk(arena, [&](DWORD blk, int t, DWORD) {    // one walk for all ids: the first block 3 / 4 of each
        if (t != 3 && t != 4) return true;
        const DWORD intro = SvBlockIntro(blk, t);
        for (int i = 0; i < 23; ++i)
            if (ids[i] == intro && !types[i]) { types[i] = t; ReadDword(blk + 4, &units[i]); }
        return true;
    });
    for (int i = 0; i < 23; ++i) {
        if (!ids[i]) continue;
        char u[80] = "-", name[64] = "";
        if (types[i]) SvUnitText(units[i], u, sizeof(u));
        const DWORD inst = SvInstFind(ids[i]);
        if (inst) SvInstName(inst, name, sizeof(name));
        LabelAdd(o, n, &used, "%s%s[%d] %lu%s%s block %d %s", used ? "; " : "", i < 15 ? "" : "g", i < 15 ? i : i - 15,
                 ids[i], name[0] ? " " : "", name, types[i], u);
    }
    WORD c[6] = {};
    for (int i = 0; i < 6; ++i) ReadWord(gb + kSvInv + 0xa4 + i * 2, &c[i]);
    LabelAdd(o, n, &used, "%scounts %u %u %u %u %u %u", used ? "; " : "", c[0], c[1], c[2], c[3], c[4], c[5]);
}
int SvWaitCount(int *lara) {
    int k = 0;
    DWORD player = 0;
    ReadDword(kPlayerPtr, &player);
    *lara = 0;
    for (DWORD i = 0; i < kSvWaitSlots; ++i) {
        const DWORD inst = HandleInstance(kSvWait + i * kSvWaitSize);
        if (!inst) continue;
        ++k;
        if (inst == player) ++*lara;
    }
    return k;
}
void SvGameBlockText(DWORD gb, char *o, size_t n) {
    char unit[64] = "";
    DWORD cp = 0;
    if (!gb || !ReadString(gb + 0x10, unit, sizeof(unit)) || !SvUnitPrintable(unit)) Out(unit, sizeof(unit), "?");
    ReadDword(gb + 0x90, &cp);
    Out(o, n, "unit '%s' checkpoint %lu", unit, cp);
}
void SvOnSave(DWORD ret, BYTE arg) {
    const LONG k = InterlockedIncrement(&g_svSaves);
    DWORD snap = 0, gbs = 0, buffered = 0, unitNow = 0;
    ReadDword(kSvSnap, &snap);
    ReadDword(kSvGbSnap, &gbs);
    ReadDword(kSvBufferCount, &buffered);
    ReadDword(kUnitId, &unitNow);
    SvSum s;
    SvSummarize(snap, &s);
    char caller[160], sum[200], gbt[120], u[80], inv[1600];
    SvCallerText(ret, caller, sizeof(caller));
    SvSumText(s, sum, sizeof(sum));
    SvGameBlockText(gbs, gbt, sizeof(gbt));
    SvUnitText(unitNow, u, sizeof(u));
    int lara = 0;
    const int wait = SvWaitCount(&lara);
    Log(1, "save: #%ld SAVE_SaveGame(%u) from %s: snapshot %s; %s; Lara's unit %s; buffered %lu, waiting %d (Lara %d)", k,
        arg, caller, gbt, sum, u, buffered, wait, lara);
    SvInvBlocks(gbs, snap, inv, sizeof(inv));
    Log(1, "save: #%ld inventory in the snapshot (%s): %s", k, arg ? "not rewritten - SaveGame(1) only copies" :
        "written by the player query 0x17 just now", inv);
}
void SvOnRestore(DWORD ret, DWORD arg, const SvSum &before) {
    const LONG k = InterlockedIncrement(&g_svRestores);
    DWORD live = 0, gbl = 0, buffered = 0, check = 0;
    ReadDword(kSvLive, &live);
    ReadDword(kSvGbLive, &gbl);
    ReadDword(kSvBufferCount, &buffered);
    ReadDword(live + kSvCheckWord, &check);
    SvSum after;
    SvSummarize(live, &after);
    char caller[160], b[200], a[200], gbt[120], inv[1600];
    SvCallerText(ret, caller, sizeof(caller));
    SvSumText(before, b, sizeof(b));
    SvSumText(after, a, sizeof(a));
    SvGameBlockText(gbl, gbt, sizeof(gbt));
    int lara = 0;
    const int wait = SvWaitCount(&lara);
    Log(1, "save: #%ld SAVE_RestoreGame(%lu) from %s: live before %s; after the copy %s (%s); rolled back: blocks %+d, "
        "block 3 %+d, block 4 %+d, dead bits %+d; check word 0x%08lx%s; buffered %lu (cleared next), waiting %d (Lara %d)",
        k, arg, caller, b, a, gbt, after.blocks - before.blocks, after.type[3] - before.type[3],
        after.type[4] - before.type[4], after.dead - before.dead, check, check == 0xdeadbeef ? "" : " (NOT 0xdeadbeef)",
        buffered, wait, lara);
    SvInvBlocks(gbl, live, inv, sizeof(inv));
    Log(1, "save: #%ld inventory after the copy (handed back by 0x715ef0 at the player's restore): %s", k, inv);
}
typedef void *(__cdecl *SvCopyFn)(void *, const void *, size_t);
// 0x557127: [ret 0x55712c][d][s][n][SAVE_SaveGame's return][its byte argument] (no push between entry and the call)
void *__cdecl SvSaveCopy(void *d, const void *s, size_t n) {
    const DWORD *frame = static_cast<const DWORD *>(_AddressOfReturnAddress());
    void *r = reinterpret_cast<SvCopyFn>(kSvCopy)(d, s, n);
    __try {
        SvOnSave(frame[4], static_cast<BYTE>(frame[5] & 0xff));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
    }
    return r;
}
// 0x5571a3: 0x1c locals, 4 registers, 2 print arguments, 3 copy arguments -> SAVE_RestoreGame's return at frame[17]
void *__cdecl SvRestoreCopy(void *d, const void *s, size_t n) {
    const DWORD *frame = static_cast<const DWORD *>(_AddressOfReturnAddress());
    SvSum before;
    __try {
        SvSummarize(reinterpret_cast<DWORD>(d), &before);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        memset(&before, 0, sizeof(before));
    }
    void *r = reinterpret_cast<SvCopyFn>(kSvCopy)(d, s, n);
    __try {
        SvOnRestore(frame[17], frame[18], before);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        InterlockedIncrement(&g_ownExceptions);
    }
    return r;
}
// [Log] Save from TruMenu.ini (the switches row is "live": TruMenu reads the key again about once a second)
void SvReadSwitch() {
    if (!g_iniPath[0]) return;
    const LONG v = GetPrivateProfileIntA("Log", "Save", atoi(OptDefault("Log", "Save")), g_iniPath) != 0 ? 1 : 0;
    const LONG was = InterlockedExchange(&g_svLogOn, v);
    if (g_svRead && was != v) {
        Log(1, "save: [Log] Save %ld -> %ld (TruMenu.ini, live)", was, v);
        g_svRefused = false;                  // a new try after a refusal
        g_svNotedNoHook = false;
    }
    g_svRead = true;
}
// PadHook, once per game frame: the switch about once a second, the unit names, the two call patches to the switch
void SvTick() {
    const DWORD now = GetTickCount();
    if (now - g_svReadTick >= 1000) {
        g_svReadTick = now;
        SvReadSwitch();
        if (g_streamNameOk) SvUnitCacheTick();
    }
    const bool want = g_svLogOn != 0;
    if (want == g_svPatchOn) return;
    SvCheck();
    if (want && !g_svHookOk) {
        if (!g_svNotedNoHook) Log(0, "save: [Log] Save=1 but no lines - %s", g_svHookWhy);
        g_svNotedNoHook = true;
        return;
    }
    M21PatchGroup(g_svPatches, 2, want, &g_svPatchOn, &g_svRefused, "0.22.27 [Log] Save: save / restore lines",
                  want ? "[Log] Save=1" : "[Log] Save=0");
}
// ---- end of 0.22.27 save probe
