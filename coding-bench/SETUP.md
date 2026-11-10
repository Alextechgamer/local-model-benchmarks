# Setup for the local coding benchmark (Phase 0)

PC: AMD Radeon RX 7900 XT 20 GB (gfx1100, RDNA3, Resizable BAR on, per the user), Ryzen 9 5900X (12 cores / 24 threads,
no AVX-512), 64 GB DDR4, PCIe 4.0, Windows 11 Pro 26100, Adrenalin driver 32.0.31041.1004. Written 2026-10-19.

This file lists the settings chosen **before** tuning, the source of each, and what was rejected. Phase 1 A/Bs the
settings that matter most on this PC; its results are in `results/tuning.json`, and the final locked settings are in
`configs/` and at the end of this file.

## How things are measured (same for both models)

| What | How | Source / check |
|---|---|---|
| GPU energy | `python E:\strata-tests\gpu_power.py log <csv> 2`. Sensor 73 is board power in watts: unnamed in the script, so identified here. It reads ~24–75 W idle (depending on the memory clock) and 308–333 W under full llama-bench load, which matches the 7900 XT's ~300 W board power | measured 2026-10-19, `logs/sensor-check/` |
| CPU energy | `typeperf "\Energy Meter(rapl_package0_pkg)\Power" -si 2` (mW), the same counter as `E:\strata-tests\power\cpu.csv` | earlier runs |
| VRAM / RAM | `tools/mem_log.ps1`: `\GPU Adapter Memory(*)\Dedicated Usage` and `Shared Usage`, available RAM, and the server process's working set, every ~1 s. Shared Usage is the spill detector (C:\models\qwen38\HauhauCS\Qwen3.8-27B\HANDOFF.md) | |
| Speed | `tools/bench_client.py`: one streaming `/v1/chat/completions`. TTFT = first streamed token (reasoning or content). Prompt tok/s = prompt tokens / TTFT. Output tok/s = (tokens − 1) / (end − first token). The server's own `timings` are saved too | |
| No cache reuse in timing tests | each repeat starts with a unique `[request id …]` line, and `cache_prompt: false` is sent. llama.cpp honours `cache_prompt: false` per request (tools/server/README.md). Strata has no per-request key; only a unique line at the very start avoids its checkpoints (Strata docs/DETAILS.md:634-637). Check: `timings.cache_n` = 0. One warm-up request after each load is discarded | |
| Tuning prompt | `tools/prompt-16k.txt`: 16,050 tokens (Qwen3.8 tokenizer) of real Python (Strata's `serve/*.py`) plus a request for a long review; `max_tokens` 512 | |

## Model A: Qwen3.8-Flash-Next Coder IQ1_M on Strata

**The model.** It is not an official Qwen model. It is ISTA-DASLab's pruned coder variant of Qwen3.8-Flash-Next (half
of the 512 experts removed, "targeted at code"; https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-Coder-GGUF).
ISTA's card gives SWE-bench Verified 79.2 against 82.8 for the BF16 base. It gives no settings, so sampling, thinking
and context follow the base card, https://huggingface.co/Qwen/Qwen3.8-Flash-Next.

**Engine version.** The installed engine is 0.1.39 (`C:\Users\user\Strata\engine\BUILD.json`, prebuilt, ROCm
10.2.0a20260930, hipBLASLt 100500). The latest stable release is 0.1.45 (2026-10-17). With the user's OK, 0.1.45 is
tested **side by side**:
- source: a separate git worktree at `tools/strata-v0.1.45` (tag v0.1.45);
- engine: the release's `strata-windows-x64-hip.zip`, SHA-256 checked;
- the user's repo folder is unchanged.

Phase 1 compares 0.1.39 with 0.1.45 and locks the faster one that passes the correctness checks.

| Setting | Chosen start value | Source | A/B in Phase 1 |
|---|---|---|---|
| Backend | HIP (the only AMD backend Strata has on Windows) | docs/AMD_HIP.md | engine 0.1.39 vs 0.1.45 |
| hipBLASLt table | 0.1.45: `STRATA_HIPBLASLT_TUNING=tools/hip/gfx1100-hipblaslt-100500.txt` | 0.1.40 notes: "hipBLASLt tables for gfx1100 (#766, #755, #565)"; PR #755: 131K prompt "1.82x"; issue/PR #2933, Windows 7900 XTX: 1,568–1,631 tok/s prompt vs 740–790 measured here on 0.1.39 without a table | with vs without (on 0.1.45). Check `STRATA_HIPBLASLT_VERBOSE=1` for `fallbacks=0` (docs/AMD_HIP.md:439-445: calibrated on ROCm 10.2.0a20261003) |
| KV cache | `--kv int8` | DETAILS.md:76-78: q4_0 costs "perplexity +8-12%" | int8 vs q4_0 (0.1.45 changed the q4_0 + streaming + MTP path, #2403). k8v4 rejected: help says "not with --kv-resident" |
| KV streaming | `--kv-resident 32768` | help: keep N cells in VRAM (min 20480); 0.1.39 log here: 97.5–99.6% of KV block reads hit VRAM | none (it measured well) |
| Max context | `--max-context 262144`, no YaRN | trained context 262,144 (base card; log line "against a trained context of 262144"). The base card says YaRN may hurt "performance on shorter texts" | Phase 4 tries 200K and 256K |
| VRAM reserve | `--vram-reserve-mib 1024` | the 0.1.39 log here warned 4 times: "LOW: requests may stall; add --vram-reserve-mib ~1000" with 163–505 MiB free; 0.1.40.3 notes (#1376): RX 7900 XT decode halved at ~300 MiB free | none |
| Expert cache | fixed slot count, so every A/B arm and the benchmark itself get the same cache (`auto` varied 4,848–6,157 slots between starts here) | 0.1.39 log; PR #826 held slots constant | value from the first start's auto size on each engine, minus a margin |
| Prompt chunk | `--prefill auto` | 0.1.42 notes: on Windows AMD a bare `auto` stops at 6,144 (8,192 crashed a 7900 XTX with 0xC0000409); 0.1.45 notes: bigger default chunk "4096 / 2048 / 1024, whatever fits" | `auto` vs `auto:16384`. Open issue #3170: silent engine death with `auto:32768` at 204,800 context on 0.1.45, so `auto:32768` is rejected |
| CPU prompt share | off | 0.1.40.2 notes: `STRATA_PREFILL_CPU_SHARE=auto` "short prompts 19-35% faster" (opt-in); issue #2329, RX 7900 XT, Windows: "872 tokens 327 -> 529 tok/s" | on vs off |
| Speculative / MTP | `--spec 4 --spec-min-p 0.5 --mtp <Strata-data\mtp\rt>` | PR #826: 43.4 → 62.9 tok/s on gfx1201 | `--spec-min-p 0.7` (PR #1297, issues #1831/#2523 on a 7900 XTX: about +4–10%); `--adapt-async 1` (#2523: +6.2%, 0.1.44+ only). `--spec 3` rejected: −3.8% in #2523 |
| `STRATA_SH_STREAM` | `0` (off) | 0.1.40 notes: "the shared-expert stream fork is off by default on AMD, which brings decode back to 0.1.38 speed (#826, #816)"; 0.1.45 notes: `=1` is "0.44x decode" on gfx1201 | none |
| Route tail skip | off | 0.1.42 notes: `STRATA_ROUTE_TAIL_SKIP=7` changes answers (KL 0.056 → 0.086) | rejected: it trades quality for speed |
| Threads | default (every physical core but one) | engine help | none |
| Batching | off (one request at a time) | docs/BATCHING.md:48-53: only where the cache holds ≥ half of the experts; here it holds ~47% | none |
| Prompt cache | on (default) for the coding test; timing tests use the nonce instead | DETAILS.md:634-644 | none |
| `HIP_VISIBLE_DEVICES` | `0` in the config's `env` | the user environment sets `HIP_VISIBLE_DEVICES=-1`, which hides the GPU from HIP programs; the config's `env` overrides it per process | none |

## Model B: Qwen3.8-27B IQ4_XS on llama.cpp

**The model.** https://huggingface.co/Qwen/Qwen3.8-27B. The file is bartowski's IQ4_XS
(https://huggingface.co/bartowski/Qwen3.8-27B-GGUF), 14.4 GiB, marked "recommended", with the MTP layer stored at Q4_0.
- The GGUF reports `qwen35` architecture, 65 blocks (64 + 1 MTP layer), full attention every 4th layer, context 262,144.
- Qwen's own coding numbers (base card): SWE-bench Pro 61.7, LiveCodeBench v6 90.3.

**Earlier tuning on this PC** (C:\models\qwen38\HauhauCS\Qwen3.8-27B\HANDOFF.md, build 10752, Vulkan):
- q4_0 KV at 160K with embedded MTP n=3 was fastest and fit without spill: ~62 tok/s short, ~50 tok/s at 48K.
- 160K is the VRAM ceiling.
- MTP n ≥ 4 was much slower on Vulkan.

| Setting | Chosen start value | Source | A/B in Phase 1 |
|---|---|---|---|
| Backend / build | Vulkan, latest release b11748 | issue #27761 (7900 XTX, Windows): ROCm faster on short prompts (pp512 954 vs 771), Vulkan faster at 80K (572 vs 462) and in decode | 5 arms: winget b10752 Vulkan; b11748 Vulkan; b11748 official ROCm 10.0; Lemonade ROCm nightly b1350 (gfx110X, runtime bundled); BeeLlama v0.4.8 Vulkan. Issue #29410 (open): on Windows + AMD driver, int8 coopmat (#27952) regressed MTP n=3 at 48K from 55.8 to 25.8 on a 7800 XT, so old vs new is a real question |
| Official ROCm zip | runs only with `HIP_VISIBLE_DEVICES=0` and Strata's ROCm `bin` (hipblas/rocblas) on PATH | release.yml: rocBLAS/hipBLASLt "are not copied"; #26964 (open); checked here: `--list-devices` showed "(none)" until both were set | runtime mix (ROCm 10.0 build, 10.2 libraries) is noted as a caveat |
| GPU layers | `-ngl 99` (all) | the model fits in 20 GB | none |
| Context | `-c 163840` | HANDOFF.md: 160K is the ceiling with q4_0 KV (dedicated ~20 GB, shared ≤ 715 MB) | Phase 4 measures the largest that fits for the locked build; BeeLlama's KVarN cache may go higher |
| KV cache | `-ctk q4_0 -ctv q4_0` | HANDOFF.md: q4_0 beat q8_0 on speed at every length here. ROCm keeps flash attention on the GPU only for matched pairs q4_0/q4_0 and q8_0/q8_0 (`GGML_CUDA_FA_QUANTS` default; #27761: mixed pairs split the graph, pp −68%). llama.cpp docs/function-calling.md warns: "Beware of extreme KV quantizations (e.g. `-ctk q4_0`), they can substantially degrade the model's tool calling performance" | q4_0 vs q8_0 at the same `-c`; the tool-call smoke test decides if q4_0 is safe |
| Flash attention | `-fa on` | needed for quantized KV | none |
| Fit | `-fit off` | b11748 `-fit` is on by default and changes unset settings | none |
| Batch | `-b 2048 -ub 512` (defaults) | tools/server/README.md; #28752: larger `-ub` did not help on AMD | `-ub 512 / 1024 / 2048` |
| Speculative | `--spec-type draft-mtp --spec-draft-n-max 3` (embedded MTP layer, no draft file) | bartowski card: "add `--spec-type draft-mtp`"; HANDOFF.md: n=3 best here (2.1x). Neither Qwen card gives a depth | none vs n=2 vs n=3; `--spec-draft-sampling probabilistic` (#27694); `GGML_VK_DISABLE_MMVQ=1` (#25666/#29410); `draft-mtp,ngram-mod` |
| Parallel | `-np 1` | single user | none |
| Threads | default | GPU-only run | none |
| Prompt cache | on (default) for the coding test; `cache_prompt: false` plus the nonce for timing tests | README | none |

## Sampling, thinking and template (both models)

| Setting | Value | Source |
|---|---|---|
| Sampling (thinking mode) | temperature 1.0, top_p 0.95, top_k 20, min_p 0, presence_penalty 0, repetition_penalty 1.0 | both official cards: "Thinking Mode: temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=0.0, repetition_penalty=1.0". The old Strata config used 0.7, Qwen's value for non-thinking mode, so it is changed |
| Thinking | on (the default), with the template's default effort | cards: thinking is on by default. The local template injects text only for `xhigh` and `low`; `medium` adds nothing. llama.cpp gets `--reasoning-effort medium`, the effort the earlier handoff picked for coding; Strata gets the same through its config |
| Thinking budget | 8,192 tokens for both | no official budget exists (neither card gives one). The old Strata config's 6,000 was hit by many replies in its log, so it is raised; the same cap is used on both models for a fair test. llama.cpp: `--reasoning-budget 8192`; Strata: `reasoning_budget_tokens: 8192` |
| Max output | opencode asks up to 32,768 per turn | opencode provider config from the earlier runs (`E:\strata-tests\oc-27b\opencode.json`) |
| Chat template / tools | the template inside each model (Qwen3-Coder XML tool calls: `<tool_call><function=…><parameter=…>`) | llama.cpp detects it as "Qwen3-Coder" (`common/chat.cpp`), `--jinja` is on by default in b11748. Strata loads the pack's `tokenizer/chat_template.jinja` and parses calls in `serve/frontend.py` |
| Reasoning output | llama.cpp `--reasoning-format deepseek` (thinking in `reasoning_content`) | tools/server/README.md |

## Rejected, and why

- **achyudh/llama.cpp, adaptive KV streaming** (the user asked).
  - Its paged decode and prefill kernels stop with `if (!GGML_CUDA_CC_IS_RDNA4(...)) return false;`, so on gfx1100 `--kv-stream` falls back to an untested gather path.
  - It targets ROCm 7.2.3 on Linux, and Windows would need the HIP SDK, which isn't installed.
  - Its MTP rejection sampling and n-gram stacking already exist upstream (#27694, comma-separated `--spec-type`), so those ideas are in the A/B anyway.
- **RaymondHuang adaptive KV streaming:** CUDA only.
- **stew675 RDNA boosts:** Linux HIP build from source; "+5.2% … 2-GPU … flat on one card".
- **ik_llama.cpp:** its README says "do not enter issues related to ROCm, Vulkan".
- **HauhauCS FastMTP sidecar:** tested here before; slower at 48K (45.2 vs 52.4 tok/s, 54% vs 76% acceptance; HANDOFF.md).
- **koboldcpp-rocm:** last release predates Qwen3.8 MTP.
- **DFlash2 drafter for the 27B:** costs 1.1–2 GB VRAM, which lowers the 160K ceiling. One maintainer says DFlash2 and MTP "look about the same within a few percent".
- **froggeric fixed chat template:** kept in reserve. It is used only if the stock template fails the tool-call smoke test (the user's choice).
- **Strata `STRATA_ROUTE_TAIL_SKIP`, `--kv k8v4`, `--spec 3`, `auto:32768`:** see the Model A table.
- **Strata 0.2.0-beta:** its notes say the packaged AMD engines "do not carry the hipBLASLt tuning tables yet" and "the maintainers have not run them on an RX 7000"; 0.1.45 is the newer stable release.
- **YaRN beyond 262K:** both cards warn it can hurt shorter texts.
- **`HSA_OVERRIDE_GFX_VERSION`:** "not supported on Windows".
- **Changing the user's `HIP_VISIBLE_DEVICES=-1`:** not done; each server sets `0` for its own process.

## Final locked settings (Phase 1, 2026-10-20)

Medians of 3 runs on the 16,050-token prompt with 512 output tokens. All arms, smoke scores and server commands are in
`results/tuning.json`. Output tok/s varies by about ±8% between runs with identical settings, because sampling at
temperature 1.0 changes how many drafted tokens are accepted, so smaller differences are not counted.

### Model A: `configs/model-a.json`, start with `configs/model-a-start.ps1`

| | Old default (engine 0.1.39) | Locked (engine 0.1.45) | Change |
|---|---|---|---|
| Time to first token | 21.4 s | 9.96 s | −53% |
| Prompt tok/s | 754 | 1,621 | 2.15x |
| Output tok/s | 67.8 | 68.2 | flat |
| Peak VRAM (dedicated) | 19.4 GB | 18.8 GB | 0.7 GB more headroom |

Locked settings, each on top of the starting values above:
- **Engine 0.1.45, plus the gfx1100 hipBLASLt table** (`STRATA_HIPBLASLT_TUNING`). The table alone doubles prompt speed: 0.1.45 without it reads 739 tok/s, the same as 0.1.39.
- **`--expert-cache auto` with `--vram-reserve-mib 1792`** instead of 1024. Speed is unchanged and peak VRAM drops from 19.5 to 18.7 GB.
  - Reason: other programs' idle VRAM use moved between 1.7 and 2.4 GB during the runs, and with the 1024 reserve the engine itself warned that only 650 MiB was free.
  - `--expert-cache 5000` is not a slot count. The engine made 6,511 slots and left 0 MiB free, which was slower (1,238 / 57.9).
- **`--prefill auto:16384`:** prompts 1,497 → 1,617 tok/s.
  - Checked against the crash reports with a 120,126-token prompt: 83.4 s to first token, 1,441 tok/s, no crash.
- **`STRATA_PREFILL_CPU_SHARE=auto`:** a 898-token prompt (an agent's tool result) goes from 1.77 to 1.49 s to first token (536 → 636 tok/s). No change on the 16K prompt.
- **Kept from the starting values:** `--kv int8`, `--spec 4 --spec-min-p 0.5`, `--kv-resident 32768`, `--max-context 262144`.

Rejected in Phase 1:

| Option | Measured | Why rejected |
|---|---|---|
| `--kv q4_0` | output 63.2 | slower, and lower quality per the docs |
| `--spec-min-p 0.7` | output 68.3 | no gain |
| `--adapt-async 1` | output 64.1 | slower |
| `--coupled-draft` | output 63.7 | slower |

Smoke test on the locked config (`A-v045-final`): tool call, typed arguments, tool result and code each passed 3 of 3.

### Model B: `configs/model-b.json`, start with `configs/model-b-start.ps1`

| | Old default (winget b10752, greedy MTP n=3, same 98K context) | Locked | Change |
|---|---|---|---|
| Time to first token | 33.0 s | 26.9 s | −18% |
| Prompt tok/s | 488 | 598 | +23% |
| Output tok/s | 53.7 | 65.5 | +22% |

The old `run.ps1` default of 163,840 context no longer fits. Other programs now hold about 1.7 GB of VRAM (0.9 GB in the earlier session), so it spilled 1.6 GB into shared memory and read the 16K prompt at about 45 tok/s. That run was aborted and its log kept.

Locked settings:
- **llama.cpp b11748, Vulkan.**
- **`-c 98304`:** the largest context with about 0.7 GB headroom for other programs' VRAM swings. The fit probe found 114,688 as the absolute limit (0.34 GB spill), and 131,072 spills 0.85 GB.
- **q4_0 KV, `-fa on`, `-b 2048 -ub 512`.**
- **`--spec-type draft-mtp --spec-draft-n-max 3 --spec-draft-sampling probabilistic`.**
- **Qwen thinking sampling and `--reasoning-budget 8192`.**

Smoke test version 2 on the locked config: 3 of 3 on all four checks.

Rejected in Phase 1, all measured at 98K unless noted:
- **Backends:**
  - **Official ROCm b11748 and Lemonade ROCm b1350:** at 65K, where they fit, prompts were 795 tok/s, against 596 for Vulkan at 65K. But their compute buffers take 1–1.4 GB more VRAM, and their speed collapses as soon as they spill.
    - At 98K: 230 and 410 prompt tok/s.
    - At 98K with `-ub 256`: 754 in one fit probe, then 248 in the full arm, once other programs' VRAM grew by 0.15 GB.
    - Not safe with this desktop's changing VRAM use.
  - **BeeLlama 0.4.8:** the same speed as b11748 (586 / 58.8) with 0.5 GB more VRAM.
  - **b10752:** slower (488 / 53.7).
- **`-ctk/-ctv q8_0`:** output 36.4, 1.5 GB spill.
- **`-ub 1024`:** +3% prompt, +0.3 GB VRAM.
- **`-ub 2048`:** spilled 2.2 GB; prompts 246 tok/s.
- **MTP off:** output 36.0, so MTP gives 1.8x.
- **MTP n=2:** 59.6.
- **`GGML_VK_DISABLE_MMVQ=1`:** 50.1.
- **`draft-mtp,ngram-mod`:** 39.9 on this non-repetitive prompt.

### Both

- **Thinking:** every request in the benchmark sends `reasoning_effort: "medium"`. Strata 0.1.39 has no config key for a default effort, so the request carries it on both models.
- **Thinking budget:** 8,192 tokens on both.
- **Smoke test change:** version 1 of the coding check failed Model A's answers only because they sorted the caller's list in place, which the prompt had not forbidden. Version 2 says "Do not modify the input list", and both locked configs pass it 3 of 3.
