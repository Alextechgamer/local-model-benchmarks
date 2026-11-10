#!/bin/bash
# Round 2: GLM 5.3 Flash and DeepSeek V4.1 Flash through opencode (superpowers only), then the local one-shot
# rerun through the lean claude-local.bat with the PC otherwise idle. Page checks run after everything.
cd /c/Users/user/strata-tests || exit 1
for pair in "glm:opencode-go/glm-5.3-flash" "deepseek:opencode-go/deepseek-v4.1-flash"; do
  name=${pair%%:*}; model=${pair#*:}
  mkdir -p "pagoda-$name" && cp pagoda-luna/opencode.json "pagoda-$name/opencode.json"
  ( cd "pagoda-$name" && t0=$(date +%s) && opencode run "$(cat ../pagoda-local-input.txt)" --pure -m "$model" --format json > "../pagoda-$name-stream.jsonl" 2> "../pagoda-$name-stderr.txt" < /dev/null; echo "$name exit $? elapsed $(( $(date +%s) - t0 )) s" | tee "../pagoda-$name-time.txt" )
done
mkdir -p pagoda-local2 && cd pagoda-local2
wc -l < /c/Users/user/Strata/strata-coder-iq1_m.log > ../pagoda-local2-logstart.txt
t0=$(date +%s)
cmd //c "C:\\Users\\user\\claude-local.bat -p --permission-mode acceptEdits --output-format stream-json --verbose" < ../pagoda-local-input.txt > ../pagoda-local2-stream.jsonl 2> ../pagoda-local2-stderr.txt
echo "local2 exit $? elapsed $(( $(date +%s) - t0 )) s" | tee ../pagoda-local2-time.txt
cd ..
for name in glm deepseek local2; do
  [ -f "pagoda-$name/pagoda.html" ] && .chk/Scripts/python.exe check_page.py "$name" "pagoda-$name/pagoda.html" Pond > /dev/null 2>&1
done
ls -la pagoda-glm pagoda-deepseek pagoda-local2 | cut -c1-100
