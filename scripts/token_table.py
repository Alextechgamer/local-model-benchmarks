"""Total tokens, cost and browser-check results for every run, from the saved opencode / Claude Code streams.

usage (from the folder that holds the pagoda-*-stream.jsonl files and shots/): python token_table.py
Writes token-cost-table.json and prints the markdown table used in the README.

Definitions
  input        uncached input tokens           cache read   tokens re-read from the prompt cache (agents re-read context every step)
  output       generated tokens, thinking included
  reported     opencode's own `cost` field (list price); 0 for free models. Claude Code's cost field is NOT used: it prices local-model tokens as Anthropic's.
  at Luna      the same tokens priced at GPT-6 Luna list prices ($/1M: input 0.10, output 0.50, cache read 0.01, cache write 0.125): a hypothetical, only there
               so free, local and paid runs share one price scale. It reproduces opencode's reported cost for the Luna runs exactly.
"""
import glob, json, re

LUNA = dict(inp=0.10, out=0.50, cr=0.01, cw=0.125)


def scan(paths):
    t = dict(inp=0, out=0, cr=0, cw=0, cost=0.0)
    for path in paths:
        for line in open(path, encoding="utf-8", errors="replace"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") == "step_finish":                       # opencode
                p = e["part"]; k = p.get("tokens") or {}; c = k.get("cache") or {}
                t["inp"] += k.get("input", 0); t["out"] += k.get("output", 0) + k.get("reasoning", 0)
                t["cr"] += c.get("read", 0); t["cw"] += c.get("write", 0); t["cost"] += p.get("cost") or 0
            elif e.get("type") == "result" and "usage" in e:          # Claude Code (stream-json)
                u = e["usage"]
                t["inp"] += u.get("input_tokens", 0); t["out"] += u.get("output_tokens", 0)
                t["cr"] += u.get("cache_read_input_tokens", 0); t["cw"] += u.get("cache_creation_input_tokens", 0)
    return t


def span(paths):  # wall time from event timestamps, for runs whose harness did not record it
    ts = []
    for p in paths:
        for line in open(p, encoding="utf-8", errors="replace"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if isinstance(e.get("timestamp"), (int, float)):
                ts.append(e["timestamp"] / 1000)
    return round(max(ts) - min(ts)) if ts else None


def chk(label):
    try:
        d = json.load(open(f"shots/{label}.json", encoding="utf-8"))
    except OSError:
        return None
    p = d.get("page") or {}; txt = (p.get("text") or "") + " ".join(d.get("logs", []))
    v = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]{3,6}", txt) if 5000 <= int(x.replace(",", "")) <= 60000]
    return dict(errors=len(d["console_errors"]) + len(d["exceptions"]), voxels=v[0] if v else None, canvas=bool(p.get("canvases")))


rows = []
def add(group, run, model, paths, secs, label, note="", tokens=True):
    rows.append(dict(group=group, run=run, model=model, secs=secs, tokens=scan(paths) if tokens else None,
                     check=chk(label) if label else None, note=note))

add("paid", "gpt-6-luna #1", "gpt-6-luna", ["pagoda-luna-stream.jsonl"], 283, "luna")
add("paid", "gpt-6-luna #2", "gpt-6-luna", ["pagoda-luna2-stream.jsonl"], 22, None, "stopped after a design note, waiting for approval")
add("paid", "gpt-6-luna #3", "gpt-6-luna", ["pagoda-luna-r2-stream.jsonl"], 437, "luna-r2")
add("paid", "glm-5.3-flash", "glm-5.3-flash", ["pagoda-glm-stream.jsonl"], 901, None, "timed out, no step finished", tokens=False)
add("paid", "deepseek-v4.1-flash", "deepseek-v4.1-flash", ["pagoda-deepseek-stream.jsonl"], 999, "deepseek")
secs3 = {}
for f in glob.glob("pagoda-*-r3-time.txt"):
    m = re.search(r"(\S+) exit (\d+) elapsed (\d+)", open(f).read()); secs3[m[1]] = int(m[3])
FREE = [("muse", "muse-spark-1.3"), ("longcat", "longcat-2.5"), ("nemolight", "nemotron-3.5-lightning"), ("bunny", "space-bunny"),
        ("pickle", "big-pickle"), ("mimo", "mimo-v2.6-flash"), ("step5", "step-5-preview"), ("nemoultra", "nemotron-3-ultra"),
        ("ling31", "ling-3.1-flash"), ("ling30", "ling-3.0-flash-fin"), ("exo", "exo")]
for n, model in FREE:
    add("free-pass1", model, model, [f"pagoda-{n}-r3-stream.jsonl"], secs3.get(f"{n}-r3"), f"{n}-r3" if n in ("muse", "longcat", "nemolight") else None)
for n, model in [("ling31", "ling-3.1-flash"), ("pickle", "big-pickle"), ("mimo", "mimo-v2.6-flash"), ("bunny", "space-bunny"),
                 ("step5", "step-5-preview"), ("nemoultra", "nemotron-3-ultra"), ("nemolight", "nemotron-3.5-lightning"), ("ling30", "ling-3.0-flash-fin")]:
    p = f"pagoda-{n}-r4-stream.jsonl"   # cumulative: includes the repair attempts
    add("free-pass2", model, model, [p], span([p]) if n != "ling30" else None, f"{n}-r4" if n != "ling30" else None)
add("orchestrated", "5 modules + 4 fix rounds", "muse + longcat + space-bunny", sorted(glob.glob("orch-r1/m-*/stream.jsonl")), None, "orch-v3",
    "lead (Claude) tokens not included")
add("local", "claude-code run 1", "flash-next IQ1_M", ["pagoda-local-stream.jsonl"], 2647, "local1")
add("local", "claude-code run 2", "flash-next IQ1_M", ["pagoda-local2-stream.jsonl"], 1210, "local2")
add("local", "claude-code guided (5 stages)", "flash-next IQ1_M", [f"guided/{s}.jsonl" for s in ("s1", "s1fix", "s2", "s3", "s4", "s5")], 3799, "guided")
add("local", "opencode", "flash-next IQ1_M", ["oc-flashnext-stream.jsonl"], 2921, "ocflash")
add("local", "opencode 27B", "qwen3.8-27b IQ4_XS", [], 3753, "oc27b", "token total not recorded (saved export is a partial snapshot)", tokens=False)

for r in rows:
    t = r["tokens"]
    if t:
        r["eq_luna"] = sum(t[k] * LUNA[k] for k in ("inp", "out", "cr", "cw")) / 1e6
json.dump(rows, open("token-cost-table.json", "w"), indent=1)


def mmss(s): return "-" if s is None else f"{s // 60}m {s % 60:02d}s"
def k(n): return "n/a" if n is None else (f"{n / 1e6:.2f}M" if n >= 1e6 else f"{n / 1e3:.0f}k" if n >= 1e4 else f"{n:,}")
def usd(x): return "n/a" if x is None else f"${x:.3f}"

names = {"paid": "Paid cloud", "free-pass1": "Free cloud, one shot", "free-pass2": "Free cloud, re-run", "orchestrated": "Orchestrated (free)", "local": "Local"}
print("| Group | Run | Time | Input | Cache read | Output + thinking | Reported cost | Same tokens at Luna prices | Errors | Voxels |")
print("|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    c, t = r["check"], r["tokens"]
    if not (c and c.get("canvas")):
        continue
    cost = usd(t["cost"]) if r["group"] == "paid" else ("$0*" if r["group"] == "local" else "$0")
    name = r["run"] if r["group"] in ("paid", "orchestrated", "local") else r["model"]
    print(f"| {names[r['group']]} | {name} | {mmss(r['secs'])} | {k(t and t['inp'])} | {k(t and t['cr'])} | {k(t and t['out'])} | {cost} | {usd(r.get('eq_luna'))} | {c['errors']} | {c['voxels']:,} |")
