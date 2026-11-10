#!/bin/bash
# Quick probe of opencode's free models (the 11 priced at zero on 2026-10-11): one small prompt each,
# 150-second cap, four at a time.
cd /e/strata-tests && mkdir -p free-probe-r3 && cp pagoda-luna/opencode.json free-probe-r3/ && cd free-probe-r3 || exit 1
PROMPT='Answer in at most 6 lines, no tools. Line 1: which model are you and which company made you (say "unknown" if you do not know). Then write a Python function is_palindrome(s) that ignores case and non-alphanumeric characters.'
probe() {
  t0=$(date +%s)
  timeout 150 opencode run "$PROMPT" --pure -m "opencode/$1" --format json > "$1.jsonl" 2> "$1.err" < /dev/null
  echo "$1 rc=$? secs=$(( $(date +%s) - t0 ))"
}
for m in big-pickle exo-free ling-3.0-flash-fin-free ling-3.1-flash-free longcat-2.5-preview-free mimo-v2.6-flash-free muse-spark-1.3-contributor-free nemotron-3-ultra-free nemotron-3.5-lightning-free space-bunny-free step-5-preview-free; do
  while [ "$(jobs -rp | wc -l)" -ge 4 ]; do wait -n; done
  probe "$m" &
done
wait
