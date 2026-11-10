"""Fifth patch: NaN recovery. For a model with a "relaunch" script: watch Strata's server log during the run; on
"numbers went non-finite", freeze opencode, restart the engine with the same flags, wait until it answers, then let
opencode go on (its own retry re-sends the request). At most 3 restarts per task, then the run ends as DNF-NaN.
Writes a copy first and checks it compiles, so a run that starts meanwhile never sees a half-written file."""
import pathlib, py_compile, os

p = pathlib.Path(r"E:\strata-dsv41\pagoda\coding-bench\tools\run_task.py")
s = p.read_text(encoding="utf-8")
rep = [
('''    "C5": {"provider": "strata", "model": "deepseek", "url": "http://127.0.0.1:8091/v1", "context": 65532,
           "output": 16384, "name": "DeepSeek-V4.1-Flash uncensored 1.75bpw (Strata)", "engine_log": True},
}''',
 '''    "C5": {"provider": "strata", "model": "deepseek", "url": "http://127.0.0.1:8091/v1", "context": 65532,
           "output": 16384, "name": "DeepSeek-V4.1-Flash uncensored 1.75bpw (Strata)", "engine_log": True},
    # C-gpu: Gate G config 2 as-is (experts on the card), with NaN recovery: the engine is restarted by this script
    "C-gpu": {"provider": "strata", "model": "deepseek", "url": "http://127.0.0.1:8091/v1", "context": 65532,
              "output": 16384, "name": "DeepSeek-V4.1-Flash uncensored 1.75bpw (Strata)", "engine_log": True,
              "relaunch": r"E:\\strata-dsv41\\gateH\\relaunch-gpu.ps1"},
}
NAN_TEXT = "numbers went non-finite"
MAX_RESTARTS = 3'''),
('''def wait_engine_idle(quiet_s=30, max_s=900):''',
 '''def server_up(url, max_s=1200):
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


def wait_engine_idle(quiet_s=30, max_s=900):'''),
('''        while p.poll() is None:
            time.sleep(5)
            if time.time() - t0 > LIMIT_S:''',
 '''        while p.poll() is None:
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
            elif time.time() - t0 > LIMIT_S:'''),
('''    t0 = time.time()
    killed = None
''', '''    t0 = time.time()
    killed = None
    restarts, nan_handled = [], 0
'''),
('''            "cmd": cmd + ["<README on stdin>"]}''',
 '''            "cmd": cmd + ["<README on stdin>"]}
    if m.get("relaunch"):
        info["nan_restarts"] = restarts
        info["restart_s_total"] = round(sum(r["restart_s"] for r in restarts), 1)'''),
]
for a, b in rep:
    assert s.count(a) == 1, (a[:80], s.count(a))
    s = s.replace(a, b)
tmp = p.with_name("run_task.py.new")
tmp.write_bytes(s.replace("\r\n", "\n").encode("utf-8"))
py_compile.compile(str(tmp), doraise=True)
os.replace(tmp, p)
print("patched")
