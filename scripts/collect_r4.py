"""Collect the third-pass pagoda runs: find each model's page, check it in the browser, print one table.

usage: .chk/Scripts/python.exe collect_r4.py [--no-check]
A page counts wherever the model left it: pagoda.html, any other .html in its folder, or an HTML block in its
chat reply (saved as pagoda.html, since the prompt asks for "the complete HTML file in one code block").
Writes r4-results.json; check_page.py writes shots/<label>-day.png, -pond.png, -night.png and shots/<label>.json.
"""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent
MODELS = [("pickle", "big-pickle"), ("exo", "exo-free"), ("ling30", "ling-3.0-flash-fin-free"),
          ("ling31", "ling-3.1-flash-free"), ("longcat", "longcat-2.5-preview-free"), ("mimo", "mimo-v2.6-flash-free"),
          ("muse", "muse-spark-1.3-contributor-free"), ("nemoultra", "nemotron-3-ultra-free"),
          ("nemolight", "nemotron-3.5-lightning-free"), ("bunny", "space-bunny-free"), ("step5", "step-5-preview-free")]


def read_stream(path: Path) -> dict:
    s = {"steps": 0, "tools": 0, "out_tokens": 0, "reasoning_tokens": 0, "last_reason": None, "error": None, "text": []}
    if not path.exists():
        return s
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        t = e.get("type")
        if t == "text":
            s["text"].append(e["part"].get("text", ""))
        elif t == "tool_use":
            s["tools"] += 1
        elif t == "step_finish":
            tok = e["part"].get("tokens") or {}
            s["steps"] += 1; s["out_tokens"] += tok.get("output", 0); s["reasoning_tokens"] += tok.get("reasoning", 0)
            s["last_reason"] = e["part"].get("reason")
        elif t == "error":
            d = e.get("error", {}).get("data", {})
            s["error"] = f"{d.get('statusCode') or ''} {str(d.get('message'))[:140]}".strip()
    return s


def find_page(folder: Path, text: str) -> tuple[Path | None, str]:
    page = folder / "pagoda.html"
    if page.exists():
        return page, "file"
    others = sorted(folder.rglob("*.html"), key=lambda p: p.stat().st_size, reverse=True) if folder.exists() else []
    if others:
        return others[0], f"file ({others[0].name})"
    blocks = re.findall(r"<!DOCTYPE html.*?</html>", text, flags=re.S | re.I)
    if blocks:
        folder.mkdir(exist_ok=True)
        page.write_text(max(blocks, key=len), encoding="utf-8")
        return page, "chat reply"
    return None, "none"


rows = []
for name, model in MODELS:
    label = f"{name}-r4"
    folder = ROOT / f"pagoda-{label}"
    timing = ROOT / f"pagoda-{label}-time.txt"
    m = re.search(r"exit (\d+) elapsed (\d+)", timing.read_text()) if timing.exists() else None
    s = read_stream(ROOT / f"pagoda-{label}-stream.jsonl")
    page, source = find_page(folder, "\n".join(s.pop("text")))
    row = {"label": label, "model": model, "exit": int(m[1]) if m else None, "secs": int(m[2]) if m else None,
           "page": source, **s}
    if page:
        row["kb"] = round(page.stat().st_size / 1024, 1)
        if "--no-check" not in sys.argv:
            subprocess.run([sys.executable, str(ROOT / "check_page.py"), label, str(page), "Pond"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
        chk = ROOT / "shots" / f"{label}.json"
        if chk.exists():
            c = json.loads(chk.read_text(encoding="utf-8")); p = c.get("page") or {}
            vox = [int(n.replace(",", "")) for t in [p.get("text", ""), *c.get("logs", [])]
                   for n in re.findall(r"\d[\d,]{3,6}", t) if 5000 <= int(n.replace(",", "")) <= 60000]
            row.update(errors=len(c["console_errors"]) + len(c["exceptions"]), first_error=(c["exceptions"] + c["console_errors"] + [None])[0],
                       canvases=len(p.get("canvases", [])), sliders=p.get("sliders"), checkboxes=p.get("checkboxes"),
                       buttons=len(p.get("buttons", [])), voxels=vox[0] if vox else None, title=p.get("hasJapaneseTitle"),
                       loading_stuck=p.get("loadingVisible"), fps=c.get("measured_fps_headless"))
    rows.append(row)

(ROOT / "r4-results.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
cols = ["model", "exit", "secs", "steps", "tools", "out_tokens", "reasoning_tokens", "last_reason", "page", "kb", "errors",
        "canvases", "voxels", "sliders", "checkboxes", "buttons", "title", "loading_stuck", "fps"]
print(" | ".join(cols))
for r in rows:
    print(" | ".join("" if r.get(c) is None else str(r[c]) for c in cols))
for r in rows:
    for k in ("error", "first_error"):
        if r.get(k):
            print(f"{r['model']} {k}: {r[k][:200]}")
