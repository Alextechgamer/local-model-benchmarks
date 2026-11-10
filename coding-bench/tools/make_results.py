"""Phase 5: build results/coding.json, results/context.json, results/power.json and the charts from the raw logs.

usage: python make_results.py
"""
import collections, json, pathlib, statistics, sys

B = pathlib.Path(r"E:\strata-tests\coding-bench")
sys.path.insert(0, str(B / "tools"))
import energy  # noqa: E402

R = B / "results"
PRICE_PER_KWH = 0.104
MODEL_NAMES = {"A": "Qwen3.8-Flash-Next Coder IQ1_M on Strata 0.1.45 (HIP)",
               "B": "Qwen3.8-27B IQ4_XS on llama.cpp b11748 (Vulkan)"}
TASK_NAMES = {"T1": "fix 3 planted bugs", "T2": "multi-currency feature", "T3": "refactor pricing.py",
              "T4": "implement from docstring", "T5": "bug from a user report", "T6": "write tests (mutation)"}


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def coding():
    runs = []
    review_path = R / "run-review.json"
    reviews = json.loads(review_path.read_text(encoding="utf-8"))["reviews"] if review_path.exists() else {}
    for rj in sorted((B / "runs").glob("[AB]/T*/r*/run.json")):
        run = json.loads(rj.read_text(encoding="utf-8"))
        sp = rj.parent / "score.json"
        score = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else None
        e = energy.window(run["t0"], run["t1"])
        row = {"model": run["model"], "task": run["task"], "rep": run["rep"], "wall_s": run["wall_s"],
               "steps": run["steps"], "tool_calls": run["tool_calls"], "killed": run["killed"],
               "exit_code": run["exit_code"], "tokens": run["tokens"], "ran_visible_tests": run["ran_visible_tests"],
               "pytest_calls": run["pytest_calls"], "peeked_outside": run["peeked_outside"],
               "valid": not run["peeked_outside"], "errors": run["errors"],
               "score": score["score"] if score else None,
               "hidden": score.get("hidden") and {k: score["hidden"][k] for k in (
                   "total", "passed", "task_total", "task_passed", "keep_total", "keep_passed", "failures")},
               "mutation": score.get("mutation") and {k: score["mutation"].get(k) for k in ("killed", "mutant_total",
                                                                                            "note")},
               "visible": score and score["visible"], "package_changed": score and score["package_changed"],
               "tests_changed": score and score["tests_changed"],
               "energy": e, "cost_usd": (e["total_wh"] / 1000 * PRICE_PER_KWH) if e.get("total_wh") else None,
               "t0": run["t0"], "t1": run["t1"]}
        rv = reviews.get(f"{run['model']}-{run['task']}-r{run['rep']}")
        if rv:
            row["valid"], row["review"] = rv["valid"], rv["finding"]
        runs.append(row)
    summary = {}
    for (m, t), rows in sorted(collections.defaultdict(list, {}).items()):
        pass
    groups = collections.defaultdict(list)
    for r in runs:
        groups[(r["model"], r["task"])].append(r)
    for (m, t), rows in sorted(groups.items()):
        summary.setdefault(m, {})[t] = {
            "runs": len(rows), "mean_score": sum(r["score"] or 0 for r in rows) / len(rows),
            "solved": sum(1 for r in rows if r["score"] == 1.0),
            "median_wall_s": med([r["wall_s"] for r in rows]), "median_steps": med([r["steps"] for r in rows]),
            "median_wh": med([r["energy"].get("total_wh") for r in rows]),
            "median_cost_usd": med([r["cost_usd"] for r in rows]),
            "mean_output_tokens": sum(r["tokens"]["output"] for r in rows) / len(rows),
            "ran_tests": sum(1 for r in rows if r["ran_visible_tests"]),
            "invalid": sum(1 for r in rows if not r["valid"]), "killed": sum(1 for r in rows if r["killed"])}
    for m in summary:
        rows = [r for r in runs if r["model"] == m]
        summary[m]["_all"] = {"runs": len(rows), "mean_score": sum(r["score"] or 0 for r in rows) / len(rows),
                              "solved": sum(1 for r in rows if r["score"] == 1.0),
                              "total_wall_s": sum(r["wall_s"] for r in rows),
                              "total_wh": sum(r["energy"].get("total_wh") or 0 for r in rows),
                              "total_cost_usd": sum(r["cost_usd"] or 0 for r in rows)}
    out = {"method": "opencode 1.19.3 (--pure, README on stdin, bench opencode.json: 7 core tools, no MCP/skills/"
                     "subagents, reasoning_effort medium), 45 min / 150 steps per run, 2 reps per task. Score = hidden "
                     "tests passed / total (T6: mutants killed / 10). Energy = GPU board power + CPU package power "
                     "over the run's wall time; cost at $0.104/kWh.",
           "models": MODEL_NAMES, "tasks": TASK_NAMES, "summary": summary, "runs": runs}
    (R / "coding.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def context():
    rows = [json.loads(l) for l in (R / "context-runs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()] \
        if (R / "context-runs.jsonl").exists() else []
    for r in rows:
        r["energy"] = energy.window(r["t_start"], r["t_end"]) if r.get("status") == "ok" else None
    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r["model"], r["size"])].append(r)
    meta = json.loads((B / "context" / "prompts.json").read_text(encoding="utf-8"))["prompts"]
    summary = {}
    for (m, s), rs in groups.items():
        ok = [r for r in rs if r["status"] == "ok"]
        summary.setdefault(m, {})[s] = {
            "status": "ok" if ok else rs[0]["status"], "runs": len(ok),
            "prompt_tokens": med([r.get("prompt_tokens") for r in ok]), "target_tokens": meta[s]["target_tokens"],
            "median_ttft_s": med([r["ttft_s"] for r in ok]), "median_prompt_tps": med([r["prompt_tps"] for r in ok]),
            "median_output_tps": med([r["output_tps"] for r in ok]),
            "peak_vram_dedicated_mb": max([r["peak_vram_dedicated_mb"] or 0 for r in ok], default=None),
            "peak_vram_shared_mb": max([r["peak_vram_shared_mb"] or 0 for r in ok], default=None),
            "peak_server_ram_mb": max([r["peak_server_ram_mb"] or 0 for r in ok], default=None),
            "answers_correct": [r["answers_correct"] for r in ok],
            "median_wh": med([(r["energy"] or {}).get("total_wh") for r in ok]),
            "errors": [r.get("error") for r in rs if r["status"] != "ok"]}
    out = {"method": "One streaming /v1/chat/completions request per repeat (3 per size), unique first line, "
                     "max_tokens min(4096, room left), thinking capped at 2048 tokens. Facts at ~10/50/90% depth; "
                     "3 questions graded automatically (Q3's fix line is executed).",
           "prompts": meta, "summary": summary, "runs": rows}
    (R / "context.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def power(cod, ctx):
    sess = {}
    for s in energy.sessions():
        g = energy.gpu_series(s)
        if not g:
            continue
        t0, t1 = g[0][0], g[-1][0]
        w = energy.window(t0, t1, s)
        sess[s] = {"start": t0, "end": t1, "minutes": round((t1 - t0) / 60, 1), **w}
    phases = collections.defaultdict(lambda: {"gpu_wh": 0, "cpu_wh": 0, "total_wh": 0, "minutes": 0})
    for s, v in sess.items():
        ph = "phase1" if s.startswith("p1-") else "phase3" if s.startswith("p3-") else "phase4" if s.startswith("p4-") \
            else "other"
        for k in ("gpu_wh", "cpu_wh", "total_wh", "minutes"):
            phases[ph][k] += v.get(k) or 0
    out = {"method": energy.__doc__, "price_per_kwh_usd": PRICE_PER_KWH, "sessions": sess, "phases": phases,
           "coding_runs": [{k: r[k] for k in ("model", "task", "rep", "wall_s", "energy", "cost_usd")} for r in cod["runs"]],
           "context_runs": [{k: r.get(k) for k in ("model", "size", "rep", "energy")} for r in ctx["runs"]
                            if r.get("status") == "ok"]}
    (R / "power.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def charts(ctx):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    colors = {"A": "#2a6fdb", "B": "#e07b28"}
    for m, sizes in ctx["summary"].items():
        pts = sorted(((v["prompt_tokens"] or v["target_tokens"], v) for v in sizes.values() if v["status"] == "ok"),
                     key=lambda x: x[0])
        if not pts:
            continue
        xs = [p[0] / 1000 for p in pts]
        axes[0].plot(xs, [p[1]["median_prompt_tps"] for p in pts], "o-", color=colors[m], label=f"Model {m}")
        axes[1].plot(xs, [p[1]["median_ttft_s"] for p in pts], "o-", color=colors[m], label=f"Model {m}")
    axes[0].set(title="Prompt reading speed vs context size", xlabel="prompt size (thousand tokens)",
                ylabel="prompt tokens per second")
    axes[1].set(title="Time to first token vs context size", xlabel="prompt size (thousand tokens)",
                ylabel="seconds")
    for ax in axes:
        ax.grid(alpha=0.3); ax.legend()
    fig.tight_layout()
    fig.savefig(R / "context-chart.png", dpi=130)


if __name__ == "__main__":
    c = coding()
    x = context()
    power(c, x)
    if x["summary"]:
        charts(x)
    for m, tasks in c["summary"].items():
        print(m, json.dumps(tasks.get("_all")))
