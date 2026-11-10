"""Phase 1 timing for one server setting: 1 warmup + N timed runs of the fixed 16K prompt with a 512-token output.

usage: python tune_run.py --url URL --tag NAME --mem-csv power/SESSION-mem.csv [--runs 3] [--extra JSON]
Each repeat gets a unique first line (nonce) and cache_prompt=false, so no prompt prefix is reused.
Appends every run to results\tuning-runs.jsonl and prints the medians.
"""
import argparse, csv, json, statistics, subprocess, sys, pathlib, time

B = pathlib.Path(r"E:\strata-tests\coding-bench")
ap = argparse.ArgumentParser()
ap.add_argument("--url", required=True)
ap.add_argument("--tag", required=True)
ap.add_argument("--mem-csv")
ap.add_argument("--runs", type=int, default=3)
ap.add_argument("--max-tokens", type=int, default=512)
ap.add_argument("--extra", default="{}")
ap.add_argument("--prompt", default=str(B / "tools" / "prompt-16k.txt"))
a = ap.parse_args()

runs_file = B / "results" / "tuning-runs.jsonl"
streams = B / "logs" / "tuning"
streams.mkdir(parents=True, exist_ok=True)


def one(kind, i):
    out = streams / f"{a.tag}.jsonl"
    cmd = [sys.executable, str(B / "tools" / "bench_client.py"), "--url", a.url, "--prompt-file", a.prompt,
           "--max-tokens", str(a.max_tokens), "--nonce", "--tag", f"{a.tag}:{kind}{i}", "--out", str(out),
           "--extra", a.extra]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(out.read_text(encoding="utf-8").strip().splitlines()[-1])


def mem_peak(t0, t1):
    if not a.mem_csv or not pathlib.Path(a.mem_csv).exists():
        return None, None, None
    ded = sh = ram = None
    with open(a.mem_csv) as f:
        for r in csv.DictReader(f):
            t = float(r["unix"])
            if t0 - 1 <= t <= t1 + 1:
                d, s, w = float(r["gpu_dedicated_mb"]), float(r["gpu_shared_mb"]), float(r["server_ws_mb"])
                ded = max(ded or 0, d); sh = max(sh or 0, s); ram = max(ram or 0, w)
    return ded, sh, ram


warm = one("warmup", 0)
print("warmup", {k: warm[k] for k in ("error", "prompt_tokens", "completion_tokens", "ttft_s")}, flush=True)
rows = []
for i in range(1, a.runs + 1):
    r = one("run", i)
    ded, sh, ram = mem_peak(r["t_start"], r["t_end"])
    row = {"tag": a.tag, "run": i, "error": r["error"], "prompt_tokens": r["prompt_tokens"],
           "completion_tokens": r["completion_tokens"], "finish_reason": r["finish_reason"], "ttft_s": r["ttft_s"],
           "prompt_tps": r["prompt_tps_client"], "output_tps": r["output_tps_client"], "wall_s": r["wall_s"],
           "server_timings": r["server_timings"], "peak_vram_dedicated_mb": ded, "peak_vram_shared_mb": sh,
           "peak_server_ram_mb": ram, "t_start": r["t_start"], "t_end": r["t_end"], "extra": json.loads(a.extra)}
    rows.append(row)
    with open(runs_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    print(json.dumps({k: row[k] for k in ("run", "error", "prompt_tokens", "completion_tokens", "ttft_s", "prompt_tps",
                                          "output_tps", "peak_vram_dedicated_mb", "peak_vram_shared_mb")}), flush=True)


def med(k):
    v = [r[k] for r in rows if r[k] is not None]
    return statistics.median(v) if v else None


summary = {"tag": a.tag, "n": len(rows), "median_ttft_s": med("ttft_s"), "median_prompt_tps": med("prompt_tps"),
           "median_output_tps": med("output_tps"), "max_vram_shared_mb": max((r["peak_vram_shared_mb"] or 0) for r in rows),
           "max_vram_dedicated_mb": max((r["peak_vram_dedicated_mb"] or 0) for r in rows),
           "completion_tokens": [r["completion_tokens"] for r in rows], "errors": [r["error"] for r in rows if r["error"]]}
with open(B / "results" / "tuning-summary.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(summary) + "\n")
print("SUMMARY", json.dumps(summary))
