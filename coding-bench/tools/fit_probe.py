"""Find the largest llama-server context that runs a 16K prompt without VRAM spill (GPU Shared Usage growth).

usage: python fit_probe.py <tag> <ctx> [<ctx> ...] -- <server exe> <args without -c>
For each ctx: start the server, send the 16K prompt once (32 output tokens), record peak dedicated/shared VRAM and
prompt tok/s, stop the server. Appends to results/fit-probe.jsonl.
"""
import json, subprocess, sys, time, pathlib, urllib.request

B = pathlib.Path(r"E:\strata-tests\coding-bench")
sep = sys.argv.index("--")
tag, ctxs = sys.argv[1], [int(x) for x in sys.argv[2:sep]]
exe = sys.argv[sep + 1:]
port = exe[exe.index("--port") + 1]
url = f"http://127.0.0.1:{port}/v1"


def counters():
    ps = ("$s=(Get-Counter '\\GPU Adapter Memory(*)\\Dedicated Usage','\\GPU Adapter Memory(*)\\Shared Usage').CounterSamples;"
          "$d=($s|?{$_.Path -match 'dedicated'}|Measure-Object CookedValue -Max).Maximum/1MB;"
          "$h=($s|?{$_.Path -match 'shared'}|Measure-Object CookedValue -Max).Maximum/1MB; \"$d $h\"")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.split()
    return float(out[0]), float(out[1])


base_d, base_s = counters()
for ctx in ctxs:
    log = open(B / "logs" / "server" / f"fit-{tag}-{ctx}.log", "ab")
    p = subprocess.Popen(exe + ["-c", str(ctx)], stdout=log, stderr=subprocess.STDOUT)
    t0 = time.time(); ok = False
    while time.time() - t0 < 300 and p.poll() is None:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5); ok = True; break
        except Exception:
            time.sleep(2)
    row = {"tag": tag, "ctx": ctx, "loaded": ok, "base_dedicated_mb": base_d, "base_shared_mb": base_s}
    if ok:
        row["after_load"] = counters()
        import threading
        peak = [0, 0]; stop = [False]

        def sample():
            while not stop[0]:
                d, s = counters(); peak[0] = max(peak[0], d); peak[1] = max(peak[1], s)
        th = threading.Thread(target=sample, daemon=True); th.start()
        r = subprocess.run([sys.executable, str(B / "tools" / "bench_client.py"), "--url", url, "--prompt-file",
                            str(B / "tools" / "prompt-16k.txt"), "--max-tokens", "32", "--nonce", "--tag",
                            f"fit-{tag}-{ctx}", "--timeout", "900"], capture_output=True, text=True)
        stop[0] = True; th.join(timeout=10)
        row.update(json.loads(r.stdout.strip().splitlines()[-1]))
        row["peak_dedicated_mb"], row["peak_shared_mb"] = peak
        row["spill_mb"] = peak[1] - base_s
    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
    time.sleep(5)
    with open(B / "results" / "fit-probe.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    print(json.dumps({k: row.get(k) for k in ("ctx", "loaded", "peak_dedicated_mb", "peak_shared_mb", "spill_mb",
                                              "prompt_tps_client", "error")}), flush=True)
