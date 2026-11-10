"""Model A Phase 1 stages as plain lists (no shell quoting). usage: python p1a_stage.py <stage>"""
import subprocess, sys, pathlib

T = pathlib.Path(r"E:\strata-tests\coding-bench\tools")
R = ["--set-arg", "--vram-reserve-mib", "1792"]          # auto cache, more VRAM left free (base for stage 2)
STAGES = {
    "s2": [
        ("v045-r1792", "A-v045-base", R + ["--smoke"]),
        ("v045-r1792-notable", "A-v045-notable", R),
        ("v045-r1792-kvq4", "A-v045-base", R + ["--set-arg", "--kv", "q4_0", "--smoke"]),
        ("v045-r1792-pf16k", "A-v045-base", R + ["--set-arg", "--prefill", "auto:16384"]),
        ("v045-r1792-minp07", "A-v045-base", R + ["--set-arg", "--spec-min-p", "0.7", "--smoke"]),
        ("v045-r1792-adaptasync", "A-v045-base", R + ["--set-arg", "--adapt-async", "1", "--smoke"]),
        ("v045-r1792-cpushare", "A-v045-base", R + ["--env", "STRATA_PREFILL_CPU_SHARE=auto", "--smoke"]),
        ("v045-r1792-coupled", "A-v045-base", R + ["--add-flag=--coupled-draft", "--smoke"]),
    ],
    # short prompts (a tool result) decide the CPU prompt share; 16K-chunk prefill rechecked with it
    "s3": [
        ("v045-r1792-short", "A-v045-base", R + ["--tune-prompt", str(T / "prompt-900.txt")]),
        ("v045-r1792-cpushare-short", "A-v045-base", R + ["--env", "STRATA_PREFILL_CPU_SHARE=auto",
                                                          "--tune-prompt", str(T / "prompt-900.txt")]),
    ],
}
for tag, base, extra in STAGES[sys.argv[1]]:
    if len(sys.argv) > 2 and tag not in sys.argv[2:]:
        continue
    print(">>> arm", tag, extra, flush=True)
    subprocess.run([sys.executable, str(T / "p1a.py"), tag, base] + extra)
