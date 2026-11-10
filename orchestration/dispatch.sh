#!/bin/bash
# dispatch.sh <module> <model> <round> [extra-instructions-file]
# Runs one free model on one module, in its own folder, 25-minute cap. Output files land in m-<module>-<round>/.
cd /e/strata-tests/orch-r1 || exit 1
mod=$1; model=$2; round=$3; extra=$4
dir="m-$mod-$round"; mkdir -p "$dir" && cp opencode.json "$dir/"
export OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX=64000
PROMPT="$(cat contract.md)

$(cat tasks/$mod.txt)
$( [ -n "$extra" ] && cat "$extra" )

Rules: write the file(s) into the current working directory with your write tool, under exactly the file name(s) given. Nobody is available to answer questions and
nobody will approve a plan: do not ask, do not plan out loud, just write the complete module (no placeholders, no TODOs, no truncation). Do not try to open a browser.
When done, run 'node --check <file>' on each .js file you wrote, fix any syntax error, then reply with one line: DONE."
( cd "$dir" && t0=$(date +%s) && timeout 1500 opencode run "$PROMPT" --pure -m "opencode/$model" --format json > stream.jsonl 2> stderr.txt < /dev/null; echo "$mod/$model/$round exit $? elapsed $(( $(date +%s) - t0 )) s" | tee time.txt )
