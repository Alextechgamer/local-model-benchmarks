"""Phase 1 for Model B (llama.cpp): run named arms in order. Each arm = build + extra args + env.

usage: python p1b.py <stage> [--smoke-all]
Stages are defined below; each arm runs arm.py (1 warmup + 3 timed runs of the 16K prompt, 512 output tokens).
"""
import os, subprocess, sys, pathlib

B = pathlib.Path(r"E:\strata-tests\coding-bench")
T = B / "tools"
MODEL = r"C:\models\qwen38\Qwen\Qwen3.8-27B\Qwen3.8-27B-IQ4_XS.gguf"
STRATA_ROCM = r"C:\Users\user\Strata\engine\rocm\bin"
BUILDS = {
    "vk10752": (r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe\llama-server.exe", []),
    "vk11748": (str(T / "llama-b11748-vulkan-x64" / "llama-server.exe"), []),
    "rocm11748": (str(T / "llama-b11748-rocm-10.0-x64" / "llama-server.exe"),
                  ["HIP_VISIBLE_DEVICES=0", f"PATH={T / 'llama-b11748-rocm-10.0-x64'};{STRATA_ROCM};" + os.environ["PATH"]]),
    "lemonade1350": (str(T / "lemonade-b1350-gfx110X" / "llama-server.exe"), ["HIP_VISIBLE_DEVICES=0"]),
    "bee048": (str(T / "beellama-v0.4.8-vulkan" / "llama-server.exe"), []),
}
SAMPLING = ["--temp", "1.0", "--top-k", "20", "--top-p", "0.95", "--min-p", "0", "--presence-penalty", "0",
            "--repeat-penalty", "1.0"]
THINK = ["--reasoning-format", "deepseek", "--reasoning-budget", "8192", "--reasoning-effort", "medium"]


def base(ctx=98304, kv="q4_0", b=2048, ub=512, spec=("--spec-type", "draft-mtp", "--spec-draft-n-max", "3")):
    return (["-m", MODEL, "-ngl", "99", "-c", str(ctx), "-np", "1", "-fa", "on", "-ctk", kv, "-ctv", kv,
             "-b", str(b), "-ub", str(ub), "-fit", "off", "--host", "127.0.0.1", "--port", "8090"]
            + list(spec) + SAMPLING + THINK)


def arm(tag, build, args, env=(), smoke=False):
    exe, benv = BUILDS[build]
    cmd = [sys.executable, str(T / "arm.py"), "--tag", f"B-{tag}", "--port", "8090",
           "--mem-csv", str(B / "power" / "p1-b-mem.csv"), "--need-gb", "8"]
    for e in list(benv) + list(env):
        cmd += ["--env", e]
    if smoke:
        cmd.append("--smoke")
    cmd += ["--", exe] + args
    print(">>>", tag, flush=True)
    return subprocess.run(cmd).returncode


stage = sys.argv[1]
smoke_all = "--smoke-all" in sys.argv
if stage == "backend":
    for b in ["vk10752", "vk11748", "rocm11748", "lemonade1350", "bee048"]:
        arm(f"backend-{b}", b, base(), smoke=smoke_all)
elif stage == "rocmfit":
    # ROCm builds spilled ~0.9 GB at 98K (bigger compute buffers); re-test where they fit, with Vulkan at the same ctx
    for b in ["rocm11748", "lemonade1350", "vk11748"]:
        arm(f"backend65k-{b}", b, base(ctx=65536))
elif stage == "kv":
    arm("kv-q8_0", "vk11748", base(kv="q8_0"), smoke=True)
elif stage == "ub":
    arm("ub-1024", "vk11748", base(b=2048, ub=1024))
    arm("ub-2048", "vk11748", base(b=2048, ub=2048))
elif stage == "mtp":
    arm("mtp-none", "vk11748", base(spec=()))
    arm("mtp-n2", "vk11748", base(spec=("--spec-type", "draft-mtp", "--spec-draft-n-max", "2")))
    arm("mtp-n3-prob", "vk11748", base(spec=("--spec-type", "draft-mtp", "--spec-draft-n-max", "3",
                                           "--spec-draft-sampling", "probabilistic")), smoke=True)
    arm("mtp-n3-nommvq", "vk11748", base(), env=["GGML_VK_DISABLE_MMVQ=1"], smoke=True)
    arm("mtp-n3-ngram", "vk11748", base(spec=("--spec-type", "draft-mtp,ngram-mod", "--spec-draft-n-max", "3")),
        smoke=True)
elif stage == "rocm2":
    # the same knobs on the official ROCm build, at a context where it does not spill
    # 98304 with -ub 256 is the largest ctx that fits ROCm without spill (fit-probe.jsonl); q8_0 KV does not fit there
    R = "rocm11748"; C = 98304; U = 256
    PROB = ("--spec-type", "draft-mtp", "--spec-draft-n-max", "3", "--spec-draft-sampling", "probabilistic")
    arm("rocm98k-ub256-n3", R, base(ctx=C, ub=U), smoke=True)
    arm("rocm98k-ub256-n3-prob", R, base(ctx=C, ub=U, spec=PROB), smoke=True)
    arm("rocm98k-ub256-n2", R, base(ctx=C, ub=U, spec=("--spec-type", "draft-mtp", "--spec-draft-n-max", "2")))
    arm("rocm98k-ub256-none", R, base(ctx=C, ub=U, spec=()))
    arm("rocm98k-ub256-n3-prob-graphsoff", R, base(ctx=C, ub=U, spec=PROB), env=["GGML_CUDA_DISABLE_GRAPHS=1"])
    arm("lemonade98k-ub256-n3-prob", "lemonade1350", base(ctx=C, ub=U, spec=PROB), smoke=True)
elif stage == "vkfinal":
    # Vulkan's best at its largest clean ctx, to compare with ROCm's best
    arm("vk114k-ub512-n3-prob", "vk11748", base(ctx=114688, spec=("--spec-type", "draft-mtp", "--spec-draft-n-max", "3",
                                                                  "--spec-draft-sampling", "probabilistic")), smoke=True)
else:
    sys.exit(f"unknown stage {stage}")
