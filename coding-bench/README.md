# Local coding benchmark: Qwen3.8-Flash-Next Coder IQ1_M (Strata) vs Qwen3.8-27B IQ4_XS (llama.cpp)

Run on an RX 7900 XT 20 GB, Ryzen 9 5900X, 64 GB RAM, Windows 11, 2026-10-19/20. Start with [REPORT.md](REPORT.md);
[SETUP.md](SETUP.md) gives every setting and its source.

| Folder | What it holds |
|---|---|
| `tasks/`, `hidden/`, `reference/`, `project/` | the inventory-service project, 6 tasks, hidden tests, reference solutions and T6 mutants (frozen: `FROZEN.txt`, checked by `validate.py`) |
| `runs/A`, `runs/B` | every coding run: the opencode stream, stderr, prompt, final work tree and score |
| `context/` | the context-size prompts (8K-250K, planted facts at 10/50/90%) |
| `results/` | tuning, coding, context and power results (JSON) and the chart |
| `logs/` | tuning, phase and server logs |
| `configs/`, `tools/` | the locked server configs and start scripts, and the scripts that built, ran and scored everything |

Left out: the downloaded llama.cpp/Strata builds and the Strata 0.1.45 worktree (in `tools/` locally, ~4.8 GB),
the scoring scratch copies and the raw power CSVs (their totals are in `results/power.json`).

The tuning prompts (`tools/prompt-*.txt`) contain source code of [Strata](https://github.com/Niko1221/Strata),
MIT License, Copyright (c) 2026 Niko1221 and the Strata contributors.
