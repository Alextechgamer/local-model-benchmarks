"""0.1.45 vs 0.1.58, same config: the same requests as the earlier runs, against the running Qwen server (port 8080).

short: tools/prompt-900.txt (948 tokens), 512 out       (0.1.45 row: tuning A-v045-r1792-short)
16k:   tools/prompt-16k.txt, 512 out                    (0.1.45 row: tuning A-v045-final)
8k:    context/ctx-8k.txt, up to 4096 out, thinking capped at 2048 (0.1.45 rows: context-runs A 8k)
Each: 1 warm-up (discarded) + 3 timed, every request with a unique first line (bench_client --nonce). Medians.
"""
import json, pathlib, statistics, subprocess, sys

T = pathlib.Path(r"E:\strata-tests\coding-bench")
BC = pathlib.Path(r"E:\strata-dsv41\pagoda\coding-bench\tools\bench_client.py")
OUT = pathlib.Path(__file__).parent / "qwen-058-runs.jsonl"
CASES = [("short", T / "tools" / "prompt-900.txt", 512, {}),
         ("16k", T / "tools" / "prompt-16k.txt", 512, {}),
         ("8k", T / "context" / "ctx-8k.txt", 4096, {"reasoning_budget_tokens": 2048, "thinking_budget_tokens": 2048})]
summary = {}
for name, prompt, mx, extra in CASES:
    rows = []
    for i in range(4):
        tag = f"q058-{name}-{'warm' if i == 0 else f'r{i}'}"
        subprocess.run([sys.executable, str(BC), "--url", "http://127.0.0.1:8080/v1", "--prompt-file", str(prompt),
                        "--max-tokens", str(mx), "--nonce", "--tag", tag, "--out", str(OUT), "--timeout", "3600",
                        "--extra", json.dumps(extra)], check=True, capture_output=True, text=True)
        r = json.loads(OUT.read_text(encoding="utf-8").strip().splitlines()[-1])
        if i:
            rows.append(r)
    pt = [r.get("prompt_tps_client") for r in rows]
    ot = [r.get("output_tps_client") for r in rows]
    summary[name] = {"prompt_tokens": [r.get("prompt_tokens") for r in rows],
                     "completion_tokens": [r.get("completion_tokens") for r in rows],
                     "errors": [r.get("error") for r in rows if r.get("error")],
                     "cache_n": [(r.get("server_timings") or {}).get("cache_n") for r in rows],
                     "prompt_tps": pt, "output_tps": ot,
                     "median_prompt_tps": statistics.median(pt), "median_output_tps": statistics.median(ot),
                     "median_ttft_s": statistics.median(r.get("ttft_s") for r in rows)}
    print(name, json.dumps(summary[name]), flush=True)
(pathlib.Path(__file__).parent / "qwen-058-summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
