"""Fourth pass: re-run the free models that failed in pass 3, with a fix for each failure mode.

Fixes (applied per model):
  - "thinking ate the reply limit" (big-pickle, mimo, space-bunny): the prompt makes the model BUILD IN PARTS (skeleton, then
    appended chunks) and write straight away; space-bunny and step-5 also get --variant low (their lowest reasoning effort).
  - "504 idle timeout / cut-off turn" (step-5, nemotron-ultra): the turn is resumed in the same session (-c) with a note to
    inspect the file and continue, instead of starting over.
  - "page with a syntax error" (nemotron-lightning): node --check on the module script; the exact error goes back to the model.
  - after all runs, a browser check; console errors / exceptions / no canvas go back to the model once, then it is re-checked.
usage: .chk/Scripts/python.exe r4.py
"""
import json, os, re, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).parent
BASE = (ROOT / "pagoda-local-input.txt").read_text(encoding="utf-8", errors="replace")
APPROVAL = "\nDo not wait for approval of a design or plan: nobody is available to answer. Go straight to building and finish in this one run."
BUILD_IN_PARTS = """
HOW TO BUILD (important, your reply budget is limited and thinking counts against it):
- Do NOT draft or outline the code in your thinking. Think for a few lines at most, then act.
- Write pagoda.html with your write tool in PARTS: first a skeleton (HTML, CSS, importmap, config, seeded RNG, voxel engine), then add each further part
  (scene builders, lighting, particles, UI wiring, animation loop) with the edit tool or by appending in a bash heredoc (cat >> pagoda.html <<'EOF' ... EOF).
  Each tool call should carry roughly 300 lines at most. The file in the current directory MUST be called pagoda.html.
- When all parts are in, run a syntax check, e.g. extract the script and run node --check on it, fix errors, and finish."""
MODELS = [  # (folder name, model, extra opencode args, build in parts)
    ("pickle", "big-pickle", [], True), ("mimo", "mimo-v2.6-flash-free", [], True),
    ("bunny", "space-bunny-free", ["--variant", "low"], True), ("step5", "step-5-preview-free", ["--variant", "low"], True),
    ("nemoultra", "nemotron-3-ultra-free", [], True), ("nemolight", "nemotron-3.5-lightning-free", [], False),
    ("ling31", "ling-3.1-flash-free", [], True), ("ling30", "ling-3.0-flash-fin-free", [], True),
]
BASH = shutil.which("bash") or r"C:\Program Files\Gitinash.exe"
MAX_ATTEMPTS, ATTEMPT_CAP, MODEL_CAP = 4, 1500, 2700


def run_opencode(folder: Path, name: str, model: str, extra: list, prompt: str, cont: bool, n: int) -> dict:
    # through Git Bash, like the earlier batch scripts: opencode is a .cmd shim on Windows and mangles multi-line arguments
    env = dict(os.environ, OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX="64000", OC_PROMPT=prompt, OC_MODEL=f"opencode/{model}")
    cmd = [BASH, "-c", 'exec opencode run "$OC_PROMPT" --pure -m "$OC_MODEL" --format json "$@"', "oc", *extra] + (["-c"] if cont else [])
    t0 = time.time()
    with open(ROOT / f"pagoda-{name}-r4-stream.jsonl", "ab") as out:
        try:
            subprocess.run(cmd, cwd=folder, stdout=out, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, env=env, timeout=ATTEMPT_CAP)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
    return {"attempt": n, "secs": round(time.time() - t0), "timed_out": timed_out}


def last_stream_error(name: str) -> str | None:
    err = None
    for line in (ROOT / f"pagoda-{name}-r4-stream.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "error":
            d = e.get("error", {}).get("data", {}); err = f"{d.get('statusCode') or ''} {str(d.get('message'))[:160]}".strip()
        elif e.get("type") == "step_start":
            err = None
    return err


def syntax_problem(page: Path) -> str | None:
    m = re.findall(r'<script type="module">(.*?)</script>', page.read_text(encoding="utf-8", errors="replace"), flags=re.S)
    if not m:
        return "there is no <script type=\"module\"> block in pagoda.html"
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "s.mjs"; f.write_text(max(m, key=len), encoding="utf-8")
        r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    return None if r.returncode == 0 else r.stderr.strip()[:900]


def drive(spec) -> dict:
    name, model, extra, parts = spec
    folder = ROOT / f"pagoda-{name}-r4"; folder.mkdir(exist_ok=True)
    (ROOT / f"pagoda-{name}-r4-stream.jsonl").write_bytes(b"")
    (folder / "opencode.json").write_text((ROOT / "pagoda-luna" / "opencode.json").read_text())
    page = folder / "pagoda.html"; log = []; t_start = time.time()
    prompt = BASE + APPROVAL + (BUILD_IN_PARTS if parts else "")
    for n in range(1, MAX_ATTEMPTS + 1):
        log.append(run_opencode(folder, name, model, extra, prompt, n > 1, n))
        err = last_stream_error(name)
        problem = None
        if not page.exists():
            problem = "pagoda.html does not exist in the current directory yet."
        elif (p := syntax_problem(page)):
            problem = f"pagoda.html has a JavaScript syntax error (node --check says):\n{p}"
        log[-1]["stream_error"] = err; log[-1]["problem"] = problem
        if not problem and not err:
            break
        if err and err.startswith(("410", "400", "404")) and not page.exists():
            break  # the service itself refuses this model: nothing to repair
        if time.time() - t_start > MODEL_CAP:
            break
        prompt = ("Your previous turn was cut off" + (f" ({err})" if err else "") + ". " if err or not problem else "") + \
                 (problem + "\n" if problem else "") + \
                 "Look at the current directory (ls, wc -l pagoda.html), then continue building or repairing pagoda.html until the complete page exists and passes node --check. " \
                 "Keep thinking short and write the file in parts."
    return {"name": name, "model": model, "attempts": log, "secs": round(time.time() - t_start)}


def browser_errors(name: str) -> tuple[list, dict]:
    page = ROOT / f"pagoda-{name}-r4" / "pagoda.html"
    subprocess.run([sys.executable, str(ROOT / "check_page.py"), f"{name}-r4", str(page), "Pond"], capture_output=True, timeout=300)
    c = json.loads((ROOT / "shots" / f"{name}-r4.json").read_text(encoding="utf-8"))
    errs = c["console_errors"] + c["exceptions"]
    if not c.get("page", {}).get("canvases"):
        errs.append("no <canvas> was created: the scene never rendered")
    return errs, c


if __name__ == "__main__":
    with ThreadPoolExecutor(3) as ex:
        results = list(ex.map(drive, MODELS))
    for r in results:  # sequential: check_page.py uses a fixed debugging port
        page = ROOT / f"pagoda-{r['name']}-r4" / "pagoda.html"
        r["browser_rounds"] = []
        for rnd in range(2):
            if not page.exists() or syntax_problem(page):
                break
            errs, c = browser_errors(r["name"]); r["browser_rounds"].append({"errors": errs[:4]})
            if not errs or rnd == 1:
                break
            fb = "Opening pagoda.html in a real browser gave these errors:\n" + "\n".join(f"- {e[:300]}" for e in errs[:5]) + \
                 "\nFix them with small edits to pagoda.html (read the relevant part first), run node --check, and finish."
            spec = next(m for m in MODELS if m[0] == r["name"])
            run_opencode(page.parent, r["name"], spec[1], spec[2], fb, True, 90 + rnd)
    (ROOT / "r4-results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("R4 DONE")
