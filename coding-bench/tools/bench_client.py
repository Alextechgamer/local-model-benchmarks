"""One streaming /v1/chat/completions request, timed on the client. Prints one JSON line.

usage: python bench_client.py --url http://127.0.0.1:8080/v1 --prompt-file p.txt --max-tokens 512 [--nonce] [--out f.jsonl]
  --nonce          prepend a unique line so no cached prefix can be reused between repeats
  --question TEXT  appended after the prompt file (used by the context test)
  --no-think       ask the server not to think (chat_template_kwargs enable_thinking=false)
  --extra JSON     extra request fields merged into the body

Times: ttft_s = first streamed token of any kind (reasoning or content); output tok/s = (completion tokens - 1)
/ (end - first token). Server-reported timings (llama.cpp `timings`, Strata fields) are saved as given.
"""
import argparse, json, time, uuid, urllib.request, sys

ap = argparse.ArgumentParser()
ap.add_argument("--url", required=True)
ap.add_argument("--model", default="local")
ap.add_argument("--prompt-file", required=True)
ap.add_argument("--question", default="")
ap.add_argument("--max-tokens", type=int, default=512)
ap.add_argument("--nonce", action="store_true")
ap.add_argument("--no-think", action="store_true")
ap.add_argument("--extra", default="{}")
ap.add_argument("--tag", default="")
ap.add_argument("--out")
ap.add_argument("--timeout", type=float, default=3600)
a = ap.parse_args()

text = open(a.prompt_file, encoding="utf-8").read()
if a.nonce:
    text = f"[request id {uuid.uuid4().hex}]\n" + text
if a.question:
    text = text + "\n\n" + a.question
body = {"model": a.model, "messages": [{"role": "user", "content": text}], "max_tokens": a.max_tokens,
        "stream": True, "stream_options": {"include_usage": True}, "cache_prompt": False,
        "reasoning_effort": "medium"}
if a.no_think:
    body["chat_template_kwargs"] = {"enable_thinking": False}
body.update(json.loads(a.extra))

req = urllib.request.Request(a.url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json", "Authorization": "Bearer none"})
t0 = time.time(); t_first = None; content = []; reasoning = []; usage = None; timings = None; last = None
finish = None; n_chunks = 0; err = None
try:
    with urllib.request.urlopen(req, timeout=a.timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            ev = json.loads(data)
            last = ev
            if ev.get("usage"):
                usage = ev["usage"]
            if ev.get("timings"):
                timings = ev["timings"]
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                piece_c = d.get("content") or ""
                piece_r = d.get("reasoning_content") or d.get("reasoning") or ""
                if (piece_c or piece_r) and t_first is None:
                    t_first = time.time()
                if piece_c or piece_r:
                    n_chunks += 1
                content.append(piece_c); reasoning.append(piece_r)
                if ch.get("finish_reason"):
                    finish = ch["finish_reason"]
except Exception as e:  # record, don't crash the batch
    err = f"{type(e).__name__}: {e}"
t_end = time.time()

ct = (usage or {}).get("completion_tokens")
pt = (usage or {}).get("prompt_tokens")
res = {
    "tag": a.tag, "t_start": t0, "t_end": t_end, "error": err,
    "prompt_tokens": pt, "completion_tokens": ct, "finish_reason": finish,
    "ttft_s": (t_first - t0) if t_first else None,
    "prompt_tps_client": (pt / (t_first - t0)) if (pt and t_first) else None,
    "output_tps_client": ((ct - 1) / (t_end - t_first)) if (ct and t_first and t_end > t_first and ct > 1) else None,
    "wall_s": t_end - t0,
    "server_timings": timings,
    "usage": usage,
    "content": "".join(content),
    "reasoning_chars": len("".join(reasoning)),
    "reasoning": "".join(reasoning),
}
line = json.dumps(res)
if a.out:
    with open(a.out, "a", encoding="utf-8") as f:
        f.write(line + "\n")
summary = {k: res[k] for k in ("tag", "error", "prompt_tokens", "completion_tokens", "finish_reason", "ttft_s",
                               "prompt_tps_client", "output_tps_client", "wall_s")}
print(json.dumps(summary))
