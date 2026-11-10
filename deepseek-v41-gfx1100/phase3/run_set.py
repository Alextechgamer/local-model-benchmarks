"""Run a list of coding-bench tasks one after another (one rep each) and log each result line.

usage: python run_set.py MODEL PROMPT T1,T2,... [EFFORT]   (PROMPT: default | smallest; EFFORT: low | medium | high)
"""
import subprocess, sys, time

model, prompt, tasks = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
effort = sys.argv[4] if len(sys.argv) > 4 else "medium"
RT = r"E:\strata-dsv41\pagoda\coding-bench\tools\run_task.py"
for t in tasks:
    print(time.strftime("%H:%M:%S"), "START", model, prompt, effort, t, flush=True)
    p = subprocess.run([sys.executable, RT, "--model", model, "--task", t, "--rep", "1", "--prompt", prompt, "--effort", effort],
                       capture_output=True, text=True)
    print(time.strftime("%H:%M:%S"), "END", t, "rc", p.returncode, (p.stdout or "").strip()[-1500:],
          (p.stderr or "").strip()[-1500:], flush=True)
print(time.strftime("%H:%M:%S"), "ALL-DONE", flush=True)
