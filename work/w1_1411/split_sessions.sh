#!/bin/sh
# W1 (2026-11-14): split copied plugin logs into one file per game session (pid) - read-only on the inputs.
# Usage: sh work/w1_1411/split_sessions.sh DIR   (DIR holds copies of TruTrace.log / TruMenu.log; writes
# DIR/TruTrace_<pid>.log and DIR/TruMenu_<pid>.log next to them)
D="$1"
[ -n "$D" ] || { echo "usage: split_sessions.sh DIR"; exit 1; }
for f in TruTrace TruMenu; do
  awk -v d="$D" -v f="$f" '/session start \(pid [0-9]+\)/ { match($0, /pid [0-9]+/); p = substr($0, RSTART+4, RLENGTH-4) } { if (p != "") print > (d "/" f "_" p ".log") }' "$D/$f.log"
done
ls -la "$D"
