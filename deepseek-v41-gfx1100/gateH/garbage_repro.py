"""Replay T2's third turn (the one that turned to garbage) and check the answer.

The request is opencode's own body (system prompt + 7 tools, from runs/_probe/capture4.jsonl) with the T2 README as the
user message, then the two bash calls the model made and their real outputs, run in a fresh copy of the task.
Sampling is whatever the server defaults to, as for opencode (which sends no temperature).

usage: python garbage_repro.py LABEL [runs] [port]   -> garbage_repro.jsonl
Garbage check: CJK characters, HTML closing tags, or a broken DSML tool marker in the answer.
"""
import json, pathlib, re, shutil, subprocess, sys, time, urllib.request

LABEL = sys.argv[1]
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 3   # [--fresh] anywhere after
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 8091
CB = pathlib.Path(r"E:\strata-dsv41\pagoda\coding-bench")
HERE = pathlib.Path(__file__).parent
work = HERE / "live" / "work"
if work.exists():
    shutil.rmtree(work)
shutil.copytree(CB / "tasks" / "T2-multi-currency", work)
bash = r"C:\Program Files\Git\bin\bash.exe"
cmds = ["ls -la && find . -maxdepth 3 -type f | head -100",
        'cd inventory_service && for f in *.py; do echo "=== $f ==="; cat "$f"; done']
outs = [subprocess.run([bash, "-c", c], cwd=work, capture_output=True, text=True, encoding="utf-8").stdout for c in cmds]

body = json.loads((CB / "runs" / "_probe" / "capture4.jsonl").read_text(encoding="utf-8").splitlines()[0])["body"]
sysmsg = body["messages"][0]
sysmsg["content"] = (sysmsg["content"] if isinstance(sysmsg["content"], str) else sysmsg["content"][0]["text"]) \
    .replace(r"E:\strata-tests\coding-bench\runs\_probe", str(work)).replace("probe/probe", "strata/deepseek") \
    .replace("model named probe", "model named DeepSeek-V4.1-Flash uncensored 1.75bpw (Strata)")
readme = (work / "README.md").read_text(encoding="utf-8")
msgs = [sysmsg, {"role": "user", "content": readme}]
for i, (c, o) in enumerate(zip(cmds, outs)):
    cid = f"call_{i}"
    msgs.append({"role": "assistant", "content": "", "tool_calls": [{"id": cid, "type": "function", "function": {
        "name": "bash", "arguments": json.dumps({"command": c, "description": "look around"})}}]})
    msgs.append({"role": "tool", "tool_call_id": cid, "content": o})
body.update({"messages": msgs, "model": "deepseek", "max_tokens": 600, "stream": True,
             "stream_options": {"include_usage": True}, "reasoning_effort": "medium"})
BAD = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]|</(html|body|td|tr|table|form)>|<｜DSML｜\s*[^a-z]")

base_sys = msgs[0]["content"]
for r in range(RUNS):
    if "--fresh" in sys.argv:          # a unique first line, so the prefix cache cannot serve any of the prompt
        msgs[0]["content"] = f"[run {time.time():.0f}]\n" + base_sys
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0, text, calls, usage, err = time.time(), [], [], None, None
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:") or line == "data: [DONE]":
                    continue
                ev = json.loads(line[5:])
                err = ev.get("error") or err
                usage = ev.get("usage") or usage
                for ch in ev.get("choices") or []:
                    d = ch.get("delta") or {}
                    text.append((d.get("reasoning_content") or "") + (d.get("content") or ""))
                    for tc in d.get("tool_calls") or []:
                        calls.append(((tc.get("function") or {}).get("name") or "") + ((tc.get("function") or {}).get("arguments") or ""))
    except Exception as e:  # noqa: BLE001
        err = repr(e)[:300]
    t = "".join(text)
    res = {"label": LABEL, "run": r + 1, "time": time.strftime("%H:%M:%S"), "wall_s": round(time.time() - t0, 1),
           "usage": usage, "error": err, "garbage": bool(BAD.search(t)) or "non-finite" in json.dumps(err or ""),
           "tool_calls": "".join(calls)[:200], "text_tail": t[-300:]}
    with open(HERE / "garbage_repro.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")
    print(json.dumps({k: res[k] for k in ("label", "run", "wall_s", "garbage", "error", "tool_calls")}, ensure_ascii=False),
          flush=True)
