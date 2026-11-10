"""Phase 3 driver for one model: power logs on, locked server up, 6 tasks x 2 reps through run_task.py, all off.

usage: python run_phase3.py A|B [--tasks T1,T2] [--reps 1,2]
Runs that already exist (runs/<model>/<task>/r<rep>/score.json) are skipped, so the driver can be resumed.
"""
import argparse, json, pathlib, re, subprocess, sys, time, urllib.request

B = pathlib.Path(r"E:\strata-tests\coding-bench")
T = B / "tools"
CFG = {"A": {"start": B / "configs" / "model-a-start.ps1", "url": "http://127.0.0.1:8080/v1", "need_gb": 36},
       "B": {"start": B / "configs" / "model-b-start.ps1", "url": "http://127.0.0.1:8090/v1", "need_gb": 8}}
LOG = B / "results" / "phase3-events.jsonl"


def note(**kw):
    kw["t"] = time.time()
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(kw) + "\n")
    print(json.dumps(kw), flush=True)


def free_gb():
    o = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
                       capture_output=True, text=True).stdout
    return int(o.strip()) / 1024 / 1024


def chat(url, messages, max_tokens=8, timeout=900, **extra):
    body = {"model": "local", "messages": messages, "max_tokens": max_tokens, "stream": False,
            "chat_template_kwargs": {"enable_thinking": False}} | extra
    req = urllib.request.Request(url + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def start_server(model):
    c = CFG[model]
    fg = free_gb()
    t_wait = time.time()
    while fg < c["need_gb"] and time.time() - t_wait < 300:
        time.sleep(15); fg = free_gb()
    if fg < c["need_gb"]:
        note(event="not_enough_ram", model=model, free_gb=round(fg, 1), need_gb=c["need_gb"])
        sys.exit(3)
    # output to a file, not a pipe: the server inherits the handle, and a pipe would never reach end-of-file
    outf = B / "logs" / f"start-{model}-{time.strftime('%Y%m%d-%H%M%S')}.txt"
    with open(outf, "w") as f:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(c["start"])],
                       stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    pid = int(re.search(r"pid (\d+)", outf.read_text()).group(1))
    t0 = time.time()
    while time.time() - t0 < 1200:
        try:
            chat(c["url"], [{"role": "user", "content": "Say OK."}], timeout=600)
            note(event="server_ready", model=model, pid=pid, load_s=round(time.time() - t0, 1), free_gb=round(fg, 1))
            return pid
        except Exception:
            time.sleep(5)
    note(event="server_failed", model=model, pid=pid)
    stop_server(pid)
    sys.exit(2)


def stop_server(pid):
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    note(event="server_stopped", pid=pid)


def alive(model):
    try:
        chat(CFG[model]["url"], [{"role": "user", "content": "Say OK."}], timeout=120)
        return True
    except Exception:
        return False


def cache_report_check(model):
    """Two requests that share a long prefix: does usage report cached prompt tokens?"""
    url = CFG[model]["url"]
    prefix = (B / "tools" / "prompt-900.txt").read_text(encoding="utf-8") * 3
    m1 = [{"role": "system", "content": prefix}, {"role": "user", "content": "Say one word."}]
    r1 = chat(url, m1, max_tokens=4)
    m2 = m1 + [{"role": "assistant", "content": "Okay."}, {"role": "user", "content": "Say another word."}]
    r2 = chat(url, m2, max_tokens=4)
    res = {"model": model, "first_usage": r1.get("usage"), "second_usage": r2.get("usage"),
           "second_timings": r2.get("timings")}
    (B / "results" / f"cache-reporting-{model}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    note(event="cache_check", model=model, usage=r2.get("usage"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model", choices=CFG)
    ap.add_argument("--tasks", default="T1,T2,T3,T4,T5,T6")
    ap.add_argument("--reps", default="1,2")
    a = ap.parse_args()
    session = f"p3-{a.model}-{time.strftime('%Y%m%d-%H%M%S')}"
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(T / "power.ps1"), "start",
                    session], check=True)
    note(event="power_start", session=session, model=a.model)
    pid = None
    try:
        pid = start_server(a.model)
        cache_report_check(a.model)
        for rep in [int(x) for x in a.reps.split(",")]:
            for task in a.tasks.split(","):
                rd = B / "runs" / a.model / task / f"r{rep}"
                if (rd / "score.json").exists():
                    continue
                if not alive(a.model):
                    note(event="server_dead_restart", model=a.model, before=f"{task} r{rep}")
                    stop_server(pid)
                    time.sleep(20)
                    pid = start_server(a.model)
                note(event="run_start", model=a.model, task=task, rep=rep, power_session=session)
                subprocess.run([sys.executable, str(T / "run_task.py"), "--model", a.model, "--task", task,
                                "--rep", str(rep)])
                note(event="run_end", model=a.model, task=task, rep=rep)
    finally:
        if pid:
            stop_server(pid)
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(T / "power.ps1"), "stop",
                        session])
        note(event="power_stop", session=session, model=a.model)


if __name__ == "__main__":
    main()
