"""Collect Phase 1 results into results/tuning.json: per arm the medians, memory, smoke score and the server command.

usage: python make_tuning_json.py
"""
import json, pathlib, collections

B = pathlib.Path(r"E:\strata-tests\coding-bench")
R = B / "results"


def jl(p):
    p = R / p
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


runs = collections.defaultdict(list)
for r in jl("tuning-runs.jsonl"):
    runs[r["tag"]].append(r)
summ = {}
for s in jl("tuning-summary.jsonl"):
    summ[s["tag"]] = s                       # last summary per tag wins (an arm rerun replaces the earlier one)
smoke = collections.defaultdict(list)
for s in jl("smoke.jsonl"):
    smoke[s["tag"]].append(s)
cmds = {}
for e in jl("arm-events.jsonl"):
    if e.get("event") == "start":
        cmds[e["tag"]] = {"cmd": e["cmd"], "env": e.get("env", [])}
    if e.get("event") == "loaded":
        cmds.setdefault(e["tag"], {})["load_s"] = e["load_s"]
    if e.get("event") == "skipped_low_ram":
        cmds.setdefault(e["tag"], {})["skipped_low_ram"] = e

arms = []
for tag in sorted(set(summ) | set(cmds)):
    s = summ.get(tag, {})
    sm = smoke.get(tag, [])
    by_ver = collections.defaultdict(list)
    for x in sm:
        by_ver[x.get("smoke_version", 1)].append(x)
    smoke_scores = {f"v{v}": {k: sum(1 for x in xs if x.get(k)) for k in ("tool_call", "tool_typed", "tool_result", "code")}
                    | {"reps": len(xs)} for v, xs in sorted(by_ver.items())}
    cfg = None
    c = cmds.get(tag, {})
    if "--config" in (c.get("cmd") or []):
        p = pathlib.Path(c["cmd"][c["cmd"].index("--config") + 1])
        cfg = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    arms.append({
        "tag": tag, "model": tag.split("-")[0],
        "median_ttft_s": s.get("median_ttft_s"), "median_prompt_tps": s.get("median_prompt_tps"),
        "median_output_tps": s.get("median_output_tps"), "max_vram_dedicated_mb": s.get("max_vram_dedicated_mb"),
        "max_vram_shared_mb": s.get("max_vram_shared_mb"), "completion_tokens": s.get("completion_tokens"),
        "errors": s.get("errors"), "runs": runs.get(tag, []), "smoke": smoke_scores, "load_s": c.get("load_s"),
        "skipped": c.get("skipped_low_ram"), "server_cmd": c.get("cmd"), "server_env": c.get("env"),
        "strata_config": cfg,
    })
fit = jl("fit-probe.jsonl")
out = {"method": "16,050-token prompt (tools/prompt-16k.txt, Strata serve/*.py source) + 512 output tokens; "
                  "1 warmup + 3 timed runs per arm, unique first line + cache_prompt=false; medians. "
                  "TTFT = first streamed token; prompt tok/s = prompt tokens / TTFT; output tok/s = "
                  "(tokens-1)/(end-first token). Smoke = tools/smoke.py, 3 reps.",
       "arms": arms, "fit_probe": fit}
A = {a["tag"]: a for a in arms}


def m(t):
    a = A[t]
    return {"tag": t, "ttft_s": round(a["median_ttft_s"], 2), "prompt_tps": round(a["median_prompt_tps"]),
            "output_tps": round(a["median_output_tps"], 1)}


out["locked"] = {
    "model_a": {"config": "configs/model-a.json", "start": "configs/model-a-start.ps1", "final": m("A-v045-final"),
                "old_default": m("A-v039-base"),
                "old_default_note": "engine 0.1.39 with the user's config args plus the Phase 1 base changes "
                                    "(--vram-reserve-mib 1024, Qwen thinking sampling, 8192 thinking budget)",
                "short_prompt_900": {"with_cpu_share": m("A-v045-r1792-cpushare-short"),
                                     "without_cpu_share": m("A-v045-r1792-short")},
                "long_prompt_120k": "120,126 prompt tokens: TTFT 83.4 s, 1,441 prompt tok/s, 42.7 output tok/s, no "
                                    "crash (logs/tuning/A-v045-final-120k.jsonl)"},
    "model_b": {"config": "configs/model-b.json", "start": "configs/model-b-start.ps1", "final": m("B-mtp-n3-prob"),
                "old_default": m("B-backend-vk10752"),
                "old_default_note": "winget b10752 Vulkan, greedy MTP n=3, same 98,304 context; the old run.ps1 "
                                    "default of 163,840 context spilled VRAM today (prompt ~45 tok/s, aborted, "
                                    "logs/tuning/B-backend-vk10752-aborted-163840.jsonl)",
                "smoke_v2": "B-final: 3/3 on all four checks"},
    "noise": "output tok/s varies about +-8% between arms with identical settings (sampling at temperature 1.0 "
             "changes the draft acceptance); differences below that are not counted as gains",
}
(R / "tuning.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
for a in arms:
    print(f"{a['tag']:38s} ttft={a['median_ttft_s'] or 0:6.1f} pp={a['median_prompt_tps'] or 0:7.0f} "
          f"out={a['median_output_tps'] or 0:5.1f} ded={a['max_vram_dedicated_mb'] or 0:6.0f} "
          f"sh={a['max_vram_shared_mb'] or 0:6.0f} smoke={json.dumps(a['smoke'])}")
