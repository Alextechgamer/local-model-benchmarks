"""Run one Phase 1 arm: start a server, wait for it, time it (tune_run.py), optionally smoke-test it, stop it.

usage: python arm.py --tag NAME --port 8090 --mem-csv CSV [--smoke] [--no-tune] [--env K=V ...] -- <server command...>
The server's stdout/stderr go to logs/server/<tag>.log. Only the process tree started here is stopped.
Free RAM is checked before the start (--need-gb); if it is short the arm is skipped and recorded.
"""
import argparse, json, os, subprocess, sys, time, urllib.request, pathlib

B = pathlib.Path(r"E:\strata-tests\coding-bench")
ap = argparse.ArgumentParser()
ap.add_argument("--tag", required=True)
ap.add_argument("--port", type=int, required=True)
ap.add_argument("--mem-csv")
ap.add_argument("--smoke", action="store_true")
ap.add_argument("--no-tune", action="store_true")
ap.add_argument("--keep", action="store_true", help="leave the server running (prints its pid)")
ap.add_argument("--need-gb", type=float, default=8)
ap.add_argument("--load-timeout", type=float, default=900)
ap.add_argument("--env", action="append", default=[])
ap.add_argument("--cwd")
ap.add_argument("--tune-prompt", help="prompt file for tune_run.py (default: the 16K prompt)")
ap.add_argument("cmd", nargs=argparse.REMAINDER)
a = ap.parse_args()
cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
url = f"http://127.0.0.1:{a.port}/v1"
logdir = B / "logs" / "server"; logdir.mkdir(parents=True, exist_ok=True)
events = B / "results" / "arm-events.jsonl"


def note(**kw):
    kw.update(tag=a.tag, t=time.time())
    with open(events, "a", encoding="utf-8") as f:
        f.write(json.dumps(kw) + "\n")
    print(json.dumps(kw), flush=True)


def free_gb():
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"], capture_output=True, text=True)
    return int(out.stdout.strip()) / 1024 / 1024


def ready():
    try:
        body = {"model": "local", "messages": [{"role": "user", "content": "Say OK."}], "max_tokens": 4,
                "chat_template_kwargs": {"enable_thinking": False}}
        req = urllib.request.Request(url + "/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status == 200
    except Exception:
        return False


fg = free_gb()
t_wait = time.time()
while fg < a.need_gb and time.time() - t_wait < 180:   # RAM from the previous server can take a minute to free
    time.sleep(10); fg = free_gb()
if fg < a.need_gb:
    note(event="skipped_low_ram", free_gb=round(fg, 1), need_gb=a.need_gb)
    sys.exit(3)
env = dict(os.environ)
for kv in a.env:
    k, v = kv.split("=", 1); env[k] = v
log = open(logdir / f"{a.tag}.log", "ab")
t0 = time.time()
p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=a.cwd,
                     creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
note(event="start", pid=p.pid, free_gb=round(fg, 1), cmd=cmd, env=a.env)
ok = False
while time.time() - t0 < a.load_timeout:
    if p.poll() is not None:
        break
    if ready():
        ok = True; break
    time.sleep(3)
load_s = time.time() - t0
if not ok:
    note(event="load_failed", exit=p.poll(), load_s=round(load_s, 1))
    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
    sys.exit(2)
note(event="loaded", load_s=round(load_s, 1))
rc = 0
try:
    if not a.no_tune:
        r = subprocess.run([sys.executable, str(B / "tools" / "tune_run.py"), "--url", url, "--tag", a.tag] +
                           (["--mem-csv", a.mem_csv] if a.mem_csv else []) +
                           (["--prompt", a.tune_prompt] if a.tune_prompt else []))
        rc |= r.returncode
    if a.smoke:
        r = subprocess.run([sys.executable, str(B / "tools" / "smoke.py"), "--url", url, "--tag", a.tag])
        rc |= r.returncode
finally:
    if a.keep:
        note(event="kept", pid=p.pid)
    else:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
        try:
            p.wait(timeout=60)
        except Exception:
            pass
        note(event="stopped", pid=p.pid, alive_s=round(time.time() - t0, 1))
sys.exit(rc)
