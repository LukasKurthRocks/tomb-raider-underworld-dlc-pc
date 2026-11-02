// SelfTest.exe - offline self test of TruDataGuard.asi (no game): loads the built plugin from the given path (its
// DllMain finds no tru.exe and patches nothing), calls TruDataGuardSelfTest and prints the report.
// Build (x86): cl /nologo /O2 /MT /W4 SelfTest.cpp /Fe<out>\SelfTest.exe   Run: SelfTest.exe <out>\TruDataGuard.asi
// Exit code: 0 all passed, 1 failures, 2 load / export error.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>

typedef int(__cdecl *SelfTestFn)(char *report, int size);

int main(int argc, char **argv) {
    if (argc < 2) {
        printf("usage: SelfTest.exe <path to TruDataGuard.asi>\n");
        return 2;
    }
    HMODULE plugin = LoadLibraryA(argv[1]);
    if (!plugin) {
        printf("LoadLibrary %s failed (%lu)\n", argv[1], GetLastError());
        return 2;
    }
    SelfTestFn test = reinterpret_cast<SelfTestFn>(GetProcAddress(plugin, "TruDataGuardSelfTest"));
    if (!test) {
        printf("export TruDataGuardSelfTest not found\n");
        return 2;
    }
    static char report[16384];
    int failed = test(report, sizeof(report));
    fputs(report, stdout);
    return failed == 0 ? 0 : 1;
}
