"""Phase 3: one opencode run of one task on one model, then scoring.

usage: python run_task.py --model A|B --task T1 --rep 1
Work folder: runs/<model>/<task>/r<rep>/work (a fresh copy of tasks/<task> + the bench opencode.json).
Saved next to it: stream.jsonl (opencode --format json), stderr.txt, run.json (times, steps, tokens, flags), score.json.
Limits: 45 minutes wall time (the process tree is killed), 150 steps (opencode "steps" setting, and counted here).
"""
import argparse, json, os, pathlib, re, shutil, subprocess, sys, time

B = pathlib.Path(__file__).resolve().parents[1]       # this coding-bench folder (was a fixed E:\strata-tests path)
sys.path.insert(0, str(B))
from score import TASK_DIRS  # noqa: E402

MODELS = {
    "A": {"provider": "strata", "model": "coder", "url": "http://127.0.0.1:8080/v1", "context": 262144,
          "name": "Qwen3.8-Flash-Next Coder IQ1_M (Strata)"},
    "B": {"provider": "llamacpp", "model": "qwen38-27b", "url": "http://127.0.0.1:8090/v1", "context": 98304,
          "name": "Qwen3.8-27B IQ4_XS (llama.cpp)"},
    # DeepSeek-V4.1-Flash (AtomicChat uncensored GSQ-RCO 1.75 bpw) on Strata, self-built gfx1100 engine. C: 6 experts
    # (full quality, Gate G config 2). C5: the same server restarted with 5 experts (a quality change). The server runs
    # --max-context 65532 and shortens max_tokens to the room left; output 16384 leaves opencode ~49K of input.
    "C": {"provider": "strata", "model": "deepseek", "url": "http://127.0.0.1:8091/v1", "context": 65532,
          "output": 16384, "name": "DeepSeek-V4.1-Flash uncensored 1.75bpw (Strata)", "engine_log": True},
    "C5": {"provider": "strata", "model": "deepseek", "url": "http://127.0.0.1:8091/v1", "context": 65532,
           "output": 16384, "name": "DeepSeek-V4.1-Flash uncensored 1.75bpw (Strata)", "engine_log": True},
    # C-gpu: Gate G config 2 as-is (experts on the card), with NaN recovery: the engine is restarted by this script
    "C-gpu": {"provider": "strata", "model": "deepseek", "url": "http://127.0.0.1:8091/v1", "context": 65532,
              "output": 16384, "name": "DeepSeek-V4.1-Flash uncensored 1.75bpw (Strata)", "engine_log": True,
              "relaunch": r"E:\strata-dsv41\gateH\relaunch-gpu.ps1"},
}
NAN_TEXT = "numbers went non-finite"
MAX_RESTARTS = 3
# One fixed work folder for every DeepSeek run, outside any git repo, so opencode's system prompt (which ends with the
# working directory and the date) is identical across tasks and Strata's prefix cache can reuse it.
LIVE = pathlib.Path(os.environ.get("BENCH_LIVE_DIR", r"E:\strata-dsv41\gateH\live\work"))
ENGINE_LOG = pathlib.Path(os.environ.get("BENCH_ENGINE_LOG",
                          r"C:\Users\user\AppData\Local\Strata\launch\ist-das-1-75bpw-65-532k.engine.log"))
SERVER_LOG = pathlib.Path(os.environ.get("BENCH_SERVER_LOG",
                          r"C:\Users\user\AppData\Local\Strata\runtime\launch-ist-das-1-75bpw-65-532k.server.log"))
PROMPTS = {"default": None, "smallest": B.parent / "bench" / "prompts" / "smallest-fix.txt"}
TURN = re.compile(r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms \(([\d.]+) tok/s\), (\d+) generated "
                  r"in (\d+) ms \(([\d.]+) tok/s\)")
DRAFT = re.compile(r"drafts (\d+) of (\d+) kept")
LIMIT_S, LIMIT_STEPS = 45 * 60, 150


def opencode_config(m, instructions=None, effort="medium", output=None):
    cfg = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {m["provider"]: {
            "npm": "@ai-sdk/openai-compatible", "name": m["name"],
            "options": {"baseURL": m["url"], "apiKey": "none", "timeout": False},
            "models": {m["model"]: {"name": m["name"], "limit": {"context": m["context"], "output": output or m.get("output", 32768)},
                                    "options": {"reasoningEffort": effort}}}}},
        "mcp": {"unityMCP": {"enabled": False}, "ghidra": {"enabled": False}, "rea": {"enabled": False}},
        "agent": {"build": {"steps": LIMIT_STEPS}},
        "permission": {"edit": "allow", "bash": "allow", "webfetch": "deny", "websearch": "deny", "task": "deny",
                       "skill": {"*": "deny"}},
    }
    if instructions:                                       # appended to opencode's system prompt
        cfg["instructions"] = [str(instructions)]
    return cfg


THINK = re.compile(r"\[strata\] thinking: (\d+) of budget")
DONE = re.compile(r"\[strata\] done: (\d+) tokens")


def server_thinking(text: str) -> list:
    """Per request, from Strata's server log: the last 'thinking: N of budget' count before its 'done: N tokens'
    line (0 when the request did not think), and the request's total output tokens."""
    out, think = [], 0
    for line in text.splitlines():
        t = THINK.search(line)
        if t:
            think = int(t.group(1))
            continue
        d = DONE.search(line)
        if d:
            out.append({"thinking": think, "output": int(d.group(1))})
            think = 0
    return out


def engine_turns(text: str) -> list:
    """Per request, from the Strata DeepSeek engine log: prompt tokens (reused from the prefix cache / read fresh),
    prompt read time (engine-side time to first token), tokens generated, decode tok/s, DSpark drafts kept."""
    turns = []
    for line in text.splitlines():
        m = TURN.search(line)
        if m:
            p, reused, fresh, ms, ptps, gen, gms, dtps = m.groups()
            turns.append({"prompt": int(p), "cached": int(reused), "fresh": int(fresh), "prompt_ms": int(ms),
                          "prompt_tok_s": float(ptps), "generated": int(gen), "gen_ms": int(gms),
                          "decode_tok_s": float(dtps)})
            continue
        d = DRAFT.search(line)
        if d and turns and "drafts_kept" not in turns[-1]:
            turns[-1]["drafts_kept"], turns[-1]["drafts"] = int(d.group(1)), int(d.group(2))
    return turns


# The disk that holds the model files. On the Gate H PC, E: is disk 0 (checked 2026-11-09 with
# `Get-Partition -DriveLetter E | Get-Disk`: Number 0, CT1000P3PSSD8), so the default is 0.
BENCH_DISK = int(os.environ.get("BENCH_DISK", "0"))


def disk_e_read():
    try:
        import psutil
        return psutil.disk_io_counters(perdisk=True)[f"PhysicalDrive{BENCH_DISK}"].read_bytes
    except Exception:
        return None


def server_up(url, max_s=1200):
    """Wait until the server lists its models again."""
    import urllib.request
    t0 = time.time()
    while time.time() - t0 < max_s:
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/models", timeout=10) as r:
                if r.status == 200:
                    return True
        except Exception:                                  # noqa: BLE001
            pass
        time.sleep(5)
    return False


def nan_restart(m, opencode_pid, log_at, srv_seen):
    """Freeze opencode, restart the engine, wait until it answers, unfreeze. Returns the restart record."""
    import psutil
    t0 = time.time()
    procs = []
    try:
        root = psutil.Process(opencode_pid)
        procs = [root] + root.children(recursive=True)
        for pr in procs:
            pr.suspend()
    except psutil.Error:
        pass
    with open(ENGINE_LOG, "rb") as f:
        f.seek(log_at)
        turns = engine_turns(f.read().decode("utf-8", "replace"))
    last = turns[-1] if turns else {}
    rc = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", m["relaunch"]],
                        capture_output=True, text=True).returncode
    up = server_up(m["url"])
    for pr in procs:
        try:
            pr.resume()
        except psutil.Error:
            pass
    return {"at_s": round(t0, 1), "turn": len(turns), "failed_prompt": last.get("prompt"),
            "failed_fresh_tokens": last.get("fresh"), "failed_generated": last.get("generated"),
            "nan_lines_seen": srv_seen, "relaunch_rc": rc, "server_up": up, "restart_s": round(time.time() - t0, 1)}


def wait_engine_idle(quiet_s=30, max_s=900):
    """After a kill the engine may still be finishing the cut-off request; wait until its log stops growing."""
    t0, last, size = time.time(), time.time(), ENGINE_LOG.stat().st_size
    while time.time() - t0 < max_s:
        time.sleep(5)
        s = ENGINE_LOG.stat().st_size
        if s != size:
            size, last = s, time.time()
        elif time.time() - last >= quiet_s:
            break
    return round(time.time() - t0, 1)


def analyse(stream: pathlib.Path) -> dict:
    steps = tool_calls = 0
    tok = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
    ran_tests, peeked, errors, last_text = [], [], [], ""
    per_step = []                                          # opencode's tokens per step (one model request each)
    for line in stream.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        t = e.get("type")
        part = e.get("part") or {}
        if t == "step_start":
            steps += 1
        elif t == "step_finish":
            k = part.get("tokens") or {}
            tok["input"] += k.get("input", 0) or 0
            tok["output"] += k.get("output", 0) or 0
            tok["reasoning"] += k.get("reasoning", 0) or 0
            tok["cache_read"] += (k.get("cache") or {}).get("read", 0) or 0
            tok["cache_write"] += (k.get("cache") or {}).get("write", 0) or 0
            per_step.append({"output": k.get("output", 0) or 0, "reasoning": k.get("reasoning", 0) or 0})
        elif t == "tool_use":
            tool_calls += 1
            inp = json.dumps((part.get("state") or {}).get("input", {}))
            if part.get("tool") == "bash" and "pytest" in inp:
                ran_tests.append(inp[:200])
            low = inp.lower().replace("\\\\", "/").replace("\\", "/")
            if any(s in low for s in ("/hidden", "coding-bench/reference", "/reference/", "../..", "frozen.txt",
                                      "score.py", "/scoring")):
                peeked.append(inp[:300])
        elif t == "text":
            last_text = part.get("text", "")[-2000:]
        elif t == "error":
            errors.append(json.dumps(e)[:500])
    return {"steps": steps, "tool_calls": tool_calls, "tokens": tok, "ran_visible_tests": bool(ran_tests),
            "pytest_calls": len(ran_tests), "tokens_per_step": per_step, "peeked_outside": peeked, "errors": errors, "final_text": last_text}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=MODELS)
    ap.add_argument("--task", required=True, choices=sorted(TASK_DIRS))
    ap.add_argument("--rep", type=int, required=True)
    ap.add_argument("--prompt", default="default", choices=PROMPTS)
    ap.add_argument("--effort", default="medium", choices=("low", "medium", "high"),
                    help="opencode reasoningEffort; medium (the default) keeps the earlier runs' names and config")
    ap.add_argument("--output", type=int, default=None,
                    help="opencode's output limit (max_tokens per request); unset keeps the model's value and run name")
    a = ap.parse_args()
    m = MODELS[a.model]
    run_name = a.model + ("" if a.prompt == "default" else f"-{a.prompt}") + ("" if a.effort == "medium" else f"-{a.effort}")         + ("" if a.output is None else f"-out{a.output // 1024}k")
    chk = subprocess.run([sys.executable, str(B / "tools" / "freeze.py"), "check"], capture_output=True, text=True)
    if chk.returncode != 0:
        sys.exit(f"freeze check failed: {chk.stdout}")
    rd = B / "runs" / run_name / a.task / f"r{a.rep}"
    if rd.exists():
        sys.exit(f"{rd} exists already")
    rd.mkdir(parents=True)
    work = LIVE if m.get("engine_log") else rd / "work"
    if work.exists():
        # never delete a folder that is not the bench's own work folder
        if work == LIVE and not ("BENCH_LIVE_DIR" in os.environ or (work.name == "work" and "gateH" in work.parts)):
            sys.exit(f"refusing to delete {work}: not a gateH work folder (set BENCH_LIVE_DIR to use another one)")
        shutil.rmtree(work)
    shutil.copytree(B / "tasks" / TASK_DIRS[a.task], work)
    (work / "opencode.json").write_text(json.dumps(opencode_config(m, PROMPTS[a.prompt], a.effort, a.output), indent=1), encoding="utf-8")
    prompt = (work / "README.md").read_text(encoding="utf-8")
    env = dict(os.environ, OPENCODE_DISABLE_CLAUDE_CODE="1", OPENCODE_DISABLE_EXTERNAL_SKILLS="1",
               OPENCODE_DISABLE_CLAUDE_CODE_SKILLS="1", OPENCODE_PURE="1")
    env.pop("PYTHONPATH", None)
    # a PWD inherited from a POSIX shell (Git Bash) makes opencode look for its config in that folder, not in cwd
    env.pop("PWD", None)
    env.pop("OLDPWD", None)
    # the native exe, not opencode.cmd: cmd.exe would mangle a multi-line prompt with quotes and backticks
    opencode = r"C:\Users\user\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe"
    # the README goes in on stdin: the exe does not parse Windows command-line quoting (checked with a capture server)
    cmd = [opencode, "run", "--pure", "-m", f"{m['provider']}/{m['model']}", "--format", "json"]
    stream, errf = rd / "stream.jsonl", rd / "stderr.txt"
    log_at = ENGINE_LOG.stat().st_size if m.get("engine_log") else 0
    srv_at = SERVER_LOG.stat().st_size if m.get("engine_log") and SERVER_LOG.exists() else 0
    disk0 = disk_e_read()
    t0 = time.time()
    killed = None
    restarts, nan_handled = [], 0
    (rd / "prompt.txt").write_text(prompt, encoding="utf-8")
    with open(stream, "wb") as so, open(errf, "wb") as se, open(rd / "prompt.txt", "rb") as si:
        p = subprocess.Popen(cmd, cwd=work, env=env, stdout=so, stderr=se, stdin=si,
                             creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        while p.poll() is None:
            time.sleep(5)
            if m.get("relaunch") and SERVER_LOG.exists():
                # NaN recovery: a NaN stop leaves the engine failing until it restarts (Phase 3, part 1)
                with open(SERVER_LOG, "rb") as f:
                    f.seek(srv_at)
                    seen = f.read().decode("utf-8", "replace").count(NAN_TEXT)
                if seen > nan_handled:
                    if len(restarts) >= MAX_RESTARTS:
                        killed = "DNF-NaN"
                    else:
                        restarts.append(nan_restart(m, p.pid, log_at, seen))
                        with open(SERVER_LOG, "rb") as f:
                            f.seek(srv_at)
                            nan_handled = f.read().decode("utf-8", "replace").count(NAN_TEXT)
            if killed:
                pass
            # NaN restarts pause opencode; their time does not count against the task's time limit
            elif time.time() - t0 - sum(r["restart_s"] for r in restarts) > LIMIT_S:
                killed = "time limit"
            else:
                try:
                    n = sum(1 for l in stream.read_text(encoding="utf-8", errors="replace").splitlines()
                            if '"type":"step_start"' in l)
                    if n > LIMIT_STEPS + 5:                      # opencode's own limit failed; stop it here
                        killed = "step limit"
                except OSError:
                    pass
            if killed:
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
                break
        p.wait()
    t1 = time.time()
    info = {"model": a.model, "prompt_variant": a.prompt, "reasoning_effort": a.effort,
            "output_limit": a.output or m.get("output", 32768), "task": a.task, "rep": a.rep, "t0": t0, "t1": t1,
            "wall_s": round(t1 - t0, 1), "exit_code": p.returncode, "killed": killed, "prompt_chars": len(prompt),
            "cmd": cmd + ["<README on stdin>"]}
    if m.get("relaunch"):
        info["nan_restarts"] = restarts
        info["restart_s_total"] = round(sum(r["restart_s"] for r in restarts), 1)
        info["wall_s_excl_restarts"] = round(info["wall_s"] - info["restart_s_total"], 1)
    info.update(analyse(stream))
    if m.get("engine_log"):
        if killed:
            info["engine_idle_wait_s"] = wait_engine_idle()
        disk1 = disk_e_read()
        with open(ENGINE_LOG, "rb") as f:
            f.seek(log_at)
            elog = f.read().decode("utf-8", "replace")
        (rd / "engine.log").write_text(elog, encoding="utf-8")
        slog = ""
        if SERVER_LOG.exists():
            with open(SERVER_LOG, "rb") as f:
                f.seek(srv_at)
                slog = f.read().decode("utf-8", "replace")
            (rd / "server.log").write_text(slog, encoding="utf-8")
        # the engine stops a request whose numbers went non-finite; opencode then retries the whole prompt
        info["nan_drops"] = slog.count("numbers went non-finite")
        thinking = server_thinking(slog)
        info["thinking_per_request"] = [t["thinking"] for t in thinking]
        info["thinking_total"] = sum(t["thinking"] for t in thinking)
        info["thinking_max"] = max((t["thinking"] for t in thinking), default=0)
        turns = engine_turns(elog)
        (rd / "turns.json").write_text(json.dumps(turns, indent=1), encoding="utf-8")
        gen_ms = sum(t["gen_ms"] for t in turns)
        pms = sorted(t["prompt_ms"] for t in turns)
        info["engine"] = {
            "turns": len(turns), "prompt_tokens": sum(t["prompt"] for t in turns),
            "cached_tokens": sum(t["cached"] for t in turns), "fresh_tokens": sum(t["fresh"] for t in turns),
            "first_turn": turns[0] if turns else None,
            "ttft_first_s": round(turns[0]["prompt_ms"] / 1000, 1) if turns else None,
            "ttft_median_s": round(pms[len(pms) // 2] / 1000, 1) if turns else None,
            "ttft_total_s": round(sum(pms) / 1000, 1),
            "output_tokens": sum(t["generated"] for t in turns),
            "decode_tok_s": round(sum(t["generated"] for t in turns) / (gen_ms / 1000), 2) if gen_ms else None,
            "drafts_kept": sum(t.get("drafts_kept", 0) for t in turns), "drafts": sum(t.get("drafts", 0) for t in turns)}
        info["disk_E_read_GB"] = round((disk1 - disk0) / 1e9, 1) if disk0 is not None and disk1 is not None else None
        shutil.move(str(work), str(rd / "work"))           # the fixed folder -> this run's folder, then score it there
        work = rd / "work"
    (rd / "run.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    sc = subprocess.run([sys.executable, str(B / "score.py"), "--task", a.task, "--dir", str(work),
                         "--out", str(rd / "score.json"), "--label", f"{run_name}-{a.task}-r{a.rep}"],
                        capture_output=True, text=True)
    print(json.dumps({"run": f"{run_name}-{a.task}-r{a.rep}", "wall_s": info["wall_s"], "steps": info["steps"],
                      "killed": killed, "ran_tests": info["ran_visible_tests"], "peeked": len(info["peeked_outside"]),
                      "score": sc.stdout.strip()[-400:] or sc.stderr.strip()[-400:]}), flush=True)


if __name__ == "__main__":
    main()
