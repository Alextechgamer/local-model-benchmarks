#!/bin/bash
# Pagoda prompt on GPT-6 Luna (repeat) and the remaining free opencode models: three cloud runs at a time,
# each in its own folder with the same superpowers-only config, 40-minute cap each. Page checks at the end.
cd /c/Users/user/strata-tests || exit 1
PROMPT="$(cat pagoda-local-input.txt)"
cloud() {   # cloud <folder-name> <model>
  mkdir -p "pagoda-$1" && cp pagoda-luna/opencode.json "pagoda-$1/opencode.json"
  ( cd "pagoda-$1" && t0=$(date +%s) && timeout 2400 opencode run "$PROMPT" --pure -m "$2" --format json > "../pagoda-$1-stream.jsonl" 2> "../pagoda-$1-stderr.txt" < /dev/null; echo "$1 exit $? elapsed $(( $(date +%s) - t0 )) s" | tee "../pagoda-$1-time.txt" )
}
cloud luna2 opencode-go/gpt-6-luna & cloud bunny opencode/space-bunny-free & cloud longcat opencode/longcat-2.5-preview-free & wait
cloud fledge opencode/fledge-alpha-free & cloud ling31 opencode/ling-3.1-flash-free & cloud mimo opencode/mimo-v2.6-flash-free & wait
cloud muse opencode/muse-spark-1.3-contributor-free & cloud nemoultra opencode/nemotron-3-ultra-free & cloud nemolight opencode/nemotron-3.5-lightning-free & wait
for n in luna2 bunny longcat fledge ling31 mimo muse nemoultra nemolight; do
  [ -f "pagoda-$n/pagoda.html" ] && .chk/Scripts/python.exe check_page.py "$n" "pagoda-$n/pagoda.html" Pond > /dev/null 2>&1
done
echo "ALL DONE"
