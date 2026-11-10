"""Phase 4 driver for one model: power logs on, locked server up, ctx_run.py over every size, all off.

usage: python run_phase4.py A|B
Model A (Strata, max context 262,144) runs 8K..250K. Model B (llama.cpp, locked at 98,304) runs 8K..96K; larger
prompts do not fit the locked context and are recorded as such without a request (the stop rule).
"""
import subprocess, sys, time, pathlib

B = pathlib.Path(r"E:\strata-tests\coding-bench")
sys.path.insert(0, str(B / "tools"))
import run_phase3 as p3  # noqa: E402

LIMITS = {"A": 262144, "B": 98304}


def main():
    model = sys.argv[1]
    session = f"p4-{model}-{time.strftime('%Y%m%d-%H%M%S')}"
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(B / "tools" / "power.ps1"),
                    "start", session], check=True)
    p3.note(event="p4_power_start", session=session, model=model)
    pid = None
    try:
        pid = p3.start_server(model)
        # one short warm-up request so the first timed size does not pay the first-request cost
        p3.chat(p3.CFG[model]["url"], [{"role": "user", "content": "Say OK."}])
        subprocess.run([sys.executable, str(B / "tools" / "ctx_run.py"), "--model", model, "--url",
                        p3.CFG[model]["url"], "--ctx-limit", str(LIMITS[model]), "--mem-csv",
                        str(B / "power" / f"{session}-mem.csv")])
    finally:
        if pid:
            p3.stop_server(pid)
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(B / "tools" / "power.ps1"), "stop", session])
        p3.note(event="p4_power_stop", session=session, model=model)


if __name__ == "__main__":
    main()
