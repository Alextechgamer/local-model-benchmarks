#!/bin/bash
# Third pass: the pagoda prompt on every free opencode model (the 11 priced at zero on 2026-10-11), all under
# the second-pass conditions: reply cap raised to 64,000 tokens and the "do not wait for approval" line.
# Three cloud runs at a time (a new one starts as soon as a slot frees), each in its own folder, 40-minute cap each.
# Pages are collected and checked afterwards by collect_r3.py.
cd /e/strata-tests || exit 1
export OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX=64000
PROMPT="$(cat pagoda-local-input.txt)
Do not wait for approval of a design or plan: nobody is available to answer. Go straight to building and finish in this one run."
cloud() {   # cloud <folder-name> <model>
  mkdir -p "pagoda-$1" && cp pagoda-luna/opencode.json "pagoda-$1/opencode.json"
  ( cd "pagoda-$1" && t0=$(date +%s) && timeout 2400 opencode run "$PROMPT" --pure -m "$2" --format json > "../pagoda-$1-stream.jsonl" 2> "../pagoda-$1-stderr.txt" < /dev/null; echo "$1 exit $? elapsed $(( $(date +%s) - t0 )) s" | tee "../pagoda-$1-time.txt" )
}
while read -r name model; do
  while [ "$(jobs -rp | wc -l)" -ge 3 ]; do wait -n; done
  cloud "$name-r3" "opencode/$model" &
done <<'EOF'
pickle big-pickle
exo exo-free
ling30 ling-3.0-flash-fin-free
ling31 ling-3.1-flash-free
longcat longcat-2.5-preview-free
mimo mimo-v2.6-flash-free
muse muse-spark-1.3-contributor-free
nemoultra nemotron-3-ultra-free
nemolight nemotron-3.5-lightning-free
bunny space-bunny-free
step5 step-5-preview-free
EOF
wait
echo "ALL DONE"
