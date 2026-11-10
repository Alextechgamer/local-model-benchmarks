"""Run one command and print the E: (PhysicalDrive0) bytes read during it, in GB."""
import psutil, subprocess, sys, time, json
d = lambda: psutil.disk_io_counters(perdisk=True)["PhysicalDrive0"].read_bytes
a, t = d(), time.time()
rc = subprocess.run(sys.argv[2:]).returncode
print(json.dumps({"label": sys.argv[1], "disk_E_read_GB": round((d() - a) / 1e9, 1), "wall_s": round(time.time() - t, 1), "rc": rc}), flush=True)
