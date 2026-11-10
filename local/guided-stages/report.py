"""Print what one guided stage did: the page check and the Claude Code result line."""
import collections, json, sys
from pathlib import Path

name = sys.argv[1]
root = Path(__file__).parent.parent
d = json.loads((root / "shots" / f"g-{name}.json").read_text(encoding="utf-8"))
p = d.get("page") or {}
print("errors:", d["console_errors"][:4], "| exceptions:", d["exceptions"][:3])
print("logs:", d["logs"][:3], "| fps", d.get("measured_fps_headless"))
print("voxelText:", p.get("voxelText"), "| sliders", p.get("sliders"), "| checkboxes", p.get("checkboxes"),
      "| buttons", p.get("buttons"))
tools = collections.Counter(); res = None; init = None
for line in (root / "guided" / f"{name}.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
    try:
        o = json.loads(line)
    except Exception:
        continue
    if o.get("type") == "system" and o.get("subtype") == "init":
        init = o
    elif o.get("type") == "assistant":
        for c in o["message"]["content"]:
            if c["type"] == "tool_use":
                tools[c["name"]] += 1
    elif o.get("type") == "result":
        res = o
if init:
    print("session: tools", len(init.get("tools") or []), "| skills", len(init.get("skills") or []),
          "| plugins", len(init.get("plugins") or []))
print("tool calls:", dict(tools))
if res:
    u = res.get("usage") or {}
    print("result:", res.get("subtype"), "| turns", res.get("num_turns"), "| in", u.get("input_tokens"), "| cached",
          u.get("cache_read_input_tokens"), "| out", u.get("output_tokens"), "|",
          str(res.get("result"))[:300].replace("\n", " "))
