#!/bin/sh
# PT.2 (2026-11-14): run one self-ending cdb command file against a dump FILE (read-only), output to a text file.
# Usage: CDB=<path to x86 cdb.exe> sh work/pt2_1411/run_cdb.sh <dump> <cmdfile> <outfile>
# (CDB defaults to "cdb" on PATH). The command file must end with "q". No symbols are loaded (-y "").
CDB="${CDB:-cdb}"
timeout 600 "$CDB" -z "$1" -y "" -cf "$2" > "$3" 2>&1
echo "exit $?"
