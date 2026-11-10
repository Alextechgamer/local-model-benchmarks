#!/bin/bash
# Round 2 (after the GLM provider timeout): DeepSeek V4.1 Flash, then the local one-shot rerun alone on the PC,
# then one more attempt at GLM 5.3 Flash (15-minute cap), then the page checks.
cd /c/Users/user/strata-tests || exit 1
cloud() {   # cloud <name> <model> <max-seconds>
  mkdir -p "pagoda-$1" && cp pagoda-luna/opencode.json "pagoda-$1/opencode.json"
  ( cd "pagoda-$1" && t0=$(date +%s) && timeout "$3" opencode run "$(cat ../pagoda-local-input.txt)" --pure -m "$2" --format json > "../pagoda-$1-stream.jsonl" 2> "../pagoda-$1-stderr.txt" < /dev/null; echo "$1 exit $? elapsed $(( $(date +%s) - t0 )) s" | tee "../pagoda-$1-time.txt" )
  taskkill //F //IM opencode.exe > /dev/null 2>&1
}
cloud deepseek opencode-go/deepseek-v4.1-flash 1800
mkdir -p pagoda-local2 && cd pagoda-local2
wc -l < /c/Users/user/Strata/strata-coder-iq1_m.log > ../pagoda-local2-logstart.txt
date +%s > ../pagoda-local2-t0.txt
cmd //c "C:\\Users\\user\\claude-local.bat -p --permission-mode acceptEdits --output-format stream-json --verbose" < ../pagoda-local-input.txt > ../pagoda-local2-stream.jsonl 2> ../pagoda-local2-stderr.txt
echo "local2 exit $? elapsed $(( $(date +%s) - $(cat ../pagoda-local2-t0.txt) )) s" | tee ../pagoda-local2-time.txt
date +%s > ../pagoda-local2-t1.txt
cd ..
rm -rf pagoda-glm; cloud glm opencode-go/glm-5.3-flash 900
for name in glm deepseek local2; do
  [ -f "pagoda-$name/pagoda.html" ] && .chk/Scripts/python.exe check_page.py "$name" "pagoda-$name/pagoda.html" Pond > /dev/null 2>&1
done
ls -la pagoda-glm pagoda-deepseek pagoda-local2 | cut -c1-100
