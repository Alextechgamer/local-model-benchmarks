"""Print the per-run table (markdown) and per-model averages from results/coding.json."""
import json

c = json.load(open(r"E:\strata-tests\coding-bench\results\coding.json", encoding="utf-8"))
print("| Run | Score | Hidden tests / mutants | Time | Steps | Input tokens | Cache-read tokens | Output tokens | Ran tests | Wh | Cost |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for r in sorted(c["runs"], key=lambda r: (r["model"], r["task"], r["rep"])):
    h, m = r["hidden"], r["mutation"]
    hs = f"{h['passed']}/{h['total']}" if h else f"{m['killed']}/{m['mutant_total']} mutants"
    t = r["tokens"]
    print(f"| {r['model']}-{r['task']}-r{r['rep']} | {r['score']:.2f} | {hs} | {r['wall_s'] / 60:.1f} min | {r['steps']} | "
          f"{t['input']:,} | {t['cache_read']:,} | {t['output']:,} | {'yes' if r['ran_visible_tests'] else 'no'} | "
          f"{r['energy']['total_wh']:.1f} | ${r['cost_usd']:.4f} |")
for mdl in "AB":
    rs = [r for r in c["runs"] if r["model"] == mdl]
    n = len(rs)
    print(mdl, "mean input", sum(r["tokens"]["input"] for r in rs) // n, "cache", sum(r["tokens"]["cache_read"] for r in rs) // n,
          "output", sum(r["tokens"]["output"] for r in rs) // n, "mean Wh", round(sum(r["energy"]["total_wh"] for r in rs) / n, 1),
          "mean cost", round(sum(r["cost_usd"] for r in rs) / n, 5),
          "GPU mean W", round(sum(r["energy"]["gpu_mean_w"] for r in rs) / n),
          "CPU mean W", round(sum(r["energy"]["cpu_mean_w"] for r in rs) / n))
