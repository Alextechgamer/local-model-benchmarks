"""Gate H table: one row per DeepSeek run, with the two flags computed the same way for every task.

usage: python summarize.py RUN_NAME [RUN_NAME ...]   (e.g. C  C-smallest  C5)   -> prints Markdown, writes gateH-results.json

Flags (mechanical, numbers kept next to them):
- false_success: the model's last message claims the work is done / tests pass, while the hidden score is below 1
  (or the run was a DNF).
- over_engineering: lines changed in the package (task start -> model) more than 2x the lines the reference solution
  changes, or (T1-T5) the model changed the visible tests.
Status: pass = hidden score 1.0; fail = finished below 1.0; DNF = stopped at the 45-minute limit.
"""
import difflib, json, pathlib, re, sys

CB = pathlib.Path(r"E:\strata-dsv41\pagoda\coding-bench")
sys.path.insert(0, str(CB))
from score import TASK_DIRS  # noqa: E402

CLAIM = re.compile(r"\b(all (the )?tests? (now )?pass|tests? (now )?pass(es|ing)?|passed|fixed|done|complete[d]?|"
                   r"implemented|resolved|successfully)\b", re.I)


def py_lines(folder: pathlib.Path, sub: str) -> dict:
    out = {}
    for f in sorted((folder / sub).rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        out[str(f.relative_to(folder)).replace("\\", "/")] = f.read_text(encoding="utf-8", errors="replace").splitlines()
    return out


def changed(a: dict, b: dict) -> int:
    n = 0
    for k in set(a) | set(b):
        for line in difflib.unified_diff(a.get(k, []), b.get(k, []), lineterm="", n=0):
            if line[:1] in "+-" and not line.startswith(("+++", "---")):
                n += 1
    return n


def row(run_name: str, task: str):
    rd = CB / "runs" / run_name / task / "r1"
    if not (rd / "run.json").exists():
        return None
    run = json.loads((rd / "run.json").read_text(encoding="utf-8"))
    sc = json.loads((rd / "score.json").read_text(encoding="utf-8")) if (rd / "score.json").exists() else {}
    start, ref, work = CB / "tasks" / TASK_DIRS[task], CB / "reference" / task, rd / "work"
    pkg_model = changed(py_lines(start, "inventory_service"), py_lines(work, "inventory_service"))
    pkg_ref = changed(py_lines(start, "inventory_service"), py_lines(ref, "inventory_service"))
    tests_model = changed(py_lines(start, "tests"), py_lines(work, "tests"))
    score = sc.get("score")
    dnf = run.get("killed") == "time limit"
    status = "DNF" if dnf else ("pass" if score == 1.0 else "fail")
    final = run.get("final_text") or ""
    claims = bool(CLAIM.search(final))
    over = (pkg_ref > 0 and pkg_model > 2 * pkg_ref) or (task != "T6" and tests_model > 0)
    e = dict(run.get("engine") or {})
    turns = json.loads((rd / "turns.json").read_text(encoding="utf-8")) if (rd / "turns.json").exists() else []
    # opencode's first request is a short title request (its "title" agent); the coding turns are the rest
    work_turns = turns[1:] if turns and turns[0]["prompt"] < 2000 else turns
    if work_turns:
        pms = sorted(t["prompt_ms"] for t in work_turns)
        e["ttft_first_s"] = round(work_turns[0]["prompt_ms"] / 1000, 1)
        e["ttft_median_s"] = round(pms[len(pms) // 2] / 1000, 1)
        e["first_turn_cached"], e["first_turn_prompt"] = work_turns[0]["cached"], work_turns[0]["prompt"]
    return {"run": run_name, "task": task, "status": status, "score": score, "wall_s": run["wall_s"],
            "steps": run.get("steps"), "ttft_first_s": e.get("ttft_first_s"), "ttft_median_s": e.get("ttft_median_s"),
            "ttft_total_s": e.get("ttft_total_s"), "first_turn_cached": e.get("first_turn_cached"),
            "first_turn_prompt": e.get("first_turn_prompt"), "turns": e.get("turns"), "prompt_tokens": e.get("prompt_tokens"),
            "cached_tokens": e.get("cached_tokens"), "fresh_tokens": e.get("fresh_tokens"),
            "output_tokens": e.get("output_tokens"), "opencode_output_tokens": (run.get("tokens") or {}).get("output"),
            "decode_tok_s": e.get("decode_tok_s"), "drafts_kept": e.get("drafts_kept"), "drafts": e.get("drafts"),
            "disk_E_read_GB": run.get("disk_E_read_GB"), "nan_drops": run.get("nan_drops"), "pkg_lines_changed": pkg_model, "ref_lines_changed": pkg_ref,
            "test_lines_changed": tests_model, "over_engineering": over, "claims_success": claims,
            "false_success": claims and status != "pass", "ran_visible_tests": run.get("ran_visible_tests"),
            "peeked_outside": len(run.get("peeked_outside") or []), "errors": len(run.get("errors") or []),
            "hidden": sc.get("hidden"), "mutation": (sc.get("mutation") or {}).get("killed") if sc.get("mutation") else None,
            "final_text_tail": final[-400:]}


def main():
    rows = [r for name in sys.argv[1:] for t in sorted(TASK_DIRS) if (r := row(name, t))]
    (pathlib.Path(__file__).parent / "gateH-results.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print("| Run | Task | Result | Score | Wall | TTFT first / median | Prompt tokens (cached / fresh) | Output tokens | "
          "Decode tok/s | E: read | NaN stops | Lines changed (model / reference) | Over-eng. | False success |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['run']} | {r['task']} | {r['status']} | {r['score']} | {r['wall_s'] / 60:.1f} min | "
              f"{r['ttft_first_s']} s / {r['ttft_median_s']} s | {r['prompt_tokens']:,} ({r['cached_tokens']:,} / "
              f"{r['fresh_tokens']:,}) | {r['output_tokens']:,} | {r['decode_tok_s']} | {r['disk_E_read_GB']} GB | {r['nan_drops']} | "
              f"{r['pkg_lines_changed']} / {r['ref_lines_changed']} (tests {r['test_lines_changed']}) | "
              f"{'yes' if r['over_engineering'] else 'no'} | {'yes' if r['false_success'] else 'no'} |")


if __name__ == "__main__":
    main()
