"""Phase 4: speed and recall at growing context, against a running server (no agent loop).

usage: python ctx_run.py --model A|B --url URL --ctx-limit N --mem-csv CSV [--sizes 8k,32k] [--reps 3]
Each size runs `reps` times with a unique first line (nothing reused from a cache). Each request streams, asks for
at most 4,096 tokens (less when the context limit leaves less room) and caps thinking at 2,048 tokens on both
servers. Results append to results/context-runs.jsonl; the full streamed text is kept in logs/context/.
"""
import argparse, csv, json, math, pathlib, re, subprocess, sys, time

B = pathlib.Path(r"E:\strata-tests\coding-bench")
CTX = B / "context"


def grade(answer: str) -> dict:
    pat = r"(?im)^\s*\**\s*(Q[123])\s*\**\s*[:.]\s*\**\s*(.+)$"      # also **Q1:** and **Q1**: forms
    lines = {m.group(1): m.group(2).strip() for m in re.finditer(pat, answer)}
    res = {"q1": False, "q2": False, "q3": False, "q3_value_ok": False, "q3_code_ok": False, "parsed": lines}
    q1 = re.findall(r"-?\d+(?:\.\d+)?", lines.get("Q1", ""))
    res["q1"] = bool(q1) and q1[0] == "92"
    res["q2"] = "03-33X" in lines.get("Q2", "")
    q3 = lines.get("Q3", "")
    if "|" in q3:
        code, value = q3.rsplit("|", 1)
        nums = re.findall(r"-?\d+", value)
        res["q3_value_ok"] = bool(nums) and nums[0] == "3"
        code = code.strip().strip("`").strip()
        if not code.startswith("return"):
            code = "return " + code
        try:
            ns = {"math": math, "CRATE_CAPACITY": 18}
            exec("def crates_needed(units):\n    " + code, ns)
            res["q3_code_ok"] = [ns["crates_needed"](u) for u in (0, 1, 17, 18, 19, 36, 37, 40)] == [0, 1, 1, 1, 2, 2, 3, 3]
        except Exception as e:
            res["q3_code_error"] = f"{type(e).__name__}: {e}"[:200]
    res["q3"] = res["q3_value_ok"] and res["q3_code_ok"]
    res["correct"] = int(res["q1"]) + int(res["q2"]) + int(res["q3"])
    return res


def mem_peak(csv_path, t0, t1):
    ded = sh = ws = None
    if csv_path and pathlib.Path(csv_path).exists():
        with open(csv_path) as f:
            for r in csv.DictReader(f):
                t = float(r["unix"])
                if t0 - 1 <= t <= t1 + 1:
                    ded = max(ded or 0, float(r["gpu_dedicated_mb"])); sh = max(sh or 0, float(r["gpu_shared_mb"]))
                    ws = max(ws or 0, float(r["server_ws_mb"]))
    return ded, sh, ws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--ctx-limit", type=int, required=True)
    ap.add_argument("--mem-csv")
    ap.add_argument("--sizes", default="8k,32k,64k,96k,128k,200k,250k")
    ap.add_argument("--reps", type=int, default=3)
    a = ap.parse_args()
    meta = json.loads((CTX / "prompts.json").read_text(encoding="utf-8"))["prompts"]
    logdir = B / "logs" / "context"
    logdir.mkdir(parents=True, exist_ok=True)
    for size in a.sizes.split(","):
        est = meta[size]["tokens"]
        room = a.ctx_limit - est - 300
        if room < 512:
            row = {"model": a.model, "size": size, "rep": 0, "status": "does_not_fit", "prompt_tokens_est": est,
                   "ctx_limit": a.ctx_limit, "t_start": time.time(), "t_end": time.time()}
            with open(B / "results" / "context-runs.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            print(json.dumps(row), flush=True)
            continue
        max_tokens = min(4096, room)
        for rep in range(1, a.reps + 1):
            out = logdir / f"{a.model}-{size}-r{rep}.jsonl"
            extra = {"reasoning_budget_tokens": 2048, "thinking_budget_tokens": 2048}
            p = subprocess.run([sys.executable, str(B / "tools" / "bench_client.py"), "--url", a.url,
                                "--prompt-file", str(CTX / f"ctx-{size}.txt"), "--max-tokens", str(max_tokens),
                                "--nonce", "--tag", f"{a.model}-{size}-r{rep}", "--out", str(out),
                                "--timeout", "3600", "--extra", json.dumps(extra)], capture_output=True, text=True)
            try:
                r = json.loads(out.read_text(encoding="utf-8").strip().splitlines()[-1])
            except Exception:
                r = {"error": f"client failed: {p.stderr[-500:]}", "t_start": time.time(), "t_end": time.time()}
            g = grade(r.get("content") or "") if not r.get("error") else {"correct": 0}
            ded, sh, ws = mem_peak(a.mem_csv, r["t_start"], r["t_end"])
            row = {"model": a.model, "size": size, "rep": rep, "status": "error" if r.get("error") else "ok",
                   "error": r.get("error"), "prompt_tokens": r.get("prompt_tokens"), "prompt_tokens_est": est,
                   "completion_tokens": r.get("completion_tokens"), "finish_reason": r.get("finish_reason"),
                   "max_tokens": max_tokens, "ttft_s": r.get("ttft_s"), "prompt_tps": r.get("prompt_tps_client"),
                   "output_tps": r.get("output_tps_client"), "wall_s": r.get("wall_s"),
                   "server_timings": r.get("server_timings"), "peak_vram_dedicated_mb": ded,
                   "peak_vram_shared_mb": sh, "peak_server_ram_mb": ws, "answers_correct": g.get("correct", 0),
                   "grading": g, "t_start": r["t_start"], "t_end": r["t_end"]}
            with open(B / "results" / "context-runs.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            print(json.dumps({k: row[k] for k in ("model", "size", "rep", "status", "error", "prompt_tokens", "ttft_s",
                                                  "prompt_tps", "output_tps", "answers_correct")}), flush=True)


if __name__ == "__main__":
    main()
