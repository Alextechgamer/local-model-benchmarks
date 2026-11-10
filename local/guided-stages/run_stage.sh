#!/bin/bash
# usage: run_stage.sh <name> <prompt-file>
# Runs one local Claude Code turn in pagoda-guided with the stage prompt, then loads the page and reports.
cd /c/Users/user/strata-tests/pagoda-guided || exit 1
{ cat ../guided/common.txt; echo; cat "../guided/$2"; } > "../guided/$1.in.txt"
t0=$(date +%s)
cmd //c "C:\\Users\\user\\claude-local.bat -p --permission-mode acceptEdits --output-format stream-json --verbose" < "../guided/$1.in.txt" > "../guided/$1.jsonl" 2> "../guided/$1.err"
el=$(( $(date +%s) - t0 ))
echo "$1 $el" >> ../guided/times.txt
echo "== $1: $el s, pagoda.html $(wc -c < pagoda.html 2>/dev/null) bytes"
cd .. && .chk/Scripts/python.exe check_page.py "g-$1" pagoda-guided/pagoda.html > /dev/null 2>&1
PYTHONIOENCODING=utf-8 .chk/Scripts/python.exe guided/report.py "$1"
