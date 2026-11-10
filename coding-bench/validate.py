"""Validate the test itself through score.py: hidden tests fail on the starting code where they should and pass on
the reference solutions, and the T6 reference tests kill every mutant.

usage: python validate.py   -> prints a report, writes VALIDATION.txt and results/validation.json
Expectations:
  starting code:  every test_task_* fails, every test_keep_* passes (T6: no tests yet -> score 0)
  reference:      every hidden test passes and every visible test passes (T6: 10 of 10 mutants killed)
"""
import json, pathlib, subprocess, sys, datetime

B = pathlib.Path(__file__).resolve().parent
from score import TASK_DIRS  # noqa: E402

stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
rows, ok_all = [], True
for task, folder in TASK_DIRS.items():
    for kind, d in (("start", B / "tasks" / folder), ("reference", B / "reference" / task)):
        label = f"validate-{stamp}-{task}-{kind}"
        out = B / "scoring" / f"{label}.json"
        subprocess.run([sys.executable, str(B / "score.py"), "--task", task, "--dir", str(d), "--out", str(out),
                        "--label", label], check=True, capture_output=True, text=True)
        r = json.loads(out.read_text(encoding="utf-8"))
        problems = []
        if task == "T6":
            m = r["mutation"]
            if kind == "start" and r["score"] != 0:
                problems.append("start should score 0")
            if kind == "reference":
                if m.get("original", {}).get("failed", 1) != 0:
                    problems.append("reference tests fail on the untouched package")
                survivors = [k for k, v in m["mutants"].items() if not v["killed"]]
                if survivors:
                    problems.append(f"mutants not killed by the reference tests: {survivors}")
            detail = f"mutants killed {m['killed']}/{m['mutant_total']}" + (f" ({m['note']})" if m.get("note") else "")
        else:
            h = r["hidden"]
            tests = h["failures"]
            if kind == "start":
                if h["task_passed"] != 0:
                    problems.append(f"{h['task_passed']} test_task_* pass on the starting code")
                if h["keep_passed"] != h["keep_total"]:
                    problems.append(f"test_keep_* failing on start: {[t for t in tests if t.startswith('test_keep_')]}")
            else:
                if h["passed"] != h["total"]:
                    problems.append(f"hidden failing on the reference: {tests}")
            detail = (f"hidden {h['passed']}/{h['total']} (task {h['task_passed']}/{h['task_total']}, "
                      f"keep {h['keep_passed']}/{h['keep_total']})")
        if kind == "reference" and r["visible"]["failed"]:
            problems.append(f"{r['visible']['failed']} visible tests fail on the reference")
        detail += f"; visible {r['visible']['passed']}/{r['visible']['total']}"
        ok = not problems
        ok_all &= ok
        rows.append({"task": task, "kind": kind, "ok": ok, "detail": detail, "problems": problems, "label": label})
        print(f"{task} {kind:9s} {'OK  ' if ok else 'FAIL'} {detail}" + (f"  <- {problems}" if problems else ""), flush=True)
report = "\n".join(f"{r['task']} {r['kind']:9s} {'OK  ' if r['ok'] else 'FAIL'} {r['detail']}"
                   + (f"  <- {r['problems']}" if r["problems"] else "") for r in rows)
(B / "VALIDATION.txt").write_text(f"validate.py run {stamp}: {'ALL OK' if ok_all else 'PROBLEMS'}\n{report}\n",
                                  encoding="utf-8")
(B / "results").mkdir(exist_ok=True)
(B / "results" / "validation.json").write_text(json.dumps({"run": stamp, "ok": ok_all, "rows": rows}, indent=1),
                                                encoding="utf-8")
print("ALL OK" if ok_all else "PROBLEMS")
sys.exit(0 if ok_all else 1)
