"""Score one finished task: copy the model's result, run the hidden tests under a time limit, write pass counts.

usage: python score.py --task T1 --dir <the model's work folder> --out <result.json> [--timeout 300] [--label NAME]

- The model's folder is copied to scoring/<label>/model and never run in place.
- Hidden tests (hidden/common + hidden/<task>) are copied to scoring/<label>/hidden and run from there with an empty
  pytest config, --noconftest and PYTHONPATH pointing only at the model's copy, so files the model wrote (conftest.py,
  pytest.ini, pyproject.toml) cannot change how they run. test_task_* are the task's own tests; test_keep_* are
  regression tests.
- The visible tests are run in the model's copy too, with its own config, and reported separately.
- T6 is scored by mutation testing: the model's tests/test_reports.py (with its tests/conftest.py) runs against the
  untouched package and then against each mutant in reference/mutants/T6. Score = mutants killed / 10, or 0 if the
  tests do not pass on the untouched package.
"""
import argparse, datetime, hashlib, json, os, pathlib, shutil, subprocess, sys, time
import xml.etree.ElementTree as ET

B = pathlib.Path(__file__).resolve().parent
PY = sys.executable
TASK_DIRS = {"T1": "T1-fix-bugs", "T2": "T2-multi-currency", "T3": "T3-refactor-pricing",
             "T4": "T4-implement-from-docstring", "T5": "T5-bug-report", "T6": "T6-write-tests"}


def run_pytest(args, cwd, env_pythonpath, junit, timeout):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS")}
    env["PYTHONPATH"] = env_pythonpath
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    t0 = time.time()
    try:
        p = subprocess.run([PY, "-m", "pytest", *args, "-p", "no:cacheprovider", "-q", f"--junitxml={junit}"],
                           cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        out, rc, timed_out = p.stdout[-6000:] + p.stderr[-3000:], p.returncode, False
    except subprocess.TimeoutExpired as e:
        out = ((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""))[-6000:]
        rc, timed_out = None, True
    return parse_junit(junit) | {"returncode": rc, "timed_out": timed_out, "seconds": round(time.time() - t0, 1),
                                  "output_tail": out[-4000:]}


def parse_junit(path):
    res = {"tests": [], "total": 0, "passed": 0, "failed": 0}
    if not os.path.exists(path):
        return res
    for tc in ET.parse(path).getroot().iter("testcase"):
        name = tc.get("name", "")
        status = "passed"
        for child in tc:
            if child.tag in ("failure", "error"):
                status = "failed"
            elif child.tag == "skipped":
                status = "skipped"
        res["tests"].append({"name": name, "file": tc.get("classname", ""), "status": status})
    res["total"] = len(res["tests"])
    res["passed"] = sum(1 for t in res["tests"] if t["status"] == "passed")
    res["failed"] = res["total"] - res["passed"]
    return res


def tree_hash(folder: pathlib.Path) -> str:
    h = hashlib.sha256()
    for p in sorted(folder.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        h.update(str(p.relative_to(folder)).encode()); h.update(p.read_bytes())
    return h.hexdigest()


def copy_model(src: pathlib.Path, dst: pathlib.Path):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".git",
                                                            "node_modules", ".opencode"))


def score_hidden(task, model_dir, work, timeout):
    hid = work / "hidden"
    hid.mkdir()
    for d in (B / "hidden" / "common", B / "hidden" / task):
        for f in d.iterdir():
            if f.is_file():
                shutil.copy(f, hid / f.name)
    ini = work / "empty.ini"
    ini.write_text("[pytest]\n", encoding="utf-8")
    r = run_pytest([str(hid), "-c", str(ini), "--rootdir", str(hid), "--noconftest"], cwd=hid,
                   env_pythonpath=str(model_dir), junit=str(work / "hidden.xml"), timeout=timeout)
    task_t = [t for t in r["tests"] if t["name"].startswith("test_task_")]
    keep_t = [t for t in r["tests"] if t["name"].startswith("test_keep_")]
    r.update(task_total=len(task_t), task_passed=sum(t["status"] == "passed" for t in task_t),
             keep_total=len(keep_t), keep_passed=sum(t["status"] == "passed" for t in keep_t),
             failures=[t["name"] for t in r["tests"] if t["status"] != "passed"])
    if r["timed_out"]:
        r.update(passed=0, failed=r["total"], task_passed=0, keep_passed=0)
    return r


def score_mutation(model_dir, work, timeout):
    """T6: the model's tests against the untouched package and each mutant."""
    pristine = B / "reference" / "T6" / "inventory_service"
    model_tests = model_dir / "tests"
    res = {"has_tests": (model_tests / "test_reports.py").exists(), "mutants": {}, "killed": 0,
           "mutant_total": len(list((B / "reference" / "mutants" / "T6").glob("*.py")))}
    if not res["has_tests"]:
        res.update(original=None, score=0.0, note="no tests/test_reports.py")
        return res
    tests_only = [f for f in model_tests.iterdir() if f.name in ("test_reports.py", "conftest.py")]

    def setup(name, reports_src):
        d = work / name
        shutil.copytree(pristine, d / "inventory_service", ignore=shutil.ignore_patterns("__pycache__"))
        if reports_src is not None:
            shutil.copy(reports_src, d / "inventory_service" / "reports.py")
        (d / "tests").mkdir()
        for f in tests_only:
            shutil.copy(f, d / "tests" / f.name)
        (d / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        return d

    d = setup("original", None)
    orig = run_pytest(["tests/test_reports.py", "-c", "pytest.ini", "--rootdir", "."], cwd=d, env_pythonpath=str(d),
                      junit=str(d / "junit.xml"), timeout=timeout)
    res["original"] = {k: orig[k] for k in ("total", "passed", "failed", "returncode", "timed_out", "seconds")}
    res["original"]["failures"] = [t["name"] for t in orig["tests"] if t["status"] != "passed"]
    if orig["timed_out"] or orig["total"] == 0 or orig["failed"] > 0:
        res.update(score=0.0, note="tests do not pass on the untouched package")
        return res
    for m in sorted((B / "reference" / "mutants" / "T6").glob("*.py")):
        d = setup(m.stem, m)
        r = run_pytest(["tests/test_reports.py", "-c", "pytest.ini", "--rootdir", "."], cwd=d, env_pythonpath=str(d),
                       junit=str(d / "junit.xml"), timeout=timeout)
        killed = r["timed_out"] or r["failed"] > 0 or r["returncode"] not in (0,)
        res["mutants"][m.stem] = {"killed": bool(killed), "failed_tests": r["failed"], "timed_out": r["timed_out"]}
    res["killed"] = sum(v["killed"] for v in res["mutants"].values())
    res["score"] = res["killed"] / res["mutant_total"]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=sorted(TASK_DIRS))
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label")
    ap.add_argument("--timeout", type=float, default=300)
    a = ap.parse_args()
    src = pathlib.Path(a.dir).resolve()
    label = a.label or f"{a.task}-{datetime.datetime.now():%Y%m%d-%H%M%S}"
    work = B / "scoring" / label
    if work.exists():
        sys.exit(f"{work} exists already; pick another --label")
    work.mkdir(parents=True)
    model = work / "model"
    copy_model(src, model)
    start = B / "tasks" / TASK_DIRS[a.task]
    result = {"task": a.task, "source_dir": str(src), "label": label, "scored_at": datetime.datetime.now().isoformat(),
              "package_changed": tree_hash(model / "inventory_service") != tree_hash(start / "inventory_service"),
              "tests_changed": tree_hash(model / "tests") != tree_hash(start / "tests")}
    vis = run_pytest(["tests"], cwd=model, env_pythonpath=str(model), junit=str(work / "visible.xml"),
                     timeout=a.timeout)
    result["visible"] = {k: vis[k] for k in ("total", "passed", "failed", "returncode", "timed_out", "seconds")}
    if a.task == "T6":
        result["mutation"] = score_mutation(model, work / "mutation", a.timeout)
        result["score"] = result["mutation"]["score"]
        result["hidden"] = None
    else:
        h = score_hidden(a.task, model, work, a.timeout)
        result["hidden"] = {k: h[k] for k in ("total", "passed", "failed", "task_total", "task_passed", "keep_total",
                                              "keep_passed", "failures", "returncode", "timed_out", "seconds")}
        result["hidden"]["output_tail"] = h["output_tail"]
        result["score"] = h["passed"] / h["total"] if h["total"] else 0.0
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    brief = {k: result[k] for k in ("task", "label", "score", "package_changed", "tests_changed")}
    brief["visible"] = f"{result['visible']['passed']}/{result['visible']['total']}"
    if result["hidden"]:
        brief["hidden"] = f"{result['hidden']['passed']}/{result['hidden']['total']} (task {result['hidden']['task_passed']}/" \
                          f"{result['hidden']['task_total']}, keep {result['hidden']['keep_passed']}/{result['hidden']['keep_total']})"
    else:
        m = result["mutation"]
        brief["mutation"] = f"{m['killed']}/{m['mutant_total']} killed" + (f" ({m.get('note')})" if m.get("note") else "")
    print(json.dumps(brief))


if __name__ == "__main__":
    main()
