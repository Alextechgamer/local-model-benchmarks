"""Gate G long-prompt test: about 8K tokens of a source file plus a one-line question, then the engine log's own prompt timing.

usage: python long_prompt.py LABEL [port] [target_tokens]
"""
import json, re, sys, time

import measure

LABEL = sys.argv[1]
measure.PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8091
TARGET = int(sys.argv[3]) if len(sys.argv) > 3 else 8000
SRC = r"E:\strata-dsv41\Strata\strata_cli\launch\runner.py"
LOG = r"C:\Users\user\AppData\Local\Strata\launch\ist-das-1-75bpw-65-532k.engine.log"

code = open(SRC, encoding="utf-8").read()[: TARGET * 3]      # ~3 characters per token for Python source
prompt = f"[run {time.time():.0f}] Here is a Python source file:\n\n```python\n{code}\n```\n\nIn five bullet points, what does this file do?"
measure.MAX_TOKENS = 128
t0 = time.time()
r = measure.ask(prompt)
r.pop("text", None)
line = [l for l in open(LOG, encoding="utf-8", errors="replace") if "maya ds4 serve: prompt" in l]
m = re.search(r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms \(([\d.]+) tok/s\)", "".join(line[-3:]))
rows = [re.search(r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms \(([\d.]+) tok/s\)", l) for l in line[-3:]]
big = max((x for x in rows if x), key=lambda x: int(x.group(3)))
r.update({"label": LABEL, "engine_prompt_tokens": int(big.group(1)), "engine_prompt_read_ms": int(big.group(4)),
          "engine_prompt_tok_s": float(big.group(5)), "time": time.strftime("%Y-%m-%d %H:%M:%S")})
with open(r"E:\strata-dsv41\gateG\results.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps({**r, "kind": "long_prompt"}) + "\n")
print(json.dumps(r))
