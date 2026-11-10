> [!NOTE]
> **AI-assisted report.** Prepared with Claude (Anthropic, Claude Opus 5.5 in Claude Code) on my machine and reviewed by me.
> Every number below is from my runs.

**The same error on AMD (RX 7900 XT, gfx1100, Windows), with stock ISTA files. One more thing that may help: after a
NaN stop, the server can stay broken (1 of 2 cases).** In 1 of the 2 cases I checked, later requests that shared nothing with
the failed one also stopped with NaN, at the same token every time, until the server was restarted.

### After one NaN stop, later requests can fail until a restart

Case 1, all on one server (stock ISTA IQ1_M, experts in VRAM, temperature 0, 256 tokens max; the 3 short prompts are
41-50 tokens and share no prefix with anything before):

| When | Prompts | Result |
|---|---|---|
| Server started, before any NaN | 5 long fresh prompts (19,900-20,362 tokens) | 5 of 5 clean |
| Then: one fresh 19,900-token prompt | - | **NaN stop** at output token 32 |
| Right after, round 1 | Fibonacci / mixture-of-experts / Git tips | **stop at token 16**, clean (141 tokens), **stop at token 88** |
| Round 2, same prompts | same | **stop at token 16**, clean (141 tokens), **stop at token 88** |
| Server restarted, round 1 | same | 235, 163, 256 tokens: **all clean** |
| Round 2 | same | 233, 181, 256 tokens: **all clean** |

So 4 of 6 failed before the restart and 6 of 6 were clean after it. The failing requests stopped at the same output
token in both rounds. These prompts are 41-50 tokens and reuse nothing from the prompt cache (`0 reused` in the
engine log), so something other than the dropped conversation's cache keeps the bad values. My guess (not checked) is
the VRAM expert slots or the drafter's state. On a coding agent this can cost whole tasks: in one coding run the engine
stopped 5 requests of the same task in a row (I did not check whether that run was in this state).

Case 2 (AtomicChat IQ1_M, same engine and settings): one NaN stop on a fresh 19,900-token prompt, then the same 3
short prompts gave 233, 152 and 256 tokens, **all clean, before any restart**. So the broken state does not follow
every stop. So far: 1 of 2. With two cases I cannot say how often it happens.

When it does happen, a failure rate measured on one long-lived server can be too high, because the later failures are
not independent of the first.

### The first stop: random, as in this issue

| Reproducer (stock ISTA IQ1_M, experts in VRAM) | NaN stops |
|---|---|
| `nan_repro.py`: 19,900 fresh tokens (unique first line), 96 out | 1 of 3 |
| `garbage_repro.py`: one opencode turn replayed (20,362 fresh tokens), 600 out | 0 of 3 |

One difference from the reports above: here the first stop came while generating (at output token 32), not while
reading the prompt. On AtomicChat's uncensored IQ1_M (same shards 1-2, different 3-4) the same engine gave 12 stops
across the coding runs, with the same pattern.

Exact text, server log:

```
[strata] the engine reported an error: the model's numbers went non-finite (NaN reached the router), so the answer would be nonsense: the request is stopped and the conversation dropped
```

Engine log, printed once per engine start (later stops do not repeat it):

```
ds4: WARNING: the router met scores that are not numbers (NaN) on CUDA0 - the model's activations went non-finite; its picks are stand-ins and the answer is not reliable
```

### What did and did not help

| Setting (AtomicChat files unless noted) | Result |
|---|---|
| Experts in VRAM, defaults (stock files too) | stops, as above |
| `STRATA_DS4_NO_TC=1` (expert matrix-core kernels off) | still 1 stop in a coding run |
| `STRATA_DS4_NO_TC=1 STRATA_DENSE_PFGEMM=0` | the replay failed 3 of 3 (not fresh) |
| **`--vram-experts 0`** (every expert on the CPU) | **no stop** in 3 fresh replays and 13 coding runs (about 7.5 hours) |

`--vram-experts 0` costs 15% of decode speed (4.13 against 4.85 tok/s) and roughly half of the fresh prompt speed
(83-104 against 155-206 tok/s). That fits this issue's finding that the fault is in the GPU path. Here it happens with a
single card and no layer split.

### Setup

| What | Value |
|---|---|
| PC | RX 7900 XT 20 GB (gfx1100), Ryzen 9 5900X, 64 GB DDR4-3200, Windows 11 26100, Adrenalin 26.9.1, one card, model on a Crucial P3 Plus (QLC NVMe) |
| Strata | Terminal 0.2.12 / Control 0.1.58 |
| Engine | `strata-dsv41` 0.1.58, self-built from `146df3c4` with `tools\dsv41\win\build_hip_win.bat`, `STRATA_HIP_ARCHS=gfx1100`, ROCm 10.2.0a20260930 (TheRock), no source changes; exe SHA-256 `ad1849814d8bf809f1ab2d2b0f516dc62173a667527c7c3756fdfde227b7900e`. It has the #4825 / #5030 dequantizer fix (`0f31e635`, `9d58393d`) |
| Model | ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF IQ1_M at `cb02422c` (all four shards match Strata's pins) + Engram IQ4_NL + Unsloth DSpark Q8_0 |
| Engine line | `--serve --pack <pack> --max-context 65532 --eos 1 --vision off --dspark-conf 0.65 --experts 6 --dspark on --ssd-cache 36`, env `HIP_VISIBLE_DEVICES=0 DS4_CPU_SMT=1 DS4_AHEAD_EXTRA=2` |
| Placement | 868 of 15,744 experts in VRAM (11.15 GB), 14,876 on the CPU lane, prompts in chunks of 15,360, 317 MiB VRAM free |

### Reproducers

The scripts and their result logs are in
[local-model-benchmarks/deepseek-v41-gfx1100](https://github.com/Alextechgamer/local-model-benchmarks/tree/main/deepseek-v41-gfx1100):
`gateH/nan_repro.py`, `gateH/garbage_repro.py` (it replays a captured opencode request from
`coding-bench/runs/_probe/capture4.jsonl` at the repo root), the speed rounds in `gateG/measure.py`, and the stock-file
results in `phase3/stock-nan.log`. To see the persistent failure:
run `nan_repro.py` until one stop, then `measure.py` twice; then restart and run `measure.py` twice again.

### Not tested

- Linux on this card.
- Whether the engine checks for NaN in the expert slots or the drafter's state after a dropped conversation. I only saw
  that a restart clears it.
- Engine 0.1.59. Between `146df3c4` and 0.2.13 the only `src/dsv41` change is `cf0161bf` (build targets), so I expect
  the same result, but I did not run it.
