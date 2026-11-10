# DeepSeek-V4.1-Flash (uncensored, 1.75 bpw) on one RX 7900 XT: the coding suite

Measured 2026-11-08 and 2026-11-09 on one PC: RX 7900 XT 20 GB (gfx1100), Ryzen 9 5900X, 64 GB DDR4-3200, Windows 11
26100, Adrenalin 26.9.1, model files on E: (Crucial P3 Plus, QLC NVMe). One rep per task.

**Result.** With every expert on the CPU (see "The NaN fault" for why), the model solved 4 of the 6 coding tasks. The other
two (T2, T6) ran out of the 45-minute limit. Every task it finished, it solved. It is 4 to 16 times slower than
Qwen3.8-Flash-Next Coder on the same PC, at 3.1-4.2 tokens a second.

## The build (reproducible)

| What | Value |
|---|---|
| Source | Niko1221/Strata v0.2.12, commit `146df3c468739147f520ac3816de806f71232571` |
| Build script | `tools\dsv41\win\build_hip_win.bat` with `STRATA_HIP_ARCHS=gfx1100` |
| CMake options (from the script) | `-G Ninja -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_HIP=ON -DSTRATA_ENABLE_CUDA=OFF -DSTRATA_BUILD_TESTS=OFF -DSTRATA_BUILD_DSV41=ON -DSTRATA_NATIVE_EXPERTS=ON -DSTRATA_PORTABLE=ON -DCMAKE_HIP_ARCHITECTURES=gfx1100` |
| Toolchain | ROCm 10.2.0a20260930 (TheRock nightly wheels: `rocm[devel,device-gfx1100,libraries]==10.2.0a20260930`), AMD clang 24.0.0git, MSVC 14.44.35207, Windows SDK 10.0.26100, CMake 4.4.3, Ninja 1.13.2 |
| Runtime DLLs | `rocm\` and the HIP DLLs copied from Strata's signed engine 0.1.58-windows-x86_64-hip-rdna3 |
| Engine | `strata-dsv41.exe` 0.1.58, SHA-256 `ad1849814d8bf809f1ab2d2b0f516dc62173a667527c7c3756fdfde227b7900e` |
| Package | `strata-dsv41-0.1.58-windows-x86_64-hip-gfx1100-self.tar.gz`, SHA-256 `e95f2694723aa97e11e259b57b6f4c0f9440aa25b16d8757f6b9518fe59bbac9` (unsigned; Strata Terminal 0.2.12 ran it through `STRATA_DSV41_EXE` without an error) |
| Kernels disabled | None in the build. At run time: none (Gate G); see "The NaN fault" for what the switches did |
| Files | `build/`: configure log, build log (gzip), BUILD.json, SHA256SUMS, both engine configs |

**Model:** AtomicChat/DeepSeek-V4.1-Flash-1017-Uncensored-GSQ-RCO-GGUF IQ1_M (4 shards) + ISTA-DASLab Engram IQ4_NL +
Unsloth DSpark Q8_0 drafter, all SHA-256 checked against the Hub. Shards 3 and 4 differ from Strata's pins (they are the
uncensored ones); Strata used them as they are.

**Engine line used for the coding runs** (Strata wrote it from the launch flags; environment `HIP_VISIBLE_DEVICES=0
DS4_CPU_SMT=1 DS4_AHEAD_EXTRA=2`):

```
strata-dsv41 --serve --pack <pack> --max-context 65532 --eos 1 --vision off --dspark-conf 0.65 --dspark on
             --ssd-cache 36 --vram-experts 0 --experts 6        (the 5-expert follow-up: --experts 5)
```

Launch: `strata launch --model-path <models> --model ist-das-1.75bpw --family deepseek41 --context 65532 --vision off
--full-quality --tune skip --access local --port 8091 --set dspark=on --set ssd-cache=36 --set vram-experts=0 --yes --no-tui`
(`--speed faster` instead of `--full-quality` for 5 experts).

## Gate G: speed (see gateG/GATE-G.md)

Config 2 (6 experts, DSpark on, 36 GB RAM cache, experts on the card where they fit): 5.45 tok/s decode, 8,227-token
prompt at 141.5 tok/s. That config turned out to have the NaN fault below. With every expert on the CPU: 4.13 tok/s.

## The NaN fault

On the first coding run the engine stopped 12 requests with: `the engine reported an error: the model's numbers went
non-finite (NaN reached the router), so the answer would be nonsense: the request is stopped and the conversation dropped`.
Once it gave garbage without that error (T2: mixed Chinese and Japanese words, broken tool-call markup, HTML closing tags).
`gateH/garbage_repro.py` replays T2's third turn exactly (20,354 tokens) and triggers it every time:

| Setting | T2 replay | Decode (short prompts) | Prompt read |
|---|---|---|---|
| Experts on the card, matrix cores on (Gate G config 2) | (T2 lost to 5 NaN stops in a coding run) | 5.45 tok/s | ~168 tok/s |
| `STRATA_DS4_NO_TC=1` | (1 NaN stop in T1) | 4.30 tok/s | 170-196 tok/s |
| `STRATA_DS4_NO_TC=1 STRATA_DENSE_PFGEMM=0` | 3 of 3 NaN | 4.56 tok/s | 169 tok/s |
| **Matrix cores on, `--vram-experts 0` (all experts on the CPU)** | **0 of 3, all three read fresh** | 4.13 tok/s | 83-104 tok/s |

So the matrix cores are not the cause. The fault is in the engine's expert path on the graphics card on gfx1100. The
engine has no "fewer layers on the card" setting, so that remedy could not be tried. The coding results below are with
every expert on the CPU unless the run is labelled `C-gpu`, and none of those runs had a NaN stop. Phase 3 (below) showed
that ISTA-DASLab's stock files hit the fault too: it is the engine, not the uncensored shards.

## Gate H: the coding suite

Harness: `coding-bench`, the same tasks, hidden tests and opencode 1.19.3 setup as the Qwen runs (`--pure`, README on
stdin, 7 core tools, `reasoningEffort: medium`, 45 minutes and 150 steps per run). Differences, all forced by this
model or server:

- Context 65,532 tokens (the Qwen runs: 262,144). opencode's output limit is 16,384 (Qwen: 32,768) so that it keeps
  about 49K for the input; the server also shortens `max_tokens` to the room left.
- Thinking: `reasoningEffort: medium` reaches DeepSeek's template as "medium". Strata caps a turn's thinking at 12,288
  tokens (75% of 16,384); the Qwen runs had a budget of 8,192.
- Every task runs in one folder (`E:\strata-dsv41\gateH\live\work`) so that opencode's system prompt, which ends with the
  working folder and the date, is the same in every task and Strata's prefix cache serves it. The folder is moved into
  the run folder before scoring.
- TTFT is the engine's own prompt time per turn (from its log). "First" is the first coding turn (opencode's short title
  request is left out); "median" is over the coding turns.
- Flags. *False success*: the last message claims the work is done or the tests pass while the hidden score is below 1.
  *Over-engineering*: more than 2x the lines the reference solution changes, or (T1-T5) changes to the visible tests.

### Run 1: opencode's default prompt, 6 experts

| Task | Result | Hidden tests | Wall | TTFT first / median | Prompt tokens (cached / fresh) | Output tokens | Decode | E: read | Lines changed (reference) | Over-eng. | False success |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 fix 3 bugs | pass | 25/25 | 8.8 min | 0.4 s / 6.5 s | 54,671 (47,666 / 7,005) | 1,138 | 3.07 tok/s | 468 GB | 5 (5) | no | no |
| T2 multi-currency | **DNF** (45 min) | 24/28 at the stop | 45.0 min | 0.6 s / 9.1 s | 364,516 (343,673 / 20,843) | 10,000 | 4.22 tok/s | 2,581 GB | 123 (104) | no | no |
| T3 refactor | pass | 25/25 | 28.4 min | 45.1 s / 45.0 s | 90,613 (76,437 / 14,176) | 4,372 | 3.99 tok/s | 1,645 GB | 103 (91) | no | no |
| T4 from docstring | pass | 28/28 | 20.6 min | 30.5 s / 22.5 s | 149,013 (141,087 / 7,926) | 3,608 | 3.81 tok/s | 1,202 GB | 39 (26) | yes: added 39 test lines | no |
| T5 bug report | pass | 21/21 | 25.0 min | 59.7 s / 25.3 s | 236,059 (220,926 / 15,133) | 3,973 | 3.80 tok/s | 1,409 GB | 2 (2) | yes: added 11 test lines | no |
| T6 write tests | **DNF** (45 min) | 0/10 mutants (no test file yet) | 45.0 min | 33.7 s / 54.6 s | 57,047 (43,888 / 13,159) | 9,940 | 4.08 tok/s | 2,531 GB | 0 (0) | no | no |

- 4 of 6 solved; mean score 0.81; total 172.8 minutes. No NaN stops.
- T4's and T5's flags come from new tests the model added; it changed no existing test line.
- T6: the last turn thought for 8,747 tokens (about 36 minutes) and was writing the test file when the limit came.
- 77-95% of every task's prompt tokens came from Strata's prefix cache. E: was read at about 1 GB/s throughout.

Against Qwen3.8-Flash-Next Coder IQ1_M on Strata 0.1.45, same PC and harness (`results/coding.json`, median of 2 reps):
T1 52.5 s, T2 447.7 s, T3 87.5 s, T4 77.5 s, T5 85.0 s, T6 395.1 s; 11 of 12 solved, mean score 0.997.

### Run 2: the smallest-change prompt appended (T1, T3, T4, T5; the two DNFs are skipped)

Prompt: `bench/prompts/smallest-fix.txt`, added to opencode's system prompt through `instructions`.

| Task | Result | Hidden tests | Wall (Run 1) | TTFT first / median | Prompt tokens (cached / fresh) | Output tokens | Decode | E: read | Lines changed (reference) | Over-eng. | False success |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | pass | 25/25 | 10.3 min (8.8) | 66.8 s / 51.1 s | 74,022 (57,048 / 16,974) | 1,292 | 3.98 tok/s | 622 GB | 5 (5) | no | no |
| T3 | pass | 25/25 | 18.0 min (28.4) | 42.6 s / 42.6 s | 71,973 (63,853 / 8,120) | 3,154 | 4.05 tok/s | 1,084 GB | 73 (91) | no | no |
| T4 | **fail** | 27/28 | 11.6 min (20.6) | 31.1 s / 31.1 s | 45,777 (42,079 / 3,698) | 1,930 | 4.14 tok/s | 651 GB | 30 (26) | no | yes, see below |
| T5 | pass | 21/21 | 14.2 min (25.0) | 38.2 s / 24.8 s | 135,266 (124,017 / 11,249) | 2,388 | 4.07 tok/s | 862 GB | 2 (2) | no | no |

- 3 of 4 solved, 54.1 minutes against 82.8 for the same tasks in Run 1 (-35%); no test file changed.
- T4: the model's last message pasted the real visible test output (`32 passed in 0.11s`), as the prompt asks; the
  hidden test `test_task_split_walks_priority_and_stops_when_covered` failed. The rule flags it; the claim itself is true
  for the tests it could see. In Run 1 it passed T4 after writing extra tests of its own.

### Follow-up: 5 experts (changes model quality), Run 1's three shortest tasks

| Task | Result | Hidden tests | Wall (6 experts) | TTFT first / median | Prompt tokens (cached / fresh) | Output tokens | Decode (6 experts) | E: read | Lines changed (reference) | Over-eng. | False success |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | pass | 25/25 | 8.8 min (8.8) | 0.3 s / 22.3 s | 98,863 (85,126 / 13,737) | 1,450 | 4.88 tok/s (3.07) | 522 GB | 5 (5) | no | no |
| T4 | pass | 28/28 | 15.6 min (20.6) | 0.4 s / 5.9 s | 94,596 (87,671 / 6,925) | 3,908 | 5.16 tok/s (3.81) | 894 GB | 36 (26) | yes: added 48 test lines | no |
| T5 | pass | 21/21 | 18.2 min (25.0) | 0.4 s / 11.1 s | 194,100 (180,931 / 13,169) | 3,740 | 4.66 tok/s (3.80) | 983 GB | 2 (2) | yes: added 12 test lines | no |

Note: the first-turn TTFTs of 0.3-0.4 s are prefix-cache hits left by the earlier runs of the same tasks, not a property of 5 experts.

5 experts uses 5 of the model's 6 experts per token, so answers differ from the full model. Here it solved the same
three tasks, 25-37% faster in decode. Each first turn was nearly all cached from the earlier runs (hence TTFT 0.3-0.4 s).

## Limits

- One rep per task; the Qwen runs had two. Sampling is the server default (opencode sends no temperature), so a repeat
  can differ.
- The first coding attempts (`coding-bench/runs/C-tc-on`, `C-notc`, `C-nowmma`) were stopped by the NaN fault and are kept
  as evidence; they are not in the tables.
- Not tested: Linux, more than one conversation at a time.

## Phase 3 (2026-11-09): stock files, low effort, NaN recovery, Qwen on 0.1.58

### Is the NaN fault the engine or the uncensored shards? The engine.

ISTA-DASLab's stock IQ1_M shards 3 and 4 at Strata's pinned revision `cb02422c` (42.2 GB; SHA-256 match Strata's pins),
with the same shards 1-2, Engram table and drafter (hard links), in their own pack (`--data-dir E:\strata-dsv41\stock`;
its `ds4.txt` and the engine log name the stock folder). Gate G config 2 as-is: experts on the card, matrix cores on.

| Test (stock files) | NaN stops |
|---|---|
| `garbage_repro.py`, 3 fully fresh replays (20,362 tokens) | 0 of 3 |
| `nan_repro.py`, 3 fresh prompts (19,900 tokens) | **1 of 3** |
| 3 short prompts x 2 rounds right after that stop | **4 of 6**, each at the same token in both rounds |
| the same 6 after a server restart | 0 of 6 |

The stock files fail too, so the fault is in the engine's expert path on the card. Once, a NaN stop left the server
failing on later short prompts until a restart. A second stop (AtomicChat files, see the recovery check below) did not.
Draft reports, not posted: `phase3/nan-5259-comment.md` (for Strata issue #5259, the same error on RTX 40 cards) and
`phase3/nan-4519-xref.md`.

**Speed if the fault were fixed** (stock files, experts on the card, fresh server; `gateG/measure.py`, 256-token answers):
decode 4.85 tok/s round-2 median (4.67, 4.85, 5.08), 54-74 GB read from E: per answer, fresh prompts read at 155-206 tok/s.
All experts on the CPU: 4.13 tok/s and 83-104 tok/s.

### T2 and T6 at low reasoning effort (all experts on the CPU)

`run_task.py --effort low` (opencode `reasoningEffort: low`; DeepSeek's template turns it into a budget of 50, against
62 for medium: a hint in the prompt, not a cap). Thinking tokens per request come from Strata's server log (opencode
reports 0 for this provider).

| Task | Result | Score (medium) | Wall | TTFT first / median | Prompt tokens (cached / fresh) | Output tokens | Thinking total / largest turn | Decode | E: read | NaN stops |
|---|---|---|---|---|---|---|---|---|---|---|
| T2 | DNF | 0.82 (0.86) | 45.0 min | 69.6 s / 3.2 s | 638,479 (609,608 / 28,871) | 9,574 | 4,927 / 2,128 | 4.17 tok/s | 2,662 GB | 0 |
| T6 | DNF | 0.00 (0.00) | 45.0 min | 34.9 s / 56.2 s | 64,972 (50,786 / 14,186) | 10,146 | 9,618 / 9,452 | 4.24 tok/s | 2,478 GB | 0 |
| T1 | fail | 0.72 (1.00) | 2.1 min | 29.5 s / 29.5 s | 6,773 (6,374 / 399) | 152 | 99 / 76 | 2.91 tok/s | 118 GB | 0 |

- Low effort did not shorten the thinking that ran T6 out of time: one turn thought for 9,452 tokens (8,747 at medium).
- T1 ended on its second turn: the model wrote its tool call as plain text in a broken mixed format
  (`<function=let me look at the directory structure.>` with a stray `</｜DSML｜ parameter>`), so opencode took it as the
  final answer. The score is the untouched code's. One rep; this did not happen at medium.

### NaN recovery in run_task.py, and T1 with experts on the card

For a model with a `relaunch` script (`C-gpu`: Gate G config 2 as-is, `gateH/relaunch-gpu.ps1`), `run_task.py` watches
Strata's server log. On "numbers went non-finite" it suspends opencode, restarts the engine with the same flags, waits
until `/v1/models` answers and resumes opencode, whose own retry re-sends the request. Each restart is logged in
`run.json` (`nan_restarts`: turn number, the failed request's prompt and fresh tokens, restart time). After 3 restarts the
run ends as `DNF-NaN`.

| Run | Result | Wall | TTFT first / median | Prompt tokens (cached / fresh) | Output tokens | Decode | E: read | NaN stops / restarts |
|---|---|---|---|---|---|---|---|---|
| C-gpu T1 (experts on the card) | pass, 25/25 | 10.6 min | 50.6 s / 54.1 s | 84,693 (68,114 / 16,579) | 1,283 | 4.62 tok/s | 661 GB | 0 / 0 |
| C T1 (Run 1, experts on the CPU) | pass, 25/25 | 8.8 min | | | 1,138 | 3.07 tok/s | 468 GB | 0 |

Decode is 50% faster with experts on the card. The wall time is not shorter, because this run took more turns and read
more fresh tokens.

No NaN came up in that run, so the recovery was checked on its own (`gateH/recovery_check.py`, `recovery-check.log`).
`nan_repro.py` gave a real NaN stop on its second try. `nan_restart()` froze a stand-in process, restarted the engine
(166 s), waited until it answered and resumed the stand-in. There were no NaN lines afterwards. Not checked: opencode's
own retry after a restart in a real run. Also, in this check the record's "failed request" fields named the last request
before the restart, which was a later one. In a run the restart follows the stop within about 5 s.

Restart time does not count against the 45-minute limit: opencode is frozen during a restart, so `run_task.py` subtracts
`restart_s` from the elapsed time before the limit check. `run.json` keeps `wall_s` (everything), `restart_s_total` and
`wall_s_excl_restarts`. Before this change a restart did count, but no run had one, so no earlier result changes.

### T6 with opencode's output limit at 8,192 (`C-gpu-out8k`)

`run_task.py --model C-gpu --output 8192`: medium effort, experts on the card, NaN recovery on. The output limit goes
into opencode's model config (its `max_tokens`). Strata then caps thinking at 6,144 of the 8,192 ("thinking capped at
6144 of max_tokens 8192 to leave room for the answer", server log).

| Run | Result | Wall | Turns | Thinking total / largest turn | Output tokens | Decode | E: read | NaN stops / restarts |
|---|---|---|---|---|---|---|---|---|
| C-gpu-out8k T6 | DNF (time limit), 0/10, visible 30/30 | 45.0 min | 7 | 10,381 / 5,484 | 11,593 | 4.99 tok/s | 2,461 GB | 0 / 0 |
| C T6 (Run 1, output 16,384, experts on the CPU) | DNF (time limit), 0/10 | 45.0 min | | largest 8,747 | | | | 0 |

Thinking tokens per request (server log): 96, 6, 0, 14, 34, 5,484, 4,747. The sixth request ended normally under the cap
(5,484 thinking + 659 answer = 6,143 tokens, 21.5 min). The seventh was still thinking when the time limit cut it
(4,752 tokens, 16.4 min). The model never wrote `tests/test_reports.py`, the file the task asks for. So the cap kept a
single turn under about 6K thinking tokens, but at 5 tok/s two such turns take 38 minutes and the task still ran out of
time. One rep.

**Conclusion:** at about 5 tok/s, a task that needs more than about 5,000 output tokens in a turn or two does not fit in
45 minutes, whatever the output limit.

### Qwen3.8-Flash-Next Coder IQ1_M: 0.1.45 vs 0.1.58, same config

Engine 0.1.58 (`C:\Strata\components\engine\0.1.58-windows-x86_64-hip-rdna3`) with every engine argument of the locked
`coding-bench/configs/model-a.json`, run by the Terminal 0.2.12 server (`phase3-qwen/model-a-058.json`). Every flag still
exists. `--vram-reserve-mib` is no longer listed in `--help`, but the engine still parses it (`src/program/generate.cpp`).
Same hipBLASLt table (byte-identical), same expert profile. DeepSeek stopped and Brave closed; other processes held 148 MB
of graphics memory (Claude 58, dwm 36, Explorer 35 MB). 1 warm-up + 3 timed requests, each with a unique first line
(`cache_n` 0), medians:

| Prompt | 0.1.45 prompt tok/s | 0.1.58 prompt tok/s | 0.1.45 output tok/s | 0.1.58 output tok/s |
|---|---|---|---|---|
| Short (948 tokens, 512 out) | 636 | 658 | 72.4 | 73.6 |
| 8K (context test, up to 4,096 out) | 1,575 | 1,543 | 80.3 | 83.5 |
| 16K (512 out) | 1,621 | 1,588 | 68.2 | 72.5 |

0.1.45 numbers: `results/tuning-summary.jsonl` (`A-v045-r1792-cpushare-short`, `A-v045-final`) and
`results/context-runs.jsonl` (A, 8k). The short row's 0.1.45 arm did not have `--prefill auto:16384`, which does not change
a 948-token prompt. On 0.1.58, prompt reading is 3.5% faster on the short prompt and 2% slower at 8K and 16K. Output is 2-6% faster. The 8K answers were not
graded this time.

## Files

`gateG/` (report, scripts, all answers), `gateH/` (run scripts, the two NaN reproducers and their results, the run logs,
`gateH-results.json`), `build/`. Per-run data: `coding-bench/runs/C`, `C-smallest`, `C5` (each has `run.json`,
`turns.json` with every turn's cached / fresh tokens and prompt time, `engine.log`, `server.log`, `stream.jsonl`,
`score.json` and the model's work).
