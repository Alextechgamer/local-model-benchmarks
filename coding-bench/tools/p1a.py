"""Phase 1 for Model A (Strata): build a config variant from a base config and run it as an arm.

usage: python p1a.py <tag> <base config name> [--set-arg FLAG VALUE] [--env K=V] [--del-env K] [--smoke] [--no-tune]
  writes configs/tune/A-<tag>.json and runs arm.py on port 8080 with that engine version's serve/server.py
"""
import argparse, json, pathlib, subprocess, sys

B = pathlib.Path(r"E:\strata-tests\coding-bench")
PY = r"C:\Users\user\Strata\.venv\Scripts\python.exe"
ap = argparse.ArgumentParser()
ap.add_argument("tag")
ap.add_argument("base")
ap.add_argument("--set-arg", nargs=2, action="append", default=[], metavar=("FLAG", "VALUE"))
ap.add_argument("--add-flag", action="append", default=[])
ap.add_argument("--env", action="append", default=[])
ap.add_argument("--del-env", action="append", default=[])
ap.add_argument("--smoke", action="store_true")
ap.add_argument("--no-tune", action="store_true")
ap.add_argument("--keep", action="store_true")
ap.add_argument("--need-gb", type=float, default=36)
ap.add_argument("--tune-prompt")
a = ap.parse_args()

cfg = json.loads((B / "configs" / "tune" / f"{a.base}.json").read_text(encoding="utf-8"))
args = cfg["args"]
for flag, val in a.set_arg:
    if flag in args:
        args[args.index(flag) + 1] = val
    else:
        args += [flag, val]
for flag in a.add_flag:
    if flag not in args:
        args.append(flag)
for kv in a.env:
    k, v = kv.split("=", 1); cfg["env"][k] = v
for k in a.del_env:
    cfg["env"].pop(k, None)
name = f"A-{a.tag}"
cfg["log"] = str(B / "logs" / "server" / f"{name}.engine.log")
out = B / "configs" / "tune" / f"{name}.json"
out.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
root = pathlib.Path(cfg["cwd"])
cmd = [sys.executable, str(B / "tools" / "arm.py"), "--tag", name, "--port", "8080", "--cwd", str(root),
       "--mem-csv", str(B / "power" / "p1-a-mem.csv"), "--need-gb", str(a.need_gb), "--load-timeout", "1200"]
if a.smoke:
    cmd.append("--smoke")
if a.no_tune:
    cmd.append("--no-tune")
if a.keep:
    cmd.append("--keep")
if a.tune_prompt:
    cmd += ["--tune-prompt", a.tune_prompt]
cmd += ["--", PY, str(root / "serve" / "server.py"), "--engine", "strata", "--config", str(out), "--port", "8080"]
print(">>>", name, flush=True)
sys.exit(subprocess.run(cmd).returncode)
