// Decompile functions of a raw memory image (read-only; finding 43, shadow power translation).
// Headless post-script: for each address argument it disassembles from there, creates the function (flow-based
// body) and writes the decompiled C to the output file given as first argument.
// Usage (analyzeHeadless, raw Xbox 360 image, no auto analysis):
//   analyzeHeadless PROJ_DIR PROJ -import tu_image_82000000.bin -noanalysis -processor PowerPC:BE:64:A2ALT-32addr
//     -loader BinaryLoader -loader-baseAddr 0x82000000 -scriptPath tools/ghidra
//     -postScript TruDecompileAt.java OUT.c 0x823d7700 0x823d81a0 ... -deleteProject
// Only the decompiled text of the named functions is written (local work file, not for the repository).
//@category TRU

import java.io.PrintWriter;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;

public class TruDecompileAt extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            printerr("usage: OUT.c ADDR [ADDR ...]");
            return;
        }
        // writable memory keeps the decompiler from folding globals into constants
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            b.setWrite(true);
            b.setExecute(true);
        }
        // pass 1: create all functions first so calls between them get names
        for (int i = 1; i < args.length; i++) {
            Address a = toAddr(args[i]);
            new DisassembleCommand(a, null, true).applyTo(currentProgram, monitor);
            if (getFunctionAt(a) == null) {
                new CreateFunctionCmd(a).applyTo(currentProgram, monitor);
            }
        }
        DecompInterface di = new DecompInterface();
        DecompileOptions opt = new DecompileOptions();
        di.setOptions(opt);
        di.openProgram(currentProgram);
        try (PrintWriter out = new PrintWriter(args[0], "UTF-8")) {
            for (int i = 1; i < args.length; i++) {
                Address a = toAddr(args[i]);
                Function f = getFunctionAt(a);
                out.println("// ===== " + args[i] + (f == null ? " (no function)" : " body " + f.getBody().getMinAddress()
                        + ".." + f.getBody().getMaxAddress()));
                if (f == null) {
                    continue;
                }
                DecompileResults r = di.decompileFunction(f, 120, monitor);
                if (r.decompileCompleted()) {
                    out.println(r.getDecompiledFunction().getC());
                } else {
                    out.println("// decompile failed: " + r.getErrorMessage());
                }
            }
        }
        di.dispose();
    }
}
