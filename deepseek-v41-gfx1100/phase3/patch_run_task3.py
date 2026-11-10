"""Third patch (phase 3): --effort option, BENCH_DISK, a guard on the LIVE rmtree, per-turn reasoning tokens."""
import pathlib

p = pathlib.Path(r"E:\strata-dsv41\pagoda\coding-bench\tools\run_task.py")
s = p.read_text(encoding="utf-8")
rep = [
('''def opencode_config(m, instructions=None):''', '''def opencode_config(m, instructions=None, effort="medium"):'''),
('''"options": {"reasoningEffort": "medium"}}}}},''', '''"options": {"reasoningEffort": effort}}}}},'''),
('''def disk_e_read():
    try:
        import psutil
        return psutil.disk_io_counters(perdisk=True)["PhysicalDrive0"].read_bytes''',
 '''# The disk that holds the model files. On the Gate H PC, E: is disk 0 (checked 2026-11-09 with
# `Get-Partition -DriveLetter E | Get-Disk`: Number 0, CT1000P3PSSD8), so the default is 0.
BENCH_DISK = int(os.environ.get("BENCH_DISK", "0"))


def disk_e_read():
    try:
        import psutil
        return psutil.disk_io_counters(perdisk=True)[f"PhysicalDrive{BENCH_DISK}"].read_bytes'''),
('''    ran_tests, peeked, errors, last_text = [], [], [], ""''',
 '''    ran_tests, peeked, errors, last_text = [], [], [], ""
    per_step = []                                          # opencode's tokens per step (one model request each)'''),
('''            tok["cache_write"] += (k.get("cache") or {}).get("write", 0) or 0
''', '''            tok["cache_write"] += (k.get("cache") or {}).get("write", 0) or 0
            per_step.append({"output": k.get("output", 0) or 0, "reasoning": k.get("reasoning", 0) or 0})
'''),
('''"pytest_calls": len(ran_tests), "peeked_outside": peeked,''',
 '''"pytest_calls": len(ran_tests), "tokens_per_step": per_step, "peeked_outside": peeked,'''),
('''    ap.add_argument("--prompt", default="default", choices=PROMPTS)
    a = ap.parse_args()
    m = MODELS[a.model]
    run_name = a.model + ("" if a.prompt == "default" else f"-{a.prompt}")''',
 '''    ap.add_argument("--prompt", default="default", choices=PROMPTS)
    ap.add_argument("--effort", default="medium", choices=("low", "medium", "high"),
                    help="opencode reasoningEffort; medium (the default) keeps the earlier runs' names and config")
    a = ap.parse_args()
    m = MODELS[a.model]
    run_name = a.model + ("" if a.prompt == "default" else f"-{a.prompt}") + ("" if a.effort == "medium" else f"-{a.effort}")'''),
('''    if work.exists():
        shutil.rmtree(work)''',
 '''    if work.exists():
        # never delete a folder that is not the bench's own work folder
        if work == LIVE and not ("BENCH_LIVE_DIR" in os.environ or (work.name == "work" and "gateH" in work.parts)):
            sys.exit(f"refusing to delete {work}: not a gateH work folder (set BENCH_LIVE_DIR to use another one)")
        shutil.rmtree(work)'''),
('''opencode_config(m, PROMPTS[a.prompt])''', '''opencode_config(m, PROMPTS[a.prompt], a.effort)'''),
('''    info = {"model": a.model, "prompt_variant": a.prompt,''', '''    info = {"model": a.model, "prompt_variant": a.prompt, "reasoning_effort": a.effort,'''),
]
for a, b in rep:
    assert s.count(a) == 1, (a[:80], s.count(a))
    s = s.replace(a, b)
p.write_bytes(s.replace("\r\n", "\n").encode("utf-8"))
print("patched")
