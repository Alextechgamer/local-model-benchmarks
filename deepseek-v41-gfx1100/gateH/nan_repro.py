"""Try to reproduce the engine's NaN fault: one long, fresh prompt (source code + a question), then up to 96 tokens.

usage: python nan_repro.py LABEL TARGET_TOKENS [port]
Writes one JSON line to nan_repro.jsonl: tokens read, whether the server stopped it with the NaN error, decode speed.
"""
import json, pathlib, sys, time, urllib.error, urllib.request

LABEL, TARGET = sys.argv[1], int(sys.argv[2])
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 8091
SRC = pathlib.Path(r"E:\strata-dsv41\Strata\serve")
code = ""
for f in sorted(SRC.glob("*.py")):
    code += f"\n# ---- {f.name}\n" + f.read_text(encoding="utf-8", errors="replace")
    if len(code) > TARGET * 3.4:
        break
code = code[: int(TARGET * 3.4)]
prompt = f"[run {time.time():.0f}] Here is some Python source:\n\n```python\n{code}\n```\n\nIn five bullet points, what does it do?"
body = {"model": "deepseek", "messages": [{"role": "user", "content": prompt}], "max_tokens": 96, "temperature": 0,
        "stream": True, "stream_options": {"include_usage": True}, "reasoning_effort": "medium"}
req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
t0 = time.time()
text, usage, err = [], None, None
try:
    with urllib.request.urlopen(req, timeout=3600) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line == "data: [DONE]":
                continue
            ev = json.loads(line[5:])
            if ev.get("error"):
                err = ev["error"]
            usage = ev.get("usage") or usage
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                text.append((d.get("reasoning_content") or "") + (d.get("content") or ""))
except urllib.error.HTTPError as e:
    err = e.read().decode("utf-8", "replace")[:500]
except Exception as e:  # noqa: BLE001
    err = repr(e)[:500]
res = {"label": LABEL, "target": TARGET, "time": time.strftime("%Y-%m-%d %H:%M:%S"), "wall_s": round(time.time() - t0, 1),
       "usage": usage, "error": err, "nan": "non-finite" in json.dumps(err) if err else False,
       "text_head": "".join(text)[:200]}
with open(pathlib.Path(__file__).with_name("nan_repro.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps(res) + "\n")
print(json.dumps(res))
