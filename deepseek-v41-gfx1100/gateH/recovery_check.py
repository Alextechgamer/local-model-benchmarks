"""Check run_task.py's NaN recovery on the real server (C-gpu, experts on the card).

1. nan_repro.py until the server reports a NaN stop (at most 6 tries).
2. measure.py once: the poisoned server (expect stops on short prompts).
3. nan_restart() from run_task.py, with a stand-in process for opencode (suspended and resumed).
4. measure.py once more: expect every answer clean.
"""
import importlib.util, json, pathlib, subprocess, sys, time

H = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("rt", r"E:\strata-dsv41\pagoda\coding-bench\tools\run_task.py")
sys.argv = ["run_task.py"]
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)
m = rt.MODELS["C-gpu"]


def nan_count(at):
    with open(rt.SERVER_LOG, "rb") as f:
        f.seek(at)
        return f.read().decode("utf-8", "replace").count(rt.NAN_TEXT)


srv_at, log_at = rt.SERVER_LOG.stat().st_size, rt.ENGINE_LOG.stat().st_size
for i in range(6):
    subprocess.run([sys.executable, str(H / "nan_repro.py"), f"recovery-try{i + 1}", "22000", "8091"])
    if nan_count(srv_at):
        print(f"NaN stop on try {i + 1}", flush=True)
        break
else:
    print("no NaN in 6 tries; recovery not exercised", flush=True)
    sys.exit(0)

meas = [sys.executable, str(H.parent / "gateG" / "measure.py")]
subprocess.run(meas + ["recovery-poisoned", "8091", "3"])
print("NaN lines before restart:", nan_count(srv_at), flush=True)
stand_in = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"])
rec = rt.nan_restart(m, stand_in.pid, log_at, nan_count(srv_at))
alive = stand_in.poll() is None
stand_in.kill()
print("restart:", json.dumps(rec), "stand-in alive after resume:", alive, flush=True)
seen = nan_count(srv_at)
subprocess.run(meas + ["recovery-after-restart", "8091", "3"])
print("new NaN lines after restart:", nan_count(srv_at) - seen, flush=True)
