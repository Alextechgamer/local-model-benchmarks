#!/bin/bash
# Second pass for the runs that produced no page. Two changes, applied to every model equally:
#   1. opencode's reply cap raised from 32,000 to 64,000 tokens (thinking counts against it)
#   2. one extra prompt line: do not wait for approval of a design
# Three cloud runs at a time, each in its own folder, 40-minute cap each; page checks at the end.
cd /c/Users/user/strata-tests || exit 1
export OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX=64000
PROMPT="$(cat pagoda-local-input.txt)
Do not wait for approval of a design or plan: nobody is available to answer. Go straight to building and finish in this one run."
cloud() {   # cloud <folder-name> <model>
  mkdir -p "pagoda-$1" && cp pagoda-luna/opencode.json "pagoda-$1/opencode.json"
  ( cd "pagoda-$1" && t0=$(date +%s) && timeout 2400 opencode run "$PROMPT" --pure -m "$2" --format json > "../pagoda-$1-stream.jsonl" 2> "../pagoda-$1-stderr.txt" < /dev/null; echo "$1 exit $? elapsed $(( $(date +%s) - t0 )) s" | tee "../pagoda-$1-time.txt" )
}
cloud bunny-r2 opencode/space-bunny-free & cloud longcat-r2 opencode/longcat-2.5-preview-free & cloud luna-r2 opencode-go/gpt-6-luna & wait
cloud mimo-r2 opencode/mimo-v2.6-flash-free & cloud ling31-r2 opencode/ling-3.1-flash-free & cloud nemoultra-r2 opencode/nemotron-3-ultra-free & wait
cloud nemolight-r2 opencode/nemotron-3.5-lightning-free & wait
for n in bunny-r2 longcat-r2 luna-r2 mimo-r2 ling31-r2 nemoultra-r2 nemolight-r2; do
  [ -f "pagoda-$n/pagoda.html" ] && .chk/Scripts/python.exe check_page.py "$n" "pagoda-$n/pagoda.html" Pond > /dev/null 2>&1
done
echo "ALL DONE"
