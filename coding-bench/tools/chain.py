"""Wait for a process to end, then run the remaining phases one after another (one model server at a time).

usage: python chain.py <pid to wait for>
"""
import ctypes, subprocess, sys, time, pathlib

B = pathlib.Path(r"E:\strata-tests\coding-bench")
STEPS = [("phase3-B", ["tools/run_phase3.py", "B"]), ("phase4-A", ["tools/run_phase4.py", "A"]),
         ("phase4-B", ["tools/run_phase4.py", "B"])]


def alive(pid: int) -> bool:
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = ctypes.c_ulong()
    ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
    ctypes.windll.kernel32.CloseHandle(h)
    return code.value == 259                                           # STILL_ACTIVE


def log(msg):
    with open(B / "logs" / "chain.log", "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    print(msg, flush=True)


pid = int(sys.argv[1])
while alive(pid):
    time.sleep(30)
log(f"pid {pid} ended")
time.sleep(30)                                                         # let the last server's RAM come back
for name, args in STEPS:
    with open(B / "logs" / f"{name}.log", "a", encoding="utf-8") as f:
        rc = subprocess.run([sys.executable] + [str(B / a) if a.endswith(".py") else a for a in args],
                            stdout=f, stderr=subprocess.STDOUT).returncode
    log(f"{name} exit {rc}")
    time.sleep(30)
log("chain done")
